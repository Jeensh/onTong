"""Authoring AI — cost logger.

Two-layer storage:
  - In-memory ring buffer: cheap, always-on, used by unit tests + the
    "current session" cost summary while the LLM is mid-flight.
  - DB row in `authoring_cost_log`: persisted iff the call references a
    real session (one created via `session.create_session`). Sessions
    that don't exist in the DB (most unit tests) skip the DB write
    silently — keeping the existing test suite working unchanged.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.exc import IntegrityError

from backend.application.authoring.orm import AuthoringCostRow, AuthoringToolCallRow
from backend.application.authoring.schemas import (
    CostRecord,
    ModelTier,
    TokenUsage,
    estimate_cost_usd,
)
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)

# Ring buffer of the most recent N records — used by unit tests and as a
# fast path for fetching the current session's running total.
_BUFFER_MAX = 1000
_recent: deque[CostRecord] = deque(maxlen=_BUFFER_MAX)


def _persist_to_db(rec: CostRecord) -> bool:
    """Append the cost row to the DB. Returns True on success.

    Returns False (and logs at DEBUG) if the session_id has no matching row
    in `authoring_session` — this happens in unit tests that pass arbitrary
    session ids to exercise the in-memory buffer without bootstrapping a DB.
    """
    try:
        with session_scope() as s:
            s.add(
                AuthoringCostRow(
                    session_id=rec.session_id,
                    turn_no=rec.turn_no,
                    capability=rec.capability,
                    tier=rec.tier.value,
                    model_id=rec.model_id,
                    input_tokens=rec.usage.input_tokens,
                    output_tokens=rec.usage.output_tokens,
                    cache_read_tokens=rec.usage.cache_read_tokens,
                    cache_write_tokens=rec.usage.cache_write_tokens,
                    cost_usd=rec.cost_usd,
                    duration_ms=rec.duration_ms,
                    cache_hit=rec.cache_hit,
                    created_at=rec.created_at,
                )
            )
        return True
    except IntegrityError:
        # FK violation: session_id is not in authoring_session. Fine for tests.
        logger.debug(
            "authoring.cost db skip — session %s not registered", rec.session_id
        )
        return False
    except Exception:  # noqa: BLE001 — DB outage must not break the LLM call
        logger.exception("authoring.cost db write failed for session=%s", rec.session_id)
        return False


def log_call(
    *,
    session_id: str,
    turn_no: int,
    capability: str,
    tier: ModelTier,
    model_id: str,
    usage: TokenUsage,
    duration_ms: int = 0,
) -> CostRecord:
    """Record one LLM call. Returns the persisted CostRecord."""
    model_short = model_id.split("/", 1)[1] if "/" in model_id else model_id
    cost = estimate_cost_usd(model_short, usage)
    cache_hit = usage.cache_read_tokens > 0
    rec = CostRecord(
        session_id=session_id,
        turn_no=turn_no,
        capability=capability,
        tier=tier,
        model_id=model_id,
        usage=usage,
        cost_usd=cost,
        duration_ms=duration_ms,
        cache_hit=cache_hit,
    )
    _recent.append(rec)
    persisted = _persist_to_db(rec)
    logger.info(
        "authoring.cost session=%s turn=%d cap=%s tier=%s model=%s "
        "in=%d out=%d cache_r=%d cache_w=%d cost=$%.5f dur=%dms hit=%s db=%s",
        session_id,
        turn_no,
        capability,
        tier.value,
        model_short,
        usage.input_tokens,
        usage.output_tokens,
        usage.cache_read_tokens,
        usage.cache_write_tokens,
        cost,
        duration_ms,
        cache_hit,
        "ok" if persisted else "skip",
    )
    return rec


def session_total_usd(session_id: str) -> float:
    """Sum of in-memory cost for a session. S5 will switch to DB query."""
    return round(sum(r.cost_usd for r in _recent if r.session_id == session_id), 6)


def session_records(session_id: str) -> list[CostRecord]:
    return [r for r in _recent if r.session_id == session_id]


def reset_buffer() -> None:
    """Test helper — clear the in-memory buffer."""
    _recent.clear()


@contextmanager
def measure() -> Iterator[dict]:
    """Time a block and surface elapsed_ms in the yielded dict.

    Usage:
        with measure() as t:
            result = await agent.run(...)
        log_call(..., duration_ms=t["elapsed_ms"], ...)
    """
    started = time.perf_counter()
    state: dict = {}
    try:
        yield state
    finally:
        state["elapsed_ms"] = int((time.perf_counter() - started) * 1000)


# ── Tool call trace (R6 graph agent) ─────────────────────────────────


def log_tool_call(
    *,
    session_id: str,
    turn_no: int,
    capability: str,
    tool_name: str,
    args: dict,
    result_summary: str,
    duration_ms: int,
    cached: bool,
    error: str | None,
) -> bool:
    """Persist one agent tool call. Returns True on DB write success.

    Like `_persist_to_db(...)` for cost rows, this swallows FK violations
    so that ad-hoc test sessions (no FK row) don't blow up the agent loop.
    """
    import json

    try:
        with session_scope() as s:
            s.add(
                AuthoringToolCallRow(
                    session_id=session_id,
                    turn_no=turn_no,
                    capability=capability,
                    tool_name=tool_name,
                    args_json=json.dumps(args, ensure_ascii=False, default=str)[:4000],
                    result_summary=result_summary[:1000],
                    duration_ms=duration_ms,
                    cached=cached,
                    error=error[:500] if error else None,
                )
            )
        return True
    except IntegrityError:
        logger.debug(
            "authoring.tool_call db skip — session %s not registered", session_id
        )
        return False
    except Exception:  # noqa: BLE001 — DB outage must not break the agent run
        logger.exception(
            "authoring.tool_call db write failed for session=%s tool=%s",
            session_id,
            tool_name,
        )
        return False
