"""Java ↔ Python 양쪽 실행 + 결과 diff.

같은 입력으로 Java SdDesigner / Python pipeline_full 모두 실행하고
field-by-field flatten diff 반환. BigDecimal tolerance 적용.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional

from backend.simulation.jvm_bridge.runner import (
    JavaBridgeError,
    JavaResult,
    is_bridge_available,
    run_java,
)
from backend.simulation.transpile.equivalence import (
    _flatten as _flatten_dict,           # type: ignore[attr-defined]
)


# ─── 정밀 비교 (BigDecimal tolerance) ───────────────────────────────


_DEFAULT_REL = Decimal("1e-9")
_DEFAULT_ABS = Decimal("1e-12")


def _to_decimal(v: Any) -> Optional[Decimal]:
    """안전한 Decimal 변환 — 어떤 입력이든 fail 시 None.
    NaN / Inf / 빈 문자열 / dict / list / None 모두 안전하게 처리.
    """
    if v is None:
        return None
    if isinstance(v, Decimal):
        # NaN/Inf 는 비교 불가
        try:
            if v.is_nan() or v.is_infinite():
                return None
        except Exception:
            return None
        return v
    if isinstance(v, bool):
        return None
    try:
        if isinstance(v, (int, float)):
            d = Decimal(str(v))
        elif isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            d = Decimal(s)
        else:
            return None
        if d.is_nan() or d.is_infinite():
            return None
        return d
    except Exception:
        return None


def values_close(
    a: Any, b: Any, *,
    rel: Decimal = _DEFAULT_REL, abs_: Decimal = _DEFAULT_ABS,
) -> bool:
    """문자열/Decimal/숫자 모두 받아 numeric tolerance 비교.

    숫자 변환 실패 → 일반 == fallback (문자열 정확 매칭 등).
    """
    if a == b:
        return True
    da, db = _to_decimal(a), _to_decimal(b)
    if da is None or db is None:
        return False
    diff = abs(da - db)
    threshold = max(abs_, rel * max(abs(da), abs(db)))
    return diff <= threshold


# ─── Differential 결과 ───────────────────────────────────────────────


@dataclass
class FieldDiff:
    """필드별 비교 결과.

    category:
      - matched      : 두 값이 같음 (numeric tolerance 포함)
      - mismatched   : 양쪽 다 값 있는데 다름
      - java_only    : Python 에만 None / 누락
      - python_only  : Java 에만 None / 누락
      - both_null    : 양쪽 다 None / 누락 (정합 — 보통 무시)
    """
    path: str
    java: Any
    python: Any
    is_close: bool
    category: str = "matched"


@dataclass
class DifferentialResult:
    java_available: bool
    java_ok: bool
    python_ok: bool

    # 새 분류 카운트 (사용자 가시성)
    matched_count: int = 0
    mismatched_count: int = 0
    java_only_count: int = 0  # python 만 null
    python_only_count: int = 0  # java 만 null
    both_null_count: int = 0

    field_diffs: list[FieldDiff] = field(default_factory=list)
    """모든 path 비교 결과 (matched 포함). UI 가 category 로 필터링."""

    summary: str = ""
    """한 줄 사람-친화 요약. 예: '38 matched / 2 mismatched / 1 java_only / 0 python_only'."""

    java_elapsed_sec: float = 0.0
    python_elapsed_sec: float = 0.0
    java_error: Optional[str] = None
    python_error: Optional[str] = None

    # raw payload (참고용 — 비교는 normalized 위에서)
    java_payload: Optional[dict[str, Any]] = None
    python_payload: Optional[dict[str, Any]] = None
    java_payload_normalized: Optional[dict[str, Any]] = None
    python_payload_normalized: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "java_available": self.java_available,
            "java_ok": self.java_ok,
            "python_ok": self.python_ok,
            "matched_count": self.matched_count,
            "mismatched_count": self.mismatched_count,
            "java_only_count": self.java_only_count,
            "python_only_count": self.python_only_count,
            "both_null_count": self.both_null_count,
            "field_diffs": [asdict(d) for d in self.field_diffs],
            "summary": self.summary,
            "java_elapsed_sec": self.java_elapsed_sec,
            "python_elapsed_sec": self.python_elapsed_sec,
            "java_error": self.java_error,
            "python_error": self.python_error,
            "java_payload": self.java_payload,
            "python_payload": self.python_payload,
            "java_payload_normalized": self.java_payload_normalized,
            "python_payload_normalized": self.python_payload_normalized,
        }


# ─── pair-run helper ────────────────────────────────────────────────


def _run_python_pipeline(inputs: dict[str, Any]) -> tuple[bool, dict[str, Any], float, Optional[str]]:
    """Python pipeline_full 실행. (ok, payload, elapsed, error_msg)."""
    import time
    from backend.simulation.sandbox.registry import STEP_REGISTRY

    started = time.monotonic()
    try:
        runner = STEP_REGISTRY.get("pipeline_full")
        if runner is None:
            return (False, {}, 0.0, "pipeline_full step 미등록")
        out = runner(inputs)
        return (True, out, time.monotonic() - started, None)
    except Exception as exc:
        return (False, {"error": repr(exc)}, time.monotonic() - started, repr(exc))


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """null/None/빈 문자열/빈 dict/빈 list 제거 — 비교 가독성 향상.

    재귀적으로 dict/list 순회. UI 에 noise 줄임.
    """
    if not isinstance(payload, dict):
        return payload

    cleaned: dict[str, Any] = {}
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if isinstance(v, dict):
            sub = _normalize_payload(v)
            if sub:  # 빈 dict 제외
                cleaned[k] = sub
        elif isinstance(v, list):
            sub_list = [_normalize_payload(item) if isinstance(item, dict) else item for item in v]
            sub_list = [item for item in sub_list if item not in (None, "", {}, [])]
            if sub_list:
                cleaned[k] = sub_list
        else:
            cleaned[k] = v
    return cleaned


def _classify_diff(jv: Any, pv: Any, *, rel: Decimal, abs_: Decimal) -> tuple[str, bool]:
    """(category, is_close) 반환.

    category:
      - both_null   : 둘 다 None
      - python_only : java=None, python=value
      - java_only   : java=value, python=None
      - matched     : 두 값 비슷
      - mismatched  : 두 값 다름
    """
    j_null = jv is None or (isinstance(jv, str) and not jv.strip())
    p_null = pv is None or (isinstance(pv, str) and not pv.strip())

    if j_null and p_null:
        return ("both_null", True)
    if j_null and not p_null:
        return ("python_only", False)
    if p_null and not j_null:
        return ("java_only", False)
    close = values_close(jv, pv, rel=rel, abs_=abs_)
    return ("matched" if close else "mismatched", close)


def run_differential(
    inputs: dict[str, Any],
    *,
    rel: Decimal = _DEFAULT_REL,
    abs_: Decimal = _DEFAULT_ABS,
    java_timeout_sec: float = 30.0,
) -> DifferentialResult:
    """같은 입력으로 Java/Python 양쪽 실행 + 카테고리별 diff.

    Java 미가용 시 java_available=False, python 만 실행.
    BigDecimal tolerance 적용 — string/Decimal 모두 numeric 비교.

    개선 (2026-05-10 STEP 3f):
    - matched / mismatched / java_only / python_only / both_null 5 카테고리 분류
    - normalized payload 추가 (null/empty 제거 — UI 가독성)
    - summary 한 줄 요약
    """
    java_avail = is_bridge_available()
    java_ok = False
    java_payload: dict[str, Any] = {}
    java_elapsed = 0.0
    java_error: Optional[str] = None

    if java_avail:
        try:
            jres: JavaResult = run_java(inputs, timeout_sec=java_timeout_sec)
            java_ok = jres.ok
            java_payload = jres.payload
            java_elapsed = jres.elapsed_sec
            if not jres.ok:
                java_error = jres.payload.get("error") or jres.stderr[:500]
        except JavaBridgeError as exc:
            java_error = str(exc)

    py_ok, py_payload, py_elapsed, py_error = _run_python_pipeline(inputs)

    diffs: list[FieldDiff] = []
    counts = {"matched": 0, "mismatched": 0, "java_only": 0, "python_only": 0, "both_null": 0}

    java_normalized: Optional[dict[str, Any]] = None
    py_normalized: Optional[dict[str, Any]] = None

    if java_ok and py_ok:
        java_normalized = _normalize_payload(java_payload)
        py_normalized = _normalize_payload(py_payload)
        # 양쪽 dict 평면화 후 같은 path 의 값 비교 (normalized 사용)
        flat_j = _flatten_dict(java_normalized)
        flat_p = _flatten_dict(py_normalized)
        all_paths = sorted(set(flat_j.keys()) | set(flat_p.keys()))
        for p in all_paths:
            jv = flat_j.get(p)
            pv = flat_p.get(p)
            category, is_close = _classify_diff(jv, pv, rel=rel, abs_=abs_)
            counts[category] += 1
            # both_null 은 noise — diff 리스트에 넣지 않음 (count 만)
            if category == "both_null":
                continue
            diffs.append(FieldDiff(
                path=p, java=jv, python=pv,
                is_close=is_close, category=category,
            ))

    summary = (
        f"{counts['matched']} matched / "
        f"{counts['mismatched']} mismatched / "
        f"{counts['java_only']} java_only / "
        f"{counts['python_only']} python_only"
        + (f" / {counts['both_null']} both_null" if counts['both_null'] else "")
    ) if (java_ok and py_ok) else (
        f"java_ok={java_ok} python_ok={py_ok} — 비교 불가"
    )

    return DifferentialResult(
        java_available=java_avail,
        java_ok=java_ok,
        python_ok=py_ok,
        field_diffs=diffs,
        matched_count=counts["matched"],
        mismatched_count=counts["mismatched"],
        java_only_count=counts["java_only"],
        python_only_count=counts["python_only"],
        both_null_count=counts["both_null"],
        summary=summary,
        java_elapsed_sec=java_elapsed,
        python_elapsed_sec=py_elapsed,
        java_error=java_error,
        python_error=py_error,
        java_payload=java_payload if java_ok else None,
        python_payload=py_payload if py_ok else None,
        java_payload_normalized=java_normalized,
        python_payload_normalized=py_normalized,
    )
