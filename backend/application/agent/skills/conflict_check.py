"""ConflictCheckSkill — detect contradictions across wiki documents."""

from __future__ import annotations

import logging
from typing import Any

from backend.application.agent.skill import SkillResult

logger = logging.getLogger(__name__)

CONFLICT_CHECK_PROMPT = (
    "You are a document conflict detector for a corporate wiki system.\n\n"
    "Analyze the following document excerpts and determine if they contain "
    "contradictory information on the same topic.\n\n"
    "Look for:\n"
    "- Different numbers/amounts for the same metric\n"
    "- Different rules or procedures for the same process\n"
    "- Multiple versions of a policy from different teams/dates without clear precedence\n\n"
    "IMPORTANT: The 'details' field MUST be written in Korean (한국어). "
    "Describe which documents conflict and how they differ specifically.\n"
)


class ConflictCheckSkill:
    name = "conflict_check"
    description = "검색된 문서들 사이의 모순을 감지합니다"

    async def execute(
        self,
        ctx: Any,
        *,
        documents: list[str] | None = None,
        metadatas: list[dict] | None = None,
        distances: list[float] | None = None,
    ) -> SkillResult:
        if not documents or len(documents) < 2:
            return SkillResult(data={"has_conflict": False, "details": "", "conflicting_docs": []})

        # Build context with metadata headers
        chunks: list[str] = []
        for i, (doc, meta) in enumerate(zip(documents, metadatas or [{}] * len(documents))):
            fp = meta.get("file_path", f"doc_{i}")
            updated = meta.get("updated", "unknown")
            domain = meta.get("domain", "")
            header = f"[출처: {fp}] [수정일: {updated}] [도메인: {domain}]"
            chunks.append(f"{header}\n{doc[:500]}")

        context = "\n\n---\n\n".join(chunks)

        try:
            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model
            from backend.application.agent.models import ConflictCheckResult

            agent = Agent(
                get_model(),
                output_type=ConflictCheckResult,
                system_prompt=CONFLICT_CHECK_PROMPT,
                retries=2,
                defer_model_check=True,
            )
            result = await agent.run(f"## 문서들\n\n{context}")
            output = result.output
            return SkillResult(data={
                "has_conflict": output.has_conflict,
                "details": output.details,
                "conflicting_docs": output.conflicting_docs,
            })

        except Exception as e:
            logger.warning(f"Conflict check failed: {e}")
            return SkillResult(data={"has_conflict": False, "details": "", "conflicting_docs": []})

    def to_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "충돌을 감지할 주제"},
                    },
                    "required": ["query"],
                },
            },
        }
