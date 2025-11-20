"""
Storage service for handling file uploads to S3
Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html
"""
import asyncio
import io
import logging
import time
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO, Union, Dict, Any
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def get_storage_service() -> 'StorageService':
    """
    Get a singleton StorageService instance.
    
    Using lru_cache ensures the same StorageService instance is reused across requests,
    avoiding repeated boto3 client initialization and improving performance.
    
    Reference: https://docs.python.org/3/library/functools.html#functools.lru_cache
    """
    return StorageService()


class StorageService:
    """Service for handling file uploads to AWS S3"""
    
    def __init__(self):
        """Initialize S3 client with credentials from settings"""
        # Optimize boto3 config for better performance
        # Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html
        config = Config(
            max_pool_connections=50,  # Connection pooling for better performance
            retries={
                'max_attempts': 3,
                'mode': 'standard'
            },
            connect_timeout=5,  # Reduced from 10s for faster failure
            read_timeout=10  # Reduced from 30s for faster failure
        )
        
        # Initialize S3 client (reused across requests via singleton)
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            config=config
        )
        
        self.bucket_name = settings.AWS_S3_BUCKET_NAME
        # Pre-compute base URL to avoid string operations on every request
        self.base_url = settings.AWS_S3_BASE_URL or self._generate_base_url()
    
    def _generate_base_url(self) -> str:
        """Generate S3 base URL from bucket name and region"""
        # Standard S3 URL format: https://bucket-name.s3.region.amazonaws.com
        return f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com"
    
    async def upload_image(
        self,
        file_content: Union[bytes, BinaryIO],
        folder: str = "images",
        file_extension: str = "jpg"
    ) -> str:
        """
        Upload an image file to S3 and return the public URL.
        
        Args:
            file_content: File content as bytes or file-like object
            folder: S3 folder/path prefix (e.g., "images", "profile", "wardrobe")
            file_extension: File extension (default: "jpg")
            
        Returns:
            Public URL of the uploaded file
            
        Raises:
            ValueError: If file is invalid
            ClientError: If S3 upload fails
        """
        method_start = time.time()
        if settings.ENVIRONMENT == "development":
            print(f"[DEBUG] upload_image method started at {method_start:.3f}")
        
        # Generate unique filename: timestamp + UUID + extension
        filename_start = time.time()
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{timestamp}_{unique_id}.{file_extension}"
        s3_key = f"{folder}/{filename}"
        filename_time = time.time()
        if settings.ENVIRONMENT == "development":
            print(f"[DEBUG] Filename generation took {(filename_time - filename_start) * 1000:.2f}ms")
        
        # Convert to bytes if it's a file-like object
        convert_start = time.time()
        was_file_like = hasattr(file_content, 'read')
        if was_file_like:
            file_content = file_content.read()
        convert_time = time.time()
        if was_file_like and settings.ENVIRONMENT == "development":
            print(f"[DEBUG] File conversion took {(convert_time - convert_start) * 1000:.2f}ms")
        
        if not file_content:
            raise ValueError("File is empty")
        
        file_size = len(file_content)
        if settings.ENVIRONMENT == "development":
            print(f"[DEBUG] File size: {file_size} bytes ({file_size / 1024:.2f} KB)")
        
        # Upload to S3 (offload sync boto3 call to thread pool)
        # Using put_object with bytes - faster for small files (<5MB) than upload_fileobj
        # Note: ACL parameter removed - modern S3 buckets often have ACLs disabled
        # Bucket policy should be configured for public read access instead
        # Note: put_object is synchronous and returns when upload completes (no need for wait_until_exists)
        try:
            s3_start = time.time()
            if settings.ENVIRONMENT == "development":
                print(f"[DEBUG] Starting S3 put_object call at {s3_start:.3f}")
                print(f"[DEBUG] Bucket: {self.bucket_name}, Key: {s3_key}, Region: {settings.AWS_REGION}")
                print(f"[DEBUG] File size: {len(file_content)} bytes")
                print(f"[DEBUG] S3 client endpoint: {self.s3_client.meta.endpoint_url if hasattr(self.s3_client.meta, 'endpoint_url') else 'default'}")
                
                # Add timeout and connection debugging
                import socket
                print(f"[DEBUG] Testing DNS resolution for {self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com")
                try:
                    dns_start = time.time()
                    socket.gethostbyname(f"{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com")
                    dns_time = (time.time() - dns_start) * 1000
                    print(f"[DEBUG] DNS resolution took {dns_time:.2f}ms")
                except Exception as dns_e:
                    print(f"[DEBUG] DNS resolution failed: {dns_e}")
            
            # Wrap the S3 call with detailed timing
            def s3_upload_wrapper():
                upload_start = time.time()
                if settings.ENVIRONMENT == "development":
                    print(f"[DEBUG] [THREAD] S3 put_object starting in thread at {upload_start:.3f}")
                try:
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        Body=file_content,
                        ContentType=f"image/{file_extension}"
                    )
                    upload_end = time.time()
                    if settings.ENVIRONMENT == "development":
                        print(f"[DEBUG] [THREAD] S3 put_object completed in {(upload_end - upload_start) * 1000:.2f}ms")
                except Exception as e:
                    upload_end = time.time()
                    if settings.ENVIRONMENT == "development":
                        print(f"[DEBUG] [THREAD] S3 put_object failed after {(upload_end - upload_start) * 1000:.2f}ms: {e}")
                    raise
            
            await asyncio.to_thread(s3_upload_wrapper)
            
            s3_end = time.time()
            s3_duration = (s3_end - s3_start) * 1000
            if settings.ENVIRONMENT == "development":
                print(f"[DEBUG] S3 put_object call completed in {s3_duration:.2f}ms")
            
            # Construct and return public URL
            url = f"{self.base_url}/{s3_key}"
            method_end = time.time()
            method_duration = (method_end - method_start) * 1000
            if settings.ENVIRONMENT == "development":
                print(f"[DEBUG] Total upload_image method time: {method_duration:.2f}ms")
            logger.info(
                "Put object '%s' to bucket '%s' (%d bytes) in %.2fms.",
                s3_key,
                self.bucket_name,
                len(file_content),
                s3_duration
            )
            return url
            
        except ClientError as e:
            # Don't convert ClientError to ValueError - let it bubble up as 500 error
            # ClientError indicates backend/S3 issues (misconfigured credentials, network, etc.)
            # These should be HTTP 500, not HTTP 400 (client error)
            logger.exception(
                "Couldn't put object '%s' to bucket '%s'.",
                s3_key,
                self.bucket_name
            )
            raise  # Re-raise ClientError so route can map to HTTP 500
    
    def generate_presigned_upload_url(
        self,
        folder: str = "images",
        file_extension: str = "jpg",
        expiration: int = 3600
    ) -> Dict[str, Any]:
        """
        Generate a presigned URL for direct client-to-S3 upload.
        
        This allows clients to upload directly to S3 without going through the server,
        which is much faster and reduces server load.
        
        Args:
            folder: S3 folder/path prefix (e.g., "images", "profile", "wardrobe")
            file_extension: File extension (default: "jpg")
            expiration: URL expiration time in seconds (default: 3600 = 1 hour)
            
        Returns:
            Dictionary with:
                - url: Presigned URL for PUT request
                - key: S3 key (path) where the file will be stored
                - public_url: Public URL to access the file after upload
        """
        # Generate unique filename: timestamp + UUID + extension
        # Optimized: use uuid4().hex[:8] instead of str(uuid.uuid4())[:8] for faster string conversion
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        unique_id = uuid.uuid4().hex[:8]
        s3_key = f"{folder}/{timestamp}_{unique_id}.{file_extension}"
        
        try:
            # Generate presigned URL for PUT operation (synchronous, no network call)
            # Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/generate_presigned_url.html
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key,
                    'ContentType': f"image/{file_extension.lstrip('.')}"
                },
                ExpiresIn=expiration
            )
            
            # Construct public URL (for accessing the file after upload)
            public_url = f"{self.base_url}/{s3_key}"
            
            return {
                "url": presigned_url,
                "key": s3_key,
                "public_url": public_url
            }
            
        except ClientError as e:
            # Don't convert ClientError to ValueError - let it bubble up as 500 error
            # ClientError indicates backend/S3 issues (misconfigured credentials, network, etc.)
            # These should be HTTP 500, not HTTP 400 (client error)
            logger.error(f"Failed to generate presigned URL: {e}", exc_info=True)
            raise  # Re-raise ClientError so route can map to HTTP 500
    
    async def delete_image(self, url: str) -> bool:
        """
        Delete an image from S3 by URL.
        
        Args:
            url: Full S3 URL of the image to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Extract S3 key from URL
            # URL format: https://bucket.s3.region.amazonaws.com/folder/filename.jpg
            if self.base_url not in url:
                logger.warning(f"URL does not match base URL: {url}")
                return False
            
            s3_key = url.replace(f"{self.base_url}/", "")
            
            # Delete from S3
            await asyncio.to_thread(
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"Successfully deleted image from S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete image from S3: {e}", exc_info=True)
            return False

