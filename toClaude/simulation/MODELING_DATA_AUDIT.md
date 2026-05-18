# Modeling Data Audit + Enrichment — slab-design-real-v2

> **시작**: 2026-05-18 4 병렬 agent 진단
> **완료**: 2026-05-18 enrichment + sim_verified 승격
> **repo_id**: `slab-design-real-v2`
> **백업**: `data/ontology.db.bak-pre-enrichment-20260518-152543`
> **작업자**: cross-section 허가 받은 section3 세션 (이 세션)

## 한 줄 요약

총 unconfirmed/placeholder 2,524건을 8 병렬 agent + 일괄 정리로 **completion-grade** 데이터로 enrichment. 36 sim-ready body_anchored actions 중 **30 actions sim_verified 승격**. E2E sandbox 2 시나리오 PASS.

## 최종 상태 (2026-05-18)

### ✅ 100% confirmed
| table | confirmed/total |
|---|---|
| business_terms | 48/48 |
| business_rules | 17/17 |
| realizations | 135/135 |
| type_realizations | 41/41 |
| anchor_bindings | 163/163 |

### actions verification_level 분포
| level | n | 의미 |
|---|---|---|
| **sim_verified** | **30** | ✨ 신규 — sim_v2 fixture PASS 검증 완료 |
| signature_locked | 94 | description/params/effects/rationale 도메인 내용 + promoted |
| body_anchored | 6 | sim ERROR (W74 typed-return stub 후속 필요) |

### call_sites 분포 (2,298 → 616 pending, **73% 감소**)
| analysis_source | n | 처리 |
|---|---|---|
| external_library | 772 | dismissed (framework noise, callee 가 repo 내 미존재) |
| name_fallback_unique | 524 | auto-confirmed (confidence 0.85, 단일 owner) |
| name_fallback_first_of_2 | 386 | heuristic-confirmed (confidence 0.5, 2-owner first) |
| ambiguous_multi_owner_deferred | 616 | needs_user_confirm 유지 (3+ owners, parser 보강 대상) |

---

## 작업 흐름

### Phase A.1 — 안전 cleanup (도메인 content 불필요)
- **28 WEAK business_terms 삭제** (27 `*Test` 클래스 + 1 Constants — auto-extractor 오류)
  - dep cleanup: 28 type_realizations 삭제 + 76 actions.declared_on_term NULL
- **772 external-lib call_sites dismiss** (analysis_source='external_library')

### Phase A.2 — 524 unique-owner call_sites name-fallback
- callee_simple_name 이 repo 내 1개 owner 만 가질 때 자동 매칭
- analysis_source='name_fallback_unique', confidence 0.85

### Phase B — 36 body_anchored actions 도메인 enrichment (4 병렬 agent)
- 각 agent 9 action 분담 — body_text 읽고 description/effects/rationale 작성
- 도메인 컨텍스트: slab steel design (CAST_SPEC/HR_SPEC 룩업, DG1xx error codes, step 1~21 algorithm)
- 모든 placeholder "자동 추천 — ..." → 실 도메인 의미로 교체
- 모든 empty effects [] → entity field 단위 read/mutate/create/emit 분류
- 모든 rationale "자동 매칭" → method body 근거의 구체적 설명

### Phase B-2 — 10 business_terms NEEDS_REVIEW
- REST controllers / DTOs / trace utils — 각 클래스 Java + javadoc 읽고 도메인 description + aliases
- 5건은 충돌로 삭제됨, 5건 enrichment 적용 (나머지는 conflict resolution 으로 처리)

### Phase B-3 — type_realizations 충돌 + NEEDS_REVIEW
- **5 conflicts 해결** — 중복 term (StepTrace, SingleDesign*, OrderSummary/Detail) → 사용자가 이미 confirmed 한 매핑 유지, 자동 mirror term 삭제
- **7 NEEDS_REVIEW confirm** — SDOrderEntity 4중 partial (의도된 flattening) + SDSlabEntity + entity 패턴 2건

### Phase B-2-ext — 15 production drafts (controllers/REST/services)
- 1 병렬 agent — `by_order` / `single_design` / `traces` / `wrap` 등 15개
- enrichment + promote DRAFT → SIGNATURE_LOCKED

### Phase B-3-ext — 76 test drafts 템플릿 + 1 orphan
- Test 메서드 76건: extract inline comment + 메서드명 → BDD 시나리오 description + promote
- Orphan `슬랩설계_실행__designer`: realization 신설 (2-arg `SdDesigner.design(SDOrderEntity,TraceCollector)`) + promote

### Phase B-ext — 12 type_realizations 일괄 confirm
- simple_name 1:1 매핑 (Java 클래스명 ↔ term label 정확 일치 검증)

### Phase B-ext — 1002 multi-owner call_sites
- 2-owner 386건: first-match heuristic confirm (confidence 0.5)
- 3+ owner 616건: ambiguous_multi_owner_deferred (parser 보강 대상)

