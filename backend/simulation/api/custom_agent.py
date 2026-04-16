"""Custom Agent API — 사용자 정의 Slab 설계 에이전트 CRUD + 빌더 + 실행.

Endpoints:
    GET    /api/simulation/custom-agents              → 목록 조회
    POST   /api/simulation/custom-agents              → 에이전트 등록
    DELETE /api/simulation/custom-agents/{id}         → 에이전트 삭제
    POST   /api/simulation/custom-agents/build/chat   → 채팅 빌더 (SSE)
    POST   /api/simulation/custom-agents/{id}/run     → 에이전트 실행 (SSE)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/simulation/custom-agents", tags=["custom-agent"])

_STORE_PATH = Path(__file__).parent.parent / "data" / "custom_agents.json"


# ── Storage helpers ──────────────────────────────────────────────────────

def _load_agents() -> list[dict]:
    if not _STORE_PATH.exists():
        _STORE_PATH.write_text("[]", encoding="utf-8")
    return json.loads(_STORE_PATH.read_text(encoding="utf-8"))


def _save_agents(agents: list[dict]) -> None:
    _STORE_PATH.write_text(
        json.dumps(agents, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Pydantic models ──────────────────────────────────────────────────────

class CustomAgentCreate(BaseModel):
    name: str
    description: str
    icon: str = "🤖"
    color: str = "#6366f1"
    system_prompt: str
    available_tools: list[str]
    example_prompt: str
    created_by: str = "form"  # "chat" | "form"


class AgentBuilderChatRequest(BaseModel):
    message: str
    history: list[dict] = []  # [{"role": "user"|"assistant", "content": str}]


class CustomAgentRunRequest(BaseModel):
    message: str


# ── CRUD endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_agents():
    """등록된 커스텀 에이전트 목록 반환."""
    return _load_agents()


@router.post("")
async def create_agent(req: CustomAgentCreate):
    """새 커스텀 에이전트 등록."""
    agents = _load_agents()
    agent = {
        "id": str(uuid.uuid4()),
        "name": req.name,
        "description": req.description,
        "icon": req.icon,
        "color": req.color,
        "system_prompt": req.system_prompt,
        "available_tools": req.available_tools,
        "example_prompt": req.example_prompt,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": req.created_by,
    }
    agents.append(agent)
    _save_agents(agents)
    logger.info(f"Custom agent registered: {agent['name']} (id={agent['id']})")
    return agent


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """에이전트 삭제."""
    agents = _load_agents()
    new_agents = [a for a in agents if a["id"] != agent_id]
    if len(new_agents) == len(agents):
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    _save_agents(new_agents)
    logger.info(f"Custom agent deleted: id={agent_id}")
    return {"deleted": agent_id}


# ── Agent Builder Chat (SSE) ──────────────────────────────────────────────

@router.post("/build/chat")
async def builder_chat(req: AgentBuilderChatRequest):
    """채팅 기반 에이전트 빌더 — LLM과 대화하며 에이전트 정의를 수집."""

    async def event_stream():
        try:
            from backend.simulation.agent.agent_builder_agent import run_agent_builder
            async for evt in run_agent_builder(req.message, req.history):
                event_type = evt.get("event", "message")
                data = json.dumps(evt.get("data", {}), ensure_ascii=False)
                yield f"event: {event_type}\ndata: {data}\n\n"
        except Exception as e:
            logger.exception(f"Agent builder error: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Custom Agent Runner (SSE) ─────────────────────────────────────────────

@router.post("/{agent_id}/run")
async def run_agent(agent_id: str, req: CustomAgentRunRequest):
    """등록된 커스텀 에이전트 실행 — LLM + Slab 도구로 응답 생성."""
    agents = _load_agents()
    agent = next((a for a in agents if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    async def event_stream():
        try:
            from backend.simulation.agent.custom_agent_runner import run_custom_agent
            async for evt in run_custom_agent(agent, req.message):
                event_type = evt.get("event", "message")
                data = json.dumps(evt.get("data", {}), ensure_ascii=False)
                yield f"event: {event_type}\ndata: {data}\n\n"
        except Exception as e:
            logger.exception(f"Custom agent run error (id={agent_id}): {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
