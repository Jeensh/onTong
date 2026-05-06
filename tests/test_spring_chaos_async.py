"""HARDCORE QA — Spring chaos integration tests.

이 파일은 모델링 엔진의 architectural blind spot 을 명시적으로 assert 한다.
"문서화된 결함" 격으로, 시뮬레이터가 어떤 런타임 인과율을 잡고 / 놓치는지를
실제 tree-sitter 파싱 결과로 검증.

각 테스트는 두 가지 형태 :
  - test_X_is_currently_BROKEN : 현재 시뮬레이터가 잡지 못함을 assert (regression
    senior — 누군가 고치면 이 테스트가 깨지면서 잡았다고 알림).
  - test_X_partial_capture     : 일부만 잡힘을 assert (어디까지 보이는지 정량화).

테스트 시나리오 :
  A. @Scheduled 비동기 오염   — main tx 와 독립적으로 BusinessRule 위반 데이터
                              생성. 영향도 그래프에 main → scheduled 엣지 X.
  B. ApplicationEventPublisher — publishEvent ↔ @EventListener 가
                              event_type 노드를 매개로 연결되는 정도.
  C. @Transactional 프록시   — REQUIRES_NEW propagation 인식 X. 롤백 경계 X.
  D. AOP @Around              — execution(* foo..*(..)) 가 메서드 단위로
                              expand 되지 않고 클래스 단위 target 만.
  E. @Qualifier 다중 구현체   — call_resolver.py 가 qualifier 무시, 첫 후보만.
  F. MyBatis XML / @Mapper    — analyzer 자체가 없음. <if test=...> dynamic
                              SQL 의 조건부 read/write 미감지.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from backend.modeling.code_analysis.call_resolver import resolve_calls
from backend.modeling.code_analysis.parser_protocol import (
    EntityKinds,
    RelationKinds,
    ParseResult,
)
from backend.modeling.code_analysis.spring import (
    AopAnalyzer,
    DIAnalyzer,
    EventsAnalyzer,
    JpaAnalyzer,
    NativeSqlAnalyzer,
    ScheduledAnalyzer,
)
from backend.modeling.code_analysis.java_parser import JavaParser

_LANG = Language(tsjava.language())


def _ts_parse(src: str):
    p = Parser(_LANG)
    return p.parse(src.encode())


# ---------------------------------------------------------------------------
# 시나리오 A — @Scheduled 비동기 오염 (배치 잡이 main flow 와 독립 mutation)
# ---------------------------------------------------------------------------
SCENARIO_A_SRC = """
package com.x;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class NightlyCleanupJob {

    private final SlabRepository repo;

    public NightlyCleanupJob(SlabRepository repo) {
        this.repo = repo;
    }

    /**
     * 매일 03:00 — 오래된 IN_PROGRESS slab 을 상태=ABANDONED 로 일괄 변경.
     * 이 변경은 designer.design() 의 main tx 와 완전 독립.
     * BusinessRule "designStatus 값은 SUCCESS|FAIL|IN_PROGRESS 중 하나" 를 위반.
     */
    @Scheduled(cron = "0 0 3 * * ?")
    public void cleanup() {
        repo.markAbandoned();   // main flow 가 한 번도 거치지 않는 path
    }
}
"""

SCENARIO_A_REPO_SRC = """
package com.x;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
public interface SlabRepository extends JpaRepository<Slab, String> {
    @Modifying
    @Query("UPDATE Slab s SET s.designStatus = 'ABANDONED' WHERE s.designStatus = 'IN_PROGRESS'")
    void markAbandoned();
}
"""


def test_scheduled_emits_entity_only_no_invocation_edge() -> None:
    """결함 1 : @Scheduled 메서드는 scheduled_task 엔티티는 생기지만,
    `<scheduler-runtime>` → cleanup() 같은 invocation edge 가 없다.
    = call graph BFS 에서 cleanup() 의 incoming 이 없음.
    = "main flow 만 보고 OK" 라고 시뮬레이터가 판단할 수 있다.
    """
    tree = _ts_parse(SCENARIO_A_SRC)
    a = ScheduledAnalyzer()
    entities, relations = a.analyze(
        tree=tree, content=SCENARIO_A_SRC.encode(),
        file_path="NightlyCleanupJob.java", pkg_name="com.x",
    )
    assert len(entities) == 1
    assert entities[0].kind == EntityKinds.SCHEDULED_TASK
    assert entities[0].qualified_name == "com.x.NightlyCleanupJob.cleanup#scheduled"
    # ! 핵심 결함 ! : edge 자체가 0개다 — main flow → cleanup 인과 X
    assert relations == [], "ScheduledAnalyzer 는 entity-only 라 invocation edge 0개 (결함 demonstrated)"


def test_scheduled_repository_call_is_callable_via_call_resolver() -> None:
    """확인용 : repo.markAbandoned() 자체는 잡힌다. 문제는 누가 그 호출의
    incoming 트리거인지 — @Scheduled 가 그 트리거임을 표현하는 엣지가 없음."""
    parser = JavaParser()
    pr1 = parser.parse_file(Path("NightlyCleanupJob.java"), SCENARIO_A_SRC)
    pr2 = parser.parse_file(Path("SlabRepository.java"), SCENARIO_A_REPO_SRC)
    # repo.markAbandoned() 는 잡힘 (call edge 존재)
    new_edges, stats = resolve_calls([pr1, pr2])
    method_call_edges = [r for r in pr1.relations if r.kind == "calls"]
    # call edge 가 1개는 있을 거다 (this.repo.markAbandoned 또는 비슷)
    assert any("markAbandoned" in r.target for r in method_call_edges + new_edges), \
        "repo.markAbandoned() call 은 정적 분석으로 잡힌다"


# ---------------------------------------------------------------------------
# 시나리오 B — ApplicationEventPublisher 비동기
# ---------------------------------------------------------------------------
SCENARIO_B_SRC = """
package com.x;

