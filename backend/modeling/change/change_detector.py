"""Git diff → mapping impact classification."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.infrastructure.git_connector import GitDiff
from backend.modeling.mapping.mapping_models import MappingFile

logger = logging.getLogger(__name__)


class ChangeKind(str, Enum):
    BROKEN = "broken"        # mapped entity was deleted
    REVIEW = "review"        # mapped entity was modified
    UNMAPPED = "unmapped"    # new entity has no mapping
    AUTO_UPDATE = "auto_update"  # rename/move


@dataclass
class ChangeImpact:
    kind: ChangeKind
    code_entity: str
    file_path: str
    owner: str
    message: str


class ChangeDetector:
    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    def classify(self, diff: GitDiff, mf: MappingFile, repo_id: str) -> list[ChangeImpact]:
        impacts: list[ChangeImpact] = []
        mapping_by_code = {m.code: m for m in mf.mappings}

        # Deleted files → broken mappings
        for path in diff.deleted:
            entities = self._entities_in_file(path, repo_id)
            for e in entities:
                qn = e["qualified_name"]
                if qn in mapping_by_code:
                    m = mapping_by_code[qn]
                    impacts.append(ChangeImpact(
                        kind=ChangeKind.BROKEN, code_entity=qn, file_path=path,
                        owner=m.owner, message=f"매핑된 코드 '{qn}'가 삭제되었습니다.",
                    ))

        # Modified files → review needed
        for path in diff.modified:
            entities = self._entities_in_file(path, repo_id)
            for e in entities:
                qn = e["qualified_name"]
                if qn in mapping_by_code:
                    m = mapping_by_code[qn]
                    impacts.append(ChangeImpact(
                        kind=ChangeKind.REVIEW, code_entity=qn, file_path=path,
                        owner=m.owner, message=f"매핑된 코드 '{qn}'가 변경되었습니다. 매핑 검토가 필요합니다.",
                    ))

        # Added files → unmapped
        for path in diff.added:
            entities = self._entities_in_file(path, repo_id)
            for e in entities:
                qn = e["qualified_name"]
                if qn not in mapping_by_code:
                    impacts.append(ChangeImpact(
                        kind=ChangeKind.UNMAPPED, code_entity=qn, file_path=path,
                        owner="", message=f"새 코드 '{qn}'에 도메인 매핑이 필요합니다.",
                    ))

        return impacts

    def _entities_in_file(self, file_path: str, repo_id: str) -> list[dict]:
        return self._neo4j.query(
            "MATCH (n:CodeEntity {file_path: $fp, repo_id: $repo_id}) "
            "RETURN n.qualified_name as qualified_name",
            {"fp": file_path, "repo_id": repo_id},
        )
