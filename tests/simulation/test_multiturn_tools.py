"""Step 1d TDD — 9 tool wrapper + Provenance auto-attach.

9 tools (spec v2 §3):
  ontology.search_action_by_keyword / get_action_detail / get_method_body /
  get_entity_schema / get_caller_graph
  sim_v2.find_action_candidates / translate_java_to_python /
  synthesize_fixtures / run_fixtures_in_process / quick_diagnose_action
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────


def test_tools_registry_lists_9_tools() -> None:
    from backend.section3.agents.multiturn.tools import TOOLS
    expected = {
        "ontology.search_action_by_keyword",
        "ontology.get_action_detail",
        "ontology.get_method_body",
        "ontology.get_entity_schema",
        "ontology.get_caller_graph",
        "sim_v2.find_action_candidates",
        "sim_v2.translate_java_to_python",
        "sim_v2.synthesize_fixtures",
        "sim_v2.run_fixtures_in_process",
        "sim_v2.quick_diagnose_action",
    }
    assert set(TOOLS.keys()) == expected


def test_each_gate_has_allowed_set() -> None:
    """Spec §3 — gate 별 tool allowlist (safety)."""
    from backend.section3.agents.multiturn.tools import ALLOWED_PER_GATE
    expected_gates = {
        "target_selected",
        "bundle_prepared",
        "executed_simulation",
        "executed_impact",
    }
    assert set(ALLOWED_PER_GATE.keys()) == expected_gates
    # Gate I: ontology search + sim_v2 candidates + ontology detail
    assert "ontology.search_action_by_keyword" in ALLOWED_PER_GATE["target_selected"]
    assert "sim_v2.find_action_candidates" in ALLOWED_PER_GATE["target_selected"]
    # Gate III impact 분기: caller_graph 가 그쪽에만
    assert "ontology.get_caller_graph" in ALLOWED_PER_GATE["executed_impact"]
    assert "ontology.get_caller_graph" not in ALLOWED_PER_GATE["executed_simulation"]


# ─────────────────────────────────────────────────────────────────────────────
# ToolResult shape — Provenance auto-attach
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ontology_search_attaches_provenance() -> None:
    """Q5 비전: 각 tool 결과에 Provenance 자동 부착 (source="ontology")."""
    from backend.section3.agents.multiturn.tools import call_ontology_search
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient

    catalog = {
        "actions": [
            {
                "action_id": "x", "label": "주문", "code_method_fqn": "X.foo",
                "aliases": [], "repo_id": "r",
                "location": {"file_path": "X.java", "line_start": 1, "line_end": 5},
            },
        ],
    }
    client = MockOntologyClient(catalog=catalog)
    result = await call_ontology_search(client, query="주문", repo_id="r")
    assert result.provenance.source == "ontology"
    assert "search_action_by_keyword" in result.provenance.detail
    assert len(result.data) == 1


@pytest.mark.asyncio
async def test_ontology_get_method_body_provenance_marks_missing() -> None:
    """누락 → confidence 0.0 + source=ontology."""
    from backend.section3.agents.multiturn.tools import call_ontology_get_method_body
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    client = MockOntologyClient(catalog={})
    result = await call_ontology_get_method_body(client, fqn="x", repo_id="r")
    assert result.data is None
    assert result.provenance.source == "ontology"
    assert result.provenance.confidence == 0.0


@pytest.mark.asyncio
async def test_sim_v2_tool_runs_in_thread() -> None:
    """sim_v2 sync 함수는 asyncio.to_thread 로 await — call 가능 확인."""
    from backend.section3.agents.multiturn.tools import call_sim_v2_translate
    # translate_java_to_python 가 fake body 받았을 때 None 반환 (parser fail) — OK
    result = await call_sim_v2_translate(body_text="not java")
    assert result.provenance.source == "sim_v2"
    assert "translate_java_to_python" in result.provenance.detail
    # data 가 None 일 수 있지만 crash 없음
