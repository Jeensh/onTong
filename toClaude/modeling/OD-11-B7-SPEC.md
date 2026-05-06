# OD-11-B7 Reflection 런타임 collector + 리터럴 해소 — 확정 스펙

**날짜**: 2026-04-19
**브랜치**: main
**근거**: `toClaude/modeling/OD-11-B7-decisions.html` (Q1~Q3) + 세션 내 Q4 추가 (리터럴 해소 주체)
**선행**: OD-11-B6 (4/4 완료 — 10 analyzer + `CrossFileEnricher`)
**후속**: OD-11-B8 Impact/BFS hops API → B9 Slab 엔진 E2E (사용자 sample repo 수령 대기)

---

## 0. 설계 원칙

1. **리터럴은 정적 해소, 동적은 런타임 해소** — `getBean("foo")` / `Class.forName("com.acme.Foo")` 같은 string literal 인자는 런타임 필요 없음. 변수·concat·type-based 만 런타임 trace 로 보강.
2. **Coexist 3-way** — 정적 확정 / 정적 미해소 / 런타임 확인 세 종류 엣지를 `source` 속성으로 구분해 그래프에 공존. Impact Analysis 쿼리 레벨 스위치.
3. **Protocol + DTO 우선, Agent 는 후순위** — JVM Agent 실제 구현은 B9 Slab sample 수령 후 임시 섹션에서. B7 은 파이프라인 인터페이스만 고정.
4. **하위 호환 marker 확장** — B5-8 의 `reflection_calls` 엔트리에 `arg_kind` 필드만 추가. 기존 `api`/`arg`/`line` 유지.
5. **CrossFileEnricher 패턴 재사용** — literal resolver 와 runtime collector 모두 "analyzer 가 marker 를 남기고 repo-level 후처리가 엣지 emit" 구조. synthetic `ParseResult(file_path=...)` 로 runtime trace 주입.

---

## 1. 서브 phase 구성

| Sub-step | 작업 | 위치 | LOC 추정 | 출력 |
|----------|------|------|---------|------|
| **B7-0** | `ReflectionAnalyzer` 확장 — `arg_kind` 필드 추가 | `backend/modeling/code_analysis/spring/reflection_analyzer.py` | ~30 delta | `reflection_calls[*]` 에 `arg_kind: "literal" \| "variable" \| "concat" \| "type" \| "other"` |
| **B7-1** | `reflection_literal_resolver.py` | `backend/modeling/code_analysis/reflection_literal_resolver.py` | ~200 | `CALLS{source: "static_literal", confidence: 0.9}` 또는 `CALLS{source: "static_unresolved", confidence: 0.4}` |
| **B7-2** | `runtime_collector.py` — Protocol + DTO | `backend/modeling/code_analysis/runtime_collector.py` | ~220 | `CALLS{source: "runtime", confidence: 0.95}` + `REFLECTS_AS` 엣지, synthetic `ParseResult(file_path="<runtime>")` |

각 서브스텝마다 TDD red → impl → 7-item docs sync.

---

## 2. 배경

### 2.1 B5-8 현재 상태

B5-8 `ReflectionAnalyzer` 는 다음 API 정적 감지 완료 (20/20 pass):
- `Class.forName(...)`
- `Proxy.newProxyInstance(...)`
- `ctx.getBean("..." | class | variable)`
- `clazz.getMethod` / `getDeclaredMethod` / `getField` / `getDeclaredField`

감지 결과는 `METHOD.attributes["reflection_calls"] = [{api, arg, line}, ...]` 로 저장.

**현재 한계**: `arg` 가 문자열 리터럴인지 변수 이름인지 concat 식인지 구분하지 않음 → 다운스트림이 재판정해야 함.

### 2.2 3 단계 해소 스펙트럼

| 케이스 | 예시 | 해소 주체 | 엣지 confidence |
|---|---|---|---|
| **리터럴** | `ctx.getBean("fooShipper")` | B7-1 static resolver | 0.9 |
| **부분 정적** | `Class.forName("com.acme." + name)` | B7-1 (prefix 매칭 후보) | 0.6 |
| **변수 / type** | `ctx.getBean(name)` / `ctx.getBean(Shipper.class)` | B7-2 runtime | 0.95 (trace 도착 시) |
| **미해소** | 위 케이스에 런타임 없을 때 | B7-1 default | 0.4 (경고 엣지) |

### 2.3 Coexist 3-way 흐름도

