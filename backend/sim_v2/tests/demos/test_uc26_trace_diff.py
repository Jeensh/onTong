"""UC26 — Trace-level twin demo verification — W60.3."""
from __future__ import annotations

from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorTwinRunner,
)
from backend.sim_v2.core.verification.engine import VerificationEngine
from backend.sim_v2.core.verification.oracle import OracleRequest
from backend.sim_v2.demos.uc26_trace_diff.run import (
    JAVA_SOURCE,
    build_store,
    main,
    translate,
)


def test_main_returns_zero():
    assert main() == 0


def test_translate_emits_trace_steps_when_with_trace():
    src = translate(with_trace=True)
    assert "_trace.step" in src


def test_translate_no_trace_when_with_trace_false():
    src = translate(with_trace=False)
    assert "_trace.step" not in src


def test_build_store_has_four_fixtures():
    store = build_store()
    ids = set(store.ids())
    assert ids == {"pass.7", "fail_output.7", "fail_trace.7", "error.boom"}


def _run_single(fid: str):
    store = build_store()
    engine = VerificationEngine(
        fixture_runner=BehaviorTwinRunner(store), plugin="t",
    )
    req = OracleRequest(proposal_id=f"uc26.{fid}", fixture_subset=[fid])
    return engine.run_oracle(req)


def test_pass_fixture_yields_pass():
    result = _run_single("pass.7")
    assert result.aggregate_status == "PASS"
    fixture_result = result.by_fixture["pass.7"]
    assert fixture_result.status == "PASS"
    assert fixture_result.trace_diff.is_equivalent


def test_fail_output_fixture_yields_fail_breaking():
    result = _run_single("fail_output.7")
    assert result.aggregate_status == "FAIL_BREAKING"
    assert result.by_fixture["fail_output.7"].status == "FAIL_OUTPUT"


def test_fail_trace_fixture_yields_fail_drift():
    result = _run_single("fail_trace.7")
    assert result.aggregate_status == "FAIL_DRIFT"
    fixture_result = result.by_fixture["fail_trace.7"]
    assert fixture_result.status == "FAIL_TRACE"
    assert not fixture_result.trace_diff.is_equivalent
    assert fixture_result.trace_diff.diverging_step_no == 0


def test_error_fixture_yields_inconclusive():
    result = _run_single("error.boom")
    assert result.aggregate_status == "INCONCLUSIVE"
    assert result.by_fixture["error.boom"].status == "ERROR"


def test_java_source_well_formed():
    assert "doubleIt" in JAVA_SOURCE
