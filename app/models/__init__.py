"""
Database models
All SQLAlchemy models should be defined here or imported here
"""

# Import Base for models to inherit from
from app.core.database import Base

# Import models here as they are created
from app.models.task import Task
from app.models.user import User

# Export all models for easy imports
__all__ = ["Base", "Task", "User"]
