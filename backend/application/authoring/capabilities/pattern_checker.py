"""Capability 7 — Pattern Checker (Opus, HARD tier).

Round 6 greenfield. Sits between cap 6 (option_proposer) and cap 8 (naming):
checks whether the user-accepted OntologyOption is consistent with patterns
already settled elsewhere in the ontology, before names are locked in.

This is **ontology-vs-ontology** consistency — distinct from cap 5
(gap_detector, which is code-vs-domain).

Public API:
    check_pattern(
        hypothesis, accepted_option, *, session_id, turn_no, event_pump=None
    ) -> PatternCheck
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
from backend.application.authoring.capabilities.hypothesis import EntityHypothesis
from backend.application.authoring.capabilities.option_proposer import OntologyOption
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "pattern_checker"
TIER = ModelTier.HARD
TOOL_BUDGET = 6  # cap 7 max_calls (HTML §3 권장 = ontology-only, narrow)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "pattern_check.md"


# ── Output schema ────────────────────────────────────────────────────


PatternDimension = Literal[
    "composition_pattern",
    "naming_convention",
    "domain_grouping",
    "facet_consistency",
    "inheritance_pattern",
]
PatternAlignment = Literal["matches", "deviates", "neutral"]
PatternSeverity = Literal["info", "warn", "block"]
PatternRecommendation = Literal[
    "그대로 진행",
    "옵션 재고려",
    "사용자 의견 필요",
]


class PatternFinding(BaseModel):
    id: str = Field(..., description="snake_case unique within this check")
    dimension: PatternDimension
    alignment: PatternAlignment
    title: str = Field(..., description="Korean ≤80 chars")
    evidence_existing: str = Field(..., description="Korean — cite existing term FQN(s)")
    evidence_proposed: str = Field(..., description="Korean — what proposal does")
    severity: PatternSeverity
    suggestion: str = Field(..., description="1-2 Korean sentences")


class PatternCheck(BaseModel):
    findings: list[PatternFinding] = Field(default_factory=list)
    consistency_score: float = Field(..., ge=0.0, le=1.0)
    summary: str
    recommendation: PatternRecommendation


# ── Cross-entity input (P1a-D) ───────────────────────────────────────


class PriorEntitySnapshot(BaseModel):
    """Compact summary of a previously-completed entity within the SAME
    authoring session. Lets cap 7 detect patterns inside the current
    session — not just against persisted ontology in DB.

    Pushed by frontend whenever the user clicks `⤳ 다음 Entity` (P1a-A).
    Persisted-or-not doesn't matter; the in-session decision is itself a
    pattern signal stronger than DB ontology (most recent intent).
    """

    class_name: str = Field(..., description="JPO class name e.g. HrPlantJpo")
    candidate_term_korean: str
    candidate_term_english: str
    domain_role: str  # equipment / standard / rule_table / lookup_table / ...
    accepted_option_name: str | None = None
    accepted_option_structure: str | None = None  # structure_sketch (≤ 6 lines)
    accepted_option_alignment: str | None = None  # high / medium / low
    persisted_fqns: list[str] = Field(default_factory=list)
    archive_summary: str | None = None


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, PatternCheck]:
    return Agent(
        get_authoring_model(TIER),
        output_type=PatternCheck,
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


def _format_for_prompt(
    hypothesis: EntityHypothesis,
    accepted_option: OntologyOption,
    prior_session_entities: list[PriorEntitySnapshot] | None,
) -> str:
    lines: list[str] = ["# Entity hypothesis"]
    lines.append(f"표시명: {hypothesis.candidate_term_korean}")
    lines.append(f"식별자: {hypothesis.candidate_term_english}")
    lines.append(f"domain_role: {hypothesis.domain_role}")
    lines.append(f"confidence: {hypothesis.confidence:.2f}")
    lines.append(f"PK 의미: {hypothesis.pk_role_summary}")
    if hypothesis.relations_hint:
        lines.append("관계 단서: " + " | ".join(hypothesis.relations_hint))

    lines.append("\n# User-accepted option (cap 6 결과)")
    lines.append(f"id: {accepted_option.id}")
    lines.append(f"name: {accepted_option.name}")
    lines.append(f"description: {accepted_option.description}")
    lines.append(f"structure_sketch:\n{accepted_option.structure_sketch}")
    lines.append(f"entities_count_hint: {accepted_option.entities_count_hint}")
    lines.append(f"domain_alignment: {accepted_option.domain_alignment}")
    if accepted_option.pros:
        lines.append("pros:")
        for p in accepted_option.pros:
            lines.append(f"  - {p}")
    if accepted_option.cons:
        lines.append("cons:")
        for c in accepted_option.cons:
            lines.append(f"  - {c}")

    # P1a-D: in-session prior entities — strongest pattern signal.
    if prior_session_entities:
        lines.append("\n# Prior entities completed THIS SESSION (in-session 패턴)")
        lines.append(
            "[중요] 아래 항목은 이번 세션에서 사용자가 방금 결정한 entity 들 — DB 영속화"
            " 여부와 무관하게 가장 신선한 패턴 신호. 새 entity 가 이들과 합치하는지 우선 검사."
        )
        for i, e in enumerate(prior_session_entities, start=1):
            lines.append(f"\n## Prior #{i} — {e.class_name}")
            lines.append(f"  표시명: {e.candidate_term_korean}")
            lines.append(f"  식별자: {e.candidate_term_english}")
            lines.append(f"  domain_role: {e.domain_role}")
            if e.accepted_option_name:
                lines.append(f"  채택 옵션: {e.accepted_option_name}")
            if e.accepted_option_structure:
                lines.append(f"  구조: {e.accepted_option_structure}")
            if e.accepted_option_alignment:
                lines.append(f"  alignment: {e.accepted_option_alignment}")
            if e.persisted_fqns:
                lines.append(f"  persisted: {', '.join(e.persisted_fqns[:5])}"
                             + (f" (+{len(e.persisted_fqns)-5} 개)" if len(e.persisted_fqns) > 5 else ""))
            if e.archive_summary:
                lines.append(f"  archive 요약: {e.archive_summary[:300]}")

    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────


async def check_pattern(
    hypothesis: EntityHypothesis,
    accepted_option: OntologyOption,
    *,
    session_id: str,
    turn_no: int,
    prior_session_entities: list[PriorEntitySnapshot] | None = None,
    event_pump: ToolEventPump | None = None,
) -> PatternCheck:
    """Compare the proposed shape against (a) persisted ontology patterns
    and (b) entities completed earlier in the same session.

    Empty `findings` is a valid (and common) output — when the ontology is
    cold-start or the proposal aligns cleanly. Uses ontology-only tools
    (PRESET `authoring_pattern_check`, max 6 calls).

    `prior_session_entities` (P1a-D): in-session completed entities. The
    prompt instructs the agent to weigh these as the strongest pattern
    signal — they're the user's most recent intent regardless of DB
    persistence.
    """
    user_prompt = _format_for_prompt(hypothesis, accepted_option, prior_session_entities)

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
        reflect_every=5,
    )
    op_session = AuthoringOperationalSession(
        session_id=session_id, turn_no=turn_no, capability=CAPABILITY_NAME
    )
    register_tools(
        agent,
        allowed=PRESETS["authoring_pattern_check"],
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
        "authoring.pattern_checker session=%s turn=%d tool_calls=%d/%d findings=%d score=%.2f",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
        len(result.output.findings),
        result.output.consistency_score,
    )
    return result.output


def reset_caches() -> None:
    _system_prompt.cache_clear()
