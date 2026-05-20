"""Step 1e/2c — 5 endpoint (start / respond / confirm / session / stream).

Spec v2 §7. Phase 2:
  - /start  → ambiguous stub (turn 1)
  - /respond first call → Gate I real (intent + sim_v2+ontology candidates, turn 2)
  - /respond turn 3+ → 501 (Gate II/III 미구현)
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
    db_path = tmp_path / "section3_multiturn_api.db"
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


def _stub_sim_v2(monkeypatch, candidates):
    """sim_v2_bridge 의 sync 후보 검색을 비활성/지정."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self):
            pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb,
        "find_action_candidates",
        lambda s, q, r, *, top_n=3: candidates[:top_n],
    )


@pytest.fixture
def slab_catalog():
    return {
        "actions": [
            {
                "action_id": "act:OrderService.validateOrder",
                "label": "주문 검증",
                "code_method_fqn": "com.slab.OrderService.validateOrder",
                "aliases": ["주문검증"],
                "repo_id": "slab-design-real-v2",
                "location": {
                    "file_path": "OrderService.java",
                    "line_start": 12, "line_end": 48,
                },
            },
        ],
    }


@pytest.fixture
def client(fresh_db, monkeypatch, slab_catalog):
    """default client — sim_v2 empty, ontology=slab_catalog, intent stub=ambiguous."""
    _stub_sim_v2(monkeypatch, [])

    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(forced_intent="ambiguous")
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog=slab_catalog)
    )
    return TestClient(app)


@pytest.fixture
def client_factory(fresh_db, monkeypatch, slab_catalog):
    """custom intent / sim_v2 후보 / catalog 주입할 때 사용."""
    def _build(
        *,
        forced_intent="simulate",
        sim_v2_candidates=None,
        catalog=None,
    ):
        _stub_sim_v2(monkeypatch, sim_v2_candidates or [])
        from backend.section3.api import multiturn_router as router_mod
        app = FastAPI()
        app.include_router(router_mod.router)
        app.dependency_overrides[router_mod.get_classifier] = lambda: (
            StubIntentClassifier(forced_intent=forced_intent, forced_confidence=0.9)
        )
        app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
            MockOntologyClient(catalog=catalog if catalog is not None else slab_catalog)
        )
        return TestClient(app)

    return _build


# ─────────────────────────────────────────────────────────────────────────────
# POST /start
# ─────────────────────────────────────────────────────────────────────────────


def test_start_returns_session_id_and_gate_i_payload(client) -> None:
    r = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증 시뮬해줘",
        "repo_id": "slab-design-real-v2",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "session_id" in body
    assert body["turn_no"] == 1
    assert body["payload"]["kind"] == "target_selected"
    assert body["payload"]["intent"] == "ambiguous"   # Phase 1: stub default
    assert body["payload"]["user_query"] == "주문 검증 시뮬해줘"


def test_start_persists_decision(client) -> None:
    """start 후 GET /session 로 같은 payload 확인."""
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "엣징 룰 조회",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    r = client.get(f"/api/section3/multiturn/session/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["id"] == sid
    assert body["session"]["repo_id"] == "slab-design-real-v2"
    assert len(body["decisions"]) == 1
    assert body["decisions"][0]["gate_kind"] == "target_selected"


def test_start_requires_repo_id(client) -> None:
    r = client.post("/api/section3/multiturn/start", json={"user_query": "x"})
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# POST /confirm/{session_id}/{turn_no}
# ─────────────────────────────────────────────────────────────────────────────


def test_confirm_persists_user_response(client) -> None:
    """confirm 시 user_response 가 persistence 에 저장되는지 확인.

    Phase 14A 가 0-cand confirm 을 차단하므로 candidates 가 있는 turn 2 에 confirm.
    """
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "주문 검증"},
    )
    r = client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    replay = client.get(f"/api/section3/multiturn/session/{sid}").json()
    decisions = replay["decisions"]
    turn2 = next(d for d in decisions if d["turn_no"] == 2)
    assert turn2["user_response"] == {
        "selected_index": 0, "action": "confirm",
    }


