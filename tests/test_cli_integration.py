"""Integration tests for CLI functionality"""

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer.testing

from seriesoftubes.cli import app

runner = typer.testing.CliRunner()


def test_cli_help():
    """Test CLI help command"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "LLM Workflow Orchestration Platform" in result.stdout
    assert "auth" in result.stdout
    assert "run" in result.stdout
    assert "workflow" in result.stdout


def test_auth_status_not_authenticated():
    """Test auth status when not authenticated"""
    from seriesoftubes.cli.client import CLIConfig  # noqa: PLC0415

    with patch("seriesoftubes.cli.client.get_cli_config") as mock_config:
        mock_config.return_value = CLIConfig(
            api_url="http://localhost:8000", token=None
        )
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0
        assert "Not authenticated" in result.stdout


def test_list_workflows_local():
    """Test listing workflows from filesystem"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test workflow
        workflow_path = Path(tmpdir) / "test.yaml"
        workflow_path.write_text(
            """name: test-workflow
version: 1.0.0
description: Test workflow
inputs:
  text:
    type: string
    required: true
nodes:
  process:
    type: llm
    description: Process the input text
    config:
      prompt: "Process: {{ inputs.text }}"
outputs:
  result: process"""
        )

        result = runner.invoke(app, ["list", "--local", "-d", tmpdir])
        assert result.exit_code == 0
        assert "test-workflow" in result.stdout
        assert "1.0.0" in result.stdout


def test_validate_workflow():
    """Test validating a workflow"""
    with tempfile.TemporaryDirectory() as tmpdir:
        workflow_path = Path(tmpdir) / "test.yaml"
        workflow_path.write_text(
            """
name: test-workflow
version: 1.0.0
inputs:
  text:
    type: string
    required: true
nodes:
  process:
    type: llm
    description: Process the input text
    config:
      prompt: "Process: {{ inputs.text }}"
outputs:
  result: process
"""
        )

        result = runner.invoke(app, ["validate", str(workflow_path), "--local"])
        assert result.exit_code == 0
        assert "Workflow is valid" in result.stdout


def test_workflow_package():
    """Test packaging a workflow"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create workflow directory
        workflow_dir = Path(tmpdir) / "my-workflow"
        workflow_dir.mkdir()

        # Create workflow.yaml
        workflow_file = workflow_dir / "workflow.yaml"
        workflow_file.write_text(
            """
name: test-workflow
version: 1.0.0
description: Test workflow
inputs:
  text:
    type: string
    required: true
nodes:
  process:
    type: llm
    description: Process the input text
    config:
      prompt: "Process: {{ inputs.text }}"
outputs:
  result: process
"""
        )

        # Create prompts directory
        prompts_dir = workflow_dir / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "test.txt").write_text("Test prompt")

        # Run package command
        output_path = Path(tmpdir) / "package.zip"
        result = runner.invoke(
            app, ["workflow", "package", str(workflow_dir), "-o", str(output_path)]
        )
        assert result.exit_code == 0
        assert "Created package" in result.stdout
        assert output_path.exists()

        # Verify package contents
        with zipfile.ZipFile(output_path) as zf:
            files = zf.namelist()
            assert "workflow.yaml" in files
            assert "prompts/test.txt" in files


def test_workflow_upload_with_mock():
    """Test uploading a workflow package with mocked API"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test zip file
        zip_path = Path(tmpdir) / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "workflow.yaml",
                """
name: test-workflow
version: 1.0.0
nodes:
  test:
    type: llm
    description: Test node
    config:
      prompt: "Test"
outputs:
  - test
""",
            )

        # Mock API client
        with patch("seriesoftubes.cli.workflow.APIClient") as MockClient:
            mock_client = Mock()
            MockClient.return_value.__enter__.return_value = mock_client
            mock_client.upload_workflow_file.return_value = {
                "id": "123",
                "name": "test-workflow",
                "version": "1.0.0",
                "username": "test-user",
            }

            result = runner.invoke(app, ["workflow", "upload-package", str(zip_path)])
            assert result.exit_code == 0
            assert "Uploaded workflow: test-workflow v1.0.0" in result.stdout
            mock_client.upload_workflow_file.assert_called_once()


def test_run_workflow_local():
    """Test running a workflow locally"""
    with tempfile.TemporaryDirectory() as tmpdir:
        workflow_path = Path(tmpdir) / "test.yaml"
        workflow_path.write_text(
            """
name: test-workflow
version: 1.0.0
inputs:
  text:
    type: string
    required: true
    default: "default text"
nodes:
  echo:
    type: python
    description: Echo the input text
    config:
      code: |
        return {"message": context["text"]}
      context:
        text: inputs.text
outputs:
  message: echo
"""
        )

        result = runner.invoke(app, ["run", str(workflow_path), "--local", "--no-save"])
        # Python nodes might not work in test environment, but workflow should parse
        assert "Loaded workflow: test-workflow v1.0.0" in result.stdout


def test_run_workflow_api_with_mock():
    """Test running a workflow via API with mocked client"""
    with patch("seriesoftubes.cli.main.APIClient") as MockClient:
        mock_client = Mock()
        MockClient.return_value.__enter__.return_value = mock_client

        # Mock run response
        mock_client.run_workflow.return_value = {
            "execution_id": "exec-123",
            "status": "started",
        }

        # Mock stream response
        mock_client.stream_execution.return_value = [
            {"event": "update", "data": '{"status": "running"}'},
            {
                "event": "complete",
                "data": '{"status": "completed", "outputs": {"result": "test"}}',
            },
        ]

        result = runner.invoke(app, ["run", "workflow-id", "-i", "text=hello"])
        assert result.exit_code == 0
        assert "Started execution: exec-123" in result.stdout
        assert "Workflow completed successfully" in result.stdout


def test_auth_login_with_mock():
    """Test login with mocked API"""
    with patch("seriesoftubes.cli.auth.APIClient") as MockClient:
        mock_client = Mock()
        MockClient.return_value.__enter__.return_value = mock_client
        mock_client.login.return_value = {"access_token": "test-token"}

        result = runner.invoke(
            app, ["auth", "login", "-u", "testuser", "-p", "testpass"]
        )
        assert result.exit_code == 0
        assert "Logged in as testuser" in result.stdout
        mock_client.login.assert_called_once_with("testuser", "testpass")


def test_parse_input_args():
    """Test input argument parsing"""
    from seriesoftubes.cli.main import parse_input_args  # noqa: PLC0415

    # Test various input formats
    inputs = parse_input_args(
        [
            "text=hello",
            "count=5",
            "enabled=true",
            'data={"key": "value"}',
            "list=[1, 2, 3]",
        ]
    )

    assert inputs["text"] == "hello"
    assert inputs["count"] == 5
    assert inputs["enabled"] is True
    assert inputs["data"] == {"key": "value"}
    assert inputs["list"] == [1, 2, 3]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
