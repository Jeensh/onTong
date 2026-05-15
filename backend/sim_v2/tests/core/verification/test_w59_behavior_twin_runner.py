"""W59 — Behavior-level twin runner tests."""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixture,
    BehaviorFixtureStore,
    BehaviorTwinRunner,
    compare_outputs,
)
from backend.sim_v2.core.verification.engine import VerificationEngine
from backend.sim_v2.core.verification.oracle import OracleRequest


# ─────────────────────────────────────────────────────────────────────────────
# compare_outputs — direct
# ─────────────────────────────────────────────────────────────────────────────


def test_compare_int_exact_match():
    d = compare_outputs(3, 3)
    assert d.is_equivalent
    assert d.summary == "match"


def test_compare_int_diff():
    d = compare_outputs(3, 4)
    assert not d.is_equivalent
    assert "diverge" in d.summary


def test_compare_float_within_tolerance():
    d = compare_outputs(1.0, 1.0001, tolerance=0.001)
    assert d.is_equivalent


def test_compare_float_outside_tolerance():
    d = compare_outputs(1.0, 1.01, tolerance=0.001)
    assert not d.is_equivalent


def test_compare_decimal_float_cross_type():
    """Decimal(`3`) vs float(3.0) — should compare numerically."""
    d = compare_outputs(Decimal("3"), 3.0)
    assert d.is_equivalent


def test_compare_string_match():
    d = compare_outputs("hello", "hello")
    assert d.is_equivalent


def test_compare_string_diff():
    d = compare_outputs("hello", "world")
    assert not d.is_equivalent


def test_compare_list_match():
    d = compare_outputs([1, 2, 3], [1, 2, 3])
    assert d.is_equivalent


def test_compare_list_length_diff():
    d = compare_outputs([1, 2], [1, 2, 3])
    assert not d.is_equivalent
    assert "length" in d.summary


def test_compare_list_element_diff():
    d = compare_outputs([1, 2, 3], [1, 9, 3])
    assert not d.is_equivalent
    assert "[1]" in d.summary


def test_compare_dict_match():
    d = compare_outputs({"a": 1, "b": 2}, {"a": 1, "b": 2})
    assert d.is_equivalent


def test_compare_dict_key_diff():
    d = compare_outputs({"a": 1}, {"a": 1, "b": 2})
    assert not d.is_equivalent
    assert "key" in d.summary


def test_compare_dict_value_diff():
    d = compare_outputs({"a": 1}, {"a": 2})
    assert not d.is_equivalent


def test_compare_nested_list_in_dict():
    d = compare_outputs({"xs": [1, 2]}, {"xs": [1, 3]})
    assert not d.is_equivalent
    assert "xs" in d.summary
    assert "[1]" in d.summary


def test_compare_type_mismatch_non_numeric():
    d = compare_outputs("3", 3)
    assert not d.is_equivalent
    assert "type mismatch" in d.summary


def test_compare_nan_to_nan():
    d = compare_outputs(float("nan"), float("nan"))
    assert d.is_equivalent  # NaN == NaN by special case


# ─────────────────────────────────────────────────────────────────────────────
# BehaviorFixtureStore
# ─────────────────────────────────────────────────────────────────────────────


def _src_add():
    return (
        "def add(a, b):\n"
        "    return a + b\n"
    )


def _fix(fid: str, *, args=(1, 2), expected=3, source=None,
         function_name="add", tolerance=0.0, kwargs=None):
    return BehaviorFixture(
        fixture_id=fid,
        python_source=source or _src_add(),
        function_name=function_name,
        input_args=tuple(args),
        input_kwargs=dict(kwargs or {}),
        expected_output=expected,
        tolerance=tolerance,
    )


def test_store_add_and_get():
    s = BehaviorFixtureStore([_fix("f1")])
    assert s.get("f1").fixture_id == "f1"
    assert s.get("missing") is None


def test_store_rejects_duplicate_id():
    s = BehaviorFixtureStore([_fix("f1")])
    with pytest.raises(ValueError):
        s.add(_fix("f1"))


