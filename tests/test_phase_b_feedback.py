"""Phase B — User Feedback Loop tests.

Tests:
- InMemoryFeedbackStore: record, get_summary, get_batch
- FeedbackTracker: record_feedback validation, summary
- FeedbackSummary model defaults
"""

import time
import pytest

from backend.application.trust.feedback_tracker import (
    InMemoryFeedbackStore,
    FeedbackTracker,
    FeedbackSummary,
    VALID_ACTIONS,
)


# ── InMemoryFeedbackStore ────────────────────────────────────────

class TestInMemoryFeedbackStore:
    def test_record_and_get_summary(self):
        store = InMemoryFeedbackStore()
        store.record("docs/a.md", "admin", "verified")
        store.record("docs/a.md", "user1", "verified")
        store.record("docs/a.md", "user2", "needs_update")

        summary = store.get_summary("docs/a.md")
        assert summary.verified_count == 2
        assert summary.needs_update_count == 1
        assert summary.last_verified_by == "user1"
        assert summary.last_verified_at > 0

    def test_get_summary_empty(self):
        store = InMemoryFeedbackStore()
        summary = store.get_summary("nonexistent.md")
        assert summary.verified_count == 0
        assert summary.needs_update_count == 0
        assert summary.last_verified_by == ""

    def test_thumbs_actions(self):
        store = InMemoryFeedbackStore()
        store.record("docs/a.md", "user1", "thumbs_up")
        store.record("docs/a.md", "user2", "thumbs_down")
        store.record("docs/a.md", "user3", "thumbs_up")

        summary = store.get_summary("docs/a.md")
        assert summary.thumbs_up_count == 2
        assert summary.thumbs_down_count == 1

    def test_get_batch(self):
        store = InMemoryFeedbackStore()
        store.record("docs/a.md", "admin", "verified")
        store.record("docs/b.md", "admin", "needs_update")

        batch = store.get_batch(["docs/a.md", "docs/b.md", "docs/c.md"])
        assert batch["docs/a.md"].verified_count == 1
        assert batch["docs/b.md"].needs_update_count == 1
        assert batch["docs/c.md"].verified_count == 0

    def test_multiple_files_independent(self):
        store = InMemoryFeedbackStore()
        store.record("docs/a.md", "admin", "verified")
        store.record("docs/b.md", "admin", "verified")

        assert store.get_summary("docs/a.md").verified_count == 1
        assert store.get_summary("docs/b.md").verified_count == 1


# ── FeedbackTracker ──────────────────────────────────────────────

class TestFeedbackTracker:
    def test_record_feedback_returns_summary(self):
        store = InMemoryFeedbackStore()
        tracker = FeedbackTracker(store)

        summary = tracker.record_feedback("docs/a.md", "admin", "verified")
        assert summary.verified_count == 1
        assert summary.last_verified_by == "admin"

    def test_record_feedback_invalid_action(self):
        store = InMemoryFeedbackStore()
        tracker = FeedbackTracker(store)

        with pytest.raises(ValueError, match="Invalid action"):
            tracker.record_feedback("docs/a.md", "admin", "invalid_action")

    def test_valid_actions(self):
        store = InMemoryFeedbackStore()
        tracker = FeedbackTracker(store)

        for action in VALID_ACTIONS:
            tracker.record_feedback("docs/test.md", "user", action)

        summary = tracker.get_feedback_summary("docs/test.md")
        assert summary.verified_count == 1
        assert summary.needs_update_count == 1
        assert summary.thumbs_up_count == 1
        assert summary.thumbs_down_count == 1

    def test_get_feedback_summary(self):
        store = InMemoryFeedbackStore()
        tracker = FeedbackTracker(store)
        tracker.record_feedback("docs/a.md", "admin", "verified")
        tracker.record_feedback("docs/a.md", "user1", "needs_update")

        summary = tracker.get_feedback_summary("docs/a.md")
        assert summary.verified_count == 1
        assert summary.needs_update_count == 1

    def test_get_batch(self):
        store = InMemoryFeedbackStore()
        tracker = FeedbackTracker(store)
        tracker.record_feedback("docs/a.md", "admin", "verified")

        batch = tracker.get_batch(["docs/a.md", "docs/b.md"])
        assert batch["docs/a.md"].verified_count == 1
        assert batch["docs/b.md"].verified_count == 0


# ── FeedbackSummary model ───────────────────────────────────────

class TestFeedbackSummary:
    def test_defaults(self):
        s = FeedbackSummary()
        assert s.verified_count == 0
        assert s.needs_update_count == 0
        assert s.thumbs_up_count == 0
        assert s.thumbs_down_count == 0
        assert s.last_verified_at == 0.0
        assert s.last_verified_by == ""

    def test_serialization(self):
        s = FeedbackSummary(
            verified_count=3,
            needs_update_count=1,
            last_verified_at=1234567890.0,
            last_verified_by="admin",
        )
        d = s.model_dump()
        assert d["verified_count"] == 3
        assert d["last_verified_by"] == "admin"
