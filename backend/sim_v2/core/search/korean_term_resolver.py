"""W77 / W78 — Korean-aware term resolver with hybrid search tiers.

Section 3 보고서 §2.4 의 명시된 한계: 한국어 keyword ("엣징", "단중") 가 영문
alias ("EdgingGroupEntity") 를 cross-match 못해서 modeling search 가 0 hit.
실제 DB 에는 그 매핑이 같은 row 의 label / aliases 컬럼에 함께 들어 있는데,
기존 검색 API 가 한쪽만 보고 있었던 것이 원인.

이 모듈은 ontology 의 business_terms 를 다음 4 차원으로 색인:

    1. label             — 한국어 표기 ("EDGING그룹")
    2. aliases_json      — 영문 표기 ("EdgingGroupEntity")
    3. description       — 한↔영 혼합 산문
    4. fqn               — term.scm.edging_group 같은 식별자

각 차원의 token 을 통합 inverted index 로 만든 뒤, query token 매칭 시
*어느 차원이든* 매칭되면 점수 가산.

**W78 hybrid tiers** (resolve() 호출 시 옵션으로 단계적 적용):

    Tier 1 (default)  — exact + substring + prefix
    Tier 2 (default)  — static transliteration table (한↔영 음역)
                         "엣징" → ["엣징", "edging"] 으로 확장 후 매칭
    Tier 3 (default)  — fuzzy edit-distance (오타 처리)
                         매칭 0건이면 difflib 으로 비슷한 token 검색
    Tier 4 (opt-in)   — LLM assist callback
                         Section 3 의 chat LLM 같은 외부 추론기 plug-in

Public API:
    - TermSearchHit         — (term, score, matched_tokens, matched_fields)
    - KoreanTermResolver    — build + resolve (tier 옵션)
    - LLMAssistCallable     — LLM plug-in 인터페이스
"""
from __future__ import annotations

import difflib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.sim_v2.core.search.transliteration import expand_transliteration


# A pluggable LLM callable: query → list of *candidate tokens*.
# The caller's chat LLM (e.g. Section 3's bridge_agent) provides a function
# that takes the raw query and returns transliterated/synonymous tokens.
LLMAssistCallable = Callable[[str], list[str]]


# ─────────────────────────────────────────────────────────────────────────────
# Tokenization
# ─────────────────────────────────────────────────────────────────────────────


# A token = run of letters/digits/Hangul. Splits on whitespace, dots, commas,
# camelCase, snake_case, hyphens. Hangul (가-힣) 은 별도 char class.
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_TOKEN_RE = re.compile(r"[A-Za-z]+|[0-9]+|[가-힯]+")


def tokenize(s: str) -> list[str]:
    """Lower-case tokens (Hangul preserved as-is)."""
    if not s:
        return []
    # First split camelCase / PascalCase
    pre = _CAMEL_SPLIT_RE.sub(" ", s)
    raw = _TOKEN_RE.findall(pre)
    out: list[str] = []
    for tok in raw:
        # lowercase latin tokens; keep Hangul/digits unchanged
        if tok.isascii():
            out.append(tok.lower())
        else:
            out.append(tok)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TermRecord:
    """Minimal projection of a business_terms row for indexing."""
    fqn:        str
    label:      str
    aliases:    tuple[str, ...]
    description: str
    kind:       str
    domain:     str


@dataclass(frozen=True)
class TermSearchHit:
    """Single hit with score + matched tokens for explainability."""
    term:            TermRecord
    score:           float
    matched_tokens:  tuple[str, ...]  # query tokens that matched
    matched_fields:  tuple[str, ...]  # "label" / "aliases" / "description" / "fqn"


# ─────────────────────────────────────────────────────────────────────────────
# Resolver
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _IndexedTerm:
    record:           TermRecord
    label_tokens:     set[str] = field(default_factory=set)
    alias_tokens:     set[str] = field(default_factory=set)
    desc_tokens:      set[str] = field(default_factory=set)
    fqn_tokens:       set[str] = field(default_factory=set)
    full_label:       str = ""        # raw lowercased label (for substring)
    full_aliases:     tuple[str, ...] = ()  # raw lowercased aliases


