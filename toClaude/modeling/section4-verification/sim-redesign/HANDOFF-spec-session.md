# Sim-Redesign Spec 작성 세션 — Handoff

작성일: 2026-05-13
이전 세션: section4-verification / sim-redesign brainstorming (2026-05-12 ~ 5-13)
다음 세션: spec 작성 (별도, ~2-3h 예상)
다음 트리거: `/sim-redesign-spec-resume` (또는 SESSION-RESUME 패턴)

---

## 0. TL;DR — 이 세션의 목표

Brainstorming 종료. Two-Engine Plugin Framework 의 정식 **spec 문서 + 4-7개 ADR 작성**.

12 결정 모두 확정 (`DECISIONS-CONFIRMED.md`). 5개 non-default 결정의 implication 이 spec 의 형태를 결정:
- D2 폐기 → Phase α v2 자산 reference only, mechanism 처음부터
- D3 실제 2nd system → spec 첫 작업 = 2nd system 선정
- D5 LLM-agnostic → multi-LLM abstraction layer
- M-D3 병행 → 2 track milestone
- M-D4 확장 → extension architecture first-class

**도착지**: spec.md + ADR-003 ~ ADR-013 작성 → 사용자 review → implementation plan 세션 (또 별도) 으로 인계

---

## 1. 확정된 12 결정 (verbatim)

`DECISIONS-CONFIRMED.md` 참조. 핵심 요약:

### Part A (D1-D7)
- D1 Two-Engine Plugin Framework: **승인**
- D2 v2 자산: **폐기** ← non-default
- D3 2nd system: **실제 선정** ← non-default
- D4 Schema Layer migration: spec 직후 즉시
- D5 LLM: **agnostic (다중 지원)** ← non-default
- D6 Onboarding cost: 50-400h 수용
- D7 다음 세션: 이대로 진행

### Part B (M-D1 ~ M-D5)
- M-D1 4 ADR (006-009): 모두 채택
- M-D2 Section 2 작업 시점: spec 단계 통합
- M-D3 v2 우선순위: **일반화 병행** ← non-default
- M-D4 Honest limits: **수용 + 확장가능 설계** ← non-default
- M-D5 인계: 즉시

---

## 2. Spec session 의 작업 범위

### 2.1 산출물

| # | 파일 | 내용 | 추정 LOC |
|---|---|---|---|
| 1 | `spec.md` | Two-Engine Plugin Framework 의 정식 spec | 600-1000 |
| 2 | `ADR-003-two-engine-substrate.md` | Integrator + proposal lifecycle + revision pointer | 300-500 |
| 3 | `ADR-004-schema-layer.md` | 5번째 ontology DDL + migration plan | 300-500 |
| 4 | `ADR-005-recommendation-llm-defenses.md` | 4 방어 mechanism | 300-500 |
| 5 | `ADR-010-phase-alpha-discard.md` | D2 폐기 결정의 historical record + Phase α 학습 자산 | 200-300 |
| 6 | `ADR-011-second-system-selection.md` | D3 — 2nd system 선정 기준 + onboarding plan | 300-400 |
| 7 | `ADR-012-llm-agnostic-recommendation.md` | D5 — multi-LLM abstraction | 200-400 |
| 8 | `ADR-013-extensibility-architecture.md` | M-D4 — plugin extension points + 새 meta-programming case 추가 path | 300-500 |
| 9 | `MILESTONES-2track.md` | M-D3 — v2 verification + framework generalization 병행 sprint plan | 200-400 |

총 ~2-4k LOC of markdown.

### 2.2 Spec session 의 첫 task

**2nd system 선정** (D3 의 직접 후속). 사용자와 검토:

- onTong 의 다른 internal Java repo? (있다면)
- 가상 controlled system (banking loan, e-commerce checkout, healthcare records, insurance claim 등) — complexity 제어
- 실제 OSS legacy (Apache OFBiz, JPetStore, PetClinic 등)

선정 기준:
- Spring DI / JPA / @Transactional 사용 (v2 와 framework overlap)
- 일정 규모 (50-100K LOC) — meaningful onboarding test
- 사용자가 도메인 일정 부분 이해 가능 (verification 검증 가능)
- Public access (보안 / 권한 issue 없음)