def test_store_ids():
    s = BehaviorFixtureStore([_fix("a"), _fix("b")])
    assert set(s.ids()) == {"a", "b"}


# ─────────────────────────────────────────────────────────────────────────────
# Runner — per-status
# ─────────────────────────────────────────────────────────────────────────────


def test_pass_when_output_matches():
    runner = BehaviorTwinRunner(BehaviorFixtureStore([_fix("pass")]))
    r = runner.run_fixture("pass", plugin="", apply_diffs={})
    assert r.status == "PASS"
    assert r.python_proposal_output == 3
    assert r.error is None


def test_fail_output_when_diverges():
    runner = BehaviorTwinRunner(BehaviorFixtureStore([_fix("bad", expected=99)]))
    r = runner.run_fixture("bad", plugin="", apply_diffs={})
    assert r.status == "FAIL_OUTPUT"
    assert r.python_proposal_output == 3
    assert "diverge" in r.output_diff.summary


def test_error_on_runtime_exception():
    src = "def boom(a, b):\n    raise ValueError('nope')\n"
    runner = BehaviorTwinRunner(BehaviorFixtureStore([
        _fix("err", source=src, function_name="boom", expected=None),
    ]))
    r = runner.run_fixture("err", plugin="", apply_diffs={})
    assert r.status == "ERROR"
    assert "ValueError" in r.error


def test_error_on_syntax_error():
    src = "def broken(a, b\n    return a\n"   # missing close paren
    runner = BehaviorTwinRunner(BehaviorFixtureStore([
        _fix("syn", source=src, function_name="broken", expected=None),
    ]))
    r = runner.run_fixture("syn", plugin="", apply_diffs={})
    assert r.status == "ERROR"
    assert "compile" in r.error


def test_error_when_function_name_missing():
    src = "def add(a, b):\n    return a + b\n"
    runner = BehaviorTwinRunner(BehaviorFixtureStore([
        _fix("wrong_name", source=src, function_name="multiply", expected=None),
    ]))
    r = runner.run_fixture("wrong_name", plugin="", apply_diffs={})
    assert r.status == "ERROR"
    assert "multiply" in r.error


def test_error_when_fixture_id_unknown():
    runner = BehaviorTwinRunner(BehaviorFixtureStore([]))
    r = runner.run_fixture("nope", plugin="", apply_diffs={})
    assert r.status == "ERROR"
    assert "unknown fixture_id" in r.error


def test_pass_with_kwargs():
    src = "def f(a, b=10):\n    return a + b\n"
    runner = BehaviorTwinRunner(BehaviorFixtureStore([
        _fix("kw", source=src, function_name="f",
             args=(1,), kwargs={"b": 41}, expected=42),
    ]))
    r = runner.run_fixture("kw", plugin="", apply_diffs={})
    assert r.status == "PASS"


def test_pass_with_decimal_arithmetic():
    """Verifies Decimal works in the sandbox."""
    src = (
        "def add_decimal(a, b):\n"
        "    return Decimal(a) + Decimal(b)\n"
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([
        _fix("dec", source=src, function_name="add_decimal",
             args=("1.5", "2.5"), expected=Decimal("4.0")),
    ]))
    r = runner.run_fixture("dec", plugin="", apply_diffs={})
    assert r.status == "PASS"


def test_sandbox_blocks_import():
    """Twin code that tries to import should ERROR (no __import__ in builtins)."""
    src = (
        "def evil():\n"
        "    import os\n"
        "    return os.getcwd()\n"
    )
    runner = BehaviorTwinRunner(BehaviorFixtureStore([
        _fix("evil", source=src, function_name="evil", args=(), expected=None),
    ]))
    r = runner.run_fixture("evil", plugin="", apply_diffs={})
    assert r.status == "ERROR"


