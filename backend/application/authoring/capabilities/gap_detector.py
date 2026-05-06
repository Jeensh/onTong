"""Capability 5 — Gap Detector (Opus, HARD tier).

Round 5 Step 11 §1 (4 gap kinds: structure / consistency / intent / historical).

Inspects code (ExtractedJpo) vs domain (EntityHypothesis + AbsorbedAnswers)
and surfaces concrete mismatches. False positives are explicitly disallowed
in the prompt — empty `gaps` is a valid output.

Public API:
    detect_gaps(jpo, hypothesis, answers, *, session_id, turn_no) -> GapAnalysis
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
from backend.application.authoring.capabilities.answer_absorber import AbsorbedAnswers
from backend.application.authoring.capabilities.code_extractor import (
    ExtractedJpo,
    _usage_from_result,
)
from backend.application.authoring.capabilities.hypothesis import EntityHypothesis
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "gap_detector"
TIER = ModelTier.HARD
TOOL_BUDGET = 12  # cap 5 max_calls (HTML §3 권장 = full graph access)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "gap_detection.md"


# ── Output schema ────────────────────────────────────────────────────


GapKind = Literal["structure", "consistency", "intent", "historical"]
GapSeverity = Literal["high", "medium", "low"]
GapResolution = Literal[
    "simplification_note",  # code is intentional shortcut, leave a mapping note
    "code_fix_scenario",    # ontology is right, code needs change — demo material
    "business_intent",      # the deviation IS the business rule
    "investigate",          # not enough info, ask more
]


class Gap(BaseModel):
    id: str = Field(..., description="snake_case unique within this analysis")
    kind: GapKind
    severity: GapSeverity
    title: str = Field(..., description="Korean, ≤80 chars")
    description: str = Field(..., description="2–3 Korean sentences")
    evidence_code: str = Field(..., description="Korean — quotes the code")
    evidence_domain: str = Field(..., description="Korean — quotes the user")
    recommended_resolution: GapResolution
    resolution_rationale: str = Field(..., description="1–2 Korean sentences")
    demo_potential: bool = False


class GapAnalysis(BaseModel):
    gaps: list[Gap] = Field(default_factory=list)
    severity_summary: str
    blocks_modeling: bool = False
    recommendation: str


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, GapAnalysis]:
    """Per-call agent — needed so each run gets its own tool wrappers
    (closures over RunTracker / session). Cheap because the LLM model
    object is cached upstream by `get_authoring_model(TIER)`."""
    return Agent(
        get_authoring_model(TIER),
        output_type=GapAnalysis,
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
    jpo: ExtractedJpo,
    hypothesis: EntityHypothesis,
    answers: AbsorbedAnswers,
) -> str:
    """Three-block render: JPO + hypothesis + answers."""
    lines: list[str] = ["# Java JPO (code structure)"]
    lines.append(f"package: {jpo.package}")
    lines.append(f"class: {jpo.class_name}")
    lines.append(f"table: {jpo.table_name}")
    if jpo.pk_class:
        lines.append(f"pk_class: {jpo.pk_class}")
    if jpo.class_docstring:
        lines.append(f"class_docstring: {jpo.class_docstring.strip()}")
    if jpo.pk_columns:
        lines.append("pk_columns:")
        for c in jpo.pk_columns:
            tail = f" // {c.comment}" if c.comment else ""
            lines.append(f"  - {c.db_column} ({c.java_type}, java={c.name}){tail}")
    if jpo.regular_columns:
        lines.append("regular_columns:")
        for c in jpo.regular_columns:
            tail = f" // {c.comment}" if c.comment else ""
            lines.append(f"  - {c.db_column} ({c.java_type}, java={c.name}){tail}")

    lines.append("\n# Entity hypothesis")
    lines.append(f"표시명: {hypothesis.candidate_term_korean}")
    lines.append(f"식별자: {hypothesis.candidate_term_english}")
    lines.append(f"domain_role: {hypothesis.domain_role}")
    lines.append(f"confidence: {hypothesis.confidence:.2f}")
    lines.append(f"PK 의미: {hypothesis.pk_role_summary}")
    if hypothesis.assumptions:
        lines.append("assumptions:")
        for a in hypothesis.assumptions:
            lines.append(f"  - {a}")
    if hypothesis.concerns:
        lines.append("concerns:")
        for c in hypothesis.concerns:
            lines.append(f"  - {c}")

    lines.append("\n# User answers (per question)")
    for qid, ans in answers.per_question.items():
        if ans.is_unknown:
            lines.append(f"  - {qid}: (모름)")
            continue
        bits = [f"  - {qid}: {ans.normalized}"]
        if ans.raw_text and ans.raw_text != ans.normalized:
            bits.append(f"raw='{ans.raw_text}'")
        if ans.contradicts_my_guess:
            bits.append(f"[CONTRADICTS my_guess: {ans.contradicts_note}]")
        lines.append(" ".join(bits))

    if answers.emergent_facts:
        lines.append("\n# Emergent facts (사용자가 추가로 알려준 것)")
        for f in answers.emergent_facts:
            lines.append(f"  - {f}")

    if answers.contradictions:
        lines.append("\n# Contradictions (가설 vs 사용자)")
        for c in answers.contradictions:
            lines.append(f"  - {c}")

    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────


async def detect_gaps(
    jpo: ExtractedJpo,
    hypothesis: EntityHypothesis,
    answers: AbsorbedAnswers,
    *,
    session_id: str,
    turn_no: int,
    event_pump: ToolEventPump | None = None,
) -> GapAnalysis:
    """Surface concrete code-vs-domain mismatches.

    May return an empty `gaps` list — false positives destroy trust faster
    than missed gaps. The prompt is calibrated accordingly.

    R6: agent has read-only access to the full Code+Ontology+Mapping graph
    via `agent_tools` (PRESET `authoring_full`, max 12 tool calls). Every
    tool call is persisted to `authoring_tool_call_log` so cap 9 archive
    can render the evidence trail. When `event_pump` is supplied, tool
    start/end events are forwarded to its asyncio queue for SSE streaming.
    """
    user_prompt = _format_for_prompt(jpo, hypothesis, answers)

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
        "authoring.gap_detector session=%s turn=%d tool_calls=%d/%d",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
    )
    return result.output


def reset_caches() -> None:
    _system_prompt.cache_clear()
