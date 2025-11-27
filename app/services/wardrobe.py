"""
Wardrobe service for managing wardrobe items
Reference: https://docs.sqlalchemy.org/en/21/orm/queryguide/
"""

import logging
import time
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.wardrobe import WardrobeCreate, WardrobeUpdate
from app.models.wardrobe import ItemStatus, Wardrobe

logger = logging.getLogger(__name__)


class WardrobeService:
    """Service for managing wardrobe items"""

    async def get_wardrobe_item(
        self, db: AsyncSession, item_id: int, user_id: str
    ) -> Optional[Wardrobe]:
        """
        Get a wardrobe item by ID for a specific user.

        Args:
            db: Database session
            item_id: Item ID
            user_id: User ID (for authorization - users can only access their own items)

        Returns:
            Wardrobe item if found and belongs to user, None otherwise
        """
        result = await db.execute(
            select(Wardrobe).where(Wardrobe.id == item_id, Wardrobe.user_id == user_id)
        )

        item = result.scalar_one_or_none()
        # Pydantic will automatically convert status string to ItemStatus enum
        # when serializing with from_attributes=True
        return item

    async def get_wardrobe_items(
        self,
        db: AsyncSession,
        user_id: str,
        category: Optional[str] = None,
        status: Optional[ItemStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Wardrobe]:
        """
        Get wardrobe items for a user with optional filtering.

        Args:
            db: Database session
            user_id: User ID (users can only access their own items)
            category: Optional category filter
            status: Optional status filter
            skip: Number of items to skip (for pagination)
            limit: Maximum number of items to return

        Returns:
            List of wardrobe items
        """
        query = select(Wardrobe).where(Wardrobe.user_id == user_id)

        if category:
            query = query.where(Wardrobe.category == category)

        if status:
            # Convert enum to string value for database comparison
            query = query.where(Wardrobe.status == status.value)

        query = query.order_by(Wardrobe.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        items = list(result.scalars().all())
        # Pydantic will automatically convert status strings to ItemStatus enum
        # when serializing with from_attributes=True
        return items

    async def create_wardrobe_item(
        self, db: AsyncSession, user_id: str, wardrobe_data: WardrobeCreate
    ) -> Wardrobe:
        """
        Create a new wardrobe item for a user.

        Args:
            db: Database session
            user_id: User ID (users can only create items for themselves)
            wardrobe_data: Wardrobe item data

        Returns:
            Created Wardrobe item

        Raises:
            ValueError: If user doesn't exist or validation fails
        """
        # Only include fields that were explicitly set
        item_data = wardrobe_data.model_dump(exclude_unset=True)

        # Set default status if not provided
        if "status" not in item_data or item_data["status"] is None:
            item_data["status"] = ItemStatus.CLEAN.value  # Store as string value
        elif isinstance(item_data["status"], ItemStatus):
            item_data["status"] = item_data["status"].value  # Convert enum to string

        # Create wardrobe item
        wardrobe_item = Wardrobe(user_id=user_id, **item_data)

        db.add(wardrobe_item)

        try:
            await db.flush()
            logger.info(
                f"Created wardrobe item '{wardrobe_item.title}' for user: {user_id}"
            )
            return wardrobe_item
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to create wardrobe item due to database error", exc_info=True
            )
            raise ValueError(
                "Failed to create wardrobe item due to database constraints"
            ) from e

    async def update_wardrobe_item(
        self,
        db: AsyncSession,
        item_id: int,
        user_id: str,
        wardrobe_data: WardrobeUpdate,
    ) -> Optional[Wardrobe]:
        """
        Update a wardrobe item.

        Only provided fields will be updated (partial update).

        Args:
            db: Database session
            item_id: Item ID
            user_id: User ID (for authorization - users can only update their own items)
            wardrobe_data: Update data (all fields optional)

        Returns:
            Updated Wardrobe item if found, None otherwise
        """
        wardrobe_item = await self.get_wardrobe_item(db, item_id, user_id)
        if not wardrobe_item:
            return None

        # Only update fields that were explicitly provided
        update_data = wardrobe_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            # Convert enum to string value for status field
            if field == "status" and isinstance(value, ItemStatus):
                value = value.value
            setattr(wardrobe_item, field, value)

        # Manually set updated_at since we can't reliably refresh in serverless environments
        wardrobe_item.updated_at = datetime.now(timezone.utc)

        try:
            await db.flush()
            logger.info(f"Updated wardrobe item {item_id} for user: {user_id}")
            return wardrobe_item
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to update wardrobe item due to database error", exc_info=True
            )
            raise ValueError(
                "Failed to update wardrobe item due to database constraints"
            ) from e

    async def delete_wardrobe_item(
        self, db: AsyncSession, item_id: int, user_id: str
    ) -> bool:
        """
        Delete a wardrobe item.

        Args:
            db: Database session
            item_id: Item ID
            user_id: User ID (for authorization - users can only delete their own items)

        Returns:
            True if deleted, False if not found
        """
        wardrobe_item = await self.get_wardrobe_item(db, item_id, user_id)
        if not wardrobe_item:
            return False

        await db.delete(wardrobe_item)
        logger.info(f"Deleted wardrobe item {item_id} for user: {user_id}")
        return True

    async def mark_item_worn(
        self, db: AsyncSession, item_id: int, user_id: str
    ) -> Optional[Wardrobe]:
        """
        Mark a wardrobe item as worn (increment wear_count and update last_worn_at).

        Uses a single atomic UPDATE query for better performance.

        Args:
            db: Database session
            item_id: Item ID
            user_id: User ID (for authorization)

        Returns:
            Updated Wardrobe item if found, None otherwise
        """
        now = datetime.now(timezone.utc)

        # Use atomic UPDATE query to increment wear_count and update fields in a single operation
        # This is faster than SELECT + UPDATE and prevents race conditions
        stmt = (
            update(Wardrobe)
            .where(Wardrobe.id == item_id, Wardrobe.user_id == user_id)
            .values(
                wear_count=Wardrobe.wear_count + 1,  # Atomic increment
                last_worn_at=now,
                status=ItemStatus.WORN.value,
                updated_at=now,
            )
            .returning(Wardrobe)
        )

        try:
            result = await db.execute(stmt)
            await db.flush()

            wardrobe_item = result.scalar_one_or_none()
            if not wardrobe_item:
                return None

            # Pydantic will automatically convert status string to ItemStatus enum
            # when serializing with from_attributes=True
            logger.info(f"Marked wardrobe item {item_id} as worn for user: {user_id}")
            return wardrobe_item
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to mark item as worn due to database error", exc_info=True
            )
            raise ValueError(
                "Failed to mark item as worn due to database constraints"
            ) from e
