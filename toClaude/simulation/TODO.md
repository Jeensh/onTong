# Section 3 — Simulation TODO

Single Source of Truth for task status. Use `[x]` (done) / `[ ]` (pending).

## Section 4 인계 통합 (2026-05-16~ )

Section 4 (sim_v2) → Section 3 인계 패키지 통합. 5 sprint 계획. 출처: `toClaude/modeling/section4-verification/section3_handoff/README.md` §8.5.

### Sprint 1 — recipe-4 full pipeline (★ 완료, 2026-05-16)

- [x] 환경 검증 (venv / slab-v2-handoff.db / sim_v2 demos / recipes / API ref)
- [x] 인계 문서 정독 (README §8, gap-analysis, recipe-4, recipe-5, W74 API)
- [x] 데모 sanity check — UC41 한국어 검색 9/10 hit (90%)
- [x] 통합 plan 사용자 승인 (Strategy B: in-process W72 교체)
- [x] `tests/simulation/test_sim_v2_bridge.py` 작성 (Smart TDD, 6 test)
- [x] `backend/section3/sim_v2_bridge.py` 신설 (8 public 심볼)
- [x] `backend/section3/agents/sandbox_agent.py` 통합 (`_run_via_simv2` + `_is_action_fqn` 분기)
- [x] end-to-end 검증: `action.scm.product.cumulative_productivity` 12/12 PASS · 3 stubs
- [x] 백엔드 재기동 + /health 200 확인
- [x] 문서 동기화 (CHANGES / TODO / demo_guide / HANDOFF / memory)

### Sprint 2 — recipe-2 baseline 부착 (★ 완료, 2026-05-16)

- [x] `sim_v2_bridge.run_fixtures_with_baseline()` — BehaviorTwinRunner + attach_baselines
- [x] `sim_v2_bridge.load_baseline_map(method_fqn)` — file-based `data/baselines/{safe}.json`
- [x] sandbox_agent 가 baseline 파일 존재 시 자동 oracle 경로 사용
- [x] case_result 새 필드 — expected_value / actual_value / output_match / diff_summary
- [x] frontend EventStreamView — input/expected/actual 3-컬럼
- [x] `data/baselines/README.md` — 파일명 규칙 + JSON shape 문서
- [ ] (후속) W74 typed-return stub 도입으로 BehaviorTwinRunner ERROR 케이스 close (sim_v2 측 작업)

### Sprint 3 — recipe-3 invariant 진단 → chat fallback (★ 완료, 2026-05-16)

- [x] `sim_v2_bridge.quick_diagnose_action()` — W71→W74→W72 quick diagnose
- [x] `bridge_agent._emit_simv2_suggestions()` — simulate intent missing target 시 호출
- [x] `simv2_suggestions` 이벤트 + frontend 카드 UI
- [ ] (확장) impact_analysis 의 [LOW] result 분기에도 동일 surface

### Sprint 4 — recipe-5 W77+W78 한국어 검색 (★ 완료, 2026-05-16)

- [x] `sim_v2_bridge.find_action_candidates()` — W77+W78 + actions LIKE 보완
- [x] bridge_agent 자연어 query 에 자동 적용 (simulate fallback 진입점)
- [ ] (확장) LLM assist callback 으로 비표준 음역 close (현재는 fuzzy 만)

### Sprint 5 (opt) — transpiler 옵션 B (★ 완료, 2026-05-16)

- [x] `backend/section3/section3_translator.py` 신설 — sim_v2 동적 subclass
- [x] `_IDIOM_REWRITES` extension point 마련 (현재 비어 있음 — W75 가 50+ idiom 자동)
- [x] `sim_v2_bridge.translate_java_to_python` 가 새 translator 사용
- [ ] (후속) `backend/section3/transpiler.py` 의 legacy custom transpiler 제거 (현재 미사용, ontology.db 비어 있음)

## STEP 3 — Section 3 boilerplate (06-developer-onboarding.md)

### 3.0 폴더 신설 — 기존 simulation 코드 (sandbox/agents/jvm_bridge) 와 병존

- `backend/simulation/` 디렉토리 (이미 존재 — 옛 simulation 작업물)
- `tests/simulation/` 폴더 + conftest 구조 (이미 존재)

