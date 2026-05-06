"""Capability 2 — Hypothesis (Opus, HARD tier).

Round 5 Step 13 §1: "가설 모델링 (1차 entity 추론)".

Takes the structured output of capability 1 (ExtractedJpo) and proposes a
first-cut domain entity for the human to confirm or refine. This is the
classic "AI 가 가설 먼저 던지기" pattern from Step 14 §C.

Public API:
    propose_entity_hypothesis(jpo, *, session_id, turn_no) -> EntityHypothesis
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
from backend.application.authoring.capabilities.code_extractor import (
    ExtractedJpo,
    _usage_from_result,
)
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "hypothesis"
TIER = ModelTier.HARD
TOOL_BUDGET = 8  # cap 2 max_calls (HTML §3 권장)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "hypothesis.md"


# ── Output schema ────────────────────────────────────────────────────


DomainRole = Literal[
    "equipment",
    "standard",
    "rule_table",
    "lookup_table",
    "transactional",
    "audit_log",
    "unknown",
]


class ColumnNote(BaseModel):
    db_column: str
    note: str = Field(..., description="One-line meaning guess; may quote Korean comment")


class EntityHypothesis(BaseModel):
    """First-cut hypothesis for one JPO. The user will confirm/refine in Step 14 ⓒ patterns."""

    candidate_term_korean: str = Field(..., description='Display name, e.g. "열연공장"')
    candidate_term_english: str = Field(..., description='PascalCase id, e.g. "HrPlant"')
    domain_role: DomainRole
    pk_role_summary: str
    column_notes: list[ColumnNote] = Field(default_factory=list)
    relations_hint: list[str] = Field(default_factory=list)
    domain_questions: list[str] = Field(
        default_factory=list,
        description="3–5 short interview questions to validate the hypothesis",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, EntityHypothesis]:
    return Agent(
        get_authoring_model(TIER),
        output_type=EntityHypothesis,
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


def _format_jpo_for_prompt(jpo: ExtractedJpo) -> str:
    """Render ExtractedJpo as a compact, human-readable block.

    JSON would also work, but a structured text form gives the LLM stronger
    cues about which parts are PK vs regular and which comments belong where.
    """
    lines: list[str] = []
    lines.append(f"# Java JPO: {jpo.package}.{jpo.class_name}")
    lines.append(f"Table: {jpo.table_name}")
    if jpo.pk_class:
        lines.append(f"Composite PK class: {jpo.pk_class}")
    if jpo.class_docstring:
        lines.append("\n## Class Javadoc (verbatim)")
        lines.append(jpo.class_docstring.strip())

    def _col(c, role: str) -> str:
        bits = [f"  - {c.db_column} ({c.java_type})"]
        meta: list[str] = []
        if c.db_length is not None:
            meta.append(f"length={c.db_length}")
        if c.db_precision is not None or c.db_scale is not None:
            meta.append(f"precision={c.db_precision},scale={c.db_scale}")
        if meta:
            bits.append(f"[{', '.join(meta)}]")
        if c.comment:
            bits.append(f"// {c.comment}")
        bits.append(f"({role}, java field: {c.name})")
        return " ".join(bits)

    if jpo.pk_columns:
        lines.append("\n## Composite PK columns (in order)")
        for c in jpo.pk_columns:
            lines.append(_col(c, "PK"))
    if jpo.regular_columns:
        lines.append("\n## Regular columns (in order)")
        for c in jpo.regular_columns:
            lines.append(_col(c, "regular"))
    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────


async def propose_entity_hypothesis(
    jpo: ExtractedJpo,
    *,
    session_id: str,
    turn_no: int,
    user_comment: str | None = None,
    event_pump: ToolEventPump | None = None,
) -> EntityHypothesis:
    """Propose a first-cut entity hypothesis for one extracted JPO.

    R6: agent has access to graph tools (PRESET `authoring_hypothesize`,
    max 8 calls). Replaces the v1 design's "pure function over JPO struct"
    contract — the LLM may now look up sibling JPOs, search ontology for
    duplicates, check existing mappings, and inspect inheritance hierarchy
    before producing the hypothesis. Critical for legacy code without
    javadoc, where graph traversal is the only way to recover meaning.

    `user_comment` (R2 / F3): when the user clicks ✏ 수정 on a previous
    hypothesis card and types a correction, that text is appended to the
    user prompt so the LLM accounts for it on the rerun.
    """
    user_prompt = _format_jpo_for_prompt(jpo)
    if user_comment and user_comment.strip():
        user_prompt += (
            "\n\n# 사용자 정정·추가 (이전 가설을 다듬어주세요)\n"
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
        allowed=PRESETS["authoring_hypothesize"],
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
        "authoring.hypothesis session=%s turn=%d tool_calls=%d/%d",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
    )
    return result.output


def reset_caches() -> None:
    _system_prompt.cache_clear()
