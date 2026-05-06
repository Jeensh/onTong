"""Authoring AI — 2-tier LLM router (Opus + Sonnet).

Round 5 Step 15 decision: capability is tagged HARD or STANDARD.
HARD     → Opus 4.7  — hypothesis / option trade-off / gap detection / re-recommend
STANDARD → Sonnet 4.6 — extraction / answer absorption / interview / pattern check / archive / naming

This module reuses the existing `_build_anthropic` machinery from
`backend.application.agent.llm_factory` rather than duplicating the
provider wiring. The split-out cache here is per-tier.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.application.agent.llm_factory import _build_anthropic, _parse_model_string
from backend.application.authoring.schemas import ModelTier
from backend.core.config import settings

logger = logging.getLogger(__name__)


_cache: dict[ModelTier, Any] = {}


def get_authoring_model(tier: ModelTier) -> Any:
    """Return a cached pydantic_ai Model instance for the requested tier.

    Lazy: first call builds and caches; subsequent calls reuse.
    """
    cached = _cache.get(tier)
    if cached is not None:
        return cached

    model_id = get_model_id(tier)
    provider, model_name = _parse_model_string(model_id)
    if provider != "anthropic":
        # 2-tier routing assumes Anthropic models. Fail loud so misconfiguration
        # surfaces immediately rather than silently falling back.
        raise ValueError(
            f"Authoring tier {tier.value!r} expects an Anthropic model, "
            f"got provider {provider!r} (model_id={model_id!r}). "
            f"Set AUTHORING_OPUS_MODEL / AUTHORING_SONNET_MODEL."
        )

    instance = _build_anthropic(model_name)
    _cache[tier] = instance
    logger.info("authoring.llm_router built tier=%s model=%s", tier.value, model_id)
    return instance


def get_model_id(tier: ModelTier) -> str:
    """Return the configured 'provider/model' string for a tier."""
    if tier is ModelTier.HARD:
        return settings.authoring_opus_model
    if tier is ModelTier.STANDARD:
        return settings.authoring_sonnet_model
    raise ValueError(f"Unknown ModelTier: {tier!r}")


def reset_cache() -> None:
    """Test helper — drop cached model instances so a reconfigured settings
    object takes effect on the next call."""
    _cache.clear()
