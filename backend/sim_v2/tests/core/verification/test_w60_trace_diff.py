"""W60 — TraceDiff integration tests.

Exercises the FAIL_TRACE / FAIL_DRIFT path in the behavior twin runner +
VerificationEngine.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixture,
    BehaviorFixtureStore,
    BehaviorTwinRunner,
)
from backend.sim_v2.core.verification.engine import VerificationEngine
from backend.sim_v2.core.verification.oracle import OracleRequest
from backend.sim_v2.core.verification.trace import TraceEvent


# ─────────────────────────────────────────────────────────────────────────────
# Twin sources — instrumented variants
# ─────────────────────────────────────────────────────────────────────────────


# A twin that emits exactly 2 trace.step events: one for x, one for the result.
_INSTRUMENTED_ADD = """
def add(self, a, b):
    x = a + b
    _trace.step('anchor_1', {'x': x})
    result = x
    _trace.step('anchor_2', {'result': result})
    return result
"""


_INSTRUMENTED_LOOP = """
def loop_sum(self, n):
    total = 0
    _trace.step('anchor_1', {'total': total})
    i = 1
    while i <= n:
        total = total + i
        _trace.step('anchor_2', {'total': total, 'i': i})
        i = i + 1
    return total
"""


def _ev(anchor, vars_dict, kind="step"):
    """Helper — build a TraceEvent. vars converted to sorted tuple-of-pairs."""
    return TraceEvent(
        anchor_id=anchor, kind=kind,
        vars=tuple(sorted(vars_dict.items())),
    )


def _fix(fid, *, source=_INSTRUMENTED_ADD, fn="add",
         args=(None, 2, 3), kwargs=None,
         expected=5, tolerance=0.0,
         expected_trace=None, trace_tolerance=0.0):
    return BehaviorFixture(
        fixture_id=fid,
        python_source=source,
        function_name=fn,
        input_args=tuple(args),
        input_kwargs=dict(kwargs or {}),
        expected_output=expected,
        tolerance=tolerance,
        expected_trace_events=(
            tuple(expected_trace) if expected_trace is not None else None
        ),
        trace_numeric_tolerance=trace_tolerance,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-status
# ─────────────────────────────────────────────────────────────────────────────


def test_pass_when_output_and_trace_match():
    fixture = _fix(
        "pass",
        expected_trace=[
            _ev("anchor_1", {"x": 5}),
            _ev("anchor_2", {"result": 5}),
        ],
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([fixture]))
    r = runner.run_fixture("pass", plugin="", apply_diffs={})
    assert r.status == "PASS"
    assert r.trace_diff.is_equivalent
    assert "2 steps matched" in r.trace_diff.summary


def test_fail_trace_when_output_matches_but_trace_differs():
    """Output is 5 (matches), but expected trace has wrong anchor_id at step 0."""
    fixture = _fix(
        "drift",
        expected_trace=[
            _ev("anchor_WRONG", {"x": 5}),
            _ev("anchor_2", {"result": 5}),
        ],
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([fixture]))
    r = runner.run_fixture("drift", plugin="", apply_diffs={})
    assert r.status == "FAIL_TRACE"
    assert not r.trace_diff.is_equivalent
    assert r.trace_diff.diverging_step_no == 0
    assert "anchor" in r.trace_diff.summary


def test_fail_trace_when_trace_length_diverges():
    fixture = _fix(
        "len",
        expected_trace=[_ev("anchor_1", {"x": 5})],  # only 1 step expected
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([fixture]))
    r = runner.run_fixture("len", plugin="", apply_diffs={})
    assert r.status == "FAIL_TRACE"
    assert "length mismatch" in r.trace_diff.summary


def test_fail_trace_when_var_value_diverges():
    fixture = _fix(
        "var",
        expected_trace=[
            _ev("anchor_1", {"x": 999}),    # actual x=5
            _ev("anchor_2", {"result": 5}),
        ],
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([fixture]))
    r = runner.run_fixture("var", plugin="", apply_diffs={})
    assert r.status == "FAIL_TRACE"
    assert "var values differ" in r.trace_diff.summary


def test_fail_output_dominates_fail_trace():
    """If both output and trace differ, status is FAIL_OUTPUT (the worse one)."""
    fixture = _fix(
        "both_bad",
        expected=999,                         # output mismatch (actual 5)
        expected_trace=[_ev("wrong", {})],    # trace mismatch too
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([fixture]))
    r = runner.run_fixture("both_bad", plugin="", apply_diffs={})
    assert r.status == "FAIL_OUTPUT"


def test_pass_without_expected_trace_does_not_inspect_trace():
    """Backward compat: fixtures without expected_trace still PASS (no instrumentation needed)."""
    fixture = _fix("nontrace", expected_trace=None)
    # Use a non-instrumented source (no _trace.step calls)
    fixture = BehaviorFixture(
        fixture_id="nontrace",
        python_source="def add(self, a, b):\n    return a + b\n",
        function_name="add",
        input_args=(None, 2, 3),
        input_kwargs={},
        expected_output=5,
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([fixture]))
    r = runner.run_fixture("nontrace", plugin="", apply_diffs={})
    assert r.status == "PASS"
    assert r.trace_diff.is_equivalent  # placeholder default still True


def test_loop_trace_records_each_iteration():
    """Loop-sum: n=3 → 3 iterations → 1 initial step + 3 loop steps = 4 events."""
    fixture = _fix(
        "loop",
        source=_INSTRUMENTED_LOOP, fn="loop_sum",
        args=(None, 3), expected=6,
        expected_trace=[
            _ev("anchor_1", {"total": 0}),
            _ev("anchor_2", {"total": 1, "i": 1}),
            _ev("anchor_2", {"total": 3, "i": 2}),
            _ev("anchor_2", {"total": 6, "i": 3}),
        ],
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([fixture]))
    r = runner.run_fixture("loop", plugin="", apply_diffs={})
    assert r.status == "PASS"
    assert "4 steps matched" in r.trace_diff.summary


def test_trace_numeric_tolerance():
    """Twin records x=5; expected x=5.0001; tolerance accepts."""
    fixture = _fix(
        "tol",
        expected_trace=[
            _ev("anchor_1", {"x": 5.0001}),
            _ev("anchor_2", {"result": 5}),
        ],
        trace_tolerance=0.001,
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([fixture]))
    r = runner.run_fixture("tol", plugin="", apply_diffs={})
    assert r.status == "PASS"


def test_trace_diff_carries_event_payload():
    """When trace diverges, TraceDiff.expected_event + actual_event populated."""
    fixture = _fix(
        "ev",
        expected_trace=[
            _ev("anchor_1", {"x": 999}),
            _ev("anchor_2", {"result": 5}),
        ],
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([fixture]))
    r = runner.run_fixture("ev", plugin="", apply_diffs={})
    assert r.status == "FAIL_TRACE"
    assert r.trace_diff.expected_event == {
        "anchor_id": "anchor_1", "kind": "step", "vars": {"x": 999},
    }
    assert r.trace_diff.actual_event == {
        "anchor_id": "anchor_1", "kind": "step", "vars": {"x": 5},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Engine integration — FAIL_DRIFT aggregate
# ─────────────────────────────────────────────────────────────────────────────


def test_engine_aggregates_fail_drift():
    """Output match + trace mismatch → aggregate FAIL_DRIFT."""
    good = _fix(
        "good",
        expected_trace=[
            _ev("anchor_1", {"x": 5}),
            _ev("anchor_2", {"result": 5}),
        ],
    )
    drift = _fix(
        "drift",
        expected_trace=[
            _ev("anchor_WRONG", {"x": 5}),
            _ev("anchor_2", {"result": 5}),
        ],
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([good, drift]))
    engine = VerificationEngine(fixture_runner=runner, plugin="t")
    req = OracleRequest(proposal_id="p1", fixture_subset=["good", "drift"])
    result = engine.run_oracle(req)
    assert result.aggregate_status == "FAIL_DRIFT"


def test_engine_fail_breaking_overrides_fail_drift():
    """If any fixture is FAIL_OUTPUT, aggregate is FAIL_BREAKING (not FAIL_DRIFT)."""
    drift_fix = _fix(
        "drift",
        expected_trace=[
            _ev("anchor_WRONG", {"x": 5}),
            _ev("anchor_2", {"result": 5}),
        ],
    )
    # Use a non-instrumented source so the trace-less fixture cleanly returns
    # an output (and therefore FAIL_OUTPUT) rather than erroring on `_trace`.
    bad_output = BehaviorFixture(
        fixture_id="bad",
        python_source="def add(self, a, b):\n    return a + b\n",
        function_name="add",
        input_args=(None, 2, 3),
        input_kwargs={},
        expected_output=999,
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([drift_fix, bad_output]))
    engine = VerificationEngine(fixture_runner=runner, plugin="t")
    req = OracleRequest(proposal_id="p1", fixture_subset=["drift", "bad"])
    result = engine.run_oracle(req)
    assert result.aggregate_status == "FAIL_BREAKING"


# ─────────────────────────────────────────────────────────────────────────────
# Real translator round-trip — with_trace=True
# ─────────────────────────────────────────────────────────────────────────────


def test_real_translator_with_trace_emits_steps():
    """Compile a Java method with with_trace=True and verify trace is captured."""
    import tree_sitter_java as tsjava
    from tree_sitter import Language, Parser

    from backend.sim_v2.core.synthesizer.java_translator import (
        JavaToPythonTranslator,
    )

    java_src = """
    public class Calc {
        public int compute(int a, int b) {
            int x = a + b;
            return x;
        }
    }
    """
    tree = Parser(Language(tsjava.language())).parse(java_src.encode())
    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    method = m
                    break
    assert method is not None

    result = JavaToPythonTranslator().translate(method, indent=0, with_trace=True)
    source = result.python_source
    assert "_trace.step" in source

    # Just verify the trace runs without error — the actual anchor_ids/vars
    # depend on translator internals so we don't assert their values, only
    # that *some* trace events are captured.
    fixture = BehaviorFixture(
        fixture_id="real",
        python_source=source,
        function_name="compute",
        input_args=(None, 2, 3),
        input_kwargs={},
        expected_output=5,
        expected_trace_events=(),  # we'll check via collector after run
    )
    # With empty expected_trace, runner expects 0 steps but actual will have
    # >= 1 → FAIL_TRACE.
    runner = BehaviorTwinRunner(BehaviorFixtureStore([fixture]))
    r = runner.run_fixture("real", plugin="", apply_diffs={})
    assert r.status == "FAIL_TRACE"
    assert "length mismatch" in r.trace_diff.summary
