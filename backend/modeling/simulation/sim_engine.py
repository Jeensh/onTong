"""Simulation engine: run parametric simulations and trace domain impact."""
from __future__ import annotations

import logging

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.mapping.mapping_models import MappingFile
from backend.modeling.mapping.mapping_service import MappingService
from backend.modeling.simulation.sim_models import (
    AffectedProcessRef,
    ParametricSimResult,
)
from backend.modeling.simulation.sim_registry import SimRegistry

logger = logging.getLogger(__name__)


class SimulationEngine:
    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j
        self._mapping_svc = MappingService(neo4j)

    def simulate(
        self,
        entity_id: str,
        params: dict[str, str],
        repo_id: str,
        mf: MappingFile,
    ) -> ParametricSimResult:
        simple_name = entity_id.rsplit(".", 1)[-1] if "." in entity_id else entity_id

        if not SimRegistry.has_entity(entity_id):
            return ParametricSimResult(
                entity_id=entity_id,
                entity_name=simple_name,
                params_before={},
                params_after={},
                outputs=[],
                affected_processes=[],
                message=f"'{simple_name}'은(는) 지원되지 않는 시뮬레이션 대상입니다.",
            )

        # Fill missing params with defaults
        registered_params = SimRegistry.get_params(entity_id)
        defaults = {p.param_name: p.default_value for p in registered_params}
        full_params = {**defaults, **params}

        # Run calculation
        outputs = SimRegistry.calculate(entity_id, full_params)

        # Trace affected domain processes via BFS
        affected = self._trace_affected_processes(entity_id, repo_id, mf)

        change_count = sum(1 for o in outputs if abs(o.change_pct) > 0.01)
        message = (
            f"{simple_name}: {change_count}개 지표 변경, "
            f"{len(affected)}개 프로세스 영향"
        )

        return ParametricSimResult(
            entity_id=entity_id,
            entity_name=simple_name,
            params_before=defaults,
            params_after=full_params,
            outputs=outputs,
            affected_processes=affected,
            message=message,
        )

    def _trace_affected_processes(
        self, entity_id: str, repo_id: str, mf: MappingFile
    ) -> list[AffectedProcessRef]:
        # 1. Get direct domain mapping for this entity
        source_domain = self._mapping_svc.resolve(mf, entity_id)
        affected: list[AffectedProcessRef] = []

        if source_domain:
            domain_info = self._neo4j.query(
                "MATCH (n:DomainNode {id: $id}) RETURN n.name as name",
                {"id": source_domain},
            )
            domain_name = domain_info[0]["name"] if domain_info else source_domain
            affected.append(AffectedProcessRef(
                domain_id=source_domain, domain_name=domain_name, distance=0,
            ))

        # 2. BFS for dependents (same logic as QueryEngine)
        cypher = """
        MATCH (source:CodeEntity {qualified_name: $qn, repo_id: $repo_id})
        MATCH path = (other:CodeEntity)-[:CALLS|EXTENDS|IMPLEMENTS|DEPENDS_ON*1..3]->(source)
        WHERE other.repo_id = $repo_id
        RETURN DISTINCT other.qualified_name as qn, length(path) as depth
        ORDER BY depth
        """
        dependents = self._neo4j.query(cypher, {"qn": entity_id, "repo_id": repo_id})

        seen_domains: set[str] = {source_domain} if source_domain else set()
        for dep in dependents:
            domain = self._mapping_svc.resolve(mf, dep["qn"])
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                domain_info = self._neo4j.query(
                    "MATCH (n:DomainNode {id: $id}) RETURN n.name as name",
                    {"id": domain},
                )
                domain_name = domain_info[0]["name"] if domain_info else domain
                affected.append(AffectedProcessRef(
                    domain_id=domain, domain_name=domain_name, distance=dep["depth"],
                ))

        return affected
