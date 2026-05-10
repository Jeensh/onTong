"""ontology_sources_router (E6) — dual ontology source 상태 endpoint 검증.

GET /api/simulation/ontology-sources
- SQLite + Neo4j 두 source 의 health / entity counts / cross_references
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client():
    from backend.simulation.api.ontology_sources_router import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_get_ontology_sources_returns_two_sources():
    """sqlite + neo4j 두 source 모두 보고."""
    resp = _client().get("/api/simulation/ontology-sources")
    assert resp.status_code == 200
    data = resp.json()
    names = {s["name"] for s in data["sources"]}
    assert names == {"sqlite", "neo4j"}


def test_sqlite_source_includes_actions_count():
    """SQLite source 의 entity_counts 에 actions 키 존재."""
    resp = _client().get("/api/simulation/ontology-sources")
    sqlite = next(s for s in resp.json()["sources"] if s["name"] == "sqlite")
    assert sqlite["schema_kind"] == "relational"
    assert "actions" in sqlite["entity_counts"]
    assert sqlite["entity_counts"]["actions"] >= 0


def test_neo4j_source_reports_status():
    """Neo4j source 의 available 필드 (env / 미설치 시 False, 떠있으면 True)."""
    resp = _client().get("/api/simulation/ontology-sources")
    neo4j = next(s for s in resp.json()["sources"] if s["name"] == "neo4j")
    assert neo4j["schema_kind"] == "graph"
    assert isinstance(neo4j["available"], bool)
    if not neo4j["available"]:
        assert neo4j["error"] is not None


def test_cross_references_when_both_available():
    """두 source 모두 살아있으면 cross_references 항목 채워짐."""
    resp = _client().get("/api/simulation/ontology-sources")
    data = resp.json()
    sqlite_ok = next(s["available"] for s in data["sources"] if s["name"] == "sqlite")
    neo4j_ok = next(s["available"] for s in data["sources"] if s["name"] == "neo4j")
    if sqlite_ok and neo4j_ok:
        assert len(data["cross_references"]) > 0
        # method_fqn 매핑 안내가 들어있어야 함
        assert any("method_fqn" in ref for ref in data["cross_references"])
    else:
        # 둘 중 하나라도 미가용이면 cross_references 비어있을 수 있음
        assert isinstance(data["cross_references"], list)


def test_purpose_text_included_per_source():
    resp = _client().get("/api/simulation/ontology-sources")
    for s in resp.json()["sources"]:
        assert s["purpose"]
        assert len(s["purpose"]) > 0
