"""Write-time lineage validation for document version chains.

Checks performed before saving:
  ERROR (blocks save):
    - Self-supersession: supersedes or superseded_by points to self
    - Cycle detection: walk the supersedes chain to detect loops
  WARNING (allows save, returned to caller):
    - Competing succession: another doc already supersedes the same target
    - Deprecated without successor: status=deprecated but superseded_by is empty
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.application.metadata.metadata_index import MetadataIndex

logger = logging.getLogger(__name__)


@dataclass
class LineageWarning:
    level: str  # "error" | "warning"
    code: str   # machine-readable code
    message: str  # human-readable description


def validate_lineage(
    path: str,
    supersedes: str,
    superseded_by: str,
    status: str,
    meta_index: MetadataIndex | None,
) -> list[LineageWarning]:
    """Validate lineage fields before saving a document.

    Returns list of warnings/errors. Callers should reject save if any error-level items exist.
    """
    warnings: list[LineageWarning] = []

    # Self-supersession check
    if supersedes and supersedes == path:
        warnings.append(LineageWarning(
            level="error",
            code="self_supersedes",
            message=f"자기 자신을 이전 버전으로 지정할 수 없습니다",
        ))
    if superseded_by and superseded_by == path:
        warnings.append(LineageWarning(
            level="error",
            code="self_superseded_by",
            message=f"자기 자신을 새 버전으로 지정할 수 없습니다",
        ))

    # Existence check: target documents must exist
    if meta_index and supersedes and not meta_index.get_file_entry(supersedes):
        warnings.append(LineageWarning(
            level="error",
            code="supersedes_not_found",
            message=f"이전 버전 문서가 존재하지 않습니다: {supersedes}",
        ))
    if meta_index and superseded_by and not meta_index.get_file_entry(superseded_by):
        warnings.append(LineageWarning(
            level="error",
            code="superseded_by_not_found",
            message=f"새 버전 문서가 존재하지 않습니다: {superseded_by}",
        ))

    # Cycle detection (only if we have the index)
    if meta_index and supersedes:
        visited = {path}
        current = supersedes
        max_depth = 50  # safety limit
        depth = 0
        while current and depth < max_depth:
            if current in visited:
                warnings.append(LineageWarning(
                    level="error",
                    code="cycle_detected",
                    message=f"버전 순환이 감지되었습니다: {path} → ... → {current} (순환 참조)",
                ))
                break
            visited.add(current)
            entry = meta_index.get_file_entry(current)
            if not entry:
                break
            current = entry.get("supersedes", "")
            depth += 1

    # Competing succession: another doc already claims to supersede the same target
    if meta_index and supersedes:
        competitors = meta_index.get_supersedes_reverse(supersedes)
        others = [p for p in competitors if p != path]
        if others:
            warnings.append(LineageWarning(
                level="warning",
                code="competing_succession",
                message=f"'{supersedes}' is also superseded by: {', '.join(others)}",
            ))

    # Deprecated without successor
    if status == "deprecated" and not superseded_by:
        warnings.append(LineageWarning(
            level="warning",
            code="deprecated_no_successor",
            message=f"Document '{path}' is deprecated but has no superseded_by set",
        ))

    return warnings
