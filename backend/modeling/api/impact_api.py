"""FastAPI router — Ontology graph Impact mode (focus 노드 + 양방향 ripple).

REST:
- GET /api/ontology/repos/{repo_id}/graph/impact?focus={fqn}&focus_kind={...}
    focus 중심 양방향 BFS. match_kind 5단계 strength 기반 risk score.
- GET /api/ontology/repos/{repo_id}/graph/impact/expand-method?code_type_fqn={...}
    특정 class 의 method 목록 (lazy expand).

알고리즘:
- focus 가 term 이면 → 관련 action 들로 promote
- focus 가 action 이면 → primary realization 의 method 시작
- focus 가 code_method 이면 → 그대로
- 양방향 BFS: backward = callers (변경 영향 받는 caller method + 그 action 들 + term 들),
              forward = action 의 sub_actions / param terms (변경하는 행동의 영향 전파)
- match_kind 5단계 (receiver_exact 0.95 / receiver_short 0.85 / runtime_type 0.85 /
  package_proximity 0.70 / name_only 0.50) edge strength
- risk_score = base(10) × strength / (distance+1)
"""
from __future__ import annotations

import logging
from collections import deque
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow
from backend.modeling.code_layer.store import CodeLayerStore
from backend.modeling.domain_layer.orm import BusinessRuleRow, BusinessTermRow
from backend.modeling.mapping_layer.orm import (
    ActionRow, AnchorBindingRow, RealizationRow,
)
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/repos", tags=["ontology-impact"])


_MATCH_STRENGTH = {
    "receiver_exact":    0.95,
    "receiver_short":    0.85,
    "runtime_type":      0.85,
    "package_proximity": 0.70,
    "name_only":         0.50,
}


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------
class ImpactNodeDTO(BaseModel):
    id: str                          # composite "kind|fqn"
    fqn: str
    kind: str                        # term / action / code_type / code_method
    label: str
    distance: int                    # focus 로부터 hop
    direction: str                   # "focus" / "forward" / "backward" / "both"
    risk_score: float                # 0~10
    confirmed: bool = False
    extra: dict[str, Any] = {}


class ImpactEdgeDTO(BaseModel):
    id: str
    source: str                      # composite id
    target: str                      # composite id
    kind: str                        # call / realization / declared_on / param / contains
    match_kind: str | None = None    # 5단계
    strength: float = 1.0
    direction: str                   # "forward" / "backward"


class ImpactResponseDTO(BaseModel):
    repo_id: str
    focus: dict[str, str]            # {kind, fqn, label}
    nodes: list[ImpactNodeDTO]
    edges: list[ImpactEdgeDTO]
    forward_count: int
    backward_count: int
    risk_top: list[dict[str, Any]]   # [{fqn, kind, risk_score}] sorted desc
    re_verify_targets: list[dict[str, Any]]   # confirmed anchor 가진 affected method 들
    truncated_at_hop: int | None = None
    expand_method_targets: list[str] = []     # 미완전 펴진 code_type fqn 들


class MethodNodeDTO(BaseModel):
    fqn: str
    name: str
    parent_type_fqn: str
    return_type: str
    role: str
    line_start: int | None = None
    line_end: int | None = None
    has_anchor: bool = False         # AnchorBinding 있나
    realizes_action_fqns: list[str] = []   # 이 method 가 realize 하는 action


class ExpandMethodResponseDTO(BaseModel):
    code_type_fqn: str
    methods: list[MethodNodeDTO]


# ---------------------------------------------------------------------------
# Impact 엔드포인트
# ---------------------------------------------------------------------------
@router.get("/{repo_id}/graph/impact", response_model=ImpactResponseDTO)
def get_impact(
    repo_id: str,
    focus: str = Query(..., description="focus entity fqn"),
    focus_kind: str = Query(..., description="action / term / code_type / code_method"),
    hops: int = Query(2, ge=1, le=5),
    direction: str = Query("both", description="forward / backward / both"),
    min_strength: float = Query(0.5, ge=0.0, le=1.0),
    include_methods: bool = Query(False, description="True 면 affected method 노드까지 포함"),
) -> ImpactResponseDTO:
    if direction not in ("both", "forward", "backward"):
        raise HTTPException(status_code=400, detail=f"invalid direction: {direction}")
    if focus_kind not in ("action", "term", "code_type", "code_method"):
        raise HTTPException(status_code=400, detail=f"invalid focus_kind: {focus_kind}")

    builder = _ImpactBuilder(
        repo_id=repo_id,
        focus_fqn=focus,
        focus_kind=focus_kind,
        hops=hops,
        direction=direction,
        min_strength=min_strength,
        include_methods=include_methods,
    )
    return builder.build()


