# Perspective: Skeptic — Round 2 Risk Catalog

## 1. Summary

ADR-002 doubles scope along two orthogonal axes (system-agnostic + LLM-based Recommendation Engine) on top of an Anchored Twin Synthesizer that has not yet shipped a single byte-identical run for v2 itself. Verification is deterministic/falsifiable; Recommendation is non-deterministic/persuasive — yet ADR-002 frames Verification as Recommendation's "oracle" with no documented interaction protocol. **Most critical finding: ADR-002 reframes 10 of 13 grills as "system-agnostic abstractions" without naming a single non-v2 reference system, while adding three grills (G11-G13) for a Schema Layer absent from the current 17-table ontology — the v2 numbers in `data/ontology.db` (38 actions, 163 anchors, 79 slots, 985 code_methods, 128 code_types split 85 domain / 41 infra / 2 framework, 36 type_realizations with only 22 confirmed, 56 single-anchor slots) were induced from one repo, so treating them as a general framework instance is a category error.**

## 2. System-agnostic 의 limit

ADR-002 D1 names v2-specific assets to generalize (79 slot / 5 KNOWN_DIVERGENCE / 9 JPA repo) but does not name **language**, **paradigm**, or **runtime** scope.

1. **Language scope undefined.** Synthesizer presupposes tree-sitter Java, Java AST nodes, Java idioms (`BigDecimal`, `@Transactional`). A COBOL 60K-LOC mainframe has no `BigDecimal` analogue (COMP-3 packed decimal), no annotation DI, and tree-sitter-cobol quality varies. Layer 1's `(java_pattern, py_emitter, runtime_imports)` triple is Java-specific. Per-language Layer 1 explodes; cross-language abstract Layer 1 contradicts deterministic dispatch.

2. **128 code_types role classifier is empirical, not theoretical.** Tuned to v2's Spring + JPA via heuristics ("package = `*.repository.*` → infra"). A Guice / hexagonal / PetClinic system will not match. G1' says "auto + 사용자 override" — if 30% need override per new system, "system-agnostic" collapses to "per-system manual classification."

3. **G2'-G5' aspirational handwaves.** The 9 JPA repos include `findByCmpCdAndOrgCdAndGradeCdAndProductCdAndCustomerCdAndHrTgtWidthLowLessThanEqualAndHrTgtWidthHighGreaterThanEqualOrderByPriorityAsc(...)` — a 146-char Spring-derived-query DSL with no MyBatis or JDBC analogue. Stubbing each pattern means different parser, different stubs, different smoke-test surface. "Data access pattern abstract" is a name, not a mechanism.

4. **Patterns beyond layered monolith break twin shape.** Event sourcing, CQRS, microservices break "one method body → one Python function". v2's `SdDesigner.design` is in-process synchronous; a microservice version has a network call replacing `cast_spec_service.lookup(...)` — twin must stub network (loses failure modes) or embed mock service (re-introduces contract gap at higher layer).

5. **Onboarding cost not estimated.** v2 took ≥ 50h. ADR-002 implies one-time per-system overhead with reusable mechanism. Without a worked second example, the framework is exactly one instance wide.

## 3. Recommendation Engine 의 LLM 위험

1. **Non-determinism collides with Verification's determinism.** Even at `temperature=0`, prompt-context drift (model version, context-window truncation, tool-call ordering) produces different proposals. Approved proposal → ontology revision changes → Verification synthesizer output changes. Recommendation is not pin-able by input hash if it depends on LLM weights. ADR-002 unspecified.

2. **Hallucination.** LLM asked "add table for thickness override" might propose `slabId` (FK to `SDSlabEntity.slabNo`) — but v2's actual identifier is `slabNoSeq` from `SlabNoSequence` (AtomicLong-based, per Round 1 skeptic §2.6). If context window omits the relevant rows, it invents plausible names. No falsifiability gate.

