"""Phase 2 Step 4a — Gate III sim handler: run fixtures + invariant aggregation."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from backend.section3.agents.multiturn.gate_iii_sim import build_gate_iii_sim
from backend.section3.agents.multiturn.schemas import (
    ActionRef,
    CodeLocation,
    GateBundle,
    Provenance,
    SchemaSummary,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _FakeFix:
    fixture_id: str
    input_args: tuple
    input_kwargs: dict
    expected_output: object = None
    python_source: str = ""
    function_name: str = ""


@dataclass
class _FakeReport:
    fixtures: list


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
        "synthesize_result": None,
        "build_stubs_result": {},
        "run_results": [],
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
        sb, "synthesize_fixtures",
        lambda session, action, *, function_name, python_source, max_combinations=12: state["synthesize_result"],
    )
    monkeypatch.setattr(
        sb, "build_stubs",
        lambda session, *, method_fqn, repo_id, python_source: state["build_stubs_result"],
    )
    monkeypatch.setattr(
        sb, "run_fixtures_in_process",
        lambda fixtures, *, stub_namespace=None, declared_return="Any", allowed_exceptions=(): state["run_results"],
    )
    return state


def _slab_bundle() -> GateBundle:
    target = ActionRef(
        action_id="action.scm.order.정합성_검증",
        code_method_fqn="com.slab.SdOrderValidator.validate(SDOrderEntity)",
        repo_id="slab-design-real-v2",
        location=CodeLocation(file_path="X.java", line_start=1, line_end=2),
    )
    return GateBundle(
        target=target,
        java_source="public X validate(SDOrderEntity o) {}",
        python_source="def validate(o):\n    return 'OK'\n",
        idiom_diffs=[],
        fixtures=[],   # Gate III re-synthesizes, so this can be empty
        schema_summary=SchemaSummary(entity_name="SDOrderEntity", fields=[]),
        sources=[Provenance(source="sim_v2", detail="fake bundle", confidence=0.9)],
        confidence=0.8,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_iii_sim_all_pass_is_clean(stub_sim_v2) -> None:
    stub_sim_v2["load_action"] = _FakeAction(
        "action.scm.order.정합성_검증", "slab-design-real-v2",
    )
    stub_sim_v2["synthesize_result"] = _FakeReport(fixtures=[
        _FakeFix(fixture_id="fx-1", input_args=(None,), input_kwargs={}),
        _FakeFix(fixture_id="fx-2", input_args=("a",), input_kwargs={}),
    ])
    stub_sim_v2["run_results"] = [
        {"case_id": "fx-1", "input": {"args": [None], "kwargs": {}},
         "execution": {"ok": True, "result": {"ok": True, "result": "OK"},
                       "error": None}, "invariant_status": "PASS"},
        {"case_id": "fx-2", "input": {"args": ["a"], "kwargs": {}},
         "execution": {"ok": True, "result": {"ok": True, "result": "OK"},
                       "error": None}, "invariant_status": "PASS"},
    ]

    exec_payload = await build_gate_iii_sim(
        bundle=_slab_bundle(), repo_id="slab-design-real-v2",
    )
    assert exec_payload.kind == "executed_simulation"
    assert len(exec_payload.results) == 2
    assert all(r.status == "PASS" for r in exec_payload.results)
    assert exec_payload.invariant_status == "clean"


@pytest.mark.asyncio
async def test_gate_iii_sim_outputs_carry_case_ids(stub_sim_v2) -> None:
    stub_sim_v2["load_action"] = _FakeAction(
        "x", "slab-design-real-v2",
    )
    stub_sim_v2["synthesize_result"] = _FakeReport(fixtures=[
        _FakeFix(fixture_id="fx-9", input_args=(), input_kwargs={}),
    ])
    stub_sim_v2["run_results"] = [
        {"case_id": "fx-9", "input": {"args": [], "kwargs": {}},
         "execution": {"ok": True, "result": {"ok": True, "result": 42},
                       "error": None}, "invariant_status": "PASS"},
    ]
    exec_payload = await build_gate_iii_sim(
        bundle=_slab_bundle(), repo_id="slab-design-real-v2",
    )
    assert exec_payload.results[0].fixture_id == "fx-9"
    assert exec_payload.results[0].output == 42


# ─────────────────────────────────────────────────────────────────────────────
# Failure aggregation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_iii_sim_dominant_failure_wins_invariant(stub_sim_v2) -> None:
    stub_sim_v2["load_action"] = _FakeAction(
        "x", "slab-design-real-v2",
    )
    stub_sim_v2["synthesize_result"] = _FakeReport(fixtures=[
        _FakeFix(fixture_id=f"fx-{i}", input_args=(), input_kwargs={})
        for i in range(3)
    ])
    stub_sim_v2["run_results"] = [
        {"case_id": "fx-0", "input": {"args": [], "kwargs": {}},
         "execution": {"ok": False, "result": {"ok": False, "result": None},
                       "error": "FAIL_RETURN_TYPE"},
         "invariant_status": "FAIL_RETURN_TYPE"},
        {"case_id": "fx-1", "input": {"args": [], "kwargs": {}},
         "execution": {"ok": False, "result": {"ok": False, "result": None},
                       "error": "FAIL_RETURN_TYPE"},
         "invariant_status": "FAIL_RETURN_TYPE"},
        {"case_id": "fx-2", "input": {"args": [], "kwargs": {}},
         "execution": {"ok": True, "result": {"ok": True, "result": "OK"},
                       "error": None}, "invariant_status": "PASS"},
    ]
    exec_payload = await build_gate_iii_sim(
        bundle=_slab_bundle(), repo_id="slab-design-real-v2",
    )
    assert exec_payload.invariant_status == "fail_return_type"


@pytest.mark.asyncio
async def test_gate_iii_sim_unexpected_throw_invariant(stub_sim_v2) -> None:
    stub_sim_v2["load_action"] = _FakeAction("x", "slab-design-real-v2")
    stub_sim_v2["synthesize_result"] = _FakeReport(fixtures=[
        _FakeFix(fixture_id="fx-0", input_args=(), input_kwargs={}),
    ])
    stub_sim_v2["run_results"] = [
        {"case_id": "fx-0", "input": {"args": [], "kwargs": {}},
         "execution": {"ok": False, "result": {"ok": False, "result": None},
                       "error": "RuntimeError"},
         "invariant_status": "FAIL_UNEXPECTED_THROW"},
    ]
    exec_payload = await build_gate_iii_sim(
        bundle=_slab_bundle(), repo_id="slab-design-real-v2",
    )
    assert exec_payload.invariant_status == "fail_unexpected_throw"


# ─────────────────────────────────────────────────────────────────────────────
# Failure modes — missing data
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_iii_sim_missing_python_source_returns_error(stub_sim_v2) -> None:
    bundle = _slab_bundle()
    bundle = bundle.model_copy(update={"python_source": ""})
    exec_payload = await build_gate_iii_sim(
        bundle=bundle, repo_id="slab-design-real-v2",
    )
    assert exec_payload.invariant_status == "error"
    assert exec_payload.results == []


@pytest.mark.asyncio
async def test_gate_iii_sim_no_action_returns_error(stub_sim_v2) -> None:
    stub_sim_v2["load_action"] = None
    exec_payload = await build_gate_iii_sim(
        bundle=_slab_bundle(), repo_id="slab-design-real-v2",
    )
    assert exec_payload.invariant_status == "error"


@pytest.mark.asyncio
async def test_gate_iii_sim_no_fixtures_returns_error(stub_sim_v2) -> None:
    stub_sim_v2["load_action"] = _FakeAction("x", "slab-design-real-v2")
    stub_sim_v2["synthesize_result"] = _FakeReport(fixtures=[])
    exec_payload = await build_gate_iii_sim(
        bundle=_slab_bundle(), repo_id="slab-design-real-v2",
    )
    assert exec_payload.invariant_status == "error"


# ─────────────────────────────────────────────────────────────────────────────
# Provenance
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_iii_sim_sources_include_sim_v2_run(stub_sim_v2) -> None:
    stub_sim_v2["load_action"] = _FakeAction("x", "slab-design-real-v2")
    stub_sim_v2["synthesize_result"] = _FakeReport(fixtures=[
        _FakeFix(fixture_id="fx-0", input_args=(), input_kwargs={}),
    ])
    stub_sim_v2["run_results"] = [
        {"case_id": "fx-0", "input": {"args": [], "kwargs": {}},
         "execution": {"ok": True, "result": {"ok": True, "result": "OK"},
                       "error": None}, "invariant_status": "PASS"},
    ]
    exec_payload = await build_gate_iii_sim(
        bundle=_slab_bundle(), repo_id="slab-design-real-v2",
    )
    assert any(s.source == "sim_v2" for s in exec_payload.sources)
