"""P1a-B — session resume / replay logic."""

from __future__ import annotations

import pytest

from backend.application.authoring import session as smod
from backend.application.authoring.replay import (
    SessionResumeState,
    build_resume_state,
)
from backend.modeling.persistence.database import bootstrap_database


@pytest.fixture(scope="module", autouse=True)
def _bootstrap_db() -> None:
    bootstrap_database()


def test_replay_unknown_session_returns_none():
    assert build_resume_state("does-not-exist") is None


def test_replay_empty_session_returns_empty_state():
    sid = smod.create_session(operator_id="replay_t", repo_id="dummy")
    state = build_resume_state(sid)
    assert state is not None
    assert state.session.id == sid
    assert state.completed_entities == []
    assert state.current.jpo is None
    assert state.decision_count == 0


def test_replay_walks_decisions_into_current_state():
    sid = smod.create_session(operator_id="replay_t2", repo_id="dummy")
    # Simulate: extract → hypothesis → option → name (no archive yet)
    smod.add_decision(
        session_id=sid, turn_no=1, decision_kind="other",
        payload={"capability": "code_extractor", "result": {"class_name": "FooJpo", "package": "x"}},
    )
    smod.add_decision(
        session_id=sid, turn_no=2, decision_kind="hypothesis_seeded",
        payload={"capability": "hypothesis", "result": {"candidate_term_english": "Foo", "confidence": 0.6}},
    )
    smod.add_decision(
        session_id=sid, turn_no=3, decision_kind="other",
        payload={"capability": "option_proposer", "result": {"options": [], "recommended_id": "A"}},
    )
    state = build_resume_state(sid)
    assert state is not None
    assert state.completed_entities == []
    assert state.current.jpo == {"class_name": "FooJpo", "package": "x"}
    assert state.current.hypothesis["candidate_term_english"] == "Foo"
    assert state.current.option_table["recommended_id"] == "A"
    assert state.decision_count == 3


def test_replay_splits_at_next_entity_started():
    sid = smod.create_session(operator_id="replay_t3", repo_id="dummy")
    # Cycle 1: extract + hypothesis + archive
    smod.add_decision(
        session_id=sid, turn_no=1, decision_kind="other",
        payload={"capability": "code_extractor", "result": {"class_name": "AJpo"}},
    )
    smod.add_decision(
        session_id=sid, turn_no=2, decision_kind="hypothesis_seeded",
        payload={"capability": "hypothesis", "result": {"candidate_term_english": "A"}},
    )
    smod.add_decision(
        session_id=sid, turn_no=3, decision_kind="archive_saved",
        payload={"capability": "archiver", "result": {"markdown": "A done"}},
    )
    # Cycle boundary
    smod.add_decision(
        session_id=sid, turn_no=4, decision_kind="next_entity_started",
        payload={},
    )
    # Cycle 2: only extract so far (in-progress)
    smod.add_decision(
        session_id=sid, turn_no=5, decision_kind="other",
        payload={"capability": "code_extractor", "result": {"class_name": "BJpo"}},
    )

    state = build_resume_state(sid)
    assert state is not None
    assert len(state.completed_entities) == 1
    a_cycle = state.completed_entities[0]
    assert a_cycle.jpo == {"class_name": "AJpo"}
    assert a_cycle.hypothesis["candidate_term_english"] == "A"
    assert a_cycle.archive["markdown"] == "A done"
    assert a_cycle.completed_at is not None  # set from boundary

    assert state.current.jpo == {"class_name": "BJpo"}
    assert state.current.hypothesis is None  # cycle 2 hasn't done hypothesis yet


def test_replay_merges_persisted_fqns_from_confirm():
    sid = smod.create_session(operator_id="replay_t4", repo_id="dummy")
    smod.add_decision(
        session_id=sid, turn_no=1, decision_kind="other",
        payload={"capability": "code_extractor", "result": {"class_name": "CJpo"}},
    )
    smod.add_decision(
        session_id=sid, turn_no=2, decision_kind="archive_saved",
        payload={
            "capability": "confirmer",
            "persisted_fqns": ["term.x.c", "term.x.c2"],
        },
    )
    state = build_resume_state(sid)
    assert state is not None
    # Persisted fqns merged into current
    assert "term.x.c" in state.current.persisted_fqns
    assert "term.x.c2" in state.current.persisted_fqns
