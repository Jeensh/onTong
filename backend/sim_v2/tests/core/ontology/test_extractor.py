"""Schema extractor test — implementation-plan §3.1 B1.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.ontology.schema_layer.extractor import (
    JpaAnnotationExtractor,
    SchemaModel,
    SchemaSource,
    SchemaSourceKind,
    get_extractor,
    register_extractor,
)


SAMPLE_JPA_ENTITY = {
    "class_fqn": "com.example.OrderImpl",
    "table_name": "orders",
    "schema_name": "public",
    "description": "주문 root entity",
    "columns": [
        {
            "field_name": "id",
            "column_name": "id",
            "data_type": "BIGINT",
            "nullable": False,
            "primary_key": True,
        },
        {
            "field_name": "totalAmount",
            "column_name": "total_amount",
            "data_type": "NUMERIC(15,2)",
            "nullable": False,
            "description": "주문 총액",
        },
        {
            "field_name": "customerId",
            "column_name": "customer_id",
            "data_type": "BIGINT",
            "nullable": True,
        },
    ],
    "indexes": [
        {"name": "idx_orders_customer", "columns": ["customer_id"], "unique": False},
    ],
    "fks": [
        {
            "name": "fk_orders_customer",
            "column": "customer_id",
            "ref_table": "customer",
            "ref_column": "id",
        },
    ],
}


def test_jpa_extractor_supports():
    ext = JpaAnnotationExtractor()
    assert ext.supports("jpa_annotation")
    assert not ext.supports("ddl_file")


def test_jpa_extractor_extracts_table():
    ext = JpaAnnotationExtractor()
    src = SchemaSource(kind="jpa_annotation", payload=[SAMPLE_JPA_ENTITY], repo_id="banking")
    model = ext.extract(src)

    assert isinstance(model, SchemaModel)
    assert len(model.tables) == 1
    table = model.tables[0]
    assert table.fqn == "public.orders"
    assert table.table_name == "orders"
    assert table.description == "주문 root entity"


def test_jpa_extractor_columns_with_position():
    ext = JpaAnnotationExtractor()
    src = SchemaSource(kind="jpa_annotation", payload=[SAMPLE_JPA_ENTITY])
    model = ext.extract(src)

    assert len(model.columns) == 3
    id_col = model.columns[0]
    assert id_col.fqn == "public.orders.id"
    assert id_col.data_type == "BIGINT"
    assert id_col.position == 0
    total_col = model.columns[1]
    assert total_col.column_name == "total_amount"
    assert total_col.position == 1
    assert total_col.nullable is False


def test_jpa_extractor_pk_constraint():
    ext = JpaAnnotationExtractor()
    model = ext.extract(SchemaSource(kind="jpa_annotation", payload=[SAMPLE_JPA_ENTITY]))

    pks = [c for c in model.constraints if c.kind == "PK"]
    assert len(pks) == 1
    assert pks[0].columns == ["id"]
    assert pks[0].constraint_name == "pk_orders"


def test_jpa_extractor_fk_constraint():
    ext = JpaAnnotationExtractor()
    model = ext.extract(SchemaSource(kind="jpa_annotation", payload=[SAMPLE_JPA_ENTITY]))

    fks = [c for c in model.constraints if c.kind == "FK"]
    assert len(fks) == 1
    assert fks[0].columns == ["customer_id"]
    assert fks[0].referenced_table_fqn == "public.customer"
    assert fks[0].referenced_columns == ["id"]


def test_jpa_extractor_not_null_constraint():
    ext = JpaAnnotationExtractor()
    model = ext.extract(SchemaSource(kind="jpa_annotation", payload=[SAMPLE_JPA_ENTITY]))

    nn = [c for c in model.constraints if c.kind == "NOT_NULL"]
    assert len(nn) == 2  # id, total_amount (customer_id is nullable)
    names = {c.constraint_name for c in nn}
    assert "nn_orders_id" in names
    assert "nn_orders_total_amount" in names


def test_jpa_extractor_index():
    ext = JpaAnnotationExtractor()
    model = ext.extract(SchemaSource(kind="jpa_annotation", payload=[SAMPLE_JPA_ENTITY]))

    assert len(model.indexes) == 1
    idx = model.indexes[0]
    assert idx.index_name == "idx_orders_customer"
    assert idx.is_unique is False
    assert idx.columns == [{"name": "customer_id", "order": "ASC"}]


def test_jpa_extractor_rejects_wrong_kind():
    ext = JpaAnnotationExtractor()
    with pytest.raises(ValueError, match="cannot handle"):
        ext.extract(SchemaSource(kind="ddl_file", payload="CREATE TABLE..."))


def test_jpa_extractor_rejects_non_list_payload():
    ext = JpaAnnotationExtractor()
    with pytest.raises(TypeError, match="must be a list"):
        ext.extract(SchemaSource(kind="jpa_annotation", payload={"single": "entity"}))


def test_registry_get_default():
    ext = get_extractor("jpa_annotation")
    assert isinstance(ext, JpaAnnotationExtractor)


def test_registry_unknown_kind_raises():
    with pytest.raises(ValueError, match="No extractor registered"):
        get_extractor("liquibase")  # 등록 안 함


def test_registry_duplicate_registration_raises():
    with pytest.raises(ValueError, match="already registered"):
        register_extractor("jpa_annotation", JpaAnnotationExtractor())
