"""Capability 11 — Next Entity Picker (Sonnet, STANDARD tier).

Given the JPOs already completed in this session, recommends 3-5 next
candidate JPOs from the same repository with concrete reasoning grounded
in the Code+Ontology graph.

Triggered automatically after the user clicks "⤳ 다음 Entity" (P1a-A) so
they don't have to manually pick from the file tree.

Public API:
    pick_next_entity(req, *, session_id, turn_no, event_pump=None) -> NextEntityRecommendation
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModelSettings

from backend.application.agent_tools import RunTracker, ToolEventPump, register_tools
from backend.application.agent_tools.registry import PRESETS
from backend.application.agent_tools.tracking import usage_limits_for
from backend.application.authoring import cost as cost_mod
from backend.application.authoring.agent_tool_adapter import (
    AuthoringOperationalSession,
    AuthoringToolLogger,
)
from backend.application.authoring.capabilities.code_extractor import _usage_from_result
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "next_entity"
TIER = ModelTier.STANDARD
TOOL_BUDGET = 6

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "next_entity.md"


# ── Schemas ──────────────────────────────────────────────────────────


NextEntitySignal = Literal[
    "pk_overlap",
    "same_package",
    "uncovered_domain",
    "frequent_caller",
    "inheritance_chain",
]


class NextEntityCandidate(BaseModel):
    fqn: str = Field(..., min_length=1)
    simple_name: str = Field(..., min_length=1)
    reason_korean: str = Field(..., description="1-2 Korean sentences citing evidence")
    signal: NextEntitySignal
    confidence: float = Field(..., ge=0.0, le=1.0)


class NextEntityRecommendation(BaseModel):
    candidates: list[NextEntityCandidate] = Field(..., min_length=0, max_length=8)
    summary_korean: str


class NextEntityRequest(BaseModel):
    """Caller-facing input. `repo_id` scopes the search; the prior fqns
    seed the graph reasoning."""

    repo_id: str
    completed_entity_fqns: list[str] = Field(default_factory=list)
    confirmed_term_fqns: list[str] = Field(default_factory=list)


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, NextEntityRecommendation]:
    return Agent(
        get_authoring_model(TIER),
        output_type=NextEntityRecommendation,
        system_prompt=_system_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _settings() -> AnthropicModelSettings:
    return AnthropicModelSettings(anthropic_cache_instructions=True)


def _make_combined_logger(*loggers):
    def combined(record):
        for log in loggers:
            if log is not None:
                log(record)
    return combined


def _format_for_prompt(req: NextEntityRequest) -> str:
    lines = [f"# Repository: {req.repo_id}"]
    if req.completed_entity_fqns:
        lines.append("\n# Already completed THIS SESSION (do not recommend these)")
        for f in req.completed_entity_fqns:
            lines.append(f"  - {f}")
    else:
        lines.append("\n# (no prior entities — fall back to "
                     "find_in_same_package / domain_search)")
    if req.confirmed_term_fqns:
        lines.append("\n# Confirmed terms (persisted to ontology this session)")
        for t in req.confirmed_term_fqns[:10]:
            lines.append(f"  - {t}")
    lines.append(
        "\n# Task\nRecommend 3-5 JPO candidates with reason + signal + confidence."
    )
    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────


# `authoring_pick_next` PRESET will be registered in registry.py.
async def pick_next_entity(
    req: NextEntityRequest,
    *,
    session_id: str,
    turn_no: int,
    event_pump: ToolEventPump | None = None,
) -> NextEntityRecommendation:
    """Recommend next JPO candidates for this session.

    Returns at most 8 candidates (the schema cap); the prompt asks for 3-5.
    Tool-driven — the agent must cite concrete graph evidence for each pick.
    """
    user_prompt = _format_for_prompt(req)

    agent = _build_agent()
    db_logger = AuthoringToolLogger(
        session_id=session_id, turn_no=turn_no, capability=CAPABILITY_NAME
    )
    tracker = RunTracker(
        max_calls=TOOL_BUDGET,
        logger_fn=_make_combined_logger(
            db_logger, event_pump.end if event_pump else None
        ),
        start_logger_fn=event_pump.start if event_pump else None,
        reflect_every=None,  # short task, no reflection beats needed
    )
    op_session = AuthoringOperationalSession(
        session_id=session_id, turn_no=turn_no, capability=CAPABILITY_NAME
    )
    register_tools(
        agent,
        allowed=PRESETS["authoring_pick_next"],
        tracker=tracker,
        operational_session=op_session,
    )

    with cost_mod.measure() as t:
        result = await agent.run(
            user_prompt,
            model_settings=_settings(),
            usage_limits=usage_limits_for(TOOL_BUDGET),
        )

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
    logger.info(
        "authoring.next_entity session=%s turn=%d tool_calls=%d/%d candidates=%d",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
        len(result.output.candidates),
    )
    return result.output


def reset_caches() -> None:
    _system_prompt.cache_clear()
