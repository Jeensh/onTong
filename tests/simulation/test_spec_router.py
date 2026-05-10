"""spec 03 router (POST /runs / GET /runs/{id}/...) — FastAPI TestClient 기반.

echo-stub iter 합의:
- TestClient app fixture — spec_router 만 mount + 의존성 override
- 실제 ontology / sandbox 없이 endpoint round-trip 검증
- POST /runs 응답 → GET /runs/{id} 로 같은 handle 조회 가능
- get_sim_result 가 completed 후에만 SimResult 반환

TDD — 본 테스트가 먼저, spec_router.py 에 코드 추가 후 GREEN.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ─── 테스트 app fixture (spec_router 만 mount) ─────────────────────


@pytest.fixture
def app_with_spec_router():
    """FastAPI app — spec_router + 의존성 override.

    의존성:
      - RunHandleStore: fresh per-test (모듈 singleton 회피)
      - Orchestrator: NullOntologyClient 기반 sandbox/lookup_factory
    """
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
        def list_code_types(self, role=None): return []

    ont = _NullOnt()
    store = RunHandleStore()
    orch = Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), ont),
        lookup_source_factory=lambda fixture: LookupDataSource(ont, fixture),
    )
    plan_builder = RunPlanBuilder(ont)

    app = FastAPI()
    app.include_router(spec_router.router)
    app.dependency_overrides[spec_router.get_store] = lambda: store
    app.dependency_overrides[spec_router.get_orchestrator] = lambda: orch
    app.dependency_overrides[spec_router.get_run_plan_builder] = lambda: plan_builder
    return app


@pytest.fixture
def client(app_with_spec_router):
    return TestClient(app_with_spec_router)


# ─── 헬퍼 ────────────────────────────────────────────────────────────


def _create_run_body(action="action.scm.std.match"):
    return {
        "change_spec": {
            "action_fqn": action,
            "atomic_overrides": {},
            "scenario_fixture": {"lookups": {}},
        },
        "requested_by": "tester",
    }


# ─── 1. POST /runs — 등록 + 실행 ────────────────────────────────────


def test_post_runs_returns_run_handle(client):
    """spec 03 §1.1 — POST /api/simulation/runs body=CreateRunRequest → RunHandle."""
    resp = client.post("/api/simulation/runs", json=_create_run_body())
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert data["run_id"].startswith("run-")
    assert data["status"] in ("completed", "failed", "running", "pending")
    # echo-stub iter 의 sync 실행이므로 보통 completed 또는 failed (terminal)
    assert "created_at" in data


def test_post_runs_persists_change_spec(client):
    """POST 후 GET /runs/{id}/changespec 로 ChangeSpec 조회."""
    resp = client.post("/api/simulation/runs", json=_create_run_body("action.demo"))
    run_id = resp.json()["run_id"]

    cs_resp = client.get(f"/api/simulation/runs/{run_id}/changespec")
    assert cs_resp.status_code == 200
    assert cs_resp.json()["action_fqn"] == "action.demo"


def test_post_runs_invalid_body_returns_422(client):
    """잘못된 body — 필드 빠짐 → 422 (FastAPI validation)."""
    resp = client.post("/api/simulation/runs", json={"missing": "fields"})
    assert resp.status_code == 422


# ─── 2. GET /runs/{run_id} — RunHandle polling ──────────────────────


def test_get_run_handle_by_id(client):
    """spec 03 §1.2 — GET /api/simulation/runs/{run_id}."""
    post = client.post("/api/simulation/runs", json=_create_run_body())
    run_id = post.json()["run_id"]

    resp = client.get(f"/api/simulation/runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id


def test_get_run_handle_unknown_returns_404(client):
    resp = client.get("/api/simulation/runs/run-nonexistent")
    assert resp.status_code == 404


# ─── 3. GET /runs/{run_id}/sim-result ───────────────────────────────


def test_get_sim_result_after_completion(client):
    """spec 03 §2.1 — 완료된 run 의 SimResult 반환."""
    post = client.post("/api/simulation/runs", json=_create_run_body())
    run_id = post.json()["run_id"]
    handle_status = post.json()["status"]
    if handle_status != "completed":
        pytest.skip(f"run not completed: {handle_status}")

    resp = client.get(f"/api/simulation/runs/{run_id}/sim-result")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["verdict"] in ("sim_verified", "sim_violation", "inconclusive")


def test_get_sim_result_unknown_run_returns_404(client):
    resp = client.get("/api/simulation/runs/run-nonexistent/sim-result")
    assert resp.status_code == 404


# ─── 4. GET /runs/{run_id}/changespec ───────────────────────────────


def test_get_changespec_unknown_returns_404(client):
    resp = client.get("/api/simulation/runs/run-nonexistent/changespec")
    assert resp.status_code == 404


def test_get_changespec_preserves_atomic_overrides(client):
    """ChangeSpec 의 atomic_overrides 가 보존됨."""
    body = _create_run_body("action.demo")
    body["change_spec"]["atomic_overrides"] = {"path.x": 1180}
    post = client.post("/api/simulation/runs", json=body)
    run_id = post.json()["run_id"]

    cs_resp = client.get(f"/api/simulation/runs/{run_id}/changespec")
    assert cs_resp.status_code == 200
    assert cs_resp.json()["atomic_overrides"] == {"path.x": 1180}


# ─── 5. GET /runs (list + filter) ───────────────────────────────────


def test_list_runs_returns_array(client):
    """spec 03 §1.3 — GET /api/simulation/runs → list[RunHandle]."""
    client.post("/api/simulation/runs", json=_create_run_body())
    client.post("/api/simulation/runs", json=_create_run_body())

    resp = client.get("/api/simulation/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert isinstance(runs, list)
    assert len(runs) >= 2


def test_list_runs_filter_by_status(client):
    """list?status=completed → completed 만."""
    client.post("/api/simulation/runs", json=_create_run_body())

    resp = client.get("/api/simulation/runs?status=completed")
    assert resp.status_code == 200
    runs = resp.json()
    assert all(r["status"] == "completed" for r in runs)


# ─── 6. e2e — POST → GET 흐름 정합 ──────────────────────────────────


def test_post_then_get_then_simresult_chain(client):
    """POST /runs → GET /runs/{id} → GET /runs/{id}/sim-result e2e."""
    body = _create_run_body("action.scm.std.demo")
    body["change_spec"]["scenario_fixture"]["metadata"] = {"scenario_origin": "TEST"}

    post = client.post("/api/simulation/runs", json=body)
    assert post.status_code == 200
    run_id = post.json()["run_id"]

    handle = client.get(f"/api/simulation/runs/{run_id}").json()
    assert handle["run_id"] == run_id

    if handle["status"] == "completed":
        sr = client.get(f"/api/simulation/runs/{run_id}/sim-result").json()
        assert sr["run_id"] == run_id

    cs = client.get(f"/api/simulation/runs/{run_id}/changespec").json()
    assert cs["action_fqn"] == "action.scm.std.demo"
    assert cs["scenario_fixture"]["metadata"]["scenario_origin"] == "TEST"


# ─── 7. main.py 등록 sanity (직접 import 시 충돌 없음) ─────────────


def test_spec_router_can_be_imported_as_module():
    """main.py 가 from backend.simulation.api.spec_router import router 로 등록 가능."""
    from backend.simulation.api.spec_router import router

    # FastAPI APIRouter 인스턴스
    from fastapi import APIRouter
    assert isinstance(router, APIRouter)
    # prefix 가 spec 03 와 정합
    assert router.prefix == "/api/simulation"
