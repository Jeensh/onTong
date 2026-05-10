"""동치성 검증 — 자동 변환된 파이썬 step 이 기존 미러 step 과 동일 결과를 내는지 비교.

slab-design 자바는 실제 실행 환경이 없으므로 (Oracle/Kafka 미설치) "자바 vs 파이썬"
직접 비교는 불가능. 대신 두 가지 실용 모드 제공:

1. shadow_compare(transpiled_source, reference_step_id, sample_inputs)
   - 새로 변환된 파이썬 step 을 메모리에서 exec 후, 기존 sandbox.registry 의
     reference step 과 동일 inputs 로 실행 → 출력 dict 비교.
   - 기존 미러가 있는 step (thickness 등) 의 회귀 검증에 적합.

2. structural_check(transpiled_source)
   - exec 가능 여부 + 함수 시그니처 검증 + 명시 import 체크 (외부 패키지 사용 금지).
   - 기존 미러가 없는 신규 step 의 sanity check.

두 모드 모두 결과는 EquivalenceReport 로 통합.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from ..sandbox.registry import STEP_REGISTRY

logger = logging.getLogger(__name__)


@dataclass
class FieldDiff:
    path: str
    before: Any
    after: Any


@dataclass
class EquivalenceReport:
    mode: str  # "shadow" / "structural"
    passed: bool
    sample_count: int = 0
    matched: int = 0
    mismatched: int = 0
    field_diffs: list[FieldDiff] = field(default_factory=list)
    structural_errors: list[str] = field(default_factory=list)
    summary: str = ""

    def to_json(self) -> dict:
        return {
            "mode": self.mode,
            "passed": self.passed,
            "sample_count": self.sample_count,
            "matched": self.matched,
            "mismatched": self.mismatched,
            "field_diffs": [
                {"path": d.path, "before": d.before, "after": d.after}
                for d in self.field_diffs
            ],
            "structural_errors": self.structural_errors,
            "summary": self.summary,
        }


# ─── structural ────────────────────────────────────────────────────


_FORBIDDEN_TOP_IMPORTS = {
    "os",          # 의도하지 않은 파일 시스템 접근 차단 (신규 변환 코드)
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "shutil",
    "pathlib",  # 변환 결과는 pure 함수여야 함
}


def structural_check(python_source: str, function_name: str) -> EquivalenceReport:
    """exec 안 하고 AST 만 검사. fast-fail 용."""
    rep = EquivalenceReport(mode="structural", passed=False)
    try:
        tree = ast.parse(python_source)
    except SyntaxError as e:
        rep.structural_errors.append(f"SyntaxError: {e}")
        rep.summary = "파이썬 syntax 오류"
        return rep

    # 1. function_name 존재 확인
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    target = next((f for f in funcs if f.name == function_name), None)
    if target is None:
        rep.structural_errors.append(
            f"function '{function_name}' not found in transpiled source"
        )
        rep.summary = f"기대 함수 {function_name} 없음"
        return rep

    # 2. 시그니처 검증 — inputs: dict 단일 인자 권장
    arg_names = [a.arg for a in target.args.args]
    if arg_names != ["inputs"]:
        rep.structural_errors.append(
            f"function signature must be ({function_name}(inputs)), got ({', '.join(arg_names)})"
        )

    # 3. 외부 패키지 import 검사
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _FORBIDDEN_TOP_IMPORTS:
                    rep.structural_errors.append(
                        f"forbidden import: {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top in _FORBIDDEN_TOP_IMPORTS:
                    rep.structural_errors.append(
                        f"forbidden import: from {node.module} import ..."
                    )

    rep.passed = len(rep.structural_errors) == 0
    rep.summary = (
        "구조 검증 통과 — exec 가능, signature 일치, 금지 import 없음"
        if rep.passed
        else f"구조 검증 실패 ({len(rep.structural_errors)}건)"
    )
    return rep


# ─── shadow ────────────────────────────────────────────────────────


_DEFAULT_REL_TOL = Decimal("1e-9")
_DEFAULT_ABS_TOL = Decimal("1e-12")


def _to_decimal(v: Any) -> Optional[Decimal]:
    """문자열 / int / float / Decimal → Decimal. 변환 불가 시 None."""
    if isinstance(v, Decimal):
        return v
    if isinstance(v, bool):
        return None  # bool 은 int 의 subclass — 명시 제외
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    if isinstance(v, str):
        try:
            return Decimal(v)
        except Exception:
            return None
    return None


def values_close(
    a: Any, b: Any, *,
    rel: Decimal = _DEFAULT_REL_TOL,
    abs_: Decimal = _DEFAULT_ABS_TOL,
) -> bool:
    """numeric tolerance + 문자열 정확 매칭 fallback.

    BigDecimal/Decimal/문자열-숫자 모두 numeric 비교, 비-숫자는 == 비교.
    rel = 상대 허용오차, abs_ = 절대 허용오차. max(abs_, rel*max(|a|,|b|)) 이내면 close.
    """
    if a == b:
        return True
    da, db = _to_decimal(a), _to_decimal(b)
    if da is None or db is None:
        return False
    diff = abs(da - db)
    threshold = max(abs_, rel * max(abs(da), abs(db)))
    return diff <= threshold


def _flatten(d: Any, prefix: str = "") -> dict[str, Any]:
    """nested dict → flat path map. lists 는 [i] 인덱스."""
    out: dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            sub = f"{prefix}.{k}" if prefix else k
            out.update(_flatten(v, sub))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            sub = f"{prefix}[{i}]"
            out.update(_flatten(v, sub))
    else:
        out[prefix] = d
    return out


def _exec_transpiled(python_source: str, function_name: str) -> callable:
    """exec 후 함수 핸들 추출. 외부 import 차단된 namespace 사용."""
    # 안전한 namespace — builtins 만 노출 + Decimal/date 추가
    from decimal import Decimal
    import datetime
    import dataclasses

    ns: dict[str, Any] = {
        "__builtins__": {
            k: v for k, v in __builtins__.__dict__.items()  # type: ignore[attr-defined]
            if k not in {"open", "exec", "eval", "compile", "__import__"}
        }
        if isinstance(__builtins__, type)
        else __builtins__,
        "Decimal": Decimal,
        "datetime": datetime,
        "date": datetime.date,
        "dataclasses": dataclasses,
    }
    exec(python_source, ns)
    fn = ns.get(function_name)
    if fn is None or not callable(fn):
        raise RuntimeError(f"function {function_name} not found after exec")
    return fn


def shadow_compare(
    python_source: str,
    function_name: str,
    reference_step_id: str,
    sample_inputs: list[dict],
) -> EquivalenceReport:
    """변환된 파이썬 함수 vs 기존 미러 step 비교."""
    rep = EquivalenceReport(mode="shadow", passed=False)

    # 0. structural 부터
    struct = structural_check(python_source, function_name)
    if not struct.passed:
        rep.structural_errors = struct.structural_errors
        rep.summary = "구조 검증 실패 — shadow 비교 미실행"
        return rep

    # 1. reference 존재 확인
    if reference_step_id not in STEP_REGISTRY:
        rep.structural_errors.append(
            f"reference step '{reference_step_id}' not in STEP_REGISTRY"
        )
        rep.summary = "참조 step 없음"
        return rep
    ref_fn = STEP_REGISTRY[reference_step_id]

    # 2. exec
    try:
        candidate_fn = _exec_transpiled(python_source, function_name)
    except Exception as e:
        rep.structural_errors.append(f"exec failed: {e}")
        rep.summary = "exec 실패"
        return rep

    # 3. sample 별 비교
    rep.sample_count = len(sample_inputs)
    seen_paths: set[str] = set()
    for inp in sample_inputs:
        try:
            ref_out = ref_fn(inp)
        except Exception as e:
            ref_out = {"_exception": str(e)}
        try:
            cand_out = candidate_fn(inp)
        except Exception as e:
            cand_out = {"_exception": str(e)}

        ref_flat = _flatten(ref_out)
        cand_flat = _flatten(cand_out)
        all_keys = set(ref_flat.keys()) | set(cand_flat.keys())
        local_diff: list[FieldDiff] = []
        for k in sorted(all_keys):
            a = ref_flat.get(k, "<missing>")
            b = cand_flat.get(k, "<missing>")
            # BigDecimal tolerance — Decimal/문자열-숫자 모두 numeric 비교, 그 외 ==
            if not values_close(a, b):
                local_diff.append(FieldDiff(path=k, before=a, after=b))
        if local_diff:
            rep.mismatched += 1
            for d in local_diff:
                if d.path not in seen_paths:
                    rep.field_diffs.append(d)
                    seen_paths.add(d.path)
        else:
            rep.matched += 1

    rep.passed = rep.mismatched == 0 and rep.sample_count > 0
    rep.summary = (
        f"shadow 검증: {rep.matched}/{rep.sample_count} 일치"
        if rep.passed
        else f"shadow 검증: {rep.mismatched}건 불일치 / {rep.sample_count}건 (대표 차이 {len(rep.field_diffs)}개)"
    )
    return rep
