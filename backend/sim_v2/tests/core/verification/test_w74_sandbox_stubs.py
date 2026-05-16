"""W74 — Sandbox stubs unit tests."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.verification.sandbox_stubs import (
    build_stub_namespace,
    classify_unbound,
    derive_anchor_constants,
    derive_class_stub,
    derive_entity_stub_from_code_types,
    derive_repository_stub,
    find_unbound_names,
    is_bean_name,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE anchor_bindings (
                anchor_locator TEXT,
                code_method_fqn TEXT,
                repo_id TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE code_types (
                fqn TEXT, fields_json TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_anchor(engine, locator, fqn, repo_id="r"):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO anchor_bindings(anchor_locator, code_method_fqn, "
                "repo_id) VALUES (:a, :f, :r)"
            ),
            {"a": locator, "f": fqn, "r": repo_id},
        )


def _insert_code_type(engine, fqn, fields, repo_id="r"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO code_types(fqn, fields_json, repo_id) "
                 "VALUES (:f, :j, :r)"),
            {"f": fqn, "j": json.dumps(fields), "r": repo_id},
        )


# ─────────────────────────────────────────────────────────────────────────────
# 1) derive_anchor_constants
# ─────────────────────────────────────────────────────────────────────────────


def test_const_int_value(fixture_db):
    _insert_anchor(fixture_db, "MAX_RETRIES = 5", "fqn")
    with Session(fixture_db) as s:
        out = derive_anchor_constants(s, "fqn", "r")
    assert out == {"MAX_RETRIES": 5}


def test_const_float_value(fixture_db):
    _insert_anchor(fixture_db, "DEFAULT_PRODUCTIVITY = 0.95", "fqn")
    with Session(fixture_db) as s:
        out = derive_anchor_constants(s, "fqn", "r")
    assert out == {"DEFAULT_PRODUCTIVITY": 0.95}


def test_const_string_value(fixture_db):
    _insert_anchor(fixture_db, 'STATUS = "ACTIVE"', "fqn")
    with Session(fixture_db) as s:
        out = derive_anchor_constants(s, "fqn", "r")
    assert out == {"STATUS": "ACTIVE"}


def test_const_boolean_value(fixture_db):
    _insert_anchor(fixture_db, "ENABLED = true", "fqn")
    _insert_anchor(fixture_db, "DISABLED = false", "fqn")
    with Session(fixture_db) as s:
        out = derive_anchor_constants(s, "fqn", "r")
    assert out == {"ENABLED": True, "DISABLED": False}


def test_const_null_value(fixture_db):
    _insert_anchor(fixture_db, "EMPTY = null", "fqn")
    with Session(fixture_db) as s:
        out = derive_anchor_constants(s, "fqn", "r")
    assert out == {"EMPTY": None}


def test_const_bigdecimal_value(fixture_db):
    _insert_anchor(fixture_db, 'PRICE = new BigDecimal("99.5")', "fqn")
    with Session(fixture_db) as s:
        out = derive_anchor_constants(s, "fqn", "r")
    assert out == {"PRICE": Decimal("99.5")}


def test_const_with_java_suffix(fixture_db):
    _insert_anchor(fixture_db, "MAX_F = 99.5f", "fqn")
    _insert_anchor(fixture_db, "MAX_L = 999L", "fqn")
    with Session(fixture_db) as s:
        out = derive_anchor_constants(s, "fqn", "r")
    assert out["MAX_F"] == 99.5
    assert out["MAX_L"] == 999


def test_non_constant_anchor_skipped(fixture_db):
    """`product = product.multiply(p)` is reassignment, not const def."""
    _insert_anchor(fixture_db, "product = product.multiply(p)", "fqn")
    _insert_anchor(fixture_db, "confirmedPlantCd == null", "fqn")
    _insert_anchor(fixture_db, "return v != null ? v : DEFAULT;", "fqn")
    with Session(fixture_db) as s:
        out = derive_anchor_constants(s, "fqn", "r")
    assert out == {}    # uppercase-only pattern → nothing matches


def test_multiple_methods_isolated(fixture_db):
    _insert_anchor(fixture_db, "A = 1", "m1")
    _insert_anchor(fixture_db, "B = 2", "m2")
    with Session(fixture_db) as s:
        assert derive_anchor_constants(s, "m1", "r") == {"A": 1}
        assert derive_anchor_constants(s, "m2", "r") == {"B": 2}


def test_empty_anchor_skipped(fixture_db):
    _insert_anchor(fixture_db, "", "fqn")
    _insert_anchor(fixture_db, None, "fqn")
    with Session(fixture_db) as s:
        out = derive_anchor_constants(s, "fqn", "r")
    assert out == {}


# ─────────────────────────────────────────────────────────────────────────────
# 2) Class / repository stubs
# ─────────────────────────────────────────────────────────────────────────────


def test_class_stub_callable():
    """Java ctor `Foo(args)` → calling stub returns a child MagicMock."""
    stub = derive_class_stub("Foo")
    obj = stub("a", "b")
    assert isinstance(obj, MagicMock)
    # Attribute access tolerates anything (default MagicMock behaviour)
    obj.someProperty
    obj.someMethod("x")


def test_class_stub_with_spec_fields():
    """Spec'd stub blocks unknown attrs."""
    stub = derive_class_stub("Order", fields=["id", "status"])
    obj = stub()
    obj.id      # OK
    obj.status  # OK
    with pytest.raises(AttributeError):
        obj.no_such_field


def test_repository_stub_method_chains():
    """`repo.findById(x).orElse(y)` should not raise."""
    repo = derive_repository_stub("orderRepository")
    out = repo.findById("o1").orElse(None)
    assert isinstance(out, MagicMock)


