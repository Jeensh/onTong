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
from backend.section3.agents.simulation import domain_data
from backend.section3.agents.simulation.hypothesis_workflow import run_hypothesis
from backend.section3.agents.simulation.suggested_questions import (
    extract_korean_tokens, generate_suggestions, lookup_terms,
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
        "run_full_design",
        "confirm_change_target", "pick_order",  # impact 단계화
        "abort",
    ]
    selected_index: int | None = None
    intent: str | None = None  # clarify_intent 시
    overrides: dict | None = None  # compare_with_overrides 시 (변경 후 값)
    order_no: str | None = None    # run_full_design / pick_order 시
    cmp_cd: str | None = None
    org_cd: str | None = None
    change_target: dict | None = None  # confirm_change_target 시 (table/column/before/after)
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
    exclude_fqns: set[str] | None = None,
    top_n: int = 12,
) -> dict:
    """multiturn 의 build_gate_i 호출 → GateTarget payload (dict).

    후처리:
    1) test 메서드 후보 제거 (*Test 클래스 / @Test).
    2) exclude_fqns 에 있는 code_method_fqn 제거 ("다른 후보" 재호출 시).
    3) recommended_index 첫 번째 살아남은 후보로 재조정.
    4) top_n 을 충분히 크게 (12) 잡아 필터링 후에도 후보가 남도록.
    """
    target = await build_gate_i(
        user_query=user_query,
        repo_id=repo_id,
        classifier=classifier,
        ontology_client=ontology_client,
        top_n=top_n,
    )
    payload = target.model_dump()
    candidates = payload.get("candidates") or []
    if candidates:
        filtered = [c for c in candidates if not _is_test_candidate(c)]
        n_test = len(candidates) - len(filtered)
        n_excl = 0
        if exclude_fqns:
            before = len(filtered)
            filtered = [
                c for c in filtered
                if (c.get("code_method_fqn") or "") not in exclude_fqns
            ]
            n_excl = before - len(filtered)
        # 최종 적용
        payload["candidates"] = filtered[:5]  # 보여줄 후보는 상위 5개로 다시 cap
        payload["recommended_index"] = 0 if filtered else None
        if n_test:
            payload["_filtered_test_count"] = n_test
        if n_excl:
            payload["_excluded_count"] = n_excl

    # 자연어 query 의 한국어 토큰을 ontology business_terms 와 매핑 — 사용자에게
    # "감지된 용어" surface
    detected_terms = lookup_terms(extract_korean_tokens(user_query), repo_id=repo_id)
    if detected_terms:
        payload["_detected_terms"] = [
            {"token": d.token, "term_fqn": d.term_fqn, "label": d.label,
             "definition": d.definition}
            for d in detected_terms
        ]
    return payload