# ---------------------------------------------------------------------------
# Expand-method 엔드포인트 (lazy)
# ---------------------------------------------------------------------------
@router.get("/{repo_id}/graph/impact/expand-method", response_model=ExpandMethodResponseDTO)
def expand_method(
    repo_id: str,
    code_type_fqn: str = Query(..., description="code_type FQN"),
    limit: int = Query(50, ge=1, le=500),
) -> ExpandMethodResponseDTO:
    with session_scope() as s:
        methods = s.execute(
            select(CodeMethodRow).where(
                CodeMethodRow.repo_id == repo_id,
                CodeMethodRow.parent_type_fqn == code_type_fqn,
            ).limit(limit)
        ).scalars().all()
        method_fqns = {m.fqn for m in methods}
        # method 별 realizes_action
        reals = s.execute(
            select(RealizationRow.action_fqn, RealizationRow.code_method_fqn).where(
                RealizationRow.repo_id == repo_id,
                RealizationRow.code_method_fqn.in_(method_fqns),
            )
        ).all() if method_fqns else []
        anchor_method_fqns = {r for r, in s.execute(
            select(AnchorBindingRow.code_method_fqn).where(
                AnchorBindingRow.repo_id == repo_id,
                AnchorBindingRow.code_method_fqn.in_(method_fqns) if method_fqns else (AnchorBindingRow.code_method_fqn == ""),
            ).distinct()
        ).all()} if method_fqns else set()

    realizes_map: dict[str, list[str]] = {}
    for action_fqn, method_fqn in reals:
        realizes_map.setdefault(method_fqn, []).append(action_fqn)

    return ExpandMethodResponseDTO(
        code_type_fqn=code_type_fqn,
        methods=[
            MethodNodeDTO(
                fqn=m.fqn,
                name=m.name,
                parent_type_fqn=m.parent_type_fqn,
                return_type=m.return_type,
                role=m.role,
                line_start=m.line_start,
                line_end=m.line_end,
                has_anchor=m.fqn in anchor_method_fqns,
                realizes_action_fqns=realizes_map.get(m.fqn, []),
            )
            for m in methods
        ],
    )


