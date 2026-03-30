"""Command-line interface for Change Impact Analyzer.

Exit codes
----------
- **0** — success
- **1** — high-risk threshold exceeded
- **2** — runtime / configuration error
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from cia import __version__

console = Console()

_SKIP_DIRS = {"__pycache__", ".git", ".tox", "node_modules", ".venv", "venv",
              ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist", "build",
              ".eggs", ".egg-info"}


def _build_project_graph(
    repo_path: Path,
    *,
    verbose: bool = False,
) -> "DependencyGraph":
    """Parse every ``.py`` file under *repo_path* and return a populated graph."""
    from cia.graph.dependency_graph import DependencyGraph
    from cia.parser.python_parser import PythonParser

    parser = PythonParser()
    py_files = sorted(
        p for p in repo_path.rglob("*.py")
        if not any(part in _SKIP_DIRS for part in p.parts)
    )
    modules = []
    for pf in py_files:
        try:
            modules.append(parser.parse_file(pf))
        except Exception:  # noqa: BLE001
            if verbose:
                console.print(f"[dim]  skip (parse error): {pf}[/dim]")
    graph = DependencyGraph()
    graph.build_from_modules(modules)
    if verbose:
        console.print(
            f"[dim]  Graph: {graph.module_count} modules, "
            f"{graph.dependency_count} edges[/dim]"
        )
    return graph


def _approximate_coverage(
    repo_path: Path,
    graph: "DependencyGraph",
) -> dict[str, float]:
    """Build a rough coverage map from test-file imports.

    Modules imported by at least one test file get 60%; others get 0%.
    This is a heuristic — real coverage data should override it.
    """
    from cia.analyzer.test_analyzer import TestAnalyzer

    ta = TestAnalyzer()
    mapping = ta.build_test_mapping(repo_path, graph)
    covered: set[str] = set()
    for m in mapping.values():
        covered.update(m.covered_modules)
    result: dict[str, float] = {}
    for mod in graph.get_all_modules():
        result[mod] = 60.0 if mod in covered else 0.0
    return result

def _extract_changed_symbols(
    changeset: "ChangeSet",
    repo_path: Path,
) -> list[dict[str, str]]:
    """Parse changed ``.py`` files and return symbols whose lines overlap the diff.

    Each entry is a dict with keys ``module``, ``name``,
    ``qualified_name``, and ``symbol_type``.
    """
    import ast

    symbols: list[dict[str, str]] = []
    for change in changeset.changes:
        if not str(change.file_path).endswith(".py"):
            continue
        abs_path = repo_path / change.file_path
        if not abs_path.exists():
            continue
        try:
            source = abs_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(abs_path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        changed_lines = set(change.added_lines)
        module_stem = change.file_path.stem
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(ln in changed_lines
                       for ln in range(node.lineno, node.end_lineno + 1)):
                    # Determine qualified name (ClassName.method or just func)
                    sym_type = "function"
                    qual = f"{module_stem}::{node.name}"
                    # Check if nested inside a class
                    for cls_node in ast.walk(tree):
                        if isinstance(cls_node, ast.ClassDef):
                            if node in ast.walk(cls_node) and node is not cls_node:
                                qual = f"{module_stem}::{cls_node.name}.{node.name}"
                                sym_type = "method"
                                break
                    symbols.append({
                        "module": module_stem,
                        "name": node.name,
                        "qualified_name": qual,
                        "symbol_type": sym_type,
                    })
    return symbols


# Exit-code constants
EXIT_OK = 0
EXIT_HIGH_RISK = 1
EXIT_ERROR = 2


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version=__version__, prog_name="cia")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """Change Impact Analyzer — Predict the impact of code changes."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# ---------------------------------------------------------------------------
# cia analyze
# ---------------------------------------------------------------------------


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "html", "markdown", "all"]),
    default="json",
    help="Output format (use 'all' to generate every format).",
)
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output file path (or base name for 'all').")
@click.option("--unstaged", is_flag=True, help="Include unstaged changes.")
@click.option("--commit-range", default=None,
              help="Analyze a specific commit range (e.g. HEAD~3..HEAD).")
@click.option("--threshold", type=int, default=None,
              help="Fail if risk score exceeds this value (0-100).")
@click.option("--explain", is_flag=True,
              help="Show detailed risk breakdown.")
@click.option("--test-only", is_flag=True,
              help="Only show test recommendations (skip full report).")
