"""Phase 15C — fill declared_on_term for actions with None + add small terms.

PM 15B 검증 + 데이터 인벤토리 발견:
  - 90 actions 가 `declared_on_term=None` — 14E ranking boost 미활용
  - 엣징 (3 BusinessTerms 풍부) / 생산성 (1 term) 도메인 actions 의 매핑 누락

이 스크립트는 멱등:
  1. 작은 신규 BusinessTerm 1 종 (`term.scm.margin` — 데이터 없지만 alias bridge 용)
  2. FQN/label 패턴 매칭으로 declared_on_term=None 인 actions 에 term 매핑 :
     - %edging% → term.scm.edging_group
     - %productivity% → term.scm.product.productivity_std
     - %margin% → term.scm.margin (신규)
     - %slab_no_sequence% → term.scm.slab.slab_no_sequence (이미 매핑된 것 무시)
     - %customer% → term.scm.customer_std
     - %algorithm% → term.scm.algorithm_step
     - %trace% → term.scm.trace_collector
     - %history% → term.scm.history_controller
     - %validation_result% → term.scm.validation_result
     - %result_controller% → term.scm.result_controller
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from backend.modeling.persistence.database import session_scope
from backend.modeling.domain_layer.orm import BusinessTermRow
from backend.modeling.mapping_layer.orm import ActionRow


REPO_ID = "slab-design-real-v2"


# 1) 신규 term 만 (기존 term 은 매핑만)
NEW_TERMS: list[dict] = [
    {
        "fqn": "term.scm.margin",
        "label": "마진",
        "aliases": [
            "margin", "Margin", "마진값", "마진 범위",
            "엣징 마진", "스펙 마진",
        ],
        "description": "도메인 마진 (margin) — 엣징/스펙/계산 등에서 사용",
    },
]


# 2) FQN/label substring → 대응 term (declared_on_term=None 인 액션만)
#    매칭 우선순위: 첫 번째 매칭 적용
PATTERN_TO_TERM: list[tuple[str, str]] = [
    # 도메인 entity / logic / service
    ("edging",         "term.scm.edging_group"),
    ("productivity",   "term.scm.product.productivity_std"),
    ("margin",         "term.scm.margin"),
    # 내부 logic / 컴포넌트
    ("slab_no_sequence", "term.scm.slab.slab_no_sequence"),
    ("customer",       "term.scm.customer_std"),
    ("algorithm",      "term.scm.algorithm_step"),
    ("trace",          "term.scm.trace_collector"),
    ("history",        "term.scm.history_controller"),
    ("validation_result", "term.scm.validation_result"),
    ("result_controller", "term.scm.result_controller"),
    ("working_controller", "term.scm.working_controller"),
    ("seed_controller", "term.scm.seed_controller"),
    ("order_controller", "term.scm.order.order_controller"),
]


def run(dry_run: bool = False) -> None:
    import json as _json

    with session_scope() as s:
        # 1) 신규 BusinessTerm 추가
        for spec in NEW_TERMS:
            existing = s.execute(
                select(BusinessTermRow).where(
                    BusinessTermRow.fqn == spec["fqn"],
                    BusinessTermRow.repo_id == REPO_ID,
                ),
            ).scalar_one_or_none()
            if existing is None:
                print(f"[ADD] BusinessTerm {spec['fqn']} (label={spec['label']!r})")
                if not dry_run:
                    s.add(BusinessTermRow(
                        fqn=spec["fqn"],
                        label=spec["label"],
                        aliases_json=_json.dumps(spec["aliases"], ensure_ascii=False),
                        kind="atomic",   # TermKind enum 은 atomic|composite 만 valid (concept 은 read-time 400)
                        domain="scm",
                        description=spec["description"],
                        is_abstract=False,
                        is_interface=False,
                        is_root_entity=False,
                        struct_like_hint=False,
                        confirmed=True,
                        repo_id=REPO_ID,
                        source="user",   # Literal["manual"|"auto"|"llm"|"user"] 만 valid
                    ))
            else:
                print(f"[SKIP] BusinessTerm {spec['fqn']} 이미 존재")

        # 2) 타깃 term 들이 실제로 BusinessTerm 테이블에 존재하는지 확인
        target_fqns = {t for _, t in PATTERN_TO_TERM}
        existing_terms = {
            r.fqn for r in s.execute(
                select(BusinessTermRow).where(
                    BusinessTermRow.repo_id == REPO_ID,
                    BusinessTermRow.fqn.in_(list(target_fqns)),
                ),
            ).scalars().all()
        }
        missing = target_fqns - existing_terms
        if missing:
            print(f"[INFO] 다음 term 은 BusinessTerm 미존재 — 매핑 skip: {missing}")

        # 3) declared_on_term=None 인 action 들을 패턴별로 정정
        none_actions = s.execute(
            select(ActionRow).where(
                ActionRow.repo_id == REPO_ID,
                ActionRow.declared_on_term.is_(None),
            ),
        ).scalars().all()
        print(f"[INFO] declared_on_term=None 인 actions 총 {len(none_actions)}")

        updated_count = 0
        for action in none_actions:
            fqn_lower = (action.fqn or "").lower()
            label_lower = (action.label or "").lower()
            for needle, term_fqn in PATTERN_TO_TERM:
                if term_fqn not in existing_terms:
                    continue
                if needle in fqn_lower or needle in label_lower:
                    print(
                        f"[UPDATE] {action.fqn} → declared_on_term={term_fqn!r} "
                        f"(matched {needle!r})"
                    )
                    if not dry_run:
                        action.declared_on_term = term_fqn
                    updated_count += 1
                    break

        print(f"\n[INFO] 정정된 actions: {updated_count} / {len(none_actions)}")

        if dry_run:
            print("[DRY-RUN] commit X")
            s.rollback()
        else:
            s.commit()
            print("[OK] commit 완료")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
