"""Integration tests for caching with the workflow engine"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from seriesoftubes.cache import MemoryCacheBackend
from seriesoftubes.cache.manager import CacheManager
from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.models import LLMNodeConfig, Node, NodeType, Workflow


@pytest.mark.asyncio
async def test_engine_with_memory_cache():
    """Test workflow engine with memory caching"""
    # Create cache manager with memory backend
    cache_backend = MemoryCacheBackend()
    cache_manager = CacheManager(cache_backend, default_ttl=3600)

    # Create engine with cache manager
    engine = WorkflowEngine(cache_manager=cache_manager)

    # Create a simple workflow
    workflow = Workflow(
        name="test-cache",
        version="1.0.0",
        nodes={
            "llm_node": Node(
                name="llm_node",
                type=NodeType.LLM,
                config=LLMNodeConfig(
                    prompt="Test prompt",
                    model="gpt-4o",
                ),
            )
        },
    )

    # Mock the LLM provider to return a predictable result
    with patch("seriesoftubes.nodes.llm.get_provider") as mock_get_provider:
        mock_provider = mock_get_provider.return_value
        mock_provider.call = AsyncMock(return_value={"test": "response"})

        # First execution - should call LLM and cache result
        context1 = await engine.execute(workflow, inputs={})

        assert context1.outputs["llm_node"]["response"] == '{"test": "response"}'
        assert context1.outputs["llm_node"]["structured_output"] == {"test": "response"}
        # Check that provider was called
        assert mock_provider.call.call_count == 1

        # Reset call count
        mock_provider.call.reset_mock()

        # Second execution with same inputs - should use cache
        context2 = await engine.execute(workflow, inputs={})

        assert context2.outputs["llm_node"]["response"] == '{"test": "response"}'
        assert context2.outputs["llm_node"]["structured_output"] == {"test": "response"}
        # Check that provider was NOT called again (cache hit)
        assert mock_provider.call.call_count == 0

    await engine.close()


@pytest.mark.asyncio
async def test_engine_cache_different_inputs():
    """Test that different inputs produce different cache keys"""
    cache_backend = MemoryCacheBackend()
    cache_manager = CacheManager(cache_backend, default_ttl=3600)
    engine = WorkflowEngine(cache_manager=cache_manager)

    workflow = Workflow(
        name="test-cache-inputs",
        version="1.0.0",
        inputs={"user_input": {"type": "string", "required": True}},
        nodes={
            "llm_node": Node(
                name="llm_node",
                type=NodeType.LLM,
                config=LLMNodeConfig(
                    prompt="Process: {{ inputs.user_input }}",
                    model="gpt-4o",
                ),
            )
        },
    )

    with patch("seriesoftubes.nodes.llm.get_provider") as mock_get_provider:
        mock_provider = mock_get_provider.return_value
        mock_provider.call = AsyncMock(
            side_effect=[{"result": "response1"}, {"result": "response2"}]
        )

        # Execute with first input
        context1 = await engine.execute(workflow, inputs={"user_input": "input1"})
        assert mock_provider.call.call_count == 1

        # Execute with different input - should not hit cache
        context2 = await engine.execute(workflow, inputs={"user_input": "input2"})
        assert mock_provider.call.call_count == 2

        # Execute with first input again - should hit cache
        context3 = await engine.execute(workflow, inputs={"user_input": "input1"})
        assert mock_provider.call.call_count == 2  # No additional call

        # Results should match
        assert context1.outputs["llm_node"]["structured_output"] == {
            "result": "response1"
        }
        assert context2.outputs["llm_node"]["structured_output"] == {
            "result": "response2"
        }
        assert context3.outputs["llm_node"]["structured_output"] == {
            "result": "response1"
        }

    await engine.close()


@pytest.mark.asyncio
async def test_engine_cache_disabled():
    """Test engine with caching disabled"""
    # Create engine without cache manager (caching disabled)
    engine = WorkflowEngine(cache_manager=None)

    workflow = Workflow(
        name="test-no-cache",
        version="1.0.0",
        nodes={
            "llm_node": Node(
                name="llm_node",
                type=NodeType.LLM,
                config=LLMNodeConfig(
                    prompt="Test prompt",
                    model="gpt-4o",
                ),
            )
        },
    )

    with patch("seriesoftubes.nodes.llm.get_provider") as mock_get_provider:
        # Create a new mock provider for each call to get_provider
        def create_mock_provider():
            mock_provider = MagicMock()
            mock_provider.call = AsyncMock(return_value={"test": "response"})
            return mock_provider

        mock_get_provider.side_effect = create_mock_provider

        # First execution
        result1 = await engine.execute(workflow, inputs={})
        assert mock_get_provider.call_count == 1

        # Second execution - should call get_provider again (no caching)
        result2 = await engine.execute(workflow, inputs={})
        assert mock_get_provider.call_count == 2

    await engine.close()


@pytest.mark.asyncio
async def test_cache_error_handling():
    """Test that cache errors don't break execution"""

    # Create a mock cache that fails
    class FailingCache:
        async def get_cached_result(self, *args, **kwargs):
            raise Exception("Cache read error")

        async def cache_result(self, *args, **kwargs):
            raise Exception("Cache write error")

        async def close(self):
            pass

    engine = WorkflowEngine(cache_manager=FailingCache())

    workflow = Workflow(
        name="test-cache-error",
        version="1.0.0",
        nodes={
            "llm_node": Node(
                name="llm_node",
                type=NodeType.LLM,
                config=LLMNodeConfig(
                    prompt="Test prompt",
                    model="gpt-4o",
                ),
            )
        },
    )

    with patch("seriesoftubes.nodes.llm.get_provider") as mock_get_provider:
        mock_provider = mock_get_provider.return_value
        mock_provider.call = AsyncMock(return_value={"test": "response"})

        # Execution should succeed despite cache errors
        context = await engine.execute(workflow, inputs={})

        assert context.outputs["llm_node"]["response"] == '{"test": "response"}'
        assert mock_provider.call.call_count == 1

    await engine.close()


