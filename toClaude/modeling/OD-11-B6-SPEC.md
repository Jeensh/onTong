# OD-11-B6 동적 매핑 3 분석기 + Cross-file Enricher — 확정 스펙

**날짜**: 2026-04-19
**브랜치**: main
**근거**: Round 1 HTML rev.3 §6-B-4 (Q9 합의 — "신뢰성 > 구현 무게"), 사용자 승인 "이대로 진행"
**선행**: OD-11-B5 (Spring 8 난제 PoC 7/8, B5-7 `JpaAnalyzer` 연기)
**후속**: OD-11-B7 Reflection 런타임 계측 수집기 → B8 Impact/BFS → B9 Slab E2E

---

## 0. 설계 원칙

1. **신뢰성 > 구현 무게** — 정확도를 낮추느니 차라리 `confidence` 속성으로 표시하고 런타임(B7)에서 보강한다.
2. **정적 AST 1 회차 + Cross-file 2 회차** — 각 파일당 call-site marker 를 먼저 남기고, repo-level post-batch 에서 타입 정보 교차 해소(`CrossFileEnricher`).
3. **기존 엔티티 Kind 재사용** — `PROPAGATES_TO`/`DERIVES_FROM`/`READS_TABLE`/`WRITES_TABLE` 엣지와 `FIELD`/`DB_TABLE`/`DB_COLUMN` 노드로 충분. 새 kind 등록 없음.
4. **B5 의 post-processor 패턴을 쓰지 않는다** — MapStruct/BeanUtils/NativeSQL 산출물은 *1 차 AST 아티팩트* 이므로 `analyze()` 가 직접 emit 한다. `enrich()` 는 B6-4 전용.
5. **테스트 파일은 분석기별 1:1** — 4 개 분석기 → 4 개 신규 테스트 파일.

---

## 1. 구성

| Sub-step | 분석기 | 위치 | LOC 추정 | 출력 |
|----------|--------|------|---------|------|
| **B6-1** | `MapStructAnalyzer` | `backend/modeling/code_analysis/spring/mapstruct_analyzer.py` | ~260 | `PROPAGATES_TO` / `DERIVES_FROM` (FIELD→FIELD, via_methods 포함) |
| **B6-2** | `BeanUtilsAnalyzer` | `backend/modeling/code_analysis/spring/beanutils_analyzer.py` | ~220 | METHOD entity 속성 `beanutils_calls = [{src_type, dst_type, ignore, confidence, line}]` |
| **B6-3** | `NativeSqlAnalyzer` | `backend/modeling/code_analysis/spring/native_sql_analyzer.py` | ~300 | `READS_TABLE` / `WRITES_TABLE` (METHOD → DB_TABLE, columns 속성), 동적 SQL 경계 마커 |
| **B6-4** | `CrossFileEnricher` | `backend/modeling/code_analysis/cross_file_enricher.py` | ~200 | B6-1/2/3 산출물 + 전체 repo 의 FIELD/CLASS import 맵을 받아 field 교집합 & column→field 해소 |

---

## 2. 승인된 10 결정 (User "이대로 진행" 2026-04-19)

### D1. MapStruct implicit same-name mapping 허용 여부 → **Option B 채택**

- **A**: `@Mapping` 으로 명시된 필드만 엣지로 만든다.
- **B** ✅: `@Mapping` + 이름이 같은 field 가 양쪽 DTO 에 존재하면 암묵적 `PROPAGATES_TO` 도 emit. 단 `confidence=0.9` (명시는 1.0).
- 이유: MapStruct 기본 동작이 implicit mapping 이라 제외하면 계보가 심각히 누락됨. cross-file 필드 교집합은 B6-4 에서 처리 — B6-1 단독으로는 `same-name: true` 플래그만 marker 로 남긴다.

### D2. BeanUtils 필드 교집합 타이밍 → **Option B 채택**

