# BROADLEAF-ONBOARDING — Broadleaf Commerce Community 의 onboarding path

작성일: 2026-05-13 (implementation plan session)
관련 ADR: ADR-002 (Two-Engine + plugin), ADR-011 (3 systems), ADR-013 (Extensibility)
Track 위치: Track B Phase B3 (W4-W10) — MILESTONES-2track.md §2
Plugin 위치: `backend/sim_v2/plugins/broadleaf/`
Cost estimate: 300-400h (ADR-011 §4) — Codebase 학습 100h + Plugin 작성 200-300h

---

## 0. TL;DR

Broadleaf Commerce community edition v6.x 의 plugin onboarding.

**핵심 제약:**
- Real-world OSS legacy — Spring DI / JPA / @Aspect / CGLib proxy / @Configurable 의 production-grade meta-programming stress test
- ~200K+ LOC 전체 X — **core + cart + order + pricing + offer 약 80-100K** 의 core path 우선
- Enterprise-only feature (dynamic field, sandbox, workflow override) → SIGNATURE_LOCKED + extension path (M-D4)
- 예상 extension (ADR-013): `broadleaf.configurable_handler`, `broadleaf.data_driven`, `broadleaf.dynamic_field`

---

## 1. Broadleaf 소개 + module 구조

### 1.1 Codebase 개요

| 항목 | 값 |
|---|---|
| Edition | Broadleaf Commerce community |
| Version | v6.x (LTS, stable Spring Boot 2.x base) |
| LOC | ~200K+ Java |
| Build | Maven multi-module |
| License | Apache 2.0 (community) / commercial (enterprise) |
| Repository | github.com/BroadleafCommerce/BroadleafCommerce |

### 1.2 Module 분할 (community)

```
BroadleafCommerce/
├── common/                      # 공통 utility, base types
├── core/                        # 도메인 core (catalog, order, pricing, offer)
├── profile/                     # Customer profile + address
├── admin/                       # Admin UI + open-admin-platform
├── cms/                         # Content management
├── framework/                   # Spring config, AOP weaving
├── workflow/                    # Activity-based workflow framework
└── integration/                 # 3rd-party (payment gateway, search)
```

### 1.3 본 plugin 의 scope (community v6.x)

| Module | 포함? | Onboarding 우선순위 |
|---|---|---|
| common | ✓ | W4 — base types, BLC custom DAO pattern |
| core (catalog) | ✓ | W4-W5 |
| core (order) | ✓ | W5-W6 — 가장 entity 많음 |
| core (pricing) | ✓ | W6-W7 |
| core (offer) | ✓ | W7-W8 |
| profile | ✓ | W7-W8 |
| framework | ✓ | W4-W5 (Spring AOP 의 weaving 정의) |
| admin | ✗ | SIGNATURE_LOCKED — admin UI 가 plugin scope 외 |
| cms | ✗ | SIGNATURE_LOCKED |
| workflow | ✗ | SIGNATURE_LOCKED — phase 2 가능 |
| integration | ✗ | SIGNATURE_LOCKED — 3rd-party gateway plugin extension 가능 |

**총 scope: ~80-100K LOC** (전체 200K 중 약 40-50%).

---

## 2. Onboarding cost 분해 (ADR-011 §4)

| Sub-task | Cost | 산출물 |
|---|---|---|
| Codebase 학습 (read-through, structure understanding) | 100h | `backend/sim_v2/plugins/broadleaf/docs/CODEBASE-NOTES.md` |
| Plugin 7 artifact 작성 | 200-300h | `backend/sim_v2/plugins/broadleaf/` 전체 |
| **Total** | **300-400h** | per ADR-011 |

3인 팀 기준 분담:
- Lead: codebase 학습 + plugin contract / manifest 작성 (W4-W5)
- Member A: entities / mappings (W5-W6)
- Member B: emitters / fixtures (W6-W8)
- 통합 + aspects: 3인 (W8-W10)

---

## 3. Critical entity classes — 우선 mapping 대상

### 3.1 Order module (core/order/)

```
org.broadleafcommerce.core.order.domain
├── Order                       # 최상위 aggregate root
├── OrderImpl                   # JPA implementation
├── OrderItem                   # Order 의 line item
├── DiscreteOrderItem           # Concrete product item
├── BundleOrderItem             # Composite item
├── OrderAttribute              # K-V extension point
├── FulfillmentGroup            # Shipping group
├── FulfillmentGroupItem        # Group 의 line item
└── PriceData                   # Pricing snapshot
```

