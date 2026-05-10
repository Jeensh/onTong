"""promote/downgrade hook (spec 04 §3.4) 검증.

Orchestrator 가 verdict + scenario.kind 에 따라
SimResult.suggested_promotion / suggested_downgrade 를 채움.

정책:
- verdict=sim_verified + scenario_kind ∈ {regression, boundary, integration}
  → suggested_promotion = "BODY_ANCHORED → SIM_VERIFIED"
- verdict=sim_violation
  → suggested_downgrade = "SIM_VERIFIED → BODY_ANCHORED"
- 그 외 → 둘 다 None
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


def _passing_sandbox():
    class _S:
        def dispatch(self, *a, **k):
            return DispatchResult(
                outputs={}, realized_method_fqn="com.X.method",
                dispatch_consistent=True, dispatch_mismatch_reason=None,
                duration_ms=0, jvm_log="",
                captured_anchors=[], captured_brs=[],
            )
    return _S()


def _violating_sandbox():
    class _S:
        def dispatch(self, *a, **k):
            return DispatchResult(
                outputs={}, realized_method_fqn="com.X.method",
                dispatch_consistent=True, dispatch_mismatch_reason=None,
                duration_ms=0, jvm_log="",
                captured_anchors=[],
                captured_brs=[BRTrigger(
                    br_fqn="br.x.violated", enforcer_method_fqn=None,
                    outcome="violated", violation_path="x",
                    expected=">=10", actual=5,
                )],
            )
    return _S()


def _orchestrator(sandbox):
    return Orchestrator(
        python_generator=_python_gen(),
        java_sandbox=sandbox,
        lookup_source_factory=lambda fx: _stub_lookup(),
    )


def _plan_one_frame():
    return RunPlan(delegates_to_tree=[
        {"action_fqn": "a", "depth": 0, "primary_input_type": "scm.X"},
    ], estimated_steps=1)


# ─── sim_verified + scenario_kind regression → promote 권장 ────


def test_promote_suggested_for_sim_verified_regression():
    cs = ChangeSpec(
        action_fqn="a",
        atomic_overrides={},
        scenario_fixture={"metadata": {"scenario_kind": "regression"}},
    )
    result = _orchestrator(_passing_sandbox()).run(cs, _plan_one_frame(), RunOptions())
    assert result.verdict == "sim_verified"
    assert result.suggested_promotion == "BODY_ANCHORED → SIM_VERIFIED"
    assert result.suggested_downgrade is None


def test_promote_suggested_for_boundary_kind():
    cs = ChangeSpec(
        action_fqn="a",
        atomic_overrides={},
        scenario_fixture={"metadata": {"scenario_kind": "boundary"}},
    )
    result = _orchestrator(_passing_sandbox()).run(cs, _plan_one_frame(), RunOptions())
    assert result.suggested_promotion == "BODY_ANCHORED → SIM_VERIFIED"


def test_promote_suggested_for_integration_kind():
    cs = ChangeSpec(
        action_fqn="a",
        atomic_overrides={},
        scenario_fixture={"metadata": {"scenario_kind": "integration"}},
    )
    result = _orchestrator(_passing_sandbox()).run(cs, _plan_one_frame(), RunOptions())
    assert result.suggested_promotion == "BODY_ANCHORED → SIM_VERIFIED"


# ─── sim_verified 지만 scenario_kind=drama → promote 안 함 ────


def test_no_promote_for_drama_scenario_kind():
    cs = ChangeSpec(
        action_fqn="a",
        atomic_overrides={},
        scenario_fixture={"metadata": {"scenario_kind": "drama"}},
    )
    result = _orchestrator(_passing_sandbox()).run(cs, _plan_one_frame(), RunOptions())
    assert result.verdict == "sim_verified"
    assert result.suggested_promotion is None  # drama 는 promote 권장 안 함
    assert result.suggested_downgrade is None


def test_no_promote_when_scenario_kind_missing():
    cs = ChangeSpec(
        action_fqn="a", atomic_overrides={}, scenario_fixture={"lookups": {}},
    )
    result = _orchestrator(_passing_sandbox()).run(cs, _plan_one_frame(), RunOptions())
    assert result.suggested_promotion is None


# ─── sim_violation → downgrade 권장 ─────────────────────────────


def test_downgrade_suggested_for_sim_violation():
    cs = ChangeSpec(
        action_fqn="a",
        atomic_overrides={},
        scenario_fixture={"metadata": {"scenario_kind": "regression"}},
    )
    result = _orchestrator(_violating_sandbox()).run(cs, _plan_one_frame(), RunOptions())
    assert result.verdict == "sim_violation"
    assert result.suggested_downgrade == "SIM_VERIFIED → BODY_ANCHORED"
    assert result.suggested_promotion is None


# ─── inconclusive → 둘 다 None ──────────────────────────────────


def test_no_hook_for_inconclusive():
    """dispatch_consistent=False 시뮬 — verdict=inconclusive."""

    class _Inconsistent:
        def dispatch(self, *a, **k):
            return DispatchResult(
                outputs={}, realized_method_fqn=None,
                dispatch_consistent=False,
                dispatch_mismatch_reason="no realization",
                duration_ms=0, jvm_log="",
                captured_anchors=[], captured_brs=[],
            )

    cs = ChangeSpec(
        action_fqn="a",
        atomic_overrides={},
        scenario_fixture={"metadata": {"scenario_kind": "regression"}},
    )
    result = _orchestrator(_Inconsistent()).run(cs, _plan_one_frame(), RunOptions())
    assert result.verdict == "inconclusive"
    assert result.suggested_promotion is None
    assert result.suggested_downgrade is None
