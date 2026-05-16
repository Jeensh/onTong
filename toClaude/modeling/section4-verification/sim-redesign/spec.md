# Two-Engine Plugin Framework — Spec

작성일: 2026-05-13
상태: 확정 (사용자 review + 승인 대기)
세션: section4-verification / sim-redesign / spec session
선행: 12 결정 (`DECISIONS-CONFIRMED.md`)
ADR 묶음: ADR-001 ~ ADR-013 (총 11 ADR, ADR-006-009 = 4 meta-programming)
다음 단계: implementation plan session (`superpowers:writing-plans`)

---

## 0. TL;DR

**Two-Engine Plugin Framework** — Section 4 simulation 의 정식 design.

핵심 변화:
- Single-system (v2) → **system-agnostic** plugin framework
- Verification-only → **Verification + Recommendation** dual engine
- 4-layer → **5-layer** ontology (Schema layer 추가)
- Single LLM → **LLM-agnostic** abstraction
- Honest limits → **확장가능 limits** (extension first-class)
- v2 자산 흡수 → **D2 폐기** (학습 자산만 reference)
- 가상 검증 → **3 systems (v2 + Broadleaf + Banking) 완전 병렬** onboarding

---

## 1. Purpose / Design 의도

### 1.1 사용자 requirement (R1-R5, 변동 없음)

| R | 내용 |
|---|---|
| R1 | Ontology = simulation precondition. Simulation 이전에 ontology 가 ground truth |
| R2 | 시뮬 에이전트가 빈틈을 자각 ("...가 불명확함" 자기-진단) |
| R3 | 동일 input → 동일 output (with explicit tolerance) |
| R4 | 동일 처리 과정 보장 (코드 형태 무관, semantic equivalence) |
| R5 | 수정 전후 비교 분석 가능 |

### 1.2 본 spec 의 design 의도

- **Verification (R3-R5)** + **Recommendation (UC4-UC6)** 동시 mechanism
- **Java twin 의 결정론적 합성** — Python 은 사람이 편집 X (ADR-001)
- **System-agnostic plugin framework** — v2 의 specifics 가 hidden assumption 으로 굳어지지 않음 (ADR-002)
- **Extension first-class** — 새 meta-programming case 가 framework 변경 없이 흡수 (ADR-013)
- **LLM-agnostic** — provider lock-in 없음 (ADR-012)
- **Honest limits 명시** — SIGNATURE_LOCKED + extension path

---

## 2. Architecture

### 2.1 Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 Two-Engine Plugin Framework                 │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────────┐    │
│  │ Verification Engine │    │ Recommendation Engine   │    │
│  │ (deterministic)     │    │ (LLM-based)             │    │
│  │                     │    │                         │    │
│  │ Anchored Twin       │    │ Schema Recommender      │    │
│  │ Synthesizer         │    │ Code Recommender        │    │
│  │ Twin Runner         │    │ Ontology Evolver        │    │
│  │ Oracle Differ       │    │                         │    │
│  │ Trace Diff Analyzer │    │ 4-layer defense         │    │
│  └─────────┬───────────┘    └────────┬────────────────┘    │
│            │                         │                     │
│            └─────────┬───────────────┘                     │
│                      ▼                                     │
│         ┌────────────────────────┐                         │
│         │     Integrator         │                         │
│         │ (proposal lifecycle +  │                         │
│         │  revision pointer +    │                         │
│         │  message bus)          │                         │
│         └─────────┬──────────────┘                         │
│                   ▼                                        │
│         ┌────────────────────────┐                         │
│         │   Plugin loader (core) │                         │
│         └─────────┬──────────────┘                         │
│                   ▼                                        │
│  ┌────────────────┴────────────────────────────────────┐  │
│  │            Per-system plugins                       │  │
│  │  ┌──────────┐  ┌────────────┐  ┌────────────┐       │  │
│  │  │ v2-slab- │  │ broadleaf  │  │ banking    │  ... │  │
│  │  │ design   │  │            │  │            │       │  │
│  │  └──────────┘  └────────────┘  └────────────┘       │  │
│  │  Each: 7 artifact + extensions                      │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │     Ontology (5-layer)│
              │ Code / Domain /       │
              │ Mapping / Simulation /│
              │ Schema                │
              └──────────────────────┘
