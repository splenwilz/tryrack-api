import asyncio
import time
from typing import Optional
import httpx
from authlib.jose import jwt, JsonWebKey
from authlib.jose.errors import DecodeError, ExpiredTokenError, InvalidClaimError, BadSignatureError
from workos import WorkOSClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.v1.schemas.auth import ForgotPasswordRequest, ForgotPasswordResponse, LoginResponse, RefreshTokenResponse, SignupResponse, WorkOSAuthorizationRequest, WorkOSLoginRequest, WorkOSRefreshTokenRequest, WorkOSResetPasswordRequest, WorkOsVerifyEmailRequest, WorkOSUserResponse
from app.core.config import settings
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.workos_client = WorkOSClient(
            api_key=settings.WORKOS_API_KEY,
            client_id=settings.WORKOS_CLIENT_ID
        )
        # Cache JWKS to avoid repeated fetches (cache for 1 hour)
        self._jwks_cache: Optional[dict] = None
        self._jwks_cache_expiry: Optional[float] = None

    async def verify_email(self, verify_email_request: WorkOsVerifyEmailRequest):
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        # Reference: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
        response = await asyncio.to_thread(
            self.workos_client.user_management.authenticate_with_email_verification,
            code=verify_email_request.code,
            pending_authentication_token=verify_email_request.pending_authentication_token,
            ip_address=verify_email_request.ip_address,
            user_agent=verify_email_request.user_agent
        )
        return response

    async def login(self, login_request: WorkOSLoginRequest) -> LoginResponse:
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        response = await asyncio.to_thread(
            self.workos_client.user_management.authenticate_with_password,
            email=login_request.email,
            password=login_request.password,
            ip_address=login_request.ip_address,
            user_agent=login_request.user_agent
        )
        return LoginResponse(
            user=response.user,
            organization_id=response.organization_id,
            access_token=response.access_token,
            refresh_token=response.refresh_token
        )

    async def signup(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> SignupResponse:
        """
        Sign up a new user.
        
        Creates the user in WorkOS and saves to database.
        User must verify their email before they can login.
        
        Args:
            db: Database session
            email: User email
            password: User password
            first_name: Optional first name
            last_name: Optional last name
            
        Returns:
            SignupResponse with user info (no tokens - email verification required)
            
        Raises:
            IntegrityError: If user already exists in database (email conflict)
            BadRequestException: If user creation fails in WorkOS (e.g., email already exists)
        """
        # Check if user already exists in database BEFORE creating in WorkOS
        # This prevents creating orphaned users in WorkOS if DB insert fails
        result = await db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            logger.warning(f"User already exists in database: {email}")
            # Raise IntegrityError to match database constraint violation behavior
            # This will be caught by the route handler and converted to 409 Conflict
            from sqlalchemy.exc import IntegrityError as SQLIntegrityError
            raise SQLIntegrityError(
                statement="INSERT INTO users",
                params=None,
                orig=Exception("duplicate key value violates unique constraint \"ix_users_email\"")
            )
        
        # Create user in WorkOS (only if not in database)
        create_user_payload = {
            "email": email,
            "password": password,
        }
        if first_name:
            create_user_payload["first_name"] = first_name
        if last_name:
            create_user_payload["last_name"] = last_name
        
        # Offload synchronous WorkOS call to thread pool
        workos_user = await asyncio.to_thread(
            self.workos_client.user_management.create_user,
            **create_user_payload
        )
        
        # Create user in database with error handling
        # If DB insert fails, we need to clean up the WorkOS user to prevent orphaned accounts
        # Reference: https://workos.com/docs/reference/user-management/delete-user
        try:
            user = User(
                id=workos_user.id,
                email=workos_user.email,
                first_name=workos_user.first_name,
                last_name=workos_user.last_name
            )
            db.add(user)
            await db.flush()
        except Exception as db_error:
            # Database operation failed - clean up WorkOS user to prevent orphaned account
            # This prevents users from being locked out if DB insert fails (race condition, connection issue, etc.)
            logger.warning(
                f"Database insert failed after WorkOS user creation for {email}. "
                f"Cleaning up WorkOS user {workos_user.id}. Error: {db_error}"
            )
            try:
                await asyncio.to_thread(
                    self.workos_client.user_management.delete_user,
                    user_id=workos_user.id
                )
                logger.info(f"Successfully cleaned up WorkOS user {workos_user.id}")
            except Exception as cleanup_error:
                # Log cleanup failure but don't mask the original error
                logger.error(
                    f"Failed to clean up WorkOS user {workos_user.id} after DB failure. "
                    f"Cleanup error: {cleanup_error}. Original error: {db_error}",
                    exc_info=True
                )
            # Re-raise the original database error
            raise
        
        logger.info(f"User created: {workos_user.id} ({email})")
        
        # Convert WorkOS user to response schema
        user_response = WorkOSUserResponse(
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
        
        return SignupResponse(user=user_response)

    async def forgot_password(self, forgot_password_request: ForgotPasswordRequest) -> ForgotPasswordResponse:
        
         # WorkOS generates token and sends email
        # The email will use the URL you configured in Dashboard → Redirects
        await asyncio.to_thread(
            self.workos_client.user_management.create_password_reset,
            email=forgot_password_request.email
        )
        
        # WorkOS automatically sends email with your configured URL
        # The URL will be: your-frontend.com/reset-password?token=...
        # NB: The WorkOS dashboard needs to be updated with the frontend password reset URL
        
        # Return generic success message (don't expose token/URL)
        return ForgotPasswordResponse(
            message="If an account exists with this email address, a password reset link has been sent."
        )

    async def reset_password(self, reset_password_request: WorkOSResetPasswordRequest) -> WorkOSUserResponse:
        """
        Reset a user's password.
        
        Args:
            reset_password_request: WorkOSResetPasswordRequest

        Returns:
            WorkOSUserResponse: User information
        """
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        response = await asyncio.to_thread(
            self.workos_client.user_management.reset_password,
            token=reset_password_request.token,
            new_password=reset_password_request.new_password
        )
        return WorkOSUserResponse(
            object=response.object,
            id=response.id,
            email=response.email,
            first_name=response.first_name,
            last_name=response.last_name,
            email_verified=response.email_verified,
            profile_picture_url=response.profile_picture_url,
            created_at=response.created_at,
            updated_at=response.updated_at,
        )

    # Generate OAuth2 authorization URL
    async def generate_oauth2_authorization_url(
        self, 
        authorization_request: WorkOSAuthorizationRequest
    ) -> str:
        """
        Generate OAuth2 authorization URL.
        
        Supports two patterns:
        1. AuthKit: provider="authkit" → Unified authentication interface
        2. SSO: connection_id="conn_xxx" → Direct provider connection
        
        Args:
            authorization_request: Request containing either provider or connection_id
            
        Returns:
            Authorization URL string
        """
        params = {
            "redirect_uri": authorization_request.redirect_uri,
        }
        
        # Add state if provided
        if authorization_request.state:
            params["state"] = authorization_request.state
        
        # Determine which pattern to use
        if authorization_request.provider:
            # AuthKit pattern
            params["provider"] = authorization_request.provider
        elif authorization_request.connection_id:
            # SSO pattern
            params["connection_id"] = authorization_request.connection_id
        
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        authorization_url = await asyncio.to_thread(
            self.workos_client.user_management.get_authorization_url,
            **params
        )
        return authorization_url


    async def oauth2_callback(
        self, 
        code: str
    ) -> LoginResponse:
        """
        Exchange a OAuth2 code for access token and refresh token.
        
        Args:
            code: OAuth2 code
            
        Returns:
            LoginResponse: Access token and refresh token
        """
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        response = await asyncio.to_thread(
            self.workos_client.user_management.authenticate_with_code,
            code=code
        )
        return LoginResponse(
            user=response.user,
            organization_id=response.organization_id,
            access_token=response.access_token,
            refresh_token=response.refresh_token
        )

    async def verify_session(self, access_token: str) -> dict:
        """
        Verify a WorkOS JWT access token with full signature verification.
        
        Uses WorkOS JWKS to verify the token signature. This ensures the token
        is authentic and hasn't been tampered with.
        
        Reference: 
        - https://workos.com/docs/reference/authkit/session-tokens/access-token
        - https://workos.com/docs/reference/authkit/session-tokens/jwks
        
        Args:
            access_token: JWT token from WorkOS
            
        Returns:
            Dict with user information from verified token:
            - user_id: User ID (sub claim)
            - session_id: Session ID (sid claim)
            - organization_id: Organization ID (org_id claim)
            - role: User role (role claim)
            - roles: Array of roles (roles claim)
            - permissions: Array of permissions (permissions claim)
            - entitlements: Array of entitlements (entitlements claim)
            - exp: Expiration timestamp
            - iat: Issued at timestamp
            
        Raises:
            ValueError: If token is invalid, expired, or signature verification fails
        """
        try:
            # Get JWKS URL from WorkOS SDK
            # Reference: https://workos.com/docs/reference/authkit/session-tokens/jwks
            # get_jwks_url() uses the client_id from the WorkOSClient initialization
            jwks_url = await asyncio.to_thread(
                self.workos_client.user_management.get_jwks_url
            )
            
            # Fetch JWKS (with caching to avoid repeated API calls)
            current_time = time.time()
            if not self._jwks_cache or (self._jwks_cache_expiry and current_time > self._jwks_cache_expiry):
                logger.debug(f"Fetching JWKS from: {jwks_url}")
                async with httpx.AsyncClient() as client:
                    response = await client.get(jwks_url, timeout=10.0)
                    response.raise_for_status()
                    self._jwks_cache = response.json()
                    # Cache for 1 hour (JWKS keys don't change often)
                    self._jwks_cache_expiry = current_time + 3600
                    logger.debug(f"JWKS fetched and cached. Keys: {len(self._jwks_cache.get('keys', []))}")
            
            # Create JWK set from JWKS
            # authlib handles parsing the JWKS and selecting the correct key
            jwk_set = JsonWebKey.import_key_set(self._jwks_cache)
            
            # Verify and decode the JWT
            # jwt.decode() verifies the signature using the correct key from JWKS (based on 'kid' in header)
            # However, it does NOT validate expiration/claims - that requires claims.validate()
            claims = jwt.decode(
                access_token,
                jwk_set,
                claims_options={
                    "exp": {"essential": True},
                    "iat": {"essential": True}
                }
            )
            
            # CRITICAL: Validate claims (expiration, issued at, etc.)
            # Without this, expired tokens would be accepted!
            claims.validate()
            
            logger.debug(f"Token verified successfully. User: {claims.get('sub')}")
            
            # Extract user information from verified token
            # Reference: https://workos.com/docs/reference/authkit/session-tokens/access-token
            return {
                'user_id': claims.get('sub'),              # User ID (subject)
                'session_id': claims.get('sid'),           # Session ID
                'organization_id': claims.get('org_id'),  # Organization ID
                'role': claims.get('role'),                # User role (e.g., "member", "admin")
                'roles': claims.get('roles', []),         # Array of roles
                'permissions': claims.get('permissions', []), # Permissions array
                'entitlements': claims.get('entitlements', []), # Entitlements array
                'exp': claims.get('exp'),
                'iat': claims.get('iat'),
            }
            
        except ExpiredTokenError:
            logger.warning("Token has expired")
            raise ValueError("Token has expired")
        except BadSignatureError:
            logger.warning("Invalid token signature")
            raise ValueError("Invalid token signature - token may have been tampered with")
        except DecodeError as e:
            logger.warning(f"Failed to decode token: {e}")
            raise ValueError(f"Invalid token format: {e}")
        except InvalidClaimError as e:
            logger.warning(f"Invalid token claim: {e}")
            raise ValueError(f"Invalid token claim: {e}")
        except Exception as e:
            logger.error(f"Error verifying session: {type(e).__name__}: {e}", exc_info=True)
            raise ValueError(f"Token verification failed: {str(e)}")


    # refresh token
    async def refresh_token(self, refresh_token_request: WorkOSRefreshTokenRequest) -> RefreshTokenResponse:
        """
        Refresh a WorkOS JWT access token.
        
        Args:
            refresh_token_request: WorkOSRefreshTokenRequest
            
        Returns:
            RefreshTokenResponse: Access token and refresh token
        """
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        response = await asyncio.to_thread(
            self.workos_client.user_management.authenticate_with_refresh_token,
            refresh_token=refresh_token_request.refresh_token,
            ip_address=refresh_token_request.ip_address,
            user_agent=refresh_token_request.user_agent
        )
        return RefreshTokenResponse(
            access_token=response.access_token,
            refresh_token=response.refresh_token
        )

