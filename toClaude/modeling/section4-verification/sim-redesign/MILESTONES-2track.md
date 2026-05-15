# MILESTONES — 2-Track Sprint Plan (M-D3 병행)

작성일: 2026-05-13
상태: 확정 (spec session)
관련 결정: M-D3 (병행), D3 (3 systems), D6 (cost 수용)
관련 ADR: ADR-011 (3 systems), ADR-013 (extension)

---

## 0. 개요

M-D3 결정 (`DECISIONS-CONFIRMED.md`):
> **일반화 병행** — 2 track work — v2 verification + framework generalization 동시 진행. v2 가 첫 plugin 으로 자연 처리되면서 framework 자체가 발전. 두 track 이 cross-validate.

본 문서는 두 track 의 sprint plan + cross-validate gate (G1-G4) 의 timing detail.

**총 duration**: 16-20 week (4-5 month) + buffer = **6-12 month** (3인 팀)
**총 cost**: 650-1000h (ADR-011)

---

## 1. Track A — v2 verification

D2 폐기 결정 (ADR-010) 후, Phase α 자산은 학습 자산만 reference. 새 plugin 처음부터 작성.

### Phase A1 (W1-W4) — Phase α 학습 자산 추출

| Week | Task | 산출물 |
|---|---|---|
| W1 | Phase α git revision tag 생성 (`phase-alpha-snapshot`) | git tag |
| W1-W2 | L1 작성 (KNOWN_DIVERGENCE root cause) | `lessons/phase-alpha-known-divergence.md` |
| W2 | L2 작성 (27 카드 over-engineering) | `lessons/phase-alpha-idiom-cards.md` |
| W3 | L3 작성 (hand-crafted twin 한계) | `lessons/phase-alpha-manual-twin.md` |
| W3 | L4 작성 (5 facade abstraction failure) | `lessons/phase-alpha-facade.md` |
| W4 | L5 작성 (fixture-driven verification 적합성) | `lessons/phase-alpha-fixture.md` |

산출: 5 lessons markdown. 새 framework 작성 시 reference. **Phase α 산출물 archive**.

### Phase A2 (W3-W8) — 새 v2 plugin 작성

(Track A1 과 일부 overlap — L4/L5 완료 후 시작)

| Week | Task | 산출물 |
|---|---|---|
| W3-W4 | `plugins/v2-slab-design/manifest.toml` + `contracts/base.py` | Plugin scaffold |
| W4-W5 | `entities/` 자동 추출 (Java AST → Python entity) | v2 entity model |
| W5-W6 | `mappings/` ontology import | Code↔Domain mapping |
| W6-W7 | `fixtures/` 새 작성 (S1-S5 와 동등 의도, 새 format) | 5 fixture |
| W7-W8 | `aspects/` (v2 단계엔 없었던 항목) | Aspect handler (minimal) |

산출: 새 v2 plugin (7 artifact). **G1 gate** (W8) 대비 완료.

### Phase A3 (W6-W12) — v2 UC1/UC2/UC3 풀 시연

| Week | Task | 산출물 |
|---|---|---|
| W6-W8 | UC1 (풀 시연) — S1' fixture 1건 | UC1 결과 (R3 보장) |
| W8-W10 | UC2 (영향 분석) — S2' input 변경 → trace diff | UC2 결과 (R4 검증) |
| W10-W12 | UC3 (R5 수정 전후) — Java 수정 후 두 Python 비교 | UC3 결과 (R5 검증) |

산출: v2 의 3 use case full demo. 사용자 메모리 "no MVP, 풀 시연 필수" 일관.

---

## 2. Track B — Framework generalization

### Phase B1 (W1-W4) — Core 5-layer ontology + Schema Layer

