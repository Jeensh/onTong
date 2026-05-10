# slab-design-real_v2 — 설계 명세 (SPEC)

작성일: 2026-05-10
대상 디렉토리: `sample-repos/slab-design-real_v2/`
기반: `sample-repos/slab-design-real/` (v1, read-only)

---

## 1. 개요

`slab-design-real_v2`는 v1의 정적 fixture 한계를 넘어 **실제 실행 + API 호출이 가능한** 청결한 baseline Spring Boot 애플리케이션이다. 두 가지 용도를 동시에 만족한다.

1. **시뮬레이션 대상 (clean baseline)** — 의도적 drama DNA(비표준 컬럼명, magic number, 깊은 nested if, reflection 매핑)를 제거한 깨끗한 시스템. onTong의 ontology / 시뮬레이션 도구가 비교 baseline으로 사용한다.
2. **시뮬레이션 검증 환경 (verification runtime)** — onTong이 ontology 기반으로 생성한 Python 시뮬레이션 코드의 정답을 v2 Java 런타임으로 산출한다. step-별 trace 응답이 정답 인터페이스가 된다.

v1 알고리즘 (21-step 슬랩 설계)은 v2에서 동작 동일성을 유지한다. 외형 청소는 가능하나 산출 결과는 v1과 같아야 한다.

---

## 2. 목적 & 비목적

### 목적

- v2 단독으로 빌드/실행/API 호출/단위·통합 테스트가 가능
- H2 in-memory DB로 외부 의존성 0개 (JDK 21만 있으면 동작)
- 5개 골든 시나리오로 21-step 알고리즘의 정확도 자동 검증
- step 단위 trace 응답으로 시뮬레이션 비교 정량화 가능
- Swagger UI로 사람이 즉시 API 탐색

### 비목적

- v1 코드 수정 (read-only)
- onTong 다른 영역 (`backend/`, `frontend/`, `data/`, `scripts/`, `toClaude/<section>/` 등) 변경
- 새 주문 생성/수정 API (입력은 시드된 주문 PK만)
- Production 수준 보안/인증 (CSRF/CORS는 dev 기본값)
- Oracle XE / PostgreSQL 등 외부 DB 지원 (H2만)
- Kafka 연동 (제거)
- 14번 step (제품단중 최대화 모드 — v1에서도 명시적 skip)

---

## 3. 프로젝트 구조

### 3.1 모듈

v1의 4-module Maven multi-module 구조를 그대로 유지한다.

```
slab-design-real_v2/
├── pom.xml                                  parent POM
├── mvnw, mvnw.cmd                           Maven Wrapper (v1에서 복사)
├── README.md                                간단 빌드/실행 가이드
├── docs/
│   ├── SPEC.md                              이 문서
│   ├── PLAN.md                              구현 계획 (다음 단계 산출)
│   ├── API.md                               API curl 예시 + trace 스키마
│   ├── SCENARIOS.md                         5개 골든 시나리오 상세
│   └── V1_TO_V2_DIFF.md                     v1 → v2 청소 매핑
├── slab-design-boot/
│   └── src/main/java/.../boot/
│       ├── SlabDesignApplication.java       @SpringBootApplication
│       ├── config/
│       │   ├── DataSourceConfig.java        H2 + Hikari 설정 (실제 wiring)
│       │   ├── JpaConfig.java               EntityScan + JpaRepositories
│       │   └── SwaggerConfig.java           OpenAPI 메타 (title, version)
│       └── resources/
│           ├── application.yml              H2 설정
│           ├── db/seed/
│           │   ├── 01_master.sql            spec/rule master row
│           │   └── 02_orders.sql            5개 시나리오 ORDER_* row
│           └── logback-spring.xml           debug-friendly 로깅
├── slab-design-facade/
│   └── src/main/java/.../facade/sd/rest/
│       ├── working/SdWorkingController.java   batch + single (+trace)
│       ├── orders/SdOrderController.java       시드 주문 조회
│       ├── results/SdResultController.java     슬랩 결과 조회
│       ├── history/SdHistoryController.java    21-step history 조회
│       └── seed/SdSeedController.java          reset + scenarios
├── slab-design-feature/
│   └── src/main/java/.../feature/sd/
│       ├── designer/SdDesigner.java         v1 그대로 + TraceCollector hook
│       ├── driver/SdDriver.java             Kafka 제거, batchDesign 단순화
│       ├── trace/
│       │   ├── TraceCollector.java          step input/output 수집
│       │   ├── StepTrace.java               record (step, name, phase, in, out, status)
│       │   └── TraceAwareAction.java        decorator (선택적)
│       ├── process/working/action/          21개 Sd*Action (v1 청소판)
│       ├── process/std/service/             spec/rule lookup 서비스 (v1 청소판)
│       └── common/SdConstants.java          magic number 추출
└── slab-design-store/
    └── src/main/java/.../store/sd/
        ├── (각 도메인)/domain/entity/         JPA @Entity (컬럼명 통일)
        ├── (각 도메인)/repository/            Spring Data JPA Repository
        └── support/SdMapper.java            JPO ↔ Entity 명시적 mapper (reflection 제거)
```

