# Perspective: Architect — System-Agnostic Generalization

## 1. Summary

Round 1's Anchored Twin Synthesizer collapses cleanly into a **framework core + system plugin** pair: every mechanism (2-layer synthesis, typed contract layer, deterministic gap surface, semantic trace diff) is universal and stays in `backend/modeling/sim_verify/core/`; every v2-specific detail (79 slot keys, 5 KNOWN_DIVERGENCE facades, 9 JPA repo shape, 4 Maven module geometry, Spring DI / `@Transactional` boundaries) collapses into per-system plugin folders under `plugins/<system>/`. New system onboarding becomes a fixed checklist of plugin artifacts plus an ontology import, never a core-engine change. The pivotal generalization lever is **`code_types.role` (domain / framework / infra)** which the v4 ontology already records — that single column lets the framework auto-derive twin scope, registry namespace selection, and stub adapter wiring without any system-specific glue.

## 2. Generalized architecture

Universal layers sit in `core/`. Pluggable layers sit in `plugins/<system>/`. The 5-layer Schema (added by ADR-002) is itself a universal ontology table; only its rows are system-scoped.

```
                +-------------------------- onTong Sim Core (universal) --------------------------+
                |                                                                                |
ontology.db --->|  CoreLoader  (queries actions/realizations/anchor_bindings/                    |
(any repo_id)   |               code_methods/code_types/code_fields/type_realizations            |
                |               + schema_tables/schema_columns)                                  |
                |       |                                                                        |
AST cache  ---->|  ASTLoader   (multi-language: java/cobol/csharp/python via tree-sitter)         |
                |       |                                                                        |
                |       v                                                                        |
                |  ScopeRouter (reads code_types.role → twin in/stub/out per role)               |
                |       |                                                                        |
                |       v                                                                        |
                |  Synthesizer ---- Layer 1: slot_registry  <-- plugin: registry/<system>/*.yaml  |
                |                 \ Layer 2: ast_visitor    <-- plugin: ast_rules/<lang>/*.py     |
                |                  \ Layer 3: stub_router   <-- plugin: stubs/<system>/*.py       |
                |       |                                                                        |
                |       v                                                                        |
                |  ContractGate (typed Protocol smoke-test, version-pinned)                       |
                |       |          ^                                                              |
                |       |          | plugin: contracts/base.py + contracts/<system>/*.py          |
                |       v                                                                        |
                |  GapSurfacer (pure fn of ontology rows → # UNCLEAR + gap-report.json)          |
                |       |                                                                        |
                |       v                                                                        |
                |  TwinRunner  ----------- stubs from plugins/<system>/stubs/* (DI, TX, clock)     |
                |       |                                                                        |
                |       v                                                                        |
                |  OracleDiffer (semantic per-action trace diff + R3 byte equality)              |
                +--------------------------------------------------------------------------------+
                          ^                                                  ^
                          |                                                  |
              plugins/<system>/role_rules.json                  plugins/<system>/twin_scope.toml
              plugins/<system>/registry/*.yaml                  plugins/<system>/contracts/*.py
              plugins/<system>/stubs/*.py                       plugins/<system>/ast_rules/*.py
```

Components labelled **Core** are written once. Components labelled **plugin** are duplicated per onboarded system. The Recommendation Engine (ADR-002 D2) reuses the same plugin set as its oracle — recommendations validate by re-invoking the same Synthesizer + TwinRunner + OracleDiffer.

## 3. Pluggable layers

### Registry namespacing

The Layer 1 registry is keyed by `(system_id, target_slot)`. v2's 79 distinct `target_slot` (verified in `anchor_bindings` of `slab-design-real-v2`) live in `plugins/slab-design/registry/`. A bank-credit system would put its own `target_slot` set (e.g., `atomic.credit_score.bound_check`, `body.regulatory_disclosure`) in `plugins/bank-credit/registry/`. The framework imports the registry module dynamically via `repo_id → system_id` map (a single `system_index.toml` at workspace root). Slot collisions across systems are by construction impossible because the registry table is namespaced.

