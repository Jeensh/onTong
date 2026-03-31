# Phase 5-B: 백엔드 동시성 + 비동기 인덱싱 — 완료 요약

## 완료일: 2026-03-30

## 목표
저장 즉시 반환, 검색 병렬화, 멀티코어 활용

## 완료 태스크 (7/7)

### P5B-1: Uvicorn 멀티 워커
- Dockerfile: `--workers 4 --timeout-keep-alive 65 --limit-max-requests 10000`
- docker-compose: CPU/메모리 리소스 제한 (backend 4C/4G, chroma 2C/2G, frontend 1C/1G)
- config.py: `uvicorn_workers` 설정 추가

### P5B-2: 비동기 인덱싱
- `save_file()`: `await indexer.index_file()` → `asyncio.create_task(_bg_index())`
- `IndexStatus` 클래스: pending 파일 추적 (mark_pending/mark_done)
- API: `GET /api/wiki/index-status`, `POST /api/wiki/reindex/{path}`, `POST /api/wiki/reindex-pending`

### P5B-2a: 인덱싱 상태 UI
- 에디터: 저장 후 "검색 반영 대기 중..." 배너 (3초 폴링, 30초 자동 해제)
- 비차단: 배너가 있어도 편집/검색 정상 동작

### P5B-3: BM25 주기적 리빌드
- `_rebuild_daemon`: 10초 주기 데몬 스레드, `threading.Lock` 보호
- 검색은 현재 인덱스 사용 (최대 10초 지연 허용)
- 첫 검색 시만 블로킹 리빌드

### P5B-4: 하이브리드 검색 병렬화
- Vector 검색: `asyncio.to_thread()` + `create_task()`로 비동기화
- BM25 검색: CPU-bound, 즉시 실행 (~5ms)
- 두 검색이 병렬 실행 → 총 시간 = max(vector, bm25)

### P5B-5: 시작 시 백그라운드 인덱싱
- 블로킹 `reindex_all()` → `asyncio.create_task(_bg_initial_index())`
- 100파일 배치 + `asyncio.sleep(0)` 양보
- health 엔드포인트에 `indexing_pending` 카운트 추가

### P5B-6: list_all_files() 최적화
- `rglob()` → `asyncio.to_thread(_scan_file_paths())` (이벤트 루프 비블로킹)
- `list_file_paths()` 경량 메서드 추가 (내용 안 읽음)
- 히든 디렉토리 내 파일 필터링 추가

## Phase 5-B 후 기대 커버 규모
| 항목 | Before | After |
|------|--------|-------|
| 동시 사용자 | ~200 | **~1,000** |
| 저장 응답 | 300-400ms | **< 100ms** |
| 검색 응답 | 2-3초 | **< 300ms** |
| 시작 시간 | 수 시간 (100K) | **< 5초** |
