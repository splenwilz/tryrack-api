import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)

from app.models.user import Gender, SizeStandard


class UserBase(BaseModel):
    """
    Base schema with common User fields
    Used as base for create schemas
    """

    first_name: Optional[str] = Field(
        None, max_length=255, description="User first name"
    )
    last_name: Optional[str] = Field(None, max_length=255, description="User last name")
    email: str = Field(..., min_length=1, max_length=255, description="User email")
    password: str = Field(
        ..., min_length=8, max_length=255, description="User password"
    )


class UserCreate(UserBase):
    """
    Schema for creating a new user
    Inherits from UserBase
    Attributes:
        first_name: User first name (optional)
        last_name: User last name (optional)
        email: User email (required)
        password: User password (required)
        confirm_password: User confirm password (required)
    Reference: https://fastapi.tiangolo.com/tutorial/body/
    """

    confirm_password: str = Field(
        ..., min_length=8, max_length=255, description="User confirm password"
    )

    @field_validator("password")
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one number")
        if not any(char.isalpha() for char in v):
            raise ValueError("Password must contain at least one letter")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v

    @model_validator(mode="after")
    def validate_confirm_password(self) -> "UserCreate":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm password do not match")
        return self


class UserResponse(BaseModel):
    """
    Schema for user response
    Includes all fields from UserBase plus database-generated fields
    Attributes:
        id: User ID (required)
        email: User email (required)
        first_name: User first name (optional)
        last_name: User last name (optional)
        is_onboarded: Boolean indicating if user has completed onboarding (required)
        created_at: Timestamp when user was created (optional)
        updated_at: Timestamp when user was last updated (optional)
    Reference: https://fastapi.tiangolo.com/tutorial/response-model/
    """

    id: str = Field(..., description="User ID")
    first_name: Optional[str] = Field(
        None, max_length=255, description="User first name"
    )
    last_name: Optional[str] = Field(None, max_length=255, description="User last name")
    email: str = Field(..., min_length=1, max_length=255, description="User email")
    is_onboarded: bool = Field(
        False, description="Boolean indicating if user has completed onboarding"
    )
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when user was created"
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when user was last updated"
    )

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """
    Schema for updating a user
    All fields are optional for partial updates
    """

    first_name: Optional[str] = Field(
        None, max_length=255, description="User first name"
    )
    last_name: Optional[str] = Field(None, max_length=255, description="User last name")
    is_onboarded: Optional[bool] = Field(
        None, description="Boolean indicating if user has completed onboarding"
    )


class WorkOSUserResponse(BaseModel):
    object: str = Field(..., description="Object")
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    first_name: str | None = Field(None, description="User first name")
    last_name: str | None = Field(None, description="User last name")
    email_verified: bool = Field(..., description="User email verified")
    profile_picture_url: str | None = Field(
        None, description="User profile picture URL"
    )
    created_at: datetime = Field(..., description="User created at")
    updated_at: datetime = Field(..., description="User updated at")

    class Config:
        from_attributes = True


class AuthUserResponse(WorkOSUserResponse):
    """
    Extended user response for auth endpoints that includes is_onboarded from our database.
    Extends WorkOSUserResponse with the is_onboarded field from our User model.
    """

    is_onboarded: bool = Field(
        False, description="Boolean indicating if user has completed onboarding"
    )


