# Perspective: Skeptic — Risk Catalog

## 1. Summary

ADR-001 assumes Java→Python translation is a deterministic function of (Java AST + ontology). In practice, the Java production runtime is a co-product of Spring DI, JPA, `@Transactional` rollback, `AtomicLong` shared state, Jackson serialization, and `LocalDateTime.now()` — **none** of which are reified into the v2 ontology (38 actions / 163 anchors / 79 slots). All three proposed approaches (A/B/C) push that contextual semantics into either the synthesizer's prompt, the runtime substrate, or hand-written shims — i.e. the divergence surface that bit Phase α (KNOWN_DIVERGENCE 5종) is being moved, not eliminated. **R3 (byte-identical output) is unreachable unless the twin owns Spring/JPA emulation, BigDecimal `.equals` scale semantics, transactional boundaries, and clock injection — and none of A/B/C currently scope this.**

## 2. Twin concept itself — where it breaks

`slab-design-real_v2` uses Java semantics with no canonical Python analogue. Each is a concrete divergence vector:

1. **Spring DI** — 72 `@Autowired`/`@Component`/`@Service`/`@Repository` annotations across the repo (`SdThicknessAction.java:35-39`, `SdSlabSaveAction.java:30-43`). A twin needs a Python container or hand-wired factory. The ontology has no `dependency_graph` table, so wiring (singleton, lazy, qualifier) is invisible.
2. **Spring Data JPA derived query names** — `EdgingGroupRepository.findByCmpCdAndOrgCdAndGradeCdAndProductCdAndCustomerCdAndHrTgtWidthLowLessThanEqualAndHrTgtWidthHighGreaterThanEqualOrderByPriorityAsc(...)` (`EdgingGroupRepository.java:24`). Spring auto-derives SQL from method names. To twin: (a) parse camelCase into predicate AST, (b) replicate `LessThanEqual`/`GreaterThanEqual` BigDecimal compare, (c) replicate stable `OrderByPriorityAsc`. The ontology stores the FQN string only.
3. **`@Transactional` rollback** — `SdSlabSaveAction.execute` is `@Transactional` (`SdSlabSaveAction.java:48`); any exception rolls back **all** `repository.save(jpo)` calls in its `for` loop (lines 56-62). Also `SdHistoryAction.java:41/60/79` and `SdOrderExtractor.java:63/86`. Python-side rollback needs a session-scoped change journal. Skip it → partial-success then fail leaves Python with rows Java would have rolled back. R3 violated.
4. **`AlgorithmException extends RuntimeException` with `errorCode`** (`AlgorithmException.java:8-26`). Dispatched by string compare: `SdErrorCode.ALG_ITERATION_NEEDED.equals(e.getErrorCode())` (`SdDesigner.java:287`). v2 throws **three distinct types** with different controller paths: `AlgorithmException` (algorithm fail), `IllegalArgumentException` (`SdDriver.java:76`), `IllegalStateException` (`EdgingService.java:85`). Switching them silently changes `SdWorkingController.java:50`'s response code.
5. **BigDecimal `.equals` vs `.compareTo`** — `new BigDecimal("1.0").equals(new BigDecimal("1.00"))` → `false`; `compareTo` → `0`. Python `Decimal("1.0") == Decimal("1.00")` → `True`. v2 currently uses **only `compareTo`** for ranges (`SdInitialSlabWgtAction.java:43-44`, `SdLengthRangeAction.java:73`, `SdSplitRangeAction.java:46`, `SdSlabWgtRecalcAction.java:40`). But R5 (v2→v2') has no fence — one new `.equals(BigDecimal.ZERO)` call diverges the twin silently.
6. **`AtomicLong` shared mutable state** — `SlabNoSequence.java:16` is process-global (`counter.getAndIncrement()`). Two slab designs in one JVM get `000000000001`, `000000000002`. Two Python twin runs get the same number both times unless the synthesizer reifies "process-scoped counter" as singleton. The ontology has no `statefulness` facet.
7. **Java `record`** — `PlantMappingService.PlantMapping(String castCd, String machineCd)` (`PlantMappingService.java:23`), plus 5 others. Gap D-3 says the extractor *silently skips* records. The twin receives `PlantMapping` as a missing type; only Java AST has the constructor.
8. **Jackson camelCase serialization** — idiom P02 needs `slab.targetSlabLength` → JSON key `"targetSlabLength"`. Fields like `hrTgtWidth1..5` and `setSlabWidth1` have embedded numerics where naïve snake_case yields ambiguous keys. One bug away from R3 failure.
9. **`LocalDateTime.now()`** — `SdSlabSaveAction.java:51`. Non-deterministic. Twin must inject a clock; otherwise R3 fails every run. None of A/B/C explicitly addresses this.

## 3. Risks specific to approach A (Full synthesis)

- **A.1 Ontology underspecification ≠ synthesizer infallibility.** Anchors pin lines, but `body.service_lookup` at `SdThicknessAction.java:L57` spans 4 lines (lines 57-60) with six parameters. The synthesizer must read Java AST anyway; the ontology is *additive metadata*, not the primary source. If A's prompt treats ontology as ground truth, the LLM undergenerates the parameter list.
- **A.2 LLM non-determinism at scale.** 985 methods × 36 actions × 163 anchors. Even with `temperature=0`, prompt-context drift across calls produces non-byte-identical Python on re-synthesis. R3 requires a pure function of inputs. A pure-LLM synthesizer is not pure.
- **A.3 Gap propagation.** Gap C has 14 type_realizations at conf 0.5-0.7 (e.g. `SdAnalysisEntity → term.scm.analysis (auto, 0.7)`). A silently picks one mapping and hides the gap unless explicitly instructed to emit `# UNCLEAR` markers — which then makes "what's unclear" an LLM decision (violates determinism).
- **A.4 JPA query-name parsing.** A's prompt must teach the LLM `findByCmpCdAndOrgCdAnd...GreaterThanEqualOrderByPriorityAsc` parsing. One prompt regression breaks every repository. R5 means every new repo method risks breaking the synthesizer.

## 4. Risks specific to approach B (Minimal twin / literal AST walk)

- **B.1** Violates R1 by construction — AST is precondition, not ontology. R2 (gap surfacing) requires reading ontology to know what's a gap; pure AST walk can't.
- **B.2 JPA repositories have no body.** `EdgingGroupRepository` is an `interface` with declarations only; Spring fills bodies at runtime. B's literal walk emits an empty Python method — unrunnable. B must special-case Spring Data → no longer "minimal."
- **B.3 `@Autowired` constructor injection.** B emits a Python class taking same params, but who calls it? B needs a wiring layer — either hand-written `main()` or a synthetic scanner. Both contradict "minimal."
- **B.4 Java mutability vs Python dataclass.** `SDSlabEntity` has 100+ getter/setter pairs. B's literal walk emits `slab.setSlabThickness(x)` — idiom card P02 explicitly forbids this. So B's "literal" output is unrunnable until normalized — the normalization is the synthesizer.
- **B.5 `static final` constants** (`STEP_NO = 1`, `STEP_NAME = "SLAB_THICKNESS"`). Module-level Python leaks across files; class-level changes imports. B has no principled answer.

## 5. Risks specific to approach C (Phase α reuse)

- **C.1 α already proved 5종 divergence between independent authors.** KNOWN_DIVERGENCE (`bd()` factory vs class-style `BigDecimal`, MathContext enum vs const, RoundingMode enum vs `decimal.ROUND_*`, SdConstants namespace vs POS_SM constants, ValidationResult dataclass vs none) is not API typos — it's α1 (runtime) + α2 (cards) producing non-interoperable types. C's "bridge 5종 with class facades" addresses one slice; the next divergence (`LocalDateTime`, camelCase, JPA) reappears.
- **C.2 Cards are stale by design.** P01 cites `SdTargetLengthAction.java:25-29` by line. R5 (Java edits) makes line numbers wrong. C assumes a card refresh process — that process is the synthesizer.
- **C.3 79 slots, 27 cards = 34% coverage.** Hot 10 slots cover 55% by count (Gap F). The **38 single-anchor slots have no card**; simulator extrapolates from nothing. C inherits Gap F directly.
- **C.4 Gap B-1 orchestration anchors.** `SdDesigner.design` got 23 anchors added (`step_call[1..7]`, `step_call[16..19]`, persist, recovery) on 2026-05-12. C's runtime had no orchestrator shape; the 21-step loop with `tryStep` retry (`SdDesigner.java:240-296`) was not modeled. Card P09 (`body.orchestration`) is a placeholder.

## 6. Common risks across A/B/C — inherent to twin concept

- **X-1 Identity matrix not built.** None of A/B/C define the contract between synthesizer, runtime substrate, and oracle differ. α's failure was a contract gap; A/B/C re-introduce it in different shapes.
- **X-2 Re-synthesis is not idempotent without source pinning.** R5 says "Java v2 → v2', re-synthesize, compare". An LLM synthesizer (A) re-synthesizing unchanged v2 produces textually different Python — translation noise dominates diff. Determinism needs seed-pinned LLM, AST-canonical input ordering, version-pinned prompt.
- **X-3 985 methods ≠ "all twin-able".** Only 38 are anchored to actions. The other 947 (helpers, controllers, JPOs, entities, services) must also be twinned or the 38 can't execute. The ontology says nothing about them; synthesizer has no inputs for these.
- **X-4 Trace contract is implicit.** v2 uses `TraceCollector.wrap(stepNo, actionClass, "AA_LOOP", iteration, snapshotMap, lambda)` (`SdDesigner.java:281-283`). Synthesizer must emit Python calls to an equivalent. The ontology has no `trace.wrap` table.
- **X-5 Float sentinel `999999.999`** (`SdConstants.NO_UPPER_BOUND`) is `double`, not `BigDecimal`. Mixed `double`+`BigDecimal` via `BigDecimal.valueOf(double)` has a precision path Python `Decimal(repr(...))` doesn't replicate exactly.

## 7. User requirement gaps (R1-R5)

| Req | A (full synth) | B (minimal) | C (α reuse) |
|---|---|---|---|
| **R1** ontology precondition | Yes — but doesn't enforce *completeness*. Gap A (2 abstract) blocks twin | Violates — AST is precondition | Partial — cards derive from ontology + Java; refresh path unclear |
| **R2** gap surfacing | LLM-prompt dependent → non-deterministic | Cannot surface gaps it doesn't read | Cards have `Anchor confidence` field, no runtime emission |
| **R3** byte-identical | Requires clock injection, camelCase, `BigDecimal.equals` — none scoped | Fails on first `LocalDateTime.now()` | α oracle has `abs_tol=1e-6` hardcoded (Gap E-2) → not bit-level |
| **R4** same process | Trace contract re-emitted on every synthesis; expensive | AST walk preserves statement order, not trace events | TraceCollector model not ported to runtime |
| **R5** before/after | Synthesizer must be idempotent — not guaranteed | Idempotent (AST canonical) but unrunnable | Cards drift; manual re-curation cost |

## 8. Scale concerns

- **Slot-card ratio**: 27 cards / 79 slots = 34%. ~52 cards more needed for C.
- **38 single-anchor slots** (Gap F): zero cross-validation, one anchor away from silent miscoding.
- **LLM synthesis cost** (A): ~3000 tokens/method × 985 methods ≈ ~3M tokens per re-synthesis. R5 (every Java edit) means cost recurs.
- **LOC ratio**: v2 ~13k Java LOC main → ~9k Python at idiomatic 0.7×. R5 text diff of 9k LOC is unreadable; **semantic diff required**, not text diff.
- **947 un-anchored methods**: in scope for execution, out of scope for ontology. Gap propagates unless explicitly handled.

## 9. Hidden user assumptions

- **"풀 시연"** = "demo flow works" ≠ "36 actions all execute byte-identical to Java". The user has not been asked which definition holds; A/B/C scope diverges sharply.
- **JPA derived-query method name (~140 chars)** has not been shown to the user. Showing this concrete case may change stance on synthesizer scope.
- **R5 "비교 분석"** — three readings: (a) two Python runs diff outputs, (b) two Python source trees semantic diff, (c) Java diff with Python as executable proof. (a) is testable; (b)/(c) are research projects. Ambiguous.
- **Twin must own `LocalDateTime`, sequence counter, transaction boundary** — cross-cutting infrastructure, not "translation." User not informed.
- **Git churn**: every Java edit re-generates ~9k Python LOC. User must accept Python files change on every Java edit. Or gitignore + external store.
- **New actions in v2'**: Synthesizer handles *additions* (new `@Component`, new repo) not just modifications. Section 2 modeling pipeline must run between R5's two passes. Not documented.

## 10. KNOWN_DIVERGENCE re-occurrence prevention

α's root cause was **two parallel agents without an inter-agent contract**, not API typos:
- α1: function-style runtime (`bd()`, `bd_set_scale(val, n)`)
- α2: class-style cards (`BigDecimal(...).set_scale(n)`)
- Neither contract named, versioned, or smoke-tested until E-1 ran.

| Approach | Prevents re-occurrence? | Why / why not |
|---|---|---|
| **A** | Partially — single synthesizer owns API choice. But sub-prompts (translation, gap-marking, trace-wrap) can drift within A. Needs explicit *internal API contract*. |
| **B** | No — AST→Python rules + runtime substrate are still two artifacts authored separately. |
| **C** | No — cards + runtime + oracle were the three artifacts that diverged in α. Reusing them doubles down on the failure mode unless an explicit contract layer is added. |

**Prevention requires** an explicit, machine-checked API surface between synthesizer and runtime (typed `Protocol` classes, doctest per surface symbol, importable contract). None of A/B/C name this layer.

## 11. Recommendations to the synthesis agent

Before any of A/B/C is finalized, address:

1. **Define twin scope precisely.** Which Java features are in (BigDecimal, control flow, repo calls) vs out (Spring DI, real DB, real time)? Every out-of-scope feature needs a deterministic Python substitute.
2. **Reify synthesizer/runtime API contract.** Boundary between generated code and substrate must be (a) named, (b) typed (Python `Protocol`/`abc`), (c) smoke-tested per symbol, (d) versioned. α failed because this layer was implicit.
3. **Decide R5 diff granularity.** Text diff of 9k LOC is unreadable. Semantic diff (per-action trace diff) requires the trace contract to be first-class — ontology table or runtime emit, not implicit.
4. **Address the 947 un-anchored methods.** Pick explicitly: (a) twin auto-synthesizes with no ontology (B-style), (b) Section 2 expands ontology to all 985, (c) synthesizer reads Java AST for helpers (hybrid).
5. **Pin determinism mechanism.** If LLM is in the loop, what makes re-synthesis byte-stable? (Seeded sampling alone is insufficient — prompt context window varies.) If pure rule-based, what handles 38 single-anchor cases?
6. **Surface gaps via ontology, not LLM judgment.** R2's "...가 불명확함" must be deterministic function of `verification_level`, `confidence`, anchor presence — not LLM discretion. Else R2 is non-falsifiable.
7. **Confirm `풀 시연` definition with user.** "All 36 actions byte-identical" vs "happy-path demo" gates the whole design effort.
8. **Audit `LocalDateTime.now()`, `AtomicLong`, `@Transactional`, JPA derived queries** for explicit twin handling. Each is a R3 silent failure.
9. **Plan git artifact volume.** ~9k Python LOC regenerated per Java edit. Choose: version-pin Python in git, gitignore + external store, or content-address (hash-named) artifacts.
10. **Smoke-test contract before scaling.** α's E-1 test was added *after* divergence was found. Next iteration must add the smoke test *before* writing the second artifact.

Bottom line: the twin concept is sound only if synthesizer + runtime are co-designed with a named contract. **Moving divergence from cards-vs-runtime to synthesizer-vs-runtime is not progress unless the contract is now first-class.**
