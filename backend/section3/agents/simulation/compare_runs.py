"""compare_runs — 같은 bundle 에 변경 전/후 두 fixture 로 simulate 2회 → diff.

Phase G: 사용자가 BundlePreviewCard 에서 fixture 의 일부 field 를 수정하면
override 를 받아 변경 전 (원래 fixture) vs 변경 후 (override 적용) 두 번 실행.
"""
from __future__ import annotations

import copy
import logging
from typing import Any

from backend.section3.agents.multiturn.gate_iii_sim import build_gate_iii_sim
from backend.section3.agents.multiturn.schemas import GateBundle
from backend.section3.agents.simulation.schemas import CompareRunResult, FieldDiff

logger = logging.getLogger(__name__)


def _flatten(d: Any, prefix: str = "") -> dict[str, Any]:
    """nested dict 를 dot-path 로 평탄화. list/scalar 은 그대로."""
    if not isinstance(d, dict):
        return {prefix.rstrip("."): d} if prefix else {}
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, prefix=f"{key}."))
        else:
            out[key] = v
    return out


def _diff_fields(before: Any, after: Any) -> list[FieldDiff]:
    fb = _flatten(before)
    fa = _flatten(after)
    keys = sorted(set(fb) | set(fa))
    out: list[FieldDiff] = []
    for k in keys:
        b, a = fb.get(k), fa.get(k)
        out.append(FieldDiff(field=k, before=b, after=a, changed=(b != a)))
    return out


def _apply_overrides(
    fixtures: list[dict[str, Any]],
    overrides: dict[str, Any],
    fixture_index: int = 0,
) -> list[dict[str, Any]]:
    """fixtures[fixture_index].args 에 overrides 를 deep-merge.

    overrides 는 dot-path 가 아닌 nested dict 형태로 가정.
    """
    if not fixtures:
        return fixtures
    cloned = copy.deepcopy(fixtures)
    target = cloned[fixture_index]
    args = target.get("args") or {}
    args = _deep_merge(args, overrides)
    target["args"] = args
    cloned[fixture_index] = target
    return cloned


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


async def compare_runs(
    *, bundle: GateBundle, overrides: dict[str, Any], repo_id: str,
    fixture_index: int = 0,
) -> CompareRunResult:
    """변경 전·후 두 번 실행 → field-level diff.

    Pipeline:
      1) before_run = build_gate_iii_sim(bundle) — 원본 fixture
      2) bundle_after = bundle with fixtures[fixture_index].args merged overrides
      3) after_run = build_gate_iii_sim(bundle_after)
      4) field_diffs = _diff_fields(before.case[0].result, after.case[0].result)
    """
    before_run = await build_gate_iii_sim(bundle=bundle, repo_id=repo_id)
    before_dict = before_run.model_dump()
    before_result = (
        before_dict.get("results", [{}])[0].get("output_value")
        if before_dict.get("results") else None
    )

    # bundle 복사 후 fixture override
    bundle_dict = bundle.model_dump()
    bundle_dict["fixtures"] = _apply_overrides(
        bundle_dict["fixtures"], overrides, fixture_index,
    )
    bundle_after = GateBundle.model_validate(bundle_dict)

    after_run = await build_gate_iii_sim(bundle=bundle_after, repo_id=repo_id)
    after_dict = after_run.model_dump()
    after_result = (
        after_dict.get("results", [{}])[0].get("output_value")
        if after_dict.get("results") else None
    )

    field_diffs = _diff_fields(before_result, after_result)
    changed = sum(1 for d in field_diffs if d.changed)

    return CompareRunResult(
        method_fqn=bundle.target.code_method_fqn,
        before_result=before_result if isinstance(before_result, dict) else None,
        after_result=after_result if isinstance(after_result, dict) else None,
        field_diffs=field_diffs,
        invariant_before=[],
        invariant_after=[],
        summary=(
            f"필드 {len(field_diffs)} 중 {changed} 변경"
            if field_diffs else "결과 비교 가능 데이터 없음"
        ),
    )
