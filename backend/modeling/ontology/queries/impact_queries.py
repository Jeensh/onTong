"""Agent 1 (영향도 파악) 쿼리.

Intent ``impact_analysis`` 핸들러. 변경 대상의 영향을 Cypher traversal로
추적하고, 결과를 그래프 (nodes/edges) 와 실행한 Cypher 쿼리까지 함께 반환한다.

target_kind:
- table  : SC 테이블 변경 → SC → Step → Method → Class
- method : 메서드 변경 → CALCULATES Step + 다운스트림 Step
- class  : 클래스 변경 → CONTAINS Method → CALCULATES Step
- order  : 주문 변경 → 14 Step 모두가 영향 (전체 흐름)
- standard_value: SC 기준값 변경 (table과 유사하지만 값 변경 시 Step 재계산 필요)
- column : 컬럼 변경 (간소화)
"""

from __future__ import annotations

import logging
from typing import Any

from ..client import OntologyClient, get_client
from backend.shared.contracts.ontology import (
    MissingInfo,
    MissingInfoQuestion,
    OntologyRequest,
    OntologyResponse,
    Status,
)

logger = logging.getLogger(__name__)


SUPPORTED_TARGET_KINDS = {
    "table",
    "method",
    "class",
    "column",
    "standard_value",
    "order",
}


def _missing_target_kind(req: OntologyRequest) -> OntologyResponse:
    return OntologyResponse(
        request_id=req.request_id,
        status=Status.NEED_MORE_INFO,
        missing_info=MissingInfo(
            reason="변경 대상 종류가 명시되지 않았습니다",
            questions=[
                MissingInfoQuestion(
                    field="target.kind",
                    question="변경 대상이 무엇인가요?",
                    input_type="select",
                    options=[
                        {"id": "table", "label": "테이블"},
                        {"id": "method", "label": "메서드"},
                        {"id": "class", "label": "클래스"},
                        {"id": "standard_value", "label": "SC 기준값"},
                        {"id": "order", "label": "주문 (14 Step 시뮬레이션)"},
                    ],
                )
            ],
        ),
    )


# ─────────────────────────────────────────────────────────────
# 그래프 빌더 — 결과를 OntologySubgraphView가 쓰는 노드/엣지로
# ─────────────────────────────────────────────────────────────


def _node(id_: str, label: str, group: str) -> dict:
    return {"id": id_, "label": label, "group": group}


def _edge(a: str, b: str, lbl: str) -> dict:
    return {"from": a, "to": b, "label": lbl}


# ─────────────────────────────────────────────────────────────
# Table 변경 영향
# ─────────────────────────────────────────────────────────────


def _table_impact(client: OntologyClient, table_id: str) -> dict[str, Any]:
    cypher = (
        "MATCH (t:Table) WHERE t.id = $tid OR t.name = $tid "
        "OPTIONAL MATCH (t)-[:MAPS_TO_STANDARD]->(std:Standard) "
        "OPTIONAL MATCH (s:Step)-[:USES_STANDARD]->(std) "
        "OPTIONAL MATCH (m:Method)-[:CALCULATES]->(s) "
        "OPTIONAL MATCH (c:Class)-[:CONTAINS]->(m) "
        "RETURN t.name AS table_name, std.code AS standard_code, "
        "       collect(DISTINCT {step_number: s.step_number, korean_name: s.korean_name}) AS steps, "
        "       collect(DISTINCT {class: c.name, name: m.name}) AS methods"
    )
    rows = client.query(cypher, tid=table_id)
    if not rows or not rows[0]["table_name"]:
        return {
            "table_name": None,
            "steps": [],
            "methods": [],
            "downstream_steps": [],
            "cypher": cypher,
            "graph": {"nodes": [], "edges": []},
        }
    r = rows[0]
    direct_methods = [m for m in r["methods"] if m.get("name")]
    direct_steps = [s for s in r["steps"] if s.get("step_number") is not None]
    downstream: list[dict] = []
    if direct_steps:
        nums = [s["step_number"] for s in direct_steps]
        d_rows = client.query(
            "MATCH (s:Step) WHERE s.step_number IN $nums "
            "MATCH (s)-[:PRECEDES|DEPENDS_ON*1..3]->(s2:Step) "
            "RETURN DISTINCT s2.step_number AS n, s2.korean_name AS name ORDER BY n",
            nums=nums,
        )
        downstream = [{"step_number": d["n"], "korean_name": d["name"]} for d in d_rows]

    # 그래프 빌드
    nodes: list[dict] = []
    edges: list[dict] = []
    table_node = f"table:{r['table_name']}"
    nodes.append(_node(table_node, r["table_name"], "table"))
    if r["standard_code"]:
        sc_node = f"std:{r['standard_code']}"
        nodes.append(_node(sc_node, r["standard_code"], "standard"))
        edges.append(_edge(table_node, sc_node, "MAPS_TO_STANDARD"))
        for s in direct_steps:
            sid = f"step:{s['step_number']}"
            nodes.append(
                _node(sid, f"Step {s['step_number']}\n{s['korean_name']}", "step")
            )
            edges.append(_edge(sid, sc_node, "USES_STANDARD"))
        for m in direct_methods:
            if not m.get("name"):
                continue
            mid = f"method:{m['class']}.{m['name']}"
            nodes.append(_node(mid, f"{m['class']}\n.{m['name']}()", "method"))
            for s in direct_steps:
                edges.append(_edge(mid, f"step:{s['step_number']}", "CALCULATES"))
        for d in downstream:
            did = f"step:{d['step_number']}"
            if not any(n["id"] == did for n in nodes):
                nodes.append(
                    _node(did, f"Step {d['step_number']}\n{d['korean_name']}", "step")
                )
            for s in direct_steps:
                edges.append(
                    _edge(f"step:{s['step_number']}", did, "PRECEDES*")
                )

    return {
        "table_name": r["table_name"],
        "standard_code": r["standard_code"],
        "direct_methods": direct_methods,
        "direct_steps": direct_steps,
        "downstream_steps": downstream,
        "cypher": cypher,
        "graph": {"nodes": nodes, "edges": edges},
    }


