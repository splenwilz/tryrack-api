"""
Image upload routes
Handles image uploads to S3 storage
"""
import logging
import time
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from botocore.exceptions import ClientError
from app.api.v1.schemas.auth import WorkOSUserResponse
from app.api.v1.schemas.storage import ImageUploadResponse, PresignedUploadResponse
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.services.storage import get_storage_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/images",
    tags=["images"],
)

@router.post(
    "/presigned-url",
    response_model=PresignedUploadResponse,
    summary="Get presigned URL for upload",
    description="Get a presigned URL that allows direct client-to-S3 upload. This bypasses the server for faster uploads.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Presigned URL generated successfully"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"}
    }
)
async def get_presigned_upload_url(
    folder: str = Form(
        default="images",
        description="S3 folder/path prefix (e.g., 'images', 'profile', 'wardrobe')"
    ),
    file_extension: str = Form(
        default="jpg",
        description="File extension (e.g., 'jpg', 'png')"
    ),
    expiration: int = Form(
        default=3600,
        ge=60,
        le=3600,
        description="URL expiration time in seconds (60-3600, default: 3600 = 1 hour)"
    ),
    current_user: WorkOSUserResponse = Depends(get_current_user)
) -> PresignedUploadResponse:
    """
    Generate a presigned URL for direct client-to-S3 image upload.
    
    **How it works:**
    1. Client calls this endpoint to get a presigned URL
    2. Client uploads directly to S3 using the presigned URL (PUT request)
    3. Client uses the returned `public_url` in profile/wardrobe creation
    
    **Benefits:**
    - Much faster uploads (bypasses server)
    - Reduces server load
    - Better scalability
    
    **Usage Example:**
    ```javascript
    // 1. Get presigned URL
    const response = await fetch('/api/v1/images/presigned-url', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer TOKEN' },
      body: new FormData({ folder: 'profile', file_extension: 'jpg' })
    });
    const { url, public_url } = await response.json();
    
    // 2. Upload directly to S3
    await fetch(url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': 'image/jpeg' }
    });
    
    // 3. Use public_url in your profile/wardrobe
    ```
    
    Args:
        folder: S3 folder/path prefix for organization
        file_extension: File extension (jpg, png, etc.)
        expiration: URL expiration time in seconds
        current_user: Authenticated user (from JWT token)
        
    Returns:
        PresignedUploadResponse with presigned URL and public URL
    """
    # Get singleton storage service (cached via lru_cache)
    storage_service = get_storage_service()
    
    try:
        # Generate presigned URL (synchronous, fast operation)
        result = storage_service.generate_presigned_upload_url(
            folder=folder,
            file_extension=file_extension,
            expiration=expiration
        )
        
        return PresignedUploadResponse(
            url=result["url"],
            key=result["key"],
            public_url=result["public_url"],
            expires_in=expiration
        )
        
    except ValueError as e:
        # ValueError indicates client-side validation issues (bad folder, invalid expiration, etc.)
        logger.warning(f"Presigned URL generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except ClientError as e:
        # ClientError indicates backend/S3 issues - map to HTTP 500
        logger.error(f"S3 error generating presigned URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate presigned URL due to a server error"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error generating presigned URL for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating presigned URL"
        ) from e

@router.post(
    "/upload",
    response_model=ImageUploadResponse,
    summary="Upload image",
    description="Upload an image file to S3. Returns the public URL that can be used in profile or wardrobe.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Image uploaded successfully"},
        400: {"description": "Invalid file format or size"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"}
    }
)
async def upload_image(
    file: UploadFile = File(..., description="Image file to upload (JPG only)"),
    folder: str = Form(
        default="images",
        description="S3 folder/path prefix (e.g., 'images', 'profile', 'wardrobe')"
    ),
    current_user: WorkOSUserResponse = Depends(get_current_user)
) -> ImageUploadResponse:
    """
    Upload an image file to S3 storage.
    
    **File Requirements:**
    - Format: JPG/JPEG only
    - Size: Max 5MB
    
    **Usage:**
    - Use the returned URL in profile creation/update (profile_picture_url, full_body_image_url)
    - Use for wardrobe item images
    - Folder parameter helps organize uploads (e.g., 'profile', 'wardrobe', 'outfits')
    
    Args:
        file: Image file to upload (multipart/form-data)
        folder: S3 folder/path prefix for organization
        current_user: Authenticated user (from JWT token)
        
    Returns:
        ImageUploadResponse with the public URL of the uploaded image
        
    Raises:
        HTTPException: 
            - 400 if file format is invalid or file is too large
            - 401 if not authenticated
            - 500 for upload failures
    """
    start_time = time.time()
    if settings.ENVIRONMENT == "development":
        print(f"[DEBUG] Image upload started at {start_time:.3f}")
    
    # Validate file type (JPG only)
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    # Check file extension
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ['.jpg', '.jpeg']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG/JPEG files are allowed"
        )
    
    validation_time = time.time()
    if settings.ENVIRONMENT == "development":
        print(f"[DEBUG] Validation took {(validation_time - start_time) * 1000:.2f}ms")
    
    # Validate file size (max 5MB for small files)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    read_start = time.time()
    file_content = await file.read()
    read_time = time.time()
    if settings.ENVIRONMENT == "development":
        print(f"[DEBUG] File read took {(read_time - read_start) * 1000:.2f}ms, size: {len(file_content)} bytes")
    
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
        )
    
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )
    
    before_service_time = time.time()
    if settings.ENVIRONMENT == "development":
        print(f"[DEBUG] Time before StorageService get: {(before_service_time - start_time) * 1000:.2f}ms")
    
    storage_service = get_storage_service()
    
    service_get_time = time.time()
    if settings.ENVIRONMENT == "development":
        print(f"[DEBUG] StorageService get took {(service_get_time - before_service_time) * 1000:.2f}ms")
    
    # Normalize extension: .jpeg -> jpeg, .jpg -> jpg (remove leading dot)
    normalized_extension = file_extension.lstrip('.')
    
    try:
        # Upload to S3 - pass content directly to avoid reading twice
        upload_start = time.time()
        if settings.ENVIRONMENT == "development":
            print(f"[DEBUG] Starting S3 upload at {upload_start:.3f}")
        url = await storage_service.upload_image(
            file_content=file_content,
            folder=folder,
            file_extension=normalized_extension
        )
        upload_end = time.time()
        upload_duration = (upload_end - upload_start) * 1000
        if settings.ENVIRONMENT == "development":
            print(f"[DEBUG] S3 upload completed in {upload_duration:.2f}ms")
        
        total_time = (upload_end - start_time) * 1000
        if settings.ENVIRONMENT == "development":
            print(f"[DEBUG] Total upload time: {total_time:.2f}ms")
        logger.info(f"Image uploaded successfully by user {current_user.id}: {url} (took {total_time:.2f}ms)")
        return ImageUploadResponse(url=url)
        
    except ValueError as e:
        # ValueError indicates client-side validation issues (empty file, invalid folder, etc.)
        logger.warning(f"Image upload validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except ClientError as e:
        # ClientError indicates backend/S3 issues - map to HTTP 500
        logger.error(f"S3 error uploading image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image due to a server error"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error uploading image for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while uploading the image"
        ) from e

