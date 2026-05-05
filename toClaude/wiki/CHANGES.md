# 위키 섹션 변경/추가 요청

> 세션 사이에 요구사항이 바뀌거나 추가되면 여기에 메모.
> 매 세션 시작 시 `[ ]` 항목 확인 후 우선 처리.
> 처리 완료 시 `[x]`로 체크하고 `TODO.md`에 반영.

---

## 2026-05-05 (Rename + 동시성 정합성 — 브레인스토밍 + 설계)

- [x] **3 라운드 인터랙티브 브레인스토밍** (HTML 폼 ↔ 사용자)
  - r1: 스코프 / 연산 / 식별 모델 / 락 / TX / 배포 / UX / cleanup / 시급도 결정
  - r2: 5 핵심 결정 (참조 패치 정확도 / 락 모델 / 충돌+스냅샷 / 인프라 / Phase) + 추가 통찰 (수만 동시사용자, OCC, 경로/내용 분리, 소/대 추상화)
  - r3: OQ-1~7 결정 + Delete 차단 정책 (G7) 추가
  - 산출: `specs/2026-05-05-rename-concurrency-brainstorm-r1/2/3.html`
- [x] **Design Doc v0.2 작성** — `specs/2026-05-05-rename-concurrency-design.md` (965 줄)
  - 핵심 결정 19 건 통합 (R1.Q1~Q11, R2.D1~D5, R3.OQ-1~7 + G7)
  - 아키텍처: Path/Content 두 갈래 분리 (별도 락/큐/도메인)
  - 데이터모델: Postgres 5 테이블 + 1 view + Redis 키 구조
  - Phase 0~6 의존성 그래프 + 작업 분해
  - Profile 추상화: dev / team / enterprise 매트릭스
- [x] **Phase 0 구현 플랜 v1** — `specs/2026-05-05-phase0-implementation-plan.md` (2870 줄)
  - 9 task × 5~10 step (TDD bite-sized)
  - 산출 컴포넌트: Profile / Backend factory / Lock / EventBus(Redis) / KVStore / MetadataIndex(Redis hash) / Postgres+Alembic / TaskQueue(Asyncio + Arq) / Profile Status API / ontong CLI
- [ ] **Phase 0 구현 시작** — 사용자 실행 방식 선택 후 진행 (subagent / inline)
- [ ] **추가 요구 (R3 Q-NOTE)**: 그래프 연결 있는 문서 삭제 차단 → G7 으로 design doc 반영, Phase 1 작업 1-7 로 분해

---

## 2026-04-25 (채팅 잔버그 정리)

- [x] **wiki_write 응답 메시지 과거형 정정** (커밋 `6eba772`)
  - 문제: Q&A 답변 텍스트만으로 "생성했습니다 / 저장했습니다"라고 주장. 실제 저장은 `approval_request` 흐름으로만 일어남.
  - 수정: `backend/application/agent/rag_agent.py` write 분기 메시지를 "승인 대기"로 표현. `backend/ontong.md` §7에 거짓 저장 주장 금지 규칙 명문화.
- [x] **AI write 미리보기 탭 404** (커밋 `cf4ed53`)
  - 문제: `MarkdownEditor`가 `agentWrite` 미리보기 모드에서도 `fetchFile(filePath)`를 호출 → 디스크 파일 없음 → 404 → `if (error)` 가드가 `agentWrite` 렌더 분기보다 먼저 단락.
  - 수정: load `useEffect`에서 `agentWrite?.filePath === filePath`이면 즉시 early-return. deps에 `agentWrite` 추가해 승인 후 자동 재로드.
- [x] **충돌 페어 과다 표시** (커밋 `b5cd714`)
  - 문제: `_build_conflict_pairs`가 `unique_sources`(검색 결과 전 파일) 위에서 C(n,2) Cartesian product → 실 충돌이 아닌 공존 문서까지 페어화. 사용자 질의에서 3 pairs 출현.
  - 수정: `conflict_check` 스킬의 `conflicting_docs` 출력을 우선 사용 (≥2건일 때) → `unique_sources`는 폴백으로만. SSE 검증: 1 pair만 (균열관리 ±2℃ × 대안적접근법 ±5℃).
- [ ] **(WIP) 충돌 배너 본문 마크다운 렌더링** — 미커밋
  - 문제: `**bold**` / `\n\n` / `- bullet`이 raw 텍스트로 보임.
  - 수정: `frontend/src/components/AICopilot.tsx:~1265`의 `<p>{details}</p>`를 `<div>...<ReactMarkdown remarkPlugins={[remarkGfm]}>...</ReactMarkdown></div>`로 교체. 앰버 톤 prose 클래스 부착. `tsc --noEmit` 통과.
  - 다음 세션: 브라우저 검증 후 markdown hunk만 stash 추출 → 단일 커밋.

