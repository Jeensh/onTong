"""Tests for Phase 3 — Read-Time Trust Context.

Covers:
- CitationTracker (InMemory backend)
- ConfidenceResult extended fields (citation_count, newer_alternatives)
- NewerAlternative model
"""

import pytest
from backend.application.trust.citation_tracker import (
    CitationTracker,
    InMemoryCitationStore,
)
from backend.application.trust.confidence import (
    ConfidenceResult,
    NewerAlternative,
    compute_confidence,
)


# ── CitationTracker ──────────────────────────────────────────────────

class TestCitationTracker:
    def _make_tracker(self) -> CitationTracker:
        return CitationTracker(InMemoryCitationStore())

    def test_record_and_get(self):
        ct = self._make_tracker()
        assert ct.get_count("a.md") == 0
        ct.record_citation("a.md")
        assert ct.get_count("a.md") == 1
        ct.record_citation("a.md")
        assert ct.get_count("a.md") == 2

    def test_record_multiple(self):
        ct = self._make_tracker()
        ct.record_citations(["a.md", "b.md", "a.md"])
        assert ct.get_count("a.md") == 2
        assert ct.get_count("b.md") == 1

    def test_get_batch(self):
        ct = self._make_tracker()
        ct.record_citation("a.md")
        ct.record_citation("a.md")
        ct.record_citation("b.md")
        result = ct.get_batch(["a.md", "b.md", "c.md"])
        assert result == {"a.md": 2, "b.md": 1, "c.md": 0}

    def test_get_batch_empty(self):
        ct = self._make_tracker()
        assert ct.get_batch([]) == {}

    def test_separate_paths(self):
        ct = self._make_tracker()
        ct.record_citation("x.md")
        assert ct.get_count("y.md") == 0


# ── ConfidenceResult extended fields ──────────────────────────────────

class TestConfidenceResultExtended:
    def test_default_citation_count(self):
        r = ConfidenceResult()
        assert r.citation_count == 0
        assert r.newer_alternatives == []

    def test_with_citation_count(self):
        r = ConfidenceResult(citation_count=15)
        assert r.citation_count == 15

    def test_with_newer_alternatives(self):
        alts = [
            NewerAlternative(path="new.md", title="New Doc", confidence_score=85, confidence_tier="high"),
        ]
        r = ConfidenceResult(newer_alternatives=alts)
        assert len(r.newer_alternatives) == 1
        assert r.newer_alternatives[0].path == "new.md"
        assert r.newer_alternatives[0].confidence_score == 85

    def test_compute_confidence_returns_extended_fields(self):
        meta = {"status": "approved", "updated": "2026-03-01",
                "domain": "infra", "process": "ops", "tags": "cache", "created_by": "test"}
        result = compute_confidence(meta)
        assert hasattr(result, "citation_count")
        assert hasattr(result, "newer_alternatives")
        assert result.citation_count == 0
        assert result.newer_alternatives == []


# ── NewerAlternative model ────────────────────────────────────────────

class TestNewerAlternative:
    def test_defaults(self):
        alt = NewerAlternative(path="doc.md")
        assert alt.title == ""
        assert alt.confidence_score == 0
        assert alt.confidence_tier == ""

    def test_full(self):
        alt = NewerAlternative(
            path="doc.md",
            title="Better Doc",
            confidence_score=92,
            confidence_tier="high",
        )
        assert alt.title == "Better Doc"
        assert alt.confidence_score == 92

    def test_serialization(self):
        alt = NewerAlternative(path="x.md", title="X", confidence_score=80, confidence_tier="high")
        d = alt.model_dump()
        assert d["path"] == "x.md"
        assert d["confidence_score"] == 80


# ── Integration: ConfidenceResult serialization ───────────────────────

class TestConfidenceResultSerialization:
    def test_full_serialization(self):
        r = ConfidenceResult(
            score=45,
            tier="medium",
            stale=True,
            stale_months=14,
            signals={"freshness": 30.0},
            citation_count=7,
            newer_alternatives=[
                NewerAlternative(path="alt.md", title="Alt", confidence_score=88, confidence_tier="high"),
            ],
        )
        d = r.model_dump()
        assert d["citation_count"] == 7
        assert len(d["newer_alternatives"]) == 1
        assert d["newer_alternatives"][0]["path"] == "alt.md"

    def test_empty_serialization(self):
        r = ConfidenceResult()
        d = r.model_dump()
        assert d["citation_count"] == 0
        assert d["newer_alternatives"] == []
