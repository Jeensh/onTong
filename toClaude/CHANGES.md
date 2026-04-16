# 변경/추가 요청

> 세션 사이에 요구사항이 바뀌거나 추가되면 여기에 메모.
> Claude는 매 세션 시작 시 이 파일의 `[ ]` 항목을 확인하고 우선 처리.
> 처리 완료 시 `[x]`로 체크하고 TODO.md/master_plan.md에 반영.

---

## 2026-04-16 (Section 2 Modeling Engine — Phase 1a)

### Engine-First Architecture 리디자인 (10 tasks, 28 tests)
- [x] **E1a-MODELS** — ParametricSimResult, SimulationParam, SimulationOutput, AffectedProcessRef
- [x] **E1a-RESOLVER** — TermResolver (Korean alias 30개 + fuzzy 0.55 + LLM fallback)
- [x] **E1a-REGISTRY** — SimRegistry (9 SCM entities × calc functions, static _REGISTRY pattern)
- [x] **E1a-ENGINE** — SimulationEngine (param clamp + calculate + BFS impact tracing)
- [x] **E1a-API** — Engine API (/engine/query, /simulate, /params/{id}, /status)
- [x] **E1a-SEED** — Seed enhancement (sim_entities count in response)
- [x] **E1a-CLIENT** — Frontend API client (4 functions + 6 TypeScript interfaces)
- [x] **E1a-ANALYSIS** — AnalysisConsole.tsx (자연어 입력 + 예시 질의 + 결과 표시)
- [x] **E1a-SIM** — SimulationPanel.tsx (엔티티 드롭다운 + 파라미터 슬라이더 + before/after)
- [x] **E1a-SIDEBAR** — ModelingSection.tsx (MAIN_NAV/SETTINGS_NAV 분리, 기본탭=analysis)
- [x] **E1a-FIX** — Division-by-zero guard + hardcoded condition fix (코드 리뷰 반영)

---

## 2026-04-12 (Section 2 Modeling MVP — Full Implementation)

### Section 2 Modeling MVP 완료 (18 tasks, 69 tests)
- [x] **S2-INFRA** — Neo4j Community docker service + Neo4jClient + config
- [x] **S2-PARSER** — CodeParser Protocol + tree-sitter Java parser (15 entity/relation types)
- [x] **S2-GRAPH** — Code graph writer (Neo4j MERGE queries)
- [x] **S2-GIT** — Git connector (clone/pull/diff/list_files)
- [x] **S2-ONTOLOGY** — SCOR+ISA-95 template (30+ nodes) + OntologyStore CRUD
- [x] **S2-MAPPING** — Mapping engine (YAML persistence, inheritance, gap detection)
- [x] **S2-QUERY** — Deterministic impact analysis (term lookup → BFS → reverse mapping)
- [x] **S2-CHANGE** — Change detector (diff → BROKEN/REVIEW/UNMAPPED classification)
- [x] **S2-APPROVAL** — Approval workflow (draft → review → confirmed)
- [x] **S2-API** — FastAPI endpoints (code, ontology, mapping, query, approval)
- [x] **S2-FE** — Frontend: API client + 5 view components + ModelingSection shell
- [x] **S2-E2E** — End-to-end integration test (7 tests)
- [x] **S2-REVIEW** — Final code review fixes (security guards, type fixes, frontend enum mismatch)

---

## 2026-04-12 (Lineage Bugfix — VersionTimeline + MetadataIndex)

### VersionTimeline 자동 갱신 수정
- [x] **P2-FIX1** — `VersionTimeline.tsx`에 `wiki:lineage-changed` 이벤트 리스너 추가. 폐기 되돌리기 후 "전체 버전 히스토리" 즉시 갱신
- [x] **P2-FIX2** — `wiki_service.py` `_clear_stale_lineage_refs()`에서 파일의 stale lineage 제거 후 MetadataIndex 미갱신 → version-chain API가 stale 체인 반환하던 버그 수정

---

## 2026-04-11 (Status Simplification + Lineage/Versioning Overhaul)

### Phase 1: Status Simplification
- [x] **SL-1** — review/미설정 제거, draft|approved|deprecated만 남김
- [x] **SL-2** — 새 문서 자동 draft, approved 수정 시 자동 draft 강등
- [x] **SL-3** — 프론트엔드 타입/드롭다운/뱃지 색상 업데이트

### Phase 2: Scoring Update
- [x] **SL-4** — review=70, unset=50 제거, draft 폴백 40

### Phase 3: MetadataIndex Enrichment
- [x] **SL-5** — status/supersedes/superseded_by 저장 + 역참조 인덱스

### Phase 4: Lineage Write-Time Validation
- [x] **SL-6** — 자기참조 차단, 사이클 감지, 경쟁 대체 경고

### Phase 5: Deprecation Side Effects
- [x] **SL-7** — 폐기 시 충돌 자동 해결, deprecated 제외, 0건 검색 폴백

### Phase 6: Version Chain API + Timeline UI
- [x] **SL-8** — version-chain API + VersionTimeline 프론트엔드 컴포넌트

### Phase 7: Reference Integrity + Deprecation UX
- [x] **SL-9** — 이동/삭제 시 참조 업데이트, TreeNav deprecated 표시, statuses API

### Phase 8: Metadata Inheritance + Bulk Status
- [x] **SL-10** — predecessor-context API, bulk-status API

---

## 2026-04-11 (UI/UX Overhaul — Content-First Layout)

### Collapsible Side Panels
- [x] **UX-1 TreeNav 접기** — react-resizable-panels collapsible prop, Cmd+B 단축키, 접힌 상태에서 아이콘 스트립 표시, localStorage 상태 유지
- [x] **UX-2 AICopilot 접기** — 동일 패턴, Cmd+J 단축키

### AI Copilot Popout
- [x] **UX-6 AI 팝아웃** — AICopilot을 별도 floating window로 분리 가능. 드래그 이동 + 리사이즈. Cmd+J로 토글. 패널 복귀(dock back) 지원. `page.tsx`

### Unified Document Info Bar
- [x] **UX-3 DocumentInfoBar** — 32px 단일 행에 status badge, domain/process, confidence pill, stale dot, 연결 문서 수, feedback 아이콘 버튼, drawer 토글
- [x] **UX-4 DocumentInfoDrawer** — 3탭(메타데이터/신뢰도/연결 문서) overlay drawer, Cmd+I 토글, Escape/외부 클릭으로 닫기
- [x] **UX-5 MarkdownEditor 리팩토링** — MetadataTagBar + TrustBanner + LinkedDocsPanel 3개 스택 → DocumentInfoBar + DocumentInfoDrawer로 교체. 기존 기능 100% 보존

---

## 2026-04-11 (세션 42 — User-Driven Self-Healing Phase C+D)

### Phase D — Knowledge Graph Unification
- [x] **PD-1 Relationship 모델** — source, target, rel_type, strength, created_by, metadata. GraphResult/GraphStats 모델 추가
- [x] **PD-2 GraphStore** — InMemoryGraphStore + RedisGraphStore. BFS get_graph(depth), stats, upsert 중복 제거, remove_all 양방향 정리
- [x] **PD-3 GraphBuilder** — metadata.related → "related", supersedes → "supersedes", ConflictStore → "conflicts" (resolved 제외). rebuild_all + rebuild_file (incremental)
- [x] **PD-4 Graph API** — GET /api/graph/{path}?depth=1&rel_type=, GET /api/graph/stats. main.py에서 startup 시 graph rebuild, tree_change 이벤트 시 incremental rebuild
- [x] **PD-5 테스트** — test_phase_d_knowledge_graph.py (22 tests: Model 3, Store 10, Builder 7, Models 2)

---

## 2026-04-11 (세션 42 — User-Driven Self-Healing Phase C: Score Integration)

### Phase C — Score Integration
- [x] **PC-1 가중치 재조정** — freshness 30→25, backlinks 15→10, owner_activity 15→10, user_feedback(신규) 15. 합계 100 유지
- [x] **PC-2 _score_user_feedback** — verified/(verified+needs_update) × 100. 피드백 없으면 50 (중립). compute_confidence에 feedback_verified, feedback_needs_update 파라미터 추가
- [x] **PC-3 ConfidenceService 피드백 연동** — set_feedback_tracker(), _get_feedback_counts(). main.py에서 feedback_tracker를 confidence_svc보다 먼저 생성하도록 순서 수정
- [x] **PC-4 "확인했음" → freshness 갱신** — POST /api/wiki/feedback/{path} action=verified 시 문서 frontmatter의 updated/updated_by 자동 갱신. 내용 변경 없이 stale 해제
- [x] **PC-5 테스트** — test_phase_c_score_integration.py (20 tests: WeightConfig 3, ScoreUserFeedback 7, ComputeConfidence 5, ServiceFeedback 3, FreshnessRefresh 2)

---

## 2026-04-11 (세션 41 — User-Driven Self-Healing Phase A+B)

### Phase B — User Feedback Loop
- [x] **PB-1 FeedbackTracker** — InMemory + Redis 이중 구현. verified/needs_update/thumbs_up/thumbs_down 4종 액션. FeedbackSummary 모델 (카운트 + last_verified_at/by)
- [x] **PB-2 Feedback API** — POST/GET /api/wiki/feedback/{path:path}. 피드백 기록 시 confidence 캐시 자동 무효화. main.py에 create_feedback_tracker() 와이어링
- [x] **PB-3 TrustBanner 피드백 버튼** — "확인했음" (초록) / "수정 필요" (주황) 버튼. 피드백 카운트 + 마지막 확인자/시간 표시. 피드백 후 신뢰도 점수 자동 리프레시
- [x] **PB-4 AICopilot 소스 thumbs** — 소스 카드 옆 ThumbsUp/ThumbsDown 아이콘. 클릭 시 thumbs_up/thumbs_down 피드백 전송
- [x] **PB-5 테스트** — test_phase_b_feedback.py (12 tests: InMemoryStore 5, Tracker 5, Model 2)

---

## 2026-04-11 (세션 41 — User-Driven Self-Healing Phase A: Foundation Fixes)

### Phase A — 기반 수리
- [x] **PA-1 MetadataIndex 확장** — on_file_saved()에 updated/updated_by/created_by/related 파라미터 추가. rebuild()에 extended kwarg 추가. wiki_service, main.py, metadata.py의 모든 호출부 업데이트
- [x] **PA-2 _get_backlink_count 버그 수정** — 루프 본문이 비어 항상 0 반환하던 버그. related 필드에서 현재 문서를 참조하는 다른 문서를 카운트하도록 수정
- [x] **PA-3 _is_owner_active 버그 수정** — 루프 본문이 비어 항상 False 반환하던 버그. updated_by 매칭 + updated 타임스탬프 90일 체크 로직 구현. _parse_date() 유틸 추가
- [x] **PA-4 프론트엔드 사용자 ID 연결** — currentUser.ts 싱글톤, AuthContext에서 setCurrentUser 호출, lockManager/MarkdownEditor에서 랜덤 SESSION_USER 제거 → getCurrentUserName() 사용. GET /api/auth/me 엔드포인트 추가
- [x] **PA-5 테스트** — test_phase_a_confidence_signals.py (16 tests: MetadataIndex 확장 4, Backlink 4, Owner Activity 5, ParseDate 3)

---

## 2026-04-11 (세션 40 — Trust System Phase 4: Smart Conflict Resolution)

