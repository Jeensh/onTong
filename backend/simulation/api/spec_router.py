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
    AnchorDiff,
    AnchorInvalidateRequest,
    AnchorInvalidateResult,
    Artifact,
    ArtifactBundle,
    BRDiff,
    Capabilities,
    ChangeSpec,
    CreateRunRequest,
    DiffRequest,
    DiffResult,
    FieldDiff,
    HealthStatus,
    PromoteRequest,
    PromoteResult,
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


# ─── Spec 03 §2.3 — GET /runs/{run_id}/artifacts ───────────────────


_ARTIFACT_CONTENT_TYPE = {
    "generated_python": "text/x-python",
    "jvm_log": "text/plain",
    "trace": "application/x-jsonlines",
    "input_fixture": "application/json",
    "output_dump": "application/json",
}


@router.get("/runs/{run_id}/artifacts", response_model=ArtifactBundle)
def get_artifacts(
    run_id: str,
    kind: Optional[str] = Query(default=None),
    store: RunHandleStore = Depends(get_store),
) -> ArtifactBundle:
    """spec 03 §2.3 — kind=generated_python|jvm_log|trace|input_fixture|output_dump|all."""
    if store.get(run_id) is None:
        raise HTTPException(status_code=404, detail=f"run_id {run_id!r} not found")

    available_kinds = store.list_artifact_kinds(run_id)
    if kind and kind != "all":
        available_kinds = [k for k in available_kinds if k == kind]

    artifacts: list[Artifact] = []
    for k in available_kinds:
        content = store.get_artifact(run_id, k) or ""
        size = len(content.encode("utf-8"))
        # head/tail summary (first 80 chars + "..." if long)
        summary = content[:80] + ("..." if len(content) > 80 else "")
        artifacts.append(Artifact(
            kind=k,  # type: ignore[arg-type]
            name=f"{k}.{_ext_for(k)}",
            content_type=_ARTIFACT_CONTENT_TYPE.get(k, "text/plain"),
            size_bytes=size,
            download_url=f"/api/simulation/runs/{run_id}/artifacts/{k}/raw",
            summary=summary,
        ))
    return ArtifactBundle(run_id=run_id, artifacts=artifacts)


def _ext_for(kind: str) -> str:
    mapping = {
        "generated_python": "py",
        "jvm_log": "log",
        "trace": "jsonl",
        "input_fixture": "json",
        "output_dump": "json",
    }
    return mapping.get(kind, "txt")


@router.get("/runs/{run_id}/artifacts/{kind}/raw")
def get_artifact_raw(
    run_id: str,
    kind: str,
    store: RunHandleStore = Depends(get_store),
):
    """spec 03 §2.3 — artifact raw download."""
    from fastapi.responses import PlainTextResponse

    if store.get(run_id) is None:
        raise HTTPException(status_code=404, detail=f"run_id {run_id!r} not found")
    content = store.get_artifact(run_id, kind)
    if content is None:
        raise HTTPException(status_code=404, detail=f"artifact {kind!r} for {run_id!r} not found")
    return PlainTextResponse(
        content=content,
        media_type=_ARTIFACT_CONTENT_TYPE.get(kind, "text/plain"),
    )


# ─── Spec 03 §3.1 — POST /runs/diff ────────────────────────────────


