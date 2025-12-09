"""
Boutique model for store/business entities.

Industry standard: Separate Boutique entity from User to enable:
- Multiple users managing one boutique (roles/permissions)
- Better separation of concerns
- Easier querying and relationships
- Scalability for future features

Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.catalog import CatalogItem
    from app.models.look import BoutiqueLook
    from app.models.user import BoutiqueProfile, User


class Boutique(Base):
    """
    Boutique model representing a store/business entity.

    Created automatically when a user completes boutique onboarding.
    One boutique can have multiple members (users) with different roles (future feature).

    Attributes:
        id: Primary key (boutique ID)
        owner_id: Foreign key to users table (the user who created/owns the boutique)
        owner: Relationship to User model (the owner)
        boutique_profile: One-to-one relationship with BoutiqueProfile
        catalog_items: One-to-many relationship with CatalogItem
        boutique_looks: One-to-many relationship with BoutiqueLook
        created_at: Timestamp when boutique was created
        updated_at: Timestamp when boutique was last updated
    """

    __tablename__ = "boutiques"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Owner relationship - the user who created/owns this boutique
    owner_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID of the boutique owner (creator)",
    )
    owner: Mapped["User"] = relationship(
        "User", foreign_keys=[owner_id], back_populates="owned_boutiques"
    )

    # Relationships
    boutique_profile: Mapped[Optional["BoutiqueProfile"]] = relationship(
        "BoutiqueProfile",
        back_populates="boutique",
        uselist=False,
        cascade="all, delete-orphan",
    )
    catalog_items: Mapped[list["CatalogItem"]] = relationship(
        "CatalogItem", back_populates="boutique", cascade="all, delete-orphan"
    )
    boutique_looks: Mapped[list["BoutiqueLook"]] = relationship(
        "BoutiqueLook", back_populates="boutique", cascade="all, delete-orphan"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Boutique(id={self.id}, owner_id={self.owner_id}, created_at={self.created_at})>"
