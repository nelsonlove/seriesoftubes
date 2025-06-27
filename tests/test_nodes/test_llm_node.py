"""Tests for LLM node executor"""

import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from seriesoftubes.models import (
    LLMNodeConfig,
    Node,
    NodeType,
)
from seriesoftubes.nodes import LLMNodeExecutor
from seriesoftubes.providers.openai import OpenAIProvider


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
async def test_llm_node_with_openai():
    """Test LLM node execution with OpenAI provider"""
    executor = LLMNodeExecutor()

    node = Node(
        name="extract_info",
        type=NodeType.LLM,
        depends_on=["previous_node"],
        config=LLMNodeConfig(
            context={"data": "previous_node"},
            prompt="Extract information from: {{ data }}",
            model="gpt-4o-mini",
            temperature=0.7,
        ),
    )

    context = MockContext(outputs={"previous_node": {"text": "Hello world"}})

    with patch("seriesoftubes.nodes.llm.get_config") as mock_config:
        mock_config.return_value.llm.provider = "openai"
        mock_config.return_value.llm.api_key = "test-key"
        mock_config.return_value.llm.model = "gpt-4o"
        mock_config.return_value.llm.temperature = 0.5

        with patch("seriesoftubes.nodes.llm.get_provider") as mock_get_provider:
            mock_provider = mock_get_provider.return_value
            mock_provider.call = AsyncMock(return_value={"extracted": "information"})

            result = await executor.execute(node, context)

            assert result.success
            assert result.output["response"] == '{"extracted": "information"}'
            assert result.output["structured_output"] == {"extracted": "information"}
            assert result.output["model_used"] == "gpt-4o-mini"

            # Check provider was called correctly
            mock_get_provider.assert_called_once_with("openai", "test-key")
            mock_provider.call.assert_called_once()
            call_args = mock_provider.call.call_args[0]
            assert "Hello world" in call_args[0]
            assert call_args[1] == "gpt-4o-mini"
            assert call_args[2] == 0.7
            assert call_args[3] is None


@pytest.mark.asyncio
async def test_llm_node_with_anthropic():
    """Test LLM node execution with Anthropic provider"""
    executor = LLMNodeExecutor()

    node = Node(
        name="summarize",
        type=NodeType.LLM,
        depends_on=[],
        config=LLMNodeConfig(
            prompt="Summarize this text",
            model="claude-3-sonnet",
        ),
    )

    context = MockContext()

    with patch("seriesoftubes.nodes.llm.get_config") as mock_config:
        mock_config.return_value.llm.provider = "anthropic"
        mock_config.return_value.llm.api_key = "test-key"
        mock_config.return_value.llm.model = "claude-3-opus"
        mock_config.return_value.llm.temperature = 0.5

        with patch("seriesoftubes.nodes.llm.get_provider") as mock_get_provider:
            mock_provider = mock_get_provider.return_value
            mock_provider.call = AsyncMock(return_value={"summary": "text summary"})

            result = await executor.execute(node, context)

            assert result.success
            assert result.output["response"] == '{"summary": "text summary"}'
            assert result.output["structured_output"] == {"summary": "text summary"}
            assert result.output["model_used"] == "claude-3-sonnet"

            mock_get_provider.assert_called_once_with("anthropic", "test-key")
            mock_provider.call.assert_called_once_with(
                "Summarize this text",
                "claude-3-sonnet",
                0.5,
                None,
            )