import org.springframework.context.ApplicationEventPublisher;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

@Component
public class OrderService {

    private final ApplicationEventPublisher publisher;
    private final SlabRepository repo;

    public OrderService(ApplicationEventPublisher publisher, SlabRepository repo) {
        this.publisher = publisher;
        this.repo = repo;
    }

    public void completeOrder(String orderNo) {
        repo.markComplete(orderNo);                    // main flow
        publisher.publishEvent(new OrderCompletedEvent(orderNo));
        // ↑ 여기서 main flow 끝, 호출자는 정상 return
    }
}

@Component
class SlabAuditListener {

    private final SlabRepository repo;

    public SlabAuditListener(SlabRepository repo) {
        this.repo = repo;
    }

    @EventListener
    @Async                                            // ← 비동기로 별도 스레드
    public void onCompleted(OrderCompletedEvent ev) {
        repo.deleteAuditTrail(ev.getOrderNo());       // main tx 외부 — rollback X
    }
}

class OrderCompletedEvent {
    private final String orderNo;
    public OrderCompletedEvent(String orderNo) { this.orderNo = orderNo; }
    public String getOrderNo() { return orderNo; }
}
"""


def test_publisher_to_listener_is_INDIRECT_via_event_type() -> None:
    """결함 2 : completeOrder() → onCompleted() direct call edge 없음.
    PUBLISHES 와 HANDLES 가 같은 event_type 노드를 가리키긴 하지만,
    impact_propagator 의 _bfs_code 는 calls edge 만 따른다 (graph_view 를
    QueryEngine 으로 traverse, 모든 kind 포괄하지만 source/target 이
    event_type 인 엣지는 계속 event_type 노드 안에서만 살아있음)."""
    tree = _ts_parse(SCENARIO_B_SRC)
    a = EventsAnalyzer()
    entities, relations = a.analyze(
        tree=tree, content=SCENARIO_B_SRC.encode(),
        file_path="OrderService.java", pkg_name="com.x",
    )
    publishes = [r for r in relations if r.kind == RelationKinds.PUBLISHES]
    handles = [r for r in relations if r.kind == RelationKinds.HANDLES]
    assert len(publishes) == 1
    assert publishes[0].source == "com.x.OrderService.completeOrder"
    assert publishes[0].target == "com.x.OrderCompletedEvent"
    assert len(handles) == 1
    assert handles[0].source == "com.x.SlabAuditListener.onCompleted"
    assert handles[0].target == "com.x.OrderCompletedEvent"
    # ! 핵심 결함 ! : completeOrder → onCompleted 직접 call edge 가 0개.
    direct = [r for r in relations
              if r.source == "com.x.OrderService.completeOrder"
              and r.target == "com.x.SlabAuditListener.onCompleted"]
    assert direct == [], (
        "publisher → listener 사이엔 직접 'calls' edge 가 없다. "
        "QueryEngine.impact(completeOrder, direction='outgoing') 는 onCompleted 를 "
        "발견하려면 PUBLISHES → event_type → HANDLES (역방향) 2-hop 을 일관되게 "
        "처리해야 하는데, _bfs 는 모든 kind 를 따르긴 하나 incoming/outgoing 의 "
        "역할이 'PUBLISHES (outgoing) → HANDLES (incoming on event_type)' 가 "
        "한 방향 BFS 안에서 자연스럽지 않음."
    )


def test_async_listener_has_no_special_marker() -> None:
    """결함 3 : @Async 가 메서드에 붙어 있어도 EventsAnalyzer 의 HANDLES 엣지에
    `async=True` 같은 marker 가 없다.
    → 시뮬레이터가 'rollback safe' 인지 'async fire-and-forget' 인지 모른다.
    → BusinessRule 위반이 비동기 listener 에서 발생하면 main tx 가 commit 후
    독립적으로 실행되어, "main 메서드 OK" 시뮬레이션 결과와 실제 런타임이 분기."""
    tree = _ts_parse(SCENARIO_B_SRC)
    a = EventsAnalyzer()
    _, relations = a.analyze(
        tree=tree, content=SCENARIO_B_SRC.encode(),
        file_path="OrderService.java", pkg_name="com.x",
    )
    handles = [r for r in relations if r.kind == RelationKinds.HANDLES]
    assert len(handles) == 1
    h = handles[0]
    # 어디에도 async marker 가 없다
    assert "async" not in (h.attributes or {}), (
        "HANDLES edge attributes 에 async marker 가 없음 — "
        "rollback boundary 분석 불가 (결함)"
    )


# ---------------------------------------------------------------------------
# 시나리오 C — @Transactional 프록시 / propagation
# ---------------------------------------------------------------------------
SCENARIO_C_SRC = """
package com.x;

