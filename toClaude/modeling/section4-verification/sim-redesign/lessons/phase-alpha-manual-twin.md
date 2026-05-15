# Phase α Lesson 3 — Hand-crafted Twin 의 한계와 Automation 의 필요성

작성일: 2026-05-13 (implementation plan session)
대상: Phase α `backend/modeling/sim_verify/runtime/` (4 hand-written substrate modules)
관련 ADR: ADR-001 (Python twin), ADR-010 (Phase α discard)
Phase α 산출물 reference:
- commit `5642a57 feat(sec4/runtime): slab_design_runtime Python substrate (bigdecimal/exception/plant_cd/lookup)`
- `backend/modeling/sim_verify/runtime/bigdecimal.py` / `algorithm_exception.py` / `confirmed_plant_cd.py` / `lookup_source.py`

---

## 1. 사실 — Phase α 의 hand-crafted substrate

Phase α 의 substrate 는 4 module 의 hand-written Python:

| Module | LOC (추정) | 역할 | 도메인 |
|---|---|---|---|
| `bigdecimal.py` | ~250 | Java BigDecimal + MathContext.DECIMAL64 + RoundingMode 의 method-level equivalent | numeric (semi-generic) |
| `algorithm_exception.py` | ~50 | slab algorithm 의 `AlgorithmException` (step_no / step_name / error_code) | slab-specific |
| `confirmed_plant_cd.py` | ~80 | slab plant code 의 8-position string helpers (POS_SM, POS_HR, ...) | slab-specific |
| `lookup_source.py` | ~120 | Spring `findById` / derived-query emulator | slab-domain (entity-tied) |

총 ~500 LOC of manual rewrite.

ADR-010 의 "5 facade class" 표현은 4 substrate module + `SdDesigner` orchestrator 추정 합산. 본 lesson 은 실제 작성된 4 module 기준.

---

## 2. Hand-crafted 의 silent drift 사례

### 2.1 negative scale 의 silent rejection (anchor-gaps Gap E-3)

`bigdecimal.py` 의 `bd_set_scale` 이 `scale >= 0` 만 허용:

```python
def bd_set_scale(value: Decimal, scale: int, rounding=...) -> Decimal:
    if scale < 0:
        raise NotImplementedError("negative scale not implemented")
    # ...
```

Java 원본의 `BigDecimal.setScale(-3, HALF_EVEN)` 은 1000 단위 절사에 합법. v2 코드는 negative scale 미사용이라 silent — 다른 도메인 적용 시 발현.

### 2.2 21-step cumulative drift (anchor-gaps Gap E-2)

`scripts/section4_oracle_diff.py` 가 `abs_tol=1e-6, rel_tol=1e-9` hardcode. SdDesigner 의 21-step algorithm loop (특히 a-a loop split fallback) 에서 BigDecimal HALF_EVEN rounding 의 last-digit 흔들림이 누적될 가능성. Phase α 종료 시 실측 측정 부재 — Phase β 의 첫 Python 구현 시점에야 발현 예상.

### 2.3 Idiom × runtime contract drift (anchor-gaps Gap E-1, Lesson 1)

5 API mismatch (BigDecimal / MathContext / RoundingMode / SdConstants / ValidationResult) — 자세한 분석은 Lesson 1. 본 lesson 의 framing: **이 mismatch 자체가 hand-crafted 의 silent drift 의 sub-instance**.

### 2.4 type_realization 14건 unconfirmed (anchor-gaps Gap C)

`auto, conf=0.5-0.7` 의 14 type_realization 미확정. Hand-crafted twin 의 `lookup_source.py` 가 어느 BusinessTerm 과 매핑되는지 사람 review 필요. Automation 이라면 ontology mapping 의 confidence threshold 자동 enforce.

---

## 3. Missed correctness cases — automation 이 잡았을 사례

### 3.1 SdDesigner.AlgorithmStep abstract dispatch (anchor-gaps Gap A)

`action.scm.run` 의 realization 이 `SdDesigner.AlgorithmStep.run(...)` — **추상 메서드**. 21 step 인스턴스가 각자 override. Hand-crafted twin 은 이 polymorphic dispatch 의 21 구체 타깃을 별도 탐색 필요.

ADR-006 (polymorphic dispatch) 의 `instanceof_guard` 또는 `subclass_dispatch` kind 가 자동 처리. Hand-crafted 는 manual chain.

### 3.2 SdDesigner.design orchestration anchor 0 (anchor-gaps Gap B-1)

`SdDesigner.design` 본문이 21-step 의 모든 알고리즘 진입점이지만 초기 anchor 0. 본 gap 은 2026-05-12 에 `scripts/add_v2_orchestration_anchors.py` 로 23 anchor 추가 처리됨 — but **그 script 자체가 hand-crafted authoring**. 새 framework 의 `backend/sim_v2/core/synthesizer/anchor_extractor.py` 자동 extraction 이 동등 mechanism.

### 3.3 Single-anchor slot 38건 (anchor-gaps Gap F)

상위 10 slot 이 anchor 78건 차지, 하위 38 slot 은 each 1 anchor. Single-anchor slot 의 Python 구현은 **참고 사례 1개** — cross-validation 부재. Hand-crafted twin 이 single-anchor slot 의 의미를 잘못 해석해도 detection 0.

Generated twin 은 Java AST 의 deterministic emission 으로 (anchor 의 의미 해석이 emitter 의 contract 안) 본 risk 없음.

