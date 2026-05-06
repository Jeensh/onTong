"""OD-11-B3 : EntityKindRegistry / RelationKindRegistry 플러그인 패턴 테스트.

Round 1 스키마 (rev.3) :
  - 기본 16 entity kind (code 7 / spring 6 / db 2 / config 1)
  - 기본 17 relation kind (code 7 / spring 5 / db 2 / config 1 / lineage 2)
  - 외부 플러그인이 런타임 등록 가능
  - CodeEntity / CodeRelation 생성 시 등록 여부 검증
"""

from __future__ import annotations

import pytest

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKindRegistry,
    EntityKindSpec,
    EntityKinds,
    ParseResult,
    RelationKindRegistry,
    RelationKindSpec,
    RelationKinds,
)


# ---------------------------------------------------------------------------
# 기본 16 entity kind 등록 확인
# ---------------------------------------------------------------------------
def test_default_entity_kinds_registered() -> None:
    registered = set(EntityKindRegistry.all_kinds())
    expected = {
        "package", "class", "interface", "enum", "method", "field", "constructor",
        "spring_bean", "http_endpoint", "aspect", "scheduled_task",
        "msg_listener", "event_type",
        "db_table", "db_column",
        "config_property",
    }
    assert expected.issubset(registered)


def test_entity_kinds_constants_match_registry() -> None:
    assert EntityKinds.CLASS == "class"
    assert EntityKinds.METHOD == "method"
    assert EntityKinds.SPRING_BEAN == "spring_bean"
    assert EntityKinds.HTTP_ENDPOINT == "http_endpoint"
    assert EntityKinds.ASPECT == "aspect"
    assert EntityKinds.CONFIG_PROPERTY == "config_property"
    for name in [
        EntityKinds.PACKAGE, EntityKinds.CLASS, EntityKinds.INTERFACE,
        EntityKinds.ENUM, EntityKinds.METHOD, EntityKinds.FIELD,
        EntityKinds.CONSTRUCTOR, EntityKinds.SPRING_BEAN,
        EntityKinds.HTTP_ENDPOINT, EntityKinds.ASPECT,
        EntityKinds.SCHEDULED_TASK, EntityKinds.MSG_LISTENER,
        EntityKinds.EVENT_TYPE, EntityKinds.DB_TABLE,
        EntityKinds.DB_COLUMN, EntityKinds.CONFIG_PROPERTY,
    ]:
        assert EntityKindRegistry.is_registered(name)


def test_entity_kind_categories() -> None:
    assert set(EntityKindRegistry.of_category("code")) >= {
        "package", "class", "interface", "enum", "method", "field", "constructor",
    }
    # P29-1/P29-2 — tx_marker, async_marker, mapper_method 추가
    assert set(EntityKindRegistry.of_category("spring")) >= {
        "spring_bean", "http_endpoint", "aspect",
        "scheduled_task", "msg_listener", "event_type",
        "tx_marker", "async_marker", "mapper_method",
    }
    assert set(EntityKindRegistry.of_category("db")) >= {"db_table", "db_column"}
    assert set(EntityKindRegistry.of_category("config")) >= {"config_property"}


def test_entity_kind_get_returns_spec() -> None:
    spec = EntityKindRegistry.get("class")
    assert spec is not None
    assert spec.kind == "class"
    assert spec.category == "code"
    assert spec.description


def test_entity_kind_get_unknown_returns_none() -> None:
    assert EntityKindRegistry.get("no_such_kind_xyz") is None


# ---------------------------------------------------------------------------
# 기본 17 relation kind 등록 확인
# ---------------------------------------------------------------------------
def test_default_relation_kinds_registered() -> None:
    registered = set(RelationKindRegistry.all_kinds())
    expected = {
        "contains", "calls", "extends", "implements", "depends_on", "reads", "writes",
        "autowires", "intercepts", "maps_url", "publishes", "handles",
        "reads_table", "writes_table",
        "has_config",
        "derives_from", "propagates_to",
    }
    assert expected.issubset(registered)


def test_relation_kind_categories() -> None:
    assert set(RelationKindRegistry.of_category("code")) >= {
        "contains", "calls", "extends", "implements",
        "depends_on", "reads", "writes",
        "reflects_as",
    }
    # P30-2 — calls_via_event 추가 (publisher → handler 합성)
    assert set(RelationKindRegistry.of_category("spring")) >= {
        "autowires", "intercepts", "maps_url", "publishes", "handles",
        "calls_via_event",
    }
    assert set(RelationKindRegistry.of_category("db")) >= {
        "reads_table", "writes_table",
    }
    assert set(RelationKindRegistry.of_category("config")) >= {"has_config"}
    assert set(RelationKindRegistry.of_category("lineage")) >= {
        "derives_from", "propagates_to",
    }


def test_relation_kinds_constants_match_registry() -> None:
    assert RelationKinds.CALLS == "calls"
    assert RelationKinds.AUTOWIRES == "autowires"
    assert RelationKinds.DERIVES_FROM == "derives_from"
    assert RelationKinds.PROPAGATES_TO == "propagates_to"
    assert RelationKinds.REFLECTS_AS == "reflects_as"


# ---------------------------------------------------------------------------
# 플러그인 확장 — 런타임 신규 kind 등록
# ---------------------------------------------------------------------------
def test_register_new_entity_kind() -> None:
    new_spec = EntityKindSpec(
        kind="feign_client_xyz",
        category="spring",
        description="Feign 클라이언트 (플러그인 테스트용)",
    )
    EntityKindRegistry.register(new_spec)
    assert EntityKindRegistry.is_registered("feign_client_xyz")
    assert EntityKindRegistry.get("feign_client_xyz") == new_spec


