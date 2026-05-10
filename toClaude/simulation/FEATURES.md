# Section 3 (Simulation) — 기능 종합

> 사용자 요청 (2026-05-04): "현재 섹션3 시스템이 어떤 기능이 있는지 정리해서 md에 정리해줘"

마지막 갱신: 2026-05-05 — Phase 7-D 완료 (Java→Python 자동 transpile + UI 리브랜딩 "코드 기반 온톨로지 시뮬레이션").

---

## 1. 한 줄 요약

> **자바 코드에서 추출한 도메인 그래프(온톨로지) 위에서, 룰 한 줄 변경 결과를 자바 빌드 없이 파이썬으로 실제 실행해서 보여주는 코드 기반 온톨로지 시뮬레이션 플랫폼.**

대상 코드베이스: `sample-repos/slab-design` (Java/Spring Boot 21단계 Slab 설계 알고리즘).

---

## 2. 핵심 차별점

| 정적 도구가 못 하는 것 | Section 3 가 하는 것 |
|---|---|
| 코드 호출 그래프만 | **실제 비즈니스 데이터로 알고리즘 실행** + Risk Heatmap |
| "가능한 분기" 만 | **Hypothesis 로 1000건 자동 생성** → 도달 빈도 시각화 |
| 사람이 직접 케이스 작성 | **도메인 용어 → 추천 시나리오 자동 생성** (OntologyBridge) |
| 1회성 실행 | **시나리오 라이브러리 + 영구 이력 + 회귀 자동 검증** |
| 로컬 결과 비교 | **양방향 lineage** (supersedes / baseline_of / regression_of) |

---

