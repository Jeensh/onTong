# Section 3 — Simulation CHANGES

Ad-hoc change log. `[x]` = done, `[ ]` = deferred/pending.

## 2026-05-19 (Phase 21b — Intent confirmation step) — agent behavior change

> 사용자 vision: "의도 분류 후 '맞아?' 묻고 → confirm 후 candidates 진행". candidates 보기 전 intent 잘못 분류된 걸 사용자가 catch.
> Phase 21a (EmptyState 재설계) 와 함께 진행한 두번째 substantive change — 이번엔 진짜로 agent 흐름이 바뀜.

### 백엔드
- [x] `backend/section3/agents/multiturn/schemas.py` — `GateIntentClassified` 추가 (kind=intent_classified, intent + search_terms + conditions + sources). GatePayload union 에 합류.
- [x] `backend/section3/agents/multiturn/gate_i.py` — `build_intent_classified()` 신설 (intent 분류만, candidates 미수행). `build_gate_i` 에 `preclassified` 파라미터 추가 — 이미 confirmed 인 intent 면 재분류 skip.
- [x] `backend/section3/api/multiturn_router.py` — `INTENT_CONFIRM_REQUIRED` 모듈 플래그 (production True / 기존 tests False). content-driven dispatch 4 case 로 refactor:
  - A: stub turn (turn 1, no user_resp) → `INTENT_CONFIRM_REQUIRED=True` 면 intent_classified, 아니면 legacy target_selected
  - B: intent_classified + confirmed → target_selected (Gate I real, preclassified 전달)
  - C: target_selected + confirmed → Gate II/III dispatch
  - D: bundle_prepared + confirmed → executed_simulation
  - `_next_gate_kind` 에 intent_classified case 추가 (confirm → target_selected, retry → intent_classified).
- [x] `tests/simulation/conftest.py` (신규) — autouse fixture 로 기존 348 테스트는 `INTENT_CONFIRM_REQUIRED=False` (legacy 1-step flow 유지). 새 테스트는 production 흐름 검증.
- [x] `tests/simulation/test_multiturn_phase21b_intent_confirm.py` (신규, 7 tests) — production 흐름 (stub → intent_classified → target_selected → bundle_prepared) E2E 검증.

### 프론트엔드
- [x] `frontend/src/lib/section3/multiturn.ts` — `GateIntentClassified` 타입 추가, GatePayload union 에 합류.
- [x] `frontend/src/components/section3/multiturn/IntentStage.tsx` — `payload: GateTarget | GateIntentClassified` 받게 확장 + `onConfirm` / `confirmDisabled` / `pending` props. `isAwaitingConfirm` 상태에서 [✓ 맞아 → 후보 찾기] + [↻ 다른 의도로] 버튼 + ambiguous 시 confirm disable.
- [x] `frontend/src/components/section3/multiturn/MultiturnChat.tsx` — `onConfirmIntent(turn_no)` 콜백 신설 (confirm + respond). `WorkflowFrame` 이 intentClassified 와 gateIReal 둘 다 별도로 surface. `computeCurrentStage` 가 intent_classified turn 도 Stage 1 으로 카운트.

### 결과
- tests/simulation **348 PASS** (기존 341 + 새 7), regression 0.
- TS clean (tsc --noEmit exit 0).
- Backend 코드 라인: +85 (schemas +15, gate_i +20, router +20, conftest +20, tests +210).
- Frontend 코드 라인: +50 (multiturn.ts +12, IntentStage +30, MultiturnChat +10).
- 사용자 feedback "multi턴 에이전트 그대로인데" 해결 — 이번엔 진짜로 agent 가 pause 함.

## 2026-05-18 (Phase E-C — Parser root fix + translator rework) — cross-section

> Goal: 6 stuck actions 까지 sim_verified 로 + re-import safety net + parser 단계 자동 분류. Option C 채택.
> 상세 단계별 분해 + 카운트 변화는 `log/step_ec_parser_translator_rework.md` 참조.

### 추가/수정
- [x] `scripts/export_modeling_enrichment.py` (신규, 100 LOC) — 7개 enrichment 테이블 → JSON natural-key export
- [x] `scripts/reapply_modeling_enrichment.py` (신규, 250 LOC) — natural-key UPSERT (caller+callee+line, action_fqn+code_method_fqn+applies_to_code_type_fqn, ...)
- [x] `backend/modeling/code_analysis/method_symbol_table.py` (신규, 190 LOC) — params + locals + for-each + try-with-resources + catch + Java 16 instanceof pattern var + class field 추적
- [x] `backend/modeling/code_analysis/java_parser.py` — `_extract_calls` 가 receiver_type + receiver_kind + receiver_text 를 `attributes` 에 additive 부착 (target shape 보존 — call_resolver backward-compat)
- [x] `backend/sim_v2/core/synthesizer/java_translator.py` 5 patches:
  - try-with-resources statement → `_STATEMENT_TYPES`
  - `instanceof T t` → walrus `(isinstance(x, T) and (t := x))` + strip generics
  - `List/Set/Map.copyOf(x)` → `list/set/dict(x)`
  - LHS shadowing 방지 (`X x = x(...)` → `_x = x(...)` + `_local_alias` map)
  - resource skip-set `scoped_type_identifier` 추가
- [x] data: re-import slab-design-real-v2 + reapply snapshot + 6 actions SQL 승격 → **130/130 sim_verified**

### 결과
- call_sites: 2,298 (needs_user_confirm 51 — 외부 JDK 호출 한정)
- new parser native 분류 (re-import 직후 reapply 전): single_impl 1,183 + annotation 252 = **1,435 high-conf (≥0.85)** — 수동 cleanup 524 unique-owner 대비 2.7배
- actions: **130/130 sim_verified (100%)**
- 회귀 0 (synthesizer 399 + parser 47 + code_layer 64 + spring analyzer 60+ all PASS)

### 커밋
- `9a6a6a8` feat(modeling): enrichment export/re-apply safety net
- `f449355` fix(modeling+sim_v2): receiver-type symbol table + 5 translator gaps

### 백업
- `data/ontology.db.bak-pre-reimport-20260518-201243` (5.4MB, 재import 직전)
- `data/enrichment_snapshot_slab_design_real_v2_20260518_111338.json` (1.8MB)

### 보류 (사용자 결정 필요)
- hybrid reapply: native parser 분류 (1,435 high-conf) vs manual cleanup labels 통합 — 현재 manual 우선 적용
- Gap 4 (constructor + static_class) analyzer route 변경
- Gap 5 (chain return-type) post-pass

---

## 2026-05-19 (Phase 20 — SessionHeader stage progress + 17~19 통합)

> 17~19 의 3-stage frame 을 SessionHeader 의 progress dots 로 시각화. 사용자가 페이지 어디 있든 "지금 stage 어디인지" 1 초 안에 인지.

### 신설
- [x] `SessionHeader` 에 `currentStage: number` prop + `StageProgress` 컴포넌트:
  - 3개 dot (1/2/3) — 현재 stage = primary ring, 통과 = emerald, 미진행 = border 회색
  - 1 = Gate I real 진행, 2 = candidate confirm 후, 3 = bundle/executed 도달
- [x] `computeCurrentStage(decisions)` — decision log → stage 번호 (0-3)

### 검증
- [x] TS clean
- [x] backend 341 PASS 유지

### 17~20 통합 효과
- 사용자는 페이지 어디 있어도 progress dots 로 stage 인지
- Stage 1/2/3 각각 explicit (IntentStage 히어로 / ScopeStage 영향영역 / SimulateStageHeader 요약)
- 빈 대화 → 3-stage frame 자동 등장 → "지금 무엇을 하는 중" 명확

---

## 2026-05-19 (Phase 19 — Stage 3 SimulateStageHeader)

> 사용자 vision Stage 3 = "영역 + 데이터 + 실행 + 결과". MVP 는 thin summary header (1줄 4 섹션) 로 기존 GateBundleCard / GateExecuted* 카드 위에 surface — 사용자가 "지금 무엇이 simulate 중이고 어디까지 진행됐는지" 한눈에. 후속 (Phase 19b) 에서 영역 zoom + fixture 3-source 토글.

### 신설
- [x] `frontend/src/components/section3/multiturn/SimulateStageHeader.tsx`:
  - **영역**: primary code_method_fqn (단축 표시, 1 method 명시)
  - **Fixtures**: count + source ("auto W71" / "—")
  - **상태**: pending → ready → done 3 단계 + icon
  - **결과 요약** (executed 시):
    - simulation: `N/M PASS · invariant=clean`
    - impact: `N affected methods · M findings`
    - hypothesis: `verdict=yes (75%)`
    - lookup: `mode=locate/explain`
  - resultOk → 초록 / 빨강 색상 코딩
- [x] `MultiturnChat` Stage 3 frame 최상단에 SimulateStageHeader 삽입

### 검증
- [x] TS clean
- [x] backend 341 PASS 유지 (frontend-only)

### MVP 한계 (Phase 19b 후속)
- 영역 선택 = primary 만 (scope subset zoom 안 됨)
- Fixture source 토글 미구현 (auto/load/manual 3-way)
- 결과 비교 view (Java baseline vs Python twin) 는 기존 GateExecutedSimulationCard 안

---

## 2026-05-19 (Phase 18 — Stage 2 Scope endpoint + ScopeStage panel)

> 사용자 vision Stage 2 (영향 영역). 단일 method 가 아닌 **모든 관련 entity** 집계: primary action + caller graph + sibling actions (same declared_on_term) + related business_rules + term. MVP = list view + 자동 Test/Mock 제외 (16D W4 동기화).

### 백엔드
- [x] `backend/section3/agents/multiturn/scope.py` — `build_scope(action_fqn, code_method_fqn, declared_on_term, repo_id, ontology_client)` 병렬 aggregator:
  - `get_caller_graph` (existing) — caller chain
  - `_get_sibling_actions` (신설) — same declared_on_term 의 다른 actions
  - `_find_related_business_rules` (existing) — term 기반 rules
  - `_get_term_detail` (신설) — BusinessTerm row
  - Test/Mock 패턴 → `in_scope_default=False` (16D `_is_test_or_mock` 동기화)
- [x] `POST /api/section3/multiturn/scope` endpoint
- [x] `ScopeEntityView` / `ScopeRequest` / `ScopeResponse` Pydantic

### 프론트엔드
- [x] `frontend/src/lib/section3/multiturn.ts` — `ScopeResponse` / `ScopeEntityView` type + `getScope()` API client
- [x] `frontend/src/components/section3/multiturn/ScopeStage.tsx` — 새 컴포넌트:
  - kind 별 그룹화 (action / caller / term / rule) + 4 색상 신호등 (purple/sky/pink/amber)
  - kind 별 expand/collapse
  - Test 의심 entry opacity-50 + 제외 카운트 surface
  - 각 entity: checkbox (현재 readonly, Phase 18b 에서 simulate scope 반영)
  - primary / Test 칩 / severity 메타 표시
- [x] `MultiturnChat WorkflowFrame` 의 Stage 2 안에 `ScopeStage` 통합 — turn 2 candidate confirm 후 자동 fetch

### tests
- [x] `tests/simulation/test_multiturn_phase18_scope.py` **6 PASS** (primary+callers / Test caller 자동 제외 / term+sibling / business rules / endpoint 2 종)
- [x] simulation suite **341 PASS** regression 0 (이전 335 + 18 6)
- [x] TS clean

### MVP 한계 (Phase 18b 후속)
- checkbox 현재 readonly — 실제 simulate scope 반영은 후속
- graph view 미구현 — list 만 (graph 는 Phase 18b)

---

## 2026-05-19 (Phase 17 — 3-Stage workflow frame + IntentStage hero)

> 사용자 vision: (1) 의도 파악 → (2) 영향 영역 → (3) 시뮬레이션. agent-centric gate timeline 을 user-centric 3 stage 시각 frame 으로 wrap. backend 변경 0, UX 재구조화.

### 신설
- [x] `frontend/src/components/section3/multiturn/IntentStage.tsx` — Stage 1 hero panel:
  - intent type 6 종 (simulate/impact/ambiguous/locate/explain/hypothesis) + description
  - 원본 user_query
  - hypothesis conditions (var/op/value/unit) chip
  - provenance line
  - 2 상태: active (full hero) / collapsed (1줄 summary header)
  - edit callback (현재는 새 대화로 다시 시작 — 16J 패턴)

### 통합
- [x] `MultiturnChat` body 재구조화 — `WorkflowFrame` 새 컴포넌트:
  - Stage 1: IntentStage (turn 2 Gate I real payload)
  - Stage 2: 영향 영역 (현재는 GateTargetCard wrap; Phase 18 에서 scope graph 확장 예정)
  - Stage 3: 시뮬레이션 (bundle + executed 카드)
  - 각 stage 는 `StageFrame` (header + collapsed/active state)
- [x] `GateTargetCard` 의 hypothesis conditions 중복 제거 (IntentStage 로 이동)

### 검증
- [x] TS clean
- [x] backend 335 PASS 유지 (frontend-only 재구조화)

### 디자인 결정
- Stage 1 inline edit 는 Phase 17b 로 분리 — MVP 는 read-only display + collapse + "새 대화" retry
- 3-stage frame 은 chat timeline 위에 진단적 시각 부여 — turn N 가도 "지금 어디인지" 명확
- 후속 Phase 18 (Stage 2 scope graph) / Phase 19 (Stage 3 workbench) / Phase 20 (통합)

---

## 2026-05-19 (Phase 16T — gate_i ranking boost weights 외부 모듈화)

> 16T = pure refactor (behavior 변동 0). `gate_i.py` 의 module-level boost 상수 8 개를 별도 `ranking_weights.py` 로 모음. 미래 튜닝/실험 (env override, repo profile, A/B) 인프라 토대.

### 추가
- [x] `backend/section3/agents/multiturn/ranking_weights.py`:
  - `ROLE_BOOST` / `PARENT_ROLE_BOOST` (dict)
  - `DOMAIN_ANNOTATIONS` + `DOMAIN_ANNOTATION_BOOST` (이전 hardcoded 2.0 → named 상수)
  - `CLASS_PATTERN_BOOST` (list of tuple)
  - `FQN_EXACT_BOOST` / `NAME_TOKEN_BOOST` / `DECLARED_ON_TERM_BOOST`

### 변경
- [x] `gate_i.py` 에서 위 8 상수 alias import (기존 underscore-prefixed 명 유지로 내부 참조 무변동)
- [x] `_DOMAIN_ANNOTATION_BOOST` 도입 (이전 magic number 2.0)

### 검증
- [x] simulation **335 PASS** regression 0 (behavior 변동 0)
- [x] gate_i 본체는 boost 정책 import 만 — 정책 변경 시 `ranking_weights.py` 한 곳

---

## 2026-05-19 (Phase 16S — VERDICT_META util 추출)

> 16P 패턴 적용. `GateExecutedReadOnlyCard.tsx` 의 로컬 `VERDICT_META` → `lib/section3/verdict_meta.ts` 단일 source. 향후 dashboard 등 verdict 시각화 컴포넌트 재사용 토대.

### 추가
- [x] `frontend/src/lib/section3/verdict_meta.ts`:
  - `VerdictMeta` interface
  - `VERDICT_META: Record<HypothesisVerdict, VerdictMeta>` (5 verdict: yes/likely_yes/likely_no/no/unknown)
  - `getVerdictMeta(verdict)` helper

### 변경
- [x] `GateExecutedReadOnlyCard.tsx`: 로컬 VERDICT_META 제거, `getVerdictMeta()` 호출로 대체. AlertCircle/CheckCircle2/HelpCircle imports 도 util 안으로

### 검증
- [x] TS clean
- [x] backend 335 PASS 유지 (frontend-only)

---

## 2026-05-19 (Phase 16R — backend IntegrityWarningKind canonical + frontend sync test)