| Week | Task | 산출물 |
|---|---|---|
| W1 | `core/ontology/` schema_*.py model | Schema entity 정의 |
| W1-W2 | Migration script (8 table 추가, additive) | `migrations/v5_schema_layer.sql` |
| W2-W3 | `schema_extractor` extension point (ADR-013) | Plugin interface |
| W3-W4 | Cross-layer query API (UC4 prep) | `core/ontology/query.py` |

산출: 5-layer ontology infrastructure. ADR-004 implementation.

### Phase B2 (W2-W6) — Integrator + Proposal lifecycle

| Week | Task | 산출물 |
|---|---|---|
| W2-W3 | `core/integrator/proposal.py` (data model + state machine) | Proposal lifecycle |
| W3-W4 | `core/integrator/integrator.py` (8 method API) | Integrator |
| W4-W5 | Revision pointer + lineage | Revision model |
| W5-W6 | Oracle protocol (`core/verification/oracle.py`) | Oracle Request/Response |

산출: Two-engine substrate. ADR-003 implementation.

### Phase B3 (W4-W10) — 3 plugin 작성 병렬

(Track A2 의 v2 plugin 과 cross-validate.)

| Week | v2 | Broadleaf | Banking |
|---|---|---|---|
| W4-W6 | (Track A2 와 동일) | Codebase 학습 + manifest scaffold | 도메인 설계 (BANKING-DESIGN.md) |
| W6-W8 | UC1 풀 시연 (Track A3) | 7 artifact scaffolding | DDL 작성 + JPA entity |
| W8-W10 | UC2 영향 분석 | core + cart + order 모듈 entity | Drools rule + BPMN 작성 |

산출: 3 plugin 의 G1 gate 통과 (W10). 

### Phase B4 (W8-W16) — Recommendation Engine

| Week | Task | 산출물 |
|---|---|---|
| W8-W10 | `core/recommendation/llm_provider.py` (Protocol) + 3 provider impl | LLM-agnostic abstraction (ADR-012) |
| W10-W12 | Defense Layer 1 (context grounding) | Pre-call defense |
| W11-W13 | Defense Layer 2 (output validation) | Post-call validation |
| W12-W14 | Defense Layer 3 (oracle integration with B2) | Runtime defense |
| W13-W15 | Defense Layer 4 (review UI scaffold) | Human review gate |
| W14-W16 | Anti-pattern catalog (5 from Phase α lessons) | `core/recommendation/anti_patterns/` |

산출: Recommendation Engine MVP. ADR-005 + ADR-012 implementation.

### Phase B5 (W12-W20) — Extension architecture validation

| Week | Task | 산출물 |
|---|---|---|
| W12-W14 | Banking Drools dispatcher extension | `plugins/banking/dispatchers/drools_kbase_lookup.py` |
| W14-W16 | Banking @Compensable + @TenantContext extensions | `plugins/banking/annotations/`, `aop/` |
| W14-W17 | Broadleaf @Configurable + dynamic_field extensions | `plugins/broadleaf/aop/`, `extensions/` |
| W17-W20 | Extension promotion path test (몇 개 동일 extension → core promotion 시뮬) | `core/synthesizer/` 의 dispatch_kind 추가 |

산출: Extension architecture validation. ADR-013 의 G4 gate 통과.

---

## 3. Cross-validate Gates (G1-G4)

### G1 — Framework core contract (W10 — Month 1+)

조건:
- 3 system 각 UC1 (풀 시연) 1건 성공
- 3 plugin 의 7 artifact 모두 작성됨
- R3 (동일 input → 동일 output) 보장 확인

산출 review:
- `g1_report.md` — 3 system × UC1 결과 표
- Plugin contract 의 strict 정도 점검 — v2-specific leak 가 있는지

후속: G1 fail 시 plugin contract 수정 + W11-W12 추가 sprint.

### G2 — Meta-programming 4 영역 coverage (W14 — Month 2+)

조건:
- ADR-006 (polymorphic): 8 dispatch_kind 각 system 등장 빈도
- ADR-007 (annotation): Lombok / custom processor 각 system 처리
- ADR-008 (AOP): @Aspect weaving 각 system 처리
- ADR-009 (bytecode): CGLib / custom plugin 각 system 처리

