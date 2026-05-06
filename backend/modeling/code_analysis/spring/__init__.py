"""Spring-specific analyzer plug-ins for OD-11 Round 1.

B4 : Protocol + 6 스텁 클래스. 실제 구현은 B5 (Spring 8 난제 PoC).

- DIAnalyzer     : @Autowired / @Inject / 생성자 주입 → `AUTOWIRES` 엣지 + profile/condition 속성
- AopAnalyzer    : @Aspect / @Before / @Around → `aspect` 노드 + `INTERCEPTS` 엣지
- HttpAnalyzer   : @RestController / @RequestMapping → `http_endpoint` 노드 + `MAPS_URL` 엣지
- EventsAnalyzer : ApplicationEventPublisher / @EventListener → `event_type` 노드 + `PUBLISHES`/`HANDLES` 엣지
- ScheduledAnalyzer : @Scheduled → `scheduled_task` 노드
- ProfileAnalyzer : @Profile / @ConditionalOnProperty → 기존 엣지에 profile/condition 속성 주입
- ReflectionAnalyzer : Class.forName / getBean(name) / getMethod / Proxy.newProxyInstance → method.reflection_calls marker
- MapStructAnalyzer : `@Mapper` + `@Mapping(source,target/expression)` → PROPAGATES_TO / DERIVES_FROM (B6-1)
- BeanUtilsAnalyzer : `BeanUtils.copyProperties` / `ModelMapper.map` → METHOD attribute marker (B6-2)
- NativeSqlAnalyzer : `@Query` / `EntityManager` / `JdbcTemplate` SQL → READS_TABLE / WRITES_TABLE (B6-3)
"""

from __future__ import annotations

from .analyzer_protocol import SpringAnalyzer
from .aop_analyzer import AopAnalyzer
from .async_analyzer import AsyncAnalyzer
from .beanutils_analyzer import BeanUtilsAnalyzer
from .config_properties_analyzer import ConfigPropertiesAnalyzer
from .di_analyzer import DIAnalyzer
from .events_analyzer import EventsAnalyzer
from .http_analyzer import HttpAnalyzer
from .jpa_analyzer import JpaAnalyzer
from .mapstruct_analyzer import MapStructAnalyzer
from .mybatis_mapper_analyzer import MyBatisMapperAnalyzer
from .native_sql_analyzer import NativeSqlAnalyzer
from .profile_analyzer import ProfileAnalyzer
from .reflection_analyzer import ReflectionAnalyzer
from .scheduled_analyzer import ScheduledAnalyzer
from .transactional_analyzer import TransactionalAnalyzer

__all__ = (
    "SpringAnalyzer",
    "DIAnalyzer",
    "AopAnalyzer",
    "AsyncAnalyzer",
    "HttpAnalyzer",
    "EventsAnalyzer",
    "ScheduledAnalyzer",
    "ProfileAnalyzer",
    "ReflectionAnalyzer",
    "MapStructAnalyzer",
    "BeanUtilsAnalyzer",
    "MyBatisMapperAnalyzer",
    "NativeSqlAnalyzer",
    "ConfigPropertiesAnalyzer",
    "JpaAnalyzer",
    "TransactionalAnalyzer",
)
