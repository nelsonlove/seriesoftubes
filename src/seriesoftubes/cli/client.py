"""CLI client for interacting with the SeriesOfTubes API"""

import json
import os
from pathlib import Path
from typing import Any, cast

import httpx
from pydantic import BaseModel


class CLIConfig(BaseModel):
    """CLI configuration"""

    api_url: str = "http://localhost:8000"
    token: str | None = None


def get_cli_config() -> CLIConfig:
    """Get CLI configuration"""
    config_path = Path.home() / ".seriesoftubes" / "cli_config.json"

    if config_path.exists():
        with open(config_path) as f:
            data = json.load(f)
        return CLIConfig(**data)

    # Default config
    return CLIConfig(
        api_url=os.getenv("SERIESOFTUBES_API_URL", "http://localhost:8000")
    )


def save_cli_config(config: CLIConfig) -> None:
    """Save CLI configuration"""
    config_path = Path.home() / ".seriesoftubes" / "cli_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(config.model_dump(), f, indent=2)


class APIClient:
    """API client for CLI"""

    def __init__(self, config: CLIConfig | None = None):
        self.config = config or get_cli_config()
        self.client = httpx.Client(
            base_url=self.config.api_url,
            headers=self._get_headers(),
            timeout=30.0,
        )

    def _get_headers(self) -> dict[str, str]:
        """Get request headers"""
        headers = {
            "Content-Type": "application/json",
            "X-CLI-User": "system",  # Use system user for CLI
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    @property
    def token(self) -> str | None:
        """Get auth token"""
        return self.config.token

    def set_token(self, token: str) -> None:
        """Set auth token and save config"""
        self.config.token = token
        save_cli_config(self.config)
        self.client.headers["Authorization"] = f"Bearer {token}"

    def close(self) -> None:
        """Close the client"""
        self.client.close()

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # Auth methods
    def register(self, username: str, email: str, password: str) -> dict[str, Any]:
        """Register a new user"""
        response = self.client.post(
            "/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def login(self, username: str, password: str) -> dict[str, Any]:
        """Login and get token"""
        response = self.client.post(
            "/auth/login",
            json={"username": username, "password": password},
        )
        response.raise_for_status()
        data = response.json()

        # Save token
        if "access_token" in data:
            self.set_token(data["access_token"])

        return cast(dict[str, Any], data)

    # Workflow methods
    def list_workflows(self) -> list[dict[str, Any]]:
        """List workflows from API"""
        response = self.client.get("/api/workflows")
        response.raise_for_status()
        return cast(list[dict[str, Any]], response.json())

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow details"""
        response = self.client.get(f"/api/workflows/{workflow_id}")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def create_workflow(
        self, yaml_content: str, is_public: bool = False
    ) -> dict[str, Any]:
        """Create a new workflow in the database"""
        response = self.client.post(
            "/api/workflows",
            json={
                "yaml_content": yaml_content,
                "is_public": is_public,
            },
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def upload_workflow_file(
        self, yaml_path: Path, is_public: bool = False
    ) -> dict[str, Any]:
        """Upload a workflow YAML file"""
        with open(yaml_path, "rb") as f:
            files = {"file": (yaml_path.name, f, "application/x-yaml")}
            response = self.client.post(
                "/api/workflows/upload",
                files=files,
                params={"is_public": is_public},
            )

        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def run_workflow(self, workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Run a workflow"""
        response = self.client.post(
            f"/api/workflows/{workflow_id}/run",
            json={"inputs": inputs},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def list_executions(self) -> list[dict[str, Any]]:
        """List executions"""
        response = self.client.get("/api/executions")
        response.raise_for_status()
        return cast(list[dict[str, Any]], response.json())

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        """Get execution details"""
        response = self.client.get(f"/api/executions/{execution_id}")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def stream_execution(self, execution_id: str) -> Any:
        """Stream execution updates via SSE"""
        url = f"/api/executions/{execution_id}/stream"

        # Parse SSE events
        with self.client.stream("GET", url) as response:
            response.raise_for_status()
            event_data = {}
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event_data["event"] = line[6:].strip()
                elif line.startswith("data:"):
                    event_data["data"] = line[5:].strip()
                elif not line and event_data:
                    # Empty line signals end of event
                    yield event_data
                    event_data = {}

    def validate_workflow(
        self, workflow_id: str, yaml_content: str | None = None
    ) -> dict[str, Any]:
        """Validate a workflow"""
        response = self.client.post(
            f"/api/workflows/{workflow_id}/validate",
            json={"yaml_content": yaml_content} if yaml_content else {},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    def download_workflow(
        self, workflow_id: str, format: str = "yaml"  # noqa: A002
    ) -> str | bytes:
        """Download a workflow"""
        response = self.client.get(
            f"/api/workflows/{workflow_id}/download",
            params={"format": format},
        )
        response.raise_for_status()

        if format == "yaml":
            return response.text
        else:
            return response.content
