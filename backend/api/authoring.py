"""Authoring AI REST API.

Endpoints (all under /api/authoring):

  Session admin
    POST   /sessions               — create
    GET    /sessions               — list (filter: operator_id, status)
    GET    /sessions/{id}          — get one
    PATCH  /sessions/{id}          — update focus / status

  History + preview + cost
    GET    /sessions/{id}/decisions — full decision log
    GET    /sessions/{id}/cost      — running cost summary
    GET    /sessions/{id}/preview   — current entity sketch + recent activity

  Capabilities (one endpoint per capability — request/response are typed)
    POST   /sessions/{id}/extract     — code_extractor (Sonnet)
    POST   /sessions/{id}/hypothesize — hypothesis    (Opus)
    POST   /sessions/{id}/interview   — interview     (Sonnet)
    POST   /sessions/{id}/absorb      — answer_absorber (Sonnet)
    POST   /sessions/{id}/options     — option_proposer (Opus)
    POST   /sessions/{id}/gaps        — gap_detector  (Opus)
    POST   /sessions/{id}/naming      — naming        (Sonnet)
    POST   /sessions/{id}/archive     — archiver      (Sonnet + templated md)

  Finalisation
    POST   /sessions/{id}/confirm — persist accepted entities to ontology DB
                                    (reuses DomainLayerStore.upsert_terms)

Each capability call:
  1. Validates the session exists.
  2. Runs the capability (LLM call, cost auto-logged via cost.py).
  3. Records a `authoring_decision_log` row with the capability output.
  4. Returns the typed result.

Confirm:
  - Takes a NamingDecision + the accepted OntologyOption.
  - Maps each EntityName → BusinessTerm and persists via DomainLayerStore.
  - Records a decision_kind="archive_saved" entry with the new entity FQNs.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal, Union

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from backend.application.agent_tools import ToolEventPump, sse_format
from backend.application.authoring import cost as cost_mod
from backend.application.authoring import session as sess_mod
from backend.application.authoring.replay import (
    SessionResumeState,
    build_resume_state,
)
from backend.application.authoring.capabilities.answer_absorber import (
    AbsorbedAnswers,
    absorb_answers,
)
from backend.application.authoring.capabilities.archiver import (
    ArchiveDocument,
    archive_entity_cycle,
)
from backend.application.authoring.capabilities.code_extractor import (
    ExtractedJpo,
    extract_jpo_from_file,
)
from backend.application.authoring.capabilities.generic_class_extractor import (
    ExtractedClass,
    ExtractedGenericClass,
    extract_from_file,
)
from backend.application.authoring.capabilities.action_extractor import ExtractedAction
from backend.application.authoring.capabilities.gap_detector import GapAnalysis, detect_gaps
from backend.application.authoring.capabilities.hypothesis import (
    ActionHypothesis,
    EntityHypothesis,
    Hypothesis,
    ServiceHypothesis,
    propose_entity_hypothesis,
    propose_hypothesis,
)
from backend.application.authoring.capabilities.service_extractor import ExtractedService
from backend.application.authoring.capabilities.interview import (
    InterviewBatch,
    design_interview,
)
from backend.application.authoring.capabilities.naming import NamingDecision, decide_names
from backend.application.authoring.capabilities.option_proposer import (
    OntologyOption,
    OptionTable,
    propose_options,
)
from backend.application.authoring.capabilities.pattern_checker import (
    PatternCheck,
    PriorEntitySnapshot,
    check_pattern,
)
from backend.application.authoring.capabilities.next_step import (
    NextStep,
    SessionStateSnapshot,
    advise_next_step,
)
from backend.application.authoring.capabilities.next_entity import (
    NextEntityRecommendation,
    NextEntityRequest as NextEntityRequestModel,
    pick_next_entity,
)
from backend.application.authoring.capabilities.comprehensive_archive import (
    ComprehensiveArchive,
    ComprehensiveArchiveRequest as ComprehensiveArchiveRequestModel,
    EntitySnapshot,
    write_comprehensive_archive,
)
from backend.modeling.domain_layer.schema import BusinessTerm, TermKind
from backend.modeling.domain_layer.store import DomainLayerStore

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/authoring", tags=["authoring"])


# ── Injected at startup via main.py.init() ───────────────────────────


_term_store: DomainLayerStore | None = None


def init(business_term_store: DomainLayerStore | None = None) -> None:
    """Wire the DomainLayerStore for the confirm endpoint.

    Pass None in tests that don't exercise /confirm; the endpoint will return
    503 instead of crashing.
    """
    global _term_store
    _term_store = business_term_store
    logger.info(
        "authoring api initialised (business_term_store=%s)",
        type(business_term_store).__name__ if business_term_store else "None",
    )


def _store() -> DomainLayerStore:
    if _term_store is None:
        raise HTTPException(
            status_code=503,
            detail="DomainLayerStore not initialised — /confirm unavailable",
        )
    return _term_store


def _require_session(session_id: str) -> sess_mod.AuthoringSession:
    sess = sess_mod.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    return sess


# ── Session admin ───────────────────────────────────────────────────


class CreateSessionRequest(BaseModel):
    operator_id: str = "default"
    branch_name: str = "main"
    repo_id: str | None = None
    entity_focus: str | None = None
    meta: dict = Field(default_factory=dict)


class UpdateSessionRequest(BaseModel):
    entity_focus: str | None = None
    status: sess_mod.SessionStatus | None = None


@router.post("/sessions", response_model=sess_mod.AuthoringSession)
async def create_session_endpoint(req: CreateSessionRequest) -> sess_mod.AuthoringSession:
    sid = sess_mod.create_session(
        operator_id=req.operator_id,
        branch_name=req.branch_name,
        repo_id=req.repo_id,
        entity_focus=req.entity_focus,
        meta=req.meta,
    )
    sess = sess_mod.get_session(sid)
    assert sess is not None  # we just created it
    return sess


@router.get("/sessions", response_model=list[sess_mod.AuthoringSession])
async def list_sessions_endpoint(
    operator_id: str | None = Query(default=None),
    status: sess_mod.SessionStatus | None = Query(default=None),
) -> list[sess_mod.AuthoringSession]:
    return sess_mod.list_sessions(operator_id=operator_id, status=status)


@router.get("/sessions/{session_id}", response_model=sess_mod.AuthoringSession)
async def get_session_endpoint(session_id: str) -> sess_mod.AuthoringSession:
    return _require_session(session_id)


@router.patch("/sessions/{session_id}", response_model=sess_mod.AuthoringSession)
async def update_session_endpoint(
    session_id: str, req: UpdateSessionRequest
) -> sess_mod.AuthoringSession:
    _require_session(session_id)
    if req.entity_focus is not None:
        sess_mod.update_focus(session_id, req.entity_focus)
    if req.status is not None:
        sess_mod.update_status(session_id, req.status)
    sess = sess_mod.get_session(session_id)
    assert sess is not None
    return sess


# ── History + cost + preview ────────────────────────────────────────


@router.get("/sessions/{session_id}/decisions", response_model=list[sess_mod.AuthoringDecision])
async def list_decisions_endpoint(session_id: str) -> list[sess_mod.AuthoringDecision]:
    _require_session(session_id)
    return sess_mod.list_decisions(session_id)


class CostSummary(BaseModel):
    session_id: str
    total_usd: float
    call_count: int


@router.get("/sessions/{session_id}/cost", response_model=CostSummary)
async def get_cost_endpoint(session_id: str) -> CostSummary:
    _require_session(session_id)
    records = cost_mod.session_records(session_id)
    return CostSummary(
        session_id=session_id,
        total_usd=cost_mod.session_total_usd(session_id),
        call_count=len(records),
    )


class SessionPreview(BaseModel):
    session: sess_mod.AuthoringSession
    decision_count: int
    latest_decisions: list[sess_mod.AuthoringDecision]
    latest_archive_markdown: str | None
    cost: CostSummary


@router.get("/sessions/{session_id}/preview", response_model=SessionPreview)
async def get_preview_endpoint(session_id: str) -> SessionPreview:
    sess = _require_session(session_id)
    decisions = sess_mod.list_decisions(session_id)
    latest_archive = next(
        (
            d.archive_markdown
            for d in reversed(decisions)
            if d.decision_kind == "archive_saved" and d.archive_markdown
        ),
        None,
    )
    cost = await get_cost_endpoint(session_id)
    return SessionPreview(
        session=sess,
        decision_count=len(decisions),
        latest_decisions=decisions[-5:],
        latest_archive_markdown=latest_archive,
        cost=cost,
    )


# ── Capability endpoints ────────────────────────────────────────────


def _record_decision(
    *,
    session_id: str,
    turn_no: int,
    kind: sess_mod.DecisionKind,
    payload: dict,
    step_label: str | None = None,
    entity_id: str | None = None,
    archive_markdown: str | None = None,
) -> int:
    """Centralised decision-logging helper used by every capability endpoint."""
    return sess_mod.add_decision(
        session_id=session_id,
        turn_no=turn_no,
        decision_kind=kind,
        payload=payload,
        step_label=step_label,
        entity_id=entity_id,
        archive_markdown=archive_markdown,
    )


# --- extract -----------------------------------------------------------------


class ExtractRequest(BaseModel):
    """Either supply (file_path + file_content) directly, or supply (fqn + repo_id)
    and the backend will resolve source_file from CodeTypeRow."""

    turn_no: int
    file_path: str | None = None
    file_content: str | None = None
    fqn: str | None = None
    repo_id: str | None = None


def _resolve_source_from_fqn(fqn: str, repo_id: str | None) -> tuple[str, str]:
    """Look up CodeTypeRow.source_file by fqn, read the file, return (path, content)."""
    from sqlalchemy import select
    from backend.modeling.code_layer.orm import CodeTypeRow
    from backend.modeling.persistence.database import session_scope

    with session_scope() as s:
        stmt = select(CodeTypeRow).where(CodeTypeRow.fqn == fqn)
        if repo_id:
            stmt = stmt.where(CodeTypeRow.repo_id == repo_id)
        row = s.execute(stmt).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"code type not found: fqn={fqn} repo={repo_id}")
        if not row.source_file:
            raise HTTPException(
                status_code=400, detail=f"code type {fqn} has no recorded source_file"
            )
        path = row.source_file

    # The source_file in code_types is typically repo-relative. Try a few resolutions.
    from pathlib import Path
    candidates = [
        Path(path),
        Path("sample-repos") / (repo_id or "") / path,
        Path("sample-repos") / "slab-design-real" / path,
    ]
    for c in candidates:
        if c.is_file():
            return str(c.resolve()), c.read_text(encoding="utf-8")
    raise HTTPException(
        status_code=404,
        detail=f"source_file not found on disk: tried {[str(c) for c in candidates]}",
    )


@router.post("/sessions/{session_id}/extract", response_model=ExtractedClass)
async def extract_endpoint(
    session_id: str, req: ExtractRequest
) -> ExtractedJpo | ExtractedGenericClass:
    """Extract one Java file. Dispatcher (extract_from_file) picks the JPO
    schema for @Entity classes and the lightweight Generic outline schema
    for everything else. Response carries `kind` discriminator so the
    frontend can branch UI without sniffing fields.
    """
    _require_session(session_id)

    # Resolve content: either explicit file_content, or look up by fqn.
    if req.file_content is not None and req.file_path is not None:
        path, content = req.file_path, req.file_content
    elif req.fqn is not None:
        path, content = _resolve_source_from_fqn(req.fqn, req.repo_id)
    else:
        raise HTTPException(
            status_code=400,
            detail="must provide either (file_path + file_content) or fqn",
        )

    out = await extract_from_file(
        path,
        content,
        session_id=session_id,
        turn_no=req.turn_no,
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="other",
        payload={
            "capability": "code_extractor",
            "file_path": path,
            "fqn": req.fqn,
            "result": out.model_dump(),
        },
        entity_id=out.class_name,
        step_label=f"Code 추출 ({out.class_name})",
    )
    return out


@router.post("/sessions/{session_id}/extract/stream")
async def extract_stream_endpoint(session_id: str, req: ExtractRequest):
    """SSE variant of /extract — emits tool_call_* events while the extractor
    looks up sibling classes / parent types, then a `done` event with the
    structured payload. The payload's `kind` field is "jpo" for @Entity
    classes (full JPO schema) or "generic" for everything else
    (lightweight outline)."""
    _require_session(session_id)

    if req.file_content is not None and req.file_path is not None:
        path, content = req.file_path, req.file_content
    elif req.fqn is not None:
        path, content = _resolve_source_from_fqn(req.fqn, req.repo_id)
    else:
        raise HTTPException(
            status_code=400,
            detail="must provide either (file_path + file_content) or fqn",
        )

    pump = ToolEventPump()

    async def event_stream():
        final_output: dict | None = None
        async for ev in pump.bridge(
            extract_from_file(
                path,
                content,
                session_id=session_id,
                turn_no=req.turn_no,
                event_pump=pump,
            )
        ):
            yield sse_format(ev)
            if ev.get("type") == "done":
                final_output = ev.get("output")
        if final_output:
            _record_decision(
                session_id=session_id,
                turn_no=req.turn_no,
                kind="other",
                payload={
                    "capability": "code_extractor",
                    "file_path": path,
                    "fqn": req.fqn,
                    "result": final_output,
                },
                entity_id=final_output.get("class_name"),
                step_label=f"Code 추출 ({final_output.get('class_name', '?')})",
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- hypothesize -------------------------------------------------------------


class HypothesizeRequest(BaseModel):
    turn_no: int
    # Accept the discriminated union directly. `extracted_jpo` is kept as an
    # alias for back-compat with existing frontend code that always sent a
    # JPO; new code should send the union via `extracted`. Validator below
    # normalises.
    extracted: Annotated[
        Union[ExtractedJpo, ExtractedService, ExtractedAction] | None,
        Field(discriminator="kind"),
    ] = None
    extracted_jpo: ExtractedJpo | None = None  # deprecated alias
    user_comment: str | None = None  # F3: ✏ 수정 from frontend card

    @model_validator(mode="after")
    def _coalesce_extracted(self) -> "HypothesizeRequest":
        if self.extracted is None and self.extracted_jpo is not None:
            self.extracted = self.extracted_jpo
        if self.extracted is None:
            raise ValueError(
                "HypothesizeRequest requires either `extracted` (union) or "
                "`extracted_jpo` (legacy alias)"
            )
        return self


def _hypothesis_decision_summary(out: Hypothesis) -> tuple[str | None, str]:
    """(entity_id, step_label) pair for _record_decision — kind-aware."""
    if isinstance(out, EntityHypothesis):
        return (
            out.candidate_term_english,
            f"가설 ({out.candidate_term_korean} / {out.candidate_term_english})",
        )
    if isinstance(out, ServiceHypothesis):
        return (
            out.candidate_capability_english,
            f"Service 가설 ({out.candidate_capability_korean} / {out.candidate_capability_english})",
        )
    if isinstance(out, ActionHypothesis):
        return (
            out.domain_verb_english,
            f"Action 가설 ({out.domain_verb_korean} / {out.domain_verb_english})",
        )
    return (None, "가설")


@router.post("/sessions/{session_id}/hypothesize", response_model=Hypothesis)
async def hypothesize_endpoint(
    session_id: str, req: HypothesizeRequest
) -> Hypothesis:
    _require_session(session_id)
    assert req.extracted is not None  # validator guarantees
    out = await propose_hypothesis(
        req.extracted,
        session_id=session_id,
        turn_no=req.turn_no,
        user_comment=req.user_comment,
    )
    entity_id, step_label = _hypothesis_decision_summary(out)
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="hypothesis_seeded",
        payload={"capability": "hypothesis", "result": out.model_dump()},
        entity_id=entity_id,
        step_label=step_label,
    )
    return out


@router.post("/sessions/{session_id}/hypothesize/stream")
async def hypothesize_stream_endpoint(session_id: str, req: HypothesizeRequest):
    """SSE variant of /hypothesize — graph-aware: streams ontology / sibling /
    inheritance lookups while the agent builds its first-cut hypothesis.
    Kind-aware: routes to entity / service / action hypothesis per
    req.extracted.kind."""
    _require_session(session_id)
    assert req.extracted is not None  # validator guarantees
    pump = ToolEventPump()

    async def event_stream():
        final_output: dict | None = None
        async for ev in pump.bridge(
            propose_hypothesis(
                req.extracted,
                session_id=session_id,
                turn_no=req.turn_no,
                user_comment=req.user_comment,
                event_pump=pump,
            )
        ):
            yield sse_format(ev)
            if ev.get("type") == "done":
                final_output = ev.get("output")
        if final_output:
            # Re-validate so we can hand a typed instance to the summary helper.
            from pydantic import TypeAdapter as _TA
            parsed = _TA(Hypothesis).validate_python(final_output)
            entity_id, step_label = _hypothesis_decision_summary(parsed)
            _record_decision(
                session_id=session_id,
                turn_no=req.turn_no,
                kind="hypothesis_seeded",
                payload={"capability": "hypothesis", "result": final_output},
                entity_id=entity_id,
                step_label=step_label,
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- interview --------------------------------------------------------------


class InterviewRequest(BaseModel):
    turn_no: int
    hypothesis: EntityHypothesis
    user_comment: str | None = None


@router.post("/sessions/{session_id}/interview", response_model=InterviewBatch)
async def interview_endpoint(
    session_id: str, req: InterviewRequest
) -> InterviewBatch:
    _require_session(session_id)
    out = await design_interview(
        req.hypothesis,
        session_id=session_id,
        turn_no=req.turn_no,
        user_comment=req.user_comment,
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="interview_designed",
        payload={"capability": "interview", "result": out.model_dump()},
        step_label=f"인터뷰 설계 ({len(out.questions)} Q)",
    )
    return out


# --- absorb -----------------------------------------------------------------


class AbsorbRequest(BaseModel):
    turn_no: int
    batch: InterviewBatch
    user_reply: str


@router.post("/sessions/{session_id}/absorb", response_model=AbsorbedAnswers)
async def absorb_endpoint(session_id: str, req: AbsorbRequest) -> AbsorbedAnswers:
    _require_session(session_id)
    out = await absorb_answers(
        req.batch, req.user_reply, session_id=session_id, turn_no=req.turn_no
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="answer_absorbed",
        payload={"capability": "answer_absorber", "result": out.model_dump()},
        step_label=(
            f"답변 흡수 (응답 {len(out.per_question) - len(out.unanswered)}/{len(out.per_question)})"
        ),
    )
    return out


# --- options ---------------------------------------------------------------


class OptionsRequest(BaseModel):
    turn_no: int
    hypothesis: EntityHypothesis
    answers: AbsorbedAnswers
    pattern_library: list[str] | None = None
    user_comment: str | None = None


@router.post("/sessions/{session_id}/options", response_model=OptionTable)
async def options_endpoint(session_id: str, req: OptionsRequest) -> OptionTable:
    _require_session(session_id)
    out = await propose_options(
        req.hypothesis,
        req.answers,
        pattern_library=req.pattern_library,
        session_id=session_id,
        turn_no=req.turn_no,
        user_comment=req.user_comment,
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="other",
        payload={"capability": "option_proposer", "result": out.model_dump()},
        step_label=f"옵션 제시 ({len(out.options)} 옵션, ★ {out.recommended_id})",
    )
    return out


@router.post("/sessions/{session_id}/options/stream")
async def options_stream_endpoint(session_id: str, req: OptionsRequest):
    """SSE variant of /options — streams `tool_call_start` / `tool_call_end`
    events while the option_proposer agent explores the graph, then a final
    `done` event with the structured `OptionTable`."""
    _require_session(session_id)
    pump = ToolEventPump()

    async def event_stream():
        final_output: dict | None = None
        async for ev in pump.bridge(
            propose_options(
                req.hypothesis,
                req.answers,
                pattern_library=req.pattern_library,
                session_id=session_id,
                turn_no=req.turn_no,
                user_comment=req.user_comment,
                event_pump=pump,
            )
        ):
            yield sse_format(ev)
            if ev.get("type") == "done":
                final_output = ev.get("output")
        if final_output:
            _record_decision(
                session_id=session_id,
                turn_no=req.turn_no,
                kind="other",
                payload={"capability": "option_proposer", "result": final_output},
                step_label=(
                    f"옵션 제시 ({len(final_output.get('options', []))} 옵션, "
                    f"★ {final_output.get('recommended_id', '?')})"
                ),
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- gaps ------------------------------------------------------------------


class GapsRequest(BaseModel):
    turn_no: int
    extracted_jpo: ExtractedJpo
    hypothesis: EntityHypothesis
    answers: AbsorbedAnswers


@router.post("/sessions/{session_id}/gaps", response_model=GapAnalysis)
async def gaps_endpoint(session_id: str, req: GapsRequest) -> GapAnalysis:
    _require_session(session_id)
    out = await detect_gaps(
        req.extracted_jpo,
        req.hypothesis,
        req.answers,
        session_id=session_id,
        turn_no=req.turn_no,
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="other",
        payload={"capability": "gap_detector", "result": out.model_dump()},
        step_label=f"갭 탐지 ({len(out.gaps)} gaps, {out.severity_summary})",
    )
    return out


@router.post("/sessions/{session_id}/gaps/stream")
async def gaps_stream_endpoint(session_id: str, req: GapsRequest):
    """SSE variant of /gaps — streams tool call events for the β progress UX."""
    _require_session(session_id)
    pump = ToolEventPump()

    async def event_stream():
        final_output: dict | None = None
        async for ev in pump.bridge(
            detect_gaps(
                req.extracted_jpo,
                req.hypothesis,
                req.answers,
                session_id=session_id,
                turn_no=req.turn_no,
                event_pump=pump,
            )
        ):
            yield sse_format(ev)
            if ev.get("type") == "done":
                final_output = ev.get("output")
        if final_output:
            _record_decision(
                session_id=session_id,
                turn_no=req.turn_no,
                kind="other",
                payload={"capability": "gap_detector", "result": final_output},
                step_label=(
                    f"갭 탐지 ({len(final_output.get('gaps', []))} gaps, "
                    f"{final_output.get('severity_summary', '?')})"
                ),
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/tool-calls")
async def tool_calls_endpoint(session_id: str):
    """Read the full tool-call trace for a session (for γ expandable UI)."""
    _require_session(session_id)
    from backend.application.authoring.agent_tool_adapter import (
        list_tool_calls_for_session,
    )

    return {"session_id": session_id, "tool_calls": list_tool_calls_for_session(session_id)}


# --- next-step advisor (R6 cap 10) ----------------------------------------


class NextStepRequest(BaseModel):
    turn_no: int
    state: SessionStateSnapshot


@router.post("/sessions/{session_id}/next-step", response_model=NextStep)
async def next_step_endpoint(session_id: str, req: NextStepRequest) -> NextStep:
    """Pure state-based advisor — recommends the next action and a Korean reason.
    Does not use graph tools; reads only the session state snapshot."""
    _require_session(session_id)
    out = await advise_next_step(
        req.state,
        session_id=session_id,
        turn_no=req.turn_no,
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="other",
        payload={"capability": "next_step", "result": out.model_dump()},
        step_label=f"다음 단계 추천 ({out.recommended_action} · {out.priority})",
    )
    return out


# --- session resume (P1a-B) ----------------------------------------------


@router.get(
    "/sessions/{session_id}/replay",
    response_model=SessionResumeState,
)
async def replay_endpoint(session_id: str) -> SessionResumeState:
    """Walk the decision log + return reconstructed state for frontend resume.

    Splits decisions into completed entity cycles (separated by
    `next_entity_started` markers) + the current in-progress cycle.
    """
    state = build_resume_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    return state


class NextEntityMarkRequest(BaseModel):
    turn_no: int


@router.post("/sessions/{session_id}/next-entity-marker")
async def next_entity_marker_endpoint(
    session_id: str, req: NextEntityMarkRequest
) -> dict:
    """Persist a `next_entity_started` decision so reload can split cycles."""
    _require_session(session_id)
    decision_id = _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="next_entity_started",
        payload={},
        step_label="다음 entity 로 전환",
    )
    return {"ok": True, "decision_id": decision_id}


# --- comprehensive archive (P1a-E, cap 12) --------------------------------


class ComprehensiveArchiveApiRequest(BaseModel):
    turn_no: int
    repo_id: str
    entities: list[EntitySnapshot] = Field(..., min_length=1)


@router.post(
    "/sessions/{session_id}/comprehensive-archive",
    response_model=ComprehensiveArchive,
)
async def comprehensive_archive_endpoint(
    session_id: str, req: ComprehensiveArchiveApiRequest
) -> ComprehensiveArchive:
    """Synthesise a session-level archive across all authored entities."""
    _require_session(session_id)
    out = await write_comprehensive_archive(
        ComprehensiveArchiveRequestModel(
            repo_id=req.repo_id,
            session_id_for_log=session_id,
            entities=req.entities,
        ),
        session_id=session_id,
        turn_no=req.turn_no,
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="archive_saved",
        payload={
            "capability": "comprehensive_archive",
            "entity_count": len(req.entities),
            "result": out.model_dump(),
        },
        archive_markdown=out.markdown,
        step_label=f"종합 archive ({len(req.entities)} entities)",
    )
    return out


# --- next-entity picker (P1a-C, cap 11) -----------------------------------


class NextEntityApiRequest(BaseModel):
    turn_no: int
    repo_id: str
    completed_entity_fqns: list[str] = Field(default_factory=list)
    confirmed_term_fqns: list[str] = Field(default_factory=list)


@router.post("/sessions/{session_id}/next-entity", response_model=NextEntityRecommendation)
async def next_entity_endpoint(
    session_id: str, req: NextEntityApiRequest
) -> NextEntityRecommendation:
    """Recommend 3-5 next JPO candidates based on this session's history."""
    _require_session(session_id)
    out = await pick_next_entity(
        NextEntityRequestModel(
            repo_id=req.repo_id,
            completed_entity_fqns=req.completed_entity_fqns,
            confirmed_term_fqns=req.confirmed_term_fqns,
        ),
        session_id=session_id,
        turn_no=req.turn_no,
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="other",
        payload={"capability": "next_entity", "result": out.model_dump()},
        step_label=f"다음 JPO 추천 ({len(out.candidates)} 후보)",
    )
    return out