@click.pass_context
def analyze(
    ctx: click.Context,
    path: str,
    output_format: str,
    output: str | None,
    unstaged: bool,
    commit_range: str | None,
    threshold: int | None,
    explain: bool,
    test_only: bool,
) -> None:
    """Analyze the impact of staged (or unstaged / commit-range) changes."""
    from cia.analyzer.change_detector import ChangeDetector
    from cia.analyzer.impact_analyzer import ImpactAnalyzer
    from cia.git.git_integration import GitIntegration
    from cia.graph.dependency_graph import DependencyGraph
    from cia.report.html_reporter import HtmlReporter
    from cia.report.json_reporter import JsonReporter
    from cia.report.markdown_reporter import MarkdownReporter
    from cia.risk.risk_scorer import RiskScorer

    verbose = ctx.obj.get("verbose", False)
    repo_path = Path(path).resolve()

    if verbose:
        console.print(f"[bold]Analyzing changes in:[/bold] {repo_path}")
        console.print(f"[bold]Output format:[/bold] {output_format}")

    # --- Git setup ---
    try:
        git = GitIntegration(repo_path)
        if not git.is_git_repository():
            console.print(
                "[red]Error:[/red] Not a Git repository.\n"
                "  Hint: Run [bold]git init[/bold] first, or pass the path "
                "to an existing repo.\n"
                "  See: https://github.com/Eng-Elias/change_impact_analyzer#quick-start"
            )
            ctx.exit(EXIT_ERROR)
            return
    except (ValueError, Exception) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        ctx.exit(EXIT_ERROR)
        return

    detector = ChangeDetector()

    # --- Detect changes (with progress spinner) ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
        disable=not verbose,
    ) as progress:
        progress.add_task("Detecting changes…", total=None)

        if commit_range:
            if verbose:
                console.print(f"[bold]Commit range:[/bold] {commit_range}")
            try:
                changeset = detector.detect_changes_for_range(git, commit_range)
            except ValueError as exc:
                console.print(
                    f"[red]Error:[/red] {exc}\n"
                    "  Hint: Use the format [bold]REF1..REF2[/bold] "
                    "(e.g. HEAD~3..HEAD or main..feature-branch)."
                )
                ctx.exit(EXIT_ERROR)
                return
        else:
            changeset = detector.detect_changes(git, staged=not unstaged)

    # --- Build dependency graph ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
        disable=not verbose,
    ) as progress:
        progress.add_task("Building dependency graph…", total=None)
        dep_graph = _build_project_graph(repo_path, verbose=verbose)
        coverage_data = _approximate_coverage(repo_path, dep_graph)

    # --- Risk scoring ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
        disable=not verbose,
    ) as progress:
        progress.add_task("Scoring risk…", total=None)
        scorer = RiskScorer()
        risk = scorer.calculate_risk(
            changeset, graph=dep_graph, coverage_data=coverage_data,
        )

    # --- Build ImpactReport ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
        disable=not verbose,
    ) as progress:
        progress.add_task("Building impact report…", total=None)
        analyzer_engine = ImpactAnalyzer(dep_graph)
        impact_report = analyzer_engine.analyze_change_set(
            changeset, risk_score=risk,
        )

    # --- Test-only mode ---
    if test_only:
        tests = impact_report.affected_tests or []
        if not tests:
            console.print("[green]No tests affected by the current changes.[/green]")
        else:
            console.print(f"[bold]Affected tests ({len(tests)}):[/bold]")
            for t in tests:
                console.print(f"  • {t}")
        if impact_report.recommendations:
            console.print("\n[bold]Recommendations:[/bold]")
            for rec in impact_report.recommendations:
                console.print(f"  - {rec}")
        return

    # --- Generate report(s) ---
    def _write_or_print(content: str, ext: str) -> None:
        if output:
            base = Path(output)
            out_path = (
                base.with_suffix(f".{ext}")
                if output_format == "all"
                else base
            )
            out_path.write_text(content, encoding="utf-8")
            console.print(f"[green]Report written to {out_path}[/green]")
        elif ext == "json":
            click.echo(content)
        else:
            console.print(content)

    formats_to_generate = (
        ["json", "html", "markdown"] if output_format == "all"
        else [output_format]
    )

    for fmt in formats_to_generate:
        if fmt == "json":
            content = JsonReporter().generate(impact_report)
            _write_or_print(content, "json")
        elif fmt == "html":
            content = HtmlReporter().generate(impact_report)
            _write_or_print(content, "html")
        elif fmt == "markdown":
            content = MarkdownReporter().generate(impact_report)
            _write_or_print(content, "md")

    if explain:
        console.print("\n[bold]Risk Breakdown:[/bold]")
        for line in risk.explanations:
            console.print(f"  {line}")
        if risk.suggestions:
            console.print("\n[bold]Suggestions:[/bold]")
            for s in risk.suggestions:
                console.print(f"  - {s}")

    # --- Threshold enforcement ---
    if threshold is not None and risk.overall_score > threshold:
        console.print(
            f"\n[red]FAIL:[/red] Risk score {risk.overall_score:.1f} "
            f"exceeds threshold {threshold}"
        )
        ctx.exit(EXIT_HIGH_RISK)


