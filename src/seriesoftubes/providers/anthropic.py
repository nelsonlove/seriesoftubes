"""Anthropic LLM provider"""

import json
from typing import Any, ClassVar

import httpx

from seriesoftubes.providers.base import LLMProvider


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

        async with httpx.AsyncClient() as client:
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
                    return json.loads(content)
                except json.JSONDecodeError:
                    # Return raw content if JSON parsing fails
                    return content

            return content

    def validate_model(self, model: str) -> bool:
        """Validate if the model name is supported"""
        return model in self.SUPPORTED_MODELS

    def get_supported_models(self) -> list[str]:
        """Get list of supported model names"""
        return self.SUPPORTED_MODELS.copy()
