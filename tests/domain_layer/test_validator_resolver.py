"""C3-3 validator + resolver tests."""
from __future__ import annotations

from backend.modeling.domain_layer import (
    BusinessTerm,
    Cardinality,
    Composition,
    Inheritance,
    InheritanceKind,
    TermKind,
    ValueType,
)
from backend.modeling.domain_layer.resolver import (
    ancestors,
    descendants,
    effective_parts,
)
from backend.modeling.domain_layer.validator import validate_graph


class TestValidator:
    def test_atomic_has_parts_blocked(self):
        terms = [
            BusinessTerm(fqn="t.a", label="A", kind=TermKind.ATOMIC,
                value_type=ValueType.FLOAT),
            BusinessTerm(fqn="t.b", label="B", kind=TermKind.ATOMIC,
                value_type=ValueType.FLOAT),
        ]
        comps = [
            Composition(parent_fqn="t.a", child_fqn="t.b", role_name="x"),
        ]
        errors = validate_graph(terms=terms, inheritance=[], composition=comps)
        assert any(e.code == "ATOMIC_HAS_PARTS" for e in errors)

    def test_inheritance_cycle_detected(self):
        terms = [
            BusinessTerm(fqn=f"t.{n}", label=n, kind=TermKind.COMPOSITE)
            for n in "abc"
        ]
        inh = [
            Inheritance(child_fqn="t.a", parent_fqn="t.b", kind=InheritanceKind.EXTENDS),
            Inheritance(child_fqn="t.b", parent_fqn="t.c", kind=InheritanceKind.EXTENDS),
            Inheritance(child_fqn="t.c", parent_fqn="t.a", kind=InheritanceKind.EXTENDS),
        ]
        errors = validate_graph(terms=terms, inheritance=inh, composition=[])
        assert any(e.code == "INHERITANCE_CYCLE" for e in errors)

    def test_composition_cycle_detected(self):
        terms = [
            BusinessTerm(fqn=f"t.{n}", label=n, kind=TermKind.COMPOSITE)
            for n in "abc"
        ]
        comps = [
            Composition(parent_fqn="t.a", child_fqn="t.b", role_name="r1"),
            Composition(parent_fqn="t.b", child_fqn="t.c", role_name="r2"),
            Composition(parent_fqn="t.c", child_fqn="t.a", role_name="r3"),
        ]
        errors = validate_graph(terms=terms, inheritance=[], composition=comps)
        assert any(e.code == "COMPOSITION_CYCLE" for e in errors)

    def test_dangling_composition_parent_detected(self):
        terms = [BusinessTerm(fqn="t.a", label="A", kind=TermKind.COMPOSITE)]
        comps = [
            Composition(parent_fqn="t.missing", child_fqn="t.a", role_name="r"),
        ]
        errors = validate_graph(terms=terms, inheritance=[], composition=comps)
        codes = {e.code for e in errors}
        assert "COMPOSITION_DANGLING_PARENT" in codes

    def test_clean_graph_no_errors(self):
        terms = [
            BusinessTerm(fqn="t.order", label="주문", kind=TermKind.COMPOSITE),
            BusinessTerm(fqn="t.spec", label="스펙", kind=TermKind.COMPOSITE),
            BusinessTerm(fqn="t.rush", label="긴급", kind=TermKind.COMPOSITE),
        ]
        inh = [
            Inheritance(child_fqn="t.rush", parent_fqn="t.order",
                kind=InheritanceKind.EXTENDS),
        ]
        comps = [
            Composition(parent_fqn="t.order", child_fqn="t.spec", role_name="spec"),
        ]
        errors = validate_graph(terms=terms, inheritance=inh, composition=comps)
        assert errors == []


class TestResolver:
    def test_ancestors_extends_chain(self):
        inh = [
            Inheritance(child_fqn="t.rush", parent_fqn="t.order", kind=InheritanceKind.EXTENDS),
            Inheritance(child_fqn="t.order", parent_fqn="t.base_entity", kind=InheritanceKind.EXTENDS),
        ]
        ancs = ancestors("t.rush", inh)
        assert "t.order" in ancs
        assert "t.base_entity" in ancs

    def test_ancestors_includes_implements(self):
        inh = [
            Inheritance(child_fqn="t.order", parent_fqn="t.trackable", kind=InheritanceKind.IMPLEMENTS),
            Inheritance(child_fqn="t.order", parent_fqn="t.auditable", kind=InheritanceKind.IMPLEMENTS),
        ]
        ancs = ancestors("t.order", inh)
        assert set(ancs) == {"t.trackable", "t.auditable"}

    def test_descendants(self):
        inh = [
            Inheritance(child_fqn="t.standard", parent_fqn="t.order", kind=InheritanceKind.EXTENDS),
            Inheritance(child_fqn="t.rush", parent_fqn="t.order", kind=InheritanceKind.EXTENDS),
        ]
        desc = descendants("t.order", inh)
        assert set(desc) == {"t.standard", "t.rush"}

    def test_effective_parts_inherited(self):
        """RushOrder extends Order — Order 의 parts 도 effective."""
        inh = [
            Inheritance(child_fqn="t.rush", parent_fqn="t.order", kind=InheritanceKind.EXTENDS),
        ]
        comps = [
            Composition(parent_fqn="t.order", child_fqn="t.spec", role_name="spec"),
            Composition(parent_fqn="t.order", child_fqn="t.customer", role_name="customer"),
            Composition(parent_fqn="t.rush", child_fqn="t.priority", role_name="priority"),
        ]
        eff = effective_parts("t.rush", inh, comps)
        roles = {c.role_name for c in eff}
        assert roles == {"spec", "customer", "priority"}

    def test_effective_parts_own_overrides_inherited(self):
        """자손이 같은 role 가지면 자손 우선."""
        inh = [
            Inheritance(child_fqn="t.rush", parent_fqn="t.order", kind=InheritanceKind.EXTENDS),
        ]
        comps = [
            Composition(parent_fqn="t.order", child_fqn="t.spec_v1", role_name="spec"),
            Composition(parent_fqn="t.rush", child_fqn="t.spec_v2", role_name="spec"),
        ]
        eff = effective_parts("t.rush", inh, comps)
        spec_part = next(c for c in eff if c.role_name == "spec")
        assert spec_part.child_fqn == "t.spec_v2"

    def test_effective_parts_multiple_inheritance(self):
        """다중 implements → 각 interface 의 parts 모두 합쳐짐."""
        inh = [
            Inheritance(child_fqn="t.order", parent_fqn="t.trackable", kind=InheritanceKind.IMPLEMENTS),
            Inheritance(child_fqn="t.order", parent_fqn="t.auditable", kind=InheritanceKind.IMPLEMENTS),
        ]
        comps = [
            Composition(parent_fqn="t.trackable", child_fqn="t.tracking_no", role_name="tracking"),
            Composition(parent_fqn="t.auditable", child_fqn="t.created_at", role_name="created"),
            Composition(parent_fqn="t.order", child_fqn="t.order_no", role_name="order_no"),
        ]
        eff = effective_parts("t.order", inh, comps)
        roles = {c.role_name for c in eff}
        assert roles == {"order_no", "tracking", "created"}
