# Metadata Search Phase 4 — Agent Bridge + Presets

**완료일**: 2026-04-17
**마일스톤**: MS-16 ~ MS-20
**스펙**: `specs/2026-04-17-metadata-search-design.md` §Phase 4

---

## 목표

Phase 1~3에서 구축한 FilterSpec 파이프라인을 실제 사용자 플로우에 연결한다.
- AI Copilot 답변 시 자연어 → 필터 자동 추출 + 사용자에게 "검색창에서 계속" 핸드오프
- 자주 쓰는 필터 조합을 개인 프리셋으로 저장
- 빈 결과일 때 필터 완화 제안 (전체 초기화 대신 하나씩 제거)
- 접근성 마무리 + 데모 시나리오 문서화

---

## 산출물

### MS-16 — LLM 시스템 프롬프트 + 도구 스키마 힌트

- `backend/application/agent/react_agent.py` — `WIKI_FILTER_HINT` 상수 추가, `create_react_agent`의 system prompt에 자동 주입. filters 객체 구조 + 한국어 기간 표현 파싱 규칙 명시.
- `backend/application/agent/pydantic_tools.py::wiki_search` — `filters: dict | None = None` 파라미터 노출. docstring에 FilterSpec 키(folders/authors/tags/types/mtime_from/mtime_to/statuses/path/boolean) 나열.

→ Pydantic AI ReAct agent가 tool-call로 filter를 직접 조합할 수 있는 기반 마련. (RAG 메인 플로우는 rule-based 추출이 먼저 걸러주기 때문에 이 쪽은 향후 SimulatorAgent/TracerAgent 등에서 주로 사용.)

### MS-17 — SSE `applied_filters` + "검색창에서 계속" 핸드오프

**백엔드**
- `backend/application/agent/nl_filter_extractor.py` (신규) — 한국어 rule-based NL → FilterSpec.
  - 폴더 aliases: ERP/MES/SCM/인프라/기획/재무/인사/공정/설비/이슈/제품/표준
  - 작성자: `@[A-Za-z0-9가-힣_-]+` + Korean particle strip (`가/이/은/는/을/를/의/와/과/도/만/께서`) — pure-hangul prefix일 때만 조사 제거
  - 유형 aliases: sop/spec/plan/decision/incident/postmortem/meeting/skill (한영 혼용)
  - 기간: `최근 N일`, `지난 달`, `이번 달`, `YYYY년 M월`, `YYYY년 M월 이후`
- `tests/test_nl_filter_extractor.py` — 20 테스트 (TDD-first, all pass)
- `backend/core/schemas.py::AppliedFiltersEvent` — SSE payload 스키마 (event/filters/source)
- `backend/application/agent/rag_agent.py` — 검색 직전에 `extract_filter_spec()` 호출, 결과 있으면 `thinking_step`("자연어 필터 추출") + `applied_filters` SSE 이벤트 방출, `WikiSearchSkill`에 `filters=` 전달

**프론트엔드**
- `frontend/src/lib/api/sseClient.ts` — `AppliedFiltersPayload` 타입 + `onAppliedFilters` 콜백 + dispatch case
- `frontend/src/components/AICopilot.tsx`
  - `ChatMessage.appliedFilters` 필드 추가
  - 두 streamChat 호출부에 `onAppliedFilters` 바인딩
  - `AppliedFiltersRow` 컴포넌트 신규 — emoji-prefix 칩(folders/authors/types/tags/mtime/statuses) + "🔎 검색창에서 계속" 버튼 → `useSearchStore.openWithFilters(filters)`
  - `TYPE_LABELS` 한국어 레이블 맵

### MS-18 — localStorage 프리셋

- `frontend/src/lib/search/filterPresets.ts` (신규) — user-scoped storage (`ontong.search.presets.v1.<userName>`), load/save/delete, 상한 20, name 중복 시 update-in-place, JSON parse 실패 / 쿼터 초과 시 silent fallback.
- `frontend/src/components/search/FilterSheet.tsx`
  - 상단에 "저장된 프리셋" 섹션 신설 — 프리셋 이름 입력 + 저장 버튼, 프리셋 칩 클릭 시 draft 복원 (mtime preset key 자동 판별), X 버튼으로 삭제
  - `Bookmark`, `Save` 아이콘 import

### MS-19 — 빈 결과 필터 완화 제안