# ---------------------------------------------------------------------------
# cia graph
# ---------------------------------------------------------------------------


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["json", "text", "dot"]),
    default="text",
    help="Output format for the graph.",
)
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Write graph to a file instead of stdout.")
@click.pass_context
def graph(
    ctx: click.Context,
    path: str,
    output_format: str,
    output: str | None,
) -> None:
    """Build and display the dependency graph for a project."""
    verbose = ctx.obj.get("verbose", False)
    repo_path = Path(path).resolve()

    if verbose:
        console.print(f"[bold]Building dependency graph for:[/bold] {repo_path}")

    dep_graph = _build_project_graph(repo_path, verbose=verbose)

    if dep_graph.module_count == 0:
        console.print("[yellow]No Python modules found.[/yellow]")
        return

    if output_format == "json":
        content = dep_graph.to_json()
    elif output_format == "dot":
        content = _graph_to_dot(dep_graph)
    else:
        content = _graph_to_text(dep_graph)

    if output:
        Path(output).write_text(content, encoding="utf-8")
        console.print(f"[green]Graph written to {output}[/green]")
    else:
        console.print(content)

    console.print(
        f"\n[bold]{dep_graph.module_count}[/bold] modules, "
        f"[bold]{dep_graph.dependency_count}[/bold] edges"
    )
    cycles = dep_graph.find_cycles()
    if cycles:
        console.print(
            f"[yellow]⚠ {len(cycles)} circular dependency(ies) detected[/yellow]"
        )


def _graph_to_text(dep_graph: "DependencyGraph") -> str:
    """Render the dependency graph as a text tree."""
    from cia.graph.dependency_graph import DependencyGraph

    lines: list[str] = []
    for module in sorted(dep_graph.get_all_modules()):
        deps = dep_graph.get_dependencies(module)
        dependents = dep_graph.get_dependents(module)
        lines.append(f"{module}")
        if deps:
            lines.append(f"  imports: {', '.join(sorted(deps))}")
        if dependents:
            lines.append(f"  used by: {', '.join(sorted(dependents))}")
    return "\n".join(lines)


def _graph_to_dot(dep_graph: "DependencyGraph") -> str:
    """Render the dependency graph in Graphviz DOT format."""
    lines = ["digraph dependencies {", "  rankdir=LR;"]
    for module in sorted(dep_graph.get_all_modules()):
        lines.append(f'  "{module}";')
    for module in sorted(dep_graph.get_all_modules()):
        for dep in sorted(dep_graph.get_dependencies(module)):
            lines.append(f'  "{module}" -> "{dep}";')
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cia install-hook / uninstall-hook
# ---------------------------------------------------------------------------


@main.command("install-hook")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--block-on",
    type=click.Choice(["high", "medium", "low", "none"]),
    default="none",
    help="Risk level at or above which the hook blocks the commit.",
)
@click.option("--force", is_flag=True,
              help="Overwrite an existing pre-commit hook.")
@click.option("--local", "scope", flag_value="local", default=True,
              help="Install in the current repository only (default).")
@click.option("--global", "scope", flag_value="global",
              help="Install in the global Git template directory.")
@click.pass_context
def install_hook(
    ctx: click.Context,
    path: str,
    block_on: str,
    force: bool,
    scope: str,
) -> None:
    """Install the CIA pre-commit hook into the Git repository."""
    from cia.git.hooks import HookManager

    repo_path = Path(path).resolve()

    if scope == "global":
        # Use the Git template directory
        try:
            result = subprocess.run(
                ["git", "config", "--global", "init.templateDir"],
                capture_output=True, text=True, check=False,
            )
            template_dir = result.stdout.strip()
            if not template_dir:
                template_dir = str(Path.home() / ".git-templates")
            hooks_dir = Path(template_dir) / "hooks"
            hooks_dir.mkdir(parents=True, exist_ok=True)
            # Point HookManager at the template dir
            manager = HookManager.__new__(HookManager)
            manager._repo_path = Path(template_dir)
            manager._hooks_dir = hooks_dir
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            ctx.exit(EXIT_ERROR)
            return
    else:
        manager = HookManager(repo_path)

    try:
        # Check for existing non-CIA hook
        if not force and manager.hook_path.exists():
            from cia.git.hooks import _CIA_MARKER
            content = manager.hook_path.read_text(encoding="utf-8")
            if _CIA_MARKER not in content:
                console.print(
                    "[red]Error:[/red] A pre-commit hook already exists. "
                    "Use --force to overwrite."
                )
                ctx.exit(EXIT_ERROR)
                return

        hook_path = manager.install(block_threshold=block_on)
        scope_label = "globally" if scope == "global" else "locally"
        console.print(
            f"[green]Pre-commit hook installed {scope_label}:[/green] {hook_path}"
        )
        if block_on != "none":
            console.print(f"[bold]Blocking threshold:[/bold] {block_on}")
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        ctx.exit(EXIT_ERROR)


