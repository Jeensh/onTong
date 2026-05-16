"""W75 — Java idiom rewriter unit tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.synthesizer.idiom_rewriter import (
    rewrite_method_invocation,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1) Unknown-receiver idioms — safe across receiver types
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("method,args,expected", [
    ("length",      [],    "len(name)"),
    ("charAt",      ["0"], "name[0]"),
    ("substring",   ["1"], "name[1:]"),
    ("substring",   ["1", "5"], "name[1:5]"),
    ("startsWith",  ["'X'"], "name.startswith('X')"),
    ("endsWith",    ["'X'"], "name.endswith('X')"),
    ("toLowerCase", [],    "name.lower()"),
    ("toUpperCase", [],    "name.upper()"),
    ("trim",        [],    "name.strip()"),
    ("toString",    [],    "str(name)"),
])
def test_unknown_idiom_rewrites(method, args, expected):
    """Unknown receiver type → still rewrite safe idioms."""
    assert rewrite_method_invocation("name", None, method, args) == expected


def test_isBlank_handles_none():
    """isBlank should not crash on None — emits guarded expression."""
    out = rewrite_method_invocation("s", None, "isBlank", [])
    assert out == "(not (s or '').strip())"


# ─────────────────────────────────────────────────────────────────────────────
# 2) Typed-receiver idioms — String
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("method,args,expected", [
    ("isEmpty",          [],         "(not name)"),
    ("equals",           ["other"],  "(name == other)"),
    ("equalsIgnoreCase", ["other"],  "(name.lower() == other.lower())"),
    ("contains",         ["'sub'"],  "('sub' in name)"),
    ("indexOf",          ["'x'"],    "name.find('x')"),
    ("lastIndexOf",      ["'x'"],    "name.rfind('x')"),
    ("replace",          ["'a'", "'b'"], "name.replace('a', 'b')"),
    ("concat",           ["other"],  "(name + other)"),
    ("split",            ["','"],    "name.split(',')"),
])
def test_string_typed_rewrites(method, args, expected):
    assert rewrite_method_invocation("name", "String", method, args) == expected


# ─────────────────────────────────────────────────────────────────────────────
# 3) Typed-receiver idioms — List
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("method,args,expected", [
    ("size",     [],        "len(items)"),
    ("isEmpty",  [],        "(not items)"),
    ("contains", ["x"],     "(x in items)"),
    ("get",      ["0"],     "items[0]"),
    ("add",      ["y"],     "items.append(y)"),
    ("remove",   ["y"],     "items.remove(y)"),
    ("clear",    [],        "items.clear()"),
    ("indexOf",  ["y"],     "items.index(y)"),
])
def test_list_typed_rewrites(method, args, expected):
    assert rewrite_method_invocation("items", "List", method, args) == expected


def test_list_arraylist_alias():
    """ArrayList / LinkedList 도 List family."""
    for t in ["ArrayList", "LinkedList", "Vector"]:
        out = rewrite_method_invocation("xs", t, "size", [])
        assert out == "len(xs)"


def test_list_generics_stripped():
    """`List<String>` → List family."""
    out = rewrite_method_invocation("xs", "List<String>", "size", [])
    assert out == "len(xs)"


# ─────────────────────────────────────────────────────────────────────────────
# 4) Typed-receiver idioms — Map
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("method,args,expected", [
    ("size",          [],     "len(m)"),
    ("isEmpty",       [],     "(not m)"),
    ("containsKey",   ["k"],  "(k in m)"),
    ("containsValue", ["v"],  "(v in m.values())"),
    ("get",           ["k"],  "m.get(k)"),
    ("getOrDefault",  ["k", "0"], "m.get(k, 0)"),
    ("keySet",        [],     "set(m.keys())"),
    ("values",        [],     "m.values()"),
    ("entrySet",      [],     "m.items()"),
])
def test_map_typed_rewrites(method, args, expected):
    assert rewrite_method_invocation("m", "Map", method, args) == expected


def test_map_hashmap_alias():
    for t in ["HashMap", "LinkedHashMap", "TreeMap", "ConcurrentHashMap"]:
        out = rewrite_method_invocation("d", t, "containsKey", ["k"])
        assert out == "(k in d)"


# ─────────────────────────────────────────────────────────────────────────────
# 5) Typed-receiver idioms — Set
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("method,args,expected", [
    ("size",     [],     "len(s)"),
    ("isEmpty",  [],     "(not s)"),
    ("contains", ["x"],  "(x in s)"),
    ("add",      ["x"],  "s.add(x)"),
    ("remove",   ["x"],  "s.discard(x)"),     # Java throws on missing, Set.discard 는 안전
    ("clear",    [],     "s.clear()"),
])
def test_set_typed_rewrites(method, args, expected):
    assert rewrite_method_invocation("s", "Set", method, args) == expected


# ─────────────────────────────────────────────────────────────────────────────
# 6) Typed-receiver idioms — Optional
# ─────────────────────────────────────────────────────────────────────────────


def test_optional_idioms():
    assert rewrite_method_invocation("opt", "Optional", "isPresent", []) == "(opt is not None)"
    assert rewrite_method_invocation("opt", "Optional", "isEmpty", []) == "(opt is None)"
    assert rewrite_method_invocation("opt", "Optional", "get", []) == "opt"
    assert (
        rewrite_method_invocation("opt", "Optional", "orElse", ["0"])
        == "(opt if opt is not None else 0)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7) Static-class idioms — Math, String.valueOf, Integer.parseInt 등
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("recv,method,args,expected", [
    ("Math", "abs",    ["-3"],            "abs(-3)"),
    ("Math", "min",    ["a", "b"],        "min(a, b)"),
    ("Math", "max",    ["a", "b"],        "max(a, b)"),
    ("Math", "pow",    ["a", "2"],        "(a ** 2)"),
    ("Math", "round",  ["x"],             "round(x)"),
    ("Math", "sqrt",   ["x"],             "((x) ** 0.5)"),
    ("Math", "floor",  ["x"],             "int(x // 1)"),
    ("Math", "ceil",   ["x"],             "(-int(-(x) // 1))"),
    ("String",  "valueOf",      ["n"],    "str(n)"),
    ("Integer", "parseInt",     ["'10'"], "int('10')"),
    ("Long",    "parseLong",    ["s"],    "int(s)"),
    ("Double",  "parseDouble",  ["s"],    "float(s)"),
    ("Float",   "parseFloat",   ["s"],    "float(s)"),
    ("Boolean", "parseBoolean", ["s"],    "(s.lower() == 'true')"),
    ("Integer", "valueOf",      ["x"],    "int(x)"),
])
def test_static_idioms(recv, method, args, expected):
    assert rewrite_method_invocation(recv, None, method, args) == expected


# ─────────────────────────────────────────────────────────────────────────────
# 8) Objects + Optional factory
# ─────────────────────────────────────────────────────────────────────────────


def test_objects_is_null():
    assert rewrite_method_invocation("Objects", None, "isNull", ["x"]) == "(x is None)"
    assert rewrite_method_invocation("Objects", None, "nonNull", ["x"]) == "(x is not None)"
    assert rewrite_method_invocation("Objects", None, "equals", ["a", "b"]) == "(a == b)"
    assert rewrite_method_invocation("Objects", None, "requireNonNull", ["x"]) == "x"


def test_optional_factory():
    assert rewrite_method_invocation("Optional", None, "of", ["x"]) == "x"
    assert rewrite_method_invocation("Optional", None, "ofNullable", ["x"]) == "x"
    assert rewrite_method_invocation("Optional", None, "empty", []) == "None"


# ─────────────────────────────────────────────────────────────────────────────
# 9) No-match → None (fallback)
# ─────────────────────────────────────────────────────────────────────────────


def test_unknown_method_returns_none():
    """Custom user method (not in idiom table) → None → caller falls back."""
    out = rewrite_method_invocation("order", None, "getCmpCd", [])
    assert out is None


def test_unknown_arity_returns_none():
    """Right method, wrong arity → None."""
    # length() is 0-arg; length(x) is not an idiom
    out = rewrite_method_invocation("s", None, "length", ["1"])
    assert out is None


def test_unknown_typed_method_returns_none():
    """List does not have charAt — typed idioms strict on signature."""
    # charAt unknown for List, falls through to unknown idioms (which match charAt(i))
    # so this is expected to *match*. Use a List-specific non-idiom instead.
    out = rewrite_method_invocation("xs", "List", "stream", [])
    assert out is None


# ─────────────────────────────────────────────────────────────────────────────
# 10) Edge: receiver_type 가 generic 으로 감싸진 경우
# ─────────────────────────────────────────────────────────────────────────────


def test_optional_with_generic():
    out = rewrite_method_invocation("opt", "Optional<String>", "isPresent", [])
    assert out == "(opt is not None)"


def test_map_with_double_generic():
    out = rewrite_method_invocation(
        "d", "Map<String, Integer>", "containsKey", ["'k'"],
    )
    assert out == "('k' in d)"
