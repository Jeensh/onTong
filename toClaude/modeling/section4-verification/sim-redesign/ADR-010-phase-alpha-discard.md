# ADR-010: Phase α 자산 폐기 결정과 학습 자산화

작성일: 2026-05-13
상태: 확정 (사용자 결정, 2026-05-13)
선행: ADR-001 (Python twin), ADR-002 (Two-Engine + plugin)
관련 결정: D2 (v2 자산 폐기), M-D3 (병행)

## 컨텍스트

Phase α (Section 4 verification, 2026-04-25 ~ 5-12) 의 산출물:
- 27 idiom card (`idioms/P*.md`) — Java → Python 변환 가이드, 사람용
- 5 facade class (slab-specific runtime stubs)
- 5 golden fixture S1-S5 (input → expected output)
- `backend/modeling/sim_verify/runtime/` (slab-specific runtime)
- KNOWN_DIVERGENCE 분석 (BigDecimal / MathContext / RoundingMode / SdConstants / ValidationResult 5종 API 미스매치)

총 ~50h 작업물.

ADR-001 (Python twin) 의 결정 후, ADR-002 (system-agnostic + plugin) 추가 후, v2 자산의 운명 결정:
- 추천 (`SYNTHESIS-ROUND2.html`): plugins/slab-design/ 으로 흡수
- D2 결정 (`DECISIONS-CONFIRMED.md`): **폐기** (추천 X, non-default)

이유:
- D3 (실제 2nd system) 와 결합 시 framework 의 v2-specifics-free 검증력 ↑
- 27 카드의 "사람용 변환 가이드" 성격이 ADR-001 의 "Python 사람이 편집 X" 와 모순
- 5 facade 의 slab-specific 가 framework 의 generic contract 와 충돌

## 결정

**Phase α 의 산출물 자체는 plugin 으로 흡수하지 않는다. Round 2 mechanism 을 v2 specifics 없이 처음부터 작성.**

다만 ~50h 작업의 **학습 자산** (lessons learned, root cause analysis, anti-patterns) 은 보존하여 새 framework 작성 시 reference.

## 폐기 대상 (Discarded)

| 산출물 | 폐기 사유 | 후속 처리 |
|---|---|---|
| 27 idiom card (`idioms/P1.md` ~ `P*.md`) | "사람용 변환 가이드" 성격이 ADR-001 의 "Python 사람 X 편집" 와 모순. 합성기 internal registry 또는 LLM prompt 의 input 으로만 elevated 가능 — but selectively, not in bulk | Reference only. 새 plugin 의 emitter 작성 시 selectively port |
| 5 facade class (Phase α specific runtime) | Slab-specific. Framework 의 generic Java contract (`core/contracts/base.py`) 와 redundancy + conflict | 폐기. 새 v2 plugin 작성 시 `plugins/v2-slab-design/contracts/` 처음부터 작성 |
| 5 golden fixture S1-S5 | Slab manufacturing 의 hand-crafted edge case. Framework 의 fixture format 결정 후 동등 의도의 fixture 재작성 | 폐기. 새 fixture 작성 시 의도만 유지 (BigDecimal precision, async batching 등) |
| Slab-specific runtime (`backend/modeling/sim_verify/runtime/`) | Slab manufacturing logic 의 reverse-engineered Python — Java twin 의 자동 합성 가 아닌 손 작업물 | 폐기. 새 framework 는 ADR-001 의 deterministic synthesis 로 대체 |
| `scripts/section4_oracle_diff.py` | Slab-specific oracle diff 도구. Framework 의 generic verification 으로 대체 | 폐기. 새 framework 의 `core/verification/oracle_diff.py` 로 generic 화 |

## 학습 자산화 (Preserved as lessons)

다음 항목은 `lessons/phase-alpha-{topic}.md` 로 추출, 새 framework 작성 시 reference:

