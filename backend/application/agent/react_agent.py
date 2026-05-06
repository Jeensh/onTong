"""Pydantic AI ReAct agent — replaces the manual tool-calling loop.

Creates a reusable Agent instance with wiki tools registered.
Used by SimulatorAgent, TracerAgent, or any future agent that needs
multi-turn tool-use conversations.
"""

from __future__ import annotations

from datetime import date

from pydantic_ai import Agent

from backend.application.agent.context import AgentContext
from backend.application.agent.llm_factory import get_model
from backend.application.agent.pydantic_tools import register_react_tools


WIKI_FILTER_HINT_TEMPLATE = """\
Today's date is {today} (ISO 8601). Use this as the reference point for all
relative date expressions.

When calling wiki_search, you MAY pass a `filters` object to narrow results:
- folders: array of folder names (e.g. ["ERP", "MES"])
- authors: array of author handles starting with @ (e.g. ["@동해", "@재인"])
- tags: {{"include": [...], "exclude": [...], "mode": "AND"|"OR"}}
- types: array of doc types — sop, spec, plan, decision, incident, postmortem, meeting, skill
- mtime_from / mtime_to: ISO dates, e.g. "2026-03-01"
- statuses: array of doc statuses (default excludes deprecated)

Parse natural-language date expressions into mtime_from/mtime_to using the
date above as "today":
- "최근 30일" → mtime_from = (today - 30 days)
- "지난 달" → mtime_from = first day of prev month, mtime_to = last day of prev month
- "이번 달" → mtime_from = first day of current month
- "YYYY년 M월 이후" → mtime_from = "YYYY-MM-01"

Only include filter fields you are confident about — unknown fields will narrow
the search incorrectly. If none apply, omit the `filters` argument entirely.
"""


def build_wiki_filter_hint(today: date | None = None) -> str:
    """Render the filter hint with today's date interpolated."""
    return WIKI_FILTER_HINT_TEMPLATE.format(today=(today or date.today()).isoformat())


# Back-compat alias — some tests/imports may reference the old constant name.
WIKI_FILTER_HINT = build_wiki_filter_hint()


def create_react_agent(system_prompt: str = "") -> Agent[AgentContext, str]:
    """Create a Pydantic AI agent with wiki tools for ReAct-style execution.

    Each caller can customize the system prompt while sharing the same tool set.
    The WIKI_FILTER_HINT is always appended so the LLM knows how to use the
    `filters` argument on wiki_search, including today's date for relative
    expressions like "지난 달" / "최근 30일".
    """
    base_prompt = system_prompt or "You are a helpful assistant with access to wiki tools."
    full_prompt = f"{base_prompt}\n\n{build_wiki_filter_hint()}"
    agent: Agent[AgentContext, str] = Agent(
        get_model(),
        output_type=str,
        deps_type=AgentContext,
        system_prompt=full_prompt,
        retries=2,
        defer_model_check=True,
    )
    register_react_tools(agent)
    return agent