def test_confirm_target_selected_simulate_returns_next_bundle(client_factory, monkeypatch) -> None:
    """spec v2 §2: target_selected + confirm + intent=simulate → bundle_prepared."""
    _stub_gate_ii_bridge(monkeypatch)
    cl = client_factory(forced_intent="simulate", catalog=_gate_ii_catalog())
    start = cl.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    cl.post(f"/api/section3/multiturn/respond/{sid}", json={"message": "주문 검증"})
    r = cl.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    assert r.status_code == 200
    assert r.json()["next_gate_kind"] == "bundle_prepared"


def test_confirm_target_selected_impact_returns_next_impact(client_factory, monkeypatch) -> None:
    """spec v2 §2: target_selected + confirm + intent=impact → executed_impact."""
    _stub_gate_ii_bridge(monkeypatch)
    cl = client_factory(
        forced_intent="impact",
        catalog=_gate_ii_catalog_with_caller_graph(),
    )
    start = cl.post("/api/section3/multiturn/start", json={
        "user_query": "주문 영향", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    cl.post(f"/api/section3/multiturn/respond/{sid}", json={"message": "주문 영향"})
    r = cl.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    assert r.status_code == 200
    assert r.json()["next_gate_kind"] == "executed_impact"


def test_confirm_target_selected_retry_returns_target_selected(client_factory, monkeypatch) -> None:
    _stub_gate_ii_bridge(monkeypatch)
    cl = client_factory(forced_intent="simulate", catalog=_gate_ii_catalog())
    start = cl.post("/api/section3/multiturn/start", json={
        "user_query": "주문", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    cl.post(f"/api/section3/multiturn/respond/{sid}", json={"message": "주문"})
    r = cl.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "retry", "user_response": {}},
    )
    assert r.json()["next_gate_kind"] == "target_selected"


def test_confirm_ambiguous_intent_returns_no_next_gate(client_factory) -> None:
    """ambiguous intent + confirm → next_gate_kind=None (재분류 필요).

    Phase 14A 가 0-cand confirm 차단하므로 candidates 가 있는 query 사용.
    """
    cl = client_factory(forced_intent="ambiguous")
    start = cl.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    cl.post(f"/api/section3/multiturn/respond/{sid}",
            json={"message": "주문 검증"})
    r = cl.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["next_gate_kind"] is None


def test_confirm_bundle_prepared_returns_executed_simulation(client_factory, monkeypatch) -> None:
    """bundle_prepared + confirm → executed_simulation."""
    _stub_gate_ii_bridge(monkeypatch)
    cl = client_factory(forced_intent="simulate", catalog=_gate_ii_catalog())
    start = cl.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    cl.post(f"/api/section3/multiturn/respond/{sid}", json={"message": "주문 검증"})
    cl.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    cl.post(f"/api/section3/multiturn/respond/{sid}", json={"message": "go"})
    # turn 3 = bundle_prepared. confirm 시 next = executed_simulation
    r = cl.post(
        f"/api/section3/multiturn/confirm/{sid}/3",
        json={"action": "confirm", "user_response": {}},
    )
    assert r.json()["next_gate_kind"] == "executed_simulation"


def test_confirm_unknown_session_returns_404(client) -> None:
    r = client.post(
        "/api/section3/multiturn/confirm/missing/1",
        json={"action": "confirm", "user_response": {}},
    )
    assert r.status_code == 404


def test_confirm_unknown_turn_returns_404(client) -> None:
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "x", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    r = client.post(
        f"/api/section3/multiturn/confirm/{sid}/99",
        json={"action": "confirm", "user_response": {}},
    )
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# GET /session/{session_id}
# ─────────────────────────────────────────────────────────────────────────────


def test_session_unknown_returns_404(client) -> None:
    r = client.get("/api/section3/multiturn/session/nope")
    assert r.status_code == 404


def test_session_replay_preserves_korean(client) -> None:
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "엣징 그룹 코드 룩업 룰 시뮬",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    body = client.get(f"/api/section3/multiturn/session/{sid}").json()
    assert body["session"]["user_query"] == "엣징 그룹 코드 룩업 룰 시뮬"
    assert (
        body["decisions"][0]["payload"]["user_query"]
        == "엣징 그룹 코드 룩업 룰 시뮬"
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /respond/{session_id} — Phase 2 Gate I real
# ─────────────────────────────────────────────────────────────────────────────


def test_respond_unknown_session_returns_404(client) -> None:
    r = client.post(
        "/api/section3/multiturn/respond/missing", json={"message": "x"},
    )
    assert r.status_code == 404


def test_respond_first_call_runs_gate_i_simulate(client_factory) -> None:
    """첫 /respond → turn_no=2 + intent=simulate + 후보 채워짐."""
    client = client_factory(forced_intent="simulate")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증 시뮬",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "주문 검증 시뮬"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["turn_no"] == 2
    assert body["payload"]["kind"] == "target_selected"
    assert body["payload"]["intent"] == "simulate"
    # ontology 후보 (주문 검증) 가 후보로 들어와야
    fqns = [c["code_method_fqn"] for c in body["payload"]["candidates"]]
    assert "com.slab.OrderService.validateOrder" in fqns
    assert body["payload"]["recommended_index"] == 0


def test_respond_first_call_runs_gate_i_impact(client_factory) -> None:
    client = client_factory(forced_intent="impact")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "validateOrder 바꾸면 영향?",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "validateOrder 바꾸면 영향?"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["payload"]["intent"] == "impact"


def test_respond_empty_message_uses_session_user_query(client_factory) -> None:
    """message="" 일 때 session.user_query 로 fallback."""
    client = client_factory(forced_intent="simulate")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": ""},
    )
    assert r.status_code == 200, r.text
    assert r.json()["payload"]["user_query"] == "주문"


def test_respond_persists_turn_2_decision(client_factory) -> None:
    """/respond 후 GET /session 에 turn 2 가 보여야."""
    client = client_factory(forced_intent="simulate")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "주문 검증"},
    )
    replay = client.get(f"/api/section3/multiturn/session/{sid}").json()
    turns = [d["turn_no"] for d in replay["decisions"]]
    assert turns == [1, 2]
    # turn 2 = real Gate I (intent=simulate)
    turn2 = next(d for d in replay["decisions"] if d["turn_no"] == 2)
    assert turn2["payload"]["intent"] == "simulate"


