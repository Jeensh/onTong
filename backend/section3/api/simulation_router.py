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

from backend.section3.agents.multiturn.gate_executed_lookup import (
    build_executed_lookup,
)
from backend.section3.agents.multiturn.gate_hypothesis import (
    build_gate_hypothesis,
)
from backend.section3.agents.multiturn.gate_i import build_gate_i
from backend.section3.agents.multiturn.gate_ii import build_gate_ii
from backend.section3.agents.multiturn.gate_iii_impact import (
    build_gate_iii_impact,
)
from backend.section3.agents.multiturn.gate_iii_sim import build_gate_iii_sim
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
from backend.section3.agents.simulation.schemas import (
    ActionRef, GateBundle, GateTarget,
)

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
    action: Literal[
        "select_candidate", "request_other", "clarify_intent",
        "confirm_bundle", "rerun", "abort",
    ]
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


async def _proceed_from_target(
    *, session_id: str, intent: str, target: ActionRef, repo_id: str,
    ontology_client: OntologyClient,
    conditions: list[dict] | None = None,
) -> "RespondResponse":
    """select_candidate 시점에서 intent 별로 다음 게이트 자동 진행.

    - simulate, hypothesis → Gate II (bundle_prepared)
    - impact               → Gate III impact 직진
    - locate, explain      → Gate III lookup 직진 (mode=locate|explain)
    """
    if intent in ("simulate", "hypothesis"):
        try:
            bundle = await build_gate_ii(
                target=target, repo_id=repo_id, ontology_client=ontology_client,
            )
            payload = bundle.model_dump()
            confidence = payload.get("confidence", 0.0)
        except Exception as e:  # noqa: BLE001
            logger.exception("Gate II 빌드 실패")
            payload = {
                "kind": "bundle_prepared",
                "target": target.model_dump(),
                "error": f"bundle 합성 실패: {e}",
                "java_source": "", "python_source": "",
                "idiom_diffs": [], "fixtures": [],
                "schema_summary": {"entity_name": "", "fields": [], "primary_key": None},
                "sources": [], "confidence": 0.0,
            }
            confidence = 0.0
        new_turn = p.add_gate_decision(
            session_id, gate_kind="bundle_prepared", payload=payload,
        )
        return RespondResponse(
            session_id=session_id, turn_no=new_turn,
            next_gate="bundle_prepared", payload=payload,
            message=f"intent={intent} → bundle (confidence {confidence:.2f})",
        )

    if intent == "impact":
        try:
            imp = await build_gate_iii_impact(
                target=target, repo_id=repo_id, ontology_client=ontology_client,
            )
            payload = imp.model_dump()
        except Exception as e:  # noqa: BLE001
            logger.exception("Gate III impact 빌드 실패")
            payload = {
                "kind": "executed_impact",
                "target": target.model_dump(),
                "error": f"impact 분석 실패: {e}",
                "affected_methods": [],
                "confidence": 0.0,
                "sim_v2_findings": [],
                "sources": [],
            }
    elif intent in ("locate", "explain"):
        try:
            look = await build_executed_lookup(
                target=target, repo_id=repo_id,
                ontology_client=ontology_client, mode=intent,
            )
            payload = look.model_dump()
        except Exception as e:  # noqa: BLE001
            logger.exception("Gate III lookup 빌드 실패 (%s)", intent)
            payload = {
                "kind": "executed_lookup",
                "mode": intent,
                "target": target.model_dump(),
                "error": f"{intent} 실패: {e}",
            }
    else:
        payload = {
            "kind": "executed_unknown",
            "intent": intent,
            "target": target.model_dump(),
            "note": "지원되지 않는 intent — clarify_intent 로 재진입",
        }

    new_turn = p.add_gate_decision(
        session_id, gate_kind="executed", payload=payload,
    )
    p.update_session(session_id, status="done")
    return RespondResponse(
        session_id=session_id, turn_no=new_turn,
        next_gate="done", payload=payload,
        message=f"intent={intent} 실행 완료",
    )


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
        intent = target.intent
        action_ref = ActionRef(
            action_id=selected.action_id,
            code_method_fqn=selected.code_method_fqn,
            repo_id=sess.repo_id,
            location=selected.location,
        )

        return await _proceed_from_target(
            session_id=session_id, intent=intent, target=action_ref,
            repo_id=sess.repo_id,
            ontology_client=ontology_client,
            conditions=target.conditions,
        )

    # ── confirm_bundle → simulate/hypothesis Gate III 실행 ──────────────
    if req.action == "confirm_bundle":
        replay = p.replay_session(session_id)
        if not replay or not replay.decisions:
            raise HTTPException(status_code=404, detail="decisions 비어있음")
        last = replay.decisions[-1]
        if last.gate_kind != "bundle_prepared":
            raise HTTPException(
                status_code=409,
                detail=f"마지막 게이트가 bundle_prepared 가 아님: {last.gate_kind}",
            )
        try:
            bundle = TypeAdapter(GateBundle).validate_python(last.payload)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(
                status_code=422, detail=f"bundle hydrate 실패: {e}",
            )
        intent = sess.intent or "simulate"
        try:
            if intent == "hypothesis":
                # hypothesis 는 conditions 가 필요 — target 의 마지막 turn 에서
                # conditions 를 가져옴
                conditions: list[dict[str, str]] = []
                for d in reversed(replay.decisions):
                    if d.gate_kind == "target_selected":
                        conditions = list(d.payload.get("conditions") or [])
                        break
                hyp = await build_gate_hypothesis(
                    target=bundle.target, conditions=conditions,
                    repo_id=sess.repo_id, ontology_client=ontology_client,
                )
                payload = hyp.model_dump()
            else:
                sim = await build_gate_iii_sim(
                    bundle=bundle, repo_id=sess.repo_id,
                )
                payload = sim.model_dump()
        except Exception as e:  # noqa: BLE001
            logger.exception("Gate III 실행 실패")
            payload = {
                "kind": "executed_simulation" if intent != "hypothesis" else "executed_hypothesis",
                "target": bundle.target.model_dump(),
                "error": f"실행 실패: {e}",
                "results": [], "invariant_status": "error",
                "baseline_diff": None,
            }
        new_turn = p.add_gate_decision(
            session_id, gate_kind="executed", payload=payload,
        )
        p.update_session(session_id, status="done")
        return RespondResponse(
            session_id=session_id, turn_no=new_turn,
            next_gate="done", payload=payload,
            message=f"intent={intent} 실행 완료",
        )

    # ── rerun (Gate III 결과 위에서 다시) ───────────────────────────────
    if req.action == "rerun":
        # 가장 최근 bundle_prepared 의 payload 로 다시 build_gate_iii_sim
        replay = p.replay_session(session_id)
        if not replay:
            raise HTTPException(status_code=404, detail="session 없음")
        bundle_decision = None
        target_decision = None
        for d in reversed(replay.decisions):
            if d.gate_kind == "bundle_prepared" and not bundle_decision:
                bundle_decision = d
            if d.gate_kind == "target_selected" and not target_decision:
                target_decision = d
            if bundle_decision and target_decision:
                break
        if bundle_decision:
            bundle = TypeAdapter(GateBundle).validate_python(bundle_decision.payload)
            sim = await build_gate_iii_sim(bundle=bundle, repo_id=sess.repo_id)
            payload = sim.model_dump()
            new_turn = p.add_gate_decision(
                session_id, gate_kind="executed", payload=payload,
            )
            return RespondResponse(
                session_id=session_id, turn_no=new_turn,
                next_gate="done", payload=payload, message="재실행 완료",
            )
        raise HTTPException(
            status_code=409,
            detail="rerun 할 bundle 이 없습니다 — confirm_bundle 부터 진행",
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