```
┌────────────────────────┐    ┌────────────────────────┐
│ B5-8 정적 marker        │    │ B7-2 런타임 trace       │
│ reflection_calls[]      │    │ (JVM Agent / JSON 파일) │
└──────────┬─────────────┘    └──────────┬─────────────┘
           │                              │
           ↓                              ↓
┌────────────────────────┐    ┌────────────────────────┐
│ B7-1 literal resolver   │    │ B7-2 runtime collector  │
│ → static_literal (0.9)  │    │ → runtime (0.95)        │
│ → static_unresolved(0.4)│    │ → REFLECTS_AS           │
└──────────┬─────────────┘    └──────────┬─────────────┘
           │                              │
           └──────────┬───────────────────┘
                      ↓
           Neo4j graph (CALLS{source, confidence, ...})
```

---

## 3. 결정 사항

### Q1. B7 sub-spec 문서화 범위 → **A 채택**

- **A** ✅ : B7-SPEC (이 문서) 먼저 승인, 이후 B7-0/1/2 TDD.
- B : SPEC 없이 바로 TDD 진입.

**이유**: B6 에서 검증된 패턴. Q2·Q3·Q4 결정을 코드 대신 문서에 박제해 다음 세션 재합의 비용 제거.

### Q2. 정적 marker × 런타임 trace 병합 규칙 → **B 채택 (Coexist 3-way)**

- A : Replace — 런타임 trace 가 정적을 덮어씀. 정적 흔적 소실.
- **B** ✅ : Coexist — `source` 속성으로 3-way 분리 (`static_literal` / `static_unresolved` / `runtime`). 엣지 공존.
- C : Merge — 단일 엣지에 `sources[]` + weighted confidence. MERGE 로직 복잡.

**이유**:
1. Impact Analysis 쿼리 레벨 스위치 가능 — "관측된 경로만" / "잠재 경로까지" 를 `source IN (...)` 으로 선택.
2. 정적은 넓게 잡고 (미사용 코드 포함), 런타임은 좁게 잡음 (실제 실행). 서로 보완적.
3. 엣지 수 증가는 뷰어단 필터로 해결 (graph_writer 는 그대로).

### Q3. JVM Agent 범위 → **A 채택**

- **A** ✅ : B7-2 는 Protocol + DTO + 합성 fixture 만. 실제 JVM Agent 는 B9 Slab 수령 후 임시 섹션에서.
- B : +로컬 JSON trace CLI (손수 작성한 fixture 로 E2E 돌려봄).
- C : JVM Agent 까지 B7 에서 — ByteBuddy / manifest / shading 포함.

**이유**: Slab repo 구조를 모르는 상태에서 Agent instrumentation 포인트 추측으로 박제하면 재작업 위험. Protocol 먼저 고정하고 Agent 는 실제 데이터 보고 결정.

### Q4. 리터럴 해소 주체 → **B 채택 (별도 모듈)**

- A : B5-8 확장 — `ReflectionAnalyzer` 내부에서 class_index 매칭까지.
- **B** ✅ : `reflection_literal_resolver.py` 별도 모듈 (B7-1). marker 는 B5-8, 엣지 emit 은 후처리에서.
- C : B7-2 `runtime_collector` 가 리터럴·런타임 둘 다 소화.

**이유**: CrossFileEnricher 에서 수렴한 "analyzer marker → repo-level 후처리 엣지 emit" 패턴과 동일. per-file analyzer 가 repo-wide class_index 에 접근하지 않는다는 원칙 유지.

---

## 4. B7-0 상세 — `ReflectionAnalyzer` arg_kind 필드

### 4.1 Marker 스키마 확장

**Before (B5-8 현재)**:
```python
method_entity.attributes["reflection_calls"] = [
    {"api": "ApplicationContext.getBean", "arg": "fooShipper", "line": 15},
    {"api": "Class.forName",              "arg": "className",  "line": 42},
]
```

**After (B7-0)**:
```python
method_entity.attributes["reflection_calls"] = [
    {"api": "ApplicationContext.getBean", "arg": "fooShipper", "arg_kind": "literal",  "line": 15},
    {"api": "Class.forName",              "arg": "className",  "arg_kind": "variable", "line": 42},
    {"api": "Class.forName",              "arg": "com.acme. + name", "arg_kind": "concat",   "line": 58},
    {"api": "ApplicationContext.getBean", "arg": "Shipper",    "arg_kind": "type",     "line": 71},
]
```

### 4.2 arg_kind 분류 규칙

AST 노드 타입별 매핑:

| tree-sitter Java 노드 | arg_kind | 예시 |
|---|---|---|
| `string_literal` | `literal` | `"fooShipper"` |
| `identifier` | `variable` | `shipperName` |
| `binary_expression` (op `+`) | `concat` | `"prefix" + name` |
| `method_invocation` | `other` | `resolveBeanName(order)` |
| `class_literal` (`Foo.class`) | `type` | `Shipper.class` |
| `field_access`, 기타 | `other` | `this.beanName` |

