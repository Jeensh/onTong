"""Writes parsed code entities and relations to Neo4j.

OD-11 Round 1 (rev.3) 대응:
  - 기본 16 entity kind + 18 relation kind (plugin-registrable).
  - `attributes` dict 직렬화 — 프리미티브/리스트는 그대로 Neo4j property 로,
    nested dict 는 JSON 문자열로 보존.
  - Edge type 은 `RelationKindRegistry` 화이트리스트 + 정규식 이중 검사로 Cypher
    인젝션 차단.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    ParseResult,
    RelationKindRegistry,
)
from backend.modeling.infrastructure.neo4j_client import Neo4jClient

_SAFE_REL_TYPE = re.compile(r"^[A-Z_]+$")

logger = logging.getLogger(__name__)


def _flatten_attributes(attrs: dict[str, object]) -> dict[str, Any]:
    """Flatten attributes for Neo4j property set.

    - primitives (str/int/float/bool/None) → 그대로
    - list 중 원소가 모두 primitives → 그대로 (Neo4j 지원)
    - 그 외 (nested dict, mixed list) → JSON 문자열
    """
    out: dict[str, Any] = {}
    for k, v in attrs.items():
        if v is None or isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, list) and all(
            isinstance(x, (str, int, float, bool)) or x is None for x in v
        ):
            out[k] = v
        else:
            out[k] = json.dumps(v, ensure_ascii=False)
    return out


class CodeGraphWriter:
    """Writes code analysis results to Neo4j graph database."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    # -- public API ---------------------------------------------------------

    def write_parse_result(self, result: ParseResult, repo_id: str) -> None:
        self.write_entities(result.entities, repo_id)
        self.write_relations(result.relations, repo_id)

    def write_entities(self, entities: list[CodeEntity], repo_id: str) -> None:
        for entity in entities:
            params: dict[str, Any] = {
                "qn": entity.qualified_name,
                "repo_id": repo_id,
                "kind": entity.kind,
                "name": entity.name,
                "file_path": entity.file_path,
                "line_start": entity.line_start,
                "line_end": entity.line_end,
                "modifiers": entity.modifiers,
                "parent": entity.parent,
            }
            params.update(_flatten_attributes(entity.attributes))

            attr_sets = "".join(f", n.{k} = ${k}" for k in entity.attributes)
            cypher = f"""
            MERGE (n:CodeEntity {{qualified_name: $qn, repo_id: $repo_id}})
            SET n.kind = $kind,
                n.name = $name,
                n.file_path = $file_path,
                n.line_start = $line_start,
                n.line_end = $line_end,
                n.modifiers = $modifiers,
                n.parent = $parent{attr_sets}
            """
            self._neo4j.write(cypher, params)

    def write_relations(self, relations: list[CodeRelation], repo_id: str) -> None:
        for rel in relations:
            if not RelationKindRegistry.is_registered(rel.kind):
                raise ValueError(f"Unregistered relation kind: {rel.kind!r}")
            rel_type = rel.kind.upper()
            if not _SAFE_REL_TYPE.match(rel_type):
                raise ValueError(f"Invalid relationship type: {rel_type}")

            params: dict[str, Any] = {
                "source": rel.source,
                "target": rel.target,
                "repo_id": repo_id,
                "file_path": rel.file_path,
                "line": rel.line,
            }
            params.update(_flatten_attributes(rel.attributes))
            attr_sets = "".join(f", r.{k} = ${k}" for k in rel.attributes)

            cypher = f"""
            MATCH (a:CodeEntity {{qualified_name: $source, repo_id: $repo_id}})
            MATCH (b:CodeEntity {{qualified_name: $target, repo_id: $repo_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r.file_path = $file_path,
                r.line = $line{attr_sets}
            """
            self._neo4j.write(cypher, params)

    def clear_repo(self, repo_id: str) -> None:
        cypher = """
        MATCH (n:CodeEntity {repo_id: $repo_id})
        DETACH DELETE n
        """
        self._neo4j.write(cypher, {"repo_id": repo_id})
        logger.info(f"Cleared code graph for repo {repo_id}")
