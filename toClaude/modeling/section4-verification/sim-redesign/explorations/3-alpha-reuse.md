# Perspective: Phase α Reuse / Incremental Bridge

## 1. Summary

Reuse the five Phase α artifacts on disk — 27 idiom cards
(`idioms/P*.md`), runtime substrate (`backend/modeling/sim_verify/runtime/`),
oracle differ (`scripts/section4_oracle_diff.py`), five golden fixtures
(`golden/S{1..5}.json`), and the smoke test
(`tests/verification/test_idiom_runtime_contract.py`). Apply ADR-001's twin
concept *on top of* them by (a) re-framing cards as a deterministic
synthesizer's translation-rule registry, (b) closing KNOWN_DIVERGENCE with
five facade classes added to the runtime, (c) extending the differ with
twin-vs-twin and twin-vs-Java diff modes. No card rewrite, no runtime
replacement, no second oracle.

## 2. Architecture

```
Section 2 ontology DB                      Phase α reuse layer (this proposal)
─────────────────────────────              ───────────────────────────────────
data/ontology.db                            backend/modeling/sim_verify/
  actions                                     runtime/ (existing)
  realizations            ──reads──►            bigdecimal.py       (keep)
  anchor_bindings                                algorithm_exception.py (keep)
  type_realizations                              confirmed_plant_cd.py  (keep)
  business_terms                                 lookup_source.py    (keep)
  code_methods                                 facades/ (NEW, ~120 LOC)
                                                  bigdecimal_class.py
                                                  math_context.py
                                                  rounding_mode.py
                                                  sd_constants.py
                                                  validation_result.py
                                              synthesizer/ (NEW)
                                                cards.py   ─►  P01–P27 *.md
                                                renderer.py    parsed at boot
                                                emit_trace.py  (wraps each
Java sample-repos/                                              anchor)
slab-design-real_v2/  ───parsed──►          generated/ (regenerable)
  *.java   (AST via existing                  v2_*.py    (one .py per Java class)
  scripts/import_code_raw.py)                 v2_prime_*.py   (v2′)

idioms/P*.md ◄──reads──┐                    scripts/
                       │                       section4_oracle_diff.py (extend)
                       ▼                          --twin-vs-twin v2 v2_prime
                  synthesizer                     --twin-vs-java twin golden
```

The synthesizer is a Python module added under
`backend/modeling/sim_verify/synthesizer/`. It boots by parsing each `P*.md`
card's *Canonical Python* code fence using the same regex
(`_FENCE_RE = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)`) already used
by `tests/verification/test_idiom_runtime_contract.py:54`. Each card becomes a
rule keyed by `target_slot` (the column in `anchor_bindings.target_slot`); the
README cover map at `idioms/README.md:28-69` already pins this 1:N mapping.
The renderer then walks the ontology for a given realization, slots each
anchor into its card template, and emits one Python method per
`code_method_fqn`. Generated files live under `generated/` and are
git-ignored — they are pure outputs.

## 3. Synthesizer internals

The synthesizer is a deterministic 5-pass pipeline. Input: one
`realizations` row (with `code_method_fqn` + `action_fqn`). Output: one
Python method body.

```python
# backend/modeling/sim_verify/synthesizer/renderer.py (NEW)
def synthesize_method(realization_row, db) -> str:
    java_ast = load_method_ast(realization_row.code_method_fqn)    # Pass 1
    anchors = db.query("""                                          # Pass 2
        SELECT line, target_slot, anchor_locator, confidence
        FROM anchor_bindings
        WHERE code_method_fqn=? AND target_action_fqn=? AND repo_id=?
        ORDER BY line
    """, realization_row.code_method_fqn, realization_row.action_fqn, 'slab-design-real-v2')
    fragments = []                                                  # Pass 3
    for a in anchors:
        card = CARDS[a.target_slot]                # P01–P27 indexed at boot
        fragment = card.render(java_ast.at_line(a.line),
                               types=db.types_for(a))
        fragments.append(emit_anchor_trace(a, fragment))
    body = assemble(fragments, java_ast.control_flow_skeleton)      # Pass 4
    return render_method(realization_row, body,                     # Pass 5
                         gap_markers(realization_row, db))
```

