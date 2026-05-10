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
