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
from backend.application.authoring.capabilities.action_extractor import (
    ExtractedAction,
)
from backend.application.authoring.capabilities.code_extractor import (
    ExtractedJpo,
    _usage_from_result,
)
from backend.application.authoring.capabilities.service_extractor import (
    ExtractedService,
)
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "hypothesis"
TIER = ModelTier.HARD
TOOL_BUDGET = 8  # cap 2 max_calls (HTML §3 권장)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_PROMPT_PATH = _PROMPTS_DIR / "hypothesis.md"
_SERVICE_PROMPT_PATH = _PROMPTS_DIR / "service_hypothesis.md"
_ACTION_PROMPT_PATH = _PROMPTS_DIR / "action_hypothesis.md"


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
    """First-cut hypothesis for one JPO. The user will confirm/refine in Step 14 ⓒ patterns.

    `kind="entity"` discriminator added in Phase C-2 so this can join the
    Hypothesis union with ServiceHypothesis / ActionHypothesis.
    """

    kind: Literal["entity"] = "entity"
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


# ── Service hypothesis (Phase C-2) ────────────────────────────────────


ServiceDomainRole = Literal[
    "orchestrator",
    "rest_facade",
    "domain_service",
    "data_access",
    "event_consumer",
    "scheduled_job",
    "infrastructure_adapter",
    "unknown",
]


class CollaboratorNote(BaseModel):
    """One-line interpretation of a dependency's role in this Service."""

    dependency: str = Field(..., description="Field/param name as appears in the Service")
    interpreted_role: str = Field(..., description='One-line meaning, e.g. "주문 영속화 담당"')


class ServiceUseCase(BaseModel):
    """One key method on the Service worth elevating into a Use-Case narrative."""

    method_name: str
    summary_korean: str = Field(..., description="1–2 sentences in Korean: what business problem this solves")
    triggers: str | None = Field(
        None,
        description='Who/what triggers this method (REST endpoint / event listener / scheduled / called by Y)',
    )


