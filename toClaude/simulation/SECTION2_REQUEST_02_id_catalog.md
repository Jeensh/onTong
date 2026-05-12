# Section 2 (Modeling) 측 요청 — ② Table / Standard / Order ID 카탈로그 endpoint

> **요청자**: Section 3 (Simulation) 팀
> **수신**: Section 2 (Modeling) 개발자
> **우선순위**: 🔴 **블로커 (UX)**
> **발견 일자**: 2026-05-12 (Section 3 재개편 Phase 1)
> **예상 작업 비용**: S — Cypher 한 두 줄로 endpoint 1~3 개

---

## 한 줄 요약

> **`/api/modeling/ontology/query` (impact_analysis) 가 받는 `target.id` 후보 목록을
> 사용자가 자동완성 / 선택할 수 있도록, Table / Standard / Order 의 ID 카탈로그 endpoint 를 신설해 주세요.**

---

## 배경 — 왜 필요한가

`POST /api/modeling/ontology/query` 의 `intent=impact_analysis` 는 `target.kind`
+ `target.id` 를 받아 강력한 영향도 분석을 반환합니다. 그러나 사용자가
**그 `target.id` 가 무엇인지 알 수 있는 방법이 없습니다.**

### 현재 상황

| 정보 | 현재 endpoint | 노출되는 것 | 빠진 것 |
|---|---|---|---|
| Table 14 개 | `GET /graph/stats` | 카운트 `Table: 14` | 실제 id (`TB_C40_050SC160` 등) |
| Standard 14 개 | `GET /graph/stats` | 카운트 `Standard: 14` | 실제 id (`SC160`, `SC370` 등) |
| Order (시뮬 가능한 주문) | 없음 | — | `order_001` 같은 id |

### 우리가 발견한 동작

```bash
# 추측한 id 로 호출 시
curl -X POST /api/modeling/ontology/query -d '{
  "intent":"impact_analysis",
  "parameters":{"target":{"kind":"table","id":"CAST_SPEC"}}
}'

# 응답
{
  "status": "success",
  "result": {
    "summary": "'CAST_SPEC'에 해당하는 테이블이 그래프에 없습니다",
    "risk_factors": ["대상 미존재"]
  }
}
```

사용자는 어떤 id 가 실제로 존재하는지 알 길이 없어 매번 추측 → 미존재 응답 →
포기하는 흐름이 발생합니다.

---

## Section 3 의 막힌 UX 시나리오 (3가지)

### Scenario 1 — 「데이터 변경 분석」 메뉴의 자동완성

사용자가 좌측 nav 의 "데이터 변경 분석" 진입 → 변경 대상 종류
(`SC 기준값` / `Table` / `주문`) 선택 후 ID 입력란을 보지만 **무엇을 입력할지
모릅니다**. 자동완성 또는 dropdown 이 필요.

> 현재 우회: hardcoded preset chip 3 개 (`SC160` / `SC370` / `TB_C40_050SC160`) 만
> 노출 중. **실제 14 개 중 일부에 불과**.

### Scenario 2 — chat 에서 "어느 Standard 가 있어?" 같은 메타 질문

사용자: "ontology 에 등록된 Standard 가 뭐가 있어?"

현재 `explain` intent 는 자연어 매칭 기반이라 이런 메타 질문에 적절히 답 못 함.
chat agent 가 catalog endpoint 만 있으면 즉시 답할 수 있음.

### Scenario 3 — 시뮬레이션 시작 전 "주문" 선택

`impact_analysis(order=order_001)` 는 14 Step 전체 시뮬을 trigger 하는 강력한
기능인데, 사용자가 어떤 `order_001`이 실제로 등록되어 있는지 모름. 시뮬을 시작도
못함.

---

## 요청 API 명세 (우리가 권장하는 옵션 A)

### 옵션 A — 별도 catalog endpoint 3 종 (★ 권장)

```
GET  /api/modeling/ontology/tables
GET  /api/modeling/ontology/standards
GET  /api/modeling/ontology/orders
```

#### 공통 쿼리 파라미터

| param | 타입 | default | 설명 |
|---|---|---|---|
| `q` | string | "" | 부분 일치 검색 (id / name / description 모두 매칭) |
| `limit` | int | 100 | 최대 결과 수 |
| `offset` | int | 0 | pagination |
| `sort` | string | "id" | `id` / `name` / `domain` |

#### 응답 shape (3 endpoint 공통)

```typescript
{
  "kind": "table" | "standard" | "order",
  "total": number,                    // 매칭 총 건수 (limit 적용 전)
  "returned": number,                 // 이번에 반환된 건수
  "items": Item[]
}
```

#### `Item` 별 schema

**Table** (`GET /tables` 의 item):
```json
{
  "id": "TB_C40_050SC160",
  "name": "TB_C40_050SC160",
  "schema_name": "POSPIA",
  "standard_code": "SC160",        // MAPS_TO_STANDARD 관계로 연결된 Standard
  "description": "...",            // optional
  "graph_node_id": "table:TB_C40_050SC160"   // 시각화용
}
```

**Standard** (`GET /standards` 의 item):
```json
{
  "id": "SC160",
  "code": "SC160",
  "name": "...",                   // 한국어 라벨 (있으면)
  "domain": "scm",
  "used_in_steps": [7, 8],         // USES_STANDARD 관계의 Step 번호들 (optional but nice)
  "mapped_tables": ["TB_C40_050SC160"],  // MAPS_TO_STANDARD 역방향 (optional)
  "graph_node_id": "std:SC160"
}
```

