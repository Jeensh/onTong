"""Phase 2 Step 2b — Gate I handler: intent + candidates 병합 + recommended."""
from __future__ import annotations

from typing import Any

import pytest

from backend.section3.agents.multiturn.gate_i import build_gate_i
from backend.section3.agents.multiturn.intent import StubIntentClassifier
from backend.section3.agents.multiturn.ontology_client import MockOntologyClient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


class _StubSimV2:
    """sim_v2.find_action_candidates 의 sync 함수 mock.

    monkeypatch 로 `backend.section3.sim_v2_bridge` 자리에 주입.
    """

    def __init__(self, candidates: list[dict[str, Any]]) -> None:
        self._candidates = candidates

    def open_sim_v2_session(self):  # type: ignore[no-untyped-def]
        class _S:
            def close(self):
                pass

        return _S()

    def find_action_candidates(
        self, session, user_query: str, repo_id: str, *, top_n: int = 3,
    ) -> list[dict[str, Any]]:
        return self._candidates[:top_n]


@pytest.fixture
def stub_sim_v2(monkeypatch):
    """sim_v2_bridge 의 두 함수를 stub 으로 교체."""
    from backend.section3 import sim_v2_bridge as sb

    def _make(candidates):
        s = _StubSimV2(candidates)
        monkeypatch.setattr(sb, "open_sim_v2_session", s.open_sim_v2_session)
        monkeypatch.setattr(sb, "find_action_candidates", s.find_action_candidates)
        return s

    return _make


