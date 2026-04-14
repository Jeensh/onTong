# onTong — Phase 1 실행 TodoList (v2)

> 기반 문서: `plan/master_plan.md`
> 최종 갱신: 2025-03-25 (전문가 검토 반영)
> 사용법: 각 단계를 순서대로 Claude에게 지시. 완료 시 `[x]`로 체크.

---

## 의존 관계 범례

```
→  : 선행 Task 완료 후 착수 가능
//  : 병렬 진행 가능
⚠️ : 백엔드 미구현 — 프론트엔드보다 먼저 작업 필요
```

---

## Step 0: 프론트엔드 환경 세팅

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 0-1 | Next.js 프로젝트 초기화 (Next.js 15 + Node 20 via nvm) | - | 10m | [x] | `frontend/` |
| 0-2 | shadcn/ui 설치 + 컴포넌트 추가 (Command, Badge, Button, Select, DropdownMenu, Popover, Dialog, Sonner) | 0-1 | 15m | [x] | `components/ui/` |
| 0-3 | Zustand, @dnd-kit/core, @dnd-kit/sortable 설치 | 0-1 | 5m | [x] | `package.json` |
| 0-4 | Next.js → 백엔드 API 프록시 설정 (`next.config.ts` rewrites → `localhost:8001`) | 0-1 | 10m | [x] | `next.config.ts` |
| 0-5 | 공통 TypeScript 타입 정의 — 백엔드 `schemas.py`와 1:1 매칭 | 0-1 | 20m | [x] | `src/types/` |

**완료 기준**: `npm run dev` → 빈 앱 기동 + `curl localhost:3000/api/wiki/tree`가 백엔드 JSON 반환

---

## Step 1-A: Tab Workspace 기반 레이아웃

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1A-1 | 3-Pane 메인 레이아웃 (TreeNav \| Workspace \| AICopilot) — 리사이즈 가능 패널 | Step 0 | 40m | [x] | `app/page.tsx` |
| 1A-2 | Zustand 탭 상태 스토어 (`openTab`, `closeTab`, `setActiveTab`, `reorderTabs`) | Step 0 | 30m | [x] | `lib/workspace/useWorkspaceStore.ts` |
| 1A-3 | TabBar 컴포넌트 (열기/닫기, ● dirty, 드래그 정렬 @dnd-kit) | 1A-2 | 40m | [x] | `components/workspace/TabBar.tsx` |
| 1A-4 | WorkspacePanel 컴포넌트 (활성 탭 콘텐츠 렌더링 + 빈 상태) | 1A-2 | 20m | [x] | `components/workspace/WorkspacePanel.tsx` |
| 1A-5 | FileRouter 컴포넌트 (확장자 기반 분기 — MD만 실제, 나머지 placeholder) | 1A-4 | 20m | [x] | `components/workspace/FileRouter.tsx` |
| 1A-6 | TreeNav 컴포넌트 (`GET /api/wiki/tree` → 트리 렌더링 → 클릭 시 탭 열기) | 1A-1, 1A-2 | 40m | [x] | `components/TreeNav.tsx` |
| 1A-7 | TreeNav 파일 생성 (+ 버튼 → 인라인 파일명 입력 → PUT API → 트리 새로고침 + 탭 열기) | 1A-6 | 30m | [x] | `components/TreeNav.tsx` |
| 1A-8 | TreeNav 파일 삭제 (우클릭 컨텍스트 메뉴 → DELETE API → 트리 새로고침 + 탭 닫기) | 1A-6 | 30m | [x] | `components/TreeNav.tsx` |
| 1A-9 | TreeNav 새로고침 버튼 | 1A-6 | 5m | [x] | `components/TreeNav.tsx` |
| 1A-10 | 폴더 생성 (헤더 버튼 + 폴더 우클릭 → 새 폴더, 백엔드 POST /api/wiki/folder API 포함) | 1A-6 | 40m | [x] | `TreeNav.tsx`, `wiki.py`, `local_fs.py` |
| 1A-11 | 폴더 삭제 (우클릭 → 삭제, 빈 폴더만 허용, 백엔드 DELETE /api/wiki/folder API 포함) | 1A-6 | 30m | [x] | `TreeNav.tsx`, `wiki.py`, `local_fs.py` |
| 1A-12 | 폴더 내 파일/하위폴더 생성 (폴더 우클릭 → 새 문서/새 폴더, 인라인 입력) | 1A-10 | 20m | [x] | `TreeNav.tsx` |
| 1A-13 | 드래그앤드롭 이동 (@dnd-kit, DragOverlay, RootDropZone, 폴더 hover 자동 확장) | 1A-6 | 60m | [x] | `TreeNav.tsx` |
| 1A-14 | 이름 변경 (우클릭 → InlineInput 인라인 편집, .md 자동 추가, 열린 탭 경로 업데이트) | 1A-6 | 30m | [x] | `TreeNav.tsx`, `useWorkspaceStore.ts` |

**완료 기준**: Tree 파일 클릭 → 탭 생성 → 탭 전환 → 탭 닫기 → 빈 상태 표시

---

## Step 1-B: Markdown Editor (Tiptap)

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1B-1 | Tiptap 패키지 설치 (`@tiptap/react`, `starter-kit`, table, image, task-list, placeholder) | Step 0 | 10m | [x] | `package.json` |
| 1B-2 | MarkdownEditor 기본 — Tiptap + StarterKit + TableKit + Image + TaskList | 1B-1, 1A-5 | 60m | [x] | `editors/MarkdownEditor.tsx` |
| 1B-3 | WYSIWYG ↔ 소스 모드 토글 | 1B-2 | 40m | [x] | MarkdownEditor 내 |
| 1B-4 | 슬래시 명령어 (`/`) 커스텀 extension — 빈 줄 시작에서만 트리거, Escape 닫기 | 1B-2 | 60m | [x] | `lib/tiptap/slashCommand.ts` |
| 1B-5 | 저장: debounce 자동 저장 + Ctrl+S → `PUT /api/wiki/{path}` | 1B-2 | 30m | [x] | MarkdownEditor 내 |
| 1B-6 | 파일 열기: 탭 활성화 시 `GET /api/wiki/file/{path}` → 에디터 로드 | 1B-2 | 20m | [x] | MarkdownEditor 내 |

**완료 기준**: `.md` 클릭 → 에디터 로드 → WYSIWYG 편집 → Ctrl+S 저장 → 새로고침 후 유지 확인

---

## Step 1-C: 클립보드 붙여넣기

> ⚠️ **1C-5 (백엔드)를 먼저 구현해야** 1C-3, 1C-4 (프론트엔드 이미지 붙여넣기)를 테스트할 수 있음

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1C-5 | ⚠️ 백엔드: `POST /api/files/upload/image` + `main.py` 라우터 등록 (wiki/assets/에 저장, 경로 반환) | - | 40m | [x] | `backend/api/files.py`, `main.py` |
| 1C-1 | HTML 테이블 → Tiptap Table 노드 변환 유틸 | 1B-2 | 30m | [x] | `lib/clipboard/tableConverter.ts` |
| 1C-2 | Tiptap paste handler: `text/html` 테이블 감지 시 Table 노드 삽입 | 1C-1 | 30m | [x] | `lib/tiptap/pasteHandler.ts` |
| 1C-3 | 이미지 붙여넣기: `image/*` blob → `POST /api/files/upload/image` → `![](path)` | **1C-5** → 1B-2 | 40m | [x] | `lib/clipboard/imagePaste.ts` |
| 1C-4 | 이미지 드래그 앤 드롭 (동일 업로드 흐름) | **1C-5** → 1B-2 | 20m | [x] | MarkdownEditor 내 |

**완료 기준**: Excel 표 복사→붙여넣기→테이블 생성 / 스크린샷 Ctrl+V→이미지 업로드+삽입

---

## Step 1-D: Multi-Format 뷰어

> ⚠️ **1D-1, 1D-2 (백엔드)를 먼저 구현해야** 프론트엔드 뷰어를 테스트할 수 있음
> 💡 **MVP 전략**: Phase 1에서는 **Excel(읽기+수정) + 이미지 뷰어**를 우선 구현.
> PPT, PDF는 Phase 1.5로 분리 가능 (데모 영향 낮음).

| # | Task | 의존 | 시간 | 우선순위 | 상태 | 산출물 |
|---|------|------|------|----------|------|--------|
| 1D-1 | ⚠️ 백엔드: `GET /api/files/{path}` (바이너리 반환 + Content-Type) | 1C-5 (files.py 공유) | 30m | P1 | [x] | `backend/api/files.py` |
| 1D-2 | ⚠️ 백엔드: `PUT /api/files/{path}` (바이너리 저장, `.md` 거부) | 1D-1 | 20m | P1 | [x] | `backend/api/files.py` |
| 1D-3 | SpreadsheetViewer: Luckysheet/Univer + SheetJS `.xlsx` ↔ JSON | 1D-1 | 120m | P1 | [x] | `editors/SpreadsheetViewer.tsx` |
| 1D-4 | SpreadsheetViewer: 수정 후 저장 (`PUT /api/files/{path}`) | 1D-1, 1D-2, 1D-3 | 40m | P1 | [x] | SpreadsheetViewer 내 |
| 1D-7 | ImageViewer: `<img>` + 줌/패닝 | 1D-1 | 30m | P1 | [x] | `editors/ImageViewer.tsx` |
| 1D-5 | PresentationViewer: 백엔드 python-pptx JSON 파싱 + 프론트 HTML 렌더링 (슬라이드 네비게이션, 키보드 조작, Bold/Italic/Color/Image 지원) | 1D-1 | 60m | P1.5 | [x] | `editors/PresentationViewer.tsx`, `api/files.py` |
| 1D-6 | PdfViewer: react-pdf (페이지 네비게이션, 줌, 50페이지 이상 시 페이지네이션) | 1D-1 | 60m | P1.5 | [x] | `editors/PdfViewer.tsx` |
| 1D-8 | FileRouter placeholder 제거 → 실제 뷰어 연결 | 1D-3~7 | 15m | P1 | [x] | FileRouter.tsx |

**P1 완료 기준**: `.xlsx` 열기+수정+저장, 이미지 줌/패닝
**P1.5 완료 기준**: `.pptx` 슬라이드 보기, `.pdf` 페이지 넘기기

---

## Step 1-E: Metadata Tagging Pipeline

> ⚠️ **백엔드 Task는 반드시 순서대로 (직렬)** 진행해야 함.
> 프론트엔드 Task는 백엔드 완료 후 착수.

### 1-E 백엔드 (직렬 — B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8 → B9)

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1E-B1 | `schemas.py`: `DocumentMetadata` 추가, `WikiFile`에 `metadata` + `raw_content` 필드 추가, `tags` property 호환 | - | 30m | [x] | `backend/core/schemas.py` |
| 1E-B2 | `local_fs.py`: `_parse_frontmatter()` 추가, `_to_wiki_file()`에서 YAML 파싱 → `WikiFile.metadata`, 기존 `#tag` 폴백 | **→ 1E-B1** | 40m | [x] | `backend/infrastructure/storage/local_fs.py` |
| 1E-B3 | `wiki_indexer.py`: `_metadata_to_chroma()` (파이프 구분자), `index_file()`에서 metadata 포함 | **→ 1E-B2** | 30m | [x] | `backend/application/wiki/wiki_indexer.py` |
| 1E-B4 | `chroma.py`: `query_with_filter(where=)` 메서드 추가 | **→ 1E-B3** | 20m | [x] | `backend/infrastructure/vectordb/chroma.py` |
| 1E-B5 | `rag_agent.py`: `metadata_filter` 파라미터 + `query_with_filter()` 사용 | **→ 1E-B4** | 20m | [x] | `backend/application/agent/rag_agent.py` |
| 1E-B6 | `metadata.py` 신규 + `main.py` 라우터 등록: `GET /api/metadata/tags` (전체 고유 목록) | **→ 1E-B2** | 40m | [x] | `backend/api/metadata.py`, `main.py` |
| 1E-B7 | `application/metadata/` 디렉토리 + `metadata_service.py`: LLM Auto-Tag (`suggest_metadata()`) | **→ 1E-B1** | 40m | [x] | `backend/application/metadata/metadata_service.py` |
| 1E-B8 | `metadata.py`에 `POST /api/metadata/suggest` 엔드포인트 추가 | **→ 1E-B7** | 20m | [x] | `backend/api/metadata.py` |
| 1E-B9 | 기존 `WikiSearchService.build_tag_index()`가 새 `WikiFile.tags` property로 정상 동작하는지 검증 | **→ 1E-B1** | 15m | [x] | 테스트 결과 |

