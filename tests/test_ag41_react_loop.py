"""AG-4-1: Q&A ReAct loop — unit tests."""

import sys
import types
from pathlib import Path

# ── Module stubs ────────────────────────────────────────────────
for mod_name in [
    "chromadb", "chromadb.config", "pydantic_ai", "pydantic_ai.models",
    "pydantic_ai.models.openai", "pydantic_settings",
    "litellm", "httpx",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

_ps = sys.modules["pydantic_settings"]
if not hasattr(_ps, "BaseSettings"):
    _ps.BaseSettings = type("BaseSettings", (), {"model_config": {}})

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_search_evaluation_model():
    """SearchEvaluation model should have sufficient, reason, retry_query."""
    from backend.application.agent.models import SearchEvaluation

    e = SearchEvaluation(sufficient=False, reason="no match", retry_query="better query")
    assert e.sufficient is False
    assert e.retry_query == "better query"


def test_search_evaluation_defaults():
    """SearchEvaluation defaults to sufficient=True."""
    from backend.application.agent.models import SearchEvaluation

    e = SearchEvaluation()
    assert e.sufficient is True
    assert e.retry_query == ""


def test_react_constants_exist():
    """MAX_REACT_TURNS and REACT_RELEVANCE_THRESHOLD should be defined."""
    from backend.application.agent.rag_agent import MAX_REACT_TURNS, REACT_RELEVANCE_THRESHOLD

    assert MAX_REACT_TURNS >= 2
    assert 0 < REACT_RELEVANCE_THRESHOLD < 1


def test_evaluate_high_relevance_sufficient():
    """High relevance results should be marked sufficient without LLM call."""
    import asyncio
    from unittest.mock import MagicMock
    from backend.application.agent.rag_agent import RAGAgent

    agent = RAGAgent(chroma=MagicMock(), storage=MagicMock())

    result = asyncio.run(agent._evaluate_search_results(
        query="test",
        search_query="test",
        documents=["doc content"],
        metadatas=[{"path": "/a.md"}],
        distances=[0.3],  # relevance = 1 - 0.3 = 0.7 (> 0.4)
        ctx=MagicMock(),
    ))
    assert result["sufficient"] is True


def test_evaluate_empty_results_insufficient():
    """Empty search results should be marked insufficient."""
    import asyncio
    from unittest.mock import MagicMock
    from backend.application.agent.rag_agent import RAGAgent

    agent = RAGAgent(chroma=MagicMock(), storage=MagicMock())

    result = asyncio.run(agent._evaluate_search_results(
        query="test",
        search_query="test",
        documents=[],
        metadatas=[],
        distances=[],
        ctx=MagicMock(),
    ))
    assert result["sufficient"] is False


def test_qa_react_prompt_exists():
    """qa_react.md prompt file should exist."""
    from backend.application.agent.skills.prompt_loader import load_prompt

    prompt = load_prompt("qa_react")
    assert len(prompt) > 100
    assert "sufficient" in prompt.lower()
