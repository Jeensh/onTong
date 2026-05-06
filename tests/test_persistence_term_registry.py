"""SqliteBusinessTermRegistry — Protocol 호환 + 영구화 검증.

InMemoryBusinessTermRegistry 와 동일 인터페이스. 회귀 테스트는 InMemory 와
동일한 시나리오를 SQLite 위에서 돌려 동등성 확인.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from backend.modeling.mapping.business_term_registry import (
    BusinessTermRegistry,
)
from backend.modeling.mapping.mapping_models import BusinessTerm, BusinessTermSource
from backend.modeling.persistence import database as db
from backend.modeling.persistence.term_registry import SqliteBusinessTermRegistry


@pytest.fixture
def sqlite_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTONG_DB_PATH", str(tmp_path / "ontology.db"))
    db.reset_engine_for_tests()
    db.bootstrap_database()
    yield SqliteBusinessTermRegistry()
    db.reset_engine_for_tests()


def _term(qfn: str, label: str | None = None, aliases=None) -> BusinessTerm:
    return BusinessTerm(
        qualified_name=qfn,
        canonical_label=label or qfn.removeprefix("term."),
        aliases=list(aliases or []),
        domain="test",
        description=f"desc of {qfn}",
        source=BusinessTermSource.MANUAL,
        confirmed=True,
        created_at=datetime.now(timezone.utc),
    )


def test_protocol_compatible(sqlite_registry):
    assert isinstance(sqlite_registry, BusinessTermRegistry)


def test_put_get_roundtrip(sqlite_registry):
    sqlite_registry.put("repo-A", _term("term.슬래브두께", aliases=["thickness", "SLAB_THICK"]))
    out = sqlite_registry.get("repo-A", "term.슬래브두께")
    assert out is not None
    assert out.qualified_name == "term.슬래브두께"
    assert out.aliases == ["thickness", "SLAB_THICK"]
    assert out.confirmed is True


def test_put_upsert(sqlite_registry):
    sqlite_registry.put("repo-A", _term("term.A", "first"))
    sqlite_registry.put("repo-A", _term("term.A", "second"))  # 같은 fqn → upsert
    out = sqlite_registry.get("repo-A", "term.A")
    assert out.canonical_label == "second"


def test_list_by_repo_isolated(sqlite_registry):
    sqlite_registry.put("repo-A", _term("term.X"))
    sqlite_registry.put("repo-A", _term("term.Y"))
    sqlite_registry.put("repo-B", _term("term.Z"))
    a_list = sorted(t.qualified_name for t in sqlite_registry.list_by_repo("repo-A"))
    b_list = sorted(t.qualified_name for t in sqlite_registry.list_by_repo("repo-B"))
    assert a_list == ["term.X", "term.Y"]
    assert b_list == ["term.Z"]


def test_put_many(sqlite_registry):
    terms = [_term(f"term.t{i}") for i in range(5)]
    sqlite_registry.put_many("repo-bulk", terms)
    out = list(sqlite_registry.list_by_repo("repo-bulk"))
    assert len(out) == 5


def test_delete(sqlite_registry):
    sqlite_registry.put("repo-A", _term("term.X"))
    assert sqlite_registry.delete("repo-A", "term.X") is True
    assert sqlite_registry.get("repo-A", "term.X") is None
    assert sqlite_registry.delete("repo-A", "term.X") is False  # 두 번째 호출 → False


def test_clear_repo(sqlite_registry):
    sqlite_registry.put("repo-A", _term("term.X"))
    sqlite_registry.put("repo-B", _term("term.Y"))
    sqlite_registry.clear("repo-A")
    assert sqlite_registry.get("repo-A", "term.X") is None
    assert sqlite_registry.get("repo-B", "term.Y") is not None


def test_clear_all(sqlite_registry):
    sqlite_registry.put("repo-A", _term("term.X"))
    sqlite_registry.put("repo-B", _term("term.Y"))
    sqlite_registry.clear()
    assert sqlite_registry.repos() == set()


def test_repos(sqlite_registry):
    sqlite_registry.put("repo-A", _term("term.X"))
    sqlite_registry.put("repo-B", _term("term.Y"))
    sqlite_registry.put("repo-A", _term("term.Z"))
    assert sqlite_registry.repos() == {"repo-A", "repo-B"}


def test_persistence_across_engine_reset(tmp_path, monkeypatch):
    """DB 재연결 후에도 데이터 유지 — 진짜 영구화 확인."""
    db_path = str(tmp_path / "ontology.db")
    monkeypatch.setenv("ONTONG_DB_PATH", db_path)
    db.reset_engine_for_tests()
    db.bootstrap_database()
    reg1 = SqliteBusinessTermRegistry()
    reg1.put("repo-X", _term("term.persistent", "영구화_테스트"))

    # engine 리셋 — 같은 DB 파일을 새로 열어도 데이터 그대로
    db.reset_engine_for_tests()
    monkeypatch.setenv("ONTONG_DB_PATH", db_path)
    db.bootstrap_database()
    reg2 = SqliteBusinessTermRegistry()
    out = reg2.get("repo-X", "term.persistent")
    assert out is not None
    assert out.canonical_label == "영구화_테스트"
    db.reset_engine_for_tests()
