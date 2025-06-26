"""Configuration loading and management for seriesoftubes"""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


class LLMConfig(BaseModel):
    """LLM provider configuration"""

    provider: str = Field(..., description="LLM provider (openai, anthropic)")
    model: str = Field(..., description="Model name")
    api_key_env: str = Field(..., description="Environment variable for API key")
    temperature: float = Field(0.7, description="Default temperature")
    api_key: str | None = Field(None, description="Resolved API key")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate LLM provider"""
        valid_providers = ["openai", "anthropic"]
        if v not in valid_providers:
            msg = f"Provider must be one of {valid_providers}"
            raise ValueError(msg)
        return v

    def resolve_api_key(self) -> None:
        """Resolve API key from environment"""
        if self.api_key_env:
            self.api_key = os.getenv(self.api_key_env)
            if not self.api_key:
                msg = (
                    f"Environment variable {self.api_key_env} not set. "
                    f"Please set it or configure a different api_key_env."
                )
                raise ValueError(msg)


class HTTPConfig(BaseModel):
    """HTTP client configuration"""

    timeout: int = Field(default=30, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")


class CacheConfig(BaseModel):
    """Cache configuration"""

    enabled: bool = Field(default=True, description="Enable caching")
    backend: str = Field(default="memory", description="Cache backend (memory, redis)")
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")
    redis_db: int = Field(default=0, description="Redis database number")
    key_prefix: str = Field(default="s10s:", description="Cache key prefix")
    default_ttl: int = Field(default=3600, description="Default TTL in seconds")


class ExecutionConfig(BaseModel):
    """Workflow execution configuration"""

    max_duration: int = Field(
        default=300, description="Maximum execution time in seconds"
    )
    save_intermediate: bool = Field(
        default=True, description="Save intermediate outputs"
    )


class Config(BaseModel):
    """Application configuration"""

    llm: LLMConfig
    http: HTTPConfig = HTTPConfig()
    execution: ExecutionConfig = ExecutionConfig()
    cache: CacheConfig = CacheConfig()

    def resolve_secrets(self) -> None:
        """Resolve all secrets from environment"""
        self.llm.resolve_api_key()


def find_config_file() -> Path | None:
    """Find .tubes.yaml config file in current or parent directories"""
    current = Path.cwd()

    # Check current directory and up to 5 parent directories
    for _ in range(6):
        config_path = current / ".tubes.yaml"
        if config_path.exists():
            return config_path

        # Stop at root directory
        if current.parent == current:
            break
        current = current.parent

    return None


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from YAML file

    Args:
        config_path: Path to config file. If None, searches for .tubes.yaml

    Returns:
        Loaded configuration object

    Raises:
        FileNotFoundError: If config file not found
        ValueError: If config is invalid
    """
    if config_path is None:
        config_path = find_config_file()
        if config_path is None:
            msg = (
                "No .tubes.yaml file found in current or parent directories. "
                "Create one from .tubes.example.yaml"
            )
            raise FileNotFoundError(msg)

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML in config file: {e}"
        raise ValueError(msg) from e
    except OSError as e:
        msg = f"Cannot read config file: {e}"
        raise FileNotFoundError(msg) from e

    if not isinstance(data, dict):
        msg = "Config file must contain a YAML object"
        raise ValueError(msg)

    try:
        config = Config(**data)
        config.resolve_secrets()
        return config
    except ValidationError as e:
        msg = f"Invalid configuration: {e}"
        raise ValueError(msg) from e


class _ConfigStore:
    """Singleton store for configuration"""

    _instance: Config | None = None

    @classmethod
    def get(cls) -> Config:
        """Get the configuration instance (loads on first call)"""
        if cls._instance is None:
            cls._instance = load_config()
        return cls._instance

    @classmethod
    def set_instance(cls, config: Config) -> None:
        """Set the configuration instance (mainly for testing)"""
        cls._instance = config

    @classmethod
    def clear(cls) -> None:
        """Clear the configuration instance (mainly for testing)"""
        cls._instance = None


def get_config() -> Config:
    """Get the global configuration instance

    Returns:
        Global config object (loads on first call)
    """
    return _ConfigStore.get()


def set_config(config: Config) -> None:
    """Set the global configuration instance (mainly for testing)"""
    _ConfigStore.set_instance(config)
