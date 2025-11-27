"""
Schemas for virtual try-on sessions.
"""

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SelectedItem(BaseModel):
    """
    Snapshot of a wardrobe item used in a try-on session.

    Supports both database wardrobe items (int IDs) and external/temporary items (str IDs).
    Examples: 6 (wardrobe item from DB), "external-123" (temporary item not yet saved).
    """

    id: Union[int, str] = Field(
        ...,
        union_mode="left_to_right",  # Try int first, then str for explicit coercion
        description="Original wardrobe item identifier (int for DB items, str for external/temporary items)",
    )
    title: str = Field(..., description="Item title at selection time")
    category: str = Field(..., description="Item category (e.g., shirt)")
    colors: List[str] = Field(..., description="Colors associated with the item")
    tags: List[str] = Field(
        ..., description="Tags associated with the item (e.g., casual, streetwear)"
    )

    @field_validator("colors", "tags")
    @classmethod
    def ensure_non_empty(cls, items: List[str]) -> List[str]:
        """Ensure list fields are not empty."""

        if not items:
            raise ValueError("At least one entry is required")
        return items


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
        description="Snapshot of wardrobe items included in this try-on",
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
