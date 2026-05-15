# Implementation Plan Session — Handoff

작성일: 2026-05-13
이전 세션: section4-verification / sim-redesign / spec session (2026-05-13)
다음 세션: implementation plan 작성 (별도, ~2-4h 예상)
다음 트리거: `/sim-redesign-resume` 또는 SESSION-RESUME 패턴
사용 skill: `superpowers:writing-plans`

---

## 0. TL;DR — 이 세션의 목표

Spec session 종료. **9 산출물 = framework 의 정식 spec + ADR + sprint plan**.

다음 = implementation plan 작성. `superpowers:writing-plans` skill 사용.

**도착지**: `implementation-plan.md` (sprint W1-W20 의 detailed task breakdown) + 3 sub-design doc (`BANKING-DESIGN.md`, `BROADLEAF-ONBOARDING.md`, `V2-MIGRATION.md`) 작성 → 사용자 review → implementation phase 시작.

---

## 1. Spec session 의 9 산출물 (모두 sim-redesign/ 폴더)

| # | File | LOC | 내용 |
|---|---|---|---|
| 1 | `spec.md` | ~500 | **Two-Engine Plugin Framework 정식 spec** (12 section) |
| 2 | `ADR-003-two-engine-substrate.md` | ~300 | Integrator + proposal lifecycle + revision pointer |
| 3 | `ADR-004-schema-layer.md` | ~250 | 5번째 ontology layer DDL + additive migration |
| 4 | `ADR-005-recommendation-llm-defenses.md` | ~350 | 4-layer defense |
| 5 | `ADR-010-phase-alpha-discard.md` | ~250 | D2 폐기 결정 + 5 lessons |
| 6 | `ADR-011-second-system-selection.md` | ~300 | 3 systems + G1-G4 gates |
| 7 | `ADR-012-llm-agnostic-recommendation.md` | ~250 | Claude/OpenAI/Gemini abstraction |
| 8 | `ADR-013-extensibility-architecture.md` | ~250 | Tier 1/2 + plugin extension |
| 9 | `MILESTONES-2track.md` | ~250 | Track A/B 16-20w sprint |

**기 ADR (선행)**: ADR-001 (Python twin) / ADR-002 (Two-Engine + plugin) / ADR-006~009 (4 meta-programming).

**확정된 12 결정**: `DECISIONS-CONFIRMED.md`.

---

## 2. Implementation plan session 의 작업 범위

### 2.1 산출물

| # | 파일 | 내용 | 추정 LOC |
|---|---|---|---|
| 1 | `implementation-plan.md` | W1-W20 의 detailed task breakdown (per-task acceptance criteria + dependency graph) | 800-1500 |
| 2 | `BANKING-DESIGN.md` | Banking 가상 system 의 entity model + Drools rule sample + BPMN definition + DDL | 400-700 |
| 3 | `BROADLEAF-ONBOARDING.md` | Broadleaf community 의 module scope + onboarding path + boundary | 200-400 |
| 4 | `V2-MIGRATION.md` | v2 의 Phase α → 새 plugin 재작성 절차 + git revision tag | 200-300 |
| 5 | `lessons/phase-alpha-{L1-L5}.md` | 5 lessons 정식 작성 (ADR-010 §학습 자산화) | 각 100-200 |

총 ~2-3k LOC of markdown.

### 2.2 Implementation plan 의 구조 (HANDOFF 추천)

```
implementation-plan.md
├── 0. TL;DR + spec reference
├── 1. Scope (16-20w sprint, 3 system, 9 산출물 reference)
├── 2. Track A — v2 verification (W1-W12)
│   ├── 2.1 Phase α 학습 자산 추출 (W1-W4)
│   │   └── L1-L5 작성의 task breakdown
│   ├── 2.2 새 v2 plugin 작성 (W3-W8)
│   │   └── 7 artifact 별 task + acceptance criteria
│   └── 2.3 UC1/UC2/UC3 풀 시연 (W6-W12)
│       └── per-UC test plan
├── 3. Track B — Framework generalization (W1-W20)
│   ├── 3.1 5-layer ontology + Schema Layer (W1-W4)
│   ├── 3.2 Integrator + Proposal lifecycle (W2-W6)
│   ├── 3.3 3 plugin 작성 병렬 (W4-W10)
│   ├── 3.4 Recommendation Engine (W8-W16)
│   └── 3.5 Extension architecture validation (W12-W20)
├── 4. Cross-validate gates (G1-G4) detail
│   ├── G1 (W10) — Framework core contract
│   ├── G2 (W14) — Meta-programming 4 영역
│   ├── G3 (W18) — Recommendation Engine
│   └── G4 (W20+) — Extension architecture
├── 5. Dependency graph (task → task)
├── 6. Acceptance criteria per task
├── 7. Sprint cadence (2-week)
└── 8. Risk register + contingency
```

### 2.3 Implementation plan session 의 첫 task

`writing-plans` skill 의 흐름:
1. **Scope agreement** — 사용자에게 implementation plan 의 boundary 확인
   - 본 plan = sprint W1-W20 의 detailed breakdown
   - Out: actual code (그건 implementation phase)
   - Out: 별도 sub-design doc (4 file 은 plan 안에서 reference, 자체 작성은 별도)