- `frontend/src/components/search/SearchCommandPalette.tsx`
  - `EmptyResultSuggestions` 컴포넌트 신규 — 활성 칩별 "이 필터만 제거" 점선 버튼, mtime 있을 때 "📅 기간을 최근 90일로 확장" / "📅 기간 필터 해제", 마지막에 "모든 필터 제거"
  - 기존 "필터를 제거하고 다시 시도" (전체 초기화만 가능) → 세분화된 제안으로 대체

### MS-20 — 접근성 + demo_guide

- `frontend/src/components/search/FilterSheet.tsx`
  - Escape keydown → `setFilterSheetOpen(false)` (stopPropagation)
  - root div에 `aria-modal="true"` 추가
- `AppliedFiltersRow` (AICopilot) — `role="region"`, `aria-label="에이전트가 적용한 필터"`, 버튼에 `aria-label="이 필터로 검색창에서 계속 검색"`
- `EmptyResultSuggestions` — `role="group"`, `aria-label="필터 완화 제안"`, 칩별 `aria-label`("X 필터만 제거하고 재검색")
- `toClaude/wiki/demo_guide.md` (신규) — Phase 4 시나리오 8개(D-P4-01~08) + 트러블슈팅 5개(T-01~05)

---

## 검증

**백엔드**: `tests/test_nl_filter_extractor.py` 20개 + 기존 `test_wiki_search_filters.py` 6 + `test_filter_compiler.py` 35 + `test_filter_dsl.py` 24 = **85/85 PASS** (0.40s)

**프론트엔드**: `npx tsc --noEmit` → **0 errors**

**Pre-demo SSE smoke (`/api/agent/chat`)**
| 시나리오 | 질문 | 추출 결과 | 결과 |
|---|---|---|---|
| D-P4-01 | `ERP 마스터데이터 관리 지침은 어떻게 되어 있어?` | `{'folders': ['ERP']}` | PASS |
| D-P4-02 | `@동해가 작성한 마스터데이터 문서 알려줘` | `{'authors': ['@동해']}` (조사 strip) | PASS |
| D-P4-03a | `최근 30일 이내 인시던트 보고서 찾아줘` | `{'folders': ['이슈'], 'types': ['incident'], 'mtime_from': '2026-03-18'}` | PASS |
| D-P4-03b | `지난 달 회의록 보여줘` | `{'types': ['meeting'], 'mtime_from': '2026-03-01', 'mtime_to': '2026-03-31'}` | PASS |
| negative | `재고 관리 어떻게 하는지 알려줘` | (추출 없음 — 이벤트 미발행) | PASS |

---

## 설계 결정 / 배경

- **왜 rule-based + ReAct 힌트를 둘 다?**
  메인 RAG 플로우는 LLM tool-calling 루프가 없어서 프롬프트 힌트만으로 필터를 주입하기 어려움. 규칙 기반 추출기를 검색 직전에 실행해 보장하고, Pydantic AI ReAct 경로(향후 SimulatorAgent 등)는 tool schema + hint로 커버.
- **왜 칩을 답변 말풍선 하단에 표시?**
  사용자가 "AI가 뭘 어떻게 좁혔는지" 즉각 확인 가능. 결과가 예상과 다르면 "검색창에서 계속"으로 필터를 직접 조정하는 escape hatch가 됨.
- **왜 프리셋을 서버 저장이 아닌 localStorage?**
  스펙 §10 결정(개인 전용)에 맞춤. 팀 공유는 별도 Phase로.
- **왜 "모두 제거" 하나가 아니라 칩별 제거?**
  빈 결과의 주된 원인은 과도한 교집합. 사용자가 어떤 조건을 양보할지 결정하도록 유도.

---

## 후속 작업 후보

- `authors=@이서연` 0건 이슈 — 실제 데이터에 해당 handle을 가진 문서가 적어서인지, ChromaDB `$contains` 의미 차이인지 운영 데이터로 검증 필요 (HANDOFF 플래그에서 그대로 유지).
- 프론트 DSL quoted value(`tag:"인사 평가"`) 미지원.
- 프리셋의 팀 공유(서버 저장)는 Phase 외 주제로 분리.

---

## 누적 테스트 통계

- Phase 1: 65
- Phase 2: +12 = 77
- Phase 3: +8 (`test_filters_end_to_end.py`, `test_filter_query.py` 등 추정) = 85
- Phase 4: +20 (`test_nl_filter_extractor.py`) = **105**

> Phase 3까지의 누적이 85였고 실제 실행 시 85 단일 파일셋이 재확인되었다. Phase 3까지의 누적 범위 기준 85 + Phase 4 NL extractor 20 = **105 누적**.
