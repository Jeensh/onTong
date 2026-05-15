"""W42 — production JPA → SchemaModel loader.

Reads `code_types.annotations_json` + `code_fields.annotations_json` from a
production SQLite DB and produces the entity-dict payload expected by
`JpaAnnotationExtractor`. Bridge between Section 2 modeling artifacts and
Section 4 verification's schema layer.

Public API:
    - parse_annotation(raw)         — `@Foo(a=b,c=d)` → {'name': 'Foo', 'params': {...}}
    - find_annotation(anns, name)   — pluck first parsed annotation by name
    - java_type_to_sql(jt)          — `String` → `VARCHAR`, etc.
    - load_entity_dicts(session, repo_id)  — read DB, return entity dicts
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


# ─────────────────────────────────────────────────────────────────────────────
# Annotation parsing
# ─────────────────────────────────────────────────────────────────────────────


_ANNOTATION_RE = re.compile(r"^@([A-Za-z_][\w.]*)\s*(?:\((.*)\)\s*)?$", re.DOTALL)


def parse_annotation(raw: str) -> dict[str, Any] | None:
    """`@Table(name=X)`               → {'name': 'Table', 'params': {'name': 'X'}}
    `@Id`                            → {'name': 'Id', 'params': {}}
    `@Column(name=X,length=2)`       → {'name': 'Column', 'params': {'name': 'X', 'length': '2'}}
    `@IdClass(value=Foo.class)`      → {'name': 'IdClass', 'params': {'value': 'Foo.class'}}

    Returns None for malformed input. Values are kept as raw strings — caller
    converts (e.g. length=2 → int) as needed. Nested parens (rare) are kept verbatim.
    """
    if not raw or not isinstance(raw, str):
        return None
    m = _ANNOTATION_RE.match(raw.strip())
    if not m:
        return None
    name = m.group(1)
    body = m.group(2)
    params: dict[str, str] = {}
    if body:
        for kv in _split_top_level(body):
            kv = kv.strip()
            if not kv:
                continue
            if "=" in kv:
                k, _, v = kv.partition("=")
                params[k.strip()] = v.strip()
            else:
                # Positional/bare param — record under empty key (rare in JPA)
                params.setdefault("", kv)
    return {"name": name, "params": params}


def _split_top_level(body: str) -> list[str]:
    """Split on commas not inside parens/braces/brackets."""
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def find_annotation(annotations: list[str], target_name: str) -> dict[str, Any] | None:
    """Find first annotation whose parsed `name` equals target_name."""
    for raw in annotations or ():
        parsed = parse_annotation(raw)
        if parsed and parsed["name"] == target_name:
            return parsed
    return None


def has_annotation(annotations: list[str], target_name: str) -> bool:
    return find_annotation(annotations, target_name) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Java type → SQL type
# ─────────────────────────────────────────────────────────────────────────────


_JAVA_TO_SQL: dict[str, str] = {
    "String":         "VARCHAR",
    "Character":      "CHAR",
    "char":           "CHAR",
    "int":            "INT",
    "Integer":        "INT",
    "long":           "BIGINT",
    "Long":           "BIGINT",
    "short":          "SMALLINT",
    "Short":          "SMALLINT",
    "byte":           "TINYINT",
    "Byte":           "TINYINT",
    "float":          "FLOAT",
    "Float":          "FLOAT",
    "double":         "DOUBLE",
    "Double":         "DOUBLE",
    "boolean":        "BOOLEAN",
    "Boolean":        "BOOLEAN",
    "BigDecimal":     "DECIMAL",
    "BigInteger":     "NUMERIC",
    "Date":           "DATE",
    "LocalDate":      "DATE",
    "LocalDateTime":  "TIMESTAMP",
    "Timestamp":      "TIMESTAMP",
    "Time":           "TIME",
    "LocalTime":      "TIME",
    "byte[]":         "BLOB",
}


def java_type_to_sql(java_type: str) -> str:
    """Map a Java type identifier to a representative SQL type. Unknown types
    pass through as the original identifier (caller can refine)."""
    if not java_type:
        return "VARCHAR"
    return _JAVA_TO_SQL.get(java_type, java_type.upper())


# ─────────────────────────────────────────────────────────────────────────────
# Loader — read code_types / code_fields and assemble entity dicts
# ─────────────────────────────────────────────────────────────────────────────


def load_entity_dicts(session: Session, repo_id: str) -> list[dict[str, Any]]:
    """Read `code_types` rows annotated with both `@Entity` and `@Table`, pair
    them with their `@Column`-annotated `code_fields`, and produce the entity
    dicts expected by `JpaAnnotationExtractor.extract()`.

    Skips types lacking either `@Entity` or `@Table` (i.e. POJOs, MappedSuperclass).
    """
    type_rows = session.execute(
        text("SELECT fqn, annotations_json FROM code_types WHERE repo_id = :rid"),
        {"rid": repo_id},
    ).fetchall()

    entities: list[dict[str, Any]] = []

    for type_fqn, ann_json in type_rows:
        try:
            anns = json.loads(ann_json) if ann_json else []
        except json.JSONDecodeError:
            continue
        if not isinstance(anns, list):
            continue
        if not has_annotation(anns, "Entity"):
            continue
        table_ann = find_annotation(anns, "Table")
        if not table_ann:
            continue

        table_name = table_ann["params"].get("name") or _default_table_name(type_fqn)
        schema_name = table_ann["params"].get("schema") or "public"

        columns = _load_columns_for_type(session, type_fqn, repo_id)
        entities.append({
            "class_fqn":   type_fqn,
            "table_name":  table_name,
            "schema_name": schema_name,
            "columns":     columns,
            "indexes":     [],
            "fks":         _extract_fks(columns, type_fqn),
        })

    return entities


def _load_columns_for_type(
    session: Session, type_fqn: str, repo_id: str,
) -> list[dict[str, Any]]:
    """Pull `code_fields` for the given type, map each `@Column`-annotated field
    to a column dict for the JPA extractor.

    Repo handling: prefer rows whose `repo_id` matches; if the type has no rows
    under that repo_id, fall back to legacy rows with `repo_id=''` (synthetic-5k
    keeps fields under that key in the production DB while the type rows are
    tagged with the repo's name). This avoids the v2 duplicate-column bug while
    still surfacing synthetic-repo data.
    """
    rows = session.execute(
        text(
            "SELECT name, type, annotations_json "
            "FROM code_fields WHERE type_fqn = :tfqn AND repo_id = :rid"
        ),
        {"tfqn": type_fqn, "rid": repo_id},
    ).fetchall()
    if not rows:
        rows = session.execute(
            text(
                "SELECT name, type, annotations_json "
                "FROM code_fields WHERE type_fqn = :tfqn AND repo_id = ''"
            ),
            {"tfqn": type_fqn},
        ).fetchall()
    columns: list[dict[str, Any]] = []
    for field_name, field_type, ann_json in rows:
        try:
            anns = json.loads(ann_json) if ann_json else []
        except json.JSONDecodeError:
            continue
        if not isinstance(anns, list):
            continue
        col_ann = find_annotation(anns, "Column")
        if not col_ann:
            continue
        column_name = col_ann["params"].get("name") or field_name
        is_id = has_annotation(anns, "Id")
        is_nullable = col_ann["params"].get("nullable", "true").lower() != "false"
        if is_id:
            is_nullable = False
        join_ann = find_annotation(anns, "JoinColumn")
        columns.append({
            "field_name":   field_name,
            "column_name":  column_name,
            "data_type":    java_type_to_sql(field_type or ""),
            "nullable":     is_nullable,
            "primary_key":  is_id,
            "_join_column": join_ann,  # consumed by _extract_fks
        })
    return columns


def _extract_fks(columns: list[dict[str, Any]], owning_type_fqn: str) -> list[dict[str, Any]]:
    """Synthesize FK descriptors from any `@JoinColumn` annotations on columns."""
    fks: list[dict[str, Any]] = []
    for col in columns:
        join = col.pop("_join_column", None)
        if not join:
            continue
        ref_table = join["params"].get("table") or join["params"].get("referencedTable")
        ref_col = join["params"].get("referencedColumnName") or join["params"].get("name")
        if not ref_table or not ref_col:
            continue
        fks.append({
            "name":       f"fk_{owning_type_fqn.split('.')[-1]}_{col['column_name']}",
            "column":     col["column_name"],
            "ref_table":  ref_table,
            "ref_column": ref_col,
        })
    return fks


def _default_table_name(type_fqn: str) -> str:
    """Fallback when @Table(name=...) is absent — JPA defaults to the simple class name."""
    return type_fqn.rsplit(".", 1)[-1]


__all__ = [
    "find_annotation",
    "has_annotation",
    "java_type_to_sql",
    "load_entity_dicts",
    "parse_annotation",
]
