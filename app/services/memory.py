"""Memory extraction and storage service for Elena."""

import json
import logging
from uuid import UUID

# from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings
from app.db.postgres import memory_repo
from app.services.embedding import get_embedding_service

logger = logging.getLogger(__name__)

# Prompt for extracting memorable information from conversations
# Note: Double curly braces {{ }} are used to escape them from .format()
MEMORY_EXTRACTION_PROMPT = """당신은 대화에서 기억할 만한 정보를 추출하는 AI입니다.

사용자와 윤슬(AI 컴패니언)의 대화에서 나중에 기억하면 좋을 정보를 찾아주세요.

## 기억할 만한 정보 유형:
1. **사용자 정보**: 이름, 나이, 직업, 거주지 등
2. **취향/선호도**: 좋아하는 음식, 취미, 관심사 등
3. **중요한 사실**: 기념일, 반려동물, 가족 관계 등
4. **감정적 맥락**: 최근 겪은 일, 고민, 기분 등
5. **약속/계획**: 사용자와 나눈 약속이나 계획

## 응답 형식:
JSON 배열로 응답하세요. 기억할 것이 없으면 빈 배열 []을 반환하세요.

```json
[
  {{
    "content": "기억할 원본 내용",
    "summary": "요약된 기억 (한 문장)",
    "memory_type": "preference|fact|emotion|plan",
    "importance": 0.1~1.0 (중요도)
  }}
]
```

## 중요도 기준:
- 0.9~1.0: 이름, 생일 등 핵심 개인정보
- 0.7~0.8: 취향, 직업, 관심사 등
- 0.5~0.6: 일시적 감정, 단순 언급
- 0.3~0.4: 맥락적 정보

대화 내용:
{conversation}

JSON 배열만 출력하세요:"""


class MemoryService:
    """Service for extracting and storing conversation memories."""

    def __init__(self):
        settings = get_settings()
        # Claude version (commented out for testing with OpenAI)
        # self.llm = ChatAnthropic(
        #     model="claude-sonnet-4-5-20250929",
        #     api_key=settings.anthropic_api_key,
        #     max_tokens=1024,
        # )
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            max_tokens=1024,
        )
        self.embedding_service = get_embedding_service()

    async def extract_memories(self, conversation: str) -> list[dict]:
        """Extract memorable information from a conversation using LLM.

        Args:
            conversation: The conversation text to analyze.

        Returns:
            List of memory dicts with content, summary, type, and importance.
        """
        logger.info(f"[Memory] Extracting memories from conversation: {conversation[:100]}...")

        messages = [
            SystemMessage(
                content="You are a memory extraction assistant. Respond only with valid JSON."
            ),
            HumanMessage(
                content=MEMORY_EXTRACTION_PROMPT.format(conversation=conversation)
            ),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()
            logger.info(f"[Memory] LLM response: {content[:200]}...")
        except Exception as e:
            logger.error(f"[Memory] LLM call failed: {e}")
            return []

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            memories = json.loads(content)
            if not isinstance(memories, list):
                logger.warning(f"[Memory] LLM returned non-list: {type(memories)}")
                return []
            logger.info(f"[Memory] Extracted {len(memories)} memories")
            return memories
        except json.JSONDecodeError as e:
            logger.error(f"[Memory] JSON parse error: {e}, content: {content}")
            return []

    async def process_and_store_memories(
        self,
        user_id: UUID,
        user_message: str,
        assistant_message: str,
        source_message_id: UUID | None = None,
    ) -> list[dict]:
        """Process a conversation turn and store any extracted memories.

        Args:
            user_id: The user's UUID.
            user_message: The user's message.
            assistant_message: Elena's response.
            source_message_id: Optional ID of the source message.

        Returns:
            List of created memory records.
        """
        logger.info(f"[Memory] Processing memories for user {user_id}")

        # Format conversation for analysis
        conversation = f"사용자: {user_message}\n윤슬: {assistant_message}"

        # Extract memories using LLM
        extracted = await self.extract_memories(conversation)

        if not extracted:
            logger.info("[Memory] No memories extracted")
            return []

        logger.info(f"[Memory] Processing {len(extracted)} extracted memories")
        logger.info(f"[Memory] Extracted data: {extracted}")
        created_memories = []

        for i, memory in enumerate(extracted):
            logger.info(f"[Memory] Processing memory {i}: {type(memory)} - {memory}")

            # Ensure memory is a dict
            if not isinstance(memory, dict):
                logger.warning(f"[Memory] Skipping non-dict memory: {memory}")
                continue

            # Skip low importance memories
            importance = memory.get("importance", 0.5)
            if importance < 0.4:
                logger.debug(f"[Memory] Skipping low importance memory: {importance}")
                continue

            content = memory.get("content", "")
            if not content:
                logger.warning("[Memory] Skipping memory with no content")
                continue

            try:
                # Generate embedding for the memory content
                logger.info(f"[Memory] Generating embedding for: {content[:50]}...")
                embedding = await self.embedding_service.embed_text(content)

                # 중복 저장 방지: 유사도 0.95 이상인 기억이 이미 있으면 스킵
                duplicates = await memory_repo.search_similar(
                    user_id=user_id,
                    query_embedding=embedding,
                    threshold=0.95,
                    limit=1,
                )
                if duplicates:
                    logger.debug(f"[Memory] 중복 기억 감지 — 저장 스킵: {content[:50]}...")
                    continue

                # Store in database
                logger.info("[Memory] Storing memory to DB...")
                created = await memory_repo.create(
                    user_id=user_id,
                    content=content,
                    embedding=embedding,
                    memory_type=memory.get("memory_type", "conversation"),
                    summary=memory.get("summary"),
                    importance=importance,
                    source_message_id=source_message_id,
                )
                created_memories.append(created)
                logger.info(f"[Memory] Successfully stored memory: {created.get('id')}")
            except Exception as e:
                logger.error(f"[Memory] Failed to store memory: {e}")

        logger.info(f"[Memory] Total stored: {len(created_memories)} memories")
        return created_memories

    async def search_relevant_memories(
        self,
        user_id: UUID,
        query: str,
        threshold: float = 0.7,
        limit: int = 5,
    ) -> list[dict]:
        """Search for memories relevant to the query.

        Args:
            user_id: The user's UUID.
            query: The search query (user's message).
            threshold: Minimum similarity threshold.
            limit: Maximum number of results.

        Returns:
            List of relevant memories with similarity scores.
            실패 시 빈 리스트 반환 (graceful degradation).
        """
        try:
            query_embedding = await self.embedding_service.embed_text(query)
            memories = await memory_repo.search_similar(
                user_id=user_id,
                query_embedding=query_embedding,
                threshold=threshold,
                limit=limit,
            )
            return memories
        except Exception as e:
            logger.warning(f"[Memory] 기억 검색 실패 — 기억 없이 진행: {e}")
            return []


# Singleton instance
memory_service = MemoryService()
