"""C3-2 store CRUD tests."""
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
from backend.modeling.domain_layer.store import DomainLayerStore


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


def _sample_terms():
    return [
        BusinessTerm(fqn="term.scm.order", label="주문",
            kind=TermKind.COMPOSITE, is_root_entity=True),
        BusinessTerm(fqn="term.scm.order_spec", label="주문스펙",
            kind=TermKind.COMPOSITE, struct_like_hint=True),
        BusinessTerm(fqn="term.scm.diameter", label="직경",
            kind=TermKind.ATOMIC, value_type=ValueType.FLOAT, unit="mm"),
    ]


class TestDomainStore:
    def test_term_crud(self, fresh_db):
        store = DomainLayerStore()
        n = store.upsert_terms(repo_id="r1", terms=_sample_terms())
        assert n == 3
        all_terms = store.list_terms(repo_id="r1")
        assert len(all_terms) == 3

        order = store.get_term("term.scm.order")
        assert order is not None
        assert order.is_root_entity is True

    def test_filter_by_kind(self, fresh_db):
        store = DomainLayerStore()
        store.upsert_terms(repo_id="r1", terms=_sample_terms())
        atomics = store.list_terms(repo_id="r1", kind=TermKind.ATOMIC)
        assert len(atomics) == 1
        assert atomics[0].fqn == "term.scm.diameter"

    def test_inheritance_crud(self, fresh_db):
        store = DomainLayerStore()
        store.upsert_terms(repo_id="r1", terms=_sample_terms())
        edges = [
            Inheritance(child_fqn="term.scm.rush_order", parent_fqn="term.scm.order",
                kind=InheritanceKind.EXTENDS),
        ]
        n = store.upsert_inheritance(repo_id="r1", edges=edges)
        assert n == 1
        # idempotent
        n2 = store.upsert_inheritance(repo_id="r1", edges=edges)
        assert n2 == 0

        parents = store.get_inheritance_parents("term.scm.rush_order")
        assert len(parents) == 1
        assert parents[0].parent_fqn == "term.scm.order"

    def test_composition_crud_and_role_replace(self, fresh_db):
        store = DomainLayerStore()
        store.upsert_terms(repo_id="r1", terms=_sample_terms())
        # 처음
        store.upsert_composition(repo_id="r1", edges=[
            Composition(parent_fqn="term.scm.order", child_fqn="term.scm.order_spec",
                role_name="spec", cardinality=Cardinality.ONE),
        ])
        children = store.get_composition_children("term.scm.order")
        assert len(children) == 1

        # 같은 role 로 다른 child → replace
        store.upsert_composition(repo_id="r1", edges=[
            Composition(parent_fqn="term.scm.order", child_fqn="term.scm.diameter",
                role_name="spec", cardinality=Cardinality.ONE),
        ])
        children2 = store.get_composition_children("term.scm.order")
        assert len(children2) == 1
        assert children2[0].child_fqn == "term.scm.diameter"

    def test_rule_crud(self, fresh_db):
        store = DomainLayerStore()
        rule = BusinessRule(fqn="rule.scm.c_range",
            statement="0.10 <= C <= 0.25", severity=RuleSeverity.HARD,
            terms_ref=["term.scm.c_pct"])
        store.upsert_rules(repo_id="r1", rules=[rule])
        all_rules = store.list_rules(repo_id="r1")
        assert len(all_rules) == 1
        assert all_rules[0].terms_ref == ["term.scm.c_pct"]

    def test_repo_isolation(self, fresh_db):
        store = DomainLayerStore()
        store.upsert_terms(repo_id="r1", terms=_sample_terms())
        store.upsert_terms(repo_id="r2", terms=[
            BusinessTerm(fqn="term.other.foo", label="Foo", kind=TermKind.COMPOSITE),
        ])
        assert len(store.list_terms(repo_id="r1")) == 3
        assert len(store.list_terms(repo_id="r2")) == 1

    def test_delete_repo(self, fresh_db):
        store = DomainLayerStore()
        store.upsert_terms(repo_id="r1", terms=_sample_terms())
        store.upsert_inheritance(repo_id="r1", edges=[
            Inheritance(child_fqn="term.scm.rush_order", parent_fqn="term.scm.order",
                kind=InheritanceKind.EXTENDS),
        ])
        n = store.delete_repo("r1")
        assert n >= 4  # 3 terms + 1 inh
        assert len(store.list_terms(repo_id="r1")) == 0
