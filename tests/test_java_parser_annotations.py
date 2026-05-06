"""P0.1 — JavaParser annotation capture.

`attributes["annotations"] = [{name, arguments}]` for class / method / field
declarations. JpaAnnotationExtractor / future analyzers depend on this.

샘플 데모 코드 (HrSpecJpo) :
    @Entity                                                 → marker
    @Table(name = "HR_SPEC")                                → keyword
    @IdClass(HrSpecPK.class)                                → single value (class_literal)
    @Id @Column(name = "CMP_CD", length = 2)               → 다중 어노테이션 + keyword
    @Column(name = "WIDTH_LOW", precision = 10, scale = 2) → 다중 keyword
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import EntityKinds


def _parse(content: str, file_path: str = "Demo.java"):
    return JavaParser().parse_file(Path(file_path), content)


def _by_kind_name(result, kind: str, name: str):
    for e in result.entities:
        if e.kind == kind and e.name == name:
            return e
    pytest.fail(f"{kind} {name!r} not found")


def _annotations_of(entity) -> list[dict]:
    return entity.attributes.get("annotations", []) or []


def _by_anno_name(annos: list[dict], name: str) -> dict:
    for a in annos:
        if a.get("name") == name:
            return a
    pytest.fail(f"annotation @{name} not found in {[a.get('name') for a in annos]}")


# ---------------------------------------------------------------------------
# Class-level annotations
# ---------------------------------------------------------------------------
class TestClassAnnotations:
    def test_marker_annotation(self) -> None:
        src = """\
package com.x;
@Entity
public class A {}
"""
        cls = _by_kind_name(_parse(src), EntityKinds.CLASS, "A")
        annos = _annotations_of(cls)
        entity = _by_anno_name(annos, "Entity")
        assert entity.get("arguments") == {}

    def test_keyword_annotation(self) -> None:
        src = """\
package com.x;
@Table(name = "HR_SPEC")
public class A {}
"""
        cls = _by_kind_name(_parse(src), EntityKinds.CLASS, "A")
        anno = _by_anno_name(_annotations_of(cls), "Table")
        assert anno["arguments"] == {"name": "HR_SPEC"}

    def test_single_value_annotation(self) -> None:
        # @Table("X") 단일 string value form (= name 으로 해석)
        src = """\
package com.x;
@Table("HR_SPEC")
public class A {}
"""
        cls = _by_kind_name(_parse(src), EntityKinds.CLASS, "A")
        anno = _by_anno_name(_annotations_of(cls), "Table")
        # 단일 value 는 "value" 키 또는 별도 키로 — 표준 컨벤션은 "value"
        assert anno["arguments"] == {"value": "HR_SPEC"}

    def test_class_literal_annotation(self) -> None:
        # @IdClass(HrSpecPK.class) — class_literal 값 보존
        src = """\
package com.x;
@IdClass(HrSpecPK.class)
public class A {}
"""
        cls = _by_kind_name(_parse(src), EntityKinds.CLASS, "A")
        anno = _by_anno_name(_annotations_of(cls), "IdClass")
        # class_literal text 그대로 보존
        assert anno["arguments"] == {"value": "HrSpecPK.class"}

    def test_multiple_class_annotations(self) -> None:
        src = """\
package com.x;
@Entity
@Table(name = "HR_SPEC")
@IdClass(HrSpecPK.class)
public class A {}
"""
        cls = _by_kind_name(_parse(src), EntityKinds.CLASS, "A")
        annos = _annotations_of(cls)
        names = [a["name"] for a in annos]
        assert names == ["Entity", "Table", "IdClass"]

    def test_no_annotations_yields_empty_or_absent(self) -> None:
        src = """\
package com.x;
public class A {}
"""
        cls = _by_kind_name(_parse(src), EntityKinds.CLASS, "A")
        # 없으면 빈 list 또는 키 부재
        assert _annotations_of(cls) == []


# ---------------------------------------------------------------------------
# Field-level annotations
# ---------------------------------------------------------------------------
class TestFieldAnnotations:
    SRC = """\