### 1-E 프론트엔드 (백엔드 B1~B8 완료 후)

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1E-F1 | MetadataTagBar 컨테이너 (에디터 상단, 열기/접기, `.md` 파일만 표시) | **1E-B6 완료** + 1B-2 | 40m | [x] | `editors/metadata/MetadataTagBar.tsx` |
| 1E-F2 | TagInput (shadcn Command + Badge, 자동 완성 + 새 태그 생성) | 1E-F1 | 40m | [x] | `editors/metadata/TagInput.tsx` |
| 1E-F3 | DomainSelect / ProcessSelect (`GET /api/metadata/tags` 로드) | 1E-F1 | 30m | [x] | `editors/metadata/DomainSelect.tsx` |
| 1E-F4 | AutoTagButton (✨ → `POST /api/metadata/suggest` → 점선 Badge → 수락/거절) | **1E-B8 완료** + 1E-F1, 1E-F2 | 50m | [x] | `editors/metadata/AutoTagButton.tsx` |
| 1E-F5 | Frontmatter 동기화 유틸 (serialize / strip / merge) | 1E-F1 | 30m | [x] | `lib/markdown/frontmatterSync.ts` |
| 1E-F6 | MarkdownEditor + MetadataTagBar 통합 (열기 시 역직렬화, 저장 시 직렬화) | 1E-F1~F5 | 30m | [x] | MarkdownEditor.tsx 수정 |

**완료 기준**: MD 열기 → TagBar에 메타데이터 표시 → Auto-Tag → 수락 → 저장 → ChromaDB 반영

---

## Step 1-F: AI Copilot + SSE 스트리밍

> ⚠️ **1F-0 (백엔드)를 먼저 구현해야** 1F-5 (승인/거절)를 테스트할 수 있음

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 1F-0 | ⚠️ 백엔드: RAGAgent에 Wiki 수정 요청 감지 → `ApprovalRequestEvent` 발행 로직 추가 | - | 60m | [x] | `backend/application/agent/rag_agent.py` |
| 1F-1 | SSE 클라이언트 (`fetch` + `ReadableStream`, 이벤트 타입별 파싱) | Step 0 | 40m | [x] | `lib/api/sseClient.ts` |
| 1F-2 | AICopilot 채팅 UI (메시지 목록 + 입력 + 자동 스크롤) | 1A-1, 1F-1 | 50m | [x] | `components/AICopilot.tsx` |
| 1F-3 | 스트리밍 토큰 실시간 표시 (`content_delta` 처리) | 1F-2 | 20m | [x] | AICopilot 내 |
| 1F-4 | 출처 표시 (`sources` → 파일 경로 링크, 클릭 시 탭 열기) | 1F-2, 1A-2 | 30m | [x] | AICopilot 내 |
| 1F-5 | 승인/거절 UI (`approval_request` → diff 미리보기 + 버튼 → `POST /api/approval/resolve`) | **1F-0 완료** + 1F-2 | 40m | [x] | AICopilot 내 |
| 1F-6 | 에러 핸들링 (`error` 이벤트 → Sonner Toast, 서버 다운 시 재연결 안내) | 1F-2 | 15m | [x] | AICopilot 내 |
| 1F-7 | RAG 명확화 질문 (모호한 질문 시 검색 결과 기반 되물어보기 + 멀티턴 히스토리) | 1F-0 | 60m | [x] | `rag_agent.py`, `agent.py` |
| 1F-8 | 출처 관련도 필터링 (MIN_SOURCE_RELEVANCE 기반, 명확화/답변 시 threshold 분리) | 1F-4 | 30m | [x] | `rag_agent.py` |
| 1F-9 | 에이전트 세션 관리 (새 대화, 세션 목록, 전환, 삭제, 자동 제목) | 1F-2 | 60m | [x] | `AICopilot.tsx` |

**완료 기준**: 채팅 → 스트리밍 답변 + 출처 → "Wiki에 추가해줘" → 승인/거절 동작

---

## Step 4: 샘플 데이터 마이그레이션 + 통합 테스트

| # | Task | 의존 | 시간 | 상태 | 산출물 |
|---|------|------|------|------|--------|
| 4-1 | `wiki/getting-started.md`에 YAML frontmatter 추가 (`#tag` → frontmatter 이전) | 1E-B2 완료 | 15m | [x] | wiki 파일 |
| 4-2 | `wiki/order-processing-rules.md`에 YAML frontmatter 추가 | 4-1 | 15m | [x] | wiki 파일 |
| 4-3 | `wiki/kv-cache-troubleshoot.md`에 YAML frontmatter 추가 | 4-1 | 15m | [x] | wiki 파일 |
| 4-4 | `POST /api/wiki/reindex` → ChromaDB metadata 포함 여부 확인 | 4-1~3 | 15m | [x] | 테스트 결과 |
| 4-5 | E2E: TreeNav→탭→MD 편집→저장→AI 채팅→RAG 답변→출처 | 1A~1F 전체 | 30m | [x] | 테스트 결과 |
| 4-6 | E2E: Auto-Tag→추천→수락→저장→Hybrid Search 필터 검증 | 1E 전체 | 20m | [x] | 테스트 결과 |
| 4-7 | E2E: Excel 열기/수정/저장, (P1.5: PPT 뷰어, PDF 뷰어) | 1D 전체 | 20m | [x] | 테스트 결과 |
| 4-8 | E2E: 이미지 붙여넣기, 엑셀 표 붙여넣기 | 1C 전체 | 15m | [x] | 테스트 결과 |

**완료 기준**: Phase 1 데모 시나리오 전체 통과

---

## Ad-hoc: UI/인프라 개선

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| AH-1 | 사이드바 빈 공간 우클릭 → 루트 컨텍스트 메뉴 (새 문서/새 폴더) | [x] | `TreeNav.tsx` |
| AH-2 | 인증 추상화 레이어 — Backend (User, AuthProvider, NoOpProvider, deps) | [x] | `backend/core/auth/` |
| AH-3 | 인증 추상화 레이어 — 전체 API 라우터에 auth dependency 적용 | [x] | `backend/api/*.py` |
| AH-4 | 인증 추상화 레이어 — Frontend (AuthContext, useAuth, DevProvider, Providers) | [x] | `frontend/src/lib/auth/`, `Providers.tsx` |
| AH-5 | 문서 메타데이터 이력 — Backend (created/updated/created_by/updated_by 자동 주입) | [x] | `schemas.py`, `local_fs.py`, `wiki_service.py`, `wiki.py`, `approval.py` |
| AH-6 | 문서 메타데이터 이력 — ChromaDB indexer 필드 반영 | [x] | `wiki_indexer.py` |
| AH-7 | 문서 메타데이터 이력 — Frontend 타입/파서/MetadataTagBar 이력 표시 | [x] | `wiki.ts`, `frontmatterSync.ts`, `MetadataTagBar.tsx` |
| AH-8 | AI Copilot 마크다운 렌더링 (react-markdown + remark-gfm) | [x] | `AICopilot.tsx` |
| AH-9 | 저장 후 metadata 갱신 버그 수정 (서버 응답 반영) | [x] | `MarkdownEditor.tsx` |
| AH-10 | 에이전트 라우팅 고도화 — 일반 검색/질문 패턴 WIKI_QA 라우팅 | [x] | `router.py` |
| AH-11 | 에이전트 라우팅 고도화 — LLM classifier WIKI_QA 기본 폴백 | [x] | `router.py` |
| AH-12 | RAG 시스템 프롬프트 범용화 (인사/조직 등 일반 Wiki 지원) | [x] | `rag_agent.py` |
| AH-13 | Clarity check 조건 완화 (짧은 질문 과도한 명확화 방지) | [x] | `rag_agent.py` |
| AH-14 | 대화 히스토리 기반 검색 쿼리 보강 (follow-up 컨텍스트 반영) | [x] | `rag_agent.py` |
| AH-15 | RAG 시스템 프롬프트 구조화 데이터 추출 강화 (인사정보 등) | [x] | `rag_agent.py` |
| AH-16 | 검색 범위 확대 (n_results 5→8) + 관련성 임계값 조정 (0.4→0.3) | [x] | `rag_agent.py` |
| AH-17 | 짧은 문서 인덱싱 품질 개선 (파일 경로 컨텍스트 추가) | [x] | `wiki_indexer.py` |
| AH-18 | 탐색 과정 시각화 — Backend thinking_step SSE 이벤트 | [x] | `schemas.py`, `rag_agent.py` |
| AH-19 | 탐색 과정 시각화 — Frontend ThinkingStepsDisplay 컴포넌트 | [x] | `AICopilot.tsx`, `sseClient.ts` |
| AH-20 | Self-Reflective Cognitive Pipeline — 의도분석→초안→자기검토→최종답변 | [x] | `rag_agent.py` |
| AH-21 | 페르소나 업그레이드 — 공감 IT 파트너 + Minto Pyramid + 실행 가능 다음 단계 | [x] | `rag_agent.py` |
| AH-22 | Cognitive Pipeline 백엔드 콘솔 로깅 (thought/draft/critique) | [x] | `rag_agent.py` |

---

## Phase 2: UI 고도화 + 메타데이터 관리

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2-1 | 탭 시스템 확장 — VirtualTabType, openVirtualTab(), TabType 기반 라우팅 | [x] | `types/workspace.ts`, `useWorkspaceStore.ts`, `FileRouter.tsx` |
| P2-2 | 사이드바 3-섹션 전환 — 파일 트리 / 태그 브라우저 / 관리 | [x] | `TreeNav.tsx` |
| P2-3 | 백엔드 템플릿 CRUD API — JSON 파일 기반 저장/로드/항목 추가·삭제 | [x] | `api/metadata.py` |
| P2-4 | 메타데이터 템플릿 에디터 — Workspace 가상 탭, Domain/Process/Tags CRUD | [x] | `editors/MetadataTemplateEditor.tsx` |
| P2-5 | MetadataTagBar — 하드코딩 기본값 → 템플릿 API 동적 로드 | [x] | `metadata/MetadataTagBar.tsx` |
| P2-6 | 에러코드 자동 추출 — 저장 시 정규식 감지 → frontmatter 주입 | [x] | `wiki_service.py` |
| P2-7 | 태그 정규화 병합 제안 API | [x] | `api/metadata.py` |
| P2-8 | 태그 기반 사이드바 브라우저 — Domain/Process/Tags 계층 탐색 + 문서 필터 | [x] | `TreeNav.tsx`, `api/metadata.py` |
| P2-9 | 미태깅 문서 대시보드 — 목록 + 일괄 자동 태깅 + 태그 사용 통계 | [x] | `editors/UntaggedDashboard.tsx`, `api/metadata.py` |

---

## Phase 2-A: RAG 성능 고도화

> 문서 대량 증가 시 응답 속도 + 검색 품질 유지를 위한 최적화.
> 상세 설계: `toClaude/plan/master_plan.md` → Phase 2-A 섹션 참조.

### Step P2A-1: LLM 호출 병렬화 + 제거

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-1-1 | 라우팅 + 쿼리보강 `asyncio.gather` 병렬화 | [x] | `agent.py`, `rag_agent.py` |
| P2A-1-2 | 명확화 확인 → 규칙 기반 전환 (LLM 제거) | [x] | `rag_agent.py` |
| P2A-1-3 | 라우팅 키워드 커버리지 확대 → LLM 폴백 빈도 최소화 | [x] | `router.py` |
| P2A-1-4 | RAG 파이프라인 지연시간 벤치마크 스크립트 | [x] | `tests/bench_rag_latency.py` |