# ─────────────────────────────────────────────────────────────
# Method 변경 영향
# ─────────────────────────────────────────────────────────────


def _method_impact(client: OntologyClient, mid: str) -> dict[str, Any]:
    cypher = (
        "MATCH (m:Method) WHERE m.id = $mid OR m.name = $mid "
        "OPTIONAL MATCH (c:Class)-[:CONTAINS]->(m) "
        "OPTIONAL MATCH (m)-[:CALCULATES]->(s:Step) "
        "RETURN m.name AS method_name, c.name AS class_name, "
        "       collect(DISTINCT {step_number: s.step_number, korean_name: s.korean_name}) AS steps"
    )
    rows = client.query(cypher, mid=mid)
    if not rows or not rows[0]["method_name"]:
        return {
            "method_name": None,
            "class_name": None,
            "direct_steps": [],
            "downstream_steps": [],
            "cypher": cypher,
            "graph": {"nodes": [], "edges": []},
        }
    r = rows[0]
    direct_steps = [s for s in r["steps"] if s.get("step_number") is not None]
    downstream: list[dict] = []
    if direct_steps:
        nums = [s["step_number"] for s in direct_steps]
        d_rows = client.query(
            "MATCH (s:Step) WHERE s.step_number IN $nums "
            "MATCH (s)-[:PRECEDES|DEPENDS_ON*1..3]->(s2:Step) "
            "RETURN DISTINCT s2.step_number AS n, s2.korean_name AS name ORDER BY n",
            nums=nums,
        )
        downstream = [{"step_number": d["n"], "korean_name": d["name"]} for d in d_rows]

    nodes, edges = [], []
    method_node = f"method:{r['class_name']}.{r['method_name']}"
    nodes.append(_node(method_node, f"{r['class_name']}\n.{r['method_name']}()", "method"))
    if r["class_name"]:
        cls_node = f"class:{r['class_name']}"
        nodes.append(_node(cls_node, r["class_name"], "class"))
        edges.append(_edge(cls_node, method_node, "CONTAINS"))
    for s in direct_steps:
        sid = f"step:{s['step_number']}"
        nodes.append(_node(sid, f"Step {s['step_number']}\n{s['korean_name']}", "step"))
        edges.append(_edge(method_node, sid, "CALCULATES"))
    for d in downstream:
        did = f"step:{d['step_number']}"
        if not any(n["id"] == did for n in nodes):
            nodes.append(_node(did, f"Step {d['step_number']}\n{d['korean_name']}", "step"))
        for s in direct_steps:
            edges.append(_edge(f"step:{s['step_number']}", did, "PRECEDES*"))

    return {
        "method_name": r["method_name"],
        "class_name": r["class_name"],
        "direct_steps": direct_steps,
        "downstream_steps": downstream,
        "cypher": cypher,
        "graph": {"nodes": nodes, "edges": edges},
    }


# ─────────────────────────────────────────────────────────────
# Order 변경 영향 — 14 Step 전체 흐름 시뮬레이션
# ─────────────────────────────────────────────────────────────


