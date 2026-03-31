# Phase 5: 엔터프라이즈 스케일링 (100K+ 파일 / 5,000+ 동시 사용자)

## Context

Phase 4까지 211+ tasks 완료, 프로덕션 배포 준비 완성. 스트레스 테스트 결과:
- **현재 안정 구간**: ~2,000 파일 / 동시 검색 10명
- **주요 병목**: 하이브리드 검색 P95=3.2초(10명), 프론트 검색 인덱스 전체 로드, 트리 전체 렌더링
- **목표**: 100K+ 파일, 5,000+ 동시 사용자에서 사용자 불편 없는 응답 속도

엔터프라이즈급 서버(멀티코어, 대용량 RAM, GPU)를 전제로, 코드 아키텍처 병목을 해소하는 플랜.

---

## 핵심 병목 19개 (우선순위별)

### Tier 1 — 브라우저 크래시/서비스 불능
1. 트리 100K DOM 노드 전체 렌더링 (TreeNav.tsx)
2. 검색 인덱스 50MB+ JSON 전체 로딩 (useSearchStore.ts)
3. `list_all_files()` 100K 파일 전체 내용 읽기 (local_fs.py)
4. Uvicorn 단일 워커 (main.py / Dockerfile)
5. 시작 시 전체 리인덱스 블로킹 (main.py)

### Tier 2 — 체감 지연
6. 파일 저장 시 동기 인덱싱 300-400ms (wiki_service.py)
7. 하이브리드 검색 순차 실행 (search.py)
8. 파일 변경마다 트리 전체 재조회 (TreeNav.tsx)
9. Lock refresh 폭풍 5000×2min (MarkdownEditor.tsx)
10. 프론트 ETag 미사용 (wiki.ts)

### Tier 3 — 운영 리스크
11. 인메모리 잠금 재시작 시 유실 (lock_service.py)
12. ACL JSON 파일 캐싱 없음 (acl_store.py)
13. Docker 리소스 제한 없음 (docker-compose.yml)
14. 수평 확장 불가 (단일 백엔드)
15. `get_all_embeddings()` 1-2GB RAM 스파이크 (chroma.py)
16. RAG LLM 2-3회 순차 호출 (rag_agent.py)
17. 쿼리 캐시 128개, 적중률 10-20% (query_cache.py)
18. ChromaDB 커넥션 풀 없음 (chroma.py)
19. BM25 전체 리빌드, 스레드 안전하지 않음 (bm25.py)

---

## Phase 5-A: 프론트엔드 생존 (4 tasks)

> **목표**: 100K 파일에서 브라우저 크래시 방지, 트리/검색 즉시 응답
> **해결 병목**: #1, #2, #8, #10

### P5A-1: 트리 Lazy Loading (depth 제한 + subtree API 연동)

**변경 파일:**
- `frontend/src/components/TreeNav.tsx`
- `frontend/src/lib/api/wiki.ts`
- `backend/api/wiki.py`
- `backend/infrastructure/storage/local_fs.py`
- `backend/infrastructure/storage/base.py`

**변경 내용:**
- `fetchTree()` → `/api/wiki/tree?depth=1` (최상위만 로드)
- 폴더 확장 시 → `/api/wiki/tree/{path}` (해당 폴더 자식만 로드)
- 백엔드 `get_subtree()` 개선: 전체 트리 빌드 후 검색 → 해당 디렉토리만 직접 스캔
- `StorageProvider` ABC에 `list_subtree(prefix)` 메서드 추가
- `LocalFSAdapter`에 구현 추가

**설계 결정:** 가상 스크롤(react-window) 대신 Lazy Loading 선택. 가상 스크롤도 전체 노드 리스트를 메모리에 보유해야 함. Lazy Loading은 서버/클라이언트 모두 경량. 사용자는 보통 3-5단계만 확장 → 200개 노드면 충분.

### P5A-2: 서버 사이드 검색 (MiniSearch 제거)

**변경 파일:**
- `frontend/src/lib/search/useSearchStore.ts`
- `backend/api/search.py`

**변경 내용:**
- 새 엔드포인트 `GET /api/search/quick?q=...&limit=20` — BM25 only 키워드 검색 (5ms)
- 프론트엔드: `loadIndex()` 제거 → 디바운스 후 `/api/search/quick` 호출
- MiniSearch 인스턴스 및 `indexEntries` 전역 변수 제거
- `resolveWikiLink()` → `GET /api/search/resolve-link?target=...` 서버 처리
- 기존 `/api/search/hybrid`는 "의미 검색" 모드로 유지

