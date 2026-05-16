"""W42 — production JPA loader tests.

Two layers tested:
1. `parse_annotation` / `find_annotation` / `java_type_to_sql` — pure functions
2. `load_entity_dicts` — DB-backed; fixture builds an in-memory ontology DB and
   verifies the loader produces the dicts expected by `JpaAnnotationExtractor`.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.schema_layer.extractor import (
    JpaAnnotationExtractor,
    SchemaSource,
)
from backend.sim_v2.core.ontology.schema_layer.production_jpa_loader import (
    find_annotation,
    has_annotation,
    java_type_to_sql,
    load_entity_dicts,
    parse_annotation,
)


# ─────────────────────────────────────────────────────────────────────────────
# parse_annotation
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_annotation_no_params():
    assert parse_annotation("@Entity") == {"name": "Entity", "params": {}}


def test_parse_annotation_single_param():
    assert parse_annotation("@Table(name=ORDERS)") == {
        "name": "Table", "params": {"name": "ORDERS"},
    }


def test_parse_annotation_multi_param():
    assert parse_annotation("@Column(name=CMP_CD,length=2)") == {
        "name": "Column", "params": {"name": "CMP_CD", "length": "2"},
    }


def test_parse_annotation_with_dotted_value():
    assert parse_annotation("@IdClass(value=Foo.class)") == {
        "name": "IdClass", "params": {"value": "Foo.class"},
    }


def test_parse_annotation_nested_parens_kept_verbatim():
    """Nested parens shouldn't be split — `@Foo(bar(a,b),c=d)` keeps `bar(a,b)` whole."""
    result = parse_annotation("@Foo(bar(a,b),c=d)")
    assert result is not None
    assert result["name"] == "Foo"
    # bar(a,b) becomes a positional param under empty key
    assert "" in result["params"] or "c" in result["params"]


def test_parse_annotation_malformed_returns_none():
    assert parse_annotation("") is None
    assert parse_annotation("not an annotation") is None
    assert parse_annotation(None) is None  # type: ignore[arg-type]


def test_parse_annotation_whitespace_tolerant():
    assert parse_annotation("  @Entity  ") == {"name": "Entity", "params": {}}


# ─────────────────────────────────────────────────────────────────────────────
# find_annotation / has_annotation
# ─────────────────────────────────────────────────────────────────────────────


def test_find_annotation_first_match_wins():
    anns = ["@Entity", "@Table(name=X)", "@Table(name=Y)"]
    result = find_annotation(anns, "Table")
    assert result is not None
    assert result["params"]["name"] == "X"


def test_find_annotation_missing_returns_none():
    assert find_annotation(["@Entity"], "Table") is None


def test_has_annotation_positive():
    assert has_annotation(["@Entity", "@Table(name=X)"], "Entity") is True


def test_has_annotation_negative():
    assert has_annotation(["@Entity"], "Table") is False


def test_has_annotation_on_empty_list():
    assert has_annotation([], "Entity") is False
    assert has_annotation(None, "Entity") is False  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# java_type_to_sql
# ─────────────────────────────────────────────────────────────────────────────


def test_java_type_to_sql_string_to_varchar():
    assert java_type_to_sql("String") == "VARCHAR"


def test_java_type_to_sql_integer_to_int():
    assert java_type_to_sql("Integer") == "INT"
    assert java_type_to_sql("int") == "INT"


def test_java_type_to_sql_bigdecimal_to_decimal():
    assert java_type_to_sql("BigDecimal") == "DECIMAL"


def test_java_type_to_sql_timestamp():
    assert java_type_to_sql("LocalDateTime") == "TIMESTAMP"


def test_java_type_to_sql_unknown_passes_through_uppercased():
    assert java_type_to_sql("CustomThing") == "CUSTOMTHING"


def test_java_type_to_sql_empty_defaults_to_varchar():
    assert java_type_to_sql("") == "VARCHAR"


