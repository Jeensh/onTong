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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 협업 — sec3 multiturn 용 3 endpoint (method body / entity schema / callers)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def app_with_callsites(monkeypatch):
    """method body + callsite + entity schema 시연용 fixture."""
    from backend.modeling.code_layer.orm import CodeTypeRow  # noqa: F401
    from backend.modeling.code_layer.schema import (
        CallAnalysisSource, CallCandidate, CallSite, CodeField,
    )
    from backend.modeling.persistence.database import (
        Base, get_engine, reset_engine_for_tests,
    )
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("ONTONG_DB_PATH", path)
    reset_engine_for_tests()
    Base.metadata.create_all(bind=get_engine())

    cs = CodeLayerStore()
    cs.upsert_types("scm", [
        CodeType(
            fqn="com.scm.Order", simple_name="Order", package="com.scm",
            kind=CodeTypeKind.CLASS, role=CodeTypeRole.DOMAIN,
            fields=[
                CodeField(name="id", type="String"),
                CodeField(name="quantity", type="int"),
                CodeField(name="items", type="List<Item>", is_collection=True,
                          element_type="Item"),
            ],
            methods=[
                CodeMethod(
                    fqn="com.scm.Order.validate", name="validate",
                    parent_type_fqn="com.scm.Order", role=MethodRole.BUSINESS,
                    body_text="public boolean validate() { return id != null; }",
                    return_type="boolean",
                    line_start=10, line_end=12,
                ),
            ],
        ),
        CodeType(
            fqn="com.scm.OrderService", simple_name="OrderService",
            package="com.scm", kind=CodeTypeKind.CLASS,
            role=CodeTypeRole.UNKNOWN,
            methods=[
                CodeMethod(
                    fqn="com.scm.OrderService.process", name="process",
                    parent_type_fqn="com.scm.OrderService",
                    role=MethodRole.BUSINESS,
                ),
            ],
        ),
    ])
    cs.upsert_call_sites("scm", [
        CallSite(
            id="cs1",
            caller_method_fqn="com.scm.OrderService.process",
            callee_simple_name="validate",
            callee_receiver_static_type="com.scm.Order",
            line=42,
            possible_runtime_types=[
                CallCandidate(code_type_fqn="com.scm.Order", score=1.0,
                              reason="단일 impl"),
            ],
            confidence=1.0,
            analysis_source=CallAnalysisSource.SINGLE_IMPL,
        ),
    ])

    app = FastAPI()
    ontology_router.init(OntologyQueryClientImpl())
    app.include_router(ontology_router.router)
    yield TestClient(app)

    reset_engine_for_tests()
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class TestPhase4CollaborationEndpoints:
    def test_method_body_returns_body_text(self, app_with_callsites):
        r = app_with_callsites.get(
            "/api/ontology/code-methods/com.scm.Order.validate/body",
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["fqn"] == "com.scm.Order.validate"
        assert "validate" in body["body_text"]
        assert body["return_type"] == "boolean"
        assert body["line_start"] == 10

    def test_method_body_unknown_returns_404(self, app_with_callsites):
        r = app_with_callsites.get(
            "/api/ontology/code-methods/com.x.Missing.foo/body",
        )
        assert r.status_code == 404

    def test_method_callers_returns_caller_list(self, app_with_callsites):
        r = app_with_callsites.get(
            "/api/ontology/code-methods/com.scm.Order.validate/callers",
        )
        assert r.status_code == 200
        body = r.json()
        fqns = [c["fqn"] for c in body["callers"]]
        assert "com.scm.OrderService.process" in fqns
        assert body["callers"][0]["distance"] == 1

    def test_method_callers_no_match_returns_empty_list(self, app_with_callsites):
        r = app_with_callsites.get(
            "/api/ontology/code-methods/com.x.Nothing.never/callers",
        )
        assert r.status_code == 200
        assert r.json()["callers"] == []

    def test_method_callers_surface_match_kind_and_strength(
        self, app_with_callsites,
    ):
        """Phase 10 — caller 마다 match_kind + strength 노출."""
        r = app_with_callsites.get(
            "/api/ontology/code-methods/com.scm.Order.validate/callers",
        )
        assert r.status_code == 200
        for c in r.json()["callers"]:
            assert "match_kind" in c
            assert c["match_kind"] in {
                "receiver_exact", "receiver_short", "runtime_type",
                "package_proximity", "name_only",
            }
            assert 0.0 < c["strength"] <= 1.0
        # 본 fixture 에서는 receiver 가 fqn 일치 → receiver_exact
        kinds = {c["match_kind"] for c in r.json()["callers"]}
        assert "receiver_exact" in kinds

    def test_method_callers_min_strength_filter(self, app_with_callsites):
        """Phase 10 — min_strength 가 약한 매치를 제거."""
        # receiver_exact (0.95) 만 필터링
        r = app_with_callsites.get(
            "/api/ontology/code-methods/com.scm.Order.validate/callers"
            "?min_strength=0.9",
        )
        assert r.status_code == 200
        assert all(c["strength"] >= 0.9 for c in r.json()["callers"])
        # 너무 높이면 빈 결과
        r2 = app_with_callsites.get(
            "/api/ontology/code-methods/com.scm.Order.validate/callers"
            "?min_strength=0.99",
        )
        assert r2.status_code == 200
        assert r2.json()["callers"] == []

    def test_entity_schema_returns_fields(self, app_with_callsites):
        r = app_with_callsites.get("/api/ontology/entities/Order/schema")
        assert r.status_code == 200
        body = r.json()
        assert body["entity_name"] == "Order"
        field_names = {f["name"] for f in body["fields"]}
        assert "id" in field_names
        assert "quantity" in field_names

    def test_entity_schema_unknown_returns_404(self, app_with_callsites):
        r = app_with_callsites.get(
            "/api/ontology/entities/UnknownEntity/schema",
        )
        assert r.status_code == 404

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
