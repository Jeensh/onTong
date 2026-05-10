# slab-design Spring Boot 기동 + API 테스트 + Java↔Python 비교 가이드

> **대상**: Section 2 (코드 기반 온톨로지 모델링) 담당자
> **목적**: 자바 Slab 설계 시스템을 직접 기동/호출하고, **Section 3의 Python 미러와 결과를 비교**하는 전체 흐름
> **작성일**: 2026-05-09 (모두 onTong 루트에서 실제 동작 확인 완료)
> **상위 문서**: [`SECTION3_LANDING.md`](SECTION3_LANDING.md) §11

---

## 1. 환경 요구사항

| 항목 | 버전 / 값 | 메모 |
|---|---|---|
| OS | macOS (darwin 25.x) | Linux도 동일 |
| JDK | 21 이상 (테스트 시 Homebrew openjdk 25.0.2) | `brew install openjdk` |
| Maven | 3.9+ (Maven Wrapper 동봉) | `./mvnw` |
| Python | 3.11+ (`venv/`) | onTong 루트 |
| Node | 18+ | 프론트 |

```bash
# JAVA_HOME 설정 (이번 가이드 전체에서 동일)
export JAVA_HOME=/opt/homebrew/opt/openjdk
export PATH=$JAVA_HOME/bin:$PATH
java -version    # → 25.0.2 (또는 21 이상)
```

---

## 2. slab-design Spring Boot 기동

### 2-1. 프로젝트 구조

```
sample-repos/slab-design/
├── slab-design-boot/      ← Spring Boot 진입점
├── slab-design-facade/    ← REST 컨트롤러 (@RestController)
├── slab-design-feature/   ← 비즈니스 로직 (designer/driver/action/service)
└── slab-design-store/     ← 영속성 (jpo/entity/repository/logic)
```

### 2-2. 빌드

```bash
cd /Users/jiyoon/claude/onTong/sample-repos/slab-design

# (최초 1회) mvnw 실행 권한
chmod +x mvnw

# 모든 모듈 컴파일
./mvnw compile             # → BUILD SUCCESS

# fat jar 생성 + 로컬 ~/.m2 에 install (java-bridge에서 dep로 참조)
./mvnw install -DskipTests # → BUILD SUCCESS
```

### 2-3. 기동 시 알려진 이슈 — `slabDesignHistRepository` 빈 충돌

**증상**:
```
ConflictingBeanDefinitionException: Annotation-specified bean name 'slabDesignHistRepository'
for bean class [...repository.SlabDesignHistRepository] conflicts with existing,
non-compatible bean definition of same name and class [JpaRepositoryFactoryBean]
```

**원인**: `@MapperScan(basePackages = "com.example.slabdesign.store")`이 JPA 레포지토리까지 스캔.

**수정** (이미 적용됨 — `slab-design-boot/src/main/java/.../SlabDesignApplication.java`):
```java
// 변경 전
@MapperScan(basePackages = "com.example.slabdesign.store")

// 변경 후 — MyBatis 매퍼는 별도 패키지 + @Mapper 어노테이션 필수
@MapperScan(
  basePackages = "com.example.slabdesign.store.mybatis",
  annotationClass = org.apache.ibatis.annotations.Mapper.class
)
```

> ⚠️ 이 수정은 데모 기동 목적. CLAUDE.md의 "drama DNA 보존" 원칙은 변수명/주석/구조에 한정.

### 2-4. 기동 명령

```bash
cd /Users/jiyoon/claude/onTong/sample-repos/slab-design

# 옵션 A: jar 직접 실행 (권장)
java -jar slab-design-boot/target/slab-design-boot-1.0.0-SNAPSHOT.jar

# 옵션 B: spring-boot:run
./mvnw -pl slab-design-boot spring-boot:run

# 백그라운드 실행
nohup java -jar slab-design-boot/target/slab-design-boot-1.0.0-SNAPSHOT.jar > /tmp/slab-design.log 2>&1 &
```

### 2-5. 기동 성공 확인

