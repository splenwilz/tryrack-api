"""
Boutique Look model - represents a styled combination of catalog items.

A "look" is a curated outfit created by a boutique, combining 2-5 catalog items
to showcase how products can be styled together.

Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class BoutiqueLook(Base):
    """
    Boutique Look model representing a styled combination of catalog items.

    Attributes:
        id: Primary key
        user_id: Foreign key to boutique owner (User)
        title: Look title/name
        description: Optional description of the look
        style: Style identifier (e.g., 'casual', 'formal', 'streetwear')
        product_ids: Array of catalog item IDs (2-5 items) - stored as JSON array of strings
        image_url: Optional URL to styled image (can be generated via virtual try-on)
        is_featured: Whether this look is featured/promoted (default: False)
        created_at: Timestamp when look was created
        updated_at: Timestamp when look was last updated
    """

    __tablename__ = "boutique_looks"

    # Indexes for common queries
    __table_args__ = (
        Index(
            "ix_boutique_looks_user_id", "user_id"
        ),  # For filtering by boutique owner
        Index("ix_boutique_looks_style", "style"),  # For filtering by style
        Index("ix_boutique_looks_is_featured", "is_featured"),  # For featured looks
        Index(
            "ix_boutique_looks_user_featured", "user_id", "is_featured"
        ),  # Composite index for boutique's featured looks
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Relationship to boutique owner (User)
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Boutique owner user ID - links look to boutique",
    )
    user: Mapped["User"] = relationship("User", back_populates="boutique_looks")

    # Look information
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Look title/name (e.g., 'Summer Casual Outfit')",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of the look and styling notes",
    )

    style: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Style identifier (e.g., 'casual', 'formal', 'streetwear', 'bohemian')",
    )

    # Product IDs stored as JSON array of strings
    # Reference: https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#sqlalchemy.dialects.postgresql.JSON
    # Validation: 2-5 items required (enforced in Pydantic schema)
    product_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        comment="Array of catalog item IDs (2-5 items). Example: ['1', '2', '3']",
    )

    # Optional styled image (can be generated via virtual try-on)
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to styled image showing the complete look (can be generated via virtual try-on)",
    )

    # Featured flag for promotion
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this look is featured/promoted (default: False)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when look was created",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when look was last updated",
    )

    def __repr__(self) -> str:
        """String representation of boutique look"""
        return (
            f"<BoutiqueLook(id={self.id}, title='{self.title}', "
            f"style='{self.style}', user_id='{self.user_id}', "
            f"is_featured={self.is_featured})>"
        )
