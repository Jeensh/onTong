# Section 2 (Modeling) 측 요청 — ⑤ `simulate` intent 에 `method` / `class` / `order` 지원 확장

> **요청자**: Section 3 (Simulation) 팀
> **수신**: Section 2 (Modeling) 개발자
> **우선순위**: 🟡 **개선** (UX 큼)
> **발견 일자**: 2026-05-12 (Ontology API 전수 호출 감사)
> **예상 작업 비용**: M — kind 별 case 생성기 추가

---

## 한 줄 요약

> **`simulate` intent 가 현재 `target.kind="step"` 만 동작한다. `method` · `class` · `order` 도
> valid_range / param schema 기반으로 자동 케이스 생성을 지원해 달라.**

---

## 실측

```bash
$ curl -X POST /api/modeling/ontology/query -d '{
  "request_id":"x", "intent":"simulate",
  "parameters":{"target":{"kind":"method","id":"…"}}
}'
# → status=unsupported, "target.kind=method에 대한 테스트 데이터 생성은 미구현 (현재는 step만 지원)"
#    supported=["step"]
```

### step 의 응답 (참고용 — 잘 만들어진 케이스)

```jsonc
{
  "status": "success",
  "result": {
    "summary": "Step 7 대상 3개 테스트 케이스 생성 (입력 변수 2개)",
    "test_cases": [
      { "case_id":"TC001", "case_type":"normal",   "input":{"SlabWeight":100, "YieldRate":0.9}, "expected_output":{"feasible":true} },
      { "case_id":"TC002", "case_type":"boundary", "input":{"SlabWeight":0,   "YieldRate":0.8}, ... },
      { "case_id":"TC003", "case_type":"error",    "input":{"SlabWeight":-1,  "YieldRate":2.0}, ... }
    ],
    "code_skeleton": "// Auto-generated JUnit skeleton ...",
    "data_dependencies": ["TB_C40_050SC370"],
    "ontology_trace": { nodes, edges }
  }
}
```

→ step 의 응답 형식이 매우 좋다. 같은 schema 를 `method`/`class`/`order` 에도 적용 가능.

---

## 요청 명세

### 5.1 `target.kind="method"` 지원

```cypher
MATCH (m:Method { fqn: $mid })           // 요청 #3 의 Method 노드
OPTIONAL MATCH (m)-[:CONTAINS_PARAM]->(p:Variable)
OPTIONAL MATCH (m)-[:USES_STANDARD]->(std:Standard)
RETURN m, collect(p) AS params, collect(std) AS used_stds
```

method 의 param schema (legacy `code-types/{fqn}.methods[].params`) 의 `type` 별:

- `String` → ["", "ABC", "특수문자"]
- `BigDecimal` → range 가 알려져 있으면 valid_range, 아니면 [0, 1, -1]
- `int/long` → [0, INT_MAX, INT_MIN]
- `boolean` → [true, false]
- `<EntityType>` (object_ref) → object_ref_term 의 sample (또는 placeholder)

기대 응답:

```jsonc
{
  "summary": "ProductivityService.cumulativeProductivity 대상 6 case (param 6개)",
  "test_cases": [...],   // step 과 동일 schema
  "code_skeleton": "...",
  "data_dependencies": [...]   // method-CALCULATES->step 의 USES_STANDARD 추적
}
```

### 5.2 `target.kind="class"` 지원

class 의 `public` 메서드 N 개를 일괄 — class 가 가진 모든 method 의 case 를 합성.

```jsonc
{
  "summary": "ProductivityService — public method 4 개 × 평균 3 case = 12 case",
  "test_cases": [
    { "case_id":"M1_TC001", "method_fqn": "...", ... },
    { "case_id":"M2_TC001", "method_fqn": "...", ... },
    ...
  ]
}
```

### 5.3 `target.kind="order"` 지원

order 로 시뮬 = 14 Step 전체 시뮬레이션 (이미 `impact_analysis(order)` 는 14 Step 반환).

```jsonc
{
  "summary": "Order ORD_001 시뮬 — 14 Step 전체",
  "test_cases": [
    { "step_number": 1, "case_id":"S1_TC001", ... },
    { "step_number": 2, ... },
    ...
  ],
  "data_dependencies": [...],
  "code_skeleton": null   // order 단위는 skeleton 의미 없음
}
```

### 5.4 `parameters.lang` 옵션 (보조)

`code_skeleton` 의 언어 선택:

```jsonc
{
  "parameters": { "target":{...}, "lang": "python" | "java" }   // default "java"
}
```

- `java` — 기존 JUnit
- `python` — `pytest` 형식 (Section 3 가 Python 으로 격리 실행하므로 매우 유익)

---

## Acceptance Criteria

- [ ] `simulate(method)` → `status=success` + `test_cases` 3개 이상
- [ ] `simulate(class)` → 클래스의 public method 다발 케이스
- [ ] `simulate(order)` → 14 Step 전체 case
- [ ] `lang=python` 옵션 시 `code_skeleton` 이 pytest 형식
- [ ] 미존재 id → `need_more_info` (현재는 error)

---

## Section 3 에서의 활용처

| Section 3 자산                                       | 변경 후 동작                                                                                       |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `SandboxPanel.tsx` (좌측 nav 2번)                    | 현재 step preset 만 노출. method 단독 시뮬 가능해지면 method dropdown 추가                          |
| `SandboxAgent` (`backend/section3/agents/sandbox_agent.py`) | 현재 method/class 호출 시 modeling 이 unsupported → Section 3 가 LLM 으로 케이스 합성하는 fallback. 이 요청 후엔 modeling 응답 그대로 사용. |
| `code_skeleton` 의 Python 변환 (LLM)                 | `lang=python` 직접 받으면 LLM 변환 step 제거 → 응답 빠르고 정확.                                    |
| Order 시뮬 (지금은 없음)                              | "주문 1개 통째 시뮬" 메뉴 신설 가능 — slab-design 의 14 Step 전체 trace.                            |

---

## 기존 endpoint 와의 관계

| endpoint                                | 이 변경 후                                                            |
| --------------------------------------- | --------------------------------------------------------------------- |
| `POST /api/modeling/ontology/query` (simulate) | supported list = `["step","method","class","order"]`               |
| `POST /api/section3/sandbox/run` (Section 3) | `target_kind=method` 응답이 modeling 정식 응답 → mock fallback 제거 |

---

## 메타

- **요청 ID**: SECTION2-REQ-05
- **요청 일자**: 2026-05-12
- **선행 작업**: 요청 #03 (Class/Method graph 적재) 권장 — 없으면 method/class kind 는 legacy code-types fetch fallback 필요
- **연관 요청**: #03, #04
