"""Document Confidence Scorer — computed at read-time, not stored.

Replaces binary deprecated/approved with a continuous 0-100 score.
Used by RAG ranking, UI badges, and trust banners.

Signals & weights:
  Freshness (25): linear decay from `updated` — 0 months=100, 24 months=0
  Status (25): deprecated=0, draft=40, review=70, approved=100, unset=50
  Metadata completeness (15): (domain + process + tags>0 + created_by) / 4 × 100
  Backlink count (10): min(backlinks / 3, 1.0) × 100
  Owner activity (10): created_by edited any doc in last 90 days → 100, else 50
  User feedback (15): verified / (verified + needs_update) × 100, no feedback → 50
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from backend.application.trust.scoring_config import SCORING

logger = logging.getLogger(__name__)

# All values from centralized config (see scoring_config.py for tuning)
_W = SCORING.confidence.weights
_T = SCORING.confidence.thresholds
_S = SCORING.confidence.status_scores

W_FRESHNESS = _W.freshness
W_STATUS = _W.status
W_METADATA = _W.metadata
W_BACKLINKS = _W.backlinks
W_OWNER = _W.owner_activity
W_FEEDBACK = _W.user_feedback

STATUS_SCORES: dict[str, float] = {
    "deprecated": _S.deprecated,
    "draft": _S.draft,
    "approved": _S.approved,
}
STATUS_DEFAULT = _S.draft  # unknown/empty status → treated as draft

FRESHNESS_MAX_MONTHS = _T.freshness_decay_months
STALE_MONTHS_THRESHOLD = _T.stale_months


class NewerAlternative(BaseModel):
    path: str
    title: str = ""
    confidence_score: int = 0
    confidence_tier: str = ""


class ConfidenceResult(BaseModel):
    score: int = 50          # 0-100
    tier: str = "medium"     # "high" (70+) | "medium" (40-69) | "low" (0-39)
    stale: bool = False      # updated > 12 months ago
    stale_months: int = 0
    signals: dict[str, float] = {}  # individual signal scores (transparency)
    citation_count: int = 0          # times cited in AI answers
    newer_alternatives: list[NewerAlternative] = []  # higher-confidence docs on same topic


def _months_since(date_str: str) -> float:
    """Parse ISO date string and return months elapsed."""
    if not date_str:
        return FRESHNESS_MAX_MONTHS  # treat missing date as maximally stale
    try:
        # Support both "2024-01-15" and "2024-01-15T10:30:00" formats
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        return max(0.0, delta.days / 30.44)  # average month length
    except (ValueError, TypeError):
        return FRESHNESS_MAX_MONTHS


def _score_freshness(updated: str) -> float:
    """Linear decay: 0 months → 100, 24 months → 0."""
    months = _months_since(updated)
    return max(0.0, 100.0 * (1.0 - months / FRESHNESS_MAX_MONTHS))


def _score_status(status: str) -> float:
    return STATUS_SCORES.get(status.lower().strip(), STATUS_DEFAULT)


def _score_metadata_completeness(meta: dict) -> float:
    """(domain + process + has_tags + created_by) / 4 × 100."""
    checks = [
        bool(meta.get("domain")),
        bool(meta.get("process")),
        bool(meta.get("tags")),
        bool(meta.get("created_by")),
    ]
    return (sum(checks) / 4) * 100.0


def _score_backlinks(backlink_count: int) -> float:
    """min(count / 3, 1.0) × 100 — caps at 3 backlinks."""
    return min(backlink_count / 3.0, 1.0) * 100.0


def _score_owner_activity(is_active: bool) -> float:
    """Active owner (edited in last 90 days) → 100, else 50."""
    return 100.0 if is_active else 50.0


def _score_user_feedback(verified_count: int, needs_update_count: int) -> float:
    """verified / (verified + needs_update) × 100. No feedback → 50 (neutral)."""
    total = verified_count + needs_update_count
    if total == 0:
        return 50.0  # neutral when no feedback exists
    return (verified_count / total) * 100.0


def compute_confidence(
    meta: dict[str, Any],
    backlink_count: int = 0,
    owner_active: bool = False,
    feedback_verified: int = 0,
    feedback_needs_update: int = 0,
) -> ConfidenceResult:
    """Compute confidence score from metadata + contextual signals.

    Args:
        meta: document metadata dict (domain, process, tags, status, updated, created_by)
        backlink_count: number of backlinks pointing to this document
        owner_active: whether created_by has edited a document in the last 90 days
        feedback_verified: number of "verified" feedbacks
        feedback_needs_update: number of "needs_update" feedbacks
    """
    freshness = _score_freshness(meta.get("updated", ""))
    status = _score_status(meta.get("status", ""))
    completeness = _score_metadata_completeness(meta)
    backlinks = _score_backlinks(backlink_count)
    owner = _score_owner_activity(owner_active)
    feedback = _score_user_feedback(feedback_verified, feedback_needs_update)

    weighted = (
        freshness * W_FRESHNESS
        + status * W_STATUS
        + completeness * W_METADATA
        + backlinks * W_BACKLINKS
        + owner * W_OWNER
        + feedback * W_FEEDBACK
    ) / 100.0  # divide by sum of weights (100)

    score = max(0, min(100, round(weighted)))

    # Determine tier (thresholds from scoring_config.py)
    if score >= _T.high_min:
        tier = "high"
    elif score >= _T.medium_min:
        tier = "medium"
    else:
        tier = "low"

    # Stale check
    months = _months_since(meta.get("updated", ""))
    stale = months >= STALE_MONTHS_THRESHOLD

    return ConfidenceResult(
        score=score,
        tier=tier,
        stale=stale,
        stale_months=round(months),
        signals={
            "freshness": round(freshness, 1),
            "status": round(status, 1),
            "metadata_completeness": round(completeness, 1),
            "backlinks": round(backlinks, 1),
            "owner_activity": round(owner, 1),
            "user_feedback": round(feedback, 1),
        },
    )
