# slab-design-real_v2

자체 완결 실행 가능한 21-step Slab 설계 데모 + 시뮬레이션 검증 baseline.

v1 (`sample-repos/slab-design-real/`)의 정적 fixture 한계를 넘어, **빌드/실행/REST 호출/단위·통합 테스트**가 모두 자체 완결되는 청결한 baseline. 외부 의존성은 JDK 21 하나뿐 (Maven Wrapper 동봉, H2 in-memory DB).

---

## 빌드 / 실행

요구사항: **JDK 21**. Maven Wrapper(`./mvnw`) 동봉이라 Maven 별도 설치 불필요.

`JAVA_HOME`을 JDK 21로 export 한 뒤 사용 (예: macOS Corretto 21).

```bash
export JAVA_HOME=/Users/donghae/Library/Java/JavaVirtualMachines/corretto-21.0.4/Contents/Home

# 1. 빌드 + 모든 테스트 (Tier 1 unit + Tier 3 golden integration; 80 tests)
./mvnw clean verify

# 2. 의존 모듈 jar 로컬 publish (boot 모듈 spring-boot:run 진입 전 최초 1회)
./mvnw install -DskipTests -am

# 3. 서버 기동 (port 8080)
./mvnw -pl slab-design-boot spring-boot:run
```

---

## API 탐색

서버 기동 후:

- Swagger UI: <http://localhost:8080/swagger-ui.html>
- H2 Console: <http://localhost:8080/h2-console>
  - JDBC URL: `jdbc:h2:mem:slabdesign`
  - User: `sa`, Password: 비움

API 사용 예시는 `docs/API.md` 참고.

---

## 5개 골든 시나리오

모두 `cmpCd=K`, `orgCd=1` 사용. 자세한 입력 / 기대 출력은 `docs/SCENARIOS.md`.

| ID | orderNo | confirmedPlantCd | 의도 | 기대 결과 |
|----|---------|------------------|-----|----------|
| S1 | `ORD20260510001` | `K1 K    ` (SM/HR/CR) | 일반 COIL 골든 패스 | Slab 1매 (split=1) |
| S2 | `ORD20260510002` | `K1      ` (SM/HR) | 다중 Slab + A-a inner loop | Slab 3매 (split=2 → final split adjust) |
| S3 | `ORD20260510003` | `K1KK    ` (SM/HR/HRF/CR) | A-a inner-loop fallback | Slab 2매 (split=1 → A-a recalc) |
| S4 | `ORD20260510004` | `K1      ` (SM/HR) | DG004 validator cross-check fail | 설계 실패 + history 1행 |
| S5 | `ORD20260510005` | `K1     K` (SM/HR/CRF) | 최소 활성 공정 | Slab 1매 |

---

## 시뮬레이션 검증 인터페이스

`POST /api/sd/working/single?trace=true` 응답의 `trace[]`가 시뮬레이션 정답 인터페이스다.
onTong이 ontology 기반으로 생성한 Python 코드를 동일 입력으로 실행해 step별 입출력을 비교 가능.

```bash
curl -s -X POST 'http://localhost:8080/api/sd/working/single?trace=true' \
  -H 'Content-Type: application/json' \
  -d '{"cmpCd":"K","orgCd":"1","orderNo":"ORD20260510001"}' | jq '.trace[0]'
```

`StepTrace` 스키마(`docs/API.md` 참고): `step`, `stepName`, `phase`, `iteration`, `input`, `output`, `status`, `errorCode`, `errorMessage`, `elapsedMs`.

---

## 골든 갱신

알고리즘 의도된 변경 시(예: 새 step 추가, 정렬 기준 변경) 골든을 재생성한다:

```bash
GOLDEN_REGEN=true ./mvnw -pl slab-design-boot test -Dtest=ScenarioGoldenTest
```

생성된 `slab-design-boot/src/test/resources/golden/S{1..5}.json`을 사람이 검토 후 commit.

휘발성 필드(비교 시 무시): `trace[].elapsedMs`, `slabResults[].slabNo`, `slabResults[].createdAt`, `trace[].input.slabNo`, `trace[].output.slabNo`.

---

## v1과의 관계

v1(`sample-repos/slab-design-real/`)을 baseline으로 drama DNA 청소 + H2 + 5 golden scenario + step trace를 추가한 깨끗한 fixture. **알고리즘 출력은 동일**, 주변 wiring(빌드/DB/API/테스트)만 정돈.

상세: `docs/V1_TO_V2_DIFF.md`.

---

## 추가 문서

- `docs/SPEC.md` — 설계 명세
- `docs/PLAN.md` — 구현 계획 / step 분해
- `docs/API.md` — REST API curl 예시 + StepTrace 스키마
- `docs/SCENARIOS.md` — 5개 골든 시나리오 상세
- `docs/V1_TO_V2_DIFF.md` — v1 → v2 변경 매핑
