"""
Virtual try-on session model.

Reference: https://docs.sqlalchemy.org/en/21/orm/declarative_tables.html
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class VirtualTryOn(Base):
    """Represents a single virtual try-on session."""

    __tablename__ = "virtual_try_on_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="WorkOS user ID for the session owner",
    )
    user: Mapped["User"] = relationship(
        "User", back_populates="virtual_try_on_sessions"
    )

    full_body_image_uri: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="User-uploaded body image used for the try-on run",
    )
    generated_image_uri: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Resulting image URI from the generation workflow",
    )
    use_clean_background: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the generation used a clean background",
    )
    custom_instructions: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Optional custom instructions provided by the user",
    )
    selected_items: Mapped[List[dict]] = mapped_column(
        JSON,
        nullable=False,
        comment="Snapshot of items selected for this session (wardrobe items and/or boutique products)",
    )

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
        """String representation."""

        return (
            f"<VirtualTryOn(id={self.id}, user_id={self.user_id}, "
            f"use_clean_background={self.use_clean_background})>"
        )
