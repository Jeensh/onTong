"""Phase 2 Step 4c — Gate III sim handler.

Gate II 의 GateBundle → run fixtures in-process + W74 stubs + W72 invariant aggregation
→ `GateExecutedSimulation` payload.

deterministic re-synthesis 의 정합성: W71 (synthesize_fixtures) 는 같은 입력 →
같은 출력. Gate II 가 만든 BehaviorFixture 와 Gate III 가 다시 만든 것은 동일.
GateBundle 의 `fixtures: list[FixtureRow]` 는 표시용 (JSON serializable), 실
실행은 sim_v2 BehaviorFixture (Python) 가 필요하므로 재합성.
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Any

from .schemas import (
    CaseResult,
    GateBundle,
    GateExecutedSimulation,
    InvariantStatus,
    Provenance,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


async def build_gate_iii_sim(
    *,
    bundle: GateBundle,
    repo_id: str,
) -> GateExecutedSimulation:
    """Gate III sim 결과 = `GateExecutedSimulation` payload.

    Pipeline:
      1) action = sim_v2.load_action(target.action_id)
      2) function_name = _extract_function_name(bundle.python_source)
      3) fixtures = sim_v2.synthesize_fixtures(action, function_name, python_source)
      4) stubs = sim_v2.build_stubs(method_fqn, repo_id, python_source)
      5) case_dicts = sim_v2.run_fixtures_in_process(fixtures, stub_namespace=stubs)
      6) results = [_to_case_result(d) for d in case_dicts]
      7) invariant_status = _aggregate_invariant(results)
    """
    if not bundle.python_source:
        return _error_payload("python_source 없음 — Gate II 결과 미완성")

    function_name = _extract_function_name(bundle.python_source)
    if not function_name:
        return _error_payload("python_source 의 function 정의 추출 실패")

    pipeline = await asyncio.to_thread(
        _run_sim_pipeline_sync,
        bundle.target.action_id,
        bundle.target.code_method_fqn,
        repo_id,
        bundle.python_source,
        function_name,
    )
    case_dicts, fail_reason, stub_count = pipeline

    if case_dicts is None:
        return _error_payload(fail_reason or "sim pipeline 실패")

    results = [_to_case_result(d) for d in case_dicts]
    invariant_status = _aggregate_invariant_from_dicts(case_dicts)
    sources = [
        Provenance(
            source="sim_v2",
            detail=(
                f"run_fixtures_in_process(cases={len(results)}, "
                f"stubs={stub_count}, target={bundle.target.code_method_fqn})"
            ),
            confidence=1.0 if invariant_status == "clean" else 0.6,
        ),
    ]
    return GateExecutedSimulation(
        results=results,
        invariant_status=invariant_status,
        baseline_diff=None,
        sources=sources,
    )


# ─────────────────────────────────────────────────────────────────────────────
# sim_v2 pipeline (sync, asyncio.to_thread wrapped)
# ─────────────────────────────────────────────────────────────────────────────


def _run_sim_pipeline_sync(
    action_id: str,
    code_method_fqn: str,
    repo_id: str,
    python_source: str,
    function_name: str,
) -> tuple[list[dict[str, Any]] | None, str | None, int]:
    """Returns (case_dicts, failure_reason, stub_count). case_dicts=None on failure."""
    from backend.section3 import sim_v2_bridge as sb

    s = sb.open_sim_v2_session()
    if s is None:
        return None, "sim_v2 session 열기 실패", 0
    try:
        action = sb.load_action(s, action_id, repo_id)
        if action is None:
            return None, f"action 못 찾음 (action_id={action_id!r})", 0

        report = sb.synthesize_fixtures(
            s, action, function_name=function_name, python_source=python_source,
        )
        if report is None or not getattr(report, "fixtures", None):
            return None, "fixture 합성 실패 또는 빈 결과", 0

        stubs = sb.build_stubs(
            s,
            method_fqn=code_method_fqn,
            repo_id=repo_id,
            python_source=python_source,
        )

        case_dicts = sb.run_fixtures_in_process(
            list(report.fixtures), stub_namespace=stubs,
        )
        return case_dicts, None, len(stubs)
    finally:
        s.close()


# ─────────────────────────────────────────────────────────────────────────────
# Conversion + aggregation
# ─────────────────────────────────────────────────────────────────────────────


_FAIL_INVARIANT_MAP: dict[str, InvariantStatus] = {
    "PASS": "clean",  # not actually a failure, but easy mapping
    "FAIL_NONDETERMINISTIC": "fail_nondeterministic",
    "FAIL_UNEXPECTED_THROW": "fail_unexpected_throw",
    "FAIL_RETURN_TYPE": "fail_return_type",
    "ERROR": "error",
}


def _to_case_result(d: dict[str, Any]) -> CaseResult:
    """sim_v2 case_result dict → Pydantic CaseResult."""
    raw_status = str(d.get("invariant_status", "")).upper()
    if raw_status == "PASS":
        status = "PASS"
    elif raw_status.startswith("FAIL"):
        status = "FAIL"
    elif raw_status == "ERROR":
        status = "ERROR"
    elif raw_status == "SKIPPED":
        status = "SKIPPED"
    else:
        status = "ERROR"

    execution = d.get("execution") or {}
    inner = execution.get("result") or {}
    output = inner.get("result")
    error = execution.get("error")
    error_class = None
    if error and not isinstance(error, str):
        error = str(error)
    return CaseResult(
        fixture_id=str(d.get("case_id", "")),
        status=status,
        output=output,
        error_class=error_class,
        error_message=error,
    )


def _aggregate_invariant_from_dicts(case_dicts: list[dict[str, Any]]) -> InvariantStatus:
    """모두 PASS → clean. 아니면 가장 빈번한 invariant_status 를 schema 의 fail_* 로 매핑.

    sim_v2 의 raw invariant_status (PASS / FAIL_NONDETERMINISTIC / FAIL_UNEXPECTED_THROW /
    FAIL_RETURN_TYPE / ERROR) 을 직접 사용.
    """
    if not case_dicts:
        return "error"
    raw_list = [str(d.get("invariant_status", "")).upper() for d in case_dicts]
    if all(s == "PASS" for s in raw_list):
        return "clean"

    failures = [_FAIL_INVARIANT_MAP.get(s, "error") for s in raw_list if s != "PASS"]
    if not failures:
        return "error"
    dominant = Counter(failures).most_common(1)[0][0]
    return dominant  # type: ignore[return-value]


def _extract_function_name(python_source: str) -> str:
    """def NAME(...) 의 NAME 추출. method 형태 (def f(self, ...)) 도 OK."""
    for line in python_source.splitlines():
        stripped = line.strip()
        if stripped.startswith("def "):
            head = stripped[4:].split("(", 1)[0].strip()
            return head
    return ""


def _error_payload(reason: str) -> GateExecutedSimulation:
    return GateExecutedSimulation(
        results=[],
        invariant_status="error",
        baseline_diff=None,
        sources=[
            Provenance(
                source="sim_v2",
                detail=f"Gate III sim aborted — {reason}",
                confidence=0.0,
            ),
        ],
    )


__all__ = ["build_gate_iii_sim"]
