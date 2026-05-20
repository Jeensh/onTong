"""Step 1c TDD — section3_decision_log persistence.

차용 원본: `backend/application/authoring/session.py:190-233` (add_decision/list_decisions).
DB 패턴: `Base.metadata.create_all()` (alembic 없이 — authoring 의 실제 패턴).
"""
from __future__ import annotations

import pytest

from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Per-test SQLite + create_all (authoring fixture 패턴 차용)."""
    db_path = tmp_path / "section3_multiturn.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    db_mod.reset_engine_for_tests()

    # ORM module import 만으로 Base.metadata 에 등록됨 — main.py 의 startup 흐름과 동일.
    from backend.modeling.code_layer import orm as _code_orm  # noqa: F401
    from backend.modeling.domain_layer import orm as _domain_orm  # noqa: F401
    from backend.modeling.mapping_layer import orm as _mapping_orm  # noqa: F401
    from backend.modeling.view_layer import orm as _view_orm  # noqa: F401
    from backend.application.authoring import orm as _authoring_orm  # noqa: F401
    from backend.section3.agents.multiturn import orm as _multiturn_orm  # noqa: F401

    db_mod.bootstrap_database()
    yield db_path
    db_mod.reset_engine_for_tests()


def _make_target_payload() -> dict:
    return {
        "kind": "target_selected",
        "intent": "simulate",
        "user_query": "주문 검증 시뮬",
        "candidates": [
            {
                "action_id": "action.scm.order.validate",
                "label": "주문 검증",
                "score": 0.9,
                "code_method_fqn": "OrderService.validateOrder",
            },
        ],
        "recommended_index": 0,
        "selected": None,
        "sources": [
            {"source": "sim_v2", "detail": "find_action_candidates", "confidence": 0.9},
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Session lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def test_start_session_returns_uuid_and_persists(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    session_id = p.start_session(repo_id="slab-design-real-v2", user_query="주문 검증 시뮬")
    assert isinstance(session_id, str) and len(session_id) >= 8
    s = p.get_session(session_id)
    assert s is not None
    assert s.repo_id == "slab-design-real-v2"
    assert s.status == "active"
    assert s.user_query == "주문 검증 시뮬"


def test_get_session_unknown_returns_none(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    assert p.get_session("nonexistent-uuid") is None


def test_update_session_status_to_done(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="slab-design-real-v2")
    p.update_session_status(sid, "done")
    assert p.get_session(sid).status == "done"


def test_update_status_unknown_raises(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    with pytest.raises(KeyError):
        p.update_session_status("nonexistent-uuid", "done")


# ─────────────────────────────────────────────────────────────────────────────
# Decision log
# ─────────────────────────────────────────────────────────────────────────────


def test_add_gate_decision_persists_and_returns_id(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="slab-design-real-v2")
    row_id = p.add_gate_decision(
        session_id=sid, turn_no=1, gate_payload=_make_target_payload(),
    )
    assert isinstance(row_id, int) and row_id > 0


def test_add_gate_decision_unknown_session_raises(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    with pytest.raises(KeyError):
        p.add_gate_decision(
            session_id="missing", turn_no=1, gate_payload=_make_target_payload(),
        )


def test_list_gate_decisions_orders_by_turn_then_id(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="slab-design-real-v2")
    a = p.add_gate_decision(session_id=sid, turn_no=2, gate_payload=_make_target_payload())
    b = p.add_gate_decision(session_id=sid, turn_no=1, gate_payload=_make_target_payload())
    c = p.add_gate_decision(session_id=sid, turn_no=1, gate_payload=_make_target_payload())
    rows = p.list_gate_decisions(sid)
    # 정렬: turn_no asc, then id asc
    assert [r.turn_no for r in rows] == [1, 1, 2]
    assert rows[0].id < rows[1].id          # 같은 turn 안에서는 id 순


def test_update_user_response_persists(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="slab-design-real-v2")
    row_id = p.add_gate_decision(
        session_id=sid, turn_no=1, gate_payload=_make_target_payload(),
    )
    p.update_user_response(row_id, {"action": "confirm", "selected_index": 0})
    rows = p.list_gate_decisions(sid)
    assert rows[0].user_response == {"action": "confirm", "selected_index": 0}


def test_update_user_response_unknown_raises(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    with pytest.raises(KeyError):
        p.update_user_response(999999, {"action": "confirm"})


def test_add_gate_decision_updates_last_activity(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="slab-design-real-v2")
    before = p.get_session(sid).last_activity_at
    # 약간의 시간차 보장
    import time; time.sleep(0.01)
    p.add_gate_decision(
        session_id=sid, turn_no=1, gate_payload=_make_target_payload(),
    )
    after = p.get_session(sid).last_activity_at
    assert after > before


def test_korean_payload_preserved_through_roundtrip(fresh_db) -> None:
    """한국어 label / user_query 가 JSON 직렬화 후도 보존."""
    from backend.section3.agents.multiturn import persistence as p
    sid = p.start_session(repo_id="slab-design-real-v2", user_query="엣징 룰 시뮬해줘")
    p.add_gate_decision(
        session_id=sid, turn_no=1, gate_payload=_make_target_payload(),
    )
    rows = p.list_gate_decisions(sid)
    assert rows[0].payload["user_query"] == "주문 검증 시뮬"
    assert rows[0].payload["candidates"][0]["label"] == "주문 검증"


# ─────────────────────────────────────────────────────────────────────────────
# replay — hydrate GatePayload (source-of-truth, sim_v2 재호출 X)
# ─────────────────────────────────────────────────────────────────────────────


def test_replay_session_hydrates_typed_payloads(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    from backend.section3.agents.multiturn.schemas import GateTarget
    sid = p.start_session(repo_id="slab-design-real-v2", user_query="주문 검증 시뮬")
    p.add_gate_decision(
        session_id=sid, turn_no=1, gate_payload=_make_target_payload(),
    )
    replay = p.replay_session(sid)
    assert replay.session.id == sid
    assert len(replay.decisions) == 1
    # payload 가 Pydantic 모델로 hydrate 됨 (source-of-truth — drift 없음)
    typed = replay.decisions[0].typed_payload
    assert isinstance(typed, GateTarget)
    assert typed.intent == "simulate"


def test_replay_unknown_session_returns_none(fresh_db) -> None:
    from backend.section3.agents.multiturn import persistence as p
    assert p.replay_session("missing-uuid") is None
