"""
Review service for managing unified reviews (products and boutiques).

Reference: https://docs.sqlalchemy.org/en/21/orm/queryguide/
"""

import asyncio
import logging
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from workos import WorkOSClient

from app.api.v1.schemas.review import ReviewCreate, ReviewUpdate
from app.core.config import settings
from app.models.boutique import Boutique
from app.models.catalog import CatalogItem
from app.models.review import Review, ReviewItemType
from app.models.review_like import ReviewLike
from app.models.virtual_try_on import VirtualTryOn

logger = logging.getLogger(__name__)


class ReviewService:
    """Service for managing unified reviews"""

    def __init__(self):
        """Initialize WorkOS client for fetching user information."""
        self.workos_client = WorkOSClient(
            api_key=settings.WORKOS_API_KEY, client_id=settings.WORKOS_CLIENT_ID
        )
        # Cache for user information to avoid repeated API calls
        self._user_cache: Dict[str, Dict[str, Optional[str]]] = {}

    async def _get_user_info(self, user_id: str) -> Optional[Dict]:
        """
        Get full user information from WorkOS.

        Uses caching to avoid repeated API calls for the same user.

        Args:
            user_id: WorkOS user ID

        Returns:
            Dict with full user information (WorkOSUserResponse fields) or None if fetch fails
        """
        # Check cache first
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            # Fetch user from WorkOS
            workos_user = await asyncio.to_thread(
                self.workos_client.user_management.get_user, user_id=user_id
            )
            # Build user dict with all WorkOSUserResponse fields
            user_info = {
                "object": workos_user.object,
                "id": workos_user.id,
                "email": workos_user.email,
                "first_name": workos_user.first_name,
                "last_name": workos_user.last_name,
                "email_verified": workos_user.email_verified,
                "profile_picture_url": workos_user.profile_picture_url,
                "created_at": workos_user.created_at,
                "updated_at": workos_user.updated_at,
            }
            # Cache the result
            self._user_cache[user_id] = user_info
            return user_info
        except Exception as e:
            logger.warning(f"Failed to fetch user info for {user_id}: {e}")
            # Return None if fetch fails
            self._user_cache[user_id] = None
            return None

    async def _enrich_reviews_with_user_info(
        self,
        db: AsyncSession,
        reviews: List[Review],
        current_user_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Enrich review objects with user name information from WorkOS, verification status, and like counts.

        Args:
            db: Database session (needed for verification checks)
            reviews: List of Review objects
            current_user_id: Optional current user ID to check if they liked each review

        Returns:
            List of dictionaries with review data, user info, verification status, and like information
        """
        if not reviews:
            return []

        # Get unique user IDs
        user_ids = list(set(review.user_id for review in reviews if review.user_id))

        # Fetch user info for all unique users in parallel
        user_info_tasks = [self._get_user_info(user_id) for user_id in user_ids]
        user_info_results = await asyncio.gather(
            *user_info_tasks, return_exceptions=True
        )

        # Create a mapping of user_id to user info
        user_info_map = {}
        for user_id, user_info in zip(user_ids, user_info_results):
            if isinstance(user_info, Exception):
                logger.warning(f"Error fetching user info for {user_id}: {user_info}")
                user_info_map[user_id] = None
            else:
                user_info_map[user_id] = user_info

        # Enrich reviews with user info and verification status
        enriched_reviews = []
        for review in reviews:
            review_dict = {
                "id": review.id,
                "item_type": review.item_type,
                "item_id": review.item_id,
                "user_id": review.user_id,
                "rating": review.rating,
                "comment": review.comment,
                "images": review.images,
                "review_metadata": review.review_metadata,
                "is_approved": review.is_approved,
                "created_at": review.created_at,
                "updated_at": review.updated_at,
            }
            # Add full user object
            user_info = user_info_map.get(review.user_id)
            review_dict["user"] = user_info

            # Check verification status
            is_verified, verification_type, verification_level = (
                await self._check_user_verification(
                    db, review.user_id, review.item_type, review.item_id, user_info
                )
            )
            review_dict["is_verified"] = is_verified
            review_dict["verification_type"] = verification_type
            review_dict["verification_level"] = verification_level

            # Get like count and check if current user has liked
            try:
                like_count_result = await db.execute(
                    select(func.count(ReviewLike.id)).where(
                        ReviewLike.review_id == review.id
                    )
                )
                like_count = like_count_result.scalar() or 0
            except Exception as e:
                logger.warning(f"Error getting like count for review {review.id}: {e}")
                like_count = 0
            review_dict["like_count"] = like_count

            # Check if current user has liked this review
            user_has_liked = False
            if current_user_id:
                try:
                    user_like_result = await db.execute(
                        select(ReviewLike).where(
                            ReviewLike.review_id == review.id,
                            ReviewLike.user_id == current_user_id,
                        )
                    )
                    user_has_liked = user_like_result.scalar_one_or_none() is not None
                except Exception as e:
                    logger.warning(f"Error checking user like for review {review.id}: {e}")
                    user_has_liked = False
            review_dict["user_has_liked"] = user_has_liked

            enriched_reviews.append(review_dict)

        return enriched_reviews

    async def _check_user_verification(
        self,
        db: AsyncSession,
        user_id: str,
        item_type: str,
        item_id: str,
        user: Optional[Dict] = None,
    ) -> tuple[bool, Optional[str], int]:
        """
        Check user verification status for reviewing an item.

        Verification tiers (in order of trust, lower number = higher trust):
        - Level 0: Purchase verification (highest trust) - TODO: Implement when order/purchase system is added
        - Level 1: Virtual try-on verification (user has tried on the product + email verified)
        - Level 2: Email verified + profile complete (first_name, last_name provided)
        - Level 3: Email verified only (lowest trust, basic legitimacy check)

        Args:
            db: Database session
            user_id: WorkOS user ID
            item_type: Type of item ("product" or "boutique")
            item_id: ID of the item being reviewed
            user: Optional user dict from WorkOS (should include email_verified, first_name, last_name, etc.)

        Returns:
            Tuple of (is_verified, verification_type, verification_level)
            - is_verified: bool indicating if user is verified
            - verification_type: "purchase", "try_on", "email_profile", "email", or None
            - verification_level: 0-3 (0 is highest trust, 3 is lowest)
        """
        # Tier 0: Purchase verification (highest trust)
        # TODO: Implement when order/purchase system is added
        # Check if user has purchased this product/boutique
        # if item_type == "product":
        #     # Check for order with this product_id, status="delivered", payment_status="paid"
        #     has_purchase = await self._check_purchase_verification(db, user_id, item_id)
        #     if has_purchase:
        #         return (True, "purchase", 0)
        # elif item_type == "boutique":
        #     # Check for any purchase from this boutique
        #     has_purchase = await self._check_boutique_purchase_verification(db, user_id, item_id)
        #     if has_purchase:
        #         return (True, "purchase", 0)

        # Tier 1: Virtual try-on verification (for products only)
        if item_type == "product":
            # Check if user has virtual try-on session for this product
            # Look for sessions where selected_items contains this product_id
            try:
                result = await db.execute(
                    select(VirtualTryOn).where(VirtualTryOn.user_id == user_id)
                )
                sessions = result.scalars().all()

                # Check if any session has this product in selected_items
                for session in sessions:
                    if session.selected_items:
                        for item in session.selected_items:
                            # Check if this is a boutique item with matching product_id
                            if (
                                isinstance(item, dict)
                                and item.get("item_type") == "boutique"
                                and item.get("product_id") == item_id
                            ):
                                # User has tried on this product
                                if user and user.get("email_verified"):
                                    return (True, "try_on", 1)
            except Exception as e:
                logger.warning(
                    f"Error checking try-on verification for user {user_id}, product {item_id}: {e}"
                )

        # Tier 2: Email verified + profile complete
        if user:
            email_verified = user.get("email_verified", False)
            has_first_name = bool(user.get("first_name"))
            has_last_name = bool(user.get("last_name"))

            if email_verified and has_first_name and has_last_name:
                return (True, "email_profile", 2)

        # Tier 3: Email verified only (lowest trust)
        if user and user.get("email_verified"):
            return (True, "email", 3)

        # Not verified
        return (False, None, 0)

    async def get_review(self, db: AsyncSession, review_id: int) -> Optional[Review]:
        """
        Get a review by ID.

        Args:
            db: Database session
            review_id: Review ID

        Returns:
            Review if found, None otherwise
        """
        result = await db.execute(select(Review).where(Review.id == review_id))
        return result.scalar_one_or_none()

    async def get_reviews(
        self,
        db: AsyncSession,
        item_type: Optional[str] = None,
        item_id: Optional[str] = None,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        include_unapproved: bool = False,
    ) -> List[Review]:
        """
        Get reviews with optional filtering.

        Args:
            db: Database session
            item_type: Optional filter by item type ("product" or "boutique")
            item_id: Optional filter by item ID
            user_id: Optional filter by reviewer user ID
            skip: Number of reviews to skip (for pagination)
            limit: Maximum number of reviews to return
            include_unapproved: If True, includes unapproved reviews (admin only)

        Returns:
            List of reviews
        """
        query = select(Review)

        if item_type:
            query = query.where(Review.item_type == item_type)

        if item_id:
            query = query.where(Review.item_id == item_id)

        if user_id:
            query = query.where(Review.user_id == user_id)

        # By default, only show approved reviews unless explicitly requested
        if not include_unapproved:
            query = query.where(Review.is_approved.is_(True))

        query = query.order_by(Review.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_reviews_for_item(
        self,
        db: AsyncSession,
        item_type: str,
        item_id: str,
        skip: int = 0,
        limit: int = 100,
        include_unapproved: bool = False,
    ) -> List[Review]:
        """
        Get all reviews for a specific item (product or boutique).

        Args:
            db: Database session
            item_type: Type of item ("product" or "boutique")
            item_id: ID of the item
            skip: Number of reviews to skip (for pagination)
            limit: Maximum number of reviews to return
            include_unapproved: If True, includes unapproved reviews (admin only)

        Returns:
            List of reviews for the item
        """
        return await self.get_reviews(
            db,
            item_type=item_type,
            item_id=item_id,
            skip=skip,
            limit=limit,
            include_unapproved=include_unapproved,
        )

    async def create_review(
        self,
        db: AsyncSession,
        review_data: ReviewCreate,
        user_id: str,
    ) -> Review:
        """
        Create a new review.

        Args:
            db: Database session
            review_data: Review data to create
            user_id: ID of the user creating the review

        Returns:
            Created review

        Raises:
            ValueError: If validation fails or item doesn't exist
        """
        # Validate that the item exists
        if review_data.item_type == ReviewItemType.PRODUCT:
            # Verify catalog item exists
            result = await db.execute(
                select(CatalogItem).where(CatalogItem.id == int(review_data.item_id))
            )
            item = result.scalar_one_or_none()
            if not item:
                raise ValueError(
                    f"Catalog item with ID {review_data.item_id} not found"
                )
        elif review_data.item_type == ReviewItemType.BOUTIQUE:
            # Verify boutique exists
            result = await db.execute(
                select(Boutique).where(Boutique.id == int(review_data.item_id))
            )
            item = result.scalar_one_or_none()
            if not item:
                raise ValueError(f"Boutique with ID {review_data.item_id} not found")
        else:
            raise ValueError(f"Invalid item_type: {review_data.item_type}")

        # Check if user already reviewed this item
        existing_review_result = await db.execute(
            select(Review).where(
                Review.item_type == review_data.item_type,
                Review.item_id == review_data.item_id,
                Review.user_id == user_id,
            )
        )
        existing_review = existing_review_result.scalar_one_or_none()
        if existing_review:
            raise ValueError(
                f"You have already reviewed this {review_data.item_type}. Update your existing review instead."
            )

        # Create review (is_approved defaults to False for moderation)
        review = Review(
            item_type=review_data.item_type,
            item_id=review_data.item_id,
            user_id=user_id,
            rating=review_data.rating,
            comment=review_data.comment,
            images=review_data.images,
            review_metadata=review_data.review_metadata,
            is_approved=False,  # Default to False for admin moderation
        )

        db.add(review)

        try:
            await db.flush()
            await db.refresh(review)  # Refresh to get timestamps
            logger.info(
                f"Created review {review.id} for {review_data.item_type} {review_data.item_id} by user {user_id}"
            )
            return review
        except IntegrityError as e:
            await db.rollback()
            error_str = str(e.orig) if hasattr(e, "orig") else str(e)
            logger.error(
                f"Failed to create review due to database error: {error_str}",
                exc_info=True,
            )
            raise ValueError(
                "Failed to create review due to database constraints"
            ) from e

    async def update_review(
        self,
        db: AsyncSession,
        review_id: int,
        user_id: str,
        review_data: ReviewUpdate,
    ) -> Optional[Review]:
        """
        Update a review.

        Args:
            db: Database session
            review_id: Review ID
            user_id: ID of the user updating the review (for ownership verification)
            review_data: Review data to update

        Returns:
            Updated review if found and user owns it, None otherwise

        Raises:
            ValueError: If validation fails
        """
        result = await db.execute(select(Review).where(Review.id == review_id))
        review = result.scalar_one_or_none()

        if not review:
            return None

        # Verify ownership
        if review.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to update review {review_id} owned by {review.user_id}"
            )
            return None

        # Update fields
        update_data = review_data.model_dump(exclude_unset=True)
        if not update_data:
            return review  # No data to update

        # Note: is_approved can only be updated by admins (check should be done at route level)
        for field, value in update_data.items():
            setattr(review, field, value)

        # Update timestamp
        from datetime import datetime, timezone

        review.updated_at = datetime.now(timezone.utc)

        try:
            await db.flush()
            await db.refresh(review)  # Refresh to get updated timestamps
            logger.info(f"Updated review {review_id} by user {user_id}")
            return review
        except IntegrityError as e:
            await db.rollback()
            error_str = str(e.orig) if hasattr(e, "orig") else str(e)
            logger.error(
                f"Failed to update review due to database error: {error_str}",
                exc_info=True,
            )
            raise ValueError(
                "Failed to update review due to database constraints"
            ) from e

    async def approve_review(
        self,
        db: AsyncSession,
        review_id: int,
    ) -> Optional[Review]:
        """
        Approve a review (admin only).

        Args:
            db: Database session
            review_id: Review ID to approve

        Returns:
            Approved review if found, None otherwise

        Raises:
            ValueError: If validation fails
        """
        result = await db.execute(select(Review).where(Review.id == review_id))
        review = result.scalar_one_or_none()

        if not review:
            return None

        # Approve the review
        review.is_approved = True

        # Update timestamp
        from datetime import datetime, timezone

        review.updated_at = datetime.now(timezone.utc)

        try:
            await db.flush()
            await db.refresh(review)
            logger.info(f"Approved review {review_id}")
            return review
        except IntegrityError as e:
            await db.rollback()
            error_str = str(e.orig) if hasattr(e, "orig") else str(e)
            logger.error(
                f"Failed to approve review due to database error: {error_str}",
                exc_info=True,
            )
            raise ValueError(
                "Failed to approve review due to database constraints"
            ) from e

    async def reject_review(
        self,
        db: AsyncSession,
        review_id: int,
    ) -> Optional[Review]:
        """
        Reject a review (admin only).

        Args:
            db: Database session
            review_id: Review ID to reject

        Returns:
            Rejected review if found, None otherwise

        Raises:
            ValueError: If validation fails
        """
        result = await db.execute(select(Review).where(Review.id == review_id))
        review = result.scalar_one_or_none()

        if not review:
            return None

        # Reject the review
        review.is_approved = False

        # Update timestamp
        from datetime import datetime, timezone

        review.updated_at = datetime.now(timezone.utc)

        try:
            await db.flush()
            await db.refresh(review)
            logger.info(f"Rejected review {review_id}")
            return review
        except IntegrityError as e:
            await db.rollback()
            error_str = str(e.orig) if hasattr(e, "orig") else str(e)
            logger.error(
                f"Failed to reject review due to database error: {error_str}",
                exc_info=True,
            )
            raise ValueError(
                "Failed to reject review due to database constraints"
            ) from e

    async def delete_review(
        self,
        db: AsyncSession,
        review_id: int,
        user_id: str,
    ) -> bool:
        """
        Delete a review.

        Args:
            db: Database session
            review_id: Review ID
            user_id: ID of the user deleting the review (for ownership verification)

        Returns:
            True if review was deleted, False if not found or user doesn't own it
        """
        result = await db.execute(select(Review).where(Review.id == review_id))
        review = result.scalar_one_or_none()

        if not review:
            return False

        # Verify ownership
        if review.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to delete review {review_id} owned by {review.user_id}"
            )
            return False

        await db.delete(review)
        await db.flush()

        logger.info(f"Deleted review {review_id} by user {user_id}")
        return True

    async def like_review(self, db: AsyncSession, review_id: int, user_id: str) -> bool:
        """
        Like a review (mark as "found helpful").

        Args:
            db: Database session
            review_id: Review ID to like
            user_id: WorkOS user ID who is liking the review

        Returns:
            True if like was created, False if already liked

        Raises:
            ValueError: If review doesn't exist
        """
        # Check if review exists
        result = await db.execute(select(Review).where(Review.id == review_id))
        review = result.scalar_one_or_none()
        if not review:
            raise ValueError(f"Review with ID {review_id} not found")

        # Check if user already liked this review
        existing_like_result = await db.execute(
            select(ReviewLike).where(
                ReviewLike.review_id == review_id, ReviewLike.user_id == user_id
            )
        )
        existing_like = existing_like_result.scalar_one_or_none()
        if existing_like:
            logger.debug(f"User {user_id} already liked review {review_id}")
            return False  # Already liked

        # Create like
        like = ReviewLike(review_id=review_id, user_id=user_id)
        db.add(like)

        try:
            await db.flush()
            logger.info(f"User {user_id} liked review {review_id}")
            return True
        except IntegrityError as e:
            await db.rollback()
            error_str = str(e.orig) if hasattr(e, "orig") else str(e)
            logger.error(
                f"Failed to like review due to database error: {error_str}",
                exc_info=True,
            )
            raise ValueError("Failed to like review due to database constraints") from e

    async def unlike_review(
        self, db: AsyncSession, review_id: int, user_id: str
    ) -> bool:
        """
        Unlike a review (remove "found helpful" mark).

        Args:
            db: Database session
            review_id: Review ID to unlike
            user_id: WorkOS user ID who is unliking the review

        Returns:
            True if like was removed, False if not liked

        Raises:
            ValueError: If review doesn't exist
        """
        # Check if review exists
        result = await db.execute(select(Review).where(Review.id == review_id))
        review = result.scalar_one_or_none()
        if not review:
            raise ValueError(f"Review with ID {review_id} not found")

        # Find existing like
        like_result = await db.execute(
            select(ReviewLike).where(
                ReviewLike.review_id == review_id, ReviewLike.user_id == user_id
            )
        )
        like = like_result.scalar_one_or_none()
        if not like:
            logger.debug(f"User {user_id} has not liked review {review_id}")
            return False  # Not liked

        # Delete like
        await db.delete(like)

        try:
            await db.flush()
            logger.info(f"User {user_id} unliked review {review_id}")
            return True
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to unlike review: {e}",
                exc_info=True,
            )
            raise ValueError("Failed to unlike review") from e
