"""
Wardrobe item schemas for request/response validation
Reference: https://fastapi.tiangolo.com/tutorial/body/
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.wardrobe import ItemStatus


class WardrobeBase(BaseModel):
    """Base schema with common Wardrobe fields"""
    title: str = Field(..., min_length=1, max_length=200, description="Item title/name")
    category: str = Field(..., min_length=1, max_length=50, description="Item category (e.g., 'shirt', 'pants', 'dress')")
    colors: list[str] = Field(..., min_items=1, description="List of colors (e.g., ['burgundy', 'olive green', 'black'])")
    image_url: str = Field(..., max_length=500, description="URL to item image")
    tags: Optional[list[str]] = Field(
        None,
        description="List of tags for filtering/searching (e.g., ['short sleeve', 'geometric', 'casual', 'summer', 'silk'])"
    )
    status: Optional[ItemStatus] = Field(
        None,
        description="Current item status (clean, worn, dirty)"
    )


class WardrobeCreate(WardrobeBase):
    """
    Schema for creating a new wardrobe item.
    
    Users can only create items for themselves (user_id is set from authenticated user).
    
    Attributes:
        title: Item title/name (required)
        category: Item category (required)
        colors: List of colors (required, at least one)
        image_url: URL to item image (required)
        tags: Optional list of tags for filtering/searching
        status: Optional item status (defaults to CLEAN if not provided)
    """
    @field_validator('colors')
    @classmethod
    def validate_colors(cls, v: list[str]) -> list[str]:
        """Validate that colors list is not empty"""
        if not v:
            raise ValueError("At least one color must be provided")
        return v


class WardrobeUpdate(BaseModel):
    """
    Schema for updating a wardrobe item.
    
    All fields are optional for partial updates.
    
    Attributes:
        title: Item title/name
        category: Item category
        colors: List of colors
        image_url: URL to item image
        tags: List of tags for filtering/searching
        status: Current item status
    """
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Item title/name")
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="Item category")
    colors: Optional[list[str]] = Field(None, min_items=1, description="List of colors")
    image_url: Optional[str] = Field(None, max_length=500, description="URL to item image")
    tags: Optional[list[str]] = Field(None, description="List of tags for filtering/searching")
    status: Optional[ItemStatus] = Field(None, description="Current item status")
    last_worn_at: Optional[datetime] = Field(None, description="Timestamp when item was last worn")
    wear_count: Optional[int] = Field(None, ge=0, description="Number of times item has been worn")
    
    @field_validator('colors')
    @classmethod
    def validate_colors(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate that colors list is not empty if provided"""
        if v is not None and not v:
            raise ValueError("Colors list cannot be empty if provided")
        return v


class WardrobeResponse(WardrobeBase):
    """
    Schema for wardrobe item response.
    
    Includes all fields from WardrobeBase plus database-generated fields.
    
    Attributes:
        id: Item ID
        user_id: User ID who owns this item
        title: Item title/name
        category: Item category
        colors: List of colors
        image_url: URL to item image
        tags: List of tags
        status: Current item status
        last_worn_at: Timestamp when item was last worn
        wear_count: Number of times item has been worn
        created_at: Timestamp when item was created
        updated_at: Timestamp when item was last updated
    """
    id: int = Field(..., description="Item ID")
    user_id: str = Field(..., description="User ID who owns this item")
    last_worn_at: Optional[datetime] = Field(None, description="Timestamp when item was last worn")
    wear_count: int = Field(..., ge=0, description="Number of times item has been worn")
    created_at: datetime = Field(..., description="Timestamp when item was created")
    updated_at: datetime = Field(..., description="Timestamp when item was last updated")
    
    model_config = ConfigDict(from_attributes=True)

