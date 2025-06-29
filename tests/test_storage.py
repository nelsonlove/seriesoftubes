"""Tests for storage backends"""

import io
import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from seriesoftubes.storage import StorageError, get_storage_backend
from seriesoftubes.storage.base import StorageFile
from seriesoftubes.storage.local import LocalStorageBackend
from seriesoftubes.storage.s3 import S3StorageBackend


@pytest.mark.asyncio
async def test_local_storage_upload_download(tmp_path):
    """Test local storage upload and download"""
    storage = LocalStorageBackend(base_path=str(tmp_path))
    await storage.initialize()
    
    # Test upload
    content = b"Hello, World!"
    key = "test/file.txt"
    
    stored_file = await storage.upload(
        key=key,
        content=content,
        content_type="text/plain",
        metadata={"test": "value"}
    )
    
    assert stored_file.key == key
    assert stored_file.size == len(content)
    assert stored_file.content_type == "text/plain"
    
    # Test download
    downloaded = await storage.download(key)
    assert downloaded == content
    
    # Test file exists on disk
    file_path = tmp_path / key
    assert file_path.exists()
    assert file_path.read_bytes() == content


@pytest.mark.asyncio
async def test_local_storage_list(tmp_path):
    """Test local storage listing"""
    storage = LocalStorageBackend(base_path=str(tmp_path))
    await storage.initialize()
    
    # Upload multiple files
    files = [
        ("folder1/file1.txt", b"Content 1"),
        ("folder1/file2.txt", b"Content 2"),
        ("folder2/file3.txt", b"Content 3"),
    ]
    
    for key, content in files:
        await storage.upload(key=key, content=content)
    
    # List all files
    all_files = await storage.list()
    assert len(all_files) == 3
    
    # List with prefix
    folder1_files = await storage.list(prefix="folder1/")
    assert len(folder1_files) == 2
    assert all(f.key.startswith("folder1/") for f in folder1_files)
    
    # List with limit
    limited_files = await storage.list(max_keys=2)
    assert len(limited_files) == 2


@pytest.mark.asyncio
async def test_local_storage_delete(tmp_path):
    """Test local storage deletion"""
    storage = LocalStorageBackend(base_path=str(tmp_path))
    await storage.initialize()
    
    # Upload a file
    key = "test/file.txt"
    await storage.upload(key=key, content=b"Test content")
    
    # Verify it exists
    file_path = tmp_path / key
    assert file_path.exists()
    
    # Delete it
    await storage.delete(key)
    
    # Verify it's gone
    assert not file_path.exists()
    
    # Deleting non-existent file should not raise error
    await storage.delete("non/existent/file.txt")


@pytest.mark.asyncio
async def test_local_storage_exists(tmp_path):
    """Test local storage exists check"""
    storage = LocalStorageBackend(base_path=str(tmp_path))
    await storage.initialize()
    
    # Upload a file
    key = "test/file.txt"
    await storage.upload(key=key, content=b"Test content")
    
    # Check existence
    assert await storage.exists(key) is True
    assert await storage.exists("non/existent/file.txt") is False


@pytest.mark.asyncio
async def test_local_storage_get_url(tmp_path):
    """Test local storage URL generation"""
    storage = LocalStorageBackend(base_path=str(tmp_path))
    await storage.initialize()
    
    # Upload a file
    key = "test/file.txt"
    await storage.upload(key=key, content=b"Test content")
    
    # Get URL (for local storage, this is just the file path)
    url = await storage.get_url(key)
    assert key in url
    assert str(tmp_path) in url


@pytest.mark.asyncio
async def test_s3_storage_upload_download():
    """Test S3 storage upload and download with mocks"""
    with patch('aioboto3.Session') as mock_session_class:
        # Setup mocks
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client
        mock_session.client.return_value.__aexit__.return_value = None
        
        # Configure S3 client responses
        mock_client.put_object.return_value = {
            'ETag': '"123456"',
            'VersionId': 'v1'
        }
        mock_client.head_object.return_value = {
            'ContentLength': 10,
            'ContentType': 'text/plain',
            'LastModified': '2024-01-01T00:00:00Z',
            'Metadata': {}
        }
        mock_client.get_object.return_value = {
            'Body': AsyncMock(read=AsyncMock(return_value=b"Hello, S3!")),
            'ContentLength': 10,
            'ContentType': 'text/plain'
        }
        
        # Create storage
        storage = S3StorageBackend(
            bucket_name="test-bucket",
            endpoint_url="http://localhost:9000",
            access_key_id="test",
            secret_access_key="test"
        )
        await storage.initialize()
        
        # Test upload
        key = "test/s3file.txt"
        content = b"Hello, S3!"
        
        stored_file = await storage.upload(
            key=key,
            content=content,
            content_type="text/plain"
        )
        
        assert stored_file.key == key
        assert stored_file.size == len(content)
        
        # Verify S3 client was called correctly
        mock_client.put_object.assert_called_once()
        call_args = mock_client.put_object.call_args[1]
        assert call_args['Bucket'] == "test-bucket"
        assert call_args['Key'] == key
        # Body is converted to BytesIO, so check the content
        body = call_args['Body']
        if hasattr(body, 'read'):
            body.seek(0)
            assert body.read() == content
        else:
            assert body == content
        
        # Test download
        downloaded = await storage.download(key)
        assert downloaded == b"Hello, S3!"
        
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=key
        )


