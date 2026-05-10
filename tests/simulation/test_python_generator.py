"""PythonGenerator echo-stub (spec 05 §1.3 단순화) — RunPlan → GeneratedScript 검증.

echo-stub 합의 (첫 iteration):
- delegates_to_tree 를 flat 순차 dispatch loop 로 emit (loop / optional 무시 — 후속 3b-4)
- atomic_overrides 는 코드 헤더 docstring 으로 echo (적용은 orchestrator 가)
- import 화이트리스트 준수 (subprocess / os / pickle / eval / exec 금지)
- source_code 는 ast.parse 통과 (compile 가능)

TDD — 본 테스트가 먼저, python_generator.py 에 코드 추가 후 GREEN.
"""

from __future__ import annotations

import ast


def _change_spec(action="action.scm.std.match", lookups=None):
    from backend.shared.contracts.simulation import ChangeSpec

    return ChangeSpec(
        action_fqn=action,
        atomic_overrides={},
        scenario_fixture={"lookups": lookups or {}},
    )


def _run_plan(actions=None, estimated_steps=None):
    from backend.shared.contracts.simulation import RunPlan

    edges = [{"action_fqn": a, "depth": i} for i, a in enumerate(actions or [], start=1)]
    return RunPlan(
        delegates_to_tree=edges,
        estimated_steps=estimated_steps if estimated_steps is not None else len(edges),
    )


# ─── 1. generate() 기본 형태 ────────────────────────────────────────


def test_generate_returns_generated_script():
    """generate(change_spec, run_plan) → GeneratedScript."""
    from backend.shared.contracts.simulation import GeneratedScript
    from backend.simulation.runner.python_generator import PythonGenerator

    gen = PythonGenerator()
    script = gen.generate(_change_spec(), _run_plan(actions=["action.scm.std.match"]))
    assert isinstance(script, GeneratedScript)


def test_generated_script_entrypoint_default_run():
    """spec 05 §1.2 — entrypoint 기본 'run'."""
    from backend.simulation.runner.python_generator import PythonGenerator

    gen = PythonGenerator()
    script = gen.generate(_change_spec(), _run_plan())
    assert script.entrypoint == "run"


# ─── 2. source_code 구조 ────────────────────────────────────────────


def test_generated_source_code_compiles():
    """source_code 는 ast.parse 통과 — Python 문법 정합."""
    from backend.simulation.runner.python_generator import PythonGenerator

    gen = PythonGenerator()
    script = gen.generate(_change_spec(), _run_plan(actions=["a1", "a2"]))
    # ast.parse 가 SyntaxError 없이 통과
    ast.parse(script.source_code)


def test_generated_source_code_contains_run_function():
    """`def run(` 정의 포함."""
    from backend.simulation.runner.python_generator import PythonGenerator

    gen = PythonGenerator()
    script = gen.generate(_change_spec(), _run_plan())
    assert "def run(" in script.source_code


def test_generated_source_code_contains_each_action_fqn():
    """각 delegation 의 action_fqn 이 source_code 에 등장 (dispatch call 로)."""
    from backend.simulation.runner.python_generator import PythonGenerator

    gen = PythonGenerator()
    actions = ["scm.workflow.SDSlabEntity_step_1_to_8", "action.scm.std.match"]
    script = gen.generate(_change_spec(), _run_plan(actions=actions))
    for a in actions:
        assert a in script.source_code


def test_empty_delegates_tree_produces_valid_minimal_script():
    """delegates_to_tree=[] → 여전히 ast.parse 통과 + run() 정의 존재."""
    from backend.simulation.runner.python_generator import PythonGenerator

    gen = PythonGenerator()
    script = gen.generate(_change_spec(), _run_plan(actions=[]))
    ast.parse(script.source_code)
    assert "def run(" in script.source_code


# ─── 3. 메타 — imports / java_dispatch_calls / fixture_keys / steps ─


def test_generated_imports_contain_simulation_contracts():
    """imports 에 spec 05 §1.4 의 화이트리스트 항목이 포함됨."""
    from backend.simulation.runner.python_generator import PythonGenerator

    gen = PythonGenerator()
    script = gen.generate(_change_spec(), _run_plan(actions=["a1"]))
    # 적어도 simulation contracts 는 import 에 등록 (DelegationTraceFrame 사용)
    assert any("backend.shared.contracts.simulation" in imp for imp in script.imports)


