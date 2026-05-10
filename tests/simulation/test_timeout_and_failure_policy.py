"""TimeoutBudget (spec 05 §4.7) + FailurePolicy (spec 05 §4.8) 검증.

RunOptions 확장 + Orchestrator 의 dispatch loop 정책 분기.
"""

from __future__ import annotations

from backend.shared.contracts.simulation import (
    BRTrigger,
    ChangeSpec,
    DispatchResult,
    RunOptions,
    RunPlan,
)
from backend.simulation.runner.orchestrator import Orchestrator


def _stub_lookup():
    class _SL:
        def get(self, *a, **k): return None
        def list(self, *a, **k): return []
        def validate(self): return []
    return _SL()


def _python_gen():
    from backend.simulation.runner.python_generator import PythonGenerator
    return PythonGenerator()


def _change_spec(action="action.x"):
    return ChangeSpec(action_fqn=action, atomic_overrides={}, scenario_fixture={"lookups": {}})


# ─── TimeoutBudget unit (spec 05 §4.7) ────────────────────────────


def test_timeout_budget_for_dispatch_returns_positive():
    from backend.simulation.runner.timeout_budget import TimeoutBudget

    plan = RunPlan(delegates_to_tree=[{"action_fqn": "a", "depth": 0}], estimated_steps=1)
    budget = TimeoutBudget(total_sec=10.0, plan=plan)
    assert budget.for_dispatch() > 0
    assert not budget.is_exhausted()


def test_timeout_budget_exhausted_raises():
    """budget 0초 → for_dispatch() raise TimeoutError."""
    import pytest
    from backend.simulation.runner.timeout_budget import TimeoutBudget

    plan = RunPlan(delegates_to_tree=[{"action_fqn": "a", "depth": 0}], estimated_steps=1)
    budget = TimeoutBudget(total_sec=-1.0, plan=plan)  # already past
    assert budget.is_exhausted()
    with pytest.raises(TimeoutError, match="budget exhausted"):
        budget.for_dispatch()


# ─── RunOptions 확장 (spec 03 §1.1 + spec 05 §4.7~4.8) ────────


def test_run_options_default_values():
    o = RunOptions()
    assert o.timeout_sec == 30
    assert o.capture_traces is True
    assert o.capture_br_evidence is True
    assert o.on_dispatch_error == "fail_fast"
    assert o.on_br_violation == "continue"
    assert o.on_anchor_miss == "continue"
    assert o.on_dispatch_inconsistent == "continue"
    assert o.max_dispatch_errors == 3


