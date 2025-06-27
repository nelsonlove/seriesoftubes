"""Tests for caching functionality"""

import pytest

from seriesoftubes.cache import MemoryCacheBackend, get_cache_backend
from seriesoftubes.cache.keys import CacheKeyBuilder, hash_config, hash_dict
from seriesoftubes.cache.manager import CacheManager
from seriesoftubes.models import LLMNodeConfig


class TestMemoryCacheBackend:
    """Test memory cache backend"""

    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """Test basic cache operations"""
        cache = MemoryCacheBackend(max_size=10)

        # Test set and get
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

        # Test non-existent key
        result = await cache.get("nonexistent")
        assert result is None

        # Test exists
        assert await cache.exists("key1") is True
        assert await cache.exists("nonexistent") is False

        # Test delete
        assert await cache.delete("key1") is True
        assert await cache.delete("nonexistent") is False
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test TTL expiration"""
        cache = MemoryCacheBackend()

        # Set with very short TTL
        await cache.set("key1", "value1", ttl=1)
        assert await cache.get("key1") == "value1"

        # Wait for expiration (simulate with manual time check)
        import time

        time.sleep(1.1)
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_max_size_eviction(self):
        """Test max size eviction"""
        cache = MemoryCacheBackend(max_size=2)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        assert cache.size() == 2

        # Adding third key should evict the first
        await cache.set("key3", "value3")
        assert cache.size() == 2
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test cache clear"""
        cache = MemoryCacheBackend()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        assert cache.size() == 2

        await cache.clear()
        assert cache.size() == 0
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None


class TestCacheKeys:
    """Test cache key generation"""

    def test_hash_dict(self):
        """Test dictionary hashing"""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 2, "a": 1}  # Different order
        dict3 = {"a": 1, "b": 3}  # Different values

        hash1 = hash_dict(dict1)
        hash2 = hash_dict(dict2)
        hash3 = hash_dict(dict3)

        # Same content should produce same hash regardless of order
        assert hash1 == hash2
        # Different content should produce different hash
        assert hash1 != hash3

    def test_hash_config(self):
        """Test config hashing"""
        config1 = LLMNodeConfig(prompt="test prompt", model="gpt-4o")
        config2 = LLMNodeConfig(prompt="test prompt", model="gpt-4o")
        config3 = LLMNodeConfig(prompt="different prompt", model="gpt-4o")

        hash1 = hash_config(config1)
        hash2 = hash_config(config2)
        hash3 = hash_config(config3)

        # Same config should produce same hash
        assert hash1 == hash2
        # Different config should produce different hash
        assert hash1 != hash3

    def test_cache_key_builder(self):
        """Test cache key builder"""
        config = LLMNodeConfig(prompt="test prompt", model="gpt-4o")
        context_data = {"inputs": {"test": "data"}}

        key = (
            CacheKeyBuilder("llm", "test_node")
            .with_config(config)
            .with_context(context_data)
            .build()
        )

        assert isinstance(key, str)
        assert "llm" in key
        assert "test_node" in key

        # Same inputs should produce same key
        key2 = (
            CacheKeyBuilder("llm", "test_node")
            .with_config(config)
            .with_context(context_data)
            .build()
        )
        assert key == key2

        # Different context should produce different key
        key3 = (
            CacheKeyBuilder("llm", "test_node")
            .with_config(config)
            .with_context({"inputs": {"different": "data"}})
            .build()
        )
        assert key != key3

    def test_exclude_context_keys(self):
        """Test excluding context keys from hash"""
        context_data = {
            "inputs": {"test": "data"},
            "timestamp": "2023-01-01",
            "execution_id": "123",
        }

        key1 = (
            CacheKeyBuilder("llm", "test_node")
            .with_config(LLMNodeConfig(prompt="test"))
            .with_context(context_data)
            .build()
        )

        key2 = (
            CacheKeyBuilder("llm", "test_node")
            .with_config(LLMNodeConfig(prompt="test"))
            .with_context(context_data, exclude_keys=["timestamp", "execution_id"])
            .build()
        )

        # Different context with timestamp should produce different keys
        context_data_different = context_data.copy()
        context_data_different["timestamp"] = "2023-01-02"
        context_data_different["execution_id"] = "456"

        key3 = (
            CacheKeyBuilder("llm", "test_node")
            .with_config(LLMNodeConfig(prompt="test"))
            .with_context(
                context_data_different, exclude_keys=["timestamp", "execution_id"]
            )
            .build()
        )

        # With exclusions, keys should be the same
        assert key2 == key3


class TestCacheManager:
    """Test cache manager"""

    @pytest.mark.asyncio
    async def test_cache_manager_operations(self):
        """Test cache manager operations"""
        backend = MemoryCacheBackend()
        manager = CacheManager(backend, default_ttl=3600)

        config = LLMNodeConfig(prompt="test prompt")
        context_data = {"inputs": {"test": "data"}}
        result = {"response": "test response"}

        # Cache result
        await manager.cache_result(
            node_type="llm",
            node_name="test_node",
            config=config,
            context_data=context_data,
            result=result,
        )

        # Get cached result
        cached = await manager.get_cached_result(
            node_type="llm",
            node_name="test_node",
            config=config,
            context_data=context_data,
        )

        assert cached == result

        # Different context should not match
        cached_different = await manager.get_cached_result(
            node_type="llm",
            node_name="test_node",
            config=config,
            context_data={"inputs": {"different": "data"}},
        )

        assert cached_different is None


class TestCacheFactory:
    """Test cache factory"""

    def test_get_memory_backend(self):
        """Test getting memory backend"""
        backend = get_cache_backend("memory", max_size=100)
        assert isinstance(backend, MemoryCacheBackend)

    def test_unsupported_backend(self):
        """Test unsupported backend"""
        with pytest.raises(ValueError, match="Unsupported cache backend"):
            get_cache_backend("unsupported")

    def test_redis_backend_unavailable(self):
        """Test Redis backend when not available"""
        # This test assumes Redis is not installed in test environment
        # If Redis is available, this will test the actual Redis backend
        try:
            backend = get_cache_backend("redis")
            # If we get here, Redis is available
            from seriesoftubes.cache.redis import RedisCacheBackend

            assert isinstance(backend, RedisCacheBackend)
        except ImportError:
            # Redis not available - this is the expected case for testing
            with pytest.raises(ImportError, match="redis package not installed"):
                get_cache_backend("redis")
