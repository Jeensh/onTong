"""FilterSpec → ChromaDB where-clause + BM25 metadata predicate.

FilterSpec shape (TypedDict-compatible dict):
    path:        str          glob, e.g. "wiki/ERP/**"
    folders:     list[str]    ["ERP", "MES/설비"]
    tags:        dict         {"include": [...], "exclude": [...], "mode": "AND"|"OR"}
    authors:     list[str]
    types:       list[str]
    mtime_from:  str          ISO date
    mtime_to:    str
    statuses:    list[str]
    acl:         list[str]
    boolean:     str          DSL expression; when present takes precedence over above
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


def compile_to_chroma_where(spec: dict | None) -> dict | None:
    """Compile FilterSpec dict into a ChromaDB where clause."""
    if not spec:
        return None

    # DSL boolean takes precedence
    boolean = spec.get("boolean")
    if boolean:
        from backend.application.agent.filter_dsl import parse_dsl
        parsed = parse_dsl(boolean)
        return parsed or None

    clauses: list[dict] = []

    if path := spec.get("path"):
        c = _compile_path_glob(path)
        if c:
            clauses.append(c)

    if folders := spec.get("folders"):
        c = _compile_folders(folders)
        if c:
            clauses.append(c)

    if tags := spec.get("tags"):
        c = _compile_tags(tags)
        if c:
            clauses.append(c)

    if authors := spec.get("authors"):
        clauses.append({"authors": {"$in": list(authors)}})

    if types := spec.get("types"):
        if len(types) == 1:
            clauses.append({"doc_type": types[0]})
        else:
            clauses.append({"doc_type": {"$in": list(types)}})

    mfrom = spec.get("mtime_from")
    mto = spec.get("mtime_to")
    if mfrom:
        clauses.append({"mtime_epoch": {"$gte": _iso_to_epoch(mfrom)}})
    if mto:
        clauses.append({"mtime_epoch": {"$lte": _iso_to_epoch(mto)}})

    if statuses := spec.get("statuses"):
        if len(statuses) == 1:
            clauses.append({"status": statuses[0]})
        else:
            clauses.append({"status": {"$in": list(statuses)}})

    if acl := spec.get("acl"):
        clauses.append({"acl_read": {"$in": list(acl)}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def compile_to_bm25_predicate(spec: dict | None) -> Callable[[dict], bool] | None:
    """Compile FilterSpec into a predicate(meta_dict) -> bool for BM25 post-filter."""
    where = compile_to_chroma_where(spec)
    if not where:
        return None

    def pred(meta: dict) -> bool:
        return eval_where(where, meta)

    return pred


# ── Internal compilation helpers ────────────────────────────────────

def _compile_path_glob(pattern: str) -> dict:
    """Convert a path glob into path_depth_* Chroma clauses.

    "wiki/ERP/**" → {"path_depth_1": "ERP"}
    "wiki/ERP/마스터데이터" → {"$and": [{"path_depth_1": "ERP"}, {"path_depth_2": "마스터데이터"}]}
    """
    parts = [p for p in pattern.strip("/").split("/") if p and p not in ("*", "**")]
    if parts and parts[0] == "wiki":
        parts = parts[1:]
    return _depths_to_where(parts)


def _compile_folders(folders: list[str]) -> dict:
    """Multiple folders → $or. Each folder may be nested (A/B) → $and inside."""
    clauses: list[dict] = []
    for folder in folders:
        parts = [p for p in folder.strip("/").split("/") if p]
        if parts and parts[0] == "wiki":
            parts = parts[1:]
        c = _depths_to_where(parts)
        if c:
            clauses.append(c)
    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$or": clauses}


def _depths_to_where(parts: list[str]) -> dict:
    """['ERP', 'MasterData'] → $and of path_depth_1, path_depth_2."""
    if not parts:
        return {}
    clauses = [{f"path_depth_{i}": seg} for i, seg in enumerate(parts, start=1)]
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _compile_tags(tags: dict) -> dict:
    include = list(tags.get("include", []))
    exclude = list(tags.get("exclude", []))
    mode = (tags.get("mode") or "OR").upper()

    clauses: list[dict] = []

    if include:
        if mode == "AND":
            clauses.append({"$and": [{"tags": {"$in": [t]}} for t in include]})
        else:
            clauses.append({"tags": {"$in": include}})

    if exclude:
        clauses.append({"tags": {"$nin": exclude}})

    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _iso_to_epoch(iso: str) -> float:
    """ISO date or datetime → Unix epoch seconds (UTC)."""
    try:
        if "T" in iso:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError as e:
        raise ValueError(f"Invalid ISO date: {iso}") from e


# ── Where-clause evaluator for BM25 post-filter ─────────────────────

def eval_where(clause: dict, meta: dict) -> bool:
    """Evaluate a ChromaDB where dict against a metadata dict. Public for reuse."""
    if "$and" in clause:
        return all(eval_where(sub, meta) for sub in clause["$and"])
    if "$or" in clause:
        return any(eval_where(sub, meta) for sub in clause["$or"])

    for field, cond in clause.items():
        if field.startswith("$"):
            continue
        val = meta.get(field)
        if isinstance(cond, dict):
            if not _eval_ops(cond, val):
                return False
        else:
            if isinstance(val, list):
                if cond not in val:
                    return False
            elif val != cond:
                return False
    return True


def _eval_ops(ops: dict, value: Any) -> bool:
    for op, expected in ops.items():
        if op == "$eq":
            if _eq_or_contains(value, expected) is False:
                return False
        elif op == "$ne":
            if _eq_or_contains(value, expected) is True:
                return False
        elif op == "$in":
            if not _any_in(value, expected):
                return False
        elif op == "$nin":
            if _any_in(value, expected):
                return False
        elif op == "$gte":
            if value is None or value < expected:
                return False
        elif op == "$lte":
            if value is None or value > expected:
                return False
        elif op == "$gt":
            if value is None or value <= expected:
                return False
        elif op == "$lt":
            if value is None or value >= expected:
                return False
    return True


def _eq_or_contains(value: Any, expected: Any) -> bool:
    if isinstance(value, list):
        return expected in value
    return value == expected


def _any_in(value: Any, expected: list) -> bool:
    if isinstance(value, list):
        return any(v in expected for v in value)
    return value in expected
