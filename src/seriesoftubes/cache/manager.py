"""Cache manager for node execution caching"""

from typing import Any, Dict, Optional

from seriesoftubes.cache.base import CacheBackend
from seriesoftubes.cache.keys import CacheKeyBuilder


class CacheManager:
    """Manages caching for node execution results"""

    def __init__(self, backend: CacheBackend, default_ttl: int = 3600):
        """Initialize cache manager

        Args:
            backend: Cache backend to use
            default_ttl: Default TTL in seconds (1 hour)
        """
        self.backend = backend
        self.default_ttl = default_ttl

    async def get_cached_result(
        self,
        node_type: str,
        node_name: str,
        config: Any,
        context_data: dict[str, Any],
        exclude_context_keys: list[str] | None = None,
    ) -> Any | None:
        """Get cached result for node execution

        Args:
            node_type: Type of the node
            node_name: Name of the node
            config: Node configuration
            context_data: Execution context data
            exclude_context_keys: Context keys to exclude from cache key

        Returns:
            Cached result or None if not found
        """
        cache_key = (
            CacheKeyBuilder(node_type, node_name)
            .with_config(config)
            .with_context(context_data, exclude_context_keys)
            .build()
        )

        return await self.backend.get(cache_key)

    async def cache_result(
        self,
        node_type: str,
        node_name: str,
        config: Any,
        context_data: dict[str, Any],
        result: Any,
        ttl: int | None = None,
        exclude_context_keys: list[str] | None = None,
    ) -> None:
        """Cache result for node execution

        Args:
            node_type: Type of the node
            node_name: Name of the node
            config: Node configuration
            context_data: Execution context data
            result: Result to cache
            ttl: Time to live in seconds (uses default if None)
            exclude_context_keys: Context keys to exclude from cache key
        """
        cache_key = (
            CacheKeyBuilder(node_type, node_name)
            .with_config(config)
            .with_context(context_data, exclude_context_keys)
            .build()
        )

        cache_ttl = ttl if ttl is not None else self.default_ttl
        await self.backend.set(cache_key, result, cache_ttl)

    async def invalidate_node(
        self,
        node_type: str,
        node_name: str,
        config: Any,
        context_data: dict[str, Any],
        exclude_context_keys: list[str] | None = None,
    ) -> bool:
        """Invalidate cached result for specific node execution

        Args:
            node_type: Type of the node
            node_name: Name of the node
            config: Node configuration
            context_data: Execution context data
            exclude_context_keys: Context keys to exclude from cache key

        Returns:
            True if cache entry was deleted
        """
        cache_key = (
            CacheKeyBuilder(node_type, node_name)
            .with_config(config)
            .with_context(context_data, exclude_context_keys)
            .build()
        )

        return await self.backend.delete(cache_key)

    async def clear_all(self) -> None:
        """Clear all cached results"""
        await self.backend.clear()

    async def close(self) -> None:
        """Close the cache backend"""
        await self.backend.close()


# Cache settings for different node types
CACHE_SETTINGS = {
    "llm": {
        "ttl": 3600,  # 1 hour - LLM responses are expensive but may become stale
        "exclude_context_keys": ["execution_id", "timestamp"],
        "enabled": True,
    },
    "http": {
        "ttl": 300,  # 5 minutes - HTTP responses may change frequently
        "exclude_context_keys": ["execution_id", "timestamp"],
        "enabled": True,
    },
    "file": {
        "ttl": 1800,  # 30 minutes - Files may be updated
        "exclude_context_keys": ["execution_id", "timestamp"],
        "enabled": True,
    },
    "python": {
        "ttl": 600,  # 10 minutes - Python execution results
        "exclude_context_keys": ["execution_id", "timestamp"],
        "enabled": True,
    },
    # Data flow nodes generally shouldn't be cached as they're transformations
    "split": {"enabled": False},
    "aggregate": {"enabled": False},
    "filter": {"enabled": False},
    "transform": {"enabled": False},
    "join": {"enabled": False},
    "foreach": {"enabled": False},
    "conditional": {"enabled": False},
}
