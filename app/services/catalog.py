"""
Catalog service for managing boutique catalog items and reviews.

Reference: https://docs.sqlalchemy.org/en/21/orm/queryguide/
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.catalog import (
    CatalogItemCreate,
    CatalogItemUpdate,
    CatalogReviewCreate,
    CatalogReviewUpdate,
)
from app.models.boutique import Boutique
from app.models.catalog import CatalogItem, CatalogItemStatus, CatalogReview

logger = logging.getLogger(__name__)


class CatalogService:
    """Service for managing catalog items and reviews"""

    async def get_catalog_item(
        self, db: AsyncSession, item_id: int
    ) -> Optional[CatalogItem]:
        """
        Get a catalog item by ID.

        Args:
            db: Database session
            item_id: Item ID

        Returns:
            Catalog item if found, None otherwise
        """
        result = await db.execute(select(CatalogItem).where(CatalogItem.id == item_id))
        return result.scalar_one_or_none()

    async def get_catalog_items(
        self,
        db: AsyncSession,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        status: Optional[CatalogItemStatus] = None,
        boutique_id: Optional[int] = None,
        user_id: Optional[
            str
        ] = None,  # For backward compatibility - gets boutique_id from user_id
        skip: int = 0,
        limit: int = 100,
    ) -> List[CatalogItem]:
        """
        Get catalog items with optional filtering.

        Args:
            db: Database session
            category: Optional category filter
            brand: Optional brand filter
            status: Optional status filter
            boutique_id: Optional boutique ID filter (preferred)
            user_id: Optional boutique owner user ID filter (converted to boutique_id)
            skip: Number of items to skip (for pagination)
            limit: Maximum number of items to return

        Returns:
            List of catalog items
        """
        query = select(CatalogItem)

        if category:
            query = query.where(CatalogItem.category == category)

        if brand:
            query = query.where(CatalogItem.brand == brand)

        if status:
            query = query.where(CatalogItem.status == status.value)

        # Handle boutique_id or user_id (for backward compatibility)
        if boutique_id:
            query = query.where(CatalogItem.boutique_id == boutique_id)
        elif user_id:
            # Get boutique_id from user_id
            boutique_result = await db.execute(
                select(Boutique).where(Boutique.owner_id == user_id)
            )
            boutique = boutique_result.scalar_one_or_none()
            if boutique:
                query = query.where(CatalogItem.boutique_id == boutique.id)
            else:
                # Return empty list if no boutique found
                return []

        query = query.order_by(CatalogItem.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def create_catalog_item(
        self, db: AsyncSession, item_data: CatalogItemCreate, user_id: str
    ) -> CatalogItem:
        """
        Create a new catalog item.

        Args:
            db: Database session
            item_data: Catalog item data
            user_id: ID of the boutique owner creating this item (required)

        Returns:
            Created catalog item

        Raises:
            ValueError: If validation fails
        """
        # Get boutique by owner_id
        boutique_result = await db.execute(
            select(Boutique).where(Boutique.owner_id == user_id)
        )
        boutique = boutique_result.scalar_one_or_none()
        if not boutique:
            raise ValueError(
                f"No boutique found for user {user_id}. Please complete boutique onboarding first."
            )

        item_dict = item_data.model_dump(exclude_unset=True)

        # Set boutique_id - required for linking item to boutique
        item_dict["boutique_id"] = boutique.id

        # Set default status if not provided
        if "status" not in item_dict or item_dict["status"] is None:
            item_dict["status"] = CatalogItemStatus.ACTIVE.value
        elif isinstance(item_dict["status"], CatalogItemStatus):
            item_dict["status"] = item_dict["status"].value

        # Convert cost_price and discount_price to None if not provided
        if "cost_price" in item_dict and item_dict["cost_price"] is None:
            item_dict.pop("cost_price")
        if "discount_price" in item_dict and item_dict["discount_price"] is None:
            item_dict.pop("discount_price")

        catalog_item = CatalogItem(**item_dict)
        db.add(catalog_item)

        try:
            await db.flush()
            logger.info(
                f"Created catalog item '{catalog_item.name}' (ID: {catalog_item.id})"
            )
            return catalog_item
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to create catalog item due to database error", exc_info=True
            )
            raise ValueError(
                "Failed to create catalog item due to database constraints"
            ) from e

    async def update_catalog_item(
        self,
        db: AsyncSession,
        item_id: int,
        item_data: CatalogItemUpdate,
        user_id: str,
    ) -> Optional[CatalogItem]:
        """
        Update a catalog item.

        Only provided fields will be updated (partial update).

        Args:
            db: Database session
            item_id: Item ID
            item_data: Update data (all fields optional)
            user_id: User ID (for authorization - users can only update their own items)

        Returns:
            Updated catalog item if found and authorized, None otherwise
        """
        catalog_item = await self.get_catalog_item(db, item_id)
        if not catalog_item:
            return None

        # Verify ownership via boutique
        boutique_result = await db.execute(
            select(Boutique).where(Boutique.owner_id == user_id)
        )
        boutique = boutique_result.scalar_one_or_none()
        if not boutique or catalog_item.boutique_id != boutique.id:
            logger.warning(
                f"User {user_id} attempted to update catalog item {item_id} not owned by their boutique"
            )
            return None

        update_data = item_data.model_dump(exclude_unset=True)

        # Validate discount_price against final price (from update or existing item)
        # This handles partial updates where only discount_price or only price is updated
        if "discount_price" in update_data or "price" in update_data:
            # Determine the final values: use updated values if provided, otherwise existing values
            final_price = (
                update_data.get("price")
                if "price" in update_data
                else catalog_item.price
            )
            final_discount_price = (
                update_data.get("discount_price")
                if "discount_price" in update_data
                else catalog_item.discount_price
            )
            # Validate if both prices exist
            if final_price is not None and final_discount_price is not None:
                if final_discount_price >= final_price:
                    raise ValueError("Discount price must be less than regular price")

        # Convert enum to string value for status field
        if "status" in update_data and isinstance(
            update_data["status"], CatalogItemStatus
        ):
            update_data["status"] = update_data["status"].value

        for field, value in update_data.items():
            setattr(catalog_item, field, value)

        # Manually set updated_at
        catalog_item.updated_at = datetime.now(timezone.utc)

        try:
            await db.flush()
            logger.info(f"Updated catalog item {item_id}")
            return catalog_item
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to update catalog item due to database error", exc_info=True
            )
            raise ValueError(
                "Failed to update catalog item due to database constraints"
            ) from e

    async def delete_catalog_item(
        self, db: AsyncSession, item_id: int, user_id: str
    ) -> bool:
        """
        Delete a catalog item.

        Args:
            db: Database session
            item_id: Item ID
            user_id: User ID (for authorization - users can only delete their own items)

        Returns:
            True if item was deleted, False if not found or not authorized
        """
        catalog_item = await self.get_catalog_item(db, item_id)
        if not catalog_item:
            return False

        # Verify ownership via boutique
        boutique_result = await db.execute(
            select(Boutique).where(Boutique.owner_id == user_id)
        )
        boutique = boutique_result.scalar_one_or_none()
        if not boutique or catalog_item.boutique_id != boutique.id:
            logger.warning(
                f"User {user_id} attempted to delete catalog item {item_id} not owned by their boutique"
            )
            return False

        await db.delete(catalog_item)
        await db.flush()
        logger.info(f"Deleted catalog item {item_id} for user: {user_id}")
        return True

    async def increment_views(
        self, db: AsyncSession, item_id: int
    ) -> Optional[CatalogItem]:
        """
        Increment view count for a catalog item (atomic operation).

        Args:
            db: Database session
            item_id: Item ID

        Returns:
            Updated catalog item if found, None otherwise
        """
        stmt = (
            update(CatalogItem)
            .where(CatalogItem.id == item_id)
            .values(views=CatalogItem.views + 1)
            .returning(CatalogItem)
        )

        try:
            result = await db.execute(stmt)
            await db.flush()
            return result.scalar_one_or_none()
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to increment views due to database error", exc_info=True
            )
            raise ValueError(
                "Failed to increment views due to database constraints"
            ) from e

    # Review methods
    async def get_review(
        self, db: AsyncSession, review_id: int
    ) -> Optional[CatalogReview]:
        """Get a review by ID."""
        result = await db.execute(
            select(CatalogReview).where(CatalogReview.id == review_id)
        )
        return result.scalar_one_or_none()

    async def get_reviews_for_item(
        self,
        db: AsyncSession,
        item_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[CatalogReview]:
        """Get reviews for a specific catalog item."""
        query = (
            select(CatalogReview)
            .where(CatalogReview.catalog_item_id == item_id)
            .order_by(CatalogReview.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create_review(
        self,
        db: AsyncSession,
        item_id: int,
        user_id: str,
        review_data: CatalogReviewCreate,
    ) -> CatalogReview:
        """
        Create a new review for a catalog item.

        Args:
            db: Database session
            item_id: Catalog item ID
            user_id: User ID writing the review
            review_data: Review data

        Returns:
            Created review

        Raises:
            ValueError: If validation fails or item doesn't exist
        """
        # Verify item exists
        catalog_item = await self.get_catalog_item(db, item_id)
        if not catalog_item:
            raise ValueError("Catalog item not found")

        review_dict = review_data.model_dump()
        review = CatalogReview(catalog_item_id=item_id, user_id=user_id, **review_dict)
        db.add(review)

        try:
            await db.flush()
            logger.info(
                f"Created review {review.id} for catalog item {item_id} by user {user_id}"
            )
            return review
        except IntegrityError as e:
            await db.rollback()
            logger.error("Failed to create review due to database error", exc_info=True)
            raise ValueError(
                "Failed to create review due to database constraints"
            ) from e

    async def update_review(
        self,
        db: AsyncSession,
        review_id: int,
        user_id: str,
        review_data: CatalogReviewUpdate,
    ) -> Optional[CatalogReview]:
        """
        Update a review (only by the user who created it).

        Args:
            db: Database session
            review_id: Review ID
            user_id: User ID (for authorization)
            review_data: Update data

        Returns:
            Updated review if found and authorized, None otherwise
        """
        review = await self.get_review(db, review_id)
        if not review or review.user_id != user_id:
            return None

        update_data = review_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(review, field, value)

        review.updated_at = datetime.now(timezone.utc)

        try:
            await db.flush()
            logger.info(f"Updated review {review_id}")
            return review
        except IntegrityError as e:
            await db.rollback()
            logger.error("Failed to update review due to database error", exc_info=True)
            raise ValueError(
                "Failed to update review due to database constraints"
            ) from e

    async def delete_review(
        self, db: AsyncSession, review_id: int, user_id: str
    ) -> bool:
        """
        Delete a review (only by the user who created it).

        Args:
            db: Database session
            review_id: Review ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False if not found or not authorized
        """
        review = await self.get_review(db, review_id)
        if not review or review.user_id != user_id:
            return False

        await db.delete(review)
        await db.flush()
        logger.info(f"Deleted review {review_id}")
        return True
