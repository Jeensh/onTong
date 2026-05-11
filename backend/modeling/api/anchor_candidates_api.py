"""FastAPI router — `GET /api/ontology/code-methods/{method_fqn:path}/anchor-candidates`.

Wave 1 of the AnchorBinding UX overhaul. Returns a deterministic list of
`AnchorCandidate` items derived from `CodeMethodRow.body_text`, so the
frontend can replace the free-text `anchor_locator` input with a typed
dropdown / autocomplete.

Cache strategy
--------------
In-memory LRU keyed by `(repo_id, method_fqn, body_signature)` where the
body signature is `(line_start, line_end, hash(body_text))`. Including
the signature in the key means that re-ingesting a repo with a changed
method body invalidates the cached entry naturally — the new body
produces a different signature, so the next request misses the old
entry and computes fresh candidates. No manual invalidation hook is
needed.

The cache is bounded to 1024 entries (LRU evicts least-recently-used).
At ~100 candidates × 200 bytes per row that is well under 20MB resident.
"""
from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from backend.modeling.code_analysis.anchor_candidate_extractor import (
    AnchorCandidate,
    extract_candidates,
)
from backend.modeling.code_layer.orm import CodeMethodRow
from backend.modeling.persistence.database import session_scope


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/ontology", tags=["ontology-anchor-candidates"])


# ---------------------------------------------------------------------------
# Cache key helper — body signature derives from body_text content + line span.
# ---------------------------------------------------------------------------
def _body_signature(method: CodeMethodRow) -> str:
    body = method.body_text or ""
    digest = hashlib.sha1(body.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{method.line_start}:{method.line_end}:{digest}"


@lru_cache(maxsize=1024)
def _cached_extract(
    cache_key: tuple[str, str, str],          # (repo_id, method_fqn, body_signature)
    body_text: str,
    line_start: int | None,
    line_end: int | None,
    params_json: str,
) -> tuple[AnchorCandidate, ...]:
    """LRU-cached extraction. Args are hashable; the cache key carries the body signature."""
    # Build a lightweight stand-in for `extract_candidates` — it only reads
    # 4 attributes (body_text / line_start / line_end / params_json). Using a
    # SimpleNamespace keeps this fully decoupled from SQLAlchemy session state
    # (which is required to instantiate a real CodeMethodRow safely).
    stub = SimpleNamespace(
        body_text=body_text,
        line_start=line_start,
        line_end=line_end,
        params_json=params_json,
    )
    return tuple(extract_candidates(stub))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Route — `:path` so dotted FQNs (com.example.Foo.bar(...)) flow through unchanged.
# ---------------------------------------------------------------------------
@router.get(
    "/code-methods/{method_fqn:path}/anchor-candidates",
    response_model=list[AnchorCandidate],
)
def get_anchor_candidates(
    method_fqn: str,
    repo_id: str = Query(..., description="repo this method belongs to"),
) -> list[AnchorCandidate]:
    """List dropdown-friendly anchor candidates for a method.

    404 if no matching `(repo_id, method_fqn)` row in `code_methods`.
    """
    with session_scope() as session:
        method = session.execute(
            select(CodeMethodRow).where(
                CodeMethodRow.repo_id == repo_id,
                CodeMethodRow.fqn == method_fqn,
            )
        ).scalar_one_or_none()

        if method is None:
            raise HTTPException(
                status_code=404,
                detail=f"code method not found: repo_id={repo_id!r} fqn={method_fqn!r}",
            )

        sig = _body_signature(method)
        cache_key = (repo_id, method_fqn, sig)
        candidates = _cached_extract(
            cache_key,
            method.body_text or "",
            method.line_start,
            method.line_end,
            method.params_json or "[]",
        )
        return list(candidates)


# ---------------------------------------------------------------------------
# Public testing hook — clears the LRU. Useful for unit tests or after a
# repo re-import if the caller wants to force a refresh without bouncing
# the process.
# ---------------------------------------------------------------------------
def reset_cache() -> None:
    _cached_extract.cache_clear()


__all__ = ("router", "reset_cache")