import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Component
public class HistoryAction {

    private final HistoryRepository repo;

    public HistoryAction(HistoryRepository repo) {
        this.repo = repo;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void recordFailure(String slabNo, String error) {
        repo.save(new HistEntity(slabNo, error));
    }
}

@Component
class Designer {

    private final HistoryAction historyAction;
    private final SlabRepository slabRepo;

    public Designer(HistoryAction historyAction, SlabRepository slabRepo) {
        this.historyAction = historyAction;
        this.slabRepo = slabRepo;
    }

    @Transactional
    public void design(String orderNo) {
        try {
            slabRepo.create(orderNo);
            doSomethingThatThrows();
        } catch (Exception e) {
            historyAction.recordFailure(orderNo, e.getMessage());   // REQUIRES_NEW
            // → 외부 tx rollback 되어도 history 만은 commit 되어야 한다.
        }
    }

    private void doSomethingThatThrows() {
        throw new RuntimeException("boom");
    }
}
"""


def test_transactional_annotation_is_NOT_recognized_anywhere() -> None:
    """결함 4 : @Transactional 자체에 대한 analyzer 가 0 개. propagation 미인식.
    그래프 어디에도 'tx_boundary' / 'rollback_scope' 마커가 없다.
    → 시뮬레이터가 design() 안의 historyAction.recordFailure() 호출이
       outer rollback 에 끌려가는지 (Propagation.REQUIRED 면 yes) /
       독립 commit 인지 (REQUIRES_NEW 면 no) 구분 불가능.
    → demo 에서 "이 변경은 안전합니다" 결론이 실제론 위험."""
    parser = JavaParser()
    pr = parser.parse_file(Path("HistoryAction.java"), SCENARIO_C_SRC)
    # 모든 entity / relation 을 훑어서 'transactional' / 'propagation' 키 포함 여부
    has_tx_marker = False
    for ent in pr.entities:
        attrs = ent.attributes or {}
        if any("transaction" in str(k).lower() or "propagation" in str(k).lower()
               or "rollback" in str(k).lower() for k in attrs.keys()):
            has_tx_marker = True
            break
    for rel in pr.relations:
        attrs = rel.attributes or {}
        if any("transaction" in str(k).lower() or "propagation" in str(k).lower()
               or "rollback" in str(k).lower() for k in attrs.keys()):
            has_tx_marker = True
            break
    assert not has_tx_marker, (
        "@Transactional 정보가 그래프에 0건 마킹됨 — "
        "REQUIRES_NEW vs REQUIRED 구분 불가 (결함)"
    )


# ---------------------------------------------------------------------------
# 시나리오 D — AOP execution(...) pointcut 의 method-level expand 부재
# ---------------------------------------------------------------------------
SCENARIO_D_SRC = """
package com.x;

import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.stereotype.Component;

@Aspect
@Component
public class AuditAspect {

