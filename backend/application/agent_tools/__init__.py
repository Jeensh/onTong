"""Cross-cutting agent tool registry.

This package wraps onTong's Code / Ontology / Mapping graph stores as
read-only `pydantic_ai` tools that any agent (Authoring AI, future RAG
agents, etc.) can use.

Public entry point:
    from backend.application.agent_tools import register_tools, RunTracker

    tracker = RunTracker(max_calls=8)
    register_tools(
        agent,
        allowed={"code_lookup", "code_search", "find_callers"},
        tracker=tracker,
        operational_session=None,
    )
"""

from backend.application.agent_tools.registry import register_tools
from backend.application.agent_tools.sse import ToolEventPump, sse_format
from backend.application.agent_tools.tracking import (
    RunTracker,
    ToolCallLogger,
    ToolCallRecord,
    ToolStartLogger,
)

__all__ = [
    "register_tools",
    "RunTracker",
    "ToolCallLogger",
    "ToolCallRecord",
    "ToolEventPump",
    "ToolStartLogger",
    "sse_format",
]
