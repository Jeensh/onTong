# Section 2 (Modeling) 에 추가 요청 사항 — 누적 문서

> Section 3 재개편 (2026-05-12~) 진행 중, modeling API 만으로 부족하거나 개선이 필요한 항목을 누적합니다.
> 각 항목에 **우선순위 / 현재 상태 / 우회 가능 여부 / 요청 사유** 를 명시합니다.

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
**현재**:
- `GET /api/modeling/ontology/graph/stats` → Table: 14 / Standard: 14 카운트만 노출
- `impact_analysis(table, "CAST_SPEC")` 호출 시 "대상 미존재" 반환 — 실 id 가 뭔지 알 길 없음
**요청**: 다음 중 하나
- (a) `GET /api/modeling/ontology/tables` → `list[{id, name, schema_name, ...}]`
- (b) `GET /api/modeling/ontology/standards` → `list[{id, code, ...}]`
- 또는 (c) `impact_analysis` 가 "대상 미존재" 시 후보 id list 같이 반환
**사유 (Section 3 측)**: 사용자가 "데이터 변경 분석" 메뉴에서 어떤 table/standard 가 있는지 select / autocomplete 해야 함.
**우회 (Section 3 현재)**: `explain` intent 자연어로 검색해서 우회 (`data_locations` 에 table_name 반환되긴 함).
**발견 일자**: 2026-05-12 Phase 1

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

## 후속 발견 시 추가

새 항목 발견 시 위 형식으로 누적. 우선순위 + 우회 가능 여부 + 발견 일자 명시.
