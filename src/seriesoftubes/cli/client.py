"""CLI client for interacting with the SeriesOfTubes API"""

import os
from pathlib import Path
from typing import Any

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
        import json
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

    import json
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
        return response.json()

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

        return data

    # Workflow methods
    def list_workflows(self, directory: str = ".", use_db: bool = False) -> list[dict[str, Any]]:
        """List workflows"""
        if use_db:
            # List from database
            response = self.client.get("/api/workflows")
        else:
            # List from filesystem
            response = self.client.get("/workflows", params={"directory": directory})

        response.raise_for_status()
        return response.json()

    def get_workflow(self, workflow_path: str) -> dict[str, Any]:
        """Get workflow details"""
        response = self.client.get(f"/workflows/{workflow_path}")
        response.raise_for_status()
        return response.json()

    def create_workflow(
        self, name: str, version: str, yaml_content: str, description: str | None = None
    ) -> dict[str, Any]:
        """Create a new workflow in the database"""
        response = self.client.post(
            "/api/workflows",
            json={
                "name": name,
                "version": version,
                "yaml_content": yaml_content,
                "description": description,
                "is_public": False,
            },
        )
        response.raise_for_status()
        return response.json()

    def upload_workflow_package(self, zip_path: Path) -> dict[str, Any]:
        """Upload a workflow package"""
        with open(zip_path, "rb") as f:
            files = {"file": (zip_path.name, f, "application/zip")}
            response = self.client.post("/api/workflows/upload", files=files)

        response.raise_for_status()
        return response.json()

    def run_workflow(
        self, workflow_path: str, inputs: dict[str, Any], use_db: bool = False
    ) -> dict[str, Any]:
        """Run a workflow"""
        if use_db:
            # Run from database
            response = self.client.post(
                f"/api/executions/workflows/{workflow_path}/run",
                json={"inputs": inputs},
            )
        else:
            # Run from filesystem
            response = self.client.post(
                f"/workflows/{workflow_path}/run",
                json={"inputs": inputs},
            )

        response.raise_for_status()
        return response.json()

    def list_executions(self) -> list[dict[str, Any]]:
        """List executions"""
        response = self.client.get("/api/executions")
        response.raise_for_status()
        return response.json()

    def get_execution(self, execution_id: str, use_db: bool = False) -> dict[str, Any]:
        """Get execution details"""
        if use_db:
            response = self.client.get(f"/api/executions/{execution_id}")
        else:
            response = self.client.get(f"/executions/{execution_id}")

        response.raise_for_status()
        return response.json()

    def stream_execution(self, execution_id: str, use_db: bool = False) -> Any:
        """Stream execution updates"""
        if use_db:
            url = f"/api/executions/{execution_id}/stream"
        else:
            url = f"/executions/{execution_id}/stream"

        # Use streaming
        with self.client.stream("GET", url) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    yield line
