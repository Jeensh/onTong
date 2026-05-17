"""Section 3 OntologyComposer — legacy `/api/ontology/*` 만 활용한 in-memory 응답 합성기.

설계 원칙 (ONTOLOGY_API_AUDIT.md §7 결론):
- modeling `/api/modeling/ontology/query` 의존 ❌ — graph 가 비어 있어도 동작.
- legacy `/api/ontology/*` 만으로 impact_analysis / simulate / explain 동등 응답 합성.
- 모든 호출은 **실시간** (캐싱 ❌ — 사용자 요구: "적재해서 읽지 않고 응답으로 작업").
- 응답 shape 은 기존 modeling 의 OntologyResponse 와 호환 — agents 가 그대로 forward 가능.

데이터 소스 (legacy endpoint):
- `actions/{fqn}` · `actions/{fqn}/anchor-bindings` · `actions/{fqn}/delegates-to-tree`
- `code-methods/{fqn}/call-sites` · `code-methods/{fqn}/anchor-bindings`
- `code-types/{class_fqn}` — Java body_text 추출
- `business-rules?repo_id=…` · `anchor-bindings?repo_id=…`
- `modules/inventory/actions?package=…` — method ↔ action 매핑 캐시
- `repos/{repo_id}/graph?mode=neighborhood&focus_fqn=…` — 시각화 trace
- `search?q=…&repo_id=…` — 자연어 매칭
- `terms/{fqn}` / `terms?repo_id=…` — term 카탈로그

응답 shape (modeling 호환):
```
{
  "status": "success|partial|need_more_info|error",
  "confidence": 0~1,
  "result": { ... intent-specific },
  "missing_info": { ... } | None,
  "timestamp": iso8601
}
```
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from backend.section3.clients.modeling_client import ModelingClient

logger = logging.getLogger(__name__)

DEFAULT_REPO_ID = "slab-design-real"
DEFAULT_PACKAGE = "com.example.slabdesign.feature.sd"


# ─── 헬퍼 ──────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_method_fqn(s: str) -> bool:
    """`com.x.Y.method(args)` 형식인가."""
    return re.search(r"\([^)]*\)$", s) is not None


def _is_action_fqn(s: str) -> bool:
    return s.startswith("action.")


def _extract_class_fqn(method_fqn: str) -> str | None:
    """`com.x.Y.MyClass.method(args)` → `com.x.Y.MyClass`."""
    m = re.match(r"^(.+)\.[A-Za-z_][\w$]*\([^)]*\)$", method_fqn)
    return m.group(1) if m else None


def _find_method(code_type: dict, method_fqn: str) -> dict | None:
    for m in code_type.get("methods") or []:
        if m.get("fqn") == method_fqn:
            return m
    return None


# ─── Composer 본체 ────────────────────────────────────────────────


class OntologyComposer:
    """legacy `/api/ontology/*` 만으로 modeling /query 와 동등 응답 합성."""

    def __init__(self, client: ModelingClient, repo_id: str = DEFAULT_REPO_ID):
        self.client = client
        self.repo_id = repo_id

    # ─── impact_analysis ──────────────────────────────────────────

    async def impact_analysis(self, target_kind: str, target_id: str) -> dict[str, Any]:
        """target.kind 별 분기.

        지원 kind: method · class · column · action · table · standard_value · order
        """
        if target_kind == "method":
            return await self._impact_method(target_id)
        if target_kind == "class":
            return await self._impact_class(target_id)
        if target_kind in ("action",) or _is_action_fqn(target_id):
            return await self._impact_action(target_id)
        if target_kind in ("table", "standard_value", "order"):
            return await self._impact_data(target_kind, target_id)
        if target_kind == "column":
            return self._unsupported(f"column kind 는 table 로 위임 — table id 입력 필요")
        return self._unsupported(f"target.kind={target_kind} 미지원")

    async def _impact_method(self, method_fqn: str) -> dict[str, Any]:
        """method_fqn 으로 impact 합성."""
        class_fqn = _extract_class_fqn(method_fqn)

        # 병렬 fetch (5종)
        tasks = [
            self.client.get_code_type(class_fqn) if class_fqn else _none(),
            self.client.get_method_anchor_bindings(method_fqn),
            self.client.get_call_sites(method_fqn),
            self.client.list_business_rules(repo_id=self.repo_id),
            self._list_modules_inventory_actions(),
        ]
        code_type, anchors, call_sites, rules, mia = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        # 정상화
        code_type = code_type if isinstance(code_type, dict) else {}
        anchors = anchors if isinstance(anchors, list) else []
        call_sites = call_sites if isinstance(call_sites, list) else []
        rules = rules if isinstance(rules, list) else []
        mia = mia if isinstance(mia, list) else []

        # method 정보 찾기
        method_info = _find_method(code_type, method_fqn) if code_type else None

        # method ↔ action 역추적 (modules/inventory/actions 의 primary_method_fqn)
        owning_actions = [a for a in mia if a.get("primary_method_fqn") == method_fqn]

        # business-rule 필터 (enforced_by 에 method_fqn 포함)
        relevant_rules = [r for r in rules if method_fqn in (r.get("enforced_by") or [])]

        # affected steps — anchor 의 target_slot 에서 step 추출 (e.g. "rule.scm.std.X.fallback")
        # 정확한 step 정보는 modeling 의 explain 응답에서 옴 → 이건 composer 가 직접 매핑 못 함.
        # 대신 owning_action 의 delegates-to-tree 로 sub-action 트래버스 + business-rule 의 statement
        # 에서 키워드 매칭.
        affected_steps: list[dict[str, Any]] = []
        downstream_steps: list[dict[str, Any]] = []
        # owning action 의 delegates tree 한 번 fetch
        delegates_tree: dict | None = None
        if owning_actions:
            try:
                delegates_tree = await self.client.get_action_delegates_tree(
                    owning_actions[0]["fqn"], max_depth=3
                )
            except Exception:
                delegates_tree = None

        # ontology_trace — repos/{repo_id}/graph?mode=neighborhood
        ontology_trace = await self._fetch_graph_trace(
            owning_actions[0]["fqn"] if owning_actions else method_fqn
        )

        # risk
        hard_rules = [r for r in relevant_rules if r.get("severity") == "hard"]
        if len(relevant_rules) >= 2 or hard_rules:
            risk_level, risk_factors = "HIGH", [f"강제 룰 {len(relevant_rules)}건", *(["hard severity"] if hard_rules else [])]
        elif relevant_rules or anchors:
            risk_level, risk_factors = "MEDIUM", [f"룰 {len(relevant_rules)}건 · anchor {len(anchors)}건"]
        else:
            risk_level, risk_factors = "LOW", []

        summary = (
            f"{(method_info or {}).get('name') or method_fqn.rsplit('.', 1)[-1]} 변경 — "
            f"action {len(owning_actions)}건 · 룰 {len(relevant_rules)}건 · anchor {len(anchors)}건"
        )

        result = {
            "summary": summary,
            "direct_impact": {
                "methods": [{
                    "fqn": method_fqn,
                    "class_fqn": class_fqn,
                    "body_text_excerpt": (method_info or {}).get("body_text", "")[:240],
                    "line_start": (method_info or {}).get("line_start"),
                    "line_end": (method_info or {}).get("line_end"),
                    "source_file": code_type.get("source_file"),
                }],
                "affected_steps": affected_steps,
                "owning_actions": [
                    {"fqn": a["fqn"], "verification_level": a.get("verification_level")}
                    for a in owning_actions
                ],
            },
            "indirect_impact": {
                "downstream_steps": downstream_steps,
                "delegates_tree": delegates_tree,
            },
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "ontology_trace": ontology_trace,
            "business_rules": [
                {
                    "fqn": r.get("fqn"),
                    "statement": r.get("statement"),
                    "severity": r.get("severity"),
                    "operational_history": r.get("operational_history") or [],
                }
                for r in relevant_rules
            ],
            "anchors": [
                {
                    "id": a.get("id"),
                    "anchor_locator": a.get("anchor_locator"),
                    "target_slot": a.get("target_slot"),
                    "target_action_fqn": a.get("target_action_fqn"),
                    "line": a.get("line"),
                }
                for a in anchors
            ],
            "call_sites": [
                {
                    "callee_simple_name": c.get("callee_simple_name"),
                    "line": c.get("line"),
                    "needs_user_confirm": c.get("needs_user_confirm"),
                    "analysis_source": c.get("analysis_source"),
                }
                for c in call_sites
                if c.get("needs_user_confirm") or (c.get("confidence") or 0) >= 0.5
            ],
        }
        return self._ok(result, confidence=0.85)

    async def _impact_class(self, class_fqn: str) -> dict[str, Any]:
        """class 전체 — 포함된 method 들의 영향 합산."""
        try:
            code_type = await self.client.get_code_type(class_fqn)
        except Exception:
            return self._error(f"class {class_fqn} 을 legacy 에서 찾을 수 없음")

        methods = code_type.get("methods") or []
        public_methods = [m for m in methods if "public" in (m.get("modifiers") or []) and not m.get("is_constructor")]

        # 병렬 — 각 method 의 owning action + rule
        mia = await self._list_modules_inventory_actions()
        method_fqns = {m["fqn"] for m in public_methods}
        owning = [a for a in mia if a.get("primary_method_fqn") in method_fqns]

        rules = await self.client.list_business_rules(repo_id=self.repo_id)
        relevant_rules = [
            r for r in rules
            if any(efqn in method_fqns for efqn in (r.get("enforced_by") or []))
        ]

        ontology_trace = await self._fetch_graph_trace(class_fqn)
        risk = "HIGH" if len(relevant_rules) >= 3 else "MEDIUM" if relevant_rules else "LOW"

        result = {
            "summary": f"{code_type.get('simple_name')} 클래스 — public method {len(public_methods)}개, owning action {len(owning)}건, 룰 {len(relevant_rules)}건",
            "direct_impact": {
                "methods": [
                    {
                        "fqn": m["fqn"],
                        "name": m.get("name"),
                        "line_start": m.get("line_start"),
                        "line_end": m.get("line_end"),
                        "role": m.get("role"),
                    }
                    for m in public_methods
                ],
                "owning_actions": [
                    {"fqn": a["fqn"], "primary_method_fqn": a.get("primary_method_fqn")}
                    for a in owning
                ],
            },
            "indirect_impact": {"downstream_steps": []},
            "risk_level": risk,
            "risk_factors": [f"강제 룰 {len(relevant_rules)}건"] if relevant_rules else [],
            "ontology_trace": ontology_trace,
            "business_rules": [
                {
                    "fqn": r.get("fqn"),
                    "statement": r.get("statement"),
                    "severity": r.get("severity"),
                }
                for r in relevant_rules
            ],
        }
        return self._ok(result, confidence=0.8)

    async def _impact_action(self, action_fqn: str) -> dict[str, Any]:
        """action_fqn 으로 impact — realizations · delegates · anchors 트래버스."""
        tasks = [
            self.client.get_action(action_fqn),
            self.client.get_action_anchor_bindings(action_fqn),
            self.client.get_action_delegates_tree(action_fqn, max_depth=3),
            self.client.list_business_rules(repo_id=self.repo_id),
        ]
        action, anchors, delegates, rules = await asyncio.gather(*tasks, return_exceptions=True)
        action = action if isinstance(action, dict) else {}
        anchors = anchors if isinstance(anchors, list) else []
        delegates = delegates if isinstance(delegates, dict) else {}
        rules = rules if isinstance(rules, list) else []

        realiz_method_fqns = {r.get("code_method_fqn") for r in (action.get("realizations") or [])}
        relevant_rules = [
            r for r in rules
            if any(efqn in realiz_method_fqns for efqn in (r.get("enforced_by") or []))
        ]
        ontology_trace = await self._fetch_graph_trace(action_fqn)
        risk = "HIGH" if len(relevant_rules) >= 2 else "MEDIUM" if (relevant_rules or anchors) else "LOW"

        result = {
            "summary": f"{action.get('label') or action_fqn} — realizations {len(realiz_method_fqns)}건 · anchor {len(anchors)}건 · 룰 {len(relevant_rules)}건",
            "direct_impact": {
                "methods": [{"fqn": fqn} for fqn in realiz_method_fqns if fqn],
                "owning_actions": [{"fqn": action_fqn, "verification_level": action.get("verification_level")}],
            },
            "indirect_impact": {
                "downstream_steps": [],
                "delegates_tree": delegates,
            },
            "risk_level": risk,
            "risk_factors": [f"강제 룰 {len(relevant_rules)}건"] if relevant_rules else [],
            "ontology_trace": ontology_trace,
            "business_rules": [
                {"fqn": r.get("fqn"), "statement": r.get("statement"), "severity": r.get("severity")}
                for r in relevant_rules
            ],
            "anchors": [
                {
                    "id": a.get("id"),
                    "anchor_locator": a.get("anchor_locator"),
                    "target_slot": a.get("target_slot"),
                    "code_method_fqn": a.get("code_method_fqn"),
                    "line": a.get("line"),
                }
                for a in anchors
            ],
        }
        return self._ok(result, confidence=0.85)

    async def _impact_data(self, kind: str, target_id: str) -> dict[str, Any]:
        """table / standard_value / order 의 영향 — anchor/rule statement 매칭."""
        tasks = [
            self.client.list_business_rules(repo_id=self.repo_id),
            self.client.list_anchor_bindings(repo_id=self.repo_id),
            self.client.search(target_id, limit=8, repo_id=self.repo_id),
        ]
        rules, anchors, search_hits = await asyncio.gather(*tasks, return_exceptions=True)
        rules = rules if isinstance(rules, list) else []
        anchors = anchors if isinstance(anchors, list) else []
        search_hits = search_hits if isinstance(search_hits, list) else []

        needle = target_id.lower()
        rel_rules = [
            r for r in rules
            if needle in (r.get("statement") or "").lower()
            or any(needle in (t or "").lower() for t in (r.get("terms_ref") or []))
            or needle in (r.get("fqn") or "").lower()
        ]
        rel_anchors = [
            a for a in anchors
            if needle in (a.get("target_slot") or "").lower()
            or needle in (a.get("anchor_locator") or "").lower()
        ]

        risk = "HIGH" if len(rel_rules) >= 2 else "MEDIUM" if (rel_rules or rel_anchors) else "LOW"
        summary = f"{kind} '{target_id}' — 룰 {len(rel_rules)}건 · anchor {len(rel_anchors)}건 · search {len(search_hits)}건"

        result = {
            "summary": summary,
            "direct_impact": {"methods": [], "affected_steps": []},
            "indirect_impact": {"downstream_steps": []},
            "risk_level": risk,
            "risk_factors": [],
            "ontology_trace": {"nodes": [], "edges": [], "cypher": ""},
            "business_rules": [
                {"fqn": r.get("fqn"), "statement": r.get("statement"), "severity": r.get("severity")}
                for r in rel_rules
            ],
            "anchors": [
                {
                    "id": a.get("id"),
                    "anchor_locator": a.get("anchor_locator"),
                    "target_slot": a.get("target_slot"),
                    "code_method_fqn": a.get("code_method_fqn"),
                    "line": a.get("line"),
                }
                for a in rel_anchors
            ],
            "search_hits": search_hits[:6],
        }
        return self._ok(result, confidence=0.6)

    # ─── simulate ─────────────────────────────────────────────────

    async def simulate(self, target_kind: str, target_id: str) -> dict[str, Any]:
        """action/method 의 param schema → test_cases 자동 합성.

        지원: action · method · class. (step 은 modeling 만 지원하므로 fallback)
        """
        if _is_action_fqn(target_id) or target_kind == "action":
            return await self._simulate_action(target_id)
        if _is_method_fqn(target_id) or target_kind == "method":
            return await self._simulate_method(target_id)
        if target_kind == "class":
            return await self._simulate_class(target_id)
        return self._unsupported(f"simulate(kind={target_kind}) 는 composer 미지원 — modeling /query 로 위임")

    async def _simulate_action(self, action_fqn: str) -> dict[str, Any]:
        action = await self.client.get_action(action_fqn)
        params = action.get("params") or []
        output = action.get("output")
        cases = self._cases_from_params(params, prefix=f"A_{action.get('label','case')}")

        # method body_text + class fields + method anchors 동봉 (transpile 단계 입력)
        realiz = (action.get("realizations") or [])[:1]
        method_fqn = realiz[0].get("code_method_fqn") if realiz else None
        body_text = None
        line_range = None
        class_fields: list[dict] = []
        method_anchors: list[dict] = []
        if method_fqn:
            try:
                class_fqn = _extract_class_fqn(method_fqn)
                code_type = await self.client.get_code_type(class_fqn) if class_fqn else {}
                m = _find_method(code_type, method_fqn)
                if m:
                    body_text = m.get("body_text")
                    line_range = [m.get("line_start"), m.get("line_end")]
                class_fields = code_type.get("fields") or []
                method_anchors = await self.client.get_method_anchor_bindings(method_fqn)
            except Exception:
                pass

        result = {
            "summary": f"action {action.get('label')} 대상 {len(cases)} case (param {len(params)}개)",
            "test_cases": cases,
            "code_skeleton": _java_skeleton_from_action(action, cases),
            "data_dependencies": [],
            "ontology_trace": await self._fetch_graph_trace(action_fqn),
            "source_for_transpile": {
                "method_fqn": method_fqn,
                "body_text": body_text,
                "line_range": line_range,
                "params": params,
                "output": output,
                "class_fields": class_fields,
                "method_anchors": method_anchors,
            },
        }
        return self._ok(result, confidence=0.8)

    async def _simulate_method(self, method_fqn: str) -> dict[str, Any]:
        class_fqn = _extract_class_fqn(method_fqn)
        code_type_task = self.client.get_code_type(class_fqn) if class_fqn else _none()
        anchors_task = self.client.get_method_anchor_bindings(method_fqn)
        code_type, method_anchors = await asyncio.gather(
            code_type_task, anchors_task, return_exceptions=True
        )
        code_type = code_type if isinstance(code_type, dict) else {}
        method_anchors = method_anchors if isinstance(method_anchors, list) else []

        m = _find_method(code_type, method_fqn) if code_type else None
        if not m:
            return self._error(f"method {method_fqn} 의 body 를 legacy code-types 에서 찾을 수 없음")

        params = m.get("params") or []
        cases = self._cases_from_params(
            [{"name": p.get("name"), "type": p.get("type")} for p in params],
            prefix=f"M_{m.get('name')}",
        )
        return self._ok({
            "summary": f"method {m.get('name')} 대상 {len(cases)} case (param {len(params)}개)",
            "test_cases": cases,
            "code_skeleton": _java_skeleton_from_method(m, cases),
            "data_dependencies": [],
            "source_for_transpile": {
                "method_fqn": method_fqn,
                "body_text": m.get("body_text"),
                "line_range": [m.get("line_start"), m.get("line_end")],
                "params": params,
                "return_type": m.get("return_type"),
                "class_fields": code_type.get("fields") or [],
                "method_anchors": method_anchors,
            },
        }, confidence=0.8)

    async def _simulate_class(self, class_fqn: str) -> dict[str, Any]:
        code_type = await self.client.get_code_type(class_fqn)
        methods = [m for m in (code_type.get("methods") or []) if "public" in (m.get("modifiers") or []) and not m.get("is_constructor")]
        cases: list[dict] = []
        for m in methods[:5]:
            for c in self._cases_from_params(
                [{"name": p.get("name"), "type": p.get("type")} for p in (m.get("params") or [])],
                prefix=f"{m['name']}",
            ):
                c["method_fqn"] = m["fqn"]
                cases.append(c)
        return self._ok({
            "summary": f"class {code_type.get('simple_name')} — public method {len(methods)}개 × {len(cases)//max(len(methods),1)} case",
            "test_cases": cases,
        }, confidence=0.7)

    # ─── explain ──────────────────────────────────────────────────

    async def explain(self, natural_language: str) -> dict[str, Any]:
        """legacy `search` 로 1차 후보 → 매칭 fqn 의 detail enrich."""
        try:
            hits = await self.client.search(natural_language, limit=10, repo_id=self.repo_id)
        except Exception:
            hits = []

        if not hits:
            # term in-memory fuzzy fallback — `terms` 받아 fuzzy match
            try:
                terms = await self.client.list_terms(repo_id=self.repo_id)
                needle = natural_language.lower()
                hits = [
                    {"kind": "term", "fqn": t["fqn"], "label": t.get("label"), "score": 0.5}
                    for t in terms
                    if needle in (t.get("label") or "").lower()
                    or needle in (t.get("description") or "").lower()
                    or any(needle in (a or "").lower() for a in (t.get("aliases") or []))
                ][:5]
            except Exception:
                hits = []

        return self._ok({
            "summary": f"legacy search 결과 {len(hits)} 건",
            "matched_hits": hits,
            "source_locations": [
                {"kind": h.get("kind"), "fqn": h.get("fqn"), "label": h.get("label")}
                for h in hits if h.get("kind") in ("action", "code_method", "code")
            ],
        }, confidence=0.7 if hits else 0.3)

    # ─── 내부 유틸 ────────────────────────────────────────────────

    _mia_cache: list[dict] | None = None

    async def _list_modules_inventory_actions(self) -> list[dict[str, Any]]:
        """ONTOLOGY_API_AUDIT.md §7.2 의 핵심 endpoint — method ↔ action 매핑.

        인스턴스 lifetime 동안만 cache (실시간성 유지). 합성기는 매 요청 새 인스턴스 사용 권장.
        """
        if self._mia_cache is not None:
            return self._mia_cache
        try:
            r = await self.client._client.get(
                f"/api/ontology/repos/{self.repo_id}/modules/inventory/actions",
                params={"package": DEFAULT_PACKAGE, "recursive": True},
            )
            r.raise_for_status()
            body = r.json()
            self._mia_cache = body if isinstance(body, list) else []
        except Exception as e:
            logger.warning("modules/inventory/actions fetch 실패: %s", e)
            self._mia_cache = []
        return self._mia_cache

    async def _fetch_graph_trace(self, focus_fqn: str) -> dict[str, Any]:
        """`repos/{repo_id}/graph?mode=neighborhood&focus_fqn=…&hops=2` 시각화 trace."""
        try:
            r = await self.client._client.get(
                f"/api/ontology/repos/{self.repo_id}/graph",
                params={"mode": "neighborhood", "focus_fqn": focus_fqn, "hops": 2},
            )
            r.raise_for_status()
            g = r.json()
            return {
                "nodes": [
                    {"id": n["id"], "label": n.get("label"), "group": n.get("kind")}
                    for n in g.get("nodes") or []
                ],
                "edges": [
                    {"from": e["source"], "to": e["target"], "label": e.get("kind")}
                    for e in g.get("edges") or []
                ],
                "cypher": "",   # legacy graph endpoint 는 cypher 미반환 — composer 가 합성한 trace
            }
        except Exception as e:
            logger.warning("graph trace 실패 (focus=%s): %s", focus_fqn, e)
            return {"nodes": [], "edges": [], "cypher": ""}

    @staticmethod
    def _cases_from_params(params: list[dict], prefix: str = "case") -> list[dict[str, Any]]:
        """param schema 기반 normal/boundary/error 케이스 자동 생성."""
        cases = []
        for case_type in ("normal", "boundary", "error"):
            inp = {p.get("name") or f"p{i}": _sample_value(p.get("type") or "String", case_type)
                   for i, p in enumerate(params)}
            cases.append({
                "case_id": f"{prefix}_{case_type[0].upper()}",
                "case_type": case_type,
                "description": f"{case_type} 케이스",
                "input": inp,
                "expected_output": None,
            })
        return cases

    @staticmethod
    def _ok(result: dict, confidence: float = 0.8) -> dict[str, Any]:
        return {
            "request_id": f"composer-{datetime.now().timestamp():.0f}",
            "status": "success",
            "confidence": confidence,
            "result": result,
            "missing_info": None,
            "timestamp": _now(),
            "source": "composer",   # ★ 응답이 modeling /query 가 아닌 composer 임을 명시
        }

    @staticmethod
    def _unsupported(message: str) -> dict[str, Any]:
        return {
            "request_id": f"composer-{datetime.now().timestamp():.0f}",
            "status": "unsupported",
            "confidence": 1.0,
            "result": {"message": message},
            "timestamp": _now(),
            "source": "composer",
        }

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {
            "request_id": f"composer-{datetime.now().timestamp():.0f}",
            "status": "error",
            "confidence": 1.0,
            "result": {"message": message},
            "timestamp": _now(),
            "source": "composer",
        }


# ─── 케이스 값 sampler ────────────────────────────────────────────


def _sample_value(java_type: str, case_type: str) -> Any:
    """Java 타입 → normal/boundary/error 샘플 값."""
    t = java_type.lower()
    if "string" in t:
        return {"normal": "ABC", "boundary": "", "error": None}[case_type]
    if "bigdecimal" in t or "double" in t or "float" in t:
        return {"normal": 1.0, "boundary": 0.0, "error": -1.0}[case_type]
    if "int" in t or "long" in t or "short" in t:
        return {"normal": 100, "boundary": 0, "error": -1}[case_type]
    if "boolean" in t:
        return {"normal": True, "boundary": False, "error": None}[case_type]
    if "list" in t or "array" in t or "[]" in t:
        return {"normal": [1, 2, 3], "boundary": [], "error": None}[case_type]
    if "map" in t or "dict" in t:
        return {"normal": {"k": "v"}, "boundary": {}, "error": None}[case_type]
    # object_ref / 사용자 타입
    return {"normal": {"_placeholder": True}, "boundary": None, "error": None}[case_type]


# ─── Java skeleton helpers ─────────────────────────────────────────


def _java_skeleton_from_action(action: dict, cases: list[dict]) -> str:
    lines = ["// Auto-generated by OntologyComposer", "import org.junit.jupiter.api.Test;\n"]
    for c in cases:
        lines.append(f"@Test\nvoid test_{c['case_id']}() {{\n    // {c['case_type']} 케이스 — input: {c['input']}\n    // TODO: implement assertion\n}}\n")
    return "\n".join(lines)


def _java_skeleton_from_method(method: dict, cases: list[dict]) -> str:
    name = method.get("name", "method")
    lines = ["// Auto-generated by OntologyComposer", "import org.junit.jupiter.api.Test;\n"]
    for c in cases:
        lines.append(f"@Test\nvoid test_{name}_{c['case_id']}() {{\n    // {c['case_type']} 케이스\n    // input: {c['input']}\n    // TODO: implement assertion\n}}\n")
    return "\n".join(lines)


async def _none() -> None:
    return None


__all__ = ["OntologyComposer", "DEFAULT_REPO_ID"]
