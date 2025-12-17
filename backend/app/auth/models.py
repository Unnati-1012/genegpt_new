# backend/app/auth/models.py
"""
SQLAlchemy database models for Noviq.AI authentication and user data.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, 
    String, 
    DateTime, 
    Text, 
    ForeignKey, 
    Boolean,
    JSON,
    Index
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


# =============================================================================
# USER MODEL
# =============================================================================
class User(Base):
    """
    User model for authentication.
    
    Attributes:
        id: Unique UUID identifier
        email: User's email (unique)
        hashed_password: Bcrypt hashed password
        created_at: Account creation timestamp
        is_active: Whether the user account is active
        preferences: JSON field for user personalization settings
    """
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    preferences = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    chat_histories = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("UserProject", back_populates="user", cascade="all, delete-orphan")
    pinned_threads = relationship("PinnedThread", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


# =============================================================================
# CHAT HISTORY MODEL
# =============================================================================
class ChatHistory(Base):
    """
    Stores chat conversations per user.
    
    Attributes:
        id: Unique UUID identifier
        user_id: Foreign key to User
        title: Chat title (auto-generated or user-defined)
        messages: JSON array of message objects
        created_at: Chat creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "chat_histories"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), default="New Chat", nullable=False)
    messages = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="chat_histories")
    
    # Indexes
    __table_args__ = (
        Index("ix_chat_histories_user_id", "user_id"),
        Index("ix_chat_histories_updated_at", "updated_at"),
    )
    
    def __repr__(self) -> str:
        return f"<ChatHistory(id={self.id}, title={self.title})>"


# =============================================================================
# USER PROJECT MODEL
# =============================================================================
class UserProject(Base):
    """
    Stores user projects/workflows.
    
    Attributes:
        id: Unique UUID identifier
        user_id: Foreign key to User
        name: Project name
        description: Project description
        data: JSON field for project-specific data
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "user_projects"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="", nullable=False)
    data = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="projects")
    
    # Indexes
    __table_args__ = (
        Index("ix_user_projects_user_id", "user_id"),
    )
    
    def __repr__(self) -> str:
        return f"<UserProject(id={self.id}, name={self.name})>"


# =============================================================================
# PINNED THREAD MODEL
# =============================================================================
class PinnedThread(Base):
    """
    Stores pinned/starred chat threads per user.
    
    Attributes:
        id: Unique UUID identifier
        user_id: Foreign key to User
        chat_id: Foreign key to ChatHistory
        pinned_at: When the thread was pinned
        note: Optional user note about why it's pinned
    """
    __tablename__ = "pinned_threads"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chat_id = Column(String(36), ForeignKey("chat_histories.id", ondelete="CASCADE"), nullable=False)
    pinned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    note = Column(Text, default="", nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="pinned_threads")
    chat = relationship("ChatHistory")
    
    # Indexes
    __table_args__ = (
        Index("ix_pinned_threads_user_id", "user_id"),
    )
    
    def __repr__(self) -> str:
        return f"<PinnedThread(id={self.id}, chat_id={self.chat_id})>"
