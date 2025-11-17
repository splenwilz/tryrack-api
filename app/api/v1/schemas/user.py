from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator


class UserBase(BaseModel):
    """
    Base schema with common User fields
    Used as base for create schemas
    """
    first_name: Optional[str] = Field(None, max_length=255, description="User first name")
    last_name: Optional[str] = Field(None, max_length=255, description="User last name")
    email: str = Field(..., min_length=1, max_length=255, description="User email")
    password: str = Field(..., min_length=8, max_length=255, description="User password")

class UserCreate(UserBase):
    """
    Schema for creating a new user
    Inherits from UserBase
    Attributes:
        first_name: User first name (optional)
        last_name: User last name (optional)
        email: User email (required)
        password: User password (required)
        confirm_password: User confirm password (required)
    Reference: https://fastapi.tiangolo.com/tutorial/body/
    """
    confirm_password: str = Field(..., min_length=8, max_length=255, description="User confirm password")
    
    @field_validator('password')
    def validate_password(cls, v: str) -> str:
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
    def validate_confirm_password(self) -> 'UserCreate':
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm password do not match")
        return self
    


class UserResponse(BaseModel):
    """
    Schema for user response
    Includes all fields from UserBase plus database-generated fields
    Attributes:
        id: User ID (required)
        email: User email (required)
        first_name: User first name (optional)
        last_name: User last name (optional)
        created_at: Timestamp when user was created (optional)
        updated_at: Timestamp when user was last updated (optional)
    Reference: https://fastapi.tiangolo.com/tutorial/response-model/
    """
    id: str = Field(..., description="User ID")
    first_name: Optional[str] = Field(None, max_length=255, description="User first name")
    last_name: Optional[str] = Field(None, max_length=255, description="User last name")
    email: str = Field(..., min_length=1, max_length=255, description="User email")
    created_at: Optional[datetime] = Field(None, description="Timestamp when user was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when user was last updated")

    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    """
    Schema for updating a user
    All fields are optional for partial updates
    """
    first_name: Optional[str] = Field(None, max_length=255, description="User first name")
    last_name: Optional[str] = Field(None, max_length=255, description="User last name")


class WorkOSUserResponse(BaseModel):
    object: str = Field(..., description="Object")
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    first_name: str | None = Field(None, description="User first name")
    last_name: str | None = Field(None, description="User last name") 
    email_verified: bool = Field(..., description="User email verified")
    profile_picture_url: str | None = Field(None, description="User profile picture URL")
    created_at: datetime = Field(..., description="User created at")
    updated_at: datetime = Field(..., description="User updated at")

    class Config:
        from_attributes = True