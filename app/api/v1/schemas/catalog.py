"""
Schemas for boutique catalog items and reviews.

Reference: https://fastapi.tiangolo.com/tutorial/body/
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.catalog import CatalogItemStatus


class CatalogItemBase(BaseModel):
    """Base schema with common catalog item fields."""

    name: str = Field(..., min_length=1, max_length=200, description="Product name")
    category: str = Field(
        ..., min_length=1, max_length=50, description="Product category (e.g., 'jeans', 'shirt', 'dress')"
    )
    brand: Optional[str] = Field(
        None, max_length=100, description="Brand name (optional for generic/unbranded items)"
    )
    cost_price: Optional[int] = Field(
        None,
        ge=0,
        description="Cost price in smallest currency unit (cents/pence). Optional - can be hidden from non-admin users. Example: 30000 = $300.00",
    )
    price: int = Field(
        ..., ge=0, description="Regular selling price in smallest currency unit (cents/pence). Example: 55000 = $550.00"
    )
    discount_price: Optional[int] = Field(
        None,
        ge=0,
        description="Discount/sale price in smallest currency unit (cents/pence). Only set when item is on sale. Example: 45000 = $450.00",
    )
    image_url: str = Field(..., max_length=500, description="URL to product image")
    stock: int = Field(
        default=0, ge=0, description="Available inventory count"
    )
    status: Optional[CatalogItemStatus] = Field(
        None, description="Product status (active, inactive, out_of_stock, discontinued)"
    )
    tags: Optional[List[str]] = Field(
        None, description="List of tags for filtering/searching (e.g., ['denim', 'moto', 'casual'])"
    )
    colors: Optional[List[str]] = Field(
        None, description="List of available colors (e.g., ['navy blue', 'white'])"
    )
    description: Optional[str] = Field(
        None, description="Product description"
    )


class CatalogItemCreate(CatalogItemBase):
    """
    Schema for creating a new catalog item.

    Attributes:
        name: Product name (required)
        category: Product category (required)
        brand: Brand name (optional)
        cost_price: Cost price in cents (optional)
        price: Regular selling price in cents (required)
        discount_price: Sale price in cents (optional)
        image_url: URL to product image (required)
        stock: Available inventory count (default: 0)
        status: Product status (defaults to 'active' if not provided)
        tags: Optional list of tags
        colors: Optional list of colors
        description: Optional product description
    """

    @model_validator(mode="after")
    def validate_discount_price(self) -> "CatalogItemCreate":
        """Ensure discount_price is less than regular price if provided."""
        if self.discount_price is not None and self.price is not None:
            if self.discount_price >= self.price:
                raise ValueError("Discount price must be less than regular price")
        return self


class CatalogItemUpdate(BaseModel):
    """
    Schema for updating a catalog item.

    All fields are optional for partial updates.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Product name")
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="Product category")
    brand: Optional[str] = Field(None, max_length=100, description="Brand name")
    cost_price: Optional[int] = Field(None, ge=0, description="Cost price in smallest currency unit")
    price: Optional[int] = Field(None, ge=0, description="Regular selling price in smallest currency unit")
    discount_price: Optional[int] = Field(None, ge=0, description="Discount/sale price in smallest currency unit")
    image_url: Optional[str] = Field(None, max_length=500, description="URL to product image")
    stock: Optional[int] = Field(None, ge=0, description="Available inventory count")
    status: Optional[CatalogItemStatus] = Field(None, description="Product status")
    tags: Optional[List[str]] = Field(None, description="List of tags")
    colors: Optional[List[str]] = Field(None, description="List of colors")
    description: Optional[str] = Field(None, description="Product description")

    @model_validator(mode="after")
    def validate_discount_price(self) -> "CatalogItemUpdate":
        """Ensure discount_price is less than regular price if both are provided."""
        if self.discount_price is not None and self.price is not None:
            if self.discount_price >= self.price:
                raise ValueError("Discount price must be less than regular price")
        return self


class CatalogItemResponse(CatalogItemBase):
    """
    Schema for catalog item response.

    Includes all fields from CatalogItemBase plus database-generated fields.
    Note: cost_price is included here but can be excluded in admin-only schemas.
    """

    id: int = Field(..., description="Product ID")
    sales: int = Field(..., ge=0, description="Number of units sold")
    revenue: int = Field(..., ge=0, description="Total revenue in smallest currency unit")
    views: int = Field(..., ge=0, description="Number of times product was viewed")
    created_at: datetime = Field(..., description="Timestamp when item was created")
    updated_at: datetime = Field(..., description="Timestamp when item was last updated")

    model_config = ConfigDict(from_attributes=True)


class CatalogReviewBase(BaseModel):
    """Base schema with common review fields."""

    rating: int = Field(..., ge=1, le=5, description="Rating value (1-5 stars)")
    comment: Optional[str] = Field(None, description="Review comment/text")


class CatalogReviewCreate(CatalogReviewBase):
    """Schema for creating a new review."""

    pass


class CatalogReviewUpdate(BaseModel):
    """Schema for updating a review."""

    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating value (1-5 stars)")
    comment: Optional[str] = Field(None, description="Review comment/text")


class CatalogReviewResponse(CatalogReviewBase):
    """Schema for review response."""

    id: int = Field(..., description="Review ID")
    catalog_item_id: int = Field(..., description="Catalog item ID being reviewed")
    user_id: str = Field(..., description="User ID who wrote the review")
    created_at: datetime = Field(..., description="Timestamp when review was created")
    updated_at: datetime = Field(..., description="Timestamp when review was last updated")

    model_config = ConfigDict(from_attributes=True)

