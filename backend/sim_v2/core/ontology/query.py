"""Cross-layer ontology query API — implementation-plan §3.1 B1.4.

5-layer ontology (Code / Domain / Mapping / Simulation / Schema) 간 cross-layer query.
UC4 (스키마 추천) 의 enabler — spec.md §3.3 의 sample query.

Public API (모두 session 인자 받음 — caller 가 transaction 관리):
    - find_schema_columns_for_business_term(session, term_fqn, repo_id)
    - find_business_terms_for_schema_column(session, column_fqn, repo_id)
    - find_schema_tables_for_code_type(session, type_fqn, repo_id)
    - find_code_types_for_schema_table(session, table_fqn, repo_id)
    - schema_tables_in_repo(session, repo_id)
    - schema_coverage_for_repo(session, repo_id) — coverage stats
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaCodeMappingRow,
    SchemaColumnRow,
    SchemaDomainMappingRow,
    SchemaTableRow,
)


# ─────────────────────────────────────────────────────────────────────────────
# Result wrappers
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SchemaTermHit:
    """Domain term ↔ schema column/table 매핑 결과."""
    table_fqn:         str
    column_fqn:        str | None     # column-level 매핑 시
    business_term_fqn: str
    confidence:        float
    confirmed:         bool
    source:            str


@dataclass(frozen=True)
class SchemaCodeHit:
    """Code class ↔ schema table/column 매핑 결과."""
    schema_table_fqn:  str | None
    schema_column_fqn: str | None
    code_type_fqn:     str | None
    code_field_fqn:    str | None
    code_method_fqn:   str | None
    mapping_kind:      str
    confidence:        float
    confirmed:         bool


@dataclass(frozen=True)
class RepoCoverage:
    table_count:                int
    column_count:               int
    domain_mapped_columns:      int
    code_mapped_columns:        int
    confirmed_domain_mappings:  int
    confirmed_code_mappings:    int


# ─────────────────────────────────────────────────────────────────────────────
# Domain ↔ Schema (UC4 핵심)
# ─────────────────────────────────────────────────────────────────────────────


def find_schema_columns_for_business_term(
    session: Session,
    term_fqn: str,
    repo_id: str,
    *,
    confirmed_only: bool = False,
) -> list[SchemaTermHit]:
    """spec.md §3.3 의 sample query 의 정식 구현.

    Given a BusinessTerm fqn, find schema tables/columns mapped to it.
    UC4 의 "feature X 추가하려면 어떤 schema 변경?" — `term=feature_X` 의 입력.
    """
    stmt = select(SchemaDomainMappingRow).where(
        SchemaDomainMappingRow.business_term_fqn == term_fqn,
        SchemaDomainMappingRow.repo_id == repo_id,
    )
    if confirmed_only:
        stmt = stmt.where(SchemaDomainMappingRow.confirmed.is_(True))

    rows = session.execute(stmt).scalars().all()

    hits: list[SchemaTermHit] = []
    for row in rows:
        table_fqn = row.schema_table_fqn
        # column-level 매핑이면 table_fqn 을 column 의 parent 에서 derive
        if table_fqn is None and row.schema_column_fqn is not None:
            col = session.execute(
                select(SchemaColumnRow).where(
                    SchemaColumnRow.fqn == row.schema_column_fqn,
                    SchemaColumnRow.repo_id == repo_id,
                )
            ).scalar_one_or_none()
            if col is not None:
                table_fqn = col.table_fqn

        hits.append(SchemaTermHit(
            table_fqn=table_fqn or "",
            column_fqn=row.schema_column_fqn,
            business_term_fqn=row.business_term_fqn,
            confidence=row.confidence,
            confirmed=row.confirmed,
            source=row.source,
        ))
    return hits


def find_business_terms_for_schema_column(
    session: Session,
    column_fqn: str,
    repo_id: str,
    *,
    confirmed_only: bool = False,
) -> list[SchemaTermHit]:
    """Reverse — given a schema column, find mapped BusinessTerms.

    column-level 또는 그 column 의 table-level 매핑 모두 포함.
    """
    # 우선 column-level mapping
    stmt = select(SchemaDomainMappingRow).where(
        SchemaDomainMappingRow.schema_column_fqn == column_fqn,
        SchemaDomainMappingRow.repo_id == repo_id,
    )
    if confirmed_only:
        stmt = stmt.where(SchemaDomainMappingRow.confirmed.is_(True))
    column_rows = session.execute(stmt).scalars().all()

    # table-level mapping (column 의 table_fqn)
    col = session.execute(
        select(SchemaColumnRow).where(
            SchemaColumnRow.fqn == column_fqn,
            SchemaColumnRow.repo_id == repo_id,
        )
    ).scalar_one_or_none()
    table_rows: list[SchemaDomainMappingRow] = []
    if col is not None:
        t_stmt = select(SchemaDomainMappingRow).where(
            SchemaDomainMappingRow.schema_table_fqn == col.table_fqn,
            SchemaDomainMappingRow.schema_column_fqn.is_(None),
            SchemaDomainMappingRow.repo_id == repo_id,
        )
        if confirmed_only:
            t_stmt = t_stmt.where(SchemaDomainMappingRow.confirmed.is_(True))
        table_rows = list(session.execute(t_stmt).scalars().all())

    hits: list[SchemaTermHit] = []
    for row in [*column_rows, *table_rows]:
        hits.append(SchemaTermHit(
            table_fqn=row.schema_table_fqn or (col.table_fqn if col is not None else ""),
            column_fqn=row.schema_column_fqn,
            business_term_fqn=row.business_term_fqn,
            confidence=row.confidence,
            confirmed=row.confirmed,
            source=row.source,
        ))
    return hits


# ─────────────────────────────────────────────────────────────────────────────
# Code ↔ Schema
# ─────────────────────────────────────────────────────────────────────────────


def find_schema_tables_for_code_type(
    session: Session,
    type_fqn: str,
    repo_id: str,
    *,
    confirmed_only: bool = False,
) -> list[SchemaCodeHit]:
    """Given a Java class FQN, find mapped schema tables/columns (JPA @Entity 등)."""
    stmt = select(SchemaCodeMappingRow).where(
        SchemaCodeMappingRow.code_type_fqn == type_fqn,
        SchemaCodeMappingRow.repo_id == repo_id,
    )
    if confirmed_only:
        stmt = stmt.where(SchemaCodeMappingRow.confirmed.is_(True))
    rows = session.execute(stmt).scalars().all()
    return [
        SchemaCodeHit(
            schema_table_fqn=row.schema_table_fqn,
            schema_column_fqn=row.schema_column_fqn,
            code_type_fqn=row.code_type_fqn,
            code_field_fqn=row.code_field_fqn,
            code_method_fqn=row.code_method_fqn,
            mapping_kind=row.mapping_kind,
            confidence=row.confidence,
            confirmed=row.confirmed,
        )
        for row in rows
    ]


def find_code_types_for_schema_table(
    session: Session,
    table_fqn: str,
    repo_id: str,
    *,
    confirmed_only: bool = False,
) -> list[SchemaCodeHit]:
    """Reverse — given a schema table, find mapped Code types."""
    stmt = select(SchemaCodeMappingRow).where(
        SchemaCodeMappingRow.schema_table_fqn == table_fqn,
        SchemaCodeMappingRow.repo_id == repo_id,
    )
    if confirmed_only:
        stmt = stmt.where(SchemaCodeMappingRow.confirmed.is_(True))
    rows = session.execute(stmt).scalars().all()
    return [
        SchemaCodeHit(
            schema_table_fqn=row.schema_table_fqn,
            schema_column_fqn=row.schema_column_fqn,
            code_type_fqn=row.code_type_fqn,
            code_field_fqn=row.code_field_fqn,
            code_method_fqn=row.code_method_fqn,
            mapping_kind=row.mapping_kind,
            confidence=row.confidence,
            confirmed=row.confirmed,
        )
        for row in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Coverage / utility queries
# ─────────────────────────────────────────────────────────────────────────────


def schema_tables_in_repo(
    session: Session,
    repo_id: str,
) -> list[SchemaTableRow]:
    return list(
        session.execute(
            select(SchemaTableRow)
            .where(SchemaTableRow.repo_id == repo_id)
            .order_by(SchemaTableRow.fqn)
        ).scalars().all()
    )


def schema_coverage_for_repo(
    session: Session,
    repo_id: str,
) -> RepoCoverage:
    """Coverage stats — Lesson 2 §3 의 reusability metric 의 schema-level mirror."""
    table_count = len(schema_tables_in_repo(session, repo_id))
    columns = session.execute(
        select(SchemaColumnRow).where(SchemaColumnRow.repo_id == repo_id)
    ).scalars().all()
    column_count = len(columns)

    domain_mapped_columns = len({
        m.schema_column_fqn for m in session.execute(
            select(SchemaDomainMappingRow).where(
                SchemaDomainMappingRow.repo_id == repo_id,
                SchemaDomainMappingRow.schema_column_fqn.is_not(None),
            )
        ).scalars().all()
    })
    confirmed_domain = len({
        m.schema_column_fqn for m in session.execute(
            select(SchemaDomainMappingRow).where(
                SchemaDomainMappingRow.repo_id == repo_id,
                SchemaDomainMappingRow.schema_column_fqn.is_not(None),
                SchemaDomainMappingRow.confirmed.is_(True),
            )
        ).scalars().all()
    })

    code_mapped_columns = len({
        m.schema_column_fqn for m in session.execute(
            select(SchemaCodeMappingRow).where(
                SchemaCodeMappingRow.repo_id == repo_id,
                SchemaCodeMappingRow.schema_column_fqn.is_not(None),
            )
        ).scalars().all()
    })
    confirmed_code = len({
        m.schema_column_fqn for m in session.execute(
            select(SchemaCodeMappingRow).where(
                SchemaCodeMappingRow.repo_id == repo_id,
                SchemaCodeMappingRow.schema_column_fqn.is_not(None),
                SchemaCodeMappingRow.confirmed.is_(True),
            )
        ).scalars().all()
    })

    return RepoCoverage(
        table_count=table_count,
        column_count=column_count,
        domain_mapped_columns=domain_mapped_columns,
        code_mapped_columns=code_mapped_columns,
        confirmed_domain_mappings=confirmed_domain,
        confirmed_code_mappings=confirmed_code,
    )


__all__ = [
    "RepoCoverage",
    "SchemaCodeHit",
    "SchemaTermHit",
    "find_business_terms_for_schema_column",
    "find_code_types_for_schema_table",
    "find_schema_columns_for_business_term",
    "find_schema_tables_for_code_type",
    "schema_coverage_for_repo",
    "schema_tables_in_repo",
]