- **A**: 분석기 내부에서 import 맵으로 즉시 교집합 산출.
- **B** ✅: METHOD 속성에 `beanutils_calls` marker 만 남기고 실제 교집합은 B6-4 에서.
- 이유: per-file 분석기가 repo 전체 CLASS/FIELD 를 알기 어려움. B6-4 post-batch 에서 모든 ParseResult 을 모아 처리하는 쪽이 깔끔.

### D3. SQL 파서 → **Option A 채택 (sqlglot)**

- **A** ✅ `sqlglot` : Python, MIT, 20+ 방언, dict AST.
- B `sqlparse` : 토큰만 주고 시맨틱 낮음. JOIN/subquery 등 테이블 추출 정확도 떨어짐.
- C 직접 파싱 : 범위 과대.
- 이유: MES/SCM 환경에서 Oracle/MySQL/Postgres 등 다방언 필요. sqlglot 의 `parse_one(..., dialect=...)` 로 통일.
- 의존성: `pyproject.toml` 에 `sqlglot>=23.0` 추가 (B6-3 에서).

### D4. SQL 컬럼 단위 DB_COLUMN 노드 생성 → **Option B 채택**

- **A**: B6-3 에서 즉시 `DB_COLUMN` 노드 + `READS`/`WRITES` 엣지 생성.
- **B** ✅: B6-3 는 `READS_TABLE`/`WRITES_TABLE` 엣지에 `columns: [...]` 속성만 달고, DB_COLUMN 노드화는 B6-4 에서.
- 이유: 같은 컬럼이 여러 파일에서 참조될 때 노드 중복 방지. DB 스키마 메타 병합은 repo-level 이 맞다.

### D5. 동적 SQL (StringBuilder / MessageFormat) → **Option A 채택**

- **A** ✅: 파싱 가능한 부분만 파싱하고 나머지는 `<dynamic>` marker + `raw_sql` 속성에 원본 보존. 엣지 `confidence=0.3`.
- B: 완전 동적 SQL 은 감지하지 않음 (skip).
- 이유: "엣지 안 그리면 의존 추적 0". marker 라도 남기면 B7 런타임 이후에 교차 검증 가능.

### D6. 구현 순서 → **순차 B6-1 → B6-2 → B6-3 → B6-4**

- 각 분석기는 독립적이라 병렬도 가능하나, sequential 이 QA 단순.
- B6-4 는 앞 3 개가 모두 필요하므로 마지막.

### D7. standalone `analyze()` vs `enrich()` → **standalone 채택**

- MapStruct/BeanUtils/NativeSQL 산출물은 1 차 아티팩트 (lineage 엣지). `analyze()` 에서 직접 emit.
- B5-6 Profile 같은 속성 주입 패턴은 부적합.
- 예외: B6-4 `CrossFileEnricher` 만 post-batch 형태 (JavaParser 단위 아님).

### D8. B6-4 CrossFileEnricher 분리 → **O (별도 sub-step)**

- BeanUtils 교집합 / SQL 컬럼→필드 해소 / MapStruct implicit 최종 확정은 repo 전체 맥락 필요.
- B6-4 는 JavaParser 외부 헬퍼: `enrich_repo(parse_results, class_index) -> list[ParseResult]`.
- 장점: per-file 분석기는 단순화되고, 엔진 통합점(B9)이 자연스럽게 모여 테스트 가능.

### D9. 새 EntityKind 필요? → **X — 기존 17 kind 재사용**

- FIELD / CLASS / METHOD / DB_TABLE / DB_COLUMN 으로 커버.
- BeanUtils marker 는 METHOD.attributes 로 충분.
- `<dynamic>` 은 attribute string 값 ("<dynamic>") 으로 표현.

### D10. 테스트 파일 수 → **4 개 (분석기별 1 개)**

- `tests/test_spring_mapstruct_analyzer.py`
- `tests/test_spring_beanutils_analyzer.py`
- `tests/test_spring_native_sql_analyzer.py`
- `tests/test_cross_file_enricher.py`

---

## 3. B6-1 MapStructAnalyzer 상세 스펙

### 3.1 감지 대상

