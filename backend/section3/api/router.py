"""Section 3 FastAPI router — chat (SSE) + 3 task endpoints.

URL prefix: /api/section3

endpoints:
- POST /api/section3/chat          (SSE 스트리밍 — bridge agent)
- POST /api/section3/sandbox/run   (SSE 스트리밍 — sandbox agent)
- POST /api/section3/code-impact   (SSE 스트리밍 — code impact agent)
- POST /api/section3/data-impact   (SSE 스트리밍 — data impact agent)
- GET  /api/section3/stats         (modeling graph stats forward)
- GET  /api/section3/term-search   (modeling term search forward)
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from backend.section3.agents.bridge_agent import BridgeAgent
from backend.section3.agents.code_impact_agent import CodeImpactAgent
from backend.section3.agents.data_impact_agent import DataImpactAgent
from backend.section3.agents.sandbox_agent import SandboxAgent
from backend.section3.clients.modeling_client import ModelingClient, get_modeling_client
from backend.section3.contracts import (
    ChatRequest,
    CodeImpactRequest,
    DataImpactRequest,
    SandboxRequest,
    StreamEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/section3", tags=["section3"])


# ─── SSE helper ───────────────────────────────────────────────


async def _sse(events: AsyncIterator[StreamEvent]) -> AsyncIterator[bytes]:
    """StreamEvent async generator → SSE byte stream."""
    import asyncio
    try:
        async for ev in events:
            payload = ev.model_dump(mode="json")
            yield f"event: {ev.type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
            # 각 event 마다 asyncio scheduler 에 즉시 yield — uvicorn/proxy 가 chunk flush 하도록 강제
            await asyncio.sleep(0)
    except Exception as e:
        logger.exception("SSE stream error")
        err = json.dumps({"type": "error", "payload": {"message": str(e)}}, ensure_ascii=False)
        yield f"event: error\ndata: {err}\n\n".encode("utf-8")


_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # nginx / 다른 proxy 의 buffering 방지
}


_V1_CHAT_DEPRECATION_HEADERS = {
    **_SSE_HEADERS,
    "X-Deprecated": "true",
    # RFC 7234 §5.5 — Warning 299 "Miscellaneous persistent warning"
    "Warning": '299 - "Section 3 chat v1 is deprecated; migrate to /api/section3/multiturn/* (Phase 1~6 complete)"',
    "X-Deprecation-Date": "2026-05-18",
    "X-Replacement": "/api/section3/multiturn/start",
}


# ─── endpoints ────────────────────────────────────────────────


@router.post("/chat")
async def chat(
    req: ChatRequest,
    modeling: ModelingClient = Depends(get_modeling_client),
):
    """온톨로지 브릿지 chat — bridge agent SSE streaming (DEPRECATED 2026-05-18).

    응답 header 에 `X-Deprecated: true` + RFC 7234 `Warning: 299` 포함.
    신 endpoint: `/api/section3/multiturn/start` (Phase 1~6 production).
    """
    logger.warning("/api/section3/chat (v1 bridge_agent) 호출 — multiturn v2 로 마이그레이션 권장")
    agent = BridgeAgent(modeling=modeling)
    return StreamingResponse(
        _sse(agent.run(req)),
        media_type="text/event-stream",
        headers=_V1_CHAT_DEPRECATION_HEADERS,
    )


@router.post("/sandbox/run")
async def sandbox_run(
    req: SandboxRequest,
    modeling: ModelingClient = Depends(get_modeling_client),
):
    """샌드박스 — 테스트 데이터 생성 + 격리 실행."""
    agent = SandboxAgent(modeling=modeling)
    return StreamingResponse(_sse(agent.run(req)), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/code-impact")
async def code_impact(
    req: CodeImpactRequest,
    modeling: ModelingClient = Depends(get_modeling_client),
):
    """영향도 분석 (코드 변경)."""
    agent = CodeImpactAgent(modeling=modeling)
    return StreamingResponse(_sse(agent.run(req)), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/data-impact")
async def data_impact(
    req: DataImpactRequest,
    modeling: ModelingClient = Depends(get_modeling_client),
):
    """데이터 변경 분석 (기준/slab data)."""
    agent = DataImpactAgent(modeling=modeling)
    return StreamingResponse(_sse(agent.run(req)), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/stats")
async def stats(modeling: ModelingClient = Depends(get_modeling_client)):
    """modeling 의 graph/stats forward — UI dashboard 용."""
    return await modeling.graph_stats()


@router.get("/term-search")
async def term_search(
    q: str = Query(..., description="검색어"),
    modeling: ModelingClient = Depends(get_modeling_client),
):
    """modeling 의 term/search forward — autocomplete."""
    return {"items": await modeling.term_search(q)}


# ─────────────────────────────────────────────────────────────────────────────
# /repos — per-repo summary for Section 3 dashboard (Phase 11)
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/repos")
def list_repos() -> dict:
    """SQLite ontology.db 의 repo 별 카운트 요약.

    반환:
      `{"repos": [{"repo_id": ..., "counts": {...}}]}`
    counts 8 종 (actions / code_methods / code_types / business_terms /
    business_rules / realizations / call_sites / sessions).
    repo_id 알파벳 정렬. 어느 한 테이블이라도 repo 가 등장하면 surface.
    """
    from sqlalchemy import distinct, func, select
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow, CallSiteRow
    from backend.modeling.domain_layer.orm import BusinessRuleRow, BusinessTermRow
    from backend.modeling.mapping_layer.orm import ActionRow, RealizationRow
    from backend.section3.agents.multiturn.orm import Section3SessionRow

    counters: list = [
        ("actions",        ActionRow),
        ("code_methods",   CodeMethodRow),
        ("code_types",     CodeTypeRow),
        ("business_terms", BusinessTermRow),
        ("business_rules", BusinessRuleRow),
        ("realizations",   RealizationRow),
        ("call_sites",     CallSiteRow),
        ("sessions",       Section3SessionRow),
    ]

    with session_scope() as s:
        # 어떤 테이블이든 등장한 repo_id 집합 — SQL UNION 보다 Python set 이 단순
        repo_ids: set[str] = set()
        for _, table in counters:
            for (rid,) in s.execute(select(distinct(table.repo_id))).all():
                if rid:
                    repo_ids.add(rid)
        all_repos: list[str] = sorted(repo_ids)

        out: list[dict] = []
        for repo_id in all_repos:
            counts: dict[str, int] = {}
            for key, table in counters:
                n = s.execute(
                    select(func.count()).where(table.repo_id == repo_id),
                ).scalar() or 0
                counts[key] = int(n)
            out.append({"repo_id": repo_id, "counts": counts})

        return {"repos": out}


__all__ = ["router"]
