"""C3-1 schema invariant tests."""
from __future__ import annotations

import pytest

from backend.modeling.domain_layer import (
    BusinessRule,
    BusinessTerm,
    Cardinality,
    Composition,
    Inheritance,
    InheritanceKind,
    RuleSeverity,
    TermKind,
    ValueType,
)


class TestBusinessTermFacets:
    def test_interface_auto_abstract(self):
        t = BusinessTerm(fqn="x", label="X", kind=TermKind.COMPOSITE, is_interface=True)
        assert t.is_abstract is True

    def test_atomic_cannot_be_interface(self):
        with pytest.raises(ValueError, match="cannot be interface"):
            BusinessTerm(fqn="x", label="X", kind=TermKind.ATOMIC, is_interface=True)

    def test_atomic_cannot_have_struct_hint(self):
        with pytest.raises(ValueError, match="struct_like_hint"):
            BusinessTerm(fqn="x", label="X", kind=TermKind.ATOMIC, struct_like_hint=True)

    def test_composite_with_all_facets(self):
        t = BusinessTerm(
            fqn="x", label="X", kind=TermKind.COMPOSITE,
            is_abstract=True, is_root_entity=True, struct_like_hint=True,
        )
        assert t.is_abstract and t.is_root_entity and t.struct_like_hint


class TestAtomicValueConstraints:
    def test_range_must_be_2(self):
        with pytest.raises(ValueError, match="length 2"):
            BusinessTerm(fqn="x", label="X", kind=TermKind.ATOMIC,
                value_type=ValueType.FLOAT, range=[1.0])

    def test_range_min_le_max(self):
        with pytest.raises(ValueError, match=r"range\[min\] > range\[max\]"):
            BusinessTerm(fqn="x", label="X", kind=TermKind.ATOMIC,
                value_type=ValueType.FLOAT, range=[1.0, 0.5])

    def test_atomic_with_unit_and_range(self):
        t = BusinessTerm(fqn="c", label="C 함량", kind=TermKind.ATOMIC,
            value_type=ValueType.FLOAT, unit="%", range=[0.10, 0.25])
        assert t.unit == "%"
        assert t.range == [0.10, 0.25]


class TestEdges:
    def test_inheritance_self_loop_blocked(self):
        with pytest.raises(ValueError, match="self-loop"):
            Inheritance(child_fqn="x", parent_fqn="x", kind=InheritanceKind.EXTENDS)

    def test_composition_self_loop_blocked(self):
        with pytest.raises(ValueError, match="self-loop"):
            Composition(parent_fqn="x", child_fqn="x", role_name="r")

    def test_default_cardinality(self):
        c = Composition(parent_fqn="a", child_fqn="b", role_name="r")
        assert c.cardinality == Cardinality.ONE
        assert c.required is True


class TestBusinessRule:
    def test_default_hard(self):
        r = BusinessRule(fqn="rule.x", statement="x > 0")
        assert r.severity == RuleSeverity.HARD
