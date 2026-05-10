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
    path: str
    java: Any
    python: Any
    is_close: bool


@dataclass
class DifferentialResult:
    java_available: bool
    java_ok: bool
    python_ok: bool
    field_diffs: list[FieldDiff] = field(default_factory=list)
    matched_count: int = 0
    mismatched_count: int = 0
    java_elapsed_sec: float = 0.0
    python_elapsed_sec: float = 0.0
    java_error: Optional[str] = None
    python_error: Optional[str] = None
    java_payload: Optional[dict[str, Any]] = None
    python_payload: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "java_available": self.java_available,
            "java_ok": self.java_ok,
            "python_ok": self.python_ok,
            "matched_count": self.matched_count,
            "mismatched_count": self.mismatched_count,
            "field_diffs": [asdict(d) for d in self.field_diffs],
            "java_elapsed_sec": self.java_elapsed_sec,
            "python_elapsed_sec": self.python_elapsed_sec,
            "java_error": self.java_error,
            "python_error": self.python_error,
            "java_payload": self.java_payload,
            "python_payload": self.python_payload,
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


def run_differential(
    inputs: dict[str, Any],
    *,
    rel: Decimal = _DEFAULT_REL,
    abs_: Decimal = _DEFAULT_ABS,
    java_timeout_sec: float = 30.0,
) -> DifferentialResult:
    """같은 입력으로 Java/Python 양쪽 실행 + flatten diff.

    Java 미가용 시 java_available=False, python 만 실행.
    BigDecimal tolerance 적용 — string/Decimal 모두 numeric 비교.
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
    matched = 0
    mismatched = 0

    if java_ok and py_ok:
        # 양쪽 dict 평면화 후 같은 path 의 값 비교
        flat_j = _flatten_dict(java_payload)
        flat_p = _flatten_dict(py_payload)
        all_paths = sorted(set(flat_j.keys()) | set(flat_p.keys()))
        for p in all_paths:
            jv = flat_j.get(p)
            pv = flat_p.get(p)
            close = values_close(jv, pv, rel=rel, abs_=abs_)
            if close:
                matched += 1
            else:
                mismatched += 1
                diffs.append(FieldDiff(path=p, java=jv, python=pv, is_close=False))

    return DifferentialResult(
        java_available=java_avail,
        java_ok=java_ok,
        python_ok=py_ok,
        field_diffs=diffs,
        matched_count=matched,
        mismatched_count=mismatched,
        java_elapsed_sec=java_elapsed,
        python_elapsed_sec=py_elapsed,
        java_error=java_error,
        python_error=py_error,
        java_payload=java_payload if java_ok else None,
        python_payload=py_payload if py_ok else None,
    )
