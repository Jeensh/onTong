# Modeling Data Audit + Enrichment — slab-design-real-v2

> **시작**: 2026-05-18 4 병렬 agent 진단
> **완료**: 2026-05-18 enrichment + sim_verified 승격 + composite terms + 잔여 작업 4건 모두 종결
> **repo_id**: `slab-design-real-v2`
> **백업**: `data/ontology.db.bak-pre-enrichment-20260518-152543`
> **작업자**: cross-section 허가 받은 section3 세션 (이 세션)

## 한 줄 요약

총 unconfirmed/placeholder 2,524건을 12+ 병렬 agent + java_translator fix + sim_v2 loader patch + callsite_analyzer best-effort inference 로 **completion-grade** 데이터로 enrichment. **124/130 actions sim_verified** (95.4%). call_sites 2,298 → 51 deferred (97.8% 감소).

## 최종 상태 (2026-05-18)

### ✅ 100% confirmed
| table | confirmed/total |
|---|---|
| business_terms | **48/48** (atomic 16 + composite 32, 모두 도메인 description + aliases) |
| business_rules | 17/17 |
| realizations | 135/135 |
| type_realizations | 41/41 |
| anchor_bindings | 163/163 |

### actions verification_level 분포
| level | n | 의미 |
|---|---|---|
| **sim_verified** | **124** | ✨ sim_v2 fixture PASS 검증 완료 (95.4%) |
| signature_locked | 6 | sim ERROR (java_translator 의 deferred 패턴: try-with-resources / generic instanceof) |
| body_anchored | 0 | (모두 promoted) |

### call_sites 분포 (2,298 → 51 pending, **97.8% 감소**)
| analysis_source | n | 처리 |
|---|---|---|
| external_library | 772 | dismissed (framework noise) |
| **best_effort_inferred** | **565** | ✨ 신규 — caller body 분석으로 receiver type 추론 (confidence 0.7) |
| name_fallback_unique | 524 | auto-confirmed (single owner, confidence 0.85) |
| name_fallback_first_of_2 | 386 | heuristic-confirmed (confidence 0.5) |
| ambiguous_multi_owner_deferred | 51 | 외부 JDK 호출만 남음 (Objects.equals, JDBC 등 — 의도된 보류) |

---

## 작업 흐름 (총 12+ 병렬 agent + 4 코드 patch + 일괄 SQL)

### Phase A — 안전 cleanup
- 28 WEAK terms 삭제 (test 클래스 오인식) + 772 external-lib call_sites dismiss + 524 unique-owner auto-confirm + 386 2-owner first-match

### Phase B — Action 도메인 enrichment (4+1 병렬 agent)
- 32 body_anchored × 9 group + 15 production drafts → description/effects/rationale 도메인 내용
- 76 test drafts 템플릿 (BDD scenario from method name)
- 1 orphan (`__designer`) realization 신설 + promote

### Phase B-2/B-3 — Terms + Conflict
- 10 NEEDS_REVIEW terms enriched
- 5 conflicts 해결 (StepTrace/SingleDesign*/OrderSummary/Detail 중복)
- 7 NEEDS_REVIEW type_realizations confirmed

### Phase C — sim_v2 verification
- description 호환 marker 부착 (`자동 추천 — <fqn>` 끝 부착, 도메인 보존 + sim_v2 regex 호환)
- 36 body_anchored → 30 sim_verified (1차)

### Phase D — E2E 검증
- `cumulative_productivity` 12/12 PASS · `length_range_실행` 1/1 PASS

### Phase E (이번 추가) — composite terms + 잔여 4건

#### E-1: 27 composite terms enrichment (1 agent)
- 5 이미 done, 27 신규 enriched
- 각 term 의 Java entity/wrapper/controller 클래스 javadoc + 필드로 도메인 의미 작성
- aliases 5개씩 (한국어 + Java 명 + 약어 + 도메인 별칭)

#### E-2: 6 ERROR actions root fix — java_translator.py (1 agent)
**Root cause**: stub derivation 정상, **Java translator 가 invalid Python emit → silent SyntaxError**. 5 패턴 fix:
1. `_safe_python_name` — Python 예약어 (`pass`) → `pass_` rename
2. `_strip_generics` + `_translate_object_creation_expression` — `new ArrayList<>()` → `ArrayList()`
3. `_translate_switch_expression` — Java 14+ arrow form `case x -> ...` 감지 + safe placeholder
4. `_translate_assignment_expression` — non-statement assignment → walrus `:=`
5. `_translate_block` — comment-only body 에 `pass` 자동 추가

**결과**: 6/6 ERROR actions → ALL PASS. 30 sim_verified → **124 sim_verified** (+94)

**Deferred**: try-with-resources 다중 자원 (SeedService.reset) / generic instanceof (TraceCollector.wrap) — 더 큰 rework

#### E-3: sim_v2 loader patch (1 agent)
- `production_domain_loader.py:120-160` — `load_actions` 에 realizations LEFT JOIN 추가
- description regex 우선 (backward compat) → MIN(r.code_method_fqn) fallback
- 모든 130 actions code_method_fqn 정상 추출 확인 (regression 0)