---

## 2026-04-17 (워크스페이스 세팅 + 메타데이터 검색 설계)

- [x] 위키 워크스페이스 초기 스캐폴딩 (README/TODO/CHANGES/HANDOFF/specs/log/archive)
- [x] 메타데이터/경로/폴더 검색 조건화 설계 스펙 작성 → `specs/2026-04-17-metadata-search-design.md`
- [x] **스펙 §10 4가지 결정 사항 사용자 확정** (전부 추천안)
  - 필터 시트: 우측 드로어
  - DSL: 완전 Boolean + 괄호
  - 프리셋: 개인만 (Phase 4)
  - 자연어 실패: 경고 칩 표시
- [x] Phase 1 (Backend 기반) 완료 — MS-1~MS-7, 65 테스트 통과
  - 산출물: `backend/application/agent/filter_compiler.py`, `filter_dsl.py`, `tests/test_filter_*.py`, `tests/test_wiki_search_filters.py`
  - `WikiSearchSkill.execute(filters=...)` + `to_tool_schema()` filters 확장
  - `BM25Index.search(filter_predicate=...)`
  - 상세: `log/step_metadata_search_phase1_summary.md`
- [x] Phase 2 (Indexer 보강) 완료 — MS-8~MS-10, 12 테스트 통과 (누적 77 테스트)
  - `DocumentMetadata`: `doc_type`, `authors[]` 필드 추가 + frontmatter 파싱/직렬화
  - `WikiIndexer`: `compute_effective_authors()`, `compute_mtime_epoch()` 헬퍼 + `_metadata_to_chroma`에서 Chroma 메타 주입 (`authors`는 `|@a|@b|` pipe-delimited)
  - `MetadataIndex`: `on_file_saved(authors, doc_type, mtime_epoch)` + `rebuild(extended=[...])` 확장 포맷 지원
  - `wiki_service.py`: 메인 저장 경로에서 새 필드 전달
  - `backend/cli/reindex_metadata.py`: 100K 규모 재인덱싱 스크립트 (`--force` / `--dry-run` / `--batch`)
  - 상세: `log/step_metadata_search_phase2_summary.md`
- [x] 테스트 위생 정리 — `sys.modules` 스텁 제거 (2026-04-18)
  - 문제: 9개 테스트 파일이 `chromadb`/`pydantic_ai`/`httpx`/`litellm`/`pydantic_settings` 등 **실제로 설치된 모듈**을 collection 시점에 `types.ModuleType(...)`로 빈 모듈 스텁화해 `sys.modules`에 주입. 이 테스트들이 먼저 실행되면 이후 테스트가 `from pydantic_ai import Agent`, `httpx.Response` 등을 못 찾아 9건의 collection ImportError 연쇄. 특히 `test_react_agent_filters.py`의 실 LLM 통합 테스트가 다른 테스트와 조합 시 `ImportError: cannot import name 'Agent' from 'pydantic_ai'`로 실패.
  - 수정: 모든 스텁은 대상 모듈이 미설치 상태를 가정하던 레거시 코드. 실제로는 전부 설치되어 있어 불필요 + 유해. `test_wiki_search_filters.py`, `test_indexer_metadata_fields.py`, `test_search_api_filters.py`, `test_ag23_skill_feedback.py`, `test_ag31_session_persistence.py`, `test_ag32_skill_permissions.py`, `test_ag41_react_loop.py`, `test_ag14_structured_summary.py`, `test_ag16_topic_shift.py`에서 스텁 블록 삭제. `test_ag14/16`의 경우 `backend.*` 하위 모듈 스텁(`backend.infrastructure.vectordb.chroma` 등)까지 실모듈로 대체돼 `test_p2b5_lineage` 등의 collection error도 함께 해소.
  - 결과: collection errors 9 → 0 (전역), `test_wiki_search_filters + test_pydantic_ai_migration::TestReactAgent` 조합 통과, 전체 리그레션 793 PASS / 22 FAIL (22건 전부 선재 존재 — 제품 코드 변화로 인한 assertion mismatch, 내 수정과 무관).