Each card exposes one `render(...)` substituting locals from the Java AST.
The Canonical Python block in the markdown stays as-is — the renderer
treats it as a template with `{var}` placeholders, where vars come from the
AST. For example, `P02-body.set_output.md:23` shows
`slab.target_slab_length = floored`; the renderer substitutes `floored`
with the local at the `setX(...)` call site, and `target_slab_length` with
`snake_case(java_setter_name)`. Deterministic, no LLM.

The `emit_anchor_trace` wrapper supplies R4 — runtime instrumentation:

```python
def emit_anchor_trace(anchor, body_str: str) -> str:
    return (f"with _trace.anchor(slot={anchor.target_slot!r}, "
            f"line={anchor.line}, confidence={anchor.confidence}):\n"
            f"{indent(body_str, 4)}")
```

`_trace` is a `TraceCollector` ported to `runtime/trace.py`, mirror of
Java's `TraceCollector.wrap(...)` (`SdDesigner.java:266`). ~80 LOC new.

## 4. R1–R5 satisfaction

| Req | Mechanism | Evidence |
|---|---|---|
| **R1** ontology=precondition | Synthesizer reads `actions`/`realizations`/`anchor_bindings`/`type_realizations`. Refuses to emit a method if `realizations.confirmed=0` for that action. | `anchor-gaps.md:14-30` (current 100% confirm); renderer Pass 2 SQL |
| **R2** gap surface | Card renderer queries `type_realizations` for each parameter type and writes `# UNCLEAR: type_realization auto, conf=0.5` for unconfirmed types. SIGNATURE_LOCKED actions get a header comment `# WARNING: action.scm.run is abstract — synth produces stub` | `anchor-gaps.md:35-48` (Gap A 2 actions); `:68-91` (Gap C 14 types) |
| **R3** byte-equal output | Reuses `runtime/bigdecimal.py:39-45` which serializes via `Decimal(repr(value))` — Java `BigDecimal.toString()` semantics. Oracle differ already at byte tolerance for strings. | `idioms/P01-body.compute.md:55-66` trace contract; `scripts/section4_oracle_diff.py:73-84` `deep_equal` |
| **R4** step sequence | `emit_anchor_trace` wraps every anchor, producing `(slot, line, confidence)` events in Java source order via Pass 4 line-sorted assembly. Compared against the golden `"trace"` array. | `golden/S1.json:56` trace key; Pass 4 line-order |
| **R5** v2 vs v2′ | Re-run synthesizer on `slab-design-real-v2-prime` repo_id (a new Section 2 import). Run both twins, oracle differ runs in `--twin-vs-twin` mode | new `--twin-vs-twin` flag in `scripts/section4_oracle_diff.py` |

## 5. Twin concept compliance

Python is never hand-edited. Even cards — which are markdown — are not
edited per generation; they are immutable templates checked into git, with
only `{var}` placeholders substituted. Output Python under `generated/`
regenerates deterministically from `(ontology_db, java_ast, cards,
facades)` — same five inputs → same Python bytes.

Re-derivation is cheap. 985 methods × 27-card parse (<50KB) × 38 actions ×
~5 anchors × template substitution = sub-second. Pure function, no
network, no LLM, no state.

Cards are where translation knowledge accumulates — the "spec" of the
translation, not transient docs. `idioms/README.md:13-18` already says
this: "Read the anchor's `target_slot` ... Find the matching card here ...
Use the **Canonical Python** block as the template". The language was
correct; only the consumer was missing. This proposal supplies it.

## 6. Concrete worked example — `SdThicknessAction.execute()`

### Input ontology rows (verified via `sqlite3 data/ontology.db`)

