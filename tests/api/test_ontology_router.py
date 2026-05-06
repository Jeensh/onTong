"""C5 REST router tests — FastAPI TestClient."""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import ontology_router
from backend.modeling.api.ontology_query import OntologyQueryClientImpl
from backend.modeling.code_layer import CodeMethod, CodeType, CodeTypeKind, CodeTypeRole, MethodRole
from backend.modeling.code_layer.store import CodeLayerStore
from backend.modeling.domain_layer import (
    BusinessTerm, Composition, Inheritance, InheritanceKind, TermKind, ValueType,
)
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.mapping_layer import (
    Action, ActionKind, ActionParam, DispatchSource, Realization,
    RealizationScope, TypeRealization,
)
from backend.modeling.mapping_layer.schema import ActionOutput
from backend.modeling.mapping_layer.store import MappingLayerStore


@pytest.fixture
def app_with_data(monkeypatch):
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

    # Seed
    cs = CodeLayerStore()
    cs.upsert_types("scm", [
        CodeType(fqn="com.scm.RushOrder", simple_name="RushOrder", package="com.scm",
            kind=CodeTypeKind.CLASS, role=CodeTypeRole.DOMAIN,
            methods=[CodeMethod(fqn="com.scm.RushOrder.validate", name="validate",
                parent_type_fqn="com.scm.RushOrder", role=MethodRole.BUSINESS)]),
    ])
    ds = DomainLayerStore()
    ds.upsert_terms("scm", [
        BusinessTerm(fqn="t.order", label="주문", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.spec", label="스펙", kind=TermKind.COMPOSITE),
        BusinessTerm(fqn="t.diameter", label="직경",
            kind=TermKind.ATOMIC, value_type=ValueType.FLOAT),
    ])
    ds.upsert_composition("scm", [
        Composition(parent_fqn="t.order", child_fqn="t.spec", role_name="spec"),
        Composition(parent_fqn="t.spec", child_fqn="t.diameter", role_name="diameter"),
    ])
    ms = MappingLayerStore()
    ms.upsert_action("scm", Action(
        fqn="action.scm.order_validate", label="주문 검증",
        kind=ActionKind.PURE_FUNCTION, declared_on_term="t.order",
        params=[ActionParam(name="주문", type="object_ref",
            object_ref_term="t.order", confirmed=True)],
        realizations=[
            Realization(code_method_fqn="com.scm.RushOrder.validate",
                dispatch_source=DispatchSource.SINGLE_IMPL,
                scope=RealizationScope.PRIMARY, confirmed=True),
        ],
    ))

    # FastAPI app
    app = FastAPI()
    ontology_router.init(OntologyQueryClientImpl())
    app.include_router(ontology_router.router)
    yield TestClient(app)

    reset_engine_for_tests()
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class TestOntologyRouter:
    def test_get_term(self, app_with_data):
        r = app_with_data.get("/api/ontology/terms/t.order")
        assert r.status_code == 200
        assert r.json()["label"] == "주문"

    def test_list_terms_filter(self, app_with_data):
        r = app_with_data.get("/api/ontology/terms?repo_id=scm&kind=atomic")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["fqn"] == "t.diameter"

    def test_effective_parts(self, app_with_data):
        r = app_with_data.get("/api/ontology/terms/t.order/effective-parts")
        assert r.status_code == 200
        roles = {c["role_name"] for c in r.json()}
        assert "spec" in roles

    def test_get_action(self, app_with_data):
        r = app_with_data.get("/api/ontology/actions/action.scm.order_validate")
        assert r.status_code == 200
        body = r.json()
        assert body["label"] == "주문 검증"
        assert len(body["realizations"]) == 1

    def test_resolve_path(self, app_with_data):
        r = app_with_data.get(
            "/api/ontology/actions/action.scm.order_validate/resolve-path"
            "?slot_path=params[0].spec.diameter&repo_id=scm"
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["last_term_fqn"] == "t.diameter"

    def test_resolve_path_bad(self, app_with_data):
        r = app_with_data.get(
            "/api/ontology/actions/action.scm.order_validate/resolve-path"
            "?slot_path=params[0].unknown&repo_id=scm"
        )
        body = r.json()
        assert body["ok"] is False

    def test_search(self, app_with_data):
        r = app_with_data.get("/api/ontology/search?q=주문&repo_id=scm")
        assert r.status_code == 200
        hits = r.json()
        assert len(hits) >= 1
        kinds = {h["kind"] for h in hits}
        assert "term" in kinds

    def test_dispatch(self, app_with_data):
        r = app_with_data.get(
            "/api/ontology/actions/action.scm.order_validate/realizations-for-input"
            "?code_type_fqn=com.scm.RushOrder"
        )
        # 정확 매칭 없으면 base 반환 (이 테스트 fixture 는 applies_to=None 인 realization 만 있음)
        assert r.status_code == 200

    def test_verification_progress(self, app_with_data):
        r = app_with_data.get("/api/ontology/queue/verification-progress/scm")
        assert r.status_code == 200
        assert r.json()["total_actions"] == 1

    def test_unmapped_methods(self, app_with_data):
        r = app_with_data.get("/api/ontology/queue/unmapped-methods?repo_id=scm")
        assert r.status_code == 200
