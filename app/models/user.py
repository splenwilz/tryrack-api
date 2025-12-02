from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.catalog import CatalogItem, CatalogReview
    from app.models.look import BoutiqueLook
    from app.models.virtual_try_on import VirtualTryOn
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
        cascade="all, delete-orphan",
    )

    # One-to-many relationship to Wardrobe items
    # Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html#one-to-many
    wardrobe_items: Mapped[list["Wardrobe"]] = relationship(
        "Wardrobe", back_populates="user", cascade="all, delete-orphan"
    )

    virtual_try_on_sessions: Mapped[list["VirtualTryOn"]] = relationship(
        "VirtualTryOn",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # One-to-many relationship to Catalog items (boutique owner's products)
    catalog_items: Mapped[list["CatalogItem"]] = relationship(
        "CatalogItem",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # One-to-many relationship to Catalog reviews
    catalog_reviews: Mapped[list["CatalogReview"]] = relationship(
        "CatalogReview",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # One-to-one relationship to BoutiqueProfile
    boutique_profile: Mapped[Optional["BoutiqueProfile"]] = relationship(
        "BoutiqueProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # One-to-many relationship to BoutiqueLooks
    boutique_looks: Mapped[list["BoutiqueLook"]] = relationship(
        "BoutiqueLook",
        back_populates="user",
        cascade="all, delete-orphan",
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
        return (
            f"<User(id={self.id}, email='{self.email}', created_at={self.created_at})>"
        )


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
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_profiles_user_id"),)

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
        gender_enum, nullable=True, comment="User's gender identity"
    )

    # Common body measurements (in centimeters)
    # Units specified in field names to avoid ambiguity
    height_cm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Height in centimeters"
    )
    waist_cm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Waist measurement in centimeters"
    )

    # Gender-specific measurements stored in JSON for flexibility
    # This avoids having many nullable columns and allows for future extensions
    # Reference: https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#sqlalchemy.dialects.postgresql.JSON
    # Structure: {"bust_cm": 90.0, "hips_cm": 95.0} for female
    #            {"chest_cm": 100.0, "shoulder_width_cm": 45.0} for male
    measurements: Mapped[Optional[dict[str, float]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Gender-specific body measurements in JSON format. Keys should include units (e.g., 'bust_cm', 'chest_cm')",
    )

    # Clothing sizes stored as string value + explicit standard for per-item flexibility
    # Supports letter sizes (XS, S, M, L, XL, XXL, XXXL), numeric (10, 12, 40), and combined (32x34)
    shoe_size_value: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Shoe size value (e.g., '7', '7.5', '40')"
    )
    shoe_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for shoe size (e.g., US, EU)",
    )

    # Male clothing sizes
    shirt_size_value: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Shirt size value (e.g., 'M', 'XL', '10')"
    )
    shirt_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for shirt size (e.g., US, EU)",
    )
    jacket_size_value: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Jacket size value (e.g., 'M', 'XL', '10')"
    )
    jacket_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for jacket size (e.g., US, EU)",
    )
    pants_size_value: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Pants size value (e.g., '32', '32x34' for waist x inseam)",
    )
    pants_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for pants size (e.g., US, EU)",
    )

    # Female clothing sizes
    top_size_value: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Top size value (e.g., 'M', 'XL', '10')"
    )
    top_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for top size (e.g., US, EU)",
    )
    dress_size_value: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Dress size value (e.g., 'M', 'XL', '10')"
    )
    dress_size_standard: Mapped[Optional[SizeStandard]] = mapped_column(
        size_standard_enum,
        nullable=True,
        comment="Standard for dress size (e.g., US, EU)",
    )

    # Image URLs
    profile_picture_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="URL to user's profile picture"
    )
    full_body_image_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="URL to user's full body image"
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


class BoutiqueProfile(Base):
    """
    Boutique profile model for store/business information.

    Single model for both onboarding and profile data. Most fields are nullable
    to allow minimal onboarding (just essential fields) and gradual profile completion.

    One-to-one relationship with User - each boutique owner has one profile.

    Attributes:
        id: Primary key
        user_id: Foreign key to users table (unique, one profile per user)
        user: Relationship to User model

        # Business Information (Essential for onboarding - nullable for flexibility)
        business_name: Name of the boutique/business
        business_address: Business address (street, city, state, zip, country)

        # Detailed Business Information (Profile - all nullable)
        business_category: Category of the boutique/business
        business_city: City
        business_state: State/province
        business_zip: ZIP/postal code
        business_country: Country
        business_phone: Business phone number
        business_email: Business email (may differ from user email)
        business_website: Business website URL
        business_social_media: JSON object with social media links
        logo_url: URL to boutique/business logo image

        # Preferences/Settings (Profile - all nullable)
        currency: Currency code (e.g., "USD", "EUR", "GBP")
        timezone: Timezone (e.g., "America/New_York", "Europe/London")
        language: Language code (e.g., "en", "fr", "es")

        # Timestamps
        created_at: Timestamp when profile was created
        updated_at: Timestamp when profile was last updated

    Note: Overall onboarding status is tracked in User.is_onboarded

    Reference:
        - https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html#one-to-one
        - https://docs.sqlalchemy.org/en/21/core/constraints.html#unique-constraint
    """

    __tablename__ = "boutique_profiles"

    # Table-level unique constraint for one-to-one relationship
    __table_args__ = (UniqueConstraint("user_id", name="uq_boutique_profiles_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Relationships - one-to-one with User
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User ID (unique - one profile per user)",
    )
    user: Mapped["User"] = relationship("User", back_populates="boutique_profile")

    # Business Information (Essential for onboarding - nullable for flexibility)
    business_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Name of the boutique/business",
    )
    business_address: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Business address (street, city, state, zip, country)",
    )

    # Detailed Business Information (Profile - all nullable)
    business_category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Category of the boutique/business",
    )
    business_city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="City",
    )
    business_state: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="State/province",
    )
    business_zip: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="ZIP/postal code",
    )
    business_country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Country",
    )
    # Geographic coordinates for proximity search
    latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Business latitude in decimal degrees (for proximity search). Example: 40.7128 for New York",
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Business longitude in decimal degrees (for proximity search). Example: -74.0060 for New York",
    )
    business_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Business phone number",
    )
    business_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Business email (may differ from user email)",
    )
    business_website: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Business website URL",
    )
    business_social_media: Mapped[Optional[dict[str, str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Social media links in JSON format (e.g., {'instagram': '...', 'facebook': '...'})",
    )
    logo_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to boutique/business logo image",
    )
    # Preferences/Settings (Profile - all nullable)
    currency: Mapped[Optional[str]] = mapped_column(
        String(3),
        nullable=True,
        comment="Currency code (e.g., 'USD', 'EUR', 'GBP')",
    )
    timezone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Timezone (e.g., 'America/New_York', 'Europe/London')",
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Language code (e.g., 'en', 'fr', 'es')",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when profile was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Timestamp when profile was last updated",
    )

    def __repr__(self) -> str:
        """String representation of BoutiqueProfile."""
        return (
            f"<BoutiqueProfile(id={self.id}, user_id={self.user_id}, "
            f"business_name={self.business_name})>"
        )
