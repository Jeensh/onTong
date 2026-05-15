"""UC25 — Behavior-level twin verification demo (W59).

Fifth and strongest verification gate. Where W47/W52/W56/W57 compare static
*surfaces*, W59 actually **runs** the Python twin against pre-authored input
fixtures and diffs the result against a Java baseline output.

This demo:
    1. Translates a handful of Java methods through `JavaToPythonTranslator`.
    2. Defines behavior fixtures (input → expected Java-side output) inline.
    3. Plugs `BehaviorTwinRunner` into `VerificationEngine`.
    4. Runs the oracle and reports per-fixture + aggregate status.

Three intentionally chosen scenarios stress the verifier end-to-end:

    add_positives    — clean pass; covers branches, locals, return
    cumulative_sum   — clean pass; covers a for-loop + accumulator
    buggy_average    — fails by design; the Java reference baseline diverges
                       from what the twin actually computes (rounded down vs
                       precise BigDecimal) — surfaces FAIL_BREAKING.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc25_behavior_twin.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

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


JAVA_LANGUAGE = Language(tsjava.language())


# ─────────────────────────────────────────────────────────────────────────────
# Java sources — small, self-contained, no external deps
# ─────────────────────────────────────────────────────────────────────────────


JAVA_SOURCES: dict[str, str] = {
    "addPositives": """
        public class Calc {
            public int addPositives(int a, int b) {
                int x = a;
                if (x < 0) { x = 0; }
                int y = b;
                if (y < 0) { y = 0; }
                return x + y;
            }
        }
    """,
    "cumulativeSum": """
        public class Calc {
            public int cumulativeSum(int n) {
                int total = 0;
                for (int i = 1; i <= n; i = i + 1) {
                    total = total + i;
                }
                return total;
            }
        }
    """,
    # buggyAverage diverges from baseline on the second fixture — the baseline
    # says 4 but the twin (integer division) returns 3. This demonstrates that
    # the behavior gate surfaces real semantic drift, not just compile errors.
    "buggyAverage": """
        public class Calc {
            public int buggyAverage(int a, int b) {
                return (a + b) / 2;
            }
        }
    """,
}


@dataclass(frozen=True)
class MethodTwin:
    method_name:   str
    function_name: str
    python_source: str


def translate_methods() -> dict[str, MethodTwin]:
    """Translate each Java source to a Python twin."""
    twins: dict[str, MethodTwin] = {}
    translator = JavaToPythonTranslator()
    for name, src in JAVA_SOURCES.items():
        tree = Parser(JAVA_LANGUAGE).parse(src.encode())
        method = None
        for c in tree.root_node.children:
            if c.type == "class_declaration":
                body = next(x for x in c.children if x.type == "class_body")
                for m in body.named_children:
                    if m.type == "method_declaration":
                        method = m
                        break
        if method is None:
            raise RuntimeError(f"method_declaration not found in {name!r}")
        result = translator.translate(method, indent=0)
        twins[name] = MethodTwin(
            method_name=name,
            function_name=name,    # translator preserves the Java identifier
            python_source=result.python_source,
        )
    return twins


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — input args (None=self) + expected Java baseline output
# ─────────────────────────────────────────────────────────────────────────────


def build_store(twins: dict[str, MethodTwin]) -> BehaviorFixtureStore:
    store = BehaviorFixtureStore()

    # addPositives — three fixtures, all should PASS
    src = twins["addPositives"].python_source
    for fid, args, expected in [
        ("addPos.both_pos",  (None, 3, 5),    8),
        ("addPos.left_neg",  (None, -2, 5),   5),
        ("addPos.both_zero", (None, 0, 0),    0),
    ]:
        store.add(BehaviorFixture(
            fixture_id=fid,
            python_source=src,
            function_name="addPositives",
            input_args=args,
            input_kwargs={},
            expected_output=expected,
        ))

    # cumulativeSum — three fixtures, all should PASS
    src = twins["cumulativeSum"].python_source
    for fid, args, expected in [
        ("sum.n_5",  (None, 5),   15),
        ("sum.n_10", (None, 10),  55),
        ("sum.n_0",  (None, 0),    0),
    ]:
        store.add(BehaviorFixture(
            fixture_id=fid,
            python_source=src,
            function_name="cumulativeSum",
            input_args=args,
            input_kwargs={},
            expected_output=expected,
        ))

    # buggyAverage — two fixtures: one PASS, one FAIL_OUTPUT (baseline expects
    # rounded-up answer, twin returns integer-truncated — semantic drift).
    src = twins["buggyAverage"].python_source
    store.add(BehaviorFixture(
        fixture_id="avg.even",
        python_source=src,
        function_name="buggyAverage",
        input_args=(None, 4, 6),
        input_kwargs={},
        expected_output=5,
    ))
    store.add(BehaviorFixture(
        fixture_id="avg.odd_baseline_wrong",
        python_source=src,
        function_name="buggyAverage",
        input_args=(None, 3, 4),
        input_kwargs={},
        expected_output=4,        # baseline insists on 4 but twin returns 3 → FAIL
    ))
    return store


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_fixture(r: FixtureOracleResult) -> None:
    marker = {"PASS": "✓", "FAIL_OUTPUT": "✗", "FAIL_TRACE": "≠",
              "ERROR": "!"}[r.status]
    print(f"  {marker} [{r.status:11s}] {r.fixture_id}")
    print(f"    expected : {r.java_baseline_output!r}")
    print(f"    actual   : {r.python_proposal_output!r}")
    if r.output_diff.summary and r.output_diff.summary != "match":
        print(f"    diff     : {r.output_diff.summary}")
    if r.error:
        print(f"    error    : {r.error.splitlines()[0]}")


def _print_oracle(result: OracleResult, label: str) -> None:
    passes  = sum(1 for r in result.by_fixture.values() if r.status == "PASS")
    fails   = sum(1 for r in result.by_fixture.values() if r.status == "FAIL_OUTPUT")
    errors  = sum(1 for r in result.by_fixture.values() if r.status == "ERROR")
    total   = len(result.by_fixture)
    _banner(label)
    print(f"  Aggregate : {result.aggregate_status}")
    print(f"  Fixtures  : {total}  (PASS {passes}, FAIL_OUTPUT {fails}, ERROR {errors})")
    print()
    for fid in sorted(result.by_fixture.keys()):
        _print_fixture(result.by_fixture[fid])
        print()


def main() -> int:
    print("=" * 78)
    print("UC25 — Behavior-level twin verification (W59)")
    print("=" * 78)
    print()

    twins = translate_methods()
    print("Translated Java methods:")
    for name, t in twins.items():
        snippet = t.python_source.splitlines()[0]
        print(f"  • {name:18s} → {snippet}")
    print()

    store = build_store(twins)
    runner = BehaviorTwinRunner(store)
    engine = VerificationEngine(fixture_runner=runner, plugin="uc25")

    # Group 1: addPositives — clean
    req = OracleRequest(
        proposal_id="uc25.addPositives",
        fixture_subset=[f for f in store.ids() if f.startswith("addPos")],
    )
    _print_oracle(engine.run_oracle(req), "addPositives — 3 fixtures (all PASS expected)")

    # Group 2: cumulativeSum — clean
    req = OracleRequest(
        proposal_id="uc25.cumulativeSum",
        fixture_subset=[f for f in store.ids() if f.startswith("sum")],
    )
    _print_oracle(engine.run_oracle(req), "cumulativeSum — 3 fixtures (all PASS expected)")

    # Group 3: buggyAverage — surfaces semantic drift
    req = OracleRequest(
        proposal_id="uc25.buggyAverage",
        fixture_subset=[f for f in store.ids() if f.startswith("avg")],
    )
    _print_oracle(engine.run_oracle(req), "buggyAverage — 2 fixtures (1 FAIL_OUTPUT expected)")

    _banner("✓ W59 behavior gate exercised; PASS / FAIL_OUTPUT both surfaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
