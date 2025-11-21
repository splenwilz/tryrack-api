from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from workos.exceptions import BadRequestException
from app.api.v1.schemas.auth import WorkOSUserResponse
from app.api.v1.schemas.user import UserProfileCreate, UserProfileResponse, UserProfileUpdate, UserResponse, UserUpdate
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
# from app.core.exceptions import InvalidPasswordException
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.services.user import UserService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/user",
    tags=["user"],
)

# IMPORTANT: Profile routes must come BEFORE /{user_id} route
# Otherwise FastAPI will match /profile as user_id="profile"
@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="Get user profile",
    description="Get the user profile for the authenticated user.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Profile retrieved successfully"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "User profile not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_user_profile(
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserProfileResponse:
    """
    Get the user profile for the authenticated user.
    
    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
        
    Returns:
        UserProfileResponse object
        
    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if profile not found
            - 500 for unexpected errors
    """
    # Debug logging (only in development)
    if settings.ENVIRONMENT == "development":
        logger.debug("=" * 80)
        logger.debug("GET /api/v1/user/profile - FUNCTION CALLED")
        logger.debug("Getting profile for authenticated user:")
        logger.debug(f"  - current_user.id: '{current_user.id}' (type: {type(current_user.id)}, length: {len(current_user.id)})")
        logger.debug(f"  - current_user.email: '{current_user.email}'")
    
    user_service = UserService()
    try:
        user_profile = await user_service.get_user_profile(db, current_user.id)
        if not user_profile:
            if settings.ENVIRONMENT == "development":
                logger.debug(f"Profile not found for user_id: '{current_user.id}'")
                logger.debug("GET /api/v1/user/profile - END (404)")
                logger.debug("=" * 80)
            logger.warning(f"Profile not found for user_id: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        if settings.ENVIRONMENT == "development":
            logger.debug(f"Profile retrieved successfully for user: '{current_user.id}'")
            logger.debug("GET /api/v1/user/profile - END (200)")
            logger.debug("=" * 80)
        logger.info(f"Profile retrieved successfully for user: {current_user.id}")
        return user_profile
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) without wrapping
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error getting profile for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while getting the user profile"
        ) from e

@router.post(
    "/profile",
    response_model=UserProfileResponse,
    summary="Create user profile",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Profile created successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "User not found"},
        409: {"description": "Profile already exists for this user"},
        500: {"description": "Internal server error"}
    }
)
async def create_user_profile(
    user_profile_data: UserProfileCreate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserProfileResponse:
    """
    Create a user profile for the authenticated user.
    
    **Note**: Users can only create their own profile. The user_id is automatically
    set from the authenticated user's ID (from JWT token).
    
    Args:
        user_profile_data: Profile data to create
        current_user: Authenticated user (from JWT token)
        db: Database session
        
    Returns:
        Created UserProfileResponse object
        
    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if user not found
            - 409 if profile already exists
            - 500 for unexpected errors
    """
    user_service = UserService()
    try:
        # Create profile for the authenticated user (current_user.id)
        user_profile = await user_service.create_user_profile(
            db, 
            current_user.id, 
            user_profile_data
        )
        logger.info(f"Profile created successfully for user: {current_user.id}")
        return user_profile
    except ValueError as e:
        logger.warning(f"Profile creation failed - user not found: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except IntegrityError as e:
        # Profile already exists (unique constraint violation)
        error_str = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "uq_user_profiles_user_id" in error_str or "unique constraint" in error_str.lower():
            logger.warning(f"Profile already exists for user: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A profile already exists for this user. Use PATCH to update it instead."
            ) from e
        # Other integrity errors (e.g., foreign key violation)
        logger.error(f"Database integrity error creating profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create profile due to a data conflict"
        ) from e
    except Exception as e:
        # Unexpected errors
        logger.error(
            f"Unexpected error creating profile for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the profile"
        ) from e

@router.patch(
    "/profile",
    response_model=UserProfileResponse,
    summary="Update user profile",
    description="Update the user profile for the authenticated user. All fields are optional for partial updates.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Profile updated successfully"},
        400: {"description": "Invalid request data or validation error"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "User profile not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_user_profile(
    user_profile_data: UserProfileUpdate,
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserProfileResponse:
    """
    Update the user profile for the authenticated user.
    
    **Partial Updates**: Only provided fields will be updated. Omitted fields remain unchanged.
    
    Args:
        user_profile_data: Profile update data (all fields optional)
        current_user: Authenticated user (from JWT token)
        db: Database session
        
    Returns:
        Updated UserProfileResponse object
        
    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if profile not found
            - 400 for validation errors
            - 500 for unexpected errors
    """
    user_service = UserService()
    try:
        user_profile = await user_service.update_user_profile(
            db, 
            current_user.id, 
            user_profile_data
        )
        if not user_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        logger.info(f"Profile updated successfully for user: {current_user.id}")
        return user_profile
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) without wrapping
        raise
    except Exception as e:
        # Unexpected errors
        logger.error(
            f"Unexpected error updating profile for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the profile"
        ) from e

@router.delete(
    "/profile",
    summary="Delete user profile",
    description="Delete the user profile for the authenticated user.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Profile deleted successfully"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "User profile not found"},
        500: {"description": "Internal server error"}
    }
)
async def delete_user_profile(
    current_user: WorkOSUserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete the user profile for the authenticated user.
    
    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
        
    Returns:
        None (204 No Content)
        
    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if profile not found
            - 500 for unexpected errors
    """
    user_service = UserService()
    try:
        deleted = await user_service.delete_user_profile(db, current_user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        logger.info(f"Profile deleted successfully for user: {current_user.id}")
        return None
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) without wrapping
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error deleting profile for user {current_user.id}: {type(e).__name__}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the user profile"
        ) from e


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

