"""LLM Provider abstraction — ADR-012.

Public API:
    - LLMRequest — pydantic input (prompt + system + provider hints)
    - LLMResponse — pydantic output (text + usage + provider metadata)
    - LLMProvider — Protocol
    - LLMProviderError — base exception
"""
from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class LLMProviderError(Exception):
    """Provider-side error (rate limit / auth / network 등)."""


class LLMRequest(BaseModel):
    """Per-call LLM request."""
    model_config = ConfigDict(frozen=True)

    system:        str
    user:          str
    max_tokens:    int = 4096
    temperature:   float = 0.2
    stop:          tuple[str, ...] = ()
    metadata:      dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Per-call LLM response."""
    model_config = ConfigDict(frozen=True)

    text:               str
    provider:           str
    model:              str
    input_tokens:       int = 0
    output_tokens:      int = 0
    stop_reason:        str = ""
    raw_response_id:    str | None = None


class LLMProvider(Protocol):
    """Provider abstraction — Claude / OpenAI / Gemini.

    Plugin manifest 의 [recommendation].default_provider 가 provider name 식별.
    """

    name: str  # "claude" / "openai" / "gemini"

    def complete(self, request: LLMRequest, model: str | None = None) -> LLMResponse:
        ...

    def validate(self) -> bool:
        """Sanity check — API key 존재 / network reachable. 호출 안 함."""
        ...


__all__ = ["LLMProvider", "LLMProviderError", "LLMRequest", "LLMResponse"]
