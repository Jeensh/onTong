"""Phase 15B — batch seed dimension BusinessTerms + correct declared_on_term.

페르소나 시니어 15A 검증 발견: 24 actions 가 모두 `term.scm.order.order` 로 매핑됨.
business_terms 에 폭/너비/길이/중량/분할 term 자체가 없음. 같은 silent wrong target
위험이 5+ dimension 에 잠재.

이 스크립트는 멱등 (15A 와 동일 패턴):
  1. 5 dimension BusinessTerms upsert (length / width / weight / slab_count / split)
  2. 13 actions 의 declared_on_term 을 dimension term 으로 정정 (기존 order term 이거나 None 인 경우만)

미정정 대상 (의도적 유지):
  - 슬랩설계_실행, order.정합성_검증, 결정, record_* (order/logging 의도)
  - product.분류, slab.slab_save_실행, resolve_and_set (별도 도메인)
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from backend.modeling.persistence.database import session_scope
from backend.modeling.domain_layer.orm import BusinessTermRow
from backend.modeling.mapping_layer.orm import ActionRow


REPO_ID = "slab-design-real-v2"
WRONG_OLD_TERM = "term.scm.order.order"


# 5 dimension terms — label / aliases / 정정할 action fqns
DIMENSION_TERMS: list[dict] = [
    {
        "fqn": "term.scm.slab.length",
        "label": "길이",
        "aliases": [
            "length", "Length", "len", "target length", "final length",
            "length range", "길이값", "길이 range",
        ],
        "description": "슬라브 길이 (slab length) — target / range / final",
        "action_fqns": [
            "action.scm.final_length_range_실행",
            "action.scm.length_range_실행",
            "action.scm.target_length_실행",
        ],
    },
    {
        "fqn": "term.scm.slab.width",
        "label": "너비",
        "aliases": [
            "width", "Width", "target width", "final width",
            "width range", "폭", "너비값", "너비 range",
        ],
        "description": "슬라브 너비/폭 (slab width)",
        "action_fqns": [
            "action.scm.final_width_range_실행",
            "action.scm.target_width_실행",
            "action.scm.width_range_실행",
        ],
    },
    {
        "fqn": "term.scm.slab.weight",
        "label": "중량",
        "aliases": [
            "weight", "Weight", "wgt", "slab weight", "kg",
            "first weight", "second weight",
            "중량값", "무게", "kgs",
        ],
        "description": "슬라브 중량 (slab weight) — first / second / recalc",
        "action_fqns": [
            "action.scm.first_weight_실행",
            "action.scm.slab.initial_slab_wgt_실행",
            "action.scm.second_wgt_high_실행",
            "action.scm.second_wgt_low_실행",
            "action.scm.slab.slab_wgt_recalc_실행",
        ],
    },
    {
        "fqn": "term.scm.slab.slab_count",
        "label": "슬라브 매수",
        "aliases": [
            "slab count", "slab_count", "매수", "row count",
            "slab no count", "갯수", "수량",
        ],
        "description": "슬라브 매수 (slab count per order)",
        "action_fqns": [
            "action.scm.slab.slab_count_실행",
        ],
    },
    {
        "fqn": "term.scm.slab.split",
        "label": "분할",
        "aliases": [
            "split", "Split", "split range", "max split count",
            "split count", "분할 범위", "분할 갯수",
        ],
        "description": "슬라브 분할 (split) — range / max count",
        "action_fqns": [
            "action.scm.max_split_count_실행",
            "action.scm.split_range_실행",
        ],
    },
]


def run(dry_run: bool = False) -> None:
    import json as _json

    with session_scope() as s:
        # 1) BusinessTerms upsert
        for spec in DIMENSION_TERMS:
            fqn = spec["fqn"]
            aliases_json = _json.dumps(spec["aliases"], ensure_ascii=False)
            existing = s.execute(
                select(BusinessTermRow).where(
                    BusinessTermRow.fqn == fqn,
                    BusinessTermRow.repo_id == REPO_ID,
                ),
            ).scalar_one_or_none()
            if existing is None:
                print(f"[ADD] BusinessTerm {fqn} (label={spec['label']!r})")
                if not dry_run:
                    s.add(BusinessTermRow(
                        fqn=fqn,
                        label=spec["label"],
                        aliases_json=aliases_json,
                        kind="atomic",   # TermKind enum 은 atomic|composite 만 valid
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
                if existing.aliases_json != aliases_json:
                    print(f"[UPDATE] BusinessTerm {fqn} aliases")
                    if not dry_run:
                        existing.aliases_json = aliases_json
                        existing.confirmed = True
                else:
                    print(f"[SKIP] BusinessTerm {fqn} 이미 일치")

        # 2) Actions declared_on_term 정정
        for spec in DIMENSION_TERMS:
            for action_fqn in spec["action_fqns"]:
                action = s.execute(
                    select(ActionRow).where(
                        ActionRow.fqn == action_fqn,
                        ActionRow.repo_id == REPO_ID,
                    ),
                ).scalar_one_or_none()
                if action is None:
                    print(f"[WARN] Action {action_fqn} 없음 — skip")
                    continue
                current = action.declared_on_term
                if current == spec["fqn"]:
                    print(f"[SKIP] Action {action_fqn}.declared_on_term 이미 정정됨")
                elif current == WRONG_OLD_TERM or current is None:
                    print(
                        f"[UPDATE] Action {action_fqn}.declared_on_term "
                        f"{current!r} → {spec['fqn']!r}"
                    )
                    if not dry_run:
                        action.declared_on_term = spec["fqn"]
                else:
                    print(
                        f"[SKIP-UNEXPECTED] Action {action_fqn}.declared_on_term="
                        f"{current!r} (예상={WRONG_OLD_TERM!r} 또는 None) — 수동 검토"
                    )

        if dry_run:
            print("\n[DRY-RUN] commit X")
            s.rollback()
        else:
            s.commit()
            print("\n[OK] commit 완료")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
