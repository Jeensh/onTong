"""bigdecimal_mapper unit tests — W7.2.

Lesson 1 §4 의 5 KNOWN_DIVERGENCE 회피 mapping 검증.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.bigdecimal_mapper import (
    REQUIRED_IMPORTS,
    binary_op_symbol,
    is_binary_op,
    is_comparison,
    map_bigdecimal_constructor,
    map_bigdecimal_method,
    map_static_field,
)


# ─────────────────────────────────────────────────────────────────────────────
# Binary ops
# ─────────────────────────────────────────────────────────────────────────────


def test_is_binary_op_recognizes_arithmetic():
    assert is_binary_op("add")
    assert is_binary_op("subtract")
    assert is_binary_op("multiply")
    assert is_binary_op("divide")
    assert is_binary_op("remainder")


def test_is_binary_op_rejects_others():
    assert not is_binary_op("compareTo")
    assert not is_binary_op("setScale")
    assert not is_binary_op("unknownMethod")


def test_binary_op_symbol():
    assert binary_op_symbol("add") == "+"
    assert binary_op_symbol("subtract") == "-"
    assert binary_op_symbol("multiply") == "*"
    assert binary_op_symbol("divide") == "/"
    assert binary_op_symbol("remainder") == "%"


# ─────────────────────────────────────────────────────────────────────────────
# Method mapping
# ─────────────────────────────────────────────────────────────────────────────


def test_map_add():
    result = map_bigdecimal_method("a", "add", ["b"])
    assert result == "(a + b)"


def test_map_multiply_with_math_context():
    result = map_bigdecimal_method("a", "multiply", ["b", "DECIMAL64"])
    # 2-arg multiply — context arg is hint to caller; binary op handler uses first arg only
    assert result == "(a * b)"


def test_map_compare_to():
    result = map_bigdecimal_method("a", "compareTo", ["b"])
    # Sign-of-diff: (a>b) - (a<b)
    assert result == "((a > b) - (a < b))"


def test_map_equals():
    result = map_bigdecimal_method("a", "equals", ["b"])
    assert result == "(a == b)"


def test_map_set_scale_with_rounding():
    result = map_bigdecimal_method("a", "setScale", ["2", "RoundingMode.HALF_UP"])
    assert "bd_set_scale" in result
    assert "RoundingMode.HALF_UP" in result


def test_map_set_scale_without_rounding():
    result = map_bigdecimal_method("a", "setScale", ["3"])
    assert "bd_set_scale" in result
    assert "RoundingMode." not in result


def test_map_negate():
    assert map_bigdecimal_method("a", "negate", []) == "(-a)"


def test_map_abs():
    assert map_bigdecimal_method("a", "abs", []) == "abs(a)"


def test_map_int_value():
    assert map_bigdecimal_method("a", "intValue", []) == "int(a)"


def test_map_unmapped_returns_signature_locked_comment():
    result = map_bigdecimal_method("a", "stripTrailingZeros", [])
    assert result.startswith("# UNMAPPED")


# ─────────────────────────────────────────────────────────────────────────────
# Static field
# ─────────────────────────────────────────────────────────────────────────────


def test_map_static_zero():
    assert map_static_field("BigDecimal", "ZERO") == "Decimal(0)"
    assert map_static_field("BigDecimal", "ONE") == "Decimal(1)"
    assert map_static_field("BigDecimal", "TEN") == "Decimal(10)"


def test_map_math_context_decimal64():
    assert map_static_field("MathContext", "DECIMAL64") == "DECIMAL64"
    assert map_static_field("MathContext", "DECIMAL32") == "DECIMAL32"
    assert map_static_field("MathContext", "DECIMAL128") == "DECIMAL128"


def test_map_rounding_mode():
    assert map_static_field("RoundingMode", "HALF_UP") == "RoundingMode.HALF_UP"
    assert map_static_field("RoundingMode", "FLOOR") == "RoundingMode.FLOOR"
    assert map_static_field("RoundingMode", "HALF_EVEN") == "RoundingMode.HALF_EVEN"


def test_map_unknown_static_returns_none():
    assert map_static_field("BigDecimal", "WEIRD") is None


# ─────────────────────────────────────────────────────────────────────────────
# Constructor
# ─────────────────────────────────────────────────────────────────────────────


def test_constructor_with_string():
    assert map_bigdecimal_constructor(['"100"']) == 'Decimal("100")'


def test_constructor_with_int():
    assert map_bigdecimal_constructor(["100"]) == "Decimal(100)"


def test_constructor_empty():
    assert map_bigdecimal_constructor([]) == "Decimal()"


# ─────────────────────────────────────────────────────────────────────────────
# Required imports — emit always-include
# ─────────────────────────────────────────────────────────────────────────────


def test_required_imports_includes_contracts():
    assert "backend.sim_v2.core.contracts.base" in REQUIRED_IMPORTS


def test_is_comparison():
    assert is_comparison("compareTo")
    assert is_comparison("equals")
    assert not is_comparison("add")
