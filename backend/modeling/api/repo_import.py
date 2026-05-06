"""FastAPI router — /api/ontology/repos/* — Java repo import 파이프라인 노출.

3 endpoint:
- POST /api/ontology/repos/import      — job 시작 (background thread), job_id 반환
- GET  /api/ontology/repos/import/{id} — 현재 상태 JSON
- GET  /api/ontology/repos/import/{id}/stream — SSE 진행률

job 상태는 in-memory dict (프로세스 단일 인스턴스 가정).
서버 재시작 시 잃어도 무방 (작업은 cli 로 재실행 가능).
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.modeling.code_layer.importer import ImportJob, RepoImporter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/repos", tags=["ontology-repos"])


# ---------------------------------------------------------------------------
# Job registry — 단순 in-memory
# ---------------------------------------------------------------------------
_jobs: dict[str, ImportJob] = {}
_jobs_lock = threading.Lock()


def _job_to_dict(job: ImportJob) -> dict[str, Any]:
    """ImportJob dataclass → JSON-safe dict (+ derived progress_pct)."""
    d = asdict(job)
    d["progress_pct"] = job.progress_pct
    d["duration_ms"] = job.duration_ms
    return d


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------
class ImportRequest(BaseModel):
    repo_id: str = Field(..., min_length=1, description="저장 키 — 같은 id 면 기존 데이터 교체")
    repo_path: str = Field(..., min_length=1, description="absolute Java repo path")


class ImportStartResponse(BaseModel):
    job_id: str
    repo_id: str
    repo_path: str
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/import", response_model=ImportStartResponse)
def start_import(req: ImportRequest) -> ImportStartResponse:
    repo_path = Path(req.repo_path).expanduser().resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise HTTPException(status_code=400, detail=f"repo_path not found: {repo_path}")

    job_id = uuid.uuid4().hex[:12]
    job = ImportJob(id=job_id, repo_id=req.repo_id, repo_path=str(repo_path))
    with _jobs_lock:
        _jobs[job_id] = job

    def _run() -> None:
        try:
            importer = RepoImporter()
            importer.run(job)  # in-place state mutation; no callback needed for polling
        except Exception as e:
            logger.exception("import job %s crashed", job_id)
            job.status = "error"
            job.errors.append(str(e))
            job.finished_at = time.time()

    threading.Thread(target=_run, name=f"repo-import-{job_id}", daemon=True).start()
    logger.info("repo import job started: id=%s repo_id=%s path=%s", job_id, req.repo_id, repo_path)
    return ImportStartResponse(
        job_id=job_id, repo_id=job.repo_id,
        repo_path=job.repo_path, status=job.status,
    )


@router.get("/import/{job_id}")
def get_import_status(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return _job_to_dict(job)


@router.get("/import/{job_id}/stream")
async def stream_import_progress(job_id: str) -> StreamingResponse:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")

    async def event_stream():
        last_payload = ""
        # poll loop — job state mutates in worker thread
        while True:
            payload = json.dumps(_job_to_dict(job), ensure_ascii=False)
            if payload != last_payload:
                yield f"event: progress\ndata: {payload}\n\n"
                last_payload = payload
            if job.status in ("done", "error"):
                yield f"event: end\ndata: {payload}\n\n"
                return
            await asyncio.sleep(0.4)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/import")
def list_jobs() -> list[dict[str, Any]]:
    """현재 프로세스가 알고 있는 모든 import job (디버깅 용)."""
    with _jobs_lock:
        return [_job_to_dict(j) for j in _jobs.values()]