**Order** (`GET /orders` 의 item):
```json
{
  "id": "order_001",
  "name": "주문 #1",               // optional
  "description": "...",            // optional
  "graph_node_id": "order:order_001"
}
```

> 핵심: `id` 필드는 그대로 `impact_analysis` 의 `target.id` 로 전달 가능해야 합니다.
> (round-trip 보장)

#### 예시 호출 / 응답

```bash
curl http://localhost:8001/api/modeling/ontology/standards?q=160
```

```json
{
  "kind": "standard",
  "total": 1,
  "returned": 1,
  "items": [
    {
      "id": "SC160",
      "code": "SC160",
      "name": "용도/주문 폭범위 기준",
      "domain": "scm",
      "used_in_steps": [7, 8],
      "mapped_tables": ["TB_C40_050SC160"],
      "graph_node_id": "std:SC160"
    }
  ]
}
```

---

### 옵션 B — `impact_analysis` "미존재" 응답에 후보 list 첨부 (보조)

이미 동작하는 endpoint 의 응답을 확장하는 방식. 옵션 A 와 함께 적용하면 가장
견고하고, 둘 다 못 하면 이것만이라도.

미존재 시 응답:
```json
{
  "status": "success",
  "result": {
    "summary": "'CAST_SPEC'에 해당하는 테이블이 그래프에 없습니다",
    "risk_factors": ["대상 미존재"],
    "candidates": [             // ★ NEW
      {"id": "TB_C40_050SC030", "name": "..."},
      {"id": "TB_C40_050SC160", "name": "..."}
    ]
  }
}
```

### 옵션 C — `graph/stats` 확장 (비추천)

기존 `graph/stats` 가 카운트만 노출 → items 까지 노출하면 응답 폭증. 카운트
endpoint 와 catalog endpoint 의 책임 분리가 더 좋음.

---

## Acceptance Criteria (체크리스트)

옵션 A 기준:

- [ ] `GET /api/modeling/ontology/tables` → HTTP 200, 14 개 모두 반환
- [ ] `GET /api/modeling/ontology/standards` → HTTP 200, 14 개 모두 반환
- [ ] `GET /api/modeling/ontology/orders` → HTTP 200, 등록된 order 모두 반환 (현재 graph 에 order 노드가 없다면 빈 list 가능)
- [ ] 각 item 의 `id` 를 그대로 `impact_analysis` `target.id` 로 호출 시 정상 응답 (round-trip)
- [ ] `q` 부분 일치 검색 동작 (`?q=160` 시 `SC160` 매칭)
- [ ] empty 결과 시 `{items: [], total: 0}` (404 아님)
- [ ] `Content-Type: application/json` + UTF-8 (한국어 라벨)
- [ ] OpenAPI doc 자동 등록 (`/docs` 에 표시)

---

## 구현 힌트 (Section 2 측에 참고용)

기존 `backend/modeling/ontology/api/ontology_router.py` 에 라우트 추가. Cypher 한 줄로 가능할 듯:

```python
@router.get("/tables")
async def list_tables(q: str = "", limit: int = 100, offset: int = 0):
    client = get_client()
    # MATCH (t:Table) OPTIONAL MATCH (t)-[:MAPS_TO_STANDARD]->(s:Standard)
    # WHERE t.name CONTAINS $q OR t.id CONTAINS $q
    # RETURN t.id AS id, t.name AS name, t.schema_name AS schema_name,
    #        s.code AS standard_code
    # ORDER BY t.id SKIP $offset LIMIT $limit
    ...
```

`Standard` 의 `used_in_steps` 는 `(s:Standard)<-[:USES_STANDARD]-(step:Step) RETURN
collect(step.step_number)` 로 한 번에 가져올 수 있을 듯.

---

## 기존 endpoint 와의 관계

| endpoint | 역할 | 이 catalog 와의 관계 |
|---|---|---|
| `GET /graph/stats` | 노드/관계 카운트 통계 | catalog 의 `total` 과 일치해야 함 |
| `POST /query` (intent=impact_analysis) | id 받아 영향 분석 | **catalog 가 그 id 를 사용자에게 공급** |
| `POST /query` (intent=explain) | 자연어 → 위치 찾기 | catalog 와는 별개 (자연어 기반) |
| `GET /term/search` | Term 자동완성 | 같은 패턴의 Standard / Table / Order 버전 |

---

## 현재 Section 3 의 우회 방안 (이 endpoint 가 없는 동안)

1. **hardcoded preset chip** — `DataImpactPanel` 에 3개씩 hardcode
   (`SC030, SC160, SC370` / `TB_C40_050SC030, ...`). 14 개 중 일부만 노출.
2. **chat 의 `explain` intent** 로 자연어 검색 → `data_locations.table_name` 추출.
   사용자가 자연어를 잘 표현해야 동작.

→ 둘 다 정식 UX 가 아니어서 사용자가 답답함을 호소함.

---

## 우선순위 산정 사유

🔴 **블로커 (UX)** — 핵심 nav 메뉴 ("데이터 변경 분석") 의 사용자 진입 자체가 막힘.
다른 6개 항목 (#1, #3 ~ #7) 은 우회 가능하지만 이건 어렵습니다. **이 항목 하나만
처리되어도 Section 3 의 핵심 메뉴 한 개가 완성됩니다.**

---

## 메타

- **요청 ID**: SECTION2-REQ-02
- **요청 일자**: 2026-05-12
- **추적**: `toClaude/simulation/SECTION2_REQUESTS.md` 의 ② 항목 (간단 버전)
- **Section 3 측 담당**: simulation 세션
- **만나면 좋을 다른 요청**: ④ Java 소스 라인 fetch endpoint (영향 분석 시 같이 표시 가능)
