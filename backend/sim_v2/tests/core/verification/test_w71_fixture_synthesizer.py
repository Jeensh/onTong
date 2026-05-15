"""W71 — Production fixture synthesizer tests."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    load_actions,
)
from backend.sim_v2.core.verification.fixture_synthesizer import (
    FixtureSynthesisReport,
    PRIMITIVE_TYPES,
    synthesize_fixtures_for_action,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


_SRC_TWO_STRINGS = (
    "def f(self, a, b):\n"
    "    return a + b\n"
)

_SRC_ONE_INT = (
    "def g(self, n):\n"
    "    return n * 2\n"
)

_SRC_ZERO_ARG = (
    "def h(self):\n"
    "    return 42\n"
)


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE actions (
                fqn TEXT, params_json TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_action(engine, fqn, params, repo_id="r"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO actions(fqn, params_json, repo_id) "
                 "VALUES (:f, :p, :r)"),
            {"f": fqn, "p": json.dumps(params), "r": repo_id},
        )


def _action(fqn, code_method_fqn=None, repo_id="r"):
    return ActionView(
        fqn=fqn, label="", code_method_fqn=code_method_fqn, repo_id=repo_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-primitive boundary value tests
# ─────────────────────────────────────────────────────────────────────────────


def test_two_string_params_produce_multiple_fixtures(fixture_db):
    _insert_action(fixture_db, "a.x", [
        {"name": "a", "type": "string"},
        {"name": "b", "type": "string"},
    ])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.f()"),
            function_name="f", python_source=_SRC_TWO_STRINGS,
        )
    # 6 string values × 6 string values capped at 12
    assert len(r.fixtures) == 12
    assert r.synthesizable_params == 2
    assert r.skipped_params == 0


def test_string_fixtures_include_boundary_values(fixture_db):
    _insert_action(fixture_db, "a.x", [{"name": "a", "type": "string"}])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.f()"),
            function_name="f", python_source=_SRC_TWO_STRINGS,
        )
    args = [f.input_args[1] for f in r.fixtures]
    assert "" in args
    assert "테스트" in args


def test_int_fixtures_include_max_min(fixture_db):
    import sys
    _insert_action(fixture_db, "a.x", [{"name": "n", "type": "int"}])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.g()"),
            function_name="g", python_source=_SRC_ONE_INT,
        )
    args = [f.input_args[1] for f in r.fixtures]
    assert 0 in args
    assert -1 in args
    assert sys.maxsize in args


def test_decimal_fixtures_use_decimal_type(fixture_db):
    _insert_action(fixture_db, "a.x", [{"name": "v", "type": "decimal"}])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.f()"),
            function_name="f", python_source=_SRC_ONE_INT,
        )
    args = [f.input_args[1] for f in r.fixtures]
    assert any(isinstance(a, Decimal) for a in args)


def test_boolean_produces_two_fixtures(fixture_db):
    _insert_action(fixture_db, "a.x", [{"name": "flag", "type": "boolean"}])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.f()"),
            function_name="f", python_source=_SRC_ONE_INT,
        )
    assert len(r.fixtures) == 2
    args = [f.input_args[1] for f in r.fixtures]
    assert set(args) == {True, False}


# ─────────────────────────────────────────────────────────────────────────────
# Zero-arg + object_ref + mixed
# ─────────────────────────────────────────────────────────────────────────────


def test_zero_arg_method_produces_single_fixture(fixture_db):
    _insert_action(fixture_db, "a.x", [])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.h()"),
            function_name="h", python_source=_SRC_ZERO_ARG,
        )
    assert len(r.fixtures) == 1
    assert r.fixtures[0].input_args == (None,)
    assert r.synthesizable_params == 0
    assert r.skipped_params == 0


def test_object_ref_param_uses_null(fixture_db):
    _insert_action(fixture_db, "a.x", [
        {"name": "order", "type": "object_ref",
         "object_ref_term": "term.scm.order.order"},
    ])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.f()"),
            function_name="f", python_source=_SRC_ONE_INT,
        )
    assert r.synthesizable_params == 0
    assert r.skipped_params == 1
    # Single fixture with None placeholder
    assert len(r.fixtures) == 1
    assert r.fixtures[0].input_args == (None, None)
    assert "object_ref" in r.reason


def test_mixed_params_synthesize_primitive_dimensions(fixture_db):
    """Mixed primitive + object_ref: vary primitive, null object_ref."""
    _insert_action(fixture_db, "a.x", [
        {"name": "code", "type": "string"},
        {"name": "order", "type": "object_ref",
         "object_ref_term": "term.scm.order"},
    ])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.f()"),
            function_name="f", python_source=_SRC_TWO_STRINGS,
        )
    assert r.synthesizable_params == 1
    assert r.skipped_params == 1
    # 6 string values × 1 null = 6 fixtures
    assert len(r.fixtures) == 6
    # Every fixture's object_ref slot is None
    for f in r.fixtures:
        assert f.input_args[2] is None


def test_max_combinations_caps_explosion(fixture_db):
    """3 string params would yield 6^3 = 216 combos; capped at 12."""
    _insert_action(fixture_db, "a.x", [
        {"name": "a", "type": "string"},
        {"name": "b", "type": "string"},
        {"name": "c", "type": "string"},
    ])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.f()"),
            function_name="f", python_source=_SRC_TWO_STRINGS,
            max_combinations=12,
        )
    assert len(r.fixtures) == 12


def test_unknown_param_type_treated_as_object_ref(fixture_db):
    _insert_action(fixture_db, "a.x", [
        {"name": "x", "type": "WeirdType"},
    ])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.f()"),
            function_name="f", python_source=_SRC_ONE_INT,
        )
    assert r.skipped_params == 1
    assert r.fixtures[0].input_args == (None, None)


def test_missing_action_returns_empty(fixture_db):
    """Action not in DB → empty params → single zero-arg fixture (degenerate)."""
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("missing.action", "com.x.f()"),
            function_name="f", python_source=_SRC_ZERO_ARG,
        )
    assert len(r.fixtures) == 1
    assert r.fixtures[0].input_args == (None,)


def test_fixture_carries_python_source(fixture_db):
    _insert_action(fixture_db, "a.x", [{"name": "n", "type": "int"}])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.g()"),
            function_name="g", python_source=_SRC_ONE_INT,
        )
    for f in r.fixtures:
        assert f.python_source == _SRC_ONE_INT
        assert f.function_name == "g"


def test_fixture_ids_are_unique(fixture_db):
    _insert_action(fixture_db, "a.x", [{"name": "n", "type": "int"}])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.g()"),
            function_name="g", python_source=_SRC_ONE_INT,
        )
    ids = {f.fixture_id for f in r.fixtures}
    assert len(ids) == len(r.fixtures)


def test_self_value_passes_through(fixture_db):
    _insert_action(fixture_db, "a.x", [{"name": "n", "type": "int"}])
    with Session(fixture_db) as session:
        r = synthesize_fixtures_for_action(
            session, _action("a.x", "com.x.g()"),
            function_name="g", python_source=_SRC_ONE_INT,
            self_value="my-self-obj",
        )
    for f in r.fixtures:
        assert f.input_args[0] == "my-self-obj"


def test_primitive_set_constant_includes_all_expected():
    assert "string" in PRIMITIVE_TYPES
    assert "decimal" in PRIMITIVE_TYPES
    assert "object_ref" not in PRIMITIVE_TYPES


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_production_action_fail_synthesizes_fixtures():
    """`action.scm.fail` declares (errorCode:string, message:string) — both
    primitive → should produce 12 fixtures (6 x 6 capped)."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real-v2")
        target = next(
            a for a in actions if a.fqn == "action.scm.fail"
        )
        r = synthesize_fixtures_for_action(
            session, target,
            function_name="fail_", python_source=_SRC_TWO_STRINGS,
        )
        assert r.synthesizable_params == 2
        assert len(r.fixtures) == 12
    finally:
        session.close()


@requires_production_db
def test_production_record_step_action_has_skipped_params():
    """`action.scm.record_step` includes order:object_ref (skipped)."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real-v2")
        target = next(a for a in actions if a.fqn == "action.scm.record_step")
        r = synthesize_fixtures_for_action(
            session, target,
            function_name="record_step", python_source=_SRC_TWO_STRINGS,
        )
        assert r.skipped_params > 0
    finally:
        session.close()
