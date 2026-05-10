"""AtomicOverridePatcher (spec 04 §1.2 4-rule 알고리즘) 검증.

Rule 1: path 에 '<...>' 가 있으면 → Action input/output 슬롯 path
        예: "scm.workflow.X.inputs[0]<scm.order.Order>.width" = 1180
Rule 2: path 가 atomic_fqn 단일 토큰 → fixture/lookups 의 모든 row 에 broadcast
        예: "scm.shared.atomic.capabilityMultiplier" = 1.05
Rule 3: path 가 'composite_fqn.slot' 형 → composite 내 atomic 슬롯
        (echo-stub iter 미구현 — composite 식별이 ontology 의존, deferred)
Rule 4: path 인식 안 되면 → ValueError ('invalid path')

TDD — 본 테스트가 먼저, atomic_override_patcher.py 에 코드 추가 후 GREEN.
"""

from __future__ import annotations

import pytest


# ─── 헬퍼 ────────────────────────────────────────────────────────────


def _run_inputs(slots=None, primary_slot="primary"):
    from backend.shared.contracts.simulation import RunInputs, TypedValue

    return RunInputs(
        slots=slots or {primary_slot: TypedValue(_type="scm.order.Order", value={})},
        overrides={},
        primary_input_slot=primary_slot,
    )


# ─── Rule 1: slot path with `<...>` ─────────────────────────────


def test_rule1_simple_field_assignment():
    """slot_path '<type>.field' 가 slot[primary].value['field'] 에 적용."""
    from backend.simulation.runner.atomic_override_patcher import AtomicOverridePatcher

    patcher = AtomicOverridePatcher()
    inputs = _run_inputs()
    overrides = {"scm.workflow.X.inputs[0]<scm.order.Order>.width": 1180}

    updated, warnings = patcher.apply(inputs, overrides, "scm.workflow.X")

    assert updated.slots["primary"].value == {"width": 1180}
    assert warnings == []


def test_rule1_nested_field_assignment():
    """nested path '<type>.spec.diameter' 가 dict 안에 patch."""
    from backend.simulation.runner.atomic_override_patcher import AtomicOverridePatcher

    patcher = AtomicOverridePatcher()
    inputs = _run_inputs()
    overrides = {"scm.workflow.X.inputs[0]<scm.order.Order>.spec.diameter": 250}

    updated, warnings = patcher.apply(inputs, overrides, "scm.workflow.X")

    assert updated.slots["primary"].value == {"spec": {"diameter": 250}}
    assert warnings == []


def test_rule1_multiple_overrides_merge_into_same_slot():
    """여러 override 가 같은 slot 에 누적 적용."""
    from backend.simulation.runner.atomic_override_patcher import AtomicOverridePatcher

    patcher = AtomicOverridePatcher()
    inputs = _run_inputs()
    overrides = {
        "scm.workflow.X.inputs[0]<scm.order.Order>.width": 1180,
        "scm.workflow.X.inputs[0]<scm.order.Order>.thickness": 220,
    }

    updated, _ = patcher.apply(inputs, overrides, "scm.workflow.X")

    assert updated.slots["primary"].value == {"width": 1180, "thickness": 220}


def test_rule1_existing_slot_value_preserved():
    """slot 에 기존 dict 가 있으면 patch 추가 (기존 키 보존)."""
    from backend.shared.contracts.simulation import RunInputs, TypedValue
    from backend.simulation.runner.atomic_override_patcher import AtomicOverridePatcher

    inputs = RunInputs(
        slots={"primary": TypedValue(
            _type="scm.order.Order",
            value={"existing_field": "keep"},
        )},
        primary_input_slot="primary",
    )
    overrides = {"scm.workflow.X.inputs[0]<scm.order.Order>.width": 1180}

    updated, _ = AtomicOverridePatcher().apply(inputs, overrides, "scm.workflow.X")

    assert updated.slots["primary"].value == {"existing_field": "keep", "width": 1180}


def test_rule1_type_mismatch_warning():
    """slot 의 _type 과 override path 의 <type> 가 불일치 → warning 누적, patch 는 시도."""
    from backend.shared.contracts.simulation import RunInputs, TypedValue
    from backend.simulation.runner.atomic_override_patcher import AtomicOverridePatcher

    inputs = RunInputs(
        slots={"primary": TypedValue(_type="scm.order.OtherType", value={})},
        primary_input_slot="primary",
    )
    overrides = {"scm.workflow.X.inputs[0]<scm.order.Order>.width": 1180}

    updated, warnings = AtomicOverridePatcher().apply(inputs, overrides, "scm.workflow.X")

    assert any("type mismatch" in w.lower() or "type" in w.lower() for w in warnings)


