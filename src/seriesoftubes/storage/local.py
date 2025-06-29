"""Local filesystem storage backend implementation."""

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, BinaryIO, Optional
from urllib.parse import quote, unquote

from .base import StorageBackend, StorageError, StorageFile


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend for development/testing."""
    
    def __init__(self, base_path: str = "/tmp/seriesoftubes-storage"):
        """Initialize local storage backend.
        
        Args:
            base_path: Base directory for storing files
        """
        self.base_path = Path(base_path)
    
    def _get_full_path(self, key: str) -> Path:
        """Get full filesystem path for a key."""
        # Remove leading slash if present
        clean_key = key.lstrip("/")
        return self.base_path / clean_key
    
    async def initialize(self) -> None:
        """Create base directory if it doesn't exist."""
        try:
            await asyncio.to_thread(self.base_path.mkdir, parents=True, exist_ok=True)
        except Exception as e:
            raise StorageError(f"Failed to initialize local storage: {e}")
    
    async def upload(
        self,
        key: str,
        content: bytes | BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> StorageFile:
        """Upload file to local filesystem."""
        try:
            file_path = self._get_full_path(key)
            
            # Create parent directories
            await asyncio.to_thread(file_path.parent.mkdir, parents=True, exist_ok=True)
            
            # Write content
            if isinstance(content, bytes):
                await asyncio.to_thread(file_path.write_bytes, content)
                size = len(content)
            else:
                # Handle file-like objects
                def write_file():
                    with open(file_path, "wb") as f:
                        shutil.copyfileobj(content, f)
                    return file_path.stat().st_size
                
                size = await asyncio.to_thread(write_file)
            
            # Store metadata if provided
            if content_type or metadata:
                meta_path = file_path.with_suffix(file_path.suffix + ".meta")
                meta_content = {}
                if content_type:
                    meta_content["content_type"] = content_type
                if metadata:
                    meta_content["metadata"] = metadata
                
                import json
                await asyncio.to_thread(
                    meta_path.write_text, json.dumps(meta_content)
                )
            
            stat = await asyncio.to_thread(file_path.stat)
            
            return StorageFile(
                key=key,
                size=size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                content_type=content_type,
                metadata=metadata,
            )
        except Exception as e:
            raise StorageError(f"Failed to upload file: {e}")
    
    async def download(self, key: str) -> bytes:
        """Download file from local filesystem."""
        try:
            file_path = self._get_full_path(key)
            if not await asyncio.to_thread(file_path.exists):
                raise StorageError(f"File not found: {key}")
            
            return await asyncio.to_thread(file_path.read_bytes)
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to download file: {e}")
    
    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file from local filesystem."""
        file_path = self._get_full_path(key)
        if not await asyncio.to_thread(file_path.exists):
            raise StorageError(f"File not found: {key}")
        
        try:
            def read_chunks():
                with open(file_path, "rb") as f:
                    while chunk := f.read(chunk_size):
                        yield chunk
            
            for chunk in await asyncio.to_thread(list, read_chunks()):
                yield chunk
        except Exception as e:
            raise StorageError(f"Failed to stream file: {e}")
    
    async def exists(self, key: str) -> bool:
        """Check if file exists in local filesystem."""
        try:
            file_path = self._get_full_path(key)
            return await asyncio.to_thread(file_path.exists)
        except Exception as e:
            raise StorageError(f"Failed to check file existence: {e}")
    
    async def delete(self, key: str) -> None:
        """Delete file from local filesystem."""
        try:
            file_path = self._get_full_path(key)
            if await asyncio.to_thread(file_path.exists):
                await asyncio.to_thread(file_path.unlink)
                
                # Also delete metadata file if it exists
                meta_path = file_path.with_suffix(file_path.suffix + ".meta")
                if await asyncio.to_thread(meta_path.exists):
                    await asyncio.to_thread(meta_path.unlink)
        except Exception as e:
            raise StorageError(f"Failed to delete file: {e}")
    
    async def list(
        self,
        prefix: str = "",
        delimiter: Optional[str] = None,
        max_keys: int = 1000,
    ) -> list[StorageFile]:
        """List files in local filesystem."""
        try:
            files = []
            search_path = self._get_full_path(prefix) if prefix else self.base_path
            
            if not await asyncio.to_thread(search_path.exists):
                return files
            
            # If delimiter is provided, only list immediate children
            if delimiter and delimiter == "/":
                pattern = "*"
                recursive = False
            else:
                pattern = "**/*"
                recursive = True
            
            def collect_files():
                nonlocal files
                for path in search_path.glob(pattern) if recursive else search_path.iterdir():
                    if path.is_file() and not path.name.endswith(".meta"):
                        # Get relative path from base
                        rel_path = path.relative_to(self.base_path)
                        key = str(rel_path)
                        
                        # Skip if doesn't match prefix
                        if prefix and not key.startswith(prefix):
                            continue
                        
                        stat = path.stat()
                        
                        # Load metadata if exists
                        meta_path = path.with_suffix(path.suffix + ".meta")
                        content_type = None
                        metadata = None
                        
                        if meta_path.exists():
                            import json
                            meta_content = json.loads(meta_path.read_text())
                            content_type = meta_content.get("content_type")
                            metadata = meta_content.get("metadata")
                        
                        files.append(
                            StorageFile(
                                key=key,
                                size=stat.st_size,
                                last_modified=datetime.fromtimestamp(stat.st_mtime),
                                content_type=content_type,
                                metadata=metadata,
                            )
                        )
                        
                        if len(files) >= max_keys:
                            break
            
            await asyncio.to_thread(collect_files)
            return files
        except Exception as e:
            raise StorageError(f"Failed to list files: {e}")
    
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate file:// URL for local filesystem."""
        file_path = self._get_full_path(key)
        if not await asyncio.to_thread(file_path.exists):
            raise StorageError(f"File not found: {key}")
        
        # Return file:// URL
        return f"file://{quote(str(file_path.absolute()))}"
    
    async def copy(self, source_key: str, dest_key: str) -> StorageFile:
        """Copy file within local filesystem."""
        try:
            source_path = self._get_full_path(source_key)
            if not await asyncio.to_thread(source_path.exists):
                raise StorageError(f"Source file not found: {source_key}")
            
            dest_path = self._get_full_path(dest_key)
            
            # Create parent directories
            await asyncio.to_thread(
                dest_path.parent.mkdir, parents=True, exist_ok=True
            )
            
            # Copy file
            await asyncio.to_thread(shutil.copy2, source_path, dest_path)
            
            # Copy metadata if exists
            source_meta = source_path.with_suffix(source_path.suffix + ".meta")
            if await asyncio.to_thread(source_meta.exists):
                dest_meta = dest_path.with_suffix(dest_path.suffix + ".meta")
                await asyncio.to_thread(shutil.copy2, source_meta, dest_meta)
            
            # Get file info
            stat = await asyncio.to_thread(dest_path.stat)
            
            # Load metadata
            meta_path = dest_path.with_suffix(dest_path.suffix + ".meta")
            content_type = None
            metadata = None
            
            if await asyncio.to_thread(meta_path.exists):
                import json
                meta_content = json.loads(
                    await asyncio.to_thread(meta_path.read_text)
                )
                content_type = meta_content.get("content_type")
                metadata = meta_content.get("metadata")
            
            return StorageFile(
                key=dest_key,
                size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                content_type=content_type,
                metadata=metadata,
            )
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to copy file: {e}")