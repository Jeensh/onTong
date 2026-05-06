"""H — RestrictedPython sandbox + SyntheticInputGenerator tests."""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.modeling.code_analysis.method_anchor import AnchorKind, MethodAnchor
from backend.modeling.simulation.sandbox_runner import (
    RestrictedPythonSandbox,
    SyntheticInputCase,
    SyntheticInputGenerator,
    _SampleDict,
    _default_value_for_type,
    _value_from_literal_anchor,
)


# ── helpers ───────────────────────────────────────────────────────────────
def _anchor(kind: str, locator: str, snippet: str = "") -> MethodAnchor:
    return MethodAnchor(
        method_fqn="x.y.M.f",
        kind=AnchorKind(kind),
        locator=locator,
        line=1,
        snippet=snippet,
    )


# ── _default_value_for_type ──────────────────────────────────────────────
def test_default_value_string():
    assert _default_value_for_type("String") == "TEST"


def test_default_value_decimal():
    assert _default_value_for_type("BigDecimal") == Decimal("1.00")


def test_default_value_int():
    assert _default_value_for_type("int") == 0


def test_default_value_bool():
    assert _default_value_for_type("Boolean") is False


def test_default_value_entity_returns_sample_dict():
    v = _default_value_for_type("SDOrderEntity")
    assert isinstance(v, dict)
    assert "slabWgtInProgress" in v        # sample 키


def test_default_value_none_returns_sample_dict():
    v = _default_value_for_type(None)
    assert isinstance(v, dict)


# ── _SampleDict 누락 키 fallback ─────────────────────────────────────────
def test_sample_dict_missing_key_fallback():
    d = _SampleDict({"a": 1})
    assert d["a"] == 1
    assert d["nonexistent"] == Decimal("1")  # 누락 키 → Decimal('1')


# ── _value_from_literal_anchor ────────────────────────────────────────────
def test_literal_anchor_int():
    a = _anchor("literal", "literal.x", "42")
    assert _value_from_literal_anchor(a) == 42


def test_literal_anchor_decimal():
    a = _anchor("literal", "literal.y", "3.14")
    assert _value_from_literal_anchor(a) == Decimal("3.14")


def test_literal_anchor_string():
    a = _anchor("literal", "literal.s", '"hello"')
    assert _value_from_literal_anchor(a) == "hello"


def test_literal_anchor_bool():
    a = _anchor("literal", "literal.b", "true")
    assert _value_from_literal_anchor(a) is True


# ── SyntheticInputGenerator ───────────────────────────────────────────────
def test_synthetic_default_case_only_when_no_anchors():
    gen = SyntheticInputGenerator()
    cases = gen.generate(method_fqn="x.M.f", param_specs=[{"name": "x", "type": "String"}], anchors=[], max_cases=3)
    assert len(cases) == 1
    assert cases[0].name == "기본 케이스"
    assert cases[0].args == ["TEST"]


def test_synthetic_literal_substitution():
    gen = SyntheticInputGenerator()
    anchors = [_anchor("literal", "literal.0", "100")]
    cases = gen.generate(
        method_fqn="x.M.f",
        param_specs=[{"name": "n", "type": "int"}],
        anchors=anchors,
        max_cases=3,
    )
    assert len(cases) == 2
    # 기본 0 → literal 100 으로 substitute 된 case 1 개 추가
    assert cases[1].args[0] == 100


# ── RestrictedPythonSandbox 실행 ─────────────────────────────────────────
def test_sandbox_simple_function():
    sb = RestrictedPythonSandbox()
    code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    cases = [SyntheticInputCase(name="기본", args=[3, 4])]
    results = sb.run(python_code=code, function_name="add", cases=cases, mock_calls=[])
    assert len(results) == 1
    assert results[0].return_value == 7
    assert results[0].exception is None


def test_sandbox_korean_variable_names():
    sb = RestrictedPythonSandbox()
    code = (
        "def 계산(슬라브중량, 두께):\n"
        "    면적 = 슬라브중량 * 두께\n"
        "    return 면적\n"
    )
    cases = [SyntheticInputCase(name="기본", args=[10, 5])]
    results = sb.run(python_code=code, function_name="계산", cases=cases, mock_calls=[])
    assert results[0].return_value == 50


def test_sandbox_decimal_arithmetic():
    sb = RestrictedPythonSandbox()
    code = (
        "from decimal import Decimal\n"
        "def 곱(x):\n"
        "    return x * Decimal('2')\n"
    )
    cases = [SyntheticInputCase(name="기본", args=[Decimal("5")])]
    results = sb.run(python_code=code, function_name="곱", cases=cases, mock_calls=[])
    assert results[0].return_value == "10"   # _safe_repr 가 Decimal → str


def test_sandbox_mock_call_default_none_for_find():
    sb = RestrictedPythonSandbox()
    code = (
        "def lookup(pk):\n"
        "    result = mock_repository_findById(pk)\n"
        "    if result is None:\n"
        "        return 'not_found'\n"
        "    return 'found'\n"
    )
    cases = [SyntheticInputCase(name="기본", args=["pk1"])]
    results = sb.run(python_code=code, function_name="lookup", cases=cases, mock_calls=["repository.findById"])
    assert results[0].return_value == "not_found"
    assert "repository.findById" in results[0].mock_calls_invoked


def test_sandbox_mutation_capture():
    sb = RestrictedPythonSandbox()
    code = (
        "def update(d: dict) -> None:\n"
        "    d['result'] = 999\n"
    )
    cases = [SyntheticInputCase(name="기본", args=[{"x": 1}])]
    results = sb.run(python_code=code, function_name="update", cases=cases, mock_calls=[])
    assert results[0].mutated_args.get(0, {}).get("result") == 999


def test_sandbox_exception_captured():
    sb = RestrictedPythonSandbox()
    code = "def boom():\n    raise ValueError('nope')\n"
    cases = [SyntheticInputCase(name="기본", args=[])]
    results = sb.run(python_code=code, function_name="boom", cases=cases, mock_calls=[])
    assert results[0].exception is not None
    assert "ValueError" in results[0].exception


def test_sandbox_compile_error_propagated():
    sb = RestrictedPythonSandbox()
    bad = "def f(:\n    pass\n"               # syntax error
    cases = [SyntheticInputCase(name="기본", args=[])]
    results = sb.run(python_code=bad, function_name="f", cases=cases, mock_calls=[])
    assert results[0].exception is not None
    assert "compile" in results[0].exception.lower() or "def exec" in results[0].exception.lower()


def test_sandbox_underscore_attr_blocked():
    sb = RestrictedPythonSandbox()
    code = (
        "def f():\n"
        "    return (1).__class__\n"          # underscore attr 차단됨
    )
    cases = [SyntheticInputCase(name="기본", args=[])]
    results = sb.run(python_code=code, function_name="f", cases=cases, mock_calls=[])
    # blocked 또는 RestrictedPython 에서 compile error
    assert results[0].exception is not None
