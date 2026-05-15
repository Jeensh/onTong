"""Cross-side trace diff + FAIL_TRACE status tests — W17.

When `with_trace=True`, ScenarioVerificationEngine injects fresh TraceCollector
into BOTH translated_fn.__globals__["_trace"] and baseline_fn.__globals__["_trace"].
diff_traces compares the two traces. PASS output + DIFFERENT trace → FAIL_TRACE.
"""
from __future__ import annotations

from decimal import Decimal

from backend.sim_v2.core.verification.oracle import OracleRequest
from backend.sim_v2.core.verification.scenario_engine import (
    Scenario,
    ScenarioVerificationEngine,
)


def _make_traced_fn(source: str):
    g = {"_trace": None}
    exec(source, g)
    return g["fn"]


# ─────────────────────────────────────────────────────────────────────────────
# PASS — output match + trace match
# ─────────────────────────────────────────────────────────────────────────────


def test_pass_when_output_and_trace_match():
    src = (
        "def fn(x):\n"
        "    _trace.step('a', {'x': x})\n"
        "    return x + 1"
    )
    fn_a = _make_traced_fn(src)
    fn_b = _make_traced_fn(src)  # identical source — identical trace
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=6)}
    engine = ScenarioVerificationEngine(fn_a, fn_b, fixtures, with_trace=True)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    assert result.by_fixture["F"].status == "PASS"
    assert result.aggregate_status == "PASS"
    assert result.by_fixture["F"].trace_diff.is_equivalent
    assert "1 steps matched" in result.by_fixture["F"].trace_diff.summary


# ─────────────────────────────────────────────────────────────────────────────
# FAIL_TRACE — output match + trace differ
# ─────────────────────────────────────────────────────────────────────────────


def test_fail_trace_when_only_trace_differs():
    """Same output but different trace var values → FAIL_TRACE → aggregate FAIL_DRIFT."""
    src_a = (
        "def fn(x):\n"
        "    intermediate = x * 2\n"
        "    _trace.step('a', {'intermediate': intermediate})\n"
        "    return x + 1"
    )
    src_b = (
        "def fn(x):\n"
        "    intermediate = x + x  # same value as x*2 for x=5\n"
        "    _trace.step('a', {'intermediate': intermediate + 1})  # 11 not 10\n"
        "    return x + 1"
    )
    fn_a = _make_traced_fn(src_a)
    fn_b = _make_traced_fn(src_b)
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=6)}
    engine = ScenarioVerificationEngine(fn_a, fn_b, fixtures, with_trace=True)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    # Output matches (both return 6), but trace var values differ (10 vs 11)
    assert result.by_fixture["F"].status == "FAIL_TRACE"
    assert result.aggregate_status == "FAIL_DRIFT"


def test_fail_trace_on_anchor_mismatch():
    """Different anchor_id but same vars → FAIL_TRACE."""
    src_a = (
        "def fn(x):\n"
        "    _trace.step('alpha', {'x': x})\n"
        "    return x"
    )
    src_b = (
        "def fn(x):\n"
        "    _trace.step('beta', {'x': x})\n"  # different anchor
        "    return x"
    )
    fn_a = _make_traced_fn(src_a)
    fn_b = _make_traced_fn(src_b)
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=5)}
    engine = ScenarioVerificationEngine(fn_a, fn_b, fixtures, with_trace=True)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    assert result.by_fixture["F"].status == "FAIL_TRACE"
    assert "anchor/kind mismatch" in result.by_fixture["F"].trace_diff.summary


def test_fail_trace_on_length_mismatch():
    """Translated emits 2 steps, baseline emits 1 → length mismatch → FAIL_TRACE."""
    src_a = (
        "def fn(x):\n"
        "    _trace.step('a', {'x': x})\n"
        "    _trace.step('b', {'y': x + 1})\n"
        "    return x"
    )
    src_b = (
        "def fn(x):\n"
        "    _trace.step('a', {'x': x})\n"
        "    return x"
    )
    fn_a = _make_traced_fn(src_a)
    fn_b = _make_traced_fn(src_b)
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=5)}
    engine = ScenarioVerificationEngine(fn_a, fn_b, fixtures, with_trace=True)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    assert result.by_fixture["F"].status == "FAIL_TRACE"
    assert "length mismatch" in result.by_fixture["F"].trace_diff.summary


# ─────────────────────────────────────────────────────────────────────────────
# Tolerance
# ─────────────────────────────────────────────────────────────────────────────


