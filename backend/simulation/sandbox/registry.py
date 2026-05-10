"""Step registry — step_id 문자열 → 실행 함수 매핑.

sandbox runner가 subprocess 안에서 이 모듈만 import해서 step을 실행한다.
"""

from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from .fixtures import fixtures as fx
from .fixtures.domain import AlgorithmError, SDOrder, SDSlab, ValidationResult
from .fixtures.domain import EdgingSpecMissingError
from .fixtures import repository_pg as fx_pg
from .fixtures.steps import (
    final_length_range as final_length_range_step,
    final_width_range as final_width_range_step,
    length_range as length_range_step,
    max_split as max_split_step,
    productivity as productivity_step,
    second_wgt as second_wgt_step,
    slab_count as slab_count_step,
    slab_weight as slab_weight_step,
    split_range as split_range_step,
    target_size as target_size_step,
    thickness as thickness_step,
    validator as validator_step,
    width_range as width_range_step,
)


# ─── PG / in-memory dispatch ────────────────────────────────────────
# `SIMULATION_DATABASE_URL` 또는 `SIM_DB_HOST` 가 설정되면 PG-backed Repo,
# 미설정이면 fixtures.py 의 in-memory 데이터. 룰 override(rules.hr 등) 가
# 들어온 경우엔 PG 모드여도 in-memory 로 fallback — 룰 변경은 휘발성 시뮬.


def _pg_enabled() -> bool:
    try:
        from backend.simulation.storage.postgres.connection import is_pg_enabled
        return is_pg_enabled()
    except Exception:
        return False


def _repo_plant_mapping():
    if _pg_enabled():
        return fx_pg.PlantMappingPgRepo()
    return fx.make_default_plant_mapping()


def _repo_cast_spec():
    if _pg_enabled():
        return fx_pg.CastSpecPgRepo()
    return fx.make_default_cast_spec()


def _repo_hr_spec():
    if _pg_enabled():
        return fx_pg.HrSpecPgRepo()
    return fx.make_default_hr_spec()


def _repo_hr_min_wgt():
    if _pg_enabled():
        return fx_pg.HrMinWgtPgRepo()
    return fx.make_default_hr_min_wgt()


def _repo_hr_max_wgt():
    if _pg_enabled():
        return fx_pg.HrMaxWgtPgRepo()
    return fx.make_default_hr_max_wgt()


def _repo_edging_group():
    if _pg_enabled():
        return fx_pg.EdgingGroupPgRepo()
    return fx.make_default_edging_group()


def _repo_edging_spec(*, include_wildcard: bool = True):
    # include_wildcard=False (시나리오 14) 는 in-memory 강제 — PG 시드는 wildcard 포함.
    if _pg_enabled() and include_wildcard:
        return fx_pg.EdgingSpecPgRepo()
    return fx.make_default_edging_spec(include_wildcard=include_wildcard)


def _repo_customer_std():
    if _pg_enabled():
        return fx_pg.CustomerStdPgRepo()
    return fx.make_default_customer_std()


def _repo_productivity_std(*, hr=None, hrf=None, anl1=None):
    """룰 override 인자 있으면 in-memory (휘발성), 없으면 PG."""
    has_override = any(v is not None for v in (hr, hrf, anl1))
    if _pg_enabled() and not has_override:
        return fx_pg.ProductivityStdPgRepo()
    return fx.make_default_productivity_std(
        hr_productivity=hr or Decimal("0.95"),
        hrf_productivity=hrf or Decimal("0.93"),
        anl1_productivity=anl1 or Decimal("0.92"),
    )


# ─── JSON 직렬화 ────────────────────────────────────────────────────


