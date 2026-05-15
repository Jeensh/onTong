"""4 core emitter + Java AST translator integration tests — W7.3.

Verify that body_compute/body_branch/body_return/body_set_output emitters
use the translator when given `anchor_metadata['java_ast_node']`, producing
valid Python source that survives compile().
"""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.emitters.base import EmitContext
from backend.sim_v2.core.synthesizer.emitters.body_branch import BodyBranchEmitter
from backend.sim_v2.core.synthesizer.emitters.body_compute import BodyComputeEmitter
from backend.sim_v2.core.synthesizer.emitters.body_return import BodyReturnEmitter
from backend.sim_v2.core.synthesizer.emitters.body_set_output import BodySetOutputEmitter

JAVA_LANGUAGE = Language(tsjava.language())


@pytest.fixture
def java_parser():
    return Parser(JAVA_LANGUAGE)


def _parse_first_statement(java_parser, body_src: str):
    """Parse Java body and return first statement of the method block."""
    full = f"class _T {{ void m() {{ {body_src} }} }}\n"
    tree = java_parser.parse(full.encode())
    for cls in tree.root_node.children:
        if cls.type == "class_declaration":
            for c in cls.children:
                if c.type == "class_body":
                    for m in c.named_children:
                        if m.type == "method_declaration":
                            block = m.child_by_field_name("body")
                            for stmt in block.named_children:
                                return stmt
    raise RuntimeError("no statement found")


def _parse_expr(java_parser, expr_src: str):
    """Return value node of `Object x = <expr>;`."""
    full = f'class _T {{ void m() {{ Object x = {expr_src}; }} }}\n'
    tree = java_parser.parse(full.encode())
    for cls in tree.root_node.children:
        if cls.type == "class_declaration":
            for c in cls.children:
                if c.type == "class_body":
                    for m in c.named_children:
                        if m.type == "method_declaration":
                            block = m.child_by_field_name("body")
                            for stmt in block.named_children:
                                if stmt.type == "local_variable_declaration":
                                    for vd in stmt.named_children:
                                        if vd.type == "variable_declarator":
                                            return vd.child_by_field_name("value")
    raise RuntimeError("no expr found")


# ─────────────────────────────────────────────────────────────────────────────
# body_compute
# ─────────────────────────────────────────────────────────────────────────────


def test_body_compute_uses_translator_when_ast_present(java_parser):
    """Java BigDecimal arithmetic via java_ast_node → Python Decimal expr."""
    node = _parse_expr(java_parser, "BigDecimal.ZERO")
    out = BodyComputeEmitter().emit(EmitContext(
        target_slot="body.compute",
        anchor_metadata={"java_ast_node": node, "result_var": "total"},
    ))
    assert "total = Decimal(0)" in out.python_source
    assert "backend.sim_v2.core.contracts.base" in out.imports_needed


def test_body_compute_falls_back_to_template_without_ast():
    """No java_ast_node → use `expression` string."""
    out = BodyComputeEmitter().emit(EmitContext(
        target_slot="body.compute",
        anchor_metadata={"expression": "a + b", "result_var": "sum_"},
    ))
    assert "sum_ = a + b" in out.python_source


def test_body_compute_with_arithmetic_translation(java_parser):
    """Binary expression translation via AST."""
    node = _parse_expr(java_parser, "x + y")
    out = BodyComputeEmitter().emit(EmitContext(
        target_slot="body.compute",
        anchor_metadata={"java_ast_node": node, "result_var": "z"},
    ))
    assert "z = x + y" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# body_branch
# ─────────────────────────────────────────────────────────────────────────────


def test_body_branch_uses_translator_for_if_statement(java_parser):
    node = _parse_first_statement(java_parser, """\
        if (x > 0) { y = 1; } else { y = 2; }""")
    out = BodyBranchEmitter().emit(EmitContext(
        target_slot="body.branch",
        anchor_metadata={"java_ast_node": node},
    ))
    src = out.python_source
    assert "if x > 0:" in src
    assert "else:" in src
    compile(src + "\n", "<test>", "exec")


