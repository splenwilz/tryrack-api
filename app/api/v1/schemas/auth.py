from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime

from app.api.v1.schemas.user import WorkOSUserResponse

class EmailVerificationRequiredResponse(BaseModel):
    message: str
    pending_authentication_token: str
    email_verification_id: str
    email: str
    requires_verification: bool = True

class VerifyEmailRequest(BaseModel):
    pending_authentication_token: str = Field(..., description="Pending authentication token")
    code: str = Field(..., description="Code")

class WorkOsVerifyEmailRequest(VerifyEmailRequest):
    ip_address: str = Field(..., description="User IP address")
    user_agent: str = Field(..., description="User user agent")



class LoginRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")

class SignupRequest(BaseModel):
    """
    Schema for user signup/registration.
    
    Used for public self-registration endpoint.
    Includes password validation and confirmation.
    """
    email: str = Field(..., min_length=1, max_length=255, description="User email")
    password: str = Field(..., min_length=8, max_length=255, description="User password")
    confirm_password: str = Field(..., min_length=8, max_length=255, description="Password confirmation")
    first_name: Optional[str] = Field(None, max_length=255, description="User first name")
    last_name: Optional[str] = Field(None, max_length=255, description="User last name")
    
    @field_validator('password')
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one number")
        if not any(char.isalpha() for char in v):
            raise ValueError("Password must contain at least one letter")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v
    
    @model_validator(mode='after')
    def validate_confirm_password(self) -> 'SignupRequest':
        """Ensure password and confirm_password match."""
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm password do not match")
        return self

class WorkOSLoginRequest(LoginRequest):
    ip_address: str = Field(..., description="User IP address")
    user_agent: str = Field(..., description="User user agent")

class LoginResponse(BaseModel):
    user: WorkOSUserResponse = Field(..., description="User")
    organization_id: str | None = Field(None, description="Organization ID")
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")

class SignupResponse(BaseModel):
    """
    Response for user signup.
    
    Returns user information without tokens since email verification is required.
    User must verify email and then login to get tokens.
    """
    user: WorkOSUserResponse = Field(..., description="Created user")
    message: str = Field(default="User created successfully. Please verify your email to login.", description="Success message")
    is_verified: bool = Field(default=False, description="Whether the user is verified")


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="User email")


class ForgotPasswordResponse(BaseModel):
    message: str = Field(
        default="If an account exists with this email address, a password reset link has been sent.",
        description="Generic success message"
    )

class WorkOSResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Reset password token")
    new_password: str = Field(..., description="New password")

class ResetPasswordRequest(WorkOSResetPasswordRequest):
    confirm_new_password: str = Field(..., description="Confirm new password")

    @field_validator('new_password')
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one number")
        if not any(char.isalpha() for char in v):
            raise ValueError("Password must contain at least one letter")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v
    
    @model_validator(mode='after')
    def validate_confirm_new_password(self) -> 'ResetPasswordRequest':
        """Ensure new password and confirm_new_password match."""
        if self.new_password != self.confirm_new_password:
            raise ValueError("New password and confirm new password do not match")
        return self

class WorkOSImpersonatorResponse(BaseModel):
    email: str | None = Field(None, description="Impersonator email")
    reason: str | None = Field(None, description="Impersonation reason")


class VerifyEmailResponse(BaseModel):
    access_token: str | None = Field(None, description="Access token")
    refresh_token: str | None = Field(None, description="Refresh token")
    authentication_method: str | None = Field(None, description="Authentication method")
    impersonator: WorkOSImpersonatorResponse | None = Field(None, description="Impersonator")
    organization_id: str | None = Field(None, description="Organization ID")
    user: WorkOSUserResponse | None = Field(None, description="User")
    sealed_session: str | None = Field(None, description="Sealed session")


class AuthorizationRequest(BaseModel):
    """
    Request to generate OAuth2 authorization URL.
    
    Supports two patterns:
    1. AuthKit: Use provider="authkit" (unified interface)
    2. SSO: Use connection_id (direct provider connection)
    
    Exactly one of provider or connection_id must be provided.
    """
    provider: str | None = Field(
        None,
        description="AuthKit provider (use 'authkit' for unified interface). Mutually exclusive with connection_id."
    )
    connection_id: str | None = Field(
        None,
        description="WorkOS SSO connection ID for direct provider (e.g., Google, Microsoft). Mutually exclusive with provider."
    )
    redirect_uri: str = Field(
        ...,
        description="URI to redirect to after authentication. Must be in allowed list."
    )
    state: str | None = Field(
        None,
        description="Optional state parameter for CSRF protection"
    )
    
    @model_validator(mode='after')
    def validate_provider_or_connection(self):
        """Ensure exactly one of provider or connection_id is provided"""
        has_provider = self.provider is not None
        has_connection = self.connection_id is not None
        
        if not has_provider and not has_connection:
            raise ValueError("Either 'provider' or 'connection_id' must be provided")
        
        if has_provider and has_connection:
            raise ValueError("'provider' and 'connection_id' are mutually exclusive. Provide only one.")
        
        return self

class AuthorizationUrlResponse(BaseModel):
    authorization_url: str = Field(..., description="Authorization URL")

class WorkOSAuthorizationRequest(AuthorizationRequest):
    pass

class OAuthCallbackRequest(BaseModel):
    code: str = Field(..., description="Authorization code from OAuth callback")
    state: str | None = Field(None, description="State parameter for CSRF verification")

class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")

class WorkOSRefreshTokenRequest(RefreshTokenRequest):
    ip_address: str = Field(..., description="User IP address")
    user_agent: str = Field(..., description="User user agent")

class RefreshTokenResponse(BaseModel):
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")