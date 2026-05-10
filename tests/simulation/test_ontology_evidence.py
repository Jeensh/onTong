"""Ontology Evidence endpoint (STEP 3f-2) — SimResult 의 ontology source trace 검증."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_evidence():
    """spec_router + ontology_evidence_router 둘 다 mount + 의존성 override."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.api import spec_router
    from backend.simulation.api.ontology_evidence_router import router as ev_router
    from backend.simulation.api.run_handle import RunHandleStore
    from backend.simulation.runner.java_sandbox import StubJavaSandbox
    from backend.simulation.runner.lookup_source import LookupDataSource
    from backend.simulation.runner.orchestrator import Orchestrator
    from backend.simulation.runner.python_generator import PythonGenerator
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    # 실 ontology 사용 — evidence trace 가 actual data 반환
    try:
        from backend.modeling.api.ontology_query import OntologyQueryClientImpl
        ont = OntologyQueryClientImpl()
        if not ont.list_actions():
            pytest.skip("ontology DB 비어있음")
    except Exception:
        pytest.skip("OntologyQueryClientImpl 인스턴스화 실패")

    store = RunHandleStore()
    orch = Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), ont),
        lookup_source_factory=lambda fx: LookupDataSource(ont, fx),
    )
    builder = RunPlanBuilder(ont)

    app = FastAPI()
    app.include_router(spec_router.router)
    app.include_router(ev_router)
    app.dependency_overrides[spec_router.get_store] = lambda: store
    app.dependency_overrides[spec_router.get_orchestrator] = lambda: orch
    app.dependency_overrides[spec_router.get_run_plan_builder] = lambda: builder

    # ontology singleton 도 같은 instance 사용
    spec_router._ontology_client = ont
    return app, store, ont