### Phase C — sim_v2 verification + 승격
- 36 body_anchored 전체 `quick_diagnose_action` 실행
- 발견 + 수정: sim_v2 loader 가 description 에서 `자동 추천 — <fqn>` regex 로 code_method_fqn 추출 — domain enrichment 후 추출 실패
- **호환 marker 부착**: 128 actions description 끝에 `\n\n자동 추천 — <code_method_fqn>` 부착 (도메인 내용 + sim_v2 호환 동시 만족)
- 재실행: **30 actions sim PASS → SIM_VERIFIED 승격**, 6 ERROR (W74 후속)

### Phase D — E2E 검증
- **E2E #1**: `action.scm.product.cumulative_productivity 시뮬해줘` → 12/12 PASS, 3 stubs ✅
- **E2E #2**: `action.scm.length_range_실행 시뮬해줘` (새 enriched) → 1/1 PASS, 7 stubs, Java→Python (W75) 변환 정상 ✅

---

## sim_verified 30 actions

```
action.scm.fail
action.scm.batch_design
action.scm.find_group
action.scm.find_spec
action.scm.first_weight_실행
action.scm.final_length_range_실행
action.scm.final_width_range_실행
action.scm.length_range_실행
action.scm.max_split_count_실행
action.scm.product.cumulative_productivity
action.scm.product.classify_by_product_code
action.scm.product.lookup_or_default
action.scm.product.분류
action.scm.record_algorithm_failure
action.scm.record_step
action.scm.record_validation_failure
action.scm.resolve_and_set
action.scm.second_wgt_high_실행
action.scm.second_wgt_low_실행
action.scm.slab.design_orchestrator
action.scm.slab.initial_slab_wgt_실행
action.scm.slab.next
action.scm.slab.slab_count_실행
action.scm.slab.slab_wgt_recalc_실행
action.scm.split_range_실행
action.scm.std.match_customer_limit_for_order
action.scm.target_length_실행
action.scm.target_width_실행
action.scm.thickness_실행
action.scm.width_range_실행
```

## 잔여 작업

### 6 body_anchored — sim ERROR (W74 typed-return stub 의존)
```
action.scm.결정
action.scm.pass
action.scm.batch_design__driver
action.scm.order.extract_designable_orders
action.scm.order.정합성_검증
action.scm.slab.slab_save_실행
```
원인: stub 의 return type 이 MagicMock → 비교 연산 (`<`, `>`) 실패. sim_v2 측 W74 typed-return stub 후속 작업 후 자동 close.

### 616 call_sites ambiguous_multi_owner_deferred
3+ owner 모호 dispatch — parser (`backend/modeling/code_layer/callsite_analyzer.py:103-120`) 의 receiver type 추출 정확도 보강 시 자동 해결. 별도 ticket.

### 1 known caveat
- sim_v2 loader (`backend/sim_v2/core/ontology/domain_layer/production_domain_loader.py:82`) 가 `actions.description` 에서 code_method_fqn 추출 regex 의존
- **현재 해법**: description 끝에 marker 부착 (회피)
- **장기**: loader 가 `realizations` table 을 직접 query 하도록 patch — sim_v2 측 개선 ticket

## 도메인 enrichment 예시

**Before** (`action.scm.length_range_실행`):
```
description: "자동 추천 — com.example.slabdesign.feature.sd.process.working.action.SdLengthRangeAction.execute(SDOrderEntity,SDSlabEntity)"
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
  {"op": "read", "target": "SDOrderEntity.confirmedPlantCd, cmpCd, orgCd, productCd",
   "description": "확정 plant 코드와 회사·소·품명을 읽어 spec 재룩업 키로 사용한다."},
  {"op": "read", "target": "CastSpecEntity.lengthLow, lengthHigh",
   "description": "연주 설비 길이 범위 spec"},
  ...
]

rationale: "메서드 본문이 castSpecService.lookup 과 hrSpecService.lookup 으로 두 설비
spec 을 재룩업한 뒤 castSpec.getLengthLow().max(hrSpec.getLengthLow()) 와
castSpec.getLengthHigh().min(hrSpec.getLengthHigh()) 로 교집합 길이 범위를 구해
slab.setFirstLengthLow/High 로 저장한다."
```

## 권장 후속

1. **callsite_analyzer parser 보강** (Section 2 owner): receiver type 추출 정확도 ↑ → 616 deferred 자동 해결
2. **W74 typed-return stub** (sim_v2 측): 6 body_anchored actions sim PASS → 30 → 36 sim_verified
3. **sim_v2 loader 개선** (sim_v2 측): description regex 대신 realizations join → 호환 marker 제거 가능
4. **effects extraction pipeline** (Section 2): 130 actions 전부 effects 가 비어있던 원인 — auto 추출 누락. ad-hoc 으로 enrichment 했으나 시스템 차원 보강 필요.
