"""Central logging configuration for Elena."""

import logging
import sys

from app.config import get_settings


def setup_logging() -> None:
    """애플리케이션 로깅을 초기화합니다.

    - development: DEBUG 레벨, 상세 포맷
    - production: INFO 레벨, 간결한 포맷
    Docker stdout 출력 기준으로 설정.
    """
    settings = get_settings()

    log_level = logging.DEBUG if settings.debug else logging.INFO

    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s"
        if settings.debug
        else "%(asctime)s | %(levelname)-8s | %(message)s"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # 외부 라이브러리 노이즈 억제
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("langgraph").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
