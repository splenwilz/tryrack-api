"""
Routes for virtual try-on sessions.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.auth import WorkOSUserResponse
from app.api.v1.schemas.virtual_try_on import (
    VirtualTryOnCreate,
    VirtualTryOnResponse,
)
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.virtual_try_on import VirtualTryOnService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/virtual-try-on", tags=["virtual try-on"])


@router.post(
    "",
    response_model=VirtualTryOnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a virtual try-on session",
    description="Persist a virtual try-on result so users can revisit generated outfits.",
)
async def create_virtual_try_on_session(
    payload: VirtualTryOnCreate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VirtualTryOnResponse:
    """Create a new virtual try-on session."""

    service = VirtualTryOnService()
    session = await service.create_session(db, current_user.id, payload)
    return session


@router.get(
    "",
    response_model=List[VirtualTryOnResponse],
    summary="List virtual try-on sessions",
    description="Fetch recent virtual try-on sessions for the authenticated user.",
)
async def list_virtual_try_on_sessions(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of sessions to return"),
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[VirtualTryOnResponse]:
    """Return the most recent sessions."""

    service = VirtualTryOnService()
    return await service.list_sessions(db, current_user.id, limit=limit)


@router.get(
    "/{session_id}",
    response_model=VirtualTryOnResponse,
    summary="Retrieve a virtual try-on session",
    description="Get the details for a single try-on session by ID.",
)
async def get_virtual_try_on_session(
    session_id: int,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VirtualTryOnResponse:
    """Retrieve a single session for the current user."""

    service = VirtualTryOnService()
    session = await service.get_session(db, session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Virtual try-on session not found"
        )
    return session