---

## 3. 모든 reference 파일 (sim-redesign/ 폴더)

### ADR 파일 (9 confirmed)
- `ADR-001-python-twin.md` — Python = Java 의 실행 인프라 우회 twin
- `ADR-002-scope-expansion.md` — System-agnostic + Recommendation Engine
- `ADR-006-polymorphic-dispatch.md` — 8 dispatch_kind
- `ADR-007-annotation-processing.md` — Lombok + custom processor
- `ADR-008-aop-aspect-weaving.md` — @Aspect handling
- `ADR-009-bytecode-generation.md` — CGLib subsume + custom plugin

### HTML 산출물 (visualization)
- `Q1-trace-granularity.html` — historical reference (Round 0 시점)
- `DESIGN-SYNTHESIS.html` — Round 1 종합 (Anchored Twin Synthesizer)
- `DESIGN-WALKTHROUGH.html` — Round 1 자체 비판 + 3 use case
- `SYNTHESIS-ROUND2.html` — Round 2 종합 (Two-Engine Plugin Framework)
- `META-PROGRAMMING.html` — 4 ADR 의 worked example
- `DECISIONS.html` — 인터랙티브 결정 도구

### Exploration 산출물 (8 perspective)
- `explorations/1-automation-purist.md` (Round 1)
- `explorations/2-minimal-twin.md` (Round 1)
- `explorations/3-alpha-reuse.md` (Round 1)
- `explorations/4-skeptic.md` (Round 1)
- `explorations/round2/1-architect-systemagnostic.md` (Round 2)
- `explorations/round2/2-recommendation-specialist.md` (Round 2)
- `explorations/round2/3-two-engine-integrator.md` (Round 2)
- `explorations/round2/4-skeptic.md` (Round 2)

### 기타
- `SESSION-RESUME.md` — 이전 세션 (brainstorming) 의 시작 시점 handoff
- `DECISIONS-CONFIRMED.md` — 12 결정 verbatim
- `AGENT-SHARED-CONTEXT.md` — 1st round agent 공유 context

### Section 4 verification 관련 (sibling)
- `toClaude/modeling/section4-verification/anchor-gaps.md` — v2 ontology gap (A-F)
- `toClaude/modeling/section4-verification/source-code-fixes-pending.md` — 보류 작업
- `toClaude/modeling/section4-verification/idioms/P*.md` — Phase α 27 카드 (D2 결정으로 폐기 대상, 학습 자산만)
- `toClaude/modeling/section4-verification/known-divergence-resolution-options.html` — 이전 옵션 (현 reference)

### 메모리 (~/.claude/projects/-Users-donghae-workspace-ai-onTong/memory/)
- `feedback_simulation_design.md` — no MVP, 풀 시연 필수 (CRITICAL)
- `project_decisions_v4_action.md` — 4-layer + CallSiteAnalyzer 7-case
- `project_pivot_authoring_ai.md` — Authoring AI 전환

---

## 4. Spec session 의 명시적 제약

### 4.1 User requirements (R1-R5, 변동 없음)
- R1: Ontology = simulation precondition
- R2: 시뮬 에이전트가 빈틈 자각 ("...가 불명확함")
- R3: 동일 input → 동일 output (with explicit tolerance)
- R4: 동일 처리 과정 보장 (코드 형태 무관)
- R5: 수정 전후 비교 분석 가능

### 4.2 Architectural 제약 (확정)
- ADR-001: Python = Java twin (사람은 Java 만 편집)
- ADR-002: Two-Engine + plugin
- 12 결정: 위 모두 적용

### 4.3 No MVP (메모리)
- 풀 시연 보장. Implementation 부분 구현 / phase 미루기 X
- 단 SIGNATURE_LOCKED 의 명시 한계는 OK (M-D4 확인)

---

## 5. Spec session 의 작업 흐름 제안

### Step 0 — Handoff 읽기
1. `DECISIONS-CONFIRMED.md` 읽기 — 5 non-default decision 의 implication 확인
2. `SYNTHESIS-ROUND2.html` + `META-PROGRAMMING.html` 다시 보기 (역사 reference)

