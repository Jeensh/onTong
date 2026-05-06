"""Authoring side adapter — wires `agent_tools` into authoring's session
log + cost log.

Two pieces:

  AuthoringToolLogger
      A `ToolCallLogger` that converts each `ToolCallRecord` into a
      DB row in `authoring_tool_call_log`.

  AuthoringOperationalSession
      An `OperationalSession` that records observations as
      `authoring_decision_log` rows (kind="other") and queues user
      questions on the session's meta.

Capability code uses these via a single helper:

    from backend.application.authoring.agent_tool_adapter import (
        build_run_tracker,
        build_operational_session,
    )

    tracker = build_run_tracker(session_id, turn_no, capability="hypothesis", max_calls=8)
    op_session = build_operational_session(session_id, turn_no, capability="hypothesis")
    register_tools(agent, allowed=preset, tracker=tracker, operational_session=op_session)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.application.agent_tools.operational import OperationalSession
from backend.application.agent_tools.tracking import (
    RunTracker,
    ToolCallLogger,
    ToolCallRecord,
)
from backend.application.authoring import cost as cost_mod
from backend.application.authoring import session as session_mod

logger = logging.getLogger(__name__)


class AuthoringToolLogger:
    """Persists every tool call into `authoring_tool_call_log`."""

    def __init__(self, *, session_id: str, turn_no: int, capability: str) -> None:
        self.session_id = session_id
        self.turn_no = turn_no
        self.capability = capability

    def __call__(self, record: ToolCallRecord) -> None:
        cost_mod.log_tool_call(
            session_id=self.session_id,
            turn_no=self.turn_no,
            capability=self.capability,
            tool_name=record.tool_name,
            args=record.args,
            result_summary=record.result_summary,
            duration_ms=record.duration_ms,
            cached=record.cached,
            error=record.error,
        )


class AuthoringOperationalSession:
    """Implements `OperationalSession` against authoring's decision log.

    `add_observation` writes a decision row (kind="other") so cap 9
    archive can surface what the agent learned. `request_user_input`
    appends to a meta-list on the session; the API layer can read this
    list and surface a "pending question" to the front-end.
    """

    def __init__(self, *, session_id: str, turn_no: int, capability: str) -> None:
        self.session_id = session_id
        self.turn_no = turn_no
        self.capability = capability

    def add_observation(self, *, text: str, kind: str = "observation") -> None:
        try:
            session_mod.add_decision(
                session_id=self.session_id,
                turn_no=self.turn_no,
                step_label=f"{self.capability}:{kind}",
                entity_id=None,
                decision_kind="other",
                payload={"observation": text, "kind": kind},
                archive_markdown=None,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "AuthoringOperationalSession.add_observation failed session=%s",
                self.session_id,
            )

    def request_user_input(
        self, *, question: str, context: str | None = None
    ) -> None:
        try:
            session_mod.add_decision(
                session_id=self.session_id,
                turn_no=self.turn_no,
                step_label=f"{self.capability}:user_question",
                entity_id=None,
                decision_kind="other",
                payload={
                    "question": question,
                    "context": context,
                    "needs_user_answer": True,
                },
                archive_markdown=None,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "AuthoringOperationalSession.request_user_input failed session=%s",
                self.session_id,
            )


def build_run_tracker(
    *, session_id: str, turn_no: int, capability: str, max_calls: int
) -> RunTracker:
    """Convenience constructor for capabilities."""
    return RunTracker(
        max_calls=max_calls,
        logger_fn=AuthoringToolLogger(
            session_id=session_id, turn_no=turn_no, capability=capability
        ),
    )


def build_operational_session(
    *, session_id: str, turn_no: int, capability: str
) -> OperationalSession:
    """Convenience constructor for capabilities."""
    return AuthoringOperationalSession(
        session_id=session_id, turn_no=turn_no, capability=capability
    )


def list_tool_calls_for_session(session_id: str) -> list[dict[str, Any]]:
    """Read-back utility — used by archive markdown rendering and trace UI."""
    from sqlalchemy import select

    from backend.application.authoring.orm import AuthoringToolCallRow
    from backend.modeling.persistence.database import session_scope

    out: list[dict[str, Any]] = []
    with session_scope() as s:
        stmt = (
            select(AuthoringToolCallRow)
            .where(AuthoringToolCallRow.session_id == session_id)
            .order_by(AuthoringToolCallRow.created_at)
        )
        for row in s.execute(stmt).scalars():
            out.append(
                {
                    "turn_no": row.turn_no,
                    "capability": row.capability,
                    "tool_name": row.tool_name,
                    "args": json.loads(row.args_json or "{}"),
                    "result_summary": row.result_summary,
                    "duration_ms": row.duration_ms,
                    "cached": row.cached,
                    "error": row.error,
                    "created_at": row.created_at.isoformat(),
                }
            )
    return out


__all__ = [
    "AuthoringToolLogger",
    "AuthoringOperationalSession",
    "build_run_tracker",
    "build_operational_session",
    "list_tool_calls_for_session",
]
