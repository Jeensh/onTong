"""Unit tests for Document Confidence Scorer (Phase 1).

Tests the scoring formula: freshness decay, status weights, metadata completeness,
backlink scoring, and owner activity.
"""

import pytest
from datetime import datetime, timezone, timedelta

from backend.application.trust.confidence import (
    compute_confidence,
    ConfidenceResult,
    _score_freshness,
    _score_status,
    _score_metadata_completeness,
    _score_backlinks,
    _score_owner_activity,
    _months_since,
)


class TestFreshnessDecay:
    def test_just_updated(self):
        """Document updated today → freshness ~100."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        score = _score_freshness(today)
        assert score >= 98.0

    def test_one_year_old(self):
        """Document updated 12 months ago → freshness ~50."""
        one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
        score = _score_freshness(one_year_ago)
        assert 45.0 <= score <= 55.0

    def test_two_years_old(self):
        """Document updated 24 months ago → freshness ~0."""
        two_years_ago = (datetime.now(timezone.utc) - timedelta(days=730)).strftime("%Y-%m-%d")
        score = _score_freshness(two_years_ago)
        assert score <= 5.0

    def test_three_years_old(self):
        """Document updated 36 months ago → freshness 0 (capped)."""
        assert _score_freshness((datetime.now(timezone.utc) - timedelta(days=1095)).strftime("%Y-%m-%d")) == 0.0

    def test_empty_date(self):
        """Missing date → max staleness."""
        assert _score_freshness("") == 0.0

    def test_invalid_date(self):
        """Invalid date → max staleness."""
        assert _score_freshness("not-a-date") == 0.0


class TestStatusScore:
    def test_approved(self):
        assert _score_status("approved") == 100.0

    def test_deprecated(self):
        assert _score_status("deprecated") == 0.0

    def test_draft(self):
        assert _score_status("draft") == 40.0

    def test_review(self):
        assert _score_status("review") == 70.0

    def test_empty(self):
        assert _score_status("") == 50.0

    def test_unknown(self):
        assert _score_status("custom_status") == 50.0


class TestMetadataCompleteness:
    def test_fully_complete(self):
        meta = {"domain": "SCM", "process": "P2P", "tags": ["cache"], "created_by": "admin"}
        assert _score_metadata_completeness(meta) == 100.0

    def test_empty(self):
        assert _score_metadata_completeness({}) == 0.0

    def test_partial(self):
        meta = {"domain": "SCM", "process": "", "tags": [], "created_by": "admin"}
        assert _score_metadata_completeness(meta) == 50.0  # 2 of 4


class TestBacklinkScore:
    def test_zero_backlinks(self):
        assert _score_backlinks(0) == 0.0

    def test_one_backlink(self):
        assert abs(_score_backlinks(1) - 33.33) < 1.0

    def test_three_backlinks_cap(self):
        assert _score_backlinks(3) == 100.0

    def test_many_backlinks(self):
        """Capped at 100 regardless of count."""
        assert _score_backlinks(10) == 100.0


class TestOwnerActivity:
    def test_active(self):
        assert _score_owner_activity(True) == 100.0

    def test_inactive(self):
        assert _score_owner_activity(False) == 50.0


class TestComputeConfidence:
    def test_perfect_score(self):
        """Document with all positive signals → high confidence."""
        meta = {
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "status": "approved",
            "domain": "SCM",
            "process": "P2P",
            "tags": ["cache"],
            "created_by": "admin",
        }
        result = compute_confidence(meta, backlink_count=5, owner_active=True)
        assert result.score >= 90
        assert result.tier == "high"
        assert result.stale is False

    def test_deprecated_old_doc(self):
        """Deprecated + 2 years old + no metadata → low confidence."""
        meta = {
            "updated": (datetime.now(timezone.utc) - timedelta(days=730)).strftime("%Y-%m-%d"),
            "status": "deprecated",
            "domain": "",
            "process": "",
            "tags": [],
            "created_by": "",
        }
        result = compute_confidence(meta, backlink_count=0, owner_active=False)
        assert result.score <= 20
        assert result.tier == "low"
        assert result.stale is True

    def test_medium_tier(self):
        """Average document → medium confidence."""
        meta = {
            "updated": (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d"),
            "status": "",
            "domain": "ERP",
            "process": "",
            "tags": ["운영"],
            "created_by": "",
        }
        result = compute_confidence(meta, backlink_count=1, owner_active=False)
        assert 35 <= result.score <= 70
        assert result.tier == "medium"

    def test_stale_flag(self):
        """Document older than 12 months → stale."""
        meta = {"updated": (datetime.now(timezone.utc) - timedelta(days=400)).strftime("%Y-%m-%d")}
        result = compute_confidence(meta)
        assert result.stale is True
        assert result.stale_months >= 12

    def test_not_stale(self):
        """Recent document → not stale."""
        meta = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
        result = compute_confidence(meta)
        assert result.stale is False

    def test_signals_transparency(self):
        """Result includes individual signal scores."""
        meta = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "status": "approved"}
        result = compute_confidence(meta)
        assert "freshness" in result.signals
        assert "status" in result.signals
        assert "metadata_completeness" in result.signals
        assert "backlinks" in result.signals
        assert "owner_activity" in result.signals

    def test_score_clamped(self):
        """Score stays within 0-100."""
        meta = {"updated": "", "status": "deprecated"}
        result = compute_confidence(meta, backlink_count=0, owner_active=False)
        assert 0 <= result.score <= 100
