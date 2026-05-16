"""UC41 — Korean-aware term search on slab-design-real-v2 (W77).

Section 3 보고서 §2.4 의 실패 케이스를 직접 close 하는 demo. 그 보고서는
"엣징", "단중" 같은 한국어 keyword 가 0 hit 였다고 명시했고, "사용자 정보량
절반" 이라고 평가했다. UC41 은 W77 KoreanTermResolver 가 같은 keyword 에
대해 정확한 term 후보를 얼마나 surface 하는지 측정.

대상 시스템:
    repo_id = "slab-design-real-v2" (43 terms)

테스트 keyword (Section 3 보고서에서 명시된 실패 + 추가 case):
    "엣징", "단중", "실수율", "주문", "에러코드", "검증결과",
    "Edging", "ValidationResult"

Run:
    .venv/bin/python -m backend.sim_v2.demos.uc41_korean_term_search.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from backend.sim_v2.core.search.korean_term_resolver import (
    KoreanTermResolver,
    TermSearchHit,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


TARGET_REPO = "slab-design-real-v2"


# Section 3 의 실패 keyword + Section 3 보고서 §2 의 다른 예제들 + 영문 sanity
TEST_QUERIES: tuple[tuple[str, str], ...] = (
    ("엣징",            "Section 3 §2.4 — search 한국어 매칭 실패"),
    ("단중",            "Section 3 §2.6 — UnitWeight 매칭"),
    ("실수율",          "Section 3 §2.2 — productivity_std 매칭"),
    ("주문",            "주문 관련 term 들"),
    ("에러코드",        "한국어 label 정확 매칭"),
    ("검증결과",        "ValidationResult 한국어 cross-match"),
    ("EDGING",          "영문 (uppercase) — Edging alias 매칭"),
    ("edging",          "영문 (lowercase) — case-insensitive"),
    ("ValidationResult","영문 alias — 한국어 label term 으로"),
    ("Productivity",    "영문 부분 매칭"),
)


@dataclass(frozen=True)
class QueryResult:
    query:   str
    note:    str
    hits:    tuple[TermSearchHit, ...]

    @property
    def hit_count(self) -> int:
        return len(self.hits)


@dataclass(frozen=True)
class UC41Report:
    repo_id:           str
    total_terms:       int
    queries:           tuple[QueryResult, ...]

    @property
    def hit_rate(self) -> float:
        if not self.queries:
            return 0.0
        with_hit = sum(1 for q in self.queries if q.hit_count > 0)
        return with_hit / len(self.queries)


def run_korean_search_demo(session, repo_id: str = TARGET_REPO) -> UC41Report:
    resolver = KoreanTermResolver.from_session(session, repo_id)
    results: list[QueryResult] = []
    for q, note in TEST_QUERIES:
        hits = resolver.resolve(q, top_n=5)
        results.append(QueryResult(query=q, note=note, hits=tuple(hits)))
    return UC41Report(
        repo_id=repo_id,
        total_terms=len(resolver),
        queries=tuple(results),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(s: str) -> None:
    print("─" * 78)
    print(s)
    print("─" * 78)


def main() -> int:
    print("=" * 78)
    print(f"UC41 — Korean term search demo  ({TARGET_REPO})")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping")
        return 0

    try:
        r = run_korean_search_demo(session)
        _banner("Setup")
        print(f"  Repo                  : {r.repo_id}")
        print(f"  Indexed terms         : {r.total_terms}")
        print(f"  Test queries          : {len(r.queries)}")
        print(f"  Queries with ≥1 hit   : {sum(1 for q in r.queries if q.hit_count > 0)} "
              f"({100 * r.hit_rate:.0f}%)")
        print()

        for q in r.queries:
            tag = "✓" if q.hit_count > 0 else "✗"
            _banner(f"{tag}  query = '{q.query}'   — {q.note}")
            if q.hit_count == 0:
                print("  (no hits)")
                print()
                continue
            for h in q.hits:
                fields = "+".join(h.matched_fields)
                print(f"  · score={h.score:.1f}  [{fields:20s}]  {h.term.label} "
                      f"({h.term.fqn})")
                if h.term.aliases:
                    print(f"     aliases: {', '.join(h.term.aliases)}")
            print()

        _banner(
            f"✓ W77 Korean search reach: {int(100 * r.hit_rate)}% of test queries "
            f"surface ≥1 term"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
