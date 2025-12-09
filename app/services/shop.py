"""
Shop service for fetching boutique catalog items for individual users.

Implements proximity-based filtering and round-robin selection algorithm
to ensure diversity across different boutiques.

Reference:
- Haversine formula: https://en.wikipedia.org/wiki/Haversine_formula
- SQLAlchemy joins: https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html#joins
"""

import logging
import math
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.boutique import Boutique
from app.models.catalog import CatalogItem, CatalogItemStatus
from app.models.user import BoutiqueProfile

logger = logging.getLogger(__name__)

# Earth's radius in miles (for haversine distance calculation)
EARTH_RADIUS_MILES = 3958.8


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great-circle distance between two points on Earth using the Haversine formula.

    Args:
        lat1: Latitude of first point in decimal degrees
        lon1: Longitude of first point in decimal degrees
        lat2: Latitude of second point in decimal degrees
        lon2: Longitude of second point in decimal degrees

    Returns:
        Distance in miles

    Reference: https://en.wikipedia.org/wiki/Haversine_formula
    """
    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return EARTH_RADIUS_MILES * c


class ShopService:
    """Service for fetching boutique catalog items with proximity filtering and round-robin selection"""

    async def get_shop_items(
        self,
        db: AsyncSession,
        category: Optional[str] = None,
        radius_miles: float = 100.0,
        user_latitude: Optional[float] = None,
        user_longitude: Optional[float] = None,
        limit: int = 50,
    ) -> tuple[List[CatalogItem], float]:
        """
        Get shop items using round-robin selection from different boutiques.

        Algorithm:
        1. Filter catalog items by category and status (ACTIVE only)
        2. If user location provided, filter by proximity using haversine distance
        3. Group items by boutique (user_id)
        4. Round-robin selection: pick one item from each boutique in rotation
        5. Return items with distance information

        Args:
            db: Database session
            category: Optional category filter (e.g., 'jeans', 'shirt')
            radius_miles: Proximity radius in miles (default: 100)
            user_latitude: User's latitude in decimal degrees (optional)
            user_longitude: User's longitude in decimal degrees (optional)
            limit: Maximum number of items to return (default: 50)

        Returns:
            Tuple of (list of catalog items, actual radius used)
        """
        # Build base query: join CatalogItem with Boutique and BoutiqueProfile
        # Only include ACTIVE items
        # Use selectinload to eagerly load relationships for performance
        query = (
            select(CatalogItem)
            .join(Boutique, CatalogItem.boutique_id == Boutique.id)
            .outerjoin(BoutiqueProfile, Boutique.id == BoutiqueProfile.boutique_id)
            .where(CatalogItem.status == CatalogItemStatus.ACTIVE)
            .options(
                selectinload(CatalogItem.boutique).selectinload(Boutique.boutique_profile)
            )
        )

        # Filter by category if provided
        if category:
            query = query.where(CatalogItem.category == category)

        # Proximity filtering (if user location provided)
        if user_latitude is not None and user_longitude is not None:
            # Only include boutiques with valid coordinates
            query = query.where(
                BoutiqueProfile.latitude.isnot(None),
                BoutiqueProfile.longitude.isnot(None),
            )

        # Execute query to get all matching items
        result = await db.execute(query)
        all_items: List[CatalogItem] = result.scalars().all()

        # Filter by proximity if user location provided
        if user_latitude is not None and user_longitude is not None:
            filtered_items = []
            for item in all_items:
                # Get boutique coordinates from boutique's boutique_profile
                boutique_profile = item.boutique.boutique_profile if item.boutique else None
                if not boutique_profile:
                    continue

                if (
                    boutique_profile.latitude is None
                    or boutique_profile.longitude is None
                ):
                    continue

                # Calculate distance
                distance = haversine_distance(
                    user_latitude,
                    user_longitude,
                    boutique_profile.latitude,
                    boutique_profile.longitude,
                )

                # Filter by radius
                if distance <= radius_miles:
                    # Store distance in item for later use (we'll add it in the response)
                    filtered_items.append(item)
            all_items = filtered_items

        # Round-robin selection: group by boutique (boutique_id) and select one from each
        boutique_groups: dict[int, List[CatalogItem]] = {}
        for item in all_items:
            boutique_id = item.boutique_id
            if boutique_id not in boutique_groups:
                boutique_groups[boutique_id] = []
            boutique_groups[boutique_id].append(item)

        # Round-robin: iterate through boutiques and pick one item from each
        selected_items: List[CatalogItem] = []
        boutique_ids = list(boutique_groups.keys())
        max_rounds = max(len(items) for items in boutique_groups.values()) if boutique_groups else 0

        # Continue until we have enough items or run out
        for round_num in range(max_rounds):
            if len(selected_items) >= limit:
                break

            for boutique_id in boutique_ids:
                if len(selected_items) >= limit:
                    break

                boutique_items = boutique_groups[boutique_id]
                if round_num < len(boutique_items):
                    selected_items.append(boutique_items[round_num])

        # Limit to requested number
        selected_items = selected_items[:limit]

        logger.info(
            f"Shop service: Found {len(all_items)} items, selected {len(selected_items)} "
            f"from {len(boutique_groups)} boutiques using round-robin"
        )

        return selected_items, radius_miles

