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
from typing import AsyncGenerator

from backend.core.schemas import (
    ApprovalRequestEvent,
    ChatRequest,
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

# ── Cognitive Pipeline Prompts ────────────────────────────────────────

COGNITIVE_REFLECT_PROMPT = (
    "You are an internal reasoning engine for a corporate wiki AI assistant. "
    "You NEVER talk to the user. Your output is consumed only by the system.\n\n"
    "Given the user's query, conversation history, and retrieved wiki context, "
    "perform a three-step cognitive analysis:\n\n"
    "## Step 1: internal_thought (English)\n"
    "Analyze:\n"
    "- What is the user REALLY asking? (surface intent vs deeper need)\n"
    "- What is their likely emotional state? (frustrated? exploring? urgent?)\n"
    "- What domain context matters? (SCM, HR, IT, production?)\n"
    "- Are there gaps between the wiki context and what they need?\n\n"
    "## Step 2: draft_response (Korean)\n"
    "Write a first-draft answer in Korean based on the wiki context.\n"
    "Use markdown formatting: paragraphs, bullet lists, bold for key terms.\n"
    "Include source citations. Be thorough.\n\n"
    "## Step 3: self_critique (English)\n"
    "Critique your draft against these quality gates:\n"
    "- EMPATHY: Does it acknowledge the user's situation before diving into info?\n"
    "- MINTO PYRAMID: Is the conclusion/answer FIRST, then supporting details?\n"
    "- ACTIONABLE: Does it suggest concrete human next-steps? "
    "(e.g., '이 문서를 바탕으로 생산팀에 확인 요청을 해보시겠어요?') "
    "Do NOT suggest tools/features that don't exist.\n"
    "- CONCISE: Can anything be cut without losing critical info?\n"
    "- FORMATTING: Does it use line breaks, bullet lists, bold? Never a wall of text.\n"
    "- CITATIONS: Are source documents properly referenced?\n"
    "- CONFLICT_CHECK: Do any documents in the context contain **different values, numbers, "
    "rules, or guidelines** on the same topic? This includes:\n"
    "  * Different numbers for the same metric (e.g., budget 30,000 vs 50,000)\n"
    "  * Different rules or procedures for the same process\n"
    "  * Multiple versions of a policy from different teams/dates without clear precedence\n"
    "  Compare [출처] headers, dates, and content. If ANY discrepancy exists between documents, "
    "set 'has_conflict' to true — even if the documents come from different teams or versions. "
    "Note which documents conflict, what the discrepancy is, and recommend referencing "
    "the most recently updated document.\n"
    "List specific improvements the final answer must make.\n\n"
    "Respond in this EXACT JSON format (no markdown fences, no extra text):\n"
    "{\n"
    '  "internal_thought": "...",\n'
    '  "draft_response": "...",\n'
    '  "self_critique": "...",\n'
    '  "has_conflict": false,\n'
    '  "conflict_details": "충돌 설명을 한국어로 작성 (has_conflict가 true일 때). 어떤 문서가 어떻게 다른지 구체적으로 기술. false면 빈 문자열"\n'
    "}"
)

FINAL_ANSWER_SYSTEM_PROMPT = (
    "당신은 On-Tong, 사내 Wiki 지식 관리 시스템의 AI 파트너입니다.\n\n"
    "## 페르소나\n"
    "- **공감하는 IT 파트너**: 사용자가 겪고 있는 상황을 먼저 인정하고, "
    "전문적이면서도 따뜻한 톤으로 답변하세요.\n"
    "- **결론 우선 (Minto Pyramid)**: 핵심 답변을 첫 문장에 제시하고, "
    "뒷받침 근거와 세부사항은 그 아래에 구조화하세요.\n"
    "- **실행 가능한 다음 단계**: 답변 끝에 사용자가 즉시 취할 수 있는 "
    "구체적 행동을 제안하세요. 존재하지 않는 시스템 기능을 언급하지 마세요.\n"
    "  예시: '이 내용을 바탕으로 XX팀에 확인 요청을 해보시겠어요?'\n"
    "- **출처 명시**: 어떤 Wiki 문서에서 정보를 가져왔는지 반드시 언급하세요.\n"
    "- **간결함**: 불필요한 서론이나 반복 없이, 핵심만 전달하세요.\n\n"
    "## 포맷팅 규칙\n"
    "- 답변은 반드시 **마크다운 형식**으로 작성하세요.\n"
    "- 핵심 답변 후 빈 줄을 넣고, 세부 내용은 **줄바꿈과 단락 구분**을 충분히 사용하세요.\n"
    "- 여러 항목이 있으면 **번호 목록(1. 2. 3.)** 또는 **불릿 목록(- )** 을 사용하세요.\n"
    "- 중요한 키워드나 이름은 **볼드**로 강조하세요.\n"
    "- 절대로 모든 내용을 한 줄에 이어 쓰지 마세요.\n\n"
    "## 문서 충돌 감지 규칙\n"
    "- 컨텍스트의 여러 문서가 **같은 주제에 대해 다른 숫자, 금액, 규칙, 기준, 절차**를 담고 있으면 반드시 알려주세요.\n"
    "- 다른 팀/부서에서 작성했더라도, 같은 항목(예: 일비, 숙박비, 안전재고 등)에 다른 값이 있으면 충돌입니다.\n"
    "- 충돌 감지 시 반드시 답변 **맨 앞에** 다음 형식으로 경고하세요:\n"
    "  ⚠️ **문서 간 내용 차이 감지**\n"
    "  - `문서A` (수정일: YYYY-MM-DD)에서는 'X'라고 설명\n"
    "  - `문서B` (수정일: YYYY-MM-DD)에서는 'Y'라고 설명\n"
    "  → 최종수정일이 더 최근인 문서를 우선 참고하시되, 담당자에게 확인을 권장합니다.\n"
    "- 충돌이 없으면 경고 없이 정상 답변하세요.\n"
    "- 각 문서의 [출처], [작성자], [최종수정] 헤더를 활용하여 비교하세요.\n\n"
    "## 절대 규칙\n"
    "- 컨텍스트에 없는 내용을 추측하거나 지어내지 마세요.\n"
    "- 구조화된 데이터(키:값)도 주의 깊게 읽고 관련 정보를 추출하세요.\n"
    "- 인사 정보가 있으면 이름과 소속을 명시하세요.\n"
)

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

        if action == "write":
            async for event in self._handle_write(request, ctx=ctx):
                yield event
            return

        # Normal Q&A flow (with clarification check)
        async for event in self._handle_qa(
            request, metadata_filter, history, attached_context,
            augmented_query, ctx=ctx, user_roles=kwargs.get("user_roles", ["admin"]),
        ):
            yield event

    async def _augment_query(self, query: str, history: list[dict]) -> str:
        """Augment follow-up queries with context from conversation history.

        Called from api/agent.py for parallel pre-computation (before ctx exists).
        Uses Pydantic AI Agent for LLM call.
        """
        if not history or len(history) < 2:
            return query

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

            agent = Agent(
                get_model(),
                output_type=str,
                system_prompt=(
                    "You are a search query rewriter. Given a follow-up question and "
                    "conversation context, rewrite the question as a standalone search query "
                    "that includes all necessary context for document retrieval.\n\n"
                    "Rules:\n"
                    "- Output ONLY the rewritten query, nothing else\n"
                    "- Keep it concise (under 50 words)\n"
                    "- Preserve the original language (Korean)\n"
                    "- Include key entities/topics from context that the follow-up refers to\n\n"
                    "Example:\n"
                    "Context: user asked about '후판 공정계획'\n"
                    "Follow-up: '담당자 누구 있는지 찾아줘'\n"
                    "Rewritten: '후판 공정계획 담당자 누구'"
                ),
                defer_model_check=True,
            )
            result = await agent.run(
                f"Conversation context:\n{chr(10).join(recent_context)}\n\n"
                f"Follow-up question: {query}"
            )
            augmented = result.output.strip()
            if augmented:
                logger.info(f"Query augmented: '{query}' → '{augmented}'")
                return augmented
        except Exception as e:
            logger.warning(f"Query augmentation failed: {e}, using original query")

        return query

    async def _handle_qa(
        self, request: ChatRequest, metadata_filter: dict | None = None,
        history: list[dict] | None = None, attached_context: str = "",
        augmented_query: str | None = None, *,
        ctx: AgentContext | None = None, user_roles: list = None,
    ) -> AsyncGenerator[str, None]:
        """Standard RAG Q&A: clarity check → search (skill) → cognitive pipeline → LLM answer (skill)."""
        query = request.message
        history = history or []
        user_roles = user_roles or (ctx.user_roles if ctx else ["admin"])

        # 0. Query augmentation (pre-computed in parallel at API layer, or fallback here)
        is_followup = len(history) >= 2
        if augmented_query and augmented_query != query:
            search_query = augmented_query
            yield self._thinking("query_augment", "done", "쿼리 보강 완료 (병렬)", search_query)
        elif is_followup:
            yield self._thinking("query_augment", "start", "검색 쿼리 보강 중")
            search_query = await self._augment_query(query, history)
            if search_query != query:
                yield self._thinking("query_augment", "done", "쿼리 보강 완료", search_query)
            else:
                yield self._thinking("query_augment", "done", "쿼리 보강 완료")
        else:
            search_query = query

        # 1. Hybrid search via wiki_search skill
        yield self._thinking("vector_search", "start", "관련 문서 검색 중")

        if ctx:
            search_result = await ctx.run_skill(
                "wiki_search",
                query=search_query,
                n_results=8,
                metadata_filter=metadata_filter,
                user_roles=user_roles,
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
        else:
            # Fallback: direct search (backward compatibility without ctx)
            from backend.application.agent.filter_extractor import extract_metadata_filter as _extract
            from backend.infrastructure.search.bm25 import bm25_index
            from backend.infrastructure.search.hybrid import reciprocal_rank_fusion
            from backend.infrastructure.cache.query_cache import query_cache as _cache
            from backend.core.auth.acl_store import acl_store

            base_filter = metadata_filter or _extract(search_query)
            deprecated_filter = {"status": {"$ne": "deprecated"}}
            effective_filter = self._merge_where_filters(base_filter, deprecated_filter)

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
            if documents and user_roles:
                acl_filtered = [
                    (doc, meta, dist)
                    for doc, meta, dist in zip(documents, metadatas, distances)
                    if acl_store.check_permission(meta.get("path", ""), user_roles, "read")
                ]
                if acl_filtered:
                    documents, metadatas, distances = map(list, zip(*acl_filtered))
                else:
                    documents, metadatas, distances = [], [], []

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

        # 3. Clarity check — only for genuinely vague queries with poor results
        best_distance = min(distances) if distances else 1.0
        best_relevance = max(0, 1 - best_distance)
        query_too_short = len(query.strip()) < 6
        results_very_poor = best_relevance < 0.15
        needs_clarity_check = query_too_short and results_very_poor

        if needs_clarity_check and not is_followup:
            yield self._thinking("clarity_check", "start", "질문 명확성 확인 중")
            clarification = self._check_clarity_rule_based(query, metadatas, distances)
            if clarification:
                yield self._thinking("clarity_check", "done", "명확화 질문 필요", "추가 정보 요청")
                clarify_sources = self._build_sources(metadatas, distances, threshold=0.2)
                if clarify_sources:
                    yield self._sse("sources", SourcesEvent(sources=clarify_sources).model_dump_json())

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

        sources = self._build_sources(metadatas, distances, threshold=MIN_SOURCE_RELEVANCE)
        if sources:
            yield self._sse("sources", SourcesEvent(sources=sources).model_dump_json())

        if not relevant_docs:
            relevant_docs = [documents[0]]
            relevant_metas = [metadatas[0]] if metadatas else [{}]
            relevant_dists = [distances[0]] if distances else [1.0]

        # ── 5. Self-Reflective Cognitive Pipeline ─────────────────────────
        context = self._build_context_with_metadata(relevant_docs, relevant_metas, relevant_dists)

        if attached_context:
            context = attached_context.strip() + "\n\n---\n\n" + context

        # 5a. Hidden cognitive reflection — check cache first
        yield self._thinking("cognitive_reflect", "start", "의도 분석 및 답변 검토 중")
        reflection = self._get_cached_reflection(query, context)
        if reflection:
            yield self._thinking("cognitive_reflect", "done", "답변 검토 완료", "캐시 적중")
        else:
            reflection = await self._cognitive_reflect(query, context, history, ctx=ctx)
            if reflection:
                self._cache_reflection(query, context, reflection)
                yield self._thinking("cognitive_reflect", "done", "답변 검토 완료", "자기 검토 통과")
            else:
                yield self._thinking("cognitive_reflect", "done", "답변 검토 완료", "기본 모드")

        # 5a-1. Conflict detection — cognitive reflection result + dedicated check
        has_conflict = reflection.get("has_conflict", False) if reflection else False
        conflict_details = reflection.get("conflict_details", "") if reflection else ""

        # If cognitive reflection missed it, run dedicated conflict_check
        # Only when there are 2+ unique high-relevance sources (both >= 60% relevance)
        unique_sources = {m.get("file_path", "") for m in relevant_metas}
        high_relevance_sources = {
            m.get("file_path", "")
            for m, d in zip(relevant_metas, relevant_dists)
            if max(0, 1 - d) >= 0.6
        }
        if not has_conflict and len(high_relevance_sources) >= 2 and ctx:
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

        final_system = FINAL_ANSWER_SYSTEM_PROMPT + f"\n## Wiki 컨텍스트\n\n{context}"

        if reflection:
            final_system += (
                f"\n\n## 내부 검토 피드백 (사용자에게 표시하지 말 것)\n"
                f"다음 피드백을 반영하여 최종 답변을 작성하세요:\n"
                f"{reflection['self_critique']}"
            )

        messages = [{"role": "system", "content": final_system}]
        for msg in history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
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

    async def _cognitive_reflect(
        self, query: str, context: str, history: list[dict],
        *, ctx: AgentContext | None = None,
    ) -> dict | None:
        """Hidden cognitive pipeline: think → draft → critique.

        Uses Pydantic AI for structured output — automatic JSON validation and retry.
        Returns dict with internal_thought/draft_response/self_critique,
        or None if reflection fails.
        """
        from backend.application.agent.structured_agents import create_cognitive_agent

        history_text = ""
        if history:
            recent = history[-4:]
            lines = []
            for msg in recent:
                role = "User" if msg.get("role") == "user" else "Assistant"
                lines.append(f"{role}: {msg.get('content', '')[:200]}")
            history_text = "\n".join(lines)

        user_prompt = (
            f"## User Query\n{query}\n\n"
            f"## Conversation History\n{history_text or '(none)'}\n\n"
            f"## Wiki Context\n{context[:6000]}"
        )

        try:
            agent = create_cognitive_agent(COGNITIVE_REFLECT_PROMPT)
            result = await agent.run(user_prompt)
            reflection = result.output

            logger.info(
                "\n╔══════════════════════════════════════════════════════════╗\n"
                "║           COGNITIVE PIPELINE — INTERNAL LOG             ║\n"
                "╚══════════════════════════════════════════════════════════╝\n"
                f"\n📌 Query: {query}\n"
                f"\n🧠 INTERNAL THOUGHT:\n{reflection.internal_thought}\n"
                f"\n📝 DRAFT RESPONSE:\n{reflection.draft_response[:500]}"
                f"{'...' if len(reflection.draft_response) > 500 else ''}\n"
                f"\n🔍 SELF-CRITIQUE:\n{reflection.self_critique}\n"
                "══════════════════════════════════════════════════════════"
            )

            if not reflection.self_critique:
                logger.warning("Cognitive reflection produced empty critique, skipping")
                return None

            return reflection.model_dump()

        except Exception as e:
            logger.warning(f"Cognitive reflection failed: {e}, proceeding without reflection")
            return None

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

        # Closing instruction
        prompt_parts.append("위 지시사항과 참조 문서를 바탕으로 사용자의 질문에 답변하세요.\n출처를 반드시 명시하세요.")

        system_prompt = "\n\n".join(prompt_parts)

        # 3. Build messages and call LLM
        messages = [{"role": "system", "content": system_prompt}]
        for msg in ctx.history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": request.message})

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
        query = request.message

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
                recent = history[-6:]
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
        metadatas: list[dict], distances: list[float], threshold: float = 0.4
    ) -> list[SourceRef]:
        """Build deduplicated, relevance-filtered source list with metadata."""
        sources = []
        seen = set()
        for meta, dist in zip(metadatas, distances):
            relevance = max(0, 1 - dist)
            file_path = meta.get("file_path", "")
            status = meta.get("status", "")
            if status == "deprecated":
                continue
            if relevance >= threshold and file_path not in seen:
                seen.add(file_path)
                sources.append(SourceRef(
                    doc=file_path,
                    relevance=round(relevance, 3),
                    updated=meta.get("updated", ""),
                    updated_by=meta.get("updated_by", "") or meta.get("created_by", ""),
                    status=meta.get("status", ""),
                ))
        return sources

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
    def _resolve_superseded_chain(
        file_path: str, supersede_map: dict[str, str], max_depth: int = 5
    ) -> str | None:
        current = file_path
        for _ in range(max_depth):
            next_path = supersede_map.get(current)
            if not next_path or next_path == current:
                break
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

    # ── Reflection caching (in-memory LRU, TTL 10min) ──────────────────

    _reflection_cache: dict[str, tuple[dict, float]] = {}
    _REFLECTION_TTL = 600

    @classmethod
    def _make_reflection_key(cls, query: str, context: str) -> str:
        import hashlib
        raw = (query.strip().lower() + "|" + context[:500]).encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    @classmethod
    def _get_cached_reflection(cls, query: str, context: str) -> dict | None:
        import time as _time
        key = cls._make_reflection_key(query, context)
        entry = cls._reflection_cache.get(key)
        if entry is None:
            return None
        result, ts = entry
        if _time.time() - ts > cls._REFLECTION_TTL:
            del cls._reflection_cache[key]
            return None
        return result

    @classmethod
    def _cache_reflection(cls, query: str, context: str, result: dict) -> None:
        import time as _time
        key = cls._make_reflection_key(query, context)
        cls._reflection_cache[key] = (result, _time.time())
        if len(cls._reflection_cache) > 256:
            oldest_key = min(cls._reflection_cache, key=lambda k: cls._reflection_cache[k][1])
            del cls._reflection_cache[oldest_key]

    @staticmethod
    def _sse(event: str, data: str) -> str:
        return f"event: {event}\ndata: {data}\n\n"