**설계 결정:** 50MB JSON 전송 완전 제거. 사내 네트워크 RTT ~20ms는 3-5초 인덱스 로드 대비 무시 가능.

### P5A-3: 트리 증분 업데이트 (전체 재조회 제거)

**변경 파일:**
- `frontend/src/components/TreeNav.tsx`
- `frontend/src/lib/workspace/useWorkspaceStore.ts`

**변경 내용:**
- 파일/폴더 변경 후 `fetchTree()` 전체 재조회 → 로컬 상태 낙관적 업데이트
- mutation API 응답에서 새 경로 정보를 받아 트리 상태에 직접 반영
- `refreshTree()` → `treeEvent({ type: 'add'|'remove'|'move', path, node })` 이벤트 시스템

### P5A-4: 프론트엔드 ETag 활용

**변경 파일:**
- `frontend/src/lib/api/wiki.ts`

**변경 내용:**
- API 응답의 ETag 저장 → 다음 요청 시 `If-None-Match` 헤더 전송
- 304 응답 시 캐시된 데이터 반환
- `fetchWithETag()` 유틸리티 함수 생성

### 검증
- DevTools Network: 초기 트리 요청 < 10KB (기존 50MB+)
- 5단계 폴더 진입: 각 확장 < 100ms
- 검색: `/api/search/index` 요청 없음, 결과 < 200ms
- 파일 이름 변경 후: `/api/wiki/tree` 전체 요청 없음

### Phase 5-A 후 커버 규모
| 항목 | Before | After |
|------|--------|-------|
| 파일 수 | ~1K (크래시) | **100K+** |
| 동시 사용자 | ~50 | ~200 |
| 트리 로딩 | 브라우저 OOM | **< 200ms** |
| 검색 | 50MB 로드 | **< 200ms** |

---

## Phase 5-B: 백엔드 동시성 + 비동기 인덱싱 (6 tasks)

> **목표**: 저장 즉시 반환, 검색 병렬화, 멀티코어 활용
> **해결 병목**: #3, #4, #5, #6, #7, #19

### P5B-1: Uvicorn 멀티 워커

**변경 파일:**
- `Dockerfile.backend`
- `docker-compose.yml`
- `backend/core/config.py`

**변경 내용:**
- Dockerfile CMD: `--workers 4 --timeout-keep-alive 65 --limit-max-requests 1000`
- config에 `uvicorn_workers: int = 4` 설정 추가
- docker-compose에 리소스 제한 추가 (CPU 4, RAM 4G)

**주의:** BM25 싱글턴과 query_cache가 워커별 독립 인스턴스가 됨. 시작 시 ChromaDB에서 리빌드하므로 단기적으로 문제없음. Phase 5-C에서 Redis로 통합.

### P5B-2: 비동기 인덱싱 (저장 즉시 반환)

**변경 파일:**
- `backend/application/wiki/wiki_service.py`
- `backend/application/wiki/wiki_indexer.py`
- `backend/main.py`

**변경 내용:**
- `save_file()`에서 `await indexer.index_file()` → `asyncio.create_task(_bg_index())`
- 인덱싱 큐 (asyncio.Queue) + 백그라운드 워커
- hash_store 업데이트 배치화: 5초마다 또는 종료 시 flush

**효과:** 저장 응답 300-400ms → **< 50ms** (파일 쓰기만)

### P5B-3: BM25 주기적 리빌드 (검색 중 블로킹 제거)

**변경 파일:**
- `backend/infrastructure/search/bm25.py`

**변경 내용:**
- `_dirty` 플래그 기반 즉시 리빌드 → 10초 주기 백그라운드 리빌드
- `threading.Lock`으로 읽기/쓰기 스왑 보호
- 검색은 항상 현재 BM25 인스턴스 사용 (최대 10초 지연 허용)
- `_rebuild_daemon` 데몬 스레드 추가

**설계 결정:** rank_bm25는 IDF 증분 업데이트 불가 → 주기적 전체 리빌드가 유일한 방법. 10초 지연은 키워드 검색에서 무시 가능 (의미 검색은 ChromaDB가 실시간).

