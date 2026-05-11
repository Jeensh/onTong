"""SQLAlchemy ORM — Audit Log (modeling section PATCH/confirm tracking).

설계:
- 한 row = (entity, field) 단위 변경 1건
  - field=NULL → 전체 entity 단위 액션 (confirm / unconfirm / created / deleted)
  - field=str → inline patch 의 단일 field 변경
- repo_id, entity_kind, entity_id 별 인덱싱 → 100K+ row 가정해도 빠른 조회
- ts 단독 인덱스 + (entity_kind, entity_id, ts DESC) compound 인덱스
  - "이 entity 의 최근 이력 N건" 쿼리가 가장 자주 들어옴 → DESC 정렬 인덱스

before/after 는 string JSON. 부분 dict 만 저장 (변경된 field 만) — 100K row × 전체 snapshot
은 디스크 폭발. 전체 snapshot 이 필요하면 별도 snapshot 테이블 추가 (현재 미설계).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.modeling.persistence.database import Base


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    repo_id:     Mapped[str] = mapped_column(String, nullable=False, default="", index=True)

    # term / action / rule / anchor / code_type
    entity_kind: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # fqn (term/action/rule/code_type) 또는 anchor id
    entity_id:   Mapped[str] = mapped_column(String, nullable=False, index=True)

    # NULL = entity-level action (confirm / unconfirm / created / deleted)
    # set  = inline patch 의 변경 field 이름
    field:       Mapped[str | None] = mapped_column(String, nullable=True)

    # JSON 직렬화 (string). 변경된 field 부분 dict 만 — 전체 snapshot 아님.
    before_json: Mapped[str] = mapped_column(Text, nullable=False, default="null")
    after_json:  Mapped[str] = mapped_column(Text, nullable=False, default="null")

    # patched / confirmed / unconfirmed / created / deleted
    action:      Mapped[str] = mapped_column(String, nullable=False)

    user_id:     Mapped[str | None] = mapped_column(String, nullable=True)

    ts:          Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        # "이 entity 의 최근 N건" 쿼리 최적화
        Index(
            "ix_audit_log_entity_ts",
            "entity_kind", "entity_id", "ts",
        ),
        # repo 단위 recent feed 쿼리 최적화
        Index(
            "ix_audit_log_repo_ts",
            "repo_id", "ts",
        ),
    )


__all__ = ("AuditLogRow",)
