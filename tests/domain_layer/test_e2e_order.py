"""C3 e2e — 주문 도메인 (주문 + 주문스펙 + 화학성분 + RushOrder + Trackable)."""
from __future__ import annotations

import os
import tempfile

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
from backend.modeling.domain_layer.resolver import effective_parts
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.domain_layer.validator import validate_graph


@pytest.fixture
def fresh_db(monkeypatch):
    from backend.modeling.domain_layer.orm import BusinessTermRow  # noqa: F401
    from backend.modeling.persistence.database import (
        Base, get_engine, reset_engine_for_tests,
    )
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("ONTONG_DB_PATH", path)
    reset_engine_for_tests()
    Base.metadata.create_all(bind=get_engine())
    yield path
    reset_engine_for_tests()
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _build_order_domain():
    """v4 메모 정합 — 주문 = 주문스펙 + 진행관리 + 품질설계 + 화학성분."""
    terms = [
        # root entities
        BusinessTerm(fqn="t.order", label="주문",
            kind=TermKind.COMPOSITE, is_root_entity=True, is_abstract=True),
        # composite parts
        BusinessTerm(fqn="t.order_spec", label="주문스펙",
            kind=TermKind.COMPOSITE, struct_like_hint=True),
        BusinessTerm(fqn="t.progress_info", label="진행관리정보", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.quality_design", label="품질설계정보", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.chemical", label="화학성분",
            kind=TermKind.COMPOSITE, struct_like_hint=True),
        # atomic leaves
        BusinessTerm(fqn="t.diameter", label="직경",
            kind=TermKind.ATOMIC, value_type=ValueType.FLOAT, unit="mm"),
        BusinessTerm(fqn="t.c_pct", label="C 함량",
            kind=TermKind.ATOMIC, value_type=ValueType.FLOAT, unit="%", range=[0.10, 0.25]),
        BusinessTerm(fqn="t.mn_pct", label="Mn 함량",
            kind=TermKind.ATOMIC, value_type=ValueType.FLOAT, unit="%", range=[1.20, 1.60]),
        BusinessTerm(fqn="t.priority_level", label="우선도",
            kind=TermKind.ATOMIC, value_type=ValueType.INT, range=[1, 5]),
        # interface
        BusinessTerm(fqn="t.trackable", label="Trackable",
            kind=TermKind.COMPOSITE, is_interface=True),
        BusinessTerm(fqn="t.tracking_no", label="추적번호",
            kind=TermKind.ATOMIC, value_type=ValueType.STRING),
        # subtypes
        BusinessTerm(fqn="t.standard_order", label="표준주문", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.rush_order", label="긴급주문", kind=TermKind.COMPOSITE),
    ]

    inheritance = [
        # subtypes extend Order
        Inheritance(child_fqn="t.standard_order", parent_fqn="t.order",
            kind=InheritanceKind.EXTENDS),
        Inheritance(child_fqn="t.rush_order", parent_fqn="t.order",
            kind=InheritanceKind.EXTENDS),
        # Order implements Trackable
        Inheritance(child_fqn="t.order", parent_fqn="t.trackable",
            kind=InheritanceKind.IMPLEMENTS),
    ]

    composition = [
        # 주문 has spec / progress / quality / chemical
        Composition(parent_fqn="t.order", child_fqn="t.order_spec", role_name="spec"),
        Composition(parent_fqn="t.order", child_fqn="t.progress_info", role_name="progress"),
        Composition(parent_fqn="t.order", child_fqn="t.quality_design", role_name="quality"),
        Composition(parent_fqn="t.order", child_fqn="t.chemical",
            role_name="chemical", cardinality=Cardinality.MANY),
        # 주문스펙 has diameter
        Composition(parent_fqn="t.order_spec", child_fqn="t.diameter", role_name="diameter"),
        # 화학성분 has C / Mn
        Composition(parent_fqn="t.chemical", child_fqn="t.c_pct", role_name="C"),
        Composition(parent_fqn="t.chemical", child_fqn="t.mn_pct", role_name="Mn"),
        # Trackable has trackingNo
        Composition(parent_fqn="t.trackable", child_fqn="t.tracking_no",
            role_name="trackingNo"),
        # RushOrder adds priorityLevel
        Composition(parent_fqn="t.rush_order", child_fqn="t.priority_level",
            role_name="priorityLevel"),
    ]

    rules = [
        BusinessRule(fqn="rule.c_range", statement="0.10 ≤ C ≤ 0.25",
            severity=RuleSeverity.HARD, terms_ref=["t.c_pct"]),
        BusinessRule(fqn="rule.priority_range", statement="1 ≤ priority ≤ 5",
            severity=RuleSeverity.HARD, terms_ref=["t.priority_level"]),
    ]

    return terms, inheritance, composition, rules


class TestOrderDomainE2E:
    def test_full_pipeline(self, fresh_db):
        terms, inh, comp, rules = _build_order_domain()

        # 1. validate (clean graph)
        errors = validate_graph(terms=terms, inheritance=inh, composition=comp)
        assert errors == [], f"validation errors: {errors}"

        # 2. store
        store = DomainLayerStore()
        store.upsert_terms(repo_id="scm", terms=terms)
        store.upsert_inheritance(repo_id="scm", edges=inh)
        store.upsert_composition(repo_id="scm", edges=comp)
        store.upsert_rules(repo_id="scm", rules=rules)

        all_terms = store.list_terms(repo_id="scm")
        assert len(all_terms) == 13

        # 3. Order 의 effective_parts (inherited via implements Trackable)
        eff_order = effective_parts("t.order", inh, comp)
        order_roles = {c.role_name for c in eff_order}
        assert "spec" in order_roles
        assert "progress" in order_roles
        assert "quality" in order_roles
        assert "chemical" in order_roles
        assert "trackingNo" in order_roles  # implements Trackable

        # 4. RushOrder 의 effective_parts (extends Order, transitively implements Trackable)
        eff_rush = effective_parts("t.rush_order", inh, comp)
        rush_roles = {c.role_name for c in eff_rush}
        assert rush_roles == {"spec", "progress", "quality", "chemical",
                              "trackingNo", "priorityLevel"}

        # 5. atomic leaf 검증
        c_pct = store.get_term("t.c_pct")
        assert c_pct.value_type == ValueType.FLOAT
        assert c_pct.unit == "%"
        assert c_pct.range == [0.10, 0.25]

        # 6. interface 자동 abstract
        trackable = store.get_term("t.trackable")
        assert trackable.is_interface is True
        assert trackable.is_abstract is True

        # 7. 화학성분 (1:N) cardinality
        chem_comp = next(c for c in store.get_composition_children("t.order")
                         if c.role_name == "chemical")
        assert chem_comp.cardinality == Cardinality.MANY
