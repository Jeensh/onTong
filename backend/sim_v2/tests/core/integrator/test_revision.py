"""Revision pointer + lineage chain test — ADR-003 §5."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.integrator.revision import (
    FixtureBaseline,
    Revision,
    RevisionStore,
)


@pytest.fixture
def store() -> RevisionStore:
    return RevisionStore()


def _make_revision(
    parent: str | None = None,
    *,
    ontology: str = "v1",
    code: str = "abc123",
    schema: str = "v1",
    proposal_id: str = "prop-1",
    created_by: str = "jeensh",
) -> Revision:
    return Revision(
        proposal_id=proposal_id,
        ontology_revision=ontology,
        code_revision=code,
        schema_revision=schema,
        parent_revision=parent,
        created_by=created_by,
    )


def test_revision_id_is_uuid():
    r = _make_revision()
    assert len(r.id) == 36
    assert r.id.count("-") == 4


def test_revision_store_add_and_get(store: RevisionStore):
    r = _make_revision()
    store.add(r)
    assert store.get(r.id) is r
    assert store.count() == 1


def test_revision_store_duplicate_rejected(store: RevisionStore):
    r = _make_revision()
    store.add(r)
    with pytest.raises(ValueError, match="already exists"):
        store.add(r)


def test_revision_store_parent_missing(store: RevisionStore):
    bad = _make_revision(parent="non-existent")
    with pytest.raises(ValueError, match="Parent revision"):
        store.add(bad)


def test_lineage_traversal_root(store: RevisionStore):
    r0 = _make_revision()
    store.add(r0)
    lineage = store.lineage(r0.id)
    assert len(lineage) == 1
    assert lineage[0].id == r0.id


def test_lineage_traversal_chain(store: RevisionStore):
    r0 = _make_revision()
    store.add(r0)
    r1 = _make_revision(parent=r0.id, ontology="v2", proposal_id="prop-2")
    store.add(r1)
    r2 = _make_revision(parent=r1.id, ontology="v3", proposal_id="prop-3")
    store.add(r2)

    lineage = store.lineage(r2.id)
    assert len(lineage) == 3
    assert lineage[0].id == r2.id
    assert lineage[1].id == r1.id
    assert lineage[2].id == r0.id


def test_fixture_baseline_attached():
    baseline = FixtureBaseline(
        fixture_id="S1",
        output={"slab_count": 5, "total_kg": 12345.678},
        trace=[{"step_no": 1, "name": "validate"}],
        measured_tolerance={"action.scm.run": 1e-5},
    )
    r = _make_revision()
    r_with_baseline = r.model_copy(update={"fixture_baselines": {"S1": baseline}})
    assert r_with_baseline.fixture_baselines["S1"].output["slab_count"] == 5


def test_latest_for_plugin(store: RevisionStore):
    r1 = _make_revision(ontology="v2-slab-design@v1")
    store.add(r1)
    r2 = _make_revision(ontology="v2-slab-design@v2", parent=r1.id, proposal_id="prop-2")
    store.add(r2)
    r3 = _make_revision(ontology="broadleaf@v1", proposal_id="prop-3")
    store.add(r3)

    latest = store.latest_for_plugin("v2-slab-design")
    assert latest is not None
    assert latest.id == r2.id


def test_latest_for_plugin_none(store: RevisionStore):
    assert store.latest_for_plugin("nonexistent") is None
