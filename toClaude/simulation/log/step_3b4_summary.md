# STEP 3b-4 — Orchestrator (running 단계 entry + e2e sim_verified)

**완료일**: 2026-05-10
**브랜치**: `section3-integration`
**의존**: `toClaude/modeling/handoff-spec/05-runner-interface.md` (Section 4.5/4.6/4.8) + `04-changespec-simresult-schema.md` (Section 3.2/3.6)

## 목표

06-developer-onboarding.md 의 STEP 3.1 7개 신설 파일 중 네 번째 — running 단계의 모든 책임을 한 곳에 모은 entry. spec 05 §4.5 의 `Orchestrator.run()` 단순화 구현 + spec 04 §3.2 verdict 6 조건 단순 판정 + **e2e sim_verified 회로 검증**.

## 작업 내용 (TDD)

### 1. 테스트 먼저 (`tests/simulation/test_orchestrator.py` +400 lines)

16 test 작성 (이전 step 의 Fake DTO 패턴 재사용):

| 영역 | 검증 |
|---|---|
| SimResult 기본 (5) | run_id / status=completed / 타임스탬프 / change_spec_ref / SimResult 인스턴스 |
| delegation_trace (2) | N edge → N frame / dispatch_consistent 전파 |
| verdict 판정 (3) | sim_verified (all pass + consistent) / inconclusive (inconsistent) / vacuously true (BR/anchor 0건) |
| evidence aggregation (3) | BRTrigger → BREvidence (severity 매핑) / AnchorHit → AnchorEvidence (method_fqn) |
| factory (1) | lookup_source_factory(fixture) 호출 확인 |
| **e2e (1)** | **Phase C P-2018-0098 회귀 → sim_verified** (drama DNA anchor + BR auto-pass + dispatch consistent) |
| failure (1) | sandbox raise → status=failed + verdict=inconclusive + failure_reason 채움 |

→ TDD red phase 16/16 fail, green phase 16/16 pass.

### 2. 코드 작성

#### `backend/simulation/runner/orchestrator.py` 신설 (+260 lines)

**클래스 — `Orchestrator`** (3개 의존성 inject):

| 의존성 | Protocol | 역할 |
|---|---|---|
| `python_generator` | `_PythonGeneratorProtocol` | GeneratedScript artifact 합성 |
| `java_sandbox` | `_JavaSandboxProtocol` | dispatch loop 의 backend |
| `lookup_source_factory` | `Callable[[fixture dict], LookupDataSource]` | per-run lookup_source 생성 |

**`run(change_spec, run_plan, run_options) -> SimResult`** spec 05 §4.5 8 step 단순화:

1. `lookup_source = factory(scenario_fixture)` (per-run)
2. `python_generator.generate(...)` (artifact 용 — exec 안 함)
3. `_build_run_inputs(...)` — primary_input_type (edge 의 `primary_input_type` 또는 후속 build_slots)
4. dispatch loop — 각 edge → `java_sandbox.dispatch(...)` + `DelegationTraceFrame` append + anchor/br 누적
5. evidence 매핑 — `BRTrigger → BREvidence` (severity: violated→error / 그 외→info), `AnchorHit → AnchorEvidence` (method_fqn 은 realized 우선)
6. **verdict 판정** (spec 04 §3.2 단순화):
   - `sim_violation`: BR(violated, severity=error) ≥1
   - `sim_verified`: 모든 BR passed + 모든 anchor hit + 모든 frame dispatch_consistent (vacuously true 도 OK)
   - `inconclusive`: 위 둘 외 (포함: status=failed)
7. `change_spec_ref = sha256(canonical_json)[:16]` — 재현 검증용
8. `SimResult` 빌드 (run_id / 타임스탬프 / duration_ms / 모든 evidence)

**failure policy** — 첫 iter 는 fail_fast 만 (sandbox 예외 → break + status=failed). 후속에서 spec 05 §4.8 의 4가지 정책 (`continue` / `abort_after_n` / BR-violation continue) 보강.

### 3. 회귀 검증

