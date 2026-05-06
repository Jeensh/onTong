"""Operational tools — agent ↔ host (session) interactions.

Unlike code/ontology/mapping tools (pure read-only graph queries), these
need a session-shaped object on the host. Hosts implement the
`OperationalSession` Protocol; the Authoring layer provides one such impl
that writes to `authoring_decision_log`.

Why a Protocol: keeping `agent_tools` cross-cutting means it cannot import
from `authoring`. Each agent (Authoring, RAG agents, etc.) supplies its
own session adapter via `register_tools(operational_session=...)`.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class OperationalSession(Protocol):
    """Host-supplied callbacks for operational tools.

    Implementations may be no-ops in tests / non-interactive agents.
    """

    def add_observation(self, *, text: str, kind: str = "observation") -> None:
        """Record an LLM-derived fact in the host session log."""

    def request_user_input(
        self, *, question: str, context: str | None = None
    ) -> None:
        """Pause exploration and ask the user a clarification question.

        Implementations typically push a "pending question" on the session
        so the front-end can surface it. The agent gets no immediate reply
        — it should produce its best-effort output and stop.
        """


class NullOperationalSession:
    """No-op default — used when an agent doesn't need operational tools."""

    def add_observation(self, *, text: str, kind: str = "observation") -> None:
        logger.debug("agent_tools.NullOperationalSession.add_observation: %s", text)

    def request_user_input(
        self, *, question: str, context: str | None = None
    ) -> None:
        logger.debug(
            "agent_tools.NullOperationalSession.request_user_input: %s", question
        )


def make_note_observation(session: OperationalSession):
    def note_observation(*, text: str, kind: str = "observation") -> dict[str, Any]:
        """Record a fact you discovered during exploration.

        Use this for non-trivial findings the user should see in the trace —
        "HrPlantConstraint shares PK with HrPlant", "applyConstraint() body
        validates Thk/Wid range", etc. Don't use it for trivial steps.
        """
        session.add_observation(text=text, kind=kind)
        return {"recorded": True, "text": text[:200]}

    return note_observation


def make_request_user_input(session: OperationalSession):
    def request_user_input(
        *, question: str, context: str | None = None
    ) -> dict[str, Any]:
        """Pause and ask the user a clarification when graph evidence is
        insufficient. Use sparingly — prefer answering with stated assumptions.
        """
        session.request_user_input(question=question, context=context)
        return {
            "queued": True,
            "question": question[:200],
            "note": (
                "User input requested. You will not get an answer this run; "
                "produce your best-effort output now and explicitly call out "
                "the assumption that prompted this question."
            ),
        }

    return request_user_input


ALL_OPERATIONAL_TOOLS = ("note_observation", "request_user_input")


__all__ = [
    "OperationalSession",
    "NullOperationalSession",
    "make_note_observation",
    "make_request_user_input",
    "ALL_OPERATIONAL_TOOLS",
]
