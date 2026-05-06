"""FastAPI router — /api/ontology/repos/{repo_id}/perspectives — view CRUD.

R4-T2.2 / 안건 2 B. 1차 read-only public — 같은 repo 누구나 fetch 가능.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.modeling.view_layer.schema import Perspective, PerspectiveSpec
from backend.modeling.view_layer.store import ViewLayerStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/repos", tags=["ontology-perspective"])


class CreatePerspectiveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    spec: PerspectiveSpec
    owner_id: str | None = None


class UpdatePerspectiveRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    spec: PerspectiveSpec | None = None


@router.get("/{repo_id}/perspectives", response_model=list[Perspective])
def list_perspectives(repo_id: str) -> list[Perspective]:
    return ViewLayerStore().list(repo_id=repo_id)


@router.post("/{repo_id}/perspectives", response_model=Perspective, status_code=201)
def create_perspective(repo_id: str, req: CreatePerspectiveRequest) -> Perspective:
    p = Perspective(
        name=req.name, repo_id=repo_id, description=req.description,
        spec=req.spec, owner_id=req.owner_id,
    )
    return ViewLayerStore().create(p)


@router.get("/{repo_id}/perspectives/{perspective_id}", response_model=Perspective)
def get_perspective(repo_id: str, perspective_id: int) -> Perspective:
    p = ViewLayerStore().get(perspective_id)
    if p is None or p.repo_id != repo_id:
        raise HTTPException(status_code=404, detail=f"perspective {perspective_id} not found in repo {repo_id}")
    return p


@router.put("/{repo_id}/perspectives/{perspective_id}", response_model=Perspective)
def update_perspective(
    repo_id: str, perspective_id: int, req: UpdatePerspectiveRequest,
) -> Perspective:
    store = ViewLayerStore()
    existing = store.get(perspective_id)
    if existing is None or existing.repo_id != repo_id:
        raise HTTPException(status_code=404, detail=f"perspective {perspective_id} not found in repo {repo_id}")
    updated = store.update(
        perspective_id,
        name=req.name, description=req.description, spec=req.spec,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"perspective {perspective_id} not found")
    return updated


@router.delete("/{repo_id}/perspectives/{perspective_id}", status_code=204)
def delete_perspective(repo_id: str, perspective_id: int) -> None:
    store = ViewLayerStore()
    existing = store.get(perspective_id)
    if existing is None or existing.repo_id != repo_id:
        raise HTTPException(status_code=404, detail=f"perspective {perspective_id} not found in repo {repo_id}")
    store.delete(perspective_id)
