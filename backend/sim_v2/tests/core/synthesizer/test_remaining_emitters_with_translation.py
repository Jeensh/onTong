"""4 remaining core emitter + translator integration tests — W12.

Verify body_loop / body_service_lookup / body_repository_call / body_entity_construction
use translator when given anchor_metadata['java_ast_node'], producing valid Python.
"""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.emitters.base import EmitContext
from backend.sim_v2.core.synthesizer.emitters.body_entity_construction import (
    BodyEntityConstructionEmitter,
)
from backend.sim_v2.core.synthesizer.emitters.body_loop import BodyLoopEmitter
from backend.sim_v2.core.synthesizer.emitters.body_repository_call import (
    BodyRepositoryCallEmitter,
)
from backend.sim_v2.core.synthesizer.emitters.body_service_lookup import (
    BodyServiceLookupEmitter,
)

JAVA_LANGUAGE = Language(tsjava.language())


@pytest.fixture
def java_parser():
    return Parser(JAVA_LANGUAGE)


def _parse_first_statement(java_parser, body_src: str):
    full = f"class _T {{ void m() {{ {body_src} }} }}\n"
    tree = java_parser.parse(full.encode())
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    block = m.child_by_field_name("body")
                    for stmt in block.named_children:
                        return stmt
    raise RuntimeError("no statement")


def _parse_expr(java_parser, expr_src: str):
    full = f'class _T {{ void m() {{ Object x = {expr_src}; }} }}\n'
    tree = java_parser.parse(full.encode())
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            cbody = next(x for x in c.children if x.type == "class_body")
            for m in cbody.named_children:
                if m.type == "method_declaration":
                    block = m.child_by_field_name("body")
                    for stmt in block.named_children:
                        if stmt.type == "local_variable_declaration":
                            for vd in stmt.named_children:
                                if vd.type == "variable_declarator":
                                    return vd.child_by_field_name("value")
    raise RuntimeError("no expr")


# ─────────────────────────────────────────────────────────────────────────────
# body_loop
# ─────────────────────────────────────────────────────────────────────────────


def test_body_loop_uses_translator_for_enhanced_for(java_parser):
    node = _parse_first_statement(java_parser, """
        for (Integer i : items) {
            total = total + i;
        }
    """)
    out = BodyLoopEmitter().emit(EmitContext(
        target_slot="body.loop",
        anchor_metadata={"java_ast_node": node},
    ))
    src = out.python_source
    assert "for i in items:" in src
    assert "total = total + i" in src
    compile(src + "\n", "<test>", "exec")


def test_body_loop_uses_translator_for_while(java_parser):
    node = _parse_first_statement(java_parser, """
        while (x > 0) {
            x = x - 1;
        }
    """)
    out = BodyLoopEmitter().emit(EmitContext(
        target_slot="body.loop",
        anchor_metadata={"java_ast_node": node},
    ))
    src = out.python_source
    assert "while x > 0:" in src
    assert "x = x - 1" in src


def test_body_loop_falls_back_to_template():
    out = BodyLoopEmitter().emit(EmitContext(
        target_slot="body.loop",
        anchor_metadata={
            "iter_var": "order",
            "iterable": "orders",
            "body": "process(order)",
        },
    ))
    assert "for order in orders:" in out.python_source
    assert "process(order)" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# body_entity_construction
# ─────────────────────────────────────────────────────────────────────────────


def test_body_entity_construction_uses_translator(java_parser):
    """`new SlabEntity(orderId)` → `SlabEntity(orderId)`."""
    node = _parse_expr(java_parser, "new SlabEntity(orderId)")
    out = BodyEntityConstructionEmitter().emit(EmitContext(
        target_slot="body.entity_construction",
        anchor_metadata={"java_ast_node": node},
    ))
    assert out.python_source == "SlabEntity(orderId)"


def test_body_entity_construction_with_bigdecimal(java_parser):
    """`new SlabEntity(new BigDecimal("100"))` → `SlabEntity(Decimal("100"))`."""
    node = _parse_expr(java_parser, 'new SlabEntity(new BigDecimal("100"))')
    out = BodyEntityConstructionEmitter().emit(EmitContext(
        target_slot="body.entity_construction",
        anchor_metadata={"java_ast_node": node},
    ))
    assert 'SlabEntity(Decimal("100"))' in out.python_source


def test_body_entity_construction_falls_back_to_template():
    out = BodyEntityConstructionEmitter().emit(EmitContext(
        target_slot="body.entity_construction",
        anchor_metadata={
            "entity_class": "Slab",
            "init_args": "1, 2",
            "result_var": "s",
        },
    ))
    assert "s = Slab(1, 2)" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# body_service_lookup
# ─────────────────────────────────────────────────────────────────────────────


def test_body_service_lookup_uses_translator(java_parser):
    """When passed a method_invocation, translator emits passthrough."""
    node = _parse_expr(java_parser, "applicationContext.getBean(StdService.class)")
    out = BodyServiceLookupEmitter().emit(EmitContext(
        target_slot="body.service_lookup",
        anchor_metadata={"java_ast_node": node},
    ))
    assert "applicationContext.getBean" in out.python_source
    # SpringDI Protocol import still added
    assert "backend.sim_v2.core.contracts.base" in out.imports_needed


def test_body_service_lookup_falls_back_to_template():
    out = BodyServiceLookupEmitter().emit(EmitContext(
        target_slot="body.service_lookup",
        anchor_metadata={
            "service_name": "StdService",
            "result_var": "svc",
        },
    ))
    assert "svc = spring_di.get_bean('StdService')" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# body_repository_call
# ─────────────────────────────────────────────────────────────────────────────


def test_body_repository_call_uses_translator(java_parser):
    """`repo.findById(id)` → passthrough."""
    node = _parse_expr(java_parser, "repo.findById(orderId)")
    out = BodyRepositoryCallEmitter().emit(EmitContext(
        target_slot="body.repository_call",
        anchor_metadata={"java_ast_node": node},
    ))
    assert "repo.findById(orderId)" in out.python_source


def test_body_repository_call_falls_back_to_template():
    out = BodyRepositoryCallEmitter().emit(EmitContext(
        target_slot="body.repository_call",
        anchor_metadata={
            "repo_var": "orderRepo",
            "repo_method": "find_by_id",
            "args": "42",
            "result_var": "order",
        },
    ))
    assert "order = orderRepo.find_by_id(42)" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Signature_locked propagation (4 emitters)
# ─────────────────────────────────────────────────────────────────────────────


def test_4_emitters_propagate_signature_locked(java_parser):
    """Unmapped Java node (synchronized) propagates signature_locked from each emitter."""
    node = _parse_first_statement(java_parser, """\
        synchronized (lock) { x = 1; }""")
    for emitter in (
        BodyLoopEmitter(),
        BodyEntityConstructionEmitter(),
        BodyServiceLookupEmitter(),
        BodyRepositoryCallEmitter(),
    ):
        out = emitter.emit(EmitContext(
            target_slot=emitter.target_slots[0],
            anchor_metadata={"java_ast_node": node},
        ))
        assert out.signature_locked is True, f"{emitter.name} did not propagate signature_locked"
