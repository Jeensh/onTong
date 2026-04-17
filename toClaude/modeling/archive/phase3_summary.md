# Phase 3: 문서 검색 + 문서 관계 그래프 — 요약

## 완료 일시: 2026-03-29

## Phase 3-A: 문서 검색 (7 tasks)

### 구현 내용
- **MiniSearch** 클라이언트 사이드 검색 (~8KB, 한글 커스텀 토크나이저, prefix+fuzzy)
- **서버 사이드 하이브리드 검색** API (`GET /api/search/hybrid` — BM25+벡터 RRF 병합)
- **Ctrl+K / Cmd+K** 커맨드 팔레트 (cmdk CommandDialog, shouldFilter=false)
- 키워드/의미 검색 모드 전환, 결과 하이라이트, 스니펫, 태그 뱃지
- TreeNav 사이드바 헤더에 검색 아이콘

### 신규 파일
- `frontend/src/lib/search/useSearchStore.ts` — 검색 zustand 스토어
- `frontend/src/components/search/SearchCommandPalette.tsx` — 팔레트 UI
- `frontend/src/components/search/SearchResultItem.tsx` — 결과 아이템

### 수정 파일
- `backend/api/search.py` — hybrid 엔드포인트 추가
- `backend/core/schemas.py` — HybridSearchResult 스키마
- `backend/main.py` — search_api.init에 chroma 전달
- `frontend/src/app/page.tsx` — 팔레트 마운트 + Ctrl+K
- `frontend/src/components/TreeNav.tsx` — 검색 버튼

## Phase 3-B: 문서 관계 그래프 (13 tasks)

### 구현 내용
- **react-force-graph-2d** 기반 force-directed 그래프 시각화
- **그래프 데이터 API** (`GET /api/search/graph` — 백링크+lineage+related+similarity 집계)
- **4가지 연결 타입**: wiki-link(gray/실선), supersedes(orange/화살표), related(blue/점선), similar(red/dotted)
- **노드**: status별 색상(approved=green, review=blue, draft=gray, deprecated=red), degree 기반 크기
- **네비게이션**: 클릭→문서 열기, 우클릭→컨텍스트 메뉴, 현재 문서 중심 보기
- **BFS 필터링**: center_path + depth로 대규모 위키 성능 보장
- **Virtual Tab**: `"document-graph"`, 관리 섹션 메뉴 진입

### 신규 파일
- `frontend/src/components/editors/DocumentGraph.tsx` — 그래프 뷰어

### 수정 파일
- `backend/api/search.py` — graph 엔드포인트 추가
- `backend/core/schemas.py` — GraphNode/Edge/Data 스키마
- `frontend/src/types/workspace.ts` — document-graph VirtualTabType
- `frontend/src/types/wiki.ts` — 그래프 타입 + HybridSearchResult
- `frontend/src/lib/workspace/useWorkspaceStore.ts` — 탭 제목 매핑
- `frontend/src/components/workspace/FileRouter.tsx` — 라우팅
- `frontend/src/components/TreeNav.tsx` — 그래프 메뉴

## 빌드 결과
- `npx next build` ✅ 성공
