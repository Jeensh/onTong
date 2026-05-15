"""LLM Provider abstraction test — ADR-012 (W5.2)."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.recommendation.providers.base import (
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
)
from backend.sim_v2.core.recommendation.providers.claude import (
    DEFAULT_MODEL as CLAUDE_DEFAULT,
    ClaudeProvider,
)
from backend.sim_v2.core.recommendation.providers.gemini import (
    DEFAULT_MODEL as GEMINI_DEFAULT,
    GeminiProvider,
)
from backend.sim_v2.core.recommendation.providers.openai import (
    DEFAULT_MODEL as OPENAI_DEFAULT,
    OpenAIProvider,
)
from backend.sim_v2.core.recommendation.providers.registry import (
    ProviderRegistry,
    get_default_registry,
    reset_default_registry,
)


@pytest.fixture(autouse=True)
def reset_registry():
    yield
    reset_default_registry()


def test_default_models():
    assert CLAUDE_DEFAULT == "claude-opus-4-7"
    assert OPENAI_DEFAULT == "gpt-4o"
    assert GEMINI_DEFAULT == "gemini-1.5-pro"


@pytest.mark.parametrize("provider_cls, expected_name", [
    (ClaudeProvider, "claude"),
    (OpenAIProvider, "openai"),
    (GeminiProvider, "gemini"),
])
def test_provider_name(provider_cls, expected_name):
    p = provider_cls(api_key="dummy")
    assert p.name == expected_name


def test_provider_validate_with_key():
    p = ClaudeProvider(api_key="key123")
    assert p.validate() is True


def test_provider_validate_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = ClaudeProvider(api_key=None)
    assert p.validate() is False


def test_complete_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = OpenAIProvider(api_key=None)
    with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
        p.complete(LLMRequest(system="s", user="u"))


def test_claude_stub_completion():
    p = ClaudeProvider(api_key="dummy")
    resp = p.complete(LLMRequest(system="sys", user="prompt"))
    assert isinstance(resp, LLMResponse)
    assert resp.provider == "claude"
    assert "claude-opus-4-7" in resp.model
    assert resp.text.startswith("[claude:")


def test_openai_stub_completion():
    p = OpenAIProvider(api_key="dummy")
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.provider == "openai"
    assert resp.model == "gpt-4o"


def test_gemini_stub_completion():
    p = GeminiProvider(api_key="dummy")
    resp = p.complete(LLMRequest(system="s", user="u"))
    assert resp.provider == "gemini"


def test_provider_model_override():
    p = ClaudeProvider(api_key="dummy")
    resp = p.complete(LLMRequest(system="s", user="u"), model="claude-haiku-4-5-20251001")
    assert resp.model == "claude-haiku-4-5-20251001"


def test_llm_request_immutable():
    req = LLMRequest(system="s", user="u")
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        req.user = "tampered"


def test_registry_register_and_get():
    reg = ProviderRegistry()
    reg.register(ClaudeProvider(api_key="d"))
    p = reg.get("claude")
    assert p.name == "claude"


def test_registry_duplicate_rejected():
    reg = ProviderRegistry()
    reg.register(ClaudeProvider(api_key="d"))
    with pytest.raises(ValueError, match="already registered"):
        reg.register(ClaudeProvider(api_key="d"))


def test_registry_unknown_provider():
    reg = ProviderRegistry()
    with pytest.raises(KeyError, match="No provider"):
        reg.get("anthropic-deprecated")


def test_registry_names():
    reg = ProviderRegistry()
    reg.register(ClaudeProvider(api_key="d"))
    reg.register(OpenAIProvider(api_key="d"))
    reg.register(GeminiProvider(api_key="d"))
    assert reg.names() == ["claude", "gemini", "openai"]


def test_default_registry_has_three_providers():
    reg = get_default_registry()
    assert reg.has("claude")
    assert reg.has("openai")
    assert reg.has("gemini")
    assert len(reg.names()) == 3


def test_protocol_compliance():
    """All providers satisfy LLMProvider Protocol via duck-typing (name + complete + validate)."""
    for cls in (ClaudeProvider, OpenAIProvider, GeminiProvider):
        p = cls(api_key="d")
        assert hasattr(p, "name")
        assert hasattr(p, "complete")
        assert hasattr(p, "validate")
        _: LLMProvider = p  # static shape check