---

## 4. Hand-crafted 의 비대칭 cost

| 작업 | 비중 | Phase α 의 실제 |
|---|---|---|
| Author substrate | 50h | 4 module (~500 LOC) |
| Validate substrate | 0h | smoke test 없음 (anchor-gaps E-1) |
| Re-validate on every Java change | manual / 누락 risk | "Phase α 산출물 재사용 여부" 불명 (anchor-gaps Day 7 checkpoint) |
| Track coverage | manual / report | anchor-gaps.md 작성 (수동) |

**비대칭 결과:**
- Authoring 은 visible cost
- Validation 은 invisible cost (drift 가 silent 까지 발현 미발생)
- Maintenance 는 latent cost (Java 변경 시 substrate 동기화 필요 — 누락 가능성 높음)

---

## 5. Automation 이 해결하는 것

ADR-001 의 deterministic synthesis 의 정당화:

### 5.1 Authoring cost 의 plugin scope 흡수

새 framework 의 substrate authoring:
- `backend/sim_v2/core/contracts/base.py` — generic Java contract (Spring/JPA/TX stub) — **한 번** 작성
- `backend/sim_v2/plugins/<sys>/contracts/` — system-specific override — 작은 delta
- `backend/sim_v2/core/synthesizer/emitters/` — generic emitter (8 dispatch_kind, ADR-006) — 한 번 작성
- `backend/sim_v2/plugins/<sys>/emitters/` — system-specific override

Hand-crafted 의 ~500 LOC × 3 system (v2/Broadleaf/Banking) ≈ 1500 LOC 의 manual substrate 가 **core 한 번 + plugin override delta** 로 대체.

### 5.2 Validation 의 contract 자동화

새 framework 의 contract validator (Lesson 1 §4.2):
- Emitter 가 emit 하는 symbol 이 plugin contract 안에 존재 확인
- Mismatch = compile time error (NameError 가 아닌 framework 의 ValidationError)
- Anti-pattern catalog (ADR-005) 자동 검사 — 5 KNOWN_DIVERGENCE 재발 차단

### 5.3 Regression 의 자동 re-emit

Java 변경 → ontology 갱신 → Python twin 자동 재생성 (ADR-001 의 핵심):
- Hand-crafted twin = Java 변경마다 manual sync, drift 누락 risk
- Generated twin = Java AST 변경 즉시 emitter 재실행, deterministic

R5 (수정 전후 비교, ADR-003 §5) 의 mechanism — revision pointer chain 이 hand-crafted 으로는 어려움 (매 revision 의 manual twin 재작성 cost), generated 에서는 자연.

### 5.4 Coverage tracking 의 metric 자동화

anchor-gaps.md 같은 보고서가 framework 의 native metric (Tier 1 emitter coverage / Tier 2 plugin coverage / R3-R5 verification level). 사람이 보고서 작성하지 않음.

---

## 6. 학습 정수

1. **Manual rewrite 의 silent drift 는 발현 비용 0, 검출 비용 高.** Phase α 의 5 API mismatch 가 이 패턴의 가장 작은 instance — runtime 의 simple drift 부터 21-step cumulative drift 까지 spectrum.
2. **Automation 의 정당화는 cost spike, not preference.** Hand-crafted = ~500 LOC × N system. Generated = framework + plugin delta. N >= 2 에서 차이 명백 (ADR-011 의 D6 cost 결정의 base).
3. **Regression mechanism 의 design 의무.** R5 (수정 전후 비교) 가 hand-crafted 으로 가능하나 expensive. Generated 에서 R5 = git revision tag + emitter rerun + diff.
4. **Coverage metric 의 native artifact.** 사람이 anchor-gaps.md 작성하지 않음 — framework 가 출력.

---

## 7. 새 framework 의 적용

| 영역 | 적용 항목 |
|---|---|
| `backend/sim_v2/core/synthesizer/` | Deterministic emitter (ADR-001) — hand-crafted substrate 의 자리 |
| `backend/sim_v2/core/contracts/base.py` | Generic Java contract (Spring/JPA/TX) — 4 module ↔ 1 base + plugin override |
| `backend/sim_v2/core/synthesizer/contract_validator.py` | Emitter 출력의 contract 검사 — silent drift 차단 |
| `backend/sim_v2/core/synthesizer/coverage_reporter.py` | anchor-gaps.md 같은 보고서의 framework native 생성 |
| `backend/sim_v2/core/integrator/revision.py` | Revision pointer chain — R5 의 mechanism (ADR-003) |
| `backend/sim_v2/core/recommendation/anti_patterns/` | 5 KNOWN_DIVERGENCE 의 anti-pattern catalog 등록 (Lesson 1 §4.3) |

---

## 8. 참조

- ADR-001 — Python = Java twin (deterministic synthesis 정당화)
- ADR-003 — Revision pointer (R5 mechanism)
- ADR-006 — Polymorphic dispatch
- ADR-010 — Phase α discard (manual substrate 의 폐기 결정)
- `anchor-gaps.md` — Gap A/B-1/C/E-1/E-2/E-3/F (모든 hand-crafted silent drift 사례의 catalog)
- `backend/modeling/sim_verify/runtime/bigdecimal.py` — α1 의 manual rewrite 실제 코드
- Lesson 1 (`phase-alpha-known-divergence.md`) — 5 API mismatch detail
