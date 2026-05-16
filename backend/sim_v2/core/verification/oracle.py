"""Oracle protocol — ADR-003 §4.

Verification Engine 이 produce, Integrator 가 consume.

Public API:
    - OracleRequest / OracleResult / FixtureOracleResult — pydantic data model
    - OutputDiff / TraceDiff — diff payload
    - FixtureRunner — Protocol implemented by verification engine
    - aggregate_status_from_fixtures — derive 4-tier status from per-fixture results

설계 결정:
- aggregate_status 4-tier: PASS / FAIL_BREAKING / FAIL_DRIFT / INCONCLUSIVE (ADR-003 §4)
- output diff = FAIL_BREAKING (output 의 contract violation)
- trace diff only = FAIL_DRIFT (output 동일하나 처리 과정 다름 — R4 위반)
- error = INCONCLUSIVE
"""
from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

OracleAggregateStatus = Literal["PASS", "FAIL_BREAKING", "FAIL_DRIFT", "INCONCLUSIVE"]
FixtureStatus = Literal["PASS", "FAIL_OUTPUT", "FAIL_TRACE", "ERROR"]


class OutputDiff(BaseModel):
    """Per-fixture output diff (Java baseline vs Python proposal)."""
    model_config = ConfigDict(frozen=True)

    is_equivalent: bool
    diff_path:     list[str] = Field(default_factory=list)
    # JSON-pointer-like path to first divergence

    baseline_value: Any = None
    proposal_value: Any = None
    tolerance:      dict[str, float] = Field(default_factory=dict)
    summary:        str = ""


class TraceDiff(BaseModel):
    """Per-fixture trace diff — Lesson 5 strong version (intermediate values + async)."""
    model_config = ConfigDict(frozen=True)

    is_equivalent:      bool
    diverging_step_no:  int | None = None
    expected_event:     dict[str, Any] | None = None
    actual_event:       dict[str, Any] | None = None
    summary:            str = ""


class FixtureOracleResult(BaseModel):
    """Per-fixture oracle outcome — ADR-003 §4."""
    model_config = ConfigDict(frozen=True)

    fixture_id:             str
    java_baseline_output:   Any
    python_proposal_output: Any
    output_diff:            OutputDiff
    trace_diff:             TraceDiff
    status:                 FixtureStatus
    error:                  str | None = None


class OracleRequest(BaseModel):
    """Verification 호출 input — ADR-003 §4."""
    model_config = ConfigDict(frozen=True)

    proposal_id:    str
    fixture_subset: list[str]
    # FixtureRef list — 어떤 fixture 로 검증?

    apply_schema_diff:   dict[str, Any] | None = None
    apply_code_diff:     dict[str, Any] | None = None
    apply_ontology_diff: dict[str, Any] | None = None


class OracleResult(BaseModel):
    """Oracle aggregate output — Integrator consumes.

    Fuller version of `backend.sim_v2.core.integrator.proposal.OracleResult`
    (which is a placeholder). Integrator's Proposal.oracle_result still uses the
    placeholder type; full result is stored separately if needed.
    """
    model_config = ConfigDict(frozen=True)

    proposal_id:      str
    by_fixture:       dict[str, FixtureOracleResult] = Field(default_factory=dict)
    aggregate_status: OracleAggregateStatus
    summary:          str = ""


class FixtureRunner(Protocol):
    """Plug-in 가 implement — verification engine 이 actual fixture run.

    `backend.sim_v2.core.verification.runner.*` 에서 actual impl (W6+).
    """

    def run_fixture(
        self,
        fixture_id: str,
        plugin: str,
        apply_diffs: dict[str, Any],
    ) -> FixtureOracleResult:
        """Fixture 의 input 으로 Java baseline + Python proposal 실행, diff 수집."""
        ...


def aggregate_status_from_fixtures(
    fixtures: dict[str, FixtureOracleResult],
) -> OracleAggregateStatus:
    """4-tier aggregate status 도출 — ADR-003 §4 의 logic.

    Rules:
    - 모든 fixture PASS → PASS
    - 하나라도 FAIL_OUTPUT → FAIL_BREAKING
    - 하나라도 FAIL_TRACE (no FAIL_OUTPUT) → FAIL_DRIFT
    - 하나라도 ERROR (no FAIL_*) → INCONCLUSIVE
    - 빈 dict → INCONCLUSIVE (검증 안 됨)
    """
    if not fixtures:
        return "INCONCLUSIVE"

    statuses = {r.status for r in fixtures.values()}

    if statuses == {"PASS"}:
        return "PASS"
    if "FAIL_OUTPUT" in statuses:
        return "FAIL_BREAKING"
    if "FAIL_TRACE" in statuses:
        return "FAIL_DRIFT"
    if "ERROR" in statuses:
        return "INCONCLUSIVE"
    return "INCONCLUSIVE"


__all__ = [
    "FixtureOracleResult",
    "FixtureRunner",
    "FixtureStatus",
    "OracleAggregateStatus",
    "OracleRequest",
    "OracleResult",
    "OutputDiff",
    "TraceDiff",
    "aggregate_status_from_fixtures",
]
