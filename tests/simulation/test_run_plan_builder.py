"""RunPlanBuilder (modeling facade 기반) — ChangeSpec.action_fqn → RunPlan.

spec 05 §1.2 의 RunPlan 빌드 알고리즘:
- delegates_to_tree : root action → BFS recursive on sub_actions
- expected_brs.direct     : root.preconditions + postconditions
- expected_brs.transitive : sub actions' preconditions+postconditions (- direct)
- expected_anchors        : ⋃ get_anchor_bindings_for_action(fqn).map(.id)
- estimated_steps         : frame 수
- primary_input_type      : action.realizations[0].applies_to_code_type_fqn
                            또는 params[0].object_ref_term

TDD — 본 테스트가 먼저, run_plan_builder.py 에 코드 추가 후 GREEN.
"""

from __future__ import annotations


# ─── Fake ontology client ───────────────────────────────────────────


class FakeRealization:
    def __init__(self, code_method_fqn, applies_to=None):
        self.code_method_fqn = code_method_fqn
        self.applies_to_code_type_fqn = applies_to


class FakeParam:
    def __init__(self, name, type_, object_ref_term=None):
        self.name = name
        self.type = type_
        self.object_ref_term = object_ref_term


class FakeAction:
    def __init__(self, fqn, sub_actions=None, preconditions=None, postconditions=None,
                 params=None, realizations=None):
        self.fqn = fqn
        self.sub_actions = sub_actions or []
        self.preconditions = preconditions or []
        self.postconditions = postconditions or []
        self.params = params or []
        self.realizations = realizations or []


class FakeAnchorBinding:
    def __init__(self, id_):
        self.id = id_


class FakeOntologyClient:
    def __init__(self, *, actions=None, anchor_bindings=None):
        self._actions = actions or {}
        self._bindings = anchor_bindings or {}

    def get_action(self, fqn):
        return self._actions.get(fqn)

    def get_anchor_bindings_for_action(self, action_fqn):
        return list(self._bindings.get(action_fqn, []))

    def get_realizations_for_input_type(self, action_fqn, code_type_fqn):
        action = self._actions.get(action_fqn)
        if action is None:
            return []
        return [r for r in action.realizations
                if r.applies_to_code_type_fqn in (None, code_type_fqn)]

    def list_code_types(self, role=None):
        return []


# ─── 1. 단일 action (sub_actions 없음) ─────────────────────────────


def test_build_returns_run_plan_with_single_frame():
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder
    from backend.shared.contracts.simulation import RunPlan

    ont = FakeOntologyClient(actions={
        "action.scm.demo": FakeAction("action.scm.demo"),
    })
    plan = RunPlanBuilder(ont).build("action.scm.demo")
    assert isinstance(plan, RunPlan)
    assert len(plan.delegates_to_tree) == 1
    assert plan.delegates_to_tree[0]["action_fqn"] == "action.scm.demo"
    assert plan.delegates_to_tree[0]["depth"] == 0
    assert plan.estimated_steps == 1


def test_build_unknown_action_returns_empty_run_plan():
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    ont = FakeOntologyClient(actions={})
    plan = RunPlanBuilder(ont).build("action.unknown")
    # Action 미존재 — warnings 채움, delegates_to_tree 빈 리스트
    assert plan.delegates_to_tree == []
    assert any("not found" in w.lower() for w in plan.warnings)


# ─── 2. sub_actions BFS ────────────────────────────────────────────


def test_build_recurses_sub_actions_bfs():
    """root → child1, child2 → grandchild — BFS 순서로 frame depth 채움."""
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    ont = FakeOntologyClient(actions={
        "root": FakeAction("root", sub_actions=["c1", "c2"]),
        "c1":   FakeAction("c1", sub_actions=["gc1"]),
        "c2":   FakeAction("c2"),
        "gc1":  FakeAction("gc1"),
    })
    plan = RunPlanBuilder(ont).build("root")
    fqns = [f["action_fqn"] for f in plan.delegates_to_tree]
    depths = [f["depth"] for f in plan.delegates_to_tree]
    assert fqns == ["root", "c1", "c2", "gc1"]
    assert depths == [0, 1, 1, 2]
    assert plan.estimated_steps == 4


def test_build_handles_cycles():
    """순환 구조 — 같은 action 두번 방문 안 함."""
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    ont = FakeOntologyClient(actions={
        "a": FakeAction("a", sub_actions=["b"]),
        "b": FakeAction("b", sub_actions=["a"]),  # cycle
    })
    plan = RunPlanBuilder(ont).build("a")
    fqns = [f["action_fqn"] for f in plan.delegates_to_tree]
    assert fqns == ["a", "b"]