def _to_json(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return [_to_json(x) for x in v]
    if isinstance(v, dict):
        return {k: _to_json(x) for k, x in v.items()}
    if is_dataclass(v):
        return {f.name: _to_json(getattr(v, f.name)) for f in fields(v)}
    return repr(v)


def _from_json_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _from_json_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


# ─── Step 정의 ──────────────────────────────────────────────────────


def _run_validator(inputs: dict) -> dict:
    """inputs: {"order": <SDOrder dict | overrides>, "today": "YYYY-MM-DD"?}"""
    order = _build_order(inputs.get("order", {}))
    today = _from_json_date(inputs.get("today"))
    result = validator_step.validate(order, today=today)
    return {"validation": result.to_json()}


def _run_productivity(inputs: dict) -> dict:
    """inputs: {"order": {...}, "rules": {hr:0.92, hrf:0.93, anl1:0.92}?}"""
    order = _build_order(inputs.get("order", {}))
    rules = inputs.get("rules", {}) or {}
    repo = _repo_productivity_std(
        hr=_from_json_decimal(rules.get("hr")),
        hrf=_from_json_decimal(rules.get("hrf")),
        anl1=_from_json_decimal(rules.get("anl1")),
    )
    cumulative = productivity_step.cumulative_productivity(order, repo)
    return {"cumulative_productivity": str(cumulative)}


def _run_thickness(inputs: dict) -> dict:
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    plant = _repo_plant_mapping()
    cast = _repo_cast_spec()
    try:
        thickness_step.execute(order, slab, plant, cast)
    except AlgorithmError as e:
        return {"error": e.to_json()}
    return {"slab": _to_json(slab)}


def _run_split_range(inputs: dict) -> dict:
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    try:
        split_range_step.execute(order, slab)
    except AlgorithmError as e:
        return {"error": e.to_json()}
    return {"slab": _to_json(slab)}


def _run_slab_count(inputs: dict) -> dict:
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    try:
        slab_count_step.execute(order, slab)
    except AlgorithmError as e:
        return {"error": e.to_json()}
    return {"slab": _to_json(slab)}


def _run_slab_weight(inputs: dict) -> dict:
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    try:
        slab_weight_step.execute(order, slab)
    except AlgorithmError as e:
        return {"error": e.to_json()}
    return {"slab": _to_json(slab)}


def _run_width_range(inputs: dict) -> dict:
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    plant = _repo_plant_mapping()
    cast = _repo_cast_spec()
    hr = _repo_hr_spec()
    eg = _repo_edging_group()
    es = _repo_edging_spec(include_wildcard=inputs.get("include_wildcard", True))
    try:
        width_range_step.execute(order, slab, plant, cast, hr, eg, es)
    except AlgorithmError as e:
        return {"error": e.to_json()}
    except EdgingSpecMissingError as e:
        return {"error": e.to_json()}
    return {"slab": _to_json(slab)}


def _run_length_range(inputs: dict) -> dict:
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    plant = _repo_plant_mapping()
    cast = _repo_cast_spec()
    hr = _repo_hr_spec()
    try:
        length_range_step.execute(order, slab, plant, cast, hr)
    except AlgorithmError as e:
        return {"error": e.to_json()}
    return {"slab": _to_json(slab)}


def _run_second_wgt(inputs: dict) -> dict:
    """step 5+6 — secondWgtLow/High 동시 산정."""
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    hr_min = _repo_hr_min_wgt()
    hr_max = _repo_hr_max_wgt()
    cust = _repo_customer_std()
    try:
        second_wgt_step.execute_low(order, slab, hr_min, cust)
        second_wgt_step.execute_high(order, slab, hr_max, cust)
    except AlgorithmError as e:
        return {"error": e.to_json(), "slab": _to_json(slab)}
    return {"slab": _to_json(slab)}


def _run_max_split(inputs: dict) -> dict:
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    try:
        max_split_step.execute(order, slab)
    except AlgorithmError as e:
        return {"error": e.to_json()}
    return {"slab": _to_json(slab)}


def _run_final_width_range(inputs: dict) -> dict:
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    try:
        final_width_range_step.execute(order, slab)
    except AlgorithmError as e:
        return {"error": e.to_json()}
    return {"slab": _to_json(slab)}


def _run_final_length_range(inputs: dict) -> dict:
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    try:
        final_length_range_step.execute(order, slab)
    except AlgorithmError as e:
        return {"error": e.to_json()}
    return {"slab": _to_json(slab)}


def _run_target_size(inputs: dict) -> dict:
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {}))
    try:
        target_size_step.execute(order, slab)
    except AlgorithmError as e:
        return {"error": e.to_json()}
    return {"slab": _to_json(slab)}


