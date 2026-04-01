"""Tests for Pydantic AI migration — validates models, factory, and tool wrappers."""

import pytest
from pydantic import ValidationError


# ── Structured Output Models ─────────────────────────────────────────


class TestCognitiveReflection:
    def test_parse_valid(self):
        from backend.application.agent.models import CognitiveReflection

        data = {
            "internal_thought": "User wants process info",
            "draft_response": "절차는 다음과 같습니다...",
            "self_critique": "Need more citations",
            "has_conflict": True,
            "conflict_details": "doc A vs doc B",
        }
        r = CognitiveReflection(**data)
        assert r.has_conflict is True
        assert r.conflict_details == "doc A vs doc B"
        assert r.internal_thought == "User wants process info"

    def test_defaults(self):
        from backend.application.agent.models import CognitiveReflection

        r = CognitiveReflection()
        assert r.has_conflict is False
        assert r.conflict_details == ""
        assert r.internal_thought == ""

    def test_model_dump_roundtrip(self):
        from backend.application.agent.models import CognitiveReflection

        r = CognitiveReflection(
            internal_thought="test",
            draft_response="답변",
            self_critique="ok",
        )
        d = r.model_dump()
        r2 = CognitiveReflection(**d)
        assert r == r2


class TestClarityCheck:
    def test_clear(self):
        from backend.application.agent.models import ClarityCheck

        r = ClarityCheck(clear=True)
        assert r.clear is True
        assert r.response == ""

    def test_unclear_with_response(self):
        from backend.application.agent.models import ClarityCheck

        r = ClarityCheck(clear=False, response="어떤 주제인가요?")
        assert r.clear is False
        assert "주제" in r.response


class TestIntentClassification:
    def test_valid_agents(self):
        from backend.application.agent.models import IntentClassification

        for agent in ("WIKI_QA", "SIMULATION", "DEBUG_TRACE"):
            r = IntentClassification(agent=agent)
            assert r.agent == agent

    def test_invalid_agent_rejected(self):
        from backend.application.agent.models import IntentClassification

        with pytest.raises(ValidationError):
            IntentClassification(agent="INVALID")

    def test_default_wiki_qa(self):
        from backend.application.agent.models import IntentClassification

        r = IntentClassification()
        assert r.agent == "WIKI_QA"


class TestWikiEditResult:
    def test_parse(self):
        from backend.application.agent.models import WikiEditResult

        r = WikiEditResult(content="# Test\nContent", summary="제목 변경")
        assert r.content == "# Test\nContent"
        assert r.summary == "제목 변경"

    def test_default_summary(self):
        from backend.application.agent.models import WikiEditResult

        r = WikiEditResult(content="test")
        assert r.summary == "문서가 수정되었습니다."


class TestWikiWriteResult:
    def test_parse(self):
        from backend.application.agent.models import WikiWriteResult

        r = WikiWriteResult(path="새문서.md", content="# 제목")
        assert r.path == "새문서.md"

    def test_default_path(self):
        from backend.application.agent.models import WikiWriteResult

        r = WikiWriteResult(content="content")
        assert r.path == "new-document.md"

    def test_content_required(self):
        from backend.application.agent.models import WikiWriteResult

        with pytest.raises(ValidationError):
            WikiWriteResult(path="test.md")


class TestConflictCheckResult:
    def test_no_conflict(self):
        from backend.application.agent.models import ConflictCheckResult

        r = ConflictCheckResult()
        assert r.has_conflict is False
        assert r.conflicting_docs == []

    def test_with_conflict(self):
        from backend.application.agent.models import ConflictCheckResult

        r = ConflictCheckResult(
            has_conflict=True,
            details="금액 차이",
            conflicting_docs=["a.md", "b.md"],
        )
        assert r.has_conflict is True
        assert len(r.conflicting_docs) == 2


# ── LLM Factory ──────────────────────────────────────────────────────