@pytest.mark.asyncio
async def test_llm_node_with_schema():
    """Test LLM node with structured output schema"""
    executor = LLMNodeExecutor()

    schema_def = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }

    node = Node(
        name="extract_person",
        type=NodeType.LLM,
        depends_on=[],
        config=LLMNodeConfig(
            prompt="Extract person information",
            schema=schema_def,
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
            mock_provider.call = AsyncMock(return_value={"name": "John", "age": 30})

            result = await executor.execute(node, context)

            assert result.success
            assert result.output["response"] == '{"name": "John", "age": 30}'
            assert result.output["structured_output"] == {"name": "John", "age": 30}
            assert result.output["model_used"] == "gpt-4o"

            # Check call was made with correct schema
            mock_get_provider.assert_called_once_with("openai", "test-key")
            mock_provider.call.assert_called_once_with(
                "Extract person information",
                "gpt-4o",
                0.5,
                schema_def,
            )


@pytest.mark.asyncio
async def test_llm_node_with_prompt_file(tmp_path):
    """Test LLM node loading prompt from file"""
    executor = LLMNodeExecutor()

    # Create prompt file
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Analyze this: {{ input_data }}")

    node = Node(
        name="analyze",
        type=NodeType.LLM,
        depends_on=[],
        config=LLMNodeConfig(
            context={"input_data": "some_node"},
            prompt_template=str(prompt_file),
        ),
    )

    context = MockContext(outputs={"some_node": "test data"})

    with patch("seriesoftubes.nodes.llm.get_config") as mock_config:
        mock_config.return_value.llm.provider = "openai"
        mock_config.return_value.llm.api_key = "test-key"
        mock_config.return_value.llm.model = "gpt-4o"
        mock_config.return_value.llm.temperature = 0.5

        with patch("seriesoftubes.nodes.llm.get_provider") as mock_get_provider:
            mock_provider = mock_get_provider.return_value
            mock_provider.call = AsyncMock(return_value={"analysis": "results"})

            result = await executor.execute(node, context)

            assert result.success
            assert result.output["response"] == '{"analysis": "results"}'
            assert result.output["structured_output"] == {"analysis": "results"}
            assert result.output["model_used"] == "gpt-4o"

            # Should use the template with context data
            mock_get_provider.assert_called_once_with("openai", "test-key")
            mock_provider.call.assert_called_once()
            assert "Analyze this: test data" in mock_provider.call.call_args[0][0]


@pytest.mark.asyncio
async def test_llm_node_error_handling():
    """Test LLM node error handling"""
    executor = LLMNodeExecutor()

    node = Node(
        name="failing_llm",
        type=NodeType.LLM,
        depends_on=[],
        config=LLMNodeConfig(prompt="Test prompt"),
    )

    context = MockContext()

    with patch("seriesoftubes.nodes.llm.get_config") as mock_config:
        mock_config.return_value.llm.provider = "openai"
        mock_config.return_value.llm.api_key = "test-key"
        mock_config.return_value.llm.model = "gpt-4o"
        mock_config.return_value.llm.temperature = 0.5

        with patch("seriesoftubes.nodes.llm.get_provider") as mock_get_provider:
            mock_provider = mock_get_provider.return_value
            mock_provider.call = AsyncMock(side_effect=Exception("API Error"))

            result = await executor.execute(node, context)

            assert not result.success
            assert "API Error" in result.error


@pytest.mark.asyncio
async def test_llm_node_invalid_config():
    """Test LLM node with invalid config type"""
    from pydantic import ValidationError  # noqa: PLC0415

    # Node creation should fail with invalid config
    with pytest.raises(ValidationError) as exc_info:
        Node(
            name="bad_config",
            type=NodeType.LLM,
            depends_on=[],
            config="not a valid config",  # Invalid config type
        )

    assert "Config must be a dictionary" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
async def test_openai_structured_outputs_integration():
    """Integration test for OpenAI structured outputs (requires real API key)"""
    api_key = os.getenv("OPENAI_API_KEY")
    provider = OpenAIProvider(api_key)
    
    # Test simple schema
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "skills": {
                "type": "array",
                "items": {"type": "string"}
            }
        }
    }
    
    result = await provider.call(
        prompt="Generate a profile for a software engineer named Alice",
        model="gpt-4o",
        temperature=0.7,
        schema=schema
    )
    
    # Verify structured output format
    assert isinstance(result, dict)
    assert "name" in result
    assert "age" in result
    assert "skills" in result
    assert isinstance(result["name"], str)
    assert isinstance(result["age"], int)
    assert isinstance(result["skills"], list)
    assert all(isinstance(skill, str) for skill in result["skills"])


@pytest.mark.asyncio
async def test_openai_structured_outputs_complex_schema():
    """Test complex nested schema conversion"""
    provider = OpenAIProvider("test-key")
    
    # Complex schema with nested objects and arrays
    complex_schema = {
        "type": "object",
        "properties": {
            "user": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"}
                }
            },
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "technologies": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            },
            "years_experience": {"type": "integer"}
        }
    }
    
    # Test that schema conversion works without errors
    pydantic_model = provider._json_schema_to_pydantic(complex_schema)
    assert pydantic_model is not None
    
    # Test that we can create an instance
    test_data = {
        "user": {"name": "John", "email": "john@example.com"},
        "projects": [
            {
                "title": "Project 1",
                "description": "A test project",
                "technologies": ["Python", "FastAPI"]
            }
        ],
        "years_experience": 5
    }
    
    instance = pydantic_model(**test_data)
    assert instance.model_dump() == test_data


@pytest.mark.asyncio
async def test_openai_fallback_to_json_mode():
    """Test fallback to JSON mode for older models"""
    provider = OpenAIProvider("test-key")
    
    # Mock the client
    mock_client = AsyncMock()
    provider.client = mock_client
    
    # Test with older model (not in STRUCTURED_OUTPUT_MODELS)
    schema = {"type": "object", "properties": {"result": {"type": "string"}}}
    
    # Mock response
    mock_completion = AsyncMock()
    mock_completion.choices = [AsyncMock()]
    mock_completion.choices[0].message.content = '{"result": "test"}'
    mock_client.chat.completions.create.return_value = mock_completion
    
    result = await provider.call(
        prompt="Test prompt",
        model="gpt-3.5-turbo",  # Older model
        temperature=0.7,
        schema=schema
    )
    
    # Should fall back to regular completions API
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert "JSON" in call_kwargs["messages"][0]["content"]
    
    assert result == {"result": "test"}
