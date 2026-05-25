"""Section 2 (Modeling) FastAPI 라우터 — 3-Layer 온톨로지 진입점.

엔드포인트:
- POST /api/modeling/ontology/query     (5종 intent 통합)
- GET  /api/modeling/ontology/graph/stats
- GET  /api/modeling/ontology/term/search
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.shared.contracts.ontology import (
    Intent,
    OntologyRequest,
    OntologyResponse,
    Status,
)

from ..client import get_client
from ..queries import impact_queries, locator_queries, test_data_queries

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/modeling/ontology", tags=["modeling-ontology"])


@router.post("/query", response_model=OntologyResponse)
async def query_ontology(req: OntologyRequest) -> OntologyResponse:
    """3개 Agent의 단일 진입점. intent에 따라 핸들러로 분기."""
    try:
        if req.intent is Intent.IMPACT_ANALYSIS:
            return await impact_queries.analyze(req)
        if req.intent is Intent.SIMULATE:
            return await test_data_queries.generate(req)
        if req.intent is Intent.EXPLAIN:
            return await locator_queries.locate(req)
        if req.intent is Intent.QUERY:
            # 단순 조회 — 현재는 term/search 자동완성과 graph/stats가 GET으로 분리됨
            return OntologyResponse(
                request_id=req.request_id,
                status=Status.UNSUPPORTED,
                result={
                    "message": "query intent는 GET /term/search 또는 /graph/stats를 사용하세요",
                },
            )
        if req.intent is Intent.OPTIMIZE:
            return OntologyResponse(
                request_id=req.request_id,
                status=Status.UNSUPPORTED,
                result={"message": "optimize intent는 추후 구현 예정"},
            )
        # Pydantic이 enum을 강제하므로 도달 불가지만, 안전망.
        return OntologyResponse(
            request_id=req.request_id,
            status=Status.UNSUPPORTED,
            result={"message": f"Unknown intent: {req.intent}"},
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — 어떤 예외도 500으로 빠지지 않게 status=ERROR로 변환
        logger.exception("Ontology query failed: %s", exc)
        return OntologyResponse(
            request_id=req.request_id,
            status=Status.ERROR,
            result={"message": str(exc)},
        )


_NODE_LABELS = (
    "Term", "TermCategory", "Step", "Standard", "Variable",
    "ErrorCode", "Class", "Method", "Table",
)
_REL_TYPES = (
    "BELONGS_TO", "IS_A", "RELATED_TO", "PRECEDES", "DEPENDS_ON",
    "USES_STANDARD", "REQUIRES_INPUT", "PRODUCES_OUTPUT", "CONSTRAINS",
    "TRIGGERS_ON_FAIL", "REFERS_TO_PROCESS", "CONTAINS", "CALCULATES",
    "IMPLEMENTS", "RELATES_TO_STANDARD", "MAPS_TO_STANDARD",
)


@router.get("/graph/stats")
async def graph_stats() -> dict:
    """온톨로지 노드/관계 통계 (디버깅/모니터링).

    Neo4j 미가용 시 모두 0 으로 응답 — 다운스트림(UI 대시보드)을 깨뜨리지 않는다.
    backend 가 SQLite 중심으로 이동했고 graph view 는 보조 기능이므로 graceful degradation.
    """
    nodes: dict[str, int] = {k: 0 for k in _NODE_LABELS}
    relations: dict[str, int] = {k: 0 for k in _REL_TYPES}
    totals = {"nodes": 0, "relations": 0}
    backend_status: dict = {"available": True}

    try:
        client = get_client()
        for label in _NODE_LABELS:
            rows = client.query(f"MATCH (n:{label}) RETURN count(n) AS n")
            nodes[label] = rows[0]["n"]
        for rel in _REL_TYPES:
            rows = client.query(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS n")
            relations[rel] = rows[0]["n"]
        totals = {
            "nodes": client.query("MATCH (n) RETURN count(n) AS n")[0]["n"],
            "relations": client.query("MATCH ()-[r]->() RETURN count(r) AS n")[0]["n"],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("graph_stats: Neo4j unavailable, returning zeros: %s", exc)
        backend_status = {"available": False, "reason": str(exc)[:200]}

    return {
        "nodes": nodes,
        "relations": relations,
        "totals": totals,
        "backend": backend_status,
    }


@router.get("/term/search")
async def search_terms(
    q: str = Query(..., min_length=1, description="검색어"),
    limit: int = Query(10, ge=1, le=100),
) -> list[dict]:
    """업무 용어 자동완성. korean/english/aliases 모두 검색.

    Neo4j 미가용 시 빈 리스트 반환 — 자동완성이 없어도 다른 검색 경로(SQLite-backed
    `/api/ontology/search`)가 살아 있으므로 UI 가 멎지 않는다.
    """
    try:
        client = get_client()
        return client.query(
            "MATCH (t:Term) "
            "WHERE t.korean_name CONTAINS $q "
            "   OR t.english_name CONTAINS $q "
            "   OR ANY(alias IN t.aliases WHERE alias CONTAINS $q) "
            "RETURN t.id AS id, t.korean_name AS name, "
            "       t.english_name AS english, t.category AS category, "
            "       t.description AS description "
            "LIMIT $limit",
            q=q,
            limit=limit,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("term_search: Neo4j unavailable, returning empty: %s", exc)
        return []
