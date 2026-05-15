"""UC1 v2 demo runner — end-to-end Java method translation + execution.

Demonstrates the full sim_v2 pipeline on a real slab-design v2 pattern:
  1. Read a small Java method (modeled after SdMaxSplitCountAction.execute)
  2. Parse via tree-sitter, translate via JavaToPythonTranslator (with type resolvers)
  3. Compile the emitted Python source to a callable
  4. Execute against 3 scenarios (normal / boundary / error)
  5. Compare against ground-truth Python re-implementation (oracle)
  6. Print PASS/FAIL/INCONCLUSIVE verdict per scenario

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc1_v2_full_demo.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.contracts.base import DECIMAL64, RoundingMode, bd_set_scale
from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.synthesizer.type_resolver import BigDecimalAwareResolver

# Java source — small clean version of the slab-design v2 pattern.
JAVA_SOURCE = """
class SlabSplit {
    public int computeMaxSplit(BigDecimal secondWgtHigh, BigDecimal orderWgtHigh, BigDecimal productivity) {
        BigDecimal raw = secondWgtHigh
            .divide(orderWgtHigh, MathContext.DECIMAL64)
            .divide(productivity, MathContext.DECIMAL64);
        int maxSplit = raw.setScale(0, RoundingMode.CEILING).intValueExact();
        if (maxSplit < 1) {
            throw new RuntimeException("maxSplit < 1");
        }
        return maxSplit;
    }
}
"""

JAVA_LANGUAGE = Language(tsjava.language())


@dataclass(frozen=True)
class Scenario:
    name: str
    inputs: dict[str, Decimal]
    expected_output: int | None  # None == expects exception
    expected_exception: type | None = None


def translate_java_method() -> tuple[str, dict[str, Any]]:
    """Parse the JAVA_SOURCE method, return (python_source, imports_collected)."""
    parser = Parser(JAVA_LANGUAGE)
    tree = parser.parse(JAVA_SOURCE.encode())

    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    method = m
                    break
            break
    if method is None:
        raise RuntimeError("computeMaxSplit method not found")

    translator = JavaToPythonTranslator(type_resolver=BigDecimalAwareResolver())
    tr = translator.translate(method, indent=0)
    return tr.python_source, {"imports": tr.imports_needed, "notes": tr.notes, "locked": tr.signature_locked}


def compile_to_callable(python_source: str):
    """Compile emitted Python source into a callable.

    The emitted source is a `def computeMaxSplit(self, ...)` method — we strip `self` for
    standalone execution.
    """
    # Strip `self, ` from the def signature for standalone calling
    python_source = python_source.replace("def computeMaxSplit(self, ", "def computeMaxSplit(")

    globals_dict: dict[str, Any] = {
        "Decimal":       Decimal,
        "RoundingMode":  RoundingMode,
        "DECIMAL64":     DECIMAL64,
        "bd_set_scale":  bd_set_scale,
    }
    exec(compile(python_source, "<demo>", "exec"), globals_dict)
    return globals_dict["computeMaxSplit"], python_source


def ground_truth_compute_max_split(
    secondWgtHigh: Decimal,
    orderWgtHigh: Decimal,
    productivity: Decimal,
) -> int:
    """Hand-written Python equivalent of the Java method — oracle baseline.

    Uses the same contract helper `bd_set_scale()` that the translated code uses,
    so oracle and twin share the same runtime substrate (Lesson 1 §4.1).
    """
    raw = secondWgtHigh / orderWgtHigh / productivity
    max_split = int(bd_set_scale(raw, 0, RoundingMode.CEILING))
    if max_split < 1:
        raise RuntimeError("maxSplit < 1")
    return max_split


def compare(actual: Any, expected: Any, exc_actual: Exception | None, exc_expected: type | None) -> str:
    """Return PASS / FAIL / INCONCLUSIVE."""
    if exc_expected is not None:
        if exc_actual is not None and isinstance(exc_actual, exc_expected):
            return "PASS (expected exception raised)"
        if exc_actual is not None:
            return f"FAIL_DRIFT (expected {exc_expected.__name__}, got {type(exc_actual).__name__})"
        return f"FAIL_BREAKING (expected {exc_expected.__name__}, got value {actual})"
    # Numeric expected
    if exc_actual is not None:
        return f"FAIL_BREAKING (raised {type(exc_actual).__name__}: {exc_actual})"
    if actual == expected:
        return "PASS"
    return f"FAIL_DRIFT (got {actual}, expected {expected})"


def run_scenarios(translated_func, scenarios: list[Scenario]) -> list[tuple[str, str, str, str]]:
    """Run each scenario through translated + ground-truth, return per-scenario verdicts."""
    rows: list[tuple[str, str, str, str]] = []
    for scenario in scenarios:
        # Translated
        tx_value: Any = None
        tx_exc: Exception | None = None
        try:
            tx_value = translated_func(**scenario.inputs)
        except Exception as e:
            tx_exc = e

        # Ground truth
        gt_value: Any = None
        gt_exc: Exception | None = None
        try:
            gt_value = ground_truth_compute_max_split(**scenario.inputs)
        except Exception as e:
            gt_exc = e

        # Compare each against scenario.expected
        tx_verdict = compare(tx_value, scenario.expected_output, tx_exc, scenario.expected_exception)
        gt_verdict = compare(gt_value, scenario.expected_output, gt_exc, scenario.expected_exception)
        # Cross-check translated vs ground truth
        cross = "MATCH" if (tx_value == gt_value and type(tx_exc) == type(gt_exc)) else "DIVERGE"

        rows.append((scenario.name, tx_verdict, gt_verdict, cross))
    return rows


def main() -> int:
    print("=" * 76)
    print("UC1 v2 demo — SlabSplit.computeMaxSplit Java→Python end-to-end")
    print("=" * 76)
    print()

    # Step 1: Translate Java to Python
    print("Step 1: Java AST → Python translation")
    py_source, meta = translate_java_method()
    print(f"  signature_locked: {meta['locked']}")
    print(f"  imports collected: {meta['imports']}")
    if meta["notes"]:
        print(f"  translator notes: {meta['notes']}")
    print()
    print("Generated Python source:")
    for line in py_source.split("\n"):
        print(f"  | {line}")
    print()

    if meta["locked"]:
        print("ABORT: translator reported signature_locked — would not be safe to execute")
        return 1

    # Step 2: Compile
    print("Step 2: Compile Python source to callable")
    try:
        translated_func, normalized_source = compile_to_callable(py_source)
        print("  OK — compiled successfully")
    except SyntaxError as e:
        print(f"  FAIL — SyntaxError: {e}")
        return 2
    print()

    # Step 3: Run scenarios
    print("Step 3: Run 3 scenarios against translated + ground-truth")
    scenarios = [
        Scenario(
            name="normal",
            inputs={
                "secondWgtHigh": Decimal("100"),
                "orderWgtHigh":  Decimal("20"),
                "productivity":  Decimal("0.5"),
            },
            expected_output=10,
        ),
        Scenario(
            name="boundary (raw < 1, ceil → 1)",
            inputs={
                "secondWgtHigh": Decimal("0.3"),
                "orderWgtHigh":  Decimal("1"),
                "productivity":  Decimal("1"),
            },
            expected_output=1,
        ),
        Scenario(
            name="error (raw == 0 → maxSplit 0 < 1)",
            inputs={
                "secondWgtHigh": Decimal("0"),
                "orderWgtHigh":  Decimal("1"),
                "productivity":  Decimal("1"),
            },
            expected_output=None,
            expected_exception=RuntimeError,
        ),
    ]
    rows = run_scenarios(translated_func, scenarios)
    print()
    print(f"  {'Scenario':<35} {'Translated':<30} {'Ground Truth':<30} {'Cross':<8}")
    print(f"  {'-' * 35} {'-' * 30} {'-' * 30} {'-' * 8}")
    for name, tx, gt, cross in rows:
        print(f"  {name:<35} {tx:<30} {gt:<30} {cross:<8}")

    # Step 4: Final verdict
    print()
    all_match = all(cross == "MATCH" and tx.startswith("PASS") for _, tx, _, cross in rows)
    if all_match:
        print("✓ Final verdict: PASS — translated Python matches ground truth on all scenarios")
        return 0
    else:
        print("✗ Final verdict: FAIL — some scenarios diverged. See per-scenario detail above.")
        return 3


if __name__ == "__main__":
    sys.exit(main())