A **base registry** at `core/registry/base/` contains ~20 truly universal slots (`atomic.null_check`, `atomic.range`, `body.branch`, `body.set_output`, `body.compute`) that any system can opt into by listing them in its `system.toml`. v2 reuses ~12 of these directly; new systems start from this base and extend.

### Contract base + system extensions

`core/contracts/base.py` defines language-runtime Protocols used by virtually any Java system: `BigDecimal`, `MathContext`, `RoundingMode`, `LocalDateTime`, `AtomicLong`, `RuntimeException`. v2's `AlgorithmException` is a system extension at `plugins/slab-design/contracts/algorithm_exception.py`, inheriting `RuntimeException`. The bank-credit system would add `CreditScoringException`, `RegulatoryCode` etc. The `ContractGate` smoke test (M2 mandate) runs over `base ∪ <system>` at synthesis start; mismatch fails the build before any Python is generated, killing α's KNOWN_DIVERGENCE class at the framework boundary.

### Stub adapters (framework adapter)

The stub adapter layer abstracts framework-specific runtime infrastructure. `core/stubs/abstract.py` defines pure abstract base classes: `DIContainerStub`, `TXBoundaryStub`, `ClockStub`, `SeqStub`, `DataAccessStub`. Per-system implementations:

- `plugins/slab-design/stubs/spring_di.py` — Spring `@Autowired/@Component` → constructor list extracted from AST → manual wiring
- `plugins/slab-design/stubs/jpa_inmem.py` — Spring Data JPA derived-query name parser → in-memory dict access
- `plugins/slab-design/stubs/transactional.py` — `@Transactional` → session journal with rollback
- A hypothetical `plugins/bank-credit/stubs/cdi.py` for CDI / Guice instead of Spring.

The framework picks the stub via a thin **stub registry** in `plugins/<system>/stub_registry.toml` (annotation FQN → stub class). This makes Spring vs Guice vs CDI a swap, not a rewrite.

### Code role classification (auto + override)

The framework calls `ScopeRouter.classify(code_type_fqn)` which reads `code_types.role` (already populated by Section 2 extraction; verified: 85 domain / 2 framework / 41 infra in v2). Default mapping is universal: `domain → twin in`, `framework → stub`, `infra → out`. Per-system override at `plugins/<system>/role_overrides.yaml` can promote a specific FQN (e.g., a hand-picked infra class `MyTimeProvider` becomes twin-in). When the ontology extractor mis-classifies a class, the override is one YAML line — no code change.

## 4. System onboarding workflow

Adding a new system "**`<sys>`**" is exactly seven artifacts plus an ontology import (order matters — each is a precondition for the next):

1. **Ontology import** — run Section 2's pipeline against the repo; rows tagged `repo_id=<sys>`.
2. **`plugins/<sys>/system.toml`** — `name`, `language`, `framework`, `base_contract_subset`, `default_twin_scope`.
3. **`plugins/<sys>/role_overrides.yaml`** — empty if `code_types.role` extraction is perfect; else per-FQN overrides.
4. **`plugins/<sys>/registry/`** — slot templates for system-specific `target_slot`: `<lang>_pattern`, `py_emitter`, `runtime_imports`.
5. **`plugins/<sys>/contracts/`** — system-specific Protocols extending base.
6. **`plugins/<sys>/stubs/`** — system framework stubs (DI, TX, ORM adapter).
7. **`plugins/<sys>/twin_scope.toml`** — explicit in / stub / out boundary table.
8. **`plugins/<sys>/golden/`** — at least one golden trace fixture for R3 validation.

`python -m sim_verify validate-plugin <sys>` (a) loads `system.toml`, (b) cross-checks every `target_slot` has registry coverage, (c) runs `ContractGate.smoke()`, (d) confirms every annotation FQN has a stub mapping. Onboarding completes when green.

## 5. Hypothetical 2nd system worked example