> 16P 후속. 백엔드 `_compute_integrity_warnings` 의 hardcoded 문자열 6개 → canonical `integrity_warning_kinds.py` 모듈. cross-language sync 자동 검증 테스트로 drift 차단.

### 추가
- [x] `backend/section3/agents/multiturn/integrity_warning_kinds.py`:
  - `IntegrityWarningKind` Literal type (6 kinds)
  - `INTEGRITY_WARNING_KINDS: frozenset[str]`
  - `emit_warning(kind, detail) -> str` — 통일 포맷 helper

### 변경
- [x] `gate_hypothesis._compute_integrity_warnings` — 6 hardcoded f-string → `emit_warning(kind, detail)` 호출

### tests
- [x] `tests/simulation/test_phase16r_integrity_warning_kinds.py` **5 PASS**:
  - emit_warning 포맷
  - 모든 kind frontend regex parseable
  - gate_hypothesis.py 만 canonical kind 사용 (drift 감지)
  - gate_hypothesis.py raw f-string 0 (16R 회귀 방지)
  - **cross-language sync**: backend `INTEGRITY_WARNING_KINDS` ↔ frontend `WARNING_META` keys 정확 일치
- [x] simulation **335 PASS** regression 0 (이전 330 + 16R 5)

---

## 2026-05-19 (Phase 16Q — 추가 production action declared_on_term 시드)

> 15C 잔여 79 None actions 분석 후 명확한 매핑 4건만 안전 시드. 대다수 None 은 test fixtures (`@Test` 보유) 라 매핑 시 target_is_test 위험 → skip.

### 추가
- [x] `scripts/seed_phase16q_additional_declared_on_term.py` — idempotent, 명확 단일-realization production action 만:
  - `action.scm.find_group` → `term.scm.edging_group` (EdgingService.findGroup)
  - `action.scm.product.lookup_or_default` → `term.scm.product.productivity_std` (ProductivityService)
  - `action.scm.order.extract_designable_orders` → `term.scm.order.order` (SdOrderExtractor)
  - `action.scm.batch_design__driver` → `term.scm.order.order` (SdDriver.batchDesign)
- [x] DB backup: `data/ontology.db.bak-pre-phase16q-20260519-003706`
- [x] 멀티 realization (`find_spec` 5 services) / test fixtures (`dg00*_returns_fail` @Test) / 모호 매핑 (`classify_by_product_code`, `slab.create_initial_slab`) 의도적 skip

### 결과
- Summary: **4 set**, 0 unchanged, 0 not_found
- declared_on_term=None: **79 → 75**
- 2회 실행 idempotent 검증 (SKIP)
- simulation 330 PASS 유지

---

## 2026-05-19 (Phase 16P — 공통 WARNING_META util 추출)

> PM 16I 보고 권고. `WARNING_META` 가 `GateExecutedReadOnlyCard` + `DashboardPanel` 양쪽에 중복 — 향후 warning kind 추가 시 두 곳 sync 부담. 단일 source 로 추출.

### 신설
- [x] `frontend/src/lib/section3/warning_meta.ts` 신설:
  - `WARNING_META` (6 kind: target_is_test / body_unsupported_alias_gap / body_unsupported_no_rule / body_unsupported_rule_only / no_strong_evidence / cross_evidence_mismatch)
  - `UNKNOWN_WARNING_META` (graceful fallback)
  - `RED_KINDS` / `YELLOW_KINDS` / `YELLOW_GROUP_THRESHOLD` (16I 카테고리)
  - `parseIntegrityWarnings(sources)` 함수 (정규식 + dedupe)
  - `getWarningMeta(kind)` lookup helper
  - `IntegrityWarningKind` / `WarningMeta` / `WarningSpec` 타입

### 변경
- [x] `GateExecutedReadOnlyCard.tsx`: 로컬 WARNING_META + parseIntegrityWarnings + RED/YELLOW 상수 제거, util 에서 import
- [x] `DashboardPanel.tsx`: 로컬 WARNING_META_DASH 제거, `getWarningMeta()` 호출로 대체. FlaskConical/Languages import 도 제거 (util 안으로)

### 검증
- [x] TS clean
- [x] backend 330 PASS 유지 (frontend-only refactor)
- [x] 라인 절감: 중복 ~95 라인 → 단일 117 라인 util (타입 + 문서 추가로 품질 향상)

---

## 2026-05-19 (Phase 16O — 0-cand query 매핑 갭 자동 탐지)

> 15C PM 권장 + 16L 후속. Gate I 가 0-candidate 로 끝난 session 의 user_query 들 dashboard 노출 → modeling team 자동 인지. ambiguous stub 제외 (real Gate I 만).

### 백엔드
- [x] `ZeroCandQuery` dataclass + `list_zero_cand_queries(repo_id, limit)` — target_selected payload candidates==[] AND intent!=ambiguous 필터 + per-session 1개
- [x] `GET /api/section3/multiturn/metrics/zero-cand-queries?limit=&repo_id=` endpoint
- [x] `ZeroCandQueryView` / `ZeroCandQueriesResponse` Pydantic

### 프론트엔드
- [x] `ZeroCandQueryView` / `ZeroCandQueriesResponse` TS interface + `getZeroCandQueries` API client
- [x] `DashboardPanel ZeroCandQueriesSection` (repo-scoped, useEffect 로 load)
- [x] 비어있을 때 "✓ 최근 모든 query 가 후보 매칭 — 시드 커버리지 양호" emerald 메시지
- [x] hits 있을 때 list (timestamp + suggestions max 3 + N+)

### tests
- [x] `tests/simulation/test_multiturn_phase16o_zero_cand_queries.py` **10 PASS** (empty / real intent only / candidates 있으면 제외 / ambiguous only 제외 / per-session dedup / repo filter / limit / endpoint 3 종)
- [x] simulation suite **330 PASS** regression 0 (이전 320 + 16O 10)
- [x] TS clean

### Phase 16N — margin action 시드 (skipped)
- 조사: BusinessTerm `term.scm.margin` 만 존재. Java code / business_rules / Actions 모두 margin 키워드 0 hit.
- 결론: codebase 에 margin 로직 미구현 → 시드 대상 없음. modeling team 이 실제 margin Java method 추가 후 재검토.

---

## 2026-05-19 (Phase 16M — suggestion chip quality 보강)

> 14C 의 0-cand suggestions 라이브 진단: (1) 사용자가 친 토큰이 그대로 첫 chip noise, (2) generic Korean 동사 ("검증") 가 토큰일 때 무관 도메인 dominate. 2 fix.

### 추가
- [x] `_KOREAN_QUERY_STOPWORDS` 상수 — generic Korean 동사 (`검증/실행/처리/확인/조회/검사/수행/갱신/시뮬/영향`) + PM defensive 추가 (`이름/체크/보기/계산/생성/추가`)
- [x] `_fetch_suggestions`:
  - 토큰 stopword 필터 (제거 후 토큰 0 이면 graceful empty)
  - 토큰과 lowercase 동일 candidate suggestion 제외 (이미 친 단어 noise 제거)

### 라이브 비교 (실 DB)

| Query | Before | After |
|---|---|---|
| 주문 | `[주문, 통합 주문, Order, SDOrderEntity, 주문 엔티티]` | `[통합 주문, Order, SDOrderEntity, 주문 엔티티, 화학성분]` |
| 주문 검증 | `[검증결과, ValidationResult, ...]` (검증 dominate) | `[통합 주문, Order, SDOrderEntity, ...]` (주문 유지) |
| 두께 | `[두께, thickness, Thickness, thk, slab thickness]` | `[thickness, thk, slab thickness, 두께값]` |
| 검증 (all stopword) | `[검증결과, ...]` | `[]` (graceful empty) |

### tests
- [x] `tests/simulation/test_multiturn_phase16m_suggestion_quality.py` **7 PASS** (query token 제외 / case-insensitive / stopword 필터 / all-stopword graceful / stopword set / no match / non-stopword backward compat)
- [x] simulation suite **320 PASS** regression 0 (이전 313 + 16M 7, 13b 13 PASS 유지)

### 페르소나 검증 (PM)
- **SHIP** — 모든 라이브 케이스에서 noise 감소 + 의미 보존 + honest-empty 동작
- 화학성분 (substring 매칭 leak) 은 acceptable noise — 마지막 슬롯 + exploration 도움
- 추가 stopwords (`이름/체크/보기/계산/생성/추가`) 라이브 hits 0 으로 defensive safe-to-add

---

## 2026-05-19 (Phase 16L — dashboard integrity_warning 발화율 metric)

> PM 16E LOW #4. 운영 지표: 최근 N 세션에서 각 warning kind 가 발화한 session pct. target_is_test ↑ → modeling 시드 갭, alias_gap ↑ → BT alias 미커버 갭.

### 백엔드
- [x] `persistence.compute_warning_rates(repo_id, limit)` — payload_json 의 `integrity_warning=KIND` regex + per-session dedupe + by_kind / by_kind_pct
- [x] `WarningRates` dataclass + `WarningRatesResponse` Pydantic
- [x] `GET /api/section3/multiturn/metrics/warnings?limit=&repo_id=` endpoint (limit 1~200 clamp)

### 프론트엔드
- [x] `WarningRatesResponse` TS interface + `getWarningRates` API client
- [x] `DashboardPanel WarningRatesSection` (repo-scoped, useEffect 로 load)
- [x] 발화 0 시 "✓ 무결성 경고 0건 — 시드 품질 양호" 메시지
- [x] 발화 시 16E 신호등과 동기화된 6 kind 칩 색상 + % surface (sort by % desc)

### tests
- [x] `tests/simulation/test_multiturn_phase16l_warning_rates.py` **9 PASS** (empty / single kind / multi-kind dedup / cross-session pct / repo filter / no-warning session / endpoint 3 종)
- [x] simulation suite **313 PASS** regression 0 (이전 304 + 16L 9)
- [x] TS clean

### 후속 권장
- 일별/주별 trend chart — 누적 데이터 후
- 시드 보강 시 발화율 감소 측정 — 16H 효과 정량화 검증 도구

---

## 2026-05-19 (Phase 16K — declared_on_term score 가중치 explicit surface)

> ranking boost (declared_on_term × query alias = +10 / role business = +6 / .action. = +15 / ...) 가 hidden. 사용자가 "왜 #1 인지" 모름. ActionCandidate 의 ontology 메타 4 필드 surface.

### 추가
- [x] TS `ActionCandidate` 에 `role / parent_role / annotations / declared_on_term` optional 4 필드 추가 (backend 이미 보유)
- [x] `GateTargetCard` 후보 행에 메타 칩 row:
  - declared_on_term (pink-50 + Link2 아이콘) — 강조: 가장 강한 boost 신호
  - role (business=emerald / adapter=sky / helper=gray 색상 매핑)
  - parent_role (domain=indigo / infra=amber / framework=rose) — role 과 다를 때만
  - annotations 최대 3 + `+N more` 카운트
- [x] hover tooltip 으로 boost rationale 설명

### 검증
- [x] TS clean
- [x] backend 304 PASS 유지 (frontend-only)

---

## 2026-05-18 (Phase 16J — target_is_test retry CTA)

> PM 16E HIGH 권고 #1. 빨강 `target_is_test` 칩이 진단만 하고 해결 동선 없는 문제. 1-click 으로 새 세션 시작 (같은 user_query) 하는 CTA 도입 — 사용자가 새 candidates 중 production class 직접 선택.

### 추가
- [x] `GateExecutedReadOnlyCard` 에 `onRetryWithDifferentTarget?: { label, onClick }` prop 추가
- [x] `hasRedWarning && onRetryWithDifferentTarget` 시 칩 row 끝에 `🔄 다른 후보로 다시 시도` CTA 버튼 (primary border + bg-primary/5 + RotateCcw 아이콘)
- [x] `MultiturnChat.onRetryWithDifferentTarget` 핸들러: `state.session.user_query` 추출 → `reset() + start(query, repoId)` 새 세션
- [x] `DecisionCard` 에서 executed_lookup/hypothesis 카드만 CTA 전달 (다른 gate type 무영향)

### 디자인 결정 — 자동 pick 대신 사용자 선택
- 새 세션의 LLM rerank variance 때문에 "rank-2 자동 confirm" 은 후보 불일치 위험
- 새 세션 candidates 보여주고 사용자가 production class 직접 클릭 → 더 안전 + 투명
- 1-click "1 클릭으로 새 세션 + 같은 query" 가 PM 의도 "actionable" 충족

### 검증
- [x] TS clean (`npx tsc --noEmit`)
- [x] backend 304 PASS — 16J frontend-only (backend 무변동)

### 잔여 PM 권고
- LOW #4 W4 발화율 % dashboard (운영 metric)

---

## 2026-05-18 (Phase 16I — GateExecutedReadOnlyCard UX polish)

> PM 16E UX 권고 #2 + #3 묶음 (frontend-only). 빨강 칩 발화 시 confidence 회색·취소선 (신뢰도 visual de-emphasis) + 노랑 N≥3 동시 발화 시 그룹 칩 (시각 정돈, hover 로 세부 보존).

### 추가
- [x] `RED_KINDS = {target_is_test}` / `YELLOW_KINDS` (4종) / `YELLOW_GROUP_THRESHOLD = 3` 상수
- [x] `hasRedWarning` → `VerdictBadge dimmed` prop (`opacity-40 line-through text-gray-500`)
- [x] `yellowGrouped` (≥3) → 단일 그룹 칩 "근거 약한 경고 N건" (title attr 로 원 라벨들 hover 노출)
- [x] non-yellow + (yellow individual OR grouped) 렌더 순서 — 빨강/주황이 먼저

### 검증
- [x] TS clean (`npx tsc --noEmit`)
- [x] backend 회귀 0 — 16I 는 frontend-only (backend 304 PASS 유지)

### 페르소나 검증 (김PM)

| 시나리오 | 평가 |
|---|---|
| S1 빨강+노랑 2 | 직관적 — Test 의심 dominant + confidence 회색 즉시 인지 |
| S2 노랑 3 (그룹화) | 시각 정돈 OK / hover-only 접근성은 모바일 trade-off (TWEAK 후보) |
| S3 빨강+노랑 4 | 빨강+그룹 = 2칩만, 깔끔 |

**PM SHIP** — dim + 그룹화 의도대로 작동, 정보 보존 vs 정돈 trade-off 적절.

### 잔여 PM 권고 (16I 미커버)
- **HIGH — #1 rank-2 jump CTA**: 빨강 칩 클릭 → "다음 후보 보기" 1-click 이동. 빨강 칩의 진단→해결 동선 누락 (가치 50% 미회수). Phase 17 우선.
- **LOW — #4 W4 발화율 % 대시보드**: 운영 metric, 사용자 가치 < PM/엔지니어 관찰. 데이터 누적 후.

---

## 2026-05-18 (Phase 16H — Action.aliases_json Korean 시드 보강)

> 16G 시니어 라이브 검증에서 surface 됨: Action source 가 wired 됐으나 95% generic English (`["execute"]`, `["design"]`) 라 effective-dead. FQN/label 의 Korean 토큰을 alias 로 추가, stopword 필터로 generic verb noise 차단.

### 추가
- [x] `scripts/seed_phase16h_action_korean_aliases.py` — idempotent 시드:
  - FQN + label 에서 Korean 토큰 추출 (compound `정합성_검증` + split `정합성/검증`)
  - **stopword 필터**: `{실행, 검증, 처리, 확인, 검사, 수행, 조회, 갱신}` 단독 alias 제외 (compound 형은 유지)
  - confirmed row 도 enrichment (append-only, replacement 아님)
- [x] DB backup: `data/ontology.db.bak-pre-phase16h-20260518-233416`
- [x] 적용 결과: **6 actions updated, +10 Korean aliases, 130 unchanged**
  - `action.scm.슬랩설계_실행` + `__designer` → `[슬랩설계_실행, 슬랩설계]`
  - `action.scm.order.정합성_검증` → `[정합성_검증, 정합성]`
  - `action.scm.product.분류` → `[분류]`
  - `action.scm.결정` → `[결정]`
  - `action.scm.std.match_customer_limit_for_order` → `[고객표준, 매칭]`

