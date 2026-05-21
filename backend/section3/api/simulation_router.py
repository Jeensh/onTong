"""Section 3 시뮬레이션 에이전트 — FastAPI endpoints (SIMULATION_AGENT_RFC.md).

URL prefix: `/api/section3/simulation`

endpoints:
    POST /start                — session 생성 + Gate I (intent 분류 + 후보 검색)
    POST /respond/{session_id} — 사용자 결정 처리 + 다음 게이트
    GET  /replay/{session_id}  — transcript hydrate

Phase C: Gate I real — multiturn 의 build_gate_i 차용. intent 가 ambiguous
면 candidates 비어있고 사용자에게 명확화 surface.
Gate II/III 는 Phase D/E 에서.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, TypeAdapter

from backend.section3.agents.multiturn.gate_i import build_gate_i
from backend.section3.agents.multiturn.intent import (
    MultiturnIntentClassifier,
    OpenAIIntentClassifier,
)
from backend.section3.agents.multiturn.ontology_client import (
    HybridOntologyClient,
    OntologyClient,
    SimV2BackedOntologyClient,
)
from backend.section3.agents.simulation import persistence as p
from backend.section3.agents.simulation.schemas import GateTarget

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/section3/simulation",
    tags=["section3-simulation"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────


class StartRequest(BaseModel):
    user_query: str = Field(min_length=1)
    repo_id: str = Field(min_length=1)


class StartResponse(BaseModel):
    session_id: str
    turn_no: int
    next_gate: Literal[
        "target_selected", "ambiguous_clarification",
        "bundle_prepared", "executed", "done",
    ]
    payload: dict
    message: str = ""


class RespondRequest(BaseModel):
    """사용자 결정.

    action 의 의미:
      - "select_candidate": 후보 1개 선택 → next gate (intent 별 분기)
      - "request_other":    같은 query 로 다른 후보 (Gate I 재실행)
      - "clarify_intent":   ambiguous 일 때 사용자가 의도 명시 (intent 필드 같이)
      - "abort":            세션 종료
    """
    turn_no: int
    action: Literal["select_candidate", "request_other", "clarify_intent", "abort"]
    selected_index: int | None = None
    intent: str | None = None  # clarify_intent 시
    note: str | None = None


class RespondResponse(BaseModel):
    session_id: str
    turn_no: int
    next_gate: Literal[
        "target_selected", "ambiguous_clarification",
        "bundle_prepared", "executed", "done", "aborted",
    ]
    payload: dict | None = None
    message: str = ""


class ReplayDecision(BaseModel):
    turn_no: int
    gate_kind: str
    payload: dict
    user_response: dict | None = None
    created_at: str


class ReplayResponse(BaseModel):
    session_id: str
    repo_id: str
    intent: str | None = None
    status: str
    user_query: str | None = None
    created_at: str
    last_activity_at: str
    decisions: list[ReplayDecision] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# DI — test 에서 dependency_overrides 로 swap
# ─────────────────────────────────────────────────────────────────────────────


def get_classifier() -> MultiturnIntentClassifier:
    return OpenAIIntentClassifier()


def get_ontology_client() -> OntologyClient:
    import os
    sec2_url = os.environ.get("ONTONG_SECTION2_API_URL", "").strip()
    if sec2_url:
        return HybridOntologyClient(base_url=sec2_url)
    return SimV2BackedOntologyClient()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _build_target_payload(
    *, user_query: str, repo_id: str,
    classifier: MultiturnIntentClassifier,
    ontology_client: OntologyClient,
) -> dict:
    """multiturn 의 build_gate_i 호출 → GateTarget payload (dict)."""
    target = await build_gate_i(
        user_query=user_query,
        repo_id=repo_id,
        classifier=classifier,
        ontology_client=ontology_client,
    )
    return target.model_dump()


def _next_gate_from_target(payload: dict) -> str:
    """target_selected payload 의 intent 로 다음 게이트 결정."""
    intent = payload.get("intent", "ambiguous")
    if intent == "ambiguous":
        return "ambiguous_clarification"
    return "target_selected"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/start", response_model=StartResponse)
async def start(
    req: StartRequest,
    classifier: MultiturnIntentClassifier = Depends(get_classifier),
    ontology_client: OntologyClient = Depends(get_ontology_client),
) -> StartResponse:
    """세션 생성 + Gate I (intent 분류 + 후보 검색) 한 번에.

    intent 가 ambiguous 면 candidates 가 빈 채로 와서 UI 가 의도 명확화
    카드 surface. 그 외 intent 면 후보 carousel surface.
    """
    sid = p.start_session(repo_id=req.repo_id, user_query=req.user_query)
    payload = await _build_target_payload(
        user_query=req.user_query, repo_id=req.repo_id,
        classifier=classifier, ontology_client=ontology_client,
    )
    intent = payload.get("intent", "ambiguous")
    p.update_session(sid, intent=intent)
    turn_no = p.add_gate_decision(sid, gate_kind="target_selected", payload=payload)
    next_gate = _next_gate_from_target(payload)
    logger.info(
        "simulation.start sid=%s turn=%s intent=%s candidates=%s",
        sid, turn_no, intent, len(payload.get("candidates", [])),
    )
    return StartResponse(
        session_id=sid,
        turn_no=turn_no,
        next_gate=next_gate,
        payload=payload,
        message=(
            "의도 명확화 필요" if next_gate == "ambiguous_clarification"
            else f"intent={intent} · 후보 {len(payload.get('candidates', []))} 건"
        ),
    )


@router.post("/respond/{session_id}", response_model=RespondResponse)
async def respond(
    session_id: str,
    req: RespondRequest,
    classifier: MultiturnIntentClassifier = Depends(get_classifier),
    ontology_client: OntologyClient = Depends(get_ontology_client),
) -> RespondResponse:
    """사용자 결정 처리 + 다음 게이트 진행."""
    sess = p.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    if sess.status in ("done", "aborted"):
        raise HTTPException(status_code=409, detail=f"session 이미 종료: {sess.status}")

    user_response = {
        "action": req.action,
        "selected_index": req.selected_index,
        "intent": req.intent,
        "note": req.note,
    }
    try:
        p.update_user_response(session_id, req.turn_no, user_response)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # ── abort ────────────────────────────────────────────────────────────
    if req.action == "abort":
        p.update_session(session_id, status="aborted")
        return RespondResponse(
            session_id=session_id, turn_no=req.turn_no,
            next_gate="aborted", message="세션 중단",
        )

    # ── request_other / clarify_intent → Gate I 재실행 ───────────────────
    if req.action in ("request_other", "clarify_intent"):
        # ambiguous 였으면 사용자가 명시한 intent 로 강제
        query = sess.user_query or ""
        if req.action == "clarify_intent" and req.intent:
            query = f"[intent={req.intent}] {query}"
        payload = await _build_target_payload(
            user_query=query, repo_id=sess.repo_id,
            classifier=classifier, ontology_client=ontology_client,
        )
        new_intent = req.intent if req.action == "clarify_intent" else payload.get("intent")
        p.update_session(session_id, intent=new_intent)
        new_turn = p.add_gate_decision(
            session_id, gate_kind="target_selected", payload=payload,
        )
        return RespondResponse(
            session_id=session_id, turn_no=new_turn,
            next_gate=_next_gate_from_target(payload),
            payload=payload,
            message=f"재검색 — intent={payload.get('intent')} · "
                    f"후보 {len(payload.get('candidates', []))} 건",
        )

    # ── select_candidate → Phase D 의 Gate II 진입 (Phase C 단계에선 stub) ──
    if req.action == "select_candidate":
        replay = p.replay_session(session_id)
        if not replay or not replay.decisions:
            raise HTTPException(status_code=404, detail="decisions 비어있음")
        last = replay.decisions[-1]
        try:
            target = TypeAdapter(GateTarget).validate_python(last.payload)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(
                status_code=422,
                detail=f"target hydrate 실패: {e}",
            )
        if req.selected_index is None or req.selected_index < 0 \
                or req.selected_index >= len(target.candidates):
            raise HTTPException(
                status_code=422, detail=f"selected_index 범위 밖: {req.selected_index}",
            )
        selected = target.candidates[req.selected_index]
        # Phase D 에서 Gate II 실제 구현. 지금은 placeholder.
        intent = target.intent
        if intent in ("simulate", "hypothesis"):
            stub_payload = {
                "kind": "bundle_prepared_stub",
                "intent": intent,
                "selected_candidate": selected.model_dump(),
                "note": "Phase D 에서 Java→Python + fixture 합성 구현 예정",
            }
            next_gate = "bundle_prepared"
        else:
            # impact / locate / explain → Gate II skip, Gate III 직진
            stub_payload = {
                "kind": "executed_stub",
                "intent": intent,
                "selected_candidate": selected.model_dump(),
                "note": "Phase E 에서 intent 별 실행 분기 구현 예정",
            }
            next_gate = "executed"

        new_turn = p.add_gate_decision(
            session_id, gate_kind=next_gate, payload=stub_payload,
        )
        return RespondResponse(
            session_id=session_id, turn_no=new_turn,
            next_gate=next_gate, payload=stub_payload,
            message=f"intent={intent} → {next_gate} 진행 (Phase D/E 에서 실제 구현)",
        )

    raise HTTPException(status_code=400, detail=f"알 수 없는 action: {req.action}")


@router.get("/replay/{session_id}", response_model=ReplayResponse)
async def replay(session_id: str) -> ReplayResponse:
    """세션 transcript hydrate."""
    rep = p.replay_session(session_id)
    if rep is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    sess = rep.session
    return ReplayResponse(
        session_id=sess.id,
        repo_id=sess.repo_id,
        intent=sess.intent,
        status=sess.status,
        user_query=sess.user_query,
        created_at=sess.created_at.isoformat(),
        last_activity_at=sess.last_activity_at.isoformat(),
        decisions=[
            ReplayDecision(
                turn_no=d.turn_no,
                gate_kind=d.gate_kind,
                payload=d.payload,
                user_response=d.user_response,
                created_at=d.created_at.isoformat(),
            )
            for d in rep.decisions
        ],
    )
