# 05 — Runner Interface

> **목적**: 시뮬 라이프사이클의 실제 실행자 (`runner`) 인터페이스 명세. PythonGenerator + Java Dispatch Sandbox + Lookup Data Source + Runner State Machine + Artifact Collection.
>
> **결정 근거**:
> - D.4 산출 = Critical 갭 #4 (시뮬 input fixture) + #5 (Java dispatch sandbox) 정밀화
> - Q4=B 결정에 따라 본 명세는 simulation 세션이 책임지는 영역 (`backend/simulation/runner/*`)
>
> **위치**: 본 파일이 `handoff-spec/05-runner-interface.md`. 적용 코드는 (실 폴더 구조 — 현재 비어있음):
> - `backend/simulation/runner/python_generator.py` (신규 — runner 폴더 신설)
> - `backend/simulation/runner/java_sandbox.py` (신규)
> - `backend/simulation/runner/dispatch.py` (신규)
> - `backend/simulation/runner/lookup_source.py` (신규)
> - `backend/simulation/runner/orchestrator.py` (신규)
> - `backend/simulation/api/router.py` (기존 빈 폴더 — endpoint 추가)
> - `backend/simulation/api/run_handle.py` / `verdict.py` / `anchor_invalidate.py` (신규)
> - `backend/shared/contracts/simulation.py` (신규)
> 
> **참고** — 기존 `backend/simulation/{tools,mock,client}/` 폴더는 비어있음. 본 명세는 그 위에 `runner/` + `api/` 안의 신규 파일을 추가하는 구조. 기존 빈 폴더와 충돌 없음.
>
> **의존**: `01` (Action.realizes / delegates_to / Realization) + `03` (RunHandle / RunOptions) + `04` (ChangeSpec / SimResult / DelegationTraceFrame.dispatch_consistent / verdict 판정).
>
> **단방향성**: 본 모듈은 modeling 세션의 코드 (`backend/modeling/api/ontology_query.py` facade + REST `/api/ontology/*`) 를 import / call 만 한다. 본 명세 어디에도 modeling 세션의 코드를 수정하는 흐름이 없다.

---

## 0. 개관

