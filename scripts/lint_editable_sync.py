#!/usr/bin/env python3
"""CI lint — verifies the YAML SSOT stays in sync with backend ORM + DTOs.

Reads:
    toClaude/modeling/editable_fields.yaml
    backend/modeling/{domain_layer,mapping_layer,code_layer}/orm.py  (via import)
    frontend/src/lib/api/ontology.ts                                  (regex parse)

Checks (all errors → exit 1, warnings → exit 0 but printed):
    1. Every YAML field's `backend_column` exists as an attribute on the named
       ORM class.
    2. Every YAML enum (`validation.one_of` and `edit_opts.options`) for the
       same field agrees pairwise.
    3. Every immutable / derived_from field is also marked edit: read_only.
    4. Every field with `serialize: json` has a `_json` ORM column suffix
       (warns if not, since this is a strong convention).
    5. Every DTO field present in ontology.ts but absent from the YAML is
       reported as a WARN (could be intentional).
    6. Every YAML `backend_column` refers to a real ORM column (cf. #1).
       Misnamed columns are the most common bug.

Run:
    python scripts/lint_editable_sync.py
Exit code:
    0 = clean (warnings allowed)
    1 = at least one error
    2 = setup failure (missing files etc.)
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
# Make `backend.*` importable when running this script directly.
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402  (after sys.path tweak — yaml is third-party, fine either way)

YAML_PATH = REPO_ROOT / "toClaude/modeling/editable_fields.yaml"
ONTOLOGY_TS = REPO_ROOT / "frontend/src/lib/api/ontology.ts"

# Map ORM table name → (module_path, class_name). Adjust if entities are added.
ORM_LOCATIONS = {
    "BusinessTermRow": "backend.modeling.domain_layer.orm",
    "BusinessRuleRow": "backend.modeling.domain_layer.orm",
    "ActionRow":       "backend.modeling.mapping_layer.orm",
    "AnchorBindingRow":"backend.modeling.mapping_layer.orm",
    "RealizationRow":  "backend.modeling.mapping_layer.orm",
    "TypeRealizationRow": "backend.modeling.mapping_layer.orm",
    "CodeTypeRow":     "backend.modeling.code_layer.orm",
    "CodeMethodRow":   "backend.modeling.code_layer.orm",
    "CodeFieldRow":    "backend.modeling.code_layer.orm",
    "CallSiteRow":     "backend.modeling.code_layer.orm",
}

# Map entity → DTO interface name in ontology.ts (for the missing-field warn).
ENTITY_TO_DTO = {
    "Term":          "TermDTO",
    "Action":        "ActionDTO",
    "BusinessRule":  "BusinessRuleDTO",
    "AnchorBinding": "AnchorBindingDTO",
    "CodeType":      "CodeTypeDTO",
}


def _load_yaml() -> dict[str, Any]:
    with YAML_PATH.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def _orm_columns(table_class: str) -> set[str]:
    if table_class not in ORM_LOCATIONS:
        raise KeyError(f"unknown ORM class: {table_class}")
    module_path = ORM_LOCATIONS[table_class]
    module = importlib.import_module(module_path)
    cls = getattr(module, table_class)
    # SQLAlchemy: __table__.columns gives the persisted columns.
    return {c.name for c in cls.__table__.columns}


_DTO_BLOCK = re.compile(
    r"export interface (\w+DTO)\s*\{(.*?)\}",
    re.DOTALL,
)
_DTO_FIELD = re.compile(r"^\s*(\w+)\??:", re.MULTILINE)


def _dto_fields() -> dict[str, set[str]]:
    """Return { 'TermDTO': {'fqn', 'label', ...}, ... } parsed from ontology.ts."""
    if not ONTOLOGY_TS.exists():
        return {}
    text = ONTOLOGY_TS.read_text(encoding="utf-8")
    out: dict[str, set[str]] = {}
    for m in _DTO_BLOCK.finditer(text):
        name = m.group(1)
        body = m.group(2)
        fields = set(_DTO_FIELD.findall(body))
        out[name] = fields
    return out


def main() -> int:
    if not YAML_PATH.exists():
        print(f"ERROR: YAML not found at {YAML_PATH}", file=sys.stderr)
        return 2

    yaml_data = _load_yaml()
    entities = yaml_data.get("entities") or {}
    dto_fields = _dto_fields()

    errors: list[str] = []
    warnings: list[str] = []

    for entity_name, entity_spec in entities.items():
        table = entity_spec.get("table")
        if not table:
            errors.append(f"[{entity_name}] missing 'table' key")
            continue
        try:
            columns = _orm_columns(table)
        except (KeyError, ImportError, AttributeError) as exc:
            errors.append(f"[{entity_name}] ORM '{table}' could not be loaded: {exc}")
            continue

        fields = entity_spec.get("fields") or {}
        for field_name, spec in fields.items():
            edit = spec.get("edit", "read_only")
            immutable = bool(spec.get("immutable"))
            derived = spec.get("derived_from")
            backend_column = spec.get("backend_column", field_name)
            serialize = spec.get("serialize", "none")

            # Check 1 + 6: backend_column exists in ORM.
            if backend_column not in columns:
                errors.append(
                    f"[{entity_name}.{field_name}] backend_column "
                    f"{backend_column!r} not in {table} columns "
                    f"(available: {sorted(columns)})"
                )

            # Check 2: enum agreement between validation.one_of and edit_opts.options
            validation = spec.get("validation") or {}
            edit_opts = spec.get("edit_opts") or {}
            one_of = validation.get("one_of")
            options = edit_opts.get("options")
            if one_of and options and set(one_of) != set(options):
                errors.append(
                    f"[{entity_name}.{field_name}] validation.one_of "
                    f"{one_of} disagrees with edit_opts.options {options}"
                )

            # Check 3: immutable/derived fields must be read_only.
            if (immutable or derived) and edit != "read_only":
                errors.append(
                    f"[{entity_name}.{field_name}] immutable/derived field must "
                    f"have edit: read_only (got {edit!r})"
                )

            # Check 4: serialize: json convention — warn if column doesn't end _json
            if serialize == "json" and not backend_column.endswith("_json"):
                warnings.append(
                    f"[{entity_name}.{field_name}] serialize=json but column "
                    f"{backend_column!r} doesn't end with '_json' (convention violated)"
                )

        # Check 5: DTO fields not covered by YAML.
        dto_name = ENTITY_TO_DTO.get(entity_name)
        if dto_name and dto_name in dto_fields:
            yaml_field_names = set(fields.keys())
            dto_only = dto_fields[dto_name] - yaml_field_names
            if dto_only:
                warnings.append(
                    f"[{entity_name}] DTO {dto_name} has fields not in YAML: "
                    f"{sorted(dto_only)} (intentional? add as read_only)"
                )

    # Print results.
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s) — FAIL",
              file=sys.stderr)
        return 1

    print(f"\nOK  {len(entities)} entit{'y' if len(entities) == 1 else 'ies'} "
          f"validated, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
