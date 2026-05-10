# STEP 3b-1 — Runner contract 모델 + LookupDataSource 신설

**완료일**: 2026-05-10
**브랜치**: `section3-integration`
**의존**: `toClaude/modeling/handoff-spec/05-runner-interface.md` (Section 1, 2, 3, 4.6, 4.8)

## 목표

06-developer-onboarding.md 의 STEP 3.1 7개 신설 파일 중 첫 번째 runner 파일 도입. spec 05 의 runner-side 모델을 contracts 에 추가하고, `LookupDataSource` (fixture_only 모드) 구현.

## 작업 내용 (TDD)

### 1. 테스트 먼저 (`tests/simulation/`)

24 test 작성:

- **`test_runner_models.py` 15 test** — Runner 모델 invariant
  - `TypedValue` (1) — `_type` alias + value
  - `RunPlan` (2) — minimal / with delegates_to_tree + expected_brs
  - `RunInputs` (1) — slots / overrides / primary_input_slot
  - `GeneratedScript` (1) — minimal
  - `AnchorHit / BRTrigger / DispatchResult / SandboxCapabilities` (5) — passed/violated/invalid backend 거부
  - `TableSpec / LookupRow` (2) — columns + drama_dna_columns
  - `FailurePolicy` (2) — defaults + custom for drama

- **`test_lookup_source.py` 9 test** — LookupDataSource fixture_only 모드
  - get / list / validate (clean / unknown table) — 5 test
  - `_derive_table_specs` — atomic_fqn 매핑된 field 만 columns 로 / is_pk 없는 CodeType skip — 2 test
  - Phase C P-2018-0098 회귀 fixture (CustomerStd:7 + HrSpec:HR-23-A) — 1 test
  - 기본 list 빈 결과 — 1 test

→ TDD red phase 24/24 fail.

### 2. 코드 작성

#### `backend/shared/contracts/simulation.py` 11 모델 추가 (+220 lines)

| 모델 | 출처 | 비고 |
|---|---|---|
| `TypedValue` | spec 05 §5.5 | `_type` alias (Pydantic v2 underscore-private 회피) |
| `RunPlan` | spec 04 §3.3 | delegates_to_tree / expected_brs (direct/transitive) / expected_anchors |
| `RunInputs` | spec 05 §4.6 | slots / fixture (duck-typed) / overrides / primary_input_slot |
| `GeneratedScript` | spec 05 §1.2 | source_code / entrypoint / imports 화이트리스트용 |
| `AnchorHit` | spec 05 §2.2 | JVM agent capture |
| `BRTrigger` | spec 05 §2.2 | passed/violated/skipped + violation_path |
| `DispatchResult` | spec 05 §2.2 | outputs + dispatch_consistent + captured_anchors/brs |
| `SandboxCapabilities` | spec 05 §2.4 | Literal["jvm_subprocess","graalvm_polyglot","stub"] |
| `TableSpec` | spec 05 §3.2 | code_type_fqn + pk_atom_fqn + columns + drama_dna_columns |
| `LookupRow` | spec 05 §3.2 | pk + table_spec_fqn + columns dict |
| `FailurePolicy` | spec 05 §4.8 | 4 정책 (dispatch_error/br_violation/anchor_miss/dispatch_inconsistent) |

모든 모델 `ConfigDict(extra="forbid")` — schema 외 필드 거부.

#### `backend/simulation/runner/__init__.py` 신설

모듈 docstring + section isolation 명시 (modeling internal layer 직접 import 금지).

#### `backend/simulation/runner/lookup_source.py` 신설 (+165 lines)

`LookupDataSource` 클래스 — fixture_only 모드:

- `_OntologyClientProtocol` — duck-typed (list_code_types(role=...) 만)
- `_derive_table_specs(client)` — spec 05 §3.4 알고리즘 1~4
  - role='lookup_table' 후보 수집
  - is_pk=True 첫 field 의 atomic_fqn 을 PK
  - atomic_fqn 매핑된 field 만 columns 로 (raw java field 제외)
  - drama_dna_kind 마킹된 field → drama_dna_columns
- `_index_fixture(fixture)` — `{(table_spec_fqn, pk) → LookupRow}` 인덱스
- `get / list / validate / table_specs / metadata` 5 public method

### 3. 회귀 검증

| 검증 | 결과 |
|---|---|
| `test_runner_models.py + test_lookup_source.py` | **24/24 GREEN** |
| 전체 `tests/simulation/` | 219 passed (이전 195 → +24), 17 skipped |
| 3 failure | sample-repos/slab-design 부재 (STEP 3a/3b1 무관) |
| Section isolation | ✅ modeling internal layer import 0건 |

## 주요 결정

- **`TypedValue.type_` + `alias='_type'`** — Pydantic v2 가 `_type` 을 private 로 처리하므로 public 필드는 `type_`. JSON 직렬화 시 `_type` 으로 노출 (`populate_by_name=True`).
- **`RunInputs.fixture` 는 `Optional[Any]`** — LookupDataSource 인스턴스 (Pydantic 외 타입). `arbitrary_types_allowed=True`. 직접 import 시 순환 회피 (LookupDataSource → simulation.py → ... 위험).
- **`_OntologyClientProtocol` duck-typed** — modeling 측 OntologyQueryClientImpl 가 아직 우리 simulation 에 안 wire 됐으므로 Protocol 만 정의. 실제 wiring 은 STEP 3b-4 orchestrator 에서.
- **`_derive_table_specs` 의 graceful failure** — `list_code_types` 호출 실패 시 빈 dict 반환 (warning log). modeling 미가용 환경에서도 LookupDataSource 자체는 동작.

## 호환성

- 기존 simulation 코드 (sandbox / agents / jvm_bridge) 와 병존. `lookup_source.py` 는 신규 모듈, 기존 import 영향 없음.
- 기존 `backend/simulation/sandbox/runner.py` 와 충돌 없음 (다른 폴더, 다른 책임).

## Diff stat

- `backend/shared/contracts/simulation.py` — +220 lines (11 모델 추가)
- `backend/simulation/runner/__init__.py` — 신규 +12 lines
- `backend/simulation/runner/lookup_source.py` — 신규 +165 lines
- `tests/simulation/test_runner_models.py` — 신규 +180 lines
- `tests/simulation/test_lookup_source.py` — 신규 +200 lines

## 다음 sub-step

| step | 내용 |
|---|---|
| **3b-2** | `java_sandbox.py` — `JavaSandbox` Protocol + `StubJavaSandbox` (spec 05 §2.5 의 stub backend, §3.4.5 anchor/BR auto-hit) |
| **3b-3** | `python_generator.py` — `PythonGenerator` (echo-stub, spec 05 §1.3 단순화) |
| **3b-4** | `orchestrator.py` — `Orchestrator.run()` (running 단계 entry, spec 05 §4.5) + end-to-end test (verdict=sim_verified) |