def test_build_respects_max_depth():
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    ont = FakeOntologyClient(actions={
        "a": FakeAction("a", sub_actions=["b"]),
        "b": FakeAction("b", sub_actions=["c"]),
        "c": FakeAction("c", sub_actions=["d"]),
        "d": FakeAction("d"),
    })
    plan = RunPlanBuilder(ont).build("a", max_depth=2)
    # depth 0 (a), 1 (b), 2 (c). d 는 depth=3 → max_depth 초과로 제외
    fqns = [f["action_fqn"] for f in plan.delegates_to_tree]
    assert fqns == ["a", "b", "c"]


# ─── 3. expected_brs ───────────────────────────────────────────────


def test_expected_brs_direct_from_root_pre_post_conditions():
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    ont = FakeOntologyClient(actions={
        "root": FakeAction(
            "root",
            preconditions=["br.x.A"],
            postconditions=["br.x.B"],
        ),
    })
    plan = RunPlanBuilder(ont).build("root")
    assert sorted(plan.expected_brs["direct"]) == ["br.x.A", "br.x.B"]
    assert plan.expected_brs.get("transitive", []) == []


def test_expected_brs_transitive_from_sub_actions_minus_direct():
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    ont = FakeOntologyClient(actions={
        "root": FakeAction("root", sub_actions=["c1"], preconditions=["br.x.A"]),
        "c1":   FakeAction("c1", preconditions=["br.x.B", "br.x.A"]),  # br.x.A duplicate
    })
    plan = RunPlanBuilder(ont).build("root")
    # direct: br.x.A
    assert plan.expected_brs["direct"] == ["br.x.A"]
    # transitive: br.x.B (br.x.A 는 direct 이므로 제외)
    assert plan.expected_brs["transitive"] == ["br.x.B"]


# ─── 4. expected_anchors ───────────────────────────────────────────


def test_expected_anchors_union_across_tree():
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    ont = FakeOntologyClient(
        actions={
            "root": FakeAction("root", sub_actions=["c1"]),
            "c1":   FakeAction("c1"),
        },
        anchor_bindings={
            "root": [FakeAnchorBinding("anchor.1"), FakeAnchorBinding("anchor.2")],
            "c1":   [FakeAnchorBinding("anchor.2"), FakeAnchorBinding("anchor.3")],  # dup anchor.2
        },
    )
    plan = RunPlanBuilder(ont).build("root")
    # 합집합 — anchor.1, anchor.2, anchor.3 (sorted)
    assert sorted(plan.expected_anchors) == ["anchor.1", "anchor.2", "anchor.3"]


# ─── 5. primary_input_type derivation ──────────────────────────────


def test_primary_input_type_from_first_realization():
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    ont = FakeOntologyClient(actions={
        "a": FakeAction("a", realizations=[
            FakeRealization("com.X.a", applies_to="com.X.OrderImpl"),
        ]),
    })
    plan = RunPlanBuilder(ont).build("a")
    frame = plan.delegates_to_tree[0]
    assert frame["primary_input_type"] == "com.X.OrderImpl"


def test_primary_input_type_from_first_object_ref_param_when_no_realizations():
    """realizations 가 비어있으면 params[0].object_ref_term 으로 fallback."""
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    ont = FakeOntologyClient(actions={
        "a": FakeAction("a", params=[
            FakeParam("order", "object_ref", object_ref_term="term.scm.order"),
        ]),
    })
    plan = RunPlanBuilder(ont).build("a")
    frame = plan.delegates_to_tree[0]
    assert frame["primary_input_type"] == "term.scm.order"


def test_primary_input_type_omitted_when_no_signal():
    """realizations / params 둘 다 없으면 primary_input_type 없음 (sandbox 가 fallback)."""
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    ont = FakeOntologyClient(actions={"a": FakeAction("a")})
    plan = RunPlanBuilder(ont).build("a")
    frame = plan.delegates_to_tree[0]
    assert frame.get("primary_input_type") is None


# ─── 6. graceful failure ──────────────────────────────────────────


def test_ontology_client_raise_recovery():
    """ontology_client 호출 중 예외 → warning 누적 + 빈 결과로 graceful."""
    from backend.simulation.runner.run_plan_builder import RunPlanBuilder

    class Crashing:
        def get_action(self, fqn):
            raise RuntimeError("ontology backend down")

        def get_anchor_bindings_for_action(self, fqn):
            return []

        def get_realizations_for_input_type(self, *a, **k):
            return []

        def list_code_types(self, role=None):
            return []

    plan = RunPlanBuilder(Crashing()).build("a")
    # Action 못 가져옴 → 빈 결과 + warning
    assert plan.delegates_to_tree == []
    assert any("ontology" in w.lower() for w in plan.warnings)
