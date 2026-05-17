# STEP 3c — A+B+C+D 통합 종결 (★ Section 3 의 모든 신경로/주요경로 ontology 기반 동작)

**완료일**: 2026-05-10
**브랜치**: `section3-integration`
**범위**: A (atomic_overrides 4-rule patcher + 첫 시나리오) / B (P-2018-0098 회귀) / C (spec 03 미구현 5 endpoints) / D (옛 broken router 재구현)

## 목표

STEP 3c (NullOntologyClient default 제거) 이후 **남은 운영화 작업** 일괄 처리:
- A — atomic_overrides 가 sandbox 까지 실 patch (이전엔 dump 만)
- B — 실 ontology 의 21-step workflow 회귀 검증
- C — spec 03 의 미구현 5 endpoint 모두 구현 (artifacts/diff/anchor-invalidate/promote/health/capabilities)
- D — 옛 broken router (slab_agent) 의 ImportError 해결 + ontology 기반 재작성

## A — atomic_overrides 4-rule patcher (spec 04 §1.2)

### 신설: `backend/simulation/runner/atomic_override_patcher.py` (+200 lines)

| Rule | path 형식 | 처리 |
|---|---|---|
| 1 | `{action}.inputs[N]<{type}>.{atom_path}` | RunInputs.slots[primary].value 에 nested patch |
| 2 | `{atomic_fqn}` (`.atomic.` 토큰 포함) | fixture.list_rows() 의 매칭 column 모두에 broadcast |
| 3 | `{composite_fqn}.{slot}` | echo-stub iter 미구현 — warning 누적 |
| 4 | 인식 안 됨 | ValueError ('invalid path') |

### Orchestrator wire

`Orchestrator.__init__()` 가 `AtomicOverridePatcher` 받음 (default 자동 생성).
`run()` 의 step 3b 에서 `inputs, warnings = patcher.apply(inputs, change_spec.atomic_overrides, action_fqn)`.
ValueError raise → `status=failed`, dispatch loop skip.

### Test
- `tests/test_atomic_override_patcher.py` 신설 (10 test)
- `tests/test_orchestrator.py` 추가 (2 test) — atomic_overrides → slots / invalid → failed

## B — P-2018-0098 회귀

### 검증 (`tests/test_ontology_integration.py` 추가)

1. `test_match_customer_limit_for_order_scenario_runs_sim_verified`:
   - 실 ontology 의 `action.scm.std.match_customer_limit_for_order`
   - realized: `CustomerStdService.findFirstMatch(String,String,String,String)`
   - BR 1 passed (`rule.scm.std.customer_find_first_match_strategy`)
   - anchor 2 hit (`anchor_customer_empty_check`, `anchor_customer_first_match`)
   - **verdict=sim_verified ★**

2. `test_p_2018_0098_regression_21_step_workflow`:
   - `action.scm.슬랩설계_실행` (21 sub_actions)
   - 22 frames trace (root + 21 BFS sub_actions, depth 0/1)
   - scenario_fixture.metadata.scenario_origin="P-2018-0098" 보존
   - status=completed

## C — spec 03 §2.3 / §3.1 / §4.1 / §5.1 / §6.1 / §6.2 endpoints

### 13 모델 추가 (`backend/shared/contracts/simulation.py`)

Artifact / ArtifactBundle / FieldDiff / BRDiff / AnchorDiff / DiffRequest / DiffResult / AnchorInvalidateRequest+Result / PromoteRequest+Result / HealthStatus / Capabilities.

### 6 endpoints (`backend/simulation/api/spec_router.py`)

| 메서드 | 경로 | 책임 |
|---|---|---|
| GET | `/runs/{id}/artifacts?kind=...` | spec 03 §2.3 ArtifactBundle (generated_python/trace/input_fixture/output_dump) |
| GET | `/runs/{id}/artifacts/{kind}/raw` | PlainTextResponse (Python source / JSONL trace 등) |
| POST | `/runs/diff` | spec 03 §3.1 — output/br/anchor/duration diff |
| POST | `/anchor-invalidate` | spec 03 §4.1 — modeling facade 호출, read-only 시뮬 |
| POST | `/verification/promote` | spec 03 §5.1 — SIM_VERIFIED 진급 시 evidence_run_ids 검증 |
| GET | `/health` | spec 03 §6.1 — queue_depth / sandbox_available / jvm_available |
| GET | `/capabilities` | spec 03 §6.2 — supported_action_kinds / verdicts / version |

### Artifact 보관

`RunHandleStore` 에 `store_artifact / get_artifact / list_artifact_kinds` 추가.
`submit()` 가 orchestrator 의 `last_generated_script` 참조해 4종 artifact (generated_python / trace JSONL / input_fixture JSON / output_dump JSON) 저장.

### Test
- `tests/test_spec_router_c.py` 신설 (13 test)

## D — 옛 broken router 재작성

### 조사 결과 (`tests/__import__` 매핑)

9 옛 routers 중:
- `slab_agent.py` — 삭제된 mock 모듈 import → **HTTP 500 (broken)**
- 8 routers (agents/scenarios/jobs/bridge/transpile/auto_pr/seed/differential) — 정상 동작 (200/422)

### slab_agent 재작성 (사용자 지시 "지우진말고" — 보존)

**이전**: `backend.simulation.mock.scenarios.slab_size_simulator` (삭제됨) → ImportError → HTTP 500.

