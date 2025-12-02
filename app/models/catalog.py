"""
Boutique catalog models for product inventory and reviews.

Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class CatalogItemStatus(str, Enum):
    """Catalog item status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"


class CatalogItem(Base):
    """
    Boutique catalog item model representing a product in the catalog.

    Attributes:
        id: Primary key
        name: Product name (e.g., "Striped Moto Jeans")
        category: Product category (e.g., "jeans", "shirt", "dress")
        brand: Brand name (optional)
        cost_price: Cost price in smallest currency unit (optional, can be hidden from non-admin users)
        price: Regular selling price in smallest currency unit
        discount_price: Discount/sale price in smallest currency unit (optional, when on sale)
        image_url: URL to product image
        sales: Number of units sold (default: 0)
        revenue: Total revenue in smallest currency unit (default: 0)
        views: Number of times product was viewed (default: 0)
        stock: Available inventory count (default: 0)
        status: Product status (active, inactive, out_of_stock, discontinued)
        tags: List of tags for filtering/searching
        colors: List of colors available
        description: Product description
        created_at: Timestamp when item was created
        updated_at: Timestamp when item was last updated
    """

    __tablename__ = "catalog_items"

    # Indexes for common queries
    # Reference: https://docs.sqlalchemy.org/en/21/core/constraints.html#indexes
    __table_args__ = (
        Index("ix_catalog_items_category", "category"),  # For filtering by category
        Index("ix_catalog_items_brand", "brand"),  # For filtering by brand
        Index("ix_catalog_items_status", "status"),  # For filtering by status
        Index(
            "ix_catalog_items_category_status", "category", "status"
        ),  # Composite index for common query pattern
        Index("ix_catalog_items_user_id", "user_id"),  # For filtering by boutique owner
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Relationship to boutique owner (User)
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Boutique owner user ID - links catalog item to boutique",
    )

    # Core product information
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Product name"
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # Index is defined in __table_args__ below to avoid duplication
        comment="Product category (e.g., 'jeans', 'shirt', 'dress')",
    )

    brand: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        # Index is defined in __table_args__ below to avoid duplication
        comment="Brand name (optional for generic/unbranded items)",
    )

    # Cost price (what the store paid for the item) - optional for access control
    # Can be hidden from sales attendants via API-level permissions
    cost_price: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Cost price in smallest currency unit (cents/pence). What the store paid for the item. Optional - can be hidden from non-admin users. Example: 30000 = $300.00",
    )

    # Selling price (regular price)
    price: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Regular selling price in smallest currency unit (cents/pence). Example: 55000 = $550.00",
    )

    # Discount/sale price (optional, only set when item is on sale)
    discount_price: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Discount/sale price in smallest currency unit (cents/pence). Only set when item is on sale. Example: 45000 = $450.00",
    )

    image_url: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="URL to product image"
    )

    # Analytics and inventory
    sales: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of units sold",
    )

    revenue: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total revenue in smallest currency unit (cents/pence)",
    )

    views: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of times product was viewed",
    )

    stock: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Available inventory count",
    )

    # Status stored as String to match pattern with Wardrobe model
    # Enum validation is handled in Pydantic schemas
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CatalogItemStatus.ACTIVE.value,
        # Index is defined in __table_args__ below to avoid duplication
        comment="Product status (active, inactive, out_of_stock, discontinued)",
    )

    # Product attributes
    tags: Mapped[Optional[list[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of tags for filtering/searching (e.g., ['denim', 'moto', 'casual'])",
    )

    colors: Mapped[Optional[list[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of available colors (e.g., ['navy blue', 'white'])",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Product description",
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

    # Relationships
    # Many-to-one: catalog item belongs to a boutique owner (User)
    user: Mapped["User"] = relationship("User", back_populates="catalog_items")

    # One-to-many: one catalog item can have many reviews
    reviews: Mapped[list["CatalogReview"]] = relationship(
        "CatalogReview",
        back_populates="catalog_item",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation of catalog item"""
        return (
            f"<CatalogItem(id={self.id}, name='{self.name}', "
            f"category='{self.category}', brand='{self.brand}', status='{self.status}')>"
        )


class CatalogReview(Base):
    """
    Product review model for catalog items.

    Attributes:
        id: Primary key
        catalog_item_id: Foreign key to catalog_items table
        user_id: Foreign key to users table (reviewer)
        rating: Rating value (1-5)
        comment: Review comment/text
        created_at: Timestamp when review was created
        updated_at: Timestamp when review was last updated
    """

    __tablename__ = "catalog_reviews"

    # Indexes for common queries
    __table_args__ = (
        Index("ix_catalog_reviews_item_id", "catalog_item_id"),  # For filtering by item
        Index("ix_catalog_reviews_user_id", "user_id"),  # For filtering by user
        Index(
            "ix_catalog_reviews_item_rating", "catalog_item_id", "rating"
        ),  # For rating-based queries
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Relationships
    catalog_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_items.id", ondelete="CASCADE"),
        nullable=False,
        # Index is defined in __table_args__ below to avoid duplication
        comment="Catalog item being reviewed",
    )

    catalog_item: Mapped["CatalogItem"] = relationship(
        "CatalogItem", back_populates="reviews"
    )

    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        # Index is defined in __table_args__ below to avoid duplication
        comment="User who wrote the review",
    )

    user: Mapped["User"] = relationship("User", back_populates="catalog_reviews")

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

    def __repr__(self) -> str:
        """String representation of catalog review"""
        return (
            f"<CatalogReview(id={self.id}, catalog_item_id={self.catalog_item_id}, "
            f"user_id={self.user_id}, rating={self.rating})>"
        )
