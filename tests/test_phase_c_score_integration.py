"""Phase C — Score Integration tests.

Tests:
- _score_user_feedback: ratio calculation, edge cases
- compute_confidence with feedback: score changes
- ConfidenceService._get_feedback_counts: with/without tracker
- Weight sum validation: all weights sum to 100
- Verified → freshness refresh logic
"""

import pytest
from datetime import datetime, timezone

from backend.application.trust.confidence import (
    _score_user_feedback,
    compute_confidence,
    ConfidenceResult,
    W_FRESHNESS,
    W_STATUS,
    W_METADATA,
    W_BACKLINKS,
    W_OWNER,
    W_FEEDBACK,
)
from backend.application.trust.scoring_config import SCORING


# ── Weight Configuration ────────────────────────────────────────

class TestWeightConfig:
    def test_weights_sum_to_100(self):
        w = SCORING.confidence.weights
        total = w.freshness + w.status + w.metadata + w.backlinks + w.owner_activity + w.user_feedback
        assert total == 100, f"Weights sum to {total}, expected 100"

    def test_user_feedback_weight_is_15(self):
        assert SCORING.confidence.weights.user_feedback == 15

    def test_rebalanced_weights(self):
        w = SCORING.confidence.weights
        assert w.freshness == 25
        assert w.backlinks == 10
        assert w.owner_activity == 10


# ── _score_user_feedback ────────────────────────────────────────

class TestScoreUserFeedback:
    def test_no_feedback_returns_neutral(self):
        assert _score_user_feedback(0, 0) == 50.0

    def test_all_verified(self):
        assert _score_user_feedback(5, 0) == 100.0

    def test_all_needs_update(self):
        assert _score_user_feedback(0, 5) == 0.0

    def test_half_and_half(self):
        assert _score_user_feedback(3, 3) == 50.0

    def test_ratio_calculation(self):
        # 3 verified, 1 needs_update → 75%
        score = _score_user_feedback(3, 1)
        assert score == 75.0

    def test_single_verified(self):
        assert _score_user_feedback(1, 0) == 100.0

    def test_single_needs_update(self):
        assert _score_user_feedback(0, 1) == 0.0


# ── compute_confidence with feedback ────────────────────────────

class TestComputeConfidenceWithFeedback:
    """Test that feedback signal affects the final score."""

    def _base_meta(self) -> dict:
        """Metadata for a recently updated, approved, fully tagged doc."""
        now = datetime.now(timezone.utc).isoformat()
        return {
            "updated": now,
            "status": "approved",
            "domain": "dev",
            "process": "build",
            "tags": ["test"],
            "created_by": "admin",
        }

    def test_no_feedback_gives_neutral_contribution(self):
        result = compute_confidence(self._base_meta(), backlink_count=3, owner_active=True)
        assert "user_feedback" in result.signals
        assert result.signals["user_feedback"] == 50.0

    def test_all_verified_boosts_score(self):
        base = compute_confidence(self._base_meta(), backlink_count=3, owner_active=True)
        boosted = compute_confidence(
            self._base_meta(), backlink_count=3, owner_active=True,
            feedback_verified=10, feedback_needs_update=0,
        )
        assert boosted.score >= base.score
        assert boosted.signals["user_feedback"] == 100.0

    def test_all_needs_update_lowers_score(self):
        base = compute_confidence(self._base_meta(), backlink_count=3, owner_active=True)
        lowered = compute_confidence(
            self._base_meta(), backlink_count=3, owner_active=True,
            feedback_verified=0, feedback_needs_update=10,
        )
        assert lowered.score <= base.score
        assert lowered.signals["user_feedback"] == 0.0

    def test_feedback_signal_in_output(self):
        result = compute_confidence(
            self._base_meta(), feedback_verified=3, feedback_needs_update=1,
        )
        assert "user_feedback" in result.signals
        assert result.signals["user_feedback"] == 75.0

    def test_score_difference_from_feedback(self):
        """All-verified vs all-needs_update should differ by exactly W_FEEDBACK points."""
        meta = self._base_meta()
        high = compute_confidence(meta, feedback_verified=10, feedback_needs_update=0)
        low = compute_confidence(meta, feedback_verified=0, feedback_needs_update=10)
        # Difference should be W_FEEDBACK * (100 - 0) / 100 = W_FEEDBACK
        expected_diff = W_FEEDBACK  # 15
        actual_diff = high.score - low.score
        # Allow ±1 for rounding
        assert abs(actual_diff - expected_diff) <= 1, f"Diff {actual_diff} != expected {expected_diff}"


