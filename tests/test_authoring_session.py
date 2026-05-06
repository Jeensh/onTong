"""S5 — Session + Decision Log + Cost persistence tests.

Uses a per-test temp SQLite DB via the ONTONG_DB_PATH env var so we never
touch the project's real ontology.db. No LLM calls.
"""

from __future__ import annotations

import os
import time

import pytest

from backend.application.authoring import cost as cost_mod
from backend.application.authoring import session as sess_mod
from backend.application.authoring.schemas import ModelTier, TokenUsage
from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point the engine at a per-test SQLite file and bootstrap the schema.

    We import the authoring orm module so its tables register with Base
    metadata before create_all().
    """
    db_path = tmp_path / "authoring_test.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    db_mod.reset_engine_for_tests()

    # Register every ORM module main.py would have imported so create_all
    # produces the same shape as production.
    from backend.modeling.code_layer import orm as _code_orm  # noqa: F401
    from backend.modeling.domain_layer import orm as _domain_orm  # noqa: F401
    from backend.modeling.mapping_layer import orm as _mapping_orm  # noqa: F401
    from backend.modeling.view_layer import orm as _view_orm  # noqa: F401
    from backend.application.authoring import orm as _authoring_orm  # noqa: F401

    db_mod.bootstrap_database()
    cost_mod.reset_buffer()
    yield db_path
    db_mod.reset_engine_for_tests()


# ── Session CRUD ─────────────────────────────────────────────────────


def test_create_session_returns_uuid_and_persists(fresh_db):
    sid = sess_mod.create_session(operator_id="alice", branch_name="feat/hrplant")
    assert len(sid) == 36 and sid.count("-") == 4  # UUID4 shape

    fetched = sess_mod.get_session(sid)
    assert fetched is not None
    assert fetched.operator_id == "alice"
    assert fetched.branch_name == "feat/hrplant"
    assert fetched.status == "active"
    assert fetched.entity_focus is None


def test_create_session_with_meta_and_repo(fresh_db):
    sid = sess_mod.create_session(
        operator_id="bob",
        branch_name="main",
        repo_id="slab-design-real",
        entity_focus="HrPlant",
        meta={"source": "round5_replay", "step": 5},
    )
    fetched = sess_mod.get_session(sid)
    assert fetched is not None
    assert fetched.repo_id == "slab-design-real"
    assert fetched.entity_focus == "HrPlant"
    assert fetched.meta == {"source": "round5_replay", "step": 5}


def test_get_session_returns_none_for_unknown(fresh_db):
    assert sess_mod.get_session("00000000-0000-0000-0000-000000000000") is None


def test_update_focus_and_status(fresh_db):
    sid = sess_mod.create_session()
    sess_mod.update_focus(sid, "HrPlantConstraint")
    sess_mod.update_status(sid, "paused")

    fetched = sess_mod.get_session(sid)
    assert fetched is not None
    assert fetched.entity_focus == "HrPlantConstraint"
    assert fetched.status == "paused"


def test_update_unknown_session_raises(fresh_db):
    with pytest.raises(KeyError, match="not found"):
        sess_mod.update_focus("nope", "X")
    with pytest.raises(KeyError, match="not found"):
        sess_mod.update_status("nope", "merged")


def test_list_sessions_filters_and_orders_newest_first(fresh_db):
    sid_a = sess_mod.create_session(operator_id="alice")
    time.sleep(0.01)
    sid_b = sess_mod.create_session(operator_id="bob")
    time.sleep(0.01)
    sid_c = sess_mod.create_session(operator_id="alice")

    # Order before any activity bump: c, b, a (newest first by creation).
    assert [s.id for s in sess_mod.list_sessions()[:3]] == [sid_c, sid_b, sid_a]

    only_alice = sess_mod.list_sessions(operator_id="alice")
    assert {s.id for s in only_alice} == {sid_a, sid_c}

    # update_status bumps last_activity_at — sid_b moves to the front.
    sess_mod.update_status(sid_b, "merged")
    assert [s.id for s in sess_mod.list_sessions()[:3]] == [sid_b, sid_c, sid_a]

    only_active = sess_mod.list_sessions(status="active")
    assert sid_b not in {s.id for s in only_active}


# ── Decision log ─────────────────────────────────────────────────────


def test_add_decision_persists_and_returns_id(fresh_db):
    sid = sess_mod.create_session()
    did = sess_mod.add_decision(
        session_id=sid,
        turn_no=5,
        decision_kind="option_selected",
        payload={"option_id": "C", "reason": "도메인 응집"},
        step_label="Step 5 — 옵션 채택",
        entity_id="HrPlant",
    )
    assert isinstance(did, int) and did > 0

    decs = sess_mod.list_decisions(sid)
    assert len(decs) == 1
    d = decs[0]
    assert d.id == did
    assert d.turn_no == 5
    assert d.decision_kind == "option_selected"
    assert d.payload == {"option_id": "C", "reason": "도메인 응집"}
    assert d.entity_id == "HrPlant"


def test_add_decision_with_archive_markdown(fresh_db):
    sid = sess_mod.create_session()
    md = "# Step 1 — HrPlant entity 결정 ✓\n\n요약: ..."
    sess_mod.add_decision(
        session_id=sid,
        turn_no=1,
        decision_kind="archive_saved",
        payload={"entities": 2},
        archive_markdown=md,
    )
    decs = sess_mod.list_decisions(sid)
    assert decs[0].archive_markdown == md


def test_list_decisions_orders_by_turn_then_id(fresh_db):
    sid = sess_mod.create_session()
    sess_mod.add_decision(
        session_id=sid, turn_no=2, decision_kind="naming_confirmed", payload={"k": 1}
    )
    sess_mod.add_decision(
        session_id=sid, turn_no=1, decision_kind="hypothesis_seeded", payload={"k": 2}
    )
    sess_mod.add_decision(
        session_id=sid, turn_no=1, decision_kind="interview_designed", payload={"k": 3}
    )

    decs = sess_mod.list_decisions(sid)
    assert [d.turn_no for d in decs] == [1, 1, 2]
    # within turn 1, the one added first comes first (id ordering)
    assert decs[0].decision_kind == "hypothesis_seeded"
    assert decs[1].decision_kind == "interview_designed"


def test_add_decision_unknown_session_raises(fresh_db):
    with pytest.raises(KeyError, match="not found"):
        sess_mod.add_decision(
            session_id="nope", turn_no=1, decision_kind="other", payload={}
        )


def test_add_decision_updates_session_last_activity(fresh_db):
    sid = sess_mod.create_session()
    before = sess_mod.get_session(sid)
    assert before is not None
    time.sleep(0.01)
    sess_mod.add_decision(
        session_id=sid, turn_no=1, decision_kind="other", payload={}
    )
    after = sess_mod.get_session(sid)
    assert after is not None
    assert after.last_activity_at >= before.last_activity_at


def test_decision_payload_with_korean_preserved(fresh_db):
    sid = sess_mod.create_session()
    sess_mod.add_decision(
        session_id=sid,
        turn_no=1,
        decision_kind="naming_confirmed",
        payload={"korean_label": "열연공장제약", "english_id": "HrPlantConstraint"},
    )
    decs = sess_mod.list_decisions(sid)
    assert decs[0].payload["korean_label"] == "열연공장제약"


# ── Cost persistence integration ─────────────────────────────────────


def test_cost_log_persists_to_db_when_session_exists(fresh_db):
    sid = sess_mod.create_session(operator_id="alice")
    cost_mod.log_call(
        session_id=sid,
        turn_no=1,
        capability="hypothesis",
        tier=ModelTier.HARD,
        model_id="anthropic/claude-opus-4-7",
        usage=TokenUsage(input_tokens=3000, output_tokens=1500),
        duration_ms=20000,
    )
    cost_mod.log_call(
        session_id=sid,
        turn_no=2,
        capability="archiver",
        tier=ModelTier.STANDARD,
        model_id="anthropic/claude-sonnet-4-6",
        usage=TokenUsage(input_tokens=2000, output_tokens=1000),
        duration_ms=18000,
    )

    # In-memory total still works
    assert cost_mod.session_total_usd(sid) > 0

    # Rows landed in the DB
    from backend.application.authoring.orm import AuthoringCostRow
    from backend.modeling.persistence.database import session_scope
    from sqlalchemy import select

    with session_scope() as s:
        rows = (
            s.execute(
                select(AuthoringCostRow).where(AuthoringCostRow.session_id == sid)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        caps = {r.capability for r in rows}
        assert caps == {"hypothesis", "archiver"}
        # Totals match the in-memory computation
        db_total = round(sum(r.cost_usd for r in rows), 6)
        assert db_total == cost_mod.session_total_usd(sid)


def test_cost_log_silently_skips_db_for_unregistered_session(fresh_db):
    """Unit-test session ids that don't exist in DB still log in-memory.

    This keeps every existing capability test (which uses arbitrary session
    ids like 's2-integration') working unchanged. The DB write is best-effort.
    """
    cost_mod.log_call(
        session_id="not-a-real-session",
        turn_no=1,
        capability="code_extractor",
        tier=ModelTier.STANDARD,
        model_id="anthropic/claude-sonnet-4-6",
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    )
    # In-memory still works
    assert len(cost_mod.session_records("not-a-real-session")) == 1

    # No DB row landed
    from backend.application.authoring.orm import AuthoringCostRow
    from backend.modeling.persistence.database import session_scope
    from sqlalchemy import select

    with session_scope() as s:
        rows = (
            s.execute(
                select(AuthoringCostRow).where(
                    AuthoringCostRow.session_id == "not-a-real-session"
                )
            )
            .scalars()
            .all()
        )
        assert rows == []


def test_decisions_cascade_delete_with_session(fresh_db):
    """ON DELETE CASCADE on FK keeps the table clean if a session is removed."""
    sid = sess_mod.create_session()
    sess_mod.add_decision(
        session_id=sid, turn_no=1, decision_kind="other", payload={}
    )
    cost_mod.log_call(
        session_id=sid,
        turn_no=1,
        capability="hypothesis",
        tier=ModelTier.HARD,
        model_id="anthropic/claude-opus-4-7",
        usage=TokenUsage(input_tokens=10, output_tokens=10),
    )

    from backend.application.authoring.orm import (
        AuthoringCostRow,
        AuthoringDecisionRow,
        AuthoringSessionRow,
    )
    from backend.modeling.persistence.database import session_scope
    from sqlalchemy import select

    with session_scope() as s:
        s.delete(s.get(AuthoringSessionRow, sid))

    with session_scope() as s:
        decs = s.execute(
            select(AuthoringDecisionRow).where(AuthoringDecisionRow.session_id == sid)
        ).scalars().all()
        costs = s.execute(
            select(AuthoringCostRow).where(AuthoringCostRow.session_id == sid)
        ).scalars().all()
        assert decs == []
        assert costs == []
