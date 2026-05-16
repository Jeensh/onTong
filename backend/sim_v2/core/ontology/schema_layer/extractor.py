"""Schema extractor — implementation-plan §3.1 B1.3.

Plugin extension point (ADR-013) — JPA annotation / Hibernate XML / DDL file
등의 source 에서 schema 추출.

Public API:
    - SchemaSource — extract input (Java AST / DDL string / Hibernate XML 등의 normalized form)
    - SchemaModel — extract output (list of SchemaTable / SchemaColumn / SchemaIndex / SchemaConstraint)
    - SchemaExtractor — Protocol
    - JpaAnnotationExtractor — default impl (dict-based input — Java AST integration W3-W4)

설계 결정:
- Java AST 합성 인프라 아직 부재 (W3-W4 예정) — extractor 가 normalized dict 받는 형태로 시작
- W3-W4 에 Java AST 인프라 갖춰지면 normalized dict 도 자동 생성 (`backend.sim_v2.core.synthesizer.java_ast` 의 output)
- SchemaSource 는 generic — extractor 별 input format 다를 수 있음
"""
from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

SchemaSourceKind = Literal[
    "jpa_annotation",
    "hibernate_xml",
    "ddl_file",
    "liquibase",
    "flyway",
]


class SchemaSource(BaseModel):
    """Extractor 의 input.

    각 extractor 가 자체 format 으로 payload 해석.
    JPA: payload = list of entity dicts (W3-W4 의 java_ast 가 produce)
    DDL file: payload = SQL string
    Hibernate XML: payload = XML string
    """
    model_config = ConfigDict(frozen=True)

    kind:    SchemaSourceKind
    payload: Any
    repo_id: str = ""


class SchemaTableDef(BaseModel):
    """Extracted table 의 plain payload (orm.py 의 SchemaTableRow 와 1:1)."""
    model_config = ConfigDict(frozen=True)

    fqn:         str
    table_name:  str
    schema_name: str = "public"
    description: str = ""


class SchemaColumnDef(BaseModel):
    model_config = ConfigDict(frozen=True)

    fqn:           str
    table_fqn:     str
    column_name:   str
    data_type:     str
    nullable:      bool = True
    default_value: str | None = None
    description:   str = ""
    position:      int = 0


