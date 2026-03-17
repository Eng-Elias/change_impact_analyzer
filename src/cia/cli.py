"""Command-line interface for Change Impact Analyzer."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console

from cia import __version__

console = Console()


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
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path (or base name for 'all').")
@click.option("--unstaged", is_flag=True, help="Include unstaged changes.")
@click.option("--commit-range", default=None, help="Analyze a specific commit range (e.g. HEAD~3..HEAD).")
@click.option("--threshold", type=int, default=None, help="Fail if risk score exceeds this value (0-100).")
@click.option("--explain", is_flag=True, help="Show detailed risk breakdown.")
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
) -> None:
    """Analyze the impact of staged (or unstaged / commit-range) changes."""
    from cia.analyzer.change_detector import ChangeDetector
    from cia.analyzer.impact_analyzer import ImpactAnalyzer, ImpactReport
    from cia.git.git_integration import GitIntegration
    from cia.graph.dependency_graph import DependencyGraph
    from cia.report.html_reporter import HtmlReporter
    from cia.report.json_reporter import JsonReporter
    from cia.report.markdown_reporter import MarkdownReporter
    from cia.risk.risk_scorer import RiskScorer

    verbose = ctx.obj["verbose"]
    repo_path = Path(path).resolve()

    if verbose:
        console.print(f"[bold]Analyzing changes in:[/bold] {repo_path}")
        console.print(f"[bold]Output format:[/bold] {output_format}")

    try:
        git = GitIntegration(repo_path)
        if not git.is_git_repository():
            console.print("[red]Error:[/red] Not a Git repository.")
            ctx.exit(1)
            return
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        ctx.exit(1)
        return

    detector = ChangeDetector()

    if commit_range:
        if verbose:
            console.print(f"[bold]Commit range:[/bold] {commit_range}")
        try:
            changeset = detector.detect_changes_for_range(git, commit_range)
        except ValueError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            ctx.exit(1)
            return
    else:
        changeset = detector.detect_changes(git, staged=not unstaged)

    # --- Risk scoring ---
    scorer = RiskScorer()
    risk = scorer.calculate_risk(changeset)

    # --- Build ImpactReport ---
    dep_graph = DependencyGraph()
    analyzer_engine = ImpactAnalyzer(dep_graph)
    impact_report = analyzer_engine.analyze_change_set(
        changeset, risk_score=risk,
    )

    # --- Generate report(s) ---
    def _write_or_print(content: str, ext: str) -> None:
        if output:
            base = Path(output)
            if output_format == "all":
                out_path = base.with_suffix(f".{ext}")
            else:
                out_path = base
            out_path.write_text(content, encoding="utf-8")
            console.print(f"[green]Report written to {out_path}[/green]")
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
        ctx.exit(1)


# ---------------------------------------------------------------------------
# cia graph
# ---------------------------------------------------------------------------


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.pass_context
def graph(ctx: click.Context, path: str) -> None:
    """Build and display the dependency graph for a project."""
    verbose = ctx.obj["verbose"]
    if verbose:
        console.print(f"[bold]Building dependency graph for:[/bold] {path}")
    console.print("[yellow]Graph builder not yet implemented.[/yellow]")


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
@click.pass_context
def install_hook(ctx: click.Context, path: str, block_on: str) -> None:
    """Install the CIA pre-commit hook into the Git repository."""
    from cia.git.hooks import HookManager

    repo_path = Path(path).resolve()
    manager = HookManager(repo_path)
    try:
        hook_path = manager.install(block_threshold=block_on)
        console.print(f"[green]Pre-commit hook installed:[/green] {hook_path}")
        if block_on != "none":
            console.print(f"[bold]Blocking threshold:[/bold] {block_on}")
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        ctx.exit(1)


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
@click.option("--affected-only", is_flag=True, help="Run only tests affected by current changes.")
@click.option("--suggest", is_flag=True, help="Show recommended new tests for uncovered changes.")
@click.option("--unstaged", is_flag=True, help="Include unstaged changes.")
@click.option("--commit-range", default=None, help="Analyze a specific commit range.")
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

    verbose = ctx.obj["verbose"]
    repo_path = Path(path).resolve()

    try:
        git = GitIntegration(repo_path)
        if not git.is_git_repository():
            console.print("[red]Error:[/red] Not a Git repository.")
            ctx.exit(1)
            return
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        ctx.exit(1)
        return

    detector = ChangeDetector()

    if commit_range:
        try:
            changeset = detector.detect_changes_for_range(git, commit_range)
        except ValueError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            ctx.exit(1)
            return
    else:
        changeset = detector.detect_changes(git, staged=not unstaged)

    ta = TestAnalyzer()
    test_mapping = ta.build_test_mapping(repo_path)

    changed_modules = [c.file_path.stem for c in changeset.changes]
    affected = ta.predict_affected_tests(changed_modules, test_mapping)

    if affected_only:
        if not affected:
            console.print("[green]No tests affected by the current changes.[/green]")
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
            console.print(f"\n[bold]Run:[/bold] pytest -k \"{expr}\"")
        return

    if suggest:
        suggestions = ta.suggest_missing_tests(
            changed_modules, test_mapping=test_mapping
        )
        if not suggestions:
            console.print("[green]All changed modules have test coverage.[/green]")
            return
        report = {
            "suggestions": [
                {"entity": s.entity, "reason": s.reason, "suggested_file": s.suggested_file}
                for s in suggestions
            ],
        }
        console.print(json.dumps(report, indent=2))
        return

    # Default: show both affected tests and suggestions
    suggestions = ta.suggest_missing_tests(
        changed_modules, test_mapping=test_mapping
    )
    report = {
        "affected_tests": [str(t) for t in affected],
        "missing_test_suggestions": [
            {"entity": s.entity, "reason": s.reason, "suggested_file": s.suggested_file}
            for s in suggestions
        ],
    }
    console.print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
