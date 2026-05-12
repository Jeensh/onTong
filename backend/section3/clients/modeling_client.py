"""Section 3 → Section 2 modeling HTTP 클라이언트.

원칙:
- 오직 HTTP 호출만 (httpx). Neo4j driver / OntologyClient / Cypher 0건.
- modeling 측 endpoint 가 어떻게 동작하든 — Neo4j 든 PostgreSQL 든 — Section 3 는 무관.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE = os.environ.get("MODELING_API_BASE", "http://localhost:8001")
DEFAULT_TIMEOUT = float(os.environ.get("MODELING_API_TIMEOUT", "30.0"))


class ModelingClient:
    """modeling 의 /api/modeling/ontology/* + /api/ontology/* HTTP wrapper.

    유의:
    - 인스턴스 당 단일 httpx.AsyncClient — connection pooling.
    - async 함수만 노출. agent 들이 await 으로 호출.
    """

    def __init__(self, base_url: str = DEFAULT_BASE, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    # ─── 새 modeling/ontology 시스템 (Section 3 의 주력) ─────────

    async def query(
        self,
        intent: str,
        parameters: Optional[dict[str, Any]] = None,
        natural_language: Optional[str] = None,
        request_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """POST /api/modeling/ontology/query — 3 intent (impact_analysis / simulate / explain) 의 단일 진입점.

        응답 shape (OntologyResponse):
        - status: success / partial / need_more_info / unsupported / error
        - result: intent 별 result dict (또는 None)
        - missing_info: questions[] + reason (need_more_info 시)
        - confidence: 0~1
        - timestamp
        """
        body = {
            "request_id": request_id or f"s3-{uuid.uuid4().hex[:12]}",
            "intent": intent,
            "parameters": parameters or {},
        }
        if natural_language:
            body["natural_language"] = natural_language
        if context:
            body["context"] = context
        r = await self._client.post("/api/modeling/ontology/query", json=body)
        r.raise_for_status()
        return r.json()

    async def graph_stats(self) -> dict[str, Any]:
        """GET /api/modeling/ontology/graph/stats — 노드/관계 카운트."""
        r = await self._client.get("/api/modeling/ontology/graph/stats")
        r.raise_for_status()
        return r.json()

    async def term_search(self, q: str) -> list[dict[str, Any]]:
        """GET /api/modeling/ontology/term/search — 자연어 키워드 → Term 후보."""
        r = await self._client.get("/api/modeling/ontology/term/search", params={"q": q})
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])

    # ─── 기존 /api/ontology/* (보조 — 14 Table / 14 Standard / 198 Method 의 raw catalog 가 필요할 때)

    async def list_actions(self, repo_id: Optional[str] = None, limit: int = 1000) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if repo_id:
            params["repo_id"] = repo_id
        r = await self._client.get("/api/ontology/actions", params=params)
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])

    async def list_terms(self, repo_id: Optional[str] = None, limit: int = 1000) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if repo_id:
            params["repo_id"] = repo_id
        r = await self._client.get("/api/ontology/terms", params=params)
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])

    async def search(self, q: str, limit: int = 20) -> list[dict[str, Any]]:
        """GET /api/ontology/search — 통합 검색 (term/action/code) — 보조."""
        r = await self._client.get("/api/ontology/search", params={"q": q, "limit": limit})
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])


# ─── 단일 인스턴스 (FastAPI dependency 용) ────────────────────────

_singleton: Optional[ModelingClient] = None


def get_modeling_client() -> ModelingClient:
    """FastAPI Depends 로 주입. 첫 호출 시 생성, 그 후 재사용."""
    global _singleton
    if _singleton is None:
        _singleton = ModelingClient()
    return _singleton


__all__ = ["ModelingClient", "get_modeling_client"]
