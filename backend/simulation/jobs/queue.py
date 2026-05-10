"""Phase 6-C — Async Job Queue + 자동 회귀 검증.

Wiki Section 의 ImageProcessingQueue 패턴 미러:
- asyncio.create_task fire-and-forget 으로 즉시 enqueued, 백그라운드 실행
- Semaphore(N) 로 동시 실행수 제한 (cold start 보호)
- JobStatus 상태머신: queued → running → done | failed | cancelled
- 결과 dict 보관 + 진행 이벤트 asyncio.Queue 로 SSE pipe

자동 회귀 검증:
- run 시 scenario_id 가 baseline 을 가지면 자동으로 candidate vs baseline diff 수행
- diff 결과를 job result.regression 에 첨부
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ..sandbox import registry
from ..storage import runs as runs_store
from ..storage import scenarios as scn_store

_DEFAULT_CONCURRENCY = 4


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobEvent:
    """Job 진행 이벤트 (SSE 송신용)."""

    type: str  # 'queued' | 'started' | 'progress' | 'done' | 'failed' | 'cancelled'
    job_id: str
    at: str
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type, "job_id": self.job_id, "at": self.at, **self.payload}


@dataclass
class Job:
    id: str
    step_id: str
    inputs: dict
    scenario_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    status: JobStatus = JobStatus.QUEUED
    submitted_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_ms: Optional[int] = None
    run_id: Optional[str] = None
    outputs: Optional[dict] = None
    error: Optional[str] = None
    regression: Optional[dict] = None
    """baseline 이 있으면 자동 회귀 결과 (diff_count + field_diffs 요약)."""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "step_id": self.step_id,
            "scenario_id": self.scenario_id,
            "parent_run_id": self.parent_run_id,
            "status": self.status.value,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_ms": self.elapsed_ms,
            "run_id": self.run_id,
            "outputs": self.outputs,
            "error": self.error,
            "regression": self.regression,
            "inputs": self.inputs,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AsyncJobQueue:
    """Section 3 의 비동기 잡 큐.

    사용 예:
        queue = AsyncJobQueue.instance()
        job = queue.submit(step_id="pipeline_full", inputs={...}, scenario_id="scn-...")
        # job 은 즉시 QUEUED, 백그라운드에서 실행됨
        async for ev in queue.stream(job.id):
            ...
    """

    _instance: Optional["AsyncJobQueue"] = None

    def __init__(self, concurrency: int = _DEFAULT_CONCURRENCY,
                 db_path: Optional[Any] = None):
        self._sem = asyncio.Semaphore(concurrency)
        self._jobs: dict[str, Job] = {}
        self._streams: dict[str, list[asyncio.Queue]] = {}
        self._db_path = db_path

    @classmethod
    def instance(cls) -> "AsyncJobQueue":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_test(cls, *, concurrency: int = _DEFAULT_CONCURRENCY,
                       db_path: Optional[Any] = None) -> "AsyncJobQueue":
        cls._instance = cls(concurrency=concurrency, db_path=db_path)
        return cls._instance

    def submit(
        self,
        *,
        step_id: str,
        inputs: dict,
        scenario_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
    ) -> Job:
        if step_id not in registry.STEP_REGISTRY:
            raise ValueError(f"unknown step_id: {step_id}")
        job = Job(
            id=f"job-{uuid.uuid4().hex[:12]}",
            step_id=step_id,
            inputs=inputs,
            scenario_id=scenario_id,
            parent_run_id=parent_run_id,
            submitted_at=_now_iso(),
        )
        self._jobs[job.id] = job
        self._emit(job.id, JobEvent(type="queued", job_id=job.id, at=_now_iso()))
        # fire-and-forget — task 자체에 대한 reference 보관 안 함 (gc 방지 위해 set 추가)
        asyncio.create_task(self._run(job))
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list(self, *, limit: int = 50) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.submitted_at, reverse=True)[:limit]

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.status != JobStatus.QUEUED:
            return False
        job.status = JobStatus.CANCELLED
        job.completed_at = _now_iso()
        self._emit(job_id, JobEvent(type="cancelled", job_id=job_id, at=job.completed_at))
        return True

    async def stream(self, job_id: str):
        """SSE/async iter — 해당 job 의 이벤트 (이미 발생한 + 후속). 종료 이벤트 후 자동 close."""
        q: asyncio.Queue[Optional[JobEvent]] = asyncio.Queue()
        self._streams.setdefault(job_id, []).append(q)
        # snapshot — 이미 종료된 job 이라면 단발성 done 이벤트
        job = self._jobs.get(job_id)
        if job and job.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED):
            yield JobEvent(
                type=job.status.value, job_id=job_id, at=job.completed_at or _now_iso(),
                payload={"summary": job.to_dict()},
            )
            return
        try:
            while True:
                ev = await q.get()
                if ev is None:
                    break
                yield ev
                if ev.type in ("done", "failed", "cancelled"):
                    break
        finally:
            self._streams.get(job_id, []).remove(q)

    # ── internal ────────────────────────────────────────────────────

    def _emit(self, job_id: str, event: JobEvent) -> None:
        for q in list(self._streams.get(job_id, [])):
            q.put_nowait(event)

    async def _run(self, job: Job) -> None:
        async with self._sem:
            if job.status == JobStatus.CANCELLED:
                return
            job.status = JobStatus.RUNNING
            job.started_at = _now_iso()
            self._emit(job.id, JobEvent(type="started", job_id=job.id, at=job.started_at))
            t0 = time.time()
            try:
                outputs = await asyncio.to_thread(
                    registry.run_step, job.step_id, job.inputs,
                )
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = repr(e)
                job.completed_at = _now_iso()
                job.elapsed_ms = int((time.time() - t0) * 1000)
                self._emit(job.id, JobEvent(
                    type="failed", job_id=job.id, at=job.completed_at,
                    payload={"error": job.error},
                ))
                return

            job.outputs = outputs
            job.elapsed_ms = int((time.time() - t0) * 1000)

            # 영구 저장
            try:
                run = runs_store.log_run(
                    step_id=job.step_id, inputs=job.inputs, outputs=outputs,
                    scenario_id=job.scenario_id, elapsed_ms=job.elapsed_ms,
                    parent_run_id=job.parent_run_id, db_path=self._db_path,
                )
                job.run_id = run.id
            except Exception as e:
                # 저장 실패는 job 자체는 done 으로 처리, error 만 마킹
                job.error = f"persist_failed: {e!r}"

            # 자동 회귀 검증
            if job.scenario_id and job.run_id:
                try:
                    baseline = runs_store.get_baseline(job.scenario_id, db_path=self._db_path)
                    if baseline and baseline.id != job.run_id:
                        diff = runs_store.regression_diff(
                            baseline.id, job.run_id, db_path=self._db_path,
                        )
                        job.regression = {
                            "baseline_run_id": baseline.id,
                            "diff_count": diff["summary"]["diff_count"],
                            "stage_changed": diff["summary"]["stage_changed"],
                            "error_code_changed": diff["summary"]["error_code_changed"],
                            "field_diffs": diff["summary"]["field_diffs"][:20],
                        }
                except Exception as e:
                    job.regression = {"error": f"regression_failed: {e!r}"}

            job.status = JobStatus.DONE
            job.completed_at = _now_iso()
            self._emit(job.id, JobEvent(
                type="done", job_id=job.id, at=job.completed_at,
                payload={"summary": job.to_dict()},
            ))


# ─── Batch helper ───────────────────────────────────────────────────


@dataclass
class BatchInfo:
    id: str
    job_ids: list[str]
    submitted_at: str

    def status(self, queue: AsyncJobQueue) -> dict:
        jobs = [queue.get(jid) for jid in self.job_ids]
        counts: dict[str, int] = {}
        for j in jobs:
            if j is None:
                continue
            counts[j.status.value] = counts.get(j.status.value, 0) + 1
        return {
            "id": self.id,
            "job_ids": self.job_ids,
            "submitted_at": self.submitted_at,
            "counts": counts,
            "total": len(self.job_ids),
            "completed": counts.get("done", 0) + counts.get("failed", 0) + counts.get("cancelled", 0),
            "regressions_with_diff": sum(
                1 for j in jobs if j and j.regression and j.regression.get("diff_count", 0) > 0
            ),
        }


_batches: dict[str, BatchInfo] = {}


def submit_batch(
    queue: AsyncJobQueue, scenario_ids: list[str], *,
    db_path: Optional[Any] = None,
) -> BatchInfo:
    """여러 시나리오를 한 번에 submit. 정합성 회귀 일괄 검증 등."""
    batch = BatchInfo(
        id=f"batch-{uuid.uuid4().hex[:12]}",
        job_ids=[],
        submitted_at=_now_iso(),
    )
    for sid in scenario_ids:
        scn = scn_store.get_scenario(sid, db_path=db_path)
        if scn is None:
            continue
        job = queue.submit(step_id=scn.step_id, inputs=scn.inputs, scenario_id=sid)
        batch.job_ids.append(job.id)
    _batches[batch.id] = batch
    return batch


def get_batch(batch_id: str) -> Optional[BatchInfo]:
    return _batches.get(batch_id)
