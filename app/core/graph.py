"""LangGraph conversation flow for Elena."""

import logging
from uuid import UUID

# from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from app.config import get_settings
from app.core.persona import (
    get_system_prompt_with_context,
    should_generate_image,
    extract_selfie_tag,
    parse_selfie_context,
    get_image_prompt,
    EMOTIONS,
)
from app.core.state import ElenaState
from app.services.memory import memory_service


logger = logging.getLogger(__name__)


def get_llm() -> ChatOpenAI:
    """Get configured OpenAI LLM instance."""
    settings = get_settings()
    # Claude version (commented out for testing with OpenAI)
    # return ChatAnthropic(
    #     model="claude-sonnet-4-5-20250929",
    #     api_key=settings.anthropic_api_key,
    #     max_tokens=1024,
    #     temperature=0.8,
    # )
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key,
        max_tokens=1024,
        temperature=0.8,
    )


async def retrieve_memories_node(state: ElenaState) -> dict:
    """Node 1: Retrieve relevant memories from past conversations.

    Uses vector similarity search to find memories related to the user's message.
    """
    # Get internal user ID for DB lookup
    internal_user_id = state.get("internal_user_id")
    if not internal_user_id:
        logger.debug("No internal_user_id in state, skipping memory retrieval")
        return {"memories": []}

    # Get the last user message as query
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    if not user_messages:
        return {"memories": []}

    query = user_messages[-1].content

    try:
        # Search for relevant memories
        raw_memories = await memory_service.search_relevant_memories(
            user_id=UUID(internal_user_id),
            query=query,
            threshold=0.7,
            limit=5,
        )

        # Transform to format expected by persona prompt
        # Expects: {"content": str, "feeling": str (optional)}
        memories = []
        for mem in raw_memories:
            memory_item = {
                "content": mem.get("summary") or mem.get("content", ""),
            }
            # Map memory_type to a feeling description
            memory_type = mem.get("memory_type", "")
            if memory_type == "emotion":
                memory_item["feeling"] = "감정적인 기억"
            elif memory_type == "preference":
                memory_item["feeling"] = "좋아하는 것"
            elif memory_type == "fact":
                memory_item["feeling"] = "중요한 정보"
            memories.append(memory_item)

        if memories:
            logger.info(f"Retrieved {len(memories)} relevant memories")

        return {"memories": memories}

    except Exception as e:
        logger.error(f"Failed to retrieve memories: {e}")
        return {"memories": []}


async def generate_response_node(state: ElenaState) -> dict:
    """Node 2: Generate Elena's response using Claude."""
    llm = get_llm()

    # Build system prompt with context
    system_prompt = get_system_prompt_with_context(
        memories=state.get("memories"),
        current_emotion=state.get("current_emotion", "calm"),
    )

    # Prepare messages for LLM
    messages = [SystemMessage(content=system_prompt)]
    messages.extend(state["messages"])

    # Generate response
    response = await llm.ainvoke(messages)

    # Detect emotion from response
    detected_emotion = detect_emotion(response.content)

    # Check for proactive selfie tag [SELFIE: ...]
    selfie_context, cleaned_response = extract_selfie_tag(response.content)

    # Update response content if tag was found
    if selfie_context:
        response = AIMessage(content=cleaned_response)

    return {
        "messages": [response],
        "current_emotion": detected_emotion,
        "selfie_context": selfie_context,  # Store for image generation
    }


async def check_image_needed_node(state: ElenaState) -> dict:
    """Node 3: Check if image generation is needed.

    Image is generated when:
    1. User explicitly requests (keywords)
    2. Elena proactively wants to share (SELFIE tag)
    """
    # Check for proactive selfie from Elena
    selfie_context = state.get("selfie_context")
    if selfie_context:
        parsed_context = parse_selfie_context(selfie_context)
        image_prompt = get_image_prompt(
            emotion=state.get("current_emotion", "calm"),
            selfie_context=parsed_context,
        )
        return {
            "should_generate_image": True,
            "image_prompt": image_prompt,
        }

    # Check for user request
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]

    if not user_messages:
        return {"should_generate_image": False}

    last_user_message = user_messages[-1].content
    needs_image = should_generate_image(last_user_message)

    image_prompt = None
    if needs_image:
        image_prompt = get_image_prompt(
            emotion=state.get("current_emotion", "calm"),
            selfie_context=None,
        )

    return {
        "should_generate_image": needs_image,
        "image_prompt": image_prompt,
    }


async def generate_image_node(state: ElenaState) -> dict:
    """Node 4: Generate selfie using fal.ai.

    TODO: Implement actual fal.ai integration.
    For now, returns placeholder.
    """
    if not state.get("should_generate_image"):
        return {"image_url": None}

    # Placeholder - will be implemented with fal.ai service
    # image_url = await fal_service.generate_selfie(state["image_prompt"])
    print(f"[DEBUG] Image prompt: {state.get('image_prompt')}")

    return {"image_url": None}


def route_after_response(state: ElenaState) -> str:
    """Router: Decide whether to generate image or end."""
    if state.get("should_generate_image"):
        return "generate_image"
    return END


def detect_emotion(text: str) -> str:
    """Detect emotion from response text using keyword matching."""
    text_lower = text.lower()

    emotion_indicators = {
        "happy": ["ㅋㅋ", "😊", "😆", "대박", "좋아", "신나", "재밌"],
        "excited": ["헐", "오!", "와!", "🔥", "❤️", "완전"],
        "sad": ["😢", "😭", "슬프", "우울", "힘들"],
        "anxious": ["걱정", "불안", "고민", "어떡", "😰", "모르겠"],
        "nostalgic": ["그때", "예전", "그리워", "추억", "생각나"],
        "calm": ["😌", "평화", "여유", "편안", "좋다"],
    }

    for emotion, indicators in emotion_indicators.items():
        if any(indicator in text_lower for indicator in indicators):
            return emotion

    return "calm"


def build_elena_graph() -> StateGraph:
    """Build and compile the Elena conversation graph."""
    # Create graph with ElenaState
    graph = StateGraph(ElenaState)

    # Add nodes
    graph.add_node("retrieve_memories", retrieve_memories_node)
    graph.add_node("generate_response", generate_response_node)
    graph.add_node("check_image", check_image_needed_node)
    graph.add_node("generate_image", generate_image_node)

    # Define edges
    graph.set_entry_point("retrieve_memories")
    graph.add_edge("retrieve_memories", "generate_response")
    graph.add_edge("generate_response", "check_image")

    # Conditional routing after checking image need
    graph.add_conditional_edges(
        "check_image",
        route_after_response,
        {
            "generate_image": "generate_image",
            END: END,
        },
    )
    graph.add_edge("generate_image", END)

    return graph.compile()


# Compiled graph instance
elena_graph = build_elena_graph()
