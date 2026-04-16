# 세션 인계 문서 (HANDOFF)

> 다른 환경에서 이어서 작업할 때 Claude가 가장 먼저 읽어야 하는 파일.
> 사용자가 "이어서 하자"라고 하면: 이 문서 → `CHANGES.md`의 `[ ]` → `TODO.md` 순으로 확인.
> 이 문서는 `~/.claude/`의 메모리/플랜이 따라오지 않는 환경(다른 컴퓨터로 디렉토리 복사 등)을 위한 백업.

마지막 업데이트: 2026-04-16

---

## 1. 다음 세션 첫 작업

### Phase 2a: Source Viewer + Mapping Workbench 완료 (2026-04-16)

**브랜치**: `main` — 10 commits, 14 source API tests, TS clean.

코드-도메인 매핑 워크벤치 구현:
- **Source API**: 파일 트리 + 파일 내용 + 엔티티 위치 조회 (path traversal/symlink 방어)
- **SourceViewer**: 파일 트리 + Monaco read-only 에디터 + 엔티티 gutter marker
- **MappingCanvas**: React Flow 도메인 온톨로지 그래프 + 엔티티 패널 + 드래그-드롭 매핑
- **MappingWorkbench**: 55/45 분할 패널 + 캔버스↔뷰어 양방향 연동
- **ModelingSection**: "매핑 워크벤치" 사이드바 탭 추가

**설계 문서**: `docs/superpowers/specs/2026-04-16-source-viewer-mapping-workbench-design.md`
**구현 플랜**: `docs/superpowers/plans/2026-04-16-source-viewer-mapping-workbench.md`

**다음 후보**: 브라우저 UI 검증, Docker Sandbox (독립 기능), Phase 1b (실제 Neo4j BFS)

### Section 2 Modeling Engine Phase 1a 완료 (2026-04-16)

**브랜치**: `main` — 11 commits, 28 tests, TS clean, UI + API 검증 완료.

Engine-First Architecture로 Section 2 리디자인:
- **분석 콘솔**: 한국어 자연어 입력 → 코드 엔티티 resolve → 영향 프로세스 분석
- **시뮬레이션 패널**: 파라미터 슬라이더 → before/after 비교 (9개 SCM 데모 엔티티)
- **Term Resolution Chain**: Korean alias(30개) → fuzzy match(0.55) → LLM fallback
- **사이드바 구조 변경**: "분석 콘솔" 기본 탭, "설정" 구분선으로 기존 탭 분리

**백엔드 신규 파일:**
- `backend/modeling/simulation/sim_models.py` — ParametricSimResult 외 4 모델
- `backend/modeling/query/term_resolver.py` — Korean alias + fuzzy + LLM
- `backend/modeling/simulation/sim_registry.py` — 9 엔티티 × calc functions
- `backend/modeling/simulation/sim_engine.py` — 시뮬레이션 + BFS 영향 추적
- `backend/modeling/api/engine_api.py` — /engine/query, /simulate, /params, /status

**프론트엔드 신규/변경:**
- `frontend/src/components/sections/modeling/AnalysisConsole.tsx` (NEW)
- `frontend/src/components/sections/modeling/SimulationPanel.tsx` (NEW)
- `frontend/src/components/sections/ModelingSection.tsx` (restructured)
- `frontend/src/lib/api/modeling.ts` (extended)

**설계 문서**: `~/.gstack/projects/Jeensh-onTong/donghae-main-design-20260415-213837.md`
**구현 플랜**: `docs/superpowers/plans/2026-04-15-modeling-engine-phase1a.md`

**다음 후보**: Phase 1b (실제 Neo4j BFS 의존성 그래프 기반 affected_processes), Phase 2 (코드 편집 샌드박스)

### ACL Domain Scoping 완료 (2026-04-14)

**브랜치**: `feat/acl-domain-scoping` — 16 commits, 100 tests, TS clean, E2E 검증 완료.

기업용 ACL 시스템으로 전환 완료:
- **ACL Store v2**: default-deny, owner/manage, 폴더 상속, 개인 공간(@username/), thread-safe
- **Multi-user Auth**: X-User-Id 헤더 기반, users.json, 그룹 해석
- **ChromaDB Access Scope**: access_read/access_write 메타데이터 → 검색/RAG/충돌감지 사전 필터링
- **Group CRUD + ACL API**: 그룹 관리, ACL 설정, manage 권한 체크
- **Frontend**: TreeNav 섹션 구조(내 문서/위키/스킬), ShareDialog, PropertiesPanel, ContextMenu, useAuth
- **Migration**: `scripts/migrate_acl.py` (기존 위키 폴더 초기 ACL + 개인 공간 생성)

