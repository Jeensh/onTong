"""CRUD operations for domain ontology in Neo4j."""

from __future__ import annotations

import logging

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.ontology.domain_models import (
    DomainNode,
    DomainOntology,
    DomainRelation,
    DomainRelationKind,
)
from backend.modeling.ontology.scor_template import load_scor_template

logger = logging.getLogger(__name__)


class OntologyStore:
    """Persist and query DomainOntology nodes/relations in Neo4j."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    # ------------------------------------------------------------------
    # Template bootstrap
    # ------------------------------------------------------------------

    def load_template(self) -> int:
        """Load the default SCOR+ISA-95 template into Neo4j.

        Returns the number of nodes written.
        """
        ontology = load_scor_template()
        for node in ontology.nodes:
            self.add_node(node)
        for rel in ontology.relations:
            self._write_relation(rel)
        return len(ontology.nodes)

    # ------------------------------------------------------------------
    # Node CRUD
    # ------------------------------------------------------------------

    def add_node(self, node: DomainNode) -> None:
        cypher = """
        MERGE (n:DomainNode {id: $id})
        SET n.kind = $kind, n.name = $name, n.description = $description,
            n.parent_id = $parent_id, n.metadata = $metadata
        """
        self._neo4j.write(cypher, {
            "id": node.id,
            "kind": node.kind.value,
            "name": node.name,
            "description": node.description,
            "parent_id": node.parent_id,
            "metadata": str(node.metadata),
        })

    def update_node(
        self,
        node_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        sets: list[str] = []
        params: dict = {"id": node_id}
        if name is not None:
            sets.append("n.name = $name")
            params["name"] = name
        if description is not None:
            sets.append("n.description = $description")
            params["description"] = description
        if not sets:
            return
        cypher = f"MATCH (n:DomainNode {{id: $id}}) SET {', '.join(sets)}"
        self._neo4j.write(cypher, params)

    def remove_node(self, node_id: str) -> None:
        self._neo4j.write(
            "MATCH (n:DomainNode {id: $id}) DETACH DELETE n",
            {"id": node_id},
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_tree(self) -> list[dict]:
        return self._neo4j.query(
            "MATCH (n:DomainNode) RETURN n.id as id, n.name as name, n.kind as kind, "
            "n.parent_id as parent_id, n.description as description ORDER BY n.id"
        )

    def get_children(self, parent_id: str) -> list[dict]:
        return self._neo4j.query(
            "MATCH (n:DomainNode {parent_id: $parent_id}) RETURN n.id as id, n.name as name, "
            "n.kind as kind, n.description as description ORDER BY n.id",
            {"parent_id": parent_id},
        )

    def get_node(self, node_id: str) -> dict | None:
        result = self._neo4j.query(
            "MATCH (n:DomainNode {id: $id}) RETURN n.id as id, n.name as name, n.kind as kind, "
            "n.parent_id as parent_id, n.description as description",
            {"id": node_id},
        )
        return result[0] if result else None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_relation(self, rel: DomainRelation) -> None:
        rel_type = rel.kind.value.upper()
        cypher = (
            f"MATCH (a:DomainNode {{id: $source}}) "
            f"MATCH (b:DomainNode {{id: $target}}) "
            f"MERGE (a)-[r:{rel_type}]->(b)"
        )
        self._neo4j.write(cypher, {
            "source": rel.source_id,
            "target": rel.target_id,
        })
