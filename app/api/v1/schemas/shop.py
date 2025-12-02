"""
Schemas for Shop API - fetching boutique catalog items for individual users.

Reference: https://fastapi.tiangolo.com/tutorial/query-params/
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.catalog import CatalogItemResponse


class ShopItemResponse(CatalogItemResponse):
    """
    Shop item response schema - extends CatalogItemResponse with boutique information.

    This schema includes the catalog item data plus boutique owner details
    for proximity-based shopping.
    """

    # Boutique information (from BoutiqueProfile via user relationship)
    boutique_name: Optional[str] = Field(
        None, description="Name of the boutique/business selling this item"
    )
    boutique_logo_url: Optional[str] = Field(
        None,
        max_length=500,
        description="URL to the boutique/business logo image",
    )
    boutique_distance_miles: Optional[float] = Field(
        None,
        ge=0,
        description="Distance from user's location to boutique in miles (if user location provided)",
    )

    model_config = ConfigDict(from_attributes=True)


class ShopResponse(BaseModel):
    """
    Shop API response schema.

    Returns a list of shop items with optional boutique information.
    """

    items: list[ShopItemResponse] = Field(..., description="List of shop items")
    total: int = Field(..., ge=0, description="Total number of items found")
    radius_miles: float = Field(..., ge=0, description="Proximity radius used (in miles)")

    model_config = ConfigDict(from_attributes=True)