class SchemaConstraintDef(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_fqn:                str
    constraint_name:          str
    kind:                     Literal["UNIQUE", "CHECK", "NOT_NULL", "FK", "PK"]
    columns:                  list[str] = Field(default_factory=list)
    expression:               str | None = None
    referenced_table_fqn:     str | None = None
    referenced_columns:       list[str] | None = None


class SchemaIndexDef(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_fqn:           str
    index_name:          str
    columns:             list[dict[str, str]] = Field(default_factory=list)
    # list of {name, order: 'ASC'|'DESC'}
    is_unique:           bool = False
    kind:                str = "BTREE"
    partial_expression:  str | None = None


class SchemaCodeMappingDef(BaseModel):
    """W43 — code ↔ schema mapping payload. Bidirectional link between a
    `code_types` / `code_fields` row and a schema-layer row.

    Exactly one of (`schema_table_fqn`, `schema_column_fqn`) and exactly one of
    (`code_type_fqn`, `code_field_fqn`, `code_method_fqn`) should be populated.
    """
    model_config = ConfigDict(frozen=True)

    schema_table_fqn:  str | None = None
    schema_column_fqn: str | None = None
    code_type_fqn:     str | None = None
    code_field_fqn:    str | None = None
    code_method_fqn:   str | None = None
    mapping_kind:      str = "entity"
    # mapping_kind: entity / value_object / projection / view / repository_method
    confidence:        float = 1.0
    confirmed:         bool = False
    source:            str = "jpa_annotation"


class SchemaModel(BaseModel):
    """Extractor 의 output — table/column/constraint/index/code_mapping 묶음."""
    model_config = ConfigDict(frozen=True)

    tables:        list[SchemaTableDef] = Field(default_factory=list)
    columns:       list[SchemaColumnDef] = Field(default_factory=list)
    constraints:   list[SchemaConstraintDef] = Field(default_factory=list)
    indexes:       list[SchemaIndexDef] = Field(default_factory=list)
    code_mappings: list[SchemaCodeMappingDef] = Field(default_factory=list)


class SchemaExtractor(Protocol):
    """Plug-in extension point — ADR-013.

    Plugin manifest.toml 의 `[schema] source = "<kind>"` 에 따라
    적절한 SchemaExtractor 선택.
    """

    def supports(self, kind: SchemaSourceKind) -> bool:
        ...

    def extract(self, source: SchemaSource) -> SchemaModel:
        ...


class JpaAnnotationExtractor:
    """Default JPA annotation extractor.

    Input payload format (W3-W4 의 java_ast 가 produce):
        [
            {
                "class_fqn": "com.example.OrderImpl",
                "table_name": "orders",      # @Table(name=)
                "schema_name": "public",     # default
                "columns": [
                    {
                        "field_name": "id",
                        "column_name": "id",
                        "data_type": "BIGINT",
                        "nullable": False,
                        "primary_key": True,
                    },
                    ...
                ],
                "indexes": [
                    {"name": "idx_orders_status", "columns": ["status"], "unique": False},
                ],
                "fks": [
                    {"name": "fk_orders_customer", "column": "customer_id",
                     "ref_table": "customers", "ref_column": "id"},
                ],
            },
            ...
        ]
    """

    def supports(self, kind: SchemaSourceKind) -> bool:
        return kind == "jpa_annotation"

    def extract(self, source: SchemaSource) -> SchemaModel:
        if not self.supports(source.kind):
            raise ValueError(f"JpaAnnotationExtractor cannot handle {source.kind!r}")

        entities: list[dict[str, Any]] = source.payload
        if not isinstance(entities, list):
            raise TypeError("payload must be a list of entity dicts")

        # Tables/columns/constraints/indexes dedupe by natural unique key (fqn /
        # (table_fqn, constraint_name) / (table_fqn, index_name)). Two distinct
        # code classes legitimately mapping to the same physical table (JPA
        # inheritance, synthetic class copies, etc.) collapse to one schema row
        # but produce two `code_mappings` entries — the cross-layer info is
        # preserved at the mapping layer while the schema stays single-physical.
        tables_by_fqn: dict[str, SchemaTableDef] = {}
        columns_by_fqn: dict[str, SchemaColumnDef] = {}
        constraints_by_key: dict[tuple[str, str], SchemaConstraintDef] = {}
        indexes_by_key: dict[tuple[str, str], SchemaIndexDef] = {}
        code_mappings: list[SchemaCodeMappingDef] = []

        for entity in entities:
            table_name = entity["table_name"]
            schema_name = entity.get("schema_name", "public")
            table_fqn = f"{schema_name}.{table_name}"
            class_fqn = entity.get("class_fqn")

            tables_by_fqn.setdefault(table_fqn, SchemaTableDef(
                fqn=table_fqn,
                table_name=table_name,
                schema_name=schema_name,
                description=entity.get("description", ""),
            ))

            # W43 — entity-level mapping: @Entity + @Table directly identifies
            # the class as the table's owning code type. Multiple classes
            # mapping to the same table each contribute a mapping row.
            if class_fqn:
                code_mappings.append(SchemaCodeMappingDef(
                    schema_table_fqn=table_fqn,
                    code_type_fqn=class_fqn,
                    mapping_kind="entity",
                    confidence=1.0,
                    confirmed=False,
                    source="jpa_annotation",
                ))

            pk_columns: list[str] = []
            for pos, col in enumerate(entity.get("columns", [])):
                column_name = col["column_name"]
                col_fqn = f"{table_fqn}.{column_name}"
                nullable = col.get("nullable", True)
                columns_by_fqn.setdefault(col_fqn, SchemaColumnDef(
                    fqn=col_fqn,
                    table_fqn=table_fqn,
                    column_name=column_name,
                    data_type=col["data_type"],
                    nullable=nullable,
                    default_value=col.get("default_value"),
                    description=col.get("description", ""),
                    position=pos,
                ))
                if not nullable:
                    nn_name = f"nn_{table_name}_{column_name}"
                    constraints_by_key.setdefault(
                        (table_fqn, nn_name),
                        SchemaConstraintDef(
                            table_fqn=table_fqn,
                            constraint_name=nn_name,
                            kind="NOT_NULL",
                            columns=[column_name],
                        ),
                    )
                if col.get("primary_key"):
                    pk_columns.append(column_name)

                # W43 — column-level mapping (@Column directly identifies the
                # field that backs the column). @Id raises confidence.
                if class_fqn and col.get("field_name"):
                    code_mappings.append(SchemaCodeMappingDef(
                        schema_column_fqn=col_fqn,
                        code_field_fqn=f"{class_fqn}.{col['field_name']}",
                        mapping_kind="entity",
                        confidence=1.0 if col.get("primary_key") else 0.95,
                        confirmed=False,
                        source="jpa_annotation",
                    ))

            if pk_columns:
                pk_name = f"pk_{table_name}"
                constraints_by_key.setdefault(
                    (table_fqn, pk_name),
                    SchemaConstraintDef(
                        table_fqn=table_fqn,
                        constraint_name=pk_name,
                        kind="PK",
                        columns=pk_columns,
                    ),
                )

            for fk in entity.get("fks", []):
                ref_table = fk["ref_table"]
                ref_schema = fk.get("ref_schema", "public")
                constraints_by_key.setdefault(
                    (table_fqn, fk["name"]),
                    SchemaConstraintDef(
                        table_fqn=table_fqn,
                        constraint_name=fk["name"],
                        kind="FK",
                        columns=[fk["column"]],
                        referenced_table_fqn=f"{ref_schema}.{ref_table}",
                        referenced_columns=[fk["ref_column"]],
                    ),
                )

            for idx in entity.get("indexes", []):
                indexes_by_key.setdefault(
                    (table_fqn, idx["name"]),
                    SchemaIndexDef(
                        table_fqn=table_fqn,
                        index_name=idx["name"],
                        columns=[{"name": c, "order": "ASC"} for c in idx.get("columns", [])],
                        is_unique=idx.get("unique", False),
                        kind=idx.get("kind", "BTREE"),
                        partial_expression=idx.get("partial_expression"),
                    ),
                )

        return SchemaModel(
            tables=list(tables_by_fqn.values()),
            columns=list(columns_by_fqn.values()),
            constraints=list(constraints_by_key.values()),
            indexes=list(indexes_by_key.values()),
            code_mappings=code_mappings,
        )


# Plugin extension registry (ADR-013 §2 pattern)
_EXTRACTOR_REGISTRY: dict[SchemaSourceKind, SchemaExtractor] = {
    "jpa_annotation": JpaAnnotationExtractor(),
}


def register_extractor(kind: SchemaSourceKind, extractor: SchemaExtractor) -> None:
    if kind in _EXTRACTOR_REGISTRY:
        raise ValueError(f"Extractor for {kind!r} already registered")
    _EXTRACTOR_REGISTRY[kind] = extractor


def get_extractor(kind: SchemaSourceKind) -> SchemaExtractor:
    extractor = _EXTRACTOR_REGISTRY.get(kind)
    if extractor is None:
        raise ValueError(f"No extractor registered for {kind!r}")
    return extractor


__all__ = [
    "JpaAnnotationExtractor",
    "SchemaCodeMappingDef",
    "SchemaColumnDef",
    "SchemaConstraintDef",
    "SchemaExtractor",
    "SchemaIndexDef",
    "SchemaModel",
    "SchemaSource",
    "SchemaSourceKind",
    "SchemaTableDef",
    "get_extractor",
    "register_extractor",
]
