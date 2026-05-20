"""Section 3 multiturn — SQLAlchemy ORM tables.

Two tables:
  - section3_session         : 한 사용자 자연어 query 의 흐름 단위
  - section3_decision_log    : per-turn gate decision (target / bundle / executed)

Importing this module registers tables with `Base.metadata`. main.py imports
this once at startup and `bootstrap_database()` calls `metadata.create_all()`.
No Alembic — same convention as authoring (CHAT_REDESIGN_SPEC.md v2 §5).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.modeling.persistence.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Section3SessionRow(Base):
    """한 사용자 자연어 query → 3 게이트 흐름 단위."""

    __tablename__ = "section3_session"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    # "active" | "done" | "blocked"
    user_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now,
    )


class Section3DecisionLogRow(Base):
    """게이트별 결정 — source-of-truth (replay 시 hydrate, sim_v2 재호출 X)."""

    __tablename__ = "section3_decision_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("section3_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_no: Mapped[int] = mapped_column(Integer, nullable=False)
    gate_kind: Mapped[str] = mapped_column(String, nullable=False)
    # GatePayload.kind: "target_selected" | "bundle_prepared"
    # | "executed_simulation" | "executed_impact"
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    user_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now,
    )

    __table_args__ = (
        Index("ix_section3_decision_log_session_turn", "session_id", "turn_no"),
    )


__all__ = [
    "Section3DecisionLogRow",
    "Section3SessionRow",
]
