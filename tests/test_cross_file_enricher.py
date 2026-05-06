"""OD-11-B6-4 TDD — CrossFileEnricher repo-level post-batch.

Covers the 4 responsibilities:
  1. MapStruct implicit finalize (B6-1 marker → PROPAGATES_TO{implicit:true})
  2. BeanUtils field intersection (B6-2 marker → PROPAGATES_TO{library,via_methods})
  3. NativeSQL column → field resolution (B6-3 edges → DB_COLUMN + READS/WRITES)
  4. DB_TABLE / DB_COLUMN dedup into synthetic ParseResult

Spec: `toClaude/modeling/OD-11-B6-SPEC.md` §6 (2026-04-19 rev.).
"""
from __future__ import annotations

from backend.modeling.code_analysis.cross_file_enricher import enrich_repo
from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
    RelationKinds,
)


# --- fixtures ----------------------------------------------------------------

def _class(fqn, jpa_entity_name=None, jpa_table=None, jpa_columns=None):
    name = fqn.rsplit(".", 1)[-1]
    attrs: dict[str, object] = {}
    if jpa_entity_name is not None:
        attrs["jpa_entity_name"] = jpa_entity_name
    if jpa_table is not None:
        attrs["jpa_table"] = jpa_table
    if jpa_columns is not None:
        attrs["jpa_columns"] = dict(jpa_columns)
    return CodeEntity(
        kind=EntityKinds.CLASS,
        qualified_name=fqn,
        name=name,
        file_path=f"{name}.java",
        line_start=1,
        line_end=1,
        attributes=attrs,
    )


def _field(class_fqn, name):
    return CodeEntity(
        kind=EntityKinds.FIELD,
        qualified_name=f"{class_fqn}.{name}",
        name=name,
        file_path=f"{class_fqn.rsplit('.', 1)[-1]}.java",
        line_start=1,
        line_end=1,
        parent=class_fqn,
    )


def _method(fqn, attrs=None):
    return CodeEntity(
        kind=EntityKinds.METHOD,
        qualified_name=fqn,
        name=fqn.rsplit(".", 1)[-1],
        file_path="T.java",
        line_start=1,
        line_end=1,
        attributes=dict(attrs) if attrs else {},
    )


def _pr(file_path, entities, relations):
    return ParseResult(
        entities=list(entities),
        relations=list(relations),
        file_path=file_path,
        language="java",
    )


def _indices(class_entities, field_entities_by_class):
    class_index = {c.qualified_name: c for c in class_entities}
    field_index = {
        cfqn: list(fields) for cfqn, fields in field_entities_by_class.items()
    }
    return class_index, field_index


# --- 1. MapStruct implicit ---------------------------------------------------

def test_mapstruct_implicit_emits_propagates_to_for_intersection_fields():
    SRC = "com.x.model.OrderReq"
    DST = "com.x.dto.OrderDto"
    MAPPER = "com.x.mapper.OrderMapper"
    M = f"{MAPPER}.toDto"

    method = _method(
        M,
        attrs={
            "mapstruct_implicit_fields": [
                {"mapper_fqn": MAPPER, "method": "toDto",
                 "src_type": SRC, "dst_type": DST, "line": 7},
            ]
        },
    )
    pr = _pr("OrderMapper.java", [method], [])

    class_index, field_index = _indices(
        [_class(SRC), _class(DST)],
        {
            SRC: [_field(SRC, "id"), _field(SRC, "total"), _field(SRC, "customer")],
            DST: [_field(DST, "id"), _field(DST, "total"), _field(DST, "customer")],
        },
    )

    enrich_repo([pr], class_index, field_index)

    emits = [r for r in pr.relations if r.kind == RelationKinds.PROPAGATES_TO]
    assert len(emits) == 3
    assert {r.target for r in emits} == {f"{DST}.id", f"{DST}.total", f"{DST}.customer"}
    for r in emits:
        assert r.attributes["confidence"] == 0.9
        assert r.attributes["implicit"] is True
        assert r.attributes["via_methods"] == [M]
        assert r.attributes["mapper_fqn"] == MAPPER
        assert r.source.startswith(SRC + ".")


