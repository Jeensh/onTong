"""Pydantic AI tool wrappers that bridge existing skills to Pydantic AI Agent tooling.

These tools are used by the ReAct agent (react_agent.py) for LLM tool-calling.
They delegate to the existing SkillRegistry via ctx.deps.run_skill().

Skills that are internal-only (llm_generate, query_augment, conflict_check) are NOT
registered here — they are called via code orchestration, not LLM tool-use.
"""

import json

from pydantic_ai import Agent, RunContext

from backend.application.agent.context import AgentContext


def register_react_tools(agent: Agent[AgentContext, str]) -> None:
    """Register LLM-callable tools on a Pydantic AI agent."""

    @agent.tool
    async def wiki_search(
        ctx: RunContext[AgentContext],
        query: str,
        n_results: int = 8,
        filters: dict | None = None,
    ) -> str:
        """Search the wiki knowledge base with optional metadata filters.

        Args:
            query: Natural-language or keyword query.
            n_results: Max documents to return (default 8).
            filters: Optional FilterSpec dict with any of these keys:
                - folders: list[str], e.g. ["ERP", "MES"]
                - authors: list[str], e.g. ["@동해", "@재인"]
                - tags: {"include": [...], "exclude": [...], "mode": "AND"|"OR"}
                - types: list[str], e.g. ["sop", "spec", "decision", "incident"]
                - mtime_from: ISO date string, e.g. "2026-03-01"
                - mtime_to: ISO date string
                - statuses: list[str], e.g. ["active", "review"]
                - path: glob string, e.g. "wiki/ERP/**"
                - boolean: Boolean DSL string, e.g. "(tag:재고 OR tag:주문) AND !author:@민수"

        Parse natural-language date expressions ("최근 30일", "지난 달",
        "2026년 3월 이후") into `mtime_from`/`mtime_to` before passing.

        Returns matching documents with their paths.
        """
        kwargs = {"query": query, "n_results": n_results}
        if filters:
            kwargs["filters"] = filters
        result = await ctx.deps.run_skill("wiki_search", **kwargs)
        if not result.success:
            return f"Error: {result.error}"
        # Return documents + metadata for LLM consumption
        docs = result.data.get("documents", [])
        metas = result.data.get("metadatas", [])
        output = []
        for doc, meta in zip(docs, metas):
            path = meta.get("path", "unknown")
            output.append(f"[{path}]\n{doc}")
        return "\n---\n".join(output) if output else "No results found."

    @agent.tool
    async def wiki_read(ctx: RunContext[AgentContext], path: str) -> str:
        """Read a specific wiki document by its file path."""
        result = await ctx.deps.run_skill("wiki_read", path=path)
        if not result.success:
            return f"Error: {result.error}"
        return result.data if isinstance(result.data, str) else json.dumps(result.data, ensure_ascii=False)

    @agent.tool
    async def wiki_edit(
        ctx: RunContext[AgentContext], instruction: str, target_path: str = ""
    ) -> str:
        """Edit an existing wiki document based on the instruction."""
        kwargs = {"instruction": instruction}
        if target_path:
            kwargs["target_path"] = target_path
        result = await ctx.deps.run_skill("wiki_edit", **kwargs)
        if not result.success:
            return f"Error: {result.error}"
        return json.dumps(
            {"path": result.data.get("path", ""), "summary": result.data.get("summary", "")},
            ensure_ascii=False,
        )

    @agent.tool
    async def wiki_write(ctx: RunContext[AgentContext], instruction: str) -> str:
        """Create a new wiki document based on the instruction."""
        result = await ctx.deps.run_skill("wiki_write", instruction=instruction)
        if not result.success:
            return f"Error: {result.error}"
        return json.dumps(
            {"path": result.data.get("path", ""), "content_preview": result.data.get("content", "")[:200]},
            ensure_ascii=False,
        )
