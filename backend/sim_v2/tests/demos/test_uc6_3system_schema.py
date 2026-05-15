"""UC6 — 3-system schema evolution verification — W29.3.

Validates that the W25 Schema Layer pattern works *identically* across all 3
plugin systems (banking, v2-slab-design, broadleaf) through a single Integrator
with `repo_id` isolation.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaColumnRow,
    SchemaMigrationRow,
    SchemaTableRow,
)
from backend.sim_v2.demos.uc6_3system_schema.run import (
    BROADLEAF_BASELINE_JPA,
    BROADLEAF_DIFF,
    BROADLEAF_REPO_ID,
    SYSTEMS,
    V2_BASELINE_JPA,
    V2_DIFF,
    V2_REPO_ID,
    main,
    run_3system_schema_evolution,
)


@pytest.fixture
def evo():
    return run_3system_schema_evolution()


# ─────────────────────────────────────────────────────────────────────────────
# Demo entry-point
# ─────────────────────────────────────────────────────────────────────────────


def test_demo_main_returns_zero():
    """The W29 demo main() exits 0 — 3-system schema evolution passes."""
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Per-system MERGED + oracle PASS
# ─────────────────────────────────────────────────────────────────────────────


def test_all_three_systems_merged(evo):
    for s in evo["systems"]:
        assert s["proposal"].state == "MERGED", f"{s['system']} not MERGED"
        assert s["rev_id"] is not None, f"{s['system']} missing revision"


def test_all_three_systems_oracle_pass(evo):
    for s in evo["systems"]:
        assert s["oracle"].aggregate_status == "PASS", f"{s['system']} oracle != PASS"


def test_each_system_three_fixtures_pass(evo):
    """Each system has 2 R3 fixtures (one per baseline table) + 1 R4."""
    for s in evo["systems"]:
        fixtures = s["oracle"].by_fixture
        assert len(fixtures) == 3
        for r in fixtures.values():
            assert r.status == "PASS"


# ─────────────────────────────────────────────────────────────────────────────
# repo_id isolation — each system's tables live under its own repo_id
# ─────────────────────────────────────────────────────────────────────────────


def test_each_repo_has_three_tables(evo):
    """Baseline = 2 tables, additive = +1 table = 3 per repo."""
    session = evo["session"]
    for s in evo["systems"]:
        n = session.query(SchemaTableRow).filter_by(repo_id=s["repo_id"]).count()
        assert n == 3, f"{s['system']} expected 3 tables, got {n}"


def test_baseline_tables_unique_per_repo(evo):
    """Cross-repo table names must NOT collide (each system has its own naming)."""
    session = evo["session"]
    banking_fqns = {r.fqn for r in session.query(SchemaTableRow).filter_by(repo_id="banking").all()}
    v2_fqns      = {r.fqn for r in session.query(SchemaTableRow).filter_by(repo_id=V2_REPO_ID).all()}
    bl_fqns      = {r.fqn for r in session.query(SchemaTableRow).filter_by(repo_id=BROADLEAF_REPO_ID).all()}
    # No overlap between any pair
    assert banking_fqns.isdisjoint(v2_fqns)
    assert banking_fqns.isdisjoint(bl_fqns)
    assert v2_fqns.isdisjoint(bl_fqns)


def test_per_repo_migration_count(evo):
    """Each system records 2 SchemaMigrationRow entries (baseline + v2)."""
    session = evo["session"]
    for s in evo["systems"]:
        n = session.query(SchemaMigrationRow).filter_by(repo_id=s["repo_id"]).count()
        assert n == 2, f"{s['system']} expected 2 migration rows, got {n}"


# ─────────────────────────────────────────────────────────────────────────────
# Single Integrator + revision store contains all three
# ─────────────────────────────────────────────────────────────────────────────


def test_single_integrator_carries_three_proposals(evo):
    integrator = evo["integrator"]
    merged = integrator.list_proposals(state="MERGED")
    assert len(merged) == 3
    plugins = {p.plugin for p in merged}
    assert plugins == {"banking", V2_REPO_ID, BROADLEAF_REPO_ID}


def test_revision_store_has_three_revisions(evo):
    integrator = evo["integrator"]
    assert integrator.revision_store.count() == 3
    for s in evo["systems"]:
        rev = integrator.revision_store.get(s["rev_id"])
        assert rev is not None
        assert rev.schema_revision == s["proposal"].schema_diff["migration_version"]


# ─────────────────────────────────────────────────────────────────────────────
# Per-system added artifacts present in ontology
# ─────────────────────────────────────────────────────────────────────────────


def test_banking_audit_log_table_present(evo):
    session = evo["session"]
    row = session.get(SchemaTableRow, ("public.audit_log", "banking"))
    assert row is not None


def test_v2_slab_revision_log_table_present(evo):
    session = evo["session"]
    row = session.get(SchemaTableRow, ("public.slab_revision_log", V2_REPO_ID))
    assert row is not None


def test_broadleaf_product_change_log_table_present(evo):
    session = evo["session"]
    row = session.get(SchemaTableRow, ("public.blc_product_change_log", BROADLEAF_REPO_ID))
    assert row is not None


def test_banking_account_gets_updated_at_column(evo):
    session = evo["session"]
    row = session.get(SchemaColumnRow, ("public.account.updated_at", "banking"))
    assert row is not None
    assert row.data_type == "TIMESTAMP"


def test_v2_slab_gets_version_no_column(evo):
    session = evo["session"]
    row = session.get(SchemaColumnRow, ("public.slab.version_no", V2_REPO_ID))
    assert row is not None
    assert row.data_type == "INT"
    assert row.nullable is False


def test_broadleaf_product_gets_last_modified_column(evo):
    session = evo["session"]
    row = session.get(SchemaColumnRow, ("public.blc_product.last_modified", BROADLEAF_REPO_ID))
    assert row is not None
    assert row.data_type == "TIMESTAMP"


# ─────────────────────────────────────────────────────────────────────────────
# 3-system parity marker
# ─────────────────────────────────────────────────────────────────────────────


def test_3system_parity_validated():
    """Schema Layer (ADR-004) works identically across all 3 plugin systems."""
    assert main() == 0


def test_system_manifest_has_three_entries():
    """SYSTEMS module-level constant is the authoritative list."""
    assert len(SYSTEMS) == 3
    assert {s["name"] for s in SYSTEMS} == {"banking", "v2-slab-design", "broadleaf"}
