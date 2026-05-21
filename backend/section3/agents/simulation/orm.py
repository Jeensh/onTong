"""시뮬레이션 에이전트 — SQLAlchemy ORM tables (multiturn 과 별도).

multiturn 의 section3_session / section3_decision_log 와 동일 schema 지만
간섭 방지를 위해 별도 테이블로 분리. RFC §7 결정.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.modeling.persistence.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SimulationSessionRow(Base):
    """시뮬레이션 에이전트 세션 — 한 사용자 query 흐름 단위."""

    __tablename__ = "section3_simulation_session"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo_id: Mapped[str] = mapped_column(String, nullable=False)
    intent: Mapped[str | None] = mapped_column(String, nullable=True)
    # MultiturnIntent — simulate/impact/locate/explain/hypothesis/ambiguous
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    # "active" | "done" | "aborted"
    user_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now,
    )


class SimulationDecisionLogRow(Base):
    """시뮬레이션 에이전트 게이트별 결정 — replay 시 hydrate source-of-truth."""

    __tablename__ = "section3_simulation_decision_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("section3_simulation_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_no: Mapped[int] = mapped_column(Integer, nullable=False)
    gate_kind: Mapped[str] = mapped_column(String, nullable=False)
    # GatePayload.kind — multiturn 과 동일 + locate/explain/hypothesis 분기
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    user_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now,
    )

    __table_args__ = (
        Index(
            "ix_sim_decision_log_session_turn",
            "session_id", "turn_no",
        ),
    )


__all__ = [
    "SimulationDecisionLogRow",
    "SimulationSessionRow",
]
