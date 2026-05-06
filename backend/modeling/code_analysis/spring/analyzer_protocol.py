"""Spring analyzer plug-in protocol + 6 default stubs.

B4 스캐폴드 단계 — 각 analyzer 는 `analyze(tree, content, file_path, pkg_name)` 호출에서
`(entities, relations)` 튜플을 반환한다. B4 에서는 전부 빈 결과만 반환.
B5 에서 8 Spring 난제별 실제 구현으로 교체된다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.modeling.code_analysis.parser_protocol import CodeEntity, CodeRelation


@runtime_checkable
class SpringAnalyzer(Protocol):
    """Interface for a Spring-focused analyzer plug-in."""

    def analyze(
        self,
        tree: object | None,
        content: bytes,
        file_path: str,
        pkg_name: str | None,
    ) -> tuple[list[CodeEntity], list[CodeRelation]]:
        """Analyze a parsed tree and yield Spring-specific nodes/edges."""
        ...


class _NoopAnalyzer:
    """Shared stub — returns empty results until B5 replaces it."""

    def analyze(
        self,
        tree: object | None,
        content: bytes,
        file_path: str,
        pkg_name: str | None,
    ) -> tuple[list[CodeEntity], list[CodeRelation]]:
        return [], []


__all__ = (
    "SpringAnalyzer",
)
