"""Pydantic models for mapping approval workflow."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewRequest(BaseModel):
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex[:12])
    mapping_code: str
    mapping_domain: str
    repo_id: str
    requested_by: str
    requested_at: datetime = Field(default_factory=datetime.now)
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    comment: str = ""
    impact_summary: str = ""
