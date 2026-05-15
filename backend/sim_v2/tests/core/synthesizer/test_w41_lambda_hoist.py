"""W41 — multi-statement lambda → nested-def hoisting.

A multi-statement Java lambda body cannot be expressed as a Python lambda
(Python lambdas are expression-only), so the translator emits a nested
`def` immediately before the statement that uses the lambda, and the
lambda expression is replaced with the def's name. Captured variables
flow through Python's lexical closure — no explicit forwarding needed.
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
    """Translate a method body (wrapped in a synthetic class+method)."""
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


# ─────────────────────────────────────────────────────────────────────────────
# Single hoist — basic shape
# ─────────────────────────────────────────────────────────────────────────────


def test_single_multi_stmt_lambda_hoisted(java_parser):
    tr = _translate_body(java_parser, """
        java.util.function.Supplier<Integer> s = () -> {
            int x = 1;
            return x + 1;
        };
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "def _lambda_1():" in src
    assert "    x = 1" in src
    assert "    return x + 1" in src
    assert "s = _lambda_1" in src


def test_hoisted_def_precedes_its_use(java_parser):
    tr = _translate_body(java_parser, """
        java.util.function.Supplier<Integer> s = () -> {
            int x = 7;
            return x;
        };
    """)
    src = tr.python_source
    def_idx = src.find("def _lambda_1")
    use_idx = src.find("s = _lambda_1")
    assert def_idx >= 0
    assert use_idx >= 0
    assert def_idx < use_idx, "def must appear before its use"


# ─────────────────────────────────────────────────────────────────────────────
# Parameterized lambda
# ─────────────────────────────────────────────────────────────────────────────


def test_lambda_with_params_hoisted(java_parser):
    tr = _translate_body(java_parser, """
        java.util.function.BiFunction<Integer,Integer,Integer> f = (a, b) -> {
            int sum = a + b;
            return sum * 2;
        };
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "def _lambda_1(a, b):" in src
    assert "f = _lambda_1" in src


def test_lambda_with_single_named_param_hoisted(java_parser):
    tr = _translate_body(java_parser, """
        java.util.function.Function<Integer,Integer> f = (x) -> {
            int y = x + 1;
            return y * y;
        };
    """)
    assert not tr.signature_locked
    assert "def _lambda_1(x):" in tr.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Multiple hoists in the same block
# ─────────────────────────────────────────────────────────────────────────────


def test_two_sibling_lambdas_get_distinct_names(java_parser):
    tr = _translate_body(java_parser, """
        foo(() -> { int x = 1; return x; });
        bar(() -> { int y = 2; return y; });
    """)
    src = tr.python_source
    assert "def _lambda_1():" in src
    assert "def _lambda_2():" in src
    assert "foo(_lambda_1)" in src
    assert "bar(_lambda_2)" in src


def test_lambda_counter_resets_per_translate_call(java_parser):
    """Each translate() invocation should reset the counter so we get _lambda_1
    again, not _lambda_42 from a prior call."""
    src = "java.util.function.Supplier<Integer> s = () -> { int x = 1; return x; };"
    tr1 = _translate_body(java_parser, src)
    tr2 = _translate_body(java_parser, src)
    assert "_lambda_1" in tr1.python_source
    assert "_lambda_1" in tr2.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Closure semantics — captured variables work via Python closure
# ─────────────────────────────────────────────────────────────────────────────


def test_hoisted_lambda_captures_enclosing_locals_via_closure(java_parser):
    tr = _translate_body(java_parser, """
        int base = 100;
        java.util.function.Supplier<Integer> s = () -> {
            int extra = 50;
            return base + extra;
        };
    """)
    assert not tr.signature_locked
    wrapped = (
        "def f():\n"
        + "\n".join("    " + line for line in tr.python_source.split("\n"))
        + "\n    return s()"
    )
    g: dict = {}
    exec(compile(wrapped, "<test>", "exec"), g)
    assert g["f"]() == 150


def test_hoisted_lambda_with_params_executes(java_parser):
    tr = _translate_body(java_parser, """
        java.util.function.BiFunction<Integer,Integer,Integer> f = (a, b) -> {
            int s = a + b;
            return s * 10;
        };
    """)
    assert not tr.signature_locked
    wrapped = (
        "def runner(a, b):\n"
        + "\n".join("    " + line for line in tr.python_source.split("\n"))
        + "\n    return f(a, b)"
    )
    g: dict = {}
    exec(compile(wrapped, "<test>", "exec"), g)
    assert g["runner"](3, 4) == 70


# ─────────────────────────────────────────────────────────────────────────────
# Production-shaped pattern — embedded in method-invocation arg list
# ─────────────────────────────────────────────────────────────────────────────


def test_lambda_embedded_in_method_invocation_arglist(java_parser):
    """Real production case from slab-design-real-v2:
    historyAction.recordStep(..., () -> { stmt; return expr; });
    """
    tr = _translate_body(java_parser, """
        historyAction.recordStep(order, slab, stepNo, stepName, actionClass, "ONE_SHOT", 1,
            snapshotMap(slab),
            () -> { step.run(order, slab); return snapshotMap(slab); });
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "def _lambda_1():" in src
    assert "step.run(order, slab)" in src
    assert "return snapshotMap(slab)" in src
    assert "historyAction.recordStep" in src
    assert "_lambda_1" in src
    # Def appears before its use
    assert src.find("def _lambda_1") < src.find("historyAction.recordStep")


# ─────────────────────────────────────────────────────────────────────────────
# Single-statement non-return block keeps the existing inline shape only when
# it's a single return; otherwise still hoists.
# ─────────────────────────────────────────────────────────────────────────────


def test_single_non_return_statement_block_also_hoists(java_parser):
    """A block with one non-return statement (e.g. just `step.run(...)`) is not
    expressible inline either, so it hoists too."""
    tr = _translate_body(java_parser, """
        Runnable r = () -> { someAction(); };
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "def _lambda_1():" in src
    assert "someAction()" in src
    assert "r = _lambda_1" in src


def test_single_return_block_still_inlines(java_parser):
    """Existing W27 behavior preserved: `(x) -> { return x + 1; }` → inline lambda."""
    tr = _translate_body(java_parser, """
        java.util.function.Function<Integer,Integer> f = (x) -> { return x + 1; };
    """)
    assert not tr.signature_locked
    src = tr.python_source
    assert "f = lambda x: x + 1" in src
    # No hoist needed for this shape
    assert "def _lambda_" not in src
