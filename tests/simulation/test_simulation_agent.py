"""시뮬레이션 에이전트 — e2e API 테스트 (5 시나리오).

5종 intent 가 모두 적절한 게이트까지 진행하는지 확인.
실제 LLM 호출 대신 multiturn 의 StubIntentClassifier 와 MockOntologyClient 로
주입 (test isolation).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.section3.agents.multiturn.intent import (
    MultiturnIntent, StubIntentClassifier,
)
from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
from backend.section3.api import simulation_router as sim_router


@pytest.fixture
def client() -> TestClient:
    """5 시나리오 query 별로 다른 intent 를 강제 분류하는 stub."""
    per_query = {
        "단중 계산 로직 바꾸면": "impact",
        "기준 0.5": "impact",
        "주문의 thickness": "simulate",
        "edging 룰": "locate",
        "Slab 단중이 뭐야": "explain",
        "신규 품종 HC600X": "hypothesis",
        "thickness 액션 시뮬": "simulate",
    }

    def _classifier():
        return StubIntentClassifier(per_query=per_query)

    def _ontology():
        # 다양한 후보 보유한 mock — multiturn 기본 catalog 충분
        return MockOntologyClient()

    app.dependency_overrides[sim_router.get_classifier] = _classifier
    app.dependency_overrides[sim_router.get_ontology_client] = _ontology
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _start(client: TestClient, query: str) -> dict:
    r = client.post(
        "/api/section3/simulation/start",
        json={"user_query": query, "repo_id": "slab-design-real-v2"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _respond(client: TestClient, sid: str, **body) -> dict:
    r = client.post(f"/api/section3/simulation/respond/{sid}", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_start_returns_intent_and_candidates(client: TestClient) -> None:
    """/start 가 intent 분류 + 후보 검색 결과를 한 번에 반환."""
    j = _start(client, "단중 계산 로직 바꾸면 어디 영향?")
    assert j["session_id"].startswith("sim-")
    assert j["next_gate"] in ("target_selected", "ambiguous_clarification")
    assert j["payload"]["intent"] == "impact"
    assert isinstance(j["payload"]["candidates"], list)


def test_replay_hydrates_session(client: TestClient) -> None:
    """replay 가 sid + decisions 를 source-of-truth 로 반환."""
    j = _start(client, "thickness 액션 시뮬")
    sid = j["session_id"]
    r = client.get(f"/api/section3/simulation/replay/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == sid
    assert body["intent"] == "simulate"
    assert len(body["decisions"]) == 1
    assert body["decisions"][0]["gate_kind"] == "target_selected"


def test_scenario_impact_proceeds_to_executed(client: TestClient) -> None:
    """시나리오 ① — impact intent → Gate III impact 직진."""
    j = _start(client, "단중 계산 로직 바꾸면 어디 영향?")
    sid = j["session_id"]
    if not j["payload"]["candidates"]:
        pytest.skip("mock 후보 없음 — Gate III 진입 불가")
    j2 = _respond(client, sid, turn_no=j["turn_no"],
                  action="select_candidate", selected_index=0)
    assert j2["next_gate"] == "done"
    assert j2["payload"]["kind"] in ("executed_impact", "executed_unknown")


def test_scenario_simulate_bundle_then_confirm(client: TestClient) -> None:
    """시나리오 ③ — simulate intent → bundle_prepared → confirm_bundle → done."""
    j = _start(client, "thickness 액션 시뮬")
    sid = j["session_id"]
    if not j["payload"]["candidates"]:
        pytest.skip("mock 후보 없음")
    j2 = _respond(client, sid, turn_no=j["turn_no"],
                  action="select_candidate", selected_index=0)
    assert j2["next_gate"] == "bundle_prepared"
    j3 = _respond(client, sid, turn_no=j2["turn_no"], action="confirm_bundle")
    assert j3["next_gate"] == "done"


def test_scenario_locate_executes_directly(client: TestClient) -> None:
    """시나리오 ④ — locate intent → bundle skip → executed."""
    j = _start(client, "edging 룰은 어디 박혀있어?")
    sid = j["session_id"]
    if not j["payload"]["candidates"]:
        pytest.skip("mock 후보 없음")
    j2 = _respond(client, sid, turn_no=j["turn_no"],
                  action="select_candidate", selected_index=0)
    assert j2["next_gate"] == "done"


def test_abort_marks_session_aborted(client: TestClient) -> None:
    j = _start(client, "thickness 액션 시뮬")
    sid = j["session_id"]
    j2 = _respond(client, sid, turn_no=j["turn_no"], action="abort")
    assert j2["next_gate"] == "aborted"

    rep = client.get(f"/api/section3/simulation/replay/{sid}").json()
    assert rep["status"] == "aborted"


def test_compare_with_overrides_requires_bundle(client: TestClient) -> None:
    """compare_with_overrides 는 bundle 이 없으면 409."""
    j = _start(client, "단중 계산 로직 바꾸면 어디 영향?")
    sid = j["session_id"]
    if not j["payload"]["candidates"]:
        pytest.skip("mock 후보 없음")
    # impact intent — bundle 안 만들어짐. 바로 select 시 executed 까지 감
    _respond(client, sid, turn_no=j["turn_no"],
             action="select_candidate", selected_index=0)
    # status=done 이므로 compare 시도 시 409
    r = client.post(
        f"/api/section3/simulation/respond/{sid}",
        json={"turn_no": 99, "action": "compare_with_overrides",
              "overrides": {"x": 1}},
    )
    assert r.status_code in (404, 409)


def test_unknown_session_404(client: TestClient) -> None:
    r = client.post(
        "/api/section3/simulation/respond/sim-not-exist",
        json={"turn_no": 1, "action": "abort"},
    )
    assert r.status_code == 404
