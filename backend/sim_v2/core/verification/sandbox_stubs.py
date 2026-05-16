"""W74 — Sandbox stub injection.

For W59's `BehaviorTwinRunner` to actually run *production* methods, the
sandbox namespace needs the same names the Java source references — JPA
repositories, Spring beans, entity ctors, module-level constants. None of
these can be derived from method's local AST. Three sources fill the gap:

    1. anchor constants    — `DEFAULT_PRODUCTIVITY = 0.95` extracted from
                              `anchor_bindings.anchor_locator` via regex.
                              Section 3 prototyped this for a single
                              method; W74 generalises.
    2. class stubs         — Capitalised identifiers referenced by the
                              translated source but not in scope. Map to
                              a `MagicMock` (callable + attr-tolerant).
                              Optionally upgraded with `spec=` from
                              `code-types.fields`.
    3. repository/bean     — Lowercase identifiers ending in
                              `Repository|Service|Mapper|Client|Manager|Dao`.
                              Spring DI convention. Map to MagicMock.

The end result is a `dict` injected into the runner's globals. Method exec
proceeds without NameError; the actual return value is dominated by primitive
arg paths (which W71 controls). For deeper fidelity W76 will record real Java
return values into `JavaBaselineMap`.

Public API:
    - derive_anchor_constants(session, method_fqn, repo_id)  → dict
    - derive_class_stub(name, fields=None)                   → MagicMock
    - derive_repository_stub(name)                           → MagicMock
    - build_stub_namespace(session, method_fqn, repo_id,
                           python_source)                    → dict
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any
from unittest.mock import MagicMock

from sqlalchemy import text
from sqlalchemy.orm import Session


# ─────────────────────────────────────────────────────────────────────────────
# 1) anchor constants
# ─────────────────────────────────────────────────────────────────────────────


_CONST_RE = re.compile(
    r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)\s*;?\s*$"
)


def _parse_literal(raw: str) -> Any:
    """Try to interpret a Java RHS as a Python literal.

    Handles: int, float, str (single + double quoted), boolean, null,
             BigDecimal("..."), and "..." with `f`/`d`/`l` numeric suffixes.
    Returns the parsed value, or the raw string if not interpretable.
    """
    s = raw.strip()
    # strip trailing semicolon
    if s.endswith(";"):
        s = s[:-1].strip()
    # null
    if s == "null":
        return None
    # boolean
    if s == "true":
        return True
    if s == "false":
        return False
    # string literal
    if (s.startswith('"') and s.endswith('"')) or \
       (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    # BigDecimal("0.95")
    bd = re.match(r'^(?:new\s+)?BigDecimal\s*\(\s*"([^"]+)"\s*\)$', s)
    if bd:
        from decimal import Decimal
        try:
            return Decimal(bd.group(1))
        except Exception:
            return s
    # Number with f/d/l/L suffix → strip
    m = re.match(r"^(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)([fFdDlL])?$", s)
    if m:
        body, suffix = m.group(1), m.group(2)
        try:
            return float(body) if "." in body or "e" in body or "E" in body else int(body)
        except ValueError:
            return s
    # fall-through — give up, return raw
    return s


def derive_anchor_constants(
    session: Session, method_fqn: str, repo_id: str,
) -> dict[str, Any]:
    """Extract `CONST = value` entries from a method's anchor_bindings."""
    rows = session.execute(
        text(
            "SELECT anchor_locator FROM anchor_bindings "
            "WHERE code_method_fqn = :f AND repo_id = :r"
        ),
        {"f": method_fqn, "r": repo_id},
    ).fetchall()
    out: dict[str, Any] = {}
    for (locator,) in rows:
        if not locator:
            continue
        m = _CONST_RE.match(locator)
        if not m:
            continue
        name, raw = m.group(1), m.group(2)
        out[name] = _parse_literal(raw)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 2) class stubs
# ─────────────────────────────────────────────────────────────────────────────


def derive_class_stub(
    name: str, fields: list[str] | None = None,
) -> MagicMock:
    """Build a `MagicMock` impersonating a Java class.

    `fields` (optional) constrains instances (the result of calling the stub)
    to those attribute names — anything else raises AttributeError. Useful for
    catching typos. Without `fields`, the stub and instances are permissive.
    """
    klass = MagicMock(name=name)
    if fields:
        # The instance returned by `Foo(args)` is spec_set'd to the fields.
        klass.return_value = MagicMock(name=f"{name}()", spec_set=fields)
    else:
        klass.return_value = MagicMock(name=f"{name}()")
    return klass


def derive_entity_stub_from_code_types(
    session: Session, class_fqn: str, repo_id: str,
) -> MagicMock:
    """Look up `code_types.fields_json` and build a stub with that spec."""
    row = session.execute(
        text(
            "SELECT fields_json FROM code_types "
            "WHERE fqn = :f AND repo_id = :r"
        ),
        {"f": class_fqn, "r": repo_id},
    ).fetchone()
    fields: list[str] = []
    if row and row[0]:
        try:
            parsed = json.loads(row[0])
            if isinstance(parsed, list):
                fields = [
                    f.get("name", "") for f in parsed
                    if isinstance(f, dict) and f.get("name")
                ]
        except (json.JSONDecodeError, AttributeError):
            pass
    short_name = class_fqn.rsplit(".", 1)[-1]
    return derive_class_stub(short_name, fields=fields if fields else None)


