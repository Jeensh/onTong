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


def init(
    wiki_service: WikiService,
    *,
    chroma: object | None = None,
    storage: object | None = None,
    skill_loader: object | None = None,
    skill_matcher: object | None = None,
) -> None:
    global _wiki_service, _chroma, _storage, _skill_loader, _skill_matcher
    _wiki_service = wiki_service
    _chroma = chroma
    _storage = storage
    _skill_loader = skill_loader
    _skill_matcher = skill_matcher

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

            session.messages.append({"role": "user", "content": request.message})

            # Route to agent + pre-compute query augmentation in parallel
            is_followup = len(history) >= 2
            rag_agent = registry.get("WIKI_QA")
            augmented_query = None

            if is_followup and rag_agent and hasattr(rag_agent, '_augment_query'):
                decision, augmented_query = await asyncio.gather(
                    main_router.route(request.message),
                    rag_agent._augment_query(request.message, history),
                )
            else:
                decision = await main_router.route(request.message)

            logger.info(
                f"Routed to {decision.agent} (confidence={decision.confidence})"
            )

            # Send routing info
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
                session.messages.append({"role": "assistant", "content": msg})
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
                    # Auto-match against triggers
                    match_result = await _skill_matcher.match(request.message, username, _skill_loader)
                    if match_result:
                        skill, confidence = match_result
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
            async for event in agent.execute(request, ctx=ctx, history=history, attached_context=attached_context, augmented_query=augmented_query, user_roles=current_user_roles):
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
                session.messages.append({"role": "assistant", "content": assistant_content})

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