- 인터페이스/추상 클래스에 `@Mapper` 또는 `@Mapper(componentModel=...)` 선언.
- 매핑 메서드(non-default) 각각에 대해:
  - `@Mapping(source = "x", target = "y")` → `PROPAGATES_TO` FIELD→FIELD, `confidence=1.0`.
  - `@Mapping(source = "x", target = "y", qualifiedByName = "name")` → 동일 `PROPAGATES_TO` + `via_methods` 에 qualifier 포함.
  - `@Mapping(expression = "java(...)", target = "y")` → `DERIVES_FROM` + `expression` 속성.
  - `@Mapping(target = "x", ignore = true)` → 엣지 미생성 (marker 도 없음).
  - `@Mappings({@Mapping(...), @Mapping(...)})` 컨테이너도 동일하게 풀어낸다.
- 명시되지 않은 필드는 B6-1 단독에서는 `mapstruct_implicit_fields` marker 를 METHOD 속성에 남긴다. B6-4 에서 교집합 확정 후 `PROPAGATES_TO{confidence: 0.9, implicit: true}` 로 승격.

### 3.2 엣지 source/target 규약

- `source` : `<SrcDtoFqn>.<fieldName>` — `@Mapping.source` 의 dotted path 첫 토큰이 파라미터 이름이라면 타입을 파라미터 시그니처에서 찾아 replace. 못 찾으면 raw 문자열 그대로 둔다.
- `target` : `<DstDtoFqn>.<fieldName>` — 메서드 반환 타입으로부터 fqn 해소.
- `via_methods` : `[<MapperInterfaceFqn>.<methodName>]`.
- `confidence` : 명시 = 1.0, implicit = 0.9 (B6-4 후).
- `conditional` : 표현식에 if/? 가 있으면 true.

### 3.3 출력 예

입력:

```java
package com.x.mapper;
import org.mapstruct.*;

@Mapper
public interface OrderMapper {
    @Mapping(source = "item.id",     target = "productId")
    @Mapping(expression = "java(src.amount() * 1.1)", target = "totalWithTax")
    OrderDto toDto(OrderReq src);
}
```

출력 엣지:

```python
CodeRelation(
    kind="propagates_to",
    source="com.x.model.OrderReq.item.id",       # B6-4 에서 OrderReq 의 parameter resolution
    target="com.x.dto.OrderDto.productId",
    attributes={
        "via_methods": ["com.x.mapper.OrderMapper.toDto"],
        "confidence": 1.0,
        "mapper_fqn": "com.x.mapper.OrderMapper",
    },
)

CodeRelation(
    kind="derives_from",
    source="com.x.model.OrderReq.amount",
    target="com.x.dto.OrderDto.totalWithTax",
    attributes={
        "expression": "java(src.amount() * 1.1)",
        "via_methods": ["com.x.mapper.OrderMapper.toDto"],
        "confidence": 1.0,
    },
)
```

### 3.4 JavaParser 통합

- `MapStructAnalyzer.analyze()` 는 parameter 타입 resolution 가능한 부분까지 FQN 해소. 해소 실패 시 raw 문자열 보존 후 B6-4 에서 `class_index` 로 재해소.
- B5 와 동일하게 SpringAnalyzer Protocol 호환. `enrich()` 훅 없음.

### 3.5 설계상 주의

- `@Mapping` 의 `target` 필드 경로에 `.` 이 있으면 중첩 매핑: `target = "address.city"`. 이 경우 `PROPAGATES_TO` 의 target 은 `Dst.address.city` 로 그대로 기록.
- `@Mapping.constant = "..."` 는 상수 주입이라 source 가 없다 → `DERIVES_FROM` + `constant` 속성으로 처리 (source 는 null 대신 `<literal>` 가상 노드... **B6-1 에서는 skip**, B6-4 후 후속 논의).
- `default` 메서드와 `@Named` 선언은 제외 (매퍼의 helper — entity/relation 으로 안 남긴다).

### 3.6 테스트 ~15 케이스 (계획)