### 3.1 신설 파일 7개 (spec 따른 ChangeSpec/SimResult 흐름)

- `backend/shared/contracts/simulation.py` — ChangeSpec/SimResult 모델 (STEP 3a, 2026-05-10)
- `tests/simulation/test_changespec_schema.py` — 19 test 통과
- `backend/simulation/runner/` 폴더 (mkdir + **init**.py) (STEP 3b-1, 2026-05-10)
- `backend/shared/contracts/simulation.py` — Runner 11 모델 추가 (TypedValue/RunPlan/RunInputs/GeneratedScript/AnchorHit/BRTrigger/DispatchResult/SandboxCapabilities/TableSpec/LookupRow/FailurePolicy)
- `backend/simulation/runner/lookup_source.py` — spec 05 §3 (fixture_only 모드)
- `tests/simulation/test_runner_models.py` — 15 test 통과
- `tests/simulation/test_lookup_source.py` — 9 test 통과
- `backend/simulation/runner/java_sandbox.py` — spec 05 §2 (JavaSandbox Protocol + StubJavaSandbox) (STEP 3b-2, 2026-05-10)
- `tests/simulation/test_java_sandbox.py` — 13 test 통과 (anchor auto-hit + BR auto-pass + P-2018-0098)
- `backend/simulation/runner/python_generator.py` — spec 05 §1 (echo-stub) (STEP 3b-3, 2026-05-10)
- `tests/simulation/test_python_generator.py` — 14 test 통과 (ast.parse + dedup + fixture_keys + end-to-end exec sanity)
- `backend/simulation/runner/orchestrator.py` — spec 05 §4.5 (running 단계 entry) (STEP 3b-4, 2026-05-10)
- `tests/simulation/test_orchestrator.py` — 16 test 통과 (verdict 판정 + e2e Phase C P-2018-0098 sim_verified)
- `backend/simulation/api/run_handle.py` — spec 03 (RunHandle state machine + RunHandleStore) (STEP 3b-5, 2026-05-10)
- `tests/simulation/test_run_handle.py` — 20 test 통과 (5 상태 전환 + submit lifecycle + e2e)
- `backend/shared/contracts/simulation.py` — RunHandle 모델 추가 (Literal 5 상태, plan: Optional[RunPlan])
- `backend/simulation/api/spec_router.py` — spec 03 §1, §2 endpoints (POST /runs / GET /runs/{id} / sim-result / changespec / list) (STEP 3b-6, 2026-05-10)
- `tests/simulation/test_spec_router.py` — 13 test 통과 (FastAPI TestClient + Depends override)
- `backend/main.py` — spec_router 등록 (scenarios_router 보다 먼저 = path 충돌 시 spec_router 우선)

### 3.2 main.py wiring

- simulation router 9개 이미 등록됨 (commit `4ddf170`)
- spec_router 추가 등록 — scenarios_router 보다 먼저 (path 충돌 시 spec 03 우선) (STEP 3b-6, 2026-05-10)

## STEP 4 — 첫 ChangeSpec → SimResult 흐름

- 4.1 시나리오 선정 — `action.scm.std.match_customer_limit_for_order` (DB 검증)
- 4.2 ChangeSpec 작성 (spec 04 + 05 정합) — Phase E #41 lookups 형식 결정 필요
- 4.3 흐름 통과: POST /runs → orchestrator → python_generator → java_sandbox → SimResult verdict=sim_verified
- 4.5 verdict 6 조건 (a~f) unit test
- 4.6 anchor invalidation manual trigger (POST /api/simulation/anchor-invalidate)

## 통합 작업 backlog (Section 2 ↔ Section 3)