# ─────────────────────────────────────────────────────────────────────────────
# 3) repository / bean stubs
# ─────────────────────────────────────────────────────────────────────────────


_BEAN_SUFFIXES = (
    "Repository", "Service", "Mapper", "Client", "Manager",
    "Dao", "Handler", "Resolver", "Helper", "Translator",
    "Validator", "Builder", "Factory", "Provider", "Loader",
    "Driver",
)


def is_bean_name(name: str) -> bool:
    """Heuristic: camelCase identifier ending in a Spring-bean suffix."""
    if not name or not name[0].islower():
        return False
    return any(name.endswith(s) for s in _BEAN_SUFFIXES)


def derive_repository_stub(name: str) -> MagicMock:
    """Spring bean placeholder. Method calls return MagicMock cascades."""
    return MagicMock(name=name)


# ─────────────────────────────────────────────────────────────────────────────
# 4) Unbound name discovery + integrated builder
# ─────────────────────────────────────────────────────────────────────────────


_PYTHON_BUILTINS = frozenset((
    # Subset of _safe_globals builtins — anything in these is already in scope.
    "abs", "min", "max", "sum", "len", "range", "round", "sorted", "reversed",
    "any", "all", "map", "filter", "zip", "enumerate", "list", "tuple", "set",
    "dict", "str", "int", "float", "bool", "isinstance", "issubclass", "type",
    "True", "False", "None", "Exception", "ValueError", "TypeError",
    "RuntimeError", "ArithmeticError", "print",
    # Other names exposed by _safe_globals
    "Decimal", "getcontext", "math",
))


def find_unbound_names(python_source: str) -> set[str]:
    """Find top-level Name references that aren't bound locally or by builtin.

    Uses ast.walk + local-binding collection. Conservative: returns names
    that *might* be unbound; runtime exec is the authority.
    """
    try:
        tree = ast.parse(python_source)
    except SyntaxError:
        return set()

    # 1) collect every locally bound name (def, class, assigns, fn params)
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
            for a in node.args.args + node.args.kwonlyargs:
                bound.add(a.arg)
            if node.args.vararg:
                bound.add(node.args.vararg.arg)
            if node.args.kwarg:
                bound.add(node.args.kwarg.arg)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for el in target.elts:
                        if isinstance(el, ast.Name):
                            bound.add(el.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                bound.add(node.target.id)
        elif isinstance(node, ast.For):
            if isinstance(node.target, ast.Name):
                bound.add(node.target.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound.add(alias.asname or alias.name)

    # 2) every Name with Load() context that isn't bound or builtin
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in bound or node.id in _PYTHON_BUILTINS:
                continue
            referenced.add(node.id)
    return referenced


def classify_unbound(name: str) -> str:
    """Return: "class" | "bean" | "unknown"."""
    if not name:
        return "unknown"
    if is_bean_name(name):
        return "bean"
    if name[0].isupper():
        return "class"
    return "unknown"


def build_stub_namespace(
    session: Session,
    method_fqn: str,
    repo_id: str,
    python_source: str,
    *,
    code_types_lookup_fqns: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the complete stub namespace for one method translation.

    Combines anchor constants + class stubs + bean stubs into one dict suitable
    for merging into `_safe_globals()`.

    `code_types_lookup_fqns` (optional) lets the caller pass short_name → FQN
    mappings so entity stubs can be spec'd from `code_types.fields_json`.
    """
    ns: dict[str, Any] = {}

    # (a) anchor constants — highest priority (real values)
    ns.update(derive_anchor_constants(session, method_fqn, repo_id))

    # (b) unbound-name discovery via AST
    refs = find_unbound_names(python_source)
    # Don't overwrite anchor consts; only stub names not already provided.
    refs -= set(ns.keys())

    # (c) stub each reference
    lookup = code_types_lookup_fqns or {}
    for name in refs:
        cls = classify_unbound(name)
        if cls == "class":
            class_fqn = lookup.get(name)
            if class_fqn:
                ns[name] = derive_entity_stub_from_code_types(
                    session, class_fqn, repo_id,
                )
            else:
                ns[name] = derive_class_stub(name)
        elif cls == "bean":
            ns[name] = derive_repository_stub(name)
        else:
            # Lowercase non-bean reference (e.g. helper function "lookup")
            # → permissive MagicMock so the exec doesn't fail.
            ns[name] = MagicMock(name=name)

    return ns


__all__ = [
    "classify_unbound",
    "derive_anchor_constants",
    "derive_class_stub",
    "derive_entity_stub_from_code_types",
    "derive_repository_stub",
    "find_unbound_names",
    "is_bean_name",
    "build_stub_namespace",
]
