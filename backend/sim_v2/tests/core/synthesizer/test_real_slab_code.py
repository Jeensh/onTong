"""Smoke test — translator on real slab-design v2 Java code.

Demonstrates W7 end-to-end: tree-sitter parses a real method, translator emits Python,
output compiles. Limitations on chained-call BigDecimal recognition documented inline.
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


def test_real_setScale_with_rounding_mode(java_parser):
    """Real slab-design v2 pattern: `raw.setScale(0, RoundingMode.CEILING)`.

    Without type info we can't auto-detect that `raw` is BigDecimal,
    so the translator emits standard method call. RoundingMode.CEILING
    is still translated via field_access path.
    """
    tree = java_parser.parse(b"""
        class _T {
            void m() {
                int maxSplit = raw.setScale(0, RoundingMode.CEILING).intValueExact();
            }
        }
    """)
    # find the local_variable_declaration → variable_declarator → value
    root = tree.root_node
    for c in root.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            method = next(x for x in body.named_children if x.type == "method_declaration")
            block = method.child_by_field_name("body")
            for stmt in block.named_children:
                if stmt.type == "local_variable_declaration":
                    vd = next(x for x in stmt.named_children if x.type == "variable_declarator")
                    value_node = vd.child_by_field_name("value")

                    tr = JavaToPythonTranslator().translate(value_node, indent=0)
                    src = tr.python_source
                    # No BigDecimal heuristic triggers (receiver = `raw`, not the literal class)
                    # But RoundingMode.CEILING should be translated correctly.
                    assert "RoundingMode.CEILING" in src
                    assert "setScale" in src or "bd_set_scale" in src
                    return
    pytest.fail("statement not found")


def test_real_bigdecimal_static_factory(java_parser):
    """`BigDecimal.ZERO.add(something)` — receiver=BigDecimal (literal), so heuristic
    triggers. add → '+' operator."""
    tree = java_parser.parse(b"""
        class _T {
            BigDecimal m(BigDecimal other) {
                return BigDecimal.ZERO.add(other);
            }
        }
    """)
    root = tree.root_node
    for c in root.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            method = next(x for x in body.named_children if x.type == "method_declaration")
            block = method.child_by_field_name("body")
            for stmt in block.named_children:
                if stmt.type == "return_statement":
                    tr = JavaToPythonTranslator().translate(stmt, indent=0)
                    src = tr.python_source
                    # BigDecimal.ZERO → Decimal(0), then .add(other) — but receiver is now
                    # `Decimal(0)`, not literal `BigDecimal`, so .add() is passthrough.
                    # That's still valid Python (Decimal has __add__).
                    assert "Decimal(0)" in src
                    # The chained .add(other) won't be auto-converted to +,
                    # but Python's Decimal.add() method does exist (alternative spelling).
                    # Either way the result compiles:
                    wrapped = "from decimal import Decimal\ndef f(other):\n    " + src.replace("\n", "\n    ")
                    compile(wrapped, "<test>", "exec")
                    return
    pytest.fail("return statement not found")


def test_real_simple_arithmetic_method(java_parser):
    """Real-style: variable decl + arithmetic + return."""
    tree = java_parser.parse(b"""
        class _T {
            int m(int orderWgt, int productivity) {
                int raw = orderWgt / productivity;
                if (raw < 1) {
                    return 1;
                }
                return raw;
            }
        }
    """)
    root = tree.root_node
    for c in root.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            method = next(x for x in body.named_children if x.type == "method_declaration")
            block = method.child_by_field_name("body")
            tr = JavaToPythonTranslator().translate(block, indent=0)
            src = tr.python_source
            assert "raw = orderWgt / productivity" in src
            assert "if raw < 1:" in src
            assert "return 1" in src
            assert "return raw" in src
            wrapped = "def f(orderWgt, productivity):\n" + "\n".join(
                "    " + line for line in src.split("\n")
            )
            compile(wrapped, "<test>", "exec")
            return
    pytest.fail("method not found")
