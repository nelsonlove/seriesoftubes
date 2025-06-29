"""Base storage backend interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, BinaryIO, Optional


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


@dataclass
class StorageFile:
    """Metadata about a stored file."""
    key: str
    size: int
    last_modified: datetime
    etag: Optional[str] = None
    content_type: Optional[str] = None
    metadata: Optional[dict[str, str]] = None


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage backend (e.g., create buckets)."""
        pass
    
    @abstractmethod
    async def upload(
        self, 
        key: str, 
        content: bytes | BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None
    ) -> StorageFile:
        """Upload a file to storage.
        
        Args:
            key: The storage key/path for the file
            content: File content as bytes or file-like object
            content_type: MIME type of the content
            metadata: Additional metadata to store with the file
            
        Returns:
            StorageFile with upload details
            
        Raises:
            StorageError: If upload fails
        """
        pass
    
    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download a file from storage.
        
        Args:
            key: The storage key/path for the file
            
        Returns:
            File content as bytes
            
        Raises:
            StorageError: If download fails or file not found
        """
        pass
    
    @abstractmethod
    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream a file from storage in chunks.
        
        Args:
            key: The storage key/path for the file
            chunk_size: Size of each chunk in bytes
            
        Yields:
            Chunks of file content
            
        Raises:
            StorageError: If streaming fails or file not found
        """
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a file exists in storage.
        
        Args:
            key: The storage key/path to check
            
        Returns:
            True if file exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a file from storage.
        
        Args:
            key: The storage key/path to delete
            
        Raises:
            StorageError: If deletion fails
        """
        pass
    
    @abstractmethod
    async def list(
        self, 
        prefix: str = "", 
        delimiter: Optional[str] = None,
        max_keys: int = 1000
    ) -> list[StorageFile]:
        """List files in storage.
        
        Args:
            prefix: Filter results to keys starting with this prefix
            delimiter: Group results by this delimiter (e.g., "/" for directories)
            max_keys: Maximum number of results to return
            
        Returns:
            List of StorageFile objects
            
        Raises:
            StorageError: If listing fails
        """
        pass
    
    @abstractmethod
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed URL for file access.
        
        Args:
            key: The storage key/path
            expires_in: URL expiration time in seconds
            
        Returns:
            Pre-signed URL
            
        Raises:
            StorageError: If URL generation fails
        """
        pass
    
    @abstractmethod
    async def copy(self, source_key: str, dest_key: str) -> StorageFile:
        """Copy a file within storage.
        
        Args:
            source_key: Source file key
            dest_key: Destination file key
            
        Returns:
            StorageFile for the copied file
            
        Raises:
            StorageError: If copy fails
        """
        pass