class UserProfileCreate(BaseModel):
    """
    Schema for creating a new user profile.

    Uses enums for type-safe clothing sizes and validates measurements JSON structure.

    Attributes:
        gender: User's gender identity
        height_cm: User height in centimeters
        waist_cm: User waist in centimeters
        measurements: User gender-specific body measurements in JSON format. Keys should include units (e.g., 'bust_cm', 'chest_cm')
        shoe_size: User shoe size (U.S. Standard)
        shirt_size: User shirt size (U.S. Standard)
        jacket_size: User jacket size (U.S. Standard)
        pants_size: User pants size (e.g., '32x34' for waist x inseam)
        top_size: User top size (U.S. Standard)
        dress_size: User dress size (U.S. Standard)
        profile_picture_url: User profile picture URL
        full_body_image_url: User full body image URL

    Reference: https://docs.pydantic.dev/latest/concepts/validators/
    """

    gender: Optional[Gender] = Field(None, description="User's gender identity")
    height_cm: Optional[float] = Field(
        None,
        ge=0,
        le=300,  # Reasonable max height in cm (~10 feet)
        description="User height in centimeters",
    )
    waist_cm: Optional[float] = Field(
        None,
        ge=0,
        le=200,  # Reasonable max waist in cm
        description="User waist in centimeters",
    )
    measurements: Optional[dict[str, float]] = Field(
        None,
        description="User gender-specific body measurements in JSON format. Keys should include units (e.g., 'bust_cm', 'chest_cm', 'hips_cm', 'shoulder_width_cm'). Example: {'bust_cm': 90.0, 'hips_cm': 95.0} for female or {'chest_cm': 100.0, 'shoulder_width_cm': 45.0} for male",
        json_schema_extra={
            "example": {
                "bust_cm": 90.0,
                "hips_cm": 95.0,
            }
        },
    )
    shoe_size_value: Optional[str] = Field(
        None, max_length=20, description="Shoe size value (e.g., '7', '7.5', '40')"
    )
    shoe_size_standard: Optional[SizeStandard] = Field(
        None, description="Standard for shoe size (defaults to US if omitted)"
    )
    shirt_size_value: Optional[str] = Field(
        None, max_length=20, description="Shirt size value (e.g., 'M', 'XL', '10')"
    )
    shirt_size_standard: Optional[SizeStandard] = Field(
        None, description="Standard for shirt size (defaults to US if omitted)"
    )
    jacket_size_value: Optional[str] = Field(
        None, max_length=20, description="Jacket size value (e.g., 'M', 'XL', '10')"
    )
    jacket_size_standard: Optional[SizeStandard] = Field(
        None, description="Standard for jacket size (defaults to US if omitted)"
    )
    pants_size_value: Optional[str] = Field(
        None,
        max_length=20,
        description="Pants size value (e.g., '32', '32x34' for waist x inseam)",
    )
    pants_size_standard: Optional[SizeStandard] = Field(
        None, description="Standard for pants size (defaults to US if omitted)"
    )
    top_size_value: Optional[str] = Field(
        None, max_length=20, description="Top size value (e.g., 'M', 'XL', '10')"
    )
    top_size_standard: Optional[SizeStandard] = Field(
        None, description="Standard for top size (defaults to US if omitted)"
    )
    dress_size_value: Optional[str] = Field(
        None, max_length=20, description="Dress size value (e.g., 'M', 'XL', '10')"
    )
    dress_size_standard: Optional[SizeStandard] = Field(
        None, description="Standard for dress size (defaults to US if omitted)"
    )
    profile_picture_url: Optional[str] = Field(
        None, max_length=500, description="User profile picture URL"
    )
    full_body_image_url: Optional[str] = Field(
        None, max_length=500, description="User full body image URL"
    )

    @field_validator("measurements")
    @classmethod
    def validate_measurements(
        cls, v: Optional[dict[str, float]]
    ) -> Optional[dict[str, float]]:
        """Validate measurements JSON structure and values"""
        if v is None:
            return v

        # Validate all values are positive floats
        for key, value in v.items():
            if not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"Measurement '{key}' must be a positive number")

            # Suggest units in key names (best practice)
            if not any(unit in key.lower() for unit in ["_cm", "_in", "_inch"]):
                # Warning: suggest including units, but don't fail
                pass

        return v

    @field_validator("shoe_size_value")
    @classmethod
    def validate_shoe_size(cls, v: Optional[str]) -> Optional[str]:
        """Validate shoe size: numeric only (e.g., '7', '7.5', '40')."""
        if v is None:
            return v

        # Numeric with optional decimal (e.g., "7", "7.5", "40")
        if re.match(r"^\d+(\.\d+)?$", v):
            return v

        raise ValueError(
            f"Invalid shoe size: '{v}'. Must be numeric (e.g., '7', '7.5', '40')"
        )

    @field_validator(
        "shirt_size_value", "jacket_size_value", "top_size_value", "dress_size_value"
    )
    @classmethod
    def validate_clothing_size(cls, v: Optional[str]) -> Optional[str]:
        """Validate clothing size format: letter sizes (XS-XXXL) or numeric."""
        if v is None:
            return v

        # Letter sizes - normalize to uppercase
        letter_sizes = {"XS", "S", "M", "L", "XL", "XXL", "XXXL"}
        if v.upper() in letter_sizes:
            return v.upper()

        # Numeric sizes (e.g., "10", "12", "14")
        if re.match(r"^\d+(\.\d+)?$", v):
            return v

        raise ValueError(
            f"Invalid size format: '{v}'. Must be letter size (XS-XXXL) or numeric (e.g., '10')"
        )

    @field_validator("pants_size_value")
    @classmethod
    def validate_pants_size(cls, v: Optional[str]) -> Optional[str]:
        """Validate pants size: numeric waist or combined waist x inseam."""
        if v is None:
            return v

        # Numeric waist size
        if re.match(r"^\d+$", v):
            return v

        # Combined waist x inseam
        if re.match(r"^\d+x\d+$", v):
            return v

        raise ValueError(
            f"Invalid pants size: '{v}'. Must be numeric (e.g., '32') "
            f"or combined (e.g., '32x34')"
        )

    @model_validator(mode="after")
    def validate_size_standards(self) -> "UserProfileCreate":
        """Ensure size standards align with provided values."""
        size_pairs = [
            ("shoe_size_value", "shoe_size_standard"),
            ("shirt_size_value", "shirt_size_standard"),
            ("jacket_size_value", "jacket_size_standard"),
            ("pants_size_value", "pants_size_standard"),
            ("top_size_value", "top_size_standard"),
            ("dress_size_value", "dress_size_standard"),
        ]
        for value_field, standard_field in size_pairs:
            value = getattr(self, value_field)
            standard = getattr(self, standard_field)
            if standard is not None and value is None:
                raise ValueError(f"{standard_field} provided without {value_field}")
            if value is not None and standard is None:
                setattr(self, standard_field, SizeStandard.US)
        return self

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(UserProfileCreate):
    """
    Schema for updating a user profile
    Inherits from UserProfileCreate
    """

    pass


