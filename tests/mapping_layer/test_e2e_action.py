"""C4 e2e — Order 도메인 위에 주문_검증 Action + 2 Realization + AnchorBinding composite path."""
from __future__ import annotations

import os
import tempfile

import pytest

from backend.modeling.code_layer import CodeType, CodeTypeKind, CodeTypeRole, CodeMethod, MethodRole
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
from backend.modeling.mapping_layer.path import parse_path, validate_path
from backend.modeling.mapping_layer.schema import ActionOutput
from backend.modeling.mapping_layer.store import MappingLayerStore
from backend.modeling.mapping_layer.verification import (
    can_simulate, compute_verification_level,
)


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


def _seed_code(code_store: CodeLayerStore):
    types = [
        CodeType(fqn="com.scm.Order", simple_name="Order", package="com.scm",
            kind=CodeTypeKind.ABSTRACT_CLASS, role=CodeTypeRole.DOMAIN, is_abstract=True,
            methods=[CodeMethod(fqn="com.scm.Order.validate", name="validate",
                parent_type_fqn="com.scm.Order", return_type="ValidationResult",
                is_abstract=True, role=MethodRole.BUSINESS)]),
        CodeType(fqn="com.scm.RushOrder", simple_name="RushOrder", package="com.scm",
            kind=CodeTypeKind.CLASS, role=CodeTypeRole.DOMAIN, extends="com.scm.Order",
            methods=[CodeMethod(fqn="com.scm.RushOrder.validate", name="validate",
                parent_type_fqn="com.scm.RushOrder", return_type="ValidationResult",
                is_override=True, role=MethodRole.BUSINESS)]),
        CodeType(fqn="com.scm.StandardOrder", simple_name="StandardOrder", package="com.scm",
            kind=CodeTypeKind.CLASS, role=CodeTypeRole.DOMAIN, extends="com.scm.Order",
            methods=[CodeMethod(fqn="com.scm.StandardOrder.validate", name="validate",
                parent_type_fqn="com.scm.StandardOrder", return_type="ValidationResult",
                is_override=True, role=MethodRole.BUSINESS)]),
    ]
    code_store.upsert_types("scm", types)


def _seed_domain(dom_store: DomainLayerStore):
    terms = [
        BusinessTerm(fqn="t.order", label="주문", kind=TermKind.COMPOSITE,
            is_abstract=True, is_root_entity=True),
        BusinessTerm(fqn="t.rush_order", label="긴급주문", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.standard_order", label="표준주문", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.spec", label="주문스펙", kind=TermKind.COMPOSITE,
            struct_like_hint=True),
        BusinessTerm(fqn="t.diameter", label="직경", kind=TermKind.ATOMIC,
            value_type=ValueType.FLOAT, unit="mm", range=[0.0, 300.0]),
        BusinessTerm(fqn="t.priority", label="우선도", kind=TermKind.ATOMIC,
            value_type=ValueType.INT, range=[1, 5]),
        BusinessTerm(fqn="t.validation_result", label="검증결과", kind=TermKind.COMPOSITE),
    ]
    inh = [
        Inheritance(child_fqn="t.rush_order", parent_fqn="t.order",
            kind=InheritanceKind.EXTENDS),
        Inheritance(child_fqn="t.standard_order", parent_fqn="t.order",
            kind=InheritanceKind.EXTENDS),
    ]
    comp = [
        Composition(parent_fqn="t.order", child_fqn="t.spec", role_name="spec"),
        Composition(parent_fqn="t.spec", child_fqn="t.diameter", role_name="diameter"),
        Composition(parent_fqn="t.rush_order", child_fqn="t.priority", role_name="priority"),
    ]
    dom_store.upsert_terms("scm", terms)
    dom_store.upsert_inheritance("scm", inh)
    dom_store.upsert_composition("scm", comp)
    return terms, inh, comp


