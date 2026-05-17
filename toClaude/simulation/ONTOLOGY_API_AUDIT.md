# Ontology API 전수 호출 감사 (2026-05-12)

> 목적: 백엔드가 노출하는 51 개 ontology / modeling endpoint 를 다양한 파라미터로 직접 호출하여
> 실제 응답 shape · 데이터 풍부도 · Section 3 활용 가능성을 정리한다.
>
> 결론 요약 (한 줄): **Section 3 는 지금 `/api/modeling/ontology/*` 3개만 쓴다. 그러나 legacy
> `/api/ontology/*` 48 개에 훨씬 풍부한 정보 (Java body_text · anchor · business-rule · call-graph)
> 가 살아 있다. modeling graph 자체는 Class/Method 노드가 0개이므로 코드 영향 분석이 사실상
> legacy API 없이는 불가능하다.**

---

## 0. 인벤토리

| 그룹                   | 개수 | 특징                                                                                          |
| ---------------------- | ---- | --------------------------------------------------------------------------------------------- |
| `/api/modeling/ontology/*` (신규 Neo4j)   | 3    | `/query`, `/graph/stats`, `/term/search`. Section 3 의 현행 데이터 소스.                       |
| `/api/ontology/*` (legacy SQLite, read)    | 41   | terms (1236) · actions (1514) · code-types (5166) · anchor-bindings · business-rules · call-sites · search · modules · queue. |
| `/api/ontology/*` (legacy SQLite, write)   | 7    | confirm / reject / patch / import. Section 3 는 read-only 원칙이므로 호출하지 않는다.          |

`graph_stats` 응답 (modeling graph):

```
Term:19 · TermCategory:5 · Step:12 · Standard:14 · Variable:10 · ErrorCode:1
Class:0  · Method:0  · Table:14
총 75 node / 117 relation
```

→ **modeling graph 에는 Class · Method 가 0 개**. Section 3 가 `target.kind=method|class` 로 impact_analysis 를 호출하면 항상 빈 응답.

---

## 1. `/api/modeling/ontology/query` 의 실제 dispatch 규칙

신규 API 중 가장 중요하지만 가장 약한 endpoint. 직접 호출하여 알아낸 사항.

### 1.1 Request schema (OpenAPI `OntologyRequest`)

```jsonc
{
  "request_id": "필수, UUID 권장",
  "intent": "query | simulate | impact_analysis | optimize | explain", // 5 종, 실 구현 3 종
  "natural_language": "...",   // 선택
  "parameters": { ... },        // intent 별 자유 스키마
  "context": { ... }
}
```

### 1.2 intent 별 동작

| intent              | status                                 | parameters 형식                                                                                  |
| ------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `query`             | ❌ unsupported (`/term/search` 사용 권장) | —                                                                                                |
| `optimize`          | ❌ unsupported (추후 구현)              | —                                                                                                |
| `impact_analysis`   | ✅ table / order / standard_value 동작 · partial: class / column · 빈응답: method | `{ target: { kind, id } }` · `kind` ∈ table·method·class·column·order·standard_value |
| `simulate`          | ✅ step 만 동작                          | `{ target: { kind: "step", id: "<step_number 문자열 또는 정수>" } }`                            |
| `explain`           | ✅ 키워드 추출 시 동작                   | `natural_language` 만으로 OK / `parameters.query` 또는 `parameters.keyword` 도 OK · `keywords` 배열 ❌ |

### 1.3 id 형식 (실측)

- `simulate` step: **`"7"` 또는 정수 7** (step_number). `"step:7"` / `"step.foo"` 는 모두 NG.
- `impact_analysis` table: **`"TB_C40_050SC160"`** (실제 table_name 문자열).
- `impact_analysis` standard_value: 분기 미구현 → table cypher 로 fallback (= 항상 미존재).
- `impact_analysis` order: 임의 string 도 success 처리 (실제 graph 매칭 안 함, 14 Step 무조건 반환).
- `impact_analysis` method/class: graph 에 Method/Class 노드 0개 → 항상 빈 응답.

