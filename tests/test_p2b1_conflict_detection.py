"""Tests for Phase 2-B Step 1: RAG conflict detection prompt pipeline.

Validates:
1. _build_context_with_metadata() produces correct headers
2. ConflictWarningEvent schema
3. Cognitive reflection prompt includes conflict check fields
"""

import json
import pytest
from backend.application.agent.rag_agent import RAGAgent, COGNITIVE_REFLECT_PROMPT, FINAL_ANSWER_SYSTEM_PROMPT
from backend.core.schemas import ConflictWarningEvent


# ── Test 1: _build_context_with_metadata ─────────────────────────────

class TestBuildContextWithMetadata:
    """P2B-1-1: Each document chunk should have source metadata headers."""

    def test_basic_headers(self):
        documents = ["Document A content about inventory management"]
        metadatas = [{
            "file_path": "wiki/inventory.md",
            "created_by": "김철수",
            "updated_by": "이영희",
            "updated": "2026-03-28",
            "domain": "SCM",
        }]
        distances = [0.3]

        result = RAGAgent._build_context_with_metadata(documents, metadatas, distances)

        assert "[출처: wiki/inventory.md]" in result
        assert "이영희" in result  # updated_by preferred
        assert "2026-03-28" in result
        assert "SCM" in result
        assert "70%" in result  # 1 - 0.3 = 0.7

    def test_fallback_to_created_by(self):
        """When updated_by is empty, use created_by."""
        documents = ["Content"]
        metadatas = [{"file_path": "a.md", "created_by": "홍길동", "updated_by": ""}]
        distances = [0.5]

        result = RAGAgent._build_context_with_metadata(documents, metadatas, distances)
        assert "홍길동" in result

    def test_duplicate_file_marker(self):
        """Same file appearing twice should be marked."""
        documents = ["Section 1", "Section 2"]
        metadatas = [
            {"file_path": "wiki/doc.md"},
            {"file_path": "wiki/doc.md"},
        ]
        distances = [0.2, 0.4]

        result = RAGAgent._build_context_with_metadata(documents, metadatas, distances)
        assert "[참고: 같은 파일의 다른 섹션]" in result
        # Should appear only once (second occurrence)
        assert result.count("[참고: 같은 파일의 다른 섹션]") == 1

    def test_multiple_docs_separated(self):
        """Multiple documents should be separated by ---."""
        documents = ["Doc A", "Doc B"]
        metadatas = [
            {"file_path": "a.md"},
            {"file_path": "b.md"},
        ]
        distances = [0.3, 0.5]

        result = RAGAgent._build_context_with_metadata(documents, metadatas, distances)
        assert "---" in result
        assert "[출처: a.md]" in result
        assert "[출처: b.md]" in result


# ── Test 2: ConflictWarningEvent schema ──────────────────────────────

class TestConflictWarningEvent:
    """P2B-1-4: Conflict warning event schema."""

    def test_schema_fields(self):
        evt = ConflictWarningEvent(
            details="문서 A와 B에서 재고 기준이 다름",
            conflicting_docs=["wiki/inventory_v1.md", "wiki/inventory_v2.md"],
        )
        data = json.loads(evt.model_dump_json())
        assert data["event"] == "conflict_warning"
        assert "재고" in data["details"]
        assert len(data["conflicting_docs"]) == 2

    def test_empty_docs_list(self):
        evt = ConflictWarningEvent(details="conflict found")
        assert evt.conflicting_docs == []


# ── Test 3: Prompt content checks ────────────────────────────────────

class TestConflictPrompts:
    """P2B-1-2 & P2B-1-3: System prompts include conflict detection rules."""

    def test_final_prompt_has_conflict_rules(self):
        assert "문서 간 내용 차이 감지" in FINAL_ANSWER_SYSTEM_PROMPT
        assert "최종수정일" in FINAL_ANSWER_SYSTEM_PROMPT

    def test_cognitive_prompt_has_conflict_check(self):
        assert "CONFLICT_CHECK" in COGNITIVE_REFLECT_PROMPT
        assert "has_conflict" in COGNITIVE_REFLECT_PROMPT
        assert "conflict_details" in COGNITIVE_REFLECT_PROMPT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
