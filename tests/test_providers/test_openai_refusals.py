"""Test OpenAI provider refusal handling"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from seriesoftubes.providers.openai import OpenAIProvider


@pytest.mark.asyncio
async def test_structured_output_refusal():
    """Test handling of refusals in structured outputs"""
    provider = OpenAIProvider(api_key="test-key")
    
    # Mock the OpenAI client
    mock_client = AsyncMock()
    provider.client = mock_client
    
    # Mock a refusal response
    mock_message = MagicMock()
    mock_message.refusal = "I cannot assist with creating content that could be harmful."
    mock_message.parsed = None
    mock_message.content = None
    
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "stop"
    
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    
    mock_client.beta.chat.completions.parse.return_value = mock_completion
    
    # Test schema for structured output
    schema = {
        "type": "object",
        "properties": {
            "response": {"type": "string"}
        },
        "required": ["response"]
    }
    
    # Call should raise ValueError with refusal message
    with pytest.raises(ValueError) as exc_info:
        await provider.call(
            prompt="Generate harmful content",
            model="gpt-4o-2024-08-06",
            temperature=0.7,
            schema=schema
        )
    
    assert "OpenAI refused to respond" in str(exc_info.value)
    assert "cannot assist with creating content that could be harmful" in str(exc_info.value)


@pytest.mark.asyncio
async def test_regular_completion_refusal():
    """Test handling of refusals in regular completions"""
    provider = OpenAIProvider(api_key="test-key")
    
    # Mock the OpenAI client
    mock_client = AsyncMock()
    provider.client = mock_client
    
    # Mock a refusal response in content
    mock_message = MagicMock()
    mock_message.content = "I'm sorry, I cannot assist with that request."
    
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "stop"
    
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    
    mock_client.chat.completions.create.return_value = mock_completion
    
    # Call without schema (regular completion)
    result = await provider.call(
        prompt="Generate something",
        model="gpt-4-turbo",
        temperature=0.7
    )
    
    # Should return the refusal message (not raise an error for regular completions)
    assert result == "I'm sorry, I cannot assist with that request."


@pytest.mark.asyncio
async def test_no_refusal_structured_output():
    """Test normal operation without refusal"""
    provider = OpenAIProvider(api_key="test-key")
    
    # Mock the OpenAI client
    mock_client = AsyncMock()
    provider.client = mock_client
    
    # Mock a successful response
    mock_parsed = MagicMock()
    mock_parsed.model_dump.return_value = {"response": "This is a valid response"}
    
    mock_message = MagicMock()
    mock_message.refusal = None
    mock_message.parsed = mock_parsed
    mock_message.content = '{"response": "This is a valid response"}'
    
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    
    mock_client.beta.chat.completions.parse.return_value = mock_completion
    
    # Test schema for structured output
    schema = {
        "type": "object",
        "properties": {
            "response": {"type": "string"}
        },
        "required": ["response"]
    }
    
    result = await provider.call(
        prompt="Generate a normal response",
        model="gpt-4o-2024-08-06",
        temperature=0.7,
        schema=schema
    )
    
    assert result == {"response": "This is a valid response"}


@pytest.mark.asyncio
async def test_content_policy_error():
    """Test handling of content policy violations in error messages"""
    provider = OpenAIProvider(api_key="test-key")
    
    # Mock the OpenAI client to raise an exception
    mock_client = AsyncMock()
    provider.client = mock_client
    
    mock_client.beta.chat.completions.parse.side_effect = Exception(
        "This request violates our content_policy"
    )
    
    schema = {
        "type": "object",
        "properties": {
            "response": {"type": "string"}
        },
        "required": ["response"]
    }
    
    with pytest.raises(ValueError) as exc_info:
        await provider.call(
            prompt="Generate something",
            model="gpt-4o-2024-08-06",
            temperature=0.7,
            schema=schema
        )
    
    assert "content policy violation" in str(exc_info.value).lower()
    assert "content_policy" in str(exc_info.value)