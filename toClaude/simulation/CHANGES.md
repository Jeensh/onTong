# Section 3 — Simulation CHANGES

Ad-hoc change log. `[x]` = done, `[ ]` = deferred/pending.

## 2026-05-17 (Chat 멀티턴 재설계 Phase 0)

브랜치: `section3/chat-agent-redesign` (origin/main 기준).

- [x] 4 인계 문서 정독 (HTML report § 1~10, MD report, `bridge_agent.py`, `backend/application/authoring/` 구조)
- [x] `toClaude/simulation/CHAT_REDESIGN_SPEC.md` 작성 (291 LOC, 12 섹션)
  - 6 게이트 정의 + state machine + tool catalog (per-gate allow-list)
  - GatePayload discriminated union schema 설계
  - `section3_decision_log` 테이블 schema + Phase 1~4 rollout
  - Mock 전략 (협업 요청 미구현 항목 → sim_v2_bridge 동일 기능 wrapper)
  - 차용 매핑 (Section 2 7 패턴 → Section 3 위치)
- [x] commit `9cb354e` on `section3/chat-agent-redesign`
- [ ] 사용자 spec 리뷰 + 4 default decision 확인 (다음 세션)
- [ ] Phase 1 진입 (인프라 scaffold + 마이그레이션)

## 2026-05-16 (★ Sprint 2~5 — Section 4 인계 recipe-2/3/4/5 + 옵션 B 통합)

Section 4 인계 패키지의 Sprint 2~5 통합 (Sprint 1 직후 연속 진행).

### Sprint 2 — recipe-2 Java baseline 부착
- [x] `sim_v2_bridge.run_fixtures_with_baseline()` — W73 attach_baselines + BehaviorTwinRunner
- [x] `sim_v2_bridge.load_baseline_map(method_fqn)` — `data/baselines/{safe_fqn}.json` file-based
- [x] `sandbox_agent._run_via_simv2` 가 baseline 파일 존재 시 자동 oracle 경로 사용
- [x] case_result 새 필드 — `expected_value`, `actual_value`, `output_match`, `diff_summary`
- [x] frontend `EventStreamView` — input/expected/actual 3-컬럼 grid + diff_summary 경고
- [x] `data/baselines/README.md` 신설 (파일명 규칙 + JSON shape 문서화)
- [x] 알려진 한계: W74 MagicMock stub 이 `BehaviorTwinRunner` 와 mismatch (UC40 FAIL_RETURN_TYPE). typed-return stub sim_v2 후속 작업이 close 예정.

### Sprint 3 — recipe-3 invariant 진단 → chat fallback surface
- [x] `sim_v2_bridge.quick_diagnose_action()` — W71→W74→W72 quick diagnose (passing/fixtures/stubs/primary_failure)
- [x] `bridge_agent._emit_simv2_suggestions()` — `simulate` intent 의 missing target 시 호출
- [x] 새 스트림 이벤트 `simv2_suggestions` — query / count / suggestions[]
- [x] frontend `EventStreamView` — suggestion 카드 (label/fqn/score/diagnostic) UI

### Sprint 4 — recipe-5 W77+W78 한국어 검색 → bridge 통합
- [x] `sim_v2_bridge.find_action_candidates(user_query, repo_id, top_n)` —
  - W77 KoreanTermResolver (한↔영 + fuzzy)
  - `actions.declared_on_term` IN 매칭 term FQN
  - actions LIKE 보완 (label/aliases/fqn token)
- [x] bridge_agent 의 `simulate` 분기에서 `_emit_simv2_suggestions(user_query)` 자동 호출
- [x] end-to-end 실측: "주문 검증" → 3 후보 (`정합성_검증`/`slab design`/`final_length_range_실행`) + invariant 진단 동봉