1. `@Mapper` 빈 인터페이스 → no entity/relation
2. `@Mapping(source, target)` → `propagates_to` 1 개
3. `@Mapping(expression)` → `derives_from` + `expression` 속성
4. `@Mapping(source = "nested.x", target = "y")` → source 에 dotted path 유지
5. `@Mapping(target = "x", ignore = true)` → no edge
6. `@Mappings({@Mapping(...), @Mapping(...)})` → 여러 엣지
7. `@Mapping(source, target, qualifiedByName)` → via_methods 에 qualifier 포함
8. 여러 매핑 메서드 → 각자 엣지 생성
9. `default` 메서드는 skip
10. `@Named` 메서드 skip
11. implicit same-name 은 marker 만 → METHOD.attributes["mapstruct_implicit_fields"] = [...]
12. `@Mapper(componentModel="spring")` 도 감지 (class annotation 파싱 강건성)
13. non-`@Mapper` interface → 무시
14. abstract class + `@Mapper` → 감지 (MapStruct 는 abstract class 도 허용)
15. nested mapper (class 내부 interface) → 감지

---

## 4. B6-2 BeanUtilsAnalyzer 상세 스펙

### 4.1 감지 대상 + 인자 순서 차이

| 라이브러리 | Import | 호출 | 인자 순서 |
|-----------|--------|------|-----------|
| Spring | `org.springframework.beans.BeanUtils.copyProperties` | `BeanUtils.copyProperties(src, dst)` | (SRC, DST) |
| Apache Commons | `org.apache.commons.beanutils.BeanUtils.copyProperties` | `BeanUtils.copyProperties(dst, src)` | **(DST, SRC) — 반대!** |
| ModelMapper | `org.modelmapper.ModelMapper` | `mm.map(src, Dst.class)` | (SRC, DST.class) |

- **구분 전략**: 같은 파일의 `import` 선언을 AST 에서 수집 → 어느 라이브러리인지 판단 → 그에 맞춰 인자 순서 해석. Import 가 애매하면 confidence 를 낮춘다.

### 4.2 출력 (METHOD 속성 marker)

```python
method.attributes["beanutils_calls"] = [
    {
        "src_type": "com.x.model.OrderReq",
        "dst_type": "com.x.dto.OrderDto",
        "library": "spring" | "apache" | "modelmapper" | "unknown",
        "ignore": ["password"],  # copyProperties(src, dst, "password") 3rd+ arg
        "confidence": 0.7,
        "line": 42,
    }
]
```

- B6-2 단독으로는 `PROPAGATES_TO` 엣지를 emit 하지 않는다 (cross-file 교집합 필요).
- B6-4 에서 import 맵 + CLASS index 로 src/dst 의 FIELD 리스트를 구해 교집합 필드 각각에 `PROPAGATES_TO{confidence: 0.7, library, via_methods}` 를 emit.

### 4.3 테스트 ~12 케이스 (계획)

1. Spring `BeanUtils.copyProperties(src, dst)` → library=spring
2. Apache Commons `BeanUtils.copyProperties(dst, src)` → library=apache, 인자 순서 반대 확인
3. ModelMapper `modelMapper.map(src, Dst.class)` → library=modelmapper
4. `BeanUtils.copyProperties(src, dst, "password")` → ignore=["password"]
5. Import 없음 → library=unknown, confidence 0.5 로 낮춤
6. 두 개 호출이 같은 메서드에 → calls 리스트 2 개
7. 다른 메서드 → scope 격리
8. Non-BeanUtils 호출 → 무시
9. Static import (`import static org.springframework.beans.BeanUtils.copyProperties`) → bare `copyProperties(...)` 도 감지
10. `map(src, dst)` (ModelMapper instance method) → object 타입 유추 안 되면 library=modelmapper 후보로 후순위 매칭
11. cross-constructor 호출 (생성자 body) → 감지
12. 표준 `analyze()` 가 entity/relation 산출 없이 METHOD marker 만 주입

---

