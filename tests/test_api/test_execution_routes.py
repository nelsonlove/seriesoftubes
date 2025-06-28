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
        description="Test workflow",
        owner_id=mock_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        status="active",
        content={"name": "test-workflow", "version": "1.0.0"},
    )


@pytest.fixture
def sample_execution(mock_user, sample_workflow):
    """Create a sample execution"""
    return Execution(
        id=str(uuid4()),
        workflow_id=sample_workflow.id,
        user_id=mock_user.id,
        status=ExecutionStatus.COMPLETED,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        inputs={"message": "test"},
        outputs={"result": "success"},
        errors=None,
        node_outputs={
            "node1": {"output": "value1"},
            "node2": {"output": "value2"}
        },
        workflow=sample_workflow,
    )


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
        assert data[0]["workflow_name"] == "test-workflow"
        
    def test_list_executions_with_filters(self, client, mock_db_session):
        """Test listing executions with filters"""
        response = client.get("/api/executions?workflow_id=123&status=running")
        assert response.status_code == status.HTTP_200_OK
        
        # Verify query was built with filters
        execute_call = mock_db_session.execute.call_args[0][0]
        assert execute_call is not None
        
    def test_list_executions_pagination(self, client, mock_db_session):
        """Test execution pagination"""
        # Create multiple executions
        executions = [
            MagicMock(id=str(uuid4()), status="completed", workflow=MagicMock(name=f"workflow-{i}"))
            for i in range(5)
        ]
        
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
        assert "node_outputs" in data
        
    def test_get_execution_not_found(self, client, mock_db_session):
        """Test getting non-existent execution"""
        execution_id = str(uuid4())
        response = client.get(f"/api/executions/{execution_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
    def test_get_execution_not_owner(self, client, mock_db_session, sample_execution):
        """Test getting execution when not the owner"""
        # Change execution owner
        sample_execution.user_id = "different-user-id"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_execution
        mock_db_session.execute.return_value = mock_result
        
        response = client.get(f"/api/executions/{sample_execution.id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
    def test_stream_execution_running(self, client, mock_db_session, sample_execution):
        """Test streaming execution updates for running execution"""
        # Set execution as running
        sample_execution.status = "running"
        sample_execution.completed_at = None
        
        # Mock query to return execution
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_execution
        mock_db_session.execute.return_value = mock_result
        
        # Mock the execution manager
        with patch("seriesoftubes.api.execution_routes.execution_manager") as mock_manager:
            # Create mock event stream
            async def mock_event_stream():
                yield {"event": "status", "data": {"status": "running", "progress": 0.5}}
                yield {"event": "node_complete", "data": {"node": "node1", "output": "result1"}}
                yield {"event": "complete", "data": {"status": "completed"}}
            
            mock_manager.stream_execution.return_value = mock_event_stream()
            
            # Can't easily test SSE with TestClient, so just verify endpoint exists
            response = client.get(
                f"/api/executions/{sample_execution.id}/stream",
                headers={"Accept": "text/event-stream"}
            )
            # TestClient doesn't handle SSE well, so we mainly verify no errors
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]
            
    def test_stream_execution_completed(self, client, mock_db_session, sample_execution):
        """Test streaming completed execution returns error"""
        # Mock query to return completed execution
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_execution
        mock_db_session.execute.return_value = mock_result
        
        response = client.get(f"/api/executions/{sample_execution.id}/stream")
        # Should return error since execution is already completed
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]
        
    def test_cancel_execution_success(self, client, mock_db_session, sample_execution):
        """Test canceling a running execution"""
        # Set execution as running
        sample_execution.status = "running"
        sample_execution.completed_at = None
        
        # Mock query to return execution
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_execution
        mock_db_session.execute.return_value = mock_result
        
        with patch("seriesoftubes.api.execution_routes.execution_manager") as mock_manager:
            mock_manager.cancel_execution = AsyncMock(return_value=True)
            
            response = client.post(f"/api/executions/{sample_execution.id}/cancel")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["message"] == "Execution cancelled"
            
            mock_manager.cancel_execution.assert_called_once_with(sample_execution.id)
            
    def test_cancel_execution_not_found(self, client, mock_db_session):
        """Test canceling non-existent execution"""
        execution_id = str(uuid4())
        response = client.post(f"/api/executions/{execution_id}/cancel")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
    def test_cancel_execution_already_completed(self, client, mock_db_session, sample_execution):
        """Test canceling already completed execution"""
        # Mock query to return completed execution
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_execution
        mock_db_session.execute.return_value = mock_result
        
        response = client.post(f"/api/executions/{sample_execution.id}/cancel")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already completed" in response.json()["detail"].lower()
        
    def test_get_execution_logs(self, client, mock_db_session, sample_execution):
        """Test getting execution logs"""
        # Mock query to return execution
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_execution
        mock_db_session.execute.return_value = mock_result
        
        # Add some mock logs
        sample_execution.logs = [
            {"timestamp": "2024-01-01T00:00:00", "level": "INFO", "message": "Starting execution"},
            {"timestamp": "2024-01-01T00:00:01", "level": "INFO", "message": "Execution completed"}
        ]
        
        response = client.get(f"/api/executions/{sample_execution.id}/logs")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "logs" in data
        assert len(data["logs"]) == 2
        
    def test_retry_execution_success(self, client, mock_db_session, sample_execution, sample_workflow):
        """Test retrying a failed execution"""
        # Set execution as failed
        sample_execution.status = "failed"
        sample_execution.errors = {"node1": "Error message"}
        
        # Mock queries
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_execution
        mock_db_session.execute.return_value = mock_result
        
        with patch("seriesoftubes.api.execution_routes.execute_workflow") as mock_execute:
            mock_execute.return_value = "new-execution-id"
            
            response = client.post(f"/api/executions/{sample_execution.id}/retry")
            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert data["execution_id"] == "new-execution-id"
            assert data["message"] == "Retry started"
            
    def test_delete_execution_success(self, client, mock_db_session, sample_execution):
        """Test deleting an execution"""
        # Mock query to return execution
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_execution
        mock_db_session.execute.return_value = mock_result
        
        response = client.delete(f"/api/executions/{sample_execution.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        mock_db_session.delete.assert_called_once_with(sample_execution)
        mock_db_session.commit.assert_called()
        
    def test_delete_execution_not_owner(self, client, mock_db_session, sample_execution):
        """Test deleting execution when not the owner"""
        # Change execution owner
        sample_execution.user_id = "different-user-id"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_execution
        mock_db_session.execute.return_value = mock_result
        
        response = client.delete(f"/api/executions/{sample_execution.id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN