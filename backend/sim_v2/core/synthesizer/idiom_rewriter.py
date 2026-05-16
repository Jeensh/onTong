"""W75 — Java idiom rewriter.

Translate Java standard-library method invocations to their Python idiom
equivalents. Plugs into `JavaToPythonTranslator._translate_method_invocation`
just before the generic `receiver.method(args)` fallback.

Three lookup tiers, tried in order:

    1. STATIC idioms     — `Math.abs(x)`, `String.valueOf(o)`, `Integer.parseInt(s)`
       (receiver_src equals class name).
    2. TYPED idioms      — `(receiver_type, method, arity)` triples. Fire only
       when the receiver's Java type is known (tracked in `_local_scope`).
    3. UNKNOWN idioms    — `(method, arity)` pairs that are safe regardless
       of receiver type (e.g. `length()` → `len(...)`, `charAt(i)` → `...[i]`).

Returns `None` if no idiom matched — caller falls back to the default
`receiver.method(args)` emission. This way Java methods like
`order.getCmpCd()` (which has no idiom rewrite) are unchanged.

Public API:
    - rewrite_method_invocation(receiver_src, receiver_type, method, arg_strs)
"""
from __future__ import annotations

from typing import Callable


RewriteFn = Callable[[str, list[str]], str]


# ─────────────────────────────────────────────────────────────────────────────
# 1) Unknown-receiver idioms — safe across String / array / Collection
# ─────────────────────────────────────────────────────────────────────────────


_UNKNOWN_IDIOMS: dict[tuple[str, int], RewriteFn] = {
    # `s.length()` / `arr.length` / `coll.size()` all map to len(...)
    ("length", 0):       lambda r, a: f"len({r})",
    # String-only, but unambiguous: only String has charAt(i)/substring/trim/...
    ("charAt", 1):       lambda r, a: f"{r}[{a[0]}]",
    ("substring", 1):    lambda r, a: f"{r}[{a[0]}:]",
    ("substring", 2):    lambda r, a: f"{r}[{a[0]}:{a[1]}]",
    ("startsWith", 1):   lambda r, a: f"{r}.startswith({a[0]})",
    ("endsWith", 1):     lambda r, a: f"{r}.endswith({a[0]})",
    ("toLowerCase", 0):  lambda r, a: f"{r}.lower()",
    ("toUpperCase", 0):  lambda r, a: f"{r}.upper()",
    ("trim", 0):         lambda r, a: f"{r}.strip()",
    ("isBlank", 0):      lambda r, a: f"(not ({r} or '').strip())",
    ("toString", 0):     lambda r, a: f"str({r})",
}


# ─────────────────────────────────────────────────────────────────────────────
# 2) Typed-receiver idioms — receiver_type must be known
# ─────────────────────────────────────────────────────────────────────────────


_TYPED_IDIOMS: dict[tuple[str, str, int], RewriteFn] = {
    # ── String ────────────────────────────────────────────────────────────
    ("String", "isEmpty", 0):           lambda r, a: f"(not {r})",
    ("String", "equals", 1):            lambda r, a: f"({r} == {a[0]})",
    ("String", "equalsIgnoreCase", 1):  lambda r, a: f"({r}.lower() == {a[0]}.lower())",
    ("String", "contains", 1):          lambda r, a: f"({a[0]} in {r})",
    ("String", "indexOf", 1):           lambda r, a: f"{r}.find({a[0]})",
    ("String", "lastIndexOf", 1):       lambda r, a: f"{r}.rfind({a[0]})",
    ("String", "replace", 2):           lambda r, a: f"{r}.replace({a[0]}, {a[1]})",
    ("String", "concat", 1):            lambda r, a: f"({r} + {a[0]})",
    ("String", "split", 1):             lambda r, a: f"{r}.split({a[0]})",

    # ── List / ArrayList / LinkedList ────────────────────────────────────
    ("List", "size", 0):       lambda r, a: f"len({r})",
    ("List", "isEmpty", 0):    lambda r, a: f"(not {r})",
    ("List", "contains", 1):   lambda r, a: f"({a[0]} in {r})",
    ("List", "get", 1):        lambda r, a: f"{r}[{a[0]}]",
    ("List", "set", 2):        lambda r, a: f"{r}.__setitem__({a[0]}, {a[1]})",
    ("List", "add", 1):        lambda r, a: f"{r}.append({a[0]})",
    ("List", "remove", 1):     lambda r, a: f"{r}.remove({a[0]})",
    ("List", "clear", 0):      lambda r, a: f"{r}.clear()",
    ("List", "indexOf", 1):    lambda r, a: f"{r}.index({a[0]})",

    # ── Map / HashMap / LinkedHashMap / TreeMap ──────────────────────────
    ("Map", "size", 0):           lambda r, a: f"len({r})",
    ("Map", "isEmpty", 0):        lambda r, a: f"(not {r})",
    ("Map", "containsKey", 1):    lambda r, a: f"({a[0]} in {r})",
    ("Map", "containsValue", 1):  lambda r, a: f"({a[0]} in {r}.values())",
    ("Map", "get", 1):            lambda r, a: f"{r}.get({a[0]})",
    ("Map", "getOrDefault", 2):   lambda r, a: f"{r}.get({a[0]}, {a[1]})",
    ("Map", "put", 2):            lambda r, a: f"{r}.__setitem__({a[0]}, {a[1]})",
    ("Map", "remove", 1):         lambda r, a: f"{r}.pop({a[0]}, None)",
    ("Map", "clear", 0):          lambda r, a: f"{r}.clear()",
    ("Map", "keySet", 0):         lambda r, a: f"set({r}.keys())",
    ("Map", "values", 0):         lambda r, a: f"{r}.values()",
    ("Map", "entrySet", 0):       lambda r, a: f"{r}.items()",

    # ── Set / HashSet / TreeSet ──────────────────────────────────────────
    ("Set", "size", 0):       lambda r, a: f"len({r})",
    ("Set", "isEmpty", 0):    lambda r, a: f"(not {r})",
    ("Set", "contains", 1):   lambda r, a: f"({a[0]} in {r})",
    ("Set", "add", 1):        lambda r, a: f"{r}.add({a[0]})",
    ("Set", "remove", 1):     lambda r, a: f"{r}.discard({a[0]})",
    ("Set", "clear", 0):      lambda r, a: f"{r}.clear()",

    # ── Optional ─────────────────────────────────────────────────────────
    ("Optional", "isPresent", 0):  lambda r, a: f"({r} is not None)",
    ("Optional", "isEmpty", 0):    lambda r, a: f"({r} is None)",
    ("Optional", "get", 0):        lambda r, a: r,
    ("Optional", "orElse", 1):     lambda r, a: f"({r} if {r} is not None else {a[0]})",
    ("Optional", "orElseGet", 1):  lambda r, a: f"({r} if {r} is not None else {a[0]}())",
}


# ─────────────────────────────────────────────────────────────────────────────
# 3) Static-class idioms — receiver_src matches class identifier
# ─────────────────────────────────────────────────────────────────────────────


