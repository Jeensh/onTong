"""OD-11-E1-f — `ConfigPropertiesAnalyzer` (11번째 Spring analyzer).

`@ConfigurationProperties` 가 붙은 클래스의 instance field 를 모두 `config_property`
엔티티 + `has_config` 엣지 (class FQN → config_property FQN) 로 emit.

스펙:
- Annotation 형식 3 종 모두 지원 :
    @ConfigurationProperties(prefix = "slab.equipment")
    @ConfigurationProperties("slab.equipment")
    @ConfigurationProperties                              ← 마커 (prefix="")
- 비-`static` instance field 만 emit (final 은 허용 — 생성자 바인딩).
- canonical FQN = `{prefix}.{fieldName}` (camelCase, 코드에 선언된 그대로).
- `attributes` :
    prefix             : "slab.equipment"
    key                : "slab.equipment.maxThicknessMm"  (canonical)
    key_kebab          : "slab.equipment.max-thickness-mm" (Spring relaxed binding alias)
    field_name         : "maxThicknessMm"
    field_type         : "double" (선언 타입)
    default_value      : "240.0" (initializer literal text — 없으면 키 부재)
    bound_class_fqn    : "com.ontong.slab.config.EquipmentProperties"
    bound_field_fqn    : "{class_fqn}.{field_name}"
- Relation : `has_config` (이미 parser_protocol 에 등록).
- 어노테이션 없는 클래스 → 빈 결과.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.modeling.code_analysis.parser_protocol import (
    EntityKinds,
    RelationKinds,
)
from backend.modeling.code_analysis.spring import ConfigPropertiesAnalyzer

_LANG = Language(tsjava.language())


def _analyze(content: str, *, pkg_name: str | None = "com.x", file_path: str = "Demo.java"):
    parser = Parser(_LANG)
    tree = parser.parse(content.encode())
    analyzer = ConfigPropertiesAnalyzer()
    return analyzer.analyze(
        tree=tree,
        content=content.encode(),
        file_path=file_path,
        pkg_name=pkg_name,
    )


def _by_name(entities, fqn: str):
    for e in entities:
        if e.qualified_name == fqn:
            return e
    pytest.fail(f"config_property {fqn!r} not found; got {[e.qualified_name for e in entities]}")


# ---------------------------------------------------------------------------
# 어노테이션 형식 3 종
# ---------------------------------------------------------------------------
class TestAnnotationForms:
    def test_keyword_prefix_form(self) -> None:
        src = """\
package com.x;
@ConfigurationProperties(prefix = "slab.equipment")
public class P {
    private double maxThicknessMm = 240.0;
}
"""
        entities, edges = _analyze(src)
        assert len(entities) == 1
        e = entities[0]
        assert e.kind == EntityKinds.CONFIG_PROPERTY
        assert e.qualified_name == "slab.equipment.maxThicknessMm"
        assert e.attributes["prefix"] == "slab.equipment"

    def test_single_value_form(self) -> None:
        src = """\
package com.x;
@ConfigurationProperties("slab.equipment")
public class P {
    private int gridStepMm = 50;
}
"""
        entities, _ = _analyze(src)
        assert len(entities) == 1
        assert entities[0].qualified_name == "slab.equipment.gridStepMm"
        assert entities[0].attributes["prefix"] == "slab.equipment"

    def test_marker_form_no_prefix(self) -> None:
        src = """\
package com.x;
@ConfigurationProperties
public class P {
    private int port = 8080;
}
"""
        entities, _ = _analyze(src)
        assert len(entities) == 1
        # 빈 prefix 면 FQN = 그냥 fieldName
        assert entities[0].qualified_name == "port"
        assert entities[0].attributes["prefix"] == ""

    def test_no_annotation_yields_nothing(self) -> None:
        src = """\
