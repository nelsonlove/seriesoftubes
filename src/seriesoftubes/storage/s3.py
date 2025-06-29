"""S3/MinIO storage backend implementation."""

import io
from datetime import datetime
from typing import AsyncIterator, BinaryIO, Optional

import aioboto3
from botocore.exceptions import ClientError, NoCredentialsError

from .base import StorageBackend, StorageError, StorageFile


class S3StorageBackend(StorageBackend):
    """S3-compatible storage backend (works with AWS S3, MinIO, etc.)."""
    
    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: str = "seriesoftubes",
        region_name: str = "us-east-1",
        use_ssl: bool = True,
    ):
        """Initialize S3 storage backend.
        
        Args:
            endpoint_url: S3 endpoint URL (e.g., "http://localhost:9000" for MinIO)
            access_key_id: AWS access key ID
            secret_access_key: AWS secret access key
            bucket_name: S3 bucket name
            region_name: AWS region name
            use_ssl: Whether to use SSL for connections
        """
        self.endpoint_url = endpoint_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.use_ssl = use_ssl
        self._session = None
    
    @property
    def session(self):
        """Lazy-load boto3 session."""
        if self._session is None:
            self._session = aioboto3.Session(
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region_name,
            )
        return self._session
    
    def _get_client_config(self):
        """Get client configuration."""
        config = {
            "region_name": self.region_name,
            "use_ssl": self.use_ssl,
        }
        if self.endpoint_url:
            config["endpoint_url"] = self.endpoint_url
        return config
    
    async def initialize(self) -> None:
        """Create bucket if it doesn't exist."""
        try:
            async with self.session.client("s3", **self._get_client_config()) as s3:
                # Check if bucket exists
                try:
                    await s3.head_bucket(Bucket=self.bucket_name)
                except ClientError as e:
                    if e.response["Error"]["Code"] == "404":
                        # Create bucket
                        await s3.create_bucket(Bucket=self.bucket_name)
        except (ClientError, NoCredentialsError) as e:
            raise StorageError(f"Failed to initialize S3 storage: {e}")
    
    async def upload(
        self,
        key: str,
        content: bytes | BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> StorageFile:
        """Upload file to S3."""
        try:
            # Convert bytes to file-like object if needed
            if isinstance(content, bytes):
                content = io.BytesIO(content)
            
            # Prepare upload arguments
            upload_args = {
                "Bucket": self.bucket_name,
                "Key": key,
                "Body": content,
            }
            if content_type:
                upload_args["ContentType"] = content_type
            if metadata:
                upload_args["Metadata"] = metadata
            
            async with self.session.client("s3", **self._get_client_config()) as s3:
                response = await s3.put_object(**upload_args)
                
                # Get file info
                head_response = await s3.head_object(
                    Bucket=self.bucket_name, Key=key
                )
                
                return StorageFile(
                    key=key,
                    size=head_response["ContentLength"],
                    last_modified=head_response["LastModified"],
                    etag=response.get("ETag", "").strip('"'),
                    content_type=head_response.get("ContentType"),
                    metadata=head_response.get("Metadata"),
                )
        except (ClientError, NoCredentialsError) as e:
            raise StorageError(f"Failed to upload file: {e}")
    
    async def download(self, key: str) -> bytes:
        """Download file from S3."""
        try:
            async with self.session.client("s3", **self._get_client_config()) as s3:
                response = await s3.get_object(Bucket=self.bucket_name, Key=key)
                return await response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise StorageError(f"File not found: {key}")
            raise StorageError(f"Failed to download file: {e}")
    
    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file from S3."""
        try:
            async with self.session.client("s3", **self._get_client_config()) as s3:
                response = await s3.get_object(Bucket=self.bucket_name, Key=key)
                async for chunk in response["Body"].iter_chunks(chunk_size):
                    yield chunk
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise StorageError(f"File not found: {key}")
            raise StorageError(f"Failed to stream file: {e}")
    
    async def exists(self, key: str) -> bool:
        """Check if file exists in S3."""
        try:
            async with self.session.client("s3", **self._get_client_config()) as s3:
                await s3.head_object(Bucket=self.bucket_name, Key=key)
                return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise StorageError(f"Failed to check file existence: {e}")
    
    async def delete(self, key: str) -> None:
        """Delete file from S3."""
        try:
            async with self.session.client("s3", **self._get_client_config()) as s3:
                await s3.delete_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            raise StorageError(f"Failed to delete file: {e}")
    
    async def list(
        self,
        prefix: str = "",
        delimiter: Optional[str] = None,
        max_keys: int = 1000,
    ) -> list[StorageFile]:
        """List files in S3."""
        try:
            files = []
            async with self.session.client("s3", **self._get_client_config()) as s3:
                paginator = s3.get_paginator("list_objects_v2")
                
                page_args = {
                    "Bucket": self.bucket_name,
                    "MaxKeys": max_keys,
                }
                if prefix:
                    page_args["Prefix"] = prefix
                if delimiter:
                    page_args["Delimiter"] = delimiter
                
                async for page in paginator.paginate(**page_args):
                    for obj in page.get("Contents", []):
                        files.append(
                            StorageFile(
                                key=obj["Key"],
                                size=obj["Size"],
                                last_modified=obj["LastModified"],
                                etag=obj.get("ETag", "").strip('"'),
                            )
                        )
                        if len(files) >= max_keys:
                            break
                    if len(files) >= max_keys:
                        break
            
            return files
        except ClientError as e:
            raise StorageError(f"Failed to list files: {e}")
    
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate pre-signed URL for S3."""
        try:
            async with self.session.client("s3", **self._get_client_config()) as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expires_in,
                )
                return url
        except ClientError as e:
            raise StorageError(f"Failed to generate URL: {e}")
    
    async def copy(self, source_key: str, dest_key: str) -> StorageFile:
        """Copy file within S3."""
        try:
            async with self.session.client("s3", **self._get_client_config()) as s3:
                copy_source = {"Bucket": self.bucket_name, "Key": source_key}
                
                await s3.copy_object(
                    CopySource=copy_source,
                    Bucket=self.bucket_name,
                    Key=dest_key,
                )
                
                # Get file info
                head_response = await s3.head_object(
                    Bucket=self.bucket_name, Key=dest_key
                )
                
                return StorageFile(
                    key=dest_key,
                    size=head_response["ContentLength"],
                    last_modified=head_response["LastModified"],
                    etag=head_response.get("ETag", "").strip('"'),
                    content_type=head_response.get("ContentType"),
                    metadata=head_response.get("Metadata"),
                )
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise StorageError(f"Source file not found: {source_key}")
            raise StorageError(f"Failed to copy file: {e}")