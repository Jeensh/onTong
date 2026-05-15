# ADR-009: Bytecode Generation Handling

작성일: 2026-05-13
상태: 확정 (사용자 D 선택 응답)
선행: ADR-001, ADR-002, ADR-008
관련: ADR-006 (Reflection — sibling concern), ADR-007 (Annotation Processing)

## 컨텍스트

Java bytecode generation 의 주요 사례:

| 종류 | 사용처 | Twin 의 관심사 |
|---|---|---|
| Spring AOP CGLib proxy | `@Transactional`, concrete-class @Aspect | Production runtime |
| Spring DI CGLib (scope=request) | scoped bean lazy resolution | Production runtime |
| Hibernate lazy loading proxy | `@OneToMany(fetch=LAZY)` 등 | Production runtime |
| Mockito | test mock object 생성 | Test scope only |
| PowerMock | static method mocking | Test scope only |
| JaCoCo coverage instrumentation | bytecode 에 counter inject | Build/CI tool |
| Custom CGLib / ASM | domain-specific code gen | 임의 |

Twin 환경: bytecode 자체는 미관찰. Bytecode 의 효과 (생성된 method 의 의미) 만 Python 으로.

## 결정

각 source 별 strategy 분리:

| Source | Twin 의 대응 |
|---|---|
| **Spring AOP CGLib** | **ADR-008 의 Python decorator 로 대체** (bytecode 자체 무시, advice 의 의미만) |
| **Spring DI scoped CGLib** | Plugin/<sys>/stubs/spring_scope.py — request/session scope 의 시뮬레이션 (twin 환경에서 의미 좁음) |
| **Hibernate lazy proxy** | LookupDataSource adapter 가 **eager load** — twin 환경에서 lazy 의미 zero |
| **Mockito** | Twin 의 main code 만 처리 — test code 의 Mockito 무관. Python 의 `unittest.mock` 또는 `pytest fixtures` 직접 사용 |
| **PowerMock** | Twin 의 test 영역 아님. 무관 |
| **JaCoCo / coverage** | Twin 은 coverage 측정 대상 아님 (Java production code 의 coverage 는 별도 tool). 무관 |
| **Custom CGLib / ASM** | Plugin 별 작성 — `plugins/<sys>/bytecode_gens/<name>.py`. 없으면 SIGNATURE_LOCKED |

## 각 case 의 Python 변환 패턴

### Spring AOP CGLib (production)

ADR-008 와 통합. CGLib 의 bytecode mechanism 자체는 무시. Advice 의 의도만 Python decorator 로.

```java
// Spring AOP 가 SdDesigner 의 CGLib subclass 생성, design() override 하여 advice 호출
@Transactional
public SlabDesignResult design(SDOrderEntity order) { ... }
```

→ 합성기 emit (ADR-008 + ADR-002 의 @Transactional stub 통합):

```python
class SdDesigner:
    @transactional  # ADR-002 stub: session journal 시작
    @timing_around  # ADR-008 의 다른 advice
    def design(self, order):
        ...
```

CGLib 의 동적 subclass 생성은 Python 에서는 평범한 decorator chain.

### Hibernate Lazy Loading

```java
@Entity
class Order {
    @OneToMany(fetch = FetchType.LAZY)
    private List<Slab> slabs;
}

// 사용:
order.getSlabs().forEach(slab -> ...);  // → 이 시점에 SELECT * FROM slab WHERE order_id = ?
```

→ Twin: ontology 의 `schema_foreign_keys` + `schema_code_map` 가 관계 정보 보유 → LookupDataSource 가 fixture 의 모든 관련 row 를 미리 채워 옴 (eager):

```python
@dataclass
class Order:
    order_no: str
    slabs: list[Slab]  # fixture 가 직접 채움

# fixture 로딩 시:
order = Order(
    order_no="ORD001",
    slabs=lookup_data_source.find_all_by_fk("slab", "order_no", "ORD001"),
)
```

LAZY 의 의미는 production 의 SQL latency 최적화 — twin 의 행동 등가성에 무관. 모든 lazy → eager.

**Edge case**: lazy field 가 `n+1 query` 문제로 production 에서 큰 데이터 (예: order 의 모든 history) 인 경우 — twin 환경에서 fixture size 확장. R3 tolerance 의 영역.

