"""Writes parsed code entities and relations to Neo4j."""

from __future__ import annotations

import logging

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity, CodeRelation, ParseResult, RelationKind,
)

logger = logging.getLogger(__name__)


class CodeGraphWriter:
    """Writes code analysis results to Neo4j graph database."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    def write_parse_result(self, result: ParseResult, repo_id: str) -> None:
        self.write_entities(result.entities, repo_id)
        self.write_relations(result.relations, repo_id)

    def write_entities(self, entities: list[CodeEntity], repo_id: str) -> None:
        for entity in entities:
            cypher = """
            MERGE (n:CodeEntity {qualified_name: $qn, repo_id: $repo_id})
            SET n.kind = $kind,
                n.name = $name,
                n.file_path = $file_path,
                n.line_start = $line_start,
                n.line_end = $line_end,
                n.modifiers = $modifiers,
                n.parent = $parent
            """
            self._neo4j.write(cypher, {
                "qn": entity.qualified_name,
                "repo_id": repo_id,
                "kind": entity.kind.value,
                "name": entity.name,
                "file_path": entity.file_path,
                "line_start": entity.line_start,
                "line_end": entity.line_end,
                "modifiers": entity.modifiers,
                "parent": entity.parent,
            })

    def write_relations(self, relations: list[CodeRelation], repo_id: str) -> None:
        for rel in relations:
            rel_type = rel.kind.value.upper()
            cypher = f"""
            MATCH (a:CodeEntity {{qualified_name: $source, repo_id: $repo_id}})
            MATCH (b:CodeEntity {{qualified_name: $target, repo_id: $repo_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r.file_path = $file_path,
                r.line = $line
            """
            self._neo4j.write(cypher, {
                "source": rel.source,
                "target": rel.target,
                "repo_id": repo_id,
                "file_path": rel.file_path,
                "line": rel.line,
            })

    def clear_repo(self, repo_id: str) -> None:
        cypher = """
        MATCH (n:CodeEntity {repo_id: $repo_id})
        DETACH DELETE n
        """
        self._neo4j.write(cypher, {"repo_id": repo_id})
        logger.info(f"Cleared code graph for repo {repo_id}")
