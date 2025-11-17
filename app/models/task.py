"""
Task database model
SQLAlchemy model for tasks
Reference: https://docs.sqlalchemy.org/en/20/orm/declarative_styles.html
"""
from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Task(Base):
    """
    Task model representing a task in the database
    
    Attributes:
        id: Primary key, auto-incrementing integer
        title: Task title (required)
        description: Optional task description
        completed: Whether the task is completed (default: False)
        created_at: Timestamp when task was created (auto-generated)
        updated_at: Timestamp when task was last updated (auto-generated)
    
    Reference: https://docs.sqlalchemy.org/en/20/orm/mapped_sql_expressions.html
    """
    __tablename__ = "tasks"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Task fields
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamps
    # Using server_default with func.now() for automatic timestamp generation
    # These are set by PostgreSQL on INSERT/UPDATE
    # Reference: https://docs.sqlalchemy.org/en/20/core/defaults.html#server-side-defaults
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
        """String representation of Task"""
        return f"<Task(id={self.id}, title='{self.title}', completed={self.completed})>"

