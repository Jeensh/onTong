# Section 2 (Modeling) 측 — Section 3 동작 자체에 **꼭 필요한 것만** 요청

> **요청자**: Section 3 (Simulation) 팀
> **수신**: Section 2 (Modeling) 개발자
> **작성 일자**: 2026-05-12
> **목적**: 49 개 ontology endpoint 전수 호출 감사 (`ONTOLOGY_API_AUDIT.md`) 결과, **Section 3 는 legacy `/api/ontology/*` 만으로 modeling Neo4j 적재 없이 자체 응답 합성이 가능**함을 확인. 그래도 Section 2 가 해줘야만 Section 3 가 정상 동작하는 항목 **3건만** 추렸다.

---

## 0. 우선 — Section 2 측 작업이 ❌ 불필요한 항목들

기존에 누적했던 7건의 요청 중 다음은 **Section 3 단독 우회 완료** 로 인해 무의미해졌다 (백로그로 남기되 압박 없음):

| 기존 #  | 제목                                                  | 우회 방법 (Section 3 단독)                                                                                          |
| ------- | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| ① / ⑤  | `simulate` 의 method/class kind                       | legacy `actions/{fqn}.params` + `code-types/{class}.methods[].params` → Section 3 가 자체 케이스 합성                |
| ②       | id 카탈로그 endpoint (`/tables` `/standards` `/orders`) | legacy `terms` (1236), `modules/inventory` (50 class), `modules/inventory/actions` (36 action) 그대로 사용         |
| ③       | modeling graph 에 Class/Method 적재                    | legacy `repos/{repo_id}/graph?mode=neighborhood&focus_fqn=...` 가 Class/Method 다 표시. 시각화도 이걸로 자립        |
| ④       | `impact_analysis` 의 standard_value/class/column 분기 | Section 3 가 modeling 호출 우회. legacy `business-rules.enforced_by` + `actions/{fqn}.realizations` 로 직접 트래버스 |
| ⑥       | `explain` 의 `keywords[]` 배열 수용                    | Section 3 가 `natural_language` 만 전송 (이미 적용)                                                                |
| ⑦       | `term/search` alias / 한↔영 cross-match                | legacy `search` (영문 부분 매칭 OK) + Section 3 가 `terms` catalog 받아 자체 fuzzy                                   |

→ 위 7건은 **삭제 아닌 보류**. 시간 나면 작업 권장. 지금 막힘 ❌.

---

## 1. 진짜 필수 3건

다음 3건은 Section 3 단독 우회로도 **회복 불가능한 정보 손실** 또는 **사용자 발화 → ontology 매칭 자체 실패**가 발생하는 항목.

---

### 🔴 필수 1 — `/api/ontology/search` 의 **한국어 / aliases 매칭** 강화

**현재**: 한국어 키워드로 검색하면 0 hit (실측).

```bash
$ curl '/api/ontology/search?q=실수율&repo_id=slab-design-real&limit=10'
[]
$ curl '/api/ontology/search?q=주문&repo_id=slab-design-real&limit=10'
[]
$ curl '/api/ontology/search?q=엣징&repo_id=slab-design-real&limit=10'
[]
```

반면 같은 ontology DB 에서:

```bash
$ curl '/api/ontology/search?q=productivity&repo_id=slab-design-real&limit=10'
# → action / term / rule 다종 hit (영문)
$ curl '/api/modeling/ontology/term/search?q=Slab&limit=10'
[ {"name":"Slab단중", "english":"SlabWeight", ...}, ... ]   # modeling 의 term/search 는 영문 hit
$ curl '/api/modeling/ontology/term/search?q=주문&limit=10'
HTTP 400   # 한국어 query 는 400 error
```

**왜 필수인가**: Section 3 의 **온톨로지 브릿지 chat** 은 사용자가 자연어로 질문하는 메인 UX. 사용자가 "실수율 어디서 계산되나" "주문 영향 분석" "엣징 룰 보여줘" 처럼 **한국어로 발화** 한다. 영문 키워드로 매칭이 안 되면:

- Section 3 의 `explain` agent → modeling 의 explain 응답으로 1차 매칭은 됨 (한국어 잘 됨).
- 하지만 매칭된 term 의 **연관 action / code / rule 후보** 를 legacy 에서 다시 가져올 때 `/api/ontology/search` 가 한국어 0 hit → 보강 데이터 없음.
- 결과: 사용자에게 "용어는 찾았지만 어디에 구현되어 있는지 모르겠음" 만 표시. **chat UX 의 정보량이 절반.**

