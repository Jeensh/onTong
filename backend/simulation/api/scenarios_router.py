"""Phase 6-B — 시나리오 / 실행 이력 / 회귀 검증 API.

엔드포인트:
- GET    /api/simulation/scenarios                   목록 (?step_id&tag)
- GET    /api/simulation/scenarios/{id}              단건
- POST   /api/simulation/scenarios                   생성
- PUT    /api/simulation/scenarios/{id}              수정
- DELETE /api/simulation/scenarios/{id}              삭제
- POST   /api/simulation/scenarios/seed              YAML 시드 로드
- POST   /api/simulation/scenarios/{id}/run          시나리오 1회 실행 + run 기록
- POST   /api/simulation/scenarios/{id}/baseline     run 을 baseline 등록 (?run_id)

- GET    /api/simulation/runs                        실행 이력 (?scenario_id&step_id&limit&only_baseline)
- GET    /api/simulation/runs/{id}                   단건
- GET    /api/simulation/runs/{id}/lineage           양방향 lineage
- POST   /api/simulation/runs/regression             baseline vs candidate diff
"""

from __future__ import annotations

import time
from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ..sandbox import registry
from ..storage import runs as runs_store
from ..storage import scenarios as scn_store

router = APIRouter(prefix="/api/simulation", tags=["simulation-storage"])


# ─── Scenario CRUD ──────────────────────────────────────────────────


class ScenarioCreate(BaseModel):
    name: str
    step_id: str
    inputs: dict = Field(default_factory=dict)
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    id: Optional[str] = None  # auto-gen if missing


@router.get("/scenarios")
def list_scenarios(
    step_id: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
):
    items = scn_store.list_scenarios(step_id=step_id, tag=tag)
    return {"items": [s.to_dict() for s in items], "count": len(items)}


@router.get("/scenarios/export", response_class=PlainTextResponse)
def export_scenarios_yaml(
    step_id: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
):
    """등록된 시나리오를 YAML 형식으로 export. 충돌 회피 위해 /scenarios/{id} 보다 먼저 등록."""
    items = scn_store.list_scenarios(step_id=step_id, tag=tag)
    payload = [
        {
            "id": s.id, "name": s.name, "description": s.description,
            "step_id": s.step_id, "tags": list(s.tags), "inputs": s.inputs,
        }
        for s in items
    ]
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    s = scn_store.get_scenario(scenario_id)
    if s is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    return s.to_dict()


@router.post("/scenarios")
def create_scenario(payload: ScenarioCreate):
    if payload.step_id not in registry.STEP_REGISTRY:
        raise HTTPException(status_code=400, detail=f"unknown step_id: {payload.step_id}")
    scn = scn_store.Scenario(
        id=payload.id or "",
        name=payload.name,
        step_id=payload.step_id,
        inputs=payload.inputs,
        description=payload.description,
        tags=payload.tags,
        source="user",
    )
    saved = scn_store.upsert_scenario(scn)
    return saved.to_dict()


@router.put("/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, payload: ScenarioCreate):
    existing = scn_store.get_scenario(scenario_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    if payload.step_id not in registry.STEP_REGISTRY:
        raise HTTPException(status_code=400, detail=f"unknown step_id: {payload.step_id}")
    existing.name = payload.name
    existing.step_id = payload.step_id
    existing.inputs = payload.inputs
    existing.description = payload.description
    existing.tags = payload.tags
    saved = scn_store.upsert_scenario(existing)
    return saved.to_dict()


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str):
    ok = scn_store.delete_scenario(scenario_id)
    if not ok:
        raise HTTPException(status_code=404, detail="scenario not found")
    return {"deleted": True}


@router.post("/scenarios/seed")
def seed_scenarios():
    n = scn_store.load_yaml_seeds()
    return {"loaded": n}


# ─── Phase 7-C: Import (export 는 위에 등록 — path 충돌 회피) ──────


class ImportPayload(BaseModel):
    yaml_text: str = Field(..., min_length=2)
    overwrite: bool = Field(False, description="동일 id 가 있으면 덮어쓰기")


@router.post("/scenarios/import")
def import_scenarios(payload: ImportPayload):
    """YAML 텍스트를 파싱하여 시나리오 일괄 등록 (export 와 호환).

    each item: {id?, name, step_id, inputs, description?, tags?}
    """
    try:
        data = yaml.safe_load(payload.yaml_text)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"YAML parse error: {e}")
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="YAML root must be a list")

    imported, skipped = 0, 0
    for item in data:
        if not isinstance(item, dict) or "name" not in item or "step_id" not in item:
            skipped += 1
            continue
        if item["step_id"] not in registry.STEP_REGISTRY:
            skipped += 1
            continue
        scn_id = item.get("id") or ""
        if scn_id and not payload.overwrite:
            existing = scn_store.get_scenario(scn_id)
            if existing is not None:
                skipped += 1
                continue
        scn = scn_store.Scenario(
            id=scn_id,
            name=item["name"],
            description=item.get("description"),
            step_id=item["step_id"],
            inputs=item.get("inputs") or {},
            tags=item.get("tags") or [],
            source="user",
        )
        scn_store.upsert_scenario(scn)
        imported += 1
    return {"imported": imported, "skipped": skipped}


