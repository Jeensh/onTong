"""C4-3 path syntax parser + validator tests."""
from __future__ import annotations

import pytest

from backend.modeling.domain_layer import (
    BusinessTerm, Cardinality, Composition, Inheritance, InheritanceKind,
    TermKind, ValueType,
)
from backend.modeling.mapping_layer.path import (
    PathParseError, PathSegmentKind,
    parse_path, validate_path,
)


class TestParser:
    @pytest.mark.parametrize("path,expected_seg_count", [
        ("params[0]", 1),
        ("params[0]<RushOrder>", 2),
        ("params[0].spec.diameter", 3),
        ("params[0].chemical[-1].C", 4),
        ("params[0].chemical[*].C", 4),
        ("params[0].chemical[2]", 3),
        ("output.value", 2),
        ("preconditions[0]", 1),
        ("effects[1].target_term", 2),
        ("params[0].spec.diameter.range[1]", 5),
    ])
    def test_valid_paths(self, path, expected_seg_count):
        pp = parse_path(path)
        assert len(pp.segments) == expected_seg_count

    @pytest.mark.parametrize("bad_path", [
        "", "foo", "params", "params[0].spec[abc]",
    ])
    def test_invalid_paths_raise(self, bad_path):
        with pytest.raises(PathParseError):
            parse_path(bad_path)

    def test_subtype_cast_extracted(self):
        pp = parse_path("params[0]<RushOrder>.priority")
        assert pp.segments[1].kind == PathSegmentKind.SUBTYPE_CAST
        assert pp.segments[1].value == "RushOrder"


@pytest.fixture
def order_domain():
    terms = [
        BusinessTerm(fqn="t.order", label="Order", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.rush", label="RushOrder", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.spec", label="Spec", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.diameter", label="Diameter",
            kind=TermKind.ATOMIC, value_type=ValueType.FLOAT, range=[0, 300]),
        BusinessTerm(fqn="t.chemical", label="Chemical", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.c_pct", label="C", kind=TermKind.ATOMIC, value_type=ValueType.FLOAT),
        BusinessTerm(fqn="t.priority", label="Priority", kind=TermKind.ATOMIC, value_type=ValueType.INT),
    ]
    inh = [Inheritance(child_fqn="t.rush", parent_fqn="t.order", kind=InheritanceKind.EXTENDS)]
    comp = [
        Composition(parent_fqn="t.order", child_fqn="t.spec", role_name="spec"),
        Composition(parent_fqn="t.order", child_fqn="t.chemical",
            role_name="chemical", cardinality=Cardinality.MANY),
        Composition(parent_fqn="t.spec", child_fqn="t.diameter", role_name="diameter"),
        Composition(parent_fqn="t.chemical", child_fqn="t.c_pct", role_name="C"),
        Composition(parent_fqn="t.rush", child_fqn="t.priority", role_name="priority"),
    ]
    return terms, inh, comp


class TestValidator:
    def test_traverse_composite_to_atomic(self, order_domain):
        terms, inh, comp = order_domain
        ap = [("주문", "t.order")]
        v = validate_path(parse_path("params[0].spec.diameter"),
            action_params=ap, terms=terms, inheritance=inh, composition=comp)
        assert v.ok
        assert v.last_term_fqn == "t.diameter"

    def test_collection_traversal(self, order_domain):
        terms, inh, comp = order_domain
        ap = [("주문", "t.order")]
        v = validate_path(parse_path("params[0].chemical[-1].C"),
            action_params=ap, terms=terms, inheritance=inh, composition=comp)
        assert v.ok
        assert v.last_term_fqn == "t.c_pct"

    def test_atomic_range_index(self, order_domain):
        terms, inh, comp = order_domain
        ap = [("주문", "t.order")]
        v = validate_path(parse_path("params[0].spec.diameter.range[1]"),
            action_params=ap, terms=terms, inheritance=inh, composition=comp)
        assert v.ok

    def test_subtype_cast_traversal(self, order_domain):
        terms, inh, comp = order_domain
        ap = [("주문", "t.order")]
        v = validate_path(parse_path("params[0]<RushOrder>.priority"),
            action_params=ap, terms=terms, inheritance=inh, composition=comp)
        assert v.ok, v.error

    def test_subtype_cast_unknown_blocked(self, order_domain):
        terms, inh, comp = order_domain
        ap = [("주문", "t.order")]
        v = validate_path(parse_path("params[0]<NonExistent>.x"),
            action_params=ap, terms=terms, inheritance=inh, composition=comp)
        assert not v.ok
        assert "NonExistent" in v.error

    def test_unknown_role_blocked(self, order_domain):
        terms, inh, comp = order_domain
        ap = [("주문", "t.order")]
        v = validate_path(parse_path("params[0].unknown_role"),
            action_params=ap, terms=terms, inheritance=inh, composition=comp)
        assert not v.ok
        assert "not found" in v.error

    def test_subtype_specific_role_not_on_base(self, order_domain):
        """priority 는 RushOrder 에만 있음. base Order 에서 접근하면 fail."""
        terms, inh, comp = order_domain
        ap = [("주문", "t.order")]
        v = validate_path(parse_path("params[0].priority"),
            action_params=ap, terms=terms, inheritance=inh, composition=comp)
        assert not v.ok

    def test_root_slot_allowed(self, order_domain):
        terms, inh, comp = order_domain
        ap = [("주문", "t.order")]
        v = validate_path(parse_path("preconditions[0]"),
            action_params=ap, terms=terms, inheritance=inh, composition=comp)
        assert v.ok

    def test_param_index_out_of_range(self, order_domain):
        terms, inh, comp = order_domain
        ap = [("주문", "t.order")]
        v = validate_path(parse_path("params[99]"),
            action_params=ap, terms=terms, inheritance=inh, composition=comp)
        assert not v.ok
        assert "out of range" in v.error