class KoreanTermResolver:
    """Token-level inverted index over (label, aliases, description, fqn).

    Build once per repo_id (or once per session if repo is fixed); resolve
    is O(query_tokens × candidates).
    """

    # 점수 가중치
    _W_LABEL_EXACT     = 3.0   # query token 이 label 의 token 과 같음
    _W_ALIAS_EXACT     = 3.0
    _W_FQN_EXACT       = 2.0
    _W_DESC_EXACT      = 1.0
    _W_LABEL_SUB       = 2.0   # query token 이 label 전체 문자열의 substring
    _W_ALIAS_SUB       = 2.0
    _W_LABEL_PREFIX    = 1.0   # token 단계 prefix 매칭 (e.g. "엣징" ⊂ "엣징그룹")

    def __init__(self, terms: Iterable[TermRecord]) -> None:
        self._terms: dict[str, _IndexedTerm] = {}
        for t in terms:
            idx = _IndexedTerm(record=t)
            idx.label_tokens   = set(tokenize(t.label))
            idx.alias_tokens   = set(tok for a in t.aliases for tok in tokenize(a))
            idx.desc_tokens    = set(tokenize(t.description))
            idx.fqn_tokens     = set(tokenize(t.fqn))
            idx.full_label     = t.label.lower()
            idx.full_aliases   = tuple(a.lower() for a in t.aliases)
            self._terms[t.fqn] = idx

    @classmethod
    def from_session(
        cls, session: Session, repo_id: str,
    ) -> "KoreanTermResolver":
        rows = session.execute(
            text(
                "SELECT fqn, label, aliases_json, description, kind, domain "
                "FROM business_terms WHERE repo_id = :r"
            ),
            {"r": repo_id},
        ).fetchall()
        records: list[TermRecord] = []
        for row in rows:
            fqn, label, aliases_json, description, kind, domain = row
            aliases: tuple[str, ...] = ()
            if aliases_json:
                try:
                    parsed = json.loads(aliases_json)
                    if isinstance(parsed, list):
                        aliases = tuple(s for s in parsed if isinstance(s, str))
                except json.JSONDecodeError:
                    pass
            records.append(TermRecord(
                fqn=fqn,
                label=label or "",
                aliases=aliases,
                description=description or "",
                kind=kind or "",
                domain=domain or "",
            ))
        return cls(records)

    def __len__(self) -> int:
        return len(self._terms)

    def resolve(
        self,
        query: str,
        *,
        top_n: int = 8,
        min_score: float = 0.5,
        use_transliteration: bool = True,
        use_fuzzy: bool = True,
        llm_assist: LLMAssistCallable | None = None,
    ) -> list[TermSearchHit]:
        """Return top-N matches by composite score (W78 hybrid tiers).

        Tier 1 (always)             — token exact / substring / prefix
        Tier 2 (use_transliteration) — 한↔영 static table expansion
        Tier 3 (use_fuzzy)           — difflib edit-distance fallback (0 hit 시)
        Tier 4 (llm_assist)          — caller-supplied LLM (위 단계 all-fail 시)

        Tier 2 는 항상 1 패스에 통합되지만, Tier 3 / Tier 4 는 *상위 단계가
        0 hit 일 때만* 호출. 비용이 큰 단계를 뒤에 두는 hybrid 전략.
        """
        q_tokens_raw = tokenize(query)
        if not q_tokens_raw:
            return []

        # ---- Tier 2: 한↔영 static transliteration 확장 ----
        if use_transliteration:
            seen: set[str] = set()
            q_tokens: list[str] = []
            for qt in q_tokens_raw:
                for variant in expand_transliteration(qt):
                    if variant not in seen:
                        seen.add(variant)
                        q_tokens.append(variant)
        else:
            q_tokens = list(q_tokens_raw)

        q_lower = query.lower().strip()

        hits = self._score(
            q_tokens, q_lower, top_n=top_n, min_score=min_score,
        )
        if hits:
            return hits

        # ---- Tier 3: fuzzy edit-distance fallback (오타 처리) ----
        if use_fuzzy:
            all_tokens: set[str] = set()
            for idx in self._terms.values():
                all_tokens.update(idx.label_tokens)
                all_tokens.update(idx.alias_tokens)
                all_tokens.update(idx.fqn_tokens)
            fuzzy_tokens: list[str] = list(q_tokens)
            fuzzy_seen: set[str] = set(q_tokens)
            for qt in q_tokens_raw:
                if len(qt) < 3:
                    continue  # 짧은 토큰은 false-match 가 많음 → skip
                for c in difflib.get_close_matches(
                    qt, all_tokens, n=3, cutoff=0.7,
                ):
                    if c not in fuzzy_seen:
                        fuzzy_seen.add(c)
                        fuzzy_tokens.append(c)
            if len(fuzzy_tokens) > len(q_tokens):
                hits = self._score(
                    fuzzy_tokens, q_lower,
                    top_n=top_n, min_score=min_score,
                )
                if hits:
                    return hits

        # ---- Tier 4: caller-supplied LLM 추론 ----
        # 예: Section 3 의 chat agent 가 "에징" 같은 비표준 음역을 ["edging"]
        # 으로 추론. 정적 table 에 없어도 LLM 의 음운 지식으로 도달.
        if llm_assist is not None:
            try:
                llm_candidates = llm_assist(query)
            except Exception:
                llm_candidates = []
            if llm_candidates:
                llm_tokens: list[str] = list(q_tokens)
                llm_seen: set[str] = set(q_tokens)
                for cand in llm_candidates:
                    if not isinstance(cand, str):
                        continue
                    for tok in tokenize(cand):
                        if tok not in llm_seen:
                            llm_seen.add(tok)
                            llm_tokens.append(tok)
                if len(llm_tokens) > len(q_tokens):
                    hits = self._score(
                        llm_tokens, q_lower,
                        top_n=top_n, min_score=min_score,
                    )
                    if hits:
                        return hits

        return []

    def _score(
        self,
        q_tokens: list[str],
        q_lower: str,
        *,
        top_n: int,
        min_score: float,
    ) -> list[TermSearchHit]:
        """Score all indexed terms against (possibly expanded) query tokens.

        resolve() 의 각 tier 에서 공통으로 호출. Tier 별로 다른 q_tokens
        (확장 / fuzzy / LLM) 를 넘기면 동일 logic 으로 점수화.
        """
        scores: dict[str, float] = defaultdict(float)
        matched_tokens: dict[str, set[str]] = defaultdict(set)
        matched_fields: dict[str, set[str]] = defaultdict(set)

        for fqn, idx in self._terms.items():
            # ---- token-level exact match ----
            for qt in q_tokens:
                if qt in idx.label_tokens:
                    scores[fqn] += self._W_LABEL_EXACT
                    matched_tokens[fqn].add(qt)
                    matched_fields[fqn].add("label")
                if qt in idx.alias_tokens:
                    scores[fqn] += self._W_ALIAS_EXACT
                    matched_tokens[fqn].add(qt)
                    matched_fields[fqn].add("aliases")
                if qt in idx.fqn_tokens:
                    scores[fqn] += self._W_FQN_EXACT
                    matched_tokens[fqn].add(qt)
                    matched_fields[fqn].add("fqn")
                if qt in idx.desc_tokens:
                    scores[fqn] += self._W_DESC_EXACT
                    matched_tokens[fqn].add(qt)
                    matched_fields[fqn].add("description")

                # ---- substring (label/alias 의 raw 문자열) ----
                if qt in idx.full_label:
                    if "label" not in matched_fields[fqn]:
                        scores[fqn] += self._W_LABEL_SUB
                        matched_tokens[fqn].add(qt)
                        matched_fields[fqn].add("label")
                for a in idx.full_aliases:
                    if qt in a:
                        if "aliases" not in matched_fields[fqn]:
                            scores[fqn] += self._W_ALIAS_SUB
                            matched_tokens[fqn].add(qt)
                            matched_fields[fqn].add("aliases")
                        break

                # ---- token-level prefix (한국어 합성어) ----
                for lt in idx.label_tokens:
                    if len(qt) >= 2 and lt.startswith(qt) and lt != qt:
                        scores[fqn] += self._W_LABEL_PREFIX
                        matched_tokens[fqn].add(qt)
                        matched_fields[fqn].add("label")
                        break

            # ---- raw query substring (붙여 쓴 입력 매칭) ----
            if q_lower and len(q_lower) >= 2:
                if q_lower in idx.full_label:
                    scores[fqn] += 0.5
                    matched_fields[fqn].add("label")
                for a in idx.full_aliases:
                    if q_lower in a:
                        scores[fqn] += 0.5
                        matched_fields[fqn].add("aliases")
                        break

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        out: list[TermSearchHit] = []
        for fqn, sc in ranked:
            if sc < min_score:
                continue
            out.append(TermSearchHit(
                term=self._terms[fqn].record,
                score=sc,
                matched_tokens=tuple(sorted(matched_tokens[fqn])),
                matched_fields=tuple(sorted(matched_fields[fqn])),
            ))
            if len(out) >= top_n:
                break
        return out


__all__ = [
    "KoreanTermResolver",
    "LLMAssistCallable",
    "TermRecord",
    "TermSearchHit",
    "tokenize",
]
