"""
Database models
All SQLAlchemy models should be defined here or imported here
"""

# Import Base for models to inherit from
from app.core.database import Base
from app.models.boutique import Boutique
from app.models.catalog import CatalogItem, CatalogItemStatus, CatalogReview

# Import models here as they are created
from app.models.look import BoutiqueLook
from app.models.review import Review, ReviewItemType
from app.models.review_like import ReviewLike
from app.models.task import Task
from app.models.user import BoutiqueProfile, User, UserProfile
from app.models.virtual_try_on import VirtualTryOn
from app.models.wardrobe import ItemStatus, Wardrobe

# Export all models for easy imports
__all__ = [
    "Base",
    "Boutique",
    "BoutiqueLook",
    "BoutiqueProfile",
    "CatalogItem",
    "CatalogItemStatus",
    "CatalogReview",
    "ItemStatus",
    "Review",
    "ReviewItemType",
    "ReviewLike",
    "Task",
    "User",
    "UserProfile",
    "VirtualTryOn",
    "Wardrobe",
]
