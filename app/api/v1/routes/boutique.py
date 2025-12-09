"""
Routes for boutique-centric operations.

Provides endpoints to access boutiques directly by boutique_id,
enabling frontend to work with boutiques without needing user context.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.auth import WorkOSUserResponse
from app.api.v1.schemas.catalog import CatalogItemResponse
from app.api.v1.schemas.look import BoutiqueLookResponse
from app.api.v1.schemas.user import BoutiqueProfileResponse, BoutiqueProfileUpdate
from app.core.database import get_db
from app.core.dependencies import get_admin_user
from app.models.boutique import Boutique
from app.models.catalog import CatalogItem, CatalogItemStatus
from app.models.review import Review, ReviewItemType
from app.services.catalog import CatalogService
from app.services.look import LookService
from app.services.user import UserService

logger = logging.getLogger(__name__)


async def enrich_boutique_profile_with_stats(
    db: AsyncSession, boutique_profile, boutique_id: int
) -> BoutiqueProfileResponse:
    """
    Enrich boutique profile with computed stats (rating, review_count, product_count).

    Args:
        db: Database session
        boutique_profile: BoutiqueProfile model instance
        boutique_id: Boutique ID

    Returns:
        BoutiqueProfileResponse with computed fields
    """
    boutique_id_str = str(boutique_id)

    # Get average rating and review count from approved reviews
    review_stats_result = await db.execute(
        select(
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count"),
        ).where(
            Review.item_type == ReviewItemType.BOUTIQUE.value,
            Review.item_id == boutique_id_str,
            Review.is_approved.is_(True),  # Only count approved reviews
        )
    )
    review_stats = review_stats_result.first()
    rating = float(review_stats.avg_rating) if review_stats.avg_rating else None
    review_count = review_stats.review_count or 0

    # Get product count (catalog items)
    product_count_result = await db.execute(
        select(func.count(CatalogItem.id)).where(CatalogItem.boutique_id == boutique_id)
    )
    product_count = product_count_result.scalar() or 0

    # Convert to response with computed fields
    profile_dict = {
        "id": boutique_profile.id,
        "boutique_id": boutique_profile.boutique_id,
        "business_name": boutique_profile.business_name,
        "business_address": boutique_profile.business_address,
        "business_category": boutique_profile.business_category,
        "business_city": boutique_profile.business_city,
        "business_state": boutique_profile.business_state,
        "business_zip": boutique_profile.business_zip,
        "business_country": boutique_profile.business_country,
        "business_phone": boutique_profile.business_phone,
        "business_email": boutique_profile.business_email,
        "business_website": boutique_profile.business_website,
        "business_social_media": boutique_profile.business_social_media,
        "logo_url": boutique_profile.logo_url,
        "cover_image_url": boutique_profile.cover_image_url,
        "featured": boutique_profile.featured,
        "currency": boutique_profile.currency,
        "timezone": boutique_profile.timezone,
        "language": boutique_profile.language,
        "rating": rating,
        "review_count": review_count,
        "product_count": product_count,
        "created_at": boutique_profile.created_at,
        "updated_at": boutique_profile.updated_at,
    }

    return BoutiqueProfileResponse(**profile_dict)


router = APIRouter(
    prefix="/boutiques",
    tags=["boutiques"],
    responses={
        404: {"description": "Boutique not found"},
        500: {"description": "Internal server error"},
    },
)


@router.get(
    "",
    response_model=List[BoutiqueProfileResponse],
    summary="List boutiques",
    description="Get all boutiques with optional filtering and pagination.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Boutiques retrieved successfully"},
        500: {"description": "Internal server error"},
    },
)
async def list_boutiques(
    featured: Optional[bool] = Query(
        None, description="Filter by featured status (true for featured boutiques only)"
    ),
    city: Optional[str] = Query(
        None, description="Filter by business city (e.g., 'New York', 'Los Angeles')"
    ),
    category: Optional[str] = Query(
        None,
        description="Filter by business category (e.g., 'Luxury Boutique', 'Fashion')",
    ),
    skip: int = Query(
        0, ge=0, description="Number of boutiques to skip (for pagination)"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of boutiques to return"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[BoutiqueProfileResponse]:
    """
    Get all boutiques with optional filtering and pagination.

    **Filtering:**
    - Filter by featured status (featured boutiques only)
    - Filter by city (business_city)
    - Filter by category (business_category)
    - Pagination with skip/limit

    **Response:**
    Each boutique includes computed fields:
    - rating: Average rating from approved reviews (0-5 stars)
    - review_count: Total number of approved reviews
    - product_count: Total number of catalog items

    Args:
        featured: Optional featured status filter
        city: Optional city filter
        category: Optional category filter
        skip: Number of boutiques to skip (for pagination)
        limit: Maximum number of boutiques to return
        db: Database session

    Returns:
        List of boutique profiles with computed stats

    Raises:
        HTTPException:
            - 500 for unexpected errors
    """
    try:
        from app.models.user import BoutiqueProfile

        # Build query
        query = select(BoutiqueProfile)

        # Apply filters
        if featured is not None:
            query = query.where(BoutiqueProfile.featured == featured)

        if city:
            query = query.where(BoutiqueProfile.business_city.ilike(f"%{city}%"))

        if category:
            query = query.where(
                BoutiqueProfile.business_category.ilike(f"%{category}%")
            )

        # Order by featured first, then by creation date (newest first)
        query = (
            query.order_by(
                BoutiqueProfile.featured.desc(), BoutiqueProfile.created_at.desc()
            )
            .offset(skip)
            .limit(limit)
        )

        # Execute query
        result = await db.execute(query)
        boutique_profiles = list(result.scalars().all())

        # Enrich each profile with computed stats
        enriched_profiles = []
        for profile in boutique_profiles:
            enriched = await enrich_boutique_profile_with_stats(
                db, profile, profile.boutique_id
            )
            enriched_profiles.append(enriched)

        logger.info(f"Retrieved {len(enriched_profiles)} boutiques")
        return enriched_profiles
    except Exception as e:
        logger.error(
            f"Unexpected error listing boutiques: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving boutiques",
        ) from e


@router.get(
    "/{boutique_id}",
    response_model=BoutiqueProfileResponse,
    summary="Get boutique profile",
    description="Get boutique profile by boutique ID.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Boutique profile retrieved successfully"},
        404: {"description": "Boutique not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_boutique_profile(
    boutique_id: int,
    db: AsyncSession = Depends(get_db),
) -> BoutiqueProfileResponse:
    """
    Get boutique profile by boutique ID.

    This endpoint allows accessing boutique information directly using boutique_id,
    without needing to know the user/owner.

    Args:
        boutique_id: Boutique ID
        db: Database session

    Returns:
        BoutiqueProfileResponse object

    Raises:
        HTTPException:
            - 404 if boutique not found
            - 500 for unexpected errors
    """
    # Verify boutique exists
    boutique_result = await db.execute(
        select(Boutique).where(Boutique.id == boutique_id)
    )
    boutique = boutique_result.scalar_one_or_none()
    if not boutique:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Boutique with ID {boutique_id} not found",
        )

    try:
        # Get boutique profile directly by boutique_id
        from app.models.user import BoutiqueProfile

        profile_result = await db.execute(
            select(BoutiqueProfile).where(BoutiqueProfile.boutique_id == boutique_id)
        )
        boutique_profile = profile_result.scalar_one_or_none()

        if not boutique_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Boutique profile not found for boutique ID {boutique_id}",
            )

        # Enrich with computed stats
        enriched_profile = await enrich_boutique_profile_with_stats(
            db, boutique_profile, boutique_id
        )

        logger.info(
            f"Boutique profile retrieved successfully for boutique: {boutique_id} "
            f"(rating={enriched_profile.rating}, reviews={enriched_profile.review_count}, "
            f"products={enriched_profile.product_count})"
        )
        return enriched_profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error getting boutique profile for boutique {boutique_id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while getting the boutique profile",
        ) from e


@router.get(
    "/{boutique_id}/items",
    response_model=List[CatalogItemResponse],
    summary="Get boutique catalog items",
    description="Get all catalog items from a specific boutique by boutique ID.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Catalog items retrieved successfully"},
        404: {"description": "Boutique not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_boutique_items(
    boutique_id: int,
    category: Optional[str] = Query(
        None, description="Filter by category (e.g., 'jeans', 'shirt', 'dress')"
    ),
    brand: Optional[str] = Query(None, description="Filter by brand name"),
    status_filter: Optional[CatalogItemStatus] = Query(
        None,
        alias="status",
        description="Filter by status (active, inactive, out_of_stock, discontinued)",
    ),
    skip: int = Query(0, ge=0, description="Number of items to skip (for pagination)"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of items to return"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[CatalogItemResponse]:
    """
    Get all catalog items from a specific boutique.

    This endpoint allows fetching all items from a boutique using boutique_id,
    enabling frontend to display boutique catalogs without user context.

    **Filtering:**
    - Filter by category (e.g., "jeans", "shirt")
    - Filter by brand
    - Filter by status (active, inactive, out_of_stock, discontinued)
    - Pagination with skip/limit

    Args:
        boutique_id: Boutique ID
        category: Optional category filter
        brand: Optional brand filter
        status_filter: Optional status filter
        skip: Number of items to skip (for pagination)
        limit: Maximum number of items to return
        db: Database session

    Returns:
        List of catalog items from the boutique

    Raises:
        HTTPException:
            - 404 if boutique not found
            - 500 for unexpected errors
    """
    # Verify boutique exists
    boutique_result = await db.execute(
        select(Boutique).where(Boutique.id == boutique_id)
    )
    boutique = boutique_result.scalar_one_or_none()
    if not boutique:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Boutique with ID {boutique_id} not found",
        )

    catalog_service = CatalogService()
    try:
        items = await catalog_service.get_catalog_items(
            db,
            category=category,
            brand=brand,
            status=status_filter,
            boutique_id=boutique_id,  # Direct boutique_id filter
            skip=skip,
            limit=limit,
        )
        logger.info(f"Retrieved {len(items)} catalog items for boutique: {boutique_id}")
        return items
    except Exception as e:
        logger.error(
            f"Unexpected error getting catalog items for boutique {boutique_id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving catalog items",
        ) from e


@router.get(
    "/{boutique_id}/looks",
    response_model=List[BoutiqueLookResponse],
    summary="Get boutique looks",
    description="Get all looks from a specific boutique by boutique ID.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Boutique looks retrieved successfully"},
        404: {"description": "Boutique not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_boutique_looks(
    boutique_id: int,
    style: Optional[str] = Query(
        None, description="Filter by style (e.g., 'casual', 'formal', 'streetwear')"
    ),
    is_featured: Optional[bool] = Query(
        None, description="Filter by featured status (true for featured looks only)"
    ),
    skip: int = Query(0, ge=0, description="Number of items to skip (for pagination)"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of items to return"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[BoutiqueLookResponse]:
    """
    Get all looks from a specific boutique.

    This endpoint allows fetching all looks from a boutique using boutique_id,
    enabling frontend to display boutique looks without user context.

    **Filtering:**
    - Filter by style (e.g., "casual", "formal")
    - Filter by featured status
    - Pagination with skip/limit

    Args:
        boutique_id: Boutique ID
        style: Optional style filter
        is_featured: Optional featured status filter
        skip: Number of items to skip (for pagination)
        limit: Maximum number of items to return
        db: Database session

    Returns:
        List of boutique looks with total_price and products populated

    Raises:
        HTTPException:
            - 404 if boutique not found
            - 500 for unexpected errors
    """
    # Verify boutique exists
    boutique_result = await db.execute(
        select(Boutique).where(Boutique.id == boutique_id)
    )
    boutique = boutique_result.scalar_one_or_none()
    if not boutique:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Boutique with ID {boutique_id} not found",
        )

    look_service = LookService()
    try:
        # Get looks filtered by boutique_id
        from app.models.look import BoutiqueLook

        query = select(BoutiqueLook).where(BoutiqueLook.boutique_id == boutique_id)

        if style:
            query = query.where(BoutiqueLook.style == style)

        if is_featured is not None:
            query = query.where(BoutiqueLook.is_featured == is_featured)

        query = query.order_by(BoutiqueLook.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        looks = list(result.scalars().all())

        # Calculate total_price and fetch product details for each look
        look_responses = []
        for look in looks:
            total_price = await look_service.calculate_total_price(db, look.product_ids)
            products = await look_service.get_catalog_items_by_ids(db, look.product_ids)
            look_dict = BoutiqueLookResponse.model_validate(look).model_dump(
                exclude_none=False
            )
            look_dict["total_price"] = total_price
            look_dict["products"] = [
                CatalogItemResponse.model_validate(product).model_dump(
                    exclude_none=False
                )
                for product in products
            ]
            look_responses.append(BoutiqueLookResponse(**look_dict))

        logger.info(
            f"Retrieved {len(look_responses)} looks for boutique: {boutique_id}"
        )
        return look_responses
    except Exception as e:
        logger.error(
            f"Unexpected error getting looks for boutique {boutique_id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving boutique looks",
        ) from e


@router.patch(
    "/{boutique_id}/admin",
    response_model=BoutiqueProfileResponse,
    summary="Update boutique profile (Admin)",
    description="Update boutique profile with admin-only fields (admin only).",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Boutique profile updated successfully"},
        401: {"description": "Unauthorized - authentication required"},
        403: {"description": "Forbidden - admin access required"},
        404: {"description": "Boutique not found"},
        500: {"description": "Internal server error"},
    },
)
async def update_boutique_profile_admin(
    boutique_id: int,
    boutique_profile_data: BoutiqueProfileUpdate,
    admin_user: WorkOSUserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> BoutiqueProfileResponse:
    """
    Update boutique profile with admin-only fields.

    This endpoint allows admins to update any boutique profile field, including
    admin-managed fields like `featured`.

    **Authorization:**
    - Requires admin authentication
    - Only admins can use this endpoint

    **Use Cases:**
    - Set/update `featured` status for boutiques
    - Update any boutique profile field as an admin
    - Manage boutique profiles across the platform

    Args:
        boutique_id: Boutique ID to update
        boutique_profile_data: Profile update data (all fields optional)
        admin_user: Authenticated admin user (from JWT token)
        db: Database session

    Returns:
        Updated BoutiqueProfileResponse object with computed stats

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 403 if not admin
            - 404 if boutique not found
            - 400 for validation errors
            - 500 for unexpected errors
    """
    # Verify boutique exists
    boutique_result = await db.execute(
        select(Boutique).where(Boutique.id == boutique_id)
    )
    boutique = boutique_result.scalar_one_or_none()
    if not boutique:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Boutique with ID {boutique_id} not found",
        )

    try:
        # Get boutique profile
        from app.models.user import BoutiqueProfile

        profile_result = await db.execute(
            select(BoutiqueProfile).where(BoutiqueProfile.boutique_id == boutique_id)
        )
        boutique_profile = profile_result.scalar_one_or_none()

        if not boutique_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Boutique profile not found for boutique ID {boutique_id}",
            )

        # Update profile using UserService
        user_service = UserService()
        # We need to get the owner's user_id to use the service method
        # But since we're admin, we can update directly
        update_data = boutique_profile_data.model_dump(exclude_unset=True)

        if not update_data:
            # No fields to update, return current profile
            enriched_profile = await enrich_boutique_profile_with_stats(
                db, boutique_profile, boutique_id
            )
            return enriched_profile

        # Update the database model directly
        for field, value in update_data.items():
            setattr(boutique_profile, field, value)

        await db.flush()

        # Manually set updated_at
        from datetime import datetime, timezone

        boutique_profile.updated_at = datetime.now(timezone.utc)

        # Enrich with computed stats
        enriched_profile = await enrich_boutique_profile_with_stats(
            db, boutique_profile, boutique_id
        )

        logger.info(
            f"Admin {admin_user.id} updated boutique profile for boutique: {boutique_id}"
        )
        return enriched_profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error updating boutique profile for boutique {boutique_id} by admin {admin_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the boutique profile",
        ) from e
