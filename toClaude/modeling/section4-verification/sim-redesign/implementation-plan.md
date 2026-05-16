# Two-Engine Plugin Framework — Implementation Plan

> **For agentic workers:** This is a sprint-level implementation plan (W1-W20). Each task in §2-§3 represents a multi-day work unit. Tasks use checkbox (`- [ ]`) syntax for sprint tracking. Bite-sized TDD steps happen at task pickup (implementation phase).

**Goal:** Build the Two-Engine Plugin Framework — system-agnostic verification + recommendation core, 3 reference plugins (v2 / Broadleaf / Banking), 5-layer ontology with Schema Layer, LLM-agnostic Recommendation Engine with 4-layer defense, and extensible meta-programming substrate.

**Architecture:** Two engines (Verification deterministic + Recommendation LLM-based) on top of Integrator (proposal lifecycle + revision pointer + message bus), each system as plugin (7 artifact), 5th ontology layer (Schema) added additively.

**Tech Stack:** Python 3.11+ (substrate + framework), Java 17 (twin source), SQLite (ontology, additive Schema layer), JPA / Spring (Broadleaf + Banking source compat), Drools 8 / Activiti BPMN (Banking meta-programming), pytest (verification harness), tomli (plugin manifest), pydantic (Proposal data model).

작성일: 2026-05-13 (implementation plan session)
선행 산출물: spec.md, MILESTONES-2track.md, 13 ADR (ADR-001 ~ ADR-013), DECISIONS-CONFIRMED.md (12 결정)
Sibling artifacts: 5 lessons (L1-L5), V2-MIGRATION.md, BROADLEAF-ONBOARDING.md, BANKING-DESIGN.md
관련 메모리: `project_sim_redesign_decisions.md`, `feedback_simulation_design.md`, `project_decisions_v4_action.md`

---

## 0. TL;DR

| 항목 | 값 |
|---|---|
| Duration | 16-20 week (4-5 month) + buffer = **6-12 month** (3인 팀) |
| Cost | **650-1000h** (D6 명시) — v2 100-200h + Broadleaf 300-400h + Banking 250-400h |
| Tracks | **2** — Track A (v2 verification) + Track B (framework generalization), 병행 (M-D3) |
| Gates | **4** — G1 (W10) / G2 (W14) / G3 (W18) / G4 (W20+) |
| 산출 | Framework core + 3 plugins + Recommendation Engine + 5-layer ontology |
| Sprint | 2-week cadence (10 sprints over W1-W20) |
| 첫 milestone | M1 (W4) — cost re-estimate gate |

---

## 1. Scope

### 1.1 In scope (본 plan)

- Framework core (`backend/sim_v2/core/synthesizer/`, `backend/sim_v2/core/verification/`, `backend/sim_v2/core/recommendation/`, `backend/sim_v2/core/integrator/`, `backend/sim_v2/core/ontology/`, `backend/sim_v2/core/plugin_loader.py`)
- 3 plugin (`backend/sim_v2/plugins/v2-slab-design/`, `backend/sim_v2/plugins/broadleaf/`, `backend/sim_v2/plugins/banking/`) — 7 artifact each
- 5-layer ontology (Code / Domain / Mapping / Simulation / + **Schema (신규)**)
- Recommendation Engine 의 4-layer defense + LLM-agnostic provider abstraction
- Extension architecture (ADR-013) — Tier 1 / Tier 2 + plugin extension promotion path
- Cross-validate G1-G4 gates
- Per-task acceptance criteria + dependency graph + risk register

### 1.2 Out of scope (Phase 2)

| Item | 이유 |
|---|---|
| Cross-plugin proposal saga (ADR-003 §6) | Phase 1 = single-plugin proposal lifecycle 충분 |
| UC5 (Code Recommender) / UC6 (Ontology Evolver) full implementation | UC4 (Schema Recommender) MVP 우선 |
| NoSQL schema layer | Phase 1 = relational (PostgreSQL / SQLite) |
| Cost-aware / quality-aware LLM routing | Phase 1 = round-robin or default provider |
| Distributed DB migration tool integration | Phase 1 = additive migration only |
| Sharding / partitioning schema modeling | Phase 1 = single-shard logical model |
| Promotion path 의 automatic detection (ADR-013 §6.3 Phase 3) | Phase 1 = manual promotion |

### 1.3 Pre-conditions (W1 시작 전)

- ✓ 13 ADR confirmed (`ADR-001` ~ `ADR-013`)
- ✓ 12 결정 confirmed (`DECISIONS-CONFIRMED.md`)
- ✓ spec.md confirmed
- ✓ 5 lessons drafted (`lessons/phase-alpha-*.md`)
- ✓ 3 sub-design drafted (V2-MIGRATION / BROADLEAF-ONBOARDING / BANKING-DESIGN)
- 3인 팀 onboarding 확인 (Lead + Member A + Member B)

---

## 2. Track A — v2 Verification (W1-W12)

### 2.1 Phase A1 (W1-W4) — Phase α 학습 자산 추출 + git tag

**Goal:** Phase α 의 ~50h 작업물을 5 lesson markdown 으로 정수 추출 + `phase-alpha-snapshot` git tag 생성.

**Owner:** Lead.

#### Task A1.1 — git tag `phase-alpha-snapshot` 생성 (W1)

- [ ] **Files:**
  - Create (tag): `phase-alpha-snapshot` at commit `dcdf251` (or 사용자 검토 후 결정)
- [ ] Confirm Phase α 최종 commit hash (`6769560` source-fixes / `0777217` gap report / `dcdf251` handoff 중 선택)
- [ ] `git tag -a phase-alpha-snapshot <commit> -m "<message>"` (V2-MIGRATION.md §2.3 의 message)
- [ ] `git push origin phase-alpha-snapshot`
- [ ] **Acceptance:** `git show phase-alpha-snapshot:backend/modeling/sim_verify/runtime/bigdecimal.py` 가 Phase α 의 코드 반환

#### Task A1.2 — L1-L5 lesson markdown 작성 (W1-W4)

본 implementation plan session 안에서 5 lesson 이미 작성 (`lessons/phase-alpha-*.md`). 본 task 의 실 작업: 5 lesson 의 사용자 review + 잔여 detail 보완.

