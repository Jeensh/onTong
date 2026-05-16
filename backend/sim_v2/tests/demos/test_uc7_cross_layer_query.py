"""UC7 — Cross-layer reasoning demo verification — W31.3.

Validates the 5-layer ontology's cross-layer query API end-to-end:
  - Code Layer (CodeTypeRow + CodeFieldRow) populated
  - Schema Layer (SchemaTableRow + SchemaColumnRow) populated
  - Domain Layer (BusinessTermRow) populated
  - Mapping rows (SchemaCodeMappingRow + SchemaDomainMappingRow) connect them
  - All 4 query directions return expected hits
  - RepoCoverage stats match the seeded data
"""
from __future__ import annotations

import pytest

from backend.modeling.code_layer.orm import CodeFieldRow, CodeTypeRow
from backend.modeling.domain_layer.orm import BusinessTermRow
from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaCodeMappingRow,
    SchemaColumnRow,
    SchemaDomainMappingRow,
    SchemaTableRow,
)
from backend.sim_v2.demos.uc7_cross_layer_query.run import (
    REPO_ID,
    build_session,
    main,
    populate_all_layers,
    run_uc4_queries,
)


@pytest.fixture
def queries():
    session = build_session()
    populate_all_layers(session)
    yield run_uc4_queries(session), session
    session.close()


def test_demo_main_returns_zero():
    """The W31 demo main() exits 0 — cross-layer reasoning works."""
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Population — verify each layer + mappings present
# ─────────────────────────────────────────────────────────────────────────────


def test_code_layer_populated(queries):
    _, session = queries
    assert session.query(CodeTypeRow).filter_by(repo_id=REPO_ID).count() == 2
    assert session.query(CodeFieldRow).count() == 7


def test_schema_layer_populated(queries):
    _, session = queries
    assert session.query(SchemaTableRow).filter_by(repo_id=REPO_ID).count() == 2
    assert session.query(SchemaColumnRow).filter_by(repo_id=REPO_ID).count() == 7


def test_domain_layer_populated(queries):
    _, session = queries
    assert session.query(BusinessTermRow).filter_by(repo_id=REPO_ID).count() == 5


def test_mapping_rows_populated(queries):
    _, session = queries
    assert session.query(SchemaCodeMappingRow).filter_by(repo_id=REPO_ID).count() == 5
    assert session.query(SchemaDomainMappingRow).filter_by(repo_id=REPO_ID).count() == 5


# ─────────────────────────────────────────────────────────────────────────────
# Q1: Domain → Schema
# ─────────────────────────────────────────────────────────────────────────────


def test_q1_term_balance_resolves_to_one_column(queries):
    results, _ = queries
    hits = results["term_to_columns_balance"]
    assert len(hits) == 1
    assert hits[0].column_fqn == "public.account.balance"
    assert hits[0].table_fqn  == "public.account"
    assert hits[0].confirmed is True


def test_q1_confirmed_only_filter_preserves_confirmed_hit(queries):
    results, _ = queries
    assert len(results["term_to_columns_balance_confirmed"]) == 1
    assert results["term_to_columns_balance_confirmed"][0].confirmed is True


# ─────────────────────────────────────────────────────────────────────────────
# Q2: Schema → Domain (column-level + table-level)
# ─────────────────────────────────────────────────────────────────────────────


def test_q2_email_addr_resolves_to_column_and_table_term(queries):
    """email_addr column itself maps to `banking.account.email` (unconfirmed),
    AND its table maps to `banking.account` (confirmed)."""
    results, _ = queries
    hits = results["column_to_terms_email_addr"]
    term_fqns = {h.business_term_fqn for h in hits}
    assert "banking.account.email" in term_fqns
    assert "banking.account"       in term_fqns
    # One confirmed (table-level), one unconfirmed (column-level)
    assert sum(1 for h in hits if h.confirmed)     == 1
    assert sum(1 for h in hits if not h.confirmed) == 1


def test_q2_transaction_amount_resolves_to_two_terms(queries):
    """amount column → its own term AND the table's term (column + table mapping)."""
    results, _ = queries
    hits = results["column_to_terms_amount"]
    term_fqns = {h.business_term_fqn for h in hits}
    assert term_fqns == {"banking.transaction.amount", "banking.transaction"}


# ─────────────────────────────────────────────────────────────────────────────
# Q3: Code → Schema
# ─────────────────────────────────────────────────────────────────────────────


def test_q3_account_class_resolves_to_account_table_and_columns(queries):
    results, _ = queries
    hits = results["code_to_schema_account"]
    # 1 table-level + 2 column-level mappings (balance + email_addr)
    assert any(h.schema_table_fqn == "public.account" for h in hits)
    column_fqns = {h.schema_column_fqn for h in hits if h.schema_column_fqn}
    assert "public.account.balance"    in column_fqns
    assert "public.account.email_addr" in column_fqns


# ─────────────────────────────────────────────────────────────────────────────
# Q4: Schema → Code
# ─────────────────────────────────────────────────────────────────────────────


def test_q4_transaction_table_resolves_to_transaction_class(queries):
    results, _ = queries
    hits = results["schema_to_code_transaction"]
    code_types = {h.code_type_fqn for h in hits if h.code_type_fqn}
    assert "com.bank.Transaction" in code_types


# ─────────────────────────────────────────────────────────────────────────────
# Q5: Coverage stats
# ─────────────────────────────────────────────────────────────────────────────


def test_q5_coverage_table_and_column_counts(queries):
    results, _ = queries
    cov = results["coverage"]
    assert cov.table_count == 2
    assert cov.column_count == 7


def test_q5_coverage_distinguishes_confirmed_and_unconfirmed(queries):
    results, _ = queries
    cov = results["coverage"]
    # 3 columns have domain mappings; 2 are confirmed (balance + amount), 1 is auto (email_addr)
    assert cov.domain_mapped_columns == 3
    assert cov.confirmed_domain_mappings == 2
    # 3 columns have code mappings (balance + email_addr + transaction.amount), all confirmed
    assert cov.code_mapped_columns == 3
    assert cov.confirmed_code_mappings == 3


# ─────────────────────────────────────────────────────────────────────────────
# Catalog scan
# ─────────────────────────────────────────────────────────────────────────────


def test_schema_tables_in_repo_returns_two_tables(queries):
    results, _ = queries
    tables = results["all_tables"]
    fqns = {t.fqn for t in tables}
    assert fqns == {"public.account", "public.transaction"}


# ─────────────────────────────────────────────────────────────────────────────
# UC4 capability marker
# ─────────────────────────────────────────────────────────────────────────────


def test_uc4_capability_marker():
    """UC4 (스키마 추천) cross-layer reasoning is end-to-end."""
    assert main() == 0
