"""Pydantic models for SCOR+ISA-95 domain ontology."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class DomainNodeKind(str, Enum):
    PROCESS = "process"
    ENTITY = "entity"
    ROLE = "role"


class DomainRelationKind(str, Enum):
    PART_OF = "part_of"
    USES = "uses"
    PRODUCES = "produces"
    RESPONSIBLE_FOR = "responsible_for"


class DomainNode(BaseModel):
    kind: DomainNodeKind
    id: str  # e.g., "SCOR/Plan/DemandPlanning"
    name: str  # e.g., "Demand Planning"
    description: str = ""
    parent_id: str | None = None
    metadata: dict = {}


class DomainRelation(BaseModel):
    kind: DomainRelationKind
    source_id: str
    target_id: str


class DomainOntology(BaseModel):
    nodes: list[DomainNode]
    relations: list[DomainRelation]
