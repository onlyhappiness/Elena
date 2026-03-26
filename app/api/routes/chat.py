"""Chat API endpoints for Elena."""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from app.core.graph import elena_graph
from app.core.state import create_initial_state
from app.schemas.chat import ChatRequest, ChatResponse
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


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to Elena and get her response.

    This endpoint handles the main conversation flow:
    1. Gets or creates user and conversation in Supabase
    2. Loads recent conversation history
    3. Retrieves relevant memories (RAG)
    4. Generates Elena's response with persona
    5. Checks if image generation is needed
    6. Saves messages to Supabase
    7. Returns response with optional selfie URL
    """
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

        # Load recent messages from DB
        previous_messages = await conversation_service.load_recent_messages(
            conversation_id, limit=20
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

        # Save user message to DB
        await conversation_service.save_user_message(
            conversation_id=conversation_id,
            content=request.message,
        )

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


@router.get("/chat/{session_id}/history")
async def get_chat_history(session_id: str):
    """Get conversation history for a session."""
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
        from app.db.supabase import conversation_repo
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


@router.delete("/chat/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session.

    Note: This marks the conversation as inactive rather than deleting data.
    """
    try:
        conversation_id = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format",
        )

    from app.db.supabase import conversation_repo

    # Mark conversation as inactive
    conversation_repo.table.update({"is_active": False}).eq(
        "id", str(conversation_id)
    ).execute()

    return {"status": "deleted", "session_id": session_id}
