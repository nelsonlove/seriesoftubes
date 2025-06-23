"""Tests for CLI commands"""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from seriesoftubes.cli import app, parse_input_args


class TestParseInputArgs:
    """Test input argument parsing"""

    def test_empty_inputs(self):
        """Test parsing empty inputs"""
        assert parse_input_args(None) == {}
        assert parse_input_args([]) == {}

    def test_string_values(self):
        """Test parsing string values"""
        inputs = parse_input_args(["name=John", "message=Hello world"])
        assert inputs == {"name": "John", "message": "Hello world"}

    def test_numeric_values(self):
        """Test parsing numeric values"""
        inputs = parse_input_args(["count=42", "price=19.99"])
        assert inputs == {"count": 42, "price": 19.99}

    def test_boolean_values(self):
        """Test parsing boolean values"""
        inputs = parse_input_args(["enabled=true", "disabled=false"])
        assert inputs == {"enabled": True, "disabled": False}

    def test_json_values(self):
        """Test parsing JSON values"""
        inputs = parse_input_args(
            ['data={"name": "John", "age": 30}', 'tags=["python", "cli"]']
        )
        assert inputs == {
            "data": {"name": "John", "age": 30},
            "tags": ["python", "cli"],
        }

    def test_mixed_values(self):
        """Test parsing mixed value types"""
        inputs = parse_input_args(
            ["text=hello", "count=5", "active=true", 'data={"key": "value"}']
        )
        assert inputs == {
            "text": "hello",
            "count": 5,
            "active": True,
            "data": {"key": "value"},
        }

    def test_invalid_format(self):
        """Test invalid input format"""
        from typer import BadParameter

        with pytest.raises(BadParameter, match="Invalid input format"):
            parse_input_args(["invalid"])


runner = CliRunner()