### P5B-4: 하이브리드 검색 병렬화

**변경 파일:**
- `backend/api/search.py`

**변경 내용:**
```python
# Before: 순차
vector_results = chroma.query(q)      # 50-200ms
bm25_results = bm25_index.search(q)   # 5-10ms

# After: 병렬
vector_task = asyncio.create_task(chroma.query(q))  # I/O bound
bm25_results = bm25_index.search(q)                 # CPU bound, 즉시
vector_results = await vector_task
```

**효과:** 검색 총 시간 200-250ms → **50-200ms** (BM25 시간 완전 숨김)

### P5B-5: 시작 시 백그라운드 인덱싱

**변경 파일:**
- `backend/main.py`

**변경 내용:**
- `await wiki_service.reindex_all()` (블로킹) → `asyncio.create_task(bg_reindex())`
- 앱 즉시 가용 → 인덱싱은 백그라운드에서 진행
- `/health` 응답에 `indexing_progress: {done: 50000, total: 100000}` 추가
- 배치 처리: 100파일씩 + `asyncio.sleep(0)` 양보

**효과:** 시작 시간 수 시간 → **< 5초** (즉시 서비스 가능)

### P5B-6: `list_all_files()` 최적화

**변경 파일:**
- `backend/infrastructure/storage/local_fs.py`

**변경 내용:**
- 메타데이터 캐시 도입: `{path: WikiFile}` dict, 파일 변경 시 무효화
- 경량 `list_file_paths()` 메서드 추가 (경로만, 내용 안 읽음)
- `rglob()` → `asyncio.to_thread()` 래핑 (이벤트 루프 블로킹 방지)
- `/api/search/index` 등 내용 불필요한 엔드포인트에서 경량 메서드 사용

### 검증
- `wrk -t4 -c100 -d10s /health` → 4개 워커 응답 확인
- 파일 저장: 응답 < 100ms, 검색 반영 10초 이내
- 하이브리드 검색: < 300ms
- 100K 파일 시작: health check 5초 이내 응답

### Phase 5-B 후 커버 규모
| 항목 | Before | After |
|------|--------|-------|
| 동시 사용자 | ~200 | **~1,000** |
| 저장 응답 | 300-400ms | **< 100ms** |
| 검색 응답 | 2-3초 | **< 300ms** |
| 시작 시간 | 수 시간 (100K) | **< 5초** |

---

## Phase 5-C: Redis 기반 상태 공유 (4 tasks)

> **목표**: 멀티 워커 간 상태 공유, 잠금 영속성, 캐시 효율
> **해결 병목**: #9, #11, #12, #17

### P5C-1: Redis 도입 + Lock 이관

**변경 파일:**
- `docker-compose.yml` (Redis 서비스 추가)
- `backend/core/config.py` (redis_url 설정)
- `backend/application/lock_service.py` (Redis 기반으로 재작성)

**변경 내용:**
- Redis 7 Alpine 서비스 추가 (docker-compose)
- `SET path NX EX ttl` 원자적 잠금 획득
- 기존 `LockService` 인터페이스 유지 → API/프론트 변경 없음
- 서버 재시작 시 잠금 유지, 멀티 워커 공유

### P5C-2: Redis 기반 쿼리 캐시

**변경 파일:**
- `backend/infrastructure/cache/query_cache.py`

**변경 내용:**
- `OrderedDict` → Redis `SET cache:{hash} value EX 300`
- 캐시 크기 128 → 무제한 (Redis LRU eviction)
- 파일별 무효화: Redis Set `file:{path} → {cache_keys}` 추적
- 멀티 워커 캐시 공유 → 적중률 60-80%

### P5C-3: Lock Refresh 배치화

**변경 파일:**
- `frontend/src/components/editors/MarkdownEditor.tsx`
- `backend/api/lock.py`

**변경 내용:**
- 새 엔드포인트 `POST /api/lock/batch-refresh` — `{paths: string[], user: string}`
- 프론트: 에디터별 개별 refresh → 중앙 Lock Manager가 2분마다 전체 잠금 일괄 갱신
- 5000 유저 × 3탭 × 2분 = 208 req/sec → **41 req/sec** (5배 감소)

### P5C-4: ACL 캐싱 + 핫 리로드

**변경 파일:**
- `backend/core/auth/acl_store.py`