@main.command("uninstall-hook")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.pass_context
def uninstall_hook(ctx: click.Context, path: str) -> None:
    """Remove the CIA pre-commit hook from the Git repository."""
    from cia.git.hooks import HookManager

    repo_path = Path(path).resolve()
    manager = HookManager(repo_path)
    if manager.uninstall():
        console.print("[green]Pre-commit hook removed.[/green]")
    else:
        console.print("[yellow]No CIA hook found to remove.[/yellow]")


# ---------------------------------------------------------------------------
# cia test
# ---------------------------------------------------------------------------


@main.command("test")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--affected-only", is_flag=True,
              help="Run only tests affected by current changes.")
@click.option("--suggest", is_flag=True,
              help="Show recommended new tests for uncovered changes.")
@click.option("--unstaged", is_flag=True, help="Include unstaged changes.")
@click.option("--commit-range", default=None,
              help="Analyze a specific commit range.")
@click.pass_context
def test_cmd(
    ctx: click.Context,
    path: str,
    affected_only: bool,
    suggest: bool,
    unstaged: bool,
    commit_range: str | None,
) -> None:
    """Predict affected tests and suggest missing test coverage."""
    from cia.analyzer.change_detector import ChangeDetector
    from cia.analyzer.test_analyzer import TestAnalyzer
    from cia.git.git_integration import GitIntegration

    verbose = ctx.obj.get("verbose", False)
    repo_path = Path(path).resolve()

    try:
        git = GitIntegration(repo_path)
        if not git.is_git_repository():
            console.print(
                "[red]Error:[/red] Not a Git repository.\n"
                "  Hint: Run [bold]git init[/bold] first, or pass the path "
                "to an existing repo."
            )
            ctx.exit(EXIT_ERROR)
            return
    except (ValueError, Exception) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        ctx.exit(EXIT_ERROR)
        return

    detector = ChangeDetector()

    if commit_range:
        try:
            changeset = detector.detect_changes_for_range(git, commit_range)
        except ValueError as exc:
            console.print(
                f"[red]Error:[/red] {exc}\n"
                "  Hint: Use the format [bold]REF1..REF2[/bold] "
                "(e.g. HEAD~3..HEAD)."
            )
            ctx.exit(EXIT_ERROR)
            return
    else:
        changeset = detector.detect_changes(git, staged=not unstaged)

    dep_graph = _build_project_graph(repo_path, verbose=verbose)

    ta = TestAnalyzer()
    test_mapping = ta.build_test_mapping(repo_path, dep_graph)

    changed_modules = [c.file_path.stem for c in changeset.changes]
    # Include transitive dependents so downstream tests are found
    expanded: set[str] = set(changed_modules)
    for mod in changed_modules:
        expanded.update(dep_graph.get_transitive_dependents(mod))
    affected = ta.predict_affected_tests(sorted(expanded), test_mapping)

    # Extract symbols from changed files for method-level suggestions
    changed_symbols = _extract_changed_symbols(changeset, repo_path)

    if affected_only:
        if not affected:
            console.print(
                "[green]No tests affected by the current changes.[/green]"
            )
            return
        expr = ta.generate_pytest_expression(affected)
        args = ta.generate_pytest_args(affected)
        report = {
            "affected_tests": [str(t) for t in affected],
            "pytest_expression": expr,
            "pytest_args": args,
        }
        console.print(json.dumps(report, indent=2))
        if verbose:
            console.print(f'\n[bold]Run:[/bold] pytest -k "{expr}"')
        return

    if suggest:
        suggestions = ta.suggest_missing_tests(
            changed_modules, test_mapping=test_mapping,
            changed_symbols=changed_symbols or None,
        )
        if not suggestions:
            console.print(
                "[green]All changed modules have test coverage.[/green]"
            )
            return
        suggest_report: dict[str, object] = {
            "suggestions": [
                {
                    "entity": s.entity,
                    "reason": s.reason,
                    "suggested_file": s.suggested_file,
                }
                for s in suggestions
            ],
        }
        console.print(json.dumps(suggest_report, indent=2))
        return

    # Default: show both affected tests and suggestions
    suggestions = ta.suggest_missing_tests(
        changed_modules, test_mapping=test_mapping,
        changed_symbols=changed_symbols or None,
    )
    combined_report: dict[str, object] = {
        "affected_tests": [str(t) for t in affected],
        "missing_test_suggestions": [
            {
                "entity": s.entity,
                "reason": s.reason,
                "suggested_file": s.suggested_file,
            }
            for s in suggestions
        ],
    }
    console.print(json.dumps(combined_report, indent=2))


