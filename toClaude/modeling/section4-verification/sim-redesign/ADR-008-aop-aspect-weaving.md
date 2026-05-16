# ADR-008: AOP (Aspect-Oriented Programming) Handling

작성일: 2026-05-13
상태: 확정 (사용자 D 선택 응답)
선행: ADR-001, ADR-002, ADR-006
관련: ADR-009 (Bytecode Generation — CGLib proxy 의 dominant case)

## 컨텍스트

Java AOP 의 cross-cutting concern:
- `@Aspect` class — aspect 정의
- `@Around` method — target method 의 전후 wrap
- `@Before` / `@After` / `@AfterThrowing` / `@AfterReturning`
- `@Pointcut` expression — target 식별 (`execution(* com.example..*Service.*(..))` 등)

Spring AOP 의 mechanism:
- Interface 기반 target: JDK dynamic proxy
- Concrete class target: CGLib bytecode generation
- 둘 다 target method call 을 intercept → advice 실행 → optional `proceed()`

Twin 환경: bytecode-level proxy 모방 불가. Advice 의 의도 (의미) 를 Python decorator 로 표현.

## 결정

Aspect 를 ontology 의 **별도 first-class entity** 로 모델 + Pointcut expression 의 정적 target expansion + 합성기의 Python decorator wrap.

### Ontology table (신규)

```sql
CREATE TABLE aspects (
    fqn                   VARCHAR NOT NULL,        -- "com.example.aspect.TimingAspect"
    advice_method_fqn     VARCHAR NOT NULL,        -- "TimingAspect.around"
    advice_kind           VARCHAR NOT NULL,        -- "around"|"before"|"after"|"afterThrowing"|"afterReturning"
    pointcut_expression   TEXT NOT NULL,           -- "execution(* SdDesigner.design(..))"
    pointcut_targets_json TEXT NOT NULL,           -- 정적 매칭된 target method_fqn[]
    order_priority        INTEGER,                 -- @Order(N), null 시 alphabetical
    aspect_args_json      TEXT NOT NULL DEFAULT '[]',  -- advice 의 추가 parameter
    source                VARCHAR NOT NULL,        -- "spring_aop"|"aspectj"|"manual"
    confirmed             BOOLEAN NOT NULL,
    repo_id               VARCHAR NOT NULL,
    revision_introduced   INTEGER NOT NULL,
    revision_obsoleted    INTEGER,
    PRIMARY KEY (advice_method_fqn, repo_id)
);
CREATE INDEX ix_aspects_repo_id ON aspects (repo_id);
CREATE INDEX ix_aspects_targets ON aspects (advice_method_fqn);
```

### Section 2 의 작업

1. AST scan 에서 `@Aspect` annotated class 식별
2. 각 advice method 의 annotation (`@Around` etc.) + pointcut expression 추출
3. Pointcut expression 의 정적 evaluation → target method 집합:
   - `execution(* Pkg..*Service.*(..))` → Pkg.*Service.* 의 모든 public method 매칭
   - `@annotation(com.example.Audited)` → @Audited 표시된 모든 method
   - `within(Foo)` → Foo class 의 모든 method
4. `aspects.pointcut_targets_json` 에 method_fqn 리스트 저장

### 합성기 (Layer 1 의 확장)

대상 method 합성 시 `aspects` table 조회 → wrapping advice 가 있으면 Python decorator 자동 적용. 여러 advice → @Order 또는 alphabetical 순으로 stack.

## 각 advice kind 의 Python 변환 패턴

### @Around (가장 일반)

```java
@Aspect
@Component
public class TimingAspect {
    private static final Logger log = LoggerFactory.getLogger(TimingAspect.class);

    @Around("execution(* SdDesigner.design(..))")
    public Object around(ProceedingJoinPoint pjp) throws Throwable {
        long start = System.currentTimeMillis();
        try {
            return pjp.proceed();
        } finally {
            long elapsed = System.currentTimeMillis() - start;
            log.info("design took {}ms", elapsed);
        }
    }
}
```

→ ontology row:
- advice_method_fqn = `TimingAspect.around`
- advice_kind = `around`
- pointcut_targets = `["SdDesigner.design(SDOrderEntity)"]`

→ 합성기 emit:

```python
# plugins/<sys>/aspects/timing.py (합성기 가 생성)
import functools
import time
import logging

log = logging.getLogger("TimingAspect")

def around_TimingAspect_around(proceed_fn):
    @functools.wraps(proceed_fn)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            return proceed_fn(*args, **kwargs)
        finally:
            elapsed_ms = (time.time() - start) * 1000
            log.info(f"design took {elapsed_ms}ms")
    return wrapper

# generated/<repo>/sd_designer.py 의 SdDesigner.design 에 자동 wrap
class SdDesigner:
    @around_TimingAspect_around
    def design(self, order: SDOrderEntity) -> SlabDesignResult:
        # 실제 design body
        ...
```