**변경 내용:**
- `check_permission()` 결과 LRU 캐싱 (TTL 60초)
- `set_acl()` / `remove_acl()` 시 캐시 무효화
- `.acl.json` 파일 변경 감지 (polling 30초) → 재시작 없이 반영

### 검증
- 백엔드 컨테이너 kill → 재시작 → `GET /api/lock/status` → 기존 잠금 유지
- 10개 탭 열기 → lock refresh 요청 2분마다 1개만 (기존 10개)
- 동일 검색 쿼리 다른 워커에서 → Redis 캐시 적중

### Phase 5-C 후 커버 규모
| 항목 | Before | After |
|------|--------|-------|
| 동시 사용자 | ~1,000 | **~3,000** |
| 잠금 영속성 | 재시작 시 유실 | **유지** |
| 캐시 적중률 | 10-20% | **60-80%** |
| Lock refresh | 208 req/sec | **~41 req/sec** |

---

## Phase 5-D: 수평 확장 + 리소스 거버넌스 (5 tasks)

> **목표**: 5,000+ 동시 사용자 수용, 단일 장애점 제거
> **해결 병목**: #13, #14, #15, #18

### P5D-1: Nginx 리버스 프록시 + 로드 밸런서

**변경/생성 파일:**
- `nginx.conf` (신규)
- `docker-compose.yml`

**변경 내용:**
- Nginx Alpine 서비스 추가 (포트 80)
- `upstream backend { least_conn; server backend:8001; }` + keepalive 32
- `docker compose up --scale backend=3` → 3인스턴스 × 4워커 = 12 워커
- 프론트엔드 프록시도 Nginx 경유 → CORS 단순화

### P5D-2: Docker 리소스 제한

**변경 파일:**
- `docker-compose.yml`

**변경 내용:**
```yaml
backend:   limits: { cpus: '4', memory: '4G' }
chromadb:  limits: { cpus: '2', memory: '2G' }
redis:     limits: { cpus: '1', memory: '512M' }
frontend:  limits: { cpus: '1', memory: '1G' }
```

### P5D-3: ChromaDB 커넥션 풀링

**변경 파일:**
- `backend/infrastructure/vectordb/chroma.py`

**변경 내용:**
- `chromadb.HttpClient` → httpx `Limits(max_connections=20, max_keepalive=10)` 설정
- 커넥션 재사용으로 TCP 핸드셰이크 오버헤드 제거
- 타임아웃 설정: connect=5s, read=30s

### P5D-4: `get_all_embeddings()` 페이지네이션

**변경 파일:**
- `backend/infrastructure/vectordb/chroma.py`
- `backend/application/conflict/conflict_service.py`

**변경 내용:**
- 전체 임베딩 로드 → `offset/limit` 기반 1000개씩 배치 조회
- ConflictDetectionService에서 점진적 유사도 계산
- 메모리 1-2GB → **< 200MB**

### P5D-5: SSE 실시간 이벤트 브로드캐스트

**변경 파일:**
- `backend/main.py` (SSE 엔드포인트)
- `backend/application/wiki/wiki_service.py` (이벤트 발행)
- `frontend/src/components/TreeNav.tsx` (이벤트 구독)

**변경 내용:**
- `GET /api/events` SSE 엔드포인트 — 트리 변경, 인덱싱 완료, 잠금 상태 브로드캐스트
- 파일 변경 시 이벤트 발행 → 프론트에서 로컬 트리 업데이트
- 폴링 제거 → 실시간 반영

### 검증
- `wrk -t8 -c500 -d30s http://nginx/api/wiki/tree?depth=1` → 2000+ req/sec
- Docker stats → 모든 컨테이너 리소스 제한 내
- 백엔드 1대 kill → Nginx가 나머지로 라우팅, 사용자 에러 없음
- 충돌 감지 100K 파일 → 메모리 4G 이내

### Phase 5-D 후 커버 규모
| 항목 | Before | After |
|------|--------|-------|
| 동시 사용자 | ~3,000 | **5,000+** |
| 가용성 | 단일 장애점 | **HA (Nginx LB)** |
| 메모리 | 무제한 증가 | **제한 내 안정** |

---

## Phase 5-E: LLM 처리량 + AI 품질 (4 tasks)

> **목표**: AI 기능도 대규모에서 정상 동작
> **해결 병목**: #16

