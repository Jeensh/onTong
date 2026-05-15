"""OpenAI provider — ADR-012 (W34: live SDK path).

Two paths:
  - Default (stub): deterministic placeholder for tests + offline demos.
  - Live SDK: openai.OpenAI().chat.completions.create — opt-in via live=True OR
    by injecting a `client` for tests.

Mirrors the W33 ClaudeProvider design.
"""
from __future__ import annotations

import os
from typing import Any

from .base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse

DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider:
    """OpenAI provider.

    Stub by default; pass `live=True` (and provide an API key) to hit the real
    OpenAI SDK. Tests inject a mock `client` to verify SDK call shape without
    network access.
    """
    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        live: bool = False,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model
        self._live = live
        self._client = client

    def complete(self, request: LLMRequest, model: str | None = None) -> LLMResponse:
        if not self._api_key and self._client is None:
            raise LLMProviderError("OpenAI provider: OPENAI_API_KEY missing.")
        if self._live or self._client is not None:
            return self._complete_via_sdk(request, model)
        effective_model = model or self._model
        return LLMResponse(
            text=f"[openai:{effective_model} stub] user-prompt-length={len(request.user)}",
            provider="openai",
            model=effective_model,
            input_tokens=len(request.user) // 4,
            output_tokens=64,
            stop_reason="stub_completion",
            raw_response_id="openai_stub_response_id",
        )

    def _complete_via_sdk(self, request: LLMRequest, model: str | None) -> LLMResponse:
        """Convert LLMRequest → openai chat.completions.create → LLMResponse.

        Caller can inject `self._client` (e.g. MagicMock) to avoid network.
        """
        client = self._client
        if client is None:
            import openai
            client = openai.OpenAI(api_key=self._api_key)

        effective_model = model or self._model
        kwargs: dict[str, Any] = {
            "model":       effective_model,
            "max_tokens":  request.max_tokens,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user",   "content": request.user},
            ],
            "temperature": request.temperature,
        }
        if request.stop:
            kwargs["stop"] = list(request.stop)

        try:
            raw = client.chat.completions.create(**kwargs)
        except Exception as e:
            raise LLMProviderError(f"OpenAI SDK call failed: {e}") from e

        # Choice 0 is the default response; extract its message.content + finish_reason
        choices = getattr(raw, "choices", []) or []
        text = ""
        stop_reason = ""
        if choices:
            choice = choices[0]
            msg = getattr(choice, "message", None)
            text = getattr(msg, "content", "") or ""
            stop_reason = getattr(choice, "finish_reason", None) or ""

        usage = getattr(raw, "usage", None)
        return LLMResponse(
            text=text,
            provider="openai",
            model=getattr(raw, "model", effective_model),
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            stop_reason=stop_reason,
            raw_response_id=getattr(raw, "id", None),
        )

    def validate(self) -> bool:
        return bool(self._api_key) or self._client is not None


_provider: LLMProvider = OpenAIProvider(api_key="dummy-for-shape-check")  # noqa: F841


__all__ = ["OpenAIProvider", "DEFAULT_MODEL"]
