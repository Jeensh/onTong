# Step OD-11-D3-3 Summary — 승인 큐 + REST/SSE API + 프런트 스텁

**기간**: 2026-04-21
**의존**: D3-2 (Rule-AST + Drift + LLM Comparator 완료)
**후속**: D4 (사람 검증 UI 설계) → Phase E 통합 검증

---

## 1. 목표

D3-1 (`MissingInDetector`) + D3-2 (`GapEngine`) 를 **단일 스캔 오케스트레이터**로 묶어 프론트가 소비 가능한 **REST + SSE API** 로 노출한다. 사람이 "스캔 실행 → 진행 단계 확인 → 후보 목록 확인 → 확정" 의 루프를 완결할 수 있어야 한다.

---

## 2. 산출물

### Backend

| 파일 | 역할 |
|------|------|
| `backend/modeling/gap_detection/gap_scanner.py` | `GapScanner` 오케스트레이터 (MissingIn + GapEngine + ManualRegistry auto-pull). `UnifiedScanResult` frozen dataclass (`code_only`/`manual_only`/`conflicts`/`errors` + `.all` property). Progress callback 4 단계 (`scanning` → `stage1_missing_in` → `stage2_conflicts` → `complete`). |
| `backend/modeling/api/gaps_api.py` | FastAPI 라우터. 4 엔드포인트 + `ScanRequest` Pydantic 모델 + `GapCandidateDTO.from_candidate()` 팩토리 + `init(scanner, gap_store, manual_registry)` 주입 훅. |
| `backend/modeling/gap_detection/embedding_drifter.py` | `HashingTextEmbedder` 추가 (SHA256 3-gram 64-dim L2 normalized, OpenAI 의존성 없는 결정적 fallback). |
| `backend/modeling/gap_detection/__init__.py` | `GapScanner` / `UnifiedScanResult` / `HashingTextEmbedder` export. |
| `backend/main.py` | lifespan 확장: `InMemoryGapStore` → `MissingInDetector` → `create_gap_engine(HIERARCHICAL, rule_differ, drifter, llm_comparator, gap_store)` → `GapScanner(fragment_source=_manual_registry)` → `gaps_api.init(...)` + 라우터 include. |

### API 계약

- **`POST /api/modeling/gaps/scan`** — sync unified scan. Request: `{repo_id, gap_mode, business_terms, rules, described_in, fragments?}`. Response: `UnifiedScanResponse` (`code_only[]` + `manual_only[]` + `conflicts[]` + `errors[]`).
- **`POST /api/modeling/gaps/scan/stream`** — SSE. 이벤트 순서: `scanning` → `stage1_missing_in` → `stage2_conflicts` → `complete` (payload 는 UnifiedScanResponse). `asyncio.to_thread` + **buffered-flush** 패턴 (thread 가 stages list 에 수집 → 메인 루프가 await 완료 후 일괄 emit) 으로 TestClient race 해결.
- **`GET /api/modeling/gaps`** — `?direction=…&severity=…&include_confirmed=true` 필터. 기본: confirmed 제외.
- **`POST /api/modeling/gaps/{gap_id}/confirm`** — 확정 토글, 404 on miss.

### API 설계 결정 (Q1/Q2/Q3)

1. **Q1 = Partial Hybrid** — fragments 만 ManualRegistry 에서 auto-pull (body 에 없으면 자동 조회). `rules` / `described_in` 은 body 필수 (전용 store 아직 없음, Phase E 에서 고려).
2. **Q2 = Unified Scan** — 단일 엔드포인트가 `MISSING_IN` + `CONFLICTS_WITH` 를 함께 실행. 프론트는 필터로만 가른다.
3. **Q3 = SSE Primary** — 4단계 스트리밍을 기본, `/scan` 은 동기 fallback. 실시간성은 PoC 수준 (buffered-flush) — 진짜 stage-by-stage streaming 은 prod 에서 고려.

### Frontend

| 파일 | 역할 |
|------|------|
| `frontend/src/lib/api/modeling.ts` | Gap 섹션 추가 (`GapCandidateDto` / `UnifiedScanResponse` / `GapScanRequest` / `SseEvent` + `scanGaps` / `scanGapsStream` (async generator, `fetch + ReadableStream + TextDecoder`, AbortSignal 지원) / `listGaps` / `confirmGap`). |
| `frontend/src/components/sections/modeling/GapQueue.tsx` (신규) | 필터 바 (direction all/code_only/manual_only/conflicts + severity 드롭다운 + include_confirmed 체크박스) + "스캔 실행" 버튼 (SSE stream, Loader2 + stages 렌더) + 후보 테이블 (direction/severity 컬러 배지, target/counterpart FQN mono, 확정 버튼). |
| `frontend/src/components/sections/ModelingSection.tsx` | MAIN_NAV 에 "갭 큐" (`gap-queue`, `ListChecks` 아이콘) 추가 + view router case 추가. |

---

## 3. 검증

### 자동 테스트

- `tests/test_gap_scanner.py` — 10 케이스 (auto-pull, body-override, 빈 registry, progress 순서, idempotent rescan, persistence, conflicts gap_mode 전달, errors collection, ManualFragment 참조).
- `tests/test_gaps_api.py` — 12 케이스 (503 unconfigured, POST /scan 200 통합 결과, auto-pull, body-override, GET 필터 3종, confirm 200/404, SSE 4-stage sequence, Pydantic 422 validation).
- **22/22 PASS** (0.26s).

### 회귀

- 모델링 회귀 (gap 계열): **127/127 PASS**.
- 전체 pytest: **1498 passed / 31 baseline failed** (31건 모두 기존 실패 — wiki_search feedback format / docx·pdf parsers / skill_api / confidence / image_analysis. 우리 변경 무관 확인 완료).
- Backend `from backend import main` 임포트 성공.
- Runtime route 집계: **156 routes** (D3-2-b 대비 +4).

### 프론트

- `bunx tsc --noEmit` — D3-3 스코프 **clean** (orphan ManualOntologyBuilder / ManualUpload 는 사전 WIP, 어디에도 import 되지 않음 — 본 스텝과 무관).

---

## 4. 주요 결정 기록

1. **Store 아키텍처 격차**: `ManualRegistry` (fragments) 만 존재. `BusinessRule` / `DescribedInBinding` 은 아직 store 없음. Partial hybrid 선택 — Phase E 에서 `RuleRegistry` 설계 예정.
2. **SSE race 해결**: 초기 구현은 `asyncio.Queue + call_soon_threadsafe` + polling loop 였으나, TestClient 동기 모드에서 scan 이 generator 시작 전에 완료되는 타이밍 race 발생. Buffered-flush 로 단순화 — PoC 수용 가능한 trade-off (실시간 진행바 → 빠른 일괄 emit).
3. **`HashingTextEmbedder` fallback**: `CosineDrifter` 초기화에 concrete embedder 필요. OpenAI 의존성 없이 결정적 동작 (SHA256 byte 3-gram → 64-dim L2 norm). Prod 는 `OpenAIEmbedder` 주입 권장.

---

## 5. 다음 스텝 (D4)

1. Gap Queue UI 에 **LLM 재평가 트리거** (사람이 "이 conflict LLM 으로 severity 재평가 요청" 버튼) — Q5=A 의 UI 면 완결.
2. **Evidence panel** — `GapCandidate.evidence` dict 를 접기 가능한 JSON 뷰로 (pdf page / fragment 본문 snippet).
3. `rules` / `described_in` store 설계 — Phase E 진입 전 full auto-pull 가능하게.
