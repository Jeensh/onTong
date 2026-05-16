"""Gemini provider — ADR-012 (W34: live SDK path).

Two paths:
  - Default (stub): deterministic placeholder for tests + offline demos.
  - Live SDK: google.genai.Client.models.generate_content — opt-in via live=True
    OR by injecting a `client` for tests.

Uses the new `google.genai` package (Client API), not the legacy
`google.generativeai` module.
"""
from __future__ import annotations

import os
from typing import Any

from .base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse

DEFAULT_MODEL = "gemini-1.5-pro"


class GeminiProvider:
    """Google Gemini provider.

    Stub by default; pass `live=True` (and provide an API key) to hit the real
    google.genai SDK. Tests inject a mock `client` to verify SDK call shape
    without network access.
    """
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        live: bool = False,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self._model = model
        self._live = live
        self._client = client

    def complete(self, request: LLMRequest, model: str | None = None) -> LLMResponse:
        if not self._api_key and self._client is None:
            raise LLMProviderError("Gemini provider: GOOGLE_API_KEY missing.")
        if self._live or self._client is not None:
            return self._complete_via_sdk(request, model)
        effective_model = model or self._model
        return LLMResponse(
            text=f"[gemini:{effective_model} stub] user-prompt-length={len(request.user)}",
            provider="gemini",
            model=effective_model,
            input_tokens=len(request.user) // 4,
            output_tokens=64,
            stop_reason="stub_completion",
            raw_response_id="gemini_stub_response_id",
        )

    def _complete_via_sdk(self, request: LLMRequest, model: str | None) -> LLMResponse:
        """Convert LLMRequest → google.genai generate_content call → LLMResponse.

        google.genai treats system_instruction as a separate config field; the
        user prompt is the `contents` argument. Caller can inject `self._client`
        (e.g. MagicMock) to avoid network.
        """
        client = self._client
        if client is None:
            from google import genai
            client = genai.Client(api_key=self._api_key)

        effective_model = model or self._model
        # google.genai config is passed via generate_content's `config` kw or
        # GenerateContentConfig type — we keep this loose so MagicMock works.
        config: dict[str, Any] = {
            "system_instruction": request.system,
            "max_output_tokens":  request.max_tokens,
            "temperature":        request.temperature,
        }
        if request.stop:
            config["stop_sequences"] = list(request.stop)

        try:
            raw = client.models.generate_content(
                model=effective_model,
                contents=request.user,
                config=config,
            )
        except Exception as e:
            raise LLMProviderError(f"Gemini SDK call failed: {e}") from e

        # genai response: .text is convenience; .candidates[0].finish_reason / usage_metadata
        text = getattr(raw, "text", "") or ""
        candidates = getattr(raw, "candidates", []) or []
        stop_reason = ""
        if candidates:
            stop_reason = str(getattr(candidates[0], "finish_reason", "") or "")

        usage = getattr(raw, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

        return LLMResponse(
            text=text,
            provider="gemini",
            model=effective_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
            raw_response_id=getattr(raw, "response_id", None),
        )

    def validate(self) -> bool:
        return bool(self._api_key) or self._client is not None


_provider: LLMProvider = GeminiProvider(api_key="dummy-for-shape-check")  # noqa: F841


__all__ = ["GeminiProvider", "DEFAULT_MODEL"]
