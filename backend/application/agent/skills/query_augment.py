"""QueryAugmentSkill — rewrite follow-up questions as standalone search queries.

Also detects topic shifts to prevent context contamination from unrelated history.
"""

from __future__ import annotations

import logging

from backend.application.agent.skill import SkillResult
from backend.application.agent.skills.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

AUGMENT_SYSTEM_PROMPT = load_prompt("query_augment")


class QueryAugmentSkill:
    name = "query_augment"
    description = "후속 질문을 독립적인 검색 쿼리로 변환하고 주제 전환을 감지합니다"

    async def execute(
        self, ctx: object, *, query: str = "", history: list[dict] | None = None
    ) -> SkillResult:
        if not history or len(history) < 2:
            return SkillResult(data={"augmented_query": query, "topic_shift": False})

        recent_context: list[str] = []
        for msg in history[-4:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                recent_context.append(content)
            elif role == "assistant":
                recent_context.append(content[:100])

        try:
            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model
            from backend.application.agent.models import QueryAugmentResult

            agent = Agent(
                get_model(),
                output_type=QueryAugmentResult,
                system_prompt=AUGMENT_SYSTEM_PROMPT,
                retries=1,
                defer_model_check=True,
            )
            result = await agent.run(
                f"Conversation context:\n{chr(10).join(recent_context)}\n\n"
                f"Follow-up question: {query}"
            )
            output = result.output
            augmented = output.augmented_query.strip() or query
            topic_shift = output.topic_shift

            logger.info(
                f"Query augmented: '{query}' → '{augmented}' (topic_shift={topic_shift})"
            )
            return SkillResult(data={
                "augmented_query": augmented,
                "topic_shift": topic_shift,
            })
        except Exception as e:
            logger.warning(f"Query augmentation failed: {e}")

        return SkillResult(data={"augmented_query": query, "topic_shift": False})

    def to_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "현재 질문"},
                    },
                    "required": ["query"],
                },
            },
        }
