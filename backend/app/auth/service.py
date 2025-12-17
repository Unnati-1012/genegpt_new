# backend/app/auth/service.py
"""
Authentication service layer for Noviq.AI.

Contains business logic for user authentication and management.
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, ChatHistory, UserProject, PinnedThread
from .schemas import (
    UserCreate, 
    UserUpdate, 
    ChatHistoryCreate, 
    ChatHistoryUpdate,
    ProjectCreate,
    ProjectUpdate,
    PinnedThreadCreate
)
from .utils import hash_password, verify_password


# =============================================================================
# USER SERVICE
# =============================================================================
async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    """
    Create a new user with hashed password.
    
    Args:
        db: Database session
        user_data: User creation data
        
    Returns:
        Created User object
        
    Raises:
        ValueError: If email already exists
    """
    # Check if email already exists
    existing = await get_user_by_email(db, user_data.email)
    if existing:
        raise ValueError("Email already registered")
    
    # Create user with hashed password
    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        preferences={}
    )
    
    db.add(user)
    await db.flush()
    await db.refresh(user)
    
    return user


async def authenticate_user(
    db: AsyncSession, 
    email: str, 
    password: str
) -> Optional[User]:
    """
    Authenticate a user by email and password.
    
    Args:
        db: Database session
        email: User's email
        password: Plain text password
        
    Returns:
        User object if authentication successful, None otherwise
    """
    user = await get_user_by_email(db, email)
    
    if not user:
        return None
    
    if not user.is_active:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """
    Get a user by their ID.
    
    Args:
        db: Database session
        user_id: User's UUID
        
    Returns:
        User object or None
    """
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    Get a user by their email.
    
    Args:
        db: Database session
        email: User's email address
        
    Returns:
        User object or None
    """
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def update_user(
    db: AsyncSession, 
    user_id: str, 
    user_data: UserUpdate
) -> Optional[User]:
    """
    Update user profile.
    
    Args:
        db: Database session
        user_id: User's UUID
        user_data: Update data
        
    Returns:
        Updated User object or None
    """
    user = await get_user_by_id(db, user_id)
    
    if not user:
        return None
    
    update_dict = user_data.model_dump(exclude_unset=True)
    
    for key, value in update_dict.items():
        setattr(user, key, value)
    
    await db.flush()
    await db.refresh(user)
    
    return user


async def update_user_password(
    db: AsyncSession,
    user_id: str,
    current_password: str,
    new_password: str
) -> bool:
    """
    Update user's password.
    
    Args:
        db: Database session
        user_id: User's UUID
        current_password: Current password for verification
        new_password: New password to set
        
    Returns:
        True if password updated, False otherwise
    """
    user = await get_user_by_id(db, user_id)
    
    if not user:
        return False
    
    if not verify_password(current_password, user.hashed_password):
        return False
    
    user.hashed_password = hash_password(new_password)
    await db.flush()
    
    return True


async def delete_user(db: AsyncSession, user_id: str) -> bool:
    """
    Delete a user and all associated data.
    
    Args:
        db: Database session
        user_id: User's UUID
        
    Returns:
        True if deleted, False if user not found
    """
    user = await get_user_by_id(db, user_id)
    
    if not user:
        return False
    
    await db.delete(user)
    await db.flush()
    
    return True


# =============================================================================
# CHAT HISTORY SERVICE
# =============================================================================
async def create_chat(
    db: AsyncSession, 
    user_id: str, 
    chat_data: ChatHistoryCreate
) -> ChatHistory:
    """
    Create a new chat for a user.
    
    Args:
        db: Database session
        user_id: User's UUID
        chat_data: Chat creation data
        
    Returns:
        Created ChatHistory object
    """
    # Convert messages to dict format
    messages = [msg.model_dump() for msg in chat_data.messages]
    
    chat = ChatHistory(
        user_id=user_id,
        title=chat_data.title or "New Chat",
        messages=messages
    )
    
    db.add(chat)
    await db.flush()
    await db.refresh(chat)
    
    return chat


