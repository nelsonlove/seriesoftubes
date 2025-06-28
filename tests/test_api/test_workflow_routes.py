"""Tests for workflow routes"""

import json
import pytest
from datetime import datetime, timezone
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from seriesoftubes.api.main import app
from seriesoftubes.api.auth import get_current_active_user
from seriesoftubes.db import User, Workflow, get_db
# WorkflowStatus not used in current implementation


@pytest.fixture
def mock_user():
    """Create a mock user for testing"""
    return User(
        id=str(uuid4()),
        username="testuser",
        email="test@example.com",
        is_active=True,
        is_admin=False,
        is_system=False,
        password_hash="dummy-hash",
    )


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    session = AsyncMock()
    
    # Mock query results
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar.return_value = 0
    session.execute.return_value = mock_result
    
    # Mock transaction methods
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    
    return session


@pytest.fixture
def client(mock_user, mock_db_session):
    """Create test client with mocked dependencies"""
    app.dependency_overrides[get_current_active_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db_session
    
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_workflow_yaml():
    """Sample workflow YAML content"""
    return """
name: test-workflow
version: 1.0.0
description: A test workflow

inputs:
  message:
    type: string
    required: true

nodes:
  echo:
    type: python
    config:
      code: |
        result = {"echo": inputs["message"]}

outputs:
  result: echo.result
"""


@pytest.fixture
def sample_workflow(mock_user, sample_workflow_yaml):
    """Create a sample workflow for testing"""
    workflow = Workflow(
        id=str(uuid4()),
        name="test-workflow",
        version="1.0.0",
        description="A test workflow",
        user_id=mock_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        is_public=False,
        package_path="/tmp/test-workflow",
        yaml_content=sample_workflow_yaml,
    )
    # Add the user relationship for response serialization
    workflow.user = mock_user
    return workflow


class TestWorkflowRoutes:
    """Test workflow routes"""
    
    def test_list_workflows_empty(self, client, mock_db_session):
        """Test listing workflows when none exist"""
        response = client.get("/api/workflows")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        
    def test_list_workflows_with_results(self, client, mock_db_session, sample_workflow):
        """Test listing workflows with results"""
        # Mock query to return workflows
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_workflow]
        mock_db_session.execute.return_value = mock_result
        
        response = client.get("/api/workflows")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "test-workflow"
        
    def test_list_workflows_with_filters(self, client, mock_db_session):
        """Test listing workflows with query filters"""
        response = client.get("/api/workflows?search=workflow&is_public=true")
        assert response.status_code == status.HTTP_200_OK
        
        # Verify query was built correctly
        execute_call = mock_db_session.execute.call_args[0][0]
        assert execute_call is not None  # Query was created
        
    def test_list_workflows_pagination(self, client, mock_db_session):
        """Test workflow pagination"""
        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50
        
        # Mock workflow query
        mock_workflow_result = MagicMock()
        mock_workflow_result.scalars.return_value.all.return_value = []
        
        mock_db_session.execute.side_effect = [mock_count_result, mock_workflow_result]
        
        response = client.get("/api/workflows?limit=10&offset=20")
        assert response.status_code == status.HTTP_200_OK
        
    def test_create_workflow_success(self, client, mock_db_session, mock_user, sample_workflow_yaml):
        """Test successful workflow creation"""
        workflow_data = {
            "yaml_content": sample_workflow_yaml,
            "is_public": False
        }
        
        # Mock the refresh to simulate database creating the workflow
        def mock_refresh(workflow):
            workflow.id = "new-workflow-id"
            workflow.created_at = datetime.now(timezone.utc)
            workflow.updated_at = datetime.now(timezone.utc)
            workflow.user = mock_user
            
        mock_db_session.refresh.side_effect = mock_refresh
        
        # Mock the created workflow
        with patch("seriesoftubes.parser.parse_workflow_yaml") as mock_parse:
            mock_parsed = MagicMock()
            mock_parsed.name = "test-workflow"
            mock_parsed.version = "1.0.0"
            mock_parsed.description = "A test workflow"  # This comes from the parsed YAML
            mock_parse.return_value = mock_parsed
            
            with patch("seriesoftubes.parser.validate_dag") as mock_validate:
                mock_validate.return_value = None
                
                response = client.post("/api/workflows", json=workflow_data)
            
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "test-workflow"
        assert data["description"] == "A test workflow"  # From parsed workflow
        
        # Verify database interaction
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called()
        
    def test_create_workflow_invalid_yaml(self, client):
        """Test creating workflow with invalid YAML"""
        workflow_data = {
            "yaml_content": "invalid: yaml: content:",
            "description": "Invalid workflow"
        }
        
        response = client.post("/api/workflows", json=workflow_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid workflow" in response.json()["detail"]
        
    def test_get_workflow_success(self, client, mock_db_session, sample_workflow):
        """Test getting a specific workflow"""
        # Mock query to return workflow
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_workflow
        mock_db_session.execute.return_value = mock_result
        
        response = client.get(f"/api/workflows/{sample_workflow.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sample_workflow.id
        assert data["name"] == "test-workflow"
        
    def test_get_workflow_not_found(self, client, mock_db_session):
        """Test getting non-existent workflow"""
        workflow_id = str(uuid4())
        response = client.get(f"/api/workflows/{workflow_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
    def test_update_workflow_success(self, client, mock_db_session, sample_workflow, sample_workflow_yaml):
        """Test updating a workflow"""
        # First mock: return workflow for ownership check
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = sample_workflow
        
        # Second mock: return None for conflict check (no conflict)
        conflict_result = MagicMock()
        conflict_result.scalar_one_or_none.return_value = None
        
        mock_db_session.execute.side_effect = [workflow_result, conflict_result]
        
        # Update requires yaml_content
        updated_yaml = sample_workflow_yaml.replace("A test workflow", "Updated description")
        update_data = {
            "yaml_content": updated_yaml,
            "is_public": True
        }
        
        # Mock parse_workflow_yaml for the update
        with patch("seriesoftubes.api.workflow_routes.parse_workflow_yaml") as mock_parse:
            mock_parsed = MagicMock()
            mock_parsed.name = "test-workflow"
            mock_parsed.version = "1.0.0"
            mock_parsed.description = "Updated description"
            mock_parse.return_value = mock_parsed
            
            with patch("seriesoftubes.api.workflow_routes.validate_dag") as mock_validate:
                mock_validate.return_value = None
                
                response = client.put(f"/api/workflows/{sample_workflow.id}", json=update_data)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify workflow was updated
        assert sample_workflow.description == "Updated description"
        assert sample_workflow.is_public is True
        mock_db_session.commit.assert_called()
        
    def test_update_workflow_not_owner(self, client, mock_db_session, sample_workflow, mock_user, sample_workflow_yaml):
        """Test updating workflow when not the owner"""
        # Change workflow owner
        sample_workflow.user_id = "different-user-id"
        
        # Mock query to return None (workflow not found for this user)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        update_data = {
            "yaml_content": sample_workflow_yaml,
            "is_public": True
        }
        
        response = client.put(f"/api/workflows/{sample_workflow.id}", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
    def test_delete_workflow_success(self, client, mock_db_session, sample_workflow):
        """Test deleting a workflow"""
        # Mock query to return workflow
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_workflow
        mock_db_session.execute.return_value = mock_result
        
        response = client.delete(f"/api/workflows/{sample_workflow.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "deleted" in data["message"]
        
        mock_db_session.delete.assert_called_once_with(sample_workflow)
        mock_db_session.commit.assert_called()
        
    def test_delete_workflow_not_owner(self, client, mock_db_session, sample_workflow):
        """Test deleting workflow when not the owner"""
        sample_workflow.user_id = "different-user-id"
        
        # Mock query to return None (workflow not found for this user)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        response = client.delete(f"/api/workflows/{sample_workflow.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
    def test_validate_workflow_success(self, client, mock_db_session, sample_workflow):
        """Test validating a workflow"""
        # Mock getting workflow
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_workflow
        mock_db_session.execute.return_value = mock_result
        
        with patch("seriesoftubes.api.workflow_routes.parse_workflow_yaml") as mock_parse:
            mock_parsed = MagicMock()
            mock_parsed.name = "test-workflow"
            mock_parsed.version = "1.0.0"
            mock_parsed.inputs = {}
            mock_parsed.nodes = {}
            mock_parsed.outputs = {}
            mock_parsed.description = "Test workflow"
            mock_parse.return_value = mock_parsed
            
            with patch("seriesoftubes.api.workflow_routes.validate_dag") as mock_validate_dag:
                mock_validate_dag.return_value = None  # No errors
                
                response = client.post(
                    f"/api/workflows/{sample_workflow.id}/validate",
                    json={}  # Validate existing YAML
                )
            
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert "parsed_structure" in data
        assert data["parsed_structure"]["name"] == "test-workflow"
        
    def test_validate_workflow_invalid(self, client, mock_db_session, sample_workflow):
        """Test validating invalid workflow"""
        # Mock getting workflow
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_workflow
        mock_db_session.execute.return_value = mock_result
        
        with patch("seriesoftubes.api.workflow_routes.parse_workflow_yaml") as mock_parse:
            mock_parse.side_effect = Exception("Invalid YAML")
            
            response = client.post(
                f"/api/workflows/{sample_workflow.id}/validate",
                json={"yaml_content": "invalid: yaml:"}
            )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert "errors" in data
        
    def test_test_workflow_not_implemented(self, client, mock_db_session, sample_workflow):
        """Test dry-run workflow execution (not implemented)"""
        # Mock getting workflow
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_workflow
        mock_db_session.execute.return_value = mock_result
        
        response = client.post(
            f"/api/workflows/{sample_workflow.id}/test",
            json={"inputs": {"message": "test"}}
        )
        
        # This endpoint is not yet implemented
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        
    def test_download_workflow(self, client, mock_db_session, sample_workflow):
        """Test downloading workflow as YAML"""
        # Mock getting workflow
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_workflow
        mock_db_session.execute.return_value = mock_result
        
        response = client.get(f"/api/workflows/{sample_workflow.id}/download")
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/x-yaml"
        assert "attachment" in response.headers["content-disposition"]
        
    def test_run_workflow_success(self, client, mock_db_session, sample_workflow):
        """Test running a workflow"""
        # Mock getting workflow
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_workflow
        mock_db_session.execute.return_value = mock_result
        
        # Mock the refresh to add an ID to the execution
        def mock_refresh(execution):
            execution.id = "execution-123"
            
        mock_db_session.refresh.side_effect = mock_refresh
        
        # Mock parse_workflow_yaml
        with patch("seriesoftubes.api.workflow_routes.parse_workflow_yaml") as mock_parse:
            mock_parsed = MagicMock()
            mock_parsed.outputs = {"result": "echo"}
            mock_parse.return_value = mock_parsed
            
            # Mock the DatabaseProgressTrackingEngine (imported inline in the function)
            with patch("seriesoftubes.api.execution.DatabaseProgressTrackingEngine") as mock_engine_class:
                mock_engine = MagicMock()
                mock_context = MagicMock()
                mock_context.outputs = {"echo": {"result": "hello"}}
                mock_context.errors = {}
                mock_engine.execute = AsyncMock(return_value=mock_context)
                mock_engine_class.return_value = mock_engine
                
                response = client.post(
                    f"/api/workflows/{sample_workflow.id}/run",
                    json={
                        "inputs": {"message": "hello"},
                        "sync": False
                    }
                )
            
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "execution_id" in data
        assert data["status"] == "started"
        
