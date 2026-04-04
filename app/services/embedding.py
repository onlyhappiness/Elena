"""Embedding service for text vectorization using OpenAI."""

import logging
from functools import lru_cache

import openai
from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

# Default embedding model and dimensions
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingService:
    """Service for generating text embeddings using OpenAI API."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=10.0)
        self.model = EMBEDDING_MODEL
        self.dimensions = EMBEDDING_DIMENSIONS

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        for attempt in range(2):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=text,
                    dimensions=self.dimensions,
                )
                return response.data[0].embedding
            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                if attempt == 0:
                    logger.warning(f"임베딩 호출 실패 (시도 1/2), 재시도 중: {e}")
                    continue
                logger.error(f"임베딩 호출 최종 실패: {e}")
                raise
            except Exception as e:
                logger.error(f"임베딩 호출 실패 (재시도 불가): {e}")
                raise

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in a single API call.

        Args:
            texts: List of texts to embed.

        Returns:
            A list of embedding vectors.
        """
        if not texts:
            return []

        for attempt in range(2):
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                    dimensions=self.dimensions,
                )
                sorted_data = sorted(response.data, key=lambda x: x.index)
                return [item.embedding for item in sorted_data]
            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                if attempt == 0:
                    logger.warning(f"임베딩(batch) 호출 실패 (시도 1/2), 재시도 중: {e}")
                    continue
                logger.error(f"임베딩(batch) 호출 최종 실패: {e}")
                raise
            except Exception as e:
                logger.error(f"임베딩(batch) 호출 실패 (재시도 불가): {e}")
                raise


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Get cached embedding service instance."""
    return EmbeddingService()
