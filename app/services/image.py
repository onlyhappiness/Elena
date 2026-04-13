"""fal.ai image generation service."""

import logging
import os
import time

import fal_client

from app.config import get_settings

logger = logging.getLogger(__name__)

# MVP: 속도·가성비 우선 (Phase 2에서 flux/dev 또는 IP-Adapter로 업그레이드 고려)
# FAL_MODEL = "fal-ai/flux/schnell"
FAL_MODEL = "fal-ai/nano-banana-2"

# 실측 기준: nano-banana-2 이미지 생성 22~32초 → 여유 포함 45초
FAL_TIMEOUT = 45


def _set_fal_credentials() -> bool:
    """Settings에서 FAL_KEY를 읽어 fal-client가 참조하는 os.environ에 주입.

    pydantic-settings는 .env를 Settings 객체에만 로드하고 os.environ에는
    전파하지 않아서 fal-client가 키를 찾지 못하는 문제를 해결.

    Returns:
        bool: 키가 설정되면 True, 없으면 False.
    """
    settings = get_settings()
    if not settings.fal_key:
        logger.warning("FAL_KEY가 설정되지 않음 — 이미지 생성 불가")
        return False
    os.environ["FAL_KEY"] = settings.fal_key
    return True


async def generate_selfie(image_prompt: str) -> str | None:
    """fal.ai로 윤슬 셀카를 생성하고 이미지 URL을 반환.

    Args:
        image_prompt: persona.get_image_prompt()가 반환한 완성된 프롬프트

    Returns:
        image_url: 생성된 이미지 URL. 실패 시 None (graceful degradation).
    """
    if not _set_fal_credentials():
        return None

    try:
        start = time.perf_counter()
        result = await fal_client.run_async(
            FAL_MODEL,
            arguments={"prompt": image_prompt},
            timeout=FAL_TIMEOUT,
        )
        elapsed = time.perf_counter() - start
        image_url = result["images"][0]["url"]
        logger.info(f"이미지 생성 성공 ({elapsed:.1f}s): {image_url}")
        return image_url

    except Exception as e:
        logger.warning(f"fal.ai 이미지 생성 실패 — image_url=None 반환: {e}")
        return None
