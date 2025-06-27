"""Tests for schema validation in node executors"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from seriesoftubes.models import (
    HTTPNodeConfig,
    LLMNodeConfig,
    Node,
    NodeType,
    PythonNodeConfig,
)
from seriesoftubes.nodes import (
    HTTPNodeExecutor,
    LLMNodeExecutor,
    PythonNodeExecutor,
)


class MockContext:
    """Mock implementation of NodeContext protocol"""

    def __init__(
        self,
        outputs: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
    ):
        self.outputs = outputs or {}
        self.inputs = inputs or {}

    def get_output(self, node_name: str) -> Any:
        return self.outputs.get(node_name)

    def get_input(self, input_name: str) -> Any:
        return self.inputs.get(input_name)


@pytest.mark.asyncio
async def test_llm_node_input_validation_error():
    """Test LLM node with invalid input data type"""
    executor = LLMNodeExecutor()

    # Create a node with valid config
    node = Node(
        name="test_llm",
        type=NodeType.LLM,
        depends_on=[],
        config=LLMNodeConfig(
            prompt="Test prompt",
        ),
    )

    context = MockContext()

    with patch("seriesoftubes.nodes.llm.get_config") as mock_config:
        mock_config.return_value.llm.provider = "openai"
        mock_config.return_value.llm.api_key = "test-key"
        mock_config.return_value.llm.model = "gpt-4o"
        mock_config.return_value.llm.temperature = 0.5

        # Patch the validate_input method to simulate validation error
        with patch.object(executor, "validate_input") as mock_validate:
            # ruff: noqa: PLC0415
            from pydantic import ValidationError

            mock_validate.side_effect = ValidationError.from_exception_data(
                "LLMNodeInput",
                [
                    {
                        "type": "string_type",
                        "loc": ("prompt",),
                        "msg": "Input should be a valid string",
                        "input": 123,
                    }
                ],
            )

            result = await executor.execute(node, context)

            assert not result.success
            assert "Input validation failed" in result.error
            assert "prompt" in result.error  # Should mention the field
            assert "Input should be a valid string" in result.error


@pytest.mark.asyncio
async def test_http_node_output_validation():
    """Test HTTP node output validation works correctly"""
    executor = HTTPNodeExecutor()

    node = Node(
        name="test_http",
        type=NodeType.HTTP,
        depends_on=[],
        config=HTTPNodeConfig(
            url="https://api.example.com/test",
            method="GET",
        ),
    )

    context = MockContext()

    with patch("httpx.AsyncClient") as mock_client_class:
        # ruff: noqa: PLC0415
        from unittest.mock import MagicMock

        mock_client = mock_client_class.return_value.__aenter__.return_value
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.url = "https://api.example.com/test"
        mock_response.json.return_value = {"data": "test"}
        mock_response.text = '{"data": "test"}'
        mock_client.request.return_value = mock_response

        result = await executor.execute(node, context)

        assert result.success
        # Check that output was validated and structured correctly
        assert result.output["status_code"] == 200
        assert isinstance(result.output["headers"], dict)
        assert result.output["body"] == {"data": "test"}
        assert result.output["url"] == "https://api.example.com/test"


@pytest.mark.asyncio
async def test_python_node_simple_execution():
    """Test Python node with simple execution"""
    executor = PythonNodeExecutor()

    node = Node(
        name="simple_calc",
        type=NodeType.PYTHON,
        depends_on=[],
        config=PythonNodeConfig(code="return {'result': 42}"),
    )

    context = MockContext()

    with patch("seriesoftubes.nodes.python._execute_in_process") as mock_execute:
        mock_execute.return_value = {"result": 42}

        result = await executor.execute(node, context)

        assert result.success
        # Python node wraps result in a 'result' key
        assert result.output == {"result": {"result": 42}}


@pytest.mark.asyncio
async def test_python_node_context_validation():
    """Test Python node context validation"""
    executor = PythonNodeExecutor()

    node = Node(
        name="python_calc",
        type=NodeType.PYTHON,
        depends_on=["data_node"],
        config=PythonNodeConfig(
            code="result = len(context['items'])",
            context={"items": "data_node"},
        ),
    )

    # Context with valid data
    context = MockContext(outputs={"data_node": [1, 2, 3, 4, 5]})

    with patch("seriesoftubes.nodes.python._execute_in_process") as mock_execute:
        mock_execute.return_value = 5

        result = await executor.execute(node, context)

        assert result.success
        assert result.output["result"] == 5

        # Verify the context was passed correctly
        call_args = mock_execute.call_args[0]
        assert call_args[1]["items"] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_llm_node_structured_output_validation():
    """Test LLM node with structured output validation"""
    executor = LLMNodeExecutor()

    node = Node(
        name="extract_data",
        type=NodeType.LLM,
        depends_on=[],
        config=LLMNodeConfig(
            prompt="Extract data",
            schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        ),
    )

    context = MockContext()

    with patch("seriesoftubes.nodes.llm.get_config") as mock_config:
        mock_config.return_value.llm.provider = "openai"
        mock_config.return_value.llm.api_key = "test-key"
        mock_config.return_value.llm.model = "gpt-4o"
        mock_config.return_value.llm.temperature = 0.5

        with patch("seriesoftubes.nodes.llm.get_provider") as mock_get_provider:
            mock_provider = mock_get_provider.return_value
            mock_provider.call = AsyncMock(return_value={"name": "John Doe", "age": 30})

            result = await executor.execute(node, context)

            assert result.success
            # Output should be validated and structured
            assert result.output["structured_output"] == {"name": "John Doe", "age": 30}
            assert result.output["response"] == '{"name": "John Doe", "age": 30}'
            assert result.output["model_used"] == "gpt-4o"


@pytest.mark.asyncio
async def test_http_node_invalid_url_validation():
    """Test HTTP node with invalid URL format"""
    executor = HTTPNodeExecutor()

    node = Node(
        name="bad_url",
        type=NodeType.HTTP,
        depends_on=[],
        config=HTTPNodeConfig(
            url="not-a-valid-url",  # Invalid URL
            method="GET",
        ),
    )

    context = MockContext()

    result = await executor.execute(node, context)

    assert not result.success
    assert "Input validation failed" in result.error
    assert "URL must start with http:// or https://" in result.error


@pytest.mark.asyncio
async def test_url_validation_error():
    """Test that URL validation works properly"""
    executor = HTTPNodeExecutor()

    # Create a node with template that will render to empty string
    node = Node(
        name="test_validation",
        type=NodeType.HTTP,
        depends_on=[],
        config=HTTPNodeConfig(
            url="{{ undefined_var }}",  # This will render to empty string
            method="GET",
        ),
    )

    context = MockContext()

    # This should fail URL validation
    result = await executor.execute(node, context)

    assert not result.success
    assert "Input validation failed" in result.error
    assert "url" in result.error.lower()
    assert "URL cannot be empty" in result.error


@pytest.mark.asyncio
async def test_invalid_url_format():
    """Test that URLs must start with http:// or https://"""
    executor = HTTPNodeExecutor()

    node = Node(
        name="bad_url",
        type=NodeType.HTTP,
        depends_on=[],
        config=HTTPNodeConfig(
            url="ftp://example.com",  # Invalid protocol
            method="GET",
        ),
    )

    context = MockContext()

    result = await executor.execute(node, context)

    assert not result.success
    assert "Input validation failed" in result.error
    assert "URL must start with http:// or https://" in result.error


