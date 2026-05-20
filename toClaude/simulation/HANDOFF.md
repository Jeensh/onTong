# Section 3 — Simulation HANDOFF

섹션 담당: 시뮬레이션 Claude 세션
쓰기 영역: `toClaude/simulation/`, `backend/section3/`, `frontend/src/components/section3/`
읽기 전용: `backend/sim_v2/`, `toClaude/modeling/`, `toClaude/wiki/`, `toClaude/_shared/`
**현재 cross-section 권한 부여됨** (사용자 명시 승인) — `backend/modeling/` + sim_v2 모두 편집 가능

---

## 🔴 다음 세션 첫 작업 (2026-05-19 갱신, **Phase 21a+21b — 진짜 agent 흐름 변경**)

**브랜치**: `section3/chat-agent-redesign`

### 가장 최근 작업 (Phase 21a → 21b, 2026-05-19)

사용자 critique ("multi턴 에이전트 그대로인데 어떻게 해야 테스트가 가능한거야") 정면 대응 — Phase 17~20 은 "decoration" 이었고 21a/21b 가 진짜 변경.

**21a — EmptyState 재설계**: 🎯 무엇을 알고 싶으세요? hero + 5 intent category 카드 (시뮬/영향/가설/위치/설명) + 최근 세션 list + 고급 옵션 collapse. examples 클릭으로 즉시 시작.

**21b — Intent confirmation step (agent behavior change)**:
- 새 turn: stub → **intent_classified** → confirm → target_selected → confirm → Gate II/III
- 사용자가 candidates 보기 전에 intent 잘못 분류된 걸 catch 가능
- `INTENT_CONFIRM_REQUIRED` flag (production True / 기존 348 tests False via autouse fixture)
- 백엔드: `GateIntentClassified` schema + `build_intent_classified()` + content-driven dispatch 4 case
- 프론트엔드: `IntentStage` 가 [✓ 맞아 → 후보 찾기] / [↻ 다른 의도로] 버튼 surface
- 새 테스트 7 (production 흐름 E2E) + 기존 348 PASS = **355 PASS** regression 0

### 진행하지 못한 부분 / 다음 세션 후보
- 21c: IntentStage inline edit (사용자가 자연어로 intent 직접 수정 — 현재는 "다른 의도로" 가 새 대화 trigger)
- 22a: condition chip inline editor (var/op/value/unit 수정)
- 22b: search_terms 수정 UI (사용자가 추출된 키워드 보고 add/remove)
- 23: SSE 진행 indicator 강화 (현재는 polling 기반 short-lived push)

### 이전 작업 (Phase 17 → 18 → 19 → 20, 2026-05-19)

사용자가 제시한 3-stage vision 그대로 구현:
1. **사용자 의도 파악** → IntentStage hero
2. **사용자 의도에 맞는 scope 파악** → ScopeStage list view (callers + sibling + term + rules)
3. **시뮬레이션 영역** → SimulateStageHeader 요약 + 기존 카드들

**17 — IntentStage**: `IntentStage.tsx` (intent type + conditions chip + user_query + provenance + collapse) + `WorkflowFrame` 3-stage 컨테이너.

**18 — Scope endpoint + panel**:
- `backend/section3/agents/multiturn/scope.py::build_scope` 병렬 aggregator
- `POST /api/section3/multiturn/scope` endpoint
- `ScopeStage.tsx` (kind 별 그룹 expand/collapse + Test 자동 제외 + checkbox readonly)
- 6 tests + simulation **341 PASS**

**19 — SimulateStageHeader**: 영역 / Fixtures / 상태 / 결과 요약 (simulation/impact/hypothesis/lookup 4 종 결과 한 줄).

**20 — SessionHeader stage progress dots**: 3 dot (current ring / pass emerald / pending border) + computeCurrentStage().

### MVP 한계 (후속 phases)
- 17b: IntentStage inline edit (chip 수정 + PATCH endpoint)
- 18b: ScopeStage graph view + checkbox 가 simulate scope 반영
- 19b: Fixture editor (auto/load/manual 3-source 토글)
- 19c: 결과 inline 비교 (Java vs Python row-by-row)
- 20b: Cmd+K command palette

### 이전 작업 (Phase 16R + 16S + 16T, 2026-05-19)

**16R** — backend `IntegrityWarningKind` canonical + frontend sync test.
- `backend/section3/agents/multiturn/integrity_warning_kinds.py` — Literal/frozenset/emit_warning
- `gate_hypothesis._compute_integrity_warnings` 6 hardcoded f-string → `emit_warning()`
- 5 tests + simulation **335 PASS** — cross-language drift test 가 backend/frontend kind set 정확 일치 강제
- 신규 kind 추가 시: 1) `integrity_warning_kinds.py` 2) `_compute_integrity_warnings` 3) frontend `WARNING_META` — 누락 시 테스트 실패

**16S** — `VERDICT_META` util 추출.
- `frontend/src/lib/section3/verdict_meta.ts` — 16P 패턴 적용 (5 verdict)
- `GateExecutedReadOnlyCard` 로컬 정의 제거 → `getVerdictMeta()` 호출

**16T** — `gate_i` ranking boost weights 외부 모듈화 (pure refactor).
- `backend/section3/agents/multiturn/ranking_weights.py` — 8 boost 상수
- `gate_i.py` 본체는 import 만 — 미래 튜닝/실험 (env override, repo profile) 토대
- behavior 변동 0, simulation 335 PASS 유지

### 이전 작업 (Phase 16Q, 2026-05-19)

**16Q** — 추가 production action declared_on_term 시드 (15C 잔여).
- 79 None action 분석 → 명확 매핑 4건만 안전 seed:
  - find_group → edging_group / lookup_or_default → productivity_std / extract_designable_orders → order / batch_design__driver → order
