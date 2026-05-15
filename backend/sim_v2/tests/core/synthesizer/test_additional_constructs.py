"""Additional Java constructs — ternary / assert / instanceof / switch / break / continue — W11."""
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
    raise RuntimeError("method body not found")


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
    raise RuntimeError("expr not found")


# ─────────────────────────────────────────────────────────────────────────────
# Ternary
# ─────────────────────────────────────────────────────────────────────────────


def test_ternary_basic(java_parser):
    node = _parse_expr(java_parser, "a > 0 ? a : -a")
    src = JavaToPythonTranslator().translate(node).python_source
    assert "a if a > 0 else -a" in src


def test_ternary_nested(java_parser):
    node = _parse_expr(java_parser, "x > 0 ? 1 : x < 0 ? -1 : 0")
    src = JavaToPythonTranslator().translate(node).python_source
    # Outer ternary
    assert "1 if x > 0 else" in src
    # Inner ternary
    assert "-1 if x < 0 else 0" in src


def test_ternary_with_method_call(java_parser):
    node = _parse_expr(java_parser, "obj.isReady() ? obj.value() : 0")
    src = JavaToPythonTranslator().translate(node).python_source
    assert "obj.value() if obj.isReady() else 0" in src


def test_ternary_compiles(java_parser):
    body = _parse_method_body(java_parser, "return a > 0 ? a : -a;")
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    wrapped = "def f(a):\n" + "\n".join("    " + l for l in src.split("\n"))
    compile(wrapped, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# assert_statement
# ─────────────────────────────────────────────────────────────────────────────


def test_assert_no_message(java_parser):
    body = _parse_method_body(java_parser, "assert x > 0;")
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert "assert x > 0" in src


def test_assert_with_message(java_parser):
    body = _parse_method_body(java_parser, 'assert x > 0 : "x must be positive";')
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert 'assert x > 0, "x must be positive"' in src


def test_assert_compiles(java_parser):
    body = _parse_method_body(java_parser, "assert x > 0;")
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    wrapped = "def f(x):\n" + "\n".join("    " + l for l in src.split("\n"))
    compile(wrapped, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# instanceof
# ─────────────────────────────────────────────────────────────────────────────


def test_instanceof_string(java_parser):
    node = _parse_expr(java_parser, "x instanceof String")
    src = JavaToPythonTranslator().translate(node).python_source
    assert src == "isinstance(x, str)"


def test_instanceof_integer(java_parser):
    node = _parse_expr(java_parser, "x instanceof Integer")
    src = JavaToPythonTranslator().translate(node).python_source
    assert src == "isinstance(x, int)"


def test_instanceof_bigdecimal(java_parser):
    node = _parse_expr(java_parser, "x instanceof BigDecimal")
    src = JavaToPythonTranslator().translate(node).python_source
    assert src == "isinstance(x, Decimal)"


def test_instanceof_custom_class(java_parser):
    """Custom (non-std) Java class passes through."""
    node = _parse_expr(java_parser, "x instanceof MyClass")
    src = JavaToPythonTranslator().translate(node).python_source
    assert src == "isinstance(x, MyClass)"


# ─────────────────────────────────────────────────────────────────────────────
# switch — Java → Python if/elif chain
# ─────────────────────────────────────────────────────────────────────────────


def test_switch_basic_with_breaks(java_parser):
    body = _parse_method_body(java_parser, """
        switch (x) {
            case 1:
                a = 1;
                break;
            case 2:
                a = 2;
                break;
            default:
                a = 0;
        }
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    assert "if x == 1:" in src
    assert "elif x == 2:" in src
    assert "else:" in src
    assert "a = 1" in src
    assert "a = 0" in src
    # `break` should be filtered out (Python doesn't fall through)
    assert "break" not in src
    assert not tr.signature_locked


def test_switch_no_default(java_parser):
    body = _parse_method_body(java_parser, """
        switch (x) {
            case 1:
                a = 1;
                break;
            case 2:
                a = 2;
                break;
        }
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    assert "if x == 1:" in src
    assert "elif x == 2:" in src
    assert "else:" not in src


def test_switch_fall_through_signature_locked(java_parser):
    """case without break (fall-through) → SIGNATURE_LOCKED."""
    body = _parse_method_body(java_parser, """
        switch (x) {
            case 1:
                a = 1;
            case 2:
                a = 2;
                break;
        }
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    # The first case (without break) triggers fall-through warning
    assert tr.signature_locked
    assert any("fall-through" in n for n in tr.notes)


def test_switch_string_case(java_parser):
    body = _parse_method_body(java_parser, """
        switch (name) {
            case "a":
                result = 1;
                break;
            case "b":
                result = 2;
                break;
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert 'if name == "a":' in src
    assert 'elif name == "b":' in src


def test_switch_compiles(java_parser):
    body = _parse_method_body(java_parser, """
        switch (x) {
            case 1: a = 1; break;
            case 2: a = 2; break;
            default: a = 0;
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    wrapped = "def f(x, a):\n" + "\n".join("    " + l for l in src.split("\n"))
    compile(wrapped, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# break / continue
# ─────────────────────────────────────────────────────────────────────────────


def test_break_in_loop(java_parser):
    body = _parse_method_body(java_parser, """
        while (x > 0) {
            if (x == 5) {
                break;
            }
            x = x - 1;
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert "while x > 0:" in src
    assert "break" in src


def test_continue_in_loop(java_parser):
    body = _parse_method_body(java_parser, """
        while (x > 0) {
            if (x == 5) {
                continue;
            }
            x = x - 1;
        }
    """)
    src = JavaToPythonTranslator().translate(body, indent=0).python_source
    assert "continue" in src


def test_labeled_break_signature_locked(java_parser):
    """`break label;` is not supported in Python — labeled_statement OR labeled break detected."""
    body = _parse_method_body(java_parser, """
        outer: for (int i = 0; i < 10; i++) {
            if (i == 5) {
                break outer;
            }
        }
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    # tree-sitter wraps in labeled_statement (unmapped node) — SIGNATURE_LOCKED at that level.
    # If we ever add labeled_statement handler that drops the label, the inner break_statement's
    # identifier child would re-trigger the SIGNATURE_LOCKED with "labeled break" note.
    assert tr.signature_locked
    # The note should mention either labeled_statement or labeled break
    assert any("labeled_statement" in n or "labeled break" in n for n in tr.notes)


def test_labeled_break_via_direct_break_statement(java_parser):
    """When break_statement is reached directly (not wrapped in labeled_statement),
    the identifier child triggers labeled-break detection."""
    full = (
        "class _T { void m() {\n"
        "    for (int i = 0; i < 10; i++) {\n"
        "        break inner;\n"
        "    }\n"
        "} }\n"
    )
    tree = java_parser.parse(full.encode())
    # find the break_statement node
    break_node = None
    def find(n):
        nonlocal break_node
        if n.type == "break_statement":
            break_node = n
            return
        for c in n.named_children:
            find(c)
            if break_node:
                return
    find(tree.root_node)
    assert break_node is not None
    tr = JavaToPythonTranslator().translate(break_node, indent=0)
    assert tr.signature_locked
    assert any("labeled break" in n for n in tr.notes)
