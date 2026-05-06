"""Authoring AI — core Pydantic schemas.

Foundational types used by the LLM router, cost logger, and capability outputs.
Capability-specific schemas live in capabilities/<name>.py and import ModelTier from here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ── Model tier ───────────────────────────────────────────────────────


class ModelTier(str, Enum):
    """2-tier routing decided in Round 5 Step 15.

    HARD     — Opus 4.7 — hypothesis / option trade-off / gap detection / re-recommend
    STANDARD — Sonnet 4.6 — extraction / answer absorption / interview gen / pattern check / archive / naming
    """

    HARD = "hard"
    STANDARD = "standard"


# ── Token + cost ──────────────────────────────────────────────────────


class TokenUsage(BaseModel):
    """Raw token counts as reported by the provider."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0  # prompt cache hits (90% cheaper)
    cache_write_tokens: int = 0  # prompt cache writes (25% premium)


class CostRecord(BaseModel):
    """One LLM call's cost + metadata. Persisted in S5 (authoring_cost_log)."""

    session_id: str
    turn_no: int
    capability: str  # e.g. "hypothesis", "code_extractor"
    tier: ModelTier
    model_id: str  # full provider/model string
    usage: TokenUsage
    cost_usd: float = Field(..., description="Computed cost in USD")
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cache_hit: bool = False  # heuristic — did this turn benefit from prompt cache?


# ── Pricing (Claude 4.x family, USD per million tokens) ───────────────
# Source: Anthropic public pricing as of 2026-05.
# Cache write = +25% over base input; cache read = ~10% of base input.

PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-opus-4-7": {
        "input": 15.0,
        "output": 75.0,
        "cache_write": 18.75,
        "cache_read": 1.50,
    },
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-haiku-4-5": {  # not used in 2-tier, kept for reference
        "input": 0.80,
        "output": 4.0,
        "cache_write": 1.0,
        "cache_read": 0.08,
    },
}


def estimate_cost_usd(model_short: str, usage: TokenUsage) -> float:
    """Compute USD cost for a single call.

    `model_short` is the bare model name without provider prefix
    (e.g. "claude-opus-4-7"). Unknown models fall back to Sonnet pricing
    so we never silently crash — a warning is logged at the call site.
    """
    rate = PRICING_USD_PER_MTOK.get(model_short, PRICING_USD_PER_MTOK["claude-sonnet-4-6"])
    cost = (
        usage.input_tokens * rate["input"]
        + usage.output_tokens * rate["output"]
        + usage.cache_write_tokens * rate["cache_write"]
        + usage.cache_read_tokens * rate["cache_read"]
    ) / 1_000_000.0
    return round(cost, 6)


# ── Caching policy (per Round 5 Step 15 axis 2) ──────────────────────


class CachePolicy(BaseModel):
    """How a capability should leverage Anthropic prompt caching.

    Round 5 Step 17 §12.3 layered cache:
      - Layer 1 (global): code metadata, pattern library, system prompt
      - Layer 2 (branch): branch interview history
      - Layer 3 (turn): direct prior turn (short TTL)
    """

    cache_instructions: bool = True  # cache the system prompt (Layer 1)
    cache_tools: bool = False  # cache tool definitions (Layer 1, when applicable)
    cache_messages: bool = False  # cache message history (Layer 2/3)
    ttl: Literal["5m", "1h"] = "5m"  # Anthropic supports 5min and 1hr TTLs
