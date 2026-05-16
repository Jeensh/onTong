"""UC7 — Cross-layer reasoning demo (W31, UC4 scenario from ADR-004 §3.3).

Demonstrates the 5-layer ontology's *cross-layer query* capability — the
"feature X 추가하려면 어떤 schema 변경이 필요?" reasoning that ADR-004 calls out
as the value proposition of stacking Code / Schema / Domain layers.

Banking ontology populated with:
  - Code Layer: CodeTypeRow + CodeFieldRow for Account/Transaction entities
  - Schema Layer: tables + columns for account/transaction
  - Domain Layer: BusinessTermRow for banking domain terms
  - Mapping rows: Schema↔Code + Schema↔Domain

Then 5 realistic queries:
  Q1  term → column   : "Where does `banking.account.balance` live?"
  Q2  column → term   : "What domain meaning does `account.email_addr` carry?"
  Q3  code → schema   : "What schema does `com.bank.Account` map to?"
  Q4  schema → code   : "What Java entity backs `public.transaction`?"
  Q5  coverage stats  : "How well-mapped is the banking ontology?"

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc7_cross_layer_query.run
"""
from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.code_layer.orm import CodeFieldRow, CodeTypeRow
from backend.modeling.domain_layer.orm import BusinessTermRow
from backend.modeling.persistence.database import Base
from backend.sim_v2.core.ontology.query import (
    find_business_terms_for_schema_column,
    find_code_types_for_schema_table,
    find_schema_columns_for_business_term,
    find_schema_tables_for_code_type,
    schema_coverage_for_repo,
    schema_tables_in_repo,
)
from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaCodeMappingRow,
    SchemaColumnRow,
    SchemaDomainMappingRow,
    SchemaTableRow,
)


REPO_ID = "banking"


# ─────────────────────────────────────────────────────────────────────────────
# Ontology population
# ─────────────────────────────────────────────────────────────────────────────


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        # Code Layer
        CodeTypeRow.__table__,
        CodeFieldRow.__table__,
        # Schema Layer
        SchemaTableRow.__table__,
        SchemaColumnRow.__table__,
        SchemaCodeMappingRow.__table__,
        SchemaDomainMappingRow.__table__,
        # Domain Layer
        BusinessTermRow.__table__,
    ])
    return Session(engine)


def seed_code_layer(session: Session) -> None:
    """Java entities: Account, Transaction."""
    session.add_all([
        CodeTypeRow(
            fqn="com.bank.Account", simple_name="Account",
            package="com.bank", kind="CLASS", role="entity", repo_id=REPO_ID,
        ),
        CodeTypeRow(
            fqn="com.bank.Transaction", simple_name="Transaction",
            package="com.bank", kind="CLASS", role="entity", repo_id=REPO_ID,
        ),
        # Account fields (CodeFieldRow has no repo_id — links to CodeTypeRow via type_fqn)
        CodeFieldRow(type_fqn="com.bank.Account", name="id",        type="java.lang.Long"),
        CodeFieldRow(type_fqn="com.bank.Account", name="balance",   type="java.math.BigDecimal"),
        CodeFieldRow(type_fqn="com.bank.Account", name="emailAddr", type="java.lang.String"),
        CodeFieldRow(type_fqn="com.bank.Account", name="status",    type="java.lang.String"),
        # Transaction fields
        CodeFieldRow(type_fqn="com.bank.Transaction", name="id",        type="java.lang.Long"),
        CodeFieldRow(type_fqn="com.bank.Transaction", name="accountId", type="java.lang.Long"),
        CodeFieldRow(type_fqn="com.bank.Transaction", name="amount",    type="java.math.BigDecimal"),
    ])


def seed_schema_layer(session: Session) -> None:
    session.add_all([
        SchemaTableRow(fqn="public.account",     table_name="account",     repo_id=REPO_ID),
        SchemaTableRow(fqn="public.transaction", table_name="transaction", repo_id=REPO_ID),
        # account columns
        SchemaColumnRow(
            fqn="public.account.id",         table_fqn="public.account",
            column_name="id", data_type="BIGINT", nullable=False, position=0, repo_id=REPO_ID,
        ),
        SchemaColumnRow(
            fqn="public.account.balance",    table_fqn="public.account",
            column_name="balance", data_type="NUMERIC(15,2)", nullable=False, position=1, repo_id=REPO_ID,
        ),
        SchemaColumnRow(
            fqn="public.account.email_addr", table_fqn="public.account",
            column_name="email_addr", data_type="VARCHAR(200)", nullable=False, position=2, repo_id=REPO_ID,
        ),
        SchemaColumnRow(
            fqn="public.account.status",     table_fqn="public.account",
            column_name="status", data_type="VARCHAR(20)", nullable=False, position=3, repo_id=REPO_ID,
        ),
        # transaction columns
        SchemaColumnRow(
            fqn="public.transaction.id",         table_fqn="public.transaction",
            column_name="id", data_type="BIGINT", nullable=False, position=0, repo_id=REPO_ID,
        ),
        SchemaColumnRow(
            fqn="public.transaction.account_id", table_fqn="public.transaction",
            column_name="account_id", data_type="BIGINT", nullable=False, position=1, repo_id=REPO_ID,
        ),
        SchemaColumnRow(
            fqn="public.transaction.amount",     table_fqn="public.transaction",
            column_name="amount", data_type="NUMERIC(15,2)", nullable=False, position=2, repo_id=REPO_ID,
        ),
    ])