    /**
     * com.x.OrderService 의 모든 public 메서드에 audit log 적재.
     * 이 audit log 는 별도 테이블에 INSERT — main tx 와 독립 (REQUIRES_NEW).
     * 변경 시 BusinessRule "audit row 는 모든 successful operation 에 1건 생성" 위반 가능.
     */
    @Around("execution(* com.x.OrderService.*(..))")
    public Object audit(ProceedingJoinPoint jp) throws Throwable {
        Object result = jp.proceed();
        // → 여기서 audit_repo.save(...) — INSERT 가 발생하지만
        //   AopAnalyzer 는 본문을 분석하지 않는다.
        return result;
    }
}
"""


def test_aop_intercepts_class_not_method() -> None:
    """결함 5 : AopAnalyzer 의 INTERCEPTS edge target 은 클래스 FQN.
    `execution(* com.x.OrderService.*(..))` 는 메서드 N개 매칭이지만
    엣지는 1개만 (target=com.x.OrderService).
    → impact(method=OrderService.completeOrder).incoming 은 INTERCEPTS 를
       포함하지 않는다 (target 이 OrderService 클래스).
    → demo 에서 "이 메서드는 advice 영향 없음" 잘못된 결론."""
    tree = _ts_parse(SCENARIO_D_SRC)
    a = AopAnalyzer()
    _, relations = a.analyze(
        tree=tree, content=SCENARIO_D_SRC.encode(),
        file_path="AuditAspect.java", pkg_name="com.x",
    )
    intercepts = [r for r in relations if r.kind == RelationKinds.INTERCEPTS]
    assert len(intercepts) == 1
    assert intercepts[0].target == "com.x.OrderService", (
        "target 이 메서드 단위가 아닌 클래스 단위로 emit 됨 — "
        "method-level impact 그래프에서 advice 가 invisible (결함)"
    )
    # 추가 결함 : advice 본문 안의 audit_repo.save() 같은 호출이
    # advice 자체의 method FQN 으로부터 outgoing 으로만 잡히고,
    # "intercepted method 의 부수 효과" 라는 인과는 그래프에 없다.


def test_aop_advice_body_calls_not_propagated_to_intercepted_methods() -> None:
    """결함 6 : @Around 가 본문에서 audit_repo.save() 같은 부수효과를 발생시켜도
    그 부수효과는 advice 메서드 자신의 calls edge 일 뿐, intercepted method
    들에게 propagate 되지 않는다.
    → "OrderService.completeOrder() 호출 시 어떤 테이블에 write 되는가?" 쿼리
       가 main flow 의 write 만 답하고, audit_repo.save() 는 누락."""
    tree = _ts_parse(SCENARIO_D_SRC)
    a = AopAnalyzer()
    entities, relations = a.analyze(
        tree=tree, content=SCENARIO_D_SRC.encode(),
        file_path="AuditAspect.java", pkg_name="com.x",
    )
    # AopAnalyzer 는 advice body 를 안 본다 — 본문 분석은 NativeSqlAnalyzer / JpaAnalyzer 가
    # 별도로 advice method 를 method 로 보고 처리하지만 그 결과 edge 의 source 는
    # AuditAspect.audit 이지 OrderService.completeOrder 가 아님.
    aspect_edges = [r for r in relations
                    if r.source == "com.x.AuditAspect" or r.source == "com.x.AuditAspect.audit"]
    # INTERCEPTS 1 개만, body 의 implicit write 는 0
    assert all(r.kind == RelationKinds.INTERCEPTS for r in aspect_edges), (
        "AopAnalyzer 는 advice body 의 부수효과를 표현하지 않음 (결함)"
    )


# ---------------------------------------------------------------------------
# 시나리오 E — @Qualifier / 다중 구현체
# ---------------------------------------------------------------------------
SCENARIO_E_IFACE = """
package com.x;
public interface PriceCalculator {
    long calculate(long base);
}
"""

SCENARIO_E_IMPL_A = """
package com.x;
import org.springframework.stereotype.Component;
@Component("standardPrice")
public class StandardPriceCalculator implements PriceCalculator {
    public long calculate(long base) {
        return base;            // 정상가
    }
}
"""

SCENARIO_E_IMPL_B = """
package com.x;
import org.springframework.stereotype.Component;
@Component("vipPrice")
public class VipPriceCalculator implements PriceCalculator {
    public long calculate(long base) {
        return base * 70 / 100;  // VIP 30% 할인 — BusinessRule 영향
    }
}
"""

SCENARIO_E_USER = """
package com.x;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
@Component
public class OrderTotalService {
    private final PriceCalculator calc;
    @Autowired
    public OrderTotalService(@Qualifier("vipPrice") PriceCalculator calc) {
        this.calc = calc;
    }
    public long total(long base) {
        return calc.calculate(base);  // → 어떤 구현체 ?
    }
}
"""


def test_call_resolver_resolves_qualifier_to_correct_impl() -> None:
    """P29-3 — call_resolver 가 @Qualifier 를 인지해 정확한 impl 을 선택.

