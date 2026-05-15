"""VerificationEngine skeleton test — ADR-001 + ADR-003 §4."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.engine import VerificationEngine
from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    FixtureRunner,
    OracleRequest,
    OutputDiff,
    TraceDiff,
)


class _PassFixtureRunner:
    def run_fixture(
        self,
        fixture_id: str,
        plugin: str,
        apply_diffs: dict,
    ) -> FixtureOracleResult:
        return FixtureOracleResult(
            fixture_id=fixture_id,
            java_baseline_output={"x": 1},
            python_proposal_output={"x": 1},
            output_diff=OutputDiff(is_equivalent=True),
            trace_diff=TraceDiff(is_equivalent=True),
            status="PASS",
        )


class _OutputFailRunner:
    def run_fixture(
        self,
        fixture_id: str,
        plugin: str,
        apply_diffs: dict,
    ) -> FixtureOracleResult:
        if fixture_id == "FAIL":
            return FixtureOracleResult(
                fixture_id=fixture_id,
                java_baseline_output={"x": 1},
                python_proposal_output={"x": 2},
                output_diff=OutputDiff(
                    is_equivalent=False,
                    diff_path=["x"],
                    baseline_value=1,
                    proposal_value=2,
                ),
                trace_diff=TraceDiff(is_equivalent=False),
                status="FAIL_OUTPUT",
            )
        return _PassFixtureRunner().run_fixture(fixture_id, plugin, apply_diffs)


class _TraceFailRunner:
    def run_fixture(
        self,
        fixture_id: str,
        plugin: str,
        apply_diffs: dict,
    ) -> FixtureOracleResult:
        return FixtureOracleResult(
            fixture_id=fixture_id,
            java_baseline_output={"x": 1},
            python_proposal_output={"x": 1},
            output_diff=OutputDiff(is_equivalent=True),
            trace_diff=TraceDiff(
                is_equivalent=False,
                diverging_step_no=7,
                summary="trace 발산 at step 7",
            ),
            status="FAIL_TRACE",
        )


class _CrashRunner:
    def run_fixture(
        self,
        fixture_id: str,
        plugin: str,
        apply_diffs: dict,
    ) -> FixtureOracleResult:
        raise RuntimeError("Java baseline NullPointerException")


# ─────────────────────────────────────────────────────────────────────────────
# run_oracle dispatch + aggregate
# ─────────────────────────────────────────────────────────────────────────────


def _request(*fixture_ids: str) -> OracleRequest:
    return OracleRequest(
        proposal_id="prop-1",
        fixture_subset=list(fixture_ids),
        apply_schema_diff={"add_table": "x"},
    )


def test_all_pass():
    engine = VerificationEngine(fixture_runner=_PassFixtureRunner(), plugin="v2-slab-design")
    result = engine.run_oracle(_request("S1", "S2", "S3"))
    assert result.aggregate_status == "PASS"
    assert len(result.by_fixture) == 3
    assert all(r.status == "PASS" for r in result.by_fixture.values())


def test_output_fail_is_breaking():
    engine = VerificationEngine(fixture_runner=_OutputFailRunner(), plugin="v2-slab-design")
    result = engine.run_oracle(_request("OK1", "FAIL", "OK2"))
    assert result.aggregate_status == "FAIL_BREAKING"
    assert result.by_fixture["FAIL"].status == "FAIL_OUTPUT"


def test_trace_only_is_drift():
    engine = VerificationEngine(fixture_runner=_TraceFailRunner(), plugin="v2-slab-design")
    result = engine.run_oracle(_request("S1"))
    assert result.aggregate_status == "FAIL_DRIFT"
    assert result.by_fixture["S1"].trace_diff.diverging_step_no == 7


def test_runner_exception_becomes_error():
    engine = VerificationEngine(fixture_runner=_CrashRunner(), plugin="v2-slab-design")
    result = engine.run_oracle(_request("S1"))
    assert result.aggregate_status == "INCONCLUSIVE"
    assert result.by_fixture["S1"].status == "ERROR"
    assert result.by_fixture["S1"].error is not None
    assert "NullPointerException" in result.by_fixture["S1"].error


def test_request_diffs_forwarded():
    captured: list[dict] = []

    class _CapturingRunner:
        def run_fixture(self, fixture_id, plugin, apply_diffs):
            captured.append(apply_diffs)
            return _PassFixtureRunner().run_fixture(fixture_id, plugin, apply_diffs)

    engine = VerificationEngine(fixture_runner=_CapturingRunner(), plugin="banking")
    engine.run_oracle(OracleRequest(
        proposal_id="p",
        fixture_subset=["BK1"],
        apply_schema_diff={"add_table": "audit_log"},
        apply_code_diff={"refactor": "x"},
    ))
    assert captured[0]["schema"] == {"add_table": "audit_log"}
    assert captured[0]["code"] == {"refactor": "x"}
    assert captured[0]["ontology"] is None


def test_empty_fixture_subset_is_inconclusive():
    engine = VerificationEngine(fixture_runner=_PassFixtureRunner())
    result = engine.run_oracle(_request())
    assert result.aggregate_status == "INCONCLUSIVE"
