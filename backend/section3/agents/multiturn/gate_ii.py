"""Phase 2 Step 3b — Gate II handler.

selected ActionRef → ontology.method_body + sim_v2.translate + ontology.entity_schema
+ sim_v2.load_action + sim_v2.synthesize_fixtures → `GateBundle` payload.

Q5 비전 ("빠진 내용은 빠진대로"): 각 단계 실패 시
- java_source/python_source 는 빈 문자열, fixtures 는 [], schema 는 empty
- Provenance 의 confidence 가 그 부재를 명시
- bundle.confidence 는 단계 성공률의 평균
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from .ontology_client import OntologyClient
from .schemas import (
    ActionRef,
    FixtureRow,
    GateBundle,
    IdiomDiff,
    Provenance,
    SchemaSummary,
)
from .tools import (
    call_ontology_get_entity_schema,
    call_ontology_get_method_body,
    call_sim_v2_synthesize_fixtures,
    call_sim_v2_translate,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


async def build_gate_ii(
    *,
    target: ActionRef,
    repo_id: str,
    ontology_client: OntologyClient,
    max_combinations: int = 12,
) -> GateBundle:
    """Gate II 결과 = `GateBundle` payload.

    Pipeline (단계 실패 시 부분 결과 + confidence ↓):
      1) body = ontology.get_method_body(target.code_method_fqn)
      2) (python_source, function_name) = sim_v2.translate_java_to_python(body)
      3) entity_name = _extract_entity_name(target.code_method_fqn)
         schema = ontology.get_entity_schema(entity_name)
      4) action = sim_v2.load_action(target.action_id)
         report = sim_v2.synthesize_fixtures(action, function_name, python_source)
    """
    body_result = await call_ontology_get_method_body(
        ontology_client, fqn=target.code_method_fqn, repo_id=repo_id,
    )
    java_source = body_result.data or ""

    if java_source:
        translate_result = await call_sim_v2_translate(body_text=java_source)
        translated = translate_result.data
    else:
        translate_result = None
        translated = None

    if translated:
        # Phase 8: translated 는 (python_source, function_name, idiom_rewrites) 3-tuple.
        # backward-compat: 2-tuple 도 graceful 처리.
        if len(translated) == 3:
            python_source, function_name, idiom_rewrites = translated
        else:
            python_source, function_name = translated  # type: ignore[misc]
            idiom_rewrites = []
    else:
        python_source, function_name = "", ""
        idiom_rewrites = []

    entity_name = _extract_entity_name(target.code_method_fqn)
    if entity_name:
        schema_result = await call_ontology_get_entity_schema(
            ontology_client, entity_name=entity_name, repo_id=repo_id,
        )
        schema_summary = schema_result.data or SchemaSummary(entity_name="", fields=[])
    else:
        schema_result = None
        schema_summary = SchemaSummary(entity_name="", fields=[])

    fixtures: list[FixtureRow] = []
    fixtures_result = None
    if python_source and function_name:
        action = await _load_action_async(
            action_fqn=target.action_id, repo_id=repo_id,
        )
        if action is not None:
            fixtures_result = await call_sim_v2_synthesize_fixtures(
                action=action,
                function_name=function_name,
                python_source=python_source,
                max_combinations=max_combinations,
            )
            fixtures = _normalize_fixtures(fixtures_result.data)

    sources: list[Provenance] = [body_result.provenance]
    if translate_result is not None:
        sources.append(translate_result.provenance)
    if schema_result is not None:
        sources.append(schema_result.provenance)
    if fixtures_result is not None:
        sources.append(fixtures_result.provenance)

    confidence = _bundle_confidence(
        body=bool(java_source),
        translated=bool(python_source),
        schema=bool(schema_summary.fields),
        fixtures=bool(fixtures),
    )

    return GateBundle(
        target=target,
        java_source=java_source,
        python_source=python_source,
        idiom_diffs=_extract_idiom_diffs(idiom_rewrites),
        fixtures=fixtures,
        schema_summary=schema_summary,
        sources=sources,
        confidence=confidence,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────


_ENTITY_PATTERN = re.compile(r"\(\s*([A-Za-z_][A-Za-z0-9_]*)")


def _extract_entity_name(code_method_fqn: str) -> str:
    """`SdOrderValidator.validate(SDOrderEntity)` → `SDOrderEntity`.

    Java 메소드 시그니처의 첫 번째 파라미터 타입. 없으면 빈 문자열.
    """
    m = _ENTITY_PATTERN.search(code_method_fqn)
    return m.group(1) if m else ""


async def _load_action_async(*, action_fqn: str, repo_id: str):
    """sim_v2.load_action 의 asyncio.to_thread wrapper."""
    from backend.section3 import sim_v2_bridge as sb

    def _run():
        s = sb.open_sim_v2_session()
        try:
            return sb.load_action(s, action_fqn, repo_id)
        finally:
            s.close()

    return await asyncio.to_thread(_run)


def _normalize_fixtures(report: Any) -> list[FixtureRow]:
    """sim_v2 의 FixtureSet → list[FixtureRow] (Pydantic)."""
    if report is None:
        return []
    raw_fixtures = getattr(report, "fixtures", None)
    if not raw_fixtures:
        return []
    out: list[FixtureRow] = []
    for fx in raw_fixtures:
        args_repr = {
            f"arg{i}": _safe_jsonable(v)
            for i, v in enumerate(getattr(fx, "input_args", ()))
        }
        args_repr.update({
            k: _safe_jsonable(v)
            for k, v in (getattr(fx, "input_kwargs", {}) or {}).items()
        })
        out.append(FixtureRow(
            fixture_id=getattr(fx, "fixture_id", f"fx-{len(out)}"),
            args=args_repr,
        ))
    return out


def _safe_jsonable(v: Any) -> Any:
    from decimal import Decimal
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (int, float, bool, str, type(None))):
        return v
    return repr(v)


def _extract_idiom_diffs(idiom_rewrites: list[dict] | None) -> list[IdiomDiff]:
    """Phase 8: W75 trace → IdiomDiff[] (UI 표면화 + dedup).

    sim_v2 의 `rewrite_method_invocation` 가 매칭 시 `_idiom_trace` 에 dict 누적.
    중복 (java_snippet, python_snippet) 은 1건으로 합치고, 순서는 첫 등장 순.
    """
    if not idiom_rewrites:
        return []
    seen: set[tuple[str, str]] = set()
    out: list[IdiomDiff] = []
    for r in idiom_rewrites:
        java_snippet = (r.get("java_snippet") or "").strip()
        python_snippet = (r.get("python_snippet") or "").strip()
        if not java_snippet or not python_snippet:
            continue
        key = (java_snippet, python_snippet)
        if key in seen:
            continue
        seen.add(key)
        out.append(IdiomDiff(
            idiom_name=r.get("idiom_name") or "?",
            java_snippet=java_snippet,
            python_snippet=python_snippet,
        ))
    return out


def _bundle_confidence(
    *, body: bool, translated: bool, schema: bool, fixtures: bool,
) -> float:
    """4 단계 성공률 가중 평균. body+translate 는 fixture 보다 비중 큼."""
    weights = (0.35, 0.30, 0.15, 0.20)
    flags = (body, translated, schema, fixtures)
    score = sum(w for w, ok in zip(weights, flags) if ok)
    return round(score, 3)


__all__ = ["build_gate_ii"]
