"""Tests for backend/modeling/ontology/builder_service.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.modeling.ontology.builder_service import (
    _strip_code_fences,
    draft_ontology_yaml,
    ontology_to_yaml,
    validate_yaml_text,
)
from backend.modeling.ontology.schema import (
    Formula,
    IOPort,
    Ontology,
    OntologyHeader,
    Process,
    ValueType,
)


class TestValidateYamlText:
    def test_empty_yaml(self) -> None:
        assert validate_yaml_text("") == ["YAML이 비어 있습니다."]
        assert validate_yaml_text("   \n  ") == ["YAML이 비어 있습니다."]

    def test_malformed_yaml(self) -> None:
        errors = validate_yaml_text("key: : value")
        assert any("YAML 파싱 오류" in e for e in errors)

    def test_root_not_mapping(self) -> None:
        assert validate_yaml_text("- item1\n- item2") == [
            "YAML 루트는 매핑(dict)이어야 합니다."
        ]

    def test_schema_violation(self) -> None:
        bad = "ontology:\n  id: test\nprocesses:\n  - name: missing-id\n"
        errors = validate_yaml_text(bad)
        assert errors
        assert any("id" in e for e in errors)

    def test_valid_minimal_ontology(self) -> None:
        good = 'ontology:\n  id: test-v1\n  version: "1.0"\n'
        assert validate_yaml_text(good) == []

    def test_valid_with_process(self) -> None:
        good = """
ontology:
  id: heating-sop
  version: "1.0"
processes:
  - id: Heating/Soak
    name: 균열 구간
    inputs:
      - {id: T, name: Temperature, type: float}
    outputs:
      - {id: Tset, name: Setpoint, type: float}
    formula:
      expression: "T + 0"
    rules:
      - id: SoakBand
        condition: "abs(T - Tset) > 2"
        action_type: warning
        action_message: "균열 편차 초과"
"""
        assert validate_yaml_text(good) == []

    def test_duplicate_process_id_caught_by_graph_validator(self) -> None:
        bad = """
ontology:
  id: dup-test
processes:
  - id: P
    name: P
    inputs: [{id: a, name: A, type: float}]
    outputs: [{id: c, name: C, type: float}]
  - id: P
    name: P
    inputs: [{id: a, name: A, type: float}]
    outputs: [{id: c, name: C, type: float}]
"""
        errors = validate_yaml_text(bad)
        assert errors
        assert any("P" in e for e in errors)


class TestStripCodeFences:
    def test_plain_text_passes_through(self) -> None:
        assert _strip_code_fences("ontology:\n  id: x") == "ontology:\n  id: x"

    def test_strips_yaml_fence(self) -> None:
        fenced = "```yaml\nontology:\n  id: x\n```"
        assert _strip_code_fences(fenced) == "ontology:\n  id: x"

    def test_strips_bare_fence(self) -> None:
        fenced = "```\nontology:\n  id: x\n```"
        assert _strip_code_fences(fenced) == "ontology:\n  id: x"

    def test_strips_missing_closing_fence(self) -> None:
        fenced = "```yaml\nontology:\n  id: x"
        assert _strip_code_fences(fenced) == "ontology:\n  id: x"


class TestOntologyToYaml:
    def test_roundtrip_minimal(self) -> None:
        ont = Ontology(
            ontology=OntologyHeader(id="rt-v1"),
            processes=[
                Process(
                    id="P",
                    name="P",
                    inputs=[IOPort(id="a", name="A", type=ValueType.FLOAT)],
                    outputs=[IOPort(id="b", name="B", type=ValueType.FLOAT)],
                    formula=Formula(expression="a + 1"),
                )
            ],
        )
        text = ontology_to_yaml(ont)
        assert "rt-v1" in text
        assert "a + 1" in text
        # Reloads back through validator
        assert validate_yaml_text(text) == []


class TestDraftOntologyYaml:
    @pytest.mark.asyncio
    async def test_empty_input(self) -> None:
        yaml_text, errors = await draft_ontology_yaml("   ")
        assert yaml_text == ""
        assert errors == ["markdown 입력이 비어 있습니다."]

    @pytest.mark.asyncio
    async def test_llm_returns_valid_yaml(self) -> None:
        fake_output = 'ontology:\n  id: heating-sop\n  version: "1.0"\n'
        with patch("backend.modeling.ontology.builder_service._build_agent") as mk:
            agent = mk.return_value
            agent.run = AsyncMock(return_value=type("R", (), {"output": fake_output})())
            yaml_text, errors = await draft_ontology_yaml("# 가열공정 SOP\n본문")
        assert errors == []
        assert "heating-sop" in yaml_text

    @pytest.mark.asyncio
    async def test_llm_returns_fenced_yaml(self) -> None:
        fenced = '```yaml\nontology:\n  id: crack-std\n  version: "1.0"\n```'
        with patch("backend.modeling.ontology.builder_service._build_agent") as mk:
            agent = mk.return_value
            agent.run = AsyncMock(return_value=type("R", (), {"output": fenced})())
            yaml_text, errors = await draft_ontology_yaml("doc")
        assert errors == []
        assert "crack-std" in yaml_text
        assert "```" not in yaml_text

    @pytest.mark.asyncio
    async def test_llm_exception_returns_error(self) -> None:
        with patch("backend.modeling.ontology.builder_service._build_agent") as mk:
            agent = mk.return_value
            agent.run = AsyncMock(side_effect=RuntimeError("boom"))
            yaml_text, errors = await draft_ontology_yaml("doc")
        assert yaml_text == ""
        assert errors
        assert any("LLM 호출 실패" in e for e in errors)

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_yaml_surfaces_errors(self) -> None:
        bad = "ontology:\n  id: test\nprocesses:\n  - name: missing-id\n"
        with patch("backend.modeling.ontology.builder_service._build_agent") as mk:
            agent = mk.return_value
            agent.run = AsyncMock(return_value=type("R", (), {"output": bad})())
            yaml_text, errors = await draft_ontology_yaml("doc")
        assert errors
        assert yaml_text == bad.strip()