def test_respond_turn_3_without_confirm_returns_422(client_factory) -> None:
    """turn 2 confirm 안 됐으면 Gate II 진입 시 422."""
    client = client_factory(forced_intent="simulate")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "주문"},
    )
    # confirm 없이 바로 두 번째 /respond
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "이 bundle"},
    )
    assert r.status_code == 422
    assert "confirm" in r.text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Gate II — turn 3 (Java + Python + fixtures bundle)
# ─────────────────────────────────────────────────────────────────────────────


def _stub_gate_ii_bridge(monkeypatch):
    """sim_v2_bridge 의 Gate II 사용 함수 stub (translate / load_action / synthesize)."""
    from backend.section3 import sim_v2_bridge as sb
    from dataclasses import dataclass

    @dataclass
    class _Fix:
        fixture_id: str
        input_args: tuple
        input_kwargs: dict

    @dataclass
    class _Report:
        fixtures: list

    class _Action:
        def __init__(self, fqn): self.fqn = fqn

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "translate_java_to_python",
        lambda body: ("def validate(o):\n    return 'OK'\n", "validate"),
    )
    monkeypatch.setattr(
        sb, "load_action",
        lambda session, fqn, repo: _Action(fqn),
    )
    monkeypatch.setattr(
        sb, "synthesize_fixtures",
        lambda session, action, *, function_name, python_source, max_combinations=12: _Report(
            fixtures=[
                _Fix(fixture_id="fx-1", input_args=(None,), input_kwargs={}),
            ],
        ),
    )


def _gate_ii_catalog():
    fqn = "com.slab.SdOrderValidator.validate(SDOrderEntity)"
    return {
        "actions": [
            {
                "action_id": "action.scm.order.정합성_검증",
                "label": "주문 검증",
                "code_method_fqn": fqn,
                "aliases": ["주문검증"],
                "repo_id": "slab-design-real-v2",
                "location": {
                    "file_path": "SdOrderValidator.java",
                    "line_start": 12, "line_end": 48,
                },
            },
        ],
        "method_bodies": {
            fqn: "public Result validate(SDOrderEntity o) { return Result.OK; }",
        },
        "entity_schemas": {
            "SDOrderEntity": {
                "entity_name": "SDOrderEntity",
                "fields": [
                    {"name": "id", "type_name": "varchar(64)", "nullable": False},
                ],
            },
        },
    }