@pytest.fixture
def slab_catalog():
    """slab-design-real-v2 의 toy catalog — ontology mock 용."""
    return {
        "actions": [
            {
                "action_id": "act:OrderService.validateOrder",
                "label": "주문 검증",
                "code_method_fqn": "com.slab.OrderService.validateOrder",
                "aliases": ["주문검증", "order validation"],
                "repo_id": "slab-design-real-v2",
                "location": {
                    "file_path": "OrderService.java",
                    "line_start": 12, "line_end": 48,
                },
            },
            {
                "action_id": "act:CumulativeProductivity.compute",
                "label": "누적 생산성",
                "code_method_fqn": "com.slab.CumulativeProductivity.compute",
                "aliases": ["cumulative productivity"],
                "repo_id": "slab-design-real-v2",
                "location": {
                    "file_path": "CumulativeProductivity.java",
                    "line_start": 30, "line_end": 80,
                },
            },
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Intent
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_i_uses_classifier_intent(stub_sim_v2, slab_catalog) -> None:
    stub_sim_v2([])  # 빈 sim_v2
    classifier = StubIntentClassifier(forced_intent="impact", forced_confidence=0.9)
    ontology = MockOntologyClient(catalog=slab_catalog)

    target = await build_gate_i(
        user_query="cumulativeProductivity 바꾸면 영향?",
        repo_id="slab-design-real-v2",
        classifier=classifier,
        ontology_client=ontology,
    )
    assert target.intent == "impact"
    assert target.user_query == "cumulativeProductivity 바꾸면 영향?"


@pytest.mark.asyncio
async def test_gate_i_ambiguous_when_classifier_returns_ambiguous(
    stub_sim_v2, slab_catalog,
) -> None:
    stub_sim_v2([])
    classifier = StubIntentClassifier(forced_intent="ambiguous")
    target = await build_gate_i(
        user_query="x",
        repo_id="slab-design-real-v2",
        classifier=classifier,
        ontology_client=MockOntologyClient(catalog=slab_catalog),
    )
    assert target.intent == "ambiguous"


# ─────────────────────────────────────────────────────────────────────────────
# Candidates merge
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_i_includes_ontology_candidates(stub_sim_v2, slab_catalog) -> None:
    """ontology 의 substring match 가 candidate 에 들어가야."""
    stub_sim_v2([])
    target = await build_gate_i(
        user_query="주문",
        repo_id="slab-design-real-v2",
        classifier=StubIntentClassifier(forced_intent="simulate"),
        ontology_client=MockOntologyClient(catalog=slab_catalog),
    )
    fqns = [c.code_method_fqn for c in target.candidates]
    assert "com.slab.OrderService.validateOrder" in fqns


@pytest.mark.asyncio
async def test_gate_i_includes_sim_v2_candidates(stub_sim_v2, slab_catalog) -> None:
    """sim_v2 의 결과도 candidate 에 들어가야."""
    stub_sim_v2([
        {
            "fqn": "com.slab.NewAction.compute",
            "label": "신규 액션",
            "code_method_fqn": "com.slab.NewAction.compute",
            "score": 5.5,
            "matched_via": "term:abc",
        },
    ])
    target = await build_gate_i(
        user_query="신규",
        repo_id="slab-design-real-v2",
        classifier=StubIntentClassifier(forced_intent="simulate"),
        ontology_client=MockOntologyClient(catalog={}),
    )
    fqns = [c.code_method_fqn for c in target.candidates]
    assert "com.slab.NewAction.compute" in fqns


@pytest.mark.asyncio
async def test_gate_i_dedupes_by_code_method_fqn(stub_sim_v2, slab_catalog) -> None:
    """ontology 와 sim_v2 가 같은 method 를 반환 → 한 행으로 합침."""
    stub_sim_v2([
        {
            "fqn": "com.slab.OrderService.validateOrder",
            "label": "주문 검증 (sim_v2)",
            "code_method_fqn": "com.slab.OrderService.validateOrder",
            "score": 4.0,
            "matched_via": "term:order",
        },
    ])
    target = await build_gate_i(
        user_query="주문",
        repo_id="slab-design-real-v2",
        classifier=StubIntentClassifier(forced_intent="simulate"),
        ontology_client=MockOntologyClient(catalog=slab_catalog),
    )
    matched = [
        c for c in target.candidates
        if c.code_method_fqn == "com.slab.OrderService.validateOrder"
    ]
    assert len(matched) == 1


@pytest.mark.asyncio
async def test_gate_i_recommended_index_is_zero_when_candidates(
    stub_sim_v2, slab_catalog,
) -> None:
    stub_sim_v2([])
    target = await build_gate_i(
        user_query="주문",
        repo_id="slab-design-real-v2",
        classifier=StubIntentClassifier(forced_intent="simulate"),
        ontology_client=MockOntologyClient(catalog=slab_catalog),
    )
    assert target.candidates
    assert target.recommended_index == 0


@pytest.mark.asyncio
async def test_gate_i_recommended_index_none_when_empty(stub_sim_v2) -> None:
    stub_sim_v2([])
    target = await build_gate_i(
        user_query="nothing matches",
        repo_id="slab-design-real-v2",
        classifier=StubIntentClassifier(forced_intent="simulate"),
        ontology_client=MockOntologyClient(catalog={}),
    )
    assert target.candidates == []
    assert target.recommended_index is None


# ─────────────────────────────────────────────────────────────────────────────
# Provenance (Q5 비전)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_i_sources_include_llm_inference(stub_sim_v2, slab_catalog) -> None:
    """intent 분류는 llm_inference Provenance 로 surface."""
    stub_sim_v2([])
    target = await build_gate_i(
        user_query="주문 검증",
        repo_id="slab-design-real-v2",
        classifier=StubIntentClassifier(
            forced_intent="simulate", forced_confidence=0.91,
            forced_reasoning="시뮬 키워드 검출",
        ),
        ontology_client=MockOntologyClient(catalog=slab_catalog),
    )
    sources = target.sources
    llm_sources = [s for s in sources if s.source == "llm_inference"]
    assert len(llm_sources) == 1
    assert "시뮬" in llm_sources[0].detail or "시뮬" in llm_sources[0].detail


@pytest.mark.asyncio
async def test_gate_i_sources_include_ontology(stub_sim_v2, slab_catalog) -> None:
    stub_sim_v2([])
    target = await build_gate_i(
        user_query="주문",
        repo_id="slab-design-real-v2",
        classifier=StubIntentClassifier(forced_intent="simulate"),
        ontology_client=MockOntologyClient(catalog=slab_catalog),
    )
    assert any(s.source == "ontology" for s in target.sources)


@pytest.mark.asyncio
async def test_gate_i_sources_include_sim_v2(stub_sim_v2) -> None:
    stub_sim_v2([
        {
            "fqn": "com.slab.NewAction.compute",
            "label": "신규",
            "code_method_fqn": "com.slab.NewAction.compute",
            "score": 3.0,
            "matched_via": "term:x",
        },
    ])
    target = await build_gate_i(
        user_query="x",
        repo_id="slab-design-real-v2",
        classifier=StubIntentClassifier(forced_intent="simulate"),
        ontology_client=MockOntologyClient(catalog={}),
    )
    assert any(s.source == "sim_v2" for s in target.sources)


# ─────────────────────────────────────────────────────────────────────────────
# Korean preservation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_i_preserves_korean_labels(stub_sim_v2, slab_catalog) -> None:
    stub_sim_v2([])
    target = await build_gate_i(
        user_query="주문 검증",
        repo_id="slab-design-real-v2",
        classifier=StubIntentClassifier(forced_intent="simulate"),
        ontology_client=MockOntologyClient(catalog=slab_catalog),
    )
    labels = [c.label for c in target.candidates]
    assert any("주문" in lbl for lbl in labels)