### Sprint 5 (opt) — transpiler 옵션 B (sim_v2 subclass 화)
- [x] `backend/section3/section3_translator.py` 신설 — sim_v2 `JavaToPythonTranslator` 의 동적 subclass
  - `__new__` 가 sim_v2 base 와 dynamically 합성한 `Section3TranslatorImpl` 반환
  - sim_v2 가 없으면 None 반환 (graceful)
  - `_IDIOM_REWRITES` extension point (현재 비어 있음 — sim_v2 W75 가 50+ idiom 자동 처리)
  - `_translate_method_invocation` override: section3 idiom 먼저 시도 → fallback super()
- [x] `sim_v2_bridge.translate_java_to_python` 가 Section3Translator 사용
- [x] `backend/section3/transpiler.py` (이전 자체 transpiler) 는 legacy composer 경로 호환 위해 잔존 (사용 빈도 0 — ontology.db 비어 있음)

### 검증
- [x] `tests/simulation/test_sim_v2_bridge.py` — 13 test (Sprint 1: 6 + Sprint 2: 3 + Sprint 3/4: 3 = +7)
- [x] end-to-end cumulativeProductivity → 12/12 PASS · 3 stubs · invariant only
- [x] end-to-end bridge `_emit_simv2_suggestions("주문 검증")` → 3 후보 + 진단 surface
- [x] 백엔드 재기동 후 /health 200, frontend / 200

### 데모 6종 (Quickstart Step 4)
| Demo | 결과 |
|---|---|
| UC41 한국어 검색 | 9/10 hit (90%) |
| UC42 hybrid tier | T1 3/3 · T2 3/4 · T3 1/2 · T4 1/1 |
| UC40 stub-injected | 6/11 PASS (54.5%) |
| UC37 fixture coverage | 11/38 driveable |
| UC38 invariant survey | 0/11 baseline-free (expected) |
| UC36 v2 capstone | FULLY CLEAN — 30 MERGED proposal |
| bonus recipe-5 | typo + 비표준 음역 close |

## 2026-05-16 (★ Sprint 1 — Section 4 인계 recipe-4 통합)

Section 4 인계 패키지 (`toClaude/modeling/section4-verification/section3_handoff/`) 의 sim_v2 자산 W71→W75→W74→W72 full pipeline 을 sandbox_agent.py 에 통합.

- [x] **`backend/section3/sim_v2_bridge.py` 신설** — sim_v2 자산 thin wrapper
  - `open_sim_v2_session()` — `data/slab-v2-handoff.db` read-only Session (없으면 None, 폴백 friendly)
  - `load_action()` — sim_v2 `ProductionAction` lookup (description 파싱으로 code_method_fqn 획득)
  - `load_body_text()` — `code_methods.body_text` 조회
  - `translate_java_to_python()` — sim_v2 `JavaToPythonTranslator` 래퍼 (W75 idiom 자동 적용)
  - `synthesize_fixtures()` — W71 `synthesize_fixtures_for_action`
  - `build_stubs()` — W74 `build_stub_namespace` (anchor + AST + entity)
  - `run_fixtures_in_process()` / `run_in_process()` — W72 `TwinInvariantRunner.check()` 래퍼. section3 case_result shape + `invariant_status` 필드 추가

- [x] **`backend/section3/agents/sandbox_agent.py` 통합**
  - `run()` 진입 직후 `_is_action_fqn(req.target_id)` 감지 → sim_v2 직통 시도
  - 신규 메서드 `_run_via_simv2()` — recipe-4 등가 흐름 (body → translate → fixtures → stubs → invariant)
  - 새 스트림 이벤트: `simv2_fixtures` (count/synthesizable/skipped), `simv2_stubs` (count/sample)
  - sim_v2 session 미사용 가능 / action 미존재 시 기존 composer+subprocess 경로로 폴백
  - 백엔드 회귀 0건 — 기존 step/method/class 경로는 그대로

- [x] **`tests/simulation/test_sim_v2_bridge.py` 신설** — 6 test
  - bridge import / session open / build_stubs (cumulativeProductivity) / run_in_process 기본·stub·실패 분류
  - 6/6 통과

- [x] **end-to-end 실측 검증**
  - `action.scm.product.cumulative_productivity` → **12/12 fixture PASS · 3 stubs auto-derived** (`DEFAULT_PRODUCTIVITY`, `lookupOrDefault`, `SdConstants`)
  - 백엔드 재기동 후 `/health` HTTP 200 확인