### Phase 4 — Smart Conflict Resolution
- [x] **P4-1 TypedConflict + ConflictAnalysis 모델** — `schemas.py`에 TypedConflict, `models.py`에 ConflictAnalysis LLM 출력 모델 추가
- [x] **P4-2 analyze_pair() + StoredConflict 확장** — ConflictCheckSkill에 LLM 기반 페어 분석 static method 추가. StoredConflict에 conflict_type/severity/summary_ko/claim_a/claim_b/suggested_resolution/resolution_detail/analyzed_at/resolved/resolved_by/resolved_action 필드 확장. conflict_analyze_pair.md 프롬프트 생성
- [x] **P4-3 해결 액션 API** — POST /resolve (dismiss/version_chain/scope_clarify/merge), GET /typed (분석된 충돌 목록), POST /analyze-pair (수동 AI 분석). ConflictStore에 update_analysis/resolve_pair 메서드 추가 (InMemory + Redis). ConflictDetectionService에 get_typed_pairs/resolve_pair/trigger_deep_analysis/update_analysis 추가
- [x] **P4-4 ConflictDashboard 유형 뱃지 + 해결 UI** — 대시보드 전면 리라이트. 제목 "관련 문서 관리"로 변경. 유형 뱃지(사실 불일치/범위 중복/시간 차이/무관), 심각도 dot, AI 분석 버튼, 원클릭 해결 버튼 4종, claim 인용 표시
- [x] **P4-5 관리 다이제스트** — DocumentDigestService (오래됨/신뢰도낮음/미해결충돌 그룹핑), GET /api/wiki/digest 엔드포인트, MaintenanceDigest.tsx 컴포넌트, 사이드바 설정에 "관리가 필요한 문서" 메뉴 추가
- [x] **P4-6 테스트 + 문서** — test_phase4_smart_conflict.py 13 tests all pass

### 스케일 대비 + UI 자기설명 개선
- [x] **API 페이지네이션** — GET /conflict/typed에 limit/offset 추가 (기본 50, 최대 200). GET /wiki/digest에 limit/offset 추가 (섹션별 적용)
- [x] **파일 스캔 안전 캡** — digest.py MAX_FILES_SCAN=100,000
- [x] **ConflictDashboard UX** — 사용 가이드 토글 (유형별 의미, 해결 액션 설명), 미분석 뱃지에 안내 문구, 타입 뱃지 툴팁에 설명 추가, 클라이언트 페이지네이션 (20건/페이지)
- [x] **MaintenanceDigest UX** — 각 섹션별 설명+조치방법 안내, 안내 배너 추가, 접기/펼치기 (기본 5건), 빈 상태 가이드 개선

### 100K+ 문서 스케일 대비 (2차)
- [x] **ConfidenceCache LRU** — OrderedDict 기반 LRU + TTL 이중 캐시 (max_size=5,000). 100K 문서 중 hot working set만 캐싱, 메모리 누수 방지
- [x] **Digest 결과 캐싱** — DigestResult TTL 5분 캐시 + tree_change 이벤트로 자동 무효화
- [x] **Digest async 스캔** — asyncio.to_thread()로 rglob 이동, 이벤트 루프 블로킹 방지. frontmatter 1KB만 읽기
- [x] **EventBus 콜백** — event_bus.on("tree_change", callback) 패턴 추가. confidence + digest 캐시 자동 무효화
- [x] **search_path 최적화** — full tree build 대신 list_file_paths() 사용 + early termination (limit 도달 시 즉시 중단)
- [x] **reindex-pending 배치 제한** — REINDEX_BATCH_LIMIT=100, 나머지는 remaining 카운트로 반환
- [x] **Storage I/O 비동기화** — list_tree(), list_subtree() 모두 asyncio.to_thread()로 이동. 100K 파일 디렉토리에서 이벤트 루프 블로킹 방지
- [x] **충돌 해결 상태 보존 버그 수정** — replace_for_file()이 재인덱싱 시 resolved/analyzed 상태를 덮어쓰던 버그. 유사도 변동 < 0.05이면 상태 보존, > 0.05이면 리셋 (내용 변경 시 재감지). InMemory + Redis 양쪽 수정. 테스트 4건 추가 (총 17건)

---

## 2026-04-11 (세션 39 — Trust System Phase 3: 읽기 시 맥락)

### Trust System Phase 3 — Read-Time Trust Context
- [x] **P3-1 CitationTracker** — AI 답변 소스 인용 카운트 (Redis/InMemory). `rag_agent.py`에서 소스 emit 후 자동 기록. 파일: `trust/citation_tracker.py`, `rag_agent.py`
- [x] **P3-2 ConfidenceResult 확장** — `citation_count` (인용 횟수) + `newer_alternatives` (신뢰도 < 40인 문서에 대한 더 높은 신뢰도 대안 3건). `NewerAlternative` 모델 추가. 파일: `trust/confidence.py`, `trust/confidence_service.py`
- [x] **P3-3 TrustBanner 컴포넌트** — 에디터 상단에 신뢰도 pill(팝오버), 오래된 문서 경고, 최신 대안 링크, 인용 카운트 통합 표시. MarkdownEditor에서 기존 pill 코드 제거 후 TrustBanner로 대체. 파일: `TrustBanner.tsx`, `MarkdownEditor.tsx`
- [x] **P3-4 와이어링** — main.py에서 CitationTracker 생성 → ConfidenceService + RAGAgent에 주입. 파일: `main.py`
- [x] **P3-5 테스트** — 14개 단위 테스트 (CitationTracker, ConfidenceResult 확장, NewerAlternative, 직렬화). 파일: `tests/test_phase3_trust.py`

---

## 2026-04-11 (세션 39 — 스코어링 중앙화 + UX 개선)

### 스코어링 설정 중앙화
- [x] **S-1 scoring_config.py** — 모든 점수 가중치/임계값/공식을 `ScoringConfig` 데이터클래스 + `explain()` 메서드로 단일 파일에 집중. 파일: `trust/scoring_config.py`
- [x] **S-2 confidence.py 리팩터** — 하드코딩 가중치(30/25/15/15/15)와 tier 임계값(70/40) → `SCORING.confidence` 참조로 교체. 파일: `trust/confidence.py`
- [x] **S-3 search.py 리팩터** — 관련 문서 min_similarity 0.5→0.7(SCORING.related.min_similarity), composite 가중치 하드코딩 → `SCORING.related.w_similarity/w_confidence`. 파일: `api/search.py`
- [x] **S-4 rag_agent.py 리팩터** — RAG boost floor 0.7 → `SCORING.rag_boost.floor`. 파일: `rag_agent.py`
- [x] **S-5 conflict_service.py 리팩터** — SIMILARITY_THRESHOLD/HNSW_N_RESULTS/MAX_RESULTS → `SCORING.conflict.*`. 파일: `conflict_service.py`
- [x] **S-6 wiki_service.py 리팩터** — auto_suggest 임계값 0.7 / top 3 → `SCORING.related.auto_suggest_similarity/auto_suggest_max`. 파일: `wiki_service.py`

### 관련 문서 UX 개선
- [x] **U-1 기본 2건 표시 + 더 보기** — LinkedDocsPanel에서 기본 2건만 보여주고 나머지는 "더 보기 (+N)" 토글. 파일: `LinkedDocsPanel.tsx`
- [x] **U-2 결과 0건일 때 섹션 숨김** — 이미 구현 완료 (relatedDocs.length > 0 조건)

### 스코어링 투명성 API
- [x] **E-1 GET /api/wiki/scoring-config** — `SCORING.explain()` 반환. 모든 가중치/임계값/공식을 한국어로 설명. 파일: `api/wiki.py`

### 사용자 투명성 + 관리자 대시보드
- [x] **V-1 신뢰도 pill 팝오버** — 에디터 상단 pill 클릭 시 5개 시그널 상세(점수 바 + 가중치 + 설명) 팝오버. 클릭 외부 닫기. 파일: `MarkdownEditor.tsx`
- [x] **V-2 ScoringDashboard 관리자 페이지** — 설정 사이드바에 "신뢰도 설정" 항목 추가. scoring-config API 호출하여 모든 가중치/임계값/공식을 카드 형태로 표시. 파일: `ScoringDashboard.tsx`, `TreeNav.tsx`, `FileRouter.tsx`, `workspace.ts`, `useWorkspaceStore.ts`
- [x] **V-3 AI소스 뱃지 툴팁 강화** — 호버 시 신뢰도 + 해석 메시지("높음 — 신뢰할 수 있는 문서" 등) 표시. 줄바꿈으로 가독성 개선. 파일: `AICopilot.tsx`

---

## 2026-04-11 (세션 38 — Trust System Phase 2: Write-Time Related Document Nudge)

### Trust System Phase 2 — 작성 시 넛지
- [x] **T2-1 관련 문서 API** — `GET /api/search/related?path=X&limit=5`. HNSW 후보 발견 → 파일 평균 임베딩 cosine 비교 → 신뢰도+메타데이터 보강. 정렬: `0.6*sim + 0.4*(conf/100)`. 시스템 경로 제외. 파일: `api/search.py`, `schemas.py`
- [x] **T2-2 LinkedDocsPanel 확장** — "참고할 만한 문서" 섹션 추가 (Sparkles 아이콘 + 신뢰도 dot + 유사도%). 파일 열 때 + 500ms 디바운스 fetch. 파일: `LinkedDocsPanel.tsx`
- [x] **T2-3 저장 시 자동 related** — `_bg_index()` 완료 후 `_auto_suggest_related()` 호출. `related` 비어있을 때만, similarity>0.7 상위 3건 frontmatter에 자동 추가. 파일: `wiki_service.py`
- [x] **T2-4 와이어링+테스트** — `main.py`에서 chroma/confidence_svc → wiki_service, search_api에 주입. 12개 테스트 통과. 파일: `main.py`, `tests/test_related_search.py`

---

## 2026-04-09 (세션 38 — Trust System Phase 1: Document Confidence Score)

### Trust System Phase 1 — 문서 신뢰도 점수
- [x] **T1-1 ConfidenceScorer 엔진** — 5개 시그널(최신성 30, 상태 25, 메타완성도 15, 백링크 15, 소유자활동 15) 가중 합산 → 0-100 점수 + tier(high/medium/low) + stale 플래그. 파일: `trust/confidence.py`, `trust/confidence_cache.py`, `trust/confidence_service.py`, `trust/__init__.py`
- [x] **T1-2 Confidence API** — `GET /api/wiki/confidence/{path}`, `GET /api/wiki/confidence-batch?paths=`. 파일: `api/wiki.py`
- [x] **T1-3 RAG 랭킹 통합** — `_build_sources()`에 confidence_service 전달, 신뢰도 기반 mild boost (`0.7 + 0.3 * conf/100`), `SourceRef`에 `confidence_score` + `confidence_tier` 필드 추가. 파일: `rag_agent.py`, `schemas.py`
- [x] **T1-4 프론트엔드 뱃지** — AICopilot 소스에 초록/노랑/회색 신뢰도 dot + 툴팁, MarkdownEditor 헤더에 신뢰도 pill(점수+메시지). 파일: `AICopilot.tsx`, `MarkdownEditor.tsx`, `sseClient.ts`
- [x] **T1-5 와이어링+테스트** — main.py에서 ConfidenceService 생성→wiki_api, RAGAgent에 주입. 28개 단위 테스트 통과. 파일: `main.py`, `tests/test_confidence.py`

---

## 2026-04-09 (세션 37 — Path-Aware RAG + 대화형 경로 명확화 + 버그 수정)

### 버그 수정
- [x] **스킬 무시 버튼 무효** — 프론트에서 "무시" 클릭해도 백엔드가 독자적으로 auto-match → 적용됨. `ChatRequest.dismissed_skills` 필드 추가, 프론트에서 무시 목록 전송, 백엔드에서 해당 스킬 건너뜀. 파일: `schemas.py`, `api/agent.py`, `sseClient.ts`, `AICopilot.tsx`
- [x] **사이드바 스킬 목록 미표시** — FastAPI 307 trailing slash redirect ↔ Next.js 308 strip slash가 무한 리다이렉트 루프 생성. `redirect_slashes=False` + 라우트 `"/"` → `""` 수정. 파일: `main.py`, `api/skill.py`
- [x] **보안-점검-도우미 frontmatter 누락** — `type: skill`, `trigger` 필드 없어서 스킬 로더가 무시. frontmatter 보완. 파일: `wiki/_skills/보안/보안-점검-도우미.md`
- [x] **채팅 첫 응답 지연 체감** — `main_router.classify()` LLM 호출 동안 UI 무반응. classify 시작 전 즉시 `thinking_step(routing, start)` 이벤트 발행. 파일: `api/agent.py`

