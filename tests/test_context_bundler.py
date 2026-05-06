"""ContextBundler tests — 코드 위치 → 컨텍스트 번들 조립 검증.

특히 의미 없는 식별자 (`a1`) 가 클래스 컨텍스트로 풍부해지는지 확인.
"""

from __future__ import annotations

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKinds,
    ParseResult,
)
from backend.modeling.mapping.context_bundler import (
    CodeContextBundle,
    ContextBundler,
    candidate_queries_from_bundle,
)


def _cls(fqn: str, name: str, *, attributes: dict | None = None) -> CodeEntity:
    return CodeEntity(
        kind=EntityKinds.CLASS, qualified_name=fqn, name=name,
        file_path=f"{name}.java", line_start=1, line_end=10,
        parent=None, attributes=attributes or {},
    )


def _field(class_fqn: str, field_name: str, *, java_type: str | None = None) -> CodeEntity:
    attrs: dict = {}
    if java_type:
        attrs["java_type"] = java_type
    return CodeEntity(
        kind=EntityKinds.FIELD,
        qualified_name=f"{class_fqn}.{field_name}",
        name=field_name, file_path="x.java",
        line_start=2, line_end=2, parent=class_fqn, attributes=attrs,
    )


def _method(class_fqn: str, method_name: str) -> CodeEntity:
    return CodeEntity(
        kind=EntityKinds.METHOD,
        qualified_name=f"{class_fqn}.{method_name}",
        name=method_name, file_path="x.java",
        line_start=5, line_end=10, parent=class_fqn, attributes={},
    )


# ---------------------------------------------------------------------------
# Basic bundle assembly
# ---------------------------------------------------------------------------
class TestBundleAssembly:
    def test_field_in_class_yields_class_context(self) -> None:
        cls = _cls("com.x.HrSpecJpo", "HrSpecJpo")
        fld = _field("com.x.HrSpecJpo", "productTypeCd", java_type="String")
        pr = ParseResult(entities=[cls, fld], relations=[], file_path="x.java", language="Java")
        bundler = ContextBundler([pr])
        b = bundler.bundle("com.x.HrSpecJpo.productTypeCd")
        assert b is not None
        assert b.code_fqn == "com.x.HrSpecJpo.productTypeCd"
        assert b.name == "productTypeCd"
        assert "product" in b.name_tokens
        assert "type" in b.name_tokens
        assert b.enclosing_class_name == "HrSpecJpo"
        assert "hr" in b.enclosing_class_tokens
        assert b.type_hint == "String"

    def test_jpa_column_meta_detected(self) -> None:
        cls = _cls("com.x.HrSpecJpo", "HrSpecJpo", attributes={
            "jpa_columns_meta": {
                "productTypeCd": {"name": "PRODUCT_TYPE_CD", "type": "VARCHAR", "length": 4},
            },
        })
        fld = _field("com.x.HrSpecJpo", "productTypeCd")
        pr = ParseResult(entities=[cls, fld], relations=[], file_path="x.java", language="Java")
        b = ContextBundler([pr]).bundle("com.x.HrSpecJpo.productTypeCd")
        assert b is not None
        assert b.is_jpa_column is True
        assert b.type_hint == "VARCHAR"

    def test_sibling_fields_included(self) -> None:
        cls = _cls("com.x.HrSpecJpo", "HrSpecJpo")
        fields = [
            _field("com.x.HrSpecJpo", "productTypeCd"),
            _field("com.x.HrSpecJpo", "hrPlantCd"),
            _field("com.x.HrSpecJpo", "thicknessMm"),
        ]
        pr = ParseResult(entities=[cls, *fields], relations=[], file_path="x.java", language="Java")
        b = ContextBundler([pr]).bundle("com.x.HrSpecJpo.productTypeCd")
        assert b is not None
        assert "hrPlantCd" in b.sibling_field_names
        assert "thicknessMm" in b.sibling_field_names
        assert "productTypeCd" not in b.sibling_field_names

    def test_method_local_climbs_to_class(self) -> None:
        cls = _cls("com.x.HrCalc", "HrCalc")
        method = _method("com.x.HrCalc", "calculate")
        local = CodeEntity(
            kind=EntityKinds.FIELD,  # parser doesn't have LOCAL_VAR; field reused
            qualified_name="com.x.HrCalc.calculate.a1",
            name="a1", file_path="x.java",
            line_start=8, line_end=8, parent="com.x.HrCalc.calculate", attributes={},
        )
        pr = ParseResult(entities=[cls, method, local], relations=[], file_path="x.java", language="Java")
        b = ContextBundler([pr]).bundle("com.x.HrCalc.calculate.a1")
        assert b is not None
        assert b.enclosing_method_name == "calculate"
        assert b.enclosing_class_name == "HrCalc"

    def test_unknown_fqn_returns_synthetic_bundle(self) -> None:
        cls = _cls("com.x.A", "A")
        pr = ParseResult(entities=[cls], relations=[], file_path="x.java", language="Java")
        # synthetic — fqn 의 entity 가 없지만 parent class 는 있음
        b = ContextBundler([pr]).bundle("com.x.A.unknownField")
        assert b is not None
        assert b.name == "unknownField"
        assert b.enclosing_class_name == "A"

    def test_completely_unknown_returns_none(self) -> None:
        bundler = ContextBundler([])
        assert bundler.bundle("foo") is None  # FQN 에 dot 도 없음


