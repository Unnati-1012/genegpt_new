# backend/app/auth/routes.py
"""
Authentication routes for Noviq.AI.

Provides endpoints for user registration, login, logout, and profile management.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from .database import get_db
from .models import User
from .schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    PasswordChange,
    TokenResponse,
    TokenRefresh,
    ChatHistoryCreate,
    ChatHistoryUpdate,
    ChatHistoryResponse,
    ChatHistoryListResponse,
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    PinnedThreadCreate,
    PinnedThreadResponse
)
from .service import (
    create_user,
    authenticate_user,
    get_user_by_id,
    update_user,
    update_user_password,
    delete_user,
    create_chat,
    get_chat_by_id,
    get_user_chats,
    update_chat,
    add_message_to_chat,
    delete_chat,
    delete_all_user_chats,
    create_project,
    get_user_projects,
    get_project_by_id,
    update_project,
    delete_project,
    pin_thread,
    get_user_pinned_threads,
    unpin_thread
)
from .utils import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token
)
from .dependencies import get_current_user, get_current_active_user


# =============================================================================
# ROUTER SETUP
# =============================================================================
router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    
    - **email**: User's email address (must be unique)
    - **password**: Password (min 8 chars, must contain upper, lower, digit)
    """
    try:
        user = await create_user(db, user_data)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login and receive access token.
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns JWT access token and optional refresh token.
    """
    user = await authenticate_user(db, credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    
    - **refresh_token**: Valid refresh token
    """
    payload = verify_refresh_token(token_data.refresh_token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    
    # Verify user still exists and is active
    user = await get_user_by_id(db, user_id)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout the current user.
    
    Note: For JWT-based auth, the client should discard the token.
    This endpoint is provided for session-based implementations.
    """
    # For JWT, logout is client-side (discard token)
    # For server-side token invalidation, implement a token blacklist
    return {"message": "Successfully logged out"}


# =============================================================================
# USER PROFILE ENDPOINTS
# =============================================================================
@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's profile.
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's profile.
    
    - **email**: New email (optional)
    - **preferences**: User preferences JSON (optional)
    """
    updated_user = await update_user(db, current_user.id, user_data)
    return updated_user


@router.post("/me/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change current user's password.
    
    - **current_password**: Current password for verification
    - **new_password**: New password
    """
    success = await update_user_password(
        db,
        current_user.id,
        password_data.current_password,
        password_data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    return {"message": "Password updated successfully"}


@router.delete("/me")
async def delete_me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete current user's account and all associated data.
    """
    await delete_user(db, current_user.id)
    return {"message": "Account deleted successfully"}


# =============================================================================
# CHAT HISTORY ENDPOINTS
# =============================================================================
@router.get("/chats", response_model=List[ChatHistoryListResponse])
async def list_chats(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of user's chat histories.
    """
    chats = await get_user_chats(db, current_user.id, limit, offset)
    
    return [
        ChatHistoryListResponse(
            id=chat.id,
            title=chat.title,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            message_count=len(chat.messages) if chat.messages else 0
        )
        for chat in chats
    ]


@router.post("/chats", response_model=ChatHistoryResponse, status_code=status.HTTP_201_CREATED)
async def create_new_chat(
    chat_data: ChatHistoryCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new chat.
    """
    chat = await create_chat(db, current_user.id, chat_data)
    return chat


@router.get("/chats/{chat_id}", response_model=ChatHistoryResponse)
async def get_chat(
    chat_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific chat by ID.
    """
    chat = await get_chat_by_id(db, chat_id, current_user.id)
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    return chat


@router.patch("/chats/{chat_id}", response_model=ChatHistoryResponse)
async def update_existing_chat(
    chat_id: str,
    chat_data: ChatHistoryUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a chat.
    """
    chat = await update_chat(db, chat_id, current_user.id, chat_data)
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    return chat


@router.delete("/chats/{chat_id}")
async def delete_existing_chat(
    chat_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a chat.
    """
    success = await delete_chat(db, chat_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    return {"message": "Chat deleted successfully"}


@router.delete("/chats")
async def delete_all_chats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete all chats for the current user.
    """
    count = await delete_all_user_chats(db, current_user.id)
    return {"message": f"Deleted {count} chats"}


# =============================================================================
# PROJECT ENDPOINTS
# =============================================================================
@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of user's projects.
    """
    projects = await get_user_projects(db, current_user.id)
    return projects


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_new_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new project.
    """
    project = await create_project(db, current_user.id, project_data)
    return project


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific project by ID.
    """
    project = await get_project_by_id(db, project_id, current_user.id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_existing_project(
    project_id: str,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a project.
    """
    project = await update_project(db, project_id, current_user.id, project_data)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


@router.delete("/projects/{project_id}")
async def delete_existing_project(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a project.
    """
    success = await delete_project(db, project_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return {"message": "Project deleted successfully"}


# =============================================================================
# PINNED THREADS ENDPOINTS
# =============================================================================
@router.get("/pinned", response_model=List[PinnedThreadResponse])
async def list_pinned_threads(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of user's pinned threads.
    """
    pins = await get_user_pinned_threads(db, current_user.id)
    return pins


@router.post("/pinned", response_model=PinnedThreadResponse, status_code=status.HTTP_201_CREATED)
async def pin_chat(
    pin_data: PinnedThreadCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Pin a chat thread.
    """
    pin = await pin_thread(db, current_user.id, pin_data)
    
    if not pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat not found or already pinned"
        )
    
    return pin


@router.delete("/pinned/{pin_id}")
async def unpin_chat(
    pin_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Unpin a chat thread.
    """
    success = await unpin_thread(db, pin_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pinned thread not found"
        )
    
    return {"message": "Thread unpinned successfully"}
