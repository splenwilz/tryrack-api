"""
Schemas for virtual try-on sessions.
"""

from datetime import datetime
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SelectedItem(BaseModel):
    """
    Snapshot of an item used in a try-on session.

    Supports both wardrobe items and boutique (shop) products.
    - Wardrobe items: User's personal items (int IDs for DB items, str IDs for external/temporary items)
    - Boutique items: Shop products from boutiques (requires product_id and boutique_id)

    Examples:
    - Wardrobe: 6 (wardrobe item from DB), "external-123" (temporary item not yet saved)
    - Boutique: "product_456" with product_id="456", boutique_id="user_789"
    """

    id: Union[int, str] = Field(
        ...,
        union_mode="left_to_right",  # Try int first, then str for explicit coercion
        description="Item identifier (int for DB wardrobe items, str for external/temporary items or boutique products)",
    )
    title: str = Field(..., description="Item title at selection time")
    category: str = Field(..., description="Item category (e.g., shirt, dress)")
    colors: List[str] = Field(..., description="Colors associated with the item")
    tags: List[str] = Field(
        ..., description="Tags associated with the item (e.g., casual, streetwear)"
    )

    # Boutique item fields (all optional for backward compatibility)
    item_type: Optional[Literal["wardrobe", "boutique"]] = Field(
        default="wardrobe",
        description="Type of item: 'wardrobe' for user's personal items, 'boutique' for shop products",
    )
    product_id: Optional[str] = Field(
        default=None,
        description="Catalog product ID for boutique items (required when item_type='boutique')",
    )
    boutique_id: Optional[str] = Field(
        default=None,
        description="Boutique owner user ID for boutique items (required when item_type='boutique')",
    )
    boutique_name: Optional[str] = Field(
        default=None,
        description="Boutique name for display (optional, recommended for boutique items)",
    )
    boutique_logo_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Boutique logo URL (optional)",
    )

    @field_validator("colors", "tags")
    @classmethod
    def ensure_non_empty(cls, items: List[str]) -> List[str]:
        """Ensure list fields are not empty."""

        if not items:
            raise ValueError("At least one entry is required")
        return items

    @model_validator(mode="after")
    def validate_boutique_fields(self) -> "SelectedItem":
        """
        Validate boutique item requirements.

        If item_type is 'boutique', product_id and boutique_id are required.
        If item_type is 'wardrobe', boutique fields should be None.
        """
        if self.item_type == "boutique":
            if not self.product_id:
                raise ValueError("product_id is required when item_type is 'boutique'")
            if not self.boutique_id:
                raise ValueError("boutique_id is required when item_type is 'boutique'")
        elif self.item_type == "wardrobe":
            # For wardrobe items, boutique fields should be None (optional, but if provided should be None)
            # We don't enforce this strictly for backward compatibility, but we can warn
            if self.product_id is not None or self.boutique_id is not None:
                # Allow it but it's not recommended
                pass

        return self


class VirtualTryOnBase(BaseModel):
    """Shared fields for virtual try-on sessions."""

    full_body_image_uri: str = Field(
        ...,
        max_length=500,
        description="URI pointing to the user-provided body photo (`userPhoto`)",
    )
    generated_image_uri: str = Field(
        ...,
        max_length=500,
        description="URI pointing to the generated outfit (`generatedImage`)",
    )
    use_clean_background: bool = Field(
        default=True,
        description="Toggle to determine clean background usage (`useCleanBackground`)",
    )
    custom_instructions: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional prompt override (`customPrompt`). Null/empty if user left it blank",
    )
    selected_items: List[SelectedItem] = Field(
        ...,
        min_length=1,
        description="Snapshot of items included in this try-on (wardrobe items and/or boutique products)",
    )


class VirtualTryOnCreate(VirtualTryOnBase):
    """Payload required to create a new try-on session."""

    @field_validator("custom_instructions")
    @classmethod
    def normalize_instructions(cls, value: Optional[str]) -> Optional[str]:
        """Trim whitespace and convert empty strings to None."""

        if value is None:
            return None
        value = value.strip()
        return value or None


class VirtualTryOnResponse(VirtualTryOnBase):
    """Response model for virtual try-on sessions."""

    id: int = Field(..., description="Try-on session ID")
    user_id: str = Field(..., description="Owner of the session")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last updated timestamp")

    model_config = ConfigDict(from_attributes=True)
