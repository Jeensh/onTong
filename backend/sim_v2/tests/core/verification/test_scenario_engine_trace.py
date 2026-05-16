"""ScenarioVerificationEngine trace capture tests — W16.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.oracle import OracleRequest
from backend.sim_v2.core.verification.scenario_engine import (
    Scenario,
    ScenarioVerificationEngine,
)
from backend.sim_v2.core.verification.trace import TraceCollector


# ─────────────────────────────────────────────────────────────────────────────
# Simulated translated_fn that calls _trace from globals
# ─────────────────────────────────────────────────────────────────────────────


def _make_traced_fn(source: str):
    """Build a translated_fn with _trace placeholder in its globals."""
    globals_dict = {"_trace": None}
    exec(source, globals_dict)
    return globals_dict["fn"], globals_dict


def test_trace_disabled_no_events_captured():
    src = "def fn(x): _trace.step('a', {'x': x}); return x + 1"
    fn, _ = _make_traced_fn(src)
    # baseline = identity (no trace)
    baseline = lambda x: x + 1
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=6)}
    engine = ScenarioVerificationEngine(fn, baseline, fixtures, with_trace=False)
    # with_trace=False: engine doesn't inject _trace, fn would crash if it tried.
    # We work around by using a fn that doesn't actually call _trace.
    src_no_trace = "def fn(x): return x + 1"
    fn2, _ = _make_traced_fn(src_no_trace)
    engine.translated_fn = fn2
    engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    assert engine.last_traces == {}


def test_trace_enabled_captures_events():
    src = "def fn(x):\n    _trace.step('a', {'x': x})\n    return x + 1"
    fn, _ = _make_traced_fn(src)
    baseline = lambda x: x + 1
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=6)}
    engine = ScenarioVerificationEngine(fn, baseline, fixtures, with_trace=True)
    engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    assert "F" in engine.last_traces
    events = engine.last_traces["F"]
    assert len(events) == 1
    assert events[0].anchor_id == "a"
    assert dict(events[0].vars) == {"x": 5}


def test_trace_diff_summary_records_length_mismatch():
    """W17: trace_diff summary records cross-side compare result.

    With translated emitting 2 events and baseline emitting 0, diff_traces
    reports a length mismatch.
    """
    src = (
        "def fn(x):\n"
        "    _trace.step('a1', {'x': x})\n"
        "    _trace.step('a2', {'y': x * 2})\n"
        "    return x"
    )
    fn, _ = _make_traced_fn(src)
    baseline = lambda x: x
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=5)}
    engine = ScenarioVerificationEngine(fn, baseline, fixtures, with_trace=True)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    trace_diff = result.by_fixture["F"].trace_diff
    assert "length mismatch" in trace_diff.summary
    # Trace not equivalent → status should be FAIL_TRACE (even though output matched)
    assert result.by_fixture["F"].status == "FAIL_TRACE"
    assert result.aggregate_status == "FAIL_DRIFT"


def test_trace_disabled_summary_records_disabled():
    src = "def fn(x): return x"
    fn, _ = _make_traced_fn(src)
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=5)}
    engine = ScenarioVerificationEngine(fn, lambda x: x, fixtures, with_trace=False)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    trace_diff = result.by_fixture["F"].trace_diff
    assert trace_diff.summary == "trace capture disabled"


def test_fresh_collector_per_fixture():
    """Two fixtures run in same engine should have independent traces."""
    src = (
        "def fn(x):\n"
        "    _trace.step('a', {'x': x})\n"
        "    return x"
    )
    fn, _ = _make_traced_fn(src)
    fixtures = {
        "F1": Scenario("F1", {"x": 1}, expected_output=1),
        "F2": Scenario("F2", {"x": 2}, expected_output=2),
    }
    engine = ScenarioVerificationEngine(fn, lambda x: x, fixtures, with_trace=True)
    engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1", "F2"]))
    # Each fixture gets its own trace — F1 saw x=1, F2 saw x=2
    assert dict(engine.last_traces["F1"][0].vars) == {"x": 1}
    assert dict(engine.last_traces["F2"][0].vars) == {"x": 2}
