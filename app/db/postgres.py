"""PostgreSQL client and database operations using asyncpg."""

import logging
from uuid import UUID

import asyncpg

from app.config import get_settings

logger = logging.getLogger(__name__)


def _to_dict(record: asyncpg.Record | None) -> dict:
    """asyncpg Record → dict 변환. UUID는 문자열로 직렬화."""
    if record is None:
        return {}
    result = {}
    for key, value in record.items():
        result[key] = str(value) if isinstance(value, UUID) else value
    return result


def _vec(embedding: list[float]) -> str:
    """임베딩 리스트를 PostgreSQL vector 리터럴 문자열로 변환."""
    return "[" + ",".join(map(str, embedding)) + "]"


class PostgresPool:
    """asyncpg 커넥션 풀 관리."""

    _pool: asyncpg.Pool | None = None

    @classmethod
    async def init(cls) -> None:
        """앱 시작 시 커넥션 풀 초기화."""
        settings = get_settings()
        cls._pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=10,
        )
        logger.info("PostgreSQL 커넥션 풀 초기화 완료")

    @classmethod
    async def close(cls) -> None:
        """앱 종료 시 커넥션 풀 정리."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("PostgreSQL 커넥션 풀 종료")

    @classmethod
    def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            raise RuntimeError("PostgreSQL 풀이 초기화되지 않았습니다. lifespan을 확인하세요.")
        return cls._pool


class UserRepository:
    """사용자 DB 작업."""

    async def get_by_external_id(self, external_id: str) -> dict | None:
        pool = PostgresPool.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE external_id = $1",
                external_id,
            )
            return _to_dict(row) if row else None

    async def get_or_create(self, external_id: str, nickname: str | None = None) -> dict:
        pool = PostgresPool.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE external_id = $1",
                external_id,
            )
            if row:
                return _to_dict(row)
            row = await conn.fetchrow(
                "INSERT INTO users (external_id, nickname) VALUES ($1, $2) RETURNING *",
                external_id,
                nickname,
            )
            return _to_dict(row)


class ConversationRepository:
    """대화 세션 DB 작업."""

    async def create(self, user_id: UUID) -> dict:
        pool = PostgresPool.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO conversations (user_id, is_active) VALUES ($1, TRUE) RETURNING *",
                user_id,
            )
            return _to_dict(row)

    async def get(self, conversation_id: UUID) -> dict | None:
        pool = PostgresPool.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM conversations WHERE id = $1",
                conversation_id,
            )
            return _to_dict(row) if row else None

    async def get_active_for_user(self, user_id: UUID) -> dict | None:
        pool = PostgresPool.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT * FROM conversations
                   WHERE user_id = $1 AND is_active = TRUE
                   ORDER BY last_message_at DESC LIMIT 1""",
                user_id,
            )
            return _to_dict(row) if row else None

    async def deactivate(self, conversation_id: UUID) -> None:
        pool = PostgresPool.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE conversations SET is_active = FALSE WHERE id = $1",
                conversation_id,
            )


class MessageRepository:
    """메시지 DB 작업."""

    async def create(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        emotion: str | None = None,
        image_url: str | None = None,
    ) -> dict:
        pool = PostgresPool.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO messages (conversation_id, role, content, emotion, image_url)
                   VALUES ($1, $2, $3, $4, $5) RETURNING *""",
                conversation_id, role, content, emotion, image_url,
            )
            return _to_dict(row)

    async def get_recent(self, conversation_id: UUID, limit: int = 20) -> list[dict]:
        pool = PostgresPool.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM messages
                   WHERE conversation_id = $1
                   ORDER BY created_at DESC LIMIT $2""",
                conversation_id, limit,
            )
        return [_to_dict(r) for r in reversed(rows)]


class MemoryRepository:
    """장기 기억 (pgvector) DB 작업."""

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
        pool = PostgresPool.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO memories
                   (user_id, content, embedding, memory_type, summary, importance, source_message_id)
                   VALUES ($1, $2, $3::vector, $4, $5, $6, $7) RETURNING *""",
                user_id, content, _vec(embedding),
                memory_type, summary, importance, source_message_id,
            )
            return _to_dict(row)

    async def search_similar(
        self,
        user_id: UUID,
        query_embedding: list[float],
        threshold: float = 0.7,
        limit: int = 5,
    ) -> list[dict]:
        pool = PostgresPool.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM search_memories($1::vector, $2, $3, $4)",
                _vec(query_embedding), user_id, threshold, limit,
            )
        return [_to_dict(r) for r in rows]


# 편의 싱글톤 인스턴스
user_repo = UserRepository()
conversation_repo = ConversationRepository()
message_repo = MessageRepository()
memory_repo = MemoryRepository()
