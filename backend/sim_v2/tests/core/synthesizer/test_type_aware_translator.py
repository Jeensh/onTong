"""Type-aware translator tests — W8.3.

Verifies that JavaToPythonTranslator with BigDecimalAwareResolver correctly handles
chained-call BigDecimal patterns by tracking local_scope and resolving method
return types.
"""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.synthesizer.type_resolver import (
    BigDecimalAwareResolver,
    NullTypeResolver,
)

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


# ─────────────────────────────────────────────────────────────────────────────
# Local scope tracking — variable declarations
# ─────────────────────────────────────────────────────────────────────────────


def test_local_scope_tracked_after_declaration(java_parser):
    """After `BigDecimal a = ...;`, subsequent `a.add(...)` should map to '+' operator."""
    body = _parse_method_body(java_parser, """
        BigDecimal a = new BigDecimal("100");
        BigDecimal b = a.add(new BigDecimal("50"));
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    assert 'a = Decimal("100")' in src
    # a.add(...) → (a + Decimal("50"))
    assert '(a + Decimal("50"))' in src


def test_chained_bigdecimal_arithmetic(java_parser):
    """`a.add(b).multiply(c)` — chain of BigDecimal returns."""
    body = _parse_method_body(java_parser, """
        BigDecimal a = new BigDecimal("10");
        BigDecimal b = new BigDecimal("5");
        BigDecimal c = new BigDecimal("2");
        BigDecimal result = a.add(b).multiply(c);
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    # a.add(b) → (a + b), then .multiply(c) → ((a + b) * c)
    assert "((a + b) * c)" in src


def test_chained_bigdecimal_setScale(java_parser):
    """`a.add(b).setScale(2, HALF_UP)` — chain ending in setScale."""
    body = _parse_method_body(java_parser, """
        BigDecimal a = new BigDecimal("10");
        BigDecimal b = new BigDecimal("5");
        BigDecimal result = a.add(b).setScale(2, RoundingMode.HALF_UP);
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    assert "(a + b)" in src
    assert "bd_set_scale" in src
    assert "RoundingMode.HALF_UP" in src


def test_bigdecimal_compareTo_in_condition(java_parser):
    """`a.compareTo(b) > 0` — compareTo result as int."""
    body = _parse_method_body(java_parser, """
        BigDecimal a = new BigDecimal("10");
        BigDecimal b = new BigDecimal("5");
        if (a.compareTo(b) > 0) {
            return;
        }
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    assert "((a > b) - (a < b)) > 0" in src


def test_bigdecimal_intValueExact_after_setScale(java_parser):
    """`a.setScale(0, CEILING).intValueExact()` — real slab-design v2 pattern."""
    body = _parse_method_body(java_parser, """
        BigDecimal a = new BigDecimal("10.5");
        int x = a.setScale(0, RoundingMode.CEILING).intValueExact();
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    # setScale → quantize, then intValueExact → int()
    assert "bd_set_scale" in src
    assert "RoundingMode.CEILING" in src
    assert "int(" in src


# ─────────────────────────────────────────────────────────────────────────────
# Without type info — fallback to W7 behavior
# ─────────────────────────────────────────────────────────────────────────────


def test_no_type_info_method_name_heuristic_still_maps_unambiguous_bd(java_parser):
    """W51 — even with `NullTypeResolver` the unambiguous-BigDecimal-method
    heuristic in `_translate_method_invocation` triggers mapping for the four
    arithmetic method names (subtract / multiply / divide / remainder). The
    heuristic is part of the translator itself, not the resolver, so it fires
    regardless of which resolver is plugged in.
    """
    body = _parse_method_body(java_parser, """
        slab.getSecondWgtHigh().divide(order.getOrderWgtHigh());
    """)
    translator = JavaToPythonTranslator(type_resolver=NullTypeResolver())
    tr = translator.translate(body, indent=0)
    src = tr.python_source
    assert "(slab.getSecondWgtHigh() / order.getOrderWgtHigh())" in src
    assert ".divide(" not in src


def test_bigdecimal_chained_call_via_unknown_receiver_w51(java_parser):
    """W51 closes the W8 limitation: `slab.getX().divide()` previously fell
    through (the resolver had no type info for `slab`). The unambiguous-method
    heuristic now triggers BigDecimal mapping anyway.
    """
    body = _parse_method_body(java_parser, """
        slab.getSecondWgtHigh().divide(order.getOrderWgtHigh());
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    assert "(slab.getSecondWgtHigh() / order.getOrderWgtHigh())" in src
    assert ".divide(" not in src


# ─────────────────────────────────────────────────────────────────────────────
# Enhanced for — element type tracked
# ─────────────────────────────────────────────────────────────────────────────


def test_enhanced_for_tracks_element_type(java_parser):
    """`for (BigDecimal item : items)` — body can use `item.add(...)`."""
    body = _parse_method_body(java_parser, """
        BigDecimal total = new BigDecimal("0");
        for (BigDecimal item : items) {
            total = total.add(item);
        }
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    assert "for item in items:" in src
    # total.add(item) → (total + item) since total is BigDecimal
    assert "(total + item)" in src


# ─────────────────────────────────────────────────────────────────────────────
# Real slab-design v2 — SdMaxSplitCountAction divide chain (W7 limitation case)
# ─────────────────────────────────────────────────────────────────────────────


def test_slab_design_v2_divide_chain_w51(java_parser):
    """Real slab pattern with declared local BigDecimal.

    Original Java:
        BigDecimal raw = slab.getSecondWgtHigh()
            .divide(order.getOrderWgtHigh(), MathContext.DECIMAL64)
            .divide(order.getProductivity(), MathContext.DECIMAL64);

    Before W51 the chain fell back to `.divide(...)` method calls because
    `slab.getSecondWgtHigh()`'s return type was unknown to BigDecimalAwareResolver.

    W51 — the unambiguous-method-name heuristic now maps every `.divide` in
    the chain, including the first one whose receiver is `slab.getX()`.
    The follow-on `raw.setScale(...).intValueExact()` continues to type-resolve
    via the declared `BigDecimal raw` local.
    """
    body = _parse_method_body(java_parser, """
        BigDecimal raw = slab.getSecondWgtHigh()
            .divide(order.getOrderWgtHigh(), MathContext.DECIMAL64)
            .divide(order.getProductivity(), MathContext.DECIMAL64);
        int maxSplit = raw.setScale(0, RoundingMode.CEILING).intValueExact();
    """)
    tr = JavaToPythonTranslator().translate(body, indent=0)
    src = tr.python_source
    # Chain on `slab` — now mapped (W51 heuristic)
    assert ".divide(" not in src
    assert "/" in src  # Python division operator emitted
    # `raw.setScale(...)` — type-aware → quantize
    assert "bd_set_scale" in src
    # `.intValueExact()` on result of setScale (BigDecimal) → int(...)
    assert "int(" in src
    # MathContext.DECIMAL64 is correctly dropped — transparent to Python decimal
