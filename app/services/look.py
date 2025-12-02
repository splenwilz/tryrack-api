"""
Boutique Look service for managing styled combinations of catalog items.

Reference: https://docs.sqlalchemy.org/en/21/orm/queryguide/
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.look import BoutiqueLookCreate, BoutiqueLookUpdate
from app.models.catalog import CatalogItem
from app.models.look import BoutiqueLook

logger = logging.getLogger(__name__)


class LookService:
    """Service for managing boutique looks"""

    async def get_look(
        self, db: AsyncSession, look_id: int, user_id: Optional[str] = None
    ) -> Optional[BoutiqueLook]:
        """
        Get a boutique look by ID.

        Args:
            db: Database session
            look_id: Look ID
            user_id: Optional user ID to filter by boutique owner

        Returns:
            Boutique look if found, None otherwise
        """
        query = select(BoutiqueLook).where(BoutiqueLook.id == look_id)

        # Filter by boutique owner if provided
        if user_id:
            query = query.where(BoutiqueLook.user_id == user_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_looks(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        style: Optional[str] = None,
        is_featured: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[BoutiqueLook]:
        """
        Get boutique looks with optional filtering.

        Args:
            db: Database session
            user_id: Optional filter by boutique owner
            style: Optional filter by style
            is_featured: Optional filter by featured status
            skip: Number of items to skip (for pagination)
            limit: Maximum number of items to return

        Returns:
            List of boutique looks
        """
        query = select(BoutiqueLook)

        if user_id:
            query = query.where(BoutiqueLook.user_id == user_id)

        if style:
            query = query.where(BoutiqueLook.style == style)

        if is_featured is not None:
            query = query.where(BoutiqueLook.is_featured == is_featured)

        query = query.order_by(BoutiqueLook.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def create_look(
        self, db: AsyncSession, look_data: BoutiqueLookCreate, user_id: str
    ) -> BoutiqueLook:
        """
        Create a new boutique look.

        Args:
            db: Database session
            look_data: Look data
            user_id: ID of the boutique owner creating this look (required)

        Returns:
            Created boutique look

        Raises:
            ValueError: If validation fails or database constraint violation
        """
        look_dict = look_data.model_dump(exclude_unset=True)

        # Set user_id (boutique owner) - required for linking look to boutique
        look_dict["user_id"] = user_id

        # Validate that all product_ids exist and belong to the boutique owner
        if "product_ids" in look_dict and look_dict["product_ids"]:
            items = await self.get_catalog_items_by_ids(db, look_dict["product_ids"])
            if len(items) != len(look_dict["product_ids"]):
                raise ValueError("One or more product IDs are invalid or do not exist")
            # Verify ownership
            for item in items:
                if item.user_id != user_id:
                    raise ValueError(
                        "One or more products do not belong to your boutique"
                    )

        boutique_look = BoutiqueLook(**look_dict)
        db.add(boutique_look)

        try:
            await db.flush()
            logger.info(
                f"Created boutique look '{boutique_look.title}' (ID: {boutique_look.id}) for user: {user_id}"
            )
            return boutique_look
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to create boutique look due to database error", exc_info=True
            )
            raise ValueError(
                "Failed to create boutique look due to database constraints"
            ) from e

    async def update_look(
        self,
        db: AsyncSession,
        look_id: int,
        look_data: BoutiqueLookUpdate,
        user_id: str,
    ) -> Optional[BoutiqueLook]:
        """
        Update a boutique look.

        Args:
            db: Database session
            look_id: Look ID to update
            look_data: Updated look data (only provided fields will be updated)
            user_id: ID of the boutique owner (for authorization)

        Returns:
            Updated boutique look if found and authorized, None otherwise

        Raises:
            ValueError: If validation fails or database constraint violation
        """
        # Get existing look and verify ownership
        existing_look = await self.get_look(db, look_id, user_id)
        if not existing_look:
            return None

        # Update only provided fields
        update_dict = look_data.model_dump(exclude_unset=True)

        # Validate product_ids if they're being updated
        if "product_ids" in update_dict and update_dict["product_ids"]:
            items = await self.get_catalog_items_by_ids(db, update_dict["product_ids"])
            if len(items) != len(update_dict["product_ids"]):
                raise ValueError("One or more product IDs are invalid or do not exist")
            # Verify ownership
            for item in items:
                if item.user_id != user_id:
                    raise ValueError(
                        "One or more products do not belong to your boutique"
                    )

        for field, value in update_dict.items():
            setattr(existing_look, field, value)

        # Manually set updated_at since we can't reliably refresh in serverless environments
        existing_look.updated_at = datetime.now(timezone.utc)

        try:
            await db.flush()
            logger.info(f"Updated boutique look {look_id} for user: {user_id}")
            return existing_look
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to update boutique look due to database error", exc_info=True
            )
            raise ValueError(
                "Failed to update boutique look due to database constraints"
            ) from e

    async def delete_look(
        self, db: AsyncSession, look_id: int, user_id: str
    ) -> bool:
        """
        Delete a boutique look.

        Args:
            db: Database session
            look_id: Look ID to delete
            user_id: ID of the boutique owner (for authorization)

        Returns:
            True if look was deleted, False if not found or not authorized
        """
        # Get existing look and verify ownership
        existing_look = await self.get_look(db, look_id, user_id)
        if not existing_look:
            return False

        await db.delete(existing_look)
        await db.flush()

        logger.info(f"Deleted boutique look {look_id} for user: {user_id}")
        return True

    async def calculate_total_price(
        self, db: AsyncSession, product_ids: list[str]
    ) -> Optional[int]:
        """
        Calculate the total price of products in a look.

        Uses discount_price if available, otherwise uses regular price.
        Prices are stored in cents (smallest currency unit).

        Args:
            db: Database session
            product_ids: List of catalog item IDs (as strings)

        Returns:
            Total price in cents, or None if any product is not found
        """
        if not product_ids:
            return None

        # Convert string IDs to integers for querying
        try:
            item_ids = [int(pid) for pid in product_ids]
        except ValueError:
            logger.warning(f"Invalid product IDs: {product_ids}")
            return None

        # Fetch all catalog items in one query
        query = select(CatalogItem).where(CatalogItem.id.in_(item_ids))
        result = await db.execute(query)
        items = list(result.scalars().all())

        # If we didn't find all items, return None
        if len(items) != len(item_ids):
            missing_ids = set(item_ids) - {item.id for item in items}
            logger.warning(f"Some catalog items not found: {missing_ids}")
            return None

        # Calculate total: use discount_price if available, otherwise price
        total = 0
        for item in items:
            # Use discount_price if available and less than regular price, otherwise use price
            item_price = (
                item.discount_price if item.discount_price and item.discount_price < item.price else item.price
            )
            total += item_price

        return total

    async def get_catalog_items_by_ids(
        self, db: AsyncSession, product_ids: list[str]
    ) -> List[CatalogItem]:
        """
        Fetch catalog items by their IDs.

        Args:
            db: Database session
            product_ids: List of catalog item IDs (as strings)

        Returns:
            List of catalog items (may be shorter than product_ids if some are not found)
        """
        if not product_ids:
            return []

        # Convert string IDs to integers for querying
        try:
            item_ids = [int(pid) for pid in product_ids]
        except ValueError:
            logger.warning(f"Invalid product IDs: {product_ids}")
            return []

        # Fetch all catalog items in one query
        query = select(CatalogItem).where(CatalogItem.id.in_(item_ids))
        result = await db.execute(query)
        items = list(result.scalars().all())

        # Sort items to match the order of product_ids
        item_dict = {item.id: item for item in items}
        sorted_items = [item_dict[int(pid)] for pid in product_ids if int(pid) in item_dict]

        return sorted_items

