"""Redis cache backend"""

import json
from typing import Any, Optional

from seriesoftubes.cache.base import CacheBackend

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
    RedisType = redis.Redis
except ImportError:
    REDIS_AVAILABLE = False
    RedisType = Any  # Fallback type when Redis not available


class RedisCacheBackend(CacheBackend):
    """Redis cache backend for persistent, distributed caching"""

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        db: int = 0,
        key_prefix: str = "s10s:",
        encoding: str = "utf-8",
    ):
        if not REDIS_AVAILABLE:
            msg = "Redis not available. Install with: pip install redis"
            raise ImportError(msg)

        self.url = url
        self.db = db
        self.key_prefix = key_prefix
        self.encoding = encoding
        self._client: RedisType | None = None

    async def _get_client(self) -> RedisType:
        """Get or create Redis client"""
        if self._client is None:
            self._client = redis.from_url(
                self.url,
                db=self.db,
                encoding=self.encoding,
                decode_responses=True,
            )
        return self._client

    def _make_key(self, key: str) -> str:
        """Add prefix to cache key"""
        return f"{self.key_prefix}{key}"

    async def get(self, key: str) -> Any | None:
        """Get a value from cache"""
        client = await self._get_client()
        prefixed_key = self._make_key(key)

        try:
            value = await client.get(prefixed_key)
            if value is None:
                return None

            # Deserialize JSON
            return json.loads(value)
        except (json.JSONDecodeError, redis.RedisError):
            # If we can't deserialize or Redis error, treat as cache miss
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value in cache"""
        client = await self._get_client()
        prefixed_key = self._make_key(key)

        try:
            # Serialize to JSON
            serialized_value = json.dumps(value, default=str)
            await client.set(prefixed_key, serialized_value, ex=ttl)
        except (json.JSONEncodeError, redis.RedisError) as e:
            # Log error but don't fail the operation
            print(f"Cache set failed for key {key}: {e}")

    async def delete(self, key: str) -> bool:
        """Delete a value from cache"""
        client = await self._get_client()
        prefixed_key = self._make_key(key)

        try:
            result = await client.delete(prefixed_key)
            return result > 0
        except redis.RedisError:
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        client = await self._get_client()
        prefixed_key = self._make_key(key)

        try:
            result = await client.exists(prefixed_key)
            return result > 0
        except redis.RedisError:
            return False

    async def clear(self) -> None:
        """Clear all cache entries with our prefix"""
        client = await self._get_client()

        try:
            # Find all keys with our prefix
            pattern = f"{self.key_prefix}*"
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)

            # Delete in batches
            if keys:
                await client.delete(*keys)
        except redis.RedisError as e:
            print(f"Cache clear failed: {e}")

    async def close(self) -> None:
        """Close the Redis connection"""
        if self._client:
            try:
                # Use aclose() for newer Redis versions
                if hasattr(self._client, "aclose"):
                    await self._client.aclose()
                else:
                    await self._client.close()
            except Exception:
                # Ignore close errors
                pass
            self._client = None