### Part 2 — 충돌 & Lineage
- [x] **2A 사이클 감지** — `_resolve_superseded_chain`에 `visited` set 추가, 재방문 시 break + warning. 파일: `rag_agent.py`
- [x] **2C deprecated 뱃지** — `SourceRef.superseded_by` 필드 추가, deprecated 소스도 검색 결과에 포함, FE에 "폐기됨" 뱃지 + "→ 새 버전" 링크. 파일: `schemas.py`, `rag_agent.py`, `sseClient.ts`, `AICopilot.tsx`
- [x] **2B 폐기 되돌리기** — `POST /api/conflict/undeprecate` API + ConflictDashboard "되돌리기" 버튼. 파일: `api/conflict.py`, `ConflictDashboard.tsx`
- [x] **2D 쌍 그룹핑** — 같은 file_a를 공유하는 충돌 쌍을 그룹 렌더링 (주 문서 + 충돌 문서 목록). 파일: `ConflictDashboard.tsx`
- [x] **충돌 스캔 결과 영속화** — `.env`에 `REDIS_URL` 추가 → RedisConflictStore 활성화. 서버 재시작해도 스캔 결과 유지. 기본 threshold 0.95 → 0.85로 변경 (`ONTONG_CONFLICT_THRESHOLD` 환경변수). 파일: `.env`, `conflict_service.py`

### Path-Aware RAG

### Phase 1 — 인덱싱 변경 (L1 + L2A)
- [x] **P1-1~3** — `_build_path_prefix()` + 모든 청크에 `[분류: X > Y] [문서: Z]` 프리픽스 + `path_depth_1/2/stem` 메타데이터. 재인덱싱 완료 (172 chunks).

### Phase 2 — 쿼리 경로 필터링 (L2B + L2C)
- [x] **P2-1~2** — `extract_path_filter()` + wiki_search 스킬 `path_preference` 파라미터 통합

### Phase 3 — 경로 분산 감지 + 대화형 명확화 (L3)
- [x] **P3-1~4** — `_detect_path_ambiguity()` (min_paths=3, dominance=0.70), `ClarificationRequestEvent` 발행, `clarification_response_id` 활성화, 세션 `path_preferences` 누적

### Phase 4 — 경로 부스트 리랭크 (L4)
- [x] **P4-1~2** — `_path_boost_rerank()` (recency decay, weight=0.08) + _handle_qa 통합

### 평가 + 문서
- [x] **E1** — 기존 RAG 12쿼리 회귀 테스트 통과 (hit@5=1.0, MRR=1.0)
- [x] **E2** — 브라우저 E2E 검증 완료
- [x] **DOC** — CHANGES/TODO/demo_guide 동기화

---

## 2026-04-07 ~ 2026-04-08 (세션 36 — 태그 자동화 고도화 + RAG tag boost)

### Phase A — 추천 정확도 + 중복 방지
- [x] **A1 프롬프트 외부화** — `auto_tag_pass1.md`, `auto_tag_pass2.md`, `auto_tag.md` (fallback)
- [x] **A2 컨텍스트 확장** — filename/parent_dir, neighbor tags/domains, related docs tags 신호 주입
- [x] **A3 2-pass 계층 추론** — Pass1: domain/process → Pass2: tags scoped to domain (domain_tags top 50 주입)
- [x] **A4 Few-shot 예시** — `auto_tag_examples.json` 7개 도메인 예시, Pass2 프롬프트에 동적 주입
- [x] **A5 Always-normalize + 스키마 확장** — 모든 추천 태그를 `tag_registry.find_similar` 3층 통과
  (auto-replace<0.35 / LLM-confirm<0.55 / soft-alternative<0.65). `TagAlternative`, `tag_replaced`, `tag_alternatives` 필드 추가
- [x] **A6 Soft UI** — AutoTagButton에 alternatives 칩 표시, 클릭 시 치환 수락, 정규화 toast
- [x] **A7 Confidence 자동 보정** — alternatives 수 / 재사용 비율 / neighbor 도메인 일치도 반영
- [x] **A8 회귀 테스트** — `tests/test_auto_tag_quality.py`, 27개 샘플에 대해 **domain 정확도 100%, 평균 conf 0.85, 22건 자동 치환** 베이스라인 기록

### Phase B — Query-time tag boost + 평가
- [x] **B1 extract_query_tags** — `filter_extractor.py`에 쿼리→기존 태그 의미 매칭 (거리 0.55)
- [x] **B2 RAG boost rerank** — `RAGAgent._tag_boost_rerank`로 태그 교집합만큼 cosine 거리 감산, `ONTONG_TAG_BOOST_WEIGHT` 환경변수
- [x] **B3 Tag-only fallback** — domain/process 필터 0건 시 태그 교집합 필터로 재시도 → 그것도 0이면 무필터
- [x] **B4 평가 스크립트** — `tests/test_rag_tag_boost.py` + `rag_eval_queries.json` (12 쿼리). **Baseline hit@5=1.0, MRR=1.0** (천장 효과, 회귀 없음)

---

## 2026-04-05 (세션 33 — Domain-Process 계층 구조 + 데이터 클린업)

- [x] **템플릿 구조 변경** — flat `{domains[], processes[]}` → hierarchical `{domain_processes: {domain: [procs]}}`
- [x] **백엔드 CRUD API** — domain/process 계층 CRUD (`POST/DELETE /templates/domain`, `/domain/{d}/process`)
- [x] **레거시 마이그레이션** — 기존 flat 템플릿 자동 감지 → hierarchical 변환
- [x] **프론트엔드 cascade UI** — domain 선택 → 해당 process만 표시, domain 변경 시 process 리셋
- [x] **위키 데이터 클린업** — 기존 20개 문서 삭제, 7개 도메인별 21개 샘플 문서 생성
- [x] **filter_extractor 동적 키워드** — 하드코딩 → templates.json에서 동적 로드 (lazy import로 테스트 호환)
- [x] **metadata_service 프롬프트** — 도메인/프로세스 목록을 templates에서 동적 생성
- [x] **AutoTagButton confidence** — 신뢰도 뱃지(색상 3단계), domain/process 개별 수락, 저신뢰 태그 흐림 처리
- [x] **메타데이터 validation** — DomainSelect 템플릿 외 값 노란 경고, wiki_service 저장 시 warning 로그
- [x] **related 문서 편집 UI** — MetadataTagBar에 관련 문서 TagInput(파일 경로 자동완성) + lineage 읽기전용 표시
- [x] **Bulk auto-tag API** — `POST /api/metadata/suggest-bulk` (배치 처리, apply 옵션)
- [x] **UntaggedDashboard 업그레이드** — bulk API 연동, 미리보기/전체적용, confidence 표시, 진행률 바
- [x] **Materialized metadata index** — `.ontong/metadata_index.json` 증분 업데이트 (save/delete/reindex)
- [x] **Lazy tag search API** — `GET /api/metadata/tags/search?q=` (debounce prefix match)
- [x] **Lazy path search API** — `GET /api/wiki/search-path?q=` (related 문서 자동완성)
- [x] **MetadataTagBar lazy refactor** — `fetchAllTags()` + `fetchTree()` 제거 → templates O(1) + debounce search
- [x] **UntaggedDashboard pagination** — offset/limit 페이지네이션 + `/api/metadata/stats` 인덱스 기반
- [x] **TagInput onSearch prop** — 정적 suggestions + async debounce search 이중 지원
- [x] **DomainProcessPicker** — Domain/Process 드롭다운 2개 → 트리형 통합 셀렉터 1개 (도메인 펼치면 하위 프로세스 lazy 표시)
- [x] **MetadataTagBar 복원** — DomainProcessPicker 적용 취소, 기존 DomainSelect 2개(Domain/Process) 방식으로 복원
- [x] **MetadataTemplateEditor 트리 구조** — Domain/Process/Tags 3섹션 → Domain-Process 트리(도메인 클릭→프로세스→파일) + Tags 2섹션으로 개편. lazy loading 적용.
- [x] **사이드바 태그 브라우저 트리 구조** — Domain/Process/Tags 3섹션 → Domain→Process→Files 트리 + Tags 2섹션. Process lazy loading 적용.

## 2026-04-06 (세션 34 — 10만 문서 스케일 성능 최적화)

- [x] **역인덱스 추가** — metadata_index에 `domain_files`, `process_files`, `tag_files` 역인덱스. rebuild/save/delete 모두 증분 유지.
- [x] **`/files-by-tag` O(n)→O(1)** — 인덱스 기반 조회 + pagination(`offset`, `limit`) 지원. 전체 스캔 제거.
- [x] **`/tags/search` pagination** — `{tags: [{name, count}], total}` 형식으로 변경, offset/limit 지원.
- [x] **`/suggest-bulk` 병렬화** — `asyncio.gather` + `Semaphore(5)` 동시 LLM 호출 (순차→병렬).
- [x] **사이드바 파일 목록 limit** — 프로세스/태그 하위 파일 20건 단위 + "더보기" 버튼.
- [x] **사이드바 태그 뱃지 limit+검색** — 상위 30개 표시 + 검색 input + 이전/다음 페이지네이션.
- [x] **UntaggedDashboard bulk 단순화** — 프론트에서 3건 청크 분할 제거, 백엔드 병렬에 위임.
- [x] **Layer 1: 프롬프트 태그 주입** — LLM suggest 시 기존 태그 상위 100개를 프롬프트에 주입, 재사용 강제 지시
- [x] **Layer 2: 임베딩+LLM 태그 정규화** — ChromaDB tag_registry 컬렉션, 유사도 <0.08 자동치환, 0.08~0.20 LLM 확인
- [x] **Tag Registry** — `tag_registry.py` NEW, ChromaDB 기반 의미적 태그 저장소, 서버 시작 시 인덱스에서 벌크 동기화
- [x] **Smart Friction** — TagInput에서 새 태그 입력 시 ��사 태그 확인 → "기존 태그를 사용하시겠습니까?" 프롬프트
- [x] **태그 건수 자동완성** — TagInput `onSearchWithCount` prop, 드롭다운에 건수 표시 (수렴 유도)
- [x] **유사 태그 그룹 대시보드** — 관리 페이지에서 "분석 실행" → 유사 태그 그룹 표시 + 클릭 병합
- [x] **고아 태그 표시** — 1건 이하 사용 태그 목록 표시
- [x] **태그 병합 API** — `POST /tags/merge?source=&target=` 전체 문서 일괄 업데이트 + 레지스트리 정리
- [x] **임베딩 임계값 교정** — OpenAI text-embedding-3-small 단문 한국어 실측 기반 임계값 대폭 상향 (auto-replace 0.08→0.35, LLM confirm 0.20→0.55, API filter 0.25→0.60, groups 0.20→0.55). 유사 태그 그룹 4건 정상 검출 확인.

## 2026-04-07 (세션 35 — Smart Friction 레이턴시 최적화)

- [x] **Smart Friction 체감 지연 제거** — `/tags/similar`가 OpenAI 임베딩 왕복으로 560ms 소요하여 Enter 누를 때 답답함. TagInput에서 디바운스된 search 콜백과 함께 `onCheckSimilar`를 백그라운드로 선제 호출하여 캐시에 저장. 사용자가 드롭다운 훑어보는 동안 워밍되어 Enter 시점엔 캐시 히트 → 체감 0ms.
- [x] **similarCache LRU 50개 제한** — `Map` 삽입 순서 특성으로 가벼운 LRU 구현(재삽입으로 recency 갱신, 초과 시 oldest eviction). 장시간 세션에서의 메모리 누수 방지.

---

## 2026-04-05 (세션 32 — 사용자별 AI 페르소나 커스터마이징)