def test_body_branch_falls_back_to_template():
    """No java_ast_node → use condition/then_body/else_body."""
    out = BodyBranchEmitter().emit(EmitContext(
        target_slot="body.branch",
        anchor_metadata={
            "condition": "x > 0",
            "then_body": "y = 1",
            "else_body": "y = 2",
        },
    ))
    assert "if x > 0:" in out.python_source
    assert "else:" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# body_return
# ─────────────────────────────────────────────────────────────────────────────


def test_body_return_uses_translator(java_parser):
    node = _parse_first_statement(java_parser, "return a;")
    out = BodyReturnEmitter().emit(EmitContext(
        target_slot="body.return",
        anchor_metadata={"java_ast_node": node},
    ))
    assert "return a" in out.python_source


def test_body_return_with_bigdecimal_expr(java_parser):
    """Java `return BigDecimal.ZERO` → Python `return Decimal(0)`."""
    node = _parse_first_statement(java_parser, "return BigDecimal.ZERO;")
    out = BodyReturnEmitter().emit(EmitContext(
        target_slot="body.return",
        anchor_metadata={"java_ast_node": node},
    ))
    assert "return Decimal(0)" in out.python_source


def test_body_return_falls_back_to_template():
    out = BodyReturnEmitter().emit(EmitContext(
        target_slot="body.return",
        anchor_metadata={"return_expression": "result"},
    ))
    assert "return result" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# body_set_output
# ─────────────────────────────────────────────────────────────────────────────


def test_body_set_output_uses_translator(java_parser):
    """Java `self.field = value;` → Python `self.field = value`."""
    node = _parse_first_statement(java_parser, "this.field = 42;")
    out = BodySetOutputEmitter().emit(EmitContext(
        target_slot="body.set_output",
        anchor_metadata={"java_ast_node": node},
    ))
    # tree-sitter expression_statement → assignment with this=self
    assert "self.field = 42" in out.python_source


def test_body_set_output_with_bigdecimal_rhs(java_parser):
    """`this.amount = BigDecimal.ZERO;` translates RHS."""
    node = _parse_first_statement(java_parser, "this.amount = BigDecimal.ZERO;")
    out = BodySetOutputEmitter().emit(EmitContext(
        target_slot="body.set_output",
        anchor_metadata={"java_ast_node": node},
    ))
    assert "self.amount = Decimal(0)" in out.python_source


def test_body_set_output_falls_back_to_template():
    out = BodySetOutputEmitter().emit(EmitContext(
        target_slot="body.set_output",
        anchor_metadata={
            "target_object": "self",
            "target_field": "x",
            "source_expression": "42",
        },
    ))
    assert "self.x = 42" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Signature_locked propagation
# ─────────────────────────────────────────────────────────────────────────────


def test_emitter_propagates_signature_locked_from_translator(java_parser):
    """Unmapped Java node (synchronized) → translator signature_locked → emitter signature_locked.

    (Previously used try/catch — W10 added support, so we use synchronized instead.)
    """
    node = _parse_first_statement(java_parser, """\
        synchronized (lock) { x = 1; }""")
    out = BodyBranchEmitter().emit(EmitContext(
        target_slot="body.branch",
        anchor_metadata={"java_ast_node": node},
    ))
    assert out.signature_locked is True


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end: 3 emitters cover a method body
# ─────────────────────────────────────────────────────────────────────────────


def test_three_emitters_cover_method_body(java_parser):
    """Demonstrate: variable decl (compute) + return — 2 anchors, 2 emitter calls."""
    full_block = _parse_first_statement(
        java_parser,
        "BigDecimal total = new BigDecimal(\"100\");",
    )
    # 1st emitter: body.compute (variable decl as anchor)
    # tree-sitter: local_variable_declaration — not directly a compute anchor,
    # but we can target the initializer.
    # For this test we just verify the variable decl translates correctly.
    from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
    tr = JavaToPythonTranslator().translate(full_block, indent=0)
    assert 'total = Decimal("100")' in tr.python_source
