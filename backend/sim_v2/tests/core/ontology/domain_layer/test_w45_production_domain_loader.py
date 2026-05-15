"""W45 — production domain layer loader tests.

Two layers:
1. `extract_method_fqn_from_description` — pure regex over action.description
2. Load helpers — fixture-driven, in-memory SQLite mirroring production schema
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    AnchorBindingView,
    BusinessTermView,
    extract_method_fqn_from_description,
    load_actions,
    load_anchor_bindings,
    load_business_terms,
)


# ─────────────────────────────────────────────────────────────────────────────
# extract_method_fqn_from_description
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_method_fqn_em_dash():
    assert extract_method_fqn_from_description(
        "자동 추천 — com.example.X.foo(int)"
    ) == "com.example.X.foo(int)"


def test_extract_method_fqn_hyphen():
    assert extract_method_fqn_from_description(
        "자동 추천 - com.example.X.bar()"
    ) == "com.example.X.bar()"


def test_extract_method_fqn_en_dash():
    assert extract_method_fqn_from_description(
        "자동 추천 – com.example.X.baz(String)"
    ) == "com.example.X.baz(String)"


def test_extract_method_fqn_no_space_before_dash():
    """Tolerant of '자동추천' (no space) and dashes either side."""
    assert extract_method_fqn_from_description(
        "자동추천 — com.example.X.zap(String,int)"
    ) == "com.example.X.zap(String,int)"


def test_extract_method_fqn_with_multiple_args():
    assert extract_method_fqn_from_description(
        "자동 추천 — com.example.X.process(int,String,Boolean)"
    ) == "com.example.X.process(int,String,Boolean)"


def test_extract_method_fqn_without_pattern_returns_none():
    assert extract_method_fqn_from_description("plain text") is None
    assert extract_method_fqn_from_description("") is None
    assert extract_method_fqn_from_description(None) is None  # type: ignore[arg-type]


def test_extract_method_fqn_no_parens_returns_none():
    """Without `(…)` the match shouldn't fire — we require a method signature."""
    assert extract_method_fqn_from_description(
        "자동 추천 — com.example.X"
    ) is None


# ─────────────────────────────────────────────────────────────────────────────
# Loaders — fixture-driven
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE business_terms (
                fqn TEXT, label TEXT, kind TEXT, domain TEXT,
                description TEXT, value_type TEXT, repo_id TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE actions (
                fqn TEXT, label TEXT, kind TEXT, declared_on_term TEXT,
                description TEXT, sub_actions_json TEXT, repo_id TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE anchor_bindings (
                id TEXT, anchor_locator TEXT, code_method_fqn TEXT,
                target_action_fqn TEXT, target_slot TEXT,
                confidence REAL, source TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_term(engine, fqn, repo_id, **kw):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO business_terms(fqn, label, kind, domain, description, value_type, repo_id) "
            "VALUES (:f, :l, :k, :d, :desc, :vt, :r)"
        ), {
            "f": fqn, "l": kw.get("label", ""), "k": kw.get("kind", ""),
            "d": kw.get("domain", ""), "desc": kw.get("description", ""),
            "vt": kw.get("value_type"), "r": repo_id,
        })


def _insert_action(engine, fqn, repo_id, **kw):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO actions(fqn, label, kind, declared_on_term, description, sub_actions_json, repo_id) "
            "VALUES (:f, :l, :k, :t, :d, :sj, :r)"
        ), {
            "f": fqn, "l": kw.get("label", ""), "k": kw.get("kind", ""),
            "t": kw.get("declared_on_term", ""), "d": kw.get("description", ""),
            "sj": json.dumps(kw.get("sub_actions", [])), "r": repo_id,
        })


def _insert_binding(engine, id, repo_id, **kw):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO anchor_bindings(id, anchor_locator, code_method_fqn, "
            "target_action_fqn, target_slot, confidence, source, repo_id) "
            "VALUES (:i, :al, :cmf, :taf, :ts, :c, :s, :r)"
        ), {
            "i": id, "al": kw.get("anchor_locator", ""),
            "cmf": kw.get("code_method_fqn", ""),
            "taf": kw.get("target_action_fqn", ""),
            "ts": kw.get("target_slot"), "c": kw.get("confidence", 1.0),
            "s": kw.get("source", ""), "r": repo_id,
        })