| 섹션 | 내용 |
|---|---|
| 1 | PythonGenerator — Action delegation tree → 실행 가능 Python |
| 2 | Java Dispatch Sandbox — 다형성 dispatch + dispatch_consistent 검증 |
| 3 | Lookup Data Source — scenario_fixture.lookups 의 row 형식 (#4/#41) |
| 4 | Runner State Machine — pending → running → completed (03 RunHandle 의 상태 전환) |
| 5 | Python ↔ Java Boundary — protocol + 직렬화 + 에러 전파 |
| 6 | Artifact Collection — 03 의 ArtifactBundle 의 5 종 |
| 7 | 의존성 점검 — modeling 세션 코드와의 단방향성 |
| 8 | design-gaps 와의 매핑 |

---

## 1. PythonGenerator

### 1.1 책임

`ChangeSpec` + `RunPlan` 을 받아, 시뮬에서 실행할 **순수 Python 함수** 를 생성한다. 생성된 함수는:

- ChangeSpec.atomic_overrides 가 입력에 적용된 상태에서
- Action delegation tree 를 따라 sub-action 호출
- 각 sub-action 은 Java sandbox 에 dispatch (Section 2)
- BR / Anchor evidence 를 collect (Section 6)

### 1.2 인터페이스

```python
# backend/simulation/runner/python_generator.py
from backend.shared.contracts.simulation import ChangeSpec, RunPlan
from backend.shared.contracts.ontology_query import ActionDTO

class PythonGenerator:
    def __init__(self, ontology_client: "OntologyQueryClient"):
        """
        ontology_client: modeling 세션의 facade (OntologyQueryClientImpl 또는 HTTP 래퍼).
        본 generator 는 ontology_client 를 read-only 로 사용 — modeling 측 storage 를
        직접 import 하지 않는다 (단방향성 보장, Section 7 참조).
        """
        self._ont = ontology_client

    def generate(
        self,
        change_spec: ChangeSpec,
        run_plan: RunPlan,
    ) -> "GeneratedScript":
        """
        Returns: GeneratedScript — 실행 가능한 Python 모듈 + 메타데이터.
        Implementation 단계는 1.3 에서 명세.
        """


class GeneratedScript(BaseModel):
    """PythonGenerator 의 산출."""
    source_code: str                       # 실행 가능한 Python 코드 (utf-8)
    entrypoint: str                        # 실행할 함수 이름 (보통 "run")
    imports: list[str]                     # 필요한 import 문 목록 (sandbox 가 화이트리스트 검증)
    estimated_steps: int                   # delegation tree depth + count
    java_dispatch_calls: list[str]         # 본 코드가 호출할 Java method_fqn 목록 (사전 검증)
    fixture_keys_used: list[str]           # 사용할 lookups key 목록 ("Customer:7" 등)
```

**RunPlan 과의 매핑** (Agent 1 검수 보강 — A2):
- `java_dispatch_calls` = `RunPlan.delegates_to_tree` 의 각 action_fqn × `realizations-for-input` (02 Section 2.2 endpoint) 의 method_fqn 합집합 — derive 가능
- `fixture_keys_used` = `ChangeSpec.scenario_fixture.lookups` 의 key 중 generated code 가 실제 참조하는 것 (정적 분석)
- `estimated_steps` = `RunPlan.estimated_steps` 와 동일 또는 +α (loop iteration 추정 포함)

### 1.3 생성 단계

```
1. RunPlan.delegates_to_tree 에서 모든 sub-action fqn 펼치기
   (modeling 의 delegates-to-tree endpoint 결과 이용)

2. 각 sub-action 의 Realization 후보 결정:
   - Action.realizes 가 있으면 그 PRIMARY action 의 realizations 사용
   - 그 외에는 Action.realizations 직접 사용
   - input runtime type 별 dispatch 분기는 sandbox 가 처리 (Section 2)

3. ChangeSpec.atomic_overrides 를 fixture / inputs 에 적용:
   - atomic_path 를 04 Section 1.2 algorithm 으로 해석
   - resolve 결과를 RunInputs.slots / RunInputs.fixture 에 patch (4.6 의 RunInputs)

4. 코드 생성 (template + AST 합성) — DelegationEdge 의 is_in_loop / optional 처리:
   - 헤더: import 화이트리스트 (1.4)
   - lookup helper: lookup_source.get(...) 호출 함수 (Section 3.4)
   - run() 함수 본문:
       a. inputs = RunInputs(...)  # 4.6 RunInputs (orchestrator 가 빌드 후 전달)
       b. trace = []
       c. for each delegation_edge in delegates_to_tree (DFS):
            if delegation_edge.optional:
              # if 분기 — 조건은 codegen 가 평가 (atomic.facets / scenario.metadata 기반)
              if not eval_optional_condition(edge, inputs):
                continue
            
            if delegation_edge.is_in_loop:
              # 루프 — A-a 21-step 등. 루프 변수 결정:
              loop_iter = derive_loop_iterable(edge, inputs)  
              # 보통 inputs.slots[primary_slot].value 의 collection field
              for iter_idx, iter_val in enumerate(loop_iter, start=1):
                inner_inputs = clone_with_iter(inputs, iter_val)
                result = java_sandbox.dispatch(edge.callee_action_fqn, inner_inputs)
                trace.append(DelegationTraceFrame(
                    seq=len(trace)+1, depth=edge.depth, in_loop_iter=iter_idx,
                    action_fqn=edge.callee_action_fqn,
                    realized_method_fqn=result.realized_method_fqn,
                    dispatch_consistent=result.dispatch_consistent,
                    dispatch_mismatch_reason=result.dispatch_mismatch_reason,
                    ...
                ))
                inputs = merge_outputs(inputs, result.outputs)
            else:
              # 일반 sequential dispatch
              result = java_sandbox.dispatch(edge.callee_action_fqn, inputs)
              trace.append(DelegationTraceFrame(
                  seq=len(trace)+1, depth=edge.depth, in_loop_iter=None, ...
              ))
              inputs = merge_outputs(inputs, result.outputs)
       d. return RunResult(outputs=inputs.slots.outputs, trace=trace)

5. 메타데이터 채우기:
   - imports 화이트리스트 검사 (subprocess / os 등 금지)
   - java_dispatch_calls 추출 (sandbox 가 사전 검증)
   - fixture_keys_used (Section 3 의 lookup_source 가 사전 검증)
```

**loop / optional 처리 규약 (Agent 2 검수 보강 — A1)**:
- `DelegationEdge.is_in_loop` (01 Section 2.2) — codegen 가 `for` 루프로 변환. 루프 iterable 은 `derive_loop_iterable()` 가 정함 (보통 primary input 의 collection field)
- `DelegationEdge.optional` — codegen 가 `if` 분기로 변환. 조건은 atomic.facets 또는 scenario.metadata 기반 (구현 자유)
- `DelegationTraceFrame.in_loop_iter` — 루프 회차 (1-based). 일반 dispatch 는 None
- `derive_loop_iterable()` 는 Action.declared_on_term 의 composite 의 collection slot 을 추출 (예: `Order.slabs` 가 21-step 루프의 iterable). atomic.facets 에 `iter_source` 마킹 가능 (선택)

### 1.4 보안 / 격리

- **import 화이트리스트** (Agent 2 검수 보강 — A3, 명시화):
  - 표준 라이브러리: `dataclasses` / `typing` / `json` / `time`
  - 외부: `pydantic` (BaseModel — RunInputs 등에 사용)
  - simulation 내부: `backend.simulation.runner.java_sandbox` / `backend.simulation.runner.lookup_source` / `backend.shared.contracts.simulation`
  - 금지: `os` / `subprocess` / `socket` / `__import__` 우회 / `eval` / `exec` / `compile` / `pickle`
  - 검사 시점: GeneratedScript.imports 와 source_code 의 import 문 둘 다 — sandbox 가 ast.parse 후 검증.
- **timeout** (Agent 2 검수 보강 — A4, Section 4.7 와 통일):
  - `RunOptions.timeout_sec` 은 **전체 run** budget. 분배는 4.7 TimeoutBudget 정책으로 (per-dispatch fair-share + dynamic 흡수)
  - 03 의 6.2 capabilities.max_timeout_sec 가 ceiling
- **sandbox 가 코드 자체를 실행** — generator 는 코드 텍스트만 만든다. 실행은 Section 4 의 runner state machine 의 `running` 단계.

### 1.5 design-gap #5 와의 관계

dispatch 정합성 검증 (04 Section 3.2 (f)) 의 데이터 source. PythonGenerator 가 코드를 만들 때 input runtime type 을 추적하고, 그 type 이 Action.realizes 의 input_type 과 일치하는지 sandbox 가 dispatch 단계에서 확인 (Section 2.3).

---

## 2. Java Dispatch Sandbox

### 2.1 책임

PythonGenerator 가 생성한 Python 코드 안의 `java_sandbox.dispatch(action_fqn, inputs)` 호출을 받아, **실제 Java 메서드** 를 격리 환경에서 실행하고 결과를 반환한다.

핵심 가치:
1. 다형성 dispatch — input runtime type 에 따라 적절한 Realization 선택
2. dispatch_consistent 검증 — 04 Section 3.2 (f) 의 verdict 조건
3. 격리 — JVM 충돌 / OOM 이 시뮬 프로세스를 죽이지 않음

### 2.2 인터페이스

```python
# backend/simulation/runner/java_sandbox.py

class JavaSandbox:
    def __init__(self, capabilities: "SandboxCapabilities"):
        """JVM in subprocess 또는 GraalVM polyglot — 전략은 구현 결정 (3-tier)."""

    def dispatch(
        self,
        action_fqn: str,
        inputs: dict[str, Any],
        run_options: RunOptions,
    ) -> "DispatchResult":
        """
        action_fqn: 호출할 Action.
        inputs: { slot_name → value }. value 는 Java 객체로 직렬화 가능해야 함.
        Returns DispatchResult.
        Raises: TimeoutError / JVMCrashError / SerializationError.
        """


class DispatchResult(BaseModel):
    outputs: dict[str, Any]                # method 의 outputs 슬롯 → 값
    realized_method_fqn: str               # 실제 dispatch 된 method
    dispatch_consistent: bool              # input runtime type ↔ Action.realizes 일치
    dispatch_mismatch_reason: str | None
    duration_ms: int
    jvm_log: str                           # stdout / stderr (Section 6 artifact)
    captured_anchors: list["AnchorHit"]    # method body 안에서 hit 된 anchor 목록
    captured_brs: list["BRTrigger"]        # 호출된 BR enforcer 메서드 trace


class AnchorHit(BaseModel):
    anchor_id: str
    marker: str
    line: int
    captured_value: Any | None             # marker 가 잡은 runtime 값


class BRTrigger(BaseModel):
    br_fqn: str
    enforcer_method_fqn: str
    outcome: Literal["passed", "violated", "skipped"]
    violation_path: str | None
    expected: Any | None
    actual: Any | None
```

### 2.3 dispatch 알고리즘

```
input: action_fqn, inputs

1. Realization 후보 조회 (modeling facade):
   realizations = ontology_client.get_realizations_for_input_type(
       action_fqn,
       code_type_fqn=runtime_type_of(inputs.primary_input)
   )
   # 기존 endpoint /api/ontology/actions/{fqn}/realizations-for-input

2. dispatch 결정:
   if realizations.empty():
     dispatch_consistent = False
     dispatch_mismatch_reason = "no realization for input type {T}"
     raise DispatchError (또는 outputs={} + flag, run policy 결정)

   selected = realizations.first(by confidence desc)

3. dispatch_consistent 판정:
   action = ontology_client.get_action(action_fqn)
   if action.realizes:
     parent_action = ontology_client.get_action(action.realizes[0])
     expected_input_type = parent_action.inputs[primary].type_fqn
     actual_input_type = runtime_type_of(inputs.primary_input)
     dispatch_consistent = type_assignable(actual_input_type, expected_input_type)
     if not consistent:
       dispatch_mismatch_reason = f"expected {expected}, got {actual}"
   else:
     dispatch_consistent = True   # PRIMARY 자체이거나 polymorphic 없음

4. JVM 호출:
   try:
     jvm_result = jvm.invoke(selected.method_fqn, inputs, timeout=run_options.timeout_sec)
   except JVMTimeout:
     raise TimeoutError
   except JVMException as e:
     # method 안에서 throw 된 BR violation — 정상 결과로 처리 (capture)
     return DispatchResult(outputs={}, ..., captured_brs=[BRTrigger(violated, ...)])

5. anchor / br capture:
   # JVM agent 가 instrumentation 으로 anchor 마커 hit 와 BR enforcer 메서드 호출을 trace
   captured_anchors = jvm_result.anchor_hits
   captured_brs = jvm_result.br_triggers

6. return DispatchResult
```

### 2.4 SandboxCapabilities

```python
class SandboxCapabilities(BaseModel):
    backend: Literal["jvm_subprocess", "graalvm_polyglot", "stub"]
    """jvm_subprocess — Java 프로세스를 별도 spawn (격리 강), 직렬화 비용 고
    graalvm_polyglot — 같은 process 의 Python ↔ Java 호출 (격리 약, 성능 고)
    stub — 테스트용 가짜 dispatch (Phase 시연 / 단위 테스트)"""
    
    java_version: str | None
    classpath_roots: list[str] = []
    instrumentation_jar: str | None
    """anchor / BR capture 용 Java agent jar 경로."""
    max_heap_mb: int = 512
    max_concurrent_dispatches: int = 4
```

### 2.5 격리 전략 권장

- **dev / 시연**: `stub` — Java 코드 실행 없이 더미 결과 반환. UI 동작 확인용.
- **운영 v1**: `jvm_subprocess` — 격리 안정성 우선. dispatch 1건당 ~100ms 직렬화 오버헤드 감수.
- **운영 v2**: `graalvm_polyglot` — 성능 필요 시. 격리 약화는 process restart 정책으로 보완.

3-tier 모두 동일 `JavaSandbox` 인터페이스 — 구현체만 swap 가능.

---

## 3. Lookup Data Source — scenario_fixture.lookups 의 row 형식

### 3.1 동기

`04 Section 1.1` 의 `scenario_fixture.lookups` 가 `{"Customer:7": {...}}` placeholder 만 명세됐음. design-gap #4 / #41 해소를 위해 row 의 atomic-set 정의를 본 절에서 정밀화.

### 3.2 row 형식 — TableSpec → atomic-set

```python
class TableSpec(BaseModel):
    """lookup 가능한 CodeType 의 메타. modeling 세션의 CodeType 에서 derive."""
    code_type_fqn: str                  # "scm.std.CustomerStd"
    pk_atom_fqn: str                    # "scm.shared.atomic.customer_no"
    columns: dict[str, str]
    """slot_name → atomic_fqn 매핑.
    예: {
      "name": "scm.shared.atomic.customer_name",
      "thickness_min": "scm.shared.atomic.thickness",
      ...
    }
    """
    drama_dna_columns: list[str] = []
    """alias / 한글 칼럼 등 drama DNA 영향 받는 슬롯."""


class LookupRow(BaseModel):
    """scenario_fixture.lookups 의 한 row — atomic 슬롯 dict."""
    pk: Any                             # PK 값 (예: 7)
    table_spec_fqn: str                 # TableSpec.code_type_fqn 참조
    columns: dict[str, Any]
    """{slot_name → 값} — table_spec.columns 의 slot 들과 매핑.
    값은 atomic.facets (range_min/max/unit/enum) 으로 검증."""
```

### 3.3 lookups 의 직렬화 형태 (ChangeSpec.scenario_fixture)

```jsonc
{
  "lookups": {
    // key 는 "{table_spec_fqn}:{pk}" (04 Section 1.1 형식)
    "scm.std.CustomerStd:7": {
      "pk": 7,
      "table_spec_fqn": "scm.std.CustomerStd",
      "columns": {
        "customer_name": "정XX",
        "thickness_min": 200,
        "thickness_max": 250,
        "width_min": 1000,
        "width_max": 1500,
        "capability_multiplier": 1.0
      }
    },
    "scm.spec.HrSpec:HR-23-A": {
      "pk": "HR-23-A",
      "table_spec_fqn": "scm.spec.HrSpec",
      "columns": {
        "proc": "0HR23456",
        "thickness_range_min": 200,
        "thickness_range_max": 230,
        "width_range_min": 1100,
        "width_range_max": 1300
      }
    }
  },
  "metadata": {
    "scenario_origin": "P-2018-0098",
    "snapshot_at": "2018-04-23T03:14"
  }
}
```

### 3.4 LookupDataSource 인터페이스 + TableSpec derive 알고리즘

```python
# backend/simulation/runner/lookup_source.py

class LookupDataSource:
    """ChangeSpec.scenario_fixture.lookups 를 sandbox 에게 in-memory 로 노출."""

    def __init__(
        self,
        ontology_client: "OntologyQueryClient",
        fixture: dict[str, Any],
    ):
        self._table_specs = self._derive_table_specs(ontology_client)
        self._rows = self._index_fixture(fixture)

    def get(self, table_spec_fqn: str, pk: Any) -> LookupRow | None:
        """단일 row 조회 — sandbox 의 Java code 가 DB 룩업처럼 호출."""

    def list(self, table_spec_fqn: str) -> list[LookupRow]:
        """전체 lookup — Java code 의 list 형 룩업용."""

    def validate(self) -> list[str]:
        """fixture 의 atomic 값이 facets (range/unit/enum) 와 일치하는지 검증.
        Returns: warning 메시지 목록 (empty 면 OK)."""

    def _derive_table_specs(self, client) -> dict[str, TableSpec]:
        """CodeType → TableSpec 자동 derive (Agent 2 검수 보강 — C1)."""
        specs = {}
        # 1. lookup 가능한 CodeType 후보 수집:
        #    role="lookup_table" 또는 declared_on_term==std/spec sub-domain 의 CodeType
        candidates = client.list_code_types(role="lookup_table")
        for ct in candidates:
            # 2. PK atomic 식별:
            #    CodeType 의 fields 중 is_pk=True 인 첫 field 의 atomic_fqn (없으면 skip)
            pk_field = next((f for f in ct.fields if f.is_pk), None)
            if pk_field is None:
                continue
            # 3. columns 매핑 빌드:
            #    각 field 의 (slot_name → atomic_fqn) 페어 추출
            #    field 가 BusinessTerm 에 매핑되어있으면 BusinessTerm.fqn 사용
            #    매핑 없는 field 는 columns 에서 제외 (raw java field 는 시뮬과 무관)
            columns = {
                f.slot_name: f.atomic_fqn
                for f in ct.fields
                if f.atomic_fqn is not None
            }
            # 4. drama_dna_columns 식별:
            #    field 에 drama_dna_kind 마킹된 것 (Realization.drama_dna_kind 와 같은 의미)
            #    또는 alias (한글 칼럼명, 별칭 등) 가 있는 것
            drama = [f.slot_name for f in ct.fields if f.drama_dna_kind is not None]
            specs[ct.fqn] = TableSpec(
                code_type_fqn=ct.fqn,
                pk_atom_fqn=pk_field.atomic_fqn,
                columns=columns,
                drama_dna_columns=drama,
            )
        return specs

    def _index_fixture(self, fixture: dict) -> dict:
        """fixture 의 모든 row 의 columns 에 대해 atomic_fqn 검증 + canonical 형태로 변환."""
```

**derive 알고리즘 단계** (요약):
1. modeling 의 CodeType list (role="lookup_table" 등) 수집
2. PK field 식별 (is_pk=True 첫 field)
3. columns 매핑 빌드 — atomic_fqn 매핑된 field 만 (raw java field 제외)
4. drama_dna_columns 식별 — 한글 칼럼 / alias / 어긋남 마킹

**전제** — 01 의 CodeType DTO 가 다음 필드 보유 가정 (없으면 modeling 측에 추가 명세 필요):
- `fields: list[CodeField]` — 각 field 가 `slot_name`, `atomic_fqn?`, `is_pk: bool`, `drama_dna_kind: str?`
- `role: str` — "lookup_table" / "domain_entity" / "value_object" 등

### 3.4.5 stub backend 의 행동 명세 (Agent 2 검수 보강 — B2)

> stub 모드에서 verdict=sim_verified 가 가능해야 검증 step 1 (Section 10) 이 동작.

stub 의 `dispatch()` 는 다음 정책을 따른다:

```python
class StubJavaSandbox(JavaSandbox):
    def __init__(self, capabilities, ontology_client):
        self._ont = ontology_client

    def dispatch(self, action_fqn, inputs, run_options) -> DispatchResult:
        # 1. Realization 후보 조회 (실 dispatch 와 동일)
        realizations = self._ont.get_realizations_for_input_type(...)
        selected = realizations[0] if realizations else None

        # 2. dispatch_consistent — Section 2.3 step 3 알고리즘 그대로
        #    실제 JVM 호출 없이도 type 매칭만 확인
        consistent, mismatch_reason = check_dispatch_consistency(...)

        # 3. anchor capture — 본 action 의 expected_anchors 모두 hit 처리
        #    (가짜 hit — dispatch 자체는 실 안 일어남, 그러나 verdict 검증을 위해)
        anchors_for_action = self._ont.get_anchor_bindings_for_action(action_fqn)
        captured = [
            AnchorHit(
                anchor_id=a.anchor_id,
                marker=a.marker,
                line=a.line,
                captured_value=None,   # stub 은 runtime 값 없음
            ) for a in anchors_for_action
        ]

        # 4. BR capture — 본 action 의 expected_brs 모두 passed 처리
        #    (단, scenario.kind=br_violation 시나리오는 violated 로)
        brs_for_action = self._ont.get_business_rules_by_action(action_fqn)
        triggers = [
            BRTrigger(
                br_fqn=br.fqn,
                enforcer_method_fqn=br.enforced_by[0] if br.enforced_by else None,
                outcome="passed",
                violation_path=None,
                expected=None, actual=None,
            ) for br in brs_for_action
        ]

        # 5. outputs — scenario.expected_outputs 가 있으면 echo, 없으면 빈 dict
        outputs = self._echo_expected_outputs(...)

        return DispatchResult(
            outputs=outputs,
            realized_method_fqn=selected.method_fqn if selected else None,
            dispatch_consistent=consistent,
            dispatch_mismatch_reason=mismatch_reason,
            duration_ms=0,
            jvm_log="[stub mode]\n",
            captured_anchors=captured,
            captured_brs=triggers,
        )
```

**stub 행동 합의**:
- anchor — 모든 expected_anchors 가 자동 hit (verdict=sim_verified 가능)
- BR — scenario.kind ≠ br_violation 인 한 모두 passed
- outputs — scenario.expected_outputs echo (없으면 빈 dict, output_values 검증 skip 가능)
- duration_ms = 0, jvm_log = "[stub mode]" — 운영 stub 임을 명시

**stub 의 검증 한계**:
- 코드 변경의 실제 효과 검증 불가 (Java code 호출 안 함)
- BR violation 회귀 (P-2018-0098) 는 jvm_subprocess / graalvm 으로만
- dev / 시연 / unit test 용 — 운영 promote 결정에 stub run 만으로는 불가

### 3.5 DB lookup 의 sandbox 모드

| 모드 | 출처 | 권장 |
|---|---|---|
| `fixture_only` | scenario_fixture.lookups 만 사용 (DB 미호출) | dev / regression / drama / unit test |
| `fixture_with_db_fallback` | fixture 에 없는 PK → 실 DB 의 read-only 미러 | 운영 사고 회귀 (운영 데이터로 채우기) |
| `db_snapshot` | scenario.metadata.snapshot_at 시점의 DB snapshot | regression with snapshot |

3 모드 모두 동일 `LookupDataSource` 인터페이스 — 구현체 swap.

### 3.6 design-gap #4 / #41 해소

- **#4 시뮬 input fixture (DB 룩업 sandbox 데이터 source)** — 본 Section 3.5 의 3 모드로 해소.
- **#41 lookups row 형식** — 본 Section 3.2 의 TableSpec + LookupRow 로 해소.

---

## 4. Runner State Machine

### 4.1 RunHandle 상태 전환 (03 Section 1.1 의 state machine 정밀화)

```
                     ┌─────────────────────────────────────────────┐
                     │                                             │
[POST /runs] ──▶ pending ──▶ running ──▶ completed                │
                              │                                     │
                              ├──▶ failed (sandbox 충돌 / timeout)    │
                              │                                     │
                              └──▶ cancelled (사용자 취소)             │
                              
[POST /runs?dry_run=true] ──▶ pending ──▶ running ──▶ completed
                                            (코드 생성만 / sandbox 안 부름)
```

### 4.2 단계별 책임

| 상태 | 책임 모듈 | 작업 |
|---|---|---|
| `pending` | `/api/simulation/router.py` | RunHandle 등록, queue 에 enqueue |
| `running` | `runner/orchestrator.py` (신규) | (a) PythonGenerator 호출 (b) JavaSandbox 호출 (c) Section 5 의 SimResult 빌드 |
| `completed` | 같은 orchestrator | DB 에 SimResult 저장 + 03 Section 1.1 의 promote/downgrade hook 호출 |
| `failed` | 같은 orchestrator | failure_reason 채우기 + audit log + alert |
| `cancelled` | router 의 cancel endpoint (옵션) | 진행 중 sandbox subprocess kill + 부분 결과 보존 |

### 4.3 Queue 전략 권장

- **v1**: in-process Python `asyncio.Queue` — 단일 process. dev / 작은 규모.
- **v2**: Redis + RQ (또는 Celery) — 다 process / 다 worker. 100K 문서 가정 (사용자 메모) 대응.
- **v3**: external (별 머신의 sandbox cluster) — Java sandbox 전용 머신.

3 tier 모두 동일 RunHandle 상태 머신 — 구현체 swap.

### 4.4 Health / Capabilities 와의 연결 (03 Section 6.x)

- `GET /api/simulation/health` 의 `queue_depth` ← 본 queue 의 pending count
- `GET /api/simulation/capabilities` 의 `runner_version` / `java_sandbox_version` ← 본 모듈 build 메타

### 4.5 ★ Orchestrator entrypoint 인터페이스 (Agent 2 검수 보강 — D1)

> 다음 개발자가 main entry 가 어딘지 모른다는 검수 합의에 따라 추가. orchestrator 는 running 단계의 모든 책임을 한 곳에 모은다.

```python
# backend/simulation/runner/orchestrator.py

class Orchestrator:
    def __init__(
        self,
        ontology_client: "OntologyQueryClient",
        python_generator: PythonGenerator,
        java_sandbox: JavaSandbox,
        lookup_source_factory: Callable[[dict], LookupDataSource],
    ): ...

    def run(
        self,
        change_spec: ChangeSpec,
        run_plan: RunPlan,
        run_options: RunOptions,
    ) -> SimResult:
        """Running 단계의 모든 책임 단일 entry.
        Steps:
          1. lookup_source = factory(change_spec.scenario_fixture)
          2. lookup_source.validate() — fixture 무결성
          3. generated = python_generator.generate(change_spec, run_plan)
          4. timeout budget 분배 (4.6 정책)
          5. dispatch loop:
             for action_fqn in run_plan.delegates_to_tree (DFS, loop/optional 처리):
               result = java_sandbox.dispatch(action_fqn, inputs, dispatch_budget)
               trace.append(DelegationTraceFrame(...))
               inputs = merge_outputs(inputs, result.outputs)
               if result error and policy=fail_fast: break
          6. verdict 판정 (04 Section 3.2 6 조건 + 3.6 보수 결정)
          7. SimResult 빌드 (br_evidence / anchor_evidence / output_values / delegation_trace)
          8. promote/downgrade hook (04 Section 3.4)
        Returns: SimResult
        Raises: TimeoutError / SandboxCrashError"""
```

### 4.6 ★ inputs dict 구조 + primary_input 식별 규약 (Agent 2 검수 보강 — A2 + B1)

> Section 1.3 / 2.3 / 5.2 의 `inputs` 가 같은 의미인지 단절돼있던 검수 지적에 따라 통일 명세.

#### 단일 표현 — `RunInputs`

```python
class RunInputs(BaseModel):
    """orchestrator → python_generator → java_sandbox 까지 일관 사용되는 입력 구조."""

    slots: dict[str, "TypedValue"]
    """Action.inputs 의 slot_name → 값.
    예: {"order": TypedValue(_type="scm.order.Order", value={...}), 
         "customer": TypedValue(_type="scm.std.CustomerStd", value={...})}
    슬롯 이름은 Action.inputs[i].name (declared)."""

    fixture: "LookupDataSource"
    """전체 fixture 접근 — Java code 가 lookup_source.get(...) 형태로 읽음.
    JSON 직렬화 시 fixture 의 모든 row 가 envelope.fixture 에 포함됨 (Section 5.2)."""

    overrides: dict[str, Any]
    """ChangeSpec.atomic_overrides — atomic_path → 값. 04 Section 1.2 4-rule 로 해석.
    overrides 는 slots 빌드 시 적용된 후 sandbox 에 같이 전달 (감사 / explanation 용)."""

    primary_input_slot: str
    """다형성 dispatch (Section 2.3 step 1 의 'inputs.primary_input') 가 참조할 슬롯 이름.
    선정 알고리즘:
      1. Action.inputs 에 role='primary' 인 슬롯이 있으면 그것
      2. 없으면 Action.inputs[0].name (첫 슬롯, declared 순)
      3. inputs 가 0 이면 None — pure constant Action 으로 dispatch 무관"""


class TypedValue(BaseModel):
    _type: str    # CodeType fqn — Section 5.5 의 _type 식별자
    value: Any    # primitive / dict / list
```

#### dispatch 흐름에서의 사용

```
1. orchestrator.run() 시작 시:
   inputs = RunInputs(
     slots = build_slots(change_spec, action_fqn),
     fixture = lookup_source,
     overrides = change_spec.atomic_overrides,
     primary_input_slot = derive_primary(action_fqn),
   )

2. atomic_overrides 적용:
   for path, val in inputs.overrides.items():
     resolve and patch into inputs.slots[?].value (04 Section 1.2)

3. JavaSandbox.dispatch(action_fqn, inputs, ...):
   - runtime_type_of(inputs.slots[inputs.primary_input_slot]._type)
     → Action.realizes 의 input_type 과 비교 (Section 2.3 step 3)
   - inputs.slots 를 Section 5.2 envelope 의 inputs 로 직렬화
     (TypedValue 의 _type / value 형태 그대로)
   - inputs.fixture 의 모든 row 도 envelope 에 포함

4. dispatch 결과의 outputs 를 inputs.slots 에 merge (다음 sub-action 의 input 이 됨):
   inputs.slots = {**inputs.slots, **dispatch_result.outputs_as_slots}
```

#### slot vs lookup 분리 규약

| 구분 | 어디 | 누가 |
|---|---|---|
| slot (Action.inputs) | `inputs.slots[slot_name]` | orchestrator 가 build_slots() 로 채움 |
| lookup (DB 룩업 row) | `inputs.fixture.get(...)` | sandbox 안의 Java code 가 호출 |
| atomic override | `inputs.overrides` | 사용자가 ChangeSpec 으로 명시 |

이로써 1.3 / 2.3 / 5.2 의 `inputs` 가 모두 RunInputs 의 동일 객체.

### 4.7 ★ Timeout 분배 정책 (Agent 2 검수 보강 — A4)

```python
# backend/simulation/runner/timeout_budget.py

class TimeoutBudget:
    """전체 run timeout 을 sub-dispatch 로 분배."""
    
    def __init__(self, total_sec: int, plan: RunPlan):
        self._deadline = time.monotonic() + total_sec
        self._reserved_per_dispatch = total_sec / max(plan.estimated_steps, 1)
        # 단순 fair-share — 21-step 의 경우 30s/21 = ~1.4s/dispatch.

    def for_dispatch(self) -> float:
        """남은 시간 기반 dynamic budget — 빠른 dispatch 가 끝나면 늦은 dispatch 가 더 받음.
        실패 임박 시 cumulative deadline check."""
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("total run budget exhausted")
        return min(remaining, self._reserved_per_dispatch * 2)
        # 2x ceiling — 한 dispatch 가 지나치게 오래 걸리는 것 방지

    def budget_remaining(self) -> float:
        return max(0, self._deadline - time.monotonic())
```

**정책**:
- `RunOptions.timeout_sec` 은 **전체 run** 의 budget (1.4 보안/격리 절의 timeout 과 같음)
- 분배는 `total / estimated_steps` 기본 + 빠른 dispatch 가 남기면 늦은 dispatch 가 흡수 (dynamic budget)
- 임의 dispatch 가 fair-share × 2 를 넘으면 강제 timeout (한 frame 의 폭발 방지)
- 03 Section 6.2 capabilities.max_timeout_sec 가 ceiling

### 4.8 ★ Dispatch loop 실패 정책 (Agent 2 검수 보강 — D3)

> 21-step 의 step-5 실패 시 step-6~21 어떻게 되는가의 결정.

```python
class FailurePolicy(BaseModel):
    on_dispatch_error: Literal["fail_fast", "continue", "abort_after_n"] = "fail_fast"
    """fail_fast — 첫 에러에 dispatch loop 중단, partial trace 보존
    continue — 에러 frame 의 error 필드만 채우고 다음 sub-action 진행
    abort_after_n — N개 누적 에러 시 abort (RunOptions.max_errors)"""

    on_br_violation: Literal["continue", "fail_fast"] = "continue"
    """continue — BR violation 도 dispatch 결과로 capture, dispatch loop 계속.
              verdict=sim_violation 으로 종료 (04 Section 3.2)
    fail_fast — BR violation 시 즉시 dispatch 중단 (debug / drama 시연용)"""

    on_anchor_miss: Literal["continue", "fail_fast"] = "continue"
    """anchor miss 는 verdict=inconclusive 이지만 dispatch 자체는 보통 계속."""

    on_dispatch_inconsistent: Literal["continue", "fail_fast"] = "continue"
    """dispatch_consistent=False 도 verdict=inconclusive (04 Section 3.6)
    이지만 trace 는 끝까지 수집."""
```

**기본 정책 합의**:
- 21-step 회귀 / drama 시연 — `on_br_violation=continue` (모든 BR evidence 수집)
- 운영 빠른 ping — `on_dispatch_error=fail_fast`
- 정책은 RunOptions 에 추가 (03 보강 가능):

```python
class RunOptions(BaseModel):
    timeout_sec: int = 30
    capture_traces: bool = True
    capture_br_evidence: bool = True
    dry_run: bool = False
    failure_policy: FailurePolicy = FailurePolicy()  # 신규
```

---

## 5. Python ↔ Java Boundary Protocol

### 5.1 직렬화 형식

| 방향 | 형식 | 이유 |
|---|---|---|
| Python → Java (입력) | JSON (UTF-8) | 타입 단순 + 디버그 쉬움 |
| Java → Python (출력) | JSON (UTF-8) | 동일 |
| Java → Python (anchor / br capture) | JSON Lines (각 줄이 한 이벤트) | 스트리밍 + 큰 trace 처리 |
| Java → Python (jvm_log) | UTF-8 텍스트 | 디버그 / artifact |

### 5.2 입력 envelope

```json
{
  "request_id": "uuid",
  "action_fqn": "scm.workflow.SDSlabEntity_step_1_to_8",
  "method_fqn": "scm.SdDesigner.runStep1",
  "inputs": {
    "order": { "_type": "scm.order.Order", "width": 1180, "thickness": 220 },
    "fixture": { "...": "..." }
  },
  "options": {
    "timeout_ms": 30000,
    "instrumentation": "all"
  }
}
```

### 5.3 출력 envelope

```json
{
  "request_id": "uuid",
  "status": "ok",
  "outputs": {
    "slabResult": { "_type": "scm.slab.SlabResult", "...": "..." }
  },
  "anchor_hits": [
    {"anchor_id": "a1", "marker": "자리 1 = HR", "line": 58, "captured_value": "HR"}
  ],
  "br_triggers": [
    {"br_fqn": "br.scm.slab.DG003.WidthMin", "outcome": "violated",
     "violation_path": "scm.slab.SlabResult.width", "expected": ">=1200", "actual": 1180}
  ],
  "jvm_log_ref": "artifacts/{run_id}/jvm.log",
  "duration_ms": 142
}
```

### 5.4 에러 envelope

```json
{
  "request_id": "uuid",
  "status": "error",
  "error_kind": "timeout | jvm_crash | serialization | dispatch_unresolved",
  "error_message": "...",
  "partial_outputs": { },          // 가능하면 일부 결과 보존
  "jvm_log_ref": "..."
}
```

### 5.5 Type 식별자 (`_type` 필드)

JSON 직렬화의 type 정보 손실을 막기 위한 convention:
- 모든 inputs / outputs 객체는 `_type: "{CodeType.fqn}"` 필드 보유
- Java sandbox 가 역직렬화 시 사용 (적절한 Java class 로 변환)
- runtime_type_of(inputs.primary_input) → 본 필드를 읽어 dispatch_consistent 검증 (Section 2.3 step 3)

### 5.6 안전 기본값

- 모든 dict 의 keys 는 ASCII (한글 atomic 변수명도 fqn 은 ASCII — Phase A 결정)
- 큰 객체 (10MB 초과) 는 분리 artifact 로 → envelope 안에 ref 만 (`{"_ref": "artifacts/.../big.json"}`)

---

## 6. Artifact Collection

### 6.1 산출 종류 (03 Section 2.3 의 5 종 매핑)

| kind | 출처 | 라이프사이클 |
|---|---|---|
| `generated_python` | PythonGenerator.GeneratedScript.source_code | run 시작 시 저장 |
| `jvm_log` | JavaSandbox 의 stdout / stderr | dispatch 별 append |
| `trace` | DelegationTraceFrame[] (JSON) | run 종료 시 |
| `input_fixture` | ChangeSpec.scenario_fixture (canonical 형) | run 시작 시 |
| `output_dump` | SimResult.output_values (JSON) | run 종료 시 |

### 6.2 저장 형태 권장

```
artifacts/{run_id}/
  generated.py       # 생성된 Python
  jvm.log            # JVM stdout/stderr (append)
  trace.jsonl        # JSON Lines — 각 줄이 한 frame
  input_fixture.json
  output_dump.json
```

03 의 `GET /runs/{run_id}/artifacts` 가 본 디렉터리를 list, `download_url` 은 본 path 의 별 endpoint (예: `GET /api/simulation/runs/{id}/artifacts/{name}`).

### 6.3 보관 정책

- `verdict=sim_verified` — 90일 유지 (재진급 evidence)
- `verdict=sim_violation` — 영구 보존 (BR.operational_history 와 link)
- `verdict=inconclusive` / `failed` — 30일 유지

---

## 7. ★ 의존성 점검 — modeling 세션 코드와의 단방향성

### 7.1 본 모듈이 modeling 세션의 무엇을 사용하는가

| 본 모듈 | 사용 대상 (modeling 세션) | 사용 방식 |
|---|---|---|
| PythonGenerator (Section 1) | OntologyQueryClient (`backend/modeling/api/ontology_query.py`) | facade import — read-only 호출 |
| PythonGenerator | `/api/ontology/actions/{fqn}/delegates-to-tree` | HTTP 또는 facade |
| JavaSandbox (Section 2) | `/api/ontology/actions/{fqn}/realizations-for-input` | HTTP 또는 facade |
| JavaSandbox | OntologyQueryClient.get_action / get_term | facade |
| LookupDataSource (Section 3) | OntologyQueryClient.get_code_type (TableSpec derive) | facade |
| Runner orchestrator (Section 4) | `/api/ontology/actions/{fqn}/business-rules` | HTTP 또는 facade |
| Result builder | `/api/ontology/actions/{fqn}/anchor-bindings` | HTTP 또는 facade |

### 7.2 본 모듈이 modeling 세션 코드를 수정하는가

**아니오**. 본 모듈은 다음 영역만 쓴다 (modeling 세션이 손대지 않을 영역) — 실 폴더 구조 (`backend/simulation/{api,tools,mock,client}/` 가 이미 비어있는 폴더로 존재):

```
backend/simulation/api/router.py              ← /api/simulation/* endpoint (기존 폴더)
backend/simulation/api/run_handle.py          ← run lifecycle state machine (4)
backend/simulation/api/verdict.py             ← 04 Section 3 verdict 판정 로직
backend/simulation/api/anchor_invalidate.py   ← 04 Section 4 invalidation
backend/simulation/runner/python_generator.py ← Section 1 (runner 폴더 신설)
backend/simulation/runner/java_sandbox.py     ← Section 2
backend/simulation/runner/dispatch.py         ← Section 2.3 dispatch 알고리즘
backend/simulation/runner/lookup_source.py    ← Section 3
backend/simulation/runner/orchestrator.py     ← Section 4 의 running 단계
backend/shared/contracts/simulation.py        ← ChangeSpec / SimResult / DelegationTraceFrame 등
```

기존 `backend/simulation/{tools,mock,client}/` 빈 폴더는 그대로 유지 (필요 시 simulation 세션이 활용).

### 7.3 modeling 세션 코드가 본 모듈을 import 하는가

**아니오**. modeling 세션의 코드는 simulation 모듈을 알지 못함. CLAUDE.md 의 Section Isolation Rule + 본 단방향성 규칙을 어긴 import 는 PR review 에서 거부할 것.

### 7.4 만약 modeling 세션의 추가 endpoint 가 필요해지면

simulation 세션이 직접 modeling 코드를 만들지 않는다. 대신:

1. simulation 세션이 `02-ontology-api-additions.md` 또는 본 패키지에 endpoint 추가 명세를 작성
2. 사용자 (또는 다음 modeling 세션) 가 modeling 영역에 endpoint 구현
3. simulation 세션은 그 endpoint 를 HTTP / facade 로 호출

이로써 두 영역의 책임 경계가 시간에 따라 흐려지지 않음.

### 7.5 dispatch 정합성 체크의 cross-session 흐름

```
  simulation 세션 (본 모듈)              modeling 세션 (Section 2)
  ──────────────────────────            ──────────────────────────
  JavaSandbox.dispatch() ─────HTTP─────▶ GET /api/ontology/actions/{fqn}
                                          /realizations-for-input?code_type_fqn=X
                          ◀─────────── list[RealizationDTO]
  
  selected = realizations[0]
  jvm.invoke(selected.method_fqn, ...)
                          
  결과: dispatch_consistent flag 를 본 모듈 안에서 결정
        (modeling 의 storage 변경 없음)
```

modeling 세션은 read-only 로 응답만 한다. dispatch_consistent 의 verdict 영향 (04 Section 3.2 (f)) 는 simulation 세션 안에서 완결.

---

## 8. design-gaps 와의 매핑

| design-gap # | 본 명세 가 해소 |
|---|---|
| #4 시뮬 input fixture | Section 3 (LookupDataSource 3 mode) |
| #5 Java dispatch sandbox | Section 2 (JavaSandbox 3-tier + 알고리즘) |
| #41 lookups row 형식 (Phase D 검수) | Section 3.2 (TableSpec + LookupRow) |
| #39 anchor invalidation T4/T5 (Phase D 검수, 부분) | Section 7 의 modeling 측 endpoint 추가 흐름으로 해소 가능. 본 명세 직접 영향 없음 |

---

## 9. 구현 순서 권장

| # | 단계 | 의존 |
|---|---|---|
| 1 | `JavaSandbox.stub` 구현 (Section 2.5 의 stub backend) | 03 RunHandle / 04 ChangeSpec |
| 2 | PythonGenerator 의 단순 case (delegation depth=0 의 pure_function Action) | 1 |
| 3 | LookupDataSource fixture_only 모드 | 3.4 |
| 4 | Runner orchestrator + state machine (in-process queue) | 1 + 2 + 3 |
| 5 | verdict 판정 + auto-promote / auto-downgrade hook | 04 Section 3 |
| 6 | JavaSandbox.jvm_subprocess 구현 (실 JVM 호출 + 직렬화) | 1 |
| 7 | anchor / br capture instrumentation jar | 6 |
| 8 | LookupDataSource 의 fixture_with_db_fallback / db_snapshot | 3 |
| 9 | Redis 큐 (외부 운영) | 4 |

---

## 10. 검증 방법

| 단계 | 검증 |
|---|---|
| 1 | stub 으로 ChangeSpec → SimResult round-trip 동작 (verdict=sim_verified case) |
| 2 | atomic_overrides 1개 적용 → output_values 변동 확인 (Phase A drama) |
| 3 | jvm_subprocess 로 실 메서드 호출 → P-2018-0098 회귀 (verdict=sim_violation, br=DG003.WidthMin) |
| 4 | dispatch_consistent=False 케이스 (input runtime type 다른 경우) → verdict=inconclusive |
| 5 | anchor invalidation 후 deferred → verdict=inconclusive |
| 6 | timeout 케이스 → status=failed, partial_outputs 보존 |
| 7 | 100 동시 run (load) → queue_depth health endpoint 정상 |

---

마지막 업데이트: 2026-05-10
