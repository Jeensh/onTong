# STEP 3f — 사용자 3 요구사항 처리 + 종합 정리

**완료일**: 2026-05-10
**브랜치**: `section3-integration`

## 0번 — Section 2 ↔ Section 3 통신 방식 검증

**사용자 질문**: "온톨로지 모델링 (섹션 2) 를 api 로 받아서 섹션 3 과 연결?"

**답변** (조사 후): **현재 in-process facade 방식. HTTP API 호출 아님.**

검증 — `06-developer-onboarding.md` 의 통신 규약:
- Q4 (line 501-506): "두 가지만 OK — HTTP / Python facade"
- line 78: "OntologyQueryClientImpl Python facade (**HTTP 우회 가능**)"

→ **둘 다 명시적으로 허용**. 현재 구현 (in-process facade) = **규약 정합 ✅**.

사용자 결정: "**규약대로 진행**" — 현재 in-process facade 유지. landing page 의 chapter 03 reveal 에 명시 결정 기록.

## 요구사항 1 — Java ↔ Python differential 정합성

### 사용자 불만
- raw 응답 비교 어려움
- 필드 다름
- Python 응답에 null 많음

### 원인 분석
- `field_diffs` 가 mismatch 만 보고 → java_only / python_only / null 분리 없음
- 두 raw payload 가 다른 schema 라 같은 path 비교 시 한쪽 None
- frontend 가 raw payload 만 dump

### 해결 (`backend/simulation/jvm_bridge/differential.py`)

#### `FieldDiff.category` 추가 — 5 카테고리 분류
| category | 의미 |
|---|---|
| matched | 두 값 같음 (numeric tolerance 포함) |
| mismatched | 양쪽 값 있는데 다름 |
| java_only | python 만 None / 누락 |
| python_only | java 만 None / 누락 |
| both_null | 양쪽 None — diff list 에서 자동 제외 (count 만) |

#### `_normalize_payload()` helper
- null / 빈 문자열 / 빈 dict / 빈 list 재귀 제거
- `java_payload_normalized` / `python_payload_normalized` 응답에 추가
- UI 가 원본 vs 정리본 둘 다 노출 가능

#### `_classify_diff()` helper
- (java_value, python_value) → (category, is_close)

#### `DifferentialResult` 신규 필드
- `matched_count / mismatched_count / java_only_count / python_only_count / both_null_count`
- `summary` — "38 matched / 2 mismatched / 1 java_only / 0 python_only" 한 줄

### Test
- `tests/test_differential_classification.py` (16 test): normalize / classify / DifferentialResult 필드 / e2e mock

## 요구사항 2 — Ontology 근거 보기

### 사용자 의도
"시뮬 결과가 ontology 모델링 기반임을 사용자가 명시적으로 느낄 수 있게."

### 신설 endpoint — `GET /api/simulation/runs/{run_id}/ontology-evidence`

각 SimResult 항목 → ontology source trace:

```json
{
  "action_fqn": "action.scm.std.match_customer_limit_for_order",
  "ontology_facade": "backend.modeling.api.ontology_query.OntologyQueryClientImpl",
  "ontology_transport": "in-process facade (HTTP 우회)",
  "traces": [
    {
      "evidence_kind": "realized_method",
      "evidence_id": "...CustomerStdService.findFirstMatch(...)",
      "ontology_source": "Realization (mapping_layer.schema.Realization)",
      "ontology_facade_call": "OntologyQueryClient.get_action(...).realizations",
      "ontology_data": {"confirmed": true, "confidence": 1.0, ...},
      "explanation": "✅ Realization → Java method ... (confirmed=True, confidence=1.00)"
    },
    ...
  ],
  "summary": {"action": 1, "realized_method": 1, "br": 1, "anchor": 2}
}
```

### 4 evidence kind
| kind | source | facade call |
|---|---|---|
| action | `Action (mapping_layer.schema.Action)` | `get_action(fqn)` |
| realized_method | `Realization` | `get_action(fqn).realizations` |
| br | `Action.preconditions / postconditions` | `get_action(fqn).preconditions/postconditions` |
| anchor | `AnchorBinding (mapping_layer.schema.AnchorBinding)` | `get_anchor_bindings_for_action(fqn)` |

### 신설 파일
- `backend/simulation/api/ontology_evidence_router.py` (+250 lines)
- `tests/test_ontology_evidence.py` (7 test)
- `backend/main.py` 등록

## 요구사항 3 — Landing page 최신화 + 스타일 개편

### 변경 (`frontend/public/section3.html` 전면 재작성)

