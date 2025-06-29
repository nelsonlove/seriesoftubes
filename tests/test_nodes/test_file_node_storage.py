"""Tests for file node with storage backend support"""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from seriesoftubes.models import FileNodeConfig, Node, NodeType, Workflow
from seriesoftubes.engine import ExecutionContext
from seriesoftubes.nodes.file import FileNodeExecutor
from seriesoftubes.storage.base import StorageFile


@pytest.fixture
def mock_workflow():
    """Create a mock workflow for testing"""
    workflow = MagicMock(spec=Workflow)
    workflow.name = "test-workflow"
    workflow.version = "1.0.0"
    workflow.inputs = {}
    workflow.nodes = {}
    workflow.outputs = {}
    return workflow


@pytest.mark.asyncio
async def test_file_node_read_from_object_storage(mock_workflow):
    """Test reading files from object storage"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.list.return_value = [
        StorageFile(
            key="data/input.json",
            size=100,
            content_type="application/json",
            last_modified="2024-01-01T00:00:00Z"
        )
    ]
    mock_storage.download.return_value = b'{"name": "test", "value": 42}'
    
    with patch('seriesoftubes.nodes.file.get_storage_backend', return_value=mock_storage):
        # Create file node
        config = FileNodeConfig(
            path="data/input.json",
            storage_type="object",
            format_type="json"
        )
        node = Node(name="file_reader", node_type=NodeType.FILE, config=config)
        
        # Execute node
        executor = FileNodeExecutor()
        context = ExecutionContext(workflow=mock_workflow, inputs={})
        result = await executor.execute(node, context)
        
        assert result.success is True
        assert result.output["data"]["name"] == "test"
        assert result.output["data"]["value"] == 42
        assert result.output["metadata"]["storage_type"] == "object"
        
        # Verify storage calls
        assert mock_storage.initialize.call_count >= 1
        mock_storage.download.assert_called_once_with("data/input.json")


@pytest.mark.asyncio
async def test_file_node_read_with_storage_prefix(mock_workflow):
    """Test reading files with storage prefix"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.list.return_value = [
        StorageFile(
            key="user-data/inputs/file.csv",
            size=50,
            content_type="text/csv",
            last_modified="2024-01-01T00:00:00Z"
        )
    ]
    mock_storage.download.return_value = b"col1,col2\nval1,val2\nval3,val4"
    
    with patch('seriesoftubes.nodes.file.get_storage_backend', return_value=mock_storage):
        # Create file node with storage prefix
        config = FileNodeConfig(
            path="inputs/file.csv",
            storage_type="object",
            storage_prefix="user-data",
            format_type="csv"
        )
        node = Node(name="csv_reader", node_type=NodeType.FILE, config=config)
        
        # Execute node
        executor = FileNodeExecutor()
        context = ExecutionContext(workflow=mock_workflow, inputs={})
        result = await executor.execute(node, context)
        
        assert result.success is True
        assert len(result.output["data"]) == 2
        assert result.output["data"][0]["col1"] == "val1"
        assert result.output["data"][0]["col2"] == "val2"


@pytest.mark.asyncio
async def test_file_node_write_to_object_storage(mock_workflow):
    """Test writing files to object storage"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.upload.return_value = StorageFile(
        key="outputs/result.json",
        size=100,
        content_type="application/json",
        last_modified="2024-01-01T00:00:00Z"
    )
    mock_storage.get_url.return_value = "https://storage.example.com/signed-url"
    
    with patch('seriesoftubes.nodes.file.get_storage_backend', return_value=mock_storage):
        # Create file node in write mode
        config = FileNodeConfig(
            mode="write",
            write_key="outputs/result_{{execution_id}}.json",
            storage_type="object",
            format="json"  # Use the alias instead of format_type
        )
        node = Node(name="file_writer", node_type=NodeType.FILE, config=config)
        
        # Execute node with input data
        executor = FileNodeExecutor()
        context = ExecutionContext(
            workflow=mock_workflow,
            inputs={"data": {"result": "success", "count": 10}}
        )
        context.execution_id = "exec-123"
        result = await executor.execute(node, context)
        
        assert result.success is True
        assert result.output["storage_type"] == "object"
        assert result.output["key"] == "outputs/result_exec-123.json"
        assert result.output["url"] == "https://storage.example.com/signed-url"
        
        # Verify storage upload was called
        mock_storage.upload.assert_called_once()
        call_args = mock_storage.upload.call_args
        # Check both positional and keyword args
        args, kwargs = call_args
        assert kwargs["key"] == "outputs/result_exec-123.json"
        assert kwargs["content_type"] == "application/json"
        
        # Verify JSON content
        uploaded_content = json.loads(kwargs["content"].decode())
        assert uploaded_content["result"] == "success"
        assert uploaded_content["count"] == 10


@pytest.mark.asyncio
async def test_file_node_write_csv_format(mock_workflow):
    """Test writing CSV files to storage"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.upload.return_value = StorageFile(
        key="exports/data.csv",
        size=50,
        content_type="text/csv",
        last_modified="2024-01-01T00:00:00Z"
    )
    mock_storage.get_url.return_value = "https://storage.example.com/csv-url"
    
    with patch('seriesoftubes.nodes.file.get_storage_backend', return_value=mock_storage):
        # Create file node for CSV output
        config = FileNodeConfig(
            mode="write",
            write_key="exports/data.csv",
            storage_type="object",
            format="csv"  # Use the alias
        )
        node = Node(name="csv_writer", node_type=NodeType.FILE, config=config)
        
        # Execute with tabular data
        executor = FileNodeExecutor()
        context = ExecutionContext(
            workflow=mock_workflow,
            inputs={"data": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]}
        )
        result = await executor.execute(node, context)
        
        assert result.success is True
        
        # Verify CSV content
        uploaded_content = mock_storage.upload.call_args[1]["content"].decode()
        assert "name,age" in uploaded_content
        assert "Alice,30" in uploaded_content
        assert "Bob,25" in uploaded_content