# ─────────────────────────────────────────────────────────────────────────────
# load_entity_dicts — backed by an in-memory ontology DB
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    """In-memory SQLite mirroring the production schema for code_types / code_fields."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE code_types (
                fqn TEXT PRIMARY KEY,
                annotations_json TEXT,
                repo_id TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE code_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_fqn TEXT,
                name TEXT,
                type TEXT,
                annotations_json TEXT,
                repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_type(engine, fqn, annotations, repo_id):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO code_types(fqn, annotations_json, repo_id) "
                 "VALUES (:fqn, :ann, :rid)"),
            {"fqn": fqn, "ann": json.dumps(annotations), "rid": repo_id},
        )


def _insert_field(engine, type_fqn, name, jtype, annotations, repo_id):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO code_fields(type_fqn, name, type, annotations_json, repo_id) "
                 "VALUES (:tf, :n, :t, :a, :r)"),
            {"tf": type_fqn, "n": name, "t": jtype,
             "a": json.dumps(annotations), "r": repo_id},
        )


def test_load_entity_dicts_returns_entity_with_columns(fixture_db):
    _insert_type(fixture_db, "com.x.Order",
                 ["@Entity", "@Table(name=ORDERS)"], "myrepo")
    _insert_field(fixture_db, "com.x.Order", "id", "Long",
                  ["@Id", "@Column(name=ORDER_ID)"], "myrepo")
    _insert_field(fixture_db, "com.x.Order", "amount", "BigDecimal",
                  ["@Column(name=AMOUNT,nullable=false)"], "myrepo")

    with Session(fixture_db) as session:
        entities = load_entity_dicts(session, "myrepo")

    assert len(entities) == 1
    e = entities[0]
    assert e["class_fqn"] == "com.x.Order"
    assert e["table_name"] == "ORDERS"
    assert len(e["columns"]) == 2
    id_col = next(c for c in e["columns"] if c["field_name"] == "id")
    assert id_col["primary_key"] is True
    assert id_col["nullable"] is False  # @Id forces NOT NULL
    assert id_col["column_name"] == "ORDER_ID"
    assert id_col["data_type"] == "BIGINT"


def test_load_entity_dicts_skips_types_without_entity_or_table(fixture_db):
    """@Entity only (no @Table) and POJOs should be skipped."""
    _insert_type(fixture_db, "com.x.Pojo", [], "r")
    _insert_type(fixture_db, "com.x.NoTable", ["@Entity"], "r")
    _insert_type(fixture_db, "com.x.NoEntity",
                 ["@Table(name=NO_ENTITY)"], "r")
    _insert_type(fixture_db, "com.x.Good",
                 ["@Entity", "@Table(name=GOOD)"], "r")

    with Session(fixture_db) as session:
        entities = load_entity_dicts(session, "r")
    assert len(entities) == 1
    assert entities[0]["class_fqn"] == "com.x.Good"


def test_load_entity_dicts_filters_by_repo_id(fixture_db):
    _insert_type(fixture_db, "com.x.A",
                 ["@Entity", "@Table(name=A)"], "repo1")
    _insert_type(fixture_db, "com.x.B",
                 ["@Entity", "@Table(name=B)"], "repo2")

    with Session(fixture_db) as session:
        assert {e["class_fqn"] for e in load_entity_dicts(session, "repo1")} == {"com.x.A"}
        assert {e["class_fqn"] for e in load_entity_dicts(session, "repo2")} == {"com.x.B"}


def test_load_entity_dicts_field_repo_id_fallback_to_legacy_empty(fixture_db):
    """When a type's repo_id has no per-repo fields, fall back to rows with repo_id=''.

    Mirrors the synthetic-5k pattern in the production DB (types tagged with
    the repo name; fields kept under repo_id='').
    """
    _insert_type(fixture_db, "com.x.Order",
                 ["@Entity", "@Table(name=ORDERS)"], "synthetic")
    _insert_field(fixture_db, "com.x.Order", "id", "Long",
                  ["@Id", "@Column(name=ORDER_ID)"], "")  # legacy empty

    with Session(fixture_db) as session:
        entities = load_entity_dicts(session, "synthetic")
    assert len(entities) == 1
    assert len(entities[0]["columns"]) == 1


def test_load_entity_dicts_no_legacy_pickup_when_repo_has_own(fixture_db):
    """If the repo has its own fields, the loader must NOT also pull legacy
    rows (the prior bug that produced duplicate columns)."""
    _insert_type(fixture_db, "com.x.Order",
                 ["@Entity", "@Table(name=ORDERS)"], "myrepo")
    _insert_field(fixture_db, "com.x.Order", "id", "Long",
                  ["@Id", "@Column(name=ORDER_ID)"], "myrepo")
    _insert_field(fixture_db, "com.x.Order", "id", "Long",
                  ["@Id", "@Column(name=ORDER_ID)"], "")  # legacy duplicate

    with Session(fixture_db) as session:
        entities = load_entity_dicts(session, "myrepo")
    assert len(entities[0]["columns"]) == 1, "must not include legacy duplicate"


def test_load_entity_dicts_default_table_name_when_table_name_omitted(fixture_db):
    """@Table without name= should fall back to the simple class name."""
    _insert_type(fixture_db, "com.x.Customer",
                 ["@Entity", "@Table"], "r")
    _insert_field(fixture_db, "com.x.Customer", "id", "Long",
                  ["@Id", "@Column"], "r")

    with Session(fixture_db) as session:
        entities = load_entity_dicts(session, "r")
    assert entities[0]["table_name"] == "Customer"


def test_load_entity_dicts_join_column_synthesizes_fk(fixture_db):
    _insert_type(fixture_db, "com.x.Order",
                 ["@Entity", "@Table(name=ORDERS)"], "r")
    _insert_field(fixture_db, "com.x.Order", "customerId", "Long",
                  ["@Column(name=CUSTOMER_ID)",
                   "@JoinColumn(name=CUSTOMER_ID,table=CUSTOMERS,referencedColumnName=ID)"],
                  "r")

    with Session(fixture_db) as session:
        entities = load_entity_dicts(session, "r")
    assert len(entities[0]["fks"]) == 1
    fk = entities[0]["fks"][0]
    assert fk["column"] == "CUSTOMER_ID"
    assert fk["ref_table"] == "CUSTOMERS"
    assert fk["ref_column"] == "ID"


# ─────────────────────────────────────────────────────────────────────────────
# Loader → JpaAnnotationExtractor round-trip
# ─────────────────────────────────────────────────────────────────────────────


def test_loader_output_feeds_extractor_cleanly(fixture_db):
    """The dicts emitted by `load_entity_dicts` must be a valid payload for
    `JpaAnnotationExtractor.extract()`, with no exceptions and sensible counts."""
    _insert_type(fixture_db, "com.x.Order",
                 ["@Entity", "@Table(name=ORDERS)"], "r")
    _insert_field(fixture_db, "com.x.Order", "id", "Long",
                  ["@Id", "@Column(name=ORDER_ID,nullable=false)"], "r")
    _insert_field(fixture_db, "com.x.Order", "amount", "BigDecimal",
                  ["@Column(name=AMOUNT)"], "r")

    with Session(fixture_db) as session:
        entities = load_entity_dicts(session, "r")
    source = SchemaSource(kind="jpa_annotation", payload=entities, repo_id="r")
    model = JpaAnnotationExtractor().extract(source)

    assert len(model.tables) == 1
    assert model.tables[0].table_name == "ORDERS"
    assert len(model.columns) == 2
    assert {c.column_name for c in model.columns} == {"ORDER_ID", "AMOUNT"}
    # Exactly one PK constraint (the @Id column)
    pks = [c for c in model.constraints if c.kind == "PK"]
    assert len(pks) == 1
    assert pks[0].columns == ["ORDER_ID"]
