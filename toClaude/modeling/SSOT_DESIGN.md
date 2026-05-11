# SSOT for editable fields — Design

**Status:** Design doc, Wave 1 (this PR). Wiring (Wave 2) replaces the
handwritten `TermPatch` / `ActionPatch` / `BRPatch` / `AnchorPatch` in
`backend/modeling/api/queue_actions_api.py` with imports from
`_generated_patch_models.py` and rewires `MainPanel.tsx` field-by-field through
`getEditConfig()`.

## Why a SSOT at all

Today, "is field X editable?" is answered in four places:

1. `frontend/src/components/sections/modeling/MainPanel.tsx` — what the user can click
2. `frontend/src/components/sections/modeling/InlineEdit.tsx` — which primitive is wired
3. `backend/modeling/api/queue_actions_api.py` — what the PATCH model accepts
4. `toClaude/modeling/editable_fields_guide.html` — the human-facing inventory

At ~30 fields across 5 entities this is annoying but survivable. At the
**stated growth target of 300+ fields across 10+ entities** (Action layer
expansion, Action.params splitting, simulation BR linkage, governance fields),
the four-file fan-out becomes a constant source of drift. Decision #10 (today)
flips from "reconsider when 100+ fields" (the prior recommendation) to "do it
now" — the 5-mismatch episode that triggered the editability deliberation was
already too expensive to debug.

## Why YAML, not JSON or TOML

| | YAML | JSON | TOML |
|---|---|---|---|
| Comments | yes | no | yes |
| Multi-line strings | yes (literal blocks) | no | yes |
| Nested maps cheap | yes (indent) | yes (braces) | awkward (`[entity.fields.label]`) |
| Diff readability | high (1 field = 1 block) | medium (braces/commas) | medium |
| Stdlib in 2026 venv | PyYAML 6.0.3 already vendored | yes | tomllib (read-only, fine for SSOT but not human-edited) |
| Schema enforcement | via lint script | via JSON Schema | via lint script |

YAML wins on **comments** alone — every non-trivial decision lives in a comment
block next to the field it explains. We can't ship a 300-field SSOT without
that. The "YAML can be ambiguous" risk is contained because the lint script
(`scripts/lint_editable_sync.py`) treats the YAML as a strict typed shape and
loudly errors on any deviation.

## Scaling considerations for 300+ fields

1. **Field order = diff order.** Codegen preserves YAML key order
   (PyYAML preserves insertion order on round-trip with `safe_load` since 5.1).
   Adding a field appends one block; PRs are localized.

2. **Editable kinds are a finite enum, not a free string.** Nine values
   (`inline_text`, `inline_textarea`, `inline_list`, `inline_select`,
   `inline_autocomplete`, `inline_number`, `inline_range`, `read_only`,
   `authoring_only`). When a 300th field needs a new affordance, you add the
   primitive to `InlineEdit.tsx` once and the YAML can use it everywhere.

