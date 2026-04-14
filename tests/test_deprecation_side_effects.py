"""Tests for deprecation side effects (Phase 5).

Validates:
1. get_neighbor_tags excludes deprecated files
2. get_neighbor_domain_summary excludes deprecated files
3. Auto-resolve conflicts helper exists (integration tested separately)
"""

import pytest
from backend.application.metadata.metadata_index import MetadataIndex


@pytest.fixture
def idx(tmp_path):
    """MetadataIndex with mix of active and deprecated files."""
    idx = MetadataIndex(str(tmp_path))
    idx.rebuild(extended=[
        {
            "path": "docs/active1.md",
            "domain": "IT", "process": "Deploy", "tags": ["docker", "k8s"],
            "status": "approved",
        },
        {
            "path": "docs/active2.md",
            "domain": "IT", "process": "Deploy", "tags": ["docker", "helm"],
            "status": "draft",
        },
        {
            "path": "docs/deprecated1.md",
            "domain": "IT", "process": "Deploy", "tags": ["docker", "legacy"],
            "status": "deprecated",
        },
        {
            "path": "docs/deprecated2.md",
            "domain": "HR", "process": "Onboard", "tags": ["onboard"],
            "status": "deprecated",
        },
    ])
    return idx


class TestNeighborTagsExcludesDeprecated:
    """get_neighbor_tags should skip deprecated files."""

    def test_deprecated_tags_excluded(self, idx):
        tags = idx.get_neighbor_tags("docs")
        tag_names = [t for t, _ in tags]
        # "legacy" only appears in deprecated1.md
        assert "legacy" not in tag_names
        # "onboard" only appears in deprecated2.md
        assert "onboard" not in tag_names
        # "docker" appears in both active files
        assert "docker" in tag_names

    def test_tag_counts_exclude_deprecated(self, idx):
        tags = dict(idx.get_neighbor_tags("docs"))
        # docker: active1 + active2 = 2 (not 3 from deprecated1)
        assert tags.get("docker") == 2
        # helm: only in active2
        assert tags.get("helm") == 1


class TestNeighborDomainSummaryExcludesDeprecated:
    """get_neighbor_domain_summary should skip deprecated files."""

    def test_deprecated_domain_excluded(self, idx):
        summary = idx.get_neighbor_domain_summary("docs")
        # HR only appears in deprecated2.md
        assert "HR" not in summary["domains"]
        # IT appears in active1 + active2 = 2 (not 3)
        assert summary["domains"]["IT"] == 2

    def test_deprecated_process_excluded(self, idx):
        summary = idx.get_neighbor_domain_summary("docs")
        # Onboard only in deprecated file
        assert "Onboard" not in summary["processes"]
        # Deploy: active1 + active2 = 2
        assert summary["processes"]["Deploy"] == 2


class TestStatusFilesAfterDeprecation:
    """Verify status_files index reflects deprecation correctly."""

    def test_deprecated_files_indexed(self, idx):
        deprecated = idx.get_files_by_status("deprecated")
        assert sorted(deprecated) == ["docs/deprecated1.md", "docs/deprecated2.md"]

    def test_active_files_indexed(self, idx):
        approved = idx.get_files_by_status("approved")
        assert approved == ["docs/active1.md"]
        draft = idx.get_files_by_status("draft")
        assert draft == ["docs/active2.md"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