- [x] **새 contract 필드 (sandbox_result 내부)**
  - `cases[i].invariant_status` ∈ `{PASS, FAIL_NONDETERMINISTIC, FAIL_UNEXPECTED_THROW, FAIL_RETURN_TYPE, ERROR}`
  - `stub_summary: {count, sample[]}`
  - `via: "sim_v2"` — 새 경로 식별자

- [x] **회귀**: sim_v2 1790 passed (기존 상태 유지, 93 failed/6 errors 는 Sprint 1 무관 — schema migration/data fixture 부재)

배경: `data/ontology.db` 가 비어 있어 기존 HTTP `/api/ontology/*` 경로는 데이터 부재로 동작 불가. Section 4 가 제공한 `data/slab-v2-handoff.db` (3.4MB · 38 actions · slab-design-real-v2) 가 유일한 실측 가능 데이터 소스.

## 2026-05-10 (★ STEP 3f-2 — 랜딩 페이지 재개편 + 모든 패널에 ontology evidence UI)

사용자 피드백: "section3.html 눈에 안 들어오고 내용 빠짐. ontology 근거 어디서 보냐 — 모든 시뮬 기능에 적용 근거 보여야"

- [x] **OntologyEvidencePanel.tsx 신설** (재사용 컴포넌트)
  - props: { runId?, actionFqn?, autoOpen?, variant }
  - 4 evidence kind 색상 구분 (Action / Realization / BR / AnchorBinding)
  - summary chips + per-kind 그룹 expand
  - `OntologyEvidenceToggle` — 다른 panel 에 임베드용 토글

- [x] **OntologyEvidenceView.tsx 신설** (메인 진입점 view)
  - 자주 쓰는 action_fqn preset 2종 (match_customer_limit / 슬랩설계_실행)
  - free input + ontology actions 검색 (autocomplete)
  - OntologyEvidencePanel 임베드

- [x] **SimulationSection.tsx — 좌측 메뉴에 "온톨로지 근거 보기" view 추가**
  - 탐색 그룹의 첫 번째 항목으로 등장
  - URL: `?section=simulation&view=evidence`

- [x] **4 핵심 panel 에 OntologyEvidenceToggle 통합**
  - `RunHistoryPanel` — 각 run 의 detail 영역. step_id → action_fqn 매핑 (STEP_TO_ACTION 테이블)
  - `SandboxPanel` — 샌드박스 결과 영역 (15 step → action 매핑)
  - `RegressionPanel` — 비교 결과 옆
  - `JavaPythonComparePanel` — 헤더 영역 ("Java/Python 모두 같은 ontology Action 기반")

- [x] **backend `/api/simulation/ontology-evidence/by-action` 신설**
  - run_id 없이 action_fqn 만으로 evidence 조회 (lightweight)
  - SandboxPanel / Differential / NavigatorPanel 같은 곳에서 spec 03 run 트리거 없이 즉시 조회 가능

- [x] **frontend/public/section3.html 전면 재개편 (745 → ~880 lines)**
  - 9 panel 카탈로그 grid (3x3) — 한 눈에 모든 기능 + endpoint + ontology 매핑 명시
  - hero 통계 4 stats (9 패널 / 58 endpoints / 4 evidence kind / 423 회귀)
  - WHY 4가지 한계 (정적 분석 / 도메인 용어 / Java↔Python / 근거 추적)
  - 4 evidence kind 시각 도식 (색상 구분 + facade call + data 필드 명시)
  - 5 컴포넌트 flow (RunPlanBuilder → PythonGenerator → JavaSandbox → Orchestrator → RunHandleStore)
  - 5 카테고리 differential 표 (matched / mismatched / java_only / python_only / both_null)
  - spec 03 핵심 12 endpoint 표 (method + path + 설명)
  - Section 2 통합 5 지점 카드 (delegates_to_tree / Realization / TableSpec / AtomicOverridePatcher / OntologyEvidence)
  - 운영화 6 reveal (TimeoutBudget / artifact disk / JvmSubprocess / async queue / promote / dual ontology)

