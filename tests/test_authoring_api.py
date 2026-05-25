"""S6 — Authoring API endpoint tests.

Covers session admin, history/preview/cost endpoints, and the confirm flow
end-to-end (with a real DomainLayerStore against a temp SQLite).

Capability endpoints are smoke-tested with monkeypatched capability functions
so we exercise the wiring without paying for live LLM calls. The actual
LLM-shaped behaviour is already covered by the per-capability tests.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import authoring as auth_api
from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities import answer_absorber as aa
from backend.application.authoring.capabilities import archiver as ar
from backend.application.authoring.capabilities import code_extractor as ce
from backend.application.authoring.capabilities import gap_detector as gd
from backend.application.authoring.capabilities import hypothesis as hp
from backend.application.authoring.capabilities import interview as iv
from backend.application.authoring.capabilities import naming as nm
from backend.application.authoring.capabilities import option_proposer as op
from backend.application.authoring import session as sess_mod
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.persistence import database as db_mod


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "authoring_api_test.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    db_mod.reset_engine_for_tests()

    from backend.modeling.code_layer import orm as _code_orm  # noqa: F401
    from backend.modeling.domain_layer import orm as _domain_orm  # noqa: F401
    from backend.modeling.mapping_layer import orm as _mapping_orm  # noqa: F401
    from backend.modeling.view_layer import orm as _view_orm  # noqa: F401
    from backend.application.authoring import orm as _authoring_orm  # noqa: F401

    db_mod.bootstrap_database()
    cost_mod.reset_buffer()
    yield db_path
    db_mod.reset_engine_for_tests()


@pytest.fixture
def client(fresh_db):
    """FastAPI TestClient with the authoring router and a real DomainLayerStore."""
    app = FastAPI()
    auth_api.init(business_term_store=DomainLayerStore())
    app.include_router(auth_api.router)
    return TestClient(app)


# ── Session admin ───────────────────────────────────────────────────


def test_create_then_get_session(client):
    r = client.post(
        "/api/authoring/sessions",
        json={"operator_id": "alice", "branch_name": "feat/hrplant", "repo_id": "slab"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    sid = body["id"]
    assert body["operator_id"] == "alice"
    assert body["status"] == "active"

    r2 = client.get(f"/api/authoring/sessions/{sid}")
    assert r2.status_code == 200
    assert r2.json()["id"] == sid


def test_get_session_404(client):
    r = client.get("/api/authoring/sessions/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_list_sessions_with_filters(client):
    sid_a = client.post(
        "/api/authoring/sessions", json={"operator_id": "alice"}
    ).json()["id"]
    sid_b = client.post(
        "/api/authoring/sessions", json={"operator_id": "bob"}
    ).json()["id"]

    rows = client.get("/api/authoring/sessions").json()
    ids = {s["id"] for s in rows}
    assert {sid_a, sid_b} <= ids

    only_alice = client.get(
        "/api/authoring/sessions", params={"operator_id": "alice"}
    ).json()
    assert {s["id"] for s in only_alice} == {sid_a}


def test_patch_session_focus_and_status(client):
    sid = client.post("/api/authoring/sessions", json={"operator_id": "alice"}).json()["id"]
    r = client.patch(
        f"/api/authoring/sessions/{sid}",
        json={"entity_focus": "HrPlant", "status": "paused"},
    )
    assert r.status_code == 200
    assert r.json()["entity_focus"] == "HrPlant"
    assert r.json()["status"] == "paused"


# ── History / cost / preview ────────────────────────────────────────


def test_decisions_endpoint_empty_then_populated(client):
    sid = client.post("/api/authoring/sessions", json={}).json()["id"]
    assert client.get(f"/api/authoring/sessions/{sid}/decisions").json() == []

    sess_mod.add_decision(
        session_id=sid,
        turn_no=1,
        decision_kind="hypothesis_seeded",
        payload={"english_id": "HrPlant"},
        entity_id="HrPlant",
    )
    rows = client.get(f"/api/authoring/sessions/{sid}/decisions").json()
    assert len(rows) == 1
    assert rows[0]["entity_id"] == "HrPlant"


def test_cost_endpoint_aggregates_session_total(client):
    from backend.application.authoring.schemas import ModelTier, TokenUsage

    sid = client.post("/api/authoring/sessions", json={}).json()["id"]
    cost_mod.log_call(
        session_id=sid,
        turn_no=1,
        capability="hypothesis",
        tier=ModelTier.HARD,
        model_id="anthropic/claude-opus-4-7",
        usage=TokenUsage(input_tokens=1_000_000, output_tokens=0),  # exactly $15
    )
    body = client.get(f"/api/authoring/sessions/{sid}/cost").json()
    assert body["session_id"] == sid
    assert body["call_count"] == 1
    assert body["total_usd"] == pytest.approx(15.0, rel=1e-6)


def test_preview_endpoint_returns_session_decisions_archive_cost(client):
    sid = client.post("/api/authoring/sessions", json={"operator_id": "alice"}).json()["id"]
    sess_mod.add_decision(
        session_id=sid,
        turn_no=1,
        decision_kind="archive_saved",
        payload={"k": 1},
        archive_markdown="# Step 1 archive\n\nSummary",
    )
    sess_mod.add_decision(
        session_id=sid,
        turn_no=2,
        decision_kind="archive_saved",
        payload={"k": 2},
        archive_markdown="# Step 2 archive (latest)\n\nSummary",
    )

    r = client.get(f"/api/authoring/sessions/{sid}/preview")
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["id"] == sid
    assert body["decision_count"] == 2
    assert body["latest_archive_markdown"] == "# Step 2 archive (latest)\n\nSummary"
    assert body["cost"]["session_id"] == sid


# ── Capability endpoints (wiring smoke tests, no LLM) ───────────────


def _stub_async(return_value):
    """Helper: monkeypatch a capability function with an async stub."""

    async def _stub(*args, **kwargs):
        # Mirror cost.log_call so cost endpoint tests still see at least one row.
        return return_value

    return _stub


def test_extract_endpoint_records_decision(client, monkeypatch):
    sid = client.post("/api/authoring/sessions", json={}).json()["id"]
    fake = ce.ExtractedJpo(
        package="p", class_name="HrSpecJpo", table_name="HR_SPEC", pk_class="HrSpecPK"
    )
    monkeypatch.setattr(auth_api, "extract_jpo_from_file", _stub_async(fake))

    r = client.post(
        f"/api/authoring/sessions/{sid}/extract",
        json={"turn_no": 1, "file_path": "HrSpecJpo.java", "file_content": "..."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["class_name"] == "HrSpecJpo"

    decs = client.get(f"/api/authoring/sessions/{sid}/decisions").json()
    assert len(decs) == 1
    assert decs[0]["entity_id"] == "HrSpecJpo"
    assert decs[0]["payload"]["capability"] == "code_extractor"


def test_hypothesize_endpoint_records_decision(client, monkeypatch):
    sid = client.post("/api/authoring/sessions", json={}).json()["id"]
    fake = hp.EntityHypothesis(
        candidate_term_korean="열연공장",
        candidate_term_english="HrPlant",
        domain_role="standard",
        pk_role_summary="온톨로지·소·열연공장·품종",
        confidence=0.7,
    )
    monkeypatch.setattr(auth_api, "propose_entity_hypothesis", _stub_async(fake))

    extracted = ce.ExtractedJpo(
        package="p", class_name="HrSpecJpo", table_name="HR_SPEC", pk_class="HrSpecPK"
    )
    r = client.post(
        f"/api/authoring/sessions/{sid}/hypothesize",
        json={"turn_no": 2, "extracted_jpo": extracted.model_dump()},
    )
    assert r.status_code == 200
    assert r.json()["candidate_term_english"] == "HrPlant"

    decs = client.get(f"/api/authoring/sessions/{sid}/decisions").json()
    assert decs[-1]["decision_kind"] == "hypothesis_seeded"
    assert decs[-1]["entity_id"] == "HrPlant"


def test_naming_endpoint_records_decision(client, monkeypatch):
    sid = client.post("/api/authoring/sessions", json={}).json()["id"]
    fake = nm.NamingDecision(
        entities=[
            nm.EntityName(
                korean_label="열연공장",
                english_id="HrPlant",
                role="root",
                description_short="열연 설비",
            ),
            nm.EntityName(
                korean_label="열연공장제약",
                english_id="HrPlantConstraint",
                role="child",
                parent_english_id="HrPlant",
                description_short="품종별 제약",
            ),
        ],
        naming_rationale="parent prefix 유지",
    )
    monkeypatch.setattr(auth_api, "decide_names", _stub_async(fake))

    h = hp.EntityHypothesis(
        candidate_term_korean="열연공장",
        candidate_term_english="HrPlant",
        domain_role="standard",
        pk_role_summary="온톨로지·소·열연공장·품종",
        confidence=0.7,
    )
    accepted = op.OntologyOption(
        id="C",
        name="옵션 C",
        description="d",
        structure_sketch="HrPlant ── HrPlantConstraint",
        entities_count_hint="중간",
        domain_alignment="high",
        trade_offs_one_line="t",
    )
    r = client.post(
        f"/api/authoring/sessions/{sid}/naming",
        json={
            "turn_no": 7,
            "hypothesis": h.model_dump(),
            "accepted_option": accepted.model_dump(),
        },
    )
    assert r.status_code == 200
    assert len(r.json()["entities"]) == 2

    decs = client.get(f"/api/authoring/sessions/{sid}/decisions").json()
    assert decs[-1]["decision_kind"] == "naming_confirmed"


def test_archive_endpoint_persists_markdown(client, monkeypatch):
    sid = client.post("/api/authoring/sessions", json={}).json()["id"]
    fake_body = ar.ArchiveBody(
        summary_korean="요약",
        decisions=[
            ar.ArchiveDecision(
                topic_korean="모델링", decision_korean="옵션 C", rationale_korean="응집 ↑"
            )
        ],
        structure_diagram="HrPlant",
    )
    fake_doc = ar.ArchiveDocument(
        title="Step 1 — 열연공장 entity 결정 ✓",
        status="completed",
        body=fake_body,
        markdown="# Step 1 — 열연공장 entity 결정 ✓\n\n요약",
    )
    monkeypatch.setattr(auth_api, "archive_entity_cycle", _stub_async(fake_doc))

    h = hp.EntityHypothesis(
        candidate_term_korean="열연공장",
        candidate_term_english="HrPlant",
        domain_role="standard",
        pk_role_summary="x",
        confidence=0.7,
    )
    answers = aa.AbsorbedAnswers()
    accepted = op.OntologyOption(
        id="C",
        name="옵션 C",
        description="d",
        structure_sketch="x",
        entities_count_hint="중간",
        domain_alignment="high",
        trade_offs_one_line="t",
    )
    names = nm.NamingDecision(
        entities=[
            nm.EntityName(
                korean_label="열연공장",
                english_id="HrPlant",
                role="root",
                description_short="d",
            )
        ],
        naming_rationale="r",
    )

    r = client.post(
        f"/api/authoring/sessions/{sid}/archive",
        json={
            "turn_no": 9,
            "hypothesis": h.model_dump(),
            "answers": answers.model_dump(),
            "accepted_option": accepted.model_dump(),
            "names": names.model_dump(),
            "step_number": 1,
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    # The decision row carries the rendered markdown so /preview can show it.
    decs = client.get(f"/api/authoring/sessions/{sid}/decisions").json()
    last = decs[-1]
    assert last["decision_kind"] == "archive_saved"
    assert "열연공장" in last["archive_markdown"]


# ── Confirm: persists to DomainLayerStore ──────────────────────────


def test_confirm_endpoint_persists_business_terms(client):
    sid = client.post("/api/authoring/sessions", json={}).json()["id"]

    names = nm.NamingDecision(
        entities=[
            nm.EntityName(
                korean_label="열연공장",
                english_id="HrPlant",
                role="root",
                description_short="온톨로지·소 단위 열연 설비",
            ),
            nm.EntityName(
                korean_label="열연공장제약",
                english_id="HrPlantConstraint",
                role="child",
                parent_english_id="HrPlant",
                description_short="품종별 폭/길이 제약",
            ),
        ],
        naming_rationale="parent prefix 유지",
    )
    accepted = op.OntologyOption(
        id="C",
        name="옵션 C",
        description="d",
        structure_sketch="HrPlant ── HrPlantConstraint",
        entities_count_hint="중간",
        domain_alignment="high",
        trade_offs_one_line="t",
    )

    r = client.post(
        f"/api/authoring/sessions/{sid}/confirm",
        json={
            "turn_no": 12,
            "names": names.model_dump(),
            "accepted_option": accepted.model_dump(),
            "repo_id": "slab",
            "domain": "scm",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["persisted_count"] == 2
    assert set(body["persisted_fqns"]) == {"term.slab.hrplant", "term.slab.hrplantconstraint"}

    # The terms actually exist in the ontology DB.
    store = DomainLayerStore()
    terms = store.list_terms(repo_id="slab")
    fqns = {t.fqn for t in terms}
    assert {"term.slab.hrplant", "term.slab.hrplantconstraint"} <= fqns

    # The root entity carries is_root_entity=True; the child does not.
    root = next(t for t in terms if t.fqn == "term.slab.hrplant")
    child = next(t for t in terms if t.fqn == "term.slab.hrplantconstraint")
    assert root.is_root_entity is True
    assert child.is_root_entity is False
    assert root.label == "열연공장"
    assert child.label == "열연공장제약"

    # A decision row was logged.
    decs = client.get(f"/api/authoring/sessions/{sid}/decisions").json()
    assert decs[-1]["decision_kind"] == "archive_saved"
    assert decs[-1]["payload"]["fqns"] == body["persisted_fqns"]

    # The session's focus jumped to the root entity.
    sess = client.get(f"/api/authoring/sessions/{sid}").json()
    assert sess["entity_focus"] == "HrPlant"


def test_confirm_returns_503_when_business_term_store_uninitialised(fresh_db):
    """If init() was called with None, /confirm fails fast instead of crashing."""
    app = FastAPI()
    auth_api.init(business_term_store=None)
    app.include_router(auth_api.router)
    c = TestClient(app)

    sid = c.post("/api/authoring/sessions", json={}).json()["id"]
    names = nm.NamingDecision(
        entities=[
            nm.EntityName(
                korean_label="X",
                english_id="X",
                role="root",
                description_short="x",
            )
        ],
        naming_rationale="r",
    )
    accepted = op.OntologyOption(
        id="A",
        name="A",
        description="d",
        structure_sketch="X",
        entities_count_hint="최소",
        domain_alignment="medium",
        trade_offs_one_line="t",
    )
    r = c.post(
        f"/api/authoring/sessions/{sid}/confirm",
        json={
            "turn_no": 1,
            "names": names.model_dump(),
            "accepted_option": accepted.model_dump(),
            "repo_id": "x",
        },
    )
    assert r.status_code == 503
