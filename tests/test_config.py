"""Tests for configuration loading"""

from pathlib import Path

import pytest

from seriesoftubes.config import LLMConfig, load_config


def test_llm_config_validation():
    """Test LLM config validation"""
    # Valid config
    config = LLMConfig(
        provider="openai",
        model="gpt-4",
        api_key_env="OPENAI_API_KEY",
        temperature=0.7,
        api_key=None,
    )
    assert config.provider == "openai"
    assert config.temperature == 0.7  # default

    # Invalid provider
    with pytest.raises(ValueError, match="Provider must be one of"):
        LLMConfig(
            provider="invalid",
            model="gpt-4",
            api_key_env="OPENAI_API_KEY",
            temperature=0.7,
            api_key=None,
        )


def test_llm_config_api_key_resolution(monkeypatch):
    """Test API key resolution from environment"""
    config = LLMConfig(
        provider="openai",
        model="gpt-4",
        api_key_env="TEST_API_KEY",
        temperature=0.7,
        api_key=None,
    )

    # No env var set
    with pytest.raises(ValueError, match="Environment variable TEST_API_KEY not set"):
        config.resolve_api_key()

    # With env var
    monkeypatch.setenv("TEST_API_KEY", "sk-test123")
    config.resolve_api_key()
    assert config.api_key == "sk-test123"


def test_load_config_from_file(tmp_path, monkeypatch):
    """Test loading config from YAML file"""
    config_file = tmp_path / ".tubes.yaml"
    config_file.write_text(
        """
llm:
  provider: openai
  model: gpt-4o
  api_key_env: TEST_KEY
  temperature: 0.5

http:
  timeout: 60
  retry_attempts: 5

execution:
  max_duration: 600
  save_intermediate: false
"""
    )

    # Set env var for API key
    monkeypatch.setenv("TEST_KEY", "test-key-123")

    config = load_config(config_file)

    assert config.llm.provider == "openai"
    assert config.llm.model == "gpt-4o"
    assert config.llm.temperature == 0.5
    assert config.llm.api_key == "test-key-123"

    assert config.http.timeout == 60
    assert config.http.retry_attempts == 5

    assert config.execution.max_duration == 600
    assert config.execution.save_intermediate is False


def test_load_config_defaults(tmp_path, monkeypatch):
    """Test config with defaults for optional sections"""
    config_file = tmp_path / ".tubes.yaml"
    config_file.write_text(
        """
llm:
  provider: anthropic
  model: claude-3-opus
  api_key_env: ANTHROPIC_API_KEY
"""
    )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    config = load_config(config_file)

    # Check defaults
    assert config.http.timeout == 30
    assert config.http.retry_attempts == 3
    assert config.execution.max_duration == 300
    assert config.execution.save_intermediate is True


def test_load_config_invalid_yaml(tmp_path):
    """Test handling of invalid YAML"""
    config_file = tmp_path / ".tubes.yaml"
    config_file.write_text("invalid: yaml: content:")

    with pytest.raises(ValueError, match="Invalid YAML"):
        load_config(config_file)


def test_load_config_missing_required(tmp_path):
    """Test handling of missing required fields"""
    config_file = tmp_path / ".tubes.yaml"
    config_file.write_text(
        """
llm:
  provider: openai
  # missing model and api_key_env
"""
    )

    with pytest.raises(ValueError, match="Invalid configuration"):
        load_config(config_file)


def test_load_config_file_not_found():
    """Test handling of missing config file"""
    with pytest.raises(FileNotFoundError, match="Cannot read config file"):
        load_config(Path("/nonexistent/.tubes.yaml"))


def test_find_config_file(tmp_path, monkeypatch):
    """Test automatic config file discovery"""
    # Create nested directory structure
    project_dir = tmp_path / "project"
    sub_dir = project_dir / "src" / "nested"
    sub_dir.mkdir(parents=True)

    # Place config in project root
    config_file = project_dir / ".tubes.yaml"
    config_file.write_text(
        """
llm:
  provider: openai
  model: gpt-4
  api_key_env: TEST_KEY
"""
    )

    # Change to nested directory
    monkeypatch.chdir(sub_dir)
    monkeypatch.setenv("TEST_KEY", "test")

    # Should find config in parent directory
    config = load_config()
    assert config.llm.provider == "openai"


def test_config_not_found_in_search(monkeypatch, tmp_path):
    """Test error when config not found in directory tree"""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="No .tubes.yaml file found"):
        load_config()
