"""OD-11-B5-7 — Spring `JpaAnalyzer` (12번째 Spring analyzer).

Spring Data JPA Repository interface 의 메서드를 `READS_TABLE` / `WRITES_TABLE`
엣지 + method attribute marker 로 변환. 데모 코드 (Slab 후속) 가 JPA 사용 예정.

스펙
----
탐지 대상 :
    - `@Repository` 가 붙은 interface, 또는
    - 4 base interface 중 하나를 extends 하는 interface :
        Repository / CrudRepository / PagingAndSortingRepository / JpaRepository
      (Spring Data 의 표준 base. 첫 generic type 파라미터 = entity simple name.)

메서드 이름 컨벤션 :
    find* / get* / query* / read* / search*  By*  → READS  (`jpa_operation="find"`)
    exists* By*                                   → READS  (`"exists"`)
    count*  By*                                   → READS  (`"count"`)
    delete* / remove* By*                         → WRITES (`"delete"`)
    save / saveAll / saveAndFlush  (정확히)        → WRITES (`"save"`)
    그 외                                         → marker only, edge 없음

Target table = entity simple name (e.g. `User`). 추후 CrossFileEnricher 가
`@Table(name="...")` 으로 rewrite — 본 analyzer 는 simple name 만.
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
from backend.modeling.code_analysis.spring import JpaAnalyzer

_LANG = Language(tsjava.language())


def _analyze(content: str, *, pkg_name: str | None = "com.x", file_path: str = "X.java"):
    parser = Parser(_LANG)
    tree = parser.parse(content.encode())
    return JpaAnalyzer().analyze(
        tree=tree, content=content.encode(),
        file_path=file_path, pkg_name=pkg_name,
    )


# ---------------------------------------------------------------------------
# 탐지
# ---------------------------------------------------------------------------
class TestDetection:
    def test_jpa_repository_extends_detected(self) -> None:
        src = """\
package com.x;
public interface UserRepository extends JpaRepository<User, Long> {
    User findByEmail(String email);
}
"""
        _, edges = _analyze(src)
        assert len(edges) == 1
        assert edges[0].kind == RelationKinds.READS_TABLE
        assert edges[0].source == "com.x.UserRepository.findByEmail"
        assert edges[0].target == "User"

    def test_crud_repository_extends_detected(self) -> None:
        src = """\
package com.x;
public interface ProductRepository extends CrudRepository<Product, Integer> {
    Product findByName(String name);
}
"""
        _, edges = _analyze(src)
        assert len(edges) == 1
        assert edges[0].target == "Product"

    def test_paging_repository_extends_detected(self) -> None:
        src = """\
package com.x;
public interface OrderRepository extends PagingAndSortingRepository<Order, Long> {
    Order findByOrderNo(String no);
}
"""
        _, edges = _analyze(src)
        assert len(edges) == 1
        assert edges[0].target == "Order"

    def test_repository_annotation_detected(self) -> None:
        # @Repository 만 붙어있고 base interface 안 extends — 탐지하되 entity 못 찾음.
        src = """\
package com.x;
@Repository
public interface CustomRepository {
    void doSomething();
}
"""
        # entity 미식별 → edge 없음, 단 marker 는 추후 가능 (현재 spec : edge 없으면 빈 결과 OK).
        entities, edges = _analyze(src)
        assert edges == []

    def test_plain_interface_yields_nothing(self) -> None:
        src = """\
package com.x;
public interface NotAJpaRepo {
    User findByEmail(String email);
}
"""
        entities, edges = _analyze(src)
        assert entities == []
        assert edges == []


# ---------------------------------------------------------------------------
# 메서드 이름 컨벤션
# ---------------------------------------------------------------------------
class TestMethodNameOperations:
    @pytest.mark.parametrize("name,op,kind", [
        ("findByEmail",          "find",   RelationKinds.READS_TABLE),
        ("findAllByActive",      "find",   RelationKinds.READS_TABLE),
        ("getByCode",            "find",   RelationKinds.READS_TABLE),
        ("queryByStatus",        "find",   RelationKinds.READS_TABLE),
        ("readByName",           "find",   RelationKinds.READS_TABLE),
        ("searchByKeyword",      "find",   RelationKinds.READS_TABLE),
        ("existsByEmail",        "exists", RelationKinds.READS_TABLE),
        ("countByStatus",        "count",  RelationKinds.READS_TABLE),
        ("deleteByEmail",        "delete", RelationKinds.WRITES_TABLE),
        ("removeByName",         "delete", RelationKinds.WRITES_TABLE),
    ])
    def test_method_name_dispatches_correctly(self, name, op, kind) -> None:
        src = f"""\
