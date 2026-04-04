"""Tests for memory service — graceful degradation and duplicate prevention."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from app.services.memory import MemoryService

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
FAKE_EMBEDDING = [0.1] * 1536
EXTRACTED_MEMORY_JSON = (
    '[{"content": "커피를 좋아함", "summary": "커피 선호",'
    ' "memory_type": "preference", "importance": 0.8}]'
)


@pytest.fixture
def memory_service():
    """MemoryService with LLM and embedding service mocked out."""
    with (
        patch("app.services.memory.ChatOpenAI"),
        patch("app.services.memory.get_embedding_service"),
    ):
        service = MemoryService()
    service.llm = MagicMock()
    service.embedding_service = MagicMock()
    return service


# ---------------------------------------------------------------------------
# extract_memories
# ---------------------------------------------------------------------------

class TestExtractMemories:
    async def test_returns_empty_list_on_llm_failure(self, memory_service):
        memory_service.llm.ainvoke = AsyncMock(side_effect=Exception("LLM 오류"))
        result = await memory_service.extract_memories("대화 내용")
        assert result == []

    async def test_returns_empty_list_on_json_parse_error(self, memory_service):
        memory_service.llm.ainvoke = AsyncMock(
            return_value=MagicMock(content="이건 JSON이 아니야")
        )
        result = await memory_service.extract_memories("대화 내용")
        assert result == []

    async def test_returns_parsed_memories_on_success(self, memory_service):
        memory_service.llm.ainvoke = AsyncMock(
            return_value=MagicMock(content=EXTRACTED_MEMORY_JSON)
        )
        result = await memory_service.extract_memories("대화 내용")
        assert len(result) == 1
        assert result[0]["content"] == "커피를 좋아함"


# ---------------------------------------------------------------------------
# search_relevant_memories — graceful degradation (TD-001)
# ---------------------------------------------------------------------------

class TestSearchRelevantMemories:
    async def test_returns_empty_list_on_embedding_failure(self, memory_service):
        memory_service.embedding_service.embed_text = AsyncMock(
            side_effect=Exception("OpenAI 연결 실패")
        )
        result = await memory_service.search_relevant_memories(
            user_id=USER_ID, query="테스트 쿼리"
        )
        assert result == []

    async def test_returns_empty_list_on_db_failure(self, memory_service):
        memory_service.embedding_service.embed_text = AsyncMock(
            return_value=FAKE_EMBEDDING
        )
        with patch("app.services.memory.memory_repo") as mock_repo:
            mock_repo.search_similar = AsyncMock(side_effect=Exception("DB 오류"))
            result = await memory_service.search_relevant_memories(
                user_id=USER_ID, query="테스트 쿼리"
            )
        assert result == []

    async def test_returns_memories_on_success(self, memory_service):
        memory_service.embedding_service.embed_text = AsyncMock(
            return_value=FAKE_EMBEDDING
        )
        expected = [{"id": "mem-1", "content": "커피 좋아함"}]
        with patch("app.services.memory.memory_repo") as mock_repo:
            mock_repo.search_similar = AsyncMock(return_value=expected)
            result = await memory_service.search_relevant_memories(
                user_id=USER_ID, query="커피"
            )
        assert result == expected


# ---------------------------------------------------------------------------
# process_and_store_memories — duplicate prevention (TD-004)
# ---------------------------------------------------------------------------

class TestDuplicateMemoryPrevention:
    async def test_skips_storing_when_duplicate_found(self, memory_service):
        memory_service.llm.ainvoke = AsyncMock(
            return_value=MagicMock(content=EXTRACTED_MEMORY_JSON)
        )
        memory_service.embedding_service.embed_text = AsyncMock(
            return_value=FAKE_EMBEDDING
        )
        with patch("app.services.memory.memory_repo") as mock_repo:
            mock_repo.search_similar = AsyncMock(
                return_value=[{"id": "existing-id"}]  # 중복 존재
            )
            mock_repo.create = AsyncMock()

            result = await memory_service.process_and_store_memories(
                user_id=USER_ID,
                user_message="커피 좋아해",
                assistant_message="나도 좋아해!",
            )

        mock_repo.create.assert_not_called()
        assert result == []

    async def test_stores_memory_when_no_duplicate(self, memory_service):
        memory_service.llm.ainvoke = AsyncMock(
            return_value=MagicMock(content=EXTRACTED_MEMORY_JSON)
        )
        memory_service.embedding_service.embed_text = AsyncMock(
            return_value=FAKE_EMBEDDING
        )
        with patch("app.services.memory.memory_repo") as mock_repo:
            mock_repo.search_similar = AsyncMock(return_value=[])  # 중복 없음
            mock_repo.create = AsyncMock(return_value={"id": "new-id"})

            result = await memory_service.process_and_store_memories(
                user_id=USER_ID,
                user_message="커피 좋아해",
                assistant_message="나도 좋아해!",
            )

        mock_repo.create.assert_called_once()
        assert len(result) == 1

    async def test_skips_low_importance_memory(self, memory_service):
        low_importance_json = (
            '[{"content": "오늘 날씨 맑음", "summary": "날씨 언급",'
            ' "memory_type": "fact", "importance": 0.2}]'
        )
        memory_service.llm.ainvoke = AsyncMock(
            return_value=MagicMock(content=low_importance_json)
        )
        with patch("app.services.memory.memory_repo") as mock_repo:
            mock_repo.create = AsyncMock()

            result = await memory_service.process_and_store_memories(
                user_id=USER_ID,
                user_message="오늘 날씨 좋다",
                assistant_message="그러게!",
            )

        mock_repo.create.assert_not_called()
        assert result == []
