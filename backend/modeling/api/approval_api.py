"""API endpoints for mapping approval workflow."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/modeling/approval", tags=["modeling-approval"])

_approval_service = None
_mapping_service = None
_git_connector = None


def init(approval_service, mapping_service, git_connector):
    global _approval_service, _mapping_service, _git_connector
    _approval_service = approval_service
    _mapping_service = mapping_service
    _git_connector = git_connector


def _load_mf(repo_id: str):
    from backend.modeling.api.mapping_api import _yaml_path
    path = _yaml_path(repo_id)
    if not path.exists():
        from backend.modeling.mapping.mapping_models import MappingFile
        return MappingFile(repo_id=repo_id, mappings=[])
    return _mapping_service.load_yaml(path)


def _save_mf(repo_id: str, mf):
    from backend.modeling.api.mapping_api import _yaml_path
    _mapping_service.save_yaml(_yaml_path(repo_id), mf)


class SubmitReviewRequest(BaseModel):
    mapping_code: str
    mapping_domain: str
    repo_id: str
    requested_by: str


@router.post("/submit")
async def submit_review(req: SubmitReviewRequest):
    """Submit a mapping for business review."""
    # Update mapping status to review
    mf = _load_mf(req.repo_id)
    _mapping_service.update_status(mf, req.mapping_code, "review")
    _save_mf(req.repo_id, mf)

    review = _approval_service.create_review(
        req.mapping_code, req.mapping_domain, req.repo_id, req.requested_by,
    )
    return review.model_dump(mode="json")


class ApproveRequest(BaseModel):
    reviewer: str


@router.post("/{review_id}/approve")
async def approve(review_id: str, req: ApproveRequest):
    """Business user approves a mapping."""
    review = _approval_service._get_review(review_id)
    mf = _load_mf(review.repo_id)
    review, mf = _approval_service.approve(review_id, req.reviewer, mf)
    _save_mf(review.repo_id, mf)
    return review.model_dump(mode="json")


class RejectRequest(BaseModel):
    reviewer: str
    comment: str


@router.post("/{review_id}/reject")
async def reject(review_id: str, req: RejectRequest):
    """Business user rejects a mapping."""
    review = _approval_service._get_review(review_id)
    mf = _load_mf(review.repo_id)
    review, mf = _approval_service.reject(review_id, req.reviewer, req.comment, mf)
    _save_mf(review.repo_id, mf)
    return review.model_dump(mode="json")


@router.get("/pending/{repo_id}")
async def list_pending(repo_id: str):
    """List pending review requests."""
    reviews = _approval_service.list_pending(repo_id)
    return {"reviews": [r.model_dump(mode="json") for r in reviews]}
