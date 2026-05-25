# Section 3 — Simulation Demo Guide

## 데모 시나리오

### S-SPRINT1. sim_v2 직통 — cumulativeProductivity 12/12 PASS (2026-05-16)

전제: 백엔드 8001 기동, `data/slab-v2-handoff.db` 존재 (3.4MB).

**A. bridge 단위 검증 (pytest)**
```bash
venv/bin/python -m pytest tests/simulation/test_sim_v2_bridge.py -v
# 기대: 6 passed
```

**B. agent end-to-end (Python REPL)**
```python
import asyncio
from backend.section3.agents.sandbox_agent import SandboxAgent
from backend.section3.contracts import SandboxRequest

class _NoModeling:
    async def query(self, *a, **kw):
        return {"status": "error", "result": {"message": "no modeling"}}

agent = SandboxAgent.__new__(SandboxAgent)
agent.modeling = _NoModeling()
agent.name = "sandbox"

req = SandboxRequest(
    target_kind="method",  # contract literal 제약 — target_id 가 action FQN 이면 sim_v2 경로
    target_id="action.scm.product.cumulative_productivity",
)

async def main():
    async for ev in agent.run(req):
        print(ev.type, str(getattr(ev, "payload", ""))[:120])

asyncio.run(main())
```
**기대 출력**:
- `[simv2_fixtures] count=12, synthesizable=6, skipped=0`
- `[simv2_stubs] count=3, sample=['DEFAULT_PRODUCTIVITY', 'lookupOrDefault', 'SdConstants']`
- `[final] ok=True, summary='sim_v2 직통 — 12 fixture · PASS 12 · stubs 3'`

**Troubleshooting**:
- `code_methods.body_text 누락` → DB 가 v2 인지 확인 (`venv/bin/python -c "import sqlite3; print(sqlite3.connect('data/slab-v2-handoff.db').execute('SELECT COUNT(*) FROM code_methods').fetchone())"` → 0이 아니어야)
- `sim_v2 translator 실패` → tree-sitter-java 미설치 가능 (`pip install tree-sitter tree-sitter-java`)
- `W71 fixture 합성 실패` → action 의 params_json 이 모두 object_ref 인 경우 (현재 cumulativeProductivity 는 6 primitive 라 정상)

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

---

# STEP 3f — Differential 5 카테고리 + Ontology Evidence + 랜딩 페이지 (2026-05-10)

## 시나리오 1: Differential 5 카테고리 분류 (요구사항 1)

**의도**: Java↔Python 응답이 비교 어렵고 null 많은 문제 해결.

```bash
# differential 응답 안에 새 필드들이 들어있는지 확인
curl -X POST http://localhost:8000/api/simulation/runs \
  -H "Content-Type: application/json" \
  -d '{"change_spec": {"action_fqn": "action.scm.std.match_customer_limit_for_order", "atomic_overrides": {}, "scenario_fixture": {"lookups": {}}}}' \
  | jq -r '.run_id' | tee /tmp/run_id.txt

curl -s http://localhost:8000/api/simulation/runs/$(cat /tmp/run_id.txt)/differential \
  | jq '{summary, matched_count, mismatched_count, java_only_count, python_only_count, both_null_count}'
# 기대: "38 matched / 2 mismatched / ..." 형식 summary + 각 count 정수
```

**결과 해석**:
| 카테고리 | 의미 |
|---|---|
| matched | 두 값 같음 (numeric tolerance 포함) |
| mismatched | 양쪽 값 있는데 다름 |
| java_only | python 응답에서 None / 누락 |
| python_only | java 응답에서 None / 누락 |
| both_null | 양쪽 None — diff list 에서 자동 제외 (count 만) |

**normalize 응답 필드**: `java_payload_normalized` / `python_payload_normalized` — null/빈값 재귀 제거. UI 가 원본 vs 정리본 둘 다 노출 가능.

## 시나리오 2: Ontology Evidence — 4 evidence kind (요구사항 2)

**의도**: SimResult 가 ontology 기반임을 사용자가 명시적으로 느낄 수 있게.

```bash
# run 생성 후 ontology-evidence endpoint 조회
RUN_ID=$(cat /tmp/run_id.txt)
curl -s http://localhost:8000/api/simulation/runs/$RUN_ID/ontology-evidence | jq '{
  action_fqn,
  ontology_facade,
  ontology_transport,
  trace_count: (.traces | length),
  summary
}'
```

**기대 응답**:
```json
{
  "action_fqn": "action.scm.std.match_customer_limit_for_order",
  "ontology_facade": "backend.modeling.api.ontology_query.OntologyQueryClientImpl",
  "ontology_transport": "in-process facade (HTTP 우회)",
  "trace_count": 4,
  "summary": {"action": 1, "realized_method": 1, "br": 1, "anchor": 2}
}
```

**4 evidence kind**:
| kind | source | facade call |
|---|---|---|
| action | `Action (mapping_layer.schema.Action)` | `get_action(fqn)` |
| realized_method | `Realization` | `get_action(fqn).realizations` |
| br | `Action.preconditions / postconditions` | `get_action(fqn).preconditions/postconditions` |
| anchor | `AnchorBinding (mapping_layer.schema.AnchorBinding)` | `get_anchor_bindings_for_action(fqn)` |

각 trace 항목엔 `evidence_kind / evidence_id / ontology_source / ontology_facade_call / ontology_data / explanation` 6 필드.

## 시나리오 3: 랜딩 페이지 — Apple/Claude 스타일 (요구사항 3)

**의도**: 호기심 유발 + 스토리라인 + 가독성.

```bash
# 새 랜딩 페이지
open http://localhost:8000/section3.html
# 폰트: Apple SD Gothic Neo + SF Pro Text
# 컬러: Claude warm cream (#faf9f5) + accent orange (#d97757)
# 레이아웃: 상단 sticky nav + 6 chapter scroll
# 인터랙션: 8 reveal 블록 (호기심 유발 클릭)
```

**6 chapter 스토리라인**:
1. **CHAPTER 01 · 왜** — 정적 도구 한계 3가지
2. **CHAPTER 02 · 무엇을** — ChangeSpec → SimResult verdict
3. **CHAPTER 03 · 어떻게** — 5 컴포넌트 + ontology in-process facade
4. **CHAPTER 04 · 근거** — `/ontology-evidence` 사용법
5. **CHAPTER 05 · Java↔Python** — 5 카테고리 + null 해결
6. **CHAPTER 06 · 운영화** — 4 stats + 13 endpoints + FailurePolicy

**이전 버전 보존**: `frontend/public/section3.legacy.html` — 사용자 지시 "지우진말고".

## 회귀 테스트 (3f)

