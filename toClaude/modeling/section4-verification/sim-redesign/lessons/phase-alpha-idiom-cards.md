# Phase α Lesson 2 — 27 Idiom Cards 의 Over-engineering

작성일: 2026-05-13 (implementation plan session)
대상: `toClaude/modeling/section4-verification/idioms/P01-P27.md` + `00-edge-cases.md` + `README.md`
관련 ADR: ADR-002 (Two-Engine + plugin), ADR-006 (polymorphic dispatch), ADR-010 (Phase α discard)
관련 결정: D2 (v2 자산 폐기, non-default)
Phase α 산출물 reference:
- commit `d4d80dc docs(sec4/idioms): 25 anchor-keyed Java→Python idiom cards + edge case taxonomy`
- `idioms/README.md` (27 cards 완성 후 갱신, 56 target_slot = 140 anchor 매핑)

---

## 1. 사실 — 27 cards 의 scope

`toClaude/modeling/section4-verification/idioms/`:
- 27 numbered cards (`P01-body.compute.md` ~ `P27-action.metadata.md`)
- `00-edge-cases.md` (10 fidelity-killer edge cases)
- `README.md` (coverage + howto)

Coverage:
- **56 distinct `target_slot`** values cover 됨 — 동일 emit 형태인 sub-slot 은 한 카드로 합침
- **140 / 140 anchors** = `repo_id='slab-design-real-v2'` 의 전체 anchor (anchor-gaps.md §0)

작업량: 카드당 ~25-40 LOC × 27 + edge cases ~60 LOC + README ~90 LOC ≈ **~1000 LOC of markdown**.

---

## 2. Idiom 카드의 분류 review

원래 분류 (README §TOC 인용):

| 그룹 | 패턴 # | Slot 예시 |
|---|---|---|
| **Compute / Output (control-flow core)** | P01-P11 | body.compute / body.set_output / body.dg_throw / body.return* / body.branch / body.loop / body.orchestration / body.delegate / body.aggregate_skipped |
| **Repository / Service Lookup** | P12-P19 | body.service_lookup / body.repository_* / body.first_match / body.query_construction / body.entity_construction / body.sequence_increment |
| **Atomic Primitives** | P20-P26 | atomic.rounding / atomic.unit_conversion / atomic.confirmed_plant_cd / atomic.edging / atomic.scm.productivity / atomic.validators / atomic.safety.absolute_max |
| **Metadata** | P27 | action.metadata.tiebreaker / action.metadata.fallback_kind |

---

## 3. Reusability test — system-agnostic 인 카드는 몇 개?

3 reference systems (v2 / Broadleaf / Banking, ADR-011) 적용 시 reuse 가능성 평가:

| Pattern | 의미 | System-agnostic? | 이유 |
|---|---|---|---|
| P01 body.compute | 산술 식 계산 (BigDecimal) | ✓ | 일반 산술. 모든 도메인 |
| P02 body.set_output | output field 할당 | ✓ | 일반 setter |
| P03 body.dg_throw | domain exception throw | ✓ | 일반 (exception class 만 plugin-specific) |
| P04 body.return | 메서드 return | ✓ | 일반 |
| P05 body.return_factory | Factory pattern | ✓ | 일반 |
| P06 body.return_default | default fallback return | ✓ | 일반 |
| P07 body.branch | if-else | ✓ | 일반 |
| P08 body.loop | for/while | ✓ | 일반 |
| P09 body.orchestration | aa_loop / save_invoke / phase1_validate | △ | slab manufacturing 의 design loop 의도 — "aa_loop" 어휘 자체가 specific |
| P10 body.delegate | 메서드 위임 | ✓ | 일반 |
| P11 body.aggregate_skipped | skipped value aggregation | △ | slab manufacturing 의 skipped-step 개념 specific |
| P12 body.service_lookup | Spring service 호출 | ✓ | 일반 (Spring DI) |
| P13 body.repository_call | JPA repository | ✓ | 일반 (JPA) |
| P14 body.repository_query | JPQL / Criteria | ✓ | 일반 |
| P15 body.repository_save | persist / save | ✓ | 일반 |
| P16 body.first_match | 첫 match return | ✓ | 일반 |
| P17 body.query_construction | dynamic query 작성 | ✓ | 일반 |
| P18 body.entity_construction | new Entity() | ✓ | 일반 |
| P19 body.sequence_increment | sequence next value | ✓ | 일반 |
| **P20** atomic.rounding | ceiling / floor / ceiling_10mm | ✗ | slab 의 10mm 단위 rounding 등 — domain rule |
| **P21** atomic.unit_conversion | factor | ✗ | slab 의 mm ↔ m, kg ↔ ton 등 — domain unit |
| **P22** atomic.confirmed_plant_cd | invalid_check / activation_check / hr_position | ✗ | **8-position string format** — slab plant code 의 specific structure |
| **P23** atomic.edging | exact_match / wildcard_fallback | ✗ | slab edging rule — domain rule |
| **P24** atomic.scm.productivity | 6 atomic 변형 | ✗ | slab supply chain productivity — domain |
| **P25** atomic.validators | 8 atomic 변형 | ✗ | slab order / pkg_wgt / design_pend_qty 등 — domain |
| **P26** atomic.safety.absolute_max | absolute_max | ✗ | slab safety constraint — domain |
| P27 action.metadata | tiebreaker / fallback_kind | △ | dispatch metadata generic 한 측면 + v2 의 specific policy 동시 |