- [ ] **Files (이미 존재):**
  - `lessons/phase-alpha-known-divergence.md` (L1)
  - `lessons/phase-alpha-idiom-cards.md` (L2)
  - `lessons/phase-alpha-manual-twin.md` (L3)
  - `lessons/phase-alpha-facade.md` (L4)
  - `lessons/phase-alpha-fixture.md` (L5)
- [ ] User review of 5 lesson
- [ ] 잔여 detail 보완 (e.g., specific commit hash, 27 card 의 정확한 reusability 수치)
- [ ] **Acceptance:** 5 lesson 의 user approval + 각 lesson 이 새 framework 의 specific reference 명시 (Anti-pattern catalog entry 식별)

### 2.2 Phase A2 (W3-W8) — 새 v2 plugin 작성 (V2-MIGRATION.md 의 정식 실행)

**Goal:** `backend/sim_v2/plugins/v2-slab-design/` 의 7 artifact 처음부터 작성, Phase α equivalent intent fixture 5건 PASS.

**Owner:** Lead + Member A (parallel with Track B Phase B3 의 v2 부분).

본 phase 의 detail 은 `V2-MIGRATION.md §3-§5` 의 정식 실행.

#### Task A2.1 — Manifest + Contracts (W3-W4)

- [ ] **Files:**
  - Create: `backend/sim_v2/plugins/v2-slab-design/manifest.toml` (V2-MIGRATION.md §4.1)
  - Create: `backend/sim_v2/plugins/v2-slab-design/contracts/base.py` (V2-MIGRATION.md §4.2)
  - Create: `backend/sim_v2/plugins/v2-slab-design/contracts/domain_namespace.py` (SdConstants)
  - Create: `backend/sim_v2/plugins/v2-slab-design/contracts/exception.py` (AlgorithmException)
  - Create: `backend/sim_v2/plugins/v2-slab-design/contracts/validation.py` (ValidationResult)
  - Test: `backend/sim_v2/tests/plugins/v2_slab_design/test_contracts.py`
- [ ] `manifest.toml` 의 plugin metadata + extensions declaration
- [ ] `SlabDesignContract(JavaContract)` 의 exception_base / domain_namespace / numeric_convention 구현
- [ ] `SdConstants` 의 POS_SM/POS_HR 등 8-position string set (Phase α 의 confirmed_plant_cd.py 의 mapping)
- [ ] **Acceptance:**
  - `core.plugin_loader.load_plugin("v2-slab-design")` 성공
  - `pytest backend/sim_v2/tests/plugins/v2_slab_design/test_contracts.py` PASS
  - Anti-pattern scan (L1 의 5 KNOWN_DIVERGENCE) 0 hit

#### Task A2.2 — Entities + Mappings (W4-W5)

- [ ] **Files:**
  - Create: `backend/sim_v2/plugins/v2-slab-design/entities/__init__.py` (V2-MIGRATION.md §4.4)
  - Create: `backend/sim_v2/plugins/v2-slab-design/mappings/__init__.py` (V2-MIGRATION.md §4.5)
  - Modify: `backend/sim_v2/core/synthesizer/java_ast.py` (entity extraction API)
  - Test: `backend/sim_v2/tests/plugins/v2_slab_design/test_entities.py`
- [ ] Java AST 자동 추출 — sample-repos/slab-design-real-v2/src/main/java/ 의 128 entity (anchor-gaps §0)
- [ ] Section 2 ontology 자동 import — 163 anchor_bindings + 43 realizations
- [ ] anchor-gaps Gap C 14건 review (modeling UI confirm 흐름, Section 2 본체 작업)
- [ ] **Acceptance:**
  - ENTITIES dict 의 128 entity (= Phase α 의 code_types count)
  - MAPPINGS 의 confirmed_rate >= 90% (Gap C 14건 review 후 22+ confirmed)
  - `pytest backend/sim_v2/tests/plugins/v2_slab_design/test_entities.py` PASS

#### Task A2.3 — Emitters (W5-W6)

- [ ] **Files:**
  - Create: `backend/sim_v2/plugins/v2-slab-design/emitters/__init__.py` (17 generic + 7-10 plugin-specific)
  - Create: `backend/sim_v2/plugins/v2-slab-design/emitters/atomic_safety_absolute_max.py`
  - Create: `backend/sim_v2/plugins/v2-slab-design/emitters/atomic_confirmed_plant_cd.py`
  - Create: `backend/sim_v2/plugins/v2-slab-design/atoms/` (Lesson 2 의 P20-P26 의 7 slab 비즈니스 룰)
  - Test: `backend/sim_v2/tests/plugins/v2_slab_design/test_emitters.py`
- [ ] 17 generic emitter — `backend/sim_v2/core/synthesizer/emitters/` 상속 (Lesson 2 §6 의 P01-P08 + P10 + P12-P19)
- [ ] 7-10 plugin-specific emitter — atomic.* slab-specific (Lesson 2 §3 의 21/27 = slab)
- [ ] 8 dispatch_kind cover (ADR-006)
- [ ] **Acceptance:**
  - 56 distinct target_slot 모두 emitter 매핑 (anchor-gaps §0 의 coverage 유지)
  - Emitter test (Java AST 입력 → Python 출력) → contract validator (L1 §4.2) 통과
  - L1 의 5 KNOWN_DIVERGENCE 재발 없음

#### Task A2.4 — Fixtures (W6-W7)

- [ ] **Files:**
  - Create: `backend/sim_v2/plugins/v2-slab-design/fixtures/S1/input.json` + expected_output.json + expected_trace.json + metadata.toml + README.md
  - Create: `backend/sim_v2/plugins/v2-slab-design/fixtures/S2/...` ~ S5
  - Test: `backend/sim_v2/tests/plugins/v2_slab_design/test_fixtures.py`
- [ ] 5 fixture (S1-S5) — Phase α 의 의도만 유지 (BigDecimal precision / async batch / boundary / fallback / error)
- [ ] Per-fixture metadata.toml — domain / scenario_intent / tolerance (per-action override)
- [ ] Trace contract strong version (intermediate values + async boundary, Lesson 5 §4.2)
- [ ] **Acceptance:**
  - 5 fixture pytest PASS (R3 보장 with tolerance)
  - Trace contract 의 strong version 충족
  - Lesson 5 의 fixture metadata 부재 anti-pattern 0 hit

