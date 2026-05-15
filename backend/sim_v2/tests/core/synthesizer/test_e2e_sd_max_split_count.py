"""End-to-end test — SdMaxSplitCountAction.execute() — W9.3.

Real slab-design v2 pattern. With OntologyTypeResolver populated for SDSlabEntity
+ SDOrderEntity getters, the full chain `slab.getSecondWgtHigh().divide(...)`
becomes BigDecimal-aware Python.
"""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tree_sitter import Language, Parser

from backend.modeling.code_layer.orm import CodeFieldRow, CodeMethodRow, CodeTypeRow
from backend.modeling.persistence.database import Base
from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.synthesizer.ontology_type_resolver import OntologyTypeResolver
from backend.sim_v2.core.synthesizer.type_resolver import (
    BigDecimalAwareResolver,
    CompositeTypeResolver,
)

JAVA_LANGUAGE = Language(tsjava.language())


@pytest.fixture
def session_with_slab_ontology():
    """Pre-populate Code Layer with SDSlabEntity + SDOrderEntity BigDecimal getters."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        CodeTypeRow.__table__,
        CodeFieldRow.__table__,
        CodeMethodRow.__table__,
    ])
    with Session(engine) as s:
        s.add_all([
            CodeTypeRow(
                fqn="com.example.slabdesign.entity.SDSlabEntity",
                simple_name="SDSlabEntity",
                package="com.example.slabdesign.entity",
                kind="CLASS", role="entity", repo_id="slab-v2",
            ),
            CodeTypeRow(
                fqn="com.example.slabdesign.entity.SDOrderEntity",
                simple_name="SDOrderEntity",
                package="com.example.slabdesign.entity",
                kind="CLASS", role="entity", repo_id="slab-v2",
            ),
            CodeMethodRow(
                fqn="com.example.slabdesign.entity.SDSlabEntity#getSecondWgtHigh",
                name="getSecondWgtHigh",
                parent_type_fqn="com.example.slabdesign.entity.SDSlabEntity",
                return_type="java.math.BigDecimal",
                repo_id="slab-v2",
            ),
            CodeMethodRow(
                fqn="com.example.slabdesign.entity.SDOrderEntity#getOrderWgtHigh",
                name="getOrderWgtHigh",
                parent_type_fqn="com.example.slabdesign.entity.SDOrderEntity",
                return_type="java.math.BigDecimal",
                repo_id="slab-v2",
            ),
            CodeMethodRow(
                fqn="com.example.slabdesign.entity.SDOrderEntity#getProductivity",
                name="getProductivity",
                parent_type_fqn="com.example.slabdesign.entity.SDOrderEntity",
                return_type="java.math.BigDecimal",
                repo_id="slab-v2",
            ),
            CodeMethodRow(
                fqn="com.example.slabdesign.entity.SDSlabEntity#setMaxSplitCountUpper",
                name="setMaxSplitCountUpper",
                parent_type_fqn="com.example.slabdesign.entity.SDSlabEntity",
                return_type="void",
                repo_id="slab-v2",
            ),
        ])
        s.commit()
        yield s


@pytest.fixture
def java_parser():
    return Parser(JAVA_LANGUAGE)


def test_full_sd_max_split_count_execute(session_with_slab_ontology, java_parser):
    """Translate the body of SdMaxSplitCountAction.execute().

    Java source:
        public void execute(SDOrderEntity order, SDSlabEntity slab) {
            BigDecimal raw = slab.getSecondWgtHigh()
                .divide(order.getOrderWgtHigh(), MathContext.DECIMAL64)
                .divide(order.getProductivity(), MathContext.DECIMAL64);

            int maxSplit = raw.setScale(0, RoundingMode.CEILING).intValueExact();

            if (maxSplit < 1) {
                throw new RuntimeException("maxSplit < 1");
            }

            slab.setMaxSplitCountUpper(maxSplit);
        }

    Expected Python (essentials):
        def execute(self, order, slab):
            raw = (slab.getSecondWgtHigh() / order.getOrderWgtHigh()) / order.getProductivity()
            maxSplit = int(bd_set_scale(raw, 0, RoundingMode.CEILING))
            if maxSplit < 1: ...
            slab.setMaxSplitCountUpper(maxSplit)
    """
    java_src = b"""
        class SdMaxSplitCountAction {
            public void execute(SDOrderEntity order, SDSlabEntity slab) {
                BigDecimal raw = slab.getSecondWgtHigh()
                    .divide(order.getOrderWgtHigh(), MathContext.DECIMAL64)
                    .divide(order.getProductivity(), MathContext.DECIMAL64);

                int maxSplit = raw.setScale(0, RoundingMode.CEILING).intValueExact();

                if (maxSplit < 1) {
                    throw new RuntimeException("maxSplit < 1");
                }

                slab.setMaxSplitCountUpper(maxSplit);
            }
        }
    """
    tree = java_parser.parse(java_src)
    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    method = m
                    break
    assert method is not None

    composite = CompositeTypeResolver([
        OntologyTypeResolver(session_with_slab_ontology, "slab-v2"),
        BigDecimalAwareResolver(),
    ])
    translator = JavaToPythonTranslator(type_resolver=composite)
    tr = translator.translate(method, indent=0)
    src = tr.python_source

    # Function signature
    assert "def execute(self, order, slab):" in src

    # slab.getSecondWgtHigh() returns BigDecimal (via OntologyResolver)
    # .divide(order.getOrderWgtHigh(), ...) → / operator (BigDecimal heuristic)
    # Chained again → / operator
    assert "raw = " in src
    # All three method-call chain steps should be replaced with / operators
    assert "(slab.getSecondWgtHigh() / order.getOrderWgtHigh())" in src
    assert "/ order.getProductivity()" in src
    # MathContext.DECIMAL64 still surfaces but as a side argument that's dropped
    # by binary op map (which only consumes first arg). That's expected — verify.

    # maxSplit = raw.setScale(0, RoundingMode.CEILING).intValueExact()
    # raw is BigDecimal (declared) → setScale → bd_set_scale → intValueExact → int()
    assert "maxSplit = int(" in src
    assert "bd_set_scale" in src
    assert "RoundingMode.CEILING" in src

    # if maxSplit < 1 — pre-existing translation
    assert "if maxSplit < 1:" in src

    # W10: throw_statement now maps. RuntimeException → RuntimeError.
    assert 'raise RuntimeError("maxSplit < 1")' in src
    assert not tr.signature_locked

    # slab.setMaxSplitCountUpper(maxSplit) — void return, regular method call
    assert "slab.setMaxSplitCountUpper(maxSplit)" in src


def test_translator_without_ontology_w51_heuristic(session_with_slab_ontology, java_parser):
    """Same input, with only BigDecimalAwareResolver. Pre-W51 the chained call
    fell back to a literal `.divide(...)` call because slab's return type was
    unknown. W51's unambiguous-method-name heuristic now maps it anyway —
    even without ontology, `.divide` is mapped to Python `/`.
    """
    java_src = b"""
        class _T {
            void m(SDOrderEntity order, SDSlabEntity slab) {
                BigDecimal raw = slab.getSecondWgtHigh()
                    .divide(order.getOrderWgtHigh());
            }
        }
    """
    tree = java_parser.parse(java_src)
    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    method = m
                    break

    translator = JavaToPythonTranslator(type_resolver=BigDecimalAwareResolver())
    tr = translator.translate(method, indent=0)
    src = tr.python_source

    # W51 — chain now maps without needing ontology
    assert ".divide(" not in src
    assert "/ order.getOrderWgtHigh()" in src
