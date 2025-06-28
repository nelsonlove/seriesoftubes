"""Integration tests for LLM providers

WARNING: These tests make real API calls and will incur costs!
Only run with: OPENAI_API_KEY=xxx RUN_EXPENSIVE_TESTS=true pytest tests/test_integration/

To run a specific test:
  RUN_EXPENSIVE_TESTS=true pytest tests/test_integration/test_llm_providers.py::test_openai_real_api
"""

import os

import pytest

from seriesoftubes.providers.openai import OpenAIProvider


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or not os.getenv("RUN_EXPENSIVE_TESTS"),
    reason="Requires OPENAI_API_KEY and RUN_EXPENSIVE_TESTS=true",
)
async def test_openai_real_api():
    """Real OpenAI API integration test - costs money!"""
    api_key = os.getenv("OPENAI_API_KEY")
    provider = OpenAIProvider(api_key)

    # Use cheaper model for integration tests
    result = await provider.call(
        prompt="Say 'Hello, World!' and nothing else.",
        model="gpt-3.5-turbo",
        temperature=0,
    )

    assert isinstance(result, str)
    assert "Hello, World!" in result


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or not os.getenv("RUN_EXPENSIVE_TESTS"),
    reason="Requires OPENAI_API_KEY and RUN_EXPENSIVE_TESTS=true",
)
async def test_openai_structured_output_real():
    """Real OpenAI structured output test - costs money!"""
    api_key = os.getenv("OPENAI_API_KEY")
    provider = OpenAIProvider(api_key)

    schema = {
        "type": "object",
        "properties": {
            "greeting": {"type": "string"},
            "number": {"type": "integer"},
        },
    }

    # Use cheaper model when possible
    result = await provider.call(
        prompt="Return a greeting 'Hello' and the number 42",
        model="gpt-4o-mini",  # Cheaper than gpt-4o
        temperature=0,
        schema=schema,
    )

    assert isinstance(result, dict)
    assert result.get("greeting") == "Hello"
    assert result.get("number") == 42


# Add similar tests for Anthropic when implemented
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("RUN_EXPENSIVE_TESTS"),
    reason="Requires ANTHROPIC_API_KEY and RUN_EXPENSIVE_TESTS=true",
)
async def test_anthropic_real_api():
    """Real Anthropic API integration test - costs money!"""
    pytest.skip("Anthropic provider not yet implemented")