**⚠️ 다음 작업 전 확인**:
1. `feat/acl-domain-scoping` 브랜치를 main에 merge할지 결정
2. 마이그레이션 실행 여부 확인 (`python scripts/migrate_acl.py`)
3. reindex로 ChromaDB access_scope 반영 (`curl -X POST http://localhost:8001/api/wiki/reindex`)

**Part 3 완료** (2026-04-15):
- 3A: require_admin (reindex) + require_write (create/move/delete folder/file) ✅
- 3B: 스킬 CRUD 권한 (personal=본인, shared delete=admin) ✅
- 3C: 프론트엔드 UI 분기 (메뉴 숨김 + "편집 권한 없습니다" 읽기전용 배너) ✅

**Part 2 완료** (2026-04-15): 2A~2C 기존 구현 확인, 2D 충돌 쌍 그룹핑 신규 구현.

**다음 후보 작업**: 사용자 논의 필요 (Part 2+3 모두 완료, ACL 기능 전체 구현 완료)

### Section 2 Modeling MVP 완료 (2026-04-12)

**Section 1 (Wiki)**: P1~P5 + Skill System + Pydantic AI + Status/Lineage Overhaul + Agent 고도화 전체 완료.

**Section 2 (Modeling)**: MVP 전체 구현 완료. 18 tasks, 69 tests, 코드 리뷰 + 보안 수정 완료.
- **백엔드**: `backend/modeling/` — Neo4j 인프라, tree-sitter Java 파서, 코드 그래프, SCOR+ISA-95 온톨로지, 매핑 엔진 (YAML+상속), 결정론적 영향분석 쿼리 엔진, 변경 감지, 승인 워크플로우, FastAPI 엔드포인트
- **프론트엔드**: `frontend/src/components/sections/modeling/` — CodeGraphViewer, DomainOntologyEditor, MappingSplitView, ImpactQueryPanel, ApprovalList
- **테스트**: 12 test files, 69 tests (unit + integration + e2e), all pass
- **설계 문서**: `docs/superpowers/specs/2026-04-12-section2-modeling-design.md`
- **구현 플랜**: `docs/superpowers/plans/2026-04-12-section2-modeling-mvp.md`
- **Section 격리**: `backend/modeling/`은 `backend/application/` (Wiki)와 완전 격리. import 없음.
- **다음 Phase**: Phase 2 (코드 편집 + 샌드박스), Phase 3 (데이터 통합), Phase 4 (다언어 파서)

**Section 3 (Simulation)**: 스캐폴딩만 완료. Section 2 Phase 2와 함께 구현 예정.

### 2026-04-12 버그 수정 (Lineage)
- **P2-FIX1**: VersionTimeline에 `wiki:lineage-changed` 이벤트 리스너 추가 — 폐기 되돌리기 후 타임라인 자동 갱신
- **P2-FIX2**: `_clear_stale_lineage_refs()`에서 MetadataIndex 갱신 누락 수정 — version-chain API stale 데이터 버그 해결

### Status Simplification + Lineage/Versioning Overhaul — 전 Phase 완료 (2026-04-11)

**8 Phase 모두 구현 완료, 67개 테스트 통과, TS 빌드 클린.**

| Phase | 내용 | 테스트 |
|-------|------|--------|
| 1 | Status 단순화 (draft/approved/deprecated만) + approved 자동강등 | 18 pass |
| 2 | Scoring 업데이트 (review=70, unset=50 제거) | Phase 1 테스트에 포함 |
| 3 | MetadataIndex 역참조 인덱스 (supersedes/related/status) | 17 pass |
| 4 | Lineage 검증 (자기참조, 사이클, 경쟁 대체, 무후계 폐기) | 14 pass |
| 5 | Deprecation 연쇄 (충돌 자동 해결, deprecated 제외, 0건 폴백) | 6 pass |
| 6 | Version Chain API + VersionTimeline UI | 5 pass |
| 7 | Reference Integrity + TreeNav deprecated 스타일 + statuses API | 7 pass |
| 8 | Metadata Inheritance + Bulk Status API | API 코드 완료 |

### User-Driven Self-Healing System — 4 Phase 전체 완료

