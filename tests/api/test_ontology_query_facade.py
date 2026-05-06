"""C5 Facade tests — OntologyQueryClientImpl 통합."""
from __future__ import annotations

import os
import tempfile

import pytest

from backend.modeling.api.ontology_query import OntologyQueryClientImpl
from backend.modeling.code_layer import (
    CodeMethod, CodeType, CodeTypeKind, CodeTypeRole, MethodRole,
)
from backend.modeling.code_layer.store import CodeLayerStore
from backend.modeling.domain_layer import (
    BusinessTerm, Cardinality, Composition, Inheritance, InheritanceKind,
    TermKind, ValueType,
)
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.mapping_layer import (
    Action, ActionKind, ActionParam, AnchorBinding, DispatchSource,
    Realization, RealizationScope, TypeRealization, VerificationLevel,
)
from backend.modeling.mapping_layer.schema import ActionOutput
from backend.modeling.mapping_layer.store import MappingLayerStore


@pytest.fixture
def fresh_db(monkeypatch):
    from backend.modeling.code_layer.orm import CodeTypeRow  # noqa: F401
    from backend.modeling.domain_layer.orm import BusinessTermRow  # noqa: F401
    from backend.modeling.mapping_layer.orm import ActionRow  # noqa: F401
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


def _seed(repo_id: str = "scm"):
    code_store = CodeLayerStore()
    domain_store = DomainLayerStore()
    map_store = MappingLayerStore()

    code_store.upsert_types(repo_id, [
        CodeType(fqn="com.scm.Order", simple_name="Order", package="com.scm",
            kind=CodeTypeKind.ABSTRACT_CLASS, role=CodeTypeRole.DOMAIN, is_abstract=True,
            methods=[CodeMethod(fqn="com.scm.Order.validate", name="validate",
                parent_type_fqn="com.scm.Order", is_abstract=True, role=MethodRole.BUSINESS)]),
        CodeType(fqn="com.scm.RushOrder", simple_name="RushOrder", package="com.scm",
            kind=CodeTypeKind.CLASS, role=CodeTypeRole.DOMAIN, extends="com.scm.Order",
            methods=[CodeMethod(fqn="com.scm.RushOrder.validate", name="validate",
                parent_type_fqn="com.scm.RushOrder", is_override=True, role=MethodRole.BUSINESS)]),
        # unmapped business method
        CodeType(fqn="com.scm.PriceCalculator", simple_name="PriceCalculator",
            package="com.scm", kind=CodeTypeKind.CLASS, role=CodeTypeRole.DOMAIN,
            methods=[CodeMethod(fqn="com.scm.PriceCalculator.compute", name="compute",
                parent_type_fqn="com.scm.PriceCalculator", role=MethodRole.BUSINESS)]),
    ])
    domain_store.upsert_terms(repo_id, [
        BusinessTerm(fqn="t.order", label="주문", kind=TermKind.COMPOSITE,
            is_abstract=True, is_root_entity=True),
        BusinessTerm(fqn="t.rush_order", label="긴급주문", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.spec", label="주문스펙", kind=TermKind.COMPOSITE,
            struct_like_hint=True),
        BusinessTerm(fqn="t.diameter", label="직경",
            kind=TermKind.ATOMIC, value_type=ValueType.FLOAT, range=[0, 300]),
    ])
    domain_store.upsert_inheritance(repo_id, [
        Inheritance(child_fqn="t.rush_order", parent_fqn="t.order",
            kind=InheritanceKind.EXTENDS),
    ])
    domain_store.upsert_composition(repo_id, [
        Composition(parent_fqn="t.order", child_fqn="t.spec", role_name="spec"),
        Composition(parent_fqn="t.spec", child_fqn="t.diameter", role_name="diameter"),
    ])
    map_store.upsert_type_realizations(repo_id, [
        TypeRealization(code_type_fqn="com.scm.RushOrder", term_fqn="t.rush_order",
            source="name_match", confirmed=True),
    ])
    map_store.upsert_action(repo_id, Action(
        fqn="action.scm.order_validate", label="주문 검증",
        kind=ActionKind.PURE_FUNCTION, is_abstract=True, declared_on_term="t.order",
        params=[ActionParam(name="주문", type="object_ref",
            object_ref_term="t.order", confirmed=True)],
        output=ActionOutput(type="object_ref", object_ref_term="t.result"),
        realizations=[
            Realization(code_method_fqn="com.scm.RushOrder.validate",
                applies_to_code_type_fqn="com.scm.RushOrder", is_override=True,
                dispatch_source=DispatchSource.SINGLE_IMPL,
                scope=RealizationScope.PRIMARY, confirmed=True),
        ],
    ))
    map_store.upsert_anchor_bindings(repo_id, [
        AnchorBinding(id="b" * 16, anchor_locator="literal:200.0",
            code_method_fqn="com.scm.RushOrder.validate",
            target_action_fqn="action.scm.order_validate",
            target_slot="params[0].spec.diameter.range[1]",
            confidence=1.0, source="literal_match", confirmed=True),
    ])


