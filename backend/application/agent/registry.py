"""ToolRegistry — plugin architecture for agent routing."""

from __future__ import annotations

import logging
from typing import Protocol

from backend.core.schemas import ChatRequest

logger = logging.getLogger(__name__)


class AgentPlugin(Protocol):
    """Interface every agent must implement."""

    name: str

    async def execute(self, request: ChatRequest, **kwargs):
        """Execute the agent logic. Yields SSE events."""
        ...


class ToolRegistry:
    """Registry for dynamically adding/removing agent plugins."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentPlugin] = {}

    def register(self, agent: AgentPlugin) -> None:
        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")

    def get(self, name: str) -> AgentPlugin | None:
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())


registry = ToolRegistry()