### Step P2A-2: 하이브리드 검색 (벡터 + BM25)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-2-1 | BM25 인덱스 구축 (rank_bm25, 토큰화) | [x] | `infrastructure/search/bm25.py` |
| P2A-2-2 | RRF 병합 모듈 (벡터 + BM25 결과 융합) | [x] | `infrastructure/search/hybrid.py` |
| P2A-2-3 | RAG Agent → hybrid_search 교체 | [x] | `rag_agent.py` |
| P2A-2-4 | BM25 인덱스 자동 갱신 (문서 저장/삭제 동기화) | [x] | `wiki_indexer.py`, `bm25.py` |
| P2A-2-5 | 검색 품질 비교 테스트 | [x] | `tests/test_hybrid_search.py` |

### Step P2A-3: 증분 인덱싱

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-3-1 | 파일 content hash 기반 변경 감지 | [x] | `infrastructure/storage/file_hash.py` |
| P2A-3-2 | index_file 시 해시 비교 → 변경 없으면 스킵 | [x] | `wiki_indexer.py` |
| P2A-3-3 | remove_file 개선 — metadata where 필터 기반 정확 삭제 | [x] | `wiki_indexer.py`, `chroma.py` |
| P2A-3-4 | reindex API에 force 파라미터 추가 | [x] | `wiki.py` |

### Step P2A-4: 임베딩/검색 캐싱

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-4-1 | 쿼리 해시 LRU 캐시 (TTL 5분) | [x] | `infrastructure/cache/query_cache.py` |
| P2A-4-2 | RAG Agent에 캐시 히트 로직 추가 | [x] | `rag_agent.py` |
| P2A-4-3 | 문서 변경 시 캐시 무효화 | [x] | `wiki_indexer.py`, `query_cache.py` |
| P2A-4-4 | 캐시 히트율 모니터링 로그 | [x] | `query_cache.py` |

### Step P2A-5: 메타데이터 사전 필터링

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-5-1 | 질문에서 domain/process 키워드 규칙 기반 추출 | [x] | `application/agent/filter_extractor.py` |
| P2A-5-2 | 추출 필터 → ChromaDB where 절 변환 | [x] | `rag_agent.py` |
| P2A-5-3 | 필터 0건 시 fallback (필터 제거 후 재검색) | [x] | `rag_agent.py` |
| P2A-5-4 | domain/process 사용 통계 캐싱 API | [x] | `filter_extractor.py` |

### Step P2A-6: Cross-encoder 리랭킹

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2A-6-1 | Cross-encoder 래퍼 구현 | [x] | `infrastructure/search/reranker.py` |
| P2A-6-2 | RAG Agent에 리랭킹 단계 추가 | [x] | `rag_agent.py` |
| P2A-6-3 | 리랭킹 on/off 설정 + 지연 시간 로깅 | [x] | `config.py`, `reranker.py` |
| P2A-6-4 | A/B 비교 테스트 (리랭킹 유무) | [x] | `tests/test_reranker.py` |

---

## Phase 2-B: 문서 충돌 감지 & 해소

> 같은 주제 문서가 여러 개일 때 사용자가 올바른 판단을 할 수 있도록 가이드.
> 상세 설계: `toClaude/plan/master_plan.md` → Phase 2-B 섹션 참조.

### Step P2B-1: RAG 답변 충돌 감지 프롬프트

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-1-1 | `_build_context_with_metadata()` — 각 문서 청크에 출처/작성자/수정일 헤더 삽입 | [x] | `rag_agent.py` |
| P2B-1-2 | `FINAL_ANSWER_SYSTEM_PROMPT` 충돌 감지 규칙 추가 — 문서 간 모순 시 경고 + 최신 문서 권고 | [x] | `rag_agent.py` |
| P2B-1-3 | `COGNITIVE_REFLECT_PROMPT` — self_critique에 문서 간 충돌 확인 항목 추가 | [x] | `rag_agent.py` |
| P2B-1-4 | 충돌 경고 SSE 이벤트 — `ConflictWarningEvent` 스키마 + 프론트엔드 경고 배너 | [x] | `schemas.py`, `agent.ts`, `AICopilot.tsx` |

### Step P2B-2: 메타데이터 기반 신뢰도 표시

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-2-1 | `DocumentMetadata`에 `status` 필드 추가 (draft/review/approved/deprecated) + 파싱/직렬화 | [x] | `schemas.py`, `local_fs.py` |
| P2B-2-2 | ChromaDB 인덱서에 `status` 필드 반영 | [x] | `wiki_indexer.py` |
| P2B-2-3 | `SourceRef` 스키마 확장 — `updated`, `updated_by`, `status` 필드 + `_build_sources()` 주입 | [x] | `schemas.py`, `rag_agent.py` |
| P2B-2-4 | 프론트엔드 소스 패널 UI 개선 — 날짜 배지, 작성자, status 아이콘, "최신" 라벨 | [x] | `agent.ts`, `AICopilot.tsx` |
| P2B-2-5 | MetadataTagBar에 status 드롭다운 추가 | [x] | `wiki.ts`, `MetadataTagBar.tsx`, `frontmatterSync.ts` |

### Step P2B-3: 문서 중복/충돌 감지 대시보드

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-3-1 | `ChromaWrapper.get_all_embeddings()` 메서드 추가 | [x] | `chroma.py` |
| P2B-3-2 | `ConflictDetectionService` — 문서별 임베딩 평균 → 코사인 유사도 → 클러스터링 | [x] | `conflict/conflict_service.py` |
| P2B-3-3 | `GET /api/conflict/duplicates` API — 유사 문서 쌍 목록 반환 | [x] | `api/conflict.py` |
| P2B-3-4 | `POST /api/conflict/deprecate` API — 문서 status를 deprecated로 변경 | [x] | `api/conflict.py` |
| P2B-3-5 | `ConflictDashboard` 프론트엔드 — VirtualTab, 유사 문서 테이블, 비교/폐기/병합 액션 | [x] | `ConflictDashboard.tsx`, `workspace.ts`, `FileRouter.tsx` |

### Step P2B-4: 인라인 비교 뷰 (Side-by-side diff)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-4-1 | `GET /api/wiki/compare` API — 두 문서 경로 → body + 메타데이터 반환 | [x] | `api/wiki.py` |
| P2B-4-2 | `DiffViewer` 컴포넌트 — line-by-line diff, 추가/삭제/변경 하이라이트 | [x] | `DiffViewer.tsx` |
| P2B-4-3 | VirtualTab 라우팅 — `"document-compare"` 탭 + `openCompareTab(pathA, pathB)` | [x] | `workspace.ts`, `useWorkspaceStore.ts`, `FileRouter.tsx` |
| P2B-4-4 | "이 문서가 최신" 버튼 — deprecated 자동 변경 + `superseded_by` 설정 | [x] | `DiffViewer.tsx`, `api/conflict.py` |
| P2B-4-5 | ConflictDashboard + RAG 답변에서 "비교" 액션 연동 | [x] | `ConflictDashboard.tsx`, `AICopilot.tsx` |

### Step P2B-5: 문서 계보(Lineage) 시스템

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-5-1 | `DocumentMetadata`에 lineage 필드 추가 (`supersedes`, `superseded_by`, `related`) | [x] | `schemas.py`, `local_fs.py` |
| P2B-5-2 | RAG 검색 시 superseded 문서 패널티 + "새 버전 있음" 노트 | [x] | `wiki_indexer.py`, `rag_agent.py` |
| P2B-5-3 | `GET /api/wiki/lineage/{path}` API — 문서 계보 트리 반환 | [x] | `api/wiki.py` |
| P2B-5-4 | 프론트엔드 Lineage 위젯 — 이전/새 버전, 관련 문서 링크 표시 | [x] | `LineageWidget.tsx`, `MarkdownEditor.tsx` |
| P2B-5-5 | 저장 시 자동 lineage 제안 — 유사 문서 감지 시 "이 문서의 새 버전인가요?" 프롬프트 | [x] | `conflict_service.py`, `DiffViewer.tsx` |

### Step P2B-6: RAG deprecated 문서 필터링 + 최신 문서 자동 대체

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-6-1 | RAG 검색에서 deprecated 문서 제외 (ChromaDB where 필터 + BM25 필터) | [x] | `rag_agent.py`, `chroma.py`, `bm25.py` |
| P2B-6-2 | deprecated만 검색된 경우 `superseded_by` 체인 추적 → 최신 문서 자동 대체 | [x] | `rag_agent.py`, `wiki_service.py` |
| P2B-6-3 | 기존 +0.3 패널티 로직 제거 (필터로 대체) + 소스 패널에 deprecated 노출 안 함 | [x] | `rag_agent.py` |

### Step P2B-7: 충돌 대시보드 해결 상태 관리

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2B-7-1 | `DuplicatePair`에 `resolved` 필드 + 자동 해결 판정 (양방향 lineage 존재 시) | [x] | `conflict_service.py` |
| P2B-7-2 | API에 `filter` 파라미터 추가 (`unresolved` / `resolved` / `all`) | [x] | `api/conflict.py` |
| P2B-7-3 | 프론트엔드 대시보드에 탭 필터 (미해결 / 해결됨 / 전체), 기본값 "미해결" | [x] | `ConflictDashboard.tsx` |

---

## Phase 3-A: 문서 검색

> Ctrl+K 커맨드 팔레트 + MiniSearch 클라이언트 검색 + 서버 하이브리드 의미 검색
> 상세 설계: `.claude/plans/dazzling-orbiting-yeti.md` 참조.

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P3A-1 | MiniSearch 패키지 설치 | [x] | `package.json` |
| P3A-2 | 검색 zustand 스토어 — MiniSearch 인덱스 로드, 검색, 모드 전환 | [x] | `lib/search/useSearchStore.ts` |
| P3A-3 | 서버 사이드 하이브리드 검색 API — BM25+벡터 RRF 노출 | [x] | `backend/api/search.py`, `schemas.py` |
| P3A-4 | SearchCommandPalette 컴포넌트 — cmdk 기반, shouldFilter=false | [x] | `components/search/SearchCommandPalette.tsx` |
| P3A-5 | SearchResultItem — 제목 하이라이트, 경로, 스니펫, 태그 뱃지 | [x] | `components/search/SearchResultItem.tsx` |
| P3A-6 | 키보드 단축키 + 마운트 — Ctrl+K, page.tsx 마운트 | [x] | `app/page.tsx` |
| P3A-7 | TreeNav 검색 버튼 — 사이드바 헤더에 Search 아이콘 | [x] | `TreeNav.tsx` |

---

## Phase 3-B: 문서 관계 그래프

> react-force-graph-2d 기반 문서 연결 시각화, 양방향 탐색
> 상세 설계: `.claude/plans/dazzling-orbiting-yeti.md` 참조.

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P3B-1 | 그래프 데이터 API — 백링크+lineage+related 집계, BFS | [x] | `backend/api/search.py`, `schemas.py` |
| P3B-2 | 유사도 엣지 확장 — include_similar, ConflictDetectionService 연동 | [x] | `backend/api/search.py` |
| P3B-3 | Virtual Tab 등록 — `"document-graph"` 타입 | [x] | `workspace.ts`, `useWorkspaceStore.ts` |
| P3B-4 | 그래프 타입 정의 — GraphNode, GraphEdge, GraphData | [x] | `types/wiki.ts` |
| P3B-5 | react-force-graph 패키지 설치 | [x] | `package.json` |
| P3B-6 | DocumentGraph 핵심 컴포넌트 — ForceGraph2D + fetch + 툴바 | [x] | `editors/DocumentGraph.tsx` |
| P3B-7 | 노드 렌더링 — status별 색상, degree 기반 크기, 라벨 | [x] | `DocumentGraph.tsx` |
| P3B-8 | 엣지 렌더링 — 타입별 색상/스타일/화살표, 범례 | [x] | `DocumentGraph.tsx` |
| P3B-9 | 노드 클릭 네비게이션 — openTab + 우클릭 컨텍스트 메뉴 | [x] | `DocumentGraph.tsx` |
| P3B-10 | 현재 문서 중심 보기 — 열린 탭 기준 센터링 | [x] | `DocumentGraph.tsx` |
| P3B-11 | FileRouter 라우팅 — dynamic import | [x] | `FileRouter.tsx` |
| P3B-12 | TreeNav 진입점 — 관리 섹션에 그래프 메뉴 | [x] | `TreeNav.tsx` |
| P3B-13 | 노드 호버 툴팁 — 제목, 경로, status, 태그, 연결 수 | [x] | `DocumentGraph.tsx` |

