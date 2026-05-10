"""asyncio queue / submit_background — STEP 3d-E2.

submit_background():
- register → pending → 즉시 RunHandle 반환
- background thread 에서 orchestrator 실행 → running → completed/failed
- store 의 thread-safe RLock 보장

spec 05 §4.3 v1 — daemon thread (asyncio worker 단순화).
"""

from __future__ import annotations

import time

import pytest

from backend.shared.contracts.simulation import (
    ChangeSpec,
    CreateRunRequest,
    DispatchResult,
    RunOptions,
    RunPlan,
    SimResult,
)


def _stub_lookup():
    class _SL:
        def get(self, *a, **k): return None
        def list(self, *a, **k): return []
        def validate(self): return []
    return _SL()


def _python_gen():
    from backend.simulation.runner.python_generator import PythonGenerator
    return PythonGenerator()


class _SlowOrchestrator:
    """orchestrator.run() 이 sleep 후 SimResult 반환 — async 검증용."""

    def __init__(self, delay_sec: float = 0.1, verdict: str = "sim_verified"):
        self.delay = delay_sec
        self.verdict = verdict
        self.last_generated_script = None

    def run(self, change_spec, run_plan, run_options):
        time.sleep(self.delay)
        from backend.shared.contracts.simulation import GeneratedScript

        self.last_generated_script = GeneratedScript(
            source_code="def run(*a, **k): pass\n",
            entrypoint="run",
        )
        return SimResult(
            run_id="placeholder",
            status="completed",
            verdict=self.verdict,
            started_at="2026-05-10T00:00:00Z",
            completed_at="2026-05-10T00:00:01Z",
            duration_ms=int(self.delay * 1000),
            change_spec_ref="sha256:test",
        )


# ─── 1. submit_background 즉시 RunHandle 반환 (status=pending or running) ───


def test_submit_background_returns_handle_immediately():
    """orchestrator.run() 이 0.5초 걸려도 submit_background 는 즉시 반환."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    orch = _SlowOrchestrator(delay_sec=0.5)
    plan = RunPlan(delegates_to_tree=[{"action_fqn": "a", "depth": 0}])
    cs = ChangeSpec(action_fqn="a", atomic_overrides={}, scenario_fixture={"lookups": {}})

    t0 = time.monotonic()
    handle = store.submit_background(CreateRunRequest(change_spec=cs), orch, plan)
    elapsed = time.monotonic() - t0

    # submit_background 가 0.5초 sleep 보다 훨씬 빨리 반환 (< 0.1초)
    assert elapsed < 0.2
    # status 는 pending 또는 running (background thread 가 막 시작)
    assert handle.status in ("pending", "running")


# ─── 2. background 완료 후 status=completed + sim_result 저장 ─────


def test_submit_background_eventually_completes():
    """polling 으로 background 완료 확인."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    orch = _SlowOrchestrator(delay_sec=0.05, verdict="sim_verified")
    plan = RunPlan(delegates_to_tree=[{"action_fqn": "a", "depth": 0}])
    cs = ChangeSpec(action_fqn="a", atomic_overrides={}, scenario_fixture={"lookups": {}})

    handle = store.submit_background(CreateRunRequest(change_spec=cs), orch, plan)

    # polling — background thread 완료 대기 (max 2초)
    deadline = time.monotonic() + 2.0
    final = None
    while time.monotonic() < deadline:
        cur = store.get(handle.run_id)
        if cur and cur.status in ("completed", "failed", "cancelled"):
            final = cur
            break
        time.sleep(0.01)

    assert final is not None, "background thread 가 2초 안에 완료 안 됨"
    assert final.status == "completed"

    sr = store.get_sim_result(handle.run_id)
    assert sr is not None
    assert sr.verdict == "sim_verified"


# ─── 3. background orchestrator 예외 → status=failed ───────────────


def test_submit_background_orchestrator_exception_marks_failed():
    """background 에서 orchestrator raise → status=failed."""
    from backend.simulation.api.run_handle import RunHandleStore

    class _CrashingOrchestrator:
        last_generated_script = None

        def run(self, *a, **k):
            time.sleep(0.05)
            raise RuntimeError("crash from background")

    store = RunHandleStore()
    plan = RunPlan(delegates_to_tree=[{"action_fqn": "a", "depth": 0}])
    cs = ChangeSpec(action_fqn="a", atomic_overrides={}, scenario_fixture={"lookups": {}})

    handle = store.submit_background(CreateRunRequest(change_spec=cs), _CrashingOrchestrator(), plan)

    # polling
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        cur = store.get(handle.run_id)
        if cur and cur.status in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.01)

    final = store.get(handle.run_id)
    assert final.status == "failed"
    # sim_result 미저장
    assert store.get_sim_result(handle.run_id) is None


# ─── 4. 다중 background submission concurrent ─────────────────────


def test_multiple_concurrent_background_submissions():
    """3개 동시 submit_background → 모두 다른 run_id + 모두 완료."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    orch = _SlowOrchestrator(delay_sec=0.05)
    plan = RunPlan(delegates_to_tree=[{"action_fqn": "a", "depth": 0}])
    cs = ChangeSpec(action_fqn="a", atomic_overrides={}, scenario_fixture={"lookups": {}})

    handles = [
        store.submit_background(CreateRunRequest(change_spec=cs), orch, plan)
        for _ in range(3)
    ]

    ids = {h.run_id for h in handles}
    assert len(ids) == 3  # 고유 run_id

    # 모두 완료 대기
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        statuses = [store.get(h.run_id).status for h in handles]
        if all(s in ("completed", "failed", "cancelled") for s in statuses):
            break
        time.sleep(0.01)

    # 모두 completed 여야 함
    for h in handles:
        assert store.get(h.run_id).status == "completed"


# ─── 5. submit (sync) 와 동일한 sim_result 형식 ────────────────────


def test_submit_background_sim_result_run_id_normalized():
    """SimResult.run_id 가 RunHandle.run_id 로 정규화 (placeholder 덮어씀)."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    orch = _SlowOrchestrator(delay_sec=0.01)
    plan = RunPlan(delegates_to_tree=[{"action_fqn": "a", "depth": 0}])
    cs = ChangeSpec(action_fqn="a", atomic_overrides={}, scenario_fixture={"lookups": {}})

    handle = store.submit_background(CreateRunRequest(change_spec=cs), orch, plan)

    # polling
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if store.get(handle.run_id).status == "completed":
            break
        time.sleep(0.01)

    sr = store.get_sim_result(handle.run_id)
    # placeholder 덮어써짐
    assert sr.run_id == handle.run_id
    assert sr.run_id != "placeholder"