# ---------------------------------------------------------------------------
# Internal builder
# ---------------------------------------------------------------------------
class _ImpactBuilder:
    def __init__(
        self, *, repo_id: str, focus_fqn: str, focus_kind: str, hops: int,
        direction: str, min_strength: float, include_methods: bool,
    ):
        self.repo_id = repo_id
        self.focus_fqn = focus_fqn
        self.focus_kind = focus_kind
        self.hops = hops
        self.direction = direction
        self.min_strength = min_strength
        self.include_methods = include_methods

        # 누적 상태
        self.nodes: dict[str, ImpactNodeDTO] = {}
        self.edges: list[ImpactEdgeDTO] = []
        self.expand_targets: set[str] = set()
        self.forward_ids: set[str] = set()
        self.backward_ids: set[str] = set()
        self.truncated = False

        # 데이터 캐시 (한 빌드 안에서 재사용)
        self._action_cache: dict[str, ActionRow] = {}
        self._term_cache: dict[str, BusinessTermRow] = {}
        self._code_type_cache: dict[str, CodeTypeRow] = {}
        self._method_cache: dict[str, CodeMethodRow] = {}
        self._code_store = CodeLayerStore()

    def build(self) -> ImpactResponseDTO:
        # 1. focus entity 정보 가져오기
        focus_label = self._resolve_label(self.focus_kind, self.focus_fqn)
        if focus_label is None:
            raise HTTPException(status_code=404, detail=f"focus not found: {self.focus_kind}={self.focus_fqn!r}")
        focus_node_id = f"{self.focus_kind}|{self.focus_fqn}"
        self.nodes[focus_node_id] = ImpactNodeDTO(
            id=focus_node_id, fqn=self.focus_fqn, kind=self.focus_kind,
            label=focus_label, distance=0, direction="focus", risk_score=10.0,
            confirmed=self._is_confirmed(self.focus_kind, self.focus_fqn),
        )

        # 2. 시작 노드 결정 (term/action 은 method 로 promote 가능)
        seeds: list[tuple[str, str, int, str]] = [(self.focus_kind, self.focus_fqn, 0, "focus")]
        if self.focus_kind == "term":
            # term 이면 → declared_on=term 인 action 들 + type_realization 으로 매핑된 code_type 들로 확장
            for a in self._actions_for_term(self.focus_fqn):
                self._add_or_update(a.fqn, "action", a.label, distance=1, direction="forward",
                                     edge_kind="declared_on", strength=0.9,
                                     source_id=focus_node_id, target_id=f"action|{a.fqn}")
                seeds.append(("action", a.fqn, 1, "forward"))
        elif self.focus_kind == "code_type":
            # method 들로 promote (limit)
            for m in self._methods_for_code_type(self.focus_fqn, limit=10):
                self._add_or_update(m.fqn, "code_method", m.name, distance=1, direction="forward",
                                     edge_kind="contains", strength=1.0,
                                     source_id=focus_node_id, target_id=f"code_method|{m.fqn}")
                if self.include_methods:
                    seeds.append(("code_method", m.fqn, 1, "forward"))

        # 3. BFS
        q = deque([s for s in seeds if s[0] != self.focus_kind or s[1] != self.focus_fqn])
        # 위 promote 단계에서 추가된 distance=1 노드들로 BFS 시작
        # focus 자체에서도 같은 kind 다음 hop 진행 가능
        if self.focus_kind in ("action", "code_method"):
            q.appendleft((self.focus_kind, self.focus_fqn, 0, "focus"))

        visited: set[tuple[str, str]] = set()
        while q:
            kind, fqn, dist, dir_tag = q.popleft()
            if (kind, fqn) in visited:
                continue
            visited.add((kind, fqn))

            if dist >= self.hops:
                # 이 노드 자체는 추가됐지만 더 펴지 않음
                if kind == "code_type":
                    self.expand_targets.add(fqn)
                continue

            # backward 확장 — 변경 영향 받는 자 (회귀 검증 대상)
            if self.direction in ("both", "backward"):
                for back in self._backward_neighbors(kind, fqn):
                    nb_kind, nb_fqn, nb_label, ek, strength, match_kind = back
                    if strength < self.min_strength:
                        continue
                    nid = self._add_or_update(
                        nb_fqn, nb_kind, nb_label,
                        distance=dist + 1, direction="backward",
                        edge_kind=ek, strength=strength, match_kind=match_kind,
                        source_id=f"{nb_kind}|{nb_fqn}",
                        target_id=f"{kind}|{fqn}",  # nb → focus 방향
                    )
                    if nid not in visited:
                        q.append((nb_kind, nb_fqn, dist + 1, "backward"))

            # forward 확장 — 변경 행위가 영향 주는 자
            if self.direction in ("both", "forward"):
                for fwd in self._forward_neighbors(kind, fqn):
                    nb_kind, nb_fqn, nb_label, ek, strength, match_kind = fwd
                    if strength < self.min_strength:
                        continue
                    nid = self._add_or_update(
                        nb_fqn, nb_kind, nb_label,
                        distance=dist + 1, direction="forward",
                        edge_kind=ek, strength=strength, match_kind=match_kind,
                        source_id=f"{kind}|{fqn}",
                        target_id=f"{nb_kind}|{nb_fqn}",
                    )
                    if nid not in visited:
                        q.append((nb_kind, nb_fqn, dist + 1, "forward"))

        # 4. 재검증 대상 추출 — affected method 중 anchor 가 있는 것
        re_verify: list[dict[str, Any]] = []
        with session_scope() as s:
            method_fqns = [n.fqn for n in self.nodes.values() if n.kind == "code_method"]
            if method_fqns:
                anchor_fqns = {r for r, in s.execute(
                    select(AnchorBindingRow.code_method_fqn).where(
                        AnchorBindingRow.repo_id == self.repo_id,
                        AnchorBindingRow.code_method_fqn.in_(method_fqns),
                        AnchorBindingRow.confirmed == True,  # noqa: E712
                    ).distinct()
                ).all()}
                for n in self.nodes.values():
                    if n.kind == "code_method" and n.fqn in anchor_fqns:
                        re_verify.append({
                            "fqn": n.fqn,
                            "label": n.label,
                            "distance": n.distance,
                            "risk_score": n.risk_score,
                        })
        re_verify.sort(key=lambda x: -x["risk_score"])

        # 5. risk_top 정렬
        risk_top = sorted(
            [{"id": n.id, "fqn": n.fqn, "kind": n.kind, "label": n.label, "risk_score": n.risk_score}
             for n in self.nodes.values() if n.id != focus_node_id],
            key=lambda x: -x["risk_score"],
        )[:20]

        return ImpactResponseDTO(
            repo_id=self.repo_id,
            focus={"kind": self.focus_kind, "fqn": self.focus_fqn, "label": focus_label},
            nodes=list(self.nodes.values()),
            edges=self.edges,
            forward_count=len(self.forward_ids),
            backward_count=len(self.backward_ids),
            risk_top=risk_top,
            re_verify_targets=re_verify,
            truncated_at_hop=self.hops if self.truncated else None,
            expand_method_targets=sorted(self.expand_targets),
        )

    # ---- helpers ─────────────────────────────────────────────────
    def _add_or_update(
        self, fqn: str, kind: str, label: str, *,
        distance: int, direction: str, edge_kind: str, strength: float,
        match_kind: str | None = None, source_id: str, target_id: str,
    ) -> str:
        nid = f"{kind}|{fqn}"
        existing = self.nodes.get(nid)
        risk = round(10.0 * strength / (distance + 1), 2)
        if existing is None:
            self.nodes[nid] = ImpactNodeDTO(
                id=nid, fqn=fqn, kind=kind, label=label,
                distance=distance, direction=direction,
                risk_score=risk,
                confirmed=self._is_confirmed(kind, fqn),
            )
        else:
            # 더 가까운 hop / 더 높은 risk 면 update. direction 충돌은 "both"
            if distance < existing.distance:
                existing.distance = distance
            if risk > existing.risk_score:
                existing.risk_score = risk
            if existing.direction != direction and existing.direction != "focus":
                existing.direction = "both"

        # edge 누적 (방향 보존)
        eid = f"{source_id}->{target_id}|{edge_kind}"
        if not any(e.id == eid for e in self.edges):
            self.edges.append(ImpactEdgeDTO(
                id=eid, source=source_id, target=target_id,
                kind=edge_kind, match_kind=match_kind, strength=strength,
                direction=direction,
            ))

        if direction == "forward":
            self.forward_ids.add(nid)
        elif direction == "backward":
            self.backward_ids.add(nid)
        return nid

    def _resolve_label(self, kind: str, fqn: str) -> str | None:
        with session_scope() as s:
            if kind == "action":
                r = s.execute(select(ActionRow).where(ActionRow.repo_id == self.repo_id, ActionRow.fqn == fqn)).scalar_one_or_none()
                return r.label if r else None
            if kind == "term":
                r = s.execute(select(BusinessTermRow).where(BusinessTermRow.repo_id == self.repo_id, BusinessTermRow.fqn == fqn)).scalar_one_or_none()
                return r.label if r else None
            if kind == "code_type":
                r = s.execute(select(CodeTypeRow).where(CodeTypeRow.repo_id == self.repo_id, CodeTypeRow.fqn == fqn)).scalar_one_or_none()
                return r.simple_name if r else None
            if kind == "code_method":
                r = s.execute(select(CodeMethodRow).where(CodeMethodRow.repo_id == self.repo_id, CodeMethodRow.fqn == fqn)).scalar_one_or_none()
                return r.name if r else None
        return None

    def _is_confirmed(self, kind: str, fqn: str) -> bool:
        with session_scope() as s:
            if kind == "action":
                r = s.execute(select(ActionRow.confirmed_by).where(ActionRow.repo_id == self.repo_id, ActionRow.fqn == fqn)).scalar_one_or_none()
                return bool(r)
            if kind == "term":
                r = s.execute(select(BusinessTermRow.confirmed).where(BusinessTermRow.repo_id == self.repo_id, BusinessTermRow.fqn == fqn)).scalar_one_or_none()
                return bool(r)
        return False

    def _actions_for_term(self, term_fqn: str) -> list[ActionRow]:
        with session_scope() as s:
            return list(s.execute(
                select(ActionRow).where(
                    ActionRow.repo_id == self.repo_id,
                    ActionRow.declared_on_term == term_fqn,
                )
            ).scalars().all())

    def _methods_for_code_type(self, ct_fqn: str, limit: int = 10) -> list[CodeMethodRow]:
        with session_scope() as s:
            return list(s.execute(
                select(CodeMethodRow).where(
                    CodeMethodRow.repo_id == self.repo_id,
                    CodeMethodRow.parent_type_fqn == ct_fqn,
                ).limit(limit)
            ).scalars().all())

    def _backward_neighbors(self, kind: str, fqn: str) -> list[tuple[str, str, str, str, float, str | None]]:
        """이 entity 에 의존하는 자들. 반환: [(neighbor_kind, neighbor_fqn, label, edge_kind, strength, match_kind)]"""
        out = []
        if kind == "code_method":
            # callers (via match_kind) — sec2 store 활용
            try:
                pairs = self._code_store.get_method_callers_with_match(fqn, repo_id=self.repo_id)
            except Exception:
                pairs = []
            for cs, mk in pairs:
                strength = _MATCH_STRENGTH.get(mk, 0.5)
                # caller method 의 name 가져오기
                label = self._resolve_label("code_method", cs.caller_method_fqn) or cs.caller_method_fqn.split(".")[-1]
                out.append(("code_method", cs.caller_method_fqn, label, "call", strength, mk))
            # 이 method 를 realize 하는 action 들도 backward (action 이 method 사용)
            with session_scope() as s:
                rows = s.execute(
                    select(RealizationRow.action_fqn).where(
                        RealizationRow.repo_id == self.repo_id,
                        RealizationRow.code_method_fqn == fqn,
                    ).distinct()
                ).all()
                for (action_fqn,) in rows:
                    label = self._resolve_label("action", action_fqn) or action_fqn.split(".")[-1]
                    out.append(("action", action_fqn, label, "realization", 1.0, None))
        elif kind == "action":
            # action 을 ref 하는 BR
            with session_scope() as s:
                br_rows = s.execute(
                    select(BusinessRuleRow).where(BusinessRuleRow.repo_id == self.repo_id)
                ).scalars().all()
                for br in br_rows:
                    # enforced_by 에 이 action 의 realization method 가 있으면 backward
                    try:
                        import json as _json
                        enforced_by = _json.loads(br.enforced_by_json) if br.enforced_by_json else []
                    except Exception:
                        enforced_by = []
                    # heuristic — 이 action 의 primary method 가 enforced_by 에 있나
                    real_rows = s.execute(
                        select(RealizationRow.code_method_fqn).where(
                            RealizationRow.repo_id == self.repo_id,
                            RealizationRow.action_fqn == fqn,
                        )
                    ).all()
                    real_methods = {r for (r,) in real_rows}
                    if any(m in real_methods for m in enforced_by):
                        out.append(("business_rule", br.fqn, br.fqn.split(".")[-1], "enforced_by", 0.9, None))
        elif kind == "term":
            # term 을 ref 하는 actions / BR / type_realizations
            actions = self._actions_for_term(fqn)
            for a in actions:
                out.append(("action", a.fqn, a.label, "declared_on", 0.9, None))
        return out

    def _forward_neighbors(self, kind: str, fqn: str) -> list[tuple[str, str, str, str, float, str | None]]:
        """이 entity 가 의존하는 자들. 변경의 영향 전파 방향."""
        out = []
        if kind == "code_method":
            # callees (이 method 가 호출하는 것) — call_sites 의 callee_simple_name 기반 best-effort
            from backend.modeling.code_layer.orm import CallSiteRow
            with session_scope() as s:
                callsites = s.execute(
                    select(CallSiteRow).where(
                        CallSiteRow.repo_id == self.repo_id,
                        CallSiteRow.caller_method_fqn == fqn,
                    )
                ).scalars().all()
                for cs in callsites:
                    # callee_simple_name → CodeMethodRow.name 매칭 (best-effort, 정확도 한계)
                    target_methods = s.execute(
                        select(CodeMethodRow).where(
                            CodeMethodRow.repo_id == self.repo_id,
                            CodeMethodRow.name == cs.callee_simple_name,
                        ).limit(3)
                    ).scalars().all()
                    for tm in target_methods:
                        out.append(("code_method", tm.fqn, tm.name, "call", 0.6, "name_only"))
        elif kind == "action":
            # action realize 하는 method 들 (forward = 변경 영향 받는 코드)
            with session_scope() as s:
                rows = s.execute(
                    select(RealizationRow).where(
                        RealizationRow.repo_id == self.repo_id,
                        RealizationRow.action_fqn == fqn,
                    )
                ).scalars().all()
                for r in rows:
                    label = self._resolve_label("code_method", r.code_method_fqn) or r.code_method_fqn.split(".")[-1]
                    out.append(("code_method", r.code_method_fqn, label, "realization", 1.0, None))
        return out


__all__ = ["router"]