# ---------------------------------------------------------------------------
# is_opaque heuristic
# ---------------------------------------------------------------------------
class TestOpaqueDetection:
    def test_a1_is_opaque(self) -> None:
        cls = _cls("com.x.A", "A")
        local = CodeEntity(
            kind=EntityKinds.FIELD, qualified_name="com.x.A.a1", name="a1",
            file_path="x.java", line_start=1, line_end=1, parent="com.x.A", attributes={},
        )
        pr = ParseResult(entities=[cls, local], relations=[], file_path="x.java", language="Java")
        b = ContextBundler([pr]).bundle("com.x.A.a1")
        assert b is not None and b.is_opaque() is True

    def test_product_type_cd_is_not_opaque(self) -> None:
        cls = _cls("com.x.A", "A")
        fld = _field("com.x.A", "productTypeCd")
        pr = ParseResult(entities=[cls, fld], relations=[], file_path="x.java", language="Java")
        b = ContextBundler([pr]).bundle("com.x.A.productTypeCd")
        assert b is not None and b.is_opaque() is False

    def test_single_letter_i_opaque(self) -> None:
        cls = _cls("com.x.A", "A")
        loc = CodeEntity(
            kind=EntityKinds.FIELD, qualified_name="com.x.A.i", name="i",
            file_path="x.java", line_start=1, line_end=1, parent="com.x.A", attributes={},
        )
        pr = ParseResult(entities=[cls, loc], relations=[], file_path="x.java", language="Java")
        b = ContextBundler([pr]).bundle("com.x.A.i")
        assert b is not None and b.is_opaque() is True


# ---------------------------------------------------------------------------
# Query generation from bundle
# ---------------------------------------------------------------------------
class TestQueryGeneration:
    def test_meaningful_name_yields_simple_queries(self) -> None:
        b = CodeContextBundle(
            code_fqn="com.x.A.productTypeCd", kind="field", name="productTypeCd",
            name_tokens=("product", "type", "cd"),
            enclosing_class_fqn="com.x.A", enclosing_class_name="A",
            enclosing_class_tokens=(),
            enclosing_method_fqn=None, enclosing_method_name=None,
        )
        queries = candidate_queries_from_bundle(b)
        assert "producttypecd" in queries
        assert "product type cd" in queries
        # suffix strip
        assert "product type" in queries

    def test_opaque_name_includes_class_context_query(self) -> None:
        b = CodeContextBundle(
            code_fqn="com.x.HrCalc.a1", kind="field", name="a1",
            name_tokens=("1",),
            enclosing_class_fqn="com.x.HrCalc", enclosing_class_name="HrCalc",
            enclosing_class_tokens=("hr", "calc"),
            enclosing_method_fqn=None, enclosing_method_name=None,
        )
        queries = candidate_queries_from_bundle(b)
        # opaque 이므로 class tokens + name tokens 합친 query 가 포함돼야 함
        joined = " ".join(["hr", "calc", "1"])
        assert joined in queries

    def test_meaningful_name_skips_class_join(self) -> None:
        b = CodeContextBundle(
            code_fqn="com.x.A.productTypeCd", kind="field", name="productTypeCd",
            name_tokens=("product", "type", "cd"),
            enclosing_class_fqn="com.x.A", enclosing_class_name="A",
            enclosing_class_tokens=("a",),
            enclosing_method_fqn=None, enclosing_method_name=None,
        )
        queries = candidate_queries_from_bundle(b)
        # 의미 있는 이름이면 클래스 합친 query 는 안 만듦 (노이즈 줄임)
        joined = "a product type cd"
        assert joined not in queries


# ---------------------------------------------------------------------------
# LLM prompt context
# ---------------------------------------------------------------------------
class TestLlmPrompt:
    def test_prompt_includes_class_method_type(self) -> None:
        b = CodeContextBundle(
            code_fqn="com.x.HrCalc.calculate.a1", kind="field", name="a1",
            name_tokens=("1",),
            enclosing_class_fqn="com.x.HrCalc", enclosing_class_name="HrCalc",
            enclosing_class_tokens=("hr", "calc"),
            enclosing_method_fqn="com.x.HrCalc.calculate", enclosing_method_name="calculate",
            sibling_field_names=("threshold", "ratio"),
            type_hint="int",
        )
        text = b.llm_prompt_context()
        assert "a1" in text
        assert "HrCalc" in text
        assert "calculate" in text
        assert "int" in text
        assert "threshold" in text