#### Task A2.5 — Aspects + 통합 검증 (W7-W8)

- [ ] **Files:**
  - Create: `backend/sim_v2/plugins/v2-slab-design/aspects/dispatch_metadata.py` (Lesson 2 의 P27)
  - Test: `backend/sim_v2/tests/plugins/v2_slab_design/test_integration.py`
- [ ] `V2DispatchMetadata(DispatchMetadataAspect)` — action.metadata.tiebreaker / fallback_kind
- [ ] 통합 검증 — 모든 7 artifact 의 plugin_loader 인식 + 5 fixture PASS + anti-pattern 0 hit
- [ ] **Acceptance:**
  - `python -m core.plugin_loader load backend/sim_v2/plugins/v2-slab-design` 성공
  - `python -m core.plugin_validator backend/sim_v2/plugins/v2-slab-design` 성공
  - `pytest backend/sim_v2/plugins/v2-slab-design/fixtures/ -v` 모두 PASS
  - `python -m core.recommendation.anti_patterns.scan backend/sim_v2/plugins/v2-slab-design` 0 hit
  - **G1 gate 대비 완료**

### 2.3 Phase A3 (W6-W12) — v2 UC1/UC2/UC3 풀 시연

**Goal:** v2 plugin 으로 3 use case 풀 시연 — R3 / R4 / R5 검증.

**Owner:** Member A + Member B (parallel with Track B Phase B4).

#### Task A3.1 — UC1 (풀 시연, R3 검증) (W6-W8)

- [ ] **Files:**
  - Create: `backend/sim_v2/demos/uc1_v2_full_demo/run.py`
  - Create: `backend/sim_v2/demos/uc1_v2_full_demo/README.md`
  - Test: `backend/sim_v2/tests/demos/test_uc1_v2.py`
- [ ] S1' fixture 입력으로 풀 시연 (Java baseline + Python twin 자동 합성 + Oracle 비교)
- [ ] R3 verdict — tolerance 안에서 동일 output
- [ ] Trace emission per-action
- [ ] Demo README — 사용자 데모 시 follow-along 가능
- [ ] **Acceptance:**
  - UC1 결과 PASS (R3 보장)
  - Demo run time < 30 sec
  - Trace JSON 의 per-action span 검증 (R4 weak version)

#### Task A3.2 — UC2 (영향 분석, R4 strong 검증) (W8-W10)

- [ ] **Files:**
  - Create: `backend/sim_v2/demos/uc2_v2_impact_analysis/run.py`
  - Test: `backend/sim_v2/tests/demos/test_uc2_v2.py`
- [ ] S2' fixture 의 input 변경 → trace diff
- [ ] Trace Diff Analyzer (`backend/sim_v2/core/verification/trace_differ.py`) 의 strong R4 — intermediate values + async boundary
- [ ] R4 verdict — same action sequence + intermediate consistent
- [ ] **Acceptance:**
  - UC2 결과 PASS (R4 strong)
  - Trace diff visualization (per-action / per-anchor)

#### Task A3.3 — UC3 (R5 수정 전후 비교) (W10-W12)

- [ ] **Files:**
  - Create: `backend/sim_v2/demos/uc3_v2_pre_post/run.py`
  - Test: `backend/sim_v2/tests/demos/test_uc3_v2.py`
- [ ] Java 코드 small change (e.g., productivity 계산 BigDecimal scale 변경) 
- [ ] 두 revision (R_old vs R_new) 의 fixture baseline 비교
- [ ] Revision pointer chain — R_old → R_new (ADR-003 §5)
- [ ] **Acceptance:**
  - UC3 결과 PASS (R5 보장)
  - Revision lineage 의 git tag chain 확인
  - Fixture baseline lineage 의 ADR-003 §5 mechanism 작동

---

## 3. Track B — Framework Generalization (W1-W20)

### 3.1 Phase B1 (W1-W4) — Core 5-layer ontology + Schema Layer

**Goal:** ADR-004 의 5번째 Schema Layer 추가, additive migration.

**Owner:** Member A.

#### Task B1.1 — Schema entity 정의 (W1)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/ontology/schema_layer/orm.py` (schema_table / schema_column / schema_constraint / schema_index / schema_view / schema_migration / schema_code_mapping / schema_domain_mapping 8 table)
  - Create: `backend/sim_v2/core/ontology/schema_layer/__init__.py`
  - Test: `backend/sim_v2/tests/core/ontology/test_schema_layer.py`
- [ ] 8 ORM model (SQLAlchemy) — ADR-004 §3.2
- [ ] **Acceptance:**
  - 8 ORM class 의 import 성공
  - `pytest backend/sim_v2/tests/core/ontology/test_schema_layer.py` PASS

#### Task B1.2 — Migration script (W1-W2)

- [ ] **Files:**
  - Create: `migrations/v5_schema_layer.sql`
  - Create: `scripts/migrate_v5_schema_layer.py`
- [ ] 8 table 추가 (additive only)
- [ ] Migration version 등록 in `schema_migration` table (ADR-004 §3.2)
- [ ] Rollback 가능
- [ ] **Acceptance:**
  - 기존 4 layer 데이터 손실 0 (D4 일관)
  - `alembic upgrade head` 성공, `alembic downgrade -1` 성공

#### Task B1.3 — Schema extractor plugin interface (W2-W3)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/ontology/schema_layer/extractor.py` (Protocol)
  - Create: `backend/sim_v2/core/ontology/schema_layer/extractors/jpa_annotation.py` (default)
- [ ] `SchemaExtractor` Protocol — plugin extension point (ADR-013)
- [ ] Default JPA annotation extractor (v2 / Broadleaf 의 JPA entity 의 @Table / @Column / @Index 추출)
- [ ] **Acceptance:**
  - `SchemaExtractor` 의 contract 명세
  - JPA extractor 의 v2 entity 추출 sanity (`code_types` table 의 128 entity 중 @Entity 있는 것의 schema 추출)

#### Task B1.4 — Cross-layer query API (W3-W4)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/ontology/query.py` (cross-layer query)
- [ ] UC4 prep query — `SELECT s.table_name, s.column_name FROM business_term bt JOIN schema_domain_mapping sdm ON ...` (spec.md §3.3)
- [ ] Schema ↔ Code mapping query
- [ ] Schema ↔ Domain mapping query
- [ ] **Acceptance:**
  - UC4 의 sample query 성공
  - Cross-layer join 의 5-layer 모두 coverage

