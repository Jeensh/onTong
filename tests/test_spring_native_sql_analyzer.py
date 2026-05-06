"""OD-11-B6-3 : Spring NativeSqlAnalyzer — SQL 호출 사이트 → READS_TABLE / WRITES_TABLE.

감지 대상:
  - Spring Data `@Query("...")` / `@Query(value="...", nativeQuery=true)` (METHOD annotation)
  - `@Modifying` + `@Query("UPDATE...")` → write
  - `EntityManager.createNativeQuery("...")` / `.createQuery("...")` (JPQL)
  - `JdbcTemplate.{query,queryForObject,queryForList}` → read
  - `JdbcTemplate.{update,batchUpdate}` → write

출력 규약:
  - `CodeRelation(kind=reads_table|writes_table, source=<METHOD fqn>, target=<lower(table)>)`
  - attributes: `columns` (dedup, order preserved / ["<dynamic>"] on parse fail),
    `confidence` (1.0 static literal, 0.3 dynamic), `raw_sql`, `dialect` ("sql"|"jpql").
  - Multi-statement : 첫 statement 처리 + `attributes["multi_statement_warning"] = True`.
  - DB_TABLE 노드 emit 없음 (B6-4 에서 dedup).

설계:
  - `analyze()` 가 relation 을 직접 emit (standalone 패턴, B6-1 MapStruct 와 동일).
  - `enrich()` 는 no-op.
"""

from __future__ import annotations

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.modeling.code_analysis.parser_protocol import EntityKinds, RelationKinds
from backend.modeling.code_analysis.spring import NativeSqlAnalyzer

_LANG = Language(tsjava.language())


def _parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


def _analyze(src: str, file_path: str = "T.java", pkg_name: str | None = "com.x.repo"):
    tree = _parse(src)
    a = NativeSqlAnalyzer()
    return a.analyze(tree=tree, content=src.encode(), file_path=file_path, pkg_name=pkg_name)


def _reads(relations) -> list:
    return [r for r in relations if r.kind == RelationKinds.READS_TABLE]


def _writes(relations) -> list:
    return [r for r in relations if r.kind == RelationKinds.WRITES_TABLE]


# ---------------------------------------------------------------------------
# 1. @Query basic SELECT → reads_table
# ---------------------------------------------------------------------------
def test_query_annotation_select_emits_reads_table() -> None:
    src = """
package com.x.repo;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface OrderRepo {
    @Query(value = "SELECT id, customer_id FROM orders WHERE customer_id = ?1", nativeQuery = true)
    List<Object> findByCustomer(Long customerId);
}
"""
    entities, relations = _analyze(src)
    assert entities == []
    reads = _reads(relations)
    assert len(reads) == 1
    r = reads[0]
    assert r.source == "com.x.repo.OrderRepo.findByCustomer"
    assert r.target == "orders"
    assert r.attributes["confidence"] == 1.0
    assert r.attributes["dialect"] == "sql"
    cols = r.attributes["columns"]
    assert "id" in cols and "customer_id" in cols
    # dedupe: customer_id appears in SELECT + WHERE but only once
    assert cols.count("customer_id") == 1
    assert "SELECT id" in r.attributes["raw_sql"]


# ---------------------------------------------------------------------------
# 2. @Query(value="INSERT", nativeQuery=true) → writes_table
# ---------------------------------------------------------------------------
def test_query_annotation_native_insert_emits_writes_table() -> None:
    src = """
package com.x.repo;
import org.springframework.data.jpa.repository.Query;

public interface OrderRepo {
    @Query(value = "INSERT INTO orders (id, total) VALUES (?, ?)", nativeQuery = true)
    void insertOrder(Long id, Long total);
}
"""
    _, relations = _analyze(src)
    assert _reads(relations) == []
    writes = _writes(relations)
    assert len(writes) == 1
    w = writes[0]
    assert w.source == "com.x.repo.OrderRepo.insertOrder"
    assert w.target == "orders"
    assert w.attributes["confidence"] == 1.0
    assert w.attributes["dialect"] == "sql"


# ---------------------------------------------------------------------------
# 3. @Modifying + @Query UPDATE → writes_table
# ---------------------------------------------------------------------------
def test_modifying_update_emits_writes_table() -> None:
    src = """
package com.x.repo;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.jpa.repository.Modifying;

public interface OrderRepo {
    @Modifying
    @Query("UPDATE orders SET status = ?1 WHERE id = ?2")
    int updateStatus(String status, Long id);
}
"""
    _, relations = _analyze(src)
    writes = _writes(relations)
    assert len(writes) == 1
    w = writes[0]
    assert w.source == "com.x.repo.OrderRepo.updateStatus"
    assert w.target == "orders"
    assert "status" in w.attributes["columns"]