### 3.2 Catalog module (core/catalog/)

```
org.broadleafcommerce.core.catalog.domain
├── Product                     # 제품
├── Sku                         # 변형 (size/color)
├── Category                    # 카테고리 (n-ary tree)
├── ProductAttribute            # K-V extension
├── ProductOption               # 변형 option
└── ProductOptionValue          # option 의 value
```

### 3.3 Pricing module (core/pricing/)

```
org.broadleafcommerce.core.pricing
├── PricingService              # Pricing 진입점
├── PricingWorkflow             # 단계별 pricing (activity-based)
├── ShippingPricingActivity     # Activity 의 sub-class
└── TaxActivity                 # Tax activity
```

### 3.4 Offer module (core/offer/)

```
org.broadleafcommerce.core.offer.domain
├── Offer                       # 할인 정의
├── OfferCode                   # 쿠폰 코드
├── OfferRule                   # MVEL rule (dynamic)
├── OrderItemOffer              # Order item 의 적용된 offer
└── FulfillmentGroupOffer
```

**중요**: `OfferRule.matchRule` = MVEL expression — runtime evaluated. ADR-009 (bytecode generation) 와 관련, MVEL interpreter 의 emitter 또는 SIGNATURE_LOCKED.

### 3.5 Profile module (profile/)

```
org.broadleafcommerce.profile.core.domain
├── Customer                    # 고객
├── CustomerAddress             # 주소
└── CustomerAttribute           # K-V extension
```

---

## 4. Meta-programming 영역 의 specifics

### 4.1 Spring AOP @Configurable on JPA entities

Broadleaf 의 핵심 패턴 — JPA entity 가 Spring DI receive:

```java
@Entity
@Configurable(autowire = Autowire.BY_TYPE)
public class OrderImpl implements Order {
    @Transient
    @Autowired(required = false)
    protected OrderService orderService;  // ← JPA load 후 Spring 이 inject
    
    // ... entity logic 가 OrderService 호출
}
```

**문제 (Python twin 합성 시점):**
- JPA entity 가 Spring DI 받음 → entity behavior 가 lazy injected service 에 의존
- ADR-008 (AOP / @Aspect weaving) 의 적용 범위
- Plugin extension 필요: `broadleaf.configurable_handler`

**SIGNATURE_LOCKED + extension path:**
- Default: synthesizer 가 @Configurable entity 발견 시 inject 된 field 의 lazy initialization 처리 모름 → SIGNATURE_LOCKED
- Extension: `backend/sim_v2/plugins/broadleaf/aop/configurable_handler.py` 가 @Configurable entity 의 @Autowired field 를 plugin contract 의 service registry 에서 lookup

### 4.2 BLC 의 polymorphic Configurable factory

Broadleaf 의 BLC 의 factory pattern — interface → concrete class 의 runtime selection:

```java
// 사용자 코드에서
Order order = blcFactory.create(Order.class);
// → 내부적으로 OrderImpl, ConcreteCustomOrderImpl 등 중 runtime selection
```

ADR-006 의 8 dispatch_kind 중 어떤 것? — `factory_dispatch` 또는 새 plugin extension.

### 4.3 @AdminPresentation 의 annotation processor

```java
@AdminPresentation(friendlyName = "Order Status", order = 1000, group = "General")
@Column(name = "STATUS")
protected String status;
```

`@AdminPresentation` 은 admin UI 메타데이터 — twin 의 algorithm 에는 영향 X. Plugin scope 외 — synthesizer 가 무시.

단 일부 BLC entity 의 사용자 정의 annotation 는 algorithm 영향 (e.g., `@MergeAnnotations`, `@OverrideEntityAnnotations`) — ADR-007 의 annotation processing 적용.

### 4.4 MVEL expression in OfferRule

```java
public class OfferRule {
    protected String matchRule;  // MVEL expression, e.g., "order.subTotal.amount > 100"
    
    public boolean evaluateRule(Order order) {
        // MVEL.eval(matchRule, vars) — runtime evaluated
    }
}
```

**Python twin 시점**:
- MVEL = Java expression language, Python equivalent 없음
- Option A: Plugin extension 로 MVEL emulator (mvel-python? 부재) → SIGNATURE_LOCKED
- Option B: OfferRule.matchRule 의 specific instance 가 fixture 에 있는 경우, Python 으로 transpile (rule 별로 hand-craft)

추천: **default SIGNATURE_LOCKED + plugin extension path** (Plugin 작성 시 specific rule 의 fixture 작성 + emitter override).

