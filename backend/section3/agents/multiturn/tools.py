"""9 tool wrapper for the 3-gate multiturn agent (spec v2 §3).

- 5 ontology tool — `OntologyClient` 통과
- 4 sim_v2 tool — `backend/section3/sim_v2_bridge.py` 의 sync 함수를
  `asyncio.to_thread` 로 wrap

각 tool 의 결과는 `ToolResult(data, provenance)` — Q5 비전 ("확실한 근거")
대응. caller (gate logic) 가 여러 ToolResult 모아 GatePayload 의 sources 채움.

ALLOWED_PER_GATE — gate 별 tool allowlist (safety). LLM 이 권한 밖 tool
호출 시 차단.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from .ontology_client import OntologyClient
from .schemas import Provenance


# ─────────────────────────────────────────────────────────────────────────────
# Result envelope
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolResult:
    data: Any
    provenance: Provenance


def _onto_prov(detail: str, *, found: bool) -> Provenance:
    return Provenance(
        source="ontology",
        detail=detail,
        confidence=1.0 if found else 0.0,
    )


def _sim_prov(detail: str, *, confidence: float = 0.9) -> Provenance:
    return Provenance(source="sim_v2", detail=detail, confidence=confidence)


# ─────────────────────────────────────────────────────────────────────────────
# Ontology tools (Section 2 API)
# ─────────────────────────────────────────────────────────────────────────────


async def call_ontology_search(
    client: OntologyClient, *, query: str, repo_id: str, top_n: int = 5,
) -> ToolResult:
    hits = await client.search_action_by_keyword(query, repo_id=repo_id, top_n=top_n)
    return ToolResult(
        data=hits,
        provenance=_onto_prov(
            f"search_action_by_keyword(query={query!r}, repo_id={repo_id!r})",
            found=bool(hits),
        ),
    )


async def call_ontology_get_action_detail(
    client: OntologyClient, *, action_id: str, repo_id: str,
) -> ToolResult:
    detail = await client.get_action_detail(action_id, repo_id=repo_id)
    return ToolResult(
        data=detail,
        provenance=_onto_prov(
            f"get_action_detail(action_id={action_id!r})", found=detail is not None,
        ),
    )


async def call_ontology_get_method_body(
    client: OntologyClient, *, fqn: str, repo_id: str,
) -> ToolResult:
    body = await client.get_method_body(fqn, repo_id=repo_id)
    return ToolResult(
        data=body,
        provenance=_onto_prov(
            f"get_method_body(fqn={fqn!r})", found=body is not None,
        ),
    )


async def call_ontology_get_entity_schema(
    client: OntologyClient, *, entity_name: str, repo_id: str,
) -> ToolResult:
    schema = await client.get_entity_schema(entity_name, repo_id=repo_id)
    return ToolResult(
        data=schema,
        provenance=_onto_prov(
            f"get_entity_schema(entity_name={entity_name!r})",
            found=schema is not None,
        ),
    )


async def call_ontology_get_caller_graph(
    client: OntologyClient, *, method_fqn: str, repo_id: str,
) -> ToolResult:
    affected = await client.get_caller_graph(method_fqn, repo_id=repo_id)
    return ToolResult(
        data=affected,
        provenance=_onto_prov(
            f"get_caller_graph(method_fqn={method_fqn!r})", found=bool(affected),
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# sim_v2 tools — async wrapper around sync sim_v2_bridge
# ─────────────────────────────────────────────────────────────────────────────


async def call_sim_v2_find_action_candidates(
    *, user_query: str, repo_id: str, top_n: int = 3,
) -> ToolResult:
    from backend.section3 import sim_v2_bridge as sb

    def _run() -> list[dict[str, Any]]:
        s = sb.open_sim_v2_session()
        try:
            return sb.find_action_candidates(s, user_query, repo_id, top_n=top_n)
        finally:
            s.close()

    candidates = await asyncio.to_thread(_run)
    return ToolResult(
        data=candidates,
        provenance=_sim_prov(
            f"find_action_candidates(query={user_query!r})",
            confidence=0.9 if candidates else 0.3,
        ),
    )


async def call_sim_v2_translate(
    *, body_text: str,
) -> ToolResult:
    from backend.section3 import sim_v2_bridge as sb
    translated = await asyncio.to_thread(sb.translate_java_to_python, body_text)
    confidence = 0.93 if translated else 0.0
    return ToolResult(
        data=translated,
        provenance=_sim_prov(
            "translate_java_to_python(W75 idiom rewrite)",
            confidence=confidence,
        ),
    )


async def call_sim_v2_synthesize_fixtures(
    *, action, function_name: str, python_source: str, max_combinations: int = 12,
) -> ToolResult:
    from backend.section3 import sim_v2_bridge as sb

    def _run():
        s = sb.open_sim_v2_session()
        try:
            return sb.synthesize_fixtures(
                s, action,
                function_name=function_name,
                python_source=python_source,
                max_combinations=max_combinations,
            )
        finally:
            s.close()

    report = await asyncio.to_thread(_run)
    return ToolResult(
        data=report,
        provenance=_sim_prov(
            "synthesize_fixtures(W71 deterministic)",
            confidence=1.0 if report and report.fixtures else 0.5,
        ),
    )


async def call_sim_v2_run_fixtures(
    *, fixtures, function_name: str, python_source: str,
    expected_output: Any | None = None,
) -> ToolResult:
    from backend.section3 import sim_v2_bridge as sb

    results = await asyncio.to_thread(
        sb.run_fixtures_in_process,
        fixtures,
        function_name=function_name,
        python_source=python_source,
        expected_output=expected_output,
    )
    return ToolResult(
        data=results,
        provenance=_sim_prov(
            "run_fixtures_in_process(W59 + W74 stubs)", confidence=0.95,
        ),
    )


async def call_sim_v2_quick_diagnose(
    *, action,
) -> ToolResult:
    from backend.section3 import sim_v2_bridge as sb

    def _run() -> dict[str, Any]:
        s = sb.open_sim_v2_session()
        try:
            return sb.quick_diagnose_action(s, action)
        finally:
            s.close()

    diag = await asyncio.to_thread(_run)
    return ToolResult(
        data=diag,
        provenance=_sim_prov(
            "quick_diagnose_action(W71→W74→W72 quick loop)",
            confidence=0.9 if diag.get("ok") else 0.4,
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Registry — LLM 에게 노출되는 9 tool 목록
# ─────────────────────────────────────────────────────────────────────────────


TOOLS: dict[str, Any] = {
    # ontology
    "ontology.search_action_by_keyword":  call_ontology_search,
    "ontology.get_action_detail":         call_ontology_get_action_detail,
    "ontology.get_method_body":           call_ontology_get_method_body,
    "ontology.get_entity_schema":         call_ontology_get_entity_schema,
    "ontology.get_caller_graph":          call_ontology_get_caller_graph,
    # sim_v2
    "sim_v2.find_action_candidates":      call_sim_v2_find_action_candidates,
    "sim_v2.translate_java_to_python":    call_sim_v2_translate,
    "sim_v2.synthesize_fixtures":         call_sim_v2_synthesize_fixtures,
    "sim_v2.run_fixtures_in_process":     call_sim_v2_run_fixtures,
    "sim_v2.quick_diagnose_action":       call_sim_v2_quick_diagnose,
}


# Spec v2 §3 — gate 별 tool allowlist
ALLOWED_PER_GATE: dict[str, set[str]] = {
    "target_selected": {
        "ontology.search_action_by_keyword",
        "ontology.get_action_detail",
        "sim_v2.find_action_candidates",
    },
    "bundle_prepared": {
        "ontology.get_method_body",
        "ontology.get_entity_schema",
        "sim_v2.translate_java_to_python",
        "sim_v2.synthesize_fixtures",
    },
    "executed_simulation": {
        "sim_v2.run_fixtures_in_process",
        "sim_v2.quick_diagnose_action",
    },
    "executed_impact": {
        "ontology.get_caller_graph",
        "sim_v2.quick_diagnose_action",
    },
}


__all__ = [
    "ALLOWED_PER_GATE",
    "TOOLS",
    "ToolResult",
    # ontology
    "call_ontology_get_action_detail",
    "call_ontology_get_caller_graph",
    "call_ontology_get_entity_schema",
    "call_ontology_get_method_body",
    "call_ontology_search",
    # sim_v2
    "call_sim_v2_find_action_candidates",
    "call_sim_v2_quick_diagnose",
    "call_sim_v2_run_fixtures",
    "call_sim_v2_synthesize_fixtures",
    "call_sim_v2_translate",
]