def test_respond_turn_3_runs_gate_ii(client_factory, monkeypatch) -> None:
    _stub_gate_ii_bridge(monkeypatch)
    cat = _gate_ii_catalog()
    client = client_factory(forced_intent="simulate", catalog=cat)

    # turn 1 (start)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    # turn 2 (Gate I)
    client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "주문 검증"},
    )
    # confirm turn 2 — selected_index=0
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    # turn 3 (Gate II)
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "이 bundle 로 진행"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["turn_no"] == 3
    payload = body["payload"]
    assert payload["kind"] == "bundle_prepared"
    assert payload["target"]["code_method_fqn"] == (
        "com.slab.SdOrderValidator.validate(SDOrderEntity)"
    )
    assert "validate" in payload["java_source"]
    assert "def validate" in payload["python_source"]
    assert payload["schema_summary"]["entity_name"] == "SDOrderEntity"
    assert len(payload["fixtures"]) == 1
    assert payload["confidence"] > 0.7


def test_respond_turn_3_uses_candidate_fqn_when_action_detail_fqn_empty(
    fresh_db, monkeypatch,
) -> None:
    """Phase 10 fix: get_action_detail 응답의 code_method_fqn 이 빈 경우,
    candidate 의 valid fqn 으로 fallback 해야 Gate II 가 body 를 fetch 할 수 있다.
    Phase 6 시드의 realization 미연결 action 의 정상 동작 보장.
    """
    _stub_gate_ii_bridge(monkeypatch)
    _stub_sim_v2(monkeypatch, [])

    from backend.section3.api import multiturn_router as router_mod
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    from backend.section3.agents.multiturn.schemas import (
        ActionRef, CodeLocation,
    )

    chosen_fqn = "com.slab.SdOrderValidator.validate(SDOrderEntity)"
    cat = _gate_ii_catalog()  # candidate 의 valid fqn 그대로

    class _EmptyDetailClient(MockOntologyClient):
        async def get_action_detail(self, action_id, *, repo_id):
            # 실 sec2 시뮬: realization 부재 → code_method_fqn="" 반환
            return ActionRef(
                action_id=action_id,
                code_method_fqn="",
                repo_id=repo_id,
                location=CodeLocation(file_path="", line_start=0, line_end=0),
            )

    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(forced_intent="simulate", forced_confidence=0.9)
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        _EmptyDetailClient(catalog=cat)
    )
    client = TestClient(app)

    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "주문 검증"},
    )
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "이 bundle 로 진행"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()["payload"]
    assert payload["kind"] == "bundle_prepared"
    # candidate fqn 으로 fallback → body fetch 가 동작
    assert payload["target"]["code_method_fqn"] == chosen_fqn
    assert "validate" in payload["java_source"]


def test_respond_turn_3_invalid_selected_index_returns_422(
    client_factory, monkeypatch,
) -> None:
    _stub_gate_ii_bridge(monkeypatch)
    cat = _gate_ii_catalog()
    client = client_factory(forced_intent="simulate", catalog=cat)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "주문"},
    )
    # 범위 밖 selected_index
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 999}},
    )
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "go"},
    )
    assert r.status_code == 422


def test_respond_turn_3_impact_intent_runs_gate_iii_impact(
    client_factory, monkeypatch,
) -> None:
    """impact intent → Gate II skip → Gate III impact (Phase 2 wired)."""
    _stub_gate_ii_bridge(monkeypatch)
    _stub_gate_iii_impact_bridge(monkeypatch)
    cat = _gate_ii_catalog_with_caller_graph()
    client = client_factory(forced_intent="impact", catalog=cat)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "주문"},
    )
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "검토"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["turn_no"] == 3
    payload = body["payload"]
    assert payload["kind"] == "executed_impact"
    assert len(payload["affected_methods"]) >= 1
    assert payload["confidence"] >= 0.5

    # session.status = done
    sess = client.get(f"/api/section3/multiturn/session/{sid}").json()
    assert sess["session"]["status"] == "done"