@router.post("/runs/diff", response_model=DiffResult)
def diff_runs(
    request: DiffRequest,
    store: RunHandleStore = Depends(get_store),
) -> DiffResult:
    """spec 03 §3.1 — base run vs head run 의 outputs/br/anchor/duration 비교."""
    base = store.get_sim_result(request.base_run_id)
    head = store.get_sim_result(request.head_run_id)
    if base is None:
        raise HTTPException(status_code=404, detail=f"base run_id {request.base_run_id!r} not found / not completed")
    if head is None:
        raise HTTPException(status_code=404, detail=f"head run_id {request.head_run_id!r} not found / not completed")

    output_diffs: list[FieldDiff] = []
    if "outputs" in request.aspects:
        output_diffs = _diff_dict("", base.output_values, head.output_values)

    br_diffs: list[BRDiff] = []
    if "br_evidence" in request.aspects:
        base_br = {b.br_fqn: b.outcome for b in base.br_evidence}
        head_br = {b.br_fqn: b.outcome for b in head.br_evidence}
        for fqn in sorted(set(base_br) | set(head_br)):
            bo = base_br.get(fqn)
            ho = head_br.get(fqn)
            change = _classify_change(bo, ho)
            if change != "unchanged":
                br_diffs.append(BRDiff(br_fqn=fqn, base_outcome=bo, head_outcome=ho, change=change))

    anchor_diffs: list[AnchorDiff] = []
    if "anchor_evidence" in request.aspects:
        base_a = {a.anchor_id: a.outcome for a in base.anchor_evidence}
        head_a = {a.anchor_id: a.outcome for a in head.anchor_evidence}
        for aid in sorted(set(base_a) | set(head_a)):
            bo = base_a.get(aid)
            ho = head_a.get(aid)
            change = _classify_change(bo, ho)
            if change != "unchanged":
                anchor_diffs.append(AnchorDiff(anchor_id=aid, base_outcome=bo, head_outcome=ho, change=change))

    duration_diff_ms: Optional[int] = None
    if "duration" in request.aspects:
        duration_diff_ms = head.duration_ms - base.duration_ms

    summary = (
        f"output_diffs={len(output_diffs)}, br_diffs={len(br_diffs)}, "
        f"anchor_diffs={len(anchor_diffs)}, "
        f"verdict={base.verdict} → {head.verdict}"
    )
    return DiffResult(
        base_run_id=request.base_run_id,
        head_run_id=request.head_run_id,
        output_diffs=output_diffs,
        br_diffs=br_diffs,
        anchor_diffs=anchor_diffs,
        duration_diff_ms=duration_diff_ms,
        summary=summary,
    )


def _classify_change(base: Optional[str], head: Optional[str]) -> str:
    if base is None and head is not None:
        return "added"
    if base is not None and head is None:
        return "removed"
    if base != head:
        return "changed"
    return "unchanged"


def _diff_dict(prefix: str, base: dict, head: dict) -> list[FieldDiff]:
    """단순 dict diff — nested 시 path 에 '.' 으로 join."""
    diffs: list[FieldDiff] = []
    keys = set(base.keys()) | set(head.keys())
    for k in sorted(keys):
        path = f"{prefix}.{k}" if prefix else k
        bv = base.get(k)
        hv = head.get(k)
        if isinstance(bv, dict) and isinstance(hv, dict):
            diffs.extend(_diff_dict(path, bv, hv))
            continue
        if bv != hv:
            change = _classify_change(
                None if k not in base else "present",
                None if k not in head else "present",
            )
            if change == "unchanged":
                change = "changed"
            diffs.append(FieldDiff(path=path, base_value=bv, head_value=hv, change=change))
    return diffs


# ─── Spec 03 §4.1 — POST /anchor-invalidate ────────────────────────


@router.post("/anchor-invalidate", response_model=AnchorInvalidateResult)
def anchor_invalidate(
    request: AnchorInvalidateRequest,
    ontology_client: object = Depends(lambda: _ontology_client or _build_default_ontology_client()),
) -> AnchorInvalidateResult:
    """spec 03 §4.1 — code 변경 시 stale anchor 일괄 invalidate.

    echo-stub iter: read-only 시뮬 — modeling 측 storage 에 실제 invalidate 안 함.
    `method_fqn` 으로 binding 을 fetch 해 어떤 anchor / action 이 영향 받는지만 보고.
    실 invalidation 은 modeling 측 endpoint (별도) 호출 필요.
    """
    invalidated: list[str] = []
    affected: set[str] = set()

    if request.method_fqn is not None:
        # 해당 method 의 anchor binding 들
        get_for_method = getattr(ontology_client, "get_anchor_bindings_for_method", None)
        if get_for_method is None:
            # fallback — list all actions, find bindings that target this method
            list_actions = getattr(ontology_client, "list_actions", lambda: [])
            for a in list_actions():
                get_for_action = getattr(ontology_client, "get_anchor_bindings_for_action", None)
                if get_for_action is None:
                    continue
                for b in (get_for_action(a.fqn) or []):
                    if getattr(b, "code_method_fqn", None) == request.method_fqn:
                        invalidated.append(getattr(b, "id", "?"))
                        target_action = getattr(b, "target_action_fqn", None)
                        if target_action:
                            affected.add(target_action)
        else:
            for b in (get_for_method(request.method_fqn) or []):
                invalidated.append(getattr(b, "id", "?"))
                target_action = getattr(b, "target_action_fqn", None)
                if target_action:
                    affected.add(target_action)

    return AnchorInvalidateResult(
        invalidated_anchor_ids=sorted(set(invalidated)),
        affected_actions=sorted(affected),
        downgrade_count=0,  # echo-stub: 실제 verification_level 업데이트는 modeling 책임
        suggested_resimulate_runs=[],
    )