class ServiceHypothesis(BaseModel):
    """First-cut hypothesis for a Spring Service-layer class.

    Focus: what business responsibility this class owns, who it collaborates
    with, where the write boundary sits. Downstream Action extraction can
    then drill into specific methods.
    """

    kind: Literal["service"] = "service"
    candidate_capability_korean: str = Field(..., description='Display name, e.g. "주문 생성 서비스"')
    candidate_capability_english: str = Field(..., description='PascalCase id, e.g. "OrderCreation"')
    service_role: ServiceDomainRole
    responsibility_summary: str = Field(..., description="2–3 sentences in Korean: what this class is responsible for")
    collaborator_notes: list[CollaboratorNote] = Field(default_factory=list)
    write_boundary_summary: str | None = Field(
        None,
        description='Plain Korean: which methods cross the write boundary and what they mutate',
    )
    key_use_cases: list[ServiceUseCase] = Field(default_factory=list)
    domain_questions: list[str] = Field(
        default_factory=list,
        description="3–5 short interview questions to validate the hypothesis",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


# ── Action hypothesis (Phase C-2) ─────────────────────────────────────


ActionKindGuess = Literal["pure_function", "effectful", "workflow", "unknown"]


class ActionParamMeaning(BaseModel):
    """One-line interpretation of an Action's parameter."""

    param_name: str
    interpreted_meaning_korean: str = Field(..., description='Domain meaning, e.g. "주문 수량"')


class ActionBrCandidate(BaseModel):
    """Hint at a BusinessRule the body seems to enforce."""

    statement_korean: str = Field(..., description="What rule the body appears to enforce, in Korean")
    severity_guess: Literal["hard", "soft", "unknown"] = "unknown"
    anchor_locator_hint: str | None = Field(
        None,
        description='Body anchor that backs this BR, e.g. "if-stmt@line-42"',
    )


class ActionHypothesis(BaseModel):
    """First-cut hypothesis for a single Java method analysed as an Action."""

    kind: Literal["action"] = "action"
    domain_verb_korean: str = Field(..., description='Domain verb in Korean, e.g. "주문 생성"')
    domain_verb_english: str = Field(..., description='PascalCase verb, e.g. "CreateOrder"')
    action_kind_guess: ActionKindGuess
    input_meanings: list[ActionParamMeaning] = Field(default_factory=list)
    output_meaning_korean: str | None = None
    preconditions_korean: list[str] = Field(default_factory=list)
    postconditions_korean: list[str] = Field(default_factory=list)
    br_candidates: list[ActionBrCandidate] = Field(default_factory=list)
    domain_questions: list[str] = Field(
        default_factory=list,
        description="3–5 short interview questions to validate the hypothesis",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


# ── Union of hypothesis kinds (Phase C-2) ─────────────────────────────


from typing import Annotated, Union  # noqa: E402

Hypothesis = Annotated[
    Union[EntityHypothesis, ServiceHypothesis, ActionHypothesis],
    Field(discriminator="kind"),
]


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=4)
def _load_prompt(path_str: str) -> str:
    return Path(path_str).read_text(encoding="utf-8")


def _system_prompt() -> str:
    return _load_prompt(str(_PROMPT_PATH))


def _service_prompt() -> str:
    return _load_prompt(str(_SERVICE_PROMPT_PATH))


def _action_prompt() -> str:
    return _load_prompt(str(_ACTION_PROMPT_PATH))


def _build_agent() -> Agent[None, EntityHypothesis]:
    return Agent(
        get_authoring_model(TIER),
        output_type=EntityHypothesis,
        system_prompt=_system_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _build_service_agent() -> Agent[None, ServiceHypothesis]:
    return Agent(
        get_authoring_model(TIER),
        output_type=ServiceHypothesis,
        system_prompt=_service_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _build_action_agent() -> Agent[None, ActionHypothesis]:
    # Action hypothesis runs against a single method's extracted shape —
    # less graph reasoning than Service, so STANDARD tier suffices.
    return Agent(
        get_authoring_model(ModelTier.STANDARD),
        output_type=ActionHypothesis,
        system_prompt=_action_prompt(),
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


def _format_service_for_prompt(svc: ExtractedService) -> str:
    """Render ExtractedService as a structured text block for the hypothesis LLM."""
    lines: list[str] = []
    lines.append(f"# Spring Service-layer class: {svc.package}.{svc.class_name}")
    if svc.class_annotations:
        lines.append("Class annotations: " + ", ".join(svc.class_annotations))
    if svc.class_docstring:
        lines.append("\n## Class Javadoc (verbatim)")
        lines.append(svc.class_docstring.strip())

    if svc.dependencies:
        lines.append("\n## Dependencies (collaborators)")
        for d in svc.dependencies:
            tag = " [repository]" if d.is_repository else ""
            lines.append(
                f"  - {d.field_name}: {d.type_simple} ({d.injection_style}){tag}"
            )

    if svc.exposed_methods:
        lines.append("\n## Exposed methods")
        for m in svc.exposed_methods:
            tx_tag = " [@Transactional]" if m.is_transactional else ""
            ann = " ".join(m.annotations) if m.annotations else ""
            params = ", ".join(m.params)
            line = f"  - {m.name}({params}) → {m.return_type}{tx_tag}"
            if ann:
                line += f"   {ann}"
            lines.append(line)
            if m.javadoc_first_line:
                lines.append(f"      // {m.javadoc_first_line}")

    if svc.transaction_boundary_methods:
        lines.append("\n## Write-boundary methods (non-readOnly @Transactional)")
        for name in svc.transaction_boundary_methods:
            lines.append(f"  - {name}")

    if svc.rest_endpoints:
        lines.append("\n## REST endpoints")
        for ep in svc.rest_endpoints:
            lines.append(f"  - {ep.http_method} {ep.path}  → {ep.handler_method}")

    if svc.publishes_events:
        lines.append("\n## Events published")
        for ev in svc.publishes_events:
            lines.append(f"  - {ev}")

    return "\n".join(lines)


def _format_action_for_prompt(act: ExtractedAction) -> str:
    """Render ExtractedAction (method-level) as a structured text block."""
    lines: list[str] = []
    lines.append(f"# Java method as Action candidate")
    lines.append(f"Enclosing class FQN: {act.enclosing_class_fqn}")
    lines.append(f"Method name: {act.method_name}")
    if act.method_annotations:
        lines.append("Annotations: " + " ".join(act.method_annotations))
    if act.javadoc:
        lines.append("\n## Javadoc (verbatim)")
        lines.append(act.javadoc.strip())

    if act.params:
        lines.append("\n## Parameters")
        for p in act.params:
            hint = f"   // {p.domain_meaning_hint}" if p.domain_meaning_hint else ""
            lines.append(f"  - {p.name}: {p.type_simple}{hint}")
    lines.append(f"\nReturn: {act.return_type}")
    if act.return_meaning_hint:
        lines.append(f"  // {act.return_meaning_hint}")

    if act.callees:
        lines.append("\n## Callees")
        for c in act.callees:
            tag = []
            if c.is_repository_call:
                tag.append("repo")
            if c.is_external_call:
                tag.append("external")
            t = f" [{', '.join(tag)}]" if tag else ""
            lines.append(f"  - {c.receiver_type}.{c.method_name}(){t}")

    if act.side_effects:
        lines.append("\n## Side effects")
        for e in act.side_effects:
            lines.append(f"  - {e.op}: {e.target_hint}")

    if act.anchors_hint:
        lines.append("\n## Anchor candidates (locator, note)")
        for a in act.anchors_hint:
            line = f"  - {a.locator}"
            if a.line is not None:
                line += f" @L{a.line}"
            if a.note:
                line += f"   // {a.note}"
            lines.append(line)

    if act.is_idempotent_guess is not None:
        lines.append(f"\nIdempotency guess (extraction): {act.is_idempotent_guess}")

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


async def propose_service_hypothesis(
    svc: ExtractedService,
    *,
    session_id: str,
    turn_no: int,
    user_comment: str | None = None,
    event_pump: ToolEventPump | None = None,
) -> ServiceHypothesis:
    """Propose a first-cut Service hypothesis. HARD tier — Service shape needs
    dependency-graph reasoning the lighter model handles inconsistently."""
    user_prompt = _format_service_for_prompt(svc)
    if user_comment and user_comment.strip():
        user_prompt += (
            "\n\n# 사용자 정정·추가 (이전 가설을 다듬어주세요)\n"
            + user_comment.strip()
        )

    agent = _build_service_agent()
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
        "authoring.service_hypothesis session=%s turn=%d tool_calls=%d/%d",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
    )
    return result.output


async def propose_action_hypothesis(
    act: ExtractedAction,
    *,
    session_id: str,
    turn_no: int,
    user_comment: str | None = None,
    event_pump: ToolEventPump | None = None,
) -> ActionHypothesis:
    """Propose a first-cut Action hypothesis. STANDARD tier — analysing one
    method body is mechanical compared to dependency-graph reasoning."""
    user_prompt = _format_action_for_prompt(act)
    if user_comment and user_comment.strip():
        user_prompt += (
            "\n\n# 사용자 정정·추가 (이전 가설을 다듬어주세요)\n"
            + user_comment.strip()
        )

    agent = _build_action_agent()
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
        tier=ModelTier.STANDARD,
        model_id=get_model_id(ModelTier.STANDARD),
        usage=usage,
        duration_ms=t["elapsed_ms"],
    )
    logger.info(
        "authoring.action_hypothesis session=%s turn=%d tool_calls=%d/%d",
        session_id,
        turn_no,
        tracker.calls,
        TOOL_BUDGET,
    )
    return result.output


async def propose_hypothesis(
    extracted: ExtractedJpo | ExtractedService | ExtractedAction,
    *,
    session_id: str,
    turn_no: int,
    user_comment: str | None = None,
    event_pump: ToolEventPump | None = None,
) -> Hypothesis:
    """Kind-aware dispatcher. Routes one extraction output to the matching
    hypothesis capability. ExtractedGenericClass is NOT supported — hypothesis
    requires a structured shape; pick a Service/JPO extraction or wait for
    the user to drill into a method (Action) instead.

    Phase C-2 — Action input arrives via a separate endpoint (method-pick UI
    lands in C-4); this dispatcher still accepts it so backend callers stay
    uniform.
    """
    if extracted.kind == "jpo":
        return await propose_entity_hypothesis(
            extracted,
            session_id=session_id,
            turn_no=turn_no,
            user_comment=user_comment,
            event_pump=event_pump,
        )
    if extracted.kind == "service":
        return await propose_service_hypothesis(
            extracted,
            session_id=session_id,
            turn_no=turn_no,
            user_comment=user_comment,
            event_pump=event_pump,
        )
    if extracted.kind == "action":
        return await propose_action_hypothesis(
            extracted,
            session_id=session_id,
            turn_no=turn_no,
            user_comment=user_comment,
            event_pump=event_pump,
        )
    raise ValueError(f"Unsupported extracted.kind for hypothesis: {extracted.kind!r}")


def reset_caches() -> None:
    _load_prompt.cache_clear()
