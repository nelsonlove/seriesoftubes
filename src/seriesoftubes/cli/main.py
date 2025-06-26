"""CLI interface for seriesoftubes (s10s)"""

import asyncio
import http.server
import json
import os
import socketserver
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

from seriesoftubes.cli.client import APIClient
from seriesoftubes.engine import run_workflow
from seriesoftubes.models import Workflow
from seriesoftubes.parser import WorkflowParseError, parse_workflow_yaml, validate_dag

app = typer.Typer(
    name="s10s",
    help="LLM Workflow Orchestration Platform",
    no_args_is_help=True,
)
console = Console()


def _truncate_description(description: str | None, max_length: int) -> str:
    """Truncate description to max length with ellipsis if needed."""
    if not description:
        return ""
    return (
        description[:max_length] + "..."
        if len(description) > max_length
        else description
    )


def parse_input_args(input_list: list[str] | None) -> dict[str, Any]:
    """Parse input arguments from command line

    Supports formats:
    - key=value
    - key="quoted value"
    - key=123 (numbers)
    - key=true/false (booleans)
    - key={"nested": "json"} (JSON objects)
    """
    if not input_list:
        return {}

    inputs = {}
    for arg in input_list:
        if "=" not in arg:
            msg = f"Invalid input format: '{arg}'. Use key=value format."
            raise typer.BadParameter(msg)

        key, value = arg.split("=", 1)

        # Try to parse as JSON first (handles objects, arrays, booleans, numbers)
        try:
            inputs[key] = json.loads(value)
        except json.JSONDecodeError:
            # Otherwise treat as string
            inputs[key] = value

    return inputs


@app.command()
def auth(
    action: Annotated[str, typer.Argument(help="Action: login, register, or status")],
    username: Annotated[str | None, typer.Option("--username", "-u")] = None,
    password: Annotated[str | None, typer.Option("--password", "-p")] = None,
    email: Annotated[str | None, typer.Option("--email", "-e")] = None,
) -> None:
    """Authenticate with the SeriesOfTubes API

    Examples:
        s10s auth status
        s10s auth login -u myuser
        s10s auth register -u newuser -e user@example.com
    """
    with APIClient() as client:
        if action == "status":
            if client.token:
                console.print("[green]✓ Authenticated[/green]")
                console.print(f"API URL: {client.config.api_url}")
            else:
                console.print("[yellow]⚠ Not authenticated[/yellow]")
                console.print("Run 's10s auth login' to authenticate")

        elif action == "login":
            if not username:
                username = typer.prompt("Username")
            if not password:
                password = typer.prompt("Password", hide_input=True)

            try:
                _ = client.login(username, password)
                console.print(f"[green]✓ Logged in as {username}[/green]")
            except httpx.HTTPStatusError as e:
                console.print(f"[red]✗ Login failed: {e.response.text}[/red]")
                raise typer.Exit(1) from e

        elif action == "register":
            if not username:
                username = typer.prompt("Username")
            if not email:
                email = typer.prompt("Email")
            if not password:
                password = typer.prompt("Password", hide_input=True)
                confirm = typer.prompt("Confirm password", hide_input=True)
                if password != confirm:
                    console.print("[red]✗ Passwords don't match[/red]")
                    raise typer.Exit(1)

            try:
                client.register(username, email, password)
                console.print(f"[green]✓ Registered user {username}[/green]")
                console.print("Now run 's10s auth login' to authenticate")
            except httpx.HTTPStatusError as e:
                console.print(f"[red]✗ Registration failed: {e.response.text}[/red]")
                raise typer.Exit(1) from e

        else:
            console.print(f"[red]✗ Unknown action: {action}[/red]")
            console.print("Valid actions: login, register, status")
            raise typer.Exit(1)


