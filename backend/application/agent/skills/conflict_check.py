"""ConflictCheckSkill — detect contradictions across wiki documents."""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.application.agent.skill import SkillResult
from backend.application.agent.skills.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

CONFLICT_CHECK_PROMPT = load_prompt("conflict_check")
ANALYZE_PAIR_PROMPT = load_prompt("conflict_analyze_pair")


class ConflictCheckSkill:
    name = "conflict_check"
    description = "검색된 문서들 사이의 모순을 감지합니다"

    async def execute(
        self,
        ctx: Any,
        *,
        documents: list[str] | None = None,
        metadatas: list[dict] | None = None,
        distances: list[float] | None = None,
    ) -> SkillResult:
        if not documents or len(documents) < 2:
            return SkillResult(data={"has_conflict": False, "details": "", "conflicting_docs": []})

        # Build context with metadata headers
        chunks: list[str] = []
        for i, (doc, meta) in enumerate(zip(documents, metadatas or [{}] * len(documents))):
            fp = meta.get("file_path", f"doc_{i}")
            updated = meta.get("updated", "unknown")
            domain = meta.get("domain", "")
            header = f"[출처: {fp}] [수정일: {updated}] [도메인: {domain}]"
            chunks.append(f"{header}\n{doc[:500]}")

        context = "\n\n---\n\n".join(chunks)

        try:
            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model
            from backend.application.agent.models import ConflictCheckResult

            agent = Agent(
                get_model(),
                output_type=ConflictCheckResult,
                system_prompt=CONFLICT_CHECK_PROMPT,
                retries=2,
                defer_model_check=True,
            )
            result = await agent.run(f"## 문서들\n\n{context}")
            output = result.output
            return SkillResult(data={
                "has_conflict": output.has_conflict,
                "details": output.details,
                "conflicting_docs": output.conflicting_docs,
            })

        except Exception as e:
            logger.warning(f"Conflict check failed: {e}")
            return SkillResult(data={"has_conflict": False, "details": "", "conflicting_docs": []})

    @staticmethod
    async def analyze_pair(
        file_a: str, content_a: str, meta_a: dict,
        file_b: str, content_b: str, meta_b: dict,
    ) -> dict:
        """Semantic analysis of a single conflict pair using LLM.

        Returns a dict matching ConflictAnalysis fields, or empty dict on failure.
        """
        try:
            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model
            from backend.application.agent.models import ConflictAnalysis

            # Build context with both documents
            doc_a_header = f"[문서 A: {file_a}] [수정일: {meta_a.get('updated', '?')}] [상태: {meta_a.get('status', '?')}]"
            doc_b_header = f"[문서 B: {file_b}] [수정일: {meta_b.get('updated', '?')}] [상태: {meta_b.get('status', '?')}]"

            context = (
                f"## 문서 A\n{doc_a_header}\n\n{content_a[:2000]}\n\n"
                f"---\n\n"
                f"## 문서 B\n{doc_b_header}\n\n{content_b[:2000]}"
            )

            agent = Agent(
                get_model(),
                output_type=ConflictAnalysis,
                system_prompt=ANALYZE_PAIR_PROMPT,
                retries=2,
                defer_model_check=True,
            )
            result = await agent.run(context)
            output = result.output
            return {
                "conflict_type": output.conflict_type,
                "severity": output.severity,
                "summary_ko": output.summary_ko,
                "claim_a": output.claim_a,
                "claim_b": output.claim_b,
                "suggested_resolution": output.suggested_resolution,
                "resolution_detail": output.resolution_detail,
                "analyzed_at": time.time(),
            }
        except Exception as e:
            logger.warning(f"Pair analysis failed for {file_a} vs {file_b}: {e}")
            return {}

    def to_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "충돌을 감지할 주제"},
                    },
                    "required": ["query"],
                },
            },
        }
