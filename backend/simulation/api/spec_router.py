"""spec 03 §1, §2 — Run lifecycle FastAPI router.

엔드포인트:
- POST /api/simulation/runs                         → spec 03 §1.1 (CreateRunRequest → RunHandle)
- GET  /api/simulation/runs                         → spec 03 §1.3 (list with status filter)
- GET  /api/simulation/runs/{run_id}                → spec 03 §1.2 (RunHandle polling)
- GET  /api/simulation/runs/{run_id}/sim-result     → spec 03 §2.1 (SimResult)
- GET  /api/simulation/runs/{run_id}/changespec     → spec 03 §2.2 (재현 / 디버깅)

★ STEP 3c (2026-05-10) — modeling facade 통합:
- Default orchestrator 가 실 `OntologyQueryClientImpl()` 사용 (Section 2 의 ontology DB 기반)
- RunPlan 도 `RunPlanBuilder` 가 `delegates_to_tree`/expected_brs/expected_anchors/
  primary_input_type 모두 ontology 에서 derive
- `_NullOntologyClient` 클래스는 보존 (test override / 비상 fallback 용 — 더 이상 default 아님)

지원하지 않는 spec 03 endpoints (후속 step):
- §2.3 GET /runs/{id}/artifacts
- §3.1 POST /runs/diff
- §4.1 POST /anchor-invalidate
- §5.1 POST /verification/promote
- §6.1 GET /health, §6.2 GET /capabilities
"""

from __future__ import annotations

import logging
from typing import Optional, Protocol

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
from backend.simulation.runner.run_plan_builder import RunPlanBuilder

logger = logging.getLogger(__name__)


# ─── Module singleton (process 단일) ─────────────────────────────


_store: Optional[RunHandleStore] = None
_orchestrator: Optional[Orchestrator] = None
_run_plan_builder: Optional[RunPlanBuilder] = None
_ontology_client: Optional[object] = None


class _OntologyClientProtocol(Protocol):
    """본 router 가 의존하는 ontology facade 의 최소 인터페이스 — duck-typed."""

    def get_action(self, fqn: str) -> object: ...
    def get_realizations_for_input_type(self, action_fqn: str, code_type_fqn: str) -> list: ...
    def get_anchor_bindings_for_action(self, action_fqn: str) -> list: ...
    def list_code_types(self, role: Optional[str] = None) -> list: ...


class _NullOntologyClient:
    """spec 05 §7.1 의 facade duck-typed stub — 비상/test override 용 (더 이상 default 아님).

    STEP 3c (2026-05-10) 부터 default 는 실 `OntologyQueryClientImpl()`. 본 클래스는
    modeling internal 이 깨졌거나 ontology DB 가 비어있을 때 router 가 부팅 자체는
    되도록 fallback 으로 보존.
    """

    def get_action(self, fqn): return None
    def get_realizations_for_input_type(self, *a, **k): return []
    def get_anchor_bindings_for_action(self, fqn): return []
    def list_code_types(self, role=None): return []


def _build_default_ontology_client() -> _OntologyClientProtocol:
    """실 modeling facade — `OntologyQueryClientImpl()` 인스턴스화.

    facade 는 SQLite-backed (CodeLayerStore / DomainLayerStore / MappingLayerStore).
    bootstrap 실패 시 _NullOntologyClient 로 graceful fallback (router 자체는 부팅).
    """
    try:
        # 부분 import — modeling 의 internal layer 직접 import 금지 (Section isolation).
        # backend.modeling.api.ontology_query 는 facade 모듈 (CLAUDE.md 허용).
        from backend.modeling.api.ontology_query import OntologyQueryClientImpl

        client = OntologyQueryClientImpl()
        logger.info("spec_router: OntologyQueryClientImpl wired (실 ontology DB 기반)")
        return client
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "spec_router: OntologyQueryClientImpl 인스턴스화 실패 — _NullOntologyClient fallback (%s)",
            exc,
        )
        return _NullOntologyClient()


def _build_default_orchestrator() -> Orchestrator:
    """singleton orchestrator — 실 OntologyQueryClient 기반 stub backend.

    STEP 3c 이전: NullOntologyClient default → 모든 dispatch 가 inconclusive.
    STEP 3c 이후: 실 ontology DB 기반 — action.realizations / anchor_bindings /
    BR (preconditions+postconditions) 모두 ontology 에서 fetch.
    """
    global _ontology_client
    if _ontology_client is None:
        _ontology_client = _build_default_ontology_client()
    ont = _ontology_client
    return Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), ont),
        lookup_source_factory=lambda fixture: LookupDataSource(ont, fixture),
    )


def _build_default_run_plan_builder() -> RunPlanBuilder:
    """singleton RunPlanBuilder — orchestrator 와 같은 ontology client 공유."""
    global _ontology_client
    if _ontology_client is None:
        _ontology_client = _build_default_ontology_client()
    return RunPlanBuilder(_ontology_client)


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


def get_run_plan_builder() -> RunPlanBuilder:
    """RunPlanBuilder singleton — test 시 dependency_overrides[get_run_plan_builder] 로 override."""
    global _run_plan_builder
    if _run_plan_builder is None:
        _run_plan_builder = _build_default_run_plan_builder()
    return _run_plan_builder


def reset_singletons() -> None:
    """test fixture / 의존성 교체 시 사용 — 모든 singleton 비움."""
    global _store, _orchestrator, _run_plan_builder, _ontology_client
    _store = None
    _orchestrator = None
    _run_plan_builder = None
    _ontology_client = None


# ─── Router ──────────────────────────────────────────────────────


router = APIRouter(prefix="/api/simulation", tags=["simulation-runs"])


# ─── Endpoints ───────────────────────────────────────────────────


@router.post("/runs", response_model=RunHandle)
def create_run(
    request: CreateRunRequest,
    store: RunHandleStore = Depends(get_store),
    orchestrator: Orchestrator = Depends(get_orchestrator),
    plan_builder: RunPlanBuilder = Depends(get_run_plan_builder),
) -> RunHandle:
    """spec 03 §1.1 — POST /api/simulation/runs.

    sync 실행. RunPlan 은 RunPlanBuilder 가 modeling facade (ontology DB) 에서 derive.
    orchestrator.run() 동기 호출 후 RunHandle 의 최종 status 반환.
    완료 후 GET /runs/{id}/sim-result 로 SimResult 조회.
    """
    plan = plan_builder.build(request.change_spec.action_fqn)
    handle = store.submit(request=request, orchestrator=orchestrator, run_plan=plan)
    logger.debug(
        "POST /runs created %s status=%s (plan: %d frames, %d expected_anchors, warnings=%d)",
        handle.run_id, handle.status,
        len(plan.delegates_to_tree), len(plan.expected_anchors), len(plan.warnings),
    )
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


__all__ = [
    "router",
    "get_store",
    "get_orchestrator",
    "get_run_plan_builder",
    "reset_singletons",
]
