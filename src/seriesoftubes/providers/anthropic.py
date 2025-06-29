"""Anthropic LLM provider"""

import json
import logging
from typing import Any, ClassVar

import httpx

from seriesoftubes.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic API provider"""

    SUPPORTED_MODELS: ClassVar[list[str]] = [
        "claude-3-haiku-20240307",
        "claude-3-sonnet-20240229",
        "claude-3-opus-20240229",
        "claude-3-5-sonnet-20241022",
    ]

    async def call(
        self,
        prompt: str,
        model: str,
        temperature: float,
        schema: dict[str, Any] | None = None,
    ) -> Any:
        """Call Anthropic API"""
        if not self.api_key:
            msg = "Anthropic API key not configured"
            raise ValueError(msg)

        # Log the exact prompt being sent
        logger.info(f"LLM Request - Model: {model}, Temperature: {temperature}")
        logger.info(f"LLM Request - Prompt: {prompt}")
        if schema:
            logger.info(f"LLM Request - Schema: {json.dumps(schema, indent=2)}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            request_data: dict[str, Any] = {
                "model": model,
                "max_tokens": 4096,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }

            # Add JSON instructions if schema is specified
            if schema:
                messages = request_data["messages"]
                messages[0]["content"] += "\n\nRespond with valid JSON."

            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=request_data,
            )
            response.raise_for_status()

            result = response.json()
            content = result["content"][0]["text"]

            # Parse JSON if schema was specified
            if schema:
                try:
                    parsed = json.loads(content)
                    logger.info(f"LLM Response - Parsed JSON: {json.dumps(parsed)}")
                    return parsed
                except json.JSONDecodeError:
                    # Return raw content if JSON parsing fails
                    logger.warning(f"LLM Response - Failed to parse JSON, returning raw content: {content[:200]}...")
                    return content

            logger.info(f"LLM Response - Content: {content[:500]}..." if len(content) > 500 else f"LLM Response - Content: {content}")
            return content

    def validate_model(self, model: str) -> bool:
        """Validate if the model name is supported"""
        return model in self.SUPPORTED_MODELS

    def get_supported_models(self) -> list[str]:
        """Get list of supported model names"""
        return self.SUPPORTED_MODELS.copy()
