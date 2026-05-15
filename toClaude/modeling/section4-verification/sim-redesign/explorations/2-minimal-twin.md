# Perspective: Minimal Twin / Literal Translation

## 1. Summary

The Python twin is a **statement-by-statement AST transliteration of Java**, not a synthesis from ontology cards or business-meaning models. The translator is a deterministic, table-driven Java→Python AST visitor whose only job is to preserve the source's literal structure (classes, methods, statements, expressions). The ontology is **auxiliary post-translation verification** — after translation, anchor lines in the Java AST must still map 1:1 to Python lines, otherwise the build fails. This is the simplest design consistent with ADR-001 and `feedback_simulation_design.md`'s "코드가 Ground Truth" directive: the Java AST literally **is** the ground truth; everything else is decoration.

## 2. Architecture

```
Java v2 *.java
   │
   ▼
JavaParser (existing, backend/modeling/code_layer/extractor.py)
   │
   ▼
Java AST forest (CompilationUnit list)
   │
   ▼
LiteralTranslator (deterministic visitor)
   - walks ClassDeclaration / MethodDeclaration / Stmt / Expr
   - 1:1 statement rules, no LLM, no ontology lookup
   - type-system stripper (@Component / JPA / @Transactional dropped)
   - identifier renamer (camelCase → snake_case)
   │
   ▼
gen/ Python twin tree  (sd_thickness_action.py, sd_designer.py, …)
   │           │
   │           ├──▶ AnchorAuditor: reads anchor_bindings,
   │           │      asserts every (file, java_line) maps to a
   │           │      python_line whose AST shape matches target_slot.
   │           │      Pass/fail = R2 surface.
   │           │
   │           └──▶ TwinRunner: builds DI graph from constructors,
   │                  invokes entry (design(order)), records trace.
   │                       │
   │                       ▼
   │                 Oracle Differ (existing α3, scripts/section4_oracle_diff.py)
   │                       │
   │                       ▼
   │                  v2 golden trace ↔ Python trace
```

The pipeline is **one-way and stateless per file**. No LLM calls, no per-step prompts, no best-effort interpretation: a Java method either translates by the rule table or the build halts at that node.

## 3. Synthesizer internals

The translator is a small visitor (~1500 LOC target) with one rule per Java AST node kind: `visit_ClassDeclaration`, `visit_MethodDeclaration`, `visit_LocalVariableDecl`, `visit_IfStmt`, `visit_ThrowStmt`, `visit_ReturnStmt`, `visit_ExpressionStmt`, `visit_BinaryOp`, `visit_MethodCall`, `visit_FieldAccess`, `visit_ObjectCreation`, `visit_NullLiteral`, etc. The rule table is mechanical:

| Java AST node                    | Python emission                              |
|----------------------------------|----------------------------------------------|
| `if (x == null)`                 | `if x is None:`                              |
| `s.isEmpty()`                    | `len(s) == 0`                                |
| `s.charAt(0)`                    | `s[0]`                                       |
| `String.valueOf(c)`              | `str(c)`                                     |
| `&&` / `\|\|`                    | `and` / `or`                                 |
| `throw fail(msg)`                | `raise self._fail(msg)`                      |
| `slab.setSlabThickness(x)`       | `slab.slab_thickness = x` (setter elision)   |
| `new BigDecimal("100")`          | `BigDecimal("100")` (ctor verbatim)          |
| `private final X x`              | `self.x: X` in `__init__`                    |
| `private static final int N = 1` | `N: ClassVar[int] = 1`                       |
| `@Autowired` / `@Component` / `@Transactional` | dropped at type-system boundary  |
| `extends X`                      | `class Y(X):`                                |
| `Foo<Bar>`                       | `Foo` (Python is duck-typed)                 |
| `record StepTrace(...)`          | `@dataclass(frozen=True) class StepTrace`    |

The renamer is a single pure function (camelCase → snake_case + getter elision), so two runs produce byte-identical Python.

**What the synthesizer does NOT do**: consult `actions` / `realizations` / `anchor_bindings`. It doesn't know what "body.compute" means. The 27 idiom cards are **obsolete**: P01 grouped 24 anchors with similar Java shapes, but the AST visitor walks `BinaryOp(*) BinaryOp(/) MethodCall(.setScale)` and emits the same Python regardless. Cards re-described what AST already encoded — α1 runtime vs α2 cards diverging was the direct consequence.