```bash
PYTHONPATH=$(pwd) ./venv/bin/python -m pytest \
  tests/simulation/test_differential_classification.py \
  tests/simulation/test_ontology_evidence.py -v
# 기대: 23 passed (16 + 7)

PYTHONPATH=$(pwd) ./venv/bin/python -m pytest tests/simulation/ -q
# 기대: 423 passed (이전 400 → +23), 17 skipped, 3 failed (sample-repos — 무관)
```

## Troubleshooting (3f)

### `/ontology-evidence` 가 404 반환
- 원인 1: 미완료 run (sim_result 없음) → register 만 하고 submit 안 함
- 원인 2: run_id 자체가 없음
- 확인: `GET /api/simulation/runs/{run_id}` 로 state 확인. `completed` 가 아니면 evidence 조회 불가

### evidence trace 가 비어있음 / `realized_method` 가 0건
- 원인: ontology DB 의 해당 action 에 `realizations` 가 0건 (orphan action)
- 확인: `OntologyQueryClientImpl().get_action(fqn).realizations` 직접 호출
- 해결: realization 이 있는 다른 action 으로 시도 (`action.scm.std.match_customer_limit_for_order` 권장)

### differential 응답에서 `summary` 필드가 없음
- 원인: 옛 cached differential 결과 — 3f 이전 데이터
- 해결: 새 run 으로 differential 재호출. 또는 `RunHandleStore` 재시작

---

## Chat 재설계 Phase 1 — multiturn endpoint 시연 (2026-05-17)

> 3 게이트 멀티턴 agent 인프라 연결 확인. Phase 1 은 *connectivity + persistence
> 시연* 만 — 실제 gate logic (LLM 호출, candidates 채움) 은 Phase 2.

### 시나리오 1 — 한국어 세션 시작 → confirm → replay

```bash
# 서버 시작
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001

# 1) 세션 시작 (한국어 query)
curl -s -X POST http://127.0.0.1:8001/api/section3/multiturn/start \
  -H "Content-Type: application/json" \
  -d '{"user_query":"엣징 사양 룩업 룰 시뮬","repo_id":"slab-design-real-v2"}' \
  | python3 -m json.tool
# → session_id, turn_no:1, GateTarget(intent="ambiguous", user_input provenance)

# 2) 카드 [확인] 버튼 응답
SID="<위 응답 session_id>"
curl -s -X POST "http://127.0.0.1:8001/api/section3/multiturn/confirm/${SID}/1" \
  -H "Content-Type: application/json" \
  -d '{"action":"confirm","user_response":{"selected_index":0}}'
# → {"ok": true, "next_gate_kind": null}

# 3) replay (decision_log hydrate)
curl -s "http://127.0.0.1:8001/api/section3/multiturn/session/${SID}" | python3 -m json.tool
# → session info + decisions[0] 에 user_response 병합된 상태
```

### 시나리오 2 — SSE snapshot stream (Phase 1 minimal)

```bash
curl -sN "http://127.0.0.1:8001/api/section3/multiturn/session/${SID}/stream"
# → event: snapshot
# → data: {"session_id":"...","status":"active","decisions":[...]}
# (한 번 emit 후 종료. Phase 2 에서 실시간 gate 진행 event 로 확장)
```

### 기대 동작 (Phase 1)
- `POST /respond/{sid}` → **501** (Phase 2 stub 의도된 동작)
- `GET /session/unknown` → **404**
- `POST /confirm/{sid}/999` → **404** (unknown turn)
- `POST /start` 에 `repo_id` 누락 → **422**

### 트러블슈팅

#### `import backend.main` 실패 — multiturn ORM 등록 안 됨
- 원인: `backend/main.py:285` 부근에서 `_section3_multiturn_orm` import 가 빠짐
- 확인: `grep section3_multiturn_orm backend/main.py`
- 해결: 누락 시 import 추가 + 서버 재시작

#### 한국어가 unicode escape 로 보임
- 정상. `payload_json` 직렬화 시 `ensure_ascii=False` 였어도 router 응답은 ascii 보존
- 클라이언트 (브라우저 / Python) 에서 자동 복원
- 확인: `python3 -c 'import json,sys;print(json.load(sys.stdin)["session"]["user_query"])'` 식으로 한글 출력 확인

#### `section3_decision_log` 테이블 없음
- 원인: `backend/main.py` 의 `_section3_multiturn_orm` import 가 `bootstrap_database()` 호출 *전* 에 와야
- 확인: `grep -B2 bootstrap_database backend/main.py` 로 import 순서 확인

---

## Chat 재설계 Phase 2 Gate I — LLM intent + 후보 채움 (2026-05-17)

> Phase 1 의 endpoint shape 위에 진짜 Gate I logic wire. `/start` 는 ambiguous stub
> 유지, `/respond` 가 turn 2 에서 실제 intent 분류 + sim_v2/ontology 후보 병합.

### 사전 요건
- `.env` 의 `OPENAI_API_KEY` 설정 (없으면 /respond 호출 시 OpenAI 인증 실패)
- 서버 기동: `set -a && source .env && set +a && uv run --no-sync uvicorn backend.main:app --host 127.0.0.1 --port 8001`

### 시나리오 — simulate intent (실데이터)

```bash
SID=$(curl -sS -X POST http://127.0.0.1:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"주문 검증 시뮬해줘","repo_id":"slab-design-real-v2"}' \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_id"])')

curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/respond/${SID}" \
  -H 'Content-Type: application/json' \
  -d '{"message":"주문 검증 시뮬해줘"}' \
  | python3 -m json.tool
```

기대:
- `turn_no: 2`
- `payload.intent: "simulate"` (LLM 분류)
- `payload.candidates`: 5개 (slab-design-real-v2 의 실데이터)
  - top: `정합성_검증` / `SdOrderValidator.validate(SDOrderEntity)` / score 10
- `payload.sources`: 3개 (llm_inference + ontology + sim_v2) — Q5 비전 surface

### 시나리오 — impact intent

```bash
SID=$(curl -sS -X POST http://127.0.0.1:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"cumulativeProductivity 바꾸면 영향?","repo_id":"slab-design-real-v2"}' \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_id"])')

curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/respond/${SID}" \
  -H 'Content-Type: application/json' \
  -d '{"message":"cumulativeProductivity 바꾸면 영향?"}' \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print("intent:",d["payload"]["intent"]);print("cand:",len(d["payload"]["candidates"]))'
```

기대: `intent: impact` · `cand: 1` (cumulativeProductivity)