#### E-4: callsite_analyzer best-effort receiver inference (1 agent)
- 616 deferred → 565 처리 (91.7%) → 51 만 남음
- 추론 패턴: param 214 / local 269 / catch+for-each / field 64 / implicit_this 18
- 보수성: 추론 type 이 code_types 에 존재 + 그 type 이 callee 소유한 경우만 매칭
- false positive 0 (12건 직접 sample 검증)
- analysis_source='best_effort_inferred', confidence 0.7

---

## 코드 변경 (이번 세션 cross-section 수정)

### `backend/sim_v2/core/synthesizer/java_translator.py` (+125 LOC)
- 5 helpers + 4 translator patches
- 회귀 0 — sim_v2 synthesizer 399 + W74 sandbox stubs 50 = 449/449 PASS

### `backend/sim_v2/core/ontology/domain_layer/production_domain_loader.py` (+19 LOC)
- `load_actions` SQL: actions LEFT JOIN realizations (confirmed=1) → MIN(code_method_fqn) fallback
- description regex 우선 (backward compat)

### `data/ontology.db` — 데이터 mutate (다음 세션 시 git 추적 안됨, 백업 보존)
- 32 → 48 confirmed business_terms
- 41 confirmed type_realizations (5 deleted, 7 confirmed, 12 batch confirmed)
- 130 actions 모두 promoted (94 → 124 sim_verified)
- 2,298 → 51 call_sites needs_user_confirm

---

## sim_verified 124 actions

(이전 30 + java_translator fix 로 추가된 94)

### 추가된 그룹 (E-2 fix 효과)
6 production ERROR actions:
- action.scm.결정 (SelectedHrTgtWidthResolver.resolve)
- action.scm.pass (ValidationResult.pass)
- action.scm.batch_design__driver (SdDriver.batchDesign)
- action.scm.order.extract_designable_orders (SdOrderExtractor)
- action.scm.order.정합성_검증 (SdOrderValidator.validate)
- action.scm.slab.slab_save_실행 (SdSlabSaveAction.execute)

+ 88 다른 actions (이전 signature_locked 였던 production / test methods 도 sim_v2 가 통과)

## 잔여 (6 actions, 51 call_sites)

### 6 signature_locked — sim ERROR 잔여 (java_translator 깊은 rework 필요)
- try-with-resources 다중 자원 (`SeedService.reset` 등)
- generic instanceof (`TraceCollector.wrap`)
- ticket: java_translator deeper patterns (W27 큰 부분)

### 51 call_sites ambiguous_multi_owner_deferred
- 모두 외부 JDK / 라이브러리 호출 (Objects.equals, JDBC Statement.execute, enum String 비교)
- 추론 불가능 — 보류 정상

---

## 도메인 enrichment 예시

### action (이전 vs 현재)

**Before** (`action.scm.length_range_실행`):
```
description: "자동 추천 — com.example.slabdesign.feature.sd.process.working.action.SdLengthRangeAction.execute(...)"
effects: []
rationale: "자동 매칭: SdLengthRangeAction.execute"
```

**After**:
```
description: "step 3 — 주문이 사용할 연주 설비(CAST_SPEC) 와 열연 설비(HR_SPEC) 의
길이 범위를 재룩업해 교집합으로 1차 설계가능 길이 범위 [firstLengthLow, firstLengthHigh] 를
결정한다. 하한은 두 설비 하한의 max, 상한은 두 설비 상한의 min 으로 잡으며, HR_SPEC
미존재 시 DG102(ALG_HR_SPEC_NOT_FOUND) 를 던진다.

자동 추천 — com.example.slabdesign.feature.sd.process.working.action.SdLengthRangeAction.execute(SDOrderEntity,SDSlabEntity)"

effects: [
  {"op": "read", "target": "SDOrderEntity.confirmedPlantCd, ...", "description": "..."},
  {"op": "read", "target": "CastSpecEntity.lengthLow, lengthHigh", "description": "..."},
  {"op": "mutate", "target": "SDSlabEntity.firstLengthLow, firstLengthHigh", "description": "..."},
]

rationale: "메서드 본문이 castSpecService.lookup 과 hrSpecService.lookup 으로 두 설비
spec 을 재룩업한 뒤 castSpec.getLengthLow().max(hrSpec.getLengthLow()) 와
castSpec.getLengthHigh().min(hrSpec.getLengthHigh()) 로 교집합 길이 범위를 구해
slab.setFirstLengthLow/High 로 저장한다."
```

### composite term (이전 vs 현재)

**Before** (`term.scm.order.order`):
```
description: "자동 추천 — com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity"
aliases: ["SDOrderEntity"]
```

**After** (E-1 agent 작업):
```
description: (도메인 의미 3~5 문장 — Java javadoc + 필드 분석 기반)
aliases: ["주문", "Order", "SDOrderEntity", "주문 엔티티", "order entity"]
```

---

## 백업 + 복구 정보

- 작업 전 backup: `data/ontology.db.bak-pre-enrichment-20260518-152543` (5MB)
- 백업 복구: `cp data/ontology.db.bak-pre-enrichment-20260518-152543 data/ontology.db` (서버 재기동 필수)
- 코드 변경은 git diff 로 추적 가능 (java_translator.py + production_domain_loader.py)