# ─── Phase 7-B: AI assist → 시나리오 저장 ────────────────────────────


class AssistSavePayload(BaseModel):
    """AI 어시스턴트가 만든 ScenarioDraft 를 라이브러리에 저장하는 요청."""

    name: str
    description: Optional[str] = None
    step_id: str
    inputs: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


@router.post("/scenarios/from-assist")
def save_assist_scenario(payload: AssistSavePayload):
    if payload.step_id not in registry.STEP_REGISTRY:
        raise HTTPException(status_code=400, detail=f"unknown step_id: {payload.step_id}")
    scn = scn_store.Scenario(
        id="",
        name=payload.name,
        description=payload.description,
        step_id=payload.step_id,
        inputs=payload.inputs,
        tags=payload.tags,
        source="auto",  # AI 생성 표시
    )
    saved = scn_store.upsert_scenario(scn)
    return saved.to_dict()


# ─── Scenario run ───────────────────────────────────────────────────


class ScenarioRunOptions(BaseModel):
    parent_run_id: Optional[str] = None
    """변경 후 회귀 실행 시 직전 run id. supersedes lineage 자동 추가."""


@router.post("/scenarios/{scenario_id}/run")
def run_scenario(scenario_id: str, options: ScenarioRunOptions = ScenarioRunOptions()):
    scn = scn_store.get_scenario(scenario_id)
    if scn is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    started = time.time()
    try:
        outputs = registry.run_step(scn.step_id, scn.inputs)
    except Exception as e:
        outputs = {"error": {"error_code": "EXEC_ERROR", "message": str(e)}}
    elapsed_ms = int((time.time() - started) * 1000)
    run = runs_store.log_run(
        step_id=scn.step_id,
        inputs=scn.inputs,
        outputs=outputs,
        scenario_id=scenario_id,
        elapsed_ms=elapsed_ms,
        parent_run_id=options.parent_run_id,
    )
    return run.to_dict()


@router.post("/scenarios/{scenario_id}/baseline")
def register_baseline(scenario_id: str, run_id: str = Query(...)):
    scn = scn_store.get_scenario(scenario_id)
    if scn is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    ok = runs_store.register_baseline(run_id, scenario_id=scenario_id)
    if not ok:
        raise HTTPException(status_code=404, detail="run not found")
    return {"baseline_run_id": run_id, "scenario_id": scenario_id}


# ─── Runs ────────────────────────────────────────────────────────────


@router.get("/runs")
def list_runs(
    scenario_id: Optional[str] = Query(None),
    step_id: Optional[str] = Query(None),
    only_baseline: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
):
    items = runs_store.list_runs(
        scenario_id=scenario_id, step_id=step_id,
        only_baseline=only_baseline, limit=limit,
    )
    return {"items": [r.to_dict() for r in items], "count": len(items)}


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    r = runs_store.get_run(run_id)
    if r is None:
        raise HTTPException(status_code=404, detail="run not found")
    return r.to_dict()


@router.get("/runs/{run_id}/lineage")
def get_lineage(run_id: str):
    return runs_store.get_lineage(run_id)


class RegressionRequest(BaseModel):
    baseline_run_id: str
    candidate_run_id: str


@router.post("/runs/regression")
def regression_diff(payload: RegressionRequest):
    return runs_store.regression_diff(payload.baseline_run_id, payload.candidate_run_id)