| 검증 | 결과 |
|---|---|
| `test_orchestrator.py` | **16/16 GREEN** |
| 전체 `tests/simulation/` | **262 passed** (이전 246 → +16), 17 skipped |
| 3 failure | sample-repos/slab-design 부재 (STEP 3b-4 무관) |
| Section isolation | ✅ modeling internal layer import 0건 (모두 duck-typed Protocol) |
| **e2e sim_verified 회로** | ✅ Phase C P-2018-0098: drama DNA anchor + BR auto-pass + dispatch_consistent → verdict=sim_verified |

## 주요 결정

- **generated source_code 는 artifact 만** — 첫 iter 는 본 모듈이 직접 dispatch loop 실행. 후속 iter (3b-5+) 에서 ast 기반 안전 실행 / sandboxed exec 보강.
- **`primary_input_type` 은 edge 에 명시 필요** — spec 05 §4.6 의 build_slots 알고리즘 (Action.params 분석) 은 미구현. 첫 iter 는 `delegates_to_tree[i].primary_input_type` 에서 추출. 후속에서 OntologyClient.get_action 으로 derive.
- **`atomic_overrides` 적용 미구현** — `RunInputs.overrides` 에 그대로 dump. spec 04 §1.2 의 4-rule algorithm 은 후속 iter (orchestrator 또는 별도 patcher).
- **verdict vacuously true** — BR 0건 + anchor 0건 + dispatch_consistent 만 충족하면 sim_verified. spec 04 §3.6 의 "expected_brs 누락은 inconclusive" 정책은 후속 iter (expected_brs 를 RunPlan 에서 주입 받아야 가능).
- **`severity` 매핑** — BRTrigger 는 severity 없음. orchestrator 가 outcome=violated→error / 그 외→info 로 매핑. 후속에서 ontology_client 의 BR.severity 직접 조회 보강.
- **`method_fqn` 매핑** — AnchorEvidence.method_fqn 은 realized_method_fqn 우선. realization 미발견 시 빈 문자열. binding.code_method_fqn 은 미사용 (anchor 가 capture 된 실 method 가 더 정확).
- **`change_spec_ref` 형식** — `sha256:{16_hex}` (canonical JSON 의 sha256 16자). spec 04 §2.1 의 명세는 형식 미고정 — 본 형식은 구현 결정.
- **failure mode** — sandbox 예외만 status=failed (fail_fast). lookup_source / python_generator 예외는 graceful warning + continue (lookup_source 는 미구현, python_generator 는 generate() 만 호출하므로 critical 아님).

## 호환성

- 기존 simulation 코드 (sandbox / agents / jvm_bridge) 와 병존. `orchestrator.py` 는 신규 모듈, 기존 import 영향 없음.
- 3b-1 (LookupDataSource) + 3b-2 (StubJavaSandbox) + 3b-3 (PythonGenerator) 가 e2e 로 묶여 verdict=sim_verified 회로 통과 — Section 3 의 핵심 흐름 검증 완료.

## Diff stat

- `backend/simulation/runner/orchestrator.py` — 신규 +260 lines
- `tests/simulation/test_orchestrator.py` — 신규 +400 lines

## 다음 sub-step

| step | 내용 |
|---|---|
| **3b-5** | `api/run_handle.py` (spec 03 — RunHandle state machine: pending/running/completed/failed/cancelled) |
| **3b-6** | `api/spec_router.py` (spec 03 — POST /api/simulation/runs / GET /api/simulation/runs/{id}/sim-result) + main.py 등록 |
| **STEP 4.1+** | 첫 시나리오 ChangeSpec → SimResult 흐름 (`action.scm.std.match_customer_limit_for_order`) — Phase E #41 lookups schema 확정 |

## 마일스톤 의의

STEP 3b-1~3b-4 통과 = **Section 3 의 spec 05 runner core 4 컴포넌트 (LookupDataSource / PythonGenerator / JavaSandbox / Orchestrator) 완성**. 이제 spec 03 의 REST API 만 wiring 하면 외부에서 시뮬 호출 가능. e2e 의 sim_verified 회로 검증으로 verdict 판정 회로 정합성 확인.
