"""W34 — Gemini provider live SDK path (mocked + opt-in live).

Uses the new `google.genai` SDK. Same mock-friendly pattern as W33 Claude tests.
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
from backend.sim_v2.core.recommendation.providers.gemini import (
    DEFAULT_MODEL,
    GeminiProvider,
)


def _fake_genai_response(
    *,
    text: str = "Hello from Gemini",
    prompt_tokens: int = 25,
    candidate_tokens: int = 8,
    finish_reason: str = "STOP",
    response_id: str | None = "gemini_test_1",
):
    """Mimic google.genai GenerateContentResponse shape."""
    candidate = SimpleNamespace(finish_reason=finish_reason)
    usage = SimpleNamespace(
        prompt_token_count=prompt_tokens,
        candidates_token_count=candidate_tokens,
        total_token_count=prompt_tokens + candidate_tokens,
    )
    return SimpleNamespace(
        text=text,
        candidates=[candidate],
        usage_metadata=usage,
        response_id=response_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stub mode (default) — preserved by W34
# ─────────────────────────────────────────────────────────────────────────────


def test_stub_mode_remains_default():
    p = GeminiProvider(api_key="dummy")
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text.startswith("[gemini:")
    assert resp.stop_reason == "stub_completion"


# ─────────────────────────────────────────────────────────────────────────────
# Live mode with injected mock client
# ─────────────────────────────────────────────────────────────────────────────


def test_live_mode_with_injected_client_calls_generate_content():
    mock = MagicMock()
    mock.models.generate_content.return_value = _fake_genai_response()
    p = GeminiProvider(api_key="dummy", client=mock)
    p.complete(LLMRequest(system="sys", user="prompt", max_tokens=256, temperature=0.5))

    mock.models.generate_content.assert_called_once()
    call_kwargs = mock.models.generate_content.call_args.kwargs
    assert call_kwargs["model"]    == DEFAULT_MODEL
    assert call_kwargs["contents"] == "prompt"
    cfg = call_kwargs["config"]
    assert cfg["system_instruction"] == "sys"
    assert cfg["max_output_tokens"]  == 256
    assert cfg["temperature"]         == 0.5


def test_live_mode_parses_response_into_llm_response():
    mock = MagicMock()
    mock.models.generate_content.return_value = _fake_genai_response(
        text="canned reply", prompt_tokens=11, candidate_tokens=4, response_id="g_xyz",
    )
    p = GeminiProvider(api_key="dummy", client=mock)
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text == "canned reply"
    assert resp.provider == "gemini"
    assert resp.input_tokens  == 11
    assert resp.output_tokens == 4
    assert "STOP" in resp.stop_reason
    assert resp.raw_response_id == "g_xyz"


def test_live_mode_forwards_stop_sequences():
    mock = MagicMock()
    mock.models.generate_content.return_value = _fake_genai_response()
    p = GeminiProvider(api_key="dummy", client=mock)
    p.complete(LLMRequest(system="s", user="u", stop=("END", "STOP")))
    cfg = mock.models.generate_content.call_args.kwargs["config"]
    assert cfg["stop_sequences"] == ["END", "STOP"]


def test_live_mode_propagates_sdk_failure_as_llm_provider_error():
    mock = MagicMock()
    mock.models.generate_content.side_effect = RuntimeError("quota exceeded")
    p = GeminiProvider(api_key="dummy", client=mock)
    with pytest.raises(LLMProviderError) as exc_info:
        p.complete(LLMRequest(system="s", user="u"))
    assert "quota exceeded" in str(exc_info.value)


def test_live_mode_handles_missing_text_gracefully():
    mock = MagicMock()
    mock.models.generate_content.return_value = SimpleNamespace(
        text=None, candidates=[], usage_metadata=None, response_id=None,
    )
    p = GeminiProvider(api_key="dummy", client=mock)
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text == ""
    assert resp.input_tokens  == 0
    assert resp.output_tokens == 0


def test_validate_true_when_client_injected():
    mock = MagicMock()
    assert GeminiProvider(api_key=None, client=mock).validate() is True


def test_live_true_without_client_triggers_real_import_path(monkeypatch):
    p = GeminiProvider(api_key="not-real", live=True)
    fake_genai_module = SimpleNamespace()
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = _fake_genai_response(text="from-live-gemini")
    fake_genai_module.Client = MagicMock(return_value=fake_client)
    # Set both possible import paths
    fake_google_pkg = SimpleNamespace(genai=fake_genai_module)
    monkeypatch.setitem(__import__("sys").modules, "google", fake_google_pkg)
    monkeypatch.setitem(__import__("sys").modules, "google.genai", fake_genai_module)

    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text == "from-live-gemini"
    fake_genai_module.Client.assert_called_once_with(api_key="not-real")


# ─────────────────────────────────────────────────────────────────────────────
# Real API integration — only when both env vars set
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.environ.get("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY not set — skipping live integration test",
)
@pytest.mark.skipif(
    os.environ.get("GEMINI_LIVE_TESTS") != "1",
    reason="GEMINI_LIVE_TESTS=1 not set — set explicitly to opt in to billed API calls",
)
def test_live_real_api_returns_non_empty_text():
    p = GeminiProvider(live=True, model="gemini-1.5-flash")
    resp = p.complete(LLMRequest(
        system="You are a one-word echo bot.",
        user="Reply with exactly the word OK and nothing else.",
        max_tokens=16,
        temperature=0.0,
    ))
    assert resp.text
    assert resp.provider == "gemini"