    원래는 type_candidates[0] (입력 순서 첫 번째) 로 fallback 하던 결함이었으나,
    P29-3 에서 (source_class, field_name) → qualifier → bean_name → class FQN
    lookup 체인을 추가. SCENARIO_E_USER 의 @Qualifier("vipPrice") 는
    VipPriceCalculator 로 정확히 resolve 되어야 한다.

    DIAnalyzer 가 wire 되어 있어야 AUTOWIRES rel 의 qualifier 가 emit 되고,
    call_resolver 가 그걸 활용해 bean_name_index lookup 으로 정확한 impl 선택."""
    parser = JavaParser(spring_analyzers=[DIAnalyzer()])
    pr_iface = parser.parse_file(Path("PriceCalculator.java"), SCENARIO_E_IFACE)
    pr_a = parser.parse_file(Path("StandardPriceCalculator.java"), SCENARIO_E_IMPL_A)
    pr_b = parser.parse_file(Path("VipPriceCalculator.java"), SCENARIO_E_IMPL_B)
    pr_user = parser.parse_file(Path("OrderTotalService.java"), SCENARIO_E_USER)

    # 의도적으로 standard 를 먼저 (→ first wins 였던 옛 결함 유발 순서) 로 배치
    new_edges, _ = resolve_calls([pr_iface, pr_a, pr_b, pr_user])

    resolved_targets = [
        r.target for r in new_edges
        if r.source == "com.x.OrderTotalService.total"
    ]
    # P29-3 fix : qualifier-aware resolution → Vip impl 로 정확히 resolve
    # (resolve 자체가 못 일어나면 — 즉 0개면 — 다른 누락 결함이므로 그것도 fail)
    assert resolved_targets, (
        "OrderTotalService.total → calc.calculate() 가 어떤 impl 로도 resolve 안됨 "
        "(call_resolver 가 호출 자체를 놓침)"
    )
    assert any("VipPriceCalculator.calculate" in t for t in resolved_targets), (
        "P29-3 fix 누락 — @Qualifier(\"vipPrice\") 가 있는데도 "
        f"VipPriceCalculator 로 resolve 안됨. 실제 resolved={resolved_targets}"
    )

    # 코드 inspect — qualifier 처리 코드가 존재하는지 확인 (regression guard)
    src = inspect.getsource(resolve_calls)
    assert "qualifier" in src.lower(), (
        "call_resolver.resolve_calls 가 'qualifier' 처리를 잃어버림 — "
        "P29-3 fix 가 regression 됨"
    )


# ---------------------------------------------------------------------------
# 시나리오 F — MyBatis XML / @Mapper dynamic SQL
# ---------------------------------------------------------------------------
SCENARIO_F_XML_PATH_HINT = "mappers/SdSlabMapper.xml"   # sample-repos 의 실제 경로

SCENARIO_F_MAPPER_INTERFACE_SRC = """
package com.x;
import org.apache.ibatis.annotations.Mapper;
public interface SdSlabMyBatisMapper {
    int updateConditionally(SlabFilter filter);   // XML 의 dynamic SQL 호출
}
"""

SCENARIO_F_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
        "https://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.x.SdSlabMyBatisMapper">
    <update id="updateConditionally">
        UPDATE SLAB
        <set>
            <if test="filter.designStatus != null">
                DESIGN_STATUS = #{filter.designStatus},
            </if>
            <if test="filter.errorCode != null">
                ERROR_CODE = #{filter.errorCode},
            </if>
        </set>
        WHERE ORDER_NO = #{filter.orderNo}
    </update>
</mapper>
"""


def test_mybatis_analyzer_module_present() -> None:
    """P29-2 — MyBatis @Mapper analyzer 가 spring 패키지에 존재.

    원래는 .xml + @Select/@Insert 처리가 0 이었던 결함. P29-2 에서
    `mybatis_mapper_analyzer.py` (annotation SQL) 추가 + 별도로
    repo_parser 에서 `mybatis_xml_parser.py` (XML <if>/<choose>) 호출."""
    from backend.modeling.code_analysis import spring as spring_pkg
    spring_dir = Path(spring_pkg.__file__).parent
    handlers = list(spring_dir.glob("*mybatis*.py"))
    assert handlers, (
        "MyBatis @Mapper analyzer 가 spring 패키지에서 사라짐 — P29-2 fix regression"
    )

