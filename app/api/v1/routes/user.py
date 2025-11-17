from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from workos.exceptions import BadRequestException
from app.api.v1.schemas.auth import WorkOSUserResponse
from app.api.v1.schemas.user import UserResponse, UserUpdate
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
# from app.core.exceptions import InvalidPasswordException
from app.core.dependencies import get_current_user
from app.services.user import UserService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

@router.get("", response_model=List[UserResponse])
async def get_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of users to return"),
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[UserResponse]:
    """
    Get a list of users
    
    Args:
        skip: Number of users to skip (for pagination)
        limit: Maximum number of users to return (for pagination)
        db: Database session

    Returns:
        List of UserResponse objects
    """
    user_service = UserService()
    users = await user_service.get_users(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Get a user by ID
    """
    user_service = UserService()
    user = await user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

# POST /users removed - use POST /auth/signup for user registration instead

@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Update a user by ID",
    status_code=status.HTTP_200_OK
)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a user by ID
    
    Args:
        user_id: ID of the user to update
        user_data: User update data
        
    Returns:
        Updated UserResponse object
    """
    user_service = UserService()
    try:
        user = await user_service.update_user(db, user_id, user_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    except BadRequestException as e:
        logger.error(f"Bad request updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update user: {e.message if hasattr(e, 'message') else str(e)}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the user"
        ) from e

@router.delete(
    "/{user_id}",
    summary="Delete user",
    description="Delete a user by ID",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "User not found"},
        204: {"description": "User deleted successfully"}
    }
)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a user by ID
    
    Args:
        user_id: ID of the user to delete
        
    Returns:
        None
    """
    user_service = UserService()
    try:
        deleted = await user_service.delete_user(db, user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return None 
    except Exception as e:
        logger.error(f"Unexpected error deleting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the user"
        ) from e