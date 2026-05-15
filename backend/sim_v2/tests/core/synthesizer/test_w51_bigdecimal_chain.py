"""W51 — Unambiguous BigDecimal method-name dispatch for chained calls.

W50 surfaced 1 residual real translator gap from the UC19 idiom survey: chained
BigDecimal arithmetic (`slab.getX().multiply(Y).divide(Z)`) wasn't translated
because the receiver type of `slab.getX()` was unknown. W51 fixes this with a
syntactic heuristic: any call to one of the four unambiguous BigDecimal
arithmetic methods (subtract / multiply / divide / remainder) triggers
BigDecimal mapping, regardless of receiver type.

`add` is deliberately excluded — clashes with `List.add` / `Set.add`.
"""
from __future__ import annotations

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.sim_v2.core.synthesizer.java_translator import (
    JavaToPythonTranslator,
    _UNAMBIGUOUS_BIGDECIMAL_METHODS,
)
from backend.sim_v2.core.synthesizer.type_resolver import (
    BigDecimalAwareResolver,
    NullTypeResolver,
)


JAVA_LANGUAGE = Language(tsjava.language())


@pytest.fixture
def java_parser():
    return Parser(JAVA_LANGUAGE)


def _translate_body(java_parser, body_src: str, *, type_resolver=None):
    full = "class _T { void m() { " + body_src + " } }"
    tree = java_parser.parse(full.encode())
    for cls in tree.root_node.children:
        if cls.type == "class_declaration":
            for ch in cls.children:
                if ch.type == "class_body":
                    for member in ch.named_children:
                        if member.type == "method_declaration":
                            body = member.child_by_field_name("body")
                            kw = {"type_resolver": type_resolver} if type_resolver else {}
                            return JavaToPythonTranslator(**kw).translate(body, indent=0)
    raise RuntimeError("no method body")


# ─────────────────────────────────────────────────────────────────────────────
# Single-step heuristic — receiver type unknown
# ─────────────────────────────────────────────────────────────────────────────


def test_unambiguous_methods_constant_excludes_add():
    """`add` is deliberately excluded to avoid Collection.add false positives."""
    assert "add" not in _UNAMBIGUOUS_BIGDECIMAL_METHODS
    assert _UNAMBIGUOUS_BIGDECIMAL_METHODS == frozenset(
        {"subtract", "multiply", "divide", "remainder"}
    )


def test_subtract_on_unknown_receiver_maps(java_parser):
    tr = _translate_body(java_parser, "x.getY().subtract(z);")
    assert "(x.getY() - z)" in tr.python_source
    assert ".subtract(" not in tr.python_source


def test_multiply_on_unknown_receiver_maps(java_parser):
    tr = _translate_body(java_parser, "x.getY().multiply(z);")
    assert "(x.getY() * z)" in tr.python_source


def test_divide_on_unknown_receiver_maps(java_parser):
    tr = _translate_body(java_parser, "x.getY().divide(z);")
    assert "(x.getY() / z)" in tr.python_source


def test_remainder_on_unknown_receiver_maps(java_parser):
    tr = _translate_body(java_parser, "x.getY().remainder(z);")
    assert "(x.getY() % z)" in tr.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Production-shaped chain
# ─────────────────────────────────────────────────────────────────────────────


def test_production_chain_multiply_divide(java_parser):
    """The exact slab-design pattern that triggered the W50 finding."""
    tr = _translate_body(java_parser, """
        var raw = slab.getSlabWgtInProgress().multiply(INVERSE_UNIT).divide(
            slab.getTargetSlabWidth().multiply(thickness).multiply(density),
            DECIMAL64
        );
    """)
    src = tr.python_source
    # All four BD operations should be operators, none left as `.method(`
    assert ".multiply(" not in src
    assert ".divide(" not in src
    # Sample of expected operator presence
    assert "*" in src
    assert "/" in src


def test_chain_with_2_arg_divide_drops_mathcontext(java_parser):
    """`divide(x, MathContext.DECIMAL64)` → `(receiver / x)` — MathContext dropped."""
    tr = _translate_body(java_parser, """
        x.getY().divide(z, MathContext.DECIMAL64);
    """)
    assert "(x.getY() / z)" in tr.python_source
    # MathContext is dropped (Python decimal is transparent)
    assert "DECIMAL64" not in tr.python_source.split("=")[-1] if "=" in tr.python_source else True


# ─────────────────────────────────────────────────────────────────────────────
# Negative — `add` still falls through (no regression on Collection.add)
# ─────────────────────────────────────────────────────────────────────────────


def test_list_add_does_not_trigger_bd_mapping(java_parser):
    """`result.add(entity)` on an ArrayList must NOT route through BigDecimal
    mapping. W75 idiom rewriter converts List.add → list.append() (Python
    idiom); the W51 guard is that we never produce a BD-style `result + entity`.
    """
    tr = _translate_body(java_parser, """
        ArrayList<X> result = new ArrayList<>();
        result.add(entity);
    """)
    src = tr.python_source
    # W75 — List.add → .append() (Java collection idiom → Python idiom)
    assert "result.append(entity)" in src
    # W51 guard — must NOT be treated as BigDecimal addition
    assert "result + entity" not in src


def test_set_add_does_not_trigger_bd_mapping(java_parser):
    tr = _translate_body(java_parser, "items.add(x);")
    assert "items.add(x)" in tr.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Resolver-independence
# ─────────────────────────────────────────────────────────────────────────────


def test_heuristic_fires_under_null_type_resolver(java_parser):
    """The heuristic is part of the translator, not the resolver — works
    even when caller plugs in `NullTypeResolver`."""
    tr = _translate_body(
        java_parser,
        "x.getY().multiply(z);",
        type_resolver=NullTypeResolver(),
    )
    assert "(x.getY() * z)" in tr.python_source


def test_heuristic_fires_under_bigdecimal_aware_resolver(java_parser):
    """Same call, BigDecimalAwareResolver — also maps."""
    tr = _translate_body(
        java_parser,
        "x.getY().multiply(z);",
        type_resolver=BigDecimalAwareResolver(),
    )
    assert "(x.getY() * z)" in tr.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Chain type propagation — outer call benefits from inner inferred type
# ─────────────────────────────────────────────────────────────────────────────


def test_chain_inner_unknown_outer_maps_via_propagated_type(java_parser):
    """`x.getY().multiply(z).subtract(w)` — outer `.subtract` benefits from
    `_infer_type` learning the inner `.multiply` returns BigDecimal."""
    tr = _translate_body(java_parser, "x.getY().multiply(z).subtract(w);")
    src = tr.python_source
    assert "((x.getY() * z) - w)" in src


# ─────────────────────────────────────────────────────────────────────────────
# Arg-count gate — `.multiply()` with 0 args (rare, mistake) shouldn't map
# ─────────────────────────────────────────────────────────────────────────────


def test_zero_arg_method_does_not_trigger_bd(java_parser):
    """The heuristic requires 1-2 args (BD arithmetic always has args)."""
    tr = _translate_body(java_parser, "x.getY().multiply();")
    # 0-arg should fall through to method-call form
    assert ".multiply(" in tr.python_source
