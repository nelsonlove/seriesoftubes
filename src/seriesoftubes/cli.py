"""CLI interface for seriesoftubes (s10s)"""

import asyncio
import json
from pathlib import Path
from typing import Annotated, Any

import jsonschema
import typer
import yaml
from rich.console import Console

from seriesoftubes.engine import run_workflow
from seriesoftubes.parser import WorkflowParseError, parse_workflow_yaml, validate_dag

app = typer.Typer(
    name="s10s",
    help="LLM Workflow Orchestration Platform",
    no_args_is_help=True,
)
console = Console()


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
def run(
    workflow: Annotated[Path, typer.Argument(help="Path to workflow YAML file")],
    inputs: Annotated[list[str] | None, typer.Option("--inputs", "-i")] = None,
    output_dir: Annotated[Path | None, typer.Option("--output-dir", "-o")] = None,
    no_save: Annotated[bool, typer.Option("--no-save")] = False,  # noqa: FBT002
) -> None:
    """Run a workflow from a YAML file

    Examples:
        s10s run workflow.yaml
        s10s run workflow.yaml -i text="Hello world" -i count=5
        s10s run workflow.yaml --no-save
        s10s run workflow.yaml -o ./my-outputs
    """
    console.print(f"[bold]Running workflow:[/bold] {workflow}")

    try:
        # Parse the workflow
        wf = parse_workflow_yaml(workflow)
        console.print(f"✓ Loaded workflow: [green]{wf.name} v{wf.version}[/green]")

        # Parse inputs
        parsed_inputs = parse_input_args(inputs)
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
def validate(
    workflow: Annotated[Path, typer.Argument(help="Path to workflow YAML file")],
) -> None:
    """Validate a workflow YAML file against schema and DAG rules"""
    console.print(f"[bold]Validating workflow:[/bold] {workflow}")

    try:
        # First, validate against JSON schema
        console.print("• Checking schema compliance...")
        schema_path = Path(__file__).parent / "schemas" / "workflow-schema.yaml"
        
        if schema_path.exists():
            with open(schema_path) as f:
                schema = yaml.safe_load(f)
            
            with open(workflow) as f:
                workflow_data = yaml.safe_load(f)
            
            try:
                jsonschema.validate(workflow_data, schema)
                console.print("  ✓ [green]Schema validation passed[/green]")
            except jsonschema.ValidationError as e:
                console.print(f"  ✗ [red]Schema validation failed:[/red] {e.message}")
                if e.path:
                    console.print(f"    Path: {'.'.join(str(p) for p in e.path)}")
                raise typer.Exit(1) from None
        else:
            console.print("  [yellow]⚠ Schema file not found, skipping schema validation[/yellow]")

        # Parse the workflow with Pydantic
        console.print("• Parsing workflow structure...")
        wf = parse_workflow_yaml(workflow)
        console.print(f"  ✓ Parsed workflow: [green]{wf.name} v{wf.version}[/green]")

        # Validate DAG
        console.print("• Validating DAG structure...")
        validate_dag(wf)
        console.print("  ✓ [green]No cycles detected[/green]")
        console.print("  ✓ [green]All dependencies exist[/green]")

        # Show summary
        console.print("\n[bold]Workflow Summary:[/bold]")
        console.print(f"  • Inputs: {len(wf.inputs)}")
        console.print(f"  • Nodes: {len(wf.nodes)}")
        for node_type in ["llm", "http", "route", "file"]:
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


@app.command(name="list")
def list_workflows(
    directory: Annotated[
        Path, typer.Option("--directory", "-d", help="Directory to search")
    ] = Path("."),
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude", "-e", help="Patterns to exclude (e.g., '.*', 'test/*')"
        ),
    ] = None,
) -> None:
    """List available workflows in the current directory

    Examples:
        s10s list
        s10s list -d ./workflows
        s10s list -e ".*" -e "test/*"  # Exclude hidden files and test directory
    """
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
    workflows = []
    for yaml_file in yaml_files:
        try:
            wf = parse_workflow_yaml(yaml_file)
            # Only include files that have nodes (actual workflows)
            if wf.nodes:
                workflows.append((yaml_file, wf))
        except Exception:  # noqa: S112
            # Skip files that aren't valid workflows
            continue

    if not workflows:
        console.print("[yellow]No valid workflow files found.[/yellow]")
        return

    # Display workflows in a table
    from rich.table import Table

    table = Table(title=f"Found {len(workflows)} workflow(s)")
    table.add_column("File", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Version")
    table.add_column("Nodes", justify="right")
    table.add_column("Description", style="dim")

    for path, wf in workflows:
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


if __name__ == "__main__":
    app()
