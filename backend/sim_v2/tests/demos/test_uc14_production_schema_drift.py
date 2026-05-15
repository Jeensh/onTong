"""UC14 — Production schema drift demo verification — W44.3.

Validates: production DB → loader → snapshot v1 → mutate → snapshot v2 →
compute_diff produces a drift report. Skips cleanly if production DB missing.
"""
from __future__ import annotations

import copy

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc14_production_schema_drift.run import (
    DEFAULT_REPO_ID,
    DriftReport,
    main,
    mutate_entities,
    survey_drift,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Demo entry point
# ─────────────────────────────────────────────────────────────────────────────


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc14_production_schema_drift import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# mutate_entities — pure-function mutations
# ─────────────────────────────────────────────────────────────────────────────


def _make_entity(class_fqn, table_name, cols):
    return {
        "class_fqn":   class_fqn,
        "table_name":  table_name,
        "schema_name": "public",
        "columns":     cols,
        "indexes":     [],
        "fks":         [],
    }


def _col(field_name, column_name, data_type="VARCHAR", nullable=True, pk=False):
    return {
        "field_name":  field_name,
        "column_name": column_name,
        "data_type":   data_type,
        "nullable":    nullable,
        "primary_key": pk,
    }


def test_mutate_entities_does_not_mutate_input():
    """mutate_entities() must deep-copy — input untouched (so the same entity
    list can drive multiple comparisons in one demo run)."""
    entities = [
        _make_entity("a", "A", [_col("id", "ID", "BIGINT", False, True),
                                _col("x", "X", "VARCHAR")]),
        _make_entity("b", "B", [_col("id", "ID", "BIGINT", False, True)]),
        _make_entity("c", "C", [_col("id", "ID", "BIGINT", False, True)]),
    ]
    snapshot = copy.deepcopy(entities)
    mutate_entities(entities)
    assert entities == snapshot, "mutate_entities must not modify its input"


def test_mutate_drops_second_column_of_first_entity():
    entities = [
        _make_entity("a", "A", [_col("id", "ID", "BIGINT", False, True),
                                _col("doomed", "DOOMED", "VARCHAR")]),
    ]
    mutated = mutate_entities(entities)
    names = [c["column_name"] for c in mutated[0]["columns"]]
    assert "DOOMED" not in names
    assert mutated[0]["_drift_note_drop"] == "DOOMED"


def test_mutate_changes_pk_type_on_second_entity():
    entities = [
        _make_entity("a", "A", [_col("id", "ID", "BIGINT", False, True),
                                _col("x", "X")]),
        _make_entity("b", "B", [_col("id", "ID", "VARCHAR", False, True)]),
    ]
    mutated = mutate_entities(entities)
    pk_col = next(c for c in mutated[1]["columns"] if c["primary_key"])
    assert pk_col["data_type"] != "VARCHAR"  # was VARCHAR, mutator flips
    assert mutated[1]["_drift_note_type"] == pk_col["column_name"]


def test_mutate_adds_audit_ts_to_third_entity():
    entities = [
        _make_entity("a", "A", [_col("id", "ID", "BIGINT", False, True),
                                _col("x", "X")]),
        _make_entity("b", "B", [_col("id", "ID", "BIGINT", False, True)]),
        _make_entity("c", "C", [_col("id", "ID", "BIGINT", False, True)]),
    ]
    mutated = mutate_entities(entities)
    names = [c["column_name"] for c in mutated[2]["columns"]]
    assert "AUDIT_TS" in names
    audit = next(c for c in mutated[2]["columns"] if c["column_name"] == "AUDIT_TS")
    assert audit["data_type"] == "TIMESTAMP"
    assert mutated[2]["_drift_note_add"] == "AUDIT_TS"


def test_mutate_is_safe_on_short_entity_lists():
    """An empty or single-entity list applies what it can without raising."""
    empty = mutate_entities([])
    assert empty == []
    one = mutate_entities([_make_entity("a", "A",
                                        [_col("id", "ID", "BIGINT", False, True)])])
    # First entity has only 1 column so drop-second mutation is a no-op
    assert len(one) == 1


# ─────────────────────────────────────────────────────────────────────────────
# survey_drift — DB-backed
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_survey_drift_returns_drift_report():
    session = open_readonly_session()
    try:
        report = survey_drift(session, DEFAULT_REPO_ID)
        assert isinstance(report, DriftReport)
        assert report.repo_id == DEFAULT_REPO_ID
        assert report.has_drift is True
        # v2 has one column dropped + one added ⇒ net zero
        assert report.v1_column_count == report.v2_column_count
    finally:
        session.close()


@requires_production_db
def test_survey_drift_surfaces_each_of_the_three_mutation_kinds():
    """The three orthogonal mutations should produce at least one add,
    one remove, and one change in the diff."""
    session = open_readonly_session()
    try:
        report = survey_drift(session, DEFAULT_REPO_ID)
        assert len(report.diff.added_columns) >= 1
        assert len(report.diff.removed_columns) >= 1
        assert len(report.diff.changed_columns) >= 1
    finally:
        session.close()


@requires_production_db
def test_survey_drift_added_column_is_audit_ts():
    """The synthetic mutation adds AUDIT_TS — assert it shows up exactly."""
    session = open_readonly_session()
    try:
        report = survey_drift(session, DEFAULT_REPO_ID)
        added_names = {c.column_name for c in report.diff.added_columns}
        assert "AUDIT_TS" in added_names
    finally:
        session.close()


@requires_production_db
def test_survey_drift_table_count_unchanged():
    """The mutations only touch columns, not tables — v1 and v2 should have
    the same table count."""
    session = open_readonly_session()
    try:
        report = survey_drift(session, DEFAULT_REPO_ID)
        assert report.v1_table_count == report.v2_table_count
        assert len(report.diff.added_tables) == 0
        assert len(report.diff.removed_tables) == 0
    finally:
        session.close()
