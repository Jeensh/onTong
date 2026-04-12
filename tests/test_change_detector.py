"""Tests for ChangeDetector — mapping impact classification from git diffs."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.modeling.change.change_detector import ChangeDetector, ChangeKind
from backend.modeling.infrastructure.git_connector import GitDiff
from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingGranularity, MappingStatus


def _make_mapping_file(*mappings: Mapping) -> MappingFile:
    return MappingFile(repo_id="test-repo", mappings=list(mappings))


def _make_mapping(code: str, owner: str = "team-a") -> Mapping:
    return Mapping(
        code=code,
        domain="domain.node.1",
        granularity=MappingGranularity.CLASS,
        owner=owner,
        status=MappingStatus.CONFIRMED,
    )


class TestChangeDetector:
    def test_deleted_file_flags_broken_mapping(self) -> None:
        """Deleted file containing a mapped entity should produce a BROKEN impact."""
        neo4j = MagicMock()
        neo4j.query.return_value = [{"qualified_name": "com.example.OrderService"}]

        detector = ChangeDetector(neo4j)
        diff = GitDiff(deleted=["src/main/java/com/example/OrderService.java"])
        mf = _make_mapping_file(_make_mapping("com.example.OrderService", owner="team-a"))

        impacts = detector.classify(diff, mf, repo_id="test-repo")

        assert len(impacts) == 1
        assert impacts[0].kind == ChangeKind.BROKEN
        assert impacts[0].code_entity == "com.example.OrderService"
        assert impacts[0].owner == "team-a"
        assert "삭제" in impacts[0].message

    def test_new_file_flags_unmapped(self) -> None:
        """Added file with a new entity that has no mapping should produce UNMAPPED."""
        neo4j = MagicMock()
        neo4j.query.return_value = [{"qualified_name": "com.example.NewFeature"}]

        detector = ChangeDetector(neo4j)
        diff = GitDiff(added=["src/main/java/com/example/NewFeature.java"])
        mf = _make_mapping_file()  # no existing mappings

        impacts = detector.classify(diff, mf, repo_id="test-repo")

        assert len(impacts) == 1
        assert impacts[0].kind == ChangeKind.UNMAPPED
        assert impacts[0].code_entity == "com.example.NewFeature"
        assert impacts[0].owner == ""
        assert "매핑이 필요" in impacts[0].message

    def test_modified_file_flags_review(self) -> None:
        """Modified file containing a mapped entity should produce REVIEW with owner."""
        neo4j = MagicMock()
        neo4j.query.return_value = [{"qualified_name": "com.example.InventoryManager"}]

        detector = ChangeDetector(neo4j)
        diff = GitDiff(modified=["src/main/java/com/example/InventoryManager.java"])
        mf = _make_mapping_file(
            _make_mapping("com.example.InventoryManager", owner="team-b"),
        )

        impacts = detector.classify(diff, mf, repo_id="test-repo")

        assert len(impacts) == 1
        assert impacts[0].kind == ChangeKind.REVIEW
        assert impacts[0].code_entity == "com.example.InventoryManager"
        assert impacts[0].owner == "team-b"
        assert "검토가 필요" in impacts[0].message
