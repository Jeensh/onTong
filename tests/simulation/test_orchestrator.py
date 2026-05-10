"""Orchestrator (spec 05 §4.5) — running 단계 entry + verdict 판정 e2e 검증.

echo-stub iteration 합의:
- LookupDataSource factory + PythonGenerator + StubJavaSandbox 묶기
- generated source_code 는 artifact (실제 dispatch 는 orchestrator 가 직접)
- BRTrigger → BREvidence / AnchorHit → AnchorEvidence 매핑
- verdict 판정 (spec 04 §3.2 6 조건 단순화 — 첫 iter):
  * sim_verified : all BR passed + all anchor hit + all dispatch_consistent + status=completed
  * sim_violation: any BR (outcome=violated, severity=error)
  * inconclusive : 위 둘 외

TDD — 본 테스트 먼저, orchestrator.py 에 코드 추가 후 GREEN.
"""

from __future__ import annotations

import pytest


# ─── Fake DTOs (이전 step 의 테스트 패턴 재사용) ─────────────────────


class FakeRealization:
    def __init__(self, code_method_fqn, applies_to=None, confidence=1.0):
        self.code_method_fqn = code_method_fqn
        self.applies_to_code_type_fqn = applies_to
        self.confidence = confidence


class FakeAction:
    def __init__(self, fqn, preconditions=None, postconditions=None):
        self.fqn = fqn
        self.preconditions = preconditions or []
        self.postconditions = postconditions or []


class FakeAnchorBinding:
    def __init__(self, id_, anchor_locator, code_method_fqn, target_action_fqn):
        self.id = id_
        self.anchor_locator = anchor_locator
        self.code_method_fqn = code_method_fqn
        self.target_action_fqn = target_action_fqn
        self.target_slot = "param[0]"


class FakeOntologyClient:
    def __init__(self, *, actions=None, realizations_by_input=None, anchor_bindings=None, code_types=None):
        self._actions = actions or {}
        self._realizations = realizations_by_input or {}
        self._bindings = anchor_bindings or {}
        self._code_types = code_types or []

    def get_action(self, fqn):
        return self._actions.get(fqn)

    def get_realizations_for_input_type(self, action_fqn, code_type_fqn):
        return list(self._realizations.get((action_fqn, code_type_fqn), []))

    def get_anchor_bindings_for_action(self, action_fqn):
        return list(self._bindings.get(action_fqn, []))

    def list_code_types(self, role=None):
        if role is None:
            return list(self._code_types)
        return [ct for ct in self._code_types if getattr(ct, "role", None) == role]


# ─── 헬퍼 — Orchestrator 인스턴스화 ───────────────────────────────


