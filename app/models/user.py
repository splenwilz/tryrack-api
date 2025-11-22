from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.wardrobe import Wardrobe


class SizeStandard(str, Enum):
    """Clothing size standard identifiers."""
    US = "US"
    UK = "UK"
    EU = "EU"
    JP = "JP"
    AU = "AU"
    OTHER = "OTHER"

size_standard_enum = SAEnum(SizeStandard, name="size_standard_enum")


class Gender(str, Enum):
    """Gender identity options."""
    MALE = "MALE"
    FEMALE = "FEMALE"

gender_enum = SAEnum(Gender, name="gender_enum")

class User(Base):
    """
    User model representing a user in the database
    
    Attributes:
        id: Primary key, UUID
        email: User email (required)
        first_name: User first name (optional)
        last_name: User last name (optional)
        is_onboarded: Boolean indicating if user has completed onboarding (default: False)
        profile: One-to-one relationship to UserProfile
        created_at: Timestamp when user was created (auto-generated)
        updated_at: Timestamp when user was last updated (auto-generated)

    Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html#one-to-one
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # One-to-one relationship to UserProfile
    # Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html#one-to-one
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile", 
        back_populates="user", 
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # One-to-many relationship to Wardrobe items
    # Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html#one-to-many
    wardrobe_items: Mapped[list["Wardrobe"]] = relationship(
        "Wardrobe",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # Server-side default for creation time
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # Server-side default for initial value
        onupdate=func.now(),  # Update on modification
        nullable=False,
    )

    def __repr__(self) -> str:
        "String representation of user"
        return f"<User(id={self.id}, email='{self.email}', created_at={self.created_at})>"

class UserProfile(Base):
    """
    User profile model representing a user's profile in the database.
    
    Uses industry-standard patterns:
    - JSON column for flexible gender-specific measurements (avoids null columns)
    - Enums for clothing sizes (type-safe validation)
    - Units specified in field names (height_cm, waist_cm)
    - Unique constraint on user_id (one profile per user)
    
    Reference: 
    - https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html#one-to-one
    - https://docs.sqlalchemy.org/en/21/core/constraints.html#unique-constraint
    - https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#sqlalchemy.dialects.postgresql.JSON
    """
    __tablename__ = "user_profiles"
    
    # Table-level unique constraint for one-to-one relationship
    # Reference: https://docs.sqlalchemy.org/en/21/core/constraints.html#unique-constraint
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Relationships - one-to-one with User
    # Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html#one-to-one
    # Note: unique=True is NOT set here - we use UniqueConstraint in __table_args__ instead
    # to avoid redundant index creation in migrations
    user_id: Mapped[str] = mapped_column(
        String, 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    user: Mapped["User"] = relationship("User", back_populates="profile")

    # Gender identity
    gender: Mapped[Optional[Gender]] = mapped_column(
        gender_enum,
        nullable=True,
        comment="User's gender identity"
    )

    # Common body measurements (in centimeters)
    # Units specified in field names to avoid ambiguity
    height_cm: Mapped[Optional[float]] = mapped_column(
        Float, 
        nullable=True,
        comment="Height in centimeters"
    )
    waist_cm: Mapped[Optional[float]] = mapped_column(
        Float, 
        nullable=True,
        comment="Waist measurement in centimeters"
    )

    # Gender-specific measurements stored in JSON for flexibility
    # This avoids having many nullable columns and allows for future extensions
    # Reference: https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#sqlalchemy.dialects.postgresql.JSON
    # Structure: {"bust_cm": 90.0, "hips_cm": 95.0} for female
    #            {"chest_cm": 100.0, "shoulder_width_cm": 45.0} for male
    measurements: Mapped[Optional[dict[str, float]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Gender-specific body measurements in JSON format. Keys should include units (e.g., 'bust_cm', 'chest_cm')"
    )

    # Clothing sizes stored as string value + explicit standard for per-item flexibility
    # Supports letter sizes (XS, S, M, L, XL, XXL, XXXL), numeric (10, 12, 40), and combined (32x34)
    shoe_size_value: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Shoe size value (e.g., '7', '7.5', '40')"
    )
    shoe_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for shoe size (e.g., US, EU)"
    )
    
    # Male clothing sizes
    shirt_size_value: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Shirt size value (e.g., 'M', 'XL', '10')"
    )
    shirt_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for shirt size (e.g., US, EU)"
    )
    jacket_size_value: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Jacket size value (e.g., 'M', 'XL', '10')"
    )
    jacket_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for jacket size (e.g., US, EU)"
    )
    pants_size_value: Mapped[Optional[str]] = mapped_column(
        String(20), 
        nullable=True,
        comment="Pants size value (e.g., '32', '32x34' for waist x inseam)"
    )
    pants_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for pants size (e.g., US, EU)"
    )
    
    # Female clothing sizes
    top_size_value: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Top size value (e.g., 'M', 'XL', '10')"
    )
    top_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for top size (e.g., US, EU)"
    )
    dress_size_value: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Dress size value (e.g., 'M', 'XL', '10')"
    )
    dress_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for dress size (e.g., US, EU)"
    )

    # Image URLs
    profile_picture_url: Mapped[Optional[str]] = mapped_column(
        String(500), 
        nullable=True,
        comment="URL to user's profile picture"
    )
    full_body_image_url: Mapped[Optional[str]] = mapped_column(
        String(500), 
        nullable=True,
        comment="URL to user's full body image"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # Server-side default for creation time
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # Server-side default for initial value
        onupdate=func.now(),  # Update on modification
        nullable=False,
    )

    def __repr__(self) -> str:
        "String representation of user profile"
        return f"<UserProfile(id={self.id}, user_id={self.user_id}, created_at={self.created_at})>"