- [x] 회귀: by-action endpoint test 2종 추가 → **425 passed** (이전 423 → +2: by-action 2종)
- [x] TypeScript 빌드 통과 (npx tsc --noEmit)

## 2026-05-10 (★ STEP 3f — 사용자 3 요구사항 + 통신 검증)

- [x] **0번 — Section 2 ↔ Section 3 통신 방식 검증**
  - `06-developer-onboarding.md` Q4 (line 501-506) + line 78 → HTTP / Python facade 둘 다 명시 허용
  - 결정: in-process facade 유지 (사용자 "규약대로 진행")
  - landing page chapter 03 reveal 에 명시 결정 기록

- [x] **요구사항 1 — Java↔Python differential 정합성**
  - `backend/simulation/jvm_bridge/differential.py` — 5 카테고리 분류 (matched/mismatched/java_only/python_only/both_null)
  - `_normalize_payload()` helper — null/빈값 재귀 제거
  - `_classify_diff()` helper — (java_value, python_value) → (category, is_close)
  - `DifferentialResult` 신규 필드 — matched_count / mismatched_count / java_only_count / python_only_count / both_null_count / summary / java_payload_normalized / python_payload_normalized
  - 16 test 통과 (`tests/simulation/test_differential_classification.py`)

- [x] **요구사항 2 — Ontology evidence endpoint**
  - `backend/simulation/api/ontology_evidence_router.py` 신설 (+250 lines)
  - `GET /api/simulation/runs/{run_id}/ontology-evidence`
  - 4 evidence kind — action / realized_method / br / anchor
  - 각 trace: evidence_kind / evidence_id / ontology_source / ontology_facade_call / ontology_data / explanation
  - `backend/main.py` — router 등록
  - 7 test 통과 (`tests/simulation/test_ontology_evidence.py`)

- [x] **요구사항 3-A — 랜딩 페이지 전면 재작성**
  - `frontend/public/section3.html` — Apple SD Gothic Neo + Claude warm cream(#faf9f5) + accent orange(#d97757)
  - 6 chapter 스토리라인 (왜/무엇을/어떻게/근거/Java↔Python/운영화)
  - 8 `<details class="reveal">` 블록 — 호기심 유발 클릭 expand
  - hero + stats grid + flow steps grid + CTA band

- [x] **요구사항 3-B — 좌측 toc → 상단 sticky nav**
  - 이전: `<nav class="toc">` 좌측 250px 고정 (12 항목)
  - 새: 상단 sticky nav + chapter scroll + scroll spy (현재 chapter accent 색)
  - `frontend/public/section3.legacy.html` — 이전 버전 보존 (사용자 지시 "지우진말고")

- [x] 회귀: **423 passed** (이전 400 → +23: differential 16 + ontology evidence 7), 17 skipped, 3 failed (sample-repos — 무관)
- [x] `toClaude/simulation/log/step_3f_summary.md` 작성

## 2026-04-17
- [x] 상단 SectionNav에서 Simulation 탭의 "soon" 배지 제거
  - `frontend/src/components/sections/SectionNav.tsx` Simulation entry `status: "scaffolding"` → `"active"`
  - 이유: Section 3 엔드포인트 동작 확인됨, 더 이상 예정 상태 아님
- [x] `networkx` 의존성 추가 및 설치
  - `pyproject.toml`: `[tool.poetry.dependencies]`에 `networkx = "^3.2"` 선언 (Graph Database neo4j 섹션 아래)
  - `venv/`에 `networkx 3.6.1` 설치 (`venv/bin/pip install "networkx>=3.2,<4"`)
  - 이유: `backend/simulation/tools/ontology_graph.py:13`의 top-level `import networkx`로 인해 `/api/simulation/slab/ontology` + scenario A/B tool 500 에러 발생 중
  - 검증: `curl http://localhost:8001/api/simulation/slab/ontology` → HTTP 200, proxy `http://localhost:3000/...` → HTTP 200