### 3.2 모듈 의존 방향 (v1과 동일)

```
boot ──▶ facade ──▶ feature ──▶ store
```

`feature`는 HTTP 모름. `facade`는 JPA 모름. `store`는 데이터만.

### 3.3 빌드 도구 / 의존성

`pom.xml` parent는 `spring-boot-starter-parent:3.4.0`. Java 21.

**v1에서 제거**:
- `oracle.database.jdbc:ojdbc11`
- `org.springframework.cloud:spring-cloud-stream-kafka`
- `org.mybatis.spring.boot:mybatis-spring-boot-starter` (MyBatis 미사용 — JPA만)

**v2에서 추가**:
- `com.h2database:h2` (runtime)
- `org.springdoc:springdoc-openapi-starter-webmvc-ui:2.6.0`
- `org.springframework.boot:spring-boot-starter-test` (test scope)
- `io.rest-assured:rest-assured` (test scope)
- `org.assertj:assertj-core` (test scope)

---

## 4. 데이터 레이어

### 4.1 application.yml

```yaml
spring:
  application:
    name: slab-design-real-v2
  datasource:
    url: jdbc:h2:mem:slabdesign;MODE=Oracle;DB_CLOSE_DELAY=-1
    driver-class-name: org.h2.Driver
    username: sa
    password:
  jpa:
    database-platform: org.hibernate.dialect.H2Dialect
    hibernate:
      ddl-auto: create-drop
    show-sql: false
    open-in-view: false
    defer-datasource-initialization: true
  sql:
    init:
      mode: always
      data-locations:
        - classpath:db/seed/01_master.sql
        - classpath:db/seed/02_orders.sql
  h2:
    console:
      enabled: true
      path: /h2-console

springdoc:
  api-docs:
    path: /v3/api-docs
  swagger-ui:
    path: /swagger-ui.html

logging:
  level:
    com.example.slabdesign: DEBUG
    org.hibernate.SQL: WARN
```

`MODE=Oracle` → Oracle SQL 방언 호환 (sequence, NUMBER 타입 등). v1 JPA 코드를 거의 그대로 가져올 수 있게 한다.

### 4.2 12개 테이블 (v1 그대로 유지)

- 4 ORDER: ORDER_OS, ORDER_OM, ORDER_QD, ORDER_CHEMICAL
- 4 spec: CAST_SPEC, HR_SPEC, EDGING_GROUP, EDGING_SPEC
- 4 rule master: CUSTOMER_STD, HR_MIN_WGT, HR_MAX_WGT, PRODUCTIVITY_STD
- 1 결과: SLAB_RESULT
- 1 이력: SLAB_DESIGN_HIST