- `sample-repos/slab-design-real_v2/` 와 우리 simulation 의 jvm_bridge HTTP endpoint 매핑 결정 (slab-design 폴더 제거 후 endpoint 재포팅 필요)
- `tests/simulation/test_agent3.py` / `test_demo_e2e.py` 3 failure 해결 — fixture 경로를 새 sample-repos 위치로
- frontend `JavaPythonComparePanel.tsx` 의 `SLAB_DESIGN_BASE` URL 매핑
- 옛 `scenarios_router` 의 `/api/simulation/runs/{run_id}` (simulation-storage tag) → `/api/simulation/scenario-runs/{run_id}` 마이그레이션 (현재는 spec_router 가 가림)
- `spec_router._build_default_orchestrator()` 의 `_NullOntologyClient` → 실 `OntologyQueryClient` 연결 (modeling 측 facade)
- `spec_router._build_minimal_run_plan()` → 실 `/api/ontology/actions/{fqn}/delegates-to-tree` HTTP 호출
- spec 03 미구현 endpoints (후속 step): §2.3 /artifacts, §3.1 /runs/diff, §4.1 /anchor-invalidate, §5.1 /verification/promote, §6.1-2 /health|/capabilities

## Phase E backlog (modeling 측 미결정 11건)

- #41 lookups schema 형식 — STEP 4.2 첫 시나리오 작성 시 굳히기
- #49 atomic ↔ method-arg broadcast 매핑 — STEP 4.2 검증
- #37~#47 나머지 — STEP 4 진행 중 부딪힐 때 결정

## Bug Fixes / 옛 작업

- `/api/simulation/slab/ontology` 500 (`ModuleNotFoundError: networkx`) — 2026-04-17
- 샌드박스 timeout 7s → 308ms (psycopg pool join hang 해결) — 2026-05-10
- slab-design SLAB_RESULT 0 → 13 (kg 단위 시드 보정) — 2026-05-10

## UI

- 상단 Section 탭에서 Simulation의 "soon" 배지 제거 (status → `active`) — 2026-04-17
- SandboxConsole 케이스 펼침 + 한국어 라벨 + case_type stat — 2026-05-10
- RunHistoryPanel ▶ 상세 토글 (input/output JSON) — 2026-05-10
- RegressionPanel ▶ 원본 JSON 보기 — 2026-05-10
- JavaPythonComparePanel H2 시드 chip 프리셋 + 📋 복사 — 2026-05-10
- slab-design.html 한글 라벨 (FIELD_LABELS 47개) + 📋 JSON copy — 2026-05-10
- section3.html 한글 보강 + §11-5/§11-6 (Section 2 통합 5 지점) — 2026-05-10

## Backlog