Take **`bank-credit`**: a Java SpringBoot loan-application scoring engine. ~600 classes, Spring Data JPA, `@Transactional`, BigDecimal monetary amounts, custom `CreditScoreException`. Distinct from v2: (a) MyBatis alongside JPA, (b) Reactor `Mono<>` async types, (c) `RegulatoryDisclosureService` calls must be journaled for audit.

Onboarding step by step:

1. **Ontology import** — `repo_id=bank-credit`. ScopeRouter reads `code_types.role`; say 320 domain / 8 framework / 272 infra.
2. **`system.toml`** — `language=java`, `framework=spring`, `base_contract_subset=[BigDecimal, MathContext, RoundingMode, LocalDateTime, RuntimeException]` (no `AtomicLong` — bank-credit doesn't use it; explicit subset stops accidental import).
3. **`role_overrides.yaml`** — extractor mis-classified `LoanRule` as infra; one-line override to domain.
4. **`registry/`** — ontology produced 110 distinct `target_slot`. ~30 reuse `core/registry/base`. Of the remaining 80, ~25 mirror v2's shape (`body.service_lookup`, `body.dg_throw`, `body.compute_arith`) and copy v2's emitter with renamed imports — **content reuse across systems**. ~55 are genuinely new (`atomic.credit_score.fico_bucket`, `body.regulatory_disclosure`, `body.mybatis_select`).
5. **`contracts/`** — `CreditScoreException extends RuntimeException`; `RegulatoryCode` namespace class; `Mono` Protocol modeling `subscribe()` + `block()` returning twin-synchronous result.
6. **`stubs/`** — reuse v2's `spring_di.py` and `transactional.py` unchanged. New: `mybatis_mapper_stub.py` (XML mapper → dict-of-functions stub), `reactor_mono_stub.py` (Mono.just/subscribe → sync resolve).
7. **`twin_scope.toml`** — `reactor.core.publisher.Flux → out (SIGNATURE_LOCKED)`; `Mono → stub via reactor_mono_stub`; `@Async → stub (synchronous execution)`.

**Compared to v2:**
- **Same**: synthesizer core, gap surfacer, oracle differ, trace contract, `# UNCLEAR` emission, R5 workflow, Spring DI stub, `@Transactional` stub.
- **Different**: 55 new registry entries, 2 new stub adapters, one new contract family, a new out-of-scope row.
- **Auto-handled**: scope routing per role, contract smoke gate, gap surface, semantic trace diff, recommendation engine LLM context (reads ontology + ast + git blame; v2 vs bank-credit agnostic).

Net plugin work: ~3000 LOC. Core: 0 LOC churn — the key invariant.

## 6. What stays system-specific

- **Registry entries** for system-specific `target_slot` values. v2 contributes 79 entries; base/core provides ~20 reusable; net delta per system is the system's unique slot count.
- **Facade implementations** that satisfy base contracts in idiosyncratic ways (e.g., bank-credit's BigDecimal might need a different default `MathContext` for monetary rounding than v2's measurement rounding — same Protocol, different facade).
- **Framework stub adapters** for the system's DI / persistence / messaging stack.
- **`twin_scope.toml`** boundary decisions — what's stub vs out.
- **Golden fixtures** for R3 validation.

## 7. What can be auto-derived

- **Scope classification** — `code_types.role` is universal across systems (already populated by Section 2 extractor).
- **Anchor coverage metric** — `count(anchored_methods) / count(domain_methods)` is a system-agnostic gate.
- **Trace contract** — `TraceCollector.anchor(slot, line)` is core; no system extension needed.
- **Gap surface formula** — pure function of `verification_level / confidence / confirmed / anchor presence`; same for all systems.
- **Per-action trace diff format** — universal (M3 mandate).
- **R5 workflow steps** — same five steps regardless of system.
- **Determinism property** — `(ontology_revision, ast_hash) → python_bytes` is universal.
- **Contract version pin smoke test** — universal mechanic.

## 8. Multi-language considerations

Java is not load-bearing in the framework. The synthesizer's input is `(ontology_rows, parsed_ast, type_resolution)`. Tree-sitter has grammars for Java, COBOL (via `tree-sitter-cobol`), C#, Python, Go, and many more. To support COBOL legacy: write `plugins/<sys>/ast_rules/cobol.py` (Layer 2 visitor for COBOL grammar) and a `plugins/<sys>/contracts/cobol_runtime.py` (PIC clause → Python value-type Protocols). The Layer 1 registry is language-agnostic because templates are output-side (`py_emitter`); the input side is a pattern matched against the parsed AST node, which exists in any language.

**Real limits**:
- The Python target itself caps applicability — languages whose memory model can't be modeled in Python (low-level C with explicit pointer arithmetic, real-time embedded with hardware interrupt semantics) need either a different target language for the twin, or a SIGNATURE_LOCKED policy that strands those methods.
- Untyped dynamic source (e.g., raw JavaScript) makes type_realizations brittle — Section 2's confidence drops.
- The contract base must be re-scoped per language family. `BigDecimal` is Java-flavoured; COBOL would substitute `PIC S9(9)V99 COMP-3`. That's expected; the framework supports parallel contract bases (`core/contracts/java.py`, `core/contracts/cobol.py`).

## 9. Round 1 design diff

| Round 1 component | Round 2 generalization |
|---|---|
| `Synthesizer` singleton | Synthesizer parameterized by `system_id`; loads plugins dynamically |
| Registry with 79 v2 slots | `core/registry/base` (universal) + `plugins/<sys>/registry/` (per-system) |
| 5 facade classes (v2 KNOWN_DIVERGENCE) | `core/contracts/base.py` + `plugins/<sys>/contracts/` |
| Spring DI / JPA / @Transactional stubs hard-coded | `core/stubs/abstract.py` + `plugins/<sys>/stubs/`, framework picked via `stub_registry.toml` |
| Twin Scope Boundary fixed in ADR-002 v1 | Per-system `twin_scope.toml` |
| `code_types.role` implicit | Explicit ScopeRouter, role_overrides.yaml escape hatch |
| Single ontology DB | Multi-tenant `repo_id` already in schema; framework reads system_id from repo_id |
| Recommendation engine (new) | Sits alongside Verification Engine, calls it as oracle; shares plugin set per-system |

## 10. Failure modes

- **System with no anchor coverage** — synthesizer falls back to 100% Layer 2 AST; gap-report.json overflows. Action: Section 2 anchor extraction investment.
- **Framework stack outside catalog** (e.g., Quarkus + Panache instead of Spring + JPA) — ContractGate smoke fails on missing stub. Action: one-time plugin work.
- **Language without tree-sitter grammar** — framework refuses to load with explicit error.
- **Recommendation engine hallucinates schema diff outside registry patterns** — Verification Engine rejects (twin can't synthesize); flagged invalid, returned to LLM with structured failure. Retry bound at 3.
- **Plugin registry template calls symbol absent from contracts** — ContractGate smoke fails at plugin validation; activation blocked until fixed.

## 11. Honest weaknesses

- **Generalization costs plugin scaffolding per system** — 7 artifact types × N systems. A one-off verification isn't free; needs a thin "scratch system" mode (Layer 2 only, no registry).
- **`code_types.role` quality is Section-2 dependent.** If auto-classifier is 20% wrong, ScopeRouter mis-routes and the user writes boring `role_overrides.yaml`.
- **Recommendation engine validity depends on plugin completeness.** A bank-credit schema-change recommendation can't be validated until the regulatory-disclosure stub exists.
- **Cross-system slot copy-paste is human judgement.** Whether bank-credit's `body.service_lookup` semantically equals v2's is the plugin author's call; framework doesn't enforce slot-name commonality.
- **Plugin authoring is a new skill.** onTong needs documented workflow + sample plugins + `plugins/_template/` scaffolder; without it, abstraction becomes onboarding friction.
- **Recommendation LLM reasoning shape is unresolved.** Prompt schema must be specified before D2 ships; this exploration sketches the boundary but defers reasoning shape to the Recommendation perspective.
