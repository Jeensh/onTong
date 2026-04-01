"""QueryAugmentSkill — rewrite follow-up questions as standalone search queries."""

from __future__ import annotations

import logging

from backend.application.agent.skill import SkillResult

logger = logging.getLogger(__name__)

AUGMENT_SYSTEM_PROMPT = (
    "You are a search query rewriter. Given a follow-up question and "
    "conversation context, rewrite the question as a standalone search query "
    "that includes all necessary context for document retrieval.\n\n"
    "Rules:\n"
    "- Output ONLY the rewritten query, nothing else\n"
    "- Keep it concise (under 50 words)\n"
    "- Preserve the original language (Korean)\n"
    "- Include key entities/topics from context that the follow-up refers to\n\n"
    "Example:\n"
    "Context: user asked about '후판 공정계획'\n"
    "Follow-up: '담당자 누구 있는지 찾아줘'\n"
    "Rewritten: '후판 공정계획 담당자 누구'"
)


class QueryAugmentSkill:
    name = "query_augment"
    description = "후속 질문을 독립적인 검색 쿼리로 변환합니다"

    async def execute(
        self, ctx: object, *, query: str = "", history: list[dict] | None = None
    ) -> SkillResult:
        if not history or len(history) < 2:
            return SkillResult(data={"augmented_query": query})

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

            agent = Agent(
                get_model(),
                output_type=str,
                system_prompt=AUGMENT_SYSTEM_PROMPT,
                defer_model_check=True,
            )
            result = await agent.run(
                f"Conversation context:\n{chr(10).join(recent_context)}\n\n"
                f"Follow-up question: {query}"
            )
            augmented = result.output.strip()
            if augmented:
                logger.info(f"Query augmented: '{query}' → '{augmented}'")
                return SkillResult(data={"augmented_query": augmented})
        except Exception as e:
            logger.warning(f"Query augmentation failed: {e}")

        return SkillResult(data={"augmented_query": query})

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
