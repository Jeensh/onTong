"""UC1 v2 demo — pytest verification — W13.3.

Verifies that the demo runner translates the sample Java method to Python,
compiles + executes against 3 scenarios, and produces PASS verdicts matching
the ground-truth Python re-implementation.
"""
from __future__ import annotations

from decimal import Decimal

from backend.sim_v2.demos.uc1_v2_full_demo.run import (
    Scenario,
    compile_to_callable,
    ground_truth_compute_max_split,
    run_scenarios,
    translate_java_method,
)


def test_translation_signature_locked_false():
    """Translation of the demo Java method must not be signature_locked."""
    _, meta = translate_java_method()
    assert not meta["locked"], (
        f"signature_locked unexpectedly true. notes={meta['notes']}"
    )


def test_translation_imports_collected():
    _, meta = translate_java_method()
    assert "backend.sim_v2.core.contracts.base" in meta["imports"]


def test_translation_emits_expected_python_features():
    """Smoke-check that the emitted Python source has the expected operators / helpers."""
    py_source, _ = translate_java_method()
    # Binary division operator from BigDecimal.divide chain
    assert "/" in py_source
    # bd_set_scale helper from setScale mapping
    assert "bd_set_scale" in py_source
    # int() wrap from intValueExact
    assert "int(" in py_source
    # raise from throw_statement
    assert "raise" in py_source
    # if maxSplit < 1 condition (translated from if statement)
    assert "if maxSplit < 1" in py_source


def test_compile_succeeds():
    py_source, _ = translate_java_method()
    fn, _ = compile_to_callable(py_source)
    assert callable(fn)


def test_normal_scenario_matches_ground_truth():
    py_source, _ = translate_java_method()
    fn, _ = compile_to_callable(py_source)
    inputs = {
        "secondWgtHigh": Decimal("100"),
        "orderWgtHigh":  Decimal("20"),
        "productivity":  Decimal("0.5"),
    }
    assert fn(**inputs) == ground_truth_compute_max_split(**inputs) == 10


def test_boundary_scenario_matches_ground_truth():
    py_source, _ = translate_java_method()
    fn, _ = compile_to_callable(py_source)
    inputs = {
        "secondWgtHigh": Decimal("0.3"),
        "orderWgtHigh":  Decimal("1"),
        "productivity":  Decimal("1"),
    }
    assert fn(**inputs) == ground_truth_compute_max_split(**inputs) == 1


def test_error_scenario_raises():
    py_source, _ = translate_java_method()
    fn, _ = compile_to_callable(py_source)
    inputs = {
        "secondWgtHigh": Decimal("0"),
        "orderWgtHigh":  Decimal("1"),
        "productivity":  Decimal("1"),
    }
    import pytest
    with pytest.raises(RuntimeError, match="maxSplit < 1"):
        fn(**inputs)
    with pytest.raises(RuntimeError, match="maxSplit < 1"):
        ground_truth_compute_max_split(**inputs)


def test_run_scenarios_all_pass():
    """Full run — all 3 scenarios produce PASS verdict + MATCH cross-check."""
    py_source, _ = translate_java_method()
    fn, _ = compile_to_callable(py_source)
    scenarios = [
        Scenario("normal",
                 {"secondWgtHigh": Decimal("100"), "orderWgtHigh": Decimal("20"), "productivity": Decimal("0.5")},
                 10),
        Scenario("boundary",
                 {"secondWgtHigh": Decimal("0.3"), "orderWgtHigh": Decimal("1"), "productivity": Decimal("1")},
                 1),
        Scenario("error",
                 {"secondWgtHigh": Decimal("0"), "orderWgtHigh": Decimal("1"), "productivity": Decimal("1")},
                 None, RuntimeError),
    ]
    rows = run_scenarios(fn, scenarios)
    for name, translated_verdict, gt_verdict, cross in rows:
        assert translated_verdict.startswith("PASS"), f"{name}: translated={translated_verdict}"
        assert gt_verdict.startswith("PASS"), f"{name}: ground_truth={gt_verdict}"
        assert cross == "MATCH", f"{name}: cross={cross}"


def test_demo_main_returns_zero():
    """The demo's main() exits with code 0 (all scenarios PASS + MATCH)."""
    from backend.sim_v2.demos.uc1_v2_full_demo.run import main
    assert main() == 0