def test_mapstruct_implicit_excludes_fields_already_in_explicit_mapping():
    SRC = "com.x.model.OrderReq"
    DST = "com.x.dto.OrderDto"
    MAPPER = "com.x.mapper.OrderMapper"
    M = f"{MAPPER}.toDto"

    method = _method(
        M,
        attrs={
            "mapstruct_implicit_fields": [
                {"mapper_fqn": MAPPER, "method": "toDto",
                 "src_type": SRC, "dst_type": DST, "line": 7},
            ]
        },
    )
    explicit = CodeRelation(
        kind=RelationKinds.PROPAGATES_TO,
        source=f"{SRC}.id",
        target=f"{DST}.id",
        attributes={"via_methods": [M], "confidence": 1.0, "mapper_fqn": MAPPER},
    )
    pr = _pr("OrderMapper.java", [method], [explicit])

    class_index, field_index = _indices(
        [_class(SRC), _class(DST)],
        {
            SRC: [_field(SRC, "id"), _field(SRC, "total")],
            DST: [_field(DST, "id"), _field(DST, "total")],
        },
    )

    enrich_repo([pr], class_index, field_index)

    implicit_emits = [
        r for r in pr.relations
        if r.kind == RelationKinds.PROPAGATES_TO
        and r.attributes.get("implicit") is True
    ]
    assert len(implicit_emits) == 1
    assert implicit_emits[0].target == f"{DST}.total"


def test_mapstruct_implicit_resolves_simple_name_to_single_fqn_candidate():
    SRC_SIMPLE = "OrderReq"
    SRC_FQN = "com.x.model.OrderReq"
    DST = "com.x.dto.OrderDto"
    MAPPER = "com.x.mapper.OrderMapper"
    M = f"{MAPPER}.toDto"

    method = _method(
        M,
        attrs={
            "mapstruct_implicit_fields": [
                {"mapper_fqn": MAPPER, "method": "toDto",
                 "src_type": SRC_SIMPLE, "dst_type": DST, "line": 7},
            ]
        },
    )
    pr = _pr("OrderMapper.java", [method], [])

    class_index, field_index = _indices(
        [_class(SRC_FQN), _class(DST)],
        {
            SRC_FQN: [_field(SRC_FQN, "id")],
            DST: [_field(DST, "id")],
        },
    )

    enrich_repo([pr], class_index, field_index)

    emits = [r for r in pr.relations if r.kind == RelationKinds.PROPAGATES_TO]
    assert len(emits) == 1
    assert emits[0].source == f"{SRC_FQN}.id"
    assert emits[0].target == f"{DST}.id"


# --- 2. BeanUtils intersection -----------------------------------------------

def test_beanutils_spring_intersection_emits_propagates_to():
    CALLER = "com.x.svc.MapService.copy"
    SRC = "com.x.model.OrderReq"
    DST = "com.x.dto.OrderDto"

    method = _method(
        CALLER,
        attrs={
            "beanutils_calls": [
                {"library": "spring", "src_type": SRC, "dst_type": DST,
                 "ignore": [], "confidence": 0.7, "line": 42},
            ]
        },
    )
    pr = _pr("MapService.java", [method], [])

    class_index, field_index = _indices(
        [_class(SRC), _class(DST)],
        {
            SRC: [_field(SRC, "id"), _field(SRC, "name")],
            DST: [_field(DST, "id"), _field(DST, "name"), _field(DST, "extra")],
        },
    )

    enrich_repo([pr], class_index, field_index)

    emits = [r for r in pr.relations if r.kind == RelationKinds.PROPAGATES_TO]
    assert len(emits) == 2
    assert {r.target for r in emits} == {f"{DST}.id", f"{DST}.name"}
    for r in emits:
        assert r.attributes["confidence"] == 0.7
        assert r.attributes["library"] == "spring"
        assert r.attributes["via_methods"] == [CALLER]