### 1.4 explain 응답 풍부도

`{intent:"explain", natural_language:"실수율이 뭐야"}` →

```jsonc
{
  "matched_terms":      [ { id, korean, english, category, description } ],
  "process_locations":  [ { step_number, korean_name, roles: ["input"|"output"|"constraint"] } ],
  "source_locations":   [ ],  // 항상 비어있음 (Class/Method 0)
  "data_locations":     [ { table_name, standard_code, schema_name } ],
  "related_terms":      [ ],
  "ontology_trace":     { nodes, edges, cypher }
}
```

→ **Section 3 는 지금 `parameters.keywords` 로 보내고 있어 "검색할 키워드가 필요합니다" 만 받고 있음.**
   → `natural_language` 만 보내면 즉시 풍부한 응답. ⚠️ **버그**.

---

## 2. legacy `/api/ontology/*` 의 보물들

### 2.1 catalog endpoints — Section 3 가 ID 후보 불러올 때 필수

| endpoint                            | size  | 의미                                                                                                 |
| ----------------------------------- | ----- | ---------------------------------------------------------------------------------------------------- |
| `GET /api/ontology/terms`           | 1236  | 한국어 label · aliases · domain · `repo_id` 별 (synthetic-5k 1191 + slab-design-real 45)                |
| `GET /api/ontology/actions`         | 1514  | label · `declared_on_term` · params · realizations[].code_method_fqn · verification_level             |
| `GET /api/ontology/code-types`      | 5166  | 5166 Java class — methods[].body_text · annotations · line_start · line_end · anchors                  |
| `GET /api/ontology/anchor-bindings` |  N    | `code_method_fqn` ↔ `target_action_fqn`·`target_slot` 매핑, line 번호 포함                              |
| `GET /api/ontology/business-rules`  |  N    | `enforced_by[code_method_fqn]` + `operational_history[]` (실 incident `P-2018-0237` 등)                |

⚠️ 필터: `?repo_id=slab-design-real` 로 좁히는 것이 일반적. `repo_id` 미지정 시 synthetic-5k 가 섞인다.

### 2.2 detail endpoints — Section 3 의 4 panel 응답에 그대로 붙일 만한 것

| endpoint                                                              | 활용 시나리오 (Section 3)                                          |
| --------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `GET /api/ontology/code-types/{fqn}`                                  | 영향도 분석 패널에서 method 의 **Java body_text** 펼치기            |
| `GET /api/ontology/code-methods/{fqn}/call-sites`                     | "이 method 는 어떤 callee 를 부르나" — confidence 0 = stdlib 자동 필터, `needs_user_confirm=true` 은 사용자에게 묻기 좋음 |
| `GET /api/ontology/code-methods/{fqn}/anchor-bindings`                | method 내 anchor (literal · invalid_check) line 번호 + slot path    |
| `GET /api/ontology/actions/{fqn}`                                     | action 상세 + realizations[].code_method_fqn (action ↔ code 1:N)    |
| `GET /api/ontology/actions/{fqn}/anchor-bindings`                     | action 의 slot → code anchor 매핑 전체                              |
| `GET /api/ontology/actions/{fqn}/delegates-to-tree?max_depth=3`       | sub-action 호출 트리 (workflow 시각화)                              |
| `GET /api/ontology/actions/{fqn}/realizations-for-input?code_type_fqn=…` | action 의 input 별 method dispatch — sandbox 입력 생성 직전 단계  |
| `GET /api/ontology/actions/{fqn}/resolve-path?slot_path=params/.../...` | slot path → 최종 term FQN 해소. **시작 prefix 는 `params/output/preconditions/postconditions/effects` 중 하나여야** |
| `GET /api/ontology/terms/{fqn}/effective-parts`                       | term 의 part-of/구성 요소                                            |
| `GET /api/ontology/search?q=…`                                        | 통합 검색 (term · action · code 한 번에). modeling `term/search` 보다 hit rate 높음 |
| `GET /api/ontology/repos/{repo_id}/graph?mode=…&focus_fqn=…&hops=…`   | 그래프 시각화 raw — RichResultCard 의 시각화 보강                    |
| `GET /api/ontology/repos/{repo_id}/modules`                           | 모듈 트리 (package 구조)                                            |
| `GET /api/ontology/repos/{repo_id}/modules/inventory?package=…`       | package 내 type/action 카탈로그                                     |
| `GET /api/ontology/repos/{repo_id}/perspectives`                      | 사용자 정의 관점 (저장된 그래프 view)                                |
| `GET /api/ontology/repos/{repo_id}/queue`                             | 미확정 mapping 큐 (LLM 이 사용자에게 물을 거리 발굴용)               |
| `GET /api/ontology/queue/unmapped-methods?repo_id=…`                  | 아직 action 에 매핑 안 된 method 들 — 새 추천 트리거                |
| `GET /api/ontology/queue/ambiguous-call-sites?repo_id=…`              | 다중 후보 call-site — 사용자 disambiguation 거리                    |
| `GET /api/ontology/queue/verification-progress/{repo_id}`             | confirmed 비율 — 대시보드용                                         |

