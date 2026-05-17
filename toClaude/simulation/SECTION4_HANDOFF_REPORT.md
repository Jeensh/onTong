# Section 4 → Section 3 인계 통합 작업 — 최종 보고서

> **기간**: 2026-05-16 (Sprint 1~5 연속 진행 + 데모 6종 검증)
> **담당**: Section 3 (Simulation) 세션
> **인계 패키지**: `toClaude/modeling/section4-verification/section3_handoff/`
> **목표**: Section 4 가 W1-W78 로 만든 sim_v2 자산을 Section 3 의 sandbox / chat 흐름에 통합

---

## 0. 한 줄 요약

**Section 4 의 sim_v2 자산 8 모듈 (W59/W71/W72/W73/W74/W75/W77/W78) 을 Section 3 에 통합 완료.** `action.scm.product.cumulative_productivity` 가 sim_v2 직통 경로로 **12/12 fixture PASS · 3 stubs auto-derived**. 자연어 chat 의 `simulate` 분기에 sim_v2 후보 검색 + invariant 진단 surface. Sprint 1~5 (옵션 포함) 모두 완료.

---

## 1. 결과 요약

### 1.1 Sprint 진행 매트릭스

| Sprint | 작업 (Quickstart §6 기준) | 대상 파일 | 검증 |
|---|---|---|---|
| 1 | recipe-4 full pipeline (W71→W75→W74→W72) | `sandbox_agent.py` | `cumulativeProductivity` **12/12 PASS · 3 stubs** |
| 2 | recipe-2 Java baseline + sandbox 표 expected 컬럼 | `sandbox_agent.py` + frontend | `data/baselines/*.json` opt-in oracle 경로 |
| 3 | recipe-3 invariant 진단 → chat `[LOW] fallback` surface | `bridge_agent.py` | `simv2_suggestions` 이벤트 + 진단 카드 UI |
| 4 | recipe-5 W77+W78 한국어 검색 → bridge | `sim_v2_bridge.py` + bridge | "주문 검증" → 3 후보 + 진단 |
| 5 (opt) | transpiler 옵션 B (sim_v2 subclass) | `section3_translator.py` 신설 | Section3Translator 동적 subclass |

### 1.2 데모 6종 (Quickstart §4) — 모두 정상

| Demo | 결과 |
|---|---|
| UC41 한국어 검색 (W77) | 9/10 hit (90%) |
| UC42 hybrid tier (W78) | T1 3/3 · T2 3/4 · T3 1/2 · T4 1/1 |
| UC40 stub-injected (W74) | 6/11 PASS (54.5%) |
| UC37 fixture coverage (W71) | 11/38 driveable |
| UC38 invariant survey (W72) | 0/11 baseline-free (의도된 결과) |
| UC36 v2 capstone | FULLY CLEAN — 30 MERGED proposal |
| bonus recipe-5 | typo + 비표준 음역 close |

### 1.3 코드 변경

**신설 (4 파일)**
- `backend/section3/sim_v2_bridge.py` — 16 public 심볼 (open_session / load_action / load_body_text / load_baseline_map / translate_java_to_python / synthesize_fixtures / build_stubs / find_action_candidates / quick_diagnose_action / run_in_process / run_fixtures_in_process / run_fixtures_with_baseline 등)
- `backend/section3/section3_translator.py` — sim_v2 `JavaToPythonTranslator` 동적 subclass + `_IDIOM_REWRITES` 확장점
- `tests/simulation/test_sim_v2_bridge.py` — 13 test (Sprint 1: 6 + Sprint 2: 3 + Sprint 3/4: 3 + 추가 1 = 13)
- `data/baselines/README.md` — Sprint 2 baseline JSON 파일 규칙 문서

**수정 (3 파일)**
- `backend/section3/agents/sandbox_agent.py` — `_run_via_simv2()` 신설 + baseline 분기 + `_is_action_fqn` 감지
- `backend/section3/agents/bridge_agent.py` — `_emit_simv2_suggestions()` + simulate fallback wiring
- `frontend/src/components/section3/EventStreamView.tsx` — `simv2_*` 이벤트 4종 + suggestion 카드 + sandbox_result 3-컬럼 (input/expected/actual)