### 기대 동작 (Phase 2 Gate I)
- `/respond` 의 turn 2 → Gate I real (200)
- `/respond` 의 turn 3+ → **501** ("Gate II/III 미구현")
- `/respond/{unknown_sid}` → **404**
- `/respond` 의 `message` 가 빈 문자열이면 → `session.user_query` 로 fallback

### 트러블슈팅

#### `/respond` 가 OpenAI 401 / 500 으로 실패
- 원인: `OPENAI_API_KEY` 누락 또는 만료
- 확인: `grep OPENAI_API_KEY .env` (값 있어야)
- 회피 (테스트만): pytest 는 stub classifier 로 동작 — `tests/simulation/test_multiturn_router.py` 참고

#### intent=ambiguous 만 나옴
- 가능: LLM 이 분류 실패 → ambiguous fallback (`classify_with_llm` 의 unknown intent 안전망)
- 확인: response 의 `sources[0].detail` 의 reasoning 문구 확인 (Korean OK)
- query 가 너무 모호하면 정상 (Q5 비전: "빠진 내용은 빠진대로")

#### 후보가 0개
- 가능: sim_v2 `find_action_candidates` 가 query 토큰을 ontology.db 에서 못 찾음
- 확인: `data/ontology.db` 의 actions 테이블에 데이터 있는지 (slab-design-real-v2 = 38 actions)
- ontology 후보가 항상 0인 것은 정상 — production `get_ontology_client()` 의 default 는 `SimV2BackedOntologyClient` (search 는 sim_v2 가 담당하므로 중복 회피)

---

## Chat 재설계 Phase 2 Gate II — Java + Python + Fixtures (2026-05-17)

> Gate I 의 후보를 사용자가 confirm 한 뒤 turn 3 에서 진짜 bundle 만듬: 실 Java body 추출 → W75 Python 변환 → entity schema (있으면) → W71 fixture 합성. 모두 한 GateBundle.

### 사전 요건
- Gate I 와 동일 — `.env` OPENAI_API_KEY 필요, port 8001 서버
- `data/ontology.db` 에 slab-design-real-v2 actions + body_text 있어야 (38 actions 권장)

### 풀 플로우 — simulate intent (Gate I → confirm → Gate II)

```bash
# turn 1 — start
SID=$(curl -sS -X POST http://127.0.0.1:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"주문 검증 시뮬해줘","repo_id":"slab-design-real-v2"}' \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_id"])')

# turn 2 — Gate I (intent + candidates)
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/respond/${SID}" \
  -H 'Content-Type: application/json' \
  -d '{"message":"주문 검증 시뮬해줘"}' \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print("intent:",d["payload"]["intent"]);print("top:",d["payload"]["candidates"][0]["label"])'

# turn 2 confirm — selected_index=0
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/confirm/${SID}/2" \
  -H 'Content-Type: application/json' \
  -d '{"action":"confirm","user_response":{"selected_index":0}}'

# turn 3 — Gate II (bundle)
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/respond/${SID}" \
  -H 'Content-Type: application/json' \
  -d '{"message":"이 bundle 로 진행"}' \
  | python3 -m json.tool
```

기대 (실데이터):
- `payload.kind: "bundle_prepared"`
- `payload.target.code_method_fqn: com.example...SdOrderValidator.validate(SDOrderEntity)`
- `payload.java_source`: 400+ chars (실 Java body, `ValidationResult`, `checkStockOrder` 등)
- `payload.python_source`: 400 chars (W75 idiom 변환)
- `payload.schema_summary.entity_name: ""` · `fields: []` — sec2 API 부재 (Q5 "빠진 대로")
- `payload.fixtures`: 1+ (W71 deterministic)
- `payload.confidence`: 0.85 안팎 (body+translate+fixtures 성공, schema 부재로 -0.15)
- `payload.sources`: 4개 (`['ontology', 'sim_v2', 'ontology', 'sim_v2']`)

### 기대 동작 (Phase 2 Gate II)
- turn 3 + simulate intent → Gate II real (200)
- turn 3 + impact intent → **501** ("Gate III impact 미구현") · Gate II skip
- turn 3 + ambiguous intent → **422** ("재분류 필요")
- turn 3 without confirm → **422** ("turn 2 가 confirm 되지 않음")
- turn 3 with `selected_index` 범위 밖 → **422**
- turn 4 → **501** (Gate III sim 미구현)

### 트러블슈팅

#### `java_source` 가 빈 문자열
- 원인: `sim_v2_bridge.load_body_text` 가 ontology.db 에서 못 찾음
- 확인: `sqlite3 data/ontology.db "SELECT fqn FROM code_methods WHERE repo_id='slab-design-real-v2' AND fqn LIKE '%validate%'"` — fqn 일치 여부
- 회피: target.code_method_fqn 의 시그니처 형식 차이 (parameter list 차이) 가능 — Gate I 의 candidates 가 ontology.db 에서 가져온 것과 동일한 fqn 이어야

#### `python_source` 가 빈 문자열인데 `java_source` 는 있음
- 원인: W75 translator 가 Java body 파싱 실패 또는 정의된 idiom 처리 못함
- 정상 동작 — Q5 비전 "빠진 내용은 빠진대로". confidence 낮춰 surface
- 확인: backend log 의 `translate 실패` 메시지

#### `fixtures: []` 인데 python_source 는 있음
- 원인: `sim_v2_bridge.load_action` 실패 또는 `synthesize_fixtures` 가 None
- 확인: action_id 가 `actions.fqn` 과 일치하는지. `sqlite3 data/ontology.db "SELECT fqn FROM actions WHERE repo_id=? AND fqn=?"`

---

## Chat 재설계 Phase 2 Gate III — Executed (sim + impact) (2026-05-17)

> Phase 2 마지막. simulate 흐름은 turn 4 에서 실행+invariant, impact 흐름은 turn 3 에서 caller_graph+진단. 두 분기 모두 production 진입. session.status="done" 갱신.

### 사전 요건
- 이전 Gate I/II 와 동일 — `.env` OPENAI_API_KEY, port 8001, `data/ontology.db` 시드

### 풀 플로우 — Simulate (turn 1 → 4)

```bash
SID=$(curl -sS -X POST http://127.0.0.1:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"주문 검증 시뮬해줘","repo_id":"slab-design-real-v2"}' \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_id"])')

# turn 2 — Gate I
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/respond/${SID}" \
  -H 'Content-Type: application/json' -d '{"message":"주문 검증 시뮬해줘"}' > /dev/null

# confirm
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/confirm/${SID}/2" \
  -H 'Content-Type: application/json' \
  -d '{"action":"confirm","user_response":{"selected_index":0}}'

# turn 3 — Gate II
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/respond/${SID}" \
  -H 'Content-Type: application/json' -d '{"message":"이 bundle"}' > /dev/null

# turn 4 — Gate III sim
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/respond/${SID}" \
  -H 'Content-Type: application/json' -d '{"message":"실행"}' \
  | python3 -m json.tool
```