# ---------------------------------------------------------------------------
# cia version
# ---------------------------------------------------------------------------


@main.command("version")
@click.pass_context
def version_cmd(ctx: click.Context) -> None:
    """Show detailed version information."""
    console.print(f"[bold]Change Impact Analyzer[/bold] v{__version__}")
    console.print(f"  Python  : {platform.python_version()}")
    console.print(f"  Platform: {platform.platform()}")
    console.print(f"  CLI     : Click {click.__version__}")


# ---------------------------------------------------------------------------
# cia init
# ---------------------------------------------------------------------------


@main.command("init")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.pass_context
def init_cmd(ctx: click.Context, path: str) -> None:
    """Initialize CIA in the current project.

    Creates a ``.ciarc`` configuration file with sensible defaults.
    """
    from cia.config import DEFAULT_CIARC_CONTENT

    target = Path(path).resolve()
    rc_path = target / ".ciarc"

    if rc_path.exists():
        console.print(
            f"[yellow]Configuration file already exists:[/yellow] {rc_path}"
        )
        ctx.exit(EXIT_OK)
        return

    rc_path.write_text(DEFAULT_CIARC_CONTENT, encoding="utf-8")
    console.print(f"[green]Created configuration file:[/green] {rc_path}")
    console.print("Edit .ciarc to customise analysis defaults.")


# ---------------------------------------------------------------------------
# cia config
# ---------------------------------------------------------------------------


@main.command("config")
@click.option("--set", "set_pair", default=None,
              help="Set a config value: key=value")
@click.option("--get", "get_key", default=None,
              help="Get a config value by key.")
@click.option("--edit", "open_editor", is_flag=True,
              help="Open configuration file in $EDITOR.")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.pass_context
def config_cmd(
    ctx: click.Context,
    set_pair: str | None,
    get_key: str | None,
    open_editor: bool,
    path: str,
) -> None:
    """Show or modify CIA configuration.

    Without flags, prints the current effective configuration.
    """
    from cia.config import (
        find_config_file,
        get_config_value,
        load_config,
        set_config_value,
    )

    target = Path(path).resolve()
    cfg = load_config(target)

    # --- --get ---
    if get_key:
        val = get_config_value(cfg, get_key)
        if val is None:
            console.print(f"[yellow]Key not found:[/yellow] {get_key}")
            ctx.exit(EXIT_ERROR)
        else:
            console.print(f"{get_key} = {val}")
        return

    # --- --set ---
    if set_pair:
        if "=" not in set_pair:
            console.print(
                "[red]Error:[/red] Use [bold]--set key=value[/bold] format.\n"
                "  Example: cia config --set analysis.format=markdown"
            )
            ctx.exit(EXIT_ERROR)
            return
        key, _, value = set_pair.partition("=")
        rc = find_config_file(target)
        if rc is None:
            rc = target / ".ciarc"
        set_config_value(rc, key.strip(), value.strip())
        console.print(f"[green]Set[/green] {key.strip()} = {value.strip()}")
        return

    # --- --edit ---
    if open_editor:
        rc = find_config_file(target)
        if rc is None:
            console.print(
                "[yellow]No .ciarc found. Run 'cia init' first.[/yellow]"
            )
            ctx.exit(EXIT_ERROR)
            return
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", ""))
        if not editor:
            editor = "notepad" if sys.platform == "win32" else "vi"
        try:
            subprocess.run([editor, str(rc)], check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            console.print(f"[red]Error launching editor:[/red] {exc}")
            ctx.exit(EXIT_ERROR)
        return

    # --- Default: show config ---
    rc = find_config_file(target)
    if rc:
        console.print(f"[bold]Config file:[/bold] {rc}")
    else:
        console.print("[dim]No .ciarc file found (using defaults).[/dim]")

    console.print("\n[bold]Effective configuration:[/bold]")
    for key, val in sorted(cfg.items()):
        console.print(f"  {key} = {val}")


if __name__ == "__main__":
    main()
