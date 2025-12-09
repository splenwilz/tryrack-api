"""
Schemas for unified reviews (products and boutiques).

Reference: https://fastapi.tiangolo.com/tutorial/body/
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.v1.schemas.auth import WorkOSUserResponse
from app.models.review import ReviewItemType

# Verification types in order of trust (lower number = higher trust)
VerificationType = Literal["purchase", "try_on", "email_profile", "email"]


class ReviewBase(BaseModel):
    """Base schema with common review fields."""

    rating: int = Field(..., ge=1, le=5, description="Rating value (1-5 stars)")
    comment: Optional[str] = Field(None, description="Review comment/text")
    images: Optional[List[str]] = Field(
        None, description="Array of image URLs associated with the review"
    )
    review_metadata: Optional[dict] = Field(
        None,
        description="Additional review metadata (product/boutique details, image_count, review_length, submitted_at, etc.)",
    )
    is_approved: bool = Field(
        False,
        description="Whether the review has been approved by an admin (defaults to False for moderation)",
    )

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate image URLs."""
        if v is not None:
            if len(v) > 10:
                raise ValueError("Maximum 10 images allowed per review")
            for img_url in v:
                if not img_url.startswith(("http://", "https://")):
                    raise ValueError(f"Invalid image URL: {img_url}")
        return v


class ReviewCreate(ReviewBase):
    """
    Schema for creating a new review.

    Attributes:
        item_type: Type of item being reviewed ("product" or "boutique")
        item_id: ID of the item being reviewed (catalog_item_id or boutique_id as string)
        rating: Rating value (1-5, required)
        comment: Review comment/text (optional)
        images: Array of image URLs (optional, max 10)
        review_metadata: Additional metadata (optional)
    """

    item_type: Literal["product", "boutique"] = Field(
        ..., description="Type of item being reviewed: 'product' (catalog item) or 'boutique'"
    )
    item_id: str = Field(..., min_length=1, max_length=50, description="ID of the item being reviewed")

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        """Validate item_type matches enum values."""
        if v not in ["product", "boutique"]:
            raise ValueError("item_type must be 'product' or 'boutique'")
        return v


class ReviewUpdate(BaseModel):
    """
    Schema for updating a review.

    All fields are optional for partial updates.
    """

    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating value (1-5 stars)")
    comment: Optional[str] = Field(None, description="Review comment/text")
    images: Optional[List[str]] = Field(
        None, description="Array of image URLs associated with the review"
    )
    review_metadata: Optional[dict] = Field(
        None, description="Additional review metadata"
    )
    is_approved: Optional[bool] = Field(
        None, description="Whether the review has been approved by an admin (admin only)"
    )

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate image URLs."""
        if v is not None:
            if len(v) > 10:
                raise ValueError("Maximum 10 images allowed per review")
            for img_url in v:
                if not img_url.startswith(("http://", "https://")):
                    raise ValueError(f"Invalid image URL: {img_url}")
        return v


class ReviewResponse(ReviewBase):
    """
    Schema for review response.

    Includes all review fields plus ID, item_type, item_id, user_id, user object,
    verification status, is_approved, and timestamps.
    """

    id: int = Field(..., description="Review ID")
    item_type: str = Field(..., description="Type of item reviewed: 'product' or 'boutique'")
    item_id: str = Field(..., description="ID of the item reviewed")
    user_id: str = Field(..., description="User ID of the reviewer")
    user: Optional[WorkOSUserResponse] = Field(
        None, description="User information of the reviewer (from WorkOS)"
    )
    is_verified: bool = Field(
        False,
        description="Whether the reviewer is verified (via purchase, try-on, or email)"
    )
    verification_type: Optional[VerificationType] = Field(
        None,
        description="Type of verification: 'purchase' (highest trust), 'try_on', 'email_profile', or 'email' (lowest trust)"
    )
    verification_level: int = Field(
        0,
        ge=0,
        le=3,
        description="Verification level: 0=purchase (highest), 1=try_on, 2=email_profile, 3=email (lowest). Lower number = higher trust."
    )
    like_count: int = Field(
        0,
        ge=0,
        description="Number of users who found this review helpful"
    )
    user_has_liked: bool = Field(
        False,
        description="Whether the current user has liked this review (only included when authenticated)"
    )
    is_approved: bool = Field(..., description="Whether the review has been approved by an admin")
    created_at: datetime = Field(..., description="Timestamp when review was created")
    updated_at: datetime = Field(..., description="Timestamp when review was last updated")

    model_config = ConfigDict(from_attributes=True)