@app.command()
def run(
    workflow: Annotated[
        str, typer.Argument(help="Workflow ID (from API) or path to local YAML file")
    ],
    inputs: Annotated[list[str] | None, typer.Option("--inputs", "-i")] = None,
    output_dir: Annotated[Path | None, typer.Option("--output-dir", "-o")] = None,
    no_save: Annotated[bool, typer.Option("--no-save")] = False,
    local: Annotated[
        bool, typer.Option("--local", help="Run locally instead of via API")
    ] = False,
) -> None:
    """Run a workflow from API (default) or locally

    Examples:
        s10s run workflow-id -i company="Acme Corp"  # Run from API
        s10s run workflow.yaml --local  # Run local file
        s10s run workflow.yaml --local -i text="Hello world" -i count=5
        s10s run workflow.yaml --local --no-save
        s10s run workflow.yaml --local -o ./my-outputs
    """
    # Parse inputs
    parsed_inputs = parse_input_args(inputs)

    if not local:
        # Run via API (default)
        console.print(f"[bold]Running workflow via API:[/bold] {workflow}")

        with APIClient() as client:
            try:
                # Run the workflow by ID
                result = client.run_workflow(workflow, parsed_inputs)
                console.print(
                    f"✓ Started execution: [green]{result['execution_id']}[/green]"
                )

                # Stream updates
                console.print("\n[bold]Execution progress:[/bold]")

                for event in client.stream_execution(result["execution_id"]):
                    if event["event"] == "update":
                        data = json.loads(event["data"])
                        console.print(f"  Status: {data.get('status')}")
                        if data.get("progress"):
                            for node, status in data["progress"].items():
                                console.print(f"    • {node}: {status}")
                    elif event["event"] == "complete":
                        data = json.loads(event["data"])
                        if data.get("status") == "completed":
                            console.print(
                                "\n[bold green]✓ Workflow completed successfully![/bold green]"
                            )
                            if data.get("outputs"):
                                console.print("\n[bold]Outputs:[/bold]")
                                console.print(json.dumps(data["outputs"], indent=2))
                        else:
                            console.print("\n[bold red]✗ Workflow failed![/bold red]")
                            if data.get("errors"):
                                console.print("\n[bold]Errors:[/bold]")
                                console.print(json.dumps(data["errors"], indent=2))

            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("detail", e.response.text)
                console.print(f"[red]✗ API error: {error_detail}[/red]")
                raise typer.Exit(1) from e
    else:
        # Run locally from file
        console.print(f"[bold]Running workflow locally:[/bold] {workflow}")

        try:
            # Parse the workflow
            wf = parse_workflow_yaml(Path(workflow))
            console.print(f"✓ Loaded workflow: [green]{wf.name} v{wf.version}[/green]")

            if parsed_inputs:
                console.print(f"✓ Parsed inputs: {list(parsed_inputs.keys())}")

            # Run the workflow
            console.print("\n[bold]Executing workflow...[/bold]")
            results = asyncio.run(
                run_workflow(
                    wf,
                    parsed_inputs,
                    save_outputs=not no_save,
                    output_dir=output_dir,
                )
            )

            # Display results
            if results["success"]:
                console.print(
                    "\n[bold green]✓ Workflow completed successfully![/bold green]"
                )

                if results["outputs"]:
                    console.print("\n[bold]Outputs:[/bold]")
                    for key, value in results["outputs"].items():
                        # Pretty print JSON outputs
                        if isinstance(value, dict | list):
                            value_str = json.dumps(value, indent=2)
                        else:
                            value_str = str(value)
                        console.print(f"  [cyan]{key}:[/cyan] {value_str}")

                if not no_save:
                    console.print(
                        "\n[dim]Results saved to: "
                        f"{output_dir or 'outputs'}/{results['execution_id']}/[/dim]"
                    )
            else:
                console.print("\n[bold red]✗ Workflow failed![/bold red]")
                if results["errors"]:
                    console.print("\n[bold]Errors:[/bold]")
                    for node, error in results["errors"].items():
                        console.print(f"  [red]{node}:[/red] {error}")
                raise typer.Exit(1)

        except WorkflowParseError as e:
            console.print(f"\n[bold red]✗ Workflow parse error:[/bold red] {e}")
            raise typer.Exit(1) from None
        except ValueError as e:
            console.print(f"\n[bold red]✗ Validation error:[/bold red] {e}")
            raise typer.Exit(1) from None
        except Exception as e:
            console.print(f"\n[bold red]✗ Unexpected error:[/bold red] {e}")
            raise typer.Exit(1) from None