@router.post("/sessions/{session_id}/next-entity/stream")
async def next_entity_stream_endpoint(session_id: str, req: NextEntityApiRequest):
    """SSE variant — streams tool_call_* events while the picker explores."""
    _require_session(session_id)
    pump = ToolEventPump()

    async def event_stream():
        final_output: dict | None = None
        async for ev in pump.bridge(
            pick_next_entity(
                NextEntityRequestModel(
                    repo_id=req.repo_id,
                    completed_entity_fqns=req.completed_entity_fqns,
                    confirmed_term_fqns=req.confirmed_term_fqns,
                ),
                session_id=session_id,
                turn_no=req.turn_no,
                event_pump=pump,
            )
        ):
            yield sse_format(ev)
            if ev.get("type") == "done":
                final_output = ev.get("output")
        if final_output:
            _record_decision(
                session_id=session_id,
                turn_no=req.turn_no,
                kind="other",
                payload={"capability": "next_entity", "result": final_output},
                step_label=(
                    f"다음 JPO 추천 ({len(final_output.get('candidates', []))} 후보)"
                ),
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- pattern check (R6 cap 7) ---------------------------------------------


class PatternCheckRequest(BaseModel):
    turn_no: int
    hypothesis: EntityHypothesis
    accepted_option: OntologyOption
    # P1a-D: in-session prior entities (most recent first), powering
    # cross-entity pattern detection within a single authoring session.
    prior_session_entities: list[PriorEntitySnapshot] | None = None


@router.post("/sessions/{session_id}/pattern", response_model=PatternCheck)
async def pattern_endpoint(session_id: str, req: PatternCheckRequest) -> PatternCheck:
    """Ontology-vs-ontology consistency check on the user-accepted option."""
    _require_session(session_id)
    out = await check_pattern(
        req.hypothesis,
        req.accepted_option,
        session_id=session_id,
        turn_no=req.turn_no,
        prior_session_entities=req.prior_session_entities,
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="other",
        payload={"capability": "pattern_checker", "result": out.model_dump()},
        step_label=(
            f"패턴 검사 ({len(out.findings)} findings, "
            f"score={out.consistency_score:.2f}, {out.recommendation})"
        ),
    )
    return out


@router.post("/sessions/{session_id}/pattern/stream")
async def pattern_stream_endpoint(session_id: str, req: PatternCheckRequest):
    """SSE variant of /pattern."""
    _require_session(session_id)
    pump = ToolEventPump()

    async def event_stream():
        final_output: dict | None = None
        async for ev in pump.bridge(
            check_pattern(
                req.hypothesis,
                req.accepted_option,
                session_id=session_id,
                turn_no=req.turn_no,
                prior_session_entities=req.prior_session_entities,
                event_pump=pump,
            )
        ):
            yield sse_format(ev)
            if ev.get("type") == "done":
                final_output = ev.get("output")
        if final_output:
            _record_decision(
                session_id=session_id,
                turn_no=req.turn_no,
                kind="other",
                payload={"capability": "pattern_checker", "result": final_output},
                step_label=(
                    f"패턴 검사 ({len(final_output.get('findings', []))} findings, "
                    f"score={final_output.get('consistency_score', 0):.2f}, "
                    f"{final_output.get('recommendation', '?')})"
                ),
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- naming ----------------------------------------------------------------


class NamingRequest(BaseModel):
    turn_no: int
    hypothesis: EntityHypothesis
    accepted_option: OntologyOption
    existing_names: list[str] | None = None
    user_comment: str | None = None


@router.post("/sessions/{session_id}/naming", response_model=NamingDecision)
async def naming_endpoint(session_id: str, req: NamingRequest) -> NamingDecision:
    _require_session(session_id)
    out = await decide_names(
        req.hypothesis,
        req.accepted_option,
        existing_names=req.existing_names,
        session_id=session_id,
        turn_no=req.turn_no,
        user_comment=req.user_comment,
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="naming_confirmed",
        payload={"capability": "naming", "result": out.model_dump()},
        entity_id=out.entities[0].english_id if out.entities else None,
        step_label=f"명명 ({len(out.entities)} entities)",
    )
    return out


# --- archive ---------------------------------------------------------------


class ArchiveRequest(BaseModel):
    turn_no: int
    hypothesis: EntityHypothesis
    answers: AbsorbedAnswers
    accepted_option: OntologyOption
    names: NamingDecision
    gaps: GapAnalysis | None = None
    step_number: int | None = None


@router.post("/sessions/{session_id}/archive", response_model=ArchiveDocument)
async def archive_endpoint(session_id: str, req: ArchiveRequest) -> ArchiveDocument:
    _require_session(session_id)
    out = await archive_entity_cycle(
        hypothesis=req.hypothesis,
        answers=req.answers,
        accepted_option=req.accepted_option,
        names=req.names,
        gaps=req.gaps,
        step_number=req.step_number,
        session_id=session_id,
        turn_no=req.turn_no,
    )
    _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="archive_saved",
        payload={"capability": "archiver", "result": out.model_dump()},
        entity_id=req.names.entities[0].english_id if req.names.entities else None,
        step_label=out.title,
        archive_markdown=out.markdown,
    )
    return out


# ── Finalisation: persist entities to ontology DB ─────────────────────


class ConfirmRequest(BaseModel):
    turn_no: int
    names: NamingDecision
    accepted_option: OntologyOption
    repo_id: str = Field(..., description="ontology repo isolation key")
    domain: str = Field(default="", description="optional domain tag")


class ConfirmResponse(BaseModel):
    session_id: str
    repo_id: str
    persisted_fqns: list[str]
    persisted_count: int
    decision_id: int


def _entity_to_business_term(
    *,
    entity_role: Literal["root", "child", "standalone"],
    korean_label: str,
    english_id: str,
    description: str,
    repo_id: str,
    domain: str,
) -> BusinessTerm:
    """Map our NamingDecision.EntityName → modeling layer BusinessTerm.

    All authored entities are COMPOSITE (their atomic parts are facets, not
    sub-terms). The `is_root_entity` facet mirrors our role:
      - root or standalone → independent lifecycle, searchable
      - child              → composes under a parent (still `is_root_entity=False`)
    """
    fqn = f"term.{repo_id}.{english_id.lower()}"
    return BusinessTerm(
        fqn=fqn,
        label=korean_label,
        description=description,
        kind=TermKind.COMPOSITE,
        is_root_entity=entity_role in ("root", "standalone"),
        confirmed=True,
        repo_id=repo_id,
        domain=domain,
        source="user",
    )


@router.post("/sessions/{session_id}/confirm", response_model=ConfirmResponse)
async def confirm_endpoint(session_id: str, req: ConfirmRequest) -> ConfirmResponse:
    """Persist the named entities into the ontology DB.

    This is the moment the authoring loop becomes durable: until now
    everything was a decision-log entry; after confirm the BusinessTerms exist
    in the modeling-layer store and are searchable in the rest of onTong.
    """
    _require_session(session_id)
    store = _store()

    terms = [
        _entity_to_business_term(
            entity_role=e.role,
            korean_label=e.korean_label,
            english_id=e.english_id,
            description=e.description_short,
            repo_id=req.repo_id,
            domain=req.domain,
        )
        for e in req.names.entities
    ]
    store.upsert_terms(req.repo_id, terms)
    fqns = [t.fqn for t in terms]

    did = _record_decision(
        session_id=session_id,
        turn_no=req.turn_no,
        kind="archive_saved",
        payload={
            "capability": "confirm",
            "repo_id": req.repo_id,
            "fqns": fqns,
            "accepted_option_id": req.accepted_option.id,
        },
        entity_id=req.names.entities[0].english_id if req.names.entities else None,
        step_label=f"Entity 영구 저장 ({len(fqns)} FQNs)",
    )
    sess_mod.update_focus(session_id, req.names.entities[0].english_id if req.names.entities else None)
    return ConfirmResponse(
        session_id=session_id,
        repo_id=req.repo_id,
        persisted_fqns=fqns,
        persisted_count=len(fqns),
        decision_id=did,
    )
