"""spec 03 §1, §2 — Run lifecycle FastAPI router.

엔드포인트:
- POST /api/simulation/runs                         → spec 03 §1.1 (CreateRunRequest → RunHandle)
- GET  /api/simulation/runs                         → spec 03 §1.3 (list with status filter)
- GET  /api/simulation/runs/{run_id}                → spec 03 §1.2 (RunHandle polling)
- GET  /api/simulation/runs/{run_id}/sim-result     → spec 03 §2.1 (SimResult)
- GET  /api/simulation/runs/{run_id}/changespec     → spec 03 §2.2 (재현 / 디버깅)

echo-stub iter 합의 (3b-6):
- sync 실행 (RunHandleStore.submit) — async queue 는 후속
- RunPlan 은 minimal — change_spec.action_fqn 1 frame 으로 (delegates_to_tree 자동 추출은 후속 STEP 4.1+)
- 의존성 주입: get_store / get_orchestrator (FastAPI Depends + 테스트 override 가능)
- 별도 ontology client 없이 동작 — orchestrator 가 stub backend 만 사용
- artifact / diff / verification / health 등은 후속 step

지원하지 않는 spec 03 endpoints (후속 step):
- §2.3 GET /runs/{id}/artifacts
- §3.1 POST /runs/diff
- §4.1 POST /anchor-invalidate
- §5.1 POST /verification/promote
- §6.1 GET /health, §6.2 GET /capabilities
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.shared.contracts.simulation import (
    ChangeSpec,
    CreateRunRequest,
    RunHandle,
    RunPlan,
    SandboxCapabilities,
    SimResult,
)
from backend.simulation.api.run_handle import RunHandleStore
from backend.simulation.runner.java_sandbox import StubJavaSandbox
from backend.simulation.runner.lookup_source import LookupDataSource
from backend.simulation.runner.orchestrator import Orchestrator
from backend.simulation.runner.python_generator import PythonGenerator

logger = logging.getLogger(__name__)


# ─── Module singleton (process 단일) ─────────────────────────────


_store: Optional[RunHandleStore] = None
_orchestrator: Optional[Orchestrator] = None


class _NullOntologyClient:
    """spec 05 §7.1 의 facade duck-typed stub.

    modeling 측 OntologyQueryClientImpl 가 wire 안 된 dev 환경에서도 router 동작.
    실제 wiring 은 별도 step (Section 2 ↔ Section 3 통합 작업 시).
    """

    def get_action(self, fqn): return None
    def get_realizations_for_input_type(self, *a, **k): return []
    def get_anchor_bindings_for_action(self, fqn): return []
    def list_code_types(self, role=None): return []


def _build_default_orchestrator() -> Orchestrator:
    """singleton orchestrator — NullOntologyClient 기반 stub backend.

    실제 modeling facade wiring 은 통합 작업 시 본 함수 교체.
    """
    ont = _NullOntologyClient()
    return Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), ont),
        lookup_source_factory=lambda fixture: LookupDataSource(ont, fixture),
    )


# ─── FastAPI Depends — 테스트에서 override 가능 ───────────────


def get_store() -> RunHandleStore:
    """RunHandleStore singleton — test 시 dependency_overrides[get_store] 로 override."""
    global _store
    if _store is None:
        _store = RunHandleStore()
    return _store


def get_orchestrator() -> Orchestrator:
    """Orchestrator singleton — test 시 dependency_overrides[get_orchestrator] 로 override."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = _build_default_orchestrator()
    return _orchestrator


# ─── Router ──────────────────────────────────────────────────────


router = APIRouter(prefix="/api/simulation", tags=["simulation-runs"])


# ─── Internal — RunPlan minimal builder ──────────────────────────


def _build_minimal_run_plan(change_spec: ChangeSpec) -> RunPlan:
    """change_spec.action_fqn 으로 1 frame RunPlan 생성 (echo-stub iter).

    실제 delegates_to_tree 추출은 후속 STEP 4.1+ — modeling 의
    /api/ontology/actions/{fqn}/delegates-to-tree 호출.
    """
    return RunPlan(
        delegates_to_tree=[
            {
                "action_fqn": change_spec.action_fqn,
                "depth": 1,
                "primary_input_type": "scm.order.Order",  # echo-stub default
            }
        ],
        estimated_steps=1,
    )


# ─── Endpoints ───────────────────────────────────────────────────


@router.post("/runs", response_model=RunHandle)
def create_run(
    request: CreateRunRequest,
    store: RunHandleStore = Depends(get_store),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> RunHandle:
    """spec 03 §1.1 — POST /api/simulation/runs.

    echo-stub iter: sync 실행. orchestrator.run() 동기 호출 후 RunHandle 의 최종 status 반환.
    완료 후 GET /runs/{id}/sim-result 로 SimResult 조회.
    """
    plan = _build_minimal_run_plan(request.change_spec)
    handle = store.submit(request=request, orchestrator=orchestrator, run_plan=plan)
    logger.debug("POST /runs created %s status=%s", handle.run_id, handle.status)
    return handle


@router.get("/runs", response_model=list[RunHandle])
def list_runs(
    status: Optional[str] = Query(default=None),
    store: RunHandleStore = Depends(get_store),
) -> list[RunHandle]:
    """spec 03 §1.3 — GET /api/simulation/runs?status=...

    spec 의 다른 filter (target_action_fqn / requested_by / since / limit) 는
    후속 step. 현재는 status 만 지원.
    """
    return store.list(status=status)


@router.get("/runs/{run_id}", response_model=RunHandle)
def get_run(
    run_id: str,
    store: RunHandleStore = Depends(get_store),
) -> RunHandle:
    """spec 03 §1.2 — GET /api/simulation/runs/{run_id}."""
    handle = store.get(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"run_id {run_id!r} not found")
    return handle


@router.get("/runs/{run_id}/sim-result", response_model=SimResult)
def get_sim_result(
    run_id: str,
    store: RunHandleStore = Depends(get_store),
) -> SimResult:
    """spec 03 §2.1 — GET /api/simulation/runs/{run_id}/sim-result.

    404 if:
      - run_id 미등록
      - run 이 completed 가 아님 (sim_result 미저장)
    """
    handle = store.get(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"run_id {run_id!r} not found")
    sr = store.get_sim_result(run_id)
    if sr is None:
        raise HTTPException(
            status_code=404,
            detail=f"sim_result for {run_id!r} not available — current status: {handle.status}",
        )
    return sr


@router.get("/runs/{run_id}/changespec", response_model=ChangeSpec)
def get_changespec(
    run_id: str,
    store: RunHandleStore = Depends(get_store),
) -> ChangeSpec:
    """spec 03 §2.2 — GET /api/simulation/runs/{run_id}/changespec (재현 / 디버깅)."""
    cs = store.get_change_spec(run_id)
    if cs is None:
        raise HTTPException(status_code=404, detail=f"run_id {run_id!r} not found")
    return cs


__all__ = ["router", "get_store", "get_orchestrator"]
