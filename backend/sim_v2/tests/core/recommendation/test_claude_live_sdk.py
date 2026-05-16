"""W33 — Claude provider live SDK path (mocked + opt-in live).

Tests the `live=True` / `client=` path of ClaudeProvider without hitting the
real Anthropic API. A separate skip-if-no-key test exercises the live path
when ANTHROPIC_API_KEY is set in the environment.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.sim_v2.core.recommendation.providers.base import (
    LLMProviderError,
    LLMRequest,
)
from backend.sim_v2.core.recommendation.providers.claude import (
    DEFAULT_MODEL,
    ClaudeProvider,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper — build a fake SDK response object
# ─────────────────────────────────────────────────────────────────────────────


def _fake_anthropic_response(
    *,
    text: str = "Hello from Claude",
    model: str = DEFAULT_MODEL,
    input_tokens: int = 42,
    output_tokens: int = 11,
    stop_reason: str = "end_turn",
    response_id: str = "msg_test_001",
):
    """Mimic the shape of anthropic.types.Message returned by messages.create."""
    text_block = SimpleNamespace(type="text", text=text)
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(
        id=response_id,
        content=[text_block],
        model=model,
        stop_reason=stop_reason,
        usage=usage,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stub mode (default) — preserved by W33
# ─────────────────────────────────────────────────────────────────────────────


def test_stub_mode_remains_default():
    p = ClaudeProvider(api_key="dummy")
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text.startswith("[claude:")
    assert resp.stop_reason == "stub_completion"


# ─────────────────────────────────────────────────────────────────────────────
# Live mode with injected mock client
# ─────────────────────────────────────────────────────────────────────────────


def test_live_mode_with_injected_client_calls_messages_create():
    mock = MagicMock()
    mock.messages.create.return_value = _fake_anthropic_response()
    p = ClaudeProvider(api_key="dummy", client=mock)
    resp = p.complete(LLMRequest(system="sys", user="user prompt", max_tokens=2048, temperature=0.3))

    mock.messages.create.assert_called_once()
    call_kwargs = mock.messages.create.call_args.kwargs
    assert call_kwargs["model"]       == DEFAULT_MODEL
    assert call_kwargs["system"]      == "sys"
    assert call_kwargs["max_tokens"]  == 2048
    assert call_kwargs["temperature"] == 0.3
    assert call_kwargs["messages"]    == [{"role": "user", "content": "user prompt"}]
    # stop_sequences absent when request.stop is empty
    assert "stop_sequences" not in call_kwargs


def test_live_mode_parses_response_into_llm_response():
    mock = MagicMock()
    mock.messages.create.return_value = _fake_anthropic_response(
        text="canned reply", input_tokens=7, output_tokens=13, response_id="msg_xyz",
    )
    p = ClaudeProvider(api_key="dummy", client=mock)
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text == "canned reply"
    assert resp.provider == "claude"
    assert resp.input_tokens == 7
    assert resp.output_tokens == 13
    assert resp.stop_reason == "end_turn"
    assert resp.raw_response_id == "msg_xyz"


def test_live_mode_uses_overridden_model():
    mock = MagicMock()
    mock.messages.create.return_value = _fake_anthropic_response(model="claude-sonnet-4-6")
    p = ClaudeProvider(api_key="dummy", client=mock)
    p.complete(LLMRequest(system="s", user="u"), model="claude-sonnet-4-6")
    assert mock.messages.create.call_args.kwargs["model"] == "claude-sonnet-4-6"


def test_live_mode_forwards_stop_sequences():
    mock = MagicMock()
    mock.messages.create.return_value = _fake_anthropic_response()
    p = ClaudeProvider(api_key="dummy", client=mock)
    p.complete(LLMRequest(system="s", user="u", stop=("END", "STOP")))
    call_kwargs = mock.messages.create.call_args.kwargs
    assert call_kwargs["stop_sequences"] == ["END", "STOP"]


def test_live_mode_propagates_sdk_failure_as_llm_provider_error():
    mock = MagicMock()
    mock.messages.create.side_effect = RuntimeError("rate limit")
    p = ClaudeProvider(api_key="dummy", client=mock)
    with pytest.raises(LLMProviderError) as exc_info:
        p.complete(LLMRequest(system="s", user="u"))
    assert "rate limit" in str(exc_info.value)


def test_live_mode_handles_empty_content_gracefully():
    """Edge: response has no text blocks (refusal etc.)."""
    mock = MagicMock()
    mock.messages.create.return_value = SimpleNamespace(
        id="msg_empty",
        content=[],
        model=DEFAULT_MODEL,
        stop_reason="refusal",
        usage=SimpleNamespace(input_tokens=5, output_tokens=0),
    )
    p = ClaudeProvider(api_key="dummy", client=mock)
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text == ""
    assert resp.stop_reason == "refusal"


def test_live_with_only_client_no_api_key():
    """Inject a client without an API key — provider should still work for tests."""
    mock = MagicMock()
    mock.messages.create.return_value = _fake_anthropic_response()
    p = ClaudeProvider(api_key=None, client=mock)
    # No raise even though api_key is None — client presence bypasses the key check
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text == "Hello from Claude"


def test_validate_true_when_client_injected():
    mock = MagicMock()
    p = ClaudeProvider(api_key=None, client=mock)
    assert p.validate() is True


def test_live_true_without_client_triggers_real_import_path(monkeypatch):
    """`live=True` (no client) should trigger the anthropic import + raise on bad key."""
    # Force the real SDK path by setting live=True
    p = ClaudeProvider(api_key="invalid-key-not-a-real-credential", live=True)

    # Mock out the anthropic module's Anthropic class to avoid network
    fake_anthropic_module = SimpleNamespace()
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_anthropic_response(text="from-live-import")
    fake_anthropic_module.Anthropic = MagicMock(return_value=fake_client)
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_anthropic_module)

    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text == "from-live-import"
    # Verify the Anthropic constructor received our api_key
    fake_anthropic_module.Anthropic.assert_called_once_with(api_key="invalid-key-not-a-real-credential")


# ─────────────────────────────────────────────────────────────────────────────
# Real API integration — only when ANTHROPIC_API_KEY is set
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live integration test",
)
@pytest.mark.skipif(
    os.environ.get("ANTHROPIC_LIVE_TESTS") != "1",
    reason="ANTHROPIC_LIVE_TESTS=1 not set — set explicitly to opt in to billed API calls",
)
def test_live_real_api_returns_non_empty_text():
    """Opt-in: hits the real Anthropic API. Both env vars must be set."""
    p = ClaudeProvider(live=True, model="claude-haiku-4-5")  # cheapest model
    resp = p.complete(LLMRequest(
        system="You are a one-word echo bot.",
        user="Reply with exactly the word OK and nothing else.",
        max_tokens=16,
        temperature=0.0,
    ))
    assert resp.text  # non-empty
    assert resp.provider == "claude"
    assert resp.input_tokens > 0
    assert resp.output_tokens > 0