**Phase A 완료** (16 tests): MetadataIndex 확장, backlink/owner 버그 수정, 사용자 ID 연결
**Phase B 완료** (12 tests): FeedbackTracker, POST/GET feedback API, TrustBanner 버튼, AICopilot thumbs
**Phase C 완료** (20 tests): 가중치 재조정 (user_feedback 15%), 피드백→점수 반영, "확인했음"→freshness 갱신
**Phase D 완료** (22 tests): Relationship 모델, GraphStore (InMemory+Redis), GraphBuilder (related/supersedes/conflicts), Graph API

**이전 완료**:
1. **Phase 1**: Document Confidence Score (5-시그널, 0-100)
2. **Phase 2**: Write-Time Related Document Nudge (관련 문서 사이드바)
3. **Phase 3**: Read-Time Trust Context (TrustBanner, CitationTracker, NewerAlternatives)
4. **Phase 4**: Smart Conflict Resolution (유형 분류, 해결 액션, 다이제스트)

### (완료) Trust System Phase 2 — 작성 시 넛지
- `GET /api/search/related` API (HNSW + 신뢰도 복합 랭킹)
- LinkedDocsPanel "참고할 만한 문서" 섹션 (Sparkles + dot + 유사도%)
- 저장 시 자동 `related` 메타데이터 제안 (sim > 0.7, 최대 3건)
- 12개 테스트 통과

### (완료) Trust System Phase 1 — 문서 신뢰도 점수
- 5-시그널 가중 합산 → 0-100 점수, tier(high/medium/low), stale 플래그
- API: `/api/wiki/confidence/{path}`, `/api/wiki/confidence-batch`
- RAG mild boost, FE 소스 dot + 에디터 pill
- 28개 테스트 통과

### Step 1 — 태그 품질 시스템 브라우저 검증 (코드 완료, UI 확인만 남음)

1. **Smart Friction**
   - 아무 문서 열기 → MetadataTagBar의 태그 입력란에 `캐싱` 입력 후 Enter
   - 기대: "유사한 태그가 있습니다: 캐시 (1건)" 프롬프트 표시 → "캐시 사용" / "그래도 생성" 선택
2. **태그 건강도 대시보드**
   - MetadataTemplateEditor 열기 → 하단 "태그 건강도" 섹션 → "분석 실행"
   - 기대: 4개 그룹 표시
     - 정책 ↔ 보안정책 (0.33)
     - 장애대응 ↔ 장애처리 (0.39)
     - Redis ↔ cache (0.43)
     - 캐싱 ↔ 캐시 (0.52)
   - 각 그룹의 병합 버튼 동작 확인
3. **건수 표시 자동완성**
   - TagInput에 검색어 입력 → 드롭다운에 `태그명  N건` 형식으로 표시되는지

검증 OK면 → Step 2

### Step 2 — Part 2 (충돌 & Lineage) 착수

플랜 원본은 `~/.claude/plans/wiggly-sauteeing-lobster.md` (다른 컴퓨터에는 없음 — 아래 7번 섹션의 요약 사용).

순서: 2A 사이클 감지 → 2C deprecated 뱃지 → 2B 폐기 되돌리기 → 2D 쌍 그룹핑

---

## 2. 마지막 작업 (2026-04-09)

**세션 37 — Path-Aware RAG + 대화형 경로 명확화** 4-Layer 구현 완료.

| Layer | 내용 | 핵심 파일 |
|-------|------|----------|
| L1 | 모든 청크에 `[분류: X > Y] [문서: Z]` 프리픽스 임베딩 | `wiki_indexer.py` |
| L2 | `path_depth_1/2/stem` 메타데이터 + `extract_path_filter()` | `wiki_indexer.py`, `filter_extractor.py`, `wiki_search.py` |
| L3 | 경로 분산 감지 → ClarificationRequest → 세션 path_preferences 누적 | `rag_agent.py`, `session.py`, `context.py`, `api/agent.py` |
| L4 | 세션 경로 선호도 recency-decay 부스트 리랭크 | `rag_agent.py` |

재인덱싱 완료 (172 chunks). 기존 RAG 12쿼리 회귀 통과. 사용자 브라우저 데모 검증 완료.

환경변수 토글: `ONTONG_PATH_EMBED_ENABLED`, `ONTONG_PATH_FILTER_ENABLED`, `ONTONG_PATH_DISAMBIG_ENABLED`, `ONTONG_PATH_DISAMBIG_MIN_PATHS`, `ONTONG_PATH_DISAMBIG_DOMINANCE`, `ONTONG_PATH_BOOST_WEIGHT`.

---

## 3. 이전 작업 (2026-04-07)