def test_register_new_relation_kind() -> None:
    new_spec = RelationKindSpec(
        kind="throws_xyz",
        category="code",
        description="예외 전파 (플러그인 테스트용)",
    )
    RelationKindRegistry.register(new_spec)
    assert RelationKindRegistry.is_registered("throws_xyz")


def test_duplicate_register_same_spec_is_idempotent() -> None:
    spec = EntityKindSpec(
        kind="dup_kind_xyz", category="code", description="dup",
    )
    EntityKindRegistry.register(spec)
    EntityKindRegistry.register(spec)
    assert EntityKindRegistry.is_registered("dup_kind_xyz")


def test_duplicate_register_different_spec_raises() -> None:
    spec_a = EntityKindSpec(
        kind="conflict_xyz", category="code", description="A",
    )
    spec_b = EntityKindSpec(
        kind="conflict_xyz", category="spring", description="B",
    )
    EntityKindRegistry.register(spec_a)
    with pytest.raises(ValueError, match="conflict_xyz"):
        EntityKindRegistry.register(spec_b)


# ---------------------------------------------------------------------------
# CodeEntity / CodeRelation 생성 + 검증
# ---------------------------------------------------------------------------
def test_code_entity_valid_creation() -> None:
    entity = CodeEntity(
        kind=EntityKinds.METHOD,
        qualified_name="com.acme.order.OrderService.place",
        name="place",
        file_path="src/main/java/com/acme/order/OrderService.java",
        line_start=42,
        line_end=80,
        modifiers=["public"],
        parent="com.acme.order.OrderService",
    )
    assert entity.kind == "method"
    assert entity.name == "place"


def test_code_entity_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown entity kind"):
        CodeEntity(
            kind="no_such_kind_qqq",
            qualified_name="x",
            name="x",
            file_path="x",
            line_start=1,
            line_end=1,
        )


def test_code_entity_attributes_for_method_fields() -> None:
    """Round 1 §6 : METHOD 노드가 precondition/postcondition 등 확장 속성을 담을 수 있어야 함."""
    entity = CodeEntity(
        kind=EntityKinds.METHOD,
        qualified_name="com.acme.OrderServiceImpl.place",
        name="place",
        file_path="OrderServiceImpl.java",
        line_start=10,
        line_end=30,
        attributes={
            "precondition": "req.items != null AND size(req.items) > 0",
            "postcondition": "result.status == 'PENDING'",
            "input_domain": {"req.items.size": [1, 100]},
            "value_flow": {"req.items": ["this.order.items"]},
            "reflection_escape": False,
        },
    )
    assert entity.attributes["precondition"].startswith("req.items")
    assert entity.attributes["input_domain"]["req.items.size"] == [1, 100]


def test_code_relation_valid_creation() -> None:
    rel = CodeRelation(
        kind=RelationKinds.CALLS,
        source="com.acme.OrderController.place",
        target="com.acme.OrderService.place",
        file_path="OrderController.java",
        line=25,
    )
    assert rel.kind == "calls"


def test_code_relation_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unknown relation kind"):
        CodeRelation(kind="no_such_rel_qqq", source="a", target="b")


def test_code_relation_lineage_with_attributes() -> None:
    """Round 1 §6-B : DERIVES_FROM/PROPAGATES_TO 엣지에 via_methods / confidence 속성."""
    rel = CodeRelation(
        kind=RelationKinds.DERIVES_FROM,
        source="com.acme.OrderRequest.items",
        target="com.acme.orders.total_amount",
        attributes={
            "via_methods": [
                "com.acme.OrderServiceImpl.place",
                "com.acme.OrderRepository.save",
            ],
            "confidence": 0.95,
        },
    )
    assert rel.kind == "derives_from"
    assert rel.attributes["confidence"] == 0.95


def test_code_relation_spring_autowires_with_profile() -> None:
    """Round 1 §5-8 (Q7) : AUTOWIRES 엣지에 profile/condition 속성."""
    rel = CodeRelation(
        kind=RelationKinds.AUTOWIRES,
        source="orderServiceBean",
        target="orderServiceImplBean",
        attributes={
            "profile": ["prod", "legacy"],
            "condition": "order.legacy.enabled=true",
        },
    )
    assert "prod" in rel.attributes["profile"]


# ---------------------------------------------------------------------------
# ParseResult
# ---------------------------------------------------------------------------
def test_parse_result_holds_entities_and_relations() -> None:
    entity = CodeEntity(
        kind=EntityKinds.CLASS,
        qualified_name="com.acme.Foo",
        name="Foo",
        file_path="Foo.java",
        line_start=1,
        line_end=10,
    )
    rel = CodeRelation(
        kind=RelationKinds.CONTAINS,
        source="com.acme",
        target="com.acme.Foo",
    )
    pr = ParseResult(
        entities=[entity],
        relations=[rel],
        file_path="Foo.java",
        language="Java",
    )
    assert len(pr.entities) == 1
    assert len(pr.relations) == 1
    assert pr.errors == []


# ---------------------------------------------------------------------------
# Count sanity (Round 1 rev.3 스키마 최소 수량 보장)
# ---------------------------------------------------------------------------
def test_minimum_default_counts() -> None:
    """기본 등록 entity ≥ 16, relation ≥ 17 (사용자 플러그인 테스트로 인한 추가 허용)."""
    assert len(EntityKindRegistry.all_kinds()) >= 16
    assert len(RelationKindRegistry.all_kinds()) >= 17
