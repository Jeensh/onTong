"""Vision LLM provider abstraction for image description generation."""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

VISION_PROMPT = """이 이미지는 사내 위키 문서에 포함된 것입니다.
이 이미지의 내용을 문서 본문의 일부로 사용할 수 있도록 상세히 설명하세요.

포함할 내용:
- 이미지 유형 (대화 캡처, 에러 화면, 시스템 화면, 다이어그램 등)
- 등장하는 사람/시스템 이름
- 핵심 내용 요약 (무슨 상황인지)
- 중요한 수치, 코드, 에러 메시지
- 시간 정보가 있으면 포함

아래는 OCR로 추출된 텍스트입니다. 참고하되, 이미지의 시각적 맥락(레이아웃, UI 상태, 관계)을 추가로 설명하세요.

OCR 텍스트:
{ocr_text}

한국어로 작성하세요."""


@runtime_checkable
class VisionProvider(Protocol):
    @property
    def provider_name(self) -> str: ...
    async def describe(self, image_path: Path, ocr_text: str) -> str: ...


class NoopVisionProvider:
    """No-op provider: returns empty description. Used when vision is disabled."""

    @property
    def provider_name(self) -> str:
        return "none"

    async def describe(self, image_path: Path, ocr_text: str) -> str:
        return ""


class OllamaVisionProvider:
    """Ollama-based vision provider using models like LLaVA."""

    def __init__(self, model: str = "llava:13b", ollama_url: str = "http://localhost:11434"):
        self._model = model
        self._ollama_url = ollama_url

    @property
    def provider_name(self) -> str:
        return f"ollama/{self._model}"

    async def describe(self, image_path: Path, ocr_text: str) -> str:
        """Send image to Ollama vision model and return description."""
        import ollama

        prompt = VISION_PROMPT.format(ocr_text=ocr_text if ocr_text else "(OCR 텍스트 없음)")

        def _call_ollama() -> str:
            image_bytes = image_path.read_bytes()
            b64 = base64.b64encode(image_bytes).decode("ascii")
            client = ollama.Client(host=self._ollama_url)
            response = client.chat(
                model=self._model,
                messages=[{"role": "user", "content": prompt, "images": [b64]}],
            )
            return response["message"]["content"]

        try:
            return await asyncio.to_thread(_call_ollama)
        except Exception as e:
            logger.warning(f"Ollama vision failed for {image_path.name}: {e}")
            return ""


class ClaudeVisionProvider:
    """Anthropic Claude-based vision provider for image description."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001", api_key: str = ""):
        self._model = model
        self._api_key = api_key

    @property
    def provider_name(self) -> str:
        return f"claude/{self._model}"

    async def describe(self, image_path: Path, ocr_text: str) -> str:
        """Send image to Claude Vision API and return description."""
        import anthropic

        prompt = VISION_PROMPT.format(ocr_text=ocr_text if ocr_text else "(OCR 텍스트 없음)")

        try:
            image_bytes = image_path.read_bytes()
            b64 = base64.b64encode(image_bytes).decode("ascii")

            suffix = image_path.suffix.lower()
            media_type_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            media_type = media_type_map.get(suffix, "image/png")

            client = anthropic.AsyncAnthropic(api_key=self._api_key or None)
            response = await client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            return response.content[0].text
        except Exception as e:
            logger.warning(f"Claude vision failed for {image_path.name}: {e}")
            return ""


def create_vision_provider(
    provider: str = "none",
    model: str = "llava:13b",
    ollama_url: str = "http://localhost:11434",
    api_key: str = "",
) -> VisionProvider:
    """Factory function to create a VisionProvider by name."""
    if provider == "ollama":
        return OllamaVisionProvider(model=model, ollama_url=ollama_url)
    if provider == "claude":
        claude_model = model if model.startswith("claude") else "claude-haiku-4-5-20251001"
        return ClaudeVisionProvider(model=claude_model, api_key=api_key)
    return NoopVisionProvider()
