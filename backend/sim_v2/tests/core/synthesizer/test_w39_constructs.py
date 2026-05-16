"""W39 — update_expression + array_access + BigDecimal.max/min/valueOf.

Each construct is parsed via tree-sitter, translated, and the emitted Python
is asserted to be the expected form. Lambda + try-with-resources (W27) and
nested class (W30) live in their own test files.
"""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.synthesizer.type_resolver import BigDecimalAwareResolver


JAVA_LANGUAGE = Language(tsjava.language())


@pytest.fixture
def java_parser():
    return Parser(JAVA_LANGUAGE)


def _translate_body(java_parser, body_src: str):
    """Translate just a method body (wrapped in a synthetic class+method).
    Returns the TranslationResult of the block."""
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
    raise RuntimeError("no method body found")


def _translate_method_with_bd_param(java_parser, body_src: str):
    """Wraps the body with a BigDecimal param so BigDecimal-typed receivers
    route through the BigDecimal mapper."""
    full = "class _T { void m(BigDecimal x) { " + body_src + " } }"
    tree = java_parser.parse(full.encode())
    for cls in tree.root_node.children:
        if cls.type == "class_declaration":
            for ch in cls.children:
                if ch.type == "class_body":
                    for member in ch.named_children:
                        if member.type == "method_declaration":
                            return JavaToPythonTranslator(
                                type_resolver=BigDecimalAwareResolver(),
                            ).translate(member, indent=0)
    raise RuntimeError("no method found")


# ─────────────────────────────────────────────────────────────────────────────
# update_expression
# ─────────────────────────────────────────────────────────────────────────────


def test_postfix_increment(java_parser):
    tr = _translate_body(java_parser, "int i = 0; i++;")
    assert not tr.signature_locked
    assert "i += 1" in tr.python_source


def test_prefix_increment(java_parser):
    tr = _translate_body(java_parser, "int i = 0; ++i;")
    assert not tr.signature_locked
    assert "i += 1" in tr.python_source


def test_postfix_decrement(java_parser):
    tr = _translate_body(java_parser, "int i = 5; i--;")
    assert not tr.signature_locked
    assert "i -= 1" in tr.python_source


def test_prefix_decrement(java_parser):
    tr = _translate_body(java_parser, "int i = 5; --i;")
    assert not tr.signature_locked
    assert "i -= 1" in tr.python_source


def test_update_expression_in_for_loop(java_parser):
    tr = _translate_body(java_parser, """
        int total = 0;
        for (int i = 0; i < 10; i++) {
            total = total + i;
        }
    """)
    # The increment in the for-update slot becomes `i += 1` somewhere in the output
    assert not tr.signature_locked
    assert "i += 1" in tr.python_source


# ─────────────────────────────────────────────────────────────────────────────
# array_access + array_creation + array_initializer
# ─────────────────────────────────────────────────────────────────────────────


def test_array_access_read(java_parser):
    tr = _translate_body(java_parser, "int[] a = {1, 2, 3}; int v = a[0] + a[1];")
    assert not tr.signature_locked
    assert "v = a[0] + a[1]" in tr.python_source


def test_array_access_write(java_parser):
    tr = _translate_body(java_parser, "int[] a = new int[5]; a[0] = 7;")
    assert not tr.signature_locked
    src = tr.python_source
    assert "[None] * 5" in src
    assert "a[0] = 7" in src


def test_array_initializer_literal(java_parser):
    tr = _translate_body(java_parser, "int[] a = {10, 20, 30};")
    assert not tr.signature_locked
    assert "a = [10, 20, 30]" in tr.python_source


def test_array_creation_one_d(java_parser):
    tr = _translate_body(java_parser, "int[] a = new int[8];")
    assert not tr.signature_locked
    assert "a = [None] * 8" in tr.python_source


def test_array_access_emitted_python_executes(java_parser):
    tr = _translate_body(java_parser, "int[] a = {1, 2, 3}; int v = a[0] + a[2];")
    wrapped = "def f():\n" + "\n".join("    " + line for line in tr.python_source.split("\n")) + "\n    return v"
    g = {}
    exec(compile(wrapped, "<test>", "exec"), g)
    assert g["f"]() == 4


# ─────────────────────────────────────────────────────────────────────────────
# BigDecimal.valueOf + x.max(y) + x.min(y)
# ─────────────────────────────────────────────────────────────────────────────


def test_bigdecimal_valueof_static(java_parser):
    tr = _translate_method_with_bd_param(java_parser, "BigDecimal y = BigDecimal.valueOf(10);")
    assert not tr.signature_locked
    assert "y = Decimal(10)" in tr.python_source


def test_bigdecimal_max_instance(java_parser):
    tr = _translate_method_with_bd_param(java_parser, "BigDecimal y = x.max(BigDecimal.ONE);")
    assert not tr.signature_locked
    assert "max(x, Decimal(1))" in tr.python_source


def test_bigdecimal_min_instance(java_parser):
    tr = _translate_method_with_bd_param(java_parser, "BigDecimal y = x.min(BigDecimal.ZERO);")
    assert not tr.signature_locked
    assert "min(x, Decimal(0))" in tr.python_source


def test_bigdecimal_max_min_combined_compiles(java_parser):
    tr = _translate_method_with_bd_param(java_parser, """
        BigDecimal lo = x.min(BigDecimal.valueOf(100));
        BigDecimal hi = x.max(BigDecimal.valueOf(0));
    """)
    assert not tr.signature_locked
    # Emitted Python must compile (with Decimal in scope)
    from decimal import Decimal
    g = {"Decimal": Decimal, "x": Decimal("50")}
    # Strip the `def m(self, x):` signature so we can exec the body
    body_lines = [line for line in tr.python_source.split("\n") if not line.startswith("def ")]
    wrapped = "x = Decimal('50')\n" + "\n".join(l.lstrip() for l in body_lines)
    exec(compile(wrapped, "<test>", "exec"), g)
    assert g["lo"] == Decimal("50")  # min(50, 100)
    assert g["hi"] == Decimal("50")  # max(50, 0)