- ★ **STEP 3f 종결** (2026-05-10) — 사용자 3 요구사항 + 통신 구조 검증 일괄 처리:
  - 0 — Section 2 ↔ Section 3 통신 방식 검증. Onboarding Q4 (line 501-506) 가 HTTP / Python facade 둘 다 명시적으로 허용 → 현재 in-process facade 유지 (사용자 "규약대로 진행" 결정).
  - 1 — Java↔Python differential 5 카테고리 분류 (matched/mismatched/java_only/python_only/both_null). `_normalize_payload()` null/빈값 재귀 제거. `summary` 한 줄 + per-category counts. 16 test 통과.
  - 2 — `GET /api/simulation/runs/{run_id}/ontology-evidence` 신설. 4 evidence kind (action / realized_method / br / anchor) trace, 각 SimResult 항목의 ontology source 명시 (mapping_layer.schema.* 클래스 + facade call). 7 test 통과.
  - 3-A — `frontend/public/section3.html` 전면 재작성. Apple SD Gothic Neo + Claude warm cream(#faf9f5) + accent orange(#d97757). 6 chapter 스토리라인 (왜/무엇을/어떻게/근거/Java↔Python/운영화) + 8 reveal 블록 (호기심 유발 클릭).
  - 3-B — 좌측 toc → 상단 sticky nav + chapter scroll + scroll spy. 이전 `section3.legacy.html` 보존 (사용자 지시 "지우진말고").
  - 회귀 423 passed (이전 400 → +23: differential 16 + ontology evidence 7).
- ★ **STEP 3.1 종결** (2026-05-10) — 7개 신설 파일 + main.py wiring 모두 완료. spec 03/04/05 1차 통합 완료.
- ★ **STEP 3c 종결** (2026-05-10) — Section 3 ↔ Section 2 ontology 실데이터 통합 완료. NullOntologyClient default 제거 / `_build_minimal_run_plan` 1-frame echo 제거 / 하드코딩 `primary_input_type` 제거. 실 ontology DB 의 1514 actions 기반으로 dispatch / anchor / BR 동작.
- ★ **STEP 3e 최종 종결** (2026-05-10) — F + E1 + E2 + E6 일괄 완료:
  * F — 실 ontology 시나리오 5종 (P-2018-0098 atomic_overrides / change_spec_ref deterministic / 21-step sub_actions / artifact 디스크 / failure_policy continue)
  * E1 — `JvmSubprocessSandbox` 신설 (spec 05 §2.5 + §5). Protocol + envelope 직렬화 + graceful fallback. spec_router 가 env `ONTONG_SANDBOX_TIER` 로 auto/jvm_subprocess/stub 자동 선택.
  * E2 — `RunHandleStore.submit_background()` (spec 05 §4.3 v1). daemon thread, Redis-RQ swap-ready.
  * E6 — `ontology_sources_router` 신설. SQLite + Neo4j dual source 명시적 endpoint (`GET /api/simulation/ontology-sources`).
  * 회귀 400 passed (이전 374 → +26: F 5 + E1 11 + E2 5 + E6 5).
- ★ **STEP 3d-E 종결** (2026-05-10) — 운영화 layer 4종 추가:
  - E3 — TimeoutBudget (spec 05 §4.7) + FailurePolicy 4가지 (spec 05 §4.8). RunOptions 6 필드 확장 (timeout_sec / capture_traces / capture_br_evidence / on_dispatch_error / on_br_violation / on_dispatch_inconsistent). Orchestrator dispatch loop 정책 분기.
  - E4 — promote/downgrade hook (spec 04 §3.4). `SimResult.suggested_promotion / suggested_downgrade`. verdict + scenario_kind metadata 로 권장.
  - E5 — artifact 디스크 저장 (spec 05 §6.2). `RunHandleStore` 의 in-memory + 디스크 dual (`ONTONG_ARTIFACT_ROOT` env / default `data/simulation/artifacts/`). graceful fallback.
  - 회귀 374 passed (이전 345 → +29: TimeoutBudget 10 + Disk Storage 12 + PromoteHook 7).
- ★ **STEP 3c-A+B+C+D 종결** (2026-05-10) — 운영화 layer 일괄 처리:
  - A — atomic_overrides 4-rule patcher (`AtomicOverridePatcher`) 신설. spec 04 §1.2 의 Rule 1/2/4 구현. ChangeSpec.atomic_overrides 가 `RunInputs.slots` 까지 실 patch 됨.
  - B — 실 ontology 의 `action.scm.std.match_customer_limit_for_order` 시나리오 → verdict=sim_verified ★ + `action.scm.슬랩설계_실행` 21-step workflow 22-frame 회귀.
  - C — spec 03 미구현 5종 endpoint (artifacts / runs/diff / anchor-invalidate / verification/promote / health / capabilities) 모두 구현.
  - D — broken slab_agent (HTTP 500 ImportError) 를 ontology 기반으로 재작성. atomic facets 추출 + spec 03 redirect 안내. 다른 8 routers 는 정상 동작 확인 (mock JSON 의존성 0건).
- 다음: 실 Java 실행 tier (jvm_subprocess) / async queue / TimeoutBudget / FailurePolicy / Neo4j ↔ SQLite ontology 통합 — 사용자 결정 대기

### STEP 3c 신설 파일 (Section 3 ↔ Section 2 ontology wire)

- `backend/simulation/runner/run_plan_builder.py` — RunPlan 빌드 (modeling facade BFS recursive). `_build_minimal_run_plan` 1-frame echo 대체.
- `backend/simulation/api/spec_router.py` 수정 — `_build_default_orchestrator()` 가 실 `OntologyQueryClientImpl()` 사용. `_NullOntologyClient` 보존 (test override / 비상 fallback). `get_run_plan_builder()` Depends getter 추가.
- `backend/simulation/runner/java_sandbox.py` 수정 — `_select_realization` fallback 추가 (primary_input 미상 시 action.realizations[0]). 이전 strict 셀렉터 `_select_realization_legacy()` 보존.
- `tests/simulation/test_run_plan_builder.py` — 12 test
- `tests/simulation/test_ontology_integration.py` — 5 test (실 DB 1514 actions hit)
- `tests/simulation/test_java_sandbox.py` — fallback 2 test 추가 (총 15)