### 3.2 Phase B2 (W2-W6) — Integrator + Proposal Lifecycle

**Goal:** ADR-003 의 Two-Engine Substrate 구현.

**Owner:** Lead + Member B.

#### Task B2.1 — Proposal data model + state machine (W2-W3)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/integrator/proposal.py` (Proposal / ProposalEvent / state machine)
  - Test: `backend/sim_v2/tests/core/integrator/test_proposal.py`
- [ ] `Proposal` pydantic model (ADR-003 §3)
- [ ] State machine: DRAFT → PROPOSED → ORACLED → REVIEWED → ACCEPTED → MERGED (+ REJECTED terminal)
- [ ] State 전이 의 audit log (ProposalEvent)
- [ ] **Acceptance:**
  - State machine 의 valid/invalid 전이 test
  - Audit log 의 immutable append-only 보장

#### Task B2.2 — Integrator API (W3-W4)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/integrator/integrator.py` (8 method API, ADR-003 §1)
  - Test: `backend/sim_v2/tests/core/integrator/test_integrator.py`
- [ ] `submit_proposal` / `request_oracle` / `refine_proposal` / `review_proposal` / `merge_proposal` 등
- [ ] **Acceptance:**
  - 8 method API 의 isolation test
  - Mock VerificationEngine + RecommendationEngine 으로 end-to-end flow

#### Task B2.3 — Revision pointer + lineage (W4-W5)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/integrator/revision.py` (Revision / fixture_baseline)
  - Modify: `backend/sim_v2/core/ontology/schema_layer/orm.py` (revision table 추가)
- [ ] `Revision` pydantic + ORM
- [ ] Lineage chain — parent_revision → new revision
- [ ] Fixture baseline 의 per-fixture output + measured_tolerance (Lesson 5 §4.4)
- [ ] **Acceptance:**
  - Revision chain 의 R5 mechanism 작동 (UC3 의 dependency)
  - Lineage graph traversal API

#### Task B2.4 — Oracle protocol (W5-W6)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/verification/oracle.py` (OracleRequest / OracleResult / FixtureOracleResult)
  - Create: `backend/sim_v2/core/verification/oracle_differ.py` (generic, Phase α scripts/section4_oracle_diff.py 대체)
  - Test: `backend/sim_v2/tests/core/verification/test_oracle.py`
- [ ] ADR-003 §4 의 Oracle Request/Response 정식
- [ ] Output diff + Trace diff
- [ ] 4-tier aggregate_status: PASS / FAIL_BREAKING / FAIL_DRIFT / INCONCLUSIVE
- [ ] **Acceptance:**
  - Oracle 의 4-tier 분류 명확 (FAIL_BREAKING = output diff, FAIL_DRIFT = trace diff only)
  - Generic — v2 / Broadleaf / Banking 모두 호출 가능

### 3.3 Phase B3 (W4-W10) — 3 plugin 작성 병렬

**Goal:** v2 (Phase A2 와 동일) + Broadleaf + Banking 의 7 artifact 병렬 작성. G1 gate (W10) 대비.

**Owner:** Lead (v2 + framework integration) + Member A (Broadleaf) + Member B (Banking).

#### Task B3.1 — v2 plugin (W4-W10)

Track A Phase A2 와 동일. 본 task = cross-validate viewpoint — v2 의 emitter 가 framework core 와 isolation 검증.

- [ ] **Files:** Track A Phase A2 의 산출물 (`backend/sim_v2/plugins/v2-slab-design/` 전체)
- [ ] v2-specific 가 framework core leak 없음 확인
- [ ] **Acceptance:** Track A Phase A2 의 acceptance + framework leak 0 (`core/` 안에 "slab" 또는 v2-specific 단어 0)

#### Task B3.2 — Broadleaf plugin (W4-W10)

BROADLEAF-ONBOARDING.md 의 정식 실행.

- [ ] **Files:**
  - Create: `backend/sim_v2/plugins/broadleaf/manifest.toml` (BROADLEAF-ONBOARDING.md §5.1)
  - Create: `backend/sim_v2/plugins/broadleaf/contracts/base.py` (§5.2)
  - Create: `backend/sim_v2/plugins/broadleaf/entities/`, `mappings/`, `emitters/`, `fixtures/`, `aspects/`
  - Test: `backend/sim_v2/tests/plugins/broadleaf/`
- [ ] BROADLEAF-ONBOARDING.md §5 의 W4-W10 sprint detail 따름
- [ ] BLC 의 4 meta-programming 영역 cover (Configurable / Factory dispatch / DynamicEntityDao / MVEL OfferRule)
- [ ] **Acceptance:**
  - Entity ~300-500 추출
  - Mapping confirmed_rate >= 90%
  - 5 fixture (B1-B5) pytest PASS
  - 5-6 plugin extension 명시 (manifest.toml `[extensions]`)
  - Boundary 명시: community-only, admin/cms/workflow/integration SIGNATURE_LOCKED

#### Task B3.3 — Banking plugin (W4-W10)

BANKING-DESIGN.md 의 정식 실행.

- [ ] **Files:**
  - Create: `sample-repos/banking-loan-twin/` (Java source 가상 작성)
  - Create: `backend/sim_v2/plugins/banking/manifest.toml`
  - Create: `backend/sim_v2/plugins/banking/contracts/base.py` (BankingContract)
  - Create: `backend/sim_v2/plugins/banking/entities/`, `mappings/`, `emitters/`, `fixtures/`, `aspects/`
  - Test: `backend/sim_v2/tests/plugins/banking/`
- [ ] BANKING-DESIGN.md §2-§10 의 design 따름 — 20 entity + 6 service + 6-step BPMN + Drools rule sample + multi-tenant aspect + Saga + DDL 17 table
- [ ] 4 plugin extension (drools_kbase_lookup / @Compensable / @TenantContext / bpmn_dynamic_class)
- [ ] **Acceptance:**
  - Banking sample Java codebase ~30-50K LOC
  - 20 entity 추출
  - 5 fixture (BK1-BK5) pytest PASS
  - 4 meta-programming 영역 모두 cover

