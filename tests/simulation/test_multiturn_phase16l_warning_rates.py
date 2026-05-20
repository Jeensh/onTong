"""Phase 16L — integrity_warning 발화율 metric (운영 dashboard).

PM 16E LOW #4. 최근 N 세션 중 각 warning kind 가 발화한 session pct.
target_is_test % 가 늘면 modeling 시드 갭, alias_gap % 가 늘면 BT alias 갭.

테스트:
  - compute_warning_rates: empty / single kind / multiple kinds / dedup per session / repo filter
  - GET /api/section3/multiturn/metrics/warnings: 200 + 정확한 % + limit/repo
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.persistence import database as db_mod
from backend.section3.agents.multiturn.intent import StubIntentClassifier
from backend.section3.agents.multiturn.ontology_client import MockOntologyClient


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase16l.db"
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
    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(forced_intent="ambiguous")
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog={})
    )
    return TestClient(app)


def _seed_session_with_warnings(*, repo: str, kinds: list[str], sid_label: str) -> str:
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id=repo, user_query=f"q-{sid_label}")
    # 1 decision row 에 모든 warning sources 묶어 넣음 (실 시나리오 동일 형식)
    sources = [
        {"source": "llm_inference", "detail": f"integrity_warning={k} (test)"}
        for k in kinds
    ]
    p.add_gate_decision(
        session_id=sid,
        turn_no=1,
        gate_payload={"kind": "executed_hypothesis", "sources": sources},
    )
    return sid


# ─────────────────────────────────────────────────────────────────────────────
# compute_warning_rates
# ─────────────────────────────────────────────────────────────────────────────


def test_empty_returns_zero(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    r = p.compute_warning_rates()
    assert r.total_sessions == 0
    assert r.by_kind == {}
    assert r.by_kind_pct == {}


def test_single_session_single_kind(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    _seed_session_with_warnings(repo="r", kinds=["target_is_test"], sid_label="s1")
    r = p.compute_warning_rates()
    assert r.total_sessions == 1
    assert r.by_kind == {"target_is_test": 1}
    assert r.by_kind_pct == {"target_is_test": 100.0}


def test_multiple_kinds_one_session_dedup(fresh_db) -> None:
    """한 session 에서 같은 kind 가 여러 번 발화해도 session count = 1."""
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="r", user_query="q")
    # 같은 kind 2 번 + 다른 kind 1 번 → 둘 다 1 count
    p.add_gate_decision(
        session_id=sid, turn_no=1,
        gate_payload={
            "kind": "executed_hypothesis",
            "sources": [
                {"source": "llm_inference", "detail": "integrity_warning=target_is_test x"},
                {"source": "llm_inference", "detail": "integrity_warning=target_is_test y"},
                {"source": "llm_inference", "detail": "integrity_warning=no_strong_evidence"},
            ],
        },
    )
    r = p.compute_warning_rates()
    assert r.total_sessions == 1
    assert r.by_kind == {"target_is_test": 1, "no_strong_evidence": 1}
    assert r.by_kind_pct == {"target_is_test": 100.0, "no_strong_evidence": 100.0}


def test_pct_across_sessions(fresh_db) -> None:
    """3 sessions 중 2 가 target_is_test, 1 이 alias_gap → 66.7 / 33.3."""
    from backend.section3.agents.multiturn import persistence as p
    _seed_session_with_warnings(repo="r", kinds=["target_is_test"], sid_label="a")
    _seed_session_with_warnings(repo="r", kinds=["target_is_test"], sid_label="b")
    _seed_session_with_warnings(repo="r", kinds=["body_unsupported_alias_gap"], sid_label="c")
    r = p.compute_warning_rates()
    assert r.total_sessions == 3
    assert r.by_kind == {"target_is_test": 2, "body_unsupported_alias_gap": 1}
    assert r.by_kind_pct == {"target_is_test": 66.7, "body_unsupported_alias_gap": 33.3}


def test_repo_id_filter(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    _seed_session_with_warnings(repo="r1", kinds=["target_is_test"], sid_label="a")
    _seed_session_with_warnings(repo="r2", kinds=["target_is_test"], sid_label="b")
    r1 = p.compute_warning_rates(repo_id="r1")
    assert r1.total_sessions == 1
    assert r1.by_kind == {"target_is_test": 1}
    r2 = p.compute_warning_rates(repo_id="r2")
    assert r2.total_sessions == 1


def test_no_warnings_session_doesnt_count_kinds(fresh_db) -> None:
    """warning 없는 session 도 total_sessions 에 포함, by_kind 에는 영향 X."""
    from backend.section3.agents.multiturn import persistence as p
    _seed_session_with_warnings(repo="r", kinds=["target_is_test"], sid_label="a")
    # warning 없는 session
    sid_clean = p.start_session(repo_id="r", user_query="clean")
    p.add_gate_decision(
        session_id=sid_clean, turn_no=1,
        gate_payload={"kind": "executed_hypothesis", "sources": []},
    )
    r = p.compute_warning_rates()
    assert r.total_sessions == 2
    assert r.by_kind == {"target_is_test": 1}
    assert r.by_kind_pct == {"target_is_test": 50.0}


# ─────────────────────────────────────────────────────────────────────────────
# GET /metrics/warnings
# ─────────────────────────────────────────────────────────────────────────────


def test_endpoint_empty(client) -> None:
    r = client.get("/api/section3/multiturn/metrics/warnings")
    assert r.status_code == 200
    body = r.json()
    assert body["total_sessions"] == 0
    assert body["by_kind"] == {}
    assert body["by_kind_pct"] == {}


def test_endpoint_returns_rates(client, fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    _seed_session_with_warnings(repo="r", kinds=["target_is_test"], sid_label="x")
    _seed_session_with_warnings(repo="r", kinds=["body_unsupported_alias_gap"], sid_label="y")
    r = client.get("/api/section3/multiturn/metrics/warnings")
    assert r.status_code == 200
    body = r.json()
    assert body["total_sessions"] == 2
    assert body["by_kind"]["target_is_test"] == 1
    assert body["by_kind_pct"]["target_is_test"] == 50.0


def test_endpoint_repo_filter(client, fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    _seed_session_with_warnings(repo="r1", kinds=["target_is_test"], sid_label="x")
    _seed_session_with_warnings(repo="r2", kinds=["target_is_test"], sid_label="y")
    r = client.get("/api/section3/multiturn/metrics/warnings?repo_id=r1")
    assert r.status_code == 200
    body = r.json()
    assert body["total_sessions"] == 1
