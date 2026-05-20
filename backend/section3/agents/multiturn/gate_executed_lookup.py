"""Phase 13a — executed_lookup builder.

locate / explain intent 응답. Gate II / III 우회.

조립 단계:
  1) target 의 method body + file_path / line_start / line_end / return_type (ontology_client)
  2) linked action label (target.action_id) + declared_on_term (ontology.db ActionRow)
  3) caller graph (ontology_client.get_caller_graph — Phase 12 활성화 후 실 데이터)
  4) business_rules — declared_on_term 기반 evidence

모든 결과를 한 카드에 surface. 박주니어 / 김PM 페르소나의 read-only 의도 1:1 해결.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

from .ontology_client import OntologyClient
from .schemas import (
    ActionRef, AffectedMethod, BusinessRuleEvidence, GateExecutedLookup,
    Provenance,
)

logger = logging.getLogger(__name__)


async def build_executed_lookup(
    *,
    target: ActionRef,
    repo_id: str,
    ontology_client: OntologyClient,
    mode: Literal["locate", "explain"],
) -> GateExecutedLookup:
    """target 의 body + file + caller + term + rules 통합 응답."""

    # 1) body + file_path + line range (병렬 fetch — body 와 meta 가 다른 endpoint)
    body_task = ontology_client.get_method_body(
        target.code_method_fqn, repo_id=repo_id,
    )
    meta_task = (
        ontology_client.get_method_meta(target.code_method_fqn, repo_id=repo_id)
        if hasattr(ontology_client, "get_method_meta") else _noop_meta()
    )
    callers_task = ontology_client.get_caller_graph(
        target.code_method_fqn, repo_id=repo_id,
    )
    body, meta, callers = await asyncio.gather(
        body_task, meta_task, callers_task,
    )

    body_text = body or ""
    file_path = (meta or {}).get("file_path") or (
        target.location.file_path if target.location else ""
    )
    line_start = int((meta or {}).get("line_start") or (
        target.location.line_start if target.location else 0
    ))
    line_end = int((meta or {}).get("line_end") or (
        target.location.line_end if target.location else 0
    ))
    return_type = str((meta or {}).get("return_type") or "")

    # 2) linked term / action label — sync DB query
    linked_action_label, linked_term = await asyncio.to_thread(
        _fetch_action_meta, target.action_id, repo_id,
    )

    # 3) business rules evidence
    business_rules = await asyncio.to_thread(
        _fetch_rule_evidence, linked_term, repo_id,
    )

    sources: list[Provenance] = [
        Provenance(
            source="ontology",
            detail=f"executed_lookup mode={mode} method={target.code_method_fqn}",
            confidence=1.0,
        ),
    ]
    if callers:
        sources.append(Provenance(
            source="ontology",
            detail=f"caller_graph {len(callers)} 행 surface",
            confidence=0.85,
        ))
    if business_rules:
        sources.append(Provenance(
            source="ontology",
            detail=f"business_rules {len(business_rules)} 행 surface",
            confidence=1.0,
        ))

    return GateExecutedLookup(
        mode=mode,
        target=target,
        body_text=body_text,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        return_type=return_type,
        linked_action_label=linked_action_label,
        linked_term=linked_term,
        callers=list(callers or []),
        business_rules=business_rules,
        sources=sources,
    )


async def _noop_meta():
    return None


def _fetch_action_meta(
    action_id: str, repo_id: str,
) -> tuple[str | None, str | None]:
    """ActionRow.label + declared_on_term — 직접 SQLite query."""
    try:
        from sqlalchemy import select as _select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.mapping_layer.orm import ActionRow

        with session_scope() as s:
            row = s.execute(
                _select(ActionRow).where(
                    ActionRow.fqn == action_id,
                    ActionRow.repo_id == repo_id,
                ),
            ).scalar_one_or_none()
        if row is None:
            return None, None
        return (row.label or None, row.declared_on_term or None)
    except Exception as e:  # noqa: BLE001
        logger.debug("_fetch_action_meta 실패: %s", e)
        return None, None


def _fetch_rule_evidence(
    linked_term: str | None, repo_id: str,
) -> list[BusinessRuleEvidence]:
    """linked_term ↔ business_rules.terms_ref_json LIKE 매칭."""
    if not linked_term:
        return []
    try:
        from sqlalchemy import select as _select
        from backend.modeling.persistence.database import session_scope
        from backend.modeling.domain_layer.orm import BusinessRuleRow

        with session_scope() as s:
            rows = s.execute(
                _select(BusinessRuleRow).where(
                    BusinessRuleRow.repo_id == repo_id,
                    BusinessRuleRow.terms_ref_json.like(f"%{linked_term}%"),
                ),
            ).scalars().all()
        return [
            BusinessRuleEvidence(
                fqn=r.fqn,
                statement=r.statement,
                severity=r.severity,
            )
            for r in rows[:10]   # cap
        ]
    except Exception as e:  # noqa: BLE001
        logger.debug("_fetch_rule_evidence 실패: %s", e)
        return []


__all__ = ["build_executed_lookup"]
