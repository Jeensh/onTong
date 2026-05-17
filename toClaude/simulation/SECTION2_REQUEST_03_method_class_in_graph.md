# Section 2 (Modeling) 측 요청 — ③ modeling graph 에 `Class` / `Method` 노드 적재

> **요청자**: Section 3 (Simulation) 팀
> **수신**: Section 2 (Modeling) 개발자
> **우선순위**: 🔴 **블로커**
> **발견 일자**: 2026-05-12 (Ontology API 전수 호출 감사 — `toClaude/simulation/ONTOLOGY_API_AUDIT.md`)
> **예상 작업 비용**: M — layer3 builder 의 출력 형식 정리

---

## 한 줄 요약

> **`/api/modeling/ontology/graph/stats` 가 `Class:0, Method:0` 을 반환한다.
> 즉 `impact_analysis(method|class)` 와 `simulate(method|class)` 가 항상 빈 응답이다.
> legacy `/api/ontology/code-types` (5166 class) 의 정보를 modeling graph 에도 적재해 달라.**

---

## 배경 — 무엇이 막혀 있는가

### 현재 상태

```bash
$ curl http://localhost:8001/api/modeling/ontology/graph/stats
{
  "nodes": {
    "Term": 19, "TermCategory": 5, "Step": 12, "Standard": 14,
    "Variable": 10, "ErrorCode": 1, "Class": 0, "Method": 0, "Table": 14
  },
  "totals": { "nodes": 75, "relations": 117 }
}
```

→ modeling graph 에 **Java Class 와 Method 노드가 0개**.

반면 legacy SQLite (`/api/ontology/code-types`) 에는:

```
GET /api/ontology/code-types?repo_id=slab-design-real   → 107 class
GET /api/ontology/code-types                            → 5166 class (synthetic 포함)
```

—class 와 그 안의 method, body_text, line_start/end, anchors 까지 풍부하게 보관.

### 그 결과 modeling `query` 응답 (실측)

```bash
$ curl -X POST /api/modeling/ontology/query -d '{
  "request_id":"r1",
  "intent":"impact_analysis",
  "parameters":{"target":{"kind":"method","id":"action.scm.product.cumulative_productivity"}}
}'
```

```jsonc
{
  "status": "success", "confidence": 0.5,
  "result": {
    "summary": "'…'에 해당하는 메서드가 그래프에 없습니다",
    "direct_impact":   { "methods": [], "affected_steps": [] },
    "indirect_impact": { "downstream_steps": [] },
    "risk_level": "LOW", "risk_factors": ["대상 미존재"],
    "ontology_trace": {
      "nodes": [], "edges": [],
      "cypher": "MATCH (m:Method) WHERE m.id = $mid OR m.name = $mid …"
    }
  }
}
```

cypher 는 정상이지만 `(m:Method)` 매치 자체가 0건이라 항상 빈 응답.

---

## Section 3 의 막힌 시나리오

### Scenario A — 「영향도 분석 — 코드 변경」 패널

좌측 nav 의 핵심 panel. `target_kind ∈ {method, class, column}` 로 method/class FQN 을 입력해 영향을 본다.

- 사용자가 `com.example.slabdesign.feature.sd.process.std.service.ProductivityService.cumulativeProductivity(...)` 입력
- modeling 응답: `"…에 해당하는 메서드가 그래프에 없습니다"`
- 즉 **panel 의 핵심 기능이 100% 실패**.

### Scenario B — 「샌드박스」 패널의 method 단독 시뮬

`simulate(target.kind=method, id=…)` 로 method 단위 valid_range 기반 케이스 생성을 하고 싶다. 현재 simulate 는 step 만 지원하지만, method 도 지원 가능하려면 graph 에 Method 노드가 있어야.

### Scenario C — chat 의 "이 method 가 어디에 영향?"

`bridge_agent` 가 `impact_analysis(method=…)` 로 분기. graph 에 노드가 없어 헛방.

### Scenario D — 시각화 (vis-network)

