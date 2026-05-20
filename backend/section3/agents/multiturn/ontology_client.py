"""Section 2 ontology API client — abstraction.

Phase 1: `MockOntologyClient` — in-memory catalog 또는 sim_v2 fallback.
Phase 2: `HTTPOntologyClient` (Section 2 REST API ready 시 swap).

5 endpoint (spec v2 §3):
    - search_action_by_keyword(query, repo_id)
    - get_action_detail(action_id, repo_id)
    - get_method_body(fqn, repo_id)
    - get_entity_schema(entity_name, repo_id)
    - get_caller_graph(method_fqn, repo_id)

모든 method 가 async — sim_v2 sync tool 과의 boundary 는 `tools.py` 에서
`asyncio.to_thread` 로 래핑.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .schemas import (
    ActionCandidate,
    ActionRef,
    AffectedMethod,
    CodeLocation,
    SchemaField,
    SchemaSummary,
)


# ─────────────────────────────────────────────────────────────────────────────
# Protocol
# ─────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class OntologyClient(Protocol):
    """Section 2 API 5 endpoint. Swap-ready (mock / http)."""

    async def search_action_by_keyword(
        self, query: str, *, repo_id: str, top_n: int = 5,
    ) -> list[ActionCandidate]: ...

    async def get_action_detail(
        self, action_id: str, *, repo_id: str,
    ) -> ActionRef | None: ...

    async def get_method_body(
        self, fqn: str, *, repo_id: str,
    ) -> str | None: ...

    async def get_entity_schema(
        self, entity_name: str, *, repo_id: str,
    ) -> SchemaSummary | None: ...

    async def get_caller_graph(
        self, method_fqn: str, *, repo_id: str,
    ) -> list[AffectedMethod]: ...


# ─────────────────────────────────────────────────────────────────────────────
# MockOntologyClient — in-memory catalog (test + Phase 1 demo)
# ─────────────────────────────────────────────────────────────────────────────


class MockOntologyClient:
    """In-memory catalog 기반. test fixture 와 Phase 1 demo 에 사용.

    catalog schema:
        {
          "actions": [
            {"action_id", "label", "code_method_fqn", "aliases",
             "repo_id", "location": {...}}
          ],
          "method_bodies": {"<fqn>": "<java source>"},
          "entity_schemas": {"<entity_name>": {entity_name, fields: [...]}},
          "caller_graphs": {"<fqn>": [{"fqn", "distance", "via"}, ...]},
        }

    Empty catalog ({}) 도 안전 — Q5 비전 "빠진 내용은 빠진대로".
    """

    def __init__(self, *, catalog: dict[str, Any] | None = None) -> None:
        self._catalog = catalog or {}

    async def search_action_by_keyword(
        self, query: str, *, repo_id: str, top_n: int = 5,
    ) -> list[ActionCandidate]:
        actions = self._catalog.get("actions") or []
        q = query.lower()
        out: list[tuple[float, ActionCandidate]] = []
        for a in actions:
            if a.get("repo_id") != repo_id:
                continue
            score = _match_score(q, a)
            if score <= 0:
                continue
            out.append((score, ActionCandidate(
                action_id=a["action_id"],
                label=a["label"],
                score=score,
                code_method_fqn=a["code_method_fqn"],
                aliases=list(a.get("aliases") or []),
            )))
        out.sort(key=lambda x: -x[0])
        return [c for _, c in out[:top_n]]

    async def get_action_detail(
        self, action_id: str, *, repo_id: str,
    ) -> ActionRef | None:
        for a in self._catalog.get("actions") or []:
            if a["action_id"] == action_id and a.get("repo_id") == repo_id:
                loc = a.get("location") or {}
                return ActionRef(
                    action_id=a["action_id"],
                    code_method_fqn=a["code_method_fqn"],
                    repo_id=repo_id,
                    location=CodeLocation(
                        file_path=loc.get("file_path", ""),
                        line_start=loc.get("line_start", 0),
                        line_end=loc.get("line_end", 0),
                    ),
                )
        return None

    async def get_method_body(
        self, fqn: str, *, repo_id: str,
    ) -> str | None:
        return (self._catalog.get("method_bodies") or {}).get(fqn)

    async def get_entity_schema(
        self, entity_name: str, *, repo_id: str,
    ) -> SchemaSummary | None:
        raw = (self._catalog.get("entity_schemas") or {}).get(entity_name)
        if raw is None:
            return None
        return SchemaSummary(
            entity_name=raw.get("entity_name", entity_name),
            fields=[SchemaField(**f) for f in raw.get("fields") or []],
        )

    async def get_caller_graph(
        self, method_fqn: str, *, repo_id: str,
    ) -> list[AffectedMethod]:
        rows = (self._catalog.get("caller_graphs") or {}).get(method_fqn) or []
        return [AffectedMethod(**r) for r in rows]


def _match_score(q: str, action: dict[str, Any]) -> float:
    """토큰 단위 substring 매칭 — query 가 label 보다 길 때도 동작.

    1) full query → label/aliases/fqn 내 substring → 가중치 ↑
    2) query 토큰 (whitespace 분할, len≥2) → 각 토큰이 substring 인지
       (label > aliases > fqn 가중치)
    score 가 0 이면 후보에서 제외.
    """
    label = (action.get("label") or "").lower()
    fqn = (action.get("code_method_fqn") or "").lower()
    aliases = [a.lower() for a in action.get("aliases") or []]

    score = 0.0
    if q and q in label:
        score += 3.0
    elif q and any(q in a for a in aliases):
        score += 2.5
    elif q and q in fqn:
        score += 2.0

    tokens = [t for t in q.split() if len(t) >= 2]
    for tok in tokens:
        if tok in label:
            score += 1.5
        elif any(tok in a for a in aliases):
            score += 1.0
        elif tok in fqn:
            score += 0.75

    return score


# ─────────────────────────────────────────────────────────────────────────────
# HTTPOntologyClient — Phase 2 swap (Section 2 REST API 준비되면)
# ─────────────────────────────────────────────────────────────────────────────


class HybridOntologyClient:
    """Section 2 HTTP API + sim_v2 fallback (Phase 4).

    sec2 가 노출하는 endpoint 2 개는 httpx wire:
      - search_action_by_keyword → GET /api/ontology/search?q=&repo_id=&limit=
      - get_action_detail        → GET /api/ontology/actions/{fqn}

    나머지 3 개는 sec2 API 에 endpoint 없으므로 SimV2BackedOntologyClient delegate:
      - get_method_body, get_entity_schema, get_caller_graph

    Q5 비전: sec2 측 endpoint 추가되면 점진적으로 fallback 에서 옮겨감.
    """

    def __init__(
        self,
        *,
        base_url: str,
        http_client: "httpx.AsyncClient | None" = None,
        fallback: OntologyClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        import httpx as _httpx
        self.base_url = base_url.rstrip("/")
        self._http = http_client or _httpx.AsyncClient(
            base_url=self.base_url, timeout=timeout,
        )
        self._fallback: OntologyClient = fallback or SimV2BackedOntologyClient()

    async def search_action_by_keyword(
        self, query: str, *, repo_id: str, top_n: int = 5,
    ) -> list[ActionCandidate]:
        try:
            resp = await self._http.get(
                "/api/ontology/search",
                params={"q": query, "repo_id": repo_id, "limit": top_n},
            )
            if resp.status_code != 200:
                return []
            raw = resp.json()
        except Exception:  # noqa: BLE001 — Q5: sec2 API 불안정해도 surface 안 멈춤
            return []
        hits = [h for h in raw if h.get("kind") == "action"]
        out: list[ActionCandidate] = []
        for h in hits:
            out.append(ActionCandidate(
                action_id=str(h.get("fqn", "")),
                label=str(h.get("label", "")),
                score=float(h.get("score", 0.0)),
                code_method_fqn="",   # search 결과엔 미포함 — 후속 get_action_detail 시 보강
                aliases=[],
            ))
        return out

    async def get_action_detail(
        self, action_id: str, *, repo_id: str,
    ) -> ActionRef | None:
        from urllib.parse import quote
        try:
            resp = await self._http.get(
                f"/api/ontology/actions/{quote(action_id, safe='')}",
            )
            if resp.status_code == 404:
                return None
            if resp.status_code != 200:
                return None
            raw = resp.json()
            if raw is None:
                return None
        except Exception:  # noqa: BLE001
            return None
        realizations = raw.get("realizations") or []
        code_method_fqn = ""
        if realizations:
            primary = next(
                (r for r in realizations if r.get("scope") == "primary"),
                realizations[0],
            )
            code_method_fqn = str(primary.get("code_method_fqn", ""))
        return ActionRef(
            action_id=str(raw.get("fqn", action_id)),
            code_method_fqn=code_method_fqn,
            repo_id=repo_id,
            location=_empty_location(),
        )

    async def get_method_body(
        self, fqn: str, *, repo_id: str,
    ) -> str | None:
        """sec2 `/api/ontology/code-methods/{fqn}/body` (Phase 4 추가 endpoint).

        sec2 가 404 또는 빈 body 반환 시 → sim_v2 fallback.
        """
        from urllib.parse import quote
        try:
            resp = await self._http.get(
                f"/api/ontology/code-methods/{quote(fqn, safe='')}/body",
            )
            if resp.status_code == 200:
                body = (resp.json() or {}).get("body_text") or ""
                if body:
                    return body
        except Exception:  # noqa: BLE001
            pass
        return await self._fallback.get_method_body(fqn, repo_id=repo_id)

    async def get_method_meta(
        self, fqn: str, *, repo_id: str,
    ) -> dict | None:
        """Phase 11 — body endpoint 의 line_start/line_end/return_type 추출.

        Hybrid 만 구현. 다른 client 들은 없음 (caller 가 hasattr 로 분기).
        파일 경로는 fqn → 디렉토리 변환으로 derive (sec2 가 별도 surface 안 함).
        """
        from urllib.parse import quote
        try:
            resp = await self._http.get(
                f"/api/ontology/code-methods/{quote(fqn, safe='')}/body",
            )
            if resp.status_code != 200:
                return None
            raw = resp.json() or {}
            line_start = int(raw.get("line_start", 0) or 0)
            line_end = int(raw.get("line_end", 0) or 0)
            return_type = str(raw.get("return_type", "") or "")
            # fqn → java path. e.g. com.example.X.foo(Y) → com/example/X.java
            head = fqn.split("(", 1)[0]
            class_fqn = head.rsplit(".", 1)[0] if "." in head else head
            file_path = class_fqn.replace(".", "/") + ".java"
            return {
                "file_path": file_path,
                "line_start": line_start,
                "line_end": line_end,
                "return_type": return_type,
            }
        except Exception:  # noqa: BLE001
            return None

    async def get_entity_schema(
        self, entity_name: str, *, repo_id: str,
    ) -> SchemaSummary | None:
        """sec2 `/api/ontology/entities/{name}/schema` (Phase 4 추가 endpoint).

        404 / 에러 시 → fallback.
        """
        from urllib.parse import quote
        try:
            params = {"repo_id": repo_id} if repo_id else None
            resp = await self._http.get(
                f"/api/ontology/entities/{quote(entity_name, safe='')}/schema",
                params=params,
            )
            if resp.status_code == 200:
                raw = resp.json() or {}
                fields = [
                    SchemaField(
                        name=f.get("name", ""),
                        type_name=f.get("type_name", ""),
                        nullable=bool(f.get("nullable", False)),
                    )
                    for f in (raw.get("fields") or [])
                ]
                return SchemaSummary(
                    entity_name=raw.get("entity_name", entity_name),
                    fields=fields,
                )
        except Exception:  # noqa: BLE001
            pass
        return await self._fallback.get_entity_schema(
            entity_name, repo_id=repo_id,
        )

    async def get_caller_graph(
        self, method_fqn: str, *, repo_id: str,
    ) -> list[AffectedMethod]:
        """sec2 `/api/ontology/code-methods/{fqn}/callers` (Phase 4 추가 endpoint).

        sec2 미응답 또는 에러 시 → fallback.
        """
        from urllib.parse import quote
        try:
            params = {"repo_id": repo_id} if repo_id else None
            resp = await self._http.get(
                f"/api/ontology/code-methods/{quote(method_fqn, safe='')}/callers",
                params=params,
            )
            if resp.status_code == 200:
                raw = resp.json() or {}
                callers = raw.get("callers") or []
                return [
                    AffectedMethod(
                        fqn=c.get("fqn", ""),
                        distance=int(c.get("distance", 1)),
                        via=c.get("via", "direct_caller"),
                        match_kind=c.get("match_kind"),
                        strength=c.get("strength"),
                    )
                    for c in callers
                ]
        except Exception:  # noqa: BLE001
            pass
        return await self._fallback.get_caller_graph(
            method_fqn, repo_id=repo_id,
        )


# Backward-compat alias — 옛 NotImplemented 스텁 이름 유지
HTTPOntologyClient = HybridOntologyClient


# ─────────────────────────────────────────────────────────────────────────────
# SimV2BackedOntologyClient — Phase 2 production default
# ─────────────────────────────────────────────────────────────────────────────


class SimV2BackedOntologyClient:
    """`backend/section3/sim_v2_bridge` 를 데이터 소스로 사용하는 production client.

    Section 2 REST API 가 준비되기 전까지의 임시 데이터 경로:
      - get_method_body → sim_v2_bridge.load_body_text (ontology.db 의 code_methods)
      - get_action_detail → sim_v2_bridge.load_action (있으면 ActionRef 변환)
      - search/entity_schema/caller_graph → 미지원 ("빠진 내용은 빠진대로")

    Q5 비전: 데모는 sim_v2 가 보유한 실데이터로 진행, 나머지는 빈 결과.
    """

    async def search_action_by_keyword(
        self, query: str, *, repo_id: str, top_n: int = 5,
    ) -> list[ActionCandidate]:
        # search 는 Gate I 의 sim_v2.find_action_candidates 가 이미 담당. 중복 피함.
        return []

    async def get_action_detail(
        self, action_id: str, *, repo_id: str,
    ) -> ActionRef | None:
        import asyncio

        def _run():
            from backend.section3 import sim_v2_bridge as sb
            s = sb.open_sim_v2_session()
            if s is None:
                return None
            try:
                return sb.load_action(s, action_id, repo_id)
            finally:
                s.close()

        action = await asyncio.to_thread(_run)
        if action is None:
            return None
        code_method_fqn = getattr(action, "code_method_fqn", None) or ""
        return ActionRef(
            action_id=action_id,
            code_method_fqn=code_method_fqn,
            repo_id=repo_id,
            location=_empty_location(),
        )

    async def get_method_body(
        self, fqn: str, *, repo_id: str,
    ) -> str | None:
        import asyncio

        def _run():
            from backend.section3 import sim_v2_bridge as sb
            s = sb.open_sim_v2_session()
            if s is None:
                return None
            try:
                return sb.load_body_text(s, fqn, repo_id)
            finally:
                s.close()

        return await asyncio.to_thread(_run)

    async def get_entity_schema(
        self, entity_name: str, *, repo_id: str,
    ) -> SchemaSummary | None:
        return None  # Phase 4 에서 sec2 API + ontology entity schema

    async def get_method_meta(
        self, fqn: str, *, repo_id: str,
    ) -> dict | None:
        """Phase 13a — code_methods row → file_path / line / return_type.

        executed_lookup 의 file_path / line_start / line_end / return_type 채우는
        용도. 이전엔 HybridOntologyClient 만 보유했으나 SimV2-only client 사용 시
        모두 빈 값 surface 되던 문제 해결.
        """
        import asyncio

        def _run() -> dict | None:
            from sqlalchemy import select as _select
            from backend.modeling.persistence.database import session_scope
            from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow

            with session_scope() as s:
                method = s.execute(
                    _select(CodeMethodRow).where(
                        CodeMethodRow.fqn == fqn,
                        CodeMethodRow.repo_id == repo_id,
                    ),
                ).scalar_one_or_none()
                if method is None:
                    return None
                parent = s.execute(
                    _select(CodeTypeRow).where(
                        CodeTypeRow.fqn == method.parent_type_fqn,
                    ),
                ).scalar_one_or_none()
            return {
                "file_path": (parent.source_file if parent else "") or "",
                "line_start": int(method.line_start or 0),
                "line_end":   int(method.line_end or 0),
                "return_type": method.return_type or "",
            }

        try:
            return await asyncio.to_thread(_run)
        except Exception:  # noqa: BLE001
            return None

    async def get_caller_graph(
        self, method_fqn: str, *, repo_id: str,
    ) -> list[AffectedMethod]:
        """SQLite ontology.db 직접 query — Section 2 의 store + match_kind heuristic 활용.

        Phase 12 Activation — 이전 stub `return []` 가 Gate III impact 의 affected_methods
        를 항상 빈 배열로 만들어 confidence 1.0 surface 되는 오해 유발했음.
        sec2 `/code-methods/{fqn}/callers` endpoint 와 동일 로직.
        """
        import asyncio

        def _run() -> list[AffectedMethod]:
            from backend.modeling.code_layer.store import CodeLayerStore
            from backend.modeling.api.ontology_router import _MATCH_STRENGTH

            store = CodeLayerStore()
            pairs = store.get_method_callers_with_match(method_fqn, repo_id=repo_id)
            # 같은 caller 중복 — 가장 강한 match 만 keep
            by_caller: dict[str, tuple[object, str]] = {}
            for cs, mk in pairs:
                prev = by_caller.get(cs.caller_method_fqn)
                if (prev is None
                        or _MATCH_STRENGTH.get(mk, 0.0)
                        > _MATCH_STRENGTH.get(prev[1], 0.0)):
                    by_caller[cs.caller_method_fqn] = (cs, mk)

            out: list[AffectedMethod] = []
            for fqn, (cs, mk) in by_caller.items():
                src = (
                    cs.analysis_source if isinstance(cs.analysis_source, str)
                    else getattr(cs.analysis_source, "value", str(cs.analysis_source))
                )
                via = ("interface_impl"
                       if ("interface" in src or "impl" in src)
                       else "direct_caller")
                out.append(AffectedMethod(
                    fqn=fqn,
                    distance=1,
                    via=via,
                    match_kind=mk,
                    strength=_MATCH_STRENGTH.get(mk, 0.0),
                ))
            # 강한 신호 먼저
            out.sort(key=lambda a: -(a.strength or 0.0))
            return out

        try:
            return await asyncio.to_thread(_run)
        except Exception:  # noqa: BLE001
            # graceful — DB 미가용 등에서 종전처럼 빈 배열
            return []


def _empty_location():
    from .schemas import CodeLocation
    return CodeLocation(file_path="", line_start=0, line_end=0)


__all__ = [
    "HTTPOntologyClient",
    "HybridOntologyClient",
    "MockOntologyClient",
    "OntologyClient",
    "SimV2BackedOntologyClient",
]
