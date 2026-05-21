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
from backend.section3.agents.simulation.compare_runs import compare_runs
from backend.section3.agents.simulation.schemas import (
    ActionRef, GateBundle, GateTarget,
)
from backend.section3.agents.simulation.slab_design_runner import (
    extract_order_no, is_full_design_intent, run_full_design,
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
        "confirm_bundle", "rerun", "compare_with_overrides",
        "run_full_design", "abort",
    ]
    selected_index: int | None = None
    intent: str | None = None  # clarify_intent 시
    overrides: dict | None = None  # compare_with_overrides 시 (변경 후 값)
    order_no: str | None = None    # run_full_design 시 (없으면 query 에서 추출)
    cmp_cd: str | None = None
    org_cd: str | None = None
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


def _is_test_candidate(c: dict) -> bool:
    """candidate 가 @Test 또는 *Test 클래스의 메서드면 True.

    Section 3 사용자는 production 도메인 로직을 보고 싶어함 — test 메서드는
    importer 가 src/test/java 도 파싱하기 때문에 후보에 섞임. 시뮬레이션
    에이전트에서는 제외.
    """
    fqn = (c.get("code_method_fqn") or "").strip()
    # 클래스 이름이 Test 로 끝나거나 (XxxTest / XxxTests) Test 시작 시 제외
    # FQN 형식: pkg.Class.method(...) — '(' 앞까지를 method, 그 앞 클래스명 추출
    head = fqn.split("(", 1)[0]              # pkg.Class.method
    class_part = head.rsplit(".", 1)[0]      # pkg.Class
    cname = class_part.rsplit(".", 1)[-1]    # Class
    if cname.endswith("Test") or cname.endswith("Tests") or cname == "SmokeTest":
        return True
    # annotations 에 @Test 가 있으면 (junit 4/5)
    anns = c.get("annotations") or []
    if any("Test" in a for a in anns):
        return True
    return False


async def _build_target_payload(
    *, user_query: str, repo_id: str,
    classifier: MultiturnIntentClassifier,
    ontology_client: OntologyClient,
) -> dict:
    """multiturn 의 build_gate_i 호출 → GateTarget payload (dict).

    후처리: test 메서드 후보 제거. recommended_index 가 가리키는 항목이
    제거되면 첫 번째 production 후보로 재조정.
    """
    target = await build_gate_i(
        user_query=user_query,
        repo_id=repo_id,
        classifier=classifier,
        ontology_client=ontology_client,
    )
    payload = target.model_dump()
    candidates = payload.get("candidates") or []
    if candidates:
        filtered = [c for c in candidates if not _is_test_candidate(c)]
        if filtered:
            payload["candidates"] = filtered
            payload["recommended_index"] = 0 if filtered else None
            # 사용자에게 알리는 메모
            payload["_filtered_test_count"] = len(candidates) - len(filtered)
    return payload


def _next_gate_from_target(payload: dict) -> str:
    """target_selected payload 의 intent 로 다음 게이트 결정."""
    intent = payload.get("intent", "ambiguous")
    if intent == "ambiguous":
        return "ambiguous_clarification"
    return "target_selected"


async def _execute_full_design(
    *, session_id: str, order_no: str,
    cmp_cd: str = "K", org_cd: str = "1",
) -> "RespondResponse":
    """Java slab-design 서버 호출 → slabResults + trace 를 executed payload 로."""
    result = await run_full_design(order_no=order_no, cmp_cd=cmp_cd, org_cd=org_cd)
    payload: dict = {
        "kind": "executed_full_design",
        "order_no": order_no,
        "cmp_cd": cmp_cd, "org_cd": org_cd,
        "ok": result["ok"],
        "slab_results": result["slab_results"],
        "trace": result["trace"],
        "error_code": result["error_code"],
        "error_message": result["error_message"],
        "base_url": result["base_url"],
    }
    if not result["ok"]:
        payload["error"] = result["error_message"]
    new_turn = p.add_gate_decision(session_id, gate_kind="executed", payload=payload)
    p.update_session(session_id, status="done")
    n_slabs = len(result["slab_results"])
    msg = (
        f"Slab {n_slabs}매 설계 완료" if result["ok"] and not result["error_code"]
        else f"실패 — {result['error_code']}: {(result['error_message'] or '')[:80]}"
    )
    return RespondResponse(
        session_id=session_id, turn_no=new_turn,
        next_gate="done", payload=payload, message=msg,
    )