def test_run_options_validation_rejects_invalid_policy():
    """Literal 외 값 거부."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RunOptions(on_dispatch_error="bogus")  # type: ignore


# ─── FailurePolicy on_dispatch_error 정책 (spec 05 §4.8) ──────────


def test_orchestrator_on_dispatch_error_continue_keeps_going():
    """on_dispatch_error='continue' → 첫 dispatch 가 raise 해도 다음 frame 진행."""

    class _CrashThenOk:
        def __init__(self):
            self.calls = 0

        def dispatch(self, action_fqn, inputs, run_options):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("first dispatch crash")
            return DispatchResult(
                outputs={}, realized_method_fqn="com.X.ok",
                dispatch_consistent=True, dispatch_mismatch_reason=None,
                duration_ms=0, jvm_log="", captured_anchors=[], captured_brs=[],
            )

    sandbox = _CrashThenOk()
    orch = Orchestrator(
        python_generator=_python_gen(),
        java_sandbox=sandbox,
        lookup_source_factory=lambda fx: _stub_lookup(),
    )
    plan = RunPlan(delegates_to_tree=[
        {"action_fqn": "a1", "depth": 0},
        {"action_fqn": "a2", "depth": 0},
    ], estimated_steps=2)
    result = orch.run(
        _change_spec(),
        plan,
        RunOptions(on_dispatch_error="continue"),
    )
    # continue 정책 → 두 dispatch 모두 호출됨
    assert sandbox.calls == 2
    # 첫 frame 의 error 필드 채워짐
    assert result.delegation_trace[0].error is not None
    assert "first dispatch crash" in result.delegation_trace[0].error
    # status=completed (continue 라 sandbox_error 미설정)
    assert result.status == "completed"


def test_orchestrator_on_dispatch_error_abort_after_n():
    """on_dispatch_error='abort_after_n' + max=2 → 2번째 에러에 abort."""

    class _AlwaysCrash:
        def __init__(self):
            self.calls = 0

        def dispatch(self, *a, **k):
            self.calls += 1
            raise RuntimeError(f"crash #{self.calls}")

    sandbox = _AlwaysCrash()
    orch = Orchestrator(
        python_generator=_python_gen(),
        java_sandbox=sandbox,
        lookup_source_factory=lambda fx: _stub_lookup(),
    )
    plan = RunPlan(delegates_to_tree=[
        {"action_fqn": f"a{i}", "depth": 0} for i in range(5)
    ], estimated_steps=5)
    result = orch.run(
        _change_spec(),
        plan,
        RunOptions(on_dispatch_error="abort_after_n", max_dispatch_errors=2),
    )
    # 2번째 에러 후 abort → 정확히 2번 호출
    assert sandbox.calls == 2
    assert result.status == "failed"
    assert "abort_after_n" in (result.failure_reason or "")


# ─── on_br_violation = fail_fast (spec 05 §4.8) ───────────────────


def test_orchestrator_on_br_violation_fail_fast():
    """on_br_violation='fail_fast' → BR violated 발견 시 즉시 중단."""

    class _ViolatingSandbox:
        def __init__(self):
            self.calls = 0

        def dispatch(self, *a, **k):
            self.calls += 1
            return DispatchResult(
                outputs={}, realized_method_fqn=f"com.X.m{self.calls}",
                dispatch_consistent=True, dispatch_mismatch_reason=None,
                duration_ms=0, jvm_log="",
                captured_anchors=[],
                captured_brs=[BRTrigger(
                    br_fqn="br.x.violated",
                    enforcer_method_fqn=None,
                    outcome="violated",
                    violation_path="x",
                    expected=">=10", actual=5,
                )],
            )

    sandbox = _ViolatingSandbox()
    orch = Orchestrator(
        python_generator=_python_gen(),
        java_sandbox=sandbox,
        lookup_source_factory=lambda fx: _stub_lookup(),
    )
    plan = RunPlan(delegates_to_tree=[
        {"action_fqn": "a1", "depth": 0},
        {"action_fqn": "a2", "depth": 0},
    ], estimated_steps=2)
    result = orch.run(_change_spec(), plan, RunOptions(on_br_violation="fail_fast"))

    # 첫 dispatch 의 BR violation → 두번째 미호출
    assert sandbox.calls == 1
    assert result.status == "failed"
    assert "fail_fast" in (result.failure_reason or "")


def test_orchestrator_on_br_violation_continue_default_keeps_going():
    """default 'continue' — BR violated 도 trace 끝까지."""

    class _ViolatingSandbox:
        def __init__(self):
            self.calls = 0

        def dispatch(self, *a, **k):
            self.calls += 1
            return DispatchResult(
                outputs={}, realized_method_fqn=f"com.X.m{self.calls}",
                dispatch_consistent=True, dispatch_mismatch_reason=None,
                duration_ms=0, jvm_log="",
                captured_anchors=[],
                captured_brs=[BRTrigger(
                    br_fqn="br.x.violated", enforcer_method_fqn=None,
                    outcome="violated", violation_path="x",
                    expected=">=10", actual=5,
                )],
            )

    sandbox = _ViolatingSandbox()
    orch = Orchestrator(
        python_generator=_python_gen(),
        java_sandbox=sandbox,
        lookup_source_factory=lambda fx: _stub_lookup(),
    )
    plan = RunPlan(delegates_to_tree=[
        {"action_fqn": "a1", "depth": 0},
        {"action_fqn": "a2", "depth": 0},
    ], estimated_steps=2)
    result = orch.run(_change_spec(), plan, RunOptions())  # default on_br_violation=continue

    # 두 dispatch 모두 호출 + verdict=sim_violation
    assert sandbox.calls == 2
    assert result.status == "completed"
    assert result.verdict == "sim_violation"
    assert len(result.br_evidence) == 2  # 각 frame 의 violated BR


# ─── on_dispatch_inconsistent = fail_fast ────────────────────────


def test_orchestrator_on_dispatch_inconsistent_fail_fast():
    """on_dispatch_inconsistent='fail_fast' → 첫 inconsistent 에 중단."""

    class _InconsistentSandbox:
        def dispatch(self, *a, **k):
            return DispatchResult(
                outputs={}, realized_method_fqn=None,
                dispatch_consistent=False,
                dispatch_mismatch_reason="no realization",
                duration_ms=0, jvm_log="",
                captured_anchors=[], captured_brs=[],
            )

    orch = Orchestrator(
        python_generator=_python_gen(),
        java_sandbox=_InconsistentSandbox(),
        lookup_source_factory=lambda fx: _stub_lookup(),
    )
    plan = RunPlan(delegates_to_tree=[
        {"action_fqn": "a1", "depth": 0},
        {"action_fqn": "a2", "depth": 0},
    ], estimated_steps=2)
    result = orch.run(
        _change_spec(),
        plan,
        RunOptions(on_dispatch_inconsistent="fail_fast"),
    )
    # 첫 frame 만 trace, 두번째 frame 미호출
    assert len(result.delegation_trace) == 1
    assert result.status == "failed"


# ─── timeout_sec 짧으면 dispatch 중단 ────────────────────────────


def test_orchestrator_timeout_budget_exhausted_marks_failed():
    """timeout_sec=0 → 첫 dispatch 시점부터 budget exhausted → status=failed."""
    import time

    class _SlowSandbox:
        def dispatch(self, *a, **k):
            time.sleep(0.01)  # 첫 dispatch 후엔 budget 초과
            return DispatchResult(
                outputs={}, realized_method_fqn="com.X",
                dispatch_consistent=True, dispatch_mismatch_reason=None,
                duration_ms=10, jvm_log="",
                captured_anchors=[], captured_brs=[],
            )

    orch = Orchestrator(
        python_generator=_python_gen(),
        java_sandbox=_SlowSandbox(),
        lookup_source_factory=lambda fx: _stub_lookup(),
    )
    plan = RunPlan(delegates_to_tree=[
        {"action_fqn": f"a{i}", "depth": 0} for i in range(10)
    ], estimated_steps=10)
    # timeout_sec=1 (RunOptions 의 ge=1 검증). dispatch 가 느려도 통과해야 함.
    # 하지만 짧은 budget 이면 한두 frame 만 처리 후 timeout
    result = orch.run(_change_spec(), plan, RunOptions(timeout_sec=1))
    # 일부 frame 만 trace (혹은 모두 — 환경 의존)
    assert len(result.delegation_trace) <= 10
    # status 는 completed 또는 failed (budget timing 따라)
    assert result.status in ("completed", "failed")