## 5. B6-3 NativeSqlAnalyzer 상세 스펙

### 5.1 감지 대상

| API | 감지 조건 | SQL 추출 위치 |
|-----|-----------|---------------|
| Spring Data `@Query` | METHOD 에 `@Query("SELECT ...")` 또는 `@Query(value="...", nativeQuery=true)` | annotation value / `value` |
| `@Query` + `@Modifying` | `@Modifying` 이 함께 있으면 write | 동일 |
| `EntityManager.createNativeQuery` | `method_invocation.name == "createNativeQuery"` + object 가 `EntityManager`/`em` 타입 | 첫 인자 string |
| `EntityManager.createQuery` | JPQL — 감지하되 native 가 아닌 것 명시 | 동일 |
| `JdbcTemplate.query` / `queryForObject` / `queryForList` | `method_invocation` name 매칭 + object 가 `JdbcTemplate` 타입 | 첫 인자 string |
| `JdbcTemplate.update` / `batchUpdate` | write | 동일 |

### 5.2 sqlglot 로 추출할 것

```python
parsed = sqlglot.parse_one(sql, dialect="ansi", error_level="ignore")
# tables : SELECT / JOIN / UPDATE / DELETE / INSERT INTO / FROM 모두
# columns : SELECT columns + WHERE references + INSERT/UPDATE target columns
# op_kind : "read" | "write" | "mixed"
```

- op_kind 는 statement 종류로 결정 (`Select`=read, `Update`/`Insert`/`Delete`=write, CTE 는 안전하게 read).
- `raw_sql` 속성에 원본 문자열도 반드시 보존 (B6-4/B9 에서 재파싱 가능).

### 5.3 엣지 포맷

```python
CodeRelation(
    kind="reads_table",
    source="com.x.repo.OrderRepo.findByCustomer",   # method FQN
    target="orders",                                  # table name (lowercased)
    attributes={
        "columns": ["id", "customer_id", "total"],
        "confidence": 1.0,                            # static literal
        "raw_sql": "SELECT id, customer_id, total FROM orders WHERE customer_id = ?",
        "dialect": "ansi",
    },
)
```

- 동적 SQL (`"SELECT * FROM " + table`) → sqlglot 가 parse 실패 → `columns=["<dynamic>"]`, `confidence=0.3`, `raw_sql` 은 concat 트리 전체 토큰을 `|` 로 join.
- DB_TABLE 노드는 B6-3 에서 emit 하지 않는다 — B6-4 에서 repo 전체에 걸쳐 중복 제거 + `CodeEntity(kind="db_table", qualified_name="<schema>.<table>")` 한 번만 생성.

### 5.4 테스트 ~16 케이스 (계획)

1. `@Query("SELECT ...")` → `reads_table`, columns 리스트
2. `@Query(value="INSERT INTO orders ...", nativeQuery=true)` → `writes_table`
3. `@Modifying` + `@Query("UPDATE ...")` → `writes_table`
4. JPQL `@Query("SELECT o FROM Order o")` → `reads_table` + dialect=jpql marker
5. `entityManager.createNativeQuery("SELECT...")` → `reads_table`
6. `jdbcTemplate.query("SELECT...")` → `reads_table`
7. `jdbcTemplate.update("UPDATE...")` → `writes_table`
8. JOIN 다중 테이블 → target 엣지 2 개
9. subquery → 내부 테이블도 포함
10. INSERT INTO ... SELECT → write 엣지 (target) + read 엣지 (source)
11. 동적 SQL (StringBuilder append) → `<dynamic>` marker, confidence=0.3
12. MyBatis XML → **Round 1 스코프 외** (negative test 로 고정, B 이후에 다룬다)
13. `@Query` native=false vs native=true 구분
14. multi-statement 구문은 첫 statement 만 처리 + warning
15. lowercase/uppercase 테이블명 정규화 (항상 lowercase)
16. standalone `analyze()` 가 relation 을 직접 emit (enrich 아님)

---

## 6. B6-4 CrossFileEnricher 상세 스펙