**Smart Friction 레이턴시 최적화** — `/tags/similar`의 560ms OpenAI 임베딩 왕복이 Enter 체감 지연의 원인. TagInput에서 디바운스된 search 콜백과 함께 `onCheckSimilar`를 백그라운드 선제 호출 → `similarCacheRef`에 저장. 사용자가 드롭다운 보는 동안 워밍되어 Enter 시점엔 캐시 히트 → 체감 0ms. LRU 50개 제한(Map 삽입 순서 기반)으로 메모리 누수 방지. 파일: `frontend/src/components/editors/metadata/TagInput.tsx`.

**임베딩 임계값 교정** — OpenAI text-embedding-3-small이 짧은 한국어 태그에서 예상보다 큰 cosine distance를 만들어 모든 임계값을 실측 기반으로 상향 조정.

| 용도 | 이전 | 이후 | 파일 |
|------|------|------|------|
| 자동치환 (LLM 없이) | 0.08 | **0.35** | `backend/application/metadata/metadata_service.py` |
| LLM 확인 요청 | 0.20 | **0.55** | `backend/application/metadata/metadata_service.py` |
| 유사 태그 API 필터 | 0.25 | **0.60** | `backend/api/metadata.py` (`/tags/similar`) |
| 유사 그룹 기본값 | 0.20 | **0.55** | `backend/application/metadata/tag_registry.py`, `backend/api/metadata.py` |

**검증된 유사 태그 거리 (curl 실측):**
- 정책 ↔ 보안정책: 0.33
- 장애대응 ↔ 장애처리: 0.39
- Redis ↔ cache: 0.43
- 캐싱 ↔ 캐시: 0.52

API 호출로 4그룹 모두 정상 검출 확인됨. 브라우저 UI 검증만 남음.

---

## 3. Part 1 (메타데이터 & Auto-tagging) — 전체 완료

- Domain-Process 계층 구조 (flat → cascade)
- 백엔드 CRUD API + 프론트엔드 cascade UI
- 위키 클린업 + 7도메인 21개 샘플 문서
- filter_extractor / metadata_service 동적 키워드/프롬프트
- AutoTagButton confidence (3단계 색상)
- 메타데이터 validation (soft warning)
- related 문서 편집 UI + lineage 읽기전용
- Bulk auto-tag API + UntaggedDashboard
- Materialized index + 역인덱스 + lazy loading (10만 문서 스케일 대비)
- MetadataTemplateEditor 트리 구조 (Domain→Process→Files)
- **태그 품질 시스템** (3-Layer 방어):
  - Layer 1: 프롬프트에 기존 태그 상위 100개 주입
  - Layer 2: ChromaDB tag_registry 임베딩 + LLM 확인
  - Layer 3: Smart Friction UI + 건수 자동완성 + 유사 그룹 대시보드 + 태그 병합/고아 태그

---

## 4. Part 2 (충돌 & Lineage) — ✅ 완료 (2026-04-15)

### 2A. Lineage 사이클 감지 (~5줄)
**파일**: `backend/application/agent/rag_agent.py` (`_resolve_superseded_chain`, ~line 1475)
- `visited: set` 추가, 재방문 시 break + warning 로그

### 2B. 폐기 되돌리기 (Undo Deprecate)
**Backend**: `backend/api/conflict.py`
- `POST /api/conflict/undeprecate?path=X` 추가
  - status를 "approved"로 복원, superseded_by 클리어
  - counterpart의 supersedes도 클리어, ChromaDB 재인덱싱
**Frontend**: `frontend/src/components/editors/ConflictDashboard.tsx`
- resolved 필터에서 deprecated 문서 옆 "되돌리기" 버튼

### 2C. 검색 결과 deprecated 뱃지
**Backend**: `backend/application/agent/rag_agent.py` sources 생성부에 `status`, `superseded_by` 필드 추가
**Frontend**: `frontend/src/components/AICopilot.tsx` SourceItem 렌더링부에 빨간 "폐기됨" 뱃지 + 새 버전 링크

### 2D. 충돌 쌍 체인 중복 제거
**파일**: `backend/application/conflict/conflict_service.py` (`get_pairs`)
- 같은 file_a를 공유하는 쌍을 그룹핑하여 "A와 충돌: [B, C]" 형태로 반환
- 프론트엔드 ConflictDashboard에서 그룹 렌더링

---

## 5. Part 3 (권한 관리) — ✅ 완료 (2026-04-15)

