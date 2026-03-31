"""WikiReadSkill — read a specific wiki document by path."""

from __future__ import annotations

import logging
from typing import Any

from backend.application.agent.skill import SkillResult

logger = logging.getLogger(__name__)


class WikiReadSkill:
    name = "wiki_read"
    description = "특정 경로의 Wiki 문서를 읽습니다"

    async def execute(self, ctx: Any, *, path: str = "") -> SkillResult:
        if not path:
            return SkillResult(data=None, success=False, error="path required")

        storage = ctx.storage
        if not storage:
            return SkillResult(data=None, success=False, error="storage not available")

        try:
            wiki_file = await storage.read(path)
            if not wiki_file:
                return SkillResult(data=None, success=False, error=f"File not found: {path}")

            return SkillResult(data={
                "path": wiki_file.path,
                "title": wiki_file.title,
                "content": wiki_file.content,
                "raw_content": wiki_file.raw_content,
                "metadata": {
                    "domain": wiki_file.metadata.domain,
                    "process": wiki_file.metadata.process,
                    "status": wiki_file.metadata.status,
                    "tags": wiki_file.metadata.tags,
                    "updated": wiki_file.metadata.updated,
                    "updated_by": wiki_file.metadata.updated_by,
                    "created_by": wiki_file.metadata.created_by,
                    "supersedes": wiki_file.metadata.supersedes,
                    "superseded_by": wiki_file.metadata.superseded_by,
                    "related": wiki_file.metadata.related,
                },
            })

        except Exception as e:
            logger.error(f"wiki_read failed for {path}: {e}")
            return SkillResult(data=None, success=False, error=str(e))

    def to_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Wiki 문서 경로 (예: 출장-경비-규정.md)"},
                    },
                    "required": ["path"],
                },
            },
        }
