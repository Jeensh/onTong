"""Tests for AG-1-4: Structured conversation summary + AG-1-5: Continuation instruction.

Validates:
1. build_history_window returns all messages when within budget
2. build_history_window prepends structured summary when messages are dropped
3. Summary includes scope, recent requests, referenced docs
4. Continuation instruction is present in summary prefix
5. ontong.md contains continuation instruction rules
"""

import sys
import types
import pytest

# Stub heavy dependencies so rag_agent can be imported without chromadb etc.
_STUBS = [
    "chromadb", "chromadb.config", "chromadb.utils", "chromadb.utils.batch_utils",
    "pydantic_ai", "litellm",
    "backend.infrastructure.vectordb.chroma",
    "backend.infrastructure.storage.base",
    "backend.infrastructure.storage.local_fs",
    "backend.core.session",
    "backend.application.agent.context",
]
for mod_name in _STUBS:
    if mod_name not in sys.modules:
        stub = types.ModuleType(mod_name)
        if "vectordb.chroma" in mod_name:
            stub.ChromaWrapper = type("ChromaWrapper", (), {})
        if "storage.base" in mod_name:
            stub.StorageProvider = type("StorageProvider", (), {})
        if "session" in mod_name:
            stub.session_store = type("SS", (), {"add_pending_action": lambda *a: "id"})()
            stub.SessionStore = type("SessionStore", (), {})
        if "context" in mod_name:
            stub.AgentContext = type("AgentContext", (), {})
        sys.modules[mod_name] = stub

from backend.application.agent.rag_agent import (
    build_history_window,
    _summarize_dropped_messages,
    get_system_prompt,
)


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_history(n: int, msg_len: int = 100) -> list[dict]:
    """Generate n alternating user/assistant message pairs."""
    history = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"{'Q' if role == 'user' else 'A'} message {i}: " + "x" * msg_len
        history.append({"role": role, "content": content})
    return history


# ── Test 1: All messages fit ────────────────────────────────────────────

class TestHistoryWindowNoSummary:
    """When all messages fit within budget, no summary is prepended."""

    def test_short_history_returns_all(self):
        history = _make_history(4, msg_len=50)
        result = build_history_window(history, max_tokens=4000)
        assert len(result) == 4
        assert all(m["role"] in ("user", "assistant") for m in result)

    def test_empty_history(self):
        assert build_history_window([], max_tokens=4000) == []

    def test_single_message(self):
        history = [{"role": "user", "content": "hello"}]
        result = build_history_window(history, max_tokens=4000)
        assert len(result) == 1


# ── Test 2: Messages dropped → summary prepended ───────────────────────

class TestHistoryWindowWithSummary:
    """When older messages are dropped, a structured summary is prepended."""

    def test_summary_prepended_when_budget_exceeded(self):
        # Each message ~100 chars = ~25 tokens. 20 messages = ~500 tokens.
        # Budget 200 tokens → should drop older messages and add summary.
        history = _make_history(20, msg_len=100)
        result = build_history_window(history, max_tokens=200)

        # First message should be the summary (system role)
        assert result[0]["role"] == "system"
        assert "[대화 요약" in result[0]["content"]

    def test_summary_contains_continuation_instruction(self):
        history = _make_history(20, msg_len=100)
        result = build_history_window(history, max_tokens=200)

        summary_content = result[0]["content"]
        assert "언급하지 말고" in summary_content or "이어서" in summary_content

    def test_summary_includes_scope(self):
        history = _make_history(20, msg_len=100)
        result = build_history_window(history, max_tokens=200)

        summary_content = result[0]["content"]
        assert "대화 규모" in summary_content

    def test_recent_messages_preserved(self):
        """The most recent messages should still be present after the summary."""
        history = _make_history(20, msg_len=100)
        result = build_history_window(history, max_tokens=200)

        # Last message in result should be the last message in history
        assert result[-1]["content"] == history[-1]["content"]


# ── Test 3: _summarize_dropped_messages ─────────────────────────────────

class TestSummarizeDroppedMessages:
    """Validate structured summary extraction."""

    def test_basic_summary(self):
        messages = [
            {"role": "user", "content": "재고 관리 규칙 알려줘"},
            {"role": "assistant", "content": "출처: wiki/inventory.md에 따르면..."},
            {"role": "user", "content": "그러면 주문 처리는?"},
            {"role": "assistant", "content": "참조: wiki/order.md 문서를 보면..."},
        ]
        summary = _summarize_dropped_messages(messages)

        assert "대화 규모" in summary
        assert "2회" in summary  # 2 user messages
        assert "이전 요청" in summary

    def test_doc_refs_extracted(self):
        messages = [
            {"role": "user", "content": "문서 찾아줘"},
            {"role": "assistant", "content": "출처: wiki/inventory.md 문서에 따르면 재고는..."},
        ]
        summary = _summarize_dropped_messages(messages)
        assert "inventory.md" in summary

    def test_skills_detected(self):
        messages = [
            {"role": "user", "content": "이 문서 수정해줘"},
            {"role": "assistant", "content": "문서를 수정했습니다."},
        ]
        summary = _summarize_dropped_messages(messages)
        assert "wiki_edit" in summary

    def test_empty_messages(self):
        assert _summarize_dropped_messages([]) == ""

    def test_only_assistant_messages(self):
        messages = [{"role": "assistant", "content": "hello"}]
        assert _summarize_dropped_messages(messages) == ""


# ── Test 4: ontong.md continuation instruction ──────────────────────────

class TestContinuationInstruction:
    """AG-1-5: ontong.md should contain explicit continuation rules."""

    def test_ontong_has_continuation_rules(self):
        prompt = get_system_prompt()
        # Should mention not acknowledging the summary
        assert "언급하지 않는다" in prompt or "메타 발언 금지" in prompt
        # Should have context awareness section
        assert "Context Awareness" in prompt

    def test_ontong_has_topic_shift_rule(self):
        prompt = get_system_prompt()
        assert "주제가 완전히 달라졌으면" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
