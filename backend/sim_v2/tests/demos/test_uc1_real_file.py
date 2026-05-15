"""UC1 real-file demo verification — W14.2/W14.3.

Verifies the demo loads the actual SdMaxSplitCountAction.java, translates with
ontology-aware type resolution, compiles, and executes all 3 scenarios correctly
including void method side-effects.
"""
from __future__ import annotations

from decimal import Decimal

from backend.sim_v2.demos.uc1_real_file.run import (
    AlgorithmException,
    REAL_JAVA_FILE,
    SDOrderEntity,
    SDSlabEntity,
    Scenario,
    build_ontology_session,
    compile_to_callable,
    main,
    make_scenarios,
    run_scenario,
    translate_real_file,
)


def test_real_java_file_exists():
    assert REAL_JAVA_FILE.exists(), f"Expected real file at {REAL_JAVA_FILE}"


def test_ontology_session_has_5_methods():
    session = build_ontology_session()
    from backend.modeling.code_layer.orm import CodeMethodRow
    count = session.query(CodeMethodRow).count()
    assert count == 5  # 3 SDSlabEntity + 2 SDOrderEntity


def test_translation_not_signature_locked():
    session = build_ontology_session()
    _, meta = translate_real_file(session)
    assert not meta["locked"], f"signature_locked: notes={meta['notes']}"


def test_translation_emits_division_operators():
    """Chained .divide() via ontology → / operators."""
    session = build_ontology_session()
    py, _ = translate_real_file(session)
    # Two chained divisions
    assert "/" in py
    assert ".divide(" not in py  # no fallback method-call syntax


def test_translation_emits_bd_set_scale():
    session = build_ontology_session()
    py, _ = translate_real_file(session)
    assert "bd_set_scale" in py
    assert "RoundingMode.CEILING" in py


def test_translation_preserves_korean_comments():
    session = build_ontology_session()
    py, _ = translate_real_file(session)
    # The real file has Korean comments
    assert "# A-a 루프 시작점" in py


def test_translation_string_concat_wraps_with_str():
    """Java `"raw=" + raw` (BigDecimal) → Python `"raw=" + str(raw)`."""
    session = build_ontology_session()
    py, _ = translate_real_file(session)
    assert "str(raw)" in py


def test_normal_scenario_sets_both_split_counts():
    session = build_ontology_session()
    py, _ = translate_real_file(session)
    fn = compile_to_callable(py)
    order = SDOrderEntity(orderWgtHigh=Decimal("20"), productivity=Decimal("0.5"))
    slab = SDSlabEntity(secondWgtHigh=Decimal("100"))
    fn(order, slab)
    assert slab.maxSplitCountUpper == 10
    assert slab.currentSplitCount == 10


def test_boundary_scenario_ceil_to_1():
    session = build_ontology_session()
    py, _ = translate_real_file(session)
    fn = compile_to_callable(py)
    order = SDOrderEntity(orderWgtHigh=Decimal("1"), productivity=Decimal("1"))
    slab = SDSlabEntity(secondWgtHigh=Decimal("0.3"))
    fn(order, slab)
    assert slab.maxSplitCountUpper == 1
    assert slab.currentSplitCount == 1


def test_error_scenario_raises_algorithm_exception():
    session = build_ontology_session()
    py, _ = translate_real_file(session)
    fn = compile_to_callable(py)
    order = SDOrderEntity(orderWgtHigh=Decimal("1"), productivity=Decimal("1"))
    slab = SDSlabEntity(secondWgtHigh=Decimal("0"))
    import pytest
    with pytest.raises(AlgorithmException) as exc_info:
        fn(order, slab)
    assert exc_info.value.step_no == 7
    assert exc_info.value.step_name == "MAX_SPLIT_COUNT"
    assert exc_info.value.code == "ALG_ITERATION_NEEDED"
    # Slab setters not invoked on error path
    assert slab.maxSplitCountUpper is None
    assert slab.currentSplitCount is None


def test_run_all_scenarios_pass():
    """Full demo run via run_scenario() — all 3 scenarios PASS for value + side-effects."""
    session = build_ontology_session()
    py, _ = translate_real_file(session)
    fn = compile_to_callable(py)
    for scenario in make_scenarios():
        value_verdict, side_verdict = run_scenario(fn, scenario)
        assert value_verdict.startswith("PASS"), f"{scenario.name}: value={value_verdict}"
        assert side_verdict.startswith("PASS"), f"{scenario.name}: side={side_verdict}"


def test_main_exits_zero():
    """Demo's main() returns 0 (all scenarios + side-effects PASS)."""
    assert main() == 0
