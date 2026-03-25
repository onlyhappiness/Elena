"""LangGraph State definitions for Elena conversation flow."""

from typing import Annotated, TypedDict
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ElenaState(TypedDict):
    """State for Elena conversation graph.

    Attributes:
        messages: Conversation history with automatic message merging
        user_id: Current user's ID
        session_id: Current conversation session ID
        memories: Retrieved relevant memories from past conversations
        current_emotion: Elena's current emotional state
        selfie_context: Context from [SELFIE: ...] tag if Elena wants to send a photo
        should_generate_image: Whether to generate a selfie
        image_prompt: Prompt for image generation if needed
        image_url: Generated image URL
    """
    # Core conversation
    messages: Annotated[list[BaseMessage], add_messages]

    # User context
    user_id: str
    session_id: str

    # Memory & RAG (dict with 'content' and optional 'feeling' keys)
    memories: list[dict]

    # Emotional state
    current_emotion: str

    # Image generation
    selfie_context: str | None  # From [SELFIE: ...] tag
    should_generate_image: bool
    image_prompt: str | None
    image_url: str | None


def create_initial_state(
    user_id: str,
    session_id: str,
) -> ElenaState:
    """Create initial state for a new conversation."""
    return ElenaState(
        messages=[],
        user_id=user_id,
        session_id=session_id,
        memories=[],
        current_emotion="calm",
        selfie_context=None,
        should_generate_image=False,
        image_prompt=None,
        image_url=None,
    )
