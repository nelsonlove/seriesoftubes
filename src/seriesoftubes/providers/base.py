"""Base LLM provider interface"""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    @abstractmethod
    async def call(
        self,
        prompt: str,
        model: str,
        temperature: float,
        schema: dict[str, Any] | None = None,
    ) -> Any:
        """Make an LLM API call

        Args:
            prompt: The prompt to send
            model: Model name to use
            temperature: Temperature setting
            schema: Optional schema for structured output

        Returns:
            The response content (string or dict if schema provided)
        """
        pass

    @abstractmethod
    def validate_model(self, model: str) -> bool:
        """Validate if the model name is supported by this provider"""
        pass

    @abstractmethod
    def get_supported_models(self) -> list[str]:
        """Get list of supported model names"""
        pass
