"""
Service for Virtual Try-On sessions.
"""

import logging
import sys
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

    async def delete_session(
        self,
        db: AsyncSession,
        session_id: int,
        user_id: str,
    ) -> bool:
        """
        Delete a virtual try-on session.

        Implements idempotent delete: if the session doesn't exist, returns True
        (desired state already achieved). Only returns False if session exists
        but belongs to a different user (permission denied).

        Args:
            db: Database session
            session_id: Session ID to delete
            user_id: User ID (for authorization - users can only delete their own sessions)

        Returns:
            True if:
                - Session was deleted successfully, OR
                - Session doesn't exist (idempotent delete)
            False if:
                - Session exists but belongs to a different user (permission denied)
        """
        # Debug: Print user_id attempting to delete (using stdout to ensure visibility)
        sys.stdout.write(
            f"[DELETE DEBUG] Attempting to delete session {session_id} for user_id: {user_id}\n"
        )
        sys.stdout.flush()

        # First, try to get the session without user filter to see if it exists
        result = await db.execute(
            select(VirtualTryOn).where(VirtualTryOn.id == session_id)
        )
        session_any_user = result.scalar_one_or_none()

        if session_any_user:
            sys.stdout.write(
                f"[DELETE DEBUG] Session {session_id} exists with user_id: '{session_any_user.user_id}' (requesting user_id: '{user_id}')\n"
            )
            sys.stdout.write(
                f"[DELETE DEBUG] User IDs match: {session_any_user.user_id == user_id}\n"
            )
            sys.stdout.flush()

            # If session exists but belongs to different user, return False (permission denied)
            if session_any_user.user_id != user_id:
                sys.stdout.write(
                    f"[DELETE DEBUG] Permission denied: session belongs to different user\n"
                )
                sys.stdout.flush()
                return False

            # Session exists and belongs to this user - proceed with deletion
            await db.delete(session_any_user)
            await db.flush()

            logger.info(
                "Deleted virtual try-on session %s for user %s", session_id, user_id
            )
            return True
        else:
            # Session doesn't exist - idempotent delete (return True because desired state is already achieved)
            sys.stdout.write(
                f"[DELETE DEBUG] Session {session_id} does not exist - idempotent delete (returning success)\n"
            )
            sys.stdout.flush()
            logger.info(
                "Delete requested for non-existent session %s (idempotent delete)",
                session_id,
            )
            return True
