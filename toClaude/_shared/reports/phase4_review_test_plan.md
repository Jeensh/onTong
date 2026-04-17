# Phase 4 검토 및 테스트 플랜

> 작성일: 2026-03-30
> 목적: Phase 4 작업물의 정상 동작 검증 + 대규모 환경 대응 능력 평가

---

## Part 1: 기능 검증 체크리스트

### 1-A. 에어갭 대응 검증

```bash
# 1) 빌드 산출물에 외부 URL이 없는지 확인
cd frontend && npm run build
cd .. && ./scripts/check-external-deps.sh

# 2) 네트워크 차단 상태 검증 (Mac)
# Wi-Fi 끄고 테스트하거나, /etc/hosts에 외부 도메인 차단
sudo bash -c 'echo "127.0.0.1 unpkg.com fonts.googleapis.com api.openai.com" >> /etc/hosts'

# 3) 기능 점검
# - PDF 파일 열기 → worker 로딩 정상?
# - 페이지 폰트 렌더링 깨지지 않음?
# - AI 질의 시 Ollama 로컬 모델 사용 확인 (config에서 litellm_model 확인)

# 4) 정리
sudo sed -i '' '/unpkg.com/d;/fonts.googleapis.com/d;/api.openai.com/d' /etc/hosts
```

**판정 기준**: 외부 네트워크 없이 모든 UI/기능 정상 동작

---

### 1-B. Docker 배포 검증

```bash
# 1) 이미지 빌드
docker compose build

# 2) 전체 기동
docker compose up -d

# 3) 헬스체크
curl http://localhost:8001/health
# 기대: {"status":"ok", "chromadb":"connected", ...}

curl http://localhost:3000
# 기대: HTML 페이지 정상 반환

# 4) 기능 테스트
# - 위키 문서 생성/수정/삭제
# - AI 질의 (Ollama 연동 확인)
# - 검색 동작

# 5) 모니터링 프로필 (선택)
docker compose --profile monitoring up -d
# Langfuse UI: http://localhost:3001

# 6) 종료 + 볼륨 유지 확인
docker compose down
docker compose up -d
# → 이전 데이터 유지되는지 확인
```

**판정 기준**: `docker compose up` 한 번에 전체 서비스 기동, 데이터 영속성 확인

---

### 1-C. 스토리지 추상화 검증

```bash
# 1) 로컬 모드 (기본)
STORAGE_BACKEND=local uvicorn backend.main:app --port 8001
# → 파일 CRUD 정상 동작

# 2) NAS 모드 (테스트 디렉토리로 시뮬레이션)
mkdir -p /tmp/nas_wiki_test
STORAGE_BACKEND=nas NAS_WIKI_DIR=/tmp/nas_wiki_test uvicorn backend.main:app --port 8001
# → 파일 생성 → /tmp/nas_wiki_test/ 아래에 실제 파일 생성 확인
# → 기존 모든 CRUD 정상 동작

# 3) 잘못된 NAS 경로
STORAGE_BACKEND=nas NAS_WIKI_DIR=/nonexistent uvicorn backend.main:app --port 8001
# → 시작 시 에러 메시지 출력
```

**판정 기준**: local/nas 전환 시 동일 동작, 잘못된 경로 시 명확한 에러

---

### 1-D. 편집 잠금 검증

```bash
# 1) 잠금 획득
curl -X POST http://localhost:8001/api/lock \
  -H "Content-Type: application/json" \
  -d '{"path": "test.md", "user": "user-a"}'
# → {"locked": true, ...}

# 2) 동일 문서 다른 사용자 잠금 시도
curl -X POST http://localhost:8001/api/lock \
  -H "Content-Type: application/json" \
  -d '{"path": "test.md", "user": "user-b"}'
# → {"locked": false, "locked_by": "user-a", ...}

# 3) 상태 확인
curl "http://localhost:8001/api/lock/status?path=test.md"
# → {"locked": true, "user": "user-a", ...}

# 4) 해제
curl -X DELETE http://localhost:8001/api/lock \
  -H "Content-Type: application/json" \
  -d '{"path": "test.md", "user": "user-a"}'

# 5) UI 테스트 (브라우저 2개)
# - 탭 A에서 문서 열기 → 편집 가능
# - 탭 B에서 같은 문서 열기 → "편집 중" 배너 + 읽기전용
# - 탭 A 닫기 → 탭 B 새로고침 → 편집 가능
```

**판정 기준**: 동시 편집 차단, TTL 자동 해제, UI 읽기전용 표시

---

### 1-E. 권한 관리 (RBAC) 검증

