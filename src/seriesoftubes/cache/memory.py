"""In-memory cache backend"""

import asyncio
import time
from typing import Any, Dict, Optional, Tuple

from seriesoftubes.cache.base import CacheBackend


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend using a dictionary

    Good for development and testing, but data is not persistent
    and is not shared between processes.
    """

    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, tuple[Any, float | None]] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """Get a value from cache"""
        async with self._lock:
            if key not in self._cache:
                return None

            value, expires_at = self._cache[key]

            # Check if expired
            if expires_at is not None and time.time() > expires_at:
                del self._cache[key]
                return None

            return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value in cache"""
        async with self._lock:
            # Calculate expiration time
            expires_at = None
            if ttl is not None:
                expires_at = time.time() + ttl

            # Evict oldest entries if at max size
            if len(self._cache) >= self._max_size and key not in self._cache:
                # Remove the first (oldest) entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[key] = (value, expires_at)

    async def delete(self, key: str) -> bool:
        """Delete a value from cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        result = await self.get(key)
        return result is not None

    async def clear(self) -> None:
        """Clear all cache entries"""
        async with self._lock:
            self._cache.clear()

    async def close(self) -> None:
        """Close the cache backend (no-op for memory cache)"""
        pass

    def size(self) -> int:
        """Get current cache size (for testing/debugging)"""
        return len(self._cache)