기대 (turn 4):
- `payload.kind: "executed_simulation"`
- `payload.invariant_status`: clean / fail_* / error 중 하나
- `payload.results`: case 별 status (PASS/FAIL/ERROR/SKIPPED)
- `payload.sources: [{"source":"sim_v2",...}]`
- 세션 종료: `GET /session/{sid}` 의 `session.status = "done"`

### 풀 플로우 — Impact (turn 1 → 3)

```bash
SID=$(curl -sS -X POST http://127.0.0.1:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"cumulativeProductivity 바꾸면 영향?","repo_id":"slab-design-real-v2"}' \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_id"])')

curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/respond/${SID}" \
  -H 'Content-Type: application/json' \
  -d '{"message":"cumulativeProductivity 바꾸면 영향?"}' > /dev/null
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/confirm/${SID}/2" \
  -H 'Content-Type: application/json' \
  -d '{"action":"confirm","user_response":{"selected_index":0}}' > /dev/null

# turn 3 — Gate III impact (Gate II skip)
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/respond/${SID}" \
  -H 'Content-Type: application/json' -d '{"message":"검토"}' \
  | python3 -m json.tool
```

기대:
- `payload.kind: "executed_impact"`
- `payload.affected_methods`: caller_graph (현재 Phase 4 swap 전이라 빈 결과)
- `payload.sim_v2_findings`: Finding[] (info: "N/M fixtures pass · K stubs" 또는 warn/error)
- `payload.confidence`: 1.0 (diagnose 모두 PASS) ~ 0.2 (blocked)
- `payload.sources: [{"source":"ontology",...},{"source":"sim_v2",...}]`
- 세션 종료

### 기대 동작 (Phase 2 Gate III)
- simulate path turn 4 → executed_simulation real (200) → `session.status="done"`
- impact path turn 3 → executed_impact real (200) → `session.status="done"`
- session done 후 추가 /respond → **501** ("session 이미 완료")

### 트러블슈팅

