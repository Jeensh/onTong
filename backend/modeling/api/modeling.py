"""Section 2 Modeling API — main router aggregator."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter

from backend.modeling.api import code_api, ontology_api, mapping_api, query_api, seed_api, engine_api
from backend.modeling.api import approval_api as modeling_approval_api

logger = logging.getLogger(__name__)

router = APIRouter(tags=["modeling"])

# Include sub-routers
router.include_router(code_api.router)
router.include_router(ontology_api.router)
router.include_router(mapping_api.router)
router.include_router(query_api.router)
router.include_router(modeling_approval_api.router)
router.include_router(seed_api.router)
router.include_router(engine_api.router)


def init(neo4j_client=None, repos_dir: Path | None = None) -> None:
    """Initialize Section 2 API with dependencies."""
    if neo4j_client is None:
        logger.info("Modeling API initialized (no Neo4j — limited mode)")
        return

    from backend.modeling.infrastructure.git_connector import GitConnector
    from backend.modeling.code_analysis.java_parser import JavaParser
    from backend.modeling.code_analysis.graph_writer import CodeGraphWriter
    from backend.modeling.ontology.ontology_store import OntologyStore
    from backend.modeling.mapping.mapping_service import MappingService
    from backend.modeling.query.query_engine import QueryEngine
    from backend.modeling.approval.approval_service import ApprovalService

    git = GitConnector(repos_dir or Path("/tmp/ontong-repos"))
    parser = JavaParser()
    writer = CodeGraphWriter(neo4j_client)
    onto_store = OntologyStore(neo4j_client)
    mapping_svc = MappingService(neo4j_client)
    query_eng = QueryEngine(neo4j_client)
    approval_svc = ApprovalService()

    code_api.init(git, parser, writer)
    ontology_api.init(onto_store)
    mapping_api.init(mapping_svc, git)
    query_api.init(query_eng, mapping_svc, git)
    modeling_approval_api.init(approval_svc, mapping_svc, git)
    seed_api.init(parser, writer, onto_store, mapping_svc)

    from backend.modeling.simulation.sim_engine import SimulationEngine
    from backend.modeling.query.term_resolver import TermResolver

    sim_engine = SimulationEngine(neo4j_client)
    term_resolver = TermResolver()

    engine_api.init(query_eng, mapping_svc, sim_engine, term_resolver, git)

    logger.info("Modeling API fully initialized with Neo4j")


@router.get("/api/modeling/health")
async def health():
    """Section 2 health check."""
    return {
        "section": "modeling",
        "status": "healthy",
        "phase": "1-mvp",
        "capabilities": [
            "code_analysis",
            "ontology_management",
            "mapping_management",
            "impact_analysis",
            "approval_workflow",
            "simulation",
            "engine_query",
        ],
    }
