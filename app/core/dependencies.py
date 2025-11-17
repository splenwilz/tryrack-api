"""
Authentication dependencies for protecting endpoints
Reference: https://fastapi.tiangolo.com/tutorial/dependencies/
"""
import asyncio
import logging
from functools import lru_cache
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from workos import WorkOSClient
from workos.exceptions import AuthenticationException, NotFoundException

from app.services.auth import AuthService
from app.api.v1.schemas.auth import WorkOSUserResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

# HTTPBearer automatically extracts Bearer token from Authorization header
# Reference: https://fastapi.tiangolo.com/reference/security/#fastapi.security.HTTPBearer
security = HTTPBearer()


@lru_cache()
def get_auth_service() -> AuthService:
    """
    Get a singleton AuthService instance.
    
    Using lru_cache ensures the same AuthService instance is reused across requests,
    which preserves the JWKS cache (_jwks_cache and _jwks_cache_expiry) at the
    application level rather than request level. This avoids repeated JWKS API calls
    to WorkOS and improves performance.
    
    Reference: https://docs.python.org/3/library/functools.html#functools.lru_cache
    """
    return AuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> WorkOSUserResponse:
    """
    Dependency to get the current authenticated user.
    
    Validates the JWT access token from the Authorization header using WorkOS JWKS,
    then fetches full user details from WorkOS.
    
    Usage:
        @router.get("/protected")
        async def protected_route(current_user = Depends(get_current_user)):
            return {"user_id": current_user.id, "email": current_user.email}
    
    Args:
        credentials: HTTPAuthorizationCredentials containing the Bearer token
        
    Returns:
        WorkOSUserResponse: The authenticated user with full details
        
    Raises:
        HTTPException: 401 if token is invalid or missing
    """
    auth_service = get_auth_service()
    
    try:
        # Extract the token from credentials
        access_token = credentials.credentials
        logger.debug(f"Verifying session with token: {access_token[:20]}...")
        
        # Verify the session with WorkOS (validates JWT signature and expiration)
        # Reference: https://workos.com/docs/reference/authkit/session-tokens/access-token
        session_data = await auth_service.verify_session(access_token)
        
        user_id = session_data.get('user_id')
        if not user_id:
            logger.error("Token missing user_id (sub claim)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user information",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.debug(f"Token verified successfully. User ID: {user_id}")
        
        # Fetch full user details from WorkOS
        # The JWT contains basic info, but we fetch full details for complete user object
        workos_client = WorkOSClient(
            api_key=settings.WORKOS_API_KEY,
            client_id=settings.WORKOS_CLIENT_ID
        )
        
        # Offload synchronous WorkOS call to thread pool
        workos_user = await asyncio.to_thread(
            workos_client.user_management.get_user,
            user_id=user_id
        )
        
        # Convert WorkOS user to our schema
        user = WorkOSUserResponse(
            object=workos_user.object,
            id=workos_user.id,
            email=workos_user.email,
            first_name=workos_user.first_name,
            last_name=workos_user.last_name,
            email_verified=workos_user.email_verified,
            profile_picture_url=workos_user.profile_picture_url,
            created_at=workos_user.created_at,
            updated_at=workos_user.updated_at,
        )
        
        logger.debug(f"User fetched: {user.id} ({user.email})")
        return user
        
    except ValueError as e:
        # Map error to RFC6750-compliant WWW-Authenticate header
        msg = str(e)
        # Default values
        error = "invalid_token"
        description = msg or "The access token is invalid"

        if "expired" in msg.lower():
            description = "The access token expired"

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=msg,
            headers={
                "WWW-Authenticate": f'Bearer realm="api", error="{error}", error_description="{description}"'
            },
        ) from e
    except NotFoundException:
        # User not found in WorkOS (shouldn't happen if token is valid)
        logger.error(f"User not found in WorkOS after token verification")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        # Re-raise HTTP exceptions (already formatted)
        raise
    except Exception as e:
        # Unexpected error - log full details for debugging
        logger.error(f"Unexpected authentication error: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e