# Section 2 (Modeling) 에 추가 요청 사항 — 누적 문서

> Section 3 재개편 (2026-05-12~) 진행 중, modeling API 만으로 부족하거나 개선이 필요한 항목을 누적합니다.
> 각 항목에 **우선순위 / 현재 상태 / 우회 가능 여부 / 요청 사유** 를 명시합니다.

---

## ★ 핵심 문서 (2026-05-12 최종) — 정말 필요한 것만

> **👉 [`SECTION2_REQUEST_ESSENTIAL.md`](./SECTION2_REQUEST_ESSENTIAL.md)** — 49 endpoint 전수 호출 감사 결과,
> Section 3 단독 우회 후에도 정말 필요한 **3건만** 추린 단일 요청서. **Section 2 개발자는 이 문서 먼저 읽기 권장**.

아래 ① ~ ⑦ 의 개별 항목은 현재 **Section 3 단독 우회 완료** 로 인해 보류된 백로그. 시간 나면 작업 권장이지만 막힘 ❌.

근거: [`ONTOLOGY_API_AUDIT.md`](./ONTOLOGY_API_AUDIT.md) §7 (다양한 variant 호출 결과)

---

상태 표기:
- 🔴 **블로커** — 이게 없으면 핵심 기능 미동작
- 🟡 **개선** — 동작은 하지만 UX/정확도 떨어짐
- 🟢 **선택** — 있으면 좋음, 우회 가능

---

## ① `simulate` intent — `method` / `class` / `standard_value` 지원 확장

**우선순위**: 🟡 개선
**현재**: `target.kind=step` 만 지원. `method` / `class` / `standard_value` 호출 시 `unsupported` 반환.
**요청**: `simulate` 에서 `method` 와 `class` 도 지원 (해당 method 의 입력 변수 / valid_range / dependencies 기반 test_cases 생성).
**사유 (Section 3 측)**: 사용자가 "이 method 만 단독 시뮬레이션" 하고 싶을 때 필요. 현재는 Step 으로만 grouped 시뮬 가능.
**우회 (Section 3 현재)**: `impact_analysis(method)` → 영향 받는 Step 발견 → 그 Step 으로 simulate. (한 단계 추가)
**발견 일자**: 2026-05-12 Phase 1

---

## ② `table` / `standard_value` 의 실제 id 카탈로그 endpoint

**우선순위**: 🔴 블로커 (UX)
**상세 문서**: 👉 [`SECTION2_REQUEST_02_id_catalog.md`](./SECTION2_REQUEST_02_id_catalog.md) (API 명세 / Acceptance Criteria / 구현 힌트 / 예시 응답 포함)

**한 줄 요약**: `/query (impact_analysis)` 의 `target.id` 후보 카탈로그가 없어 사용자가 어떤 id 가 있는지 모름.

**요청 (권장)**:
- `GET /api/modeling/ontology/tables`
- `GET /api/modeling/ontology/standards`
- `GET /api/modeling/ontology/orders`

→ 상세 문서 참조.
**발견 일자**: 2026-05-12 Phase 1

---

## ★★ NEW (2026-05-12 사용자 요청) — Build step 제거 / lazy 적재로 architecture 전환

**우선순위**: 🟡 개선 (아키텍처)
**발견 일자**: 2026-05-12 (사용자 의도 직접 표명)

**사용자 메시지**:
> "적재해서 읽는 방식이 아니라, 처음부터 ontology API 호출 후 그 응답을 가지고 작업이 되게끔 개편이 필요할 것 같은데."

**현재**:
- `data/*.json` → `builders/*.py` (Python 모듈 실행) → Neo4j MERGE → query
- "Build step" 이 사용자/운영자에게 명시적 명령으로 존재
- API 호출만으로 셋업 → 동작 흐름 불가

**요청 (옵션)**:
- 옵션 A — startup lifespan 자동 build (개발/데모 환경)
- 옵션 B — `POST /api/modeling/ontology/rebuild` HTTP API
- 옵션 C — lazy build (modeling API 가 빈 응답 감지 시 자동 적재)
- 옵션 D — Neo4j 제거, modeling API 가 매 호출 JSON 직접 읽어 응답 합성. graph traversal 은 in-memory 로 재구현.

**trade-off (옵션 D 의 경우)**:
- impact_analysis 의 `indirect_impact.downstream_steps` 같은 multi-hop traversal 재구현 필요
- 16 relation 의 양방향 index 자체 구현
- 16+ Cypher 쿼리 → Python in-memory traversal 로 재작성

**Section 3 측 상태**:
- 사용자가 명시: **Section 2 코드 수정 절대 안 됨**. 이 작업은 Section 2 책임.
- Section 3 는 modeling API 응답만 활용. modeling 내부가 어떻게 동작하든 무관.

