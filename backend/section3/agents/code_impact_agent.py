"""코드 변경 영향도 분석 agent — method / class / column 단위.

흐름:
1. modeling.query(intent=impact_analysis, target={kind:method|class|column, id}) 호출
2. response 의 direct_impact / indirect_impact / risk_level / ontology_trace 그대로 forward
3. modeling graph 에 Class/Method 노드가 없는 환경 (현재) → legacy `/api/ontology/*` 로 보강:
   - `actions/{id}` (id 가 action fqn 인 경우) → realizations[].code_method_fqn
   - `code-methods/{fqn}/anchor-bindings` → method 내 anchor (literal·guard) 라인
   - `code-types/{class_fqn}` → 해당 method 의 body_text·line_start/end
   - `business-rules` 의 enforced_by 매칭 → 위반 시 위반될 rule 목록
4. layer 순서 스캔 (Method → Step → 다운스트림 Step → Java body → Rule) progress
5. risk_level 에 따라 사용자에게 안내 message
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncIterator

from backend.section3.agents.base import BaseAgent
from backend.section3.composer import OntologyComposer
from backend.section3.contracts import (
    AgentFinalResult,
    CodeImpactRequest,
    StreamEvent,
)

logger = logging.getLogger(__name__)

_REPO_ID = "slab-design-real"  # ONTOLOGY_API_AUDIT.md §2.1 — legacy 의 main repo


def _extract_class_fqn(method_fqn: str) -> str | None:
    """`com.x.y.MyClass.myMethod(args)` → `com.x.y.MyClass`."""
    # method fqn = `<class fqn>.<method name>(<params>)`
    m = re.match(r"^(.+)\.[A-Za-z_][\w$]*\([^)]*\)$", method_fqn)
    return m.group(1) if m else None


def _find_method_in_code_type(code_type: dict, method_fqn: str) -> dict | None:
    """code-types/{class_fqn} 응답의 methods[] 에서 fqn 일치하는 항목."""
    for m in code_type.get("methods") or []:
        if m.get("fqn") == method_fqn:
            return m
    return None


class CodeImpactAgent(BaseAgent):
    name = "code_impact"

    async def run(self, req: CodeImpactRequest) -> AsyncIterator[StreamEvent]:
        """flow:
        1. OntologyComposer.impact_analysis — legacy `/api/ontology/*` 실시간 합성 (modeling /query 미호출)
        2. composer 응답을 modeling_response 호환 shape 로 forward
        3. (보조) modeling /query 도 호출하여 ontology_trace 비교 — 일치 시 confidence 가산
        """
        yield self.thinking(
            f"코드 영향도 — {req.target_kind}={req.target_id!r} (composer 실시간 합성)"
        )

        composer = OntologyComposer(self.modeling, repo_id=_REPO_ID)
        yield self.modeling_call("composer.impact_analysis", {"target": {"kind": req.target_kind, "id": req.target_id}})
        try:
            resp = await composer.impact_analysis(req.target_kind, req.target_id)
        except Exception as e:
            yield self.error(f"composer 실패: {e}")
            return

        status = resp.get("status")
        if status == "unsupported":
            yield self.error(f"composer unsupported: {resp.get('result', {}).get('message')}")
            return
        if status == "error":
            yield self.error(f"composer error: {resp.get('result', {}).get('message')}")
            return

        yield self.modeling_result(resp)
        result = resp.get("result") or {}

        # layer scan
        for layer_name, items in self.extract_layers(result):
            yield self.layer_scan(layer_name, items)

        # 추가 layer — composer 의 자체 합성 데이터
        if result.get("business_rules"):
            yield self.layer_scan("비즈니스 룰", result["business_rules"])
        if result.get("anchors"):
            yield self.layer_scan("anchor (라인 매핑)", result["anchors"])
        if result.get("call_sites"):
            yield self.layer_scan("call-sites", result["call_sites"])
        if (result.get("direct_impact") or {}).get("owning_actions"):
            yield self.layer_scan("owning actions", result["direct_impact"]["owning_actions"])

        risk = result.get("risk_level", "UNKNOWN")
        factors = result.get("risk_factors") or []
        summary = result.get("summary") or f"{req.target_kind} {req.target_id} 영향 분석 완료"

        # legacy_enrich payload (UI 가 동일 형식으로 표시 가능)
        legacy = {
            "business_rules": result.get("business_rules") or [],
            "anchors": result.get("anchors") or [],
            "call_sites": result.get("call_sites") or [],
            "source_code": [
                {
                    "method_fqn": m.get("fqn"),
                    "body_text": m.get("body_text_excerpt") or m.get("body_text"),
                    "line_start": m.get("line_start"),
                    "line_end": m.get("line_end"),
                    "source_file": m.get("source_file"),
                }
                for m in (result.get("direct_impact") or {}).get("methods") or []
                if m.get("body_text_excerpt") or m.get("body_text")
            ],
        }
        # 빈 값 제거
        legacy = {k: v for k, v in legacy.items() if v}

        yield self.final(
            AgentFinalResult(
                ok=True,
                summary=f"[{risk}] {summary}" + (f" · 위험요인: {', '.join(factors)}" if factors else ""),
                modeling_response=resp,
                visualization=result.get("ontology_trace"),
                legacy_enrich=legacy or None,
            ).model_dump()
        )

    async def _enrich_with_legacy(self, kind: str, target_id: str) -> dict[str, Any]:
        """legacy `/api/ontology/*` 다종 endpoint 를 병렬 호출하여 enrich.

        Returns:
            {
              "source_code":      [{ method_fqn, body_text, line_start, line_end, source_file }],
              "business_rules":   [{ fqn, statement, severity, operational_history[] }],
              "anchors":          [{ id, anchor_locator, target_slot, line }],
              "action_realizations": [{ code_method_fqn, confidence, scope }],
            }
        """
        out: dict[str, Any] = {}

        # 병렬 fetch: business-rules + anchor-bindings + (kind=method 이면 method anchor + code-type)
        tasks: dict[str, Any] = {
            "rules": self.modeling.list_business_rules(repo_id=_REPO_ID),
        }

        is_action_fqn = target_id.startswith("action.")
        is_method_fqn = re.search(r"\([^)]*\)$", target_id) is not None

        if is_action_fqn:
            tasks["action"] = self.modeling.get_action(target_id)
            tasks["action_anchors"] = self.modeling.get_action_anchor_bindings(target_id)
            tasks["delegates"] = self.modeling.get_action_delegates_tree(target_id, max_depth=2)
        elif is_method_fqn:
            tasks["method_anchors"] = self.modeling.get_method_anchor_bindings(target_id)
            tasks["call_sites"] = self.modeling.get_call_sites(target_id)
            class_fqn = _extract_class_fqn(target_id)
            if class_fqn:
                tasks["code_type"] = self.modeling.get_code_type(class_fqn)
        elif kind == "class":
            tasks["code_type"] = self.modeling.get_code_type(target_id)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        data = dict(zip(tasks.keys(), results))

        # business-rules → enforced_by 에 target 매칭되는 것만 필터
        rules = data.get("rules")
        if isinstance(rules, list):
            matched_rules = [
                {
                    "fqn": r.get("fqn"),
                    "statement": r.get("statement"),
                    "severity": r.get("severity"),
                    "enforced_by": r.get("enforced_by") or [],
                    "operational_history": r.get("operational_history") or [],
                }
                for r in rules
                if _rule_matches_target(r, target_id, is_action_fqn, is_method_fqn)
            ]
            if matched_rules:
                out["business_rules"] = matched_rules

        # anchor → method/action target
        anchors_raw = data.get("method_anchors") or data.get("action_anchors")
        if isinstance(anchors_raw, list) and anchors_raw:
            out["anchors"] = [
                {
                    "id": a.get("id"),
                    "anchor_locator": a.get("anchor_locator"),
                    "target_slot": a.get("target_slot"),
                    "target_action_fqn": a.get("target_action_fqn"),
                    "code_method_fqn": a.get("code_method_fqn"),
                    "line": a.get("line"),
                    "confidence": a.get("confidence"),
                }
                for a in anchors_raw
            ]

        # action.realizations
        action = data.get("action")
        if isinstance(action, dict):
            realiz = action.get("realizations") or []
            if realiz:
                out["action_realizations"] = [
                    {
                        "code_method_fqn": r.get("code_method_fqn"),
                        "confidence": r.get("confidence"),
                        "scope": r.get("scope"),
                        "rationale": r.get("rationale"),
                    }
                    for r in realiz
                ]

        # delegates_tree (action 의 sub-action 트리)
        delegates = data.get("delegates")
        if isinstance(delegates, dict) and delegates.get("children"):
            out["delegates_tree"] = delegates

        # source code (body_text + line_start/end)
        code_type = data.get("code_type")
        if isinstance(code_type, dict):
            if is_method_fqn:
                m = _find_method_in_code_type(code_type, target_id)
                if m:
                    out["source_code"] = [{
                        "method_fqn": m.get("fqn"),
                        "body_text": m.get("body_text"),
                        "line_start": m.get("line_start"),
                        "line_end": m.get("line_end"),
                        "source_file": code_type.get("source_file"),
                        "annotations": m.get("annotations"),
                        "role": m.get("role"),
                    }]
            else:
                # class 전체 — 모든 method 의 body_text 는 너무 큼. 핵심 method 만.
                methods = (code_type.get("methods") or [])[:5]
                out["source_code"] = [
                    {
                        "method_fqn": m.get("fqn"),
                        "body_text": (m.get("body_text") or "")[:400],
                        "line_start": m.get("line_start"),
                        "line_end": m.get("line_end"),
                        "source_file": code_type.get("source_file"),
                        "role": m.get("role"),
                    }
                    for m in methods
                ]

        # call_sites (confidence>0.5 또는 needs_user_confirm)
        call_sites = data.get("call_sites")
        if isinstance(call_sites, list):
            interesting = [
                {
                    "callee_simple_name": c.get("callee_simple_name"),
                    "line": c.get("line"),
                    "needs_user_confirm": c.get("needs_user_confirm"),
                    "analysis_source": c.get("analysis_source"),
                }
                for c in call_sites
                if c.get("needs_user_confirm") or (c.get("confidence") or 0) >= 0.5
            ]
            if interesting:
                out["call_sites"] = interesting

        return out


def _rule_matches_target(rule: dict, target_id: str, is_action: bool, is_method: bool) -> bool:
    """business_rule.enforced_by 에 target_id 가 포함되는지."""
    enforced = rule.get("enforced_by") or []
    if is_method:
        return target_id in enforced
    if is_action:
        # action fqn → realizations 의 method fqn 으로 매칭은 caller 가 채워야. 여기선 약식 (simple_name).
        simple = target_id.split(".")[-1]
        return any(simple in e for e in enforced)
    # class 의 simple_name 또는 fqn
    return any(target_id in e for e in enforced)


__all__ = ["CodeImpactAgent"]