class TestFacadeBasics:
    def test_get_term(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        t = q.get_term("t.order")
        assert t is not None and t.label == "주문"

    def test_list_terms_filter(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        composites = q.list_terms(repo_id="scm", kind="composite")
        atomics = q.list_terms(repo_id="scm", kind="atomic")
        assert len(composites) == 3
        assert len(atomics) == 1

    def test_effective_parts(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        eff = q.effective_parts("t.rush_order", repo_id="scm")
        roles = {c.role_name for c in eff}
        assert "spec" in roles  # inherited from 주문

    def test_resolve_path_ok(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        ok, last, err = q.resolve_path("action.scm.order_validate",
            "params[0].spec.diameter", repo_id="scm")
        assert ok
        assert last == "t.diameter"

    def test_resolve_path_bad(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        ok, last, err = q.resolve_path("action.scm.order_validate",
            "params[0].nonexistent", repo_id="scm")
        assert not ok
        assert "not found" in err

    def test_resolve_path_unknown_action(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        ok, last, err = q.resolve_path("action.unknown", "params[0]")
        assert not ok
        assert "unknown action" in err


class TestActionAndDispatch:
    def test_get_action_with_realizations(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        a = q.get_action("action.scm.order_validate")
        assert a is not None
        assert len(a.realizations) == 1
        assert a.realizations[0].applies_to_code_type_fqn == "com.scm.RushOrder"

    def test_dispatch_for_input(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        # RushOrder 입력 → 정확 매칭
        reals = q.get_realizations_for_input_type(
            "action.scm.order_validate", "com.scm.RushOrder")
        assert len(reals) == 1
        assert reals[0].code_method_fqn == "com.scm.RushOrder.validate"

    def test_list_actions_by_kind(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        purefns = q.list_actions(repo_id="scm", kind="pure_function")
        assert len(purefns) == 1


class TestMappingQueue:
    def test_unmapped_methods(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        ums = q.list_unmapped_methods(repo_id="scm")
        # PriceCalculator.compute (no realization) + Order.validate (Action 의 base, but realization 0 for it)
        fqns = {u.code_method.fqn for u in ums}
        assert "com.scm.PriceCalculator.compute" in fqns

    def test_verification_progress(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        prog = q.get_verification_progress("scm")
        assert prog.total_actions == 1


class TestSearch:
    def test_search_korean_label(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        hits = q.search("주문", repo_id="scm", limit=10)
        # 적어도 t.order, action.scm.order_validate 포함
        kinds = {h.kind for h in hits}
        assert "term" in kinds
        assert "action" in kinds

    def test_search_code_type(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        hits = q.search("RushOrder", repo_id="scm", limit=10)
        assert any(h.kind == "code_type" and h.label == "RushOrder" for h in hits)

    def test_search_empty_query(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        assert q.search("", repo_id="scm") == []

    def test_search_score_descending(self, fresh_db):
        _seed()
        q = OntologyQueryClientImpl()
        hits = q.search("주문", repo_id="scm", limit=10)
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)
