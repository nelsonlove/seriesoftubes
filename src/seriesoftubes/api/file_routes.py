"""File management API routes."""

import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_db
from ..db.models import User
from ..storage import StorageError, get_storage_backend
from .models import SuccessResponse

router = APIRouter(prefix="/files", tags=["files"])


class FileUploadResponse(SuccessResponse):
    """Response for file upload."""
    file_id: str
    filename: str
    size: int
    content_type: Optional[str]
    upload_time: datetime


class FileInfo:
    """File information response."""
    file_id: str
    filename: str
    size: int
    content_type: Optional[str]
    last_modified: datetime
    is_public: bool = False


class FileListResponse(SuccessResponse):
    """Response for file list."""
    files: list[FileInfo]
    total: int


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    is_public: bool = Query(False, description="Make file publicly accessible"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file to storage.
    
    Files are stored in the user's private space by default.
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Generate file ID
    file_id = str(uuid.uuid4())
    
    # Determine storage path
    if is_public:
        storage_key = f"public/{file_id}/{file.filename}"
    else:
        storage_key = f"{current_user.id}/uploads/{file_id}/{file.filename}"
    
    try:
        # Get storage backend
        storage = get_storage_backend()
        await storage.initialize()
        
        # Read file content
        content = await file.read()
        
        # Upload to storage
        stored_file = await storage.upload(
            key=storage_key,
            content=content,
            content_type=file.content_type,
            metadata={
                "user_id": current_user.id,
                "original_filename": file.filename,
                "upload_time": datetime.utcnow().isoformat(),
            }
        )
        
        return FileUploadResponse(
            success=True,
            message="File uploaded successfully",
            file_id=file_id,
            filename=file.filename,
            size=stored_file.size,
            content_type=file.content_type,
            upload_time=datetime.utcnow(),
        )
        
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a file from storage.
    
    Users can only download their own files or public files.
    """
    try:
        storage = get_storage_backend()
        await storage.initialize()
        
        # Try user's private files first
        private_key = f"{current_user.id}/uploads/{file_id}/"
        files = await storage.list(prefix=private_key, max_keys=1)
        
        if files:
            file_info = files[0]
            content = await storage.download(file_info.key)
            filename = os.path.basename(file_info.key)
            
            return StreamingResponse(
                io.BytesIO(content),
                media_type=file_info.content_type or "application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
        
        # Try public files
        public_key = f"public/{file_id}/"
        files = await storage.list(prefix=public_key, max_keys=1)
        
        if files:
            file_info = files[0]
            content = await storage.download(file_info.key)
            filename = os.path.basename(file_info.key)
            
            return StreamingResponse(
                io.BytesIO(content),
                media_type=file_info.content_type or "application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
        
        raise HTTPException(status_code=404, detail="File not found")
        
    except HTTPException:
        raise
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/{file_id}/url")
async def get_file_url(
    file_id: str,
    expires_in: int = Query(3600, description="URL expiration time in seconds"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a pre-signed URL for direct file access.
    
    This is useful for large files or when you want to serve files directly
    from storage without proxying through the API.
    """
    try:
        storage = get_storage_backend()
        await storage.initialize()
        
        # Try user's private files first
        private_key = f"{current_user.id}/uploads/{file_id}/"
        files = await storage.list(prefix=private_key, max_keys=1)
        
        if files:
            url = await storage.get_url(files[0].key, expires_in=expires_in)
            return {"url": url, "expires_in": expires_in}
        
        # Try public files
        public_key = f"public/{file_id}/"
        files = await storage.list(prefix=public_key, max_keys=1)
        
        if files:
            url = await storage.get_url(files[0].key, expires_in=expires_in)
            return {"url": url, "expires_in": expires_in}
        
        raise HTTPException(status_code=404, detail="File not found")
        
    except HTTPException:
        raise
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate URL: {str(e)}")


@router.get("", response_model=FileListResponse)
async def list_files(
    prefix: str = Query("", description="Filter files by prefix"),
    limit: int = Query(100, le=1000, description="Maximum files to return"),
    include_public: bool = Query(False, description="Include public files"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's uploaded files."""
    try:
        storage = get_storage_backend()
        await storage.initialize()
        
        all_files = []
        
        # List user's private files
        user_prefix = f"{current_user.id}/uploads/{prefix}"
        private_files = await storage.list(prefix=user_prefix, max_keys=limit)
        
        for f in private_files:
            # Extract file_id from key
            parts = f.key.split("/")
            if len(parts) >= 4:  # user_id/uploads/file_id/filename
                file_id = parts[2]
                filename = "/".join(parts[3:])
                
                all_files.append(FileInfo(
                    file_id=file_id,
                    filename=filename,
                    size=f.size,
                    content_type=f.content_type,
                    last_modified=f.last_modified,
                    is_public=False,
                ))
        
        # List public files if requested
        if include_public and len(all_files) < limit:
            public_prefix = f"public/{prefix}"
            public_files = await storage.list(
                prefix=public_prefix, 
                max_keys=limit - len(all_files)
            )
            
            for f in public_files:
                # Extract file_id from key
                parts = f.key.split("/")
                if len(parts) >= 3:  # public/file_id/filename
                    file_id = parts[1]
                    filename = "/".join(parts[2:])
                    
                    all_files.append(FileInfo(
                        file_id=file_id,
                        filename=filename,
                        size=f.size,
                        content_type=f.content_type,
                        last_modified=f.last_modified,
                        is_public=True,
                    ))
        
        return FileListResponse(
            success=True,
            message=f"Found {len(all_files)} files",
            files=all_files,
            total=len(all_files),
        )
        
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a file from storage.
    
    Users can only delete their own files.
    """
    try:
        storage = get_storage_backend()
        await storage.initialize()
        
        # Only check user's private files
        private_key = f"{current_user.id}/uploads/{file_id}/"
        files = await storage.list(prefix=private_key, max_keys=10)  # Handle multiple files
        
        if not files:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Delete all files with this file_id
        for f in files:
            await storage.delete(f.key)
        
        return SuccessResponse(
            success=True,
            message=f"Deleted {len(files)} file(s)"
        )
        
    except HTTPException:
        raise
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# Add this for the missing import
import io