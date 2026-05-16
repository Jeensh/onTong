"""UC26 — Trace-level twin verification demo (W60).

Closes the FAIL_DRIFT bucket in oracle's 4-tier aggregate. Where W59 only
checked the *output* of the Python twin, W60 also captures the *execution
trace* (per-statement `_trace.step` events) and diffs it against an expected
trace authored alongside the fixture.

A FAIL_DRIFT case is the precise case where the twin yields the right answer
but takes a different path to get there — R4 of ADR-001's verification rules.

The demo translates one Java method twice — once plain, once with
`with_trace=True` — then runs four fixtures designed to expose each of the
four oracle outcomes individually:

    PASS        — output + trace match
    FAIL_OUTPUT — output diverges (aggregate → FAIL_BREAKING)
    FAIL_TRACE  — output matches but trace diverges (aggregate → FAIL_DRIFT)
    ERROR       — twin throws (aggregate → INCONCLUSIVE)

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc26_trace_diff.run
"""
from __future__ import annotations

import sys

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.java_translator import (
    JavaToPythonTranslator,
)
from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixture,
    BehaviorFixtureStore,
    BehaviorTwinRunner,
)
from backend.sim_v2.core.verification.engine import VerificationEngine
from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    OracleRequest,
    OracleResult,
)
from backend.sim_v2.core.verification.trace import TraceEvent


JAVA_LANGUAGE = Language(tsjava.language())


JAVA_SOURCE = """
public class Calc {
    public int doubleIt(int a) {
        int x = a + a;
        return x;
    }
}
"""


def translate(*, with_trace: bool) -> str:
    tree = Parser(JAVA_LANGUAGE).parse(JAVA_SOURCE.encode())
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    return JavaToPythonTranslator().translate(
                        m, indent=0, with_trace=with_trace,
                    ).python_source
    raise RuntimeError("method not found")


def _ev(anchor, vars_dict, kind="step") -> TraceEvent:
    return TraceEvent(
        anchor_id=anchor, kind=kind,
        vars=tuple(sorted(vars_dict.items())),
    )


def _capture_expected_trace(source_with_trace: str) -> list[TraceEvent]:
    """Run the instrumented twin once with a fresh collector to discover what
    the real trace looks like, then return its events as the canonical
    'expected' trace for PASS fixtures."""
    from backend.sim_v2.core.verification.trace import TraceCollector
    ns: dict = {}
    collector = TraceCollector()
    exec(
        compile(source_with_trace, "<discover>", "exec"),
        {"__builtins__": __builtins__, "_trace": collector},
        ns,
    )
    ns["doubleIt"](None, 7)   # any input — we just want the trace shape
    return collector.events


def build_store() -> BehaviorFixtureStore:
    plain_src       = translate(with_trace=False)
    instrumented_src = translate(with_trace=True)

    # Discover what trace the instrumented twin actually produces, so the PASS
    # fixture matches by construction. The drift fixture mutates this to force
    # a divergence.
    canonical_trace = _capture_expected_trace(instrumented_src)

    store = BehaviorFixtureStore()

    # 1) PASS — instrumented, expected trace matches reality.
    store.add(BehaviorFixture(
        fixture_id="pass.7",
        python_source=instrumented_src,
        function_name="doubleIt",
        input_args=(None, 7),
        input_kwargs={},
        expected_output=14,
        expected_trace_events=tuple(canonical_trace),
    ))

    # 2) FAIL_OUTPUT — plain twin, wrong expected output.
    store.add(BehaviorFixture(
        fixture_id="fail_output.7",
        python_source=plain_src,
        function_name="doubleIt",
        input_args=(None, 7),
        input_kwargs={},
        expected_output=999,
    ))

    # 3) FAIL_TRACE — instrumented twin, output match BUT expected trace
    #    swaps the first anchor_id → trace diff at step 0.
    if canonical_trace:
        bad_first = TraceEvent(
            anchor_id="anchor_WRONG",
            kind=canonical_trace[0].kind,
            vars=canonical_trace[0].vars,
        )
        bad_trace = (bad_first,) + tuple(canonical_trace[1:])
    else:
        # Translator emitted no trace.step (shouldn't happen for this method)
        bad_trace = (_ev("anchor_WRONG", {}),)
    store.add(BehaviorFixture(
        fixture_id="fail_trace.7",
        python_source=instrumented_src,
        function_name="doubleIt",
        input_args=(None, 7),
        input_kwargs={},
        expected_output=14,
        expected_trace_events=bad_trace,
    ))

    # 4) ERROR — twin source has runtime bug.
    store.add(BehaviorFixture(
        fixture_id="error.boom",
        python_source="def doubleIt(self, a):\n    raise ValueError('nope')\n",
        function_name="doubleIt",
        input_args=(None, 7),
        input_kwargs={},
        expected_output=14,
    ))

    return store


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_fixture(r: FixtureOracleResult) -> None:
    marker = {"PASS": "✓", "FAIL_OUTPUT": "✗", "FAIL_TRACE": "≠",
              "ERROR": "!"}[r.status]
    print(f"  {marker} [{r.status:11s}] {r.fixture_id}")
    print(f"    expected_output : {r.java_baseline_output!r}")
    print(f"    actual_output   : {r.python_proposal_output!r}")
    if r.output_diff.summary and r.output_diff.summary != "match":
        print(f"    output_diff     : {r.output_diff.summary}")
    if r.trace_diff and r.trace_diff.summary:
        ok = "ok" if r.trace_diff.is_equivalent else "diff"
        print(f"    trace ({ok})     : {r.trace_diff.summary}")
        if r.trace_diff.diverging_step_no is not None:
            print(f"    diverge_step    : {r.trace_diff.diverging_step_no}")
            if r.trace_diff.expected_event:
                print(f"    expected_event  : {r.trace_diff.expected_event}")
            if r.trace_diff.actual_event:
                print(f"    actual_event    : {r.trace_diff.actual_event}")
    if r.error:
        print(f"    error           : {r.error.splitlines()[0]}")


def _print_oracle(result: OracleResult, label: str) -> None:
    _banner(label)
    print(f"  Aggregate : {result.aggregate_status}")
    print(f"  Fixtures  : {len(result.by_fixture)}")
    print()
    for fid in sorted(result.by_fixture.keys()):
        _print_fixture(result.by_fixture[fid])
        print()


def main() -> int:
    print("=" * 78)
    print("UC26 — Trace-level twin verification (W60)")
    print("=" * 78)
    print()

    store = build_store()
    runner = BehaviorTwinRunner(store)
    engine = VerificationEngine(fixture_runner=runner, plugin="uc26")

    # Single-fixture runs to surface each aggregate state cleanly.
    for fid, label, expected_agg in [
        ("pass.7",         "Group A — output + trace match",   "PASS"),
        ("fail_output.7",  "Group B — output diverges",        "FAIL_BREAKING"),
        ("fail_trace.7",   "Group C — output OK, trace drifts","FAIL_DRIFT"),
        ("error.boom",     "Group D — twin throws at runtime", "INCONCLUSIVE"),
    ]:
        req = OracleRequest(proposal_id=f"uc26.{fid}", fixture_subset=[fid])
        result = engine.run_oracle(req)
        _print_oracle(result, f"{label}  (expected aggregate: {expected_agg})")
        assert result.aggregate_status == expected_agg, (
            f"unexpected aggregate for {fid}: got {result.aggregate_status}"
        )

    _banner("✓ All 4 oracle aggregate states demonstrated end-to-end")
    return 0


if __name__ == "__main__":
    sys.exit(main())