**현재** — `backend/simulation/api/slab_agent.py`:
- `_get_ontology_client()` lazy singleton (graceful fallback _Null)
- `GET /constraints` → ontology 의 atomic facets (range/unit/enum) 를 slab 키워드 (slab/thickness/width/length/weight/diameter) 로 필터
- `POST /calculate` → input params 의 ontology atomic 매칭 검증 + spec 03 redirect 안내 (`{"status": "deprecated", "redirect_to": "POST /api/simulation/runs"}`)

### Test
- `tests/test_slab_agent_ontology.py` 신설 (4 test)

## 라이브 서버 검증 (uvicorn + curl)

```bash
# slab_agent (이전 500 → 현재 200, ontology 기반)
GET /api/simulation/slab/constraints
  HTTP 200 / source=ontology / atomic_count=0
POST /api/simulation/slab/calculate
  status=deprecated / redirect_to=POST /api/simulation/runs

# C endpoints
GET /api/simulation/health → {"status": "ok", "queue_depth": 0, "sandbox_available": true}
GET /api/simulation/capabilities → 3 action_kinds + 5 scenario_kinds + runner_version=echo-stub-3c

# A+B 실 ontology 시나리오
POST /api/simulation/runs (action.scm.std.match_customer_limit_for_order)
  → verdict=sim_verified ★
  br_evidence=1 / anchor_evidence=2
  realized=CustomerStdService.findFirstMatch(...)

GET /api/simulation/runs/{id}/artifacts
  → ['generated_python', 'trace', 'input_fixture', 'output_dump'] 4종
```

## 회귀

| | |
|---|---|
| `test_atomic_override_patcher.py` | 10 test |
| `test_orchestrator.py` (확장) | 18 test |
| `test_ontology_integration.py` (확장) | 7 test |
| `test_spec_router_c.py` | 13 test |
| `test_slab_agent_ontology.py` | 4 test |
| **전체 `tests/simulation/`** | **345 passed** (이전 314 → +31), 17 skipped, 3 failed (sample-repos — 무관) |
| Section isolation | ✅ — modeling internal layer 직접 import 0건 |

## 주요 결정

- **slab_agent endpoint 보존** — 사용자 지시 "지우진말고". 내부 구현만 ontology 기반으로 교체. frontend 호환 위해 같은 path/method 유지.
- **slab_agent `/calculate` 응답** — `status="deprecated"` + `redirect_to` 명시. 실 시뮬은 spec 03 신경로 사용 안내.
- **artifact storage** — in-memory (RunHandleStore dict). spec 05 §6.2 의 `artifacts/{run_id}/*` 디스크 저장은 후속 step.
- **anchor-invalidate read-only** — modeling 측 storage 실 invalidate 는 modeling 책임. spec_router 는 binding 조회만.
- **verification/promote** — SIM_VERIFIED 만 evidence_run_ids 검증. 다른 level 진급은 echo (modeling 측 storage update 미구현).
- **JVM 미연결** — `jvm_available=False` health 명시. StubJavaSandbox 만.
- **임시 코드 보존** — `_NullOntologyClient` (3c) / `_select_realization_legacy` (3c) / 옛 mock_simulator 삭제분 (commit 2a346e3) — 호출 0건 + 보존.

## Section 3 의 ontology 통합 도달 수준 — 종합

| 영역 | 상태 | 비고 |
|---|---|---|
| spec_router (POST /runs) | ✅ ontology | OntologyQueryClientImpl default |
| RunPlan 생성 | ✅ ontology | RunPlanBuilder (delegates_to_tree BFS) |
| primary_input_type derive | ✅ ontology | Action.realizations / params |
| dispatch (StubJavaSandbox) | ✅ ontology + fallback | get_realizations / fallback to action.realizations[0] |
| anchor capture | ✅ ontology | get_anchor_bindings_for_action |
| BR enumeration | ✅ ontology | Action.preconditions+postconditions |
| LookupDataSource TableSpec derive | ✅ ontology | list_code_types(role=) |
| **atomic_overrides 적용** | ✅ ontology | **AtomicOverridePatcher 4-rule (3c-A)** |
| **artifacts** | ✅ in-memory | **store/get artifact (3c-C)** |
| **slab_agent 재구현** | ✅ ontology | **Atomic facets / spec 03 redirect (3c-D)** |
| 실 Java code 실행 | ❌ stub | spec 05 §2.5 (jvm_subprocess / graalvm 후속) |
| generated source_code 실행 | ❌ artifact 만 | orchestrator 가 직접 dispatch |
| async queue | ❌ sync | spec 05 §4.3 v2 (Redis-RQ) 후속 |
| TimeoutBudget / FailurePolicy | ❌ | spec 05 §4.7~4.8 후속 |

## Diff stat

- `backend/simulation/runner/atomic_override_patcher.py` — 신규 +200 lines
- `backend/simulation/runner/orchestrator.py` — patcher wire +20 lines
- `backend/simulation/api/run_handle.py` — artifact storage +35 lines
- `backend/simulation/api/spec_router.py` — 6 endpoints +280 lines
- `backend/simulation/api/slab_agent.py` — 전면 재작성 (이전 broken → ontology 기반)
- `backend/shared/contracts/simulation.py` — 13 모델 +130 lines
- 테스트 4개 신규 (총 +31 test)

## 다음 작업 (사용자 결정 대기)

남은 후속 backlog:
- spec 05 §2.5 jvm_subprocess tier 도입 — 실 Java 코드 실행
- spec 05 §4.7 TimeoutBudget + §4.8 FailurePolicy 4가지 정책
- async queue (asyncio.Queue / Redis-RQ) v2
- promote/downgrade hook (spec 04 §3.4) — auto verification level 조정
- artifact 디스크 저장 (현재 in-memory)
- agents_router (Neo4j-backed) → SQLite-backed OntologyQueryClientImpl 통합
