"""
Review like model for tracking which users found reviews helpful.

Reference: https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html#many-to-many
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.review import Review
    from app.models.user import User


class ReviewLike(Base):
    """
    Represents a user's "found helpful" like on a review.

    This creates a many-to-many relationship between users and reviews,
    allowing users to like multiple reviews and reviews to be liked by multiple users.
    """

    __tablename__ = "review_likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    review_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Review ID that was liked",
    )
    review: Mapped["Review"] = relationship("Review", back_populates="likes")

    user_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
        comment="WorkOS user ID who liked the review",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the review was liked",
    )

    __table_args__ = (
        UniqueConstraint("review_id", "user_id", name="uq_review_likes_review_user"),
        {"comment": "Review likes - tracks which users found reviews helpful"},
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<ReviewLike(id={self.id}, review_id={self.review_id}, user_id={self.user_id})>"

