"""W63 — Exception agreement verifier tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    load_actions,
)
from backend.sim_v2.core.verification.exception_verifier import (
    ExceptionVerification,
    extract_declared_exceptions,
    extract_thrown_exceptions,
    verify_action_exceptions,
    verify_action_exceptions_batch,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE actions (
                fqn TEXT, effects_json TEXT, repo_id TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE code_methods (
                fqn TEXT, body_text TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_action(engine, fqn, effects, repo_id="r"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO actions(fqn, effects_json, repo_id) "
                 "VALUES (:f, :e, :r)"),
            {"f": fqn, "e": json.dumps(effects) if effects is not None else None,
             "r": repo_id},
        )


def _insert_method(engine, fqn, body_text, repo_id="r"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO code_methods(fqn, body_text, repo_id) "
                 "VALUES (:f, :b, :r)"),
            {"f": fqn, "b": body_text, "r": repo_id},
        )


def _action(fqn, code_method_fqn=None, repo_id="r"):
    return ActionView(
        fqn=fqn, label="", code_method_fqn=code_method_fqn, repo_id=repo_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# extract_thrown_exceptions
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_thrown_from_simple_throw():
    body = "if (x) { throw new IllegalStateException(\"oops\"); }"
    assert extract_thrown_exceptions(body) == ("IllegalStateException",)


def test_extract_thrown_strips_package_prefix():
    body = "throw new java.lang.IllegalStateException();"
    assert extract_thrown_exceptions(body) == ("IllegalStateException",)


def test_extract_thrown_strips_inner_class():
    body = "throw new Foo$BarException();"
    assert extract_thrown_exceptions(body) == ("BarException",)


def test_extract_thrown_dedupes():
    body = """
    if (a) throw new XException(1);
    else if (b) throw new XException(2);
    else throw new YException(3);
    """
    assert extract_thrown_exceptions(body) == ("XException", "YException")


def test_extract_thrown_handles_newline_after_new():
    body = "throw new\n    AlgorithmException(STEP_NO, STEP_NAME, code,\n        args);"
    assert extract_thrown_exceptions(body) == ("AlgorithmException",)


def test_extract_thrown_empty_for_no_throws():
    assert extract_thrown_exceptions("return x + 1;") == ()


def test_extract_thrown_empty_for_none():
    assert extract_thrown_exceptions(None) == ()


def test_extract_thrown_ignores_non_throw_new_pattern():
    """`new XException()` without preceding `throw` is not a throw."""
    body = "Exception e = new XException(); return e;"
    assert extract_thrown_exceptions(body) == ()


# ─────────────────────────────────────────────────────────────────────────────
# extract_declared_exceptions
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_declared_from_raises_kind():
    j = json.dumps([{"kind": "raises", "exception": "AlgorithmException"}])
    assert extract_declared_exceptions(j) == ("AlgorithmException",)


def test_extract_declared_from_throws_kind():
    j = json.dumps([{"kind": "throws", "exception": "XException"}])
    assert extract_declared_exceptions(j) == ("XException",)


def test_extract_declared_lenient_type_key():
    j = json.dumps([{"type": "raises", "exception": "XException"}])
    assert extract_declared_exceptions(j) == ("XException",)


def test_extract_declared_strips_fqn():
    j = json.dumps([{"kind": "raises", "exception": "com.x.Foo$BarException"}])
    assert extract_declared_exceptions(j) == ("BarException",)


def test_extract_declared_dedupes_and_sorts():
    j = json.dumps([
        {"kind": "raises", "exception": "Y"},
        {"kind": "raises", "exception": "X"},
        {"kind": "raises", "exception": "Y"},  # dup
    ])
    assert extract_declared_exceptions(j) == ("X", "Y")


def test_extract_declared_ignores_non_raises_entries():
    j = json.dumps([
        {"kind": "writes_table", "table": "T"},
        {"kind": "raises", "exception": "X"},
    ])
    assert extract_declared_exceptions(j) == ("X",)


def test_extract_declared_empty_for_none():
    assert extract_declared_exceptions(None) == ()


def test_extract_declared_empty_for_malformed_json():
    assert extract_declared_exceptions("{not json") == ()


def test_extract_declared_empty_for_non_list():
    assert extract_declared_exceptions(json.dumps({"kind": "raises"})) == ()


# ─────────────────────────────────────────────────────────────────────────────
# Per-status — verify_action_exceptions
# ─────────────────────────────────────────────────────────────────────────────


def test_no_recommendation_when_code_method_fqn_missing(fixture_db):
    a = _action("a.x")
    with Session(fixture_db) as session:
        v = verify_action_exceptions(session, a)
    assert v.status == "NO_RECOMMENDATION"


def test_method_not_found_when_no_code_row(fixture_db):
    _insert_action(fixture_db, "a.x", None)
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_exceptions(session, a)
    assert v.status == "METHOD_NOT_FOUND"


def test_verified_when_both_empty(fixture_db):
    _insert_action(fixture_db, "a.x", None)
    _insert_method(fixture_db, "com.x.foo()", "return 1;")
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_exceptions(session, a)
    assert v.status == "VERIFIED"
    assert v.declared == ()
    assert v.thrown == ()


def test_verified_when_both_match(fixture_db):
    _insert_action(fixture_db, "a.x", [
        {"kind": "raises", "exception": "AlgorithmException"},
    ])
    _insert_method(fixture_db, "com.x.foo()",
                   "throw new AlgorithmException(1, 2);")
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_exceptions(session, a)
    assert v.status == "VERIFIED"
    assert v.declared == ("AlgorithmException",)
    assert v.thrown == ("AlgorithmException",)


def test_undeclared_throws_when_action_declares_none(fixture_db):
    """The dominant production case: method throws but action declares nothing."""
    _insert_action(fixture_db, "a.x", None)
    _insert_method(fixture_db, "com.x.foo()",
                   "throw new IllegalStateException(\"oops\");")
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_exceptions(session, a)
    assert v.status == "UNDECLARED_THROWS"
    assert v.undeclared_only == ("IllegalStateException",)
    assert v.missing_only == ()


def test_missing_throws_when_method_throws_none(fixture_db):
    _insert_action(fixture_db, "a.x", [
        {"kind": "raises", "exception": "FooException"},
    ])
    _insert_method(fixture_db, "com.x.foo()", "return null;")
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_exceptions(session, a)
    assert v.status == "MISSING_THROWS"
    assert v.missing_only == ("FooException",)
    assert v.undeclared_only == ()


def test_divergent_throws_when_both_non_empty_but_differ(fixture_db):
    _insert_action(fixture_db, "a.x", [
        {"kind": "raises", "exception": "AlgorithmException"},
    ])
    _insert_method(fixture_db, "com.x.foo()",
                   "throw new IllegalStateException(\"oops\");")
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_exceptions(session, a)
    assert v.status == "DIVERGENT_THROWS"
    assert "AlgorithmException" in v.missing_only
    assert "IllegalStateException" in v.undeclared_only


def test_verified_when_overlapping_full(fixture_db):
    """Action declares 2, method throws same 2 → VERIFIED."""
    _insert_action(fixture_db, "a.x", [
        {"kind": "raises", "exception": "A"},
        {"kind": "raises", "exception": "B"},
    ])
    _insert_method(fixture_db, "com.x.foo()",
                   "if(x) throw new A(); else throw new B();")
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_exceptions(session, a)
    assert v.status == "VERIFIED"


def test_divergent_when_action_subset_of_thrown(fixture_db):
    """Action declares {A}, method throws {A, B} — A overlaps, B undeclared → DIVERGENT."""
    _insert_action(fixture_db, "a.x", [
        {"kind": "raises", "exception": "A"},
    ])
    _insert_method(fixture_db, "com.x.foo()",
                   "if(x) throw new A(); else throw new B();")
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_exceptions(session, a)
    assert v.status == "DIVERGENT_THROWS"
    assert v.undeclared_only == ("B",)
    assert v.missing_only == ()


# ─────────────────────────────────────────────────────────────────────────────
# Batch + frozen
# ─────────────────────────────────────────────────────────────────────────────


def test_batch_preserves_order(fixture_db):
    _insert_action(fixture_db, "a.1", None)
    _insert_action(fixture_db, "a.2", None)
    _insert_method(fixture_db, "com.x.foo()", "throw new XException();")
    _insert_method(fixture_db, "com.x.bar()", "return 0;")
    actions = [
        _action("a.1", code_method_fqn="com.x.foo()"),
        _action("a.2", code_method_fqn="com.x.bar()"),
    ]
    with Session(fixture_db) as session:
        verifs = verify_action_exceptions_batch(session, actions)
    assert [v.action_fqn for v in verifs] == ["a.1", "a.2"]


def test_exception_verification_is_frozen():
    v = ExceptionVerification(
        action_fqn="a", code_method_fqn=None, status="NO_RECOMMENDATION",
    )
    with pytest.raises(Exception):
        v.status = "VERIFIED"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_production_slab_design_yields_undeclared_throws():
    """slab-design-real has 12 methods that throw but effects_json is empty
    in production → most throwing actions surface UNDECLARED_THROWS."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_exceptions_batch(session, actions)
        undeclared = [v for v in verifs if v.status == "UNDECLARED_THROWS"]
        # AlgorithmException is the dominant case (11 methods)
        assert len(undeclared) > 0
        assert any("AlgorithmException" in v.undeclared_only
                   for v in undeclared)
    finally:
        session.close()


@requires_production_db
def test_production_majority_of_actions_have_no_throws():
    """Most actions don't throw anything → status VERIFIED (both empty)
    or NO_RECOMMENDATION."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_exceptions_batch(session, actions)
        clean = [v for v in verifs
                 if v.status in ("VERIFIED", "NO_RECOMMENDATION")]
        # More than half the actions are clean
        assert len(clean) > len(verifs) // 2
    finally:
        session.close()