### 1.4 새 contract / 이벤트

**case_result 추가 필드** (sandbox_result 내부)
- `invariant_status` ∈ `{PASS, FAIL_NONDETERMINISTIC, FAIL_UNEXPECTED_THROW, FAIL_RETURN_TYPE, ERROR, UNVERIFIED}`
- `expected_value`, `actual_value`, `output_match`, `diff_summary` (Sprint 2 oracle 경로)
- sandbox_result.via = `"sim_v2"` / `"sim_v2_suggestions"`
- sandbox_result.stub_summary = `{count, sample[]}`
- sandbox_result.baseline_summary = `{enabled, entries, method_fqn}`

**스트림 이벤트 4종 신설**
- `simv2_fixtures` — W71 합성 결과 (count/synthesizable/skipped)
- `simv2_stubs` — W74 stub 결과 (count/sample[])
- `simv2_baseline` — Java baseline 부착 정보
- `simv2_suggestions` — chat fallback 후보 list + 진단

---

## 2. 검증 결과

### 2.1 단위 + end-to-end

| 항목 | 결과 |
|---|---|
| pytest `tests/simulation/test_sim_v2_bridge.py` | **13/13 PASS** |
| pytest `backend/sim_v2/` (회귀) | 1790 passed (Sprint 1~5 이전과 동일) |
| Backend `/health` | HTTP 200 |
| Frontend `/` | HTTP 200 |
| Chat 자연어 → simulate (`action.*` FQN) | 정상 — sim_v2 직통 12/12 PASS |
| Chat 자연어 → explain | 정상 — LLM 기반 term 매칭 |
| Chat fallback (`simulate` + missing target) | Sprint 3+4 wiring 정상 |

### 2.2 실측 — Chat end-to-end (curl)

```bash
curl -sN -X POST http://localhost:8001/api/section3/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"action.scm.product.cumulative_productivity 시뮬해줘"}'
```

→ 이벤트 시퀀스:
1. `thinking` — 의도 분석
2. `intent_classification` (confidence 0.9) — simulate / method 분류
3. `thinking` — sim_v2 직통 진입
4. `code_gen` — Java→Python 변환 (sim_v2 W75 적용)
5. `simv2_fixtures` count=12
6. `simv2_stubs` count=3 sample=[DEFAULT_PRODUCTIVITY, SdConstants, lookupOrDefault]
7. `sandbox_run` / `sandbox_result` / `final` — **12/12 PASS**

---

## 3. 동작하는 부분 vs 동작하지 않는 부분 (정직한 평가)

### 3.1 ✅ 동작

| 영역 | 상태 |
|---|---|
| LLM intent 분류 | Anthropic API 호출 정상 (`backend/section3/llm/intent_classifier.py`) |
| sim_v2 직통 sandbox (`action.*` FQN 직접 입력) | **12/12 PASS** end-to-end |
| W74 stub injection | NameError 0건 (anchor + AST + entity 자동 derive) |
| W75 Java idiom rewrite | 50+ idiom 자동 처리 (String/Collection/Optional/Math/Objects) |
| W77 한국어 검색 (`KoreanTermResolver`) | 4 컬럼 통합 — 9/10 query hit |
| W78 hybrid tier | typo + 비표준 음역 close |
| Sprint 2 baseline oracle 경로 | file-based `data/baselines/*.json` 활성화 |
| Sprint 3 quick_diagnose_action | 후보별 invariant 진단 요약 |
| Sprint 4 find_action_candidates | term + LIKE 보완 검색 — 3 후보 surface |
| Sprint 5 Section3Translator | 동적 subclass — MRO 정상 |

### 3.2 ⚠️ 알려진 한계 — 후속 작업 필요