```sql
-- actions row:
fqn=action.scm.thickness_실행 | verification_level=body_anchored | repo_id=slab-design-real-v2

-- realizations row (id=1810):
action_fqn=action.scm.thickness_실행
code_method_fqn=com.example.slabdesign.feature.sd.process.working.action.SdThicknessAction.execute(SDOrderEntity,SDSlabEntity)
dispatch_source=single_impl | confirmed=1

-- anchor_bindings (5 rows, sorted by line):
L43 atomic.confirmed_plant_cd.invalid_check   (conf 0.9, manual)
L47 atomic.confirmed_plant_cd.activation_check (conf 0.9, manual)
L52 body.service_lookup                        (conf 0.9, manual)
L57 body.service_lookup                        (conf 0.95, manual)
L70 body.set_output                            (conf 0.95, manual)
```

### Synthesis steps

1. **Card lookup**: L43→P22, L47→P22, L52→P12, L57→P12, L70→P02.
2. **AST extraction**: parse `SdThicknessAction.java` (already cached by
   `scripts/import_code_raw.py`). Locals: `confirmed`, `smChar`, `smCd`,
   `mapping`, `spec`.
3. **Type-realization check**: `CastSpecEntity` → `term.scm.cast_spec`
   (confirmed=1, OK); `PlantMappingService.PlantMapping` → unconfirmed
   (Gap C residual) → emit `# UNCLEAR` marker.
4. **Card render**: P22 invalid_check at `:44-50` fits L43; P22
   activation_check at `:53-59` fits L47; P12 service_lookup at `:26-35`
   fits L52+L57 with arg-list adapted from AST; P02 at `:23` fits L70.
5. **Helper emit**: AST detects private `fail(String)` at
   `SdThicknessAction.java:73-75`; emitted as `_fail` Python method.

### Output Python (full method, generated)

```python
# generated/v2_sd_thickness_action.py — DO NOT EDIT — regenerated by
# backend.modeling.sim_verify.synthesizer
# Source: SdThicknessAction.java (slab-design-real-v2)
# Ontology: action.scm.thickness_실행 @ body_anchored (5 anchors confirmed)

from backend.modeling.sim_verify.runtime import (
    BigDecimal, MathContext, RoundingMode,                   # facades
    AlgorithmException, SdErrorCode,
    ConfirmedPlantCd, SdConstants, ValidationResult,         # facades
    LookupDataSource,
    TraceCollector,
)

STEP_NO = 1
STEP_NAME = "SLAB_THICKNESS"


class SdThicknessAction:
    # UNCLEAR: type_realization 'PlantMappingService.PlantMapping' is
    #   auto/conf=0.7 (Gap C residual). Treating as opaque dataclass.
    def __init__(self, cast_spec_service, plant_mapping):
        self.cast_spec_service = cast_spec_service
        self.plant_mapping = plant_mapping

    def execute(self, order, slab, _trace: TraceCollector | None = None):
        _trace = _trace or TraceCollector.noop()

        # anchor L43 atomic.confirmed_plant_cd.invalid_check (conf 0.9)
        with _trace.anchor("atomic.confirmed_plant_cd.invalid_check", line=43, confidence=0.9):
            confirmed = order.confirmed_plant_cd
            if confirmed is None or not confirmed:
                raise self._fail("확정통과공장코드 미설정")

        # anchor L47 atomic.confirmed_plant_cd.activation_check (conf 0.9)
        with _trace.anchor("atomic.confirmed_plant_cd.activation_check", line=47, confidence=0.9):
            sm_char = confirmed[0]
            if sm_char == SdConstants.INACTIVE_PROCESS:
                raise self._fail("제강 공장 비활성 (확통[0] = ' ')")
            sm_cd = str(sm_char)

        # anchor L52 body.service_lookup (conf 0.9)
        with _trace.anchor("body.service_lookup", line=52, confidence=0.9):
            mapping = self.plant_mapping.get_mapping(sm_cd=sm_cd)
            if mapping is None:
                raise self._fail(f"PlantMapping 미정의 for smCd={sm_cd}")

        # anchor L57 body.service_lookup (conf 0.95)
        with _trace.anchor("body.service_lookup", line=57, confidence=0.95):
            spec = self.cast_spec_service.lookup(
                cmp_cd=order.cmp_cd, org_cd=order.org_cd,
                sm_cd=sm_cd,
                cast_cd=mapping.cast_cd, machine_cd=mapping.machine_cd,
                product_cd=order.product_cd,
            )
            if spec is None:
                raise self._fail(
                    f"CAST_SPEC 미존재 (sm={sm_cd}, cast={mapping.cast_cd}, "
                    f"machine={mapping.machine_cd}, productType={order.product_cd})"
                )
            if spec.slab_thickness is None:
                raise self._fail("CAST_SPEC.SLAB_THICKNESS NULL")

        # anchor L70 body.set_output (conf 0.95)
        with _trace.anchor("body.set_output", line=70, confidence=0.95):
            slab.slab_thickness = spec.slab_thickness

    def _fail(self, message: str) -> AlgorithmException:
        return AlgorithmException(
            step_no=STEP_NO, step_name=STEP_NAME,
            error_code=SdErrorCode.ALG_CAST_SPEC_NOT_FOUND,
            message=message,
        )
```

