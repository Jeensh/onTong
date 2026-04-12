# tests/test_code_graph.py
import pytest
from unittest.mock import MagicMock, call

from backend.modeling.code_analysis.graph_writer import CodeGraphWriter
from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity, CodeRelation, EntityKind, RelationKind, ParseResult,
)


class TestCodeGraphWriter:
    def setup_method(self):
        self.neo4j = MagicMock()
        self.writer = CodeGraphWriter(self.neo4j)

    def test_write_entities_generates_merge_cypher(self):
        entities = [
            CodeEntity(
                kind=EntityKind.CLASS,
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
        cypher = self.neo4j.write.call_args[0][0]
        assert "MERGE" in cypher
        assert "CodeEntity" in cypher

    def test_write_relations_generates_merge_cypher(self):
        relations = [
            CodeRelation(
                kind=RelationKind.CALLS,
                source="com.example.Foo.bar",
                target="com.example.Baz.qux",
            ),
        ]
        self.writer.write_relations(relations, repo_id="test-repo")
        self.neo4j.write.assert_called()
        cypher = self.neo4j.write.call_args[0][0]
        assert "CALLS" in cypher

    def test_clear_repo_deletes_all_nodes(self):
        self.writer.clear_repo("test-repo")
        self.neo4j.write.assert_called()
        cypher = self.neo4j.write.call_args[0][0]
        assert "DELETE" in cypher
        assert "test-repo" in str(self.neo4j.write.call_args)

    def test_write_parse_result(self):
        result = ParseResult(
            entities=[
                CodeEntity(
                    kind=EntityKind.CLASS,
                    qualified_name="com.example.Foo",
                    name="Foo",
                    file_path="Foo.java",
                    line_start=1, line_end=10,
                ),
            ],
            relations=[
                CodeRelation(
                    kind=RelationKind.CONTAINS,
                    source="com.example",
                    target="com.example.Foo",
                ),
            ],
            file_path="Foo.java",
            language="Java",
        )
        self.writer.write_parse_result(result, repo_id="test-repo")
        assert self.neo4j.write.call_count >= 2  # entities + relations
