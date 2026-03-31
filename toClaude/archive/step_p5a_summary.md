# Phase 5-A: 프론트엔드 생존 — 완료 요약

## 완료일: 2026-03-30

## 목표
100K 파일에서 브라우저 크래시 방지, 트리/검색 즉시 응답

## 완료 태스크 (4/4)

### P5A-1: 트리 Lazy Loading
- **변경**: `WikiTreeNode`에 `has_children` 필드 추가, `StorageProvider`에 `list_subtree()` 추가
- **동작**: `GET /api/wiki/tree?depth=1` → 최상위만 로드, 폴더 클릭 시 `GET /api/wiki/tree/{path}` → 해당 폴더 자식만 로드
- **산출물**: `schemas.py`, `base.py`, `local_fs.py`, `wiki_service.py`, `wiki.py`, `TreeNav.tsx`, `wiki.ts`
- **테스트**: `tests/test_p5a1_lazy_tree.py` — ALL PASS

### P5A-2: 서버 사이드 검색 (MiniSearch 제거)
- **변경**: `GET /api/search/quick` (BM25 only, ~4ms), `GET /api/search/resolve-link` 신규 엔드포인트
- **동작**: MiniSearch 클라이언트 인덱스 완전 제거 → 200ms 디바운스 후 서버 검색
- **효과**: 번들 크기 576KB → 570KB, 50MB 인덱스 다운로드 제거
- **산출물**: `search.py`, `useSearchStore.ts`
- **테스트**: `tests/test_p5a2_server_search.py` — ALL PASS

### P5A-3: 트리 증분 업데이트
- **변경**: 파일/폴더 CRUD 후 `fetchTreeData()` 전체 재조회 → 로컬 낙관적 업데이트
- **헬퍼 함수**: `removeTreeNode()`, `addTreeNode()`, `updateNodePath()`, `sortNodes()`
- **유지**: 초기 로드, treeVersion (AI 작업), 수동 새로고침은 서버 재조회
- **산출물**: `TreeNav.tsx`

### P5A-4: 프론트엔드 ETag 활용
- **변경**: `fetchWithETag<T>()` 유틸리티 — 응답 ETag 저장, 다음 요청 시 `If-None-Match` 전송
- **적용**: 트리 API에 ETag 캐싱 적용 (304 응답 시 캐시 반환)
- **산출물**: `wiki.ts`

## 핵심 설계 결정
1. **Lazy Loading > 가상 스크롤**: 가상 스크롤도 전체 노드 리스트 필요, Lazy Loading은 메모리 상수
2. **서버 사이드 검색 > 클라이언트 MiniSearch**: 네트워크 RTT 20ms ≪ 50MB 인덱스 전송 3-5초
3. **낙관적 업데이트**: API 성공 후 로컬 상태 즉시 반영, 서버 왕복 제거

## Phase 5-A 후 기대 커버 규모
| 항목 | Before | After |
|------|--------|-------|
| 파일 수 | ~1K (크래시) | **100K+** |
| 트리 로딩 | 브라우저 OOM | **< 200ms** |
| 검색 | 50MB 로드 | **< 200ms** |
| 트리 업데이트 | 전체 재조회 | **즉시 (로컬)** |
