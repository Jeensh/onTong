"""Claude provider — ADR-012 (W33: live SDK path).

Two paths:
  - Default (stub): deterministic placeholder for tests + offline demos.
  - Live SDK: anthropic.Anthropic().messages.create() — opt-in via live=True
    OR by injecting a `client` for tests.

The provider stays Protocol-compliant in both modes.
"""
from __future__ import annotations

import os
from typing import Any

from .base import LLMProvider, LLMProviderError, LLMRequest, LLMResponse

DEFAULT_MODEL = "claude-opus-4-7"


class ClaudeProvider:
    """Anthropic Claude provider.

    Stub by default; pass `live=True` (and provide an API key) to hit the real
    anthropic SDK. Tests inject a mock `client` to verify SDK call shape without
    network access.
    """
    name = "claude"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        live: bool = False,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model
        self._live = live
        self._client = client

    def complete(self, request: LLMRequest, model: str | None = None) -> LLMResponse:
        if not self._api_key and self._client is None:
            raise LLMProviderError(
                "Claude provider: ANTHROPIC_API_KEY missing. "
                "Set env var or pass api_key= to ClaudeProvider()."
            )
        # Route via SDK when explicitly opted in or when a (test) client is injected
        if self._live or self._client is not None:
            return self._complete_via_sdk(request, model)
        # Stub — deterministic placeholder for test isolation
        effective_model = model or self._model
        return LLMResponse(
            text=f"[claude:{effective_model} stub] user-prompt-length={len(request.user)}",
            provider="claude",
            model=effective_model,
            input_tokens=len(request.user) // 4,
            output_tokens=64,
            stop_reason="stub_completion",
            raw_response_id="claude_stub_response_id",
        )

    def _complete_via_sdk(self, request: LLMRequest, model: str | None) -> LLMResponse:
        """Convert LLMRequest → anthropic.messages.create call → LLMResponse.

        Caller can inject `self._client` (e.g. MagicMock) to avoid network.
        """
        client = self._client
        if client is None:
            import anthropic
            client = anthropic.Anthropic(api_key=self._api_key)

        effective_model = model or self._model
        kwargs: dict[str, Any] = {
            "model":       effective_model,
            "max_tokens":  request.max_tokens,
            "system":      request.system,
            "messages":    [{"role": "user", "content": request.user}],
            "temperature": request.temperature,
        }
        if request.stop:
            kwargs["stop_sequences"] = list(request.stop)

        try:
            raw = client.messages.create(**kwargs)
        except Exception as e:  # network / auth / rate-limit
            raise LLMProviderError(f"Claude SDK call failed: {e}") from e

        # Extract text from the first TextBlock; ignore non-text blocks
        text = ""
        for block in getattr(raw, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text = block.text
                break

        usage = getattr(raw, "usage", None)
        return LLMResponse(
            text=text,
            provider="claude",
            model=getattr(raw, "model", effective_model),
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            stop_reason=getattr(raw, "stop_reason", None) or "",
            raw_response_id=getattr(raw, "id", None),
        )

    def validate(self) -> bool:
        return bool(self._api_key) or self._client is not None


# Ensure Protocol compliance (run-time check via isinstance for Protocol with @runtime_checkable
# would require @runtime_checkable; we rely on duck-typing).
_provider: LLMProvider = ClaudeProvider(api_key="dummy-for-shape-check")  # noqa: F841


__all__ = ["ClaudeProvider", "DEFAULT_MODEL"]