### P5E-1: RAG LLM 파이프라인 병합 + 병렬화

**변경 파일:**
- `backend/application/agent/rag_agent.py`

**변경 내용:**
- clarity_check + cognitive_reflect 병합 → 1회 LLM 호출로 통합
- LLM 호출 2-3회 → **1회 리플렉션 + 1회 답변 = 2회**
- 검색과 쿼리 보강 병렬 실행 (이미 agent.py에 일부 구현됨)

### P5E-2: LLM 응답 캐싱

**변경 파일:**
- `backend/application/agent/rag_agent.py`

**변경 내용:**
- cognitive_reflect 결과 Redis 캐싱 (키: query+context 해시, TTL 10분)
- 동일 쿼리+동일 문서 → 리플렉션 스킵, 바로 답변 생성
- reranker 결과도 캐싱

### P5E-3: Ollama 동시 처리 설정

**변경 파일:**
- `docker-compose.yml`
- `backend/core/config.py`

**변경 내용:**
- `OLLAMA_NUM_PARALLEL=4` 환경변수 설정
- `ollama_num_parallel: int = 4` config 추가
- RAG 에이전트에 세마포어 추가: 동시 LLM 호출 수 제한

### P5E-4: 백그라운드 검색 인덱스 캐싱

**변경 파일:**
- `backend/api/search.py`

**변경 내용:**
- `/api/search/backlinks`, `/api/search/tags`, `/api/search/graph`에서 매번 `get_all_files()` 호출 → Redis 캐싱
- 60초 TTL + 파일 변경 이벤트로 무효화
- 100K 파일에서 수 초 → **< 50ms**

### 검증
- RAG 쿼리 E2E: < 4초 (기존 6-9초)
- 동일 쿼리 반복: < 1초 (캐시)
- 10명 동시 RAG 쿼리: 15초 이내 전체 완료

### Phase 5-E 후 커버 규모 (최종)
| 항목 | Before | After |
|------|--------|-------|
| RAG 응답 | 6-9초 | **< 4초** |
| RAG 캐시 | 없음 | **< 1초** |
| AI 동시 | ~5명 | **GPU당 4병렬** |

---

## 최종 규모 비교

| 지표 | 현재 (Phase 4) | Phase 5 완료 후 |
|------|---------------|----------------|
| **파일 수** | ~2,000 안정 | **100,000+** |
| **동시 사용자** | ~50 (검색 10) | **5,000+** |
| **트리 로딩** | 77ms (2K), OOM (100K) | **< 200ms (100K)** |
| **검색 응답** | 3.2초 (10명 동시) | **< 300ms (100명 동시)** |
| **저장 응답** | 300-400ms | **< 50ms** |
| **시작 시간** | 수 시간 (100K) | **< 5초** |
| **RAG 응답** | 6-9초 | **< 4초** |
| **가용성** | 단일 장애점 | **HA (Nginx LB)** |
| **잠금** | 재시작 시 유실 | **Redis 영속** |

## 총 태스크: 23개 (5 sub-phase)

## 실행 순서

```
Phase 5-A (프론트 생존) ────────┐
Phase 5-B (백엔드 동시성) ──────┤ 병렬 가능
                                ↓
Phase 5-C (Redis 상태 공유) ────┘
            ↓
Phase 5-D (수평 확장) ← Redis 완료 후
            ↓
Phase 5-E (LLM 최적화) ← 마지막, 전체 안정화 후
```

## 핵심 아키텍처 결정

1. **Lazy Loading > 가상 스크롤**: 가상 스크롤도 전체 노드 리스트 필요. Lazy Loading은 클라이언트 메모리 상수.
2. **서버 사이드 검색 > 클라이언트 MiniSearch**: 네트워크 RTT 20ms ≪ 50MB 인덱스 전송 3-5초.
3. **Redis > PostgreSQL** (잠금/캐시): 잠금은 sub-ms 원자성 필요. Redis가 최적.
4. **BM25 주기적 리빌드**: rank_bm25가 증분 IDF 업데이트 미지원. 10초 지연 허용.
5. **백그라운드 인덱싱**: 위키는 읽기 즉시 가능해야 함. 불완전 인덱스 > 서비스 불가.
6. **SSE > WebSocket**: 단방향 서버→클라이언트 푸시, HTTP 프록시 호환, 자동 재연결.
