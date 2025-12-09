"""
Unified review model for products (catalog items) and boutiques.

Supports reviews for both catalog items and boutiques with:
- Multiple images per review
- Rich metadata storage
- Polymorphic item_type/item_id pattern
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.review_like import ReviewLike
    from app.models.user import User


class ReviewItemType(str, Enum):
    """Review item type enumeration."""

    PRODUCT = "product"  # Catalog item
    BOUTIQUE = "boutique"  # Boutique


class Review(Base):
    """
    Unified review model for products and boutiques.

    Supports reviews for both catalog items and boutiques using a polymorphic
    pattern with item_type and item_id.

    Attributes:
        id: Primary key
        item_type: Type of item being reviewed ("product" or "boutique")
        item_id: ID of the item being reviewed (catalog_item_id or boutique_id)
        user_id: Foreign key to users table (reviewer)
        rating: Rating value (1-5)
        comment: Review comment/text
        images: Array of image URLs associated with the review
        review_metadata: JSON object containing additional review metadata
            - For products: product_name, product_category, product_brand, etc.
            - For boutiques: boutique_name, boutique_category, etc.
        created_at: Timestamp when review was created
        updated_at: Timestamp when review was last updated
    """

    __tablename__ = "reviews"

    # Indexes for common queries
    __table_args__ = (
        Index(
            "ix_reviews_item_type_id", "item_type", "item_id"
        ),  # For filtering by item
        Index("ix_reviews_user_id", "user_id"),  # For filtering by user
        Index(
            "ix_reviews_item_rating", "item_type", "item_id", "rating"
        ),  # For rating-based queries
        Index("ix_reviews_item_type", "item_type"),  # For filtering by type
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Polymorphic item identification
    item_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type of item being reviewed: 'product' (catalog item) or 'boutique'",
    )

    item_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="ID of the item being reviewed (catalog_item_id or boutique_id as string)",
    )

    # Relationship to User (reviewer)
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who wrote the review",
    )

    user: Mapped["User"] = relationship("User", back_populates="reviews")

    # Review content
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Rating value (1-5 stars)",
    )

    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Review comment/text",
    )

    # Images associated with the review
    images: Mapped[Optional[list[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Array of image URLs associated with the review",
    )

    # Review metadata stored as JSON for flexibility
    # For products: product_name, product_category, product_brand, product_id, image_count, review_length, submitted_at
    # For boutiques: boutique_name, boutique_category, boutique_id, image_count, review_length, submitted_at
    # Note: Using 'review_metadata' instead of 'metadata' because 'metadata' is reserved by SQLAlchemy
    review_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional review metadata (product/boutique details, image_count, review_length, submitted_at, etc.)",
    )

    # Moderation
    is_approved: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="Whether the review has been approved by an admin (defaults to False for moderation)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when review was created",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when review was last updated",
    )

    # Relationship to review likes
    likes: Mapped[list["ReviewLike"]] = relationship(
        "ReviewLike",
        back_populates="review",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation of review"""
        return (
            f"<Review(id={self.id}, item_type='{self.item_type}', "
            f"item_id='{self.item_id}', user_id={self.user_id}, rating={self.rating})>"
        )
