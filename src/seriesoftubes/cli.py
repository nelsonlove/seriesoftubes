"""CLI interface for seriesoftubes (s10s)"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from seriesoftubes.parser import WorkflowParseError, parse_workflow_yaml, validate_dag

app = typer.Typer(
    name="s10s",
    help="LLM Workflow Orchestration Platform",
    no_args_is_help=True,
)
console = Console()


@app.command()
def run(
    workflow: str,
    inputs: Annotated[list[str] | None, typer.Option("--inputs", "-i")] = None,
) -> None:
    """Run a workflow from a YAML file"""
    typer.echo(f"Running workflow: {workflow}")
    if inputs:
        typer.echo(f"With inputs: {inputs}")
    typer.echo("Not implemented yet!")


@app.command()
def validate(
    workflow: Annotated[Path, typer.Argument(help="Path to workflow YAML file")],
) -> None:
    """Validate a workflow YAML file"""
    console.print(f"[bold]Validating workflow:[/bold] {workflow}")

    try:
        # Parse the workflow
        wf = parse_workflow_yaml(workflow)
        console.print(f"✓ Parsed workflow: [green]{wf.name} v{wf.version}[/green]")

        # Validate DAG
        validate_dag(wf)
        console.print("✓ [green]DAG structure is valid[/green]")

        # Show summary
        console.print("\n[bold]Workflow Summary:[/bold]")
        console.print(f"  • Inputs: {len(wf.inputs)}")
        console.print(f"  • Nodes: {len(wf.nodes)}")
        for node_type in ["llm", "http", "route"]:
            count = sum(1 for n in wf.nodes.values() if n.node_type.value == node_type)
            if count > 0:
                console.print(f"    - {node_type}: {count}")
        console.print(f"  • Outputs: {len(wf.outputs)}")

        console.print("\n[bold green]✓ Workflow is valid![/bold green]")

    except WorkflowParseError as e:
        console.print(f"\n[bold red]✗ Validation failed:[/bold red] {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error:[/bold red] {e}")
        raise typer.Exit(1) from None


@app.command()
def list_workflows() -> None:
    """List available workflows"""
    typer.echo("Listing workflows...")
    typer.echo("Not implemented yet!")


@app.command()
def test(
    workflow: str,
    *,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Test a workflow with optional dry-run mode"""
    typer.echo(f"Testing workflow: {workflow}")
    if dry_run:
        typer.echo("(Dry run mode)")
    typer.echo("Not implemented yet!")


if __name__ == "__main__":
    app()
