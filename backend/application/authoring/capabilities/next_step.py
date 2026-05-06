"""Capability 10 — Next-step Advisor (Sonnet, STANDARD tier).

Reads the current authoring session state (which artifacts exist) and
returns a single recommended next action with a short Korean reason.
This is the only capability that does NOT use the agent_tools graph —
it's a pure policy decision from existing state.

Public API:
    advise_next_step(state, *, session_id, turn_no) -> NextStep
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModelSettings

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities.code_extractor import _usage_from_result
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "next_step"
TIER = ModelTier.STANDARD

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "next_step.md"


# ── Output schema ────────────────────────────────────────────────────


RecommendedAction = Literal[
    "run_interview",
    "submit_answers",
    "run_options",
    "accept_option",
    "run_pattern_check",
    "run_gaps",
    "revise_hypothesis",
    "revise_options",
    "run_naming",
    "run_archive",
    "run_confirm",
    "done",
    "escalate_to_user",
]
Priority = Literal["critical", "recommended", "optional"]


class NextStep(BaseModel):
    recommended_action: RecommendedAction
    reason_korean: str = Field(..., description="1-2 Korean sentences citing state")
    priority: Priority
    alternatives: list[RecommendedAction] = Field(default_factory=list, max_length=2)


# ── State input shape ────────────────────────────────────────────────


class SessionStateSnapshot(BaseModel):
    """Lightweight snapshot of `useAuthoring` state passed by the caller.

    Each field is a flag (whether the artifact exists) plus light meta —
    enough for the advisor to decide. The advisor never sees full hypotheses
    or answers, only their presence + a few signals.
    """

    has_hypothesis: bool = False
    hypothesis_confidence: float | None = None
    has_interview_batch: bool = False
    has_answers: bool = False
    has_option_table: bool = False
    has_accepted_option: bool = False
    has_gaps: bool = False
    gaps_block_modeling: bool = False
    gap_high_count: int = 0
    has_pattern_check: bool = False
    pattern_recommendation: str | None = None  # "그대로 진행" | "옵션 재고려" | "사용자 의견 필요" | None
    has_names: bool = False
    has_archive: bool = False
    persisted_fqn_count: int = 0


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, NextStep]:
    return Agent(
        get_authoring_model(TIER),
        output_type=NextStep,
        system_prompt=_system_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _settings() -> AnthropicModelSettings:
    return AnthropicModelSettings(anthropic_cache_instructions=True)


def _format_for_prompt(state: SessionStateSnapshot) -> str:
    lines = ["# Current session state"]
    lines.append(f"has_hypothesis: {state.has_hypothesis}")
    if state.has_hypothesis:
        lines.append(f"  hypothesis_confidence: {state.hypothesis_confidence}")
    lines.append(f"has_interview_batch: {state.has_interview_batch}")
    lines.append(f"has_answers: {state.has_answers}")
    lines.append(f"has_option_table: {state.has_option_table}")
    lines.append(f"has_accepted_option: {state.has_accepted_option}")
    lines.append(f"has_gaps: {state.has_gaps}")
    if state.has_gaps:
        lines.append(f"  gaps_block_modeling: {state.gaps_block_modeling}")
        lines.append(f"  gap_high_count: {state.gap_high_count}")
    lines.append(f"has_pattern_check: {state.has_pattern_check}")
    if state.has_pattern_check:
        lines.append(f"  pattern_recommendation: {state.pattern_recommendation}")
    lines.append(f"has_names: {state.has_names}")
    lines.append(f"has_archive: {state.has_archive}")
    lines.append(f"persisted_fqn_count: {state.persisted_fqn_count}")
    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────


async def advise_next_step(
    state: SessionStateSnapshot,
    *,
    session_id: str,
    turn_no: int,
) -> NextStep:
    """Recommend the single most appropriate next action."""
    user_prompt = _format_for_prompt(state)

    agent = _build_agent()

    with cost_mod.measure() as t:
        result = await agent.run(user_prompt, model_settings=_settings())

    usage = _usage_from_result(result.usage())
    cost_mod.log_call(
        session_id=session_id,
        turn_no=turn_no,
        capability=CAPABILITY_NAME,
        tier=TIER,
        model_id=get_model_id(TIER),
        usage=usage,
        duration_ms=t["elapsed_ms"],
    )
    return result.output


def reset_caches() -> None:
    _system_prompt.cache_clear()