### 4.5 BLC dynamic entity DAO 의 CGLib proxy

Broadleaf 의 DynamicEntityDao — runtime 에 CGLib proxy 로 entity behavior 변경:

```java
// Spring config 으로 등록된 dynamic proxy
@Service
public class DynamicEntityDao {
    public <T> T retrieve(Class<T> entityClass, Object id) {
        Object proxy = createCglibProxy(entityClass);
        // proxy 가 lazy-load behavior 추가
    }
}
```

ADR-009 (bytecode generation) 의 CGLib pattern 적용. Plugin extension: `broadleaf.dynamic_entity_dao_proxy`.

---

## 5. Plugin 의 7 artifact 작성 절차 (W4-W10 sprint)

### W4-W5 — Codebase 학습 + manifest + contract (Artifact 1, 7)

#### 5.1 `manifest.toml` (Artifact 7)

```toml
[plugin]
name = "broadleaf"
version = "0.1.0"
description = "Broadleaf Commerce community v6.x plugin"

[recommendation]
default_provider = "claude"
default_model = "claude-opus-4-7"
allowed_providers = ["claude", "openai", "gemini"]
max_retries = 3

[extensions]
dispatchers = ["broadleaf.factory_dispatch", "broadleaf.dynamic_proxy_dispatch"]
annotations = ["broadleaf.merge_annotations", "broadleaf.override_entity"]
aop = ["broadleaf.configurable_handler", "broadleaf.dynamic_field"]
bytecode = ["broadleaf.dynamic_entity_dao_proxy"]

[schema]
source = "jpa_annotation"
ignore_modules = ["admin", "cms", "workflow", "integration"]

[fixtures]
ids = ["B1", "B2", "B3", "B4", "B5"]

[contracts]
domain_exception_base = "BroadleafException"
numeric_convention = "ecommerce_2decimal"
```

#### 5.2 `contracts/base.py` (Artifact 1)

```python
# backend/sim_v2/plugins/broadleaf/contracts/base.py

from core.contracts.base import JavaContract
from core.contracts.numeric_base import RoundingMode

from .exception import BroadleafException
from .domain_namespace import BLCConstants


class BroadleafContract(JavaContract):
    """Broadleaf Commerce community plugin contract."""
    exception_base = BroadleafException

    def domain_namespace(self) -> dict:
        return {
            "BLCConstants": BLCConstants,
            "OrderStatus": OrderStatus,
            "FulfillmentType": FulfillmentType,
        }

    def numeric_convention(self) -> NumericConvention:
        return NumericConvention(
            bigdecimal_precision=10,
            bigdecimal_rounding=RoundingMode.HALF_UP,
            domain_scales={
                "money.amount": 2,        # USD, EUR, GBP 등 minor unit
                "weight.kg": 3,
                "quantity": 0,            # 정수 quantity
                "tax.rate": 5,
            },
        )
```

### W5-W6 — Entities + Mappings (Artifact 2, 3)

```python
# backend/sim_v2/plugins/broadleaf/entities/__init__.py

from core.synthesizer.java_ast import extract_entities

ENTITIES = extract_entities(
    java_source_root=Path("sample-repos/BroadleafCommerce/"),
    package_filter=[
        "org.broadleafcommerce.common.*",
        "org.broadleafcommerce.core.catalog.*",
        "org.broadleafcommerce.core.order.*",
        "org.broadleafcommerce.core.pricing.*",
        "org.broadleafcommerce.core.offer.*",
        "org.broadleafcommerce.profile.*",
        "org.broadleafcommerce.framework.*",
    ],
    exclude_filter=[
        "org.broadleafcommerce.admin.*",
        "org.broadleafcommerce.cms.*",
        "org.broadleafcommerce.workflow.*",
    ],
)
```

추정 entity count: ~300-500 classes (200K LOC scope 의 약 0.2% entity 비율). v2 의 128 entity 대비 ~3배.

Mapping import (Section 2 ontology):
- 추정 mapping count: 1000+ method anchor
- Manual confirm 의 anchor-gaps Gap C 유사 risk — 일부 type 의 confidence < 1.0

### W6-W8 — Emitters + Fixtures (Artifact 4, 5)

#### 5.3 `emitters/`

