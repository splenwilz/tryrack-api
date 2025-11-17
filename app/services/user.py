import asyncio
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from workos import WorkOSClient
from datetime import datetime, timezone
from app.core.config import settings
from app.models.user import User
from app.api.v1.schemas.user import UserCreate, UserUpdate

class UserService:
    def __init__(self):
        self.workos_client = WorkOSClient(
            api_key=settings.WORKOS_API_KEY,
            client_id=settings.WORKOS_CLIENT_ID
        )

    async def get_user(self, db: AsyncSession, user_id: str) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_users(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
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
            self.workos_client.user_management.create_user,
            **create_user_payload
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
            last_name=workos_user_response.last_name
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
        
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        # Only send fields that were explicitly provided (prevents clearing fields with None)
        await asyncio.to_thread(
            self.workos_client.user_management.update_user,
            user_id=user_id,
            **update_data
        )   
        
        # Update the database model with the same filtered data
        for field, value in update_data.items():
            setattr(existing_user, field, value)

        # Don't commit here - let the get_db() dependency handle commit/rollback
        await db.flush() # flush changes to database (without committing)
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
            self.workos_client.user_management.delete_user,
            user_id=user_id
        )

        await db.delete(existing_user)
        return True