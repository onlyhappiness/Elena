"""Supabase client and database operations."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from supabase import create_client, Client

from app.config import get_settings


class SupabaseClient:
    """Async-compatible Supabase client wrapper."""

    _instance: Client | None = None

    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client singleton."""
        if cls._instance is None:
            settings = get_settings()
            cls._instance = create_client(
                settings.supabase_url,
                settings.supabase_service_key or settings.supabase_anon_key,
            )
        return cls._instance


class UserRepository:
    """User database operations."""

    def __init__(self):
        self.client = SupabaseClient.get_client()
        self.table = self.client.table("users")

    async def get_or_create(self, external_id: str, nickname: str | None = None) -> dict:
        """Get existing user or create new one."""
        # Try to find existing user
        result = self.table.select("*").eq("external_id", external_id).execute()

        if result.data:
            return result.data[0]

        # Create new user
        new_user = {
            "external_id": external_id,
            "nickname": nickname,
        }
        result = self.table.insert(new_user).execute()
        return result.data[0]


class ConversationRepository:
    """Conversation database operations."""

    def __init__(self):
        self.client = SupabaseClient.get_client()
        self.table = self.client.table("conversations")

    async def create(self, user_id: UUID) -> dict:
        """Create a new conversation."""
        new_conversation = {
            "user_id": str(user_id),
            "is_active": True,
        }
        result = self.table.insert(new_conversation).execute()
        return result.data[0]

    async def get(self, conversation_id: UUID) -> dict | None:
        """Get conversation by ID."""
        result = self.table.select("*").eq("id", str(conversation_id)).execute()
        return result.data[0] if result.data else None

    async def get_active_for_user(self, user_id: UUID) -> dict | None:
        """Get the most recent active conversation for a user."""
        result = (
            self.table.select("*")
            .eq("user_id", str(user_id))
            .eq("is_active", True)
            .order("last_message_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None


class MessageRepository:
    """Message database operations."""

    def __init__(self):
        self.client = SupabaseClient.get_client()
        self.table = self.client.table("messages")

    async def create(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        emotion: str | None = None,
        image_url: str | None = None,
    ) -> dict:
        """Create a new message."""
        new_message = {
            "conversation_id": str(conversation_id),
            "role": role,
            "content": content,
            "emotion": emotion,
            "image_url": image_url,
        }
        result = self.table.insert(new_message).execute()
        return result.data[0]

    async def get_recent(
        self, conversation_id: UUID, limit: int = 20
    ) -> list[dict]:
        """Get recent messages for a conversation."""
        result = (
            self.table.select("*")
            .eq("conversation_id", str(conversation_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        # Reverse to get chronological order
        return list(reversed(result.data)) if result.data else []


class MemoryRepository:
    """Memory (vector) database operations."""

    def __init__(self):
        self.client = SupabaseClient.get_client()
        self.table = self.client.table("memories")

    async def create(
        self,
        user_id: UUID,
        content: str,
        embedding: list[float],
        memory_type: str = "conversation",
        summary: str | None = None,
        importance: float = 0.5,
        source_message_id: UUID | None = None,
    ) -> dict:
        """Create a new memory with embedding."""
        new_memory = {
            "user_id": str(user_id),
            "content": content,
            "embedding": embedding,
            "memory_type": memory_type,
            "summary": summary,
            "importance": importance,
            "source_message_id": str(source_message_id) if source_message_id else None,
        }
        result = self.table.insert(new_memory).execute()
        return result.data[0]

    async def search_similar(
        self,
        user_id: UUID,
        query_embedding: list[float],
        threshold: float = 0.7,
        limit: int = 5,
    ) -> list[dict]:
        """Search for similar memories using vector similarity."""
        # Use the RPC function defined in schema.sql
        result = self.client.rpc(
            "search_memories",
            {
                "query_embedding": query_embedding,
                "target_user_id": str(user_id),
                "match_threshold": threshold,
                "match_count": limit,
            },
        ).execute()
        return result.data if result.data else []


# Convenience instances
user_repo = UserRepository()
conversation_repo = ConversationRepository()
message_repo = MessageRepository()
memory_repo = MemoryRepository()
