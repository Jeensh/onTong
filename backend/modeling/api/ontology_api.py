"""API endpoints for domain ontology management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.modeling.ontology.domain_models import DomainNode, DomainNodeKind

router = APIRouter(prefix="/api/modeling/ontology", tags=["modeling-ontology"])

_ontology_store = None


def init(ontology_store):
    global _ontology_store
    _ontology_store = ontology_store


@router.post("/load-template")
async def load_template():
    """Load the SCOR+ISA-95 template into Neo4j."""
    count = _ontology_store.load_template()
    return {"loaded": count}


@router.get("/tree")
async def get_tree():
    """Get the full domain ontology tree."""
    nodes = _ontology_store.get_tree()
    return {"nodes": nodes, "count": len(nodes)}


@router.get("/children/{node_id:path}")
async def get_children(node_id: str):
    """Get child nodes of a domain node."""
    children = _ontology_store.get_children(node_id)
    return {"parent": node_id, "children": children}


class AddNodeRequest(BaseModel):
    id: str
    name: str
    kind: DomainNodeKind = DomainNodeKind.PROCESS
    parent_id: str | None = None
    description: str = ""


@router.post("/node")
async def add_node(req: AddNodeRequest):
    """Add a custom domain node."""
    node = DomainNode(**req.model_dump())
    _ontology_store.add_node(node)
    return {"added": node.id}


class UpdateNodeRequest(BaseModel):
    name: str | None = None
    description: str | None = None


@router.put("/node/{node_id:path}")
async def update_node(node_id: str, req: UpdateNodeRequest):
    """Update a domain node."""
    _ontology_store.update_node(node_id, name=req.name, description=req.description)
    return {"updated": node_id}


@router.delete("/node/{node_id:path}")
async def delete_node(node_id: str):
    """Delete a domain node."""
    _ontology_store.remove_node(node_id)
    return {"deleted": node_id}
