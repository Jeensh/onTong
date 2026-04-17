# 세션 인계 문서 (HANDOFF)

> 다른 환경에서 이어서 작업할 때 Claude가 가장 먼저 읽어야 하는 파일.
> 사용자가 "이어서 하자"라고 하면: 이 문서 → `CHANGES.md`의 `[ ]` → `TODO.md` 순으로 확인.
> 이 문서는 `~/.claude/`의 메모리/플랜이 따라오지 않는 환경(다른 컴퓨터로 디렉토리 복사 등)을 위한 백업.

마지막 업데이트: 2026-04-17 (Image Management 구현 완료)

---

## 1. 다음 세션 첫 작업

### Image Management 브라우저 데모 테스트 (예정)

사용자가 데모 테스트 시나리오를 요청할 예정. `toClaude/modeling/demo_guide.md`의 "Image Management" 섹션 참고.
서버 기동 후 브라우저에서 다음을 검증:
1. 이미지 클릭 → 뷰어 모달 (풀스크린 + 정보 패널)
2. 어노테이션 편집 (사각형/타원/화살표/텍스트) → 새 이미지로 저장
3. 이미지 우클릭 → "이미지 복사" → 클립보드 동작
4. 설정 → "이미지 관리" → 갤러리 페이지 (페이지네이션, 필터, 검색, 일괄삭제)
5. 해시 dedup: 같은 이미지 두 번 업로드 → `deduplicated: true`

### Image Management System 구현 완료 (2026-04-17)

**브랜치**: `main` — 11 tasks, 28+32 tests (registry + analysis), TS clean.

위키 이미지 관리 시스템 (3 subsystem):
- **SHA-256 해시 중복 제거**: 업로드 시 콘텐츠 해시로 중복 방지, 12자 prefix 파일명
- **ImageRegistry**: 인메모리 hash→filename 인덱스, ref counting, 시작 시 assets/ 스캔
- **어노테이션 편집기**: fabric.js 캔버스 (사각형/타원/화살표/텍스트), OCR 상속
- **관리자 갤러리**: 페이지네이션, 필터(전체/사용중/미사용/파생본), 검색, 일괄삭제
- **이미지 복사**: Ctrl+C + 우클릭 컨텍스트 메뉴 → 클립보드 복사
- **이벤트 기반 ref tracking**: 문서 저장 시 diff, 삭제 시 정리

**백엔드 신규**: `backend/application/image/image_registry.py`
**백엔드 변경**: `files.py` (dedup+admin API), `main.py` (registry init), `wiki_service.py` (ref tracking), `models.py` (source field)
**프론트엔드 신규**: `ImageViewerModal.tsx`, `ImageManagementPage.tsx`
**프론트엔드 변경**: `pasteHandler.ts` (ImageCopyExtension), `MarkdownEditor.tsx` (click-to-view), `workspace.ts`/`useWorkspaceStore.ts`/`FileRouter.tsx`/`TreeNav.tsx` (routing)
**설계 문서**: `docs/superpowers/specs/2026-04-17-image-management-design.md`
**구현 플랜**: `docs/superpowers/plans/2026-04-17-image-management.md`

**다음 후보**: 브라우저 UI 검증 (이미지 클릭→뷰어, 어노테이션, 갤러리 페이지)

### Image Search 구현 완료 (2026-04-17)

**브랜치**: `main` — 11 commits, 30 tests, 코드 리뷰 + 4건 수정 완료.

위키 이미지 검색 가능화 파이프라인:
- **OCR Engine**: EasyOCR (한국어+영어, lazy init, asyncio.to_thread)
- **Vision Provider**: 프로토콜 기반 (noop/ollama/openai), 기본값 none (OCR only)
- **Sidecar .meta.json**: 이미지별 분석 결과 캐시, mtime 비교로 재처리 판단
- **Indexer Integration**: `enrich_chunk_with_images()` → `![](assets/...)` → `[이미지: 설명]` 치환
- **Background Processing**: 문서 저장 시 asyncio.create_task로 비동기 분석 + 재인덱싱
- **Backfill CLI**: `python -m backend.cli.backfill_images` (--dry-run/--ocr-only/--vision-only/--reprocess/--workers N)
- **병렬 처리**: asyncio.Semaphore + gather (max_concurrent)

