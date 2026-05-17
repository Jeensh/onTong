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

    async def search(self, q: str, limit: int = 20, repo_id: Optional[str] = None) -> list[dict[str, Any]]:
        """GET /api/ontology/search — 통합 검색 (term/action/code) — 보조."""
        params: dict[str, Any] = {"q": q, "limit": limit}
        if repo_id:
            params["repo_id"] = repo_id
        r = await self._client.get("/api/ontology/search", params=params)
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])

    # ─── code-types — Java class/method 의 body_text · line · anchors ───────
    # ONTOLOGY_API_AUDIT.md §2.2 — RichResultCard 의 source_locations 채우기용

    async def get_code_type(self, fqn: str) -> dict[str, Any]:
        """GET /api/ontology/code-types/{fqn} — Java class detail (methods.body_text 포함)."""
        r = await self._client.get(f"/api/ontology/code-types/{fqn}")
        r.raise_for_status()
        return r.json()

    async def list_code_types(
        self,
        repo_id: Optional[str] = None,
        kind: Optional[str] = None,
        role: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """GET /api/ontology/code-types — class catalog. role: service|adapter|controller|model|util|framework."""
        params: dict[str, Any] = {}
        if repo_id:
            params["repo_id"] = repo_id
        if kind:
            params["kind"] = kind
        if role:
            params["role"] = role
        r = await self._client.get("/api/ontology/code-types", params=params)
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])

    async def get_call_sites(self, method_fqn: str) -> list[dict[str, Any]]:
        """GET /api/ontology/code-methods/{fqn}/call-sites — method 의 호출 그래프."""
        r = await self._client.get(f"/api/ontology/code-methods/{method_fqn}/call-sites")
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])

    async def get_method_anchor_bindings(self, method_fqn: str) -> list[dict[str, Any]]:
        """GET /api/ontology/code-methods/{fqn}/anchor-bindings — method 내 anchor (literal/guard) 라인."""
        r = await self._client.get(f"/api/ontology/code-methods/{method_fqn}/anchor-bindings")
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])

    # ─── actions — action ↔ code realization · delegate tree ─────────

    async def get_action(self, fqn: str) -> dict[str, Any]:
        """GET /api/ontology/actions/{fqn} — action 상세 + realizations."""
        r = await self._client.get(f"/api/ontology/actions/{fqn}")
        r.raise_for_status()
        return r.json()

    async def get_action_anchor_bindings(self, action_fqn: str) -> list[dict[str, Any]]:
        """GET /api/ontology/actions/{fqn}/anchor-bindings — action slot ↔ code anchor 매핑."""
        r = await self._client.get(f"/api/ontology/actions/{action_fqn}/anchor-bindings")
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])

    async def get_action_delegates_tree(self, action_fqn: str, max_depth: int = 3) -> dict[str, Any]:
        """GET /api/ontology/actions/{fqn}/delegates-to-tree — sub-action 호출 트리."""
        r = await self._client.get(
            f"/api/ontology/actions/{action_fqn}/delegates-to-tree",
            params={"max_depth": max_depth},
        )
        r.raise_for_status()
        return r.json()

    # ─── business-rules · anchor-bindings (전역) ──────────────────────

    async def list_business_rules(self, repo_id: Optional[str] = None) -> list[dict[str, Any]]:
        """GET /api/ontology/business-rules — 룰 statement + enforced_by + operational_history."""
        params: dict[str, Any] = {}
        if repo_id:
            params["repo_id"] = repo_id
        r = await self._client.get("/api/ontology/business-rules", params=params)
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])

    async def list_anchor_bindings(self, repo_id: Optional[str] = None) -> list[dict[str, Any]]:
        """GET /api/ontology/anchor-bindings — 전역 anchor (code line ↔ action slot)."""
        params: dict[str, Any] = {}
        if repo_id:
            params["repo_id"] = repo_id
        r = await self._client.get("/api/ontology/anchor-bindings", params=params)
        r.raise_for_status()
        body = r.json()
        return body if isinstance(body, list) else body.get("items", [])

    # ─── terms detail ────────────────────────────────────────────────

    async def get_term(self, fqn: str) -> dict[str, Any]:
        """GET /api/ontology/terms/{fqn}."""
        r = await self._client.get(f"/api/ontology/terms/{fqn}")
        r.raise_for_status()
        return r.json()

    async def get_term_effective_parts(self, term_fqn: str, repo_id: Optional[str] = None) -> dict[str, Any]:
        """GET /api/ontology/terms/{fqn}/effective-parts — term 의 part-of 구성요소."""
        params: dict[str, Any] = {}
        if repo_id:
            params["repo_id"] = repo_id
        r = await self._client.get(f"/api/ontology/terms/{term_fqn}/effective-parts", params=params)
        r.raise_for_status()
        return r.json()


# ─── 단일 인스턴스 (FastAPI dependency 용) ────────────────────────

_singleton: Optional[ModelingClient] = None


def get_modeling_client() -> ModelingClient:
    """FastAPI Depends 로 주입. 첫 호출 시 생성, 그 후 재사용."""
    global _singleton
    if _singleton is None:
        _singleton = ModelingClient()
    return _singleton


__all__ = ["ModelingClient", "get_modeling_client"]
