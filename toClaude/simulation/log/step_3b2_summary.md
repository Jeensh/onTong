# STEP 3b-2 — JavaSandbox Protocol + StubJavaSandbox

**완료일**: 2026-05-10
**브랜치**: `section3-integration`
**의존**: `toClaude/modeling/handoff-spec/05-runner-interface.md` (Section 2 + §3.4.5 + §7.1)

## 목표

06-developer-onboarding.md 의 STEP 3.1 7개 신설 파일 중 두 번째 — Java dispatch sandbox 추상 인터페이스 + 가장 가벼운 stub tier 구현. spec 05 §2 의 3-tier 중 **stub 만 본 step**, jvm_subprocess / graalvm 은 후속.

## 작업 내용 (TDD)

### 1. 테스트 먼저 (`tests/simulation/test_java_sandbox.py` +330 lines)

13 test 작성:

| # | 영역 | 검증 |
|---|---|---|
| 1 | Protocol | `JavaSandbox.dispatch` 시그니처 존재 |
| 2~3 | 인스턴스화 | `SandboxCapabilities.backend='stub'` 만 받음 / 'jvm_subprocess' 거부 |
| 4~5 | dispatch 기본 | DispatchResult 반환 / `duration_ms=0` + `jvm_log='[stub mode]\\n'` |
| 6 | realization 선택 | `get_realizations_for_input_type[0].code_method_fqn` → `realized_method_fqn`, `dispatch_consistent=True` |
| 7~8 | inconsistent | realization 없음 → consistent=False + reason / primary_input_slot=None → reason="primary_input not declared" |
| 9 | anchor auto-hit | `get_anchor_bindings_for_action` 의 모든 binding → `AnchorHit` (id, anchor_locator → marker) |
| 10 | BR auto-pass | `Action.preconditions + postconditions` → `BRTrigger(passed)` |
| 11 | graceful | `get_action()=None` 시 BR 빈 리스트 |
| 12 | outputs 기본 | `outputs={}` (echo 미구현) |
| 13 | P-2018-0098 회귀 | drama DNA "자리 1 = HR" anchor capture + sim_verified 가능한 복합 시나리오 |

→ TDD red phase 13/13 fail, green phase 13/13 pass.

### 2. 코드 작성

#### `backend/simulation/runner/java_sandbox.py` 신설 (+200 lines)

**Protocol — `JavaSandbox`**:
- `@runtime_checkable` Python Protocol — duck-typed dispatch interface
- 단일 메서드 `dispatch(action_fqn, inputs: RunInputs, run_options: RunOptions) -> DispatchResult`
- 3-tier 구현체 swap 의 추상 (stub/jvm_subprocess/graalvm)

**클래스 — `StubJavaSandbox`**:

| 단계 | 동작 | spec 05 § |
|---|---|---|
| 1 | `__init__` 에서 `capabilities.backend != 'stub'` 거부 | §2.5 |
| 2 | `_select_realization` — primary_input_slot 의 `_type` 으로 realization 조회, 첫 번째 선택 | §2.3 step 1~3 단순화 |
| 3 | `_capture_anchors` — `get_anchor_bindings_for_action` → `AnchorHit` 변환 | §3.4.5 step 3 |
| 4 | `_capture_brs` — `Action.preconditions + postconditions` → `BRTrigger(passed)` | §3.4.5 step 4 |
| 5 | `outputs={}` (echo 미구현 — 후속 iteration) | §3.4.5 step 5 |
| 6 | `duration_ms=0`, `jvm_log='[stub mode]\\n'` | §3.4.5 합의 |

**duck-typed `_OntologyClientProtocol`** — 3 메서드만:
- `get_action(fqn)` — Action.preconditions/postconditions 추출
- `get_realizations_for_input_type(action_fqn, code_type_fqn)` — 다형성 dispatch
- `get_anchor_bindings_for_action(action_fqn)` — anchor capture

**Graceful failure** — modeling facade 호출 실패 (`Exception`) 시 warning log + 빈 결과 (sandbox 자체는 동작 계속). Section 3 가 modeling 미가용 환경에서도 unit test 가능.

#### `backend/simulation/runner/__init__.py` — 미수정

기존 docstring 의 java_sandbox 항목이 이미 본 step 의 책임을 명시.

### 3. 회귀 검증

| 검증 | 결과 |
|---|---|
| `test_java_sandbox.py` | **13/13 GREEN** |
| 전체 `tests/simulation/` | **232 passed** (이전 219 → +13), 17 skipped |
| 3 failure | sample-repos/slab-design 부재 (STEP 3b-2 무관) |
| Section isolation | ✅ modeling internal layer import 0건 |

## 주요 결정

- **`Action.realizes` 역포인터 검증 단순화** — spec 05 §2.3 step 3 의 `parent_action.inputs[primary].type_fqn` 비교는 우리 schema 에 `realizes` field 없음 (Action.realizations 정방향만). stub 첫 iter 는 realization 발견 = consistent=True, 미발견 = False 로 처리. 후속: modeling 측에 `Action.realizes_action_fqn` 추가 명세 시 보강.
- **`AnchorBinding.marker` / `line` 미존재** — 우리 mapping_layer.AnchorBinding 은 `id`, `anchor_locator`, `code_method_fqn` 만. 본 step 에서 `marker = anchor_locator`, `line = 0` default 로 매핑. 후속: code_method 의 line range 가 mapping 가능해지면 보강.
- **BR 시나리오 분기 (`scenario.kind=br_violation`) 후속 처리** — spec 05 §3.4.5 의 violation 시나리오 violated 처리는 첫 iter 미구현. orchestrator (3b-4) 가 `ChangeSpec.scenario_fixture.metadata` 의 hint 로 결정 가능 시 보강.
- **`@runtime_checkable` Protocol** — duck-typed 검증 (`isinstance(sandbox, JavaSandbox)`) 가능. orchestrator 가 swap 검증 시 사용.
- **`RunOptions.timeout_sec` 미존재 발견** — 현재 schema 는 `sandbox_tier` + `dry_run` 만. spec 05 §4.7 의 TimeoutBudget 도 후속 step 에서 `RunOptions` 확장과 함께 도입.

## 호환성

- 기존 simulation 코드 (sandbox / agents / jvm_bridge) 와 병존. `java_sandbox.py` 는 신규 모듈, 기존 import 영향 없음.
- 기존 `backend/simulation/sandbox/runner.py` 와 충돌 없음 (다른 폴더, 다른 책임 — sandbox/ 는 옛 ad-hoc Python 실행, runner/ 는 spec 05 의 새 추상).
- `LookupDataSource` (3b-1) 와 같은 duck-typed Protocol 패턴 — 두 모듈 일관성.

## Diff stat

- `backend/simulation/runner/java_sandbox.py` — 신규 +200 lines
- `tests/simulation/test_java_sandbox.py` — 신규 +330 lines

## 다음 sub-step

| step | 내용 |
|---|---|
| **3b-3** | `python_generator.py` — `PythonGenerator` (echo-stub, spec 05 §1.3 단순화) |
| **3b-4** | `orchestrator.py` — `Orchestrator.run()` (running 단계 entry, spec 05 §4.5) + end-to-end test (verdict=sim_verified) |