_STATIC_IDIOMS: dict[tuple[str, str, int], RewriteFn] = {
    # Math
    ("Math", "abs", 1):    lambda r, a: f"abs({a[0]})",
    ("Math", "min", 2):    lambda r, a: f"min({a[0]}, {a[1]})",
    ("Math", "max", 2):    lambda r, a: f"max({a[0]}, {a[1]})",
    ("Math", "pow", 2):    lambda r, a: f"({a[0]} ** {a[1]})",
    ("Math", "round", 1):  lambda r, a: f"round({a[0]})",
    ("Math", "sqrt", 1):   lambda r, a: f"(({a[0]}) ** 0.5)",
    ("Math", "floor", 1):  lambda r, a: f"int({a[0]} // 1)",
    ("Math", "ceil", 1):   lambda r, a: f"(-int(-({a[0]}) // 1))",
    # Boxing / parsing
    ("String",  "valueOf", 1):  lambda r, a: f"str({a[0]})",
    ("Integer", "parseInt", 1): lambda r, a: f"int({a[0]})",
    ("Long",    "parseLong", 1):  lambda r, a: f"int({a[0]})",
    ("Double",  "parseDouble", 1):lambda r, a: f"float({a[0]})",
    ("Float",   "parseFloat", 1): lambda r, a: f"float({a[0]})",
    ("Boolean", "parseBoolean", 1):lambda r, a: f"({a[0]}.lower() == 'true')",
    ("Integer", "valueOf", 1):  lambda r, a: f"int({a[0]})",
    ("Long",    "valueOf", 1):  lambda r, a: f"int({a[0]})",
    # Objects (java.util.Objects)
    ("Objects", "isNull", 1):     lambda r, a: f"({a[0]} is None)",
    ("Objects", "nonNull", 1):    lambda r, a: f"({a[0]} is not None)",
    ("Objects", "equals", 2):     lambda r, a: f"({a[0]} == {a[1]})",
    ("Objects", "requireNonNull", 1): lambda r, a: a[0],
    # Optional factory
    ("Optional", "of", 1):           lambda r, a: a[0],
    ("Optional", "ofNullable", 1):   lambda r, a: a[0],
    ("Optional", "empty", 0):        lambda r, a: "None",
}


# ─────────────────────────────────────────────────────────────────────────────
# Type normalization — strip generics, alias common families
# ─────────────────────────────────────────────────────────────────────────────


_TYPE_FAMILY: dict[str, str] = {
    "String":          "String",
    "List":            "List",
    "ArrayList":       "List",
    "LinkedList":      "List",
    "Vector":          "List",
    "Map":             "Map",
    "HashMap":         "Map",
    "LinkedHashMap":   "Map",
    "TreeMap":         "Map",
    "ConcurrentHashMap":"Map",
    "Set":             "Set",
    "HashSet":         "Set",
    "TreeSet":         "Set",
    "LinkedHashSet":   "Set",
    "Optional":        "Optional",
}


def _normalize_type(t: str | None) -> str:
    """Java type → canonical family. Strips generics. Returns "" if unknown."""
    if not t:
        return ""
    base = t.split("<", 1)[0].strip()
    return _TYPE_FAMILY.get(base, "")


# ─────────────────────────────────────────────────────────────────────────────
# Public entry
# ─────────────────────────────────────────────────────────────────────────────


def rewrite_method_invocation(
    receiver_src: str,
    receiver_type: str | None,
    method_name: str,
    arg_strs: list[str],
) -> str | None:
    """Try to rewrite a Java idiom invocation to Python.

    Returns the rewritten Python expression, or None if no idiom matched
    (caller should fall back to default `receiver.method(args)` emission).
    """
    arity = len(arg_strs)

    # 1) Static-class idioms (Math.abs / String.valueOf / Integer.parseInt / ...)
    static_key = (receiver_src, method_name, arity)
    if static_key in _STATIC_IDIOMS:
        return _STATIC_IDIOMS[static_key](receiver_src, arg_strs)

    # 2) Typed-receiver idioms — receiver_type known
    family = _normalize_type(receiver_type)
    if family:
        typed_key = (family, method_name, arity)
        if typed_key in _TYPED_IDIOMS:
            return _TYPED_IDIOMS[typed_key](receiver_src, arg_strs)

    # 3) Unknown-receiver idioms — safe regardless of type
    unknown_key = (method_name, arity)
    if unknown_key in _UNKNOWN_IDIOMS:
        return _UNKNOWN_IDIOMS[unknown_key](receiver_src, arg_strs)

    return None


__all__ = [
    "rewrite_method_invocation",
]