async def get_chat_by_id(
    db: AsyncSession, 
    chat_id: str, 
    user_id: str
) -> Optional[ChatHistory]:
    """
    Get a chat by ID (ensures user ownership).
    
    Args:
        db: Database session
        chat_id: Chat's UUID
        user_id: User's UUID (for ownership check)
        
    Returns:
        ChatHistory object or None
    """
    result = await db.execute(
        select(ChatHistory).where(
            ChatHistory.id == chat_id,
            ChatHistory.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def get_user_chats(
    db: AsyncSession, 
    user_id: str,
    limit: int = 50,
    offset: int = 0
) -> List[ChatHistory]:
    """
    Get all chats for a user.
    
    Args:
        db: Database session
        user_id: User's UUID
        limit: Maximum number of chats to return
        offset: Number of chats to skip
        
    Returns:
        List of ChatHistory objects
    """
    result = await db.execute(
        select(ChatHistory)
        .where(ChatHistory.user_id == user_id)
        .order_by(ChatHistory.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def update_chat(
    db: AsyncSession,
    chat_id: str,
    user_id: str,
    chat_data: ChatHistoryUpdate
) -> Optional[ChatHistory]:
    """
    Update a chat.
    
    Args:
        db: Database session
        chat_id: Chat's UUID
        user_id: User's UUID
        chat_data: Update data
        
    Returns:
        Updated ChatHistory object or None
    """
    chat = await get_chat_by_id(db, chat_id, user_id)
    
    if not chat:
        return None
    
    if chat_data.title is not None:
        chat.title = chat_data.title
    
    if chat_data.messages is not None:
        chat.messages = [msg.model_dump() for msg in chat_data.messages]
    
    chat.updated_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(chat)
    
    return chat


async def add_message_to_chat(
    db: AsyncSession,
    chat_id: str,
    user_id: str,
    role: str,
    content: str
) -> Optional[ChatHistory]:
    """
    Add a message to an existing chat.
    
    Args:
        db: Database session
        chat_id: Chat's UUID
        user_id: User's UUID
        role: Message role ('user' or 'assistant')
        content: Message content
        
    Returns:
        Updated ChatHistory object or None
    """
    chat = await get_chat_by_id(db, chat_id, user_id)
    
    if not chat:
        return None
    
    # Add new message
    messages = list(chat.messages) if chat.messages else []
    messages.append({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    chat.messages = messages
    chat.updated_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(chat)
    
    return chat


async def delete_chat(
    db: AsyncSession, 
    chat_id: str, 
    user_id: str
) -> bool:
    """
    Delete a chat.
    
    Args:
        db: Database session
        chat_id: Chat's UUID
        user_id: User's UUID
        
    Returns:
        True if deleted, False if not found
    """
    chat = await get_chat_by_id(db, chat_id, user_id)
    
    if not chat:
        return False
    
    await db.delete(chat)
    await db.flush()
    
    return True


async def delete_all_user_chats(db: AsyncSession, user_id: str) -> int:
    """
    Delete all chats for a user.
    
    Args:
        db: Database session
        user_id: User's UUID
        
    Returns:
        Number of chats deleted
    """
    result = await db.execute(
        delete(ChatHistory).where(ChatHistory.user_id == user_id)
    )
    await db.flush()
    
    return result.rowcount


# =============================================================================
# PROJECT SERVICE
# =============================================================================
async def create_project(
    db: AsyncSession,
    user_id: str,
    project_data: ProjectCreate
) -> UserProject:
    """
    Create a new project for a user.
    
    Args:
        db: Database session
        user_id: User's UUID
        project_data: Project creation data
        
    Returns:
        Created UserProject object
    """
    project = UserProject(
        user_id=user_id,
        name=project_data.name,
        description=project_data.description or "",
        data=project_data.data or {}
    )
    
    db.add(project)
    await db.flush()
    await db.refresh(project)
    
    return project


async def get_user_projects(
    db: AsyncSession,
    user_id: str
) -> List[UserProject]:
    """
    Get all projects for a user.
    
    Args:
        db: Database session
        user_id: User's UUID
        
    Returns:
        List of UserProject objects
    """
    result = await db.execute(
        select(UserProject)
        .where(UserProject.user_id == user_id)
        .order_by(UserProject.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_project_by_id(
    db: AsyncSession,
    project_id: str,
    user_id: str
) -> Optional[UserProject]:
    """
    Get a project by ID (ensures user ownership).
    """
    result = await db.execute(
        select(UserProject).where(
            UserProject.id == project_id,
            UserProject.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def update_project(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    project_data: ProjectUpdate
) -> Optional[UserProject]:
    """
    Update a project.
    """
    project = await get_project_by_id(db, project_id, user_id)
    
    if not project:
        return None
    
    update_dict = project_data.model_dump(exclude_unset=True)
    
    for key, value in update_dict.items():
        setattr(project, key, value)
    
    project.updated_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(project)
    
    return project


async def delete_project(
    db: AsyncSession,
    project_id: str,
    user_id: str
) -> bool:
    """
    Delete a project.
    """
    project = await get_project_by_id(db, project_id, user_id)
    
    if not project:
        return False
    
    await db.delete(project)
    await db.flush()
    
    return True


# =============================================================================
# PINNED THREADS SERVICE
# =============================================================================
async def pin_thread(
    db: AsyncSession,
    user_id: str,
    pin_data: PinnedThreadCreate
) -> Optional[PinnedThread]:
    """
    Pin a chat thread.
    
    Args:
        db: Database session
        user_id: User's UUID
        pin_data: Pin creation data
        
    Returns:
        Created PinnedThread object or None if chat doesn't exist
    """
    # Verify chat exists and belongs to user
    chat = await get_chat_by_id(db, pin_data.chat_id, user_id)
    if not chat:
        return None
    
    # Check if already pinned
    existing = await db.execute(
        select(PinnedThread).where(
            PinnedThread.user_id == user_id,
            PinnedThread.chat_id == pin_data.chat_id
        )
    )
    if existing.scalar_one_or_none():
        return None  # Already pinned
    
    pin = PinnedThread(
        user_id=user_id,
        chat_id=pin_data.chat_id,
        note=pin_data.note or ""
    )
    
    db.add(pin)
    await db.flush()
    await db.refresh(pin)
    
    return pin


async def get_user_pinned_threads(
    db: AsyncSession,
    user_id: str
) -> List[PinnedThread]:
    """
    Get all pinned threads for a user.
    """
    result = await db.execute(
        select(PinnedThread)
        .where(PinnedThread.user_id == user_id)
        .order_by(PinnedThread.pinned_at.desc())
    )
    return list(result.scalars().all())


async def unpin_thread(
    db: AsyncSession,
    pin_id: str,
    user_id: str
) -> bool:
    """
    Unpin a chat thread.
    """
    result = await db.execute(
        select(PinnedThread).where(
            PinnedThread.id == pin_id,
            PinnedThread.user_id == user_id
        )
    )
    pin = result.scalar_one_or_none()
    
    if not pin:
        return False
    
    await db.delete(pin)
    await db.flush()
    
    return True