산출 review:
- `g2_report.md` — 3 system × 4 영역 매트릭스
- Unsupported case → SIGNATURE_LOCKED 발동 위치 list

후속: G2 fail (unsupported case 너무 많음) 시 extension 작성 우선순위 재조정.

### G3 — Recommendation Engine (W18 — Month 3+)

조건:
- 3 system 모두에서 LLM 의 reasonable proposal 생성
- Recommendation Engine 의 4 defense mechanism 작동
- LLM provider 최소 2개 (Claude + GPT) 에서 동등 quality

산출 review:
- `g3_report.md` — 3 system × 2+ provider 매트릭스
- Proposal quality 평가 (manual review)

후속: G3 fail (특정 provider quality 낮음) 시 `allowed_providers` 조정.

### G4 — Extension architecture (W20+, Month 4+)

조건:
- Banking Drools integration 이 plugin extension 으로 흡수
- Broadleaf enterprise-specific case 가 SIGNATURE_LOCKED + extension path 처리
- 새 meta-programming case 추가 시 framework 자체 변경 X

산출 review:
- `g4_report.md` — Extension 등록 case + framework core 변경 없음 확인
- Promotion path 시뮬 (몇 개 plugin 공통 extension → core 흡수)

후속: G4 fail (framework core 변경 발생) 시 ADR-013 의 contract 재검토.

---

## 4. Risk + Contingency

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Cost spike (Total 1000h+ over) | Medium | High | M1 (W4) gate 후 cost re-estimate. 1 plugin reduce 검토 |
| 3-way churn (conflicting signal) | Medium | High | Plugin contract strict from day 1. G1-G2 빈도 ↑ |
| Banking 가상 → real-world 검증력 약함 | Medium | Medium | Drools/BPMN/multi-tenant 의도 포함으로 보완. Broadleaf 가 real-world 보완 |
| Broadleaf enterprise-only feature 결손 | Low | Low | Community edition 한정. SIGNATURE_LOCKED + extension path |
| 1 system 만 stuck → 전체 지연 | Medium | Medium | Per-system independent track. Stuck system 은 partial onboarding |
| Provider API 변경 (Claude/GPT) | Low | Medium | Provider adapter test 의 isolated suite |
| Phase α lessons 추출 시 작업 underestimate | Low | Low | W1-W4 buffer 있음 |

---

## 5. Sprint cadence

- **2-week sprint** (Mon-Fri × 2)
- **Sprint planning**: 매 sprint 시작 월요일 30min
- **Sprint review + retro**: 매 sprint 종료 금요일 60min
- **G-gate review**: 매 gate 직후 dedicated session (90min)

산출물 storage:
- Track A: `toClaude/modeling/section4-verification/sim-redesign/track-a/`
- Track B: `toClaude/modeling/section4-verification/sim-redesign/track-b/`
- Gate reports: `toClaude/modeling/section4-verification/sim-redesign/gates/g{1-4}_report.md`

---

## 6. Out of scope (Phase 2)

- Cross-plugin proposal saga (ADR-003)
- UC5 (Code Recommender) / UC6 (Ontology Evolver) 의 full implementation
- NoSQL schema layer
- Cost-aware / quality-aware LLM routing
- 4th+ reference system onboarding
- Production-grade DB migration tool integration

---

## 7. 참조

- ADR-011 (3 systems + G1-G4 gates)
- ADR-013 (Extension architecture, G4 의 검증 대상)
- ADR-010 (Phase α discard, Track A1 의 source)
- ADR-003 (Integrator, Track B2 의 산출물)
- ADR-004 (Schema Layer, Track B1)
- ADR-005, ADR-012 (Recommendation Engine, Track B4)
- DECISIONS-CONFIRMED.md (M-D3)
- spec.md (전체 framework spec)
