"""RAG Agent — WIKI_QA: vector search → cognitive pipeline → streamed answer.

Supports three modes:
1. Clarification — asks follow-up questions when query is ambiguous
2. Normal Q&A — retrieves docs, runs self-reflective cognitive pipeline, streams answer
3. Wiki modification — detects write intent, generates content, emits ApprovalRequestEvent

Cognitive Pipeline (Option A — Two-Step Run):
  Step 1 (Hidden): LLM generates internal_thought + draft + self_critique → backend log only
  Step 2 (Visible): LLM takes critique context → streams polished final answer via SSE

Refactored to delegate capabilities to skills (wiki_search, llm_generate, wiki_edit, etc.)
while keeping orchestration logic here.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import AsyncGenerator

from backend.core.schemas import (
    ApprovalRequestEvent,
    ChatRequest,
    ClarificationRequestEvent,
    ConflictPair,
    ConflictWarningEvent,
    ContentDelta,
    DoneEvent,
    ErrorEvent,
    SkillContext,
    SourceRef,
    SourcesEvent,
    ThinkingStepEvent,
    TokenUsage,
)
from backend.core.session import session_store
from backend.infrastructure.storage.base import StorageProvider
from backend.infrastructure.vectordb.chroma import ChromaWrapper
from backend.application.agent.context import AgentContext

logger = logging.getLogger(__name__)


# ── Thresholds ────────────────────────────────────────────────────────

LOW_RELEVANCE_THRESHOLD = 0.55
MIN_SOURCE_RELEVANCE = 0.30
MAX_REACT_TURNS = 3  # max search attempts in ReAct loop
REACT_RELEVANCE_THRESHOLD = 0.25  # below this, results are considered insufficient

# Cognitive reflect pipeline removed (AG-1-8).
# Quality gates moved to ontong.md; conflict detection via conflict_check skill.
COGNITIVE_REFLECT_PROMPT = None

_ONTONG_MD_PATH = Path(__file__).resolve().parent.parent.parent / "ontong.md"


@lru_cache(maxsize=1)
def _load_ontong_md() -> str:
    """Load ontong.md as the base system prompt. Cached after first read."""
    try:
        return _ONTONG_MD_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("ontong.md not found at %s, using fallback", _ONTONG_MD_PATH)
        return (
            "당신은 On-Tong, 사내 Wiki 지식 관리 시스템의 AI 어시스턴트입니다.\n"
            "검색된 문서를 기반으로 간결하고 정확하게 답변하세요.\n"
            "문서에 없는 내용은 추측하지 마세요."
        )


def get_system_prompt() -> str:
    """Return the current ontong.md system prompt."""
    return _load_ontong_md()


# ── Scoring config ──────────────────────────────────────────────────
from backend.application.trust.scoring_config import SCORING as _SCORING

# ── Per-user persona (ontong.local.md) ───────────────────────────────

import time as _time

_persona_cache: dict[str, tuple[str, float]] = {}
_PERSONA_TTL = 60  # seconds


def invalidate_persona_cache(username: str) -> None:
    """Called when a user updates their persona settings."""
    _persona_cache.pop(username, None)


async def get_user_persona(username: str, storage: object) -> str:
    """Load per-user persona markdown (freeform). Returns empty string if not set.

    The persona file is a regular wiki document edited by the user in Tiptap.
    Its full content is injected into the system prompt as-is.
    """
    if not username or not storage:
        return ""

    cached = _persona_cache.get(username)
    if cached and (_time.time() - cached[1]) < _PERSONA_TTL:
        return cached[0]

    path = f"_personas/@{username}/ontong.local.md"
    try:
        wiki_file = await storage.read(path)  # type: ignore[union-attr]
        if not wiki_file:
            _persona_cache[username] = ("", _time.time())
            return ""

        content = wiki_file.content.strip()

        # Strip YAML frontmatter if present (wiki storage may add it)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()

        # Skip template-only content (guide comments with no real instructions)
        # If the content is mostly HTML comments, treat as empty
        import re
        stripped = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL).strip()
        stripped = re.sub(r"^#+\s+.*$", "", stripped, flags=re.MULTILINE).strip()
        stripped = re.sub(r"^>.*$", "", stripped, flags=re.MULTILINE).strip()
        if not stripped:
            _persona_cache[username] = ("", _time.time())
            return ""

        _persona_cache[username] = (content, _time.time())
        return content
    except Exception as e:
        logger.debug(f"Failed to load persona for '{username}': {e}")
        return ""


async def build_system_prompt(username: str, storage: object) -> str:
    """Build the full system prompt: base ontong.md + per-user persona."""
    base = get_system_prompt()
    persona = await get_user_persona(username, storage)
    if persona:
        return base + "\n\n---\n\n## 사용자 개인 설정\n\n" + persona
    return base


def build_history_window(
    history: list[dict], max_tokens: int = 4000
) -> list[dict]:
    """Select recent messages that fit within a token budget.

    When older messages are dropped, a structured summary is prepended
    so the LLM retains awareness of the full conversation scope.
    """
    if not history:
        return []

    window: list[dict] = []
    token_count = 0
    cutoff_idx = len(history)  # index where we stopped including

    for i, msg in enumerate(reversed(history)):
        est = len(msg.get("content", "")) // 4
        if token_count + est > max_tokens:
            cutoff_idx = len(history) - i
            break
        token_count += est
        window.insert(0, msg)

    # If all messages fit, no summary needed
    if cutoff_idx == len(history) or cutoff_idx == 0:
        return window

    # Build structured summary of dropped messages
    dropped = history[:cutoff_idx]
    summary = _summarize_dropped_messages(dropped)
    if summary:
        summary_msg = {
            "role": "system",
            "content": (
                "[대화 요약 — 이전 대화 내용을 요약한 것입니다. "
                "이 요약을 언급하지 말고 자연스럽게 이어서 답변하세요.]\n\n"
                + summary
            ),
        }
        window.insert(0, summary_msg)

    return window


def _summarize_dropped_messages(messages: list[dict]) -> str:
    """Rule-based structured summary of dropped conversation messages.

    Extracts: scope, referenced docs, recent requests, skills used, current work.
    No LLM call — pure extraction from message content.
    """
    user_messages = [m for m in messages if m.get("role") == "user"]
    assistant_messages = [m for m in messages if m.get("role") == "assistant"]

    if not user_messages:
        return ""

    parts: list[str] = []

    # 1. Scope
    total_turns = len(user_messages)
    parts.append(f"- **대화 규모**: 사용자 {total_turns}회 질문")

    # 2. Recent requests (last 3 user messages from dropped portion)
    recent_requests = []
    for msg in user_messages[-3:]:
        content = msg.get("content", "").strip()
        if content:
            # Truncate long messages
            truncated = content[:80] + ("..." if len(content) > 80 else "")
            recent_requests.append(truncated)
    if recent_requests:
        req_lines = "\n".join(f"  - {r}" for r in recent_requests)
        parts.append(f"- **이전 요청**:\n{req_lines}")

    # 3. Referenced docs — extract file paths from assistant responses
    doc_refs: set[str] = set()
    doc_pattern = re.compile(r'(?:출처|참조|📄)\s*[:\s]*([^\s\n\]]+\.md)', re.IGNORECASE)
    for msg in assistant_messages:
        content = msg.get("content", "")
        for match in doc_pattern.finditer(content):
            doc_refs.add(match.group(1))
    if doc_refs:
        parts.append(f"- **참조된 문서**: {', '.join(sorted(doc_refs)[:5])}")

    # 4. Skills used — detect skill keywords
    skill_keywords = {
        "수정": "wiki_edit", "생성": "wiki_write", "검색": "wiki_search",
        "시뮬레이션": "simulation", "인덱싱": "reindex",
    }
    skills_used: set[str] = set()
    for msg in user_messages:
        content = msg.get("content", "")
        for keyword, skill in skill_keywords.items():
            if keyword in content:
                skills_used.add(skill)
    if skills_used:
        parts.append(f"- **사용된 기능**: {', '.join(sorted(skills_used))}")

    # 5. Current work — last assistant response summary
    if assistant_messages:
        last_assist = assistant_messages[-1].get("content", "").strip()
        if last_assist:
            summary_line = last_assist[:120] + ("..." if len(last_assist) > 120 else "")
            parts.append(f"- **마지막 응답 요약**: {summary_line}")

    return "\n".join(parts)


# Keep legacy name for backward compatibility in imports (e.g., tests)
FINAL_ANSWER_SYSTEM_PROMPT = None  # Replaced by ontong.md — use get_system_prompt()

CLARITY_CHECK_PROMPT = (
    "You are a helpful assistant for a corporate wiki knowledge system.\n"
    "The user asked a question and we searched the wiki. Below are the search results.\n\n"
    "Your job: decide if the query is specific enough to answer directly.\n\n"
    "Mark as CLEAR (answer directly) when:\n"
    "- The query asks about a specific topic, person, process, or keyword\n"
    "- The search results contain documents clearly related to the query\n"
    "- Even short queries ('포스코 OJT 진행자') are clear if results match\n"
    "- The query mentions a company, team, role, or specific term\n"
    "- There are ANY search results with relevance > 30%\n\n"
    "Mark as UNCLEAR only when:\n"
    "- The query has NO specific topic at all (e.g., just '알려줘' or '도와줘')\n"
    "- Search results are about completely unrelated topics\n\n"
    "BIAS STRONGLY TOWARD CLEAR. If there is any doubt, choose CLEAR.\n\n"
    "If UNCLEAR, generate a clarifying response using MARKDOWN formatting:\n"
    "- Use **bold** for names and key terms\n"
    "- Use numbered list (1. 2. 3.) for options\n"
    "- Use line breaks between sections\n\n"
    "Respond in this exact JSON format (no markdown fences):\n"
    '{"clear": true}\n'
    "or\n"
    '{"clear": false, "response": "마크다운 형식으로 검색 결과 요약 + 선택지 제시 + 질문"}\n\n'
    "Example UNCLEAR response format:\n"
    '{"clear": false, "response": "Wiki에서 관련 문서를 찾았습니다.\\n\\n'
    "1. **김태헌** — 포스코DX 후판공정계획\\n"
    "2. **장은영** — 포스코DX 마케팅DX그룹\\n\\n"
    '어떤 분에 대해 더 알고 싶으신가요?"}\n\n'
    "IMPORTANT:\n"
    "- Always respond in Korean\n"
    "- A query with a company name, person name, team, OJT, error code, or topic keyword → ALWAYS CLEAR\n"
)


# Intent detection is now handled by the LLM-based router (UserIntent model).
# The router passes intent.action ("question" | "write" | "edit") to execute().


def _extract_pair_summary(file_a: str, file_b: str, conflict_details: str) -> str:
    """Extract a concise summary relevant to a specific file pair from conflict_details.

    If the details text mentions both files, extract the first complete sentence
    that references them. Otherwise, take the first sentence of the details.
    """
    if not conflict_details:
        return ""

    # Try to find a sentence mentioning either file
    name_a = file_a.split("/")[-1].replace(".md", "")
    name_b = file_b.split("/")[-1].replace(".md", "")

    # Split on sentence boundaries (Korean period, newline)
    sentences = [s.strip() for s in conflict_details.replace("\n", ". ").split(". ") if s.strip()]
    if not sentences:
        return conflict_details[:150]

    # Prefer sentences mentioning both files
    for s in sentences:
        if name_a in s and name_b in s:
            return s[:150]

    # Fallback: first sentence only
    return sentences[0][:150]


class RAGAgent:
    name = "WIKI_QA"

    def __init__(self, chroma: ChromaWrapper, storage: StorageProvider | None = None) -> None:
        self.chroma = chroma
        self.storage = storage
        self._confidence_service = None  # set via set_confidence_service()
        self._citation_tracker = None    # set via set_citation_tracker()

    def set_confidence_service(self, svc: object) -> None:
        self._confidence_service = svc

    def set_citation_tracker(self, tracker: object) -> None:
        self._citation_tracker = tracker

    async def execute(
        self, request: ChatRequest, metadata_filter: dict | None = None,
        history: list[dict] | None = None, attached_context: str = "",
        augmented_query: str | None = None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Execute RAG pipeline, yielding SSE events."""
        query = request.message
        history = history or []

        # Extract AgentContext if provided (Phase 4+), otherwise build a minimal one
        ctx: AgentContext | None = kwargs.get("ctx")

        # User-facing skill matched → delegate to skill-based Q&A
        if ctx and ctx.user_skill:
            async for event in self._handle_skill_qa(request, ctx):
                yield event
            return

        # Determine action from LLM-based intent (passed from router via kwargs)
        intent = kwargs.get("intent")
        action = getattr(intent, "action", "question") if intent else "question"

        if action == "edit":
            async for event in self._handle_edit(request, history, ctx=ctx):
                yield event
            return

        # Wiki chat is Q&A-only. Document creation ('write') is handled by
        # explicit UI affordances (tree create, editor), not the chat endpoint.
        # Fall through to Q&A so the answer is rendered inline (including
        # code blocks) instead of silently creating a wiki file.
        if action == "write":
            action = "question"

        # Normal Q&A flow (with clarification check)
        async for event in self._handle_qa(
            request, metadata_filter, history, attached_context,
            augmented_query, ctx=ctx, user_roles=kwargs.get("user_roles", ["admin"]),
            topic_shift=kwargs.get("topic_shift", False),
        ):
            yield event

    async def _augment_query(self, query: str, history: list[dict]) -> dict:
        """Augment follow-up queries with context from conversation history.

        Called from api/agent.py for parallel pre-computation (before ctx exists).
        Returns dict with 'augmented_query' and 'topic_shift' keys.
        """
        default = {"augmented_query": query, "topic_shift": False}
        if not history or len(history) < 2:
            return default

        recent_context = []
        for msg in history[-4:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                recent_context.append(content)
            elif role == "assistant":
                recent_context.append(content[:100])

        try:
            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model
            from backend.application.agent.models import QueryAugmentResult
            from backend.application.agent.skills.query_augment import AUGMENT_SYSTEM_PROMPT

            agent = Agent(
                get_model(),
                output_type=QueryAugmentResult,
                system_prompt=AUGMENT_SYSTEM_PROMPT,
                retries=1,
                defer_model_check=True,
            )
            result = await agent.run(
                f"Conversation context:\n{chr(10).join(recent_context)}\n\n"
                f"Follow-up question: {query}"
            )
            output = result.output
            augmented = output.augmented_query.strip() or query
            logger.info(f"Query augmented: '{query}' → '{augmented}' (topic_shift={output.topic_shift})")
            return {"augmented_query": augmented, "topic_shift": output.topic_shift}
        except Exception as e:
            logger.warning(f"Query augmentation failed: {e}, using original query")

        return default

    async def _evaluate_search_results(
        self,
        query: str,
        search_query: str,
        documents: list[str],
        metadatas: list[dict],
        distances: list[float],
        ctx: AgentContext,
    ) -> dict:
        """ReAct: evaluate if search results can answer the question.

        Returns dict with 'sufficient', 'reason', 'retry_query'.
        Uses rule-based check first; falls back to LLM only when ambiguous.
        """
        # Rule-based fast path
        if not documents:
            return {"sufficient": False, "reason": "no results", "retry_query": query}

        best_relevance = max(0, 1 - min(distances)) if distances else 0

        # High relevance → sufficient
        if best_relevance >= 0.4:
            return {"sufficient": True, "reason": "high relevance", "retry_query": ""}

        # Very low relevance → insufficient, try LLM for refined query
        if best_relevance < REACT_RELEVANCE_THRESHOLD:
            try:
                from pydantic_ai import Agent
                from backend.application.agent.llm_factory import get_model
                from backend.application.agent.models import SearchEvaluation
                from backend.application.agent.skills.prompt_loader import load_prompt

                doc_summaries = []
                for doc, meta, dist in zip(documents[:5], metadatas[:5], distances[:5]):
                    title = meta.get("path", meta.get("file_path", "unknown"))
                    relevance = max(0, 1 - dist)
                    doc_summaries.append(f"- {title} (관련도: {relevance:.0%}): {doc[:150]}...")

                eval_prompt = load_prompt("qa_react")
                agent = Agent(
                    get_model(),
                    output_type=SearchEvaluation,
                    system_prompt=eval_prompt,
                    retries=1,
                    defer_model_check=True,
                )
                result = await agent.run(
                    f"User question: {query}\n"
                    f"Search query used: {search_query}\n"
                    f"Search results:\n" + "\n".join(doc_summaries)
                )
                output = result.output
                return {
                    "sufficient": output.sufficient,
                    "reason": output.reason,
                    "retry_query": output.retry_query if not output.sufficient else "",
                }
            except Exception as e:
                logger.warning(f"ReAct evaluation failed: {e}, treating as sufficient")
                return {"sufficient": True, "reason": "eval_error", "retry_query": ""}

        # Moderate relevance → sufficient (answer with what's available)
        return {"sufficient": True, "reason": "moderate relevance", "retry_query": ""}

    async def _handle_qa(
        self, request: ChatRequest, metadata_filter: dict | None = None,
        history: list[dict] | None = None, attached_context: str = "",
        augmented_query: str | None = None, *,
        ctx: AgentContext | None = None, user_roles: list = None,
        topic_shift: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Standard RAG Q&A: clarity check → search (skill) → cognitive pipeline → LLM answer (skill)."""
        query = request.message
        history = history or []
        user_roles = user_roles or (ctx.user_roles if ctx else ["admin"])

        # 0. Query augmentation (pre-computed in parallel at API layer, or fallback here)
        import asyncio as _asyncio

        is_followup = len(history) >= 2
        if augmented_query and augmented_query != query:
            search_query = augmented_query
            shift_label = " [주제 전환]" if topic_shift else ""
            yield self._thinking("query_augment", "done", f"쿼리 보강 완료 (병렬){shift_label}", search_query)
        elif is_followup:
            yield self._thinking("query_augment", "start", "검색 쿼리 보강 중")
            augment_result = await self._augment_query(query, history)
            search_query = augment_result["augmented_query"]
            topic_shift = augment_result["topic_shift"]
            shift_label = " [주제 전환]" if topic_shift else ""
            if search_query != query:
                yield self._thinking("query_augment", "done", f"쿼리 보강 완료{shift_label}", search_query)
            else:
                yield self._thinking("query_augment", "done", f"쿼리 보강 완료{shift_label}")
        else:
            search_query = query

        # 1. Hybrid search via wiki_search skill (with ReAct loop)
        yield self._thinking("vector_search", "start", "관련 문서 검색 중")

        # Topic shift → clear path preferences so old folder scope doesn't contaminate new search
        if topic_shift and ctx:
            if ctx.path_preference or ctx.path_preferences:
                logger.info(f"Topic shift — clearing path prefs: pref={ctx.path_preference}, prefs={ctx.path_preferences}")
                ctx.path_preference = None
                ctx.path_preferences = []

        if ctx:
            # ReAct loop: search → evaluate → re-search if insufficient
            tried_queries: list[str] = []
            for react_turn in range(MAX_REACT_TURNS):
                search_result = await ctx.run_skill(
                    "wiki_search",
                    query=search_query,
                    n_results=8,
                    metadata_filter=metadata_filter,
                    user_roles=user_roles,
                    path_preference=ctx.path_preference if ctx else None,
                    user_scope=ctx.user_scope if ctx else None,
                )
                if not search_result.success:
                    yield self._sse("content_delta", ContentDelta(
                        delta=f"검색 실패: {search_result.error}"
                    ).model_dump_json())
                    yield self._sse("done", DoneEvent().model_dump_json())
                    return

                documents = search_result.data["documents"]
                metadatas = search_result.data["metadatas"]
                distances = search_result.data["distances"]
                search_mode = search_result.data["search_mode"]

                # Surface non-fatal feedback (e.g., deprecated doc warnings)
                if search_result.feedback:
                    logger.info(f"Search feedback: {search_result.feedback}")
                    yield self._thinking("vector_search", "info", search_result.feedback)

                tried_queries.append(search_query)

                # Evaluate: should we re-search?
                if react_turn < MAX_REACT_TURNS - 1 and documents:
                    evaluation = await self._evaluate_search_results(
                        query, search_query, documents, metadatas, distances, ctx,
                    )
                    if evaluation["sufficient"]:
                        break
                    retry_query = evaluation["retry_query"]
                    if retry_query and retry_query not in tried_queries:
                        logger.info(
                            f"ReAct turn {react_turn + 1}: re-searching "
                            f"(reason: {evaluation['reason']}, new query: '{retry_query}')"
                        )
                        yield self._thinking(
                            "vector_search", "retry",
                            f"재검색 중 ({evaluation['reason']})",
                            retry_query,
                        )
                        search_query = retry_query
                        continue
                break  # sufficient or no retry_query
        else:
            # Fallback: direct search (backward compatibility without ctx)
            from backend.application.agent.filter_extractor import (
                extract_metadata_filter as _extract,
                extract_query_tags as _extract_tags,
            )
            from backend.infrastructure.search.bm25 import bm25_index
            from backend.infrastructure.search.hybrid import reciprocal_rank_fusion
            from backend.infrastructure.cache.query_cache import query_cache as _cache
            from backend.core.auth.acl_store import acl_store

            base_filter = metadata_filter or _extract(search_query)
            deprecated_filter = {"status": {"$ne": "deprecated"}}
            effective_filter = self._merge_where_filters(base_filter, deprecated_filter)

            # B1: extract tag concepts from query for boost + fallback
            query_tags: list[str] = _extract_tags(search_query)

            cached = _cache.get(search_query, effective_filter)
            if cached:
                results = cached
                search_mode = "캐시"
            else:
                if effective_filter:
                    vector_results = self.chroma.query_with_filter(
                        query_text=search_query, n_results=8, where=effective_filter
                    )
                else:
                    vector_results = self.chroma.query(query_text=search_query, n_results=8)

                v_docs = vector_results.get("documents", [[]])[0]
                # B3: tag-only fallback before fully removing the filter
                if effective_filter and not v_docs and query_tags:
                    tag_filter = self._build_tag_filter(query_tags, deprecated_filter)
                    if tag_filter:
                        tag_results = self.chroma.query_with_filter(
                            query_text=search_query, n_results=8, where=tag_filter
                        )
                        if tag_results.get("documents", [[]])[0]:
                            vector_results = tag_results
                            effective_filter = tag_filter
                            v_docs = vector_results["documents"][0]
                            logger.info(f"Tag-only fallback hit ({len(v_docs)} docs) for tags={query_tags}")

                if effective_filter and not v_docs:
                    vector_results = self.chroma.query(query_text=search_query, n_results=8)
                    effective_filter = None

                bm25_results = bm25_index.search(search_query, n_results=8)
                if bm25_results:
                    results = reciprocal_rank_fusion(vector_results, bm25_results, n_results=8)
                    search_mode = "하이브리드"
                else:
                    results = vector_results
                    search_mode = "벡터"

                _cache.put(search_query, results, effective_filter)

            documents = results["documents"][0] if results["documents"][0] else []
            metadatas = results["metadatas"][0] if results["metadatas"][0] else []
            distances = results["distances"][0] if results["distances"][0] else []

            # Post-RRF deprecated filter
            if documents:
                filtered = [
                    (doc, meta, dist)
                    for doc, meta, dist in zip(documents, metadatas, distances)
                    if meta.get("status") != "deprecated"
                ]
                if filtered:
                    documents, metadatas, distances = map(list, zip(*filtered))
                else:
                    documents, metadatas, distances = [], [], []

            # ACL filter
            acl_user = ctx.user if ctx else None
            if documents and acl_user:
                acl_filtered = [
                    (doc, meta, dist)
                    for doc, meta, dist in zip(documents, metadatas, distances)
                    if acl_store.check_permission(meta.get("path", ""), acl_user, "read")
                ]
                if acl_filtered:
                    documents, metadatas, distances = map(list, zip(*acl_filtered))
                else:
                    documents, metadatas, distances = [], [], []

            # B2: tag intersection boost rerank
            if documents and query_tags:
                import os
                boost_weight = float(os.environ.get("ONTONG_TAG_BOOST_WEIGHT", "0.05"))
                if boost_weight > 0:
                    documents, metadatas, distances = self._tag_boost_rerank(
                        documents, metadatas, distances, query_tags, weight=boost_weight
                    )

        doc_count = len(documents)
        if doc_count > 0:
            best_rel = max(0, 1 - min(distances)) if distances else 0
            yield self._thinking("vector_search", "done", "문서 검색 완료", f"{doc_count}건 ({search_mode}, 최고 관련도 {best_rel:.0%})")
        else:
            yield self._thinking("vector_search", "done", "문서 검색 완료", "0건")

        # 2. Build context from retrieved docs
        if not documents:
            yield self._sse("content_delta", ContentDelta(
                delta=(
                    "Wiki에서 관련 문서를 찾지 못했습니다.\n\n"
                    "다음과 같이 질문해보시면 도움이 될 수 있습니다:\n"
                    "- \"주문 처리 규칙 알려줘\"\n"
                    "- \"DG320 에러 대응 방법은?\"\n"
                    "- \"재고 관리 절차가 어떻게 돼?\""
                )
            ).model_dump_json())
            yield self._sse("done", DoneEvent().model_dump_json())
            return

        # 2.5. L3: Path divergence disambiguation
        import os as _os
        _disambig_enabled = _os.environ.get("ONTONG_PATH_DISAMBIG_ENABLED", "true").lower() == "true"
        _has_path_pref = ctx and (ctx.path_preference or ctx.path_preferences)
        if _disambig_enabled and documents and not is_followup and not _has_path_pref:
            _min_paths = int(_os.environ.get("ONTONG_PATH_DISAMBIG_MIN_PATHS", "3"))
            _dominance = float(_os.environ.get("ONTONG_PATH_DISAMBIG_DOMINANCE", "0.70"))
            is_ambiguous, path_stats = self._detect_path_ambiguity(
                metadatas, distances, min_paths=_min_paths, dominance_ratio=_dominance,
            )
            if is_ambiguous:
                logger.info(f"Path ambiguity detected: {path_stats}")
                options = [p for p, _c, _r in path_stats[:5]]
                import uuid as _uuid
                evt = ClarificationRequestEvent(
                    request_id=str(_uuid.uuid4()),
                    question="검색 결과가 여러 영역에 걸쳐 있습니다. 어떤 영역의 문서를 찾으시나요?",
                    options=options,
                    context=f"path_disambiguation:{search_query}",
                )
                yield self._sse("clarification_request", evt.model_dump_json())
                yield self._sse("done", DoneEvent().model_dump_json())
                return

        # L4: Path boost rerank (session-accumulated preferences)
        if ctx and ctx.path_preferences and documents:
            _path_weight = float(_os.environ.get("ONTONG_PATH_BOOST_WEIGHT", "0.08"))
            if _path_weight > 0:
                documents, metadatas, distances = self._path_boost_rerank(
                    documents, metadatas, distances, ctx.path_preferences, weight=_path_weight,
                )

        # 3. Clarity check — short vague queries with mediocre results
        best_distance = min(distances) if distances else 1.0
        best_relevance = max(0, 1 - best_distance)
        query_too_short = len(query.strip()) < 8
        results_ambiguous = best_relevance < 0.40
        needs_clarity_check = query_too_short and results_ambiguous

        if needs_clarity_check and not is_followup:
            yield self._thinking("clarity_check", "start", "질문 명확성 확인 중")
            clarification = self._check_clarity_rule_based(query, metadatas, distances)
            if clarification:
                yield self._thinking("clarity_check", "done", "명확화 질문 필요", "추가 정보 요청")
                clarify_sources = self._build_sources(metadatas, distances, threshold=0.2, confidence_service=self._confidence_service)
                if clarify_sources:
                    yield self._sse("sources", SourcesEvent(sources=clarify_sources).model_dump_json())

                # Build structured clarification options from search results
                options = self._build_clarification_options(metadatas, distances)
                if options:
                    import uuid as _uuid
                    evt = ClarificationRequestEvent(
                        request_id=str(_uuid.uuid4()),
                        question=f"Wiki에서 관련 문서를 찾았습니다.\n\n어떤 내용에 대해 알고 싶으신가요?",
                        options=options,
                        context=query,
                    )
                    yield self._sse("clarification_request", evt.model_dump_json())
                else:
                    yield self._sse("content_delta", ContentDelta(delta=clarification).model_dump_json())
                yield self._sse("done", DoneEvent().model_dump_json())
                return

        # 3.5. Replace deprecated docs with their latest version via superseded_by chain
        supersede_map = {
            meta.get("file_path", ""): meta.get("superseded_by", "")
            for meta in metadatas if meta.get("superseded_by")
        }
        if supersede_map:
            replaced = await self._replace_deprecated_with_latest(
                documents, metadatas, distances, supersede_map
            )
            if replaced:
                logger.info(f"Replaced {replaced} deprecated doc(s) with latest version")

        # 4. Filter by relevance — keep aligned triples
        relevant_docs = []
        relevant_metas = []
        relevant_dists = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            if max(0, 1 - dist) >= MIN_SOURCE_RELEVANCE:
                relevant_docs.append(doc)
                relevant_metas.append(meta)
                relevant_dists.append(dist)

        sources = self._build_sources(metadatas, distances, threshold=MIN_SOURCE_RELEVANCE, confidence_service=self._confidence_service)
        if sources:
            yield self._sse("sources", SourcesEvent(sources=sources).model_dump_json())
            self._record_citations(sources)

        if not relevant_docs:
            relevant_docs = [documents[0]]
            relevant_metas = [metadatas[0]] if metadatas else [{}]
            relevant_dists = [distances[0]] if distances else [1.0]

        # ── 5. Build context + conflict detection ─────────────────────────
        context = self._build_context_with_metadata(relevant_docs, relevant_metas, relevant_dists)

        if attached_context:
            context = attached_context.strip() + "\n\n---\n\n" + context

        # 5a. Conflict detection via dedicated skill
        has_conflict = False
        conflict_details = ""
        unique_sources = {m.get("file_path", "") for m in relevant_metas}
        high_relevance_sources = {
            m.get("file_path", "")
            for m, d in zip(relevant_metas, relevant_dists)
            if max(0, 1 - d) >= 0.6
        }
        if len(high_relevance_sources) >= 2 and ctx:
            try:
                conflict_result = await ctx.run_skill(
                    "conflict_check",
                    documents=relevant_docs,
                    metadatas=relevant_metas,
                    distances=relevant_dists,
                )
                if conflict_result and conflict_result.data.get("has_conflict"):
                    has_conflict = True
                    conflict_details = conflict_result.data.get("details", "")
                    logger.info(f"Dedicated conflict_check detected: {conflict_details[:100]}")
            except Exception as e:
                logger.debug(f"Dedicated conflict check skipped: {e}")

        if has_conflict:
            conflicting_docs = sorted(unique_sources) if unique_sources else (
                [s.doc for s in sources] if sources else []
            )
            # Build explicit conflict pairs for comparison UI
            pairs: list[ConflictPair] = []
            if len(conflicting_docs) >= 2:
                pairs = self._build_conflict_pairs(
                    conflicting_docs, relevant_metas, relevant_dists, conflict_details,
                )
            yield self._sse(
                "conflict_warning",
                ConflictWarningEvent(
                    details=conflict_details,
                    conflicting_docs=conflicting_docs[:5],
                    conflict_pairs=pairs,
                ).model_dump_json(),
            )
            # Register detected conflicts in ConflictStore for dashboard sync
            if pairs and ctx and ctx.conflict_store:
                try:
                    import time as _time
                    from backend.application.conflict.conflict_store import StoredConflict
                    for pair in pairs:
                        stored = StoredConflict(
                            file_a=min(pair.file_a, pair.file_b),
                            file_b=max(pair.file_a, pair.file_b),
                            similarity=pair.similarity,
                            detected_at=_time.time(),
                            meta_a={}, meta_b={},
                        )
                        ctx.conflict_store.replace_for_file(pair.file_a, [stored])
                except Exception as e:
                    logger.debug(f"Failed to register conflict in store: {e}")

        # 5b. Final polished answer — streamed to user via llm_generate skill
        yield self._thinking("answer_gen", "start", "최종 답변 생성 중", f"컨텍스트 {len(relevant_docs)}건 사용")

        username = ctx.username if ctx else ""
        base_prompt = await build_system_prompt(username, self.storage)
        final_system = base_prompt + f"\n\n---\n\n## Wiki 컨텍스트\n\n{context}"

        # Token-based history window — skip when topic shifted to prevent contamination
        messages = [{"role": "system", "content": final_system}]
        if not topic_shift:
            for msg in build_history_window(history):
                messages.append({"role": msg["role"], "content": msg["content"]})
        else:
            logger.info("Topic shift detected — skipping history injection for clean context")
        messages.append({"role": "user", "content": request.message})

        if ctx:
            gen_result = await ctx.run_skill(
                "llm_generate", messages=messages, stream=True, temperature=0.3,
            )
            if not gen_result.success:
                yield self._sse(
                    "error",
                    ErrorEvent(
                        error_code="LLM_UNAVAILABLE",
                        message=f"LLM 호출에 실패했습니다: {gen_result.error}",
                        retry_hint="잠시 후 다시 시도해주세요.",
                    ).model_dump_json(),
                )
                return

            total_tokens = 0
            async for chunk in gen_result.data["chunks"]:
                yield self._sse("content_delta", ContentDelta(delta=chunk).model_dump_json())
                total_tokens += 1

            yield self._thinking("answer_gen", "done", "최종 답변 생성 완료")
            yield self._sse(
                "done",
                DoneEvent(usage=TokenUsage(input_tokens=0, output_tokens=total_tokens)).model_dump_json(),
            )
        else:
            # Fallback: Pydantic AI streaming (when ctx not provided)
            try:
                from pydantic_ai import Agent
                from backend.application.agent.llm_factory import get_model

                system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
                user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
                agent = Agent(get_model(), output_type=str, system_prompt=system_msg, defer_model_check=True)

                total_tokens = 0
                async with agent.run_stream(user_msg) as stream:
                    async for delta in stream.stream_text(delta=True):
                        if delta:
                            yield self._sse("content_delta", ContentDelta(delta=delta).model_dump_json())
                            total_tokens += 1
                    usage = stream.usage()
                    token_usage = TokenUsage(
                        input_tokens=usage.input_tokens or 0,
                        output_tokens=usage.output_tokens or 0,
                    )

                yield self._thinking("answer_gen", "done", "최종 답변 생성 완료")
                yield self._sse("done", DoneEvent(usage=token_usage).model_dump_json())

            except Exception as e:
                logger.error(f"RAG LLM error: {e}")
                yield self._sse(
                    "error",
                    ErrorEvent(
                        error_code="LLM_UNAVAILABLE",
                        message=f"LLM 호출에 실패했습니다: {e}",
                        retry_hint="잠시 후 다시 시도해주세요.",
                    ).model_dump_json(),
                )

    @staticmethod
    def _build_clarification_options(metadatas: list[dict], distances: list[float]) -> list[str]:
        """Build clickable option labels from search results for clarification UI."""
        options: list[str] = []
        seen: set[str] = set()
        for meta, dist in zip(metadatas[:5], distances[:5]):
            fp = meta.get("file_path", "")
            if fp in seen:
                continue
            seen.add(fp)
            heading = meta.get("heading", fp.split("/")[-1].replace(".md", ""))
            domain = meta.get("domain", "")
            label = f"{heading} — {domain}" if domain else heading
            options.append(label)
        return options if len(options) >= 2 else []

    def _check_clarity_rule_based(
        self, query: str, metadatas: list[dict], distances: list[float],
    ) -> str | None:
        """Rule-based clarity check (no LLM). Returns clarifying message or None."""
        query_stripped = query.strip()

        if re.search(r'[A-Z]{2,}|[가-힣]{2,4}(님|씨)|[A-Z]+[-_]?\d+|\d{3,}', query_stripped):
            return None

        if not metadatas:
            return None

        options: list[str] = []
        seen_files: set[str] = set()
        for meta, dist in zip(metadatas[:5], distances[:5]):
            fp = meta.get("file_path", "")
            if fp in seen_files:
                continue
            seen_files.add(fp)
            heading = meta.get("heading", fp.split("/")[-1])
            domain = meta.get("domain", "")
            label = f"**{heading}**"
            if domain:
                label += f" — {domain}"
            options.append(label)

        if len(options) <= 1:
            return None

        numbered = "\n".join(f"{i + 1}. {opt}" for i, opt in enumerate(options[:5]))
        logger.info(f"Clarity check (rule-based): asking follow-up for '{query}'")
        return (
            f"Wiki에서 관련 문서를 찾았습니다.\n\n"
            f"{numbered}\n\n"
            f"어떤 내용에 대해 알고 싶으신가요?"
        )

    async def _handle_skill_qa(
        self, request: ChatRequest, ctx: AgentContext,
    ) -> AsyncGenerator[str, None]:
        """Skill-based Q&A with 6-layer prompt: preamble → role → workflow → instructions → checklist → output → regulation."""
        skill = ctx.user_skill
        sc: SkillContext = ctx.skill_context if isinstance(ctx.skill_context, SkillContext) else SkillContext(instructions=str(ctx.skill_context or ""))

        # 1. Thinking events — skill match + doc loading with missing doc warnings
        yield self._thinking("skill_match", "done", f"{skill.icon} {skill.title}", "스킬 적용")

        total_docs = sc.preamble_docs_found + len(sc.preamble_docs_missing)
        if total_docs > 0:
            yield self._thinking("doc_load", "start", "참조 문서 로딩 중", f"{total_docs}건 탐색")
            for i, (title, _) in enumerate(sc.referenced_doc_contents, 1):
                yield self._thinking("doc_ref", "done", f"📄 {title}", f"{i}/{total_docs}")
            for missing in sc.preamble_docs_missing:
                doc_name = missing.replace(".md", "")
                yield self._thinking("doc_ref", "done", f"⚠️ {doc_name} (없음)", "누락")
            yield self._thinking("doc_load", "done", "참조 문서 로딩 완료",
                                  f"{sc.preamble_docs_found}건 적용" + (f", {len(sc.preamble_docs_missing)}건 누락" if sc.preamble_docs_missing else ""))

        # 2. Build 6-layer system prompt
        prompt_parts: list[str] = []

        # Layer 1: Preamble (runtime context — always present)
        preamble_lines = []
        if sc.preamble_date:
            preamble_lines.append(f"현재 날짜: {sc.preamble_date}")
        if sc.preamble_user:
            preamble_lines.append(f"질문자: {sc.preamble_user}")
        preamble_lines.append(f"참조 문서: {sc.preamble_docs_found}건 로드됨")
        if sc.preamble_docs_missing:
            preamble_lines.append(f"누락 문서: {', '.join(sc.preamble_docs_missing)}")
        prompt_parts.append("## 컨텍스트\n" + "\n".join(preamble_lines))

        # Layer 2: Role (skill-specific or default)
        if sc.role:
            prompt_parts.append(f"## 역할\n{sc.role}")
        else:
            prompt_parts.append("## 역할\n당신은 사내 Wiki AI 파트너입니다.")

        # Skill identity
        prompt_parts.append(f"## 스킬: {skill.title}\n{skill.description}")

        # Layer 3: Workflow (conditional)
        if sc.workflow:
            prompt_parts.append(f"## 워크플로우\n다음 단계를 순서대로 따르세요:\n\n{sc.workflow}")

        # Instructions (always present)
        prompt_parts.append(f"## 지시사항\n{sc.instructions}")

        # Layer 4: Checklist (conditional)
        if sc.checklist:
            prompt_parts.append(f"## 체크리스트\n{sc.checklist}")

        # Layer 5: Output format (conditional)
        if sc.output_format:
            prompt_parts.append(f"## 출력 형식\n{sc.output_format}")

        # Layer 6: Self-regulation (conditional)
        if sc.self_regulation:
            prompt_parts.append(f"## 제한사항\n{sc.self_regulation}")

        # Referenced doc contents
        for title, content in sc.referenced_doc_contents:
            prompt_parts.append(f"---\n## 참조: {title}\n\n{content}")

        # Per-user persona (appended before closing instruction)
        persona = await get_user_persona(ctx.username, self.storage) if ctx else ""
        if persona:
            prompt_parts.append(f"## 사용자 개인 설정\n{persona}")

        # Closing instruction
        prompt_parts.append("위 지시사항과 참조 문서를 바탕으로 사용자의 질문에 답변하세요.\n출처를 반드시 명시하세요.")

        system_prompt = "\n\n".join(prompt_parts)

        # 3. Build messages and call LLM
        # Use augmented query for follow-up context (e.g. "그거 더 설명해줘" → includes what "그거" refers to)
        user_message = (ctx.augmented_query if ctx.augmented_query else None) or request.message
        messages = [{"role": "system", "content": system_prompt}]
        for msg in build_history_window(ctx.history):
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        yield self._thinking("answer_gen", "start", "답변 생성 중")

        if ctx:
            gen = await ctx.run_skill("llm_generate", messages=messages, stream=True)
            if gen.success and gen.data and "chunks" in gen.data:
                async for chunk in gen.data["chunks"]:
                    yield f"event: content_delta\ndata: {ContentDelta(delta=chunk).model_dump_json()}\n\n"
            elif not gen.success:
                yield f"event: error\ndata: {ErrorEvent(error_code='SKILL_LLM_ERROR', message=gen.error or 'LLM generation failed').model_dump_json()}\n\n"
                return
        else:
            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model

            system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            agent = Agent(get_model(), output_type=str, system_prompt=system_msg, defer_model_check=True)
            async with agent.run_stream(user_msg) as stream:
                async for delta in stream.stream_text(delta=True):
                    if delta:
                        yield f"event: content_delta\ndata: {ContentDelta(delta=delta).model_dump_json()}\n\n"

        # 4. Show referenced docs as sources
        sources = [
            SourceRef(doc=doc, relevance=1.0)
            for doc in skill.referenced_docs
        ]
        if sources:
            yield f"event: sources\ndata: {SourcesEvent(sources=sources).model_dump_json()}\n\n"

        yield self._thinking("answer_gen", "done", "답변 생성 완료")
        yield f"event: done\ndata: {DoneEvent().model_dump_json()}\n\n"

    async def _handle_edit(
        self, request: ChatRequest, history: list[dict],
        *, ctx: AgentContext | None = None,
    ) -> AsyncGenerator[str, None]:
        """Handle wiki edit intent: delegate to wiki_edit skill."""
        # Prefer augmented query for follow-up edits (e.g. "그 문서 수정해줘" → includes context)
        query = (ctx.augmented_query if ctx and ctx.augmented_query else None) or request.message

        if ctx:
            # Use wiki_edit skill
            yield self._thinking("vector_search", "start", "수정 대상 문서 검색 중")

            target_path = request.attached_files[0] if request.attached_files else ""
            if target_path:
                yield self._thinking("vector_search", "done", "첨부 문서 사용", target_path)
            else:
                yield self._thinking("vector_search", "done", "문서 검색 완료")

            yield self._thinking("answer_gen", "start", "문서 수정 중")

            edit_result = await ctx.run_skill(
                "wiki_edit",
                instruction=query,
                target_path=target_path,
                history=history,
            )

            if not edit_result.success:
                yield self._thinking("answer_gen", "done", "수정 실패")
                yield self._sse("content_delta", ContentDelta(
                    delta=edit_result.error or "문서 수정에 실패했습니다."
                ).model_dump_json())
                yield self._sse("done", DoneEvent().model_dump_json())
                return

            data = edit_result.data
            yield self._thinking("answer_gen", "done", "문서 수정 완료")

            yield self._sse("content_delta", ContentDelta(
                delta=f"**`{data['path']}`** 문서 수정안을 생성했습니다. 워크스페이스에서 확인하세요."
            ).model_dump_json())

            yield self._sse(
                "approval_request",
                data["approval_event"].model_dump_json(),
            )
            yield self._sse("done", DoneEvent().model_dump_json())
        else:
            # Fallback: inline edit (backward compatibility)
            async for event in self._handle_edit_inline(request, history):
                yield event

    async def _handle_edit_inline(
        self, request: ChatRequest, history: list[dict],
    ) -> AsyncGenerator[str, None]:
        """Legacy inline edit handler (no ctx)."""
        query = request.message
        best_file_path = ""

        try:
            if request.attached_files:
                best_file_path = request.attached_files[0]
                yield self._thinking("vector_search", "start", "첨부 문서 확인 중")
                yield self._thinking("vector_search", "done", "첨부 문서 사용", best_file_path)
            else:
                yield self._thinking("vector_search", "start", "수정 대상 문서 검색 중")
                results = self.chroma.query(query, n_results=8)
                documents = results.get("documents", [[]])[0]
                metadatas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]

                yield self._thinking(
                    "vector_search", "done", "문서 검색 완료",
                    f"{len(documents)}건 (최고 관련도 {max(0, round((1 - min(distances)) * 100)) if distances else 0}%)",
                )

                if not documents:
                    yield self._sse("content_delta", ContentDelta(
                        delta="수정할 대상 문서를 찾지 못했습니다. 📎 버튼으로 수정할 파일을 첨부하거나, 더 구체적으로 말씀해주세요."
                    ).model_dump_json())
                    yield self._sse("done", DoneEvent().model_dump_json())
                    return

                seen_files: dict[str, str] = {}
                for meta, doc in zip(metadatas, documents):
                    fp = meta.get("file_path", "")
                    if fp and fp not in seen_files:
                        seen_files[fp] = doc[:200]

                file_list = "\n".join(
                    f"- {fp}: {preview[:100]}..." for fp, preview in seen_files.items()
                )

                from pydantic_ai import Agent
                from backend.application.agent.llm_factory import get_model

                pick_agent = Agent(
                    get_model(), output_type=str,
                    system_prompt=(
                        "사용자가 Wiki 문서를 수정하려고 합니다. "
                        "아래 후보 문서 목록에서 사용자의 수정 요청에 가장 적합한 문서를 선택하세요.\n\n"
                        "응답은 파일명만 한 줄로 (예: 직원정보-마케팅DX그룹.md)"
                    ),
                    defer_model_check=True,
                )
                pick_result = await pick_agent.run(f"수정 요청: {query}\n\n후보 문서:\n{file_list}")
                picked = pick_result.output.strip().replace("`", "").strip()
                for fp in seen_files:
                    if fp in picked or picked in fp:
                        best_file_path = fp
                        break
                if not best_file_path:
                    best_file_path = next(iter(seen_files), "")

            if not best_file_path or not self.storage:
                yield self._sse("content_delta", ContentDelta(
                    delta="문서 내용을 읽을 수 없습니다. 다시 시도해주세요."
                ).model_dump_json())
                yield self._sse("done", DoneEvent().model_dump_json())
                return

            wiki_file = await self.storage.read(best_file_path)
            if not wiki_file:
                yield self._sse("content_delta", ContentDelta(
                    delta=f"**{best_file_path}** 문서를 찾을 수 없습니다."
                ).model_dump_json())
                yield self._sse("done", DoneEvent().model_dump_json())
                return

            original_content = wiki_file.raw_content or wiki_file.content

            yield self._thinking("answer_gen", "start", "문서 수정 중")

            history_text = ""
            if history:
                recent = build_history_window(history, max_tokens=1500)
                history_text = "\n".join(
                    f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content'][:200]}"
                    for h in recent
                )
                history_text = f"\n\n## 대화 히스토리\n{history_text}"

            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model
            from backend.application.agent.models import WikiEditResult

            edit_agent = Agent(
                get_model(), output_type=WikiEditResult,
                system_prompt=(
                    "당신은 사내 Wiki 문서 수정 전문가입니다. "
                    "사용자의 요청에 따라 기존 문서를 수정하세요.\n\n"
                    "## 규칙\n"
                    "- YAML frontmatter(--- 사이의 내용)는 그대로 유지하세요.\n"
                    "- 사용자가 요청한 부분만 수정하고, 나머지는 최대한 보존하세요.\n"
                    "- 수정된 전체 문서를 반환하세요 (frontmatter 포함).\n"
                ),
                retries=2,
                defer_model_check=True,
            )
            edit_result = await edit_agent.run(
                f"## 수정 대상 문서: {best_file_path}\n\n"
                f"## 현재 문서 내용\n```\n{original_content}\n```\n"
                f"{history_text}\n\n"
                f"## 수정 요청\n{query}"
            )
            new_content = edit_result.output.content
            summary = edit_result.output.summary

            yield self._thinking("answer_gen", "done", "문서 수정 완료")

            if not new_content:
                yield self._sse("content_delta", ContentDelta(
                    delta="문서 수정 내용을 생성하지 못했습니다. 더 구체적으로 요청해주세요."
                ).model_dump_json())
                yield self._sse("done", DoneEvent().model_dump_json())
                return

            preview_lines = new_content.split("\n")[:25]
            diff_preview = "\n".join(preview_lines)
            if len(new_content.split("\n")) > 25:
                diff_preview += "\n... (truncated)"

            yield self._sse("content_delta", ContentDelta(
                delta=(
                    f"**`{best_file_path}`** 문서를 수정하겠습니다.\n\n"
                    f"**수정 내용**: {summary}\n\n"
                )
            ).model_dump_json())

            from backend.core.schemas import WikiEditAction
            action = WikiEditAction(path=best_file_path, content=new_content, diff_preview=diff_preview)
            action_id = session_store.add_pending_action(request.session_id, action)

            yield self._sse(
                "approval_request",
                ApprovalRequestEvent(
                    action_id=action_id, action_type="wiki_edit",
                    path=best_file_path, diff_preview=diff_preview,
                ).model_dump_json(),
            )
            yield self._sse("done", DoneEvent().model_dump_json())

        except json.JSONDecodeError:
            yield self._sse("content_delta", ContentDelta(
                delta="문서 수정 중 형식 오류가 발생했습니다. 다시 시도해주세요."
            ).model_dump_json())
            yield self._sse("done", DoneEvent().model_dump_json())

        except Exception as e:
            logger.error(f"RAG edit error: {e}")
            yield self._sse(
                "error",
                ErrorEvent(
                    error_code="EDIT_FAILED",
                    message=f"문서 수정에 실패했습니다: {e}",
                    retry_hint="잠시 후 다시 시도해주세요.",
                ).model_dump_json(),
            )

    async def _handle_write(
        self, request: ChatRequest, *, ctx: AgentContext | None = None,
    ) -> AsyncGenerator[str, None]:
        """Handle wiki write intent: delegate to wiki_write skill."""
        query = request.message

        if ctx:
            yield self._thinking("answer_gen", "start", "문서 작성 중")

            write_result = await ctx.run_skill("wiki_write", instruction=query)

            if not write_result.success:
                yield self._thinking("answer_gen", "done", "문서 작성 실패")
                yield self._sse("content_delta", ContentDelta(
                    delta=write_result.error or "문서 생성에 실패했습니다."
                ).model_dump_json())
                yield self._sse("done", DoneEvent().model_dump_json())
                return

            data = write_result.data
            yield self._thinking("answer_gen", "done", "문서 작성 완료")
            yield self._sse("content_delta", ContentDelta(
                delta=f"**`{data['path']}`** 문서를 생성했습니다. 워크스페이스에서 확인하세요."
            ).model_dump_json())

            yield self._sse(
                "approval_request",
                data["approval_event"].model_dump_json(),
            )
            yield self._sse("done", DoneEvent().model_dump_json())
        else:
            # Fallback: inline write (backward compatibility)
            async for event in self._handle_write_inline(request):
                yield event

    async def _handle_write_inline(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Legacy inline write handler (no ctx)."""
        query = request.message

        try:
            yield self._sse("content_delta", ContentDelta(
                delta="Wiki 문서 작성을 준비하고 있습니다...\n\n"
            ).model_dump_json())

            from pydantic_ai import Agent
            from backend.application.agent.llm_factory import get_model
            from backend.application.agent.models import WikiWriteResult

            write_agent = Agent(
                get_model(), output_type=WikiWriteResult,
                system_prompt=(
                    "당신은 사내 Wiki 기술 문서 작성 전문가입니다. "
                    "사용자의 요청에 맞는 Wiki 문서를 Markdown 형식으로 작성하세요.\n\n"
                    "path는 적절한 파일명(한글 가능, .md 확장자), "
                    "content는 완전한 Markdown 문서입니다."
                ),
                retries=2,
                defer_model_check=True,
            )
            write_result = await write_agent.run(query)
            path = write_result.output.path
            content = write_result.output.content

            if not content:
                yield self._sse("content_delta", ContentDelta(
                    delta="문서 내용을 생성하지 못했습니다. 더 구체적으로 요청해주세요."
                ).model_dump_json())
                yield self._sse("done", DoneEvent().model_dump_json())
                return

            preview_lines = content.split("\n")[:20]
            diff_preview = "\n".join(preview_lines)
            if len(content.split("\n")) > 20:
                diff_preview += "\n... (truncated)"

            yield self._sse("content_delta", ContentDelta(
                delta=f"다음 내용으로 **`{path}`** 문서를 생성하겠습니다:\n\n```markdown\n{diff_preview}\n```\n\n"
            ).model_dump_json())

            from backend.core.schemas import WikiWriteAction
            action = WikiWriteAction(path=path, content=content, diff_preview=diff_preview)
            action_id = session_store.add_pending_action(request.session_id, action)

            yield self._sse(
                "approval_request",
                ApprovalRequestEvent(
                    action_id=action_id, action_type="wiki_write",
                    path=path, diff_preview=diff_preview,
                ).model_dump_json(),
            )
            yield self._sse("done", DoneEvent().model_dump_json())

        except json.JSONDecodeError:
            yield self._sse("content_delta", ContentDelta(
                delta="문서 생성 중 형식 오류가 발생했습니다. 다시 시도해주세요."
            ).model_dump_json())
            yield self._sse("done", DoneEvent().model_dump_json())

        except Exception as e:
            logger.error(f"RAG write error: {e}")
            yield self._sse(
                "error",
                ErrorEvent(
                    error_code="WRITE_FAILED",
                    message=f"문서 생성에 실패했습니다: {e}",
                    retry_hint="잠시 후 다시 시도해주세요.",
                ).model_dump_json(),
            )

    # ── Static helpers ────────────────────────────────────────────────────

    @staticmethod
    def _thinking(step: str, status: str, label: str, detail: str = "") -> str:
        """Emit a thinking_step SSE event."""
        evt = ThinkingStepEvent(step=step, status=status, label=label, detail=detail)
        return f"event: thinking_step\ndata: {evt.model_dump_json()}\n\n"

    @staticmethod
    def _build_conflict_pairs(
        conflicting_docs: list[str],
        relevant_metas: list[dict],
        relevant_dists: list[float],
        conflict_details: str,
    ) -> list[ConflictPair]:
        """Build explicit ConflictPair list from detected conflict info."""
        # Pre-compute per-file average relevance from retrieval distances
        file_sims: dict[str, list[float]] = {}
        for meta, dist in zip(relevant_metas, relevant_dists):
            fp = meta.get("file_path", "")
            if fp:
                file_sims.setdefault(fp, []).append(max(0.0, 1.0 - dist))

        pairs: list[ConflictPair] = []
        for i, a in enumerate(conflicting_docs):
            for b in conflicting_docs[i + 1:]:
                # Average the two files' retrieval relevance as pair similarity
                avg_a = sum(file_sims.get(a, [0.5])) / max(len(file_sims.get(a, [0.5])), 1)
                avg_b = sum(file_sims.get(b, [0.5])) / max(len(file_sims.get(b, [0.5])), 1)
                sim = round((avg_a + avg_b) / 2, 3)

                # Extract pair-relevant summary from conflict_details
                summary = _extract_pair_summary(a, b, conflict_details)

                pairs.append(ConflictPair(
                    file_a=a,
                    file_b=b,
                    similarity=sim,
                    summary=summary,
                ))
        return pairs

    @staticmethod
    def _build_context_with_metadata(
        documents: list[str], metadatas: list[dict], distances: list[float],
    ) -> str:
        """Build LLM context with source metadata headers for each document chunk."""
        chunks: list[str] = []
        seen_files: set[str] = set()

        for doc, meta, dist in zip(documents, metadatas, distances):
            file_path = meta.get("file_path", "unknown")
            author = meta.get("updated_by") or meta.get("created_by") or "unknown"
            updated = meta.get("updated") or meta.get("created") or "unknown"
            domain = meta.get("domain", "")
            relevance = max(0, 1 - dist)

            is_duplicate_source = file_path in seen_files
            seen_files.add(file_path)

            header_lines = [
                f"[출처: {file_path}]",
                f"[작성자: {author} | 최종수정: {updated} | 관련도: {relevance:.0%}]",
            ]
            if domain:
                header_lines[1] = f"[작성자: {author} | 최종수정: {updated} | 도메인: {domain} | 관련도: {relevance:.0%}]"
            if is_duplicate_source:
                header_lines.append("[참고: 같은 파일의 다른 섹션]")

            status = meta.get("status", "")
            superseded_by = meta.get("superseded_by", "")
            if superseded_by:
                header_lines.append(f"[⚠ 폐기됨 — 새 버전: {superseded_by}]")
            elif status == "deprecated":
                header_lines.append("[⚠ deprecated 상태]")

            header = "\n".join(header_lines)
            chunks.append(f"{header}\n{doc}")

        return "\n\n---\n\n".join(chunks)

    @staticmethod
    def _build_sources(
        metadatas: list[dict], distances: list[float], threshold: float = 0.4,
        confidence_service: object | None = None,
    ) -> list[SourceRef]:
        """Build deduplicated, relevance-filtered source list with metadata."""
        sources = []
        seen = set()
        for meta, dist in zip(metadatas, distances):
            relevance = max(0, 1 - dist)
            file_path = meta.get("file_path", "")
            if relevance >= threshold and file_path not in seen:
                seen.add(file_path)
                # Confidence scoring
                conf_score = -1
                conf_tier = ""
                if confidence_service:
                    try:
                        cr = confidence_service.get_confidence(file_path)
                        conf_score = cr.score
                        conf_tier = cr.tier
                    except Exception:
                        pass
                sources.append(SourceRef(
                    doc=file_path,
                    relevance=round(relevance, 3),
                    updated=meta.get("updated", ""),
                    updated_by=meta.get("updated_by", "") or meta.get("created_by", ""),
                    status=meta.get("status", ""),
                    superseded_by=meta.get("superseded_by", ""),
                    confidence_score=conf_score,
                    confidence_tier=conf_tier,
                ))
        # Apply confidence-based mild boost: re-sort by adjusted relevance
        if confidence_service and sources:
            for s in sources:
                if s.confidence_score >= 0:
                    # Mild boost: confidence 100 → 100% weight, confidence 0 → floor% weight
                    _floor = _SCORING.rag_boost.floor
                    s.relevance = round(s.relevance * (_floor + (1 - _floor) * s.confidence_score / 100), 3)
            sources.sort(key=lambda s: -s.relevance)
        return sources

    def _record_citations(self, sources: list) -> None:
        """Record citation counts for documents used in AI answers."""
        if not self._citation_tracker:
            return
        try:
            paths = list({s.doc for s in sources if s.doc})
            if paths:
                self._citation_tracker.record_citations(paths)
        except Exception:
            pass  # citation tracking is best-effort

    @staticmethod
    def _build_status_filter() -> dict:
        return {"status": {"$ne": "deprecated"}}

    @staticmethod
    def _merge_where_filters(filter_a: dict | None, filter_b: dict | None) -> dict | None:
        if not filter_a and not filter_b:
            return None
        if not filter_a:
            return filter_b
        if not filter_b:
            return filter_a
        return {"$and": [filter_a, filter_b]}

    @staticmethod
    def _build_tag_filter(tags: list[str], extra: dict | None = None) -> dict | None:
        """Build a ChromaDB where clause that matches docs containing any of the given tags.

        ChromaDB metadata is stored as comma-joined strings (see chroma.py),
        so we use $in over individual tag matches via $or with $contains-style equality.
        Falls back to None if tags is empty.
        """
        if not tags:
            return None
        # Tags in ChromaDB metadata are stored as comma-separated string per doc.
        # Use $or with multiple tag-equality not feasible directly; instead match
        # by tag substring via the dedicated `tag_*` boolean keys if present.
        # As a portable fallback we filter post-query (see _tag_boost_rerank).
        # Here we return a marker dict that the caller can choose to ignore.
        clauses = [{"tags": {"$in": [t]}} for t in tags]
        tag_clause = clauses[0] if len(clauses) == 1 else {"$or": clauses}
        if extra:
            return {"$and": [tag_clause, extra]}
        return tag_clause

    @staticmethod
    def _tag_boost_rerank(
        documents: list,
        metadatas: list,
        distances: list,
        query_tags: list[str],
        weight: float = 0.05,
    ) -> tuple[list, list, list]:
        """Reorder search results by boosting docs whose tags intersect query_tags.

        ChromaDB returns cosine distance (smaller=better). We subtract
        `weight * |intersection|` from each distance and resort.
        """
        if not query_tags or not documents:
            return documents, metadatas, distances
        qset = set(query_tags)
        scored = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            raw_tags = meta.get("tags", "") if meta else ""
            doc_tags = set()
            if isinstance(raw_tags, str) and raw_tags:
                doc_tags = {t.strip() for t in raw_tags.split(",") if t.strip()}
            elif isinstance(raw_tags, list):
                doc_tags = set(raw_tags)
            overlap = len(qset & doc_tags)
            adjusted = dist - (weight * overlap)
            scored.append((adjusted, doc, meta, dist))
        scored.sort(key=lambda x: x[0])
        new_docs = [s[1] for s in scored]
        new_metas = [s[2] for s in scored]
        new_dists = [s[3] for s in scored]
        return new_docs, new_metas, new_dists

    @staticmethod
    def _detect_path_ambiguity(
        metadatas: list[dict],
        distances: list[float],
        min_paths: int = 3,
        dominance_ratio: float = 0.70,
    ) -> tuple[bool, list[tuple[str, int, float]]]:
        """Detect if search results span ambiguously many path clusters.

        Returns (is_ambiguous, path_stats) where path_stats is
        [(path_depth_1, count, avg_relevance), ...] sorted by count desc.
        """
        from collections import Counter

        path_relevances: dict[str, list[float]] = {}
        for meta, dist in zip(metadatas, distances):
            p = (meta or {}).get("path_depth_1", "")
            if not p:
                continue
            path_relevances.setdefault(p, []).append(max(0, 1 - dist))

        if len(path_relevances) < min_paths:
            return False, []

        total = sum(len(v) for v in path_relevances.values())
        stats = sorted(
            [
                (path, len(rels), sum(rels) / len(rels))
                for path, rels in path_relevances.items()
            ],
            key=lambda x: x[1],
            reverse=True,
        )

        # If the most frequent path dominates, not ambiguous
        if total > 0 and stats[0][1] / total >= dominance_ratio:
            return False, stats

        return True, stats

    @staticmethod
    def _path_boost_rerank(
        documents: list,
        metadatas: list,
        distances: list,
        path_preferences: list[str],
        weight: float = 0.08,
    ) -> tuple[list, list, list]:
        """Boost docs whose path_depth_1 matches session path preferences.

        More recent preferences get higher weight (recency decay).
        """
        if not path_preferences or not documents:
            return documents, metadatas, distances

        # Build preference score: most recent = 1.0, decaying by 0.5
        pref_scores: dict[str, float] = {}
        for i, pref in enumerate(reversed(path_preferences)):
            if pref not in pref_scores:
                pref_scores[pref] = 0.5 ** i  # 1.0, 0.5, 0.25, ...

        scored = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            path = (meta or {}).get("path_depth_1", "")
            boost = pref_scores.get(path, 0.0)
            adjusted = dist - (weight * boost)
            scored.append((adjusted, doc, meta, dist))

        scored.sort(key=lambda x: x[0])
        return (
            [s[1] for s in scored],
            [s[2] for s in scored],
            [s[3] for s in scored],
        )

    @staticmethod
    def _resolve_superseded_chain(
        file_path: str, supersede_map: dict[str, str], max_depth: int = 5
    ) -> str | None:
        current = file_path
        visited: set[str] = {current}
        for _ in range(max_depth):
            next_path = supersede_map.get(current)
            if not next_path or next_path == current:
                break
            if next_path in visited:
                logger.warning(f"Supersede cycle detected: {file_path} -> ... -> {next_path}")
                break
            visited.add(next_path)
            current = next_path
        return current if current != file_path else None

    async def _replace_deprecated_with_latest(
        self, documents: list[str], metadatas: list[dict],
        distances: list[float], supersede_map: dict[str, str],
    ) -> int:
        """Replace deprecated documents in search results with their latest versions."""
        replaced = 0
        seen_files = {m.get("file_path") for m in metadatas}

        for i, meta in enumerate(metadatas):
            status = meta.get("status", "")
            file_path = meta.get("file_path", "")
            if status != "deprecated" or file_path not in supersede_map:
                continue

            latest = self._resolve_superseded_chain(file_path, supersede_map)
            if not latest or latest in seen_files:
                continue

            if not self.storage:
                continue
            latest_file = await self.storage.read(latest)
            if not latest_file:
                continue

            documents[i] = latest_file.content if hasattr(latest_file, 'content') else str(latest_file)
            metadatas[i] = {
                "file_path": getattr(latest_file, 'path', latest),
                "domain": getattr(getattr(latest_file, 'metadata', None), 'domain', ''),
                "process": getattr(getattr(latest_file, 'metadata', None), 'process', ''),
                "status": getattr(getattr(latest_file, 'metadata', None), 'status', ''),
                "updated": getattr(getattr(latest_file, 'metadata', None), 'updated', ''),
                "updated_by": getattr(getattr(latest_file, 'metadata', None), 'updated_by', ''),
                "created_by": getattr(getattr(latest_file, 'metadata', None), 'created_by', ''),
            }
            seen_files.add(latest)
            replaced += 1

        return replaced

    @staticmethod
    def _sse(event: str, data: str) -> str:
        return f"event: {event}\ndata: {data}\n\n"