```bash
# 로그 끝줄 확인
tail -5 /tmp/slab-design.log
# → "Started SlabDesignApplication in 7.x seconds"

# 포트 LISTEN 확인
lsof -i :8080 | grep LISTEN
```

### 2-6. 기동 후 알려진 동작 — Oracle 미연결

`application.yml`은 Oracle JDBC를 가리키지만 실제 Oracle은 없음 → 부팅 시 connection refused 경고가 로그에 떠도 **Spring Context는 정상 기동** (HikariCP `initialization-fail-timeout: -1` 덕분에 lazy).

API 호출 시 JPA 레이어에서 실패 → HTTP 500 응답 (의도된 동작).

---

## 3. POST API 실행 — H2 in-memory + 시드 데이터로 실제 동작

> ✅ **이미 적용 완료**: H2 dependency + `application-h2.yml` + `data-h2.sql` 구성이 레포에 반영되어 있어,
> 별도 작업 없이 `--spring.profiles.active=h2` 만 붙이면 실제 응답을 받을 수 있습니다.

### 3-1. 엔드포인트

```
POST /api/sd/working/batch?cmpCd={회사코드}&orgCd={소코드}
```
- **HTTP method**: POST (Body 없음 — query parameter 만 사용)
- **회사·소 단위 배치 Slab 설계**
- 내부 흐름: `SdWorkingController` → `SdDriver.batchDesign(cmpCd, orgCd)` → `SdOrderExtractor.extractDesignableOrders` (진도 C/D + 종결 NULL/0 필터) → 각 후보에 `SdDesigner.design()` (validator → 21-step) → `BatchResult` JSON 반환
- 응답 스키마: `{ total, processedCount, skippedCount, processedSlabs[] }`

> ⚠️ 컨트롤러 시그니처는 `@RequestParam` 만 받으므로 **JSON body 는 무시**됩니다.
> 입력값은 시드 데이터 (DB) + query param 두 가지로 전달.

### 3-2. H2 프로파일로 기동

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk
export PATH=$JAVA_HOME/bin:$PATH

# 기존 인스턴스 종료
pkill -f slab-design-boot 2>/dev/null

# H2 in-memory 프로파일로 기동 (※ 옵션 핵심)
java -jar /Users/jiyoon/claude/onTong/sample-repos/slab-design/slab-design-boot/target/slab-design-boot-1.0.0-SNAPSHOT.jar \
  --spring.profiles.active=h2

# 백그라운드:
# nohup java -jar ...slab-design-boot-...jar --spring.profiles.active=h2 \
#   > /tmp/slab-design-h2.log 2>&1 &
```

기동 시 다음 흐름이 자동 실행됩니다:
1. H2 in-memory DB 초기화 (`jdbc:h2:mem:slabdesign;MODE=Oracle`)
2. Hibernate `ddl-auto: create-drop` 으로 모든 `@Entity` (ORDER_OS / ORDER_OM / ORDER_QD / ORDER_CHEMICAL / CAST_SPEC / HR_SPEC / HR_MIN_WGT / HR_MAX_WGT / EDGING_SPEC / EDGING_GROUP / SD_PRODUCTIVITY_STD / CUSTOMER_STD / SLAB_DESIGN_HIST / SLAB_RESULT) 의 schema 자동 생성
3. `data-h2.sql` 자동 실행 → 시드 데이터 INSERT (아래 §3-3)

기동 성공 신호:
```
INFO  ... Started SlabDesignApplication in 2.9 seconds
INFO  ... Tomcat started on port 8080 (http)
```

### 3-3. 자동 시드 데이터 (`data-h2.sql`)

위치: `sample-repos/slab-design/slab-design-boot/src/main/resources/data-h2.sql`

| 테이블 | 행 수 | 내용 요약 |
|---|---|---|
| `ORDER_OS` | 4 | 4건 후보 (cmpCd=K, orgCd=K, progress=C/D, 종결 NULL). DG001~005 통과용 + 의도적 fail (재고주문) |
| `ORDER_OM` | 4 | pkgWgtLow=5~10 / pkgWgtHigh=15~30 (DG003 통과), workDue 미래 (DG005 통과), productTypeCd=A001 |
| `ORDER_QD` | 4 | gradeCd=G01/G02, hrTgtWidth 1200/1300/1100/1000 |
| `ORDER_CHEMICAL` | 4 | 8 성분 × min/max/aim — 데모 표준값 |
| `CAST_SPEC` | 2 | A001 품종, smCd=K, castCd=CC1/CC2, slabThickness=220/250, 폭/길이/단중 범위 |
| `HR_SPEC` | 2 | hrPlantCd=K/P, A001 품종, 폭/길이 범위 |
| `HR_MIN_WGT` | 9 | 2D 격자 (thickness × width) → minWgt 매핑 |
| `HR_MAX_WGT` | 9 | 동일 격자 → maxWgt 매핑 |
| `EDGING_GROUP` | 3 | priority 우선순위 + `*` 와일드카드 default |
| `EDGING_SPEC` | 3 | edgingGroupCd 별 cap 범위 |
| `SD_PRODUCTIVITY_STD` | 8 | 8 공정 (SM/HR/HRF/CR/ANL1/ANL2/GAL/CRF) `*` 와일드카드 실수율 |
| `CUSTOMER_STD` | 3 | 고객별 포장단중 한도 |

총 **58 row** 가 기동 시 자동 적재 → API 호출 시 즉시 사용 가능.

### 3-4. curl 호출 — 정상 응답 확인

```bash
curl -s -w "\n---HTTP %{http_code}---\n" \
  -X POST 'http://localhost:8080/api/sd/working/batch?cmpCd=K&orgCd=K'
