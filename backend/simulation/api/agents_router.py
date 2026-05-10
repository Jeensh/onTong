"""Section 3 — Agent 4종 라우터 + 온톨로지 시각화.

엔드포인트:
- POST /api/simulation/agents/impact          ← Agent 1 영향도 (order target도 지원)
- POST /api/simulation/agents/test-data       ← Agent 2 동기 호출 (≤200건)
- POST /api/simulation/agents/test-data/stream ← Agent 2 SSE 스트리밍 (Phase 2 신규)
- POST /api/simulation/agents/locator         ← Agent 3 위치 파악
- GET  /api/simulation/agents/explorer/search ← Agent 4 노드 검색
- POST /api/simulation/agents/explorer/expand ← Agent 4 1-2 hop 이웃
- POST /api/simulation/agents/explorer/path   ← Agent 4 두 노드 간 shortest path
- GET  /api/simulation/agents/ontology-graph  ← 전역 시각화 (디자인 흐름 등)
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.modeling.ontology.client import get_client

from ..agents.agent1_impact import Agent1Request, Agent1Result, execute_agent1
from ..agents.agent2_test_data import (
    Agent2Request,
    Agent2Result,
    execute_agent2,
    stream_agent2,
)
from ..agents.agent3_locator import Agent3Request, Agent3Result, execute_agent3
from ..agents.agent4_explorer import (
    ExpandRequest,
    ExpandResult,
    NodeSearchResult,
    PathRequest,
    PathResult,
    expand,
    find_path,
    search_nodes,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation/agents", tags=["simulation-agents"])


# ─── Agent 1/2/3 ────────────────────────────────────────────────────


@router.post("/impact", response_model=Agent1Result)
async def run_agent1(req: Agent1Request) -> Agent1Result:
    try:
        return await execute_agent1(req)
    except Exception as exc:
        logger.exception("Agent 1 failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/test-data", response_model=Agent2Result)
async def run_agent2(req: Agent2Request) -> Agent2Result:
    try:
        return await execute_agent2(req)
    except Exception as exc:
        logger.exception("Agent 2 failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/test-data/stream")
async def run_agent2_stream(req: Agent2Request) -> StreamingResponse:
    """SSE 스트리밍. 큰 N (≤1000)에서 진행 상황 실시간 표시.

    이벤트 스키마: `{event: "case_started"|"case_done"|"case_failed"|"summary"|"run_started"|"run_complete", data: {...}}`
    """

    async def gen():
        try:
            async for evt in stream_agent2(req):
                payload = json.dumps(evt, ensure_ascii=False, default=str)
                yield f"data: {payload}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent 2 stream failed")
            err = {"event": "error", "data": {"message": str(exc), "type": type(exc).__name__}}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx buffering off
            "Connection": "keep-alive",
        },
    )


@router.post("/locator", response_model=Agent3Result)
async def run_agent3(req: Agent3Request) -> Agent3Result:
    try:
        return await execute_agent3(req)
    except Exception as exc:
        logger.exception("Agent 3 failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ─── Agent 4 — 온톨로지 익스플로러 ─────────────────────────────────


@router.get("/explorer/search", response_model=NodeSearchResult)
def explorer_search(
    q: str = Query(..., min_length=1),
    groups: str | None = Query(None, description="콤마 구분 group 필터"),
) -> NodeSearchResult:
    group_list = groups.split(",") if groups else None
    return search_nodes(q, group_list)


@router.post("/explorer/expand", response_model=ExpandResult)
def explorer_expand(req: ExpandRequest) -> ExpandResult:
    return expand(req)


@router.post("/explorer/path", response_model=PathResult)
def explorer_path(req: PathRequest) -> PathResult:
    return find_path(req)


# ─── 전역 그래프 시각화 ─────────────────────────────────────────────


@router.get("/ontology-graph")
def ontology_graph(scope: str = "design-flow") -> dict:
    """전체 그래프 (디자인 흐름 / Term-Step / Method-Step / 전체)."""
    client = get_client()
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    if scope in ("design-flow", "all"):
        for r in client.query(
            "MATCH (s:Step)-[:USES_STANDARD]->(std:Standard) "
            "RETURN s.step_number AS n, s.korean_name AS step_name, "
            "       std.code AS code, std.korean_name AS std_name"
        ):
            sid = f"step:{r['n']}"
            std_id = f"standard:{r['code']}"
            nodes[sid] = {"id": sid, "label": f"Step {r['n']}\n{r['step_name']}", "group": "step"}
            nodes[std_id] = {"id": std_id, "label": f"{r['code']}\n{r['std_name']}", "group": "standard"}
            edges.append({"from": sid, "to": std_id, "label": "USES_STANDARD"})

    if scope in ("method-step", "design-flow", "all"):
        for r in client.query(
            "MATCH (m:Method)-[:CALCULATES]->(s:Step) "
            "OPTIONAL MATCH (c:Class)-[:CONTAINS]->(m) "
            "RETURN m.name AS method, c.name AS cls, s.step_number AS n"
        ):
            mid = f"method:{r['cls']}.{r['method']}"
            sid = f"step:{r['n']}"
            nodes[mid] = {
                "id": mid,
                "label": f"{r['cls']}\n.{r['method']}()",
                "group": "method",
            }
            nodes.setdefault(sid, {"id": sid, "label": f"Step {r['n']}", "group": "step"})
            edges.append({"from": mid, "to": sid, "label": "CALCULATES"})

    if scope in ("term-process", "all"):
        for r in client.query(
            "MATCH (t:Term)-[r:REFERS_TO_PROCESS]->(s:Step) "
            "RETURN t.korean_name AS term, t.id AS tid, "
            "       s.step_number AS n, r.role AS role"
        ):
            tid = f"term:{r['tid']}"
            sid = f"step:{r['n']}"
            nodes[tid] = {"id": tid, "label": r["term"], "group": "term"}
            nodes.setdefault(sid, {"id": sid, "label": f"Step {r['n']}", "group": "step"})
            edges.append({"from": tid, "to": sid, "label": r["role"] or "REFERS_TO"})

    return {"nodes": list(nodes.values()), "edges": edges, "scope": scope}