### 3.4 Phase B4 (W8-W16) — Recommendation Engine

**Goal:** ADR-005 의 4-layer defense + ADR-012 의 LLM-agnostic provider 구현.

**Owner:** Lead.

#### Task B4.1 — LLM provider abstraction (W8-W10)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/recommendation/llm_provider.py` (Protocol)
  - Create: `backend/sim_v2/core/recommendation/providers/claude.py`
  - Create: `backend/sim_v2/core/recommendation/providers/openai.py`
  - Create: `backend/sim_v2/core/recommendation/providers/gemini.py`
  - Test: `backend/sim_v2/tests/core/recommendation/test_providers.py`
- [ ] `LLMProvider` Protocol (ADR-012)
- [ ] 3 provider impl (Claude / OpenAI / Gemini)
- [ ] Per-call provider selection via manifest.toml `[recommendation].default_provider`
- [ ] **Acceptance:**
  - 3 provider 의 동일 sample prompt 응답 비교 (manual review)
  - Provider swap test (manifest.toml 의 provider 변경 → 동일 proposal interface)

#### Task B4.2 — Defense Layer 1 (context grounding) (W10-W12)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/recommendation/defenses/grounding.py`
  - Test: `backend/sim_v2/tests/core/recommendation/test_grounding.py`
- [ ] Pre-call defense — ontology 의 관련 entity / schema / business_term 자동 grounding
- [ ] Prompt 의 system message 에 grounding context inject
- [ ] **Acceptance:**
  - Grounding context 의 ontology 5-layer 모두 활용 (Code / Domain / Mapping / Simulation / Schema)
  - Sample proposal 의 grounding accuracy manual review

#### Task B4.3 — Defense Layer 2 (output validation) (W11-W13)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/recommendation/defenses/output_validator.py`
  - Test: `backend/sim_v2/tests/core/recommendation/test_output_validator.py`
- [ ] Post-call validation — cross-ref + consistency
- [ ] Anti-pattern catalog scan (Lesson 1 의 5 KNOWN_DIVERGENCE 자동 검사)
- [ ] Retry logic — validation fail 시 LLM 재호출 (max_retries)
- [ ] **Acceptance:**
  - 5 KNOWN_DIVERGENCE 의 자동 검출
  - Retry loop 의 max_retries 후 graceful fail

#### Task B4.4 — Defense Layer 3 (oracle integration) (W12-W14)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/recommendation/defenses/oracle_integration.py`
  - Modify: `backend/sim_v2/core/integrator/integrator.py` (oracle 호출 dependency)
- [ ] Runtime defense — proposal 등록 후 Oracle 자동 호출
- [ ] Oracle 의 PASS/FAIL_BREAKING/FAIL_DRIFT/INCONCLUSIVE 4-tier 반영
- [ ] **Acceptance:**
  - 4-tier 의 ORACLED state 전이 (ADR-003 §2)
  - FAIL_BREAKING 시 proposal 자동 reject (refine loop 대상 아님)

#### Task B4.5 — Defense Layer 4 (review UI scaffold) (W13-W15)

- [ ] **Files:**
  - Create: `frontend/src/components/sections/modeling/recommendation/ProposalReview.tsx` (UI scaffold)
  - Create: `backend/api/recommendation_review.py` (FastAPI endpoint)
  - Test: `backend/sim_v2/tests/api/test_recommendation_review.py`
- [ ] Human review gate — proposal summary + diff (schema/code/ontology) + oracle result + anti-pattern warning
- [ ] User decision: ACCEPT / REJECT / CHANGE_REQUEST / PARTIAL_ACCEPT
- [ ] **Note (feedback_ui_ux_rework.md):** UI 는 minimal scaffold — API 가 견고, UI 는 후 대대적 개편 가능성
- [ ] **Acceptance:**
  - API endpoint 의 4 decision 처리
  - UI scaffold 의 sample render

#### Task B4.6 — Anti-pattern catalog 작성 (W14-W16)

- [ ] **Files:**
  - Create: `backend/sim_v2/core/recommendation/anti_patterns/known_divergence_5.py` (Lesson 1 의 5 entry)
  - Create: `backend/sim_v2/core/recommendation/anti_patterns/facade_over_fit.py` (Lesson 4)
  - Create: `backend/sim_v2/core/recommendation/anti_patterns/fixture_no_metadata.py` (Lesson 5)
  - Create: `backend/sim_v2/core/recommendation/anti_patterns/over_categorization.py` (Lesson 2)
  - Create: `backend/sim_v2/core/recommendation/anti_patterns/silent_drift.py` (Lesson 3)
- [ ] 5 lesson 의 anti-pattern entries 등록
- [ ] Anti-pattern scanner — proposal output 의 자동 검사
- [ ] **Acceptance:**
  - 5 anti-pattern 의 entry registered
  - Sample proposal (intentionally containing pattern) 의 검출

### 3.5 Phase B5 (W12-W20) — Extension Architecture Validation

**Goal:** ADR-013 의 Tier 1 + Tier 2 의 stress test, G4 gate 통과.

**Owner:** Member B + Lead.

#### Task B5.1 — Banking plugin extension 작성 (W12-W14)

- [ ] **Files:**
  - Create: `backend/sim_v2/plugins/banking/dispatchers/drools_kbase_lookup.py` (BANKING-DESIGN §10.1)
  - Create: `backend/sim_v2/plugins/banking/annotations/compensable.py` (§10.2)
  - Create: `backend/sim_v2/plugins/banking/aop/tenant_context.py` (§10.3)
  - Create: `backend/sim_v2/plugins/banking/bytecode/bpmn_dynamic_class.py` (§10.4)
  - Test: `backend/sim_v2/tests/plugins/banking/extensions/test_*.py`
- [ ] 4 plugin extension 의 ADR-013 §2 의 register_* API 호출
- [ ] Plugin manifest 의 `[extensions]` declaration
- [ ] **Acceptance:**
  - 4 extension 의 plugin_loader 자동 등록
  - core 의 SIGNATURE_LOCKED 가 4 case 에서 extension 호출 (G4 gate 의 input)

#### Task B5.2 — Broadleaf plugin extension (W14-W17)

