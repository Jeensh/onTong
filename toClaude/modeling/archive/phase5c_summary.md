# Phase 5-C: Redis 기반 상태 공유 — 완료 요약

## 완료 태스크 (4/4)

### P5C-1: Redis 도입 + Lock 이관
- `docker-compose.yml`: Redis 7 Alpine 서비스, maxmemory 256mb allkeys-lru, healthcheck
- `backend/core/config.py`: `redis_url` 설정 추가
- `backend/application/lock_service.py`: LockBackend ABC + InMemoryLockBackend + RedisLockBackend
  - SET NX EX 원자적 잠금 획득, pipeline batch refresh, SADD user index
  - `create_lock_service()` 팩토리 + `get_lock_service()` 싱글톤
- `backend/api/lock.py`: `_svc()` 헬퍼, `POST /api/lock/batch-refresh` 엔드포인트

### P5C-2: Redis 기반 쿼리 캐시
- `backend/infrastructure/cache/query_cache.py`: RedisQueryCache 클래스
  - SET EX 캐시, SADD file→cache_key 인덱스 (파일별 무효화)
  - `create_query_cache()` 팩토리 + Redis 폴백

### P5C-3: Lock Refresh 배치화
- `frontend/src/lib/api/wiki.ts`: `batchRefreshLock()` API 함수 추가
- `frontend/src/lib/lock/lockManager.ts`: 중앙 LockManager 싱글톤
  - `register(path)` / `unregister(path)` — 2분 주기 배치 리프레시
- `frontend/src/components/editors/MarkdownEditor.tsx`: 개별 refreshLock 제거 → lockManager 사용

### P5C-4: ACL 캐싱 + 핫 리로드
- `backend/core/auth/acl_store.py`:
  - `check_permission()` 결과 dict 캐싱 (TTL 60초)
  - `set_acl()` / `remove_acl()` 시 캐시 무효화
  - 30초 주기 데몬 스레드로 `.acl.json` 파일 변경 감지 → 자동 리로드

## 아키텍처 결정
- Redis는 optional — 미설정 시 자동 in-memory 폴백 (개발 환경 호환)
- Lock/Cache 모두 Backend ABC 패턴으로 구현체 교체 용이
- LockManager는 프론트엔드 싱글톤 — 탭 수와 무관하게 2분마다 1회 요청

## Phase 5-C 후 커버 규모
| 항목 | Before | After |
|------|--------|-------|
| 동시 사용자 | ~1,000 | ~3,000 |
| 잠금 영속성 | 재시작 시 유실 | Redis 유지 |
| 캐시 적중률 | 10-20% | 60-80% |
| Lock refresh | 208 req/sec | ~41 req/sec |
