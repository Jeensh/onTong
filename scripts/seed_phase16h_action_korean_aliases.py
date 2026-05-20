"""Phase 16H — seed Korean aliases into ActionRow.aliases_json (idempotent).

16G 시니어 라이브 검증에서 surface 됨: Action source 가 wired 됐으나
`aliases_json` 의 95% 가 generic English (`["execute"]`, `["design"]`,
`["validate"]`...) → Korean query 가 Action source 를 활용 못 함.

이 script 는 Action FQN/label 에 포함된 **Korean substring** 을
`aliases_json` 에 append (idempotent — 이미 있으면 skip).

derive 규칙:
1. FQN 의 각 `.`-split part 에서 Korean 토큰 추출 (regex `[가-힣]+`)
2. label 에서도 동일 추출
3. `_` 로 분리된 multi-Korean 도 분해 후 각각 추가
   e.g., "정합성_검증" → ["정합성", "검증", "정합성_검증"]

confirmed row 도 변경 — 이는 **enrichment** (append-only), replacement 아님.
[[feedback-idempotent-writes]] 규칙 준수.

사용: `python scripts/seed_phase16h_action_korean_aliases.py [--dry-run]`
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from sqlalchemy import select

from backend.modeling.persistence.database import session_scope
from backend.modeling.mapping_layer.orm import ActionRow


REPO_ID = "slab-design-real-v2"
KOREAN_RE = re.compile(r"[가-힣]+")
KOREAN_COMPOUND_RE = re.compile(r"[가-힣]+(?:_[가-힣]+)+")

# 단독 Korean alias 로는 너무 generic — N actions 에 매핑되면 over-expansion 노이즈
# (compound 형 e.g. "슬랩설계_실행" 은 specific 이므로 유지)
KOREAN_STOPWORDS = {"실행", "검증", "처리", "확인", "검사", "수행", "조회", "갱신"}


def derive_korean_aliases(fqn: str, label: str) -> list[str]:
    """FQN + label 에서 Korean 토큰 도출 (중복 제거, stopword 제외, 순서 유지).

    - compound (e.g. "정합성_검증") 는 specific 이므로 유지
    - 단독 generic verbs (e.g. "실행", "검증") 는 stopword 로 제외
    """
    out: list[str] = []
    seen: set[str] = set()

    def _emit(tok: str, *, is_compound: bool) -> None:
        if not tok or tok in seen:
            return
        if not is_compound and tok in KOREAN_STOPWORDS:
            return
        out.append(tok)
        seen.add(tok)

    for source in (fqn, label):
        if not source:
            continue
        # (1) compound (e.g. "정합성_검증") 전체 형 → specific 이므로 stopword 무시
        for m in KOREAN_COMPOUND_RE.finditer(source):
            tok = m.group(0)
            _emit(tok, is_compound=True)
            # split parts → 단독은 stopword 필터 적용
            for sub in tok.split("_"):
                _emit(sub, is_compound=False)
        # (2) plain Korean (e.g. "두께", "슬랩설계", "분류") → stopword 필터
        for m in KOREAN_RE.finditer(source):
            _emit(m.group(0), is_compound=False)
    return out


def run(dry_run: bool = False) -> None:
    added_total = 0
    actions_changed = 0
    actions_unchanged = 0

    with session_scope() as s:
        rows = s.execute(
            select(ActionRow).where(ActionRow.repo_id == REPO_ID),
        ).scalars().all()

        for a in rows:
            korean = derive_korean_aliases(a.fqn, a.label or "")
            if not korean:
                actions_unchanged += 1
                continue

            try:
                existing = json.loads(a.aliases_json or "[]")
                if not isinstance(existing, list):
                    existing = []
            except Exception:
                existing = []

            existing_set = {str(x) for x in existing}
            to_add = [k for k in korean if k not in existing_set]
            if not to_add:
                actions_unchanged += 1
                continue

            new_aliases = existing + to_add
            print(
                f"[ADD] {a.fqn[:50]:50s} +{to_add!r}",
            )
            added_total += len(to_add)
            actions_changed += 1
            if not dry_run:
                a.aliases_json = json.dumps(new_aliases, ensure_ascii=False)

    print()
    print(f"Summary: {actions_changed} action(s) updated, +{added_total} aliases, {actions_unchanged} unchanged")
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
