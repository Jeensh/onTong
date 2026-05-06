"""View Layer (Perspective) store CRUD tests — R4-T2.2."""
from __future__ import annotations

import os
import tempfile

import pytest

from backend.modeling.view_layer.schema import Perspective, PerspectiveSpec
from backend.modeling.view_layer.store import ViewLayerStore


@pytest.fixture
def fresh_db(monkeypatch):
    from backend.modeling.persistence.database import Base, get_engine, reset_engine_for_tests
    from backend.modeling.view_layer.orm import PerspectiveRow  # noqa: F401
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


def _sample_spec() -> PerspectiveSpec:
    return PerspectiveSpec(
        mode="neighborhood",
        n_max=60,
        focus_fqn="term.scm.order",
        visible_kinds=["term", "code_type", "action"],
    )


def test_create_get_list(fresh_db):
    store = ViewLayerStore()
    p = Perspective(name="도메인 전문가용", repo_id="r1", description="주문 중심 view", spec=_sample_spec())
    created = store.create(p)
    assert created.id is not None
    assert created.name == "도메인 전문가용"
    assert created.repo_id == "r1"
    assert created.spec.focus_fqn == "term.scm.order"
    assert created.created_at is not None

    # list — 같은 repo
    assert len(store.list(repo_id="r1")) == 1
    # 다른 repo 면 0
    assert len(store.list(repo_id="r2")) == 0

    # get by id
    fetched = store.get(created.id)
    assert fetched is not None
    assert fetched.name == "도메인 전문가용"


def test_update(fresh_db):
    store = ViewLayerStore()
    created = store.create(Perspective(name="v1", repo_id="r1", spec=_sample_spec()))
    new_spec = PerspectiveSpec(mode="cluster", n_max=100, visible_kinds=["term"])
    updated = store.update(created.id, name="v2", spec=new_spec)
    assert updated is not None
    assert updated.name == "v2"
    assert updated.spec.mode == "cluster"
    assert updated.spec.n_max == 100
    # updated_at 진행
    assert updated.updated_at >= created.updated_at


def test_delete(fresh_db):
    store = ViewLayerStore()
    created = store.create(Perspective(name="v1", repo_id="r1", spec=_sample_spec()))
    assert store.delete(created.id) is True
    assert store.get(created.id) is None
    assert store.delete(created.id) is False  # 이미 삭제


def test_repo_isolation(fresh_db):
    store = ViewLayerStore()
    store.create(Perspective(name="a", repo_id="r1", spec=_sample_spec()))
    store.create(Perspective(name="b", repo_id="r2", spec=_sample_spec()))
    assert len(store.list(repo_id="r1")) == 1
    assert len(store.list(repo_id="r2")) == 1
    assert len(store.list(repo_id=None)) == 2  # all


def test_id_must_be_none_for_create(fresh_db):
    store = ViewLayerStore()
    with pytest.raises(ValueError):
        store.create(Perspective(id=99, name="x", repo_id="r", spec=_sample_spec()))