3. **Prompt context overflow.** Memory `feedback_scale_5k_classes.md` assumes 5000+ classes. 5K types × ~50 tokens = 250K tokens for code_types alone. Add code_methods (5K-30K rows), code_fields, call_sites, anchors, terms — multi-million tokens for a real legacy system. ADR-002 §"LLM context" says "Read: ontology 전체" as if it fits. It does not. Selective retrieval (RAG) is required and unspecified.

4. **"스키마 추천" scope under-specified.** Can mean DDL only / + data migration / + rollback / + index / + partition / + replication. v2's production DB is not in ontology (17 tables in `data/ontology.db` are about the ontology). Each scope is a different engineering project. ADR-002 picks none.

5. **LLM normalization is statistically wrong.** 3NF vs denormalized needs read/write access pattern. LLM without query-log access will not reliably choose between extending `SD_SLAB` (cheap reads, expensive history) vs new `SD_SLAB_THICKNESS_OVERRIDE` (cheap writes, JOIN cost).

6. **Verification gap of LLM reasoning.** "This is the right column" needs (a) `effectiveFrom` term in ontology, (b) action references it, (c) `NOW()` is right backfill default. (c) requires business judgment, not ontology consultation. LLM does not know to ask.

## 4. Two-engine sync issues

1. **Lifecycle ambiguity.** Proposal at t=0: when staged vs applied, who applies (Recommendation / human / CI), does Verification consume staged or applied? Report against `current` while proposal is `proposed` shows no oracle answer.

2. **Concurrent access.** User A: "add `thickness_override`"; User B: "rename `slab_thickness`". Schema-migration tools (Liquibase / Alembic) handle DDL only, but Recommendation also proposes ontology edits (G11) and code edits (UC5). Source-of-truth unspecified.

3. **Audit trail immutability.** Verification produces reproducible artifacts. Recommendation produces LLM completions. If rationale is "based on pattern in `SdSlabSaveAction.java:51`", **user cannot tell whether LLM inspected the line or hallucinated**. Current `audit_log` (`before_json` / `after_json` / `user_id`) is shaped for human edits, not "LLM looked at these tokens and decided this." LLM reasoning provenance is not represented.

4. **Silent-wrong-direction.** Recommendation splits `slab_thickness` into `target` and `actual`. Twin still passes S1-S5 byte-identical — **that does not mean the split was correct**, only that existing fixtures still pass. The split may break a use case with no fixture (re-rolled product thickness). Verification cannot detect this; user must write new fixture before trusting Recommendation.

## 5. Schema Layer ontology 의 missing 부분

1. **Migration cost not estimated.** Current 17 tables, 5K+ rows for v2. Adding tables/columns/foreign_keys/indexes/constraints = minimum 5 new tables, possibly 10 (M2M junctions). Each needs migration scripts, audit_log integration, ACL extension. 9 JPA repos → ~90 column rows (manageable). 5000-entity system → 50K column rows + composition_edges explosion.

2. **JPO ↔ Schema mapping reliability.** v2 JPA: mostly mechanical (`@Entity` field → column same name). MyBatis: mapping in XML files (need XML parser). JDBC: mapping in string literals inside bodies (unrecoverable without query-log analysis). "Data access pattern abstract" bundles incompatible extraction surfaces.

3. **Cascade tracking on schema change.** If `SLAB_THICKNESS` renamed: `SDSlabEntity.slabThickness` references, 8+ anchor_bindings, mapped business_terms, generated Python twin, S1-S5 fixtures all affected. Current `realizations` handles single-step Code→Domain; no Schema→Code→Domain→Twin cascade walk implemented.

4. **Schema Layer vs production DB sync.** Schema-first (ontology truth, DB regenerated) blocks production teams. Production-first (DB truth, Schema Layer introspected) needs per-RDBMS introspector (Oracle vs Postgres vs SQL Server). v2 has no introspection pipeline; JPO ↔ production DB match is unverified.

## 6. User behavioral assumption 빈틈

1. **"복잡한 시스템 다 커버" cardinality.** One at a time / 10 concurrent / global catalog? `repo_id` scoping (16 of 17 tables) gives data isolation but ACL, audit, recommendation context need scoping decisions.