# ── ConfidenceService feedback integration ──────────────────────

class TestConfidenceServiceFeedback:
    def test_get_feedback_counts_no_tracker(self):
        """Without feedback tracker, returns (0, 0)."""
        from unittest.mock import MagicMock
        from backend.application.trust.confidence_service import ConfidenceService

        mock_meta = MagicMock()
        svc = ConfidenceService(mock_meta, "/tmp/wiki")
        assert svc._get_feedback_counts("any.md") == (0, 0)

    def test_get_feedback_counts_with_tracker(self):
        """With feedback tracker, returns actual counts."""
        from unittest.mock import MagicMock
        from backend.application.trust.confidence_service import ConfidenceService
        from backend.application.trust.feedback_tracker import FeedbackSummary

        mock_meta = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_feedback_summary.return_value = FeedbackSummary(
            verified_count=5, needs_update_count=2,
        )

        svc = ConfidenceService(mock_meta, "/tmp/wiki")
        svc.set_feedback_tracker(mock_tracker)
        assert svc._get_feedback_counts("doc.md") == (5, 2)

    def test_get_feedback_counts_tracker_error(self):
        """If tracker raises, returns (0, 0)."""
        from unittest.mock import MagicMock
        from backend.application.trust.confidence_service import ConfidenceService

        mock_meta = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.get_feedback_summary.side_effect = RuntimeError("boom")

        svc = ConfidenceService(mock_meta, "/tmp/wiki")
        svc.set_feedback_tracker(mock_tracker)
        assert svc._get_feedback_counts("doc.md") == (0, 0)


# ── Verified → freshness refresh ────────────────────────────────

class TestVerifiedFreshnessRefresh:
    def test_refresh_updates_frontmatter(self, tmp_path):
        """Simulates _refresh_document_timestamp logic."""
        import yaml

        doc = tmp_path / "test.md"
        doc.write_text(
            "---\ntitle: Test\nupdated: '2024-01-01'\ncreated_by: admin\n---\nContent here\n",
            encoding="utf-8",
        )

        # Simulate what _refresh_document_timestamp does
        raw = doc.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        fm = yaml.safe_load(parts[1]) or {}
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        fm["updated"] = now_iso
        fm["updated_by"] = "verifier"
        new_raw = "---\n" + yaml.dump(fm, allow_unicode=True, default_flow_style=False) + "---" + parts[2]
        doc.write_text(new_raw, encoding="utf-8")

        # Verify
        raw2 = doc.read_text(encoding="utf-8")
        parts2 = raw2.split("---", 2)
        fm2 = yaml.safe_load(parts2[1])
        assert fm2["updated"] == now_iso
        assert fm2["updated_by"] == "verifier"
        assert fm2["title"] == "Test"
        assert "Content here" in parts2[2]

    def test_refresh_preserves_content(self, tmp_path):
        """Ensures document body is not modified."""
        import yaml

        content_body = "\n# Important\n\nThis is the actual content.\n"
        doc = tmp_path / "test.md"
        doc.write_text(
            f"---\ntitle: Doc\nupdated: '2023-06-01'\n---{content_body}",
            encoding="utf-8",
        )

        raw = doc.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        fm = yaml.safe_load(parts[1]) or {}
        fm["updated"] = datetime.now(timezone.utc).isoformat()
        new_raw = "---\n" + yaml.dump(fm, allow_unicode=True, default_flow_style=False) + "---" + parts[2]
        doc.write_text(new_raw, encoding="utf-8")

        raw2 = doc.read_text(encoding="utf-8")
        assert content_body in raw2