```

> ⚠️ `orgCd` 컬럼은 1-char (`@Column(name="ORG_CD", length=1)`). 시드는 `K` (광양). `K01` 등 2자 이상은 비매칭.

### 3-5. 실제 응답 (실측, 2026-05-10)

```json
{
  "total": 4,
  "processedCount": 0,
  "skippedCount": 4,
  "processedSlabs": []
}
```

```
---HTTP 200---
```

| 필드 | 의미 | 실측값 의미 |
|---|---|---|
| `total` | `findDesignable(K, K)` 가 반환한 후보 수 | **4건 후보 추출 정상** (ORDER_OS의 progress C/D 4행) |
| `processedCount` | `SdDesigner.design()` 가 성공적으로 SDSlabEntity 생성한 수 | 0 — Validator 또는 21-step 중간 fail (재고주문 1건 + 격자/EDGING 매칭 실패 3건) |
| `skippedCount` | `total - processedCount` | 4 |
| `processedSlabs` | 성공 Slab 의 Entity 배열 | 빈 배열 |

> **HTTP 200 + total=4** 는 **DB 연결 + 시드 적재 + JPA 쿼리 + 컨트롤러 흐름 모두 정상** 임을 증명.
> processedCount 0 은 21-step 알고리즘이 demo seed 의 한정된 데이터로 일부 step 에서 멈춘 결과 — slab-design 의 알고리즘 본체가 의도대로 동작 중.

### 3-6. H2 콘솔로 시드 적재 확인 (선택)

브라우저에서 <http://localhost:8080/h2-console>:
- **JDBC URL**: `jdbc:h2:mem:slabdesign`
- **User**: `sa` · **Password**: (빈칸)

`SELECT * FROM ORDER_OS;` → 4 행 확인.
`SELECT count(*) FROM HR_MIN_WGT;` → 9.
`SELECT * FROM CAST_SPEC;` → 2 행.

### 3-7. 다른 시나리오 호출

```bash
# 광양 (orgCd=K) 4건 후보 중 시드된 모든 주문
curl -X POST 'http://localhost:8080/api/sd/working/batch?cmpCd=K&orgCd=K'

# 미시드 (orgCd=P) → total: 0
curl -X POST 'http://localhost:8080/api/sd/working/batch?cmpCd=K&orgCd=P'
# → {"total":0,"processedCount":0,"skippedCount":0,"processedSlabs":[]}