`SLAB_RESULT`, `SLAB_DESIGN_HIST`는 시드 비어있음 → API 호출이 채움.

### 4.3 5개 골든 시나리오 시드

| ID | 시나리오 | 활성 공정 (8-char) | 핵심 검증점 |
|----|---------|--------------------|-----------|
| S1 | 일반 COIL 주문 | `"K   K   "` (SM, CR) | 골든 패스 — 슬랩 1매 정상 설계, DG 코드 0건 |
| S2 | 다중 분할 | `"KK      "` (SM, HR) | maxSplitCount=4 → 슬랩 4매. 매수=4 |
| S3 | A-a 루프 fallback | `"KKKK    "` (SM, HR, HRF, CR) | splitCount 첫 시도 fail → splitCount-1 재진입 후 성공. trace에 iteration=1 RETRY + iteration=2 OK |
| S4 | DG004 (포장단중 cross-check fail) | `"KK      "` | 5단계 validation에서 DG004 trip → SLAB_RESULT 0건 + SLAB_DESIGN_HIST에 fail row 1 |
| S5 | 최소 활성 공정 | `"K      K"` (SM, CRF) | 누적실수율 = productivity_SM × productivity_CRF. 비활성 공정 6개 제외 검증 |

**시드 데이터 출처**: 합성 (v1의 `toClaude/slab-design.md` 도메인 글로서리에서 합리적 값 추출). 실제 운영 데이터 아님. 강종 SS400, 폭 800-1500mm, 단중 8000-15000kg 범위.

**시드 PK**:
- 회사·소: `cmpCd="K"`, `orgCd="K01"`
- 주문번호: `ORD20260510001` ~ `ORD20260510005` (5건)

### 4.4 reset 동작

`POST /api/sd/seed/reset`:
1. `SET REFERENTIAL_INTEGRITY FALSE` (H2) — FK 임시 비활성
2. 12개 테이블 TRUNCATE
3. `01_master.sql` 재실행
4. `02_orders.sql` 재실행
5. `SET REFERENTIAL_INTEGRITY TRUE`
6. SLAB_RESULT, SLAB_DESIGN_HIST 비워둠
7. 응답: `{ ok: true, scenarios: ["S1", "S2", "S3", "S4", "S5"] }`

H2 in-memory + 단일 JVM 가정. 동시성 보호 없음 (test/dev 용도).

---

## 5. API 표면

### 5.1 endpoint 목록

| Method | Path | 용도 |
|--------|------|------|
| `POST` | `/api/sd/working/batch?cmpCd=&orgCd=` | 회사·소 단위 배치 (v1 호환) |
| `POST` | `/api/sd/working/single` | 주문 1건 설계 |
| `POST` | `/api/sd/working/single?trace=true` | 1건 + step 단위 trace |
| `GET` | `/api/sd/orders?cmpCd=&orgCd=&page=&size=` | 시드 주문 목록 (페이징) |
| `GET` | `/api/sd/orders/{cmpCd}/{orgCd}/{orderNo}` | 주문 1건 상세 (4 ORDER_* 조인) |
| `GET` | `/api/sd/results?cmpCd=&orgCd=&orderNo=` | 슬랩 결과 |
| `GET` | `/api/sd/results/{slabNo}` | 슬랩 1건 (12-digit) |
| `GET` | `/api/sd/history?cmpCd=&orgCd=&orderNo=` | 21-step history JSON |
| `POST` | `/api/sd/seed/reset` | DB 리셋 + 시드 재실행 |
| `GET` | `/api/sd/seed/scenarios` | 5개 시나리오 메타 + 골든 |

### 5.2 single 입력 / 출력

**Request**:
```json
{ "cmpCd": "K", "orgCd": "K01", "orderNo": "ORD20260510001" }
```

**Response (trace=false)**:
```json
{
  "slabResults": [
    {
      "slabNo": "000000000001",
      "targetWidth": 1100,
      "targetLength": 8500,
      "slabWgt": 12450.0,
      "...": "..."
    }
  ],
  "errorCode": null,
  "errorMessage": null
}
```

