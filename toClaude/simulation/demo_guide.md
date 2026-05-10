# Section 3 — Simulation Demo Guide

## 데모 시나리오

### S1. Ontology Graph 로드 확인
```bash
curl -sS http://localhost:8001/api/simulation/slab/ontology | head -c 300
# 기대: {"nodes":[...], "edges":[...]} 형식 JSON, HTTP 200
```

### S2. Mock Orders 로드 확인
```bash
curl -sS http://localhost:8001/api/simulation/slab/orders | head -c 300
# 기대: [{"order_id":"ORD-2024-0042", ...}, ...] 배열
```

### S3. Equipment Constraints 확인
```bash
curl -sS http://localhost:8001/api/simulation/slab/constraints
# 기대: {"target_width": {"min":900,"max":1570,...}, ...}
```

### S4. 프론트엔드 Slab Simulator 페이지
- http://localhost:3000 접속 후 상단 Simulation 탭 진입
- 상단 탭에 "soon" 배지가 없어야 함 (Wiki / Modeling / Simulation 모두 일반 탭)
- 페이지 로드 시 ontology 그래프가 렌더링되는지 확인
- 시나리오 A/B/C 실행 시 SSE 이벤트가 스트리밍되는지 확인

## Troubleshooting

### `/api/simulation/slab/ontology` 500 (ModuleNotFoundError)
- 원인: `venv/`에 `networkx` 미설치
- 해결: `venv/bin/pip install "networkx>=3.2,<4"`
- 재발 방지: `pyproject.toml`에 `networkx = "^3.2"` 선언 확인

### `/api/simulation/slab/run` scenario A/B에서 tool 호출 실패
- 원인: 동일 (networkx 필요). `find_edging_specs_for_order`, `find_orders_by_rolling_line`이 `build_mock_graph()` 내부에서 networkx 사용
- 해결: 동일

### Python 환경 혼동
- 프로젝트에 `venv/`와 `.venv/` 두 개 존재. 백엔드 서버는 `venv/`로 실행 중
- `ps -p <backend_pid> -o command`로 확인하거나 `lsof -p <pid> | grep site-packages`로 어느 환경인지 식별

---

## 2026-05-10 STEP 3a — ChangeSpec / SimResult schema 도입

### S5. ChangeSpec / SimResult Pydantic 모델 인스턴스화 검증

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
from backend.shared.contracts.simulation import ChangeSpec, SimResult, BREvidence

# spec 04 §6.3 P-2018-0098 회귀 시나리오
cs = ChangeSpec(
    action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
    atomic_overrides={
        "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.width": 1180,
        "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.thickness": 220,
    },
    scenario_fixture={
        "lookups": {"Customer:7": {"id": 7, "priority": 1}},
        "metadata": {"scenario_origin": "P-2018-0098", "snapshot_at": "2018-04-23T03:14"},
    },
)
print("ChangeSpec OK:", cs.action_fqn)
print("  scenario_origin:", cs.scenario_fixture["metadata"]["scenario_origin"])

# SimResult sim_violation (DG003 width min 위반)
sr = SimResult(
    run_id="run-demo",
    status="completed",
    verdict="sim_violation",
    br_evidence=[BREvidence(
        br_fqn="br.scm.slab.DG003.WidthMin",
        severity="error",
        enforcer_method_fqn=None,
        outcome="violated",
        violation_path="scm.slab.SlabResult.width",
        expected=">=1200",
        actual=1180,
        operational_history_refs=["P-2018-0098"],
    )],
    affected_design_gaps=[3],
    started_at="2026-05-10T12:00:00Z",
    completed_at="2026-05-10T12:00:02Z",
    duration_ms=2000,
    change_spec_ref="sha256:demo",
)
print("SimResult OK:", sr.verdict)
print("  br violation:", sr.br_evidence[0].br_fqn, "→", sr.br_evidence[0].actual)
print("  affected_gaps:", sr.affected_design_gaps)
PY
# 기대 출력:
# ChangeSpec OK: scm.workflow.SDSlabEntity_step_1_to_8
#   scenario_origin: P-2018-0098
# SimResult OK: sim_violation
#   br violation: br.scm.slab.DG003.WidthMin → 1180
#   affected_gaps: [3]
```

### S6. 19 schema test 통과 확인

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/test_changespec_schema.py -v
# 기대: 19 passed
```