### 2.3 raw 응답 sample (요약)

`code-types/{ProductivityService FQN}` 에서 method 한 개를 발췌:

```jsonc
{
  "fqn": "...ProductivityService.cumulativeProductivity(String,String,String,String,String,String)",
  "body_text": "BigDecimal product = …;\nfor (int i = 0; i < confirmedPlantCd.length(); ++i) { … }",
  "line_start": 80, "line_end": 110,
  "annotations": [...],
  "params": [...],
  "anchors": [ { kind:"literal", locator:"DEFAULT_PRODUCTIVITY = 0.95", line: 31 }, ... ]
}
```

`business-rules` 응답:

```jsonc
{
  "fqn": "rule.scm.std.productivity_safe_range",
  "statement": "실수율 범위 (0.5 ≤ p ≤ 1.0)",
  "severity": "hard",
  "enforced_by": ["...ProductivityService.cumulativeProductivity(...)"],
  "operational_history": [{ "incident_id": "P-2018-0237", "summary": "EdgingSpec 룩업 실패 사고" }]
}
```

→ Section 3 가 영향도 분석할 때 이 두 응답을 결합하면 "이 method 가 어떤 rule 을 강제하며, 과거 어떤 incident 와 연관 있는지" 까지 한 번에 보여줄 수 있다.

---

## 3. Section 3 현행 미활용 = 핵심 손실

### 3.1 modeling explain bug (Section 3 측 수정 대상)

`bridge_agent.py` 가 LLM 분류 결과로 `parameters.keywords` 같은 키를 만들어 보낸다. modeling API 는 `natural_language` 또는 `parameters.query/keyword` 만 인식 → **headless 호출**.

→ 수정: explain 호출 시 무조건 `natural_language=user_message` 를 함께 보내고, `parameters` 는 비워두거나 `{ query: keyword_str }` 형식으로.

### 3.2 코드 정보 (body_text · line · anchors) 0% 노출

ModelingClient 가 `code-types` · `call-sites` · `anchor-bindings` · `business-rules` 를 한 번도 호출하지 않는다. → RichResultCard 의 `source_locations` 가 항상 빈 배열.

### 3.3 ID catalog 미제공

사용자가 SandboxPanel · CodeImpactPanel · DataImpactPanel 에서 빈 input 을 클릭하면 "어떤 id 가 있는지" 알 수 없다. legacy `actions` · `code-types` · `terms` listing 으로 자동완성 가능.

---

## 4. Section 3 단독으로 가능한 보강 (Section 2 수정 없이)

