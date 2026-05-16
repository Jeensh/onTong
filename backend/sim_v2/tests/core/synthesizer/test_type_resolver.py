"""TypeResolver unit tests — W8.1."""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.type_resolver import (
    BigDecimalAwareResolver,
    CompositeTypeResolver,
    NullTypeResolver,
    is_bigdecimal_type,
)


# ─────────────────────────────────────────────────────────────────────────────
# NullTypeResolver
# ─────────────────────────────────────────────────────────────────────────────


def test_null_resolver_returns_none():
    r = NullTypeResolver()
    assert r.resolve_method_return_type("java.math.BigDecimal", "add") is None
    assert r.resolve_field_type("Foo", "bar") is None


# ─────────────────────────────────────────────────────────────────────────────
# BigDecimalAwareResolver — BigDecimal-returning methods
# ─────────────────────────────────────────────────────────────────────────────


def test_bd_add_returns_bigdecimal():
    r = BigDecimalAwareResolver()
    assert r.resolve_method_return_type("java.math.BigDecimal", "add") == "java.math.BigDecimal"
    assert r.resolve_method_return_type("BigDecimal", "add") == "java.math.BigDecimal"


def test_bd_chain_methods_return_bigdecimal():
    r = BigDecimalAwareResolver()
    for method in ("subtract", "multiply", "divide", "remainder",
                   "abs", "negate", "setScale", "round", "min", "max"):
        result = r.resolve_method_return_type("BigDecimal", method)
        assert result == "java.math.BigDecimal", f"{method} should return BigDecimal"


def test_bd_compareTo_returns_int():
    r = BigDecimalAwareResolver()
    assert r.resolve_method_return_type("BigDecimal", "compareTo") == "int"
    assert r.resolve_method_return_type("BigDecimal", "signum") == "int"


def test_bd_int_value_returns_int():
    r = BigDecimalAwareResolver()
    assert r.resolve_method_return_type("BigDecimal", "intValue") == "int"
    assert r.resolve_method_return_type("BigDecimal", "intValueExact") == "int"


def test_bd_long_value():
    r = BigDecimalAwareResolver()
    assert r.resolve_method_return_type("BigDecimal", "longValue") == "long"


def test_bd_double_value():
    r = BigDecimalAwareResolver()
    assert r.resolve_method_return_type("BigDecimal", "doubleValue") == "double"


def test_bd_equals_returns_boolean():
    r = BigDecimalAwareResolver()
    assert r.resolve_method_return_type("BigDecimal", "equals") == "boolean"


def test_bd_to_string_returns_string():
    r = BigDecimalAwareResolver()
    assert r.resolve_method_return_type("BigDecimal", "toString") == "java.lang.String"


def test_bd_unknown_method_returns_none():
    r = BigDecimalAwareResolver()
    assert r.resolve_method_return_type("BigDecimal", "weirdMethod") is None


def test_bd_resolver_does_not_handle_non_bigdecimal_receiver():
    r = BigDecimalAwareResolver()
    assert r.resolve_method_return_type("Foo", "add") is None
    assert r.resolve_method_return_type(None, "add") is None


def test_bd_static_field_types():
    r = BigDecimalAwareResolver()
    assert r.resolve_field_type("BigDecimal", "ZERO") == "java.math.BigDecimal"
    assert r.resolve_field_type("BigDecimal", "ONE") == "java.math.BigDecimal"
    assert r.resolve_field_type("BigDecimal", "TEN") == "java.math.BigDecimal"


def test_bd_unknown_field_returns_none():
    r = BigDecimalAwareResolver()
    assert r.resolve_field_type("BigDecimal", "WEIRD") is None
    assert r.resolve_field_type("Foo", "bar") is None


# ─────────────────────────────────────────────────────────────────────────────
# CompositeTypeResolver
# ─────────────────────────────────────────────────────────────────────────────


def test_composite_first_match_wins():
    class _FirstAlwaysReturns:
        def resolve_method_return_type(self, *a, **k):
            return "FirstHit"
        def resolve_field_type(self, *a, **k):
            return None

    class _SecondAlwaysReturns:
        def resolve_method_return_type(self, *a, **k):
            return "SecondHit"
        def resolve_field_type(self, *a, **k):
            return "SecondField"

    composite = CompositeTypeResolver([_FirstAlwaysReturns(), _SecondAlwaysReturns()])
    assert composite.resolve_method_return_type("X", "y") == "FirstHit"
    # field — first returns None, second returns SecondField
    assert composite.resolve_field_type("X", "y") == "SecondField"


def test_composite_all_none_returns_none():
    composite = CompositeTypeResolver([NullTypeResolver(), NullTypeResolver()])
    assert composite.resolve_method_return_type("Foo", "bar") is None


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────


def test_is_bigdecimal_type():
    assert is_bigdecimal_type("java.math.BigDecimal")
    assert is_bigdecimal_type("BigDecimal")
    assert not is_bigdecimal_type("int")
    assert not is_bigdecimal_type(None)
