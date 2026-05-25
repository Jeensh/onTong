"""Phase 16Q — 추가 production action declared_on_term 시드 (idempotent).

15C 에서 90 None actions 중 12 정정. 79 잔여 분석 (16Q):
  - 대부분 test fixtures (@Test annotation 보유) → 시드 X (W4 target_is_test 위험)
  - 명확한 매핑이 가능한 4 production action 만 시드

명확 매핑 (single realization + 명백한 도메인):
  - action.scm.find_group → term.scm.edging_group (EdgingService.findGroup)
  - action.scm.product.lookup_or_default → term.scm.product.productivity_std (ProductivityService.lookupOrDefault)
  - action.scm.order.extract_designable_orders → term.scm.order.order (SdOrderExtractor.extractDesignableOrders)
  - action.scm.batch_design__driver → term.scm.order.order (SdDriver.batchDesign)

회피한 케이스:
  - find_spec (5 realizations 폴리몰픽 — 단일 term 매핑 불가)
  - dg00*_returns_fail (테스트 메서드, @Test 보유)
  - product.classify_by_product_code (product_kind/classification term 모호)
  - slab.create_initial_slab (slab_count vs slab 모호)

사용: `python scripts/seed_phase16q_additional_declared_on_term.py [--dry-run]`
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from backend.modeling.persistence.database import session_scope
from backend.modeling.mapping_layer.orm import ActionRow


REPO_ID = "slab-design-real-v2"

SEEDS = [
    ("action.scm.find_group", "term.scm.edging_group"),
    ("action.scm.product.lookup_or_default", "term.scm.product.productivity_std"),
    ("action.scm.order.extract_designable_orders", "term.scm.order.order"),
    ("action.scm.batch_design__driver", "term.scm.order.order"),
]


def run(dry_run: bool = False) -> None:
    changed = 0
    unchanged = 0
    not_found = 0

    with session_scope() as s:
        for action_fqn, term_fqn in SEEDS:
            row = s.execute(
                select(ActionRow).where(
                    ActionRow.fqn == action_fqn,
                    ActionRow.repo_id == REPO_ID,
                ),
            ).scalar_one_or_none()

            if row is None:
                print(f"[MISS] {action_fqn} not found")
                not_found += 1
                continue

            if row.declared_on_term == term_fqn:
                print(f"[SKIP] {action_fqn} already → {term_fqn}")
                unchanged += 1
                continue

            if row.declared_on_term is not None:
                print(
                    f"[KEEP] {action_fqn} already declared_on_term={row.declared_on_term!r} "
                    f"(no override)",
                )
                unchanged += 1
                continue

            print(f"[SET ] {action_fqn} → {term_fqn}")
            changed += 1
            if not dry_run:
                row.declared_on_term = term_fqn

    print()
    print(
        f"Summary: {changed} set, {unchanged} unchanged, {not_found} not_found"
    )
    if dry_run:
        print("(dry-run — no changes committed)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