def _collect_seen_fqns(session_id: str) -> set[str]:
    """현 세션의 모든 이전 target_selected payload 에서 candidate fqn 추출.

    'request_other' 시 같은 후보 재노출 방지.
    """
    seen: set[str] = set()
    rep = p.replay_session(session_id)
    if rep is None:
        return seen
    for d in rep.decisions:
        if d.gate_kind != "target_selected":
            continue
        for c in (d.payload.get("candidates") or []):
            fqn = (c.get("code_method_fqn") or "").strip()
            if fqn:
                seen.add(fqn)
    return seen


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
        # 풍부화 — 사용자 질문에서 변경 대상·매칭 주문·관련 룰 추출
        try:
            _enrich_impact_payload(payload, user_query=user_query or "", repo_id=repo_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("impact payload 풍부화 실패: %s", e)
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
    """세션 생성 + Gate I (intent 분류 + 후보 검색).

    intent 별 fast-path:
      - simulate + ORD pattern → full_design 직진 (Java :8080 호출)
      - hypothesis → run_hypothesis 직진 (단계화 카드)
      - explain / locate → 자동 첫 후보 pick → executed 직진
      - simulate (no ORD) / impact → 후보 carousel (사용자 선택 필요)
      - ambiguous → 명확화 카드
    """
    sid = p.start_session(repo_id=req.repo_id, user_query=req.user_query)
    payload = await _build_target_payload(
        user_query=req.user_query, repo_id=req.repo_id,
        classifier=classifier, ontology_client=ontology_client,
    )
    intent = payload.get("intent", "ambiguous")

    # ── LLM 분류 보정: "신규 X 추가" / "추가되면" 패턴 → hypothesis 강제 ──
    import re as _re
    if _re.search(r"신규\s*\S+\s*(추가|들어오)|새\s*\S+\s*(추가|들어오)|"
                  r"가\s*추가되면|이\s*추가되면", req.user_query):
        if intent != "hypothesis":
            logger.info("hypothesis pattern detected, override intent %s→hypothesis", intent)
            intent = "hypothesis"
            payload["intent"] = "hypothesis"
            payload["_intent_overridden"] = True
    p.update_session(sid, intent=intent)
    turn_no = p.add_gate_decision(sid, gate_kind="target_selected", payload=payload)
    logger.info(
        "simulation.start sid=%s turn=%s intent=%s candidates=%s",
        sid, turn_no, intent, len(payload.get("candidates", [])),
    )

    # ── intent 별 fast-path: 후보 carousel 의미 없는 intent 는 자동 진행 ──

    # 1) simulate + 주문번호 감지 → 전체 설계 직진
    if intent == "simulate" and extract_order_no(req.user_query):
        order_no = extract_order_no(req.user_query)
        if order_no:
            r = await _execute_full_design(session_id=sid, order_no=order_no)
            return StartResponse(
                session_id=sid, turn_no=r.turn_no, next_gate="done",
                payload=r.payload, message=r.message,
            )

    # 2) hypothesis → 자동으로 hypothesis_workflow 호출 (default params)
    if intent == "hypothesis":
        # 후보는 surface 하되 곧 hypothesis 결과로 덮어쓰기
        hyp_payload = await _execute_hypothesis_from_query(
            session_id=sid, user_query=req.user_query,
        )
        return StartResponse(
            session_id=sid,
            turn_no=hyp_payload["_turn_no"],
            next_gate="done", payload=hyp_payload["_payload"],
            message=f"가설 분석 완료 — 4-step workflow 실행",
        )

    # 3) explain / locate 후보 0건 — ontology 검색이 안 잡혔어도 lookup 시도 가능하도록
    #    가상 ActionRef 로 fallback (executed_lookup 이 빈 결과 + 메시지로 응답)
    if intent in ("explain", "locate") and not payload.get("candidates"):
        from backend.section3.agents.multiturn.schemas import CodeLocation as _CL
        action_ref = ActionRef(
            action_id=f"virtual.{intent}.fallback",
            code_method_fqn="",
            repo_id=req.repo_id,
            location=_CL(file_path="(no match)", line_start=0, line_end=0),
        )
        p.update_user_response(sid, turn_no, {
            "action": "select_candidate", "selected_index": -1, "auto": True,
            "note": "no candidate — fallback empty target",
        })
        r = await _proceed_from_target(
            session_id=sid, intent=intent, target=action_ref,
            repo_id=req.repo_id, ontology_client=ontology_client,
            conditions=[], user_query=req.user_query,
        )
        return StartResponse(
            session_id=sid, turn_no=r.turn_no, next_gate=r.next_gate,
            payload=r.payload or {}, message=r.message,
        )

    # 4) explain / locate → 자동 첫 후보 pick (사용자 후보 선택 의미 없음)
    if intent in ("explain", "locate") and payload.get("candidates"):
        first = payload["candidates"][0]
        from backend.section3.agents.multiturn.schemas import CodeLocation
        action_ref = ActionRef(
            action_id=first.get("action_id", ""),
            code_method_fqn=first.get("code_method_fqn", ""),
            repo_id=req.repo_id,
            location=CodeLocation(**first["location"]) if first.get("location") else
                     CodeLocation(file_path="(unknown)", line_start=0, line_end=0),
        )
        # update_user_response 로 자동 select 기록 (UX 일관성)
        p.update_user_response(sid, turn_no, {
            "action": "select_candidate", "selected_index": 0, "auto": True,
        })
        r = await _proceed_from_target(
            session_id=sid, intent=intent, target=action_ref,
            repo_id=req.repo_id, ontology_client=ontology_client,
            conditions=[], user_query=req.user_query,
        )
        return StartResponse(
            session_id=sid, turn_no=r.turn_no, next_gate=r.next_gate,
            payload=r.payload or {}, message=r.message,
        )

    # 5) 기본: 후보 carousel 표시 (simulate no ORD / impact / ambiguous)
    next_gate = _next_gate_from_target(payload)
    return StartResponse(
        session_id=sid, turn_no=turn_no, next_gate=next_gate, payload=payload,
        message=(
            "의도 명확화 필요" if next_gate == "ambiguous_clarification"
            else f"intent={intent} · 후보 {len(payload.get('candidates', []))} 건"
        ),
    )


def _detect_intent_focus(user_query: str) -> str:
    """질문에서 '어떤 X 가 영향?' 의 X 추출.

    Returns one of: step / method / action / api / rule / order / code (default).
    """
    q = user_query.lower()
    # 우선순위: 구체 → 추상
    patterns = [
        ("step", ["step", "단계"]),
        ("api",  ["api", "endpoint", "rest", "controller"]),
        ("action", ["action", "동작", "액션"]),
        ("method", ["method", "메서드", "메소드", "함수"]),
        ("rule", ["rule", "룰", "규칙", "조건", "business rule", "business_rule"]),
        ("order", ["주문", "order_no", "ord2", "ord3"]),
    ]
    for kind, kws in patterns:
        if any(kw in q for kw in kws):
            return kind
    return "code"


def _enrich_impact_payload(payload: dict, *, user_query: str, repo_id: str) -> None:
    """impact intent 의 payload 에 (detected_terms, target_change, affected_orders,
    affected_rules) 를 in-place 추가.

    user_query 에서:
      - table 이름 / 한국어 alias 매칭 (CAST_SPEC, ORDER_OS, EDGING_GROUP 등)
      - column 키워드 (두께/단중/폭/길이)
      - 변경값 패턴 ("240으로 변경", "0.5→0.3")
      - 매칭 주문 (column 값이 일치하는 ORDER_*) + business_rules
    """
    import re, json as _json
    from sqlalchemy import select
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessRuleRow

    # 1) detected_terms (이미 _build_target_payload 에서 추가됐을 수도 있음)
    if "_detected_terms" not in payload:
        from backend.section3.agents.simulation.suggested_questions import (
            extract_korean_tokens, lookup_terms,
        )
        toks = extract_korean_tokens(user_query)
        detected = lookup_terms(toks, repo_id=repo_id)
        payload["_detected_terms"] = [
            {"token": d.token, "term_fqn": d.term_fqn, "label": d.label, "definition": d.definition}
            for d in detected
        ]

    # 2) target_change — table.column + before/after 추출
    # 한국어 alias → table.column 가벼운 매핑
    TBL_ALIAS = {
        "연주설비사양": ("CAST_SPEC", "SLAB_THICKNESS"),
        "연주설비사양기준": ("CAST_SPEC", "SLAB_THICKNESS"),
        "열연사양": ("HR_SPEC", None),
        "EDGING": ("EDGING_GROUP", None),
        "edging": ("EDGING_GROUP", None),
        "단중하한": ("HR_MIN_WGT", "MIN_WGT"),
        "단중상한": ("HR_MAX_WGT", "MAX_WGT"),
        "실수율": ("SD_PRODUCTIVITY_STD", "PRODUCTIVITY"),
        "productivity": ("SD_PRODUCTIVITY_STD", "PRODUCTIVITY"),
        "고객표준": ("CUSTOMER_STD", None),
    }
    COL_ALIAS = {
        "두께": "SLAB_THICKNESS",
        "단중": "WGT",       # 어느 wgt 인지는 컨텍스트
        "폭": "WIDTH",
        "길이": "LENGTH",
    }
    target_table: str | None = None
    target_column: str | None = None
    target_product: str | None = None
    for kw, (tbl, col) in TBL_ALIAS.items():
        if kw in user_query:
            target_table = tbl
            target_column = col
            break
    for kw, col in COL_ALIAS.items():
        if kw in user_query and target_column is None:
            target_column = col
            break
    # 제품 분기 (COIL / FS)
    m_prod = re.search(r"\b(COIL|FS)\b", user_query)
    if m_prod:
        target_product = m_prod.group(1)
    # 변경값 — "240 으로", "0.5 → 0.3", "0.95 배"
    after_val: str | None = None
    before_val: str | None = None
    m_change = re.search(r"(\d+(?:\.\d+)?)\s*(?:으?로|→|->)\s*변경?", user_query)
    if m_change:
        after_val = m_change.group(1)
    if not after_val:
        m_arrow = re.search(r"(\d+(?:\.\d+)?)\s*(?:→|->)\s*(\d+(?:\.\d+)?)", user_query)
        if m_arrow:
            before_val = m_arrow.group(1); after_val = m_arrow.group(2)
    if not after_val:
        m_for = re.search(r"(\d+(?:\.\d+)?)\s*으?로", user_query)
        if m_for:
            after_val = m_for.group(1)
    # 현재값 — seed 에서 first row
    if target_table and target_column and before_val is None:
        try:
            rows = domain_data.list_rows(target_table, limit=20)
            for r in rows:
                v = r.values.get(target_column)
                if target_product and r.values.get("PRODUCT_CD") not in (target_product, None):
                    continue
                if v is not None:
                    before_val = str(v); break
        except Exception:
            pass
    if target_table or target_column or after_val:
        payload["_target_change"] = {
            "table": target_table or "?", "column": target_column or "?",
            "before": before_val, "after": after_val,
            "product": target_product,
            "note": "자연어에서 추출. 정확하지 않을 수 있으니 확인 필요." if not (target_table and target_column and after_val) else "",
        }

    # 3) 매칭 주문 — seed ORDER_OM × ORDER_QD join, target_product / target_term 기반
    matched_orders: list[dict] = []
    try:
        om_rows = domain_data.list_rows("ORDER_OM", limit=50)
        qd_rows_by_order: dict[str, dict] = {}
        for q in domain_data.list_rows("ORDER_QD", limit=50):
            qno = str(q.values.get("ORDER_NO"))
            qd_rows_by_order[qno] = q.values
        for om in om_rows:
            v = om.values
            order_no = str(v.get("ORDER_NO"))
            qd = qd_rows_by_order.get(order_no, {})
            if target_product and v.get("PRODUCT_CD") != target_product:
                continue
            matched_orders.append({
                "ORDER_NO": order_no,
                "GRADE_CD": qd.get("GRADE_CD"),
                "PRODUCT_CD": v.get("PRODUCT_CD"),
                "ORDER_WIDTH": v.get("ORDER_WIDTH"),
                "ORDER_LENGTH": v.get("ORDER_LENGTH"),
                "DESIGN_PEND_QTY": v.get("DESIGN_PEND_QTY"),
            })
    except Exception:
        pass
    if matched_orders:
        payload["_affected_orders"] = matched_orders

    # 4) 관련 business_rules — detected_term 의 fqn 이 terms_ref_json 안에 있으면
    detected_fqns: set[str] = set()
    for d in payload.get("_detected_terms") or []:
        fqn = (d.get("term_fqn") or "").strip()
        if fqn: detected_fqns.add(fqn)
    rules: list[dict] = []
    if detected_fqns:
        try:
            with session_scope() as s:
                rows = s.execute(
                    select(BusinessRuleRow).where(BusinessRuleRow.repo_id == repo_id)
                ).scalars().all()
                for r in rows:
                    try:
                        refs = _json.loads(r.terms_ref_json or "[]")
                    except Exception:
                        refs = []
                    if any(f in detected_fqns for f in refs):
                        rules.append({
                            "fqn": r.fqn, "severity": r.severity,
                            "statement": (r.statement or "")[:200],
                        })
                        if len(rules) >= 6: break
        except Exception:
            pass
    if rules:
        payload["_affected_rules"] = rules

    # 5) intent_focus — 질문에서 어떤 entity kind 를 묻는지
    focus = _detect_intent_focus(user_query)
    payload["_intent_focus"] = focus

    # 6) affected_actions — ontology actions 매칭 (detected_terms 와 연결된 action)
    try:
        from sqlalchemy import select
        from backend.modeling.persistence.database import session_scope as _ss
        from backend.modeling.mapping_layer.orm import ActionRow
        affected_actions: list[dict] = []
        if detected_fqns:
            with _ss() as s:
                rows = s.execute(
                    select(ActionRow).where(ActionRow.repo_id == repo_id)
                ).scalars().all()
                for r in rows:
                    if r.declared_on_term and r.declared_on_term in detected_fqns:
                        affected_actions.append({
                            "fqn": r.fqn, "label": r.label,
                            "kind": r.kind, "declared_on_term": r.declared_on_term,
                        })
                        if len(affected_actions) >= 8: break
        if affected_actions:
            payload["_affected_actions"] = affected_actions
    except Exception:
        pass

    # 7) affected_steps — code_methods 중 SdXxxAction 패턴 (slab-design 21-step)
    try:
        steps: list[dict] = []
        methods = payload.get("affected_methods") or []
        # SdXxxAction 클래스의 메서드 → step
        STEP_MAP = {
            "SdThicknessAction": 1, "SdWidthRangeAction": 2, "SdLengthRangeAction": 3,
            "SdFirstWeightAction": 4, "SdSecondWgtLowAction": 5, "SdSecondWgtHighAction": 6,
            "SdMaxSplitCountAction": 7, "SdSplitRangeAction": 8, "SdSlabCountAction": 9,
            "SdInitialSlabWgtAction": 10, "SdFinalWidthRangeAction": 16,
            "SdFinalLengthRangeAction": 17, "SdTargetWidthAction": 18,
            "SdTargetLengthAction": 19, "SdSlabSaveAction": 20,
        }
        seen_steps: set[int] = set()
        for m in methods:
            fqn = str(m.get("fqn", ""))
            for cls, step in STEP_MAP.items():
                if cls in fqn and step not in seen_steps:
                    seen_steps.add(step)
                    steps.append({"step": step, "action_class": cls, "method_fqn": fqn})
        if steps:
            payload["_affected_steps"] = sorted(steps, key=lambda x: x["step"])
    except Exception:
        pass

    # 8) affected_apis — Spring controller annotation 매칭 (간단 — controller fqn 추출)
    try:
        apis: list[dict] = []
        methods = payload.get("affected_methods") or []
        for m in methods:
            fqn = str(m.get("fqn", ""))
            if "Controller" in fqn or "controller" in fqn:
                apis.append({"controller": fqn.split(".")[-2] if "." in fqn else fqn,
                             "method_fqn": fqn})
        if apis:
            payload["_affected_apis"] = apis[:6]
    except Exception:
        pass


async def _execute_hypothesis_from_query(
    *, session_id: str, user_query: str,
) -> dict:
    """hypothesis intent 의 query 에서 grade / order 추출 후 run_hypothesis 호출.

    LLM 정확 추출은 후속 — 일단 정규식 + 기본값 fallback.
    """
    import re
    # 강종 패턴
    grade_match = re.search(r"\b(SS\d{2,4}|HC\d{2,4}[A-Z]?)\b", user_query)
    new_grade = grade_match.group(0) if grade_match else "SS500"
    # 주문번호
    order_no = extract_order_no(user_query) or "ORD20260510001"
    # multiplier
    mult_match = re.search(r"productivity\s*[×x*]\s*(\d+\.?\d*)", user_query, re.I)
    mult = float(mult_match.group(1)) if mult_match else 0.95
    if mult > 2: mult = mult / 100  # "5%" 같은 경우 0.05 → 0.95 로 변환은 사용자 입력 의도 다름. 단순 raw 사용.

    r = await run_hypothesis(
        base_grade="SS400", new_grade=new_grade,
        productivity_multiplier=mult, base_order_no=order_no,
    )
    payload = {
        "kind": "executed_hypothesis_workflow",
        "base_grade": r.base_grade, "new_grade": r.new_grade,
        "productivity_multiplier": r.productivity_multiplier,
        "base_order_no": r.base_order_no,
        "existing_productivity_rows": r.existing_productivity_rows,
        "existing_order_rows": r.existing_order_rows,
        "virtual_productivity_rows": r.virtual_productivity_rows,
        "virtual_order_rows": r.virtual_order_rows,
        "baseline_slab": r.baseline_slab,
        "baseline_trace": r.baseline_trace,
        "projected_slab": r.projected_slab,
        "diff_summary": r.diff_summary,
        "notes": r.notes,
    }
    new_turn = p.add_gate_decision(session_id, gate_kind="executed", payload=payload)
    p.update_session(session_id, status="done")
    return {"_turn_no": new_turn, "_payload": payload}


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
        # 'request_other' 일 때만 이전 후보 제외 (clarify_intent 는 다른 intent 라
        # 자연스럽게 다른 후보 set 이 나옴 → 굳이 제외 안 함)
        exclude = _collect_seen_fqns(session_id) if req.action == "request_other" else None
        payload = await _build_target_payload(
            user_query=query, repo_id=sess.repo_id,
            classifier=classifier, ontology_client=ontology_client,
            exclude_fqns=exclude,
        )
        new_intent = req.intent if req.action == "clarify_intent" else payload.get("intent")
        p.update_session(session_id, intent=new_intent)
        new_turn = p.add_gate_decision(
            session_id, gate_kind="target_selected", payload=payload,
        )
        n_excl = payload.get("_excluded_count", 0)
        cands_n = len(payload.get("candidates", []))
        msg = (
            f"재검색 — intent={payload.get('intent')} · 후보 {cands_n} 건"
            + (f" (이전 후보 {n_excl} 건 제외됨)" if n_excl else "")
            + (" — 새 후보 없음. 다른 질문을 시도해 보세요." if cands_n == 0 else "")
        )
        return RespondResponse(
            session_id=session_id, turn_no=new_turn,
            next_gate=_next_gate_from_target(payload),
            payload=payload, message=msg,
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


# ─────────────────────────────────────────────────────────────────────────────
# 도메인 데이터 surface — slab-design-real_v2 의 H2 schema + seed
# ─────────────────────────────────────────────────────────────────────────────


class DomainColumnView(BaseModel):
    name: str
    java_field: str = ""
    is_pk: bool = False
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    type_hint: str = ""


class DomainTableView(BaseModel):
    table_name: str
    jpa_class: str
    jpa_file: str
    category: str
    pk_columns: list[str]
    column_count: int
    row_count: int


class DomainTableDetail(BaseModel):
    table_name: str
    jpa_class: str
    jpa_file: str
    category: str
    columns: list[DomainColumnView]
    pk_columns: list[str]
    rows: list[dict]
    row_count_total: int


class SuggestedQuestionView(BaseModel):
    intent: str
    label: str
    query: str
    rationale: str = ""
    grounded_terms: list[dict] = Field(default_factory=list)


@router.get("/suggested_questions", response_model=list[SuggestedQuestionView])
async def list_suggested_questions(seed: int = 0) -> list[SuggestedQuestionView]:
    """JPO 한국어 주석 + business_terms + seed orders 기반 동적 예시 질문.

    같은 ontology snapshot 에서 같은 결과 (seed 고정). 클라이언트가 seed 를
    바꿔 호출하면 다른 set.
    """
    qs = generate_suggestions(seed=seed or None)
    out: list[SuggestedQuestionView] = []
    for q in qs:
        # 각 질문의 한국어 토큰을 ontology business_terms 와 매핑
        toks = extract_korean_tokens(q.query)
        detected = lookup_terms(toks)
        out.append(SuggestedQuestionView(
            intent=q.intent, label=q.label, query=q.query, rationale=q.rationale,
            grounded_terms=[
                {"token": d.token, "term_fqn": d.term_fqn, "label": d.label,
                 "definition": d.definition}
                for d in detected
            ],
        ))
    return out


class TermLookupRequest(BaseModel):
    text: str


class DetectedTermView(BaseModel):
    token: str
    term_fqn: str
    label: str
    definition: str = ""
    aliases: list[str] = Field(default_factory=list)


@router.post("/term_lookup", response_model=list[DetectedTermView])
async def term_lookup(req: TermLookupRequest) -> list[DetectedTermView]:
    """자연어 안의 한국어 토큰 → ontology business_terms 매핑.

    UI 에서 사용자가 query 입력 시 실시간으로 호출하면, "감지된 용어" 카드를
    pre-flight 로 surface 가능.
    """
    toks = extract_korean_tokens(req.text)
    detected = lookup_terms(toks)
    return [
        DetectedTermView(
            token=d.token, term_fqn=d.term_fqn, label=d.label,
            definition=d.definition, aliases=d.aliases or [],
        )
        for d in detected
    ]


class HypothesisRequest(BaseModel):
    base_grade: str = "SS400"
    new_grade: str = "SS500"
    productivity_multiplier: float = 0.95
    base_order_no: str = "ORD20260510001"


class HypothesisResponse(BaseModel):
    base_grade: str
    new_grade: str
    productivity_multiplier: float
    base_order_no: str
    existing_productivity_rows: list[dict]
    existing_order_rows: dict[str, dict]
    virtual_productivity_rows: list[dict]
    virtual_order_rows: dict[str, dict]
    baseline_slab: dict | None = None
    baseline_trace: list[dict] = Field(default_factory=list)
    projected_slab: dict | None = None
    diff_summary: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@router.post("/hypothesis/run", response_model=HypothesisResponse)
async def hypothesis_run(req: HypothesisRequest) -> HypothesisResponse:
    """신규 강종 추가 가설 — 4단계 결과를 한 번에 surface.

    1) 기존 grade 의 SD_PRODUCTIVITY_STD row 조회
    2) productivity_multiplier 로 가상 grade row 합성
    3) base_order 복제 → ORDER_QD.GRADE_CD 만 변경
    4) Java :8080 으로 base_order 실행 + projection 추론
    """
    r = await run_hypothesis(
        base_grade=req.base_grade, new_grade=req.new_grade,
        productivity_multiplier=req.productivity_multiplier,
        base_order_no=req.base_order_no,
    )
    return HypothesisResponse(
        base_grade=r.base_grade, new_grade=r.new_grade,
        productivity_multiplier=r.productivity_multiplier,
        base_order_no=r.base_order_no,
        existing_productivity_rows=r.existing_productivity_rows,
        existing_order_rows=r.existing_order_rows,
        virtual_productivity_rows=r.virtual_productivity_rows,
        virtual_order_rows=r.virtual_order_rows,
        baseline_slab=r.baseline_slab,
        baseline_trace=r.baseline_trace,
        projected_slab=r.projected_slab,
        diff_summary=r.diff_summary,
        notes=r.notes,
    )


class MethodBodyView(BaseModel):
    method_fqn: str
    body: str = ""
    file_path: str = ""
    line_start: int | None = None
    line_end: int | None = None
    annotations: list[str] = Field(default_factory=list)
    callers: list[str] = Field(default_factory=list)
    callees: list[str] = Field(default_factory=list)


@router.get("/method/body", response_model=MethodBodyView)
async def get_method_body(
    fqn: str, repo_id: str = "slab-design-real-v2",
    ontology_client: OntologyClient = Depends(get_ontology_client),
) -> MethodBodyView:
    """impact intent 의 affected method 행 click 시 코드 본문 + 1-hop graph 확장."""
    body_text = ""
    file_path = ""
    line_start = None
    line_end = None
    callers: list[str] = []
    callees: list[str] = []
    annotations: list[str] = []

    try:
        body_r = await ontology_client.get_method_body(fqn, repo_id=repo_id)
        body_text = body_r.data or ""
    except Exception as e:  # noqa: BLE001
        logger.warning("get_method_body 실패: %s", e)

    # 우리 SQLite ontology.db 에서 직접 meta 보완
    try:
        from sqlalchemy import select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.code_layer.orm import CodeMethodRow
        with session_scope() as s:
            row = s.execute(
                select(CodeMethodRow).where(
                    CodeMethodRow.fqn == fqn,
                    CodeMethodRow.repo_id == repo_id,
                )
            ).scalar_one_or_none()
            if row:
                if not body_text and row.body_text:
                    body_text = row.body_text
                line_start = row.line_start
                line_end = row.line_end
                try:
                    import json
                    annotations = json.loads(row.annotations_json or "[]")
                except Exception:
                    pass
    except Exception as e:  # noqa: BLE001
        logger.warning("CodeMethod 조회 실패: %s", e)

    # callers / callees (1-hop)
    try:
        cg = await ontology_client.get_caller_graph(fqn, repo_id=repo_id)
        cg_dict = cg.data.model_dump() if cg.data and hasattr(cg.data, "model_dump") else (cg.data or {})
        callers = [c.get("method_fqn") or c.get("fqn") or "" for c in (cg_dict.get("callers") or [])][:10]
        callees = [c.get("method_fqn") or c.get("fqn") or "" for c in (cg_dict.get("callees") or [])][:10]
        callers = [c for c in callers if c]
        callees = [c for c in callees if c]
    except Exception as e:  # noqa: BLE001
        logger.warning("get_caller_graph 실패: %s", e)

    return MethodBodyView(
        method_fqn=fqn, body=body_text, file_path=file_path,
        line_start=line_start, line_end=line_end,
        annotations=annotations, callers=callers, callees=callees,
    )


@router.get("/data/tables", response_model=list[DomainTableView])
async def list_domain_tables() -> list[DomainTableView]:
    """slab-design-real_v2 의 JPA Entity 기준 table 목록 + seed row 수."""
    out: list[DomainTableView] = []
    for t in domain_data.list_tables():
        out.append(DomainTableView(
            table_name=t.table_name, jpa_class=t.jpa_class,
            jpa_file=t.jpa_file, category=t.category,
            pk_columns=t.pk_columns, column_count=len(t.columns),
            row_count=domain_data.table_row_count(t.table_name),
        ))
    return out


@router.get("/data/table/{table_name}", response_model=DomainTableDetail)
async def get_domain_table(table_name: str, limit: int = 100) -> DomainTableDetail:
    """단일 table 의 schema + seed rows."""
    t = domain_data.get_table(table_name)
    if t is None:
        raise HTTPException(status_code=404, detail=f"table not found: {table_name}")
    rows = domain_data.list_rows(t.table_name, limit=limit)
    return DomainTableDetail(
        table_name=t.table_name, jpa_class=t.jpa_class, jpa_file=t.jpa_file,
        category=t.category,
        columns=[
            DomainColumnView(
                name=c.name, java_field=c.java_field, is_pk=c.is_pk,
                length=c.length, precision=c.precision, scale=c.scale,
                type_hint=c.type_hint,
            )
            for c in t.columns
        ],
        pk_columns=t.pk_columns,
        rows=[r.values for r in rows],
        row_count_total=domain_data.table_row_count(t.table_name),
    )


class SessionSummary(BaseModel):
    session_id: str
    repo_id: str
    intent: str | None = None
    status: str
    user_query: str | None = None
    created_at: str
    last_activity_at: str


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    ok = p.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return {"deleted": session_id}


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(limit: int = 30) -> list[SessionSummary]:
    """최근 대화 이력 list. 사용자가 과거 대화로 재진입 가능."""
    sessions = p.list_sessions(limit=limit)
    return [
        SessionSummary(
            session_id=s.id, repo_id=s.repo_id, intent=s.intent,
            status=s.status, user_query=s.user_query,
            created_at=s.created_at.isoformat(),
            last_activity_at=s.last_activity_at.isoformat(),
        )
        for s in sessions
    ]


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
