"""Phase 2 Step 3a — Gate II handler: Java body + Python + Schema + Fixtures bundle."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from backend.section3.agents.multiturn.gate_ii import build_gate_ii
from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
from backend.section3.agents.multiturn.schemas import (
    ActionRef,
    CodeLocation,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — sim_v2 stubs
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _FakeFixture:
    fixture_id: str
    input_args: tuple
    input_kwargs: dict


@dataclass
class _FakeFixtureSet:
    fixtures: list[_FakeFixture]


class _FakeAction:
    def __init__(self, fqn: str) -> None:
        self.fqn = fqn


@pytest.fixture
def stub_sim_v2(monkeypatch):
    """sim_v2_bridge 의 6개 sync 함수 stub. caller 가 각각 지정 가능."""
    from backend.section3 import sim_v2_bridge as sb

    state: dict[str, Any] = {
        "translate_result": None,
        "load_action_result": None,
        "synthesize_result": None,
    }

    class _S:
        def close(self):
            pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "translate_java_to_python", lambda src: state["translate_result"],
    )
    monkeypatch.setattr(
        sb, "load_action",
        lambda session, fqn, repo: state["load_action_result"],
    )
    monkeypatch.setattr(
        sb, "synthesize_fixtures",
        lambda session, action, *, function_name, python_source, max_combinations=12: (
            state["synthesize_result"]
        ),
    )
    return state


@pytest.fixture
def slab_target() -> ActionRef:
    return ActionRef(
        action_id="action.scm.order.정합성_검증",
        code_method_fqn="com.slab.SdOrderValidator.validate(SDOrderEntity)",
        repo_id="slab-design-real-v2",
        location=CodeLocation(
            file_path="SdOrderValidator.java",
            line_start=12, line_end=48,
        ),
    )


@pytest.fixture
def full_catalog(slab_target):
    """모든 ontology data 다 있는 catalog."""
    return {
        "actions": [
            {
                "action_id": slab_target.action_id,
                "label": "주문 검증",
                "code_method_fqn": slab_target.code_method_fqn,
                "aliases": [],
                "repo_id": slab_target.repo_id,
                "location": {
                    "file_path": slab_target.location.file_path,
                    "line_start": slab_target.location.line_start,
                    "line_end": slab_target.location.line_end,
                },
            },
        ],
        "method_bodies": {
            slab_target.code_method_fqn: (
                "public Result validate(SDOrderEntity o) { return Result.OK; }"
            ),
        },
        "entity_schemas": {
            "SDOrderEntity": {
                "entity_name": "SDOrderEntity",
                "fields": [
                    {"name": "id", "type_name": "varchar(64)", "nullable": False},
                    {"name": "qty", "type_name": "int", "nullable": False},
                ],
            },
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Happy path — all data present
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_ii_happy_path_builds_full_bundle(
    stub_sim_v2, slab_target, full_catalog,
) -> None:
    stub_sim_v2["translate_result"] = (
        "def validate(o):\n    return 'OK'\n", "validate",
    )
    stub_sim_v2["load_action_result"] = _FakeAction(slab_target.action_id)
    stub_sim_v2["synthesize_result"] = _FakeFixtureSet(fixtures=[
        _FakeFixture(fixture_id="fx-1", input_args=(None,), input_kwargs={}),
        _FakeFixture(fixture_id="fx-2", input_args=("x",), input_kwargs={"k": 1}),
    ])
    onto = MockOntologyClient(catalog=full_catalog)

    bundle = await build_gate_ii(
        target=slab_target, repo_id=slab_target.repo_id, ontology_client=onto,
    )
    assert bundle.kind == "bundle_prepared"
    assert bundle.target.code_method_fqn == slab_target.code_method_fqn
    assert "validate" in bundle.java_source
    assert "def validate" in bundle.python_source
    assert bundle.schema_summary.entity_name == "SDOrderEntity"
    assert len(bundle.schema_summary.fields) == 2
    assert len(bundle.fixtures) == 2
    assert bundle.confidence > 0.7   # 다 잘 풀린 happy path


@pytest.mark.asyncio
async def test_gate_ii_sources_collect_4_provenance(
    stub_sim_v2, slab_target, full_catalog,
) -> None:
    """ontology body + sim_v2 translate + ontology schema + sim_v2 fixtures = 4 source."""
    stub_sim_v2["translate_result"] = ("def f(): pass\n", "f")
    stub_sim_v2["load_action_result"] = _FakeAction(slab_target.action_id)
    stub_sim_v2["synthesize_result"] = _FakeFixtureSet(fixtures=[])
    onto = MockOntologyClient(catalog=full_catalog)

    bundle = await build_gate_ii(
        target=slab_target, repo_id=slab_target.repo_id, ontology_client=onto,
    )
    sources = {(s.source, "found" if s.confidence and s.confidence > 0 else "missing")
               for s in bundle.sources}
    # 최소 ontology 2 + sim_v2 2 = 4 source
    assert sum(1 for s in bundle.sources if s.source == "ontology") >= 2
    assert sum(1 for s in bundle.sources if s.source == "sim_v2") >= 2


# ─────────────────────────────────────────────────────────────────────────────
# Missing data — Q5 비전 "빠진 내용은 빠진대로"
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_ii_missing_body_returns_empty_string_low_confidence(
    stub_sim_v2, slab_target,
) -> None:
    onto = MockOntologyClient(catalog={})   # 아무것도 없음
    stub_sim_v2["translate_result"] = None
    stub_sim_v2["load_action_result"] = None
    stub_sim_v2["synthesize_result"] = None

    bundle = await build_gate_ii(
        target=slab_target, repo_id=slab_target.repo_id, ontology_client=onto,
    )
    assert bundle.kind == "bundle_prepared"
    assert bundle.java_source == ""
    assert bundle.python_source == ""
    assert bundle.fixtures == []
    assert bundle.confidence < 0.3


@pytest.mark.asyncio
async def test_gate_ii_translate_failure_keeps_java_drops_python(
    stub_sim_v2, slab_target, full_catalog,
) -> None:
    """body 는 있는데 translate 실패 (None) → java OK, python="" + confidence ↓."""
    stub_sim_v2["translate_result"] = None
    stub_sim_v2["load_action_result"] = None
    stub_sim_v2["synthesize_result"] = None
    onto = MockOntologyClient(catalog=full_catalog)

    bundle = await build_gate_ii(
        target=slab_target, repo_id=slab_target.repo_id, ontology_client=onto,
    )
    assert "validate" in bundle.java_source
    assert bundle.python_source == ""
    assert bundle.fixtures == []


@pytest.mark.asyncio
async def test_gate_ii_missing_entity_schema_returns_empty_summary(
    stub_sim_v2, slab_target,
) -> None:
    """method body 만 있고 entity_schema 없음 → empty SchemaSummary (entity_name='')."""
    cat = {
        "method_bodies": {
            slab_target.code_method_fqn: "public X foo() { return null; }",
        },
    }
    stub_sim_v2["translate_result"] = ("def foo(): return None\n", "foo")
    stub_sim_v2["load_action_result"] = _FakeAction(slab_target.action_id)
    stub_sim_v2["synthesize_result"] = _FakeFixtureSet(fixtures=[])
    onto = MockOntologyClient(catalog=cat)

    bundle = await build_gate_ii(
        target=slab_target, repo_id=slab_target.repo_id, ontology_client=onto,
    )
    assert bundle.schema_summary.fields == []
    # entity_name 추출 실패 시 빈 문자열 (parameter 가 없어서 entity 없음)
    assert bundle.schema_summary.entity_name == ""


# ─────────────────────────────────────────────────────────────────────────────
# Entity 추출
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_ii_extracts_entity_from_method_signature(
    stub_sim_v2, slab_target, full_catalog,
) -> None:
    """SdOrderValidator.validate(SDOrderEntity) → entity_name 'SDOrderEntity'."""
    stub_sim_v2["translate_result"] = ("def f(o): pass\n", "f")
    stub_sim_v2["load_action_result"] = _FakeAction(slab_target.action_id)
    stub_sim_v2["synthesize_result"] = _FakeFixtureSet(fixtures=[])
    onto = MockOntologyClient(catalog=full_catalog)

    bundle = await build_gate_ii(
        target=slab_target, repo_id=slab_target.repo_id, ontology_client=onto,
    )
    assert bundle.schema_summary.entity_name == "SDOrderEntity"


# ─────────────────────────────────────────────────────────────────────────────
# Schema roundtrip
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_ii_payload_serializes_to_dict_kind(
    stub_sim_v2, slab_target, full_catalog,
) -> None:
    stub_sim_v2["translate_result"] = ("def f(): pass\n", "f")
    stub_sim_v2["load_action_result"] = _FakeAction(slab_target.action_id)
    stub_sim_v2["synthesize_result"] = _FakeFixtureSet(fixtures=[])
    onto = MockOntologyClient(catalog=full_catalog)

    bundle = await build_gate_ii(
        target=slab_target, repo_id=slab_target.repo_id, ontology_client=onto,
    )
    payload = bundle.model_dump()
    assert payload["kind"] == "bundle_prepared"
    assert "java_source" in payload
    assert "python_source" in payload
    assert "fixtures" in payload
    assert "schema_summary" in payload
    assert "sources" in payload


# ─────────────────────────────────────────────────────────────────────────────
# Phase 8 — idiom_diffs surface (W75 rewrites)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_ii_extracts_idiom_diffs_from_translate_result(
    stub_sim_v2, slab_target, full_catalog,
) -> None:
    """translate_java_to_python 가 3-tuple (src, fn, idiom_rewrites) 반환 시
    GateBundle.idiom_diffs 가 populated 되어야 한다."""
    stub_sim_v2["translate_result"] = (
        "def validate(o):\n    return len(o)\n",
        "validate",
        [
            {
                "idiom_name": "String.length",
                "java_snippet": "o.length()",
                "python_snippet": "len(o)",
                "tier": "unknown",
                "arity": 0,
            },
            {
                "idiom_name": "List.isEmpty",
                "java_snippet": "items.isEmpty()",
                "python_snippet": "(not items)",
                "tier": "typed",
                "arity": 0,
            },
        ],
    )
    stub_sim_v2["load_action_result"] = _FakeAction(slab_target.action_id)
    stub_sim_v2["synthesize_result"] = _FakeFixtureSet(fixtures=[])
    onto = MockOntologyClient(catalog=full_catalog)

    bundle = await build_gate_ii(
        target=slab_target, repo_id=slab_target.repo_id, ontology_client=onto,
    )
    assert len(bundle.idiom_diffs) == 2
    names = {d.idiom_name for d in bundle.idiom_diffs}
    assert names == {"String.length", "List.isEmpty"}


@pytest.mark.asyncio
async def test_gate_ii_dedupes_repeated_idiom_rewrites(
    stub_sim_v2, slab_target, full_catalog,
) -> None:
    """동일 (java_snippet, python_snippet) 은 dedup — 같은 idiom 이 여러 번 등장해도 1건."""
    stub_sim_v2["translate_result"] = (
        "def foo(): pass\n",
        "foo",
        [
            {"idiom_name": "String.length", "java_snippet": "s.length()",
             "python_snippet": "len(s)", "tier": "unknown", "arity": 0},
            {"idiom_name": "String.length", "java_snippet": "s.length()",
             "python_snippet": "len(s)", "tier": "unknown", "arity": 0},
        ],
    )
    stub_sim_v2["load_action_result"] = _FakeAction(slab_target.action_id)
    stub_sim_v2["synthesize_result"] = _FakeFixtureSet(fixtures=[])
    onto = MockOntologyClient(catalog=full_catalog)

    bundle = await build_gate_ii(
        target=slab_target, repo_id=slab_target.repo_id, ontology_client=onto,
    )
    assert len(bundle.idiom_diffs) == 1


@pytest.mark.asyncio
async def test_gate_ii_backward_compat_2tuple_no_idiom_diffs(
    stub_sim_v2, slab_target, full_catalog,
) -> None:
    """기존 2-tuple stub 도 graceful — idiom_diffs 는 빈 리스트."""
    stub_sim_v2["translate_result"] = ("def f(): pass\n", "f")
    stub_sim_v2["load_action_result"] = _FakeAction(slab_target.action_id)
    stub_sim_v2["synthesize_result"] = _FakeFixtureSet(fixtures=[])
    onto = MockOntologyClient(catalog=full_catalog)

    bundle = await build_gate_ii(
        target=slab_target, repo_id=slab_target.repo_id, ontology_client=onto,
    )
    assert bundle.idiom_diffs == []