package com.x;
public class Plain {
    private double thickness = 240.0;
}
"""
        entities, edges = _analyze(src)
        assert entities == []
        assert edges == []

    def test_other_annotation_yields_nothing(self) -> None:
        src = """\
package com.x;
@Component
public class NotConfig {
    private double x = 1.0;
}
"""
        entities, _ = _analyze(src)
        assert entities == []


# ---------------------------------------------------------------------------
# 다중 field, 정적 field skip
# ---------------------------------------------------------------------------
class TestFieldSelection:
    SRC = """\
package com.x;
@ConfigurationProperties(prefix = "app")
public class A {
    private double a = 1.0;
    private int b = 2;
    private static final String CONST = "x";   // skip
    private final double c = 3.0;              // 허용 (생성자 바인딩 가능)
    private double d;                          // default 없음
}
"""

    def test_emits_one_per_instance_field(self) -> None:
        entities, _ = _analyze(self.SRC)
        names = {e.attributes["field_name"] for e in entities}
        # static 만 제외
        assert names == {"a", "b", "c", "d"}

    def test_static_field_is_skipped(self) -> None:
        entities, _ = _analyze(self.SRC)
        for e in entities:
            assert e.attributes["field_name"] != "CONST"

    def test_final_field_is_kept(self) -> None:
        entities, _ = _analyze(self.SRC)
        c = _by_name(entities, "app.c")
        assert "final" in c.modifiers

    def test_field_without_default_lacks_default_key(self) -> None:
        entities, _ = _analyze(self.SRC)
        d = _by_name(entities, "app.d")
        assert "default_value" not in d.attributes


# ---------------------------------------------------------------------------
# attributes 상세
# ---------------------------------------------------------------------------
class TestAttributes:
    SRC = """\
package com.x;
@ConfigurationProperties(prefix = "slab.equipment")
public class P {
    private double maxThicknessMm = 240.0;
}
"""

    def test_canonical_key_camel_case(self) -> None:
        entities, _ = _analyze(self.SRC)
        e = entities[0]
        assert e.attributes["key"] == "slab.equipment.maxThicknessMm"

    def test_kebab_alias_for_relaxed_binding(self) -> None:
        entities, _ = _analyze(self.SRC)
        e = entities[0]
        assert e.attributes["key_kebab"] == "slab.equipment.max-thickness-mm"

    def test_field_type_recorded(self) -> None:
        entities, _ = _analyze(self.SRC)
        e = entities[0]
        assert e.attributes["field_type"] == "double"

    def test_default_value_recorded(self) -> None:
        entities, _ = _analyze(self.SRC)
        e = entities[0]
        assert e.attributes["default_value"] == "240.0"

    def test_bound_class_and_field_fqn(self) -> None:
        entities, _ = _analyze(self.SRC)
        e = entities[0]
        assert e.attributes["bound_class_fqn"] == "com.x.P"
        assert e.attributes["bound_field_fqn"] == "com.x.P.maxThicknessMm"

    def test_field_name_recorded(self) -> None:
        entities, _ = _analyze(self.SRC)
        e = entities[0]
        assert e.attributes["field_name"] == "maxThicknessMm"


# ---------------------------------------------------------------------------
# has_config 엣지
# ---------------------------------------------------------------------------
class TestHasConfigEdge:
    SRC = """\
package com.x;
@ConfigurationProperties(prefix = "app")
public class A {
    private int a = 1;
    private int b = 2;
}
"""

    def test_one_edge_per_field(self) -> None:
        _, edges = _analyze(self.SRC)
        assert len(edges) == 2

    def test_edge_kind_is_has_config(self) -> None:
        _, edges = _analyze(self.SRC)
        assert all(e.kind == RelationKinds.HAS_CONFIG for e in edges)

    def test_edge_source_is_class_fqn(self) -> None:
        _, edges = _analyze(self.SRC)
        sources = {e.source for e in edges}
        assert sources == {"com.x.A"}

    def test_edge_targets_match_config_property_fqns(self) -> None:
        entities, edges = _analyze(self.SRC)
        edge_targets = {e.target for e in edges}
        entity_fqns = {e.qualified_name for e in entities}
        assert edge_targets == entity_fqns


# ---------------------------------------------------------------------------
# kebab-case 변환 corner cases
# ---------------------------------------------------------------------------
class TestKebabCaseEdgeCases:
    def test_consecutive_capitals_are_split(self) -> None:
        # rollingMillMaxWidthMm → rolling-mill-max-width-mm
        src = """\