요약:
- **17 cards (63%)** system-agnostic 후보 (P01-P08, P10, P12-P19)
- **7 cards (26%)** slab-specific domain primitive (P20-P26)
- **3 cards (11%)** mixed/marginal (P09, P11, P27)

**즉 27 cards 중 약 63% 만 generic emitter 로 흡수 가능, 나머지 37% 는 v2 plugin 의 emitter override.**

---

## 4. Over-engineering 의 구체적 양상

### 4.1 Sub-slot 의 over-categorization

여러 카드가 다중 sub-slot 을 한 카드로 묶음:
- P04: `body.return`, `body.return_aggregate`
- P07: `body.branch`, `body.fallback`, `body.fallback_strategy`
- P15: `body.repository_save`, `body.persist`
- P18: `body.entity_construction`, `body.snapshot_serialization`, `body.slab_null_marker`, `body.error_code_propagation`

이런 합집합이 자연스러우면 — sub-slot 자체가 over-classification. 새 framework 의 8 dispatch_kind (ADR-006) 는 anchor 의 emit 형태로 분류, sub-slot pleonasm 없음.

### 4.2 Slab-specific atomic 의 catalog 화

P20-P26 의 atomic 카드 21개가 **slab manufacturing 의 비즈니스 룰**:
- `atomic.confirmed_plant_cd.*` (P22) — 8-position string format (POS_SM, POS_HR, ...)
- `atomic.edging.*` (P23) — exact match 후 wildcard fallback
- `atomic.scm.productivity.default` (P24) — supply chain productivity default 값
- `atomic.safety.absolute_max` (P26) — slab manufacturing safety constraint

이들은 emitter 가 아니라 **business rule** 임. Plugin 의 `backend/sim_v2/plugins/v2-slab-design/aspects/business_rules.py` 또는 `backend/sim_v2/plugins/v2-slab-design/atoms/` 에 흡수 자연.

### 4.3 사람용 가이드의 visual mirror

README §1.3 인용:

> Use the Canonical Python block as the template, substituting locals (variable names, FQNs, error codes).

즉 카드 = **사람이 베끼는 reference**. ADR-001 ("Python 사람이 편집 X") 와 직접 모순. Phase α 의 audience 가 "사람 (Section 3 작업자)" 이었기 때문 — Round 2 의 결정 (ADR-001 채택) 후 카드의 의미가 사라짐.

### 4.4 카드 작성 비용 vs 검증 부재

카드 27장 × ~30 LOC = ~800 LOC of detailed code template + Java reference + anti-patterns + trace contract.
검증 (anchor-gaps E-1): smoke test 가 없어 idiom × runtime contract 의 정합성 검증되지 않음 — 5건 mismatch (Lesson 1) silent.

작업 비중이 카드 작성에 편중, 통합 검증에 0. 비대칭.

---

## 5. 왜 발생했나 — process 적 분석