**자체 우회의 한계**: Section 3 가 `terms` 1236건을 다 받아 in-memory 한국어 fuzzy 가능하나:
- term 만 매칭. **action / rule / code 까지는 매칭 불가** (그쪽도 한국어 description 가지지만 별도 endpoint, 매번 1.3MB+8KB+5166class 다 받아야).
- modeling 측 single endpoint 가 처리하면 한 번의 호출로 다종 hit.

**요청 명세**:

```cypher
-- /api/ontology/search 의 매칭 정책
MATCH (n)
WHERE n:Term OR n:Action OR n:CodeType OR n:Rule OR n:CodeMethod
WITH n,
  CASE
    WHEN n.korean = $q OR n.english = $q OR n.label = $q THEN 100
    WHEN any(a IN n.aliases WHERE a = $q) THEN 90
    WHEN n.korean CONTAINS $q OR n.label CONTAINS $q THEN 70
    WHEN n.english CONTAINS $q THEN 60
    WHEN n.description CONTAINS $q OR n.statement CONTAINS $q THEN 40
    ELSE 0
  END AS score
WHERE score > 0
RETURN n.fqn, n.label, labels(n)[0] AS kind, score
ORDER BY score DESC
LIMIT $limit
```

**Acceptance**:
- [ ] `?q=실수율&repo_id=slab-design-real` → term (`term.scm.product.productivity_std`) + action (`action.scm.product.cumulative_productivity`) + rule (`rule.scm.std.productivity_safe_range`) **합쳐서 3건 이상** 반환
- [ ] `?q=주문` → term + action 매칭
- [ ] `?q=YieldRate` 와 `?q=실수율` 가 같은 term 을 반환 (한↔영 cross-match)
- [ ] `modeling/ontology/term/search?q=주문` 가 400 아닌 정상 응답

**Section 3 에서의 활용**:
- `BridgeChatPanel` — 사용자 자연어 입력 → 1 호출로 term/action/rule/code 동시 매칭
- `CodeImpactPanel` / `DataImpactPanel` 의 id 자동완성 — 한국어 입력 → 후보 dropdown

---

### 🔴 필수 2 — `action.output` schema 채우기 (현재 55% 비어있음)

**현재**: `slab-design-real` 38 action 중 21 (55%) 이 `output: null`. (실측: `params` 는 87% 채워짐 → OK, `realizations` 는 97% 채워짐 → OK. **output 만 부족.**)

```bash
$ curl /api/ontology/actions/action.scm.final_length_range_실행
{
  "params": [ {name:"order", type:"object_ref", ...}, {name:"slab", ...} ],
  "output": null,                  # ← 55% 가 이 상태
  "preconditions": [], "postconditions": [], "effects": [], ...
}
```

**왜 필수인가**: Section 3 의 **샌드박스** 패널이 `simulate` 시 `expected_output` 을 자동 생성해야 한다. legacy `actions/{fqn}.output` 이 비어있으면:
- `expected_output` 추론 불가 → LLM 으로 합성 (정확도 ↓)
- 사용자 검증 흐름: 케이스 실행 → expected 와 일치 비교 → **expected 가 없으면 비교 자체 불가**

`params` 가 채워져 있으니 input 생성은 됨. **output 만 채우면 검증 fully 동작.**

**요청 명세**: `actions` table 의 `output` column 에 다음 schema 채우기:

```jsonc
{
  "output": {
    "name": "result",
    "type": "object_ref",                   // 또는 primitive: BigDecimal/int/...
    "object_ref_term": "term.scm.slab.slab", // type=object_ref 인 경우
    "unit": null,
    "range": null,
    "nullable": false,
    "description": "변경된 slab entity 반환",
    "anchor_locator": null,
    "confirmed": false
  }
}
```

→ 채울 데이터 소스: `actions.realizations[].code_method_fqn` 의 `return_type` (legacy code-types 의 method.return_type) 으로 자동 매핑 가능.

**Acceptance**:
- [ ] `actions?repo_id=slab-design-real` 의 `output` 충실도 90% 이상 (55% → 90%+)
- [ ] `output.type` = `object_ref` 인 경우 `object_ref_term` 도 명시
- [ ] return_type 이 `void` 인 method 의 action 은 `output: { type: "void" }` (null 이 아닌)

