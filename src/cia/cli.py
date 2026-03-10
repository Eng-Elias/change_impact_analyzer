"""Command-line interface for Change Impact Analyzer."""

from __future__ import annotations

import click
from rich.console import Console

from cia import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="cia")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """Change Impact Analyzer - Predict the impact of code changes."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--format", "-f", "output_format", type=click.Choice(["json", "html", "markdown"]), default="json", help="Output format.")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path.")
@click.pass_context
def analyze(ctx: click.Context, path: str, output_format: str, output: str | None) -> None:
    """Analyze the impact of staged changes in a Git repository."""
    verbose = ctx.obj["verbose"]
    if verbose:
        console.print(f"[bold]Analyzing changes in:[/bold] {path}")
        console.print(f"[bold]Output format:[/bold] {output_format}")
    console.print("[yellow]Analysis engine not yet implemented.[/yellow]")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.pass_context
def graph(ctx: click.Context, path: str) -> None:
    """Build and display the dependency graph for a project."""
    verbose = ctx.obj["verbose"]
    if verbose:
        console.print(f"[bold]Building dependency graph for:[/bold] {path}")
    console.print("[yellow]Graph builder not yet implemented.[/yellow]")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--install", is_flag=True, help="Install the pre-commit hook.")
@click.option("--uninstall", is_flag=True, help="Uninstall the pre-commit hook.")
@click.pass_context
def hook(ctx: click.Context, path: str, install: bool, uninstall: bool) -> None:
    """Manage Git hooks for automatic impact analysis."""
    if install:
        console.print("[yellow]Hook installation not yet implemented.[/yellow]")
    elif uninstall:
        console.print("[yellow]Hook uninstallation not yet implemented.[/yellow]")
    else:
        console.print("Use --install or --uninstall to manage hooks.")


if __name__ == "__main__":
    main()