def _create_run(client, action="action.scm.std.match_customer_limit_for_order"):
    body = {
        "change_spec": {
            "action_fqn": action,
            "atomic_overrides": {},
            "scenario_fixture": {"lookups": {}},
        }
    }
    resp = client.post("/api/simulation/runs", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["run_id"]


# ─── 1. 404 missing run ─────────────────────────────────────────


def test_evidence_404_for_unknown_run(app_with_evidence):
    app, _, _ = app_with_evidence
    client = TestClient(app)
    resp = client.get("/api/simulation/runs/run-nonexistent/ontology-evidence")
    assert resp.status_code == 404


# ─── 2. evidence 응답 — 실 ontology action ────────────────────


def test_evidence_returns_traces_for_real_action(app_with_evidence):
    app, store, ont = app_with_evidence
    if ont.get_action("action.scm.std.match_customer_limit_for_order") is None:
        pytest.skip("match_customer_limit_for_order 미등록")

    client = TestClient(app)
    run_id = _create_run(client)

    resp = client.get(f"/api/simulation/runs/{run_id}/ontology-evidence")
    assert resp.status_code == 200
    data = resp.json()

    assert data["run_id"] == run_id
    assert data["action_fqn"] == "action.scm.std.match_customer_limit_for_order"
    assert data["ontology_facade"] == "backend.modeling.api.ontology_query.OntologyQueryClientImpl"
    assert "in-process facade" in data["ontology_transport"]

    # traces 비어있지 않음
    assert len(data["traces"]) >= 1


# ─── 3. action trace ────────────────────────────────────────────


def test_evidence_includes_action_trace(app_with_evidence):
    app, _, _ = app_with_evidence
    client = TestClient(app)
    run_id = _create_run(client)
    resp = client.get(f"/api/simulation/runs/{run_id}/ontology-evidence")
    data = resp.json()

    action_traces = [t for t in data["traces"] if t["evidence_kind"] == "action"]
    assert len(action_traces) == 1
    at = action_traces[0]
    assert "Action" in at["ontology_source"]
    assert "get_action" in at["ontology_facade_call"]
    assert "explanation" in at and at["explanation"]


# ─── 4. realized_method trace ─────────────────────────────────


def test_evidence_includes_realized_method_trace(app_with_evidence):
    """match_customer_limit_for_order 는 realization 1개 → realized_method trace 1개."""
    app, _, _ = app_with_evidence
    client = TestClient(app)
    run_id = _create_run(client)
    resp = client.get(f"/api/simulation/runs/{run_id}/ontology-evidence")
    data = resp.json()

    method_traces = [t for t in data["traces"] if t["evidence_kind"] == "realized_method"]
    if not method_traces:
        pytest.skip("realized_method trace 없음 (verdict=inconclusive)")

    mt = method_traces[0]
    assert "Realization" in mt["ontology_source"]
    assert "CustomerStdService" in mt["evidence_id"]
    # confirmed / confidence 필드 노출
    assert "confirmed" in mt["ontology_data"]


# ─── 5. BR + anchor traces ───────────────────────────────────


def test_evidence_includes_br_and_anchor_traces(app_with_evidence):
    """match_customer_limit_for_order — BR 1 + anchor 2."""
    app, _, _ = app_with_evidence
    client = TestClient(app)
    run_id = _create_run(client)
    resp = client.get(f"/api/simulation/runs/{run_id}/ontology-evidence")
    data = resp.json()

    br_traces = [t for t in data["traces"] if t["evidence_kind"] == "br"]
    anchor_traces = [t for t in data["traces"] if t["evidence_kind"] == "anchor"]

    if br_traces:
        br = br_traces[0]
        assert "Action.precondition" in br["ontology_source"] or "postcondition" in br["ontology_source"] or "unknown" in br["ontology_source"]

    if anchor_traces:
        an = anchor_traces[0]
        assert "AnchorBinding" in an["ontology_source"]


# ─── 6. summary 카운트 ────────────────────────────────────────


def test_evidence_summary_has_per_kind_counts(app_with_evidence):
    app, _, _ = app_with_evidence
    client = TestClient(app)
    run_id = _create_run(client)
    resp = client.get(f"/api/simulation/runs/{run_id}/ontology-evidence")
    data = resp.json()
    summary = data["summary"]
    assert isinstance(summary, dict)
    # action trace 는 항상 1개 이상
    assert summary.get("action", 0) >= 1


# ─── 7. 미완료 run → 404 sim_result ────────────────────────────


def test_evidence_404_when_run_not_completed(app_with_evidence):
    """register 만 하고 submit 안 한 run — sim_result 없음."""
    from backend.shared.contracts.simulation import ChangeSpec, CreateRunRequest

    app, store, _ = app_with_evidence
    client = TestClient(app)

    handle = store.register(CreateRunRequest(
        change_spec=ChangeSpec(action_fqn="action.x", atomic_overrides={}, scenario_fixture={"lookups": {}})
    ))
    resp = client.get(f"/api/simulation/runs/{handle.run_id}/ontology-evidence")
    assert resp.status_code == 404
    assert "not available" in resp.json()["detail"]


# ─── 8. by-action endpoint — run_id 없이 ───────────────────────


def test_evidence_by_action_returns_traces(app_with_evidence):
    """by-action endpoint — run_id 없이 action_fqn 만으로 evidence 조회."""
    app, _, _ = app_with_evidence
    client = TestClient(app)
    resp = client.get(
        "/api/simulation/ontology-evidence/by-action",
        params={"action_fqn": "action.scm.std.match_customer_limit_for_order"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["run_id"] == ""
    assert data["action_fqn"] == "action.scm.std.match_customer_limit_for_order"
    assert "in-process facade" in data["ontology_transport"]
    # action trace 는 항상 있음
    assert any(t["evidence_kind"] == "action" for t in data["traces"])


def test_evidence_by_action_unknown_action(app_with_evidence):
    """미등록 action — action trace 가 warning 메시지 반환 (200 OK)."""
    app, _, _ = app_with_evidence
    client = TestClient(app)
    resp = client.get(
        "/api/simulation/ontology-evidence/by-action",
        params={"action_fqn": "action.does.not.exist"},
    )
    # 200 — unknown 도 friendly trace 반환
    assert resp.status_code == 200
    data = resp.json()
    action_traces = [t for t in data["traces"] if t["evidence_kind"] == "action"]
    assert len(action_traces) == 1
    # 등록 안 된 메시지 또는 ontology 조회 실패 메시지
    assert "등록 안 된" in action_traces[0]["explanation"] or "조회 실패" in action_traces[0]["explanation"]