```bash
# 1) ACL 설정
curl -X PUT http://localhost:8001/api/acl \
  -H "Content-Type: application/json" \
  -d '{"path": "hr/", "read": ["all"], "write": ["hr-team", "admin"]}'

# 2) viewer 역할로 읽기 시도 → 성공
# 3) viewer 역할로 쓰기 시도 → 403 Forbidden
# 4) admin 역할로 쓰기 시도 → 성공

# 5) RAG 필터링 검증
# - hr/ 폴더에 문서 추가 + 인덱싱
# - viewer 역할로 AI 질의 → hr 문서 결과에서 제외
# - admin 역할로 AI 질의 → hr 문서 결과 포함

# 6) UI 검증
# - TreeNav에서 "접근 권한 관리" 버튼 → PermissionEditor 열림
# - ACL 추가/수정/삭제 동작 확인
```

**판정 기준**: 역할별 읽기/쓰기 분리, RAG 결과 필터링, 관리 UI 동작

---

### 1-F. 보안 강화 검증

```bash
# 1) Path traversal 차단
curl http://localhost:8001/api/wiki/file/../../../etc/passwd
# → 400 Bad Request

curl http://localhost:8001/api/wiki/file/test%00.md
# → 400 Bad Request (null byte)

# 2) 대용량 요청 차단
python3 -c "import requests; requests.put('http://localhost:8001/api/wiki/file/big.md', json={'content': 'x'*11*1024*1024})"
# → 422 Validation Error (10MB 초과)

# 3) CORS 확인
curl -I -X OPTIONS http://localhost:8001/api/wiki/tree \
  -H "Origin: https://evil.com"
# → Access-Control-Allow-Origin 없음

# 4) 구조화 로깅 확인
# 백엔드 로그에 JSON 포맷 + request_id 포함되는지 확인
curl http://localhost:8001/api/wiki/tree
# 로그: {"timestamp": "...", "request_id": "abc123", "message": "..."}

# 5) 에러 응답 포맷
curl http://localhost:8001/api/nonexistent
# → {"detail": "Not Found"} (일관된 JSON)
```

**판정 기준**: 공격 벡터 차단, 로그 추적 가능, 일관된 에러 응답

---

## Part 2: 대규모 대응 능력 평가

### 현재 구현의 규모별 예상 성능

| 컴포넌트 | 1K 파일 | 5K 파일 | 10K 파일 | 50K 파일 | 100K 파일 |
|----------|---------|---------|----------|----------|-----------|
| **트리 로딩** | ✅ <200ms | ⚠️ ~500ms | ❌ 1-2초 | ❌ 5초+ | ❌ 10초+ |
| **검색 인덱스** (프론트) | ✅ <100ms | ⚠️ ~300ms | ❌ 1초+ | ❌ OOM 위험 | ❌ 브라우저 크래시 |
| **ChromaDB 인덱싱** | ✅ <30초 | ⚠️ ~2분 | ❌ ~5분 | ❌ 20분+ | ❌ 1시간+ |
| **ETag 계산** | ✅ 즉시 | ✅ ~50ms | ⚠️ ~200ms | ❌ 1초+ | ❌ 3초+ |
| **잠금 서비스** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **ACL 체크** | ✅ | ✅ | ✅ | ✅ | ⚠️ 누적 지연 |

> ✅ 문제없음 | ⚠️ 체감 지연 | ❌ 사용자 경험 저하

### 결론: 현재 구현으로 안정적으로 커버 가능한 규모

```
┌─────────────────────────────────────────────────────────┐
│  안정 운영 구간: 1,000 ~ 5,000 파일 / 100명 동시 사용  │
│  주의 구간:      5,000 ~ 10,000 파일                    │
│  위험 구간:      10,000+ 파일                           │
└─────────────────────────────────────────────────────────┘
```

**5,000 파일 이하**: 모든 기능이 1초 이내 응답, 프로덕션 투입 가능
**5,000~10,000 파일**: 트리 로딩과 검색 인덱스에서 체감 지연 발생, 사용은 가능하나 최적화 필요
**10,000 파일 이상**: 프론트엔드 검색 인덱스 OOM, 트리 로딩 2초+, 추가 최적화 필수

---

### 병목 원인 분석

#### 병목 1: 트리 로딩 — 매 요청마다 파일시스템 전체 스캔

```
요청 → LocalFSAdapter._build_tree() → directory.iterdir() 재귀
     → 모든 파일/폴더 순회 → JSON 직렬화 → 응답
```

- `depth` 파라미터와 subtree API가 **구현되어 있지만 프론트엔드에서 사용하지 않음**
- 백엔드는 매번 전체 트리를 구축 후 ETag 계산 (304 반환해도 연산 발생)

**해결 방향**:
- 프론트엔드에서 `depth=1` 초기 로딩 → 폴더 클릭 시 subtree API 호출
- 백엔드에 트리 캐시 (메모리 캐시 + 파일 변경 시 무효화)