- [x] **Persona API** — `POST /api/persona/ensure` (템플릿 자동 생성), `POST /api/persona/invalidate`
- [x] **시스템 프롬프트 병합** — `build_system_prompt(username, storage)`, 60초 TTL 캐시, Q&A+스킬 경로 적용
- [x] **AgentContext.username** — 인증된 사용자명 전달
- [x] **자유 마크다운 페르소나** — Settings 버튼 → 워크스페이스에서 ontong.local.md 탭 열기 (Tiptap 에디터)
- [x] **가이드 템플릿** — 처음 열 때 "나에 대해/응답 스타일/참고 사항" 가이드 자동 생성
- [x] **자동 캐시 무효화** — wiki save 시 persona 파일이면 캐시 클리어
- [x] **빈 템플릿 감지** — 가이드 주석만 있는 상태(미작성)는 프롬프트에 주입 안 함

---

## 2026-04-05 (세션 31b — 스킬 UX 개선: 사용자 교육 & 가이드)

- [x] **스킬 소개 배너** — TreeNav 스킬 섹션 상단에 일회성 안내 ("스킬이란?"), localStorage 기반 닫기
- [x] **빈 상태 → 액션 유도** — 내 스킬/공용 스킬 빈 상태에 아이콘+설명+CTA ("첫 번째 스킬 만들기")
- [x] **스킬 피커 교육** — 채팅 피커 헤더 서브텍스트, 빈 상태 안내, 자동제안 설명 추가
- [x] **스킬 생성 가이드** — 다이얼로그 헤더 개선, 트리거 힌트, 6-Layer 라벨 인라인 설명
- [x] **탭 툴팁 개선** — "스킬 — AI 응답을 커스터마이징하는 템플릿"

---

## 2026-04-05 (세션 31 — 훅 시스템 + Completion Protocol + 스킬 고도화)

- [x] **AG-3-3: PreSkill/PostSkill 훅 시스템** — SkillHook protocol, HookRegistry, PreHookResult, QuerySanitizeHook(pre), DeprecatedDocHook(post), main.py 등록
- [x] **CompletionStatus 확장** — SkillResult에 DONE/DONE_WITH_CONCERNS/BLOCKED/NEEDS_CONTEXT enum 추가, 자동 상태 추론
- [x] **AG-4-3: 사용자 확인 루프** — ClarificationRequestEvent SSE, ChatRequest.clarification_response_id, AgentContext.emit_clarification()
- [x] **Per-Skill allowed-tools** — SkillMeta/SkillCreateRequest에 allowed_tools 필드, skill_loader YAML 파싱, context.py 우선순위 적용, skill_api 마크다운 템플릿
- [x] **스킬 크리에이터 UI 강화** — SkillCreateDialog에 allowed-tools 체크박스 UI, TypeScript 타입 동기화
- [x] **agent-architecture.md 업데이트** — 훅, CompletionStatus, Clarification, per-skill tools 문서화
- [x] **test_ag33_hooks.py** — 14 tests (CompletionStatus 5, HookRegistry 6, BuiltinHooks 3)

---

## 2026-04-05 (세션 30 — 고도화 완료 + 문서화 + Claude 전환)

- [x] **Claude API 키 설정** — `anthropic/claude-sonnet-4-20250514`로 모델 전환, .env gitignore 확인
- [x] **CORS 3001 포트 추가** — 프론트엔드 포트 변경(3001) 대응
- [x] **README.md 업데이트** — AI Copilot 섹션 v3 고도화 내용 반영, 구 Self-Reflective Pipeline 제거
- [x] **docs/agent-architecture.md 신규** — 에이전트 v3 아키텍처 기술 문서 (파이프라인, ReAct, 스킬, 권한, 세션, 프롬프트)
- [x] **demo_guide.md 업데이트** — AG-2~4 데모 시나리오 12개 + 트러블슈팅 추가
- [x] **테스트 격리 수정** — AG-3-1/3-2 pytest 크로스테스트 모듈 캐시 문제 해결 (importlib.reload)

---

## 2026-04-04 (세션 29 — 에이전트 고도화 착수)

- [x] **agent_bible(claw-code-parity) 분석** — 6개 영역 + 3개 심층 분석, 9개 분석 문서 작성
- [x] **99_adoption_plan.md v3 확정** — 전문가 리뷰 반영 (하이브리드 라우팅 삭제, topic_shift 추가, 훅 후퇴 등)
- [x] **TODO.md 에이전트 고도화 태스크 추가** — AG-1~4, 17 tasks
- [x] **.env LLM 모델 복원** — `gpt-4o-mini` → `gpt-4o` (API 키 권한 해결)
- [x] **AG-1-1: ontong.md 생성** — 에이전트 성격/규칙 정의 (`backend/ontong.md`)
- [x] **AG-1-2: 시스템 프롬프트 교체** — FINAL_ANSWER_SYSTEM_PROMPT → `get_system_prompt()` (ontong.md 로드)
- [x] **AG-1-3: 토큰 기반 히스토리** — `history[-6:]` → `build_history_window()` (4000 토큰 예산)
- [x] **AG-1-4: 구조화된 대화 요약** — 예산 초과 시 규칙 기반 요약 (Scope/Requests/Docs/Skills/Last response)
- [x] **AG-1-5: Continuation instruction** — ontong.md Context Awareness 강화 + 요약 프리픽스에 지시 내장
- [x] **AG-1-6: query_augment + topic_shift** — QueryAugmentResult 구조화 출력, 주제 전환 시 히스토리 미주입
- [x] **AG-1-7: 스킬 프롬프트 마크다운 분리** — 4개 스킬 프롬프트 .md 파일로 분리 + prompt_loader.py
- [x] **AG-1-8: Cognitive Reflect 제거** — 3단계 자기성찰 파이프라인 제거, LLM 1회 절약, 충돌 감지는 conflict_check 스킬로 전담
- [x] **AG-2-1: 스킬별 도구 풀 제한** — INTENT_ALLOWED_SKILLS 매핑 + run_skill() 차단 로직
- [x] **AG-2-2: 파이프라인 병렬화** — api/agent.py에서 routing+augment 병렬화 이미 구현, 추가 병렬화 여지 제한적
- [x] **AG-2-3: SkillResult feedback 필드** — `feedback`/`retry_hint` 필드 추가, wiki_search에서 deprecated 문서 필터 시 경고 반환, rag_agent에서 thinking_step으로 표시
- [x] **AG-3-1: 세션 JSONL 영속성** — 인메모리 → JSONL append 방식, 서버 재시작 후 대화 복원, `session_store.append_message()` API 추가, path traversal 방지
- [x] **AG-3-2: 스킬 권한 매핑** — `PermissionLevel` enum (READ/WRITE/EXECUTE), `SKILL_PERMISSIONS` 매핑, WRITE 스킬은 editor/admin 역할 필요, 권한 부족 시 retry_hint 반환
- [x] **AG-4-1: Q&A ReAct 자율 검색** — 검색 결과 품질 평가 후 자동 재검색 (최대 3턴), `SearchEvaluation` 모델, `qa_react.md` 프롬프트, 규칙 기반 fast-path (관련도 40%↑ → 즉시 답변)
- [x] **AG-4-2: 검색 자기 평가 + 재검색 전략** — qa_react.md에 충분성 체크리스트 + 5단계 재검색 전략(구체화→시간→동의어→상위개념→탐색) 보강
- [x] **.env 모델 변경** — `openai/gpt-4o-mini` → `anthropic/claude-sonnet-4-20250514` (Claude API 키 적용 완료)

---

## 2026-04-04 (세션 28 — 외부 접속 환경 구축 + 인프라 수정)

- [x] **외부 접속 환경 구축** — cloudflared → ngrok 고정 도메인(`architecturally-televisional-fumiko.ngrok-free.dev`) 전환
- [x] **SSE 스트리밍 프록시 추가** — `frontend/src/app/api/agent/chat/route.ts` (Next.js rewrite 버퍼링 우회)
- [x] **sseClient.ts 수정** — 외부 접속 시 Next.js API route 경유, localhost는 직접 백엔드 호출
- [x] **Next.js production 빌드 전환** — dev 모드 85개 청크 → prod 5개 번들 (외부 접속 속도 개선)
- [x] **.env LLM 모델 변경** — `gpt-4o` → `gpt-4o-mini` (API 키 권한 이슈)
- [x] **ChromaDB 강제 재인덱싱** — `force=true`로 해시 캐시 초기화 후 236 청크 인덱싱
- [ ] **ngrok 자동 시작 스크립트** — 매 세션마다 수동 실행 필요, 자동화 미구현

---

## 2026-04-01 (세션 27 — Phase 0 스캐폴딩 + 개발자 C 환경 구축)

- [x] **shared/contracts/ 생성** — `simulation.py` typed 계약 (DemandForecastParams, InventoryOptimizeParams, LeadTimeAnalysisParams, SimulationJob 등)
- [x] **shared/agent_framework/ 생성** — AgentPlugin Protocol re-export
- [x] **backend/simulation/ 스캐폴딩** — API 라우터, mock 서버(파라미터 기반), client Protocol, agent/visualization/storage 빈 모듈
- [x] **backend/modeling/ 스캐폴딩** — API 라우터(health), agent/ontology/code_analysis/mapping/simulation/data 빈 모듈
- [x] **main.py 라우터 등록** — modeling_api, simulation_api 등록 + MockModelingClient 초기화
- [x] **프론트엔드 Section 네비게이션** — SectionNav 상단 탭 (Wiki/Modeling/Simulation), useWorkspaceStore에 activeSection 상태 추가
- [x] **SimulationSection 3-pane 레이아웃** — 시나리오 목록(API 연동) + 대시보드 영역 + SimCopilot placeholder
- [x] **ModelingSection stub** — Phase 1 로드맵 카드 + ModelingCopilot placeholder
- [x] **개발자 C 가이드 문서** — `docs/section3-developer-guide.md` (실행법, 디렉토리, API 계약, mock 사용법, 규칙)
- [x] **전체 테스트 통과** — 177/177 pass + TypeScript 빌드 성공

---

## 2026-04-01 (세션 26 — 3-Section Platform 아키텍처 v2)

- [x] **3-Section 플랫폼 아키텍처 설계** — Wiki / Source-Domain Modeling / Simulation 3섹션 분리
- [x] **3관점 리뷰 수행** — Systems Architect, Developer C, Domain Expert 관점 검토 (26건 이슈 도출)
- [x] **리뷰 반영 아키텍처 v2 확정** — 시뮬레이션 2종 분리, SCOR+ISA-95, typed 계약, 비동기 job, 매핑 임계값 상향
- [x] **아키텍처 문서 작성** — `toClaude/reports/platform_architecture_v2.md` (16개 섹션)
- [x] **TODO.md 업데이트** — V2 Phase 0~3 태스크 44건 추가
- [x] **메모리 업데이트** — project_status, architecture_v2, user_role
- [x] **Phase 0 실행 시작** — 세션 27에서 스캐폴딩 + 개발자 C 환경 구축 완료

### 핵심 아키텍처 결정 (합의 완료)
- 에이전트 섹션별 독립 (공유 금지, Protocol만 공유)
- ISA-95 단독 X → SCOR + ISA-95 하이브리드 온톨로지
- 시뮬레이션 2종: 코드 영향분석(그래프 BFS) + 비즈니스시뮬(파라메트릭 모델)
- 매핑 자동승인 임계값 0.95 (제조업 기준 상향)
- 비동기 Job queue 필수 (동기 HTTP X)
- Typed 계약 (dict X → 시나리오별 Pydantic 모델)
- Chat + Dashboard 하이브리드 UI (섹션 3)
- 모노리스 솔직하게 인정 (Python Protocol → 나중에 HTTP 분리)
- MVP 순서: Phase 1은 코드 영향분석 (데이터 없이 가치 제공 가능)
- Neo4j Community (그래프 DB)

