"""S1 unit tests — LLM router + cost logger + schemas.

No live LLM calls — only tier routing, pricing math, and the in-memory
cost buffer. Real call integration is exercised in the capability tests
(S2 onward) under the `integration` marker.
"""

from __future__ import annotations

import pytest

from backend.application.authoring import cost as cost_mod
from backend.application.authoring import llm_router
from backend.application.authoring.schemas import (
    PRICING_USD_PER_MTOK,
    CachePolicy,
    ModelTier,
    TokenUsage,
    estimate_cost_usd,
)


# ── schemas ──────────────────────────────────────────────────────────


def test_model_tier_values():
    assert ModelTier.HARD.value == "hard"
    assert ModelTier.STANDARD.value == "standard"


def test_pricing_table_has_required_models():
    for model in ("claude-opus-4-7", "claude-sonnet-4-6"):
        rate = PRICING_USD_PER_MTOK[model]
        assert {"input", "output", "cache_write", "cache_read"} <= rate.keys()


def test_cost_zero_usage_returns_zero():
    assert estimate_cost_usd("claude-opus-4-7", TokenUsage()) == 0.0


def test_cost_opus_basic():
    # 1M input + 1M output Opus = $15 + $75 = $90
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert estimate_cost_usd("claude-opus-4-7", usage) == 90.0


def test_cost_sonnet_with_cache_hit():
    # Cache read is ~10% of base input → 1M cached read on Sonnet = $0.30
    usage = TokenUsage(cache_read_tokens=1_000_000)
    assert estimate_cost_usd("claude-sonnet-4-6", usage) == 0.30


def test_cost_unknown_model_falls_back_to_sonnet():
    usage = TokenUsage(input_tokens=1_000_000)
    # Falls back to Sonnet: $3
    assert estimate_cost_usd("does-not-exist", usage) == 3.0


def test_cache_policy_defaults():
    cp = CachePolicy()
    assert cp.cache_instructions is True
    assert cp.cache_messages is False
    assert cp.ttl == "5m"


# ── cost logger ──────────────────────────────────────────────────────


def test_log_call_records_and_sums(caplog):
    cost_mod.reset_buffer()
    rec1 = cost_mod.log_call(
        session_id="s1",
        turn_no=1,
        capability="hypothesis",
        tier=ModelTier.HARD,
        model_id="anthropic/claude-opus-4-7",
        usage=TokenUsage(input_tokens=10_000, output_tokens=2_000),
        duration_ms=4321,
    )
    cost_mod.log_call(
        session_id="s1",
        turn_no=2,
        capability="archiver",
        tier=ModelTier.STANDARD,
        model_id="anthropic/claude-sonnet-4-6",
        usage=TokenUsage(input_tokens=5_000, output_tokens=500),
    )
    cost_mod.log_call(
        session_id="other",
        turn_no=1,
        capability="hypothesis",
        tier=ModelTier.HARD,
        model_id="anthropic/claude-opus-4-7",
        usage=TokenUsage(input_tokens=100, output_tokens=10),
    )

    # First call: 10k * $15 + 2k * $75 = $0.15 + $0.15 = $0.30
    assert rec1.cost_usd == pytest.approx(0.30, rel=1e-6)
    # Session "s1" total = 0.30 (Opus) + (5000*3 + 500*15)/1e6 = 0.30 + 0.0225 = 0.3225
    assert cost_mod.session_total_usd("s1") == pytest.approx(0.3225, rel=1e-4)
    # Other session not mixed in
    assert cost_mod.session_records("s1") and len(cost_mod.session_records("s1")) == 2


def test_cache_hit_flag_set_when_cache_read_present():
    cost_mod.reset_buffer()
    rec = cost_mod.log_call(
        session_id="s2",
        turn_no=1,
        capability="hypothesis",
        tier=ModelTier.HARD,
        model_id="anthropic/claude-opus-4-7",
        usage=TokenUsage(input_tokens=100, cache_read_tokens=5_000),
    )
    assert rec.cache_hit is True


def test_measure_context_manager_records_elapsed():
    import time as _t

    with cost_mod.measure() as t:
        _t.sleep(0.01)
    assert "elapsed_ms" in t
    assert t["elapsed_ms"] >= 10


# ── router ───────────────────────────────────────────────────────────


def test_get_model_id_returns_configured_strings():
    assert llm_router.get_model_id(ModelTier.HARD).startswith("anthropic/")
    assert llm_router.get_model_id(ModelTier.STANDARD).startswith("anthropic/")
    assert llm_router.get_model_id(ModelTier.HARD) != llm_router.get_model_id(ModelTier.STANDARD)


def test_get_authoring_model_rejects_non_anthropic(monkeypatch):
    from backend.core.config import settings

    llm_router.reset_cache()
    monkeypatch.setattr(settings, "authoring_opus_model", "openai/gpt-4o", raising=False)
    with pytest.raises(ValueError, match="expects an Anthropic model"):
        llm_router.get_authoring_model(ModelTier.HARD)


def test_get_authoring_model_caches_per_tier(monkeypatch):
    """Two calls for the same tier return the same instance.

    We don't actually hit the network — `_build_anthropic` constructs an
    AnthropicModel object lazily, which is cheap, and we just check identity.
    """
    from backend.core.config import settings

    llm_router.reset_cache()
    # Ensure a sane Anthropic config for the test (key may be empty in CI; the
    # AnthropicModel constructor doesn't call out to the network).
    monkeypatch.setattr(
        settings, "authoring_opus_model", "anthropic/claude-opus-4-7", raising=False
    )
    monkeypatch.setattr(
        settings, "authoring_sonnet_model", "anthropic/claude-sonnet-4-6", raising=False
    )

    a = llm_router.get_authoring_model(ModelTier.HARD)
    b = llm_router.get_authoring_model(ModelTier.HARD)
    assert a is b

    c = llm_router.get_authoring_model(ModelTier.STANDARD)
    assert c is not a
