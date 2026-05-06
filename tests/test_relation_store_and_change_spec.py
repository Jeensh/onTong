"""H — SqliteOntologyRelationStore + SqliteChangeSpecStore unit tests."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from backend.modeling.persistence.database import bootstrap_database


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """각 test 가 자기만의 SQLite 사용."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    # database 모듈은 ONTONG_DB_PATH 를 lazy 로 읽으므로 reset 후 재 bootstrap
    from backend.modeling.persistence import database as _db
    _db._engine = None    # type: ignore[attr-defined]
    _db._SessionLocal = None    # type: ignore[attr-defined]
    bootstrap_database()
    yield


# ── OntologyRelation ─────────────────────────────────────────────────────
def test_relation_put_and_get():
    from backend.modeling.persistence.relation_store import (
        NodeKind, OntologyRelation, RelationKind, SqliteOntologyRelationStore,
    )
    s = SqliteOntologyRelationStore()
    rel = OntologyRelation(
        repo_id="repo1",
        src_kind=NodeKind.TERM, src_fqn="term.A",
        dst_kind=NodeKind.TERM, dst_fqn="term.B",
        kind=RelationKind.RELATED_TO,
        rationale="동일 도메인",
        source="manual",
    )
    saved = s.put(rel)
    assert saved.id != ""
    fetched = s.get(saved.id)
    assert fetched is not None
    assert fetched.src_fqn == "term.A"
    assert fetched.kind == RelationKind.RELATED_TO


def test_relation_list_by_repo():
    from backend.modeling.persistence.relation_store import (
        NodeKind, OntologyRelation, RelationKind, SqliteOntologyRelationStore,
    )
    s = SqliteOntologyRelationStore()
    s.put(OntologyRelation(repo_id="r1", src_kind=NodeKind.TERM, src_fqn="A",
                            dst_kind=NodeKind.TERM, dst_fqn="B", kind=RelationKind.IS_A))
    s.put(OntologyRelation(repo_id="r1", src_kind=NodeKind.TERM, src_fqn="C",
                            dst_kind=NodeKind.TERM, dst_fqn="D", kind=RelationKind.PART_OF))
    s.put(OntologyRelation(repo_id="r2", src_kind=NodeKind.TERM, src_fqn="X",
                            dst_kind=NodeKind.TERM, dst_fqn="Y", kind=RelationKind.IS_A))
    items_r1 = list(s.list_by_repo("r1"))
    assert len(items_r1) == 2


def test_relation_list_by_node():
    from backend.modeling.persistence.relation_store import (
        NodeKind, OntologyRelation, RelationKind, SqliteOntologyRelationStore,
    )
    s = SqliteOntologyRelationStore()
    s.put(OntologyRelation(repo_id="r1", src_kind=NodeKind.TERM, src_fqn="A",
                            dst_kind=NodeKind.TERM, dst_fqn="B", kind=RelationKind.IS_A))
    s.put(OntologyRelation(repo_id="r1", src_kind=NodeKind.TERM, src_fqn="A",
                            dst_kind=NodeKind.TERM, dst_fqn="C", kind=RelationKind.PART_OF))
    items = list(s.list_by_node("r1", "A"))
    assert len(items) == 2


def test_relation_delete():
    from backend.modeling.persistence.relation_store import (
        NodeKind, OntologyRelation, RelationKind, SqliteOntologyRelationStore,
    )
    s = SqliteOntologyRelationStore()
    saved = s.put(OntologyRelation(repo_id="r", src_kind=NodeKind.TERM, src_fqn="A",
                                    dst_kind=NodeKind.TERM, dst_fqn="B", kind=RelationKind.IS_A))
    assert s.delete(saved.id) is True
    assert s.get(saved.id) is None
    assert s.delete("nonexistent") is False


def test_relation_derive_id_deterministic():
    from backend.modeling.persistence.relation_store import OntologyRelation
    id1 = OntologyRelation.derive_id("r", "A", "B", "is_a")
    id2 = OntologyRelation.derive_id("r", "A", "B", "is_a")
    assert id1 == id2
    assert len(id1) == 16