def test_beanutils_apache_with_ignore_list_excludes_listed_fields():
    CALLER = "com.x.svc.MapService.copy"
    SRC = "com.x.model.OrderReq"
    DST = "com.x.dto.OrderDto"

    method = _method(
        CALLER,
        attrs={
            "beanutils_calls": [
                {"library": "apache", "src_type": SRC, "dst_type": DST,
                 "ignore": ["password"], "confidence": 0.7, "line": 10},
            ]
        },
    )
    pr = _pr("MapService.java", [method], [])

    class_index, field_index = _indices(
        [_class(SRC), _class(DST)],
        {
            SRC: [_field(SRC, "id"), _field(SRC, "password")],
            DST: [_field(DST, "id"), _field(DST, "password")],
        },
    )

    enrich_repo([pr], class_index, field_index)

    emits = [r for r in pr.relations if r.kind == RelationKinds.PROPAGATES_TO]
    assert len(emits) == 1
    assert emits[0].target == f"{DST}.id"
    assert emits[0].attributes["library"] == "apache"


def test_beanutils_ambiguous_simple_name_skips_and_adds_marker():
    CALLER = "com.x.svc.MapService.copy"
    DST = "com.x.dto.OrderDto"

    method = _method(
        CALLER,
        attrs={
            "beanutils_calls": [
                {"library": "spring", "src_type": "OrderDto", "dst_type": DST,
                 "ignore": [], "confidence": 0.7, "line": 10},
            ]
        },
    )
    pr = _pr("MapService.java", [method], [])

    # two simple-name candidates for "OrderDto"
    class_index, field_index = _indices(
        [_class("com.x.dto.OrderDto"), _class("com.y.dto.OrderDto")],
        {
            "com.x.dto.OrderDto": [_field("com.x.dto.OrderDto", "id")],
            "com.y.dto.OrderDto": [_field("com.y.dto.OrderDto", "id")],
        },
    )

    enrich_repo([pr], class_index, field_index)

    emits = [r for r in pr.relations if r.kind == RelationKinds.PROPAGATES_TO]
    assert emits == []

    updated = next(e for e in pr.entities if e.qualified_name == CALLER)
    ambiguous = updated.attributes.get("beanutils_ambiguous_types")
    assert isinstance(ambiguous, list) and len(ambiguous) == 1
    assert ambiguous[0]["call_line"] == 10
    assert set(ambiguous[0]["src_candidates"]) == {
        "com.x.dto.OrderDto", "com.y.dto.OrderDto",
    }


# --- 3. NativeSQL column → field --------------------------------------------

def test_native_sql_reads_table_creates_db_column_and_reads_edges_preserving_reads_table():
    M = "com.x.repo.OrderRepo.findById"
    ORDER_FQN = "com.x.model.Order"

    reads_table = CodeRelation(
        kind=RelationKinds.READS_TABLE,
        source=M,
        target="orders",
        attributes={
            "columns": ["id", "customer_id"],
            "confidence": 1.0,
            "raw_sql": "SELECT id, customer_id FROM orders",
            "dialect": "sql",
        },
    )
    pr = _pr("OrderRepo.java", [_method(M)], [reads_table])

    class_index, field_index = _indices(
        [_class(
            ORDER_FQN,
            jpa_entity_name="Order",
            jpa_table="orders",
            jpa_columns={"id": "id", "customerId": "customer_id"},
        )],
        {ORDER_FQN: [_field(ORDER_FQN, "id"), _field(ORDER_FQN, "customerId")]},
    )

    result = enrich_repo([pr], class_index, field_index)

    # synthetic ParseResult appended
    assert len(result) == 2
    synth = result[-1]
    assert synth.file_path == "<db_schema>"

    # DB_TABLE + 2 DB_COLUMN in synth
    db_tables = [e for e in synth.entities if e.kind == EntityKinds.DB_TABLE]
    assert len(db_tables) == 1
    assert db_tables[0].qualified_name == "orders"

    cols = {
        e.qualified_name: e for e in synth.entities
        if e.kind == EntityKinds.DB_COLUMN
    }
    assert set(cols.keys()) == {"orders.id", "orders.customer_id"}
    assert cols["orders.id"].attributes["field_fqn"] == f"{ORDER_FQN}.id"
    assert cols["orders.customer_id"].attributes["field_fqn"] == f"{ORDER_FQN}.customerId"
    for c in cols.values():
        assert c.attributes["table"] == "orders"

    # READS edges in caller pr
    reads_edges = [r for r in pr.relations if r.kind == RelationKinds.READS]
    assert {r.target for r in reads_edges} == {"orders.id", "orders.customer_id"}
    for r in reads_edges:
        assert r.source == M
        assert r.attributes["confidence"] == 1.0

    # READS_TABLE preserved (병존)
    rt_kept = [r for r in pr.relations if r.kind == RelationKinds.READS_TABLE]
    assert len(rt_kept) == 1