package com.x;
@ConfigurationProperties(prefix = "slab.equipment")
public class P {
    private double rollingMillMaxWidthMm = 2400.0;
}
"""
        entities, _ = _analyze(src)
        e = entities[0]
        assert e.attributes["key_kebab"] == "slab.equipment.rolling-mill-max-width-mm"

    def test_single_word_field(self) -> None:
        src = """\
package com.x;
@ConfigurationProperties(prefix = "app")
public class P {
    private int port = 8080;
}
"""
        entities, _ = _analyze(src)
        assert entities[0].attributes["key_kebab"] == "app.port"


# ---------------------------------------------------------------------------
# Slab 실증
# ---------------------------------------------------------------------------
class TestSlabSample:
    def setup_method(self) -> None:
        self.path = Path(
            "sample-repos/slab-design-engine/src/main/java/"
            "com/ontong/slab/config/EquipmentProperties.java"
        )

    def test_emits_five_config_properties(self) -> None:
        if not self.path.exists():
            pytest.skip("slab sample missing")
        text = self.path.read_text()
        entities, edges = _analyze(text, pkg_name="com.ontong.slab.config", file_path=str(self.path))
        # EquipmentProperties 5 instance fields → 5 config_property
        assert len(entities) == 5
        assert len(edges) == 5

    def test_max_thickness_mm_default_240(self) -> None:
        if not self.path.exists():
            pytest.skip("slab sample missing")
        text = self.path.read_text()
        entities, _ = _analyze(text, pkg_name="com.ontong.slab.config", file_path=str(self.path))
        e = _by_name(entities, "slab.equipment.maxThicknessMm")
        assert e.attributes["default_value"] == "240.0"
        assert e.attributes["field_type"] == "double"
        assert e.attributes["key_kebab"] == "slab.equipment.max-thickness-mm"

    def test_all_five_keys_present(self) -> None:
        if not self.path.exists():
            pytest.skip("slab sample missing")
        text = self.path.read_text()
        entities, _ = _analyze(text, pkg_name="com.ontong.slab.config", file_path=str(self.path))
        keys = {e.attributes["key"] for e in entities}
        assert keys == {
            "slab.equipment.rollingMillMaxWidthMm",
            "slab.equipment.furnaceMaxLengthMm",
            "slab.equipment.craneMaxLoadKg",
            "slab.equipment.minThicknessMm",
            "slab.equipment.maxThicknessMm",
        }

    def test_edge_source_is_equipment_properties_fqn(self) -> None:
        if not self.path.exists():
            pytest.skip("slab sample missing")
        text = self.path.read_text()
        _, edges = _analyze(text, pkg_name="com.ontong.slab.config", file_path=str(self.path))
        assert all(
            e.source == "com.ontong.slab.config.EquipmentProperties" for e in edges
        )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
class TestProtocol:
    def test_conforms_to_spring_analyzer(self) -> None:
        from backend.modeling.code_analysis.spring import SpringAnalyzer
        assert isinstance(ConfigPropertiesAnalyzer(), SpringAnalyzer)

    def test_empty_tree_yields_nothing(self) -> None:
        analyzer = ConfigPropertiesAnalyzer()
        entities, edges = analyzer.analyze(
            tree=None,
            content=b"",
            file_path="empty.java",
            pkg_name=None,
        )
        assert entities == []
        assert edges == []