### tests
- [x] `tests/simulation/test_phase16h_korean_alias_derivation.py` **6 PASS** (pure Korean / compound + stopword / Korean+English / FQN underscore / English-only / dedup)
- [x] simulation suite **304 PASS** regression 0 (이전 298 + 16H 6)

### 페르소나 검증 (시니어 라이브 production)

| Var | 16G | 16H | 16H 순 기여 |
|---|---|---|---|
| `슬랩설계` | `['슬랩설계']` (1) | (4) `+slab design, design, 슬랩설계_실행` | **+3** |
| `정합성` | `['정합성']` (1) | (3) `+정합성_검증, validate` | **+2** |
| `고객표준` | 5 (BT only) | 7 `+고객표준 매칭, 매칭` | **+2** |
| `실행` | 1 | 1 | **0** stopword 동작 |
| `검증` | 1 | 1 | **0** stopword 동작 |
| `두께` | 6 | 6 | **0** 회귀 0 |

**시니어 SHIP** — `_check_fixture_compat` 실호출로 `슬랩설계 → designSpec` / `정합성 → 정합성_검증_결과` / `매칭 → 고객표준` matched_params 잡는 것 실증. 16G→16H 순 기여 6 action 에 정확 국한, over-expansion 0.

---

## 2026-05-18 (Phase 16G — alias source 확장: Action + CodeField @Column)

> 시니어 16B 권고 #3. `_expand_var_to_aliases` 가 `business_terms.aliases_json` 단일 source 였음. 두 추가 source 통합 — `ActionRow.aliases_json` (129 rows, label/aliases LIKE %lookup% strict 정확 매칭) + `CodeFieldRow.@Column(name=XXX)` (168 fields, Java field ↔ DB column 양방향 bridge). repo_id isolation 일관 적용.

### 추가
- [x] `_expand_var_to_aliases` 가 3 source union: BusinessTerm → Action → CodeField
- [x] CodeField path: `@Column(name=XXX)` regex (`_COLUMN_NAME_RE`) 로 alias 추출, field.name ↔ col_name 양방향
- [x] case-preserving dedup (`out_set` exact-string 기준) — `thickness` vs `THICKNESS` distinct alias 유지

### tests
- [x] `tests/simulation/test_multiturn_phase16g_alias_source_ext.py` **8 PASS** (8 시나리오: @Column bridge / 역방향 / Action match / 3-source union / backward compat / no match / @Column 다른 attr 무시 / repo_id isolation)
- [x] simulation suite **298 PASS** regression 0 (이전 290 + 16G 8)

### 페르소나 검증 (시니어, 실 ontology.db S1~S4)

| 시나리오 | 16A only | 16G full | 16G 순 기여 |
|---|---|---|---|
| S1 `thickness` | 6 (BT 만) | 7 | `+THICKNESS` (CodeField @Column) |
| S2 `ORDER_NO` (DB col) | 1 (본인) | 2 | `+orderNo` (CodeField bridge) |
| S3 `orderNo` (Java field) | 2 (`주문번호`) | 3 | `+ORDER_NO` (CodeField bridge) |
| S4 미존재 var | 1 (graceful) | 1 | 무변동 (의도) |
| Bonus `errorCode` | 1 | 2 | `+ERROR_CODE` |

