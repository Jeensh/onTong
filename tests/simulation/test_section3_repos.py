"""GET /api/section3/repos — per-repo summary for dashboard.

새 endpoint. ontology.db SQLite 의 repo_id 별로:
  - actions / code_methods / code_types / business_terms / business_rules
  - realizations / call_sites
  - section3_session 의 누적 세션 수
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "section3_repos.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    db_mod.reset_engine_for_tests()

    from backend.modeling.code_layer import orm as _code_orm  # noqa: F401
    from backend.modeling.domain_layer import orm as _domain_orm  # noqa: F401
    from backend.modeling.mapping_layer import orm as _mapping_orm  # noqa: F401
    from backend.modeling.view_layer import orm as _view_orm  # noqa: F401
    from backend.application.authoring import orm as _authoring_orm  # noqa: F401
    from backend.section3.agents.multiturn import orm as _multiturn_orm  # noqa: F401

    db_mod.bootstrap_database()
    yield db_path
    db_mod.reset_engine_for_tests()


@pytest.fixture
def client(fresh_db):
    from backend.section3.api import router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    return TestClient(app)


def _seed_minimal(repo_id: str, *, methods: int = 0, actions: int = 0,
                   terms: int = 0, sessions: int = 0) -> None:
    """주어진 repo 에 카운트 충족하도록 seed.

    code_methods 는 FK → code_types 가 있어서 parent CodeType 1 개 먼저 생성.
    """
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeTypeRow, CodeMethodRow
    from backend.modeling.mapping_layer.orm import ActionRow
    from backend.modeling.domain_layer.orm import BusinessTermRow
    from backend.section3.agents.multiturn.orm import Section3SessionRow
    import uuid

    with session_scope() as s:
        if methods:
            parent_fqn = f"{repo_id}.TestType"
            s.add(CodeTypeRow(
                fqn=parent_fqn, simple_name="TestType", package="test",
                kind="class", repo_id=repo_id,
            ))
            s.flush()
            for i in range(methods):
                s.add(CodeMethodRow(
                    fqn=f"{repo_id}.TestType.m{i}",
                    name=f"m{i}",
                    parent_type_fqn=parent_fqn,
                    repo_id=repo_id,
                ))
        for i in range(actions):
            s.add(ActionRow(
                fqn=f"{repo_id}.A{i}",
                label=f"액션{i}",
                kind="bridge",
                repo_id=repo_id,
            ))
        for i in range(terms):
            s.add(BusinessTermRow(
                fqn=f"{repo_id}.T{i}",
                label=f"용어{i}",
                kind="concept",
                repo_id=repo_id,
            ))
        for _ in range(sessions):
            s.add(Section3SessionRow(
                id=str(uuid.uuid4()),
                repo_id=repo_id,
                status="active",
                user_query=f"q-{repo_id}",
            ))


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/section3/repos
# ─────────────────────────────────────────────────────────────────────────────


def test_empty_returns_empty_list(client) -> None:
    r = client.get("/api/section3/repos")
    assert r.status_code == 200
    assert r.json() == {"repos": []}


def test_single_repo_returns_summary(client) -> None:
    _seed_minimal("slab-design-real-v2", methods=10, actions=3, terms=5, sessions=2)
    r = client.get("/api/section3/repos")
    assert r.status_code == 200
    body = r.json()
    assert len(body["repos"]) == 1
    summary = body["repos"][0]
    assert summary["repo_id"] == "slab-design-real-v2"
    counts = summary["counts"]
    assert counts["code_methods"] == 10
    assert counts["actions"] == 3
    assert counts["business_terms"] == 5
    assert counts["sessions"] == 2


def test_multiple_repos_sorted_by_repo_id(client) -> None:
    _seed_minimal("zeta-repo", methods=1)
    _seed_minimal("alpha-repo", methods=2)
    _seed_minimal("middle-repo", methods=3)

    r = client.get("/api/section3/repos")
    assert r.status_code == 200
    repo_ids = [s["repo_id"] for s in r.json()["repos"]]
    assert repo_ids == ["alpha-repo", "middle-repo", "zeta-repo"]


def test_counts_filtered_per_repo(client) -> None:
    """A repo 의 카운트가 B repo 와 섞이지 않아야."""
    _seed_minimal("repo-A", methods=10, actions=2)
    _seed_minimal("repo-B", methods=3, actions=5)

    r = client.get("/api/section3/repos")
    repos = {s["repo_id"]: s["counts"] for s in r.json()["repos"]}
    assert repos["repo-A"]["code_methods"] == 10
    assert repos["repo-A"]["actions"] == 2
    assert repos["repo-B"]["code_methods"] == 3
    assert repos["repo-B"]["actions"] == 5


def test_repo_with_only_sessions_still_surfaces(client) -> None:
    """code data 가 없어도 session 만 있으면 repo 로 잡혀야."""
    _seed_minimal("sessions-only-repo", sessions=4)
    r = client.get("/api/section3/repos")
    repo_ids = [s["repo_id"] for s in r.json()["repos"]]
    assert "sessions-only-repo" in repo_ids
    summary = next(s for s in r.json()["repos"] if s["repo_id"] == "sessions-only-repo")
    assert summary["counts"]["sessions"] == 4
    assert summary["counts"]["code_methods"] == 0


def test_summary_includes_all_expected_keys(client) -> None:
    _seed_minimal("r", methods=1)
    r = client.get("/api/section3/repos")
    counts = r.json()["repos"][0]["counts"]
    for key in (
        "actions", "code_methods", "code_types",
        "business_terms", "business_rules",
        "realizations", "call_sites", "sessions",
    ):
        assert key in counts, f"missing key: {key}"
