"""JavaSandbox + StubJavaSandbox (spec 05 §2 + §3.4.5) — fixture_only stub tier 검증.

spec 05 §2.5 stub backend 의 합의:
- 모든 expected_anchors 자동 hit
- 모든 BR (Action.preconditions + postconditions) 자동 passed
- duration_ms=0, jvm_log="[stub mode]\\n"
- outputs 는 비어있음 (echo expected_outputs 는 후속 iteration)

TDD — 본 테스트가 먼저, java_sandbox.py 에 코드 추가 후 GREEN.
"""

from __future__ import annotations

import pytest


# ─── Fake DTOs (modeling 측 schema 와 같은 attribute 만 노출 — duck-typed) ───


class FakeRealization:
    def __init__(self, code_method_fqn, applies_to=None, confidence=1.0):
        self.code_method_fqn = code_method_fqn
        self.applies_to_code_type_fqn = applies_to
        self.confidence = confidence


class FakeAction:
    def __init__(self, fqn, preconditions=None, postconditions=None, params=None):
        self.fqn = fqn
        self.preconditions = preconditions or []
        self.postconditions = postconditions or []
        self.params = params or []


class FakeAnchorBinding:
    def __init__(self, id_, anchor_locator, code_method_fqn, target_action_fqn, target_slot="param[0]"):
        self.id = id_
        self.anchor_locator = anchor_locator
        self.code_method_fqn = code_method_fqn
        self.target_action_fqn = target_action_fqn
        self.target_slot = target_slot


class FakeOntologyClient:
    """spec 05 §7.1 의 modeling facade duck stub.

    StubJavaSandbox 가 의존하는 메서드만 노출:
      - get_action(fqn) -> FakeAction | None
      - get_realizations_for_input_type(action_fqn, code_type_fqn) -> list[FakeRealization]
      - get_anchor_bindings_for_action(action_fqn) -> list[FakeAnchorBinding]
    """

    def __init__(self, *, actions=None, realizations_by_input=None, anchor_bindings=None):
        self._actions = actions or {}
        self._realizations = realizations_by_input or {}
        self._bindings = anchor_bindings or {}

    def get_action(self, fqn):
        return self._actions.get(fqn)

    def get_realizations_for_input_type(self, action_fqn, code_type_fqn):
        return list(self._realizations.get((action_fqn, code_type_fqn), []))

    def get_anchor_bindings_for_action(self, action_fqn):
        return list(self._bindings.get(action_fqn, []))


def make_run_inputs(*, primary_type="scm.order.Order", primary_value=None):
    """헬퍼 — primary_input_slot='order' 로 RunInputs 생성."""
    from backend.shared.contracts.simulation import RunInputs, TypedValue

    return RunInputs(
        slots={"order": TypedValue(_type=primary_type, value=primary_value or {"width": 1180})},
        overrides={},
        primary_input_slot="order",
    )


def make_run_options():
    from backend.shared.contracts.simulation import RunOptions

    return RunOptions(sandbox_tier="stub_dispatch")


# ─── 1. JavaSandbox Protocol 존재 확인 ─────────────────────────────


def test_java_sandbox_protocol_defines_dispatch_method():
    """JavaSandbox 는 dispatch(action_fqn, inputs, run_options) -> DispatchResult Protocol."""
    from backend.simulation.runner.java_sandbox import JavaSandbox

    # Protocol 은 attribute 'dispatch' 를 가져야 함
    assert hasattr(JavaSandbox, "dispatch")


# ─── 2. StubJavaSandbox 인스턴스화 ─────────────────────────────────


def test_stub_java_sandbox_instantiation_with_stub_capabilities():
    """SandboxCapabilities(backend='stub') 로 StubJavaSandbox 생성."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    cap = SandboxCapabilities(backend="stub")
    client = FakeOntologyClient()
    sandbox = StubJavaSandbox(capabilities=cap, ontology_client=client)
    assert sandbox is not None


def test_stub_java_sandbox_rejects_non_stub_backend():
    """SandboxCapabilities.backend='jvm_subprocess' 는 StubJavaSandbox 가 거부."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    cap = SandboxCapabilities(backend="jvm_subprocess")
    with pytest.raises(ValueError, match="stub"):
        StubJavaSandbox(capabilities=cap, ontology_client=FakeOntologyClient())


# ─── 3. dispatch — DispatchResult 기본 형태 ──────────────────────


def test_stub_dispatch_returns_dispatch_result():
    """dispatch() → DispatchResult."""
    from backend.shared.contracts.simulation import DispatchResult, SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=FakeOntologyClient(),
    )
    result = sandbox.dispatch(
        action_fqn="action.scm.std.match",
        inputs=make_run_inputs(),
        run_options=make_run_options(),
    )
    assert isinstance(result, DispatchResult)