def test_tolerance_makes_close_decimals_equivalent():
    src_a = (
        "def fn(x):\n"
        "    from decimal import Decimal\n"
        "    raw = Decimal('1.0000001')\n"
        "    _trace.step('a', {'raw': raw})\n"
        "    return x"
    )
    src_b = (
        "def fn(x):\n"
        "    from decimal import Decimal\n"
        "    raw = Decimal('1.0')\n"
        "    _trace.step('a', {'raw': raw})\n"
        "    return x"
    )
    fn_a = _make_traced_fn(src_a)
    fn_b = _make_traced_fn(src_b)
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=5)}
    engine = ScenarioVerificationEngine(
        fn_a, fn_b, fixtures, with_trace=True, trace_tolerance=0.001,
    )
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    assert result.by_fixture["F"].status == "PASS"
    assert result.aggregate_status == "PASS"


def test_tolerance_zero_catches_exact_diff():
    src_a = (
        "def fn(x):\n"
        "    from decimal import Decimal\n"
        "    raw = Decimal('1.0000001')\n"
        "    _trace.step('a', {'raw': raw})\n"
        "    return x"
    )
    src_b = (
        "def fn(x):\n"
        "    from decimal import Decimal\n"
        "    raw = Decimal('1.0')\n"
        "    _trace.step('a', {'raw': raw})\n"
        "    return x"
    )
    fn_a = _make_traced_fn(src_a)
    fn_b = _make_traced_fn(src_b)
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=5)}
    engine = ScenarioVerificationEngine(
        fn_a, fn_b, fixtures, with_trace=True,
    )  # trace_tolerance defaults to 0.0
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    assert result.by_fixture["F"].status == "FAIL_TRACE"


# ─────────────────────────────────────────────────────────────────────────────
# TraceDiff fields populated
# ─────────────────────────────────────────────────────────────────────────────


def test_trace_diff_has_expected_and_actual_events_on_diff():
    src_a = (
        "def fn(x):\n"
        "    _trace.step('a', {'x': x})\n"
        "    return x"
    )
    src_b = (
        "def fn(x):\n"
        "    _trace.step('a', {'x': x + 1})\n"
        "    return x"
    )
    fn_a = _make_traced_fn(src_a)
    fn_b = _make_traced_fn(src_b)
    fixtures = {"F": Scenario("F", {"x": 5}, expected_output=5)}
    engine = ScenarioVerificationEngine(fn_a, fn_b, fixtures, with_trace=True)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F"]))
    diff = result.by_fixture["F"].trace_diff
    assert diff.diverging_step_no == 0
    assert diff.expected_event is not None
    assert diff.actual_event is not None
    # baseline emitted 6 (x+1 with x=5), translated emitted 5
    assert diff.expected_event["vars"]["x"] == 6
    assert diff.actual_event["vars"]["x"] == 5


def test_aggregate_fail_drift_with_mixed_pass_and_trace_fail():
    """Multi-fixture aggregate: 2 PASS + 1 FAIL_TRACE → FAIL_DRIFT (no FAIL_OUTPUT)."""
    src_a = (
        "def fn(x):\n"
        "    _trace.step('a', {'x': x})\n"
        "    return x"
    )
    src_b = (
        "def fn(x):\n"
        "    _trace.step('a', {'x': x + (x // 5)})\n"  # x for x<5, x+1 for x>=5
        "    return x"
    )
    fn_a = _make_traced_fn(src_a)
    fn_b = _make_traced_fn(src_b)
    fixtures = {
        "F1_low":  Scenario("F1_low",  {"x": 1}, expected_output=1),  # both step → x=1
        "F2_high": Scenario("F2_high", {"x": 5}, expected_output=5),  # translated=5, baseline=6
    }
    engine = ScenarioVerificationEngine(fn_a, fn_b, fixtures, with_trace=True)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1_low", "F2_high"]))
    assert result.by_fixture["F1_low"].status == "PASS"
    assert result.by_fixture["F2_high"].status == "FAIL_TRACE"
    assert result.aggregate_status == "FAIL_DRIFT"


# ─────────────────────────────────────────────────────────────────────────────
# Demo integration
# ─────────────────────────────────────────────────────────────────────────────


def test_demo_main_returns_zero_with_trace():
    """The W17-updated demo's main() exits 0 (all 3 scenarios + trace match)."""
    from backend.sim_v2.demos.uc1_integrator_pipeline.run import main
    assert main() == 0