- [ ] **Files:**
  - Create: `backend/sim_v2/plugins/broadleaf/aop/configurable_handler.py` (BROADLEAF-ONBOARDING §6.2)
  - Create: `backend/sim_v2/plugins/broadleaf/aop/dynamic_field.py`
  - Create: `backend/sim_v2/plugins/broadleaf/dispatchers/factory_dispatch.py`
  - Create: `backend/sim_v2/plugins/broadleaf/bytecode/dynamic_entity_dao_proxy.py`
  - Create: `backend/sim_v2/plugins/broadleaf/extensions/mvel_offer_rule.py` (escape hatch — RATIONALE.md 의무)
  - Create: `backend/sim_v2/plugins/broadleaf/extensions/RATIONALE.md`
  - Test: `backend/sim_v2/tests/plugins/broadleaf/extensions/test_*.py`
- [ ] 5-6 plugin extension (BROADLEAF-ONBOARDING §6.2 의 list)
- [ ] RATIONALE.md 의 escape hatch 정당화
- [ ] **Acceptance:**
  - 5-6 extension 의 plugin_loader 자동 등록
  - Broadleaf 의 4 meta-programming 영역 모두 cover

#### Task B5.3 — Extension promotion path test (W17-W20)

- [ ] **Files:**
  - Test: `backend/sim_v2/tests/core/extensibility/test_promotion_path.py`
  - Modify (if promotion 발생): `backend/sim_v2/core/synthesizer/dispatchers/__init__.py` (새 dispatch_kind 추가)
- [ ] 시뮬: 여러 plugin 에서 동일 extension 반복 등장 — 가상 case
- [ ] Promotion 절차 검증 (ADR-013 §6.3 Phase 3)
- [ ] **Acceptance:**
  - Promotion 후 backward compat (existing plugin 의 register 시 ConflictError, default core 로 fallback)
  - Framework version bump (semver minor) 의 절차 명시

#### Task B5.4 — G4 gate report (W20)

- [ ] **Files:**
  - Create: `gates/g4_report.md`
- [ ] Extension 등록 case list (Banking 4 + Broadleaf 5-6 + v2 minimal)
- [ ] Framework core 변경 없음 확인 (`backend/sim_v2/core/synthesizer/dispatchers/__init__.py` 등의 git diff 0 line)
- [ ] Promotion path 시뮬 결과
- [ ] **Acceptance:**
  - Framework core 의 4 ADR (006-009) 변경 0
  - 모든 새 meta-programming case 는 plugin extension 으로 흡수

---

## 4. Cross-validate Gates (G1-G4)

### 4.1 G1 — Framework core contract 검증 (W10)

**조건:**
- 3 system 각 UC1 (풀 시연) 1건 성공 (v2 / Broadleaf / Banking)
- 3 plugin 의 7 artifact 모두 작성됨
- R3 (동일 input → 동일 output) 보장 확인

**Tasks:**
- [ ] **Files:**
  - Create: `gates/g1_report.md`
  - Run: `pytest backend/sim_v2/plugins/v2-slab-design/fixtures/`, `pytest backend/sim_v2/plugins/broadleaf/fixtures/`, `pytest backend/sim_v2/plugins/banking/fixtures/`
- [ ] 3 system × UC1 결과 표 작성
- [ ] Plugin contract 의 strict 정도 점검 — v2-specific leak 0 (`core/` 안 grep "slab" / "v2" / "broadleaf" / "banking" → 0)
- [ ] **Acceptance:**
  - 3 system 의 UC1 PASS
  - Framework core 의 system-specific leak 0
  - **G1 fail 시:** plugin contract 수정 + W11-W12 추가 sprint

### 4.2 G2 — Meta-programming 4 영역 coverage (W14)

**조건:**
- ADR-006 (polymorphic): 8 dispatch_kind 각 system 등장 빈도
- ADR-007 (annotation): Lombok / custom processor 각 system 처리
- ADR-008 (AOP): @Aspect weaving 각 system 처리
- ADR-009 (bytecode): CGLib / custom plugin 각 system 처리

**Tasks:**
- [ ] **Files:**
  - Create: `gates/g2_report.md`
- [ ] 3 system × 4 영역 매트릭스 작성
- [ ] Unsupported case → SIGNATURE_LOCKED 발동 위치 list
- [ ] Plugin extension 등록 case 의 4 영역 coverage 확인
- [ ] **Acceptance:**
  - 4 ADR 각 영역에서 3 system 의 적용 case >= 1
  - SIGNATURE_LOCKED 의 list 가 unsupported case 만 (false positive 0)
  - **G2 fail (unsupported case 너무 많음) 시:** extension 작성 우선순위 재조정

### 4.3 G3 — Recommendation Engine (W18)

**조건:**
- 3 system 모두에서 LLM 의 reasonable proposal 생성
- Recommendation Engine 의 4 defense mechanism 작동
- LLM provider 최소 2개 (Claude + GPT) 에서 동등 quality

**Tasks:**
- [ ] **Files:**
  - Create: `gates/g3_report.md`
- [ ] 3 system × 2+ provider 매트릭스 (Claude / OpenAI / Gemini)
- [ ] Proposal quality manual review — UC4 (schema 추천) 의 sample case 5건
- [ ] 4 defense layer 모두 작동 확인
- [ ] **Acceptance:**
  - 3 system × 2 provider = 6 cell 의 reasonable proposal
  - Anti-pattern catalog scan 의 5 entry 작동
  - **G3 fail (특정 provider quality 낮음) 시:** `allowed_providers` 조정

### 4.4 G4 — Extension architecture (W20+)

**조건:**
- Banking Drools integration 이 plugin extension 으로 흡수
- Broadleaf enterprise-specific case 가 SIGNATURE_LOCKED + extension path 처리
- 새 meta-programming case 추가 시 framework 자체 변경 X

**Tasks:**
- [ ] Phase B5.4 의 `gates/g4_report.md`
- [ ] **Acceptance:**
  - Framework core 의 git diff 0 (Phase B5 동안)
  - Banking 4 + Broadleaf 5-6 + v2 minimal extension 의 모든 ADR-013 §2 register_* API 통과
  - **G4 fail (framework core 변경 발생) 시:** ADR-013 의 contract 재검토

---

## 5. Dependency Graph

### 5.1 Task-level dependencies

