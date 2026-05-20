"""GET /api/section3/multiturn/sessions — recent sessions list.

Phase 11 — Option B (Session History Browser). Surface 시킬 데이터:
    section3_session + section3_decision_log → SessionSummary

테스트 매트릭스:
    persistence.list_recent_sessions
        - empty
        - turn_count + last_gate_kind 채워짐
        - last_activity_at desc 정렬
        - repo_id 필터
        - user_query substring 검색
        - limit
    GET /api/section3/multiturn/sessions
        - empty
        - /start 후 보임
        - latest first
        - repo_id 필터
        - search 필터
        - limit 적용
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.persistence import database as db_mod
from backend.section3.agents.multiturn.intent import StubIntentClassifier
from backend.section3.agents.multiturn.ontology_client import MockOntologyClient


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "section3_session_list.db"
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


# ─────────────────────────────────────────────────────────────────────────────
# persistence.list_recent_sessions
# ─────────────────────────────────────────────────────────────────────────────


def test_list_returns_empty_when_no_sessions(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    assert p.list_recent_sessions() == []


def test_list_returns_summary_with_turn_count(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="repo-A", user_query="주문 검증")
    p.add_gate_decision(
        session_id=sid, turn_no=1,
        gate_payload={"kind": "target_selected"},
    )
    p.add_gate_decision(
        session_id=sid, turn_no=2,
        gate_payload={"kind": "bundle_prepared"},
    )

    rows = p.list_recent_sessions()
    assert len(rows) == 1
    summary = rows[0]
    assert summary.id == sid
    assert summary.repo_id == "repo-A"
    assert summary.user_query == "주문 검증"
    assert summary.turn_count == 2
    assert summary.last_gate_kind == "bundle_prepared"


def test_list_orders_by_last_activity_desc(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid1 = p.start_session(repo_id="r", user_query="첫번째")
    time.sleep(0.02)
    sid2 = p.start_session(repo_id="r", user_query="두번째")
    time.sleep(0.02)
    p.update_session_status(sid1, "done")  # touch sid1 → 가장 최신

    rows = p.list_recent_sessions()
    assert [r.id for r in rows] == [sid1, sid2]


def test_list_filters_by_repo_id(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid_a = p.start_session(repo_id="repo-A", user_query="A 쿼리")
    p.start_session(repo_id="repo-B", user_query="B 쿼리")

    rows = p.list_recent_sessions(repo_id="repo-A")
    assert len(rows) == 1
    assert rows[0].id == sid_a


def test_list_searches_user_query_substring(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    p.start_session(repo_id="r", user_query="주문 검증 시뮬")
    p.start_session(repo_id="r", user_query="배송 처리")

    rows = p.list_recent_sessions(search="주문")
    assert len(rows) == 1
    assert "주문" in (rows[0].user_query or "")


def test_list_search_is_case_insensitive(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    p.start_session(repo_id="r", user_query="ValidateOrder simulation")

    rows = p.list_recent_sessions(search="validateorder")
    assert len(rows) == 1


def test_list_respects_limit(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    for i in range(5):
        p.start_session(repo_id="r", user_query=f"q{i}")
        time.sleep(0.005)

    rows = p.list_recent_sessions(limit=3)
    assert len(rows) == 3


def test_list_last_gate_kind_is_latest_turn(fresh_db) -> None:
    """마지막 turn 의 gate_kind 가 surface 되어야."""
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="r", user_query="q")
    p.add_gate_decision(
        session_id=sid, turn_no=1,
        gate_payload={"kind": "target_selected"},
    )
    p.add_gate_decision(
        session_id=sid, turn_no=2,
        gate_payload={"kind": "bundle_prepared"},
    )
    p.add_gate_decision(
        session_id=sid, turn_no=3,
        gate_payload={"kind": "executed_simulation"},
    )

    rows = p.list_recent_sessions()
    assert rows[0].last_gate_kind == "executed_simulation"


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/section3/multiturn/sessions
# ─────────────────────────────────────────────────────────────────────────────


def test_endpoint_returns_empty_list(client) -> None:
    r = client.get("/api/section3/multiturn/sessions")
    assert r.status_code == 200
    assert r.json() == {"sessions": []}


def test_endpoint_returns_recent_sessions_latest_first(client) -> None:
    client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    time.sleep(0.02)
    client.post("/api/section3/multiturn/start", json={
        "user_query": "배송 시뮬", "repo_id": "slab-design-real-v2",
    })

    r = client.get("/api/section3/multiturn/sessions")
    assert r.status_code == 200
    sessions = r.json()["sessions"]
    assert len(sessions) == 2
    assert sessions[0]["user_query"] == "배송 시뮬"   # latest first
    assert sessions[1]["user_query"] == "주문 검증"


def test_endpoint_filters_by_repo_id(client) -> None:
    client.post("/api/section3/multiturn/start", json={
        "user_query": "A 쿼리", "repo_id": "repo-A",
    })
    client.post("/api/section3/multiturn/start", json={
        "user_query": "B 쿼리", "repo_id": "repo-B",
    })

    r = client.get("/api/section3/multiturn/sessions?repo_id=repo-A")
    assert r.status_code == 200
    sessions = r.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["repo_id"] == "repo-A"


def test_endpoint_searches_user_query(client) -> None:
    client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증 시뮬", "repo_id": "r",
    })
    client.post("/api/section3/multiturn/start", json={
        "user_query": "배송 처리", "repo_id": "r",
    })

    r = client.get("/api/section3/multiturn/sessions?search=주문")
    assert r.status_code == 200
    sessions = r.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["user_query"] == "주문 검증 시뮬"


def test_endpoint_respects_limit(client) -> None:
    for i in range(4):
        client.post("/api/section3/multiturn/start", json={
            "user_query": f"q{i}", "repo_id": "r",
        })
        time.sleep(0.01)

    r = client.get("/api/section3/multiturn/sessions?limit=2")
    sessions = r.json()["sessions"]
    assert len(sessions) == 2


def test_endpoint_summary_includes_turn_count_and_status(client) -> None:
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "r",
    })
    sid = start.json()["session_id"]

    r = client.get("/api/section3/multiturn/sessions")
    sessions = r.json()["sessions"]
    s = next(s for s in sessions if s["id"] == sid)
    assert s["turn_count"] == 1   # /start 가 turn 1 추가
    assert s["status"] == "active"
    assert s["last_gate_kind"] == "target_selected"
    assert "created_at" in s
    assert "last_activity_at" in s