@pytest.mark.asyncio
async def test_file_node_pattern_matching_object_storage(mock_workflow):
    """Test pattern matching in object storage"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.list.return_value = [
        StorageFile(
            key="logs/2024-01-01.log",
            size=1000,
            content_type="text/plain",
            last_modified="2024-01-01T00:00:00Z"
        ),
        StorageFile(
            key="logs/2024-01-02.log",
            size=1200,
            content_type="text/plain",
            last_modified="2024-01-02T00:00:00Z"
        ),
        StorageFile(
            key="logs/summary.txt",
            size=500,
            content_type="text/plain",
            last_modified="2024-01-03T00:00:00Z"
        )
    ]
    mock_storage.download.side_effect = [
        b"Log entry 1",
        b"Log entry 2"
    ]
    
    with patch('seriesoftubes.nodes.file.get_storage_backend', return_value=mock_storage):
        # Create file node with pattern
        config = FileNodeConfig(
            pattern="logs/*.log",
            storage_type="object",
            format_type="txt",
            merge=True
        )
        node = Node(name="log_reader", node_type=NodeType.FILE, config=config)
        
        # Execute node
        executor = FileNodeExecutor()
        context = ExecutionContext(workflow=mock_workflow, inputs={})
        result = await executor.execute(node, context)
        
        assert result.success is True
        assert len(result.output["data"]) == 2
        assert "Log entry 1" in result.output["data"]
        assert "Log entry 2" in result.output["data"]
        
        # Verify only .log files were downloaded
        assert mock_storage.download.call_count == 2


@pytest.mark.asyncio
async def test_file_node_write_with_template(mock_workflow):
    """Test writing files with templated paths"""
    # Setup mock storage
    mock_storage = AsyncMock()
    mock_storage.upload.return_value = StorageFile(
        key="results/workflow-123/node-abc/output.json",
        size=100,
        content_type="application/json",
        last_modified="2024-01-01T00:00:00Z"
    )
    mock_storage.get_url.return_value = "https://storage.example.com/url"
    
    with patch('seriesoftubes.nodes.file.get_storage_backend', return_value=mock_storage):
        # Create file node with templated write key
        config = FileNodeConfig(
            mode="write",
            write_key="results/{{workflow_id}}/{{node_name}}/output.json",
            storage_type="object",
            storage_prefix="executions",
            format="json"  # Use the alias
        )
        node = Node(name="templated_writer", node_type=NodeType.FILE, config=config)
        
        # Execute with context variables
        executor = FileNodeExecutor()
        # Update the mock workflow name
        mock_workflow.name = "workflow-123"
        context = ExecutionContext(
            workflow=mock_workflow,
            inputs={"result": "processed"}
        )
        result = await executor.execute(node, context)
        
        assert result.success is True
        # The node name comes from the actual node, not context
        assert result.output["key"] == "executions/results/workflow-123/templated_writer/output.json"
        
        # Verify the full key was used
        mock_storage.upload.assert_called_once()
        call_args = mock_storage.upload.call_args[1]
        assert call_args["key"] == "executions/results/workflow-123/templated_writer/output.json"


@pytest.mark.asyncio
async def test_file_node_local_fallback(mock_workflow):
    """Test file node works with local storage when object storage not configured"""
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = os.path.join(tmpdir, "test.json")
        with open(test_file, 'w') as f:
            json.dump({"local": "data"}, f)
        
        # Create file node with local storage
        config = FileNodeConfig(
            path=test_file,
            storage_type="local",
            format_type="json"
        )
        node = Node(name="local_reader", node_type=NodeType.FILE, config=config)
        
        # Execute node
        executor = FileNodeExecutor()
        context = ExecutionContext(workflow=mock_workflow, inputs={})
        result = await executor.execute(node, context)
        
        assert result.success is True
        assert result.output["data"]["local"] == "data"
        assert result.output["metadata"]["storage_type"] == "local"


@pytest.mark.asyncio
async def test_file_node_error_handling(mock_workflow):
    """Test error handling in file node with storage"""
    # Setup mock storage to raise error
    mock_storage = AsyncMock()
    mock_storage.list.side_effect = Exception("Storage service unavailable")
    
    with patch('seriesoftubes.nodes.file.get_storage_backend', return_value=mock_storage):
        # Create file node
        config = FileNodeConfig(
            path="data/missing.json",
            storage_type="object",
            format_type="json",
            skip_errors=False
        )
        node = Node(name="error_reader", node_type=NodeType.FILE, config=config)
        
        # Execute node
        executor = FileNodeExecutor()
        context = ExecutionContext(workflow=mock_workflow, inputs={})
        result = await executor.execute(node, context)
        
        assert result.success is False
        assert "Storage service unavailable" in result.error