| 영역 | 이전 | 새 버전 |
|---|---|---|
| 폰트 | system-ui mix | Apple SD Gothic Neo + SF Pro Text |
| 컬러 | 단순 회색 (#0c1219, #94a3b8 등) | Claude warm cream (#faf9f5) + accent orange (#d97757) |
| 레이아웃 | 좌측 toc + 본문 (2-column) | 상단 nav + chapter scroll (story-driven) |
| 상호작용 | 정적 텍스트 + 앵커 링크 | `<details class="reveal">` 펼침 토글 (호기심 유발) |
| 구조 | 11 섹션 (목차 기반) | 6 chapter + hero + CTA (스토리라인) |
| 가독성 | 12px monospace 다수 | 16px 본문 + 22px lede + 36px h2 |

### 6 chapter 스토리라인
1. **CHAPTER 01 · 왜** — 정적 도구의 한계 3가지 (reveal)
2. **CHAPTER 02 · 무엇을** — ChangeSpec 한 번 → SimResult verdict (verdict 3가지 reveal)
3. **CHAPTER 03 · 어떻게** — 5 컴포넌트 + ontology in-process facade 설명 (reveal)
4. **CHAPTER 04 · 근거** — `/ontology-evidence` 사용법 (4 evidence kind reveal)
5. **CHAPTER 05 · Java↔Python** — 5 카테고리 분류 + null 해결 (원인+해결 reveal)
6. **CHAPTER 06 · 운영화** — 통계 4 stats + 13 endpoints reveal + FailurePolicy reveal

### Reveal (호기심 유발 클릭)
- 8 개의 `<details class="reveal">` 블록
- summary 만 보이면 "→ 자세히" hint
- 펼침 시 "↑ 접기"
- 호버 시 border 색 강조

### 좌측 탭 → 상단 nav (3-B 처리됨)
- 이전: `<nav class="toc">` 좌측 250px 고정 (12 항목)
- 새: 상단 sticky nav (왜 / 무엇을 / 어떻게 / 근거 / Java↔Python / 운영화 / 직접 보기 →)
- scroll spy — 현재 chapter 가 nav 에 accent 색으로 표시

### 보존
- `frontend/public/section3.legacy.html` — 이전 버전 유지 (사용자 지시 "지우진말고")
- 새 페이지 footer 에 legacy link

## 회귀

| | |
|---|---|
| 신규 test (1 + 2) | 23 test (differential 16 + ontology evidence 7) |
| 전체 `tests/simulation/` | **423 passed** (이전 400 → +23), 17 skipped, 3 failed (sample-repos — 무관) |
| Section isolation | ✅ |

## 사용자 요구 처리 결과

| 요구 | 결과 |
|---|---|
| 0. 통신 구조 확인 | ✅ Onboarding Q4 정합 — in-process facade 유지 결정 (사용자 "규약대로 진행") |
| 1. Java↔Python 비교 어려움 + null 많음 | ✅ 5 카테고리 분류 + normalize + summary 한 줄 |
| 2. ontology 근거 보기 | ✅ GET /runs/{id}/ontology-evidence — 4 evidence kind 별 trace |
| 3-A. 랜딩 페이지 최신화 + Apple/Claude 스타일 | ✅ 전면 재작성 — Apple SD Gothic Neo + Claude orange + Cream |
| 3-A. 클릭 expand (호기심 유발) | ✅ 8 reveal 블록 |
| 3-A. 스토리라인 | ✅ 6 chapter (왜/무엇을/어떻게/근거/Java↔Python/운영화) |
| 3-B. 좌측 탭 → 다른 레이아웃 (랜딩 페이지) | ✅ 좌측 toc → 상단 sticky nav + chapter scroll |

## Diff stat

- `backend/simulation/jvm_bridge/differential.py` — 5 카테고리 + normalize +120 lines
- `backend/simulation/api/ontology_evidence_router.py` — 신규 +250 lines
- `backend/main.py` — ontology_evidence_router 등록
- `frontend/public/section3.html` — 전면 재작성 (~600 lines)
- `frontend/public/section3.legacy.html` — 이전 버전 보존 (2094 lines)
- 테스트 2개 신규 (23 test)

## 다음 작업 (사용자 결정 대기)

- frontend SimulationSection 의 in-app 좌측 탭 — 변경 안 함 (사용자가 랜딩 페이지만 의도)
- ontology evidence frontend UI — JavaPythonComparePanel 처럼 SimResult 옆에 토글 패널 가능 (별도 task)
- differential frontend — `category` 필드 활용해 카테고리별 필터 UI (별도 task)