#### 병목 2: 프론트엔드 MiniSearch 인덱스 — 전체 로딩

```
검색 실행 → fetch("/api/search/index") → 전체 인덱스 다운로드
          → MiniSearch.addAll() → 브라우저 메모리에 전체 보관
```

- 5,000 엔트리 시 ~100MB 메모리 사용
- 10,000 엔트리 시 모바일 브라우저 OOM 위험

**해결 방향**:
- 서버 사이드 검색으로 전환 (MiniSearch를 백엔드로 이동)
- 또는 인덱스 청크 로딩 (5,000개씩 점진 로드)

#### 병목 3: ChromaDB 인덱싱 — 순차 처리

```
reindex_all() → for file in all_files:
                  await read_file(file)      # 디스크 I/O
                  chunk_content(content)      # CPU
                  chroma.upsert(chunks)       # 네트워크 I/O
```

- 파일별 순차 처리, 병렬 없음
- 10,000 파일 × 평균 6 청크 = 60,000 청크 upsert

**해결 방향**:
- asyncio.gather로 파일 읽기 병렬화
- 백그라운드 인덱싱 (save 시 즉시 반환, 비동기 인덱싱)

#### 병목 4: `list_all_files()` — 모든 파일 내용 읽기

```python
for item in self.wiki_dir.rglob("*"):
    wiki_file = await self.read(rel)  # 파일 전체 읽기!
```

- 메타데이터 추출을 위해 **파일 전체를 읽음**
- 10,000 파일 × 평균 5KB = 50MB I/O

**해결 방향**:
- YAML frontmatter만 파싱하는 경량 읽기 함수
- 메타데이터 캐시 (`.ontong/metadata_cache.json`)

---

### 스트레스 테스트 시나리오

아래 스크립트로 대규모 환경을 시뮬레이션하여 실제 병목을 측정합니다.

#### 테스트 1: 대량 파일 생성 + 트리 로딩 시간

```python
"""tests/stress/test_tree_scale.py"""
import asyncio
import time
import httpx

BASE = "http://localhost:8001"

async def create_files(count: int):
    """테스트 파일 대량 생성"""
    async with httpx.AsyncClient() as client:
        for i in range(count):
            folder = f"stress/dept-{i // 100}"
            path = f"{folder}/doc-{i:05d}.md"
            content = f"# Document {i}\n\nThis is test document {i}.\n" + ("Lorem ipsum. " * 50)
            await client.put(f"{BASE}/api/wiki/file/{path}", json={"content": content})
            if i % 100 == 0:
                print(f"  Created {i}/{count} files")

async def measure_tree_load():
    """트리 로딩 시간 측정"""
    async with httpx.AsyncClient() as client:
        start = time.time()
        resp = await client.get(f"{BASE}/api/wiki/tree")
        elapsed = time.time() - start
        tree_size = len(resp.content)
        return elapsed, tree_size

async def measure_search_index():
    """검색 인덱스 로딩 시간 측정"""
    async with httpx.AsyncClient() as client:
        start = time.time()
        resp = await client.get(f"{BASE}/api/search/index")
        elapsed = time.time() - start
        index_size = len(resp.content)
        return elapsed, index_size

async def main():
    scales = [100, 500, 1000, 2000, 5000]

    for count in scales:
        print(f"\n{'='*50}")
        print(f"Scale: {count} files")
        print(f"{'='*50}")

        # 1) 파일 생성
        await create_files(count)

        # 2) 트리 로딩 측정
        tree_time, tree_size = await measure_tree_load()
        print(f"  Tree load: {tree_time:.2f}s ({tree_size/1024:.0f} KB)")

        # 3) 검색 인덱스 측정
        idx_time, idx_size = await measure_search_index()
        print(f"  Search index: {idx_time:.2f}s ({idx_size/1024:.0f} KB)")

        # 4) 리인덱스 측정
        start = time.time()
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(f"{BASE}/api/wiki/reindex")
        reindex_time = time.time() - start
        print(f"  Reindex: {reindex_time:.2f}s")

        # 5) ETag 캐싱 측정 (두 번째 요청)
        async with httpx.AsyncClient() as client:
            resp1 = await client.get(f"{BASE}/api/wiki/tree")
            etag = resp1.headers.get("etag")
            start = time.time()
            resp2 = await client.get(f"{BASE}/api/wiki/tree", headers={"If-None-Match": etag})
            etag_time = time.time() - start
            print(f"  ETag 304: {etag_time:.2f}s (status={resp2.status_code})")

if __name__ == "__main__":
    asyncio.run(main())
```

#### 테스트 2: 동시 사용자 시뮬레이션