### @Before

```java
@Before("execution(* *Service.*(..))")
public void logEntry(JoinPoint jp) {
    log.debug("entering {}", jp.getSignature().toShortString());
}
```

→ Python:

```python
def before_LoggingAspect_logEntry(target_fn):
    @functools.wraps(target_fn)
    def wrapper(*args, **kwargs):
        log.debug(f"entering {target_fn.__qualname__}")
        return target_fn(*args, **kwargs)
    return wrapper
```

### @After / @AfterReturning / @AfterThrowing

```java
@After("execution(* *Service.*(..))")
public void cleanup() { ... }
```

→ Python try/finally wrap:

```python
def after_CleanupAspect_cleanup(target_fn):
    @functools.wraps(target_fn)
    def wrapper(*args, **kwargs):
        try:
            return target_fn(*args, **kwargs)
        finally:
            cleanup_impl()
    return wrapper
```

`@AfterReturning` 은 try 이후, `@AfterThrowing` 은 except 안.

### Multiple aspects on same target

```java
@Order(1) @Around(...) Foo
@Order(2) @Around(...) Bar
```

→ Python decorator stack (적용 순서는 outer → inner):

```python
@around_Foo  # @Order(1) — outermost
@around_Bar  # @Order(2) — innermost
def target():
    ...
```

@Order 부재 시 alphabetical (자동 결정).

## Pointcut expression 의 정적 분석

Section 2 가 다음 expression 지원:

| Expression | 의미 | 정적 매칭 |
|---|---|---|
| `execution(* Pkg..*Service.*(..))` | Pkg 의 모든 *Service class 의 모든 method | code_methods join code_types where package match |
| `@annotation(Auditable)` | @Auditable annotated method | code_methods.annotations 검색 |
| `within(Foo)` | Foo class 의 모든 method | code_methods where class_fqn = Foo |
| `target(Service+)` | Service subtype | code_types subtree |
| `args(String, Integer)` | 인자 type 으로 필터 | code_methods.params join |
| `bean(*Service)` | Spring bean name pattern | bean 정보 ontology (별도) |

복잡 expression (예: `@Around("@annotation(a) && args(x)") public void advice(Auditable a, String x)`) 의 일부는 SIGNATURE_LOCKED + 사용자 큐.

## v2 Reality

verified: v2 는 `@Aspect`, `@Around`, `@Before`, `@After` 모두 **0건**. 단 framework-internal AOP (Spring 의 `@Transactional` 의 CGLib proxy) 는 존재 — 이건 ADR-002 의 `@Transactional` stub 처리.

본 ADR 의 즉시 v2 작업 없음. **일반화 대상 system 이 custom aspect 사용하면 본 ADR mechanism 활성**.

## Honest Limits

- **Pointcut expression 의 full AspectJ grammar**: 모든 expression 의 정적 매칭은 불가능. 일반 expression 만 (execution/@annotation/within/target/args/bean). 미지원 expression → user queue + SIGNATURE_LOCKED
- **ProceedingJoinPoint 의 argument modification**: advice 가 `pjp.proceed(modifiedArgs)` 하면 Python wrapper 도 args 명시 manipulation 필요. 자동 추출 한계
- **Cross-aspect ordering ambiguity**: @Order 부재 + alphabetical 이 의도와 다른 경우 — 사용자가 명시
- **AspectJ compile-time weaving (CTW)**: bytecode level. Twin 은 source level 이므로 generated bytecode 미관찰. CTW 사용 시 weaving 전 source 만 처리 → 누락 가능. Plugin 별 weaving simulator 가 필요한 경우
- **Conditional advice**: `@Around("...&& if()")` 의 if() body 동적 — 일부 SIGNATURE_LOCKED
- **Aspects on private method**: Spring AOP 는 일반적으로 public method 만 — Python decorator 의 access 와 align 됨

## 결과

- AOP 가 ontology 의 first-class entity
- Section 2 의 aspect extractor (Java parser pass) 추가 작업
- 합성기의 Layer 1 emitter 가 target method 합성 시 자동 decorator wrap
- `@Transactional` 같은 spring-internal AOP 도 일관된 처리 (현 ADR-002 의 stub 과 통합 가능)
- v2 영향 zero
- 일반화: AOP 사용 system 의 cross-cutting 자동 흡수

## 참조

- ADR-002 (plugins/<sys>/)
- ADR-006 (Case 3 annotation dispatch — sibling)
- ADR-009 (Bytecode generation — CGLib proxy 는 본 ADR 의 dominant case)
- 사용자 D 선택 응답