3. **Per-field overrides via `edit_opts`.** Confirm modal (#1 severity), enum
   options (#3 value_type), autocomplete source (#2 anchor_locator), number
   stepping, textarea row count — all stay attached to the field that needs
   them. No global config table.

4. **`backend_column` decoupling.** Field name (DTO key) and ORM column name
   diverge constantly (`aliases` vs `aliases_json`). Making this explicit per
   field means the YAML is the dictionary the code lives by.

5. **`confidence_label`.** When a field has both a parser-derived value and a
   user override (#8 CodeType.role pattern), one flag in YAML drives the UI
   badge ("(user override)") and the dispatch logic. Anticipate ~10 of these
   at scale (Action.kind, Term.is_root_entity, etc. all candidates).

## Pipeline

```
                              edit
                              ───►
        ┌──────────────────────────────────────────────────┐
        │ toClaude/modeling/editable_fields.yaml           │  ← SSOT
        └──────────────────────────────────────────────────┘
                  │                 │                  │
                  ▼                 ▼                  ▼
   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
   │ codegen_patch_   │  │ codegen_inline_  │  │ lint_editable_   │
   │ models.py        │  │ wiring.py        │  │ sync.py          │
   └──────────────────┘  └──────────────────┘  └──────────────────┘
            │                     │                       │
            ▼                     ▼                       ▼
   _generated_patch_      _generated/inline_       (CI gate — exits 1
   models.py              wiring.ts                 on drift)
   (Pydantic v2)          (Record<entity,
                           Record<field, cfg>>)
            │                     │
            └─── Wave 2 ──────────┘
                  │
       queue_actions_api.py uses ENTITY_TO_PATCH dispatch
       MainPanel.tsx reads getEditConfig() to pick primitive
```

Three commands, each idempotent:

```bash
.venv/bin/python scripts/codegen_patch_models.py     # writes backend file
.venv/bin/python scripts/codegen_inline_wiring.py    # writes frontend file
.venv/bin/python scripts/lint_editable_sync.py       # CI gate
```

`--check` mode exits 1 if regeneration would change anything; both codegens
support it for CI.

## Lint rationale

Five checks, in this order of importance:

1. **`backend_column` ↔ ORM column.** The most common drift bug: developer
   renames a column in ORM, forgets the YAML. Lint catches this in seconds.
   Caught a real instance during initial development (CodeType.role pointing
   at a not-yet-created `role_user_override` column).

2. **`validation.one_of` ↔ `edit_opts.options`.** When BR severity must be
   `[hard, soft]`, both the backend validator and the frontend `<select>`
   options need to agree. One YAML, one source.

3. **`immutable: true` / `derived_from` ⇒ `edit: read_only`.** Defensive — an
   immutable field that gets `edit: inline_text` would still emit a Patch
   field but ORM would silently drop it. Catch the typo at lint time.

4. **`serialize: json` ⇒ `*_json` suffix.** Convention check (warning, not
   error). Detects accidental JSON-on-non-JSON-column.

5. **DTO field not in YAML.** Warning. The DTO interfaces in
   `frontend/src/lib/api/ontology.ts` are the public surface; if YAML omits a
   DTO field it could be intentional (`fields`, `methods` on CodeType are
   nested DTOs, properly handled by their own ORM tables). Surfaces it for
   review without blocking.

## Future extensions

- **Role-based affordance overlay.** Add `roles: { editor: read_only }` per
  field; UI computes effective `edit` from `(base, role)`. The codegen TS
  helper already returns the full config — adding a roles overlay is a
  per-field addition.

- **Undo/redo via audit table.** `audit.enabled: true` is already the YAML
  contract. Wave 2 wires `PatchAuditMiddleware` to log every successful PATCH;
  per-field undo becomes a server query against `modeling_audit_log`.

- **Per-field permission.** YAML adds `requires_permission: <perm_name>` and
  the FastAPI dependency reads the lookup at PATCH time. Mirrors the existing
  ACL system.

- **Bulk PATCH endpoint.** The dispatch table (`ENTITY_TO_PATCH`) already
  enables a generic `POST /api/ontology/patch-batch` route that takes
  `[{entity, fqn, patch}]` instead of N round-trips. Wave 3.

- **Generated guide HTML.** The current `editable_fields_guide.html` is
  hand-maintained. A third codegen would render it from the YAML, killing
  the guide-out-of-sync risk entirely.

## Wave 2 follow-ups (not in this PR)

- Replace handwritten `TermPatch` / `ActionPatch` / `BRPatch` / `AnchorPatch` in
  `queue_actions_api.py` with `from backend.modeling.api._generated_patch_models import ...`
- Add `CodeType` PATCH endpoint (currently no route exists; YAML asserts the
  contract for when it lands).
- Add `PatchAuditMiddleware` and `modeling_audit_log` table.
- Add CI step:
  ```
  .venv/bin/python scripts/codegen_patch_models.py --check
  .venv/bin/python scripts/codegen_inline_wiring.py --check
  .venv/bin/python scripts/lint_editable_sync.py
  ```
- Wire `MainPanel.tsx` Detail components to read `getEditConfig()` and
  dispatch InlineEdit primitives generically.
- Wire `confirm_modal: true` flag through `InlineEditSelect` (today the
  primitive doesn't yet read it).
- Add the `role_user_override` ALTER TABLE on `code_types` and switch the
  YAML's `backend_column: role` → `backend_column: role_user_override`.