```
A1.1 (git tag) ───┐
                  ├──→ A1.2 (lessons review)
                  │       │
                  │       └──→ A2.1 (manifest + contracts) [W3]
                  │                  │
                  │                  ├──→ A2.2 (entities + mappings) [W4]
                  │                  │           │
                  │                  │           └──→ A2.3 (emitters) [W5]
                  │                  │                       │
                  │                  │                       └──→ A2.4 (fixtures) [W6]
                  │                  │                                   │
                  │                  │                                   └──→ A2.5 (aspects + 통합) [W7]
                  │                  │                                               │
                  │                  │                                               └──→ A3.1 (UC1) [W6, partial]
                  │                  │                                                                │
                  │                  │                                                                └──→ A3.2 (UC2) [W8]
                  │                  │                                                                              │
                  │                  │                                                                              └──→ A3.3 (UC3) [W10]
                  │
B1.1 (schema entity) ──→ B1.2 (migration) ──→ B1.3 (extractor) ──→ B1.4 (cross-layer query) [W4]
                                                                          │
                                                                          └──→ Task B4.2 (grounding) [W10]

B2.1 (proposal model) ──→ B2.2 (Integrator API) ──→ B2.3 (revision) ──→ B2.4 (oracle protocol) [W6]
                                                          │                        │
                                                          │                        └──→ B4.4 (oracle integration) [W12]
                                                          │
                                                          └──→ A3.3 (UC3, R5)

B3.1 (v2) === A2.1-A2.5 (Track A 와 cross-share)
B3.2 (Broadleaf) ─[independent]→ G1 gate (W10)
B3.3 (Banking) ─[independent]→ G1 gate (W10)

B4.1 (provider) ──→ B4.2 (grounding) [parallel] ──→ B4.3 (validator) ──→ B4.4 (oracle) ──→ B4.5 (review UI) ──→ B4.6 (anti-pattern) [W14]
                                                                                                                              │
                                                                                                                              └──→ G3 gate (W18)

B5.1 (Banking ext) ─[parallel]→ B5.2 (Broadleaf ext) ─[parallel]→ B5.3 (promotion test) ──→ B5.4 (G4 report) [W20]
```

### 5.2 Sprint-level dependencies

```
W1-W2  ┃ A1 (lessons + tag)                B1.1-B1.2 (schema entity + migration)       B2.1 (proposal model)
W3-W4  ┃ A2.1-A2.2 (v2 contracts + entities)  B1.3-B1.4 (extractor + query)            B2.2-B2.3 (Integrator + revision)
W5-W6  ┃ A2.3-A2.4 (v2 emitters + fixtures)   B2.4 (oracle)                            B3.2-B3.3 (Broadleaf + Banking 시작)
W7-W8  ┃ A2.5 (v2 aspects + 통합) + A3.1 (UC1)  B3.2-B3.3 (계속)                          B4.1 (provider)
W9-W10 ┃ A3.1-A3.2 (UC1+UC2)                  G1 gate                                  B4.2 (grounding)
W11-W12┃ A3.3 (UC3)                           B4.3 (validator)                          B5.1 (Banking ext)
W13-W14┃                                       B4.4-B4.5 (oracle + review UI)            G2 gate
W15-W16┃                                       B4.6 (anti-pattern catalog)               B5.2 (Broadleaf ext)
W17-W18┃                                       G3 gate                                   B5.3 (promotion test)
W19-W20┃                                       Phase 1 closure + G4 gate                 B5.4 (G4 report)
```

---

## 6. Acceptance Criteria Summary

### 6.1 Per-track final acceptance

| Track | Acceptance |
|---|---|
| Track A — v2 verification | UC1 / UC2 / UC3 모두 PASS, R3-R5 보장, 5 fixture (S1'-S5') PASS, v2 plugin 의 7 artifact 통합 |
| Track B — Framework | 5-layer ontology + Integrator + Recommendation Engine + 3 plugin (v2/Broadleaf/Banking) 모두 작동, G1-G4 gates 모두 PASS |

### 6.2 Gate 의 cumulative acceptance

| Gate | Cumulative Acceptance |
|---|---|
| G1 (W10) | 3 system 의 UC1 + plugin contract 의 system-specific leak 0 |
| G2 (W14) | + 4 meta-programming 영역 각 system 적용 |
| G3 (W18) | + Recommendation Engine 의 reasonable proposal × 3 system × 2 provider |
| G4 (W20+) | + Extension architecture 의 framework core 변경 0 |

### 6.3 Phase 1 closure (W20+)

- 4 gate 모두 PASS
- Cost: 650-1000h 안 (M1 gate W4 의 re-estimate 의 +/- 10%)
- All 13 ADR 의 contract 명세 코드로 구현됨
- 사용자 메모리 R1-R5 의 5 requirement 모두 verifiable

---

## 7. Sprint Cadence

### 7.1 2-week sprint structure

- **Sprint planning** (매 sprint 시작 월요일, 30min)
  - 이전 sprint review
  - 본 sprint task pickup (per-task acceptance criteria 확인)
  - Cross-track sync (Track A ↔ Track B)
- **Daily standup** (15min) — optional but recommended
- **Sprint review + retro** (sprint 종료 금요일, 60min)
  - 산출물 demo
  - Retro: 학습 / blocker / next sprint adjust

### 7.2 Gate review session (각 gate 직후)

- **G1 review** (W10 직후, 90min): G1 report walk-through, fail 항목 fix plan
- **G2 review** (W14 직후): same
- **G3 review** (W18 직후): same
- **G4 review** (W20+ 직후): Phase 1 closure decision

### 7.3 M1 cost re-estimate (W4)

- Phase B1 + Phase A1 완료 시점
- Cost actual vs estimated 비교
- 1 plugin reduction 검토 (만약 spike > +30%)

---

## 8. Risk Register + Contingency

### 8.1 High-impact risks