# ---------------------------------------------------------------------------
# 4. JPQL @Query (nativeQuery omitted) → reads_table + dialect=jpql
# ---------------------------------------------------------------------------
def test_query_annotation_jpql_default_marks_dialect() -> None:
    src = """
package com.x.repo;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface OrderRepo {
    @Query("SELECT o FROM Order o WHERE o.customer.id = :cid")
    List<Object> findByCustomerJpql(Long cid);
}
"""
    _, relations = _analyze(src)
    reads = _reads(relations)
    assert len(reads) == 1
    assert reads[0].attributes["dialect"] == "jpql"
    # JPQL entity-name is kept as table-name token (lowercased) — B6-4 resolves to real table
    assert reads[0].target == "order"


# ---------------------------------------------------------------------------
# 5. EntityManager.createNativeQuery(...) → reads_table
# ---------------------------------------------------------------------------
def test_entity_manager_native_query_emits_reads_table() -> None:
    src = """
package com.x.svc;
import javax.persistence.EntityManager;

public class OrderService {
    private final EntityManager em;
    public OrderService(EntityManager em) { this.em = em; }
    public Object loadOrder(Long id) {
        return em.createNativeQuery("SELECT id, total FROM orders WHERE id = ?").getSingleResult();
    }
}
"""
    _, relations = _analyze(src, pkg_name="com.x.svc")
    reads = _reads(relations)
    assert len(reads) == 1
    r = reads[0]
    assert r.source == "com.x.svc.OrderService.loadOrder"
    assert r.target == "orders"
    assert r.attributes["dialect"] == "sql"


# ---------------------------------------------------------------------------
# 6. JdbcTemplate.query(...) → reads_table
# ---------------------------------------------------------------------------
def test_jdbc_template_query_emits_reads_table() -> None:
    src = """
package com.x.svc;
import org.springframework.jdbc.core.JdbcTemplate;
import java.util.List;

public class OrderDao {
    private final JdbcTemplate jdbc;
    public OrderDao(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public List<Object> listOrders() {
        return jdbc.query("SELECT id, customer_id FROM orders", (rs, i) -> null);
    }
}
"""
    _, relations = _analyze(src, pkg_name="com.x.svc")
    reads = _reads(relations)
    assert len(reads) == 1
    assert reads[0].source == "com.x.svc.OrderDao.listOrders"
    assert reads[0].target == "orders"
    assert "customer_id" in reads[0].attributes["columns"]


# ---------------------------------------------------------------------------
# 7. JdbcTemplate.update(...) → writes_table
# ---------------------------------------------------------------------------
def test_jdbc_template_update_emits_writes_table() -> None:
    src = """
package com.x.svc;
import org.springframework.jdbc.core.JdbcTemplate;

public class OrderDao {
    private final JdbcTemplate jdbc;
    public OrderDao(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public int updateTotal(Long id, Long total) {
        return jdbc.update("UPDATE orders SET total = ? WHERE id = ?", total, id);
    }
}
"""
    _, relations = _analyze(src, pkg_name="com.x.svc")
    assert _reads(relations) == []
    writes = _writes(relations)
    assert len(writes) == 1
    assert writes[0].source == "com.x.svc.OrderDao.updateTotal"
    assert writes[0].target == "orders"


# ---------------------------------------------------------------------------
# 8. JOIN multi-table → 2 reads_table edges
# ---------------------------------------------------------------------------
def test_join_emits_reads_for_each_table() -> None:
    src = """
package com.x.repo;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface OrderRepo {
    @Query(value = "SELECT o.id, c.name FROM orders o JOIN customers c ON o.customer_id = c.id", nativeQuery = true)
    List<Object> listJoined();
}
"""
    _, relations = _analyze(src)
    reads = _reads(relations)
    assert len(reads) == 2
    targets = sorted(r.target for r in reads)
    assert targets == ["customers", "orders"]
    # Both edges share the same source method
    assert all(r.source == "com.x.repo.OrderRepo.listJoined" for r in reads)


# ---------------------------------------------------------------------------
# 9. Subquery → inner tables also reads_table
# ---------------------------------------------------------------------------
def test_subquery_includes_inner_tables() -> None:
    src = """
package com.x.repo;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface OrderRepo {
    @Query(value = "SELECT * FROM customers WHERE id IN (SELECT customer_id FROM orders WHERE status = ?1)", nativeQuery = true)
    List<Object> activeCustomers(String status);
}
"""
    _, relations = _analyze(src)
    reads = _reads(relations)
    targets = sorted(r.target for r in reads)
    assert targets == ["customers", "orders"]


# ---------------------------------------------------------------------------
# 10. INSERT INTO ... SELECT → writes_table (target) + reads_table (source)
# ---------------------------------------------------------------------------
def test_insert_select_emits_both_write_and_read() -> None:
    src = """
package com.x.repo;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.jpa.repository.Modifying;

public interface OrderRepo {
    @Modifying
    @Query(value = "INSERT INTO audit_log SELECT id, customer_id FROM orders WHERE status = ?1", nativeQuery = true)
    int archive(String status);
}
"""
    _, relations = _analyze(src)
    writes = _writes(relations)
    reads = _reads(relations)
    assert len(writes) == 1
    assert writes[0].target == "audit_log"
    assert len(reads) == 1
    assert reads[0].target == "orders"
    # Same source method
    assert writes[0].source == reads[0].source == "com.x.repo.OrderRepo.archive"


