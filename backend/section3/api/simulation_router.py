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
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
from backend.section3.agents.simulation.impact_compare import compare_impact_slab
from backend.section3.agents.simulation.new_standard_workflow import run_new_standard_workflow
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
    # 사용자 관점 — "business" = 현업 (코드 카드 hide, 데이터·결과 중심),
    # "it" = IT (기존 default, 코드/디버깅 정보 모두 표시).
    perspective: Literal["business", "it"] = "it"
    # 결과 형태 — "data_only" = 데이터·요약만, "code_and_data" = 둘 다, "auto" = intent 별 default
    result_mode: Literal["auto", "data_only", "code_and_data"] = "auto"


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
             "definition": d.definition, "aliases": d.aliases or []}
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
        # affected_methods 에서 @Test / *Test 클래스 제거
        if payload.get("affected_methods"):
            payload["affected_methods"] = [
                m for m in payload["affected_methods"]
                if not _is_test_candidate({"code_method_fqn": m.get("fqn", "")})
            ]
        # 풍부화 — 사용자 질문에서 변경 대상·매칭 주문·관련 룰 추출
        try:
            _enrich_impact_payload(payload, user_query=user_query or "", repo_id=repo_id)
            # affected_methods 0건일 때 related methods 로 fallback (사용자 요구 2026-05-25)
            _attach_related_methods_fallback(payload, repo_id=repo_id)
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
        # locate 보강 — 추가 매칭 위치 + 각 위치의 본문/line range
        if intent == "locate":
            try:
                await _enrich_locate_payload(
                    payload, user_query=user_query or "", repo_id=repo_id,
                    ontology_client=ontology_client,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("locate payload 보강 실패: %s", e)
        # explain 보강 — atomic term 직접 답변 + ontology fan-out
        if intent == "explain":
            # _detected_terms 가 payload 안에 없으면 _build_target_payload 의 결과에서
            # 가져오기 — _proceed_from_target 호출자가 이미 채워준다. 안전 fallback:
            try:
                from backend.section3.agents.simulation.suggested_questions import (
                    extract_korean_tokens, lookup_terms,
                )
                if "_detected_terms" not in payload and user_query:
                    dts = lookup_terms(extract_korean_tokens(user_query), repo_id=repo_id)
                    if dts:
                        payload["_detected_terms"] = [
                            {"token": d.token, "term_fqn": d.term_fqn, "label": d.label,
                             "definition": d.definition, "aliases": d.aliases or []}
                            for d in dts
                        ]
                # Q1 — 단중 영향 변수 카탈로그 (우선)
                catalog_done = await _enrich_explain_weight_catalog(
                    payload, user_query=user_query or "", repo_id=repo_id,
                )
                # 일반 term-first 답변 — catalog 가 안 채워졌을 때만
                if not catalog_done:
                    await _enrich_explain_payload(
                        payload, user_query=user_query or "", repo_id=repo_id,
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning("explain payload 보강 실패: %s", e)
    else:
        payload = {
            "kind": "executed_unknown",
            "intent": intent,
            "target": target.model_dump(),
            "note": "지원되지 않는 intent — clarify_intent 로 재진입",
        }

    # 2026-05-25 — detected_terms 모든 intent 분기에서 보장 (explain 이외에도 보강)
    if "_detected_terms" not in payload and user_query:
        try:
            from backend.section3.agents.simulation.suggested_questions import (
                extract_korean_tokens, lookup_terms,
            )
            dts = lookup_terms(extract_korean_tokens(user_query), repo_id=repo_id)
            if dts:
                payload["_detected_terms"] = [
                    {"token": d.token, "term_fqn": d.term_fqn, "label": d.label,
                     "definition": d.definition, "aliases": d.aliases or []}
                    for d in dts
                ]
        except Exception as e:  # noqa: BLE001
            logger.warning("detected_terms 보강 실패: %s", e)

    # pipeline timeline 첨부 (2026-05-23) — 순차 진행 시각화용
    try:
        payload["_pipeline_steps"] = _compose_pipeline_trace(
            intent=intent, user_query=user_query or "", payload=payload,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("pipeline trace 합성 실패: %s", e)

    # 21-step 카탈로그 매칭 (2026-05-25) — 질문 관련 step 자동 surface
    _attach_walkthrough_steps(payload, user_query=user_query or "")

    # LLM 분석 답변 첨부 (2026-05-23) — 줄글 한글 분석
    try:
        payload["_llm_analysis"] = _compose_llm_analysis(
            intent=intent, user_query=user_query or "", payload=payload,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("llm analysis 합성 실패: %s", e)

    # 2026-05-25: 동적 UI block 첨부 — LLM 이 질문별 최적 block 결정
    #   (metric_grid / table / sweep_chart / comparison / step_callout / formula / text)
    try:
        from backend.section3.agents.simulation.dynamic_blocks import compose_dynamic_blocks
        payload["_dynamic_blocks"] = compose_dynamic_blocks(
            intent=intent, user_query=user_query or "", payload=payload,
        )
        # 슬랩→Slab 일괄 (LLM 출력 정규화)
        payload["_dynamic_blocks"] = _enforce_slab_korean(payload["_dynamic_blocks"])
        if payload.get("_llm_analysis"):
            payload["_llm_analysis"] = _enforce_slab_korean(payload["_llm_analysis"])
        if payload.get("_walkthrough_insight"):
            payload["_walkthrough_insight"] = _enforce_slab_korean(payload["_walkthrough_insight"])
    except Exception as e:  # noqa: BLE001
        logger.warning("dynamic_blocks 합성 실패: %s", e)

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

    # ── LLM 분류 보정 ──
    import re as _re
    q = req.user_query
    # 1) hypothesis: "신규 X 추가" / "들어오면" / "추가되면"
    has_new_keyword = bool(_re.search(r"\b(신규|새|new|추가|추가되면|들어오면)\b", q, _re.I)) \
                      or any(kw in q for kw in ("신규", "새 ", "추가되면", "추가된다면", "들어오면"))
    if has_new_keyword and intent != "hypothesis":
        logger.info("hypothesis pattern detected, override intent %s→hypothesis", intent)
        intent = "hypothesis"
        payload["intent"] = "hypothesis"
        payload["_intent_overridden"] = True

    # 2) explain: "관련된 항목", "관련 있는", "관련 항목", "관련된 게", "뭐가 있어",
    #    "어떤게 있어", "무엇이 있나", "뭐야", "무엇이야", "이란?" 등 → explain 강제
    #    + "영향을 주는 변수", "어떤 것들이 있어", "변수가 무엇" — 카탈로그 질문
    #    (locate 의 "어디" / "위치" 와 구별 — 후자는 locate 유지)
    has_locate_keyword = bool(_re.search(r"(어디|어느 파일|위치|어디에|어디서)", q))
    has_explain_keyword = bool(_re.search(
        r"(관련된 항목|관련 있는|관련된 게|관련 항목|뭐가 있|어떤게 있|무엇이 있|뭐야|무엇이야|뭐죠|이란|이 뭐|는 뭐"
        r"|영향을 주는 변수|어떤 것들이 있|변수가 무엇|변수가 뭐|어떤 변수)", q
    ))
    if has_explain_keyword and not has_locate_keyword and intent not in ("explain", "hypothesis"):
        logger.info("explain pattern detected, override intent %s→explain", intent)
        intent = "explain"
        payload["intent"] = "explain"
        payload["_intent_overridden"] = True

    # 3) locate: "어디" / "위치" 명시 + "뭐야" 없음 → locate 보강 (이미 locate 면 유지)
    if has_locate_keyword and not has_explain_keyword and intent not in ("locate", "hypothesis"):
        logger.info("locate pattern detected, override intent %s→locate", intent)
        intent = "locate"
        payload["intent"] = "locate"
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

    # 2) hypothesis → 자동으로 hypothesis_workflow 호출
    #    단, 진짜 "신규 X 추가" 시그널 (신규/새/추가/들어오) 이 있을 때만 new-standard workflow 로.
    #    그 외 hypothesis (조건/sweep 류 — "X 를 N 만큼 증가시키면 ...") 는
    #    explain 으로 demote 해서 generic ontology fan-out + walkthrough 가
    #    질문 맥락에 맞게 동적으로 응답하도록 한다. (2026-05-25 hardcoded 답변 방지)
    if intent == "hypothesis":
        has_new_entity_signal = any(
            kw in q for kw in ("신규", "새 ", "새로운", "추가", "들어오", "도입")
        )
        if has_new_entity_signal:
            hyp_payload = await _execute_hypothesis_from_query(
                session_id=sid, user_query=req.user_query,
            )
            _attach_walkthrough_steps(hyp_payload["_payload"], user_query=req.user_query)
            return StartResponse(
                session_id=sid,
                turn_no=hyp_payload["_turn_no"],
                next_gate="done", payload=hyp_payload["_payload"],
                message=f"가설 분석 완료 — 4-step workflow 실행",
            )
        # 신규 시그널 없으면 → explain 으로 demote (generic ontology + walkthrough)
        logger.info(
            "hypothesis without 'new entity' signal — demote to explain (avoid hardcoded fallback)"
        )
        intent = "explain"
        payload["intent"] = "explain"
        payload["_intent_overridden"] = True
        payload["_demoted_from_hypothesis"] = True
        # ★ session 의 intent 도 explain 으로 갱신 — frontend 의 replay.intent 가
        #   여전히 "hypothesis" 였다면 _HypothesisView (신규 강종 SS500 카드) 가 떠버림.
        p.update_session(sid, intent="explain")

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
        # 2026-05-25 — detected_terms 와 매칭되는 후보를 우선 선택
        #   (예: "slab 분할수" → split / split_count 키워드 가진 후보 우선)
        cands = payload["candidates"]
        dts = payload.get("_detected_terms") or []
        keywords: list[str] = []
        for dt in dts:
            label = (dt.get("label") or "").lower()
            fqn = (dt.get("term_fqn") or "").lower()
            aliases = dt.get("aliases") or []
            for s in [label, fqn] + list(aliases):
                s = str(s).lower()
                # 의미있는 키워드만 (공통 단어 제외)
                if s and len(s) >= 2 and s not in {"slab", "코드", "term"}:
                    # fqn 의 마지막 segment 우선
                    keywords.append(s.split(".")[-1])
        def _score(c: dict) -> int:
            blob = (str(c.get("action_id", "")) + " " + str(c.get("code_method_fqn", "")) + " "
                    + str(c.get("action_label", "")) + " " + str(c.get("action_kind", ""))).lower()
            sc = 0
            for kw in keywords:
                if kw and kw in blob:
                    sc += len(kw)  # 긴 키워드 매칭이 더 강한 매치
            return sc
        if keywords:
            cands = sorted(cands, key=_score, reverse=True)
            best = cands[0]
            best_idx = payload["candidates"].index(best) if best in payload["candidates"] else 0
            first = best
            logger.info(
                "locate/explain — detected term keywords %s → 후보 재정렬, best idx=%s (%s)",
                keywords[:5], best_idx, first.get("code_method_fqn", "")[:80],
            )
        else:
            first = cands[0]
            best_idx = 0
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
            "action": "select_candidate", "selected_index": best_idx, "auto": True,
            "score_keywords": keywords[:5] if keywords else [],
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

    # 4-b) impact + Q2 (Edging) / Q3 (포장단중·설계대기량) trigger → 자동 fast-path
    #      사용자 질문이 카탈로그/sweep 류라 candidates 가 비거나 의미 없음. dummy
    #      ActionRef 로 _proceed_from_target 호출 → _enrich_impact_payload 가
    #      _edging_impact / _q3_interactive / _weight_sweep 채움.
    if intent == "impact":
        q = req.user_query
        is_edging = (
            ("Edging" in q or "edging" in q or "EDGING" in q or "EDGING_GROUP" in q)
            and any(t in q for t in ("능력", "상한", "하한", "상하한", "변경"))
        )
        is_q3 = any(t in q for t in ("포장단중", "설계대기량", "DESIGN_PEND_QTY", "ORDER_WGT"))
        if (is_edging or is_q3) and not payload.get("candidates"):
            from backend.section3.agents.multiturn.schemas import CodeLocation as _CL2
            action_ref = ActionRef(
                action_id=f"virtual.impact.{'edging' if is_edging else 'q3'}",
                code_method_fqn="",
                repo_id=req.repo_id,
                location=_CL2(file_path="(no match)", line_start=0, line_end=0),
            )
            p.update_user_response(sid, turn_no, {
                "action": "select_candidate", "selected_index": -1, "auto": True,
                "note": f"impact fast-path: {'edging' if is_edging else 'q3'}",
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
        # candidates 가 있으면 첫 후보 자동 pick + executed 진행 (Edging/Q3 트리거 한정)
        if (is_edging or is_q3) and payload.get("candidates"):
            first = payload["candidates"][0]
            from backend.section3.agents.multiturn.schemas import CodeLocation as _CL3
            action_ref = ActionRef(
                action_id=first.get("action_id", ""),
                code_method_fqn=first.get("code_method_fqn", ""),
                repo_id=req.repo_id,
                location=_CL3(**first["location"]) if first.get("location") else
                         _CL3(file_path="(unknown)", line_start=0, line_end=0),
            )
            p.update_user_response(sid, turn_no, {
                "action": "select_candidate", "selected_index": 0, "auto": True,
                "note": f"impact fast-path auto-pick: {'edging' if is_edging else 'q3'}",
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


def _compose_pipeline_trace(*, intent: str, user_query: str, payload: dict) -> list[dict[str, Any]]:
    """결과를 만들 때까지의 순차 단계 timeline.

    사용자가 한 번에 결과만 보지 않고, 각 단계 (자연어 분석 → ontology 호출 → 합성)
    를 볼 수 있게 step list 합성. 각 step 은 frontend 가 collapsible 로 표시.
    실제 호출은 backend 가 이미 완료 — 이 trace 는 사후 reconstruction.
    """
    steps: list[dict[str, Any]] = []

    # Step 1 — 자연어 분석 (intent 분류 + 토큰 추출)
    detected = payload.get("_detected_terms") or []
    steps.append({
        "step_no": 1,
        "title": "자연어 분석",
        "action": "intent 분류 + 한국어/영문 토큰 추출",
        "result_summary": f"intent={intent} · ontology 용어 {len(detected)}건 감지",
        "details": {
            "user_query": user_query,
            "intent": intent,
            "detected_terms": [
                {"token": d.get("token"), "label": d.get("label"), "fqn": d.get("term_fqn")}
                for d in detected[:5]
            ],
        },
        "evidence_kind": "inference",
        "duration_hint": "~5ms",
    })

    # Step 2 — ontology 호출 (현재 carousel candidates / lookup)
    cands = payload.get("candidates") or []
    if cands or intent in ("explain", "locate", "impact"):
        steps.append({
            "step_no": 2,
            "title": "ontology API 호출",
            "action": "modeling 서버에 business_terms / actions / business_rules / anchor_bindings 조회",
            "result_summary": f"후보 action {len(cands)}건 · 관련 ontology 객체 다수 로딩",
            "details": {
                "candidate_count": len(cands),
                "called_endpoints": [
                    "/api/ontology/terms",
                    "/api/ontology/actions",
                    "/api/ontology/business-rules",
                    "/api/ontology/anchor-bindings",
                ],
                "first_candidates": [
                    {"action_id": c.get("action_id"), "code_method_fqn": c.get("code_method_fqn")}
                    for c in cands[:3]
                ],
            },
            "evidence_kind": "ontology",
            "duration_hint": "~30~150ms",
        })

    # Step 3 — intent 별 보강
    if intent == "explain":
        te = payload.get("_term_explain") or {}
        wc = payload.get("_weight_catalog") or {}
        if wc:
            steps.append({
                "step_no": 3,
                "title": "단중 영향 변수 catalog 합성 (Q1 fast-path)",
                "action": "ontology terms 에서 단중/두께/폭/길이 키워드 매칭 + 8개 변수 카탈로그 + 통제가능성 분류",
                "result_summary": f"{len(wc.get('variables', []))} 영향 변수 · {len(wc.get('ontology_terms', []))} 매칭 term",
                "details": {"core_formula": wc.get("core_formula")},
                "evidence_kind": "propagation",
                "duration_hint": "~50ms",
            })
        elif te:
            steps.append({
                "step_no": 3,
                "title": "atomic term ontology fan-out",
                "action": "선택된 term 의 get_term + effective_parts + 관련 action/rule/anchor 모두 병렬 호출",
                "result_summary": (
                    f"term={(te.get('term') or {}).get('label')} · "
                    f"related_actions {len(te.get('related_actions') or [])} · "
                    f"business_rules {len(te.get('business_rules') or [])} · "
                    f"anchor_bindings {len(te.get('anchor_bindings') or [])}"
                ),
                "details": {
                    "term_fqn": te.get("term_fqn"),
                    "aliases": (te.get("term") or {}).get("aliases", [])[:5],
                },
                "evidence_kind": "ontology",
                "duration_hint": "~60ms",
            })
    elif intent == "impact":
        tc = payload.get("_target_change") or {}
        ws = payload.get("_weight_sweep") or {}
        ei = payload.get("_edging_impact") or {}
        if ei:
            steps.append({
                "step_no": 3,
                "title": "Edging 능력 변경 영향 분석 (Q2 fast-path)",
                "action": "EDGING_GROUP × CAST_SPEC × HR_SPEC 교집합 ±5/15% 시나리오 propagation",
                "result_summary": f"{len(ei.get('scenarios', []))} 시나리오 평가",
                "details": {"base_edging": ei.get("base_edging")},
                "evidence_kind": "propagation",
                "duration_hint": "~30ms",
            })
        elif ws:
            steps.append({
                "step_no": 3,
                "title": "포장단중·설계대기량 sweep (Q3 fast-path)",
                "action": f"{ws.get('total_cells', 0)} 조합 grid sweep + feasibility 필터",
                "result_summary": f"feasible {ws.get('feasible_cells', 0)}건 · best slab 단중 {(ws.get('best') or {}).get('projected_slab_wgt', 0):,.0f}kg" if ws.get("best") else f"feasible {ws.get('feasible_cells', 0)}건",
                "details": {"sweep_variables": ws.get("sweep_variables")},
                "evidence_kind": "propagation",
                "duration_hint": "~80ms",
            })
        elif tc:
            steps.append({
                "step_no": 3,
                "title": "기준 변경 영향 추출",
                "action": f"target={tc.get('table')}.{tc.get('column')} 기반 affected_methods · _affected_orders · _affected_rules 수집",
                "result_summary": (
                    f"methods {len(payload.get('affected_methods') or [])}건 · "
                    f"orders {len(payload.get('_affected_orders') or [])}건 · "
                    f"rules {len(payload.get('_affected_rules') or [])}건"
                ),
                "details": tc,
                "evidence_kind": "ontology",
                "duration_hint": "~80ms",
            })
    elif intent == "locate":
        locs = payload.get("_locate_matches") or []
        steps.append({
            "step_no": 3,
            "title": "코드 위치 keyword 매칭",
            "action": "CodeMethodRow 의 fqn/body_text/name LIKE 매칭 + 본문 snippet 추출",
            "result_summary": f"{len(locs)} 위치 매칭",
            "details": {"top_files": [l.get("file_path") for l in locs[:3]]},
            "evidence_kind": "java_anchor",
            "duration_hint": "~40ms",
        })

    # Step 4 — 분석 합성
    if payload.get("_evidence"):
        e = payload["_evidence"]
        steps.append({
            "step_no": len(steps) + 1,
            "title": "신뢰도 평가 + 자연어 분석 합성",
            "action": "각 field 의 evidence 가중평균 + 한국어 줄글 답변 생성",
            "result_summary": (
                f"종합 신뢰도 {(e.get('overall_confidence', 0) * 100):.0f}% — "
                + " · ".join(f"{k}:{v}%" for k, v in (e.get('source_breakdown_pct') or {}).items() if v > 0)
            ),
            "details": e.get("source_breakdown_pct") or {},
            "evidence_kind": "inference",
            "duration_hint": "~10ms",
        })

    return steps


def _enforce_slab_korean(obj):
    """2026-05-25 — payload 의 모든 한국어 string 에서 '슬랩' / '슬래브' → 'Slab' 강제. 재귀 적용.
    LLM 출력은 종종 '슬랩' 또는 '슬래브' 로 돌아오므로 응답 직전에 일괄 치환.
    """
    if isinstance(obj, str):
        return obj.replace("슬랩", "Slab").replace("슬래브", "Slab")
    if isinstance(obj, dict):
        return {k: _enforce_slab_korean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_enforce_slab_korean(x) for x in obj]
    return obj


def _attach_walkthrough_steps(payload: dict, *, user_query: str) -> None:
    """사용자 질문에 관련된 21-step 카탈로그 항목 payload._walkthrough_steps 에 첨부.

    2026-05-25 — 질문별 동적 인사이트(_walkthrough_insight) 도 같이 합성.
    하드코딩된 "주문 데이터로 Slab 가능 범위 좁히고..." 같은 fixed 문구 제거.
    """
    try:
        from backend.section3.agents.simulation.step_catalog import (
            steps_matching_query, step_to_dict, PHASE_LABELS,
        )
        matched = steps_matching_query(user_query, max_n=8)
        if not matched:
            return
        payload["_walkthrough_steps"] = [step_to_dict(s) for s in matched]
        payload["_walkthrough_phases"] = PHASE_LABELS

        # ── 질문별 동적 인사이트 합성 ────────────────────────────────────
        # 매칭된 step 들의 phase·step_no·title 만으로 한 줄 인사이트.
        # 같은 질문에 같은 문구가 반복되지 않도록 질문 키워드를 반영.
        phases_hit = {s.phase for s in matched}
        steps_hit = [s.step_no for s in matched if s.step_no is not None]
        first_step = matched[0]
        q = user_query or ""

        # 인사이트 텍스트 — 질문 키워드 + 매칭 step 기반 동적
        bits: list[str] = []
        if "단중" in q and "영향" in q:
            bits.append("이 질문은 Slab 단중(무게) 결정 로직의 핵심 step 들을 짚습니다")
            bits.append("step 4 (1차 무게) → step 5/6 (압연·고객·설계대기량 적용) → step 7 (최대 분할수) 흐름이 단중 결과를 좌우합니다")
        elif "edging" in q.lower() or "EDGING" in q.upper() or "폭" in q:
            bits.append("이 질문은 Slab 폭 결정 로직 (step 2) + EDGING 능력이 폭 교집합에 미치는 영향을 짚습니다")
            bits.append("연주·열연·EDGING 3 설비의 폭 범위 교집합에서 가장 좁은 것이 결과를 결정합니다")
        elif "포장단중" in q or "설계대기량" in q:
            bits.append("이 질문은 step 6 (단중 상한 결정) + A-a 루프 (step 8~15) 의 분할수·매수 탐색에 직접 영향을 줍니다")
            bits.append("주문측 변수 (포장단중·설계대기량) 가 변하면 단중 상한과 최적 split 수가 함께 바뀝니다")
        elif "분할" in q or "split" in q.lower():
            bits.append("이 질문은 Phase 2-B (A-a 루프) 의 핵심인 분할수×매수 동시 탐색을 다룹니다")
            bits.append("step 7 (최대 분할수 ceil) 에서 시작해 step 8 (분할단중 범위) 로 줄여가며 feasible 조합을 찾습니다")
        elif "두께" in q or "thickness" in q.lower():
            bits.append("이 질문은 step 1 (CAST_SPEC 룩업) 의 Slab 두께 결정 + 그 두께가 step 4·6 의 무게 계산에 자동 전파되는 흐름을 짚습니다")
        elif "신규" in q and ("강종" in q or "품종" in q or "고객" in q):
            bits.append("신규 기준 추가 시나리오 — Phase 1 (누적 실수율 재산정) + Phase 2-A (가능 범위) + Save 까지 전 흐름이 가상 주문으로 시뮬됩니다")
        elif "어디" in q or "위치" in q:
            bits.append(f"질문 키워드와 매칭된 코드 위치는 {first_step.title} 단계입니다")
            if first_step.action_fqn:
                bits.append(f"ontology action: {first_step.action_fqn}")
        elif "확정통과공장코드" in q or "뭐야" in q or "무엇" in q:
            bits.append("이 질문은 ontology 의 atomic term 직접 조회 — 온톨로지에 등록된 정의·별칭·관련 규칙을 그대로 surface 합니다")
        else:
            # generic — 매칭된 phase + step 기반
            if first_step.step_no is not None:
                bits.append(f"질문에 가장 가까운 단계는 {PHASE_LABELS.get(first_step.phase, str(first_step.phase))} 의 step {first_step.step_no} ({first_step.title}) 입니다")
            else:
                bits.append(f"질문은 {PHASE_LABELS.get(first_step.phase, str(first_step.phase))} 에 해당합니다")
            if len(matched) > 1:
                others = ", ".join(f"step {s.step_no}" for s in matched[1:4] if s.step_no is not None)
                if others:
                    bits.append(f"관련 단계: {others}")

        payload["_walkthrough_insight"] = "\n".join(bits)
    except Exception as e:  # noqa: BLE001
        logger.warning("walkthrough steps 첨부 실패: %s", e)


def _compose_llm_analysis(*, intent: str, user_query: str, payload: dict) -> dict:
    """결과 카드 끝에 표시할 자연어 분석 — "왜 이런 결과가 나왔는가".

    2026-05-25 변경: 정적 템플릿 → 실제 LLM 호출 동적 생성 + 정적 fallback.
      - 1차 시도: OpenAI chat_json → 질문/의도/ontology 결과를 받아 동적 단락 생성
      - 실패 (key 없음/timeout/parse 실패) → 기존 정적 템플릿 fallback
    구조화된 dict 반환: { sections: [{heading, body}] }
    """
    sections: list[dict[str, str]] = []
    intent_ko = {
        "simulate": "시뮬레이션", "impact": "영향도 분석", "locate": "위치 찾기",
        "explain": "설명", "hypothesis": "가설 검증",
    }.get(intent, intent)

    # ── 1차: LLM 동적 생성 시도 (질문마다 다른 답변) ──
    try:
        from backend.section3.llm.openai_client import get_llm_client
        dt_labels = [d.get("label", "") for d in (payload.get("_detected_terms") or [])[:8]]
        tc = payload.get("_target_change") or {}
        aff_m = len(payload.get("affected_methods") or [])
        aff_o = len(payload.get("_affected_orders") or [])
        aff_r = len(payload.get("_affected_rules") or [])
        wc = payload.get("_weight_catalog") or {}
        te = payload.get("_term_explain") or {}
        ws = payload.get("_weight_sweep") or {}
        wkstep = payload.get("_walkthrough_steps") or []

        # 2026-05-25 — dynamic_blocks 의 실측 데이터 (가상 주문 + 21-step 결과 + comparison)
        # 도 ctx 에 포함시켜 LLM 이 정확한 수치 인용하도록.
        db = payload.get("_dynamic_blocks") or []
        ctx_lines = [
            f"의도: {intent_ko}",
            f"감지된 ontology 용어({len(dt_labels)}개): {', '.join(dt_labels) or '없음'}",
        ]
        if tc:
            ctx_lines.append(f"변경 대상: {tc.get('table')}.{tc.get('column')} ({tc.get('before')}→{tc.get('after')})")
        if aff_m: ctx_lines.append(f"영향받는 Java method: {aff_m}개")
        if aff_o: ctx_lines.append(f"가상 주문 {aff_o}건 합성 (5케이스: 하한/정상/상한/범위초과/매칭실패)")
        if aff_r: ctx_lines.append(f"적용 business rule: {aff_r}개")
        if wc.get("variables"): ctx_lines.append(f"가중치 카탈로그 변수: {len(wc['variables'])}개")
        if te.get("term"): ctx_lines.append(f"답변 중심 term: {te['term'].get('label')} ({te['term'].get('kind')})")
        if ws.get("best"):
            best = ws["best"]
            ctx_lines.append(f"sweep best: {best.get('vars')} → slab {int(best.get('projected_slab_wgt',0)):,}kg")
        if wkstep:
            steps_brief = ", ".join(f"step {s.get('step_no')}" for s in wkstep[:5] if s.get('step_no'))
            if steps_brief:
                ctx_lines.append(f"관련 21-step: {steps_brief}")
        # dynamic_blocks 의 실측 데이터 ctx (정확한 수치 인용용)
        for b in db[:8]:
            bt = b.get("type")
            bd = b.get("data") or {}
            if bt == "metric_grid" and bd.get("items"):
                metrics = ", ".join(f"{i.get('label')}={i.get('value')}{i.get('unit','')}" for i in bd["items"][:6])
                ctx_lines.append(f"[metric_grid] {b.get('title','')}: {metrics}")
            elif bt == "comparison" and bd.get("rows"):
                rows = "; ".join(
                    f"{r.get('label')}: {r.get('before')}→{r.get('after')}"
                    + (f" ({r.get('change_pct'):+.1f}%)" if isinstance(r.get('change_pct'),(int,float)) else "")
                    for r in bd["rows"][:6]
                )
                ctx_lines.append(f"[comparison] {b.get('title','')} — {bd.get('before_label')} vs {bd.get('after_label')}: {rows}")
            elif bt == "table" and bd.get("rows"):
                # 첫 3 행만 컴팩트하게
                rows_preview = []
                for r in bd["rows"][:3]:
                    rows_preview.append(", ".join(f"{k}={v}" for k, v in list(r.items())[:5]))
                ctx_lines.append(f"[table] {b.get('title','')} ({len(bd['rows'])}건): {' / '.join(rows_preview)}")
            elif bt == "sweep_chart" and bd.get("points"):
                pts = bd["points"]
                if pts:
                    ctx_lines.append(f"[sweep_chart] {b.get('title','')}: {pts[0].get('x')}={pts[0].get('y')} → {pts[-1].get('x')}={pts[-1].get('y')} (best idx={bd.get('best_index')})")

        system = (
            "당신은 제조 IT 시뮬레이션 에이전트입니다. 사용자 질문 + ontology 분석 + dynamic_blocks 의 실측 데이터(metric_grid·comparison·table·sweep_chart) 를 받아 "
            "'왜 이런 결과가 나왔는가' 를 한국어 단락 3~5개로 설명합니다.\n\n"
            "==[작성 규칙]==\n"
            "● dynamic_blocks 컨텍스트의 실측 숫자가 있으면 반드시 인용. 없으면 ontology + 감지된 용어 + 21-step 메커니즘 기반으로 일반 분석 진행 (안내 문구 X — 그냥 분석).\n"
            "● 컨텍스트 외 임의 수치 (예: 0.1~500mm 같은 가짜 범위) 생성은 자제 — 단, ontology 정의에 명시된 범위·산식·기본값은 인용 가능.\n"
            "● '일반적으로', '~수 있습니다' 같은 너무 모호한 일반론은 자제. 21-step 알고리즘 안에서 '어느 step 에서 어떻게' 같은 도메인 특화 분석 선호.\n"
            "● 당연한 상식 (두께 늘리면 무게 증가) 은 짧게만, 핵심은 시스템 특화 (어느 step·산식·rule 에 영향).\n"
            "● 이모지(😊⚠️✅), 마크다운(**##``) 사용 금지.\n\n"
            "==[작성 지침]==\n"
            "1) heading 은 간결한 명사구 (예: 'Step 6 단중 상한 변화', '분할수 영향').\n"
            "2) body 는 컨텍스트 실측치를 인용 — 'baseline 20,000kg → after 19,500kg (-2.5%) — Step 6 의 secondWgtHigh 가 HR_MAX_WGT 한계에 막혀서'.\n"
            "3) 21-step 산식 메커니즘 (Step 6 = min(HR_MAX, ORDER_WGT_HIGH, DPQ/productivity) 등) 함께 인용.\n"
            "4) 변화가 없으면 '왜 변화가 없는가' 도 명시 — 'ow_high(20,000) 가 hr_max(25,000) 보다 작아 HR_MAX 5% 증가는 결과에 영향 없음'.\n\n"
            'JSON 형식: {"sections": [{"heading": "...", "body": "..."}, ...]}'
        )
        user_msg = (
            f"사용자 질문:\n{user_query}\n\n"
            f"분석 컨텍스트:\n" + "\n".join(f"- {x}" for x in ctx_lines)
        )
        llm = get_llm_client()
        raw = llm.chat_json([
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ], temperature=0.3)
        llm_sections = raw.get("sections") if isinstance(raw, dict) else None
        if isinstance(llm_sections, list) and llm_sections:
            cleaned: list[dict[str, str]] = []
            for s in llm_sections[:6]:
                if not isinstance(s, dict): continue
                h = str(s.get("heading", "")).strip().replace("**", "").replace("`", "").replace("#", "")
                b = str(s.get("body", "")).strip().replace("**", "").replace("`", "")
                if h and b:
                    cleaned.append({"heading": h[:80], "body": b[:1200]})
            if cleaned:
                legacy_md = "\n\n".join(f"### {s['heading']}\n{s['body']}" for s in cleaned)
                return {"sections": cleaned, "markdown": legacy_md, "_llm_source": "dynamic"}
    except Exception as e:  # noqa: BLE001
        logger.info("LLM 동적 분석 실패 → 정적 fallback: %s", e)

    # ── fallback: 기존 정적 템플릿 (LLM 실패/key 없을 때) ──

    dt = payload.get("_detected_terms") or []
    detected_names = ", ".join(d.get("label", "") for d in dt[:4])

    # 공통 — 질문 + 의도
    sections.append({
        "heading": "질문 의도 파악",
        "body": (
            f"사용자 질문을 “{intent_ko}” 로 분류했습니다.\n"
            + (f"질문에서 감지된 ontology 용어는 {len(dt)}개 — {detected_names} 입니다."
               if dt else "질문에서 직접 매칭된 ontology 용어는 없었습니다.")
        ),
    })

    if intent == "explain":
        wc = payload.get("_weight_catalog") or {}
        if wc:
            vars_n = len(wc.get("variables", []))
            sections.append({
                "heading": "분석한 변수들",
                "body": (
                    f"slab 단중에 영향을 주는 변수 {vars_n}개를 ontology business_terms 와 "
                    f"propagation 규칙으로 식별했습니다.\n"
                    f"핵심 공식: weight = thickness × width × length × density\n"
                    f"외부 제약: {wc.get('external_constraint','')}"
                ),
            })
            sections.append({
                "heading": "단중 최대화 전략",
                "body": (
                    "단기적으로 가장 효과 큰 변수는 포장단중 상한과 설계대기량입니다.\n"
                    "주문 단계에서 직접 조정 가능하므로 IT 개입 없이 시뮬 후 결정 가능합니다.\n"
                    "중기적으로는 EDGING_GROUP 폭 능력, 장기적으로는 HR_MAX_WGT 상향이 한계 단중을 끌어올립니다"
                ),
            })
            sections.append({
                "heading": "신뢰도 근거",
                "body": (
                    "이 카탈로그는 ontology business_terms (slab/두께/단중 키워드 매칭) + "
                    "21-step 알고리즘의 propagation 규칙을 결합해 합성했습니다.\n"
                    "변수별 영향 방향과 제약은 ontology business_rules 와 직접 매핑되므로 검증 가능합니다"
                ),
            })
            legacy_md = "\n\n".join(f"### {s['heading']}\n{s['body']}" for s in sections)
            return {"sections": sections, "markdown": legacy_md}
        te = payload.get("_term_explain") or {}
        term = te.get("term") or {}
        if term:
            label = term.get("label")
            kind = term.get("kind")
            desc = (term.get("description") or "").strip()
            sections.append({
                "heading": f"{label} — 무엇인가",
                "body": (
                    f"이 용어는 ontology 에 등록된 {kind} 도메인 단어입니다.\n"
                    + (desc[:300] + ("…" if len(desc) > 300 else "") if desc else ""),
                ).__getitem__(0)
                if False else
                (f"이 용어는 ontology 에 등록된 {kind} 도메인 단어입니다.\n"
                 + (desc[:300] + ("…" if len(desc) > 300 else "") if desc else "")),
            })
            connect_parts: list[str] = []
            if te.get("related_actions"):
                connect_parts.append(f"관련 action {len(te['related_actions'])}개")
            if te.get("business_rules"):
                connect_parts.append(f"적용 business rule {len(te['business_rules'])}개")
            if connect_parts:
                sections.append({
                    "heading": "ontology 안 연결",
                    "body": (
                        f"이 용어와 직접 연결된 항목: {', '.join(connect_parts)} 가 ontology 에 등록되어 있습니다.\n"
                        f"각 항목은 위 카드의 펼침에서 확인할 수 있습니다"
                    ),
                })
        sections.append({
            "heading": "답변 합성 방식",
            "body": (
                "이 답변은 Modeling Agent 가 만든 ontology API 응답만으로 합성했습니다.\n"
                "Java 소스 코드를 직접 보지 않으므로 코드가 바뀌어도 도메인 의미는 안정적으로 유지됩니다"
            ),
        })

    elif intent == "impact":
        tc = payload.get("_target_change") or {}
        if tc:
            table = tc.get("table"); column = tc.get("column")
            before = tc.get("before"); after = tc.get("after")
            sections.append({
                "heading": "변경 대상",
                "body": (
                    f"{table} 테이블의 {column} 컬럼이 변경 대상입니다.\n"
                    f"값: {before if before is not None else '미입력'} → "
                    f"{after if after is not None else '미입력'}"
                ),
            })
        aff_meth = payload.get("affected_methods") or []
        aff_orders = payload.get("_affected_orders") or []
        aff_rules = payload.get("_affected_rules") or []
        impact_lines: list[str] = []
        if aff_meth:
            impact_lines.append(
                f"이 변경은 Java method {len(aff_meth)}개에 직접·간접으로 영향을 줍니다.\n"
                f"ontology 의 action ↔ code_method realization 관계를 따라가 추출했습니다"
            )
        if aff_orders:
            impact_lines.append(
                f"이 변경이 적용된다고 가정하고 합성한 가상 주문 {len(aff_orders)}건을 함께 보여드립니다.\n"
                f"실제 DB 의 주문 데이터는 전혀 사용·변경하지 않으며, 기준 데이터(CAST/HR/EDGING 등) 의 실제 범위 안에서 ontology 로 합성한 dry-run 주문입니다"
            )
        if aff_rules:
            severities = [r.get("severity") for r in aff_rules]
            hard = severities.count("hard")
            impact_lines.append(
                f"관련 business rule {len(aff_rules)}개"
                + (f" (그 중 hard {hard}개 — 위반 시 설계 실패)" if hard else "")
                + " 가 ontology 에 등록되어 있어 변경 시 우선 검토가 필요합니다"
            )
        if impact_lines:
            sections.append({
                "heading": "변경의 영향 범위",
                "body": "\n\n".join(impact_lines),
            })
        ws = payload.get("_weight_sweep") or {}
        if ws and ws.get("best"):
            best = ws["best"]
            best_vars = ", ".join(f"{k} = {int(v):,}" for k, v in best["vars"].items())
            sections.append({
                "heading": "변수 조합 sweep 결과",
                "body": (
                    f"{ws.get('total_cells', 0)}개 조합을 평가했고 그 중 "
                    f"{ws.get('feasible_cells', 0)}개가 제약을 만족합니다.\n"
                    f"slab 단중을 최대화하는 조합: {best_vars}\n"
                    f"이 조합에서 예상 slab 단중은 {int(best['projected_slab_wgt']):,} kg, "
                    f"분할 수는 {best['projected_split_count']}개입니다"
                ),
            })
        sections.append({
            "heading": "정확도 안내",
            "body": (
                "위 결과는 ontology 의 propagation 규칙과 가상 입력으로 계산한 추정치입니다.\n"
                "실제 운영 적용 전, 영향받는 method 의 Java→Python 변환 코드를 변경된 값으로 "
                "다시 실행해 baseline 과 비교하시기 바랍니다"
            ),
        })

    elif intent == "locate":
        locs = payload.get("_locate_matches") or []
        if locs:
            sections.append({
                "heading": "위치 추출 방법",
                "body": (
                    f"ontology anchor_bindings 에서 {len(locs)}개 Java 위치를 찾았습니다.\n"
                    f"Java 소스를 직접 grep 하지 않고, ontology 의 anchor → method 매핑만 사용했습니다"
                ),
            })
    elif intent == "hypothesis":
        sections.append({
            "heading": "가설 시뮬 방식",
            "body": (
                "신규 기준·주문을 가상으로 합성한 뒤 sim_v2 가 Java→Python 으로 변환한 코드를 "
                "그 가상 데이터로 실행해 기존 결과와 비교했습니다.\n"
                "실제 DB 는 전혀 변경하지 않은 read-only dry-run 입니다"
            ),
        })

    # legacy compat — markdown string 도 같이 (기존 frontend 호환)
    legacy_md = "\n\n".join(f"### {s['heading']}\n{s['body']}" for s in sections)
    return {"sections": sections, "markdown": legacy_md}


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
    # 1) 직접 table 이름 (대문자 영문)
    for t in domain_data.list_tables():
        if t.table_name in user_query:
            target_table = t.table_name
            break
    # 2) 한국어 alias 매칭
    for kw, (tbl, col) in TBL_ALIAS.items():
        if kw in user_query:
            if target_table is None:
                target_table = tbl
            if col:
                target_column = col
            break
    for kw, col in COL_ALIAS.items():
        if kw in user_query and target_column is None:
            target_column = col
            break
    # column 매칭이 부정확하면 table 의 실제 columns 와 keyword substring 으로 재매칭.
    # 예: "EDGING 의 폭" → target_column 후보 'WIDTH'. table EDGING_GROUP 의 실제 컬럼은
    # 'HR_TGT_WIDTH_LOW'/'HR_TGT_WIDTH_HIGH'. 후자가 더 적합 → 부분 매칭으로 보정.
    if target_table:
        try:
            t_def = domain_data.get_table(target_table)
            if t_def:
                actual_cols = [c.name for c in t_def.columns]
                # 사용자 query 에서 직접 등장한 컬럼명 (정확 매칭) 우선
                for col_name in actual_cols:
                    if col_name in user_query or col_name.lower() in user_query.lower():
                        target_column = col_name
                        break
                else:
                    # target_column 이 table 에 실제로 없으면 — substring 매칭으로 best
                    if target_column and target_column not in actual_cols:
                        kw_l = target_column.lower()
                        match = next((c for c in actual_cols if kw_l in c.lower()), None)
                        if match:
                            target_column = match
        except Exception:  # noqa: BLE001
            pass
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
    # Q3 (포장단중·설계대기량) 트리거 시 _target_change 자체를 만들지 않음 — 별도 UI 사용
    is_q3_question = any(t in user_query for t in (
        "포장단중", "설계대기량", "DESIGN_PEND_QTY", "ORDER_WGT",
    ))
    if (target_table or target_column or after_val) and not is_q3_question:
        payload["_target_change"] = {
            "table": target_table or "?", "column": target_column or "?",
            "before": before_val, "after": after_val,
            "product": target_product,
            "note": "자연어에서 추출. 정확하지 않을 수 있으니 확인 필요." if not (target_table and target_column and after_val) else "",
        }
        # 기준 테이블의 모든 row 도 함께 surface — 사용자가 어떤 row 의 값을 바꿀지 선택
        if target_table:
            try:
                rows = domain_data.list_rows(target_table, limit=50)
                payload["_target_table_rows"] = [r.values for r in rows]
                t_def = domain_data.get_table(target_table)
                if t_def:
                    payload["_target_table_meta"] = {
                        "pk_columns": t_def.pk_columns,
                        "columns": [c.name for c in t_def.columns],
                        "description": t_def.description,
                    }
            except Exception:
                pass

    # 3) 매칭 주문 — seed ORDER_OM × ORDER_QD join, target_product / target_term 기반
    # 사용자 질문에 따라 동적으로 컬럼 선택 — 변경 대상 column 과 직접 관련된 ORDER 컬럼만 surface.
    # 예: SLAB_THICKNESS 변경 → ORDER_THICKNESS / ORDER_WIDTH / ORDER_LENGTH 영향. WIDTH 변경 → ORDER_WIDTH 영향. WGT 변경 → ORDER_WGT_LOW/HIGH/DESIGN_PEND_QTY 영향.
    # 또 가상 주문 (ontology 기반) 으로 합성해서 실제 seed 가 아닌 dry-run 데이터 표시.
    def _dynamic_order_columns(query: str, target_col: str | None) -> list[str]:
        """질문 키워드별 컬럼 set — 매번 다르게 surface 되도록 최소 cols 만 포함."""
        cols = ["ORDER_NO"]   # 필수 식별자만
        col_l = (target_col or "").lower()
        q_upper = query.upper()
        # 우선순위: 매우 명시적인 키워드부터
        if "EDGING" in q_upper or "edging" in col_l:
            cols += ["EDGING_GROUP_CD", "ORDER_WIDTH", "PRODUCT_CD"]  # 폭 + EDGING 그룹
        elif "포장단중" in query or "wgt_low" in col_l or "wgt_high" in col_l:
            cols += ["ORDER_WGT_LOW", "ORDER_WGT_HIGH", "DESIGN_PEND_QTY", "GRADE_CD"]
        elif "설계대기량" in query or "pend" in col_l:
            cols += ["DESIGN_PEND_QTY", "ORDER_WGT_HIGH", "GRADE_CD"]
        elif "두께" in query or "thickness" in col_l:
            cols += ["ORDER_THICKNESS", "GRADE_CD", "PRODUCT_CD", "ORDER_WIDTH"]
        elif "길이" in query or "length" in col_l:
            cols += ["ORDER_LENGTH", "DESIGN_PEND_QTY", "PRODUCT_CD"]
        elif "폭" in query or "width" in col_l:
            cols += ["ORDER_WIDTH", "EDGING_GROUP_CD", "PRODUCT_CD"]
        elif "단중" in query or "wgt" in col_l:
            cols += ["ORDER_WGT_LOW", "ORDER_WGT_HIGH", "DESIGN_PEND_QTY"]
        elif "실수율" in query or "productivity" in col_l:
            cols += ["GRADE_CD", "PRODUCT_CD", "DESIGN_PEND_QTY"]
        elif "고객" in query or "customer" in col_l:
            cols += ["CUSTOMER_CD", "GRADE_CD", "PRODUCT_CD"]
        elif "강종" in query or "grade" in col_l:
            cols += ["GRADE_CD", "PRODUCT_CD", "DESIGN_PEND_QTY"]
        elif "품종" in query or "product" in col_l:
            cols += ["PRODUCT_CD", "GRADE_CD", "ORDER_WIDTH"]
        else:
            cols += ["PRODUCT_CD", "GRADE_CD", "ORDER_WIDTH", "DESIGN_PEND_QTY"]
        return cols

    # ontology 기반 가상 주문 합성 — base table row 값을 가져와 교집합 범위 안에서 가상값
    matched_orders: list[dict] = []
    try:
        import random
        # 기준 row 1건 — target_table 의 seed 가져와 PK/공장 정보 추출 (가상 주문 단순화용)
        base_row: dict[str, Any] = {}
        if target_table:
            try:
                _rs = domain_data.list_rows(target_table, limit=1)
                if _rs: base_row = _rs[0].values
            except Exception:
                pass
        # 폭·단중·길이 합리적 범위 (없으면 default)
        def _f(v: Any) -> float | None:
            try: return float(v) if v is not None else None
            except Exception: return None
        w_low = _f(base_row.get("WIDTH_LOW")) or 1100.0
        w_high = _f(base_row.get("WIDTH_HIGH")) or 2000.0
        l_low = _f(base_row.get("LENGTH_LOW")) or 4500.0
        l_high = _f(base_row.get("LENGTH_HIGH")) or 10000.0
        thickness = _f(base_row.get("SLAB_THICKNESS")) or 230.0
        # CUSTOMER_STD / HR_MAX/MIN_WGT 도 시도
        hr_max = 22000.0
        hr_min = 8500.0
        try:
            _hm = domain_data.list_rows("HR_MAX_WGT", limit=1)
            if _hm: hr_max = _f(_hm[0].values.get("MAX_WGT")) or hr_max
            _hn = domain_data.list_rows("HR_MIN_WGT", limit=1)
            if _hn: hr_min = _f(_hn[0].values.get("MIN_WGT")) or hr_min
        except Exception:
            pass

        product_pool = ["COIL", "FS"]
        grade_pool = ["SS400", "SS490", "SM355", "HR1010"]
        cust_pool = ["CUST-A", "CUST-B", "CUST-VIP"]
        edging_pool = ["EG-STD", "EG-WIDE", "EG-NARROW"]

        for i in range(5):
            pcd = target_product or random.choice(product_pool)
            order = {
                "ORDER_NO": f"VIRT{i + 1:03d}",
                "GRADE_CD": random.choice(grade_pool),
                "PRODUCT_CD": pcd,
                "ORDER_THICKNESS": thickness,
                "ORDER_WIDTH": round(random.uniform(w_low, w_high) / 50) * 50,
                "ORDER_LENGTH": round(random.uniform(l_low, l_high) / 100) * 100,
                "ORDER_WGT_LOW": round(random.uniform(hr_min, (hr_min + hr_max) / 2) / 500) * 500,
                "ORDER_WGT_HIGH": round(random.uniform((hr_min + hr_max) / 2, hr_max) / 500) * 500,
                "DESIGN_PEND_QTY": round(random.uniform(hr_max, hr_max * 3) / 500) * 500,
                "CUSTOMER_CD": random.choice(cust_pool),
                "EDGING_GROUP_CD": random.choice(edging_pool),
                "_virtual": True,
            }
            matched_orders.append(order)
    except Exception as e:  # noqa: BLE001
        logger.warning("virtual orders 합성 실패: %s", e)
    if matched_orders:
        payload["_affected_orders"] = matched_orders
        # frontend 가 어느 컬럼 surface 할지 hint
        payload["_affected_orders_columns"] = _dynamic_order_columns(user_query, target_column)
        payload["_affected_orders_synthesis"] = "실제 기준 데이터(CAST_SPEC·HR_SPEC·HR_MAX/MIN_WGT 등) 의 폭·단중 범위를 토대로 ontology 가 합성한 가상 주문입니다. 실제 DB 의 주문 데이터는 사용·변경하지 않습니다"

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

    # ── Q2: "Edging 능력 상하한 변경" 사전 영향 분석 ───────────────────────
    q = (user_query or "")
    is_edging = (
        "Edging" in q or "edging" in q or "EDGING" in q or "EDGING_GROUP" in q
    ) and any(t in q for t in ("능력", "상한", "하한", "상하한", "변경"))
    if is_edging:
        try:
            from backend.section3.agents.simulation import evidence as ev
            # 기본 base — seed EDGING_GROUP 첫 row + CAST_SPEC + HR_SPEC 교집합
            edging_rows = []
            cast_rows = []
            hr_rows = []
            try:
                edging_rows = domain_data.list_rows("EDGING_GROUP", limit=10)
                cast_rows = domain_data.list_rows("CAST_SPEC", limit=10)
                hr_rows = domain_data.list_rows("HR_SPEC", limit=10)
            except Exception:
                pass
            edging_base = edging_rows[0].values if edging_rows else {}
            cast_base = cast_rows[0].values if cast_rows else {}
            hr_base = hr_rows[0].values if hr_rows else {}

            def _f(v: Any) -> float | None:
                try: return float(v) if v is not None else None
                except Exception: return None

            # 2026-05-25 — 사용자 지적: "1200/2000" 이 항상 같은 fallback 이라 무의미.
            # EDGING_GROUP 의 HR_TGT_WIDTH 매칭 범위 (실제 seed 의 priority 1 row) 사용 +
            # 없으면 명시적 random 으로 표시 (사용자가 fallback 인지 알도록).
            import random as _rnd
            _base_low_raw = _f(edging_base.get("HR_TGT_WIDTH_LOW"))
            _base_high_raw = _f(edging_base.get("HR_TGT_WIDTH_HIGH"))
            base_low = _base_low_raw if _base_low_raw is not None else float(_rnd.choice([500, 600, 800, 1000, 1200]))
            base_high = _base_high_raw if _base_high_raw is not None else float(_rnd.choice([1800, 2000, 2200, 2400, 2500]))
            base_is_fallback = _base_low_raw is None or _base_high_raw is None
            cast_low = _f(cast_base.get("WIDTH_LOW")) or float(_rnd.choice([800, 900, 1000, 1100]))
            cast_high = _f(cast_base.get("WIDTH_HIGH")) or float(_rnd.choice([2000, 2100, 2200, 2300]))
            hr_low = _f(hr_base.get("WIDTH_LOW")) or float(_rnd.choice([750, 900, 1100]))
            hr_high = _f(hr_base.get("WIDTH_HIGH")) or float(_rnd.choice([2100, 2300, 2400]))

            # 변경 전후 시나리오 — 실제로 효과 보이는 범위로 동적 조정.
            # base EDGING 이 CAST/HR 보다 넓으면 EDGING 변경이 효과 없으므로,
            # 시나리오 폭을 CAST/HR 폭으로 정규화해서 사용자가 의미있게 비교 가능하게.
            outer_low = min(cast_low, hr_low)         # 가장 넓은 외부
            outer_high = max(cast_high, hr_high)
            inner_low = max(cast_low, hr_low)         # 외부 교집합 (CAST ∩ HR)
            inner_high = min(cast_high, hr_high)

            # 절대값 시나리오 — EDGING 이 binding 되는 시나리오를 포함시켜 실제 영향 비교 가능.
            # inner (CAST ∩ HR) 폭 안에서 EDGING 을 더 좁게 만들면 EDGING 이 binding 으로 바뀜.
            inner_w = max(0, inner_high - inner_low)
            mid = (inner_low + inner_high) / 2
            scenarios_spec = [
                ("외부 한계까지 최대 확장", outer_low, outer_high),
                ("현재 EDGING", base_low, base_high),
                ("CAST ∩ HR 한계 (현재 binding)", inner_low, inner_high),
                ("능력 축소 — inner 폭의 80%", mid - inner_w * 0.4, mid + inner_w * 0.4),
                ("능력 축소 — inner 폭의 60%", mid - inner_w * 0.3, mid + inner_w * 0.3),
                ("능력 축소 — inner 폭의 40%", mid - inner_w * 0.2, mid + inner_w * 0.2),
            ]
            # base 의 effective (현재 상태)
            base_eff_low = max(cast_low, hr_low, base_low)
            base_eff_high = min(cast_high, hr_high, base_high)
            base_range = max(0, base_eff_high - base_eff_low)
            base_avg_width = (base_eff_low + base_eff_high) / 2 if base_range > 0 else 1

            def _binding(eff_low: float, eff_high: float, ed_low: float, ed_high: float) -> str:
                """이 교집합에서 최협착(binding) 인 설비 식별."""
                bind_low = "CAST" if cast_low == eff_low else "HR" if hr_low == eff_low else "EDGING"
                bind_high = "CAST" if cast_high == eff_high else "HR" if hr_high == eff_high else "EDGING"
                if bind_low == bind_high: return f"{bind_low} (양쪽)"
                return f"low: {bind_low}, high: {bind_high}"

            scenarios = []
            for label, new_low, new_high in scenarios_spec:
                eff_low = max(cast_low, hr_low, new_low)
                eff_high = min(cast_high, hr_high, new_high)
                eff_range = max(0, eff_high - eff_low)
                range_change_pct = (
                    (eff_range - base_range) / base_range * 100 if base_range > 0 else 0
                )
                avg_width = (eff_low + eff_high) / 2 if eff_range > 0 else 0
                # 최대 단중 변화 — slab 단중 ∝ 폭, 최대 단중은 effective_high 에 비례
                max_wgt_change_pct = (eff_high / base_eff_high - 1) * 100 if base_eff_high else 0
                # 최소 단중 변화 — effective_low 기준
                min_wgt_change_pct = (eff_low / base_eff_low - 1) * 100 if base_eff_low else 0
                # 대표 weight_change — 최대 단중 변화 (사용자가 단중 최대화 관심)
                weight_change_pct = max_wgt_change_pct
                binding = _binding(eff_low, eff_high, new_low, new_high) if eff_range > 0 else "교집합 없음"
                edging_active = (new_low > cast_low and new_low > hr_low) or (new_high < cast_high and new_high < hr_high)

                scenarios.append({
                    "label": label,
                    "new_low": round(new_low, 1),
                    "new_high": round(new_high, 1),
                    "effective_low": round(eff_low, 1),
                    "effective_high": round(eff_high, 1),
                    "effective_range": round(eff_range, 1),
                    "range_change_pct": round(range_change_pct, 1),
                    "avg_width": round(avg_width, 1),
                    "weight_change_pct": round(weight_change_pct, 1),
                    "max_wgt_change_pct": round(max_wgt_change_pct, 1),
                    "min_wgt_change_pct": round(min_wgt_change_pct, 1),
                    "feasible": eff_range > 0,
                    "binding_constraint": binding,
                    "edging_active": edging_active,  # EDGING 이 실제로 binding 인지
                    "warning": "교집합 음수 — 폭 설계 불가" if eff_range <= 0 else None,
                })

            # 현재 EDGING 능력 binding 여부 — 사용자에게 핵심 인사이트
            edging_currently_binding = any(s["edging_active"] for s in scenarios if s["label"] == "현재 EDGING")
            insight: str
            if base_low <= cast_low and base_low <= hr_low and base_high >= cast_high and base_high >= hr_high:
                insight = (
                    f"💡 현재 EDGING 능력 ({base_low:.0f}~{base_high:.0f}) 이 "
                    f"CAST_SPEC ({cast_low:.0f}~{cast_high:.0f}) 및 HR_SPEC ({hr_low:.0f}~{hr_high:.0f}) 보다 넓어 "
                    f"EDGING 단독 변경의 효과가 거의 없습니다. 실제 binding 은 CAST 또는 HR 설비. "
                    f"EDGING 능력을 CAST/HR 보다 좁게 축소할 때 영향이 나타나며, 위 시나리오의 '능력 축소' 케이스 참조."
                )
            elif edging_currently_binding:
                insight = (
                    f"⚡ 현재 EDGING 능력 ({base_low:.0f}~{base_high:.0f}) 이 binding constraint — "
                    f"EDGING 능력 변경이 효과 폭/단중에 직접 영향을 줍니다."
                )
            else:
                insight = (
                    f"현재 EDGING 능력 ({base_low:.0f}~{base_high:.0f}) 은 일부만 binding. "
                    f"각 시나리오의 binding_constraint 열 참조."
                )

            payload["_edging_impact"] = {
                "title": "Edging 능력 상하한 변경 → 영향 분석",
                "purpose": "공장 설비 변경 예정 — 변경 후 slab 폭 / 단중 영향 사전 파악",
                "base_edging": {
                    "HR_TGT_WIDTH_LOW": base_low, "HR_TGT_WIDTH_HIGH": base_high,
                },
                "external_constraints": {
                    "CAST_SPEC_WIDTH_LOW": cast_low, "CAST_SPEC_WIDTH_HIGH": cast_high,
                    "HR_SPEC_WIDTH_LOW": hr_low, "HR_SPEC_WIDTH_HIGH": hr_high,
                },
                "scenarios": scenarios,
                "core_logic": (
                    "효과 폭 = max(CAST.WIDTH_LOW, HR.WIDTH_LOW, EDGING.HR_TGT_WIDTH_LOW) "
                    "~ min(CAST.WIDTH_HIGH, HR.WIDTH_HIGH, EDGING.HR_TGT_WIDTH_HIGH). "
                    "최대 단중 ∝ effective_high, 최소 단중 ∝ effective_low (다른 변수 고정)."
                ),
                "insight": insight,
                "note": (
                    "Edging 단독 변경은 CAST_SPEC/HR_SPEC 가 더 좁으면 효과 없음. "
                    "능력 축소 시 EDGING 이 binding 으로 바뀌면 효과 폭이 줄어들고 단중도 ↓."
                ),
            }

            # evidence
            bundle = ev.EvidenceBundle()
            bundle.add("base_edging", ev.seed_data(
                "EDGING_GROUP", "HR_TGT_WIDTH_LOW/HIGH", f"{base_low}~{base_high}",
            ))
            bundle.add("external_constraints", ev.seed_data(
                "CAST_SPEC + HR_SPEC", "WIDTH_LOW/HIGH",
                f"cast {cast_low}~{cast_high}, hr {hr_low}~{hr_high}",
            ))
            bundle.add("scenarios", ev.propagation(
                "effective = max(low) ~ min(high) ∩ 3 설비",
                ["EDGING_GROUP", "CAST_SPEC", "HR_SPEC"],
                confidence=0.85,
            ))
            bundle.add("scenarios", ev.propagation(
                "단중 ∝ 폭 (thickness·length·density 고정)",
                ["slabWidth"],
                confidence=0.75,
            ))
            for sc in scenarios:
                bundle.add(f"scenarios[{sc['label']}].weight_change_pct", ev.Evidence(
                    kind="propagation",
                    summary=f"{sc['label']} → 평균 폭 ±{sc['weight_change_pct']:.1f}% → 단중 같은 방향",
                    confidence=0.75,
                    source_ref=sc['label'],
                    detail=f"effective {sc['effective_low']}~{sc['effective_high']}",
                ))
            # 기존 _evidence 가 있으면 merge — 신뢰도 통합
            existing = payload.get("_evidence")
            if existing and isinstance(existing, dict):
                # 기존 fields 와 합치기
                bundle.fields.update({
                    k: [ev.Evidence(**ee) for ee in evs]
                    for k, evs in (existing.get("fields") or {}).items()
                })
            payload["_evidence"] = bundle.to_dict()
        except Exception as e:  # noqa: BLE001
            logger.warning("Edging 영향 분석 실패: %s", e)

    # ── Q3: "포장단중·설계대기량 변경 → slab 단중 최대화" sweep 자동 ─────────
    # 사용자 요구 (2026-05-23 추가): sweep 을 자동으로 다 보여주지 말고
    # 1) ontology 기반 가상 주문 1건 합성 → 사용자에게 표시
    # 2) 사용자가 변경 전·후 포장단중 상하한 / 설계대기량 입력
    # 3) /weight_optimize/sweep endpoint 호출 → 결과
    # backend 는 stage 1 의 가상 주문만 payload._q3_interactive 에 첨부, sweep 은
    # frontend 가 사용자 입력 후 직접 호출.
    q = (user_query or "")
    sweep_triggers = ["포장단중", "설계대기량", "DESIGN_PEND_QTY", "ORDER_WGT"]
    if any(t in q for t in sweep_triggers):
        try:
            # 기본 base order — seed 첫 row (또는 default)
            base_order: dict[str, Any] = {
                "ORDER_NO": "BASE-001",
                "ORDER_WIDTH": 1500,
                "ORDER_LENGTH": 8000,
                "ORDER_WGT_LOW": 10000,
                "ORDER_WGT_HIGH": 20000,
                "DESIGN_PEND_QTY": 40000,
                "_HR_MAX_WGT": 25000,
                "_HR_MIN_WGT": 8000,
            }
            try:
                om_rows = domain_data.list_rows("ORDER_OM", limit=1)
                if om_rows:
                    base_order.update({
                        k: v for k, v in om_rows[0].values.items()
                        if v is not None
                    })
            except Exception:
                pass

            # sweep variables 자동 결정
            sweep_vars = []
            if "포장단중" in q or "WGT_HIGH" in q or "WGT_LOW" in q:
                sweep_vars += ["ORDER_WGT_HIGH", "ORDER_WGT_LOW"]
            if "설계대기량" in q or "DESIGN_PEND_QTY" in q or "pend" in q.lower():
                sweep_vars.append("DESIGN_PEND_QTY")
            if not sweep_vars:
                sweep_vars = ["ORDER_WGT_HIGH", "DESIGN_PEND_QTY"]

            # 직접 sweep 계산 (endpoint 호출 없이 inline)
            from backend.section3.agents.simulation import evidence as ev
            hr_max = float(base_order.get("_HR_MAX_WGT", 25000))
            hr_min = float(base_order.get("_HR_MIN_WGT", 8000))
            import itertools, math
            def _grid(low: float, high: float, n: int = 5) -> list[float]:
                if n <= 1: return [(low + high) / 2]
                step = (high - low) / (n - 1)
                return [round(low + i * step, 1) for i in range(n)]
            var_ranges: dict[str, tuple[float, float]] = {}
            for v in sweep_vars:
                bv = float(base_order.get(v, 0) or 0)
                if v == "ORDER_WGT_HIGH":
                    var_ranges[v] = (max(hr_min + 1000, bv * 0.7 if bv else hr_min + 1000), min(hr_max, bv * 1.3 if bv else hr_max))
                elif v == "ORDER_WGT_LOW":
                    var_ranges[v] = (hr_min, max(hr_min + 2000, bv * 1.2 if bv else hr_max / 2))
                elif v == "DESIGN_PEND_QTY":
                    var_ranges[v] = (max(hr_min, bv * 0.5 if bv else hr_min * 2), bv * 2 if bv else hr_max * 3)
            grids = {v: _grid(rng[0], rng[1], 5) for v, rng in var_ranges.items()}
            grid_cells: list[dict[str, Any]] = []
            var_names = list(grids.keys())
            for combo in itertools.product(*[grids[v] for v in var_names]):
                cell_vars = dict(zip(var_names, combo))
                ow_high = cell_vars.get("ORDER_WGT_HIGH", base_order.get("ORDER_WGT_HIGH", hr_max))
                ow_low = cell_vars.get("ORDER_WGT_LOW", base_order.get("ORDER_WGT_LOW", hr_min))
                dpq = cell_vars.get("DESIGN_PEND_QTY", base_order.get("DESIGN_PEND_QTY", hr_max))
                wgt_cap = min(float(ow_high), hr_max)
                wgt_floor = max(float(ow_low), hr_min)
                vio: list[str] = []
                if wgt_floor > wgt_cap:
                    vio.append(f"하한({wgt_floor:.0f}) > 상한({wgt_cap:.0f})")
                    grid_cells.append({"vars": cell_vars, "projected_slab_wgt": 0,
                                        "projected_split_count": 0, "feasible": False, "violations": vio})
                    continue
                split_count = max(1, math.ceil(float(dpq) / wgt_cap))
                slab_wgt = float(dpq) / split_count
                while slab_wgt < wgt_floor and split_count > 1:
                    split_count -= 1
                    slab_wgt = float(dpq) / split_count
                if slab_wgt < wgt_floor: vio.append(f"slab_wgt({slab_wgt:.0f}) < 하한")
                if slab_wgt > wgt_cap: vio.append(f"slab_wgt({slab_wgt:.0f}) > 상한")
                grid_cells.append({
                    "vars": cell_vars,
                    "projected_split_count": split_count,
                    "projected_slab_wgt": round(slab_wgt, 1),
                    "feasible": len(vio) == 0,
                    "violations": vio,
                })
            feasible = [c for c in grid_cells if c["feasible"]]
            best = max(feasible, key=lambda c: c["projected_slab_wgt"], default=None)
            # Q3 interactive — backend 는 가상 주문 + sweep 초기 결과 둘 다 첨부.
            # frontend 는 stage 1 (가상 주문 표시·수정) → stage 2 (변경 전·후 입력) →
            # stage 3 (필요 시 sweep 재호출) → stage 4 (결과·LLM 분석)
            payload["_q3_interactive"] = {
                "virtual_order": base_order,
                "constraints": {
                    "HR_MAX_WGT": hr_max, "HR_MIN_WGT": hr_min,
                },
                "ontology_basis": [
                    "term.scm.order.order — 주문 master",
                    "rule.scm.slab.wgt_range (단중 상하한)",
                    "HR_MAX_WGT / HR_MIN_WGT 기준 테이블",
                ],
                "default_before": {
                    "ORDER_WGT_LOW": float(base_order.get("ORDER_WGT_LOW", hr_min)),
                    "ORDER_WGT_HIGH": float(base_order.get("ORDER_WGT_HIGH", hr_max * 0.8)),
                    "DESIGN_PEND_QTY": float(base_order.get("DESIGN_PEND_QTY", hr_max)),
                },
                "default_after_hint": {
                    "ORDER_WGT_LOW": round(float(base_order.get("ORDER_WGT_LOW", hr_min)) * 1.1, 0),
                    "ORDER_WGT_HIGH": round(float(base_order.get("ORDER_WGT_HIGH", hr_max * 0.8)) * 1.1, 0),
                    "DESIGN_PEND_QTY": round(float(base_order.get("DESIGN_PEND_QTY", hr_max)) * 1.2, 0),
                },
            }
            payload["_weight_sweep"] = {
                "base_order": base_order,
                "sweep_variables": sweep_vars,
                "var_ranges": {k: [v[0], v[1]] for k, v in var_ranges.items()},
                "grid": grid_cells,
                "best": best,
                "total_cells": len(grid_cells),
                "feasible_cells": len(feasible),
                "summary": (
                    f"최적 조합 — slab 단중 최대 {best['projected_slab_wgt']:,.0f}kg "
                    f"({best['projected_split_count']} split). 변수: "
                    + ", ".join(f"{k}={v:,.0f}" for k, v in best['vars'].items())
                ) if best else "feasible 조합 없음 — 제약 위반",
            }
        except Exception as e:  # noqa: BLE001
            logger.warning("weight sweep 자동 실행 실패: %s", e)

    # ── 신뢰도 evidence bundle (impact) ─────────────────────────────────────
    try:
        from backend.section3.agents.simulation import evidence as ev
        bundle = ev.EvidenceBundle()
        tc = payload.get("_target_change") or {}
        if tc.get("table") and tc.get("column"):
            bundle.add("_target_change.table", ev.Evidence(
                kind="inference",
                summary=f"자연어 키워드 → table 매핑: '{tc['table']}'",
                confidence=0.7,
                detail=f"user_query 에서 '{tc['table']}' 또는 한국어 alias (예: '연주설비사양') 매칭",
            ))
            bundle.add("_target_change.column", ev.Evidence(
                kind="inference",
                summary=f"자연어 키워드 → column 매핑: '{tc['column']}'",
                confidence=0.65,
                detail="user_query 에서 columname 직접 등장 또는 한국어 키워드 (두께/단중/폭/길이) 매칭",
            ))
            if tc.get("before") is not None:
                bundle.add("_target_change.before", ev.seed_data(
                    tc["table"], tc["column"], tc["before"],
                ))
        for r in payload.get("_affected_rules") or []:
            bundle.add("_affected_rules", ev.business_rule(
                r.get("fqn", ""), r.get("statement", ""), r.get("severity", "soft"),
            ))
        for m in (payload.get("affected_methods") or [])[:10]:
            bundle.add("affected_methods", ev.ontology_action(
                m.get("action_fqn", "") or m.get("fqn", ""),
                m.get("action_label"),
            ))
        for o in (payload.get("_affected_orders") or [])[:10]:
            bundle.add("_affected_orders", ev.seed_data(
                "ORDER_OM/QD", "ORDER_NO", o.get("ORDER_NO", ""),
            ))
        payload["_evidence"] = bundle.to_dict()
    except Exception as e:  # noqa: BLE001
        logger.warning("impact evidence bundle 실패: %s", e)


def _attach_related_methods_fallback(payload: dict, *, repo_id: str) -> None:
    """affected_methods 가 0건일 때 — detected term 의 관련 action 의 realization (method) 으로 fallback.

    사용자 요구 (2026-05-25): "영향받는 코드 0건이면, 관련 있는 코드라도 띄우게".
    ontology 만으로 처리 — Java 소스 직접 검색 0건.
    """
    if payload.get("affected_methods"):
        return  # 이미 있음
    detected = payload.get("_detected_terms") or []
    if not detected:
        return
    try:
        from sqlalchemy import select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.mapping_layer.orm import ActionRow, RealizationRow
        import json as _json
        term_fqns = {d.get("term_fqn") for d in detected if d.get("term_fqn")}
        if not term_fqns:
            return
        related: list[dict] = []
        seen: set[str] = set()
        with session_scope() as s:
            actions = s.execute(
                select(ActionRow).where(ActionRow.repo_id == repo_id)
            ).scalars().all()
            related_action_fqns: set[str] = set()
            for a in actions:
                try:
                    params = _json.loads(a.params_json or "[]")
                except Exception:
                    params = []
                param_terms = [p.get("object_ref_term") for p in params if isinstance(p, dict)]
                try:
                    output = _json.loads(a.output_json or "{}")
                except Exception:
                    output = {}
                output_term = output.get("object_ref_term") if isinstance(output, dict) else None
                if (a.declared_on_term in term_fqns
                    or any(t in term_fqns for t in param_terms)
                    or output_term in term_fqns):
                    related_action_fqns.add(a.fqn)
            if not related_action_fqns:
                return
            real_rows = s.execute(
                select(RealizationRow).where(
                    RealizationRow.repo_id == repo_id,
                    RealizationRow.action_fqn.in_(related_action_fqns),
                )
            ).scalars().all()
            for r in real_rows:
                fqn = r.code_method_fqn or ""
                if not fqn or fqn in seen:
                    continue
                # @Test 클래스 제외
                cname = fqn.split("(")[0].rsplit(".", 1)[0].rsplit(".", 1)[-1]
                if cname.endswith("Test") or cname.endswith("Tests"):
                    continue
                seen.add(fqn)
                related.append({
                    "fqn": fqn,
                    "action_fqn": r.action_fqn,
                    "action_label": r.action_fqn.split(".")[-1] if r.action_fqn else "",
                    "kind": "related (term→action→method)",
                })
                if len(related) >= 8:
                    break
        if related:
            payload["affected_methods"] = related
            payload["_affected_methods_source"] = "related"
    except Exception as e:  # noqa: BLE001
        logger.warning("related methods fallback 실패: %s", e)


async def _enrich_explain_weight_catalog(
    payload: dict, *, user_query: str, repo_id: str,
) -> bool:
    """Q1 — "slab 단중에 영향을 주는 변수" 같은 카탈로그 질문 전용.

    단중/두께/폭/길이 등 weight-influence 키워드가 query 에 있으면, ontology 에서
    관련 Term/Action/BusinessRule 을 자동 집계하고, 사용자 목적 (단중 최대화) 에
    맞게 "어떤 변수를 어느 방향으로 움직이면 단중이 ↑ 하는지" 정리.

    return True 면 catalog 가 채워짐 (frontend 가 _weight_catalog 보고 맞춤 UI 렌더).
    """
    q = user_query or ""
    # 트리거 키워드 — "단중 영향 / 영향 주는 변수 / 단중 최대화 / 단중 관련 변수"
    triggers = [
        "단중에 영향", "단중 영향", "영향을 주는 변수", "단중 최대화",
        "단중을 최대", "단중 관련 변수",
    ]
    if not any(t in q for t in triggers):
        return False

    from sqlalchemy import select
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow
    import json as _json
    from backend.section3.agents.simulation import evidence as ev

    # 단중 관련 term 자동 발굴
    KEYWORDS_KO = ("단중", "두께", "폭", "길이", "중량")
    KEYWORDS_EN = ("wgt", "weight", "thickness", "width", "length")

    weight_terms: list[dict] = []
    try:
        with session_scope() as s:
            rows = s.execute(
                select(BusinessTermRow).where(BusinessTermRow.repo_id == repo_id)
            ).scalars().all()
            for r in rows:
                label = r.label or ""
                desc = r.description or ""
                try:
                    aliases = _json.loads(r.aliases_json or "[]")
                except Exception:
                    aliases = []
                # test 클래스 term 제외
                if "Test" in label or "test" in r.fqn:
                    continue
                hit_ko = any(k in label or k in desc for k in KEYWORDS_KO)
                hit_en = any(
                    k in (label.lower() or "") or k in (r.fqn or "").lower()
                    or any(k in a.lower() for a in aliases)
                    for k in KEYWORDS_EN
                )
                if hit_ko or hit_en:
                    weight_terms.append({
                        "fqn": r.fqn,
                        "label": label,
                        "description": (desc or "")[:200],
                        "aliases": aliases[:4],
                        "kind": r.kind,
                        "value_type": r.value_type,
                    })
    except Exception as e:  # noqa: BLE001
        logger.warning("weight catalog term lookup 실패: %s", e)
        return False

    if not weight_terms:
        return False

    # 단중 계산 공식 → 영향 방향 + 변수 카탈로그
    # weight = thickness * width * length * density (step 4 SdFirstWeightAction)
    # → thickness ↑ → weight ↑
    # → width ↑ → weight ↑ (단, slab 폭 제약 범위 내)
    # → length ↑ → weight ↑ (단, slab 길이 제약 범위 내)
    # → density 는 grade 별 고정
    # weight 상하한: HR_MIN_WGT / HR_MAX_WGT / CUSTOMER_STD 가 외부 제약
    influence_map: list[dict] = [
        {
            "variable": "slab 두께 (slabThickness)",
            "table_column": "CAST_SPEC.SLAB_THICKNESS",
            "direction": "비례",
            "formula_role": "weight = thickness × width × length × density",
            "rationale": "두께가 커질수록 단중 선형 증가. 단 CAST_SPEC 의 thickness 는 설비별 고정값에 가까워 일반 운영에서 자주 조정하지 않음.",
            "constraint": "CAST_SPEC.SLAB_THICKNESS 자체가 설비 능력 (연주기 cast machine) 제약",
            "controllable_by": "공장 설비 변경 (장기 의사결정)",
        },
        {
            "variable": "slab 폭 (slabWidth)",
            "table_column": "CAST_SPEC.WIDTH_LOW/HIGH ∩ HR_SPEC.WIDTH_LOW/HIGH ∩ EDGING_GROUP",
            "direction": "비례",
            "formula_role": "weight = thickness × [폭] × length × density",
            "rationale": "폭 ↑ → 단중 ↑. 단 연주기·열연·EDGING 의 폭 범위 교집합 안에서만 가능.",
            "constraint": "WIDTH_LOW ≤ slabWidth ≤ WIDTH_HIGH (3개 설비 교집합)",
            "controllable_by": "EDGING_GROUP HR_TGT_WIDTH_LOW/HIGH 조정 (운영 변경)",
        },
        {
            "variable": "slab 길이 (slabLength)",
            "table_column": "CAST_SPEC.LENGTH_LOW/HIGH ∩ HR_SPEC.LENGTH_LOW/HIGH",
            "direction": "비례",
            "formula_role": "weight = thickness × width × [길이] × density",
            "rationale": "길이 ↑ → 단중 ↑. 그러나 설계대기량 (DESIGN_PEND_QTY) 이 작으면 긴 slab 불필요 → splitCount 줄여서 길이 조정.",
            "constraint": "LENGTH_LOW ≤ slabLength ≤ LENGTH_HIGH",
            "controllable_by": "주문 input — DESIGN_PEND_QTY 가 충분히 크면 길이 ↑",
        },
        {
            "variable": "분할수 (splitCount)",
            "table_column": "Step 7~8 SdSplitRangeAction 계산",
            "direction": "반비례",
            "formula_role": "splitWgt = totalWgt / splitCount",
            "rationale": "분할 ↓ → 1 slab 당 단중 ↑. 단 splitCount 는 polygon 제약 (HR_MAX_WGT, HR_MIN_WGT, ORDER_WGT_HIGH/LOW) 만족하는 최소값을 자동 선택.",
            "constraint": "각 split 의 단중이 HR_MIN_WGT ≤ wgt ≤ HR_MAX_WGT 만족 필요",
            "controllable_by": "HR_MAX_WGT 상향 또는 ORDER_WGT_HIGH 상향",
        },
        {
            "variable": "설계대기량 (designPendQty)",
            "table_column": "ORDER_OM.DESIGN_PEND_QTY",
            "direction": "비례 (간접)",
            "formula_role": "totalWgt = sum(designPendQty) — slab 들의 합",
            "rationale": "총 단중량의 직접 input. 클수록 분할수 증가 가능 + 1 slab 당 단중도 상한 근처까지 가능.",
            "constraint": "주문 자체의 발주량 — 시뮬에선 가상 input 으로 sweep 가능",
            "controllable_by": "사용자가 가설 시나리오로 조정 (실제 발주량 변경)",
        },
        {
            "variable": "포장단중 상한 (ORDER_WGT_HIGH)",
            "table_column": "ORDER_OM.ORDER_WGT_HIGH",
            "direction": "비례 (제약 완화)",
            "formula_role": "slab.wgt ≤ ORDER_WGT_HIGH 제약",
            "rationale": "주문 측에서 받을 수 있는 최대 단중. 이 값이 커질수록 slab 단중 ↑ 여지 ↑. HR_MAX_WGT 와 min() 으로 실제 상한 결정.",
            "constraint": "ORDER_WGT_LOW ≤ slab.wgt ≤ min(ORDER_WGT_HIGH, HR_MAX_WGT)",
            "controllable_by": "주문 자체 수정 — 고객 협의 필요",
        },
        {
            "variable": "포장단중 하한 (ORDER_WGT_LOW)",
            "table_column": "ORDER_OM.ORDER_WGT_LOW",
            "direction": "직접 영향 없음 (제약)",
            "formula_role": "slab.wgt ≥ ORDER_WGT_LOW",
            "rationale": "최저 단중을 보장. 하한 ↑ 면 작은 split 이 막혀 분할수 ↓ → 1 slab 단중 ↑ 효과 가능.",
            "constraint": "ORDER_WGT_LOW ≤ HR_MAX_WGT 이어야 split 가능",
            "controllable_by": "주문 수정",
        },
        {
            "variable": "HR 최대 단중 (HR_MAX_WGT)",
            "table_column": "HR_MAX_WGT.MAX_WGT",
            "direction": "비례 (제약 완화)",
            "formula_role": "각 slab.wgt ≤ HR_MAX_WGT",
            "rationale": "열연 압연 설비의 1 slab 처리 가능 최대 단중. 이 값이 커질수록 slab 단중 상한 ↑.",
            "constraint": "물리 설비 능력",
            "controllable_by": "공장 설비 능력 향상 (장기)",
        },
    ]

    payload["_weight_catalog"] = {
        "title": "slab 설계 단중에 영향을 주는 변수",
        "purpose": "단중 최대화 — 제약을 어기지 않는 범위에서 어떤 변수를 어느 방향으로 움직일지",
        "core_formula": "slab.wgt = slabThickness × slabWidth × slabLength × density",
        "external_constraint": "ORDER_WGT_LOW ≤ wgt ≤ min(ORDER_WGT_HIGH, HR_MAX_WGT, CUSTOMER_STD.wgt)",
        "variables": influence_map,
        "ontology_terms": weight_terms[:15],
        "controllable_summary": [
            {
                "priority": "🔝 단기 조정 가능",
                "items": ["포장단중 상한 (ORDER_WGT_HIGH)", "포장단중 하한 (ORDER_WGT_LOW)",
                          "설계대기량 (DESIGN_PEND_QTY)"],
                "note": "주문 수정으로 바로 적용. Q3 시나리오와 동일.",
            },
            {
                "priority": "🔧 중기 조정 가능",
                "items": ["EDGING_GROUP HR_TGT_WIDTH_HIGH 상향",
                          "CUSTOMER_STD 단중 제약 완화 (고객 협의)"],
                "note": "ontology 기준 데이터 수정 + 영향 사전 시뮬",
            },
            {
                "priority": "🏭 장기 (설비 변경)",
                "items": ["CAST_SPEC.WIDTH_HIGH (연주기 폭)", "HR_MAX_WGT 상향 (열연 능력)"],
                "note": "물리 설비 투자 필요",
            },
        ],
    }

    # summary 자연어 합성 — 마크업 제거, 단락 분리
    payload["summary"] = (
        f"slab 단중에 영향을 주는 변수 {len(influence_map)}개를 ontology 에서 식별했습니다\n"
        f"\n"
        f"단중 계산 공식\n"
        f"  weight = thickness × width × length × density\n"
        f"\n"
        f"외부 제약\n"
        f"  {payload['_weight_catalog']['external_constraint']}\n"
        f"\n"
        f"단중 최대화 우선순위\n"
        f"  단기 조정: 포장단중 상한 ORDER_WGT_HIGH, 설계대기량 DESIGN_PEND_QTY\n"
        f"  중기 조정: EDGING_GROUP HR_TGT_WIDTH_HIGH\n"
        f"  장기 조정: HR_MAX_WGT 상향"
    )

    # evidence — ontology term 매칭은 ontology 근거
    bundle = ev.EvidenceBundle()
    for t in weight_terms[:15]:
        bundle.add("ontology_terms", ev.ontology_term(t["fqn"], t["label"], detail=t.get("description")))
    for v in influence_map:
        bundle.add(f"variables[{v['variable']}].direction", ev.Evidence(
            kind="propagation",
            summary=f"{v['variable']} → 단중 {v['direction']}",
            confidence=0.85,
            source_ref=v["table_column"],
            detail=v["formula_role"],
        ))
        bundle.add(f"variables[{v['variable']}].constraint", ev.business_rule(
            "domain_constraint",
            v["constraint"],
            severity="hard",
        ))
        bundle.add(f"variables[{v['variable']}].controllable_by", ev.inference(
            v["rationale"], confidence=0.75,
        ))
    payload["_evidence"] = bundle.to_dict()
    return True


async def _enrich_explain_payload(
    payload: dict, *, user_query: str, repo_id: str,
) -> None:
    """explain intent 의 핵심 — atomic term 질문에 직접 답변 합성.

    auto-pick 된 무관한 Action 본문에 의존하지 않고, _detected_terms 중 score 가 가장
    높은 term 의 ontology fan-out (get_term + effective_parts + related_actions
    + business_rules + anchor_bindings) 결과를 payload 의 _term_explain 키에 첨부.
    summary 도 자연어로 합성.
    """
    detected = payload.get("_detected_terms") or []
    if not detected:
        return
    # match score — 정확 매칭 우선 (token == label 또는 token in aliases)
    primary = detected[0]
    for d in detected:
        tok = (d.get("token") or "").lower()
        label = (d.get("label") or "").lower()
        aliases = [a.lower() for a in (d.get("aliases") or [])]
        if tok == label or tok in aliases:
            primary = d
            break

    term_fqn = primary.get("term_fqn")
    if not term_fqn:
        return

    try:
        from backend.section3.clients.modeling_client import get_modeling_client
        client = get_modeling_client()
        term = await client.get_term(term_fqn)
        parts = await client.get_term_effective_parts(term_fqn, repo_id=repo_id) or []
        all_actions = await client.list_actions(repo_id=repo_id, limit=2000) or []
        all_rules = await client.list_business_rules(repo_id=repo_id) or []
        all_anchors = await client.list_anchor_bindings(repo_id=repo_id) or []
    except Exception as e:  # noqa: BLE001
        logger.warning("explain enrich 실패 (term=%s): %s", term_fqn, e)
        return

    # related actions — declared_on_term + params + output 매칭
    related_actions: list[dict] = []
    related_action_fqns: set[str] = set()
    for a in all_actions:
        declared = a.get("declared_on_term")
        params = a.get("params") or []
        param_terms = [p.get("object_ref_term") for p in params if isinstance(p, dict)]
        output = a.get("output") or {}
        output_term = output.get("object_ref_term") if isinstance(output, dict) else None
        if term_fqn == declared or term_fqn in param_terms or term_fqn == output_term:
            kind = "declared_on" if term_fqn == declared else (
                "param" if term_fqn in param_terms else "output")
            related_actions.append({
                "fqn": a.get("fqn"), "label": a.get("label"), "kind": kind,
                "description": (a.get("description") or "")[:300],
            })
            related_action_fqns.add(a.get("fqn"))

    business_rules: list[dict] = []
    for r in all_rules:
        if term_fqn in (r.get("terms_ref") or []):
            business_rules.append({
                "fqn": r.get("fqn"),
                "statement": (r.get("statement") or "")[:240],
                "severity": r.get("severity"),
                "enforced_by": (r.get("enforced_by") or [])[:5],
            })

    anchor_bindings: list[dict] = []
    term_short = term_fqn.split(".")[-1] if "." in term_fqn else term_fqn
    for ab in all_anchors:
        target_action = ab.get("target_action_fqn") or ""
        target_slot = ab.get("target_slot") or ""
        if target_action in related_action_fqns or term_short in target_slot:
            anchor_bindings.append({
                "anchor_id": ab.get("id"),
                "method_fqn": ab.get("code_method_fqn"),
                "target_action_fqn": target_action,
                "target_slot": target_slot,
                "anchor_locator": ab.get("anchor_locator"),
                "line": ab.get("line"),
            })

    # 사용자 요구 (2026-05-23): java 소스 직접 보는 anchor_bindings 는 agent 표면에서
    # 제외 — ontology + AI 추론만으로 작동해야 함. anchor 자체 metadata 는 유지하되 (1건)
    # 강조 surface 안 함.
    payload["_term_explain"] = {
        "term_fqn": term_fqn,
        "term": term,
        "effective_parts": parts,
        "related_actions": related_actions[:20],
        "business_rules": business_rules[:10],
        # anchor_bindings 는 사용자 요구로 표면에서 제거. 필요 시 별도 토글로.
        "_anchor_count_hint": len(anchor_bindings),  # 카운트만 hint
    }

    # ── 신뢰도 evidence bundle (2026-05-23) — ontology + AI 추론만 ─────────
    from backend.section3.agents.simulation import evidence as ev
    bundle = ev.EvidenceBundle()
    # term 본문
    bundle.add(
        "term",
        ev.ontology_term(
            term_fqn,
            label=(term or {}).get("label"),
            detail=(term or {}).get("description"),
        ),
    )
    for a in (term or {}).get("aliases") or []:
        bundle.add(f"aliases", ev.Evidence(
            kind="ontology", summary=f"alias '{a}'",
            confidence=0.95, source_ref=f"{term_fqn}.aliases",
        ))
    # related actions
    for a in related_actions[:20]:
        bundle.add("related_actions", ev.ontology_action(a["fqn"], a.get("label")))
    # business rules — 사용자 요구상 java 근거가 아니라 ontology 의 일부로 분류
    for r in business_rules[:10]:
        bundle.add(
            "business_rules",
            ev.Evidence(
                kind="ontology",
                summary=f"business rule [{r.get('severity','soft')}]: {r['fqn']}",
                confidence=0.95 if r.get("severity") == "hard" else 0.85,
                source_ref=r["fqn"],
                detail=r.get("statement"),
            ),
        )
    # summary 합성 (자연어) — AI 추론
    bundle.add("summary", ev.inference(
        f"ontology fields (label/aliases/description) 기반 자연어 답변 합성",
        confidence=0.85,
    ))
    payload["_evidence"] = bundle.to_dict()

    # 자연어 summary 합성 — 가독성 우선. 단락 사이 빈 줄로 호흡.
    label = (term or {}).get("label") or primary.get("label")
    desc = (term or {}).get("description") or ""
    aliases = (term or {}).get("aliases") or []
    aliases_clean = [a for a in aliases if a != label][:6]
    kind = (term or {}).get("kind") or ""
    value_type = (term or {}).get("value_type")
    unit = (term or {}).get("unit")
    parts_count = len(parts)

    # description 을 문장 단위로 끊어 가독성 ↑
    sentences: list[str] = []
    for s in desc.replace("。", ".").split("."):
        s = s.strip()
        if s:
            sentences.append(s + ".")

    bits: list[str] = []
    # 1) 헤드라인 — 굵게, 한 줄
    head = f"{label}"
    if value_type:
        head += f" · {value_type}"
    if unit:
        head += f" ({unit})"
    if kind:
        head += f" — {kind} term"
    bits.append(head)

    # 2) 별칭 — 별도 단락
    if aliases_clean:
        bits.append("")
        bits.append(f"📝 별칭: {', '.join(aliases_clean)}")

    # 3) 정의 — 문장별로 줄 분리 (2~3 문장씩 묶기)
    if sentences:
        bits.append("")
        bits.append("📖 정의")
        # 2 문장씩 묶어 단락
        for i in range(0, len(sentences), 2):
            bits.append("  " + " ".join(sentences[i:i + 2]))

    # 4) 연관 — 단락 분리 + 글머리 기호
    extras: list[str] = []
    if parts_count:
        extras.append(f"구성요소 {parts_count}건")
    if related_actions:
        extras.append(f"관련 action {len(related_actions)}건")
    if business_rules:
        extras.append(f"business rule {len(business_rules)}건")
    if extras:
        bits.append("")
        bits.append("🔗 ontology 연관: " + ", ".join(extras))

    payload["summary"] = "\n".join(bits)
    # 무관한 body_text 의존 줄이기 — frontend hint
    payload["_explain_primary_source"] = "term"


async def _enrich_locate_payload(
    payload: dict, *, user_query: str, repo_id: str, ontology_client: OntologyClient,
) -> None:
    """사용자 요구 (2026-05-23): java 소스 직접 grep 의존 제거. ontology
    anchor_bindings + action realizations 만으로 위치 찾기.

    기존 CodeMethodRow.body_text LIKE 매칭은 비활성화. 대신:
      - anchor_bindings 의 target_slot 에 사용자 keyword 매칭
      - business_terms 의 label/aliases 매칭 후 그 term 의 declared action → realization fqn
    """
    from sqlalchemy import select
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import (
        BusinessTermRow, ActionRow, AnchorBindingRow,
    )
    import json as _json
    import re

    tokens = [t for t in re.findall(r"[가-힣A-Za-z_]{2,}", user_query or "")]
    STOP = {"어디", "위치", "이고", "에서", "throw", "이거", "있어", "있나", "어디서",
            "찾기", "코드", "라인", "있는지", "the", "and", "in", "로직", "있어요"}
    tokens = [t for t in tokens if t.lower() not in STOP][:6]
    if not tokens:
        return

    locations: list[dict] = []
    try:
        with session_scope() as s:
            # 1) ontology terms 매칭 — token ↔ label/alias
            term_rows = s.execute(
                select(BusinessTermRow).where(BusinessTermRow.repo_id == repo_id)
            ).scalars().all()
            term_match: list[str] = []  # 매칭된 term fqn
            for r in term_rows:
                label = r.label or ""
                try: aliases = _json.loads(r.aliases_json or "[]")
                except Exception: aliases = []
                lo_l = label.lower()
                for tok in tokens:
                    tl = tok.lower()
                    if (tok in label or tl in lo_l
                        or any(tok in a or tl in a.lower() for a in aliases)):
                        term_match.append(r.fqn)
                        break

            # 2) anchor_bindings — target_slot 에 token 포함 또는 매칭 term 관련 action
            anchor_rows = s.execute(
                select(AnchorBindingRow).where(AnchorBindingRow.repo_id == repo_id)
            ).scalars().all()
            # term → action 매핑 (declared_on_term / params / output)
            action_rows = s.execute(
                select(ActionRow).where(ActionRow.repo_id == repo_id)
            ).scalars().all()
            term_to_action_fqns: set[str] = set()
            for a in action_rows:
                try:
                    params = _json.loads(a.params_json or "[]")
                except Exception:
                    params = []
                param_terms = [p.get("object_ref_term") for p in params if isinstance(p, dict)]
                try:
                    output = _json.loads(a.output_json or "{}")
                except Exception:
                    output = {}
                output_term = output.get("object_ref_term") if isinstance(output, dict) else None
                if (a.declared_on_term in term_match
                    or any(t in term_match for t in param_terms)
                    or output_term in term_match):
                    term_to_action_fqns.add(a.fqn)

            seen_fqns: set[str] = set()
            for ab in anchor_rows:
                method_fqn = ab.code_method_fqn or ""
                target_slot = ab.target_slot or ""
                target_action = ab.target_action_fqn or ""
                locator = ab.anchor_locator or ""
                hit_reason: str | None = None
                # token 매칭
                for tok in tokens:
                    tl = tok.lower()
                    if (tok in target_slot or tl in target_slot.lower()
                        or tok in locator or tl in locator.lower()):
                        hit_reason = f"slot/locator 매칭: {tok}"; break
                # term-action 통한 간접 매칭
                if not hit_reason and target_action in term_to_action_fqns:
                    hit_reason = "감지된 term 의 관련 action"
                if hit_reason and method_fqn and method_fqn not in seen_fqns:
                    seen_fqns.add(method_fqn)
                    locations.append({
                        "method_fqn": method_fqn,
                        "method_name": method_fqn.split(".")[-1].split("(")[0] if "." in method_fqn else method_fqn,
                        "file_path": (method_fqn.split("(")[0].rsplit(".", 1)[0]).replace(".", "/") + ".java",
                        "line_start": ab.line,
                        "line_end": ab.line,
                        "matched_line": ab.line,
                        "keyword": hit_reason,
                        "snippet": "",  # body_text 직접 grep 제거 — ontology anchor 만 surface
                        "anchor_locator": locator,
                        "target_slot": target_slot,
                        "_source": "ontology_anchor",
                    })
                    if len(locations) >= 12:
                        break
        payload["_locate_matches"] = locations
        payload["_locate_source"] = "ontology_anchor_bindings_only"
    except Exception as e:  # noqa: BLE001
        logger.warning("ontology-only locate 실패: %s", e)
        return


async def _enrich_locate_payload_legacy(
    payload: dict, *, user_query: str, repo_id: str, ontology_client: OntologyClient,
) -> None:
    """locate intent — code_methods body_text/name 에 keyword 매칭되는 위치들 surface.

    각 위치마다 file_path · line range · body 스니펫 첨부.
    """
    from sqlalchemy import select, or_
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeMethodRow
    # keyword 추출 — 사용자 query 안의 한·영 토큰
    import re
    tokens = [t for t in re.findall(r"[가-힣A-Za-z_]{2,}", user_query or "")]
    # 너무 일반적인 단어 제거
    STOP = {"어디", "위치", "이고", "에서", "throw", "이거", "있어", "있나", "어디서",
            "찾기", "코드", "라인", "있는지", "the", "and", "in"}
    tokens = [t for t in tokens if t.lower() not in STOP][:6]
    if not tokens:
        return

    locations: list[dict] = []
    try:
        with session_scope() as s:
            for tok in tokens:
                rows = s.execute(
                    select(CodeMethodRow).where(
                        CodeMethodRow.repo_id == repo_id,
                        or_(
                            CodeMethodRow.fqn.ilike(f"%{tok}%"),
                            CodeMethodRow.body_text.ilike(f"%{tok}%"),
                            CodeMethodRow.name.ilike(f"%{tok}%"),
                        ),
                    ).limit(5)
                ).scalars().all()
                for r in rows:
                    # 본문 중 keyword 주변 snippet 추출
                    body = (r.body_text or "")
                    snippet = ""
                    line_in_body = -1
                    if body:
                        lower = body.lower()
                        idx = lower.find(tok.lower())
                        if idx >= 0:
                            # 해당 idx 가 몇 번째 줄인지
                            line_in_body = body[:idx].count("\n")
                            start_line = max(0, line_in_body - 2)
                            end_line = line_in_body + 3
                            snippet = "\n".join(body.split("\n")[start_line:end_line + 1])
                    abs_line = (r.line_start or 0) + line_in_body if line_in_body >= 0 else r.line_start
                    locations.append({
                        "method_fqn": r.fqn,
                        "method_name": r.name,
                        "file_path": (r.parent_type_fqn or "").replace(".", "/") + ".java",
                        "line_start": r.line_start,
                        "line_end": r.line_end,
                        "matched_line": abs_line,
                        "keyword": tok,
                        "snippet": snippet[:500],
                    })
        # dedupe by fqn, sort by matched line
        seen = set()
        deduped = []
        for l in locations:
            if l["method_fqn"] in seen: continue
            seen.add(l["method_fqn"])
            deduped.append(l)
        payload["_locate_matches"] = deduped[:12]
    except Exception as e:  # noqa: BLE001
        logger.warning("locate enrich 실패: %s", e)


async def _execute_hypothesis_from_query(
    *, session_id: str, user_query: str,
) -> dict:
    """hypothesis intent 의 query 에서 *명시적* 신규 기준 추출 후 workflow 호출.

    2026-05-25 재설계 — caller (`start` route) 가 "신규/추가/들어오" 시그널이 없으면
    이미 explain 으로 demote 한 상태로 도착하지만, 본 함수도 안전장치로 강화:
      - "신규 품종 X" / "신규 강종 X" / "SS\d{3,4}" 등 명시 코드 → new_standard_workflow
      - "productivity ×Y" 명시 → run_hypothesis
      - **그 외 (조건/sweep/증가/감소 류) → dynamic explain payload 반환**
        (default "신규 강종 SS500 추가" 가짜 답변 fallback 완전 제거)
    """
    import re
    order_no = extract_order_no(user_query) or "ORD20260510001"

    # ── 명시 신규 시그널 검사 ──
    has_new_signal = any(kw in user_query for kw in ("신규", "새 ", "새로운", "추가", "들어오", "도입"))

    # 신규 품종
    new_product_cd: str | None = None
    prod_code = re.search(r"신규\s*품종\s*([A-Z][A-Z0-9_-]{1,15})\b", user_query)
    if prod_code:
        new_product_cd = prod_code.group(1)
    elif has_new_signal and "품종" in user_query:
        new_product_cd = "SHEET"  # default 가상 품종 코드

    # 신규 강종
    new_grade_cd: str | None = None
    grade_match = re.search(r"신규\s*강종\s*([A-Z][A-Z0-9_-]{1,15})|새\s*강종\s*([A-Z][A-Z0-9_-]{1,15})", user_query)
    if grade_match:
        new_grade_cd = grade_match.group(1) or grade_match.group(2)
    elif has_new_signal:
        gm = re.search(r"\b(SS\d{2,4}|HC\d{2,4}[A-Z]?)\b", user_query)
        if gm:
            new_grade_cd = gm.group(0)
        elif "강종" in user_query:
            new_grade_cd = "SS500"

    # productivity multiplier (×0.95 등)
    mult_match = re.search(r"productivity\s*[×x*]\s*(\d+\.?\d*)", user_query, re.I)
    has_productivity = mult_match is not None

    payload: dict
    if has_productivity and new_grade_cd:
        # 기존 hypothesis_workflow (강종 productivity)
        mult = float(mult_match.group(1))
        r = await run_hypothesis(
            base_grade="SS400", new_grade=new_grade_cd,
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
    elif new_product_cd or new_grade_cd:
        # 신규 기준 추가 workflow — 명시 시그널 있을 때만
        from backend.section3.agents.simulation.new_standard_workflow import (
            run_new_standard_workflow as _run_ns,
        )
        r = await _run_ns(
            new_product_cd=new_product_cd, new_grade_cd=new_grade_cd,
            base_order_no=order_no,
        )
        payload = {
            "kind": "executed_new_standard",
            **r,
        }
    else:
        # 신규 시그널 없음 — default 가짜 답변 fallback 금지. dynamic explain payload.
        logger.info(
            "hypothesis without explicit new-standard signal — generate dynamic explain payload "
            "for query=%r", user_query[:100],
        )
        payload = {
            "kind": "executed_dynamic_explain",
            "user_query": user_query,
            "notes": [
                "이 질문은 '신규 X 추가' 형태가 아니므로 가상 강종/품종을 합성하지 않았습니다.",
                "ontology 매칭된 term 의 effective_parts · actions · business_rules 를 동적으로 fan-out 합니다.",
            ],
        }

    # 21-step walkthrough 첨부 — 질문 키워드에 맞춰 동적 합성
    try:
        _attach_walkthrough_steps(payload, user_query=user_query or "")
    except Exception:
        pass

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
        # 2026-05-25 — simulate 결과에도 walkthrough + LLM 분석 + dynamic blocks 첨부
        _user_q = sess.user_query or ""
        try: _attach_walkthrough_steps(payload, user_query=_user_q)
        except Exception: pass
        try:
            payload["_llm_analysis"] = _compose_llm_analysis(
                intent=intent, user_query=_user_q, payload=payload,
            )
        except Exception: pass
        try:
            from backend.section3.agents.simulation.dynamic_blocks import compose_dynamic_blocks
            payload["_dynamic_blocks"] = compose_dynamic_blocks(
                intent=intent, user_query=_user_q, payload=payload,
            )
        except Exception: pass
        # 슬랩→Slab 강제 (LLM 출력 일괄 정규화)
        try:
            if payload.get("_dynamic_blocks"):
                payload["_dynamic_blocks"] = _enforce_slab_korean(payload["_dynamic_blocks"])
            if payload.get("_llm_analysis"):
                payload["_llm_analysis"] = _enforce_slab_korean(payload["_llm_analysis"])
            if payload.get("_walkthrough_insight"):
                payload["_walkthrough_insight"] = _enforce_slab_korean(payload["_walkthrough_insight"])
        except Exception: pass
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


class WeightOptimizationRequest(BaseModel):
    """Q3 — 포장단중 상하한 + 설계대기량 sweep → slab 단중 최대화 추천.

    사용자가 base order (또는 가상 주문 1건) + sweep 할 변수와 범위 지정 → 다수
    조합을 시뮬해서 best slab 단중 케이스 추천.
    """
    base_order: dict[str, Any]                  # ORDER_OM 1건 (실측 또는 virtual)
    sweep_variables: list[str] = Field(default_factory=lambda: ["ORDER_WGT_HIGH", "DESIGN_PEND_QTY"])
    grid_size: int = 5                           # 변수당 분할 개수
    repo_id: str = "slab-design-real-v2"


class WeightOptimizationResponse(BaseModel):
    base_order: dict[str, Any]
    sweep_variables: list[str]
    grid: list[dict[str, Any]]                   # 각 cell: {vars, projected_slab_wgt, feasible, violations}
    best: dict[str, Any] | None                  # 최적 cell
    summary: str
    evidence: dict[str, Any]
    # 2026-05-25 — best 결과에 대한 21-step 산식 trace (walkthrough 형식)
    calculation_trace: list[dict[str, Any]] = Field(default_factory=list)
    var_ranges: dict[str, list[float]] = Field(default_factory=dict)


def _build_calculation_trace(base: dict, best: dict | None,
                             hr_max: float, hr_min: float) -> list[dict[str, Any]]:
    """best 조합 기준 21-step 산식 trace 생성 (walkthrough.md 형식).
    각 step: {step_no, title, formula, computation, result, unit, notes}
    """
    if not best:
        return []
    vars_ = best.get("vars") or {}
    ow_high = vars_.get("ORDER_WGT_HIGH", base.get("ORDER_WGT_HIGH"))
    ow_low  = vars_.get("ORDER_WGT_LOW",  base.get("ORDER_WGT_LOW"))
    dpq     = vars_.get("DESIGN_PEND_QTY", base.get("DESIGN_PEND_QTY"))
    width   = base.get("ORDER_WIDTH") or 0
    length  = base.get("ORDER_LENGTH") or 0
    thickness = base.get("_THICKNESS", 230)   # CAST_SPEC 추정값 (실측 안 가져옴)
    density = 7.82
    productivity = base.get("_PRODUCTIVITY", 0.90307)
    split = best.get("projected_split_count") or 1
    slab_wgt = best.get("projected_slab_wgt") or 0

    def _kg(v): return f"{float(v):,.2f} kg" if v else "—"
    def _mm(v): return f"{float(v):,.0f} mm" if v else "—"
    def _f(v):  return f"{float(v):,.4f}" if v else "—"

    trace: list[dict[str, Any]] = []
    trace.append({
        "step_no": 1, "title": "Slab 두께 결정",
        "formula": "CAST_SPEC.slabThickness 룩업 (smCd, castCd, machineCd, productCd)",
        "computation": f"CAST_SPEC 조회 → slabThickness = {thickness}",
        "result": f"{thickness} mm", "phase": "phase_2a",
        "notes": "PlantMapping 으로 smCd → (cast, machine) 추정",
    })
    if width:
        trace.append({
            "step_no": 2, "title": "Slab 폭 범위 (1차)",
            "formula": "max(CAST/HR.widthLow, hrTgtWidth+edgingCapLow) ≤ width ≤ min(CAST/HR.widthHigh, hrTgtWidth+edgingCapHigh)",
            "computation": f"base.ORDER_WIDTH={width} → EDGING_GROUP/SPEC 매칭 후 폭 범위 결정",
            "result": f"width ≈ {width} mm (1차 폭 범위 안)", "phase": "phase_2a",
        })
    if length:
        trace.append({
            "step_no": 3, "title": "Slab 길이 범위 (1차)",
            "formula": "max(CAST.lengthLow, HR.lengthLow) ≤ length ≤ min(CAST.lengthHigh, HR.lengthHigh)",
            "computation": f"base.ORDER_LENGTH={length} → 연주·열연 교집합",
            "result": f"length ≈ {length} mm", "phase": "phase_2a",
        })

    fw_high = thickness * width * length * density * 1e-6 if (width and length) else 0
    if fw_high:
        trace.append({
            "step_no": 4, "title": "1차 무게 범위 (순수 산식)",
            "formula": "무게(kg) = 두께(mm) × 폭(mm) × 길이(mm) × 비중(7.82) × 1e-6",
            "computation": f"{thickness} × {width} × {length} × {density} × 1e-6 = {_kg(fw_high)}",
            "result": _kg(fw_high), "phase": "phase_2a",
            "notes": "Phase 2-A step 4 — 폭·길이 범위 양 끝값으로 1차 무게 범위 산출",
        })

    trace.append({
        "step_no": 5, "title": "2차 무게 하한 (압연·고객 한도 적용)",
        "formula": "secondWgtLow = max(firstWgtLow, HR_MIN_WGT, [CUSTOMER_STD.wgtLow])",
        "computation": f"max({_kg(fw_high)}, HR_MIN={_kg(hr_min)}) → 압연 최소단중 적용",
        "result": _kg(max(fw_high or 0, hr_min)), "phase": "phase_2a",
    })

    yield_adj = dpq / productivity if (dpq and productivity) else 0
    sw_high = min(ow_high or 0, hr_max, yield_adj)
    trace.append({
        "step_no": 6, "title": "2차 무게 상한 ★ (설계대기량/HR_MAX 적용)",
        "formula": "secondWgtHigh = min(firstWgtHigh, HR_MAX_WGT, ORDER_WGT_HIGH, designPendQty/productivity)",
        "computation": (f"yieldAdjustedDesignPendHigh = {dpq} / {productivity} = {_kg(yield_adj)}\n"
                       f"min(ORDER_WGT_HIGH={_kg(ow_high)}, HR_MAX={_kg(hr_max)}, {_kg(yield_adj)}) "
                       f"→ {_kg(sw_high)}"),
        "result": _kg(sw_high), "phase": "phase_2a",
        "notes": "이 step 이 단중 상한을 가장 강하게 좁힘 — 주문 한도 또는 설계대기량이 결정자가 되는 경우 많음",
    })

    if sw_high and ow_high and productivity:
        max_split_raw = sw_high / ow_high / productivity
        import math
        max_split = math.ceil(max_split_raw)
        trace.append({
            "step_no": 7, "title": "최대 분할수 계산",
            "formula": "maxSplitCountUpper = ceil(secondWgtHigh / orderWgtHigh / productivity)",
            "computation": f"ceil({_kg(sw_high)} / {_kg(ow_high)} / {productivity}) = ceil({max_split_raw:.3f}) = {max_split}",
            "result": f"{max_split} 분할", "phase": "phase_2a",
            "notes": "A-a 루프는 maxSplitCountUpper 부터 -1 씩 감소시키며 step 8 통과까지 시도",
        })

    trace.append({
        "step_no": 8, "title": "A-a 루프 — 분할 단중 범위",
        "formula": "splitWgtLow=max(orderWgtLow×split/productivity, secondWgtLow)\nsplitWgtHigh=min(orderWgtHigh×split/productivity, secondWgtHigh)",
        "computation": (f"split={split} 으로 수렴\n"
                       f"orderRangeLow  = {ow_low} × {split} / {productivity} = {_kg((ow_low or 0)*split/productivity)}\n"
                       f"orderRangeHigh = {ow_high} × {split} / {productivity} = {_kg((ow_high or 0)*split/productivity)}\n"
                       f"교집합 → splitWgtHigh = {_kg(sw_high)}"),
        "result": f"splitWgtHigh = {_kg(sw_high)} (split={split})", "phase": "phase_2b",
        "notes": "splitWgtLow > splitWgtHigh 면 DG108 throw → split -= 1 재시도",
    })

    trace.append({
        "step_no": 9, "title": "Slab 매수 계산",
        "formula": "slabCount = floor(designPendQty / productivity / splitWgtHigh)",
        "computation": f"floor({dpq} / {productivity} / {_kg(sw_high)}) = {split} 매",
        "result": f"매수 {split}", "phase": "phase_2b",
    })

    trace.append({
        "step_no": 10, "title": "초기 Slab 단중 + 검증",
        "formula": "slabWgt = splitWgtHigh ∈ [designPendQtyLow/productivity, designPendQtyHigh/productivity]?",
        "computation": f"slabWgt = {_kg(slab_wgt)} 확정 — 설계대기량 범위 안",
        "result": _kg(slab_wgt), "phase": "phase_2b",
    })

    if slab_wgt and width and thickness:
        # 16~17 final width/length range (역산)
        import math
        fwl = math.ceil(slab_wgt * 1e6 / ((length or 12000) * thickness * density)) if length else None
        fwh = math.floor(slab_wgt * 1e6 / ((4000) * thickness * density)) if thickness else None
        trace.append({
            "step_no": 16, "title": "최종 폭 범위 (역산)",
            "formula": "폭 = 무게×1e6 / (길이×두께×비중)",
            "computation": (f"길이 최대일 때 → 폭 최소: ceil({slab_wgt:.2f}×1e6 / ({length or 12000}×{thickness}×{density})) = {fwl or '—'}\n"
                           f"길이 최소(4000)일 때 → 폭 최대: floor({slab_wgt:.2f}×1e6 / (4000×{thickness}×{density})) = {fwh or '—'}"),
            "result": f"{fwl or '—'} ~ {fwh or '—'} mm", "phase": "phase_2c",
        })
    trace.append({
        "step_no": 18, "title": "목표 폭 결정 (10mm 단위)",
        "formula": "targetSlabWidth = ceil(raw / 10) × 10",
        "computation": f"폭 raw 값을 10mm 단위로 올림 → 현장 가공 편의",
        "result": f"{round((width or 1000)/10)*10} mm", "phase": "phase_2c",
    })
    trace.append({
        "step_no": 19, "title": "목표 길이 결정 (1mm 단위)",
        "formula": "targetSlabLength = floor(무게 × 1e6 / (폭 × 두께 × 비중))",
        "computation": f"무게 {_kg(slab_wgt)} 를 목표폭/두께/비중으로 역산해 1mm 단위 내림",
        "result": _mm(length), "phase": "phase_2c",
    })
    trace.append({
        "step_no": 20, "title": "SLAB_RESULT insert",
        "formula": "INSERT INTO SLAB_RESULT (slabNo, orderNo, slabWidth=target, slabLength=target, slabWgt, splitCount)",
        "computation": f"slabWgt={_kg(slab_wgt)} × {split} 매 = 총 {_kg(slab_wgt * split)}",
        "result": f"Slab {split} 장 — 각 {_kg(slab_wgt)}", "phase": "save",
    })
    return trace


@router.post("/weight_optimize/sweep", response_model=WeightOptimizationResponse)
async def weight_optimize_sweep(req: WeightOptimizationRequest) -> WeightOptimizationResponse:
    """변수 sweep → 각 조합의 예상 slab 단중 계산 + 최적 추천.

    실제 Java 8080 호출하지 않고 ontology propagation 규칙으로 빠르게 추정.
    핵심 공식: split_wgt ≈ min(ORDER_WGT_HIGH, HR_MAX_WGT, CUSTOMER.wgt_high) — 즉 상한
    근처가 가장 큰 단중. 단 split_count 는 dpq / split_wgt 가 정수가 되는 식으로 결정.
    """
    from backend.section3.agents.simulation import evidence as ev
    bundle = ev.EvidenceBundle()

    base = req.base_order
    # 기본 제약 (없으면 default)
    hr_max = float(base.get("_HR_MAX_WGT", 25000))
    hr_min = float(base.get("_HR_MIN_WGT", 8000))
    bundle.add("constraints", ev.business_rule(
        "rule.scm.slab.wgt_range",
        f"hr_min={hr_min} ≤ split_wgt ≤ hr_max={hr_max} (HR_MAX/MIN_WGT)",
        severity="hard",
    ))

    # sweep variable 별 grid
    def _grid(low: float, high: float, n: int) -> list[float]:
        if n <= 1:
            return [(low + high) / 2]
        step = (high - low) / (n - 1)
        return [round(low + i * step, 1) for i in range(n)]

    var_ranges: dict[str, tuple[float, float]] = {}
    for v in req.sweep_variables:
        base_v = float(base.get(v, 0) or 0)
        if v == "ORDER_WGT_HIGH":
            var_ranges[v] = (max(hr_min + 1000, base_v * 0.7), min(hr_max, base_v * 1.3 if base_v else hr_max))
        elif v == "ORDER_WGT_LOW":
            var_ranges[v] = (max(hr_min, base_v * 0.7 if base_v else hr_min), base_v * 1.3 if base_v else hr_max / 2)
        elif v == "DESIGN_PEND_QTY":
            var_ranges[v] = (max(hr_min, base_v * 0.5 if base_v else hr_min * 2), base_v * 2 if base_v else hr_max * 3)
        else:
            var_ranges[v] = (base_v * 0.7 if base_v else 1, base_v * 1.3 if base_v else 100)
        bundle.add(f"sweep[{v}]", ev.inference(
            f"sweep 범위 {var_ranges[v][0]:.0f}~{var_ranges[v][1]:.0f} (base={base_v}, hr_max={hr_max}, hr_min={hr_min} 기반)",
            confidence=0.7,
        ))

    # grid 생성 (변수당 grid_size 개, 조합 cartesian)
    grids = {v: _grid(rng[0], rng[1], req.grid_size) for v, rng in var_ranges.items()}
    grid: list[dict[str, Any]] = []
    import itertools
    var_names = list(grids.keys())
    for combo in itertools.product(*[grids[v] for v in var_names]):
        cell_vars = dict(zip(var_names, combo))
        ow_high = cell_vars.get("ORDER_WGT_HIGH", base.get("ORDER_WGT_HIGH", hr_max))
        ow_low = cell_vars.get("ORDER_WGT_LOW", base.get("ORDER_WGT_LOW", hr_min))
        dpq = cell_vars.get("DESIGN_PEND_QTY", base.get("DESIGN_PEND_QTY", hr_max))
        # 각 slab 의 wgt 상한 = min(ow_high, hr_max, customer)
        wgt_cap = min(ow_high, hr_max)
        wgt_floor = max(ow_low, hr_min)
        # split_count = ceil(dpq / wgt_cap) — 단 slab 수가 적으면 1 slab 당 wgt 커짐
        violations: list[str] = []
        if wgt_floor > wgt_cap:
            violations.append(f"ORDER_WGT_LOW({wgt_floor}) > 상한({wgt_cap}) — 설계 불가")
            cell = {
                "vars": cell_vars,
                "projected_split_count": 0,
                "projected_slab_wgt": 0,
                "feasible": False,
                "violations": violations,
            }
            grid.append(cell)
            continue
        import math
        split_count = max(1, math.ceil(dpq / wgt_cap))
        slab_wgt = dpq / split_count
        # 만약 slab_wgt < wgt_floor 면 split 수 줄여서 다시 시도
        while slab_wgt < wgt_floor and split_count > 1:
            split_count -= 1
            slab_wgt = dpq / split_count
        if slab_wgt < wgt_floor:
            violations.append(f"min split_wgt({slab_wgt:.0f}) < ORDER_WGT_LOW({wgt_floor:.0f})")
        if slab_wgt > wgt_cap:
            violations.append(f"split_wgt({slab_wgt:.0f}) > 상한({wgt_cap:.0f})")
        cell = {
            "vars": cell_vars,
            "projected_split_count": split_count,
            "projected_slab_wgt": round(slab_wgt, 1),
            "feasible": len(violations) == 0,
            "violations": violations,
        }
        grid.append(cell)

    feasible = [c for c in grid if c["feasible"]]
    best = max(feasible, key=lambda c: c["projected_slab_wgt"], default=None)
    bundle.add("best_cell", ev.propagation(
        "slab.wgt = dpq / split_count, split_count = ceil(dpq / min(ORDER_WGT_HIGH, HR_MAX_WGT))",
        ["ORDER_WGT_HIGH", "DESIGN_PEND_QTY", "HR_MAX_WGT"],
        confidence=0.8,
    ))

    if best:
        summary = (
            f"최적 조합 — slab 단중 최대 {best['projected_slab_wgt']:,.0f} kg "
            f"({best['projected_split_count']} split)\n"
            f"권장 변수: " + ", ".join(f"{k}={int(v):,}" for k, v in best["vars"].items()) + "\n"
            f"전체 {len(grid)} 조합 중 {len(feasible)} 건이 제약 만족"
        )
    else:
        summary = (
            f"feasible 조합 없음 — 제약 (HR_MAX_WGT={hr_max}, HR_MIN_WGT={hr_min}) "
            f"안에서 모든 sweep 점이 위반. 제약을 완화하거나 sweep 범위 조정 필요"
        )

    # 2026-05-25 — best 결과 21-step 산식 trace
    calc_trace = _build_calculation_trace(base, best, hr_max, hr_min)

    return WeightOptimizationResponse(
        base_order=base, sweep_variables=req.sweep_variables,
        grid=grid, best=best, summary=summary,
        evidence=bundle.to_dict(),
        calculation_trace=calc_trace,
        var_ranges={k: list(v) for k, v in var_ranges.items()},
    )


class VirtualOrderSynthesizeRequest(BaseModel):
    """사용자가 선택한 기준 데이터 row(들) 기반으로 ontology 추론으로 가상 주문 합성.

    실제 java/seed 데이터를 보지 않고 ontology business_terms + effective_parts +
    business_rules + valid_ranges 만으로 합성. 결과는 에이전트의 dry-run 입력.
    """
    base_rows: dict[str, dict[str, Any]]  # 예: {"CAST_SPEC": {...}, "HR_SPEC": {...}}
    count: int = 3
    target_term_fqn: str = "term.scm.order.order"
    repo_id: str = "slab-design-real-v2"


class VirtualOrderSynthesizeResponse(BaseModel):
    orders: list[dict[str, Any]]
    synthesis_log: list[str]
    evidence: dict[str, Any]


@router.post("/virtual_order/synthesize", response_model=VirtualOrderSynthesizeResponse)
async def virtual_order_synthesize(req: VirtualOrderSynthesizeRequest) -> VirtualOrderSynthesizeResponse:
    """ontology 만으로 가상 주문 합성 — 사실 java 안 봐도 됨.

    1) ontology 의 `target_term_fqn` (default: term.scm.order.order) 의 effective_parts
       에서 atomic Term 들의 list 획득.
    2) 각 atomic Term 의 value_type / unit / range / enum_values 로 필드 의미 결정.
    3) 사용자 base_rows (CAST_SPEC 등) 가 정한 폭·두께·길이 범위 안에서 가상 값 선택.
    4) business_rules.statement (terms_ref 매칭) 로 cross-field 제약 검증.
    """
    import random
    from sqlalchemy import select
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow, BusinessRuleRow
    from backend.section3.agents.simulation import evidence as ev

    bundle = ev.EvidenceBundle()
    log: list[str] = []

    # ontology Term 로딩
    target_term: dict[str, Any] | None = None
    related_terms: dict[str, dict[str, Any]] = {}
    rules: list[dict[str, Any]] = []
    try:
        with session_scope() as s:
            target = s.execute(
                select(BusinessTermRow).where(
                    BusinessTermRow.repo_id == req.repo_id,
                    BusinessTermRow.fqn == req.target_term_fqn,
                )
            ).scalar_one_or_none()
            if target:
                target_term = {
                    "fqn": target.fqn, "label": target.label,
                    "description": target.description,
                    "kind": target.kind,
                }
                bundle.add("target_term", ev.ontology_term(target.fqn, target.label))
                log.append(f"target Term 로딩: {target.label} ({target.fqn})")

            # order 관련 atomic term 들 — order 키워드 기반
            rows = s.execute(
                select(BusinessTermRow).where(BusinessTermRow.repo_id == req.repo_id)
            ).scalars().all()
            for r in rows:
                if r.kind == "atomic" and ("order" in (r.fqn or "").lower() or
                                            "product" in (r.fqn or "").lower() or
                                            "grade" in (r.fqn or "").lower() or
                                            "wgt" in (r.fqn or "").lower()):
                    related_terms[r.fqn] = {
                        "fqn": r.fqn, "label": r.label, "description": r.description,
                        "value_type": r.value_type, "unit": r.unit,
                        "range": r.range, "enum_values": r.enum_values,
                    }

            rule_rows = s.execute(
                select(BusinessRuleRow).where(BusinessRuleRow.repo_id == req.repo_id)
            ).scalars().all()
            import json as _json
            for rr in rule_rows:
                try:
                    terms_ref = _json.loads(rr.terms_ref_json or "[]")
                except Exception:
                    terms_ref = []
                rules.append({
                    "fqn": rr.fqn, "statement": rr.statement,
                    "severity": rr.severity, "terms_ref": terms_ref,
                })
    except Exception as e:  # noqa: BLE001
        logger.warning("virtual order ontology 로딩 실패: %s", e)
        log.append(f"⚠ ontology 로딩 실패: {e}")

    log.append(f"ontology 에서 order 관련 atomic term {len(related_terms)} 건 발굴")
    log.append(f"business rules {len(rules)} 건 로딩")

    # base_rows 분석 — 사용자가 선택한 기준 (예: CAST_SPEC)
    cast = req.base_rows.get("CAST_SPEC") or {}
    hr = req.base_rows.get("HR_SPEC") or {}
    edging = req.base_rows.get("EDGING_GROUP") or {}
    cust = req.base_rows.get("CUSTOMER_STD") or {}
    hr_max = req.base_rows.get("HR_MAX_WGT") or {}
    hr_min = req.base_rows.get("HR_MIN_WGT") or {}

    log.append(f"사용자 base_rows: {list(req.base_rows.keys())}")
    for k, v in req.base_rows.items():
        bundle.add(f"base_rows.{k}", ev.seed_data(k, "row", v.get(list(v.keys())[0]) if v else None))

    # 가능한 폭·길이·단중 범위 — base rows 교집합
    def _f(v: Any) -> float | None:
        try: return float(v) if v is not None else None
        except Exception: return None

    width_low = max(filter(None, [_f(cast.get("WIDTH_LOW")), _f(hr.get("WIDTH_LOW")), _f(edging.get("HR_TGT_WIDTH_LOW"))]), default=900.0)
    width_high = min(filter(None, [_f(cast.get("WIDTH_HIGH")), _f(hr.get("WIDTH_HIGH")), _f(edging.get("HR_TGT_WIDTH_HIGH"))]), default=2200.0)
    length_low = max(filter(None, [_f(cast.get("LENGTH_LOW")), _f(hr.get("LENGTH_LOW"))]), default=4000.0)
    length_high = min(filter(None, [_f(cast.get("LENGTH_HIGH")), _f(hr.get("LENGTH_HIGH"))]), default=12000.0)
    thickness = _f(cast.get("SLAB_THICKNESS")) or 230.0
    wgt_low = max(filter(None, [_f(hr_min.get("MIN_WGT")), _f(cust.get("WGT_LOW"))]), default=8000.0)
    wgt_high = min(filter(None, [_f(hr_max.get("MAX_WGT")), _f(cust.get("WGT_HIGH"))]), default=25000.0)

    log.append(f"교집합 폭 [{width_low:.0f}, {width_high:.0f}], 길이 [{length_low:.0f}, {length_high:.0f}], 두께 {thickness:.0f}, 단중 [{wgt_low:.0f}, {wgt_high:.0f}]")
    bundle.add("range_intersection", ev.propagation(
        "min/max 교집합",
        ["CAST_SPEC", "HR_SPEC", "EDGING_GROUP", "HR_MAX_WGT", "HR_MIN_WGT", "CUSTOMER_STD"],
        confidence=0.85,
    ))

    # 가상 주문 합성 — 다양 케이스 (경계 / 정상 / 에러) 로 분산
    # 2026-05-25 사용자 요구: 5건이 모두 정상범위 random 이 아니라,
    #   하한경계 / 정상중앙 / 상한경계 / 범위초과 (DG104/107) / 매칭실패 (DG103)
    #   같은 케이스 다양성을 갖도록 구성. count 만큼 round-robin 으로 채택.
    orders: list[dict[str, Any]] = []
    product_cd = cast.get("PRODUCT_CD") or "COIL"
    grade_cd = cust.get("GRADE_CD") or "SS400"

    width_mid  = (width_low + width_high) / 2
    length_mid = (length_low + length_high) / 2
    wgt_mid    = (wgt_low + wgt_high) / 2

    def _round(v: float, unit: int) -> int:
        return int(round(v / unit) * unit)

    # 케이스 카탈로그 — 각 항목은 (case_kind, case_label, expected_outcome, builder)
    # builder 는 (ow, ol, ow_low, ow_high, dpq, override_dict) 반환
    def _case_boundary_low() -> tuple:
        ow = _round(width_low,  50)
        ol = _round(length_low, 100)
        ow_lo = _round(wgt_low,             500)
        ow_hi = _round(wgt_low + 1000,      500)
        dpq   = _round(ow_hi * 1.2,         500)
        return (ow, ol, ow_lo, ow_hi, dpq, {})

    def _case_typical_mid() -> tuple:
        ow = _round(width_mid,  50)
        ol = _round(length_mid, 100)
        ow_lo = _round(wgt_low + (wgt_mid - wgt_low) * 0.4, 500)
        ow_hi = _round(wgt_mid + (wgt_high - wgt_mid) * 0.4, 500)
        dpq   = _round(ow_hi * 1.8, 500)
        return (ow, ol, ow_lo, ow_hi, dpq, {})

    def _case_boundary_high() -> tuple:
        ow = _round(width_high,  50)
        ol = _round(length_high, 100)
        ow_lo = _round(wgt_high - 2000, 500)
        ow_hi = _round(wgt_high,        500)
        dpq   = _round(ow_hi * 2.5,     500)
        return (ow, ol, ow_lo, ow_hi, dpq, {})

    def _case_error_out_of_range() -> tuple:
        # 폭 widthHigh+200 — DG104 invalid_width_range / Step 2 교집합 실패 유발
        ow = _round(width_high + 200, 50)
        ol = _round(length_mid,       100)
        ow_lo = _round(wgt_low,       500)
        ow_hi = _round(wgt_high + 5000, 500)  # 단중도 maxWgt 초과 — DG107
        dpq   = _round(ow_hi * 2.0,   500)
        return (ow, ol, ow_lo, ow_hi, dpq,
                {"_error_hint": "ORDER_WIDTH 가 설비 widthHigh 초과 + ORDER_WGT_HIGH > HR_MAX_WGT — DG104/DG107 validator 실패 예상"})

    def _case_error_no_match() -> tuple:
        # 강종 / 고객사를 의도적으로 unknown 으로 — EDGING_GROUP 매칭 실패 → DG103
        ow = _round(width_mid,  50)
        ol = _round(length_mid, 100)
        ow_lo = _round(wgt_mid - 1500, 500)
        ow_hi = _round(wgt_mid + 1500, 500)
        dpq   = _round(ow_hi * 1.5, 500)
        return (ow, ol, ow_lo, ow_hi, dpq,
                {"GRADE_CD": "SS9999", "CUSTOMER_CD": "CUST-UNKNOWN",
                 "_error_hint": "GRADE/CUSTOMER 매칭 row 없음 — EDGING_GROUP 룩업 실패 → DG103 throw 예상"})

    CASE_CATALOG = [
        ("boundary_low",      "🔽 하한 경계",   "Step 2~7 모두 최소값 — 작은 slab 1장 가능성 ↑", _case_boundary_low),
        ("typical_mid",       "✅ 정상 중앙",   "가장 흔한 케이스 — 무난한 결과 기대",         _case_typical_mid),
        ("boundary_high",     "🔼 상한 경계",   "Step 2~7 모두 최대값 — 큰 slab + 분할수 ↑",    _case_boundary_high),
        ("error_out_range",   "⚠️ 범위 초과 (에러)", "DG104/DG107 검증 실패 예상 — Phase 1 reject", _case_error_out_of_range),
        ("error_no_match",    "⚠️ 매칭 실패 (에러)", "EDGING_GROUP/CUSTOMER 매칭 0건 — DG103 throw 예상", _case_error_no_match),
    ]

    n = max(1, min(req.count, 10))
    for i in range(n):
        case_kind, case_label, outcome, builder = CASE_CATALOG[i % len(CASE_CATALOG)]
        ow, ol, ow_lo, ow_hi, dpq, override = builder()
        order = {
            "ORDER_NO": f"VIRT{20260525:08d}{i:03d}",
            "CMP_CD": cast.get("CMP_CD", "K"),
            "ORG_CD": cast.get("ORG_CD", "1"),
            "PRODUCT_CD": product_cd,
            "GRADE_CD": grade_cd,
            "ORDER_WIDTH": ow,
            "ORDER_LENGTH": ol,
            "ORDER_WGT_LOW": ow_lo,
            "ORDER_WGT_HIGH": ow_hi,
            "DESIGN_PEND_QTY": dpq,
            "CUSTOMER_CD": cust.get("CUSTOMER_CD") or edging.get("CUSTOMER_CD") or "CUST001",
            "_virtual": True,
            "_case_kind": case_kind,
            "_case_label": case_label,
            "_expected_outcome": outcome,
            "_synthesis_basis": "case-diverse: boundary low/mid/high + DG-error scenarios",
        }
        order.update(override)
        orders.append(order)
        bundle.add(f"orders[{i}]", ev.inference(
            f"가상 주문 #{i+1} [{case_label}] — {outcome}",
            confidence=0.9 if case_kind.startswith("error") else 0.85,
        ))

    log.append(
        f"가상 주문 {len(orders)} 건 합성 — "
        f"케이스 분포: {[o.get('_case_kind') for o in orders]}"
    )

    return VirtualOrderSynthesizeResponse(
        orders=orders, synthesis_log=log,
        evidence=bundle.to_dict(),
    )


class OntologyCallRecord(BaseModel):
    """ontology API 한 번 호출의 trace — URL · 응답 size · 소요 ms · 200 byte 미리보기."""
    method: str
    url: str
    elapsed_ms: int
    status: str               # "ok" | "error" | "empty"
    item_count: int | None = None
    error: str | None = None


class OntologyInspectRequest(BaseModel):
    term_fqn: str
    repo_id: str = "slab-design-real-v2"


class OntologyInspectResponse(BaseModel):
    term_fqn: str
    term: dict[str, Any] | None = None
    effective_parts: list[dict[str, Any]] = Field(default_factory=list)
    related_actions: list[dict[str, Any]] = Field(default_factory=list)
    business_rules: list[dict[str, Any]] = Field(default_factory=list)
    anchor_bindings: list[dict[str, Any]] = Field(default_factory=list)
    calls: list[OntologyCallRecord] = Field(default_factory=list)
    total_ms: int = 0


@router.post("/ontology_inspect", response_model=OntologyInspectResponse)
async def ontology_inspect(req: OntologyInspectRequest) -> OntologyInspectResponse:
    """현대화 modeling 시스템에 실제로 부르는 ontology API fan-out + 실시간 trace.

    detected term 1건의 fqn 으로 5종 endpoint 병렬 호출, 응답 + 호출 메타데이터를 함께 반환.
    UI 의 우측 패널이 이걸 250ms 디바운스로 호출해 raw ontology 응답을 surface.
    """
    import time
    from backend.section3.clients.modeling_client import get_modeling_client

    client = get_modeling_client()
    calls: list[OntologyCallRecord] = []
    overall_t0 = time.perf_counter()

    async def _trace(method: str, path: str, awaitable):
        t0 = time.perf_counter()
        try:
            result = await awaitable
            elapsed = int((time.perf_counter() - t0) * 1000)
            item_count: int | None = None
            status = "ok"
            if isinstance(result, list):
                item_count = len(result)
                if item_count == 0:
                    status = "empty"
            elif result is None:
                status = "empty"
            calls.append(OntologyCallRecord(
                method=method, url=path, elapsed_ms=elapsed,
                status=status, item_count=item_count,
            ))
            return result
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.perf_counter() - t0) * 1000)
            calls.append(OntologyCallRecord(
                method=method, url=path, elapsed_ms=elapsed,
                status="error", error=str(exc)[:200],
            ))
            return None

    term = await _trace(
        "GET", f"/api/ontology/terms/{req.term_fqn}",
        client.get_term(req.term_fqn),
    )
    parts = await _trace(
        "GET", f"/api/ontology/terms/{req.term_fqn}/effective-parts",
        client.get_term_effective_parts(req.term_fqn, repo_id=req.repo_id),
    )
    # related actions — list_actions 후 client side 에서 term_fqn 으로 필터
    all_actions = await _trace(
        "GET", f"/api/ontology/actions?repo_id={req.repo_id}",
        client.list_actions(repo_id=req.repo_id, limit=2000),
    ) or []
    # Action 매칭: declared_on_term, params[].object_ref_term, output.object_ref_term
    related_actions: list[dict[str, Any]] = []
    related_action_fqns: set[str] = set()
    if all_actions:
        for a in all_actions:
            declared = a.get("declared_on_term")
            params = a.get("params") or []
            param_terms = [p.get("object_ref_term") for p in params if isinstance(p, dict)]
            output = a.get("output") or {}
            output_term = output.get("object_ref_term") if isinstance(output, dict) else None
            if req.term_fqn == declared or req.term_fqn in param_terms or req.term_fqn == output_term:
                kind = "declared_on" if req.term_fqn == declared else (
                    "param" if req.term_fqn in param_terms else "output")
                related_actions.append({
                    "fqn": a.get("fqn"), "label": a.get("label"),
                    "kind": kind,
                    "description": (a.get("description") or "")[:240],
                })
                related_action_fqns.add(a.get("fqn"))

    all_rules = await _trace(
        "GET", f"/api/ontology/business-rules?repo_id={req.repo_id}",
        client.list_business_rules(repo_id=req.repo_id),
    ) or []
    business_rules: list[dict[str, Any]] = []
    for r in all_rules:
        terms_ref = r.get("terms_ref") or []
        if req.term_fqn in terms_ref:
            business_rules.append({
                "fqn": r.get("fqn"),
                "statement": (r.get("statement") or "")[:240],
                "severity": r.get("severity"),
                "enforced_by": (r.get("enforced_by") or [])[:5],
            })

    all_anchors = await _trace(
        "GET", f"/api/ontology/anchor-bindings?repo_id={req.repo_id}",
        client.list_anchor_bindings(repo_id=req.repo_id),
    ) or []
    anchor_bindings: list[dict[str, Any]] = []
    # term 명을 anchor 의 target_slot 안에서 부분 매칭 (예: term.scm.shared.confirmed_plant_cd
    # → "atomic.confirmed_plant_cd.invalid_check"). action 경로로도 잡힘.
    term_short = req.term_fqn.split(".")[-1] if "." in req.term_fqn else req.term_fqn
    for ab in all_anchors:
        target_action = ab.get("target_action_fqn") or ""
        target_slot = ab.get("target_slot") or ""
        if target_action in related_action_fqns or term_short in target_slot:
            anchor_bindings.append({
                "anchor_id": ab.get("id"),
                "method_fqn": ab.get("code_method_fqn"),
                "target_action_fqn": target_action,
                "target_slot": target_slot,
                "anchor_locator": ab.get("anchor_locator"),
                "line": ab.get("line"),
                "confidence": ab.get("confidence"),
            })

    total_ms = int((time.perf_counter() - overall_t0) * 1000)
    return OntologyInspectResponse(
        term_fqn=req.term_fqn, term=term, effective_parts=parts or [],
        related_actions=related_actions[:30], business_rules=business_rules[:30],
        anchor_bindings=anchor_bindings[:30], calls=calls, total_ms=total_ms,
    )


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


@router.post("/hypothesis/stream")
async def hypothesis_stream(req: HypothesisRequest):
    """SSE — hypothesis 4-step 을 순차로 전송.
    each event: { stage: int, label: str, data: dict }
    """
    import json as _j
    from backend.section3.agents.simulation import hypothesis_workflow as _hw

    async def gen():
        # Stage 1: existing data
        existing_prod = _hw._filter_rows("SD_PRODUCTIVITY_STD", GRADE_CD=req.base_grade)
        existing_order_rows: dict[str, dict] = {}
        for tbl in ("ORDER_OS", "ORDER_OM", "ORDER_QD", "ORDER_CHEMICAL"):
            rows = _hw._filter_rows(tbl, ORDER_NO=req.base_order_no)
            if rows:
                existing_order_rows[tbl] = rows[0]
        yield "data: " + _j.dumps({
            "stage": 1, "label": "기존 데이터 분석",
            "data": {
                "existing_productivity_rows": existing_prod,
                "existing_order_rows": existing_order_rows,
            },
        }, ensure_ascii=False) + "\n\n"

        # Stage 2: virtual grade synthesis
        virtual_prod = [
            _hw._synthesize_grade_row(r, req.new_grade, req.productivity_multiplier)
            for r in existing_prod
        ]
        yield "data: " + _j.dumps({
            "stage": 2, "label": "가상 강종 합성",
            "data": {"virtual_productivity_rows": virtual_prod},
        }, ensure_ascii=False) + "\n\n"

        # Stage 3: virtual order
        new_order_no = f"V{req.base_order_no[1:]}"
        virtual_order_rows: dict[str, dict] = {}
        for tbl, base in existing_order_rows.items():
            virtual_order_rows[tbl] = _hw._synthesize_order_row(
                base, new_order_no,
                req.new_grade if tbl == "ORDER_QD" else None,
            )
        yield "data: " + _j.dumps({
            "stage": 3, "label": "가상 주문 합성",
            "data": {"virtual_order_rows": virtual_order_rows, "new_order_no": new_order_no},
        }, ensure_ascii=False) + "\n\n"

        # Stage 4: baseline + projection
        try:
            from backend.section3.agents.simulation.slab_design_runner import run_full_design
            baseline = await run_full_design(order_no=req.base_order_no)
            slabs = baseline.get("slab_results") or []
            trace = baseline.get("trace") or []
            if slabs:
                base_mult = sum(float(r.get("PRODUCTIVITY") or 0) for r in existing_prod) / max(len(existing_prod), 1)
                new_mult = base_mult * req.productivity_multiplier
                projected, diff = _hw._project_slab(slabs[0], base_mult, new_mult)
                yield "data: " + _j.dumps({
                    "stage": 4, "label": "Slab 결과 비교 (추론)",
                    "data": {
                        "baseline_slab": slabs[0],
                        "baseline_trace": trace[:5],
                        "projected_slab": projected,
                        "diff_summary": [d.model_dump() for d in diff] if hasattr(diff[0] if diff else None, "model_dump") else diff,
                    },
                }, ensure_ascii=False) + "\n\n"
            else:
                yield "data: " + _j.dumps({
                    "stage": 4, "label": "Slab 결과 비교",
                    "data": {"error": "baseline 결과 없음"},
                }, ensure_ascii=False) + "\n\n"
        except Exception as e:  # noqa: BLE001
            yield "data: " + _j.dumps({
                "stage": 4, "label": "Slab 결과 비교", "data": {"error": str(e)},
            }, ensure_ascii=False) + "\n\n"

        yield "data: " + _j.dumps({"stage": "done", "label": "완료"}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


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


class NewStandardRequest(BaseModel):
    new_product_cd: str | None = None
    new_grade_cd: str | None = None
    new_custom_attrs: dict | None = None
    base_order_no: str = "ORD20260510001"


class NewStandardResponse(BaseModel):
    new_product_cd: str | None = None
    new_grade_cd: str | None = None
    new_custom_attrs: dict = Field(default_factory=dict)
    closest_existing_order: dict | None = None
    use_virtual: bool = False
    virtual_order: dict = Field(default_factory=dict)
    baseline_order_no: str
    baseline_slab: dict | None = None
    projected_slab: dict | None = None
    diff: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    transpiled_methods: list[dict] = Field(default_factory=list)
    code_changes_needed: list[dict] = Field(default_factory=list)


@router.post("/new_standard/run", response_model=NewStandardResponse)
async def new_standard_run(req: NewStandardRequest) -> NewStandardResponse:
    """신규 기준 (품종 / 강종 / 사용자 정의) 추가 시나리오:
    - 가장 가까운 기존 주문 찾기 → baseline
    - 매칭 없으면 가상 주문 합성
    - 신규 기준 적용 시 slab 결과 추론 + Java→Python 변환
    - 코드 수정 필요 여부 안내
    """
    r = await run_new_standard_workflow(
        new_product_cd=req.new_product_cd,
        new_grade_cd=req.new_grade_cd,
        new_custom_attrs=req.new_custom_attrs,
        base_order_no=req.base_order_no,
    )
    return NewStandardResponse(**r)


class ImpactCompareRequest(BaseModel):
    table: str
    column: str
    before: str | None = None
    after: str | None = None
    order_no: str
    cmp_cd: str = "K"
    org_cd: str = "1"
    affected_method_fqns: list[str] | None = None


class ImpactCompareResponse(BaseModel):
    ok: bool
    order_no: str
    target: dict
    baseline_slab: dict | None = None
    projected_slab: dict | None = None
    diff: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    transpiled_methods: list[dict] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None


@router.post("/impact/compare_slab", response_model=ImpactCompareResponse)
async def impact_compare_slab_endpoint(req: ImpactCompareRequest) -> ImpactCompareResponse:
    """선택 주문 + 변경 대상 → baseline vs projected slab 비교 + Java→Python."""
    r = await compare_impact_slab(
        table=req.table, column=req.column, before=req.before, after=req.after,
        order_no=req.order_no, cmp_cd=req.cmp_cd, org_cd=req.org_cd,
        affected_method_fqns=req.affected_method_fqns,
    )
    return ImpactCompareResponse(**r)


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


class ExcelExportField(BaseModel):
    """Excel 추출 1 컬럼 — backend 가 ontology 로 한국어 라벨/영어 키를 보완."""
    key: str                       # 원본 응답의 field name (예: slabThickness)
    label_ko: str | None = None    # ontology business_term.label (없으면 backend lookup)
    sample: Any | None = None      # 미리보기 (frontend 가 보낸 값)


class ExcelExportRequest(BaseModel):
    session_id: str
    fields: list[ExcelExportField]
    rows: list[dict[str, Any]]      # frontend 가 결과 카드에서 추출한 row data
    sheet_name: str = "결과"
    title: str | None = None        # 시트 상단 큰 제목


@router.get("/export/preview/{session_id}")
async def export_preview(session_id: str) -> dict[str, Any]:
    """세션의 마지막 executed payload 에서 Excel 추출 후보 컬럼·row 를 자동 추출.

    frontend 다이얼로그가 이 응답을 받아 multi-select 표시 → 사용자가 항목 고른 후
    /export/xlsx 호출. ontology business_terms 로 한국어 라벨 매핑.
    """
    rep = p.replay_session(session_id)
    if rep is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    if not rep.decisions:
        return {"intent": None, "rows": [], "columns": []}
    intent = rep.session.intent or ""
    last = rep.decisions[-1].payload or {}
    rows: list[dict[str, Any]] = []
    # intent / kind 별 추출 휴리스틱
    kind = last.get("kind", "")
    if intent == "simulate" or kind == "executed_full_design":
        for slab in (last.get("slab_results") or []):
            if isinstance(slab, dict):
                rows.append(slab)
    if kind == "executed_compare":
        baseline = last.get("baseline_slab") or {}
        projected = last.get("projected_slab") or {}
        if baseline:
            rows.append({"_label": "변경전 (baseline)", **baseline})
        if projected:
            rows.append({"_label": "변경후 (projected)", **projected})
    if kind == "executed_hypothesis_workflow":
        for s in (last.get("simulation_results") or []):
            if isinstance(s, dict):
                rows.append(s)
    # 2026-05-25 — dynamic_blocks 의 table type block 도 rows 후보로 추가
    # (모든 의도 — 가상 주문 + 21-step 결과 + 비교 등 동적 생성된 표 데이터)
    db = last.get("_dynamic_blocks") or []
    for b in db if isinstance(db, list) else []:
        if not isinstance(b, dict): continue
        if b.get("type") != "table": continue
        bd = b.get("data") or {}
        block_rows = bd.get("rows") or []
        block_cols = bd.get("columns") or []
        # column meta — key 로 raw 데이터 그대로
        for r in block_rows:
            if isinstance(r, dict):
                # _block_title 메타 추가 (어느 표에서 왔는지 사용자가 알 수 있도록)
                row_out = {"_block": b.get("title", "")[:40], **{k: v for k, v in r.items()}}
                rows.append(row_out)
    if not rows:
        # 일반 dict 인 경우 (impact / locate / explain) — top-level scalars 한 줄
        scalars = {k: v for k, v in last.items()
                   if not k.startswith("_") and isinstance(v, (str, int, float, bool))}
        if scalars:
            rows.append(scalars)

    # 컬럼 — 모든 row 의 key 합집합. 단 _meta / list / dict 컬럼은 제외.
    col_keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k, v in r.items():
            if k in seen or k.startswith("_"):
                continue
            if isinstance(v, (list, dict)):
                continue
            seen.add(k); col_keys.append(k)

    # ontology business_terms 에서 한국어 라벨 lookup — camelCase / snake_case 모두 fallback
    label_map: dict[str, str] = {}
    try:
        from sqlalchemy import select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.domain_layer.orm import BusinessTermRow
        import json as _json
        with session_scope() as s:
            terms = s.execute(
                select(BusinessTermRow).where(BusinessTermRow.repo_id == rep.session.repo_id)
            ).scalars().all()
            def _norm(s: str) -> str:
                return s.lower().replace("_", "").replace(" ", "").replace("-", "")
            for k in col_keys:
                k_norm = _norm(k)
                for t in terms:
                    aliases = []
                    try:
                        aliases = _json.loads(t.aliases_json or "[]")
                    except Exception:
                        pass
                    cand = [t.label or ""] + list(aliases)
                    if any(_norm(c) == k_norm for c in cand if c):
                        label_map[k] = t.label or k
                        break
    except Exception as e:  # noqa: BLE001
        logger.warning("excel preview label lookup 실패: %s", e)

    columns = [
        {
            "key": k,
            "label_ko": label_map.get(k),
            "sample": rows[0].get(k) if rows else None,
        }
        for k in col_keys
    ]
    return {
        "intent": intent,
        "kind": kind,
        "rows": rows,
        "columns": columns,
        "row_count": len(rows),
    }


@router.post("/export/xlsx")
async def export_xlsx(req: ExcelExportRequest):
    """현업 자율화 — 선택한 컬럼만 xlsx 로 추출. 컬럼명 = 한국어\\n영어 두 줄."""
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    import io

    rep = p.replay_session(req.session_id)
    intent = rep.session.intent if rep else None
    user_query = rep.session.user_query if rep else ""

    wb = Workbook()
    ws = wb.active
    ws.title = req.sheet_name[:31]

    thin = Side(border_style="thin", color="cccccc")
    border = Border(top=thin, bottom=thin, left=thin, right=thin)

    # 제목 (사용자 query) 1행
    title = req.title or (f"{user_query or '시뮬레이션 결과'} · intent={intent or '-'}")
    ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=12, color="065f46")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(len(req.fields), 1))
    ws.cell(row=1, column=1).alignment = Alignment(horizontal="left", vertical="center")

    # 컬럼 헤더 2행 — 한국어 (윗줄) + 영어 키 (아랫줄)
    header_fill = PatternFill(start_color="065f46", end_color="065f46", fill_type="solid")
    for col_idx, f in enumerate(req.fields, start=1):
        cell = ws.cell(row=2, column=col_idx)
        ko = f.label_ko or f.key
        cell.value = f"{ko}\n{f.key}"
        cell.font = Font(bold=True, color="ffffff", size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.fill = header_fill
        cell.border = border
        ws.column_dimensions[cell.column_letter].width = max(14, len(ko) + 4)
    ws.row_dimensions[2].height = 36

    # data rows
    for r_idx, row in enumerate(req.rows, start=3):
        for c_idx, f in enumerate(req.fields, start=1):
            v = row.get(f.key)
            if isinstance(v, (list, dict)):
                v = str(v)[:300]
            cell = ws.cell(row=r_idx, column=c_idx, value=v)
            cell.alignment = Alignment(vertical="center", wrap_text=False)
            cell.border = border
            if isinstance(v, (int, float)):
                cell.number_format = "#,##0.##"

    ws.freeze_panes = "A3"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    from datetime import datetime as _dt
    fname = f"sim_{intent or 'result'}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/walkthrough/steps")
async def walkthrough_steps(query: str = "", phase: str = ""):
    """21-step 카탈로그 — 사용자 질문에 관련된 step 들 + phase 별 step list 반환.

    카탈로그는 backend step_catalog.py 에 정적으로 정의 (walkthrough.md 정독 후 한 번 채움).
    런타임엔 ontology + 기준 DB 만 사용 — walkthrough.md 파일이 없어도 정상 동작.
    """
    from backend.section3.agents.simulation.step_catalog import (
        STEP_CATALOG, PHASE_LABELS, steps_matching_query, steps_in_phase, step_to_dict,
    )
    if query:
        matched = steps_matching_query(query, max_n=8)
        return {
            "query": query,
            "matched_steps": [step_to_dict(s) for s in matched],
            "match_count": len(matched),
            "phases": PHASE_LABELS,
        }
    if phase:
        steps = steps_in_phase(phase)  # type: ignore[arg-type]
        return {
            "phase": phase,
            "phase_label": PHASE_LABELS.get(phase, phase),
            "steps": [step_to_dict(s) for s in steps],
        }
    return {
        "phases": PHASE_LABELS,
        "all_steps": [step_to_dict(s) for s in STEP_CATALOG],
        "total": len(STEP_CATALOG),
    }


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