1. **explain bug fix** — `natural_language` 항상 전달.
2. **ModelingClient 확장** — 다음 메서드 추가:
   - `get_code_type(fqn)` → body_text 포함 method 전체
   - `list_code_types(repo_id, kind, role)`
   - `get_call_sites(method_fqn)`
   - `get_method_anchor_bindings(method_fqn)`
   - `get_action(fqn)` / `get_action_anchor_bindings(fqn)` / `get_action_delegates(fqn)` / `get_action_realizations_for_input(fqn, code_type_fqn)`
   - `list_business_rules(repo_id)`
   - `list_anchor_bindings(repo_id)`
   - `get_term(fqn)` / `get_term_effective_parts(fqn)`
   - `legacy_search(q, repo_id, limit)`  ← modeling term/search 의 fallback
   - `list_repo_graph(repo_id, mode, focus_fqn, hops)`
   - `list_repo_modules(repo_id)`
3. **agents 가 modeling.query 응답에 legacy 응답을 enrich** — modeling 의 `source_locations` 가 비어 있으면 anchor-bindings 에서 method_fqn 채우고, code-types 에서 body_text 추출.
4. **카탈로그 GET endpoints 신설** — Section 3 router 에:
   - `GET /api/section3/catalog/steps` → modeling graph_stats 의 Step 노드 12 개
   - `GET /api/section3/catalog/tables` → `/api/ontology/terms?kind=table` 또는 modeling graph
   - `GET /api/section3/catalog/standards` → 위와 동일하게 standard
   - `GET /api/section3/catalog/methods?q=…` → legacy `/api/ontology/search?q=…&limit=20`
5. **UI 자동완성** — 각 panel 의 input 옆 datalist 또는 dropdown.

---

## 5. 그래도 Section 2 가 해야 할 일

(`SECTION2_REQUESTS.md` 에 누적. 별도 파일 `SECTION2_REQUEST_03_*` ~ `SECTION2_REQUEST_06_*` 로 분리.)

핵심 5건:

