"""
Storage schemas for image upload responses
"""
from pydantic import BaseModel, Field


class ImageUploadResponse(BaseModel):
    """
    Response schema for image upload endpoint
    
    Attributes:
        url: Public URL of the uploaded image
        message: Success message
    """
    url: str = Field(..., description="Public URL of the uploaded image")
    message: str = Field(default="Image uploaded successfully", description="Upload status message")
    
    model_config = {"json_schema_extra": {"example": {"url": "https://bucket.s3.amazonaws.com/images/20241119_abc123.jpg", "message": "Image uploaded successfully"}}}


class PresignedUploadResponse(BaseModel):
    """
    Response schema for presigned URL endpoint
    
    Allows clients to upload directly to S3 without going through the server.
    """
    url: str = Field(..., description="Presigned URL for PUT request (use this to upload directly to S3)")
    key: str = Field(..., description="S3 key/path where the file will be stored")
    public_url: str = Field(..., description="Public URL to access the file after upload")
    expires_in: int = Field(..., description="URL expiration time in seconds")
    
    model_config = {"json_schema_extra": {
        "example": {
            "url": "https://bucket.s3.amazonaws.com/images/20241119_abc123.jpg?X-Amz-Algorithm=...",
            "key": "images/20241119_abc123.jpg",
            "public_url": "https://bucket.s3.amazonaws.com/images/20241119_abc123.jpg",
            "expires_in": 3600
        }
    }}

