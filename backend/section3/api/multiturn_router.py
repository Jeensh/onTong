"""Section 3 multiturn agent — FastAPI endpoints (spec v2 §7).

URL prefix: `/api/section3/multiturn`

endpoints:
    POST   /start                                   — session 생성 + Gate I (stub) entry
    POST   /respond/{session_id}                    — Gate progression (Phase 2 = Gate I real)
    POST   /confirm/{session_id}/{turn_no}          — card button user_response 저장
    GET    /session/{session_id}                    — replay (decision_log hydrate)
    GET    /session/{session_id}/stream             — SSE current-snapshot (Phase 1 minimal)

Phase 2 scope: Gate I real (LLM intent + sim_v2+ontology candidates merge).
Gate II/III 진입 시 501.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.section3.agents.multiturn import persistence as p
from backend.section3.agents.multiturn.gate_executed_lookup import (
    build_executed_lookup,
)
from backend.section3.agents.multiturn.gate_hypothesis import (
    build_gate_hypothesis,
)
from backend.section3.agents.multiturn.gate_i import (
    build_gate_i, build_intent_classified,
)
from backend.section3.agents.multiturn.gate_ii import build_gate_ii
from backend.section3.agents.multiturn.gate_iii_impact import build_gate_iii_impact
from backend.section3.agents.multiturn.gate_iii_sim import build_gate_iii_sim
from backend.section3.agents.multiturn.intent import (
    MultiturnIntentClassifier,
    OpenAIIntentClassifier,
)
from backend.section3.agents.multiturn.ontology_client import (
    HybridOntologyClient,
    MockOntologyClient,
    OntologyClient,
    SimV2BackedOntologyClient,
)
from backend.section3.agents.multiturn.schemas import (
    ActionRef,
    CodeLocation,
    GateBundle,
    GateIntentClassified,
    GateTarget,
    Provenance,
)
from pydantic import TypeAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/section3/multiturn", tags=["section3-multiturn"])


# Phase 21b — production default: True (사용자 vision: stub → intent_classified
# → confirm → target_selected). 기존 26 tests 는 1-step 가정이므로
# tests/simulation/conftest.py 가 autouse 로 False 설정 (legacy 1-step flow 유지).
INTENT_CONFIRM_REQUIRED: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────


class StartRequest(BaseModel):
    user_query: str
    repo_id: str


class StartResponse(BaseModel):
    session_id: str
    turn_no: int
    payload: dict


class RespondRequest(BaseModel):
    message: str


class ConfirmRequest(BaseModel):
    action: Literal["confirm", "modify", "retry"]
    user_response: dict = Field(default_factory=dict)


class ConfirmResponse(BaseModel):
    ok: bool
    next_gate_kind: str | None = None


class SessionInfo(BaseModel):
    id: str
    repo_id: str
    status: str
    user_query: str | None
    created_at: str
    last_activity_at: str


class DecisionView(BaseModel):
    id: int
    turn_no: int
    gate_kind: str
    payload: dict
    user_response: dict | None
    created_at: str


class SessionResponse(BaseModel):
    session: SessionInfo
    decisions: list[DecisionView]


class SessionSummaryView(BaseModel):
    """history browser 용 — turn_count + last_gate_kind 포함된 요약."""
    id: str
    repo_id: str
    status: str
    user_query: str | None
    created_at: str
    last_activity_at: str
    turn_count: int
    last_gate_kind: str | None


class SessionsListResponse(BaseModel):
    sessions: list[SessionSummaryView]


# Phase 16L — integrity_warning 발화율 (운영 dashboard)
class WarningRatesResponse(BaseModel):
    total_sessions: int
    by_kind: dict[str, int]
    by_kind_pct: dict[str, float]


# Phase 16O — 0-candidate 매핑 갭 추적
class ZeroCandQueryView(BaseModel):
    session_id: str
    user_query: str
    repo_id: str
    created_at: str
    suggestions: list[str]


class ZeroCandQueriesResponse(BaseModel):
    queries: list[ZeroCandQueryView]


# Phase 18 — Stage 2 scope aggregator
class ScopeEntityView(BaseModel):
    kind: str  # action / caller / term / rule
    fqn: str
    label: str
    detail: str = ""
    in_scope_default: bool = True
    meta: dict = {}


class ScopeRequest(BaseModel):
    action_fqn: str
    code_method_fqn: str
    declared_on_term: str | None = None
    repo_id: str


class ScopeResponse(BaseModel):
    primary_action_fqn: str
    primary_method_fqn: str
    entities: list[ScopeEntityView]
    counts: dict[str, int]


# ─────────────────────────────────────────────────────────────────────────────
# Gate I stub — /start 의 즉시 응답 (ambiguous, intent 분류 미실행)
# ─────────────────────────────────────────────────────────────────────────────


def _build_gate_i_stub(user_query: str) -> dict:
    """/start 직후의 임시 ambiguous payload — UI 즉시 응답용.

    실제 intent 분류 + 후보 검색은 /respond (Gate I real) 에서.
    """
    return GateTarget(
        intent="ambiguous",
        user_query=user_query,
        candidates=[],
        recommended_index=None,
        selected=None,
        sources=[
            Provenance(
                source="user_input",
                detail=f"start_session(user_query={user_query!r})",
                confidence=None,
            ),
        ],
    ).model_dump()


# ─────────────────────────────────────────────────────────────────────────────
# DI — FastAPI Depends (test 에서 swap)
# ─────────────────────────────────────────────────────────────────────────────


def get_classifier() -> MultiturnIntentClassifier:
    """default = OpenAIIntentClassifier. test 에서 dependency_overrides 로 swap."""
    return OpenAIIntentClassifier()


def get_ontology_client() -> OntologyClient:
    """default 분기 — env `ONTONG_SECTION2_API_URL` 있으면 HybridOntologyClient.

    - 있음 → `HybridOntologyClient(base_url=...)` : search+action_detail = sec2 HTTP,
            method_body/entity_schema/caller_graph = sim_v2 fallback (Phase 4 wire 후 점진 이전)
    - 없음 → `SimV2BackedOntologyClient` : 100% sim_v2 (Phase 2~3 default)
    test 에서는 `app.dependency_overrides[get_ontology_client]` 로 MockOntologyClient 주입.
    """
    import os
    sec2_url = os.environ.get("ONTONG_SECTION2_API_URL", "").strip()
    if sec2_url:
        return HybridOntologyClient(base_url=sec2_url)
    return SimV2BackedOntologyClient()


# ─────────────────────────────────────────────────────────────────────────────
# Response model for /respond
# ─────────────────────────────────────────────────────────────────────────────


class RespondResponse(BaseModel):
    session_id: str
    turn_no: int
    payload: dict


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/start", response_model=StartResponse)
def start(req: StartRequest) -> StartResponse:
    session_id = p.start_session(repo_id=req.repo_id, user_query=req.user_query)
    payload = _build_gate_i_stub(req.user_query)
    p.add_gate_decision(session_id=session_id, turn_no=1, gate_payload=payload)
    return StartResponse(session_id=session_id, turn_no=1, payload=payload)


@router.post("/respond/{session_id}", response_model=RespondResponse)
async def respond(
    session_id: str,
    req: RespondRequest,
    classifier: MultiturnIntentClassifier = Depends(get_classifier),
    ontology_client: OntologyClient = Depends(get_ontology_client),
) -> RespondResponse:
    """Gate progression.

    Phase 2 scope:
      - turn 2 (= /start 직후 첫 /respond): Gate I real (intent + candidates)
      - turn 3+ : 501 (Gate II/III 미구현)
    """
    session = p.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session.status == "done":
        raise HTTPException(
            status_code=501,
            detail=(
                f"session {session_id} 이미 완료 — Gate III 후 추가 응답은 미지원"
            ),
        )

    decisions = p.list_gate_decisions(session_id)
    next_turn = len(decisions) + 1
    last = decisions[-1] if decisions else None

    # ── Phase 21b — content-driven dispatch ────────────────────────────
    # Case A: /start 직후 stub turn (turn_no=1, no user_response). 정확히
    # 이 1턴 stub 만 stub 으로 인식 — 이후 turns 는 user_response 누락 시 422.
    is_stub = (
        last is not None
        and last.turn_no == 1
        and last.user_response is None
    )
    if is_stub:
        query = req.message.strip() or (session.user_query or "")
        if not query:
            raise HTTPException(
                status_code=422,
                detail="respond 의 message 또는 session.user_query 가 필요",
            )
        if INTENT_CONFIRM_REQUIRED:
            # Phase 21b production: intent 분류만 → 사용자 confirm 대기
            ic = await build_intent_classified(
                user_query=query, classifier=classifier,
            )
            payload = ic.model_dump()
        else:
            # Legacy 1-step (tests): intent + candidates 한 번에 (Gate I real)
            target = await build_gate_i(
                user_query=query,
                repo_id=session.repo_id,
                classifier=classifier,
                ontology_client=ontology_client,
            )
            payload = target.model_dump()
        p.add_gate_decision(
            session_id=session_id, turn_no=next_turn, gate_payload=payload,
        )
        return RespondResponse(
            session_id=session_id, turn_no=next_turn, payload=payload,
        )

    # Case B: intent_classified confirmed → candidates fetch (Gate I real)
    if last is not None and last.gate_kind == "intent_classified":
        if last.user_response is None or last.user_response.get("action") != "confirm":
            raise HTTPException(
                status_code=422,
                detail=(
                    f"turn {last.turn_no} intent_classified 가 confirm 되지 않음 — "
                    "POST /confirm 으로 action=confirm 보내야"
                ),
            )
        try:
            ic = TypeAdapter(GateIntentClassified).validate_python(last.payload)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(
                status_code=422,
                detail=f"intent_classified hydrate 실패: {e}",
            )
        if ic.intent == "ambiguous":
            raise HTTPException(
                status_code=422,
                detail="turn intent 가 ambiguous — 자연어 재입력 필요",
            )
        target = await build_gate_i(
            user_query=ic.user_query,
            repo_id=session.repo_id,
            classifier=classifier,
            ontology_client=ontology_client,
            preclassified=ic,
        )
        payload = target.model_dump()
        p.add_gate_decision(
            session_id=session_id, turn_no=next_turn, gate_payload=payload,
        )
        return RespondResponse(
            session_id=session_id, turn_no=next_turn, payload=payload,
        )

    # Case C: target_selected confirmed → Gate II/III dispatch (intent 별)
    # (legacy: turn 2 target_selected 가 user_response 보유 시 그대로)
    if last is not None and last.gate_kind == "target_selected":
        gate_i_decision = last
        intent = gate_i_decision.payload.get("intent")
        if intent == "ambiguous":
            raise HTTPException(
                status_code=422,
                detail="intent 가 ambiguous — 사용자에게 재분류 필요",
            )
        if intent == "impact":
            # spec v2 §2: impact 분기는 Gate II skip → Gate III impact 직행
            target_ref = await _resolve_gate_ii_target(
                gate_i_decision=gate_i_decision,
                repo_id=session.repo_id,
                ontology_client=ontology_client,
            )
            executed = await build_gate_iii_impact(
                target=target_ref,
                repo_id=session.repo_id,
                ontology_client=ontology_client,
            )
            payload = executed.model_dump()
            p.add_gate_decision(
                session_id=session_id, turn_no=next_turn, gate_payload=payload,
            )
            p.update_session_status(session_id, "done")
            return RespondResponse(
                session_id=session_id, turn_no=next_turn, payload=payload,
            )
        if intent in ("locate", "explain"):
            # Phase 13a: locate / explain → Gate II/III 우회, executed_lookup 직행
            target_ref = await _resolve_gate_ii_target(
                gate_i_decision=gate_i_decision,
                repo_id=session.repo_id,
                ontology_client=ontology_client,
            )
            executed = await build_executed_lookup(
                target=target_ref,
                repo_id=session.repo_id,
                ontology_client=ontology_client,
                mode=intent,   # type: ignore[arg-type]
            )
            payload = executed.model_dump()
            p.add_gate_decision(
                session_id=session_id, turn_no=next_turn, gate_payload=payload,
            )
            p.update_session_status(session_id, "done")
            return RespondResponse(
                session_id=session_id, turn_no=next_turn, payload=payload,
            )
        if intent == "hypothesis":
            # Phase 13c: hypothesis → Gate II/III 우회, executed_hypothesis 직행
            target_ref = await _resolve_gate_ii_target(
                gate_i_decision=gate_i_decision,
                repo_id=session.repo_id,
                ontology_client=ontology_client,
            )
            conditions = list(
                gate_i_decision.payload.get("conditions") or [],
            )
            executed = await build_gate_hypothesis(
                target=target_ref,
                conditions=conditions,
                repo_id=session.repo_id,
                ontology_client=ontology_client,
            )
            payload = executed.model_dump()
            p.add_gate_decision(
                session_id=session_id, turn_no=next_turn, gate_payload=payload,
            )
            p.update_session_status(session_id, "done")
            return RespondResponse(
                session_id=session_id, turn_no=next_turn, payload=payload,
            )
        # intent == "simulate" → Gate II
        target_ref = await _resolve_gate_ii_target(
            gate_i_decision=gate_i_decision,
            repo_id=session.repo_id,
            ontology_client=ontology_client,
        )
        bundle = await build_gate_ii(
            target=target_ref,
            repo_id=session.repo_id,
            ontology_client=ontology_client,
        )
        payload = bundle.model_dump()
        p.add_gate_decision(
            session_id=session_id, turn_no=next_turn, gate_payload=payload,
        )
        return RespondResponse(
            session_id=session_id, turn_no=next_turn, payload=payload,
        )

    # Case D: bundle_prepared → executed_simulation
    if last is not None and last.gate_kind == "bundle_prepared":
        gate_ii_decision = last
        if gate_ii_decision.gate_kind != "bundle_prepared":
            raise HTTPException(
                status_code=422,
                detail=(
                    f"turn {gate_ii_decision.turn_no} 가 bundle_prepared 가 아님 "
                    f"(actual={gate_ii_decision.gate_kind}) — Gate III sim 진입 불가"
                ),
            )
        try:
            bundle = TypeAdapter(GateBundle).validate_python(
                gate_ii_decision.payload,
            )
        except Exception as e:  # noqa: BLE001
            raise HTTPException(
                status_code=422,
                detail=f"turn {gate_ii_decision.turn_no} payload hydrate 실패: {e}",
            )
        executed = await build_gate_iii_sim(
            bundle=bundle, repo_id=session.repo_id,
        )
        payload = executed.model_dump()
        p.add_gate_decision(
            session_id=session_id, turn_no=next_turn, gate_payload=payload,
        )
        p.update_session_status(session_id, "done")
        return RespondResponse(
            session_id=session_id, turn_no=next_turn, payload=payload,
        )

    raise HTTPException(
        status_code=501,
        detail=(
            f"multiturn respond turn_no={next_turn} — "
            "session 이미 완료 또는 추가 게이트 미정의"
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Gate II target resolution
# ─────────────────────────────────────────────────────────────────────────────


async def _resolve_gate_ii_target(
    *,
    gate_i_decision: "p.Section3Decision",
    repo_id: str,
    ontology_client: OntologyClient,
) -> ActionRef:
    """turn 2 GateTarget 의 user_response → selected ActionRef.

    프로토콜:
      - turn 2 가 반드시 `target_selected` 여야
      - user_response 가 `action="confirm"` 이고 `selected_index` 보유
      - candidates[selected_index] 의 정보 + ontology.get_action_detail 로 location 보강
    """
    if gate_i_decision.gate_kind != "target_selected":
        raise HTTPException(
            status_code=422,
            detail=(
                f"turn {gate_i_decision.turn_no} 가 target_selected 가 아님 "
                f"(actual={gate_i_decision.gate_kind})"
            ),
        )
    user_resp = gate_i_decision.user_response or {}
    if user_resp.get("action") != "confirm":
        raise HTTPException(
            status_code=422,
            detail=(
                f"turn {gate_i_decision.turn_no} 가 confirm 되지 않음 — "
                "POST /confirm 으로 selected_index 보내야"
            ),
        )
    try:
        selected_index = int(user_resp["selected_index"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="user_response 에 selected_index (int) 가 없음",
        )

    candidates = gate_i_decision.payload.get("candidates") or []
    if not (0 <= selected_index < len(candidates)):
        raise HTTPException(
            status_code=422,
            detail=(
                f"selected_index={selected_index} 가 candidates 범위 밖 "
                f"(len={len(candidates)})"
            ),
        )
    chosen = candidates[selected_index]
    action_id = chosen.get("action_id")
    code_method_fqn = chosen.get("code_method_fqn")
    if not action_id or not code_method_fqn:
        raise HTTPException(
            status_code=422,
            detail=(
                "선택된 candidate 가 action_id 또는 code_method_fqn 누락"
            ),
        )

    # ontology.get_action_detail 로 location 보강. detail 응답이
    # code_method_fqn 을 비워 둘 수 있음 (예: sec2 actions 가 realization
    # 미연결 — Phase 6 시드 갭). 그 경우 candidate 의 valid fqn 으로 채워야
    # Gate II 의 body fetch 가 동작.
    detail = await ontology_client.get_action_detail(action_id, repo_id=repo_id)
    if detail is not None and detail.code_method_fqn:
        return detail
    if detail is not None:
        # detail 의 다른 메타 (location 등) 는 살리되 fqn 만 candidate 로 보강
        return detail.model_copy(update={"code_method_fqn": code_method_fqn})
    return ActionRef(
        action_id=action_id,
        code_method_fqn=code_method_fqn,
        repo_id=repo_id,
        location=CodeLocation(file_path="", line_start=0, line_end=0),
    )


@router.post("/confirm/{session_id}/{turn_no}", response_model=ConfirmResponse)
def confirm(
    session_id: str, turn_no: int, req: ConfirmRequest,
) -> ConfirmResponse:
    if p.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")

    decisions = p.list_gate_decisions(session_id)
    target = next((d for d in decisions if d.turn_no == turn_no), None)
    if target is None:
        raise HTTPException(
            status_code=404, detail=f"no decision for turn_no={turn_no}",
        )

    # Phase 14A — confirm guard: action="confirm" + target_selected 면
    # candidates / selected_index 사전 검증. 잘못된 confirm → 즉시 422 (turn 3
    # 진입 후 4xx 가 아닌 사용자 click 순간에 명확한 응답).
    if (
        req.action == "confirm"
        and target.gate_kind == "target_selected"
    ):
        candidates = target.payload.get("candidates") or []
        if not candidates:
            suggestions = target.payload.get("suggestions") or []
            detail = (
                "candidates 가 0 개 — confirm 불가. "
                + (
                    f"suggestions={suggestions[:3]} 로 재질문하거나 "
                    if suggestions else ""
                )
                + "action='retry' / 'modify' 로 다시 시도."
            )
            raise HTTPException(status_code=422, detail=detail)
        selected_index = req.user_response.get("selected_index")
        try:
            si = int(selected_index)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail=(
                    "action='confirm' 인데 user_response.selected_index (int) 없음"
                ),
            )
        if not (0 <= si < len(candidates)):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"selected_index={si} 가 candidates 범위 밖 "
                    f"(len={len(candidates)})"
                ),
            )

    user_response = dict(req.user_response)
    user_response["action"] = req.action
    p.update_user_response(target.id, user_response)

    return ConfirmResponse(
        ok=True,
        next_gate_kind=_next_gate_kind(target, req.action),
    )


# ─────────────────────────────────────────────────────────────────────────────
# State machine — confirm 후 다음 gate 결정 (spec v2 §2)
# ─────────────────────────────────────────────────────────────────────────────


def _next_gate_kind(
    decision: "p.Section3Decision",
    action: Literal["confirm", "modify", "retry"],
) -> str | None:
    """spec v2 §2 state machine 의 explicit 계산.

    - target_selected + confirm + simulate intent → bundle_prepared
    - target_selected + confirm + impact intent   → executed_impact
    - target_selected + retry                     → target_selected (재실행)
    - bundle_prepared + confirm                   → executed_simulation
    - bundle_prepared + modify/retry              → bundle_prepared (재합성)
    - executed_*       + 모든 action              → None (session 종료)
    """
    kind = decision.gate_kind
    if kind == "intent_classified":
        # Phase 21b: confirm → target_selected (candidates fetch)
        # retry → 새 intent_classified (자연어 재입력)
        if action == "confirm":
            return "target_selected"
        if action == "retry":
            return "intent_classified"
        return None
    if kind == "target_selected":
        if action == "retry":
            return "target_selected"
        if action == "confirm":
            intent = decision.payload.get("intent")
            if intent == "simulate":
                return "bundle_prepared"
            if intent == "impact":
                return "executed_impact"
            if intent in ("locate", "explain"):
                return "executed_lookup"   # Phase 13a
            if intent == "hypothesis":
                return "executed_hypothesis"   # Phase 13c
            return None  # ambiguous — 재분류 필요
        return None
    if kind == "bundle_prepared":
        if action == "confirm":
            return "executed_simulation"
        if action in ("modify", "retry"):
            return "bundle_prepared"
        return None
    # executed_simulation / executed_impact → 종료
    return None


@router.get("/sessions", response_model=SessionsListResponse)
def list_sessions(
    limit: int = 50,
    repo_id: str | None = None,
    search: str | None = None,
) -> SessionsListResponse:
    """최근 multiturn 세션 N 개 + turn_count + last_gate_kind.

    Query params:
      - limit (1-200, default 50)
      - repo_id: equality filter
      - search: user_query substring (case-insensitive)
    """
    limit = max(1, min(limit, 200))
    rows = p.list_recent_sessions(
        limit=limit, repo_id=repo_id, search=search,
    )
    return SessionsListResponse(
        sessions=[
            SessionSummaryView(
                id=r.id,
                repo_id=r.repo_id,
                status=r.status,
                user_query=r.user_query,
                created_at=r.created_at.isoformat(),
                last_activity_at=r.last_activity_at.isoformat(),
                turn_count=r.turn_count,
                last_gate_kind=r.last_gate_kind,
            )
            for r in rows
        ],
    )


@router.get("/metrics/warnings", response_model=WarningRatesResponse)
def metrics_warnings(
    limit: int = 50,
    repo_id: str | None = None,
) -> WarningRatesResponse:
    """Phase 16L — 최근 N 세션의 integrity_warning 발화율.

    by_kind: warning_kind → 발화한 session 수 (per-session dedupe)
    by_kind_pct: total_sessions 대비 백분율 (1자리 round)

    운영 활용: target_is_test % 가 늘면 modeling 시드 갭, alias_gap % 가 늘면
    business_terms.aliases 미커버 갭.
    """
    limit = max(1, min(limit, 200))
    rates = p.compute_warning_rates(repo_id=repo_id, limit=limit)
    return WarningRatesResponse(
        total_sessions=rates.total_sessions,
        by_kind=rates.by_kind,
        by_kind_pct=rates.by_kind_pct,
    )


@router.post("/scope", response_model=ScopeResponse)
async def scope(
    req: ScopeRequest,
    ontology_client: OntologyClient = Depends(get_ontology_client),
) -> ScopeResponse:
    """Phase 18 — Stage 2 (영향 영역) aggregator.

    선택한 action 의 영향 영역 (callers + sibling actions + related terms + rules)
    한 번에 집계. frontend ScopeStage 가 단일 호출로 모든 entity 확보.

    Test/Mock 패턴 entity 는 `in_scope_default=False` (W4 동기화).
    """
    from backend.section3.agents.multiturn.scope import build_scope

    sc = await build_scope(
        action_fqn=req.action_fqn,
        code_method_fqn=req.code_method_fqn,
        declared_on_term=req.declared_on_term,
        repo_id=req.repo_id,
        ontology_client=ontology_client,
    )
    return ScopeResponse(
        primary_action_fqn=sc.primary_action_fqn,
        primary_method_fqn=sc.primary_method_fqn,
        entities=[
            ScopeEntityView(
                kind=e.kind,
                fqn=e.fqn,
                label=e.label,
                detail=e.detail,
                in_scope_default=e.in_scope_default,
                meta=e.meta,
            )
            for e in sc.entities
        ],
        counts=sc.counts,
    )


@router.get("/metrics/zero-cand-queries", response_model=ZeroCandQueriesResponse)
def metrics_zero_cand_queries(
    limit: int = 20,
    repo_id: str | None = None,
) -> ZeroCandQueriesResponse:
    """Phase 16O — 최근 매핑 갭 query 추적.

    Gate I 가 0-candidate 로 끝난 session 의 user_query 들. modeling team 이
    "어떤 단어로 검색했는데 매칭 안 됐는가" 자동 인지 → BT 시드 보강 가이드.
    ambiguous stub (Phase 2 /start 직후) 는 제외.
    """
    limit = max(1, min(limit, 100))
    rows = p.list_zero_cand_queries(repo_id=repo_id, limit=limit)
    return ZeroCandQueriesResponse(
        queries=[
            ZeroCandQueryView(
                session_id=r.session_id,
                user_query=r.user_query,
                repo_id=r.repo_id,
                created_at=r.created_at.isoformat(),
                suggestions=r.suggestions,
            )
            for r in rows
        ],
    )


@router.get("/session/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    replay = p.replay_session(session_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="session not found")

    return SessionResponse(
        session=SessionInfo(
            id=replay.session.id,
            repo_id=replay.session.repo_id,
            status=replay.session.status,
            user_query=replay.session.user_query,
            created_at=replay.session.created_at.isoformat(),
            last_activity_at=replay.session.last_activity_at.isoformat(),
        ),
        decisions=[
            DecisionView(
                id=d.id, turn_no=d.turn_no, gate_kind=d.gate_kind,
                payload=d.payload, user_response=d.user_response,
                created_at=d.created_at.isoformat(),
            )
            for d in replay.decisions
        ],
    )


@router.get("/session/{session_id}/stream")
def stream(session_id: str) -> StreamingResponse:
    """Phase 1 minimal SSE — 현재 snapshot 한 번 emit 후 종료.

    Phase 2 에서 진짜 실시간 게이트 진행 event 로 확장.
    """
    replay = p.replay_session(session_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="session not found")

    async def _events() -> AsyncIterator[bytes]:
        """폴링 기반 server-push (short-lived).

        - 연결 직후 즉시 snapshot emit
        - 0.5초마다 decisions 길이/user_response 변경 감지 → re-emit
        - session.status="done" 도달 시 done event emit 후 종료
        - 최대 `MAX_TICKS` (default 60 = 30초) 후 timeout 종료 — EventSource 자동 reconnect
        """
        MAX_TICKS = 60
        TICK_SEC = 0.5

        last_signature: tuple[int, str, tuple[int, ...]] | None = None

        for _tick in range(MAX_TICKS):
            current = p.replay_session(session_id)
            if current is None:
                yield b"event: gone\ndata: {}\n\n"
                return

            sig: tuple[int, str, tuple[int, ...]] = (
                len(current.decisions),
                current.session.status,
                tuple(
                    1 if d.user_response is not None else 0
                    for d in current.decisions
                ),
            )
            if sig != last_signature:
                snapshot = {
                    "session_id": session_id,
                    "status": current.session.status,
                    "decisions": [
                        {
                            "id": d.id,
                            "turn_no": d.turn_no,
                            "gate_kind": d.gate_kind,
                            "payload": d.payload,
                            "user_response": d.user_response,
                            "created_at": d.created_at.isoformat(),
                        }
                        for d in current.decisions
                    ],
                }
                yield (
                    f"event: snapshot\n"
                    f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
                ).encode("utf-8")
                last_signature = sig

            if current.session.status == "done":
                yield b"event: done\ndata: {}\n\n"
                return

            await asyncio.sleep(TICK_SEC)

        # tick budget 소진 — 클라이언트가 EventSource 면 자동 reconnect

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 11 — run-custom (user 가 편집한 python_source + custom fixtures 실행)
# Phase 11 — modification-guide (수정 가이드 데이터 묶음)
# ─────────────────────────────────────────────────────────────────────────────


class RunCustomFixture(BaseModel):
    fixture_id: str = Field(default_factory=lambda: "fx-user")
    input_args: list = Field(default_factory=list)
    input_kwargs: dict = Field(default_factory=dict)
    expected_output: object | None = None


class RunCustomRequest(BaseModel):
    python_source: str
    function_name: str
    fixtures: list[RunCustomFixture] = Field(default_factory=list)
    method_fqn: str | None = None
    repo_id: str | None = None
    declared_return: str = "Any"


class RunCustomCaseResult(BaseModel):
    fixture_id: str
    status: str
    output_repr: str = ""
    error: str = ""
    elapsed_sec: float = 0.0


class RunCustomResponse(BaseModel):
    function_name: str
    cases: list[RunCustomCaseResult]
    stub_namespace_size: int
    blocked: bool = False
    block_reason: str = ""


_BLOCKED_PY_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "ctypes",
    "multiprocessing", "threading", "asyncio",
    "pickle", "marshal", "pty", "tty", "fcntl", "resource",
}


def _ast_check_unsafe(python_source: str) -> str | None:
    """AST scan — 명시적으로 위험한 import 차단. 안전하면 None, 위험하면 사유.

    in-process exec 라 strict sandbox 는 아니지만, 사용자가 자주 실수로 넣을 수
    있는 `import os` / `subprocess` 등은 deny 한다. 본질적 격리는 별도 ticket.
    """
    import ast
    try:
        tree = ast.parse(python_source)
    except SyntaxError as e:
        return f"SyntaxError: {e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                root = n.name.split(".", 1)[0]
                if root in _BLOCKED_PY_IMPORTS:
                    return f"import {n.name!r} 차단 (보안)"
        if isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".", 1)[0]
            if mod in _BLOCKED_PY_IMPORTS:
                return f"from {node.module!r} import ... 차단 (보안)"
    return None


@router.post("/run-custom", response_model=RunCustomResponse)
def run_custom(req: RunCustomRequest) -> RunCustomResponse:
    """user 가 편집한 python_source + 직접 지정한 fixtures 실행.

    - 안전: `_ast_check_unsafe` 가 명시적으로 위험한 import 차단.
    - stub: method_fqn + repo_id 제공 시 W74 typed-return stub namespace 자동 구성.
    - 결과: 각 fixture 마다 case_result + invariant status.
    """
    blocked = _ast_check_unsafe(req.python_source)
    if blocked:
        return RunCustomResponse(
            function_name=req.function_name,
            cases=[],
            stub_namespace_size=0,
            blocked=True,
            block_reason=blocked,
        )

    if not req.fixtures:
        return RunCustomResponse(
            function_name=req.function_name,
            cases=[],
            stub_namespace_size=0,
            blocked=True,
            block_reason="fixtures 비어있음 — 최소 1건 필요",
        )

    # stub namespace
    stub_ns: dict = {}
    if req.method_fqn and req.repo_id:
        try:
            from backend.modeling.persistence.database import session_scope
            from backend.sim_v2.core.verification.sandbox_stubs import (
                build_stub_namespace,
            )
            with session_scope() as s:
                stub_ns = build_stub_namespace(
                    s, req.method_fqn, req.repo_id, req.python_source,
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("build_stub_namespace 실패 (graceful): %s", e)
            stub_ns = {}

    # BehaviorFixture 로 변환
    from backend.sim_v2.core.verification.behavior_twin_runner import BehaviorFixture
    from backend.section3 import sim_v2_bridge as sb

    fixtures = [
        BehaviorFixture(
            fixture_id=fx.fixture_id,
            python_source=req.python_source,
            function_name=req.function_name,
            input_args=tuple(fx.input_args),
            input_kwargs=dict(fx.input_kwargs),
            expected_output=fx.expected_output,
        )
        for fx in req.fixtures
    ]

    raw = sb.run_fixtures_in_process(
        fixtures,
        stub_namespace=stub_ns or None,
        declared_return=req.declared_return,
    )

    cases = [
        RunCustomCaseResult(
            fixture_id=r["case_id"],
            status=r.get("invariant_status", "ERROR"),
            output_repr=str(r.get("execution", {}).get("result", {}).get("result", "")),
            error=str(r.get("execution", {}).get("error", "") or ""),
            elapsed_sec=float(r.get("execution", {}).get("elapsed_sec", 0.0)),
        )
        for r in raw
    ]
    return RunCustomResponse(
        function_name=req.function_name,
        cases=cases,
        stub_namespace_size=len(stub_ns),
    )


class ModificationGuideRequest(BaseModel):
    code_method_fqn: str
    repo_id: str


class ModificationCallerRow(BaseModel):
    fqn: str
    match_kind: str | None = None
    strength: float | None = None


class ModificationIdiomRow(BaseModel):
    idiom_name: str
    java_snippet: str
    python_snippet: str


class ModificationGuideResponse(BaseModel):
    method_fqn: str
    body_text: str
    line_start: int
    line_end: int
    return_type: str
    callers: list[ModificationCallerRow]
    idiom_rewrites: list[ModificationIdiomRow]
    diagnostic_passing: int = 0
    diagnostic_fixtures: int = 0
    diagnostic_stubs: int = 0
    hints: list[str] = Field(default_factory=list)


@router.post("/modification-guide", response_model=ModificationGuideResponse)
async def modification_guide(
    req: ModificationGuideRequest,
    ontology_client: OntologyClient = Depends(get_ontology_client),
) -> ModificationGuideResponse:
    """주어진 method 의 수정 가이드 데이터를 한 번에 묶어서 반환.

    구성 요소:
      - body + line range + return_type (sec2)
      - callers (Phase 10 match_kind) (sec2)
      - W75 idiom_rewrites (sim_v2 translate)
      - W71→W72 quick_diagnose (passing/fixtures/stubs)
      - hints: 데이터 기반 권고 메시지
    """
    body = await ontology_client.get_method_body(
        req.code_method_fqn, repo_id=req.repo_id,
    )
    callers_raw = await ontology_client.get_caller_graph(
        req.code_method_fqn, repo_id=req.repo_id,
    )
    callers = [
        ModificationCallerRow(
            fqn=c.fqn,
            match_kind=getattr(c, "match_kind", None),
            strength=getattr(c, "strength", None),
        )
        for c in callers_raw
    ]

    # idiom rewrites — translate 결과의 3rd elem
    idioms: list[ModificationIdiomRow] = []
    if body:
        translated = await asyncio.to_thread(_translate_safe, body)
        if translated and len(translated) >= 3:
            for r in translated[2] or []:
                idioms.append(ModificationIdiomRow(
                    idiom_name=r.get("idiom_name") or "?",
                    java_snippet=r.get("java_snippet") or "",
                    python_snippet=r.get("python_snippet") or "",
                ))

    # diagnostic — quick_diagnose
    diag = await asyncio.to_thread(_quick_diag_safe, req.code_method_fqn, req.repo_id)

    hints: list[str] = []
    if not body:
        hints.append("⚠ method body 가 sec2 에 없습니다 — modeling 시드 갱신 필요")
    if len(callers) > 10:
        hints.append(
            f"호출처가 {len(callers)} 군데로 많음 — 리턴 타입 / 시그니처 변경 시 광범위 영향. min_strength 로 신호 필터링 권장."
        )
    if len(callers) == 0:
        hints.append("호출처 0건 surface — dead code 가능성. 또는 receiver 정보 부재로 매칭 안 됨")
    if idioms:
        hints.append(f"W75 idiom rewrite {len(idioms)}건 — Python 시뮬레이션 시 자동 매핑됨")
    if diag.get("fixtures", 0) > 0:
        passing = diag.get("passing", 0)
        fixtures_n = diag.get("fixtures", 0)
        hints.append(
            f"현재 invariant 결과 {passing}/{fixtures_n} fixtures PASS — 수정 후 동일 baseline 유지 검증 가능"
        )

    line_start = 0
    line_end = 0
    return_type = ""
    if body:
        # body 자체는 string 만. line/return_type 은 추가 API 호출 필요하나 그 데이터는
        # 같은 sec2 endpoint 가 이미 반환했음. 단순화 위해 별도 호출 생략 (graceful).
        try:
            import os as _os
            sec2 = _os.environ.get("ONTONG_SECTION2_API_URL", "").strip()
            if sec2:
                import httpx
                from urllib.parse import quote
                async with httpx.AsyncClient(base_url=sec2, timeout=5.0) as c:
                    r = await c.get(
                        f"/api/ontology/code-methods/{quote(req.code_method_fqn, safe='')}/body",
                        params={"repo_id": req.repo_id},
                    )
                    if r.status_code == 200:
                        raw = r.json()
                        line_start = int(raw.get("line_start", 0) or 0)
                        line_end = int(raw.get("line_end", 0) or 0)
                        return_type = str(raw.get("return_type", "") or "")
        except Exception:  # noqa: BLE001
            pass

    return ModificationGuideResponse(
        method_fqn=req.code_method_fqn,
        body_text=body or "",
        line_start=line_start,
        line_end=line_end,
        return_type=return_type,
        callers=callers,
        idiom_rewrites=idioms,
        diagnostic_passing=int(diag.get("passing", 0)),
        diagnostic_fixtures=int(diag.get("fixtures", 0)),
        diagnostic_stubs=int(diag.get("stubs", 0)),
        hints=hints,
    )


def _translate_safe(body_text: str):
    """sim_v2.translate_java_to_python 의 안전 래퍼."""
    from backend.section3 import sim_v2_bridge as sb
    try:
        return sb.translate_java_to_python(body_text)
    except Exception as e:  # noqa: BLE001
        logger.warning("translate 실패: %s", e)
        return None


def _quick_diag_safe(code_method_fqn: str, repo_id: str) -> dict:
    """quick_diagnose_action 의 안전 래퍼 — action FQN 으로 변환 후 실행."""
    from backend.section3 import sim_v2_bridge as sb
    try:
        s = sb.open_sim_v2_session()
        if s is None:
            return {}
        try:
            # method_fqn → action_fqn 매핑은 realizations 조회 — 간단히 fqn 으로 시도
            from sqlalchemy import text
            row = s.execute(
                text(
                    "SELECT action_fqn FROM realizations "
                    "WHERE code_method_fqn = :m AND repo_id = :r AND scope='primary' "
                    "LIMIT 1"
                ),
                {"m": code_method_fqn, "r": repo_id},
            ).fetchone()
            if not row:
                return {}
            action = sb.load_action(s, row[0], repo_id)
            if action is None:
                return {}
            return sb.quick_diagnose_action(s, action) or {}
        finally:
            s.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("quick_diag 실패: %s", e)
        return {}


__all__ = ["router"]