Section 3 의 `OntologyTrace` 응답에는 `nodes/edges` 가 들어 있다. 사용자가 "ProductivityService 가 어디서 어떻게 호출되나" 를 그래프로 보고 싶지만, graph 에 코드 노드가 없으면 시각화 자체가 불가능.

---

## 요청 명세

### 옵션 A — modeling graph 에 `Class` / `Method` 노드 적재 (★ 권장)

`layer3_code` builder 가 다음 노드를 Neo4j 에 적재:

#### Class 노드

```cypher
(c:Class {
  fqn: "com.example.slabdesign.feature.sd.process.std.service.ProductivityService",
  simple_name: "ProductivityService",
  package: "com.example.slabdesign.feature.sd.process.std.service",
  kind: "class",       // class | interface | enum | annotation
  role: "service",     // service | adapter | framework | model | util | controller
  source_file: "...ProductivityService.java",
  line_start: 14, line_end: 120,
  repo_id: "slab-design-real"
})
```

#### Method 노드

```cypher
(m:Method {
  fqn: "...ProductivityService.cumulativeProductivity(String,String,String,String,String,String)",
  name: "cumulativeProductivity",
  parent_type_fqn: "...ProductivityService",
  return_type: "BigDecimal",
  modifiers: ["public"],
  role: "calculator",
  line_start: 80, line_end: 110,
  repo_id: "slab-design-real"
})
```

> ⚠️ **body_text 는 노드 property 에 넣지 말 것**. 너무 큼. 별도 endpoint `/code-types/{fqn}` (legacy) 로 가져오면 됨.

#### 관계 (relation)

| Cypher                                | 의미                                   |
| ------------------------------------- | -------------------------------------- |
| `(c:Class)-[:CONTAINS]->(m:Method)`   | class 가 method 포함                   |
| `(m:Method)-[:CALCULATES]->(s:Step)`  | method 가 어느 Step 의 핵심 계산을 수행 (anchor 또는 action ↔ step 매핑 기반) |
| `(m:Method)-[:USES_STANDARD]->(std:Standard)` | method 가 SC 기준값 사용 (anchor 의 target_slot 파싱) |
| `(m:Method)-[:CALLS]->(m2:Method)`    | method → method 호출 (legacy `call-sites` 의 confidence≥0.5 만) |
| `(m:Method)-[:ENFORCES]->(r:Rule)`    | business-rules 의 enforced_by 역방향  |
| `(m:Method)-[:REALIZES]->(a:Action)`  | action.realizations[].code_method_fqn  |

#### graph_stats 기대 응답 (예시)

```jsonc
{
  "nodes": {
    "Class": 107,        // slab-design-real 만
    "Method": 198,       // service+action 만 (모든 method 다 넣지 않음 — getter/setter 제외)
    "Step": 12, "Standard": 14, "Table": 14, "Term": 19, ...
  }
}
```

### 옵션 B — modeling 이 legacy 를 호출하는 hybrid (차선)

modeling `query(impact_analysis)` 핸들러 안에서 legacy `/api/ontology/code-types` 를 fetch 하여 method 정보를 채워 반환. graph 에는 안 넣고 응답에만 enrich.

- 장점: graph 변경 없음
- 단점: 그래프 시각화 (ontology_trace.nodes) 에서 코드 노드가 안 보임. 응답 매번 늦어짐 (5166 class scan).

→ 옵션 A 가 정공법.

---

## Acceptance Criteria

- [ ] `GET /graph/stats` → `Class > 0, Method > 0` (slab-design-real 만 적재 시 107 class / 200~ method 예상)
- [ ] `impact_analysis(target.kind=method, id="<실제 method fqn>")` → `direct_impact.affected_steps[]` non-empty, `ontology_trace.nodes` 에 Class·Method 노드 포함
- [ ] `impact_analysis(target.kind=class, id="<실제 class fqn>")` → "추후 구현 예정" 이 아닌 실 응답 (직접 영향 method 리스트 등)
- [ ] method → step 의 `CALCULATES` 관계가 anchor-bindings 기반으로 정확히 연결됨
- [ ] **시각화** — `ontology_trace.nodes` 에 group 이 `class` / `method` 인 항목이 등장
- [ ] graph 적재 후 `query` 응답 latency p95 < 2 s 유지

