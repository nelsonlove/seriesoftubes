"""Test Redis backend using fakeredis"""

from typing import Optional

from seriesoftubes.cache.redis import RedisCacheBackend

try:
    import fakeredis.aioredis as fake_redis

    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False
    fake_redis = None


class FakeRedisCacheBackend(RedisCacheBackend):
    """Redis cache backend using fakeredis for testing"""

    def __init__(
        self,
        key_prefix: str = "test:",
        encoding: str = "utf-8",
    ):
        if not FAKEREDIS_AVAILABLE:
            msg = "fakeredis not available. Install with dev dependencies: pip install -e .[dev]"
            raise ImportError(msg)

        # Don't call super().__init__ since we don't need Redis connection params
        self.key_prefix = key_prefix
        self.encoding = encoding
        self._client: fake_redis.FakeRedis | None = None

    async def _get_client(self) -> fake_redis.FakeRedis:
        """Get or create fake Redis client"""
        if self._client is None:
            self._client = fake_redis.FakeRedis(
                encoding=self.encoding,
                decode_responses=True,
            )
        return self._client