1. **ADR-001 (Python = Java twin, 사람 편집 X) 결정 시점이 카드 27장 작성 후.** Phase α 의 audience 가 "사람 (Section 3 작업자)" 라는 가정 하에 카드 시작 → 후속 결정으로 audience invalidated.
2. **Plugin scope 의 first-class decision 부재.** "이 카드는 framework core 인가 plugin 인가" 의 판단 mechanism 없음 → 모두 한 디렉토리.
3. **Anchor coverage 100% 목표가 over-fit 유발.** "140 / 140 anchor 매핑" 의 목표 가 atomic.* slab-specific 까지 catalog 화로 이끌림. Reusability 가 metric 에 없음.
4. **Edge case taxonomy (00-edge-cases.md) 의 적정 abstraction level 부재.** 10 case 중 일부는 generic (e.g., null handling), 일부는 slab-specific.

---

## 6. 새 framework 의 적용

### 6.1 Plugin scope 의 first-class decision

ADR-002 의 plugin contract 에서 27 cards 의 적용 위치 매핑:

| Tier | 위치 | 27 cards 중 흡수 |
|---|---|---|
| Framework core | `backend/sim_v2/core/synthesizer/emitters/` 8 dispatch_kind (ADR-006) | P01-P08, P10, P12-P19 의 generic 부분 (~17 cards) |
| Plugin emitter override | `backend/sim_v2/plugins/v2-slab-design/emitters/` | atomic.* 의 일부 (P09, P11 marginal 포함) |
| Plugin atomic / aspect | `backend/sim_v2/plugins/v2-slab-design/atoms/` 또는 `aspects/business_rules.py` | P20-P26 의 7 slab-specific 비즈니스 룰 |
| Plugin dispatch metadata | `backend/sim_v2/plugins/v2-slab-design/aspects/dispatch_metadata.py` | P27 |

### 6.2 Reusability metric 의 plugin contract 의무화

새 framework 의 plugin 작성 시:
- 각 emitter override 가 다른 plugin 의 reusable potential 추정 필요
- Reusability > 50% → core promotion 후보 (ADR-013 §6.3 Phase 3)
- Reusability < 30% → plugin-local 확정

이 metric 이 ADR-013 의 promotion path 의 가이드.

### 6.3 사람용 reference 의 분리

Plugin 의 emitter 가 코드. 사람용 reference 가 필요하면 별도 `backend/sim_v2/plugins/<sys>/docs/emitter-spec.md` 에 작성, machine-executable spec 과 분리.

---

## 7. 학습 정수

1. **Plugin scope 결정은 first-class artifact.** Plugin 의 emitter 와 framework core 의 emitter boundary 는 명시적. 27 cards 의 분류 자체가 scope 결정 미실행의 결과.
2. **사람용 가이드와 machine spec 은 별개 artifact.** Audience 가 다르면 contract 도 다름.
3. **Anchor coverage 100% 는 reusability 의 보장 아님.** Coverage metric 외에 reusability metric 동시 추적 필요.
4. **Audience 결정의 timing.** ADR-001 (audience = machine) 결정이 카드 작성 시작 전 결정되었으면, 카드 자체 작성 무산. Process 적으로 ADR 결정의 우선순위.

---

## 8. 새 framework 의 적용 요약

| 영역 | 적용 항목 |
|---|---|
| `backend/sim_v2/core/synthesizer/emitters/` | 8 dispatch_kind generic emitter (ADR-006) — 17 cards 흡수 |
| `backend/sim_v2/plugins/v2-slab-design/emitters/` | atomic.* 의 일부 + P09/P11 marginal |
| `backend/sim_v2/plugins/v2-slab-design/atoms/` | P20-P26 의 7 slab 비즈니스 룰 |
| `backend/sim_v2/plugins/v2-slab-design/aspects/` | P27 의 dispatch metadata |
| Plugin manifest 의 `[extensions]` | system-specific emitter declaration |
| `backend/sim_v2/core/recommendation/anti_patterns/over_categorization.py` | "category 가 plugin 의 reusability 를 가리는 over-engineering" 의 anti-pattern entry |

---

## 9. 참조

- ADR-002 — Two-Engine + plugin (plugin contract source)
- ADR-006 — Polymorphic dispatch (8 dispatch_kind)
- ADR-013 — Extensibility (promotion path)
- ADR-010 — Phase α discard rationale (Lesson preservation)
- `idioms/README.md` — α2 의 작성 의도
- `idioms/00-edge-cases.md` — 10 fidelity-killer edge cases
- `anchor-gaps.md` — coverage 통계
