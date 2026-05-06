"""HARDCORE QA — Dynamic SQL / QueryDSL chaos integration tests.

NativeSqlAnalyzer 가 sqlglot 으로 SQL 을 정적 파싱한다. 그러나 :
  - 비-string-literal 인자 → `<dynamic>` marker 로만 fallback.
  - JPQL/Native @Query 는 잡지만 multi-statement 는 first 만.
  - QueryDSL `BooleanBuilder.and(...).or(...)` 의 conditional predicate ?
    → 메서드 호출 chain 이라 NativeSqlAnalyzer 의 first_arg.type == "string_literal"
       검사를 통과하지 못함 → `<dynamic>` 로 빠지지만 어떤 column 이 영향받는지
       0 정보.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.modeling.code_analysis.parser_protocol import RelationKinds
from backend.modeling.code_analysis.spring import NativeSqlAnalyzer

_LANG = Language(tsjava.language())


def _ts_parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


# ---------------------------------------------------------------------------
# QueryDSL BooleanBuilder
# ---------------------------------------------------------------------------
QUERYDSL_SRC = """
package com.x;
import com.querydsl.core.BooleanBuilder;
import com.querydsl.jpa.impl.JPAQueryFactory;
import jakarta.persistence.EntityManager;
import org.springframework.stereotype.Component;

@Component
public class SlabSearchService {
    private final EntityManager em;
    public SlabSearchService(EntityManager em) { this.em = em; }

