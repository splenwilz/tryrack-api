"""
Routes for boutique catalog items and reviews.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.auth import WorkOSUserResponse
from app.api.v1.schemas.catalog import (
    CatalogItemCreate,
    CatalogItemResponse,
    CatalogItemUpdate,
    CatalogReviewCreate,
    CatalogReviewResponse,
    CatalogReviewUpdate,
)
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.catalog import CatalogItemStatus
from app.services.catalog import CatalogService

# Import look router to include under catalog
from app.api.v1.routes import look

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
)

# Include look router under catalog
# Pass tags to ensure looks appear under "catalog" tag in docs
router.include_router(look.router, tags=["catalog"])


# Catalog Item Routes
@router.get(
    "",
    response_model=List[CatalogItemResponse],
    summary="Get catalog items",
    description="Get all catalog items with optional filtering by category, brand, or status.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Catalog items retrieved successfully"},
        500: {"description": "Internal server error"},
    },
)
async def get_catalog_items(
    category: Optional[str] = Query(
        None, description="Filter by category (e.g., 'jeans', 'shirt', 'dress')"
    ),
    brand: Optional[str] = Query(
        None, description="Filter by brand name"
    ),
    status_filter: Optional[CatalogItemStatus] = Query(
        None,
        alias="status",
        description="Filter by status (active, inactive, out_of_stock, discontinued)",
    ),
    boutique_id: Optional[int] = Query(
        None,
        description="Filter by boutique ID (to get all items from a specific boutique)",
    ),
    user_id: Optional[str] = Query(
        None,
        description="[Deprecated] Filter by boutique owner user ID. Use boutique_id instead.",
    ),
    skip: int = Query(0, ge=0, description="Number of items to skip (for pagination)"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of items to return"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[CatalogItemResponse]:
    """
    Get catalog items for browsing.

    **Filtering:**
    - Filter by category (e.g., "jeans", "shirt")
    - Filter by brand
    - Filter by status (active, inactive, out_of_stock, discontinued)
    - Filter by boutique ID (boutique_id) to get all items from a specific boutique
    - Filter by boutique owner (user_id) - deprecated, use boutique_id instead
    - Pagination with skip/limit
    """
    catalog_service = CatalogService()
    try:
        items = await catalog_service.get_catalog_items(
            db,
            category=category,
            brand=brand,
            status=status_filter,
            boutique_id=boutique_id,
            user_id=user_id,  # For backward compatibility
            skip=skip,
            limit=limit,
        )
        logger.info(f"Retrieved {len(items)} catalog items")
        return items
    except Exception as e:
        logger.error(f"Unexpected error getting catalog items: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving catalog items",
        ) from e


@router.get(
    "/my-items",
    response_model=List[CatalogItemResponse],
    summary="Get my boutique's catalog items",
    description="Get all catalog items for the authenticated boutique owner.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Catalog items retrieved successfully"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def get_my_catalog_items(
    category: Optional[str] = Query(
        None, description="Filter by category (e.g., 'jeans', 'shirt', 'dress')"
    ),
    brand: Optional[str] = Query(
        None, description="Filter by brand name"
    ),
    status_filter: Optional[CatalogItemStatus] = Query(
        None,
        alias="status",
        description="Filter by status (active, inactive, out_of_stock, discontinued)",
    ),
    skip: int = Query(0, ge=0, description="Number of items to skip (for pagination)"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of items to return"
    ),
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CatalogItemResponse]:
    """
    Get all catalog items for the authenticated boutique owner.

    This endpoint automatically filters items to only return those owned by the authenticated user's boutique.

    **Authorization:**
    - Requires authentication
    - Only returns items owned by the authenticated user's boutique

    **Filtering:**
    - Filter by category (e.g., "jeans", "shirt")
    - Filter by brand
    - Filter by status (active, inactive, out_of_stock, discontinued)
    - Pagination with skip/limit
    """
    catalog_service = CatalogService()
    try:
        items = await catalog_service.get_catalog_items(
            db,
            category=category,
            brand=brand,
            status=status_filter,
            user_id=current_user.id,  # Automatically filter by authenticated user's boutique
            skip=skip,
            limit=limit,
        )
        logger.info(
            f"Retrieved {len(items)} catalog items for boutique owner: {current_user.id}"
        )
        return items
    except Exception as e:
        logger.error(
            f"Unexpected error getting catalog items for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving catalog items",
        ) from e


@router.get(
    "/{item_id}",
    response_model=CatalogItemResponse,
    summary="Get catalog item",
    description="Get a specific catalog item by ID and increment view count.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Catalog item retrieved successfully"},
        404: {"description": "Catalog item not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_catalog_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
) -> CatalogItemResponse:
    """
    Get a specific catalog item by ID.

    Automatically increments the view count when an item is viewed.
    """
    catalog_service = CatalogService()
    try:
        # Increment views atomically
        item = await catalog_service.increment_views(db, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Catalog item not found"
            )
        logger.info(f"Retrieved catalog item {item_id} (views incremented)")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error getting catalog item {item_id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the catalog item",
        ) from e


@router.post(
    "",
    response_model=CatalogItemResponse,
    summary="Create catalog item",
    description="Create a new catalog item (admin/owner only).",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Catalog item created successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def create_catalog_item(
    item_data: CatalogItemCreate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CatalogItemResponse:
    """
    Create a new catalog item for the authenticated boutique owner.

    The item will be automatically linked to the authenticated user's boutique.

    **Authorization:**
    - Requires authentication
    - Item is automatically assigned to the authenticated user's boutique

    **Defaults:**
    - status defaults to "active" if not provided
    - sales, revenue, views default to 0
    """
    catalog_service = CatalogService()
    try:
        # Pass user_id to link item to authenticated boutique owner
        item = await catalog_service.create_catalog_item(db, item_data, current_user.id)
        logger.info(f"Created catalog item '{item.name}' for user: {current_user.id}")
        return item
    except ValueError as e:
        logger.warning(f"Catalog item creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error creating catalog item for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the catalog item",
        ) from e


@router.patch(
    "/{item_id}",
    response_model=CatalogItemResponse,
    summary="Update catalog item",
    description="Update a catalog item (admin/owner only).",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Catalog item updated successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Catalog item not found"},
        500: {"description": "Internal server error"},
    },
)
async def update_catalog_item(
    item_id: int,
    item_data: CatalogItemUpdate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CatalogItemResponse:
    """
    Update a catalog item.

    **Partial Updates:**
    - Only provided fields will be updated
    - Omitted fields remain unchanged

    **Authorization:**
    - Requires authentication
    - Users can only update their own catalog items
    """
    catalog_service = CatalogService()
    try:
        item = await catalog_service.update_catalog_item(
            db, item_id, item_data, current_user.id
        )
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Catalog item not found or you don't have permission to update it",
            )
        logger.info(f"Updated catalog item {item_id} for user: {current_user.id}")
        return item
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Catalog item update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error updating catalog item {item_id} for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the catalog item",
        ) from e


@router.delete(
    "/{item_id}",
    summary="Delete catalog item",
    description="Delete a catalog item (admin/owner only).",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Catalog item deleted successfully"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Catalog item not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_catalog_item(
    item_id: int,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a catalog item.

    **Authorization:**
    - Requires authentication
    - Users can only delete their own catalog items
    """
    catalog_service = CatalogService()
    try:
        deleted = await catalog_service.delete_catalog_item(db, item_id, current_user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Catalog item not found or you don't have permission to delete it",
            )
        logger.info(f"Deleted catalog item {item_id} for user: {current_user.id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error deleting catalog item {item_id} for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the catalog item",
        ) from e


