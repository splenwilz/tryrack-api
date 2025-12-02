"""
Boutique Look API routes for managing styled combinations of catalog items.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.auth import WorkOSUserResponse
from app.api.v1.schemas.catalog import CatalogItemResponse
from app.api.v1.schemas.look import (
    BoutiqueLookCreate,
    BoutiqueLookResponse,
    BoutiqueLookUpdate,
)
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.look import LookService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/looks",
    # No tags here - will inherit "catalog" tag from parent router
    responses={
        500: {"description": "Internal server error"},
    },
)


@router.get(
    "",
    response_model=List[BoutiqueLookResponse],
    summary="Get boutique looks",
    description="Get all boutique looks with optional filtering by style, featured status, and boutique owner.",
    status_code=status.HTTP_200_OK,
    tags=["catalog"],  # Appears under catalog in API docs
    responses={
        200: {"description": "Boutique looks retrieved successfully"},
        500: {"description": "Internal server error"},
    },
)
async def get_looks(
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
    Get boutique looks for browsing.

    **Filtering:**
    - Filter by style (e.g., "casual", "formal")
    - Filter by featured status
    - Pagination with skip/limit

    **Note:** This endpoint returns looks from all boutiques. To get looks for a specific boutique,
    use the authenticated endpoint with the boutique owner's token.
    """
    look_service = LookService()
    try:
        looks = await look_service.get_looks(
            db,
            user_id=None,  # Get looks from all boutiques
            style=style,
            is_featured=is_featured,
            skip=skip,
            limit=limit,
        )

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

        logger.info(f"Retrieved {len(look_responses)} boutique looks")
        return look_responses
    except Exception as e:
        logger.error(
            f"Unexpected error getting boutique looks: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving boutique looks",
        ) from e