# ── ChangeSpec ────────────────────────────────────────────────────────────
def test_change_spec_put_and_get():
    from backend.modeling.simulation.change_spec import (
        ChangeSpec, ChangeSpecKind, ChangeSpecStatus, SqliteChangeSpecStore,
    )
    s = SqliteChangeSpecStore()
    spec = ChangeSpec(
        repo_id="r1",
        target_method_fqn="x.y.M.f",
        kind=ChangeSpecKind.RULE_SEVERITY,
        description="test",
        payload={"old": "soft", "new": "hard"},
    )
    saved = s.put(spec)
    assert saved.id != ""
    fetched = s.get(saved.id)
    assert fetched is not None
    assert fetched.kind == ChangeSpecKind.RULE_SEVERITY
    assert fetched.status == ChangeSpecStatus.DRAFT


def test_change_spec_list_by_method():
    from backend.modeling.simulation.change_spec import (
        ChangeSpec, ChangeSpecKind, SqliteChangeSpecStore,
    )
    s = SqliteChangeSpecStore()
    s.put(ChangeSpec(repo_id="r1", target_method_fqn="m1", kind=ChangeSpecKind.RULE_SEVERITY, description="a"))
    s.put(ChangeSpec(repo_id="r1", target_method_fqn="m1", kind=ChangeSpecKind.METHOD_BODY, description="b"))
    s.put(ChangeSpec(repo_id="r1", target_method_fqn="m2", kind=ChangeSpecKind.ANCHOR_VALUE, description="c"))
    items_m1 = list(s.list_by_method("r1", "m1"))
    assert len(items_m1) == 2


def test_change_spec_status_filter():
    from backend.modeling.simulation.change_spec import (
        ChangeSpec, ChangeSpecKind, ChangeSpecStatus, SqliteChangeSpecStore,
    )
    s = SqliteChangeSpecStore()
    a = s.put(ChangeSpec(repo_id="r", target_method_fqn="m", kind=ChangeSpecKind.RULE_SEVERITY, description="a"))
    b = s.put(ChangeSpec(repo_id="r", target_method_fqn="m", kind=ChangeSpecKind.METHOD_BODY, description="b"))
    # a 를 completed 로 갱신
    s.put(a.model_copy(update={"status": ChangeSpecStatus.COMPLETED}))
    completed = list(s.list_by_repo("r", ChangeSpecStatus.COMPLETED))
    assert len(completed) == 1


def test_change_spec_delete():
    from backend.modeling.simulation.change_spec import (
        ChangeSpec, ChangeSpecKind, SqliteChangeSpecStore,
    )
    s = SqliteChangeSpecStore()
    saved = s.put(ChangeSpec(repo_id="r", target_method_fqn="m", kind=ChangeSpecKind.RULE_SEVERITY, description="x"))
    assert s.delete(saved.id) is True
    assert s.get(saved.id) is None
    assert s.delete("nonexistent") is False


def test_change_spec_simulation_result_roundtrip():
    """simulation_result (dict) JSON serialization round-trip."""
    from backend.modeling.simulation.change_spec import (
        ChangeSpec, ChangeSpecKind, ChangeSpecStatus, SqliteChangeSpecStore,
    )
    s = SqliteChangeSpecStore()
    spec = ChangeSpec(
        repo_id="r", target_method_fqn="m",
        kind=ChangeSpecKind.METHOD_BODY, description="x",
        status=ChangeSpecStatus.COMPLETED,
        simulation_result={
            "engine": "test",
            "before": {"x": 1, "korean": "한국어"},   # utf-8 처리 검증
            "after": {"y": "value"},
        },
    )
    saved = s.put(spec)
    fetched = s.get(saved.id)
    assert fetched is not None
    assert fetched.simulation_result["engine"] == "test"
    assert fetched.simulation_result["before"]["korean"] == "한국어"