### Ad-hoc: Phase 3 고도화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P3-AH1 | 문서 열기 시 연결 문서 패널 (lineage+wikilink 백링크, 접이식) | [x] | `LinkedDocsPanel.tsx`, `MarkdownEditor.tsx` |
| P3-AH2 | 그래프 내 문서 검색 — 검색→노드 센터링+줌 | [x] | `DocumentGraph.tsx` |
| P3-AH5 | 문서 관계 그래프 검색 우선 리디자인 — 전체 그래프 대신 검색으로 중심 문서 선택, BFS 관계만 표시 | [x] | `DocumentGraph.tsx`, `search.py` |
| P3-AH3 | 문서 링크 복사 — 사이드바 우클릭 (md→`[[문서명]]`, 기타→경로) | [x] | `TreeNav.tsx` |
| P3-AH4 | WikiLink 인라인 노드 — `[[문서명]]` 입력/붙여넣기 시 클릭 가능한 링크 자동 변환, 클릭→openTab | [x] | `wikiLink.ts`, `pasteHandler.ts`, `markdown.ts`, `MarkdownEditor.tsx`, `globals.css` |

---

## 진행 요약

| Step | 내용 | Task 수 | 상태 |
|------|------|---------|------|
| Step 0 | 프론트엔드 환경 세팅 | 5 | ✅ 완료 |
| Step 1-A | Tab Workspace 레이아웃 | 14 | ✅ 완료 |
| Step 1-B | Tiptap MD 에디터 | 6 | ✅ 완료 |
| Step 1-C | 클립보드 붙여넣기 | 5 | ✅ 완료 |
| Step 1-D | Multi-Format 뷰어 (P1+P1.5) | 8 | ✅ 완료 |
| Step 1-E | Metadata Pipeline | 15 | ✅ 완료 |
| Step 1-F | AI Copilot + SSE | 9 | ✅ 완료 |
| Step 4 | 마이그레이션 + 통합 테스트 | 8 | ✅ 완료 |
| Ad-hoc | UI/인프라 개선 | 19 | ✅ 완료 |
| | **Phase 1 합계** | **89 tasks** | **✅ 완료** |
| | | | |
| Phase 2 | UI 고도화 + 메타데이터 관리 | 9 | ✅ 완료 |
| | | | |
| P2A-1 | LLM 호출 병렬화 + 제거 | 4 | ✅ 완료 |
| P2A-2 | 하이브리드 검색 (BM25) | 5 | ✅ 완료 |
| P2A-3 | 증분 인덱싱 | 4 | ✅ 완료 |
| P2A-4 | 임베딩/검색 캐싱 | 4 | ✅ 완료 |
| P2A-5 | 메타데이터 사전 필터링 | 4 | ✅ 완료 |
| P2A-6 | Cross-encoder 리랭킹 | 4 | ✅ 완료 |
| | **Phase 2-A 합계** | **25 tasks** | **✅ 완료** |
| | | | |
| P2B-1 | RAG 충돌 감지 프롬프트 | 4 | ✅ 완료 |
| P2B-2 | 메타데이터 신뢰도 표시 | 5 | ✅ 완료 |
| P2B-3 | 중복/충돌 감지 대시보드 | 5 | ✅ 완료 |
| P2B-4 | 인라인 비교 뷰 (diff) | 5 | ✅ 완료 |
| P2B-5 | 문서 계보 시스템 | 5 | ✅ 완료 |
| P2B-6 | RAG deprecated 필터 + 자동 대체 | 3 | ✅ 완료 |
| P2B-7 | 충돌 대시보드 해결 상태 관리 | 3 | ✅ 완료 |
| | **Phase 2-B 합계** | **30 tasks** | **✅ 완료** |
| | | | |
| P3A | 문서 검색 (커맨드 팔레트 + MiniSearch + 의미 검색) | 7 | ✅ 완료 |
| P3B | 문서 관계 그래프 (react-force-graph + 양방향 탐색) | 13 | ✅ 완료 |
| P3-AH | Phase 3 고도화 (연결 문서 패널, 그래프 검색, 링크 복사, WikiLink 노드, 그래프 검색 우선 UX) | 5 | ✅ 완료 |
| | **Phase 3 합계** | **24 tasks** | **✅ 완료** |
| | | | |
| P4A | 에어갭 대응 (외부 의존성 제거) | 5 | ✅ 완료 |
| P4B | Docker 컨테이너화 | 5 | ✅ 완료 |
| P4C | 스토리지 추상화 (NAS 대응) | 4 | ✅ 완료 |
| P4D | 편집 잠금 (동시 편집 방지) | 4 | ✅ 완료 |
| P4E | 권한 관리 (RBAC) | 7 | ✅ 완료 |
| P4F | 보안 강화 + 운영 안정성 | 5 | ✅ 완료 |
| P4G | 대규모 대응 (100명+, 수만 문서) | 4 | ✅ 완료 |
| | **Phase 4 합계** | **34 tasks** | **✅ 완료** |
| | | | |
| P5A | 프론트엔드 생존 (Lazy Tree + 서버 검색) | 4 | ✅ 완료 |
| P5B | 백엔드 동시성 + 비동기 인덱싱 | 7 | ✅ 완료 |
| P5C | Redis 기반 상태 공유 | 4 | ✅ 완료 |
| P5D | 수평 확장 + 리소스 거버넌스 | 5 | ✅ 완료 |
| P5E | LLM 처리량 최적화 | 4 | ✅ 완료 |
| | **Phase 5 합계** | **24 tasks** | **✅ 완료** |
| | | | |
| CR-1 | ChromaDB 네이티브 유사도 검색 메서드 추가 | 2 | ✅ 완료 |
| CR-2 | ConflictStore 신규 (Redis + InMemory 이중 백엔드) | 1 | ✅ 완료 |
| CR-3 | ConflictService 리라이트 (incremental check_file) | 1 | ✅ 완료 |
| CR-4 | API 레이어 수정 (store 읽기 + full-scan 엔드포인트) | 1 | ✅ 완료 |
| CR-5 | WikiService 훅 연결 (save/delete/move) | 1 | ✅ 완료 |
| CR-6 | 프론트엔드 즉시 로드 + 전체 스캔 버튼 | 1 | ✅ 완료 |
| CR-7 | 테스트 작성 (Unit + E2E) | 4 | ✅ 완료 |
| | **충돌 감지 리팩토링 합계** | **11 tasks** | **✅ 완료** |
| | | | |
| SK-1 | Skill Protocol + SkillResult + SkillRegistry | 1 | ✅ 완료 |
| SK-2 | AgentContext (per-request, run_skill, emit_thinking, sse) | 1 | ✅ 완료 |
| SK-3 | 7개 스킬 추출 (query_augment, wiki_search, wiki_read, wiki_write, wiki_edit, llm_generate, conflict_check) | 7 | ✅ 완료 |
| SK-4 | ReAct loop + tool executor (tool_executor.py) | 1 | ✅ 완료 |
| SK-5 | RAGAgent 리팩토링 (skill 호출 전환, backward compat) | 1 | ✅ 완료 |
| SK-6 | main.py + api/agent.py wiring (skill 등록, AgentContext 생성) | 2 | ✅ 완료 |
| SK-7 | 기존 테스트 회귀 확인 (68/68 PASSED) | 1 | ✅ 완료 |
| | **Skill System 합계** | **14 tasks** | **✅ 완료** |

---

## Phase 4-A: 에어갭(Air-gap) 대응 — 외부 의존성 제거

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4A-1 | PDF.js worker 로컬 번들링 — unpkg CDN → public/ 로컬 파일 | [x] | `PdfViewer.tsx`, `public/pdf.worker.min.mjs` |
| P4A-2 | Google Fonts 제거 — next/font/google → 시스템 폰트 스택 | [x] | `layout.tsx`, `globals.css` |
| P4A-3 | LLM 설정 추상화 — Ollama 로컬 모델 기본값, OpenAI는 옵션 | [x] | `config.py`, `.env.example` |
| P4A-4 | 임베딩 로컬 전환 — ChromaDB 기본 임베딩 함수 사용 | [x] | `chroma.py` |
| P4A-5 | 외부 의존성 점검 스크립트 — 빌드 산출물에 외부 URL 없는지 검증 | [x] | `scripts/check-external-deps.sh` |

## Phase 4-B: Docker 컨테이너화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4B-1 | Backend Dockerfile — Python 3.10-slim 멀티스테이지 빌드 | [x] | `Dockerfile.backend` |
| P4B-2 | Frontend Dockerfile — Node 20-alpine 멀티스테이지 (build→serve) | [x] | `frontend/Dockerfile` |
| P4B-3 | docker-compose.yml 통합 — backend + frontend + chromadb 추가 | [x] | `docker-compose.yml` |
| P4B-4 | 환경 변수 분리 — .env.example + docker-compose env_file 연동 | [x] | `.env.example`, `.env.production.example` |
| P4B-5 | 헬스체크 + 시작 순서 — depends_on + healthcheck | [x] | `docker-compose.yml`, `main.py` |

## Phase 4-C: 스토리지 추상화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4C-1 | StorageBackend ABC 정의 (이미 완료) | [x] | `storage/base.py` |
| P4C-2 | LocalFSBackend 구현 (이미 완료) | [x] | `storage/local_fs.py` |
| P4C-3 | NASBackend 구현 — 마운트 경로 기반 | [x] | `storage/nas_backend.py` |
| P4C-4 | 스토리지 팩토리 + 설정 — config에 storage_backend 설정 | [x] | `config.py`, `storage/factory.py` |

## Phase 4-D: 편집 잠금

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4D-1 | Lock 서비스 — 인메모리 잠금 관리 (TTL 자동 해제) | [x] | `lock_service.py` |
| P4D-2 | Lock API — POST /lock, DELETE /unlock, GET /lock/status | [x] | `api/lock.py` |
| P4D-3 | 에디터 잠금 UI — 편집 시 잠금 획득, 타 사용자 읽기전용 | [x] | `MarkdownEditor.tsx` |
| P4D-4 | 자동 해제 — 탭 닫기/세션 종료/5분 TTL 만료 자동 해제 | [x] | `lock_service.py`, `MarkdownEditor.tsx` |

## Phase 4-E: 권한 관리 (RBAC)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4E-1 | 권한 모델 정의 — 기존 User.roles 활용 | [x] | `auth/models.py` (기존) |
| P4E-2 | ACL 저장소 — 폴더/문서별 접근 권한 JSON 관리 | [x] | `auth/acl_store.py` |
| P4E-3 | 권한 체크 의존성 — require_read/require_write | [x] | `auth/permission.py` |
| P4E-4 | Wiki API 권한 적용 — 읽기/쓰기/삭제에 권한 체크 | [x] | `api/wiki.py` |
| P4E-5 | RAG 권한 필터 — 검색 결과에서 접근 불가 문서 제외 | [x] | `rag_agent.py` |
| P4E-6 | 프론트엔드 권한 반영 — 403 에러 시 저장 실패 표시 | [x] | `MarkdownEditor.tsx` (기존 toast) |
| P4E-7 | 권한 관리 UI — ACL 설정 패널 + TreeNav 메뉴 | [x] | `PermissionEditor.tsx`, `api/acl.py` |

