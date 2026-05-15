"""Oracle protocol test — ADR-003 §4."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    OracleRequest,
    OracleResult,
    OutputDiff,
    TraceDiff,
    aggregate_status_from_fixtures,
)


def _make_fixture_result(
    fixture_id: str,
    status: str,
    output_equal: bool = True,
    trace_equal: bool = True,
) -> FixtureOracleResult:
    return FixtureOracleResult(
        fixture_id=fixture_id,
        java_baseline_output={"x": 1},
        python_proposal_output={"x": 1},
        output_diff=OutputDiff(is_equivalent=output_equal),
        trace_diff=TraceDiff(is_equivalent=trace_equal),
        status=status,
    )


def test_oracle_request_serialize():
    req = OracleRequest(
        proposal_id="prop-1",
        fixture_subset=["S1", "S2"],
        apply_schema_diff={"add_table": "audit"},
    )
    payload = req.model_dump_json()
    assert "prop-1" in payload
    revived = OracleRequest.model_validate_json(payload)
    assert revived.fixture_subset == ["S1", "S2"]


def test_aggregate_status_all_pass():
    fixtures = {
        "S1": _make_fixture_result("S1", "PASS"),
        "S2": _make_fixture_result("S2", "PASS"),
    }
    assert aggregate_status_from_fixtures(fixtures) == "PASS"


def test_aggregate_status_breaking_takes_priority():
    fixtures = {
        "S1": _make_fixture_result("S1", "PASS"),
        "S2": _make_fixture_result("S2", "FAIL_OUTPUT", output_equal=False),
        "S3": _make_fixture_result("S3", "FAIL_TRACE", trace_equal=False),
    }
    assert aggregate_status_from_fixtures(fixtures) == "FAIL_BREAKING"


def test_aggregate_status_drift_when_only_trace_diff():
    fixtures = {
        "S1": _make_fixture_result("S1", "PASS"),
        "S2": _make_fixture_result("S2", "FAIL_TRACE", trace_equal=False),
    }
    assert aggregate_status_from_fixtures(fixtures) == "FAIL_DRIFT"


def test_aggregate_status_inconclusive_on_error():
    fixtures = {
        "S1": _make_fixture_result("S1", "PASS"),
        "S2": FixtureOracleResult(
            fixture_id="S2",
            java_baseline_output=None,
            python_proposal_output=None,
            output_diff=OutputDiff(is_equivalent=False),
            trace_diff=TraceDiff(is_equivalent=False),
            status="ERROR",
            error="Java baseline crashed: NullPointerException",
        ),
    }
    assert aggregate_status_from_fixtures(fixtures) == "INCONCLUSIVE"


def test_aggregate_status_inconclusive_on_empty():
    assert aggregate_status_from_fixtures({}) == "INCONCLUSIVE"


def test_oracle_result_with_full_payload():
    result = OracleResult(
        proposal_id="prop-1",
        by_fixture={
            "S1": _make_fixture_result("S1", "PASS"),
            "S2": _make_fixture_result("S2", "FAIL_TRACE", trace_equal=False),
        },
        aggregate_status="FAIL_DRIFT",
        summary="trace diverges at step 7 (a-a loop fallback)",
    )
    payload = result.model_dump_json()
    assert "FAIL_DRIFT" in payload
    revived = OracleResult.model_validate_json(payload)
    assert revived.aggregate_status == "FAIL_DRIFT"
    assert len(revived.by_fixture) == 2


def test_output_diff_immutable():
    diff = OutputDiff(is_equivalent=True)
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        diff.is_equivalent = False