| 영역 | 한계 | 원인 / 후속 |
|---|---|---|
| `data/ontology.db` (modeling 측 DB) | **0 actions / 0 code_methods 등 전 테이블 0 rows** | modeling 측이 v2 데이터 import 안 됨 — legacy `/api/ontology/*` HTTP 경로 사실상 비활성 |
| BehaviorTwinRunner ERROR (Sprint 2 oracle) | W74 stub 이 `MagicMock` 반환 시 `<` 등 비교 연산 실패 | typed-return stub (sim_v2 후속 작업, UC40 의 FAIL_RETURN_TYPE 3건) |
| explain 분기 sim_v2 미연결 | LLM 이 `explain` 으로 분류된 자연어는 sim_v2 자산 활용 못 함 | bridge_agent 의 `_handle_explain` 에 simv2 enrich 추가 필요 |
| explain 의 legacy enrich | `slab-design-real` repo HTTP search 가 ontology.db 비어 0 hit | sim_v2 `find_action_candidates` 로 enrich 대체 권장 |
| `action.*` 외 target (method/class FQN 직접) | sim_v2 직통은 `_is_action_fqn(target_id)` 체크 | method/class FQN → action 으로 역추적 매핑 필요 |
| impact_analysis [LOW] fallback | `code_impact_agent` / `data_impact_agent` 가 sim_v2 미사용 | 동일한 simv2_suggestions surface 패턴 적용 가능 |
| frontend SandboxPanel 직접 진입 | chat 외 패널에서는 sim_v2 후보 검색 UI 없음 | 패널에도 검색 박스 + 후보 카드 |
| baseline 파일 작성 도구 | 수동 JSON 작성 | "이 case 의 actual 값을 baseline 으로 저장" 버튼 |

---

## 4. 자연어 Chat 동작 진단 (사용자 질문 핵심)

### 4.1 현재 chat 흐름

```
사용자 message
  ↓
classify_intent (LLM, Anthropic Claude) — explain / simulate / impact_analysis 분류
  ↓
intent 별 분기:
  • explain          → modeling.query(explain) — LLM 기반 term 매칭
                       + legacy enrich (search) — ★ ontology.db 비어 0 hit
  • simulate         → sandbox_agent
                       + target_id 가 action.* 면 sim_v2 직통 ★ 정상
                       + target_id 누락 시 simv2_suggestions fallback ★ 정상
  • impact_analysis  → code_impact / data_impact agent — ★ ontology.db 비어 미동작
```

### 4.2 사용자 입력 유형별 동작 여부

| 사용자 발화 예시 | 분류 | 동작 |
|---|---|---|
| `action.scm.product.cumulative_productivity 시뮬해줘` | simulate | ✅ sim_v2 직통 → 12/12 PASS |
| `cumulativeProductivity 메서드 시뮬레이션` | simulate | ⚠️ target_id 가 method 식별자라 sim_v2 직통 매칭 안 됨 → composer 폴백 → ontology.db 비어 실패 |
| `cumulativeProductivity 메서드 시뮬레이션` (target_id 누락) | simulate | ✅ simv2_suggestions fallback → 후보 + 진단 |
| `엣징 사양 룩업 룰 보여줘` | explain (LLM 분류 가능) | ⚠️ explain → modeling LLM term 매칭 → enrich search 0 hit |
| `주문 검증 액션이 뭐야` | explain (실측) | ⚠️ 동일하게 explain → matched_terms 부정확 (주문단중 등) |
| `cumulativeProductivity 바꾸면 뭐가 영향받아` | impact_analysis | ❌ ontology.db 비어 0 결과 |
| `Step 5 시뮬해줘` | simulate (step) | ⚠️ modeling /query simulate 호출 → ontology.db 비어 실패 |

### 4.3 결론

**chat은 작동합니다.** 단, 두 가지 시나리오에서만 sim_v2 자산이 활용됩니다:
1. **사용자가 action FQN 을 직접 입력** — Sprint 1 경로
2. **simulate 의도이나 target 누락** — Sprint 3+4 fallback

**자연어 → action 자동 매핑** 이 부족합니다. 자연어가 `explain` 또는 `impact_analysis` 로 분류되면 sim_v2 가 작동하지 않습니다.

---

## 5. 향후 고도화 로드맵

### 5.1 P0 (즉시, 작은 변경)

#### 5.1.1 `explain` 분기에 sim_v2 enrich 부착
- 위치: `backend/section3/agents/bridge_agent.py` `_handle_explain()`
- 변경: legacy enrich (modeling.search) 이후 또는 대체로 `_emit_simv2_suggestions(user_query)` 호출
- 효과: "엣징 사양 룩업 룰 보여줘" → matched_terms 외에 sim_v2 후보 action 까지 surface

