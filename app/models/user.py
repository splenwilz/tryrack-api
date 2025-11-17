from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class User(Base):
    """
    User model representing a user in the database
    
    Attributes:
        id: Primary key, UUID
        email: User email (required)
        first_name: User first name (optional)
        last_name: User last name (optional)
        created_at: Timestamp when user was created (auto-generated)
        updated_at: Timestamp when user was last updated (auto-generated)

    Reference: https://docs.sqlalchemy.org/en/20/orm/mapped_sql_expressions.html
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # pending_verification_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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