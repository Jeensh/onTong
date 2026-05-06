"""OD-11-B6-1 : Spring MapStructAnalyzer — `@Mapper` + `@Mapping` → PROPAGATES_TO / DERIVES_FROM.

감지 대상:
  - `@Mapper` 또는 `@Mapper(componentModel=...)` 가 붙은 interface / abstract class
  - `@Mapping(source, target)` → FIELD→FIELD `PROPAGATES_TO` (confidence=1.0)
  - `@Mapping(expression = "java(...)", target)` → `DERIVES_FROM` (expression 속성)
  - `@Mapping(target, ignore = true)` → 엣지 미생성
  - `@Mappings({@Mapping(...), @Mapping(...)})` 컨테이너 → 여러 엣지
  - `@Mapping(source, target, qualifiedByName = "name")` → `via_methods` 에 qualifier 포함
  - `default` 메서드 / `@Named` 메서드 → skip (매퍼 helper)

출력 규약:
  - source / target FQN : 메서드 파라미터/반환 타입을 import 맵으로 해소.
    `@Mapping.source` 의 첫 토큰이 파라미터 이름이면 타입 FQN 으로 replace.
  - `via_methods` : [mapper_fqn.method_name], `mapper_fqn` 속성도 별도 보존.
  - implicit mapping (명시 @Mapping 없는 필드) 은 B6-1 에서는 METHOD.attributes["mapstruct_implicit_fields"] marker 만 남긴다 — B6-4 에서 확정.

설계:
  - `analyze()` 가 entity/relation 을 직접 emit (standalone, B5-6 의 enrich 패턴 아님).
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import EntityKinds, RelationKinds
from backend.modeling.code_analysis.spring import MapStructAnalyzer

_LANG = Language(tsjava.language())


def _parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


def _rels(result, kind: str) -> list:
    return [r for r in result.relations if r.kind == kind]


def _method_entity(result, method_name: str):
    for e in result.entities:
        if e.kind == EntityKinds.METHOD and e.qualified_name.endswith(f".{method_name}"):
            return e
    return None


# ---------------------------------------------------------------------------
# 1. Standalone analyze() — no @Mapper → no output
# ---------------------------------------------------------------------------
def test_non_mapper_class_yields_no_edges() -> None:
    src = """