@app.command()
def upload(
    workflow: Annotated[Path, typer.Argument(help="Path to workflow YAML file")],
    public: Annotated[
        bool, typer.Option("--public", help="Make workflow public")
    ] = False,
) -> None:
    """Upload a workflow YAML file to the API

    Examples:
        s10s upload workflow.yaml
        s10s upload workflow.yaml --public
    """
    console.print(f"[bold]Uploading workflow:[/bold] {workflow}")

    try:
        # Read the workflow file
        with open(workflow) as f:
            yaml_content = f.read()

        # Upload via API
        with APIClient() as client:
            try:
                result = client.create_workflow(yaml_content, is_public=public)
                console.print(
                    f"✓ Uploaded workflow: [green]{result['name']} v{result['version']}[/green]"
                )
                console.print(f"  ID: [cyan]{result['id']}[/cyan]")
                console.print(f"  Public: {'✓' if result['is_public'] else '✗'}")

            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("detail", e.response.text)
                console.print(f"[red]✗ Upload failed: {error_detail}[/red]")
                raise typer.Exit(1) from e

    except FileNotFoundError:
        console.print(f"[red]✗ File not found: {workflow}[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(1) from None


@app.command()
def download(
    workflow_id: Annotated[str, typer.Argument(help="Workflow ID to download")],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output file path")
    ] = None,
    format: Annotated[  # noqa: A002
        str, typer.Option("--format", "-f", help="Download format (yaml or tubes)")
    ] = "yaml",
) -> None:
    """Download a workflow from the API

    Examples:
        s10s download workflow-id
        s10s download workflow-id -o my-workflow.yaml
        s10s download workflow-id --format tubes -o workflow.tubes
    """
    console.print(f"[bold]Downloading workflow:[/bold] {workflow_id}")

    with APIClient() as client:
        try:
            # Get workflow details first
            workflow = client.get_workflow(workflow_id)

            # Download the workflow
            content = client.download_workflow(workflow_id, format=format)

            # Determine output filename
            if output is None:
                if format == "yaml":
                    output = Path(f"{workflow['name']}_v{workflow['version']}.yaml")
                else:
                    output = Path(f"{workflow['name']}_v{workflow['version']}.tubes")

            # Save to file
            if format == "yaml":
                output.write_text(content)
            else:
                output.write_bytes(content)

            console.print(f"✓ Downloaded to: [green]{output}[/green]")

        except httpx.HTTPStatusError as e:
            error_detail = e.response.json().get("detail", e.response.text)
            console.print(f"[red]✗ Download failed: {error_detail}[/red]")
            raise typer.Exit(1) from e