class TestCLI:
    """Test CLI commands"""

    def test_validate_command(self, tmp_path):
        """Test validate command"""
        # Create a simple workflow file
        workflow_file = tmp_path / "test.yaml"
        workflow_file.write_text(
            """
name: test_workflow
version: "1.0"
inputs:
  text: string
nodes:
  echo:
    type: route
    config:
      routes:
        - when: "true"
          to: "echo"
        - default: true
          to: "echo"
outputs:
  result: echo
"""
        )

        result = runner.invoke(app, ["validate", str(workflow_file)])
        assert result.exit_code == 0
        assert "✓ Parsed workflow: test_workflow v1.0" in result.stdout
        assert "✓ DAG structure is valid" in result.stdout
        assert "✓ Workflow is valid!" in result.stdout

    def test_validate_invalid_workflow(self, tmp_path):
        """Test validate command with invalid workflow"""
        workflow_file = tmp_path / "invalid.yaml"
        workflow_file.write_text("invalid: yaml: content:")

        result = runner.invoke(app, ["validate", str(workflow_file)])
        assert result.exit_code == 1
        assert "✗ Validation failed:" in result.stdout

    @patch("seriesoftubes.cli.run_workflow")
    def test_run_command(self, mock_run_workflow, tmp_path):
        """Test run command"""
        # Create a simple workflow file
        workflow_file = tmp_path / "test.yaml"
        workflow_file.write_text(
            """
name: test_workflow
version: "1.0"
inputs:
  text:
    type: string
    required: true
nodes:
  echo:
    type: route
    config:
      routes:
        - default: true
          to: "echo"
outputs:
  result: echo
"""
        )

        # Mock the run_workflow function
        mock_run_workflow.return_value = {
            "execution_id": "test-id",
            "start_time": "2023-01-01T00:00:00",
            "end_time": "2023-01-01T00:00:01",
            "success": True,
            "outputs": {"result": "echo"},
            "errors": {},
        }

        result = runner.invoke(
            app, ["run", str(workflow_file), "-i", "text=Hello", "--no-save"]
        )
        assert result.exit_code == 0
        assert "✓ Loaded workflow: test_workflow v1.0" in result.stdout
        assert "✓ Parsed inputs: ['text']" in result.stdout
        assert "✓ Workflow completed successfully!" in result.stdout
        assert "result: echo" in result.stdout

    @patch("seriesoftubes.cli.run_workflow")
    def test_run_command_with_error(self, mock_run_workflow, tmp_path):
        """Test run command with workflow error"""
        workflow_file = tmp_path / "test.yaml"
        workflow_file.write_text(
            """
name: test_workflow
nodes:
  fail:
    type: route
    config:
      routes:
        - default: true
          to: "fail"
"""
        )

        # Mock workflow failure
        mock_run_workflow.return_value = {
            "execution_id": "test-id",
            "start_time": "2023-01-01T00:00:00",
            "end_time": "2023-01-01T00:00:01",
            "success": False,
            "outputs": {},
            "errors": {"fail": "Test error"},
        }

        result = runner.invoke(app, ["run", str(workflow_file), "--no-save"])
        assert result.exit_code == 1
        assert "✗ Workflow failed!" in result.stdout
        assert "fail: Test error" in result.stdout

    def test_run_missing_file(self):
        """Test run command with missing file"""
        result = runner.invoke(app, ["run", "nonexistent.yaml"])
        assert result.exit_code == 1
        assert "✗" in result.stdout

    def test_list_command(self, tmp_path):
        """Test list command"""
        # Create test workflow files
        workflow1 = tmp_path / "workflow1.yaml"
        workflow1.write_text(
            """
name: workflow_one
version: "1.0"
description: Test workflow 1
nodes:
  node1:
    type: route
    config:
      routes:
        - default: true
          to: "node1"
"""
        )

        workflow2 = tmp_path / "subdir" / "workflow2.yml"
        workflow2.parent.mkdir()
        workflow2.write_text(
            """
name: workflow_two
version: "2.0"
nodes:
  node1:
    type: route
    config:
      routes:
        - default: true
          to: "node1"
  node2:
    type: route
    depends_on: [node1]
    config:
      routes:
        - default: true
          to: "node2"
"""
        )

        # Also create a non-workflow YAML (empty workflow with no nodes)
        (tmp_path / "not-workflow.yaml").write_text("name: empty\nversion: '1.0'")

        result = runner.invoke(app, ["list", "-d", str(tmp_path)])
        assert result.exit_code == 0
        assert "Found 2 workflow(s)" in result.stdout
        assert "workflow_one" in result.stdout
        assert "workflow_two" in result.stdout
        assert "1.0" in result.stdout
        assert "2.0" in result.stdout
        assert "Test workflow 1" in result.stdout

    def test_list_command_no_workflows(self, tmp_path):
        """Test list command with no workflows"""
        result = runner.invoke(app, ["list", "-d", str(tmp_path)])
        assert result.exit_code == 0
        assert "No YAML files found" in result.stdout

    def test_list_command_with_exclude(self, tmp_path):
        """Test list command with exclude patterns"""
        # Create workflows in different directories
        (tmp_path / "workflow.yaml").write_text(
            """
name: main_workflow
nodes:
  node1:
    type: route
    config:
      routes:
        - default: true
          to: "node1"
"""
        )
        
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "test_workflow.yaml").write_text(
            """
name: test_workflow
nodes:
  node1:
    type: route
    config:
      routes:
        - default: true
          to: "node1"
"""
        )
        
        # List without exclude
        result = runner.invoke(app, ["list", "-d", str(tmp_path)])
        assert "Found 2 workflow(s)" in result.stdout
        
        # List with exclude
        result = runner.invoke(app, ["list", "-d", str(tmp_path), "-e", "test/*"])
        assert "Found 1 workflow(s)" in result.stdout
        assert "main_workflow" in result.stdout
        assert "test_workflow" not in result.stdout

    def test_test_command_dry_run(self, tmp_path):
        """Test test command in dry-run mode"""
        workflow_file = tmp_path / "test.yaml"
        workflow_file.write_text(
            """
name: test_workflow
version: "1.0"
inputs:
  text:
    type: string
    required: true
  count:
    type: number
    required: false
    default: 5
nodes:
  echo:
    type: route
    config:
      routes:
        - default: true
          to: "echo"
outputs:
  result: echo
"""
        )

        result = runner.invoke(
            app, ["test", str(workflow_file), "--dry-run", "-i", "text=hello", "-v"]
        )
        assert result.exit_code == 0
        assert "✓ Loaded workflow: test_workflow v1.0" in result.stdout
        assert "✓ DAG structure is valid" in result.stdout
        assert "✓ All required inputs provided" in result.stdout
        assert "Workflow Details:" in result.stdout
        assert "text: string required" in result.stdout
        assert "count: number optional (default: 5)" in result.stdout
        assert "Dry run mode - workflow not executed" in result.stdout
        assert "✓ Workflow validation passed!" in result.stdout

    @patch("seriesoftubes.cli.run_workflow")
    def test_test_command_execute(self, mock_run_workflow, tmp_path):
        """Test test command with execution"""
        workflow_file = tmp_path / "test.yaml"
        workflow_file.write_text(
            """
name: test_workflow
inputs:
  text:
    type: string
    required: true
nodes:
  echo:
    type: route
    config:
      routes:
        - default: true
          to: "echo"
outputs:
  result: echo
"""
        )

        # Mock successful execution
        mock_run_workflow.return_value = {
            "execution_id": "test-id",
            "start_time": "2023-01-01T00:00:00",
            "end_time": "2023-01-01T00:00:01",
            "success": True,
            "outputs": {"result": "test output"},
            "errors": {},
        }

        result = runner.invoke(app, ["test", str(workflow_file), "-i", "text=hello"])
        assert result.exit_code == 0
        assert "✓ Test passed!" in result.stdout
        assert "result: test output" in result.stdout

    def test_test_command_missing_inputs(self, tmp_path):
        """Test test command with missing required inputs"""
        workflow_file = tmp_path / "test.yaml"
        workflow_file.write_text(
            """
name: test_workflow
inputs:
  required_input:
    type: string
    required: true
nodes:
  echo:
    type: route
    config:
      routes:
        - default: true
          to: "echo"
"""
        )

        result = runner.invoke(app, ["test", str(workflow_file), "--dry-run"])
        assert result.exit_code == 0
        assert "⚠ Missing required inputs: required_input" in result.stdout