def test_derive_entity_stub_from_code_types(fixture_db):
    _insert_code_type(
        fixture_db,
        "com.x.Order",
        [{"name": "id", "type": "String"},
         {"name": "amount", "type": "BigDecimal"}],
    )
    with Session(fixture_db) as s:
        stub = derive_entity_stub_from_code_types(s, "com.x.Order", "r")
    obj = stub()
    obj.id
    obj.amount
    with pytest.raises(AttributeError):
        obj.invalid_field


def test_derive_entity_stub_missing_class_falls_back(fixture_db):
    with Session(fixture_db) as s:
        stub = derive_entity_stub_from_code_types(s, "com.x.NoSuch", "r")
    # No spec → permissive
    obj = stub()
    obj.anything_at_all


# ─────────────────────────────────────────────────────────────────────────────
# 3) is_bean_name + classify_unbound
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name,expected", [
    ("orderRepository", True),
    ("userService", True),
    ("xmlMapper", True),
    ("paymentClient", True),
    ("orderManager", True),
    ("validationHelper", True),
    ("OrderRepository", False),    # uppercase first → not a bean
    ("repository", False),         # no suffix beyond itself
    ("util", False),
    ("", False),
])
def test_is_bean_name(name, expected):
    assert is_bean_name(name) == expected


@pytest.mark.parametrize("name,expected", [
    ("OrderEntity",       "class"),
    ("ValidationResult",  "class"),
    ("orderRepository",   "bean"),
    ("driverService",     "bean"),
    ("lookup",            "unknown"),
    ("",                  "unknown"),
])
def test_classify_unbound(name, expected):
    assert classify_unbound(name) == expected


# ─────────────────────────────────────────────────────────────────────────────
# 4) find_unbound_names — AST-based detection
# ─────────────────────────────────────────────────────────────────────────────


def test_find_unbound_finds_class_ref():
    src = (
        "def f(self, x):\n"
        "    return ValidationResult(False, x)\n"
    )
    out = find_unbound_names(src)
    assert "ValidationResult" in out


def test_find_unbound_excludes_locals():
    src = (
        "def f(self, x):\n"
        "    y = x + 1\n"
        "    return y\n"
    )
    out = find_unbound_names(src)
    assert "y" not in out
    assert "x" not in out
    assert "self" not in out


def test_find_unbound_excludes_builtins():
    src = (
        "def f(self, xs):\n"
        "    return len(xs) + max(0, 1)\n"
    )
    out = find_unbound_names(src)
    assert "len" not in out
    assert "max" not in out


def test_find_unbound_excludes_decimal_and_math():
    src = (
        "def f(self, x):\n"
        "    return Decimal('0.5') * math.pi\n"
    )
    out = find_unbound_names(src)
    assert "Decimal" not in out
    assert "math" not in out


def test_find_unbound_syntax_error_returns_empty():
    src = "def whoops( ): return ! ! !"
    assert find_unbound_names(src) == set()


def test_find_unbound_handles_for_loop_var():
    src = (
        "def f(self, xs):\n"
        "    for x in xs:\n"
        "        print(x)\n"
    )
    out = find_unbound_names(src)
    assert "x" not in out


def test_find_unbound_handles_imports():
    src = (
        "from x import Y\n"
        "import z\n"
        "def f(self): return Y() + z.thing\n"
    )
    out = find_unbound_names(src)
    assert "Y" not in out
    assert "z" not in out


# ─────────────────────────────────────────────────────────────────────────────
# 5) build_stub_namespace — integrated
# ─────────────────────────────────────────────────────────────────────────────


def test_build_stub_namespace_anchor_plus_class(fixture_db):
    _insert_anchor(fixture_db, "DEFAULT_PRODUCTIVITY = 0.95", "method")
    src = (
        "def cumulativeProductivity(self, cmpCd):\n"
        "    if cmpCd == None:\n"
        "        return DEFAULT_PRODUCTIVITY\n"
        "    return ValidationResult(True, cmpCd)\n"
    )
    with Session(fixture_db) as s:
        ns = build_stub_namespace(s, "method", "r", src)
    assert ns["DEFAULT_PRODUCTIVITY"] == 0.95
    assert "ValidationResult" in ns
    assert isinstance(ns["ValidationResult"], MagicMock)


def test_build_stub_namespace_beans(fixture_db):
    src = (
        "def find(self, k):\n"
        "    return groupRepository.findById(k).orElse(specRepository)\n"
    )
    with Session(fixture_db) as s:
        ns = build_stub_namespace(s, "method", "r", src)
    assert "groupRepository" in ns
    assert "specRepository" in ns


def test_build_stub_namespace_anchor_overrides_unbound(fixture_db):
    """If anchor already provides DEFAULT, don't override it with MagicMock."""
    _insert_anchor(fixture_db, "DEFAULT = 99", "method")
    src = (
        "def f(self):\n"
        "    return DEFAULT\n"
    )
    with Session(fixture_db) as s:
        ns = build_stub_namespace(s, "method", "r", src)
    assert ns["DEFAULT"] == 99


def test_build_stub_namespace_with_entity_lookup(fixture_db):
    _insert_code_type(
        fixture_db, "com.x.Order",
        [{"name": "id", "type": "String"}],
    )
    src = (
        "def f(self):\n"
        "    return Order()\n"
    )
    with Session(fixture_db) as s:
        ns = build_stub_namespace(
            s, "method", "r", src,
            code_types_lookup_fqns={"Order": "com.x.Order"},
        )
    obj = ns["Order"]()
    obj.id    # ok
    with pytest.raises(AttributeError):
        obj.no_such_field
