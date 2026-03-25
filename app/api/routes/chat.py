"""Chat API endpoints for Elena."""

from uuid import uuid4

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from app.core.graph import elena_graph
from app.core.state import create_initial_state
from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter()

# In-memory session storage (will be replaced with Supabase)
_sessions: dict[str, dict] = {}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to Elena and get her response.

    This endpoint handles the main conversation flow:
    1. Retrieves relevant memories (RAG)
    2. Generates Elena's response with persona
    3. Checks if image generation is needed
    4. Returns response with optional selfie URL
    """
    # Get or create session
    session_id = request.session_id or str(uuid4())

    # Get existing state or create new one
    if session_id in _sessions:
        state = _sessions[session_id]
    else:
        state = create_initial_state(
            user_id=request.user_id,
            session_id=session_id,
        )

    # Add user message to state
    state["messages"].append(HumanMessage(content=request.message))

    try:
        # Run the conversation graph
        result = await elena_graph.ainvoke(state)

        # Update session state
        _sessions[session_id] = result

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

        return ChatResponse(
            message=response_content,
            session_id=session_id,
            image_url=result.get("image_url"),
            emotion=result.get("current_emotion"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}",
        )


@router.get("/chat/{session_id}/history")
async def get_chat_history(session_id: str):
    """Get conversation history for a session."""
    if session_id not in _sessions:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    state = _sessions[session_id]
    history = []

    for msg in state["messages"]:
        history.append({
            "role": "user" if isinstance(msg, HumanMessage) else "assistant",
            "content": msg.content,
        })

    return {
        "session_id": session_id,
        "messages": history,
        "current_emotion": state.get("current_emotion"),
    }


@router.delete("/chat/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session."""
    if session_id in _sessions:
        del _sessions[session_id]

    return {"status": "deleted", "session_id": session_id}
