"""
Wardrobe item routes
Handles CRUD operations for wardrobe items
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.auth import WorkOSUserResponse
from app.api.v1.schemas.wardrobe import WardrobeCreate, WardrobeResponse, WardrobeUpdate
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.wardrobe import ItemStatus
from app.services.wardrobe import WardrobeService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/wardrobe",
    tags=["wardrobe"],
)


@router.get(
    "",
    response_model=list[WardrobeResponse],
    summary="Get wardrobe items",
    description="Get all wardrobe items for the authenticated user with optional filtering.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Wardrobe items retrieved successfully"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def get_wardrobe_items(
    category: Optional[str] = Query(
        None, description="Filter by category (e.g., 'shirt', 'pants', 'dress')"
    ),
    status_filter: Optional[ItemStatus] = Query(
        None, alias="status", description="Filter by status (clean, worn, dirty)"
    ),
    skip: int = Query(0, ge=0, description="Number of items to skip (for pagination)"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of items to return"
    ),
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WardrobeResponse]:
    """
    Get wardrobe items for the authenticated user.

    **Filtering:**
    - Filter by category (e.g., "shirt", "pants")
    - Filter by status (clean, worn, dirty)
    - Pagination with skip/limit

    **Authorization:**
    - Users can only access their own wardrobe items

    Args:
        category: Optional category filter
        status_filter: Optional status filter
        skip: Number of items to skip
        limit: Maximum number of items to return
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        List of wardrobe items
    """
    wardrobe_service = WardrobeService()
    try:
        import time

        db_query_start = time.time()
        items = await wardrobe_service.get_wardrobe_items(
            db,
            current_user.id,
            category=category,
            status=status_filter,
            skip=skip,
            limit=limit,
        )
        db_query_time = (time.time() - db_query_start) * 1000
        logger.debug(
            f"Database query (get_wardrobe_items) took {db_query_time:.1f}ms",
            extra={"timing_ms": db_query_time, "operation": "get_wardrobe_items"},
        )
        logger.info(
            f"Retrieved {len(items)} wardrobe items for user: {current_user.id}"
        )
        return items
    except Exception as e:
        logger.error(
            f"Unexpected error getting wardrobe items for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving wardrobe items",
        ) from e


@router.get(
    "/{item_id}",
    response_model=WardrobeResponse,
    summary="Get wardrobe item",
    description="Get a specific wardrobe item by ID for the authenticated user.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Wardrobe item retrieved successfully"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Wardrobe item not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_wardrobe_item(
    item_id: int,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WardrobeResponse:
    """
    Get a specific wardrobe item by ID.

    **Authorization:**
    - Users can only access their own wardrobe items

    Args:
        item_id: Item ID
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Wardrobe item

    Raises:
        HTTPException: 404 if item not found or doesn't belong to user
    """
    wardrobe_service = WardrobeService()
    try:
        item = await wardrobe_service.get_wardrobe_item(db, item_id, current_user.id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Wardrobe item not found"
            )
        logger.info(f"Retrieved wardrobe item {item_id} for user: {current_user.id}")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error getting wardrobe item {item_id} for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the wardrobe item",
        ) from e


@router.post(
    "",
    response_model=WardrobeResponse,
    summary="Create wardrobe item",
    description="Create a new wardrobe item for the authenticated user.",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Wardrobe item created successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def create_wardrobe_item(
    wardrobe_data: WardrobeCreate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WardrobeResponse:
    """
    Create a new wardrobe item.

    **Authorization:**
    - Users can only create items for themselves (user_id is automatically set from authenticated user)

    **Defaults:**
    - status defaults to "clean" if not provided
    - wear_count defaults to 0

    Args:
        wardrobe_data: Wardrobe item data
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Created wardrobe item

    Raises:
        HTTPException: 400 for validation errors, 500 for unexpected errors
    """
    wardrobe_service = WardrobeService()
    try:
        item = await wardrobe_service.create_wardrobe_item(
            db, current_user.id, wardrobe_data
        )
        logger.info(f"Created wardrobe item '{item.title}' for user: {current_user.id}")
        return item
    except ValueError as e:
        logger.warning(f"Wardrobe item creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error creating wardrobe item for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the wardrobe item",
        ) from e


@router.patch(
    "/{item_id}",
    response_model=WardrobeResponse,
    summary="Update wardrobe item",
    description="Update a wardrobe item. All fields are optional for partial updates.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Wardrobe item updated successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Wardrobe item not found"},
        500: {"description": "Internal server error"},
    },
)
async def update_wardrobe_item(
    item_id: int,
    wardrobe_data: WardrobeUpdate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WardrobeResponse:
    """
    Update a wardrobe item.

    **Partial Updates:**
    - Only provided fields will be updated
    - Omitted fields remain unchanged

    **Authorization:**
    - Users can only update their own wardrobe items

    Args:
        item_id: Item ID
        wardrobe_data: Update data (all fields optional)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Updated wardrobe item

    Raises:
        HTTPException: 404 if item not found, 400 for validation errors
    """
    wardrobe_service = WardrobeService()
    try:
        item = await wardrobe_service.update_wardrobe_item(
            db, item_id, current_user.id, wardrobe_data
        )
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Wardrobe item not found"
            )
        logger.info(f"Updated wardrobe item {item_id} for user: {current_user.id}")
        return item
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Wardrobe item update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error updating wardrobe item {item_id} for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the wardrobe item",
        ) from e


@router.delete(
    "/{item_id}",
    summary="Delete wardrobe item",
    description="Delete a wardrobe item.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Wardrobe item deleted successfully"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Wardrobe item not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_wardrobe_item(
    item_id: int,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a wardrobe item.

    **Authorization:**
    - Users can only delete their own wardrobe items

    Args:
        item_id: Item ID
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        None (204 No Content)

    Raises:
        HTTPException: 404 if item not found
    """
    wardrobe_service = WardrobeService()
    try:
        deleted = await wardrobe_service.delete_wardrobe_item(
            db, item_id, current_user.id
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Wardrobe item not found"
            )
        logger.info(f"Deleted wardrobe item {item_id} for user: {current_user.id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error deleting wardrobe item {item_id} for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the wardrobe item",
        ) from e


@router.post(
    "/{item_id}/mark-worn",
    response_model=WardrobeResponse,
    summary="Mark item as worn",
    description="Mark a wardrobe item as worn (increments wear_count and updates last_worn_at).",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Item marked as worn successfully"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Wardrobe item not found"},
        500: {"description": "Internal server error"},
    },
)
async def mark_item_worn(
    item_id: int,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WardrobeResponse:
    """
    Mark a wardrobe item as worn.

    This endpoint:
    - Increments wear_count by 1
    - Updates last_worn_at to current timestamp
    - Sets status to "worn"

    **Authorization:**
    - Users can only mark their own items as worn

    Args:
        item_id: Item ID
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Updated wardrobe item

    Raises:
        HTTPException: 404 if item not found
    """
    wardrobe_service = WardrobeService()
    try:
        item = await wardrobe_service.mark_item_worn(db, item_id, current_user.id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Wardrobe item not found"
            )
        logger.info(
            f"Marked wardrobe item {item_id} as worn for user: {current_user.id}"
        )
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error marking item {item_id} as worn for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while marking the item as worn",
        ) from e
