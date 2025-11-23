import asyncio
import logging
import time
from typing import Optional

import httpx
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import (
    BadSignatureError,
    DecodeError,
    ExpiredTokenError,
    InvalidClaimError,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from workos import WorkOSClient

from app.api.v1.schemas.auth import (
    AuthUserResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginResponse,
    RefreshTokenResponse,
    SignupResponse,
    VerifyEmailResponse,
    WorkOSAuthorizationRequest,
    WorkOSLoginRequest,
    WorkOSRefreshTokenRequest,
    WorkOSResetPasswordRequest,
    WorkOSUserResponse,
    WorkOsVerifyEmailRequest,
)
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self.workos_client = WorkOSClient(
            api_key=settings.WORKOS_API_KEY, client_id=settings.WORKOS_CLIENT_ID
        )
        # Cache JWKS to avoid repeated fetches (cache for 1 hour)
        self._jwks_cache: Optional[dict] = None
        self._jwks_cache_expiry: Optional[float] = None

    async def _decode_and_validate_token(self, access_token: str) -> dict:
        """
        Decode and validate a JWT token using WorkOS JWKS.

        This is a private helper method that extracts the common JWKS fetch/cache
        and token decoding logic used by both verify_session and logout.

        Args:
            access_token: JWT token to decode and validate

        Returns:
            Dict of token claims (decoded and validated)

        Raises:
            ValueError: If token is invalid, expired, or signature verification fails
        """
        # Get JWKS URL from WorkOS SDK
        jwks_url = await asyncio.to_thread(
            self.workos_client.user_management.get_jwks_url
        )

        # Fetch JWKS (with caching to avoid repeated API calls)
        current_time = time.time()
        if not self._jwks_cache or (
            self._jwks_cache_expiry and current_time > self._jwks_cache_expiry
        ):
            jwks_start = time.time()
            import sys

            sys.stdout.write(f"[TIMING] Fetching JWKS from: {jwks_url}\n")
            sys.stdout.flush()
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url, timeout=10.0)
                response.raise_for_status()
                self._jwks_cache = response.json()
                # Cache for 1 hour (JWKS keys don't change often)
                self._jwks_cache_expiry = current_time + 3600
                jwks_time = (time.time() - jwks_start) * 1000
                sys.stdout.write(f"[TIMING] JWKS fetch took {jwks_time:.1f}ms\n")
                sys.stdout.flush()
                logger.debug(
                    f"JWKS fetched and cached. Keys: {len(self._jwks_cache.get('keys', []))}"
                )
        else:
            import sys

            sys.stdout.write(
                f"[TIMING] JWKS cache HIT (expires in {self._jwks_cache_expiry - current_time:.1f}s)\n"
            )
            sys.stdout.flush()

        # Create JWK set from JWKS
        jwk_set = JsonWebKey.import_key_set(self._jwks_cache)

        # Verify and decode the JWT
        claims = jwt.decode(
            access_token,
            jwk_set,
            claims_options={"exp": {"essential": True}, "iat": {"essential": True}},
        )

        # CRITICAL: Validate claims (expiration, issued at, etc.)
        claims.validate()

        return claims

    async def verify_email(
        self, verify_email_request: WorkOsVerifyEmailRequest, db: AsyncSession
    ) -> VerifyEmailResponse:
        """
        Verify email and return response with user info including is_onboarded.

        Args:
            verify_email_request: Email verification request
            db: Database session to fetch user's is_onboarded status

        Returns:
            VerifyEmailResponse with user info including is_onboarded
        """
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        # Reference: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
        response = await asyncio.to_thread(
            self.workos_client.user_management.authenticate_with_email_verification,
            code=verify_email_request.code,
            pending_authentication_token=verify_email_request.pending_authentication_token,
            ip_address=verify_email_request.ip_address,
            user_agent=verify_email_request.user_agent,
        )

        # Fetch user from database to get is_onboarded
        user_id = response.user.id if response.user else None
        is_onboarded = False
        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            db_user = result.scalar_one_or_none()
            if db_user:
                is_onboarded = db_user.is_onboarded

        # Build AuthUserResponse with is_onboarded
        user_response = None
        if response.user:
            user_response = AuthUserResponse(
                object=response.user.object,
                id=response.user.id,
                email=response.user.email,
                first_name=response.user.first_name,
                last_name=response.user.last_name,
                email_verified=response.user.email_verified,
                profile_picture_url=response.user.profile_picture_url,
                created_at=response.user.created_at,
                updated_at=response.user.updated_at,
                is_onboarded=is_onboarded,
            )

        return VerifyEmailResponse(
            access_token=response.access_token,
            refresh_token=response.refresh_token,
            authentication_method=response.authentication_method,
            impersonator=response.impersonator,
            organization_id=response.organization_id,
            user=user_response,
            sealed_session=response.sealed_session,
        )

    async def login(
        self, login_request: WorkOSLoginRequest, db: AsyncSession
    ) -> LoginResponse:
        """
        Login user and return response with user info including is_onboarded.

        Args:
            login_request: Login request
            db: Database session to fetch user's is_onboarded status

        Returns:
            LoginResponse with user info including is_onboarded
        """
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        response = await asyncio.to_thread(
            self.workos_client.user_management.authenticate_with_password,
            email=login_request.email,
            password=login_request.password,
            ip_address=login_request.ip_address,
            user_agent=login_request.user_agent,
        )

        # Fetch user from database to get is_onboarded
        user_id = response.user.id if response.user else None
        is_onboarded = False
        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            db_user = result.scalar_one_or_none()
            if db_user:
                is_onboarded = db_user.is_onboarded

        # Build AuthUserResponse with is_onboarded
        user_response = None
        if response.user:
            user_response = AuthUserResponse(
                object=response.user.object,
                id=response.user.id,
                email=response.user.email,
                first_name=response.user.first_name,
                last_name=response.user.last_name,
                email_verified=response.user.email_verified,
                profile_picture_url=response.user.profile_picture_url,
                created_at=response.user.created_at,
                updated_at=response.user.updated_at,
                is_onboarded=is_onboarded,
            )

        return LoginResponse(
            user=user_response,
            organization_id=response.organization_id,
            access_token=response.access_token,
            refresh_token=response.refresh_token,
        )

    async def signup(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
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
                orig=Exception(
                    'duplicate key value violates unique constraint "ix_users_email"'
                ),
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
            self.workos_client.user_management.create_user, **create_user_payload
        )

        # Create user in database with error handling
        # If DB insert fails, we need to clean up the WorkOS user to prevent orphaned accounts
        # Reference: https://workos.com/docs/reference/user-management/delete-user
        try:
            user = User(
                id=workos_user.id,
                email=workos_user.email,
                first_name=workos_user.first_name,
                last_name=workos_user.last_name,
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
                    user_id=workos_user.id,
                )
                logger.info(f"Successfully cleaned up WorkOS user {workos_user.id}")
            except Exception as cleanup_error:
                # Log cleanup failure but don't mask the original error
                logger.error(
                    f"Failed to clean up WorkOS user {workos_user.id} after DB failure. "
                    f"Cleanup error: {cleanup_error}. Original error: {db_error}",
                    exc_info=True,
                )
            # Re-raise the original database error
            raise

        logger.info(f"User created: {workos_user.id} ({email})")

        # Get is_onboarded from the user we just created in the database
        # The user object should have is_onboarded with default False
        is_onboarded = user.is_onboarded

        # Convert WorkOS user to AuthUserResponse schema with is_onboarded
        user_response = AuthUserResponse(
            object=workos_user.object,
            id=workos_user.id,
            email=workos_user.email,
            first_name=workos_user.first_name,
            last_name=workos_user.last_name,
            email_verified=workos_user.email_verified,
            profile_picture_url=workos_user.profile_picture_url,
            created_at=workos_user.created_at,
            updated_at=workos_user.updated_at,
            is_onboarded=is_onboarded,
        )

        return SignupResponse(user=user_response)

    async def forgot_password(
        self, forgot_password_request: ForgotPasswordRequest
    ) -> ForgotPasswordResponse:

        # WorkOS generates token and sends email
        # The email will use the URL you configured in Dashboard → Redirects
        await asyncio.to_thread(
            self.workos_client.user_management.create_password_reset,
            email=forgot_password_request.email,
        )

        # WorkOS automatically sends email with your configured URL
        # The URL will be: your-frontend.com/reset-password?token=...
        # NB: The WorkOS dashboard needs to be updated with the frontend password reset URL

        # Return generic success message (don't expose token/URL)
        return ForgotPasswordResponse(
            message="If an account exists with this email address, a password reset link has been sent."
        )

    async def reset_password(
        self, reset_password_request: WorkOSResetPasswordRequest, db: AsyncSession
    ) -> AuthUserResponse:
        """
        Reset a user's password.

        Args:
            reset_password_request: WorkOSResetPasswordRequest
            db: Database session to fetch user's is_onboarded status

        Returns:
            AuthUserResponse: User information including is_onboarded
        """
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        response = await asyncio.to_thread(
            self.workos_client.user_management.reset_password,
            token=reset_password_request.token,
            new_password=reset_password_request.new_password,
        )

        # Fetch user from database to get is_onboarded
        user_id = response.id
        is_onboarded = False
        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            db_user = result.scalar_one_or_none()
            if db_user:
                is_onboarded = db_user.is_onboarded

        return AuthUserResponse(
            object=response.object,
            id=response.id,
            email=response.email,
            first_name=response.first_name,
            last_name=response.last_name,
            email_verified=response.email_verified,
            profile_picture_url=response.profile_picture_url,
            created_at=response.created_at,
            updated_at=response.updated_at,
            is_onboarded=is_onboarded,
        )

    # Generate OAuth2 authorization URL
    async def generate_oauth2_authorization_url(
        self, authorization_request: WorkOSAuthorizationRequest
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
            self.workos_client.user_management.get_authorization_url, **params
        )
        return authorization_url

    async def oauth2_callback(self, code: str, db: AsyncSession) -> LoginResponse:
        """
        Exchange a OAuth2 code for access token and refresh token.

        Args:
            code: OAuth2 code
            db: Database session to fetch user's is_onboarded status

        Returns:
            LoginResponse: Access token and refresh token with user info including is_onboarded
        """
        # Offload synchronous WorkOS call to thread pool to avoid blocking event loop
        response = await asyncio.to_thread(
            self.workos_client.user_management.authenticate_with_code, code=code
        )

        # Fetch user from database to get is_onboarded
        user_id = response.user.id if response.user else None
        is_onboarded = False
        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            db_user = result.scalar_one_or_none()
            if db_user:
                is_onboarded = db_user.is_onboarded

        # Build AuthUserResponse with is_onboarded
        user_response = None
        if response.user:
            user_response = AuthUserResponse(
                object=response.user.object,
                id=response.user.id,
                email=response.user.email,
                first_name=response.user.first_name,
                last_name=response.user.last_name,
                email_verified=response.user.email_verified,
                profile_picture_url=response.user.profile_picture_url,
                created_at=response.user.created_at,
                updated_at=response.user.updated_at,
                is_onboarded=is_onboarded,
            )

        return LoginResponse(
            user=user_response,
            organization_id=response.organization_id,
            access_token=response.access_token,
            refresh_token=response.refresh_token,
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
            # Decode and validate token using shared helper method
            claims = await self._decode_and_validate_token(access_token)

            logger.debug(f"Token verified successfully. User: {claims.get('sub')}")

            # Check token blacklist before returning
            # This allows immediate invalidation of tokens after logout
            # Uses Redis for multi-instance support, falls back to in-memory if Redis not configured
            jti = claims.get("jti")  # JWT ID - unique identifier for this token
            if jti:
                from app.core.dependencies import (
                    _cleanup_expired_blacklist_tokens,
                    is_token_blacklisted,
                )

                # Clean up expired tokens from in-memory blacklist (only for fallback)
                _cleanup_expired_blacklist_tokens()

                # Check if token is blacklisted (uses Redis if available)
                if await is_token_blacklisted(jti):
                    logger.warning(f"Token is blacklisted: {jti}")
                    # Return "expired" message for security - don't reveal token was revoked
                    raise ValueError("Token has expired")

            # Extract user information from verified token
            # Reference: https://workos.com/docs/reference/authkit/session-tokens/access-token
            return {
                "user_id": claims.get("sub"),  # User ID (subject)
                "session_id": claims.get("sid"),  # Session ID
                "jti": jti,  # JWT ID (for blacklisting)
                "organization_id": claims.get("org_id"),  # Organization ID
                "role": claims.get("role"),  # User role (e.g., "member", "admin")
                "roles": claims.get("roles", []),  # Array of roles
                "permissions": claims.get("permissions", []),  # Permissions array
                "entitlements": claims.get("entitlements", []),  # Entitlements array
                "exp": claims.get("exp"),
                "iat": claims.get("iat"),
            }

        except ExpiredTokenError:
            logger.warning("Token has expired")
            raise ValueError("Token has expired")
        except BadSignatureError:
            logger.warning("Invalid token signature")
            raise ValueError(
                "Invalid token signature - token may have been tampered with"
            )
        except DecodeError as e:
            logger.warning(f"Failed to decode token: {e}")
            raise ValueError(f"Invalid token format: {e}")
        except InvalidClaimError as e:
            logger.warning(f"Invalid token claim: {e}")
            raise ValueError(f"Invalid token claim: {e}")
        except Exception as e:
            logger.error(
                f"Error verifying session: {type(e).__name__}: {e}", exc_info=True
            )
            raise ValueError(f"Token verification failed: {str(e)}")

    # refresh token
    async def refresh_token(
        self, refresh_token_request: WorkOSRefreshTokenRequest
    ) -> RefreshTokenResponse:
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
            user_agent=refresh_token_request.user_agent,
        )
        return RefreshTokenResponse(
            access_token=response.access_token, refresh_token=response.refresh_token
        )

    async def logout(self, access_token: str) -> bool:
        """
        Logout a user by revoking their session and blacklisting the token.

        Extracts the session ID from the access token and revokes it via WorkOS API.
        Also adds the token to the blacklist to immediately invalidate it.
        This invalidates the session and prevents the token from being used.

        Reference: https://workos.com/docs/reference/authkit/authentication/get-authorization-url/pkce

        Args:
            access_token: JWT access token containing session ID and JWT ID (jti)

        Returns:
            True if logout successful, False otherwise

        Raises:
            ValueError: If token is invalid or session ID cannot be extracted
        """
        try:
            # Decode and validate token using shared helper method
            claims = await self._decode_and_validate_token(access_token)

            # Extract required claims
            jti = claims.get("jti")  # JWT ID for blacklisting
            token_exp = claims.get("exp")  # Token expiration
            session_id = claims.get("sid")  # Session ID for revocation

            if not session_id:
                logger.warning("Token missing session_id (sid claim)")
                raise ValueError("Invalid token: missing session information")

            # Revoke the session via WorkOS API
            # Reference: https://workos.com/docs/reference/authkit/authentication/get-authorization-url/pkce
            # POST /user_management/sessions/revoke
            await asyncio.to_thread(
                self.workos_client.user_management.revoke_session, session_id=session_id
            )

            # Add token to blacklist using JWT ID (jti)
            # Uses Redis for multi-instance support, falls back to in-memory if Redis not configured
            # Store with token expiration time so it auto-cleans up when token expires
            if jti and token_exp:
                from app.core.dependencies import add_token_to_blacklist

                success = await add_token_to_blacklist(jti, float(token_exp))
                if success:
                    logger.info(f"Token blacklisted: {jti} (expires at {token_exp})")
                else:
                    logger.warning(f"Failed to blacklist token: {jti}")
            else:
                logger.warning(
                    f"Token missing jti or exp claim, cannot blacklist: jti={jti}, exp={token_exp}"
                )

            logger.info(f"Session revoked successfully: {session_id}")
            return True

        except ValueError:
            # Let token verification errors propagate unchanged
            raise
        except Exception as e:
            logger.error(f"Error during logout: {type(e).__name__}: {e}", exc_info=True)
            raise ValueError(f"Logout failed: {e}") from e
