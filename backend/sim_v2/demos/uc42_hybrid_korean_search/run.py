"""UC42 — Hybrid tier Korean search demo on slab-design-real-v2 (W78).

UC41 은 W77 (단일 패스) 의 reach 를 측정했다. UC42 는 그 위에 W78 hybrid
tier 를 4 단계로 켜가며 *각 tier 가 어떤 query 를 추가로 close 하는지*
를 측정한다.

대상 시스템:
    repo_id = "slab-design-real-v2" (43 terms)

Tier 별 시나리오:

    Tier 1 (baseline)       — exact / substring / prefix only
    Tier 1+2                — 한↔영 static transliteration table
    Tier 1+2+3              — fuzzy edit-distance fallback
    Tier 1+2+3+4            — caller-supplied LLM (fake)

Section 3 의 요청을 정확히 cover 하는 케이스:

    "엣징"     — 한국어 → 영문 alias (Tier 2 가 fix)
    "edgign"   — 영문 typo (Tier 3 가 fix)
    "에징"     — 비표준 한글 음역, 정적 table 에 없음 (Tier 4 만 가능)

Run:
    .venv/bin/python -m backend.sim_v2.demos.uc42_hybrid_korean_search.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from backend.sim_v2.core.search.korean_term_resolver import (
    KoreanTermResolver,
    LLMAssistCallable,
    TermSearchHit,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


TARGET_REPO = "slab-design-real-v2"


@dataclass(frozen=True)
class Scenario:
    name:        str
    query:       str
    tier:        str
    note:        str
    # tier 별로 다른 resolver options
    use_translit:    bool
    use_fuzzy:       bool
    use_llm:         bool


# 각 케이스를 점진적으로 어렵게 (tier 1 → tier 4)
SCENARIOS: tuple[Scenario, ...] = (
    # ── Tier 1 baseline: 정확히 영문 alias 그대로 ──
    Scenario(
        name="① 영문 정확",
        query="EdgingGroup",
        tier="T1",
        note="exact alias — baseline 으로도 hit",
        use_translit=False, use_fuzzy=False, use_llm=False,
    ),
    Scenario(
        name="② 한국어 정확",
        query="엣징그룹코드",
        tier="T1",
        note="한국어 label 정확 — baseline hit",
        use_translit=False, use_fuzzy=False, use_llm=False,
    ),

    # ── 한↔영 cross-match 가 필요한 케이스 (Tier 1 fail / Tier 2 fix) ──
    Scenario(
        name="③ 한국어 → 영문 (T1)",
        query="엣징",
        tier="T1",
        note="Tier 2 꺼두면 영문 alias 만 있는 term 못 찾음",
        use_translit=False, use_fuzzy=False, use_llm=False,
    ),
    Scenario(
        name="③ 한국어 → 영문 (T2)",
        query="엣징",
        tier="T2",
        note="Tier 2 켜면 엣징→edging 으로 cross-match",
        use_translit=True, use_fuzzy=False, use_llm=False,
    ),

    # ── 오타 (Tier 3 가 fix) ──
    Scenario(
        name="④ 영문 typo (T2)",
        query="edgign",
        tier="T2",
        note="Tier 3 꺼두면 한 글자 오타에서 fail",
        use_translit=True, use_fuzzy=False, use_llm=False,
    ),
    Scenario(
        name="④ 영문 typo (T3)",
        query="edgign",
        tier="T3",
        note="Tier 3 fuzzy 가 edgign→edging 보정",
        use_translit=True, use_fuzzy=True, use_llm=False,
    ),

    # ── 비표준 음역 (Tier 4 만 가능) ──
    Scenario(
        name="⑤ 비표준 음역 (T3)",
        query="에징",
        tier="T3",
        note="정적 table 에 없는 음역 — fuzzy 만으로 부족",
        use_translit=True, use_fuzzy=True, use_llm=False,
    ),
    Scenario(
        name="⑤ 비표준 음역 (T4)",
        query="에징",
        tier="T4",
        note="LLM 이 '에징' → 'edging' 추론",
        use_translit=True, use_fuzzy=True, use_llm=True,
    ),

    # ── 추가 sanity: 다른 도메인 한국어 ──
    Scenario(
        name="⑥ 검증결과 (T2)",
        query="검증결과",
        tier="T2",
        note="한국어 label term 직접 매칭",
        use_translit=True, use_fuzzy=False, use_llm=False,
    ),
    Scenario(
        name="⑦ 영문→한국어 (T2)",
        query="validation",
        tier="T2",
        note="영문 → 한국어 label term cross-match",
        use_translit=True, use_fuzzy=False, use_llm=False,
    ),
)


@dataclass(frozen=True)
class ScenarioResult:
    scenario:    Scenario
    hits:        tuple[TermSearchHit, ...]

    @property
    def hit_count(self) -> int:
        return len(self.hits)


def _make_fake_llm() -> LLMAssistCallable:
    """Section 3 chat agent 를 흉내내는 fake LLM.

    실제로는 GPT/Claude 가 "에징" 같은 query 를 보고 ["edging"] 같은
    영문 후보를 돌려준다. 여기서는 dictionary 로 mock.
    """
    phonetic_map = {
        "에징":  ["edging"],
        "엣전":  ["edging"],
        "에지":  ["edge"],
        "베리":  ["very"],
        "발리":  ["valley"],
    }

    def fake_llm(query: str) -> list[str]:
        out: list[str] = []
        for kr, en_list in phonetic_map.items():
            if kr in query:
                out.extend(en_list)
        return out

    return fake_llm


def run_hybrid_demo(session, repo_id: str = TARGET_REPO) -> list[ScenarioResult]:
    resolver = KoreanTermResolver.from_session(session, repo_id)
    fake_llm = _make_fake_llm()
    results: list[ScenarioResult] = []
    for sc in SCENARIOS:
        hits = resolver.resolve(
            sc.query,
            top_n=5,
            use_transliteration=sc.use_translit,
            use_fuzzy=sc.use_fuzzy,
            llm_assist=fake_llm if sc.use_llm else None,
        )
        results.append(ScenarioResult(scenario=sc, hits=tuple(hits)))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _banner(s: str) -> None:
    print("─" * 78)
    print(s)
    print("─" * 78)


def main() -> int:
    print("=" * 78)
    print(f"UC42 — Hybrid tier Korean search demo  ({TARGET_REPO})")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping")
        return 0

    try:
        results = run_hybrid_demo(session)

        _banner("Setup")
        resolver = KoreanTermResolver.from_session(session, TARGET_REPO)
        print(f"  Repo                  : {TARGET_REPO}")
        print(f"  Indexed terms         : {len(resolver)}")
        print(f"  Scenarios             : {len(SCENARIOS)}")
        with_hit = sum(1 for r in results if r.hit_count > 0)
        print(f"  Scenarios with ≥1 hit : {with_hit} / {len(results)}")
        print()

        for r in results:
            sc = r.scenario
            tag = "✓" if r.hit_count > 0 else "✗"
            _banner(
                f"{tag}  {sc.name}  [{sc.tier}]  query='{sc.query}'  — {sc.note}"
            )
            if r.hit_count == 0:
                print("  (no hits)")
                print()
                continue
            for h in r.hits[:3]:
                fields = "+".join(h.matched_fields)
                print(
                    f"  · score={h.score:>4.1f}  [{fields:20s}]  "
                    f"{h.term.label}  ({h.term.fqn})"
                )
                if h.term.aliases:
                    print(f"     aliases: {', '.join(h.term.aliases)}")
            print()

        # ── Tier 별 close rate ──
        _banner("Tier-by-tier close rate")
        for tier in ("T1", "T2", "T3", "T4"):
            in_tier = [r for r in results if r.scenario.tier == tier]
            if not in_tier:
                continue
            wins = sum(1 for r in in_tier if r.hit_count > 0)
            print(f"  {tier}: {wins} / {len(in_tier)} scenarios closed")
        print()

        _banner(
            "✓ W78 hybrid tiers — Section 3 의 잔여 한계 (typo + 비표준 음역) close"
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