def test_respond_turn_3_ambiguous_intent_returns_422(
    client_factory, monkeypatch,
) -> None:
    """ambiguous intent → 재분류 필요 (422)."""
    _stub_gate_ii_bridge(monkeypatch)
    cat = _gate_ii_catalog()
    client = client_factory(forced_intent="ambiguous", catalog=cat)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "x", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "x"},
    )
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "go"},
    )
    assert r.status_code == 422
    assert "ambiguous" in r.text.lower()


def test_respond_turn_4_runs_gate_iii_sim(
    client_factory, monkeypatch,
) -> None:
    """simulate path: turn 4 = Gate III sim (run fixtures + invariant)."""
    _stub_gate_ii_bridge(monkeypatch)
    _stub_gate_iii_sim_bridge(monkeypatch)
    cat = _gate_ii_catalog()
    client = client_factory(forced_intent="simulate", catalog=cat)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "주문"},
    )
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "go"},
    )
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "run"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["turn_no"] == 4
    payload = body["payload"]
    assert payload["kind"] == "executed_simulation"
    assert payload["invariant_status"] == "clean"
    assert len(payload["results"]) >= 1

    # session.status = done
    sess = client.get(f"/api/section3/multiturn/session/{sid}").json()
    assert sess["session"]["status"] == "done"


def test_respond_turn_5_returns_501_session_closed(
    client_factory, monkeypatch,
) -> None:
    """Gate III 후 추가 /respond 는 501 (session 종료)."""
    _stub_gate_ii_bridge(monkeypatch)
    _stub_gate_iii_sim_bridge(monkeypatch)
    cat = _gate_ii_catalog()
    client = client_factory(forced_intent="simulate", catalog=cat)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    r2 = client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "주문 검증"},
    )
    assert r2.status_code == 200, r2.text
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    r3 = client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "go"},
    )
    assert r3.status_code == 200, r3.text
    r4 = client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "run"},
    )
    assert r4.status_code == 200, r4.text
    # turn 5 — session 이미 done
    r5 = client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "more"},
    )
    assert r5.status_code == 501
    assert "완료" in r5.text or "already" in r5.text.lower() or "이미" in r5.text


# ─────────────────────────────────────────────────────────────────────────────
# Gate III stub helpers
# ─────────────────────────────────────────────────────────────────────────────


def _gate_ii_catalog_with_caller_graph():
    cat = _gate_ii_catalog()
    fqn = "com.slab.SdOrderValidator.validate(SDOrderEntity)"
    cat["caller_graphs"] = {
        fqn: [
            {"fqn": "com.slab.SdOrderService.process",
             "distance": 1, "via": "direct_caller"},
        ],
    }
    return cat


def _stub_gate_iii_sim_bridge(monkeypatch):
    """sim_v2_bridge Gate III sim 함수 stub: build_stubs + run_fixtures_in_process."""
    from backend.section3 import sim_v2_bridge as sb

    monkeypatch.setattr(
        sb, "build_stubs",
        lambda session, *, method_fqn, repo_id, python_source: {},
    )
    monkeypatch.setattr(
        sb, "run_fixtures_in_process",
        lambda fixtures, *, stub_namespace=None, declared_return="Any", allowed_exceptions=(): [
            {"case_id": getattr(f, "fixture_id", "fx-x"),
             "input": {"args": list(getattr(f, "input_args", ())),
                       "kwargs": dict(getattr(f, "input_kwargs", {}))},
             "execution": {"ok": True, "result": {"ok": True, "result": "OK"},
                           "error": None},
             "invariant_status": "PASS"}
            for f in fixtures
        ],
    )


