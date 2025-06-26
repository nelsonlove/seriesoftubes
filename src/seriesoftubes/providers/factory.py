"""LLM provider factory"""

from seriesoftubes.providers.anthropic import AnthropicProvider
from seriesoftubes.providers.base import LLMProvider
from seriesoftubes.providers.openai import OpenAIProvider

# Provider registry
PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def get_provider(provider_name: str, api_key: str | None = None) -> LLMProvider:
    """Get an LLM provider instance

    Args:
        provider_name: Name of the provider (openai, anthropic)
        api_key: API key for the provider

    Returns:
        Provider instance

    Raises:
        ValueError: If provider is not supported
    """
    if provider_name not in PROVIDERS:
        supported = ", ".join(PROVIDERS.keys())
        msg = f"Unsupported LLM provider: {provider_name}. Supported: {supported}"
        raise ValueError(msg)

    provider_class = PROVIDERS[provider_name]
    return provider_class(api_key=api_key)


def get_supported_providers() -> list[str]:
    """Get list of supported provider names"""
    return list(PROVIDERS.keys())
