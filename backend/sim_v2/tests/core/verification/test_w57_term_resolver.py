"""W57 — Term→Java type resolver tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.verification.term_type_resolver import (
    TermJavaResolution,
    extract_class_fqn_from_description,
    resolve_term_to_java_type,
    simple_name_of,
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
            CREATE TABLE business_terms (
                fqn TEXT, description TEXT, aliases_json TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_term(engine, fqn, description, aliases, repo_id="r"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO business_terms(fqn, description, aliases_json, repo_id) "
                 "VALUES (:f, :d, :a, :r)"),
            {"f": fqn, "d": description, "a": json.dumps(aliases), "r": repo_id},
        )


# ─────────────────────────────────────────────────────────────────────────────
# extract_class_fqn_from_description
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_class_fqn_em_dash():
    fqn = extract_class_fqn_from_description(
        "자동 추천 — com.example.slabdesign.feature.X.ValidationResult"
    )
    assert fqn == "com.example.slabdesign.feature.X.ValidationResult"


def test_extract_class_fqn_en_dash():
    fqn = extract_class_fqn_from_description("자동 추천 – com.x.Foo")
    assert fqn == "com.x.Foo"


def test_extract_class_fqn_hyphen():
    fqn = extract_class_fqn_from_description("자동 추천 - com.x.Foo")
    assert fqn == "com.x.Foo"


def test_extract_class_fqn_returns_none_for_method_pattern():
    """`com.x.Foo.bar()` is a method, not a class — reject."""
    assert extract_class_fqn_from_description("자동 추천 — com.x.Foo.bar()") is None


def test_extract_class_fqn_returns_none_for_no_match():
    assert extract_class_fqn_from_description("something else") is None
    assert extract_class_fqn_from_description("") is None
    assert extract_class_fqn_from_description(None) is None  # type: ignore[arg-type]


def test_extract_class_fqn_handles_inner_class():
    """`Outer$Inner` should still match as a class."""
    fqn = extract_class_fqn_from_description("자동 추천 — com.x.Outer$Inner")
    assert fqn == "com.x.Outer$Inner"


# ─────────────────────────────────────────────────────────────────────────────
# simple_name_of
# ─────────────────────────────────────────────────────────────────────────────


def test_simple_name_strips_package():
    assert simple_name_of("com.x.Foo") == "Foo"


def test_simple_name_strips_inner_class():
    assert simple_name_of("com.x.Outer$Inner") == "Inner"


def test_simple_name_of_empty():
    assert simple_name_of("") == ""


def test_simple_name_of_already_simple():
    assert simple_name_of("Foo") == "Foo"


# ─────────────────────────────────────────────────────────────────────────────
# TermJavaResolution candidates
# ─────────────────────────────────────────────────────────────────────────────


def test_resolution_candidates_includes_simple_and_fqn():
    r = TermJavaResolution(term_fqn="t.x", java_fqn="com.x.Foo")
    assert r.candidates == ("Foo", "com.x.Foo")


def test_resolution_candidates_includes_aliases_after_fqn():
    r = TermJavaResolution(
        term_fqn="t.x",
        java_fqn="com.x.Foo",
        aliases=("FooEntity", "FooDTO"),
    )
    assert r.candidates == ("Foo", "com.x.Foo", "FooEntity", "FooDTO")


def test_resolution_candidates_dedupes():
    r = TermJavaResolution(
        term_fqn="t.x",
        java_fqn="com.x.Foo",
        aliases=("Foo",),
    )
    assert r.candidates == ("Foo", "com.x.Foo")


def test_resolution_is_resolved_when_alias_present_only():
    r = TermJavaResolution(term_fqn="t.x", aliases=("Foo",))
    assert r.is_resolved is True


def test_resolution_is_resolved_false_when_empty():
    r = TermJavaResolution(term_fqn="t.x")
    assert r.is_resolved is False


# ─────────────────────────────────────────────────────────────────────────────
# resolve_term_to_java_type (fixture)
# ─────────────────────────────────────────────────────────────────────────────


def test_resolve_unknown_term_returns_unresolved(fixture_db):
    with Session(fixture_db) as session:
        r = resolve_term_to_java_type(session, "no.such.term", "r")
    assert r.is_resolved is False


def test_resolve_with_description_only(fixture_db):
    _insert_term(fixture_db, "t.x", "자동 추천 — com.x.Foo", [])
    with Session(fixture_db) as session:
        r = resolve_term_to_java_type(session, "t.x", "r")
    assert r.java_fqn == "com.x.Foo"
    assert r.aliases == ()
    assert r.candidates == ("Foo", "com.x.Foo")


def test_resolve_with_aliases_only(fixture_db):
    _insert_term(fixture_db, "t.x", "no pattern here", ["Foo"])
    with Session(fixture_db) as session:
        r = resolve_term_to_java_type(session, "t.x", "r")
    assert r.java_fqn is None
    assert r.aliases == ("Foo",)
    assert r.is_resolved is True


def test_resolve_combined(fixture_db):
    _insert_term(fixture_db, "t.x", "자동 추천 — com.x.Foo", ["FooEntity"])
    with Session(fixture_db) as session:
        r = resolve_term_to_java_type(session, "t.x", "r")
    assert r.java_fqn == "com.x.Foo"
    assert r.aliases == ("FooEntity",)
    assert r.candidates == ("Foo", "com.x.Foo", "FooEntity")


def test_resolve_malformed_aliases_json_treated_as_empty(fixture_db):
    with fixture_db.begin() as conn:
        conn.execute(text(
            "INSERT INTO business_terms(fqn, description, aliases_json, repo_id) "
            "VALUES ('t.x', 'no pattern', '{not json', 'r')"
        ))
    with Session(fixture_db) as session:
        r = resolve_term_to_java_type(session, "t.x", "r")
    assert r.aliases == ()


def test_resolve_aliases_filters_non_strings(fixture_db):
    with fixture_db.begin() as conn:
        conn.execute(text(
            "INSERT INTO business_terms(fqn, description, aliases_json, repo_id) "
            "VALUES ('t.x', '', :a, 'r')"
        ), {"a": json.dumps(["Foo", 42, None, "Bar"])})
    with Session(fixture_db) as session:
        r = resolve_term_to_java_type(session, "t.x", "r")
    assert r.aliases == ("Foo", "Bar")


def test_resolve_repo_id_isolates(fixture_db):
    _insert_term(fixture_db, "t.x", "자동 추천 — com.r1.Foo", [], repo_id="r1")
    _insert_term(fixture_db, "t.x", "자동 추천 — com.r2.Foo", [], repo_id="r2")
    with Session(fixture_db) as session:
        r1 = resolve_term_to_java_type(session, "t.x", "r1")
        r2 = resolve_term_to_java_type(session, "t.x", "r2")
    assert r1.java_fqn == "com.r1.Foo"
    assert r2.java_fqn == "com.r2.Foo"


def test_resolution_is_frozen():
    r = TermJavaResolution(term_fqn="t.x")
    with pytest.raises(Exception):
        r.term_fqn = "other"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_validation_result_term_resolves_to_class():
    session = open_readonly_session()
    try:
        r = resolve_term_to_java_type(
            session, "term.scm.validation_result", "slab-design-real",
        )
        assert r.is_resolved is True
        assert "ValidationResult" in r.candidates
    finally:
        session.close()


@requires_production_db
def test_edging_group_term_resolves_to_class():
    session = open_readonly_session()
    try:
        r = resolve_term_to_java_type(
            session, "term.scm.edging_group", "slab-design-real",
        )
        assert r.is_resolved is True
        # method returns "EdgingGroupEntity" — must be one of the candidates
        assert "EdgingGroupEntity" in r.candidates
    finally:
        session.close()