class UserProfileResponse(UserProfileCreate):
    """
    Schema for user profile response
    Includes all fields from UserProfileCreate plus database-generated fields
    """

    id: int = Field(..., description="User profile ID")
    user_id: str = Field(..., description="User ID")
    created_at: datetime = Field(..., description="User profile created at")
    updated_at: datetime = Field(..., description="User profile updated at")

    class Config:
        from_attributes = True


class BoutiqueProfileBase(BaseModel):
    """Base schema with common boutique profile fields."""

    business_name: Optional[str] = Field(
        None, max_length=200, description="Name of the boutique/business"
    )
    business_address: Optional[str] = Field(
        None,
        max_length=500,
        description="Business address (street, city, state, zip, country)",
    )
    business_category: Optional[str] = Field(
        None, max_length=100, description="Category of the boutique/business"
    )
    business_city: Optional[str] = Field(None, max_length=100, description="City")
    business_state: Optional[str] = Field(
        None, max_length=100, description="State/province"
    )
    business_zip: Optional[str] = Field(
        None, max_length=20, description="ZIP/postal code"
    )
    business_country: Optional[str] = Field(None, max_length=100, description="Country")
    business_phone: Optional[str] = Field(
        None, max_length=20, description="Business phone number"
    )
    business_email: Optional[str] = Field(
        None, max_length=255, description="Business email (may differ from user email)"
    )
    business_website: Optional[str] = Field(
        None, max_length=500, description="Business website URL"
    )
    business_social_media: Optional[dict[str, str]] = Field(
        None,
        description="Social media links in JSON format (e.g., {'instagram': '...', 'facebook': '...'})",
    )
    logo_url: Optional[str] = Field(
        None, max_length=500, description="URL to boutique/business logo image"
    )
    currency: Optional[str] = Field(
        None, max_length=3, description="Currency code (e.g., 'USD', 'EUR', 'GBP')"
    )
    timezone: Optional[str] = Field(
        None,
        max_length=50,
        description="Timezone (e.g., 'America/New_York', 'Europe/London')",
    )
    language: Optional[str] = Field(
        None, max_length=10, description="Language code (e.g., 'en', 'fr', 'es')"
    )


class BoutiqueProfileCreate(BoutiqueProfileBase):
    """
    Schema for creating a boutique profile.

    All fields are optional to allow minimal onboarding and gradual profile completion.
    """

    pass


class BoutiqueProfileUpdate(BoutiqueProfileBase):
    """
    Schema for updating a boutique profile.

    All fields are optional for partial updates.
    """

    pass


class BoutiqueProfileResponse(BoutiqueProfileBase):
    """
    Schema for boutique profile response.

    Includes all fields from BoutiqueProfileBase plus database-generated fields.
    """

    id: int = Field(..., description="Boutique profile ID")
    user_id: str = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Boutique profile created at")
    updated_at: datetime = Field(..., description="Boutique profile updated at")

    model_config = ConfigDict(from_attributes=True)