def test_generated_imports_no_blacklisted_modules():
    """spec 05 §1.4 — os / subprocess / socket / pickle 금지."""
    from backend.simulation.runner.python_generator import PythonGenerator

    blacklist = {"os", "subprocess", "socket", "pickle"}
    gen = PythonGenerator()
    script = gen.generate(_change_spec(), _run_plan(actions=["a1"]))

    # source_code 의 import 문 직접 검사 (ast 사용)
    tree = ast.parse(script.source_code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in blacklist
        elif isinstance(node, ast.ImportFrom):
            mod_root = (node.module or "").split(".")[0]
            assert mod_root not in blacklist


def test_java_dispatch_calls_extracted_from_delegates_tree():
    """spec 05 §1.2 — java_dispatch_calls 는 delegates_to_tree 의 action_fqn 합."""
    from backend.simulation.runner.python_generator import PythonGenerator

    gen = PythonGenerator()
    actions = ["a1", "a2", "a3"]
    script = gen.generate(_change_spec(), _run_plan(actions=actions))
    assert script.java_dispatch_calls == actions


def test_java_dispatch_calls_deduplicates_repeated_action_fqn():
    """같은 action_fqn 이 두 번 나와도 dedup (tree 의 sequential 호환)."""
    from backend.shared.contracts.simulation import RunPlan
    from backend.simulation.runner.python_generator import PythonGenerator

    plan = RunPlan(delegates_to_tree=[
        {"action_fqn": "a1", "depth": 1},
        {"action_fqn": "a2", "depth": 2},
        {"action_fqn": "a1", "depth": 3},  # 중복
    ])
    gen = PythonGenerator()
    script = gen.generate(_change_spec(), plan)
    # dedup 보장 + 첫 등장 순서 유지
    assert script.java_dispatch_calls == ["a1", "a2"]


def test_fixture_keys_used_extracted_from_scenario_fixture():
    """fixture_keys_used 는 ChangeSpec.scenario_fixture.lookups 의 key 목록."""
    from backend.simulation.runner.python_generator import PythonGenerator

    cs = _change_spec(lookups={
        "scm.std.CustomerStd:7": {"pk": 7, "table_spec_fqn": "scm.std.CustomerStd", "columns": {}},
        "scm.spec.HrSpec:HR-23-A": {"pk": "HR-23-A", "table_spec_fqn": "scm.spec.HrSpec", "columns": {}},
    })
    gen = PythonGenerator()
    script = gen.generate(cs, _run_plan(actions=["a1"]))
    assert sorted(script.fixture_keys_used) == [
        "scm.spec.HrSpec:HR-23-A",
        "scm.std.CustomerStd:7",
    ]


def test_estimated_steps_propagated_from_run_plan():
    """estimated_steps 는 RunPlan.estimated_steps 그대로."""
    from backend.simulation.runner.python_generator import PythonGenerator

    gen = PythonGenerator()
    plan = _run_plan(actions=["a1", "a2", "a3"], estimated_steps=21)
    script = gen.generate(_change_spec(), plan)
    assert script.estimated_steps == 21


# ─── 4. echo behavior — atomic_overrides 노출 ─────────────────────


def test_atomic_overrides_echoed_in_source_code_docstring():
    """ChangeSpec.atomic_overrides 의 path 가 source_code 에 흔적 (docstring 등)."""
    from backend.shared.contracts.simulation import ChangeSpec
    from backend.simulation.runner.python_generator import PythonGenerator

    cs = ChangeSpec(
        action_fqn="action.scm.std.match",
        atomic_overrides={
            "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.width": 1180,
        },
        scenario_fixture={},
    )
    gen = PythonGenerator()
    script = gen.generate(cs, _run_plan(actions=["a1"]))
    # echo: override path 가 source 에 (docstring or comment) 로 등장
    assert "scm.order.Order" in script.source_code or "atomic_overrides" in script.source_code


def test_action_fqn_in_source_code_header():
    """ChangeSpec.action_fqn 이 source_code 헤더 docstring 에."""
    from backend.simulation.runner.python_generator import PythonGenerator

    cs = _change_spec(action="scm.workflow.SDSlabEntity_step_1_to_8")
    gen = PythonGenerator()
    script = gen.generate(cs, _run_plan())
    assert "scm.workflow.SDSlabEntity_step_1_to_8" in script.source_code
