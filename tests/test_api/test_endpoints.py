"""Tests for API endpoints"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from seriesoftubes.api.auth import get_current_active_user
from seriesoftubes.api.main import app
from seriesoftubes.db import User, get_db


@pytest.fixture
def mock_user():
    """Create a mock user for testing"""
    return User(
        id="12345678-1234-5678-1234-567812345678",
        username="testuser",
        email="test@example.com",
        is_active=True,
        is_system=False,
        password_hash="dummy-hash",
    )


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    session = AsyncMock(spec=AsyncSession)

    # Mock the execute method to return empty results by default
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    # Mock the add, commit, refresh methods
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()

    return session


@pytest.fixture
def client(mock_user, mock_db_session):
    """Create test client with mocked authentication and database"""
    # Override the authentication dependency
    app.dependency_overrides[get_current_active_user] = lambda: mock_user
    # Override the database dependency
    app.dependency_overrides[get_db] = lambda: mock_db_session

    client = TestClient(app)
    yield client
    # Clean up
    app.dependency_overrides.clear()


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
    type: conditional
    config:
      conditions:
        - is_default: true
          then: echo

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

    def test_list_workflows(self, client):
        """Test listing workflows"""
        # List workflows from database (initially empty for test user)
        response = client.get("/api/workflows")
        assert response.status_code == 200
        workflows = response.json()
        assert isinstance(workflows, list)
        # Should be empty since we haven't created any workflows

    def test_list_workflows_with_filter(self, client):
        """Test listing workflows with include_public filter"""
        response = client.get("/api/workflows", params={"include_public": False})
        assert response.status_code == 200
        workflows = response.json()
        assert isinstance(workflows, list)

    def test_get_workflow(self, client):
        """Test getting a specific workflow"""
        # This would normally test with a workflow ID from the database
        # For now, test that non-existent ID returns 404
        response = client.get("/api/workflows/nonexistent-id")
        assert response.status_code == 404

    def test_create_workflow(self, client, mock_db_session, mock_user):
        """Test creating a workflow"""
        yaml_content = """name: test-workflow
version: 1.0.0
nodes:
  echo:
    type: llm
    config:
      prompt: "Hello"
outputs:
  result: echo"""

        # Mock the database responses
        # First, mock the check for existing workflow (should return None)
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

        # Mock the refresh to populate the created workflow
        async def mock_refresh(obj):
            obj.id = "workflow-123"
            obj.created_at = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")
            obj.updated_at = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.post(
            "/api/workflows",
            json={"yaml_content": yaml_content, "is_public": False},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-workflow"
        assert data["version"] == "1.0.0"
        assert data["username"] == "testuser"

    def test_run_workflow_not_found(self, client):
        """Test running a non-existent workflow"""
        response = client.post(
            "/api/workflows/nonexistent-id/run",
            json={"inputs": {"message": "hello"}},
        )
        assert response.status_code == 404

    def test_validate_workflow(self, client):
        """Test validating a workflow"""
        # This would normally test with a workflow ID
        # For now, test that non-existent ID returns 404
        response = client.post(
            "/api/workflows/nonexistent-id/validate",
            json={},
        )
        assert response.status_code == 404

    def test_list_executions(self, client):
        """Test listing executions"""
        # List executions (should be empty for test user)
        response = client.get("/api/executions")
        assert response.status_code == 200
        executions = response.json()
        assert isinstance(executions, list)

    def test_get_execution(self, client):
        """Test getting execution details"""
        # Test with non-existent execution ID
        response = client.get("/api/executions/nonexistent-id")
        assert response.status_code == 404

    def test_get_execution_not_found(self, client):
        """Test getting non-existent execution"""
        response = client.get("/api/executions/nonexistent-id")
        assert response.status_code == 404

    def test_stream_execution_not_found(self, client, mock_user, mock_db_session):
        """Test streaming non-existent execution"""
        from seriesoftubes.api.auth import create_access_token
        
        # Create a valid JWT token for the mock user
        token = create_access_token(data={"sub": mock_user.id})
        
        # Create two mock results - one for user lookup (found), one for execution lookup (not found)
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = mock_user
        
        execution_result = MagicMock()
        execution_result.scalar_one_or_none.return_value = None  # Execution not found
        
        # Set up execute to return user first, then execution not found
        mock_db_session.execute.side_effect = [user_result, execution_result]
        
        response = client.get(f"/api/executions/nonexistent-id/stream?token={token}")
        assert response.status_code == 404

    def test_invalid_workflow_yaml(self, client):
        """Test handling invalid workflow YAML"""
        # Try to create workflow with invalid YAML
        response = client.post(
            "/api/workflows",
            json={"yaml_content": "invalid: yaml: content: [", "is_public": False},
        )
        assert response.status_code == 400
