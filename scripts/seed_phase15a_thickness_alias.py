"""Phase 15A — seed thickness BusinessTerm + correct SdThicknessAction.declared_on_term.

페르소나 검증 (시니어 14E): "두께 검증 시뮬" 의 silent wrong target 원인 — modeling
시드에 한·영 alias term 없음 + action 이 잘못된 term 으로 매핑.

이 스크립트는 멱등 (다시 돌려도 안전):
  1. BusinessTerm `term.scm.thickness` (label="두께" + aliases) upsert
  2. action.scm.thickness_실행.declared_on_term 을 `term.scm.order.order` →
     `term.scm.thickness` 로 정정 (단, term.scm.order.order 에 매핑된 다른 action 은
     유지 — 두께 action 만 수정)

사용: `python scripts/seed_phase15a_thickness_alias.py [--dry-run]`
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from backend.modeling.persistence.database import session_scope
from backend.modeling.domain_layer.orm import BusinessTermRow
from backend.modeling.mapping_layer.orm import ActionRow


THICKNESS_TERM_FQN = "term.scm.thickness"
THICKNESS_LABEL = "두께"
THICKNESS_ALIASES_JSON = (
    '["thickness", "Thickness", "thk", "slab thickness", "두께값"]'
)
REPO_ID = "slab-design-real-v2"

THICKNESS_ACTION_FQN = "action.scm.thickness_실행"
WRONG_OLD_TERM = "term.scm.order.order"
CORRECTED_TERM = THICKNESS_TERM_FQN


def run(dry_run: bool = False) -> None:
    with session_scope() as s:
        # 1) BusinessTerm upsert (idempotent)
        existing = s.execute(
            select(BusinessTermRow).where(
                BusinessTermRow.fqn == THICKNESS_TERM_FQN,
                BusinessTermRow.repo_id == REPO_ID,
            ),
        ).scalar_one_or_none()

        if existing is None:
            print(f"[ADD] BusinessTerm {THICKNESS_TERM_FQN} (label={THICKNESS_LABEL!r})")
            if not dry_run:
                s.add(BusinessTermRow(
                    fqn=THICKNESS_TERM_FQN,
                    label=THICKNESS_LABEL,
                    aliases_json=THICKNESS_ALIASES_JSON,
                    kind="atomic",   # TermKind enum 은 atomic|composite 만 valid
                    domain="scm",
                    description="슬라브 두께 (slab thickness) — 한·영 alias bridge",
                    is_abstract=False,
                    is_interface=False,
                    is_root_entity=False,
                    struct_like_hint=False,
                    confirmed=True,
                    repo_id=REPO_ID,
                    source="user",   # Literal["manual"|"auto"|"llm"|"user"] 만 valid
                ))
        else:
            # 이미 존재 — alias 갱신만 (필요 시)
            if existing.aliases_json != THICKNESS_ALIASES_JSON:
                print(f"[UPDATE] BusinessTerm {THICKNESS_TERM_FQN} aliases")
                if not dry_run:
                    existing.aliases_json = THICKNESS_ALIASES_JSON
                    existing.confirmed = True
            else:
                print(f"[SKIP] BusinessTerm {THICKNESS_TERM_FQN} 이미 일치")

        # 2) Action.declared_on_term 정정 (thickness_실행 만)
        action = s.execute(
            select(ActionRow).where(
                ActionRow.fqn == THICKNESS_ACTION_FQN,
                ActionRow.repo_id == REPO_ID,
            ),
        ).scalar_one_or_none()

        if action is None:
            print(f"[WARN] Action {THICKNESS_ACTION_FQN} 없음 — skip")
        else:
            current = action.declared_on_term
            if current == CORRECTED_TERM:
                print(f"[SKIP] Action {THICKNESS_ACTION_FQN}.declared_on_term 이미 정정됨")
            elif current == WRONG_OLD_TERM or current is None:
                print(
                    f"[UPDATE] Action {THICKNESS_ACTION_FQN}.declared_on_term "
                    f"{current!r} → {CORRECTED_TERM!r}"
                )
                if not dry_run:
                    action.declared_on_term = CORRECTED_TERM
            else:
                # 예상 못한 값 — 사용자 결정 영역. 변경 안 함.
                print(
                    f"[SKIP-UNEXPECTED] Action {THICKNESS_ACTION_FQN}.declared_on_term="
                    f"{current!r} (예상={WRONG_OLD_TERM!r} 또는 None) — 수동 검토 필요"
                )

        if dry_run:
            print("\n[DRY-RUN] 변경 사항 commit X")
            s.rollback()
        else:
            s.commit()
            print("\n[OK] commit 완료")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="변경 사항 미적용")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
