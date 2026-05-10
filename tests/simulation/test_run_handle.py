"""RunHandle state machine + RunHandleStore (spec 03 §1.1 + spec 05 §4.1~4.4).

echo-stub iter 합의:
- in-memory dict store ({run_id → RunHandle}) — async queue 는 3b-6+ 에서
- 5 상태 전환: pending → running → {completed, failed, cancelled}
                pending → cancelled (시작 전 취소 허용)
- submit() 헬퍼: orchestrator 동기 실행 → 상태 자동 전이
- get_sim_result(run_id) — completed 전엔 None

TDD — 본 테스트가 먼저, run_handle.py 에 코드 추가 후 GREEN.
"""

from __future__ import annotations

import pytest


# ─── 헬퍼 ────────────────────────────────────────────────────────────


def _change_spec(action="action.scm.std.match"):
    from backend.shared.contracts.simulation import ChangeSpec

    return ChangeSpec(action_fqn=action, atomic_overrides={}, scenario_fixture={"lookups": {}})


def _create_run_request(action="action.scm.std.match"):
    from backend.shared.contracts.simulation import CreateRunRequest

    return CreateRunRequest(change_spec=_change_spec(action), requested_by="tester")


# ─── 1. RunHandle Pydantic 모델 ────────────────────────────────────


def test_run_handle_model_created_with_minimal_fields():
    """spec 03 §1.1 — RunHandle 의 필수 필드 (run_id / status / created_at)."""
    from backend.shared.contracts.simulation import RunHandle

    rh = RunHandle(run_id="run-1", status="pending", created_at="2026-05-10T12:00:00Z")
    assert rh.run_id == "run-1"
    assert rh.status == "pending"
    assert rh.plan is None  # 기본 None


def test_run_handle_status_literal_enforced():
    """status 는 Literal — 허용된 5 값 외 거부."""
    from pydantic import ValidationError

    from backend.shared.contracts.simulation import RunHandle

    with pytest.raises(ValidationError):
        RunHandle(run_id="run-1", status="invalid_status", created_at="2026-05-10T12:00:00Z")


# ─── 2. RunHandleStore — register / get / list ─────────────────────


def test_register_creates_pending_run_handle():
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    handle = store.register(_create_run_request())
    assert handle.status == "pending"
    assert handle.run_id.startswith("run-")
    assert handle.created_at != ""


def test_register_assigns_unique_run_id():
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    h1 = store.register(_create_run_request())
    h2 = store.register(_create_run_request())
    assert h1.run_id != h2.run_id


def test_get_returns_handle_for_known_run_id():
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    handle = store.register(_create_run_request())
    fetched = store.get(handle.run_id)
    assert fetched is not None
    assert fetched.run_id == handle.run_id


def test_get_returns_none_for_unknown_run_id():
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    assert store.get("run-nonexistent") is None


def test_list_returns_all_registered_runs():
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    h1 = store.register(_create_run_request())
    h2 = store.register(_create_run_request())
    all_runs = store.list()
    ids = {r.run_id for r in all_runs}
    assert {h1.run_id, h2.run_id}.issubset(ids)


def test_list_filters_by_status():
    """list(status='pending') → pending 인 것만."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    h1 = store.register(_create_run_request())
    h2 = store.register(_create_run_request())
    store.transition(h1.run_id, "running")
    pending = store.list(status="pending")
    assert {r.run_id for r in pending} == {h2.run_id}


def test_get_change_spec_returns_original_input():
    """spec 03 §2.2 — GET /runs/{id}/changespec 의 source."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    handle = store.register(_create_run_request("action.scm.demo"))
    cs = store.get_change_spec(handle.run_id)
    assert cs is not None
    assert cs.action_fqn == "action.scm.demo"


# ─── 3. 상태 전환 (state machine) ─────────────────────────────────


def test_transition_pending_to_running_to_completed():
    """spec 05 §4.1 의 정상 흐름: pending → running → completed."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    h = store.register(_create_run_request())
    store.transition(h.run_id, "running")
    assert store.get(h.run_id).status == "running"
    store.transition(h.run_id, "completed")
    assert store.get(h.run_id).status == "completed"


def test_transition_pending_to_cancelled_allowed():
    """spec 05 §4.1 — pending 에서 직접 cancelled 허용 (사용자가 시작 전 취소)."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    h = store.register(_create_run_request())
    store.transition(h.run_id, "cancelled")
    assert store.get(h.run_id).status == "cancelled"


