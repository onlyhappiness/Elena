"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging_config import setup_logging
from app.db.postgres import PostgresPool
from app.api.routes import chat

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()
    logger.info(f"Elena starting in {settings.app_env} mode")
    await PostgresPool.init()
    yield
    await PostgresPool.close()
    logger.info("Elena shutting down")


OPENAPI_TAGS = [
    {
        "name": "chat",
        "description": "윤슬과의 대화 — 메시지 전송, 히스토리 조회, 세션 삭제",
    },
    {
        "name": "health",
        "description": "서버 상태 확인",
    },
]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    docs_url = None if settings.is_production else "/docs"
    redoc_url = None if settings.is_production else "/redoc"

    app = FastAPI(
        title="Project Elena — 윤슬 AI Companion",
        description=(
            "윤슬(Elena)과 1:1로 대화하는 AI 컴패니언 백엔드 API.\n\n"
            "## 주요 기능\n"
            "- **장기 기억(RAG)**: 대화 내용을 기억하고 자연스럽게 활용\n"
            "- **감정 인식**: 대화 맥락에 따라 윤슬의 감정 상태 변화\n"
            "- **능동적 셀카**: 상황에 맞게 fal.ai 기반 이미지 자동 생성\n\n"
            "## 인증\n"
            "현재 버전은 `user_id`를 클라이언트에서 관리합니다."
        ),
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
        docs_url=docs_url,
        redoc_url=redoc_url,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])

    @app.get("/health", tags=["health"], summary="서버 상태 확인")
    async def health_check():
        return {"status": "healthy", "persona": "윤슬"}

    return app


app = create_app()