`arg` 값은 기존 그대로 보존 (literal 은 unquote, 그 외는 source text). backward compat 유지.

### 4.3 테스트 추가

`tests/test_spring_reflection_analyzer.py` 에 기존 20 cases 각각 `arg_kind` 검증 assertion 추가 + 신규 4 cases:
1. `ctx.getBean("literal")` → `arg_kind: literal`
2. `ctx.getBean(variableName)` → `arg_kind: variable`
3. `Class.forName("com.acme." + suffix)` → `arg_kind: concat`
4. `ctx.getBean(Shipper.class)` → `arg_kind: type`

**회귀 목표**: Spring 7-analyzer 143/143 유지 + 4 신규 pass.

---

## 5. B7-1 상세 — `reflection_literal_resolver.py`

### 5.1 API

```python
def resolve_reflection_literals(
    parse_results: list[ParseResult],
    class_index: dict[str, CodeEntity],
    bean_index: dict[str, CodeEntity],  # bean_name → CLASS entity
) -> list[ParseResult]:
    """In-place: appends CALLS/REFLECTS_AS edges for literal-arg reflection calls.
    - arg_kind=="literal" + class_index match → CALLS{source:static_literal, confidence:0.9}
    - arg_kind=="literal" + no match         → CALLS{source:static_unresolved, confidence:0.4}
    - arg_kind in (variable/concat/type/other) → skip (B7-2 런타임 대상)
    Returns the same parse_results list.
    """
```

### 5.2 bean_index 구축

`build_bean_index(parse_results)` 헬퍼:
1. `@Component("name")` / `@Service("name")` / `@Repository("name")` / `@Controller("name")` / `@RestController("name")` → explicit name
2. `@Bean(name="...")` / `@Bean` (메서드명) → bean name
3. Explicit name 없으면 class simple name → camelCase (`OrderService` → `orderService`)

### 5.3 리터럴 해소 규칙 per API

| API | literal arg 해석 | 매칭 대상 |
|---|---|---|
| `Class.forName("FQN")` | FQN | `class_index[FQN]` |
| `ctx.getBean("name")` | bean name | `bean_index[name]` |
| `ctx.getBean(Type.class)` | `arg_kind=type`, skip in B7-1 | (B7-2) |
| `clazz.getMethod("name")` | method simple name | METHOD 후보 리스트 (class resolution 먼저) |
| `clazz.getField("name")` | field simple name | FIELD 후보 |
| `Proxy.newProxyInstance(..., new Class[]{Foo.class}, ...)` | `arg_kind=type`, skip | (B7-2 가 handler 타겟 관측) |

### 5.4 엣지 shape

```python
CodeRelation(
    kind="calls",
    source="com.acme.OrderService.dispatch",   # METHOD fqn
    target="com.acme.FooShipper",                # resolved CLASS fqn
    attributes={
        "source": "static_literal",              # Q2 Coexist 3-way discriminator
        "confidence": 0.9,
        "api": "ApplicationContext.getBean",
        "arg": "fooShipper",
        "line": 15,
    },
)

# 미해소 시:
CodeRelation(
    kind="calls",
    source="com.acme.OrderService.dispatch",
    target="<reflection-site>",                  # sentinel — 실체 없음
    attributes={
        "source": "static_unresolved",
        "confidence": 0.4,
        "api": "ApplicationContext.getBean",
        "arg": "unknownBean",
        "arg_kind": "literal",
        "line": 15,
        "reason": "bean_not_found",
    },
)
```

### 5.5 REFLECTS_AS 엣지

`getMethod("calculate")` 가 실제 METHOD 로 해소되면:
```python
CodeRelation(
    kind="reflects_as",
    source="com.acme.OrderService.dispatch",
    target="com.acme.FooShipper.calculate",      # METHOD fqn
    attributes={"source": "static_literal", "confidence": 0.8, "line": 71},
)
```

### 5.6 테스트 계획 (10 cases)

