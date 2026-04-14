"""Built-in skill hooks — pre/post execution interceptors.

These hooks demonstrate the hook system and provide useful default behaviors:
  - QuerySanitizeHook (pre): strips excessive whitespace from search queries
  - DeprecatedDocHook (post): flags deprecated documents in search results
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.application.agent.skill import (
    CompletionStatus,
    PreHookResult,
    SkillResult,
)

logger = logging.getLogger(__name__)


class QuerySanitizeHook:
    """Pre-hook: sanitize search queries by stripping excessive whitespace and trimming."""

    name = "query_sanitize"

    def should_run(self, skill_name: str, ctx: Any) -> bool:
        return skill_name in ("wiki_search", "query_augment")

    async def before(self, skill_name: str, ctx: Any, kwargs: dict[str, Any]) -> PreHookResult:
        query = kwargs.get("query") or kwargs.get("q")
        if not query or not isinstance(query, str):
            return PreHookResult(allow=True)

        cleaned = re.sub(r"\s+", " ", query).strip()
        if not cleaned:
            return PreHookResult(allow=False, block_reason="Empty query after sanitization")

        if cleaned != query:
            key = "query" if "query" in kwargs else "q"
            logger.debug(f"QuerySanitizeHook: '{query}' → '{cleaned}'")
            return PreHookResult(allow=True, modified_kwargs={key: cleaned})

        return PreHookResult(allow=True)


class DeprecatedDocHook:
    """Post-hook: flag deprecated documents in wiki_search results."""

    name = "deprecated_doc_filter"

    def should_run(self, skill_name: str, ctx: Any) -> bool:
        return skill_name == "wiki_search"

    async def after(self, skill_name: str, ctx: Any, result: SkillResult) -> SkillResult:
        if not result.success or not result.data:
            return result

        docs = result.data if isinstance(result.data, list) else []
        deprecated_count = 0

        for doc in docs:
            metadata = None
            if isinstance(doc, dict):
                metadata = doc.get("metadata", {})
            elif hasattr(doc, "metadata"):
                metadata = getattr(doc.metadata, "__dict__", {}) if hasattr(doc.metadata, "__dict__") else {}

            if metadata and metadata.get("status") == "deprecated":
                deprecated_count += 1

        if deprecated_count > 0:
            warning = f"폐기(deprecated) 문서 {deprecated_count}건이 검색 결과에 포함되어 있습니다."
            result.feedback = f"{result.feedback}; {warning}" if result.feedback else warning
            result.status = CompletionStatus.DONE_WITH_CONCERNS

        return result


def register_default_hooks() -> None:
    """Register built-in hooks. Called during app startup."""
    from backend.application.agent.skill import hook_registry

    hook_registry.register_pre(QuerySanitizeHook())
    hook_registry.register_post(DeprecatedDocHook())
    logger.info(f"Default hooks registered: {hook_registry.list_hooks()}")