### 3A. 미보호 엔드포인트 권한 추가
**파일**: `backend/api/wiki.py`
- `create_folder`, `move_folder`, `delete_folder`, `move_file` → `Depends(require_write)`
- `reindex`, `reindex_file`, `reindex_pending` → `require_admin` (NEW)
**파일**: `backend/core/auth/permission.py`
- `require_admin` 추가: `user.roles`에 "admin" 있는지 확인

### 3B. 스킬 CRUD 권한
**파일**: `backend/api/skill.py`
- personal 스킬: 본인만 (`@username` 확인)
- shared 스킬: `require_write`
- 삭제: 본인 or admin

### 3C. 프론트엔드 권한 기반 UI 분기
**파일**: `frontend/src/components/TreeNav.tsx`
- `useAuth()` 훅으로 roles 확인 → editor/admin이 아니면 삭제/이동/생성 메뉴 숨김
**파일**: `frontend/src/components/editors/MarkdownEditor.tsx` (또는 관련)
- write 권한 없으면 읽기 전용 모드 + "편집 권한 없음" 안내

---

## 6. 환경/실행 방법

```bash
# 의존성
docker compose up -d chroma redis

# 백엔드 (반드시 .env 로드 — OPENAI_API_KEY 없으면 tag_registry 임베딩 실패)
source venv/bin/activate
set -a && source .env && set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8001

# 프론트엔드
cd frontend && npm run dev
```

**중요한 주의사항:**
- Python 3.13에서는 onnxruntime 미지원 → 기본 ChromaDB 임베딩 안 됨 → **OPENAI_API_KEY 필수**
- 백엔드 포트는 **8001** (8000은 ChromaDB)
- tag_registry는 서버 시작 시 metadata_index에서 자동 동기화. 새 환경에서는 한번 reindex 필요할 수 있음.

---

## 7. 핵심 파일 맵 (변경된 주요 파일)

### Backend
- `backend/main.py` — 시작 시 tag_registry 초기화 + 동기화
- `backend/application/metadata/metadata_index.py` — 역인덱스, paginated API
- `backend/application/metadata/tag_registry.py` — ChromaDB 기반 의미 태그 저장소 (NEW)
- `backend/application/metadata/metadata_service.py` — 3-Layer 정규화 (프롬프트 + 임베딩 + LLM)
- `backend/api/metadata.py` — Bulk suggest, similar/groups/orphans/merge 엔드포인트

### Frontend
- `frontend/src/components/TreeNav.tsx` — 사이드바 트리 + 페이지네이션
- `frontend/src/components/editors/MetadataTemplateEditor.tsx` — 트리 구조 + 태그 건강도 대시보드
- `frontend/src/components/editors/metadata/TagInput.tsx` — Smart Friction + 건수 표시
- `frontend/src/components/editors/metadata/MetadataTagBar.tsx` — onSearchWithCount/onCheckSimilar 연동
- `frontend/src/components/editors/UntaggedDashboard.tsx` — bulk API 연동
- `frontend/src/lib/api/metadata.ts` — searchTagsWithCount, checkSimilarTags

### 테스트 샘플 파일 (의도적으로 분산된 태그)
- `wiki/인프라/캐시-장애-대응-매뉴얼.md` (캐시, Redis, 장애대응)
- `wiki/인프라/캐싱-전략-가이드.md` (캐싱, 성능최적화, 가이드)
- `wiki/인프라/cache-troubleshooting.md` (cache, troubleshooting, 레디스)
- `wiki/인프라/서버-장애처리-절차.md` (장애처리, 서버, SOP)
- `wiki/인프라/네트워크-보안-정책.md` (네트워크, 보안정책, 방화벽)
- `wiki/SCM/재고-실사-절차.md` (재고관리, 실사, 희귀태그테스트 — orphan)

---

## 8. 사용자 작업 스타일 (메모리 백업)

- **언어**: 사용자 응답은 한국어, 코드/내부 추론은 영어
- **승인 워크플로우**: 각 작업 단위마다 요구사항 질의 → 승인 → 실행. 플랜 승인 후에도 착수 전 확인.
- **데모 검증 필수**: pytest/TS 빌드만으로 데모 넘기지 말 것. 반드시 서버 띄워서 직접 테스트.
- **에이전트 변경 시**: 실제 RAG 채팅 테스트(ChromaDB+백엔드) 포함
- **문서 동기화**: 중간 추가 요청도 TODO/CHANGES/demo_guide에 즉시 반영
- **단계 완료 정의**: 코드 + 검증 + summary + demo_guide + TODO 체크 + memory + 보고. 7개 모두 완료해야 단계 끝.
- **LLM Rate**: API 키 테스트는 최소한으로
