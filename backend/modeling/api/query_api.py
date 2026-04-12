"""API endpoint for impact analysis queries."""

from __future__ import annotations

from fastapi import APIRouter

from backend.modeling.query.query_models import ImpactQuery

router = APIRouter(prefix="/api/modeling/impact", tags=["modeling-impact"])

_query_engine = None
_mapping_service = None
_git_connector = None


def init(query_engine, mapping_service, git_connector):
    global _query_engine, _mapping_service, _git_connector
    _query_engine = query_engine
    _mapping_service = mapping_service
    _git_connector = git_connector


def _load_mf(repo_id: str):
    from backend.modeling.api.mapping_api import _yaml_path
    path = _yaml_path(repo_id)
    if not path.exists():
        from backend.modeling.mapping.mapping_models import MappingFile
        return MappingFile(repo_id=repo_id, mappings=[])
    return _mapping_service.load_yaml(path)


@router.post("/analyze")
async def analyze_impact(query: ImpactQuery):
    """Run deterministic impact analysis."""
    mf = _load_mf(query.repo_id)
    result = _query_engine.analyze(query, mf)
    return result.model_dump(mode="json")