class TestActionPolymorphismE2E:
    def test_full_pipeline(self, fresh_db):
        # 1. Seed Code + Domain
        code_store = CodeLayerStore()
        dom_store = DomainLayerStore()
        _seed_code(code_store)
        terms, inh, comp = _seed_domain(dom_store)

        # 2. TypeRealization (Code ↔ Domain)
        map_store = MappingLayerStore()
        map_store.upsert_type_realizations("scm", [
            TypeRealization(code_type_fqn="com.scm.Order", term_fqn="t.order",
                source="name_match", confirmed=True),
            TypeRealization(code_type_fqn="com.scm.RushOrder", term_fqn="t.rush_order",
                source="name_match", confirmed=True),
            TypeRealization(code_type_fqn="com.scm.StandardOrder",
                term_fqn="t.standard_order", source="name_match", confirmed=True),
        ])
        assert map_store.get_term_for_code_type("com.scm.RushOrder").term_fqn == "t.rush_order"

        # 3. Action 주문_검증 (abstract, declared on Order)
        action = Action(
            fqn="action.scm.order_validate", label="주문 검증",
            kind=ActionKind.PURE_FUNCTION, is_abstract=True,
            declared_on_term="t.order",
            params=[ActionParam(name="주문", type="object_ref",
                object_ref_term="t.order", confirmed=True)],
            output=ActionOutput(type="object_ref", object_ref_term="t.validation_result"),
            realizations=[
                Realization(code_method_fqn="com.scm.RushOrder.validate",
                    applies_to_code_type_fqn="com.scm.RushOrder", is_override=True,
                    dispatch_source=DispatchSource.SINGLE_IMPL,
                    scope=RealizationScope.PRIMARY, confirmed=True),
                Realization(code_method_fqn="com.scm.StandardOrder.validate",
                    applies_to_code_type_fqn="com.scm.StandardOrder", is_override=True,
                    dispatch_source=DispatchSource.SINGLE_IMPL,
                    scope=RealizationScope.PRIMARY, confirmed=True),
            ],
        )
        map_store.upsert_action("scm", action)

        # 4. AnchorBinding — RushOrder 의 priority literal
        ab = AnchorBinding(
            id="b" * 16,
            anchor_locator="literal:1",
            code_method_fqn="com.scm.RushOrder.validate",
            target_action_fqn="action.scm.order_validate",
            target_slot="params[0]<RushOrder>.priority.range[0]",
            confidence=1.0, source="literal_match", confirmed=True,
        )
        map_store.upsert_anchor_bindings("scm", [ab])

        # 5. Path validation — slot 이 Domain 그래프에서 traversal 가능?
        ap = [(p.name, p.object_ref_term) for p in action.params]
        for slot in [
            "params[0]",
            "params[0].spec.diameter",
            "params[0].spec.diameter.range[1]",
            "params[0]<RushOrder>.priority",
            "params[0]<RushOrder>.priority.range[0]",
            "preconditions[0]",
        ]:
            v = validate_path(parse_path(slot),
                action_params=ap, terms=terms, inheritance=inh, composition=comp)
            assert v.ok, f"slot {slot!r} should be valid: {v.error}"

        # 6. VerificationLevel 자동 계산
        got = map_store.get_action("action.scm.order_validate")
        anchors = map_store.get_anchor_bindings_for_action("action.scm.order_validate")
        level = compute_verification_level(got, anchor_bindings=anchors)
        assert level == VerificationLevel.BODY_ANCHORED
        assert can_simulate(level)

        # 7. 다형성 — RushOrder 입력 시 어느 Realization 이 dispatch?
        #    (실제 dispatch 로직은 PythonGenerator/A2 가 담당. 여기서는 Realization 조회만.)
        reals = map_store.list_realizations("action.scm.order_validate")
        rush_real = next(
            r for r in reals if r.applies_to_code_type_fqn == "com.scm.RushOrder"
        )
        assert rush_real.code_method_fqn == "com.scm.RushOrder.validate"
        assert rush_real.is_override is True
