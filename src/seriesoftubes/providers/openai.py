"""OpenAI LLM provider"""

import json
from typing import Any, ClassVar

import httpx

from seriesoftubes.providers.base import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI API provider"""

    SUPPORTED_MODELS: ClassVar[list[str]] = [
        "gpt-4",
        "gpt-4-turbo",
        "gpt-4o",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
    ]

    async def call(
        self,
        prompt: str,
        model: str,
        temperature: float,
        schema: dict[str, Any] | None = None,
    ) -> Any:
        """Call OpenAI API"""
        if not self.api_key:
            msg = "OpenAI API key not configured"
            raise ValueError(msg)

        async with httpx.AsyncClient() as client:
            messages = [{"role": "user", "content": prompt}]

            request_data = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }

            # Add JSON mode if schema is specified
            if schema:
                request_data["response_format"] = {"type": "json_object"}
                messages[0]["content"] += "\n\nRespond with valid JSON."

            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=request_data,
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

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
