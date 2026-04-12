"""Pydantic models for code-to-domain mappings."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class MappingStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    CONFIRMED = "confirmed"


class MappingGranularity(str, Enum):
    PACKAGE = "package"
    CLASS = "class"
    METHOD = "method"


class Mapping(BaseModel):
    code: str                           # qualified name of code entity
    domain: str                         # domain node id
    granularity: MappingGranularity = MappingGranularity.CLASS
    owner: str = ""
    status: MappingStatus = MappingStatus.DRAFT
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    notes: str = ""


class MappingFile(BaseModel):
    version: str = "1"
    repo_id: str
    mappings: list[Mapping]


class MappingGap(BaseModel):
    qualified_name: str
    kind: str
    file_path: str
    suggested_domain: str | None = None