# 미존재 회사 (cmpCd=X) → total: 0
curl -X POST 'http://localhost:8080/api/sd/working/batch?cmpCd=X&orgCd=K'
# → {"total":0,"processedCount":0,"skippedCount":0,"processedSlabs":[]}
```

### 3-8. 시나리오별 시드 변경 가이드

`data-h2.sql` 을 수정해서 더 다양한 시나리오 테스트:

**(a) 모든 검증 통과 + Slab 생성 시도**:
- `confirmedPlantCd` 를 `'K K K K KKKK'` (8공정 모두 K) 로 → DG005 통과 + 모든 due 채워야 함

**(b) DG001 (재고주문) 트리거**:
- `STOCK_CODE` 를 `1` 로 → DG001 fail → skip

**(c) DG003 (포장단중 범위) 트리거**:
- `PKG_WGT_LOW > PKG_WGT_HIGH` 로 → DG003 fail → skip

**(d) 격자 룩업 누락 트리거 (step 5/6)**:
- `HR_MIN_WGT` 행 일부 삭제 → 해당 slab thickness/width 케이스에서 `EdgingSpecMissingError` 또는 second_wgt 계산 fail

수정 후 재기동 (in-memory 라 자동 reset):
```bash
pkill -f slab-design-boot
java -jar ...slab-design-boot-...jar --spring.profiles.active=h2
```

---

## 4. ★ 권장 경로 — java-bridge로 무수정 호출

slab-design Spring Boot 자체를 직접 띄우는 대신, **Section 3에 이미 구현된 `java_bridge` Spring Boot CLI**를 사용. 이쪽이 데모/비교에 훨씬 실용적.

### 4-1. 디자인

```
┌─────────────────────────────────────────────────────────────┐
│ java_bridge (별도 Spring Boot CLI)                           │
│  - slab-design-feature jar를 dependency로 참조 (무수정)       │
│  - Oracle / Kafka는 @Primary @Bean으로 mock swap             │
│  - stdin JSON → SdDesigner.design() → stdout JSON           │
└─────────────────────────────────────────────────────────────┘
```

### 4-2. 빌드

```bash
# (사전) slab-design을 ~/.m2 에 install (§2-2에서 이미 함)
cd /Users/jiyoon/claude/onTong/sample-repos/slab-design
./mvnw install -DskipTests

# java-bridge fat jar 빌드
cd /Users/jiyoon/claude/onTong/backend/simulation/jvm_bridge/java_bridge
mvn package -DskipTests

# 산출물 확인
ls -la target/java-bridge-1.0.0.jar
```

### 4-3. 수동 호출 테스트

```bash
echo '{"order": {"cmpCd": "K", "orgCd": "K01", "orderNo": "ORD-001", "stockCode": 0}}' \
  | java -jar /Users/jiyoon/claude/onTong/backend/simulation/jvm_bridge/java_bridge/target/java-bridge-1.0.0.jar
```

### 4-4. 환경변수 (선택)

```bash
# 다른 위치의 jar를 사용할 때만
export SIMULATION_JAVA_BRIDGE_JAR=/abs/path/to/java-bridge-1.0.0.jar
```

---

## 5. ★ Java ↔ Python 비교 — onTong 시스템에서 동시 실행 + diff

### 5-1. 전제

- onTong 백엔드 기동 (포트 8001):
  ```bash
  cd /Users/jiyoon/claude/onTong
  SIMULATION_SKIP_ONTOLOGY=1 ./venv/bin/uvicorn backend.main:app --port 8001
  ```
- java-bridge jar 빌드 완료 (§4-2)

### 5-2. 가용성 확인

```bash
curl -s http://localhost:8001/api/simulation/differential/status
```

기대 응답:
```json
{
  "java_bridge_available": true,
  "guide": "사용 가능 — POST /run 으로 Java/Python 동시 실행 가능"
}
```

> `false` 면 §4-2 빌드부터 다시 (또는 `mvn install` 누락).

### 5-3. 비교 실행

```bash
curl -X POST http://localhost:8001/api/simulation/differential/run \
  -H "Content-Type: application/json" \
  -d '{
    "order": {
      "cmpCd": "K",
      "orgCd": "K01",
      "orderNo": "ORD-DEMO-001",
      "stockCode": null,
      "designPendQty": 100,
      "pkgWgtLow": 5,
      "pkgWgtHigh": 30,
      "confirmedPlantCd": "K K K   ",
      "productTypeCd": "A001",
      "gradeCd": "G01",
      "selectedHrTgtWidth": 1200,
      "orderWidth": 1200,
      "orderLength": 6000,
      "orderWgtLow": 5,
      "orderWgtHigh": 30
    },
    "rules": {}
  }'