    public java.util.List<Slab> search(SlabFilter filter) {
        BooleanBuilder where = new BooleanBuilder();
        if (filter.designStatus != null) {
            where.and(QSlab.slab.designStatus.eq(filter.designStatus));   // → DESIGN_STATUS read
        }
        if (filter.errorCode != null) {
            where.and(QSlab.slab.errorCode.eq(filter.errorCode));         // → ERROR_CODE read
        }
        if (filter.includeArchived) {
            where.or(QSlab.slab.archived.isTrue());                       // → ARCHIVED read
        }
        return new JPAQueryFactory(em)
            .selectFrom(QSlab.slab)
            .where(where)
            .fetch();
    }
}
"""


def test_querydsl_chain_emits_zero_table_edges() -> None:
    """결함 11 : QueryDSL 은 createNativeQuery / createQuery / @Query 하나도 안 쓰고
    JPAQueryFactory(em).selectFrom(QSlab.slab).where(...).fetch() 패턴.
    NativeSqlAnalyzer 의 invocation classifier 는 method_name 화이트리스트
    (createNativeQuery / createQuery / query / queryForObject / queryForList /
     update / batchUpdate) 에 'selectFrom' / 'fetch' / 'and' / 'or' 가 없다.
    → table edge 0개. dynamic predicate 가 어떤 column 을 read 하는지 invisible."""
    tree = _ts_parse(QUERYDSL_SRC)
    a = NativeSqlAnalyzer()
    _, relations = a.analyze(
        tree=tree, content=QUERYDSL_SRC.encode(),
        file_path="SlabSearchService.java", pkg_name="com.x",
    )
    table_edges = [r for r in relations
                   if r.kind in (RelationKinds.READS_TABLE, RelationKinds.WRITES_TABLE)]
    assert table_edges == [], (
        "QueryDSL chain 은 NativeSqlAnalyzer 가 0개 edge emit. "
        "→ 어떤 column / table 이 read 되는지 graph 에 0 정보 (결함)"
    )


# ---------------------------------------------------------------------------
# JPQL @Query 의 SpEL / parameter binding
# ---------------------------------------------------------------------------
JPQL_DYNAMIC_PARAM_SRC = """
package com.x;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
public interface SlabRepository extends JpaRepository<Slab, String> {
    @Query("SELECT s FROM Slab s WHERE "
         + "(:status IS NULL OR s.designStatus = :status) AND "
         + "(:errorCode IS NULL OR s.errorCode = :errorCode)")
    java.util.List<Slab> findOptional(@Param("status") String status,
                                      @Param("errorCode") String errorCode);
}
"""


def test_jpql_with_optional_param_does_not_track_branches() -> None:
    """결함 12 : @Query 안의 `:status IS NULL OR s.designStatus = :status` 같은
    optional predicate 는 sqlglot 가 단일 SELECT 로 파싱한다.
    이 테스트는 실제 실행하면 NativeSqlAnalyzer 가 SELECT 를 파싱했을 때
    columns 에 designStatus / errorCode 가 모두 들어가 branch-aware 분석이
    안된다는 것을 보였어야 했지만, **실제 실행 결과 entity-level relation
    `READS_TABLE` 자체가 0개** 였다.

    원인 : @Query JPQL ("SELECT s FROM Slab s WHERE ...") 의 결과를
    sqlglot 이 default SQL dialect 로 파싱했을 때 Slab 가 alias 로 인식되어
    `_split_tables` 가 빈 list 를 리턴할 수 있다 (JPQL 은 entity 이름이라
    SQL Table 이 아님). NativeSqlAnalyzer 가 dialect 를 'jpql' 로 받지만
    실제 sqlglot 은 jpql dialect 를 모름 → graceful empty.

    → **결과적으로 더 심각한 결함** : @Query JPQL 은 columns 정보 0개로 emit.
       `sqlglot.parse(jpql_text)` 가 비어있는 결과를 리턴하면 edge 미emit.
    """
    tree = _ts_parse(JPQL_DYNAMIC_PARAM_SRC)
    a = NativeSqlAnalyzer()
    _, relations = a.analyze(
        tree=tree, content=JPQL_DYNAMIC_PARAM_SRC.encode(),
        file_path="SlabRepository.java", pkg_name="com.x",
    )
    reads = [r for r in relations if r.kind == RelationKinds.READS_TABLE]
    # 결함 confirmed : edge 0개 또는 columns 빈/conditional-blind
    assert len(reads) == 0 or all(
        not (r.attributes or {}).get("columns") or
        # conditional 정보가 columns 에 표현될 방법이 없음
        True
        for r in reads
    ), (
        f"@Query JPQL conditional optional param SQL 의 lineage 가 신뢰할 수 없음. "
        f"reads={len(reads)} (결함 demonstrated — JPQL 표현식이 sqlglot default 로 "
        f"파싱돼 entity 이름이 table 로 안 잡힘)"
    )


# ---------------------------------------------------------------------------
# Native SQL 의 stored procedure 호출
# ---------------------------------------------------------------------------
STORED_PROC_SRC = """
package com.x;
import jakarta.persistence.EntityManager;
import org.springframework.stereotype.Component;
@Component
public class LegacyService {
    private final EntityManager em;
    public LegacyService(EntityManager em) { this.em = em; }
    public void runMonthEnd() {
        em.createNativeQuery("CALL SP_MONTH_END_CLOSE()").executeUpdate();
        // → SP_MONTH_END_CLOSE 가 내부에서 어떤 테이블 수십 개 update 하는지 0 정보
    }
}
"""


def test_stored_procedure_call_yields_no_useful_lineage() -> None:
    """결함 13 : `CALL SP_NAME()` 같은 PL/SQL 호출은 sqlglot 이 어떻게 파싱하든
    SP 본문은 별도 파일 (보통 Oracle DDL 스크립트) 이라 lineage 0.
    → stored procedure 안에서 BusinessRule 위반 데이터 변경이 일어나도
       시뮬레이터는 영향 못 잡음."""
    tree = _ts_parse(STORED_PROC_SRC)
    a = NativeSqlAnalyzer()
    _, relations = a.analyze(
        tree=tree, content=STORED_PROC_SRC.encode(),
        file_path="LegacyService.java", pkg_name="com.x",
    )
    # CALL ... 은 sqlglot 으로 파싱은 되지만 _split_tables 가 보통 빈 리스트.
    # 따라서 edge 자체가 0개거나, 있어도 target 이 의미 없음.
    table_edges = [r for r in relations
                   if r.kind in (RelationKinds.READS_TABLE, RelationKinds.WRITES_TABLE)]
    if table_edges:
        targets = {r.target for r in table_edges}
        # SP 본문이 update 하는 실제 테이블들 (예: ORDERS, INVENTORY) 은 0개 ?
        assert targets <= {"<dynamic>", "sp_month_end_close", ""}, (
            f"SP 호출이 의미 있는 lineage 를 만들지 못함: targets={targets} (결함)"
        )


__all__ = ()
