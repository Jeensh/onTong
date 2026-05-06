"""Authoring AI — SQLAlchemy ORM tables.

Four tables:
  - authoring_session         : the M-2 branch + operator + entity focus
  - authoring_decision_log    : per-turn decisions (option pick, naming, gap, archive)
  - authoring_cost_log        : per-turn LLM cost (replaces cost.py's ring buffer)
  - authoring_tool_call_log   : per-tool-invocation trace (R6 graph agent tools)

Importing this module registers the tables with `Base.metadata`. main.py imports
this once at startup and `bootstrap_database()` calls `metadata.create_all()`.
No Alembic — same convention as the modeling layer.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.modeling.persistence.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthoringSessionRow(Base):
    """One authoring session = one operator working on one branch."""

    __tablename__ = "authoring_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID4
    branch_name: Mapped[str] = mapped_column(String(120), nullable=False, default="main")
    operator_id: Mapped[str] = mapped_column(String(120), nullable=False, default="default")
    entity_focus: Mapped[str | None] = mapped_column(String(200), nullable=True)
    repo_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # active | paused | merged | abandoned
    meta_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utc_now
    )


class AuthoringDecisionRow(Base):
    """One row per recorded decision within a session.

    A "decision" is anything the user (or system on the user's behalf) commits
    to during an authoring cycle: an option pick, a name confirmation, a gap
    resolution, an archive being saved. The full payload lives as JSON in
    `payload_json`; `archive_markdown` is broken out so we can render it
    directly without re-parsing payload.
    """

    __tablename__ = "authoring_decision_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("authoring_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    decision_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # option_selected | naming_confirmed | gap_resolved | archive_saved | hypothesis_seeded | other
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    archive_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)


class AuthoringCostRow(Base):
    """One row per LLM call. Replaces cost.py's in-memory ring buffer in production."""

    __tablename__ = "authoring_cost_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("authoring_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_no: Mapped[int] = mapped_column(Integer, nullable=False)
    capability: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    model_id: Mapped[str] = mapped_column(String(120), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)


class AuthoringToolCallRow(Base):
    """One row per agent tool invocation (graph lookup, observation, etc.).

    R6 introduces graph-aware ReAct loops. Every tool call (code_lookup,
    domain_search, find_callers, …) is recorded so that:
      - cap 9 archive can render the evidence trail in the markdown
      - cost analysis can attribute graph traffic per session/cap
      - replay / debugging can reconstruct what the agent saw

    Stored shape mirrors `agent_tools.tracking.ToolCallRecord` — the
    cross-cutting transport — plus session FK and cap label.
    """

    __tablename__ = "authoring_tool_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("authoring_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_no: Mapped[int] = mapped_column(Integer, nullable=False)
    capability: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    args_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)


__all__ = [
    "AuthoringSessionRow",
    "AuthoringDecisionRow",
    "AuthoringCostRow",
    "AuthoringToolCallRow",
]