### S7. 회귀 — 전체 simulation test suite

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/ -q
# 기대: 195 passed, 17 skipped (+ 3 failed for sample-repos/slab-design/ 부재 — STEP 3a 무관)
```

## Troubleshooting

### `Cannot resolve 'backend.shared.contracts.simulation'`
- 원인: PYTHONPATH 미설정
- 해결: `export PYTHONPATH=$(pwd)` (onTong 루트에서)

### `ValidationError: Extra inputs are not permitted`
- 원인: schema 외 필드 전달 (Pydantic `extra="forbid"`)
- 해결: spec 04 §1~§2 의 필드명 정확히 사용. typo 의심.

### tests/simulation/test_agent3.py / test_demo_e2e.py 3 failure
- 원인: `sample-repos/slab-design/` 부재 (commit `2a346e3` 옵션 A 정렬 영향)
- 해결: 통합 작업 시 `sample-repos/slab-design-real_v2/` 와 매핑 결정 후 fixture 경로 갱신

---

## 2026-05-10 STEP 3b-1 — Runner contract 모델 11종 + LookupDataSource

### S8. LookupDataSource 인스턴스화 + fixture_only 모드 검증

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
from backend.simulation.runner.lookup_source import LookupDataSource


# spec 05 §3.4 _derive_table_specs 가 기대하는 최소 인터페이스
class FakeField:
    def __init__(self, slot_name, atomic_fqn=None, is_pk=False, drama_dna_kind=None):
        self.slot_name, self.atomic_fqn, self.is_pk, self.drama_dna_kind = (
            slot_name, atomic_fqn, is_pk, drama_dna_kind
        )


class FakeCT:
    def __init__(self, fqn, fields, role="lookup_table"):
        self.fqn, self.fields, self.role = fqn, fields, role


class FakeOnt:
    def __init__(self, cts):
        self._cts = cts

    def list_code_types(self, role=None):
        return [c for c in self._cts if role is None or c.role == role]


customer = FakeCT("scm.std.CustomerStd", [
    FakeField("customer_no", atomic_fqn="scm.shared.atomic.customer_no", is_pk=True),
    FakeField("customer_name", atomic_fqn="scm.shared.atomic.customer_name", drama_dna_kind="alias"),
])

# spec 04 §6.3 P-2018-0098 회귀 fixture
fixture = {
    "lookups": {
        "scm.std.CustomerStd:7": {
            "pk": 7,
            "table_spec_fqn": "scm.std.CustomerStd",
            "columns": {"customer_name": "정XX"},
        }
    },
    "metadata": {"scenario_origin": "P-2018-0098"},
}
src = LookupDataSource(ontology_client=FakeOnt([customer]), fixture=fixture)

row = src.get("scm.std.CustomerStd", 7)
print("get OK:", row.pk, row.columns["customer_name"])
print("table_specs:", list(src.table_specs().keys()))
print("validate:", src.validate())  # []
print("metadata:", src.metadata())  # {'scenario_origin': 'P-2018-0098'}
PY
# 기대 출력:
# get OK: 7 정XX
# table_specs: ['scm.std.CustomerStd']
# validate: []
# metadata: {'scenario_origin': 'P-2018-0098'}
```

### S9. Runner 모델 + LookupDataSource 24 test 통과 확인

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest \
  tests/simulation/test_runner_models.py \
  tests/simulation/test_lookup_source.py -v
# 기대: 24 passed (15 + 9)
```

### S10. 회귀 — 전체 simulation test suite (3a + 3b-1 누적)

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/ -q
# 기대: 219 passed (이전 195 → +24), 17 skipped, 3 failed (sample-repos/slab-design 부재 — 무관)
```

## Troubleshooting (3b-1)

### `_type` 필드 ValidationError / Pydantic v2 underscore-private 경고
- 원인: Pydantic v2 가 `_type` 으로 시작하는 필드를 private 로 처리
- 해결: 모델은 `type_: str = Field(alias="_type")` 로 정의 + `populate_by_name=True`. 직렬화 시 `_type` 으로 노출됨
- 확인: `TypedValue(_type="atomic.foo", value=1).model_dump(by_alias=True)` → `{"_type": "atomic.foo", "value": 1}`

### `RunInputs.fixture` 타입 오류 (`arbitrary_types_allowed`)
- 원인: fixture 는 LookupDataSource 인스턴스 (Pydantic 외 타입). 직접 import 시 contracts ↔ runner 순환 발생
- 해결: `RunInputs.fixture: Optional[Any]` + `arbitrary_types_allowed=True`. 실제 타입은 duck-typed (sandbox 가 호출 시점에 .get/.list 사용)

### `_derive_table_specs` 가 빈 dict 반환
- 원인 1: `list_code_types(role='lookup_table')` 가 빈 리스트 — modeling 측에 lookup_table role 의 CodeType 없음
- 원인 2: 모든 CodeType 이 is_pk=True + atomic_fqn 매핑된 field 없음 (skip)
- 확인: warning log 에 "list_code_types(role='lookup_table') 호출 실패" 출력 여부 — 출력되면 ontology_client 가 graceful 실패 (modeling 미가용)
- 정상 동작: LookupDataSource 자체는 `_index_fixture` 로 row 인덱싱 계속 — get/list 는 작동, validate 만 unknown table_spec_fqn 경고

---

## 2026-05-10 STEP 3b-2 — JavaSandbox Protocol + StubJavaSandbox

### S11. StubJavaSandbox 합성 dispatch — sim_verified 가능한 경로

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
from backend.shared.contracts.simulation import (
    RunInputs, RunOptions, SandboxCapabilities, TypedValue,
)
from backend.simulation.runner.java_sandbox import StubJavaSandbox


# 가짜 ontology client (modeling 미가용 환경)
class FakeBinding:
    def __init__(self, id_, locator):
        self.id = id_
        self.anchor_locator = locator
        self.code_method_fqn = "com.scm.SdDesigner.runStep1"
        self.target_action_fqn = "scm.workflow.SDSlabEntity_step_1_to_8"
        self.target_slot = "param[0]"


class FakeAction:
    fqn = "scm.workflow.SDSlabEntity_step_1_to_8"
    preconditions = ["br.scm.slab.DG003.WidthMin"]
    postconditions = ["br.scm.slab.DG003.WidthMax"]


class FakeRealization:
    code_method_fqn = "com.scm.SdDesigner.runStep1"


class FakeOnt:
    def get_action(self, fqn):
        return FakeAction() if fqn == FakeAction.fqn else None

    def get_realizations_for_input_type(self, action_fqn, code_type_fqn):
        return [FakeRealization()] if code_type_fqn == "scm.order.Order" else []

    def get_anchor_bindings_for_action(self, action_fqn):
        return [FakeBinding("anchor.scm.proc_kind_hr", "자리 1 = HR")]


