"""Cache decorators for node execution"""

from collections.abc import Callable
from functools import wraps
from typing import Any, Optional

from seriesoftubes.cache.manager import CACHE_SETTINGS, CacheManager
from seriesoftubes.models import Node
from seriesoftubes.nodes.base import NodeContext, NodeResult


def cached_execution(
    cache_manager: CacheManager | None = None,
    ttl: int | None = None,
    exclude_context_keys: list[str] | None = None,
) -> Callable:
    """Decorator to add caching to node execution

    Args:
        cache_manager: Cache manager instance (if None, no caching)
        ttl: Time to live in seconds (overrides node type default)
        exclude_context_keys: Context keys to exclude from cache key

    Returns:
        Decorated function
    """

    def decorator(execute_func: Callable) -> Callable:
        @wraps(execute_func)
        async def wrapper(self, node: Node, context: NodeContext) -> NodeResult:
            # If no cache manager or caching disabled, execute normally
            if cache_manager is None:
                return await execute_func(self, node, context)

            node_type = (
                node.node_type.value
                if hasattr(node.node_type, "value")
                else str(node.node_type)
            )

            # Check if caching is enabled for this node type
            cache_settings = CACHE_SETTINGS.get(node_type, {})
            if not cache_settings.get("enabled", False):
                return await execute_func(self, node, context)

            # Prepare context data for caching
            context_data = {}
            if hasattr(context, "outputs"):
                context_data["outputs"] = context.outputs
            if hasattr(context, "inputs"):
                context_data["inputs"] = context.inputs

            # Use provided exclude keys or defaults from settings
            cache_exclude_keys = exclude_context_keys or cache_settings.get(
                "exclude_context_keys", []
            )

            # Try to get cached result
            try:
                cached_result = await cache_manager.get_cached_result(
                    node_type=node_type,
                    node_name=node.name,
                    config=node.config,
                    context_data=context_data,
                    exclude_context_keys=cache_exclude_keys,
                )

                if cached_result is not None:
                    # Return cached result wrapped in NodeResult
                    return NodeResult(
                        output=cached_result, success=True, metadata={"cache_hit": True}
                    )
            except Exception as e:
                # Cache read error - continue with execution
                print(f"Cache read error for node {node.name}: {e}")

            # Execute the function
            result = await execute_func(self, node, context)

            # Cache successful results
            if result.success and result.output is not None:
                try:
                    cache_ttl = ttl or cache_settings.get("ttl")
                    await cache_manager.cache_result(
                        node_type=node_type,
                        node_name=node.name,
                        config=node.config,
                        context_data=context_data,
                        result=result.output,
                        ttl=cache_ttl,
                        exclude_context_keys=cache_exclude_keys,
                    )

                    # Add cache metadata
                    if result.metadata is None:
                        result.metadata = {}
                    result.metadata["cache_hit"] = False

                except Exception as e:
                    # Cache write error - don't fail the execution
                    print(f"Cache write error for node {node.name}: {e}")

            return result

        return wrapper

    return decorator
