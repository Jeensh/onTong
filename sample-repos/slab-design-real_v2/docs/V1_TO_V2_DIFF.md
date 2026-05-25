# v1 → v2 변경 매핑

`sample-repos/slab-design-real/` (v1, read-only) → `sample-repos/slab-design-real_v2/` (이 디렉토리). 알고리즘 출력이 동일한 한도 내에서 **drama DNA 청소 + 자체 완결 실행 환경 + 시뮬레이션 검증 인터페이스**를 추가했다.

요지: 21-step 알고리즘 자체는 v1과 v2가 동일한 결과를 낸다. 변경된 건 그 주변 wiring(빌드/DB/모듈 패키지/테스트/REST 표면)이다.

---

## 1. 보존 (절대 안 건드림)

알고리즘 정합성에 직결되는 다음 항목들은 v1을 그대로 옮겼다.

- 21-step 순서와 step별 결과 (한 step의 출력이 다음 step의 입력)
- DG 코드 의미론
  - DG001: 재고주문 차단 (`STOCK_CODE = 1`)
  - DG002: 주문 폭/길이 양수 위반
  - DG003: 포장 단중 범위 정합성
  - DG004: 설계대기량 vs 포장 단중 cross-check
  - DG005: 작업 기한일 정합성
  - DG101: CAST_SPEC 매칭 실패
  - DG102: HR_SPEC 매칭 실패
  - DG103: EDGING_GROUP 매칭 실패
  - DG104/DG105: 산정 폭/길이 범위 invalid
  - DG106/DG107: HR_MIN_WGT/HR_MAX_WGT lookup 실패
  - DG108: A-a 루프 silent control signal (history 미적재)
  - DG109: A-a 루프 최종 비수렴
- 8-char `confirmedPlantCd` 위치 인코딩 (SM/HR/HRF/CR/ANL1/ANL2/GAL/CRF)
- 누적 실수율 곱 공식 (활성 공정 productivity 곱)
- `EDGING_SPEC.EDGING_GROUP_CD = '*'` wildcard fallback
- `_1` suffix 컬럼 (SLAB_RESULT의 `SLAB_WIDTH_1`, `SLAB_LENGTH_1`, `SLAB_WGT_1`, …)
- 12-digit zero-padded `slabNo`
- 4 모듈 구성: boot ▶ facade ▶ feature ▶ store

---

## 2. drama DNA 청소

v1이 의도적으로 심어둔 "더러운 코드" 패턴 중 알고리즘 동일성을 해치지 않는 선에서 정리.

| v1 패턴 | v1 위치 | v2 처리 |
|--------|---------|---------|
| `PRODUCT_TYPE_CD` / `PRODUCT_NAME_CD` / `PRODUCT_KIND_CD` 혼재 | ORDER_OS / ORDER_OM / ORDER_QD JPO | 모두 `PRODUCT_CD`로 통일 (`@Column` + getter/setter 동기) |
| Magic number `999999.999`, `0.95`, `7.82`, `12`(slabNo digits) | action 곳곳 | `SdConstants` 상수 (`NO_UPPER_BOUND`, `DEFAULT_PRODUCTIVITY`, `DEFAULT_SPECIFIC_GRAVITY`, `SLAB_NO_DIGITS`, `PROC_CODES[]`) |
| `SDOrderLogic` reflection JPO ↔ Entity 매핑 | `slab-design-store/.../logic/SDOrderLogic.java` | 명시적 setter 매핑 (실패 시 컴파일 에러 — 리플렉션 silent skip 제거) |
| 4+ level nested if | `SdOrderValidator` 등 | early-return / 가드절로 평탄화. 분기 결과 동일성 단위테스트로 보증 |
| `@author 김XX (2017-08-21)` 주석 | 곳곳 | 제거 (작성자 메타 무의미) |
| 주석 처리된 코드 블록 / 운영 티켓 번호 / TODO 미정 메모 | 곳곳 | 제거 |
| 한/영 혼합 주석 의미 없는 것 | 곳곳 | 제거. 의미 명확한 한국어 주석은 유지 |

청소 작업은 단위테스트(70개 + 21 action class) 통과 한도 내에서만 진행. 알고리즘 동일성이 청소보다 우선.

---

## 3. 인프라 변경