sandbox = StubJavaSandbox(
    capabilities=SandboxCapabilities(backend="stub"),
    ontology_client=FakeOnt(),
)
inputs = RunInputs(
    slots={"order": TypedValue(_type="scm.order.Order", value={"width": 1180})},
    overrides={},
    primary_input_slot="order",
)
result = sandbox.dispatch(
    action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
    inputs=inputs,
    run_options=RunOptions(sandbox_tier="stub_dispatch"),
)
print("realized:", result.realized_method_fqn)
print("consistent:", result.dispatch_consistent)
print("anchors:", [(a.anchor_id, a.marker) for a in result.captured_anchors])
print("brs:", [(b.br_fqn, b.outcome) for b in result.captured_brs])
print("jvm_log:", repr(result.jvm_log))
PY
# 기대 출력:
# realized: com.scm.SdDesigner.runStep1
# consistent: True
# anchors: [('anchor.scm.proc_kind_hr', '자리 1 = HR')]
# brs: [('br.scm.slab.DG003.WidthMin', 'passed'), ('br.scm.slab.DG003.WidthMax', 'passed')]
# jvm_log: '[stub mode]\n'
```

### S12. `backend != 'stub'` 거부 확인

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
from backend.shared.contracts.simulation import SandboxCapabilities
from backend.simulation.runner.java_sandbox import StubJavaSandbox


class FakeOnt:
    def get_action(self, fqn): return None
    def get_realizations_for_input_type(self, *a, **k): return []
    def get_anchor_bindings_for_action(self, fqn): return []


try:
    StubJavaSandbox(capabilities=SandboxCapabilities(backend="jvm_subprocess"), ontology_client=FakeOnt())
except ValueError as e:
    print("OK rejected:", e)
PY
# 기대 출력:
# OK rejected: StubJavaSandbox 는 SandboxCapabilities.backend='stub' 만 받음 — got 'jvm_subprocess'. ...
```

### S13. JavaSandbox 13 test + 회귀 (3a + 3b-1 + 3b-2 누적)

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/test_java_sandbox.py -v
# 기대: 13 passed

PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/ -q
# 기대: 232 passed (이전 219 → +13), 17 skipped, 3 failed (sample-repos/slab-design 부재 — 무관)
```

## Troubleshooting (3b-2)

### `ValueError: StubJavaSandbox 는 SandboxCapabilities.backend='stub' 만 받음`
- 원인: capabilities 의 backend 가 `jvm_subprocess` / `graalvm_polyglot` 으로 설정됨
- 해결: stub tier 사용 시 `SandboxCapabilities(backend="stub")` 명시. 운영 promote 결정에는 jvm_subprocess / graalvm tier 필요 (별도 클래스, 후속 step)

### `dispatch_consistent=False` + `mismatch_reason="primary_input slot not declared"`
- 원인: `RunInputs.primary_input_slot=None` 로 dispatch 호출 — pure constant Action 경로
- 해결: stub 의 첫 iter 는 conservative — primary 없으면 consistent=False. 진짜 pure constant 인 경우는 후속 iteration 에서 sandbox 가 type 검증 skip 정책으로 보강

### `captured_anchors` 가 빈 리스트
- 원인 1: `get_anchor_bindings_for_action(fqn)` 가 빈 리스트 — modeling 측에 해당 action 의 binding 없음
- 원인 2: ontology_client 호출 시 Exception → warning log 후 graceful 빈 결과
- 확인: `import logging; logging.basicConfig(level=logging.WARNING)` 후 dispatch 실행해 warning log 검사

### `captured_brs` 가 빈 리스트
- 원인 1: `get_action(fqn) → None` (modeling 미수록)
- 원인 2: Action.preconditions + postconditions 둘 다 비어있음
- 원인 3: ontology_client 호출 Exception (warning log 출력)

---

## 2026-05-10 STEP 3b-3 — PythonGenerator (echo-stub)

### S14. PythonGenerator 합성 + GeneratedScript 검증

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
from backend.shared.contracts.simulation import ChangeSpec, RunPlan
from backend.simulation.runner.python_generator import PythonGenerator

cs = ChangeSpec(
    action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
    atomic_overrides={"order.width": 1180},
    scenario_fixture={"lookups": {"scm.std.CustomerStd:7": {"pk": 7, "table_spec_fqn": "scm.std.CustomerStd", "columns": {}}}},
)
plan = RunPlan(
    delegates_to_tree=[
        {"action_fqn": "scm.workflow.SDSlabEntity_step_1_to_8", "depth": 1},
        {"action_fqn": "action.scm.std.match", "depth": 2},
    ],
    estimated_steps=2,
)
script = PythonGenerator().generate(cs, plan)
print("entrypoint:", script.entrypoint)
print("imports:", script.imports)
print("dispatch_calls:", script.java_dispatch_calls)
print("fixture_keys:", script.fixture_keys_used)
print("estimated_steps:", script.estimated_steps)
print("--- source_code (앞 600 chars) ---")
print(script.source_code[:600])
PY
# 기대 출력 (요약):
# entrypoint: run
# imports: ['from backend.shared.contracts.simulation import DelegationTraceFrame']
# dispatch_calls: ['scm.workflow.SDSlabEntity_step_1_to_8', 'action.scm.std.match']
# fixture_keys: ['scm.std.CustomerStd:7']
# estimated_steps: 2
```