---

## 2026-04-01 (세션 23 — GitHub 배포 + 방법론 + 기술스택 + 에이전트 논의)

- [x] **README.md 한국어 가이드** — 주요 기능, 아키텍처, 실행법, API, 스킬 작성법, 배포 가이드
- [x] **GitHub 공개 배포** — Jeensh/onTong, v1.0.0 태그, 프론트엔드 서브모듈 fix
- [x] **위키 콘텐츠 교체** — IT 시스템 운영 데모용 21개 문서 (장애대응/인프라/보안/업무절차/개발운영 + 스킬 3개)
- [x] **Agentic Workflow 방법론** — agentic-workflow/ 폴더 (가이드 + 템플릿 5개 + CLAUDE.md 프리셋 3개 + 6-Layer 스킬 2개)
- [x] **Mermaid 다이어그램** — ASCII → Mermaid 전환, 서브에이전트 검토 반영
- [x] **기술스택 상세 문서** — docs/tech-stack.md 작성 완료 (2회 검토, 로컬에 있음, 미커밋)
- [x] **Pydantic AI 프레임워크 도입** — Hybrid 접근: 구조화된 출력(cognitive reflect, classify, edit, write, conflict) + ReAct 루프 + 스트리밍을 Pydantic AI로 전환. litellm 직접 호출을 llm_generate.py 1곳으로 격리. 신규 7파일, 수정 12파일, 테스트 174/174 PASS
- [x] **SIMULATION/DEBUG_TRACE 에이전트** — 스캐폴딩 완료. 본격 구현은 동료가 별도 진행 (본 TODO 범위 밖)

## 2026-04-01 (세션 25 — 충돌 문서 비교 해결 기능)

- [x] **ConflictPair 모델** — `schemas.py`에 `ConflictPair(file_a, file_b, similarity, summary)` 추가, `ConflictWarningEvent`에 `conflict_pairs` 필드 추가
- [x] **충돌 페어 빌드** — `rag_agent.py`에서 충돌 감지 시 문서 쌍별 similarity 계산 + 명시적 ConflictPair 목록 생성
- [x] **ConflictStore 연동** — `AgentContext`에 `conflict_store` 추가, 채팅에서 감지된 충돌을 ConflictStore에 등록하여 ConflictDashboard와 동기화
- [x] **채팅 충돌 배너 개선** — 페어별 유사도 표시 + "나란히 비교" 버튼 → 기존 DiffViewer에서 "A가 최신/B가 최신" 선택으로 해결
- [x] **해결 상태 반영** — DiffViewer에서 deprecation 완료 시 채팅 배너에 "해결됨" 표시 (`resolvedConflicts` 상태 관리)
- [x] **하위 호환** — `conflict_pairs`가 없는 기존 이벤트에서도 레거시 배너 정상 표시
- [x] **충돌 감지 오탐 수정** — 2차 conflict_check 조건을 관련도 60% 이상 문서 2개 이상으로 강화, 일반적 질문에서 불필요한 충돌 경고 방지
- [x] **충돌 요약 품질 개선** — conflict_details[:200] 단순 자르기 → 문서명 기반 문장 추출 (`_extract_pair_summary`)

## 2026-04-01 (세션 24 — Pydantic AI 데모 테스트 버그 수정)

- [x] **스킬 참조문서 wikilink 해석 버그** — `[[장애등급-분류기준]]` 등 하위 디렉토리 문서를 파일명만으로 찾지 못하던 문제. skill_loader에 파일명→전체경로 인덱스 추가
- [x] **Pydantic AI LiteLLMProvider API 키 버그** — LiteLLMProvider가 OPENAI_API_KEY를 무시하고 placeholder 키를 사용하던 문제. OpenAIProvider로 직접 교체하여 올바른 API 키 전달
- [x] **Write intent 패턴 확장** — "체크리스트/가이드/매뉴얼/절차서 만들어줘" 패턴 추가 (기존은 "문서/위키" 키워드 필수)
- [x] **LLM Provider 추상화** — llm_factory.py를 레지스트리 패턴으로 재설계. OpenAI/Anthropic/Ollama/Google/Azure/Groq/DeepSeek 7개 프로바이더 지원. .env의 LITELLM_MODEL만 변경하면 전환 가능
- [x] **LLM 모델 업그레이드** — gpt-4o-mini → gpt-4o로 변경
- [x] **키워드 라우팅 → LLM 통합 분류** — router.py의 40+ regex 규칙과 rag_agent.py의 edit/write regex를 제거. 단일 LLM 호출(UserIntent 모델)로 agent + action을 동시에 판단. 키워드 누락 문제 근본 해결
- [x] **문서 업데이트** — README.md (AI Copilot 설명, LLM 설정 7개 프로바이더, 환경 변수 테이블, 테스트 수 177), docs/tech-stack.md (LiteLLM→Pydantic AI 섹션 재작성, Ollama 연동 방식 업데이트)
- [x] **충돌 감지 버그 수정** — (1) context[:3000]→[:6000] 확장 (2) zip() 불일치 수정: relevant_docs/metas/dists 동기화 (3) cognitive reflection이 놓친 충돌을 conflict_check 스킬로 2차 감지
- [x] **Lineage 동기화 버그 수정** — status를 미설정으로 변경 시 supersedes/superseded_by 자동 정리 + 상대 문서의 역참조도 연동 삭제
- [x] **충돌 설명 한국어화** — cognitive reflection + conflict_check 스킬 프롬프트에서 conflict_details를 한국어로 출력하도록 변경
- [x] **채팅 입력 히스토리** — 위/아래 방향키로 이전 질문 재입력 기능 (세션 내 히스토리)
- [x] **문서 생성/수정 워크스페이스 직접 작업** — 채팅에서 승인 버튼 제거, workspace에서 바로 미리보기+승인/취소/편집. 생성: 렌더링된 미리보기+상단바(저장/직접편집/취소). 수정: DiffView에서 hunk별 선택+전체적용/되돌리기/직접편집. 채팅은 상태 메시지만 표시.

## 2026-04-01 (세션 22 — Skill 시스템 테스트 추가)

- [x] **skill_loader Unit 테스트** — frontmatter 파싱, 카테고리 추출, 6-Layer 섹션, 캐시, wikilink 참조 (39 tests)
- [x] **skill_matcher Unit 테스트** — substring/Jaccard 매칭, threshold, priority 가중치, 한국어 토큰화 (18 tests)
- [x] **Skill API Integration 테스트** — CRUD, toggle, move, match, context 엔드포인트 (20 tests)

## 2026-04-01 (세션 21 — 스킬 관리 편의 기능)

- [x] **스킬 우클릭 컨텍스트 메뉴** — 편집/복제/토글/삭제 메뉴 (SkillContextMenu 컴포넌트)
- [x] **스킬 삭제 기능** — confirm 확인 후 deleteSkill API 호출
- [x] **스킬 드래그앤드롭** — 카테고리 간 이동 (PATCH /api/skills/{path}/move + 네이티브 DnD)
- [x] **BE move API** — 카테고리 변경 시 파일 이동 + frontmatter 업데이트

## 2026-03-31 (세션 21 — FE 고급 설정 UI)

- [x] **SkillCreateDialog 모달** — 6-Layer 필드(역할/워크플로우/체크리스트/출력형식/제한사항) + 참조문서 피커 포함 스킬 생성 다이얼로그
- [x] **ReferencedDocsPicker** — /api/search/quick 기반 문서 검색/선택 컴포넌트
- [x] **GET /api/skills/{path}/context** — 스킬 6-Layer 컨텍스트 조회 API
- [x] **스킬 복제 6-Layer 복사** — handleDuplicate에서 context API로 전체 내용 복사
- [x] **SkillContext TypeScript 타입** — FE 타입 추가

## 2026-03-31 (세션 20 — 6-Layer Skill Architecture)

- [x] **SkillContext 구조체** — 6개 레이어(role, workflow, checklist, output_format, self_regulation + instructions) 독립 필드
- [x] **skill_loader 업그레이드** — load_skill_context()가 SkillContext 반환, 참조문서 누락 추적
- [x] **Preamble 런타임 주입** — 날짜, 사용자 이름, 참조문서 현황을 코드가 자동 수집
- [x] **6-Layer 프롬프트 빌더** — _handle_skill_qa()에서 레이어별 조건부 조립 (빈 레이어 skip → 하위호환)
- [x] **스킬 생성 템플릿 확장** — 역할/워크플로우/체크리스트/출력형식/제한사항 가이드 추가
- [x] **SkillCreateRequest 확장** — role, workflow, checklist, output_format, self_regulation 필드 (BE+FE)
- [x] **데모 스킬 업그레이드** — 신규입사자-온보딩.md를 6-layer 형식으로 전환
- [x] **후속 질문 스킬 유지** — sessionSkill state로 세션 내 스킬 자동 유지, X 버튼/세션 전환 시만 해제
- [x] **자동 매칭 스킬 유지** — onSkillMatch SSE에서도 sessionSkill 저장
- [x] **스킬 유지 UI** — pill에 "(유지 중)" 라벨, Zap 버튼 하이라이트
- [x] **테스트 회귀 확인** — 68/68 PASSED

## 2026-03-31 (세션 19 — Skill System 고도화)

- [x] **스킬 생성 템플릿** — 지시사항/배경/제약조건/질문예시/참조문서 가이드 자동 채움
- [x] **스킬 CRUD 직접 파일 쓰기** — create/update도 storage.write() 우회 (frontmatter 보존)
- [x] **참조 문서 탐색 시각화** — thinking step에서 각 참조 문서를 개별 표시 (📄 문서명 1/N)
- [x] **스킬 목록 API 비활성 포함** — list_skills(include_disabled=True)로 사이드바에서 재활성화 가능
- [x] **Copilot 피커 실시간 갱신** — 피커 열 때마다 refreshSkillList() 호출
- [x] **HR 스킬 파일 복원** — storage.write()로 frontmatter 손상된 파일 복구
- [x] **토글 API 직접 파일 쓰기** — storage.write() 우회하여 스킬 frontmatter 보존
- [x] **SE-1~12: Skill System 고도화** (카테고리 + 우선순위 + 무시 관리)
  - BE: SkillMeta에 category/priority/pinned 필드 추가
  - skill_loader: 폴더 경로 기반 카테고리 자동 추출 (_skills/HR/file.md → "HR")
  - skill_matcher: priority 곱셈 가중치 (score * (0.8 + p*0.04)) + tiebreaker 확장
  - PATCH toggle API: enabled 필드 flip
  - FE 사이드바: 카테고리 접이식 그룹, 검색, 토글(활성/비활성), 복제 버튼, pinned 표시
  - FE 생성 폼: 카테고리(combobox) + 우선순위 입력 추가
  - Copilot 피커: 카테고리별 그룹핑 + 스킬 검색
  - localStorage: dismissed skills 영속화
  - 데모 스킬 카테고리 폴더 이동: HR/신규입사자, Finance/출장비, @개발자/SCM/구매발주

---

## 2026-03-31 (세션 18 — User-Facing Skill System)

- [x] **US-1~15: User-Facing Skill System 전체 구현** (6 phases)
  - Phase 1: 스키마(SkillMeta, SkillListResponse, SkillCreateRequest) + skill_loader + skill_matcher
  - Phase 2: AgentContext 확장 + api/agent.py 스킬 해석 + RAGAgent._handle_skill_qa
  - Phase 3: Skill CRUD API + main.py 와이어링
  - Phase 4: 사이드바 ⚡ 스킬 탭 + 인라인 생성 폼
  - Phase 5: Copilot 스킬 피커 + 자동 제안 + SSE skill_match 이벤트
  - Phase 6: 그래프 스킬 노드 (보라색 다이아몬드)
