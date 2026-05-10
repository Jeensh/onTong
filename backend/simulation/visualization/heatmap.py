"""Risk Heatmap — Java 코드 라인별 sandbox 실행 빈도 시각화.

Sandbox 실행 결과를 Java 소스 라인에 매핑해서 어떤 라인이 자주/드물게/한 번도 실행 안 됐는지 표시.

매핑 전략:
- 우리 Python step (validator/productivity/...)이 실행될 때, 해당 step의 Java 미러 파일을 식별
- 각 case 결과의 stage / error_code 정보로 어느 분기에 도달했는지 추정
- 결과: file_path → list[{line, count, branch_label}]

이 demo에선 정밀 line-level 추적은 안 함 — 대신 "step별 분기 도달 빈도"를
대표 라인에 매핑한 heuristic. 데모 임팩트가 정확도보다 우선.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


# step_id → (Java 파일, 분기별 대표 라인 매핑)
# branch_label은 sandbox 결과의 stage/error_code에서 유래.
_HEATMAP_MAP: dict[str, dict] = {
    "validator": {
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdOrderValidator.java",
        "branches": {
            "DG001": {"line": 58, "label": "재고주문 (STOCK_CODE=1)"},
            "DG002": {"line": 67, "label": "주문 폭/길이"},
            "DG003": {"line": 80, "label": "포장단중 range"},
            "DG004": {"line": 93, "label": "설계대기량 cross-check"},
            "DG005": {"line": 117, "label": "작업기한일"},
            "PASS": {"line": 53, "label": "전체 통과"},
        },
    },
    "productivity": {
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/std/service/ProductivityService.java",
        "branches": {
            "PASS": {"line": 95, "label": "누적 실수율 곱셈"},
        },
    },
    "thickness": {
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdThicknessAction.java",
        "branches": {
            "PASS": {"line": 69, "label": "slabThickness set"},
            "DG101": {"line": 60, "label": "CAST_SPEC 미존재"},
        },
    },
    "split_range": {
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdSplitRangeAction.java",
        "branches": {
            "PASS": {"line": 53, "label": "splitWgtLow/High set"},
            "DG108": {"line": 47, "label": "공통 단중범위 없음"},
        },
    },
    "slab_count": {
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdSlabCountAction.java",
        "branches": {
            "PASS": {"line": 39, "label": "매수 set"},
            "DG108": {"line": 35, "label": "매수 < 1"},
        },
    },
    "slab_weight": {
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdInitialSlabWgtAction.java",
        "branches": {
            "PASS": {"line": 33, "label": "설계대기량 만족"},
            "DG108": {"line": 47, "label": "iteration 필요"},
        },
    },
}


@dataclass
class LineMark:
    line: int
    count: int
    label: str


@dataclass
class HeatmapResult:
    step_id: str
    file_path: str
    file_content: str
    marks: list[LineMark] = field(default_factory=list)
    total_cases: int = 0


def _slab_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    # backend/simulation/visualization → 3단계 상위 = project root
    return os.path.normpath(os.path.join(here, "..", "..", "..", "sample-repos", "slab-design"))


def collect_branch_for_outcome(step_id: str, sandbox_result: dict | None) -> Optional[str]:
    """결과에서 branch label 추정."""
    if not sandbox_result:
        return None

    if step_id == "pipeline":
        # pipeline은 stage로 어느 단계에서 멈췄는지 파악 — 가장 가까운 step 매핑
        stage = sandbox_result.get("stage")
        if stage == "validate":
            ec = (sandbox_result.get("validation") or {}).get("error_code")
            return ec  # DG001~005
        if stage == "algorithm":
            err = sandbox_result.get("error") or {}
            return err.get("error_code")  # DG108 등
        if stage == "ok":
            return "PASS"
        return None

    if step_id == "validator":
        v = sandbox_result.get("validation") or {}
        if v.get("passed"):
            return "PASS"
        return v.get("error_code")

    # productivity, thickness, split_range, slab_count, slab_weight
    if "error" in sandbox_result and sandbox_result.get("error"):
        return sandbox_result["error"].get("error_code")
    return "PASS"


def build_heatmap(step_id: str, outcomes: list[dict]) -> Optional[HeatmapResult]:
    """outcomes: list of {sandbox_result: dict, ...}.

    Returns None if step not mappable (pipeline maps to validator/slab_count/etc.)
    """
    # pipeline은 가장 큰 분기 발생 step으로 대체
    use_step = step_id
    if step_id == "pipeline":
        # 분기를 표시할 대상은 가장 자주 실패한 step. heuristic: validator first.
        use_step = "validator"

    cfg = _HEATMAP_MAP.get(use_step)
    if cfg is None:
        return None

    file_rel = cfg["file"]
    file_path = os.path.normpath(os.path.join(_slab_root(), file_rel))
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return None

    counts: dict[str, int] = {}
    for o in outcomes:
        branch = collect_branch_for_outcome(step_id, o.get("sandbox_result"))
        if branch:
            counts[branch] = counts.get(branch, 0) + 1

    marks: list[LineMark] = []
    for branch_key, branch_info in cfg["branches"].items():
        count = counts.get(branch_key, 0)
        marks.append(LineMark(
            line=branch_info["line"],
            count=count,
            label=f"{branch_key} — {branch_info['label']}",
        ))

    return HeatmapResult(
        step_id=use_step,
        file_path=file_rel,
        file_content=content,
        marks=marks,
        total_cases=len(outcomes),
    )


def heatmap_to_json(h: HeatmapResult) -> dict:
    return {
        "step_id": h.step_id,
        "file_path": h.file_path,
        "file_content": h.file_content,
        "marks": [{"line": m.line, "count": m.count, "label": m.label} for m in h.marks],
        "total_cases": h.total_cases,
    }
