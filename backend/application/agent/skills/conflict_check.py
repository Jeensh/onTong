"""ConflictCheckSkill — detect contradictions across wiki documents."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

from backend.core.config import settings
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
    "Respond in this exact JSON format (no markdown fences):\n"
    '{"has_conflict": false}\n'
    "or\n"
    '{"has_conflict": true, "details": "brief Korean description of the conflict", '
    '"conflicting_docs": ["file_a.md", "file_b.md"]}\n'
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
            response = await litellm.acompletion(
                model=settings.litellm_model,
                messages=[
                    {"role": "system", "content": CONFLICT_CHECK_PROMPT},
                    {"role": "user", "content": f"## 문서들\n\n{context}"},
                ],
                max_tokens=300,
                temperature=0,
            )

            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(raw)
            return SkillResult(data={
                "has_conflict": result.get("has_conflict", False),
                "details": result.get("details", ""),
                "conflicting_docs": result.get("conflicting_docs", []),
            })

        except (json.JSONDecodeError, Exception) as e:
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
