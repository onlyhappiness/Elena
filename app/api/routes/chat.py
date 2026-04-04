"""Chat API endpoints for Elena."""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from app.core.graph import elena_graph
from app.core.state import create_initial_state
from app.schemas.chat import ChatRequest, ChatResponse, ChatHistoryResponse, DeleteSessionResponse
from app.services.conversation import conversation_service
from app.services.memory import memory_service


router = APIRouter()
logger = logging.getLogger(__name__)


async def _process_memories_background(
    user_id: UUID,
    user_message: str,
    assistant_message: str,
) -> None:
    """Background task to extract and store memories from conversation.

    This runs asynchronously after the response is sent to avoid latency.
    """
    import traceback

    try:
        logger.info(f"[Background] Starting memory processing for user {user_id}")
        memories = await memory_service.process_and_store_memories(
            user_id=user_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )
        if memories:
            logger.info(f"Stored {len(memories)} memories for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to process memories: {e}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="윤슬에게 메시지 전송",
    description=(
        "사용자 메시지를 받아 윤슬의 응답을 반환합니다.\n\n"
        "**처리 흐름**\n"
        "1. 유저 및 세션 조회/생성\n"
        "2. 관련 장기 기억 검색 (RAG)\n"
        "3. 윤슬 페르소나로 응답 생성\n"
        "4. 셀카 필요 여부 판단 → fal.ai 이미지 생성\n"
        "5. 대화 저장 (메모리 추출은 백그라운드)\n\n"
        "**응답 시간 목표**: 텍스트 < 5초 / 이미지 포함 < 10초"
    ),
    responses={
        200: {"description": "윤슬의 응답 (이미지 생성 실패 시에도 텍스트는 항상 반환)"},
        500: {"description": "LLM 응답 생성 실패"},
    },
    tags=["chat"],
)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        # Get or create user
        user = await conversation_service.get_or_create_user(request.user_id)
        user_uuid = UUID(user["id"])

        # Get or create conversation
        conversation = await conversation_service.get_or_create_conversation(
            user_id=user_uuid,
            session_id=request.session_id,
        )
        conversation_id = UUID(conversation["id"])
        session_id = str(conversation_id)

        # 메시지 로드와 저장을 병렬로 처리
        previous_messages, _ = await asyncio.gather(
            conversation_service.load_recent_messages(conversation_id, limit=20),
            conversation_service.save_user_message(
                conversation_id=conversation_id,
                content=request.message,
            ),
        )

        # Create state with loaded messages
        state = create_initial_state(
            user_id=request.user_id,
            session_id=session_id,
            internal_user_id=str(user_uuid),
        )
        state["messages"] = previous_messages

        # Add user message to state
        state["messages"].append(HumanMessage(content=request.message))

        # Run the conversation graph
        result = await elena_graph.ainvoke(state)

        # Extract response
        ai_messages = [
            msg for msg in result["messages"]
            if hasattr(msg, "type") and msg.type == "ai"
        ]

        if not ai_messages:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate response",
            )

        response_content = ai_messages[-1].content
        emotion = result.get("current_emotion")
        image_url = result.get("image_url")

        # Save assistant message to DB
        await conversation_service.save_assistant_message(
            conversation_id=conversation_id,
            content=response_content,
            emotion=emotion,
            image_url=image_url,
        )

        # Process memories in background (non-blocking)
        asyncio.create_task(
            _process_memories_background(
                user_id=user_uuid,
                user_message=request.message,
                assistant_message=response_content,
            )
        )

        return ChatResponse(
            message=response_content,
            session_id=session_id,
            image_url=image_url,
            emotion=emotion,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}",
        )


@router.get(
    "/chat/{session_id}/history",
    response_model=ChatHistoryResponse,
    summary="대화 히스토리 조회",
    responses={
        200: {"description": "세션의 전체 메시지 목록"},
        400: {"description": "유효하지 않은 session_id 형식"},
        404: {"description": "존재하지 않는 세션"},
    },
    tags=["chat"],
)
async def get_chat_history(session_id: str):
    try:
        conversation_id = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format",
        )

    history = await conversation_service.get_conversation_history(conversation_id)

    if not history:
        # Check if conversation exists
        from app.db.postgres import conversation_repo
        conversation = await conversation_repo.get(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Session not found",
            )

    return {
        "session_id": session_id,
        "messages": history,
    }


@router.delete(
    "/chat/{session_id}",
    response_model=DeleteSessionResponse,
    summary="대화 세션 종료",
    description="세션을 비활성화합니다. 데이터는 보존되며 실제 삭제는 하지 않습니다.",
    responses={
        200: {"description": "세션 비활성화 성공"},
        400: {"description": "유효하지 않은 session_id 형식"},
    },
    tags=["chat"],
)
async def delete_session(session_id: str):
    try:
        conversation_id = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format",
        )

    from app.db.postgres import conversation_repo

    # Mark conversation as inactive
    await conversation_repo.deactivate(conversation_id)

    return {"status": "deleted", "session_id": session_id}
