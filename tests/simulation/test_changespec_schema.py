"""ChangeSpec / SimResult Pydantic schema 검증.

spec 04 (`toClaude/modeling/handoff-spec/04-changespec-simresult-schema.md`) 의 schema 가
`backend/shared/contracts/simulation.py` 에 1:1 로 정의되어 있는지 검증.

TDD — 본 테스트가 먼저 작성됨, simulation.py 는 본 테스트가 통과하도록 구현.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


# ─── ChangeSpec ─────────────────────────────────────────────────────


def test_change_spec_minimal_only_action_fqn():
    """ChangeSpec 은 action_fqn 만 필수, 나머지는 default 빈 dict (spec 04 §1.1)."""
    from backend.shared.contracts.simulation import ChangeSpec

    cs = ChangeSpec(action_fqn="action.scm.std.match_customer_limit_for_order")
    assert cs.action_fqn == "action.scm.std.match_customer_limit_for_order"
    assert cs.atomic_overrides == {}
    assert cs.scenario_fixture == {}


def test_change_spec_with_atomic_overrides():
    """atomic_overrides 는 dict[str, Any] (spec 04 §1.4 Case A)."""
    from backend.shared.contracts.simulation import ChangeSpec

    cs = ChangeSpec(
        action_fqn="scm.action.CalcCapability",
        atomic_overrides={"scm.shared.atomic.capabilityMultiplier": 1.05},
    )
    assert cs.atomic_overrides["scm.shared.atomic.capabilityMultiplier"] == 1.05


def test_change_spec_with_scenario_fixture_lookups_and_metadata():
    """scenario_fixture 는 lookups + metadata 키 모두 보존 (spec 04 §1.1 구조)."""
    from backend.shared.contracts.simulation import ChangeSpec

    cs = ChangeSpec(
        action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
        atomic_overrides={
            "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.width": 1180,
        },
        scenario_fixture={
            "lookups": {"Customer:7": {"id": 7, "priority": 1}},
            "metadata": {"scenario_origin": "P-2018-0098", "snapshot_at": "2018-04-23T03:14"},
        },
    )
    assert "Customer:7" in cs.scenario_fixture["lookups"]
    assert cs.scenario_fixture["metadata"]["scenario_origin"] == "P-2018-0098"


def test_change_spec_action_fqn_required():
    """action_fqn 누락 시 ValidationError."""
    from backend.shared.contracts.simulation import ChangeSpec

    with pytest.raises(ValidationError):
        ChangeSpec()  # type: ignore[call-arg]


# ─── CreateRunRequest ───────────────────────────────────────────────


def test_create_run_request_with_change_spec_only():
    """CreateRunRequest 의 필수 필드는 change_spec, 나머지는 optional (spec 04 §1.1)."""
    from backend.shared.contracts.simulation import ChangeSpec, CreateRunRequest

    req = CreateRunRequest(change_spec=ChangeSpec(action_fqn="x.y.z"))
    assert req.change_spec.action_fqn == "x.y.z"
    assert req.scenario_id is None
    assert req.requested_by is None


def test_create_run_request_with_scenario_id_and_requester():
    """scenario_id + requested_by 모두 받을 수 있다."""
    from backend.shared.contracts.simulation import ChangeSpec, CreateRunRequest

    req = CreateRunRequest(
        change_spec=ChangeSpec(action_fqn="a"),
        scenario_id="scn-001",
        requested_by="alice",
    )
    assert req.scenario_id == "scn-001"
    assert req.requested_by == "alice"


# ─── BREvidence ─────────────────────────────────────────────────────


def test_br_evidence_passed_minimal():
    """BREvidence outcome=passed 는 violation_path/expected/actual 없이 가능 (spec 04 §2.1)."""
    from backend.shared.contracts.simulation import BREvidence

    ev = BREvidence(
        br_fqn="rule.scm.std.customer_find_first_match_strategy",
        severity="error",
        enforcer_method_fqn="CustomerStdService.findFirstMatch",
        outcome="passed",
    )
    assert ev.outcome == "passed"
    assert ev.violation_path is None
    assert ev.operational_history_refs == []


def test_br_evidence_violated_full():
    """outcome=violated 시 expected/actual + operational_history_refs 채울 수 있다 (spec 04 §6.3)."""
    from backend.shared.contracts.simulation import BREvidence

    ev = BREvidence(
        br_fqn="br.scm.slab.DG003.WidthMin",
        severity="error",
        enforcer_method_fqn=None,
        outcome="violated",
        violation_path="scm.slab.SlabResult.width",
        expected=">=1200",
        actual=1180,
        operational_history_refs=["P-2018-0098"],
    )
    assert ev.outcome == "violated"
    assert ev.actual == 1180
    assert "P-2018-0098" in ev.operational_history_refs


def test_br_evidence_invalid_outcome_rejected():
    """outcome 은 Literal — 알려지지 않은 값은 거부."""
    from backend.shared.contracts.simulation import BREvidence

    with pytest.raises(ValidationError):
        BREvidence(
            br_fqn="x",
            severity="error",
            enforcer_method_fqn=None,
            outcome="unknown",  # type: ignore[arg-type]
        )


# ─── AnchorEvidence ─────────────────────────────────────────────────


def test_anchor_evidence_hit():
    """AnchorEvidence outcome=hit 가 marker + captured_value 보존 (spec 04 §6.2)."""
    from backend.shared.contracts.simulation import AnchorEvidence

    ev = AnchorEvidence(
        anchor_id="a1_proc_pos1",
        marker="자리 1 = HR",
        method_fqn="SdWidthRangeAction.execute",
        line=42,
        outcome="hit",
        captured_value="HR",
    )
    assert ev.outcome == "hit"
    assert ev.captured_value == "HR"


def test_anchor_evidence_deferred_for_stale_anchor():
    """outcome=deferred — anchor 가 stale 마킹된 경우 (spec 04 §4.5)."""
    from backend.shared.contracts.simulation import AnchorEvidence

    ev = AnchorEvidence(
        anchor_id="a2",
        marker="loop_max_iter_check",
        method_fqn="SdAaLoop.execute",
        line=120,
        outcome="deferred",
    )
    assert ev.outcome == "deferred"
    assert ev.captured_value is None


# ─── DelegationTraceFrame ───────────────────────────────────────────


def test_delegation_trace_frame_dispatch_consistent():
    """DelegationTraceFrame 의 dispatch_consistent True (spec 04 §2.1)."""
    from backend.shared.contracts.simulation import DelegationTraceFrame

    f = DelegationTraceFrame(
        seq=1,
        depth=0,
        action_fqn="action.scm.slab.design_orchestrator",
        realized_method_fqn="SdDesigner.design",
        dispatch_consistent=True,
        dispatch_mismatch_reason=None,
        inputs_summary={"order_id": 7},
        outputs_summary=None,
        duration_ms=120,
        in_loop_iter=None,
        error=None,
    )
    assert f.dispatch_consistent is True
    assert f.in_loop_iter is None


def test_delegation_trace_frame_dispatch_mismatch():
    """dispatch_consistent=False 면 verdict 의 (f) 조건 미달 (spec 04 §3.2)."""
    from backend.shared.contracts.simulation import DelegationTraceFrame

    f = DelegationTraceFrame(
        seq=2,
        depth=1,
        action_fqn="action.scm.std.match",
        realized_method_fqn="CustomerStdService.findFirstMatch",
        dispatch_consistent=False,
        dispatch_mismatch_reason="expected scm.order.Order, got scm.order.OrderArchive",
        inputs_summary={},
        outputs_summary=None,
        duration_ms=10,
        in_loop_iter=None,
        error=None,
    )
    assert f.dispatch_consistent is False
    assert "OrderArchive" in (f.dispatch_mismatch_reason or "")


def test_delegation_trace_frame_in_loop():
    """in_loop_iter 채우면 루프 회차 표현."""
    from backend.shared.contracts.simulation import DelegationTraceFrame

    f = DelegationTraceFrame(
        seq=10,
        depth=2,
        action_fqn="action.scm.slab.aa_loop",
        realized_method_fqn=None,
        dispatch_consistent=True,
        dispatch_mismatch_reason=None,
        inputs_summary={},
        outputs_summary=None,
        duration_ms=5,
        in_loop_iter=3,
        error=None,
    )
    assert f.in_loop_iter == 3


# ─── SimResult ──────────────────────────────────────────────────────


def test_sim_result_sim_verified():
    """sim_verified — BR passed + anchor hit (spec 04 §6.1)."""
    from backend.shared.contracts.simulation import (
        AnchorEvidence,
        SimResult,
    )

    r = SimResult(
        run_id="run-001",
        status="completed",
        verdict="sim_verified",
        br_evidence=[],
        anchor_evidence=[
            AnchorEvidence(
                anchor_id="a1",
                marker="m",
                method_fqn="X.f",
                line=1,
                outcome="hit",
                captured_value=1.05,
            )
        ],
        output_values={"capability": 1050.5},
        delegation_trace=[],
        affected_design_gaps=[],
        failure_reason=None,
        started_at="2026-05-10T12:00:00Z",
        completed_at="2026-05-10T12:00:01Z",
        duration_ms=1000,
        change_spec_ref="sha256:abc",
    )
    assert r.verdict == "sim_verified"
    assert len(r.anchor_evidence) == 1


def test_sim_result_sim_violation_with_br_evidence():
    """sim_violation — BR violated + operational_history (spec 04 §6.3)."""
    from backend.shared.contracts.simulation import BREvidence, SimResult

    r = SimResult(
        run_id="run-002",
        status="completed",
        verdict="sim_violation",
        br_evidence=[
            BREvidence(
                br_fqn="br.scm.slab.DG003.WidthMin",
                severity="error",
                enforcer_method_fqn=None,
                outcome="violated",
                violation_path="scm.slab.SlabResult.width",
                expected=">=1200",
                actual=1180,
                operational_history_refs=["P-2018-0098"],
            )
        ],
        anchor_evidence=[],
        output_values={},
        delegation_trace=[],
        affected_design_gaps=[3],
        failure_reason=None,
        started_at="2026-05-10T12:00:00Z",
        completed_at="2026-05-10T12:00:02Z",
        duration_ms=2000,
        change_spec_ref="sha256:def",
    )
    assert r.verdict == "sim_violation"
    assert r.br_evidence[0].outcome == "violated"
    assert 3 in r.affected_design_gaps


def test_sim_result_inconclusive():
    """inconclusive — anchor deferred 또는 sandbox 실패 (spec 04 §3.6)."""
    from backend.shared.contracts.simulation import SimResult

    r = SimResult(
        run_id="run-003",
        status="failed",
        verdict="inconclusive",
        failure_reason="sandbox subprocess timeout",
        started_at="2026-05-10T12:00:00Z",
        completed_at="2026-05-10T12:00:30Z",
        duration_ms=30000,
        change_spec_ref="sha256:ghi",
    )
    assert r.verdict == "inconclusive"
    assert r.failure_reason and "timeout" in r.failure_reason


def test_sim_result_invalid_verdict_rejected():
    """verdict 은 Literal — 3 값 외 거부 (spec 04 §2.1)."""
    from backend.shared.contracts.simulation import SimResult

    with pytest.raises(ValidationError):
        SimResult(
            run_id="x",
            status="completed",
            verdict="passed",  # type: ignore[arg-type]
            started_at="2026-05-10T00:00:00Z",
            completed_at="2026-05-10T00:00:00Z",
            duration_ms=0,
            change_spec_ref="x",
        )


# ─── 통합 — Phase B 시연 (spec 04 §6.2) ────────────────────────────


def test_phase_b_drama_dna_hr_proc_pos1_full_flow():
    """Phase B drama DNA 시연 — HrSpec proc[1] 자리 'HR' 검출 (spec 04 §6.2)."""
    from backend.shared.contracts.simulation import (
        AnchorEvidence,
        ChangeSpec,
        SimResult,
    )

    # Input
    cs = ChangeSpec(
        action_fqn="scm.action.SdWidthRangeAction",
        atomic_overrides={"scm.spec.HrSpec.proc": "0HR23456"},
    )

    # Expected SimResult
    r = SimResult(
        run_id="phase-b-drama",
        status="completed",
        verdict="sim_verified",
        anchor_evidence=[
            AnchorEvidence(
                anchor_id="a1_proc_pos1",
                marker="자리 1 = HR",
                method_fqn="SdWidthRangeAction.execute",
                line=42,
                outcome="hit",
                captured_value="HR",
            )
        ],
        output_values={"width_range": {"min": 1100, "max": 1300}},
        started_at="2026-05-10T12:00:00Z",
        completed_at="2026-05-10T12:00:01Z",
        duration_ms=1000,
        change_spec_ref="sha256:phase-b",
    )

    assert cs.atomic_overrides["scm.spec.HrSpec.proc"] == "0HR23456"
    assert r.verdict == "sim_verified"
    assert r.anchor_evidence[0].captured_value == "HR"
    assert r.output_values["width_range"]["min"] == 1100