```

### 2.2 Core 구성 요소

| 구성 | 위치 | 역할 | 관련 ADR |
|---|---|---|---|
| **Verification Engine** | `core/verification/` | Deterministic twin synthesis + oracle | ADR-001, ADR-002 |
| **Anchored Twin Synthesizer** | `core/verification/synthesizer/` | Java AST + ontology → Python twin | ADR-001, ADR-006~009 |
| **Twin Runner** | `core/verification/runner/` | Python twin 실행 + trace emit | ADR-001 |
| **Oracle Differ** | `core/verification/oracle/` | Java baseline 과 Python proposal 비교 | ADR-003 |
| **Trace Diff Analyzer** | `core/verification/trace/` | Per-action semantic diff | ADR-002 |
| **Recommendation Engine** | `core/recommendation/` | LLM-based proposal generation | ADR-002, ADR-005 |
| **LLM Provider abstraction** | `core/recommendation/providers/` | Claude / OpenAI / Gemini swap | ADR-012 |
| **Defense Layer 1-4** | `core/recommendation/defenses/` | Hallucination 등 4-layer 방어 | ADR-005 |
| **Anti-pattern catalog** | `core/recommendation/anti_patterns/` | Phase α lessons 보존 | ADR-010 L1 |
| **Integrator** | `core/integrator/` | Two engine 통합 + proposal lifecycle + revision pointer | ADR-003 |
| **Plugin Loader** | `core/plugin_loader.py` | Plugin discovery + extension registration | ADR-013 |
| **Ontology API** | `core/ontology/` | 5-layer SQLite access | ADR-004 |

---

## 3. 5-layer Ontology

### 3.1 Layer 개관

```
Layer 1 — Code        (Java AST → entity, method, call site 등)
Layer 2 — Domain      (BusinessTerm, 도메인 개념)
Layer 3 — Mapping     (Code ↔ Domain 연결, fragment-level anchor)
Layer 4 — Simulation  (Action, fixture, trace, divergence record)
Layer 5 — Schema      (★ 신규) Table, Column, Constraint, Index, View, Migration
```

### 3.2 Schema Layer 추가 (ADR-004)

기존 4 layer (메모리 `project_decisions_v4_action.md` 의 D2-D6) 변경 **없이** 8개 새 table 추가:
- `schema_table` / `schema_column` / `schema_constraint` / `schema_index` / `schema_view`
- `schema_migration` (DDL version 관리)
- `schema_code_mapping` (Schema ↔ Code 양방향)
- `schema_domain_mapping` (Schema ↔ BusinessTerm)

Migration: **additive only**, rollback 가능. 기존 4 layer 데이터 손실 risk 0 (D4 일관).

### 3.3 Cross-layer queries

UC4 (스키마 추천) 의 핵심:
```sql
-- "feature X 추가하려면 어떤 schema 변경?"
SELECT s.table_name, s.column_name
FROM business_term bt
  JOIN schema_domain_mapping sdm ON bt.id = sdm.domain_term_id
  JOIN schema_column sc ON sdm.schema_column_id = sc.id
  JOIN schema_table s ON sc.table_id = s.id
WHERE bt.term = ?  -- "X feature 의 도메인 용어"
```

---

## 4. Plugin Contract

### 4.1 Per-system 의 7 artifact

각 plugin (`plugins/<system>/`) 은 7 artifact 작성:

| Artifact | 위치 | 역할 | 관련 ADR |
|---|---|---|---|
| 1 | `contracts/base.py` | Java contract (Spring stub, JPA stub, TX stub) | ADR-002 |
| 2 | `entities/` | Java AST → entity model (자동 추출) | ADR-002 |
| 3 | `mappings/` | Code ↔ Domain mapping (ontology import) | ADR-002 |
| 4 | `emitters/` | 8 dispatch_kind emitter override (optional) | ADR-006 |
| 5 | `fixtures/` | Input → expected output fixture | ADR-002 |
| 6 | `aspects/` | @Aspect handler (system-specific) | ADR-008 |
| 7 | `manifest.toml` | Plugin metadata (model_version, LLM_provider, extensions) | ADR-002, ADR-012, ADR-013 |

### 4.2 Plugin manifest 구조

```toml
[plugin]
name = "v2-slab-design"
version = "0.1.0"
description = "onTong slab manufacturing twin plugin"