1. `ctx.getBean("fooShipper")` + `@Component("fooShipper")` 클래스 → `CALLS{source:static_literal, 0.9}`
2. `ctx.getBean("orderService")` + `@Service` (name 없음, camelCase fallback) → match
3. `ctx.getBean("unknown")` + 매칭 실패 → `CALLS{source:static_unresolved, target:<reflection-site>, 0.4}`
4. `Class.forName("com.acme.FooShipper")` + class_index hit → match
5. `Class.forName("invalid.Class")` → static_unresolved
6. `clazz.getMethod("calculate")` + target CLASS 미확정 → skip (method 는 class 확정 후에만)
7. `clazz.getMethod("calculate")` + 직전 `Class.forName("FooShipper")` literal chain → `REFLECTS_AS`
8. `ctx.getBean(shipperName)` (`arg_kind=variable`) → B7-1 skip (B7-2 대상)
9. `ctx.getBean(Shipper.class)` (`arg_kind=type`) → B7-1 skip
10. 같은 파일 2 개 METHOD 가 같은 bean 리터럴 참조 → 각각 엣지 emit (중복 아님, source 가 다름)

---

## 6. B7-2 상세 — `runtime_collector.py`

### 6.1 API

```python
@dataclass(frozen=True)
class ReflectionTrace:
    method_fqn: str              # 호출한 메서드 FQN
    api: str                     # "Class.forName" 등
    line: int                    # 소스 라인 (marker 와 매칭 키)
    resolved_target: str         # 런타임에 실제 해소된 FQN
    sample_count: int = 1        # 동일 trace 관측 횟수

@dataclass(frozen=True)
class CallTrace:                 # 비-Reflection 일반 런타임 호출 trace (B8 확장 여지)
    caller_fqn: str
    callee_fqn: str
    sample_count: int = 1

class RuntimeCollector(Protocol):
    """JVM Agent / JSON 파일 / DB 등 소스 무관한 수집기 인터페이스."""
    def load_reflection_traces(self) -> list[ReflectionTrace]: ...
    def load_call_traces(self) -> list[CallTrace]: ...


def merge_runtime_traces(
    parse_results: list[ParseResult],
    collector: RuntimeCollector,
    class_index: dict[str, CodeEntity],
) -> list[ParseResult]:
    """Appends synthetic ParseResult(file_path='<runtime>') with runtime edges.
    Reflection trace 는 기존 METHOD 의 reflection_calls marker 와 line 매칭해
    CALLS{source:runtime, 0.95} + REFLECTS_AS emit. trace 가 없는 marker 는 B7-1 결과 유지.
    """
```

### 6.2 JSON trace format (B9 instrumentation 이 뱉을 스키마)

```json
{
  "version": "1.0",
  "repo_id": "slab-engine",
  "reflection_traces": [
    {
      "method_fqn": "com.acme.OrderService.dispatch",
      "api": "ApplicationContext.getBean",
      "line": 15,
      "resolved_target": "com.acme.FooShipper",
      "sample_count": 127
    }
  ],
  "call_traces": [
    {
      "caller_fqn": "com.acme.OrderController.createOrder",
      "callee_fqn": "com.acme.OrderService.dispatch",
      "sample_count": 127
    }
  ]
}
```

### 6.3 synthetic ParseResult

```python
runtime_pr = ParseResult(
    entities=[],                         # 런타임에서 새 CLASS/METHOD 발견하면 B8 에서
    relations=[*reflection_edges, *call_edges],
    file_path="<runtime>",               # CrossFileEnricher 의 "<db_schema>" 와 동일 패턴
    language="java",
)
parse_results.append(runtime_pr)
```

### 6.4 line-based marker 매칭

B5-8 marker `{line: 15}` + trace `{line: 15, method_fqn: "OrderService.dispatch"}` 이 같은 호출 site 를 가리키면:
- trace 에서 해소된 `resolved_target` 으로 runtime 엣지 emit
- B7-1 이 남겼을 `static_unresolved` 엣지는 그대로 둠 (Coexist — 런타임에 안 찍힌 다른 경로 표시)

### 6.5 테스트 계획 (10 cases, 실제 JVM Agent 없이 fixture JSON 사용)

1. 단일 `ReflectionTrace` → `CALLS{source:runtime, 0.95}` + `REFLECTS_AS`
2. 같은 method·line 에 static_unresolved + runtime trace → 둘 다 존재 (Coexist 3-way 검증)
3. trace 의 `method_fqn` 이 parse_results 어디에도 없음 → skip
4. 동일 call-site 에 서로 다른 `resolved_target` 2 개 (동적 dispatch) → 2 엣지, 각각 `sample_count` 반영
5. `sample_count: 1` vs `sample_count: 127` → 엣지 속성에 그대로 전달
6. `CallTrace` (비-reflection) → 일반 `CALLS{source:runtime}` 엣지
7. `load_reflection_traces` 가 빈 리스트 → synthetic ParseResult 는 여전히 emit (상징적 진입점)
8. JSON schema 오류 (필수 필드 누락) → `ValueError` 로 fail fast
9. 중복 trace (동일 method+line+target) → 엣지 1 개 + `sample_count` 합산
10. Collector Protocol duck-typing — 가짜 collector 클래스로 동일 인터페이스 소화 확인

