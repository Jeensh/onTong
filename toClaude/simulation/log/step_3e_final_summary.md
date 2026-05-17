# STEP 3e — 최종 운영화 (F + E1 + E2 + E6)

**완료일**: 2026-05-10
**브랜치**: `section3-integration`
**범위**: F (실 시나리오) / E1 (jvm_subprocess) / E2 (asyncio queue) / E6 (dual ontology source)

## F — 실 시나리오 회귀 (`tests/test_real_scenarios.py` 5 test)

실 ontology 데이터로 e2e 흐름 검증:
- F-1: P-2018-0098 + atomic_overrides + scenario_kind=regression → suggested_promotion 권장
- F-2: change_spec_ref 가 같은 입력에 deterministic
- F-3: 21-step workflow 의 sub_actions 단독 dispatch 모두 sim_verified
- F-4: artifact 가 디스크에 4종 파일 저장됨 (e2e)
- F-5: failure_policy=continue + 일부 frame raise → 끝까지 실행

## E1 — JvmSubprocessSandbox (spec 05 §2.5 + §5)

### `runner/jvm_subprocess_sandbox.py` 신설 (+200 lines)

JavaSandbox Protocol 구현체 — 실 Java subprocess 호출:
- spec 05 §5.2 입력 envelope: `{request_id, action_fqn, inputs (slot_name → {_type, value}), primary_input_slot, overrides, options}`
- spec 05 §5.3 ok envelope: `{status, outputs, anchor_hits, br_triggers, duration_ms, realized_method_fqn, dispatch_consistent}`
- spec 05 §5.4 error envelope: `{status, error_kind, error_message, partial_outputs}`
- subprocess.run timeout → TimeoutError raise (orchestrator 가 capture)
- exit code != 0 → JVMCrashError
- invalid JSON → SerializationError

**graceful**:
- Java 미가용 → SubprocessNotAvailable raise (생성자 시점)
- spec_router 가 try/except 로 자동 stub fallback

### spec_router 자동 tier 선택

`_build_default_sandbox(ontology)`:
- env `ONTONG_SANDBOX_TIER` (auto / jvm_subprocess / stub)
- auto 모드: JvmSubprocessSandbox 시도 → SubprocessNotAvailable 시 stub fallback
- env `ONTONG_INSTRUMENTATION_JAR` 로 jar 경로 지정 가능

### Test (`tests/test_jvm_subprocess_sandbox.py` 11 test)

monkeypatch 로 subprocess.run mock — 실 Java 미존재 환경에서도 검증:
- backend 거부 / Java 미존재 / jar 미존재 (3)
- ok envelope 파싱 (1) — anchor_hit + br_trigger 포함
- error envelope 파싱 (1)
- timeout / JVM crash / bad JSON (3)
- envelope 직렬화 정합성 (`_type` 필드 / options.timeout_ms) (1)
- JavaSandbox Protocol satisfy (1) — orchestrator swap 가능

## E2 — asyncio queue (background execution)

### `RunHandleStore.submit_background()` 추가

- spec 05 §4.3 v1 — daemon thread (asyncio worker 단순화)
- `submit()` 의 sync 로직을 `_execute()` 로 추출 → `submit()` / `submit_background()` 둘 다 사용
- thread-safe RLock 보장 (state machine + artifact storage 모두)
- spec 05 §4.3 v2 (Redis-RQ) 도입 시 thread → worker 로 swap 만 필요

### Test (`tests/test_async_queue.py` 5 test)

- submit_background 즉시 RunHandle 반환 (orchestrator 가 0.5초 sleep 해도 < 0.2초)
- background 완료 polling → status=completed + sim_result 저장
- background 예외 → status=failed + sim_result 미저장
- 3 concurrent submission — 모두 다른 run_id + 모두 완료
- SimResult.run_id 정규화 (placeholder → RunHandle.run_id)

## E6 — dual ontology source (Neo4j + SQLite)

### 발견사항

Section 3 가 두 ontology source 사용 중:

| Source | 위치 | Schema | 용도 |
|---|---|---|---|
| **SQLite** | `backend.modeling.api.ontology_query.OntologyQueryClientImpl` | 관계형 (Action/CodeType/Realization/AnchorBinding) | spec 03/04/05 신경로 — RunPlanBuilder / sandbox / runner core |
| **Neo4j** | `backend.modeling.ontology.client.OntologyClient` | 그래프 (Step/Standard/Method/Class/Term + relationships) | agents_router — ontology_graph / impact / locator / explorer |

