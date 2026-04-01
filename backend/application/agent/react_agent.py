"""Pydantic AI ReAct agent — replaces the manual tool-calling loop.

Creates a reusable Agent instance with wiki tools registered.
Used by SimulatorAgent, TracerAgent, or any future agent that needs
multi-turn tool-use conversations.
"""

from __future__ import annotations

from pydantic_ai import Agent

from backend.application.agent.context import AgentContext
from backend.application.agent.llm_factory import get_model
from backend.application.agent.pydantic_tools import register_react_tools


def create_react_agent(system_prompt: str = "") -> Agent[AgentContext, str]:
    """Create a Pydantic AI agent with wiki tools for ReAct-style execution.

    Each caller can customize the system prompt while sharing the same tool set.
    """
    agent: Agent[AgentContext, str] = Agent(
        get_model(),
        output_type=str,
        deps_type=AgentContext,
        system_prompt=system_prompt or "You are a helpful assistant with access to wiki tools.",
        retries=2,
        defer_model_check=True,
    )
    register_react_tools(agent)
    return agent
