"""Chat-related Pydantic schemas."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class Role(str, Enum):
    """Message role enum."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Single message in conversation."""
    role: Role
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""
    user_id: str = Field(..., description="Unique user identifier")
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    session_id: str | None = Field(None, description="Optional session ID for conversation continuity")


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""
    message: str = Field(..., description="윤슬's response")
    session_id: str = Field(..., description="Session ID for this conversation")
    image_url: str | None = Field(None, description="Generated selfie URL if applicable")
    emotion: str | None = Field(None, description="Current emotional state of 윤슬")