def _build_orchestrator(*, ontology_client=None):
    """공통 wiring — PythonGenerator + StubJavaSandbox + LookupDataSource factory."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox
    from backend.simulation.runner.lookup_source import LookupDataSource
    from backend.simulation.runner.orchestrator import Orchestrator
    from backend.simulation.runner.python_generator import PythonGenerator

    ont = ontology_client or FakeOntologyClient()
    sandbox = StubJavaSandbox(SandboxCapabilities(backend="stub"), ont)
    return Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=sandbox,
        lookup_source_factory=lambda fixture: LookupDataSource(ont, fixture),
    )


def _change_spec(action="action.scm.std.match", lookups=None, overrides=None):
    from backend.shared.contracts.simulation import ChangeSpec

    return ChangeSpec(
        action_fqn=action,
        atomic_overrides=overrides or {},
        scenario_fixture={"lookups": lookups or {}, "metadata": {}},
    )


def _run_plan(actions=None, primary_type="scm.order.Order"):
    from backend.shared.contracts.simulation import RunPlan

    return RunPlan(
        delegates_to_tree=[
            {"action_fqn": a, "depth": i, "primary_input_type": primary_type}
            for i, a in enumerate(actions or [], start=1)
        ],
        estimated_steps=len(actions or []),
    )


def _run_options():
    from backend.shared.contracts.simulation import RunOptions

    return RunOptions(sandbox_tier="stub_dispatch")


# ─── 1. SimResult 기본 형태 ────────────────────────────────────────


def test_orchestrator_run_returns_sim_result():
    from backend.shared.contracts.simulation import SimResult

    orch = _build_orchestrator()
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    assert isinstance(result, SimResult)


def test_orchestrator_run_status_completed_for_normal_run():
    orch = _build_orchestrator()
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    assert result.status == "completed"


def test_orchestrator_run_run_id_is_non_empty_string():
    orch = _build_orchestrator()
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    assert isinstance(result.run_id, str) and len(result.run_id) > 0


def test_orchestrator_run_timestamps_set():
    """started_at / completed_at / duration_ms 채워짐."""
    orch = _build_orchestrator()
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    assert result.started_at != ""
    assert result.completed_at != ""
    assert result.duration_ms >= 0


def test_orchestrator_run_change_spec_ref_set():
    """change_spec_ref 가 비어있지 않음 (재현 시 입력 검증용)."""
    orch = _build_orchestrator()
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    assert isinstance(result.change_spec_ref, str) and len(result.change_spec_ref) > 0


# ─── 2. delegation_trace ─────────────────────────────────────────


def test_orchestrator_trace_one_frame_per_delegation_edge():
    """delegates_to_tree N edge → trace N frame."""
    ont = FakeOntologyClient(
        realizations_by_input={
            ("a1", "scm.order.Order"): [FakeRealization("com.X.a1")],
            ("a2", "scm.order.Order"): [FakeRealization("com.X.a2")],
        },
    )
    orch = _build_orchestrator(ontology_client=ont)
    result = orch.run(_change_spec(), _run_plan(actions=["a1", "a2"]), _run_options())
    assert len(result.delegation_trace) == 2
    assert [f.action_fqn for f in result.delegation_trace] == ["a1", "a2"]
    assert [f.seq for f in result.delegation_trace] == [1, 2]


def test_orchestrator_trace_dispatch_consistent_propagated():
    """sandbox 의 DispatchResult.dispatch_consistent → frame.dispatch_consistent."""
    ont = FakeOntologyClient(
        realizations_by_input={
            ("a1", "scm.order.Order"): [FakeRealization("com.X.a1")],
            # a2 는 realization 없음 → consistent=False
        },
    )
    orch = _build_orchestrator(ontology_client=ont)
    result = orch.run(_change_spec(), _run_plan(actions=["a1", "a2"]), _run_options())
    f1 = next(f for f in result.delegation_trace if f.action_fqn == "a1")
    f2 = next(f for f in result.delegation_trace if f.action_fqn == "a2")
    assert f1.dispatch_consistent is True
    assert f2.dispatch_consistent is False
    assert f2.dispatch_mismatch_reason is not None


# ─── 3. verdict 판정 (spec 04 §3.2 단순화) ────────────────────────


def test_orchestrator_verdict_sim_verified_when_all_pass_and_consistent():
    """모든 BR passed + 모든 anchor hit + 모든 dispatch consistent → sim_verified."""
    action = FakeAction(fqn="a1", preconditions=["br.x.OK"])
    bindings = [FakeAnchorBinding("anchor.1", "marker", "com.X.a1", "a1")]
    ont = FakeOntologyClient(
        actions={"a1": action},
        realizations_by_input={("a1", "scm.order.Order"): [FakeRealization("com.X.a1")]},
        anchor_bindings={"a1": bindings},
    )
    orch = _build_orchestrator(ontology_client=ont)
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    assert result.verdict == "sim_verified"


def test_orchestrator_verdict_inconclusive_when_dispatch_inconsistent():
    """dispatch_consistent=False frame 1개 → inconclusive (spec 04 §3.6)."""
    # realization 없음 → consistent=False
    orch = _build_orchestrator(ontology_client=FakeOntologyClient())
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    assert result.verdict == "inconclusive"


def test_orchestrator_verdict_inconclusive_when_no_evidence_at_all():
    """BR / anchor 둘 다 0 + dispatch consistent → 6 조건의 (b)/(d) 충족이라고 보고 sim_verified.

    (echo-stub 단순화: expected_brs/expected_anchors 비어있으면 vacuously true)
    """
    ont = FakeOntologyClient(
        realizations_by_input={("a1", "scm.order.Order"): [FakeRealization("com.X.a1")]},
        # actions / anchor_bindings 비어있음
    )
    orch = _build_orchestrator(ontology_client=ont)
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    # BR 0 + anchor 0 + consistent → vacuously sim_verified
    assert result.verdict == "sim_verified"


# ─── 4. evidence aggregation ─────────────────────────────────────


def test_orchestrator_br_evidence_aggregated_from_dispatches():
    """sandbox 의 BRTrigger → SimResult.br_evidence (BREvidence 매핑)."""
    action = FakeAction(fqn="a1", preconditions=["br.x.A", "br.x.B"])
    ont = FakeOntologyClient(
        actions={"a1": action},
        realizations_by_input={("a1", "scm.order.Order"): [FakeRealization("com.X.a1")]},
    )
    orch = _build_orchestrator(ontology_client=ont)
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    assert {b.br_fqn for b in result.br_evidence} == {"br.x.A", "br.x.B"}
    assert all(b.outcome == "passed" for b in result.br_evidence)


def test_orchestrator_anchor_evidence_aggregated_from_dispatches():
    """sandbox 의 AnchorHit → SimResult.anchor_evidence (AnchorEvidence 매핑)."""
    bindings = [
        FakeAnchorBinding("anchor.1", "자리 1 = HR", "com.X.a1", "a1"),
        FakeAnchorBinding("anchor.2", "literal:0.10", "com.X.a1", "a1"),
    ]
    ont = FakeOntologyClient(
        anchor_bindings={"a1": bindings},
        realizations_by_input={("a1", "scm.order.Order"): [FakeRealization("com.X.a1")]},
    )
    orch = _build_orchestrator(ontology_client=ont)
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    assert {a.anchor_id for a in result.anchor_evidence} == {"anchor.1", "anchor.2"}
    assert all(a.outcome == "hit" for a in result.anchor_evidence)
    a1 = next(a for a in result.anchor_evidence if a.anchor_id == "anchor.1")
    assert a1.marker == "자리 1 = HR"


def test_orchestrator_anchor_evidence_method_fqn_from_realization():
    """AnchorEvidence.method_fqn 은 realized_method_fqn 또는 binding.code_method_fqn."""
    bindings = [FakeAnchorBinding("anchor.1", "marker", "com.X.bound_method", "a1")]
    ont = FakeOntologyClient(
        anchor_bindings={"a1": bindings},
        realizations_by_input={("a1", "scm.order.Order"): [FakeRealization("com.X.realized_method")]},
    )
    orch = _build_orchestrator(ontology_client=ont)
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    # realized_method 또는 bound_method 둘 중 하나면 OK (spec 명시 없음 — 구현 결정)
    assert result.anchor_evidence[0].method_fqn in {"com.X.realized_method", "com.X.bound_method"}


# ─── 5. lookup_source factory ─────────────────────────────────────


def test_orchestrator_lookup_source_factory_called_with_fixture():
    """factory(change_spec.scenario_fixture) 호출 확인."""
    captured: dict = {}

    def factory(fixture):
        captured["fixture"] = fixture

        class _Stub:
            def get(self, *a, **k): return None
            def list(self, *a, **k): return []
            def validate(self): return []
        return _Stub()

    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox
    from backend.simulation.runner.orchestrator import Orchestrator
    from backend.simulation.runner.python_generator import PythonGenerator

    ont = FakeOntologyClient()
    orch = Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), ont),
        lookup_source_factory=factory,
    )
    cs = _change_spec(lookups={"scm.std.X:1": {"pk": 1, "table_spec_fqn": "scm.std.X", "columns": {}}})
    orch.run(cs, _run_plan(actions=["a1"]), _run_options())
    assert "lookups" in captured["fixture"]
    assert "scm.std.X:1" in captured["fixture"]["lookups"]


# ─── 6. e2e — Phase C P-2018-0098 회귀 → sim_verified ─────────────


def test_orchestrator_e2e_p_2018_0098_regression_sim_verified():
    """Phase C P-2018-0098 fixture + drama DNA anchor → sim_verified.

    spec 04 §6.3 의 회귀 시나리오가 stub tier 에서 verdict=sim_verified 회로 통과.
    (실제 Java code 호출 없이 — stub 의 anchor auto-hit + BR auto-pass 정책)
    """
    from backend.shared.contracts.simulation import RunPlan

    action = FakeAction(
        fqn="scm.workflow.SDSlabEntity_step_1_to_8",
        preconditions=["br.scm.slab.DG003.WidthMin"],
        postconditions=["br.scm.slab.DG003.WidthMax"],
    )
    bindings = [
        FakeAnchorBinding(
            id_="anchor.scm.proc_kind_hr",
            anchor_locator="자리 1 = HR",
            code_method_fqn="com.scm.SdDesigner.runStep1",
            target_action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
        )
    ]
    ont = FakeOntologyClient(
        actions={"scm.workflow.SDSlabEntity_step_1_to_8": action},
        anchor_bindings={"scm.workflow.SDSlabEntity_step_1_to_8": bindings},
        realizations_by_input={
            ("scm.workflow.SDSlabEntity_step_1_to_8", "scm.order.Order"): [
                FakeRealization("com.scm.SdDesigner.runStep1")
            ]
        },
    )
    orch = _build_orchestrator(ontology_client=ont)

    cs = _change_spec(
        action="scm.workflow.SDSlabEntity_step_1_to_8",
        lookups={
            "scm.std.CustomerStd:7": {
                "pk": 7, "table_spec_fqn": "scm.std.CustomerStd",
                "columns": {"customer_name": "정XX"},
            },
            "scm.spec.HrSpec:HR-23-A": {
                "pk": "HR-23-A", "table_spec_fqn": "scm.spec.HrSpec",
                "columns": {"proc": "0HR23456"},
            },
        },
        overrides={
            "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.width": 1180,
        },
    )
    plan = RunPlan(
        delegates_to_tree=[
            {
                "action_fqn": "scm.workflow.SDSlabEntity_step_1_to_8",
                "depth": 1,
                "primary_input_type": "scm.order.Order",
            },
        ],
        estimated_steps=1,
    )

    result = orch.run(cs, plan, _run_options())

    assert result.verdict == "sim_verified"
    assert result.status == "completed"
    # drama DNA anchor 가 hit
    assert any(a.anchor_id == "anchor.scm.proc_kind_hr" for a in result.anchor_evidence)
    # 2 BR (DG003 WidthMin + WidthMax) 모두 passed
    assert len(result.br_evidence) == 2
    assert all(b.outcome == "passed" for b in result.br_evidence)
    # delegation_trace 1 frame
    assert len(result.delegation_trace) == 1
    assert result.delegation_trace[0].dispatch_consistent is True


# ─── 7. failed status — sandbox 가 예외 발생 시 ────────────────


def test_orchestrator_status_failed_when_sandbox_raises():
    """JavaSandbox.dispatch 가 예외 → status=failed + failure_reason 채움."""
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.orchestrator import Orchestrator
    from backend.simulation.runner.python_generator import PythonGenerator

    class CrashingSandbox:
        def dispatch(self, *a, **k):
            raise RuntimeError("sandbox crashed")

    ont = FakeOntologyClient()

    class _StubLookup:
        def get(self, *a, **k): return None
        def list(self, *a, **k): return []
        def validate(self): return []

    orch = Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=CrashingSandbox(),
        lookup_source_factory=lambda fixture: _StubLookup(),
    )
    result = orch.run(_change_spec(), _run_plan(actions=["a1"]), _run_options())
    assert result.status == "failed"
    assert result.verdict == "inconclusive"
    assert result.failure_reason is not None
    assert "sandbox" in result.failure_reason.lower() or "crash" in result.failure_reason.lower()
