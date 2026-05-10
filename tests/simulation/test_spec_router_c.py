"""spec 03 §2.3 / §3.1 / §4.1 / §5.1 / §6.1 / §6.2 endpoints (STEP 3c-C).

artifacts / runs/diff / anchor-invalidate / verification/promote / health / capabilities.

TDD red→green. 각 endpoint 의 핵심 round-trip + 404 / 거부 case 검증.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ─── 공통 fixture ──────────────────────────────────────────────────


@pytest.fixture
def app_with_store_and_orch():
    """fresh store + minimal orchestrator (NullOnt) + spec_router."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.api.run_handle import RunHandleStore
    from backend.simulation.api import spec_router
    from backend.simulation.runner.java_sandbox import StubJavaSandbox
    from backend.simulation.runner.lookup_source import LookupDataSource
    from backend.simulation.runner.orchestrator import Orchestrator
    from backend.simulation.runner.python_generator import PythonGenerator
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    class _NullOnt:
        def get_action(self, fqn): return None
        def get_realizations_for_input_type(self, *a, **k): return []
        def get_anchor_bindings_for_action(self, fqn): return []
        def get_anchor_bindings_for_method(self, fqn): return []
        def list_actions(self): return []
        def list_code_types(self, role=None): return []

    ont = _NullOnt()
    store = RunHandleStore()
    orch = Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), ont),
        lookup_source_factory=lambda fx: LookupDataSource(ont, fx),
    )
    builder = RunPlanBuilder(ont)

    app = FastAPI()
    app.include_router(spec_router.router)
    app.dependency_overrides[spec_router.get_store] = lambda: store
    app.dependency_overrides[spec_router.get_orchestrator] = lambda: orch
    app.dependency_overrides[spec_router.get_run_plan_builder] = lambda: builder
    return app, store


@pytest.fixture
def client(app_with_store_and_orch):
    app, _ = app_with_store_and_orch
    return TestClient(app)


def _create_run(client, action="action.x", overrides=None):
    body = {
        "change_spec": {
            "action_fqn": action,
            "atomic_overrides": overrides or {},
            "scenario_fixture": {"lookups": {}},
        }
    }
    resp = client.post("/api/simulation/runs", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["run_id"]


# ─── C1: GET /runs/{id}/artifacts ─────────────────────────────────


def test_get_artifacts_returns_bundle_with_generated_python(client):
    run_id = _create_run(client)
    resp = client.get(f"/api/simulation/runs/{run_id}/artifacts")
    assert resp.status_code == 200
    bundle = resp.json()
    assert bundle["run_id"] == run_id
    kinds = {a["kind"] for a in bundle["artifacts"]}
    # generated_python / trace / input_fixture / output_dump 4종 보관됨
    assert "generated_python" in kinds
    assert "trace" in kinds


def test_get_artifacts_filter_by_kind(client):
    run_id = _create_run(client)
    resp = client.get(f"/api/simulation/runs/{run_id}/artifacts?kind=generated_python")
    assert resp.status_code == 200
    bundle = resp.json()
    assert all(a["kind"] == "generated_python" for a in bundle["artifacts"])


def test_get_artifacts_404_unknown_run(client):
    resp = client.get("/api/simulation/runs/run-nonexistent/artifacts")
    assert resp.status_code == 404


def test_get_artifact_raw_returns_python_text(client):
    run_id = _create_run(client)
    resp = client.get(f"/api/simulation/runs/{run_id}/artifacts/generated_python/raw")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/x-python")
    assert "def run(" in resp.text


def test_get_artifact_raw_404_unknown_kind(client):
    run_id = _create_run(client)
    resp = client.get(f"/api/simulation/runs/{run_id}/artifacts/nonsense/raw")
    assert resp.status_code == 404


# ─── C2: POST /runs/diff ───────────────────────────────────────────


def test_diff_two_runs_same_input_unchanged(client):
    rid1 = _create_run(client)
    rid2 = _create_run(client)

    resp = client.post(
        "/api/simulation/runs/diff",
        json={"base_run_id": rid1, "head_run_id": rid2},
    )
    assert resp.status_code == 200
    diff = resp.json()
    assert diff["base_run_id"] == rid1
    assert diff["head_run_id"] == rid2
    # 동일 input → diffs 비어있음
    assert diff["br_diffs"] == []
    assert diff["anchor_diffs"] == []


def test_diff_404_unknown_run(client):
    resp = client.post(
        "/api/simulation/runs/diff",
        json={"base_run_id": "nonexistent", "head_run_id": "alsonope"},
    )
    assert resp.status_code == 404


# ─── C3: POST /anchor-invalidate ──────────────────────────────────


def test_anchor_invalidate_returns_result_structure(client):
    """ontology client (NullOnt) 라 invalidated 빈 리스트, 그래도 200 반환."""
    resp = client.post(
        "/api/simulation/anchor-invalidate",
        json={
            "repo_id": "demo",
            "method_fqn": "com.X.method",
            "reason": "code_change",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "invalidated_anchor_ids" in data
    assert "affected_actions" in data
    assert "downgrade_count" in data


# ─── C4: POST /verification/promote ───────────────────────────────


def test_promote_to_sim_verified_blocked_without_evidence(client):
    """SIM_VERIFIED 진급 — evidence run 없으면 blocked."""
    resp = client.post(
        "/api/simulation/verification/promote",
        json={
            "action_fqn": "action.x",
            "target_level": "SIM_VERIFIED",
            "evidence_run_ids": [],
            "approver": "tester",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked_reason"] is not None
    assert "evidence" in data["blocked_reason"].lower() or "sim_verified" in data["blocked_reason"].lower()


def test_promote_to_body_anchored_allowed(client):
    """SIM_VERIFIED 외 진급은 echo-stub 에서 항상 허용 (modeling 측에서 storage update)."""
    resp = client.post(
        "/api/simulation/verification/promote",
        json={
            "action_fqn": "action.x",
            "target_level": "BODY_ANCHORED",
            "evidence_run_ids": [],
            "approver": "tester",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked_reason"] is None
    assert data["new_level"] == "BODY_ANCHORED"
    assert data["promoted_at"]


# ─── C5: GET /health, /capabilities ───────────────────────────────


def test_health_returns_status_ok_with_zero_queue(client):
    resp = client.get("/api/simulation/health")
    assert resp.status_code == 200
    h = resp.json()
    assert h["status"] == "ok"
    assert h["sandbox_available"] is True
    assert h["jvm_available"] is False  # stub only
    assert h["queue_depth"] == 0


def test_health_queue_depth_reflects_pending_runs(client, app_with_store_and_orch):
    """pending 상태의 run 만 남도록 store 직접 조작."""
    _, store = app_with_store_and_orch
    from backend.shared.contracts.simulation import ChangeSpec, CreateRunRequest

    store.register(CreateRunRequest(change_spec=ChangeSpec(action_fqn="x")))  # pending
    store.register(CreateRunRequest(change_spec=ChangeSpec(action_fqn="y")))  # pending

    resp = client.get("/api/simulation/health")
    assert resp.json()["queue_depth"] == 2


def test_capabilities_returns_supported_features(client):
    resp = client.get("/api/simulation/capabilities")
    assert resp.status_code == 200
    cap = resp.json()
    assert "pure_function" in cap["supported_action_kinds"]
    assert "workflow" in cap["supported_action_kinds"]
    assert "sim_verified" in cap["supported_verdicts"]
    assert cap["runner_version"]
    assert cap["max_timeout_sec"] >= 1