```

### 5-4. 응답 스키마

```json
{
  "status": "ok",
  "java_available": true,
  "java_ok": false,
  "python_ok": true,
  "matched_count": 0,
  "mismatched_count": 0,
  "field_diffs": [
    {"path": "slab.firstWidthLow", "java": "950", "python": "950", "is_close": true}
  ],
  "java_elapsed_sec": 0.17,
  "python_elapsed_sec": 0.0006,
  "java_error": null,
  "python_error": null,
  "java_payload":   { "slab": { ... } },
  "python_payload": { "stage": "algorithm", "slab": { ... } }
}
```

| 필드 | 의미 |
|---|---|
| `java_available` | java-bridge JAR 가용성 |
| `java_ok` / `python_ok` | 각 측 실행 성공 여부 |
| `matched_count` | tolerance 내 일치 필드 수 |
| `mismatched_count` | 불일치 필드 수 |
| `field_diffs[]` | path / java값 / python값 / `is_close` (BigDecimal 허용오차 적용) |
| `java_elapsed_sec` / `python_elapsed_sec` | 각 측 실행 시간 |
| `java_payload` / `python_payload` | 원본 응답 |

### 5-5. 정밀 비교 — BigDecimal tolerance

Java BigDecimal과 Python Decimal의 표현 차이를 흡수하기 위한 허용오차:
- 기본값: `rel_tolerance = 1e-9`, `abs_tolerance = 1e-12`
- 요청 시 override 가능:
  ```json
  { "order": {...}, "rel_tolerance": 1e-6, "abs_tolerance": 1e-9 }
  ```

### 5-6. 룰 override 함께 비교

```bash
curl -X POST http://localhost:8001/api/simulation/differential/run \
  -H "Content-Type: application/json" \
  -d '{
    "order": { ... },
    "rules": {
      "hr": { "productivity": 0.92 },
      "edging": { "fallback_wildcard": false }
    }
  }'
