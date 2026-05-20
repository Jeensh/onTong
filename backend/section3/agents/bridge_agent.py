"""온톨로지 브릿지 (chat) — Section 3 v1 (DEPRECATED 2026-05-18).

⚠️ DEPRECATED — multiturn v2 로 마이그레이션 권장 (Phase 1~6 완료).
- 신 path: `backend/section3/agents/multiturn/` + `/api/section3/multiturn/*`
- 신 UI:  `frontend/src/components/section3/multiturn/MultiturnChat.tsx`
- 신 진입: `http://localhost:3000/?view=multiturn`

본 v1 (`/api/section3/chat`) 는 backward-compat 유지 — 호출하면 deprecation
warning header (`X-Deprecated`, `Warning`) 가 응답에 포함됨. v2 가 모든 기능을
대체하면 v1 path 완전 제거 예정.

이력 (v1):
1. 사용자 자연어 message + history
2. LLM 으로 intent 분류 (impact_analysis / simulate / explain)
3. 적절한 task agent 호출 (또는 explain 은 자체 처리)
4. task agent 의 streaming events 를 forward
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from backend.section3.agents.base import BaseAgent
from backend.section3.agents.code_impact_agent import CodeImpactAgent
from backend.section3.agents.data_impact_agent import DataImpactAgent
from backend.section3.agents.sandbox_agent import SIM_V2_REPO_ID, SandboxAgent
from backend.section3.sim_v2_bridge import (
    find_action_candidates,
    load_action,
    open_sim_v2_session,
    quick_diagnose_action,
)
from backend.section3.contracts import (
    AgentFinalResult,
    ChatMessage,
    ChatRequest,
    CodeImpactRequest,
    DataImpactRequest,
    SandboxRequest,
    StreamEvent,
)
from backend.section3.llm.intent_classifier import classify_intent

logger = logging.getLogger(__name__)


class BridgeAgent(BaseAgent):
    name = "bridge"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sandbox = SandboxAgent(self.modeling, self.llm)
        self._code_impact = CodeImpactAgent(self.modeling, self.llm)
        self._data_impact = DataImpactAgent(self.modeling, self.llm)

    async def run(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield self.thinking(f"의도 분석 중 — {req.message!r}")

        try:
            ic = classify_intent(req.message, req.history, llm=self.llm)
        except Exception as e:
            yield self.error(f"의도 분류 실패: {e}")
            return

        yield self.event(
            "intent_classification",
            modeling_intent=ic.modeling_intent,
            parameters=ic.parameters,
            confidence=ic.confidence,
            reasoning=ic.reasoning,
            suggested_followups=ic.suggested_followups,
        )

        # routing
        target = (ic.parameters or {}).get("target") or {}
        kind = target.get("kind")
        target_id = target.get("id")

        if ic.modeling_intent == "explain":
            # explain 은 task agent 없이 직접 처리
            async for ev in self._handle_explain(req.message):
                yield ev
            return

        if ic.modeling_intent == "simulate":
            if not target_id or kind not in ("step", "method", "class"):
                # Sprint 3+4 — sim_v2 후보 검색 + invariant 진단을 먼저 surface
                emitted_simv2 = False
                async for ev in self._emit_simv2_suggestions(req.message):
                    yield ev
                    emitted_simv2 = True
                if not emitted_simv2:
                    yield self.need_more_info({
                        "reason": "어떤 step 을 시뮬할지 명시 필요 (Step 번호 또는 method 이름)",
                        "questions": [{
                            "field": "target",
                            "question": "어느 step / method 를 시뮬할까요?",
                            "input_type": "text",
                        }],
                    })
                return
            sb_req = SandboxRequest(
                target_kind=kind if kind in ("step", "method", "class") else "step",
                target_id=target_id,
            )
            async for ev in self._sandbox.run(sb_req):
                yield ev
            return

        if ic.modeling_intent == "impact_analysis":
            if not target_id or not kind:
                yield self.need_more_info({
                    "reason": "어떤 대상의 변경 영향을 분석할지 명시 필요",
                    "questions": [{
                        "field": "target.kind",
                        "question": "변경 대상이 무엇인가요?",
                        "input_type": "select",
                        "options": [
                            {"id": "table", "label": "테이블"},
                            {"id": "method", "label": "메서드"},
                            {"id": "class", "label": "클래스"},
                            {"id": "standard_value", "label": "SC 기준값"},
                            {"id": "order", "label": "주문"},
                        ],
                    }],
                })
                return
            if kind in ("method", "class", "column"):
                ci_req = CodeImpactRequest(target_kind=kind, target_id=target_id)
                async for ev in self._code_impact.run(ci_req):
                    yield ev
            else:
                di_req = DataImpactRequest(target_kind=kind, target_id=target_id)
                async for ev in self._data_impact.run(di_req):
                    yield ev
            return

        yield self.error(f"지원하지 않는 intent: {ic.modeling_intent}")

    async def _emit_simv2_suggestions(self, user_query: str) -> AsyncIterator[StreamEvent]:
        """Sprint 3 + 4 — chat [LOW] fallback 자리에 sim_v2 후보 + invariant 진단 surface.

        흐름:
        1. W77+W78 KoreanTermResolver 로 user_query 매칭 term/action 찾기
        2. actions LIKE 보완 — label/aliases token 매칭
        3. 각 후보에 대해 W71→W74→W72 quick diagnose
        4. 결과를 `simv2_suggestions` 이벤트로 emit

        호출자가 generator 의 yield 발생 여부로 빈 결과를 감지 가능.
        """
        session = open_sim_v2_session()
        if session is None:
            return

        try:
            try:
                candidates = find_action_candidates(
                    session, user_query, SIM_V2_REPO_ID, top_n=3,
                )
            except Exception as e:
                logger.warning("find_action_candidates 실패: %s", e)
                candidates = []

            if not candidates:
                return

            yield self.thinking(
                f"sim_v2 후보 검색 → {len(candidates)}건. invariant 진단 진행…"
            )

            suggestions: list[dict[str, Any]] = []
            for cand in candidates:
                action = load_action(session, cand["fqn"], SIM_V2_REPO_ID)
                diag = quick_diagnose_action(session, action) if action else {
                    "ok": False, "fixtures": 0, "stubs": 0, "passing": 0,
                    "primary_failure": "action 로드 실패",
                }
                suggestions.append({
                    "action_fqn": cand["fqn"],
                    "label": cand["label"],
                    "code_method_fqn": cand.get("code_method_fqn"),
                    "matched_via": cand.get("matched_via"),
                    "score": cand["score"],
                    "diagnostic": diag,
                })

            yield self.event(
                "simv2_suggestions",
                query=user_query,
                count=len(suggestions),
                suggestions=suggestions,
            )

            top_lines = [
                f"{s['label']} ({s['action_fqn']}) — {s['diagnostic']['passing']}/{s['diagnostic']['fixtures']} PASS"
                for s in suggestions
            ]
            yield self.final(AgentFinalResult(
                ok=True,
                summary="자연어 query 의 가능 후보 — invariant 진단 동봉. 원하는 action 을 명시해 주세요:\n  - " + "\n  - ".join(top_lines),
                sandbox_result={
                    "via": "sim_v2_suggestions",
                    "suggestions": suggestions,
                },
            ).model_dump())
        finally:
            try:
                session.close()
            except Exception:
                pass

    async def _handle_explain(self, message: str) -> AsyncIterator[StreamEvent]:
        """explain intent — modeling.query 직접 호출 + (필요시) legacy search 로 source_locations 보강.

        ONTOLOGY_API_AUDIT.md §3.2 — modeling 의 source_locations 는 Class/Method 노드가 0개라
        항상 빈 배열. legacy `/api/ontology/search` 와 `/api/ontology/actions` 로 method fqn 후보를 보강.
        """
        yield self.modeling_call("explain", {"natural_language": message})
        try:
            resp = await self.modeling.query(
                intent="explain", natural_language=message
            )
        except Exception as e:
            yield self.error(f"modeling /query (explain) 호출 실패: {e}")
            return

        status = resp.get("status")
        if status in ("unsupported", "error"):
            result = resp.get("result") or {}
            yield self.error(f"explain 응답 {status}: {result.get('message')}", response=resp)
            return

        yield self.modeling_result(resp)

        result = resp.get("result") or {}
        for layer_name, items in self.extract_layers(result):
            yield self.layer_scan(layer_name, items)

        # legacy enrich — source_locations 가 비었을 때 legacy search 로 후보 method fqn 채우기.
        # modeling 의 matched_terms[].korean/english 가 더 정확한 검색어 (사용자 발화 통째보다).
        legacy: dict[str, Any] = {}
        if not result.get("source_locations"):
            queries: list[str] = []
            for t in (result.get("matched_terms") or [])[:3]:
                for k in ("korean", "english"):
                    v = t.get(k)
                    if v and v not in queries:
                        queries.append(v)
            if not queries:
                queries = [message]   # 매칭 term 없으면 원문 fallback

            all_hits: list[dict[str, Any]] = []
            try:
                for q in queries[:3]:
                    hits = await self.modeling.search(q, limit=6, repo_id="slab-design-real")
                    for h in hits:
                        if h not in all_hits:
                            all_hits.append(h)
            except Exception as e:
                logger.warning("legacy search enrich 실패: %s", e)
            if all_hits:
                yield self.layer_scan("legacy 검색 — 코드/액션 후보", all_hits[:10])
                legacy["search_hits"] = all_hits[:10]
                legacy["queries"] = queries[:3]

        summary = result.get("summary") or "위치 정보를 조회했습니다"
        yield self.final(
            AgentFinalResult(
                ok=True,
                summary=summary,
                modeling_response=resp,
                visualization=result.get("ontology_trace"),
                legacy_enrich=legacy or None,
            ).model_dump()
        )


__all__ = ["BridgeAgent"]