**What it DOES need**: JavaParser (already in `code_layer/extractor.py`) and a Java-runtime facade (`backend/modeling/sim_verify/runtime/`) whose API surface matches Java verbatim: `BigDecimal` as a class with `.multiply / .divide / .setScale` (not a `bd()` factory), `MathContext.DECIMAL64` as class-level constant, `RoundingMode.HALF_EVEN` as enum, `SdConstants.INACTIVE_PROCESS` as namespaced constant (current α's `POS_SM` consts in `confirmed_plant_cd.py` reorganize into `SdConstants`), `ValidationResult` as `@dataclass`. The facade is hand-written once, separate from `gen/`. It's the only "Python that isn't a mechanical Java mirror" — it exists solely because Java's stdlib isn't Python's stdlib.

## 4. R1-R5 satisfaction

| R | Mechanism | Evidence/file |
|---|-----------|---------------|
| R1 | Ontology is *consumed by* the AnchorAuditor only (post-translation check). Translator never blocks on ontology. | `anchor_bindings` table query: line-column ↔ python file:line equivalence map |
| R2 | Methods without anchor coverage receive `# UNCLEAR: ontology has no anchor for this method's body` marker emitted as a Python module-level docstring; methods on `signature_locked` actions get a stronger `raise NotImplementedError("SIGNATURE_LOCKED: ontology says body unknown")` for the body | AnchorAuditor + `verification_level=signature_locked` check |
| R3 | Bit-level output: each Java `BigDecimal` op routes to runtime facade with identical `MathContext.DECIMAL64` + `HALF_EVEN` semantics; oracle differ (`scripts/section4_oracle_diff.py`) compares stringified results | existing α3 + facade `bigdecimal.py` redesigned as class |
| R4 | Statement-order preserved by construction (visitor preserves AST child order); trace events emitted on each `ExpressionStmt` exit when `target_slot ∈ {body.service_lookup, body.set_output, body.dg_throw, …}` based on AST line ↔ anchor join | new TraceCollector emits step events on AST lines that have anchor_bindings |
| R5 | Re-run translator on v2' → produces deterministic `gen-v2'/`. `diff gen-v2/ gen-v2'/` is a real git-quality file diff. Run both, oracle-diff the traces | git-style diff + `scripts/section4_oracle_diff.py` |

## 5. Twin concept compliance (ADR-001)

- **Regenerable**: `python -m backend.modeling.sim_verify.translator --repo slab-design-real-v2` produces `gen/`. Idempotent.
- **Deterministic**: No LLM. No randomness. Two runs on the same Java source produce byte-identical Python (visitor walks the AST in declared order; renamer is pure).
- **No human edits**: `gen/` is `.gitignore`d. CI generates fresh. Manual edit to `gen/` is detected by a file-header SHA marker (`# AUTOGEN sha=<commit>`); any drift fails the build.
- **Java is the source**: `gen/` is byte-identical to a transliteration of v2 Java. To change Python, change Java.

## 6. Concrete worked example — `SdThicknessAction.execute()`

### Input

Java at `sample-repos/slab-design-real_v2/.../SdThicknessAction.java`, file 76 lines, method body L41-71 (verified via `code_methods.line_start=41, line_end=71`). Ontology rows (verified via `data/ontology.db`):

```
actions:        action.scm.thickness_실행 | body_anchored
realizations:   id=1810 | …SdThicknessAction.execute(SDOrderEntity,SDSlabEntity) | confirmed=1
anchor_bindings (5, all confirmed=1, source=manual):
  L43  atomic.confirmed_plant_cd.invalid_check     "confirmed == null || confirmed.isEmpty()"
  L47  atomic.confirmed_plant_cd.activation_check  "smChar == SdConstants.INACTIVE_PROCESS"
  L52  body.service_lookup                          "plantMapping.getMapping(smCd)"
  L57  body.service_lookup                          "castSpecService.lookup(...)"
  L70  body.set_output                              "slab.setSlabThickness(spec.getSlabThickness())"
```

### Translation steps

1. `ClassDeclaration` `SdThicknessAction` → `class SdThicknessAction:`.
2. Fields `STEP_NO=1`, `STEP_NAME="SLAB_THICKNESS"` → class-level `ClassVar`.
3. Constructor `SdThicknessAction(CastSpecService, PlantMappingService)` with `@Autowired` → `__init__(self, cast_spec_service, plant_mapping)`; `@Autowired` and `@Component` dropped at type-system boundary.
4. `void execute(SDOrderEntity, SDSlabEntity)` → `def execute(self, order, slab):`.
5. Body walk — each statement 1:1, line correspondence preserved:

```python
class SdThicknessAction:
    STEP_NO: ClassVar[int] = 1
    STEP_NAME: ClassVar[str] = "SLAB_THICKNESS"

    def __init__(self, cast_spec_service, plant_mapping):
        self.cast_spec_service = cast_spec_service
        self.plant_mapping = plant_mapping

    def execute(self, order, slab):                              # J:L41
        confirmed = order.confirmed_plant_cd                      # J:L42
        if confirmed is None or len(confirmed) == 0:              # J:L43 [ANCHOR]
            raise self._fail("확정통과공장코드 미설정")
        sm_char = confirmed[0]                                    # J:L46
        if sm_char == SdConstants.INACTIVE_PROCESS:               # J:L47 [ANCHOR]
            raise self._fail("제강 공장 비활성 (확통[0] = ' ')")
        sm_cd = str(sm_char)                                      # J:L50

        mapping = self.plant_mapping.get_mapping(sm_cd)           # J:L52 [ANCHOR]
        if mapping is None:
            raise self._fail("PlantMapping 미정의 for smCd=" + sm_cd)

        spec = self.cast_spec_service.lookup(                     # J:L57 [ANCHOR]
            order.cmp_cd, order.org_cd,
            sm_cd, mapping.cast_cd, mapping.machine_cd,
            order.product_cd)
        if spec is None:
            raise self._fail("CAST_SPEC 미존재 (sm=" + sm_cd + ", ...)")
        if spec.slab_thickness is None:
            raise self._fail("CAST_SPEC.SLAB_THICKNESS NULL")

        slab.slab_thickness = spec.slab_thickness                 # J:L70 [ANCHOR]

    def _fail(self, message):                                     # J:L73
        return AlgorithmException(self.STEP_NO, self.STEP_NAME,
                                  SdErrorCode.ALG_CAST_SPEC_NOT_FOUND, message)
```

### Ontology check

AnchorAuditor reads the 5 rows above, joins each `(java_file, java_line)` to the translator's line map, asserts the python line is non-empty and structurally matches the anchor's `target_slot`:

| Anchor                             | java_line | python_line | slot rule                           | pass? |
|------------------------------------|-----------|-------------|-------------------------------------|-------|
| atomic.confirmed_plant_cd.invalid_check | 43        | 9           | line is an `if` with `is None or len(...)==0` | ✓ |
| atomic.confirmed_plant_cd.activation_check | 47        | 12          | line is `if ... == SdConstants.INACTIVE_PROCESS` | ✓ |
| body.service_lookup                | 52        | 15          | line is a method-call assignment    | ✓ |
| body.service_lookup                | 57        | 18          | line is a method-call assignment    | ✓ |
| body.set_output                    | 70        | 30          | line is an attribute assignment to entity | ✓ |

If any check fails, build halts with `AnchorViolation(java_line=L52, python_line=15, expected=service_lookup_shape, got=...)`. **The ontology never decides what Python to write — it only validates that the AST walk preserved the anchor invariants.**

### Runtime behavior

The TwinRunner instantiates `SdThicknessAction(MockCastSpec, MockPlantMapping)`, calls `.execute(order, slab)` on a v2 fixture, captures trace events whenever the line being executed has an `anchor_bindings.target_slot`. Oracle differ compares to v2's golden trace.

## 7. R2 gap surface

### Gap A — abstract methods (`action.scm.run`, `action.scm.슬랩설계_실행`)

`SdDesigner.AlgorithmStep.run(...)` is `abstract` in Java. The translator emits a Python ABC method:

```python
class AlgorithmStep(ABC):
    @abstractmethod
    def run(self, order, slab):
        """UNCLEAR: action.scm.run is SIGNATURE_LOCKED in ontology.
        Body is abstract in Java (no body to translate). 21 subclasses override.
        """
        ...
```

The Korean alias `action.scm.슬랩설계_실행` has no realization in the DB. Translator does not see it. The AnchorAuditor reports it as **orphan ontology**: `[orphan] action.scm.슬랩설계_실행 has no realization` (R2 surface).

### Gap C — unconfirmed type_realizations (14 rows, conf 0.5-0.7)

These rows say e.g. `SdAnalysisEntity → term.scm.analysis (auto, 0.7)`. The translator **ignores** them — type identity is irrelevant to AST walk. The AnchorAuditor emits one comment per affected class:

```python
# gen/sd_analysis_entity.py
# UNCLEAR: type_realization SdAnalysisEntity → term.scm.analysis is unconfirmed
# (source=auto, confidence=0.7). Translation is structural only.

class SdAnalysisEntity:
    ...
```

A separate report file `gen/.gaps.md` lists all 14 to make them grep-able for a human reviewer (the **modeling** session, not the translator).

## 8. KNOWN_DIVERGENCE prevention

| Divergence              | Resolution                                                                  |
|-------------------------|------------------------------------------------------------------------------|
| BigDecimal class vs `bd()` factory | Facade exposes class form. Visitor emits `BigDecimal("100")` verbatim — never factory. |
| MathContext enum vs consts | Facade `class MathContext: DECIMAL64 = …`. Visitor preserves Java fqn. |
| RoundingMode enum vs `decimal.ROUND_*` | Facade `class RoundingMode(Enum): HALF_EVEN = …`. Visitor preserves. |
| SdConstants namespace vs `POS_SM` consts | Visitor emits `SdConstants.INACTIVE_PROCESS` verbatim. Runtime substrate moves `POS_*` consts into an `SdConstants` class. |
| ValidationResult dataclass missing | Java `record ValidationResult` → Python `@dataclass(frozen=True)`. AST visitor handles `RecordDeclaration`. |

α's 5 divergences were caused by two humans choosing **different abstractions** for the same Java APIs. Under literal translation there is one rule: **match Java's API surface verbatim in the facade**, then the translator never has to choose.

## 9. R5 workflow

1. Edit Java on a branch: `git checkout -b v2-prime; edit SdThicknessAction.java`.
2. Re-run modeling extractor: `python -m backend.modeling.extractor --repo slab-design-real-v2-prime`. Ontology updates; new anchors confirmed via modeling UI.
3. Re-run translator: `python -m backend.modeling.sim_verify.translator --repo slab-design-real-v2-prime` → `gen-v2-prime/`.
4. Three diffs surface side-by-side:
   - `git diff` on the Java file — **source diff** (the human edit).
   - `diff -u gen-v2/ gen-v2-prime/` — **twin diff** (proves translator deterministic; Python changed because Java did).
   - `scripts/section4_oracle_diff.py gen-v2 gen-v2-prime --fixture S1.json` — **behavioral diff** (trace+output deltas).

Reviewer reads all three: middle says "Python tracks Java"; right says "behavior changed at step N"; left explains why.

## 10. Failure modes

- **Unsupported Java node**: inline lambda capturing non-final var, etc. Build halts with `UnsupportedJavaNode(file:line)`. Fix: extend visitor (one rule).
- **Anchor mismatch after refactor**: v2' anchor L43 lands on blank line. `AnchorOrphan(L43)`. Fix: modeling UI re-anchors.
- **Missing facade API**: `slab.getXxx()` not in facade → `MissingFacadeMethod(SDSlabEntity.getXxx)`. Fix: add stub to facade.
- **Float ctor drift**: `new BigDecimal(0.95)` (float overload) — facade reproduces IEEE-754 binary via `Decimal(repr(0.95))`. Impossible to drift unless `repr` changes.

## 11. Honest weaknesses

- **Java expressivity limits**: checked-exception decls, `synchronized`, bounded wildcards — translator drops what's structurally irrelevant; load-bearing use requires custom rules.
- **Spring DI semantics**: orchestrator must explicitly assemble `SdThicknessAction(MockCastSpec, MockPlant)`. One DI wire-up file per repo.
- **Anchors are post-hoc**: if modeling's anchors are wrong, translator still produces literal Python that runs but doesn't match the expected shape. Right behavior per "code is ground truth", but auditor failures need a human triage path to the modeling UI.
- **No business-meaning lift**: a reviewer can't read `gen/sd_thickness_action.py` and "see the algorithm" any better than Java. Twin is for execution + diff, not explanation.
- **Records with custom accessors**: `record Foo(int x) { public int x() {…} }` needs a heuristic (pure record → `@dataclass`, custom accessor → method).