# ─── Rule 2: atomic_fqn broadcast to fixture rows ─────────────


def test_rule2_atomic_only_path_broadcasts_to_fixture():
    """atomic_fqn 만 (단일 토큰) → fixture 의 모든 매칭 row 에 broadcast."""
    from backend.shared.contracts.simulation import RunInputs, TypedValue
    from backend.simulation.runner.atomic_override_patcher import AtomicOverridePatcher

    # fake fixture — 두 row 가 capabilityMultiplier atomic 슬롯 보유
    class FakeFixture:
        def __init__(self):
            self.rows = {
                ("scm.std.Customer", 7): {"capabilityMultiplier": 1.0, "name": "정XX"},
                ("scm.std.Customer", 8): {"capabilityMultiplier": 1.0, "name": "박XX"},
            }
            # column → atomic_fqn 매핑
            self.column_to_atomic = {"capabilityMultiplier": "scm.shared.atomic.capabilityMultiplier"}

        def list_rows(self):
            return list(self.rows.items())

        def get_atomic_for_column(self, column):
            return self.column_to_atomic.get(column)

    inputs = RunInputs(
        slots={},
        fixture=FakeFixture(),
        primary_input_slot=None,
    )
    overrides = {"scm.shared.atomic.capabilityMultiplier": 1.05}

    updated, warnings = AtomicOverridePatcher().apply(inputs, overrides, "x")

    # 두 row 모두 capabilityMultiplier 가 1.05 로 patch
    fixture = updated.fixture
    assert fixture.rows[("scm.std.Customer", 7)]["capabilityMultiplier"] == 1.05
    assert fixture.rows[("scm.std.Customer", 8)]["capabilityMultiplier"] == 1.05
    # name 은 보존
    assert fixture.rows[("scm.std.Customer", 7)]["name"] == "정XX"
    # broadcast 알림 warning
    assert any("broadcast" in w.lower() for w in warnings)


def test_rule2_atomic_fixture_none_warns():
    """fixture 없으면 broadcast 불가 — warning."""
    from backend.simulation.runner.atomic_override_patcher import AtomicOverridePatcher

    inputs = _run_inputs()  # fixture=None
    overrides = {"scm.shared.atomic.capabilityMultiplier": 1.05}

    updated, warnings = AtomicOverridePatcher().apply(inputs, overrides, "x")

    assert any("fixture" in w.lower() for w in warnings)


# ─── Rule 4: invalid path → ValueError ────────────────────────


def test_rule4_invalid_path_raises():
    """완전히 인식 못 하는 path → ValueError."""
    from backend.simulation.runner.atomic_override_patcher import AtomicOverridePatcher

    patcher = AtomicOverridePatcher()
    # 빈 문자열은 분명 invalid
    with pytest.raises(ValueError, match="invalid path"):
        patcher.apply(_run_inputs(), {"": 123}, "x")


# ─── 통합: empty overrides → no-op ─────────────────────────────


def test_empty_overrides_returns_inputs_unchanged():
    from backend.simulation.runner.atomic_override_patcher import AtomicOverridePatcher

    inputs = _run_inputs()
    updated, warnings = AtomicOverridePatcher().apply(inputs, {}, "x")
    assert updated.slots["primary"].value == {}
    assert warnings == []


# ─── Rule 1 ↔ slot index 매핑 — inputs[1] 이라면 다른 slot ─────


def test_rule1_inputs_index_matches_slot_position():
    """inputs[1] 은 두 번째 slot. 현재 echo-stub 은 'primary' slot 1개만 — index>0 은 warning."""
    from backend.simulation.runner.atomic_override_patcher import AtomicOverridePatcher

    inputs = _run_inputs()  # slot 1개만 (primary)
    overrides = {"scm.workflow.X.inputs[1]<scm.order.Order>.width": 1180}

    updated, warnings = AtomicOverridePatcher().apply(inputs, overrides, "scm.workflow.X")
    # inputs[1] 매칭 slot 없음 → warning, patch 안 됨
    assert updated.slots["primary"].value == {}
    assert any("index" in w.lower() or "slot" in w.lower() for w in warnings)
