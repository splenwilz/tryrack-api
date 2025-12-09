"""
Schemas for Boutique Look API - styled combinations of catalog items.

Reference: https://fastapi.tiangolo.com/tutorial/body/
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.v1.schemas.catalog import CatalogItemResponse


class BoutiqueLookBase(BaseModel):
    """Base schema with common boutique look fields."""

    title: str = Field(
        ..., min_length=1, max_length=200, description="Look title/name (e.g., 'Summer Casual Outfit')"
    )
    description: Optional[str] = Field(
        None, description="Optional description of the look and styling notes"
    )
    style: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Style identifier (e.g., 'casual', 'formal', 'streetwear', 'bohemian')",
    )
    product_ids: list[str] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="Array of catalog item IDs (2-5 items required). Example: ['1', '2', '3']",
    )
    image_url: Optional[str] = Field(
        None,
        max_length=500,
        description="URL to styled image showing the complete look (can be generated via virtual try-on)",
    )
    is_featured: bool = Field(
        default=False, description="Whether this look is featured/promoted (default: False)"
    )

    @field_validator("product_ids")
    @classmethod
    def validate_product_ids(cls, v: list[str]) -> list[str]:
        """
        Validate that product_ids contains 2-5 items.

        Args:
            v: List of product ID strings

        Returns:
            Validated list of product IDs

        Raises:
            ValueError: If list has fewer than 2 or more than 5 items
        """
        if len(v) < 2:
            raise ValueError("At least 2 product IDs are required")
        if len(v) > 5:
            raise ValueError("Maximum 5 product IDs allowed")
        return v


class BoutiqueLookCreate(BoutiqueLookBase):
    """
    Schema for creating a new boutique look.

    Attributes:
        title: Look title (required)
        description: Optional description
        style: Style identifier (required)
        product_ids: Array of 2-5 catalog item IDs (required)
        image_url: Optional styled image URL
        is_featured: Featured flag (default: False)
    """

    pass


class BoutiqueLookUpdate(BaseModel):
    """
    Schema for updating a boutique look.

    All fields are optional - only provided fields will be updated.
    """

    title: Optional[str] = Field(
        None, min_length=1, max_length=200, description="Look title/name"
    )
    description: Optional[str] = Field(
        None, description="Optional description of the look and styling notes"
    )
    style: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Style identifier (e.g., 'casual', 'formal', 'streetwear')",
    )
    product_ids: Optional[list[str]] = Field(
        None,
        min_length=2,
        max_length=5,
        description="Array of catalog item IDs (2-5 items required)",
    )
    image_url: Optional[str] = Field(
        None,
        max_length=500,
        description="URL to styled image showing the complete look",
    )
    is_featured: Optional[bool] = Field(
        None, description="Whether this look is featured/promoted"
    )

    @field_validator("product_ids")
    @classmethod
    def validate_product_ids(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """
        Validate that product_ids contains 2-5 items if provided.

        Args:
            v: Optional list of product ID strings

        Returns:
            Validated list of product IDs or None

        Raises:
            ValueError: If list has fewer than 2 or more than 5 items
        """
        if v is None:
            return v
        if len(v) < 2:
            raise ValueError("At least 2 product IDs are required")
        if len(v) > 5:
            raise ValueError("Maximum 5 product IDs allowed")
        return v


class BoutiqueLookResponse(BoutiqueLookBase):
    """
    Schema for boutique look response.

    Includes all base fields plus ID, timestamps, boutique_id, total_price, and products.
    """

    id: int = Field(..., description="Look ID")
    boutique_id: int = Field(..., description="Boutique ID (links to Boutique entity)")
    created_at: datetime = Field(..., description="Timestamp when look was created")
    updated_at: datetime = Field(..., description="Timestamp when look was last updated")
    total_price: Optional[int] = Field(
        default=None,
        description="Total price of all products in the look (in cents). Uses discount_price if available, otherwise regular price.",
        json_schema_extra={"example": 75000},
    )
    products: Optional[List[CatalogItemResponse]] = Field(
        default=None,
        description="Full details of all products in the look, ordered to match product_ids",
    )

    model_config = ConfigDict(
        from_attributes=True,
        # Ensure totalPrice is always included in response, even if None
        json_schema_extra={"include_totalPrice": True},
    )

