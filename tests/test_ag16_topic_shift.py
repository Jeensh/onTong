"""Tests for AG-1-6: query_augment strengthening + topic shift detection.

Validates:
1. QueryAugmentResult model has topic_shift field
2. QueryAugmentSkill returns topic_shift in result data
3. _augment_query returns dict with augmented_query and topic_shift
4. AUGMENT_SYSTEM_PROMPT contains topic shift rules
5. Topic shift flag is propagated correctly
"""

import asyncio
import pytest

from backend.application.agent.models import QueryAugmentResult
from backend.application.agent.skills.query_augment import (
    QueryAugmentSkill,
    AUGMENT_SYSTEM_PROMPT,
)


# ── Test 1: QueryAugmentResult model ───────────────────────────────────

class TestQueryAugmentResult:
    """Model should have augmented_query and topic_shift fields."""

    def test_default_values(self):
        r = QueryAugmentResult()
        assert r.augmented_query == ""
        assert r.topic_shift is False

    def test_with_values(self):
        r = QueryAugmentResult(augmented_query="후판 공정계획 담당자", topic_shift=True)
        assert r.augmented_query == "후판 공정계획 담당자"
        assert r.topic_shift is True

    def test_json_serialization(self):
        r = QueryAugmentResult(augmented_query="test", topic_shift=False)
        data = r.model_dump()
        assert "augmented_query" in data
        assert "topic_shift" in data


# ── Test 2: QueryAugmentSkill returns topic_shift ───────────────────────

class TestQueryAugmentSkill:
    """Skill should return topic_shift in result data."""

    def test_no_history_returns_default(self):
        skill = QueryAugmentSkill()
        result = asyncio.run(skill.execute(None, query="test", history=None))
        assert result.data["augmented_query"] == "test"
        assert result.data["topic_shift"] is False

    def test_short_history_returns_default(self):
        skill = QueryAugmentSkill()
        result = asyncio.run(skill.execute(None, query="test", history=[{"role": "user", "content": "hi"}]))
        assert result.data["topic_shift"] is False

    def test_skill_description_mentions_topic(self):
        skill = QueryAugmentSkill()
        assert "주제 전환" in skill.description


# ── Test 3: AUGMENT_SYSTEM_PROMPT content ───────────────────────────────

class TestAugmentPrompt:
    """Prompt should contain topic shift detection rules."""

    def test_prompt_mentions_topic_shift(self):
        assert "topic_shift" in AUGMENT_SYSTEM_PROMPT

    def test_prompt_has_examples(self):
        assert "Example 1" in AUGMENT_SYSTEM_PROMPT or "Example" in AUGMENT_SYSTEM_PROMPT

    def test_prompt_has_rewrite_rules(self):
        assert "subject" in AUGMENT_SYSTEM_PROMPT or "rewrite" in AUGMENT_SYSTEM_PROMPT.lower()

    def test_prompt_mentions_pronoun_handling(self):
        assert "pronoun" in AUGMENT_SYSTEM_PROMPT.lower() or "참조" in AUGMENT_SYSTEM_PROMPT


# ── Test 4: _augment_query return type ──────────────────────────────────

class TestAugmentQueryReturn:
    """_augment_query should return dict with augmented_query and topic_shift."""

    def test_no_history_returns_dict(self):
        from backend.application.agent.rag_agent import RAGAgent
        agent = RAGAgent.__new__(RAGAgent)
        result = asyncio.run(agent._augment_query("test query", []))
        assert isinstance(result, dict)
        assert result["augmented_query"] == "test query"
        assert result["topic_shift"] is False

    def test_short_history_returns_dict(self):
        from backend.application.agent.rag_agent import RAGAgent
        agent = RAGAgent.__new__(RAGAgent)
        result = asyncio.run(agent._augment_query("test", [{"role": "user", "content": "hi"}]))
        assert isinstance(result, dict)
        assert "augmented_query" in result
        assert "topic_shift" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
