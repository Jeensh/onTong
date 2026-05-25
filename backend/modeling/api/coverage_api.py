"""FastAPI router — Ontology graph Coverage mode (도메인별 진척률 + 우선 처리 대상).

REST:
- GET /api/ontology/repos/{repo_id}/graph/coverage
    도메인 grid heatmap 데이터. 각 도메인 cell 의 confirmed/draft/unmapped/orphan/recent 수.
- GET /api/ontology/repos/{repo_id}/graph/coverage/{domain}/priority
    특정 도메인 안의 우선 처리 entity 목록 (lens 토글로 필터).

Lens 정의:
- draft: verification_level ∈ {draft, unmapped} 또는 confirmed=False
- orphan: term with 0 realizations / action with 0 anchors / code_type with no term mapping
- recent: 최근 N 일 안에 user 가 변경한 entity (entity_change_log 의 changed_by IS NOT NULL)
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from backend.modeling.audit.store import recently_changed_ids
from backend.modeling.domain_layer.orm import BusinessRuleRow, BusinessTermRow
from backend.modeling.mapping_layer.orm import (
    ActionRow, AnchorBindingRow, RealizationRow, TypeRealizationRow,
)
from backend.modeling.code_layer.orm import CodeTypeRow
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/repos", tags=["ontology-coverage"])


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------
class DomainCellDTO(BaseModel):
    domain: str
    total: int
    by_kind: dict[str, int]              # term/action/code_type 등 별 count
    confirmed: int
    draft: int
    unmapped: int
    orphan_count: int
    recent_count: int
    confirmed_ratio: float


class CoverageSummaryDTO(BaseModel):
    total: int
    confirmed_ratio: float
    stalled_domains: list[str]            # confirmed_ratio < 0.3 인 도메인


class CoverageResponseDTO(BaseModel):
    repo_id: str
    domains: list[DomainCellDTO]
    summary: CoverageSummaryDTO


class PriorityEntityDTO(BaseModel):
    kind: str                              # action / term / code_type
    fqn: str
    label: str
    verification_level: str | None = None  # action 만
    confirmed: bool
    priority_score: float                  # 0~10
    reasons: list[str]                     # ["draft", "orphan", "recent"]


class PriorityResponseDTO(BaseModel):
    domain: str
    lens: list[str]
    entities: list[PriorityEntityDTO]
    total_match: int


# ---------------------------------------------------------------------------
# Coverage — 도메인 grid heatmap
# ---------------------------------------------------------------------------
@router.get("/{repo_id}/graph/coverage", response_model=CoverageResponseDTO)
def get_coverage(repo_id: str, recent_days: int = Query(7, ge=1, le=90)) -> CoverageResponseDTO:
    """도메인 별 매핑 진척률 + orphan/recent count.

    "도메인" 정의:
    - Term/Action: domain 컬럼
    - CodeType: package 의 마지막 2 segment (예: feature.sd.process.std.service → "process.std")
    """
    with session_scope() as s:
        # ─── Term aggregates ─────────────────────────────────────
        term_rows = s.execute(
            select(BusinessTermRow).where(BusinessTermRow.repo_id == repo_id)
        ).scalars().all()
        # term orphan = type_realizations 에 한 번도 등장 안 함
        tr_term_fqns = {r for r, in s.execute(
            select(TypeRealizationRow.term_fqn).where(TypeRealizationRow.repo_id == repo_id).distinct()
        ).all()}

        # ─── Action aggregates ────────────────────────────────────
        action_rows = s.execute(
            select(ActionRow).where(ActionRow.repo_id == repo_id)
        ).scalars().all()
        # action orphan = realizations 0 + anchor_bindings 0
        action_real_fqns = {r for r, in s.execute(
            select(RealizationRow.action_fqn).where(RealizationRow.repo_id == repo_id).distinct()
        ).all()}
        action_anchor_fqns = {r for r, in s.execute(
            select(AnchorBindingRow.target_action_fqn).where(AnchorBindingRow.repo_id == repo_id).distinct()
        ).all()}

        # ─── CodeType aggregates ──────────────────────────────────
        ct_rows = s.execute(
            select(CodeTypeRow).where(CodeTypeRow.repo_id == repo_id)
        ).scalars().all()
        ct_mapped_fqns = {r for r, in s.execute(
            select(TypeRealizationRow.code_type_fqn).where(TypeRealizationRow.repo_id == repo_id).distinct()
        ).all()}

    # ─── recent changes (changed_by IS NOT NULL) ───────────────────
    recent_term_ids = recently_changed_ids(repo_id, "term", since_days=recent_days)
    recent_action_ids = recently_changed_ids(repo_id, "action", since_days=recent_days)

    # ─── 집계 by domain ────────────────────────────────────────────
    by_domain: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "by_kind": defaultdict(int),
        "confirmed": 0, "draft": 0, "unmapped": 0,
        "orphan_count": 0, "recent_count": 0,
    })

    for t in term_rows:
        d = t.domain or "(unknown)"
        cell = by_domain[d]
        cell["total"] += 1
        cell["by_kind"]["term"] += 1
        if t.confirmed:
            cell["confirmed"] += 1
        else:
            cell["draft"] += 1
        if t.fqn not in tr_term_fqns:
            cell["orphan_count"] += 1
        if t.fqn in recent_term_ids:
            cell["recent_count"] += 1

    for a in action_rows:
        d = a.domain or "(unknown)"
        cell = by_domain[d]
        cell["total"] += 1
        cell["by_kind"]["action"] += 1
        if a.verification_level in ("body_anchored", "sim_verified", "pr_proven", "signature_locked") and a.confirmed_by:
            cell["confirmed"] += 1
        elif a.verification_level == "unmapped":
            cell["unmapped"] += 1
        else:
            cell["draft"] += 1
        if a.fqn not in action_real_fqns and a.fqn not in action_anchor_fqns:
            cell["orphan_count"] += 1
        if a.fqn in recent_action_ids:
            cell["recent_count"] += 1

    for ct in ct_rows:
        pkg = ct.package or ""
        d = ".".join(pkg.split(".")[-2:]) if pkg.count(".") >= 1 else (pkg or "(unknown)")
        cell = by_domain[d]
        cell["total"] += 1
        cell["by_kind"]["code_type"] += 1
        # CodeType 은 confirmed 개념이 다름 — primary realization 있으면 confirmed 로 간주
        if ct.fqn in ct_mapped_fqns:
            cell["confirmed"] += 1
        else:
            cell["draft"] += 1
            cell["orphan_count"] += 1  # 매핑 안 된 code_type = orphan

    # ─── DTO 빌드 ─────────────────────────────────────────────────
    cells: list[DomainCellDTO] = []
    total_all = 0
    total_confirmed = 0
    for d, cell in sorted(by_domain.items()):
        ratio = (cell["confirmed"] / cell["total"]) if cell["total"] > 0 else 0.0
        cells.append(DomainCellDTO(
            domain=d,
            total=cell["total"],
            by_kind=dict(cell["by_kind"]),
            confirmed=cell["confirmed"],
            draft=cell["draft"],
            unmapped=cell["unmapped"],
            orphan_count=cell["orphan_count"],
            recent_count=cell["recent_count"],
            confirmed_ratio=round(ratio, 3),
        ))
        total_all += cell["total"]
        total_confirmed += cell["confirmed"]

    summary = CoverageSummaryDTO(
        total=total_all,
        confirmed_ratio=round((total_confirmed / total_all) if total_all > 0 else 0.0, 3),
        stalled_domains=[c.domain for c in cells if c.confirmed_ratio < 0.3 and c.total >= 5],
    )

    return CoverageResponseDTO(repo_id=repo_id, domains=cells, summary=summary)


# ---------------------------------------------------------------------------
# Priority — 한 도메인 안의 우선 처리 대상 entity list
# ---------------------------------------------------------------------------
_VALID_LENS = {"draft", "orphan", "recent"}


@router.get("/{repo_id}/graph/coverage/{domain}/priority", response_model=PriorityResponseDTO)
def get_priority(
    repo_id: str,
    domain: str,
    lens: str = Query("draft,orphan,recent", description="comma-separated lens: draft,orphan,recent"),
    limit: int = Query(50, ge=1, le=500),
    recent_days: int = Query(7, ge=1, le=90),
) -> PriorityResponseDTO:
    lens_set = {l.strip() for l in lens.split(",") if l.strip()}
    invalid = lens_set - _VALID_LENS
    if invalid:
        raise HTTPException(status_code=400, detail=f"invalid lens: {sorted(invalid)} (allowed: {sorted(_VALID_LENS)})")

    with session_scope() as s:
        # term + action both filtered by domain
        terms = s.execute(
            select(BusinessTermRow).where(
                BusinessTermRow.repo_id == repo_id,
                BusinessTermRow.domain == domain,
            )
        ).scalars().all()
        actions = s.execute(
            select(ActionRow).where(
                ActionRow.repo_id == repo_id,
                ActionRow.domain == domain,
            )
        ).scalars().all()
        # CodeType: domain 은 package 마지막 2 segment 로 derive (coverage 와 일관)
        all_cts = s.execute(
            select(CodeTypeRow).where(CodeTypeRow.repo_id == repo_id)
        ).scalars().all()
        code_types = [
            ct for ct in all_cts
            if _ct_domain(ct.package) == domain
        ]

        tr_term_fqns = {r for r, in s.execute(
            select(TypeRealizationRow.term_fqn).where(TypeRealizationRow.repo_id == repo_id).distinct()
        ).all()}
        action_real_fqns = {r for r, in s.execute(
            select(RealizationRow.action_fqn).where(RealizationRow.repo_id == repo_id).distinct()
        ).all()}
        action_anchor_fqns = {r for r, in s.execute(
            select(AnchorBindingRow.target_action_fqn).where(AnchorBindingRow.repo_id == repo_id).distinct()
        ).all()}
        ct_mapped_fqns = {r for r, in s.execute(
            select(TypeRealizationRow.code_type_fqn).where(TypeRealizationRow.repo_id == repo_id).distinct()
        ).all()}

    recent_term_ids = recently_changed_ids(repo_id, "term", since_days=recent_days) if "recent" in lens_set else set()
    recent_action_ids = recently_changed_ids(repo_id, "action", since_days=recent_days) if "recent" in lens_set else set()
    recent_ct_ids = recently_changed_ids(repo_id, "code_type", since_days=recent_days) if "recent" in lens_set else set()

    candidates: list[PriorityEntityDTO] = []

    for t in terms:
        reasons: list[str] = []
        if "draft" in lens_set and not t.confirmed:
            reasons.append("draft")
        if "orphan" in lens_set and t.fqn not in tr_term_fqns:
            reasons.append("orphan")
        if "recent" in lens_set and t.fqn in recent_term_ids:
            reasons.append("recent")
        if not reasons:
            continue
        score = _score_term(t, reasons)
        candidates.append(PriorityEntityDTO(
            kind="term",
            fqn=t.fqn,
            label=t.label,
            verification_level=None,
            confirmed=t.confirmed,
            priority_score=score,
            reasons=reasons,
        ))

    for a in actions:
        reasons = []
        is_confirmed = (a.verification_level in ("body_anchored", "sim_verified", "pr_proven", "signature_locked")) and bool(a.confirmed_by)
        if "draft" in lens_set and not is_confirmed:
            reasons.append("draft")
        if "orphan" in lens_set and a.fqn not in action_real_fqns and a.fqn not in action_anchor_fqns:
            reasons.append("orphan")
        if "recent" in lens_set and a.fqn in recent_action_ids:
            reasons.append("recent")
        if not reasons:
            continue
        score = _score_action(a, reasons)
        candidates.append(PriorityEntityDTO(
            kind="action",
            fqn=a.fqn,
            label=a.label,
            verification_level=a.verification_level,
            confirmed=is_confirmed,
            priority_score=score,
            reasons=reasons,
        ))

    for ct in code_types:
        reasons = []
        is_mapped = ct.fqn in ct_mapped_fqns
        if "draft" in lens_set and not is_mapped:
            reasons.append("draft")
        if "orphan" in lens_set and not is_mapped:
            reasons.append("orphan")
        if "recent" in lens_set and ct.fqn in recent_ct_ids:
            reasons.append("recent")
        if not reasons:
            continue
        score = _score_code_type(ct, reasons)
        candidates.append(PriorityEntityDTO(
            kind="code_type",
            fqn=ct.fqn,
            label=ct.simple_name or ct.fqn.split(".")[-1],
            verification_level=None,
            confirmed=is_mapped,
            priority_score=score,
            reasons=reasons,
        ))

    candidates.sort(key=lambda c: -c.priority_score)
    sliced = candidates[:limit]

    return PriorityResponseDTO(
        domain=domain,
        lens=sorted(lens_set),
        entities=sliced,
        total_match=len(candidates),
    )


def _score_term(t: Any, reasons: list[str]) -> float:
    """간단 score: orphan + draft 같이 있으면 가산, recent 는 약간 boost."""
    score = 0.0
    if "draft" in reasons:  score += 3.0
    if "orphan" in reasons: score += 4.0
    if "recent" in reasons: score += 1.5
    # composite term + draft 면 부담 큼 (구성요소 다수)
    if "draft" in reasons and getattr(t, "kind", "") == "composite":
        score += 1.0
    return round(score, 2)


def _score_action(a: Any, reasons: list[str]) -> float:
    score = 0.0
    if "draft" in reasons:
        score += 3.5
        # verification level lower = higher priority
        if a.verification_level in ("unmapped", "draft"):
            score += 1.5
    if "orphan" in reasons: score += 4.0
    if "recent" in reasons: score += 1.5
    return round(score, 2)


def _score_code_type(ct: Any, reasons: list[str]) -> float:
    score = 0.0
    if "draft" in reasons:  score += 2.5
    if "orphan" in reasons: score += 3.0
    if "recent" in reasons: score += 1.5
    # domain role 가 우선순위 가산 — framework/infra 는 mapping 우선순위 ↓
    role = getattr(ct, "role", "unknown")
    if role == "domain":
        score += 1.5
    return round(score, 2)


def _ct_domain(package: str | None) -> str:
    """CodeType 의 domain = package 마지막 2 segment. coverage 와 일치."""
    pkg = package or ""
    if pkg.count(".") >= 1:
        return ".".join(pkg.split(".")[-2:])
    return pkg or "(unknown)"


__all__ = ["router"]
