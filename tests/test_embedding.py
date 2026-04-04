"""Tests for embedding service — timeout and retry logic."""

import pytest
import openai
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.embedding import EmbeddingService

FAKE_EMBEDDING = [0.1] * 1536


def _make_embed_response(embedding: list[float]) -> MagicMock:
    """Helper: build a mock embeddings.create response."""
    item = MagicMock()
    item.embedding = embedding
    item.index = 0
    response = MagicMock()
    response.data = [item]
    return response


@pytest.fixture
def embedding_service():
    """EmbeddingService with a mocked AsyncOpenAI client."""
    with patch("app.services.embedding.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = "test-key"
        service = EmbeddingService()
    return service


# ---------------------------------------------------------------------------
# embed_text — retry on network / timeout errors
# ---------------------------------------------------------------------------

class TestEmbedTextRetry:
    async def test_retries_once_on_connection_error(self, embedding_service):
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=[
                openai.APIConnectionError(request=MagicMock()),
                _make_embed_response(FAKE_EMBEDDING),
            ]
        )
        result = await embedding_service.embed_text("테스트")
        assert result == FAKE_EMBEDDING
        assert embedding_service.client.embeddings.create.call_count == 2

    async def test_retries_once_on_timeout_error(self, embedding_service):
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=[
                openai.APITimeoutError(request=MagicMock()),
                _make_embed_response(FAKE_EMBEDDING),
            ]
        )
        result = await embedding_service.embed_text("테스트")
        assert result == FAKE_EMBEDDING
        assert embedding_service.client.embeddings.create.call_count == 2

    async def test_raises_after_two_consecutive_failures(self, embedding_service):
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=openai.APIConnectionError(request=MagicMock())
        )
        with pytest.raises(openai.APIConnectionError):
            await embedding_service.embed_text("테스트")
        assert embedding_service.client.embeddings.create.call_count == 2

    async def test_no_retry_on_non_network_error(self, embedding_service):
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=ValueError("예상치 못한 오류")
        )
        with pytest.raises(ValueError):
            await embedding_service.embed_text("테스트")
        assert embedding_service.client.embeddings.create.call_count == 1

    async def test_success_on_first_try(self, embedding_service):
        embedding_service.client.embeddings.create = AsyncMock(
            return_value=_make_embed_response(FAKE_EMBEDDING)
        )
        result = await embedding_service.embed_text("테스트")
        assert result == FAKE_EMBEDDING
        assert embedding_service.client.embeddings.create.call_count == 1


# ---------------------------------------------------------------------------
# embed_texts — batch retry
# ---------------------------------------------------------------------------

class TestEmbedTextsRetry:
    async def test_returns_empty_list_for_empty_input(self, embedding_service):
        result = await embedding_service.embed_texts([])
        assert result == []

    async def test_retries_once_on_connection_error(self, embedding_service):
        item0 = MagicMock(embedding=FAKE_EMBEDDING, index=0)
        item1 = MagicMock(embedding=FAKE_EMBEDDING, index=1)
        response = MagicMock(data=[item0, item1])

        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=[
                openai.APIConnectionError(request=MagicMock()),
                response,
            ]
        )
        result = await embedding_service.embed_texts(["텍스트1", "텍스트2"])
        assert len(result) == 2
        assert embedding_service.client.embeddings.create.call_count == 2
