"""Pydantic models for impact analysis queries and results."""

from __future__ import annotations

from pydantic import BaseModel


class ImpactQuery(BaseModel):
    """User's impact analysis request."""
    term: str                      # natural language term or code entity name
    repo_id: str
    depth: int = 3                 # BFS traversal depth
    confirmed_only: bool = True    # only use confirmed mappings


class AffectedProcess(BaseModel):
    """A domain process affected by the queried change."""
    domain_id: str
    domain_name: str
    path: list[str]                # code entities in the impact path
    distance: int                  # BFS hops from source


class ImpactResult(BaseModel):
    """Deterministic result of an impact analysis query."""
    source_term: str
    source_code_entity: str | None  # resolved code entity
    source_domain: str | None       # resolved domain mapping
    affected_processes: list[AffectedProcess]
    unmapped_entities: list[str]    # code entities found but not mapped
    resolved: bool                  # whether the term was found in mappings
    message: str                    # human-readable summary