## 3. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
│  ┌────────┬──────────┬──────────┬──────────┬────────┬──────────┐    │
│  │샌드박스│시나리오  │실행이력  │회귀검증  │임팩트  │브릿지    │    │
│  │시뮬    │라이브러리│          │          │분석    │/내비게이│    │
│  └────────┴──────────┴──────────┴──────────┴────────┴──────────┘    │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ /api/simulation/*  (Next proxy → :8001)
┌────────────────────────────────▼────────────────────────────────────┐
│                       Backend (FastAPI)                             │
│  ┌──────────────────┬──────────────┬──────────────┬──────────────┐  │
│  │ AsyncJobQueue    │ Storage      │ OntologyBridge│ Heatmap      │  │
│  │ (Sem N=4)        │ (SQLite)     │ (term ↔ step) │ (line cov)   │  │
│  └────────┬─────────┴───────┬──────┴───────┬──────┴──────┬───────┘  │
│           │                 │              │             │          │
│  ┌────────▼─────────────────▼──────────────▼─────────────▼───────┐  │
│  │                    Sandbox (subprocess + setrlimit)            │  │
│  │  validator(0)→thickness(1)→width_range(2)→length_range(3)      │  │
│  │  →second_wgt(5+6)→max_split(7)→split_range(8)→slab_count(9)    │  │
│  │  →slab_weight(10)→final_width_range(16)→final_length_range(17) │  │
│  │  →target_size(18+19)                                           │  │
│  └────────────────────────────────────────────────────────────────┘  │
│           │                                                          │
│           ▼ (Section 2 ontology 호출 — graceful timeout)            │
│  ┌──────────────────────┐                                            │
│  │ OntologyClient       │ →  Section 2 (Modeling) Neo4j BFS / 매핑  │
│  │ (in_process / HTTP)  │                                            │
│  └──────────────────────┘                                            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. 핵심 기능 카탈로그

### 4-1. Sandbox (Python 샌드박스)

자바 21-step 알고리즘의 Python 미러. 격리된 subprocess + `resource.setrlimit` (POSIX) 으로 안전 실행.

**구현된 step (16개)**:

| ID | 자바 대응 | 설명 |
|---|---|---|
| `validator` | SdOrderValidator | DG001~005 검증 (5건) |
| `productivity` | ProductivityService.cumulativeProductivity | 활성 공정 실수율 곱 |
| `thickness` | SdThicknessAction (step 1) | CAST_SPEC → slab.thickness |
| `width_range` | SdWidthRangeAction (step 2) | CAST_SPEC ∩ HR_SPEC ∩ EDGING_GROUP+SPEC |
| `length_range` | SdLengthRangeAction (step 3) | CAST_SPEC ∩ HR_SPEC |
| `second_wgt` | SdSecondWgtLowAction + High (step 5+6) | **HR_MIN/MAX_WGT 2D sheet 룩업** ★ |
| `max_split` | SdMaxSplitCountAction (step 7) | A-a 루프 시작점 |
| `split_range` | SdSplitRangeAction (step 8) | 분할수 고려 단중 범위 |
| `slab_count` | SdSlabCountAction (step 9) | Slab 매수 산정 ★ |
| `slab_weight` | SdInitialSlabWgtAction (step 10) | Slab 단중 산정 |
| `final_width_range` | SdFinalWidthRangeAction (step 16) | 최종 폭 범위 |
| `final_length_range` | SdFinalLengthRangeAction (step 17) | 최종 길이 범위 |
| `target_size` | SdTargetWidth+LengthAction (step 18+19) | 목표 폭/길이 |
| `pipeline` | (compose) | validate → split → count → weight |
| `pipeline_full` | (compose) | **validate → step 1~19 전체 흐름** |
| `plant_mapping_migrate` | — | **마이그 시뮬: 변경 전·후 룩업 결과 비교** |

**격자 룩업 패턴** (Phase 6-A 핵심):
- HrMinWgt/HrMaxWgt: `cell.thickness ≥ input AND cell.width ≥ input ORDER BY ASC LIMIT 1`
- EdgingSpec: 정확매칭 → `*` 와일드카드 fallback → 모두 미존재 시 `EdgingSpecMissingError` (데이터 정합성 차단)
- EdgingGroup: 조건 매칭 + `priority ASC` 첫 row

### 4-2. Hypothesis testgen (케이스 자동 생성)

`hypothesis` 6.x property-based 라이브러리. 4종 strategy:

| 유형 | 의미 | 예 |
|---|---|---|
| `normal` | 통과 기대 | 정상 주문 |
| `boundary` | 임계치 | pkgWgtLow=pkgWgtHigh |
| `error` | DG 트리거 | stockCode=1 → DG001 |
| `performance` | 대량 | designPendQty=10000 |

생성된 케이스는 4-way 병렬 subprocess 로 실행 (격리 + 타임아웃).

### 4-3. SSE 스트리밍

`POST /api/simulation/agents/test-data/stream` — Server-Sent Events:

| 이벤트 | 시점 | payload |
|---|---|---|
| `run_started` | 시작 | total_count, target_id |
| `case_started` | 케이스 시작 | case_id, case_type |
| `case_done` / `case_failed` | 케이스 종료 | result, expected, mismatch |
| `summary` | 모든 케이스 후 | passed/failed/heatmap/code_skeleton |
| `run_complete` | 종료 | elapsed_ms |

### 4-4. Risk Heatmap (★ 동적 커버리지)

자바 코드 라인을 빨강/노랑/녹색으로 칠함:
- 🔴 0건 도달 = "Hypothesis 로도 못 찾은 분기 — 진짜 위험"
- 🟡 ≤10% = 드물게
- 🟢 자주

`backend/simulation/visualization/heatmap.py`:
- `_HEATMAP_MAP`: step_id → Java 파일 + 분기별 라인 매핑 (curated)
- sandbox 결과 → branch label (DG001~005, DG108, PASS) → 라인 카운트

정적 도구는 "테스트가 닿았는가" 만 보여주지만, 우리는 **실제 비즈니스 데이터로 도달한 빈도**.

### 4-5. Cascade Sankey (Impact Panel)

룰 변경의 fan-out 흐름도:
```
변경 전 → OK / Fail
        → 결과 변동 / 결과 동일
        → 변경 후 OK / 변경 후 Fail
```
Plotly sankey diagram. 단순 histogram 보다 깊은 인사이트.

### 4-6. 시나리오 라이브러리 (Phase 6-B)

`backend/simulation/data/scenarios/*.yaml` — 운영자가 검증할 룰 변경 카탈로그.

기본 시드 8건:
- HR 실수율 0.95 → 0.92
- HRF 실수율 0.93 → 0.88
- EDGING_SPEC `*` fallback 누락
- 넓은 Slab (selectedHrTgtWidth=1700) → DG103
- PlantMapping K → CC2/M2 마이그
- 포장단중 범위 좁힘 (10~20)
- Step 1 — A001 품종 두께 (220mm)
- Step 5/6 — 얇고 좁은 Slab (HR_MIN/MAX 격자 외)

**CRUD + 태그/step 필터 + YAML 시드 멱등 로딩.**

### 4-7. 영구 저장소 + lineage (Phase 6-B)

SQLite 3-table:
- `scenarios` — 라이브러리 (id, step_id, inputs YAML, tags, source)
- `runs` — 실행 이력 (inputs/outputs JSON, stage, error_code, baseline flag, parent_run_id)
- `lineage` — 양방향 관계 (supersedes / baseline_of / regression_of)

각 run 은:
- inputs/outputs 직렬화 보관
- baseline 등록 후 회귀 비교 대상
- parent_run_id 로 supersedes chain (룰 fix 후 재실행 추적)

### 4-8. AsyncJobQueue + 자동 회귀 검증 (Phase 6-C)

Wiki Section 의 ImageProcessingQueue 패턴 미러:
- `asyncio.create_task` fire-and-forget — 즉시 queued
- `Semaphore(N=4)` 동시 실행 제한
- 상태머신: queued → running → done | failed | cancelled
- SSE 진행 이벤트 + asyncio.Queue 로 multi-subscriber

**자동 회귀**: scenario 가 baseline 을 가지면, 신규 candidate run 완료 시 자동으로 `regression_diff` 수행 → `job.regression` 에 첨부.

batch 제출: `POST /api/simulation/jobs/batch` 로 여러 시나리오 일괄 실행 + counts/diff 카운트.

### 4-9. OntologyBridge (Phase 6-D — Agent 4 재구성)

이전 "온톨로지 익스플로러" (Agent 4) 를 **시뮬 가이드 역할** 로 재정의.

도메인 용어 16종 정규화 (한국어/영문/컬럼명 alias 통합):
실수율 / 두께 / 포장단중 / 단중 / EDGING / 폭 / 길이 / 분할 / 제강 / HR_MIN_WGT / HR_MAX_WGT / HR_SPEC / CAST_SPEC / 주문 / 설계대기량 / 21-step

각 용어 → 영향받는 step 목록 + **추천 시나리오** (input 프리셋 + rationale 설명).

Section 2 ontology 와 결합:
- `SIMULATION_SKIP_ONTOLOGY=1` (default) → local 매핑만
- `=0` 시 Section 2 `OntologyClient.query` 호출 + 2초 timeout fallback

UI 의 "샌드박스로 →" 버튼으로 시나리오 → SandboxPanel 핸드오프.

### 4-10. UI — 룰 운영 플랫폼 (Phase 6-E)

w-56 좌측 사이드바 + Section 2 디자인 시스템 미러 + 다크모드 호환.

**3 그룹 / 7 패널**:

| 그룹 | 패널 | 역할 |
|---|---|---|
| **실행** | 샌드박스 시뮬 | step 직접 실행 + Hypothesis 케이스 + Risk Heatmap |
|  | 시나리오 라이브러리 | YAML 시드 + CRUD + 태그 필터 + 1-click 잡 등록 |
| **운영** | 실행 이력 | 모든 run 표시 (4초 폴링) + baseline 표시 + 비교 핸드오프 |
|  | 회귀 검증 | baseline ↔ candidate select + diff field-by-field 표시 |
|  | 임팩트 분석 | 룰 변경 전·후 sandbox 2회 실행 + Cascade Sankey |
| **탐색** | 온톨로지 브릿지 | 용어 검색 → 영향 step + 추천 시나리오 |
|  | 코드 내비게이터 | 비즈니스 용어 → Java 코드 위치 (preview 스니펫) |

### 4-11. AI 시나리오 어시스턴트 (★ Phase 7-B)

자연어 ("HR 실수율 0.85로 줄이면?", "PlantMapping K → CC2 마이그하면?") → 바로 sandbox 실행 가능한 ScenarioDraft 변환.

**구조**: Pydantic AI Agent (output_type=ScenarioDraft) + LLM 미가용 시 OntologyBridge 카탈로그 fallback (graceful).
- `method="llm"` — 신뢰도 0.8+
- `method="fallback"` — 키워드 매칭 0.2~0.7

**OntologyBridgePanel** 에 통합: 입력 → "추천 받기" → 카드 (title/rationale/step_id/inputs/tags/confidence) → "샌드박스로" 또는 "라이브러리에 저장" 핸드오프.

LLM disable 토글: `SIMULATION_DISABLE_LLM_ASSIST=1`. 기본은 `prefer_llm=True` 시도 후 fallback.

### 4-12. 시나리오 Export / Import (★ Phase 7-C)

YAML 형식 양방향 전송:
- `GET /scenarios/export?step_id=&tag=` — 필터된 시나리오를 YAML 다운로드
- `POST /scenarios/import` — YAML 텍스트 일괄 등록 (overwrite 옵션)

ScenarioLibraryPanel 헤더에 [Export] [Import] 버튼 + 모달 textarea.
**확산 가치**: 운영 노하우를 YAML 1파일로 팀 간 공유. 다른 도메인 적용 시 fixture 만 교체하고 시나리오 라이브러리 그대로 재사용.

### 4-13. PlantMapping 마이그 Before/After 카드 (★ Phase 7-C)

`MigrationDiffCard` 컴포넌트 — `plant_mapping_migrate` step 결과를 직관적으로 시각화.
- 좌: Before (default 매핑) / 우: After (override 적용)
- castCd / machineCd / thickness 3 필드 비교
- thickness 가 null → 빨간 ★ "마이그 시 깨짐" 강조 + 운영 권장사항 표시

HomeDashboardPanel 에 "라이브 마이그 데모" 섹션으로 1-click 실행. 평가 기준 1-2 (업무 임팩트) 강조.

### 4-14b. Time-travel scrubber (★ Phase 7-E)

샌드박스 SSE 로 누적된 케이스 array 를 timeline 슬라이더로 스크럽 + 자동 재생.

**위치**: 안전 가상 실행 (샌드박스) → 실행 결과 영역, 결과 차트 다음.

**구현**: `frontend/src/components/simulation/TimelineScrubber.tsx`
- cursor 슬라이더 (0 ~ N-1) — 슬라이더 위치 = 그 시점까지 본 케이스 누적 통계
- 자동 재생: 60ms 간격 → 100건 ≈ 6초 영상처럼
- 처음/뒤로(-5)/재생/끝 컨트롤
- 누적 통계: matched / failed / 비율 + 케이스 유형별 진행 + 평균 실행시간
- 진행 바: matched(녹색) / failed(빨강) 비율 시각화
- 현재 cursor 케이스의 `input_data` / `actual_output` JsonTable 미리보기

**구현 변경**:
- `useAgent2Stream.ts` 에 `casesDetailed: CaseDoneEvent["data"][]` 추가 — case_done 풀 payload 보존 (기존 `cases` 는 lightweight 진행표시용)
- 매 case_done 시 `setCasesDetailed(prev => [...prev, d])`

**가치**: 1000건 샌드박스 결과를 정적 통계가 아닌 시계열 영상으로 — "어느 시점부터 fail 이 늘기 시작했나" 직관적 발견.

### 4-14c. Auto-PR 자바 방어 코드 자동 생성 (★ Phase 7-E)

실패 케이스 → LLM 이 자바 메서드에 가드 추가한 패치 + unified diff 자동 생성.

**위치**: 안전 가상 실행 (샌드박스) → 「기대 불일치 케이스」 섹션 상단.

**파이프라인**:
1. step_id → 자바 파일/메서드 매핑 (`autoPrApi.ts STEP_TO_TARGET`)
2. transpile.parser 의 `extract_method` 로 자바 본문 추출 재사용
3. Pydantic AI Agent + `output_type=PatchSuggestion` (rationale / patched_method / additional_imports / risk_notes / confidence)
4. `difflib.unified_diff` 로 unified diff 생성
5. LLM 미가용 시 fallback stub (실패 케이스를 자바 주석으로 보존)

**API** (`/api/simulation/auto_pr/*`):
- `POST /suggest` — 실패 케이스 + 자바 메서드 → PatchSuggestion + unified_diff

**프론트** — `AutoPRCard.tsx`:
- "패치 제안 받기" 버튼 → LLM 호출
- 메타 (LLM/Fallback / 신뢰도 / 추가 import 수)
- rationale 카드 (왜 이 가드?)
- Unified Diff (color-coded: +녹색 / -빨강 / @@보라) + 클립보드 복사
- 패치된 메서드 전체 (details/summary 접힘) + 복사
- risk_notes (AlertTriangle 강조)

**구현 모듈**:
- `backend/simulation/auto_pr/__init__.py / suggester.py`
- `backend/simulation/api/auto_pr_router.py` (path traversal 가드 + ALLOWED_ROOTS 재사용)
- `frontend/src/lib/simulation/autoPrApi.ts`
- `frontend/src/components/simulation/AutoPRCard.tsx`

**테스트** — `tests/simulation/test_auto_pr.py` 6건:
- unified_diff: 변경 검출 / 동일 시 빈 diff
- fallback: stub 패치 / case_id 주석 보존 / +N건 더 있음 truncate / risk_notes
- e2e: parser → suggest → diff

**환경 토글**: `SIMULATION_DISABLE_LLM_AUTO_PR=1` 로 비활성 (CI 안정용).

**가치**: 단순히 "여기서 깨져요" 가 아니라 **"이렇게 고치면 됩니다"** 까지 — 운영자/개발자 사이의 핸드오프 비용 감소.

### 4-14a. Java → Python 자동 transpile (★ Phase 7-D)

다른 도메인 자바 코드를 시뮬레이션 단계로 자동 편입하기 위한 모듈.

**파이프라인**:
1. **tree-sitter (Java)** — `backend/simulation/transpile/parser.py`. 자바 메서드의 시그니처/본문/import/필드/Javadoc 추출. Section 2 의 `tree_sitter_java` 의존성 재사용.
2. **LLM 변환** — `llm_transpile.py`. Pydantic AI Agent + `output_type=PythonStepDraft`. system prompt 에 변환 규칙 11개 (BigDecimal→Decimal, AlgorithmException→ValueError, 외부 import 금지 등). LLM 미가용 시 fallback stub (자바 본문을 파이썬 주석으로 보존).
3. **동치성 검증** — `equivalence.py`.
   - `structural_check`: AST 검사 — signature `(inputs: dict)` 강제 + 금지 import (os/subprocess/socket/requests 등) 차단 + syntax 검증.
   - `shadow_compare`: 변환 결과 vs 기존 미러 step 결과 비교 (같은 inputs N개 → flat field-by-field diff).
4. **저장** — `sandbox/steps_transpiled/<step_id>.py` 로 저장 (overwrite 옵션, structural 검증 강제 통과).

**API** (`/api/simulation/transpile/*`):
- `GET  /methods?java_path=...` — 파일의 메서드 시그니처 목록
- `POST /preview` — 변환 + 동치성 검증 (저장 X)
- `POST /save` — sandbox/steps_transpiled/ 에 저장

**프론트** — `TranspilePanel.tsx` (사이드바 「탐색」 그룹).
- 자바 파일 선택 (slab-design 샘플 2건 프리셋) → 메서드 목록 → LLM 변환 → 신뢰도 / 변환 근거 / 동치성 카드 / 파이썬 코드 미리보기 → 저장.

**테스트** — `tests/simulation/test_transpile.py` (14건):
- parser: list_methods / extract_method / summarize_for_llm / missing case
- transpile: fallback stub structural 통과
- structural_check: 금지 import / signature / missing fn / syntax error
- shadow_compare: 일치 / 불일치 / unknown reference
- e2e: 자바 파일 → fallback transpile → structural pass

**가치**: 새 도메인 (예: 공정관리 / SCM / 품질) 의 자바 코드를 1시간 안에 시뮬레이션 단계로 자동 편입. 운영 노하우 (시나리오 라이브러리) 만 도메인 별로 채우면 끝.

### 4-14. 홈 대시보드 + 온보딩 (★ Phase 7-A)

**HomeDashboardPanel**: 첫 진입 시 표시. 평가 기준 60% 비즈니스 관점 매핑.
- ① 페인포인트 3종 (룰 변경 영향 안 보임 / 테스트 환경 부재 / 회귀 추적성 부재)
- ② Before-After 카드 4종 (시간 단축 / 동적 커버리지 / 자동화 / 추적성)
- ③ 재사용/공유가치 3종 (다른 도메인 / 시나리오 라이브러리 / Section 통합)
- ④ Quick Action 6종 (각 패널로 점프)
- ⑤ 적용 기술 정리
- KPI 4종 (시나리오 / 누적 실행 / baseline / 회귀 발견) — 8초 폴링 라이브 갱신
- 라이브 마이그 데모 섹션 (1-click)

**OnboardingBanner**: 5단계 미니 투어. localStorage dismiss 기억. "사용 가이드 다시 보기" 링크.

**HelpPopover**: 각 패널 헤더 ? 아이콘. 클릭 시 "이 메뉴는 무엇을?" 팝업.

사이드바 hover 시 HTML title 툴팁 (긴 설명).

### 4-15. 안전성 (subprocess sandbox)

- `resource.setrlimit` (Linux/macOS): RLIMIT_AS / RLIMIT_CPU / RLIMIT_NOFILE
- subprocess timeout
- JSON I/O 표준 (stdin/stdout 만)
- Path traversal 차단

---

## 5. API 엔드포인트 종합

### 5-1. Agents (Phase 1~5)
- `POST /api/simulation/agents/impact` — 임팩트 분석
- `POST /api/simulation/agents/test-data` — Hypothesis 케이스 동기 (≤200건)
- `POST /api/simulation/agents/test-data/stream` — SSE 스트리밍
- `POST /api/simulation/agents/locator` — 코드 위치 파악
- `GET  /api/simulation/agents/explorer/search|expand|path`
- `GET  /api/simulation/agents/ontology-graph`

### 5-2. Scenarios (Phase 6-B)
- `GET    /api/simulation/scenarios?step_id=&tag=`
- `GET    /api/simulation/scenarios/{id}`
- `POST   /api/simulation/scenarios`
- `PUT    /api/simulation/scenarios/{id}`
- `DELETE /api/simulation/scenarios/{id}`
- `POST   /api/simulation/scenarios/seed`
- `POST   /api/simulation/scenarios/{id}/run`
- `POST   /api/simulation/scenarios/{id}/baseline?run_id=`

### 5-3. Runs (Phase 6-B)
- `GET    /api/simulation/runs?scenario_id=&step_id=&only_baseline=&limit=`
- `GET    /api/simulation/runs/{id}`
- `GET    /api/simulation/runs/{id}/lineage`
- `POST   /api/simulation/runs/regression`

### 5-4. Jobs (Phase 6-C)
- `POST   /api/simulation/jobs/run`
- `POST   /api/simulation/jobs/scenario/{id}/run`
- `POST   /api/simulation/jobs/batch`
- `GET    /api/simulation/jobs?limit=`
- `GET    /api/simulation/jobs/{id}`
- `POST   /api/simulation/jobs/{id}/cancel`
- `GET    /api/simulation/jobs/{id}/stream`  ← SSE
- `GET    /api/simulation/jobs/batch/{id}`

### 5-5. Bridge (Phase 6-D + 7-B)
- `GET    /api/simulation/bridge/terms`
- `GET    /api/simulation/bridge/term/{term}/overlay`
- `GET    /api/simulation/bridge/step/{step_id}/terms`
- `GET    /api/simulation/bridge/index`
- `POST   /api/simulation/bridge/assist` ← AI 어시스턴트 (자연어 → ScenarioDraft)

### 5-7. Export / Import (Phase 7-C)
- `GET    /api/simulation/scenarios/export?step_id=&tag=` (YAML 응답)
- `POST   /api/simulation/scenarios/import`
- `POST   /api/simulation/scenarios/from-assist` (어시스턴트 결과 라이브러리 저장)

### 5-8. Java→Python Transpile (★ Phase 7-D)
- `GET    /api/simulation/transpile/methods?java_path=` — 자바 파일 메서드 시그니처 목록
- `POST   /api/simulation/transpile/preview` — 변환 + 동치성 검증
- `POST   /api/simulation/transpile/save` — sandbox/steps_transpiled/<step_id>.py 저장

### 5-9. Auto-PR 자바 방어 코드 (★ Phase 7-E)
- `POST   /api/simulation/auto_pr/suggest` — 실패 케이스 + 자바 메서드 → PatchSuggestion + unified diff

### 5-6. Slab Agent (Phase 1)
- `POST   /api/simulation/slab-design/agent` — 자연어 → 두께/실수율 변경 요약

---

## 6. 운영자 워크플로우 시나리오

### 6-1. 룰 변경 영향 시뮬

1. **온톨로지 브릿지** 에서 "실수율" 검색
2. 영향 step 8개 + 추천 시나리오 2건 표시
3. "HR 실수율 0.95 → 0.92" 카드의 "샌드박스로 →" 클릭
4. **샌드박스 시뮬** 자동 진입 + step 프리셋
5. 100건 × 2 케이스 유형 실행 → Risk Heatmap 으로 도달 분기 시각화

### 6-2. 회귀 검증 (룰 fix 후)

1. **시나리오 라이브러리** 에서 "EDGING_SPEC `*` fallback 누락" 실행
2. **실행 이력** 에서 해당 run 의 "baseline" 클릭
3. 데이터 fix 후 동일 시나리오 재실행 → 자동으로 baseline 과 diff
4. **회귀 검증** 패널에서 비교 → field 변경 0건 확인 → fix 검증 완료

### 6-3. 마이그레이션 영향

1. **시나리오 라이브러리** 에서 "PlantMapping K → CC2/M2 마이그" 실행
2. 결과: `before.thickness=220 / after.thickness=null` → 마이그 시 어느 주문 깨지는지 발견
3. **온톨로지 브릿지** 에서 "제강" 검색 → 영향 step 5개 추가 검증

### 6-4. 데이터 정합성 회귀

1. **시나리오 라이브러리** 의 "EDGING `*` fallback 누락" 시나리오 batch 실행
2. **실행 이력** 에서 어느 시나리오에서 EdgingSpecMissingError 발생했는지 확인
3. 데이터 정합성 점검 PR 생성

---

## 7. 검증 / 테스트 현황

`pytest tests/simulation/` (2026-05-04 기준):

| 모듈 | 건수 |
|---|---|
| test_sandbox_phase1.py | 33 |
| test_testgen.py | 11 |
| test_demo_e2e.py | 6 |
| test_agent1.py + 2 + 3 | 28 |
| test_sandbox_subprocess.py | 11 |
| **test_sandbox_phase6a.py** | **29** (2D / `*` / migrate / pipeline_full) |
| **test_storage.py** | **16** (CRUD / lineage / regression diff) |
| **test_jobs.py** | **9** (queue / auto regression / batch / SSE) |
| **test_bridge.py** | **16** (term resolution / suggestions / overlay) |
| **합계** | **159 통과** |

TypeScript: `tsc --noEmit` exit 0.

---

## 8. 코드 구조

```
backend/simulation/
├── sandbox/
│   ├── fixtures/
│   │   ├── domain.py           # SDOrder/SDSlab/CastSpec/HrSpec/HrMinWgt/...
│   │   ├── repository.py        # In-memory repos + 2D sheet lookup
│   │   ├── fixtures.py          # mock 데이터 팩토리 13종
│   │   └── steps/               # 16개 step 모듈
│   ├── registry.py              # step_id → 실행 함수 + JSON 직렬화
│   └── runner.py                # subprocess + setrlimit + ThreadPool
├── testgen/
│   ├── hypothesis_strategies.py # 4종 strategy
│   └── case_builder.py          # build_cases / analyze / summarize
├── agents/
│   ├── agent1_impact.py         # 임팩트 (rule diff)
│   ├── agent2_test_data.py      # 케이스 생성 + SSE
│   └── agent3_locator.py        # 코드 위치 + handoff
├── visualization/
│   ├── diff_summary.py          # impact 시각화
│   └── heatmap.py               # Risk Heatmap (line-level)
├── storage/                     # ★ Phase 6-B
│   ├── db.py                    # SQLite schema + 트랜잭션
│   ├── scenarios.py             # CRUD + YAML 로더
│   └── runs.py                  # 실행 이력 + lineage + regression
├── jobs/                        # ★ Phase 6-C
│   └── queue.py                 # AsyncJobQueue + 자동 회귀
├── ontology_bridge/             # ★ Phase 6-D
│   └── bridge.py                # 용어 → step + 추천 시나리오
├── client/
│   └── ontology_client.py       # Section 2 in_process / HTTP
├── data/
│   └── scenarios/
│       └── rule_changes.yaml    # 8건 시드
└── api/
    ├── slab_agent.py
    ├── agents_router.py
    ├── scenarios_router.py      # ★ Phase 6-B
    ├── jobs_router.py           # ★ Phase 6-C
    └── bridge_router.py         # ★ Phase 6-D

frontend/src/
├── components/simulation/
│   ├── SimulationSection.tsx    # 7-패널 사이드바
│   ├── SandboxPanel.tsx
│   ├── ImpactPanel.tsx
│   ├── NavigatorPanel.tsx
│   ├── ScenarioLibraryPanel.tsx # ★ Phase 6-E
│   ├── RunHistoryPanel.tsx       # ★
│   ├── RegressionPanel.tsx       # ★
│   ├── OntologyBridgePanel.tsx   # ★
│   ├── SandboxConsole.tsx
│   ├── ResultChart.tsx
│   └── RiskHeatmap.tsx
└── lib/simulation/
    ├── agentApi.ts
    ├── storageApi.ts             # ★ Phase 6-E
    └── useAgent2Stream.ts
```

---

## 9. 데모 5분 시나리오 (요약)

1. (30초) "이 사례에서 Slab 매수가 잘못 계산되어 시정이 나갔다고 가정"
2. (60초) **온톨로지 브릿지**: "실수율" → 영향 8 step + 추천 시나리오
3. (90초) **샌드박스 시뮬**: pipeline_full + Hypothesis 100건 → Risk Heatmap (java SdSlabCountAction line 35 빨강)
4. (60초) **임팩트 분석**: HR 0.95 → 0.92 → Cascade Sankey (50건 결과 변동)
5. (60초) **시나리오 라이브러리** 에서 baseline 등록 → 룰 fix 후 회귀 자동 검증 → diff 0 확인

---

## 10. 향후 후보 (Phase 7+)

- ~~Java → Python 자동 transpile (tree-sitter + LLM)~~ ✅ Phase 7-D 완료 (2026-05-05)
- ~~What-if 미니 슬라이더 (결과 화면에서 값 즉시 바꿔 재시뮬)~~ ✅ Phase 7-E 완료
- ~~Time-travel scrubber (1000건 케이스 영상처럼 스크럽)~~ ✅ Phase 7-E 완료
- ~~Auto-PR 패치 생성 (실패 케이스 → LLM Java 방어 코드)~~ ✅ Phase 7-E 완료
- Z3 SMT solver (Hypothesis 보다 정확한 boundary) — **보류** (의존성 무거움 + 학술적, 데모 가치 낮음)
- Worker pool 재사용 (cold start 최적화 — N>500 케이스)
- LLM tool-use 로 boundary 케이스 힌트 보강
- baseline 자동 추천 (시나리오 첫 정상 실행 자동 등록)
- Heatmap 라인 매핑 자동화 (현재 hand-curated → tree-sitter 활용 — Phase 7-D 가 인프라 제공)
- Section 2 온톨로지 BFS 통합 (현재 graceful skip)
- transpile shadow 비교 UX — Hypothesis 자동 sample 생성 (현재는 hard-coded 3건 샘플)
- Auto-PR 의 GitHub PR 직접 생성 (현재는 클립보드 복사만)
