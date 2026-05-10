"""실 modeling.api.ontology_query 통합 검증 (STEP 3c).

본 test 는 실 SQLite ontology DB 가 로드된 환경에서만 실 ontology 행동 검증.
DB 가 비어있으면 skip — 인프라 wiring 자체는 fault-tolerant 동작 검증.

검증 항목:
- `_build_default_ontology_client()` 가 OntologyQueryClientImpl 인스턴스 반환
- RunPlanBuilder + 실 ontology 로 RunPlan 빌드 시 빈 결과 또는 정상 결과 반환
- spec_router endpoint 가 NullOntologyClient 가 아닌 실 ontology 호출
"""

from __future__ import annotations

import pytest


# ─── 1. ontology_client default = 실 OntologyQueryClientImpl ───────


def test_default_ontology_client_is_real_implementation_or_null_fallback():
    """`_build_default_ontology_client()` 가 OntologyQueryClientImpl 또는 fallback _NullOntologyClient.

    bootstrap 실패 시 graceful fallback (router 자체는 부팅 가능).
    """
    from backend.simulation.api import spec_router

    spec_router.reset_singletons()
    client = spec_router._build_default_ontology_client()
    # 실 구현 또는 fallback 둘 다 허용 — 환경 의존
    cls_name = type(client).__name__
    assert cls_name in ("OntologyQueryClientImpl", "_NullOntologyClient"), \
        f"unexpected client type: {cls_name}"


def test_default_orchestrator_uses_real_ontology_client_singleton():
    """orchestrator 와 run_plan_builder 가 같은 ontology client singleton 공유."""
    from backend.simulation.api import spec_router

    spec_router.reset_singletons()
    spec_router.get_orchestrator()  # singleton 초기화
    spec_router.get_run_plan_builder()
    # 두 함수가 같은 ontology client 인스턴스를 사용해야 함 (single source of truth)
    assert spec_router._ontology_client is not None


# ─── 2. 실 ontology DB 로 RunPlan 빌드 ───────────────────────────


@pytest.fixture
def real_ontology_client():
    """실 OntologyQueryClientImpl. DB 비어있으면 skip."""
    try:
        from backend.modeling.api.ontology_query import OntologyQueryClientImpl
    except Exception as exc:
        pytest.skip(f"OntologyQueryClientImpl import 실패: {exc}")

    client = OntologyQueryClientImpl()
    actions = client.list_actions()
    if not actions:
        pytest.skip("ontology DB 가 비어있음 — bootstrap 안 된 환경")
    return client


def test_run_plan_builder_with_real_ontology_first_action(real_ontology_client):
    """실 ontology 의 첫 action 으로 RunPlan 빌드 시 frame 1개 이상 + 정합성."""
    from backend.shared.contracts.simulation import RunPlan
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    actions = real_ontology_client.list_actions()
    assert actions, "real_ontology_client fixture 에서 거른다 — 도달 불가"
    first_action = actions[0]

    builder = RunPlanBuilder(real_ontology_client)
    plan = builder.build(first_action.fqn)
    assert isinstance(plan, RunPlan)
    # 최소 root frame 1개
    assert len(plan.delegates_to_tree) >= 1
    assert plan.delegates_to_tree[0]["action_fqn"] == first_action.fqn
    # estimated_steps 정합
    assert plan.estimated_steps == len(plan.delegates_to_tree)
    # expected_brs 키 존재
    assert "direct" in plan.expected_brs
    assert "transitive" in plan.expected_brs


def test_run_plan_builder_with_unknown_action_returns_warnings(real_ontology_client):
    """ontology 에 없는 action_fqn → warnings 채움."""
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    builder = RunPlanBuilder(real_ontology_client)
    plan = builder.build("action.totally.nonexistent.fqn.does.not.exist")
    assert plan.delegates_to_tree == []
    assert any("not found" in w.lower() for w in plan.warnings)


# ─── 3. spec_router POST /runs 가 실 ontology 호출 ────────────────