def seed_domain_layer(session: Session) -> None:
    session.add_all([
        BusinessTermRow(
            fqn="banking.account",         label="Account",           domain="banking",
            kind="entity", is_root_entity=True, confirmed=True, repo_id=REPO_ID,
        ),
        BusinessTermRow(
            fqn="banking.account.balance", label="Account Balance",   domain="banking",
            kind="atomic", value_type="java.math.BigDecimal", unit="USD", confirmed=True, repo_id=REPO_ID,
        ),
        BusinessTermRow(
            fqn="banking.account.email",   label="Customer Email",    domain="banking",
            kind="atomic", value_type="java.lang.String", confirmed=False, repo_id=REPO_ID,
        ),
        BusinessTermRow(
            fqn="banking.transaction",     label="Transaction",       domain="banking",
            kind="entity", is_root_entity=True, confirmed=True, repo_id=REPO_ID,
        ),
        BusinessTermRow(
            fqn="banking.transaction.amount", label="Transaction Amount", domain="banking",
            kind="atomic", value_type="java.math.BigDecimal", unit="USD", confirmed=True, repo_id=REPO_ID,
        ),
    ])


def seed_mappings(session: Session) -> None:
    """Connect the 3 layers via mapping rows."""
    session.add_all([
        # Code ↔ Schema: Account class ↔ account table
        SchemaCodeMappingRow(
            schema_table_fqn="public.account", code_type_fqn="com.bank.Account",
            mapping_kind="entity", confidence=1.0, confirmed=True,
            source="jpa_annotation", repo_id=REPO_ID,
        ),
        SchemaCodeMappingRow(
            schema_column_fqn="public.account.balance",
            code_type_fqn="com.bank.Account",  # also record parent class so Code→Schema query catches it
            code_field_fqn="com.bank.Account#balance",
            mapping_kind="entity", confidence=1.0, confirmed=True,
            source="jpa_annotation", repo_id=REPO_ID,
        ),
        SchemaCodeMappingRow(
            schema_column_fqn="public.account.email_addr",
            code_type_fqn="com.bank.Account",
            code_field_fqn="com.bank.Account#emailAddr",
            mapping_kind="entity", confidence=0.92, confirmed=True,
            source="name_match", repo_id=REPO_ID,
        ),
        # Code ↔ Schema: Transaction class ↔ transaction table
        SchemaCodeMappingRow(
            schema_table_fqn="public.transaction", code_type_fqn="com.bank.Transaction",
            mapping_kind="entity", confidence=1.0, confirmed=True,
            source="jpa_annotation", repo_id=REPO_ID,
        ),
        SchemaCodeMappingRow(
            schema_column_fqn="public.transaction.amount",
            code_type_fqn="com.bank.Transaction",
            code_field_fqn="com.bank.Transaction#amount",
            mapping_kind="entity", confidence=1.0, confirmed=True,
            source="jpa_annotation", repo_id=REPO_ID,
        ),
        # Schema ↔ Domain: confirmed terms
        SchemaDomainMappingRow(
            schema_table_fqn="public.account", business_term_fqn="banking.account",
            confidence=1.0, confirmed=True, source="user", repo_id=REPO_ID,
        ),
        SchemaDomainMappingRow(
            schema_column_fqn="public.account.balance", business_term_fqn="banking.account.balance",
            confidence=0.95, confirmed=True, source="name_match", repo_id=REPO_ID,
        ),
        # Schema ↔ Domain: low-confidence (auto, unconfirmed)
        SchemaDomainMappingRow(
            schema_column_fqn="public.account.email_addr", business_term_fqn="banking.account.email",
            confidence=0.7, confirmed=False, source="auto", repo_id=REPO_ID,
        ),
        SchemaDomainMappingRow(
            schema_table_fqn="public.transaction", business_term_fqn="banking.transaction",
            confidence=1.0, confirmed=True, source="user", repo_id=REPO_ID,
        ),
        SchemaDomainMappingRow(
            schema_column_fqn="public.transaction.amount", business_term_fqn="banking.transaction.amount",
            confidence=0.98, confirmed=True, source="name_match", repo_id=REPO_ID,
        ),
    ])


def populate_all_layers(session: Session) -> None:
    seed_code_layer(session)
    seed_schema_layer(session)
    seed_domain_layer(session)
    seed_mappings(session)
    session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# UC4 queries — wrapper that returns structured results
# ─────────────────────────────────────────────────────────────────────────────


