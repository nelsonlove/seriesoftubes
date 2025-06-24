"""Tests for API endpoints"""

import pytest
from fastapi.testclient import TestClient

from seriesoftubes.api.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def sample_workflow(tmp_path):
    """Create a sample workflow file"""
    workflow_path = tmp_path / "test_workflow.yaml"
    workflow_path.write_text(
        """
name: test-api-workflow
version: "1.0"
description: Test workflow for API

inputs:
  message:
    type: string
    required: true

nodes:
  echo:
    type: route
    config:
      routes:
        - default: true
          to: echo

outputs:
  result: echo
"""
    )
    return workflow_path


class TestAPIEndpoints:
    """Test API endpoints"""

    def test_root(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    def test_health(self, client):
        """Test health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_list_workflows(self, client, sample_workflow):
        """Test listing workflows"""
        # List workflows in the test directory
        response = client.get(
            "/workflows", params={"directory": str(sample_workflow.parent)}
        )
        assert response.status_code == 200
        workflows = response.json()
        assert isinstance(workflows, list)
        assert len(workflows) == 1
        assert workflows[0]["name"] == "test-api-workflow"

    def test_list_workflows_invalid_dir(self, client):
        """Test listing workflows with invalid directory"""
        response = client.get("/workflows", params={"directory": "/nonexistent"})
        assert response.status_code == 404

    def test_get_workflow(self, client, sample_workflow):
        """Test getting a specific workflow"""
        response = client.get(f"/workflows/{sample_workflow}")
        assert response.status_code == 200
        workflow = response.json()
        assert workflow["name"] == "test-api-workflow"
        assert workflow["version"] == "1.0"
        assert "message" in workflow["inputs"]

    def test_get_workflow_not_found(self, client):
        """Test getting non-existent workflow"""
        response = client.get("/workflows/nonexistent.yaml")
        assert response.status_code == 404

    def test_run_workflow(self, client, sample_workflow):
        """Test running a workflow"""
        response = client.post(
            f"/workflows/{sample_workflow}/run",
            json={"inputs": {"message": "hello"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert data["status"] == "started"

        # Give it a moment to execute
        import time

        time.sleep(0.5)

    def test_run_workflow_missing_input(self, client, sample_workflow):
        """Test running workflow without required input"""
        response = client.post(
            f"/workflows/{sample_workflow}/run",
            json={"inputs": {}},
        )
        # The execution will be created but will fail during execution
        assert response.status_code == 200

    def test_list_executions(self, client, sample_workflow):
        """Test listing executions"""
        # First run a workflow
        run_response = client.post(
            f"/workflows/{sample_workflow}/run",
            json={"inputs": {"message": "test"}},
        )
        execution_id = run_response.json()["execution_id"]

        # List executions
        response = client.get("/executions")
        assert response.status_code == 200
        executions = response.json()
        assert isinstance(executions, list)
        assert any(e["execution_id"] == execution_id for e in executions)

    def test_get_execution(self, client, sample_workflow):
        """Test getting execution details"""
        # Run a workflow
        run_response = client.post(
            f"/workflows/{sample_workflow}/run",
            json={"inputs": {"message": "test"}},
        )
        execution_id = run_response.json()["execution_id"]

        # Get execution details
        response = client.get(f"/executions/{execution_id}")
        assert response.status_code == 200
        execution = response.json()
        assert execution["execution_id"] == execution_id
        assert "status" in execution
        assert "workflow_name" in execution

    def test_get_execution_not_found(self, client):
        """Test getting non-existent execution"""
        response = client.get("/executions/nonexistent-id")
        assert response.status_code == 404

    def test_stream_execution(self, client, sample_workflow):
        """Test streaming execution updates"""
        # Run a workflow
        run_response = client.post(
            f"/workflows/{sample_workflow}/run",
            json={"inputs": {"message": "test"}},
        )
        execution_id = run_response.json()["execution_id"]

        # Stream updates (just test that endpoint exists)
        # Note: TestClient doesn't support SSE well, so just check it doesn't 404
        with client.stream("GET", f"/executions/{execution_id}/stream") as response:
            assert response.status_code == 200
            # In a real test, we'd parse SSE events here

    def test_invalid_workflow_yaml(self, client, tmp_path):
        """Test handling invalid workflow YAML"""
        bad_workflow = tmp_path / "bad.yaml"
        bad_workflow.write_text("invalid: yaml: content: [")

        response = client.get(f"/workflows/{bad_workflow}")
        assert response.status_code == 400
