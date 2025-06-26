"""Cache backend factory"""

from typing import Optional

from seriesoftubes.cache.base import CacheBackend
from seriesoftubes.cache.memory import MemoryCacheBackend
from seriesoftubes.cache.redis import REDIS_AVAILABLE, RedisCacheBackend


def get_cache_backend(
    backend_type: str = "memory",
    redis_url: str | None = None,
    **kwargs,
) -> CacheBackend:
    """Get a cache backend instance

    Args:
        backend_type: Type of cache backend ("memory", "redis", or "test_redis")
        redis_url: Redis connection URL (for redis backend)
        **kwargs: Additional backend-specific arguments

    Returns:
        Cache backend instance

    Raises:
        ValueError: If backend type is not supported
        ImportError: If Redis backend is requested but not available
    """
    if backend_type == "memory":
        return MemoryCacheBackend(**kwargs)

    elif backend_type == "redis":
        if not REDIS_AVAILABLE:
            msg = "Redis backend requested but redis package not installed. Install with: pip install redis"
            raise ImportError(msg)

        redis_kwargs = kwargs.copy()
        if redis_url:
            redis_kwargs["url"] = redis_url

        return RedisCacheBackend(**redis_kwargs)

    elif backend_type == "test_redis":
        # Import here to avoid dependency issues
        from seriesoftubes.cache.test_redis import FakeRedisCacheBackend

        return FakeRedisCacheBackend(**kwargs)

    else:
        supported = ["memory", "redis"] if REDIS_AVAILABLE else ["memory"]
        supported.append("test_redis")
        msg = f"Unsupported cache backend: {backend_type}. Supported: {', '.join(supported)}"
        raise ValueError(msg)


def get_supported_backends() -> list[str]:
    """Get list of supported cache backend types"""
    backends = ["memory"]
    if REDIS_AVAILABLE:
        backends.append("redis")
    return backends
