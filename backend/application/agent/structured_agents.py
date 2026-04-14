"""Specialized Pydantic AI agents for structured output extraction.

These are lightweight agents that call the LLM once and return validated
Pydantic models — replacing manual json.loads() + .get() patterns.
"""

from __future__ import annotations

from pydantic_ai import Agent

from backend.application.agent.llm_factory import get_model
from backend.application.agent.models import (
    ClarityCheck,
    IntentClassification,
    UserIntent,
)

_model = get_model()


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
    "   - question: ask for info, search, lookup, OR show examples/code inline in chat (DEFAULT)\n"
    "   - write: CREATE a NEW WIKI DOCUMENT that gets saved as a file (체크리스트 문서, 가이드 문서, 매뉴얼, 보고서 파일 등)\n"
    "   - edit: MODIFY existing wiki content (수정, 변경, 업데이트, 편집, 고치기, 추가, 삭제)\n\n"
    "3. **confidence** — 0.0 to 1.0\n\n"
    "Rules:\n"
    "- 'write' ONLY when the user clearly wants a new wiki DOCUMENT saved as a file.\n"
    "  Examples: '체크리스트 문서 만들어줘', '가이드 파일로 작성해줘', '보고서 문서 생성해줘'\n"
    "- If the user wants to SEE code, examples, samples, snippets shown inline in the chat\n"
    "  (e.g. '코드 보여줘', '예시 작성해서 보여줘', '샘플 코드 알려줘'), that's 'question' — NOT 'write'.\n"
    "- 'edit' = user wants to CHANGE something that already exists in the wiki.\n"
    "  Examples: '2단계 내용 수정해줘', '날짜 바꿔줘'\n"
    "- When a file is attached (noted in the message), bias toward 'edit'.\n"
    "- When in doubt between write and question, prefer 'question'.\n"
    "- When in doubt between agents, prefer 'WIKI_QA'.\n"
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