[recommendation]
default_provider = "claude"
default_model = "claude-opus-4-7"
allowed_providers = ["claude", "openai", "gemini"]
max_retries = 3

[extensions]
dispatchers = []           # v2 minimal — Case 1-2 만 사용
annotations = []
aop = []
bytecode = []

[schema]
source = "jpa_annotation"  # or "hibernate_xml" or "ddl_file"
```

### 4.3 Extension hierarchy (ADR-013)

```
Tier 1 — Framework core (semver, 변경 빈도 낮음)
  core/synthesizer/dispatchers/      # 8 dispatch_kind (ADR-006)
  core/synthesizer/annotations/      # Lombok + custom (ADR-007)
  core/synthesizer/aop/              # @Aspect weaving (ADR-008)
  core/synthesizer/bytecode/         # CGLib + custom (ADR-009)

Tier 2 — Plugin extensions (system 별)
  plugins/<sys>/dispatchers/         # 새 dispatch_kind
  plugins/<sys>/annotations/         # 새 annotation
  plugins/<sys>/aop/                 # 새 aspect type
  plugins/<sys>/bytecode/            # 새 bytecode pattern
  plugins/<sys>/extensions/          # escape hatch (RATIONALE.md 의무)
```

Plugin extension 의 namespace prefix 권장: `banking.drools_kbase_lookup` (not `drools_kbase_lookup`) — collision 방지.

---

## 5. Two-Engine Workflow

### 5.1 R3 (동일 input → 동일 output) workflow

```
1. User triggers UC1 (풀 시연)
   → fixture S1 의 input 으로 Java baseline 실행 → output_J
   → Python twin (same fixture) 실행 → output_P
   → Oracle Differ: output_J vs output_P with tolerance
   → R3 verdict
```

### 5.2 R4 (동일 처리 과정) workflow

```
1. Java baseline 실행 시 trace_J emit (per-action span)
2. Python twin 실행 시 trace_P emit (per-action span)
3. Trace Diff Analyzer: trace_J vs trace_P
   - Same action sequence? (semantic alignment)
   - Same intermediate values? (per-anchor)
   - Same async boundary? (TX, async batch)
4. R4 verdict
```

### 5.3 R5 (수정 전후 비교) workflow

```
1. Pre-modification revision (R_old)
   - Ontology version, code commit, schema migration version
   - Fixture baseline (모든 fixture 의 output)

2. Java 수정 → ontology 갱신 → Python twin 자동 재생성

3. Post-modification revision (R_new)
   - 새 ontology, 새 code commit, 새 schema migration
   - 새 fixture baseline

4. R5 비교:
   - R_old.fixture_baseline vs R_new (each fixture 의 output diff)
   - Trace diff per fixture (의도된 변경인지 user confirm)

5. Revision pointer chain: R_old → R_new (ADR-003)
```

### 5.4 UC4 (스키마 추천) workflow

```
1. User: "feature X 를 추가하려면 schema 어떻게 변경?"

2. Recommendation Engine:
   - Defense Layer 1: ontology 의 관련 entity/schema/term grounding
   - LLM call (provider-agnostic, ADR-012)
   - Defense Layer 2: output validation (cross-ref + consistency)
   - Retry if validation fails

3. Integrator (ADR-003):
   - Proposal 등록 (PROPOSED state)
   - Oracle 호출: Verification Engine 이 schema_diff 적용 후 fixture 시뮬
   - Defense Layer 3: Oracle result PASS/FAIL_BREAKING/FAIL_DRIFT/INCONCLUSIVE
   - ORACLED state 전이

4. User review (Defense Layer 4):
   - Proposal summary + schema diff + code diff + ontology diff + oracle result
   - Anti-pattern warning (Phase α lessons)
   - ACCEPT / REJECT / CHANGE_REQUEST / PARTIAL_ACCEPT

