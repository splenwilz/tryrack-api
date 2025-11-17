"""
API v1 router aggregation
Combines all v1 route handlers into a single router
Reference: https://fastapi.tiangolo.com/tutorial/bigger-applications/
"""
from fastapi import APIRouter

from app.api.v1.routes import health, task, user, auth
from app.core.config import settings


# Create main API router for v1
# All v1 routes will be prefixed with /api/v1
api_router = APIRouter(prefix=settings.API_V1_PREFIX)

# Include route modules
# Each route module is added as a sub-router
api_router.include_router(auth.router)
api_router.include_router(user.router)
api_router.include_router(task.router)
api_router.include_router(health.router)
