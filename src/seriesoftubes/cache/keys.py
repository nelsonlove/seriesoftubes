"""Cache key generation utilities"""

import hashlib
import json
from typing import Any, Dict, Optional


def generate_cache_key(
    node_type: str,
    node_name: str,
    config_hash: str,
    context_hash: str,
    prefix: str | None = None,
) -> str:
    """Generate a cache key for node execution

    Args:
        node_type: Type of the node (llm, http, file, etc.)
        node_name: Name of the node
        config_hash: Hash of the node configuration
        context_hash: Hash of the execution context
        prefix: Optional prefix for the key

    Returns:
        Cache key string
    """
    key_parts = [node_type, node_name, config_hash, context_hash]
    if prefix:
        key_parts.insert(0, prefix)

    return ":".join(key_parts)


def hash_dict(data: dict[str, Any]) -> str:
    """Create a deterministic hash of a dictionary

    Args:
        data: Dictionary to hash

    Returns:
        MD5 hash string
    """
    # Sort keys for deterministic ordering
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()


def hash_config(config: Any) -> str:
    """Hash a node configuration object

    Args:
        config: Node configuration (Pydantic model)

    Returns:
        MD5 hash string
    """
    if hasattr(config, "model_dump"):
        # Pydantic model
        config_dict = config.model_dump()
    elif hasattr(config, "dict"):
        # Legacy Pydantic model
        config_dict = config.dict()
    else:
        # Assume it's already a dict
        config_dict = config

    return hash_dict(config_dict)


def hash_context(
    context_data: dict[str, Any], exclude_keys: list[str] | None = None
) -> str:
    """Hash execution context data

    Args:
        context_data: Context data dictionary
        exclude_keys: Keys to exclude from hashing (e.g., timestamps)

    Returns:
        MD5 hash string
    """
    if exclude_keys:
        filtered_data = {k: v for k, v in context_data.items() if k not in exclude_keys}
    else:
        filtered_data = context_data

    return hash_dict(filtered_data)


class CacheKeyBuilder:
    """Builder class for constructing cache keys"""

    def __init__(self, node_type: str, node_name: str):
        self.node_type = node_type
        self.node_name = node_name
        self.prefix: str | None = None
        self.config_hash: str | None = None
        self.context_hash: str | None = None

    def with_prefix(self, prefix: str) -> "CacheKeyBuilder":
        """Add a prefix to the cache key"""
        self.prefix = prefix
        return self

    def with_config(self, config: Any) -> "CacheKeyBuilder":
        """Add configuration hash to the cache key"""
        self.config_hash = hash_config(config)
        return self

    def with_context(
        self, context_data: dict[str, Any], exclude_keys: list[str] | None = None
    ) -> "CacheKeyBuilder":
        """Add context hash to the cache key"""
        self.context_hash = hash_context(context_data, exclude_keys)
        return self

    def build(self) -> str:
        """Build the final cache key"""
        if self.config_hash is None:
            msg = "Configuration hash is required"
            raise ValueError(msg)
        if self.context_hash is None:
            msg = "Context hash is required"
            raise ValueError(msg)

        return generate_cache_key(
            self.node_type,
            self.node_name,
            self.config_hash,
            self.context_hash,
            self.prefix,
        )
