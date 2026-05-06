# OD-11-D1.6 — parser_protocol EntityKinds/RelationKinds 확장

**완료 일시**: 2026-04-20
**담당 섹션**: modeling (Section 2)
**선행**: D1.5 (DTO 확장 완료)
**후속**: D2 (인제스트 파이프라인)

---

## 1. 범위

Round 3 (기준서/조직/Gap 레이어) 에서 정의한 13 DTO 중 그래프 기록 대상인 5 엔티티 + 6 관계를 `parser_protocol.py` 레지스트리에 **category="concept"** 로 등록. `EntityKinds` / `RelationKinds` 편의 문자열 상수 클래스에 동일 항목을 노출.

## 2. 산출물

### 편집 (1 파일)
- `backend/modeling/code_analysis/parser_protocol.py`
  - 모듈 docstring : Round 3 블록 추가 (Q1~Q9 합의 참조)
  - `_DEFAULT_ENTITY_KINDS` 튜플 : +5 `EntityKindSpec(..., "concept", ...)`
    - `business_process` / `role` / `manual_document` / `manual_section` / `manual_fragment`
  - `_DEFAULT_RELATION_KINDS` 튜플 : +6 `RelationKindSpec(..., "concept", ...)`
    - `part_of` / `responsible_for` / `parent_process` / `described_in` / `conflicts_with` / `missing_in`
  - `EntityKinds` 클래스 : +5 상수
    - `BUSINESS_PROCESS` / `ROLE` / `MANUAL_DOCUMENT` / `MANUAL_SECTION` / `MANUAL_FRAGMENT`
  - `RelationKinds` 클래스 : +6 상수
    - `PART_OF` / `RESPONSIBLE_FOR` / `PARENT_PROCESS` / `DESCRIBED_IN` / `CONFLICTS_WITH` / `MISSING_IN`

### 신규 (1 파일)
- `tests/test_parser_protocol_phase_d.py` — 24 테스트
  - 5 × `test_phase_d_entity_kind_registered_with_concept_category` (parametrized)
  - 6 × `test_phase_d_relation_kind_registered_with_concept_category` (parametrized)
  - `test_phase_d_entity_kind_count_in_concept_category` (Round2+Round3 ≥ 7)
  - `test_phase_d_relation_kind_count_in_concept_category` (Round2+Round3 ≥ 9)
  - `test_phase_d_entity_constants_match_registry`
  - `test_phase_d_relation_constants_match_registry`
  - `test_business_process_entity_instantiable`
  - `test_role_entity_instantiable`
  - `test_manual_entities_instantiable` (Document + Section + Fragment)
  - 6 × `test_phase_d_relation_instantiable_via_code_relation` (parametrized)

---

## 3. 설계 결정

### category="concept" 정책
Round 2 에서 도입한 `concept` 라벨을 Round 3 에도 유지. 이유 :
- `code` / `spring` / `db` / `config` 카테고리는 Java/Spring 파싱 결과에서 직접 추출되는 노드/엣지
- `concept` 는 **사람 승인 + 수동 seed + LLM 제안** 으로 만들어지는 비즈니스/조직/문서 레이어
- 그래프 뷰에서 카테고리별 시각 스타일 분리 시 `code` vs `concept` 이분법이 실용적

### ontology_validator 영향도
`backend/modeling/ontology/schema.py` 의 `RelationKind = Literal["part_of", "uses", "produces", "responsible_for"]` 는 별도 YAML 온톨로지 (BusinessTerm/Rule 빌더) 전용 좁은 리터럴 타입. `part_of` / `responsible_for` 이름이 겹치지만 모듈 경계가 완전히 분리돼 있어 **충돌 없음**. parser_protocol 레지스트리 확장이 ontology_validator 를 깨뜨리지 않음을 확인.

### graph_writer 화이트리스트
`backend/modeling/code_analysis/graph_writer.py` 는 `RelationKindRegistry.is_registered(rel.kind)` 로 동적 검증 — 신규 kind 6 종이 자동으로 통과. 정규식 이중 검사 `^[A-Z_]+$` 는 `graph_writer` 가 `rel.kind.upper()` 로 Cypher 라벨을 구성하므로 Phase D kinds 도 그대로 호환.

---

## 4. 검증

### 단위 — `tests/test_parser_protocol_phase_d.py`
```
24/24 PASS (0.02s)
```

### 회귀 — 모델링 범위
```
pytest tests/ -k "modeling or parser_protocol or java_parser or code_analysis or graph_writer or ontology or mapping_models or manual_models or reverse_lookup or term_resolver or cross_file or spring"
→ 524/524 PASS (3.19s)
```
D1.5 (246/246) 에서 D1.6 테스트 24 + 이미 등록된 테스트 254 추가 → 총 524. 모든 테스트 그대로 통과.

### 레지스트리 카운트
- entity kinds : 18 (B7-2 기준) → Round 2 2 추가 → Round 3 5 추가 = **25**
- relation kinds : 18 (B7-2 기준) → Round 2 3 추가 → Round 3 6 추가 = **27**

---

## 5. 다음 단계 (D2)

인제스트 파이프라인 (`backend/modeling/manual_ingest/`) :
- 3 트리거 : UI 업로드 + watch folder + git hook (Q7=E)
- 5 파서 : pypdf + pdfplumber (PDF, Q9=D) / python-docx (Word) / python-pptx (PPT, 기존 재사용) / OCREngine (이미지, 기존 재사용) / MD (기본 파이썬)
- 출력 : ManualDocument → ManualSection → ManualFragment 파이프라인
- 신규 deps : `pypdf` `pdfplumber` `python-docx` (python-pptx 는 이미 존재)

사용자 승인 대기.
