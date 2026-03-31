"""AgentContext — runtime context passed to agents and skills per request."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.core.schemas import ChatRequest, ThinkingStepEvent
from backend.core.session import SessionStore

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Runtime context for a single agent request.

    Constructed once per request in api/agent.py, threaded to agents and skills.
    """

    request: ChatRequest
    chroma: Any  # ChromaWrapper (avoid import cycle)
    storage: Any  # StorageProvider (avoid import cycle)
    session_store: SessionStore
    history: list[dict] = field(default_factory=list)
    attached_context: str = ""
    augmented_query: str | None = None
    user_roles: list[str] = field(default_factory=lambda: ["admin"])
    user_skill: Any = None        # SkillMeta | None — matched user-facing skill
    skill_context: Any = None     # SkillContext | None — structured 6-layer context

    @staticmethod
    def emit_thinking(step: str, status: str, label: str, detail: str = "") -> str:
        """Format a ThinkingStepEvent as an SSE string."""
        evt = ThinkingStepEvent(step=step, status=status, label=label, detail=detail)
        return f"event: thinking_step\ndata: {evt.model_dump_json()}\n\n"

    @staticmethod
    def sse(event: str, data: str) -> str:
        """Format a generic SSE event string."""
        return f"event: {event}\ndata: {data}\n\n"

    async def run_skill(self, skill_name: str, **kwargs: Any) -> Any:
        """Look up and execute a skill by name.

        Returns SkillResult on success, or SkillResult(success=False) if not found.
        """
        from backend.application.agent.skill import SkillResult, skill_registry

        skill = skill_registry.get(skill_name)
        if skill is None:
            logger.warning(f"Skill not found: {skill_name}")
            return SkillResult(data=None, success=False, error=f"Skill '{skill_name}' not found")
        return await skill.execute(self, **kwargs)
