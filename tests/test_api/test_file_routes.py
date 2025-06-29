"""Tests for file management API routes"""

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from seriesoftubes.api.main import app
from seriesoftubes.api.auth import get_current_user
from seriesoftubes.db import User, get_db
from seriesoftubes.storage.base import StorageFile


def test_upload_file(client_with_auth, mock_storage_backend):
    """Test file upload endpoint"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.upload.return_value = StorageFile(
        key="user123/uploads/file-id/test.txt",
        size=100,
        content_type="text/plain",
        last_modified="2024-01-01T00:00:00Z"
    )
    mock_storage_backend.return_value = mock_storage
    
    # Create file upload
    file_content = b"Test file content"
    files = {"file": ("test.txt", file_content, "text/plain")}
    
    response = client_with_auth.post(
        "/api/files/upload",
        files=files,
        params={"is_public": False}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["success"] is True
    assert data["filename"] == "test.txt"
    assert data["size"] == 100
    assert data["content_type"] == "text/plain"
    assert "file_id" in data
    
    # Verify storage was called correctly
    mock_storage.upload.assert_called_once()
    call_args = mock_storage.upload.call_args[1]
    assert call_args["content"] == file_content
    assert call_args["content_type"] == "text/plain"


def test_upload_public_file(client_with_auth, mock_storage_backend):
    """Test uploading a public file"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.upload.return_value = StorageFile(
        key="public/file-id/test.txt",
        size=100,
        content_type="text/plain",
        last_modified="2024-01-01T00:00:00Z"
    )
    mock_storage_backend.return_value = mock_storage
    
    # Create file upload
    files = {"file": ("test.txt", b"Public content", "text/plain")}
    
    response = client_with_auth.post(
        "/api/files/upload",
        files=files,
        params={"is_public": True}
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verify public path was used
    call_args = mock_storage.upload.call_args[1]
    assert call_args["key"].startswith("public/")


def test_list_files(client_with_auth, mock_storage_backend):
    """Test file listing endpoint"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.list.return_value = [
        StorageFile(
            key="user123/uploads/id1/file1.txt",
            size=100,
            content_type="text/plain",
            last_modified="2024-01-01T00:00:00Z"
        ),
        StorageFile(
            key="user123/uploads/id2/file2.json",
            size=200,
            content_type="application/json",
            last_modified="2024-01-02T00:00:00Z"
        ),
    ]
    mock_storage_backend.return_value = mock_storage
    
    response = client_with_auth.get("/api/files")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["success"] is True
    assert len(data["files"]) == 2
    assert data["total"] == 2
    
    # Check first file
    file1 = data["files"][0]
    assert file1["file_id"] == "id1"
    assert file1["filename"] == "file1.txt"
    assert file1["size"] == 100
    assert file1["content_type"] == "text/plain"
    assert file1["is_public"] is False


def test_list_files_with_prefix(client_with_auth, mock_storage_backend):
    """Test file listing with prefix filter"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.list.return_value = []
    mock_storage_backend.return_value = mock_storage
    
    response = client_with_auth.get(
        "/api/files",
        params={"prefix": "documents/"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verify prefix was used in storage call
    mock_storage.list.assert_called()
    call_args = mock_storage.list.call_args[1]
    assert "user123/uploads/documents/" in call_args["prefix"]


def test_download_file(client_with_auth, mock_storage_backend):
    """Test file download endpoint"""
    # Setup mock storage
    mock_storage = AsyncMock()
    file_content = b"Downloaded content"
    mock_storage.download.return_value = file_content
    mock_storage.list.return_value = [
        StorageFile(
            key="user123/uploads/file-id/test.txt",
            size=len(file_content),
            content_type="text/plain",
            last_modified="2024-01-01T00:00:00Z"
        )
    ]
    mock_storage_backend.return_value = mock_storage
    
    response = client_with_auth.get("/api/files/file-id/download")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == file_content
    assert response.headers["content-type"].startswith("text/plain")
    assert 'attachment; filename="test.txt"' in response.headers["content-disposition"]


def test_download_nonexistent_file(client_with_auth, mock_storage_backend):
    """Test downloading a non-existent file"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.list.return_value = []  # No files found
    mock_storage_backend.return_value = mock_storage
    
    response = client_with_auth.get("/api/files/nonexistent/download")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "File not found" in response.json()["detail"]


def test_get_file_url(client_with_auth, mock_storage_backend):
    """Test getting pre-signed URL for file"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.list.return_value = [
        StorageFile(
            key="user123/uploads/file-id/test.txt",
            size=100,
            content_type="text/plain",
            last_modified="2024-01-01T00:00:00Z"
        )
    ]
    mock_storage.get_url.return_value = "https://storage.example.com/signed-url"
    mock_storage_backend.return_value = mock_storage
    
    response = client_with_auth.get(
        "/api/files/file-id/url",
        params={"expires_in": 7200}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["url"] == "https://storage.example.com/signed-url"
    assert data["expires_in"] == 7200
    
    # Verify get_url was called with correct expiration
    mock_storage.get_url.assert_called_once_with(
        "user123/uploads/file-id/test.txt",
        expires_in=7200
    )


def test_delete_file(client_with_auth, mock_storage_backend):
    """Test file deletion endpoint"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.list.return_value = [
        StorageFile(
            key="user123/uploads/file-id/test.txt",
            size=100,
            content_type="text/plain",
            last_modified="2024-01-01T00:00:00Z"
        )
    ]
    mock_storage_backend.return_value = mock_storage
    
    response = client_with_auth.delete("/api/files/file-id")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["success"] is True
    assert "Deleted 1 file(s)" in data["message"]
    
    # Verify delete was called
    mock_storage.delete.assert_called_once_with("user123/uploads/file-id/test.txt")


def test_delete_nonexistent_file(client_with_auth, mock_storage_backend):
    """Test deleting a non-existent file"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.list.return_value = []  # No files found
    mock_storage_backend.return_value = mock_storage
    
    response = client_with_auth.delete("/api/files/nonexistent")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "File not found" in response.json()["detail"]


def test_download_by_key(client_with_auth, mock_storage_backend):
    """Test downloading file by storage key"""
    # Setup mock storage
    mock_storage = AsyncMock()
    file_content = b"Content by key"
    mock_storage.download.return_value = file_content
    mock_storage_backend.return_value = mock_storage
    
    # Test downloading own file
    response = client_with_auth.get(
        "/api/files/download-by-key",
        params={"key": "user123/executions/exec-id/outputs/result.json"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == file_content
    assert response.headers["content-type"] == "application/json"
    
    # Test downloading public file
    mock_storage.download.return_value = b"Public content"
    response = client_with_auth.get(
        "/api/files/download-by-key",
        params={"key": "public/shared/file.txt"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"Public content"


def test_download_by_key_access_denied(client_with_auth, mock_storage_backend):
    """Test access denied when downloading another user's file"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage_backend.return_value = mock_storage
    
    # Try to download another user's file
    response = client_with_auth.get(
        "/api/files/download-by-key",
        params={"key": "other-user/executions/exec-id/outputs/result.json"}
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Access denied" in response.json()["detail"]


def test_upload_without_filename(client_with_auth, mock_storage_backend):
    """Test uploading file without filename"""
    # Create file upload without filename
    files = {"file": (None, b"No filename content", "text/plain")}
    
    response = client_with_auth.post(
        "/api/files/upload",
        files=files
    )
    
    # FastAPI returns 422 for validation errors
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_file_upload_storage_error(client_with_auth, mock_storage_backend):
    """Test handling storage errors during upload"""
    # Setup mock storage to raise error
    mock_storage = AsyncMock()
    mock_storage.upload.side_effect = Exception("Storage service unavailable")
    mock_storage_backend.return_value = mock_storage
    
    files = {"file": ("test.txt", b"Content", "text/plain")}
    
    response = client_with_auth.post(
        "/api/files/upload",
        files=files
    )
    
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Upload failed" in response.json()["detail"]


# Test fixtures
@pytest.fixture
def mock_user():
    """Create a mock user for testing"""
    return User(
        id="user123",
        username="testuser",
        email="test@example.com",
        password_hash="hashed",
        is_active=True,
        is_admin=False,
    )


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    session = AsyncMock()
    
    # Mock the execute method
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    
    # Mock transaction methods
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    
    return session


@pytest.fixture
def client_with_auth(mock_db_session, mock_user):
    """Create test client with authentication"""
    app.dependency_overrides[get_db] = lambda: mock_db_session
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# Fixture for mocking storage backend
@pytest.fixture
def mock_storage_backend():
    with patch('seriesoftubes.api.file_routes.get_storage_backend') as mock:
        yield mock