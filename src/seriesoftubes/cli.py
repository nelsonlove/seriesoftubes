"""CLI interface for seriesoftubes (s10s)"""

import typer
from typing import Optional

app = typer.Typer(
    name="s10s",
    help="LLM Workflow Orchestration Platform",
    no_args_is_help=True,
)


@app.command()
def run(
    workflow: str,
    inputs: Optional[list[str]] = typer.Option(None, "--inputs", "-i"),
):
    """Run a workflow from a YAML file"""
    typer.echo(f"Running workflow: {workflow}")
    if inputs:
        typer.echo(f"With inputs: {inputs}")
    typer.echo("Not implemented yet!")


@app.command()
def validate(workflow: str):
    """Validate a workflow YAML file"""
    typer.echo(f"Validating workflow: {workflow}")
    typer.echo("Not implemented yet!")


@app.command()
def list():
    """List available workflows"""
    typer.echo("Listing workflows...")
    typer.echo("Not implemented yet!")


@app.command()
def test(workflow: str, dry_run: bool = typer.Option(False, "--dry-run")):
    """Test a workflow with optional dry-run mode"""
    typer.echo(f"Testing workflow: {workflow}")
    if dry_run:
        typer.echo("(Dry run mode)")
    typer.echo("Not implemented yet!")


if __name__ == "__main__":
    app()
