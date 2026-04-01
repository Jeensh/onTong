"""Main Router — LLM-based unified intent classification.

Replaces the old 2-tier (keyword → LLM fallback) approach with a single
LLM call that determines both the target agent AND the action type.
The result is passed downstream so RAGAgent doesn't need its own regex.
"""

from __future__ import annotations

import logging

from backend.application.agent.models import UserIntent
from backend.core.schemas import RouterDecision

logger = logging.getLogger(__name__)


class MainRouter:
    async def classify(self, message: str, has_attached_files: bool = False) -> UserIntent:
        """Classify user message into agent + action via LLM.

        Returns a UserIntent with agent, action, and confidence.
        """
        from backend.application.agent.structured_agents import create_intent_agent

        try:
            agent = create_intent_agent()
            prompt = message
            if has_attached_files:
                prompt = f"[파일 첨부됨] {message}"
            result = await agent.run(prompt)
            intent = result.output
            logger.info(f"Intent: agent={intent.agent}, action={intent.action}, confidence={intent.confidence:.2f}")
            return intent
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return UserIntent(agent="WIKI_QA", action="question", confidence=0.5)

    async def route(self, message: str) -> RouterDecision:
        """Route user message to the appropriate agent (backward-compatible API)."""
        intent = await self.classify(message)
        return RouterDecision(
            agent=intent.agent,
            confidence=intent.confidence,
            reasoning=f"llm_intent: action={intent.action}",
        )


router = MainRouter()