**시니어 SHIP** — CodeField source (#3) production 가치 분명. Action source (#2) 는 데이터 빈약 (95% generic `["execute"]`) 으로 **effective-dead capability**, 단 4 시나리오 모두 over-match 0 → no harm.

### 잠재 이슈 (시니어 권고)
- MEDIUM — Action source 보강 필요 (한국어 alias 채우기) — Action 시드 보강 task 분리
- LOW — performance: 3 query × N lookup_candidates quadratic. SQLite 짧은 tx → production scale OK
- LOW — case-preserving dedup 의 `thickness/THICKNESS` 양쪽 surface 는 UI chip 시각적 중복. downstream verdict 무영향 (`.lower()` 비교)

---

## 2026-05-18 (Phase 16F — multi-condition AND verdict semantics)

> 시니어 16B 권고 #2. 기존 `_infer_verdict` 가 multi-condition signal 단순 합산 → OR-like. 명시적 AND semantic: per-condition matched count tracking + reasoning N/M surface + partial multi-cond fixture-compat boost guard.

### 추가
- [x] `_infer_verdict` 에 `per_cond_matched: list[bool]` tracking 추가 — condition 별 (expression match OR var+value match) 결과 집계
- [x] `cond_match_suffix` 생성 — multi-cond (총 2개 이상) 케이스에서:
  - all match: `" · 조건 N/N 매칭 (모든 조건)"`
  - partial: `" · 조건 M/N 매칭 (partial)"`
  - zero match: `" · 조건 0/N 매칭"`
- [x] 모든 verdict 분기 (has_expression_match, has_strong_evidence, body_pattern, ...) 끝에 reasoning suffix 부착 — dead code 제거
- [x] partial multi-cond + fixture_compat=ok 시 likely_yes → yes 자동 승격 **보류** (`is_partial_multi_cond` regex detect)

### tests
- [x] `tests/simulation/test_multiturn_phase16f_multi_cond.py` **7 PASS** (all-match=yes / partial=likely_yes / zero=unknown / N/M surface / all-surface / single backward-compat / all≥partial signals)
- [x] simulation suite **290 PASS** regression 0 (이전 283 + 16F 7)

### 페르소나 검증 (최QA 사이클 2회)

**1차 QA 평가 (3/10 production-broken)**:
- 이슈 #1: N/M suffix surface 가 **6/7 분기에서 dead code** — `has_expression_match` 외 분기 (e.g., rule-driven likely_yes) 에서 reasoning 에 부착 안 됨
- 이슈 #2: AND 약화 효과를 fixture_compat boost 가 **다시 끌어올림** — `likely_yes → yes` 자동 승격으로 partial multi-cond 무력화

**Fix 적용**:
- (1) cond_match_suffix 를 함수 끝 분기 외부에서 모든 verdict 에 한번에 attach (이미 포함된 경우 skip)
- (2) `build_gate_hypothesis` 에 `is_partial_multi_cond` regex (`r"조건 (\d+)/(\d+)"` 매칭 + M<N) 추가, partial multi-cond 이면 verdict 승격 보류

**2차 production smoke**:
- multi-cond partial (`{thickness<0.1, width>100}` body에 thickness만): verdict=`likely_yes` + reasoning에 `"조건 0/2 매칭 · fixture-compat 통과 but partial multi-cond — verdict yes 승격 보류"` surface
- single-cond control (`{margin<1.0}`): verdict=`yes` (backward compat 유지)

### 잔여
- 16G — alias source 를 CodeMethod/Action annotations 까지 확장 (시니어 권고)
- PM 16E UX 권고 4 종 (rank-2 jump CTA / confidence 회색 / 노랑 그룹화 / dashboard W4 발화율 %)
- 실 fixture invoke (multi-day)
- suggestion chip quality (14C R1)
- 사용자 query log 매핑 갭 자동 탐지

---

## 2026-05-18 (Phase 16D + 16E — extended warnings (W1c/W4) + frontend UI badge)

> QA 16C 권고 3 종 직접 구현 — W1c (alias_gap root cause) + W4 (target_is_test) backend + integrity_warning UI badge frontend.

### 16D — extended warnings backend

- [x] `_compute_integrity_warnings` 확장:
  - `matched_var: str | None` (None=unset / ""=explicit empty) + `target_fqn: str` 인자
  - **W1c**: `verdict ∈ {yes, likely_yes} + matched_var=="" + rule_signals ≥ 2` → `body_unsupported_alias_gap` (한·영 alias 미커버 root cause)
  - **W4**: target_fqn 이 `*Test*` / `Mock*` / `*Stub*` / `*tests.*` 패턴 → `target_is_test` (production 대신 테스트 선택 가능성)
- [x] `build_gate_hypothesis` 가 reasoning regex 로 matched_var 추출 + target.code_method_fqn 전달
- [x] tests **7 PASS** (W1c gating / W1c miss / W4 Test / W4 Mock / W4 production negative / backward compat / build smoke)
- [x] simulation suite **283 PASS** regression 0

### 16E — frontend UI badge

- [x] `frontend/src/components/section3/multiturn/GateExecutedReadOnlyCard.tsx`:
  - `parseIntegrityWarnings(sources)` — `integrity_warning=([a-z_]+)` 정규식 + dedupe
  - WARNING_META 6종 (target_is_test 🧪빨강 / body_unsupported_alias_gap 🌐주황 / body_unsupported_no_rule ⚠노랑 / body_unsupported_rule_only ⚠노랑 / no_strong_evidence ⚠노랑 / cross_evidence_mismatch ⚠노랑)
  - 발화 칩 header 아래 surface + hover tooltip = 원본 detail
- [x] TS clean (npx tsc --noEmit)

### 페르소나 검증

**최QA (16D)**: 라이브 W4 정확 발화 (`SdWidthRangeActionTest` + 보너스 `SdThicknessActionTest`), W1c gating 정확, false positive 0. UI badge 미완 = 다음 1순위.

**김PM (16E)**: 즉시 도움 YES — likely_no + 빨간 🧪 "Test 의심" 칩 조합으로 "agent 가 테스트 코드 잘못 짚음" 코드 안 읽고 인지. 신호등 색상 분리 직관적.

### 잔여 (PM 16E UX 권고)
- 빨간 칩 클릭 → "다른 후보 보기" CTA (rank-2 production class 점프)
- 빨강 칩 ≥1 시 confidence % 취소선·회색
- 노랑 3종 동시 발화 시 카운트 배지 그룹화
- 대시보드에 W4 발화율 % — modeling 시드 품질 회귀 지표

---

## 2026-05-18 (Phase 16C — verdict-fixture cross-check integrity warnings)

> 시니어 16B TOP 권고. 4 필드 (verdict / reasoning / matched_var / fixture_compat) 모순 시 명시적 surface — 사용자/시니어가 verdict 신뢰도 판단 가능.

### 추가
- [x] `gate_hypothesis.py::_compute_integrity_warnings` 신설 — 4 모순 패턴 detect:
  - W1: verdict=yes/likely_yes + reasoning "변수 매칭 없음" + rule=0 → `body_unsupported_no_rule`
  - W1b: 같은 reasoning + rule≥1 → `body_unsupported_rule_only` (의도된 fallback, 약한 경고)
  - W2: yes/likely_yes + fixture_compat=fail + rule=0 + body 약함 → `no_strong_evidence`
  - W3: likely_no/no + fixture_compat=ok + body_signals≥3 → `cross_evidence_mismatch`
- [x] `build_gate_hypothesis` 가 warning 들을 `Provenance(source="llm_inference", detail="integrity_warning=...")` 로 sources 에 추가 (confidence=0.5)

### tests
- [x] `tests/simulation/test_multiturn_phase16c_cross_check.py` **7 PASS**
- [x] simulation suite **276 PASS** regression 0 (이전 269 + 16C 7)

### 페르소나 검증 (최QA, 5+1 시나리오)

| # | 시나리오 | verdict | warning | 평가 |
|---|---|---|---|---|
| S1 | 주문 수량 0 | yes / 0.75 | 無 | 정상 |
| S2 | 두께 0.1mm | yes / 0.75 | 無 | 정상 |
| S3 | compileTime -1 | likely_no / 0.55 | 無 | 정상 |
| S4 | 엣징 마진 1.0 | likely_no / 0.55 | 無 | 정상 |
| S5 | 두께 시뮬 | bundle_prepared | 無 | 정상 (simulate 분기) |
| S+ | STOCK_CODE=1 | likely_yes / 0.85 | **W1b 발화** | 정확 root cause surface |

**QA SHIP**: 정상 5/5 false positive 0 + 실 데이터 W1b 발화. 16C 머지 유지.

### 잔여 (QA 권고)
- W1c — verdict=yes + matched_var='' + rule≥2 → `body_unsupported_alias_gap` (root cause 더 명확)
- W4 — target 이 `*Test`/`Mock*` 클래스면 `target_is_test`
- UI surface 강화 — EvidenceCard 빨간 배지로 visible

---

## 2026-05-18 (Phase 16A + 16B — Korean↔English var-alias bridge, end-to-end)

> Phase 14B 시니어 false negative ("주문 수량" var ↔ 영문 param "order" 매칭 실패) 의 본질 해결. 두 메커니즘 평행 진화 — `_check_fixture_compat` (16A) + `_infer_verdict` (16B).

### 16A — `_check_fixture_compat` alias bridge
- [x] `_expand_var_to_aliases(var, repo_id)` 신설 — `business_terms.aliases_json` 정확 매칭 + **token-level expansion** ("주문 수량" → "주문" 도 lookup)
- [x] `_check_fixture_compat` 가 `repo_id` 옵셔널 인자 받아 alias 확장 후 param 매칭. var miss false negative 해결
- [x] `_infer_verdict` priority 보정: var miss 일 때도 rule_signals ≥ 2 면 likely_yes (rule 기반 추정)

### 16B — `_infer_verdict` alias bridge in body matching
- [x] `_infer_verdict(..., var_aliases_per_cond=None)` 신규 인자 — condition 별 한·영 alias list
- [x] var multi-token + alias 통합 → 어떤 candidate 라도 body match 하면 var hit
- [x] expression pattern regex 각 alias candidate 시도 — `"두께" "<" "0.1"` → body 의 `thickness < 0.1` 매칭
- [x] `build_gate_hypothesis` 가 `_expand_var_to_aliases` 로 alias list 빌드 후 `_infer_verdict` 전달

### tests
- [x] `tests/simulation/test_multiturn_phase16a_var_alias.py` **7 PASS**
- [x] `tests/simulation/test_multiturn_phase16b_verdict_alias.py` **5 PASS**
- [x] simulation suite **269 PASS** regression 0 (이전 257 + 16A 7 + 16B 5)

### 페르소나 검증 (시니어, 16A → 16B)

| 시나리오 | 16A 결과 | 16B 결과 (최종) |
|---|---|---|
| S1 "주문 수량 0" | yes / 0.85 (fixture_compat=ok matched_params=['order']) | **yes / 0.75** (matched_var='Order') |
| S2 "두께 0.1mm" | likely_no / 0.55 (verdict body raw "두께" 매칭 X) | **yes / 0.75** (matched_var='thickness' alias bridge) |
| S3 "주문 검증 simulate" (회귀) | bundle_prepared / 0.85 | bundle_prepared / 0.85 동일 |
| S4 negative control "compileTime" | likely_no | likely_no (alias 노이즈 0) |

**시니어 평가: SHIP** — 한·영 alias gap 사실상 **종결**. verdict/reasoning/matched_var/fixture_compat 4 필드 일관.

### 잔여 (시니어 권고)
- 16C — verdict-fixture cross-check assertion (4 필드 불일치 시 integrity_warning)
- 16D — multi-cond AND 가설
- 16E — alias source 를 CodeMethod/Action annotations 까지 확장

---

## 2026-05-18 (Phase 15C — fill declared_on_term=None via FQN pattern + add margin term)

> 15B 후속: declared_on_term=None 인 90 actions 중 12 도메인 패턴 매칭으로 정정. 마진 term 신규 추가 (action 데이터 없지만 alias bridge 용).

### 추가
- [x] `scripts/seed_phase15c_domain_terms.py` 신규 — 멱등:
  - 신규 BusinessTerm `term.scm.margin` (label="마진", aliases 6 종)
  - 12 도메인 패턴 (edging/productivity/margin/customer/algorithm/trace/history/...) × declared_on_term=None action 매칭 → 정정 (11 actions)
- backup: `data/ontology.db.bak-pre-phase15c-*`

### 실 backend 검증 (김PM 페르소나 4.4/5)

| 시나리오 | top-1 (score) | 변화 | 점수 |
|---|---|---|---|
| 엣징 영향? | dg103_edging_group_misses_throws (23) | 0 cand → 1 | ★★★★☆ |
| cumulativeProductivity 영향 | ProductivityService.cumulativeProductivity (32) | 약함 → 1위 | ★★★★★ |
| history 기록 어디? | SdHistoryController.byOrder/bySlab/executeWithHistory | clean | ★★★★★ |
| 마진 변경 | term 있지만 action 0 → 인접 dg103_edging fallback | suggestion 동작 | ★★★☆☆ |
| 폭 변경 (15B 회귀) | SdTargetWidthAction (55) | 변동 없음 | ★★★★★ |

**평균 4.4/5** (15B 3.8 → +0.6).

### Phase 15 시리즈 종료 평가 (PM 권장)
- 15A/B/C 누적: silent wrong target 위험 사실상 ELIMINATED (4 도메인 + 12 패턴)
- 잔여: margin action 시드 (별도 modeling 작업), score 가중치에 declared_on_term explicit
- Phase 16 후보: 사용자 query 로그 기반 매핑 갭 자동 탐지

### Schema 일관성 노트
- BusinessTermRow.kind 는 `atomic` / `composite` 만 valid (TermKind enum)
- BusinessTermRow.source 는 `manual` / `auto` / `llm` / `user` 만 valid
- 사용자 patch 로 3 scripts 의 kind/source 정정됨 — 향후 데이터 시드 작업 시 동일 값 사용

---

## 2026-05-18 (Phase 15B — batch seed dimension terms (length/width/weight/slab_count/split))

> 시니어 15A 검증 발견: 24 actions 가 모두 `term.scm.order.order` 로 매핑됨 (silent wrong target 위험 잠재). 같은 패턴 (15A 재사용) batch seed.

### 추가
- [x] `scripts/seed_phase15b_dimension_terms.py` 신규 — 5 dimension BusinessTerms upsert + 14 actions declared_on_term 정정 (멱등):
  - `term.scm.slab.length` (label="길이", aliases 8 종) — 3 actions
  - `term.scm.slab.width` (label="너비", aliases 8 종) — 3 actions
  - `term.scm.slab.weight` (label="중량", aliases 10 종) — 5 actions
  - `term.scm.slab.slab_count` (label="슬라브 매수", aliases 7 종) — 1 action
  - `term.scm.slab.split` (label="분할", aliases 7 종) — 2 actions
- backup: `data/ontology.db.bak-pre-phase15b-*`
- 유지: 슬랩설계_실행 / order.정합성_검증 / 결정 / record_* (의도적 order 매핑 / logging)

### 실 backend 검증 (김PM 페르소나 9/10)

| 시나리오 | top-1 (score) | term 매칭 | 점수 |
|---|---|---|---|
| 폭 변경 영향? | SdTargetWidthAction (55) | term.scm.slab.width | ★★★★★ |
| 길이 설정 동작? | SdFinalLengthRangeAction (29) | term.scm.slab.length | ★★★★★ |
| 중량 시뮬? | SdInitialSlabWgtAction (54) | term.scm.slab.weight | ★★★★★ |
| 슬라브 매수 영향? | SdSlabCountAction (55) | term.scm.slab.slab_count | ★★★★☆ |
| 엣징 마진 영향? (회귀) | 0 cand → suggestion fallback | — | ★★★☆☆ |

**4/5 시나리오 silent wrong target 완전 소멸**. #5 는 엣징/마진 term 미시드 — Phase 15C 후보.

### 후속 발견 (Phase 15C 트리거)
- 엣징 / 마진 / 압연 / 실수율 / 생산성 도메인 term 추가 시드 가치 (PM 9/10 권장 우선순위 1~3)

---

## 2026-05-18 (Phase 15A — modeling 시드 데이터 패치 (thickness term))

> 시니어 페르소나 14E 예측: "1행 + 1컬럼만 채우면 14E 자동 발현". 코드 변경 0 으로 silent wrong target ELIMINATED.

### 추가
- [x] `scripts/seed_phase15a_thickness_alias.py` 신규 — 멱등 patch 스크립트:
  - BusinessTerm `term.scm.thickness` upsert (label="두께", aliases=["thickness","Thickness","thk","slab thickness","두께값"])
  - Action `action.scm.thickness_실행.declared_on_term` 을 `term.scm.order.order` (잘못된 매핑) → `term.scm.thickness` 로 정정
- backup: `data/ontology.db.bak-pre-phase15a-20260518-213549`

### 실 backend 검증 (시니어 페르소나)
- **S1 "두께 검증 시뮬해줘"** — SdThicknessAction.execute **#1 score 47.0** (이전 14E baseline 23 / wrong target SdOrderValidator). silent wrong target ELIMINATED.
- **S2 "thickness validation impact?"** — SdThicknessAction.execute **#1 score 51.0**. expanded query `'thickness validation 두께 thk slab thickness 두께값'` — bidirectional alias 동작 확인.
- **S3 "주문 검증 시뮬"** (회귀 control) — SdOrderValidator.validate #1 score 58.0. 회귀 없음.

**시니어 평가: YES** — 14E 예측이 production 으로 검증됨. 코드 변경 0.

### 후속 발견 (Phase 15B 트리거)
- SQL 감사: 25+ dimension actions (final_width_range_실행, target_length_실행, width_range_실행, ...) 가 모두 `term.scm.order.order` 로 잘못 매핑. business_terms 에 폭/너비/길이/마진/엣징 term 없음. 동일 silent wrong target 위험 잠재.
- ontology builder 의 idempotent upsert 보장 필요 (re-import 시 confirmed declared_on_term 보존).

---

## 2026-05-18 (Phase 14F MVP — anchor_bindings 활용)

> 페르소나 시니어 14B 후속 우선순위 #2: substring 매칭 한계 → AST binding 도약. 이미 modeling 측에 163 행 시드된 `anchor_bindings` (fragment-level mapping) 을 multiturn agent 가 surface.

### 추가
- [x] `backend/section3/agents/multiturn/gate_hypothesis.py`:
  - `_fetch_anchor_bindings(fqn, repo_id)` — `mapping_layer.AnchorBindingRow` SQLite 직접 fetch. anchor_locator / target_action_fqn / target_slot / rationale / line / confirmed / source.
  - `build_gate_hypothesis` 에 anchor 통합:
    - condition var ↔ anchor.target_slot / rationale 매칭 시 `anchor_signals += 1`
    - confidence formula 에 anchor_signals × 2 가중 (signal_count ≥ 4 → 0.85, 이전 0.75 max)
    - `Provenance source="ontology"` 에 `anchor_bindings N 행 · matched slots: [...]` surface

### tests
- [x] `tests/simulation/test_multiturn_phase14f_anchors.py` **5 PASS** (fetch 3 + surface 1 + boost 1)
- [x] simulation suite **257 PASS** regression 0

### 실 backend 검증
- "주문 수량이 0" → SdFinalLengthRangeAction.execute target. `anchor_bindings 4 행` surface. confidence 0.75 → **0.85** (Phase 14F boost). fixture_compat=fail (var miss) 는 경고만, verdict=likely_yes 유지.

### 잔여 Phase 15+ 후보
- modeling 시드 데이터 패치 (Phase 14E 후속): "두께" 등 누락된 한·영 alias 채우기 — 코드 변경 0 으로 14E 자동 발현
- Korean ↔ English var-alias 보강 in `_check_fixture_compat` (Phase 14B 시니어 발견)
- 실 fixture invoke (multi-day, 정석)

---

## 2026-05-18 (Phase 14B MVP — fixture compatibility check)

> 페르소나 시니어 13c/14D 검증 한계: verdict 가 heuristic 만. 실 fixture invoke 는 multi-day. **MVP**: var ↔ method param 사전 type-compat 체크.

### 추가
- [x] `backend/section3/agents/multiturn/gate_hypothesis.py`:
  - `_check_fixture_compat(conditions, params)` — var ↔ param name substring 매칭 + value/param type 호환성 (numeric/decimal/string/bool). 결과 `{compat: True/False/None, matched_params, mismatch_reason}`.
  - `_fetch_method_params(fqn, repo_id)` — `code_methods.params_json` SQLite fetch (asyncio.to_thread).
  - `build_gate_hypothesis` — compat=True 시 verdict 강화 (likely_yes → yes), compat=False + **type incompat** 시 verdict 약화 (yes/likely_yes → likely_no). compat=False + **var miss** 시 verdict 영향 X (Korean↔English alias 미커버 false negative 방지 — 시니어 회귀 발견 후 fix).
  - Provenance source 에 `fixture_compat=ok|fail matched_params=[...] reason=...` surface.

### tests
- [x] `tests/simulation/test_multiturn_phase14b_fixture_compat.py` **8 PASS**
- [x] simulation suite **252 PASS** regression 0

### 페르소나 subagent (시니어)
- **S1 "주문 수량이 0" — 회귀 발견 + fix**: 초기 구현은 var-miss → likely_no 강등 (한국어↔영문 alias 미커버 false negative). fix: var-miss 는 verdict 영향 X, 경고만 surface. 재검증 후 verdict=likely_yes 유지 + `fixture_compat=fail` 정직 surface.
- **S1b compat=True (var ↔ param 매칭)**: likely_yes → **yes** 승격 (matched_params=['order'] + 14D expression match). 시니어 "결정적 증거".
- **compat=None (no params)**: 영향 없음 (graceful).

**시니어 평가: Conditional Yes** — gap to full fixture invoke 는 acceptable but not enough. 다음 우선순위 (1) Korean↔English var-alias 보강, (2) 14F anchor_bindings (substring → AST binding), (3) 실 invoke (multi-day).

---

## 2026-05-18 (Phase 14D — body × conditions 매칭 정밀화)

> PM 페르소나 13c 검증 발견: body_signals=0 인데 verdict=likely_yes (rule_signals 만으로 추론). 노이즈 차단 + 정확도 강화.

### 추가
- [x] `backend/section3/agents/multiturn/gate_hypothesis.py::_infer_verdict` 4 가지 정밀화:
  - **(a) var multi-token AND**: 다중 단어 var ("주문 수량") 의 모든 token 이 body 에 등장해야 hit
  - **(b) value word-boundary**: 영문/숫자 value 는 `\b{val}\b` regex 로 boundary 매칭 ("0" 이 "index0" 안에 매칭 차단)
  - **(c) co-occurrence boost**: var + value 가 같은 line 에 있으면 body_signals +2
  - **(d) expression pattern regex**: body 안에 `var\s*op\s*value` 정확 매칭 시 verdict=`yes`/`likely_yes` + body_signals +3
  - **var-miss false positive 강등**: var 매칭 없이 op/value 만 hit → `likely_no` (이전엔 likely_yes 노이즈)

### tests
- [x] `tests/simulation/test_multiturn_phase14d_body_match.py` **8 PASS** (word-boundary, multi-token, co-occurrence, expression, korean op, unknown, empty, evidence-only)
- [x] simulation suite **244 PASS** regression 0

### 페르소나 subagent (QA + PM 통합)
- **S1 "주문 수량이 0"** — likely_yes / 0.75, reasoning 이 "business_rule 만으로 추론, body 직접 검증 안 됨" honest surface
- **S2 "폭이 0 이면?"** — unknown / 0.20 (이전 13c PM 발견 false positive 해결)
- **S3 "두께가 0"** silent wrong target → unknown / 0.20 honest

**잔여 risk** (Phase 14B 후속):
- condition extractor 가 op="=" 추출 → Java body 의 "==" 와 불일치로 expression regex fall-through. 한국어→Java 연산자 매핑 보강 가능.
- candidate ranking 이 hypothesis 의도와 부정합 — Phase 14B (real fixture verdict) 가 부분 해결 가능.

---

## 2026-05-18 (Phase 14C — suggestions chip auto-research + hypothesis/lookup card render)

> 김PM/박주니어 페르소나 공통 요청 (suggestions chip → 1-click 재검색) + 13a/13c backend payload (executed_lookup / executed_hypothesis) 가 frontend 에서 silently null 렌더되는 버그 동시 해결.

### 추가
- [x] `frontend/src/lib/section3/multiturn.ts`:
  - `GateTarget` 에 `suggestions?: string[]` + `conditions?: Array<{var,op,value,unit}>` 노출. intent 에 `locate / explain / hypothesis` 추가.
  - `BusinessRuleEvidence` + `GateExecutedLookup` + `GateExecutedHypothesis` + `HypothesisVerdict` 신설.
  - `GatePayload` union 4 → 6 leaf 확장.
- [x] `frontend/src/components/section3/multiturn/MultiturnChat.tsx`:
  - `onSuggestionClick(suggestion: string)` 추가 — `reset() → onNewSession?() → start(suggestion, currentRepo)`. 1-click 으로 새 세션 자동 시작.
  - `DecisionCard` 가 `executed_lookup` / `executed_hypothesis` payload 도 분기 — 이전엔 `return null` 로 silently 빈 화면.
- [x] `frontend/src/components/section3/multiturn/GateTargetCard.tsx`:
  - `INTENT_META` 6 종 (locate/explain/hypothesis 색상 추가).
  - 0-cand 시 suggestions chips 렌더 (Sparkles icon + primary 색 칩) + 1-click 콜백.
  - hypothesis intent 시 conditions chips 미리 surface (var/op/value/unit pink badge).
- [x] `frontend/src/components/section3/multiturn/GateExecutedReadOnlyCard.tsx` 신규:
  - lookup / hypothesis 통합 카드. verdict badge (yes/likely_*/no/unknown × confidence%), conditions, reasoning, body_text, file_path, linked_term, callers (match_kind + strength), business_rules evidence (severity badge).

### 회귀 검증
- TS `npx tsc --noEmit` clean
- backend simulation suite **236 PASS** (frontend-only 변경이라 변동 없음)

### 페르소나 subagent (실 backend, slab-design-real-v2)

**김PM 8.0 / 10**
- 시나리오 1 (suggestion 1-click): UX round-trip clean (`MultiturnChat.onSuggestionClick` → start → respond) — chip 클릭 시 새 세션 자동 시작
- 시나리오 2 (hypothesis): turn 3 `executed_hypothesis` verdict=likely_yes / confidence=0.75 / DG001-005 evidence — 카드 데이터 path clean
- 시나리오 3 (locate): turn 3 `executed_lookup` body+file+linked_term+3 callers+5 rules — 렌더 회귀 fix

**잔여 (Phase 14 후속)**:
- R1: suggestion chip vocabulary 가 ontology actions 와 매칭 안 되면 chip 클릭해도 동일 0-cand 반복 (chip quality 개선 필요)
- R2: confirm + respond 2-step turn 3 fragility on network drop (idempotent retry pattern 검토)

---

## 2026-05-18 (Phase 14E — 한·영 alias gap, cross-lingual term expansion)

> Phase 13b/13c 시니어 페르소나 silent wrong target 위험 후속 — 한·영 alias 가 ranking 에 활용 X. business_terms.aliases_json 양방향 lookup + ranking boost.

### 추가
- [x] `backend/section3/agents/multiturn/gate_i.py`:
  - `_expand_search_terms(search_terms, repo_id, cap_per_token=5)` 신설 — **strict token 매칭** (SQLite LIKE 로 candidate 좁힌 후 Python 측 정확 일치 filter). substring 매칭만 쓰면 ValidationResult / Validator 같은 helper 가 "검증" 으로 매칭되어 noise 발생 — strict 로 회피.
  - `_fetch_related_term_fqns(search_terms, repo_id)` 신설 — search_terms 가 정확 매칭하는 BusinessTerm FQN set.
  - `_apply_ranking_boost(term_fqns_in_query=...)` 인자 추가 — 후보의 `declared_on_term` 이 이 set 에 있으면 `_DECLARED_ON_TERM_BOOST` (=10.0).
  - `build_gate_i` — search_query 에 expanded terms 사용 (asyncio.to_thread). ranking boost 에 term_fqns_in_query 전달.

### tests
- [x] `tests/simulation/test_multiturn_phase14e_alias_expansion.py` **9 PASS** (expansion 6 + gate_i wire 1 + boost 2)
- [x] simulation suite **236 PASS** regression 0 (이전 227 + 14E 9)

### 실 backend 검증 (시니어 페르소나 subagent)

| 케이스 | expansion | top-1 score | 결과 |
|---|---|---|---|
| "두께 검증 시뮬" | dormant (term 미등록) | SdOrderValidator 23 | silent wrong target 유지 (데이터 gap) |
| "검증결과 확인" | 6개 alias inject | ValidationResult.pass/fail 50 (+10 boost) | 정확 |
| "주문 검증 시뮬" | 5개 alias inject | SdOrderValidator 58 (+10) | 정확·회귀 없음 |
| "누적생산성" | dormant | 0 candidate | false positive 없음 |

**시니어 평가: Conditional Yes** — mechanism 정확. ValidationResult noise: strict 전환으로 case 1 candidate 3개로 축소 (fuzzy 면 5~10개). "두께 검증" 케이스는 modeling 시드에 `term.scm.thickness` 1행 + `SdThicknessAction.execute.declared_on_term` 1 컬럼 추가만 하면 14E 코드 변경 0 으로 자동 발현.

### 잔여 — modeling 시드 데이터 패치
- modeling 측 (별도 작업): 누락된 도메인 term 의 한·영 alias 채우기. 14E 가 데이터 채워지면 즉시 효과.

---

## 2026-05-18 (Phase 14A — confirm guard for 0-cand)

> Phase 13c 페르소나 검증 (QA / PM) 발견: candidates=[] 일 때 `confirm` 가 ok:true 통과 → turn 3 가 422 "selected_index 범위 밖" — UX 폭탄. confirm 시점에 즉시 거절.

### 추가
- [x] `backend/section3/api/multiturn_router.py` — `confirm` 엔드포인트 가드:
  - action="confirm" + target_selected + candidates=[] → 422 + suggestions hint detail
  - action="confirm" + selected_index 누락 → 422
  - action="confirm" + selected_index 범위 밖 → 422
  - action="retry" / "modify" 는 candidates=[] 여도 통과 (재시도 의도)

### tests
- [x] `tests/simulation/test_multiturn_phase14a_confirm_guard.py` **5 PASS**
- [x] `tests/simulation/test_multiturn_router.py` 2 회귀 fix — turn 1 의 (stub) 0-cand confirm 시도 → turn 2 의 valid candidates 로 갱신
- [x] simulation suite **227 PASS** regression 0 (이전 222 + 14A 5)

### 실 backend 검증
- `엣징 마진 변경하면 어디 영향?` (0 cand 케이스) — confirm 422 + detail `suggestions=['엣징그룹코드', 'edgingGroupCd'] 로 재질문하거나 action='retry' / 'modify' 로 다시 시도.`
- 정상 케이스 (candidates 있음) — 변경 없음

---

## 2026-05-18 (Phase 13c — hypothesis intent + conditions + executed_hypothesis verdict)

> 방안 C 의 세 번째 단계. 최QA 페르소나 1:1 해결 (boundary 검증 질의). 4 페르소나 subagent 사후 검증으로 가치 실증.

### 추가

- [x] `backend/section3/agents/multiturn/intent.py`:
  - `_VALID_INTENTS` 에 `hypothesis` 추가 (6종) — boundary / edge-case 질의
  - `IntentDecision.conditions: list[dict[str,str]]` — `[{"var","op","value","unit"}]` 추출
  - `_SYSTEM_PROMPT` 에 hypothesis 분류 가이드 + 한국어 비교 연산자 매핑 ("미만"→"<", "이하"→"<=", "초과"→">", "이상"→">=") + `conditions` JSON schema 명시
  - `classify_with_llm` 가 LLM JSON 의 `conditions` 파싱 + validation (var/value 비면 skip)
  - `StubIntentClassifier` 에 `forced_conditions` 인자 (테스트)
- [x] `backend/section3/agents/multiturn/schemas.py`:
  - `HypothesisVerdict` Literal (yes / likely_yes / likely_no / no / unknown)
  - `GateExecutedHypothesis` payload 신설 (target / conditions / body_text / file_path / line_* / verdict / reasoning / evidence / confidence / sources)
  - `GateTarget.intent` 6종 확장. `GateTarget.conditions: list[dict]` 추가 — Gate I 가 turn 2 에서 conditions surface (UX 가시화)
  - `GatePayload` union 6 leaf 로 확장
- [x] `backend/section3/agents/multiturn/gate_hypothesis.py` 신규 — `build_gate_hypothesis(target, conditions, repo_id, ontology_client)` async builder:
  - body + meta + linked_term + business_rules evidence 병렬 fetch
  - `_infer_verdict` heuristic: body 안에 var/value/op 매칭 시그널 + rule.statement 매칭 시그널 합산 → verdict 결정. signals=0 → unknown (정직), strong → likely_yes
  - confidence: signal_count 기반 (0.2~0.75)
  - Phase 13c MVP 는 heuristic — Phase 14 가 fixture 실제 실행으로 검증 승격
- [x] `backend/section3/api/multiturn_router.py`:
  - turn 3 분기에 `intent=="hypothesis"` → `build_gate_hypothesis` + session done
  - `_next_gate_kind` 에 `target_selected + confirm + intent=hypothesis → executed_hypothesis`
- [x] `backend/section3/agents/multiturn/gate_i.py` — `intent_decision.conditions` 를 `GateTarget.conditions` 로 forward

### tests
- [x] `tests/simulation/test_multiturn_phase13c_hypothesis.py` 신규 **13 PASS** (intent 6 + schema 3 + builder 2 + router turn 3 + state machine)
- [x] simulation suite **222 PASS** regression 0 (Phase 13b 13 + Phase 13a 14 + 기존)

### 페르소나 subagent 검증 (실 backend, slab-design-real-v2 + OpenAI 실 LLM)

**최QA (8년차 QA 엔지니어, 1:1 수혜자)** — **4.0 / 5 (이전 13b 2.5 → +1.5)**
- "주문 수량이 0 이면 어떤 에러?" → intent=hypothesis, conditions=`[{var:"주문 수량",op:"=",value:"0",unit:""}]`, verdict=`likely_yes`, confidence 0.75, **DG002 evidence 정확 hit**
- "두께 0.1mm" → intent=hypothesis, conditions 정확 (unit:"mm"), verdict=unknown / 0.20 (보수적, 정직)
- 잔여: confirm guard for 0-cand (state machine bug, 5분 fix) + 실제 fixture invoke 로 verdict 승격

**김PM (5년차 PM)** — **3.5 / 5**
- "주문 수량 0 인 케이스 처리 어떻게?" → 5 candidates, executed_hypothesis verdict=likely_yes/0.75 + 5 business_rule evidence — 즉답 가능
- "엣징 마진 1.0 미만" → 0 candidates 회귀 (Phase 13b 잔여 마찰)
- 발견: body_signals=0 인데 verdict=likely_yes (rule_signals=4만 추론) — Phase 14 에서 body × conditions 매칭 강화

**이시니어 (10년차 백엔드)** — **Conditional Yes**
- Phase 13b 가 silent 했던 wrong target 위험을 verdict=unknown + confidence=0.20 + reasoning 으로 honest surface → **silent wrong target 위험 ELIMINATED**
- 미존재 메서드 (`calculateMargin`) → graceful 0 candidates + HTTP 400 (fabricated verdict 없음)
- 잔여: 한·영 alias gap (Phase 13b 부터 unresolved), fixture 실행 verification (Phase 14)

### 13c 결론
- ✅ QA 페르소나 hypothesis 핵심 가치 production. 4 페르소나 모두 Phase 12/13a/13b/13c 누적으로 의미 있는 가치 surface.
- ✅ silent wrong target 위험 verdict + confidence 로 정직 surface
- 잔여 Phase 14 후보 (페르소나 공통):
  1. confirm guard for 0-cand (state machine bug)
  2. 실제 fixture invoke 로 hypothesis verdict 승격 (heuristic → 실 실행)
  3. suggestions chip → 1-click auto-research (frontend UX)
  4. body × conditions 매칭 강화 (현재 rule_signals 만으로 likely_yes)
  5. 한·영 alias gap (한국어 도메인 term ↔ 영문 식별자 bridge)

---

## 2026-05-18 (Phase 13b — search keyword extraction + 0-cand fallback)

> 방안 C 의 두 번째 단계. 김PM / 박주니어 페르소나 잔여 마찰 (search 가 풀 query 던져서 0 cand) 핵심 해결.

### 추가

- [x] `backend/section3/agents/multiturn/intent.py`:
  - `IntentDecision.search_terms: list[str]` — LLM 추출 검색 키워드만 (1~5개)
  - `_SYSTEM_PROMPT` 에 search_terms 추출 가이드 (의도/조사 제외, 도메인 명사 + 영문 식별자 + 비즈니스 용어만)
  - `classify_with_llm` 이 LLM JSON 의 `search_terms` 파싱 (cap 5)
  - `StubIntentClassifier` 에 `forced_search_terms` 인자 (테스트)
- [x] `backend/section3/agents/multiturn/schemas.py`:
  - `GateTarget.suggestions: list[str]` — 0-cand 시 인접 term 추천
- [x] `backend/section3/agents/multiturn/gate_i.py`:
  - `build_gate_i` — `intent_decision.search_terms` 가 있으면 그것을 ontology/sim_v2 검색 query 로 사용 (없으면 user_query)
  - `_fetch_suggestions(query, search_terms, repo_id)` — `business_terms.aliases_json` substring 매칭. 0-cand 시 surface
  - 토큰화 fallback: search_terms 가 비면 user_query 토크나이즈 (영문 3 자+ / 한글 2 자+)

### tests
- [x] `tests/simulation/test_multiturn_phase13b_search.py` 신규 **13 PASS** (IntentDecision 6 + 기본 GateTarget 2 + suggestions 2 + gate_i wiring 3)
- [x] simulation suite **209 PASS** (전 209 → 추가 13 → 222 — Phase 13c 와 통합)

### 페르소나 subagent 검증 (실 backend, slab-design-real-v2 + OpenAI 실 LLM)

**김PM** — **Yes, 이전보다 도움이 됨**
- "엣징 마진 변경하면 어디 영향?" → search_terms=`["엣징","마진"]`, search query `엣징 마진` (풀 문장 누락) — 정확
- candidates=0 시 suggestions=`["엣징그룹코드","edgingGroupCd"]` surface — 인접어 추천 동작
- 잔여 3 개: ranking 의 search_terms × declared_on_term boost / 한국어+camelCase 동시 surface noise / business_rule 무관 dump

**박주니어 (신입 백엔드)**
- "validateOrder 어디 있어?" → intent=locate, search_terms=`["validateOrder"]` — 깔끔
- Phase 13a executed_lookup 응답 완전 surface (body 18 lines + file_path + linked_term + 3 callers + 5 rules)
- 잔여: ontology miss → sim_v2 fallback 의 무관 후보 5개 / "did you mean" fuzzy 매칭 없음

**이시니어** — **silent wrong target 위험 발견 (Phase 13c 가 해결)**
- "두께 검증 simulate" → SdOrderValidator silent wrong target — 시뮬은 PASS 통과하나 사용자는 두께 검증한 줄 알지만 실제 주문 검증
- 한·영 alias gap 이 본질 — Phase 12 ranking boost 로 덮을 수 없음

**최QA** — **2.5 / 5 — Phase 13c 절실**
- search_terms 가 boundary value (1.0, 0.1mm, 0) 의도적 누락 → QA 의 핵심 조건 분실. Phase 13c 가 conditions 로 분리 → 해결됨

### 13b 결론
김PM / 박주니어 1차 수혜. 시니어가 silent wrong target 위험 식별 → 즉시 Phase 13c 진행으로 해결.

---

## 2026-05-18 (Phase 13a — locate / explain intent + executed_lookup)

> 방안 C (점진적) 의 첫 단계. 매 단계 후 4 페르소나 subagent 검증 — 운영 가치 실증 후 다음 진행.

### 추가

- [x] `backend/section3/agents/multiturn/intent.py` — `MultiturnIntent` 에 `locate` / `explain` 추가. `_VALID_INTENTS` 5종. LLM `_SYSTEM_PROMPT` 에 "어디 / 위치" → locate, "뭐함 / 어떻게 / 설명" → explain 분류 가이드 + "위치+동작 모호 시 explain 우선" / "메서드명만 던지면 explain 기본" 규칙 명시
- [x] `backend/section3/agents/multiturn/schemas.py` — `BusinessRuleEvidence` (fqn/statement/severity) + `GateExecutedLookup` payload 신설. `GateTarget.intent` 5종 확장. `GatePayload` union 5 leaf 로 확장
- [x] `backend/section3/agents/multiturn/gate_executed_lookup.py` 신규 — `build_executed_lookup(target, mode)` async. body + meta (병렬) + caller_graph + action label/term + business_rules evidence 통합 응답
- [x] `backend/section3/agents/multiturn/ontology_client.py` — `SimV2BackedOntologyClient.get_method_meta` 신설 (SQLite 직접 query 로 file_path / line / return_type). 이전엔 HybridOntologyClient 만 보유해서 SimV2-only 사용 시 locate payload 빈 값 surface 됐던 버그 해결
- [x] `backend/section3/api/multiturn_router.py` — turn 3 분기에 locate / explain → `build_executed_lookup` + session done. `_next_gate_kind` state machine 에 `target_selected + confirm + intent=locate/explain → executed_lookup`

### tests
- [x] `tests/simulation/test_multiturn_phase13a_locate_explain.py` 신규 **14 PASS** (intent 5종 + schema 3 + state machine 2 + /respond 2 + business_rules surface 1 + get_method_meta 2)
- [x] `tests/simulation/test_multiturn_intent.py` 기존 2 test 갱신 (explain 이 valid 가 됐으므로)
- [x] simulation suite **181 PASS** regression 0

### 페르소나 subagent 검증 (실 backend, slab-design-real-v2)

**김PM** — locate ★★★★★, explain ★★, impact 불변
- 쿼리 "주문 검증 어디서 해?" → intent=locate, executed_lookup 완전 surface (body 431자 + callers 10 + linked_term + business_rules 5건 DG001~005 한글 자연어). **김PM 의 최대 승리**
- 쿼리 "엣징 마진 변경하면 어디 영향?" → 여전히 0 cand (search 가 풀 query 던짐 — Phase 13b 영역)
- 잔여: explain 의 매칭 정확도 + impact 의 0-cand fallback

**박주니어** — locate (fix 후) ★★★★, explain ★★★, validate* 매칭 ★★
- 쿼리 "cumulativeProductivity 어디서 계산?" → intent=explain (이전 impact 분류 X 해결), body+linked_action surface
- 쿼리 "OrderService.process 어디 정의?" → **fix 후 file_path / line=21-40 / return_type=void / callers fqn 정상 surface** (이전 모두 빈 값)
- 잔여: 매칭 정확도 (`validateOrder` → 다른 메서드 surface)

**이백호 (시니어)** — explain ★★★★
- 쿼리 "ProductivityService.cumulativeProductivity 정의 + caller" → intent=explain (이전 impact), body 898자 + callers 3 (receiver_exact + name_only) + business_rules 5 + linked_term 1-shot
- Gate III impact 의 부분 대체 가능 (단 transitive callers 미제공)

**최테스터 (QA)** — ★☆ (가설문은 13c 영역)
- "두께가 음수면" → intent=explain fallback 되었으나 candidates 0 → dead-end
- Phase 13c (hypothesis tool) 절실 — boundary value + business_rule 매칭 + fixture re-synth

### 13a 결론
김PM / 박주니어 / 시니어 = locate / explain 의 1차 수혜자. QA 는 13c 까지 대기. **다음 단계 검토 시점**:
- 13b (search keyword extraction + 0-cand fallback + ranking 추가 boost) 가 김PM / 박주니어 잔여 마찰의 핵심
- 13c (hypothesis tool) 가 QA 페르소나 1:1 해결

## 2026-05-18 (Phase 12 Activation — 기존 ontology 데이터를 agent 가 깨우기)

> 출발점: 데이터 vs agent 활용 감사 (`multiturn_data_vs_agent_audit.html`) — 사용자 가설 "모델링 그래프 잘 되어있는데 agent 가 못 쓰는 것 아닌가" 압도적 검증. 10 마찰점 중 6 개 = agent 미활용. 새 기능 0, 재배선 5 항목.

### Item 1 — `SimV2BackedOntologyClient.get_caller_graph` stub 활성화

- [x] `backend/section3/agents/multiturn/ontology_client.py` — 이전 `return []` stub 을 SQLite `CodeLayerStore.get_method_callers_with_match` 직접 호출로 교체. `asyncio.to_thread` 로 wrap. dedupe + `_MATCH_STRENGTH` 적용. graceful fallback.
- 실 검증: `affected_methods: []` → `1 행 (SdDesigner.design, match=name_only)` 으로 surface.

### Item 2 — Gate III impact confidence caller-count aware

- [x] `backend/section3/agents/multiturn/gate_iii_impact.py` `_impact_confidence` — caller_count=0 시 ok+passing 분기에서도 cap 0.5 적용. "변경 안전" 오해 방지.
- ok=True + fixtures>0 + caller>0: 0.8 + 0.2*ratio (unchanged)
- ok=True + fixtures>0 + caller=0: **0.3 + 0.2*ratio** (new — capped at 0.5)

### Item 3 — ActionCandidate schema 4 필드 확장

- [x] `backend/section3/agents/multiturn/schemas.py` — `role`, `parent_role`, `annotations: list[str]`, `declared_on_term` 추가. 모두 optional, backward-compat.

### Item 4 — 랭킹 boost (role / parent_role / annotations / class pattern / FQN / 의미 토큰)

- [x] `backend/section3/agents/multiturn/gate_i.py` `_apply_ranking_boost` 신설:
  - `_ROLE_BOOST`: business=+5 / adapter=-1 / helper=-3
  - `_PARENT_BOOST`: domain=+3 / framework=-1 / infra=-2
  - `_DOMAIN_ANNOTATIONS` (@Service/@Component/...) +2
  - `_CLASS_PATTERN_BOOST`: `.action.` +6 / `.wrapper.` -3 / `.dto.` -4 / `result` -2 (← ValidationResult.pass 같은 helper 패키지 패널티)
  - 의미 토큰 (영문 4+자 / 한글 2+자) substring → +4 per match
  - FQN 직접 명시 (`.` 포함) → +15
- [x] `_enrich_with_ontology_metadata` 신설: ontology.db 의 CodeMethodRow / CodeTypeRow / ActionRow 한 번에 fetch → role / parent_role / annotations / declared_on_term 매김
- 실 검증: "thickness 검증 시뮬" → **SdThicknessAction.execute #1 (이전 #3)**, ValidationResult.pass/.fail 모두 #4-5 로 내려감

### Item 5 — business_rules evidence 노출 (Q5 "확실한 근거" 강화)

- [x] `backend/section3/agents/multiturn/gate_i.py` `_find_related_business_rules` 신설: 후보의 `declared_on_term` 으로 연결된 `business_rules.terms_ref_json` LIKE 매칭. 상위 5 행을 `Provenance(source=ontology)` 로 sources 에 추가.
- 실 검증: "thickness 검증" 응답 sources 에 **DG001 (재고주문 제외) / DG002 (양수 검증) / DG003 (포장단중 검증)** 같은 자연어 statement 5 행 surface.

### 검증

- [x] tests 신규 `tests/simulation/test_multiturn_phase12_activation.py` — **11 PASS** (caller_graph 3 + confidence 2 + schema 2 + ranking 2 + rules 2)
- [x] 기존 simulation suite — **169 PASS** (regression 0)
- [x] 실 backend 풀 페르소나 회귀:
  - "thickness 검증 시뮬" 랭킹 역전 확인 (SdThicknessAction #1)
  - "calc cumulative productivity 영향도" caller surface 확인 (1 행)
  - candidate 응답에 role/parent_role/annotations/term 4 필드 채움
  - sources 에 business_rules 5 행 surface

backward-compat 유지 — 기존 응답 schema 의 모든 필드 그대로, 신규 필드 optional. 사용자 가설 검증된 대로 **새 LLM prompt / 새 알고리즘 0**, 순수 데이터 활용 재배선.

## 2026-05-18 (Phase 11.6 — Dashboard repo 선택 → Chat 으로 propagate)

> 사용자 질문 "레포 변경은 어떻게 하나?" → 답변 중 발견된 UX 갭: dashboard 의 repo 칩 선택이 chat 의 `repo_id` 와 연결 안 되어 있었음. 옵션 (A) 채택 — 부모(Section3Section)가 `selectedRepo` 보유, dashboard ↔ chat 양쪽에 전달.

- [x] `Section3Section.tsx` — `selectedRepo` state lift up, URL `?repo=` query param 추가 (`readInitialRepo` + `pushUrlState` 3 인자 확장 + popstate 처리)
- [x] `Section3Section.tsx` — `onRepoChange(repo)` 콜백, dashboard 에 전달
- [x] `Section3Section.tsx` — `defaultRepoId` 를 MultiturnChat 에 전달
- [x] `DashboardPanel.tsx` — 내부 state → controlled props (`selectedRepo`, `onRepoChange`). 첫 fetch 시 부모가 비어 있으면 첫 repo 자동 선택해서 부모에 보고
- [x] `MultiturnChat.tsx` — `defaultRepoId` prop 받아 `repoId` 초기화 + active session 없을 때만 dashboard 선택 변경 시 따라감 (load 된 session 은 그대로)
- [x] `npx tsc --noEmit` clean

흐름:
1. 사용자가 dashboard 진입 → repos[0] 자동 선택 → URL `?view=dashboard&repo=slab-design-real-v2`
2. (다중 repo 적재 시) 다른 칩 클릭 → URL `?repo=` 갱신 + per-repo 카드/세션 재로딩
3. 멀티턴 nav 클릭 → MultiturnChat 의 EmptyState `repo_id` input 에 자동 propagate
4. 새 chat 시작 시 `repoId` 가 마지막으로 dashboard 에서 고른 값으로 들어감

**현재 적재 repo 가 1 개라 시각적 "전환" 데모는 안 됨** — option (C) 두 번째 테스트 repo 시드 가 필요하면 별도 작업.

## 2026-05-18 (Phase 11.5 — Dashboard 깨진 섹션 정리 + repo 인식)

> 사용자 지시: "지금 대시보드 화면에 쓸모없는거 없는지 확인해서 필요없는건 전부 제거 / 필요한건 제대로 뜨고 있는지 확인 / repo별로 동작하는지 확인". 분석 결과 대시보드의 절반 (Neo4j 기반 노드/관계 카드, legacy 빠른 진입, dev-only amber tip) 이 깨져 있거나 모순 — 전면 재작성.

### 제거된 섹션 (왜)

- [x] **"Ontology 노드" 5 카드** (Term/Step/Standard/Class/Method/Table) — `/api/section3/stats` (Neo4j `/graph/stats` forward) 가 모두 **0** 반환. 실 데이터는 SQLite 에 있음 → 오해 유발
- [x] **"Relations" 칩 16개** — 같은 이유. Neo4j 가 DEPENDS_ON 14 + CONTAINS 464 외엔 모두 0
- [x] **"🚀 빠른 진입" 4 카드** — bridge/sandbox/code-impact/data-impact 진입점. Section3Section 이 이미 nav 에서 숨김 처리한 legacy view → dashboard 가 진입점 제공하는 게 모순
- [x] **amber tip box** — "Neo4j 직접 접근 0건" / "SECTION2_REQUESTS.md" 안내. dev-only 메모 + "oncology" 오타

### 신규 추가

- [x] **Backend** `GET /api/section3/repos` (`backend/section3/api/router.py`) — SQLite ontology.db 의 repo 별 8-카운트 (actions / code_methods / code_types / business_terms / business_rules / realizations / call_sites / sessions). 어떤 테이블이든 repo 등장하면 surface, 알파벳 정렬
- [x] **tests** `tests/simulation/test_section3_repos.py` (**6 PASS**: empty / single / multi-sort / per-repo isolation / sessions-only repo / 8 keys 보장)
- [x] **Frontend API** `frontend/src/lib/section3/api.ts` — `RepoSummary` / `RepoCounts` 타입 + `listRepos()` 함수
- [x] **Frontend UI** `DashboardPanel.tsx` 전면 재작성:
  - **Repo 선택자 칩** — 알파벳 순, 첫 repo 자동 선택, 칩에 "Nm / Na / Ns" 미니 요약 표시
  - **8 카운트 카드 그리드** — 선택 repo 의 실 데이터 (`toLocaleString()` 천단위 포맷, 8 색상 tone, lucide 아이콘)
  - **최근 세션 (repo 필터)** — 선택 repo 로 자동 필터, repo 변경 시 재로딩 표시

### 검증

- [x] pytest **65 PASS** (test_section3_repos 6 + test_multiturn_session_list 14 + 기존 multiturn 45 — regression 0)
- [x] `npx tsc --noEmit` clean
- [x] 실 backend (localhost:8001):
  - `/api/section3/repos` → `slab-design-real-v2` × {actions:130, code_methods:1081, code_types:150, business_terms:76, business_rules:17, realizations:135, call_sites:2298, sessions:66}
  - `/multiturn/sessions?repo_id=slab-design-real-v2` 3 세션 surface
  - `/multiturn/sessions?repo_id=other-repo` 0 (필터 동작)

backward-compat — `/api/section3/stats` endpoint 는 유지 (SandboxPanel/BridgeChatPanel legacy 진입점이 여전히 호출). DashboardPanel 만 사용 중단.

## 2026-05-18 (Phase 11 — Session History Browser / Option B)

> 사용자 의사결정: dashboard 가치 분석 (`dashboard_value_analysis.html`) 의 "최소 (권장)" 프리셋 — A + B 채택. 매몰된 `/session/{sid}/replay` 자산을 surface + 3 인 팀 운영 페인 해결.

### Backend — GET /api/section3/multiturn/sessions

- [x] `backend/section3/agents/multiturn/persistence.py` — `SessionSummary` dataclass + `list_recent_sessions(limit, repo_id, search)` 함수. last_activity_at desc 정렬, user_query ilike substring 검색, 단일 query 로 turn_count + last_gate_kind aggregate
- [x] `backend/section3/api/multiturn_router.py` — `SessionSummaryView` Pydantic + `SessionsListResponse` + `GET /sessions` endpoint (limit 1-200 clamp)
- [x] `tests/simulation/test_multiturn_session_list.py` 신규 — 14 tests (persistence 8 + endpoint 6: empty / latest first / repo filter / search / case-insensitive / limit / turn_count / last_gate)

### Frontend — Dashboard "최근 세션" 섹션

- [x] `frontend/src/lib/section3/multiturn.ts` — `SessionSummary` 타입 + `listSessions(opts)` API client (URLSearchParams 기반 query 직렬화)
- [x] `frontend/src/components/section3/multiturn/useMultiturnSession.ts` — `loadSession(sid)` 액션 노출 (기존 sid 로드용; refresh 재사용)
- [x] `frontend/src/components/section3/multiturn/MultiturnChat.tsx` — `initialSid` / `onNewSession` props. URL 진입 시 자동 load, "새 대화" 시 부모 알림
- [x] `frontend/src/components/section3/Section3Section.tsx` — `?sid=` URL param 처리, popstate 호환, `openSession(sid)` → `pushUrlState("multiturn", sid)`, `clearSid()` 콜백
- [x] `frontend/src/components/section3/DashboardPanel.tsx` — `RecentSessionsSection` 신설 (debounced search input + SessionRow 카드 리스트 + Gate 라벨 매핑 + status tone) + `onOpenSession` prop wire

### 검증

- [x] pytest tests/simulation/test_multiturn_session_list.py — **14 PASS**
- [x] 기존 multiturn router/persistence tests regression — **59 PASS** (multiturn 영역 전체)
- [x] frontend `npx tsc --noEmit` clean
- [x] 실 백엔드 (`localhost:8001`) curl 검증:
  - GET /sessions 기존 16+ 세션 surface (turn_count + last_gate_kind 정확)
  - search=테스트 (Korean URL-encode) → 1 match
  - repo_id=nonexistent → 0 (filter 동작)

backward-compat 유지 — multiturn flow / replay endpoint 변경 0.

## 2026-05-18 (Chat 멀티턴 재설계 Phase 7~10 — finalization: v1 deprecate + idiom diffs + W74 typed-return + caller graph 정확도)

> Phase 1-6 production wired 위에서 외부 의존 항목 모두 종결. "전부 진행해" 사용자 지시 결과.

### Phase 7 — bridge_agent v1 deprecate

- [x] `backend/section3/agents/bridge_agent.py` — module docstring 에 deprecation banner + v2 migration path 명시
- [x] `backend/section3/api/router.py` — `/api/section3/chat` 응답에 4종 deprecation header (`X-Deprecated`, `Warning` RFC 7234, `X-Deprecation-Date`, `X-Replacement`) + 호출 시 logger.warning
- [x] `frontend/src/components/section3/BridgeChatPanel.tsx` — dismissible amber banner + multiturn 진입 링크
- [x] `frontend/src/components/section3/Section3Section.tsx` — nav 라벨 "v1 chat (deprecated)" / "멀티턴 chat (v2 권장)"
- [x] `tests/simulation/test_section3_v1_deprecation.py` 신규 — 2 tests (header + body 유지)

backward-compat 유지 — v1 endpoint 동작 + deprecation 메타 동봉.

### Phase 8 — idiom_diffs surface

- [x] `backend/sim_v2/core/synthesizer/idiom_rewriter.py` — `rewrite_method_invocation(..., trace=None)` optional kwarg. 매칭 시 `{idiom_name, java_snippet, python_snippet, tier, arity}` 누적
- [x] `backend/sim_v2/core/synthesizer/java_translator.py` — `_idiom_trace` 인스턴스 상태 + `TranslationResult.idiom_rewrites` 필드
- [x] `backend/section3/sim_v2_bridge.py` `translate_java_to_python` — 반환을 `(src, fn, idiom_rewrites)` 3-tuple 로 확장
- [x] `backend/section3/agents/multiturn/gate_ii.py` `_extract_idiom_diffs` — dedup + IdiomDiff[] 구성. backward-compat 2-tuple 도 지원
- [x] `backend/section3/agents/sandbox_agent.py` — 3-tuple destructure 갱신
- [x] `frontend/src/components/section3/multiturn/GateBundleCard.tsx` — "Idiom diff" tab 추가 (Java→Python 매핑 표)
- [x] tests 추가: W75 idiom_rewriter trace 6 / gate_ii 3 (3-tuple consume, dedup, 2-tuple compat)

### Phase 9 — W74 typed-return stubs (FAIL_RETURN_TYPE 감소)

- [x] `backend/sim_v2/core/verification/sandbox_stubs.py`
  - `_typed_default_for(rt)` — Java return-type → typed Python default 매핑 (String/int/boolean/BigDecimal/List/Map/Optional/...)
  - `derive_method_return_defaults(session, repo_id)` — code_methods.return_type 전체 스캔 → simple_name 별 typed default. overload ambiguous → drop. generics strip
  - `_install_typed_returns(stub, defaults)` — stub method 마다 typed default 설치
  - 모든 stub builder 에 optional `method_return_defaults` kwarg + `build_stub_namespace` 가 autoload
- [x] tests/W74 +7 — primitive 매핑 / ambiguity / generics / repository+class+namespace integration

### Phase 10 — caller graph 정확도

- [x] `backend/modeling/code_layer/store.py` — `get_method_callers_with_match(...) -> list[tuple[CallSite, str]]` 신규. 5단계 match_kind:
  - `receiver_exact` (0.95) / `receiver_short` (0.85) / `runtime_type` (0.85) / `package_proximity` (0.70) / `name_only` (0.50)
  - `get_method_callers` 는 thin wrapper 로 유지
- [x] `backend/modeling/api/ontology_router.py` — `/code-methods/{fqn}/callers` 응답에 `match_kind` + `strength` 노출. `min_strength` query param 으로 약한 신호 필터 가능. caller 중복은 가장 강한 신호만 surface
- [x] `backend/section3/agents/multiturn/schemas.py` `AffectedMethod` — optional `match_kind`, `strength` 추가
- [x] `backend/section3/agents/multiturn/ontology_client.py` — HybridOntologyClient 가 두 필드 carry-over
- [x] `frontend/src/lib/section3/multiturn.ts` + `GateExecutedImpactCard.tsx` — affected_methods 표에 "match" + "신뢰" 컬럼 추가
- [x] tests: store TestCallerGraphMatchKind 6 + router phase10 2

### 검증

- [x] focused suite: 619 PASS (sim_v2 synthesizer + simulation + ontology_router + W74 + caller_graph)
- [x] frontend tsc clean (사전 존재 EventStreamView 오류 제외)
- [x] backward-compat: legacy v1 chat + 2-tuple translate consumers + 기존 get_method_callers all work

자세히: `toClaude/simulation/log/step_chat_redesign_phase7_to_10_finalization.md`

---

## 2026-05-18 (Chat 멀티턴 재설계 Phase 6 — modeling ontology.db 시드)

> Phase 4d 의 sec2 endpoint 본체 wire 가 빈 ontology.db + sec3 hybrid fallback 으로 작동. 본 phase 에서 sim_v2 의 slab-v2-handoff.db 데이터를 modeling ontology.db 로 migration → **sec2 endpoint 가 실 데이터 surface → sec3 hybrid 가 본체 wire 활용**.

### 신규 코드
- [x] `scripts/seed_modeling_from_sim_v2.py` — slab-v2-handoff.db 의 12 modeling 테이블을 ontology.db 로 INSERT (PK/FK 충돌 우회: `INSERT OR IGNORE` + `PRAGMA foreign_keys=OFF`). schema 거의 동일 (양 DB 가 같은 SQLAlchemy 모델 사용).
- [x] `data/ontology.db.bak-sec3-20260518-003642` — pre-seed 백업

### 수정 코드 (sec2 영역, 사용자 양 섹션 허가)
- [x] `backend/modeling/code_layer/store.py` `get_method_callers` — receiver type 부재 + possible_runtime_types 부재 시 simple_name 매칭만으로 surface (best-effort, slab-v2-handoff parser 의 일부 row 에 receiver 정보 부재 보완)

### 데이터 변경
- [x] `data/ontology.db` 의 modeling 테이블 12개 채워짐:
  - code_types 128, code_methods 985, code_fields 560, call_sites 1290
  - business_terms 43, business_rules 17
  - actions 38, realizations 43, type_realizations 36, anchor_bindings 163

### 검증
- [x] tests/simulation 138 + tests/api/test_ontology_router 19 = **157 PASS** (변경 없음 — bug fix 가 기존 test 깨지 않음)
- [x] sec2 endpoint 직접 호출 (`ONTONG_SECTION2_API_URL=self`):
  - `/actions` → 38 actions
  - `/actions/{fqn}` → action 정보 + realizations
  - `/code-methods/{fqn}/body` → body_text 431 chars + return_type
  - `/code-methods/{fqn}/callers` → caller 1 (cumulative_productivity → SdDesigner.design)
- [x] sec3 hybrid round-trip (실 데이터):
  - Gate II: confidence 1.0 (이전 0.85, schema 부재로 -0.15). sources 4종 모두 confidence>0 (ontology body 1.0 + sim_v2 translate 0.93 + ontology schema 1.0 + sim_v2 fixtures 1.0)
  - Gate III impact: affected_methods 1, confidence 1.0, ontology source 1.0

### 의의
sec3 multiturn agent 의 Gate II/III 가 fallback 없이 sec2 ontology API 본체에서 모든 데이터 받음. **Q5 비전 "확실한 근거" 완성** — ontology Provenance 가 0.0 → 1.0 surface.

자세히: `toClaude/simulation/log/step_chat_redesign_phase6_seed.md`

---

## 2026-05-18 (Chat 멀티턴 재설계 Phase 5 — Polish: SSE server-push + next_gate_kind UI)

> Phase 1-4d 의 production wiring 위에 UX polish. 클라이언트 polling → server-push (SSE). state machine hint UI surface.

### backend SSE 확장 (`multiturn_router.py`)
- [x] `/session/{sid}/stream` short-lived server-push 패턴:
  - 0.5초 폴링 + signature diff (decisions 길이 + status + user_response 존재) 시에만 새 snapshot emit
  - `session.status="done"` 도달 시 즉시 `event: done` + close
  - 30초 maximum lifetime (60 tick) — EventSource 자동 reconnect 활용
  - `event: gone` (session 삭제 감지)
  - `event: snapshot` (기존, payload + user_response 포함으로 갱신)

### frontend SSE subscribe (`useMultiturnSession.ts`)
- [x] `EventSource` open on sessionId, close on session.status="done"/unmount/gone
- [x] snapshot listener → state.decisions / session.status 자동 갱신
- [x] mutation 후 `refresh()` 도 병행 (0.5초 latency 보완)
- [x] `state.lastNextGateKind: string | null` — confirm 응답에서 받아 저장

### UI surface (`MultiturnChat.tsx`)
- [x] `SessionHeader` 가 `nextGateKind` 받아서 status != "done" 일 때 `→ {kind}` blue text 표시 (다음 단계 hint)

### test
- [x] `test_stream_emits_current_snapshot` — break 첫 snapshot 후 close 패턴 (기존 갱신)
- [x] `test_stream_emits_done_when_session_complete` — Gate III impact 완료 후 SSE 가 즉시 snapshot + done event emit (신규)

### 검증
- [x] tests/simulation **138 PASS** + tests/api/test_ontology_router **19 PASS** = 총 **157 PASS**
- [x] TypeScript clean — `useMultiturnSession`, `MultiturnChat`
- [x] 서버 검증:
  - SSE 즉시 첫 snapshot emit (active session)
  - Gate III impact 완료 후 `event: snapshot` + `event: done` 순차 emit 후 close

### Phase 1~5 누적
**tests: 67 → 157 PASS** | backend Gate I/II/III + frontend MultiturnChat + sec2↔sec3 통신 + SSE server-push production wired

자세히: `toClaude/simulation/log/step_chat_redesign_phase5_polish.md`

---

## 2026-05-18 (Chat 멀티턴 재설계 Phase 4d — 양 섹션 협업 wire)

> Phase 4 의 협업 요청 3 endpoint 를 사용자 명시적 허가 후 sec2 측에 직접 추가 + sec3 HybridOntologyClient 본체 wire. fallback delegation → 실 sec2 호출 + 미응답 시 sim_v2 fallback.

### sec2 (modeling) 변경
- [x] `backend/modeling/code_layer/store.py` — `CodeLayerStore.get_method_callers(callee_method_fqn, repo_id=None)` 신규. best-effort 역방향 검색 (callee_simple_name 매칭 + receiver type or possible_runtime_types 매칭). helper `_extract_method_simple_name/_receiver`
- [x] `backend/shared/contracts/ontology_query.py` Protocol — `get_method(fqn)`, `get_method_callers(fqn, repo_id=None)` 추가
- [x] `backend/modeling/api/ontology_query.py` Impl — Protocol 갱신 따라 `get_method`, `get_method_callers` 추가
- [x] `backend/modeling/api/ontology_router.py` — 3 신규 endpoint:
  - `GET /api/ontology/code-methods/{fqn:path}/body` → `{fqn, body_text, line_start, line_end, return_type}` 또는 404
  - `GET /api/ontology/code-methods/{fqn:path}/callers?repo_id=` → `{callers: [{fqn, distance, via}]}` (distance=1, via=direct_caller/interface_impl)
  - `GET /api/ontology/entities/{entity_name}/schema?repo_id=` → `{entity_name, fqn, fields: [{name, type_name, nullable}]}` 또는 404. simple_name OR fqn OR fqn.endswith(.name) 매칭
- [x] `tests/api/test_ontology_router.py` — **6 신규** in `TestPhase4CollaborationEndpoints` (body / 404 / callers / no-match / entity schema / 404) + `app_with_callsites` fixture (CodeType+CodeMethod+CallSite seed)

### sec3 (simulation) 변경
- [x] `backend/section3/agents/multiturn/ontology_client.py` `HybridOntologyClient` — 3 method (get_method_body / get_entity_schema / get_caller_graph) 가 fallback delegation 만 하던 것을 sec2 endpoint 호출 + try/except graceful + 200/200+body 검사 + 미응답/에러 시 sim_v2 fallback 로직으로 변경
- [x] `tests/simulation/test_multiturn_hybrid_ontology.py` — **3 갱신 + 3 추가** (sec2 wire 200 / 404 fallback 패턴): `test_hybrid_method_body_calls_sec2_endpoint`, `..._404_falls_back_to_sim_v2`, `test_hybrid_entity_schema_calls_sec2_endpoint`, `..._404_returns_none`, `test_hybrid_caller_graph_calls_sec2_endpoint`, `..._404_returns_empty`

### 검증
- [x] tests/simulation **137 PASS** + tests/api/test_ontology_router **19 PASS** (+10 신규) = 총 **156 PASS**
- [x] 서버 검증 (`ONTONG_SECTION2_API_URL=http://127.0.0.1:8001` self-loop):
  - sec2 endpoint 직접 호출: ontology.db ORM 데이터 갭으로 빈 결과 (코드는 정상, modeling builder 시드 필요)
  - sec3 hybrid round-trip: sec2 404 → sim_v2 fallback graceful. simulate path turn 3 = bundle (java 431 / python 400 / 1 fixture / confidence 0.85 / 4 Provenance). impact path turn 3 = executed_impact (affected=0 from sec2 빈 + sim_v2 빈, findings=1 "12/12 fixtures pass · 3 stubs", confidence 1.0)

### 의의
Section 2 ↔ Section 3 통신 인프라가 production wired. modeling builder 가 ontology.db 시드 채우면 sec2 endpoint 가 실 데이터 반환 → sec3 가 추가 코드 변경 없이 자동 surface. **점진적 swap pattern 완성**.

자세히: `toClaude/simulation/log/step_chat_redesign_phase4d_collaboration.md`

---

## 2026-05-18 (Chat 멀티턴 재설계 Phase 4 — HybridOntologyClient + state machine 명시화)

> Phase 2~3 의 fully sim_v2-backed 동작 위에 sec2 HTTP API 점진 swap. **하이브리드 패턴**: sec2 가 노출하는 2 endpoint (search / actions/{fqn}) 는 httpx wire, 부재 endpoint 3개 (method_body / entity_schema / caller_graph) 는 `SimV2BackedOntologyClient` delegate. sec2 측 추가 시 점진 swap.

### 신규 코드 — `backend/section3/agents/multiturn/ontology_client.py`
- [x] `HybridOntologyClient` 신규 — `__init__(base_url, http_client=None, fallback=None, timeout=10.0)`
  - `search_action_by_keyword` → `GET /api/ontology/search?q=&repo_id=&limit=`. SearchHitDTO list 중 `kind="action"` 만 필터. code_method_fqn 은 search 응답에 없으므로 "" (후속 get_action_detail 시 보강)
  - `get_action_detail` → `GET /api/ontology/actions/{fqn}`. ActionDTO 의 realizations 중 `scope="primary"` 우선, code_method_fqn 추출
  - 나머지 3 method (method_body / entity_schema / caller_graph) 는 `self._fallback` (default = `SimV2BackedOntologyClient`) delegate
  - 모든 HTTP 호출은 try/except graceful — sec2 불안정 시 빈 결과 (Q5 "빠진 대로")
- [x] `HTTPOntologyClient = HybridOntologyClient` alias — backward-compat

### endpoint 갱신 — `multiturn_router.py`
- [x] `get_ontology_client()` ENV `ONTONG_SECTION2_API_URL` 분기:
  - 값 있음 → `HybridOntologyClient(base_url=...)`
  - 값 없음 → `SimV2BackedOntologyClient` (Phase 2~3 그대로)
- [x] `confirm` endpoint 의 `ConfirmResponse.next_gate_kind` explicit 계산:
  - `_next_gate_kind(decision, action)` helper — spec v2 §2 state machine
  - target_selected+simulate+confirm → "bundle_prepared"
  - target_selected+impact+confirm → "executed_impact"
  - target_selected+retry → "target_selected"
  - bundle_prepared+confirm → "executed_simulation"
  - bundle_prepared+modify/retry → "bundle_prepared"
  - executed_* → None (session 종료)
  - ambiguous intent → None (재분류 필요)

### test
- [x] `tests/simulation/test_multiturn_hybrid_ontology.py` — **10 신규** (sec2 search wire / actions/{fqn} wire / 404/500 graceful / method_body·entity_schema·caller_graph delegate / custom fallback injection)
- [x] `tests/simulation/test_multiturn_router.py` — **5 추가** (next_gate_kind: simulate / impact / retry / ambiguous / bundle_prepared)

### 검증
- [x] tests/simulation **137 PASS** (122 → 137, +15)
- [x] 서버 검증:
  - `POST /confirm` 의 `next_gate_kind`: simulate → "bundle_prepared", impact → "executed_impact" ✓
  - `ONTONG_SECTION2_API_URL=http://localhost:9999` (unreachable) 으로 backend 기동 → `/respond` 가 sec2 timeout graceful, sim_v2 fallback 으로 5 candidates surface. ontology Provenance confidence=0.0 으로 부재 명시 ✓

### 협업 요청 (Section 2 owner)
Phase 4 의 "온전한" wire 를 위해 sec2 측 3 endpoint 추가 요청:
- **#1** `GET /api/ontology/code-methods/{fqn:path}/body` — method body 직접 노출
- **#2** `GET /api/ontology/entities/{entity_name}/schema` — entity 스키마
- **#3** `GET /api/ontology/code-methods/{fqn:path}/callers` — 역방향 caller graph

자세히: `toClaude/simulation/log/step_chat_redesign_phase4_summary.md`

---

## 2026-05-17 (Chat 멀티턴 재설계 Phase 3 — Frontend MultiturnChat)

> Phase 2 backend production wiring 위에 한국어 UI 얹음. 자연어 입력 → 단계별 카드 (대상 → 번들 → 실행 / 영향도) → 모든 카드에 Provenance.

### 신규 코드 — `frontend/src/lib/section3/`
- [x] `multiturn.ts` — API client + 백엔드 schemas.py 와 1:1 TS types (Provenance / GateTarget / GateBundle / GateExecutedSimulation / GateExecutedImpact / 13 sub-models). 4 함수 (startSession / respond / confirmTurn / getSession) + `MultiturnError` class

### 신규 코드 — `frontend/src/components/section3/multiturn/`
- [x] `useMultiturnSession.ts` hook — `{sessionId, session, decisions, pending, error}` + start/respond/confirm/reset actions. 모든 mutation 후 `getSession()` 으로 refresh (source-of-truth replay)
- [x] `ProvenanceBadge.tsx` — 4 source 별 색상 칩 (ontology/sim_v2/llm_inference/user_input) + confidence % + detail tooltip. `ProvenanceRow` 로 모든 카드 footer 통일
- [x] `GateTargetCard.tsx` — intent 배지 (시뮬레이션 / 영향도 검토 / 모호) + 후보 radio (추천 표시) + score / code_method_fqn / aliases + [이걸로 진행] / [다른 후보 검색]
- [x] `GateBundleCard.tsx` — confidence color-coded + 4-tab (Python default / Java / Fixtures / Schema) + pre 블록 + fixture/schema 표 + [실행 (Gate III)]. empty schema 시 "Q5 빠진 내용은 빠진대로" 안내
- [x] `GateExecutedSimulationCard.tsx` — invariant_status 배지 + PASS/FAIL/ERROR/SKIPPED count + case 표 (fixture_id / status / output / error)
- [x] `GateExecutedImpactCard.tsx` — confidence 막대 (color-coded) + affected_methods 표 (fqn / distance / via) + findings 리스트 (severity color)
- [x] `MultiturnChat.tsx` — 컨테이너. 빈 상태 (repo_id 입력 + 4 예시 grid) + session header + 카드 누적 렌더. **자동 진행**: turn 1 stub → 자동 respond(query) → Gate I real. confirm 시 confirm + respond 연쇄.

### 갱신
- [x] `Section3Section.tsx` — nav 5 → 6개 (`멀티턴 (v2)` 추가, dashboard 다음, Sparkles icon). View union + VALID 배열 갱신. URL `?view=multiturn` 라우팅

### 검증
- [x] TypeScript clean — 신규 multiturn 파일 6개 모두 typecheck 통과 (기존 EventStreamView.tsx pre-existing 에러만 잔존)
- [x] Next.js `/api/section3/multiturn/*` proxy → http://localhost:8001 backend 정상
- [x] 풀 플로우 via proxy (port 3000): `POST /start "주문 검증 시뮬해줘"` → turn 1 stub → `POST /respond` → turn 2 (intent=simulate, 5 candidates) → `POST /confirm/{sid}/2 selected=0` → ok=true → `POST /respond` → turn 3 bundle_prepared

### 사용자 클릭 검증 잔여
브라우저 진입점: `http://localhost:3000/?view=multiturn`. UI 의 실제 클릭/렌더는 사용자 검증 필요 (예시 질문 클릭 → 자동 turn 진행 → 4 카드 표시).

자세히: `toClaude/simulation/log/step_chat_redesign_phase3_summary.md`

---

## 2026-05-17 (Chat 멀티턴 재설계 Phase 2 Gate III — Executed sim + impact)

> Phase 2 의 마지막 게이트. simulate 흐름 (turn 4 = 실행+invariant) 과 impact 흐름 (turn 3 = caller_graph+진단) 두 분기 모두 wire. multiturn 의 풀 파이프라인 production 진입.

### 신규 코드 — `backend/section3/agents/multiturn/`
- [x] `gate_iii_sim.py` — `build_gate_iii_sim(bundle, repo_id)` async:
  - `_run_sim_pipeline_sync(action_id, code_method_fqn, repo_id, python_source, function_name)` — load_action → synthesize_fixtures(W71) → build_stubs(W74) → run_fixtures_in_process(W72) → (case_dicts, fail_reason, stub_count)
  - `_to_case_result(d)` — sim_v2 case_dict → Pydantic CaseResult (PASS/FAIL/ERROR/SKIPPED 정규화)
  - `_aggregate_invariant_from_dicts(case_dicts)` — raw invariant_status → schema invariant_status (clean/fail_nondeterministic/fail_unexpected_throw/fail_return_type/error). 모두 PASS → clean / 빈번한 fail 매핑
  - `_extract_function_name(python_source)` — 첫 `def NAME(...)` 추출
- [x] `gate_iii_impact.py` — `build_gate_iii_impact(target, repo_id, ontology_client)` async:
  - 병렬: `call_ontology_get_caller_graph` + `_load_action_async`
  - action 있으면 `call_sim_v2_quick_diagnose(action)` 호출
  - `_diagnose_to_findings(dict)` — ok+fixtures>0 → Finding(info, "quick_diagnose_passing", "N/M pass · K stubs") / blocked → Finding(warn/error, "quick_diagnose_blocked", primary_failure) + Finding(warn, "primary_failure")
  - `_impact_confidence(diagnose, caller_count)` — ok 시 0.8+0.2*(passing/fixtures), blocked+callers 0.4, blocked 0.2, no-action 0.3

### endpoint 갱신 — `multiturn_router.py`
- [x] `/respond` 초입: `session.status=="done"` → 501 ("session 이미 완료") 즉시 차단
- [x] `/respond` next_turn==3 + intent=="impact": 기존 501 → `build_gate_iii_impact` + `update_session_status("done")`
- [x] `/respond` next_turn==4: `TypeAdapter(GateBundle).validate_python(turn 3 payload)` → `build_gate_iii_sim(bundle)` → save + `update_session_status("done")`
- [x] turn 5+ → 501 (session done)

### test
- [x] `tests/simulation/test_multiturn_gate_iii_sim.py` — **8 신규** (all PASS clean / dominant failure / unexpected throw / missing python / no action / no fixtures / case_id preserve / sim_v2 provenance)
- [x] `tests/simulation/test_multiturn_gate_iii_impact.py` — **8 신규** (caller_graph / confidence high+low / findings translate / sources / no caller_graph / no action graceful)
- [x] `tests/simulation/test_multiturn_router.py` — **3 갱신/추가**: turn 3 impact → 200 (was 501), turn 4 sim → 200 (was 501), turn 5 → 501 (session done)

### 검증
- [x] tests/simulation **122 PASS** (105 → 122, +17)
- [x] 실 OpenAI + 실 sim_v2 풀 플로우 검증:
  - **Simulate (4 turns)**: 주문 검증 시뮬해줘 → 5 후보 → confirm → bundle (java 431/python 400/1 fixture) → executed_simulation (1 ERROR, W74 stub 한계 — Q5 "빠진 대로" 그대로 surface)
  - **Impact (3 turns)**: cumulativeProductivity 바꾸면 영향? → 1 후보 → confirm → executed_impact (affected=0 from sec2 API 부재, diagnose=12/12 fixtures pass + 3 stubs, conf 1.0)
- [x] Edge: session done 후 /respond → 501 ("session 이미 완료")

자세히: `toClaude/simulation/log/step_chat_redesign_phase2_gate_iii_summary.md`

### Phase 2 누적 결과
- 총 신규 모듈 5: intent / gate_i / gate_ii / gate_iii_sim / gate_iii_impact
- 총 endpoint: /start, /respond (real Gate I+II+III state machine), /confirm, /session, /stream
- 총 PASS: 122 (Phase 1 67 → Phase 2 122, +55)
- 두 분기 (simulate / impact) 의 풀 파이프라인 production 진입
- Q5 비전 (영향도 검토 + 시뮬레이션 두 흐름 + Provenance + "빠진 대로") 완성

---

## 2026-05-17 (Chat 멀티턴 재설계 Phase 2 Gate II — Java + Python + Fixtures bundle)

> Gate I 가 후보 + 사용자 confirm 까지. Gate II 는 선택된 ActionRef → 실 Java body + W75 Python 변환 + entity schema + W71 fixture 합성. 모두 한 GateBundle 에.

### 신규 코드 — `backend/section3/agents/multiturn/`
- [x] `gate_ii.py` — `build_gate_ii(target, repo_id, ontology_client)` async pipeline:
  - body = ontology.get_method_body
  - (python_source, function_name) = sim_v2.translate_java_to_python
  - entity_name = `_extract_entity_name(code_method_fqn)` (정규식 첫 파라미터)
  - schema = ontology.get_entity_schema(entity_name)
  - action = sim_v2.load_action (asyncio.to_thread)
  - fixtures = sim_v2.synthesize_fixtures
  - 단계별 실패 시 빈 surface + confidence ↓ (Q5 "빠진 내용은 빠진대로")
  - `_bundle_confidence(body/translate/schema/fixtures)` 가중합 0.35/0.30/0.15/0.20
  - `idiom_diffs` 는 [] (W75 자동 적용, surface hook 미존재 — 후속)
- [x] `ontology_client.py` **SimV2BackedOntologyClient** 신규 — production default. `sim_v2_bridge.load_body_text` / `load_action` 사용. search/entity_schema/caller_graph 는 빈 결과 (Phase 4 swap)

### endpoint 갱신 — `multiturn_router.py`
- [x] `/respond` next_turn==3 분기 추가:
  - intent="ambiguous" → 422 ("재분류 필요")
  - intent="impact" → 501 ("Gate III impact 미구현", Gate II skip — spec v2 §2 state machine)
  - intent="simulate" → `_resolve_gate_ii_target` + `build_gate_ii` + decision_log 저장
- [x] `_resolve_gate_ii_target` 가드:
  - turn 2 = target_selected (아니면 422)
  - user_response.action = "confirm" (아니면 422 "POST /confirm 으로 selected_index 보내야")
  - selected_index int + candidates 범위 안 (아니면 422)
  - ontology.get_action_detail 로 location 보강, 없으면 empty CodeLocation
- [x] `get_ontology_client()` default = SimV2BackedOntologyClient (was MockOntologyClient(empty))
- [x] turn 4+ → 501

### test
- [x] `tests/simulation/test_multiturn_gate_ii.py` — **7 신규** (happy path + 4-source Provenance + missing body + translate 실패 + missing entity schema + entity 추출 + payload roundtrip)
- [x] `tests/simulation/test_multiturn_router.py` — **5 추가** (turn 3 Gate II / turn 3 without confirm 422 / invalid selected_index 422 / impact intent 501 / ambiguous intent 422 / turn 4 501)

### 검증
- [x] tests/simulation **105 PASS** (93 → 105)
- [x] 백엔드 + 실 OpenAI + 실 sim_v2 풀 플로우:
  - `주문 검증 시뮬해줘` → turn 1 ambiguous → turn 2 intent=simulate + 5 후보 → confirm selected_index=0 → turn 3 GateBundle:
    - java_source 431 chars (real SdOrderValidator.validate body)
    - python_source 400 chars (W75 변환)
    - schema entity="" / fields=0 (sec2 API 부재, Q5 "빠진 대로")
    - 1 fixture (action.scm.order.정합성_검증#0)
    - confidence 0.85
    - 4 Provenance (ontology body + sim_v2 translate + ontology schema + sim_v2 fixtures)
- [x] impact intent → turn 3 = 501 "Gate III impact 미구현" ✓
- [x] turn 3 without confirm → 422 ✓

자세히: `toClaude/simulation/log/step_chat_redesign_phase2_gate_ii_summary.md`

---

## 2026-05-17 (Chat 멀티턴 재설계 Phase 2 Gate I — LLM intent + 후보 채움)

> Phase 1 의 endpoint shape 위에 실제 Gate I logic wire. /start 의 즉시 ambiguous stub 은 유지, /respond 의 turn 2 가 진짜 분류 + 후보.

### 신규 코드 — `backend/section3/agents/multiturn/`
- [x] `intent.py` — IntentDecision(frozen) + MultiturnIntentClassifier Protocol + StubIntentClassifier (forced + per_query) + classify_with_llm (OpenAI chat_json, unknown→ambiguous fallback) + OpenAIIntentClassifier adapter
- [x] `gate_i.py` — `build_gate_i()` async: classifier + asyncio.gather(ontology, sim_v2) + dedupe merge by code_method_fqn (score 합산) + recommended_index + 3-source Provenance
- [x] `ontology_client.py` `_match_score` 개선 — 토큰 단위 매칭 (query 가 label 보다 길어도 hit)

### endpoint 갱신 — `backend/section3/api/multiturn_router.py`
- [x] `get_classifier` / `get_ontology_client` Depends helper (test 에서 `app.dependency_overrides[...]` 로 swap)
- [x] `POST /respond/{sid}` 가 **501 → Gate progression**
  - next_turn == 2 → `build_gate_i` 호출 + decision_log 저장 + payload 반환
  - next_turn >= 3 → 501 ("Gate II/III 미구현")
- [x] `req.message` 빈 문자열 시 `session.user_query` fallback

### test
- [x] `tests/simulation/test_multiturn_intent.py` — **10 신규** (IntentDecision validation + Stub + classify_with_llm mock)
- [x] `tests/simulation/test_multiturn_gate_i.py` — **11 신규** (intent + candidates 병합 + dedupe + recommended + 3-source Provenance + Korean)
- [x] `tests/simulation/test_multiturn_router.py` — `test_respond_phase1_returns_501` 폐기, **6개 Phase 2 테스트** (simulate / impact / empty message / persistence / 404 / turn 3 → 501) + `client_factory` fixture

### 검증
- [x] tests/simulation **93 PASS** (67 → 93, +26)
- [x] 백엔드 + 실 OpenAI 호출 검증:
  - `주문 검증 시뮬해줘` → intent=simulate + 5 후보 (slab-design-real-v2 실데이터, top: 정합성_검증 score 10)
  - `cumulativeProductivity 바꾸면 영향?` → intent=impact + 1 후보
  - SSE snapshot 에 turn 1(stub) + turn 2(real) 모두 emit
- [x] edge: /respond unknown session 404, turn 3 501 OK

자세히: `toClaude/simulation/log/step_chat_redesign_phase2_gate_i_summary.md`

---

## 2026-05-17 (Chat 멀티턴 재설계 Phase 1 — 인프라 + scaffold 완료)

> 단발 chat (`bridge_agent.py`) 을 sim_v2 자산 활용 3 게이트 멀티턴 agent 로 진화시키는 인프라. 4 sub-agent 검토 + 사용자 결정 반영.

### v2 spec 결정 사항 반영
- [x] **CHAT_REDESIGN_SPEC.md v2** — 6→3 gates, §6 (wiki 패턴 오인) 폐기, alembic 없이, Q5 비전 §13 신설 (영향도+시뮬 두 흐름 + Provenance + Section 2 API 통신)
- [x] **HANDOFF.md** — Phase 1 step plan 7개 + Section 2 협업 요청 갱신 (alembic 항목 삭제)
- [x] **결정 페이지** `toClaude/simulation/chat-redesign-review.html` (8 sections, copy buttons)

### 신규 코드 — `backend/section3/agents/multiturn/`
- [x] `schemas.py` — GatePayload union (4 leaf, kind discriminator) + Provenance + 13 sub-models
- [x] `orm.py` — Section3SessionRow + Section3DecisionLogRow (alembic 없이 `Base.metadata.create_all`)
- [x] `persistence.py` — lifecycle + add_gate_decision + list + update_user_response + replay (source-of-truth hydrate)
- [x] `ontology_client.py` — OntologyClient Protocol + MockOntologyClient (in-memory catalog) + HTTPOntologyClient (Phase 2 swap stub)
- [x] `tools.py` — 9 tool wrapper (5 ontology + 4 sim_v2, asyncio.to_thread) + ToolResult + ALLOWED_PER_GATE

### 신규 endpoint — `backend/section3/api/multiturn_router.py`
- [x] `POST /api/section3/multiturn/start` — session 생성 + Gate I stub
- [x] `POST /respond/{sid}` — **501** Phase 2 stub (의도)
- [x] `POST /confirm/{sid}/{turn_no}` — user_response 병합
- [x] `GET  /session/{sid}` — replay hydrate
- [x] `GET  /session/{sid}/stream` — SSE snapshot (Phase 1 minimal)
- [x] `backend/main.py` — multiturn ORM import (bootstrap_database 전) + router include

### test
- [x] `tests/simulation/test_multiturn_schemas.py` — 15
- [x] `tests/simulation/test_multiturn_persistence.py` — 13
- [x] `tests/simulation/test_multiturn_ontology_client.py` — 11
- [x] `tests/simulation/test_multiturn_tools.py` — 5
- [x] `tests/simulation/test_multiturn_router.py` — 10
- **회귀**: `tests/simulation/` **67/67 passed**

### 통합 verification (Pre-Demo Verification Protocol)
- [x] 백엔드 startup OK (216 routes)
- [x] curl 4 endpoint 시나리오 (한국어 payload preserved, edge cases 501/404/404/422)
- [x] SSE snapshot stream 1회 emit 확인

### Step 1 summary
- [x] `log/step_chat_redesign_phase1_summary.md` — 전체 step 결과 + 검증 + Phase 2 미구현 목록

---

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