**Response (trace=true)**:
위 + `trace: StepTrace[]` 추가.

### 5.3 StepTrace 스키마

```json
{
  "step": 1,
  "stepName": "SdThicknessAction",
  "phase": "ONE_SHOT" | "AA_LOOP" | "FINAL" | "SAVE",
  "iteration": 1,
  "input": { /* action 입력 dto */ },
  "output": { /* action 출력 dto, null on fail */ },
  "status": "OK" | "RETRY" | "FAIL",
  "errorCode": "DG104" | null,
  "errorMessage": "..." | null,
  "elapsedMs": 0.4
}
```

A-a 루프는 step 8-13이 iteration N회 반복 → trace에 iteration 다른 동일 step 여러 row 등장.

### 5.4 trace 구현 전략

`SdDesigner.designOne(order, traceCollector)` 시그니처. `traceCollector`는 nullable.

각 action 호출 지점에서:

```java
T result = traceCollector == null
    ? action.run(in)
    : traceCollector.wrap(stepNum, stepName, phase, iter, in, () -> action.run(in));
```

`wrap`은 timing + try/catch + status 분류 후 `StepTrace` 한 row 적재. action 내부 코드는 무지(unaware).

비-trace 호출은 collector=null → 분기 비용만 (zero overhead).

### 5.5 Swagger / OpenAPI

- `springdoc-openapi-starter-webmvc-ui` 의존성 한 줄로 자동 생성
- Controller 메서드에 `@Operation`, `@ApiResponse`, `@ExampleObject` 어노테이션
- 5개 시나리오 입력 예시 inline
- UI: `http://localhost:8080/swagger-ui.html`
- 스키마 JSON: `/v3/api-docs`

---

## 6. 테스트 전략

### 6.1 3-tier 구조

**Tier 1 — Action 단위테스트** (총 21개 클래스, 60-80 메서드)
- 위치: `slab-design-feature/src/test/java/.../action/`
- 도구: JUnit 5 + Mockito + AssertJ
- 의존성 mock (lookup service 등)
- 케이스 패턴: 정상 / DG 코드 발생 / boundary
- DB 미사용 → ~5초 내 완료

**Tier 2 — Repository/JPA 테스트** (7-8개 클래스)
- 위치: `slab-design-store/src/test/java/.../repository/`
- 도구: `@DataJpaTest` + H2 + AssertJ
- 픽스처: `@Sql("classpath:db/seed/01_master.sql")`
- 핵심 쿼리만: HR_SPEC 2D lookup, EDGING_SPEC `*` wildcard, PRODUCTIVITY_STD 누적

**Tier 3 — 시나리오 골든 통합테스트** (5개)
- 위치: `slab-design-boot/src/test/java/.../integration/ScenarioGoldenTest.java`
- 도구: `@SpringBootTest(webEnvironment=RANDOM_PORT)` + RestAssured
- 흐름: seedReset → single(trace=true) → 골든 비교
- 골든 파일: `src/test/resources/golden/S{1..5}.json` (5개)
- 비교: AssertJ `usingRecursiveComparison`. timestamp / sequence-derived 필드 (createdAt, slabNo)는 ignore.

### 6.2 골든 파일 생성 절차

1. 처음에는 비어있음
2. 첫 통합테스트 실행 → 실제 응답을 골든으로 capture (테스트 모드에서 envvar `GOLDEN_REGEN=true`로 재생성 지원)
3. capture된 파일을 사람이 manual 검토 (값 합리성, DG 코드 일치)
4. 검토 통과 후 골든 fix
5. 이후 알고리즘 변경 → 의도된 변경이면 골든 갱신, 의도 외면 회귀로 잡힘

### 6.3 빌드/테스트 진입점