def _run_plant_mapping_migrate(inputs: dict) -> dict:
    """PlantMapping 마이그레이션 시뮬레이션.

    inputs.mapping_overrides: {smCd: {castCd, machineCd}}  ← 변경 후 매핑
    inputs.smCd / inputs.productTypeCd: 룩업 입력

    변경 전(default) vs 변경 후(overrides) 모두 thickness 룩업해서 결과 비교.
    """
    overrides = inputs.get("mapping_overrides", {}) or {}
    sm_cd = inputs.get("smCd", "K")
    prod = inputs.get("productTypeCd", "A001")

    base_repo = fx.make_default_plant_mapping()
    cast = fx.make_default_cast_spec()

    base_mapping = base_repo.get(sm_cd)
    base_lookup = None
    if base_mapping:
        bs = cast.lookup("K", "K01", sm_cd, base_mapping.castCd, base_mapping.machineCd, prod)
        base_lookup = {
            "castCd": base_mapping.castCd,
            "machineCd": base_mapping.machineCd,
            "thickness": str(bs.slabThickness) if bs else None,
        }

    from .fixtures.domain import PlantMapping
    from .fixtures.repository import PlantMappingRepo

    new_dict = base_repo.all()
    for k, v in overrides.items():
        new_dict[k] = PlantMapping(castCd=v["castCd"], machineCd=v["machineCd"])
    new_repo = PlantMappingRepo(new_dict)

    new_mapping = new_repo.get(sm_cd)
    new_lookup = None
    if new_mapping:
        ns = cast.lookup("K", "K01", sm_cd, new_mapping.castCd, new_mapping.machineCd, prod)
        new_lookup = {
            "castCd": new_mapping.castCd,
            "machineCd": new_mapping.machineCd,
            "thickness": str(ns.slabThickness) if ns else None,
        }

    return {
        "before": base_lookup,
        "after": new_lookup,
        "changed": base_lookup != new_lookup,
    }


def _run_pipeline(inputs: dict) -> dict:
    """validator → cumulativeProductivity → split_range → slab_count → slab_weight 한 번 흘림.

    단일 분할수 시도 (A-a 루프 미포함). 데모/테스트용 end-to-end.
    inputs: {"order": {...}, "slab": {...}, "rules": {hr:..., hrf:..., anl1:...}}
    """
    order = _build_order(inputs.get("order", {}))
    slab = _build_slab(inputs.get("slab", {"currentSplitCount": 1}))
    rules = inputs.get("rules", {}) or {}

    # 1. validate
    val = validator_step.validate(order)
    if not val.passed:
        return {"stage": "validate", "validation": val.to_json()}

    # 2. cumulative productivity
    repo = _repo_productivity_std(
        hr=_from_json_decimal(rules.get("hr")),
        hrf=_from_json_decimal(rules.get("hrf")),
        anl1=_from_json_decimal(rules.get("anl1")),
    )
    order.productivity = productivity_step.cumulative_productivity(order, repo)

    try:
        split_range_step.execute(order, slab)
        slab_count_step.execute(order, slab)
        slab_weight_step.execute(order, slab)
    except AlgorithmError as e:
        return {"stage": "algorithm", "error": e.to_json(), "slab": _to_json(slab)}

    return {
        "stage": "ok",
        "validation": val.to_json(),
        "productivity": str(order.productivity),
        "slab": _to_json(slab),
    }


def _run_pipeline_full(inputs: dict) -> dict:
    """전체 파이프라인 — Phase 6-A 신규 step 포함.

    flow: validate → productivity → thickness(1) → width_range(2) → length_range(3)
        → second_wgt(5+6) → max_split(7) → split_range(8) → slab_count(9) → slab_weight(10)
        → final_width_range(16) → final_length_range(17) → target_size(18+19)

    HR/SM 양쪽 활성 필요 (step 2/3). order overrides 로 confirmedPlantCd 조정 가능.
    rules: hr/hrf/anl1 productivity + edging_wildcard (true/false) + plant_overrides (dict).
    """
    order_overrides = dict(inputs.get("order", {}) or {})
    # Pipeline_full 은 step 2 가 HR 필요 → 기본으로 step2_order 사용
    if "confirmedPlantCd" not in order_overrides:
        order_overrides["confirmedPlantCd"] = "KKKK    "
    if "selectedHrTgtWidth" not in order_overrides:
        order_overrides["selectedHrTgtWidth"] = "1200"
    order = _build_order(order_overrides)
    slab = _build_slab(inputs.get("slab", {}) or {})
    rules = inputs.get("rules", {}) or {}
    include_wildcard = bool(rules.get("edging_wildcard", True))

    val = validator_step.validate(order)
    if not val.passed:
        return {"stage": "validate", "validation": val.to_json()}

    prod_repo = _repo_productivity_std(
        hr=_from_json_decimal(rules.get("hr")),
        hrf=_from_json_decimal(rules.get("hrf")),
        anl1=_from_json_decimal(rules.get("anl1")),
    )
    order.productivity = productivity_step.cumulative_productivity(order, prod_repo)

    plant = _repo_plant_mapping()
    cast = _repo_cast_spec()
    hr = _repo_hr_spec()
    eg = _repo_edging_group()
    es = _repo_edging_spec(include_wildcard=include_wildcard)
    hr_min = _repo_hr_min_wgt()
    hr_max = _repo_hr_max_wgt()
    cust = _repo_customer_std()

    try:
        thickness_step.execute(order, slab, plant, cast)
        width_range_step.execute(order, slab, plant, cast, hr, eg, es)
        length_range_step.execute(order, slab, plant, cast, hr)
        # firstWgt low/high 는 단순화: orderWgt 사용
        if slab.firstWgtLow is None:
            slab.firstWgtLow = order.orderWgtLow
        if slab.firstWgtHigh is None:
            slab.firstWgtHigh = order.orderWgtHigh
        second_wgt_step.execute_low(order, slab, hr_min, cust)
        second_wgt_step.execute_high(order, slab, hr_max, cust)
        max_split_step.execute(order, slab)
        split_range_step.execute(order, slab)
        slab_count_step.execute(order, slab)
        slab_weight_step.execute(order, slab)
        final_width_range_step.execute(order, slab)
        final_length_range_step.execute(order, slab)
        target_size_step.execute(order, slab)
    except AlgorithmError as e:
        return {"stage": "algorithm", "error": e.to_json(), "slab": _to_json(slab)}
    except EdgingSpecMissingError as e:
        return {"stage": "data_integrity", "error": e.to_json(), "slab": _to_json(slab)}

    return {
        "stage": "ok",
        "validation": val.to_json(),
        "productivity": str(order.productivity),
        "slab": _to_json(slab),
    }


