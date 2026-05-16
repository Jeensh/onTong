"""Recipe 5 — Korean ↔ English term cross-search on slab-design-real-v2.

★ 관계 명시 ★
W77 KoreanTermResolver 는 ontology 의 `business_terms.aliases_json` 컬럼을
"대체" 하는 것이 아니라, 그 alias 데이터를 *완전히 활용* 하는 검색 layer 입니다.

    business_terms row    →   W77 이 4 컬럼 모두 token 화
      label    (한국어)        → "엣징그룹코드", "엣징"...
      aliases  (혼합)          → "엣징그룹코드", "edging", "group", "cd"
      description              → token...
      fqn                      → token...

    기존 modeling search 는 한 컬럼만 봤기 때문에 §2.4 실패.
    W77 은 4 컬럼 통합 token index 로 검색 → "엣징" 으로 영문 alias term
    까지 cross-match 도달.

실행:
    .venv/bin/python toClaude/modeling/section4-verification/section3_handoff/usage-recipes/recipe-5-korean-term-search.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from backend.sim_v2.core.search.korean_term_resolver import (
    KoreanTermResolver,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


def main() -> int:
    if not PRODUCTION_DB_PATH.exists():
        print(f"production DB not found at {PRODUCTION_DB_PATH}")
        return 1
    session = open_readonly_session()
    if session is None:
        return 1
    try:
        # 0) 사전 사실: business_terms 에 이미 한↔영 alias 가 있다는 것을 surface
        from sqlalchemy import text
        rows = session.execute(text(
            "SELECT fqn, label, aliases_json FROM business_terms "
            "WHERE repo_id='slab-design-real-v2' AND label LIKE '%엣징%' "
            "OR aliases_json LIKE '%edging%' OR aliases_json LIKE '%Edging%'"
        )).fetchall()
        print("=== 사전 데이터 — ontology 의 alias (이미 등록되어 있음)")
        for r in rows[:4]:
            print(f"  fqn={r[0]}")
            print(f"    label   = {r[1]!r}")
            print(f"    aliases = {r[2]}")
        print(f"  → W77 은 위 alias 를 *대체하지 않고* 검색에 fully exploit")
        print()

        # 1) Resolver 빌드 — v2 의 43 terms 통합 index
        resolver = KoreanTermResolver.from_session(session, "slab-design-real-v2")
        print(f"=== Resolver built: {len(resolver)} terms indexed (4 컬럼 통합)")
        print()

        # 2) Section 3 §2.4 의 실패 케이스 — "엣징"
        print("=== Section 3 §2.4 실패 케이스 — '엣징'")
        hits = resolver.resolve("엣징")
        for h in hits:
            print(f"  · {h.term.label:20s} ({h.term.fqn})  score={h.score:.1f}")
            print(f"    matched fields: {'+'.join(h.matched_fields)}")
            if h.term.aliases:
                print(f"    이 매칭의 source — aliases: {', '.join(h.term.aliases)}")
        print()

        # 3) 역방향 — 영문 alias 로 한국어 label term 매칭
        print("=== 역방향: 영문 'ValidationResult' → 한국어 '검증결과' term")
        hits = resolver.resolve("ValidationResult")
        for h in hits[:2]:
            print(f"  · {h.term.label:20s} ({h.term.fqn})  score={h.score:.1f}")
        print()

        # 4) 다중 keyword
        print("=== 다중 keyword — '엣징 사양'")
        hits = resolver.resolve("엣징 사양")
        for h in hits[:3]:
            print(f"  · {h.term.label:20s} ({h.term.fqn})  score={h.score:.1f}")
            print(f"    matched tokens: {h.matched_tokens}")
        print()

        # 5) Section 3 chat agent 통합 흐름 예시
        print("=== Section 3 의 bridge_agent 통합 예시")
        natural_queries = [
            "엣징 사양 룩업 룰 보여줘",      # Section 3 §2.4 실패 케이스
            "실수율이 어디서 계산되나?",       # Section 3 §2.2
            "주문번호가 뭐야?",
        ]
        for q in natural_queries:
            # 간단한 keyword 추출 (실제로는 LLM 또는 형태소 분석)
            keywords = [tok for tok in q.split() if len(tok) >= 2]
            candidates: dict = {}
            for kw in keywords:
                for h in resolver.resolve(kw, top_n=2):
                    candidates[h.term.fqn] = max(
                        candidates.get(h.term.fqn, 0), h.score,
                    )
            ranked = sorted(candidates.items(), key=lambda x: -x[1])[:3]
            print(f"  query: '{q}'")
            for fqn, sc in ranked:
                print(f"    → {fqn:50s}  score={sc:.1f}")
            print()

        # 6) W78 hybrid tier — typo + 비표준 음역 시연
        print("=== W78 hybrid tier — Section 3 잔여 한계 close")

        # 6a) Typo (Tier 3 fuzzy fallback)
        print("  6a) typo 'edgign' (한 글자 오타)")
        hits = resolver.resolve("edgign", use_fuzzy=True)
        for h in hits[:2]:
            print(f"     → {h.term.label}  score={h.score:.1f}")

        # 6b) 비표준 음역 (Tier 4 LLM callback)
        # 실제로는 Section 3 의 chat agent 가 자기 LLM 을 callback 으로 plug-in
        def section3_llm(query: str) -> list[str]:
            """Section 3 bridge_agent 의 LLM 추론을 흉내내는 fake."""
            mapping = {"에징": ["edging"], "에지": ["edge"]}
            return [v for kr, vs in mapping.items() if kr in query for v in vs]

        print("  6b) 비표준 음역 '에징' (정적 table 에 없음 — LLM 만 추론 가능)")
        hits = resolver.resolve("에징", llm_assist=section3_llm)
        for h in hits[:2]:
            print(f"     → {h.term.label}  score={h.score:.1f}")
        print()

        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