### S15. PythonGenerator + StubJavaSandbox end-to-end exec

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
"""echo-stub 의 source_code 가 exec 후 run() 호출 가능한지 sanity."""
from backend.shared.contracts.simulation import (
    ChangeSpec, RunInputs, RunOptions, RunPlan, SandboxCapabilities, TypedValue,
)
from backend.simulation.runner.java_sandbox import StubJavaSandbox
from backend.simulation.runner.python_generator import PythonGenerator


class FakeOnt:
    def get_action(self, fqn): return None
    def get_realizations_for_input_type(self, *a, **k): return []
    def get_anchor_bindings_for_action(self, fqn): return []


cs = ChangeSpec(action_fqn="action.x", atomic_overrides={}, scenario_fixture={"lookups": {}})
plan = RunPlan(delegates_to_tree=[
    {"action_fqn": "a1", "depth": 1},
    {"action_fqn": "a2", "depth": 2},
])
script = PythonGenerator().generate(cs, plan)
ns = {}
exec(script.source_code, ns)
result = ns["run"](
    inputs=RunInputs(slots={"o": TypedValue(_type="scm.X", value={})}, primary_input_slot="o"),
    java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), FakeOnt()),
    lookup_source=None,
    run_options=RunOptions(sandbox_tier="stub_dispatch"),
)
print("trace 길이:", len(result["trace"]))
for f in result["trace"]:
    print(" -", f.action_fqn, f"depth={f.depth}", f"consistent={f.dispatch_consistent}")
PY
# 기대 출력:
# trace 길이: 2
#  - a1 depth=1 consistent=False  (FakeOnt 가 realization 없음)
#  - a2 depth=2 consistent=False
```

### S16. PythonGenerator 14 test + 회귀 (3a + 3b-1 + 3b-2 + 3b-3 누적)

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/test_python_generator.py -v
# 기대: 14 passed

PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/ -q
# 기대: 246 passed (이전 232 → +14), 17 skipped, 3 failed (sample-repos/slab-design 부재 — 무관)
```

## Troubleshooting (3b-3)

### 생성된 source_code 가 ast.parse 시 SyntaxError
- 원인: action_fqn 에 따옴표/줄바꿈 등 비정상 문자 포함 (정상이라면 일어나지 않음)
- 해결: `PythonGenerator._build_run_body` 가 `repr()` 사용하므로 일반 fqn 은 안전. 비정상 문자 발견 시 RunPlan 단계에서 sanitize

### `java_dispatch_calls` 에서 같은 fqn 중복 제거됨
- 의도된 동작 — spec 05 §1.2 에서 java_dispatch_calls 는 사전 검증용 fqn 합집합. dedup 시 첫 등장 순 유지
- 실제 dispatch 횟수는 `delegation_trace` 의 frame 수로 확인

### `atomic_overrides` 적용 안 됨
- 의도된 동작 — echo-stub 첫 iter 는 헤더 docstring 으로 echo 만. 실제 patching 은 orchestrator (3b-4) 가 spec 04 §1.2 4-rule algorithm 으로
- 검증: 생성된 source_code 에 override path 가 docstring 으로 등장하는지

### `loop_iterable` / `optional` 분기가 무시됨
- 의도된 동작 — echo-stub 첫 iter 는 sequential dispatch 만. is_in_loop / optional 플래그는 `delegation frame N` comment 에 depth 정보만 echo
- 후속: 3b-4 orchestrator 에서 atomic.facets 의 iter_source 마킹 + scenario.metadata 조건 평가 추가

---

## 2026-05-10 STEP 3b-4 — Orchestrator (running 단계 entry)

### S17. Orchestrator e2e — Phase C P-2018-0098 회귀 sim_verified 회로

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
"""Orchestrator + LookupDataSource + PythonGenerator + StubJavaSandbox 묶음 → SimResult."""
from backend.shared.contracts.simulation import (
    ChangeSpec, RunOptions, RunPlan, SandboxCapabilities,
)
from backend.simulation.runner.java_sandbox import StubJavaSandbox
from backend.simulation.runner.lookup_source import LookupDataSource
from backend.simulation.runner.orchestrator import Orchestrator
from backend.simulation.runner.python_generator import PythonGenerator


# Fake DTOs (modeling 미가용 환경)
class FakeRz:
    code_method_fqn = "com.scm.SdDesigner.runStep1"


class FakeAct:
    fqn = "scm.workflow.SDSlabEntity_step_1_to_8"
    preconditions = ["br.scm.slab.DG003.WidthMin"]
    postconditions = ["br.scm.slab.DG003.WidthMax"]


class FakeAB:
    id = "anchor.scm.proc_kind_hr"
    anchor_locator = "자리 1 = HR"
    code_method_fqn = "com.scm.SdDesigner.runStep1"
    target_action_fqn = "scm.workflow.SDSlabEntity_step_1_to_8"
    target_slot = "param[0]"


class FakeOnt:
    def get_action(self, fqn):
        return FakeAct() if fqn == FakeAct.fqn else None

    def get_realizations_for_input_type(self, action_fqn, code_type_fqn):
        if action_fqn == FakeAct.fqn and code_type_fqn == "scm.order.Order":
            return [FakeRz()]
        return []

    def get_anchor_bindings_for_action(self, action_fqn):
        return [FakeAB()] if action_fqn == FakeAct.fqn else []

    def list_code_types(self, role=None):
        return []


ont = FakeOnt()
orch = Orchestrator(
    python_generator=PythonGenerator(),
    java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), ont),
    lookup_source_factory=lambda fixture: LookupDataSource(ont, fixture),
)

