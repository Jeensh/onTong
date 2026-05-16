# Section 2 (Modeling) 측 요청 — ④ `impact_analysis` 의 `standard_value` / `class` / `column` 분기 구현

> **요청자**: Section 3 (Simulation) 팀
> **수신**: Section 2 (Modeling) 개발자
> **우선순위**: 🟡 **개선**
> **발견 일자**: 2026-05-12 (Ontology API 전수 호출 감사)
> **예상 작업 비용**: M — handler 분기 3 개 + Cypher 3 개

---

## 한 줄 요약

> **`POST /api/modeling/ontology/query` (intent=impact_analysis) 의 dispatch 중 일부 `target.kind`
> 가 잘못 라우팅되거나 partial 미구현 상태이다. 4 개 kind 의 정상화를 요청한다.**

---

## 실측 — 각 `target.kind` 별 현재 동작

| `target.kind`     | 실측 응답                                                                                              | 진단                                 |
| ----------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| `table`           | ✅ 정상 (예: `TB_C40_050SC160` → Step 8 + 다운스트림 4개)                                                | OK                                   |
| `order`           | ⚠️ 임의 id 도 success — graph 매칭 없이 무조건 14 Step 반환                                              | id 검증 없음                          |
| `method`          | ❌ `(m:Method)` 매칭 0건 (요청 #3 의 graph 적재 후 자연 해결)                                              | graph 데이터 부재                    |
| `standard_value`  | ❌ cypher 가 `MATCH (t:Table)` 로 빠짐 → `SC160` 으로 호출해도 "테이블이 그래프에 없습니다"                  | dispatch 잘못                        |
| `class`           | ❌ `partial` — "추후 구현 예정"                                                                          | 미구현                                |
| `column`          | ❌ `partial` — "추후 구현 예정"                                                                          | 미구현                                |

### 재현 명령

```bash
curl -X POST /api/modeling/ontology/query -d '{
  "request_id":"x",
  "intent":"impact_analysis",
  "parameters":{"target":{"kind":"standard_value","id":"SC160"}}
}'
# →
# {
#   "summary": "'SC160'에 해당하는 테이블이 그래프에 없습니다",   ★ "테이블"이라고 출력됨!
#   "ontology_trace": { "cypher": "MATCH (t:Table) WHERE t.id = $tid ..." }
# }
```

cypher 가 standard_value 가 아닌 table 분기를 타고 있음 → handler 코드의 분기 bug.

---

## 요청 사항 — 4 개 kind 정상화

### 4.1 `standard_value` 분기 (블로커 — 잘못된 dispatch)

```cypher
MATCH (std:Standard)
WHERE std.code = $sid OR std.id = $sid
OPTIONAL MATCH (t:Table)-[:MAPS_TO_STANDARD]->(std)
OPTIONAL MATCH (step:Step)-[:USES_STANDARD]->(std)
OPTIONAL MATCH (m:Method)-[:CALCULATES]->(step)
RETURN
  std.code AS standard_code,
  collect(DISTINCT { id: t.name, schema_name: t.schema_name }) AS mapped_tables,
  collect(DISTINCT { step_number: step.step_number, korean_name: step.korean_name }) AS direct_steps,
  collect(DISTINCT { fqn: m.fqn, name: m.name }) AS direct_methods
```

기대 응답 (예: `SC160`):

```jsonc
{
  "summary": "SC160 변경 시 Step 2개 직접 영향 (Step 7·8) · 매핑 table 2개",
  "direct_impact": {
    "affected_steps": [
      { "step_number": 7, "korean_name": "분할수 계산", "via_standard": "SC160" },
      { "step_number": 8, "korean_name": "매수 및 목표단중 계산", "via_standard": "SC160" }
    ],
    "mapped_tables": [
      { "id": "TB_C40_050SC160", "schema_name": "POSPIA" }
    ],
    "methods": []     // 요청 #3 적용 전엔 빈 배열, 적용 후엔 method 리스트
  },
  "indirect_impact": { "downstream_steps": [...] },   // 기존 table 분기와 동일 로직
  "ontology_trace": { ... }
}
```

### 4.2 `class` 분기

`(c:Class)-[:CONTAINS]->(m:Method)-[:CALCULATES]->(s:Step)` 패턴 이용 (요청 #3 적용 후).

```cypher
MATCH (c:Class)
WHERE c.fqn = $cid OR c.simple_name = $cid
OPTIONAL MATCH (c)-[:CONTAINS]->(m:Method)
OPTIONAL MATCH (m)-[:CALCULATES]->(step:Step)
OPTIONAL MATCH (m)-[:USES_STANDARD]->(std:Standard)
OPTIONAL MATCH (m)-[:ENFORCES]->(r:Rule)
RETURN
  c.fqn AS class_fqn,
  collect(DISTINCT m.fqn) AS contained_methods,
  collect(DISTINCT { step_number: step.step_number, korean_name: step.korean_name }) AS affected_steps,
  collect(DISTINCT std.code) AS used_standards,
  collect(DISTINCT r.fqn) AS enforced_rules
```

응답에 `risk_level` 산정: 영향 Step ≥ 3 이면 HIGH, ≥1 이면 MEDIUM, 0이면 LOW.

### 4.3 `column` 분기

DB column → table 추론. Section 2 가 column 메타데이터를 갖고 있다면 직접, 없다면 table 분기로 위임:

```python
if kind == "column":
    # column id 형식: "TB_C40_050SC160.COL_TARGET_WEIGHT" 또는 "COL_..."
    table_id = column_id.split(".")[0] if "." in column_id else lookup_table_for_column(column_id)
    if not table_id:
        return need_more_info(question="column 이 어느 table 에 속하나요?")
    return await impact_analysis_table(table_id)
```

### 4.4 `order` 분기 — id 검증 + Standard/Table 별 영향

현재는 id 검증 없이 14 Step 무조건 반환. 다음 동작이 더 유익:

```cypher
MATCH (o:Order { id: $oid })
OPTIONAL MATCH (o)-[:REQUIRES_STEP]->(s:Step)  // (또는 모든 Step 14 개)
OPTIONAL MATCH (s)-[:USES_STANDARD]->(std:Standard)
RETURN
  o.id AS order_id,
  collect(DISTINCT s.step_number) AS required_steps,
  collect(DISTINCT std.code) AS required_standards
```

graph 에 Order 노드가 없는 환경에선 `status="need_more_info"` + question (`order_id 가 등록되어 있지 않습니다`) 를 반환.

---

## Acceptance Criteria

- [ ] `standard_value` 호출 시 cypher 가 `(:Standard)` 로 시작 (현재 `(:Table)` 잘못 분기)
- [ ] `standard_value` 응답의 `summary` 가 `"…테이블이 그래프에 없습니다"` 가 아닌 표준 정상 문장
- [ ] `class` 호출 시 contained_methods + affected_steps 반환 (#3 적용 후)
- [ ] `column` 호출 시 table 분기 위임 또는 column 메타 기반 분기 동작
- [ ] `order` 호출 시 미존재 id → `need_more_info` 또는 `risk_factors=["대상 미존재"]`

---

## Section 3 에서의 활용처

| Section 3 자산                              | 변경 후 동작                                                                                       |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `DataImpactPanel` 의 `target_kind=standard_value`  | SC160 입력 시 실제 영향 Step 2개 표시. 지금은 "테이블이 그래프에 없습니다" 오답.                     |
| `CodeImpactPanel` 의 `target_kind=class/column`  | 추후 구현 예정 메시지 → 실 응답으로 전환                                                            |
| `BridgeChatPanel` 의 chat 분기              | LLM 분류가 `class`/`column` 으로 들어와도 정상 응답 (현재 partial 응답으로 빈 결과)                  |

---

## 기존 endpoint 와의 관계

| endpoint                                | 이 변경 후                                                            |
| --------------------------------------- | --------------------------------------------------------------------- |
| `POST /api/modeling/ontology/query`     | dispatch 표가 깔끔히 완성 — 6 kind 모두 정상                            |
| `GET /api/modeling/ontology/graph/stats`| Standard:14 와 affected_steps 응답이 일관되게 매핑                      |

---

## 메타

- **요청 ID**: SECTION2-REQ-04
- **요청 일자**: 2026-05-12
- **선행 작업**: 부분 가능. `standard_value` 분기는 즉시 가능, `class/column` 은 #3 (Class/Method 적재) 선행이면 더 풍부.
- **연관 요청**: #03, #05