- [x] **데모용 샘플 스킬 3개 생성**
  - `_skills/출장비-정산-도우미.md` (공용, trigger: 출장비/출장 정산)
  - `_skills/신규입사자-온보딩.md` (공용, trigger: 신규입사/온보딩)
  - `_skills/@개발자/구매발주-안내.md` (개인, trigger: 구매발주/납품 검수)

---

## 2026-03-30 (세션 16 — 문서 관계 그래프 리디자인)

- [x] **P3-AH5: 그래프 검색 우선 UX** — 전체 그래프 대신 검색 우선 UI로 전환. 중심 문서 선택 후 BFS 관계만 표시
  - `DocumentGraph.tsx`: 검색 랜딩 페이지 + `/api/search/quick` 디바운스(200ms) + 인라인 문서 전환 검색
  - `search.py`: `center_path` 필수 파라미터로 변경, 유사도 엣지 conflict store에서 읽기 (broken import 수정)

---

## 2026-03-30 (세션 15 — 충돌 감지 리팩토링)

- [x] **CR-1: ChromaDB 네이티브 유사도 검색** — `get_file_embeddings()`, `query_by_embedding()` 추가
- [x] **CR-2: ConflictStore 신규** — Redis/InMemory 이중 백엔드, SHA256 해시 키, `replace_for_file`/`remove_for_file`
- [x] **CR-3: ConflictService 리라이트** — `check_file()` 증분 감지, `full_scan()`, `get_pairs()`, `update_metadata()`
- [x] **CR-4: API 수정** — `/duplicates` store 읽기, `/full-scan` + `/scan-status` 신규
- [x] **CR-5: WikiService 훅** — `_bg_index()`, `delete_file()`, `move_file()`, `move_folder()`에 충돌 감지 연결
- [x] **CR-6: 프론트엔드** — 즉시 로드 + "전체 스캔" 버튼 + 프로그레스 바
- [x] **CR-7: 테스트** — conflict_store, conflict_service, API, E2E (23 tests 통과)

---

## 2026-03-30 (세션 14 — Phase 5 구현)

- [x] P5A-1: 트리 Lazy Loading — depth=1 초기 로드 + subtree API, `has_children` 플래그
- [x] P5A-2: 서버 사이드 검색 — MiniSearch 제거, `/api/search/quick` + `/api/search/resolve-link`
- [x] P5A-3: 트리 증분 업데이트 — CRUD 후 낙관적 로컬 업데이트 (fetchTree 제거)
- [x] P5A-4: 프론트엔드 ETag 활용 — `fetchWithETag()` 유틸리티, 304 캐시
- [x] P5B-1: Uvicorn 멀티 워커 — `--workers 4` + Docker 리소스 제한
- [x] P5B-2: 비동기 인덱싱 — save 즉시 반환 + IndexStatus 추적
- [x] P5B-2a: 인덱싱 상태 UI — 에디터 "검색 반영 대기 중" 배너
- [x] P5B-3: BM25 주기적 리빌드 — 10초 데몬 스레드
- [x] P5B-4: 하이브리드 검색 병렬화 — vector + BM25 병렬 실행
- [x] P5B-5: 시작 시 백그라운드 인덱싱 — 앱 즉시 가용
- [x] P5B-6: list_all_files() 최적화 — asyncio.to_thread + list_file_paths()
- [x] P5C-1: Redis 도입 + Lock 이관 — SET NX EX, LockBackend ABC, 자동 폴백
- [x] P5C-2: Redis 기반 쿼리 캐시 — RedisQueryCache, file→key 인덱스
- [x] P5C-3: Lock Refresh 배치화 — lockManager 중앙 매니저 + batchRefreshLock API
- [x] P5C-4: ACL 캐싱 + 핫 리로드 — check_permission LRU 캐시(60s TTL), 30s 파일 변경 감지
- [x] P5D-1: Nginx 리버스 프록시 — nginx.conf + docker-compose nginx 서비스
- [x] P5D-2: Docker 리소스 제한 — 이전 세션에서 완료 (backend 4C/4G, frontend 1C/1G 등)
- [x] P5D-3: ChromaDB 커넥션 풀링 — chromadb.Settings 설정
- [x] P5D-4: get_all_embeddings 페이지네이션 — offset/limit 1000건 배치 조회
- [x] P5D-5: SSE 실시간 이벤트 — EventBus + /api/events SSE endpoint + TreeNav 구독
- [x] P5E-1: RAG LLM 파이프라인 최적화 — reflection 캐시로 반복 쿼리 LLM 호출 스킵
- [x] P5E-2: LLM 응답 캐싱 — cognitive_reflect 인메모리 LRU (256개, TTL 10분)
- [x] P5E-3: Ollama 동시 처리 — OLLAMA_NUM_PARALLEL=4, asyncio.Semaphore(8)
- [x] P5E-4: 검색 인덱스 캐싱 — backlinks/tags 엔드포인트 60s TTL 캐시
- [x] P5E-5: 메타데이터 엔드포인트 최적화 — `list_all_metadata()` (frontmatter 4KB만 읽기) + 60s TTL 캐시
- [x] **충돌 감지 성능 개선 + 500 에러 수정** — numpy 벡터화 코사인 유사도, asyncio.to_thread() 래핑, threshold 0.95로 상향, 결과 200건 제한, 120s TTL 캐시. ChromaDB get_all_embeddings 79초 병목은 캐싱으로 완화.

---

## 2026-03-30 (세션 13)

- [x] Phase 4 프로덕션 작업 리포트 작성 → `toClaude/reports/phase4_production_readiness.md`
- [x] Phase 4 검토/테스트 플랜 작성 → `toClaude/reports/phase4_review_test_plan.md`
- [x] 대규모 대응 규모 분석 (컴포넌트별 병목, 커버 가능 규모 판정)
- [x] 스트레스 테스트 스크립트 3종 포함 (파일 규모, 동시 사용자, 잠금 동시성)
- [x] 스트레스 테스트 실행 + 결과 리포트 → `toClaude/reports/phase4_stress_test_results.md`
- [x] Phase 5 엔터프라이즈 스케일링 플랜 수립 (23 tasks, 5 sub-phase)
- [x] TODO.md에 Phase 5 태스크 추가 (P5A~P5E)

---

## 2026-03-29 (세션 12 — Phase 4 프로덕션 준비)

- [x] P4A-1: PDF.js worker 로컬 번들링 (unpkg CDN → public/)
- [x] P4A-2: Google Fonts 제거 → 시스템 폰트 스택
- [x] P4A-3: LLM 설정 추상화 (Ollama 기본값, OpenAI 옵션)
- [x] P4A-4: 임베딩 로컬 전환 (설정 기반, ChromaDB 기본 embedding)
- [x] P4A-5: 외부 의존성 점검 스크립트
- [x] P4B-1: Backend Dockerfile (Python 3.10-slim 멀티스테이지)
- [x] P4B-2: Frontend Dockerfile (Node 20-alpine 멀티스테이지 + standalone)
- [x] P4B-3: docker-compose.yml 통합 (backend+frontend+chroma, monitoring profile)
- [x] P4B-4: 환경 변수 분리 (.env.example + .env.production.example)
- [x] P4B-5: 헬스체크 + 시작 순서 + .dockerignore
- [x] P4C-3: NASBackend 구현 (LocalFSAdapter 서브클래스, 마운트 경로 검증)
- [x] P4C-4: 스토리지 팩토리 설정 기반 전환 (STORAGE_BACKEND=local/nas)
- [x] next.config.ts: standalone 출력 모드 + BACKEND_URL 환경변수 지원
- [x] P4D-1: Lock 서비스 (인메모리, TTL 5분, 자동 만료)
- [x] P4D-2: Lock API (POST /lock, DELETE, GET /status, POST /refresh)
- [x] P4D-3: 에디터 잠금 UI (잠금 획득, 읽기전용 배너, 세션 사용자 ID)
- [x] P4D-4: 자동 해제 (탭 닫기 → releaseLock, 2분 주기 TTL 리프레시)
- [x] P4F-1: .gitignore 강화 (.pem, .key, credentials.json 추가)
- [x] P4F-2: CORS 강화 (와일드카드 → 명시적 메서드/헤더 화이트리스트)
- [x] P4F-3: 구조화 로깅 (JSON 포맷 + request_id 미들웨어)
- [x] P4F-4: 입력 검증 (path traversal 차단, content 10MB 제한)
- [x] P4F-5: 전역 에러 핸들러 (500 → JSON 응답, ValueError → 400)
- [x] P4E-1~2: ACL 저장소 (JSON 기반, 폴더 상속, document 오버라이드)
- [x] P4E-3: require_read/require_write 의존성
- [x] P4E-4: Wiki API에 읽기/쓰기 권한 체크 적용
- [x] P4E-5: RAG 검색 결과에 ACL 기반 필터 추가
- [x] P4E-7: ACL 관리 API + PermissionEditor UI + TreeNav 메뉴
- [x] P4G-1: 검색 인덱스 API에 offset/limit 페이지네이션
- [x] P4G-2: 트리 API depth 파라미터 + subtree lazy load API
- [x] P4G-3: ChromaDB upsert 100건 단위 배치 처리
- [x] P4G-4: 트리 API ETag/304 캐싱

---

## 2026-03-29 (세션 11)

- [x] **Phase 3-A: 문서 검색 (커맨드 팔레트)** (7 tasks)
  - MiniSearch 클라이언트 사이드 검색 (즉시 결과, prefix+fuzzy, 한글 토크나이저)
  - 서버 사이드 하이브리드 검색 API (`GET /api/search/hybrid` — BM25+벡터 RRF)
  - Ctrl+K / Cmd+K 커맨드 팔레트 UI (cmdk CommandDialog 기반)
  - 키워드/의미 검색 모드 전환, 결과 하이라이트, 태그 뱃지, 스니펫 미리보기
  - TreeNav 사이드바 헤더에 검색 아이콘 추가

- [x] **Phase 3 고도화** (4 tasks)
  - 문서 열기 시 연결 문서 패널 (lineage + wiki-link 백링크, 참조/역참조, 접이식)
  - 그래프 내 문서 검색 (검색→노드 센터링+줌)
  - 문서 링크 복사 — 사이드바 우클릭 "문서 링크 복사" (md→`[[문서명]]`, 기타→경로)
  - WikiLink 인라인 노드: `[[문서명]]` 타이핑/붙여넣기 시 클릭 가능한 링크로 자동 변환, 클릭 시 openTab

- [x] **Phase 3-B: 문서 관계 그래프** (13 tasks)
  - react-force-graph-2d 기반 force-directed 그래프 시각화
  - 그래프 데이터 API (`GET /api/search/graph` — 백링크+lineage+related+similarity 집계, BFS)
  - 4가지 연결 타입: wiki-link(gray), supersedes(orange), related(blue/dashed), similar(red/dotted)
  - 노드: status별 색상, degree 기반 크기, 라벨, 호버 툴팁
  - 노드 클릭→문서 열기, 우클릭→컨텍스트 메뉴, 현재 문서 중심 보기
  - center_path + depth BFS로 대규모 위키 성능 보장
  - Virtual Tab (`"document-graph"`), 관리 섹션 메뉴 진입점

---

## 2026-03-29 (세션 10)

- [x] **P2B-6: RAG deprecated 문서 필터링 + 최신 문서 자동 대체** (3 tasks)
  - 검색 시 deprecated 문서 제외 (ChromaDB where + BM25 필터)
  - deprecated만 검색 시 superseded_by 체인 추적 → 최신 문서 자동 대체
  - 기존 +0.3 패널티 로직 제거

- [x] **P2B-7: 충돌 대시보드 해결 상태 관리** (3 tasks)
  - DuplicatePair에 resolved 필드 + 양방향 lineage 자동 해결 판정
  - API filter 파라미터 (unresolved/resolved/all)
  - 프론트엔드 탭 필터 (미해결/해결됨/전체), 기본값 "미해결"