```python
"""tests/stress/test_concurrent_users.py"""
import asyncio
import time
import httpx

BASE = "http://localhost:8001"

async def simulate_user(user_id: int, results: list):
    """단일 사용자 동작 시뮬레이션: 트리 → 파일 읽기 → 검색"""
    async with httpx.AsyncClient(timeout=30) as client:
        start = time.time()

        # 1) 트리 로딩
        await client.get(f"{BASE}/api/wiki/tree")

        # 2) 파일 읽기
        await client.get(f"{BASE}/api/wiki/file/stress/dept-0/doc-00001.md")

        # 3) 검색
        await client.get(f"{BASE}/api/search/hybrid", params={"q": "test document", "n": 10})

        elapsed = time.time() - start
        results.append({"user": user_id, "time": elapsed})

async def main():
    concurrency_levels = [10, 25, 50, 100]

    for n_users in concurrency_levels:
        print(f"\n--- {n_users} concurrent users ---")
        results = []
        tasks = [simulate_user(i, results) for i in range(n_users)]

        start = time.time()
        await asyncio.gather(*tasks)
        total = time.time() - start

        times = [r["time"] for r in results]
        avg = sum(times) / len(times)
        p95 = sorted(times)[int(len(times) * 0.95)]

        print(f"  Total: {total:.2f}s")
        print(f"  Avg per user: {avg:.2f}s")
        print(f"  P95: {p95:.2f}s")

        if p95 > 3.0:
            print(f"  ⚠️ P95 > 3초 — 사용자 체감 지연 발생")

if __name__ == "__main__":
    asyncio.run(main())
```

#### 테스트 3: 잠금 동시성

```python
"""tests/stress/test_lock_concurrency.py"""
import asyncio
import time
import httpx

BASE = "http://localhost:8001"

async def lock_unlock_cycle(user_id: int, n_files: int):
    """사용자별 잠금/해제 사이클"""
    async with httpx.AsyncClient() as client:
        for i in range(n_files):
            path = f"stress/dept-{i % 50}/doc-{i:05d}.md"
            await client.post(f"{BASE}/api/lock", json={"path": path, "user": f"user-{user_id}"})
            await client.delete(f"{BASE}/api/lock", json={"path": path, "user": f"user-{user_id}"})

async def main():
    # 50명이 각 20개 파일을 잠금/해제
    n_users = 50
    n_files_per_user = 20

    start = time.time()
    tasks = [lock_unlock_cycle(i, n_files_per_user) for i in range(n_users)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start

    ops = n_users * n_files_per_user * 2  # lock + unlock
    print(f"  {ops} lock ops in {elapsed:.2f}s = {ops/elapsed:.0f} ops/sec")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 테스트 실행 순서

```
Phase  | 테스트                     | 기대 결과                    | 판정
-------|---------------------------|------------------------------|--------
  1    | Part 1 기능 검증 (A~F)     | 모든 기능 정상 동작           | PASS/FAIL
  2    | 스트레스 테스트 1: 파일 규모 | 응답 시간 테이블 산출         | 수치 기록
  3    | 스트레스 테스트 2: 동시 사용 | P95 < 3초                    | 수치 기록
  4    | 스트레스 테스트 3: 잠금 동시 | 1,000+ ops/sec               | 수치 기록
  5    | 결과 종합 → 규모 권장안     | "N천 파일까지 안정" 결론 도출 | 리포트
```

---

## Part 3: 규모 확장이 필요할 때 (10K+ 파일 로드맵)

현재 구현으로 5,000 파일까지 안정적이나, 10,000+ 파일을 지원하려면 추가 최적화가 필요합니다.

| 우선순위 | 작업 | 효과 | 난이도 |
|---------|------|------|--------|
| **P0** | 트리 캐시 (메모리 + 변경시 무효화) | 트리 로딩 10x 가속 | 중 |
| **P0** | 프론트엔드 depth=1 초기 로딩 + subtree lazy load | 초기 렌더링 5x 가속 | 중 |
| **P1** | 서버사이드 검색 (MiniSearch → 백엔드) | 브라우저 OOM 방지 | 상 |
| **P1** | 메타데이터 경량 읽기 (frontmatter만 파싱) | 인덱싱 I/O 80% 감소 | 하 |
| **P2** | 비동기 인덱싱 (save 후 백그라운드) | 저장 응답 즉시 반환 | 중 |
| **P2** | 트리 가상 스크롤 (react-window) | 대용량 폴더 렌더링 | 중 |
| **P3** | ChromaDB 병렬 인덱싱 | 재인덱싱 시간 3x 감소 | 중 |
| **P3** | RAG 사전 필터링 (ACL → ChromaDB where) | 검색 정확도 향상 | 중 |
