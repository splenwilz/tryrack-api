"""
Wardrobe item model representing clothing items in a user's wardrobe.

Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Import User only for type checking to avoid circular imports
# Reference: https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.user import User


class ItemStatus(str, Enum):
    """Item status enumeration."""

    CLEAN = "clean"
    PLANNED = "planned"  # Item selected for future wear (outfit planning)
    WORN = "worn"
    DIRTY = "dirty"


# Note: We store status as String(10) in the database, not as a PostgreSQL enum
# This allows flexibility and avoids enum value/name mismatches
# Pydantic schemas handle enum validation at the API boundary


class Wardrobe(Base):
    """
    Wardrobe item model representing a clothing item in a user's wardrobe.

    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        title: Item title/name (e.g., "Givenchy Geometric Print Short Sleeve Shirt")
        category: Item category (e.g., "shirt", "pants", "dress")
        colors: List of colors (e.g., ["burgundy", "olive green", "black"])
        image_url: URL to item image
        tags: List of tags for filtering/searching (e.g., ["short sleeve", "geometric", "casual", "summer", "silk"])
        status: Current status (clean, planned, worn, dirty)
        last_worn_at: Timestamp when item was last worn (nullable for unworn items)
        wear_count: Number of times item has been worn (default: 0)

        created_at: Timestamp when item was created
        updated_at: Timestamp when item was last updated
    """

    __tablename__ = "wardrobe_items"

    # Indexes for common queries
    # Reference: https://docs.sqlalchemy.org/en/21/core/constraints.html#indexes
    __table_args__ = (
        Index("ix_wardrobe_items_user_id", "user_id"),  # For filtering by user
        Index("ix_wardrobe_items_category", "category"),  # For filtering by category
        Index(
            "ix_wardrobe_items_user_category", "user_id", "category"
        ),  # Composite index for common query pattern
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Relationships
    # Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html#many-to-one
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "users.id", ondelete="CASCADE"
        ),  # Cascade delete when user is deleted
        nullable=False,
        # Index is defined in __table_args__ below to avoid duplication
    )
    user: Mapped["User"] = relationship("User", back_populates="wardrobe_items")

    # Core item information
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Item title/name"
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # Index is defined in __table_args__ below to avoid duplication
        comment="Item category (e.g., 'shirt', 'pants', 'dress')",
    )

    # Visual attributes
    colors: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        comment="List of colors (e.g., ['burgundy', 'olive green', 'black'])",
    )

    image_url: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="URL to item image"
    )

    # Tags for filtering and searching
    # Reference: https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#sqlalchemy.dialects.postgresql.JSON
    tags: Mapped[Optional[list[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of tags for filtering/searching (e.g., ['short sleeve', 'geometric', 'casual', 'summer', 'silk'])",
    )

    # Status and usage tracking
    # Store as String (VARCHAR) since we migrated from enum to VARCHAR
    # Enum validation is handled in Pydantic schemas
    status: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        default=ItemStatus.CLEAN.value,  # Use enum value ('clean') as default
        comment="Current item status (clean, planned, worn, dirty)",
    )
    last_worn_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when item was last worn (nullable for unworn items)",
    )
    wear_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="Number of times item has been worn"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when item was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when item was last updated",
    )

    def __repr__(self) -> str:
        """String representation of wardrobe item"""
        return f"<Wardrobe(id={self.id}, user_id={self.user_id}, title='{self.title}', category='{self.category}')>"
