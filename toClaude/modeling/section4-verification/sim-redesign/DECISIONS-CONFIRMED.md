# Sim-Redesign 결정 — 확정 답변 (12 항목)

작성일: 2026-05-13
세션: section4-verification / sim-redesign brainstorming
사용자: jeensh (팀 리더, Section 2 담당)
다음 단계: spec 작성 세션 (별도)

## Part A — Round 2 Synthesis (D1-D7)

### D1. Two-Engine Plugin Framework 채택?
**선택**: 승인 (추천 옵션)
**의미**: core + plugins + Verification + Recommendation + Integrator + 5번째 Schema Layer 의 종합 architecture 채택.

### D2. v2 자산 (27 카드 + 5 facade + 5 fixture) 의 운명
**선택**: **폐기** (추천 X — 추천은 "plugins/slab-design/ 흡수")
**의미**:
- 27 idiom card → 폐기 (Phase α 산출물 reference only)
- 5 facade class → 폐기 (core/contracts/base.py 의 generic Java contract 로 재설계)
- 5 golden fixture (S1-S5) → 폐기 (새 fixture 작성 필요)
- Phase α 의 ~50시간 작업 = 학습 자산 (KNOWN_DIVERGENCE 의 root cause lesson 등). 단 산출물 자체는 plugin 으로 흡수 X
- Round 2 의 mechanism 을 v2 specifics 없이 처음부터 작성 — 진정한 system-agnostic 시도

### D3. 2nd reference system 명시 (system-agnostic 검증)
**선택**: **실제 2nd system 선정** (추천 X — 추천은 "bank-credit aspirational")
**의미**:
- Skeptic M1 "category error" 의 정면 해소
- spec 단계에서 실제 2nd system 선정 + onboarding 시작
- v2 + 실제 2nd system 동시 onboarding 으로 framework universality 검증
- D2 폐기 + D3 실제 system 조합 → "v2 의 우연성 제거" 의 강한 시그널
- **Spec session 의 첫 작업 = 2nd system 후보 검토 + 선정**

### D4. Schema Layer migration 시점
**선택**: spec 직후 즉시 (추천 옵션)
**의미**: Additive only — risk 낮음. Spec 이 schema-ready 상태로 출발.

### D5. Recommendation Engine 의 LLM 선택
**선택**: **LLM-agnostic (다중 지원)** (추천 X — 추천은 "Claude")
**의미**:
- Per-call LLM provider abstraction layer
- Manifest 확장: model_version 외 LLM_provider field 추가
- Prompt template 의 model-specific 회피 (예: Claude tool use 의 input_schema → 일반 JSON schema)
- 설계 복잡도 ↑, ecosystem flexibility ↑ — Claude / GPT / Gemini swap 가능
- 신규 ADR 필요 (spec session 에서 ADR-006 등 — meta-programming 과 별도)

### D6. Onboarding cost 50-400h per system 수용?
**선택**: 수용 (추천 옵션)
**의미**: Plugin scaffolding 만 reusable, curation dominant. 사용자에게 비용 명시.

### D7. 다음 세션 (별도) — spec + ADR-003~005 작성
**선택**: 이대로 진행 (추천 옵션)
**의미**: spec.md + ADR-003 (Two-Engine Substrate) + ADR-004 (Schema Layer) + ADR-005 (Recommendation Engine LLM defenses). 추가 ADR (D2 폐기 결정 / D3 system 선정 / D5 LLM-agnostic / M-D4 extensibility) 도 spec 안에 통합 또는 별도.

## Part B — Meta-Programming (M-D1 ~ M-D5)

### M-D1. 4 ADR (006-009) 채택 — meta-programming 처리
**선택**: 4 ADR 모두 채택 (추천 옵션)
**의미**: Polymorphic / Annotation / AOP / Bytecode 4 영역 mechanism 완전 명시.

### M-D2. Section 2 의 작업 시점
**선택**: spec 단계 통합 (추천 옵션)
**의미**: Section 2 의 추가 작업 항목 (CallSiteAnalyzer / Aspect extractor / 등) 을 spec 안에 포함.

### M-D3. v2 의 즉시 우선순위
**선택**: **일반화 병행** (추천 X — 추천은 "v2 verification 먼저")
**의미**:
- 2 track work — v2 verification + framework generalization 동시 진행
- v2 가 첫 plugin 으로 자연 처리되면서 framework 자체가 발전
- 두 track 이 cross-validate
- Resource 분산 risk 수용 (D6 와 일관)

### M-D4. Honest limits 의 명시적 수용
**선택**: **Other — 수용하되, 이런 기능은 지속 추가될 수 있으니, 확장가능한 형태로 설계 및 코딩 진행**
**의미**:
- Default: SIGNATURE_LOCKED for unsupported cases
- **Extension first-class**: plugins/<sys>/<extension-type>/ pattern 으로 새 case 추가
- Framework 변경 X, plugin 만 추가 → 새 meta-programming case 흡수
- 신규 ADR 필요 (Extension Architecture)

### M-D5. spec 작성 세션으로 인계 시점
**선택**: 지금 인계 (즉시) (추천 옵션)
**의미**: 본 결정 답변 시점 = spec session handoff.

## 5 non-default 결정의 종합 영향

| 결정 | Non-default 의미 | Spec session 에 미치는 영향 |
|---|---|---|
| D2 폐기 | v2 자산 → 학습 자산만 | Layer 1 registry 를 generic 으로 처음부터 |
| D3 실제 2nd system | system-agnostic 의 실제 falsifiable test | Spec 의 첫 task = 2nd system 선정. v2 + 2nd 동시 onboarding scope 명시 |
| D5 LLM-agnostic | 다중 LLM provider 지원 | LLM abstraction layer ADR 추가 (ADR-010 후보) |
| M-D3 일반화 병행 | 2 track 동시 진행 | Spec 의 milestone 이 v2 track + framework track 모두 cover |
| M-D4 확장가능 설계 | SIGNATURE_LOCKED + extension first-class | Extension Architecture ADR 추가 (ADR-011 후보) |

## Spec session 의 작업 범위 (확정)

1. **spec.md** — Two-Engine Plugin Framework 의 정식 spec 문서
2. **ADR-003** — Two-Engine Substrate (Integrator + proposal lifecycle + revision pointer)
3. **ADR-004** — Schema Layer (5번째 ontology DDL + migration plan)
4. **ADR-005** — Recommendation Engine LLM defenses (4 방어 + LLM-agnostic abstraction)
5. **ADR-010 (신규)** — Phase α discard rationale (D2 결정의 historical record)
6. **ADR-011 (신규)** — 2nd system selection criteria + onboarding plan (D3)
7. **ADR-012 (신규)** — LLM-agnostic Recommendation API (D5)
8. **ADR-013 (신규)** — Extensibility Architecture for meta-programming (M-D4)
9. **2 track milestone plan** (M-D3) — v2 verification + framework generalization 병행 sprint
10. **Cost estimate** (D6) — onboarding cost per system breakdown