def test_stub_dispatch_metadata_jvm_log_and_duration():
    """spec 05 §3.4.5 — duration_ms=0, jvm_log='[stub mode]\\n'."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=FakeOntologyClient(),
    )
    result = sandbox.dispatch(
        action_fqn="action.scm.std.match",
        inputs=make_run_inputs(),
        run_options=make_run_options(),
    )
    assert result.duration_ms == 0
    assert result.jvm_log == "[stub mode]\n"


# ─── 4. Realization 선택 + dispatch_consistent ────────────────────


def test_stub_dispatch_realized_method_from_first_realization():
    """spec 05 §2.3 step 1~2 — list_realizations_for_input_type[0].code_method_fqn 을 realized_method_fqn."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    client = FakeOntologyClient(
        realizations_by_input={
            ("action.scm.std.match", "scm.order.Order"): [
                FakeRealization("com.scm.OrderMatcher.match", confidence=0.9),
                FakeRealization("com.scm.AltMatcher.match", confidence=0.5),
            ]
        }
    )
    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=client,
    )
    result = sandbox.dispatch(
        action_fqn="action.scm.std.match",
        inputs=make_run_inputs(primary_type="scm.order.Order"),
        run_options=make_run_options(),
    )
    assert result.realized_method_fqn == "com.scm.OrderMatcher.match"
    assert result.dispatch_consistent is True
    assert result.dispatch_mismatch_reason is None


def test_stub_dispatch_inconsistent_when_no_realization_for_input_type():
    """realization 없음 → dispatch_consistent=False + mismatch_reason 채움."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=FakeOntologyClient(),  # realizations 없음
    )
    result = sandbox.dispatch(
        action_fqn="action.scm.std.match",
        inputs=make_run_inputs(primary_type="scm.order.Order"),
        run_options=make_run_options(),
    )
    assert result.dispatch_consistent is False
    assert result.dispatch_mismatch_reason is not None
    assert "scm.order.Order" in result.dispatch_mismatch_reason
    assert result.realized_method_fqn is None


def test_stub_dispatch_no_primary_input_slot_returns_inconsistent():
    """primary_input_slot=None → dispatch 무관 (pure constant Action) 이지만 stub 은 consistent=False 로 conservative."""
    from backend.shared.contracts.simulation import RunInputs, RunOptions, SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=FakeOntologyClient(),
    )
    result = sandbox.dispatch(
        action_fqn="action.scm.std.constant",
        inputs=RunInputs(slots={}, overrides={}, primary_input_slot=None),
        run_options=RunOptions(sandbox_tier="stub_dispatch"),
    )
    assert result.realized_method_fqn is None
    assert result.dispatch_consistent is False
    assert "primary_input" in (result.dispatch_mismatch_reason or "").lower()


# ─── 5. Anchor auto-hit (spec 05 §3.4.5 step 3) ───────────────────


def test_stub_dispatch_captured_anchors_from_bindings():
    """get_anchor_bindings_for_action 의 모든 binding 이 AnchorHit 로 변환."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    bindings = [
        FakeAnchorBinding(
            id_="a1", anchor_locator="자리 1 = HR",
            code_method_fqn="com.scm.OrderMatcher.match",
            target_action_fqn="action.scm.std.match",
        ),
        FakeAnchorBinding(
            id_="a2", anchor_locator="literal:0.10",
            code_method_fqn="com.scm.OrderMatcher.match",
            target_action_fqn="action.scm.std.match",
        ),
    ]
    client = FakeOntologyClient(
        anchor_bindings={"action.scm.std.match": bindings},
        realizations_by_input={
            ("action.scm.std.match", "scm.order.Order"): [FakeRealization("com.scm.OrderMatcher.match")]
        },
    )
    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=client,
    )
    result = sandbox.dispatch(
        action_fqn="action.scm.std.match",
        inputs=make_run_inputs(),
        run_options=make_run_options(),
    )
    assert len(result.captured_anchors) == 2
    ids = {a.anchor_id for a in result.captured_anchors}
    assert ids == {"a1", "a2"}
    a1 = next(a for a in result.captured_anchors if a.anchor_id == "a1")
    assert a1.marker == "자리 1 = HR"
    assert a1.captured_value is None  # stub 은 runtime 값 없음


# ─── 6. BR auto-pass (spec 05 §3.4.5 step 4) ──────────────────────


def test_stub_dispatch_captured_brs_from_action_pre_post_conditions():
    """Action.preconditions + postconditions → BRTrigger(outcome=passed)."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    action = FakeAction(
        fqn="action.scm.std.match",
        preconditions=["br.scm.slab.DG003.WidthMin"],
        postconditions=["br.scm.slab.DG003.WidthMax"],
    )
    client = FakeOntologyClient(
        actions={"action.scm.std.match": action},
        realizations_by_input={
            ("action.scm.std.match", "scm.order.Order"): [FakeRealization("com.scm.OrderMatcher.match")]
        },
    )
    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=client,
    )
    result = sandbox.dispatch(
        action_fqn="action.scm.std.match",
        inputs=make_run_inputs(),
        run_options=make_run_options(),
    )
    assert len(result.captured_brs) == 2
    assert {b.br_fqn for b in result.captured_brs} == {
        "br.scm.slab.DG003.WidthMin",
        "br.scm.slab.DG003.WidthMax",
    }
    assert all(b.outcome == "passed" for b in result.captured_brs)
    assert all(b.violation_path is None for b in result.captured_brs)


def test_stub_dispatch_no_brs_when_action_unknown():
    """get_action() → None 시 BR 비어있음 (graceful)."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=FakeOntologyClient(),  # actions 비어있음
    )
    result = sandbox.dispatch(
        action_fqn="action.scm.std.unknown",
        inputs=make_run_inputs(),
        run_options=make_run_options(),
    )
    assert result.captured_brs == []