- 다수 None 은 `@Test` annotation 보유 test fixtures → seed 시 W4 target_is_test 위험 → skip
- 모호 매핑 (find_spec 5 polymorphic / classify_by_product_code 등) skip
- DB backup `data/ontology.db.bak-pre-phase16q-20260519-003706`
- declared_on_term=None: **79 → 75**. simulation 330 PASS 유지.

### 이전 작업 (Phase 16P, 2026-05-19)

**16P** — 공통 WARNING_META util 추출 (PM 16I 보고 권고).
- `frontend/src/lib/section3/warning_meta.ts` 신설 — WARNING_META 6 kind + RED/YELLOW kind sets + YELLOW_GROUP_THRESHOLD + parseIntegrityWarnings + getWarningMeta + 타입 정의
- `GateExecutedReadOnlyCard` + `DashboardPanel` 양쪽 로컬 정의 제거, util import 로 대체
- TS clean + backend 330 PASS 유지 (frontend refactor only)
- 효과: 향후 warning kind 추가 시 1 곳 수정 → 두 컴포넌트 자동 동기화

### 이전 작업 (Phase 16O, 2026-05-19)

**16O** — 0-cand query 매핑 갭 자동 탐지 (15C PM 권장 + 16L 후속).
- `list_zero_cand_queries(repo_id, limit)` + `GET /metrics/zero-cand-queries` + `DashboardPanel ZeroCandQueriesSection`
- ambiguous stub 제외 (real Gate I 진입 후 0-cand 만)
- 10 tests + simulation **330 PASS** regression 0
- 효과: modeling team 이 dashboard 에서 "어떤 단어로 매칭 실패했나" 자동 인지 → 시드 보강 가이드

**16N (skipped)** — margin action 시드. 조사 결과 codebase 에 margin Java 코드 0건 → 시드 대상 없음. modeling team 의 실제 margin method 추가 후 재검토.

### 이전 작업 (Phase 16M, 2026-05-19)

**16M** — 0-cand suggestion chip 품질 보강 (14C R1).
- `_KOREAN_QUERY_STOPWORDS` (16 generic 동사) + lowercase 동일 토큰 제외
- 7 tests + simulation **320 PASS** regression 0
- PM SHIP 라이브: "주문" 첫 chip "통합 주문" (informative) / "주문 검증" 검증 stopword 차단 주문 도메인 유지 / "검증" 단독 → graceful empty

### 이전 작업 (Phase 16K + 16L, 2026-05-19)

**16K** — declared_on_term ranking boost rationale 표면화.
- TS `ActionCandidate` 에 role/parent_role/annotations/declared_on_term optional 4 필드 (backend 이미 보유)
- `GateTargetCard` 메타 칩 row: declared_on_term 강조 (pink-50 + Link2) + role 색상 + annotations max 3
- hover tooltip 으로 boost rationale 설명. TS clean + backend 304 PASS.

**16L** — integrity_warning 발화율 dashboard metric.
- `persistence.compute_warning_rates(repo_id, limit)` — payload_json regex + per-session dedupe + by_kind_pct
- `GET /api/section3/multiturn/metrics/warnings` endpoint
- `DashboardPanel WarningRatesSection` (repo-scoped, 16E 신호등 색상 동기화)
- 9 tests + simulation **313 PASS** regression 0
- PM 16E #4 LOW 완료. target_is_test % 가 modeling 시드 품질 회귀 지표 / alias_gap % 가 BT alias gap 회귀 지표.

### 이전 작업 (Phase 16J, 2026-05-18)