@pytest.mark.asyncio
async def test_s3_storage_list():
    """Test S3 storage listing with mocks"""
    with patch('aioboto3.Session') as mock_session_class:
        # Setup mocks
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client
        mock_session.client.return_value.__aexit__.return_value = None
        
        # Configure S3 list response with paginator
        mock_paginator = MagicMock()  # Use MagicMock for get_paginator since it's not async
        mock_client.get_paginator = MagicMock(return_value=mock_paginator)
        
        # Mock async iterator for paginator
        async def mock_paginate(**kwargs):
            yield {
                'Contents': [
                    {
                        'Key': 'folder1/file1.txt',
                        'Size': 100,
                        'LastModified': datetime(2024, 1, 1, 0, 0, 0)
                    },
                    {
                        'Key': 'folder1/file2.txt',
                        'Size': 200,
                        'LastModified': datetime(2024, 1, 2, 0, 0, 0)
                    }
                ]
            }
        
        mock_paginator.paginate = mock_paginate
        
        # Create storage
        storage = S3StorageBackend(
            bucket_name="test-bucket",
            endpoint_url="http://localhost:9000",
            access_key_id="test",
            secret_access_key="test"
        )
        await storage.initialize()
        
        # Test list
        files = await storage.list(prefix="folder1/")
        assert len(files) == 2
        assert files[0].key == 'folder1/file1.txt'
        assert files[0].size == 100
        assert files[1].key == 'folder1/file2.txt'
        assert files[1].size == 200


@pytest.mark.asyncio
async def test_s3_storage_presigned_url():
    """Test S3 storage presigned URL generation"""
    with patch('aioboto3.Session') as mock_session_class:
        # Setup mocks
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client
        mock_session.client.return_value.__aexit__.return_value = None
        
        # Configure presigned URL response
        expected_url = "https://test-bucket.s3.amazonaws.com/test/file.txt?signature=xxx"
        mock_client.generate_presigned_url.return_value = expected_url
        
        # Create storage
        storage = S3StorageBackend(
            bucket_name="test-bucket",
            endpoint_url="http://localhost:9000",
            access_key_id="test",
            secret_access_key="test"
        )
        await storage.initialize()
        
        # Test URL generation
        url = await storage.get_url("test/file.txt", expires_in=3600)
        assert url == expected_url
        
        mock_client.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': 'test-bucket', 'Key': 'test/file.txt'},
            ExpiresIn=3600
        )


@pytest.mark.asyncio
async def test_storage_factory():
    """Test storage backend factory"""
    # Test local backend selection
    with patch.dict(os.environ, {}, clear=True):
        backend = get_storage_backend()
        assert isinstance(backend, LocalStorageBackend)
    
    # Test S3 backend selection with MinIO
    with patch.dict(os.environ, {'MINIO_ENDPOINT': 'localhost:9000'}):
        backend = get_storage_backend()
        assert isinstance(backend, S3StorageBackend)
    
    # Test S3 backend selection with AWS
    with patch.dict(os.environ, {'AWS_ENDPOINT_URL': 'https://s3.amazonaws.com'}):
        backend = get_storage_backend()
        assert isinstance(backend, S3StorageBackend)
    
    # Test explicit backend selection
    backend = get_storage_backend(backend_type="local")
    assert isinstance(backend, LocalStorageBackend)
    
    backend = get_storage_backend(backend_type="s3", bucket_name="test")
    assert isinstance(backend, S3StorageBackend)
    
    # Test invalid backend
    with pytest.raises(ValueError, match="Invalid storage backend type"):
        get_storage_backend(backend_type="invalid")


@pytest.mark.asyncio
async def test_storage_upload_with_file_object(tmp_path):
    """Test uploading from file-like objects"""
    storage = LocalStorageBackend(base_path=str(tmp_path))
    await storage.initialize()
    
    # Test with BytesIO
    content = b"File object content"
    file_obj = io.BytesIO(content)
    
    stored_file = await storage.upload(
        key="test/fileobj.txt",
        content=file_obj,
        content_type="text/plain"
    )
    
    assert stored_file.size == len(content)
    
    # Verify content
    downloaded = await storage.download("test/fileobj.txt")
    assert downloaded == content


@pytest.mark.asyncio
async def test_storage_error_handling():
    """Test storage error handling"""
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageBackend(base_path=tmpdir)
        await storage.initialize()
        
        # Upload to invalid path should raise StorageError
        with pytest.raises(StorageError):
            await storage.upload(
                key="../../../etc/passwd",  # Path traversal attempt
                content=b"malicious"
            )
        
        # Download non-existent file should raise StorageError
        with pytest.raises(StorageError):
            await storage.download("non/existent/file.txt")