@app.command()
def validate(
    workflow: Annotated[str, typer.Argument(help="Workflow ID or path to YAML file")],
    local: Annotated[bool, typer.Option("--local", help="Validate local file")] = False,
) -> None:
    """Validate a workflow from API or local file"""

    if not local:
        # Validate via API
        console.print(f"[bold]Validating workflow from API:[/bold] {workflow}")

        with APIClient() as client:
            try:
                result = client.validate_workflow(workflow)

                if result["valid"]:
                    console.print("✓ [green]Workflow is valid![/green]")

                    if result.get("parsed_structure"):
                        structure = result["parsed_structure"]
                        console.print("\n[bold]Workflow Summary:[/bold]")
                        console.print(
                            f"  • Name: {structure['name']} v{structure['version']}"
                        )
                        if structure.get("description"):
                            console.print(
                                f"  • Description: {structure['description']}"
                            )
                        console.print(f"  • Inputs: {len(structure.get('inputs', {}))}")
                        console.print(f"  • Nodes: {len(structure.get('nodes', {}))}")
                        console.print(
                            f"  • Outputs: {len(structure.get('outputs', {}))}"
                        )
                else:
                    console.print("✗ [red]Workflow validation failed![/red]")

                if result.get("errors"):
                    console.print("\n[bold red]Errors:[/bold red]")
                    for error in result["errors"]:
                        console.print(f"  • {error}")

                if result.get("warnings"):
                    console.print("\n[bold yellow]Warnings:[/bold yellow]")
                    for warning in result["warnings"]:
                        console.print(f"  • {warning}")

                if not result["valid"]:
                    raise typer.Exit(1)

            except httpx.HTTPStatusError as e:
                error_detail = e.response.json().get("detail", e.response.text)
                console.print(f"[red]✗ API error: {error_detail}[/red]")
                raise typer.Exit(1) from e
    else:
        # Validate local file
        console.print(f"[bold]Validating local workflow:[/bold] {workflow}")

        try:
            # Parse the workflow with Pydantic
            console.print("• Parsing workflow structure...")
            wf = parse_workflow_yaml(Path(workflow))
            console.print(
                f"  ✓ Parsed workflow: [green]{wf.name} v{wf.version}[/green]"
            )

            # Validate DAG
            console.print("• Validating DAG structure...")
            validate_dag(wf)
            console.print("  ✓ [green]No cycles detected[/green]")
            console.print("  ✓ [green]All dependencies exist[/green]")

            # Show summary
            console.print("\n[bold]Workflow Summary:[/bold]")
            console.print(f"  • Inputs: {len(wf.inputs)}")
            console.print(f"  • Nodes: {len(wf.nodes)}")
            for node_type in ["llm", "http", "route", "file", "python"]:
                count = sum(
                    1 for n in wf.nodes.values() if n.node_type.value == node_type
                )
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