#### 5.1.2 `impact_analysis` 분기에도 simv2 fallback
- 위치: `backend/section3/agents/bridge_agent.py` impact_analysis 분기 후
- 변경: code_impact_agent / data_impact_agent 가 `ok=False` 또는 empty result 시 `_emit_simv2_suggestions(user_query)` 호출
- 효과: "cumulativeProductivity 바꾸면 영향" → 후보 action + 진단

#### 5.1.3 sandbox `method`/`class` target 도 sim_v2 우선
- 위치: `sandbox_agent.py` 의 분기 조건
- 변경: `_is_method_fqn(target_id)` 도 감지해서 sim_v2 에서 코드 매핑 시도 (현재는 `_is_action_fqn` 만)
- 효과: 메서드 FQN 직접 입력도 sim_v2 직통

### 5.2 P1 (1 sprint, 핵심 사용성)

#### 5.2.1 LLM intent classifier 에 "candidate hint" 주입
- 위치: `backend/section3/llm/intent_classifier.py`
- 변경: classify 전에 `find_action_candidates(user_query)` 로 sim_v2 후보를 미리 찾아 prompt 에 hint 로 주입
- 효과: "엣징 사양 룩업 룰 보여줘" → LLM 이 actual action FQN 을 알고 simulate / impact_analysis 로 정확히 분류

#### 5.2.2 frontend SandboxPanel / CodeImpactPanel 에 검색 박스
- 위치: `frontend/src/components/section3/SandboxPanel.tsx`, `CodeImpactPanel.tsx`
- 변경: 자연어 입력 → `/api/section3/simv2/candidates?q=` 새 endpoint 호출 → 후보 카드 surface
- 효과: chat 외 패널에서도 자연어로 action 검색

#### 5.2.3 baseline 작성 도구 — "이 case 의 actual 을 baseline 으로 저장"
- 위치: frontend EventStreamView 의 sandbox_result 카드
- 변경: "📌 baseline 으로 저장" 버튼 — backend `/api/section3/baseline/save` endpoint 가 `data/baselines/*.json` write
- 효과: 사용자가 직접 baseline 누적 가능 → BehaviorTwinRunner ERROR 케이스 점진적 close

### 5.3 P2 (sim_v2 후속 — Section 4 협업)

#### 5.3.1 W74 typed-return stub (sim_v2 측 작업)
- 현재 한계: `MagicMock` 이 declared return type 과 mismatch → UC40 의 FAIL_RETURN_TYPE 3건 + Sprint 2 ERROR
- 후속: stub 이 declared return 의 typed default 반환 (float → 0.0, str → "", etc.)

#### 5.3.2 W78 LLM assist callback 연결
- 현재: `KoreanTermResolver.resolve(..., llm_assist=None)` — Tier 4 미사용
- 후속: Section 3 의 chat LLM 을 callback 으로 plug-in — 비표준 음역 자동 close
- 위치: `backend/section3/sim_v2_bridge.py` 의 `find_action_candidates` 에서 호출

#### 5.3.3 `data/ontology.db` 시드 (modeling 측)
- 현재: 0 rows 전 테이블
- 후속: modeling 세션에 v2 데이터 import 요청
- 효과: legacy `/api/ontology/*` HTTP 경로 부활 → composer 경로 정상화

### 5.4 P3 (architectural — 멀티 시스템)

#### 5.4.1 multi-repo 지원
- 현재: `slab-design-real-v2` 하나만 (`SIM_V2_REPO_ID` 상수)
- 후속: 사용자 선택 / 다중 동시 검색 (Banking + Broadleaf + slab-v2)
- ADR 참조: `toClaude/modeling/section4-verification/sim-redesign/ADR-011-second-system-selection.md`

#### 5.4.2 closed-loop fix proposal
- gap-analysis #8 — "영향 분석 → 수정 제안" 까지 (5축 lifecycle + UC36 capstone simulator)
- 위치: `bridge_agent` suggested_followups 자리에 sim_v2 의 RENAME_PARAM / ADD_EXCEPTION 제안 surface

