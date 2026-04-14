"""Agent API — SSE streaming chat endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.core.schemas import (
    ChatRequest,
    ContentDelta,
    DoneEvent,
    ErrorEvent,
    RouterDecision,
    UnknownIntentResponse,
)
from backend.core.session import session_store
from backend.application.agent.router import router as main_router
from backend.application.agent.registry import registry
from backend.application.agent.context import AgentContext
from backend.application.wiki.wiki_service import WikiService

_wiki_service: WikiService | None = None
_chroma: object | None = None
_storage: object | None = None
_skill_loader: object | None = None   # UserSkillLoader
_skill_matcher: object | None = None  # SkillMatcher
_conflict_store: object | None = None  # ConflictStore
_meta_index: object | None = None     # MetadataIndex


def init(
    wiki_service: WikiService,
    *,
    chroma: object | None = None,
    storage: object | None = None,
    skill_loader: object | None = None,
    skill_matcher: object | None = None,
    conflict_store: object | None = None,
    meta_index: object | None = None,
) -> None:
    global _wiki_service, _chroma, _storage, _skill_loader, _skill_matcher, _conflict_store, _meta_index
    _wiki_service = wiki_service
    _chroma = chroma
    _storage = storage
    _skill_loader = skill_loader
    _skill_matcher = skill_matcher
    _conflict_store = conflict_store
    _meta_index = meta_index

logger = logging.getLogger(__name__)

from backend.core.auth import get_current_user, User

router = APIRouter(prefix="/api/agent", tags=["agent"], dependencies=[Depends(get_current_user)])


@router.post("/chat")
async def chat(request: ChatRequest, user: User = Depends(get_current_user)):
    """SSE streaming chat endpoint. Routes to appropriate agent."""
    current_user_roles = user.roles

    async def event_stream():
        try:
            # Get or create session
            session = session_store.get_or_create_session(request.session_id)

            # Capture history BEFORE adding current message (for multi-turn context)
            history = list(session.messages)

            session_store.append_message(request.session_id, {"role": "user", "content": request.message})

            # Immediate feedback — user sees activity before LLM classify
            yield f"event: thinking_step\ndata: {json.dumps({'step': 'routing', 'status': 'start', 'label': '질문 분석 중...', 'detail': ''})}\n\n"

            # Route to agent + pre-compute query augmentation in parallel
            is_followup = len(history) >= 2
            rag_agent = registry.get("WIKI_QA")
            augmented_query = None
            topic_shift = False

            if is_followup and rag_agent and hasattr(rag_agent, '_augment_query'):
                intent, augment_result = await asyncio.gather(
                    main_router.classify(request.message, has_attached_files=bool(request.attached_files)),
                    rag_agent._augment_query(request.message, history),
                )
                augmented_query = augment_result.get("augmented_query")
                topic_shift = augment_result.get("topic_shift", False)
            else:
                intent = await main_router.classify(request.message, has_attached_files=bool(request.attached_files))

            # Wiki section only uses WIKI_QA. SIMULATION/DEBUG_TRACE belong
            # to Section 2/3 (modeling/simulation) which are separate modules
            # and must not be reachable from the Wiki chat endpoint.
            forced_agent = "WIKI_QA" if intent.agent != "UNKNOWN" else "UNKNOWN"
            decision = RouterDecision(
                agent=forced_agent,
                confidence=intent.confidence,
                reasoning=f"wiki_section_forced (classified={intent.agent}, action={intent.action})",
            )
            logger.info(
                f"Routed to {decision.agent} (confidence={decision.confidence}, action={intent.action})"
            )

            # Mark routing step done and send routing info
            yield f"event: thinking_step\ndata: {json.dumps({'step': 'routing', 'status': 'done', 'label': '질문 분석 완료', 'detail': ''})}\n\n"

            routing_data = json.dumps({
                "agent": decision.agent,
                "confidence": decision.confidence,
            })
            yield f"event: routing\ndata: {routing_data}\n\n"

            # Handle UNKNOWN intent
            if decision.agent == "UNKNOWN":
                resp = UnknownIntentResponse()
                msg = f"{resp.message}\n\n사용 가능한 에이전트: {', '.join(resp.available_agents)}\n\n예시:\n"
                for ex in resp.examples:
                    msg += f"- {ex}\n"
                yield f"event: content_delta\ndata: {ContentDelta(delta=msg).model_dump_json()}\n\n"
                yield f"event: done\ndata: {DoneEvent().model_dump_json()}\n\n"
                session_store.append_message(request.session_id, {"role": "assistant", "content": msg})
                return

            # Get agent from registry
            agent = registry.get(decision.agent)
            if agent is None:
                yield f"event: error\ndata: {ErrorEvent(error_code='AGENT_NOT_FOUND', message=f'Agent {decision.agent} not registered').model_dump_json()}\n\n"
                return

            # Load attached file contents if any
            attached_context = ""
            if request.attached_files and _wiki_service:
                for fp in request.attached_files:
                    wiki_file = await _wiki_service.get_file(fp)
                    if wiki_file:
                        attached_context += f"\n\n--- 첨부 파일: {fp} ---\n{wiki_file.content}\n"
                        logger.info(f"Attached file loaded: {fp}")

            # L3: Handle path disambiguation responses
            path_preference = None
            if request.clarification_response_id:
                # User selected a path from disambiguation options
                selected = request.message.strip()
                # Validate: is this a known path_depth_1 value?
                if selected and not selected.startswith("/"):
                    path_preference = selected
                    if selected not in session.path_preferences:
                        session.path_preferences.append(selected)
                    logger.info(f"Path preference set: {selected} (session total: {session.path_preferences})")

            # Build AgentContext for skill-based agents
            ctx = AgentContext(
                request=request,
                chroma=_chroma,
                storage=_storage,
                session_store=session_store,
                history=history,
                attached_context=attached_context,
                augmented_query=augmented_query,
                user_roles=current_user_roles,
                conflict_store=_conflict_store,
                meta_index=_meta_index,
                intent_action=intent.action,
                username=user.name,
                path_preference=path_preference,
                path_preferences=list(session.path_preferences),
            )

            # Resolve user-facing skill (explicit or auto-matched)
            if _skill_loader:
                username = user.name if user else ""
                if request.skill_path:
                    # Explicit skill invocation
                    skill = await _skill_loader.get_skill(request.skill_path)
                    if skill:
                        ctx.user_skill = skill
                        ctx.skill_context = await _skill_loader.load_skill_context(skill)
                        ctx.skill_context.preamble_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                        ctx.skill_context.preamble_user = user.name if user else ""
                        logger.info(f"Explicit skill: {skill.title} ({skill.path})")
                elif _skill_matcher:
                    # Auto-match against triggers (skip skills user dismissed)
                    match_result = await _skill_matcher.match(request.message, username, _skill_loader)
                    if match_result:
                        skill, confidence = match_result
                        if skill.path in request.dismissed_skills:
                            logger.info(f"Skipped dismissed skill: {skill.title} ({skill.path})")
                        else:
                            ctx.user_skill = skill
                            ctx.skill_context = await _skill_loader.load_skill_context(skill)
                            ctx.skill_context.preamble_date = datetime.now().strftime("%Y-%m-%d %H:%M")
                            ctx.skill_context.preamble_user = user.name if user else ""
                            # Notify client which skill matched
                            match_data = json.dumps({
                                "skill_path": skill.path,
                                "skill_title": skill.title,
                                "skill_icon": skill.icon,
                                "confidence": confidence,
                            })
                            yield f"event: skill_match\ndata: {match_data}\n\n"
                            logger.info(f"Auto-matched skill: {skill.title} (confidence={confidence:.2f})")

            # Execute agent (yields SSE events), collect assistant response
            assistant_content = ""
            async for event in agent.execute(request, ctx=ctx, history=history, attached_context=attached_context, augmented_query=augmented_query, topic_shift=topic_shift, user_roles=current_user_roles, intent=intent):
                yield event
                # Capture content deltas for session history
                if "content_delta" in event and '"delta"' in event:
                    try:
                        data_line = event.split("data: ", 1)[1].split("\n")[0]
                        parsed = json.loads(data_line)
                        assistant_content += parsed.get("delta", "")
                    except (IndexError, json.JSONDecodeError):
                        pass

            # Store assistant response in session for multi-turn context
            if assistant_content:
                session_store.append_message(request.session_id, {"role": "assistant", "content": assistant_content})

        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            yield f"event: error\ndata: {ErrorEvent(error_code='INTERNAL_ERROR', message=str(e), retry_hint='잠시 후 다시 시도해주세요.').model_dump_json()}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