# Review Routes
@router.get(
    "/{item_id}/reviews",
    response_model=List[CatalogReviewResponse],
    summary="Get reviews for catalog item",
    description="Get all reviews for a specific catalog item.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Reviews retrieved successfully"},
        404: {"description": "Catalog item not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_item_reviews(
    item_id: int,
    skip: int = Query(0, ge=0, description="Number of reviews to skip (for pagination)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of reviews to return"),
    db: AsyncSession = Depends(get_db),
) -> List[CatalogReviewResponse]:
    """Get reviews for a specific catalog item."""
    catalog_service = CatalogService()
    try:
        # Verify item exists
        item = await catalog_service.get_catalog_item(db, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Catalog item not found"
            )

        reviews = await catalog_service.get_reviews_for_item(db, item_id, skip=skip, limit=limit)
        logger.info(f"Retrieved {len(reviews)} reviews for catalog item {item_id}")
        return reviews
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error getting reviews for item {item_id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving reviews",
        ) from e


@router.post(
    "/{item_id}/reviews",
    response_model=CatalogReviewResponse,
    summary="Create review",
    description="Create a new review for a catalog item.",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Review created successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Catalog item not found"},
        500: {"description": "Internal server error"},
    },
)
async def create_review(
    item_id: int,
    review_data: CatalogReviewCreate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CatalogReviewResponse:
    """
    Create a new review for a catalog item.

    **Authorization:**
    - Requires authentication
    - Users can review any item
    """
    catalog_service = CatalogService()
    try:
        review = await catalog_service.create_review(db, item_id, current_user.id, review_data)
        logger.info(f"Created review {review.id} for catalog item {item_id} by user {current_user.id}")
        return review
    except ValueError as e:
        logger.warning(f"Review creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error creating review for item {item_id} by user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the review",
        ) from e


@router.patch(
    "/reviews/{review_id}",
    response_model=CatalogReviewResponse,
    summary="Update review",
    description="Update a review (only by the user who created it).",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Review updated successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Review not found or not authorized"},
        500: {"description": "Internal server error"},
    },
)
async def update_review(
    review_id: int,
    review_data: CatalogReviewUpdate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CatalogReviewResponse:
    """
    Update a review.

    **Authorization:**
    - Users can only update their own reviews
    """
    catalog_service = CatalogService()
    try:
        review = await catalog_service.update_review(db, review_id, current_user.id, review_data)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review not found or not authorized"
            )
        logger.info(f"Updated review {review_id} for user: {current_user.id}")
        return review
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Review update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error updating review {review_id} for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the review",
        ) from e


@router.delete(
    "/reviews/{review_id}",
    summary="Delete review",
    description="Delete a review (only by the user who created it).",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Review deleted successfully"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Review not found or not authorized"},
        500: {"description": "Internal server error"},
    },
)
async def delete_review(
    review_id: int,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a review.

    **Authorization:**
    - Users can only delete their own reviews
    """
    catalog_service = CatalogService()
    try:
        deleted = await catalog_service.delete_review(db, review_id, current_user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review not found or not authorized"
            )
        logger.info(f"Deleted review {review_id} for user: {current_user.id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error deleting review {review_id} for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the review",
        ) from e