def run_uc4_queries(session: Session) -> dict[str, Any]:
    return {
        # Q1: term → schema columns (UC4 핵심)
        "term_to_columns_balance":
            find_schema_columns_for_business_term(session, "banking.account.balance", REPO_ID),
        "term_to_columns_balance_confirmed":
            find_schema_columns_for_business_term(session, "banking.account.balance", REPO_ID, confirmed_only=True),
        # Q2: column → terms (reverse)
        "column_to_terms_email_addr":
            find_business_terms_for_schema_column(session, "public.account.email_addr", REPO_ID),
        "column_to_terms_amount":
            find_business_terms_for_schema_column(session, "public.transaction.amount", REPO_ID),
        # Q3: code → schema
        "code_to_schema_account":
            find_schema_tables_for_code_type(session, "com.bank.Account", REPO_ID),
        # Q4: schema → code
        "schema_to_code_transaction":
            find_code_types_for_schema_table(session, "public.transaction", REPO_ID),
        # Q5: coverage stats
        "coverage": schema_coverage_for_repo(session, REPO_ID),
        # bonus: catalog scan
        "all_tables": schema_tables_in_repo(session, REPO_ID),
    }


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────


def _banner(title: str) -> None:
    print("─" * 78)
    print(title)
    print("─" * 78)


def main() -> int:
    print("=" * 78)
    print("UC7 — Cross-layer reasoning demo (W31, UC4 from ADR-004 §3.3)")
    print("=" * 78)
    print()

    session = build_session()
    populate_all_layers(session)
    results = run_uc4_queries(session)

    _banner("Populated 5-layer ontology")
    print(f"  Code   : {session.query(CodeTypeRow).filter_by(repo_id=REPO_ID).count()} types, "
          f"{session.query(CodeFieldRow).count()} fields")
    print(f"  Schema : {session.query(SchemaTableRow).filter_by(repo_id=REPO_ID).count()} tables, "
          f"{session.query(SchemaColumnRow).filter_by(repo_id=REPO_ID).count()} columns")
    print(f"  Domain : {session.query(BusinessTermRow).filter_by(repo_id=REPO_ID).count()} business terms")
    print(f"  Maps   : {session.query(SchemaCodeMappingRow).filter_by(repo_id=REPO_ID).count()} schema↔code, "
          f"{session.query(SchemaDomainMappingRow).filter_by(repo_id=REPO_ID).count()} schema↔domain")
    print()

    _banner("Q1  Domain → Schema   `banking.account.balance` → ?")
    for h in results["term_to_columns_balance"]:
        print(f"  table={h.table_fqn:<20} column={h.column_fqn:<32} "
              f"confidence={h.confidence} confirmed={h.confirmed} source={h.source}")
    print(f"  (confirmed-only filter yields {len(results['term_to_columns_balance_confirmed'])} hit(s))")
    print()

    _banner("Q2  Schema → Domain   `public.account.email_addr` → ?")
    for h in results["column_to_terms_email_addr"]:
        print(f"  term={h.business_term_fqn:<40} confidence={h.confidence} confirmed={h.confirmed}")
    print()

    _banner("Q2'  Schema → Domain   `public.transaction.amount` → ? (via column-AND-table-level)")
    for h in results["column_to_terms_amount"]:
        print(f"  term={h.business_term_fqn:<40} confidence={h.confidence} confirmed={h.confirmed}")
    print()

    _banner("Q3  Code → Schema   `com.bank.Account` class → ?")
    for h in results["code_to_schema_account"]:
        print(f"  table={h.schema_table_fqn or '-':<20} column={h.schema_column_fqn or '-':<32} "
              f"kind={h.mapping_kind}")
    print()

    _banner("Q4  Schema → Code   `public.transaction` table → ?")
    for h in results["schema_to_code_transaction"]:
        print(f"  code_type={h.code_type_fqn or '-':<30} field={h.code_field_fqn or '-':<40}")
    print()

    _banner("Q5  Repo coverage (RepoCoverage)")
    cov = results["coverage"]
    print(f"  table_count             : {cov.table_count}")
    print(f"  column_count            : {cov.column_count}")
    print(f"  domain-mapped columns   : {cov.domain_mapped_columns}  "
          f"(confirmed: {cov.confirmed_domain_mappings})")
    print(f"  code-mapped columns     : {cov.code_mapped_columns}  "
          f"(confirmed: {cov.confirmed_code_mappings})")
    print()

    # Validity expectations
    success = (
        len(results["term_to_columns_balance"]) >= 1
        and len(results["term_to_columns_balance_confirmed"]) >= 1
        and len(results["column_to_terms_email_addr"]) >= 1
        and len(results["column_to_terms_amount"]) >= 2   # column-level + table-level
        and len(results["code_to_schema_account"]) >= 1
        and len(results["schema_to_code_transaction"]) >= 1
        and cov.table_count == 2
        and cov.code_mapped_columns >= 3
    )
    if success:
        print("✓ Final verdict: PASS — cross-layer reasoning works across all 5 layers")
        print("  UC4 capability: 'feature X 추가하려면 어떤 schema 변경?' enabled by domain-to-schema query")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
