# backend/app/auth/dependencies.py
"""
FastAPI dependencies for authentication in Noviq.AI.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import User
from .service import get_user_by_id
from .utils import verify_access_token


# =============================================================================
# SECURITY SCHEME
# =============================================================================
# Bearer token security scheme
security = HTTPBearer(auto_error=False)


# =============================================================================
# AUTHENTICATION DEPENDENCIES
# =============================================================================
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    
    Validates the JWT token and returns the user.
    Raises HTTPException if token is invalid or user not found.
    
    Args:
        credentials: Bearer token credentials
        db: Database session
        
    Returns:
        Current authenticated User
        
    Raises:
        HTTPException: 401 if not authenticated
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials:
        raise credentials_exception
    
    token = credentials.credentials
    
    # Verify token
    payload = verify_access_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    
    if user_id is None:
        raise credentials_exception
    
    # Get user from database
    user = await get_user_by_id(db, user_id)
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to optionally get the current authenticated user.
    
    Returns None if not authenticated instead of raising an exception.
    Useful for endpoints that work both with and without authentication.
    
    Args:
        credentials: Bearer token credentials (optional)
        db: Database session
        
    Returns:
        Current authenticated User or None
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    
    # Verify token
    payload = verify_access_token(token)
    
    if payload is None:
        return None
    
    user_id: str = payload.get("sub")
    
    if user_id is None:
        return None
    
    # Get user from database
    user = await get_user_by_id(db, user_id)
    
    if user is None or not user.is_active:
        return None
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to ensure user is active.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current active User
        
    Raises:
        HTTPException: 403 if user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user