**신규 파일**: `backend/application/image/` (models, ocr_engine, vision_provider, analyzer, queue), `backend/cli/backfill_images.py`, `tests/test_image_analysis.py`
**변경 파일**: `config.py` (8 settings), `wiki_indexer.py` (enrichment), `wiki_service.py` (bg processing), `main.py` (pipeline init)
**설계 문서**: `docs/superpowers/specs/2026-04-16-image-search-design.md`
**구현 플랜**: `docs/superpowers/plans/2026-04-16-image-search-plan.md`

**다음 후보**: 실제 이미지로 backfill 테스트, Ollama Vision 연동 테스트, 브라우저 UI 검증

### Phase 2a: Source Viewer + Mapping Workbench 완료 (2026-04-16, design review 수정 2026-04-17)

**브랜치**: `main` — 14 source API tests, TS clean, design review 완료.

코드-도메인 매핑 워크벤치 구현:
- **Source API**: 파일 트리 + 파일 내용 + 엔티티 위치 조회 (path traversal/symlink 방어)
- **SourceViewer**: 파일 트리 + Monaco read-only 에디터 + 엔티티 gutter marker
- **MappingCanvas**: React Flow 도메인 온톨로지 그래프 + 엔티티 패널 + 드래그-드롭 매핑 + fitView 자동 적용
- **MappingWorkbench**: 55/45 분할 패널 + 캔버스↔뷰어 양방향 연동
- **ModelingSection**: "매핑 워크벤치" 사이드바 탭 추가
- **Seed API 수정**: 소스 파일 자동 복사 (데모 시 수동 복사 불필요)

**설계 문서**: `docs/superpowers/specs/2026-04-16-source-viewer-mapping-workbench-design.md`
**구현 플랜**: `docs/superpowers/plans/2026-04-16-source-viewer-mapping-workbench.md`
**데모 가이드**: `toClaude/modeling/demo_guide_modeling.md` (Part A: Engine, Part B: Workbench)

**다음 후보**: Phase 1b (실제 Neo4j BFS 의존성 그래프), Docker Sandbox (독립 기능)

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

---

## 2. 이전 완료 작업

2026-04-13 이전 완료 작업 상세:
- `toClaude/modeling/CHANGES.md` — 타임스탬프순 변경 로그
- `toClaude/modeling/archive/` — 스텝별 요약 (Modeling MVP, Self-Healing, Trust System, Part 1/2/3, Path-Aware RAG, Smart Friction 등)

---

## 3. 환경/실행 방법

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

## 4. 핵심 파일 맵 (변경된 주요 파일)

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

## 5. 사용자 작업 스타일 (메모리 백업)

- **언어**: 사용자 응답은 한국어, 코드/내부 추론은 영어
- **승인 워크플로우**: 각 작업 단위마다 요구사항 질의 → 승인 → 실행. 플랜 승인 후에도 착수 전 확인.
- **데모 검증 필수**: pytest/TS 빌드만으로 데모 넘기지 말 것. 반드시 서버 띄워서 직접 테스트.
- **에이전트 변경 시**: 실제 RAG 채팅 테스트(ChromaDB+백엔드) 포함
- **문서 동기화**: 중간 추가 요청도 TODO/CHANGES/demo_guide에 즉시 반영
- **단계 완료 정의**: 코드 + 검증 + summary + demo_guide + TODO 체크 + memory + 보고. 7개 모두 완료해야 단계 끝.
- **LLM Rate**: API 키 테스트는 최소한으로