cs = ChangeSpec(
    action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
    atomic_overrides={
        "scm.workflow.SDSlabEntity_step_1_to_8.inputs[0]<scm.order.Order>.width": 1180,
    },
    scenario_fixture={
        "lookups": {
            "scm.std.CustomerStd:7": {
                "pk": 7, "table_spec_fqn": "scm.std.CustomerStd",
                "columns": {"customer_name": "정XX"},
            },
            "scm.spec.HrSpec:HR-23-A": {
                "pk": "HR-23-A", "table_spec_fqn": "scm.spec.HrSpec",
                "columns": {"proc": "0HR23456"},
            },
        },
        "metadata": {"scenario_origin": "P-2018-0098"},
    },
)
plan = RunPlan(
    delegates_to_tree=[
        {"action_fqn": "scm.workflow.SDSlabEntity_step_1_to_8", "depth": 1, "primary_input_type": "scm.order.Order"},
    ],
    estimated_steps=1,
)

result = orch.run(cs, plan, RunOptions(sandbox_tier="stub_dispatch"))
print("verdict :", result.verdict)
print("status  :", result.status)
print("run_id  :", result.run_id)
print("duration:", result.duration_ms, "ms")
print("trace   :", [(f.action_fqn, f.dispatch_consistent) for f in result.delegation_trace])
print("BR      :", [(b.br_fqn, b.outcome) for b in result.br_evidence])
print("anchor  :", [(a.anchor_id, a.outcome) for a in result.anchor_evidence])
print("ref     :", result.change_spec_ref)
PY
# 기대 출력 (요약):
# verdict : sim_verified
# status  : completed
# run_id  : run-... (12-hex)
# duration: ... ms
# trace   : [('scm.workflow.SDSlabEntity_step_1_to_8', True)]
# BR      : [('br.scm.slab.DG003.WidthMin', 'passed'), ('br.scm.slab.DG003.WidthMax', 'passed')]
# anchor  : [('anchor.scm.proc_kind_hr', 'hit')]
# ref     : sha256:...
```

### S18. inconclusive 회로 — dispatch 부정합 시

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
"""primary_input_type 매핑 안되는 경우 → dispatch_consistent=False → inconclusive."""
from backend.shared.contracts.simulation import (
    ChangeSpec, RunOptions, RunPlan, SandboxCapabilities,
)
from backend.simulation.runner.java_sandbox import StubJavaSandbox
from backend.simulation.runner.lookup_source import LookupDataSource
from backend.simulation.runner.orchestrator import Orchestrator
from backend.simulation.runner.python_generator import PythonGenerator


class FakeOnt:
    def get_action(self, fqn): return None
    def get_realizations_for_input_type(self, *a, **k): return []  # 항상 빈 리스트
    def get_anchor_bindings_for_action(self, fqn): return []
    def list_code_types(self, role=None): return []


ont = FakeOnt()
orch = Orchestrator(
    python_generator=PythonGenerator(),
    java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), ont),
    lookup_source_factory=lambda fixture: LookupDataSource(ont, fixture),
)
result = orch.run(
    ChangeSpec(action_fqn="a1", atomic_overrides={}, scenario_fixture={"lookups": {}}),
    RunPlan(delegates_to_tree=[{"action_fqn": "a1", "depth": 1, "primary_input_type": "scm.order.Order"}]),
    RunOptions(sandbox_tier="stub_dispatch"),
)
print("verdict:", result.verdict)
print("frame consistent:", result.delegation_trace[0].dispatch_consistent)
print("frame reason   :", result.delegation_trace[0].dispatch_mismatch_reason)
PY
# 기대 출력:
# verdict: inconclusive
# frame consistent: False
# frame reason   : no realization for input type 'scm.order.Order' on action 'a1'
```

### S19. Orchestrator 16 test + 회귀 (3a + 3b-1~3b-4 누적)

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/test_orchestrator.py -v
# 기대: 16 passed

PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/ -q
# 기대: 262 passed (이전 246 → +16), 17 skipped, 3 failed (sample-repos/slab-design 부재 — 무관)
```

## Troubleshooting (3b-4)

### `verdict=inconclusive` 인데 BR / anchor 모두 정상
- 원인 1: 어떤 frame 의 `dispatch_consistent=False` (spec 04 §3.2 (f) 미달)
- 원인 2: `delegates_to_tree[i].primary_input_type` 누락 → `_build_run_inputs` 가 primary_input_slot=None 으로 설정 → StubJavaSandbox 가 mismatch_reason="primary_input not declared" 반환
- 해결: edge 에 `"primary_input_type": "scm.order.Order"` 등 명시 (spec 05 §4.6 build_slots 알고리즘은 후속 iter)

### `status=failed` + `failure_reason="sandbox crashed on ..."`
- 원인: JavaSandbox.dispatch() 가 예외 발생 — fail_fast 정책 (echo-stub 첫 iter)
- 해결: sandbox 구현체 점검 / ontology_client 호출 graceful failure 확인 (StubJavaSandbox 는 이미 graceful, custom sandbox 는 예외 처리 추가 필요)
- 후속: spec 05 §4.8 의 `on_dispatch_error="continue"` 정책 도입 시 frame 의 error 필드만 채우고 다음 sub-action 진행

### `change_spec_ref` 가 다른 두 ChangeSpec 인데 같음 / 같은데 다름
- 의도된 동작 — `sha256:{16_hex}` 형식. canonical JSON (sort_keys=True, ensure_ascii=False) 의 sha256 16자 prefix
- 충돌 가능성: 16자 prefix 라 약 1/2^64 — 실용 충돌 위험 낮음. 후속에서 64자 full hash 로 확장 가능

### `br_evidence` 의 severity 가 모두 'info'
- 의도된 동작 — orchestrator 가 outcome=violated→error / 그 외→info 로 매핑 (echo-stub iter)
- 후속: ontology_client 의 BusinessRule.severity 직접 조회 보강

---

## 2026-05-10 STEP 3b-5 — RunHandle state machine + RunHandleStore

### S20. RunHandleStore + Orchestrator e2e — submit → completed/sim_verified

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
"""Phase C P-2018-0098 ChangeSpec → submit() → RunHandle.completed → SimResult.sim_verified."""
from backend.shared.contracts.simulation import (
    ChangeSpec, CreateRunRequest, RunOptions, RunPlan, SandboxCapabilities,
)
from backend.simulation.api.run_handle import RunHandleStore
from backend.simulation.runner.java_sandbox import StubJavaSandbox
from backend.simulation.runner.lookup_source import LookupDataSource
from backend.simulation.runner.orchestrator import Orchestrator
from backend.simulation.runner.python_generator import PythonGenerator


# (FakeOnt 정의 — S17 참조)
class FakeRz:
    code_method_fqn = "com.scm.SdDesigner.runStep1"


class FakeAct:
    fqn = "scm.workflow.SDSlabEntity_step_1_to_8"
    preconditions = ["br.scm.slab.DG003.WidthMin"]
    postconditions = ["br.scm.slab.DG003.WidthMax"]


class FakeAB:
    id = "anchor.scm.proc_kind_hr"
    anchor_locator = "자리 1 = HR"
    code_method_fqn = "com.scm.SdDesigner.runStep1"
    target_action_fqn = "scm.workflow.SDSlabEntity_step_1_to_8"
    target_slot = "param[0]"


class FakeOnt:
    def get_action(self, fqn): return FakeAct() if fqn == FakeAct.fqn else None
    def get_realizations_for_input_type(self, action_fqn, code_type_fqn):
        return [FakeRz()] if (action_fqn == FakeAct.fqn and code_type_fqn == "scm.order.Order") else []
    def get_anchor_bindings_for_action(self, action_fqn):
        return [FakeAB()] if action_fqn == FakeAct.fqn else []
    def list_code_types(self, role=None): return []


ont = FakeOnt()
orch = Orchestrator(
    python_generator=PythonGenerator(),
    java_sandbox=StubJavaSandbox(SandboxCapabilities(backend="stub"), ont),
    lookup_source_factory=lambda fixture: LookupDataSource(ont, fixture),
)
store = RunHandleStore()

req = CreateRunRequest(change_spec=ChangeSpec(
    action_fqn="scm.workflow.SDSlabEntity_step_1_to_8",
    atomic_overrides={},
    scenario_fixture={"lookups": {}, "metadata": {"scenario_origin": "P-2018-0098"}},
), requested_by="tester")
plan = RunPlan(delegates_to_tree=[
    {"action_fqn": FakeAct.fqn, "depth": 1, "primary_input_type": "scm.order.Order"},
])

handle = store.submit(req, orch, plan)
print("RunHandle :", handle.run_id, "status=", handle.status)
print("ChangeSpec:", store.get_change_spec(handle.run_id).action_fqn)
sr = store.get_sim_result(handle.run_id)
print("SimResult :", "verdict=", sr.verdict, "/ run_id=", sr.run_id)
print("List pending  :", len(store.list(status="pending")))
print("List completed:", len(store.list(status="completed")))
PY
# 기대 출력 (요약):
# RunHandle : run-... status= completed
# ChangeSpec: scm.workflow.SDSlabEntity_step_1_to_8
# SimResult : verdict= sim_verified / run_id= run-...
# List pending  : 0
# List completed: 1
```

### S21. 상태 전환 invalid 검출

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
"""terminal 상태에서 다른 상태로 못 가는지 검증."""
from backend.shared.contracts.simulation import ChangeSpec, CreateRunRequest
from backend.simulation.api.run_handle import RunHandleStore

store = RunHandleStore()
h = store.register(CreateRunRequest(change_spec=ChangeSpec(action_fqn="x")))
store.transition(h.run_id, "running")
store.transition(h.run_id, "completed")
try:
    store.transition(h.run_id, "running")
except ValueError as e:
    print("OK rejected:", e)

# pending 에서 직접 cancelled 는 허용
h2 = store.register(CreateRunRequest(change_spec=ChangeSpec(action_fqn="y")))
store.transition(h2.run_id, "cancelled")
print("pending → cancelled OK:", store.get(h2.run_id).status)
PY
# 기대 출력:
# OK rejected: invalid transition 'completed' → 'running' for run 'run-...'. Allowed: (terminal)
# pending → cancelled OK: cancelled
```

### S22. RunHandle 20 test + 회귀 (3a + 3b-1~3b-5 누적)

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/test_run_handle.py -v
# 기대: 20 passed

PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/ -q
# 기대: 282 passed (이전 262 → +20), 17 skipped, 3 failed (sample-repos 부재 — 무관)
```

## Troubleshooting (3b-5)

### `ValueError: invalid transition 'completed' → 'X'`
- 의도된 동작 — terminal 상태 (completed/failed/cancelled) 에서 다른 상태로 전이 거부
- 디버그: `_VALID_TRANSITIONS` dict 의 entry 확인
- 새 상태 추가 시: dict 에 forward edge + (필요 시) backward 도 추가

### `KeyError: run_id 'X' not registered`
- 원인: 등록 안 된 run_id 로 transition 호출
- 확인: `store.list()` 로 등록된 run_id 목록 확인. test 격리 (각 test 가 fresh store 사용) 보장