class TestLLMFactory:
    def test_get_model_id_returns_raw_model(self):
        from backend.application.agent.llm_factory import get_model_id

        model_id = get_model_id()
        assert model_id  # non-empty

    def test_get_model_returns_model_instance(self):
        from backend.application.agent.llm_factory import get_model, reset_model

        reset_model()
        model = get_model()
        assert model is not None
        reset_model()

    def test_parse_model_string(self):
        from backend.application.agent.llm_factory import _parse_model_string

        assert _parse_model_string("openai/gpt-4o-mini") == ("openai", "gpt-4o-mini")
        assert _parse_model_string("anthropic/claude-sonnet-4-20250514") == ("anthropic", "claude-sonnet-4-20250514")
        assert _parse_model_string("ollama/llama3") == ("ollama", "llama3")
        assert _parse_model_string("gpt-4o") == ("openai", "gpt-4o")  # no prefix → openai

    def test_unsupported_provider_raises(self):
        from backend.application.agent.llm_factory import _parse_model_string, PROVIDER_BUILDERS

        provider, _ = _parse_model_string("unknown/some-model")
        assert provider not in PROVIDER_BUILDERS

    def test_all_expected_providers_registered(self):
        from backend.application.agent.llm_factory import PROVIDER_BUILDERS

        expected = {"openai", "anthropic", "ollama", "google", "gemini", "azure", "groq", "deepseek"}
        assert expected == set(PROVIDER_BUILDERS.keys())


# ── Pydantic AI Tool Wrappers ────────────────────────────────────────


class TestPydanticTools:
    def test_register_tools(self):
        from pydantic_ai import Agent
        from backend.application.agent.context import AgentContext
        from backend.application.agent.pydantic_tools import register_react_tools

        agent: Agent[AgentContext, str] = Agent(
            "litellm:test",
            output_type=str,
            deps_type=AgentContext,
            defer_model_check=True,
        )
        register_react_tools(agent)
        # Verify tools were registered by checking the agent's function toolset
        tool_names = set(agent._function_toolset.tools.keys())
        assert "wiki_search" in tool_names
        assert "wiki_read" in tool_names
        assert "wiki_edit" in tool_names
        assert "wiki_write" in tool_names


# ── Structured Agent Factories ───────────────────────────────────────


class TestStructuredAgents:
    def test_create_cognitive_agent(self):
        from backend.application.agent.structured_agents import create_cognitive_agent

        agent = create_cognitive_agent("test prompt")
        assert agent is not None

    def test_create_clarity_agent(self):
        from backend.application.agent.structured_agents import create_clarity_agent

        agent = create_clarity_agent("test prompt")
        assert agent is not None

    def test_create_classify_agent(self):
        from backend.application.agent.structured_agents import create_classify_agent

        agent = create_classify_agent("test prompt")
        assert agent is not None


# ── React Agent Factory ──────────────────────────────────────────────


class TestReactAgent:
    def test_create_react_agent(self):
        from backend.application.agent.react_agent import create_react_agent

        agent = create_react_agent("You are a test agent.")
        assert agent is not None
        # Verify tools are registered
        tool_names = set(agent._function_toolset.tools.keys())
        assert "wiki_search" in tool_names


# ── litellm Import Check ─────────────────────────────────────────────


class TestLitellmRemoval:
    """Verify litellm is only imported in llm_generate.py within agent layer."""

    def test_no_litellm_in_rag_agent(self):
        import inspect
        from backend.application.agent import rag_agent

        source = inspect.getsource(rag_agent)
        # Should not import litellm at module level
        assert "import litellm" not in source

    def test_no_litellm_in_router(self):
        import inspect
        from backend.application.agent import router

        source = inspect.getsource(router)
        assert "import litellm" not in source

    def test_no_litellm_in_conflict_check(self):
        import inspect
        from backend.application.agent.skills import conflict_check

        source = inspect.getsource(conflict_check)
        assert "import litellm" not in source

    def test_no_litellm_in_wiki_write(self):
        import inspect
        from backend.application.agent.skills import wiki_write

        source = inspect.getsource(wiki_write)
        assert "import litellm" not in source

    def test_no_litellm_in_wiki_edit(self):
        import inspect
        from backend.application.agent.skills import wiki_edit

        source = inspect.getsource(wiki_edit)
        assert "import litellm" not in source

    def test_no_litellm_in_query_augment(self):
        import inspect
        from backend.application.agent.skills import query_augment

        source = inspect.getsource(query_augment)
        assert "import litellm" not in source

    def test_litellm_still_in_llm_generate(self):
        """llm_generate retains litellm for streaming/tool support."""
        import inspect
        from backend.application.agent.skills import llm_generate

        source = inspect.getsource(llm_generate)
        assert "import litellm" in source
