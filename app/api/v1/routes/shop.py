"""
Shop API routes for fetching boutique catalog items for individual users.

Implements proximity-based filtering and round-robin selection to ensure
diversity across different boutiques.

Reference: https://fastapi.tiangolo.com/tutorial/query-params/
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.shop import ShopItemResponse, ShopResponse
from app.core.database import get_db
from app.services.shop import ShopService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/shop",
    tags=["shop"],
    responses={
        500: {"description": "Internal server error"},
    },
)


@router.get(
    "",
    response_model=ShopResponse,
    summary="Get shop items",
    description="Get boutique catalog items with proximity filtering and round-robin selection from different boutiques.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Shop items retrieved successfully"},
        400: {"description": "Invalid query parameters"},
        500: {"description": "Internal server error"},
    },
)
async def get_shop_items(
    category: Optional[str] = Query(
        None,
        description="Filter by category (e.g., 'jeans', 'shirt', 'dress'). If not provided, returns items from all categories.",
    ),
    radius_miles: float = Query(
        100.0,
        ge=0.1,
        le=10000.0,
        description="Proximity radius in miles (default: 100). Only used if latitude and longitude are provided.",
    ),
    latitude: Optional[float] = Query(
        None,
        ge=-90.0,
        le=90.0,
        description="User's latitude in decimal degrees (optional). If provided with longitude, filters items by proximity.",
    ),
    longitude: Optional[float] = Query(
        None,
        ge=-180.0,
        le=180.0,
        description="User's longitude in decimal degrees (optional). If provided with latitude, filters items by proximity.",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Maximum number of items to return (default: 50, max: 200)",
    ),
    db: AsyncSession = Depends(get_db),
) -> ShopResponse:
    """
    Get shop items from different boutiques using round-robin selection.

    **Features:**
    - Proximity filtering: If latitude/longitude provided, only returns items from boutiques within the specified radius
    - Round-robin selection: Ensures diversity by selecting items from different boutiques in rotation
    - Category filtering: Optional filter by product category
    - Only returns ACTIVE items

    **Algorithm:**
    1. Filters catalog items by category (if provided) and status (ACTIVE only)
    2. If user location provided, calculates distance to each boutique using Haversine formula
    3. Filters items by proximity radius
    4. Groups items by boutique (user_id)
    5. Round-robin selection: picks one item from each boutique in rotation until limit reached

    **Examples:**
    - Get all items within 50 miles: `?latitude=40.7128&longitude=-74.0060&radius_miles=50`
    - Get jeans within 100 miles: `?category=jeans&latitude=40.7128&longitude=-74.0060`
    - Get all items (no proximity filter): `?limit=100`

    Args:
        category: Optional category filter
        radius_miles: Proximity radius in miles (default: 100)
        latitude: User's latitude (optional)
        longitude: User's longitude (optional)
        limit: Maximum number of items to return
        db: Database session

    Returns:
        ShopResponse with list of items, total count, and radius used
    """
    # Validate that both latitude and longitude are provided together
    if (latitude is not None and longitude is None) or (
        latitude is None and longitude is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both latitude and longitude must be provided together, or both omitted",
        )

    shop_service = ShopService()

    try:
        items, actual_radius = await shop_service.get_shop_items(
            db,
            category=category,
            radius_miles=radius_miles,
            user_latitude=latitude,
            user_longitude=longitude,
            limit=limit,
        )

        # Transform items to include boutique information and distance
        shop_items: list[ShopItemResponse] = []
        for item in items:
            # Get boutique information
            boutique_profile = (
                item.user.boutique_profile if item.user else None
            )
            boutique_name = (
                boutique_profile.business_name if boutique_profile else None
            )
            boutique_logo_url = (
                boutique_profile.logo_url if boutique_profile else None
            )

            # Calculate distance if user location provided
            boutique_distance_miles = None
            if (
                latitude is not None
                and longitude is not None
                and boutique_profile
                and boutique_profile.latitude is not None
                and boutique_profile.longitude is not None
            ):
                from app.services.shop import haversine_distance

                boutique_distance_miles = haversine_distance(
                    latitude,
                    longitude,
                    boutique_profile.latitude,
                    boutique_profile.longitude,
                )

            # Create shop item response
            shop_item = ShopItemResponse.model_validate(item)
            shop_item.boutique_name = boutique_name
            shop_item.boutique_logo_url = boutique_logo_url
            shop_item.boutique_distance_miles = boutique_distance_miles
            shop_items.append(shop_item)

        logger.info(
            f"Shop API: Returning {len(shop_items)} items (radius: {actual_radius} miles)"
        )

        return ShopResponse(
            items=shop_items,
            total=len(shop_items),
            radius_miles=actual_radius,
        )

    except Exception as e:
        logger.error(
            f"Unexpected error getting shop items: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving shop items",
        ) from e