### submit 후 `get_sim_result` 가 None 반환
- 원인 1: orchestrator 가 예외 발생 → status=failed, sim_result 미저장
- 원인 2: status=cancelled (pending 에서 취소된 run)
- 확인: `store.get(run_id).status` 검사 — completed 만 sim_result 보관

### multi-thread 환경에서 race condition 의심
- 본 store 는 `threading.RLock` 보호 — 단일 process 다 thread 안전 (FastAPI worker)
- multi-process 환경 (gunicorn workers) 는 본 v1 에서 미지원 — 운영 v2 (Redis) 에서 보강

---

## 2026-05-10 STEP 3b-6 — spec 03 Run lifecycle FastAPI router (★ STEP 3.1 종결)

### S23. 서버 기동 + curl smoke (POST → GET 흐름 e2e)

```bash
# 백엔드 기동 (별 터미널 / background)
PYTHONPATH=$(pwd) ./venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8765

# POST /api/simulation/runs
RUN_ID=$(curl -sS -X POST http://127.0.0.1:8765/api/simulation/runs \
  -H "Content-Type: application/json" \
  -d '{"change_spec":{"action_fqn":"action.scm.demo","atomic_overrides":{},"scenario_fixture":{"lookups":{}}},"requested_by":"smoke"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['run_id'])")
echo "run_id: $RUN_ID"

# GET /api/simulation/runs/{run_id} (RunHandle polling)
curl -sS http://127.0.0.1:8765/api/simulation/runs/$RUN_ID | python3 -m json.tool
# 기대: {"run_id":"...","status":"completed","created_at":"...","plan":null}

# GET /api/simulation/runs/{run_id}/sim-result
curl -sS http://127.0.0.1:8765/api/simulation/runs/$RUN_ID/sim-result | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print('verdict:', d['verdict'], '/ status:', d['status'])"
# 기대: verdict: inconclusive / status: completed
# (NullOntologyClient 환경 — realization 없으니 dispatch_consistent=False → inconclusive. 정상)

# GET /api/simulation/runs/{run_id}/changespec
curl -sS http://127.0.0.1:8765/api/simulation/runs/$RUN_ID/changespec | \
  python3 -c "import sys, json; print('action_fqn:', json.load(sys.stdin)['action_fqn'])"
# 기대: action_fqn: action.scm.demo

# GET /api/simulation/runs (list)
curl -sS http://127.0.0.1:8765/api/simulation/runs | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print('list count:', len(d))"
# 기대: list count: 1+

# GET /api/simulation/runs?status=completed (filter)
curl -sS "http://127.0.0.1:8765/api/simulation/runs?status=completed" | \
  python3 -c "import sys, json; print('completed:', len(json.load(sys.stdin)))"

# 404 unknown
curl -sS -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8765/api/simulation/runs/run-nonexistent
# 기대: HTTP 404
```

### S24. spec_router 13 test + 회귀 (3a + 3b-1~3b-6 누적)

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/test_spec_router.py -v
# 기대: 13 passed

PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/ -q
# 기대: 295 passed (이전 282 → +13), 17 skipped, 3 failed (sample-repos 부재 — 무관)
```

### S25. main.py route 확인 (충돌 검출)

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -c "
from backend.main import app
seen = {}
for r in app.routes:
    p = getattr(r, 'path', '')
    if '/runs' in p:
        for m in sorted(getattr(r, 'methods', []) or []):
            key = (m, p)
            seen.setdefault(key, []).append(r.endpoint.__module__)
for (m, p), mods in sorted(seen.items()):
    marker = '⚠️' if len(mods) > 1 else '✓'
    print(f'{marker} {m:6s} {p}')
    for mod in mods:
        print(f'           {mod}')
"
# 기대: 모든 route 가 ✓ (단일 owner). spec_router 가 우선이라 GET /runs, GET /runs/{id} 는 spec_router 만.
```

## Troubleshooting (3b-6)

### POST /runs → 422 Validation Error
- 원인: `change_spec` 필드 누락 또는 잘못된 형태
- 해결: `{"change_spec": {"action_fqn": "...", "atomic_overrides": {}, "scenario_fixture": {"lookups": {}}}}` 형태 확인
- 디버그: response body 의 `detail` 필드 — Pydantic 가 어느 필드 missing 인지 알려줌

### GET /runs/{id} 가 다른 store 의 응답을 반환
- 원인: scenarios_router 의 옛 `/runs/{id}` 와 path 충돌
- 해결: main.py 에서 `app.include_router(spec_router)` 가 **`scenarios_router` 보다 먼저** 호출되는지 확인
- 검증: `app.routes` iteration 으로 path-method 별 owner module 확인 (S25)

### GET /runs/{id}/sim-result 가 404 — completed 인데도
- 원인: orchestrator 가 예외 발생 → status=failed (sim_result 미저장)
- 확인: `GET /runs/{id}` 의 `status` 필드 검사 — completed 만 sim_result 보관
- 디버그: 로그 / orchestrator 실행 직접 호출

### POST /runs 가 예상보다 느림 (sync 실행)
- 원인: echo-stub iter 는 sync orchestrator — request 가 SimResult 빌드까지 block
- 후속 보강: STEP 3b-7 (또는 운영 v2) 에서 asyncio.Queue / Redis-RQ 로 비동기화

