# backend/app/auth/schemas.py
"""
Pydantic schemas for authentication in Noviq.AI.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, Field, validator
import re


# =============================================================================
# USER SCHEMAS
# =============================================================================
class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    
    @validator("password")
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class UserResponse(BaseModel):
    """Schema for user response (excludes password)."""
    id: str
    email: str
    created_at: datetime
    is_active: bool
    preferences: Dict[str, Any] = {}
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    email: Optional[EmailStr] = None
    preferences: Optional[Dict[str, Any]] = None


class PasswordChange(BaseModel):
    """Schema for changing password."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @validator("new_password")
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


# =============================================================================
# TOKEN SCHEMAS
# =============================================================================
class TokenResponse(BaseModel):
    """Schema for token response after login."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenData(BaseModel):
    """Schema for decoded token data."""
    sub: Optional[str] = None  # user_id
    exp: Optional[datetime] = None
    type: Optional[str] = None


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str


# =============================================================================
# CHAT HISTORY SCHEMAS
# =============================================================================
class MessageSchema(BaseModel):
    """Schema for a single chat message."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None


class ChatHistoryCreate(BaseModel):
    """Schema for creating a new chat."""
    title: Optional[str] = "New Chat"
    messages: List[MessageSchema] = []


class ChatHistoryUpdate(BaseModel):
    """Schema for updating a chat."""
    title: Optional[str] = None
    messages: Optional[List[MessageSchema]] = None


class ChatHistoryResponse(BaseModel):
    """Schema for chat history response."""
    id: str
    user_id: str
    title: str
    messages: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ChatHistoryListResponse(BaseModel):
    """Schema for list of chat histories (minimal info)."""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    
    class Config:
        from_attributes = True


# =============================================================================
# PROJECT SCHEMAS
# =============================================================================
class ProjectCreate(BaseModel):
    """Schema for creating a project."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ""
    data: Optional[Dict[str, Any]] = {}


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""
    name: Optional[str] = None
    description: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    """Schema for project response."""
    id: str
    user_id: str
    name: str
    description: str
    data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# =============================================================================
# PINNED THREAD SCHEMAS
# =============================================================================
class PinnedThreadCreate(BaseModel):
    """Schema for pinning a thread."""
    chat_id: str
    note: Optional[str] = ""


class PinnedThreadResponse(BaseModel):
    """Schema for pinned thread response."""
    id: str
    user_id: str
    chat_id: str
    pinned_at: datetime
    note: str
    
    class Config:
        from_attributes = True