@router.get(
    "/my-looks",
    response_model=List[BoutiqueLookResponse],
    summary="Get my boutique looks",
    description="Get all looks for the authenticated boutique owner.",
    status_code=status.HTTP_200_OK,
    tags=["catalog"],  # Appears under catalog in API docs
    responses={
        200: {"description": "Boutique looks retrieved successfully"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def get_my_looks(
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
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[BoutiqueLookResponse]:
    """
    Get boutique looks for the authenticated boutique owner.

    **Authorization:**
    - Requires authentication
    - Returns only looks created by the authenticated user's boutique

    **Filtering:**
    - Filter by style (e.g., "casual", "formal")
    - Filter by featured status
    - Pagination with skip/limit
    """
    look_service = LookService()
    try:
        looks = await look_service.get_looks(
            db,
            user_id=current_user.id,
            style=style,
            is_featured=is_featured,
            skip=skip,
            limit=limit,
        )

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
            f"Retrieved {len(look_responses)} boutique looks for user: {current_user.id}"
        )
        return look_responses
    except Exception as e:
        logger.error(
            f"Unexpected error getting boutique looks for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving boutique looks",
        ) from e


@router.get(
    "/{look_id}",
    response_model=BoutiqueLookResponse,
    summary="Get boutique look",
    description="Get a specific boutique look by ID.",
    status_code=status.HTTP_200_OK,
    tags=["catalog"],  # Appears under catalog in API docs
    responses={
        200: {"description": "Boutique look retrieved successfully"},
        404: {"description": "Boutique look not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_look(
    look_id: int,
    db: AsyncSession = Depends(get_db),
) -> BoutiqueLookResponse:
    """
    Get a specific boutique look by ID.
    """
    look_service = LookService()
    try:
        look = await look_service.get_look(db, look_id)
        if not look:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Boutique look not found"
            )

        # Calculate total_price and fetch product details
        total_price = await look_service.calculate_total_price(db, look.product_ids)
        products = await look_service.get_catalog_items_by_ids(db, look.product_ids)
        look_dict = BoutiqueLookResponse.model_validate(look).model_dump(
            exclude_none=False
        )
        look_dict["total_price"] = total_price
        look_dict["products"] = [
            CatalogItemResponse.model_validate(product).model_dump(exclude_none=False)
            for product in products
        ]

        logger.info(f"Retrieved boutique look {look_id}")
        return BoutiqueLookResponse(**look_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error getting boutique look {look_id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the boutique look",
        ) from e


@router.post(
    "",
    response_model=BoutiqueLookResponse,
    summary="Create boutique look",
    description="Create a new boutique look (requires authentication).",
    status_code=status.HTTP_201_CREATED,
    tags=["catalog"],  # Appears under catalog in API docs
    responses={
        201: {"description": "Boutique look created successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def create_look(
    look_data: BoutiqueLookCreate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BoutiqueLookResponse:
    """
    Create a new boutique look for the authenticated boutique owner.

    The look will be automatically linked to the authenticated user's boutique.

    **Validation:**
    - `product_ids` must contain 2-5 catalog item IDs
    - All product IDs must reference existing catalog items owned by the boutique

    **Authorization:**
    - Requires authentication
    - Look is automatically assigned to the authenticated user's boutique
    """
    look_service = LookService()
    try:
        # Pass user_id to link look to authenticated boutique owner
        look = await look_service.create_look(db, look_data, current_user.id)

        # Calculate total_price and fetch product details
        total_price = await look_service.calculate_total_price(db, look.product_ids)
        products = await look_service.get_catalog_items_by_ids(db, look.product_ids)
        look_dict = BoutiqueLookResponse.model_validate(look).model_dump(
            exclude_none=False
        )
        look_dict["total_price"] = total_price
        look_dict["products"] = [
            CatalogItemResponse.model_validate(product).model_dump(exclude_none=False)
            for product in products
        ]

        logger.info(f"Created boutique look '{look.title}' for user: {current_user.id}")
        return BoutiqueLookResponse(**look_dict)
    except ValueError as e:
        logger.warning(f"Boutique look creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error creating boutique look for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the boutique look",
        ) from e


@router.patch(
    "/{look_id}",
    response_model=BoutiqueLookResponse,
    summary="Update boutique look",
    description="Update a boutique look (requires authentication and ownership).",
    status_code=status.HTTP_200_OK,
    tags=["catalog"],  # Appears under catalog in API docs
    responses={
        200: {"description": "Boutique look updated successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        404: {
            "description": "Boutique look not found or you don't have permission to update it"
        },
        500: {"description": "Internal server error"},
    },
)
async def update_look(
    look_id: int,
    look_data: BoutiqueLookUpdate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BoutiqueLookResponse:
    """
    Update a boutique look.

    **Authorization:**
    - Requires authentication
    - You can only update looks created by your boutique

    **Partial Updates:**
    - Only provided fields will be updated
    - All other fields remain unchanged
    """
    look_service = LookService()
    try:
        look = await look_service.update_look(db, look_id, look_data, current_user.id)
        if not look:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Boutique look not found or you don't have permission to update it",
            )

        # Calculate total_price and fetch product details (may have changed if product_ids were updated)
        total_price = await look_service.calculate_total_price(db, look.product_ids)
        products = await look_service.get_catalog_items_by_ids(db, look.product_ids)
        look_dict = BoutiqueLookResponse.model_validate(look).model_dump(
            exclude_none=False
        )
        look_dict["total_price"] = total_price
        look_dict["products"] = [
            CatalogItemResponse.model_validate(product).model_dump(exclude_none=False)
            for product in products
        ]

        logger.info(f"Updated boutique look {look_id} for user: {current_user.id}")
        return BoutiqueLookResponse(**look_dict)
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Boutique look update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error updating boutique look {look_id} for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the boutique look",
        ) from e


@router.delete(
    "/{look_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete boutique look",
    description="Delete a boutique look (requires authentication and ownership).",
    tags=["catalog"],  # Appears under catalog in API docs
    responses={
        204: {"description": "Boutique look deleted successfully"},
        401: {"description": "Unauthorized - authentication required"},
        404: {
            "description": "Boutique look not found or you don't have permission to delete it"
        },
        404: {"description": "Boutique look not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_look(
    look_id: int,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a boutique look.

    **Authorization:**
    - Requires authentication
    - You can only delete looks created by your boutique
    """
    look_service = LookService()
    try:
        deleted = await look_service.delete_look(db, look_id, current_user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Boutique look not found or you don't have permission to delete it",
            )
        logger.info(f"Deleted boutique look {look_id} for user: {current_user.id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error deleting boutique look {look_id} for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the boutique look",
        ) from e