# ---------------------------------------------------------------------------
# 11. Dynamic SQL (StringBuilder / string concat) → <dynamic> marker, confidence 0.3
# ---------------------------------------------------------------------------
def test_dynamic_sql_marks_low_confidence() -> None:
    src = """
package com.x.svc;
import org.springframework.jdbc.core.JdbcTemplate;
import java.util.List;

public class OrderDao {
    private final JdbcTemplate jdbc;
    public OrderDao(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public List<Object> dynamic(String tableName) {
        String sql = "SELECT * FROM " + tableName + " WHERE status = ?";
        return jdbc.query(sql, (rs, i) -> null);
    }
}
"""
    _, relations = _analyze(src, pkg_name="com.x.svc")
    reads = _reads(relations)
    assert len(reads) == 1
    r = reads[0]
    assert r.attributes["confidence"] == 0.3
    assert r.attributes["columns"] == ["<dynamic>"]
    assert r.target == "<dynamic>"
    assert "raw_sql" in r.attributes


# ---------------------------------------------------------------------------
# 12. MyBatis-style sqlSession call is out of scope → no edges
# ---------------------------------------------------------------------------
def test_mybatis_style_call_is_ignored() -> None:
    src = """
package com.x.svc;

public class OrderService {
    private final Object sqlSession;
    public OrderService(Object sqlSession) { this.sqlSession = sqlSession; }
    public Object byId(Long id) {
        return ((org.apache.ibatis.session.SqlSession) sqlSession).selectOne("OrderMapper.selectById", id);
    }
}
"""
    _, relations = _analyze(src, pkg_name="com.x.svc")
    assert _reads(relations) == []
    assert _writes(relations) == []


# ---------------------------------------------------------------------------
# 13. @Query native=false (default) vs native=true → dialect differs
# ---------------------------------------------------------------------------
def test_query_native_vs_jpql_dialect_flag() -> None:
    src = """
package com.x.repo;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface OrderRepo {
    @Query("SELECT o FROM Order o")
    List<Object> jpqlAll();

    @Query(value = "SELECT id FROM orders", nativeQuery = true)
    List<Object> nativeAll();
}
"""
    _, relations = _analyze(src)
    reads = _reads(relations)
    by_source = {r.source: r for r in reads}
    assert by_source["com.x.repo.OrderRepo.jpqlAll"].attributes["dialect"] == "jpql"
    assert by_source["com.x.repo.OrderRepo.nativeAll"].attributes["dialect"] == "sql"


# ---------------------------------------------------------------------------
# 14. Multi-statement SQL → first statement processed + warning marker
# ---------------------------------------------------------------------------
def test_multi_statement_processes_first_with_warning() -> None:
    src = """
package com.x.svc;
import org.springframework.jdbc.core.JdbcTemplate;

public class OrderDao {
    private final JdbcTemplate jdbc;
    public OrderDao(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public void both() {
        jdbc.update("UPDATE orders SET status = 'A'; DELETE FROM archive WHERE id = 1");
    }
}
"""
    _, relations = _analyze(src, pkg_name="com.x.svc")
    writes = _writes(relations)
    # first statement is UPDATE orders → writes_table
    assert len(writes) == 1
    assert writes[0].target == "orders"
    assert writes[0].attributes.get("multi_statement_warning") is True


# ---------------------------------------------------------------------------
# 15. Table name normalization → always lowercase
# ---------------------------------------------------------------------------
def test_table_names_are_lowercased() -> None:
    src = """
package com.x.repo;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface OrderRepo {
    @Query(value = "SELECT * FROM ORDERS WHERE ID = ?1", nativeQuery = true)
    List<Object> byId(Long id);
}
"""
    _, relations = _analyze(src)
    reads = _reads(relations)
    assert len(reads) == 1
    assert reads[0].target == "orders"  # was ORDERS in SQL


# ---------------------------------------------------------------------------
# 16. Standalone analyze() emits relations directly (no enrich dependency)
# ---------------------------------------------------------------------------
def test_analyze_is_standalone_not_enrich_based() -> None:
    src = """
package com.x.repo;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface OrderRepo {
    @Query(value = "SELECT id FROM orders", nativeQuery = true)
    List<Object> allIds();
}
"""
    tree = _parse(src)
    a = NativeSqlAnalyzer()
    entities, relations = a.analyze(
        tree=tree, content=src.encode(), file_path="OrderRepo.java", pkg_name="com.x.repo",
    )
    # analyze() alone is enough to produce the edge — no enrich() needed.
    assert _reads(relations), "analyze() must emit relations directly (standalone pattern)"
    # enrich() is a no-op: identity on the inputs.
    ent_out, rel_out = a.enrich(
        entities=entities, relations=relations, tree=tree, pkg_name="com.x.repo",
    )
    assert ent_out is entities or ent_out == entities
    assert rel_out is relations or rel_out == relations
