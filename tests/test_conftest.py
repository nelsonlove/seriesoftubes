"""
Extended test configuration for handling external services
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# --- Redis/Cache Configuration ---

@pytest.fixture
def mock_redis():
    """Mock Redis for tests that don't need actual Redis"""
    with patch('seriesoftubes.cache.redis.RedisCacheBackend') as mock:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=None)
        instance.set = AsyncMock(return_value=True)
        instance.exists = AsyncMock(return_value=False)
        instance.delete = AsyncMock(return_value=True)
        instance.clear = AsyncMock(return_value=True)
        instance.close = AsyncMock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def use_memory_cache():
    """Force memory cache instead of Redis"""
    with patch.dict(os.environ, {'REDIS_URL': '', 'CACHE_BACKEND': 'memory'}):
        yield


# --- MinIO/S3 Configuration ---

@pytest.fixture
def mock_s3_client():
    """Mock S3 client for tests"""
    client = AsyncMock()
    
    # Mock common S3 operations
    client.upload = AsyncMock()
    client.download = AsyncMock(return_value=b"test content")
    client.delete = AsyncMock()
    client.list_objects_v2 = AsyncMock(return_value={
        'Contents': [],
        'IsTruncated': False
    })
    client.head_object = AsyncMock(return_value={
        'ContentLength': 100,
        'ContentType': 'text/plain'
    })
    client.generate_presigned_url = MagicMock(
        return_value="https://example.com/presigned"
    )
    
    return client


@pytest.fixture
def mock_s3_storage(mock_s3_client):
    """Mock S3 storage backend"""
    with patch('seriesoftubes.storage.s3.S3StorageBackend') as mock:
        instance = AsyncMock()
        instance._client = mock_s3_client
        instance.upload = AsyncMock()
        instance.download = AsyncMock(return_value=b"test content")
        instance.delete = AsyncMock()
        instance.list = AsyncMock(return_value=[])
        instance.exists = AsyncMock(return_value=False)
        instance.get_url = AsyncMock(return_value="https://example.com/file")
        mock.return_value = instance
        yield instance


@pytest.fixture
def use_local_storage(tmp_path):
    """Force local storage instead of S3/MinIO"""
    with patch.dict(os.environ, {
        'MINIO_ENDPOINT': '',
        'AWS_ENDPOINT_URL': '',
        'STORAGE_BACKEND': 'local',
        'STORAGE_PATH': str(tmp_path)
    }):
        yield tmp_path


# --- Celery Configuration ---

@pytest.fixture
def mock_celery_task():
    """Mock Celery task for tests"""
    with patch('seriesoftubes.tasks.execute_workflow') as mock_task:
        # Mock the delay method
        mock_task.delay = MagicMock(return_value=MagicMock(id='test-task-id'))
        # Mock the apply_async method
        mock_task.apply_async = MagicMock(return_value=MagicMock(id='test-task-id'))
        yield mock_task


@pytest.fixture
def disable_celery():
    """Disable Celery for tests (force in-process execution)"""
    with patch('seriesoftubes.api.workflow_routes.execute_workflow', side_effect=ImportError):
        yield


# --- Database Configuration ---

@pytest.fixture
async def test_db_session():
    """Create a test database session"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from seriesoftubes.db.models import Base
    
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with AsyncSession(engine) as session:
        yield session
    
    # Cleanup
    await engine.dispose()


# --- Integration Test Markers ---

# Mark tests that require real Redis
pytest.mark.requires_redis = pytest.mark.skipif(
    not os.getenv('TEST_WITH_REDIS'),
    reason="Set TEST_WITH_REDIS=1 to run Redis integration tests"
)

# Mark tests that require real MinIO/S3
pytest.mark.requires_minio = pytest.mark.skipif(
    not os.getenv('TEST_WITH_MINIO'),
    reason="Set TEST_WITH_MINIO=1 to run MinIO integration tests"
)

# Mark tests that require real Celery
pytest.mark.requires_celery = pytest.mark.skipif(
    not os.getenv('TEST_WITH_CELERY'),
    reason="Set TEST_WITH_CELERY=1 to run Celery integration tests"
)


# --- Test Environment Setup ---

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up clean test environment"""
    # Set test-specific environment variables
    test_env = {
        'TESTING': '1',
        'LOG_LEVEL': 'WARNING',  # Reduce log noise in tests
        'CACHE_ENABLED': '0',  # Disable caching by default in tests
    }
    
    with patch.dict(os.environ, test_env):
        yield


# --- Example Usage ---
"""
# Test that uses mocked services (default for unit tests):
def test_workflow_execution(mock_celery_task, mock_s3_storage, mock_redis):
    # Your test code here
    pass

# Test that uses local alternatives:
def test_workflow_with_local_services(disable_celery, use_local_storage, use_memory_cache):
    # Your test code here
    pass

# Integration test that requires real services:
@pytest.mark.requires_redis
@pytest.mark.requires_minio
@pytest.mark.requires_celery
def test_full_integration():
    # This test will only run if TEST_WITH_* env vars are set
    pass
"""