Expected runtime behavior: invoking with an order where
`confirmedPlantCd="K1 K    "` and the LookupDataSource fixtures populated
produces an emit sequence `[L43, L47, L52, L57, L70]` and mutates
`slab.slab_thickness = 230.0` — byte-matches `golden/S1.json:88-89`.

## 7. R2 gap surface

### Gap A (2 SIGNATURE_LOCKED abstracts)

```python
# generated/v2_algorithm_step.py
class AlgorithmStep:
    # WARNING: action.scm.run is SIGNATURE_LOCKED — abstract base, no body.
    # 21 concrete overrides exist (see realizations). This stub raises to
    # force callers to dispatch via the concrete class, not the base.
    def run(self, order, slab):
        raise NotImplementedError(
            "action.scm.run is abstract; dispatch via the 21 concrete subclasses"
        )
```

### Gap C (14 unconfirmed type_realizations)

Each emitted comment names the unconfirmed mapping with its confidence:

```python
class SdHistoryEntity:
    # UNCLEAR: type_realization 'SdHistoryController' → 'term.scm.history_controller'
    #   source=auto, confidence=0.5 (Gap C residual). Synthesis used best
    #   effort; verify field names against Section 2 modeling UI.
    ...
```

The list of 14 is the one currently in `anchor-gaps.md:75-83`. Each Python
class header carries the same marker.

## 8. KNOWN_DIVERGENCE prevention

Add five facade modules to `backend/modeling/sim_verify/runtime/facades/`:

| Card expectation | Facade | LOC | Strategy |
|---|---|---:|---|
| `BigDecimal` class w/ `.multiply()`, `.divide()`, `.set_scale()`, `.compare_to()` | `bigdecimal_class.py` | ~50 | Wraps `bd()`; methods delegate to `bd_multiply_decimal64` etc. |
| `MathContext.DECIMAL64`, `.DECIMAL32` | `math_context.py` | ~10 | Module constants holding `(precision, rounding)` |
| `RoundingMode.HALF_EVEN/FLOOR/CEILING` | `rounding_mode.py` | ~10 | Re-export of `decimal.ROUND_*` |
| `SdConstants.INACTIVE_PROCESS`, `.CONFIRMED_PLANT_CD_LENGTH` | `sd_constants.py` | ~15 | Class with `__slots__=()`; pulls `INACTIVE`/`LENGTH` from `confirmed_plant_cd.py` |
| `ValidationResult.ok()/.fail()` | `validation_result.py` | ~25 | Dataclass `failed/error_code/message` |