package com.x.mapper;
public class PlainClass {
    public OrderDto toDto(OrderReq src) { return null; }
}
"""
    tree = _parse(src)
    a = MapStructAnalyzer()
    entities, relations = a.analyze(
        tree=tree, content=src.encode(), file_path="PlainClass.java", pkg_name="com.x.mapper",
    )
    assert entities == []
    assert relations == []


# ---------------------------------------------------------------------------
# 2. @Mapper empty interface → no entity/relation
# ---------------------------------------------------------------------------
def test_empty_mapper_interface_yields_no_edges() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
@Mapper
public interface OrderMapper { }
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    assert _rels(result, RelationKinds.PROPAGATES_TO) == []
    assert _rels(result, RelationKinds.DERIVES_FROM) == []


# ---------------------------------------------------------------------------
# 3. @Mapping(source, target) → PROPAGATES_TO
# ---------------------------------------------------------------------------
def test_mapping_source_target_emits_propagates_to() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public interface OrderMapper {
    @Mapping(source = "productCode", target = "productId")
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    assert len(props) == 1
    rel = props[0]
    assert rel.source == "com.x.model.OrderReq.productCode"
    assert rel.target == "com.x.dto.OrderDto.productId"
    assert rel.attributes["confidence"] == 1.0
    assert rel.attributes["mapper_fqn"] == "com.x.mapper.OrderMapper"
    assert rel.attributes["via_methods"] == ["com.x.mapper.OrderMapper.toDto"]


# ---------------------------------------------------------------------------
# 4. @Mapping(expression) → DERIVES_FROM
# ---------------------------------------------------------------------------
def test_mapping_expression_emits_derives_from() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public interface OrderMapper {
    @Mapping(expression = "java(src.amount() * 1.1)", target = "totalWithTax")
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    derives = _rels(result, RelationKinds.DERIVES_FROM)
    assert len(derives) == 1
    rel = derives[0]
    assert rel.target == "com.x.dto.OrderDto.totalWithTax"
    assert rel.attributes["expression"] == "java(src.amount() * 1.1)"
    assert rel.attributes["confidence"] == 1.0
    assert rel.attributes["via_methods"] == ["com.x.mapper.OrderMapper.toDto"]
    # expression-only => source 는 <expression> 가상 노드 (B6-4 에서 해소)
    assert rel.source == "<expression>"


# ---------------------------------------------------------------------------
# 5. @Mapping(source="nested.path", target)
# ---------------------------------------------------------------------------
def test_mapping_dotted_source_path_preserved() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public interface OrderMapper {
    @Mapping(source = "item.id", target = "productId")
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    assert len(props) == 1
    assert props[0].source == "com.x.model.OrderReq.item.id"


# ---------------------------------------------------------------------------
# 6. @Mapping.source 가 파라미터 prefix 로 시작하면 replace
# ---------------------------------------------------------------------------
def test_mapping_source_param_prefix_replaced_with_type_fqn() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public interface OrderMapper {
    @Mapping(source = "src.item.id", target = "productId")
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    assert len(props) == 1
    assert props[0].source == "com.x.model.OrderReq.item.id"


# ---------------------------------------------------------------------------
# 7. @Mapping(ignore=true) → skip
# ---------------------------------------------------------------------------
def test_mapping_ignore_true_skipped() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public interface OrderMapper {
    @Mapping(target = "productId", ignore = true)
    @Mapping(source = "total", target = "total")
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    assert len(props) == 1
    assert props[0].target == "com.x.dto.OrderDto.total"


# ---------------------------------------------------------------------------
# 8. @Mappings container → 여러 엣지
# ---------------------------------------------------------------------------
def test_mappings_container_emits_multiple_edges() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.Mappings;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public interface OrderMapper {
    @Mappings({
        @Mapping(source = "a", target = "x"),
        @Mapping(source = "b", target = "y")
    })
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    targets = sorted(r.target for r in props)
    assert targets == ["com.x.dto.OrderDto.x", "com.x.dto.OrderDto.y"]


# ---------------------------------------------------------------------------
# 9. @Mapping(qualifiedByName) → via_methods 에 qualifier 포함
# ---------------------------------------------------------------------------
def test_mapping_qualified_by_name_appends_qualifier_in_via_methods() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public interface OrderMapper {
    @Mapping(source = "amount", target = "totalWithTax", qualifiedByName = "addTax")
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    assert len(props) == 1
    via = props[0].attributes["via_methods"]
    assert "com.x.mapper.OrderMapper.toDto" in via
    # qualifier 는 별도 element 로 추가
    assert "addTax" in via


# ---------------------------------------------------------------------------
# 10. 여러 매핑 메서드 → scope 격리
# ---------------------------------------------------------------------------
def test_multiple_mapping_methods_isolated_scopes() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;
import com.x.model.UserReq;
import com.x.dto.UserDto;

@Mapper
public interface MultiMapper {
    @Mapping(source = "total", target = "total")
    OrderDto toOrderDto(OrderReq src);

    @Mapping(source = "name", target = "fullName")
    UserDto toUserDto(UserReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("MultiMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    by_target = {r.target: r for r in props}
    assert "com.x.dto.OrderDto.total" in by_target
    assert "com.x.dto.UserDto.fullName" in by_target
    assert by_target["com.x.dto.OrderDto.total"].source == "com.x.model.OrderReq.total"
    assert by_target["com.x.dto.UserDto.fullName"].source == "com.x.model.UserReq.name"


# ---------------------------------------------------------------------------
# 11. default method skip
# ---------------------------------------------------------------------------
def test_default_method_skipped() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public interface OrderMapper {
    default String helper(String s) { return s.toUpperCase(); }

    @Mapping(source = "total", target = "total")
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    # default 메서드는 via_methods 에 안 잡혀야 한다
    assert all("helper" not in r.attributes["via_methods"] for r in props)
    assert len(props) == 1


# ---------------------------------------------------------------------------
# 12. @Named method skip
# ---------------------------------------------------------------------------
def test_named_method_skipped() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.Named;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public interface OrderMapper {
    @Named("taxCalc")
    BigDecimal applyTax(BigDecimal amount);

    @Mapping(source = "amount", target = "total", qualifiedByName = "taxCalc")
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    # @Named helper 는 자체적으로 엣지 만들면 안 된다
    assert len(props) == 1
    via = props[0].attributes["via_methods"]
    assert "com.x.mapper.OrderMapper.toDto" in via


# ---------------------------------------------------------------------------
# 13. implicit same-name marker on method (no explicit @Mapping)
# ---------------------------------------------------------------------------
def test_implicit_marker_when_no_explicit_mapping() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public interface OrderMapper {
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    method = _method_entity(result, "toDto")
    assert method is not None
    markers = method.attributes.get("mapstruct_implicit_fields")
    assert isinstance(markers, list)
    assert len(markers) == 1
    m = markers[0]
    assert m["src_type"] == "com.x.model.OrderReq"
    assert m["dst_type"] == "com.x.dto.OrderDto"
    assert m["mapper_fqn"] == "com.x.mapper.OrderMapper"
    # B6-1 은 implicit 엣지를 직접 만들지 않는다
    assert _rels(result, RelationKinds.PROPAGATES_TO) == []


# ---------------------------------------------------------------------------
# 14. @Mapper(componentModel="spring") 도 감지
# ---------------------------------------------------------------------------
def test_mapper_with_component_model_attribute_detected() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper(componentModel = "spring")
public interface OrderMapper {
    @Mapping(source = "total", target = "total")
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    assert len(props) == 1
    assert props[0].attributes["mapper_fqn"] == "com.x.mapper.OrderMapper"


# ---------------------------------------------------------------------------
# 15. abstract class 에 @Mapper → 감지
# ---------------------------------------------------------------------------
def test_abstract_class_mapper_detected() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import com.x.model.OrderReq;
import com.x.dto.OrderDto;

@Mapper
public abstract class AbstractOrderMapper {
    @Mapping(source = "total", target = "total")
    public abstract OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("AbstractOrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    assert len(props) == 1
    assert props[0].attributes["mapper_fqn"] == "com.x.mapper.AbstractOrderMapper"


# ---------------------------------------------------------------------------
# 16. 빈 import 맵 → unqualified fallback
# ---------------------------------------------------------------------------
def test_unresolved_types_fall_back_to_simple_names() -> None:
    src = """
package com.x.mapper;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper
public interface OrderMapper {
    @Mapping(source = "total", target = "total")
    OrderDto toDto(OrderReq src);
}
"""
    parser = JavaParser(spring_analyzers=[MapStructAnalyzer()])
    result = parser.parse_file(Path("OrderMapper.java"), src)
    props = _rels(result, RelationKinds.PROPAGATES_TO)
    assert len(props) == 1
    assert props[0].source == "OrderReq.total"
    assert props[0].target == "OrderDto.total"
