"""Runner-side Pydantic 모델 검증 (spec 05 Section 1, 2, 3, 4.6, 4.8).

`backend/shared/contracts/simulation.py` 에 추가될 모델:
- TypedValue / RunInputs / RunPlan
- GeneratedScript
- DispatchResult / AnchorHit / BRTrigger / SandboxCapabilities
- TableSpec / LookupRow
- FailurePolicy

TDD — 본 테스트가 먼저, simulation.py 에 모델 추가 후 GREEN.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


# ─── TypedValue / RunInputs / RunPlan (spec 05 §4.6) ────────────────


def test_typed_value_with_type_and_value():
    """TypedValue 는 _type (CodeType FQN) + value (any) 보유."""
    from backend.shared.contracts.simulation import TypedValue

    tv = TypedValue(type_="scm.order.Order", value={"width": 1180, "thickness": 220})
    assert tv.type_ == "scm.order.Order"
    assert tv.value["width"] == 1180


def test_run_plan_minimal():
    """RunPlan — delegates_to_tree 없이도 minimal (estimated_steps 만)."""
    from backend.shared.contracts.simulation import RunPlan

    p = RunPlan(estimated_steps=3)
    assert p.estimated_steps == 3
    assert p.delegates_to_tree == []


def test_run_plan_with_tree_and_brs():
    """RunPlan — delegates_to_tree + expected_brs.direct/transitive (spec 04 §3.3)."""
    from backend.shared.contracts.simulation import RunPlan

    p = RunPlan(
        delegates_to_tree=[
            {"action_fqn": "action.scm.std.match_customer_limit_for_order", "depth": 0},
        ],
        expected_brs={
            "direct": ["rule.scm.std.customer_find_first_match_strategy"],
            "transitive": [],
        },
        expected_anchors=["anchor_customer_first_match"],
        estimated_steps=2,
        warnings=[],
    )
    assert "rule.scm.std.customer_find_first_match_strategy" in p.expected_brs["direct"]
    assert p.estimated_steps == 2


def test_run_inputs_with_slots_and_primary():
    """RunInputs — slots / overrides / primary_input_slot (spec 05 §4.6)."""
    from backend.shared.contracts.simulation import RunInputs, TypedValue

    inp = RunInputs(
        slots={
            "order": TypedValue(type_="scm.order.Order", value={"width": 1180}),
            "customer": TypedValue(type_="scm.std.CustomerStd", value={"id": 7}),
        },
        overrides={"scm.shared.atomic.thickness": 220},
        primary_input_slot="order",
    )
    assert inp.primary_input_slot == "order"
    assert inp.slots["order"].type_ == "scm.order.Order"
    assert inp.overrides["scm.shared.atomic.thickness"] == 220


# ─── GeneratedScript (spec 05 §1.2) ─────────────────────────────────


def test_generated_script_minimal():
    """GeneratedScript — source_code + entrypoint 만 필수."""
    from backend.shared.contracts.simulation import GeneratedScript

    gs = GeneratedScript(
        source_code="def run(inputs): return inputs",
        entrypoint="run",
        imports=["dataclasses", "typing"],
        estimated_steps=1,
        java_dispatch_calls=[],
        fixture_keys_used=[],
    )
    assert gs.entrypoint == "run"
    assert "dataclasses" in gs.imports


# ─── DispatchResult / AnchorHit / BRTrigger (spec 05 §2.2) ──────────


def test_anchor_hit_minimal():
    """AnchorHit — anchor_id / marker / line + captured_value optional."""
    from backend.shared.contracts.simulation import AnchorHit

    a = AnchorHit(anchor_id="a1", marker="자리 1 = HR", line=58, captured_value="HR")
    assert a.captured_value == "HR"


def test_br_trigger_passed():
    """BRTrigger outcome=passed."""
    from backend.shared.contracts.simulation import BRTrigger

    t = BRTrigger(
        br_fqn="rule.scm.std.customer_find_first_match_strategy",
        enforcer_method_fqn="CustomerStdService.findFirstMatch",
        outcome="passed",
    )
    assert t.outcome == "passed"
    assert t.violation_path is None


def test_br_trigger_violated():
    """BRTrigger outcome=violated 는 violation_path/expected/actual 채울 수 있다."""
    from backend.shared.contracts.simulation import BRTrigger

    t = BRTrigger(
        br_fqn="br.scm.slab.DG003.WidthMin",
        enforcer_method_fqn=None,
        outcome="violated",
        violation_path="scm.slab.SlabResult.width",
        expected=">=1200",
        actual=1180,
    )
    assert t.actual == 1180


def test_dispatch_result_with_anchors_and_brs():
    """DispatchResult — outputs + realized_method_fqn + dispatch_consistent + captured 리스트."""
    from backend.shared.contracts.simulation import (
        AnchorHit,
        BRTrigger,
        DispatchResult,
    )

    r = DispatchResult(
        outputs={"slabResult": {"width": 1200}},
        realized_method_fqn="SdWidthRangeAction.execute",
        dispatch_consistent=True,
        dispatch_mismatch_reason=None,
        duration_ms=42,
        jvm_log="[stub mode]\n",
        captured_anchors=[AnchorHit(anchor_id="a1", marker="m", line=1, captured_value=None)],
        captured_brs=[
            BRTrigger(
                br_fqn="rule.x", enforcer_method_fqn="X.f", outcome="passed",
            )
        ],
    )
    assert r.dispatch_consistent is True
    assert len(r.captured_anchors) == 1
    assert r.captured_brs[0].outcome == "passed"


def test_sandbox_capabilities_stub():
    """SandboxCapabilities backend=stub — minimal."""
    from backend.shared.contracts.simulation import SandboxCapabilities

    c = SandboxCapabilities(backend="stub")
    assert c.backend == "stub"
    assert c.max_concurrent_dispatches == 4  # default


def test_sandbox_capabilities_invalid_backend():
    """backend 는 Literal — 외 값 거부."""
    from backend.shared.contracts.simulation import SandboxCapabilities

    with pytest.raises(ValidationError):
        SandboxCapabilities(backend="rust")  # type: ignore[arg-type]


# ─── TableSpec / LookupRow (spec 05 §3.2) ──────────────────────────


def test_table_spec_with_columns_and_drama_dna():
    """TableSpec — code_type_fqn + pk_atom_fqn + columns + drama_dna_columns."""
    from backend.shared.contracts.simulation import TableSpec

    ts = TableSpec(
        code_type_fqn="scm.std.CustomerStd",
        pk_atom_fqn="scm.shared.atomic.customer_no",
        columns={
            "name": "scm.shared.atomic.customer_name",
            "thickness_min": "scm.shared.atomic.thickness",
        },
        drama_dna_columns=["name"],
    )
    assert ts.columns["name"] == "scm.shared.atomic.customer_name"
    assert "name" in ts.drama_dna_columns


def test_lookup_row_with_columns():
    """LookupRow — pk + table_spec_fqn + columns 값 dict."""
    from backend.shared.contracts.simulation import LookupRow

    r = LookupRow(
        pk=7,
        table_spec_fqn="scm.std.CustomerStd",
        columns={"customer_name": "정XX", "thickness_min": 200},
    )
    assert r.pk == 7
    assert r.columns["customer_name"] == "정XX"


# ─── FailurePolicy (spec 05 §4.8) ──────────────────────────────────


def test_failure_policy_defaults():
    """FailurePolicy 기본값 — fail_fast / continue / continue / continue."""
    from backend.shared.contracts.simulation import FailurePolicy

    fp = FailurePolicy()
    assert fp.on_dispatch_error == "fail_fast"
    assert fp.on_br_violation == "continue"
    assert fp.on_anchor_miss == "continue"
    assert fp.on_dispatch_inconsistent == "continue"


def test_failure_policy_custom_for_drama():
    """drama 시연 — on_br_violation=fail_fast 로 설정 가능 (spec 05 §4.8)."""
    from backend.shared.contracts.simulation import FailurePolicy

    fp = FailurePolicy(on_br_violation="fail_fast")
    assert fp.on_br_violation == "fail_fast"
