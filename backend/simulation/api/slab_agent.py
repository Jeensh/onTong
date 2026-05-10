"""Slab 3D 뷰어 호환 라우터 — ontology 기반 재구현 (STEP 3c-D, 2026-05-10).

이전 (commit 2a346e3 이전):
- `/api/simulation/slab/calculate` → backend.simulation.mock.scenarios.slab_size_simulator
- `/api/simulation/slab/constraints` → 같은 모듈
- 위 모듈은 main 정렬 시 삭제됨 → 두 endpoint 가 ImportError 로 HTTP 500 반환

현재 (STEP 3c-D):
- 옛 endpoint 자체는 보존 (사용자 지시 "지우진말고" + frontend 호환).
- 내부 구현을 **`backend.modeling.api.ontology_query.OntologyQueryClientImpl` 기반**으로 재작성.
  * `/constraints` — ontology 의 atomic facets (range/unit/enum) 를 slab 관련 키로 필터링해 반환.
  * `/calculate` — spec 03 의 POST /api/simulation/runs 로 redirect 안내 + 즉시 echo (deprecated marker).
- 별도 mock 데이터 / 임시 Python 코드 의존성 0건.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation/slab", tags=["slab-3d"])


# ─── ontology client lazy singleton (spec_router 와 동일 패턴) ───


_ontology_client: Optional[object] = None


def _get_ontology_client() -> object:
    global _ontology_client
    if _ontology_client is not None:
        return _ontology_client
    try:
        from backend.modeling.api.ontology_query import OntologyQueryClientImpl

        _ontology_client = OntologyQueryClientImpl()
        logger.info("slab_agent: OntologyQueryClientImpl wired")
    except Exception as exc:  # noqa: BLE001
        logger.warning("slab_agent: OntologyQueryClientImpl 인스턴스화 실패 (%s)", exc)

        class _Null:
            def list_terms(self, *a, **k): return []
            def get_term(self, fqn): return None
            def list_actions(self, *a, **k): return []

        _ontology_client = _Null()
    return _ontology_client


# ─── /constraints — ontology 의 atomic facets 모음 ─────────────────


_SLAB_KEYWORDS = ("slab", "thickness", "width", "length", "weight", "diameter")


@router.get("/constraints")
async def get_slab_constraints() -> dict[str, Any]:
    """slab 관련 atomic 의 range/unit/enum 을 ontology 에서 수집.

    응답 형식:
        { atomic_fqn: {min, max, unit, enum} }

    이전 mock_simulator 의 hardcoded constraints 를 ontology atomic facets 로 대체.
    """
    ont = _get_ontology_client()
    try:
        all_terms = ont.list_terms() or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("list_terms() 실패 — %s", exc)
        all_terms = []

    constraints: dict[str, dict[str, Any]] = {}
    for t in all_terms:
        # atomic 만 (composite 제외)
        kind = getattr(t, "kind", None)
        if hasattr(kind, "value"):
            kind = kind.value
        if kind not in (None, "atomic"):
            continue
        fqn = getattr(t, "fqn", "")
        # slab 관련 키워드 필터
        if not any(k in fqn.lower() for k in _SLAB_KEYWORDS):
            continue
        # facets 추출 — ontology BusinessTerm 의 가능한 attribute 들
        facets: dict[str, Any] = {}
        for attr in ("range_min", "range_max", "unit", "enum_values"):
            val = getattr(t, attr, None)
            if val is not None:
                facets[attr.replace("range_", "").replace("_values", "")] = val
        # nested facets (e.g., t.facets dict)
        nested = getattr(t, "facets", None)
        if isinstance(nested, dict):
            facets.update({k: v for k, v in nested.items() if v is not None})
        if facets:
            constraints[fqn] = facets

    return {
        "constraints": constraints,
        "_meta": {
            "source": "ontology",
            "note": "이전 mock_simulator hardcoded constraints 를 ontology atomic facets 로 대체",
            "atomic_count": len(constraints),
        },
    }


# ─── /calculate — spec 03 신경로로 안내 + ontology atomic 검증 ────


@router.post("/calculate")
async def calculate_slab(params_data: dict) -> dict[str, Any]:
    """이전 mock_simulator.calculate_slab_design 대체 — ontology 기반 minimal echo.

    실 시뮬은 `POST /api/simulation/runs` (spec 03 §1.1) 로 redirect 권장.
    본 endpoint 는 frontend 의 SlabViewer3D 호환 위해 보존 — params echo + ontology
    기반 atomic 검증만 수행.
    """
    ont = _get_ontology_client()

    matched_atomics: list[str] = []
    unknown_keys: list[str] = []
    try:
        all_terms = ont.list_terms() or []
        atomic_names = {getattr(t, "fqn", "") for t in all_terms}
    except Exception:
        atomic_names = set()

    for k in (params_data or {}).keys():
        matched = [a for a in atomic_names if a.endswith(f".{k}") or a == k]
        if matched:
            matched_atomics.append(matched[0])
        else:
            unknown_keys.append(k)

    return {
        "status": "deprecated",
        "_meta": {
            "deprecated_since": "2026-05-10 (STEP 3c-D)",
            "redirect_to": "POST /api/simulation/runs (spec 03 §1.1 — ChangeSpec → SimResult)",
            "source": "ontology",
        },
        "input_echo": params_data,
        "validation": {
            "matched_atomics": matched_atomics,
            "unknown_keys": unknown_keys,
        },
        "result": {
            "note": "실제 시뮬은 spec 03 신경로 (POST /api/simulation/runs) 사용",
            "atomic_count": len(matched_atomics),
        },
    }