> **확정 날짜**: 2026-04-19 — 사용자 "추천 그대로 진행" (QA HTML `OD-11-B6-4-QA.md/html` Q1~Q10 + 보조 5건 모두 채택).

### 6.1 입력 / 출력

```python
def enrich_repo(
    parse_results: list[ParseResult],
    class_index: dict[str, CodeEntity],        # FQN → CLASS/INTERFACE/ENUM entity
    field_index: dict[str, list[CodeEntity]],  # class_fqn → [FIELD, ...]
) -> list[ParseResult]:
    """Mutate parse_results in-place + append synthetic DB-schema ParseResult.

    Returns the same list object after:
      - appending PROPAGATES_TO / READS / WRITES relations into caller ParseResults
      - appending a new synthetic ParseResult(file_path="<db_schema>") at list end
        that holds all repo-level DB_TABLE / DB_COLUMN entities.
    """
```

Q1 채택 — **in-place 수정** (100K 규모에서 메모리 copy 회피, B9 JavaParser 통합 단순). 반환 리스트는 원본 parse_results 와 동일 객체 + 말미에 `<db_schema>` synthetic ParseResult 1개 추가.

Q3 채택 — **`build_indices(parse_results) -> (class_index, field_index)` 헬퍼를 `cross_file_enricher.py` 내부에 노출**. 운영 통합 코드 (B9 JavaParser 파이프라인) 는 이 헬퍼 호출. 테스트는 합성 index 직접 주입.

### 6.2 JPA annotation 추출 (Q2)

**별도 모듈** `backend/modeling/code_analysis/jpa_annotation_extractor.py` 가 담당 (Q2 Option C).

- 입력 : `ParseResult` (tree 포함) + class FQN.
- 출력 : class CodeEntity 의 `attributes` 에 merge:
  - `jpa_entity_name: str | None` — `@Entity(name="Order")` 의 name, 미명시면 simple class name 그대로.
  - `jpa_table: str | None` — `@Table(name="orders")` 의 name (lowercase). 없으면 `None`.
  - `jpa_columns: dict[str, str]` — `{field_name: column_name (lowercase)}`. `@Column(name=...)` 명시된 필드만 채움 (Q8 채택). 미명시 필드는 매핑에 포함하지 않음 (snake_case 추측 없음).
- JavaParser 본체는 건드리지 않음 — B6-4 가 build_indices 안에서 JpaAnnotationExtractor 를 호출해 class_index 의 CodeEntity 속성에 JPA info 를 merge.

### 6.3 책임 4 가지

#### 6.3.1 MapStruct implicit finalize (B6-1 marker 소비)

marker 포맷 (B6-1 에서 METHOD.attributes 에 주입됨):

```python
METHOD.attributes["mapstruct_implicit_fields"] = [
    {"mapper_fqn": str, "method": str, "src_type": str, "dst_type": str, "line": int},
    ...
]
```

처리 절차:

1. marker 의 `src_type` / `dst_type` 을 class_index 로 FQN 해소. 해소 실패 시 simple name suffix 매칭 — 후보 1개면 사용, ≥2면 skip.
2. src/dst 의 FIELD 리스트를 field_index 에서 가져옴. **Q4 채택 — 이름만 같으면 교집합** (타입 호환 검사 없음).
3. **Q5 채택** — 같은 METHOD 에 B6-1 이 이미 emit 한 `PROPAGATES_TO` 엣지들의 target 필드셋 (`<DstFqn>.<field>`) 을 수집 → implicit 후보에서 제외.
4. 교집합 필드 각각에 `PROPAGATES_TO` 엣지 emit:

```python
CodeRelation(
    kind="propagates_to",
    source=f"{src_fqn}.{field_name}",
    target=f"{dst_fqn}.{field_name}",
    attributes={
        "via_methods": [f"{mapper_fqn}.{method}"],
        "confidence": 0.9,
        "implicit": True,
        "mapper_fqn": mapper_fqn,
    },
)
```

