"""In-memory approval workflow for mapping reviews."""
from __future__ import annotations

from datetime import datetime

from backend.modeling.approval.approval_models import ReviewRequest, ReviewStatus
from backend.modeling.mapping.mapping_models import MappingFile, MappingStatus


class ApprovalService:
    """Manages review requests for code-to-domain mappings."""

    def __init__(self) -> None:
        self._reviews: list[ReviewRequest] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_review(self, review_id: str) -> ReviewRequest:
        for r in self._reviews:
            if r.id == review_id:
                return r
        raise ValueError(f"Review not found: {review_id}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_review(
        self,
        mapping_code: str,
        mapping_domain: str,
        repo_id: str,
        requested_by: str,
        impact_summary: str = "",
    ) -> ReviewRequest:
        review = ReviewRequest(
            mapping_code=mapping_code,
            mapping_domain=mapping_domain,
            repo_id=repo_id,
            requested_by=requested_by,
            impact_summary=impact_summary,
        )
        self._reviews.append(review)
        return review

    def approve(
        self,
        review_id: str,
        reviewer: str,
        mf: MappingFile,
    ) -> tuple[ReviewRequest, MappingFile]:
        review = self._get_review(review_id)
        review.status = ReviewStatus.APPROVED
        review.reviewer = reviewer
        review.reviewed_at = datetime.now()

        # Set the corresponding mapping to CONFIRMED
        for m in mf.mappings:
            if m.code == review.mapping_code:
                m.status = MappingStatus.CONFIRMED
                m.confirmed_by = reviewer
                m.confirmed_at = datetime.now()
                break

        return review, mf

    def reject(
        self,
        review_id: str,
        reviewer: str,
        comment: str,
        mf: MappingFile,
    ) -> tuple[ReviewRequest, MappingFile]:
        review = self._get_review(review_id)
        review.status = ReviewStatus.REJECTED
        review.reviewer = reviewer
        review.reviewed_at = datetime.now()
        review.comment = comment

        # Revert the corresponding mapping to DRAFT
        for m in mf.mappings:
            if m.code == review.mapping_code:
                m.status = MappingStatus.DRAFT
                break

        return review, mf

    def list_pending(self, repo_id: str) -> list[ReviewRequest]:
        return [
            r
            for r in self._reviews
            if r.repo_id == repo_id and r.status == ReviewStatus.PENDING
        ]

    def list_all(self, repo_id: str) -> list[ReviewRequest]:
        return [r for r in self._reviews if r.repo_id == repo_id]