@app.command(name="list")
def list_workflows(
    directory: Annotated[
        Path | None, typer.Option("--directory", "-d", help="Directory to search")
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude", "-e", help="Patterns to exclude (e.g., '.*', 'test/*')"
        ),
    ] = None,
    local: Annotated[
        bool, typer.Option("--local", help="List local files instead of API")
    ] = False,
) -> None:
    """List workflows from API (default) or local directory

    Examples:
        s10s list  # List from API
        s10s list --local  # List local files in current directory
        s10s list --local -d ./workflows
        s10s list --local -e ".*" -e "test/*"  # Exclude patterns
    """
    if not local:
        # List from API (default)
        console.print("[bold]Your workflows:[/bold]")

        with APIClient() as client:
            try:
                workflows = client.list_workflows()

                if not workflows:
                    console.print("\n[yellow]No workflows found in database[/yellow]")
                    console.print("Upload workflows using 's10s workflow upload'")
                    return

                # Create table
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("ID", style="cyan", no_wrap=True)
                table.add_column("Name", style="green")
                table.add_column("Version", style="yellow")
                table.add_column("Public", style="blue")
                table.add_column("Description", style="dim")

                for wf_data in workflows:
                    table.add_row(
                        wf_data["id"][:8],  # Show first 8 chars of ID
                        wf_data["name"],
                        wf_data["version"],
                        "✓" if wf_data["is_public"] else "✗",
                        _truncate_description(
                            wf_data.get("description", ""), max_length=50
                        ),
                    )

                console.print(table)
                console.print(f"\n[dim]Total workflows: {len(workflows)}[/dim]")

            except httpx.HTTPStatusError as e:
                console.print(f"[red]✗ API error: {e.response.text}[/red]")
                raise typer.Exit(1) from e
        return

    # List from filesystem
    if directory is None:
        directory = Path(".")
    console.print(f"[bold]Searching for workflows in:[/bold] {directory}")

    # Find all YAML files
    yaml_files = list(directory.rglob("*.yaml")) + list(directory.rglob("*.yml"))

    # Apply exclusion patterns
    if exclude:
        import fnmatch

        excluded_files = []
        for yaml_file in yaml_files:
            relative_path = yaml_file.relative_to(directory)
            if any(fnmatch.fnmatch(str(relative_path), pattern) for pattern in exclude):
                excluded_files.append(yaml_file)
        yaml_files = [f for f in yaml_files if f not in excluded_files]

    if not yaml_files:
        console.print("[yellow]No YAML files found.[/yellow]")
        return

    # Try to parse each file and collect valid workflows
    local_workflows: list[tuple[Path, Workflow]] = []
    for yaml_file in yaml_files:
        try:
            wf: Workflow = parse_workflow_yaml(yaml_file)
            # Only include files that have nodes (actual workflows)
            if wf.nodes:
                local_workflows.append((yaml_file, wf))
        except Exception:  # noqa: S112
            # Skip files that aren't valid workflows
            continue

    if not local_workflows:
        console.print("[yellow]No valid workflow files found.[/yellow]")
        return

    # Display workflows in a table
    table = Table(title=f"Found {len(local_workflows)} workflow(s)")
    table.add_column("File", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Version")
    table.add_column("Nodes", justify="right")
    table.add_column("Description", style="dim")

    for path, wf in local_workflows:
        relative_path = (
            path.relative_to(directory) if path.is_relative_to(directory) else path
        )
        table.add_row(
            str(relative_path),
            wf.name,
            wf.version,
            str(len(wf.nodes)),
            wf.description or "",
        )

    console.print(table)


@app.command()
def test(
    workflow: Annotated[Path, typer.Argument(help="Path to workflow YAML file")],
    *,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    inputs: Annotated[list[str] | None, typer.Option("--inputs", "-i")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Test a workflow with optional dry-run mode

    In dry-run mode, the workflow is validated but not executed.
    This is useful for checking workflow syntax and structure.

    Examples:
        s10s test workflow.yaml --dry-run
        s10s test workflow.yaml -i text="test input" --verbose
    """
    console.print(f"[bold]Testing workflow:[/bold] {workflow}")

    try:
        # Parse and validate the workflow
        wf = parse_workflow_yaml(workflow)
        console.print(f"✓ Loaded workflow: [green]{wf.name} v{wf.version}[/green]")

        # Validate DAG structure
        validate_dag(wf)
        console.print("✓ [green]DAG structure is valid[/green]")

        # Parse test inputs
        parsed_inputs = parse_input_args(inputs)

        # Validate inputs against workflow requirements
        console.print("\n[bold]Validating inputs...[/bold]")
        required_inputs = {name: inp for name, inp in wf.inputs.items() if inp.required}

        missing_inputs = []
        for input_name, input_def in required_inputs.items():
            if input_name not in parsed_inputs and input_def.default is None:
                missing_inputs.append(input_name)

        if missing_inputs:
            console.print(
                f"[yellow]⚠ Missing required inputs: "
                f"{', '.join(missing_inputs)}[/yellow]"
            )
        else:
            console.print("✓ [green]All required inputs provided[/green]")

        # Show workflow details if verbose
        if verbose:
            console.print("\n[bold]Workflow Details:[/bold]")
            console.print(f"  Description: {wf.description or 'N/A'}")
            console.print(f"  Inputs: {len(wf.inputs)}")
            for name, inp in wf.inputs.items():
                req_str = (
                    "[red]required[/red]" if inp.required else "[dim]optional[/dim]"
                )
                default_str = (
                    f" (default: {inp.default})" if inp.default is not None else ""
                )
                console.print(f"    • {name}: {inp.input_type} {req_str}{default_str}")

            console.print(f"  Nodes: {len(wf.nodes)}")
            for name, node in wf.nodes.items():
                deps = f" → {', '.join(node.depends_on)}" if node.depends_on else ""
                console.print(f"    • {name} ({node.node_type.value}){deps}")

            console.print(f"  Outputs: {', '.join(wf.outputs.keys())}")

        if dry_run:
            console.print("\n[dim]Dry run mode - workflow not executed[/dim]")
            console.print("[bold green]✓ Workflow validation passed![/bold green]")
        else:
            # Actually run the workflow in test mode
            console.print("\n[bold]Executing workflow in test mode...[/bold]")

            # Add default values for missing optional inputs
            test_inputs = dict(parsed_inputs)
            for name, inp in wf.inputs.items():
                if name not in test_inputs and inp.default is not None:
                    test_inputs[name] = inp.default

            # Run with test output directory
            test_output_dir = Path("outputs") / "test"
            results = asyncio.run(
                run_workflow(
                    wf,
                    test_inputs,
                    save_outputs=True,
                    output_dir=test_output_dir,
                )
            )

            if results["success"]:
                console.print("\n[bold green]✓ Test passed![/bold green]")
                if results["outputs"]:
                    console.print("\n[bold]Test outputs:[/bold]")
                    for key, value in results["outputs"].items():
                        console.print(f"  [cyan]{key}:[/cyan] {value}")
            else:
                console.print("\n[bold red]✗ Test failed![/bold red]")
                if results["errors"]:
                    for node, error in results["errors"].items():
                        console.print(f"  [red]{node}:[/red] {error}")
                raise typer.Exit(1)

    except WorkflowParseError as e:
        console.print(f"\n[bold red]✗ Workflow parse error:[/bold red] {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"\n[bold red]✗ Test failed:[/bold red] {e}")
        raise typer.Exit(1) from None


# Create workflow subcommand group
workflow_app = typer.Typer(
    name="workflow",
    help="Manage workflows in the database",
    no_args_is_help=True,
)
app.add_typer(workflow_app, name="workflow")


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

            result = client.create_workflow(name, version, yaml_content, description)
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


@app.command()
def docs(
    subcommand: Annotated[
        str, typer.Argument(help="Subcommand: generate, serve")
    ] = "generate",
    *,
    output: Annotated[  # noqa ARG001
        Path | None, typer.Option("--output", "-o", help="Output directory")
    ] = None,
    port: Annotated[
        int, typer.Option("--port", "-p", help="Port for serving docs")
    ] = 8000,
) -> None:
    """Generate or serve workflow documentation

    Commands:
        generate - Generate documentation from schema
        serve    - Serve documentation locally (requires generated docs)

    Examples:
        s10s docs generate
        s10s docs serve --port 8080
    """
    if subcommand == "generate":
        console.print("[bold]Generating documentation from schema...[/bold]")

        try:
            # Run the documentation generator
            script_path = (
                Path(__file__).parent.parent.parent / "scripts" / "generate_docs.py"
            )

            if not script_path.exists():
                console.print(
                    "[red]Error: Documentation generator script not found at "
                    f"{script_path}[/red]"
                )
                raise typer.Exit(1)

            # Run the script
            result = subprocess.run(  # noqa S603
                [sys.executable, str(script_path)],
                check=False,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                console.print(result.stdout)
                console.print(
                    "\n[bold green]✓ Documentation generated successfully![/bold green]"
                )
                console.print("\nDocumentation files created in:")
                console.print("  • docs/reference/nodes/ - Node type reference")
                console.print("  • docs/guides/ - Workflow guides")
                console.print("  • .vscode/ - VS Code snippets")
            else:
                console.print(
                    f"[red]Error generating documentation:[/red]\n{result.stderr}"
                )
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"[red]Failed to generate documentation:[/red] {e}")
            raise typer.Exit(1) from e

    elif subcommand == "serve":
        console.print(f"[bold]Serving documentation on port {port}...[/bold]")

        docs_dir = Path("docs")
        if not docs_dir.exists():
            console.print(
                "[red]Error: Documentation not found. "
                "Run 's10s docs generate' first.[/red]"
            )
            raise typer.Exit(1)

        try:
            os.chdir(docs_dir)

            handler = http.server.SimpleHTTPRequestHandler
            with socketserver.TCPServer(("", port), handler) as httpd:
                console.print(
                    f"\n[green]Documentation server running at http://localhost:{port}[/green]"
                )
                console.print("[dim]Press Ctrl+C to stop[/dim]\n")
                httpd.serve_forever()

        except KeyboardInterrupt:
            console.print("\n[yellow]Server stopped[/yellow]")
        except Exception as e:
            console.print(f"[red]Failed to start server:[/red] {e}")
            raise typer.Exit(1) from e
    else:
        console.print(f"[red]Unknown subcommand: {subcommand}[/red]")
        console.print("Available subcommands: generate, serve")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