| Lesson | 내용 | 새 framework 의 어디서 활용 |
|---|---|---|
| L1: KNOWN_DIVERGENCE root cause | BigDecimal / MathContext 등 5종 API 미스매치의 근본 원인 분석. Python decimal 의 ROUND_HALF_UP 과 Java RoundingMode.HALF_UP 의 silent difference 등 | ADR-005 의 Recommendation Engine 의 "anti-pattern detection" + framework 의 numeric precision contract |
| L2: 27 카드의 over-engineering | "사람용" idiom card 가 ADR-001 결정 후 무의미. Why 27 cards weren't reusable across systems — 분류 자체가 v2 specifics 에 over-fit | ADR-002 의 plugin scope 결정 + system-agnostic 의 의미 명확화 |
| L3: Hand-crafted twin 의 한계 | Phase α 의 manual rewrite 에서 missed correctness case 다수 — automation 의 필요성 입증 | ADR-001 의 deterministic synthesis 정당화. Manual 의 silent drift risk 명시 |
| L4: 5 facade 의 abstraction failure | Slab-specific facade 가 다른 도메인 system 에 reusable 아님 — generic Java contract 의 필요성 입증 | ADR-002 의 plugin contract design 정당화 |
| L5: Fixture-driven verification 의 적합성 | S1-S5 가 R5 (수정 전후 비교) 의 유효 mechanism 입증 | Framework 의 fixture format 의 핵심 design |

## 처리 절차

```
1. spec session (현)
   - 본 ADR 작성
   - 5 lessons 추출 (lessons/phase-alpha-*.md) — implementation plan session 으로 위임

2. Implementation plan session (다음)
   - v2 plugin 의 처음부터 작성 절차 명시
   - Phase α 산출물의 git revision tag (`phase-alpha-snapshot`) 생성
   - 새 작성 후 비교 verification (regression check)

3. Implementation phase (이후)
   - 새 v2 plugin 작성 → 동등 fixture (S1'-S5') 작성 → 동등 결과 확인
   - 완료 후 phase-alpha-snapshot tag 의 산출물은 archive
```

## v2 새 plugin 의 boundary

새 v2 plugin (`plugins/v2-slab-design/`) 의 7 artifact (ADR-002 의 plugin contract):

| Artifact | 작성 방식 |
|---|---|
| `contracts/base.py` | Framework 의 generic Java contract (`core/contracts/base.py`) 를 상속 + slab-domain override |
| `entities/` | Java AST 로부터 자동 추출 — Phase α 의 hand-crafted Python entity 재사용 X |
| `mappings/` | Section 2 ontology table 에서 자동 생성 |
| `emitters/` | Round 2 의 8 dispatch_kind emitter (ADR-006) — generic |
| `fixtures/` | 새로 작성. 의도는 S1-S5 와 동등 (BigDecimal 정밀도, async batching 등) |
| `aspects/` | Phase α 단계엔 없었던 항목 — @Aspect handler (ADR-008) |
| `manifest.toml` | Plugin metadata (model_version, LLM_provider, etc.) |

## 결과 / 영향

- Framework 의 "처음부터 generic" 보장 — v2 specifics leak 차단
- Phase α 의 ~50h 가 lessons 형태로 보존됨 — sunk cost mitigation
- 새 v2 plugin 의 cost 100-200h 추가 (ADR-011 에 반영)
- 사용자 메모리 `feedback_simulation_design.md` ("풀 시연") 와 일관 — partial reuse 안 함

## 미해결 — 다음 단계로 위임

- Lesson markdown 5개 (L1-L5) 의 정식 작성: implementation plan session 안에서 별도 file `lessons/phase-alpha-*.md`
- Phase α git revision tag 의 정확한 commit hash: implementation plan session
- 새 v2 plugin 의 작성 절차 detail: implementation plan session

## 참조

- DECISIONS-CONFIRMED.md (D2)
- ADR-001 (Python twin)
- ADR-002 (system-agnostic)
- ADR-011 (sibling — 3 systems 의 v2 처리 명시)
- `toClaude/modeling/section4-verification/anchor-gaps.md` (Gap A-F)
- `toClaude/modeling/section4-verification/source-code-fixes-pending.md`
- `toClaude/modeling/section4-verification/idioms/P*.md` (폐기 대상, reference only)
