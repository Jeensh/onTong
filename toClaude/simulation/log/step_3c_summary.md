# STEP 3c — Section 3 ↔ Section 2 ontology 실데이터 통합 (★ NullOntologyClient 제거)

**완료일**: 2026-05-10
**브랜치**: `section3-integration`
**의존**: STEP 3.1 (3a / 3b-1~6) 종결 + `backend.modeling.api.ontology_query.OntologyQueryClientImpl` 사용 가능

## 목표

STEP 3.1 종결 시점의 critical 갭 해소 — spec_router 의 default 가 `_NullOntologyClient` 이라서 POST /runs 호출 시 항상 `verdict=inconclusive`. **실 modeling.api.ontology_query.OntologyQueryClientImpl 을 default 로 wire** + RunPlan 도 modeling facade 호출로 빌드. echo-stub 의 하드코딩 (`primary_input_type="scm.order.Order"`) 완전 제거.

## 작업 내용 (TDD)

### 1. RunPlanBuilder 신설 (`runner/run_plan_builder.py` +175 lines)

**의존성**: duck-typed `_OntologyClientProtocol` (4 메서드: get_action / get_anchor_bindings_for_action / get_realizations_for_input_type / list_code_types).

**`build(action_fqn, max_depth=10) → RunPlan`** 알고리즘:
1. BFS — root → sub_actions recursive (cycle / max_depth / unknown 처리)
2. 각 frame 의 `primary_input_type` derive:
   - 1순위: `action.realizations[0].applies_to_code_type_fqn`
   - 2순위: `action.params[0].object_ref_term` (object_ref 파라미터)
   - 미상이면 None — sandbox 가 fallback 처리
3. `expected_brs.direct` = root.preconditions + postconditions
4. `expected_brs.transitive` = sub action 의 BR fqn (- direct)
5. `expected_anchors` = ⋃ get_anchor_bindings_for_action(fqn).map(.id)
6. graceful failure — facade 예외 시 `warnings` 누적, 빈 결과 반환

**TDD test** (`test_run_plan_builder.py` +220 lines, 12 test):
- 단일 frame / sub_actions BFS / cycle / max_depth / expected_brs direct+transitive / anchors union / primary_input_type 3 derivation / unknown action / ontology raise recovery

### 2. StubJavaSandbox `_select_realization` fallback 추가

**문제**: 실 ontology 의 많은 action 이 `realizations[0].applies_to_code_type_fqn=None` (base method, no subtype filter). 또는 action.params 가 비어있어 RunPlanBuilder 가 `primary_input_type` 을 derive 못 함. 이전 strict 셀렉터는 이 경우 항상 inconsistent.

**해결**:
1. primary_input_slot 있고 + `get_realizations_for_input_type` 매칭 0건 → `get_action(fqn).realizations[0]` fallback
2. primary_input_slot=None → 같은 fallback (object_ref 미참조 action)
3. fallback 도 실패하면 기존처럼 inconsistent

**테스트 추가** (`test_java_sandbox.py` +2 test = 15 total):
- primary_input unknown 시 action.realizations[0] fallback → consistent=True
- primary_type 별 realization 0건 시 fallback 동작

이전 strict 동작은 `_select_realization_legacy()` 로 보존 (호출 안 됨 — 임시 코드 미삭제 정책).

### 3. spec_router default 교체 (`api/spec_router.py` 수정)

**핵심 교체**:
- `_build_default_orchestrator()` 가 `_NullOntologyClient` → `OntologyQueryClientImpl()` 인스턴스 사용 (graceful fallback 포함)
- `_build_minimal_run_plan()` (1-frame echo + 하드코딩 `"scm.order.Order"`) 제거 → `RunPlanBuilder` 가 modeling facade 로 RunPlan 빌드
- `get_run_plan_builder()` Depends getter 신설
- `reset_singletons()` test 헬퍼 신설 (의존성 교체 시 사용)
- `_NullOntologyClient` 클래스 보존 (test override / 비상 fallback 용 — 더 이상 default 아님)
- `_build_default_ontology_client()` 가 modeling facade 인스턴스화 실패 시 `_NullOntologyClient` 로 graceful fallback (router 자체는 부팅 보장)

기존 test (`test_spec_router.py` 13/13) 가 `get_run_plan_builder` override 추가 후 모두 GREEN 유지.

### 4. 실 ontology 통합 test 신설 (`test_ontology_integration.py` +180 lines, 5 test)

- `_build_default_ontology_client()` 가 OntologyQueryClientImpl 또는 fallback `_NullOntologyClient` 반환
- orchestrator + run_plan_builder 가 같은 ontology client singleton 공유
- 실 ontology DB 의 첫 action 으로 RunPlan 빌드 시 frame ≥1 + estimated_steps 정합
- unknown action_fqn → warnings 채움
- **POST /runs 가 실 ontology 호출 — realization 있는 action 은 dispatch_consistent=True**

DB 가 비어있으면 `pytest.skip` (CI 환경 호환).

### 5. 회귀 + 실 서버 sanity

