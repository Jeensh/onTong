"""Capability 6 — Option Proposer (Opus, HARD tier).

Round 5 Step 13 §1: "모델링 옵션 제시 (A/B/C trade-off + ★ 추천)".

This is the most decisive capability — it converts a hypothesis + the user's
absorbed answers into a 2–4 option decision table mirroring the Round 5
Step 5 / Step 7 / Step 8 / Step 10 patterns.

Public API:
    propose_options(
        hypothesis, answers, *, pattern_library=None, session_id, turn_no
    ) -> OptionTable
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
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
from backend.application.authoring.capabilities.answer_absorber import AbsorbedAnswers
from backend.application.authoring.capabilities.code_extractor import _usage_from_result
from backend.application.authoring.capabilities.hypothesis import EntityHypothesis
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "option_proposer"
TIER = ModelTier.HARD
TOOL_BUDGET = 10  # cap 6 max_calls (HTML §3 권장 = full graph access)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "option_proposal.md"


# ── Output schema ────────────────────────────────────────────────────


DomainAlignment = Literal["high", "medium", "low"]


class OntologyOption(BaseModel):
    id: str = Field(..., description="Short id; snake_case or letter")
    name: str = Field(..., description="Korean name; English suffix OK")
    description: str = Field(..., description="≤3 Korean sentences")
    structure_sketch: str = Field(
        ..., description="Short ASCII sketch of entity shape (≤~6 lines)"
    )
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    entities_count_hint: str
    domain_alignment: DomainAlignment
    trade_offs_one_line: str


class OptionTable(BaseModel):
    title: str
    context_summary: str
    options: list[OntologyOption] = Field(..., min_length=2, max_length=4)
    recommended_id: str
    recommendation_reasoning: str
    caveats: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _recommended_must_match_one_option(self) -> OptionTable:
        ids = {o.id for o in self.options}
        if self.recommended_id not in ids:
            raise ValueError(
                f"recommended_id {self.recommended_id!r} not in options {sorted(ids)}"
            )
        return self


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, OptionTable]:
    return Agent(
        get_authoring_model(TIER),
        output_type=OptionTable,
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
    answers: AbsorbedAnswers,
    pattern_library: list[str] | None,
) -> str:
    """Compact render of hypothesis + answers + (optional) pattern library."""
    lines: list[str] = [
        "# Entity hypothesis",
        f"표시명: {hypothesis.candidate_term_korean}",
        f"식별자: {hypothesis.candidate_term_english}",
        f"domain_role: {hypothesis.domain_role}",
        f"confidence: {hypothesis.confidence:.2f}",
        f"PK 의미: {hypothesis.pk_role_summary}",
    ]
    if hypothesis.relations_hint:
        lines.append("관계 단서: " + " | ".join(hypothesis.relations_hint))
    if hypothesis.concerns:
        lines.append("우려: " + " | ".join(hypothesis.concerns))

    lines.append("\n# User answers (per question)")
    for qid, ans in answers.per_question.items():
        if ans.is_unknown:
            lines.append(f"  - {qid}: (모름 / 답변 없음)")
            continue
        bits = [f"  - {qid}: {ans.normalized}"]
        if ans.picked_option:
            bits.append(f"[picked={ans.picked_option}]")
        if ans.contradicts_my_guess:
            bits.append(f"[CONTRADICTS my_guess: {ans.contradicts_note}]")
        lines.append(" ".join(bits))

    if answers.emergent_facts:
        lines.append("\n# Emergent facts (질문 외에 사용자가 알려준 것)")
        for f in answers.emergent_facts:
            lines.append(f"  - {f}")

    if answers.contradictions:
        lines.append("\n# Contradictions (가설 vs 사용자 답변)")
        for c in answers.contradictions:
            lines.append(f"  - {c}")

    if pattern_library:
        lines.append("\n# Pattern library (이미 결정된 패턴 — 재사용 후보)")
        for p in pattern_library:
            lines.append(f"  - {p}")

    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────


async def propose_options(
    hypothesis: EntityHypothesis,
    answers: AbsorbedAnswers,
    *,
    pattern_library: list[str] | None = None,
    session_id: str,
    turn_no: int,
    user_comment: str | None = None,
    event_pump: ToolEventPump | None = None,
) -> OptionTable:
    """Generate a 2–4 option decision table with a starred recommendation.

    `pattern_library`, when supplied, is a list of short Korean lines
    describing patterns already settled elsewhere in the ontology
    (e.g. "Plant + Constraint Composition (Step 5)"). Pass an empty list
    or None on cold start.

    `user_comment` (R2 / F3): user correction from ✏ 수정 button on a prior
    options card — appended to the prompt so the LLM accounts for it.

    R6: full graph access via `agent_tools` (PRESET `authoring_full`,
    max 10 tool calls). Tool calls are persisted + (when `event_pump` is
    supplied) streamed to SSE.
    """
    user_prompt = _format_for_prompt(hypothesis, answers, pattern_library)
    if user_comment and user_comment.strip():
        user_prompt += (
            "\n\n# 사용자 정정·추가 (이전 옵션을 다듬어주세요)\n"
            + user_comment.strip()
        )

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
        allowed=PRESETS["authoring_full"],
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
        "authoring.option_proposer session=%s turn=%d tool_calls=%d/%d",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
    )
    return result.output


def reset_caches() -> None:
    _system_prompt.cache_clear()