### 6.6 deferred

- **JVM Agent 실제 구현** → B9 Slab sample repo 수령 후 `toClaude/temp-runtime/` + `backend/temp_runtime/` 에서. ByteBuddy / `java.lang.instrument` API 선정은 그때.
- **`@Primary` / `@Qualifier` 해소** — `ctx.getBean(Shipper.class)` 같은 type-based 의 정적 1차 추론은 Q3 의 후속 (별도 `spring_bean_type_resolver.py`?) 으로 남김. B7-2 테스트에서는 trace 로만 해소.

---

## 7. Confidence 테이블 (B6·B7 통합 뷰)

| 엣지 | 상황 | confidence |
|---|---|---|
| `PROPAGATES_TO` (explicit `@Mapping`) | B6-1 | 1.0 |
| `PROPAGATES_TO{implicit:true}` | B6-1 implicit | 0.9 |
| `PROPAGATES_TO{library}` | B6-2 BeanUtils 교집합 | 0.7 |
| `PROPAGATES_TO{library, library:unknown}` | B6-2 import 미판별 | 0.5 |
| `READS/WRITES_TABLE` (literal SQL) | B6-3 | 1.0 |
| `READS/WRITES_TABLE{target:<dynamic>}` | B6-3 dynamic | 0.3 |
| **`CALLS{source:static_literal}`** | **B7-1 리터럴 해소** | **0.9** |
| **`CALLS{source:static_unresolved, target:<reflection-site>}`** | **B7-1 해소 실패 + 비-literal** | **0.4** |
| **`CALLS{source:runtime}`** | **B7-2 런타임 trace** | **0.95** |
| **`REFLECTS_AS`** | B7-1/2 getMethod→METHOD | 0.8 |

Impact Analysis BFS 는 threshold 파라미터로 (B8 에서 파라미터화):
- "안전한 변경 범위" → `confidence >= 0.9`
- "관측된 경로" → `source IN ('runtime', 'static_literal')`
- "잠재 전체" → threshold 없음

---

## 8. 엣지 schema 요약

```
METHOD ─[CALLS{source:static_literal,  confidence:0.9,  api, arg, line}]→ CLASS
METHOD ─[CALLS{source:static_unresolved, confidence:0.4, api, arg, arg_kind, line, reason}]→ <reflection-site>
METHOD ─[CALLS{source:runtime,          confidence:0.95, api, line, sample_count}]→ CLASS

METHOD ─[REFLECTS_AS{source, confidence, line}]→ METHOD|FIELD
```

`<reflection-site>` 는 sentinel 노드 — CrossFileEnricher 의 `<dynamic>` 과 동일 역할.

---

## 9. 테스트 계획 (누적)

| 서브스텝 | 신규 테스트 | 회귀 범위 |
|---|---|---|
| B7-0 | +4 cases in `test_spring_reflection_analyzer.py` | Spring 7-analyzer 147/147 목표 |
| B7-1 | `test_reflection_literal_resolver.py` 10 cases | 모델링 범위 282/282 목표 |
| B7-2 | `test_runtime_collector.py` 10 cases | 모델링 범위 292/292 목표 |

각 서브스텝 완료 시 Step Completion Protocol 7 항목 sync.

---

## 10. 범위 바깥 (Deferred)

- **JVM Agent 바이너리** → B9 Slab repo 수령 후 `toClaude/temp-runtime/`.
- **type-based `getBean(Class<T>)` 정적 해소** → Spring `@Primary`/`@Qualifier` 룰 엔진 별도 step. B7-2 에서는 런타임 trace 에만 의존.
- **call-trace 기반 일반 메서드 호출 엣지 보강** → B8 Impact Analysis + hops API 에서. B7-2 DTO `CallTrace` 는 미리 선언만.
- **Sample-count 기반 confidence 조정** → 관측된 trace 가 100+ 회면 0.95 → 0.99 같은 동적 조정. 필요성 확인 후 별도 enhancement.
- **Reflection chain 간단 추론** (`Class x = Class.forName("Foo"); x.getMethod(...)`) — 동일 메서드 내 local var tracking 으로 B7-1 확장 가능. 1 단계 chain 까지는 포함, n-단계는 제외.

---

## 11. 승인 흐름

1. 사용자 이 문서 승인 → B7-0 TDD red 착수
2. 각 서브스텝 (B7-0 → B7-1 → B7-2) 완료 시 7-item sync + 보고
3. B7 완료 시 HANDOFF "다음 세션 첫 할 일" 을 OD-11-B8 로 전환
