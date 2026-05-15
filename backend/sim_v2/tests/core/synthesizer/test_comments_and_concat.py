"""Comment + string concat translator tests — W14.1."""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

JAVA_LANGUAGE = Language(tsjava.language())


@pytest.fixture
def java_parser():
    return Parser(JAVA_LANGUAGE)


def _parse_method_body(java_parser, body_src: str):
    full = f"class _T {{ void m() {{ {body_src} }} }}\n"
    tree = java_parser.parse(full.encode())
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            method = next(x for x in body.named_children if x.type == "method_declaration")
            return method.child_by_field_name("body")
    raise RuntimeError("no body")


def _parse_expr(java_parser, expr_src: str):
    full = f'class _T {{ void m() {{ Object x = {expr_src}; }} }}\n'
    tree = java_parser.parse(full.encode())
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            cbody = next(x for x in c.children if x.type == "class_body")
            method = next(x for x in cbody.named_children if x.type == "method_declaration")
            block = method.child_by_field_name("body")
            for stmt in block.named_children:
                if stmt.type == "local_variable_declaration":
                    for vd in stmt.named_children:
                        if vd.type == "variable_declarator":
                            return vd.child_by_field_name("value")
    raise RuntimeError("no expr")


# ─────────────────────────────────────────────────────────────────────────────
# line_comment / block_comment
# ─────────────────────────────────────────────────────────────────────────────


def test_line_comment_translated(java_parser):
    body = _parse_method_body(java_parser, """
        // this is a comment
        x = 1;
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    assert "# this is a comment" in tr.python_source
    assert "x = 1" in tr.python_source
    assert not tr.signature_locked


def test_block_comment_translated(java_parser):
    body = _parse_method_body(java_parser, """
        /* block comment */
        x = 1;
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    assert "# block comment" in tr.python_source


def test_javadoc_block_comment(java_parser):
    body = _parse_method_body(java_parser, """
        /**
         * Javadoc-style comment
         * spanning multiple lines.
         */
        x = 1;
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    assert "# Javadoc-style comment" in src
    assert "# spanning multiple lines." in src


def test_korean_line_comment(java_parser):
    body = _parse_method_body(java_parser, """
        // 한국어 주석
        x = 1;
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    assert "# 한국어 주석" in tr.python_source


# ─────────────────────────────────────────────────────────────────────────────
# String concat with auto-toString
# ─────────────────────────────────────────────────────────────────────────────


def test_string_plus_int_wraps_int(java_parser):
    node = _parse_expr(java_parser, '"count: " + 42')
    src = JavaToPythonTranslator().translate(node).python_source
    assert '"count: " + str(42)' in src


def test_string_plus_var_wraps_var(java_parser):
    """`"x=" + x` where x is BigDecimal (from local scope)."""
    body = _parse_method_body(java_parser, """
        BigDecimal x = new BigDecimal("100");
        String s = "value: " + x;
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    # x is BigDecimal → wrap with str()
    assert '"value: " + str(x)' in src


def test_two_strings_no_wrap(java_parser):
    """`"a" + "b"` — both strings, no wrap needed."""
    node = _parse_expr(java_parser, '"a" + "b"')
    src = JavaToPythonTranslator().translate(node).python_source
    assert '"a" + "b"' in src
    assert "str(" not in src


def test_concat_chain(java_parser):
    """`"x=" + a + ", y=" + b` — chain of concatenations."""
    body = _parse_method_body(java_parser, """
        BigDecimal a = new BigDecimal("1");
        BigDecimal b = new BigDecimal("2");
        String s = "x=" + a + ", y=" + b;
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    # Each non-string operand wrapped with str()
    assert "str(a)" in src
    assert "str(b)" in src


def test_int_plus_int_no_str_wrap(java_parser):
    """`1 + 2` — both numeric, no str() wrap."""
    node = _parse_expr(java_parser, "1 + 2")
    src = JavaToPythonTranslator().translate(node).python_source
    assert src == "1 + 2"
    assert "str(" not in src


def test_concat_with_method_call(java_parser):
    """`"raw=" + obj.getValue()` — method call result wrapped with str()."""
    body = _parse_method_body(java_parser, """
        BigDecimal val = new BigDecimal("100");
        String s = "raw=" + val;
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert '"raw=" + str(val)' in src