### Step 1 — 2nd system 선정 (D3 직접 후속)
사용자와 인터뷰 → 후보 ~3-5개 → 선정. 결과를 `ADR-011` 의 1차 초안에 기록.

### Step 2 — spec.md 작성
구조 제안:
1. 목적 (Two-Engine 의 design 의도)
2. Architecture (core + plugins + Verification + Recommendation + Integrator)
3. 5-layer ontology (Code/Domain/Mapping/Simulation/Schema)
4. Plugin contract (system 별 7 artifact)
5. Two-engine workflow (R3-R5 + UC1-UC4)
6. Extension architecture (M-D4)
7. Multi-track milestone (M-D3)
8. ADR cross-reference

### Step 3 — 4 신규 ADR 작성 (ADR-010 ~ 013)
- ADR-010: Phase α discard rationale
- ADR-011: 2nd system selection (Step 1 결과)
- ADR-012: LLM-agnostic abstraction
- ADR-013: Extensibility for meta-programming

### Step 4 — 3 미작성 ADR 작성 (ADR-003 ~ 005)
- ADR-003: Two-Engine Substrate (현 Round 2 의 Integrator)
- ADR-004: Schema Layer (현 Round 2 의 DDL)
- ADR-005: Recommendation Engine LLM defenses (현 Round 2 의 4 defense)

### Step 5 — Self-review + 사용자 confirm
spec self-review (placeholder / contradiction / scope / ambiguity).
사용자 review → 수정 → 승인.

### Step 6 — Implementation plan 세션으로 인계
또 별도 세션 — implementation plan 작성 (`superpowers:writing-plans`).

---

## 6. 워크스페이스 격리 주의사항

- 현 브랜치 `section4-verification` (main 미머지)
- 다른 modeling 세션이 frontend/ 작업 중 — git status 로 확인
- 본 세션의 쓰기 영역: `toClaude/modeling/section4-verification/sim-redesign/` 만
- Section 2 본체 (`backend/modeling/`) 수정은 spec 승인 후 implementation 단계에서만

---

## 7. 이전 brainstorming 세션 (이번) 의 흐름 요약

| 단계 | 결과 |
|---|---|
| Step 1 — Q1 trace granularity 깊이 | emit 정의 + ontology vs runtime trace + 5 옵션 (E/A/B/C/D) |
| Step 2 — ADR-001 (twin) | Python = Java 의 실행 인프라 우회 twin, 사람은 Java 만 편집 |
| Step 3 — Round 1 4 perspective | automation purist / minimal twin / α reuse / skeptic |
| Step 4 — Round 1 종합 | Anchored Twin Synthesizer (2-layer + contract + gap surface + trace diff) |
| Step 5 — 자체 비판 + use case | 8 weakness + UC1 풀 시연 + UC2 영향 분석 + UC3 R5 |
| Step 6 — ADR-002 (확장) | System-agnostic + Recommendation Engine |
| Step 7 — Round 2 4 perspective | architect / recommendation / integrator / skeptic |
| Step 8 — Round 2 종합 | Two-Engine Plugin Framework |
| Step 9 — Reflection / meta-programming | ADR-006~009 + META-PROGRAMMING.html |
| Step 10 — 12 결정 인터랙티브 + handoff | DECISIONS-CONFIRMED.md + 본 handoff |

---

## 8. 다음 세션의 첫 task (clear instruction)

```
1. cd /Users/donghae/workspace/ai/onTong
2. Read: toClaude/modeling/section4-verification/sim-redesign/HANDOFF-spec-session.md (이 파일)
3. Read: toClaude/modeling/section4-verification/sim-redesign/DECISIONS-CONFIRMED.md
4. 사용자에게: "2nd system 선정 시작합니다. 후보 검토하시겠습니까?"
5. 인터뷰 → ADR-011 1차 초안 → 나머지 ADR + spec.md
```

---

## 9. 참고: 사용자가 spec session 시작 시 명시한 의도

> "최고의 결과를 너와 내가 도출할 수 있도록 방법을 찾아줘"
> — 사용자, 2026-05-12 (SESSION-RESUME 의 원문)

본 brainstorming + spec 작성은 이 의도의 양 단계. spec 완료 후 implementation plan 세션에서 실제 작업 시작.