```python
# backend/sim_v2/plugins/broadleaf/emitters/__init__.py

from core.synthesizer.emitters import (
    BodyComputeEmitter,
    BodySetOutputEmitter,
    BodyBranchEmitter,
    BodyLoopEmitter,
    BodyServiceLookupEmitter,
    BodyRepositoryCallEmitter,
    # ... 17 generic emitters
)

from .blc_factory_dispatch import BLCFactoryDispatchEmitter
from .configurable_jpa_entity import ConfigurableJPAEntityEmitter
from .mvel_offer_rule import MVELOfferRuleEmitter
from .dynamic_entity_dao import DynamicEntityDaoEmitter

EMITTERS = {
    # generic emitters
    "body.compute": BodyComputeEmitter(),
    # ... 17 generic
    
    # plugin-specific
    "broadleaf.factory_dispatch": BLCFactoryDispatchEmitter(),
    "broadleaf.configurable_entity": ConfigurableJPAEntityEmitter(),
    "broadleaf.mvel_offer_rule": MVELOfferRuleEmitter(),
    "broadleaf.dynamic_entity_dao": DynamicEntityDaoEmitter(),
}
```

#### 5.4 `fixtures/` — 5 scenario

| Fixture | 도메인 시나리오 | Meta-programming 의도 cover |
|---|---|---|
| B1 | 단순 주문 (1 item, no offer, no shipping) | Spring DI on JPA entity (@Configurable) |
| B2 | 다중 item + offer 적용 | OfferRule MVEL expression (SIGNATURE_LOCKED + manual emit) |
| B3 | Bundle item + Sku 변형 | BLC factory dispatch (polymorphic 9th case) |
| B4 | Pricing workflow (activity-based) | Workflow activity chain (sequential dispatch) |
| B5 | Fulfillment group + tax 계산 | DynamicEntityDao CGLib proxy (bytecode) |

5 fixture 가 4 meta-programming 영역 (ADR-006/007/008/009) 모두 cover — G2 gate 의 Broadleaf 입력.

### W8-W10 — Aspects + 통합 검증 (Artifact 6)

```python
# backend/sim_v2/plugins/broadleaf/aspects/configurable_handler.py

from core.synthesizer.aspects import AspectBase

class ConfigurableJPAEntityAspect(AspectBase):
    """@Configurable JPA entity 의 @Autowired field 처리.
    
    Lazy-injected service 를 plugin contract 의 service registry 에서 lookup.
    """
    def weave(self, entity_ast: JavaAST) -> JavaAST:
        # 1. @Configurable annotation 탐지
        # 2. @Autowired field 추출
        # 3. service registry lookup 코드 inject
        ...
```

---

## 6. SIGNATURE_LOCKED 후보 + plugin extension list (ADR-013 §6)

### 6.1 명시적 SIGNATURE_LOCKED

| 영역 | 사유 | 처리 |
|---|---|---|
| Admin module | UI scope 외 | 무시 (SIGNATURE_LOCKED + 사용자 review 필요 없음) |
| CMS module | content scope 외 | 무시 |
| Workflow module | activity DSL — phase 2 후보 | SIGNATURE_LOCKED + extension path 명시 |
| Integration (3rd-party payment) | external API — fixture 의 mock | SIGNATURE_LOCKED + plugin extension 가능 |

### 6.2 Plugin extension 후보 (G4 gate, W12-W20)

| Extension | 위치 | 적용 패턴 |
|---|---|---|
| `broadleaf.factory_dispatch` | `backend/sim_v2/plugins/broadleaf/dispatchers/` | BLC factory 의 runtime concrete class selection |
| `broadleaf.configurable_handler` | `backend/sim_v2/plugins/broadleaf/aop/` | @Configurable JPA entity 의 @Autowired field handling |
| `broadleaf.data_driven` | `backend/sim_v2/plugins/broadleaf/annotations/` | Custom annotation processor (data-driven entity merging) |
| `broadleaf.dynamic_field` | `backend/sim_v2/plugins/broadleaf/aop/` | Dynamic field injection (admin-driven entity extension, enterprise 만 — community 에서는 minimal) |
| `broadleaf.dynamic_entity_dao_proxy` | `backend/sim_v2/plugins/broadleaf/bytecode/` | DynamicEntityDao CGLib proxy |
| `broadleaf.mvel_offer_rule` | `backend/sim_v2/plugins/broadleaf/extensions/` (escape hatch — RATIONALE.md 의무) | MVEL expression for OfferRule.matchRule |

---

## 7. Boundary 결정 — Enterprise vs community

### 7.1 Community-only 의 의미

