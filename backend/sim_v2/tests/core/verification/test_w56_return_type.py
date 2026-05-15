"""W56 — Return-type agreement verifier tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    load_actions,
)
from backend.sim_v2.core.verification.return_type_verifier import (
    ReturnTypeVerification,
    verify_action_return_type,
    verify_action_return_types,
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
                fqn TEXT, output_json TEXT, repo_id TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE code_methods (
                fqn TEXT, return_type TEXT, repo_id TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE business_terms (
                fqn TEXT, description TEXT, aliases_json TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_term(engine, fqn, description, aliases=None, repo_id="r"):
    import json as _json
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO business_terms(fqn, description, aliases_json, repo_id) "
                 "VALUES (:f, :d, :a, :r)"),
            {"f": fqn, "d": description,
             "a": _json.dumps(aliases or []), "r": repo_id},
        )


def _insert_action(engine, fqn, output, repo_id):
    output_json = json.dumps(output) if output is not None else "null"
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO actions(fqn, output_json, repo_id) "
                 "VALUES (:f, :o, :r)"),
            {"f": fqn, "o": output_json, "r": repo_id},
        )


def _insert_method(engine, fqn, return_type, repo_id):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO code_methods(fqn, return_type, repo_id) "
                 "VALUES (:f, :r, :rid)"),
            {"f": fqn, "r": return_type, "rid": repo_id},
        )


def _action(fqn, code_method_fqn=None, repo_id="r"):
    return ActionView(
        fqn=fqn, label="", code_method_fqn=code_method_fqn, repo_id=repo_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-status
# ─────────────────────────────────────────────────────────────────────────────


def test_no_recommendation_when_code_method_fqn_missing(fixture_db):
    a = _action("a.x")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "NO_RECOMMENDATION"


def test_method_not_found_when_method_row_missing(fixture_db):
    _insert_action(fixture_db, "a.x", {"type": "string"}, "r")
    a = _action("a.x", code_method_fqn="com.unknown.X.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "METHOD_NOT_FOUND"


def test_verified_when_both_void(fixture_db):
    _insert_action(fixture_db, "a.x", None, "r")
    _insert_method(fixture_db, "com.x.A.foo()", "void", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "VERIFIED"
    assert v.action_output is None


def test_verified_when_string_to_string(fixture_db):
    _insert_action(fixture_db, "a.x", {"type": "string"}, "r")
    _insert_method(fixture_db, "com.x.A.foo()", "String", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "VERIFIED"


def test_verified_when_int_to_int(fixture_db):
    _insert_action(fixture_db, "a.x", {"type": "int"}, "r")
    _insert_method(fixture_db, "com.x.A.foo()", "int", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "VERIFIED"


def test_verified_when_int_to_Integer(fixture_db):
    _insert_action(fixture_db, "a.x", {"type": "int"}, "r")
    _insert_method(fixture_db, "com.x.A.foo()", "Integer", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "VERIFIED"


def test_verified_when_decimal_to_BigDecimal(fixture_db):
    _insert_action(fixture_db, "a.x", {"type": "decimal"}, "r")
    _insert_method(fixture_db, "com.x.A.foo()", "BigDecimal", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "VERIFIED"


def test_void_mismatch_when_action_declares_output_but_method_void(fixture_db):
    _insert_action(fixture_db, "a.x", {"type": "string"}, "r")
    _insert_method(fixture_db, "com.x.A.foo()", "void", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "VOID_MISMATCH"
    assert "void" in v.details


def test_implicit_output_when_action_void_but_method_returns_something(fixture_db):
    _insert_action(fixture_db, "a.x", None, "r")
    _insert_method(fixture_db, "com.x.A.foo()", "String", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "IMPLICIT_OUTPUT"
    assert v.method_return == "String"


def test_primitive_mismatch_for_string_to_custom_class(fixture_db):
    """The exact production case: action declares 'string' but method returns
    a domain class (e.g., ProductCategory)."""
    _insert_action(fixture_db, "a.x", {"type": "string"}, "r")
    _insert_method(fixture_db, "com.x.A.foo()", "ProductCategory", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "PRIMITIVE_MISMATCH"
    assert v.action_output == "string"
    assert v.method_return == "ProductCategory"


def test_primitive_mismatch_for_int_to_long_strict(fixture_db):
    """int vs long are not interchangeable in this verifier."""
    _insert_action(fixture_db, "a.x", {"type": "int"}, "r")
    _insert_method(fixture_db, "com.x.A.foo()", "long", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    # `long` is not in `int`'s compatibility set ⇒ mismatch
    assert v.status == "PRIMITIVE_MISMATCH"


def test_object_ref_unresolved_when_term_missing(fixture_db):
    """Term row missing → cannot resolve, status UNRESOLVED (not VERIFIED)."""
    _insert_action(fixture_db, "a.x",
                   {"type": "object_ref", "object_ref_term": "term.scm.x"},
                   "r")
    _insert_method(fixture_db, "com.x.A.foo()", "ValidationResult", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "OBJECT_REF_UNRESOLVED"
    assert "term.scm.x" in (v.action_output or "")


def test_object_ref_verified_via_description(fixture_db):
    """Term description points to ValidationResult; method returns ValidationResult."""
    _insert_action(fixture_db, "a.x",
                   {"type": "object_ref", "object_ref_term": "term.scm.x"},
                   "r")
    _insert_method(fixture_db, "com.x.A.foo()", "ValidationResult", "r")
    _insert_term(fixture_db, "term.scm.x",
                 "자동 추천 — com.example.wrapper.ValidationResult")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "VERIFIED"


def test_object_ref_verified_via_aliases(fixture_db):
    """No description pattern, but aliases provide the simple name."""
    _insert_action(fixture_db, "a.x",
                   {"type": "object_ref", "object_ref_term": "term.scm.x"},
                   "r")
    _insert_method(fixture_db, "com.x.A.foo()", "FooEntity", "r")
    _insert_term(fixture_db, "term.scm.x", "", aliases=["FooEntity"])
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "VERIFIED"


def test_object_ref_verified_strips_generics(fixture_db):
    """`List<Foo>` → simple name `List` — generics stripped before compare."""
    _insert_action(fixture_db, "a.x",
                   {"type": "object_ref", "object_ref_term": "term.scm.x"},
                   "r")
    _insert_method(fixture_db, "com.x.A.foo()", "List<String>", "r")
    _insert_term(fixture_db, "term.scm.x", "", aliases=["List"])
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "VERIFIED"


def test_object_ref_mismatch_when_term_and_method_disagree(fixture_db):
    """Term resolves to ValidationResult but method returns OrderEntity."""
    _insert_action(fixture_db, "a.x",
                   {"type": "object_ref", "object_ref_term": "term.scm.x"},
                   "r")
    _insert_method(fixture_db, "com.x.A.foo()", "OrderEntity", "r")
    _insert_term(fixture_db, "term.scm.x",
                 "자동 추천 — com.example.wrapper.ValidationResult")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "OBJECT_REF_MISMATCH"
    assert "ValidationResult" in v.details


def test_object_ref_void_mismatch_when_method_void(fixture_db):
    """Action declares object_ref output but method is void."""
    _insert_action(fixture_db, "a.x",
                   {"type": "object_ref", "object_ref_term": "term.scm.x"},
                   "r")
    _insert_method(fixture_db, "com.x.A.foo()", "void", "r")
    _insert_term(fixture_db, "term.scm.x",
                 "자동 추천 — com.example.wrapper.ValidationResult")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "VOID_MISMATCH"


def test_object_ref_unresolved_when_term_blank(fixture_db):
    """Empty `object_ref_term` field — cannot resolve."""
    _insert_action(fixture_db, "a.x",
                   {"type": "object_ref", "object_ref_term": ""},
                   "r")
    _insert_method(fixture_db, "com.x.A.foo()", "Foo", "r")
    a = _action("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    assert v.status == "OBJECT_REF_UNRESOLVED"


def test_malformed_output_json_treated_as_no_output(fixture_db):
    with fixture_db.begin() as conn:
        conn.execute(text(
            "INSERT INTO actions(fqn, output_json, repo_id) "
            "VALUES ('a.bad', '{not json', 'r')"
        ))
    _insert_method(fixture_db, "com.x.A.foo()", "void", "r")
    a = _action("a.bad", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_return_type(session, a)
    # Malformed JSON ⇒ treated as no output. Method is void ⇒ VERIFIED.
    assert v.status == "VERIFIED"


def test_verify_returns_preserve_order(fixture_db):
    _insert_action(fixture_db, "a.1", {"type": "string"}, "r")
    _insert_action(fixture_db, "a.2", None, "r")
    _insert_method(fixture_db, "com.x.foo()", "String", "r")
    _insert_method(fixture_db, "com.x.bar()", "void", "r")
    actions = [
        _action("a.1", code_method_fqn="com.x.foo()"),
        _action("a.2", code_method_fqn="com.x.bar()"),
    ]
    with Session(fixture_db) as session:
        verifs = verify_action_return_types(session, actions)
    assert [v.action_fqn for v in verifs] == ["a.1", "a.2"]


def test_return_type_verification_is_frozen():
    v = ReturnTypeVerification(
        action_fqn="a", code_method_fqn=None, status="VERIFIED",
    )
    with pytest.raises(Exception):
        v.status = "VOID_MISMATCH"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_slab_design_real_yields_mixed_outcomes():
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_return_types(session, actions)
        from collections import Counter
        counts = Counter(v.status for v in verifs)
        # VERIFIED + PRIMITIVE_MISMATCH must appear; OBJECT_REF rows now
        # split into VERIFIED / OBJECT_REF_MISMATCH / OBJECT_REF_UNRESOLVED
        # depending on resolver outcome.
        assert counts.get("VERIFIED", 0) > 0
        assert counts.get("PRIMITIVE_MISMATCH", 0) > 0
    finally:
        session.close()


@requires_production_db
def test_slab_design_real_object_ref_rows_resolve_or_mismatch_not_skipped():
    """W57 closes the OBJECT_REF gap: no rows should be UNRESOLVED for the
    fully-stocked slab-design-real repo (every term carries a description)."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_return_types(session, actions)
        unresolved = [v for v in verifs if v.status == "OBJECT_REF_UNRESOLVED"]
        # Production should have its terms fully described — unresolved is a
        # data-quality regression signal.
        assert len(unresolved) == 0, (
            f"Unexpected unresolved object_ref rows: "
            f"{[v.action_fqn for v in unresolved]}"
        )
    finally:
        session.close()


@requires_production_db
def test_production_primitive_mismatch_includes_string_vs_class_drift():
    """Known production case: action declares 'string' output, method returns a class."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_return_types(session, actions)
        primitive_mismatches = [v for v in verifs if v.status == "PRIMITIVE_MISMATCH"]
        assert any(v.action_output == "string" for v in primitive_mismatches)
    finally:
        session.close()