| 영역 | v1 | v2 |
|------|----|----|
| DB | Oracle (compile-time only — 실행 안 됨) | H2 in-memory (`MODE=Oracle`) — 실행됨 |
| DDL | 별도 SQL 미제공 | `spring.jpa.hibernate.ddl-auto: create-drop` (JPA가 entity → table 생성) |
| 시드 | 없음 | `db/seed/01_master.sql` (master) + `02_orders.sql` (5 시나리오 ORDER_*) |
| ORM | JPA + 일부 MyBatis 잔재 | JPA만 (MyBatis 의존성 제거) |
| Kafka | spring-cloud-stream-kafka 의존성 (사용 안 됨) | 의존성 제거 |
| Oracle JDBC | `com.oracle.database.jdbc:ojdbc11:23.6.0.24.10` | 제거 |
| Spring Cloud | `2024.0.0` (사용 안 됨) | 제거 |
| Swagger | 없음 | `springdoc-openapi-starter-webmvc-ui:2.6.0` + `/swagger-ui.html` |
| 테스트 | 없음 (`mvn package -DskipTests`만 통과) | 80개 (Tier 1 unit 75 + Tier 3 integration 5) — JUnit 5 + Mockito + AssertJ + RestAssured |
| 패키지 | `com.example.slabdesign.store.sd.*.{oracle.jpo, oracle.repository}` (Oracle 명시) | `com.example.slabdesign.store.sd.*.{jpo, repository}` (DB 종속 제거) |
| 진입 모듈 | `slab-design-boot` (실행 시 DataSource 미설정으로 fail) | `slab-design-boot` (H2로 즉시 실행) |

---

## 4. REST API 표면 변경

v1은 1개의 진짜 endpoint(`POST /api/sd/working/batch`) + 빈 placeholder controller 3개. v2는 10+ endpoint 살아있음.

| Method | Path | v1 | v2 |
|--------|------|----|----|
| `POST` | `/api/sd/working/batch` | ✓ (DB 없어 실행 fail) | ✓ |
| `POST` | `/api/sd/working/single` | ✗ | ✓ |
| `POST` | `/api/sd/working/single?trace=true` | ✗ | ✓ (시뮬레이션 검증 인터페이스) |
| `GET`  | `/api/sd/orders` | ✗ | ✓ |
| `GET`  | `/api/sd/orders/{cmpCd}/{orgCd}/{orderNo}` | ✗ | ✓ |
| `GET`  | `/api/sd/results` | ✗ | ✓ |
| `GET`  | `/api/sd/results/{slabNo}` | ✗ | ✓ |
| `GET`  | `/api/sd/history` | placeholder (empty class) | ✓ |
| `GET`  | `/api/sd/history/slab/{slabNo}` | ✗ | ✓ |
| `POST` | `/api/sd/seed/reset` | ✗ | ✓ |
| `GET`  | `/api/sd/seed/scenarios` | ✗ | ✓ |
| `GET`  | `/api/sd/std/*` | placeholder | 제거 |
| `GET`  | `/api/sd/analysis/*` | placeholder | 제거 |

---

## 5. v2가 새로 도입한 것

| 영역 | 설명 |
|------|------|
| `TraceCollector` + `StepTrace` record | step 단위 input/output snapshot. `wrap()`이 OK/FAIL 자동 적재. nullable 주입 → trace 미사용 시 zero overhead |
| Phase tagging | `ONE_SHOT` / `AA_LOOP` / `FINAL` / `SAVE` / `PHASE_1`(validation) — 시뮬레이션 비교 시 step 그룹 식별 |
| 5 Golden Scenarios + `ScenarioGoldenTest` | 21-step 통합 회귀. RestAssured + JSON byte-equal (휘발성 필드 normalize) |
| `GOLDEN_REGEN=true` envvar | 의도된 알고리즘 변경 시 골든 일괄 재생성 |
| `SdSeedController` | DB 초기화 + 시나리오 meta 조회 |
| `SdConstants` | v1의 magic number 상수화 |
| `SwaggerConfig` + `@Operation`/`@Tag` annotation | 컨트롤러 self-documenting |
| Single design entry (`SdDriver.singleDesign`) | 진도 필터 미적용으로 골든 시나리오 / API 단건 호출 가능 |

---

## 6. v1 관점 breaking changes (단순 추가가 아닌 의미 변경)

### 6.1 `orgCd` 의미

- v1 placeholder 시드/문서: `K01` (3자)
- v2 실제: `1` (`ORDER_OS.ORG_CD` 컬럼 길이 1, JPA `@Column(length=1)`)
- 영향: v1 문서/예시에 보였던 `orgCd=K01`은 v2에서 그대로 쓰면 `data too long for column ORG_CD` fail. 모든 curl/seed/test가 `orgCd=1`.

### 6.2 `PlantMappingService`에 `'K'` 키 추가

- v1: `A`/`B`/`C`/`D` 4개만 매핑 (`A→CC1/M1` 등). 시드도 없으니 의미 없음.
- v2: 골든 fixture가 `confirmedPlantCd[0] = 'K'` 사용 → `'K' → CC1/M1` 매핑 추가. 그렇지 않으면 step 1 CAST_SPEC lookup이 DG101로 fail.

### 6.3 무게 단위 통일 — 모두 kg

