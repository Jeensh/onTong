"""Tests for lineage write-time validation (Phase 4).

Validates:
1. Self-supersession → error
2. Cycle detection → error
3. Competing succession → warning
4. Deprecated without successor → warning
5. Valid lineage → no warnings
"""

import pytest
from backend.application.wiki.lineage_validator import validate_lineage, LineageWarning
from backend.application.metadata.metadata_index import MetadataIndex


@pytest.fixture
def idx(tmp_path):
    """MetadataIndex with a simple version chain: v1 → v2 → v3."""
    idx = MetadataIndex(str(tmp_path))
    idx.rebuild(extended=[
        {
            "path": "doc/v1.md",
            "domain": "IT", "process": "", "tags": [],
            "status": "deprecated",
            "superseded_by": "doc/v2.md",
        },
        {
            "path": "doc/v2.md",
            "domain": "IT", "process": "", "tags": [],
            "status": "deprecated",
            "supersedes": "doc/v1.md",
            "superseded_by": "doc/v3.md",
        },
        {
            "path": "doc/v3.md",
            "domain": "IT", "process": "", "tags": [],
            "status": "approved",
            "supersedes": "doc/v2.md",
        },
    ])
    return idx


class TestSelfSupersession:
    """Self-referencing supersedes or superseded_by → error."""

    def test_supersedes_self(self):
        result = validate_lineage("doc/a.md", "doc/a.md", "", "draft", None)
        errors = [w for w in result if w.level == "error"]
        assert len(errors) == 1
        assert errors[0].code == "self_supersedes"

    def test_superseded_by_self(self):
        result = validate_lineage("doc/a.md", "", "doc/a.md", "draft", None)
        errors = [w for w in result if w.level == "error"]
        assert len(errors) == 1
        assert errors[0].code == "self_superseded_by"

    def test_both_self(self):
        result = validate_lineage("doc/a.md", "doc/a.md", "doc/a.md", "draft", None)
        errors = [w for w in result if w.level == "error"]
        assert len(errors) == 2


class TestCycleDetection:
    """Cycle in the supersedes chain → error."""

    def test_direct_cycle(self, tmp_path):
        """v1 supersedes v2, and we try to save v2 superseding v1 → cycle."""
        idx = MetadataIndex(str(tmp_path))
        idx.rebuild(extended=[
            {
                "path": "doc/v1.md",
                "domain": "IT", "process": "", "tags": [],
                "supersedes": "doc/v2.md",
            },
        ])
        # Now validate saving v2 with supersedes=v1
        result = validate_lineage("doc/v2.md", "doc/v1.md", "", "draft", idx)
        errors = [w for w in result if w.level == "error" and w.code == "cycle_detected"]
        assert len(errors) == 1

    def test_long_chain_no_cycle(self, idx):
        """v3 supersedes v2 (which supersedes v1) — no cycle."""
        result = validate_lineage("doc/v3.md", "doc/v2.md", "", "approved", idx)
        errors = [w for w in result if w.level == "error"]
        assert len(errors) == 0

    def test_three_node_cycle(self, tmp_path):
        """A → B → C, and we try to save C → A → cycle."""
        idx = MetadataIndex(str(tmp_path))
        idx.rebuild(extended=[
            {"path": "a.md", "domain": "", "process": "", "tags": [], "supersedes": "b.md"},
            {"path": "b.md", "domain": "", "process": "", "tags": [], "supersedes": "c.md"},
        ])
        # Save c.md superseding a.md → c→a→b→c cycle
        result = validate_lineage("c.md", "a.md", "", "draft", idx)
        errors = [w for w in result if w.code == "cycle_detected"]
        assert len(errors) == 1


class TestCompetingSuccession:
    """Multiple docs superseding the same target → warning."""

    def test_competing(self, idx):
        # v3 already supersedes v2. Now doc/v3alt.md also wants to supersede v2.
        result = validate_lineage("doc/v3alt.md", "doc/v2.md", "", "draft", idx)
        warnings = [w for w in result if w.code == "competing_succession"]
        assert len(warnings) == 1
        assert "doc/v3.md" in warnings[0].message

    def test_no_competition_for_same_file(self, idx):
        # v3 re-saving with same supersedes=v2 should not warn about competition
        result = validate_lineage("doc/v3.md", "doc/v2.md", "", "approved", idx)
        warnings = [w for w in result if w.code == "competing_succession"]
        assert len(warnings) == 0


class TestDeprecatedNoSuccessor:
    """Deprecated without superseded_by → warning."""

    def test_deprecated_no_successor(self):
        result = validate_lineage("doc/old.md", "", "", "deprecated", None)
        warnings = [w for w in result if w.code == "deprecated_no_successor"]
        assert len(warnings) == 1

    def test_deprecated_with_successor(self):
        result = validate_lineage("doc/old.md", "", "doc/new.md", "deprecated", None)
        warnings = [w for w in result if w.code == "deprecated_no_successor"]
        assert len(warnings) == 0

    def test_draft_no_successor_ok(self):
        result = validate_lineage("doc/a.md", "", "", "draft", None)
        assert len(result) == 0


class TestValidLineage:
    """Clean lineage produces no warnings."""

    def test_no_lineage(self):
        result = validate_lineage("doc/a.md", "", "", "draft", None)
        assert len(result) == 0

    def test_clean_chain(self, idx):
        result = validate_lineage("doc/v3.md", "doc/v2.md", "", "approved", idx)
        assert len(result) == 0

    def test_new_file_superseding_unknown(self, idx):
        """Superseding a file not in the index — no cycle possible, no error."""
        result = validate_lineage("doc/v4.md", "doc/unknown.md", "", "draft", idx)
        errors = [w for w in result if w.level == "error"]
        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
