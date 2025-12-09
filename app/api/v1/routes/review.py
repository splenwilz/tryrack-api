"""
Routes for unified reviews (products and boutiques).
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.auth import WorkOSUserResponse
from app.api.v1.schemas.review import ReviewCreate, ReviewResponse, ReviewUpdate
from app.core.database import get_db
from app.core.dependencies import get_admin_user, get_current_user
from app.models.review import ReviewItemType
from app.services.review import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
)

# Security scheme for optional authentication
security = HTTPBearer(auto_error=False)


@router.get(
    "",
    response_model=List[ReviewResponse],
    summary="Get reviews",
    description="Get all reviews with optional filtering by item_type, item_id, or user_id.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Reviews retrieved successfully"},
        500: {"description": "Internal server error"},
    },
)
async def get_reviews(
    item_type: Optional[str] = Query(
        None,
        description="Filter by item type: 'product' (catalog item) or 'boutique'",
    ),
    item_id: Optional[str] = Query(
        None, description="Filter by item ID (catalog_item_id or boutique_id)"
    ),
    user_id: Optional[str] = Query(None, description="Filter by reviewer user ID"),
    skip: int = Query(
        0, ge=0, description="Number of reviews to skip (for pagination)"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of reviews to return"
    ),
    include_unapproved: bool = Query(
        False, description="Include unapproved reviews (admin only, defaults to False)"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[ReviewResponse]:
    """
    Get reviews with optional filtering.

    **Filtering:**
    - Filter by item_type ("product" or "boutique")
    - Filter by item_id (catalog_item_id or boutique_id)
    - Filter by user_id (reviewer)
    - Pagination with skip/limit
    """
    review_service = ReviewService()
    try:
        reviews = await review_service.get_reviews(
            db,
            item_type=item_type,
            item_id=item_id,
            user_id=user_id,
            skip=skip,
            limit=limit,
            include_unapproved=include_unapproved,
        )
        # Enrich reviews with user information
        enriched_reviews = await review_service._enrich_reviews_with_user_info(
            db, reviews
        )
        # Convert to ReviewResponse objects
        review_responses = [
            ReviewResponse(**review_data) for review_data in enriched_reviews
        ]
        logger.info(f"Retrieved {len(review_responses)} reviews")
        return review_responses
    except Exception as e:
        logger.error(
            f"Unexpected error getting reviews: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving reviews",
        ) from e


@router.get(
    "/{review_id}",
    response_model=ReviewResponse,
    summary="Get review",
    description="Get a specific review by ID.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Review retrieved successfully"},
        404: {"description": "Review not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_review(
    review_id: int,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """
    Get a specific review by ID.

    If authenticated, includes user_has_liked status.
    """
    review_service = ReviewService()
    try:
        review = await review_service.get_review(db, review_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
            )
        # Enrich with user information (include current_user_id if authenticated)
        current_user_id = None
        if credentials:
            try:
                current_user = await get_current_user(credentials)
                current_user_id = current_user.id
            except HTTPException:
                # Invalid token, but continue without user context
                pass
        enriched = await review_service._enrich_reviews_with_user_info(
            db, [review], current_user_id
        )
        review_data = enriched[0] if enriched else {}
        review_response = ReviewResponse(**review_data)
        logger.info(f"Retrieved review {review_id}")
        return review_response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error getting review {review_id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the review",
        ) from e


@router.get(
    "/items/{item_type}/{item_id}",
    response_model=List[ReviewResponse],
    summary="Get reviews for item",
    description="Get all reviews for a specific item (product or boutique).",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Reviews retrieved successfully"},
        400: {"description": "Invalid item_type"},
        500: {"description": "Internal server error"},
    },
)
async def get_item_reviews(
    item_type: str,
    item_id: str,
    skip: int = Query(
        0, ge=0, description="Number of reviews to skip (for pagination)"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of reviews to return"
    ),
    include_unapproved: bool = Query(
        False, description="Include unapproved reviews (admin only, defaults to False)"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[ReviewResponse]:
    """
    Get all reviews for a specific item.

    **Parameters:**
    - item_type: "product" or "boutique"
    - item_id: ID of the catalog item or boutique
    - include_unapproved: Include unapproved reviews (admin only)
    """
    if item_type not in ["product", "boutique"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="item_type must be 'product' or 'boutique'",
        )

    review_service = ReviewService()
    try:
        reviews = await review_service.get_reviews_for_item(
            db,
            item_type=item_type,
            item_id=item_id,
            skip=skip,
            limit=limit,
            include_unapproved=include_unapproved,
        )
        # Enrich reviews with user information (no current_user_id for public endpoint)
        enriched_reviews = await review_service._enrich_reviews_with_user_info(
            db, reviews
        )
        # Convert to ReviewResponse objects
        review_responses = [
            ReviewResponse(**review_data) for review_data in enriched_reviews
        ]
        logger.info(
            f"Retrieved {len(review_responses)} reviews for {item_type} {item_id}"
        )
        return review_responses
    except Exception as e:
        logger.error(
            f"Unexpected error getting reviews for {item_type} {item_id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving reviews",
        ) from e


@router.post(
    "",
    response_model=ReviewResponse,
    summary="Create review",
    description="Create a new review for a product or boutique.",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Review created successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Item not found"},
        409: {"description": "Review already exists for this item"},
        500: {"description": "Internal server error"},
    },
)
async def create_review(
    review_data: ReviewCreate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """
    Create a new review for a product or boutique.

    **Authorization:**
    - Requires authentication
    - Users can review any item
    - Users can only create one review per item (update existing instead)

    **Validation:**
    - Item must exist (catalog item or boutique)
    - Rating must be between 1-5
    - Maximum 10 images per review
    """
    review_service = ReviewService()
    try:
        review = await review_service.create_review(db, review_data, current_user.id)
        # Enrich with user information
        enriched = await review_service._enrich_reviews_with_user_info(db, [review])
        review_data_dict = enriched[0] if enriched else {}
        review_response = ReviewResponse(**review_data_dict)
        logger.info(
            f"Created review {review_response.id} for {review_data.item_type} {review_data.item_id} by user {current_user.id}"
        )
        return review_response
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            logger.warning(f"Review creation failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=error_msg
            ) from e
        elif "already reviewed" in error_msg.lower():
            logger.warning(f"Review creation failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=error_msg
            ) from e
        else:
            logger.warning(f"Review creation failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
            ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error creating review for {review_data.item_type} {review_data.item_id} by user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the review",
        ) from e


@router.patch(
    "/{review_id}",
    response_model=ReviewResponse,
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
    review_data: ReviewUpdate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """
    Update a review.

    **Authorization:**
    - Users can only update their own reviews
    """
    review_service = ReviewService()
    try:
        review = await review_service.update_review(
            db, review_id, current_user.id, review_data
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found or you don't have permission to update it",
            )
        # Enrich with user information (include current_user_id to check if they liked)
        enriched = await review_service._enrich_reviews_with_user_info(
            db, [review], current_user.id
        )
        review_data_dict = enriched[0] if enriched else {}
        review_response = ReviewResponse(**review_data_dict)
        logger.info(f"Updated review {review_id} for user: {current_user.id}")
        return review_response
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


@router.patch(
    "/{review_id}/approve",
    response_model=ReviewResponse,
    summary="Approve review (Admin)",
    description="Approve a review for public display (admin only).",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Review approved successfully"},
        401: {"description": "Unauthorized - authentication required"},
        403: {"description": "Forbidden - admin access required"},
        404: {"description": "Review not found"},
        500: {"description": "Internal server error"},
    },
)
async def approve_review(
    review_id: int,
    admin_user: WorkOSUserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """
    Approve a review for public display.

    **Authorization:**
    - Requires admin authentication
    - Only admins can approve reviews
    """
    review_service = ReviewService()
    try:
        review = await review_service.approve_review(db, review_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found",
            )
        logger.info(f"Admin {admin_user.id} approved review {review_id}")
        return review
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Review approval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error approving review {review_id} by admin {admin_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while approving the review",
        ) from e


@router.patch(
    "/{review_id}/reject",
    response_model=ReviewResponse,
    summary="Reject review (Admin)",
    description="Reject a review to hide it from public display (admin only).",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Review rejected successfully"},
        401: {"description": "Unauthorized - authentication required"},
        403: {"description": "Forbidden - admin access required"},
        404: {"description": "Review not found"},
        500: {"description": "Internal server error"},
    },
)
async def reject_review(
    review_id: int,
    admin_user: WorkOSUserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """
    Reject a review to hide it from public display.

    **Authorization:**
    - Requires admin authentication
    - Only admins can reject reviews
    """
    review_service = ReviewService()
    try:
        review = await review_service.reject_review(db, review_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found",
            )
        # Enrich with user information (include admin_user_id to check if they liked)
        enriched = await review_service._enrich_reviews_with_user_info(
            db, [review], admin_user.id
        )
        review_data_dict = enriched[0] if enriched else {}
        review_response = ReviewResponse(**review_data_dict)
        logger.info(f"Admin {admin_user.id} rejected review {review_id}")
        return review_response
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Review rejection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error rejecting review {review_id} by admin {admin_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while rejecting the review",
        ) from e


@router.post(
    "/{review_id}/like",
    summary="Like review",
    description="Mark a review as 'found helpful' (like).",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Review liked successfully"},
        400: {"description": "Review not found or already liked"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def like_review(
    review_id: int,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Like a review (mark as "found helpful").

    **Authorization:**
    - Requires authentication
    - Users can like any review
    - Users can only like a review once (idempotent - returns success if already liked)
    """
    review_service = ReviewService()
    try:
        liked = await review_service.like_review(db, review_id, current_user.id)
        if liked:
            logger.info(f"User {current_user.id} liked review {review_id}")
            return {"message": "Review liked successfully", "liked": True}
        else:
            # Already liked - return success (idempotent)
            logger.debug(f"User {current_user.id} already liked review {review_id}")
            return {"message": "Review already liked", "liked": True}
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            logger.warning(f"Like failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=error_msg
            ) from e
        else:
            logger.warning(f"Like failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
            ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error liking review {review_id} by user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while liking the review",
        ) from e


