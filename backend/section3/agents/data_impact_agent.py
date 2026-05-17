"""데이터 변경 영향도 분석 agent — table / standard_value / order 단위.

흐름은 CodeImpactAgent 와 동일하지만 target.kind 가 데이터 layer (table/standard/order).

* 사용자 요구의 "기준 변경 / slab data 변경 영향도" 매핑:
    - "기준" → standard_value
    - "slab data" → table
    - "주문" → order (14 Step 전체 시뮬)

* legacy enrich (ONTOLOGY_API_AUDIT.md §3): modeling 의 `standard_value` 분기가 잘못된 cypher 로 빠지는 버그 (요청 #04)
  가 있어, standard_value/table 호출 시 legacy `business-rules` + `anchor-bindings` 로 보강.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from backend.section3.agents.base import BaseAgent
from backend.section3.composer import OntologyComposer
from backend.section3.contracts import (
    AgentFinalResult,
    DataImpactRequest,
    StreamEvent,
)

logger = logging.getLogger(__name__)

_REPO_ID = "slab-design-real"


class DataImpactAgent(BaseAgent):
    name = "data_impact"

    async def run(self, req: DataImpactRequest) -> AsyncIterator[StreamEvent]:
        """composer.impact_analysis(table|standard_value|order) — legacy 실시간 합성."""
        yield self.thinking(
            f"데이터 변경 영향도 — {req.target_kind}={req.target_id!r} (composer 실시간 합성)"
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

        for layer_name, items in self.extract_layers(result):
            yield self.layer_scan(layer_name, items)

        # composer 의 자체 합성 데이터 layer
        if result.get("business_rules"):
            yield self.layer_scan("관련 비즈니스 룰", result["business_rules"])
        if result.get("anchors"):
            yield self.layer_scan("관련 anchor", result["anchors"])
        if result.get("search_hits"):
            yield self.layer_scan("legacy 통합 검색", result["search_hits"])

        risk = result.get("risk_level", "UNKNOWN")
        factors = result.get("risk_factors") or []
        summary = result.get("summary") or f"{req.target_kind} {req.target_id} 영향 분석 완료"

        legacy = {
            "business_rules": result.get("business_rules") or [],
            "anchors": result.get("anchors") or [],
            "search_hits": result.get("search_hits") or [],
        }
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
        """standard_code / table_name 으로 legacy 검색.

        - business-rules: statement / terms_ref 에 target_id 가 포함된 룰
        - anchor-bindings: target_slot 에 target_id 가 포함된 anchor
        - search: target_id 그대로 통합 검색 → term/action/code 후보 (fuzzy fallback)
        """
        out: dict[str, Any] = {}
        rules, anchors, search_hits = await asyncio.gather(
            self.modeling.list_business_rules(repo_id=_REPO_ID),
            self.modeling.list_anchor_bindings(repo_id=_REPO_ID),
            self.modeling.search(target_id, limit=8, repo_id=_REPO_ID),
            return_exceptions=True,
        )

        needle = target_id.lower()

        if isinstance(rules, list):
            matched = [
                {
                    "fqn": r.get("fqn"),
                    "statement": r.get("statement"),
                    "severity": r.get("severity"),
                    "enforced_by": r.get("enforced_by") or [],
                    "operational_history": r.get("operational_history") or [],
                }
                for r in rules
                if needle in (r.get("statement") or "").lower()
                or any(needle in (t or "").lower() for t in (r.get("terms_ref") or []))
                or needle in (r.get("fqn") or "").lower()
            ]
            if matched:
                out["business_rules"] = matched[:10]

        if isinstance(anchors, list):
            matched_anc = [
                {
                    "id": a.get("id"),
                    "anchor_locator": a.get("anchor_locator"),
                    "target_slot": a.get("target_slot"),
                    "target_action_fqn": a.get("target_action_fqn"),
                    "code_method_fqn": a.get("code_method_fqn"),
                    "line": a.get("line"),
                }
                for a in anchors
                if needle in (a.get("target_slot") or "").lower()
                or needle in (a.get("anchor_locator") or "").lower()
            ]
            if matched_anc:
                out["anchors"] = matched_anc[:10]

        if isinstance(search_hits, list) and search_hits:
            out["search_hits"] = search_hits[:8]

        return out


__all__ = ["DataImpactAgent"]
