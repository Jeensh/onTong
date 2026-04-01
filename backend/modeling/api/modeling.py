"""Section 2 Modeling API — code analysis, ontology, impact analysis.

Endpoints:
    GET  /api/modeling/health             → Section 2 health check
    POST /api/modeling/simulation/scenario → Submit simulation (Section 3 calls this)
    GET  /api/modeling/simulation/job/{id} → Poll job status
    GET  /api/modeling/simulation/scenarios → Available scenario types

Phase 1+ endpoints (not yet implemented):
    POST /api/modeling/code/parse          → Parse code with tree-sitter
    GET  /api/modeling/ontology/graph      → Get ontology graph
    POST /api/modeling/impact/analyze      → Run impact analysis (BFS)
    GET  /api/modeling/mapping/status      → Mapping confidence overview
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/modeling", tags=["modeling"])


def init() -> None:
    """Initialize Section 2 API (dependency injection placeholder)."""
    logger.info("Modeling API initialized")


@router.get("/health")
async def health():
    """Section 2 health check."""
    return {
        "section": "modeling",
        "status": "healthy",
        "phase": "0-scaffolding",
        "capabilities": [
            "code_analysis (Phase 1)",
            "ontology_management (Phase 1)",
            "impact_analysis (Phase 1)",
            "simulation_execution (Phase 2)",
        ],
    }