| ID | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Cost spike (Total > 1000h+30%) | Medium | High | M1 (W4) gate 후 cost re-estimate. 1 plugin reduction 검토 (가장 가능: Banking 단순화) |
| R2 | 3-way churn — conflicting framework signal from 3 plugin | Medium | High | Plugin contract strict from day 1. G1-G2 빈도 ↑. Cross-validate gate W10 + W12 추가 가능 |
| R3 | Broadleaf 의 @Configurable JPA entity 합성 trap | High | High | W4 prototype + W8 plugin extension `broadleaf.configurable_handler` 완성. Lesson 1 의 contract validator strict |
| R4 | Banking Drools KIE container Python emulation 불가 | High | Medium | SIGNATURE_LOCKED + specific rule fixture 만 manual emit. ADR-013 의 escape hatch (`extensions/`) 활용 |
| R5 | Phase α 와 새 v2 plugin 의 R3 equivalence 실패 | Medium | High | W9-W10 regression check. Phase α silent bug 발견 시 새 plugin 이 올바름 — accept |
| R6 | LLM provider 1 fail (Gemini 등) | Low | Medium | `allowed_providers` 의 G3 gate 후 조정. 2 provider (Claude + GPT) 최소 보장 |
| R7 | 1 system stuck → 전체 지연 | Medium | Medium | Per-system independent track. Stuck system 은 partial onboarding 로 G2/G3 통과 |

### 8.2 Medium-impact risks

| ID | Risk | Mitigation |
|---|---|---|
| R8 | Banking 가상 → real-world 검증력 약함 | Drools/BPMN/multi-tenant/saga 의도 포함으로 보완. Broadleaf 가 real-world 보완 |
| R9 | Broadleaf enterprise-only feature 결손 | Community-only scope. Enterprise = phase 2 plugin extension |
| R10 | Provider API 변경 (Anthropic / OpenAI / Google) | Provider adapter test 의 isolated suite. Quarterly review |
| R11 | Phase α lessons 추출 underestimate | W1-W4 buffer 있음. 본 implementation plan session 안에서 이미 5 lesson drafted |
| R12 | Section 2 본체 의 ORM composite PK 미완 (source-code-fixes D-1) | Implementation phase 의 Section 2 작업으로 분리. Plugin onboarding 의 blocker 아님 |
| R13 | 5-layer ontology query performance | UC4 의 cross-layer join 의 EXPLAIN ANALYZE — phase 2 indexing |

### 8.3 Low-impact risks

| ID | Risk | Mitigation |
|---|---|---|
| R14 | UI 의 review gate scaffold 의 prematurity (feedback_ui_ux_rework.md) | Minimal UI, robust API. UI rework 가능성 명시 |
| R15 | Sprint planning overhead | 30min cap. Tools: TODO.md + CHANGES.md (modeling section) |
| R16 | Documentation drift | 매 sprint 종료 시 CHANGES.md 갱신 의무 (CLAUDE.md `Ad-hoc Change Protocol` 일관) |

---

## 9. Implementation Phase 인계 (W21+)

본 plan 의 W1-W20 종료 후 implementation phase 의 진행:

### 9.1 인계 산출물

| Artifact | 위치 | 인계 form |
|---|---|---|
| 13 ADR | `sim-redesign/ADR-*.md` | reference |
| spec.md | `sim-redesign/spec.md` | reference |
| MILESTONES-2track.md | `sim-redesign/MILESTONES-2track.md` | reference |
| 5 lessons | `sim-redesign/lessons/phase-alpha-*.md` | reference + anti-pattern catalog source |
| 3 sub-design (V2-MIGRATION / BROADLEAF-ONBOARDING / BANKING-DESIGN) | `sim-redesign/*.md` | per-plugin onboarding playbook |
| 본 implementation-plan.md | `sim-redesign/implementation-plan.md` | sprint task tracker |

### 9.2 Implementation phase 의 첫 work item

W21 의 첫 task = phase 1 의 production readiness review:
- 4 gate report (`gates/g{1-4}_report.md`)
- Cost actual vs D6 estimate
- Phase 2 priority (Out of scope §1.2 의 7 item) decision
- 3 plugin 의 ongoing maintenance plan

### 9.3 Phase 2 후보 work

| # | Item | Priority indicator |
|---|---|---|
| 1 | UC5 (Code Recommender) full implementation | high |
| 2 | UC6 (Ontology Evolver) full implementation | medium |
| 3 | Cross-plugin proposal saga | medium |
| 4 | 4th+ reference system onboarding | low |
| 5 | NoSQL schema layer | low |
| 6 | Cost-aware / quality-aware LLM routing | low |
| 7 | Sharding / partitioning schema modeling | low |

본 priority 는 정량 X — Phase 1 종료 후 사용자 결정.

---

## 10. 참조

### 본 implementation plan session 의 sibling artifacts (모두 `sim-redesign/`)

- `spec.md` — Two-Engine Plugin Framework 의 정식 spec
- `MILESTONES-2track.md` — 2-Track sprint plan (W1-W20)
- `DECISIONS-CONFIRMED.md` — 12 결정 verbatim
- `ADR-001` ~ `ADR-013` (13 ADR)
- `lessons/phase-alpha-known-divergence.md` (L1)
- `lessons/phase-alpha-idiom-cards.md` (L2)
- `lessons/phase-alpha-manual-twin.md` (L3)
- `lessons/phase-alpha-facade.md` (L4)
- `lessons/phase-alpha-fixture.md` (L5)
- `V2-MIGRATION.md`
- `BROADLEAF-ONBOARDING.md`
- `BANKING-DESIGN.md`

### Brainstorming 산출물 (history reference)

- `SYNTHESIS-ROUND2.html` — Round 2 종합
- `META-PROGRAMMING.html` — 4 meta-programming worked example
- `DESIGN-SYNTHESIS.html` / `DESIGN-WALKTHROUGH.html` — Round 1

### 메모리

- `feedback_simulation_design.md` — no MVP, 풀 시연 필수
- `project_decisions_v4_action.md` — 4-layer + 7-case
- `project_sim_redesign_decisions.md` — 본 sim-redesign track 의 status (갱신 예정)
- `feedback_ui_ux_rework.md` — Section 2 UI 의 대대적 개편 가능성
- `feedback_scale_100k.md` — 100K+ 문서 규모 가정 (Broadleaf scope decision 의 input)
- `feedback_verify_before_demo.md` — 데모 전 verify 의무

### Section 2 본체 (cross-section reference)

- `toClaude/modeling/CHANGES.md` — modeling 섹션의 ongoing change log
- `toClaude/modeling/TODO.md` — modeling 섹션의 ongoing task list
- `toClaude/modeling/section4-verification/` — Phase α 산출물 (archived via `phase-alpha-snapshot` tag)
