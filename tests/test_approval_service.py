"""Tests for the approval workflow service."""
import pytest

from backend.modeling.approval.approval_models import ReviewStatus
from backend.modeling.approval.approval_service import ApprovalService
from backend.modeling.mapping.mapping_models import (
    Mapping,
    MappingFile,
    MappingStatus,
)


def _make_mapping_file(*codes: str, repo_id: str = "repo-1") -> MappingFile:
    """Helper to build a MappingFile with REVIEW-status mappings."""
    return MappingFile(
        repo_id=repo_id,
        mappings=[
            Mapping(code=c, domain=f"domain.{c}", status=MappingStatus.REVIEW)
            for c in codes
        ],
    )


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_create_review_request():
    svc = ApprovalService()
    review = svc.create_review(
        mapping_code="com.example.OrderService",
        mapping_domain="scor.source",
        repo_id="repo-1",
        requested_by="alice",
        impact_summary="Maps order service to SCOR Source",
    )

    assert review.status == ReviewStatus.PENDING
    assert review.mapping_code == "com.example.OrderService"
    assert review.requested_by == "alice"
    assert review.impact_summary == "Maps order service to SCOR Source"
    assert len(review.id) == 12


def test_approve_review():
    svc = ApprovalService()
    mf = _make_mapping_file("com.example.OrderService")

    review = svc.create_review(
        mapping_code="com.example.OrderService",
        mapping_domain="scor.source",
        repo_id="repo-1",
        requested_by="alice",
    )

    updated_review, updated_mf = svc.approve(review.id, "bob", mf)

    assert updated_review.status == ReviewStatus.APPROVED
    assert updated_review.reviewer == "bob"
    assert updated_review.reviewed_at is not None

    mapping = updated_mf.mappings[0]
    assert mapping.status == MappingStatus.CONFIRMED
    assert mapping.confirmed_by == "bob"


def test_reject_review():
    svc = ApprovalService()
    mf = _make_mapping_file("com.example.OrderService")

    review = svc.create_review(
        mapping_code="com.example.OrderService",
        mapping_domain="scor.source",
        repo_id="repo-1",
        requested_by="alice",
    )

    updated_review, updated_mf = svc.reject(
        review.id, "bob", "Domain mismatch", mf
    )

    assert updated_review.status == ReviewStatus.REJECTED
    assert updated_review.reviewer == "bob"
    assert updated_review.comment == "Domain mismatch"

    mapping = updated_mf.mappings[0]
    assert mapping.status == MappingStatus.DRAFT


def test_list_pending_reviews():
    svc = ApprovalService()

    svc.create_review(
        mapping_code="com.example.A",
        mapping_domain="domain.a",
        repo_id="repo-1",
        requested_by="alice",
    )
    svc.create_review(
        mapping_code="com.example.B",
        mapping_domain="domain.b",
        repo_id="repo-1",
        requested_by="alice",
    )
    # Different repo — should not appear
    svc.create_review(
        mapping_code="com.example.C",
        mapping_domain="domain.c",
        repo_id="repo-2",
        requested_by="alice",
    )

    pending = svc.list_pending("repo-1")
    assert len(pending) == 2
    assert all(r.status == ReviewStatus.PENDING for r in pending)


def test_approve_nonexistent_raises():
    svc = ApprovalService()
    mf = _make_mapping_file("com.example.A")

    with pytest.raises(ValueError, match="Review not found"):
        svc.approve("nonexistent-id", "bob", mf)
