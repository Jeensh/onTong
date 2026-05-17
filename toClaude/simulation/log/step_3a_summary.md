# STEP 3a — ChangeSpec / SimResult Pydantic schema 신설

**완료일**: 2026-05-10
**브랜치**: `section3-integration`
**의존**: `toClaude/modeling/handoff-spec/04-changespec-simresult-schema.md`

## 목표

06-developer-onboarding.md 의 STEP 3.1 7개 신설 파일 중 첫 번째 — `backend/shared/contracts/simulation.py` (ChangeSpec / SimResult Pydantic 모델) 도입. spec 04 §1~§2 의 schema 를 1:1 로 옮김.

## 작업 내용 (TDD)

### 1. 테스트 먼저 (`tests/simulation/test_changespec_schema.py`)

19 test 작성 — 7 모델별 invariant + 3 통합 시나리오 (Phase A drama / Phase B drama DNA proc[1]=HR / Phase C P-2018-0098 회귀):

- `ChangeSpec` 4 test (minimal / atomic_overrides / scenario_fixture / action_fqn 필수)
- `CreateRunRequest` 2 test (minimal / scenario_id+requested_by)
- `BREvidence` 3 test (passed / violated / invalid outcome 거부)
- `AnchorEvidence` 2 test (hit / deferred)
- `DelegationTraceFrame` 3 test (consistent / mismatch / in_loop)
- `SimResult` 4 test (sim_verified / sim_violation / inconclusive / invalid verdict 거부)
- 통합 1 test (Phase B 시연 — drama DNA proc[1]=HR 흐름)

→ TDD red phase 19/19 fail (코드 없음).

### 2. 코드 작성 (`backend/shared/contracts/simulation.py`)

7 BaseModel — `model_config = ConfigDict(extra="forbid")` 로 schema 엄수:

| 모델 | 필드 |
|---|---|
| `ChangeSpec` | `action_fqn`, `atomic_overrides`, `scenario_fixture` |
| `RunOptions` | `sandbox_tier` (Literal 3-tier), `dry_run` — spec 03 RunOptions 정의 후 보강 예정 |
| `CreateRunRequest` | `change_spec`, `scenario_id?`, `run_options?`, `requested_by?` |
| `BREvidence` | `br_fqn`, `severity`, `enforcer_method_fqn?`, `outcome` (passed/violated/skipped), `violation_path?`, `expected?`, `actual?`, `operational_history_refs[]` |
| `AnchorEvidence` | `anchor_id`, `marker`, `method_fqn`, `line`, `outcome` (hit/miss/deferred), `captured_value?` |
| `DelegationTraceFrame` | `seq`, `depth`, `action_fqn`, `realized_method_fqn?`, `dispatch_consistent`, `dispatch_mismatch_reason?`, `inputs_summary`, `outputs_summary?`, `duration_ms`, `in_loop_iter?`, `error?` |
| `SimResult` | `run_id`, `status`, `verdict`, `br_evidence[]`, `anchor_evidence[]`, `output_values`, `delegation_trace[]`, `affected_design_gaps[]`, `failure_reason?`, `started_at`, `completed_at`, `duration_ms`, `change_spec_ref` |

→ TDD green phase 19/19 pass.

### 3. 회귀 검증

- 전체 `tests/simulation/`: **195 passed, 17 skipped, 3 failed**
- 3 failure 모두 `sample-repos/slab-design/` 폴더 부재가 원인 (`commit 2a346e3` 의 옵션 A 정렬 영향). STEP 3a 작업과 무관.
- Section isolation 검사 통과 (modeling 직접 import 0건).

## 주요 결정

- **Pydantic v2 + extra="forbid"** — spec 04 외 추가 필드 거부. 호환성 위험 조기 발견.
- **`Literal` 으로 verdict / outcome / severity 제한** — typo 방지 + IDE autocomplete.
- **`RunOptions` minimal 시작** — sandbox_tier 3-tier 와 dry_run 만. spec 03 의 RunOptions 정의 후 보강 (POST /runs body schema 와 매칭).
- **기존 simulation 코드 (sandbox/agents/jvm_bridge) 와 병존** — ChangeSpec 흐름은 별도 router/runner 로 도입 예정. 본 모듈은 그 entry contract.

## Phase E backlog 미결정 (STEP 4 진행 시 부딪힘)

- `#41` `lookups` row 형식 — 본 schema 는 `dict[str, Any]` 로 받아두고, 첫 시나리오 작성 시 굳히기.
- `#49` atomic ↔ method-arg 매핑 — atomic_overrides path 해석 알고리즘 (spec 04 §1.2) 의 step 2 (broadcast) 가 첫 시나리오로 검증.

## Diff stat

- `backend/shared/contracts/simulation.py` — 신규 +173 lines
- `tests/simulation/test_changespec_schema.py` — 신규 +260 lines

## 다음 step (3b 후보)

| 후보 | 의존 |
|---|---|
| `backend/simulation/runner/` 폴더 + `lookup_source.py` (spec 05 §3, fixture 모드만) | spec 05 |
| `backend/simulation/runner/python_generator.py` (echo-stub) | spec 05 §1 |
| `backend/simulation/api/run_handle.py` (run lifecycle state machine) | spec 03 |
| spec router 신설 — `backend/simulation/api/spec_router.py` (POST /runs / GET /runs/{id}/sim-result) | 본 모듈 + run_handle |

→ 사용자 승인 후 결정.
