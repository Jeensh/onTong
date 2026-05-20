# Section 3 — Simulation TODO

Single Source of Truth for task status. Use `[x]` (done) / `[ ]` (pending).

## Chat 멀티턴 재설계 (2026-05-17~ )

브랜치: `section3/chat-agent-redesign` · spec: `CHAT_REDESIGN_SPEC.md` · 차용 원본: Section 2 `backend/application/authoring/`

### Phase 0 — Spec + alignment (완료, 2026-05-17)
- [x] 4 인계 문서 정독 (HTML report / MD report / bridge_agent.py / authoring/)
- [x] `CHAT_REDESIGN_SPEC.md` 작성 (291 LOC, 12 섹션)
- [x] Phase 0~4 rollout plan + 협업 요청 매트릭스
- [x] commit `9cb354e` on `section3/chat-agent-redesign`
- [ ] 사용자 spec 리뷰 + 4 default decision 확인

### Phase 1 — 멀티턴 인프라 scaffold (대기)
- [ ] `backend/section3/agents/multiturn/` 패키지 신설 (`__init__.py`, `agent.py`, `schemas.py`, `tools.py`, `persistence.py`)
- [ ] `GatePayload` discriminated union (6 게이트: candidates/target/code/python/fixtures/sandbox) — `schemas.py`
- [ ] `section3_decision_log` ORM (`backend/section3/orm.py` 신설 또는 기존 위치 협의)
- [ ] alembic 마이그레이션 `migrations/versions/2026_05_18_006_section3_decision_log.py` (협업 요청 #3)
- [ ] Pending action gate wiring — `backend/core/session.py:70-87` 그대로 재사용 (신규 코드 0)
- [ ] Endpoint 4개 신설 (`backend/section3/api/multiturn.py`):
  - `POST /api/section3/multiturn/start`
  - `POST /api/section3/multiturn/respond/{session_id}`
  - `POST /api/section3/multiturn/confirm/{gate_kind}/{action_id}`
  - `GET  /api/section3/multiturn/session/{session_id}` (+ /stream)
- [ ] Mock ontology tool wrapper 3개 (`tools.py`):
  - `ontology.get_action_detail(id)` → sim_v2 `load_action(...)` 결과 변환
  - `ontology.get_method_body(fqn)` → sim_v2 `load_body_text(...)`
  - `ontology.get_entity_schema(name)` → sim_v2 fixture synth 의 schema 로직

### Phase 2 — 게이트 단위 구현 (1 게이트씩, 대기)
- [ ] Gate 1 (candidates) — sim_v2 find_action_candidates + LLM 후보 선별 + frontend `GateCandidatesCard.tsx`
- [ ] Gate 2 (target) — 선택 검증 + action detail + `GateTargetCard.tsx`
- [ ] Gate 3 (code) — Java 추출 + anchor highlight + `GateCodeCard.tsx`
- [ ] Gate 4 (python) — sim_v2 W75 변환 + idiom diff + `GatePythonCard.tsx`
- [ ] Gate 5 (fixtures) — entity schema → fixture table (수정 가능) + `GateFixturesCard.tsx`
- [ ] Gate 6 (sandbox) — run + invariant 진단 + `GateSandboxCard.tsx`
- [ ] `MultiturnChat.tsx` 컨테이너 + SSE 구독 + 카드 누적 렌더 + `useMultiturnSession.ts` (Zustand)

### Phase 3 — 통합 + 검증 (대기)
- [ ] End-to-end 시나리오 1: "주문 검증 액션이 뭐야" → 6 게이트 완주
- [ ] End-to-end 시나리오 2: 세션 끊고 다음날 resume (replay)
- [ ] End-to-end 시나리오 3: Gate 4 에서 Gate 3 으로 "다시" 분기
- [ ] 데모 가이드 갱신 (`demo_guide.md`)
- [ ] CHECKLIST.md 신규 시나리오 추가

### Phase 4 — 옛 path deprecate (optional, 대기)
- [ ] Frontend 토글 default 를 멀티턴으로
- [ ] 옛 `bridge_agent.py` 의 `_handle_explain` / sandbox 분기 deprecate notice
- [ ] retention 기간 후 옛 `POST /api/section3/chat` 제거

### 협업 요청 (Section 2 owner, 대기)
- [ ] **#1** `ontology.db` 시드 보충 — impact_analysis 게이트 활성화용 (Phase 2 후반)
- [ ] **#2** OntologyClient 3 endpoint 신설 (Phase 1 mock 후 swap)
- [ ] **#3** `section3_decision_log` 마이그레이션 — Section 3 가 alembic 파일 PR? 또는 Section 2 측 진행? (Phase 1 와 같이)

---

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

## Phase E-C — Parser root fix + translator rework (★ 완료, 2026-05-18)

cross-section 권한으로 modeling 영역 작업. 상세는 `log/step_ec_parser_translator_rework.md`.

- [x] **E-C1** safety net — `scripts/export_modeling_enrichment.py` + `reapply_modeling_enrichment.py` (round-trip verified)
- [x] **E-C2** parser symbol table — `backend/modeling/code_analysis/method_symbol_table.py` (신규) + `java_parser._extract_calls` receiver_type 부착 (2,114/2,448 = 86% 자동 채움, 1,435 high-conf native 분류)
- [x] **E-C3** translator 5 patches — try-with-resources / instanceof T t walrus / Collection.copyOf / shadowing rename / scoped FQN resource (synthesizer 399/399 regression-clean)
- [x] **E-C4** re-import + reapply + 6 actions sim_verified 승격 → **130/130 (100%)**
- 커밋: `9a6a6a8`, `f449355` on `section3/chat-agent-redesign`
- 백업: `data/ontology.db.bak-pre-reimport-20260518-201243` + snapshot `data/enrichment_snapshot_slab_design_real_v2_20260518_111338.json`
- 보류: hybrid reapply (native vs manual 통합), Gap 4 (constructor + static_class analyzer route), Gap 5 (chain return-type)

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

---

## Chat 재설계 — Phase 1 인프라 (2026-05-17)

> SPEC: `CHAT_REDESIGN_SPEC.md` v2. 6→3 gates, §6 폐기, alembic 없이.
> 결정 페이지: `chat-redesign-review.html`. 4 sub-agent 검토 후 사용자 OK.

### Phase 1 — 인프라 + Scaffold (완료)
- [x] **Step 1a** — spec v2 + HANDOFF 갱신 (3 gates / §6 폐기 / Q5 §13 신설)
- [x] **Step 1b** — `backend/section3/agents/multiturn/{__init__.py, schemas.py}` (GatePayload union + Provenance)
- [x] **Step 1c** — `orm.py` + `persistence.py` + `main.py` startup import (Base.metadata.create_all)
- [x] **Step 1d** — `ontology_client.py` (Protocol + Mock + HTTP stub) + `tools.py` (9 tool wrapper + ToolResult + ALLOWED_PER_GATE)
- [x] **Step 1e** — `backend/section3/api/multiturn_router.py` (5 endpoint) + `main.py` include
- [x] **Step 1f** — integration verification (서버 + curl + edge cases + SSE)
- [x] **Step 1g** — Step 1 summary + doc sync (이 항목)

검증: `tests/simulation/` **67/67 passed** (schemas 15 + persistence 13 + ontology_client 11 + tools 5 + router 10 + sim_v2_bridge 13). 서버 curl 4 endpoint 한국어 payload + edge cases 모두 정상.

### Phase 2 — 게이트 단위 production wiring (진행 중)

#### Gate I — intent + candidates (완료, 2026-05-17)
- [x] **Step 2a** — `intent.py` (IntentDecision + Protocol + Stub + classify_with_llm + OpenAIAdapter)
- [x] **Step 2b** — `gate_i.py` (build_gate_i: classifier + asyncio.gather + dedupe merge + Provenance 3종)
- [x] **Step 2c** — `multiturn_router.py /respond` DI + turn 2 = Gate I real / turn 3+ = 501
- [x] **Step 2d** — tests/simulation **93 PASS** (+26) + 실 OpenAI curl (simulate / impact) + edge cases

검증: 서버 + 실 OpenAI key 로 `주문 검증 시뮬해줘` → intent=simulate + 5 후보 (slab-design-real-v2 실데이터). `cumulativeProductivity 바꾸면 영향?` → intent=impact + 1 후보. /respond turn 3 = 501 OK.

#### Gate II — Java + Python + Schema + Fixtures (완료, 2026-05-17)
- [x] **Step 3a** — `tests/simulation/test_multiturn_gate_ii.py` (7 test: happy path + missing data + entity 추출 + schema roundtrip)
- [x] **Step 3b** — `gate_ii.py` (build_gate_ii: body → translate → schema → fixtures pipeline, 단계별 부분 실패 graceful)
- [x] **Step 3c** — `/respond` turn 3 wire + state machine 분기 (simulate→GateII / impact→501 / ambiguous→422) + `_resolve_gate_ii_target` (user_response.selected_index → ActionRef)
- [x] **Step 3d** — tests/simulation **105 PASS** (+12) + 실데이터 curl 검증 + edge cases

#### SimV2BackedOntologyClient (production default, 2026-05-17)
- [x] `sim_v2_bridge` 를 데이터 소스로 쓰는 production ontology client (Phase 4 swap target)
- [x] `get_method_body` → `load_body_text`, `get_action_detail` → `load_action` (ActionRef 변환)
- [x] search / entity_schema / caller_graph 는 빈 결과 ("빠진 내용은 빠진대로")

#### Gate III sim (완료, 2026-05-17)
- [x] **Step 4a** — `tests/simulation/test_multiturn_gate_iii_sim.py` (8 test: clean / dominant failure / unexpected throw / missing python_source / no action / no fixtures / case_id preserve / provenance)
- [x] **Step 4c** — `gate_iii_sim.py` (load_action → re-synthesize → build_stubs → run_fixtures_in_process → CaseResult + invariant aggregation)
- [x] `_aggregate_invariant_from_dicts` — raw invariant_status (PASS/FAIL_*/ERROR) → schema 의 (clean/fail_*) 매핑
- [x] `_extract_function_name(python_source)` — 첫 `def NAME(...)` 추출
- [x] `/respond` next_turn==4 wire + `session.status="done"` 갱신

#### Gate III impact (완료, 2026-05-17)
- [x] **Step 4b** — `tests/simulation/test_multiturn_gate_iii_impact.py` (8 test: caller_graph / confidence high/low / findings translate / sources / no caller_graph / no action graceful)
- [x] **Step 4c** — `gate_iii_impact.py` (asyncio.gather caller_graph + load_action → quick_diagnose if action → Finding list + confidence)
- [x] `_diagnose_to_findings` — quick_diagnose dict → list[Finding] (info/warn/error severity 분기)
- [x] `_impact_confidence` — ok 시 0.8 + 0.2*(passing/fixtures), blocked 시 0.2~0.4
- [x] `/respond` next_turn==3 + impact intent wire (501 → real) + `session.status="done"` 갱신

#### Router state machine 갱신 (완료, 2026-05-17)
- [x] `session.status=="done"` 시 즉시 501 ("session 이미 완료") — Gate III 후 추가 호출 차단
- [x] turn 5 = 501 (simulate path 완료 후), turn 4 = 501 (impact path 완료 후)

#### Frontend Phase 3 (완료, 2026-05-17)
- [x] **P3a** — `frontend/src/lib/section3/multiturn.ts` API client + TS types (백엔드 schemas.py 와 1:1)
- [x] **P3b** — `useMultiturnSession.ts` hook (state + start/respond/confirm/reset, source-of-truth refresh)
- [x] **P3c** — 5 컴포넌트: `ProvenanceBadge` + `GateTargetCard` + `GateBundleCard` + `GateExecutedSimulationCard` + `GateExecutedImpactCard`
- [x] **P3d** — `MultiturnChat.tsx` 컨테이너 (빈 상태 + 예시 + 자동 turn 진행)
- [x] **P3e** — `Section3Section` nav 6개로 확장 (`멀티턴 (v2)`, URL `?view=multiturn`)
- [x] **P3f** — TS clean + Next.js proxy → 8001 OK + 풀 플로우 verified via curl

#### Phase 4 완료 (2026-05-18)
- [x] **P4a** — `HybridOntologyClient` (sec2 HTTP + sim_v2 fallback). search/actions/{fqn} wire, 나머지 3 endpoint delegate. ENV `ONTONG_SECTION2_API_URL` 분기. 10 tests PASS
- [x] **P4b** — `confirm.next_gate_kind` explicit state machine (`_next_gate_kind` helper). 5 tests PASS
- [x] **P4c** — tests/simulation **137 PASS** (+15) + 서버 curl (next_gate_kind + fallback) 검증

#### Phase 4d — sec2 ↔ sec3 협업 wire (완료, 2026-05-18)
- [x] **sec2** — `CodeLayerStore.get_method_callers` + helper 2 (simple_name / receiver 추출)
- [x] **sec2** — `OntologyQueryClient` Protocol+Impl 2 method (`get_method`, `get_method_callers`)
- [x] **sec2 routes** — 3 신규 endpoint:
  - `GET /api/ontology/code-methods/{fqn:path}/body`
  - `GET /api/ontology/code-methods/{fqn:path}/callers?repo_id=`
  - `GET /api/ontology/entities/{entity_name}/schema?repo_id=`
- [x] **sec2 tests** — 6 신규 (`TestPhase4CollaborationEndpoints`) + `app_with_callsites` fixture
- [x] **sec3** — `HybridOntologyClient` 3 method 본체 wire (sec2 200 → use, 404/error → sim_v2 fallback)
- [x] **sec3 tests** — 6 갱신 (sec2 wire + 404 fallback)
- [x] tests 합 **156 PASS** + 서버 round-trip 검증

#### Phase 5 — Polish (완료, 2026-05-18)
- [x] **P5a** — backend SSE `/session/{sid}/stream` short-lived server-push (0.5초 폴, 30초 max lifetime, signature-diff, done event, gone event, EventSource 자동 reconnect)
- [x] **P5b** — frontend `useMultiturnSession` 이 EventSource subscribe (snapshot/done/gone listener, mutation refresh 병행)
- [x] **P5c** — `state.lastNextGateKind` + `SessionHeader → {kind}` blue hint (다음 단계 surface)
- [x] **P5d** — tests/simulation **138 PASS** (+1 SSE done test) + 서버 SSE 동작 + TS clean

#### Phase 6 — modeling ontology.db 시드 (완료, 2026-05-18)
- [x] **P6a** — `scripts/seed_modeling_from_sim_v2.py` — slab-v2-handoff.db 의 12 테이블 → ontology.db INSERT OR IGNORE
- [x] **P6b** — script 실행 (code_methods 985 + call_sites 1290 + actions 38 등) + `get_method_callers` receiver fallback 추가 + 서버 검증 (Gate II confidence 1.0, Gate III impact affected 1)
- [x] **P6c** — 157 PASS 회귀 + doc sync

#### Phase 7 — bridge_agent v1 deprecate (완료, 2026-05-18)
- [x] **P7a** — `bridge_agent.py` module docstring + `/api/section3/chat` 응답 4종 deprecation header (RFC 7234 Warning 299)
- [x] **P7b** — Frontend `BridgeChatPanel` deprecation banner + nav 라벨 변경
- [x] **P7c** — `tests/simulation/test_section3_v1_deprecation.py` 신규 2 tests

#### Phase 8 — idiom_diffs surface (완료, 2026-05-18)
- [x] **P8a** — sim_v2 `rewrite_method_invocation(..., trace=...)` optional kwarg + `TranslationResult.idiom_rewrites` 필드
- [x] **P8b** — `translate_java_to_python` 반환을 3-tuple 로 확장 + gate_ii 가 IdiomDiff[] 채움 (dedup)
- [x] **P8c** — `GateBundleCard` 에 "Idiom diff" tab 추가
- [x] **P8d** — W75 idiom_rewriter +6 tests + gate_ii +3 tests

#### Phase 9 — W74 typed-return stubs (완료, 2026-05-18)
- [x] **P9a** — `sandbox_stubs.derive_method_return_defaults` + `_typed_default_for` (String/int/boolean/BigDecimal/List/Map/Optional/...)
- [x] **P9b** — `derive_class_stub`/`derive_repository_stub`/`build_stub_namespace` 가 typed-default kwarg 수용 + autoload
- [x] **P9c** — W74 sandbox_stubs +7 tests

#### Phase 10 — caller graph 정확도 (완료, 2026-05-18)
- [x] **P10a** — `get_method_callers_with_match` 5단계 match_kind heuristic (receiver_exact / receiver_short / runtime_type / package_proximity / name_only)
- [x] **P10b** — `/api/ontology/code-methods/{fqn}/callers` 응답에 `match_kind` + `strength` + `min_strength` query param
- [x] **P10c** — `AffectedMethod` schema (Pydantic + TS) + `GateExecutedImpactCard` 표 컬럼 추가
- [x] **P10d** — store +6 tests + router +2 tests

#### 남은 작업 — 외부 의존성
- [ ] **sim_v2 parser callsite receiver type** — 현재 시드 1290 row 가 모두 빈 receiver. parser 측 작업 (협업 필요)
- [ ] **production_db tests** — `tests/sim_v2/.../test_production_*` 는 slab-design-real 외부 데이터 시드 + alembic 의존 (별도 ticket)

### Phase 3 — 통합 + 검증 / Phase 4 — 옛 path deprecate
- 자세히는 `CHAT_REDESIGN_SPEC.md` §10

### Phase 13a — locate / explain intent + executed_lookup (2026-05-18)

> 방안 C (점진적) 첫 단계. 매 단계 페르소나 검증 후 진행.

- [x] intent 5종 (locate / explain 추가) + LLM prompt 가이드
- [x] BusinessRuleEvidence + GateExecutedLookup schema
- [x] gate_executed_lookup.py — body + meta + callers + linked_term + rules 통합
- [x] SimV2BackedOntologyClient.get_method_meta — file_path/line/return_type SQLite query (Bug fix from persona test)
- [x] router state machine — target_selected + confirm + locate/explain → executed_lookup
- [x] tests/simulation/test_multiturn_phase13a_locate_explain.py 14 PASS + simulation 181 PASS regression 0
- [x] 4 페르소나 subagent 검증 — 김PM ★★★★★ (locate) / 박주니어 ★★★★ (fix 후) / 시니어 ★★★★ / QA ★☆ (13c 까지 대기)

### Phase 13b — search keyword extraction + 0-cand fallback (2026-05-18, ✅ 완료)
- [x] **search keyword extraction** — LLM intent prompt 에 `search_terms` 도 함께 추출 (예: "엣징 마진 변경하면 어디 영향?" → ["엣징", "마진"]). 풀 query 매칭 실패 해결.
- [x] **0-cand fallback** — `business_terms.aliases_json` substring 매칭으로 인접어 suggestion (`GateTarget.suggestions`)
- [x] tests/simulation/test_multiturn_phase13b_search.py **13 PASS** + simulation suite 209 PASS regression 0
- [x] 4 페르소나 subagent 검증 — 김PM Yes / 박주니어 Yes / 시니어 silent wrong target 위험 발견 (Phase 13c 가 해결) / QA 2.5/5 (Phase 13c 절실)

### Phase 13c — hypothesis intent + conditions + executed_hypothesis (2026-05-18, ✅ 완료)
- [x] **hypothesis intent 6 번째 카테고리** — boundary / edge case 질의. LLM `_SYSTEM_PROMPT` 에 한국어 비교 연산자 매핑 ("미만"→"<" 등)
- [x] **conditions 추출** — `IntentDecision.conditions: list[{"var","op","value","unit"}]`. boundary value (1.0, 0.1mm, 0) 보존
- [x] **GateExecutedHypothesis payload** — body + verdict (yes/likely_yes/likely_no/no/unknown) + reasoning + evidence + confidence
- [x] **gate_hypothesis.py builder** — heuristic verdict inference (body 안 var/value/op 시그널 + rule.statement 매칭). signals=0 → unknown (정직)
- [x] router turn 3 hypothesis → build_gate_hypothesis + `_next_gate_kind`
- [x] tests/simulation/test_multiturn_phase13c_hypothesis.py **13 PASS** + simulation suite **222 PASS** regression 0
- [x] 3 페르소나 subagent 검증 — QA 4.0/5 (이전 2.5 → +1.5) / 김PM 3.5/5 / 시니어 Conditional Yes (silent wrong target 위험 ELIMINATED)

### Phase 14 (페르소나 13c 검증 잔여)
- [x] **14A — confirm guard for 0-cand** (2026-05-18) — confirm 엔드포인트가 candidates=[] / selected_index OOR / 누락 시 즉시 422 + suggestions hint detail. tests 5 PASS + 회귀 2건 fix + simulation 227 PASS.
- [x] **14E — 한·영 alias gap** (2026-05-18) — `_expand_search_terms` (strict token 매칭) + `_fetch_related_term_fqns` + `_apply_ranking_boost(term_fqns_in_query=...)` (+10 boost). 9 tests PASS + simulation 236 PASS regression 0. 시니어 Conditional Yes. ValidationResult noise 제거. "두께→thickness" 케이스는 modeling 시드 데이터 1행만 채우면 자동 발현.
- [x] **14C — suggestions chip auto-research + hypothesis/lookup card render** (2026-05-18) — frontend `onSuggestionClick` 1-click 새 세션 + `GateTargetCard` suggestions chips/conditions chips + `GateExecutedReadOnlyCard` 신규 (lookup/hypothesis 통합 verdict+evidence). TS clean + simulation 236 PASS. PM 8.0/10. **잔여 R1 (suggestion chip vocabulary 매칭 quality), R2 (confirm+respond 2-step retry).**
- [x] **14D — body × conditions 매칭 정밀화** (2026-05-18) — `_infer_verdict` 4 정밀화 (var AND token / value word-boundary / co-occurrence +2 / expression regex +3) + var-miss false positive 강등. 8 tests PASS + simulation 244 PASS. QA+PM 통합 검증 — PM 의 13c false positive 해결.
- [x] **14B MVP — fixture compatibility check** (2026-05-18) — `_check_fixture_compat` (var ↔ param name 매칭 + value/param type 호환) + `_fetch_method_params` SQLite. compat=True → verdict 강화 (likely_yes→yes), compat=False+type incompat → 약화, compat=False+var miss → 경고만 (false negative 차단). 8 tests PASS + simulation 252 PASS. 시니어 Conditional Yes (S1 회귀 발견 후 즉시 fix).
- [x] **14F MVP — anchor_bindings 활용** (2026-05-18) — `_fetch_anchor_bindings` + `build_gate_hypothesis` 가 condition var ↔ anchor.target_slot 매칭 시 anchor_signals 가중 (×2). confidence formula 갱신 (signal ≥ 4 → 0.85). Provenance source 에 anchor 카운트 + matched slots surface. 5 tests PASS + simulation 257 PASS. 실 검증: "주문 수량 0" → 4 anchors / confidence 0.75 → 0.85.

### Phase 15 — modeling 시드 데이터 패치 (2026-05-18, ✅ 완료)
- [x] **15A — thickness term + SdThicknessAction declared_on_term 정정** — 시니어 페르소나 "1행+1컬럼" 예측 검증. SdThicknessAction.execute #1 으로 역전. 시니어 YES.
- [x] **15B — 5 dimension terms batch seed (length/width/weight/slab_count/split)** — 14 actions declared_on_term 정정. PM 9/10. 4/5 시나리오 silent wrong target 완전 소멸.
- [x] **15C — fill declared_on_term=None via FQN pattern (11 actions) + margin term** — 12 도메인 패턴 자동 매핑. PM 4.4/5. cumulativeProductivity/엣징/history 도메인 즉시 매칭.

### Phase 16 — Korean↔English alias bridge end-to-end (2026-05-18, ✅ 완료)
- [x] **16A — `_check_fixture_compat` alias bridge** — `_expand_var_to_aliases` (token-level) + `_check_fixture_compat(repo_id=...)` + `_infer_verdict` rule-driven branch. 7 tests + 시니어 S1 완전 해결. simulation 264 PASS.
- [x] **16B — `_infer_verdict` body match alias bridge** — `var_aliases_per_cond` 인자 + multi-token alias + expression regex 각 candidate 시도. 5 tests + 시니어 S2 갭 직접 해결 (verdict likely_no → yes). simulation 269 PASS.

### Phase 16+ 후속 (시니어 16B 권고)
- [x] **16C — verdict-fixture cross-check assertion** (2026-05-18) — `_compute_integrity_warnings` (W1/W1b/W2/W3) + sources Provenance surface. 7 tests + simulation 276 PASS. QA 5/5 false positive 0 + W1b 실 데이터 발화.
- [x] **16D — extended warnings W1c + W4** (2026-05-18) — `_compute_integrity_warnings(matched_var, target_fqn)` 인자 + body_unsupported_alias_gap + target_is_test 2 종. 7 tests + simulation 283 PASS. QA 라이브 W4 (SdWidthRangeActionTest + SdThicknessActionTest) 정확 발화.
- [x] **16E — frontend integrity_warning UI badge** (2026-05-18) — `GateExecutedReadOnlyCard` parseIntegrityWarnings + 6 종 색상 칩 (빨강/주황/노랑 신호등). TS clean. PM "코드 안 읽고 인지 가능" 직관적.
- [x] **16F — multi-cond AND verdict semantics** (2026-05-18) — `_infer_verdict` 에 per_cond_matched tracking + cond_match_suffix (N/M 매칭) 모든 verdict 분기 attach + partial multi-cond fixture-compat boost 승격 보류 (`is_partial_multi_cond` regex guard). 7 tests + simulation 290 PASS. QA 2회 사이클 (1차 dead-code/boost 무력화 fix → 2차 라이브 partial=likely_yes·single=yes 검증).
- [x] **16G — alias source 확장: Action + CodeField @Column** (2026-05-18) — `_expand_var_to_aliases` 가 3 source union (BusinessTerm + Action.aliases_json + CodeField `@Column(name=XXX)` 양방향 bridge). case-preserving dedup. 8 tests + simulation 298 PASS. 시니어 SHIP: S1 `thickness`+THICKNESS / S2 `ORDER_NO`+orderNo / S3 `orderNo`+ORDER_NO. Action source 는 데이터 빈약 (95% generic `["execute"]`) 으로 effective-dead but no harm.
- [x] **16H — Action.aliases_json Korean 시드 보강** (2026-05-18) — `scripts/seed_phase16h_action_korean_aliases.py` idempotent. FQN+label Korean 토큰 추출 + stopword 필터 (`실행/검증/처리/확인/검사/수행/조회/갱신` 단독 제외). 6 actions updated, +10 specific Korean aliases. derive 6 unit tests + simulation 304 PASS. 시니어 라이브 SHIP: `슬랩설계/정합성/고객표준/매칭` 모두 Action label/aliases bridge, `실행/검증` stopword 차단, 회귀 0.
- [x] **16I — UX polish (PM 16E #2 + #3)** (2026-05-18) — `GateExecutedReadOnlyCard.tsx` 의 빨강 칩 발화 시 confidence % 취소선·회색 (`dimmed` prop) + 노랑 N≥3 동시 발화 시 단일 그룹 칩 (title hover 로 세부 보존). TS clean + backend 304 PASS 유지. PM SHIP — dim/그룹화 의도대로, 정보 보존 OK.
- [x] **16J — target_is_test retry CTA (PM 16E #1 HIGH)** (2026-05-18) — `GateExecutedReadOnlyCard` 에 `onRetryWithDifferentTarget` prop + `MultiturnChat` 핸들러로 새 세션 같은 query 1-click 시작. RotateCcw 아이콘 + primary 컬러 칩. TS clean + backend 304 PASS. 자동 pick 대신 사용자 선택 (LLM rerank variance 회피).
- [x] **16K — declared_on_term score 가중치 explicit surface** (2026-05-19) — `ActionCandidate` 에 role/parent_role/annotations/declared_on_term TS 필드 + `GateTargetCard` 메타 칩 row (pink-50 declared_on_term 강조, role 색상 매핑, annotations 최대 3 + `+N more`). hover tooltip 으로 boost rationale 설명. TS clean + backend 304 PASS.
- [x] **16L — dashboard integrity_warning 발화율 metric** (2026-05-19) — `compute_warning_rates` 함수 + `WarningRates` dataclass + `GET /api/section3/multiturn/metrics/warnings` endpoint + `DashboardPanel WarningRatesSection` (16E 신호등 동기화 칩 + %). 9 tests + simulation 313 PASS. PM 16E LOW #4 완료.
- [ ] **실 fixture invoke** (multi-day, 정석)
- [x] **16M — suggestion chip quality 보강** (2026-05-19) — `_KOREAN_QUERY_STOPWORDS` (16 generic 동사) + lowercase 동일 토큰 제외. 7 tests + simulation 320 PASS. PM SHIP 라이브: "주문" 첫 chip "통합 주문" / "주문 검증" 주문 도메인 유지 / "검증" stopword 단독 → graceful empty.
- [x] **16O — 0-cand query 매핑 갭 자동 탐지** (2026-05-19) — `list_zero_cand_queries` + `GET /metrics/zero-cand-queries` + `DashboardPanel ZeroCandQueriesSection`. 10 tests + simulation 330 PASS. modeling team 이 "어떤 단어로 매칭 실패했나" 자동 인지 가능.
- [x] **16P — 공통 WARNING_META util 추출** (2026-05-19) — `frontend/src/lib/section3/warning_meta.ts` 신설. `GateExecutedReadOnlyCard` + `DashboardPanel` 두 소비자 단일 source 로 통합. ~95 라인 중복 제거. TS clean + backend 330 PASS 유지.
- [x] **16Q — 추가 production action declared_on_term 시드** (2026-05-19) — `scripts/seed_phase16q_additional_declared_on_term.py` (idempotent). 명확한 4건만 (find_group / lookup_or_default / extract_designable_orders / batch_design__driver). 79 → 75 None remaining. test fixtures + 모호 매핑 skip (target_is_test 회피).
- [x] **16R — backend IntegrityWarningKind canonical + frontend sync test** (2026-05-19) — `integrity_warning_kinds.py` (Literal + frozenset + emit_warning helper) + `gate_hypothesis` 6 hardcoded → `emit_warning()`. cross-language sync 자동 검증 5 tests. simulation 335 PASS.
- [x] **16S — VERDICT_META util 추출** (2026-05-19) — `lib/section3/verdict_meta.ts` 단일 source. 16P 패턴 적용. TS clean.
- [x] **16T — gate_i ranking boost weights 외부 모듈화** (2026-05-19) — `ranking_weights.py` 8 상수 (ROLE/PARENT_ROLE/DOMAIN_ANNOTATIONS/CLASS_PATTERN/FQN_EXACT/NAME_TOKEN/DECLARED_ON_TERM + DOMAIN_ANNOTATION). pure refactor — behavior 변동 0, simulation 335 PASS. 미래 튜닝 인프라.

### Phase 17~20 — 3-Stage UX 재설계 (사용자 vision)
- [x] **17 — IntentStage hero + 3-Stage workflow frame** (2026-05-19) — `IntentStage.tsx` (intent + conditions + provenance + collapse) + `WorkflowFrame` 컨테이너 + `StageFrame` 공통 header. agent-centric gate → user-centric 3 stage. backend 변동 0.
- [x] **18 — Stage 2 Scope endpoint + ScopeStage panel** (2026-05-19) — `scope.py::build_scope` 병렬 aggregator (callers + sibling actions + term + rules) + `POST /scope` endpoint + `ScopeStage.tsx` (kind 별 그룹 + Test 자동 제외). 6 tests + simulation 341 PASS. MVP list view (graph + checkbox simulate 반영은 후속).
- [x] **19 — Stage 3 SimulateStageHeader** (2026-05-19) — 영역 / Fixtures / 상태 / 결과 요약 4 섹션 thin header. simulation/impact/hypothesis/lookup 4 종 결과 한 줄 surface.
- [x] **20 — SessionHeader stage progress dots** (2026-05-19) — 3개 dot (current ring / pass emerald / pending border) + computeCurrentStage(decisions). 페이지 어디 있어도 1초 인지.

### Phase 21 — 사용자 critique 대응 (agent 실제 변경)
- [x] **21a — EmptyState 재설계** (2026-05-19) — 🎯 무엇을 알고 싶으세요? hero + 5 intent category 카드 + 최근 세션 list + 고급 옵션 collapse. examples 클릭 시작.
- [x] **21b — Intent confirmation step (agent 흐름 변경)** (2026-05-19) — 새 turn `intent_classified` 추가. stub → /respond → intent_classified → confirm → target_selected → confirm → Gate II/III. `INTENT_CONFIRM_REQUIRED` 모듈 flag (production True / 기존 tests False). `GateIntentClassified` schema + `build_intent_classified()` + content-driven dispatch 4 case + IntentStage [✓ 맞아 → 후보 찾기] / [↻ 다른 의도로] 버튼. 새 테스트 7 (production 흐름 E2E) + 기존 348 PASS = **355 PASS**.

### Phase 17~21 후속 (미구현 항목)
- [ ] **17b/21c** — IntentStage inline edit (조건 chip 클릭 수정 + 자연어 intent 직접 수정)
- [ ] **18b** — ScopeStage graph view + checkbox 가 simulate scope 반영 (영역 zoom)
- [ ] **18c** — Scope 의 fixture 사전 surface ("X actions × Y fixtures 예상")
- [ ] **19b** — Fixture editor (auto/load/manual 3-source 토글 + 직접 입력 table)
- [ ] **19c** — 결과 inline 비교 (Java vs Python row-by-row)
- [ ] **20b** — Cmd+K command palette (BusinessTerm/Action/FQN/session 전역 검색)
- [ ] **22a** — condition chip inline editor (var/op/value/unit 수정)
- [ ] **22b** — search_terms 수정 UI (사용자가 추출 키워드 add/remove)
- [~] **margin action 데이터 시드** (modeling 측) — 16N 조사 결과 codebase 에 margin Java 코드 0건. 시드 대상 없음 → modeling team 의 실제 margin method 추가 대기.
- [ ] **score 가중치에 declared_on_term explicit surface** (UI/UX)

### Phase 12 Activation — 기존 ontology 데이터를 agent 가 깨우기 (2026-05-18)

> 데이터 vs agent 활용 감사 결과 (`multiturn_data_vs_agent_audit.html`) — 마찰점 10 중 6 = agent 미활용. 새 기능 0, 재배선 5 항목.

- [x] **Item 1** SimV2BackedOntologyClient.get_caller_graph stub → SQLite CodeLayerStore 직접 query
- [x] **Item 2** Gate III impact `_impact_confidence` caller_count=0 시 cap 0.5
- [x] **Item 3** ActionCandidate schema 확장 — role/parent_role/annotations/declared_on_term
- [x] **Item 4** Ranking boost — role + parent_role + annotations + class pattern + FQN substring + 의미 토큰
- [x] **Item 5** business_rules evidence 5 행 sources surface
- [x] tests/simulation/test_multiturn_phase12_activation.py 11 PASS + simulation suite 169 PASS regression 0
- [x] 실 backend 페르소나 회귀 — SdThicknessAction 이 #1 으로 역전, affected_methods 1 surface, DG001~DG003 statement surface

### Phase 13 (예정) — 사전 부스트 + anchor 활용 + 0-cand fallback
- [ ] anchor_bindings 163 행을 synthesize_fixtures 에 inject (QA 가설값 80% 해결)
- [ ] KoreanTermResolver score 를 랭킹에 합산
- [ ] 0-cand 시 동의어 / aliases 제안 + browse 모드
- [ ] 사전-merge 후보 pool 확장 (top_n 5 → 15) — FQN substring boost 가 더 많은 후보에 작동

### Phase 11.5 — Dashboard 정리 + repo 인식 (2026-05-18)

> 사용자 지시: 깨진 / 쓸모없는 섹션 제거 + 실 데이터 띄우는지 확인 + repo 별 동작 확인.

- [x] **제거**: ontology 노드 5 카드 (Neo4j 0) + relations 16 칩 (Neo4j 0) + 빠른 진입 4 카드 (legacy hidden views) + dev-only amber tip
- [x] backend `GET /api/section3/repos` — repo 별 8-카운트 SQLite 집계
- [x] tests/simulation/test_section3_repos.py 6 PASS
- [x] frontend `listRepos()` + `RepoSummary`/`RepoCounts` 타입
- [x] frontend DashboardPanel 전면 재작성 — repo 칩 + 8-카운트 카드 + repo 필터된 세션 리스트
- [x] 실 backend 검증 (130 actions / 1081 methods / 150 types / 76 terms / ... 표시 OK)
- [x] repo 필터 검증 — slab-design-real-v2 3 세션, other-repo 0 세션

### Phase 11 — Session History Browser (2026-05-18, Option B 채택)

> 분석 출발점: `toClaude/simulation/dashboard_value_analysis.html` (5 옵션 인터랙티브 평가). 사용자 결정 = 최소 (권장) 프리셋 = A + B. C/D/E 는 backend persistence 깔린 후 재평가.

- [x] backend `persistence.list_recent_sessions` + `SessionSummary` (turn_count + last_gate_kind aggregate, last_activity_at desc, ilike search)
- [x] backend `GET /api/section3/multiturn/sessions` endpoint (limit/repo_id/search)
- [x] tests/simulation/test_multiturn_session_list.py 14 PASS
- [x] frontend `listSessions()` + `SessionSummary` type
- [x] frontend `useMultiturnSession.loadSession(sid)` 액션 노출
- [x] frontend `MultiturnChat` initialSid / onNewSession props
- [x] frontend `Section3Section` `?sid=` URL param + popstate + openSession 콜백
- [x] frontend `DashboardPanel` 의 `RecentSessionsSection` (debounced search + 카드 리스트 + Gate 라벨)
- [x] 실 백엔드 curl + tsc clean 검증
- [ ] (보류) 옵션 C/D/E — backend persistence (verification 8-axis log / proposal audit / llm_call) 깔린 후
- [ ] (보류) Maturity badge — 대시보드 상단에 UC36 capstone 통과 시각 + MERGED proposal 수 (modeling 시드 hook 후)