def _order_impact(client: OntologyClient, order_id: str) -> dict[str, Any]:
    """주문 변경 시 14 Step + 사용 SC + 매핑 Method 모두를 그래프로 표시."""
    cypher = (
        "MATCH (s:Step) "
        "OPTIONAL MATCH (s)-[:USES_STANDARD]->(std:Standard) "
        "OPTIONAL MATCH (m:Method)-[:CALCULATES]->(s) "
        "OPTIONAL MATCH (c:Class)-[:CONTAINS]->(m) "
        "RETURN s.step_number AS n, s.korean_name AS name, "
        "       collect(DISTINCT std.code) AS stds, "
        "       collect(DISTINCT {class: c.name, method: m.name}) AS methods "
        "ORDER BY s.step_number"
    )
    rows = client.query(cypher)
    nodes: list[dict] = []
    edges: list[dict] = []
    order_node = f"order:{order_id}"
    nodes.append(_node(order_node, f"Order\n{order_id}", "order"))

    all_steps = []
    all_stds = set()
    all_methods = []
    for r in rows:
        sid = f"step:{r['n']}"
        nodes.append(_node(sid, f"Step {r['n']}\n{r['name']}", "step"))
        edges.append(_edge(order_node, sid, "TRIGGERS_STEP"))
        all_steps.append({"step_number": r["n"], "korean_name": r["name"]})
        for std in r["stds"]:
            if not std:
                continue
            std_id = f"std:{std}"
            if not any(n["id"] == std_id for n in nodes):
                nodes.append(_node(std_id, std, "standard"))
            edges.append(_edge(sid, std_id, "USES_STANDARD"))
            all_stds.add(std)
        for m in r["methods"]:
            if not m.get("method"):
                continue
            mid = f"method:{m['class']}.{m['method']}"
            if not any(n["id"] == mid for n in nodes):
                nodes.append(_node(mid, f"{m['class']}\n.{m['method']}()", "method"))
            edges.append(_edge(mid, sid, "CALCULATES"))
            all_methods.append({"class": m["class"], "name": m["method"]})

    return {
        "order_id": order_id,
        "all_steps": all_steps,
        "all_standards": sorted(all_stds),
        "all_methods": all_methods,
        "cypher": cypher,
        "graph": {"nodes": nodes, "edges": edges},
    }


# ─────────────────────────────────────────────────────────────
# 위험도 평가
# ─────────────────────────────────────────────────────────────


def _assess_risk(direct: int, downstream: int) -> tuple[str, list[str]]:
    factors: list[str] = []
    if direct >= 5:
        factors.append("직접 영향 5개 이상")
    if downstream >= 3:
        factors.append("다운스트림 Step 3개 이상")
    if direct == 0:
        return "LOW", ["영향 대상 없음"]
    if direct >= 5 or downstream >= 3:
        return "HIGH", factors
    if direct >= 2 or downstream >= 1:
        return "MEDIUM", factors or ["다단계 파급 가능"]
    return "LOW", factors or ["국소적 변경"]


# ─────────────────────────────────────────────────────────────
# 메인 핸들러
# ─────────────────────────────────────────────────────────────