Total ≈ 110 LOC. Each facade is a thin wrapper, not a reimplementation. The
functional API (`bd()`, `bd_multiply_decimal64`) stays public — existing
`tests/verification/test_runtime_bigdecimal.py` keeps passing. Re-export
via `runtime/__init__.py` so `from backend.modeling.sim_verify.runtime
import BigDecimal` works (cards' expectation at `P01-body.compute.md:27`).

`tests/verification/test_idiom_runtime_contract.py:46-52` lists the five
divergences; `test_known_divergence_is_actually_referenced` at `:181-187`
enforces that the set shrinks to empty when facades land — automatic
verification.

Spring/JPA/DB stripping uses the same pattern. `@Autowired` services →
constructor injection (see P12 at `:26-35`). `@Repository` Spring-Data →
`LookupDataSource` from JSON fixtures (`lookup_source.py:16-83`). Spring
class APIs get shadowed by facades with matching method names but
constructor-injection contracts. Scales to any Spring boundary.

## 9. R5 workflow

1. **Edit Java** — dev modifies `SdThicknessAction.java`, e.g. adds a
   fourth pre-condition check before L70. Artifact: Java diff.
2. **Re-run ingestion** — `python scripts/import_code_raw.py --repo
   slab-design-real-v2-prime` re-parses AST under a new `repo_id`.
   Artifact: new `code_methods` rows.
3. **Re-run anchor inference** — Section 2 modeling agent re-applies
   heuristics; new anchors prompt user-confirm. Artifact: side-by-side
   v2 vs v2_prime anchors in modeling UI.
4. **Re-synthesize** — `python -m backend.modeling.sim_verify.synthesizer
   --repo slab-design-real-v2-prime --out generated/v2_prime/`. Artifact:
   full set of `v2_prime_*.py` files (inspect read-only).
5. **Run both twins** — `python -m backend.modeling.sim_verify.runner
   --twin generated/v2/ --scenario S1` then same for v2_prime. Artifact:
   two `trace.json` files.
6. **Differ** — `scripts/section4_oracle_diff.py --twin-vs-twin --a
   v2/trace.json --b v2_prime/trace.json --golden golden/S1.json`.
   Artifact: markdown diff report showing which step's snapshot changed
   and which anchors fired only in v2_prime (the new precondition).

## 10. Failure modes

- **Card doesn't cover a `target_slot`.** README claims 27 cards over 56
  slots (`idioms/README.md:22-24`). A 57th slot triggers
  `MissingCardError(slot)` at synth time — no silent fallback. User
  artifact: red error before any Python written.
- **Anchor's AST shape mismatch.** A `body.compute` anchor landing on a
  non-arithmetic line. Renderer detects via card confidence thresholds
  (`P01-body.compute.md:68-74`). Below 0.85, emits
  `# UNCLEAR: anchor confidence {conf} below 0.85` and best-effort. Trace
  diverges from golden → developer sees "L52 unexpected shape" in diff.
- **Twin-vs-Java drift.** When differ flags divergence, renderer dumps
  per-anchor fragments so user sees which slot's card emitted bad code.

## 11. Honest weaknesses

- **Cards are inputs, not outputs.** New `target_slot` values require new
  cards. Not full automation — it's a curated translation registry. Defense:
  cards are short (5-95 LOC), one-time per slot, current set covers all 56
  slots.
- **Renderer needs Java AST + ontology.** Cards substitute locals from AST.
  Synthesizer is therefore ontology-driven and AST-aware. Defense: AST
  already ingested by `scripts/import_code_raw.py` — reuse, not new infra.
- **Cards encode opinion.** Style choices (`compare_to(...)` vs Python
  operators, `LookupDataSource` shape). Future repo could diverge. Defense:
  multi-repo support layers via `card_set` keyed by `repo_id`.
- **No LLM for novel Java constructs.** A radically different Java
  structure (30-case switch with arithmetic) matches no card. Hard failure
  by design — `MissingCardError`. Defense: current 27 cards cover 140/140
  anchors; novel structure implies new ontology slot anyway.
- **Facade semantic drift.** `BigDecimal.multiply` defaulting to DECIMAL64
  must thread an explicit `MathContext.DECIMAL32` through if Java passes
  one. Defense: facade methods take `math_context=DECIMAL64` and switch
  `localcontext()` like `runtime/bigdecimal.py:103-108` already does.

The fundamental claim: ≈ tens of hours of α work (commits `5642a57`,
`37c423d`, `d4d80dc`, `0777217`, `8c9ebd9`, `6769560`) embedded the right
*content* in cards + runtime + golden + differ. ADR-001 invalidated the
*framing* of cards as human-doc translation guides, not the content. This
proposal re-frames them as synthesizer input registry — same content,
correct consumer. Discarding this to restart from a literal AST walker or
pure LLM synth throws away the anchor-keyed translation table — the
hardest artifact to recreate, the only one that survives across approaches.