---

## Section 3 에서의 활용처 (이 변경 후 바로 켜질 기능)

| Section 3 자산                                       | 변경 후 동작                                                                                     |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `CodeImpactPanel.tsx` (좌측 nav 3번)                 | method/class FQN 입력 시 영향 method · Step · downstream 다단 표시. 지금은 항상 빈 응답.            |
| `BridgeChatPanel.tsx` → `impact_analysis` 분기       | 자연어 "ProductivityService 바꾸면?" → 직접 method 리스트 + cypher trace                          |
| `RichResultCard.tsx` 의 `source_locations`           | `affected_methods[].file_path` + `line_start/end` 표시 (현재 항상 빈 배열)                         |
| `OntologyGraphView` (vis-network — 차후 추가 예정)   | Class/Method 노드가 시각화 그래프에 등장 → impact path 시각화 가능                                 |
| `SandboxPanel.tsx` (method 단독 시뮬 — 요청 #5 와 연동) | method 노드가 graph 에 있어야 `simulate(method)` 구현 시 안전한 dispatch                           |

---

## 구현 힌트 (Section 2 측 참고)

`backend/modeling/ontology/builders/layer3_code.py` 에서 legacy SQLite 의 `code_types` 테이블을
Neo4j 로 MERGE. 의사 코드:

```python
async def build_layer3_code(repo_id: str = "slab-design-real"):
    types = await fetch_code_types(repo_id, kind="class")
    for t in types:
        await session.run("""
          MERGE (c:Class {fqn: $fqn})
          SET c.simple_name=$sn, c.package=$pkg, c.role=$role, c.source_file=$sf,
              c.line_start=$ls, c.line_end=$le, c.repo_id=$repo
        """, fqn=t.fqn, sn=t.simple_name, ...)
        for m in t.methods:
            if m.role in ("calculator", "service", "validator"):  # 필터
                await session.run("""
                  MERGE (m:Method {fqn: $fqn})
                  SET m.name=$nm, m.return_type=$rt, m.role=$role, m.line_start=$ls, m.line_end=$le
                  WITH m
                  MATCH (c:Class {fqn: $parent})
                  MERGE (c)-[:CONTAINS]->(m)
                """, ...)
    # 관계: anchor-bindings 로부터 method ↔ step / standard 연결
    anchors = await fetch_anchor_bindings(repo_id)
    for a in anchors:
        # a.code_method_fqn ↔ a.target_action_fqn ↔ action.realizations ↔ step 추론
        ...
```

`call-sites` 의 `confidence` 가 0 = stdlib (자동 필터) 인 것은 제외. `analysis_source=static_unresolved` 인 것도 일단 제외 (signal too noisy).

---

## 기존 endpoint 와의 관계

| endpoint                                       | 이 변경 후                                                                          |
| ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| `GET /api/modeling/ontology/graph/stats`       | Class/Method count 가 0 → N 으로 변경                                               |
| `POST /api/modeling/ontology/query` (impact_analysis, method/class) | 빈 응답 → 정상 dispatch                                                              |
| `POST /api/modeling/ontology/query` (simulate, method — 요청 #5 와 함께) | "step만 지원" → "method 지원"                                                       |
| `GET /api/ontology/code-types/{fqn}` (legacy)  | body_text 가져올 때 그대로 활용 (Section 3 가 detail 조회)                          |

---

## 메타

- **요청 ID**: SECTION2-REQ-03
- **요청 일자**: 2026-05-12
- **추적**: `toClaude/simulation/SECTION2_REQUESTS.md`
- **선행 작업**: 없음 (legacy SQLite 데이터는 이미 풍부)
- **연관 요청**: #04 (`impact_analysis` 의 standard_value/class/column 분기 — 이 노드들이 graph 에 있어야 분기 의미 있음), #05 (`simulate` method 지원 — graph 에 method 노드 필요)