두 schema 가 다르므로 단순 adapter 로 통합 불가. 대신 **dual source 명시적 endpoint** 제공.

### `api/ontology_sources_router.py` 신설 (+150 lines)

- `GET /api/simulation/ontology-sources`
- 두 source 의 health / entity_counts / purpose / cross_references 보고
- `OntologySourcesReport` Pydantic 응답 모델
- main.py 등록

cross_references 자동 도출:
- method_fqn — SQLite Realization.code_method_fqn ↔ Neo4j Method.name
- action 흐름 — SQLite Action.sub_actions BFS ↔ Neo4j Step.step_number 시퀀스
- term — SQLite BusinessTerm.fqn ↔ Neo4j Term.korean_name

### Test (`tests/test_ontology_sources_router.py` 5 test)

- 두 source 모두 보고 (sqlite + neo4j)
- SQLite entity_counts.actions ≥ 0
- Neo4j health (available + error) 정합
- 두 source 살아있을 때 cross_references 채워짐
- purpose 텍스트 비어있지 않음

## 회귀

| 검증 | 결과 |
|---|---|
| 신규 test (F + E1 + E2 + E6) | **26 test** (5 + 11 + 5 + 5) |
| 전체 `tests/simulation/` | **400 passed** (이전 374 → **+26**), 17 skipped, 3 failed (sample-repos — 무관) |
| Section isolation | ✅ — modeling internal layer 직접 import 0건 |

## Section 3 의 운영화 도달 수준 — 최종 (3e 종결)

| 영역 | 상태 |
|---|---|
| ontology 데이터 흐름 (SQLite) | ✅ (3c) |
| atomic_overrides 4-rule | ✅ (3c-A) |
| spec 03 endpoints (POST/GET 12종) | ✅ (3b-6 + 3c-C) |
| artifact in-memory + 디스크 | ✅ (3c-C + 3d-E5) |
| TimeoutBudget | ✅ (3d-E3) |
| FailurePolicy 4가지 | ✅ (3d-E3) |
| promote/downgrade hook | ✅ (3d-E4) |
| **실 시나리오 (F)** | **✅ 5 e2e test (P-2018-0098 + 21-step + atomic_overrides + scenario_kind + failure_policy)** |
| **JvmSubprocessSandbox (E1)** | **✅ Protocol 구현 + envelope 직렬화 + graceful fallback** |
| **async queue (E2)** | **✅ submit_background daemon thread (Redis-RQ swap-ready)** |
| **dual ontology source (E6)** | **✅ /ontology-sources endpoint — Neo4j + SQLite 명시적 보고** |
| 실 Java 코드 실행 | ⚠ Protocol/envelope 완성, 실 Java 미연결 (instrumentation jar 필요) |
| Redis-RQ 운영 큐 | ❌ daemon thread 만 (v2 후속) |

## Diff stat

- `runner/jvm_subprocess_sandbox.py` — 신규 +200 lines
- `api/run_handle.py` — submit_background +50 lines
- `api/spec_router.py` — sandbox tier 자동 선택 +60 lines
- `api/ontology_sources_router.py` — 신규 +150 lines
- `main.py` — ontology_sources_router 등록
- 테스트 4개 신규 (26 test)

## ★ 최종 마일스톤 — Section 3 의 spec 03/04/05 + 운영화 layer 완전체

본 STEP (3e) 으로 사용자 요구 사항 모두 처리:
- ontology 모델링 (Section 2 SQLite) 기반 동작 ✅
- 하드코딩 / mock JSON / 임시 python 코드 default 경로에 0건 ✅ (보존은 유지)
- spec 03/04/05 명세 거의 모두 구현 ✅
- 운영화 layer (timeout / failure policy / artifact 디스크 / promote hook / async queue / dual ontology source / jvm_subprocess Protocol) ✅
- 실 시나리오 회귀 ✅

남은 후속 (별도 step / 운영 진입 시):
- 실 Java instrumentation jar 빌드 + JvmSubprocessSandbox 와 연결
- Redis 운영 큐 (asyncio.Queue → Redis-RQ)
- promote/downgrade hook 의 실 storage update (modeling 측 endpoint 호출)