package com.x;
public interface R extends JpaRepository<E, Long> {{
    Object {name}(Object arg);
}}
"""
        _, edges = _analyze(src)
        assert len(edges) == 1
        assert edges[0].kind == kind

    @pytest.mark.parametrize("name", ["save", "saveAll", "saveAndFlush"])
    def test_save_methods_are_writes(self, name) -> None:
        src = f"""\
package com.x;
public interface R extends JpaRepository<E, Long> {{
    Object {name}(Object e);
}}
"""
        _, edges = _analyze(src)
        assert len(edges) == 1
        assert edges[0].kind == RelationKinds.WRITES_TABLE
        assert edges[0].target == "E"

    def test_unknown_method_name_yields_no_edge(self) -> None:
        # `customComputeStuff` 는 컨벤션 외 — query 메서드일지 모르지만 edge 안 잡음.
        src = """\
package com.x;
public interface R extends JpaRepository<E, Long> {
    void customComputeStuff(int x);
}
"""
        _, edges = _analyze(src)
        assert edges == []


# ---------------------------------------------------------------------------
# attributes — method marker
# ---------------------------------------------------------------------------
class TestMethodAttributes:
    """JpaAnalyzer 는 method entity 를 직접 emit 하지 않음 (JavaParser 가 이미 함).
    대신 method 의 attribute marker 를 위한 별도 channel — 본 PoC 에서는
    `attributes["jpa_operation"]` 을 EDGE 의 attributes 에 넣어 추적.
    """

    def test_edge_attributes_carry_jpa_operation(self) -> None:
        src = """\
package com.x;
public interface UserRepository extends JpaRepository<User, Long> {
    User findByEmail(String email);
}
"""
        _, edges = _analyze(src)
        assert edges[0].attributes.get("jpa_operation") == "find"

    def test_edge_attributes_carry_property_path(self) -> None:
        src = """\
package com.x;
public interface R extends JpaRepository<E, Long> {
    E findByEmailAndStatus(String email, String status);
}
"""
        _, edges = _analyze(src)
        # property path : findBy 뒤에 "EmailAndStatus" → ["email", "status"] (소문자 시작)
        path = edges[0].attributes.get("jpa_property_path")
        assert path == ["email", "status"]

    def test_save_edge_has_no_property_path(self) -> None:
        src = """\
package com.x;
public interface R extends JpaRepository<E, Long> {
    E save(E entity);
}
"""
        _, edges = _analyze(src)
        # save 메서드는 By 가 없으므로 property_path 부재 (또는 빈 리스트).
        path = edges[0].attributes.get("jpa_property_path", [])
        assert path == []


# ---------------------------------------------------------------------------
# 다중 메서드 한 interface 안
# ---------------------------------------------------------------------------
class TestMultipleMethods:
    def test_multiple_methods_emit_one_edge_each(self) -> None:
        src = """\
package com.x;
public interface OrderRepository extends JpaRepository<Order, Long> {
    Order findByOrderNo(String no);
    long countByStatus(String status);
    void deleteByCustomerId(Long id);
    Order save(Order o);
    void someInternalHelper();
}
"""
        _, edges = _analyze(src)
        # 4 메서드 매칭 (find/count/delete/save), helper 는 미매칭.
        assert len(edges) == 4
        ops = {e.attributes["jpa_operation"] for e in edges}
        assert ops == {"find", "count", "delete", "save"}

    def test_each_edge_targets_same_entity(self) -> None:
        src = """\
package com.x;
public interface OrderRepository extends JpaRepository<Order, Long> {
    Order findByOrderNo(String no);
    void deleteByCustomerId(Long id);
}
"""
        _, edges = _analyze(src)
        targets = {e.target for e in edges}
        assert targets == {"Order"}


# ---------------------------------------------------------------------------
# Protocol 적합 + 빈 입력
# ---------------------------------------------------------------------------
class TestProtocol:
    def test_conforms_to_spring_analyzer(self) -> None:
        from backend.modeling.code_analysis.spring import SpringAnalyzer
        assert isinstance(JpaAnalyzer(), SpringAnalyzer)

    def test_empty_tree_yields_nothing(self) -> None:
        analyzer = JpaAnalyzer()
        entities, edges = analyzer.analyze(
            tree=None, content=b"",
            file_path="empty.java", pkg_name=None,
        )
        assert entities == []
        assert edges == []

    def test_class_declaration_is_ignored(self) -> None:
        # JpaRepository extends 는 interface 만 — class 가 (잘못) extends 해도 안 봄.
        src = """\
package com.x;
public class WrongUseAsClass extends JpaRepository<E, Long> {
    public E findByName(String name) { return null; }
}
"""
        _, edges = _analyze(src)
        assert edges == []