@pytest.mark.asyncio
async def test_file_node_validation_with_path():
    """Test file node validation with path parameter"""
    from seriesoftubes.models import FileNodeConfig
    from seriesoftubes.nodes.file import FileNodeExecutor

    executor = FileNodeExecutor()

    # Test with valid path
    node = Node(
        name="read_file",
        type=NodeType.FILE,
        depends_on=[],
        config=FileNodeConfig(
            path="/tmp/test.json",  # noqa: S108
            format_type="json",
        ),
    )

    context = MockContext()

    # Mock the file reading
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = True
        with patch("builtins.open", create=True) as mock_open:
            import io

            mock_open.return_value.__enter__.return_value = io.StringIO(
                '{"data": "test"}'
            )

            result = await executor.execute(node, context)

            assert result.success
            assert result.output["data"] == {"data": "test"}
            assert result.output["metadata"]["files_read"] == 1


@pytest.mark.asyncio
async def test_file_node_validation_with_empty_path():
    """Test file node validation with empty path"""
    from seriesoftubes.models import FileNodeConfig
    from seriesoftubes.nodes.file import FileNodeExecutor

    executor = FileNodeExecutor()

    # Test with template that renders to empty string
    node = Node(
        name="read_file",
        type=NodeType.FILE,
        depends_on=[],
        config=FileNodeConfig(
            path="{{ undefined_var }}",  # Will render to empty string
            format_type="json",
        ),
    )

    context = MockContext()

    result = await executor.execute(node, context)

    assert not result.success
    # Now with proper validation, we get a clear error about empty path
    assert "Input validation failed" in result.error
    assert "Path cannot be empty" in result.error


@pytest.mark.asyncio
async def test_file_node_validation_with_pattern():
    """Test file node validation with pattern parameter"""
    from seriesoftubes.models import FileNodeConfig
    from seriesoftubes.nodes.file import FileNodeExecutor

    executor = FileNodeExecutor()

    # Test with valid pattern
    node = Node(
        name="read_files",
        type=NodeType.FILE,
        depends_on=[],
        config=FileNodeConfig(
            pattern="*.json",
            format_type="json",
            merge=True,
        ),
    )

    context = MockContext()

    # Mock glob
    with patch("glob.glob") as mock_glob:
        mock_glob.return_value = ["test1.json", "test2.json"]
        with patch("pathlib.Path.is_file") as mock_is_file:
            mock_is_file.return_value = True
            with patch("builtins.open", create=True) as mock_open:
                import io

                mock_open.side_effect = [
                    io.StringIO('{"id": 1}'),
                    io.StringIO('{"id": 2}'),
                ]

                result = await executor.execute(node, context)

                assert result.success
                assert result.output["data"] == [{"id": 1}, {"id": 2}]
                assert result.output["metadata"]["files_read"] == 2


@pytest.mark.asyncio
async def test_file_node_output_validation():
    """Test file node output validation structure"""
    from seriesoftubes.models import FileNodeConfig
    from seriesoftubes.nodes.file import FileNodeExecutor

    executor = FileNodeExecutor()

    node = Node(
        name="read_json",
        type=NodeType.FILE,
        depends_on=[],
        config=FileNodeConfig(
            path="data.json",
            format_type="json",
        ),
    )

    context = MockContext()

    # Mock file reading
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = True
        with patch("builtins.open", create=True) as mock_open:
            import io

            mock_open.return_value.__enter__.return_value = io.StringIO(
                '{"name": "test", "value": 42}'
            )

            result = await executor.execute(node, context)

            assert result.success
            # Check output structure matches schema
            assert "data" in result.output
            assert "metadata" in result.output
            assert result.output["metadata"]["files_read"] == 1
            assert (
                result.output["metadata"]["format"] == "json"
                or result.output["metadata"]["format"] == "auto"
            )
            assert result.output["metadata"]["output_mode"] == "content"
