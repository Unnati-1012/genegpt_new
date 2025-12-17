# backend/app/auth/__init__.py
"""
Authentication module for Noviq.AI.
"""

from .models import User, ChatHistory, UserProject, PinnedThread
from .schemas import (
    UserCreate, 
    UserLogin, 
    UserResponse, 
    TokenResponse, 
    TokenData
)
from .utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)
from .dependencies import get_current_user, get_current_user_optional
from .database import get_db, init_db, close_db
from .routes import router as auth_router

__all__ = [
    # Models
    "User",
    "ChatHistory", 
    "UserProject",
    "PinnedThread",
    # Schemas
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "TokenData",
    # Utils
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    # Dependencies
    "get_current_user",
    "get_current_user_optional",
    # Database
    "get_db",
    "init_db",
    "close_db",
    # Router
    "auth_router",
]
