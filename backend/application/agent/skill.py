"""Skill system — composable, reusable agent capabilities.

Each Skill is an independent building block that agents can invoke.
Skills support two consumption patterns:
  1. Code orchestration: agent calls ctx.run_skill("name", ...) directly
  2. LLM tool-use: agent passes skill.to_tool_schema() to LLM function calling
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class SkillResult:
    """Unified return type from any skill execution."""

    data: Any = None
    success: bool = True
    error: str = ""


@runtime_checkable
class Skill(Protocol):
    """Interface every skill must implement."""

    name: str
    description: str  # human-readable, also used in LLM tool schemas

    async def execute(self, ctx: Any, **kwargs: Any) -> SkillResult:
        """Run the skill and return a structured result."""
        ...

    def to_tool_schema(self) -> dict:
        """Return OpenAI function-calling compatible tool schema."""
        ...


class SkillRegistry:
    """Central registry for all skills. Singleton at module level."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        return list(self._skills.keys())

    def to_tool_schemas(self) -> list[dict]:
        """Return all skills as OpenAI function-calling tool schemas."""
        return [s.to_tool_schema() for s in self._skills.values()]


skill_registry = SkillRegistry()