### Mockito (testing)

Twin 의 production code 와 무관. Twin 검증 시 사용자가 작성하는 fixture 는 Python 의 mock 사용:

```python
# tests/test_twin.py
from unittest.mock import Mock
import pytest

@pytest.fixture
def mock_cast_spec_service():
    mock = Mock(spec=CastSpecService)
    mock.lookup.return_value = CastSpecEntity(slab_thickness=BigDecimal("230"))
    return mock

def test_thickness_action(mock_cast_spec_service):
    action = SdThicknessAction(mock_cast_spec_service, mock_plant_mapping)
    order = SDOrderEntity(...)
    slab = SDSlabEntity()
    action.execute(order, slab)
    assert slab.slab_thickness == BigDecimal("230")
```

Java 의 `Mockito.when(svc.lookup(any())).thenReturn(...)` 와 동등.

### Custom CGLib / ASM

사용자가 직접 `new Enhancer()` / `new ClassWriter()` 등으로 bytecode 생성. 예:

```java
Enhancer enhancer = new Enhancer();
enhancer.setSuperclass(MyService.class);
enhancer.setCallback(new MyInterceptor());
Object enhanced = enhancer.create();
```

→ Twin: ontology 의 정적 분석으로 enhancer 의 callback 의도 파악 불가. **SIGNATURE_LOCKED + plugin 권장**:

```python
# plugins/<sys>/bytecode_gens/my_enhancer.py (사용자 작성)
def emit_my_enhancer_equivalent(target_class):
    # 사용자가 enhancer 의 의도를 Python class 로 직접 작성
    class Enhanced(target_class):
        def some_method(self, *args, **kwargs):
            # interceptor 의 의도
            result = super().some_method(*args, **kwargs)
            ...
            return result
    return Enhanced
```

자동화 X, 사용자 manual.

## v2 Reality

verified: v2 는 직접 bytecode gen 없음 (`new Enhancer()` 등 zero). Spring AOP CGLib (@Transactional) 만 — ADR-002 의 stub + ADR-008 의 decorator 로 subsume.

Mockito 는 v2 test scope 에 사용 가능성 있음 — twin scope 외이므로 무관.

→ 본 ADR 의 즉시 v2 작업 없음. **일반화 대상 system 이 custom CGLib 사용하면 plugin 작성**.

## Honest Limits

- **Spring AOP CGLib 의 `private` method advice**: Spring AOP 는 일반적으로 public 만 — 단 AspectJ load-time weaving (LTW) 은 private 도 가능. Twin 의 Python decorator 는 access 와 align 되므로 private 의 LTW 는 미지원
- **Hibernate proxy 의 identity 보존**: Java 에서 lazy proxy 가 unwrapped entity 와 `.equals()` true. Python eager 의 경우 identity 일치 — 차이 없음 (행동 동등)
- **Bytecode-level instrumentation** (예: JaCoCo coverage, profiling agent): Twin 의 Python 은 별도 coverage tool 사용 (coverage.py). Java side 와 measurement 불일치 — 단 twin 의 본 목적 (R3/R4 검증) 과 무관
- **Custom CGLib 의 자동 추출**: ASM-level analysis 없이는 enhancer 의 callback 의도를 정적 추출 불가. 사용자 plugin 의존
- **JIT 의 영향**: Java JIT (escape analysis, inlining) 의 결과로 production 의 일부 수치 precision 이 source-level 과 다를 수 있음 — R3 tolerance 의 별도 한계 (twin 의 Python 이 Java JIT 결과 추적 불가)

## 결과

- 대부분의 bytecode gen 효과는 ADR-006-008 으로 subsume
- Spring AOP CGLib, Hibernate lazy → 자동 처리 (decorator + eager load)
- Mockito 등 test 영역 → twin scope 외, 무관
- Custom CGLib 만 plugin 작성 + SIGNATURE_LOCKED fallback
- v2 영향 zero
- 일반화: bytecode gen 효과의 분류 → 각 분류별 strategy 명확

## 참조

- ADR-002 (plugins/<sys>/stubs/)
- ADR-008 (AOP — CGLib proxy 의 dominant case)
- ADR-006 (sibling: 다른 meta-programming 분류)
- 사용자 D 선택 응답