2. **Sub-design doc 우선순위** — 4 doc (BANKING / BROADLEAF / V2-MIGRATION / lessons) 중 어떤 걸 plan session 안에서 작성, 어떤 걸 implementation phase 로 위임
3. **Plan 작성** — 위 §2.2 구조로 작성
4. **Self-review + 사용자 review**
5. **Implementation phase 인계**

---

## 3. Spec session 의 명시적 제약 (변동 없음)

### 3.1 User requirements (R1-R5)
- R1: Ontology = simulation precondition
- R2: 시뮬 에이전트가 빈틈 자각
- R3: 동일 input → 동일 output
- R4: 동일 처리 과정 보장
- R5: 수정 전후 비교 분석

### 3.2 Architectural 제약 (확정)
- ADR-001 ~ ADR-013 (총 11 ADR + 4 = 15 ADR? No, ADR-001/002/003/004/005/006/007/008/009/010/011/012/013 = 13 ADR)
- 12 결정 (DECISIONS-CONFIRMED.md)
- 5-layer ontology (Code/Domain/Mapping/Simulation/Schema)
- 3 systems 완전 병렬 (v2 + Broadleaf + Banking)
- LLM-agnostic (Claude/OpenAI/Gemini)
- Extension first-class (M-D4)

### 3.3 No MVP (메모리 `feedback_simulation_design.md`)
- 풀 시연 보장. Implementation 부분 구현 / phase 미루기 X
- 단 SIGNATURE_LOCKED 의 명시 한계는 OK (M-D4 확인)

### 3.4 Cost commitment (D6, ADR-011)
- Total 650-1000h (3인 팀, 6-12 month)
- M1 (W4) gate 후 cost re-estimate 의무

---

## 4. 다음 세션의 첫 task (clear instruction)

```
1. cd /Users/donghae/workspace/ai/onTong
2. Read: toClaude/modeling/section4-verification/sim-redesign/HANDOFF-implementation-plan-session.md (이 파일)
3. Read: toClaude/modeling/section4-verification/sim-redesign/spec.md (framework spec)
4. Read: toClaude/modeling/section4-verification/sim-redesign/MILESTONES-2track.md (sprint 기본)
5. Invoke superpowers:writing-plans skill
6. 사용자에게: "spec session 완료. implementation plan 작성 시작합니다. 
   Plan scope 확인부터 시작할게요 — implementation-plan.md 안에서 어디까지 작성할까요?"
7. Plan 작성 → user review → implementation phase 인계
```

---

## 5. 워크스페이스 격리 주의사항 (CLAUDE.md 일관)

- 현 브랜치 `section4-verification` (main 미머지)
- 본 세션의 쓰기 영역: `toClaude/modeling/section4-verification/sim-redesign/` 만
- Section 2 본체 (`backend/modeling/`) 수정은 implementation phase 에서만
- 다른 modeling 세션이 frontend/ 작업 중일 수 있음 — git status 로 확인

---

## 6. 참고: spec session 진행 요약

| 단계 | 결과 |
|---|---|
| Step 0 — Handoff + DECISIONS 읽기 | HANDOFF-spec-session.md + DECISIONS-CONFIRMED.md |
| Step 1 — 2nd system 선정 인터뷰 | Hybrid (v2 + Broadleaf community + Banking 가상) + 완전 병렬 + Banking 복잡 scope |
| Step 2 — ADR-011 작성 | 3 systems + G1-G4 gates + cost 650-1000h |
| Step 3 — ADR-010 작성 | Phase α 폐기 + 5 lessons |
| Step 4 — ADR-012 작성 | LLM-agnostic abstraction |
| Step 5 — ADR-013 작성 | Extensibility (Tier 1/2) |
| Step 6 — ADR-003 작성 | Integrator + proposal lifecycle |
| Step 7 — ADR-004 작성 | Schema Layer DDL |
| Step 8 — ADR-005 작성 | 4-layer defense |
| Step 9 — spec.md 작성 | 12 section, all ADR cross-reference |
| Step 10 — MILESTONES-2track.md | Track A/B 16-20w sprint |
| Step 11 — Self-review | Placeholder 0, 13 ADR cross-reference, 12 결정 cover |
| Step 12 — 사용자 review + 승인 | (this) |

---

## 7. 참조

### 본 spec session 산출물
- 9 file (위 §1 table)

### 선행 ADR
- ADR-001 (Python twin), ADR-002 (Two-Engine + plugin)
- ADR-006/007/008/009 (4 meta-programming)

### 결정
- DECISIONS-CONFIRMED.md (12 결정)

### Brainstorming 산출물
- SYNTHESIS-ROUND2.html (Round 2 종합)
- META-PROGRAMMING.html (worked example)
- DESIGN-SYNTHESIS.html / DESIGN-WALKTHROUGH.html (Round 1)
- Q1-trace-granularity.html (Round 0)

### 메모리
- `feedback_simulation_design.md` — no MVP, 풀 시연 필수
- `project_decisions_v4_action.md` — 4-layer + 7-case
- `project_sim_redesign_decisions.md` — 본 sim-redesign track 의 status (갱신 예정)
