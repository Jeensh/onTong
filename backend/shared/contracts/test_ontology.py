"""Section 2 ↔ Section 3 Ontology contract pytest 스위트.

스펙(`section2-section3-protocol.md`)에 정의된 Pydantic 모델의 검증 동작을
확인한다. 실제 Neo4j 연결이 없어도 동작해야 하므로 순수 모델 단위 테스트만 포함.

실행: ``pytest backend/shared/contracts/test_ontology.py -v``
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from backend.shared.contracts.ontology import (
    ImpactAnalysisResult,
    Intent,
    LocatorResult,
    MissingInfo,
    MissingInfoQuestion,
    OntologyRequest,
    OntologyResponse,
    Status,
    TestDataResult,
    VisualizationHint,
)


# ─────────────────────────────────────────────────────────────
# Intent / Status enum
# ─────────────────────────────────────────────────────────────


def test_intent_has_five_members() -> None:
    assert {i.value for i in Intent} == {
        "query",
        "simulate",
        "impact_analysis",
        "optimize",
        "explain",
    }


def test_status_has_five_members() -> None:
    assert {s.value for s in Status} == {
        "success",
        "partial",
        "need_more_info",
        "unsupported",
        "error",
    }


# ─────────────────────────────────────────────────────────────
# OntologyRequest
# ─────────────────────────────────────────────────────────────


def test_ontology_request_minimal() -> None:
    req = OntologyRequest(request_id="req-1", intent=Intent.QUERY)
    assert req.request_id == "req-1"
    assert req.intent is Intent.QUERY
    assert req.parameters == {}
    assert req.context is None


def test_ontology_request_intent_string_coerced() -> None:
    req = OntologyRequest(request_id="req-1", intent="impact_analysis")
    assert req.intent is Intent.IMPACT_ANALYSIS


def test_ontology_request_invalid_intent() -> None:
    with pytest.raises(ValidationError):
        OntologyRequest(request_id="req-1", intent="not_a_real_intent")


def test_ontology_request_full_payload() -> None:
    payload = {
        "request_id": "req-impact-001",
        "intent": "impact_analysis",
        "natural_language": "TB_C40_050SC070에 컬럼 추가하면 영향이 어디까지?",
        "parameters": {
            "target": {"kind": "table", "id": "TB_C40_050SC070"},
            "change_type": "add_column",
        },
        "context": {"ontology_version": "2026.04.25"},
        "expected_output": {"visualization": "impact_tree"},
    }
    req = OntologyRequest(**payload)
    assert req.parameters["target"]["id"] == "TB_C40_050SC070"
    # JSON round-trip
    dumped = json.loads(req.model_dump_json())
    assert dumped["intent"] == "impact_analysis"


# ─────────────────────────────────────────────────────────────
# OntologyResponse
# ─────────────────────────────────────────────────────────────


def test_ontology_response_success_minimal() -> None:
    resp = OntologyResponse(
        request_id="req-1", status=Status.SUCCESS, result={"answer": 42}
    )
    assert resp.confidence == 1.0
    assert resp.timestamp is not None


def test_ontology_response_confidence_bounds() -> None:
    OntologyResponse(request_id="r", status=Status.SUCCESS, confidence=0.0)
    OntologyResponse(request_id="r", status=Status.SUCCESS, confidence=1.0)
    with pytest.raises(ValidationError):
        OntologyResponse(request_id="r", status=Status.SUCCESS, confidence=1.5)
    with pytest.raises(ValidationError):
        OntologyResponse(request_id="r", status=Status.SUCCESS, confidence=-0.1)


def test_ontology_response_need_more_info() -> None:
    resp = OntologyResponse(
        request_id="r",
        status=Status.NEED_MORE_INFO,
        missing_info=MissingInfo(
            reason="대상 테이블이 모호합니다",
            questions=[
                MissingInfoQuestion(
                    field="target_table",
                    question="어떤 테이블을 의미하나요?",
                    input_type="select",
                    options=[
                        {"value": "TB_C40_050SC070", "label": "Edging 능력 기준"},
                        {"value": "TB_C40_050SC080", "label": "열연 Min 단중"},
                    ],
                )
            ],
        ),
    )
    assert resp.missing_info is not None
    assert len(resp.missing_info.questions) == 1
    assert resp.missing_info.questions[0].input_type == "select"


# ─────────────────────────────────────────────────────────────
# Visualization & 결과 모델
# ─────────────────────────────────────────────────────────────


def test_visualization_hint_invalid_type_rejected() -> None:
    with pytest.raises(ValidationError):
        VisualizationHint(type="bogus_chart")


def test_impact_analysis_result_risk_levels() -> None:
    for risk in ("HIGH", "MEDIUM", "LOW"):
        ImpactAnalysisResult(
            summary="ok",
            direct_impact={},
            indirect_impact={},
            risk_level=risk,
        )
    with pytest.raises(ValidationError):
        ImpactAnalysisResult(
            summary="x",
            direct_impact={},
            indirect_impact={},
            risk_level="CRITICAL",
        )


def test_test_data_result_default_dependencies() -> None:
    r = TestDataResult(test_cases=[{"name": "tc1"}])
    assert r.data_dependencies == []


def test_locator_result_required_fields() -> None:
    r = LocatorResult(
        matched_terms=[{"id": "term_edging"}],
        process_locations=[{"step_number": 2}],
        source_locations=[{"class_name": "SlabDesignService"}],
        data_locations=[{"table_name": "TB_C40_050SC070"}],
    )
    assert r.related_terms == []


# ─────────────────────────────────────────────────────────────
# 시리얼라이즈 / 디시리얼라이즈
# ─────────────────────────────────────────────────────────────


def test_request_response_round_trip() -> None:
    req = OntologyRequest(
        request_id="rt-1",
        intent=Intent.EXPLAIN,
        parameters={"keyword": "Edging"},
    )
    payload = req.model_dump_json()
    restored = OntologyRequest.model_validate_json(payload)
    assert restored.intent is Intent.EXPLAIN
    assert restored.parameters == {"keyword": "Edging"}


def test_response_round_trip_with_visualization() -> None:
    resp = OntologyResponse(
        request_id="rt-2",
        status=Status.SUCCESS,
        result={
            "visualization": VisualizationHint(
                type="impact_tree",
                payload={"root": "TB_C40_050SC070"},
            ).model_dump()
        },
    )
    restored = OntologyResponse.model_validate_json(resp.model_dump_json())
    assert restored.status is Status.SUCCESS
    assert restored.result is not None
    assert restored.result["visualization"]["type"] == "impact_tree"
