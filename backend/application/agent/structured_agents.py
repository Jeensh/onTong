"""Specialized Pydantic AI agents for structured output extraction.

These are lightweight agents that call the LLM once and return validated
Pydantic models — replacing manual json.loads() + .get() patterns.
"""

from __future__ import annotations

from pydantic_ai import Agent

from backend.application.agent.llm_factory import get_model
from backend.application.agent.models import (
    ClarityCheck,
    CognitiveReflection,
    IntentClassification,
    UserIntent,
)

_model = get_model()


def create_cognitive_agent(system_prompt: str) -> Agent[None, CognitiveReflection]:
    """Create an agent for cognitive reflection (hidden first-pass analysis)."""
    return Agent(
        _model,
        output_type=CognitiveReflection,
        system_prompt=system_prompt,
        retries=2,
        defer_model_check=True,
    )


def create_clarity_agent(system_prompt: str) -> Agent[None, ClarityCheck]:
    """Create an agent for clarity checking (is the query specific enough?)."""
    return Agent(
        _model,
        output_type=ClarityCheck,
        system_prompt=system_prompt,
        retries=2,
        defer_model_check=True,
    )


def create_classify_agent(system_prompt: str) -> Agent[None, IntentClassification]:
    """Create an agent for intent classification (WIKI_QA/SIMULATION/DEBUG_TRACE)."""
    return Agent(
        _model,
        output_type=IntentClassification,
        system_prompt=system_prompt,
        retries=2,
        defer_model_check=True,
    )


_INTENT_SYSTEM_PROMPT = (
    "You are an intent classifier for a corporate wiki knowledge system.\n"
    "Given a user message, determine:\n\n"
    "1. **agent** — which system should handle this:\n"
    "   - WIKI_QA: knowledge questions, document lookup, procedures, policies (DEFAULT)\n"
    "   - SIMULATION: prediction, optimization, parameter tuning, what-if scenarios\n"
    "   - DEBUG_TRACE: debugging, root cause analysis, git/commit investigation\n\n"
    "2. **action** — what the user wants to DO:\n"
    "   - question: ask about existing information, search, lookup (DEFAULT)\n"
    "   - write: CREATE new content (체크리스트, 가이드, 매뉴얼, 문서, 템플릿, 보고서 등 만들기/작성)\n"
    "   - edit: MODIFY existing content (수정, 변경, 업데이트, 편집, 고치기, 추가, 삭제)\n\n"
    "3. **confidence** — 0.0 to 1.0\n\n"
    "Rules:\n"
    "- 'write' = user wants NEW content created, even without the word '문서'\n"
    "  Examples: '체크리스트 만들어줘', '가이드 작성해줘', '보고서 써줘'\n"
    "- 'edit' = user wants to CHANGE something that already exists\n"
    "  Examples: '2단계 내용 수정해줘', '날짜 바꿔줘'\n"
    "- When a file is attached (noted in the message), bias toward 'edit'\n"
    "- When in doubt between write and question, prefer 'question'\n"
    "- When in doubt between agents, prefer 'WIKI_QA'\n"
)


def create_intent_agent() -> Agent[None, UserIntent]:
    """Create the unified intent classifier — replaces all keyword-based routing."""
    return Agent(
        _model,
        output_type=UserIntent,
        system_prompt=_INTENT_SYSTEM_PROMPT,
        retries=2,
        defer_model_check=True,
    )