- v6.x community edition 의 source 만 (github.com/BroadleafCommerce/BroadleafCommerce)
- Enterprise extension (BLC enterprise — sandbox / dynamic field admin / workflow override) 폐기
- 단 community 가 enterprise 의 hook (e.g., `EnterpriseExtensionHandler` interface) 정의 — interface 는 plugin contract 에 포함, implementation 만 SIGNATURE_LOCKED

### 7.2 Why community + enterprise 분리

ADR-011 §3 의 "Broadleaf enterprise-only feature 결손 — Low impact":
- Community 가 enough complex (200K+ LOC) — universality stress test 가 enough
- Enterprise feature 가 framework 의 limit boundary 명시 (M-D4 의 SIGNATURE_LOCKED) 의 test case

### 7.3 Enterprise 의 plugin extension upgrade path (phase 2)

Phase 1 종료 후:
- Enterprise 사용 시 BLC enterprise 의 source 추가 — `backend/sim_v2/plugins/broadleaf-enterprise/` separate plugin
- 또는 `backend/sim_v2/plugins/broadleaf/extensions/enterprise-*.py` plugin extension (RATIONALE.md 의무)

---

## 8. Risk + contingency

| Risk | Impact | Mitigation |
|---|---|---|
| 200K+ LOC 의 codebase 학습 100h 부족 | High | 80-100K scope 으로 boundary 명확. Lead 가 W4-W5 에 priority entity 만 학습 후 W6-W8 에 sub-domain 분담 |
| @Configurable JPA entity 의 Python twin 합성 trap | High | W4 에 ConfigurableJPAEntityAspect prototype 작성. Plugin extension `broadleaf.configurable_handler` 의 W8 까지 완성 |
| MVEL expression 의 Python emulator 부재 | Medium | SIGNATURE_LOCKED + B2 fixture 의 specific MVEL rule 만 manual emit. Phase 2 에 MVEL-py 검토 |
| BLC factory dispatch 의 9번째 dispatch_kind | Medium | ADR-006 의 8 dispatch_kind 외 9번째 → Plugin extension `broadleaf.factory_dispatch`. ADR-013 의 promotion path 후보 (다른 plugin 에서도 등장 시 core 흡수) |
| Spring AOP CGLib proxy 의 합성 복잡도 | High | ADR-009 의 CGLib pattern 의 baseline 적용. Plugin extension `broadleaf.dynamic_entity_dao_proxy` |
| 사람의 BLC 사전 지식 0 시 학습 cost 증가 | Medium | Lead 가 BLC official docs (docs.broadleafcommerce.com/v6.x) + ROOT-LEVEL README 우선 학습. 100h cost 안에 충분 |
| Sample-repos 의 BLC source 의 build 의존성 | Low | `sample-repos/BroadleafCommerce/` 의 mvn dependency:tree 로 확인. JDK 11+ + Maven 3.6+ |

---

## 9. Acceptance criteria (G1 gate, W10)

- 7 artifact 모두 작성 완료
- Entity import: ~300-500 entity (community v6.x scope)
- Mapping confirmed_rate >= 90%
- 5 fixture (B1-B5) pytest PASS
- Anti-pattern 0 hit (KNOWN_DIVERGENCE 5 재발 없음 — Lesson 1)
- Plugin extensions 명시: 5-6개 (dispatchers / annotations / aop / bytecode)
- Boundary 명시: community-only, admin/cms/workflow/integration SIGNATURE_LOCKED

---

## 10. 참조

### ADRs
- ADR-002 (plugin contract) — 7 artifact 의 source
- ADR-006 (polymorphic dispatch) — BLC factory dispatch
- ADR-008 (AOP / @Aspect) — @Configurable JPA entity
- ADR-009 (bytecode) — DynamicEntityDao CGLib proxy
- ADR-011 (3 systems) — cost 300-400h estimate
- ADR-013 (extensibility) — plugin extension 5-6개

### External references
- github.com/BroadleafCommerce/BroadleafCommerce (community v6.x)
- docs.broadleafcommerce.com/v6.x (official docs)
- BLC framework 의 @Configurable + AspectJ weaving 패턴

### Related plan artifacts
- `BANKING-DESIGN.md` — Banking 가상 system (sibling plugin)
- `V2-MIGRATION.md` — v2 plugin onboarding (sibling)
- `implementation-plan.md` — Track B Phase B3 의 본 onboarding 의 sprint task
- `lessons/phase-alpha-*.md` — 5 lessons (사전 학습)

### 메모리
- `feedback_simulation_design.md` — no MVP, 풀 시연 필수