#### 5.4.3 legacy `transpiler.py` deprecate
- 현재: 미사용 (ontology.db 비어 composer 경로 실질 비활성)
- 후속: section3 transpiler.py 제거, sim_v2 직통 + Section3Translator 만 유지 → 코드 70% 감소 (transpiler-bridge §3 옵션 B 의 완성형)

---

## 6. 검증 시나리오 (사용자가 직접 확인)

### 6.1 즉시 — 5분

```bash
# 1) sim_v2 sanity
venv/bin/python -m backend.sim_v2.demos.uc41_korean_term_search.run | tail -3
# 기대: "9/10 query hit (90%)"

# 2) bridge 단위
venv/bin/python -m pytest tests/simulation/test_sim_v2_bridge.py -v
# 기대: 13 passed

# 3) end-to-end (action FQN 직접)
curl -sN -X POST http://localhost:8001/api/section3/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"action.scm.product.cumulative_productivity 시뮬해줘"}' \
  | grep -E 'simv2_(fixtures|stubs)|final'
# 기대: simv2_fixtures(12), simv2_stubs(3), final ok=true, summary "12 fixture · PASS 12"
```

### 6.2 브라우저 (10분)

`http://localhost:3000` → Section 3 메뉴 → BridgeChat 패널.

| 입력 | 기대 |
|---|---|
| `action.scm.product.cumulative_productivity 시뮬해줘` | 12/12 PASS + 코드 표시 |
| `cumulative productivity 메서드` (target id 누락) | simv2_suggestions 카드 3장 |
| `주문 검증 액션이 뭐야` | matched_terms 1건 ("주문단중") — ★ 부정확 (P0 #1 후속에서 close) |

### 6.3 Sprint 2 baseline 흐름 시연

```bash
# baseline 파일 1개 drop
cat > data/baselines/com_example_slabdesign_feature_sd_process_std_service_ProductivityService_cumulativeProductivity_String_String_String_String_String_String_.json <<'JSON'
[
  { "args": [null, "", "", "", "", "", ""], "expected": 0.95 }
]
JSON

# 다시 시뮬 — simv2_baseline 이벤트 + oracle 경로 활성화 확인
curl -sN -X POST http://localhost:8001/api/section3/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"action.scm.product.cumulative_productivity 시뮬"}' \
  | grep simv2_baseline
# 기대: simv2_baseline event with entries=1
```

> ⚠️ 단, baseline 경로는 현재 W74 MagicMock stub 한계로 BehaviorTwinRunner ERROR (정직한 한계). typed-return stub 후속 작업 후 close 예정.

---

## 7. 이전 작업 자료 위치

본 보고서는 다음 자료들을 통합합니다:
- `toClaude/simulation/CHANGES.md` — Sprint 1~5 상세 ad-hoc log
- `toClaude/simulation/TODO.md` — 진행 상황 (Single Source of Truth)
- `toClaude/simulation/HANDOFF.md` — 세션 인계용 요약
- `toClaude/simulation/demo_guide.md` — Sprint 1 시나리오
- memory `project_status.md` — 메모리 인덱스
- `toClaude/simulation/WORK_REPORT.md` — **Sprint 1~5 이전** 작업 보고 (2026-05-12~13). stale.

인계 패키지 (read-only):
- `toClaude/modeling/section4-verification/section3_handoff/` — Section 4 의 모든 인계 자료
- `backend/sim_v2/` — sim_v2 framework 코드 (직접 수정 금지)

---

## 8. 다음 세션 첫 작업 (recommended)

순서 우선:
1. **P0 #1** (`explain` 분기 sim_v2 enrich) — 자연어 chat 의 가장 큰 gap. 1~2 시간.
2. **P0 #3** (sandbox method/class target sim_v2) — 사용자 UX 큼. 1 시간.
3. **P1 #1** (LLM classifier 에 candidate hint 주입) — 자연어 → action 정확도 비약적 증가. 3~4 시간 (LLM prompt 튜닝 포함).
4. **P1 #3** (baseline 저장 버튼) — Sprint 2 활용성 즉시 증가. 2~3 시간.

뒤로 미룰 것:
- P3 (multi-repo, closed-loop fix) — sim_v2 시스템이 multi-system 으로 확장된 후 진행 권장.
- P2 #3 (ontology.db 시드) — modeling 세션의 협업 필요. 비동기.