@router.delete(
    "/{review_id}/like",
    summary="Unlike review",
    description="Remove 'found helpful' mark from a review (unlike).",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Review unliked successfully"},
        400: {"description": "Review not found"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Review not found or not liked"},
        500: {"description": "Internal server error"},
    },
)
async def unlike_review(
    review_id: int,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Unlike a review (remove "found helpful" mark).

    **Authorization:**
    - Requires authentication
    - Users can unlike reviews they previously liked
    - Idempotent - returns success even if not liked
    """
    review_service = ReviewService()
    try:
        unliked = await review_service.unlike_review(db, review_id, current_user.id)
        if unliked:
            logger.info(f"User {current_user.id} unliked review {review_id}")
            return {"message": "Review unliked successfully", "liked": False}
        else:
            # Not liked - return success (idempotent)
            logger.debug(f"User {current_user.id} has not liked review {review_id}")
            return {"message": "Review was not liked", "liked": False}
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            logger.warning(f"Unlike failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=error_msg
            ) from e
        else:
            logger.warning(f"Unlike failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
            ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error unliking review {review_id} by user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while unliking the review",
        ) from e


@router.delete(
    "/{review_id}",
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
    review_service = ReviewService()
    try:
        deleted = await review_service.delete_review(db, review_id, current_user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found or you don't have permission to delete it",
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
