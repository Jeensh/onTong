"""Tests for version chain logic (Phase 6).

Tests the MetadataIndex-based chain walking that powers the version-chain API.
These are unit tests on the index layer; the API endpoint is tested via integration.
"""

import pytest
from backend.application.metadata.metadata_index import MetadataIndex


@pytest.fixture
def chain_idx(tmp_path):
    """3-node chain: v1 → v2 → v3."""
    idx = MetadataIndex(str(tmp_path))
    idx.rebuild(extended=[
        {
            "path": "doc/v1.md", "domain": "IT", "process": "", "tags": [],
            "status": "deprecated", "superseded_by": "doc/v2.md",
            "created": "2024-01-01", "updated": "2024-01-01", "created_by": "Alice",
        },
        {
            "path": "doc/v2.md", "domain": "IT", "process": "", "tags": [],
            "status": "deprecated", "supersedes": "doc/v1.md", "superseded_by": "doc/v3.md",
            "created": "2024-06-01", "updated": "2024-06-01", "created_by": "Bob",
        },
        {
            "path": "doc/v3.md", "domain": "IT", "process": "", "tags": [],
            "status": "approved", "supersedes": "doc/v2.md",
            "created": "2025-01-01", "updated": "2025-01-01", "created_by": "Charlie",
        },
    ])
    return idx


class TestChainWalking:
    """Walk the supersedes/superseded_by chain via MetadataIndex."""

    def test_walk_backward_from_v3(self, chain_idx):
        """Starting from v3, walk backward to find v2 and v1."""
        entry = chain_idx.get_file_entry("doc/v3.md")
        chain = []
        visited = {"doc/v3.md"}
        cursor = entry.get("supersedes", "")
        while cursor and cursor not in visited:
            visited.add(cursor)
            e = chain_idx.get_file_entry(cursor)
            chain.append(cursor)
            cursor = e.get("supersedes", "") if e else ""
        assert chain == ["doc/v2.md", "doc/v1.md"]

    def test_walk_forward_from_v1(self, chain_idx):
        """Starting from v1, walk forward to find v2 and v3."""
        entry = chain_idx.get_file_entry("doc/v1.md")
        chain = []
        visited = {"doc/v1.md"}
        cursor = entry.get("superseded_by", "")
        while cursor and cursor not in visited:
            visited.add(cursor)
            e = chain_idx.get_file_entry(cursor)
            chain.append(cursor)
            cursor = e.get("superseded_by", "") if e else ""
        assert chain == ["doc/v2.md", "doc/v3.md"]


class TestSingleNode:
    """Single node (no chain)."""

    def test_no_chain(self, tmp_path):
        idx = MetadataIndex(str(tmp_path))
        idx.rebuild(extended=[
            {"path": "doc/solo.md", "domain": "IT", "process": "", "tags": [], "status": "draft"},
        ])
        entry = idx.get_file_entry("doc/solo.md")
        assert entry.get("supersedes", "") == ""
        assert entry.get("superseded_by", "") == ""


class TestBranchDetection:
    """Detect when multiple docs supersede the same target."""

    def test_branch(self, tmp_path):
        idx = MetadataIndex(str(tmp_path))
        idx.rebuild(extended=[
            {"path": "doc/v1.md", "domain": "IT", "process": "", "tags": [], "status": "deprecated"},
            {"path": "doc/v2a.md", "domain": "IT", "process": "", "tags": [],
             "status": "approved", "supersedes": "doc/v1.md"},
            {"path": "doc/v2b.md", "domain": "IT", "process": "", "tags": [],
             "status": "draft", "supersedes": "doc/v1.md"},
        ])
        competitors = idx.get_supersedes_reverse("doc/v1.md")
        assert sorted(competitors) == ["doc/v2a.md", "doc/v2b.md"]


class TestCycleProtection:
    """Chain walking should not loop infinitely on cycles."""

    def test_cycle_in_data(self, tmp_path):
        """Even if data has a cycle, walking should terminate."""
        idx = MetadataIndex(str(tmp_path))
        idx.rebuild(extended=[
            {"path": "a.md", "domain": "", "process": "", "tags": [],
             "supersedes": "b.md", "superseded_by": ""},
            {"path": "b.md", "domain": "", "process": "", "tags": [],
             "supersedes": "a.md", "superseded_by": ""},
        ])
        # Walk backward from a.md: a → b → a (cycle, should stop)
        visited = {"a.md"}
        chain = []
        cursor = "b.md"
        while cursor and cursor not in visited and len(chain) < 50:
            visited.add(cursor)
            e = idx.get_file_entry(cursor)
            chain.append(cursor)
            cursor = e.get("supersedes", "") if e else ""
        # Should stop after finding b.md (a.md is in visited)
        assert chain == ["b.md"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