**현재 우회 (Section 3 측)**:
- modeling API 의 미활용 endpoint 들 적극 활용 (`/api/ontology/code-types` body_text 등)
- 빈 응답 시 사용자에게 명시적 안내 ("modeling 데이터 적재 필요 — `python -m backend.modeling.ontology.builders.*`")

---

## ★ NEW — Build/Rebuild HTTP API 신설 (적재 자동화)

**우선순위**: 🟡 개선 (운영 UX)
**발견 일자**: 2026-05-12 (사용자 검증 흐름 중)

**현재 상황**:
- `/api/modeling/ontology/*` 는 **read-only** (query / search / stats)
- ontology 적재는 **Python 모듈 직접 실행** 필요 (HTTP API 없음):
  ```
  python -m backend.modeling.ontology.builders.layer1_business
  python -m backend.modeling.ontology.builders.layer2_process
  python -m backend.modeling.ontology.builders.layer3_code
  python -m backend.modeling.ontology.builders.bridges
  ```
- 사용자가 Neo4j volume 을 비우면 Section 3 가 "헛방" 응답 — 적재가 사용자/운영자의 별도 step

**요청**:
- 옵션 A: `POST /api/modeling/ontology/rebuild` — body 로 `{"layers": ["1","2","3","bridges"]}` 받아 builder 들 sync/async 실행. async 면 SSE 로 progress.
- 옵션 B: backend startup lifespan 에서 `Neo4j 가 비어있으면 자동 build` (개발 환경 한정 toggle)

**Section 3 측 영향**:
- 옵션 A 만 있어도 Section 3 가 "데이터 비어있으면 자동으로 rebuild 호출" 같은 UX 가능
- 사용자 검증 흐름 (volume 삭제 → 재기동 → API 호출 → 결과 확인) 이 한 줄로 단축

**우회 (현재)**:
- 사용자가 직접 4 builder Python 모듈 실행

---

## ③ `explain` 의 keyword alias / partial match 강화

**우선순위**: 🟡 개선
**현재**: LLM 으로 키워드 추출은 잘 됨 (e.g. "단중상한" 추출 OK). 단 ontology DB 의 Term 매칭 시 정확 매치 / 부분 매치 약함 — `matched_terms: []` (0건) 가 자주 나옴.
**요청**: Term 의 `aliases` 활용 강화 + 부분 일치 매칭 + 한국어 / 영문 / 약어 cross-match.
**우회 (Section 3 현재)**: `term/search?q=...` 별도 GET endpoint 활용 (자동완성용).
**발견 일자**: 2026-05-12 Phase 1

---

## ④ Java 소스 라인 fetch endpoint

**우선순위**: 🟡 개선 (영향 분석 / AST 파싱 단계에서 유용)
**현재**: `explain` 응답의 `source_locations` 에 `file_path` 는 있지만, 실 코드 line 내용은 없음.
**요청**: `GET /api/modeling/ontology/source/{file_path}?line_start=N&line_end=M` — 해당 파일의 line range 코드 반환.
**사유 (Section 3 측)**: AST 파싱 / "이 method 의 실 코드 보기" / LLM 으로 Python 변환 시 reference 가능.
**우회 (Section 3 현재)**: 우리 LLM 이 code_method_fqn + signature 만 가지고 Python mirror 생성. 실 Java 코드 없이도 method 의 input/output schema 만으로 적당히 합성. 정확도 떨어질 가능성.
**발견 일자**: 2026-05-12 Phase 1

---

## ⑤ `code_skeleton` 의 Python 버전 옵션

**우선순위**: 🟢 선택
**현재**: `simulate` 응답의 `code_skeleton` 이 JUnit (Java) 한 가지.
**요청**: `parameters.lang = "python" | "java"` 같은 옵션 추가, Python skeleton 도 반환.
**우회 (Section 3 현재)**: JUnit skeleton 을 LLM 으로 Python pytest 형식으로 변환. 정확하게 동작 중.
**발견 일자**: 2026-05-12 Phase 1

---

## ⑥ 시뮬 실행 결과를 ontology 에 기록하는 endpoint

**우선순위**: 🟢 선택
**현재**: 없음.
**요청**: `POST /api/modeling/ontology/simulation-result` — Section 3 가 실행한 시뮬 결과 (test_case + outcome + cypher reference) 를 ontology 에 `RAN_ON` / `VERIFIED_BY` 관계로 기록.
**사유**: modeling 측 verification level 자동 상승 / 누적 시뮬 history 추적.
**발견 일자**: 2026-05-12 Phase 1

---

## ⑦ `Variable` 의 `valid_range` 명시 노출

