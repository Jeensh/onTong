"""Method parameter scope tests — W9.2.

Verifies that JavaToPythonTranslator binds method parameter types in local_scope,
enabling type-aware dispatch from the first call onwards.
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


def _parse_method_decl(java_parser, full_method_src: str):
    """Parse a method_declaration node."""
    full = f"class _T {{ {full_method_src} }}\n"
    tree = java_parser.parse(full.encode())
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    return m
    raise RuntimeError("method_declaration not found")


# ─────────────────────────────────────────────────────────────────────────────
# method_declaration → def with parameter binding
# ─────────────────────────────────────────────────────────────────────────────


def test_method_declaration_to_def_signature(java_parser):
    method = _parse_method_decl(java_parser, """
        public BigDecimal compute(BigDecimal a, BigDecimal b) {
            return a.add(b);
        }
    """)
    tr = JavaToPythonTranslator().translate(method, indent=0)
    src = tr.python_source
    assert "def compute(self, a, b):" in src
    # a.add(b) is type-aware via param scope → (a + b)
    assert "return (a + b)" in src


def test_method_declaration_with_chained_call(java_parser):
    method = _parse_method_decl(java_parser, """
        public BigDecimal process(BigDecimal a, BigDecimal b, BigDecimal c) {
            return a.add(b).multiply(c).setScale(2, RoundingMode.HALF_UP);
        }
    """)
    tr = JavaToPythonTranslator().translate(method, indent=0)
    src = tr.python_source
    # parameters bound → all chained methods get BigDecimal mapping
    assert "((a + b) * c)" in src
    assert "bd_set_scale" in src
    assert "RoundingMode.HALF_UP" in src


def test_method_declaration_void_return(java_parser):
    method = _parse_method_decl(java_parser, """
        public void doSomething(int x) {
            x = x + 1;
        }
    """)
    tr = JavaToPythonTranslator().translate(method, indent=0)
    src = tr.python_source
    assert "def doSomething(self, x):" in src
    assert "x = x + 1" in src


def test_method_declaration_no_parameters(java_parser):
    method = _parse_method_decl(java_parser, """
        public BigDecimal getZero() {
            return BigDecimal.ZERO;
        }
    """)
    tr = JavaToPythonTranslator().translate(method, indent=0)
    src = tr.python_source
    assert "def getZero(self):" in src
    assert "return Decimal(0)" in src


# ─────────────────────────────────────────────────────────────────────────────
# register_method_parameters — body-only translation with param scope
# ─────────────────────────────────────────────────────────────────────────────


def test_register_method_parameters_then_translate_body(java_parser):
    """Caller has method_decl node but wants to translate only the body block,
    while keeping param types in scope."""
    method = _parse_method_decl(java_parser, """
        public BigDecimal compute(BigDecimal a, BigDecimal b) {
            return a.add(b);
        }
    """)
    body = method.child_by_field_name("body")

    translator = JavaToPythonTranslator()
    # Trick: register params then translate. translate() resets local_scope at start,
    # so we need to populate AFTER translate's reset.
    # Approach: build a stand-alone helper that doesn't reset.
    translator._collected_imports = set()
    translator._collected_notes = []
    translator._signature_locked = False
    translator._local_scope = {}
    translator.register_method_parameters(method)

    # Now manually dispatch (bypassing translate's reset)
    body_src = translator._dispatch(body, indent=0)
    assert "(a + b)" in body_src


def test_register_method_parameters_idempotent(java_parser):
    """Calling register_method_parameters twice doesn't break — same scope."""
    method = _parse_method_decl(java_parser, """
        void m(BigDecimal a) { return; }
    """)
    translator = JavaToPythonTranslator()
    translator._local_scope = {}
    translator.register_method_parameters(method)
    translator.register_method_parameters(method)
    assert translator._local_scope == {"a": "BigDecimal"}


# ─────────────────────────────────────────────────────────────────────────────
# Mixed: parameters + local variables in same scope
# ─────────────────────────────────────────────────────────────────────────────


def test_method_with_params_and_locals(java_parser):
    method = _parse_method_decl(java_parser, """
        public BigDecimal compute(BigDecimal input) {
            BigDecimal multiplier = new BigDecimal("2");
            return input.multiply(multiplier);
        }
    """)
    tr = JavaToPythonTranslator().translate(method, indent=0)
    src = tr.python_source
    # input is param (BigDecimal) and multiplier is local (BigDecimal)
    # input.multiply(multiplier) → (input * multiplier)
    assert "(input * multiplier)" in src
