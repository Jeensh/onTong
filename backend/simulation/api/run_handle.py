"""RunHandle state machine + RunHandleStore (spec 03 §1.1 + spec 05 §4.1~4.4).

echo-stub iter 합의 (3b-5):
- in-memory dict store ({run_id → RunHandle / ChangeSpec / SimResult}) — async queue 는 후속
- submit() 헬퍼: orchestrator 동기 실행 → 상태 자동 전이
- 5 상태 + 2 terminal (completed/failed/cancelled) state machine

상태 전환 (spec 05 §4.1):
    pending ──▶ running ──▶ completed
                  │
                  ├──▶ failed (sandbox 충돌 / timeout)
                  │
                  └──▶ cancelled (사용자 취소)
    pending ──▶ cancelled (시작 전 취소 허용)

후속 step (3b-6+ / 운영):
- spec 05 §4.3 v2: Redis + RQ / Celery (다 process 큐)
- spec 05 §4.3 v3: external sandbox cluster
- 상태 전환은 동일 머신 — 큐만 swap
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional, Protocol

from backend.shared.contracts.simulation import (
    ChangeSpec,
    CreateRunRequest,
    RunHandle,
    RunOptions,
    RunPlan,
    SimResult,
)

logger = logging.getLogger(__name__)


# ─── 상태 전환 매트릭스 (spec 05 §4.1) ───────────────────────────


_VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "cancelled"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),  # terminal
    "failed": set(),     # terminal
    "cancelled": set(),  # terminal
}


# ─── Orchestrator Protocol (duck-typed) ────────────────────────────


class _OrchestratorProtocol(Protocol):
    def run(
        self,
        change_spec: ChangeSpec,
        run_plan: RunPlan,
        run_options: RunOptions,
    ) -> SimResult: ...


# ─── RunHandleStore ──────────────────────────────────────────────


class RunHandleStore:
    """in-memory store + state machine — Section 3 의 spec 03 §1.1 endpoint backend.

    Thread-safe (lock 으로 보호) — 단일 process 의 동시 호출 안전.
    multi-process 는 v2 (Redis) 에서 보강.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handles: dict[str, RunHandle] = {}
        self._change_specs: dict[str, ChangeSpec] = {}
        self._sim_results: dict[str, SimResult] = {}
        self._run_options: dict[str, RunOptions] = {}

    # ─── Public — register / get / list ───────────────────────

    def register(self, request: CreateRunRequest) -> RunHandle:
        """spec 03 §1.1 — POST /runs: pending 상태로 등록."""
        with self._lock:
            run_id = self._make_run_id()
            handle = RunHandle(
                run_id=run_id,
                status="pending",
                created_at=datetime.now(timezone.utc).isoformat(),
                plan=None,
            )
            self._handles[run_id] = handle
            self._change_specs[run_id] = request.change_spec
            self._run_options[run_id] = request.run_options or RunOptions()
            logger.debug("RunHandle %s registered (action=%s)", run_id, request.change_spec.action_fqn)
            return handle

    def get(self, run_id: str) -> Optional[RunHandle]:
        """spec 03 §1.2 — GET /runs/{run_id}."""
        with self._lock:
            return self._handles.get(run_id)

    def list(self, status: Optional[str] = None) -> list[RunHandle]:
        """spec 03 §1.3 — GET /runs?status=...&limit=... (filter 는 status 만 우선)."""
        with self._lock:
            result = list(self._handles.values())
            if status is not None:
                result = [h for h in result if h.status == status]
            return result

    def get_change_spec(self, run_id: str) -> Optional[ChangeSpec]:
        """spec 03 §2.2 — GET /runs/{run_id}/changespec."""
        with self._lock:
            return self._change_specs.get(run_id)

    def get_sim_result(self, run_id: str) -> Optional[SimResult]:
        """spec 03 §2.1 — GET /runs/{run_id}/sim-result.

        Returns: SimResult if status=completed, else None.
        """
        with self._lock:
            return self._sim_results.get(run_id)

    # ─── Public — state transitions ───────────────────────────

    def transition(self, run_id: str, new_status: str) -> RunHandle:
        """state machine — invalid transition 은 ValueError.

        Raises:
            KeyError: run_id 미등록
            ValueError: invalid transition (terminal → 다른 상태 등)
        """
        with self._lock:
            handle = self._handles.get(run_id)
            if handle is None:
                raise KeyError(f"run_id {run_id!r} not registered")

            current = handle.status
            allowed = _VALID_TRANSITIONS.get(current, set())
            if new_status not in allowed:
                raise ValueError(
                    f"invalid transition {current!r} → {new_status!r} for run {run_id!r}. "
                    f"Allowed: {sorted(allowed) or '(terminal)'}"
                )

            updated = handle.model_copy(update={"status": new_status})
            self._handles[run_id] = updated
            logger.debug("RunHandle %s: %s → %s", run_id, current, new_status)
            return updated

    def cancel(self, run_id: str) -> RunHandle:
        """편의 메서드 — pending 또는 running → cancelled."""
        return self.transition(run_id, "cancelled")

    # ─── Public — submit (sync orchestrator 실행) ────────────

    def submit(
        self,
        request: CreateRunRequest,
        orchestrator: _OrchestratorProtocol,
        run_plan: RunPlan,
    ) -> RunHandle:
        """register + sync orchestrator 실행 + 상태 자동 전이.

        흐름:
          1. register → pending
          2. transition pending → running
          3. orchestrator.run(change_spec, run_plan, run_options) 동기 호출
          4. 결과:
             - 정상 + sim_result.status='completed' → store sim_result + transition running → completed
             - 정상 + sim_result.status='failed'    → store sim_result + transition running → failed
             - 예외 raise                          → transition running → failed (sim_result 미저장)

        후속 (운영) — 본 메서드를 async 큐의 worker 에서 호출하면 v2 가 됨.
        """
        handle = self.register(request)
        run_id = handle.run_id
        self.transition(run_id, "running")
        run_options = self._run_options[run_id]

        try:
            sim_result = orchestrator.run(
                change_spec=request.change_spec,
                run_plan=run_plan,
                run_options=run_options,
            )
        except Exception as exc:
            logger.warning("Orchestrator.run() raised for run %s — marking failed: %s", run_id, exc)
            self.transition(run_id, "failed")
            return self.get(run_id)  # fresh handle

        # SimResult.run_id 를 RunHandle 의 run_id 로 정규화 (orchestrator 가 placeholder 썼을 가능성)
        sim_result = sim_result.model_copy(update={"run_id": run_id})
        with self._lock:
            self._sim_results[run_id] = sim_result

        terminal = "completed" if sim_result.status == "completed" else "failed"
        self.transition(run_id, terminal)
        return self.get(run_id)

    # ─── 내부 ─────────────────────────────────────────────────

    @staticmethod
    def _make_run_id() -> str:
        return f"run-{uuid.uuid4().hex[:12]}"


__all__ = ["RunHandleStore"]