## Phase 4-F: 보안 강화 + 운영 안정성

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4F-1 | 시크릿 관리 — .env 분리, .gitignore 강화 | [x] | `.env.example`, `.gitignore` |
| P4F-2 | CORS 강화 — 와일드카드 제거, 명시적 화이트리스트 | [x] | `main.py` |
| P4F-3 | 구조화 로깅 — JSON 포맷 + 요청 ID 추적 | [x] | `main.py`, `logging_config.py` |
| P4F-4 | 입력 검증 강화 — 파일 경로 검증, 요청 크기 제한 | [x] | `api/wiki.py` |
| P4F-5 | 백엔드 에러 핸들러 — 전역 예외 처리 | [x] | `main.py` |

## Phase 4-G: 대규모 대응 + 성능

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4G-1 | 검색 인덱스 페이지네이션 — offset/limit 파라미터 | [x] | `search.py` |
| P4G-2 | 트리 지연 로딩 — depth 파라미터 + subtree API | [x] | `wiki.py` |
| P4G-3 | ChromaDB 배치 인덱싱 — 100건 단위 배치 upsert | [x] | `chroma.py` |
| P4G-4 | API 응답 캐싱 — 트리 API ETag/304 | [x] | `wiki.py` |

---

## Phase 5-A: 프론트엔드 생존 — Lazy Tree + 서버 검색

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P5A-1 | 트리 Lazy Loading — depth=1 초기 로드 + subtree API 연동 | [x] | `TreeNav.tsx`, `wiki.ts`, `wiki.py`, `local_fs.py`, `base.py`, `schemas.py` |
| P5A-2 | 서버 사이드 검색 — MiniSearch 제거, `/api/search/quick` 신규 | [x] | `useSearchStore.ts`, `search.py` |
| P5A-3 | 트리 증분 업데이트 — 전체 재조회 → 낙관적 로컬 업데이트 | [x] | `TreeNav.tsx` |
| P5A-4 | 프론트엔드 ETag 활용 — If-None-Match 전송 + 304 캐시 | [x] | `wiki.ts` |

## Phase 5-B: 백엔드 동시성 + 비동기 인덱싱

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P5B-1 | Uvicorn 멀티 워커 — `--workers 4` + 리소스 제한 | [x] | `Dockerfile.backend`, `docker-compose.yml`, `config.py` |
| P5B-2 | 비동기 인덱싱 — save 즉시 반환, 백그라운드 인덱싱 큐 + 인덱싱 상태 추적 | [x] | `wiki_service.py`, `wiki.py` |
| P5B-2a | 인덱싱 상태 UI — 에디터/트리에 반영 여부 표시, 파일별 수동 재인덱싱, 관리 페이지에서 미반영 문서 일괄 재인덱싱 | [x] | `MarkdownEditor.tsx`, `wiki.py` (API: index-status, reindex/{path}, reindex-pending) |
| P5B-3 | BM25 주기적 리빌드 — 10초 백그라운드 + threading.Lock | [x] | `bm25.py` |
| P5B-4 | 하이브리드 검색 병렬화 — asyncio.gather(vector, bm25) | [x] | `search.py` |
| P5B-5 | 시작 시 백그라운드 인덱싱 — 블로킹 → create_task | [x] | `main.py` |
| P5B-6 | `list_all_files()` 최적화 — 메타 캐시 + 경량 list_file_paths | [x] | `local_fs.py`, `base.py` |

## Phase 5-C: Redis 기반 상태 공유

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P5C-1 | Redis 도입 + Lock 이관 — SET NX EX 원자 잠금 | [x] | `docker-compose.yml`, `config.py`, `lock_service.py`, `lock.py` |
| P5C-2 | Redis 기반 쿼리 캐시 — 무제한 LRU + 멀티 워커 공유 | [x] | `query_cache.py` |
| P5C-3 | Lock Refresh 배치화 — batch-refresh API + 중앙 매니저 | [x] | `MarkdownEditor.tsx`, `lock.py`, `wiki.ts`, `lockManager.ts` |
| P5C-4 | ACL 캐싱 + 핫 리로드 — LRU + 파일 변경 감지 | [x] | `acl_store.py` |

## Phase 5-D: 수평 확장 + 리소스 거버넌스

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P5D-1 | Nginx 리버스 프록시 + 로드 밸런서 | [x] | `nginx.conf`, `docker-compose.yml` |
| P5D-2 | Docker 리소스 제한 — CPU/메모리 제한 | [x] | `docker-compose.yml` |
| P5D-3 | ChromaDB 커넥션 풀링 — Settings 설정 | [x] | `chroma.py` |
| P5D-4 | `get_all_embeddings()` 페이지네이션 — 1000건 배치 | [x] | `chroma.py` |
| P5D-5 | SSE 실시간 이벤트 — 트리/잠금/인덱싱 브로드캐스트 | [x] | `main.py`, `wiki_service.py`, `TreeNav.tsx`, `event_bus.py` |

## Phase 5-E: LLM 처리량 최적화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P5E-1 | RAG LLM 파이프라인 최적화 — reflection 캐시 + 세마포어 | [x] | `rag_agent.py` |
| P5E-2 | LLM 응답 캐싱 — cognitive_reflect 인메모리 캐시 (10분 TTL) | [x] | `rag_agent.py` |
| P5E-3 | Ollama 동시 처리 — NUM_PARALLEL + llm_semaphore_limit | [x] | `docker-compose.yml`, `config.py`, `rag_agent.py` |
| P5E-4 | 백그라운드 검색 인덱스 캐싱 — backlinks/tags 60s TTL 캐시 | [x] | `search.py` |
| P5E-5 | 메타데이터 엔드포인트 최적화 — frontmatter-only 읽기 + 60s TTL 캐시 | [x] | `metadata.py`, `local_fs.py`, `base.py`, `wiki_service.py` |

---

## 충돌 감지 리팩토링 (Batch → Incremental)

> 기존 O(n²) 전체 스캔(79초)을 문서 저장 시 ChromaDB HNSW 쿼리(~50ms)로 대체.
> 설계 문서: `~/.gstack/projects/onTong/donghae-unknown-design-20260330-155500.md`
> 플랜: `~/.claude/plans/dazzling-orbiting-yeti.md`

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| CR-1 | ChromaDB `get_file_embeddings()` + `query_by_embedding()` 추가 | [x] | `chroma.py` |
| CR-2a | `ConflictStore` ABC + `InMemoryConflictStore` 구현 | [x] | `conflict_store.py` |
| CR-2b | `RedisConflictStore` 구현 (SHA256 해시 키) | [x] | `conflict_store.py` |
| CR-3a | `ConflictService.check_file()` — 파일별 증분 감지 | [x] | `conflict_service.py` |
| CR-3b | `ConflictService.remove_file()` + `full_scan()` + `get_pairs()` + `update_metadata()` | [x] | `conflict_service.py` |
| CR-4a | `GET /duplicates` 리라이트 — store 직접 읽기 | [x] | `api/conflict.py` |
| CR-4b | `POST /full-scan` + `GET /scan-status` 신규 | [x] | `api/conflict.py` |
| CR-5a | `_bg_index()` 훅 — 인덱싱 후 `check_file()` | [x] | `wiki_service.py` |
| CR-5b | `delete_file()` + `move_file()` + `move_folder()` 훅 | [x] | `wiki_service.py` |
| CR-6 | 프론트엔드 즉시 로드 + "전체 스캔" 버튼 + 프로그레스 | [x] | `ConflictDashboard.tsx` |
| CR-7 | 테스트 — conflict_store + conflict_service + API + E2E | [x] | `tests/test_p2b3_conflict_dashboard.py` |

## Skill System 기반 구축

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SK-1 | Skill Protocol + SkillResult + SkillRegistry | [x] | `backend/application/agent/skill.py` |
| SK-2 | AgentContext (per-request context, run_skill, emit_thinking, sse) | [x] | `backend/application/agent/context.py` |
| SK-3a | QueryAugmentSkill — 후속 질문 → 독립 검색 쿼리 변환 | [x] | `backend/application/agent/skills/query_augment.py` |
| SK-3b | WikiSearchSkill — 하이브리드 검색 (vector + BM25 + RRF + 필터 + reranking) | [x] | `backend/application/agent/skills/wiki_search.py` |
| SK-3c | WikiReadSkill — 단일 문서 읽기 | [x] | `backend/application/agent/skills/wiki_read.py` |
| SK-3d | WikiWriteSkill — 새 문서 생성 + 승인 요청 | [x] | `backend/application/agent/skills/wiki_write.py` |
| SK-3e | WikiEditSkill — 기존 문서 편집 + 승인 요청 | [x] | `backend/application/agent/skills/wiki_edit.py` |
| SK-3f | LLMGenerateSkill — LLM 호출 (streaming/non-streaming, tool-use 지원) | [x] | `backend/application/agent/skills/llm_generate.py` |
| SK-3g | ConflictCheckSkill — 문서 간 모순 감지 | [x] | `backend/application/agent/skills/conflict_check.py` |
| SK-4 | ReAct loop + tool executor (LLM tool-use 에이전트용 공용 유틸) | [x] | `backend/application/agent/tool_executor.py` |
| SK-5 | RAGAgent 리팩토링 — skill 호출 전환, ctx 없을 때 inline fallback | [x] | `backend/application/agent/rag_agent.py` |
| SK-6a | main.py — register_all_skills() + chroma/storage 전달 | [x] | `backend/main.py` |
| SK-6b | api/agent.py — AgentContext 생성 + ctx=ctx kwarg 전달 | [x] | `backend/api/agent.py` |
| SK-7 | 기존 테스트 회귀 확인 (68/68 PASSED) | [x] | `tests/` |

## User-Facing Skill System (사용자 스킬 관리)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| US-1 | Pydantic 스키마 (SkillMeta, SkillListResponse, SkillCreateRequest, ChatRequest.skill_path, GraphNode.node_type) | [x] | `schemas.py` |
| US-2 | UserSkillLoader — _skills/ 스캔, frontmatter 파싱, 캐시, [[wikilink]] 참조 문서 로딩 | [x] | `backend/application/skill/skill_loader.py` |
| US-3 | SkillMatcher — trigger 키워드 매칭 (substring + token overlap) | [x] | `backend/application/skill/skill_matcher.py` |
| US-4 | AgentContext 확장 — user_skill, skill_context 필드 | [x] | `backend/application/agent/context.py` |
| US-5 | api/agent.py 스킬 해석 — 명시적 skill_path + 자동 매칭 + SSE skill_match 이벤트 | [x] | `backend/api/agent.py` |
| US-6 | RAGAgent._handle_skill_qa — 스킬 기반 Q&A (지시사항 + 참조 문서 → LLM 답변) | [x] | `backend/application/agent/rag_agent.py` |
| US-7 | Skill CRUD API — list, get, create, update, delete, match 엔드포인트 | [x] | `backend/api/skill.py` |
| US-8 | main.py 와이어링 — UserSkillLoader/SkillMatcher 초기화, skill_api 라우터 등록 | [x] | `backend/main.py` |
| US-9 | 프론트엔드 타입 — SkillMeta, SkillListResponse, GraphNode.node_type | [x] | `types/wiki.ts` |
| US-10 | API 클라이언트 — fetchSkills, createSkill, deleteSkill, matchSkill | [x] | `lib/api/skills.ts` |
| US-11 | 사이드바 Skills 탭 — SkillsSection, SkillCard, 인라인 생성 폼 | [x] | `TreeNav.tsx` |
| US-12 | Copilot 통합 — 스킬 피커 버튼, selectedSkill pill, 자동 제안 배너 | [x] | `AICopilot.tsx` |
| US-13 | SSE 확장 — skillPath 파라미터, onSkillMatch 콜백, skill_match 이벤트 | [x] | `sseClient.ts` |
| US-14 | 그래프 노드 타입 구분 — node_type=skill, 다이아몬드 렌더링, 보라색, 범례 | [x] | `search.py`, `DocumentGraph.tsx` |
| US-15 | 기존 테스트 회귀 확인 (68/68 PASSED) | [x] | `tests/` |
| | **User-Facing Skill System 합계** | **15 tasks** | **✅ 완료** |
| | | | |
| ST | Skill 시스템 테스트 추가 (loader, matcher, API) | 4 | ✅ 완료 |