2. **Schema recommendation scope per user.** Column add / new table+FK / cross-table refactor / partition / index — without explicit scoping, Recommendation produces too-narrow or too-broad outputs. Both erode trust.

3. **Manual vs auto Schema Layer authoring.** ADR-002 says "9 JPA repo + JPO 가 자연스럽게 source" — auto-derive. But `SDOrderEntity` has 100+ fields, mostly uninteresting. Curating to "important columns" is human judgment ADR-002 does not assign.

4. **Wrong-recommendation lifecycle.** Reject in UI where? Counter-propose how? Re-iterate — does Recommendation maintain conversation state? `authoring_decision_log` has `decision_kind`/`payload_json` but conversational state for "iterate until right" is not modeled.

5. **Multi-user proposals.** Parallel approves of conflicting changes. Conflict resolution unspecified.

## 7. v2 vs 다른 system onboarding cost (실측 추정)

Phase α + sim-redesign actuals for v2:

| Item | v2 actual | Reusable | Per-new-system |
|---|---|---|---|
| Sample-repo ingest | ~1h | 80% | ~0.2h × scale |
| Action curation (38) | ~10h | 0% | 10h × (count/38) |
| Anchor binding (163) | ~12h | 0% | 12h × (count/163) |
| Business term (43) | ~5h | 0% | 5h × (count/43) |
| Type realization (36, 22 confirmed) | ~3h | 50% | 1.5-3h |
| Idiom card (27 in `toClaude/.../idioms/`) | ~12h | 30% | ~8h |
| KNOWN_DIVERGENCE (5) | ~2h | 100% | 0h |
| Facade classes (5) | ~3h | 100% | 0h |
| Smoke test set | ~2h | 100% | 0h |
| **Total** | **~50h** | — | **~37h per medium Java system** |

