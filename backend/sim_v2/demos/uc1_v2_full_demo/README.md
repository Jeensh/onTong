# UC1 v2 Demo — End-to-End Java → Python Twin

**Goal:** Demonstrate the full `backend/sim_v2` pipeline on a small slab-design v2 pattern:
Java method → tree-sitter parse → translator → compile → execute → compare against
ground-truth Python re-implementation.

## What it shows

A 6-line Java method `SlabSplit.computeMaxSplit` (modeled after the real
`SdMaxSplitCountAction.execute` from `sample-repos/slab-design-real_v2/`):

```java
public int computeMaxSplit(BigDecimal secondWgtHigh, BigDecimal orderWgtHigh, BigDecimal productivity) {
    BigDecimal raw = secondWgtHigh
        .divide(orderWgtHigh, MathContext.DECIMAL64)
        .divide(productivity, MathContext.DECIMAL64);
    int maxSplit = raw.setScale(0, RoundingMode.CEILING).intValueExact();
    if (maxSplit < 1) {
        throw new RuntimeException("maxSplit < 1");
    }
    return maxSplit;
}
```

becomes:

```python
def computeMaxSplit(self, secondWgtHigh, orderWgtHigh, productivity):
    raw = ((secondWgtHigh / orderWgtHigh) / productivity)
    maxSplit = int(bd_set_scale(raw, 0, RoundingMode.CEILING))
    if maxSplit < 1:
        raise RuntimeError("maxSplit < 1")
    return maxSplit
```

The translation covers:
- `divide()` chained calls → `/` operator (W7 BigDecimal mapper + W8 type-aware dispatch)
- `setScale(scale, mode)` → `bd_set_scale(value, scale, mode)` contract helper (Lesson 1 §4.1)
- `intValueExact()` → `int(...)`
- `MathContext.DECIMAL64` → contract namespace constant (dropped here since binary `/` already implies precision context)
- `if` condition → Python `if`
- `throw new RuntimeException(...)` → `raise RuntimeError(...)` (W10 exception mapper)
- Method signature with formal parameter types → Python `def` with `self` prefix

## Running

From repo root:

```bash
.venv/bin/python -m backend.sim_v2.demos.uc1_v2_full_demo.run
```

Expected output (last block):

```
  Scenario                            Translated                       Ground Truth                     Cross
  normal                              PASS                             PASS                             MATCH
  boundary (raw < 1, ceil → 1)        PASS                             PASS                             MATCH
  error (raw == 0 → maxSplit 0 < 1)   PASS (expected exception raised) PASS (expected exception raised) MATCH

✓ Final verdict: PASS — translated Python matches ground truth on all scenarios
```

## Scenarios

| Name | Inputs | Expected output |
|---|---|---|
| normal | secondWgtHigh=100, orderWgtHigh=20, productivity=0.5 | maxSplit=10 |
| boundary | secondWgtHigh=0.3, orderWgtHigh=1, productivity=1 | raw=0.3 → ceil → maxSplit=1 |
| error | secondWgtHigh=0, orderWgtHigh=1, productivity=1 | raw=0 → maxSplit=0 → throw RuntimeError |

## Pipeline traced

1. **Parse** — `tree_sitter_java` produces a Java AST tree
2. **Translate** — `JavaToPythonTranslator(type_resolver=BigDecimalAwareResolver())`
   walks the tree, emits Python source. Builds local_scope from parameter types
   (`secondWgtHigh: BigDecimal`, etc.) so chained `.divide()` calls map to `/`.
3. **Compile** — `compile(py_source, "<demo>", "exec")` then `exec()` populates
   a globals dict with `Decimal`, `RoundingMode`, `bd_set_scale`.
4. **Execute** — calls the compiled `computeMaxSplit(**scenario.inputs)`.
5. **Oracle** — a hand-written Python implementation `ground_truth_compute_max_split`
   serves as the baseline. Both implementations share the same contract helper
   `bd_set_scale`, so they share the same runtime substrate (Lesson 1 §4.1).
6. **Compare** — translated output vs ground truth, per scenario.
   - `PASS` — value matches expected (and exception identity matches when expected)
   - `FAIL_BREAKING` — wrong exception or unexpected exception
   - `FAIL_DRIFT` — value differs from expected
   - `MATCH` / `DIVERGE` — translated vs ground-truth cross-check

## Why this matters

This is the first end-to-end **R3-style** check (translated Python produces the
same output as the Java baseline within tolerance). The R4/R5 variants
(trace consistency, revision pointer) are not yet wired — they require the
Integrator + RevisionStore pipeline (W2-W3 substrate, but no live demo yet).

## Known limitations

- The Java sample is inlined as a string, not loaded from a real file in the
  slab-design-real_v2 codebase. W14+ will wire the demo to the actual
  `SdMaxSplitCountAction.execute` via `code_layer` ontology lookups.
- The "Decimal arithmetic" path uses Python's native `/` operator. The real Java
  semantics use `MathContext.DECIMAL64` precision (16 significant digits, HALF_EVEN).
  For the demo's scenarios this happens to produce identical results, but
  precision-sensitive scenarios will need a contract `bd_divide(a, b, mc)` helper.
- Ground truth shares the same `bd_set_scale` as the translated code. If a bug
  is in the helper itself, both sides exhibit it and the oracle gives a false PASS.
  Defense layer 3 (oracle integration, ADR-005) addresses this via separate
  golden-master fixtures captured from the actual Java baseline.