| 검증 | 결과 |
|---|---|
| `test_run_plan_builder.py` | **12/12 GREEN** |
| `test_java_sandbox.py` (기존 13 + fallback 2) | **15/15 GREEN** |
| `test_spec_router.py` (Depends override 추가) | **13/13 GREEN** |
| `test_ontology_integration.py` | **5/5 GREEN** (실 DB 1514 actions) |
| 전체 `tests/simulation/` | **314 passed** (이전 295 → +19), 17 skipped, 3 failed (sample-repos — 무관) |
| Section isolation | ✅ — `backend.modeling.api.ontology_query` facade import 만 (internal layer 0건) |

### 6. 실 서버 sanity (curl)

**수치 비교** (이전 STEP 3.1 종결 시점 vs STEP 3c 종결 후):

| 시나리오 | 이전 (NullOntologyClient) | 현재 (실 ontology) |
|---|---|---|
| `syn1.action.scm.final_length_range_실행` (single, has realization) | verdict=inconclusive | **verdict=sim_verified** ★ |
| `action.scm.슬랩설계_실행` (workflow, 21 sub_actions) | 1 frame, inconsistent | **22 frames, 21 sub-actions consistent=True, 7 anchor_evidence** ★ |
| dispatch_consistent | 항상 False | sub-action 별 정상 (workflow root 만 False) |

★ **실 ontology DB 의 realization / anchor_binding 데이터가 sandbox 에 도달함을 확인** — 더 이상 Null/Mock 로 차단되지 않음.

## 주요 결정

- **graceful fallback 유지** — `_build_default_ontology_client()` 가 OntologyQueryClientImpl 인스턴스화 실패 시 `_NullOntologyClient` 로 fallback. router 자체는 부팅 보장. 운영 환경 (DB 정상) 에선 실 facade 가 default.
- **`_NullOntologyClient` 보존** — 사용자 지시 "지우진말고". test override / 비상 fallback 용으로 유지. default 가 아님을 docstring 명시.
- **`_select_realization_legacy()` 보존** — 이전 strict 셀렉터. 새 fallback 셀렉터로 대체됐지만 호환/문서화 위해 보존 (호출 0건).
- **singleton ontology_client 공유** — orchestrator 와 run_plan_builder 가 같은 인스턴스 사용 (single source of truth + 캐시 효율).
- **`reset_singletons()`** — test 격리용. 의존성 교체 시 호출.
- **Section isolation** — `backend.modeling.api.ontology_query` facade 만 import. modeling 의 internal layer (mapping/code/domain/persistence) 직접 import 0건.

## 호환성

- 기존 8 simulation routers (sandbox / agents / scenarios / jobs / bridge / transpile / auto_pr / seed / differential) 와 옛 mock JSON fixtures 그대로 — 미수정 (사용자 지시).
- 옛 `_NullOntologyClient` / `_select_realization_legacy` 코드 보존.
- Section 3 의 spec 03/04/05 신경로만 실 ontology wire — 사용자 옵션 1 채택 (권장 안).

## Diff stat

- `backend/simulation/runner/run_plan_builder.py` — 신규 +175 lines
- `backend/simulation/runner/java_sandbox.py` — fallback +50 lines / legacy 보존
- `backend/simulation/api/spec_router.py` — default 교체 + getter 추가 (+50 lines, -25 lines)
- `tests/simulation/test_run_plan_builder.py` — 신규 +220 lines (12 test)
- `tests/simulation/test_java_sandbox.py` — fallback test +50 lines (2 test)
- `tests/simulation/test_spec_router.py` — Depends override 추가 (3 lines)
- `tests/simulation/test_ontology_integration.py` — 신규 +180 lines (5 test)

## 남은 통합 backlog (운영화 보강)

본 step 으로 **infra wiring 은 완료**. 후속 보강 항목:

1. **lookups schema 형식 확정** (Phase E #41) — `LookupDataSource` 가 ontology 의 `list_code_types(role='lookup_table')` 를 호출하나, 현재 ontology 데이터에 `role='lookup_table'` 마킹된 CodeType 적음. 시나리오 작성 시 보강.
2. **ChangeSpec.atomic_overrides 적용** — `Orchestrator._build_run_inputs` 가 dump 만. spec 04 §1.2 4-rule patcher 후속.
3. **delegates_to_tree depth/loop/optional** — 현재 BFS 만. spec 05 §1.3 step 4c 의 `is_in_loop` / `optional` 분기는 미적용.
4. **ChangeSpec scenario_fixture.lookups → LookupDataSource** — fixture 가 비어있어도 sandbox 가 lookup 호출 안 함 (echo-stub 의 한계). 실 시나리오 작성 시 fixture 채워 넣어야 sandbox 가 데이터 lookup.
5. **TimeoutBudget / FailurePolicy** (spec 05 §4.7~4.8) 미구현.
6. **promote/downgrade hook** (spec 04 §3.4) 미구현.
7. **spec 03 미구현 endpoints**: §2.3 /artifacts, §3.1 /runs/diff, §4.1 /anchor-invalidate, §5.1 /verification/promote, §6.1-2 /health|/capabilities.

## 마일스톤 의의

★ **Section 3 의 sandbox / orchestrator / spec_router 가 모두 실 Section 2 ontology DB 기반으로 동작**. 더 이상 `_NullOntologyClient` 도, 하드코딩 `primary_input_type` 도, `_build_minimal_run_plan` 의 1-frame echo 도 default 경로에 없음. ChangeSpec → SimResult 흐름이 실 ontology 데이터 기반 dispatch / anchor capture / BR 누적 로 동작.