# ─── Spec 03 §5.1 — POST /verification/promote ─────────────────────


@router.post("/verification/promote", response_model=PromoteResult)
def verification_promote(
    request: PromoteRequest,
    store: RunHandleStore = Depends(get_store),
) -> PromoteResult:
    """spec 03 §5.1 — VerificationLevel 진급.

    echo-stub iter: storage 에 실제 진급 저장 안 함 (modeling 책임). 본 endpoint 는
    evidence_run_ids 검증 + audit 응답 반환. SIM_VERIFIED 진급 시 evidence run 의
    verdict=sim_verified 1건 이상 있어야 허용.
    """
    promoted_at = datetime.now(timezone.utc).isoformat()

    if request.target_level == "SIM_VERIFIED":
        # evidence run 검증
        verified_runs = [
            rid for rid in request.evidence_run_ids
            if (store.get_sim_result(rid) or _no_sr()).verdict == "sim_verified"
        ]
        if not verified_runs:
            return PromoteResult(
                action_fqn=request.action_fqn,
                previous_level=None,
                new_level=request.target_level,
                promoted_at=promoted_at,
                blocked_reason="SIM_VERIFIED 진급 거부 — evidence_run_ids 중 verdict=sim_verified 인 run 없음",
            )

    return PromoteResult(
        action_fqn=request.action_fqn,
        previous_level=None,  # 실제 storage 조회 미구현
        new_level=request.target_level,
        promoted_at=promoted_at,
        blocked_reason=None,
    )


def _no_sr():
    """SimResult-like sentinel — verdict=none."""
    class _NS:
        verdict = "none"
    return _NS()


# ─── Spec 03 §6.1 — GET /health ────────────────────────────────────


@router.get("/health", response_model=HealthStatus)
def health(
    store: RunHandleStore = Depends(get_store),
) -> HealthStatus:
    """spec 03 §6.1 — 시뮬 시스템 상태."""
    pending = store.list(status="pending")
    completed = store.list(status="completed")
    last_run_at: Optional[str] = None
    if completed:
        last_run_at = max(h.created_at for h in completed)

    return HealthStatus(
        status="ok",
        sandbox_available=True,
        jvm_available=False,  # StubJavaSandbox 만 — 실 JVM 미연결
        queue_depth=len(pending),
        last_run_at=last_run_at,
    )


# ─── Spec 03 §6.2 — GET /capabilities ──────────────────────────────


@router.get("/capabilities", response_model=Capabilities)
def capabilities() -> Capabilities:
    """spec 03 §6.2 — 클라이언트 capability negotiation."""
    return Capabilities(
        supported_action_kinds=["pure_function", "workflow", "effectful"],
        supported_scenario_kinds=["regression", "boundary", "drama", "br_violation", "integration"],
        supported_verdicts=["sim_verified", "sim_violation", "inconclusive"],
        runner_version="echo-stub-3c",
        java_sandbox_version="stub",
        max_timeout_sec=30,
        max_atomic_overrides=100,
    )


# datetime import 보강 (위 핸들러들에서 사용)
from datetime import datetime, timezone  # noqa: E402


__all__ = [
    "router",
    "get_store",
    "get_orchestrator",
    "get_run_plan_builder",
    "reset_singletons",
]
