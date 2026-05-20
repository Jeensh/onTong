"""Phase 2 Step 2b — Gate I handler.

자연어 user_query → intent (LLM) + 후보 (sim_v2 ⊕ ontology) → GateTarget payload.

Q5 비전 ("확실한 근거"): 모든 ToolResult 의 Provenance + IntentDecision 의
llm_inference Provenance 가 `sources` 에 모임.

병렬: sim_v2.find_action_candidates + ontology.search_action_by_keyword.
dedupe: code_method_fqn 동일 → 한 행으로 합치고 score 합산, label 은 ontology 우선.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .intent import IntentDecision, MultiturnIntentClassifier
from .ontology_client import OntologyClient
from .schemas import ActionCandidate, GateIntentClassified, GateTarget, Provenance
from .tools import (
    call_ontology_search,
    call_sim_v2_find_action_candidates,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


async def build_intent_classified(
    *,
    user_query: str,
    classifier: MultiturnIntentClassifier,
) -> GateIntentClassified:
    """Phase 21b — Gate I-a: intent 분류만 (candidates fetch 안 함).

    user_query → intent / conditions / search_terms 추출만. 사용자가 confirm
    한 후에 `build_gate_i` 가 후보 검색 진행 (turn 3).
    """
    intent_decision = classifier.classify(user_query)
    sources = [_intent_provenance(user_query, intent_decision)]
    return GateIntentClassified(
        intent=intent_decision.intent,
        user_query=user_query,
        search_terms=list(intent_decision.search_terms or []),
        conditions=list(intent_decision.conditions),
        sources=sources,
    )


async def build_gate_i(
    *,
    user_query: str,
    repo_id: str,
    classifier: MultiturnIntentClassifier,
    ontology_client: OntologyClient,
    top_n: int = 5,
    # Phase 21b — 이미 confirmed intent 가 있으면 재분류 skip
    preclassified: GateIntentClassified | None = None,
) -> GateTarget:
    """Gate I 결과 = `GateTarget` payload.

    1) classifier 로 intent 분류 (sync — Stub) 또는 LLM 호출 (지금은 sync OpenAI)
    2) ontology + sim_v2 후보 병렬 호출
    3) merge by code_method_fqn → ActionCandidate list (dedupe + score 합)
    4) Phase 12 — ontology metadata 보강 (role / parent_role / annotations / term)
       + 랭킹 boost (도메인 액션 우선, FQN substring 매칭 부스트)
    5) recommended_index = 0 if any
    6) Provenance 모음 + Phase 12 business_rules evidence → GateTarget.sources
    """
    # Phase 21b — preclassified 가 있으면 (turn 2 confirm 된 intent) 재분류 skip
    if preclassified is not None:
        from .intent import IntentDecision as _ID
        intent_decision = _ID(
            intent=preclassified.intent,
            conditions=preclassified.conditions,
            search_terms=preclassified.search_terms,
            confidence=1.0,
            reasoning="confirmed by user at turn 2 (Phase 21b)",
        )
    else:
        intent_decision = classifier.classify(user_query)

    # Phase 13b — LLM 추출 search_terms 가 있으면 그것을 검색에 사용 (페르소나 마찰
    # 해결: "엣징 마진 변경하면 어디 영향?" → ["엣징", "마진"] 으로 검색).
    # 없으면 backward-compat 으로 user_query 그대로.
    base_search_terms = list(intent_decision.search_terms or [])
    # Phase 14E — 한·영 양방향 alias expansion (cross-lingual gap 해결)
    expanded_terms: list[str] = base_search_terms
    if base_search_terms:
        expanded_terms = await asyncio.to_thread(
            lambda: _expand_search_terms(
                search_terms=base_search_terms, repo_id=repo_id,
            ),
        )
    search_query = (
        " ".join(expanded_terms) if expanded_terms else user_query
    )

    onto_task = call_ontology_search(
        ontology_client, query=search_query, repo_id=repo_id, top_n=top_n,
    )
    sim_task = call_sim_v2_find_action_candidates(
        user_query=search_query, repo_id=repo_id, top_n=top_n,
    )
    onto_result, sim_result = await asyncio.gather(onto_task, sim_task)

    candidates = _merge_candidates(
        ontology_hits=list(onto_result.data),
        sim_v2_hits=list(sim_result.data),
        top_n=top_n,
    )

    # Phase 11 — 후보별 location + body_preview 보강 (병렬).
    candidates = await _enrich_candidates(
        candidates, ontology_client=ontology_client, repo_id=repo_id,
    )
    # Phase 12 — ontology 풍부 메타 (role / parent_role / annotations / term) 보강
    candidates = await asyncio.to_thread(
        _enrich_with_ontology_metadata, candidates, repo_id,
    )
    # Phase 12 — 도메인 가중치 + FQN substring 부스트로 재정렬
    # Phase 14E — search_terms 의 한·영 alias 가 매칭되는 term FQN set 도 함께 전달
    term_fqns_in_query: set[str] = set()
    if base_search_terms:
        term_fqns_in_query = await asyncio.to_thread(
            lambda: _fetch_related_term_fqns(
                search_terms=base_search_terms, repo_id=repo_id,
            ),
        )
    candidates = _apply_ranking_boost(
        candidates,
        user_query=user_query,
        term_fqns_in_query=term_fqns_in_query,
    )
    # top_n 잘라내기 (boost 가 순서를 바꿨으므로)
    candidates = candidates[:top_n]

    # Phase 12 — business_rules evidence (Q5 "확실한 근거")
    related_terms = [c.declared_on_term for c in candidates if c.declared_on_term]
    related_rules = await asyncio.to_thread(
        lambda: _find_related_business_rules(terms=related_terms, repo_id=repo_id),
    )
    rule_provenances = [
        Provenance(
            source="ontology",
            detail=f"business_rule[{r.severity}]: {r.statement}",
            confidence=1.0 if r.confirmed else 0.7,
        )
        for r in related_rules[:5]   # 너무 많으면 5개로 cap
    ]

    sources: list[Provenance] = [
        _intent_provenance(user_query, intent_decision),
        onto_result.provenance,
        sim_result.provenance,
        *rule_provenances,
    ]

    # Phase 13b — 0-cand fallback: business_terms.aliases_json 인접어 추천.
    suggestions: list[str] = []
    if not candidates:
        suggestions = await asyncio.to_thread(
            _fetch_suggestions,
            query=user_query,
            search_terms=intent_decision.search_terms,
            repo_id=repo_id,
        )

    return GateTarget(
        intent=intent_decision.intent,
        user_query=user_query,
        candidates=candidates,
        recommended_index=0 if candidates else None,
        selected=None,
        sources=sources,
        suggestions=suggestions,
        conditions=list(intent_decision.conditions),
    )


async def _enrich_candidates(
    candidates: list[ActionCandidate],
    *,
    ontology_client: OntologyClient,
    repo_id: str,
) -> list[ActionCandidate]:
    """후보마다 (location, body_preview, return_type) 를 병렬 fetch.

    실패 graceful — 개별 fetch 실패해도 다른 후보 영향 없음.
    """
    if not candidates:
        return candidates

    async def _enrich_one(c: ActionCandidate) -> ActionCandidate:
        try:
            detail = await ontology_client.get_action_detail(c.action_id, repo_id=repo_id)
        except Exception as e:  # noqa: BLE001
            logger.debug("get_action_detail fail %s: %s", c.action_id, e)
            detail = None
        location = detail.location if detail and detail.location else None
        # body fetch — candidate fqn 으로 (detail.code_method_fqn 이 비어 있을 수 있음)
        try:
            body = await ontology_client.get_method_body(
                c.code_method_fqn, repo_id=repo_id,
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("get_method_body fail %s: %s", c.code_method_fqn, e)
            body = None
        body_preview = _truncate_lines(body, max_lines=5) if body else None

        # Phase 11 — line range / return_type 가 detail.location 에 부재할 때
        # sec2 body endpoint metadata 로 보강 (Hybrid client 만 구현 — graceful).
        return_type = None
        if hasattr(ontology_client, "get_method_meta"):
            try:
                meta = await ontology_client.get_method_meta(
                    c.code_method_fqn, repo_id=repo_id,
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("get_method_meta fail %s: %s", c.code_method_fqn, e)
                meta = None
            if meta:
                # location 이 비어 있거나 meta 가 더 정확 (line_start>0) 이면 갱신
                if not location or not getattr(location, "file_path", ""):
                    from .schemas import CodeLocation as _Loc
                    location = _Loc(
                        file_path=meta.get("file_path") or "",
                        line_start=int(meta.get("line_start") or 0),
                        line_end=int(meta.get("line_end") or 0),
                    )
                return_type = meta.get("return_type") or None

        return c.model_copy(update={
            "location": location,
            "body_preview": body_preview,
            "return_type": return_type,
        })

    enriched = await asyncio.gather(
        *[_enrich_one(c) for c in candidates], return_exceptions=False,
    )
    return list(enriched)


def _truncate_lines(text: str, *, max_lines: int) -> str:
    """첫 N 줄만 발췌 — 마지막 줄에 `…` 추가 (잘렸을 때)."""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + "\n…"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 12 Activation — ontology metadata + ranking boost + business_rules
# ─────────────────────────────────────────────────────────────────────────────


def _enrich_with_ontology_metadata(
    candidates: list[ActionCandidate], repo_id: str,
) -> list[ActionCandidate]:
    """ontology.db 직접 query — role / parent_role / annotations / declared_on_term.

    sync 함수. caller 가 `asyncio.to_thread` 로 wrap.
    실패 graceful — 어느 후보든 메타 못 찾으면 그냥 원본 반환.
    """
    if not candidates:
        return candidates
    try:
        import json as _json
        from sqlalchemy import select as _select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow
        from backend.modeling.mapping_layer.orm import ActionRow

        fqns = [c.code_method_fqn for c in candidates if c.code_method_fqn]
        action_ids = [c.action_id for c in candidates if c.action_id]
        if not fqns and not action_ids:
            return candidates

        with session_scope() as s:
            # CodeMethod -> CodeType 한 번에
            method_rows = s.execute(
                _select(CodeMethodRow).where(
                    CodeMethodRow.fqn.in_(fqns),
                    CodeMethodRow.repo_id == repo_id,
                ),
            ).scalars().all()
            method_by_fqn = {r.fqn: r for r in method_rows}

            parent_fqns = {r.parent_type_fqn for r in method_rows}
            type_rows = s.execute(
                _select(CodeTypeRow).where(
                    CodeTypeRow.fqn.in_(parent_fqns),
                ),
            ).scalars().all() if parent_fqns else []
            type_by_fqn = {r.fqn: r for r in type_rows}

            # Action -> declared_on_term
            action_rows = s.execute(
                _select(ActionRow).where(
                    ActionRow.fqn.in_(action_ids),
                    ActionRow.repo_id == repo_id,
                ),
            ).scalars().all() if action_ids else []
            action_by_fqn = {r.fqn: r for r in action_rows}

        def _parse_annotations(raw: str | None) -> list[str]:
            if not raw:
                return []
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:  # noqa: BLE001
                pass
            return []

        out: list[ActionCandidate] = []
        for c in candidates:
            method = method_by_fqn.get(c.code_method_fqn)
            parent = type_by_fqn.get(method.parent_type_fqn) if method else None
            action = action_by_fqn.get(c.action_id)

            method_anns = _parse_annotations(method.annotations_json if method else None)
            parent_anns = _parse_annotations(parent.annotations_json if parent else None)
            all_anns = sorted(set(method_anns + parent_anns))

            out.append(c.model_copy(update={
                "role":             method.role if method else c.role,
                "parent_role":      parent.role if parent else c.parent_role,
                "annotations":      all_anns if all_anns else c.annotations,
                "declared_on_term": (
                    action.declared_on_term if action and action.declared_on_term
                    else c.declared_on_term
                ),
            }))
        return out
    except Exception as e:  # noqa: BLE001
        logger.debug("_enrich_with_ontology_metadata 실패 (graceful): %s", e)
        return candidates


# Phase 16T — boost 가중치는 ranking_weights 모듈에서 import
from .ranking_weights import (
    ROLE_BOOST as _ROLE_BOOST,
    PARENT_ROLE_BOOST as _PARENT_BOOST,
    DOMAIN_ANNOTATIONS as _DOMAIN_ANNOTATIONS,
    DOMAIN_ANNOTATION_BOOST as _DOMAIN_ANNOTATION_BOOST,
    CLASS_PATTERN_BOOST as _CLASS_PATTERN_BOOST,
    FQN_EXACT_BOOST as _FQN_EXACT_BOOST,
    NAME_TOKEN_BOOST as _NAME_TOKEN_BOOST,
    DECLARED_ON_TERM_BOOST as _DECLARED_ON_TERM_BOOST,
)


def _apply_ranking_boost(
    candidates: list[ActionCandidate],
    *,
    user_query: str,
    term_fqns_in_query: set[str] | None = None,
) -> list[ActionCandidate]:
    """role / parent_role / annotations / class-pattern / FQN substring 종합 boost.

    Phase 12 Activation — 데이터 의 풍부한 메타 (role, parent_role, annotations,
    classname pattern) 가 ontology 에 모두 typed 되어 있는데 랭킹에서 0% 활용
    되던 문제 해결. ValidationResult.pass 같은 helper 가 SdThicknessAction.execute
    위로 랭크되는 사례 보정.

    Phase 14E — `term_fqns_in_query`: search_terms 의 한·영 alias 가 매칭되는
    business_terms FQN set. 후보의 `declared_on_term` 이 이 set 에 있으면 강한
    boost. "두께" → term.scm.thickness → SdThicknessAction.execute 우선.
    """
    if not candidates:
        return candidates
    term_fqns = term_fqns_in_query or set()

    import re as _re

    fqn_exact: list[str] = []
    word_tokens: list[str] = []
    for tok in _re.split(r"[\s,;\"'`]+", user_query or ""):
        if not tok:
            continue
        if "." in tok and any(ch.isalpha() for ch in tok):
            fqn_exact.append(tok.lower())
        elif _re.match(r"^[A-Za-z][A-Za-z0-9_]{3,}$", tok):
            word_tokens.append(tok.lower())
        elif _re.match(r"^[가-힣]{2,}$", tok):
            word_tokens.append(tok)

    def _boost(c: ActionCandidate) -> float:
        b = 0.0
        if c.role:
            b += _ROLE_BOOST.get(c.role.lower(), 0.0)
        if c.parent_role:
            b += _PARENT_BOOST.get(c.parent_role.lower(), 0.0)
        if any(a in _DOMAIN_ANNOTATIONS for a in (c.annotations or [])):
            b += _DOMAIN_ANNOTATION_BOOST

        fqn_lower = (c.code_method_fqn or "").lower()
        label_lower = (c.label or "").lower()

        for needle, weight in _CLASS_PATTERN_BOOST:
            if needle in fqn_lower:
                b += weight

        if fqn_exact:
            for tok in fqn_exact:
                if tok in fqn_lower:
                    b += _FQN_EXACT_BOOST
                    break
        if word_tokens:
            for tok in word_tokens:
                if tok in fqn_lower or tok in label_lower:
                    b += _NAME_TOKEN_BOOST

        # Phase 14E — declared_on_term × query alias FQN set 매칭
        if term_fqns and c.declared_on_term and c.declared_on_term in term_fqns:
            b += _DECLARED_ON_TERM_BOOST
        return b

    rescored = sorted(
        candidates,
        key=lambda c: -(c.score + _boost(c)),
    )
    # 사용자가 보는 score 도 갱신 (transparency)
    return [
        c.model_copy(update={"score": round(c.score + _boost(c), 3)})
        for c in rescored
    ]


def _expand_search_terms(
    *,
    search_terms: list[str],
    repo_id: str,
    cap_per_token: int = 5,
) -> list[str]:
    """Phase 14E — 한·영 양방향 alias expansion (strict token 매칭).

    `business_terms` 에서 search_terms 가 **label 정확 일치** 또는 **aliases 중 한
    element 정확 일치** 시에만 expansion. substring LIKE 만 쓰면 ValidationResult
    같은 helper 가 "검증" 으로 매칭되어 noise 발생.

    예:
      - ["두께"] + term "두께"(aliases=["thickness","thk"]) → ["두께","thickness","thk"]
      - ["검증"] + term "ValidationResult"(aliases=["검증결과","결과"]) → ["검증"] (확장 X)
      - ["검증"] + term "검증"(aliases=["validation"]) → ["검증","validation"]

    cap_per_token: 토큰 한 개당 추가될 alias 수 cap.
    repo_id 로 strict filter.
    """
    if not search_terms:
        return []
    seen: list[str] = []
    seen_lower: set[str] = set()
    for t in search_terms:
        ts = (t or "").strip()
        if ts and ts.lower() not in seen_lower:
            seen.append(ts)
            seen_lower.add(ts.lower())

    try:
        import json as _json
        from sqlalchemy import select as _select, or_
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.domain_layer.orm import BusinessTermRow

        for tok in list(seen):
            tok_lower = tok.lower()
            # SQLite 측 substring 으로 candidate 좁힌 후 Python 측 정확 일치 filter
            with session_scope() as s:
                rows = s.execute(
                    _select(BusinessTermRow).where(
                        BusinessTermRow.repo_id == repo_id,
                        or_(
                            BusinessTermRow.label.like(f"%{tok}%"),
                            BusinessTermRow.aliases_json.like(f"%{tok}%"),
                        ),
                    ).limit(20),
                ).scalars().all()

            added = 0
            for r in rows:
                if added >= cap_per_token:
                    break
                label = (r.label or "").strip()
                try:
                    aliases = _json.loads(r.aliases_json or "[]")
                except Exception:  # noqa: BLE001
                    aliases = []
                alias_strs = [str(a).strip() for a in aliases]
                # strict token 매칭: label 정확 일치 OR aliases 중 한 element 정확 일치
                if (
                    label.lower() == tok_lower
                    or any(a.lower() == tok_lower for a in alias_strs)
                ):
                    # 이 term 의 다른 표기 (label + 다른 aliases) 추가
                    if label and label.lower() not in seen_lower:
                        seen.append(label)
                        seen_lower.add(label.lower())
                        added += 1
                    for a in alias_strs:
                        if added >= cap_per_token:
                            break
                        if a and a.lower() not in seen_lower:
                            seen.append(a)
                            seen_lower.add(a.lower())
                            added += 1
    except Exception as e:  # noqa: BLE001
        logger.debug("_expand_search_terms 실패 (graceful): %s", e)

    return seen


def _fetch_related_term_fqns(
    *,
    search_terms: list[str],
    repo_id: str,
) -> set[str]:
    """search_terms 가 label / alias 와 **정확 일치** 하는 BusinessTermRow.fqn set.

    Phase 14E ranking boost 용 — `actions.declared_on_term` 와 비교해
    cross-lingual 매칭 후보를 boost. strict 매칭 (expand_search_terms 와 동일
    원칙) 으로 ValidationResult 노이즈 차단.
    """
    if not search_terms:
        return set()
    tokens_lower = {(t or "").strip().lower() for t in search_terms if (t or "").strip()}
    if not tokens_lower:
        return set()
    try:
        import json as _json
        from sqlalchemy import select as _select, or_
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.domain_layer.orm import BusinessTermRow

        clauses = []
        for t in search_terms:
            ts = (t or "").strip()
            if not ts:
                continue
            clauses.append(BusinessTermRow.label.like(f"%{ts}%"))
            clauses.append(BusinessTermRow.aliases_json.like(f"%{ts}%"))
        if not clauses:
            return set()
        with session_scope() as s:
            rows = s.execute(
                _select(BusinessTermRow).where(
                    BusinessTermRow.repo_id == repo_id,
                    or_(*clauses),
                ),
            ).scalars().all()

        out: set[str] = set()
        for r in rows:
            label = (r.label or "").strip()
            try:
                aliases = _json.loads(r.aliases_json or "[]")
            except Exception:  # noqa: BLE001
                aliases = []
            alias_lowers = {str(a).strip().lower() for a in aliases}
            if label.lower() in tokens_lower or (tokens_lower & alias_lowers):
                if r.fqn:
                    out.add(r.fqn)
        return out
    except Exception as e:  # noqa: BLE001
        logger.debug("_fetch_related_term_fqns 실패 (graceful): %s", e)
        return set()


# Phase 16M — generic Korean verbs that match too broadly to be useful
# suggestions. compound 형은 stopword 아님 (e.g. "검증결과" 은 의미 있음).
_KOREAN_QUERY_STOPWORDS: set[str] = {
    "검증", "실행", "처리", "확인", "조회", "검사", "수행", "갱신",
    "시뮬", "시뮬레이션", "영향", "영향도",
    # PM 16M 권고 (defensive — 라이브 hits=0 으로 verified safe-to-add):
    "이름", "체크", "보기", "계산", "생성", "추가",
}


def _fetch_suggestions(
    *,
    query: str,
    search_terms: list[str] | None = None,
    repo_id: str,
    limit: int = 5,
) -> list[str]:
    """0-cand 시 `business_terms.aliases_json` 인접어 추천.

    Phase 13b — LLM 추출 search_terms (혹은 fallback 으로 user_query) 가 어떤
    business_term 의 alias 와 substring 매칭되면 그 term 의 label + 다른 aliases
    를 surface. 사용자가 "엣징" 검색 → "엣징그룹" / "EDGING_GROUP" 추천.

    repo_id 로 필터링 (다른 repo 의 term 노이즈 차단).

    Phase 16M — quality 보강:
      (a) 사용자가 친 토큰과 정확히 동일 (lowercase) 한 candidate 는 제외
          — 이미 친 단어를 다시 추천하는 noise 제거
      (b) generic Korean 동사 stopword (`검증/실행/처리/...`) 토큰은 무시
          — `주문 검증` 시 `검증` 이 무관 domain dominate 막음
    """
    tokens: list[str] = []
    if search_terms:
        tokens = [t.strip() for t in search_terms if t and t.strip()]
    if not tokens and query:
        # search_terms 가 비었으면 user_query 를 토크나이즈 (영문 3 자+ / 한글 2 자+).
        import re as _re
        for tok in _re.split(r"[\s,;\"'`?.()]+", query):
            if not tok:
                continue
            if _re.match(r"^[A-Za-z][A-Za-z0-9_]{2,}$", tok) or _re.match(
                r"^[가-힣]{2,}$", tok,
            ):
                tokens.append(tok)

    # Phase 16M (b) — generic Korean 동사 토큰 제거
    tokens = [t for t in tokens if t not in _KOREAN_QUERY_STOPWORDS]
    if not tokens:
        return []
    # Phase 16M (a) — 이미 친 토큰 (case-insensitive) 은 surface 안 함
    excluded_lower: set[str] = {t.lower() for t in tokens}

    try:
        import json as _json
        from sqlalchemy import select as _select, or_
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.domain_layer.orm import BusinessTermRow

        clauses = [
            BusinessTermRow.aliases_json.like(f"%{t}%") for t in tokens
        ] + [
            BusinessTermRow.label.like(f"%{t}%") for t in tokens
        ]
        with session_scope() as s:
            rows = s.execute(
                _select(BusinessTermRow).where(
                    BusinessTermRow.repo_id == repo_id,
                    or_(*clauses),
                ).limit(limit * 3),
            ).scalars().all()
            out: list[str] = []
            seen_lower: set[str] = set(excluded_lower)
            for r in rows:
                label = (r.label or "").strip()
                if label and label.lower() not in seen_lower:
                    seen_lower.add(label.lower())
                    out.append(label)
                # aliases 도 풀어서 노출 (top N 까지)
                try:
                    aliases = _json.loads(r.aliases_json or "[]")
                except Exception:  # noqa: BLE001
                    aliases = []
                for a in aliases:
                    a = str(a).strip()
                    if a and a.lower() not in seen_lower:
                        seen_lower.add(a.lower())
                        out.append(a)
                if len(out) >= limit:
                    break
        return out[:limit]
    except Exception as e:  # noqa: BLE001
        logger.debug("_fetch_suggestions 실패 (graceful): %s", e)
        return []


def _find_related_business_rules(
    *,
    terms: list[str] | None = None,
    repo_id: str,
):
    """주어진 term FQN 목록에 연결된 business_rules 행 반환.

    `terms_ref_json` 의 substring 매칭으로 1차 필터. 빈 terms / 빈 결과면 [].
    Phase 12 Activation — business_rules 17 자연어 statement 가 chat evidence
    로 미노출 되던 문제 해결. Q5 "확실한 근거" 의 ontology source 강화.
    """
    if not terms:
        return []
    try:
        from sqlalchemy import select as _select, or_
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.domain_layer.orm import BusinessRuleRow

        clauses = [BusinessRuleRow.terms_ref_json.like(f"%{t}%") for t in terms if t]
        if not clauses:
            return []
        with session_scope() as s:
            rows = s.execute(
                _select(BusinessRuleRow).where(
                    BusinessRuleRow.repo_id == repo_id,
                    or_(*clauses),
                ),
            ).scalars().all()
        return list(rows)
    except Exception as e:  # noqa: BLE001
        logger.debug("_find_related_business_rules 실패 (graceful): %s", e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


def _intent_provenance(user_query: str, decision: IntentDecision) -> Provenance:
    return Provenance(
        source="llm_inference",
        detail=(
            f"intent={decision.intent!r} · "
            f"reasoning={decision.reasoning!r} · "
            f"query={user_query!r}"
        )[:500],
        confidence=decision.confidence,
    )


def _normalize_sim_v2_hit(raw: dict[str, Any]) -> ActionCandidate | None:
    code_fqn = raw.get("code_method_fqn") or raw.get("fqn")
    if not code_fqn:
        return None
    return ActionCandidate(
        action_id=str(raw.get("fqn") or raw.get("action_id") or code_fqn),
        label=str(raw.get("label") or code_fqn.rsplit(".", 1)[-1]),
        score=float(raw.get("score", 0.0)),
        code_method_fqn=str(code_fqn),
        aliases=[],
    )


def _merge_candidates(
    *,
    ontology_hits: list[ActionCandidate],
    sim_v2_hits: list[dict[str, Any]],
    top_n: int,
) -> list[ActionCandidate]:
    """ontology 결과 (ActionCandidate) + sim_v2 결과 (dict) 를 code_method_fqn 으로 dedupe.

    같은 code_method_fqn → score 합산, label/aliases 는 ontology 우선.
    """
    by_fqn: dict[str, ActionCandidate] = {}

    for hit in ontology_hits:
        by_fqn[hit.code_method_fqn] = hit

    for raw in sim_v2_hits:
        norm = _normalize_sim_v2_hit(raw)
        if norm is None:
            continue
        existing = by_fqn.get(norm.code_method_fqn)
        if existing is None:
            by_fqn[norm.code_method_fqn] = norm
        else:
            by_fqn[norm.code_method_fqn] = existing.model_copy(
                update={"score": existing.score + norm.score},
            )

    ranked = sorted(by_fqn.values(), key=lambda c: -c.score)
    return ranked[:top_n]


__all__ = ["build_gate_i"]
