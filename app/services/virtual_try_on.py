"""
Service for Virtual Try-On sessions.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.virtual_try_on import VirtualTryOnCreate
from app.models.virtual_try_on import VirtualTryOn

logger = logging.getLogger(__name__)


class VirtualTryOnService:
    """Business logic for virtual try-on sessions."""

    async def create_session(
        self,
        db: AsyncSession,
        user_id: str,
        session_data: VirtualTryOnCreate,
    ) -> VirtualTryOn:
        """
        Persist a new try-on session for a user.

        Args:
            db: AsyncSession
            user_id: WorkOS user ID
            session_data: Payload describing the try-on session
        """

        payload = session_data.model_dump()
        now = datetime.now(timezone.utc)
        session = VirtualTryOn(user_id=user_id, **payload)
        # Manually set timestamps to ensure they're available for serialization
        # Server-generated defaults won't be populated until after commit
        session.created_at = now
        session.updated_at = now
        db.add(session)
        await db.flush()

        logger.info(
            "Created virtual try-on session %s for user %s", session.id, user_id
        )
        return session

    async def get_session(
        self,
        db: AsyncSession,
        session_id: int,
        user_id: str,
    ) -> Optional[VirtualTryOn]:
        """Retrieve a single session."""

        result = await db.execute(
            select(VirtualTryOn).where(
                VirtualTryOn.id == session_id,
                VirtualTryOn.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_sessions(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 50,
    ) -> List[VirtualTryOn]:
        """List recent sessions for a user."""

        result = await db.execute(
            select(VirtualTryOn)
            .where(VirtualTryOn.user_id == user_id)
            .order_by(VirtualTryOn.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