package com.x;
public class A {
    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Column(name = "WIDTH_LOW", precision = 10, scale = 2)
    private java.math.BigDecimal widthLow;

    @Column(name = "ENABLED", nullable = false)
    private Boolean enabled;
}
"""

    def test_field_with_id_and_column(self) -> None:
        f = _by_kind_name(_parse(self.SRC), EntityKinds.FIELD, "cmpCd")
        annos = _annotations_of(f)
        names = {a["name"] for a in annos}
        assert names == {"Id", "Column"}
        col = _by_anno_name(annos, "Column")
        assert col["arguments"] == {"name": "CMP_CD", "length": 2}

    def test_field_with_precision_scale(self) -> None:
        f = _by_kind_name(_parse(self.SRC), EntityKinds.FIELD, "widthLow")
        col = _by_anno_name(_annotations_of(f), "Column")
        assert col["arguments"] == {"name": "WIDTH_LOW", "precision": 10, "scale": 2}

    def test_field_with_boolean_arg(self) -> None:
        f = _by_kind_name(_parse(self.SRC), EntityKinds.FIELD, "enabled")
        col = _by_anno_name(_annotations_of(f), "Column")
        assert col["arguments"] == {"name": "ENABLED", "nullable": False}


# ---------------------------------------------------------------------------
# Method-level annotations
# ---------------------------------------------------------------------------
class TestMethodAnnotations:
    def test_method_marker_annotation(self) -> None:
        src = """\
package com.x;
public class A {
    @Override
    public String toString() { return ""; }
}
"""
        m = _by_kind_name(_parse(src), EntityKinds.METHOD, "toString")
        annos = _annotations_of(m)
        names = [a["name"] for a in annos]
        assert "Override" in names

    def test_method_keyword_annotation(self) -> None:
        src = """\
package com.x;
public class A {
    @GetMapping(value = "/orders", produces = "application/json")
    public String list() { return "[]"; }
}
"""
        m = _by_kind_name(_parse(src), EntityKinds.METHOD, "list")
        anno = _by_anno_name(_annotations_of(m), "GetMapping")
        assert anno["arguments"] == {"value": "/orders", "produces": "application/json"}


# ---------------------------------------------------------------------------
# Slab demo 실증 — HrSpecJpo
# ---------------------------------------------------------------------------
class TestSlabDemoExtraction:
    def setup_method(self) -> None:
        self.path = Path(
            "sample-repos/slab-design-real/slab-design-store/src/main/java/"
            "com/example/slabdesign/store/sd/std/oracle/jpo/HrSpecJpo.java"
        )

    def test_class_has_entity_table_idclass(self) -> None:
        if not self.path.exists():
            pytest.skip("Slab demo missing")
        result = _parse(self.path.read_text(), str(self.path))
        cls = _by_kind_name(result, EntityKinds.CLASS, "HrSpecJpo")
        names = {a["name"] for a in _annotations_of(cls)}
        assert {"Entity", "Table", "IdClass"} <= names
        table = _by_anno_name(_annotations_of(cls), "Table")
        assert table["arguments"]["name"] == "HR_SPEC"

    def test_field_product_type_cd_has_length_4(self) -> None:
        # 시나리오 1 의 핵심 데이터 — VARCHAR2(4)
        if not self.path.exists():
            pytest.skip("Slab demo missing")
        result = _parse(self.path.read_text(), str(self.path))
        f = _by_kind_name(result, EntityKinds.FIELD, "productTypeCd")
        col = _by_anno_name(_annotations_of(f), "Column")
        assert col["arguments"]["name"] == "PRODUCT_TYPE_CD"
        assert col["arguments"]["length"] == 4

    def test_field_width_low_has_precision_scale(self) -> None:
        if not self.path.exists():
            pytest.skip("Slab demo missing")
        result = _parse(self.path.read_text(), str(self.path))
        f = _by_kind_name(result, EntityKinds.FIELD, "widthLow")
        col = _by_anno_name(_annotations_of(f), "Column")
        assert col["arguments"]["name"] == "WIDTH_LOW"
        assert col["arguments"]["precision"] == 10
        assert col["arguments"]["scale"] == 2
