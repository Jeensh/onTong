"""Deterministic impact analysis: term lookup -> BFS -> reverse mapping."""

from __future__ import annotations

import logging

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.mapping.mapping_models import MappingFile, MappingStatus
from backend.modeling.mapping.mapping_service import MappingService
from backend.modeling.query.query_models import (
    ImpactQuery, ImpactResult, AffectedProcess,
)

logger = logging.getLogger(__name__)


class QueryEngine:
    """100% deterministic impact analysis — no LLM in the data path."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j
        self._mapping_svc = MappingService(neo4j)

    def analyze(self, query: ImpactQuery, mf: MappingFile) -> ImpactResult:
        # Step 1: Resolve term to a code entity
        code_entity = self._resolve_term(query.term, mf)

        if code_entity is None:
            return ImpactResult(
                source_term=query.term,
                source_code_entity=None,
                source_domain=None,
                affected_processes=[],
                unmapped_entities=[],
                resolved=False,
                message=f"'{query.term}'은(는) 매핑되지 않은 용어입니다. 매핑을 추가하시겠습니까?",
            )

        # Step 2: Get source domain mapping
        source_domain = self._mapping_svc.resolve(mf, code_entity)

        # Step 3: BFS traversal — find all code entities that depend on this one
        dependents = self._bfs_dependents(code_entity, query.repo_id, query.depth)

        # Step 4: Reverse mapping — map dependent code entities to domain processes
        affected: list[AffectedProcess] = []
        unmapped: list[str] = []

        for dep in dependents:
            qn = dep["qn"]
            domain = self._mapping_svc.resolve(mf, qn)

            if domain is None:
                unmapped.append(qn)
                continue

            # Filter by confirmed_only
            if query.confirmed_only:
                mapping = next((m for m in mf.mappings if m.code == qn), None)
                if mapping and mapping.status != MappingStatus.CONFIRMED:
                    # Check inherited mapping status
                    parent_mapping = self._find_inherited_mapping(mf, qn)
                    if parent_mapping and parent_mapping.status != MappingStatus.CONFIRMED:
                        continue

            # Get domain name from Neo4j
            domain_info = self._neo4j.query(
                "MATCH (n:DomainNode {id: $id}) RETURN n.name as name",
                {"id": domain},
            )
            domain_name = domain_info[0]["name"] if domain_info else domain

            affected.append(AffectedProcess(
                domain_id=domain,
                domain_name=domain_name,
                path=[code_entity, qn],
                distance=dep["depth"],
            ))

        # Deduplicate by domain_id (keep shortest path)
        seen: dict[str, AffectedProcess] = {}
        for ap in affected:
            if ap.domain_id not in seen or ap.distance < seen[ap.domain_id].distance:
                seen[ap.domain_id] = ap
        affected = list(seen.values())

        message = f"'{query.term}' 변경 시 {len(affected)}개 프로세스에 영향."
        if unmapped:
            message += f" 미매핑 코드 {len(unmapped)}건."

        return ImpactResult(
            source_term=query.term,
            source_code_entity=code_entity,
            source_domain=source_domain,
            affected_processes=affected,
            unmapped_entities=unmapped,
            resolved=True,
            message=message,
        )

    def _resolve_term(self, term: str, mf: MappingFile) -> str | None:
        """Resolve a natural language term to a code entity qualified name."""
        # 1. Direct code entity match (exact or suffix)
        for m in mf.mappings:
            if m.code == term or m.code.endswith(f".{term}"):
                return m.code

        # 2. Domain id match -> find code entity mapped to that domain
        for m in mf.mappings:
            domain_suffix = m.domain.split("/")[-1]
            if term.lower() == domain_suffix.lower() or term.lower() in m.domain.lower():
                return m.code

        return None

    def _bfs_dependents(self, entity: str, repo_id: str, max_depth: int) -> list[dict]:
        """Find all code entities that depend on the given entity (callers, inheritors)."""
        cypher = """
        MATCH (source:CodeEntity {qualified_name: $qn, repo_id: $repo_id})
        MATCH path = (other:CodeEntity)-[:CALLS|EXTENDS|IMPLEMENTS|DEPENDS_ON*1..%d]->(source)
        WHERE other.repo_id = $repo_id
        RETURN DISTINCT other.qualified_name as qn,
               length(path) as depth
        ORDER BY depth
        """ % max_depth
        return self._neo4j.query(cypher, {"qn": entity, "repo_id": repo_id})

    def _find_inherited_mapping(self, mf: MappingFile, qn: str):
        """Find the mapping entry that would apply via inheritance."""
        parts = qn.rsplit(".", 1)
        while len(parts) == 2:
            parent = parts[0]
            for m in mf.mappings:
                if m.code == parent:
                    return m
            parts = parent.rsplit(".", 1)
        return None