    # XML pass 는 repo_parser 에서 불러주는 별도 모듈
    from backend.modeling.code_analysis import mybatis_xml_parser  # noqa: F401


def test_mybatis_mapper_interface_emits_no_table_edges() -> None:
    """결함 9 : @Mapper interface 의 메서드는 JPA 도 아니고 NativeSql 도 아니어서
    어느 analyzer 도 READS_TABLE/WRITES_TABLE 을 emit 하지 않는다."""
    parser = JavaParser()
    pr = parser.parse_file(Path("SdSlabMyBatisMapper.java"), SCENARIO_F_MAPPER_INTERFACE_SRC)
    table_edges = [r for r in pr.relations
                   if r.kind in (RelationKinds.READS_TABLE, RelationKinds.WRITES_TABLE)]
    assert table_edges == [], (
        "@Mapper interface 메서드에 대해 table edge 0개 — "
        "MyBatis 사용 코드는 영향도 그래프에서 'phantom' (결함)"
    )


def test_native_sql_analyzer_marks_dynamic_concat_low_confidence() -> None:
    """확인용 (반례) : Java 코드 안의 String concat SQL 은 NativeSqlAnalyzer 가
    dynamic 으로 marker 한다 (confidence=0.3, target=<dynamic>).
    이건 잘 잡힌다. 문제는 MyBatis XML 의 <if> 는 별도 처리 X 라는 것."""
    src = """
package com.x;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
@Component
public class DynamicQueryService {
    private final JdbcTemplate jdbc;
    public DynamicQueryService(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public int conditional(boolean active) {
        String sql = "UPDATE SLAB SET DESIGN_STATUS = 'X' "
                   + (active ? "WHERE ACTIVE = 1" : "WHERE ARCHIVED = 1");
        return jdbc.update(sql);
    }
}
"""
    tree = _ts_parse(src)
    a = NativeSqlAnalyzer()
    _, relations = a.analyze(
        tree=tree, content=src.encode(),
        file_path="DynamicQueryService.java", pkg_name="com.x",
    )
    # 적어도 1개의 dynamic edge 가 있어야 함
    dynamics = [r for r in relations
                if r.target == "<dynamic>" and (r.attributes or {}).get("confidence") == 0.3]
    assert len(dynamics) == 1, (
        "Java 코드 안의 dynamic concat SQL 은 잘 marker 됨 (대조군). "
        "그런데 MyBatis XML <if> 는 같은 시나리오인데 0 marker."
    )


# ---------------------------------------------------------------------------
# 종합 — JpaAnalyzer 의 entity simple-name 스코프 누수
# ---------------------------------------------------------------------------
def test_jpa_analyzer_target_is_simple_entity_name_not_table() -> None:
    """결함 10 : JpaAnalyzer 의 target = entity simple name (예: "Slab"),
    실제 DB 테이블이 아닌 클래스 이름. @Table(name="SLAB_DESIGN_HIST_2024")
    같은 변환은 cross_file_enricher 에 위임. 그러나 entity 클래스가
    repo 안에 있어야만 enricher 가 잡는다.
    → 외부 모듈 (slab-design-store / facade) 에 entity 가 있고 다른 모듈에
       repository 만 있는 상황에서, 분리 빌드 시 enricher 가 못 잡을 수 있음.
    """
    src = """
package com.x;
import org.springframework.data.jpa.repository.JpaRepository;
public interface SlabRepository extends JpaRepository<Slab, String> {
    Slab findByOrderNo(String orderNo);
}
"""
    tree = _ts_parse(src)
    a = JpaAnalyzer()
    _, relations = a.analyze(
        tree=tree, content=src.encode(), file_path="SlabRepository.java",
        pkg_name="com.x",
    )
    reads = [r for r in relations if r.kind == RelationKinds.READS_TABLE]
    assert len(reads) == 1
    assert reads[0].target == "Slab", (
        "target 이 'Slab' 로 entity simple name. "
        "실제 테이블명 SLAB_HISTORY 같은 @Table override 는 별도 패스 필요. "
        "다른 모듈의 entity 면 enricher 도 못 잡을 수 있음 (결함)"
    )
    assert reads[0].attributes.get("target_kind") == "jpa_entity_simple_name", (
        "target_kind 가 'jpa_entity_simple_name' 으로 명시됨 — "
        "이 marker 가 다음 패스에서 정상적으로 resolve 안 되면 'Slab' 가 "
        "DB_TABLE 로 잘못 promoted 될 수 있다."
    )


__all__ = ()
