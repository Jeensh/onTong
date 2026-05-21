"""Section 3 시뮬레이션 에이전트 — FastAPI endpoints (SIMULATION_AGENT_RFC.md).

URL prefix: `/api/section3/simulation`

endpoints:
    POST /start                — session 생성 + Gate I 진입 (stub Phase B)
    POST /respond/{session_id} — 사용자 결정 처리 + 다음 게이트 진행 (stub Phase B)
    GET  /replay/{session_id}  — transcript hydrate

Phase B scope: scaffold 만 — /start /replay 은 작동, /respond 는 echo stub.
Gate I 실제 LLM 분류는 Phase C 에서 구현.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.section3.agents.simulation import persistence as p

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
    next_gate: Literal[
        "intent_classified", "target_selected",
        "bundle_prepared", "executed", "done",
    ]
    payload: dict | None = None
    message: str = ""


class RespondRequest(BaseModel):
    turn_no: int
    user_response: dict


class RespondResponse(BaseModel):
    session_id: str
    next_gate: Literal[
        "intent_classified", "target_selected",
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
# Endpoints (Phase B = scaffold stub)
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/start", response_model=StartResponse)
async def start(req: StartRequest) -> StartResponse:
    """세션 생성 + Gate I (stub) 진입.

    Phase B: intent 분류 없이 stub payload 반환.
    Phase C 에서 실제 multiturn intent classifier 호출로 교체.
    """
    sid = p.start_session(repo_id=req.repo_id, user_query=req.user_query)
    stub_payload = {
        "kind": "stub_intent",
        "user_query": req.user_query,
        "note": "Phase B scaffold — Gate I real intent classifier 는 Phase C 에서 구현",
    }
    turn_no = p.add_gate_decision(sid, gate_kind="stub_intent", payload=stub_payload)
    logger.info("simulation.start sid=%s turn=%s repo=%s", sid, turn_no, req.repo_id)
    return StartResponse(
        session_id=sid,
        next_gate="intent_classified",
        payload=stub_payload,
        message="세션 생성됨 — Phase C 에서 실제 intent 분류 진행 예정",
    )


@router.post("/respond/{session_id}", response_model=RespondResponse)
async def respond(session_id: str, req: RespondRequest) -> RespondResponse:
    """사용자 결정 처리 + 다음 게이트 진행.

    Phase B: 사용자 응답을 turn 에 기록만 하고 'done' 으로 종료 (stub).
    Phase C 부터 Gate I→II→III 실제 흐름.
    """
    sess = p.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    try:
        p.update_user_response(session_id, req.turn_no, req.user_response)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    p.update_session(session_id, status="done")
    logger.info("simulation.respond sid=%s turn=%s → stub done", session_id, req.turn_no)
    return RespondResponse(
        session_id=session_id,
        next_gate="done",
        payload=None,
        message="Phase B stub — 실제 게이트 진행은 Phase C+ 에서",
    )


@router.get("/replay/{session_id}", response_model=ReplayResponse)
async def replay(session_id: str) -> ReplayResponse:
    """세션 transcript hydrate."""
    replay = p.replay_session(session_id)
    if replay is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    sess = replay.session
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
            for d in replay.decisions
        ],
    )
