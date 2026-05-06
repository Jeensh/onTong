# 위키 섹션 Demo Guide (Section 1)

> 각 Phase 완료마다 데모 시나리오와 트러블슈팅을 누적 기록.
> 세션 시작 시 참조, 사용자에게 데모 넘기기 전 해당 시나리오 최소 1개 수동 확인.

---

## Phase 4 — Agent 브릿지 + 프리셋 (MS-16 ~ MS-20)

### Phase 4 시나리오 개요

| # | 목적 | 진입점 | 예상 결과 |
|---|------|--------|-----------|
| D-P4-01 | NL 필터 자동 추출 (폴더) | AI Copilot | `📁 ERP` 칩 + 필터 적용된 RAG 답변 |
| D-P4-02 | NL 필터 자동 추출 (작성자 + 조사 strip) | AI Copilot | `👤 @동해` 칩 (조사 제거) |
| D-P4-03 | NL 필터 자동 추출 (기간 "최근 30일") | AI Copilot | `📅 YYYY-MM-DD 이후` 칩 |
| D-P4-04 | "검색창에서 계속" 핸드오프 | AI Copilot → 검색 팔레트 | 팔레트 열리며 동일 필터 사전 적용 |
| D-P4-05 | 프리셋 저장 → 재사용 | FilterSheet | 프리셋 칩 클릭 시 draft 복원 |
| D-P4-06 | 프리셋 삭제 | FilterSheet | 즉시 목록에서 제거 |
| D-P4-07 | 빈 결과 필터 완화 제안 | 검색 팔레트 | 칩별 "이 필터만 제거" + "기간 90일로 확장" |
| D-P4-08 | 접근성: Escape 닫기 / aria-modal | FilterSheet | Escape로 닫힘, 스크린리더 모달 공지 |

---

### D-P4-01 — NL 필터 자동 추출 (폴더)

**사전조건**: 백엔드 + 프론트 실행 중. `wiki/ERP/` 아래 문서 존재.

1. AI Copilot 열기 (우측 패널)
2. 질문 입력: `ERP 마스터데이터 관리 지침은 어떻게 되어 있어?`
3. SSE 시퀀스 확인:
   - `thinking_step` "자연어 필터 추출" ← 새 단계
   - `applied_filters` 이벤트 (source="nl")
   - `content_delta` 스트리밍
4. 답변 말풍선 위에 "적용된 필터: `📁 ERP`" 칩 row + "🔎 검색창에서 계속" 버튼 렌더링 확인

**PASS 기준**:
- 필터 칩이 답변 소스(SourceChips)보다 위에 표시
- `appliedFilters` 메시지 상태에 저장 (후속 핸드오프 가능)

---

### D-P4-02 — NL 필터 자동 추출 (작성자 + 조사 strip)

1. AI Copilot에 질문 입력: `@동해가 작성한 마스터데이터 문서 찾아줘`
2. 확인: `👤 @동해` 칩 (조사 "가"가 정확히 제거되었는지)
3. 같은 플로우로 `@재인은`, `@지우는` 시도 → 각각 `@재인`, `@지우` 추출

**왜 중요한가**: `_AUTHOR_RE` 그리디 매칭이 한글 조사까지 삼키는 것을 `_strip_particle`로 방지.
초기 구현에서 `@동해가`가 필터로 들어가서 모든 문서가 0건이었던 버그를 차단.

---

### D-P4-03 — NL 필터 자동 추출 (기간)

1. `최근 30일 이내 인시던트 보고서` → `📅 YYYY-MM-DD 이후` + `📄 인시던트` 2칩
2. `2026년 3월 이후 결정 문서` → `📅 2026-03-01 이후` + `📄 결정`
3. `지난 달 회의록` → `📅 (prev month start) ~ (prev month end)` + `📄 회의`

Backend 유닛: `tests/test_nl_filter_extractor.py` (20 테스트)로 엣지 케이스 고정.

---

### D-P4-04 — "검색창에서 계속" 핸드오프

1. D-P4-01 재현 후 답변 하단 "🔎 검색창에서 계속" 클릭
2. SearchCommandPalette 열림 확인 (Cmd/Ctrl+K로 여는 것과 동일)
3. 칩 영역에 `📁 ERP` 이미 적용됨
4. 검색창에서 자유롭게 query 입력 가능 — 같은 필터 재사용

**구현 포인트**: `useSearchStore.openWithFilters(filters)` — merge + `isOpen: true` 한 번에.

---

### D-P4-05 — 프리셋 저장 → 재사용

1. 검색 팔레트 열고 "+ 필터" → FilterSheet 드로어 열림
2. 폴더 `ERP` + 작성자 `@동해` + 유형 `sop` 추가
3. 상단 "저장된 프리셋" 섹션에서 이름 입력: `내 ERP SOP`
4. "저장" 클릭 → 프리셋 칩 즉시 등장
5. FilterSheet 닫은 뒤 재오픈 → 프리셋 보임 (localStorage 영속성)
6. 프리셋 칩 클릭 → draft가 복원됨 (mtime preset은 저장된 값 기준 자동 판별)
7. "적용" 눌러 반영