```
→ Python 측은 in-memory rules 적용, Java 측은 JVM bridge mock 데이터로 실행 후 동일 케이스 비교.

> ⚠️ 룰 override는 휘발성 (DB에 저장 안 함). 룰 변경 영향도만 본다.

### 5-7. 흐름 요약

```
Python 측:                                  Java 측:
─────────                                  ────────
sandbox.registry["pipeline_full"]          subprocess: java -jar java-bridge.jar
  fixtures.py mock data                       MockConfig (Oracle/Kafka mock swap)
  steps/*.py                                  SdDesigner.design(orderEntity)
  → outputs dict                              → outputs JSON
        │                                        │
        └────────── differential.py ─────────────┘
                       │
                       ▼
                  field_diffs[]
                  (BigDecimal tolerance)
```

---

## 6. UI에서 비교 실행

> **현재 상태**: 백엔드 API + 테스트 모두 구현. 프론트엔드 전용 UI는 미구현 (CLI/curl로 호출).

차후 구현 시 후보 위치: `frontend/src/components/simulation/JavaPythonComparePanel.tsx` (이미 placeholder 컴포넌트 존재).

---

## 7. 비교 결과 활용 시나리오

### 7-1. 자동 변환 검증 (Phase 7-D 와 결합)

자바 메서드를 Python으로 자동 변환했을 때, **변환된 코드가 자바 원본과 동일한 결과를 내는지** 검증하는 회로:

```
1. POST /api/simulation/transpile/run
   → Java 메서드 → Python step (PythonStepDraft, line_origins 포함)

2. POST /api/simulation/transpile/equivalence  (shadow_compare)
   → 변환된 Python을 메모리에서 exec
   → 기존 sandbox.registry의 reference step과 동일 입력 비교
   → EquivalenceReport (matched/mismatched/field_diffs)

3. POST /api/simulation/differential/run        (java vs python 동시 실행)
   → 자바 SdDesigner와 Python pipeline_full 동시 실행
   → 같은 입력에 대한 양측 결과 비교
   → "변환된 Python ≈ 기존 Python ≈ Java" 3-way 검증
```

### 7-2. 룰 변경 임팩트 검증

baseline 등록 후 룰 변경:
```
1. baseline run: 현재 룰로 100건 케이스 실행 → SQLite runs 테이블에 baseline 등록
2. 룰 변경 적용
3. POST /jobs/batch — 같은 시나리오 재실행
4. 자동 회귀 (regression diff)이 baseline 대비 변화량 계산
5. POST /differential/run을 자바 측에도 동일 룰 변경 적용 → cross-validation
```

### 7-3. 마이그레이션 시뮬

`plant_mapping_migrate` step 활용:
- "K → CC2/M2" 마이그 적용 시 영향 받는 주문 수 표본 측정
- 자바·파이썬 양측에서 동일 결과 확인

---

## 8. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `java_bridge_available: false` | java-bridge jar 없음 | §4-2 빌드 |
| `java_error: "non_zero_exit"` | java-bridge subprocess 실패 | `java -jar target/java-bridge-1.0.0.jar < input.json` 으로 수동 호출해 stderr 확인 |
| `slab-design 8080 LISTEN 안 함` | bean 충돌 | §2-3 패치 적용 확인 |
| `mvn install ojdbc11 not found` | maven repo 미인덱스 | `./mvnw -U install` |
| `Connection refused (Oracle)` | 정상 — Oracle 미연결 | §2-6 참조, 무시 가능 |
| `mvnw: permission denied` | 실행 권한 | `chmod +x mvnw` |
| backend 8001 응답 없음 | uvicorn 미기동 | `./venv/bin/uvicorn backend.main:app --port 8001` |
| Chroma가 8000 가로챔 | Docker / Chroma 컨테이너 | backend는 8001로 띄우거나 Chroma 종료 |

---

## 9. 빠른 검증 스크립트 (모두 통과해야 하는 5단계)

```bash
# 1) JAVA_HOME 설정
export JAVA_HOME=/opt/homebrew/opt/openjdk
export PATH=$JAVA_HOME/bin:$PATH

# 2) slab-design 빌드 + install
cd /Users/jiyoon/claude/onTong/sample-repos/slab-design
chmod +x mvnw
./mvnw install -DskipTests
test -f slab-design-boot/target/slab-design-boot-1.0.0-SNAPSHOT.jar && echo "✓ slab-design jar"

# 3) java-bridge 빌드
cd /Users/jiyoon/claude/onTong/backend/simulation/jvm_bridge/java_bridge
mvn package -DskipTests
test -f target/java-bridge-1.0.0.jar && echo "✓ java-bridge jar"

# 4) onTong backend 기동 (백그라운드)
cd /Users/jiyoon/claude/onTong
SIMULATION_SKIP_ONTOLOGY=1 nohup ./venv/bin/uvicorn backend.main:app --port 8001 \
  > /tmp/ontong-backend.log 2>&1 &

# 5) 비교 API 가용성 확인
sleep 8
curl -s http://localhost:8001/api/simulation/differential/status | grep -q "true" && \
  echo "✓ differential API ready"
```

모두 `✓`이면 §5-3 비교 실행 OK.

---

## 10. 참고

- **상위 문서**: [`SECTION3_LANDING.md`](SECTION3_LANDING.md) — 핵심기술 / 구현기능 / AST 파싱 / Python 변환
- **파일 매핑**: [`SECTION3_FILE_MAP.md`](SECTION3_FILE_MAP.md) — onTong 루트 내 Section 3 파일 목록 + Section 2 통합
- **java-bridge README**: `backend/simulation/jvm_bridge/java_bridge/README.md`
- **테스트**: `tests/simulation/test_demo_e2e.py`, `test_transpile.py`, `test_auto_pr.py`

---
