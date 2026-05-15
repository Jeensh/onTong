"""W52 — Action ↔ Method parameter-signature verifier tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    load_actions,
)
from backend.sim_v2.core.verification.param_signature_verifier import (
    ParamVerification,
    verify_action_param_signature,
    verify_action_param_signatures,
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
# Fixture: in-memory `actions` + `code_methods` tables
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE actions (
                fqn TEXT, params_json TEXT, repo_id TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE code_methods (
                fqn TEXT, params_json TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_action_row(engine, fqn, params, repo_id):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO actions(fqn, params_json, repo_id) "
                 "VALUES (:f, :p, :r)"),
            {"f": fqn, "p": json.dumps(params), "r": repo_id},
        )


def _insert_method_row(engine, fqn, params, repo_id):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO code_methods(fqn, params_json, repo_id) "
                 "VALUES (:f, :p, :r)"),
            {"f": fqn, "p": json.dumps(params), "r": repo_id},
        )


def _action_view(fqn, code_method_fqn=None, repo_id="r"):
    return ActionView(
        fqn=fqn, label="", code_method_fqn=code_method_fqn, repo_id=repo_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-status classification
# ─────────────────────────────────────────────────────────────────────────────


def test_no_recommendation_when_action_lacks_code_method_fqn(fixture_db):
    with Session(fixture_db) as session:
        v = verify_action_param_signature(session, _action_view("a.x"))
    assert v.status == "NO_RECOMMENDATION"
    assert isinstance(v, ParamVerification)


def test_no_action_params_when_action_params_empty(fixture_db):
    _insert_action_row(fixture_db, "a.x", [], "r")
    _insert_method_row(fixture_db, "com.x.A.foo()", [], "r")
    av = _action_view("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_param_signature(session, av)
    assert v.status == "NO_ACTION_PARAMS"


def test_method_not_found_when_code_method_missing(fixture_db):
    _insert_action_row(fixture_db, "a.x",
                       [{"name": "order"}, {"name": "slab"}], "r")
    # No code_methods row inserted
    av = _action_view("a.x", code_method_fqn="com.unknown.X.foo()")
    with Session(fixture_db) as session:
        v = verify_action_param_signature(session, av)
    assert v.status == "METHOD_NOT_FOUND"
    assert v.action_params == ("order", "slab")
    assert v.method_params == ()


def test_arity_mismatch_when_counts_differ(fixture_db):
    _insert_action_row(fixture_db, "a.x",
                       [{"name": "order"}], "r")
    _insert_method_row(fixture_db, "com.x.A.foo(SDOrder,SDSlab)",
                       [{"name": "order"}, {"name": "slab"}], "r")
    av = _action_view("a.x", code_method_fqn="com.x.A.foo(SDOrder,SDSlab)")
    with Session(fixture_db) as session:
        v = verify_action_param_signature(session, av)
    assert v.status == "ARITY_MISMATCH"
    assert "1 params" in v.details
    assert "2" in v.details


def test_name_mismatch_when_names_differ(fixture_db):
    _insert_action_row(fixture_db, "a.x",
                       [{"name": "order"}, {"name": "blob"}], "r")
    _insert_method_row(fixture_db, "com.x.A.foo(SDOrder,SDSlab)",
                       [{"name": "order"}, {"name": "slab"}], "r")
    av = _action_view("a.x", code_method_fqn="com.x.A.foo(SDOrder,SDSlab)")
    with Session(fixture_db) as session:
        v = verify_action_param_signature(session, av)
    assert v.status == "NAME_MISMATCH"
    assert v.action_params == ("order", "blob")
    assert v.method_params == ("order", "slab")


def test_name_mismatch_when_order_differs(fixture_db):
    """Order matters — `(order, slab)` vs `(slab, order)` is NAME_MISMATCH."""
    _insert_action_row(fixture_db, "a.x",
                       [{"name": "slab"}, {"name": "order"}], "r")
    _insert_method_row(fixture_db, "com.x.A.foo()",
                       [{"name": "order"}, {"name": "slab"}], "r")
    av = _action_view("a.x", code_method_fqn="com.x.A.foo()")
    with Session(fixture_db) as session:
        v = verify_action_param_signature(session, av)
    assert v.status == "NAME_MISMATCH"


def test_verified_when_exact_match(fixture_db):
    _insert_action_row(fixture_db, "a.x",
                       [{"name": "order", "type": "object_ref"},
                        {"name": "slab", "type": "object_ref"}], "r")
    _insert_method_row(fixture_db, "com.x.A.foo(SDOrder,SDSlab)",
                       [{"name": "order", "type": "SDOrder"},
                        {"name": "slab", "type": "SDSlab"}], "r")
    av = _action_view("a.x", code_method_fqn="com.x.A.foo(SDOrder,SDSlab)")
    with Session(fixture_db) as session:
        v = verify_action_param_signature(session, av)
    assert v.status == "VERIFIED"
    assert v.action_params == ("order", "slab")
    assert v.method_params == ("order", "slab")


def test_verify_actions_preserves_order(fixture_db):
    _insert_action_row(fixture_db, "a.1", [{"name": "x"}], "r")
    _insert_action_row(fixture_db, "a.2", [{"name": "x"}], "r")
    _insert_method_row(fixture_db, "com.x.foo()", [{"name": "x"}], "r")
    actions = [
        _action_view("a.1", code_method_fqn="com.x.foo()"),
        _action_view("a.2", code_method_fqn="com.x.foo()"),
    ]
    with Session(fixture_db) as session:
        result = verify_action_param_signatures(session, actions)
    assert [v.action_fqn for v in result] == ["a.1", "a.2"]


def test_param_verification_is_frozen():
    v = ParamVerification(action_fqn="a", code_method_fqn=None, status="VERIFIED")
    with pytest.raises(Exception):
        v.status = "ARITY_MISMATCH"  # type: ignore[misc]


def test_malformed_action_params_json_falls_back_to_no_params(fixture_db):
    with fixture_db.begin() as conn:
        conn.execute(text(
            "INSERT INTO actions(fqn, params_json, repo_id) "
            "VALUES ('a.bad', '{not json', 'r')"
        ))
    _insert_method_row(fixture_db, "com.x.foo()", [{"name": "x"}], "r")
    av = _action_view("a.bad", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_param_signature(session, av)
    assert v.status == "NO_ACTION_PARAMS"


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke test
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_slab_design_real_verified_rate_above_75():
    """Most slab-design-real actions should match their methods (auto-recommend
    pipeline kept the param names aligned)."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifications = verify_action_param_signatures(session, actions)
        verified = sum(1 for v in verifications if v.status == "VERIFIED")
        rate = verified / len(verifications)
        assert rate >= 0.75
    finally:
        session.close()


@requires_production_db
def test_slab_design_v2_surfaces_name_mismatch_findings():
    """v2 has 3 known NAME_MISMATCH findings on productCd vs productTypeCd /
    prodKindCd — the verifier should detect them."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real-v2")
        verifications = verify_action_param_signatures(session, actions)
        name_mismatches = [v for v in verifications if v.status == "NAME_MISMATCH"]
        assert len(name_mismatches) >= 1
        # Confirm at least one references the productCd / productTypeCd / prodKindCd cluster
        mismatch_names = {n for v in name_mismatches
                          for n in v.action_params + v.method_params}
        assert "productCd" in mismatch_names or "productTypeCd" in mismatch_names \
            or "prodKindCd" in mismatch_names
    finally:
        session.close()