@pytest.mark.asyncio
async def test_cache_with_non_cacheable_nodes():
    """Test that non-cacheable nodes are not cached"""
    cache_backend = MemoryCacheBackend()
    cache_manager = CacheManager(cache_backend, default_ttl=3600)
    engine = WorkflowEngine(cache_manager=cache_manager)

    workflow = Workflow(
        name="test-no-cache-nodes",
        version="1.0.0",
        nodes={
            "conditional_node": Node(
                name="conditional_node",
                type=NodeType.CONDITIONAL,
                config={
                    "conditions": [
                        {
                            "condition": "default",
                            "then": "default_path",
                            "is_default": True,
                        }
                    ]
                },
            )
        },
    )

    # Execute twice - conditional nodes should not be cached
    context1 = await engine.execute(workflow, inputs={})
    context2 = await engine.execute(workflow, inputs={})

    # Both should execute normally (conditional nodes don't cache)
    assert context1.outputs["conditional_node"]["selected_route"] == "default_path"
    assert context2.outputs["conditional_node"]["selected_route"] == "default_path"

    # Cache should be empty (no cacheable nodes)
    assert cache_backend.size() == 0

    await engine.close()


try:
    from seriesoftubes.cache.test_redis import FakeRedisCacheBackend

    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False


@pytest.mark.asyncio
@pytest.mark.skipif(not FAKEREDIS_AVAILABLE, reason="fakeredis not available")
async def test_engine_with_test_redis_cache():
    """Test workflow engine with test Redis caching"""
    # Create cache manager with test Redis backend
    cache_backend = FakeRedisCacheBackend()
    cache_manager = CacheManager(cache_backend, default_ttl=3600)
    engine = WorkflowEngine(cache_manager=cache_manager)

    workflow = Workflow(
        name="test-redis-cache",
        version="1.0.0",
        nodes={
            "llm_node": Node(
                name="llm_node",
                type=NodeType.LLM,
                config=LLMNodeConfig(
                    prompt="Test prompt",
                    model="gpt-4o",
                ),
            )
        },
    )

    with patch("seriesoftubes.nodes.llm.get_provider") as mock_get_provider:
        mock_provider = mock_get_provider.return_value
        mock_provider.call = AsyncMock(return_value={"test": "redis_response"})

        # First execution - should call LLM and cache in Redis
        context1 = await engine.execute(workflow, inputs={})
        assert context1.outputs["llm_node"]["structured_output"] == {
            "test": "redis_response"
        }
        assert mock_provider.call.call_count == 1

        # Reset call count
        mock_provider.call.reset_mock()

        # Second execution - should use Redis cache
        context2 = await engine.execute(workflow, inputs={})
        assert context2.outputs["llm_node"]["structured_output"] == {
            "test": "redis_response"
        }
        assert mock_provider.call.call_count == 0

    await engine.close()
