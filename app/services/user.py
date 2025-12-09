import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from workos import WorkOSClient

from app.api.v1.schemas.user import (
    BoutiqueProfileCreate,
    BoutiqueProfileUpdate,
    UserCreate,
    UserProfileCreate,
    UserProfileUpdate,
    UserUpdate,
)
from app.core.config import settings
from app.models.boutique import Boutique
from app.models.user import BoutiqueProfile, User, UserProfile

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self):
        self.workos_client = WorkOSClient(
            api_key=settings.WORKOS_API_KEY, client_id=settings.WORKOS_CLIENT_ID
        )

    async def get_user(self, db: AsyncSession, user_id: str) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_users(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[User]:
        result = await db.execute(select(User).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create_user(self, db: AsyncSession, user_data: UserCreate) -> User:

        create_user_payload = {
            "email": user_data.email,
            "password": user_data.password,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
        }

        # Create user in WorkOS
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        workos_user_response = await asyncio.to_thread(
            self.workos_client.user_management.create_user, **create_user_payload
        )

        # Send verification email
        # On signup, we don't send the verification email to the user, because it will be sent later in the login process for the first time.
        # self.workos_client.user_management.send_verification_email(
        #     user_id=workos_user_response.id
        # )

        # Create user in database
        user = User(
            id=workos_user_response.id,
            email=workos_user_response.email,
            first_name=workos_user_response.first_name,
            last_name=workos_user_response.last_name,
        )
        db.add(user)
        await db.flush()
        return user

    async def update_user(self, db: AsyncSession, user_id: str, user_data: UserUpdate):
        existing_user = await self.get_user(db, user_id)
        if not existing_user:
            return None

        # Get only fields that were explicitly set (exclude_unset=True)
        # This prevents sending None values for omitted fields, which could clear them in WorkOS
        # Reference: https://docs.pydantic.dev/latest/api/standard_library/#pydantic.BaseModel.model_dump
        update_data = user_data.model_dump(exclude_unset=True)

        # Early return if no fields to update
        if not update_data:
            return existing_user

        # Separate fields that should be sent to WorkOS from fields that are only in our database
        # is_onboarded is only stored in our database, not in WorkOS
        workos_fields = ["first_name", "last_name"]  # Fields that exist in WorkOS
        workos_update_data = {
            k: v for k, v in update_data.items() if k in workos_fields
        }

        # Update WorkOS if there are WorkOS fields to update
        if workos_update_data:
            # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
            # Only send fields that were explicitly provided (prevents clearing fields with None)
            await asyncio.to_thread(
                self.workos_client.user_management.update_user,
                user_id=user_id,
                **workos_update_data,
            )

        # Update the database model with all update data (including is_onboarded)
        for field, value in update_data.items():
            setattr(existing_user, field, value)

        # Don't commit here - let the get_db() dependency handle commit/rollback
        await db.flush()  # flush changes to database (without committing)
        # Don't refresh here - timestamps will be available after commit
        # In serverless, refreshing before commit can cause connection issues

        # Manually set updated_at since we can't reliably refresh in serverless environments
        existing_user.updated_at = datetime.now(timezone.utc)

        return existing_user

    async def delete_user(self, db: AsyncSession, user_id: str) -> bool:
        existing_user = await self.get_user(db, user_id)
        if not existing_user:
            return False

        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        await asyncio.to_thread(
            self.workos_client.user_management.delete_user, user_id=user_id
        )

        await db.delete(existing_user)
        return True

    async def create_user_profile(
        self, db: AsyncSession, user_id: str, user_profile_data: UserProfileCreate
    ) -> UserProfile:
        """
        Create a user profile for a given user.

        Edge cases handled:
        - Validates user exists before creating profile
        - Prevents duplicate profile creation (unique constraint)
        - Only sets fields that were explicitly provided (exclude_unset=True)
        - Handles database integrity errors gracefully

        Args:
            db: Database session
            user_id: ID of the user to create profile for
            user_profile_data: Profile data to create

        Returns:
            Created UserProfile instance

        Raises:
            ValueError: If user doesn't exist
            IntegrityError: If profile already exists for this user
        """
        # Edge case 1: Validate user exists before creating profile
        # Prevents foreign key constraint violation
        user = await self.get_user(db, user_id)
        if not user:
            logger.warning(
                f"Attempted to create profile for non-existent user: {user_id}"
            )
            raise ValueError(f"User with ID '{user_id}' does not exist")

        # Edge case 2: Check if profile already exists
        # Prevents unique constraint violation at database level
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        existing_profile = result.scalar_one_or_none()
        if existing_profile:
            logger.warning(f"Profile already exists for user: {user_id}")
            raise IntegrityError(
                statement="INSERT INTO user_profiles",
                params=None,
                orig=Exception(
                    f"duplicate key value violates unique constraint "
                    f'"uq_user_profiles_user_id" - profile already exists for user {user_id}'
                ),
            )

        # Edge case 3: Only include fields that were explicitly set
        # Prevents overwriting with None values for omitted fields
        # Reference: https://docs.pydantic.dev/latest/api/standard_library/#pydantic.BaseModel.model_dump
        profile_data = user_profile_data.model_dump(exclude_unset=True)

        # Edge case 4: Create profile with validated data
        # Enums are already validated by Pydantic schema
        user_profile = UserProfile(user_id=user_id, **profile_data)

        db.add(user_profile)

        try:
            await db.flush()
            logger.info(f"Created profile for user: {user_id}")
            return user_profile
        except IntegrityError as e:
            # Edge case 5: Handle race condition - profile created between check and insert
            # This can happen in concurrent requests
            error_str = str(e.orig) if hasattr(e, "orig") else str(e)
            if (
                "uq_user_profiles_user_id" in error_str
                or "unique constraint" in error_str.lower()
            ):
                logger.warning(
                    f"Profile creation race condition detected for user: {user_id}"
                )
                # Fetch the existing profile that was just created
                result = await db.execute(
                    select(UserProfile).where(UserProfile.user_id == user_id)
                )
                existing_profile = result.scalar_one_or_none()
                if existing_profile:
                    return existing_profile
            # Re-raise if it's a different integrity error
            raise

    async def get_user_profile(
        self, db: AsyncSession, user_id: str
    ) -> Optional[UserProfile]:
        """
        Get user profile by user ID.

        Args:
            db: Database session
            user_id: ID of the user

        Returns:
            UserProfile if found, None otherwise
        """
        sys.stdout.write(
            f"[DEBUG] get_user_profile SERVICE CALLED with user_id: '{user_id}'\n"
        )
        sys.stdout.flush()
        sys.stderr.write(
            f"[DEBUG STDERR] get_user_profile SERVICE CALLED with user_id: '{user_id}'\n"
        )
        sys.stderr.flush()
        logger.error(
            f"[DEBUG LOGGER] Searching for profile with user_id: '{user_id}' (type: {type(user_id)}, length: {len(user_id)})"
        )
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        user_profile = result.scalar_one_or_none()
        if user_profile:
            logger.error(
                f"[DEBUG] Found profile: id={user_profile.id}, user_id='{user_profile.user_id}' (type: {type(user_profile.user_id)}, length: {len(user_profile.user_id)})"
            )
            sys.stderr.write(
                f"[DEBUG] Found profile: id={user_profile.id}, user_id='{user_profile.user_id}'\n"
            )
            sys.stderr.flush()
        else:
            logger.error(f"[DEBUG] No profile found for user_id: '{user_id}'")
            sys.stderr.write(f"[DEBUG] No profile found for user_id: '{user_id}'\n")
            sys.stderr.flush()
            # Also check what user_ids exist in the database
            all_profiles = await db.execute(select(UserProfile))
            existing_user_ids = [p.user_id for p in all_profiles.scalars().all()]
            logger.error(f"[DEBUG] Existing user_ids in database: {existing_user_ids}")
            sys.stderr.write(
                f"[DEBUG] Existing user_ids in database: {existing_user_ids}\n"
            )
            sys.stderr.flush()
            logger.error(f"[DEBUG] Comparison check:")
            for existing_id in existing_user_ids:
                match = user_id == existing_id
                repr_match = repr(user_id) == repr(existing_id)
                logger.error(f"  - '{user_id}' == '{existing_id}'? {match}")
                logger.error(
                    f"  - repr('{user_id}') == repr('{existing_id}')? {repr_match}"
                )
                sys.stderr.write(f"  - '{user_id}' == '{existing_id}'? {match}\n")
                sys.stderr.write(
                    f"  - repr('{user_id}') == repr('{existing_id}')? {repr_match}\n"
                )
                sys.stderr.flush()
        return user_profile

    async def update_user_profile(
        self, db: AsyncSession, user_id: str, user_profile_data: UserProfileUpdate
    ) -> Optional[UserProfile]:
        """
        Update an existing user profile.

        Args:
            db: Database session
            user_id: ID of the user whose profile to update
            user_profile_data: Profile update data (partial)

        Returns:
            Updated UserProfile if found, None otherwise
        """
        existing_user_profile = await self.get_user_profile(db, user_id)
        if not existing_user_profile:
            return None

        # Get only fields that were explicitly set (exclude_unset=True)
        # This prevents overwriting with None values for omitted fields
        # Reference: https://docs.pydantic.dev/latest/api/standard_library/#pydantic.BaseModel.model_dump
        update_data = user_profile_data.model_dump(exclude_unset=True)

        # Early return if no fields to update
        if not update_data:
            return existing_user_profile

        # Update the database model with all update data
        # Use setattr loop (SQLAlchemy models don't have .update() method)
        for field, value in update_data.items():
            setattr(existing_user_profile, field, value)

        # Don't commit here - let the get_db() dependency handle commit/rollback
        await db.flush()  # Flush changes to database (without committing)
        # Don't refresh here - timestamps will be available after commit
        # In serverless, refreshing before commit can cause connection issues

        # Manually set updated_at since we can't reliably refresh in serverless environments
        # (onupdate=func.now() may not work reliably in serverless)
        existing_user_profile.updated_at = datetime.now(timezone.utc)

        logger.info(f"Profile updated for user: {user_id}")
        return existing_user_profile

    async def delete_user_profile(self, db: AsyncSession, user_id: str) -> bool:
        """
        Delete a user profile.

        Args:
            db: Database session
            user_id: ID of the user whose profile to delete

        Returns:
            True if deleted, False if not found
        """
        existing_user_profile = await self.get_user_profile(db, user_id)
        if not existing_user_profile:
            logger.debug(f"Profile not found for user: {user_id}")
            return False

        # Delete profile using SQLAlchemy delete statement
        # Use delete() statement for reliable async deletion
        # Reference: https://docs.sqlalchemy.org/en/20/core/dml.html#sqlalchemy.sql.expression.delete
        profile_id = existing_user_profile.id
        stmt = delete(UserProfile).where(UserProfile.id == profile_id)
        result = await db.execute(stmt)
        await db.flush()  # Flush to execute the delete immediately

        # Check if any rows were deleted
        rows_deleted = result.rowcount
        if rows_deleted == 0:
            logger.warning(
                f"No rows deleted for profile_id: {profile_id}, user_id: {user_id}"
            )
            return False

        logger.info(
            f"Profile deleted successfully for user: {user_id}, profile_id: {profile_id} (rows_deleted: {rows_deleted})"
        )
        return True

    async def get_boutique_profile(
        self, db: AsyncSession, user_id: str
    ) -> Optional[BoutiqueProfile]:
        """
        Get boutique profile by user ID (owner).

        Args:
            db: Database session
            user_id: ID of the user (boutique owner)

        Returns:
            BoutiqueProfile if found, None otherwise
        """
        # Get boutique by owner_id, then get profile
        boutique_result = await db.execute(
            select(Boutique).where(Boutique.owner_id == user_id)
        )
        boutique = boutique_result.scalar_one_or_none()
        if not boutique:
            return None

        result = await db.execute(
            select(BoutiqueProfile).where(BoutiqueProfile.boutique_id == boutique.id)
        )
        return result.scalar_one_or_none()

    async def create_boutique_profile(
        self,
        db: AsyncSession,
        user_id: str,
        boutique_profile_data: BoutiqueProfileCreate,
    ) -> BoutiqueProfile:
        """
        Create a boutique profile for a given user.

        Args:
            db: Database session
            user_id: ID of the user to create profile for
            boutique_profile_data: Profile data to create

        Returns:
            Created BoutiqueProfile instance

        Raises:
            ValueError: If user doesn't exist
            IntegrityError: If profile already exists for this user
        """
        # Validate user exists
        user = await self.get_user(db, user_id)
        if not user:
            logger.warning(
                f"Attempted to create boutique profile for non-existent user: {user_id}"
            )
            raise ValueError(f"User with ID '{user_id}' does not exist")

        # Check if user already has a boutique (from migration or previous creation)
        existing_boutique_result = await db.execute(
            select(Boutique).where(Boutique.owner_id == user_id)
        )
        existing_boutique = existing_boutique_result.scalar_one_or_none()

        if existing_boutique:
            # Boutique already exists (from migration), use it
            boutique = existing_boutique
            logger.info(f"Using existing boutique {boutique.id} for user: {user_id}")
        else:
            # Create Boutique entity first (industry standard: separate boutique from user)
            boutique = Boutique(owner_id=user_id)
            db.add(boutique)
            await db.flush()  # Flush to get the boutique.id

        # Check if boutique profile already exists (from migration or previous creation)
        existing_profile = await self.get_boutique_profile(db, user_id)
        if existing_profile:
            # Profile already exists, update it instead
            logger.info(
                f"Boutique profile already exists for user {user_id}, updating instead"
            )
            return await self.update_boutique_profile(
                db, user_id, boutique_profile_data
            )

        # Only include fields that were explicitly set
        profile_data = boutique_profile_data.model_dump(exclude_unset=True)

        # Create BoutiqueProfile linked to the Boutique
        boutique_profile = BoutiqueProfile(boutique_id=boutique.id, **profile_data)

        db.add(boutique_profile)

        try:
            await db.flush()
            logger.info(f"Created boutique profile for user: {user_id}")
            return boutique_profile
        except IntegrityError as e:
            # Handle race condition
            error_str = str(e.orig) if hasattr(e, "orig") else str(e)
            if "unique constraint" in error_str.lower():
                logger.warning(
                    f"Boutique profile creation race condition detected for user: {user_id}"
                )
                existing_profile = await self.get_boutique_profile(db, user_id)
                if existing_profile:
                    return existing_profile
            raise

    async def update_boutique_profile(
        self,
        db: AsyncSession,
        user_id: str,
        boutique_profile_data: BoutiqueProfileUpdate,
    ) -> Optional[BoutiqueProfile]:
        """
        Update an existing boutique profile.

        Args:
            db: Database session
            user_id: ID of the user whose profile to update
            boutique_profile_data: Profile update data (partial)

        Returns:
            Updated BoutiqueProfile if found, None otherwise
        """
        existing_profile = await self.get_boutique_profile(db, user_id)
        if not existing_profile:
            return None

        # Get only fields that were explicitly set
        update_data = boutique_profile_data.model_dump(exclude_unset=True)

        # Early return if no fields to update
        if not update_data:
            return existing_profile

        # Update the database model
        for field, value in update_data.items():
            setattr(existing_profile, field, value)

        await db.flush()

        # Manually set updated_at
        existing_profile.updated_at = datetime.now(timezone.utc)

        logger.info(f"Boutique profile updated for user: {user_id}")
        return existing_profile
