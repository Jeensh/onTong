# Perspective: Automation Purist / Full Synthesis

## 1. Summary

The synthesizer is a single deterministic pipeline `(ontology DB, Java AST) -> Python module`, owning BOTH translation rules (formerly the 27 idiom cards) AND runtime API selection — paired in one source-of-truth table so a runtime signature change forces synthesis-time error, never silent KNOWN_DIVERGENCE. Same `(ontology revision, Java AST)` input always yields same Python bytes, so R4 "동일 처리 과정" is a synthesizer property; runtime trace becomes optional diagnostic, not verification gate.

## 2. Architecture

```
ontology.db (actions, realizations, anchor_bindings,    Java AST (per
  type_realizations, business_terms, code_methods) ---+ code_method_fqn,
                                                      | tree-sitter-java)
                                                      v
       +--------- Synthesizer (pure pipeline) ---------+
       | 1. Load ontology rows for action_fqn          |
       | 2. Parse Java method AST                      |
       | 3. Anchor<->AST align (line + locator hash)   |
       | 4. Slot dispatch -> emit Python AST nodes     |
       | 5. Runtime imports derived from emitted nodes |
       | 6. UNCLEAR markers + gap-report.json          |
       | 7. Format with Black; write file              |
       +-----------------------+-----------------------+
                               v
   backend/modeling/sim_verify/generated/<repo_id>/...py
                               v
        pytest runner ==> run vs golden trace + bit-diff
```

Components:

- **Registry**: `synth/registry.py`. Each entry is a 4-tuple `(slot, java_pattern, python_emitter, runtime_imports)` keyed by `target_slot` (79 distinct values today). Slot `body.service_lookup` emits `<service>.lookup(**kwargs)` derived from anchor metadata.
- **Anchor->AST aligner**: `anchor_bindings.line` is a hint; the `anchor_locator` string (e.g. `"confirmed == null || confirmed.isEmpty()"`) hashed against AST node text is authoritative — survives line drift.
- **Gap surfacer**: `# UNCLEAR:` inline comments at synthesis line + `gap-report.json` artifact.
- **No human edit surface**: generated `*.py` live under `backend/modeling/sim_verify/generated/<repo_id>/`, banner `# DO NOT EDIT — regenerate via python -m synth.run`.

## 3. Synthesizer internals

The synthesizer is one module (~800 LoC estimate). Pseudocode:

```python
def synthesize_action(action_fqn, repo_id) -> str:
    action  = db.fetch_one("actions", fqn=action_fqn, repo_id=repo_id)
    realiz  = db.fetch_all("realizations", action_fqn=action_fqn, repo_id=repo_id)
    anchors = db.fetch_all("anchor_bindings",
                           target_action_fqn=action_fqn, repo_id=repo_id)
    if action.is_abstract or action.verification_level == "signature_locked":
        return emit_polymorphic_dispatcher(action, realiz)
    java_ast = tree_sitter_java.parse(java_loader.load(realiz[0].code_method_fqn))
    py_body = []
    for stmt in java_ast.body:
        anchor = match_anchor(stmt, anchors)   # line + locator
        if anchor is None:
            py_body.append(literal_translate(stmt))
            py_body.append(f"# UNCLEAR: stmt at L{stmt.line} has no anchor")
        else:
            py_body.extend(REGISTRY[anchor.target_slot].emit(stmt, anchor, db))
    return render_module(action, collect_imports(py_body), py_body)
```

Key invariants:

- The registry is **internal**, not a human reference. Each entry references the runtime symbol it imports — when `bd()` factory changes signature, the registry entry breaks at synthesis (Python `ImportError`), not at user runtime. This is the KNOWN_DIVERGENCE prevention by construction.
- All translations are **pure functions** of `(java_ast_node, anchor_row, ontology_db)`. Determinism is guaranteed; given identical inputs, output bytes are identical (after `black --line-length=100`).
- The synthesizer never invents a Python helper. Every emitted call resolves to a symbol in `backend/modeling/sim_verify/runtime/__init__.py` or to a generated sibling module. If it cannot resolve, it raises `SynthesisError` and aborts — fail loud.

Ontology queries the synthesizer makes for `action.scm.thickness_실행` (verified against `data/ontology.db`):