| # | 우선순위 | 제목                                                          | 1줄 요약                                                                                              |
| - | -------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| 3 | 🔴 블로커 | modeling graph 에 Class/Method 적재                            | 현재 0 개라 `impact_analysis(method/class)` 와 `simulate(method)` 가 사실상 동작 불가                  |
| 4 | 🟡 개선   | `impact_analysis` 의 `standard_value`/`class`/`column` 분기 구현 | 현재 standard_value 는 table cypher 로 잘못 분기, class/column 은 partial 미구현                       |
| 5 | 🟡 개선   | `simulate` 에 method · class · order 지원 추가                  | 현재 step 만. method/class/order 도 valid_range 기반 케이스 생성                                       |
| 6 | 🟢 선택   | `explain` 의 `parameters.keywords` 배열 형식 수용              | 현재 `keyword` (단수) 또는 `natural_language` 만 인식. Section 3 LLM 분류 결과는 배열 형태가 자연스러움 |
| 7 | 🟢 선택   | id 카탈로그 endpoint (`/tables`, `/standards`, `/orders`, `/steps`) | 이미 02 번 요청에서 다룬 내용. Class/Method 적재 (#3) 이후엔 `/methods`, `/classes` 도 추가             |

상세 명세는 `SECTION2_REQUEST_03_*.md` ~ `SECTION2_REQUEST_07_*.md` 참조.

---

## 6. 호출 raw 응답 저장 위치

전수 호출의 raw JSON 은 작업 디렉토리 `/tmp/ontology_audit/` 에 보관 (재현 가능):

- `01_modeling_stats.json` ~ `94_modeling_search_edging.json` (94 호출 — 1차)
- `A01_repo_graph.json` ~ `E07_modeling_search_empty.json` (33 호출 — 2차 보강, 다양한 variant)
- 각 응답의 status / shape / size 는 본 문서 §1·§2·§7 표로 정리됨

재실행 명령:

```bash
cd /tmp/ontology_audit
ls -lh *.json
```

---

## 7. 2차 보강 호출 (2026-05-12 추가) — 결정적 신규 발견

49 endpoint 중 1차 호출에서 누락했거나 variant 미시도였던 항목을 추가 호출. 결정적 신규 발견 4가지.

### 7.1 ★ `/api/ontology/repos/{repo_id}/graph` — Section 3 시각화 완전 자립

`mode ∈ {neighborhood, path, cluster}` × `focus_fqn` · `target_fqn` · `hops` · `n_max` · `include_kinds` · `connected_only`.

| variant                                                  | 응답                                                                                  |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `?mode=neighborhood&focus_fqn=action.scm.product.cumulative_productivity&hops=2` | 4 nodes / 5 edges. action ↔ realization ↔ code_type 정확히 트래버스                  |
| `?mode=path&focus_fqn=A&target_fqn=B&hops=4`              | A · B 두 노드 (edges 0 — 경로 미발견 케이스 정확히 표현)                                |
| `?mode=cluster&n_max=20`                                  | 134 nodes (package 단위 cluster) / 105 edges. 전체 ontology 시각화                     |
| 기본 (`mode` 생략)                                        | 60 nodes / 5 edges                                                                    |

응답 shape:

```jsonc
{
  "repo_id": "slab-design-real",
  "nodes": [{ "id", "label", "kind": "term|code_type|action|domain", "role", "domain", "confirmed", "extra" }],
  "edges": [{ "id", "source", "target", "kind", "label" }],
  "truncated": false,
  "summary": { "nodes_total", "edges_total", "nodes_term", "nodes_code_type", "nodes_action", "nodes_domain" },
  "focus_fqn", "hops"
}
```

→ **modeling `query.ontology_trace` 가 빈 응답이라도, Section 3 가 이 endpoint 를 직접 호출해 그래프 시각화 완벽 자립 가능.** (요청 #3 의 modeling graph 적재가 사실상 불필요해진다.)

### 7.2 ★★ `/api/ontology/repos/{repo_id}/modules/inventory/actions` — method ↔ action 직접 매핑

```bash
curl /api/ontology/repos/slab-design-real/modules/inventory/actions?package=com.example.slabdesign.feature.sd&recursive=true
```

→ 36 action, 모두 `primary_method_fqn` + `verification_level=signature_locked`.

```jsonc
{
  "fqn": "action.scm.batch_design__driver",
  "name": "batch_design",
  "kind": "pure_function",
  "declared_on_term": null,
  "verification_level": "signature_locked",
  "realization_count": 1,
  "primary_method_fqn": "com.example.slabdesign.feature.sd.driver.SdDriver.batchDesign(...)"
}
```

→ **method ↔ action 의 1:1 매핑이 이 한 endpoint 로 다 노출**. modeling graph 에 Class/Method 노드 0개여도, Section 3 가 이걸로 자체 매핑 인덱스 구축 가능. 요청 #3 우회 완전.

### 7.3 ★ `/api/ontology/repos/{repo_id}/modules/inventory?package=…` — package 별 class 카탈로그

50 class. 각 항목: `{ fqn, simple_name, role, kind, has_term, term_fqn, method_count }`.

→ Section 3 자동완성 / catalog UI 의 데이터 소스로 직결.

### 7.4 ★ `POST /api/ontology/repos/{repo_id}/recommend?persist=false` — read-only 추천 dump

```jsonc
{
  "summary": { "terms": "...", "actions": "...", "type_realizations": "..." },
  "persisted": false,
  "term_candidates":         [...19],
  "action_candidates":       [...22],
  "type_realization_candidates": [...24]
}
```

→ modeling builder 가 이걸 기반으로 적재한다. **Section 3 가 이걸 직접 호출하면 modeling 적재 단계 생략 가능** — `persist=false` 면 사이드이펙트 없음.

### 7.5 그 외 variant 발견

| endpoint                                                | 발견                                                                                                                         |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `actions?repo_id=slab-design-real&kind=workflow`        | 1 hit (`슬랩설계_실행`). kind ∈ {workflow, effectful, pure_function} 로 필터링 가능.                                          |
| `actions?verification_min=signature_locked`             | 50KB 전부 verified. Section 3 가 "확정된 action 만" UI 노출 가능.                                                              |
| `actions?declared_on_term=<term>`                       | 특정 term 에 selector — Section 3 의 term-centric 탐색에 활용 가능.                                                            |
| `terms?kind=composite` / `kind=atomic`                  | composite 12KB · atomic 6KB — 분류별 fetch.                                                                                   |
| `terms?domain=scm.product`                              | domain 단위 19KB — 분야별 fetch.                                                                                              |
| `code-types?role=service` / `adapter` / `controller`    | **400 error** — `'service' is not a valid CodeTypeRole`. enum 은 `{framework, domain, infra}` 3개뿐. Section 2 의 분류가 단순. |
| `code-types?kind=enum`                                  | 1 hit (`ProductCategory`). kind = {class, interface, enum, annotation}.                                                       |
| `code-types?repo_id=slab-design-real` 의 role 분포      | `domain:74, infra:27, framework:6` — service/controller 가 다 `domain` 으로 묶임.                                              |
| `actions/{fqn}/resolve-path?slot_path=params`           | `'params' requires index: 'params[i]'`. → `params[0]` 형식 필요.                                                              |
| `actions/{fqn}/resolve-path?slot_path=output`           | `ok=true, last_term_fqn=null` — output 미정의된 action 이 많아 빈 응답.                                                       |
| `actions/{fqn}/resolve-path?slot_path=preconditions`    | 동일 — preconditions 도 미정의 대부분.                                                                                        |
| `search?q=실수율` / `?q=주문` / `?q=edging`             | **0 hit** — 한국어 / aliases / category 매칭 약함. 영문 키워드는 hit.                                                          |
| `search?q=productivity&repo_id=slab-design-real`        | 1.5KB hit. domain 영문은 잘 됨.                                                                                                |
| `search?q=cumulative` (no repo)                         | 10 hit (`syn1/syn2/syn3.action.…cumulative_productivity` 다 섞임). **repo_id 지정 권장**.                                       |
| `modeling/ontology/term/search?q=Slab`                  | 2 hit (`Slab단중`, `Slab설계방침`) — 영문/한국어 mix 표시.                                                                     |
| `modeling/ontology/term/search?q=주문`                  | **400 error**. URL encoding 통과해도 거절.                                                                                     |
| `modeling/ontology/term/search?q=`                      | 422. 빈 query 거절 (OK).                                                                                                       |
| `repos/import/no_such_job`                              | 404 정상.                                                                                                                     |

### 7.6 action 데이터 충실도 통계 (38 action)

- `params`: 87% 채워짐 (5/38 만 빈) — **simulate 케이스 자동 생성 가능 수준**
- `realizations`: 97% 채워짐 (1/38 만 빈) — **method 매핑 충실**
- `output`: 45% 채워짐 (21/38 빈) — **결과 schema 부족** — Acceptance check / expected_output 정확도에 영향

### 7.7 종합 결론 — modeling Neo4j 적재 의존 ❌

§7.1~§7.6 으로 확정된 사실:

> **Section 3 는 legacy `/api/ontology/*` 만으로 modeling Neo4j 와 동등 또는 그 이상의 응답을 합성할 수 있다.**

| Section 3 기능       | 필요한 legacy endpoint                                                  | modeling 의존 |
| -------------------- | ----------------------------------------------------------------------- | ------------- |
| 코드 영향도          | `actions/{fqn}`, `modules/inventory/actions`, `code-types/{fqn}`, `business-rules`, `anchor-bindings`, `repos/{repo_id}/graph?mode=neighborhood` | ❌            |
| 데이터 영향도        | `business-rules`, `anchor-bindings` + 자체 term/standard 인덱스 (`terms`, `repos/{repo_id}/graph`)  | ❌            |
| 시뮬 케이스 생성     | `actions/{fqn}.params`, `code-types/{class}.methods[].params`, `business-rules` (constraint)        | ❌            |
| 자연어 explain       | `search` (영문) + `terms` 자체 fuzzy + `business-rules.statement` | ❌            |
| 그래프 시각화        | `repos/{repo_id}/graph` 3 mode                                          | ❌            |
| 자동완성 / catalog   | `terms`, `actions`, `modules/inventory`, `modules/inventory/actions`     | ❌            |

→ modeling `/query` 호출은 "보조" 로 격하 가능. Section 3 가 legacy 기반 자체 합성기를 갖는다.
