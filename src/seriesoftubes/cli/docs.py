import http.server
import os
import socketserver
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()


docs_app = typer.Typer(
    name="docs",
    help="Generate or serve workflow documentation",
    no_args_is_help=True,
)


@docs_app.command()
def generate(
    output: Annotated[  # noqa ARG001
        Path | None, typer.Option("--output", "-o", help="Output directory")
    ] = None,
) -> None:
    """Generate documentation from schema

    Example:
        s10s docs generate
    """
    console.print("[bold]Generating documentation from schema...[/bold]")

    try:
        # Run the documentation generator
        script_path = (
            Path(__file__).parent.parent.parent.parent / "scripts" / "generate_docs.py"
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


@docs_app.command()
def serve(
    port: Annotated[
        int, typer.Option("--port", "-p", help="Port for serving docs")
    ] = 8000,
) -> None:
    """Serve documentation locally (requires generated docs)

    Example:
        s10s docs serve --port 8080
    """
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