**우선순위**: 🟢 선택
**현재**: `simulate` 가 응답 시 자동으로 valid_range 기반 case 생성. Section 3 가 직접 추론하려면 `Variable` 의 min/max/sample 메타가 따로 필요.
**요청**: `GET /api/modeling/ontology/variables/{id}` → `valid_range / unit / sample_values`.
**우회 (Section 3 현재)**: `simulate` 의 응답 그대로 사용. Section 3 가 직접 합성할 때만 필요.
**발견 일자**: 2026-05-12 Phase 1

---

---

## ★★★ NEW (2026-05-12) — Ontology API 전수 호출 감사 기반 신규 요청 5 건

**감사 문서**: 👉 [`ONTOLOGY_API_AUDIT.md`](./ONTOLOGY_API_AUDIT.md) (51 endpoint 호출 결과 + Section 3 활용 가능성)

51 개 endpoint 를 다양한 파라미터로 직접 호출한 결과를 토대로 다음 5 건을 정식 요청서로 작성.

---

## ③ modeling graph 에 `Class` / `Method` 노드 적재

**우선순위**: 🔴 블로커
**상세 문서**: 👉 [`SECTION2_REQUEST_03_method_class_in_graph.md`](./SECTION2_REQUEST_03_method_class_in_graph.md)

**한 줄 요약**: `graph/stats` 에 `Class:0, Method:0`. 따라서 `impact_analysis(method|class)` 가 항상 빈 응답. legacy `/api/ontology/code-types` (5166 class) 의 정보를 modeling Neo4j 에도 적재해 달라.

**Section 3 막힌 곳**: `CodeImpactPanel` (좌측 nav 3번) 의 핵심 기능이 100% 실패.

---

## ④ `impact_analysis` 의 `standard_value` / `class` / `column` 분기 정상화

**우선순위**: 🟡 개선
**상세 문서**: 👉 [`SECTION2_REQUEST_04_impact_dispatch.md`](./SECTION2_REQUEST_04_impact_dispatch.md)

**한 줄 요약**: `standard_value` 호출이 잘못된 cypher (`MATCH (t:Table)`) 로 라우팅되고, `class`/`column` 은 partial 미구현. 4 kind 정상화.

**Section 3 막힌 곳**: `DataImpactPanel` 의 `target_kind=standard_value` 시 "테이블이 그래프에 없습니다" 오답.

---

## ⑤ `simulate` intent 에 `method` / `class` / `order` 추가 지원

**우선순위**: 🟡 개선
**상세 문서**: 👉 [`SECTION2_REQUEST_05_simulate_kinds.md`](./SECTION2_REQUEST_05_simulate_kinds.md)

**한 줄 요약**: 현재 `step` 만 지원. `method` / `class` / `order` 도 valid_range / param schema 기반 자동 케이스 생성. 보너스로 `parameters.lang=python` 옵션도.

**Section 3 막힌 곳**: `SandboxPanel` 의 method 단독 시뮬이 modeling 으로 불가 → LLM fallback 으로 정확도 떨어짐.

---

## ⑥ `explain` 의 `parameters.keywords[]` 배열 형식 수용

**우선순위**: 🟡 개선 (Section 3 가 우회 가능)
**상세 문서**: 👉 [`SECTION2_REQUEST_06_explain_params.md`](./SECTION2_REQUEST_06_explain_params.md)

**한 줄 요약**: 현재 `natural_language` 또는 `parameters.query|keyword` (단수) 만 인식. Section 3 LLM 은 자연스럽게 `keywords: string[]` 을 만든다. 둘 다 받도록 normalize.

**Section 3 막힌 곳**: `BridgeChatPanel` 의 explain 호출이 "검색할 키워드가 필요합니다" 로 자주 거절됨. (Section 3 측 즉시 우회 적용 예정)

---

## ⑦ `term/search` 의 hit rate / alias / 한↔영 cross-match 강화

**우선순위**: 🟢 선택
**상세 문서**: 👉 [`SECTION2_REQUEST_07_modeling_search_quality.md`](./SECTION2_REQUEST_07_modeling_search_quality.md)

**한 줄 요약**: `/api/modeling/ontology/term/search?q=실수율` 빈 응답. 같은 graph 의 explain 은 잘 매칭되는데 search GET 만 약하다. exact / prefix / contains / alias / 한↔영 cross-match 강화.

**Section 3 막힌 곳**: 자동완성 / 빠른 검색 UX. (legacy `/api/ontology/search` 로 우회 중)

---

## 후속 발견 시 추가

새 항목 발견 시 위 형식으로 누적. 우선순위 + 우회 가능 여부 + 발견 일자 명시.
