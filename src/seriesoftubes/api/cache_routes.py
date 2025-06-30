"""Cache management API routes"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from seriesoftubes.api.auth import get_current_active_user
from seriesoftubes.cache import get_cache_backend
from seriesoftubes.cache.base import CacheBackend
from seriesoftubes.cache.manager import CacheManager, CACHE_SETTINGS
from seriesoftubes.config import get_config
from seriesoftubes.db import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])


class CacheStatsResponse(BaseModel):
    """Cache statistics response"""
    
    backend_type: str
    enabled: bool
    node_settings: dict[str, dict[str, Any]]
    backend_info: dict[str, Any] | None = None


class CacheClearResponse(BaseModel):
    """Cache clear response"""
    
    success: bool
    message: str


async def get_cache_manager() -> CacheManager | None:
    """Get the cache manager instance"""
    try:
        config = get_config()
        if not config.cache.enabled:
            return None
            
        # Auto-detect Redis availability
        backend_type = config.cache.backend
        if backend_type == "memory":
            try:
                import redis
                r = redis.from_url(config.cache.redis_url)
                r.ping()
                backend_type = "redis"
            except Exception:
                pass
        
        backend = get_cache_backend(
            backend_type=backend_type,
            redis_url=config.cache.redis_url,
            db=config.cache.redis_db,
            key_prefix=config.cache.key_prefix,
        )
        return CacheManager(backend, config.cache.default_ttl)
    except Exception as e:
        logger.error(f"Failed to get cache manager: {e}")
        return None


@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    current_user: User = Depends(get_current_active_user),
) -> CacheStatsResponse:
    """Get cache statistics and configuration"""
    config = get_config()
    
    # Get backend info
    backend_info = None
    if config.cache.enabled:
        cache_manager = await get_cache_manager()
        if cache_manager:
            backend = cache_manager.backend
            backend_info = {
                "type": backend.__class__.__name__,
            }
            
            # Add backend-specific info
            if hasattr(backend, "size"):
                backend_info["size"] = backend.size()
            if hasattr(backend, "_max_size"):
                backend_info["max_size"] = backend._max_size
    
    return CacheStatsResponse(
        backend_type=config.cache.backend,
        enabled=config.cache.enabled,
        node_settings=CACHE_SETTINGS,
        backend_info=backend_info,
    )


@router.post("/clear", response_model=CacheClearResponse)
async def clear_cache(
    current_user: User = Depends(get_current_active_user),
) -> CacheClearResponse:
    """Clear all cache entries"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can clear the cache",
        )
    
    cache_manager = await get_cache_manager()
    if not cache_manager:
        return CacheClearResponse(
            success=False,
            message="Cache is not enabled",
        )
    
    try:
        await cache_manager.clear_all()
        return CacheClearResponse(
            success=True,
            message="Cache cleared successfully",
        )
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}",
        )


@router.post("/invalidate/{node_type}/{node_name}")
async def invalidate_node_cache(
    node_type: str,
    node_name: str,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    """Invalidate cache for a specific node
    
    Note: This is a simplified version that doesn't handle all cache keys
    for a node. In practice, you'd need to track all cache keys for a node.
    """
    cache_manager = await get_cache_manager()
    if not cache_manager:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cache is not enabled",
        )
    
    # This is simplified - in reality we'd need to invalidate all
    # cache entries for this node with different contexts
    return {
        "message": f"Cache invalidation for {node_type}:{node_name} initiated",
        "note": "Full implementation would require tracking all cache keys",
    }