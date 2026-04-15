# backend/modeling/api/engine_api.py
"""Engine API — unified entry for analysis console and simulation."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.modeling.query.query_models import ImpactQuery, ImpactResult
from backend.modeling.simulation.sim_models import ParametricSimResult
from backend.modeling.simulation.sim_registry import SimRegistry

router = APIRouter(prefix="/api/modeling/engine", tags=["modeling-engine"])
logger = logging.getLogger(__name__)

_query_engine = None
_mapping_svc = None
_sim_engine = None
_term_resolver = None
_git = None
_load_mapping_file = None


def init(query_engine, mapping_svc, sim_engine, term_resolver, git) -> None:
    global _query_engine, _mapping_svc, _sim_engine, _term_resolver, _git, _load_mapping_file
    _query_engine = query_engine
    _mapping_svc = mapping_svc
    _sim_engine = sim_engine
    _term_resolver = term_resolver
    _git = git

    def _load_mf(repo_id: str):
        from backend.modeling.mapping.yaml_store import load_mapping_yaml
        mf_path = Path("/tmp/ontong-repos") / repo_id / ".ontology" / "mapping.yaml"
        if not mf_path.exists():
            from backend.modeling.mapping.mapping_models import MappingFile
            return MappingFile(repo_id=repo_id, mappings=[])
        return load_mapping_yaml(mf_path)

    _load_mapping_file = _load_mf


class EngineQueryRequest(BaseModel):
    query: str
    repo_id: str
    depth: int = Field(default=3, ge=1, le=10)
    use_llm: bool = False


class EngineSimulateRequest(BaseModel):
    entity_id: str
    repo_id: str
    params: dict[str, str]


@router.post("/query")
async def engine_query(req: EngineQueryRequest) -> ImpactResult:
    if _query_engine is None:
        raise HTTPException(503, "Engine not initialized")

    mf = _load_mapping_file(req.repo_id)

    if req.use_llm:
        resolved = await _term_resolver.resolve_with_llm(req.query, mf)
    else:
        resolved = _term_resolver.resolve_deterministic(req.query, mf)

    if resolved is None:
        return ImpactResult(
            source_term=req.query,
            source_code_entity=None,
            source_domain=None,
            affected_processes=[],
            unmapped_entities=[],
            resolved=False,
            message=f"'{req.query}'에 해당하는 코드 엔티티를 찾을 수 없습니다.",
        )

    impact_query = ImpactQuery(
        term=resolved, repo_id=req.repo_id,
        depth=req.depth, confirmed_only=False,
    )
    return _query_engine.analyze(impact_query, mf)


@router.post("/simulate")
async def engine_simulate(req: EngineSimulateRequest) -> ParametricSimResult:
    if _sim_engine is None:
        raise HTTPException(503, "Engine not initialized")

    mf = _load_mapping_file(req.repo_id)
    return _sim_engine.simulate(
        entity_id=req.entity_id,
        params=req.params,
        repo_id=req.repo_id,
        mf=mf,
    )


@router.get("/params/{entity_id:path}")
async def engine_params(entity_id: str) -> dict:
    params = SimRegistry.get_params(entity_id)
    return {"entity_id": entity_id, "params": [p.model_dump() for p in params]}


@router.get("/status")
async def engine_status(repo_id: str = "scm-demo") -> dict:
    mf = _load_mapping_file(repo_id) if _load_mapping_file else None
    mapping_count = len(mf.mappings) if mf else 0
    sim_entities = SimRegistry.all_entity_ids()
    simulatable_in_repo = [
        eid for eid in sim_entities
        if mf and any(m.code == eid for m in mf.mappings)
    ]
    return {
        "repo_id": repo_id,
        "mapping_count": mapping_count,
        "total_mappings": mapping_count,
        "simulatable_entities": len(simulatable_in_repo),
        "total_registered": len(sim_entities),
        "ready": mapping_count > 0,
    }
