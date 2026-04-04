"""Conversation persistence service for Elena."""

import logging
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.db.postgres import (
    conversation_repo,
    message_repo,
    user_repo,
)

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversation persistence."""

    async def get_or_create_user(self, external_id: str) -> dict:
        """Get existing user or create a new one."""
        user = await user_repo.get_or_create(external_id)
        logger.debug(f"[User] id={user['id']} external_id={external_id}")
        return user

    async def get_or_create_conversation(
        self, user_id: UUID, session_id: str | None = None
    ) -> dict:
        """Get existing conversation by session_id or create a new one.

        Args:
            user_id: The internal user UUID.
            session_id: Optional existing conversation ID.

        Returns:
            Conversation dict with 'id' and other fields.
        """
        if session_id:
            conversation = await conversation_repo.get(UUID(session_id))
            if conversation:
                logger.debug(f"[Conversation] 기존 세션 재사용: {session_id}")
                return conversation

        conversation = await conversation_repo.create(user_id)
        logger.info(f"[Conversation] 새 세션 생성: {conversation['id']}")
        return conversation

    async def load_recent_messages(
        self, conversation_id: UUID, limit: int = 20
    ) -> list[BaseMessage]:
        """Load recent messages from DB and convert to LangChain format.

        Args:
            conversation_id: The conversation UUID.
            limit: Maximum number of messages to load.

        Returns:
            List of LangChain BaseMessage objects.
        """
        db_messages = await message_repo.get_recent(conversation_id, limit)

        messages: list[BaseMessage] = []
        for msg in db_messages:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
            # Skip system messages for now

        return messages

    async def save_user_message(
        self, conversation_id: UUID, content: str
    ) -> dict:
        """Save a user message to the database.

        Args:
            conversation_id: The conversation UUID.
            content: The message content.

        Returns:
            The created message dict.
        """
        return await message_repo.create(
            conversation_id=conversation_id,
            role="user",
            content=content,
        )

    async def save_assistant_message(
        self,
        conversation_id: UUID,
        content: str,
        emotion: str | None = None,
        image_url: str | None = None,
    ) -> dict:
        """Save an assistant (Elena) message to the database.

        Args:
            conversation_id: The conversation UUID.
            content: The message content.
            emotion: Elena's emotional state.
            image_url: Generated image URL if any.

        Returns:
            The created message dict.
        """
        return await message_repo.create(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            emotion=emotion,
            image_url=image_url,
        )

    async def get_conversation_history(
        self, conversation_id: UUID
    ) -> list[dict]:
        """Get conversation history in simple dict format.

        Args:
            conversation_id: The conversation UUID.

        Returns:
            List of message dicts with role and content.
        """
        db_messages = await message_repo.get_recent(conversation_id, limit=100)
        return [
            {
                "role": msg["role"],
                "content": msg["content"],
                "emotion": msg.get("emotion"),
                "image_url": msg.get("image_url"),
                "created_at": msg.get("created_at"),
            }
            for msg in db_messages
        ]


# Singleton instance
conversation_service = ConversationService()