def test_jpql_entity_target_is_rewritten_to_jpa_table_and_dedup_emits_orders():
    M = "com.x.repo.OrderRepo.findAll"
    ORDER_FQN = "com.x.model.Order"

    reads = CodeRelation(
        kind=RelationKinds.READS_TABLE,
        source=M,
        target="order",  # JPQL entity name lowercased by B6-3
        attributes={
            "columns": [],
            "confidence": 1.0,
            "raw_sql": "SELECT o FROM Order o",
            "dialect": "jpql",
        },
    )
    pr = _pr("OrderRepo.java", [_method(M)], [reads])

    class_index, field_index = _indices(
        [_class(
            ORDER_FQN,
            jpa_entity_name="Order",
            jpa_table="orders",
            jpa_columns={},
        )],
        {ORDER_FQN: []},
    )

    result = enrich_repo([pr], class_index, field_index)

    synth = result[-1]
    assert any(
        e.kind == EntityKinds.DB_TABLE and e.qualified_name == "orders"
        for e in synth.entities
    )
    # edge target rewritten in place
    rt = pr.relations[0]
    assert rt.target == "orders"


def test_dynamic_sql_skips_db_table_and_db_column_creation():
    M = "com.x.repo.DynRepo.run"

    reads = CodeRelation(
        kind=RelationKinds.READS_TABLE,
        source=M,
        target="<dynamic>",
        attributes={
            "columns": ["<dynamic>"],
            "confidence": 0.3,
            "raw_sql": "SELECT *",
            "dialect": "sql",
        },
    )
    pr = _pr("DynRepo.java", [_method(M)], [reads])

    result = enrich_repo([pr], {}, {})

    # READS_TABLE kept, no READS edge
    assert any(r.kind == RelationKinds.READS_TABLE for r in pr.relations)
    assert all(r.kind != RelationKinds.READS for r in pr.relations)

    # no DB_TABLE/DB_COLUMN for <dynamic>
    for presult in result:
        for e in presult.entities:
            assert e.qualified_name != "<dynamic>"
            assert not e.qualified_name.startswith("<dynamic>.")


# --- 4. DB_TABLE dedup -------------------------------------------------------

def test_db_table_dedup_across_multiple_parse_results():
    READ_FQN = "com.x.repo.OrderRepo.find"
    WRITE_FQN = "com.x.svc.OrderService.save"

    reads = CodeRelation(
        kind=RelationKinds.READS_TABLE,
        source=READ_FQN,
        target="orders",
        attributes={
            "columns": [],
            "confidence": 1.0,
            "raw_sql": "SELECT",
            "dialect": "sql",
        },
    )
    writes = CodeRelation(
        kind=RelationKinds.WRITES_TABLE,
        source=WRITE_FQN,
        target="orders",
        attributes={
            "columns": [],
            "confidence": 1.0,
            "raw_sql": "INSERT",
            "dialect": "sql",
        },
    )
    pr_a = _pr("OrderRepo.java", [_method(READ_FQN)], [reads])
    pr_b = _pr("OrderService.java", [_method(WRITE_FQN)], [writes])

    result = enrich_repo([pr_a, pr_b], {}, {})

    assert result[:2] == [pr_a, pr_b]
    synth = result[-1]
    assert synth.file_path == "<db_schema>"

    db_tables = [e for e in synth.entities if e.kind == EntityKinds.DB_TABLE]
    assert len(db_tables) == 1
    assert db_tables[0].qualified_name == "orders"