```sql
-- actions: kind=effectful, verification_level=body_anchored
-- realizations: id=1810, code_method_fqn=...SdThicknessAction.execute(...)
--               confidence=1.0, confirmed=1
-- anchor_bindings (5 rows): L43 invalid_check 0.9, L47 activation_check 0.9,
--   L52 service_lookup 0.9, L57 service_lookup 0.95, L70 set_output 0.95
-- type_realizations:
--   SDOrderEntity     -> term.scm.order.order      name_match 1.0 confirmed=1
--   SDSlabEntity      -> term.scm.slab.slab        name_match 1.0 confirmed=1
--   CastSpecEntity    -> term.scm.spec.cast_spec   name_match 1.0 confirmed=1
--   AlgorithmException-> term.scm.algorithm_exception  auto 0.5 confirmed=0 (Gap C)
```

## 4. R1-R5 satisfaction

| Req | Mechanism | Evidence / file |
|---|---|---|
| R1 ontology precondition | Synthesizer reads `data/ontology.db` directly; refuses to emit if `realizations.confirmed=0` | `synth/loader.py` (proposed); ontology = sole input alongside Java AST |
| R2 gap surface | `# UNCLEAR` inline comments + `gap-report.json` + synthesizer log lines | See Section 7 |
| R3 bit-equal output | Synthesizer determinism + `bd()` factory matching Java BigDecimal HALF_EVEN | `backend/modeling/sim_verify/runtime/bigdecimal.py:30-38` (DECIMAL64) |
| R4 same processing | By construction — same input -> same output -> same step sequence emitted. Trace is diagnostic, not gate | `synth/main.py` purity guarantee |
| R5 v2 vs v2' compare | Re-run synthesizer on both ontology snapshots; bytes-diff `*.py`; run both; diff oracle outputs | See Section 9 |

R4 deserves attention. Phase α's `TraceCollector` + golden fixture treats R4 as a *runtime property to be verified*. Under full synthesis, R4 becomes a *compile-time property*: a correct deterministic synthesizer implies Python step sequence equals Java step sequence by construction. Runtime trace exists for human R5 diff readability, not as correctness gate.

## 5. Twin concept compliance (ADR-001)

Every generated `*.py` carries a banner: `# AUTO-GENERATED FROM ontology.db revision <git_sha> AND Java AST. DO NOT EDIT. Edits will be erased on next synthesis.` A pre-commit hook re-runs synthesis and `git diff --exit-code` against `generated/`. Human edits fail CI — ADR-001's "사람이 편집하지 않는다" enforced mechanically, not by policy. Generated modules import only from `backend.modeling.sim_verify.runtime` and from other generated modules; no Section 2 modeling code coupling.

## 6. Concrete worked example — SdThicknessAction.execute()

**Input rows** (queried above).

**Synthesis steps**:

1. Load action: `verification_level=body_anchored`, single realization, conf 1.0.
2. Parse Java AST of `SdThicknessAction.execute` L41-71.
3. Walk statements, match anchors by `line` + `anchor_locator` substring:
   - L42 var decl — no anchor, literal translate
   - L43-45 if-block — anchor `confirmed_plant_cd.invalid_check` -> registry emitter
   - L46 var decl — no anchor, literal translate
   - L47-49 if-block — anchor `confirmed_plant_cd.activation_check` -> emitter with `INACTIVE`
   - L50 var decl — no anchor, literal translate
   - L52-55 — anchor `body.service_lookup` -> service call with positional->kwarg rewrite
   - L57-65 — anchor `body.service_lookup` -> same emitter; multi-key lookup
   - L66-68 — no anchor on null-guard; literal translation + UNCLEAR
   - L70 — anchor `body.set_output` -> direct attribute assignment
4. Collect imports: `AlgorithmException`, `SdErrorCode`, `INACTIVE` from runtime.
5. Render module.

**Output Python** (`generated/slab-design-real-v2/.../sd_thickness_action.py`):