def test_pass_with_tolerance():
    src = "def f(x):\n    return x * 0.1 + x * 0.2\n"
    runner = BehaviorTwinRunner(BehaviorFixtureStore([
        _fix("tol", source=src, function_name="f",
             args=(10,), expected=3.0, tolerance=1e-9),
    ]))
    r = runner.run_fixture("tol", plugin="", apply_diffs={})
    # Floating point arithmetic: 10*0.1 + 10*0.2 == 3.0000000000000004
    assert r.status == "PASS"


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end with VerificationEngine
# ─────────────────────────────────────────────────────────────────────────────


def test_engine_aggregates_pass():
    fixtures = [_fix("f1"), _fix("f2", expected=3)]
    runner = BehaviorTwinRunner(BehaviorFixtureStore(fixtures))
    engine = VerificationEngine(fixture_runner=runner, plugin="test")
    req = OracleRequest(proposal_id="p1", fixture_subset=["f1", "f2"])
    result = engine.run_oracle(req)
    assert result.aggregate_status == "PASS"
    assert len(result.by_fixture) == 2


def test_engine_aggregates_fail_breaking():
    fixtures = [_fix("good"), _fix("bad", expected=999)]
    runner = BehaviorTwinRunner(BehaviorFixtureStore(fixtures))
    engine = VerificationEngine(fixture_runner=runner, plugin="test")
    req = OracleRequest(proposal_id="p1", fixture_subset=["good", "bad"])
    result = engine.run_oracle(req)
    assert result.aggregate_status == "FAIL_BREAKING"


def test_engine_aggregates_inconclusive():
    src = "def boom():\n    raise RuntimeError('x')\n"
    fixtures = [_fix("err", source=src, function_name="boom",
                     args=(), expected=None)]
    runner = BehaviorTwinRunner(BehaviorFixtureStore(fixtures))
    engine = VerificationEngine(fixture_runner=runner, plugin="test")
    req = OracleRequest(proposal_id="p1", fixture_subset=["err"])
    result = engine.run_oracle(req)
    assert result.aggregate_status == "INCONCLUSIVE"


# ─────────────────────────────────────────────────────────────────────────────
# Real-translator round-trip — Java → Python → exec → diff
# ─────────────────────────────────────────────────────────────────────────────


def test_real_translation_round_trip_simple_method():
    """Translate a tiny Java method via JavaToPythonTranslator and verify
    the emitted Python actually runs and produces the expected output."""
    import tree_sitter_java as tsjava
    from tree_sitter import Language, Parser

    java_src = """
    public class Calc {
        public int addPositives(int a, int b) {
            int x = a;
            if (x < 0) { x = 0; }
            int y = b;
            if (y < 0) { y = 0; }
            return x + y;
        }
    }
    """

    java_lang = Language(tsjava.language())
    tree = Parser(java_lang).parse(java_src.encode())
    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    method = m
                    break
    assert method is not None

    from backend.sim_v2.core.synthesizer.java_translator import (
        JavaToPythonTranslator,
    )
    translator = JavaToPythonTranslator()
    result = translator.translate(method, indent=0)
    python_source = result.python_source
    assert "def addPositives" in python_source or "def add_positives" in python_source

    # Find which name was emitted
    function_name = (
        "addPositives" if "def addPositives" in python_source
        else "add_positives"
    )

    # Translator emits instance methods with `self` first → pass None for self.
    runner = BehaviorTwinRunner(BehaviorFixtureStore([
        BehaviorFixture(
            fixture_id="both_pos",
            python_source=python_source,
            function_name=function_name,
            input_args=(None, 3, 5),
            input_kwargs={},
            expected_output=8,
        ),
        BehaviorFixture(
            fixture_id="one_neg",
            python_source=python_source,
            function_name=function_name,
            input_args=(None, -2, 5),
            input_kwargs={},
            expected_output=5,
        ),
    ]))
    r1 = runner.run_fixture("both_pos", plugin="", apply_diffs={})
    r2 = runner.run_fixture("one_neg", plugin="", apply_diffs={})
    assert r1.status == "PASS", r1.error or r1.output_diff.summary
    assert r2.status == "PASS", r2.error or r2.output_diff.summary