**Section 3 에서의 활용**:
- `SandboxPanel` 의 case 검증 — expected 자동 생성, 결과 일치 표시
- `BridgeChatPanel` 의 `simulate` 분기 — case + expected 한 번에 표시

**Section 2 측 작업 비용**: 자동 — `realizations[].code_method_fqn` 의 return_type 을 lookup 하여 일괄 backfill 스크립트 1회.

---

### 🟡 필수 3 — `repos/{repo_id}/graph` 의 `include_kinds` 필터 정상화 + `mode` doc 일치

**현재**: OpenAPI doc 의 `mode` 는 `^(neighborhood|path|cluster)$` 로 강제되어 있는데, 호출 결과 정상 동작. 다만 `mode` 누락 시 default 가 무엇인지 (현재는 60 nodes 응답이 떨어지지만 spec 에 명시 없음).

**왜 필수인가**: Section 3 가 시각화에 `repos/{repo_id}/graph` 를 직접 호출하는데, 큰 그래프 (60+ nodes) 가 default 로 떨어진다. UI 가 무거워짐. 명확한 default + 명시적 `include_kinds` 필터 동작이 필요.

**요청 명세**:

1. **default mode 명시** — `mode` 미지정 시 `neighborhood` (또는 빈 응답) 가 default 임을 spec 에 적시.
2. **`include_kinds` 동작 검증** — `?include_kinds=term,code_type` 같은 comma-separated 가 동작하는지 확인. 현재 spec 만 있고 실제 동작 미확인.
3. **`connected_only=true` 시 isolated node 제외**.

**Acceptance**:
- [ ] `?mode=neighborhood&focus_fqn=…&hops=2&include_kinds=action,term` → 지정 kind 만 반환
- [ ] `?mode=cluster&n_max=20` → exactly ≤20 cluster nodes
- [ ] OpenAPI `/docs` 에서 mode default 명시

**Section 3 에서의 활용**:
- `OntologyGraphSVG` — `mode=neighborhood&hops=2` 로 적당한 크기 그래프 표시
- 그래프 시각화의 핵심 endpoint — 이게 정확해야 UX 깔끔

---

## 2. (선택) 시뮬 결과 기록 endpoint — 향후 필요

> **우선순위**: 🟢 선택 (지금 막힘 아님)

Section 3 가 시뮬 실행 후 결과를 ontology 에 기록할 수 있는 write endpoint:

```
POST /api/ontology/repos/{repo_id}/simulation-results
{
  "case_id": "TC001",
  "target_kind": "step", "target_id": "7",
  "input": {...}, "expected_output": {...}, "actual_output": {...},
  "matched": true,
  "executed_at": "...",
  "section3_session_id": "..."
}
```

→ Section 3 의 검증 history 가 ontology 에 누적 → 다음 호출 시 verification level 자동 상승.

지금은 Section 3 가 로컬 SSE event 로만 표시하고 사라짐. 누적 안 됨.

→ 막힘은 아니지만 향후 검증 흐름의 핵심.

---

## 3. 요약 — 정말 필요한 것 1줄 정리

| #  | 한 줄                                                                    | 우선순위 | 막힘 정도                                                                        |
| -- | ------------------------------------------------------------------------ | -------- | -------------------------------------------------------------------------------- |
| 1  | `search` 의 한국어 / aliases 매칭                                         | 🔴 필수  | chat UX 정보량 절반 (사용자가 한국어 발화하므로)                                  |
| 2  | `action.output` schema 채우기 (55% → 90%+, return_type 자동 backfill)    | 🔴 필수  | 샌드박스의 expected_output 검증 불가                                              |
| 3  | `repos/.../graph` 의 default mode 명시 + `include_kinds` 동작 검증         | 🟡 권장  | 시각화가 무거워짐 — UI 폴리시 영향                                                |

선택 1건 (시뮬 결과 누적 endpoint) 은 향후 검증 흐름 강화용.

위 3건 이외는 Section 3 가 단독 우회 완료 — Section 2 측 큰 변경 ❌ 필요 없음.

---

## 4. 메타

- **요청 ID**: SECTION2-REQ-ESSENTIAL
- **요청 일자**: 2026-05-12
- **근거 문서**: `toClaude/simulation/ONTOLOGY_API_AUDIT.md` §7 (49 endpoint × multi-variant 호출 결과)
- **취소된 요청**: `SECTION2_REQUEST_02_*.md` ~ `SECTION2_REQUEST_07_*.md` — 보류 (Section 3 단독 우회 완료)
