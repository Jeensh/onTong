"""FastAPI router — /api/ontology/repos/{repo_id}/modules — 패키지 트리 (V7 IA).

좌측 navigator 가 하드코딩 mock 카드 (SCM/Quality/Production/Logistics) 대신
실제 Java 패키지 계층 + 각 노드의 inventory (CodeType/Term/Action 카운트) 를 표시.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.modeling.code_layer.store import CodeLayerStore
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.mapping_layer.store import MappingLayerStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/repos", tags=["ontology-modules"])


class ModuleNode(BaseModel):
    path: str = Field(description="dotted full path, e.g. 'com.example.slabdesign.feature.sd'")
    name: str = Field(description="last segment, e.g. 'sd'")
    direct_classes: int = Field(description="이 패키지에 직접 속한 CodeType 수")
    total_classes: int = Field(description="이 패키지 + 하위 모든 CodeType 수")
    direct_actions: int = 0
    direct_terms: int = 0
    confirmed_ratio: float = Field(default=0.0, description="confirmed=True 비율 (0~1)")
    children: list["ModuleNode"] = Field(default_factory=list)


class ModulesResponse(BaseModel):
    repo_id: str
    root: ModuleNode
    flat_count: int = Field(description="총 CodeType 수 (sanity check)")


@router.get("/{repo_id}/modules", response_model=ModulesResponse)
def get_modules(
    repo_id: str,
    min_classes: int = Query(0, ge=0, description="이만큼 미만 직접/하위 클래스 가진 패키지 노드 제외"),
) -> ModulesResponse:
    code_store = CodeLayerStore()
    # R4-T1.1 perf — methods/anchors 안 로드 (modules tree 는 카운트만 필요)
    types_raw = code_store.list_types_summary(repo_id=repo_id)
    if not types_raw:
        raise HTTPException(status_code=404, detail=f"no CodeTypes for repo_id={repo_id}")
    # 호환: types 는 dict list 로, 아래에서 ct.fqn / ct.package 대신 ct["fqn"] 등 사용
    types = types_raw

    # Term/Action 의 declared_on / parent 정보로 패키지 별 inventory 계산
    domain_store = DomainLayerStore()
    mapping_store = MappingLayerStore()
    terms = domain_store.list_terms(repo_id=repo_id)
    actions = mapping_store.list_actions(repo_id=repo_id)

    # 어느 CodeType.fqn 이 어떤 term 에 매핑되어 있는가 — TypeRealization 으로
    # (R4-T1.1 perf fix — list_type_realizations 한 번만 fetch, in-memory lookup.
    # 이전엔 CodeType 마다 다시 호출 → 5K class repo 에서 15s.)
    all_trs = mapping_store.list_type_realizations(repo_id=repo_id)
    code_to_term: dict[str, str] = {}
    primary_confirmed: set[str] = set()    # PRIMARY + confirmed 인 code_type fqn
    for tr in all_trs:
        if tr.scope.value == "primary":
            code_to_term[tr.code_type_fqn] = tr.term_fqn
            if tr.confirmed:
                primary_confirmed.add(tr.code_type_fqn)

    # 각 action 의 realization 의 parent CodeType 구하기 (action 이 어느 패키지에 "속하나")
    action_parents: dict[str, list[str]] = {}  # action_fqn → [code_type_fqn]
    for a in actions:
        for r in a.realizations:
            base = r.code_method_fqn.split("(", 1)[0].split("@line", 1)[0]
            if "." in base:
                parent = base.rsplit(".", 1)[0]
                action_parents.setdefault(a.fqn, []).append(parent)

    # 트리 빌드 — segment 별
    root = _PkgNode("", "")
    for ct in types:
        pkg = ct["package"] or "(default)"
        node = _ensure_path(root, pkg)
        node.direct_classes.append(ct["fqn"])
        if ct["fqn"] in primary_confirmed:
            node.confirmed_classes += 1
        # term 카운트 — 이 CodeType 이 primary mapping 인 term
        if ct["fqn"] in code_to_term:
            node.direct_terms.add(code_to_term[ct["fqn"]])

    # action 카운트 — action 의 realization parent 가 어느 pkg 에 들어있나
    code_pkg: dict[str, str] = {ct["fqn"]: (ct["package"] or "(default)") for ct in types}
    for a_fqn, parents in action_parents.items():
        for p in parents:
            pkg = code_pkg.get(p)
            if pkg:
                _ensure_path(root, pkg).direct_actions.add(a_fqn)
                break  # 한 action 은 한 pkg 에만 카운트

    # 변환 + min_classes 필터 (하위 합산 후 적용)
    out_root = _to_dto(root, min_classes)
    return ModulesResponse(
        repo_id=repo_id,
        root=out_root,
        flat_count=len(types),
    )


# ---------------------------------------------------------------------------
# 내부 트리 빌드
# ---------------------------------------------------------------------------
class _PkgNode:
    __slots__ = ("path", "name", "children", "direct_classes",
                 "direct_terms", "direct_actions", "confirmed_classes")

    def __init__(self, path: str, name: str) -> None:
        self.path = path
        self.name = name
        self.children: dict[str, _PkgNode] = {}
        self.direct_classes: list[str] = []
        self.direct_terms: set[str] = set()
        self.direct_actions: set[str] = set()
        self.confirmed_classes: int = 0


def _ensure_path(root: _PkgNode, dotted: str) -> _PkgNode:
    if not dotted or dotted == "(default)":
        return root
    cur = root
    parts = dotted.split(".")
    for i, seg in enumerate(parts):
        if seg not in cur.children:
            full = ".".join(parts[: i + 1])
            cur.children[seg] = _PkgNode(full, seg)
        cur = cur.children[seg]
    return cur


def _total_classes(node: _PkgNode) -> int:
    return len(node.direct_classes) + sum(_total_classes(c) for c in node.children.values())


def _to_dto(node: _PkgNode, min_classes: int) -> ModuleNode:
    children_dtos: list[ModuleNode] = []
    for c in sorted(node.children.values(), key=lambda x: x.name):
        if _total_classes(c) < min_classes:
            continue
        children_dtos.append(_to_dto(c, min_classes))

    direct = len(node.direct_classes)
    total = direct + sum(c.total_classes for c in children_dtos)
    confirmed_ratio = (node.confirmed_classes / direct) if direct else 0.0

    return ModuleNode(
        path=node.path or "(root)",
        name=node.name or "(root)",
        direct_classes=direct,
        total_classes=total,
        direct_actions=len(node.direct_actions),
        direct_terms=len(node.direct_terms),
        confirmed_ratio=confirmed_ratio,
        children=children_dtos,
    )


# ---------------------------------------------------------------------------
# 패키지 별 CodeType list (좌측 트리에서 패키지 클릭 시)
# ---------------------------------------------------------------------------
class CodeTypeInventoryDTO(BaseModel):
    fqn: str
    simple_name: str
    role: str
    kind: str
    has_term: bool = False
    term_fqn: str | None = None
    method_count: int


@router.get("/{repo_id}/modules/inventory", response_model=list[CodeTypeInventoryDTO])
def get_inventory(
    repo_id: str,
    package: str = Query(..., description="dotted full path"),
    recursive: bool = Query(False),
) -> list[CodeTypeInventoryDTO]:
    code_store = CodeLayerStore()
    mapping_store = MappingLayerStore()

    # R4-T1.1 perf — summary fetch (method body 안 로드)
    types = code_store.list_types_summary(repo_id=repo_id)
    primary_map: dict[str, str] = {
        tr.code_type_fqn: tr.term_fqn
        for tr in mapping_store.list_type_realizations(repo_id=repo_id)
        if tr.scope.value == "primary"
    }

    out: list[CodeTypeInventoryDTO] = []
    for ct in types:
        pkg = ct["package"] or ""
        match = (pkg == package) if not recursive else (
            pkg == package or pkg.startswith(package + ".")
        )
        if not match:
            continue
        out.append(CodeTypeInventoryDTO(
            fqn=ct["fqn"],
            simple_name=ct["simple_name"],
            role=ct["role"],
            kind=ct["kind"],
            has_term=ct["fqn"] in primary_map,
            term_fqn=primary_map.get(ct["fqn"]),
            method_count=ct["method_count"],
        ))
    out.sort(key=lambda x: x.simple_name)
    return out