5. Merge (Revision pointer 발급, ADR-003):
   - New revision: ontology_revision + code_revision + schema_revision
   - Lineage: parent_revision → new revision
   - Next proposal 의 oracle 기준
```

### 5.5 UC5/UC6 (Code / Ontology 추천)

UC4 와 동일한 4-layer defense + Integrator flow. Proposal type 만 다름 (`code_change`, `ontology_evolution`).

---

## 6. Extension Architecture (ADR-013, M-D4 일관)

### 6.1 Default: SIGNATURE_LOCKED

Plugin extension 없는 unknown meta-programming case 는 default 로 SIGNATURE_LOCKED:

```python
def synthesize(self, call_site):
    return PythonStatement(
        f"# UNCLEAR: dispatch_kind = {call_site.kind!r} not handled.\n"
        f"# SIGNATURE_LOCKED. Add plugins/<sys>/dispatchers/ extension.\n"
        f"def {call_site.method}(...):\n"
        f"    raise NotImplementedError('SIGNATURE_LOCKED: {call_site.kind}')"
    )
```

### 6.2 Extension lifecycle

```
Phase 1 — Discovery
  Onboarding 중 unknown case → SIGNATURE_LOCKED auto-trigger
  User 가 plugins/<sys>/extensions/proposal-<case>.md 작성

Phase 2 — Implementation
  Plugin 의 dispatcher / annotation / aop / bytecode 작성
  Cross-plugin test suite 통과

Phase 3 — Promotion (선택적)
  여러 plugin 에서 동일 extension 반복 → core 로 promote
  → 새 dispatch_kind / annotation_kind 추가
  → ADR-006~009 갱신 (framework version bump, semver minor)
```

### 6.3 3 system 의 예상 extension (ADR-011 의 G4 gate 검증 대상)

| System | 예상 extensions |
|---|---|
| v2 | (minimal) — Case 1-2 만 사용. `extensions/` 비어있을 가능성 |
| Broadleaf | `broadleaf.configurable_handler`, `broadleaf.data_driven`, `broadleaf.dynamic_field` |
| Banking | `banking.drools_kbase_lookup`, `@Compensable`, `@TenantContext`, `banking.bpmn_dynamic_class` |

---

## 7. Multi-track Milestone (M-D3 병행, ADR-011 일관)

### 7.1 v2 verification + framework generalization 병행

```
Track A — v2 verification (D2 폐기 결정 반영)
  W1-W4   Phase α 학습 자산 추출 (5 lessons)
  W3-W8   새 v2 plugin 작성 (Phase α 처음부터, 7 artifact)
  W6-W12  v2 의 UC1/UC2/UC3 풀 시연

Track B — Framework generalization
  W1-W4   Core 의 5-layer ontology DDL 작성 (ADR-004)
  W2-W6   Integrator + proposal lifecycle (ADR-003)
  W4-W10  3 system plugin 작성 병렬 (v2 + Broadleaf + Banking)
  W8-W16  Recommendation Engine 의 4-layer defense (ADR-005, ADR-012)
  W12-W20 Extension architecture validation (ADR-013, G4 gate)
```

상세는 `MILESTONES-2track.md` 참조.

### 7.2 Cross-validate gates (G1-G4)

ADR-011 의 G1-G4 = framework universality 의 falsifiable test.

```
G1 (Month 1) — Framework core contract 검증
  3 system 각 UC1 풀 시연 1건 + plugin 7 artifact + R3 보장

G2 (Month 2) — Meta-programming 4 영역 coverage
  ADR-006/007/008/009 각 system 적용

G3 (Month 3) — Recommendation Engine
  3 system + 2+ provider (Claude + GPT) 의 reasonable proposal

G4+ (Month 4+) — Extension architecture
  Banking Drools + Broadleaf enterprise-only feature 의 SIGNATURE_LOCKED + extension path 검증
