"""Section 3 → Section 2 호출 전담 클라이언트 (신규 v2).

기존 ``modeling_client.py``와는 별도 파일이며, 신규 온톨로지 API를 호출한다.
in-process 모드(direct call)와 HTTP 모드를 모두 지원한다:
- 단일 프로세스(개발/통합 테스트): ``in_process=True``로 라우터 함수 직접 호출 → HTTP 오버헤드 없음
- 분리 배포: HTTP로 ``MODELING_API_URL`` 호출
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from backend.shared.contracts.ontology import OntologyRequest, OntologyResponse

logger = logging.getLogger(__name__)


class OntologyClient:
    """Section 3 → Section 2 ontology 단일 호출 인터페이스."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        in_process: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url or os.getenv(
            "MODELING_API_URL", "http://localhost:8001"
        )
        self.in_process = in_process
        self._http: httpx.AsyncClient | None = None
        self._timeout = timeout

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self._timeout)
        return self._http

    async def query(self, req: OntologyRequest) -> OntologyResponse:
        if self.in_process:
            from backend.modeling.ontology.api.ontology_router import (
                query_ontology,
            )

            return await query_ontology(req)

        resp = await self.http.post(
            f"{self.base_url}/api/modeling/ontology/query",
            json=req.model_dump(mode="json"),
        )
        resp.raise_for_status()
        return OntologyResponse.model_validate(resp.json())

    async def search_terms(self, q: str, limit: int = 10) -> list[dict]:
        if self.in_process:
            from backend.modeling.ontology.api.ontology_router import search_terms

            return await search_terms(q=q, limit=limit)

        resp = await self.http.get(
            f"{self.base_url}/api/modeling/ontology/term/search",
            params={"q": q, "limit": limit},
        )
        resp.raise_for_status()
        return resp.json()

    async def graph_stats(self) -> dict:
        if self.in_process:
            from backend.modeling.ontology.api.ontology_router import graph_stats

            return await graph_stats()

        resp = await self.http.get(
            f"{self.base_url}/api/modeling/ontology/graph/stats"
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None


_client: OntologyClient | None = None


def get_ontology_client() -> OntologyClient:
    """싱글톤. 기본값은 in-process — 같은 백엔드 프로세스 내에서 호출."""
    global _client
    if _client is None:
        in_proc = os.getenv("ONTOLOGY_CLIENT_MODE", "in_process") == "in_process"
        _client = OntologyClient(in_process=in_proc)
    return _client


async def close_ontology_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
