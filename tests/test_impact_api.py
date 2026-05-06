"""impact_api end-to-end tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import impact_api
from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity, CodeRelation, EntityKinds, ParseResult, RelationKinds,
)
from backend.modeling.code_analysis.repository_registry import (
    InMemoryRepositoryRegistry, RepositoryEntry,
)


def _make_repo_registry_with_graph() -> InMemoryRepositoryRegistry:
    """A → calls → B → calls → C 그래프."""
    cls_a = CodeEntity(
        kind=EntityKinds.CLASS, qualified_name="com.x.A", name="A",
        file_path="A.java", line_start=1, line_end=10, parent=None, attributes={},
    )
    method_a = CodeEntity(
        kind=EntityKinds.METHOD, qualified_name="com.x.A.run", name="run",
        file_path="A.java", line_start=2, line_end=5, parent="com.x.A", attributes={},
    )
    cls_b = CodeEntity(
        kind=EntityKinds.CLASS, qualified_name="com.x.B", name="B",
        file_path="B.java", line_start=1, line_end=10, parent=None, attributes={},
    )
    method_b = CodeEntity(
        kind=EntityKinds.METHOD, qualified_name="com.x.B.process", name="process",
        file_path="B.java", line_start=2, line_end=5, parent="com.x.B", attributes={},
    )
    cls_c = CodeEntity(
        kind=EntityKinds.CLASS, qualified_name="com.x.C", name="C",
        file_path="C.java", line_start=1, line_end=10, parent=None, attributes={},
    )
    method_c = CodeEntity(
        kind=EntityKinds.METHOD, qualified_name="com.x.C.compute", name="compute",
        file_path="C.java", line_start=2, line_end=5, parent="com.x.C", attributes={},
    )
    rel_ab = CodeRelation(
        kind=RelationKinds.CALLS, source="com.x.A.run", target="com.x.B.process",
        file_path="A.java", line=3,
    )
    rel_bc = CodeRelation(
        kind=RelationKinds.CALLS, source="com.x.B.process", target="com.x.C.compute",
        file_path="B.java", line=3,
    )

    pr = ParseResult(
        entities=[cls_a, method_a, cls_b, method_b, cls_c, method_c],
        relations=[rel_ab, rel_bc],
        file_path="multi.java", language="Java",
    )

    reg = InMemoryRepositoryRegistry()
    entry = RepositoryEntry(
        repo_id="abc", path="/tmp/abc",
        files=1, entities=6, relations=2, errors=[],
        registered_at=datetime.now(timezone.utc),
        parse_results=[pr],
    )
    reg._by_id["abc"] = entry  # bypass register() — already-parsed
    return reg


def _make_app(reg: InMemoryRepositoryRegistry) -> tuple[FastAPI, TestClient]:
    impact_api.reset()
    impact_api.init(repo_registry=reg)
    app = FastAPI()
    app.include_router(impact_api.router)
    return app, TestClient(app)


# ---------------------------------------------------------------------------
class TestImpactAnalyze:
    def test_incoming_finds_callers(self) -> None:
        reg = _make_repo_registry_with_graph()
        _, client = _make_app(reg)
        # C.compute incoming = B.process (그리고 그 위 A.run)
        r = client.post("/api/modeling/impact/analyze", json={
            "repo_id": "abc",
            "target_fqn": "com.x.C.compute",
            "direction": "incoming",
            "max_hops": 5,
            "mode": "potential",
        })
        assert r.status_code == 200, r.json()
        body = r.json()
        assert body["target_exists"] is True
        affected_fqns = {a["qualified_name"] for a in body["affected"]}
        assert "com.x.B.process" in affected_fqns
        assert "com.x.A.run" in affected_fqns

    def test_outgoing_finds_dependencies(self) -> None:
        reg = _make_repo_registry_with_graph()
        _, client = _make_app(reg)
        # A.run outgoing = B.process → C.compute
        r = client.post("/api/modeling/impact/analyze", json={
            "repo_id": "abc",
            "target_fqn": "com.x.A.run",
            "direction": "outgoing",
            "max_hops": 5,
            "mode": "potential",
        })
        body = r.json()
        affected_fqns = {a["qualified_name"] for a in body["affected"]}
        assert "com.x.B.process" in affected_fqns
        assert "com.x.C.compute" in affected_fqns

    def test_unknown_target_returns_empty_with_flag(self) -> None:
        reg = _make_repo_registry_with_graph()
        _, client = _make_app(reg)
        r = client.post("/api/modeling/impact/analyze", json={
            "repo_id": "abc",
            "target_fqn": "com.x.Unknown.method",
            "direction": "incoming",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["target_exists"] is False
        assert body["affected"] == []

    def test_unknown_repo_returns_404(self) -> None:
        reg = _make_repo_registry_with_graph()
        _, client = _make_app(reg)
        r = client.post("/api/modeling/impact/analyze", json={
            "repo_id": "ghost",
            "target_fqn": "com.x.A.run",
            "direction": "incoming",
        })
        assert r.status_code == 404


def test_unconfigured_returns_503() -> None:
    impact_api.reset()
    app = FastAPI()
    app.include_router(impact_api.router)
    client = TestClient(app)
    r = client.post("/api/modeling/impact/analyze", json={
        "repo_id": "abc", "target_fqn": "x", "direction": "incoming",
    })
    assert r.status_code == 503