#### `invariant_status: "error"` · 모든 case ERROR
- 원인: W74 typed-return stub 부족 → run_fixtures_in_process 가 외부 의존성 호출 실패
- 정상 동작 — Q5 비전 "빠진 대로". confidence 낮춰 surface
- 확인: backend log 의 `run_fixtures_in_process` 결과
- 해결: ontology.db 의 W74 stub 데이터 보충 (Phase 4 협업 #1)

#### `affected_methods: []` (impact 분기)
- 원인: `SimV2BackedOntologyClient.get_caller_graph` 가 빈 결과 반환 (의도된 Phase 1~3 동작)
- 확인: `payload.sources` 의 ontology entry 의 `confidence: 0.0` 표기
- 해결: Phase 4 의 `HTTPOntologyClient` wire 후 sec2 API 의 caller_graph 사용

#### impact 분기에서 quick_diagnose findings 가 모두 blocked
- 원인: `sim_v2_bridge.quick_diagnose_action` 의 W71→W74→W72 quick loop 중 한 단계 실패
- finding 의 `primary_failure` 메시지로 원인 추적: "body_text 없음" / "translate 실패" / "fixture 합성 실패"
- confidence 도 낮게 (0.2~0.4) — 사용자 측에서 신뢰도 판단 가능

---

## Chat 재설계 Phase 3 — Frontend MultiturnChat (2026-05-17)

> Phase 2 백엔드 위에 한국어 UI. `Section 3 → 멀티턴 (v2)` nav 진입.

### 사전 요건
- 백엔드 (port 8001) + `.env` OPENAI_API_KEY
- `npm run dev` 로 frontend (port 3000)

### 시연 시나리오 — Simulate (4 turn)

브라우저: `http://localhost:3000/?view=multiturn`

1. **빈 상태**: repo_id 기본 `slab-design-real-v2` + 4 예시 grid. "주문 검증 시뮬" 클릭 또는 직접 입력 → [시작]
2. **자동 turn 진행**: turn 1 (ambiguous stub) 은 hidden. 곧바로 LLM intent 분류 호출.
3. **GateTargetCard 출현** (turn 2):
   - intent 배지 = "시뮬레이션"
   - 5 candidates radio (top = 정합성_검증, "추천" 라벨)
   - [이걸로 진행] 클릭
4. **GateBundleCard 출현** (turn 3):
   - Python tab (default) → W75 변환된 코드
   - Java tab → 실 Java body
   - Fixtures tab → W71 fixture 표
   - Schema tab → "Q5 빠진 내용은 빠진대로" 안내 (entity_schema 부재)
   - confidence 0.85 표시
   - [실행 (Gate III)] 클릭
5. **GateExecutedSimulationCard 출현** (turn 4):
   - invariant 배지 (clean / fail_* / error)
   - PASS/FAIL/ERROR/SKIPPED count
   - case 결과 표
   - "✓ 세션 완료"

### 시연 시나리오 — Impact (3 turn)

1. "cumulativeProductivity 바꾸면 어디 영향?" 예시 클릭 → [시작]
2. **GateTargetCard** (turn 2): intent = "영향도 검토" 배지, 1 candidate
3. [이걸로 진행]
4. **GateExecutedImpactCard** (turn 3):
   - confidence 막대 (100%)
   - affected_methods: "Section 2 API 미연결" 안내 (caller_graph 부재)
   - findings: "12/12 fixtures pass · 3 stubs" (info)
   - "✓ 세션 완료"

### Provenance surface

모든 카드 footer 에 "근거" 라벨 + 색칠된 칩:
- 🔵 `ontology` (Section 2)
- 🟣 `sim_v2`
- 🟡 `LLM`
- ⚪ `user`

각 칩 hover → detail (e.g. `search_action_by_keyword(query='주문 검증 시뮬해줘', repo_id='slab-design-real-v2')`)

### 트러블슈팅 (Frontend)

#### `?view=multiturn` 진입 시 404 또는 다른 view 표시
- 원인: dev server 재기동 안 함 (Section3Section.tsx 변경 반영 안 됨)
- 해결: `npm run dev` 재시작 또는 hot reload 확인

#### 카드가 안 뜨고 "처리 중…" 만 계속
- 원인: backend /respond 가 OpenAI 호출 중 timeout (정상은 2~5초)
- 확인: backend log 의 `respond` 요청 진행 상황
- 백엔드 OPENAI_API_KEY 누락 시: error banner 에 "OpenAI" 관련 detail 표시

#### HTTP 422 "turn 2 가 confirm 되지 않음"
- 정상 메시지 — confirm 버튼 안 누르고 다음 단계 시도한 경우. UI 자동 진행이 정상이면 발생 안 함
- 발생하면: hook 의 sequence 버그. confirm + respond 연쇄가 깨졌는지 dev tools 확인

#### "Section 2 API 미연결" 박스가 항상 떠 있음
- 정상 — `SimV2BackedOntologyClient` 가 default. `get_entity_schema` / `get_caller_graph` 빈 결과 반환 (Q5 vision)
- 해결: Phase 4 의 `HybridOntologyClient` swap 후 Section 2 데이터 surface

---

## Chat 재설계 Phase 4 — HybridOntologyClient + state machine (2026-05-18)

> sec2 HTTP API 점진 swap + `confirm` 의 next_gate_kind explicit 계산.

### sec2 HTTP wire 활성화

`.env` 또는 export:
```bash
export ONTONG_SECTION2_API_URL=http://localhost:8001
# (또는 sec2 가 별도 호스트면 그쪽)
```

설정되면 `get_ontology_client()` 가 `HybridOntologyClient` 반환.
설정 안 되면 `SimV2BackedOntologyClient` (Phase 2~3 동작).

### 시연 — Hybrid 동작 확인

서버 기동 (`ONTONG_SECTION2_API_URL` 설정 후):
```bash
SID=$(curl -sS -X POST http://127.0.0.1:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"주문 검증 시뮬","repo_id":"slab-design-real-v2"}' \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_id"])')
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/respond/${SID}" \
  -H 'Content-Type: application/json' -d '{"message":"주문 검증 시뮬"}' \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print([s for s in d["payload"]["sources"] if s["source"]=="ontology"])'
```

sec2 가 응답하면 ontology Provenance confidence > 0, sec2 endpoint 없거나 unreachable 이면 0.0 + sim_v2 fallback 의 candidates 가 surface.

### 시연 — next_gate_kind state machine

```bash
# turn 2 confirm → next = bundle_prepared (simulate path)
curl -sS -X POST "http://127.0.0.1:8001/api/section3/multiturn/confirm/${SID}/2" \
  -H 'Content-Type: application/json' \
  -d '{"action":"confirm","user_response":{"selected_index":0}}'
# → {"ok":true,"next_gate_kind":"bundle_prepared"}

# impact intent 의 turn 2 confirm → next = executed_impact
# bundle_prepared (turn 3) confirm → next = executed_simulation
# retry → 해당 gate 재실행
```

### 트러블슈팅

#### `ONTONG_SECTION2_API_URL` 설정했는데 ontology Provenance confidence 가 항상 0
- 원인: sec2 API 가 endpoint 응답 안 함 (배포 안 됨 / URL 오타)
- 확인: 직접 호출 — `curl ${ONTONG_SECTION2_API_URL}/api/ontology/search?q=test&repo_id=x`
- 정상이면 200 + JSON 응답. 아니면 sec2 측 배포 상태 점검
- 회피: env 변수 제거 → `SimV2BackedOntologyClient` 로 자동 fallback

#### `next_gate_kind: null` 인데 turn 다음 단계 모름
- 원인: 의도된 동작 — ambiguous intent 또는 session 종료 후
- 확인: 직전 decision 의 payload.kind ("executed_simulation" / "executed_impact" → 종료)
- 또는 intent="ambiguous" → 재분류 필요 (다른 단어로 새 세션)

---

## Chat 재설계 Phase 5 — SSE 실시간 server-push (2026-05-18)

> polling 기반 UI 가 SSE subscribe 로 전환. 클라이언트가 mutation 후 별도 GET 안 해도 server 가 push.

### 동작

브라우저 진입 (`http://localhost:3000/?view=multiturn`) 후 세션 시작:
1. `useMultiturnSession` 이 자동 EventSource open (`/api/section3/multiturn/session/{sid}/stream`)
2. backend SSE 가 0.5초 폴 + 변경 시 `event: snapshot` emit
3. frontend 가 onmessage 마다 state.decisions / session.status 자동 갱신
4. session.status="done" 시 `event: done` → EventSource close (reconnect 안 함)
5. 30초 tick 소진 시 close → EventSource 가 자동 reconnect (long-lived 효과)

### SSE event 종류

| event | 의미 |
|---|---|
| `snapshot` | decisions/status 변경. data = SessionResponse-like |
| `done` | session 종료. close 후 reconnect 안 함 |
| `gone` | session 삭제됨 |

### 시연 (curl)

```bash
SID=$(curl -sS -X POST http://127.0.0.1:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"x","repo_id":"slab-design-real-v2"}' \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_id"])')

# active session → snapshot 즉시 emit, 그 후 30초까지 변경 monitoring
curl -sN --max-time 5 "http://127.0.0.1:8001/api/section3/multiturn/session/${SID}/stream"
```

### UI hint — next_gate_kind

`POST /confirm` 후 응답의 `next_gate_kind` 가 SessionHeader 에 `→ bundle_prepared` 같이 surface. session.status="done" 시 hint 숨김 (이미 종료).

### 트러블슈팅

#### EventSource 가 계속 재연결 (네트워크 탭 매 30초)
- 정상 동작 — 백엔드 SSE 의 30초 lifetime 패턴. 브라우저 EventSource 가 자동 reconnect
- 의도: long-lived 연결 + 짧은 keep-alive 사이클 (heartbeat 대체)

#### SSE 가 멈춰 보임 (snapshot 안 옴)
- 가능: session.status="done" 이미 도달 → SSE close (정상)
- 확인: `GET /api/section3/multiturn/session/{sid}` 의 session.status 확인

#### confirm 후 SessionHeader 의 `→ {nextGateKind}` 안 보임
- 원인: confirm 응답의 next_gate_kind 가 null (ambiguous intent / Gate III 후)
- 정상 — state machine 종료 의미

---

## Phase 6 — modeling ontology.db 시드 (2026-05-18)

> sec2 endpoint 본체 wire 가 빈 ontology.db + sec3 fallback 으로 작동했었음. seed script 실행 후 sec2 endpoint 가 실 데이터 surface → sec3 hybrid 본체 활용.

### 시드 실행

```bash
uv run python scripts/seed_modeling_from_sim_v2.py
```

slab-v2-handoff.db 의 12 테이블 (code_methods 985, call_sites 1290, actions 38, ...) → ontology.db INSERT OR IGNORE.

### 동작 차이

| 항목 | 시드 전 | 시드 후 |
|---|---|---|
| `GET /api/ontology/actions` | `[]` | 38 actions |
| `GET /api/ontology/code-methods/{fqn}/body` | 404 | body_text 431 chars |
| `GET /api/ontology/code-methods/{fqn}/callers` | `{"callers":[]}` | 1+ caller |
| Gate II `payload.confidence` | 0.85 (schema 부재) | 1.0 (sec2 schema surface) |
| Gate II Provenance ontology confidence | 1.0 (body) / 0.0 (schema) | 1.0 / 1.0 (양쪽 sec2 surface) |
| Gate III impact `affected_methods` | 0 | 1+ |

### 환경 변수 활성화

`ONTONG_SECTION2_API_URL=http://127.0.0.1:8001` 으로 backend 기동 시 sec3 가 HybridOntologyClient 사용 → sec2 endpoint 본체 호출.

```bash
ONTONG_SECTION2_API_URL=http://127.0.0.1:8001 \
  uv run uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

### 트러블슈팅

#### 시드 후에도 affected_methods 비어있음
- 가능: receiver type 부재로 매칭 실패 (특정 method)
- 확인: `sqlite3 data/ontology.db "SELECT * FROM call_sites WHERE callee_simple_name='<simpleName>' LIMIT 5"`
- best-effort fallback 으로 receiver 부재 시 simple_name 만 매칭 — 그래도 0 이면 정말 caller 없음

#### Gate II confidence 가 시드 전과 동일 (0.85)
- 가능: `ONTONG_SECTION2_API_URL` env 안 설정 → `SimV2BackedOntologyClient` 만 사용 (sec2 본체 wire 안 함)
- 확인: backend 시작 시 logs / env 확인. env 설정하면 confidence 1.0 surface

---

## Phase 7~10 — finalization (2026-05-18)

> "전부 진행해" 사용자 지시로 남은 4개 외부 의존 항목 모두 production 처리.

### Phase 7 — v1 chat deprecation

신/구 chat 진입점 비교:

| 항목 | v1 (deprecated) | v2 (권장) |
|---|---|---|
| URL | `/?view=bridge` | `/?view=multiturn` |
| Backend endpoint | `/api/section3/chat` (deprecation 헤더 포함) | `/api/section3/multiturn/*` (5 endpoint) |
| UI | `BridgeChatPanel` (amber 배너 + dismissible) | `MultiturnChat` |
| 멀티턴 | X (한 번에 1 question/response) | O (Gate I~III) |
| Provenance surface | 일부 | 4 source 전체 |

#### Deprecation 헤더 확인

```bash
curl -i -X POST http://127.0.0.1:8001/api/section3/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"x","history":[]}' | head -10
```

응답 헤더에 다음 4종 surface:
```
X-Deprecated: true
Warning: 299 - "Section 3 chat v1 is deprecated; migrate to /api/section3/multiturn/* (Phase 1~6 complete)"
X-Deprecation-Date: 2026-05-18
X-Replacement: /api/section3/multiturn/start
```

### Phase 8 — Idiom diffs surface

Gate II 결과의 GateBundleCard 에 "Idiom diff" 탭 신규. W75 가 다시 쓴 Java idiom 을 java→python 매핑 표로 보여줌:

```
idiom              Java                Python
String.length      o.length()          len(o)
List.isEmpty       items.isEmpty()     (not items)
Math.abs           Math.abs(x)         abs(x)
Optional.isPresent opt.isPresent()     (opt is not None)
```

상세는 W75 의 50+ idiom 카탈로그 자동 매칭.

#### 확인 방법
1. `/?view=multiturn` 진입 → "주문 검증" 등 자연어 입력
2. Gate I → 후보 선택 → confirm
3. Gate II 카드에서 "Idiom diff (N)" 탭 클릭
4. N=0 시: body 가 Java idiom 을 사용 안 함 (예: `getCmpCd` 같은 getter 만)

### Phase 9 — W74 typed-return stubs (Gate III sim ERROR 감소)

Gate III sim 실행 시 stub method 호출 결과가 String/int/BigDecimal/... 타입으로 자동 매핑됨. 결과:
- `FAIL_RETURN_TYPE` invariant 사례 감소
- `getCmpCd()` → `""` (Java String 매핑)
- `getCount()` → `0` (Java int)
- `getPrice()` → `Decimal("0")` (Java BigDecimal)

#### 동작 확인

```bash
uv run python -c "
import os
os.environ['ONTONG_DB_PATH'] = 'data/ontology.db'
from backend.modeling.persistence.database import get_engine, reset_engine_for_tests
from sqlalchemy.orm import Session
from backend.sim_v2.core.verification.sandbox_stubs import derive_method_return_defaults
reset_engine_for_tests()
with Session(get_engine()) as s:
    d = derive_method_return_defaults(s, 'slab-design-real')
print(f'{len(d)} method return defaults')
for k in sorted(list(d.keys())[:10]):
    print(f'  {k} -> {d[k]!r}')
"
```

기대 출력: 100+ method 별 typed default (`getCmpCd -> ''`, `getPrice -> Decimal('0')` 등).

### Phase 10 — Caller graph 정확도 (5단계 match_kind)

Gate III impact 의 affected_methods 표에 "match" + "신뢰" 컬럼 추가. caller 와 callee 의 매칭 강도를 5단계로 surface:

| match_kind | strength | 의미 |
|---|---|---|
| `receiver_exact` | 0.95 | callee_receiver_static_type 이 fqn 정확 일치 |
| `receiver_short` | 0.85 | callee_receiver_static_type 이 short name 일치 |
| `runtime_type` | 0.85 | possible_runtime_types 중 매칭 |
| `package_proximity` | 0.70 | parser 가 receiver 못 잡았고 caller/callee 같은 package |
| `name_only` | 0.50 | simple_name 만 일치 (best-effort, false positive 가능) |

#### min_strength 필터 사용

```bash
curl "http://127.0.0.1:8001/api/ontology/code-methods/example.slabdesign.facade.sd.rest.orders.SdOrderController.detail(String,String,String)/callers?min_strength=0.7"
```

응답에서 약한 신호 (name_only=0.5) 가 제거됨.

### 트러블슈팅

#### Idiom diff 탭이 항상 비어 있음
- 가능: body 가 단순 getter / setter 만 사용 (Java idiom 없음)
- 가능: translate 실패 (java_source 빈 문자열)
- 확인: Java 소스 탭에 body 가 있는지 + Python 탭에도 코드가 있는지

#### affected_methods 표가 모두 name_only 매치
- 가능: 시드 데이터의 call_sites 가 receiver type 부재 (parser 한계)
- 정상 — 현재 1290 row 가 모두 receiver 빈 상태. `min_strength=0.7` 로 필터링하면 package_proximity 만 남음

#### v1 chat 배너 닫고 싶음
- "닫기" 클릭 시 현재 세션에서만 숨김 (localStorage 미사용)
- 새로고침하면 다시 표시 — 의도적: deprecation 인지 유지 목적

---

## Phase 11.5 — Dashboard 정리 + repo 인식 (2026-05-18)

대시보드 절반 (Neo4j 노드/관계 카드, legacy 빠른진입, dev-only tip) 이 깨진 / 모순된 상태였음 — 전면 재작성. 이제 SQLite ontology.db 의 repo 별 실 데이터만 노출.

### API 검증

```bash
# 적재된 repo 별 카운트 8 종
curl -s "http://localhost:8001/api/section3/repos" | python3 -m json.tool
# 기대:
# {
#   "repos": [{"repo_id": "slab-design-real-v2",
#              "counts": {"actions": 130, "code_methods": 1081, "code_types": 150,
#                         "business_terms": 76, "business_rules": 17,
#                         "realizations": 135, "call_sites": 2298, "sessions": 66}}]
# }

# repo 필터된 multiturn 세션
curl -s "http://localhost:8001/api/section3/multiturn/sessions?repo_id=slab-design-real-v2&limit=3" | python3 -m json.tool
```

### UI 시연

1. http://localhost:3000/?view=dashboard 진입
2. **상단 Repo 칩** — 현재 `slab-design-real-v2` 1 개. 칩에 "1081m / 130a / 66s" 미니 요약. 다중 repo 적재 시 알파벳 정렬되어 모두 표시.
3. **8 카운트 카드** — 선택된 repo 의 실 데이터 (천단위 콤마 포맷). 색상 tone 8 종 (blue/emerald/cyan/pink/amber/violet/orange/slate).
4. **최근 세션 (repo 필터)** — header 우측에 selected repo_id 함께 표시. repo 칩 변경 시 자동 재로딩. 검색 input 은 200ms debounce.
5. 세션 클릭 → URL `?view=multiturn&sid=<UUID>` 로 이동 (Phase 11 그대로).

### 트러블슈팅

#### Repo 칩이 0 개로 뜸
- backend `/api/section3/repos` 가 200 + `{"repos": []}` 반환 시 — ontology.db 가 비어있음. modeling 측에서 repo import 후 재시도.
- 401/500 — backend 미기동 또는 ORM 마이그레이션 누락. `lsof -i :8001` 확인 + uvicorn 재기동.

#### Repo 칩은 있는데 모든 카드가 0
- `/repos` 결과 확인 후 0 이면 import 가 partial 한 상태. 보통 actions / code_methods 만 채워지고 business_terms 가 0 인 경우는 정상 (Section 2 후속 작업 필요).

#### 다른 repo 선택해도 세션 리스트가 안 바뀜
- 브라우저 캐시 — F5. 또는 backend `/multiturn/sessions?repo_id=<id>` curl 로 직접 확인.

## Phase 11 — Session History Browser (2026-05-18, Option B)

대시보드 가치 분석 (`toClaude/simulation/dashboard_value_analysis.html`) 의 권장 옵션 — 매몰돼 있던 `/session/{sid}/replay` 자산을 surface + 3 인 팀 운영 페인 (어제 그 분석 어디 갔지) 해결.

### 시연 흐름

#### 1. API 직접 검증

```bash
# 최근 세션 N 개 (latest first, turn_count + last_gate_kind 채워짐)
curl -s "http://localhost:8001/api/section3/multiturn/sessions?limit=5" | python3 -m json.tool

# user_query substring 검색 (한국어 URL-encode 필수)
curl -sG "http://localhost:8001/api/section3/multiturn/sessions" \
  --data-urlencode "search=주문" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['sessions']))"

# repo_id 필터
curl -s "http://localhost:8001/api/section3/multiturn/sessions?repo_id=slab-design-real-v2" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['sessions']))"
```

기대:
- 각 세션이 `{id, repo_id, status, user_query, created_at, last_activity_at, turn_count, last_gate_kind}` 를 가짐
- 정렬: last_activity_at desc — 최근 활동 세션이 맨 위
- limit clamp: 1~200, 기본 50

#### 2. UI 시연 — 대시보드 진입

1. http://localhost:3000/?view=dashboard 접속
2. ontology 통계 카드 아래 새 섹션 "📋 최근 세션" 표시
3. 각 row: `[YY-MM-DD HH:MM] [status badge] [turn_count] [Gate 라벨] "user_query"` + `sid(8 chars) · repo_id`
4. 검색 입력 (debounce 200ms) — 입력 즉시 백엔드 filter

#### 3. UI 시연 — 세션 클릭 → 멀티턴 replay

1. row 클릭 → URL 이 `?view=multiturn&sid=<UUID>` 로 변경 + pushState
2. MultiturnChat 가 `initialSid` 받아 자동 `loadSession(sid)` 호출
3. 과거 결정 (Gate I/II/III 카드) 즉시 렌더 — 새 sim_v2 호출 0 (payload_json 이 source-of-truth)
4. SSE 스트림은 session.status === "done" 이면 즉시 close

#### 4. 새 대화 시작

- header "새 대화" 버튼 → `reset()` + `clearSid()` → URL 에서 sid 제거 + EmptyState 복귀

### 검증 결과 (2026-05-18)

- pytest tests/simulation/test_multiturn_session_list.py — **14 PASS** (persistence 8 + endpoint 6)
- 기존 multiturn router/persistence — **59 PASS** (regression 0)
- `npx tsc --noEmit` clean
- localhost:8001 실 데이터 sanity:
  - 기존 16+ 세션 (thickness / cumulativeProductivity / 주문 검증 등) 정상 surface
  - turn_count 1~3 분포 (turn 1 = /start stub, turn 2 = Gate I real, turn 3 = Gate II 또는 Gate III impact)
  - last_gate_kind = target_selected / bundle_prepared 혼합

### 트러블슈팅

#### "최근 세션" 섹션이 영구 비어 있음
- 가능: backend 가 재기동 후 `ONTONG_DB_PATH` 가 빈 DB 가리킴 → 확인: `ls -la data/ontology.db`
- 가능: GET /sessions endpoint 가 미반영 (stale uvicorn) → `lsof -i :8001 -t | xargs kill` 후 재기동

#### 한글 search 가 무응답
- URL-encode 누락 가능 — curl 은 `--data-urlencode`, fetch 는 `URLSearchParams` (이미 client 가 처리)

#### session 클릭 후 화면이 빈 상태
- `loadSession` 이 호출됐는지 콘솔에서 `apiGetSession` 확인
- 가능: session_id 가 DB 에서 삭제되었음 (CASCADE) → "새 대화" 로 복귀


---

## Phase 13b — search keyword extraction + 0-cand fallback (2026-05-18)

> 김PM / 박주니어 페르소나 잔여 마찰 (search 가 풀 query 던져서 0 cand) 해결.

### 사전 조건
- backend `http://localhost:8001` 동작 + repo `slab-design-real-v2` (76 business_terms 시드 필요).

### 시연 시나리오

#### 1. search_terms 추출 — 검색 정확도 향상

```bash
START_JSON=$(curl -s -X POST http://localhost:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"엣징 마진 변경하면 어디 영향?","repo_id":"slab-design-real-v2"}')
SID=$(echo "$START_JSON" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
curl -s -X POST "http://localhost:8001/api/section3/multiturn/respond/$SID" \
  -H 'Content-Type: application/json' \
  -d '{"message":"엣징 마진 변경하면 어디 영향?"}' | python3 -m json.tool
```

기대:
- `intent`: `"impact"` (confidence ≥ 0.85)
- `sources[]` 의 ontology / sim_v2 항목에서 `query='엣징 마진'` — 풀 문장 (`엣징 마진 변경하면 어디 영향?`) 이 아니라 핵심 키워드만 search 에 사용된다.
- `suggestions`: `["엣징그룹코드","edgingGroupCd"]` 같은 인접어 surface (candidates 0 일 때).

#### 2. 0-cand fallback — suggestions surface

```bash
START_JSON=$(curl -s -X POST http://localhost:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"엣징 마진 변경하면 어디 영향?","repo_id":"slab-design-real-v2"}')
SID=$(echo "$START_JSON" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
RESP=$(curl -s -X POST "http://localhost:8001/api/section3/multiturn/respond/$SID" \
  -H 'Content-Type: application/json' \
  -d '{"message":"엣징 마진 변경하면 어디 영향?"}')
echo "$RESP" | grep -o '"suggestions":\[[^]]*\]'
```

기대 출력 (예):
```
"suggestions":["엣징그룹코드","edgingGroupCd"]
```

---

## Phase 13c — hypothesis intent + conditions + executed_hypothesis (2026-05-18)

> 최QA 페르소나 boundary value 질의 1:1 해결. silent wrong target 위험 verdict + confidence 로 honest surface.

### 시연 시나리오

#### 1. hypothesis intent + conditions 추출 — boundary value 보존

```bash
START_JSON=$(curl -s -X POST http://localhost:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"두께 0.1mm 인 슬라브 입력하면 검증 실패하나?","repo_id":"slab-design-real-v2"}')
SID=$(echo "$START_JSON" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
curl -s -X POST "http://localhost:8001/api/section3/multiturn/respond/$SID" \
  -H 'Content-Type: application/json' \
  -d '{"message":"두께 0.1mm 인 슬라브 입력하면 검증 실패하나?"}' | python3 -m json.tool
```

기대:
- `intent`: `"hypothesis"`
- `conditions`: `[{"var":"두께","op":"=","value":"0.1","unit":"mm"}]` — boundary value (0.1) + unit (mm) 보존
- `candidates[]`: 매칭 후보 (예: SdDesigner.design / SdThicknessAction 등)

#### 2. executed_hypothesis verdict + evidence — turn 3

```bash
# Step 1: turn 2 (위 시나리오 1)
# Step 2: confirm
curl -s -X POST "http://localhost:8001/api/section3/multiturn/confirm/$SID/2" \
  -H 'Content-Type: application/json' \
  -d '{"action":"confirm","user_response":{"selected_index":0}}'
# Step 3: turn 3
curl -s -X POST "http://localhost:8001/api/section3/multiturn/respond/$SID" \
  -H 'Content-Type: application/json' \
  -d '{"message":""}' | python3 -m json.tool
```

기대:
- `kind`: `"executed_hypothesis"`
- `verdict`: `"likely_yes"` | `"likely_no"` | `"unknown"` — heuristic 기반 (body 안에 var/value/op 시그널 + business_rule.statement 매칭 시그널 합산)
- `reasoning`: 1~2 문장 (한국어 OK)
- `evidence[]`: BusinessRuleEvidence — declared_on_term 기반 rules 5~10 행 (fqn / statement / severity)
- `confidence`: 0.2 (unknown) ~ 0.75 (강한 시그널)

#### 3. silent wrong target 검증 — verdict=unknown 으로 honest surface

```bash
# 시니어 페르소나 시나리오 — 잘못된 method 가 top-1 으로 picked 되어도
# verdict + confidence 가 honest 하게 신호한다.
START_JSON=$(curl -s -X POST http://localhost:8001/api/section3/multiturn/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"엣징그룹코드가 E001 이면 SdEdging 처리 어떻게 분기?","repo_id":"slab-design-real-v2"}')
SID=$(echo "$START_JSON" | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
curl -s -X POST "http://localhost:8001/api/section3/multiturn/respond/$SID" \
  -H 'Content-Type: application/json' \
  -d '{"message":"엣징그룹코드가 E001 이면 SdEdging 처리 어떻게 분기?"}' > /dev/null
curl -s -X POST "http://localhost:8001/api/section3/multiturn/confirm/$SID/2" \
  -H 'Content-Type: application/json' \
  -d '{"action":"confirm","user_response":{"selected_index":0}}' > /dev/null
RESP=$(curl -s -X POST "http://localhost:8001/api/section3/multiturn/respond/$SID" \
  -H 'Content-Type: application/json' \
  -d '{"message":""}')
echo "$RESP" | python3 -c "import sys, json; d = json.load(sys.stdin)['payload']; print('verdict:', d['verdict']); print('confidence:', d['confidence']); print('reasoning:', d['reasoning'])"
```

기대 (시니어 페르소나 검증 결과):
- 만약 wrong target picked → `verdict: "unknown"`, `confidence: 0.20`, `reasoning: "...다른 method 일 가능성"`
- Phase 13b 처럼 silent PASS 가 아닌, honest uncertainty surface.

### 트러블슈팅

#### confirm 후 turn 3 4xx — candidates=0 일 때
- Phase 14 후보 (state machine bug). 임시 우회: candidates 가 있는 query 부터 시연.

#### verdict 가 항상 unknown
- body 안에 conditions 의 var/value/op 가 매칭이 안 됨 — top candidate 가 wrong target 일 가능성. recommendation_index 가 0 이라도 다른 candidate (selected_index=1~) 로 confirm 시도.

#### intent 가 hypothesis 가 아닌 explain 으로 분류
- LLM 이 boundary value (숫자 + 비교 연산자) 시그널 못 잡음. user_query 를 "X 가 N 이면 결과?" 식으로 명확히.