- [x] Phase 4 후속 — 에이전트(ReAct tool-call) 경로 통합 테스트 (2026-04-18)
  - 문제: Phase 4에서 rule-based NL extractor는 수동 QA로 검증했지만, `react_agent.py` WIKI_FILTER_HINT + `pydantic_tools.wiki_search(filters=)`는 live consumer가 없어 E2E 미검증이었음
  - 수정: `react_agent.py`에 `build_wiki_filter_hint(today)` 추가 — 시스템 프롬프트에 오늘 날짜 주입해 LLM이 상대 날짜 표현을 올바른 기준으로 해석하도록. (초기 테스트에서 LLM이 "지난 달"을 학습 시점 기준 2024-11로 매핑하던 hallucination 차단)
  - 신규: `tests/test_react_agent_filters.py` — 실 LLM 호출 3 테스트 (API key 있을 때만 실행)
    1. `ERP 폴더의…` → `filters.folders=['ERP']`
    2. `@동해가 작성한 sop…` → `filters.authors`에 `@동해` + `filters.types`에 `sop`
    3. `지난 달 회의록` → `types=['meeting']` + `mtime_from` 오늘 기준 전월 (날짜 하드코딩 금지)
  - 결과: 3/3 PASS (약 40s, Anthropic Sonnet 4 실호출)
- [x] Phase 4 (Agent 브릿지 + 프리셋) 완료 — MS-16~MS-20, 20 신규 NL extractor 테스트 (누적 105 테스트) + TS 0 에러 + SSE 수동 QA 5건 PASS
  - 백엔드: `backend/application/agent/nl_filter_extractor.py` (rule-based 한국어 NL → FilterSpec), `backend/core/schemas.py::AppliedFiltersEvent`, `rag_agent.py`에서 검색 직전 추출 + `applied_filters` SSE + `WikiSearchSkill(filters=)` 전달, `react_agent.py`에 `WIKI_FILTER_HINT` system prompt 주입, `pydantic_tools.py::wiki_search`에 `filters` 파라미터 노출
  - 프론트: `lib/api/sseClient.ts` `AppliedFiltersPayload` + dispatch, `AICopilot.tsx::AppliedFiltersRow` (emoji 칩 + "🔎 검색창에서 계속" → `openWithFilters()`), `lib/search/filterPresets.ts` (user-scoped localStorage, 상한 20), `FilterSheet.tsx`에 프리셋 섹션 + Escape 핸들러 + `aria-modal`, `SearchCommandPalette.tsx::EmptyResultSuggestions` (칩별 제거 / 기간 90일 확장 / 전체 제거)
  - 문서: `toClaude/wiki/demo_guide.md` 신규 (Phase 4 시나리오 8 + 트러블슈팅 5), `log/step_metadata_search_phase4_summary.md`
  - Korean particle strip 버그 수정: `@동해가` → `@동해` (pure hangul prefix + 조사 whitelist 검사)
- [x] 운영 재인덱싱 — 22 wiki 파일 → 140 chunks (13.8s). 버그 수정: `_rebuild_metadata_index`가 `wiki_dir` 인자를 받지 못해 `compute_mtime_epoch` 파일시스템 fallback이 동작하지 않던 문제(`mtime=0` 다수) → `abs_path=str(wiki_dir / wf.path)` 전달하도록 수정.
- [x] Phase 3 (Frontend UI) 완료 — MS-11~MS-15, 8 신규 백엔드 테스트 통과 (누적 85 테스트) + TS 0 에러
  - 백엔드: `backend/api/search.py`에 `filters` Query 파라미터 + `compile_to_chroma_where` 벡터 경로 + BM25 `_build_bm25_predicate` 클로저 (path_depth 런타임 주입) + `main.py`에서 `meta_index` 주입
  - `useSearchStore`: `FilterSpec`/`TagFilter` 타입 + filters 상태/액션(set/remove/clear/merge) + `filterSheetOpen` + `openWithFilters(patch)` + `buildFiltersQuery` JSON 인코딩
  - `SearchCommandPalette`: 칩 영역 렌더링(emoji prefix + 제외 tag는 destructive), trailing-space DSL 승격, "+ 필터" 버튼, 빈 결과 시 "필터 제거" CTA
  - `FilterSheet` (신규, 우측 드로어 fixed-position): 폴더/작성자/태그 include·exclude + AND·OR/타입/상태/mtime 프리셋/ACL/Boolean DSL, draft + 적용 패턴
  - `dslParser.ts` (신규): prefix 토큰 경량 파서 (`folder:`, `author:`, `tag:`, `-tag:`, `type:`, `status:`, `acl:`, `since:`/`until:`)
  - `TreeNav`: 폴더 우클릭 "이 폴더에서 검색" → `openWithFilters({ folders: [path] })`
  - `wiki/제품/K-Pro-양산이관계획.md` 데이터 수정 — frontmatter `tags`의 `2026`을 `"2026"`으로 quote (Pydantic 검증 실패로 인한 인덱서 블록 해소)
  - 상세: `log/step_metadata_search_phase3_summary.md`
