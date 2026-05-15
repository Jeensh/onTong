"""W54 — Java factory methods → Python literal forms.

Closes a real translator gap surfaced by W53 (UC21 on slab-design-real-v2):
`List<X> slabs = slab == null ? List.of() : List.of(slab);` was preserved
verbatim instead of being translated to `[]` / `[slab]`.

Mappings:
    List.of(...)  → [...]   (empty: List.of() → [])
    Set.of(...)   → {...}   (empty: Set.of()  → set())
    Map.of(k, v, k, v) → {k: v, k: v}  (empty: Map.of() → {})
"""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator


JAVA_LANGUAGE = Language(tsjava.language())


@pytest.fixture
def java_parser():
    return Parser(JAVA_LANGUAGE)


def _translate_body(java_parser, body_src: str):
    full = "class _T { void m() { " + body_src + " } }"
    tree = java_parser.parse(full.encode())
    for cls in tree.root_node.children:
        if cls.type == "class_declaration":
            for ch in cls.children:
                if ch.type == "class_body":
                    for member in ch.named_children:
                        if member.type == "method_declaration":
                            body = member.child_by_field_name("body")
                            return JavaToPythonTranslator().translate(body, indent=0)
    raise RuntimeError("no body")


# ─────────────────────────────────────────────────────────────────────────────
# List.of
# ─────────────────────────────────────────────────────────────────────────────


def test_list_of_empty(java_parser):
    tr = _translate_body(java_parser, 'List<String> a = List.of();')
    assert "a = []" in tr.python_source


def test_list_of_single_arg(java_parser):
    tr = _translate_body(java_parser, 'List<String> a = List.of("x");')
    assert 'a = ["x"]' in tr.python_source


def test_list_of_multi_arg(java_parser):
    tr = _translate_body(java_parser, 'List<String> a = List.of("a", "b", "c");')
    assert 'a = ["a", "b", "c"]' in tr.python_source


def test_list_of_with_var_args(java_parser):
    tr = _translate_body(java_parser, 'List<Object> a = List.of(x, y, z);')
    assert "a = [x, y, z]" in tr.python_source


def test_list_of_in_ternary_production_pattern(java_parser):
    """The exact case from slab-design-real-v2's SdWorkingController.singleDesign."""
    tr = _translate_body(
        java_parser,
        'List<X> slabs = slab == null ? List.of() : List.of(slab);',
    )
    src = tr.python_source
    assert "List.of(" not in src
    assert "[]" in src
    assert "[slab]" in src


# ─────────────────────────────────────────────────────────────────────────────
# Set.of
# ─────────────────────────────────────────────────────────────────────────────


def test_set_of_empty(java_parser):
    tr = _translate_body(java_parser, 'Set<String> s = Set.of();')
    assert "s = set()" in tr.python_source


def test_set_of_args(java_parser):
    tr = _translate_body(java_parser, 'Set<String> s = Set.of("x", "y");')
    assert 's = {"x", "y"}' in tr.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Map.of
# ─────────────────────────────────────────────────────────────────────────────


def test_map_of_empty(java_parser):
    tr = _translate_body(java_parser, 'Map<String,Integer> m = Map.of();')
    assert "m = {}" in tr.python_source


def test_map_of_key_value_pairs(java_parser):
    tr = _translate_body(java_parser, 'Map<String,Integer> m = Map.of("a", 1, "b", 2);')
    assert 'm = {"a": 1, "b": 2}' in tr.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Negative — instance .of() not affected
# ─────────────────────────────────────────────────────────────────────────────


def test_instance_method_of_does_not_trigger(java_parser):
    """`someList.of(x)` — instance method, NOT a factory. Should remain a call."""
    tr = _translate_body(java_parser, 'something.of(x);')
    assert "something.of(x)" in tr.python_source
    # Not transformed into a Python literal
    assert "[" not in tr.python_source or "[x]" not in tr.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Executable round-trip — emitted Python compiles + produces expected values
# ─────────────────────────────────────────────────────────────────────────────


def test_emitted_list_of_compiles_and_executes(java_parser):
    tr = _translate_body(java_parser, 'List<Integer> a = List.of(1, 2, 3);')
    wrapped = (
        "def f():\n"
        + "\n".join("    " + line for line in tr.python_source.split("\n"))
        + "\n    return a"
    )
    g: dict = {}
    exec(compile(wrapped, "<test>", "exec"), g)
    assert g["f"]() == [1, 2, 3]


def test_emitted_set_of_executes(java_parser):
    tr = _translate_body(java_parser, 'Set<Integer> s = Set.of(1, 2, 3);')
    wrapped = (
        "def f():\n"
        + "\n".join("    " + line for line in tr.python_source.split("\n"))
        + "\n    return s"
    )
    g: dict = {}
    exec(compile(wrapped, "<test>", "exec"), g)
    assert g["f"]() == {1, 2, 3}


def test_emitted_map_of_executes(java_parser):
    tr = _translate_body(java_parser, 'Map<String,Integer> m = Map.of("a", 1, "b", 2);')
    wrapped = (
        "def f():\n"
        + "\n".join("    " + line for line in tr.python_source.split("\n"))
        + "\n    return m"
    )
    g: dict = {}
    exec(compile(wrapped, "<test>", "exec"), g)
    assert g["f"]() == {"a": 1, "b": 2}
