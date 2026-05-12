"""OpenAI thin wrapper — Section 3 의 LLM 단일 진입점.

설계:
- 모델은 환경변수 OPENAI_MODEL (default: gpt-4o-mini). 추후 다른 provider 교체 시
  이 파일만 바꾸면 됨.
- JSON 모드 (`response_format={"type": "json_object"}`) 지원 — intent classifier 가 사용.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


class LLMClient:
    """OpenAI Chat Completions thin wrapper."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.model = model
        self._client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        """일반 chat completion. text 반환."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """JSON object 만 반환. 호출자는 system prompt 에서 JSON 스키마를 명시해야 함."""
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning("LLM JSON parse failed: %s\ncontent=%s", e, content[:500])
            return {"_parse_error": str(e), "_raw": content}


# ─── 단일 인스턴스 ────────────────────────────────────────────────

_singleton: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _singleton
    if _singleton is None:
        _singleton = LLMClient()
    return _singleton


__all__ = ["LLMClient", "get_llm_client", "DEFAULT_MODEL"]
