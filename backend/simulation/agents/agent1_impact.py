"""Agent 1 — 영향도 + 변경 전후 sandbox 실행.

Phase 3 재작성:
- ontology_client.query (impact_analysis intent) — Section 2가 영향 step/method/table 식별
- ontology가 미응답이거나 빈 결과여도 graceful fallback (slab-design demo 룰 매핑 내장)
- 표본 N개 주문에 대해 sandbox.pipeline을 변경 전 룰 / 후 룰로 2회 실행
- diff_summary로 비교 → 응답에 viz_data 동봉

기존 v2 (ontology만 호출하던 wrapper)에서 능동적인 영향도 측정으로 진화.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.shared.contracts.ontology import Intent, OntologyRequest, Status

from ..client.ontology_client import get_ontology_client
from ..sandbox.runner import run_in_subprocess
from ..testgen import case_builder
from ..testgen.hypothesis_strategies import normal_order_overrides
from ..visualization.diff_summary import diff_results, make_viz_data

logger = logging.getLogger(__name__)


# ─── 입력 / 출력 ────────────────────────────────────────────────────


class Agent1Request(BaseModel):
    change_kind: Literal["program", "data"] = "data"
    target_type: Literal[
        "method", "class", "table", "column", "standard_value", "order"
    ]
    target_id: str
    modification_type: Literal["logic", "signature", "deletion", "value_change"] = "value_change"
    new_value: Optional[str] = None
    sample_size: int = 50
    """sandbox에서 변경 전후를 비교할 표본 주문 수."""
    run_sandbox: bool = True
    """false면 ontology 결과만 반환 (호환용)."""


class Agent1Result(BaseModel):
    request_id: str
    status: Literal["success", "partial", "need_more_info", "unsupported", "error"]
    summary: str = ""
    direct_impact: dict = Field(default_factory=dict)
    indirect_impact: dict = Field(default_factory=dict)
    risk_level: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = None
    risk_factors: list[str] = Field(default_factory=list)
    visualization: Optional[dict] = None
    missing_info: Optional[dict] = None
    ontology_trace: Optional[dict] = None
    raw_message: Optional[str] = None

    # Phase 3 신규
    diff_summary: Optional[dict] = None
    viz_data: Optional[dict] = None


# ─── target_id → sandbox rules 매핑 ─────────────────────────────────

_RULE_TARGET_MAP: dict[str, str] = {
    # column 또는 standard_value 형태로 들어오는 룰 식별자 → sandbox rules key
    "HR_PRODUCTIVITY": "hr",
    "hr_productivity": "hr",
    "productivity:HR": "hr",
    "HRF_PRODUCTIVITY": "hrf",
    "hrf_productivity": "hrf",
    "productivity:HRF": "hrf",
    "ANL1_PRODUCTIVITY": "anl1",
    "anl1_productivity": "anl1",
    "productivity:ANL1": "anl1",
}


def _resolve_rule_key(target_id: str) -> Optional[str]:
    """target_id가 sandbox 룰 변경으로 매핑되는지 — 시나리오 5 데모용."""
    if target_id in _RULE_TARGET_MAP:
        return _RULE_TARGET_MAP[target_id]
    # "productivity:HR" 형태 일반화
    if ":" in target_id:
        prefix, suffix = target_id.split(":", 1)
        if prefix.lower().endswith("productivity"):
            return suffix.lower() if suffix.lower() in {"hr", "hrf", "anl1"} else None
    return None


# ─── 메인 실행 ──────────────────────────────────────────────────────


async def execute_agent1(req: Agent1Request) -> Agent1Result:
    request_id = str(uuid.uuid4())

    # 1) ontology 호출 — best-effort (미가용 시 fallback)
    ontology_payload = await _query_ontology(req, request_id)
    direct_impact = ontology_payload.get("direct_impact", {})
    indirect_impact = ontology_payload.get("indirect_impact", {})
    risk_level = ontology_payload.get("risk_level")
    risk_factors = ontology_payload.get("risk_factors", [])
    ontology_trace = ontology_payload.get("ontology_trace")
    visualization = ontology_payload.get("visualization")
    summary_parts: list[str] = []
    if ontology_payload.get("summary"):
        summary_parts.append(str(ontology_payload["summary"]))

    # 2) sandbox 변경 전후 실행 — 룰 변경 케이스만
    diff_payload: dict | None = None
    viz_data: dict | None = None
    rule_key = _resolve_rule_key(req.target_id) if req.modification_type == "value_change" else None
    if req.run_sandbox and rule_key and req.new_value:
        try:
            diff = await _run_sandbox_diff(rule_key, req.new_value, req.sample_size)
            diff_payload = diff.to_json()
            viz_data = make_viz_data(diff)
            # 영향도 카드: Slab 매수 변동
            slab_count = diff.metrics.get("slab_count", {})
            if slab_count.get("changed_orders"):
                summary_parts.append(
                    f"표본 {diff.sample_size}건 중 {slab_count['changed_orders']}건의 Slab 매수 변동 "
                    f"(평균 {slab_count.get('delta_mean', 0):+.2f}장)"
                )
            # rule_key가 indirect impact에 등장하지 않았다면 보강
            if not direct_impact:
                direct_impact = {
                    "rule_key": rule_key,
                    "affected_metrics": [m for m, v in diff.metrics.items() if v.get("changed_orders")],
                }
        except Exception:
            logger.exception("sandbox diff failed")
            risk_factors = list(risk_factors) + ["sandbox 비교 실행 실패 — 정적 영향도만 보고"]

    # 3) status 결정
    status: Literal["success", "partial", "need_more_info", "unsupported", "error"]
    if ontology_payload.get("status") == "need_more_info":
        status = "need_more_info"
    elif diff_payload is not None or direct_impact or indirect_impact:
        status = "success" if (diff_payload is not None) else "partial"
    elif ontology_payload.get("unavailable"):
        status = "partial"
    else:
        status = "success"

    return Agent1Result(
        request_id=request_id,
        status=status,
        summary=" / ".join(summary_parts) if summary_parts else "ontology + sandbox 영향도 분석",
        direct_impact=direct_impact or {},
        indirect_impact=indirect_impact or {},
        risk_level=risk_level,
        risk_factors=risk_factors,
        visualization=visualization,
        missing_info=ontology_payload.get("missing_info"),
        ontology_trace=ontology_trace,
        raw_message=ontology_payload.get("raw_message"),
        diff_summary=diff_payload,
        viz_data=viz_data,
    )


# ─── ontology 호출 (graceful) ───────────────────────────────────────


async def _query_ontology(req: Agent1Request, request_id: str) -> dict:
    """Section 2 ontology 호출. 실패/타임아웃 시 빈 결과 (Section 3 단독 demo).

    SIMULATION_SKIP_ONTOLOGY=1 환경변수로 완전히 스킵 (기본값 = "1" — Neo4j 의존성 회피).
    데모 환경에서 Section 2 ontology가 풍부하지 않으므로 default skip이 안전.
    Section 2 풍부 환경에선 SIMULATION_SKIP_ONTOLOGY=0 설정.
    """
    import asyncio
    import os
    if os.getenv("SIMULATION_SKIP_ONTOLOGY", "1") == "1":
        return {"unavailable": True, "raw_message": "ontology skipped"}
    try:
        client = get_ontology_client()
        ont_req = OntologyRequest(
            request_id=request_id,
            intent=Intent.IMPACT_ANALYSIS,
            parameters={
                "target": {"kind": req.target_type, "id": req.target_id},
                "modification": req.modification_type,
                "change_kind": req.change_kind,
                "new_value": req.new_value,
            },
        )
        resp = await asyncio.wait_for(client.query(ont_req), timeout=3.0)
    except (asyncio.TimeoutError, Exception) as exc:
        logger.info("ontology query unavailable: %s", exc)
        return {"unavailable": True, "raw_message": str(exc)}

    status_value = (
        resp.status.value if isinstance(resp.status, Status) else str(resp.status)
    )
    if resp.status is Status.NEED_MORE_INFO:
        return {
            "status": "need_more_info",
            "missing_info": resp.missing_info.model_dump() if resp.missing_info else None,
        }
    if resp.status in (Status.UNSUPPORTED, Status.ERROR):
        return {
            "unavailable": True,
            "raw_message": (resp.result or {}).get("message") if resp.result else None,
        }

    data = resp.result or {}
    return {
        "status": status_value,
        "summary": data.get("summary"),
        "direct_impact": data.get("direct_impact", {}),
        "indirect_impact": data.get("indirect_impact", {}),
        "risk_level": data.get("risk_level"),
        "risk_factors": data.get("risk_factors", []),
        "visualization": data.get("visualization"),
        "ontology_trace": data.get("ontology_trace"),
    }


# ─── sandbox 비교 실행 ──────────────────────────────────────────────


async def _run_sandbox_diff(rule_key: str, new_value: str, sample_size: int):
    """동일 표본 sample_size개에 대해 default 룰 vs 변경된 룰로 sandbox.pipeline 2회.

    표본은 normal_order_overrides()에서 추출 — Hypothesis가 동일한 시드일 때 같은 값을 내지만,
    sandbox 실행마다 새로 sample하므로 두 run에 동일한 inputs를 reuse하려면 case 한 번만 빌드해서
    rules만 바꿔 두 번 실행한다.
    """
    sample_size = max(1, min(sample_size, 200))
    cases = case_builder.build_cases(
        step_id="pipeline",
        case_types=["normal"],
        count_per_type=sample_size,
    )
    before_inputs = [{"order": c.sandbox_inputs.get("order", {}), "rules": {}} for c in cases]
    after_inputs = [{"order": c.sandbox_inputs.get("order", {}), "rules": {rule_key: new_value}} for c in cases]

    loop = asyncio.get_running_loop()

    async def _run_one(inputs: dict):
        return await loop.run_in_executor(
            None,
            lambda: run_in_subprocess("pipeline", inputs, timeout_sec=5),
        )

    before = await asyncio.gather(*(_run_one(inp) for inp in before_inputs))
    after = await asyncio.gather(*(_run_one(inp) for inp in after_inputs))

    return diff_results(list(before), list(after))