def test_load_business_terms_returns_view_with_label(fixture_db):
    _insert_term(fixture_db, "term.scm.order", "r1",
                 label="주문", kind="composite", domain="scm")
    with Session(fixture_db) as session:
        terms = load_business_terms(session, "r1")
    assert len(terms) == 1
    assert isinstance(terms[0], BusinessTermView)
    assert terms[0].fqn == "term.scm.order"
    assert terms[0].label == "주문"
    assert terms[0].domain == "scm"


def test_load_business_terms_filters_by_repo_id(fixture_db):
    _insert_term(fixture_db, "term.scm.a", "r1", label="A")
    _insert_term(fixture_db, "term.scm.b", "r2", label="B")
    with Session(fixture_db) as session:
        assert {t.fqn for t in load_business_terms(session, "r1")} == {"term.scm.a"}
        assert {t.fqn for t in load_business_terms(session, "r2")} == {"term.scm.b"}


def test_load_business_terms_empty_for_unknown_repo(fixture_db):
    _insert_term(fixture_db, "term.scm.x", "r1", label="X")
    with Session(fixture_db) as session:
        assert load_business_terms(session, "nonexistent") == []


def test_load_actions_parses_method_fqn_from_description(fixture_db):
    _insert_action(
        fixture_db, "action.scm.foo", "r1",
        description="자동 추천 — com.example.X.foo(int)",
    )
    with Session(fixture_db) as session:
        actions = load_actions(session, "r1")
    assert len(actions) == 1
    assert isinstance(actions[0], ActionView)
    assert actions[0].code_method_fqn == "com.example.X.foo(int)"


def test_load_actions_keeps_code_method_fqn_none_when_pattern_absent(fixture_db):
    _insert_action(fixture_db, "action.scm.foo", "r1", description="manual entry")
    with Session(fixture_db) as session:
        actions = load_actions(session, "r1")
    assert actions[0].code_method_fqn is None


def test_load_actions_parses_sub_actions_json_list(fixture_db):
    _insert_action(
        fixture_db, "action.scm.workflow", "r1",
        sub_actions=["action.scm.a", "action.scm.b"],
    )
    with Session(fixture_db) as session:
        actions = load_actions(session, "r1")
    assert actions[0].sub_actions == ("action.scm.a", "action.scm.b")


def test_load_actions_handles_malformed_sub_actions_json_gracefully(fixture_db):
    with fixture_db.begin() as conn:
        conn.execute(text(
            "INSERT INTO actions(fqn, label, kind, declared_on_term, description, "
            "sub_actions_json, repo_id) VALUES "
            "('action.bad', 'X', 'effectful', '', '', '{not json}', 'r1')"
        ))
    with Session(fixture_db) as session:
        actions = load_actions(session, "r1")
    # Should not raise; sub_actions falls back to empty
    assert actions[0].sub_actions == ()


def test_load_anchor_bindings_returns_view_with_confidence(fixture_db):
    _insert_binding(
        fixture_db, "binding_1", "r1",
        anchor_locator="literal 8",
        code_method_fqn="com.example.X.foo()",
        target_action_fqn="action.scm.foo",
        confidence=0.85,
    )
    with Session(fixture_db) as session:
        bindings = load_anchor_bindings(session, "r1")
    assert len(bindings) == 1
    assert isinstance(bindings[0], AnchorBindingView)
    assert bindings[0].confidence == 0.85
    assert bindings[0].target_action_fqn == "action.scm.foo"


def test_load_anchor_bindings_filters_by_repo_id(fixture_db):
    _insert_binding(fixture_db, "b1", "r1", anchor_locator="A")
    _insert_binding(fixture_db, "b2", "r2", anchor_locator="B")
    with Session(fixture_db) as session:
        assert {b.id for b in load_anchor_bindings(session, "r1")} == {"b1"}
        assert {b.id for b in load_anchor_bindings(session, "r2")} == {"b2"}


def test_views_are_frozen():
    """Pydantic ConfigDict(frozen=True) — assigning should raise."""
    t = BusinessTermView(fqn="term.x", label="X")
    with pytest.raises(Exception):
        t.label = "mutated"  # type: ignore[misc]