async def analyze(req: OntologyRequest) -> OntologyResponse:
    target = req.parameters.get("target") or {}
    kind = target.get("kind")
    target_id = target.get("id")

    if not kind or not target_id:
        return _missing_target_kind(req)

    if kind not in SUPPORTED_TARGET_KINDS:
        return OntologyResponse(
            request_id=req.request_id,
            status=Status.UNSUPPORTED,
            result={
                "message": f"target.kind '{kind}'는 지원되지 않습니다",
                "supported": sorted(SUPPORTED_TARGET_KINDS),
            },
        )

    client = get_client()

    if kind == "table" or kind == "standard_value":
        impact = _table_impact(client, target_id)
        if impact["table_name"] is None:
            return OntologyResponse(
                request_id=req.request_id,
                status=Status.SUCCESS,
                confidence=0.5,
                result={
                    "summary": f"'{target_id}'에 해당하는 테이블이 그래프에 없습니다",
                    "direct_impact": {"methods": [], "affected_steps": []},
                    "indirect_impact": {"downstream_steps": []},
                    "risk_level": "LOW",
                    "risk_factors": ["대상 미존재"],
                    "ontology_trace": {
                        "nodes": [],
                        "edges": [],
                        "cypher": impact["cypher"],
                    },
                },
            )
        direct_count = len(impact["direct_methods"])
        ds_count = len(impact["downstream_steps"])
        risk, factors = _assess_risk(direct_count, ds_count)
        summary = (
            f"{impact['table_name']} 변경 시 메서드 {direct_count}개, "
            f"Step {len(impact['direct_steps'])}개 직접 영향 "
            f"(다운스트림 Step {ds_count}개)"
        )
        seed_ids = [f"table:{impact['table_name']}"]
        if impact["standard_code"]:
            seed_ids.append(f"std:{impact['standard_code']}")
        return OntologyResponse(
            request_id=req.request_id,
            status=Status.SUCCESS,
            confidence=0.95,
            result={
                "summary": summary,
                "direct_impact": {
                    "methods": impact["direct_methods"],
                    "affected_steps": [
                        {**s, "via_standard": impact["standard_code"]}
                        for s in impact["direct_steps"]
                    ],
                },
                "indirect_impact": {"downstream_steps": impact["downstream_steps"]},
                "risk_level": risk,
                "risk_factors": factors,
                "ontology_trace": {
                    "nodes": impact["graph"]["nodes"],
                    "edges": impact["graph"]["edges"],
                    "seed_ids": seed_ids,
                    "cypher": impact["cypher"],
                },
            },
        )

    if kind == "method":
        impact = _method_impact(client, target_id)
        if impact["method_name"] is None:
            return OntologyResponse(
                request_id=req.request_id,
                status=Status.SUCCESS,
                confidence=0.5,
                result={
                    "summary": f"'{target_id}'에 해당하는 메서드가 그래프에 없습니다",
                    "direct_impact": {"methods": [], "affected_steps": []},
                    "indirect_impact": {"downstream_steps": []},
                    "risk_level": "LOW",
                    "risk_factors": ["대상 미존재"],
                    "ontology_trace": {
                        "nodes": [],
                        "edges": [],
                        "cypher": impact["cypher"],
                    },
                },
            )
        ds_count = len(impact["downstream_steps"])
        risk, factors = _assess_risk(len(impact["direct_steps"]), ds_count)
        return OntologyResponse(
            request_id=req.request_id,
            status=Status.SUCCESS,
            confidence=0.92,
            result={
                "summary": (
                    f"{impact['class_name']}.{impact['method_name']} 변경 시 "
                    f"Step {len(impact['direct_steps'])}개 + 다운스트림 {ds_count}개 영향"
                ),
                "direct_impact": {
                    "methods": [
                        {"class": impact["class_name"], "name": impact["method_name"]}
                    ],
                    "affected_steps": impact["direct_steps"],
                },
                "indirect_impact": {"downstream_steps": impact["downstream_steps"]},
                "risk_level": risk,
                "risk_factors": factors,
                "ontology_trace": {
                    "nodes": impact["graph"]["nodes"],
                    "edges": impact["graph"]["edges"],
                    "seed_ids": [f"method:{impact['class_name']}.{impact['method_name']}"],
                    "cypher": impact["cypher"],
                },
            },
        )

    if kind == "order":
        impact = _order_impact(client, target_id)
        return OntologyResponse(
            request_id=req.request_id,
            status=Status.SUCCESS,
            confidence=0.9,
            result={
                "summary": (
                    f"주문 {target_id} 처리 시 14개 Step 모두 실행, "
                    f"SC 기준 {len(impact['all_standards'])}개, "
                    f"메서드 {len(impact['all_methods'])}개 호출됨"
                ),
                "direct_impact": {
                    "methods": impact["all_methods"],
                    "affected_steps": impact["all_steps"],
                },
                "indirect_impact": {"downstream_steps": []},
                "risk_level": "HIGH",
                "risk_factors": [
                    "주문 1건당 14 Step 전체 실행",
                    f"SC 기준 {len(impact['all_standards'])}개 의존",
                ],
                "ontology_trace": {
                    "nodes": impact["graph"]["nodes"],
                    "edges": impact["graph"]["edges"],
                    "seed_ids": [f"order:{target_id}"],
                    "cypher": impact["cypher"],
                },
            },
        )

    # class / column: 간소화 처리
    return OntologyResponse(
        request_id=req.request_id,
        status=Status.PARTIAL,
        confidence=0.4,
        result={
            "summary": f"target.kind={kind}에 대한 상세 분석은 추후 구현 예정",
            "direct_impact": {"methods": [], "affected_steps": []},
            "indirect_impact": {"downstream_steps": []},
            "risk_level": "LOW",
            "risk_factors": ["미구현 분석 경로"],
            "ontology_trace": {"nodes": [], "edges": [], "cypher": ""},
        },
    )
