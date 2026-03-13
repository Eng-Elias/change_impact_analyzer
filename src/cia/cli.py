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
    type=click.Choice(["json", "html", "markdown"]),
    default="json",
    help="Output format.",
)
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path.")
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
    from cia.git.git_integration import GitIntegration
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

    report = {
        "path": str(repo_path),
        "commit_range": commit_range,
        "staged": not unstaged and commit_range is None,
        "added": [str(p) for p in changeset.added],
        "modified": [str(p) for p in changeset.modified],
        "deleted": [str(p) for p in changeset.deleted],
        "renamed": [(str(a), str(b)) for a, b in changeset.renamed],
        "total_changes": len(changeset.changes),
        "risk_level": risk.level.value,
        "risk_score": risk.overall_score,
        "factor_scores": risk.factor_scores,
    }

    if explain:
        report["explanations"] = risk.explanations
        report["suggestions"] = risk.suggestions

    report_str = json.dumps(report, indent=2)

    if output:
        Path(output).write_text(report_str, encoding="utf-8")
        console.print(f"[green]Report written to {output}[/green]")
    else:
        console.print(report_str)

    if explain and output_format != "json":
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


if __name__ == "__main__":
    main()