**16J** — `target_is_test` 빨강 칩 retry CTA (PM 16E HIGH #1).
- `GateExecutedReadOnlyCard onRetryWithDifferentTarget` prop + 칩 옆 RotateCcw 버튼
- `MultiturnChat` 핸들러: `state.session.user_query` 로 새 세션 1-click 시작
- 자동 rank-2 pick 대신 사용자 선택 (LLM rerank variance 회피 + 투명성)
- TS clean + backend 304 PASS
- 빨강 칩 진단→해결 동선 회수, PM #1 목표 충족

### 이전 작업 (Phase 16I, 2026-05-18)

**16I** — `GateExecutedReadOnlyCard.tsx` UX polish (PM 16E #2 + #3).
- 빨강 칩 발화 시 confidence % 취소선·회색 (`VerdictBadge dimmed` prop)
- 노랑 N≥3 동시 발화 시 단일 그룹 칩 (`근거 약한 경고 N건`, hover title 로 세부 라벨 보존)
- frontend-only, TS clean, backend 304 PASS 유지
- 김PM SHIP — dim + 그룹화 의도대로, 정보 보존 vs 정돈 trade-off 적절
- 잔여: HIGH #1 rank-2 jump CTA (빨강 칩 진단→해결 동선) — Phase 17 우선 / LOW #4 W4 발화율 % dashboard

### 이전 작업 (Phase 16H, 2026-05-18)

**16H** — Action.aliases_json Korean 시드. 16G 시니어 라이브 verification 후속.
- `scripts/seed_phase16h_action_korean_aliases.py` (idempotent)
- FQN/label Korean 토큰 추출 + stopword 필터 (`실행/검증/처리/확인/검사/수행/조회/갱신` 단독 제외, compound 유지)
- 6 actions updated, +10 Korean aliases (`슬랩설계_실행/슬랩설계/정합성_검증/정합성/분류/결정/고객표준/매칭`)
- 6 derive unit tests + simulation **304 PASS** regression 0
- DB backup: `data/ontology.db.bak-pre-phase16h-20260518-233416`
- 시니어 라이브 SHIP: dead-capability 6 action 정확 활성화, over-expansion 0, BT 회귀 0

### 이전 작업 (Phase 16G, 2026-05-18)

**16G** — alias source 확장. 시니어 16B 권고 #3.
- `_expand_var_to_aliases` 가 3 source union: BusinessTerm → Action.aliases_json (129 rows) → CodeField `@Column(name=XXX)` 양방향 bridge (168 fields)
- case-preserving dedup (`thickness` vs `THICKNESS` 양쪽 surface)
- 8 tests + simulation **298 PASS** regression 0
- 시니어 SHIP: CodeField source 가 production 가치 분명 (S1 `thickness`+THICKNESS / S2 `ORDER_NO`+orderNo / S3 `orderNo`+ORDER_NO). Action source 는 데이터 빈약 (95% generic `["execute"]`) → effective-dead but no harm. 후속 권장: Action.aliases_json 한국어 보강.

### 이전 작업 (Phase 16F, 2026-05-18)

**16F** — multi-condition AND verdict semantics. 시니어 16B 권고 #2.
- `_infer_verdict` 에 `per_cond_matched` tracking + `cond_match_suffix` (N/M 매칭 라벨) 모든 verdict 분기에 attach
- partial multi-cond + fixture_compat=ok 시 likely_yes → yes 자동 승격 **보류** (`is_partial_multi_cond` regex guard)
- 7 tests + simulation **290 PASS** regression 0
- 최QA 2회 사이클:
  - 1차 (3/10): N/M suffix 가 6/7 분기 dead code + fixture-compat boost 가 약화 효과 무력화
  - Fix: 분기 외 한번에 suffix attach + partial 시 boost 가드
  - 2차 production: partial → likely_yes / single → yes 정확

### Phase 16 누적 (A→O)

| Phase | 변경 | 효과 |
|---|---|---|
| 16A | `_check_fixture_compat` 한·영 alias 확장 | 시니어 S1 ("주문 수량 0") yes |
| 16B | `_infer_verdict` body match alias | 시니어 S2 ("두께 0.1mm") yes |
| 16C | `_compute_integrity_warnings` W1/W1b/W2/W3 | 4-필드 모순 surface |
| 16D | W1c + W4 확장 | alias_gap root cause + Test 의심 발화 |
| 16E | UI integrity_warning 칩 (frontend) | 코드 안 읽고 신뢰도 인지 |
| 16F | multi-cond AND semantic + N/M reasoning | partial 보호 + 사용자 인식 surface |
| 16G | alias source 확장 (Action + CodeField @Column) | Java field ↔ DB column 양방향 bridge |
| 16H | Action.aliases_json Korean 시드 (6 actions, +10 aliases) | 16G effective-dead Action source 활성화 |
| 16I | UX polish (confidence dim + 노랑 그룹화) | 16E 신호등 가독성 정돈 |
| 16J | target_is_test retry CTA (1-click 새 세션) | 빨강 칩 진단→해결 동선 회수 |
| 16K | ranking boost rationale 칩 (declared_on_term/role/annotations) | "왜 #1 인지" 투명성 |
| 16L | integrity_warning 발화율 dashboard metric | 시드 품질 회귀 지표 |
| 16M | 0-cand suggestion 품질 (Korean stopword + 토큰 제외) | "내가 모르는 단어 추천" 원칙 |
| 16N | margin action 시드 (skipped) | codebase Java 코드 부재로 시드 대상 없음 |
| 16O | 0-cand query 매핑 갭 dashboard metric | modeling team 시드 보강 자동 가이드 |
| 16P | 공통 WARNING_META util 추출 | 신호등 단일 source — 향후 kind 추가 1곳 수정 |
| 16Q | 추가 production action declared_on_term 시드 (4건) | 79→75 None, 시드 커버리지 ↑ |
| 16R | backend IntegrityWarningKind canonical + cross-lang sync test | warning kind drift 자동 차단 |
| 16S | VERDICT_META util 추출 | 16P 패턴 적용 |
| 16T | ranking_weights 모듈화 (pure refactor) | 미래 튜닝/실험 인프라 |

### 다음 단계 후보 (사용자 결정 대기)

- A. **실 fixture invoke** (multi-day, 정석) — fixture 실행 인프라
- B. **margin action 시드** — modeling team 이 Java 코드 추가 후
- C. **0-cand query trend** — 16O 일별/주별 변화 chart (데이터 누적 후)
- D. **ranking weight profile** (16T 후속) — env var override / repo-specific
- E. **VERDICT_META Korean alias** (16S 후속) — i18n 토대

### 이전 작업 — Phase 15 modeling 시드 (참고)

Phase 15 (A/B/C) modeling 시드 패치 완료. 7 BusinessTerms 추가 + 25+ actions declared_on_term 정정. 시니어 14E 예측 production 검증.

---

## 🟡 이전 latest (Phase 15 완료, archived)



**브랜치**: `section3/chat-agent-redesign`

### 가장 최근 작업 (Phase 15, 2026-05-18)

페르소나 14E 시니어 예측 ("1행+1컬럼만 채우면 14E 자동 발현") 검증 → batch seed 확장:

**15A** — `scripts/seed_phase15a_thickness_alias.py` (멱등). BusinessTerm `term.scm.thickness` (label="두께", 5 aliases) + `action.scm.thickness_실행.declared_on_term` 정정. 시니어 검증: SdThicknessAction.execute #1 score 47 (이전 23/wrong target). **YES**.

**15B** — `scripts/seed_phase15b_dimension_terms.py`. 5 dimension terms (length/width/weight/slab_count/split) + 14 actions 정정. PM 검증: 4/5 시나리오 silent wrong target 완전 소멸. **9/10**.

**15C** — `scripts/seed_phase15c_domain_terms.py`. margin term 신규 + 12 도메인 패턴으로 90 None actions 중 11 정정 (edging/productivity/customer/algorithm/trace/history/...). PM 검증: cumulativeProductivity / 엣징 / history 즉시 매칭. **4.4/5**.

**Schema 일관성**:
- BusinessTermRow.kind 는 `atomic` / `composite` 만 valid (`concept` 불가)
- BusinessTermRow.source 는 `manual` / `auto` / `llm` / `user` 만 valid
- 사용자 patch 로 3 scripts kind/source 정정됨

**누적 검증**: simulation **257 PASS** regression 0.

**Backups**: `data/ontology.db.bak-pre-phase15{a,b,c}-*`

### 다음 단계 후보 (Phase 16+, 사용자 결정 대기)

페르소나 15C 권고:
- A. **Korean↔English var-alias 보강** `_check_fixture_compat` (Phase 14B 시니어 발견)
- B. **실 fixture invoke** (multi-day, 정석)
- C. **suggestion chip quality** (14C R1)
- D. **사용자 query 로그 기반 매핑 갭 자동 탐지** (15C PM 신축 권장)
- E. **margin action 데이터 시드** (modeling 측 — actions 추가 필요)
- F. **score 가중치 declared_on_term explicit surface** (UI/UX)

### 이전 작업 — Phase 14 (참고)

Phase 14 (A/B/C/D/E/F) 완료. 6 항목 페르소나 사이클로 silent wrong target 위험 + verdict false positive 해결.

---

## 🟡 이전 latest (Phase 14 완료, archived)



**브랜치**: `section3/chat-agent-redesign`

### 가장 최근 작업 (Phase 14, 2026-05-18)

페르소나 검증 결과로 도출된 Phase 14 6 항목 모두 완료. 매 항목 TDD + 페르소나 검증:

**14A — confirm guard for 0-cand** (5 tests). 0-cand 일 때 confirm 즉시 422 + suggestion hint.
**14E — 한·영 alias gap** (9 tests). `_expand_search_terms` (strict token) + `_fetch_related_term_fqns` + `_apply_ranking_boost(term_fqns_in_query)` (+10 boost). ValidationResult noise 제거.
**14C — suggestions chip 1-click + hypothesis/lookup card render**. frontend `onSuggestionClick`/`GateExecutedReadOnlyCard` 신규. 이전 frontend 가 silently null 렌더하던 executed_lookup/executed_hypothesis 카드 렌더 추가.
**14D — body × conditions 매칭 정밀화** (8 tests). var multi-token AND + value word-boundary + co-occurrence +2 + expression regex +3. var-miss false positive 강등.
**14B MVP — fixture compatibility check** (8 tests). `_check_fixture_compat` (var ↔ param name + type 호환) + `_fetch_method_params`. compat=True → likely_yes→yes, type incompat → 약화, var miss → 경고만.
**14F MVP — anchor_bindings 활용** (5 tests). `_fetch_anchor_bindings` + verdict signal 보강. 163 행 fragment-level mapping surface.

**누적**: tests `test_multiturn_phase13b/c, 14a/b/c/d/e/f` 합 **57+ tests** + simulation suite **257 PASS** regression 0. TS clean.

페르소나 검증 (Phase 14 사이클):
- 14A: smoke test (production)
- 14E: 시니어 Conditional Yes — ValidationResult noise 제거 확인
- 14C: 김PM 8.0/10 — hypothesis/lookup card 회귀 fix + suggestion 1-click
- 14D: QA + PM 통합 — 13c false positive 해결
- 14B: 시니어 Conditional Yes — S1 회귀 발견 후 즉시 fix (var miss 는 verdict 영향 X)
- 14F: 실 backend 검증 — anchor 4 행 surface + confidence 0.75 → 0.85

### 다음 단계 후보 (Phase 15+, 사용자 결정 대기)

페르소나 14 검증에서 surfaced 잔여:

A. **modeling 시드 데이터 패치** — "두께" 등 한·영 alias 채우기 (코드 변경 0, 14E 가 자동 발현)
B. **Korean↔English var-alias 보강** `_check_fixture_compat` (14B 시니어 회귀 후속)
C. **실 fixture invoke** (multi-day, 정석 14B 완성)
D. **suggestion chip quality** — 14C R1 (chip 이 후보 produce 못하면 surface 안 함)

### 이전 작업 — Phase 13b/c (참고)

**Phase 13b — search keyword extraction + 0-cand fallback** (13 tests)
**Phase 13c — hypothesis intent + conditions + executed_hypothesis** (13 tests)

페르소나 13c 검증 — QA 4.0/5 (+1.5 from 13b), 시니어 silent wrong target 위험 ELIMINATED (verdict=unknown + confidence=0.20 honest surface)

---

## 🟡 이전 latest (Phase 13b + 13c 완료, archived)

**브랜치**: `section3/chat-agent-redesign`

### 가장 최근 작업 (Phase 13b + 13c, 2026-05-18)

**Phase 13b — search keyword extraction + 0-cand fallback**
- `intent.py` — `IntentDecision.search_terms: list[str]` 신설 + LLM prompt 가이드 (의도/조사 제외, 도메인 명사 + 영문 식별자만)
- `schemas.py` — `GateTarget.suggestions: list[str]` 신설
- `gate_i.py` — search_terms 가 있으면 그것을 ontology/sim_v2 검색 query 로 (없으면 user_query). 0-cand 시 `business_terms.aliases_json` substring 매칭으로 suggestions surface
- tests `test_multiturn_phase13b_search.py` **13 PASS**

**Phase 13c — hypothesis intent + conditions + executed_hypothesis**
- `intent.py` — `_VALID_INTENTS` 6종 (hypothesis 추가) + `IntentDecision.conditions: list[{var,op,value,unit}]` + LLM prompt 한국어 비교 연산자 매핑 ("미만"→"<" 등)
- `schemas.py` — `HypothesisVerdict` Literal (5종) + `GateExecutedHypothesis` payload (target/conditions/body/verdict/reasoning/evidence/confidence/sources)
- `gate_hypothesis.py` 신규 — `build_gate_hypothesis` 가 body + business_rules evidence 병렬 fetch 후 `_infer_verdict` heuristic (body 안 var/value/op 시그널 + rule.statement 매칭 시그널)
- `multiturn_router.py` — turn 3 hypothesis → build_gate_hypothesis + `_next_gate_kind` 갱신
- tests `test_multiturn_phase13c_hypothesis.py` **13 PASS**

**전체 simulation suite 222 PASS** (regression 0).

**페르소나 검증** (실 backend + 실 OpenAI):
- 13b — 김PM Yes / 박주니어 Yes (search_terms 정확) / 시니어가 silent wrong target 위험 발견 → Phase 13c 가 해결 / QA 2.5/5
- 13c — QA 4.0/5 (+1.5) / 김PM 3.5/5 / 시니어 Conditional Yes ("silent wrong target 위험 ELIMINATED" — verdict=unknown + confidence=0.20 으로 honest surface)

### 다음 단계 후보 (Phase 14, 사용자 결정 대기)

페르소나 13c 검증에서 발견된 Phase 14 후보:

A. **confirm guard for 0-cand** (state machine bug, 5분 fix) — candidates=0 시 confirm 통과 → turn 3 4xx
B. **실제 fixture invoke 로 verdict 승격** — heuristic → real fixture run (Phase 13c 의 verdict 신뢰도 강화)
C. **suggestions chip → 1-click auto-research** (frontend UX, 모든 페르소나 공통 요청)
D. **body × conditions 매칭 강화** — body_signals=0 인데 rule_signals 만으로 likely_yes 인 케이스 보정
E. **한·영 alias gap** — 한국어 도메인 term ↔ 영문 식별자 bridge (Phase 13b 부터 unresolved)
F. **anchor_bindings activation** — 163 행 fragment-level mapping 을 fixture synth 에 inject

### 이전 작업 — Phase E-C 완료 (참고)

- 130/130 sim_verified — Option C parser root fix + translator 5 patches + re-import + reapply
- 커밋 `9a6a6a8`, `f449355`. 백업 `data/ontology.db.bak-pre-reimport-20260518-201243`

---

## 과거 작업 (참고)

### Phase 13a 결과 (locate / explain intent, 2026-05-18)

> 방안 C (점진적 ReAct 도입) 첫 단계 — locate / explain intent 신설 + executed_lookup payload. 매 단계 페르소나 subagent 검증.

- intent.py — `MultiturnIntent` 5종 (simulate / impact / ambiguous + locate / explain) + LLM prompt 가이드
- schemas.py — `BusinessRuleEvidence` + `GateExecutedLookup` (body + file + caller + linked_term + rules 통합)
- gate_executed_lookup.py 신규 — `build_executed_lookup(target, mode)` 병렬 fetch
- ontology_client.py — `SimV2BackedOntologyClient.get_method_meta` (SQLite query 로 file_path/line/return_type; 페르소나 검증서 발견한 buge fix)
- multiturn_router.py — turn 3 분기 + state machine `confirm + locate/explain → executed_lookup`
- tests 14 PASS + simulation 181 PASS regression 0

**페르소나 검증** (실 backend):
- 김PM ★★★★★ "주문 검증 어디서 해?" — body+callers+5 rules surface
- 박주니어 ★★★★ "OrderService.process 어디?" (bug fix 후) — file_path + line=21-40 + return_type
- 시니어 ★★★★ "ProductivityService 정의+caller" — Gate III impact 부분 대체
- QA ★☆ "두께 음수?" — candidates 0, 13c hypothesis 절실

**다음 단계 후보**:
- 13b (search keyword extraction + 0-cand fallback + ranking 강화) — 김PM/박주니어 잔여 마찰
- 13c (hypothesis tool + anchor_bindings + yes/no verdict) — QA 1:1 해결

### Phase 12 Activation 결과 (기존 ontology 데이터 활성화, 2026-05-18)

> 사용자 가설 검증: 모델링 그래프 풍부, agent 가 거의 사용 안 함. 새 기능 0, 재배선 5 항목.

- **Item 1**: `SimV2BackedOntologyClient.get_caller_graph` 가 stub `return []` → SQLite `CodeLayerStore.get_method_callers_with_match` 직접 호출. `_MATCH_STRENGTH` 적용 dedupe. graceful fallback.
- **Item 2**: `_impact_confidence` caller_count=0 시 cap 0.5 (이전: caller 0 + diagnose OK → confidence 1.0 false safety).
- **Item 3**: `ActionCandidate` schema 4 필드 추가 — role / parent_role / annotations / declared_on_term. 모두 optional.
- **Item 4**: `_apply_ranking_boost` 신설 — role/parent_role/annotations + `_CLASS_PATTERN_BOOST` (.action+6 / .wrapper-3 / result-2) + FQN substring +15 / 의미 토큰 +4. `_enrich_with_ontology_metadata` 가 ontology.db 의 CodeMethodRow/CodeTypeRow/ActionRow 한 번에 fetch.
- **Item 5**: `_find_related_business_rules` 신설 — candidate 의 declared_on_term ↔ business_rules.terms_ref_json LIKE 매칭, 상위 5 행 `Provenance(source=ontology)` 로 sources.
- **검증**: tests/simulation/test_multiturn_phase12_activation.py **11 PASS** + simulation suite **169 PASS** regression 0. 실 백엔드 (slab-design-real-v2):
  - "thickness 검증 시뮬" → SdThicknessAction.execute **#1 (이전 #3)** 으로 역전, ValidationResult.pass/.fail #4-5 로 내려감
  - "calc cumulative productivity 영향도" → `affected_methods: [SdDesigner.design (name_only 0.5)]` (이전 빈 배열)
  - candidate 4 신규 필드 채워서 응답 (role=business, parent_role=domain, annotations=[@Component], declared_on_term=term.scm.order.order)
  - sources 에 DG001 / DG002 / DG003 같은 business_rules 자연어 statement 5 행 surface

### Phase 11.6 결과 (Dashboard repo → Chat propagate, 2026-05-18)

- `Section3Section` 가 `selectedRepo` state lift up 보유. URL `?repo=` query param 추가 + popstate 호환
- DashboardPanel 는 controlled props (`selectedRepo` / `onRepoChange`). 첫 fetch 시 부모가 비어 있으면 첫 repo 자동 보고
- MultiturnChat 는 `defaultRepoId` prop 받아 EmptyState `repo_id` input 초기화. active session 없을 때만 부모 변경에 따라감 (load 된 session 의 repo 는 보존)
- tsc clean. 단, **현재 1 repo 만 적재** 라 시각적 "전환" 데모는 안 됨 — 필요시 옵션 (C) 두 번째 테스트 repo 시드 별도 작업.

### Phase 11.5 결과 (Dashboard 정리 + repo 인식, 2026-05-18)

> 사용자 지시: 대시보드 쓸모없는거 제거 + 필요한건 제대로 뜨는지 확인 + repo 별 동작 확인. 분석 결과 절반이 깨진 / 모순된 상태 (Neo4j 0, legacy 진입점) → 전면 재작성.

- **제거**: ontology 노드 5 카드 (모두 0) / relations 16 칩 (대부분 0) / "빠른 진입" 4 카드 (legacy hidden views 진입점) / dev-only amber tip
- **Backend**: `GET /api/section3/repos` — SQLite ontology.db 의 repo 별 8-카운트 (actions / code_methods / code_types / business_terms / business_rules / realizations / call_sites / sessions). repo 알파벳 정렬.
- **Frontend**: DashboardPanel 전면 재작성 — Repo 선택자 칩 (자동 첫 repo 선택, 미니 요약) + 8 카운트 카드 (실 데이터 + 천단위 포맷) + 최근 세션 (repo 필터 자동 wire)
- **검증**: tests/simulation/test_section3_repos.py **6 PASS** + 기존 multiturn 59 PASS regression 0 + tsc clean + 실 데이터 sanity (slab-design-real-v2 × 130/1081/150/76/17/135/2298/66)

### Phase 11 결과 (Session History Browser / Option B, 2026-05-18)

> 대시보드 가치 분석 (`toClaude/simulation/dashboard_value_analysis.html` 5 옵션 인터랙티브) → 사용자 결정 "최소 (권장)" 프리셋 = A + B → 매몰돼 있던 `/session/{sid}/replay` 자산 surface + 3 인 팀 운영 페인 해결.

- **Backend**: `persistence.list_recent_sessions(limit, repo_id, search)` + `SessionSummary` + `GET /api/section3/multiturn/sessions` (limit 1-200 clamp, repo/search filter)
- **Frontend**: `listSessions()` + `useMultiturnSession.loadSession(sid)` + `MultiturnChat initialSid/onNewSession` + `Section3Section ?sid=` URL routing (pushState + popstate) + `DashboardPanel RecentSessionsSection` (debounced search + SessionRow 카드)
- **tests** tests/simulation/test_multiturn_session_list.py **14 PASS** + multiturn 영역 59 PASS regression 0 + `npx tsc --noEmit` clean + 실 백엔드 (`localhost:8001`) curl 검증 (16+ 세션 surface, Korean search, repo filter)
- **보류 (옵션 C/D/E)** — verification metric / proposal pipeline / cost monitoring 은 backend persistence (verification_result / proposal_audit_log / llm_call_log 테이블) 깔린 후 재평가

### Phase 2 (Backend) ✓ — Gate I/II/III(sim+impact) production wired. 122 tests
### Phase 3 (Frontend) ✓ — MultiturnChat + 5 컴포넌트. UI 진입점 `/?view=multiturn`
### Phase 4 ✓ — HybridOntologyClient (sec2 HTTP + sim_v2 fallback) + state machine 명시화
### Phase 4d ✓ — 양 섹션 협업 wire (sec2 3 endpoint 추가 + sec3 hybrid 본체 wire)

### Phase 7~10 결과 (finalization, 2026-05-18)

- **Phase 7 — bridge_agent v1 deprecate**: 4종 RFC 7234 deprecation header (`X-Deprecated`, `Warning: 299`, `X-Deprecation-Date`, `X-Replacement`) + Frontend amber banner + nav 라벨 변경. v1 endpoint backward-compat 유지.
- **Phase 8 — idiom_diffs surface**: W75 idiom rewriter 가 매칭한 50+ Java idiom 을 `_idiom_trace` 로 누적 → `TranslationResult.idiom_rewrites` → `translate_java_to_python` 3-tuple → `GateBundle.idiom_diffs[]` → UI "Idiom diff" tab.
- **Phase 9 — W74 typed-return stubs**: `derive_method_return_defaults` 로 `code_methods.return_type` → simple_name 별 typed default 매핑. stub method 호출 결과가 String/int/BigDecimal/... 타입 형 default 반환 → FAIL_RETURN_TYPE invariant 사례 감소.
- **Phase 10 — caller graph 정확도**: 5단계 match_kind heuristic (receiver_exact / receiver_short / runtime_type / package_proximity / name_only) + strength 0.5~0.95 + min_strength 필터. UI 에 match + 신뢰 컬럼 surface.
- **tests**: focused suite 619 PASS (sim_v2 synthesizer + simulation + ontology_router + W74 + caller_graph). frontend tsc clean.
- 자세히: `log/step_chat_redesign_phase7_to_10_finalization.md`

**Phase 4 결과**:
- `HybridOntologyClient` 신규 (`ontology_client.py`) — sec2 가 노출하는 2 endpoint (search / actions/{fqn}) 만 httpx wire, 나머지 3 endpoint (method_body / entity_schema / caller_graph) 는 `SimV2BackedOntologyClient` delegate
- `get_ontology_client()` env 분기 — `ONTONG_SECTION2_API_URL` 있으면 Hybrid, 없으면 sim_v2-only
- `ConfirmResponse.next_gate_kind` explicit 계산 (spec v2 §2 state machine):
  - target_selected + simulate + confirm → "bundle_prepared"
  - target_selected + impact + confirm → "executed_impact"
  - target_selected + retry → "target_selected"
  - bundle_prepared + confirm → "executed_simulation"
  - bundle_prepared + modify/retry → "bundle_prepared"
  - executed_* → None (session 종료)
- tests/simulation **137 PASS** (+15)
- 자세히: `log/step_chat_redesign_phase4_summary.md`

### Phase 6 결과 (modeling 시드, 2026-05-18)

- `scripts/seed_modeling_from_sim_v2.py` — slab-v2-handoff.db → ontology.db 12 테이블 migration (code_methods 985, call_sites 1290, actions 38, 등)
- `backend/modeling/code_layer/store.py` `get_method_callers` receiver fallback (best-effort) 추가
- sec2 endpoint 가 이제 실 데이터 반환 (38 actions, 985 methods, 1290 call_sites)
- sec3 hybrid round-trip: **Gate II confidence 1.0** (이전 0.85), **Gate III impact affected_methods 1 + ontology conf 1.0**
- tests **157 PASS** (변경 없음)
- 자세히: `log/step_chat_redesign_phase6_seed.md`

### Phase 5 결과 (Polish, 2026-05-18)

- **backend SSE**: `/session/{sid}/stream` short-lived server-push (0.5초 폴, 30초 max lifetime, signature-diff emit, done event 후 close, EventSource 자동 reconnect)
- **frontend SSE subscribe**: `useMultiturnSession` 이 EventSource open on sessionId, snapshot/done/gone listener, mutation refresh 병행
- **next_gate_kind UI**: `state.lastNextGateKind` + `SessionHeader` 가 status != "done" 일 때 `→ {kind}` blue hint
- tests/simulation **138** + tests/api/test_ontology_router **19** = **157 PASS**
- 자세히: `log/step_chat_redesign_phase5_polish.md`

### Phase 4d 결과 (양 섹션 동시 작업, 2026-05-18)

**Section 2 측 신규 3 endpoint** (`backend/modeling/api/ontology_router.py`):
- `GET /api/ontology/code-methods/{fqn:path}/body` — method body + return_type + line range
- `GET /api/ontology/code-methods/{fqn:path}/callers?repo_id=` — 역방향 caller (best-effort: simple_name + receiver type 매칭)
- `GET /api/ontology/entities/{entity_name}/schema?repo_id=` — CodeType.fields → SchemaSummary

지원 변경: `CodeLayerStore.get_method_callers`, `OntologyQueryClient` Protocol+Impl 3 method, `_extract_method_simple_name/_receiver` helpers.

**Section 3 측 HybridOntologyClient 본체 wire**:
3 method (get_method_body, get_entity_schema, get_caller_graph) 가 fallback delegation 만 하던 것 → 실 sec2 endpoint 호출 + try/except graceful + 미응답 시 sim_v2 fallback.

**tests**: tests/simulation **137 PASS** + tests/api/test_ontology_router **19 PASS** (+10 신규) — 합 **156 PASS**

**서버 검증** (`ONTONG_SECTION2_API_URL=http://127.0.0.1:8001` self-loop):
- sec2 endpoint 직접 호출 시 ontology.db ORM 데이터 부재로 404 / 빈 결과 — 코드는 정상, 데이터 갭만
- sec3 hybrid round-trip: sec2 404 → sim_v2 fallback graceful, java 431 chars / 1 fixture / confidence 0.85 surface

자세히: `log/step_chat_redesign_phase4d_collaboration.md`

### 남은 작업 (모두 외부 의존)

- **sim_v2 parser callsite receiver type** — Phase 6 시드의 1290 call_sites row 가 모두 빈 receiver. sim_v2 parser 측에서 receiver type 추출 정확도 개선 시 Phase 10 의 receiver_exact/short/runtime_type 매치가 활성화됨. 현재는 package_proximity / name_only fallback 가 surface.
- **production_db tests** — `tests/sim_v2/.../test_production_*` 등 102개 test 는 slab-design-real 외부 데이터 시드 + alembic 설치 의존. 별도 환경 ticket.

### 완료된 항목 (이전 후보)
- ✓ Phase 5 — SSE 실시간 스트리밍 + `confirm.next_gate_kind` UI surface
- ✓ Phase 6 — modeling ontology.db 시드 (Q5 비전 "확실한 근거" 완성)
- ✓ Phase 7 — 옛 `bridge_agent.py` deprecate (header + UI banner)
- ✓ Phase 8 — `idiom_diffs` surface (W75 trace + 3-tuple + UI tab)
- ✓ Phase 9 — W74 typed-return stubs (Gate III sim ERROR 감소)
- ✓ Phase 10 — caller graph 정확도 (5단계 match_kind heuristic)

**브라우저 진입점**: `http://localhost:3000/?view=multiturn`

세부: `CHAT_REDESIGN_SPEC.md` v2 §10 / §13 Q5 비전 / §9 협업 요청

---

## 현재 상태 (2026-05-17) — Chat 멀티턴 재설계 진입

**브랜치 신설**: `section3/chat-agent-redesign` (origin/main 기준, local-only)

**Phase 0 완료** (commit `9cb354e`):
- 4 인계 문서 정독 (HTML report / MD report / bridge_agent.py / authoring/)
- `toClaude/simulation/CHAT_REDESIGN_SPEC.md` 작성 (291 LOC)
  - 6 게이트 정의 + state machine + tool catalog
  - DecisionKind 영속화 schema (`section3_decision_log`)
  - Frontend 컴포넌트 map + endpoint surface
  - 협업 요청 3 항목 + mock 전략
  - Phase 0~4 rollout plan

**4 default decision** (사용자 미확인):
1. 협업 요청 → mock 으로 우선
2. 옛 `bridge_agent.py` 보존 + 새 `multiturn/` 패키지 병행
3. P0 quick win 스킵, 멀티턴 바로 진입
4. spec 산출물 = markdown (HTML 아님)

---

## 현재 상태 (2026-05-16) — Sprint 1~5 완료

**브랜치 (history)**: `section3-integration` — origin/main 머지 완료 (PR #4, commit `b8a5498`)

**최근 완료 (Section 4 인계 Sprint 1~5, 2026-05-16)**:

| Sprint | 작업 | 상태 |
|---|---|---|
| 1 | recipe-4 full pipeline (W71→W75→W74→W72) | ✅ 12/12 cumulativeProductivity PASS |
| 2 | recipe-2 Java baseline + sandbox 표 expected 컬럼 | ✅ file-based load_baseline_map + BehaviorTwinRunner 경로 |
| 3 | recipe-3 invariant 진단 → chat fallback surface | ✅ quick_diagnose_action + simv2_suggestions 이벤트 |
| 4 | recipe-5 W77+W78 한국어 검색 → bridge | ✅ find_action_candidates (term + LIKE) |
| 5 (opt) | transpiler 옵션 B (sim_v2 subclass) | ✅ Section3Translator 동적 subclass |

- 신설 파일: `backend/section3/sim_v2_bridge.py` (16 public 심볼) · `backend/section3/section3_translator.py` · `tests/simulation/test_sim_v2_bridge.py` (13 test) · `data/baselines/README.md`
- 수정 파일: `backend/section3/agents/{sandbox,bridge}_agent.py` · `frontend/src/components/section3/EventStreamView.tsx`
- 데모 6종 sanity check 완료 (UC36/37/38/40/41/42 + bonus recipe-5)
- 백엔드 재기동 후 /health 200, 프론트 3000 동작

**이전 완료 (2026-05-10)**:
- main 머지 / sample-repos main 100% 정렬 / 인계 검증 9/9
- STEP 3a-f 종결 (ChangeSpec/SimResult/Runner/Orchestrator/RunHandle/spec_router/ontology evidence)
- 백엔드 simulation 패키지 (sandbox / agents / transpile / jvm_bridge) + 프론트 27 패널 + 9 lib API

## 다음 세션 후속 후보 (Phase 1 외)

위 § "🔴 다음 세션 첫 작업" 의 Phase 1 진입이 primary. 그 외 backlog:

1. **W74 typed-return stub** — `BehaviorTwinRunner` 의 FAIL_RETURN_TYPE 케이스 (UC40 의 5건 中 3건) close. sim_v2 측 작업이라 협업 필요.
2. **impact_analysis [LOW] fallback** — bridge_agent 의 `impact_analysis` 분기도 `_emit_simv2_suggestions` surface (멀티턴 재설계 시 자연스럽게 흡수)
3. **legacy transpiler.py 정리** — ontology.db 비어 있어 미사용. 안전 제거 + composer 경로 deprecate (Phase 4)
4. **`data/ontology.db` 시드 작업** — modeling 측에 v2 데이터 import 요청 (협업 요청)
5. **frontend SandboxPanel** — chat 이외 sandbox 직접 진입점에서 sim_v2 후보 검색 surface

데이터 사실:
- `data/ontology.db` (316KB) — 비어 있음 (0 actions)
- `data/slab-v2-handoff.db` (3.4MB) — slab-design-real-v2 38 actions · 유일한 실측 데이터 소스
- legacy `/api/ontology/*` HTTP 는 빈 DB 를 가리키므로 sim_v2 직통이 사실상 primary 경로

## 환경 설정 메모

- 백엔드 실행: `venv/` (`.venv/`가 아님). uvicorn `backend.main:app --host 0.0.0.0 --port 8001`
- 프론트엔드: port 3000, Next.js rewrite `/api/*` → `http://localhost:8001/api/*`
- slab-design (Java legacy 데모): port 8080, `--spring.profiles.active=h2` (단, **`sample-repos/slab-design/` 폴더 제거됨** — 통합 작업 시 `slab-design-real_v2/` 와 매핑 결정 필요)
- ontology 데이터: `data/ontology.db` (read-only ground truth, 80MB SQLite, 9/9 검증 통과)
- 시뮬 결과 저장: `backend/simulation/data/storage.db` 또는 신설 (modeling DB 와 분리)

## Section 2 통합 인터페이스

| 통합 지점 | 사용할 API |
|---|---|
| ontology Core query | `from backend.modeling.api.ontology_query import OntologyQueryClientImpl` (Python facade, DTO 만) |
| 또는 HTTP | `GET http://localhost:8001/api/ontology/{terms,actions,business-rules,anchor-bindings,...}` |
| 금지 (CI 차단) | `backend.modeling.{mapping_layer,domain_layer,code_layer,persistence}.*` — `tools/check_agent_isolation.py` 가 검사 |

## 환경 의존성 (main 통합 시 추가 설치된 것)

```
sqlalchemy, alembic, anthropic, sqlglot, hypothesis, fakeredis, pytest-postgresql, locust,
pydantic-ai-slim[anthropic]
+ frontend: elkjs, @xyflow/react
```
