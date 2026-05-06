"""H — ontology_graph_api integration tests (FastAPI TestClient)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import ontology_graph_api
from backend.modeling.persistence.database import bootstrap_database


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    from backend.modeling.persistence import database as _db
    _db._engine = None    # type: ignore[attr-defined]
    _db._SessionLocal = None    # type: ignore[attr-defined]
    bootstrap_database()
    yield


def _make_app():
    from backend.modeling.persistence.relation_store import SqliteOntologyRelationStore
    from backend.modeling.persistence.term_registry import SqliteBusinessTermRegistry
    from backend.modeling.persistence.rule_registry import SqliteRuleRegistry

    rel_store = SqliteOntologyRelationStore()
    term_reg = SqliteBusinessTermRegistry()
    rule_reg = SqliteRuleRegistry()

    ontology_graph_api.reset()
    ontology_graph_api.init(
        relation_store=rel_store,
        term_registry=term_reg,
        rule_registry=rule_reg,
    )
    app = FastAPI()
    app.include_router(ontology_graph_api.router)
    return app, rel_store, term_reg, rule_reg


def _seed_term(reg, repo_id: str, fqn: str, label: str = ""):
    from backend.modeling.mapping.mapping_models import BusinessTerm, BusinessTermSource
    t = BusinessTerm(
        qualified_name=fqn,
        canonical_label=label or fqn,
        aliases=[],
        domain="test",
        description="",
        source=BusinessTermSource.MANUAL,
        confirmed=True,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    reg.put(repo_id, t)


def _seed_rule(reg, repo_id: str, fqn: str, statement: str = "test", confirmed: bool = True):
    from backend.modeling.mapping.mapping_models import BusinessRule, RuleSeverity
    r = BusinessRule(
        qualified_name=fqn,
        statement=statement,
        terms_ref=[],
        severity=RuleSeverity.SOFT,
        source="test",
        confirmed=confirmed,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    reg.put(repo_id, r)


# ── tests ────────────────────────────────────────────────────────────────
def test_graph_empty():
    app, _, _, _ = _make_app()
    client = TestClient(app)
    r = client.get("/api/modeling/repos/empty/ontology-graph")
    assert r.status_code == 200
    data = r.json()
    assert data["counts"] == {"terms": 0, "rules": 0, "explicit_edges": 0, "derived_edges": 0}


def test_graph_with_term_and_rule_nodes():
    app, _, term_reg, rule_reg = _make_app()
    _seed_term(term_reg, "r1", "term.A", "용어A")
    _seed_rule(rule_reg, "r1", "rule.X", "test rule", confirmed=True)
    _seed_rule(rule_reg, "r1", "rule.Y", "unconfirmed", confirmed=False)
    client = TestClient(app)
    r = client.get("/api/modeling/repos/r1/ontology-graph")
    data = r.json()
    # confirmed rules 만 default
    assert data["counts"]["terms"] == 1
    assert data["counts"]["rules"] == 1
    # include unconfirmed → 2
    r2 = client.get("/api/modeling/repos/r1/ontology-graph?include_unconfirmed_rules=true")
    assert r2.json()["counts"]["rules"] == 2


def test_create_relation():
    app, _, term_reg, _ = _make_app()
    _seed_term(term_reg, "r", "term.A")
    _seed_term(term_reg, "r", "term.B")
    client = TestClient(app)
    r = client.post("/api/modeling/relations", json={
        "repo_id": "r",
        "src_kind": "term", "src_fqn": "term.A",
        "dst_kind": "term", "dst_fqn": "term.B",
        "kind": "is_a", "rationale": "test", "source": "manual",
    })
    assert r.status_code == 200
    edge = r.json()
    assert edge["kind"] == "is_a"
    assert edge["src_id"] == "term.A"


def test_create_relation_invalid_kind():
    app, *_ = _make_app()
    client = TestClient(app)
    r = client.post("/api/modeling/relations", json={
        "repo_id": "r", "src_kind": "term", "src_fqn": "A",
        "dst_kind": "term", "dst_fqn": "B", "kind": "INVALID",
    })
    assert r.status_code == 400


def test_delete_relation():
    app, *_ = _make_app()
    client = TestClient(app)
    r = client.post("/api/modeling/relations", json={
        "repo_id": "r", "src_kind": "term", "src_fqn": "A",
        "dst_kind": "term", "dst_fqn": "B", "kind": "related_to",
    })
    rel_id = r.json()["id"]
    d = client.delete(f"/api/modeling/relations/{rel_id}")
    assert d.status_code == 200
    assert d.json()["deleted"] is True


def test_delete_relation_404():
    app, *_ = _make_app()
    client = TestClient(app)
    d = client.delete("/api/modeling/relations/nonexistent")
    assert d.status_code == 404
