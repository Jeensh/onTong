"""Unit tests for Related Documents Search (Phase 2).

Tests the RelatedDocResult model and ranking logic.
"""

import pytest
from backend.core.schemas import RelatedDocResult


class TestRelatedDocResult:
    def test_model_defaults(self):
        r = RelatedDocResult(path="a.md", title="Test", snippet="content", similarity=0.85)
        assert r.confidence_score == -1
        assert r.confidence_tier == ""
        assert r.relationship == "similar_topic"

    def test_model_full(self):
        r = RelatedDocResult(
            path="docs/cache.md",
            title="Cache Guide",
            snippet="Redis caching tips...",
            similarity=0.92,
            confidence_score=85,
            confidence_tier="high",
            relationship="same_domain",
        )
        assert r.similarity == 0.92
        assert r.confidence_score == 85
        assert r.relationship == "same_domain"


class TestCompositeScoring:
    """Test the composite scoring formula: 0.6 * similarity + 0.4 * (confidence / 100)."""

    def _composite(self, sim: float, conf: int) -> float:
        return 0.6 * sim + 0.4 * (conf / 100 if conf >= 0 else 0.5)

    def test_high_sim_high_conf(self):
        score = self._composite(0.95, 90)
        assert score > 0.9

    def test_high_sim_low_conf(self):
        score = self._composite(0.95, 20)
        assert 0.6 < score < 0.8

    def test_low_sim_high_conf(self):
        score = self._composite(0.55, 90)
        assert 0.5 < score < 0.75

    def test_missing_confidence(self):
        """When confidence is -1, use 0.5 fallback."""
        score = self._composite(0.8, -1)
        assert abs(score - (0.6 * 0.8 + 0.4 * 0.5)) < 0.001

    def test_ranking_order(self):
        """High-sim + high-conf beats high-sim + low-conf."""
        docs = [
            {"sim": 0.90, "conf": 30},  # composite: 0.54 + 0.12 = 0.66
            {"sim": 0.85, "conf": 90},  # composite: 0.51 + 0.36 = 0.87
            {"sim": 0.92, "conf": 50},  # composite: 0.552 + 0.20 = 0.752
        ]
        scored = sorted(docs, key=lambda d: -self._composite(d["sim"], d["conf"]))
        assert scored[0]["conf"] == 90  # high conf wins
        assert scored[1]["sim"] == 0.92  # medium conf, highest sim
        assert scored[2]["conf"] == 30  # low conf last


class TestRelationshipClassification:
    """Test relationship type logic."""

    def _classify(self, source_domain: str, source_tags: set, other_domain: str, other_tags: set) -> str:
        relationship = "similar_topic"
        if source_domain and other_domain == source_domain:
            relationship = "same_domain"
        if source_tags and other_tags and source_tags & other_tags:
            relationship = "shared_tags"
        return relationship

    def test_similar_topic(self):
        assert self._classify("SCM", set(), "ERP", set()) == "similar_topic"

    def test_same_domain(self):
        assert self._classify("SCM", set(), "SCM", set()) == "same_domain"

    def test_shared_tags(self):
        assert self._classify("SCM", {"cache", "redis"}, "ERP", {"redis"}) == "shared_tags"

    def test_shared_tags_overrides_domain(self):
        """shared_tags takes priority over same_domain."""
        assert self._classify("SCM", {"cache"}, "SCM", {"cache"}) == "shared_tags"

    def test_no_source_tags(self):
        assert self._classify("", set(), "", {"redis"}) == "similar_topic"
