"""OD-11-B4 : CodeGraphWriter — 17 relation kind + attributes 직렬화.

- kind 는 이제 문자열 (이전 enum `.value` 접근 제거).
- `attributes` dict 는 Neo4j property set 으로 직렬화되어야 한다 (프리미티브/리스트는 그대로,
  nested dict 는 JSON 문자열로 보존).
- 엣지 타입 화이트리스트는 `RelationKindRegistry` 기준 (SQL 인젝션 방지).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from backend.modeling.code_analysis.graph_writer import CodeGraphWriter
from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKindRegistry,
    EntityKindSpec,
    EntityKinds,
    ParseResult,
    RelationKindRegistry,
    RelationKinds,
)


class TestWriteEntities:
    def setup_method(self) -> None:
        self.neo4j = MagicMock()
        self.writer = CodeGraphWriter(self.neo4j)

    def test_basic_entity_merge_cypher(self) -> None:
        entities = [
            CodeEntity(
                kind=EntityKinds.CLASS,
                qualified_name="com.example.Foo",
                name="Foo",
                file_path="Foo.java",
                line_start=1,
                line_end=10,
                modifiers=["public"],
            ),
        ]
        self.writer.write_entities(entities, repo_id="test-repo")
        self.neo4j.write.assert_called()
        cypher, params = self.neo4j.write.call_args[0]
        assert "MERGE" in cypher
        assert "CodeEntity" in cypher
        assert params["kind"] == "class"
        assert params["qn"] == "com.example.Foo"

    def test_method_attributes_are_serialized(self) -> None:
        entities = [
            CodeEntity(
                kind=EntityKinds.METHOD,
                qualified_name="com.example.OrderService.place",
                name="place",
                file_path="OrderService.java",
                line_start=10,
                line_end=30,
                attributes={
                    "precondition": "req.items != null",
                    "postcondition": "result.status == 'PENDING'",
                    "value_flow": {"req.items": ["this.order.items"]},
                    "reflection_escape": False,
                },
            ),
        ]
        self.writer.write_entities(entities, repo_id="repo")
        cypher, params = self.neo4j.write.call_args[0]
        assert params["precondition"] == "req.items != null"
        # nested dict → JSON string
        assert isinstance(params["value_flow"], str)
        assert json.loads(params["value_flow"]) == {"req.items": ["this.order.items"]}
        assert params["reflection_escape"] is False


class TestWriteRelations:
    def setup_method(self) -> None:
        self.neo4j = MagicMock()
        self.writer = CodeGraphWriter(self.neo4j)

    def test_calls_edge_uses_uppercase_rel_type(self) -> None:
        rels = [
            CodeRelation(
                kind=RelationKinds.CALLS,
                source="com.example.Foo.bar",
                target="com.example.Baz.qux",
                file_path="Foo.java",
                line=15,
            ),
        ]
        self.writer.write_relations(rels, repo_id="repo")
        cypher, _ = self.neo4j.write.call_args[0]
        assert "[r:CALLS]" in cypher

    def test_lineage_edge_derives_from_with_attributes(self) -> None:
        rels = [
            CodeRelation(
                kind=RelationKinds.DERIVES_FROM,
                source="com.example.OrderRequest.items",
                target="com.example.orders.total_amount",
                attributes={
                    "via_methods": [
                        "com.example.OrderServiceImpl.place",
                        "com.example.OrderRepository.save",
                    ],
                    "confidence": 0.95,
                },
            ),
        ]
        self.writer.write_relations(rels, repo_id="repo")
        cypher, params = self.neo4j.write.call_args[0]
        assert "[r:DERIVES_FROM]" in cypher
        assert params["confidence"] == 0.95
        assert params["via_methods"] == [
            "com.example.OrderServiceImpl.place",
            "com.example.OrderRepository.save",
        ]

    def test_autowires_edge_with_profile_list(self) -> None:
        rels = [
            CodeRelation(
                kind=RelationKinds.AUTOWIRES,
                source="orderServiceBean",
                target="orderServiceImplBean",
                attributes={
                    "profile": ["prod", "legacy"],
                    "condition": "order.legacy.enabled=true",
                },
            ),
        ]
        self.writer.write_relations(rels, repo_id="repo")
        cypher, params = self.neo4j.write.call_args[0]
        assert "[r:AUTOWIRES]" in cypher
        assert params["profile"] == ["prod", "legacy"]
        assert params["condition"] == "order.legacy.enabled=true"

    def test_rejects_relation_kind_not_in_registry(self) -> None:
        """SQL-injection 방지: 화이트리스트 외 kind 는 애초에 `CodeRelation` 생성이 불가.
        하지만 runtime 에 직접 kind 를 조작한 경우에도 writer 가 한 번 더 검사해야 한다."""
        rel = CodeRelation(
            kind=RelationKinds.CONTAINS,
            source="a",
            target="b",
        )
        object.__setattr__(rel, "kind", "malicious; DROP DATABASE")
        with pytest.raises(ValueError):
            self.writer.write_relations([rel], repo_id="repo")

    def test_all_17_default_edge_kinds_are_writable(self) -> None:
        """Round 1 기본 17 relation kind 전부 Neo4j write 가 성공해야 한다."""
        all_kinds = RelationKindRegistry.all_kinds()
        rels = [
            CodeRelation(kind=k, source="a", target="b") for k in all_kinds
        ]
        self.writer.write_relations(rels, repo_id="repo")
        # n번 write 호출 중 edge type 이 모두 등장했는지 확인
        cyphers = [c.args[0] for c in self.neo4j.write.call_args_list]
        for k in all_kinds:
            assert any(f"[r:{k.upper()}]" in c for c in cyphers), f"missing edge {k}"


class TestWriteParseResult:
    def setup_method(self) -> None:
        self.neo4j = MagicMock()
        self.writer = CodeGraphWriter(self.neo4j)

    def test_writes_entities_then_relations(self) -> None:
        result = ParseResult(
            entities=[
                CodeEntity(
                    kind=EntityKinds.CLASS,
                    qualified_name="com.example.Foo",
                    name="Foo",
                    file_path="Foo.java",
                    line_start=1,
                    line_end=10,
                ),
            ],
            relations=[
                CodeRelation(
                    kind=RelationKinds.CONTAINS,
                    source="com.example",
                    target="com.example.Foo",
                ),
            ],
            file_path="Foo.java",
            language="Java",
        )
        self.writer.write_parse_result(result, repo_id="repo")
        assert self.neo4j.write.call_count >= 2


class TestClearRepo:
    def test_clear_repo_detach_delete(self) -> None:
        neo4j = MagicMock()
        CodeGraphWriter(neo4j).clear_repo("repo-x")
        cypher, params = neo4j.write.call_args[0]
        assert "DETACH DELETE" in cypher
        assert params["repo_id"] == "repo-x"