```python
# AUTO-GENERATED FROM ontology.db revision 8c9ebd9 AND Java AST. DO NOT EDIT.
from backend.modeling.sim_verify.runtime import (
    INACTIVE, AlgorithmException, SdErrorCode)
STEP_NO, STEP_NAME = 1, "SLAB_THICKNESS"
ERR = SdErrorCode.ALG_CAST_SPEC_NOT_FOUND

class SdThicknessAction:
    """Realizes action.scm.thickness_실행"""
    def __init__(self, cast_spec_service, plant_mapping):
        self.cast_spec_service = cast_spec_service
        self.plant_mapping = plant_mapping

    def execute(self, order, slab):
        confirmed = order.confirmed_plant_cd
        # anchor: atomic.confirmed_plant_cd.invalid_check L43 conf=0.9
        if confirmed is None or confirmed == "":
            raise AlgorithmException(STEP_NO, STEP_NAME, ERR, "확정통과공장코드 미설정")
        sm_char = confirmed[0]
        # anchor: atomic.confirmed_plant_cd.activation_check L47 conf=0.9
        if sm_char == INACTIVE:
            raise AlgorithmException(STEP_NO, STEP_NAME, ERR,
                "제강 공장 비활성 (확통[0] = ' ')")
        sm_cd = str(sm_char)
        # anchor: body.service_lookup L52 conf=0.9
        mapping = self.plant_mapping.get_mapping(sm_cd)
        if mapping is None:
            raise AlgorithmException(STEP_NO, STEP_NAME, ERR,
                f"PlantMapping 미정의 for smCd={sm_cd}")
        # anchor: body.service_lookup L57 conf=0.95
        spec = self.cast_spec_service.lookup(
            cmp_cd=order.cmp_cd, org_cd=order.org_cd, sm_cd=sm_cd,
            cast_cd=mapping.cast_cd, machine_cd=mapping.machine_cd,
            product_cd=order.product_cd)
        if spec is None:
            raise AlgorithmException(STEP_NO, STEP_NAME, ERR,
                f"CAST_SPEC 미존재 (sm={sm_cd}, cast={mapping.cast_cd}, ...)")
        # UNCLEAR: L66 null-guard has no anchor; literal-translated
        if spec.slab_thickness is None:
            raise AlgorithmException(STEP_NO, STEP_NAME, ERR,
                "CAST_SPEC.SLAB_THICKNESS NULL")
        # anchor: body.set_output L70 conf=0.95
        slab.slab_thickness = spec.slab_thickness
```

Note: `INACTIVE` is imported from runtime (`backend/modeling/sim_verify/runtime/confirmed_plant_cd.py`) — replaces `SdConstants.INACTIVE_PROCESS`. No "namespace vs constant" divergence is possible: registry only knows the runtime constant; if runtime renames it, registry breaks.

Expected runtime behavior: a fixture providing `cast_spec` rows produces `slab.slab_thickness = Decimal("230")` (or whatever). Trace event `{step:1, stepName:"SLAB_THICKNESS", status:"OK"}` emitted by an optional instrumentation pass.

## 7. R2 gap surface

**Gap A — abstract methods (`action.scm.run`, `action.scm.슬랩설계_실행`)**:

Synthesizer detects `is_abstract=1` or `verification_level='signature_locked'`. Emits:

```python
# AUTO-GENERATED — abstract action: action.scm.run
# UNCLEAR: 21 concrete implementations not enumerated in ontology.
# Synthesizer cannot dispatch without realization rows for each.
# See toClaude/modeling/section4-verification/anchor-gaps.md Gap A.

class AlgorithmStepDispatcher:
    def run(self, order, slab):
        raise NotImplementedError(
            "action.scm.run is abstract. "
            "Concrete realizations must be added via ontology fix; "
            "synthesizer cannot pick a runtime target."
        )
```

Plus `gap-report.json` entry:

```json
{"gap": "A", "action_fqn": "action.scm.run", "kind": "abstract_no_realizations",
 "blocks_synthesis": ["action.scm.slab.design_orchestrator"],
 "remediation": "add realization rows for 21 concrete AlgorithmStep impls"}
```

**Gap C — unconfirmed type_realizations (14 rows, conf 0.5-0.7)**:

When the synthesizer encounters `AlgorithmException` in Java AST and looks up its term, it finds `confirmed=0, confidence=0.5`. It still emits the import (the Java type maps somewhere) but tags it:

```python
# UNCLEAR: type 'AlgorithmException' -> term.scm.algorithm_exception
# (source=auto, confidence=0.5, confirmed=0).
# Semantic correspondence not human-verified; behavior matches Java by AST translation,
# but business-term mapping is unverified.
from backend.modeling.sim_verify.runtime import AlgorithmException
```

For type usage sites (e.g., a parameter typed `SdHistoryController`):

```python
def some_method(
    history: "SdHistoryController",  # UNCLEAR: -> term.scm.history_controller (auto, 0.5)
):
    ...
```

Both forms appear in `gap-report.json`. The user reads the report once, drives the modeling UI to confirm, re-runs synthesis. The marker tells the human reader EXACTLY where the uncertainty lives in the executable code.

## 8. KNOWN_DIVERGENCE prevention

