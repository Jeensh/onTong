"""C2-2 store CRUD tests (SQLite)."""
from __future__ import annotations

import os
import tempfile

import pytest

from backend.modeling.code_layer import (
    CallAnalysisSource,
    CallCandidate,
    CallSite,
    CodeField,
    CodeMethod,
    CodeType,
    CodeTypeKind,
    CodeTypeRole,
    MethodRole,
)
from backend.modeling.code_layer.store import CodeLayerStore


@pytest.fixture
def fresh_db(monkeypatch):
    """매 테스트마다 임시 SQLite DB."""
    from backend.modeling.code_layer.orm import CodeTypeRow  # noqa: F401 — register
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


def _sample_types() -> list[CodeType]:
    order = CodeType(
        fqn="com.scm.Order",
        simple_name="Order",
        package="com.scm",
        kind=CodeTypeKind.ABSTRACT_CLASS,
        role=CodeTypeRole.DOMAIN,
        is_abstract=True,
        methods=[
            CodeMethod(
                fqn="com.scm.Order.validate",
                name="validate",
                parent_type_fqn="com.scm.Order",
                return_type="ValidationResult",
                is_abstract=True,
                role=MethodRole.BUSINESS,
            ),
        ],
    )
    rush = CodeType(
        fqn="com.scm.RushOrder",
        simple_name="RushOrder",
        package="com.scm",
        kind=CodeTypeKind.CLASS,
        role=CodeTypeRole.DOMAIN,
        extends="com.scm.Order",
        fields=[CodeField(name="priorityLevel", type="int")],
        methods=[
            CodeMethod(
                fqn="com.scm.RushOrder.validate",
                name="validate",
                parent_type_fqn="com.scm.RushOrder",
                return_type="ValidationResult",
                is_override=True,
                role=MethodRole.BUSINESS,
            ),
        ],
    )
    return [order, rush]


class TestCodeLayerStore:
    def test_upsert_and_list(self, fresh_db):
        store = CodeLayerStore()
        n = store.upsert_types(repo_id="r1", code_types=_sample_types())
        assert n == 2

        all_types = store.list_types(repo_id="r1")
        assert len(all_types) == 2

        rush = next(t for t in all_types if t.simple_name == "RushOrder")
        assert rush.extends == "com.scm.Order"
        assert len(rush.fields) == 1
        assert rush.fields[0].name == "priorityLevel"

    def test_get_method(self, fresh_db):
        store = CodeLayerStore()
        store.upsert_types(repo_id="r1", code_types=_sample_types())
        m = store.get_method("com.scm.RushOrder.validate")
        assert m is not None
        assert m.is_override is True
        assert m.role == MethodRole.BUSINESS

    def test_filter_by_role(self, fresh_db):
        store = CodeLayerStore()
        store.upsert_types(repo_id="r1", code_types=_sample_types())
        domains = store.list_types(repo_id="r1", role=CodeTypeRole.DOMAIN)
        assert len(domains) == 2
        infras = store.list_types(repo_id="r1", role=CodeTypeRole.INFRA)
        assert len(infras) == 0

    def test_idempotent_upsert(self, fresh_db):
        store = CodeLayerStore()
        store.upsert_types(repo_id="r1", code_types=_sample_types())
        store.upsert_types(repo_id="r1", code_types=_sample_types())
        assert len(store.list_types(repo_id="r1")) == 2

    def test_repo_isolation(self, fresh_db):
        store = CodeLayerStore()
        store.upsert_types(repo_id="r1", code_types=_sample_types())
        store.upsert_types(repo_id="r2", code_types=[_sample_types()[0].model_copy(
            update={"fqn": "com.other.Foo", "simple_name": "Foo",
                    "methods": []})])
        assert len(store.list_types(repo_id="r1")) == 2
        assert len(store.list_types(repo_id="r2")) == 1

    def test_call_sites(self, fresh_db):
        store = CodeLayerStore()
        store.upsert_types(repo_id="r1", code_types=_sample_types())
        cs = CallSite(
            id="c" * 16,
            caller_method_fqn="com.scm.OrderService.process",
            callee_simple_name="validate",
            callee_receiver_static_type="Order",
            line=42,
            possible_runtime_types=[
                CallCandidate(code_type_fqn="com.scm.RushOrder", score=0.5, reason="후보"),
                CallCandidate(code_type_fqn="com.scm.StandardOrder", score=0.5, reason="후보"),
            ],
            confidence=0.0,
            analysis_source=CallAnalysisSource.STATIC_UNRESOLVED,
            needs_user_confirm=True,
        )
        store.upsert_call_sites(repo_id="r1", call_sites=[cs])
        sites = store.get_call_sites("com.scm.OrderService.process")
        assert len(sites) == 1
        assert sites[0].needs_user_confirm is True

        ambig = store.list_ambiguous_call_sites(repo_id="r1")
        assert len(ambig) == 1