**저장 위치**: `localStorage["ontong.search.presets.v1.<userName>"]` — 유저 스코프.
**상한**: 20개 (이후 오래된 것부터 밀림).

---

### D-P4-06 — 프리셋 삭제

1. D-P4-05 상태에서 프리셋 칩 우측 X 클릭
2. 칩 사라짐 + localStorage에서 제거 확인

---

### D-P4-07 — 빈 결과 필터 완화 제안

1. 검색 팔레트 열고 query `aslkdjfhaskdf` (고의적 0건) + 필터 `📁 ERP` + `📅 2026-04-15 이후`
2. CommandEmpty 영역에서 다음 요소 확인:
   - "검색 결과가 없습니다" 헤더
   - 칩별 "이 필터만 제거" 토글(점선 테두리, hover 시 destructive)
   - "📅 기간을 최근 90일로 확장" + "📅 기간 필터 해제" 버튼 (mtime 있을 때만)
   - "모든 필터 제거" 버튼

**UX 원칙**: 사용자가 어떤 필터를 양보할지 선택하도록 — "전체 제거"만 제공하지 않음.

---

### D-P4-08 — 접근성 수동 체크

1. FilterSheet 열기 (검색 팔레트 "+ 필터" 버튼)
2. `Escape` 키 누르면 닫힘 확인
3. 브라우저 DevTools → Accessibility 패널 → 다이얼로그 `aria-modal="true"`, `aria-label="고급 필터"` 확인
4. 답변 필터 칩 row에 `role="region"`, `aria-label="에이전트가 적용한 필터"` 확인
5. 빈 결과 제안 영역에 `role="group"`, `aria-label="필터 완화 제안"` 확인
6. Tab 순회: 칩 삭제 X → 검색 입력 → 모드 토글 → "+ 필터" → 결과 아이템 순 정상 이동

---

## Troubleshooting

### T-01: `applied_filters` SSE가 안 들어오는데요
- 질문에 폴더/작성자/유형/기간 중 하나라도 들어가야 추출됩니다 (rule-based).
- 로그에 `자연어 필터 추출` thinking_step이 찍히는지 확인 (`backend/application/agent/rag_agent.py` 주위).
- 추출 결과가 빈 dict면 이벤트 스킵.

### T-02: 프리셋이 저장 안 돼요
- `localStorage` 쿼터 초과 가능성 (Safari ITP 등). 콘솔에 `preset save failed:` 로그 확인.
- 시크릿 모드에서는 세션 종료 시 사라짐 — 정상 동작.
- 20개 상한 도달 시 가장 오래된 프리셋이 밀려남.

### T-03: "검색창에서 계속" 클릭해도 필터가 안 들어옴
- 답변 시점에 `msg.appliedFilters`가 비어있으면 버튼이 렌더링되지 않음 (정상).
- `useSearchStore.openWithFilters`가 `mergeFilters` 동등 로직 — 기존 검색 필터가 있으면 덮어쓰기가 아니라 merge.

### T-04: 한글 조사가 작성자 이름에 붙어 있어요
- `@동해가`, `@재인은` 같은 케이스는 `_strip_particle()`로 제거.
- 신규 조사가 필요하면 `backend/application/agent/nl_filter_extractor.py::_KOREAN_PARTICLES` 에 추가.

### T-05: FilterSheet Escape가 ChatPanel Escape랑 충돌해요
- `stopPropagation` 처리됨. 충돌 발생 시 `FilterSheet.tsx`의 keydown 핸들러 우선순위 확인.

---

## 에이전트(ReAct tool-call) 경로 통합 테스트 (2026-04-18)

`nl_filter_extractor.py`(rule-based)와 별개로, Pydantic AI ReAct 에이전트가 시스템 프롬프트 힌트만으로 `filters`를 직접 조합하는 경로도 실 LLM 호출 테스트로 계약 고정.

```bash
source venv/bin/activate && set -a && source .env && set +a
python -m pytest tests/test_react_agent_filters.py -v
# 3 PASS, ~40s (Anthropic Sonnet 4)
# API 키 없으면 자동 skip
```

**왜 중요한가**: 초기 실행에서 "지난 달"이 학습 데이터 기준 2024-11로 해석되는 hallucination이 발견돼 `react_agent.py::build_wiki_filter_hint(today)`로 오늘 날짜 주입. 이 테스트가 회귀를 차단.

---

## Phase 3 빠른 스모크 (보존용)

1. 검색 팔레트에서 `folder:ERP ` 입력 (trailing space) → 칩 자동 승격
2. TreeNav 폴더 우클릭 → "이 폴더에서 검색" → 팔레트 열리며 `📁 <path>` 칩
3. FilterSheet에서 폴더/태그 include·exclude + AND/OR 조합 → 백엔드 필터 적용 확인