async def _proceed_from_target(
    *, session_id: str, intent: str, target: ActionRef, repo_id: str,
    ontology_client: OntologyClient,
    conditions: list[dict] | None = None,
    user_query: str | None = None,
) -> "RespondResponse":
    """select_candidate 시점에서 intent 별로 다음 게이트 자동 진행.

    - simulate + 주문번호 감지 → Java :8080 전체 설계 직진 (executed_full_design)
    - simulate, hypothesis     → Gate II (bundle_prepared)
    - impact                   → Gate III impact 직진
    - locate, explain          → Gate III lookup 직진 (mode=locate|explain)
    """
    # 우선 simulate intent + 주문번호 매칭 시 전체 설계
    if intent == "simulate" and user_query:
        order_no = extract_order_no(user_query)
        if order_no:
            logger.info("full design 분기: %s", order_no)
            return await _execute_full_design(
                session_id=session_id, order_no=order_no,
            )

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
        # location 이 mock 등에서 None 일 수 있어 stub 으로 채움
        from backend.section3.agents.multiturn.schemas import CodeLocation
        location = selected.location or CodeLocation(
            file_path="(unknown)", line_start=0, line_end=0,
        )
        action_ref = ActionRef(
            action_id=selected.action_id,
            code_method_fqn=selected.code_method_fqn,
            repo_id=sess.repo_id,
            location=location,
        )

        return await _proceed_from_target(
            session_id=session_id, intent=intent, target=action_ref,
            repo_id=sess.repo_id,
            ontology_client=ontology_client,
            conditions=target.conditions,
            user_query=sess.user_query,
        )

    # ── run_full_design — 사용자가 BundlePreview 에서 명시적으로 전체 설계 실행 ──
    if req.action == "run_full_design":
        order_no = req.order_no or extract_order_no(sess.user_query or "")
        if not order_no:
            raise HTTPException(
                status_code=422,
                detail="order_no 가 필요합니다. ORD20260510001 같은 형식.",
            )
        return await _execute_full_design(
            session_id=session_id, order_no=order_no,
            cmp_cd=req.cmp_cd or "K", org_cd=req.org_cd or "1",
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

    # ── compare_with_overrides (변경 전·후 두 번 실행 + field diff) ─────
    if req.action == "compare_with_overrides":
        if not req.overrides:
            raise HTTPException(
                status_code=422, detail="overrides 가 비어있음 — 변경 후 값을 보내야",
            )
        replay = p.replay_session(session_id)
        if not replay:
            raise HTTPException(status_code=404, detail="session 없음")
        bundle_decision = next(
            (d for d in reversed(replay.decisions) if d.gate_kind == "bundle_prepared"),
            None,
        )
        if bundle_decision is None:
            raise HTTPException(
                status_code=409,
                detail="비교할 bundle 이 없습니다 — select_candidate 부터 진행",
            )
        bundle = TypeAdapter(GateBundle).validate_python(bundle_decision.payload)
        try:
            cmp = await compare_runs(
                bundle=bundle, overrides=req.overrides, repo_id=sess.repo_id,
            )
            payload = cmp.model_dump()
            payload["kind"] = "executed_compare"
        except Exception as e:  # noqa: BLE001
            logger.exception("compare_runs 실패")
            payload = {
                "kind": "executed_compare", "error": f"compare 실패: {e}",
                "method_fqn": bundle.target.code_method_fqn,
                "field_diffs": [], "summary": "실행 실패",
            }
        new_turn = p.add_gate_decision(
            session_id, gate_kind="executed", payload=payload,
        )
        p.update_session(session_id, status="done")
        return RespondResponse(
            session_id=session_id, turn_no=new_turn,
            next_gate="done", payload=payload,
            message=payload.get("summary", "compare 완료"),
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


class GraphNode(BaseModel):
    id: str
    label: str
    kind: Literal["term", "action", "code_method", "code_type", "rule"]


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str  # "calls" | "realizes" | "uses_term" | "constrains" | "delegates"


class GraphResponse(BaseModel):
    target_fqn: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    note: str = ""


@router.get("/graph/{session_id}", response_model=GraphResponse)
async def get_graph(
    session_id: str,
    ontology_client: OntologyClient = Depends(get_ontology_client),
) -> GraphResponse:
    """현재 세션의 target method 주변 ontology 그래프.

    가장 최근 target_selected 의 selected 또는 첫 후보 method 를 중심으로
    caller_graph + realizations + declared_on_term + business_rules 까지
    1-hop 노드/엣지 합성.
    """
    rep = p.replay_session(session_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="session not found")
    target_decision = None
    for d in reversed(rep.decisions):
        if d.gate_kind == "target_selected":
            target_decision = d
            break
    if target_decision is None:
        return GraphResponse(target_fqn="", note="아직 target 이 선택되지 않음")

    cands = target_decision.payload.get("candidates") or []
    if not cands:
        return GraphResponse(target_fqn="", note="후보 없음")
    sel_idx = target_decision.user_response and target_decision.user_response.get("selected_index")
    cand = cands[sel_idx if isinstance(sel_idx, int) else 0]
    target_fqn = cand.get("code_method_fqn", "")
    target_label = cand.get("label", target_fqn)
    declared_term = cand.get("declared_on_term")

    nodes: list[GraphNode] = [
        GraphNode(id=target_fqn, label=target_label, kind="code_method"),
    ]
    edges: list[GraphEdge] = []

    # ── 1-hop callers ────────────────────────────────────────────────
    try:
        graph_resp = await ontology_client.get_caller_graph(target_fqn, repo_id=rep.session.repo_id)
        cg = graph_resp.data
        if cg is not None and hasattr(cg, "model_dump"):
            cg_dict = cg.model_dump()
        else:
            cg_dict = cg or {}
        for c in (cg_dict.get("callers") or [])[:8]:
            cfqn = c.get("method_fqn") or c.get("fqn")
            if cfqn and cfqn != target_fqn:
                nodes.append(GraphNode(id=cfqn, label=cfqn.split(".")[-1][:40], kind="code_method"))
                edges.append(GraphEdge(source=cfqn, target=target_fqn, kind="calls"))
        for c in (cg_dict.get("callees") or [])[:8]:
            cfqn = c.get("method_fqn") or c.get("fqn")
            if cfqn and cfqn != target_fqn:
                nodes.append(GraphNode(id=cfqn, label=cfqn.split(".")[-1][:40], kind="code_method"))
                edges.append(GraphEdge(source=target_fqn, target=cfqn, kind="calls"))
    except Exception as e:  # noqa: BLE001
        logger.warning("get_caller_graph 실패: %s", e)

    # ── declared_on_term ────────────────────────────────────────────
    if declared_term:
        nodes.append(GraphNode(id=declared_term, label=declared_term.split(".")[-1], kind="term"))
        edges.append(GraphEdge(source=target_fqn, target=declared_term, kind="uses_term"))

    return GraphResponse(
        target_fqn=target_fqn,
        nodes=nodes, edges=edges,
        note=f"{len(nodes)} nodes · {len(edges)} edges",
    )


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
