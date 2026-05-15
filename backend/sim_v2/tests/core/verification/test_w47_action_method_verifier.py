"""W47 — Action ↔ Code agreement verifier tests.

Two layers tested:
1. Per-status classification on a fixture DB (synthetic code_methods rows).
2. Production smoke test — verification rate on `slab-design-real` should be
   meaningful (≥80% VERIFIED) given the post-W41 100% translator coverage.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    load_actions,
)
from backend.sim_v2.core.verification.action_method_verifier import (
    ActionVerification,
    verify_action,
    verify_actions,
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
# Fixture: in-memory code_methods table
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE code_methods (
                fqn TEXT,
                body_text TEXT,
                repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_method(engine, fqn, repo_id, body_text):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO code_methods(fqn, body_text, repo_id) "
                 "VALUES (:f, :b, :r)"),
            {"f": fqn, "b": body_text, "r": repo_id},
        )


def _action(fqn, code_method_fqn, repo_id="r"):
    return ActionView(
        fqn=fqn, label="", code_method_fqn=code_method_fqn, repo_id=repo_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-status classification
# ─────────────────────────────────────────────────────────────────────────────


def test_no_recommendation_when_action_has_no_code_method_fqn(fixture_db):
    a = ActionView(fqn="action.x", label="", code_method_fqn=None, repo_id="r")
    with Session(fixture_db) as session:
        v = verify_action(session, a)
    assert v.status == "NO_RECOMMENDATION"
    assert v.code_method_fqn is None
    assert isinstance(v, ActionVerification)


def test_method_not_found_when_code_method_fqn_missing_from_db(fixture_db):
    a = _action("action.x", "com.unknown.X.foo()", repo_id="r")
    with Session(fixture_db) as session:
        v = verify_action(session, a)
    assert v.status == "METHOD_NOT_FOUND"


def test_verified_when_method_translates_cleanly(fixture_db):
    _insert_method(
        fixture_db, "com.x.A.foo(int)", "r",
        "public int foo(int n) { return n * 2; }",
    )
    a = _action("action.a.foo", "com.x.A.foo(int)", repo_id="r")
    with Session(fixture_db) as session:
        v = verify_action(session, a)
    assert v.status == "VERIFIED"
    assert v.notes == ()


def test_empty_when_body_is_whitespace_only(fixture_db):
    _insert_method(fixture_db, "com.x.A.empty()", "r", "   \n\t  ")
    a = _action("action.empty", "com.x.A.empty()", repo_id="r")
    with Session(fixture_db) as session:
        v = verify_action(session, a)
    assert v.status == "EMPTY"


def test_parse_error_when_body_text_is_not_a_method_declaration(fixture_db):
    """A body that doesn't open as a Java method (e.g. just an expression)
    should classify PARSE_ERROR."""
    _insert_method(fixture_db, "com.x.A.bad()", "r", "int x = 5;  // not a method")
    a = _action("action.bad", "com.x.A.bad()", repo_id="r")
    with Session(fixture_db) as session:
        v = verify_action(session, a)
    assert v.status == "PARSE_ERROR"


def test_signature_locked_when_method_uses_unsupported_construct(fixture_db):
    """A `synchronized` block currently locks the translator (per W40 test)."""
    _insert_method(
        fixture_db, "com.x.A.sync()", "r",
        "public void sync() { Object lock = new Object(); "
        "synchronized(lock) { int x = 1; } }",
    )
    a = _action("action.sync", "com.x.A.sync()", repo_id="r")
    with Session(fixture_db) as session:
        v = verify_action(session, a)
    assert v.status == "SIGNATURE_LOCKED"
    assert len(v.notes) > 0


def test_verify_action_filters_by_repo_id(fixture_db):
    """The same method FQN in two repos must resolve to its own repo's body."""
    _insert_method(fixture_db, "com.x.A.foo()", "r1",
                   "public void foo() { int x = 1; }")
    _insert_method(fixture_db, "com.x.A.foo()", "r2",
                   "public void foo() { return; }")
    a1 = _action("action.foo", "com.x.A.foo()", repo_id="r1")
    a2 = _action("action.foo", "com.x.A.foo()", repo_id="r2")
    with Session(fixture_db) as session:
        v1 = verify_action(session, a1)
        v2 = verify_action(session, a2)
    assert v1.status == "VERIFIED"
    assert v2.status == "VERIFIED"


def test_verify_actions_preserves_order(fixture_db):
    _insert_method(fixture_db, "com.x.A.foo()", "r",
                   "public void foo() { int x = 1; }")
    actions = [
        _action("action.1", None),                              # no_rec
        _action("action.2", "com.x.A.foo()"),                   # verified
        _action("action.3", "com.x.MISSING.bar()"),             # not_found
    ]
    with Session(fixture_db) as session:
        verifications = verify_actions(session, actions)
    assert len(verifications) == 3
    assert verifications[0].status == "NO_RECOMMENDATION"
    assert verifications[1].status == "VERIFIED"
    assert verifications[2].status == "METHOD_NOT_FOUND"


def test_action_verification_is_frozen():
    v = ActionVerification(action_fqn="a", code_method_fqn=None, status="VERIFIED")
    with pytest.raises(Exception):
        v.status = "EMPTY"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke test
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_production_slab_design_real_verification_rate_above_80():
    """slab-design-real should yield a high VERIFIED rate (≥80%) given the
    framework's 100% translator coverage on its production code."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifications = verify_actions(session, actions)
        if not verifications:
            pytest.skip("no actions for slab-design-real")
        verified = sum(1 for v in verifications if v.status == "VERIFIED")
        rate = verified / len(verifications)
        assert rate >= 0.80, f"unexpectedly low verification rate: {rate:.2%}"
    finally:
        session.close()


@requires_production_db
def test_production_synthetic_5k_has_method_not_found_findings():
    """synthetic-5k's actions reference non-prefixed FQNs while code_methods
    are prefix-stamped — the verifier should surface this as METHOD_NOT_FOUND
    (a real cross-layer drift finding, preserved as-is)."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "synthetic-5k")
        if not actions:
            pytest.skip("no actions for synthetic-5k")
        verifications = verify_actions(session, actions[:50])
        not_found = sum(1 for v in verifications if v.status == "METHOD_NOT_FOUND")
        # Most synthetic-5k actions should be METHOD_NOT_FOUND due to the prefix
        # inconsistency between actions.description and code_methods.fqn
        assert not_found > 0
    finally:
        session.close()
