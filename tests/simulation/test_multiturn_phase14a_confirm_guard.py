"""Phase 14A — confirm guard for 0-cand.

페르소나 검증 (QA / PM) 에서 발견된 state machine 비대칭:
  - turn 2 에서 candidates=[] 인 경우에도 `confirm` 은 `ok:true` 반환
  - turn 3 호출 시 `_resolve_gate_ii_target` 가 `selected_index 범위 밖` 422 응답
  - UX 폭탄: 사용자는 ok 후 무엇이 잘못된지 모름

해결책: `confirm` 가 turn 2 의 payload.kind == "target_selected" 일 때
candidates 가 비었으면 422 + explicit message 즉시 반환.
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
    db_path = tmp_path / "phase14a.db"
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


def _build_app(intent="impact", **kwargs):
    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(forced_intent=intent, **kwargs)
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog={})
    )
    return app


def test_confirm_returns_422_when_candidates_empty(fresh_db, monkeypatch) -> None:
    """candidates=[] 인 turn 2 에 confirm 시 422 — turn 3 진입 차단."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(sb, "find_action_candidates",
                       lambda s, q, r, *, top_n=3: [])

    app = _build_app(intent="impact")
    client = TestClient(app)

    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "엣징 마진",
        "repo_id": "r1",
    })
    sid = start.json()["session_id"]
    turn2 = client.post(f"/api/section3/multiturn/respond/{sid}",
                       json={"message": "엣징 마진"})
    assert turn2.status_code == 200
    assert turn2.json()["payload"]["candidates"] == []

    # confirm 호출 — 422 + explicit message
    resp = client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    assert resp.status_code == 422, resp.text
    detail = resp.json().get("detail", "")
    assert "candidates" in detail.lower() or "후보" in detail or "0" in detail, (
        f"detail 에 0-cand 설명 있어야: {detail}"
    )


def test_confirm_with_modify_action_ok_when_empty(fresh_db, monkeypatch) -> None:
    """action=modify / retry 는 0-cand 여도 통과 — 재시도 의도."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(sb, "find_action_candidates",
                       lambda s, q, r, *, top_n=3: [])

    app = _build_app(intent="impact")
    client = TestClient(app)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "x", "repo_id": "r1",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
                json={"message": "x"})

    # modify / retry 는 user_response 에 selected_index 없어도 OK
    resp = client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "retry", "user_response": {}},
    )
    assert resp.status_code == 200, resp.text


def test_confirm_422_when_selected_index_out_of_range(fresh_db, monkeypatch) -> None:
    """candidates 1 개인데 selected_index=5 → 즉시 422."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(sb, "find_action_candidates",
                       lambda s, q, r, *, top_n=3: [
                           {"code_method_fqn": "A.b", "fqn": "act.x",
                            "label": "x", "score": 1.0},
                       ])

    app = _build_app(intent="impact")
    client = TestClient(app)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "x", "repo_id": "r1",
    })
    sid = start.json()["session_id"]
    turn2 = client.post(f"/api/section3/multiturn/respond/{sid}",
                       json={"message": "x"})
    assert turn2.json()["payload"]["candidates"]

    # selected_index=5 인데 candidates=1 → 422
    resp = client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 5}},
    )
    assert resp.status_code == 422, resp.text


def test_confirm_with_valid_selected_index_still_ok(fresh_db, monkeypatch) -> None:
    """기존 정상 케이스 회귀 확인."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(sb, "find_action_candidates",
                       lambda s, q, r, *, top_n=3: [
                           {"code_method_fqn": "A.b", "fqn": "act.x",
                            "label": "x", "score": 1.0},
                       ])

    app = _build_app(intent="impact")
    client = TestClient(app)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "x", "repo_id": "r1",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
               json={"message": "x"})
    resp = client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    assert resp.status_code == 200, resp.text


def test_confirm_missing_selected_index_with_confirm_action_422(
    fresh_db, monkeypatch,
) -> None:
    """action=confirm 인데 selected_index 누락 → 즉시 422."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(sb, "find_action_candidates",
                       lambda s, q, r, *, top_n=3: [
                           {"code_method_fqn": "A.b", "fqn": "act.x",
                            "label": "x", "score": 1.0},
                       ])

    app = _build_app(intent="impact")
    client = TestClient(app)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "x", "repo_id": "r1",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
               json={"message": "x"})
    # action=confirm 인데 user_response 가 empty
    resp = client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {}},
    )
    assert resp.status_code == 422, resp.text