| α divergence | How registry prevents it |
|---|---|
| BigDecimal (class vs `bd()`) | Registry entry imports `bd, bd_max, bd_multiply_decimal64`. Rename `bd()` -> ImportError at synthesizer startup. Cannot ship a nonexistent symbol. |
| MathContext (enum vs `DECIMAL64_*`) | Registry imports `DECIMAL64_PRECISION` directly; no free choice. |
| RoundingMode (enum vs `decimal.ROUND_*`) | Compute emitter has hardcoded `{"HALF_EVEN":"ROUND_HALF_EVEN",...}`. Unknown mode -> `KeyError` at synthesis. |
| SdConstants vs `POS_SM`/`INACTIVE` | Explicit substitution table `{"SdConstants.INACTIVE_PROCESS":"INACTIVE",...}`. Unknown identifier -> synthesis error. |
| ValidationResult dataclass | Validator emitter only produces direct booleans or `AlgorithmException`. The type isn't in allowed outputs. |

Central claim: under α, two humans (card author and runtime author) drifted. Under full synthesis, one machine reads both at synthesis time and refuses to ship a mismatch.

## 9. R5 workflow

Step-by-step for Java v2 -> v2' edit:

1. **Human edits Java** (e.g. SdThicknessAction L70 `spec.getSlabThickness()` -> `spec.getAdjustedThickness()`).
2. **Re-run Section 2 modeling agent**: updates `anchor_bindings` for L70 or flags reconfirmation. Output: ontology revision `v2'`.
3. **Re-run synthesizer** with `--ontology-revision v2'`. Produces tree `generated/slab-design-real-v2-prime/`.
4. **Bytes-diff** the two trees: `diff -ur generated/slab-design-real-v2 generated/slab-design-real-v2-prime`. The diff focuses on `sd_thickness_action.py` line change.
5. **Run both**: pytest harness runs every action under both trees with the same 5 v2 golden fixtures (S1-S5).
6. **Oracle diff**: `scripts/section4_oracle_diff.py` (Phase α holdover) compares output sets.

Human-facing artifacts: after step 3, two `gap-report.json` files (gaps diff); after step 4, a textual code diff a reviewer scans in minutes; after step 6, an oracle report showing which fixtures changed output. Entirely mechanical and reproducible — no card rewriting, no manual port.

## 10. Failure modes

- **Java construct outside registry coverage** (e.g. a `switch` expression v2 doesn't currently use but a future v2' adds). The synthesizer aborts with `UnknownConstructError` naming the AST node kind and line. Human extends registry, re-runs. No partial emit, no silent gap.
- **Anchor line drift after Java edit before ontology re-derivation**. Locator hash mismatch -> synthesizer flags `STALE_ANCHOR` and refuses to use it. Forces ontology refresh.
- **Registry-runtime divergence (the very thing we are preventing)**. Synthesizer startup imports registry, registry imports runtime symbols. Mismatch -> ImportError at synthesizer process start. Cannot generate stale code.
- **Tree-sitter mis-parses Java** (e.g. exotic generic). Synthesis fails with parse error pointing to byte offset. Java fix required.

In every case the user-visible error is a synthesizer log line + non-zero exit code at synthesis time, never at runtime. Compare to α: KNOWN_DIVERGENCE only surfaces when a human writes test fixtures and runs them.

## 11. Honest weaknesses

- **Registry bottleneck for new patterns**. v2 has 79 distinct `target_slot` values today. A new repo with novel idioms (async, reactive) needs registry entries first. The win: work happens once, replays across all matching anchors.
- **Literal-translation fallback is brittle**. Only 163 anchors over 985 methods; most statements inside anchored methods still rely on literal AST translation. If translation misjudges (e.g., Java `String.format` vs f-string), bugs leak. Mitigation: aggressively expand anchor coverage in Section 2.
- **Abstract method dispatch (Gap A)** is not solved by the synthesizer. It emits a stub, refuses to fabricate the 21 concrete `AlgorithmStep` realizations. Section 2 does the work.
- **Determinism depends on AST library**. Tree-sitter is deterministic for a fixed version; parser upgrades may shift AST shape. Pin version + reproducible-build CI.
- **Performance**: 985 methods may take seconds to synthesize cold. Negligible in human review, mild in CI. Cache by `(java_file_hash, ontology_revision)`.

The skeptic will press on these. The defense is that every alternative (α reuse, manual Python, hybrid scaffolding) trades these *known, bounded* weaknesses for *uncountable, silent* divergences. Full synthesis converts unknowable runtime risk into known compile-time engineering tasks.