5. static / final static 필드, `serialVersionUID`, `$jacocoData`, `transient` 필드는 교집합에서 제외.

#### 6.3.2 BeanUtils field intersection (B6-2 marker 소비)

marker 포맷:

```python
METHOD/CONSTRUCTOR.attributes["beanutils_calls"] = [
    {"library": str, "src_type": str, "dst_type": str, "ignore": list[str],
     "confidence": float, "line": int},
    ...
]
```

처리 절차:

1. **Q6 채택** — `src_type` / `dst_type` 이 simple name 이면 class_index suffix 매칭 → 후보 1개 = 사용 (confidence 그대로), ≥2 = skip + METHOD.attributes 에 `beanutils_ambiguous_types` 리스트 append (`[{call_line, src_candidates, dst_candidates}]` 형태).
2. src/dst FIELD 이름 교집합 (Round 1 same-name only — Spring / Apache / ModelMapper 공통 기본 동작).
3. `ignore` 리스트에 포함된 필드명 제외.
4. 교집합 필드 각각에 `PROPAGATES_TO` 엣지 emit:

```python
CodeRelation(
    kind="propagates_to",
    source=f"{src_fqn}.{field_name}",
    target=f"{dst_fqn}.{field_name}",
    attributes={
        "via_methods": [caller_fqn],    # METHOD or CONSTRUCTOR FQN
        "confidence": marker["confidence"],
        "library": marker["library"],
    },
)
```

5. static / final static / transient / `serialVersionUID` 제외.

#### 6.3.3 NativeSQL column → field resolution (B6-3 엣지 소비)

대상 : 기존 `READS_TABLE` / `WRITES_TABLE` 엣지 (B6-3 emit).

처리 절차:

1. 엣지의 `target` (lowercase table name) 과 `columns` (리스트) 를 순회.
2. `target == "<dynamic>"` → skip (DB_TABLE/DB_COLUMN 노드 생성 없음, 엣지만 유지).
3. `columns` 에 `"<dynamic>"` 이 포함되면 해당 컬럼은 개별 엣지 emit skip, 다른 컬럼은 정상 처리.
4. `dialect == "jpql"` 인 경우 entity → table 해소:
   - class_index 순회하며 `jpa_entity_name == edge.target` 또는 class simple name lowercase 와 동일한 class 탐색.
   - 해당 class 의 `jpa_table` 이 있으면 edge target 을 실제 table 로 치환 (in-place). 없으면 entity name 그대로 사용.
5. 각 column 에 대해 DB_COLUMN qn 생성 (**Q7 채택**):

```python
DB_TABLE qn  = "<table>" (lowercase)
DB_COLUMN qn = "<table>.<column>" (lowercase)
```

6. 컬럼 → field 해소 (Q8 채택 — 명시만):
   - 관련 class 의 `jpa_columns` 에서 역인덱스 (`{column: field}`) 구축.
   - column 이 명시되지 않은 경우 DB_COLUMN 노드만 생성하고 field 매핑 없음.
7. 각 column 에 대해 `READS` / `WRITES` 엣지 emit (**Q9 채택 — 병존**, 기존 READS_TABLE/WRITES_TABLE 유지):

```python
CodeRelation(
    kind="reads" | "writes",
    source=method_fqn,                      # READS_TABLE 의 source 동일
    target=f"{table}.{column}",             # DB_COLUMN qn
    attributes={
        "confidence": edge.attributes["confidence"],
        "field_fqn": f"{class_fqn}.{field}",  # 해소된 경우만
    },
)
```

#### 6.3.4 DB_TABLE / DB_COLUMN dedup (Q10 채택)

- 모든 `READS_TABLE` / `WRITES_TABLE` / `READS` / `WRITES` 엣지의 target 을 수집.
- **synthetic `ParseResult(file_path="<db_schema>", tree=None, pkg_name=None, entities=[...], relations=[])`** 를 parse_results 리스트 말미에 1개 추가.
- DB_TABLE / DB_COLUMN entity 는 synthetic ParseResult.entities 에만 모아 담음 (dedup, 파일간 중복 제거).
- `CodeEntity(kind="db_table", qualified_name="<table>", ...)` + `CodeEntity(kind="db_column", qualified_name="<table>.<column>", attributes={"table": <table>, "field_fqn"?: <class.field>})`.

