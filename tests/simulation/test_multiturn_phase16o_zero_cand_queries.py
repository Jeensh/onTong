"""Phase 16O — 0-candidate query 매핑 갭 자동 탐지.

15C PM 권장 + 16L 후속. Gate I 가 0-candidate 로 끝난 session 의 user_query 들을
dashboard 에 노출 → modeling team 이 어떤 단어로 매칭 실패했는지 인지.

기준:
  - target_selected payload 에서 candidates == []
  - ambiguous stub (Phase 2 /start 직후) 는 제외 → real Gate I 만
  - per-session 1개 (가장 최근 0-cand decision)
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
    db_path = tmp_path / "phase16o.db"
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


def _add_target_selected(
    *,
    sid: str,
    turn_no: int,
    intent: str,
    candidates: list,
    suggestions: list[str] | None = None,
) -> None:
    from backend.section3.agents.multiturn import persistence as p
    payload = {
        "kind": "target_selected",
        "intent": intent,
        "candidates": candidates,
        "suggestions": suggestions or [],
        "user_query": "stub",
        "sources": [],
    }
    p.add_gate_decision(session_id=sid, turn_no=turn_no, gate_payload=payload)


# ─────────────────────────────────────────────────────────────────────────────
# list_zero_cand_queries
# ─────────────────────────────────────────────────────────────────────────────


def test_empty_when_no_sessions(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    assert p.list_zero_cand_queries() == []


def test_finds_zero_cand_real_intent(fresh_db) -> None:
    """real Gate I 의 0-cand 만 surface (ambiguous stub 제외)."""
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="r", user_query="모르는 단어 검색")
    # Phase 2 stub
    _add_target_selected(sid=sid, turn_no=1, intent="ambiguous", candidates=[])
    # real Gate I — 0 candidates
    _add_target_selected(sid=sid, turn_no=2, intent="simulate", candidates=[], suggestions=["검증결과"])

    rows = p.list_zero_cand_queries()
    assert len(rows) == 1
    assert rows[0].session_id == sid
    assert rows[0].user_query == "모르는 단어 검색"
    assert rows[0].suggestions == ["검증결과"]


def test_excludes_sessions_with_candidates(fresh_db) -> None:
    """candidates > 0 인 session 은 제외."""
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="r", user_query="잘 매칭됨")
    _add_target_selected(sid=sid, turn_no=1, intent="ambiguous", candidates=[])
    _add_target_selected(
        sid=sid, turn_no=2, intent="simulate",
        candidates=[{"action_id": "a", "label": "L", "score": 1.0, "code_method_fqn": "f", "aliases": []}],
    )
    assert p.list_zero_cand_queries() == []


def test_excludes_ambiguous_only(fresh_db) -> None:
    """ambiguous + 0-cand 만 있는 session 도 제외 (real Gate I 진입 X)."""
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="r", user_query="중단됨")
    _add_target_selected(sid=sid, turn_no=1, intent="ambiguous", candidates=[])
    assert p.list_zero_cand_queries() == []


def test_dedupe_per_session(fresh_db) -> None:
    """같은 session 에 0-cand decision 이 여러 개여도 1개만 surface."""
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="r", user_query="중복 가능")
    _add_target_selected(sid=sid, turn_no=1, intent="ambiguous", candidates=[])
    _add_target_selected(sid=sid, turn_no=2, intent="simulate", candidates=[])
    _add_target_selected(sid=sid, turn_no=3, intent="hypothesis", candidates=[])
    rows = p.list_zero_cand_queries()
    assert len(rows) == 1


def test_repo_id_filter(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid1 = p.start_session(repo_id="r1", user_query="q1")
    _add_target_selected(sid=sid1, turn_no=1, intent="simulate", candidates=[])
    sid2 = p.start_session(repo_id="r2", user_query="q2")
    _add_target_selected(sid=sid2, turn_no=1, intent="simulate", candidates=[])
    assert len(p.list_zero_cand_queries(repo_id="r1")) == 1
    assert p.list_zero_cand_queries(repo_id="r1")[0].user_query == "q1"
    assert len(p.list_zero_cand_queries(repo_id="r2")) == 1


def test_limit(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    for i in range(5):
        sid = p.start_session(repo_id="r", user_query=f"q-{i}")
        _add_target_selected(sid=sid, turn_no=1, intent="simulate", candidates=[])
    rows = p.list_zero_cand_queries(limit=3)
    assert len(rows) == 3


# ─────────────────────────────────────────────────────────────────────────────
# GET /metrics/zero-cand-queries
# ─────────────────────────────────────────────────────────────────────────────


def test_endpoint_empty(client) -> None:
    r = client.get("/api/section3/multiturn/metrics/zero-cand-queries")
    assert r.status_code == 200
    assert r.json() == {"queries": []}


def test_endpoint_returns_queries(client, fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="r", user_query="새 단어")
    _add_target_selected(
        sid=sid, turn_no=1, intent="simulate",
        candidates=[], suggestions=["기존 단어"],
    )
    r = client.get("/api/section3/multiturn/metrics/zero-cand-queries")
    assert r.status_code == 200
    body = r.json()
    assert len(body["queries"]) == 1
    q = body["queries"][0]
    assert q["user_query"] == "새 단어"
    assert q["suggestions"] == ["기존 단어"]
    assert q["repo_id"] == "r"


def test_endpoint_repo_filter(client, fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid1 = p.start_session(repo_id="r1", user_query="r1-q")
    _add_target_selected(sid=sid1, turn_no=1, intent="simulate", candidates=[])
    sid2 = p.start_session(repo_id="r2", user_query="r2-q")
    _add_target_selected(sid=sid2, turn_no=1, intent="simulate", candidates=[])
    r = client.get("/api/section3/multiturn/metrics/zero-cand-queries?repo_id=r1")
    assert r.status_code == 200
    body = r.json()
    assert len(body["queries"]) == 1
    assert body["queries"][0]["user_query"] == "r1-q"