## Skill System 고도화 (카테고리 + 우선순위 + 무시 관리)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SE-1 | 스키마 확장 — category, priority, pinned (BE SkillMeta/SkillCreateRequest/SkillListResponse + FE types) | [x] | `schemas.py`, `wiki.ts` |
| SE-2 | skill_loader 카테고리 추출 — 폴더 경로 기반 + frontmatter 오버라이드, categories 집계 | [x] | `skill_loader.py` |
| SE-3 | 카테고리 기반 스킬 생성 경로 + frontmatter 출력 | [x] | `api/skill.py` |
| SE-4 | 매칭 priority 가중치 (score * (0.8 + p*0.04)) + pinned/priority tiebreaker | [x] | `skill_matcher.py` |
| SE-5 | PATCH toggle API — enabled 필드 flip | [x] | `api/skill.py` |
| SE-6 | toggleSkill API 클라이언트 | [x] | `skills.ts` |
| SE-7 | 사이드바 카테고리 접이식 그룹 + 검색 + 토글 + 복제 + pinned 표시 | [x] | `TreeNav.tsx` |
| SE-8 | 생성 폼 카테고리/우선순위 필드 추가 | [x] | `TreeNav.tsx` |
| SE-9 | Copilot 피커 카테고리 그룹핑 + 검색 | [x] | `AICopilot.tsx` |
| SE-10 | localStorage dismissed 영속화 | [x] | `AICopilot.tsx` |
| SE-11 | 데모 스킬 카테고리 폴더 이동 (HR, Finance, SCM) | [x] | `wiki/_skills/` |
| SE-12 | 기존 테스트 회귀 확인 (68/68 PASSED) | [x] | `tests/` |
| | **Skill System 고도화 합계** | **12 tasks** | **✅ 완료** |

## Skill System 버그픽스 + UX 개선

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SF-1 | storage.write() frontmatter 손상 수정 — 스킬 CRUD에 직접 파일 쓰기 적용 | [x] | `api/skill.py` |
| SF-2 | PATCH toggle API 직접 파일 쓰기 — storage.write() 우회 | [x] | `api/skill.py` |
| SF-3 | 스킬 목록 API 비활성 포함 — include_disabled=True로 사이드바 재활성화 가능 | [x] | `api/skill.py`, `skill_loader.py` |
| SF-4 | Copilot 피커 실시간 갱신 — 열 때마다 refreshSkillList() | [x] | `AICopilot.tsx` |
| SF-5 | HR 스킬 파일 복원 (type: skill frontmatter) | [x] | `wiki/_skills/HR/신규입사자-온보딩.md` |
| SF-6 | 참조 문서 탐색 시각화 — 개별 📄 thinking step 표시 | [x] | `rag_agent.py` |
| SF-7 | 스킬 생성 템플릿 — 지시사항/배경/제약조건/질문예시/참조문서 가이드 | [x] | `api/skill.py` |
| | **버그픽스 + UX 개선 합계** | **7 tasks** | **✅ 완료** |

## 6-Layer Skill Architecture (gstack 패턴 적용)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SL-1 | SkillContext 모델 추가 + SkillCreateRequest에 5개 optional 필드 (role, workflow, checklist, output_format, self_regulation) | [x] | `schemas.py`, `wiki.ts` |
| SL-2 | skill_loader — load_skill_context() → SkillContext 구조체 반환, 6개 섹션 추출, 참조문서 누락 추적 | [x] | `skill_loader.py` |
| SL-3 | AgentContext.skill_context 타입 변경 (str → Any) | [x] | `context.py` |
| SL-4 | api/agent.py — Preamble 런타임 주입 (날짜, 사용자) | [x] | `api/agent.py` |
| SL-5 | _handle_skill_qa — 6-Layer 시스템 프롬프트 빌더 (Preamble→Role→Workflow→Instructions→Checklist→Output→Regulation) | [x] | `rag_agent.py` |
| SL-6 | _build_skill_markdown — 마크다운 생성에 새 6개 섹션 + 템플릿 추가 | [x] | `api/skill.py` |
| SL-7 | 데모 스킬 업그레이드 — 신규입사자-온보딩.md를 6-layer 형식으로 전환, 출장비 기본 형식 유지 (하위호환 검증) | [x] | `wiki/_skills/HR/신규입사자-온보딩.md` |
| SL-8 | 기존 테스트 회귀 확인 (68/68 PASSED) | [x] | `tests/` |
| SL-9 | 후속 질문 스킬 유지 — sessionSkill state로 세션 내 자동 유지 + 자동매칭 저장 + UI 표시 | [x] | `AICopilot.tsx` |
| | **6-Layer Skill 합계** | **9 tasks** | **✅ 완료** |

## FE 고급 설정 UI — 스킬 생성 6-Layer 폼

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SA-1 | SkillContext TypeScript 타입 추가 | [x] | `types/wiki.ts` |
| SA-2 | ReferencedDocsPicker 컴포넌트 (문서 검색/선택) | [x] | `components/skills/ReferencedDocsPicker.tsx` |
| SA-3 | SkillCreateDialog 모달 컴포넌트 (6-Layer 입력 폼) | [x] | `components/skills/SkillCreateDialog.tsx` |
| SA-4 | TreeNav.tsx 통합 (고급 설정 버튼 + 모달 연결) | [x] | `TreeNav.tsx` |
| SA-5 | 스킬 컨텍스트 API 엔드포인트 (GET /api/skills/{path}/context) | [x] | `api/skill.py` |
| SA-6 | 스킬 복제 시 6-Layer 콘텐츠 복사 | [x] | `skills.ts`, `TreeNav.tsx` |
| | **FE 고급 설정 UI 합계** | **6 tasks** | **✅ 완료** |

## 스킬 관리 편의 기능 (우클릭 컨텍스트 메뉴 + 드래그앤드롭)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SU-1 | 스킬 우클릭 컨텍스트 메뉴 (삭제/복제/토글/편집) | [x] | `TreeNav.tsx` |
| SU-2 | 스킬 삭제 확인 다이얼로그 + 삭제 핸들러 | [x] | `TreeNav.tsx` |
| SU-3 | 스킬 드래그앤드롭 (카테고리 간 이동) | [x] | `TreeNav.tsx`, `api/skill.py` |
| SU-4 | 테스트 + 문서 업데이트 | [x] | `demo_guide.md`, `TODO.md` |

## Skill 시스템 테스트 추가

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| ST-1 | skill_loader Unit 테스트 — frontmatter 파싱, 카테고리 추출, 6-Layer 섹션, 캐시, wikilink | [x] | `tests/test_skill_loader.py` |
| ST-2 | skill_matcher Unit 테스트 — substring/Jaccard, threshold, priority, 한국어 토큰화 | [x] | `tests/test_skill_matcher.py` |
| ST-3 | Skill API Integration 테스트 — CRUD, toggle, move, match, context | [x] | `tests/test_skill_api.py` |
| ST-4 | 전체 회귀 확인 (기존 68 + 신규 77 = 145 PASSED) | [x] | 테스트 결과 |

---

## Pydantic AI 프레임워크 마이그레이션

> 에이전트 프레임워크 유지보수성 확보를 위해 Pydantic AI로 마이그레이션.
> SIMULATION/DEBUG_TRACE 에이전트 구현은 동료가 별도 진행 (본 TODO 범위 밖).

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| PA-1 | Pydantic AI 의존성 추가 + 환경 구성 | [x] | `pyproject.toml`, `llm_factory.py` |
| PA-2 | 기존 Skill 프로토콜 → Pydantic AI `@agent.tool` 전환 + 구조화 출력 모델 | [x] | `models.py`, `pydantic_tools.py` |
| PA-3 | AgentPlugin/Registry 유지 (Hybrid 접근) + litellm 제거 (5개 스킬) | [x] | `skills/*.py` |
| PA-4 | RAGAgent 마이그레이션 (cognitive_reflect + 스트리밍 + 인라인 핸들러) | [x] | `rag_agent.py` |
| PA-5 | ReAct 루프 (tool_executor.py) → Pydantic AI 내장 도구 호출 전환 | [x] | `tool_executor.py`, `react_agent.py` |
| PA-6 | SSE 스트리밍 연동 확인 (기존 이벤트 타입 유지) | [x] | `api/agent.py` (변경 없음) |
| PA-7 | 기존 테스트 회귀 확인 (174/174 PASS, 신규 29개) | [x] | `tests/test_pydantic_ai_migration.py` |
| PA-8 | 새 에이전트 구조로 SIMULATION/DEBUG_TRACE 스캐폴딩 | [x] | `simulator_agent.py`, `tracer_agent.py` |

## Pydantic AI 데모 테스트 버그 수정

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| BF-1 | 스킬 참조문서 wikilink 해석 — 하위 디렉토리 검색 | [x] | `skill_loader.py` |
| BF-2 | LiteLLMProvider API 키 → OpenAIProvider 직접 사용 | [x] | `llm_factory.py` |
| BF-3 | Write intent 패턴 확장 (체크리스트/가이드/매뉴얼 등) | [x] | `rag_agent.py` |
| BF-4 | LLM Provider 추상화 — 레지스트리 패턴, 7개 프로바이더 | [x] | `llm_factory.py`, `config.py` |
| BF-5 | LLM 모델 업그레이드 (gpt-4o-mini → gpt-4o) | [x] | `.env` |
| BF-6 | 키워드 라우팅 → LLM 통합 분류 (UserIntent) | [x] | `router.py`, `rag_agent.py`, `models.py`, `structured_agents.py`, `api/agent.py` |
| BF-7 | 충돌 감지 — context 확장(6000자) + zip 불일치 + conflict_check 2차 호출 | [x] | `rag_agent.py` |
| BF-8 | Lineage 동기화 — status 미설정 시 supersedes/superseded_by 자동 정리 | [x] | `local_fs.py`, `wiki_service.py` |
| BF-9 | 충돌 설명 한국어 출력 | [x] | `rag_agent.py`, `conflict_check.py` |
| BF-10 | 채팅 입력 히스토리 (↑↓ 방향키) | [x] | `AICopilot.tsx` |
| BF-11 | 문서 생성/수정 워크스페이스 직접 작업 (채팅 승인 제거) | [x] | `schemas.py`, `wiki_edit.py`, `wiki_write.py`, `rag_agent.py`, `AICopilot.tsx`, `MarkdownEditor.tsx`, `useWorkspaceStore.ts`, `sseClient.ts` |
| BF-12 | README.md + docs/tech-stack.md 업데이트 | [x] | `README.md`, `docs/tech-stack.md` |
| BF-13 | 충돌 비교 해결 — ConflictPair 모델 + SSE 이벤트 확장 | [x] | `schemas.py` |
| BF-14 | 충돌 비교 해결 — 페어 빌드 로직 + ConflictStore 연동 | [x] | `rag_agent.py`, `context.py`, `agent.py`, `main.py` |
| BF-15 | 충돌 비교 해결 — 채팅 배너 "나란히 비교" 버튼 + 해결 상태 반영 | [x] | `AICopilot.tsx`, `sseClient.ts`, `useWorkspaceStore.ts`, `DiffViewer.tsx` |
| BF-16 | 충돌 감지 오탐 수정 + 요약 품질 개선 | [x] | `rag_agent.py` |

---

### 권장 작업 순서 (크리티컬 패스)

