"""Tests for execution routes"""

import json
import pytest
from datetime import datetime, timezone
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from seriesoftubes.api.main import app
from seriesoftubes.api.auth import get_current_active_user
from seriesoftubes.db import User, Workflow, Execution, ExecutionStatus, get_db


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
def sample_workflow(mock_user):
    """Create a sample workflow"""
    return Workflow(
        id=str(uuid4()),
        name="test-workflow",
        version="1.0.0",
        description="Test workflow",
        user_id=mock_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        is_public=False,
        package_path="/tmp/test-workflow",
        yaml_content="name: test-workflow\nversion: 1.0.0\n",
    )


@pytest.fixture
def sample_execution(mock_user, sample_workflow):
    """Create a sample execution"""
    execution = Execution(
        id=str(uuid4()),
        workflow_id=sample_workflow.id,
        user_id=mock_user.id,
        status=ExecutionStatus.COMPLETED.value,  # Use the string value
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        inputs={"message": "test"},
        outputs={"result": "success"},
        errors=None,
        progress={"nodes_completed": 2, "total_nodes": 2}
    )
    # Add relationships for response serialization
    execution.workflow = sample_workflow
    execution.user = mock_user
    return execution


class TestExecutionRoutes:
    """Test execution routes"""
    
    def test_list_executions_empty(self, client, mock_db_session):
        """Test listing executions when none exist"""
        response = client.get("/api/executions")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        
    def test_list_executions_with_results(self, client, mock_db_session, sample_execution):
        """Test listing executions with results"""
        # Mock query to return executions
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_execution]
        mock_db_session.execute.return_value = mock_result
        
        response = client.get("/api/executions")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "completed"
        # Check that the execution is in the list
        assert data[0]["workflow_id"] == sample_execution.workflow_id
        
    def test_list_executions_with_filters(self, client, mock_db_session):
        """Test listing executions with filters"""
        response = client.get("/api/executions?workflow_id=123&status=running")
        assert response.status_code == status.HTTP_200_OK
        
        # Verify query was built with filters
        execute_call = mock_db_session.execute.call_args[0][0]
        assert execute_call is not None
        
    def test_list_executions_pagination(self, client, mock_db_session, mock_user):
        """Test execution pagination"""
        # Create multiple executions with proper attributes
        executions = []
        for i in range(5):
            workflow = MagicMock()
            workflow.id = str(uuid4())
            workflow.name = f"workflow-{i}"
            workflow.version = "1.0.0"
            
            execution = MagicMock()
            execution.id = str(uuid4())
            execution.workflow_id = workflow.id
            execution.workflow = workflow
            execution.user_id = mock_user.id
            execution.user = mock_user
            execution.status = "completed"  # Store as string like the DB does
            execution.inputs = {"test": f"input-{i}"}
            execution.outputs = {"result": f"output-{i}"}
            execution.errors = None
            execution.progress = {}
            execution.storage_keys = {}
            execution.started_at = datetime.now(timezone.utc)
            execution.completed_at = datetime.now(timezone.utc)
            executions.append(execution)
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = executions
        mock_db_session.execute.return_value = mock_result
        
        response = client.get("/api/executions?limit=5&offset=0")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 5
        
    def test_get_execution_success(self, client, mock_db_session, sample_execution):
        """Test getting a specific execution"""
        # Mock query to return execution
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_execution
        mock_db_session.execute.return_value = mock_result
        
        response = client.get(f"/api/executions/{sample_execution.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sample_execution.id
        assert data["status"] == "completed"
        assert data["outputs"] == {"result": "success"}
        assert data["progress"] == {"nodes_completed": 2, "total_nodes": 2}
        
    def test_get_execution_not_found(self, client, mock_db_session):
        """Test getting non-existent execution"""
        execution_id = str(uuid4())
        response = client.get(f"/api/executions/{execution_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
    def test_get_execution_not_owner(self, client, mock_db_session, sample_execution):
        """Test getting execution when not the owner"""
        # Change execution owner
        sample_execution.user_id = "different-user-id"
        
        # Mock execution query to return execution not owned by user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Not found for this user
        mock_db_session.execute.return_value = mock_result
        
        response = client.get(f"/api/executions/{sample_execution.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
    def test_stream_execution_not_found(self, client, mock_db_session, mock_user):
        """Test streaming non-existent execution"""
        execution_id = str(uuid4())
        
        # Mock user lookup (for token verification)
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = mock_user
        
        # Mock execution lookup (not found)
        execution_result = MagicMock()
        execution_result.scalar_one_or_none.return_value = None
        
        # Set up execute to return user first, then execution not found
        mock_db_session.execute.side_effect = [user_result, execution_result]
        
        # Need a token for streaming endpoint
        from seriesoftubes.api.auth import create_access_token
        token = create_access_token(data={"sub": mock_user.id})
        
        response = client.get(f"/api/executions/{execution_id}/stream?token={token}")
        # Should return 404 since execution doesn't exist
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