def _stub_gate_iii_impact_bridge(monkeypatch):
    """sim_v2_bridge Gate III impact 함수 stub: quick_diagnose_action."""
    from backend.section3 import sim_v2_bridge as sb

    monkeypatch.setattr(
        sb, "quick_diagnose_action",
        lambda session, action: {
            "ok": True, "fixtures": 5, "stubs": 2, "passing": 5,
            "primary_failure": "",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /session/{id}/stream — Phase 1 minimal SSE
# ─────────────────────────────────────────────────────────────────────────────


def test_run_custom_executes_simple_python(client) -> None:
    """Phase 11 — run-custom: 사용자가 편집한 python_source 실행."""
    src = (
        "def my_add(a, b):\n"
        "    return a + b\n"
    )
    r = client.post(
        "/api/section3/multiturn/run-custom",
        json={
            "python_source": src,
            "function_name": "my_add",
            "fixtures": [
                {"fixture_id": "fx-1", "input_args": [1, 2]},
                {"fixture_id": "fx-2", "input_args": [10, -3]},
            ],
            "declared_return": "int",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["function_name"] == "my_add"
    assert body["blocked"] is False
    assert len(body["cases"]) == 2
    for c in body["cases"]:
        assert c["status"] in ("PASS", "FAIL_RETURN_TYPE")  # int 받으면 PASS


def test_run_custom_blocks_unsafe_imports(client) -> None:
    """Phase 11 — `import os` 등 위험 import 는 차단."""
    src = (
        "import os\n"
        "def hack():\n"
        "    return os.environ\n"
    )
    r = client.post(
        "/api/section3/multiturn/run-custom",
        json={
            "python_source": src, "function_name": "hack",
            "fixtures": [{"fixture_id": "fx-1", "input_args": []}],
        },
    )
    body = r.json()
    assert body["blocked"] is True
    assert "os" in body["block_reason"]
    assert body["cases"] == []


def test_run_custom_blocks_syntax_error(client) -> None:
    """syntax error 도 blocked + reason surface."""
    r = client.post(
        "/api/section3/multiturn/run-custom",
        json={
            "python_source": "def f(:\n  pass",
            "function_name": "f",
            "fixtures": [{"fixture_id": "fx", "input_args": []}],
        },
    )
    body = r.json()
    assert body["blocked"] is True
    assert "Syntax" in body["block_reason"]


def test_run_custom_requires_fixtures(client) -> None:
    """fixtures 비어있으면 blocked."""
    r = client.post(
        "/api/section3/multiturn/run-custom",
        json={
            "python_source": "def f(): return 1",
            "function_name": "f", "fixtures": [],
        },
    )
    body = r.json()
    assert body["blocked"] is True
    assert "fixtures" in body["block_reason"]


def test_stream_emits_current_snapshot(client) -> None:
    """SSE: 연결 직후 즉시 snapshot emit. 첫 snapshot 만 받고 close.
    decision dict 에 id 필드 포함 — 프론트엔드 React key 충돌 방지.
    """
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "x", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    with client.stream("GET", f"/api/section3/multiturn/session/{sid}/stream") as r:
        assert r.status_code == 200
        collected: list[str] = []
        for line in r.iter_lines():
            collected.append(line)
            # data 행 받으면 종료 (SSE 는 active 동안 무한 alive)
            if line and line.startswith("data:") and "target_selected" in line:
                break
    body = "\n".join(collected)
    assert "target_selected" in body
    assert "event: snapshot" in body
    # SSE snapshot 의 decisions 각 row 는 id + created_at 포함해야 한다
    # (Phase 7~10 fix — 빠진 id 가 React key 충돌 유발했었음)
    import json as _json
    data_line = next(ln for ln in collected if ln.startswith("data:") and "decisions" in ln)
    snap = _json.loads(data_line[len("data: "):])
    assert "decisions" in snap and snap["decisions"]
    for d in snap["decisions"]:
        assert "id" in d and isinstance(d["id"], int)
        assert "created_at" in d


def test_stream_emits_done_when_session_complete(
    client_factory, monkeypatch,
) -> None:
    """SSE: session.status=done 이면 즉시 snapshot + done emit 후 종료."""
    _stub_gate_ii_bridge(monkeypatch)
    _stub_gate_iii_impact_bridge(monkeypatch)
    cl = client_factory(
        forced_intent="impact",
        catalog=_gate_ii_catalog_with_caller_graph(),
    )
    start = cl.post("/api/section3/multiturn/start", json={
        "user_query": "주문 영향", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    cl.post(f"/api/section3/multiturn/respond/{sid}", json={"message": "주문 영향"})
    cl.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    cl.post(f"/api/section3/multiturn/respond/{sid}", json={"message": "검토"})
    # 이제 session.status="done"
    with cl.stream("GET", f"/api/section3/multiturn/session/{sid}/stream") as r:
        chunks = list(r.iter_lines())   # done 이면 빨리 끝남
    body = "\n".join(chunks)
    assert "event: snapshot" in body
    assert "event: done" in body