```
Step 0 (환경)
  → Step 1-A (레이아웃)
    → Step 1-B (에디터)  ─────────────────────────┐
      → Step 1-C (클립보드, BE 먼저)               │ 병렬 가능
  → Step 1-E BE (B1→B9 직렬)                      │
    → Step 1-E FE (F1→F6)                         │
  → Step 1-D BE (1D-1,2)                          │
    → Step 1-D FE (뷰어들)                         │
  → Step 1-F (1F-0 BE 먼저 → FE)  ────────────────┘
    → Step 4 (통합 테스트)
```

---

## 작업 지시 방법

각 Step을 시작할 때:
```
Step 0 시작해줘
```

특정 태스크 범위 지정:
```
1E-B1부터 1E-B5까지 진행해줘
```

백엔드 먼저 지시:
```
Step 1-C 백엔드(1C-5)부터 시작해줘
```

완료 태스크는 이 파일 + `CHECKLIST.md`에서 동시 업데이트합니다.

---

## 🔷 3-Section Platform (모델링/시뮬레이션은 별도 팀 진행)

> Modeling(Section 2) + Simulation(Section 3)은 다른 팀에서 별도 진행 중.
> 아래는 Wiki 팀에서 완료한 공유 인프라 스캐폴딩 기록만 남김.

### Phase 0 완료분 (Wiki 팀 기여)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| V2-0-2 | `shared/contracts/simulation.py` — typed 계약 합의 | [x] | `backend/shared/contracts/simulation.py` |
| V2-0-3 | `shared/agent_framework/` — BaseAgent Protocol 추출 | [x] | `backend/shared/agent_framework/` |
| V2-0-10 | `backend/modeling/` 스캐폴딩 | [x] | `backend/modeling/` |
| V2-0-11 | `backend/simulation/` 스캐폴딩 + mock 서버 | [x] | `backend/simulation/` |
| V2-0-12 | Frontend Section 네비게이션 + 3-pane 레이아웃 | [x] | `SectionNav.tsx`, `ModelingSection.tsx`, `SimulationSection.tsx` |
| V2-0-17 | Section 3 개발자 가이드 | [x] | `docs/section3-developer-guide.md` |

> Phase 0 잔여 (온톨로지, shared/ 추출, wiki/ 이동, Neo4j, job queue 등) 및 Phase 1~3은 모델링/시뮬레이션 팀 관할.

---

## 🧠 에이전트 고도화 (agent_bible 분석 기반, v3)

> 기반 문서: `toClaude/agent_bible_analysis/99_adoption_plan.md` (v3 — 전문가 리뷰 반영)
> 제1 목표: 에이전트 이해력/답변 품질 최대화

### Phase 1: 이해력 혁신 (VOC 직접 해결)

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| AG-1-1 | ontong.md 생성 (에이전트 성격/규칙 정의) | - | [x] | `backend/ontong.md` |
| AG-1-2 | 시스템 프롬프트 교체 (FINAL_ANSWER_SYSTEM_PROMPT → ontong.md 로드) | AG-1-1 | [x] | `rag_agent.py` |
| AG-1-3 | 토큰 기반 히스토리 윈도우 (history[-6:] → 동적 예산) | - | [x] | `rag_agent.py`, `wiki_edit.py` |
| AG-1-4 | 구조화된 대화 요약 (규칙 기반, Scope/Skills/Requests/Docs/Current) | AG-1-3 | [x] | `rag_agent.py` |
| AG-1-5 | Continuation instruction 추가 ("요약 인정하지 말고 이어서") | AG-1-4 | [x] | `rag_agent.py`, `ontong.md` |
| AG-1-6 | query_augment 강화 + 주제 전환 감지 (topic_shift) | - | [x] | `skills/query_augment.py`, `rag_agent.py`, `models.py`, `api/agent.py` |
| AG-1-7 | 스킬 프롬프트 마크다운 분리 (코드 ↔ LLM 지시 분리) | AG-1-1 | [x] | `skills/prompts/*.md`, `prompt_loader.py` |
| AG-1-8 | Cognitive Reflect 제거 (AG-1-1~2 검증 후) | AG-1-2 | [x] | `rag_agent.py`, `structured_agents.py` |

### Phase 2: 실행 최적화

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| AG-2-1 | 스킬별 도구 풀 제한 (allowed-tools 매핑) | Phase 1 | [x] | `context.py`, `api/agent.py` |
| AG-2-2 | 파이프라인 병렬화 (query_augment ∥ vector_search) | Phase 1 | [x] | `api/agent.py` (기존 병렬화 충분) |
| AG-2-3 | SkillResult feedback 필드 추가 | Phase 1 | [x] | `skill.py`, `wiki_search.py`, `rag_agent.py` |

### Phase 3: 인프라 강화

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| AG-3-1 | 세션 영속성 (JSONL append) | Phase 2 | [x] | `core/session.py`, `api/agent.py` |
| AG-3-2 | 스킬 권한 매핑 (READ/WRITE/EXECUTE) | Phase 2 | [x] | `skill.py`, `context.py` |
| AG-3-3 | PreSkill/PostSkill 훅 시스템 | AG-3-2 | [x] | `skill.py` HookRegistry, `hooks.py` 내장훅, `context.py` 훅 파이프라인 |

### Phase 4: Q&A ReAct 루프

| # | Task | 의존 | 상태 | 산출물 |
|---|------|------|------|--------|
| AG-4-1 | Q&A 멀티턴 자율 검색 (ReAct 루프 확장) | Phase 2 | [x] | `rag_agent.py`, `models.py`, `prompts/qa_react.md` |
| AG-4-2 | 검색 결과 자기 평가 + 재검색 전략 | AG-4-1 | [x] | `skills/prompts/qa_react.md` (충분성 체크리스트 + 재검색 전략 5단계) |
| AG-4-3 | 사용자 확인 루프 + CompletionStatus | AG-4-1 | [x] | ClarificationRequestEvent SSE, CompletionStatus enum, emit_clarification() |

### 에이전트 고도화 진행 요약

| Phase | 내용 | Task 수 | 상태 |
|-------|------|---------|------|
| Phase 1 | 이해력 혁신 | 8 | ✅ 완료 (8/8) |
| Phase 2 | 실행 최적화 | 3 | ✅ 완료 (3/3) |
| Phase 3 | 인프라 강화 | 3 | ✅ 완료 (3/3) |
| Phase 4 | Q&A ReAct 루프 | 3 | ✅ 완료 (3/3) |
| | **합계** | **17/17 완료** | 전체 완료 |

---

## 세션 35 (2026-04-07) — Smart Friction 레이턴시 최적화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| S35-1 | Smart Friction 선제 캐싱 — 디바운스 search와 동시에 `onCheckSimilar` 백그라운드 호출, 캐시 히트 시 Enter 즉시 반응 | [x] | `frontend/src/components/editors/metadata/TagInput.tsx` |
| S35-2 | similarCache LRU 50개 제한 — Map 삽입 순서 기반 경량 LRU, 장시간 세션 메모리 누수 방지 | [x] | `frontend/src/components/editors/metadata/TagInput.tsx` |

## 세션 36 (2026-04-07~08) — 태그 자동화 고도화 (Phase A+B)

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| S36-A1 | 프롬프트 외부화 (auto_tag_pass1/pass2/auto_tag.md) | [x] | `backend/application/agent/skills/prompts/auto_tag*.md` |
| S36-A2 | 컨텍스트 확장 — filename/parent/neighbor tags/neighbor domains/related docs | [x] | `metadata_service.py`, `metadata_index.py` (4개 메서드 추가) |
| S36-A3 | 2-pass 계층 추론 (domain/process → tags scoped) | [x] | `metadata_service.py` `_pass1_domain`/`_pass2_tags` |
| S36-A4 | Few-shot 7개 도메인 예시 | [x] | `backend/application/metadata/auto_tag_examples.json` |
| S36-A5 | Always-normalize + `TagAlternative` 스키마 | [x] | `metadata_service.py`, `core/schemas.py` |
| S36-A6 | 프론트 Soft UI (alternatives 칩 + 치환 클릭) | [x] | `AutoTagButton.tsx`, `MetadataTagBar.tsx` |
| S36-A7 | Confidence 자동 보정 | [x] | `metadata_service.py` |
| S36-A8 | 회귀 테스트 (domain 정확도 100%, 22건 자동 치환) | [x] | `tests/test_auto_tag_quality.py`, `tests/fixtures/auto_tag_baseline.json` |
| S36-B1 | `extract_query_tags` (쿼리→태그 의미매칭) | [x] | `backend/application/agent/filter_extractor.py` |
| S36-B2 | RAG tag boost rerank (`ONTONG_TAG_BOOST_WEIGHT`) | [x] | `backend/application/agent/rag_agent.py` |
| S36-B3 | Tag-only fallback (domain 0건 → 태그 필터 → 무필터) | [x] | `backend/application/agent/rag_agent.py` |
| S36-B4 | RAG 평가 스크립트 (12 쿼리, baseline hit@5=1.0) | [x] | `tests/test_rag_tag_boost.py`, `tests/fixtures/rag_eval_queries.json` |

---

## 세션 37 (2026-04-09) — Path-Aware RAG + 대화형 경로 명확화

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| S37-P1-1 | 경로 프리픽스 함수 `_build_path_prefix()` | [x] | `wiki_indexer.py` |
| S37-P1-2 | 모든 청크에 경로 프리픽스 적용 | [x] | `wiki_indexer.py` |
| S37-P1-3 | 구조화된 경로 메타데이터 (`path_depth_1/2/stem`) | [x] | `wiki_indexer.py` |
| S37-P1-4 | 재인덱싱 실행 + 검증 | [x] | `wiki_service.py` |
| S37-P2-1 | `extract_path_filter()` 쿼리 경로 추출 | [x] | `filter_extractor.py` |
| S37-P2-2 | wiki_search 스킬 경로 필터 통합 | [x] | `skills/wiki_search.py` |
| S37-P3-1 | `_detect_path_ambiguity()` 경로 분산 분석 | [x] | `rag_agent.py` |
| S37-P3-2 | _handle_qa() 명확화 이벤트 발행 통합 | [x] | `rag_agent.py` |
| S37-P3-3 | `clarification_response_id` 활성화 + 경로 재검색 | [x] | `api/agent.py` |
| S37-P3-4 | 세션 `path_preferences` 누적 | [x] | `session.py`, `context.py` |
| S37-P4-1 | `_path_boost_rerank()` 경로 부스트 리랭크 | [x] | `rag_agent.py` |
| S37-P4-2 | _handle_qa() 리랭크 통합 | [x] | `rag_agent.py` |
| S37-E1 | 평가 + 회귀 테스트 | [x] | `tests/test_rag_tag_boost.py` 회귀 통과 |
| S37-E2 | 브라우저 E2E 검증 | [x] | 사용자 데모 확인 완료 |
| S37-DOC | 문서 동기화 (CHANGES, demo_guide, HANDOFF) | [x] | `toClaude/` |

## 세션 37 버그 수정

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| S37-BF1 | 스킬 무시 버튼 무효 — `dismissed_skills` 프론트→백 전달 | [x] | `schemas.py`, `api/agent.py`, `sseClient.ts`, `AICopilot.tsx` |
| S37-BF2 | 사이드바 스킬 목록 미표시 — FastAPI `redirect_slashes` + 라우트 slash 충돌 | [x] | `main.py`, `api/skill.py` |
| S37-BF3 | 보안-점검-도우미 스킬 frontmatter 누락 (`type: skill`, `trigger`) | [x] | `wiki/_skills/보안/보안-점검-도우미.md` |
| S37-BF4 | 채팅 첫 응답 지연 체감 — classify 전 즉시 thinking_step 이벤트 발행 | [x] | `api/agent.py` |

