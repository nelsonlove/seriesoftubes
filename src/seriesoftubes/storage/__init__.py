"""Storage backend abstraction for SeriesOfTubes."""

from .base import StorageBackend, StorageError, StorageFile
from .factory import get_storage_backend
from .local import LocalStorageBackend
from .s3 import S3StorageBackend

__all__ = [
    "StorageBackend",
    "StorageError",
    "StorageFile",
    "get_storage_backend",
    "LocalStorageBackend",
    "S3StorageBackend",
]