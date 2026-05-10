# API Reference — slab-design-real_v2

REST endpoint 카탈로그. 모든 예시는 서버가 `http://localhost:8080`에서 기동된 상태를 가정한다.

대화형 탐색은 Swagger UI(<http://localhost:8080/swagger-ui.html>) 를 권장. 이 문서는 curl 한 줄 예시 + 응답 발췌 모음.

공통:

- 모든 시나리오는 `cmpCd=K`, `orgCd=1` (orgCd 컬럼 길이 1).
- JSON `Content-Type: application/json`.
- 응답 4xx/5xx는 Spring 기본 에러 포맷.

---

## 1. Working — 21-step 슬랩 설계 실행

### 1.1 `POST /api/sd/working/batch`

회사·소 단위 배치 (v1 호환). `findDesignable()`이 잡는 모든 후보 주문을 차례로 설계.

```bash
curl -s -X POST 'http://localhost:8080/api/sd/working/batch?cmpCd=K&orgCd=1' | jq .
```

응답(`SdDriver.BatchResult`):

```json
{
  "total": 5,
  "processedCount": 4,
  "skippedCount": 1,
  "processedSlabs": [
    { "slabNo": "000000000001", "orderNo": "ORD20260510001", "...": "..." }
  ]
}
```

`skippedCount`는 알고리즘이 fail로 종결한 주문 수(예: S4 DG004). 처리된 슬랩의 마지막 한 개씩만 `processedSlabs`에 들어간다(각 주문당 1 entity 반환).

### 1.2 `POST /api/sd/working/single`

주문 1건 설계. 주문 PK는 body로 전달.

```bash
curl -s -X POST http://localhost:8080/api/sd/working/single \
  -H 'Content-Type: application/json' \
  -d '{"cmpCd":"K","orgCd":"1","orderNo":"ORD20260510001"}' | jq .
```

응답(`SingleDesignResponse`):

```json
{
  "slabResults": [
    {
      "slabNo": "000000000001",
      "orderNo": "ORD20260510001",
      "confirmedPlantCd": "K1 K    ",
      "slabThickness": 230.00,
      "slabWidth": 1200.00,
      "slabLength": 8500.00,
      "slabWgt": 17944.200,
      "splitCount": 1,
      "designStatus": "SUCCESS",
      "...": "..."
    }
  ],
  "errorCode": null,
  "errorMessage": null,
  "trace": null
}
```

DG 코드 fail 시:

```json
{
  "slabResults": [],
  "errorCode": "DG004",
  "errorMessage": "DG004 — 설계대기량 상한 < 포장 단중 하한",
  "trace": null
}
```

> **Quirk**: `slabResults`는 길이 ≤ 1로 제한된다(알고리즘이 마지막 슬랩 entity 한 개만 반환). 분할이 N매인 경우 N개 record 모두 보려면 `GET /api/sd/results?...&orderNo=...`를 사용.

### 1.3 `POST /api/sd/working/single?trace=true`

Step 단위 input/output trace 동봉. 시뮬레이션 검증 인터페이스.

```bash
curl -s -X POST 'http://localhost:8080/api/sd/working/single?trace=true' \
  -H 'Content-Type: application/json' \
  -d '{"cmpCd":"K","orgCd":"1","orderNo":"ORD20260510001"}' \
  | jq '{slabCount: (.slabResults|length), errorCode, traceLen: (.trace|length), step1: .trace[0]}'
```

응답 발췌:

```json
{
  "slabCount": 1,
  "errorCode": null,
  "traceLen": 21,
  "step1": {
    "step": 1,
    "stepName": "SdThicknessAction",
    "phase": "ONE_SHOT",
    "iteration": 1,
    "input": { "smCd": "K", "productCd": "COIL" },
    "output": { "slabThickness": 230.00 },
    "status": "OK",
    "errorCode": null,
    "errorMessage": null,
    "elapsedMs": 0.4
  }
}
```

A-a 루프 iteration이 도는 시나리오(S2/S3)는 step 8-13이 여러 번 재등장 — 각 row의 `iteration` 값으로 구분.

#### `StepTrace` 스키마

```text
step          1 ~ 21                  알고리즘 step 번호
stepName      SdThicknessAction 등    action class simple name
phase         "ONE_SHOT" | "AA_LOOP" | "FINAL" | "SAVE" | "VALIDATION"
iteration     1, 2, ...               A-a 루프 순회 카운터 (one-shot 은 1)
input         { ... }                 action 호출 직전 주요 입력 snapshot
output        { ... } | null          action 호출 후 주요 출력 (FAIL/RETRY/SKIP 시 null)
status        "OK" | "RETRY" | "FAIL" | "SKIP"
errorCode     "DG104" 등 | null       FAIL 시 SdErrorCode 상수
errorMessage  string | null           FAIL/RETRY 시 사람이 읽는 메시지
elapsedMs     0.4                     wrap() 측정 ms (RETRY/SKIP 은 0)
```

---

## 2. Orders — 시드 주문 조회 (read-only)

### 2.1 `GET /api/sd/orders` — 페이지 목록

```bash
curl -s 'http://localhost:8080/api/sd/orders?cmpCd=K&orgCd=1&page=0&size=10' | jq .
```

응답(`OrderSummary[]`):

```json
[
  {
    "cmpCd": "K",
    "orgCd": "1",
    "orderNo": "ORD20260510001",
    "productCd": "COIL",
    "confirmedPlantCd": "K1 K    ",
    "orderWidth": 1200.00,
    "orderLength": 8500.00
  }
]
```

기본 page=0 size=20.

### 2.2 `GET /api/sd/orders/{cmpCd}/{orgCd}/{orderNo}` — 상세

```bash
curl -s 'http://localhost:8080/api/sd/orders/K/1/ORD20260510001' | jq '{os: .os.orderNo, om: .om.productCd, qd: .qd.gradeCd, chem: .chemical.cMin}'
```

응답(`OrderDetail`)은 `os` / `om` / `qd` / `chemical` 4 JPO 그대로 묶음.

```json
{ "os": "ORD20260510001", "om": "COIL", "qd": "SS400", "chem": 0.05 }
```

미존재 PK는 404.

---

## 3. Results — 슬랩 결과(SLAB_RESULT)

### 3.1 `GET /api/sd/results` — 주문번호 기준 N건

```bash
curl -s 'http://localhost:8080/api/sd/results?cmpCd=K&orgCd=1&orderNo=ORD20260510002' | jq '.[] | {slabNo, splitCount, slabWgt}'
```

응답:

```json
{ "slabNo": "000000000002", "splitCount": 2, "slabWgt": 18333.333 }
{ "slabNo": "000000000003", "splitCount": 2, "slabWgt": 18333.333 }
{ "slabNo": "000000000004", "splitCount": 2, "slabWgt": 18333.334 }
```

(S2는 split=2이지만 슬랩 row가 3개 — 알고리즘이 split 결과 매수를 마지막에 조정하기 때문. `docs/SCENARIOS.md` 참고.)

### 3.2 `GET /api/sd/results/{slabNo}` — 단건

```bash
curl -s 'http://localhost:8080/api/sd/results/000000000001' | jq .
```

응답: `SlabResultJpo` 한 entity. 미존재 시 404.

---

## 4. History — 21-step 이력(SLAB_DESIGN_HIST)

### 4.1 `GET /api/sd/history` — 주문 기준

성공/실패 step 모두 `eventTime` 오름차순.

```bash
curl -s 'http://localhost:8080/api/sd/history?cmpCd=K&orgCd=1&orderNo=ORD20260510004' | jq '.[] | {stepNo, errorCode, eventTime}'
```

응답 (S4 — DG004 validator fail 1행만):

```json
{ "stepNo": 0, "errorCode": "DG004", "eventTime": "2026-05-10T13:33:18" }
```

### 4.2 `GET /api/sd/history/slab/{slabNo}` — 슬랩 기준 (성공 케이스)

`stepNo` 오름차순. `cmpCd`/`orgCd`는 query 로 받음.

```bash
curl -s 'http://localhost:8080/api/sd/history/slab/000000000001?cmpCd=K&orgCd=1' | jq '.[] | {stepNo, slabNo}'
```

---

## 5. Seed — DB 초기화 + 시나리오 메타

### 5.1 `POST /api/sd/seed/reset`

12개 테이블 TRUNCATE → master + orders SQL 재실행. SLAB_RESULT, SLAB_DESIGN_HIST는 비워둠. 골든 테스트 `@BeforeEach`도 이 endpoint를 호출.

```bash
curl -s -X POST http://localhost:8080/api/sd/seed/reset | jq .
```

응답:

```json
{ "ok": true, "scenarios": ["S1", "S2", "S3", "S4", "S5"] }
```

### 5.2 `GET /api/sd/seed/scenarios`

5개 시나리오 메타 (id, orderNo, description, confirmedPlantCd, expectedOutcome).

```bash
curl -s 'http://localhost:8080/api/sd/seed/scenarios' | jq .
```

응답:

```json
[
  {
    "id": "S1",
    "orderNo": "ORD20260510001",
    "description": "일반 COIL 주문 (golden path: split fallback → 1 slab)",
    "confirmedPlantCd": "K1 K    ",
    "expectedOutcome": "1 slab"
  },
  { "id": "S2", "orderNo": "ORD20260510002", "expectedOutcome": "3 slabs", "...": "..." }
]
```

---

## 6. 진단(`confirmedPlantCd` 인코딩)

`confirmedPlantCd`는 길이 8 문자열. 위치별 공정:

| pos | proc | 설명 |
|-----|------|-----|
| 0   | SM   | 제강 — 'K' (PlantMappingService → CC1/M1) |
| 1   | HR   | 열연 — '1'..'5' (SelectedHrTgtWidthResolver의 ORDER_QD `HR_TGT_WIDTH_N` 컬럼 인덱스. step 2 필수: 공백이면 DG102) |
| 2   | HRF  | 열연 후처리 |
| 3   | CR   | 냉연 |
| 4   | ANL1 | 1차 소둔 |
| 5   | ANL2 | 2차 소둔 |
| 6   | GAL  | 도금 |
| 7   | CRF  | 냉연 후처리 |

공백(`' '`)은 비활성. 활성 공정의 productivity 곱이 누적실수율(`PRODUCTIVITY_STD` lookup)이 된다.

---

## 7. 참고 — 5개 골든 시나리오 1줄 요약

| ID | orderNo | confirmedPlantCd | 의도 | 결과 |
|----|---------|------------------|-----|------|
| S1 | ORD20260510001 | `K1 K    ` | 골든 패스 | 1 slab |
| S2 | ORD20260510002 | `K1      ` | 다중 슬랩 + A-a inner loop | 3 slabs (split=2) |
| S3 | ORD20260510003 | `K1KK    ` | A-a inner-loop fallback | 2 slabs (split=1 → recalc) |
| S4 | ORD20260510004 | `K1      ` | DG004 cross-check fail | 0 slab + history 1 |
| S5 | ORD20260510005 | `K1     K` | 최소 활성 공정 | 1 slab |

상세는 `SCENARIOS.md`.
