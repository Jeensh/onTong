"""Phase 6-C — Async Job Queue API + 자동 회귀 검증.

엔드포인트:
- POST /api/simulation/jobs/run                  단일 step 실행 잡 등록 (즉시 queued)
- POST /api/simulation/jobs/scenario/{id}/run   시나리오 실행 잡 등록
- POST /api/simulation/jobs/batch                여러 시나리오 일괄 실행
- GET  /api/simulation/jobs                      잡 목록
- GET  /api/simulation/jobs/{id}                 잡 단건
- POST /api/simulation/jobs/{id}/cancel          큐 대기 중인 잡 취소
- GET  /api/simulation/jobs/{id}/stream          SSE 진행 이벤트
- GET  /api/simulation/jobs/batch/{id}           배치 진행 상태
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..jobs.queue import AsyncJobQueue, JobEvent, get_batch, submit_batch
from ..storage import scenarios as scn_store

router = APIRouter(prefix="/api/simulation/jobs", tags=["simulation-jobs"])


# ─── Submit ──────────────────────────────────────────────────────────


class JobSubmit(BaseModel):
    step_id: str
    inputs: dict = Field(default_factory=dict)
    scenario_id: Optional[str] = None
    parent_run_id: Optional[str] = None


@router.post("/run")
async def submit_job(payload: JobSubmit):
    queue = AsyncJobQueue.instance()
    try:
        job = queue.submit(
            step_id=payload.step_id,
            inputs=payload.inputs,
            scenario_id=payload.scenario_id,
            parent_run_id=payload.parent_run_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return job.to_dict()


@router.post("/scenario/{scenario_id}/run")
async def submit_scenario_job(scenario_id: str, parent_run_id: Optional[str] = None):
    scn = scn_store.get_scenario(scenario_id)
    if scn is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    queue = AsyncJobQueue.instance()
    job = queue.submit(
        step_id=scn.step_id, inputs=scn.inputs,
        scenario_id=scenario_id, parent_run_id=parent_run_id,
    )
    return job.to_dict()


class BatchSubmit(BaseModel):
    scenario_ids: list[str]


@router.post("/batch")
async def submit_batch_jobs(payload: BatchSubmit):
    queue = AsyncJobQueue.instance()
    batch = submit_batch(queue, payload.scenario_ids)
    return batch.status(queue)


# ─── Inspect ────────────────────────────────────────────────────────


@router.get("")
def list_jobs(limit: int = 50):
    queue = AsyncJobQueue.instance()
    items = queue.list(limit=limit)
    return {"items": [j.to_dict() for j in items], "count": len(items)}


@router.get("/{job_id}")
def get_job(job_id: str):
    queue = AsyncJobQueue.instance()
    j = queue.get(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail="job not found")
    return j.to_dict()


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str):
    queue = AsyncJobQueue.instance()
    ok = queue.cancel(job_id)
    if not ok:
        raise HTTPException(status_code=409, detail="cannot cancel (not queued or already running)")
    return {"cancelled": True}


@router.get("/{job_id}/stream")
async def stream_job(job_id: str):
    queue = AsyncJobQueue.instance()
    if queue.get(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")

    async def gen():
        async for ev in queue.stream(job_id):
            yield f"data: {json.dumps(ev.to_dict(), ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/batch/{batch_id}")
def get_batch_status(batch_id: str):
    batch = get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    queue = AsyncJobQueue.instance()
    return batch.status(queue)
