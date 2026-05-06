"""OD-11-E1-c (A2) — JavaParser field 추출 확장.

`field.attributes` 에 `field_type` / `initializer` / `initializer_kind` 가
들어가야 CONFLICTS_WITH gap 감지 (매직넘버 240/1.02/50 비교) 가 가능.

동기 : Slab Design Engine 검증에서 모든 field.attributes 가 비어 있던 사실 확인됨.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import EntityKinds


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
SAMPLE = """\
package com.example.demo;

import java.util.List;

public class FieldShowcase {
    private static final double WEIGHT_BIAS_FACTOR = 1.02;
    private static final int GRID_STEP_MM = 50;
    private double maxThicknessMm = 240.0;
    private String label = "slab";
    private boolean enabled = true;
    private Object cached = null;
    private double bias = -1.5;
    private char marker = 'A';
    private long limit = 1000L;
    private int hex = 0xFF;
    private int unset;
    private int computed = compute();
    private List<String> items;

    private static int compute() { return 1; }
}
"""


def _parse(text: str = SAMPLE):
    parser = JavaParser()
    return parser.parse_file(Path("FieldShowcase.java"), text)


def _field(result, name: str):
    for e in result.entities:
        if e.kind == EntityKinds.FIELD and e.name == name:
            return e
    pytest.fail(f"field {name!r} not found in entities")


# ---------------------------------------------------------------------------
# field_type 캡처
# ---------------------------------------------------------------------------
class TestFieldType:
    def test_primitive_double(self) -> None:
        f = _field(_parse(), "WEIGHT_BIAS_FACTOR")
        assert f.attributes.get("field_type") == "double"

    def test_primitive_int(self) -> None:
        f = _field(_parse(), "GRID_STEP_MM")
        assert f.attributes.get("field_type") == "int"

    def test_reference_string(self) -> None:
        f = _field(_parse(), "label")
        assert f.attributes.get("field_type") == "String"

    def test_generic_list(self) -> None:
        f = _field(_parse(), "items")
        # tree-sitter Java 의 generic_type text 를 그대로 보존
        assert f.attributes.get("field_type") == "List<String>"


# ---------------------------------------------------------------------------
# initializer 리터럴 캡처 (gap 감지의 핵심)
# ---------------------------------------------------------------------------
class TestInitializerLiteral:
    def test_floating_point(self) -> None:
        f = _field(_parse(), "WEIGHT_BIAS_FACTOR")
        assert f.attributes.get("initializer") == "1.02"
        assert f.attributes.get("initializer_kind") == "literal_number"

    def test_integer(self) -> None:
        f = _field(_parse(), "GRID_STEP_MM")
        assert f.attributes.get("initializer") == "50"
        assert f.attributes.get("initializer_kind") == "literal_number"

    def test_floating_point_explicit_zero(self) -> None:
        f = _field(_parse(), "maxThicknessMm")
        assert f.attributes.get("initializer") == "240.0"
        assert f.attributes.get("initializer_kind") == "literal_number"

    def test_string(self) -> None:
        f = _field(_parse(), "label")
        assert f.attributes.get("initializer") == '"slab"'
        assert f.attributes.get("initializer_kind") == "literal_string"

    def test_boolean(self) -> None:
        f = _field(_parse(), "enabled")
        assert f.attributes.get("initializer") == "true"
        assert f.attributes.get("initializer_kind") == "literal_boolean"

    def test_null(self) -> None:
        f = _field(_parse(), "cached")
        assert f.attributes.get("initializer") == "null"
        assert f.attributes.get("initializer_kind") == "literal_null"

    def test_negative_number(self) -> None:
        f = _field(_parse(), "bias")
        # 부호 포함 텍스트 보존
        assert f.attributes.get("initializer") == "-1.5"
        assert f.attributes.get("initializer_kind") == "literal_number"

    def test_character(self) -> None:
        f = _field(_parse(), "marker")
        assert f.attributes.get("initializer") == "'A'"
        assert f.attributes.get("initializer_kind") == "literal_char"

    def test_long_suffix(self) -> None:
        f = _field(_parse(), "limit")
        assert f.attributes.get("initializer") == "1000L"
        assert f.attributes.get("initializer_kind") == "literal_number"

    def test_hex_integer(self) -> None:
        f = _field(_parse(), "hex")
        assert f.attributes.get("initializer") == "0xFF"
        assert f.attributes.get("initializer_kind") == "literal_number"


# ---------------------------------------------------------------------------
# 비-리터럴 / 부재 케이스
# ---------------------------------------------------------------------------
class TestInitializerEdgeCases:
    def test_no_initializer(self) -> None:
        f = _field(_parse(), "unset")
        # initializer 키 자체가 없어야 함 (None 도 아님)
        assert "initializer" not in f.attributes
        assert "initializer_kind" not in f.attributes
        # 단, field_type 은 있어야 함
        assert f.attributes.get("field_type") == "int"

    def test_no_initializer_for_generic(self) -> None:
        f = _field(_parse(), "items")
        assert "initializer" not in f.attributes

    def test_expression_initializer_recorded_as_expression(self) -> None:
        f = _field(_parse(), "computed")
        # 표현식은 텍스트만 보존 + kind 로 구분
        assert f.attributes.get("initializer") == "compute()"
        assert f.attributes.get("initializer_kind") == "expression"


# ---------------------------------------------------------------------------
# Slab 샘플 실증 (CONFLICTS_WITH 의 입력 검증)
# ---------------------------------------------------------------------------
class TestSlabSampleLiterals:
    """실제 sample-repos/slab-design-engine 파일을 그대로 파싱."""

    def setup_method(self) -> None:
        self.parser = JavaParser()
        self.root = Path("sample-repos/slab-design-engine/src/main/java")

    def _parse(self, rel: str):
        path = self.root / rel
        if not path.exists():
            pytest.skip(f"slab sample missing: {rel}")
        return self.parser.parse_file(path, path.read_text())

    def test_weight_bias_factor_captured(self) -> None:
        res = self._parse("com/ontong/slab/optimizer/WeightMaximizer.java")
        f = _field(res, "WEIGHT_BIAS_FACTOR")
        assert f.attributes.get("initializer") == "1.02"

    def test_grid_step_mm_captured(self) -> None:
        res = self._parse("com/ontong/slab/optimizer/WeightMaximizer.java")
        f = _field(res, "GRID_STEP_MM")
        assert f.attributes.get("initializer") == "50.0"

    def test_max_thickness_mm_captured(self) -> None:
        res = self._parse("com/ontong/slab/config/EquipmentProperties.java")
        f = _field(res, "maxThicknessMm")
        assert f.attributes.get("initializer") == "240.0"
