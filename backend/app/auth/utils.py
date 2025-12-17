# backend/app/auth/utils.py
"""
Authentication utility functions for Noviq.AI.

Provides password hashing, JWT token creation/validation, and helper functions.
"""

from datetime import datetime, timedelta
from typing import Optional, Any
from jose import jwt, JWTError
from passlib.context import CryptContext

from ..config import settings


# =============================================================================
# PASSWORD HASHING
# =============================================================================
# Using argon2 for password hashing - no length limits and more secure than bcrypt
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plain text password using Argon2.
    
    Args:
        password: Plain text password of any length
        
    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


# =============================================================================
# JWT TOKEN FUNCTIONS
# =============================================================================
def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string to decode
        
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def verify_access_token(token: str) -> Optional[dict]:
    """
    Verify an access token and return its payload.
    
    Args:
        token: JWT access token to verify
        
    Returns:
        Token payload if valid access token, None otherwise
    """
    payload = decode_token(token)
    
    if payload is None:
        return None
    
    # Check token type
    if payload.get("type") != "access":
        return None
    
    return payload


def verify_refresh_token(token: str) -> Optional[dict]:
    """
    Verify a refresh token and return its payload.
    
    Args:
        token: JWT refresh token to verify
        
    Returns:
        Token payload if valid refresh token, None otherwise
    """
    payload = decode_token(token)
    
    if payload is None:
        return None
    
    # Check token type
    if payload.get("type") != "refresh":
        return None
    
    return payload


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def extract_user_id_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        User ID if token is valid, None otherwise
    """
    payload = verify_access_token(token)
    
    if payload is None:
        return None
    
    return payload.get("sub")
