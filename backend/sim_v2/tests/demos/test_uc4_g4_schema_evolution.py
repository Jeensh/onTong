"""UC4 G4 schema evolution demo verification — W25.3.

Validates ADR-004 Schema Layer evolution:
  - Baseline JPA extraction → ORM rows
  - Additive forward DDL preserves baseline (R3 + R4)
  - SchemaMigrationRow records each migration application
  - Rollback reverses cleanly + records rollback row
  - schema_change proposal flows through MERGED with revision lineage
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaColumnRow,
    SchemaConstraintRow,
    SchemaMigrationRow,
    SchemaTableRow,
)
from backend.sim_v2.demos.uc4_g4_schema_evolution.run import (
    BANKING_BASELINE_JPA,
    FIXTURES,
    REPO_ID,
    SCHEMA_DIFF_V1_TO_V2,
    SchemaVerificationEngine,
    apply_backward,
    apply_forward,
    baseline_columns,
    build_ontology_session,
    main,
    run_schema_evolution,
    seed_baseline_schema,
    table_exists,
)


def test_demo_main_returns_zero():
    """The W25 demo main() exits 0 — full schema evolution arc passes."""
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Baseline extraction
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_session():
    session = build_ontology_session()
    seed_baseline_schema(session)
    yield session
    session.close()


def test_baseline_has_two_tables(seeded_session):
    tables = seeded_session.query(SchemaTableRow).filter_by(repo_id=REPO_ID).all()
    fqns = {t.fqn for t in tables}
    assert fqns == {"public.account", "public.transaction"}


def test_baseline_account_columns(seeded_session):
    assert baseline_columns(seeded_session, "public.account") == ["id", "name", "balance", "status"]


def test_baseline_transaction_columns(seeded_session):
    assert baseline_columns(seeded_session, "public.transaction") == ["id", "account_id", "amount", "type"]


def test_baseline_pk_constraints_present(seeded_session):
    pks = seeded_session.query(SchemaConstraintRow).filter_by(kind="PK", repo_id=REPO_ID).all()
    assert {c.table_fqn for c in pks} == {"public.account", "public.transaction"}


def test_baseline_fk_constraint_present(seeded_session):
    fks = seeded_session.query(SchemaConstraintRow).filter_by(kind="FK", repo_id=REPO_ID).all()
    assert len(fks) == 1
    assert fks[0].constraint_name == "fk_transaction_account"
    assert fks[0].referenced_table_fqn == "public.account"


def test_baseline_migration_recorded(seeded_session):
    rows = seeded_session.query(SchemaMigrationRow).filter_by(repo_id=REPO_ID).all()
    assert len(rows) == 1
    assert rows[0].version == "v1_initial"


# ─────────────────────────────────────────────────────────────────────────────
# Forward migration (additive)
# ─────────────────────────────────────────────────────────────────────────────


def test_forward_adds_updated_at_column(seeded_session):
    apply_forward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    cols = baseline_columns(seeded_session, "public.account")
    assert "updated_at" in cols
    # Existing columns preserved (R3)
    for baseline_col in ["id", "name", "balance", "status"]:
        assert baseline_col in cols


def test_forward_creates_audit_log_table(seeded_session):
    apply_forward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    assert table_exists(seeded_session, "public.audit_log")
    audit_cols = baseline_columns(seeded_session, "public.audit_log")
    assert audit_cols == ["id", "account_id", "event_type", "occurred_at"]


def test_forward_records_migration_row(seeded_session):
    apply_forward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    v2 = seeded_session.query(SchemaMigrationRow).filter_by(
        version="v2_add_audit", repo_id=REPO_ID,
    ).first()
    assert v2 is not None
    assert v2.rollback_sql is not None
    assert "DROP TABLE audit_log" in v2.rollback_sql


def test_forward_preserves_existing_pk_constraint(seeded_session):
    apply_forward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    account_pks = (
        seeded_session.query(SchemaConstraintRow)
        .filter_by(table_fqn="public.account", kind="PK", repo_id=REPO_ID)
        .all()
    )
    assert len(account_pks) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Rollback (backward DDL)
# ─────────────────────────────────────────────────────────────────────────────


def test_rollback_removes_added_column(seeded_session):
    apply_forward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    apply_backward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    assert "updated_at" not in baseline_columns(seeded_session, "public.account")


def test_rollback_drops_audit_table(seeded_session):
    apply_forward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    apply_backward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    assert not table_exists(seeded_session, "public.audit_log")


def test_rollback_records_audit_migration(seeded_session):
    apply_forward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    apply_backward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    rollback_rows = (
        seeded_session.query(SchemaMigrationRow)
        .filter(SchemaMigrationRow.version.endswith("_rollback"))
        .all()
    )
    assert len(rollback_rows) == 1
    assert "v2_add_audit_rollback" == rollback_rows[0].version


def test_rollback_preserves_baseline_tables(seeded_session):
    """After rollback the baseline tables (account, transaction) must remain intact."""
    apply_forward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    apply_backward(seeded_session, SCHEMA_DIFF_V1_TO_V2)
    assert table_exists(seeded_session, "public.account")
    assert table_exists(seeded_session, "public.transaction")
    assert baseline_columns(seeded_session, "public.account") == ["id", "name", "balance", "status"]


# ─────────────────────────────────────────────────────────────────────────────
# Oracle (R3 + R4) — SchemaVerificationEngine
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def loop_result():
    return run_schema_evolution()


def test_oracle_aggregate_status_pass(loop_result):
    assert loop_result["oracle_result"].aggregate_status == "PASS"


def test_oracle_each_fixture_pass(loop_result):
    fixtures = loop_result["oracle_result"].by_fixture
    for fid in FIXTURES:
        assert fixtures[fid].status == "PASS", f"{fid} not PASS"


def test_oracle_r4_table_count_monotone(loop_result):
    """R4 fixture: table count after migration must be >= baseline."""
    f = loop_result["oracle_result"].by_fixture["R4_table_count_monotone"]
    baseline_n = f.java_baseline_output["table_count"]
    current_n  = f.python_proposal_output["table_count"]
    assert current_n >= baseline_n
    assert current_n == baseline_n + 1  # exactly 1 table added (audit_log)


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle reaches MERGED
# ─────────────────────────────────────────────────────────────────────────────


def test_lifecycle_reaches_merged(loop_result):
    assert loop_result["final_proposal"].state == "MERGED"
    assert loop_result["revision_id"] is not None


def test_revision_records_schema_version(loop_result):
    integrator = loop_result["integrator"]
    revision = integrator.revision_store.get(loop_result["revision_id"])
    assert revision is not None
    assert revision.schema_revision == SCHEMA_DIFF_V1_TO_V2["migration_version"]


def test_lifecycle_history_transitions(loop_result):
    transitions = [(e.from_state, e.to_state) for e in loop_result["final_proposal"].history]
    assert transitions == [
        ("DRAFT",    "PROPOSED"),
        ("PROPOSED", "ORACLED"),
        ("ORACLED",  "REVIEWED"),
        ("REVIEWED", "ACCEPTED"),
        ("ACCEPTED", "MERGED"),
    ]


def test_rollback_actually_reduces_table_count(loop_result):
    assert loop_result["table_count_after_forward"] == 3
    assert loop_result["table_count_after_rollback"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# G4 gate marker
# ─────────────────────────────────────────────────────────────────────────────


def test_g4_gate_schema_evolution_covered():
    """G4 gate — Schema Layer evolution (ADR-004) active end-to-end."""
    assert main() == 0