# ─── Helpers ────────────────────────────────────────────────────────


_ORDER_DECIMAL_FIELDS = {
    "orderWidth", "orderLength", "pkgWgtLow", "pkgWgtHigh",
    "orderWgtLow", "orderWgtHigh", "designPendQty",
    "designPendQtyLow", "designPendQtyHigh",
    "productivity", "selectedHrTgtWidth", "specificGravity",
}
_ORDER_DATE_FIELDS = {
    "smDue", "hrDue", "hrfDue", "crDue",
    "anl1Due", "anl2Due", "galDue", "crfDue",
    "workDue",
}


def _build_order(overrides: dict) -> SDOrder:
    base = fx.make_default_order()
    for k, v in overrides.items():
        if not hasattr(base, k):
            continue
        if k in _ORDER_DECIMAL_FIELDS:
            v = _from_json_decimal(v)
        elif k in _ORDER_DATE_FIELDS:
            v = _from_json_date(v)
        setattr(base, k, v)
    return base


_SLAB_DECIMAL_FIELDS = {
    "slabThickness", "secondWgtLow", "secondWgtHigh",
    "splitWgtLow", "splitWgtHigh", "slabWgtInProgress",
    "firstWidthLow", "firstWidthHigh", "firstLengthLow", "firstLengthHigh",
    "firstWgtLow", "firstWgtHigh",
    "finalWidthLow", "finalWidthHigh", "finalLengthLow", "finalLengthHigh",
    "targetWidth", "targetLength",
}


def _build_slab(overrides: dict) -> SDSlab:
    base = fx.make_default_slab()
    for k, v in overrides.items():
        if not hasattr(base, k):
            continue
        if k in _SLAB_DECIMAL_FIELDS:
            v = _from_json_decimal(v)
        setattr(base, k, v)
    return base


# ─── Registry ───────────────────────────────────────────────────────


STEP_REGISTRY: dict[str, Callable[[dict], dict]] = {
    # Phase 1
    "validator": _run_validator,
    "productivity": _run_productivity,
    "thickness": _run_thickness,
    "split_range": _run_split_range,
    "slab_count": _run_slab_count,
    "slab_weight": _run_slab_weight,
    # Phase 6-A
    "width_range": _run_width_range,
    "length_range": _run_length_range,
    "second_wgt": _run_second_wgt,
    "max_split": _run_max_split,
    "final_width_range": _run_final_width_range,
    "final_length_range": _run_final_length_range,
    "target_size": _run_target_size,
    "plant_mapping_migrate": _run_plant_mapping_migrate,
    # Pipeline
    "pipeline": _run_pipeline,
    "pipeline_full": _run_pipeline_full,
}


def list_steps() -> list[str]:
    return sorted(STEP_REGISTRY.keys())


def run_step(step_id: str, inputs: dict) -> dict:
    """In-process 실행 (테스트/유닛용). subprocess 격리는 runner.py 가 담당."""
    if step_id not in STEP_REGISTRY:
        raise ValueError(f"Unknown step_id: {step_id}. Available: {list_steps()}")
    return STEP_REGISTRY[step_id](inputs)
