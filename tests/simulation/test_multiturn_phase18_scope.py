"""Phase 18 — Stage 2 scope aggregator + endpoint.

사용자 vision Stage 2 (영향 영역). 단일 호출로 caller + sibling action + term +
rule 집계. Test/Mock 자동 제외 (W4 동기화).
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.persistence import database as db_mod
from backend.section3.agents.multiturn.intent import StubIntentClassifier
from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
from backend.section3.agents.multiturn.schemas import AffectedMethod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase18.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    db_mod.reset_engine_for_tests()

    from backend.modeling.code_layer import orm as _code_orm  # noqa: F401
    from backend.modeling.domain_layer import orm as _domain_orm  # noqa: F401
    from backend.modeling.mapping_layer import orm as _mapping_orm  # noqa: F401
    from backend.modeling.view_layer import orm as _view_orm  # noqa: F401
    from backend.application.authoring import orm as _authoring_orm  # noqa: F401
    from backend.section3.agents.multiturn import orm as _multiturn_orm  # noqa: F401

    db_mod.bootstrap_database()
    yield db_path
    db_mod.reset_engine_for_tests()


def _seed_term(*, fqn: str, label: str, repo_id: str = "r"):
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow
    with session_scope() as s:
        s.add(BusinessTermRow(
            fqn=fqn, label=label, aliases_json="[]",
            kind="atomic", domain="scm", description="",
            confirmed=True, repo_id=repo_id, source="user",
        ))


def _seed_action(*, fqn: str, label: str, declared_on_term: str | None, repo_id: str = "r"):
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.mapping_layer.orm import ActionRow
    with session_scope() as s:
        s.add(ActionRow(
            fqn=fqn, label=label, aliases_json="[]",
            domain="scm", kind="atomic",
            declared_on_term=declared_on_term, repo_id=repo_id,
        ))


def _seed_rule(*, fqn: str, statement: str, terms_ref_json: str, severity: str = "HARD", repo_id: str = "r"):
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessRuleRow
    with session_scope() as s:
        s.add(BusinessRuleRow(
            fqn=fqn, statement=statement, severity=severity,
            terms_ref_json=terms_ref_json,
            source="manual", confirmed=True, repo_id=repo_id,
        ))


@pytest.fixture
def fake_ontology():
    class _FakeOntology(MockOntologyClient):
        async def get_caller_graph(self, method_fqn, *, repo_id):
            return [
                AffectedMethod(
                    fqn="com.x.SdController.process",
                    distance=1, via="caller",
                    match_kind="receiver_exact", strength=1.0,
                ),
                AffectedMethod(
                    fqn="com.x.SdControllerTest.testProcess",
                    distance=1, via="caller",
                    match_kind="name_only", strength=0.3,
                ),
            ]
    return _FakeOntology(catalog={})


# ─────────────────────────────────────────────────────────────────────────────
# build_scope direct (single primary, no siblings, no rules)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scope_primary_with_callers(fresh_db, fake_ontology) -> None:
    from backend.section3.agents.multiturn.scope import build_scope

    sc = await build_scope(
        action_fqn="action.scm.thickness_실행",
        code_method_fqn="com.x.SdThicknessAction.execute",
        declared_on_term=None,
        repo_id="r",
        ontology_client=fake_ontology,
    )
    kinds = [e.kind for e in sc.entities]
    assert "action" in kinds  # primary
    assert "caller" in kinds  # 2 callers
    # primary action 1 + 2 callers = 3
    assert sc.counts.get("action", 0) == 1
    assert sc.counts.get("caller", 0) == 2


@pytest.mark.asyncio
async def test_test_caller_marked_excluded_by_default(fresh_db, fake_ontology) -> None:
    """Test 패턴 caller 는 in_scope_default=False (W4 동기화)."""
    from backend.section3.agents.multiturn.scope import build_scope

    sc = await build_scope(
        action_fqn="action.x",
        code_method_fqn="com.x.Sd.method",
        declared_on_term=None,
        repo_id="r",
        ontology_client=fake_ontology,
    )
    test_callers = [
        e for e in sc.entities
        if e.kind == "caller" and "Test" in e.fqn
    ]
    assert len(test_callers) == 1
    assert test_callers[0].in_scope_default is False
    assert test_callers[0].meta.get("test_suspect") is True


@pytest.mark.asyncio
async def test_scope_with_term_and_siblings(fresh_db, fake_ontology) -> None:
    """declared_on_term 주면 sibling actions + term entity 포함."""
    from backend.section3.agents.multiturn.scope import build_scope

    _seed_term(fqn="term.scm.thickness", label="두께")
    _seed_action(
        fqn="action.scm.thickness_실행", label="thickness_실행",
        declared_on_term="term.scm.thickness",
    )
    _seed_action(
        fqn="action.scm.thickness_validate", label="thickness_validate",
        declared_on_term="term.scm.thickness",
    )

    sc = await build_scope(
        action_fqn="action.scm.thickness_실행",
        code_method_fqn="com.x.SdThicknessAction.execute",
        declared_on_term="term.scm.thickness",
        repo_id="r",
        ontology_client=fake_ontology,
    )
    # primary + 1 sibling + 1 term + 2 callers
    assert sc.counts.get("action", 0) == 2  # primary + 1 sibling
    assert sc.counts.get("term", 0) == 1
    assert sc.counts.get("caller", 0) == 2
    sibling = [e for e in sc.entities if e.meta.get("sibling")]
    assert len(sibling) == 1
    assert sibling[0].fqn == "action.scm.thickness_validate"


@pytest.mark.asyncio
async def test_scope_with_business_rules(fresh_db, fake_ontology) -> None:
    from backend.section3.agents.multiturn.scope import build_scope

    _seed_term(fqn="term.scm.thickness", label="두께")
    _seed_rule(
        fqn="rule.dg108", statement="thickness < 0.1 → throw",
        terms_ref_json='["term.scm.thickness"]',
        severity="HARD",
    )

    sc = await build_scope(
        action_fqn="action.x", code_method_fqn="com.x.M.exec",
        declared_on_term="term.scm.thickness",
        repo_id="r", ontology_client=fake_ontology,
    )
    rules = [e for e in sc.entities if e.kind == "rule"]
    assert len(rules) == 1
    assert "0.1" in rules[0].detail
    assert rules[0].meta.get("severity") == "HARD"


# ─────────────────────────────────────────────────────────────────────────────
# POST /scope endpoint
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def client(fresh_db, fake_ontology):
    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(forced_intent="ambiguous")
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: fake_ontology
    return TestClient(app)


def test_scope_endpoint_returns_entities(client, fresh_db) -> None:
    r = client.post(
        "/api/section3/multiturn/scope",
        json={
            "action_fqn": "action.x",
            "code_method_fqn": "com.x.M.exec",
            "declared_on_term": None,
            "repo_id": "r",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["primary_action_fqn"] == "action.x"
    assert body["counts"]["caller"] == 2
    # action entity (primary) 포함
    kinds = [e["kind"] for e in body["entities"]]
    assert "action" in kinds


def test_scope_endpoint_with_term(client, fresh_db) -> None:
    _seed_term(fqn="term.scm.thickness", label="두께")
    _seed_action(
        fqn="action.scm.thickness_sibling", label="sibling",
        declared_on_term="term.scm.thickness",
    )

    r = client.post(
        "/api/section3/multiturn/scope",
        json={
            "action_fqn": "action.scm.thickness_main",
            "code_method_fqn": "com.x.M.exec",
            "declared_on_term": "term.scm.thickness",
            "repo_id": "r",
        },
    )
    assert r.status_code == 200
    body = r.json()
    # term entity 포함
    term_ents = [e for e in body["entities"] if e["kind"] == "term"]
    assert len(term_ents) == 1
    assert term_ents[0]["label"] == "두께"
