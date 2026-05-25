"""Phase 2 Step 4b — Gate III impact handler: caller_graph + quick_diagnose."""
from __future__ import annotations

import pytest

from backend.section3.agents.multiturn.gate_iii_impact import build_gate_iii_impact
from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
from backend.section3.agents.multiturn.schemas import ActionRef, CodeLocation


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


class _FakeAction:
    def __init__(self, fqn: str, repo_id: str) -> None:
        self.fqn = fqn
        self.code_method_fqn = fqn
        self.repo_id = repo_id


@pytest.fixture
def stub_sim_v2(monkeypatch):
    from backend.section3 import sim_v2_bridge as sb

    state: dict[str, object] = {
        "load_action": None,
        "quick_diagnose_result": {
            "ok": False, "fixtures": 0, "stubs": 0, "passing": 0,
            "primary_failure": "default",
        },
    }

    class _S:
        def close(self):
            pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "load_action",
        lambda session, fqn, repo: state["load_action"],
    )
    monkeypatch.setattr(
        sb, "quick_diagnose_action",
        lambda session, action: state["quick_diagnose_result"],
    )
    return state


def _slab_target() -> ActionRef:
    return ActionRef(
        action_id="action.scm.order.정합성_검증",
        code_method_fqn="com.slab.SdOrderValidator.validate(SDOrderEntity)",
        repo_id="slab-design-real-v2",
        location=CodeLocation(file_path="x.java", line_start=1, line_end=2),
    )


def _catalog_with_callers(method_fqn: str):
    return {
        "caller_graphs": {
            method_fqn: [
                {"fqn": "com.slab.SdOrderService.process",
                 "distance": 1, "via": "direct_caller"},
                {"fqn": "com.slab.OrderController.submit",
                 "distance": 2, "via": "direct_caller"},
            ],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_iii_impact_includes_caller_graph(stub_sim_v2) -> None:
    target = _slab_target()
    cat = _catalog_with_callers(target.code_method_fqn)
    onto = MockOntologyClient(catalog=cat)
    stub_sim_v2["load_action"] = _FakeAction(target.action_id, target.repo_id)
    stub_sim_v2["quick_diagnose_result"] = {
        "ok": True, "fixtures": 5, "stubs": 2, "passing": 5,
        "primary_failure": "",
    }

    payload = await build_gate_iii_impact(
        target=target, repo_id=target.repo_id, ontology_client=onto,
    )
    assert payload.kind == "executed_impact"
    fqns = [m.fqn for m in payload.affected_methods]
    assert "com.slab.SdOrderService.process" in fqns
    assert "com.slab.OrderController.submit" in fqns


@pytest.mark.asyncio
async def test_gate_iii_impact_high_confidence_when_diagnose_passing(
    stub_sim_v2,
) -> None:
    target = _slab_target()
    onto = MockOntologyClient(catalog=_catalog_with_callers(target.code_method_fqn))
    stub_sim_v2["load_action"] = _FakeAction(target.action_id, target.repo_id)
    stub_sim_v2["quick_diagnose_result"] = {
        "ok": True, "fixtures": 4, "stubs": 1, "passing": 4,
        "primary_failure": "",
    }
    payload = await build_gate_iii_impact(
        target=target, repo_id=target.repo_id, ontology_client=onto,
    )
    assert payload.confidence >= 0.8


@pytest.mark.asyncio
async def test_gate_iii_impact_low_confidence_when_diagnose_blocked(
    stub_sim_v2,
) -> None:
    target = _slab_target()
    onto = MockOntologyClient(catalog=_catalog_with_callers(target.code_method_fqn))
    stub_sim_v2["load_action"] = _FakeAction(target.action_id, target.repo_id)
    stub_sim_v2["quick_diagnose_result"] = {
        "ok": False, "fixtures": 0, "stubs": 0, "passing": 0,
        "primary_failure": "body_text 없음",
    }
    payload = await build_gate_iii_impact(
        target=target, repo_id=target.repo_id, ontology_client=onto,
    )
    assert payload.confidence < 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Findings translation (diagnose dict → Finding[])
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_iii_impact_findings_translate_primary_failure(
    stub_sim_v2,
) -> None:
    target = _slab_target()
    onto = MockOntologyClient(catalog=_catalog_with_callers(target.code_method_fqn))
    stub_sim_v2["load_action"] = _FakeAction(target.action_id, target.repo_id)
    stub_sim_v2["quick_diagnose_result"] = {
        "ok": False, "fixtures": 0, "stubs": 0, "passing": 0,
        "primary_failure": "translate 실패",
    }
    payload = await build_gate_iii_impact(
        target=target, repo_id=target.repo_id, ontology_client=onto,
    )
    kinds = [f.kind for f in payload.sim_v2_findings]
    assert any("primary_failure" in k or "blocked" in k for k in kinds)
    assert any("translate 실패" in f.message for f in payload.sim_v2_findings)


@pytest.mark.asyncio
async def test_gate_iii_impact_findings_summarize_passing_diagnose(
    stub_sim_v2,
) -> None:
    target = _slab_target()
    onto = MockOntologyClient(catalog=_catalog_with_callers(target.code_method_fqn))
    stub_sim_v2["load_action"] = _FakeAction(target.action_id, target.repo_id)
    stub_sim_v2["quick_diagnose_result"] = {
        "ok": True, "fixtures": 5, "stubs": 2, "passing": 5,
        "primary_failure": "",
    }
    payload = await build_gate_iii_impact(
        target=target, repo_id=target.repo_id, ontology_client=onto,
    )
    assert any(f.severity == "info" for f in payload.sim_v2_findings)


# ─────────────────────────────────────────────────────────────────────────────
# Sources (Provenance)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_iii_impact_sources_include_ontology_and_sim_v2(
    stub_sim_v2,
) -> None:
    target = _slab_target()
    onto = MockOntologyClient(catalog=_catalog_with_callers(target.code_method_fqn))
    stub_sim_v2["load_action"] = _FakeAction(target.action_id, target.repo_id)
    payload = await build_gate_iii_impact(
        target=target, repo_id=target.repo_id, ontology_client=onto,
    )
    sources = {s.source for s in payload.sources}
    assert "ontology" in sources
    assert "sim_v2" in sources


# ─────────────────────────────────────────────────────────────────────────────
# Missing data — Q5 "빠진 대로"
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_iii_impact_no_caller_graph_returns_empty_list(
    stub_sim_v2,
) -> None:
    target = _slab_target()
    onto = MockOntologyClient(catalog={})   # 비어있음
    stub_sim_v2["load_action"] = _FakeAction(target.action_id, target.repo_id)
    payload = await build_gate_iii_impact(
        target=target, repo_id=target.repo_id, ontology_client=onto,
    )
    assert payload.affected_methods == []


@pytest.mark.asyncio
async def test_gate_iii_impact_no_action_still_returns_payload(
    stub_sim_v2,
) -> None:
    """action 못 찾아도 caller_graph 만 surface (Q5 비전)."""
    target = _slab_target()
    onto = MockOntologyClient(catalog=_catalog_with_callers(target.code_method_fqn))
    stub_sim_v2["load_action"] = None
    payload = await build_gate_iii_impact(
        target=target, repo_id=target.repo_id, ontology_client=onto,
    )
    assert payload.kind == "executed_impact"
    assert len(payload.affected_methods) == 2