- [x] **증분 인덱싱 해시 비교 버그 수정** — frontmatter만 변경 시 인덱싱 스킵되던 문제
- [x] **conflict_service numpy array 비교 버그** — ChromaDB embeddings가 numpy array → len() 체크로 변경
- [x] **deprecate API 500 에러 수정** — storage.save → _serialize_frontmatter + save_file로 변경
- [x] **DiffViewer React key 경고 수정** — Fragment key 추가
- [x] **CONFLICT_CHECK 프롬프트 강화** — 다른 팀/부서의 다른 수치도 충돌로 판정
- [x] **ChromaDB 메타데이터 동기화 버그 수정** — `_metadata_to_chroma()`에 `superseded_by`/`supersedes` 누락 → 추가
- [x] **deprecate API force reindex** — 상태 변경 후 ChromaDB 즉시 동기화 보장
- [x] **메타데이터 완전성 가드 테스트** — `DocumentMetadata` 스칼라 필드 누락 시 테스트 실패
- [x] **`_metadata_to_chroma()` 자동생성 전환** — 수동 필드 나열 → `DocumentMetadata.model_fields` 순회 방식으로 변경. 새 필드 추가 시 자동 반영
- [x] **재고관리 샘플 데이터 lineage 누락 수정** — v1에 `superseded_by`, v2에 `supersedes` 추가

---

## 2026-03-28 (세션 9)

- [x] **증분 인덱싱 해시 비교 버그 수정** — frontmatter만 변경 시 인덱싱 스킵되던 문제
  - `wiki_indexer.py`: `has_changed()` 비교 대상을 `wiki_file.content` → `wiki_file.raw_content`로 변경
  - `sseClient.ts`: `onSources` 콜백 타입에 `status`, `updated`, `updated_by` 필드 추가

- [x] **P2B-5: 문서 계보(Lineage) 시스템** (5 tasks)
  - `schemas.py`: `DocumentMetadata`에 `supersedes`, `superseded_by`, `related` 필드 추가
  - `local_fs.py`: frontmatter 파싱/직렬화에 lineage 필드 반영
  - `rag_agent.py`: superseded 문서 +0.3 거리 패널티 + "폐기됨" 경고 삽입
  - `api/wiki.py`: `GET /api/wiki/lineage/{path}` — 계보 트리 반환 (supersedes/superseded_by/related 해석)
  - `LineageWidget.tsx`: 에디터 상단 lineage 배너 (이전/새 버전 링크, 관련 문서)
  - `DiffViewer.tsx`: "A가 최신"/"B가 최신" 버튼 → bidirectional lineage 자동 설정
  - `tests/test_p2b5_lineage.py`: 10 tests (lineage 필드, frontmatter roundtrip, 패널티) ✅

- [x] **P2B-4: 인라인 비교 뷰** (5 tasks)
  - `api/wiki.py`: `GET /api/wiki/compare?path_a=&path_b=` — 두 문서 body+메타데이터 반환
  - `DiffViewer.tsx`: side-by-side diff (추가=녹색, 삭제=빨강, 변경=amber), 라인 번호
  - `workspace.ts`: `document-compare` VirtualTabType
  - `useWorkspaceStore.ts`: `openCompareTab(pathA, pathB)` 메서드 + 타이틀 자동 생성
  - `FileRouter.tsx`: compare 탭 라우팅 (filePath에서 경로 파싱)
  - `DiffViewer.tsx`: "A가 최신"/"B가 최신" 버튼 → deprecated 자동 설정
  - `ConflictDashboard.tsx`: "나란히 비교" 버튼 → openCompareTab 연동

- [x] **P2B-3: 문서 중복/충돌 감지 대시보드** (5 tasks)
  - `chroma.py`: `get_all_embeddings()` — 전체 임베딩/문서/메타데이터 조회
  - `conflict/conflict_service.py`: `ConflictDetectionService` — 파일별 평균 임베딩 + 코사인 유사도 쌍 탐지
  - `api/conflict.py`: `GET /duplicates` (유사 문서 쌍) + `POST /deprecate` (deprecated 설정)
  - `main.py`: conflict_api 라우터 등록
  - `workspace.ts`: `conflict-dashboard` VirtualTabType 추가
  - `useWorkspaceStore.ts`: 탭 타이틀 추가
  - `FileRouter.tsx`: ConflictDashboard 라우팅
  - `TreeNav.tsx`: 관리 섹션에 "문서 충돌 감지" 메뉴 (AlertTriangle 아이콘)
  - `ConflictDashboard.tsx`: 유사도 임계값 조절 + 유사 문서 쌍 테이블 + 파일 열기/폐기 액션
  - `tests/test_p2b3_conflict_dashboard.py`: 11 tests (코사인유사도, 평균임베딩, 서비스 통합)

- [x] **P2B-2: 메타데이터 기반 신뢰도 표시** (5 tasks)
  - `schemas.py`: `DocumentMetadata.status` 필드 추가 (draft/review/approved/deprecated)
  - `local_fs.py`: frontmatter 파싱/직렬화에 status 반영
  - `wiki_indexer.py`: ChromaDB metadata에 status 포함
  - `schemas.py`: `SourceRef`에 `updated`, `updated_by`, `status` 필드 확장
  - `rag_agent.py`: `_build_sources()`에서 메타데이터 주입
  - `agent.ts`: SourceRef 타입 확장
  - `AICopilot.tsx`: 소스 패널에 status 아이콘/색상 + 날짜 배지 + 상세 tooltip
  - `wiki.ts`: `DocumentStatus` 타입 + `DocumentMetadata.status`
  - `MetadataTagBar.tsx`: status 드롭다운 + collapsed 뱃지
  - `frontmatterSync.ts`: status 파싱/직렬화
  - `tests/test_p2b2_status_field.py`: 10 tests (스키마, SourceRef, frontmatter roundtrip)

- [x] **P2B-1: RAG 답변 충돌 감지 프롬프트** (4 tasks)
  - `rag_agent.py`: `_build_context_with_metadata()` — 각 청크에 [출처/작성자/최종수정/도메인/관련도] 헤더 삽입, 중복 파일 표시
  - `rag_agent.py`: `FINAL_ANSWER_SYSTEM_PROMPT`에 문서 충돌 감지 규칙 추가 (모순 시 ⚠️ 경고 + 최신 문서 권고)
  - `rag_agent.py`: `COGNITIVE_REFLECT_PROMPT`에 CONFLICT_CHECK 항목 + `has_conflict`/`conflict_details` JSON 필드
  - `schemas.py`: `ConflictWarningEvent` 스키마 신규 (details + conflicting_docs)
  - `agent.ts`: `ConflictWarningEvent` 타입 추가
  - `sseClient.ts`: `onConflictWarning` 콜백 + dispatch 처리
  - `AICopilot.tsx`: `ConflictWarning` 인터페이스, ChatMessage에 필드 추가, amber 경고 배너 UI
  - `tests/test_p2b1_conflict_detection.py`: 8 tests (메타데이터 헤더, 스키마, 프롬프트 검증)

---

## 2026-03-28 (세션 8)

- [x] **P2A-1: LLM 호출 병렬화 + 제거** (4 tasks)
  - `router.py`: 키워드 규칙 확대 — 기업/도메인 용어 + 한글 catch-all 패턴 추가 (11/12 키워드 적중)
  - `rag_agent.py`: `_check_clarity` LLM 호출 → `_check_clarity_rule_based` 규칙 기반으로 전환 (0ms)
  - `agent.py` + `rag_agent.py`: 라우팅 + 쿼리보강 `asyncio.gather` 병렬화, `augmented_query` 파라미터 전달
  - `tests/bench_rag_latency.py`: 파이프라인 지연시간 벤치마크 스크립트 (키워드 적중률, 순차/병렬 비교)

- [x] **메타데이터 템플릿 한글 IME 버그 수정**
  - `MetadataTemplateEditor.tsx`: `onKeyDown`에 `isComposing` 체크 추가 — 한글 조합 중 Enter 이중 등록 방지

- [x] **샘플 PDF/PPTX 파일 재생성**
  - 이전 세션에서 깨진 파일(8B/70B) → reportlab/python-pptx로 정상 재생성

- [x] **P2A-2: 하이브리드 검색 (벡터 + BM25)** (5 tasks)
  - `infrastructure/search/bm25.py`: BM25Okapi 인덱스 + 한글/영어 토크나이저
  - `infrastructure/search/hybrid.py`: RRF(Reciprocal Rank Fusion) 병합
  - `rag_agent.py`: 하이브리드 검색 적용, thinking step에 검색 모드 표시
  - `wiki_indexer.py`: BM25 인덱스 자동 동기화 (추가/삭제/전체 재인덱싱)
  - `tests/test_hybrid_search.py`: 검색 품질 비교 테스트

- [x] **P2A-3: 증분 인덱싱** (4 tasks)
  - `infrastructure/storage/file_hash.py`: SHA256 해시 기반 변경 감지
  - `wiki_indexer.py`: 해시 비교 → 미변경 파일 스킵 (15파일 0초 완료)
  - `wiki.py`: `POST /api/wiki/reindex?force=true` 파라미터 추가

- [x] **P2A-4: 임베딩/검색 캐싱** (4 tasks)
  - `infrastructure/cache/query_cache.py`: LRU 캐시 (TTL 5분, 128 entries)
  - `rag_agent.py`: 캐시 히트 시 검색 스킵 ("캐시" 모드 표시)
  - `wiki_indexer.py`: 문서 변경 시 해당 파일 관련 캐시 자동 무효화
  - 캐시 히트율 모니터링 로그 내장

- [x] **P2A-5: 메타데이터 사전 필터링** (4 tasks)
  - `application/agent/filter_extractor.py`: domain/process 키워드 자동 추출
  - `rag_agent.py`: 추출 필터 → ChromaDB where 절 적용 + 0건 시 필터 제거 fallback

- [x] **P2A-6: Cross-encoder 리랭킹** (4 tasks)
  - `infrastructure/search/reranker.py`: LLM 기반 리랭킹 (기존 LiteLLM 활용)
  - `rag_agent.py`: 검색 후 리랭킹 단계 추가
  - `config.py`: `enable_reranker` 설정 (on/off), 지연 시간 로깅
  - `tests/test_reranker.py`: A/B 비교 테스트

- [x] **Phase 2-B: 문서 충돌 감지 & 해소 계획 수립** (5 Steps, 24 Tasks)
  - `master_plan.md`에 Phase 2-B 섹션 추가 (배경, 5단계 상세 설계, 타임라인)
  - `TODO.md`에 P2B-1 ~ P2B-5 태스크 테이블 추가 + 진행 요약 갱신
  - 항목: RAG 충돌 감지 프롬프트, 메타데이터 신뢰도, 중복 감지 대시보드, 인라인 비교 뷰, 문서 계보

---

## 2026-03-28 (세션 7)

- [x] **Phase 1.5: PDF Viewer 구현**
  - `react-pdf` 패키지 설치
  - `PdfViewer.tsx`: 페이지 네비게이션, 6단계 줌(50%~200%), 50페이지 이상 페이지 그룹 페이지네이션
  - 키보드 화살표 네비게이션, 페이지 번호 직접 입력
  - `FileRouter.tsx`: dynamic import (ssr: false)

- [x] **Phase 1.5: Presentation Viewer 구현**
  - 백엔드: `GET /api/files/pptx-data/{path}` — python-pptx로 슬라이드 JSON 추출 (텍스트/이미지/서식)
  - `PresentationViewer.tsx`: 백엔드 JSON → HTML/CSS 렌더링, 슬라이드 네비게이션, 키보드 조작
  - pptx-viewer 패키지는 Turbopack 호환 문제로 제거, 백엔드 파싱 방식으로 전환

---

## 2026-03-26 (세션 5)

