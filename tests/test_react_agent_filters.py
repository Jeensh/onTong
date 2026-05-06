"""Integration test — verifies LLM (Pydantic AI ReAct agent) actually uses the
`filters` arg on `wiki_search` when the user query contains clear filter signals.

Gated on a configured API key so CI without secrets is skipped.

Why this test exists:
- Phase 4 MS-16 added `WIKI_FILTER_HINT` to the system prompt and exposed
  `filters` on `wiki_search`. The main RAG path uses a rule-based extractor
  (`nl_filter_extractor.py`), so the LLM tool-call path with hints is not
  exercised by existing SSE QA.
- SimulatorAgent/TracerAgent (the only live consumers of `react_loop`) aren't
  wired into `/api/agent/chat` yet. This test locks in the contract so when
  those agents go live, filter emission is already validated.

Cost: one real LLM round-trip per test case. Runs only when the configured
model can be instantiated (api key present).
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.application.agent.llm_factory import reset_model
from backend.application.agent.react_agent import create_react_agent
from backend.application.agent.skill import CompletionStatus, SkillResult


def _llm_available() -> bool:
    """Return True if the configured LITELLM_MODEL has a usable API key."""
    model = os.environ.get("LITELLM_MODEL", "")
    provider = model.split("/", 1)[0].lower() if "/" in model else "openai"
    key_env = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
    }.get(provider)
    if provider == "ollama":
        return True  # local
    if key_env is None:
        return False
    return bool(os.environ.get(key_env))


def _make_ctx(capture: list[dict[str, Any]]) -> Any:
    """Build a minimal AgentContext whose run_skill records every call.

    Returns a SkillResult with empty documents so the agent terminates fast
    after one tool call (no follow-up searches triggered by useful data).
    """
    ctx = MagicMock()
    ctx.user_roles = ["admin"]
    ctx.path_preference = None
    ctx.user_scope = None
    ctx.user_skill = None
    ctx.intent_action = "question"

    async def fake_run_skill(skill_name: str, **kwargs: Any) -> SkillResult:
        capture.append({"skill": skill_name, "kwargs": kwargs})
        return SkillResult(
            data={"documents": [], "metadatas": []},
            success=True,
            error=None,
            status=CompletionStatus.DONE,
        )

    ctx.run_skill = fake_run_skill
    return ctx


def _find_wiki_search_call(capture: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the kwargs of the first `wiki_search` call, or None."""
    for c in capture:
        if c["skill"] == "wiki_search":
            return c["kwargs"]
    return None


@pytest.mark.skipif(not _llm_available(), reason="no LLM API key for configured provider")
@pytest.mark.asyncio
async def test_react_agent_extracts_folder_filter_from_korean():
    """A query mentioning a folder name should produce filters.folders=['ERP']."""
    reset_model()
    capture: list[dict[str, Any]] = []
    ctx = _make_ctx(capture)
    agent = create_react_agent(
        "You must call the wiki_search tool with the best `filters` you can infer."
    )
    await agent.run("ERP 폴더의 마스터데이터 관리 지침 찾아줘", deps=ctx)

    call = _find_wiki_search_call(capture)
    assert call is not None, f"LLM did not call wiki_search. Captured: {capture}"
    filters = call.get("filters") or {}
    assert "ERP" in (filters.get("folders") or []), (
        f"Expected folders to contain 'ERP', got filters={filters}"
    )


@pytest.mark.skipif(not _llm_available(), reason="no LLM API key for configured provider")
@pytest.mark.asyncio
async def test_react_agent_extracts_author_and_type_filters():
    """`@동해` + `sop` in the query should surface in filters.authors + filters.types."""
    reset_model()
    capture: list[dict[str, Any]] = []
    ctx = _make_ctx(capture)
    agent = create_react_agent(
        "You must call the wiki_search tool with the best `filters` you can infer."
    )
    await agent.run("@동해가 작성한 sop 문서를 찾아줘", deps=ctx)

    call = _find_wiki_search_call(capture)
    assert call is not None, f"LLM did not call wiki_search. Captured: {capture}"
    filters = call.get("filters") or {}
    authors = filters.get("authors") or []
    types = filters.get("types") or []
    assert any("동해" in a for a in authors), (
        f"Expected authors to include '@동해', got filters={filters}"
    )
    assert "sop" in [t.lower() for t in types], (
        f"Expected types to include 'sop', got filters={filters}"
    )


@pytest.mark.skipif(not _llm_available(), reason="no LLM API key for configured provider")
@pytest.mark.asyncio
async def test_react_agent_parses_korean_date_range():
    """`지난 달 회의록` → types=['meeting'] + mtime range grounded on today's date.

    Critical: this test locks in the date-injection fix. Without the
    `Today's date is …` line in the prompt, LLMs hallucinate a prev-month
    range anchored to their training cutoff (e.g. 2024-11-01).
    """
    from datetime import date, timedelta

    reset_model()
    capture: list[dict[str, Any]] = []
    ctx = _make_ctx(capture)
    agent = create_react_agent(
        "You must call the wiki_search tool with the best `filters` you can infer."
    )
    await agent.run("지난 달 작성된 회의록 찾아줘", deps=ctx)

    call = _find_wiki_search_call(capture)
    assert call is not None, f"LLM did not call wiki_search. Captured: {capture}"
    filters = call.get("filters") or {}
    types = filters.get("types") or []
    assert "meeting" in [t.lower() for t in types], (
        f"Expected types to include 'meeting', got filters={filters}"
    )

    mtime_from = filters.get("mtime_from", "")
    assert mtime_from, f"Expected mtime_from to be set, got filters={filters}"

    # Compute expected prev-month first day from today
    today = date.today()
    first_of_this_month = today.replace(day=1)
    prev_month_last = first_of_this_month - timedelta(days=1)
    expected_prev_month = prev_month_last.strftime("%Y-%m")

    assert mtime_from.startswith(expected_prev_month), (
        f"Expected mtime_from to be in {expected_prev_month} (prev month of today "
        f"{today.isoformat()}), got {mtime_from!r} — LLM may be hallucinating a "
        f"date instead of using the 'today' value injected into the prompt."
    )
