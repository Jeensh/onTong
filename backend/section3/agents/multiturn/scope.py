"""Phase 18 — Stage 2 (영향 영역) scope aggregator.

사용자 vision: 선택한 action 의 영향 영역 (callers + declared_on_term sibling
actions + related business_rules + 같은 도메인 entities) 한 눈에. modeling
graph 의 부분 view.

backend collectors 재사용:
  - `get_caller_graph` (ontology_client) — caller chain
  - `_find_related_business_rules` (gate_i) — terms 기반 룰
  - `business_terms` + `actions.declared_on_term` — sibling actions (같은 term)

구현 위치 선택: gate_i.py 에 두면 cycle 위험 (현 위치도 비대). 별도 `scope.py`.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from .ontology_client import OntologyClient


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Result schema
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScopeEntity:
    """scope 안의 한 엔티티 (action / caller / term / rule / fixture)."""
    kind: str  # "action" / "caller" / "term" / "rule"
    fqn: str
    label: str
    detail: str = ""
    # frontend 가 check/uncheck 한 default 여부. Test/Mock 패턴은 False.
    in_scope_default: bool = True
    # 메타 (e.g., caller match_kind, rule severity)
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Scope:
    primary_action_fqn: str
    primary_method_fqn: str
    entities: list[ScopeEntity]
    # 통계
    counts: dict[str, int] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Test/Mock pattern (Phase 16D W4 와 동일 정책)
# ─────────────────────────────────────────────────────────────────────────────


def _is_test_or_mock(fqn: str) -> bool:
    """`target_is_test` 정책과 동기화 (gate_hypothesis _compute_integrity_warnings)."""
    lower = (fqn or "").lower()
    is_test = any(
        pat in lower for pat in ("test.", "test(", "stub.", "stub(")
    ) or "tests." in lower or lower.endswith("test")
    is_mock = "mock" in lower
    return is_test or is_mock


# ─────────────────────────────────────────────────────────────────────────────
# Collectors
# ─────────────────────────────────────────────────────────────────────────────


def _get_sibling_actions(declared_on_term: str | None, repo_id: str) -> list[dict]:
    """같은 BusinessTerm 에 declared_on_term 가리키는 다른 actions."""
    if not declared_on_term:
        return []
    try:
        from sqlalchemy import select as _select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.mapping_layer.orm import ActionRow

        with session_scope() as s:
            rows = s.execute(
                _select(ActionRow).where(
                    ActionRow.repo_id == repo_id,
                    ActionRow.declared_on_term == declared_on_term,
                ).limit(20),
            ).scalars().all()
        return [
            {"fqn": r.fqn, "label": r.label}
            for r in rows
        ]
    except Exception as e:  # noqa: BLE001
        logger.debug("_get_sibling_actions 실패 (graceful): %s", e)
        return []


def _get_term_detail(term_fqn: str, repo_id: str) -> dict | None:
    """declared_on_term 의 BusinessTerm row → label / domain / aliases."""
    if not term_fqn:
        return None
    try:
        from sqlalchemy import select as _select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.domain_layer.orm import BusinessTermRow

        with session_scope() as s:
            row = s.execute(
                _select(BusinessTermRow).where(
                    BusinessTermRow.fqn == term_fqn,
                    BusinessTermRow.repo_id == repo_id,
                ),
            ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "fqn": row.fqn,
            "label": row.label,
            "domain": row.domain,
        }
    except Exception as e:  # noqa: BLE001
        logger.debug("_get_term_detail 실패 (graceful): %s", e)
        return None


async def build_scope(
    *,
    action_fqn: str,
    code_method_fqn: str,
    declared_on_term: str | None,
    repo_id: str,
    ontology_client: OntologyClient,
) -> Scope:
    """선택한 action 의 영향 영역 집계.

    병렬 fetch:
      - caller_graph (existing ontology_client method)
      - sibling actions (same declared_on_term)
      - related business_rules (existing _find_related_business_rules)
      - term detail

    Test/Mock 패턴은 in_scope_default=False (사용자 명시적 체크 필요).
    """
    from .gate_i import _find_related_business_rules

    # 병렬 fetch
    caller_task = ontology_client.get_caller_graph(
        code_method_fqn, repo_id=repo_id,
    )
    sibling_task = asyncio.to_thread(
        _get_sibling_actions, declared_on_term, repo_id,
    )
    rules_task = asyncio.to_thread(
        _find_related_business_rules,
        terms=[declared_on_term] if declared_on_term else [],
        repo_id=repo_id,
    )
    term_task = asyncio.to_thread(
        _get_term_detail, declared_on_term or "", repo_id,
    )

    caller_result, siblings, rules, term_detail = await asyncio.gather(
        caller_task, sibling_task, rules_task, term_task,
    )

    entities: list[ScopeEntity] = []

    # Primary action 자체
    entities.append(ScopeEntity(
        kind="action",
        fqn=action_fqn,
        label=action_fqn.split(".")[-1],
        detail=code_method_fqn,
        in_scope_default=True,
        meta={"primary": True},
    ))

    # Term
    if term_detail:
        entities.append(ScopeEntity(
            kind="term",
            fqn=term_detail["fqn"],
            label=term_detail["label"],
            detail=f"domain={term_detail['domain']}",
            in_scope_default=True,
        ))

    # Sibling actions (같은 term, primary 제외)
    for sib in siblings:
        if sib["fqn"] == action_fqn:
            continue
        sib_test = _is_test_or_mock(sib["fqn"])
        entities.append(ScopeEntity(
            kind="action",
            fqn=sib["fqn"],
            label=sib.get("label") or sib["fqn"].split(".")[-1],
            detail="declared_on 동일 term",
            in_scope_default=not sib_test,
            meta={"sibling": True, "test_suspect": sib_test},
        ))

    # Callers — get_caller_graph 가 list[AffectedMethod] 직접 반환
    caller_list = caller_result if isinstance(caller_result, list) else []
    for c in caller_list:
        fqn = getattr(c, "fqn", "") or (c.get("fqn", "") if isinstance(c, dict) else "")
        match_kind = (
            getattr(c, "match_kind", None)
            or (c.get("match_kind") if isinstance(c, dict) else None)
        )
        strength = (
            getattr(c, "strength", None)
            if hasattr(c, "strength")
            else (c.get("strength") if isinstance(c, dict) else None)
        )
        if not fqn:
            continue
        is_test = _is_test_or_mock(fqn)
        entities.append(ScopeEntity(
            kind="caller",
            fqn=fqn,
            label=fqn.split(".")[-1],
            detail=f"match={match_kind or 'unknown'}"
            + (f" strength={strength:.2f}" if isinstance(strength, (int, float)) else ""),
            in_scope_default=not is_test,
            meta={
                "match_kind": match_kind,
                "strength": strength,
                "test_suspect": is_test,
            },
        ))

    # Business rules
    for r in rules:
        entities.append(ScopeEntity(
            kind="rule",
            fqn=r.fqn,
            label=r.fqn.split(".")[-1],
            detail=(r.statement or "")[:200],
            in_scope_default=True,
            meta={"severity": r.severity},
        ))

    # Counts
    counts: dict[str, int] = {}
    for e in entities:
        counts[e.kind] = counts.get(e.kind, 0) + 1

    return Scope(
        primary_action_fqn=action_fqn,
        primary_method_fqn=code_method_fqn,
        entities=entities,
        counts=counts,
    )


__all__ = [
    "Scope",
    "ScopeEntity",
    "build_scope",
]