- [x] **에이전트 라우팅/RAG 고도화 — 일반 질문 WIKI_QA 미라우팅 수정**
  - `router.py`: KEYWORD_RULES 확장 — 일반 검색(찾아줘, 누구, 어떻게 등) 패턴 WIKI_QA 매칭
  - `router.py`: LLM classifier 프롬프트 개선 — UNKNOWN 대신 WIKI_QA를 기본 폴백으로 설정
  - `rag_agent.py`: 시스템 프롬프트 범용화 ("제조 SCM 도메인" → "사내 Wiki", 인사/조직 등 포함)
  - `rag_agent.py`: Clarity check 조건 완화 — `len(query) < 10` 제거, 관련성 기반으로만 판단
  - `rag_agent.py`: Clarity check 프롬프트 개선 — 구체적 키워드 있으면 CLEAR 처리

- [x] **RAG 검색 품질 고도화 — 구조화 데이터(인사정보) 미검색 수정**
  - `rag_agent.py`: 대화 히스토리 기반 쿼리 보강 (`_augment_query`) — 후속 질문에 이전 맥락 반영
  - `rag_agent.py`: 시스템 프롬프트 강화 — 구조화 데이터(키:값) 추출, 인사정보 이름/소속 명시 규칙
  - `rag_agent.py`: 검색 범위 확대 (n_results 5→8) + MIN_SOURCE_RELEVANCE 0.4→0.3
  - `wiki_indexer.py`: 짧은 문서에 파일 경로 컨텍스트 프리픽스 추가 → 임베딩 품질 향상

- [x] **RAG 탐색 과정 시각화 (하이브리드 방식)**
  - Backend: `ThinkingStepEvent` 스키마 추가, RAG 파이프라인 각 단계에서 `thinking_step` SSE 이벤트 방출
  - 단계: 쿼리 보강 → 문서 검색 → 명확성 확인 → 답변 생성 (각각 start/done 상태)
  - Frontend: `ThinkingStepsDisplay` 컴포넌트 — 진행 중 애니메이션 + 완료 후 접이식 로그
  - SSE client에 `onThinkingStep` 콜백 추가

- [x] **Self-Reflective Cognitive Pipeline (Option A: Two-Step Run)**
  - `rag_agent.py`: `_cognitive_reflect()` — 숨겨진 LLM 호출로 의도분석/초안/자기검토 수행, 백엔드 콘솔에만 로깅
  - `rag_agent.py`: 최종 답변 생성 시 critique 피드백을 시스템 프롬프트로 주입 → 품질 향상
  - `rag_agent.py`: `FINAL_ANSWER_SYSTEM_PROMPT` — 공감 IT 파트너 페르소나, Minto Pyramid, 실행 가능 다음 단계
  - `rag_agent.py`: `COGNITIVE_REFLECT_PROMPT` — 3단계 인지 분석 (thought/draft/critique)
  - `AICopilot.tsx`: `cognitive_reflect` thinking step + Brain 아이콘 추가
  - **SSE 파이프라인 무변경**: content_delta에는 최종 답변만 전송, 내부 사고 절대 미노출

- [x] **Phase 2-A: RAG 성능 고도화 계획 수립** (6 Steps, 25 Tasks)
  - `master_plan.md`에 Phase 2-A 섹션 추가 (배경, 6단계 상세 설계, 타임라인)
  - `TODO.md`에 P2A-1 ~ P2A-6 태스크 테이블 추가 + 진행 요약 갱신
  - 항목: LLM 병렬화, 하이브리드 검색, 증분 인덱싱, 캐싱, 메타데이터 필터링, 리랭킹

---

## 2026-03-26 (세션 4)

- [x] **문서 메타데이터 이력 관리 (생성일/수정일/생성자/수정자)**
  - `DocumentMetadata`에 `updated`, `created_by`, `updated_by` 필드 추가 (기존 `author` → `created_by` 마이그레이션)
  - Backend Storage Layer: 저장 시 자동 타임스탬프/작성자 주입 (`created`/`created_by`는 최초만, `updated`/`updated_by`는 매번)
  - WikiService + Wiki API에 `user_name` 전달 경로 연결 (인증 레이어 활용)
  - ChromaDB indexer에 새 필드 반영 → RAG 검색에서 활용 가능
  - Frontend: 타입/파서/시리얼라이저 업데이트, MetadataTagBar에 읽기전용 이력 표시

- [x] **AI Copilot 마크다운 렌더링 + 저장 후 메타데이터 갱신 버그 수정**
  - `react-markdown` + `remark-gfm` 설치, AssistantBubble에 마크다운 렌더링 적용
  - prose 스타일링 (볼드, 이탤릭, 코드, 리스트, 테이블, 헤딩 등)
  - `handleSave` 후 서버 응답의 metadata를 로컬 상태에 반영 (updated/updated_by 갱신)

- [x] **사이드바 빈 공간 우클릭 컨텍스트 메뉴**
  - 빈 공간 우클릭 시 "새 문서" / "새 폴더" 메뉴 표시 (루트 레벨)
  - ContextMenuState.node를 nullable로 변경, RootDropZone에 onContextMenu 핸들러 추가

- [x] **인증 추상화 레이어 (Auth Abstraction Layer)**
  - Backend: `backend/core/auth/` — User 모델, AuthProvider ABC, NoOpProvider, FastAPI Depends
  - Backend: 전체 API 라우터에 `dependencies=[Depends(get_current_user)]` 적용
  - Backend: `config.py`에 `auth_provider` 설정, `factory.py`로 provider 선택
  - Frontend: `lib/auth/` — AuthProvider 인터페이스, AuthContext, useAuth hook, DevAuthProvider
  - Frontend: `Providers.tsx` → `layout.tsx` 연결, `useAuthFetch` 유틸
  - 추후 SSO/LDAP/OIDC 등으로 교체 시 Provider만 구현하면 됨

---

## 2026-03-26 (세션 3)

- [x] **TreeNav 활성 파일 강조 + 폴더 기본 접힘**
  - 현재 열린 탭의 파일이 사이드바에 `bg-primary/15` 강조 표시
  - 폴더 기본값 접힘 (`useState(false)`), 활성 파일 포함 폴더만 자동 펼침
  - `activeFilePath` prop을 DraggableTreeItem에 전달

- [x] **Context Engineering 시스템 업그레이드**
  - `toClaude/archive/` 생성, 기존 요약/이슈 파일 8개 아카이브 이동
  - CHECKLIST.md → 테스트 매뉴얼로 전환 (모든 체크박스 제거)
  - `agent_tools_schema.md` 스켈레톤 생성 (PydanticAI tool SSOT)
  - CLAUDE.md에 Smart TDD Rule + Archive Rule 추가
  - TODO.md = 상태 추적 SSOT 확립

---

## 2026-03-26 (세션 2)

- [x] **RAG 에이전트 명확화 질문 기능** (Step 1-F 고도화)
  - 모호한 질문 시 바로 답변하지 않고 검색 결과 기반 명확화 질문
  - 검색 결과를 보여주면서 선택지 제시 ("이런 문서를 찾았는데 어떤 걸 원하시나요?")
  - 대화 히스토리 활용 (세션 내 멀티턴 맥락 유지)

- [x] **RAG 출처 참조 고도화** (Step 1-F 고도화)
  - 관련도 필터링: MIN_SOURCE_RELEVANCE(0.4) 미만 출처 제외
  - 명확화 질문 시 낮은 threshold(0.2)로 참조 문서 표시
  - 구체적 답변 시 높은 threshold(0.4)로 관련 문서만 표시

- [x] **UI 라벨 변경**
  - AI Copilot → On-Tong Agent
  - 사이드바 Wiki → On-Tong

- [x] **에이전트 세션 관리** (Step 1-F 고도화)
  - 새 대화 시작 / 세션 목록 / 세션 전환 / 세션 삭제
  - 첫 메시지 기반 세션 제목 자동 생성
  - 세션별 독립된 대화 히스토리

- [x] **드래그앤드롭 + 이름 변경** (Step 1-A 고도화)
  - @dnd-kit DndContext + DragOverlay + PointerSensor(distance:8)
  - DraggableTreeItem: useDraggable + useDroppable(폴더만)
  - RootDropZone: 루트 레벨 드롭 지원
  - 이름 변경: 우클릭 → InlineInput 인라인 편집 → PATCH API
  - 열린 탭 경로 자동 업데이트 (updateTabPath 스토어 메서드 추가)
  - 백엔드: PATCH /api/wiki/file/{path}, PATCH /api/wiki/folder/{path}

- [x] **사이드바 파일/폴더 관리** (Step 1-A 고도화)
  - 새 문서 생성 (+ 버튼 → 파일명 입력 → .md 자동 생성)
  - 파일 삭제 (우클릭 → 컨텍스트 메뉴 → 삭제 + 탭 자동 닫기)
  - 새 폴더 생성 (헤더 버튼 + 폴더 우클릭 → 새 폴더)
  - 폴더 삭제 (우클릭 → 삭제, 빈 폴더만 가능)
  - 폴더 내 파일/하위폴더 생성 (폴더 우클릭 컨텍스트 메뉴)
  - 트리 새로고침 버튼
  - 백엔드: POST/DELETE /api/wiki/folder API 추가

---

## 2026-03-26 (세션 1)

- [x] **메타데이터 템플릿 관리 기능** (Phase 2)
  - 백엔드: `GET/PUT/POST /api/metadata/templates` — JSON 파일 기반 CRUD (`wiki/.ontong/metadata_templates.json`)
  - 프론트엔드: `MetadataTemplateEditor` — Workspace 가상 탭으로 열림, Domain/Process/Tags 추가·삭제 UI
  - MetadataTagBar의 하드코딩된 DEFAULT_DOMAINS/DEFAULT_PROCESSES → 템플릿 API에서 동적 로드로 대체

- [x] **메타데이터 태깅 고도화** (Phase 2)
  - 에러코드 자동 추출: 저장 시 본문에서 정규식(`DG320`, `ERR-001` 등) 자동 감지 → frontmatter에 주입
  - 태그 정규화: `GET /api/metadata/tag-merge-suggestions` — 유사 태그 감지 (캐시/캐쉬/cache → 통합 제안)
  - 태그 기반 사이드바: Domain > Process > Tags 계층 브라우저, 클릭 시 문서 목록 표시
  - 미태깅 문서 대시보드: `UntaggedDashboard` — 미태깅 목록 + 일괄 자동 태깅 + 태그 사용 통계
  - `GET /api/metadata/files-by-tag` — 필드·값 기반 문서 필터링 API
  - `GET /api/metadata/untagged` — 미태깅 문서 목록 API

- [x] **3-Pane UI 고도화** (Phase 2)
  - 탭 시스템 확장: `TabType = FileType | VirtualTabType`, `openVirtualTab()` 스토어 메서드 추가
  - 사이드바 3-섹션 전환: 파일 트리(FolderTree) / 태그 브라우저(Tags) / 관리(Settings) 아이콘 탭
  - Workspace: 가상 탭(메타데이터 템플릿, 미태깅 대시보드) 지원, FileRouter에서 TabType 기반 라우팅

---

## 2026-03-30 (세션 17 — Skill System 기반 구축)

- [x] **Skill System Phase 1-5 구현**
  - Skill Protocol + SkillResult + SkillRegistry (`backend/application/agent/skill.py`)
  - AgentContext: per-request context with `run_skill()`, `emit_thinking()`, `sse()` (`backend/application/agent/context.py`)
  - 7개 스킬 추출: query_augment, wiki_search, wiki_read, wiki_write, wiki_edit, llm_generate, conflict_check (`backend/application/agent/skills/`)
  - ReAct loop + tool executor for LLM tool-use agents (`backend/application/agent/tool_executor.py`)
  - RAGAgent refactoring: skill 호출로 전환, backward compatibility 유지 (ctx 없을 때 inline fallback)
  - main.py: `register_all_skills()` 호출 + `agent_api.init(wiki_service, chroma, storage)` 업데이트
  - api/agent.py: AgentContext 생성 + `ctx=ctx` kwarg으로 agent에 전달
  - 68개 기존 테스트 전부 통과 (regression 없음)