### 6.4 보조 결정 (확정)

- **테스트 픽스처** : 합성 `ParseResult` + 합성 `class_index` / `field_index` 로 직접 구성. 통합 케이스 1~2개만 실제 JavaParser + JpaAnnotationExtractor 전체 경로.
- **중복 엣지 dedup** : `(kind, source, target)` 튜플로 dedup, `confidence = max(duplicates)`, `attributes` 는 first-wins (library / via_methods 는 첫 번째 기준).
- **`via_methods` 컨벤션**:
  - BeanUtils : caller METHOD / CONSTRUCTOR FQN 1개 (호출 지점).
  - MapStruct implicit : `<MapperFqn>.<method>` (B6-1 명시 엣지와 동일).
- **JPQL entity → table 해소**: (1) `@Entity(name="Order")` 명시 우선 (lowercase 비교), (2) 없으면 class simple name lowercase, (3) `@Table(name="orders")` 있으면 table name 치환.
- **confidence merge**: 한 메서드가 BeanUtils 여러 번 호출 + 같은 (src, dst) 중복 → dedup 후 `max`.

### 6.5 테스트 ~10 케이스 (확정 계획)

합성 시나리오 기반 (`tests/test_cross_file_enricher.py`):

1. MapStruct implicit — src/dst FIELD 교집합 3개 → `PROPAGATES_TO{confidence=0.9, implicit=true}` 3 엣지
2. MapStruct implicit — B6-1 명시 엣지와 중복 (id 필드) → implicit 에서 id 제외
3. MapStruct implicit — simple name suffix 매칭 (단일 후보)
4. BeanUtils — Spring `copyProperties(src, dst)` → 교집합 3개 `PROPAGATES_TO{confidence=0.7, library=spring}`
5. BeanUtils — Apache 인자 순서 반대 + ignore 리스트 적용
6. BeanUtils — simple name 후보 ≥2 → skip + `beanutils_ambiguous_types` marker
7. NativeSQL — `READS_TABLE orders` + columns=[id, customer_id] → `DB_TABLE orders` + `DB_COLUMN orders.id`, `orders.customer_id` + `READS` 엣지 2개 (기존 `READS_TABLE` 유지)
8. NativeSQL JPQL — `target="order"` → class_index 에서 Order 클래스 `jpa_table="orders"` 로 치환
9. NativeSQL `<dynamic>` — DB_TABLE/DB_COLUMN 생성 skip, 원본 `READS_TABLE` 엣지 유지
10. DB_TABLE dedup — 2개 파일이 같은 `orders` 참조 → synthetic ParseResult 에 `DB_TABLE orders` 1개만 + 각 파일의 relations 에는 기존 + `READS` 엣지 부착

---

## 7. 회귀 + 검증 기준

- 각 sub-step 완료 시:
  - 신규 테스트 100% pass
  - Spring 전체 분석기 테스트 pass (B5-1~B5-6,8 + 신규)
  - 모델링 scope `pytest -k "spring or java_parser or code_analysis or modeling or graph"` pass
- B6-3 시 `sqlglot` 의존성 추가 → `pip install` 후 import 에러 없음 확인

---

## 8. 진행 순서 요약

1. B6-1 MapStruct — TDD (~15 cases) → impl → docs sync
2. B6-2 BeanUtils — TDD (~12 cases) → impl → docs sync
3. B6-3 NativeSQL — `sqlglot` 의존성 추가 → TDD (~16 cases) → impl → docs sync
4. B6-4 CrossFileEnricher — TDD (~10 cases, 합성 시나리오) → impl → docs sync
5. Phase B 전체 통합 회귀

각 sub-step 후 사용자 보고 + 체크리스트 확인.