- v1: 명시 단위 표기 부재. 일부 코드가 ton 가정한 듯 보였음 (drama DNA의 일부).
- v2: 무게 컬럼 (designPendQty, pkgWgt*, orderWgt*, slabWgt*, splitWgt*)을 **모두 kg**로 통일. `SdFirstWeightAction`의 `mm³ × g/cm³ × 1e-6 → kg` 공식이 시드와 정합.
- 영향: 시드 값(`12000`, `25000`, `55000` 등)은 모두 kg. v1 코드를 ton으로 읽은 적이 있다면 1000× 차이 주의.

### 6.4 `SDOrderLogic` 매핑 메커니즘 변경

- v1: reflection 기반 (필드 이름 일치 시 자동 복사). 한 쪽이 빠지면 silent skip → 디버그 어려움.
- v2: 명시적 setter 호출. JPO에 필드가 빠지면 컴파일 에러. 의도된 매핑만 명시.

### 6.5 `slabResults` 응답 길이 (단건 endpoint)

- `POST /api/sd/working/single` 응답 `slabResults`는 분할이 N매여도 길이 ≤ 1.
  알고리즘이 마지막 Slab entity 한 개만 반환하기 때문. N개 row 보려면 `GET /api/sd/results?...&orderNo=...` 사용.
- v1엔 단건 endpoint 자체가 없었으므로 새 quirk.

---

## 7. 시드 fixture 구축 시 발견 사항 (U14 findings)

골든 시나리오를 실제 통과하게 만들기 위해 시드를 다음과 같이 조정.

### 7.1 `confirmedPlantCd[1]`은 반드시 `'1'`..`'5'`

`SelectedHrTgtWidthResolver`가 이 char를 `ORDER_QD.HR_TGT_WIDTH_N` 컬럼 인덱스로 사용. 동시에 `HR_PLANT_CD` 값으로도 쓰인다 (HR_SPEC PK 일부). 따라서:

- 5 시나리오 모두 pos 1 = `'1'`
- `HR_SPEC` 시드 row의 `HR_PLANT_CD = '1'` 1개로 충분
- `ORDER_QD`의 5 컬럼(`HR_TGT_WIDTH_1`..`_5`)은 모두 동일 값으로 채움 (resolver가 어느 컬럼을 골라도 같은 값)

### 7.2 시드 무게 일관성 — kg 재정렬

초기 시드는 `designPendQty=10` 처럼 ton 가정한 값들이 섞여 있었음. `SdFirstWeightAction`의 dimension 변환 공식과 충돌해 `firstWgtHigh`가 무한대 가까이 튐. → 모든 무게를 kg로 통일하고 시드 값을 재계산.

### 7.3 S4 — DG004 trigger 조건

`SdOrderValidator.checkDesignPendQty`는 `pkgWgtLow > designPendQtyHigh`일 때 DG004를 던진다. 따라서 시드:

- `designPendQtyHigh = 12,000`
- `pkgWgtLow = 20,000` (Low > pendHigh!)

다른 cross-check가 먼저 trip하지 않도록 `pkgWgtLow ≤ pkgWgtHigh = 22,000`도 충족.

### 7.4 S2 — Slab 매수가 4가 아닌 3

SPEC.md 초고는 4매 가정이었으나 시드 `CAST_SPEC.LENGTH_HIGH = 12000`이 `maxSplitCountUpper`를 캡 → 골든 결과는 3매. SPEC.md(`§4.3`)와 위 기록이 충돌하면 골든 파일(`S2.json`)이 truth.

### 7.5 `SeedService` TRUNCATE 대상 = 14 테이블

12 master + 2 결과/이력. `SET REFERENTIAL_INTEGRITY FALSE`로 FK 임시 해제 후 일괄 TRUNCATE → master/orders SQL 재실행. SLAB_RESULT, SLAB_DESIGN_HIST는 비워둠 (API 호출이 채움).

### 7.6 `ScenarioGoldenTest` `@BeforeEach`가 reset 호출

각 시나리오 시작마다 `POST /api/sd/seed/reset`을 호출 → SLAB_RESULT/HIST가 비어진 상태에서 `singleDesign`이 1순위로 row를 만든다. 이게 없으면 시나리오 간 PK 충돌 / slabNo sequence 누적 → 골든 byte-equal 실패.

---

## 8. 한 줄 요약

> v2는 v1의 21-step 알고리즘은 **그대로**, 그 주변(빌드/DB/REST/테스트/매직넘버)을 청소했다. 외부에서 보이는 행동 변화는 (a) 더 많은 endpoint, (b) trace 응답, (c) 단위 일관성, (d) `orgCd=1` 그리고 (e) `'K'` smCd 매핑 추가뿐. 알고리즘 출력은 시나리오 5개 모두 골든 fix.
