"""repos_api end-to-end tests — register/list/delete + SSE stream."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import repos_api
from backend.modeling.code_analysis.repository_registry import (
    InMemoryRepositoryRegistry,
)


def _make_app(project_root: Path):
    repos_api.reset()
    reg = InMemoryRepositoryRegistry()
    repos_api.init(registry=reg, project_root=project_root)
    app = FastAPI()
    app.include_router(repos_api.router)
    return app, reg


def _make_tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "tiny"
    src = repo / "src" / "main" / "java" / "com" / "x"
    src.mkdir(parents=True)
    (src / "A.java").write_text(
        "package com.x; public class A { private int n = 5; }",
        encoding="utf-8",
    )
    return repo


# ---------------------------------------------------------------------------
# 503 if not initialized
# ---------------------------------------------------------------------------
def test_unconfigured_returns_503() -> None:
    repos_api.reset()
    app = FastAPI()
    app.include_router(repos_api.router)
    client = TestClient(app)
    r = client.get("/api/modeling/repos")
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# GET /repos
# ---------------------------------------------------------------------------
class TestList:
    def test_empty_initially(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path)
        client = TestClient(app)
        r = client.get("/api/modeling/repos")
        assert r.status_code == 200
        assert r.json() == {"items": []}

    def test_lists_after_register(self, tmp_path: Path) -> None:
        app, reg = _make_app(tmp_path)
        client = TestClient(app)
        repo = _make_tiny_repo(tmp_path)
        r = client.post("/api/modeling/repos/register", json={
            "repo_id": "tiny", "path": str(repo),
        })
        assert r.status_code == 200, r.json()

        listed = client.get("/api/modeling/repos")
        items = listed.json()["items"]
        assert len(items) == 1
        assert items[0]["repo_id"] == "tiny"
        # files = 1 .java + 1 synthetic <db_schema> ParseResult (cross_file_enricher append).
        assert items[0]["files"] == 2


# ---------------------------------------------------------------------------
# POST /repos/register (sync)
# ---------------------------------------------------------------------------
class TestRegisterSync:
    def test_register_returns_entry_meta(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path)
        client = TestClient(app)
        repo = _make_tiny_repo(tmp_path)
        r = client.post("/api/modeling/repos/register", json={
            "repo_id": "tiny", "path": str(repo),
        })
        assert r.status_code == 200
        body = r.json()
        assert body["repo_id"] == "tiny"
        # 1 .java + synthetic <db_schema> = 2 ParseResult
        assert body["files"] == 2
        assert body["entities"] >= 1
        assert body["errors_count"] == 0

    def test_invalid_path_returns_404(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path)
        client = TestClient(app)
        r = client.post("/api/modeling/repos/register", json={
            "repo_id": "x", "path": str(tmp_path / "nonexistent"),
        })
        assert r.status_code == 404

    def test_relative_path_resolved_against_project_root(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path)
        client = TestClient(app)
        # tmp_path 안에 sub/ 만들고 그것을 상대경로로 register
        sub = tmp_path / "sub"
        java = sub / "x"
        java.mkdir(parents=True)
        (java / "B.java").write_text(
            "package com.x; public class B {}", encoding="utf-8",
        )
        r = client.post("/api/modeling/repos/register", json={
            "repo_id": "rel", "path": "sub",  # 상대 경로
        })
        assert r.status_code == 200, r.json()


# ---------------------------------------------------------------------------
# DELETE /repos/{repo_id}
# ---------------------------------------------------------------------------
class TestUnregister:
    def test_delete_existing(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path)
        client = TestClient(app)
        repo = _make_tiny_repo(tmp_path)
        client.post("/api/modeling/repos/register", json={
            "repo_id": "tiny", "path": str(repo),
        })
        r = client.delete("/api/modeling/repos/tiny")
        assert r.status_code == 200
        assert r.json()["removed"] is True

    def test_delete_unknown_returns_404(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path)
        client = TestClient(app)
        r = client.delete("/api/modeling/repos/ghost")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------
class TestRegisterStream:
    def test_stream_emits_progress_then_done(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path)
        client = TestClient(app)
        repo = _make_tiny_repo(tmp_path)

        with client.stream(
            "POST", "/api/modeling/repos/register/stream",
            json={"repo_id": "tiny", "path": str(repo)},
        ) as r:
            assert r.status_code == 200
            events = []
            for raw in r.iter_lines():
                line = raw if isinstance(raw, str) else raw.decode("utf-8")
                if line.startswith("event:"):
                    events.append(line[len("event:"):].strip())

        # 최소 discovering / parsing / enriching / done 이 옴
        assert "discovering" in events
        assert "parsing" in events
        assert "enriching" in events
        # 마지막은 "done" (또는 done 이후 sentinel 로 종료)
        assert events[-1] == "done"

    def test_stream_invalid_path_returns_404(self, tmp_path: Path) -> None:
        app, _ = _make_app(tmp_path)
        client = TestClient(app)
        r = client.post("/api/modeling/repos/register/stream", json={
            "repo_id": "x", "path": str(tmp_path / "nope"),
        })
        # SSE endpoint 가 path 검증 실패 → 즉시 404 (StreamingResponse 시작 전)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# terms_api 통합 — register 후 propose-bindings 가 즉시 동작
# ---------------------------------------------------------------------------
class TestTermsApiIntegration:
    def test_terms_propose_after_register_works(self, tmp_path: Path) -> None:
        # 통합 — repos_api + terms_api 를 같은 RepositoryRegistry 로 묶기
        from backend.modeling.api import terms_api
        from backend.modeling.mapping.business_term_registry import (
            InMemoryBusinessTermRegistry,
        )
        from backend.modeling.mapping.concept_store import (
            InMemoryConceptBindingStore,
        )
        from backend.modeling.mapping.mapping_models import (
            BusinessTerm, BusinessTermSource,
        )
        from backend.modeling.mapping.propose_bindings_service import (
            ProposeBindingsService,
        )
        from datetime import datetime as _dt, timezone as _tz

        repos_api.reset()
        terms_api.reset()
        reg = InMemoryRepositoryRegistry()
        repos_api.init(registry=reg, project_root=tmp_path)

        term_reg = InMemoryBusinessTermRegistry()
        term_reg.put("tiny", BusinessTerm(
            qualified_name="term.n",
            canonical_label="N",
            aliases=["n"],
            domain="t",
            source=BusinessTermSource.MANUAL,
            created_at=_dt.now(_tz.utc),
        ))
        store = InMemoryConceptBindingStore()
        svc = ProposeBindingsService(term_registry=term_reg, binding_store=store)
        terms_api.init(
            term_registry=term_reg,
            binding_store=store,
            propose_service=svc,
            repo_registry=reg,
        )

        app = FastAPI()
        app.include_router(repos_api.router)
        app.include_router(terms_api.router)
        client = TestClient(app)

        # 등록 전 propose → 404
        r = client.post("/api/modeling/terms/propose-bindings",
                        json={"repo_id": "tiny"})
        assert r.status_code == 404

        # 등록 — JPA Entity 만들기
        java = tmp_path / "src"
        java.mkdir(parents=True)
        (java / "T.java").write_text(
            'package com.x;\n'
            '@Entity public class T {\n'
            '  @Column(name = "N") private int n;\n'
            '}\n',
            encoding="utf-8",
        )
        r = client.post("/api/modeling/repos/register", json={
            "repo_id": "tiny", "path": str(tmp_path),
        })
        assert r.status_code == 200, r.json()

        # 등록 후 propose → 매칭 1건 예상 (n 필드 의 N 컬럼 ↔ "N" alias)
        r = client.post("/api/modeling/terms/propose-bindings",
                        json={"repo_id": "tiny"})
        assert r.status_code == 200
        assert r.json()["total_proposed"] >= 1