## Status Simplification + Lineage/Versioning Overhaul

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| SL-1 | Status 단순화 — review/미설정 제거, draft/approved/deprecated만 | [x] | `schemas.py`, `local_fs.py` |
| SL-2 | Approved 강등 — 내용 수정 시 자동 draft + undeprecate→draft | [x] | `wiki_service.py`, `conflict.py` |
| SL-3 | 프론트엔드 타입/드롭다운/뱃지 업데이트 | [x] | `wiki.ts`, `DocumentInfoDrawer.tsx`, `MetadataTagBar.tsx`, `DocumentInfoBar.tsx`, `DocumentGraph.tsx` |
| SL-4 | Scoring — review=70/unset=50 제거, draft 폴백 40 | [x] | `scoring_config.py`, `confidence.py` |
| SL-5 | MetadataIndex — status/supersedes/superseded_by 저장 + 역참조 인덱스 | [x] | `metadata_index.py`, `wiki_service.py`, `main.py` |
| SL-6 | Lineage 검증 — 자기참조/사이클/경쟁 대체/무후계 폐기 | [x] | `lineage_validator.py`, `wiki_service.py`, `api/wiki.py` |
| SL-7 | Deprecation 연쇄 — 충돌 자동 해결, deprecated 제외, 0건 폴백 | [x] | `wiki_service.py`, `metadata_index.py`, `wiki_search.py` |
| SL-8 | Version Chain API + Timeline UI | [x] | `api/wiki.py`, `VersionTimeline.tsx`, `LineageWidget.tsx` |
| SL-9 | Reference Integrity + Deprecation UX | [x] | `wiki_service.py`, `TreeNav.tsx`, `api/metadata.py` |
| SL-10 | Metadata Inheritance + Bulk Status | [x] | `api/wiki.py` |

---

## UI/UX Overhaul — Content-First Layout

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| UX-1 | TreeNav 접기 — collapsible prop, Cmd+B, 아이콘 스트립, localStorage 유지 | [x] | `app/page.tsx` |
| UX-2 | AICopilot 접기 — 동일 패턴, Cmd+J | [x] | `app/page.tsx` |
| UX-3 | DocumentInfoBar — 32px 단일 행 통합 정보 바 | [x] | `editors/DocumentInfoBar.tsx` |
| UX-4 | DocumentInfoDrawer — 3탭 overlay drawer, Cmd+I | [x] | `editors/DocumentInfoDrawer.tsx` |
| UX-5 | MarkdownEditor 리팩토링 — 3개 스택 컴포넌트 → InfoBar+InfoDrawer 교체 | [x] | `editors/MarkdownEditor.tsx` |
| UX-6 | AI 팝아웃 — floating window 분리, 드래그/리사이즈, dock back, Cmd+J 토글 | [x] | `app/page.tsx` |

---

## Part 2 — 충돌 & Lineage

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P2-2A | Lineage 사이클 감지 — visited set + warning 로그 | [x] | `rag_agent.py` |
| P2-2C-BE | 검색 결과 deprecated 뱃지 — SourceRef에 superseded_by 필드, deprecated 소스 포함 | [x] | `schemas.py`, `rag_agent.py`, `sseClient.ts` |
| P2-2C-FE | deprecated "폐기됨" 뱃지 + "→ 새 버전" 링크 | [x] | `AICopilot.tsx` |
| P2-2B-BE | 폐기 되돌리기 API — POST /api/conflict/undeprecate | [x] | `api/conflict.py` |
| P2-2B-FE | ConflictDashboard deprecated 문서 "되돌리기" 버튼 | [x] | `ConflictDashboard.tsx` |
| P2-2D | 충돌 쌍 그룹핑 — 같은 file_a 공유 쌍을 그룹 렌더링 | [x] | `ConflictDashboard.tsx` |
| P2-REDIS | 충돌 스캔 결과 Redis 영속화 + 기본 threshold 0.85 | [x] | `.env`, `conflict_service.py` |
| P2-FIX1 | VersionTimeline `wiki:lineage-changed` 이벤트 리스너 — 폐기 되돌리기 후 타임라인 자동 갱신 | [x] | `VersionTimeline.tsx` |
| P2-FIX2 | `_clear_stale_lineage_refs` MetadataIndex 갱신 누락 수정 — version-chain API stale 데이터 버그 | [x] | `wiki_service.py` |

## 스코어링 중앙화 + UX 개선 (세션 39)

| # | Task | 상태 | 파일 |
|---|------|------|------|
| S-1 | scoring_config.py 중앙 설정 생성 | [x] | `trust/scoring_config.py` |
| S-2 | confidence.py → SCORING 참조 리팩터 | [x] | `trust/confidence.py` |
| S-3 | search.py min_similarity 0.5→0.7 + composite 중앙화 | [x] | `api/search.py` |
| S-4 | rag_agent.py boost floor 중앙화 | [x] | `rag_agent.py` |
| S-5 | conflict_service.py 임계값 중앙화 | [x] | `conflict_service.py` |
| S-6 | wiki_service.py auto_suggest 임계값 중앙화 | [x] | `wiki_service.py` |
| U-1 | LinkedDocsPanel 기본 2건 + 더 보기 토글 | [x] | `LinkedDocsPanel.tsx` |
| E-1 | GET /api/wiki/scoring-config 투명성 API | [x] | `api/wiki.py` |
| V-1 | 신뢰도 pill 클릭 시 시그널 상세 팝오버 | [x] | `MarkdownEditor.tsx` |
| V-2 | ScoringDashboard 관리자 페이지 | [x] | `ScoringDashboard.tsx`, `TreeNav.tsx`, `FileRouter.tsx` |
| V-3 | AI소스 뱃지 툴팁 강화 (해석 메시지) | [x] | `AICopilot.tsx` |

## Trust System Phase 3 — 읽기 시 맥락

| # | Task | 상태 | 파일 |
|---|------|------|------|
| P3-1 | CitationTracker (Redis/InMemory) | [x] | `trust/citation_tracker.py`, `rag_agent.py` |
| P3-2 | ConfidenceResult 확장 (citation_count, newer_alternatives) | [x] | `trust/confidence.py`, `trust/confidence_service.py` |
| P3-3 | TrustBanner 컴포넌트 | [x] | `TrustBanner.tsx`, `MarkdownEditor.tsx` |
| P3-4 | 와이어링 (main.py) | [x] | `main.py` |
| P3-5 | 단위 테스트 14개 | [x] | `tests/test_phase3_trust.py` |

## Trust System Phase 1 — Document Confidence Score

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| T1-1 | ConfidenceScorer 엔진 (신뢰도 0-100 계산) | [x] | `trust/confidence.py`, `trust/confidence_cache.py`, `trust/confidence_service.py` |
| T1-2 | Confidence API 엔드포인트 | [x] | `api/wiki.py` — GET /confidence/{path}, /confidence-batch |
| T1-3 | RAG 랭킹 통합 (신뢰도 기반 mild boost) | [x] | `rag_agent.py`, `schemas.py` — SourceRef 확장 |
| T1-4 | 프론트엔드 신뢰도 뱃지 | [x] | `AICopilot.tsx` (소스 dot), `MarkdownEditor.tsx` (헤더 pill), `sseClient.ts` |
| T1-5 | 와이어링 + 테스트 + 문서 | [x] | `main.py`, `tests/test_confidence.py` (28 pass) |

## Trust System Phase 2 — Write-Time Related Document Nudge

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| T2-1 | 관련 문서 API (`GET /api/search/related`) | [x] | `api/search.py`, `schemas.py` (RelatedDocResult) |
| T2-2 | LinkedDocsPanel AI 추천 섹션 | [x] | `LinkedDocsPanel.tsx` — "참고할 만한 문서" 섹션 |
| T2-3 | 저장 시 자동 related 제안 | [x] | `wiki_service.py` — _auto_suggest_related() |
| T2-4 | 와이어링 + 테스트 + 문서 | [x] | `main.py`, `tests/test_related_search.py` (12 pass) |

## Trust System Phase 4 — Smart Conflict Resolution

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| P4-1 | TypedConflict 모델 + ConflictAnalysis LLM 모델 | [x] | `schemas.py`, `models.py` |
| P4-2 | analyze_pair() + StoredConflict 확장 | [x] | `conflict_check.py`, `conflict_store.py`, `prompts/conflict_analyze_pair.md` |
| P4-3 | 해결 액션 API (resolve, typed, analyze-pair) | [x] | `api/conflict.py`, `conflict_service.py` |
| P4-4 | ConflictDashboard 유형 뱃지 + 해결 버튼 UI | [x] | `ConflictDashboard.tsx`, `TreeNav.tsx`, `useWorkspaceStore.ts` |
| P4-5 | 관리 다이제스트 (BE + FE) | [x] | `trust/digest.py`, `MaintenanceDigest.tsx`, `FileRouter.tsx`, `main.py` |
| P4-6 | 테스트 + 문서 업데이트 | [x] | `tests/test_phase4_smart_conflict.py` (13 pass) |

## User-Driven Self-Healing — Phase A: Foundation Fixes

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| PA-1 | MetadataIndex에 updated/updated_by/created_by/related 필드 추가 | [x] | `metadata_index.py` — on_file_saved() 확장, rebuild() extended kwarg 지원 |
| PA-2 | _get_backlink_count 버그 수정 (항상 0 반환 → related 기반 카운팅) | [x] | `confidence_service.py:191-208` |
| PA-3 | _is_owner_active 버그 수정 (항상 False → updated_by/updated 기반 체크) | [x] | `confidence_service.py:210-243` |
| PA-4 | 프론트엔드 사용자 ID를 백엔드 인증과 연결 | [x] | `auth/currentUser.ts`, `AuthContext.tsx`, `lockManager.ts`, `MarkdownEditor.tsx`, `api/auth.py` |
| PA-5 | Phase A 테스트 작성 및 검증 | [x] | `tests/test_phase_a_confidence_signals.py` (16 pass) |

## User-Driven Self-Healing — Phase B: User Feedback Loop

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| PB-1 | FeedbackTracker 백엔드 (InMemory + Redis) | [x] | `trust/feedback_tracker.py` — FeedbackTracker, InMemory/RedisFeedbackStore, FeedbackSummary |
| PB-2 | Feedback API 엔드포인트 | [x] | `api/wiki.py` — POST/GET /api/wiki/feedback/{path}, main.py 와이어링 |
| PB-3 | TrustBanner 피드백 버튼 | [x] | `TrustBanner.tsx` — "확인했음"/"수정 필요" 버튼 + 피드백 카운트 표시 |
| PB-4 | AICopilot 소스 thumbs | [x] | `AICopilot.tsx` — 소스 카드 옆 thumbs up/down 버튼 |
| PB-5 | Phase B 테스트 | [x] | `tests/test_phase_b_feedback.py` (12 pass) |

## User-Driven Self-Healing — Phase C: Score Integration

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| PC-1 | Confidence 시그널 가중치 재조정 + user_feedback 추가 | [x] | `scoring_config.py` (freshness 25, backlinks 10, owner 10, user_feedback 15), `confidence.py` (_score_user_feedback + compute_confidence 확장) |
| PC-2 | ConfidenceService 피드백 연동 | [x] | `confidence_service.py` (set_feedback_tracker, _get_feedback_counts), `main.py` 와이어링 순서 수정 |
| PC-3 | "확인했음" → freshness 갱신 | [x] | `api/wiki.py` (_refresh_document_timestamp: verified 시 updated/updated_by frontmatter 갱신) |
| PC-4 | Phase C 테스트 | [x] | `tests/test_phase_c_score_integration.py` (20 pass) |

## User-Driven Self-Healing — Phase D: Knowledge Graph Unification

| # | Task | 상태 | 산출물 |
|---|------|------|--------|
| PD-1 | Relationship 모델 + GraphStore | [x] | `core/schemas.py` (Relationship, GraphResult, GraphStats), `graph/graph_store.py` (InMemory + Redis) |
| PD-2 | GraphBuilder | [x] | `graph/graph_builder.py` — metadata.related/supersedes → related/supersedes, ConflictStore → conflicts |
| PD-3 | Graph API + main.py 와이어링 | [x] | `api/graph.py` (GET /api/graph/{path}, GET /api/graph/stats), main.py 초기화 + tree_change 연동 |
| PD-4 | Phase D 테스트 | [x] | `tests/test_phase_d_knowledge_graph.py` (22 pass) |
