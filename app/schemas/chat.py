"""Chat-related Pydantic schemas."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class Role(str, Enum):
    """Message role enum."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Single message in conversation."""
    role: Role
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """윤슬에게 메시지를 보내는 요청 스키마."""

    user_id: str = Field(..., description="클라이언트가 관리하는 고유 사용자 식별자")
    message: str = Field(..., min_length=1, max_length=2000, description="사용자 메시지")
    session_id: str | None = Field(
        None,
        description="대화 세션 ID. 생략 시 새 세션 자동 생성. 이전 대화를 이어가려면 응답의 session_id를 전달.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "새 대화 시작",
                    "value": {
                        "user_id": "user-abc123",
                        "message": "안녕! 오늘 뭐 했어?",
                    },
                },
                {
                    "summary": "기존 세션 이어가기",
                    "value": {
                        "user_id": "user-abc123",
                        "message": "사진 보여줘",
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                    },
                },
            ]
        }
    }


class ChatResponse(BaseModel):
    """윤슬의 응답 스키마."""

    message: str = Field(..., description="윤슬의 응답 텍스트")
    session_id: str = Field(..., description="대화 세션 ID. 다음 요청 시 전달하면 대화가 이어짐.")
    image_url: str | None = Field(None, description="생성된 셀카 이미지 URL. 셀카가 없으면 null.")
    emotion: str | None = Field(
        None,
        description="윤슬의 현재 감정 상태. happy | calm | anxious | nostalgic | excited | sad",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "텍스트 응답",
                    "value": {
                        "message": "오늘 바다 보면서 멍 때렸어 🌊 파도 소리가 진짜 좋더라",
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "image_url": None,
                        "emotion": "calm",
                    },
                },
                {
                    "summary": "셀카 포함 응답",
                    "value": {
                        "message": "야 지금 노을 미쳤어 진짜 🌅",
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "image_url": "https://fal.media/files/example.jpg",
                        "emotion": "excited",
                    },
                },
            ]
        }
    }


class ChatHistoryResponse(BaseModel):
    """대화 히스토리 응답 스키마."""

    session_id: str = Field(..., description="대화 세션 ID")
    messages: list[dict] = Field(..., description="메시지 목록 (role, content, emotion, image_url, created_at)")


class DeleteSessionResponse(BaseModel):
    """세션 삭제 응답 스키마."""

    status: str = Field(..., description="처리 결과. 항상 'deleted'.")
    session_id: str = Field(..., description="삭제된 세션 ID")
