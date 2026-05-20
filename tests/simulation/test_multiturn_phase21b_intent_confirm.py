"""Phase 21b — intent confirmation step (production flow).

사용자 vision: "의도 분류 후 '맞아?' 묻고 → confirm 후 candidates 진행".
candidates 보기 전 intent 잘못 분류된 걸 사용자가 catch.

state machine:
  /start → turn 1 stub (target_selected, intent=ambiguous, cand=0)
  /respond → turn 2 intent_classified (intent + search_terms + conditions)
  /confirm turn 2 (action=confirm) → next_gate_kind=target_selected
  /respond → turn 3 target_selected (intent + candidates)
  /confirm turn 3 (action=confirm, selected_index=N) → next_gate_kind=bundle_prepared/executed_*
  /respond → turn 4 bundle_prepared 또는 executed_* (intent 별)

기존 tests/simulation/conftest.py 가 autouse 로 INTENT_CONFIRM_REQUIRED=False
설정 → 이 파일은 함수-scope fixture 로 다시 True 로 override 하여 production
흐름 검증.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.persistence import database as db_mod
from backend.section3.agents.multiturn.intent import StubIntentClassifier
from backend.section3.agents.multiturn.ontology_client import MockOntologyClient


@pytest.fixture
def production_intent_confirm(monkeypatch):
    """Override conftest autouse → production 흐름 (INTENT_CONFIRM_REQUIRED=True)."""
    from backend.section3.api import multiturn_router as mr
    monkeypatch.setattr(mr, "INTENT_CONFIRM_REQUIRED", True)
    yield


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase21b.db"
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


_SLAB_CATALOG = {
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


def _client(forced_intent="simulate", catalog=_SLAB_CATALOG):
    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(forced_intent=forced_intent, forced_confidence=0.9)
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog=catalog)
    )
    return TestClient(app)


def test_first_respond_returns_intent_classified(
    fresh_db, production_intent_confirm, monkeypatch,
) -> None:
    """첫 /respond 는 intent_classified 만 (candidates 미수행)."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass
    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "find_action_candidates",
        lambda s, q, r, *, top_n=3: [],
    )

    client = _client(forced_intent="simulate")
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
    payload = body["payload"]
    # Phase 21b: turn 2 = intent_classified (candidates 미수행)
    assert payload["kind"] == "intent_classified"
    assert payload["intent"] == "simulate"
    assert payload["user_query"] == "주문 검증 시뮬"
    # candidates 필드는 아예 없음 (intent_classified schema)
    assert "candidates" not in payload


def test_confirm_intent_classified_returns_target_selected_kind(
    fresh_db, production_intent_confirm, monkeypatch,
) -> None:
    """intent_classified + confirm → next_gate_kind=target_selected."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass
    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "find_action_candidates",
        lambda s, q, r, *, top_n=3: [],
    )

    client = _client(forced_intent="simulate")
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
        json={"action": "confirm", "user_response": {}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["next_gate_kind"] == "target_selected"


def test_second_respond_returns_target_selected_with_candidates(
    fresh_db, production_intent_confirm, monkeypatch,
) -> None:
    """confirm intent_classified 후 /respond → turn 3 = target_selected (candidates)."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass
    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "find_action_candidates",
        lambda s, q, r, *, top_n=3: [],
    )

    client = _client(forced_intent="simulate")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    # turn 2 = intent_classified
    client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "주문 검증"},
    )
    # confirm intent
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {}},
    )
    # turn 3 = target_selected (Gate I real)
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "candidates 부탁"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["turn_no"] == 3
    payload = body["payload"]
    assert payload["kind"] == "target_selected"
    assert payload["intent"] == "simulate"
    # MockOntologyClient 의 catalog 후보가 들어와야
    fqns = [c["code_method_fqn"] for c in payload["candidates"]]
    assert "com.slab.OrderService.validateOrder" in fqns


def test_respond_without_intent_confirm_returns_422(
    fresh_db, production_intent_confirm, monkeypatch,
) -> None:
    """intent_classified turn confirm 안 됐는데 /respond 호출 → 422."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass
    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "find_action_candidates",
        lambda s, q, r, *, top_n=3: [],
    )

    client = _client(forced_intent="simulate")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "주문 검증"},
    )
    # confirm 없이 바로 두 번째 /respond
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "skip"},
    )
    assert r.status_code == 422
    assert "confirm" in r.text.lower()


def test_intent_classified_ambiguous_blocks_progression(
    fresh_db, production_intent_confirm, monkeypatch,
) -> None:
    """intent_classified 결과가 ambiguous 일 때 confirm 후 /respond → 422.

    Phase 21b: 사용자가 ambiguous 인데 confirm 했어도 candidates fetch 불가.
    UI 는 IntentStage 에서 confirm 버튼 disabled 시켜야 함 (이 테스트는 백엔드 가드).
    """
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass
    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "find_action_candidates",
        lambda s, q, r, *, top_n=3: [],
    )

    client = _client(forced_intent="ambiguous")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "뭐든", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "뭐든"},
    )
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {}},
    )
    r = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "skip"},
    )
    assert r.status_code == 422
    assert "ambiguous" in r.text.lower()


def test_intent_classified_retry_action_state_machine(
    fresh_db, production_intent_confirm,
) -> None:
    """state machine: intent_classified + retry → next_gate_kind=intent_classified."""
    client = _client(forced_intent="simulate")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(
        f"/api/section3/multiturn/respond/{sid}", json={"message": "주문"},
    )
    r = client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "retry", "user_response": {}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["next_gate_kind"] == "intent_classified"


def test_full_simulate_flow_through_phase21b(
    fresh_db, production_intent_confirm, monkeypatch,
) -> None:
    """End-to-end: stub → intent_classified → target_selected → bundle_prepared.

    Phase 21b 흐름 전체가 Gate II 까지 도달하는지 검증.
    """
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
        sb, "find_action_candidates",
        lambda s, q, r, *, top_n=3: [],
    )
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
        lambda session, action, *, function_name, python_source, max_combinations=12: (
            _Report(fixtures=[
                _Fix(fixture_id="fx-1", input_args=(None,), input_kwargs={}),
            ])
        ),
    )

    fqn = "com.slab.SdOrderValidator.validate(SDOrderEntity)"
    cat = {
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
    client = _client(forced_intent="simulate", catalog=cat)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    # turn 2: intent_classified
    r2 = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "주문 검증"},
    )
    assert r2.json()["payload"]["kind"] == "intent_classified"
    # confirm intent
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {}},
    )
    # turn 3: target_selected
    r3 = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "candidates please"},
    )
    assert r3.json()["payload"]["kind"] == "target_selected"
    # confirm candidate
    client.post(
        f"/api/section3/multiturn/confirm/{sid}/3",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    # turn 4: bundle_prepared
    r4 = client.post(
        f"/api/section3/multiturn/respond/{sid}",
        json={"message": "이 bundle"},
    )
    assert r4.status_code == 200, r4.text
    assert r4.json()["payload"]["kind"] == "bundle_prepared"
    assert r4.json()["turn_no"] == 4
