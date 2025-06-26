from typing import Annotated

import httpx
import typer
from rich.console import Console

from seriesoftubes.cli.client import APIClient

console = Console()


auth_app = typer.Typer(
    name="auth",
    help="Authenticate with the SeriesOfTubes API",
    no_args_is_help=True,
)


@auth_app.command()
def status() -> None:
    """Check authentication status

    Example:
        s10s auth status
    """
    with APIClient() as client:
        if client.token:
            console.print("[green]✓ Authenticated[/green]")
            console.print(f"API URL: {client.config.api_url}")
        else:
            console.print("[yellow]⚠ Not authenticated[/yellow]")
            console.print("Run 's10s auth login' to authenticate")


@auth_app.command()
def login(
    username: Annotated[str | None, typer.Option("--username", "-u")] = None,
    password: Annotated[str | None, typer.Option("--password", "-p")] = None,
) -> None:
    """Login to the SeriesOfTubes API

    Example:
        s10s auth login -u myuser
    """
    with APIClient() as client:
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


@auth_app.command()
def register(
    username: Annotated[str | None, typer.Option("--username", "-u")] = None,
    password: Annotated[str | None, typer.Option("--password", "-p")] = None,
    email: Annotated[str | None, typer.Option("--email", "-e")] = None,
) -> None:
    """Register a new user

    Example:
        s10s auth register -u newuser -e user@example.com
    """
    with APIClient() as client:
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
