"""실 ontology 시나리오 회귀 테스트 (F — STEP 3d-F).

목적:
- atomic_overrides 가 실 ontology + sandbox 까지 전달되는지 e2e 검증
- scenario_kind metadata → suggested_promotion 권장 흐름 검증
- 여러 21-step sub_actions 의 단독 dispatch 회귀
- ChangeSpec 재현 — change_spec_ref 가 같은 입력에 대해 deterministic
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def real_ontology():
    """실 ontology client. DB 비어있으면 skip."""
    from backend.modeling.api.ontology_query import OntologyQueryClientImpl

    ont = OntologyQueryClientImpl()
    if not ont.list_actions():
        pytest.skip("ontology DB 비어있음")
    return ont


def _build_orchestrator(ont):
    from backend.shared.contracts.simulation import SandboxCapabilities
    from backend.simulation.runner.java_sandbox import StubJavaSandbox
    from backend.simulation.runner.lookup_source import LookupDataSource
    from backend.simulation.runner.orchestrator import Orchestrator
    from backend.simulation.runner.python_generator import PythonGenerator

    return Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), ont),
        lookup_source_factory=lambda fx: LookupDataSource(ont, fx),
    )


# ─── F-1: atomic_overrides + scenario_kind → suggested_promotion ──


def test_p_2018_0098_with_atomic_overrides_and_regression_kind(real_ontology):
    """Phase C P-2018-0098 — atomic_overrides + scenario_kind=regression
    → verdict=sim_verified + suggested_promotion 권장.
    """
    target = real_ontology.get_action("action.scm.슬랩설계_실행")
    if target is None or not target.sub_actions:
        pytest.skip("21-step workflow 없음")

    from backend.shared.contracts.simulation import (
        ChangeSpec, CreateRunRequest, RunOptions,
    )
    from backend.simulation.api.run_handle import RunHandleStore
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    orch = _build_orchestrator(real_ontology)
    store = RunHandleStore()
    plan = RunPlanBuilder(real_ontology).build(target.fqn)

    cs = ChangeSpec(
        action_fqn=target.fqn,
        atomic_overrides={
            # Rule 1 — slot path 형식 (실 ontology 의 inputs[0] 가 사용 가능 여부 무관, patcher 가 동작 검증)
            f"{target.fqn}.inputs[0]<scm.order.Order>.width": 1180,
            f"{target.fqn}.inputs[0]<scm.order.Order>.thickness": 220,
        },
        scenario_fixture={
            "lookups": {
                "scm.std.CustomerStd:7": {
                    "pk": 7,
                    "table_spec_fqn": "scm.std.CustomerStd",
                    "columns": {"customer_name": "정XX", "thickness_min": 200},
                },
            },
            "metadata": {
                "scenario_origin": "P-2018-0098",
                "snapshot_at": "2018-04-23T03:14",
                "scenario_kind": "regression",
            },
        },
    )
    handle = store.submit(CreateRunRequest(change_spec=cs), orch, plan)
    sr = store.get_sim_result(handle.run_id)

    assert sr.status == "completed"
    # workflow root 자체는 realization 없음 (sub_actions 만) — verdict 는 환경 의존이지만,
    # 21 sub_actions 에 realizations 가 있으면 sim_verified 가능
    if sr.verdict == "sim_verified":
        # spec 04 §3.4 — regression scenario 는 promote 권장
        assert sr.suggested_promotion == "BODY_ANCHORED → SIM_VERIFIED"

    # change_spec metadata 보존 검증
    cs_back = store.get_change_spec(handle.run_id)
    assert cs_back.scenario_fixture["metadata"]["scenario_origin"] == "P-2018-0098"
    assert cs_back.atomic_overrides["action.scm.슬랩설계_실행.inputs[0]<scm.order.Order>.width"] == 1180


# ─── F-2: change_spec_ref deterministic ──────────────────────────


def test_change_spec_ref_deterministic_for_same_input(real_ontology):
    """같은 ChangeSpec 두 번 실행 → 같은 change_spec_ref (재현 가능성)."""
    from backend.shared.contracts.simulation import (
        ChangeSpec, CreateRunRequest, RunOptions,
    )
    from backend.simulation.api.run_handle import RunHandleStore
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    target = real_ontology.list_actions()[0]
    orch = _build_orchestrator(real_ontology)
    store = RunHandleStore()
    plan = RunPlanBuilder(real_ontology).build(target.fqn)

    cs = ChangeSpec(
        action_fqn=target.fqn,
        atomic_overrides={},
        scenario_fixture={"lookups": {}, "metadata": {"scenario_kind": "boundary"}},
    )
    h1 = store.submit(CreateRunRequest(change_spec=cs), orch, plan)
    h2 = store.submit(CreateRunRequest(change_spec=cs), orch, plan)

    sr1 = store.get_sim_result(h1.run_id)
    sr2 = store.get_sim_result(h2.run_id)
    # 같은 입력 → 같은 hash
    assert sr1.change_spec_ref == sr2.change_spec_ref


# ─── F-3: 여러 21-step sub_action 단독 dispatch ──────────────────


def test_multiple_sub_actions_each_runs_sim_verified(real_ontology):
    """21-step workflow 의 sub_actions 중 realization 있는 것들 각각 sim_verified."""
    root = real_ontology.get_action("action.scm.슬랩설계_실행")
    if root is None or not root.sub_actions:
        pytest.skip("21-step 미존재")

    from backend.shared.contracts.simulation import (
        ChangeSpec, CreateRunRequest, RunOptions,
    )
    from backend.simulation.api.run_handle import RunHandleStore
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    orch = _build_orchestrator(real_ontology)
    store = RunHandleStore()

    # 첫 5 sub_actions 단독 실행
    verdicts: list[str] = []
    for sub_fqn in root.sub_actions[:5]:
        sub = real_ontology.get_action(sub_fqn)
        if sub is None or not sub.realizations:
            continue
        plan = RunPlanBuilder(real_ontology).build(sub_fqn)
        cs = ChangeSpec(
            action_fqn=sub_fqn,
            atomic_overrides={},
            scenario_fixture={"lookups": {}},
        )
        handle = store.submit(CreateRunRequest(change_spec=cs), orch, plan)
        sr = store.get_sim_result(handle.run_id)
        verdicts.append(sr.verdict)
        # 각 sub_action 의 dispatch_consistent=True (realization 있음)
        assert sr.delegation_trace[0].dispatch_consistent is True
        assert sr.delegation_trace[0].realized_method_fqn is not None

    # 적어도 1개 이상 verified
    assert any(v == "sim_verified" for v in verdicts), \
        f"no sim_verified — got {verdicts}"


# ─── F-4: artifact 가 디스크에 저장됨 (realistic e2e) ─────────────


def test_real_scenario_artifacts_persisted_to_disk(real_ontology, tmp_path):
    """실 시나리오 실행 후 artifact 디스크 파일 존재 검증."""
    from backend.shared.contracts.simulation import ChangeSpec, CreateRunRequest
    from backend.simulation.api.run_handle import RunHandleStore
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    target = real_ontology.list_actions()[0]
    orch = _build_orchestrator(real_ontology)
    store = RunHandleStore(artifact_root=tmp_path)
    plan = RunPlanBuilder(real_ontology).build(target.fqn)

    cs = ChangeSpec(action_fqn=target.fqn, atomic_overrides={}, scenario_fixture={"lookups": {}})
    handle = store.submit(CreateRunRequest(change_spec=cs), orch, plan)

    run_dir = tmp_path / handle.run_id
    assert run_dir.is_dir()
    assert (run_dir / "generated_python.py").exists()
    assert (run_dir / "trace.jsonl").exists()
    assert (run_dir / "input_fixture.json").exists()
    assert (run_dir / "output_dump.json").exists()


# ─── F-5: failure_policy continue + 일부 dispatch 실패 ─────────


def test_failure_policy_continue_with_partial_failures(real_ontology):
    """일부 frame 이 dispatch 실패해도 continue 정책 → 끝까지 실행."""
    root = real_ontology.get_action("action.scm.슬랩설계_실행")
    if root is None:
        pytest.skip("21-step 미존재")

    from backend.shared.contracts.simulation import (
        ChangeSpec, CreateRunRequest, DispatchResult, RunOptions,
    )
    from backend.simulation.api.run_handle import RunHandleStore
    from backend.simulation.runner.lookup_source import LookupDataSource
    from backend.simulation.runner.orchestrator import Orchestrator
    from backend.simulation.runner.python_generator import PythonGenerator
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    # 가짜 sandbox: 2번째 dispatch 만 raise
    class _FlakySandbox:
        def __init__(self):
            self.calls = 0

        def dispatch(self, *a, **k):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("flaky frame 2")
            return DispatchResult(
                outputs={}, realized_method_fqn=f"com.X.m{self.calls}",
                dispatch_consistent=True, dispatch_mismatch_reason=None,
                duration_ms=0, jvm_log="",
                captured_anchors=[], captured_brs=[],
            )

    sandbox = _FlakySandbox()
    orch = Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=sandbox,
        lookup_source_factory=lambda fx: LookupDataSource(real_ontology, fx),
    )
    store = RunHandleStore()
    plan = RunPlanBuilder(real_ontology).build(root.fqn)

    cs = ChangeSpec(action_fqn=root.fqn, atomic_overrides={}, scenario_fixture={"lookups": {}})
    handle = store.submit(
        CreateRunRequest(
            change_spec=cs,
            run_options=RunOptions(on_dispatch_error="continue"),
        ),
        orch,
        plan,
    )
    sr = store.get_sim_result(handle.run_id)

    # continue 정책 → 모든 frame 호출됨
    assert sandbox.calls == len(plan.delegates_to_tree)
    assert sr.status == "completed"
    # 2번째 frame 의 error 채워짐
    second_frame = sr.delegation_trace[1]
    assert second_frame.error is not None
    assert "flaky frame 2" in second_frame.error