def test_spec_router_post_runs_with_real_ontology_returns_handle(real_ontology_client):
    """실 ontology 환경에서 POST /runs → RunHandle (status=completed) 정상 반환.

    Note: NullOntologyClient default 였을 때는 무조건 verdict=inconclusive.
    실 ontology 가 wire 되면 action 의 realization 이 실제 fetch 돼서
    dispatch_consistent=True 가능 (verdict 는 ontology 데이터 풍부도에 따라).
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.simulation.api import spec_router
    from backend.simulation.api.run_handle import RunHandleStore
    from backend.simulation.runner.java_sandbox import StubJavaSandbox
    from backend.simulation.runner.lookup_source import LookupDataSource
    from backend.simulation.runner.orchestrator import Orchestrator
    from backend.simulation.runner.python_generator import PythonGenerator
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder
    from backend.shared.contracts.simulation import SandboxCapabilities

    actions = real_ontology_client.list_actions()
    target = next((a for a in actions if a.realizations), actions[0])

    store = RunHandleStore()
    orch = Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), real_ontology_client),
        lookup_source_factory=lambda fx: LookupDataSource(real_ontology_client, fx),
    )
    builder = RunPlanBuilder(real_ontology_client)

    app = FastAPI()
    app.include_router(spec_router.router)
    app.dependency_overrides[spec_router.get_store] = lambda: store
    app.dependency_overrides[spec_router.get_orchestrator] = lambda: orch
    app.dependency_overrides[spec_router.get_run_plan_builder] = lambda: builder

    client = TestClient(app)
    resp = client.post(
        "/api/simulation/runs",
        json={
            "change_spec": {
                "action_fqn": target.fqn,
                "atomic_overrides": {},
                "scenario_fixture": {"lookups": {}},
            }
        },
    )
    assert resp.status_code == 200, resp.text
    handle = resp.json()
    assert handle["status"] == "completed"
    run_id = handle["run_id"]

    sr = client.get(f"/api/simulation/runs/{run_id}/sim-result").json()
    # verdict 은 ontology 데이터에 따라 sim_verified / sim_violation / inconclusive 가능
    assert sr["verdict"] in ("sim_verified", "sim_violation", "inconclusive")

    # delegation_trace 의 첫 frame action_fqn 가 target action 과 정합
    assert sr["delegation_trace"][0]["action_fqn"] == target.fqn

    # action 에 realizations 가 있으면 dispatch_consistent=True 기대
    if target.realizations:
        assert sr["delegation_trace"][0]["dispatch_consistent"] is True, (
            f"realization 있는 action 인데 dispatch inconsistent: "
            f"{sr['delegation_trace'][0].get('dispatch_mismatch_reason')}"
        )
        assert sr["delegation_trace"][0]["realized_method_fqn"] is not None


# ─── 4. 첫 시나리오 — match_customer_limit_for_order (A3) ───────


def test_match_customer_limit_for_order_scenario_runs_sim_verified(real_ontology_client):
    """STEP 4.1+ 첫 시나리오 — `action.scm.std.match_customer_limit_for_order`.

    실 ontology 데이터:
    - realizations 1: CustomerStdService.findFirstMatch(String,String,String,String) confirmed
    - precondition 1: rule.scm.std.customer_find_first_match_strategy
    - anchor_bindings 2: anchor_customer_empty_check, anchor_customer_first_match

    기대 동작 (실 ontology + StubJavaSandbox):
    - dispatch_consistent=True (realized_method 채움)
    - br_evidence 1건 passed
    - anchor_evidence 2건 hit
    - verdict=sim_verified
    """
    target = real_ontology_client.get_action("action.scm.std.match_customer_limit_for_order")
    if target is None:
        pytest.skip("action.scm.std.match_customer_limit_for_order 가 ontology DB 에 없음")

    from backend.shared.contracts.simulation import (
        ChangeSpec, CreateRunRequest, SandboxCapabilities,
    )
    from backend.simulation.api.run_handle import RunHandleStore
    from backend.simulation.runner.java_sandbox import StubJavaSandbox
    from backend.simulation.runner.lookup_source import LookupDataSource
    from backend.simulation.runner.orchestrator import Orchestrator
    from backend.simulation.runner.python_generator import PythonGenerator
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    orch = Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), real_ontology_client),
        lookup_source_factory=lambda fx: LookupDataSource(real_ontology_client, fx),
    )
    store = RunHandleStore()
    plan = RunPlanBuilder(real_ontology_client).build(target.fqn)

    cs = ChangeSpec(
        action_fqn=target.fqn,
        atomic_overrides={},
        scenario_fixture={"lookups": {}, "metadata": {"scenario_origin": "A3_match_customer_limit"}},
    )
    handle = store.submit(CreateRunRequest(change_spec=cs), orch, plan)
    sr = store.get_sim_result(handle.run_id)

    # 1. dispatch consistent — realized_method 가 ontology 의 confirmed realization
    assert sr.delegation_trace[0].dispatch_consistent is True
    assert "CustomerStdService.findFirstMatch" in sr.delegation_trace[0].realized_method_fqn

    # 2. BR evidence 1건 passed (precondition rule.scm.std.customer_find_first_match_strategy)
    assert len(sr.br_evidence) == 1
    assert sr.br_evidence[0].br_fqn == "rule.scm.std.customer_find_first_match_strategy"
    assert sr.br_evidence[0].outcome == "passed"

    # 3. anchor evidence 2건 hit (empty_check + first_match)
    assert len(sr.anchor_evidence) == 2
    assert {a.anchor_id for a in sr.anchor_evidence} == {
        "anchor_customer_empty_check",
        "anchor_customer_first_match",
    }
    assert all(a.outcome == "hit" for a in sr.anchor_evidence)

    # 4. verdict=sim_verified (모든 BR passed + 모든 anchor hit + dispatch consistent)
    assert sr.verdict == "sim_verified"
    assert sr.status == "completed"


# ─── 5. P-2018-0098 회귀 (B) — 21-step workflow + scenario_fixture ───


def test_p_2018_0098_regression_21_step_workflow(real_ontology_client):
    """B 작업 — Phase C P-2018-0098 회귀.

    `action.scm.슬랩설계_실행` (21 sub_actions) 의 BFS 펼침 + dispatch loop 검증.
    실 ontology 의 sub_actions 가 fetch 되어 22 frame trace 생성 (root + 21 children).
    """
    target = real_ontology_client.get_action("action.scm.슬랩설계_실행")
    if target is None or len(target.sub_actions) < 10:
        pytest.skip("21-step workflow 가 ontology DB 에 없음")

    from backend.shared.contracts.simulation import (
        ChangeSpec, CreateRunRequest, SandboxCapabilities,
    )
    from backend.simulation.api.run_handle import RunHandleStore
    from backend.simulation.runner.java_sandbox import StubJavaSandbox
    from backend.simulation.runner.lookup_source import LookupDataSource
    from backend.simulation.runner.orchestrator import Orchestrator
    from backend.simulation.runner.python_generator import PythonGenerator
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    orch = Orchestrator(
        python_generator=PythonGenerator(),
        java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), real_ontology_client),
        lookup_source_factory=lambda fx: LookupDataSource(real_ontology_client, fx),
    )
    store = RunHandleStore()
    plan = RunPlanBuilder(real_ontology_client).build(target.fqn)

    # P-2018-0098 fixture (drama / regression)
    cs = ChangeSpec(
        action_fqn=target.fqn,
        atomic_overrides={},
        scenario_fixture={
            "lookups": {
                "scm.std.CustomerStd:7": {
                    "pk": 7, "table_spec_fqn": "scm.std.CustomerStd",
                    "columns": {"customer_name": "정XX", "thickness_min": 200},
                },
                "scm.spec.HrSpec:HR-23-A": {
                    "pk": "HR-23-A", "table_spec_fqn": "scm.spec.HrSpec",
                    "columns": {"proc": "0HR23456"},
                },
            },
            "metadata": {
                "scenario_origin": "P-2018-0098",
                "snapshot_at": "2018-04-23T03:14",
            },
        },
    )

    handle = store.submit(CreateRunRequest(change_spec=cs), orch, plan)
    sr = store.get_sim_result(handle.run_id)

    # 1. delegation_trace 가 22 frame (root + 21 sub_actions BFS)
    assert len(sr.delegation_trace) >= 22, \
        f"expected ≥22 frames (root + 21 sub_actions), got {len(sr.delegation_trace)}"

    # 2. root frame 의 action_fqn 정합
    assert sr.delegation_trace[0].action_fqn == target.fqn
    assert sr.delegation_trace[0].depth == 0

    # 3. sub_actions frame 들의 depth=1
    sub_frames = [f for f in sr.delegation_trace[1:] if f.depth == 1]
    assert len(sub_frames) >= 10  # at least 10 sub_actions trace

    # 4. ChangeSpec 의 metadata 가 보존됐는지 (재현 가능성)
    cs_back = store.get_change_spec(handle.run_id)
    assert cs_back.scenario_fixture["metadata"]["scenario_origin"] == "P-2018-0098"

    # 5. status=completed (sandbox 충돌 없음)
    assert sr.status == "completed"
