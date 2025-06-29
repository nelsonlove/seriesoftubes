"""Storage backend factory."""

import os
from typing import Optional

from .base import StorageBackend
from .local import LocalStorageBackend
from .s3 import S3StorageBackend


def get_storage_backend(
    backend_type: Optional[str] = None,
    **kwargs
) -> StorageBackend:
    """Get a storage backend instance.
    
    Args:
        backend_type: Type of backend ("s3", "local", or None for auto-detect)
        **kwargs: Backend-specific configuration
        
    Returns:
        StorageBackend instance
        
    Raises:
        ValueError: If backend type is invalid
    """
    # Auto-detect based on environment if not specified
    if backend_type is None:
        if os.getenv("MINIO_ENDPOINT") or os.getenv("AWS_ENDPOINT_URL"):
            backend_type = "s3"
        else:
            backend_type = "local"
    
    if backend_type == "s3":
        # Get configuration from environment or kwargs
        config = {
            "endpoint_url": kwargs.get("endpoint_url") or os.getenv("MINIO_ENDPOINT") or os.getenv("AWS_ENDPOINT_URL"),
            "access_key_id": kwargs.get("access_key_id") or os.getenv("MINIO_ACCESS_KEY") or os.getenv("AWS_ACCESS_KEY_ID"),
            "secret_access_key": kwargs.get("secret_access_key") or os.getenv("MINIO_SECRET_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY"),
            "bucket_name": kwargs.get("bucket_name") or os.getenv("MINIO_BUCKET") or os.getenv("S3_BUCKET") or "seriesoftubes",
            "region_name": kwargs.get("region_name") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1",
            "use_ssl": kwargs.get("use_ssl", os.getenv("MINIO_SECURE", "true").lower() == "true"),
        }
        
        # For MinIO, prepend http:// if no protocol specified
        if config["endpoint_url"] and not config["endpoint_url"].startswith(("http://", "https://")):
            protocol = "https://" if config["use_ssl"] else "http://"
            config["endpoint_url"] = protocol + config["endpoint_url"]
        
        return S3StorageBackend(**config)
    
    elif backend_type == "local":
        base_path = kwargs.get("base_path") or os.getenv("STORAGE_PATH") or "/tmp/seriesoftubes-storage"
        return LocalStorageBackend(base_path=base_path)
    
    else:
        raise ValueError(f"Invalid storage backend type: {backend_type}")