```bash
./mvnw clean verify                            # 컴파일 + 모든 테스트
./mvnw spring-boot:run -pl slab-design-boot    # 서버 기동 (8080)
GOLDEN_REGEN=true ./mvnw -pl slab-design-boot test -Dtest=ScenarioGoldenTest   # 골든 재생성
```

### 6.4 시뮬레이션 검증 인터페이스

골든 테스트의 `trace[]`가 시뮬레이션 검증의 정답 인터페이스가 된다.

1. v2 Java 실행 → `POST /api/sd/working/single?trace=true` → 정답 trace
2. onTong이 ontology 기반 생성한 Python 코드 실행 → 동일 입력 → trace 출력
3. step별 input / output diff → ontology 매핑 정확도 정량화
4. 5개 시나리오를 모두 동일 trace 형식으로 비교 가능

---

## 7. drama DNA 청소 매핑 (v1 → v2)

| v1 패턴 | v1 위치 | v2 처리 |
|---------|---------|---------|
| `PRODUCT_TYPE_CD` / `PRODUCT_NAME_CD` / `PRODUCT_KIND_CD` 혼재 | ORDER_OS, ORDER_OM, ORDER_QD | 모두 `PRODUCT_CD`로 통일 (entity @Column + JPO 필드명 동기) |
| Magic number `999999.999`, `0.95` 등 | action 곳곳 | `SdConstants` 상수 |
| `SDOrderLogic` reflection JPO ↔ Entity 매핑 | `slab-design-store/.../logic/SDOrderLogic.java` | `SdMapper` 명시적 mapper (record + 생성자) |
| 4+ level nested if | `SdOrderValidator`, 일부 action | early-return + 가드절로 평탄화 (행동 동일) |
| `@author 김XX (2017-08-21)` 주석 | 곳곳 | 제거 (작성자 메타 무의미) |
| 주석 처리된 코드 블록 | 곳곳 | 제거 |
| H/한 mixed 주석 | 곳곳 | 한국어 주석만 유지 (의미 명확한 경우), 무의미 주석 제거 |
| 중복 로직 | 일부 action에 산재 | DRY 가능한 곳 only — 위험 시 보수적으로 유지 |

**보존 (절대 안 건드림)**:
- 21-step 알고리즘 순서 / 산출 결과
- DG001-005 / DG101-109 에러 코드 의미론
- 8-char `confirmedPlantCd` 위치 인코딩
- 누적 실수율 곱 공식
- EDGING `*` wildcard fallback
- `_1` suffix 컬럼 (SLAB_RESULT 의 TARGET_WIDTH_1, TARGET_LENGTH_1, SLAB_WGT_1)
- 12-digit zero-padded slabNo

청소 작업은 **각 step별 단위테스트가 통과하는 한도 내에서**만 진행. 알고리즘 동일성이 청소보다 우선.

---

## 8. 검증 (Definition of Done)

v2가 완성됐다고 말하려면:

1. `./mvnw clean verify` 가 BUILD SUCCESS + 모든 테스트 PASS (Tier 1, 2, 3)
2. `./mvnw spring-boot:run -pl slab-design-boot` 후 `http://localhost:8080/swagger-ui.html` 접속 가능
3. `POST /api/sd/working/single` 5개 시나리오 모두 200 응답 + 골든 일치
4. `POST /api/sd/working/batch?cmpCd=K&orgCd=K01` 응답에 5건 처리 (S1-S3, S5는 success, S4는 skip)
5. v1 (`sample-repos/slab-design-real/`) 파일 0개 변경
6. onTong 다른 영역 (`backend/`, `frontend/`, `data/`, `scripts/`, `toClaude/<section>/`) 0개 변경
7. v2가 자체 완결: 외부 의존성은 JDK 21만 (Maven Wrapper 포함)

---

## 9. Open Questions

현 시점 미해결 항목 없음. 모든 의사결정은 사용자와 합의 완료.

만약 구현 중 새 결정이 필요하면 PLAN.md의 해당 step에 옵션 + 추천을 적고 사용자 승인을 받는다.