```

---

## 8. Onboarding Cost (D6 명시)

| System | Cost | 분해 |
|---|---|---|
| v2 | 100-200h | Phase α reference 50h + 새 plugin 50-150h |
| Broadleaf | 300-400h | 학습 100h + plugin 200-300h |
| Banking | 250-400h | 도메인 설계 100h + 구현 100-200h + plugin 50-100h |
| **Total** | **650-1000h** | 3인 팀, 6-12 month |

M1 gate 후 cost re-estimate 의무.

---

## 9. ADR Cross-reference

| ADR | 제목 | 결정 source |
|---|---|---|
| ADR-001 | Python = Java twin | brainstorming step 2 |
| ADR-002 | Two-Engine + plugin | brainstorming step 6 |
| ADR-003 | Two-Engine Substrate (Integrator) | D1, D7 |
| ADR-004 | Schema Layer | D4 |
| ADR-005 | Recommendation LLM defenses (4-layer) | D7, D5 |
| ADR-006 | Polymorphic dispatch (8 kind) | M-D1 |
| ADR-007 | Annotation processing | M-D1 |
| ADR-008 | AOP / @Aspect weaving | M-D1 |
| ADR-009 | Bytecode generation (CGLib + custom) | M-D1 |
| ADR-010 | Phase α discard rationale | D2 (non-default) |
| ADR-011 | 2nd system selection (3 systems hybrid) | D3 (non-default) |
| ADR-012 | LLM-agnostic Recommendation | D5 (non-default) |
| ADR-013 | Extensibility Architecture | M-D4 (non-default) |

5 non-default 결정 (D2, D3, D5, M-D3, M-D4) 의 ADR (010, 011, 012, MILESTONES-2track, 013) 가 본 spec 의 핵심 변화.

---

## 10. Out of scope (Phase 2 후보)

- Cross-plugin proposal saga (ADR-003)
- NoSQL schema layer (ADR-004)
- Cost-aware / quality-aware LLM routing (ADR-012)
- Distributed DB migration tool integration (ADR-004)
- UC5 (Code Recommender) / UC6 (Ontology Evolver) 의 full implementation (ADR-002)
- Sharding / partitioning schema modeling (ADR-004)
- Promotion path 의 automatic detection (ADR-013)

---

## 11. 다음 단계

1. **본 spec session 종료** — 사용자 review + approval
2. **Implementation plan session** — `superpowers:writing-plans` 로 별도 세션
   - W1-W20 의 detailed sprint plan
   - 5 lessons (L1-L5) 의 정식 작성
   - BANKING-DESIGN.md 의 entity / DDL / BPMN 명세
   - BROADLEAF-ONBOARDING.md 의 module scope + onboarding path
   - V2-MIGRATION.md 의 Phase α → 새 plugin 절차
3. **Implementation phase** — implementation plan 의 sprint 실행

---

## 12. 참조

### 결정
- `DECISIONS-CONFIRMED.md` (12 결정 verbatim)

### Brainstorming 산출물
- `SYNTHESIS-ROUND2.html` — Round 2 종합 (Two-Engine Plugin Framework 의 motivation)
- `META-PROGRAMMING.html` — 4 meta-programming ADR 의 worked example
- `DESIGN-SYNTHESIS.html` — Round 1 종합 (Anchored Twin Synthesizer)
- `DESIGN-WALKTHROUGH.html` — Round 1 자체 비판 + UC1/UC2/UC3
- `Q1-trace-granularity.html` — historical reference (Round 0)

### Exploration
- `explorations/1-4-*.md` — Round 1 4 perspective
- `explorations/round2/1-4-*.md` — Round 2 4 perspective (architect / recommendation / integrator / skeptic)

### Section 4 sibling
- `toClaude/modeling/section4-verification/anchor-gaps.md`
- `toClaude/modeling/section4-verification/source-code-fixes-pending.md`
- `toClaude/modeling/section4-verification/idioms/P*.md` (폐기 대상, ADR-010 참조)

### 사용자 메모리
- `feedback_simulation_design.md` — no MVP, 풀 시연 필수
- `project_decisions_v4_action.md` — 4-layer + CallSiteAnalyzer 7-case
- `project_pivot_authoring_ai.md` — Authoring AI 전환 (related)
- `project_sim_redesign_decisions.md` — 본 sim-redesign brainstorming 종료 record