# ─── 7. outputs 기본값 (spec 05 §3.4.5 step 5 — echo 미구현, 빈 dict) ──


def test_stub_dispatch_outputs_empty_by_default():
    """첫 iteration 의 stub 은 outputs={} (expected_outputs echo 는 미구현)."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    client = FakeOntologyClient(
        realizations_by_input={
            ("action.scm.std.match", "scm.order.Order"): [FakeRealization("com.scm.OrderMatcher.match")]
        }
    )
    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=client,
    )
    result = sandbox.dispatch(
        action_fqn="action.scm.std.match",
        inputs=make_run_inputs(),
        run_options=make_run_options(),
    )
    assert result.outputs == {}


# ─── 8. Phase B P-2018-0098 회귀 — drama DNA HR proc anchor capture ────


def test_stub_dispatch_falls_back_to_action_realizations_when_primary_input_unknown():
    """primary_input_slot=None 이라도 action.realizations[0] 가 있으면 fallback consistent=True.

    실 ontology 회귀: 많은 action 이 params 없거나 primary_input_type 미상.
    """
    from backend.shared.contracts.simulation import RunInputs, RunOptions, SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    action = FakeAction(fqn="action.x")
    action.realizations = [FakeRealization("com.X.method")]
    client = FakeOntologyClient(actions={"action.x": action})

    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=client,
    )
    result = sandbox.dispatch(
        action_fqn="action.x",
        inputs=RunInputs(slots={}, overrides={}, primary_input_slot=None),
        run_options=RunOptions(sandbox_tier="stub_dispatch"),
    )
    # fallback: action.realizations[0] 의 code_method_fqn → consistent=True
    assert result.realized_method_fqn == "com.X.method"
    assert result.dispatch_consistent is True


def test_stub_dispatch_falls_back_when_primary_type_yields_no_realizations():
    """primary_input_slot 있지만 type 별 realization 0건 + action.realizations 는 있음 → fallback."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    action = FakeAction(fqn="action.y")
    action.realizations = [FakeRealization("com.Y.method")]
    # get_realizations_for_input_type 는 빈 리스트 반환 (type-specific 매칭 없음)
    client = FakeOntologyClient(actions={"action.y": action})

    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=client,
    )
    result = sandbox.dispatch(
        action_fqn="action.y",
        inputs=make_run_inputs(primary_type="scm.unknown.Type"),
        run_options=make_run_options(),
    )
    assert result.realized_method_fqn == "com.Y.method"
    assert result.dispatch_consistent is True


def test_stub_dispatch_p_2018_0098_anchor_capture_for_drama_dna():
    """P-2018-0098 회귀: '자리 1 = HR' anchor 가 드라마 DNA 로 capture 되는지."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox

    bindings = [
        FakeAnchorBinding(
            id_="anchor.scm.proc_kind_hr",
            anchor_locator="자리 1 = HR",
            code_method_fqn="com.scm.SdDesigner.runStep1",
            target_action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
        ),
    ]
    action = FakeAction(
        fqn="scm.workflow.SDSlabEntity_step_1_to_8",
        preconditions=["br.scm.slab.DG003.WidthMin"],
    )
    client = FakeOntologyClient(
        actions={"scm.workflow.SDSlabEntity_step_1_to_8": action},
        anchor_bindings={"scm.workflow.SDSlabEntity_step_1_to_8": bindings},
        realizations_by_input={
            ("scm.workflow.SDSlabEntity_step_1_to_8", "scm.order.Order"): [
                FakeRealization("com.scm.SdDesigner.runStep1")
            ]
        },
    )
    sandbox = StubJavaSandbox(
        capabilities=SandboxCapabilities(backend="stub"),
        ontology_client=client,
    )
    result = sandbox.dispatch(
        action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
        inputs=make_run_inputs(primary_type="scm.order.Order"),
        run_options=make_run_options(),
    )
    # drama DNA anchor 가 자동 hit
    assert len(result.captured_anchors) == 1
    assert result.captured_anchors[0].anchor_id == "anchor.scm.proc_kind_hr"
    assert result.captured_anchors[0].marker == "자리 1 = HR"
    # BR auto-pass (sim_verified verdict 가능)
    assert len(result.captured_brs) == 1
    assert result.captured_brs[0].outcome == "passed"
    # dispatch_consistent — verdict 6 조건 (f) 통과
    assert result.dispatch_consistent is True
    assert result.realized_method_fqn == "com.scm.SdDesigner.runStep1"