60K-LOC Java banking system (3× v2's 8390 LOC): linear scaling → **100-150h per new Java system**. "System-agnostic" implies near-zero; actual is dominated by curation.

A new architectural pattern or language: new AST parser, new role classifier, new idiom cards, new runtime substrate, new stubs. **First non-Java system: 200-400h mechanism + 100-150h curation.**

## 8. Round 1 design 의 hidden v2-coupling

1. **2-layer registry / 79 slot.** 79 slots induced from v2's 163 anchor_bindings. Names like `body.set_output`, `atomic.confirmed_plant_cd.activation_check`, `atomic.edging`, `atomic.safety_absolute_max`. `atomic.*` are v2-specific operations; banking system has `atomic.credit_score_lookup`, `atomic.fraud_check`. Estimated 40-50 of 79 slots are domain-specific → Layer 1 is **~40% reusable, 60% per-system**.

2. **Per-action template.** `SdDesigner.design` is v2's 21-step orchestrator with `tryStep` retry loop. Fits "main entry → step sequence". Multi-entry systems (controllers + jobs + Kafka consumers) have no single main entry. Trace diff structure assumes one trace per request; multi-entry needs trace per consumer + correlation. G9 "유지" silently keeps this.

3. **Trace contract is per-action.** `with _trace.anchor("slot_name", line=43)` assumes anchor → trace event is 1:1. For async/parallel/streaming, trace events form a DAG with timing, not a sequence. R5 "trace diff" is well-defined for sequences, ill-defined for DAGs.

4. **Java idiom assumptions throughout.** BigDecimal, MathContext, RoundingMode, LocalDateTime, AtomicLong, `@Transactional` — all Java-specific. Contracts/facades layer is Java-portable, not language-portable. A bank with `Money` + `Currency` + `LocalDate` needs different contracts.

5. **Code_methods scale.** v2 has 985; "947 un-anchored handled by Layer 2." A 60K-LOC Java system has 5K-8K methods, same ratio. Layer 2 mechanical rule table grows as new Java idioms surface (Java 17 sealed classes, records — v2 uses records in 6 places per Gap D-3).

## 9. 공통 risks across 3 imagined design (architect/recommendation/integrator)

1. **Bootstrap paradox.** Recommendation needs ontology to recommend; Recommendation evolves ontology. First-time on new system: ontology empty → low-quality proposals → reject → ontology stays empty. Self-bootstrapping requires separate seeding (manual or auto-extraction). Unspecified.

2. **LLM reasoning over ontology is unverifiable at user level.** User can verify referenced entity exists; cannot verify "this is the right entity to base recommendation on" without becoming domain expert. Trust gap grows with ontology size.

3. **Verification is partial oracle.** Can answer "does twin pass S1-S5?" but cannot answer "is this schema change correct?". ADR-002's "Verification 은 Recommendation 의 oracle" overclaims.

4. **Versioning across two engines + ontology.** Verification: registry+contract. Recommendation: prompt+LLM-model. Ontology: revision. Any of 5 axes change → cached state invalid. No invalidation strategy.

5. **No second system to validate generalization.** Until at least one non-v2 system is processed end-to-end, "system-agnostic" is unfalsifiable.

6. **Schema Layer migration is irreversible.** Adding 5+ tables to `data/ontology.db` is one-way. Audit_log, ACL, all consumers update. If Recommendation deferred, Schema Layer is dead weight.

## 10. Hidden assumptions (user 가 명시 안한)

1. **"테이블을 어떻게 변경" = DDL only?** User said only DDL. ADR-002 extended to "schema diff SQL + code stub + ontology additions" without confirming.

2. **Recommendation user = developer or domain expert?** Developer wants DDL with rationale. Domain expert wants "to add feature X, you need to track Y" without SQL. ADR-002 assumes developer.

3. **시뮬레이션 = single-shot or interactive?** sim_verify assumes single-shot. Recommendation use case implies interactive (propose → feedback → re-propose). Twin Runner has no interactive surface.

4. **온톨로지 = system-private or shared?** "복잡한 시스템 다 커버" implies one ontology for many systems. `repo_id` scoping gives isolation; cross-system queries are not modeled.

5. **"예시일 뿐" of v2.** Are v2-specific artifacts (27 idiom cards, 5 facades, S1-S5 fixtures) deleted post-generalization, kept as v2-example, or migrated to generic+v2-extension? Each path has different branch/PR implications.

6. **Non-determinism allowed?** ADR-001 made determinism load-bearing for Verification. Is the system now non-deterministic at "recommendation" while deterministic at "verification"? User has not confirmed.

## 11. Recommendations to synthesis agent (Round 2)

Before any Round 2 design is finalized:

1. **Name the second system.** Concrete non-v2 reference (language, framework, scale, architectural pattern). All "system-agnostic" claims tested against it.

2. **Recommendation scope decision tree.** UC4 explicit scopes: (a) column add only, (b) column + downstream code stubs, (c) multi-table refactor, (d) full migration plan. User picks one.

3. **Determinism boundary.** Diagram artifact provenance: deterministic vs LLM-derived; how prompt + input is hashed for cache.

4. **Schema Layer migration plan.** Enumerate new tables. Compatibility with `audit_log`, `realizations`, `composition_edges`. Migration + backout scripts.

5. **Two-engine sync protocol.** When Recommendation modifies ontology (immediate/staged), conflict resolution, audit trail for LLM-derived state, versioning across registry+contract+prompt+model+ontology.

6. **Layer 2 scaling test.** 5K-8K-method synthetic load.

7. **Recommendation context retrieval.** Ontology does not fit in prompt. Specify RAG mechanism: FTS, graph walk, learned ranker.

8. **User-facing trust mechanism.** Detection surface for wrong recommendations: review UI, validation steps, fixture-must-be-added-before-approve rule.

9. **Onboarding cost honesty.** Per-new-system cost breakdown (mechanism vs curation), compared to v2 ≥ 50h.

10. **Failure mode catalog.** For each new UC4-UC6 use case, at least 3 failure modes and system response.

11. **v2 artifact disposition.** v2 = ground-truth example / migrated to generic+v2-extension / deleted post-generalization. Affects branch state.

Until these have concrete answers, Round 2 synthesis is rearranging Round 1 handwaves. The expansion is not additive risk-free — it doubles surface area while v2 verification has not shipped a single byte-identical run.
