"""W34 — OpenAI provider live SDK path (mocked + opt-in live).

Mirrors W33 Claude tests. The `live=True` / `client=` path of OpenAIProvider is
verified against a mock chat.completions response shape.
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
from backend.sim_v2.core.recommendation.providers.openai import (
    DEFAULT_MODEL,
    OpenAIProvider,
)


def _fake_chat_completion(
    *,
    text: str = "Hello from OpenAI",
    model: str = DEFAULT_MODEL,
    prompt_tokens: int = 30,
    completion_tokens: int = 9,
    finish_reason: str = "stop",
    response_id: str = "chatcmpl_test",
):
    """Mimic openai.types.chat.ChatCompletion shape."""
    message = SimpleNamespace(content=text, role="assistant")
    choice = SimpleNamespace(message=message, finish_reason=finish_reason, index=0)
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens)
    return SimpleNamespace(id=response_id, choices=[choice], model=model, usage=usage)


# ─────────────────────────────────────────────────────────────────────────────
# Stub mode (default) — preserved by W34
# ─────────────────────────────────────────────────────────────────────────────


def test_stub_mode_remains_default():
    p = OpenAIProvider(api_key="dummy")
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text.startswith("[openai:")
    assert resp.stop_reason == "stub_completion"


# ─────────────────────────────────────────────────────────────────────────────
# Live mode with injected mock client
# ─────────────────────────────────────────────────────────────────────────────


def test_live_mode_with_injected_client_calls_chat_completions_create():
    mock = MagicMock()
    mock.chat.completions.create.return_value = _fake_chat_completion()
    p = OpenAIProvider(api_key="dummy", client=mock)
    p.complete(LLMRequest(system="sys", user="user prompt", max_tokens=512, temperature=0.4))

    mock.chat.completions.create.assert_called_once()
    call_kwargs = mock.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == DEFAULT_MODEL
    assert call_kwargs["max_tokens"] == 512
    assert call_kwargs["temperature"] == 0.4
    # system + user routed as 2 message entries
    assert call_kwargs["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user",   "content": "user prompt"},
    ]


def test_live_mode_parses_response_into_llm_response():
    mock = MagicMock()
    mock.chat.completions.create.return_value = _fake_chat_completion(
        text="canned reply", prompt_tokens=7, completion_tokens=13, response_id="chat_xyz",
    )
    p = OpenAIProvider(api_key="dummy", client=mock)
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text == "canned reply"
    assert resp.provider == "openai"
    assert resp.input_tokens == 7
    assert resp.output_tokens == 13
    assert resp.stop_reason == "stop"
    assert resp.raw_response_id == "chat_xyz"


def test_live_mode_forwards_stop_sequences():
    mock = MagicMock()
    mock.chat.completions.create.return_value = _fake_chat_completion()
    p = OpenAIProvider(api_key="dummy", client=mock)
    p.complete(LLMRequest(system="s", user="u", stop=("END",)))
    call_kwargs = mock.chat.completions.create.call_args.kwargs
    assert call_kwargs["stop"] == ["END"]


def test_live_mode_propagates_sdk_failure_as_llm_provider_error():
    mock = MagicMock()
    mock.chat.completions.create.side_effect = RuntimeError("auth fail")
    p = OpenAIProvider(api_key="dummy", client=mock)
    with pytest.raises(LLMProviderError) as exc_info:
        p.complete(LLMRequest(system="s", user="u"))
    assert "auth fail" in str(exc_info.value)


def test_live_mode_handles_empty_choices_gracefully():
    mock = MagicMock()
    mock.chat.completions.create.return_value = SimpleNamespace(
        id="chat_empty", choices=[], model=DEFAULT_MODEL,
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=0),
    )
    p = OpenAIProvider(api_key="dummy", client=mock)
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text == ""
    assert resp.stop_reason == ""


def test_validate_true_when_client_injected():
    mock = MagicMock()
    assert OpenAIProvider(api_key=None, client=mock).validate() is True


def test_live_true_without_client_triggers_real_import_path(monkeypatch):
    p = OpenAIProvider(api_key="not-real", live=True)
    fake_openai = SimpleNamespace()
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_chat_completion(text="from-live-openai")
    fake_openai.OpenAI = MagicMock(return_value=fake_client)
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_openai)

    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.text == "from-live-openai"
    fake_openai.OpenAI.assert_called_once_with(api_key="not-real")


# ─────────────────────────────────────────────────────────────────────────────
# Real API integration — only when both env vars set
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping live integration test",
)
@pytest.mark.skipif(
    os.environ.get("OPENAI_LIVE_TESTS") != "1",
    reason="OPENAI_LIVE_TESTS=1 not set — set explicitly to opt in to billed API calls",
)
def test_live_real_api_returns_non_empty_text():
    p = OpenAIProvider(live=True, model="gpt-4o-mini")  # cheapest
    resp = p.complete(LLMRequest(
        system="You are a one-word echo bot.",
        user="Reply with exactly the word OK and nothing else.",
        max_tokens=16,
        temperature=0.0,
    ))
    assert resp.text
    assert resp.provider == "openai"
    assert resp.input_tokens > 0
    assert resp.output_tokens > 0
