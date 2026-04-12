"""API endpoints for code-domain mapping management."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.modeling.mapping.mapping_models import Mapping, MappingStatus, MappingGranularity

router = APIRouter(prefix="/api/modeling/mapping", tags=["modeling-mapping"])

_mapping_service = None
_git_connector = None


def init(mapping_service, git_connector):
    global _mapping_service, _git_connector
    _mapping_service = mapping_service
    _git_connector = git_connector


def _yaml_path(repo_id: str) -> Path:
    return _git_connector.repos_dir / repo_id / ".ontology" / "mapping.yaml"


def _load_mf(repo_id: str):
    path = _yaml_path(repo_id)
    if not path.exists():
        from backend.modeling.mapping.mapping_models import MappingFile
        return MappingFile(repo_id=repo_id, mappings=[])
    return _mapping_service.load_yaml(path)


@router.get("/{repo_id}")
async def get_mappings(repo_id: str):
    """Get all mappings for a repo."""
    mf = _load_mf(repo_id)
    return {"repo_id": repo_id, "mappings": [m.model_dump(mode="json") for m in mf.mappings]}


class AddMappingRequest(BaseModel):
    code: str
    domain: str
    granularity: MappingGranularity = MappingGranularity.CLASS
    owner: str = ""


@router.post("/{repo_id}")
async def add_mapping(repo_id: str, req: AddMappingRequest):
    """Add a new code-domain mapping."""
    mf = _load_mf(repo_id)
    mapping = Mapping(**req.model_dump())
    try:
        mf = _mapping_service.add_mapping(mf, mapping)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _mapping_service.save_yaml(_yaml_path(repo_id), mf)
    _mapping_service.sync_to_neo4j(mf)
    return {"added": req.code}


@router.delete("/{repo_id}/{code:path}")
async def remove_mapping(repo_id: str, code: str):
    """Remove a mapping."""
    mf = _load_mf(repo_id)
    mf = _mapping_service.remove_mapping(mf, code)
    _mapping_service.save_yaml(_yaml_path(repo_id), mf)
    _mapping_service.sync_to_neo4j(mf)
    return {"removed": code}


@router.get("/{repo_id}/gaps")
async def get_gaps(repo_id: str):
    """Find unmapped code entities."""
    mf = _load_mf(repo_id)
    gaps = _mapping_service.find_gaps(mf, repo_id)
    return {"repo_id": repo_id, "gaps": [g.model_dump() for g in gaps], "count": len(gaps)}


@router.get("/{repo_id}/resolve/{qualified_name:path}")
async def resolve_mapping(repo_id: str, qualified_name: str):
    """Resolve the domain mapping for a code entity (with inheritance)."""
    mf = _load_mf(repo_id)
    domain = _mapping_service.resolve(mf, qualified_name)
    return {"code": qualified_name, "domain": domain, "resolved": domain is not None}
