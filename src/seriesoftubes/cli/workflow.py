import zipfile
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console

from seriesoftubes.cli.client import APIClient
from seriesoftubes.parser import parse_workflow_yaml

console = Console()


workflow_app = typer.Typer(
    name="workflow",
    help="Manage workflows in the database",
    no_args_is_help=True,
)


@workflow_app.command(name="upload-package")
def upload_package(
    path: Annotated[Path, typer.Argument(help="Path to workflow package (ZIP file)")],
) -> None:
    """Upload a workflow package (ZIP file)

    Example:
        s10s workflow upload my-workflow.zip
    """
    if not path.exists():
        console.print(f"[red]✗ File not found: {path}[/red]")
        raise typer.Exit(1)

    if not path.suffix == ".zip":
        console.print("[red]✗ File must be a ZIP archive[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Uploading workflow package:[/bold] {path}")

    with APIClient() as client:
        try:
            result = client.upload_workflow_file(path, is_public=False)
            console.print(
                f"[green]✓ Uploaded workflow: "
                f"{result['name']} v{result['version']}[/green]"
            )
            console.print(f"  ID: {result['id']}")
            console.print(f"  Owner: {result['username']}")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]✗ Upload failed: {e.response.text}[/red]")
            raise typer.Exit(1) from e


@workflow_app.command()
def create(
    path: Annotated[Path, typer.Argument(help="Path to workflow YAML file")],
    name: Annotated[str | None, typer.Option("--name", "-n")] = None,
    version: Annotated[str | None, typer.Option("--version", "-v")] = None,
    description: Annotated[str | None, typer.Option("--description", "-d")] = None,
) -> None:
    """Create a workflow from a YAML file

    Example:
        s10s workflow create workflow.yaml
        s10s workflow create workflow.yaml --name "My Workflow" --version "2.0.0"
    """
    if not path.exists():
        console.print(f"[red]✗ File not found: {path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Creating workflow from:[/bold] {path}")

    with APIClient() as client:
        try:
            # Read and parse workflow
            yaml_content = path.read_text()
            wf = parse_workflow_yaml(path)

            # Use workflow metadata or provided values
            name = name or wf.name
            version = version or wf.version
            description = description or wf.description

            result = client.create_workflow(yaml_content, is_public=False)
            console.print(
                f"[green]✓ Created workflow: "
                f"{result['name']} v{result['version']}[/green]"
            )
            console.print(f"  ID: {result['id']}")
            console.print(f"  Owner: {result['username']}")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]✗ Creation failed: {e.response.text}[/red]")
            raise typer.Exit(1) from e


@workflow_app.command()
def package(
    path: Annotated[Path, typer.Argument(help="Path to workflow directory")],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n")] = None,
    version: Annotated[str | None, typer.Option("--version", "-v")] = None,
) -> None:
    """Package a workflow directory into a ZIP file

    Example:
        s10s workflow package ./my-workflow
        s10s workflow package ./my-workflow -o package.zip
        s10s workflow package ./my-workflow -n "My Workflow" -v "1.0.0"
    """
    if not path.exists():
        console.print(f"[red]✗ Directory not found: {path}[/red]")
        raise typer.Exit(1)

    workflow_file = path / "workflow.yaml"
    if not workflow_file.exists():
        console.print(f"[red]✗ No workflow.yaml found in {path}[/red]")
        raise typer.Exit(1)

    # Parse workflow to get metadata
    wf = parse_workflow_yaml(workflow_file)
    name = name or wf.name
    version = version or wf.version

    # Determine output path
    if not output:
        output = Path(f"{name}_{version}.zip")

    console.print(f"[bold]Creating workflow package:[/bold] {output}")

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add all files from the directory
        file_count = 0
        for file in path.rglob("*"):
            if file.is_file() and not file.name.startswith("."):
                arcname = file.relative_to(path)
                zf.write(file, arcname)
                console.print(f"  Added: {arcname}")
                file_count += 1

    console.print(f"[green]✓ Created package: {output}[/green]")
    console.print(f"  Files: {file_count}")
    console.print(f"  Size: {output.stat().st_size / 1024:.1f} KB")