### NullOntologyClient 라 `verdict=inconclusive` 만 나옴
- **STEP 3c (2026-05-10) 부터 해결** — default 가 실 `OntologyQueryClientImpl()` 사용. 1514 actions 로딩된 환경에선 dispatch_consistent=True 가능.
- 그래도 inconclusive 가 나오면: ontology DB 가 비었거나, 해당 action 이 realizations 0건 + sub_actions 도 0건 (workflow root 만 sub_actions 있는 경우 등)

---

## 2026-05-10 STEP 3c — Section 3 ↔ Section 2 ontology 실데이터 통합

### S26. 실 ontology + RunPlanBuilder e2e

```bash
# 백엔드 기동 후
ACTION_FQN=$(PYTHONPATH=$(pwd) ./venv/bin/python -c "
from backend.modeling.api.ontology_query import OntologyQueryClientImpl
ont = OntologyQueryClientImpl()
for a in ont.list_actions():
    if a.realizations:
        print(a.fqn); break
")
echo "target: $ACTION_FQN"

RUN_ID=$(curl -sS -X POST http://127.0.0.1:8001/api/simulation/runs \
  -H "Content-Type: application/json" \
  -d "{\"change_spec\":{\"action_fqn\":\"$ACTION_FQN\",\"atomic_overrides\":{},\"scenario_fixture\":{\"lookups\":{}}}}" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['run_id'])")

curl -sS http://127.0.0.1:8001/api/simulation/runs/$RUN_ID/sim-result | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('verdict:', d['verdict'])
print('frame[0].dispatch_consistent:', d['delegation_trace'][0]['dispatch_consistent'])
print('frame[0].realized_method_fqn:', d['delegation_trace'][0]['realized_method_fqn'])
"
# 기대 (실 ontology DB 환경):
# verdict: sim_verified
# frame[0].dispatch_consistent: True
# frame[0].realized_method_fqn: <실 Java method fqn>
```

### S27. 21-step workflow 회로

```bash
RUN_ID=$(curl -sS -X POST http://127.0.0.1:8001/api/simulation/runs \
  -H "Content-Type: application/json" \
  -d '{"change_spec":{"action_fqn":"action.scm.슬랩설계_실행","atomic_overrides":{},"scenario_fixture":{"lookups":{}}}}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['run_id'])")

curl -sS http://127.0.0.1:8001/api/simulation/runs/$RUN_ID/sim-result | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('frame count:', len(d['delegation_trace']))
print('anchor_evidence:', len(d['anchor_evidence']))
print('consistent count:', sum(1 for f in d['delegation_trace'] if f['dispatch_consistent']))
"
# 기대: 22 frames (root + 21 sub_actions), anchor 7+, consistent 21+
```

### S28. RunPlanBuilder 단독 검증

```bash
PYTHONPATH=$(pwd) ./venv/bin/python - <<'PY'
from backend.modeling.api.ontology_query import OntologyQueryClientImpl
from backend.simulation.runner.run_plan_builder import RunPlanBuilder

ont = OntologyQueryClientImpl()
builder = RunPlanBuilder(ont)
plan = builder.build("action.scm.슬랩설계_실행")
print("frames :", len(plan.delegates_to_tree))
print("expected_brs.direct    :", plan.expected_brs.get("direct", []))
print("expected_brs.transitive:", len(plan.expected_brs.get("transitive", [])), "건")
print("expected_anchors       :", len(plan.expected_anchors), "건")
print("warnings:", len(plan.warnings))
PY
```

### S29. STEP 3c test 회귀

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/test_run_plan_builder.py tests/simulation/test_ontology_integration.py -v
# 기대: 17 passed (12 + 5)

PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/ -q
# 기대: 314 passed (이전 295 → +19), 17 skipped, 3 failed (sample-repos — 무관)
```

## Troubleshooting (3c)

### `OntologyQueryClientImpl 인스턴스화 실패` warning log
- 원인: SQLite DB 파일 미존재 / 권한 문제 / modeling internal schema 호환성 문제
- 해결: backend/main.py 의 `bootstrap_database()` 호출 확인. 또는 ontology DB 가 없는 상태로도 동작 (NullOntologyClient fallback)
- 영향: 이 경우 verdict 가 무조건 inconclusive — STEP 3c 이전 동작과 동일

### POST /runs 가 여전히 verdict=inconclusive
- 원인 1: ontology DB 가 비어있음 → `list_actions()` 가 빈 리스트
- 원인 2: 해당 action 의 realizations 가 0건 + sub_actions 도 0건 (orphan action)
- 원인 3: workflow root action 자체는 realization 없음 (sub_actions 만) → root frame 만 inconsistent. sub-action 들은 consistent=True 가능
- 확인: GET /runs/{id}/sim-result 의 delegation_trace 검사 — 각 frame 의 dispatch_consistent / realized_method_fqn

### `_NullOntologyClient` 가 default 로 사용됨
- 원인: spec_router import 시점 또는 첫 dispatch 시 OntologyQueryClientImpl 인스턴스화 실패
- 해결: backend/main.py 의 init() 호출 순서 확인. uvicorn 로그의 `spec_router: OntologyQueryClientImpl wired` 메시지 검출
- 강제 리셋: `from backend.simulation.api.spec_router import reset_singletons; reset_singletons()` 후 재호출

### 21-step workflow 가 frame 수 적게 나옴
- 원인: `RunPlanBuilder.build(max_depth=10)` 의 max_depth 초과
- 해결: 현재 default 10. 더 깊은 tree 면 `RunPlanBuilder.build(action_fqn, max_depth=30)` 로 호출 시 깊이 확장
- 확인: plan.warnings 에 "max_depth=N 초과" 메시지 있는지