def test_transition_running_to_failed_allowed():
    """sandbox 충돌 / timeout → failed."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    h = store.register(_create_run_request())
    store.transition(h.run_id, "running")
    store.transition(h.run_id, "failed")
    assert store.get(h.run_id).status == "failed"


def test_invalid_transition_completed_to_running_raises():
    """완료된 run 은 다시 running 으로 못 감."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    h = store.register(_create_run_request())
    store.transition(h.run_id, "running")
    store.transition(h.run_id, "completed")
    with pytest.raises(ValueError, match="invalid transition"):
        store.transition(h.run_id, "running")


def test_invalid_transition_completed_to_failed_raises():
    """terminal 상태 (completed/failed/cancelled) 에서 다른 상태로 못 감."""
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    h = store.register(_create_run_request())
    store.transition(h.run_id, "running")
    store.transition(h.run_id, "completed")
    with pytest.raises(ValueError, match="invalid transition"):
        store.transition(h.run_id, "failed")


def test_transition_unknown_run_id_raises():
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    with pytest.raises(KeyError):
        store.transition("run-nonexistent", "running")


# ─── 4. submit — orchestrator 동기 실행 ─────────────────────────


def test_submit_runs_orchestrator_inline_and_completes():
    """submit() 가 orchestrator 동기 실행 → 자동 transitions → completed."""
    from backend.shared.contracts.simulation import RunPlan, SimResult
    from backend.simulation.api.run_handle import RunHandleStore

    captured: dict = {}

    class FakeOrchestrator:
        def run(self, change_spec, run_plan, run_options):
            captured["called"] = True
            captured["action_fqn"] = change_spec.action_fqn
            return SimResult(
                run_id="placeholder",  # store 가 덮어씀
                status="completed",
                verdict="sim_verified",
                started_at="2026-05-10T12:00:00Z",
                completed_at="2026-05-10T12:00:01Z",
                duration_ms=1000,
                change_spec_ref="sha256:test",
            )

    store = RunHandleStore()
    handle = store.submit(
        request=_create_run_request("action.x"),
        orchestrator=FakeOrchestrator(),
        run_plan=RunPlan(),
    )
    assert captured["called"] is True
    assert captured["action_fqn"] == "action.x"
    final = store.get(handle.run_id)
    assert final.status == "completed"


def test_submit_orchestrator_exception_marks_failed():
    """orchestrator 가 raise → status=failed + sim_result 미저장."""
    from backend.shared.contracts.simulation import RunPlan
    from backend.simulation.api.run_handle import RunHandleStore

    class CrashingOrchestrator:
        def run(self, *a, **k):
            raise RuntimeError("orchestrator boom")

    store = RunHandleStore()
    handle = store.submit(
        request=_create_run_request(),
        orchestrator=CrashingOrchestrator(),
        run_plan=RunPlan(),
    )
    assert store.get(handle.run_id).status == "failed"
    assert store.get_sim_result(handle.run_id) is None


def test_submit_stores_sim_result_for_completed_run():
    """submit 완료 후 get_sim_result 로 SimResult 조회 가능."""
    from backend.shared.contracts.simulation import RunPlan, SimResult
    from backend.simulation.api.run_handle import RunHandleStore

    class FakeOrchestrator:
        def run(self, change_spec, run_plan, run_options):
            return SimResult(
                run_id="placeholder",
                status="completed",
                verdict="sim_verified",
                started_at="2026-05-10T12:00:00Z",
                completed_at="2026-05-10T12:00:01Z",
                duration_ms=1000,
                change_spec_ref="sha256:test",
            )

    store = RunHandleStore()
    handle = store.submit(
        request=_create_run_request(),
        orchestrator=FakeOrchestrator(),
        run_plan=RunPlan(),
    )
    sr = store.get_sim_result(handle.run_id)
    assert sr is not None
    assert sr.verdict == "sim_verified"
    # run_id 가 RunHandle 의 run_id 로 덮어써짐 (placeholder 가 아닌)
    assert sr.run_id == handle.run_id


def test_get_sim_result_returns_none_for_pending_run():
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    handle = store.register(_create_run_request())
    assert store.get_sim_result(handle.run_id) is None


def test_get_sim_result_returns_none_for_unknown_run_id():
    from backend.simulation.api.run_handle import RunHandleStore

    store = RunHandleStore()
    assert store.get_sim_result("run-nonexistent") is None
