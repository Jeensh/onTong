"""Agent 2 (테스트 데이터 생성) 쿼리.

Intent ``simulate`` 핸들러. Step / Method / Standard 기준으로 입출력 변수와
valid_range를 그래프에서 추출하여 normal/boundary/error 케이스를 생성한다.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..client import OntologyClient, get_client
from backend.shared.contracts.ontology import (
    OntologyRequest,
    OntologyResponse,
    Status,
)

logger = logging.getLogger(__name__)

ALLOWED_CASE_TYPES = {"normal", "boundary", "error", "performance"}


def _parse_range(valid_range: str | None) -> tuple[float, float] | None:
    """'[200, 310]' → (200.0, 310.0)."""
    if not valid_range:
        return None
    m = re.match(r"\s*\[\s*([0-9.+\-eE]+)\s*,\s*([0-9.+\-eE]+)\s*\]\s*", valid_range)
    if not m:
        return None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None


def _step_inputs_outputs(
    client: OntologyClient, step_number: int
) -> dict[str, list[dict]]:
    rows = client.query(
        "MATCH (s:Step {step_number: $n}) "
        "OPTIONAL MATCH (s)-[:REQUIRES_INPUT]->(i:Variable) "
        "OPTIONAL MATCH (s)-[:PRODUCES_OUTPUT]->(o:Variable) "
        "OPTIONAL MATCH (s)-[:USES_STANDARD]->(std:Standard) "
        "OPTIONAL MATCH (s)-[:TRIGGERS_ON_FAIL]->(e:ErrorCode) "
        "RETURN collect(DISTINCT {id: i.id, name: i.name, type: i.type, "
        "                          unit: i.unit, valid_range: i.valid_range}) AS inputs, "
        "       collect(DISTINCT {id: o.id, name: o.name, type: o.type}) AS outputs, "
        "       collect(DISTINCT std.code) AS standards, "
        "       collect(DISTINCT {code: e.code, message: e.korean_message}) AS errors",
        n=step_number,
    )
    if not rows:
        return {"inputs": [], "outputs": [], "standards": [], "errors": []}
    r = rows[0]
    return {
        "inputs": [v for v in r["inputs"] if v.get("name")],
        "outputs": [v for v in r["outputs"] if v.get("name")],
        "standards": [s for s in r["standards"] if s],
        "errors": [e for e in r["errors"] if e.get("code")],
    }


def _generate_value(var: dict, mode: str) -> Any:
    """valid_range 기반 normal/boundary/error 값 생성."""
    rng = _parse_range(var.get("valid_range"))
    var_type = var.get("type", "integer")

    if rng:
        lo, hi = rng
        if mode == "normal":
            return int((lo + hi) / 2) if var_type == "integer" else (lo + hi) / 2
        if mode == "boundary_low":
            return int(lo) if var_type == "integer" else lo
        if mode == "boundary_high":
            return int(hi) if var_type == "integer" else hi
        if mode == "error":
            # 범위 밖 값
            return int(hi + (hi - lo) * 0.1) if var_type == "integer" else hi + 1.0
    # fallback by type
    defaults = {
        "integer": {"normal": 100, "boundary_low": 0, "boundary_high": 1000, "error": -1},
        "float": {"normal": 1.0, "boundary_low": 0.0, "boundary_high": 10.0, "error": -1.0},
        "range": {"normal": [100, 200], "boundary_low": [0, 0], "boundary_high": [9999, 9999], "error": [-1, -1]},
        "enum": {"normal": "DEFAULT", "boundary_low": "MIN", "boundary_high": "MAX", "error": "INVALID"},
    }
    return defaults.get(var_type, defaults["integer"]).get(mode, 0)


def _build_test_cases(
    inputs: list[dict],
    case_types: list[str],
    count: int,
    error_codes: list[dict],
) -> list[dict]:
    cases: list[dict] = []
    case_idx = 1
    for case_type in case_types:
        per_type_count = max(1, count // max(1, len(case_types)))
        for i in range(per_type_count):
            input_data: dict[str, Any] = {}
            if case_type == "normal":
                mode = "normal"
            elif case_type == "boundary":
                mode = "boundary_low" if i % 2 == 0 else "boundary_high"
            elif case_type == "error":
                mode = "error"
            else:
                mode = "normal"
            for var in inputs:
                input_data[var["name"]] = _generate_value(var, mode)
            cases.append(
                {
                    "case_id": f"TC{case_idx:03d}",
                    "case_type": case_type,
                    "description": f"{case_type} 케이스 #{i + 1}",
                    "input": input_data,
                    "expected_output": (
                        {"error_code": error_codes[0]["code"]}
                        if case_type == "error" and error_codes
                        else {"feasible": True}
                    ),
                }
            )
            case_idx += 1
            if case_idx > count + 1:
                break
        if case_idx > count + 1:
            break
    return cases[:count] if count > 0 else cases


def _code_skeleton(target_id: str, cases: list[dict]) -> str:
    lines = ["// Auto-generated JUnit skeleton (Agent 2)", "import org.junit.jupiter.api.Test;", ""]
    for c in cases:
        method_name = f"test_{target_id}_{c['case_id'].lower()}"
        lines.append("@Test")
        lines.append(f"void {method_name}() {{")
        lines.append(f"    // case_type: {c['case_type']}")
        lines.append("    // TODO: implement assertion using inputs above")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


async def generate(req: OntologyRequest) -> OntologyResponse:
    """simulate intent 핸들러 (test_data_request 모드 위주)."""
    target = req.parameters.get("target") or {}
    kind = target.get("kind")
    target_id = target.get("id", "")

    test_req = req.parameters.get("test_data_request") or {}
    case_types_raw = test_req.get("case_types", ["normal", "boundary", "error"])
    case_types = [t for t in case_types_raw if t in ALLOWED_CASE_TYPES]
    count = int(test_req.get("count", 5))

    if kind != "step":
        return OntologyResponse(
            request_id=req.request_id,
            status=Status.UNSUPPORTED,
            result={
                "message": f"target.kind={kind}에 대한 테스트 데이터 생성은 미구현 (현재는 step만 지원)",
                "supported": ["step"],
            },
        )

    # 'step_2' → 2
    if isinstance(target_id, str) and target_id.startswith("step_"):
        try:
            step_number = int(target_id.split("_", 1)[1])
        except ValueError:
            return OntologyResponse(
                request_id=req.request_id,
                status=Status.ERROR,
                result={"message": f"잘못된 step id: {target_id}"},
            )
    else:
        try:
            step_number = int(target_id)
        except (TypeError, ValueError):
            return OntologyResponse(
                request_id=req.request_id,
                status=Status.ERROR,
                result={"message": f"잘못된 target.id: {target_id}"},
            )

    client = get_client()
    info = _step_inputs_outputs(client, step_number)
    if not info["inputs"] and not info["outputs"]:
        return OntologyResponse(
            request_id=req.request_id,
            status=Status.SUCCESS,
            confidence=0.5,
            result={
                "summary": f"Step {step_number}에 등록된 입출력 변수가 없습니다",
                "test_cases": [],
                "code_skeleton": "",
                "data_dependencies": [],
            },
        )

    cases = _build_test_cases(info["inputs"], case_types, count, info["errors"])
    skeleton = _code_skeleton(f"step{step_number}", cases)

    # data_dependencies: 사용 SC → 매핑된 Table
    data_deps: list[str] = []
    if info["standards"]:
        rows = client.query(
            "MATCH (t:Table)-[:MAPS_TO_STANDARD]->(s:Standard) "
            "WHERE s.code IN $codes "
            "RETURN t.name AS name",
            codes=info["standards"],
        )
        data_deps = [r["name"] for r in rows]

    # 그래프 trace — Step + 입출력 Variable + 사용 SC
    nodes: list[dict] = [
        {
            "id": f"step:{step_number}",
            "label": f"Step {step_number}",
            "group": "step",
        }
    ]
    edges: list[dict] = []
    for v in info["inputs"]:
        vid = f"variable:{v['id']}"
        nodes.append({"id": vid, "label": v.get("korean_name", v["name"]), "group": "variable"})
        edges.append({"from": f"step:{step_number}", "to": vid, "label": "REQUIRES_INPUT"})
    for v in info["outputs"]:
        vid = f"variable:{v['id']}"
        if not any(n["id"] == vid for n in nodes):
            nodes.append({"id": vid, "label": v.get("name", ""), "group": "variable"})
        edges.append({"from": f"step:{step_number}", "to": vid, "label": "PRODUCES_OUTPUT"})
    for sc in info["standards"]:
        sid = f"standard:{sc}"
        nodes.append({"id": sid, "label": sc, "group": "standard"})
        edges.append({"from": f"step:{step_number}", "to": sid, "label": "USES_STANDARD"})
    for ec in info["errors"]:
        eid = f"errorcode:{ec['code']}"
        nodes.append({"id": eid, "label": f"{ec['code']}\n{ec.get('message', '')}", "group": "errorcode"})
        edges.append({"from": f"step:{step_number}", "to": eid, "label": "TRIGGERS_ON_FAIL"})

    cypher = (
        f"MATCH (s:Step {{step_number: {step_number}}}) "
        "OPTIONAL MATCH (s)-[:REQUIRES_INPUT]->(i:Variable) "
        "OPTIONAL MATCH (s)-[:PRODUCES_OUTPUT]->(o:Variable) "
        "OPTIONAL MATCH (s)-[:USES_STANDARD]->(std:Standard) "
        "OPTIONAL MATCH (s)-[:TRIGGERS_ON_FAIL]->(e:ErrorCode)"
    )

    return OntologyResponse(
        request_id=req.request_id,
        status=Status.SUCCESS,
        confidence=0.85,
        result={
            "summary": (
                f"Step {step_number} 대상 {len(cases)}개 테스트 케이스 생성 "
                f"(입력 변수 {len(info['inputs'])}개)"
            ),
            "test_cases": cases,
            "code_skeleton": skeleton,
            "data_dependencies": data_deps,
            "ontology_trace": {
                "nodes": nodes,
                "edges": edges,
                "seed_ids": [f"step:{step_number}"],
                "cypher": cypher,
            },
        },
    )
