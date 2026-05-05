# 위키 Rename / 경로 변경 + 동시성 정합성 — 설계서

> 라운드 1·2 브레인스토밍 결과를 통합한 1차 설계서.
> 후속: 본 문서 검토 → 변경/승인 → Phase 0 구현 플랜 (`writing-plans` 스킬).

| 항목 | 값 |
|---|---|
| 작성일 | 2026-05-05 |
| 작성자 | 위키 Claude 세션 |
| 버전 | v0.1 (초안) |
| 상태 | Draft — review 대기 |
| 선행 | `2026-05-05-rename-concurrency-brainstorm-r1.html`, `r2.html` |

---

## 1. 개요

### 1.1 문제 정의

현재 onTong 위키는 문서 간 참조를 4 종 그래프로 관리한다:

1. **L1 — Frontmatter** (`supersedes`, `superseded_by`, `related[]`) : `MetadataIndex` 가 정/역방향 인덱스 보유
2. **L2 — Body wikilink** `[[stem]]` : `WikiSearchService` 가 stem-기반 backlink 만 빌드 (rename 안전성 X)
3. **L3 — Body markdown link** `[text](path.md)` : **추출조차 안 됨**
4. **L5 — ChromaDB chunk metadata `file_path`** : 신규 path 만 갱신, 다른 문서 chunk 본문 안의 path 는 stale

기존 `move_file` / `move_folder` 는 다음과 같이 부분적이고 위험한 처리만 한다:

- `_update_references` 가 `raw.replace(old, new)` naive 치환 → frontmatter 외 코드블록·부분문자열까지 매칭
- `move_folder` 는 **인바운드 참조를 0 줄도 갱신하지 않음**, 전체 reindex 만 트리거
- rename 작업이 편집 락을 검사하지 않음 → 편집 중인 문서를 다른 사용자가 옮길 수 있음
- BG 인덱싱과 race → ghost chunk 잔존 가능
- 멀티 워커 환경에서 BM25 / `MetadataIndex._data` / `IndexStatus` 가 워커별로 드리프트
- 저장 시 load↔save 사이 다른 사용자가 저장한 경우를 감지하는 메커니즘 없음

### 1.2 목표 (Goals)

- **G1** 파일/폴더 rename·move 시 모든 참조 (L1·L2·L3·L5) 가 자동 갱신
- **G2** 수만 동시사용자 환경에서 데이터 손실 0
- **G3** 저장 시점 동시 편집 충돌을 안전하게 인지 + 사용자 머지 가능
- **G4** 100K 코퍼스에서 인기 문서 (1만 inbound) rename 도 progressive 진행
- **G5** 소/중 (10~100명) ↔ 대 (5K~30K명) 환경을 동일 코드로 토글
- **G6** 깨진 링크 검사 도구 제공 (read-only 리포트)
- **G7** 그래프 연결 (L1+L2+L3) 이 inbound 로 존재하는 문서 삭제 차단 (`force=true` 우회 불가; 모든 inbound 를 먼저 정리해야 함)

### 1.3 비목표 (Non-Goals)

- **NG1** CRDT / 실시간 협업 편집 — 자동 저장 모델 아님
- **NG2** UUID 기반 안정 ID — 경로 기반 유지
- **NG3** 이미지 ref `![alt](assets/...)` 자동 이동 — `ImageRegistry` 가 filename 기반이라 영향 없음
- **NG4** 기존 깨진 링크 자동 수정 — 리포트만, 사용자가 수동 처리

### 1.4 가이드 원칙 (라운드 2 사용자 노트 반영)

- **P1** 읽기는 캐시·인덱스로 빠르게. 락은 쓰기 경로에만.
- **P2** 편집 중 (저장 전) 은 자유. 저장·rename 만 정합성 검증.
- **P3** **경로 변경 (rename/move) 와 내용 변경 (edit) 은 별도 서비스 / 별도 큐 / 별도 락 도메인.**
- **P4** 모든 인프라 의존성은 abstract backend 뒤에. `Profile` 으로 dev / team / enterprise 토글.

---

## 2. 핵심 결정 요약

| 결정 | 선택 | 출처 |
|---|---|---|
| 식별 모델 | 경로 기반 | R1.Q3 |
| 동기화 스코프 | L1 + L2 + L3 + L5 (이미지 제외) | R1.Q1 |
| 정확도 | ReferenceIndex (정/역방향) | R2.D1 |
| 락 모델 | Two-Phase + 배치 락 | R2.D2 |
| 충돌 처리 | OCC + 3-way diff | R2.D3 |
| 스냅샷 | 사용자별 N=20, Postgres LOB | R2.D3 + 보조2 |
| 인프라 | Redis + Arq + Postgres ( + ES enterprise) | R2.D4 + 보조1 |
| TX | 진행 + 재시도 큐 + 사용자 알림 | R1.Q5 |
| 락 TTL | 5s | R2.보조2 |
| confirm 임계 | inbound 10 개 초과 | R2.보조2 |
| 청크 batch | 50 개 | R2.보조2 |
| undo 윈도우 | 5 분 | R2.보조2 |
| 인바운드 패치 권한 | 시스템 권한 (ACL 우회) | R3.OQ-1 |
| 스냅샷 보존 | 파일별 N=20, 시간 무제한 | R3.OQ-2 |
| ES 도입 시점 | Phase 6 이후 (enterprise 만) | R3.OQ-3 |
| L5 chunk path 처리 | 텍스트 패치 + 임베딩 재생성 | R3.OQ-4 |
| Bulk 동시 한도 | 사용자당 1 bulk | R3.OQ-5 |
| ContentStore 매체 | NFS 공유 (enterprise) | R3.OQ-6 |
| Profile reload | 재시작 필요 | R3.OQ-7 |
| Delete 정책 (G7) | ReferenceIndex inbound 있으면 차단 | R3 추가 |

---

## 3. 아키텍처

### 3.1 두 갈래 분리 — Path Service vs Content Service

라운드 2 사용자 통찰의 핵심: **경로 변경과 내용 변경은 비용 / 락 / 큐가 완전히 다르다.** 이 분리를 architecture 의 1 등급 결정으로 격상.

```
                        ┌────────────────────────────────────────────┐
                        │              REST / SSE API                │
                        └───────────────┬────────────────────────────┘
                                        │
              ┌──────────────────────────┴──────────────────────────┐
              │                                                       │
   ┌──────────▼───────────┐                          ┌────────────────▼────────────┐
   │  WikiContentService  │                          │      WikiPathService        │
   │  (내용 변경 핫패스)   │                          │   (경로/이름 변경 핫패스)    │
   │                      │                          │                              │
   │  • OCC version 발급  │                          │  • RenameOrchestrator        │
   │  • 본문 저장 + 스냅샷 │                          │  • 영향도 계산 (ReferenceIdx)│
   │  • 청킹·임베딩·BM25   │                          │  • Two-Phase 배치 락        │
   │  • 추출기 → RefIndex │                          │  • 본문 정확 패치 (AST)     │
   │                      │                          │  • Chunk metadata 갱신       │
   └──────────┬───────────┘                          └─────────────┬───────────────┘
              │                                                     │
              │   content lock                                      │   path lock
              │   (per-path, 5s)                                    │   (source + inbound batch)
              │                                                     │
              │   content queue                                     │   path queue
              │   (BG 임베딩, BM25, 스냅샷)                          │   (인바운드 패치, chroma 갱신)
              │                                                     │
              └─────────────────┬───────────────────────────────────┘
                                │
              ┌─────────────────▼─────────────────────────────────┐
              │                    Backends                       │
              │                                                   │
              │   LockBackend  EventBus   ReferenceIndex         │
              │   SnapshotStore  TaskQueue  FullTextSearch       │
              │   MetadataIndex  ContentStore                    │
              └───────────────────────────────────────────────────┘
```

핵심 효과:

1. **rename-only 작업은 임베딩 / BM25 재생성을 트리거하지 않는다.** `WikiContentService.bg_index` 가 호출되지 않음. ChromaDB 는 chunk metadata 의 `file_path` 만 in-place update.
2. **edit-only 작업은 ReferenceIndex / chunk metadata path 갱신을 우회한다.** 단, 본문에서 추출한 reference 가 변하면 ReferenceIndex `add` / `remove` 만 부분 갱신.
3. **edit + rename 동시** 는 두 락을 모두 잡는 정의된 순서 (path → content) 로 진행. 데드락 회피.

### 3.2 컴포넌트 트리 (논리)

| 영역 | 컴포넌트 | 책임 |
|---|---|---|
| Service | `WikiContentService` | save, snapshot, OCC, 추출기 호출, BG 인덱싱 트리거 |
| Service | `WikiPathService` | rename, move, RenameOrchestrator, 영향도 미리보기, broken-link report |
| Service | `LockService` | per-path 락, batch 락 (정렬-순서 데드락 회피) |
| Backend | `LockBackend` | InMemory / Redis |
| Backend | `EventBus` | 단일 프로세스 / Redis Pub/Sub |
| Backend | `ReferenceIndex` | SQLite / Postgres |
| Backend | `SnapshotStore` | filesystem / Postgres LOB / S3 (옵션) |
| Backend | `TaskQueue` | asyncio / Arq + Redis |
| Backend | `FullTextSearch` | BM25 in-memory / Postgres FTS / Elasticsearch |
| Backend | `MetadataIndex` | JSON file / Redis hash |
| Backend | `ContentStore` | LocalFS (현재) / S3-호환 (선택) |
| Domain | `ReferenceExtractor` | frontmatter YAML + body markdown AST → reference 목록 |
| Domain | `RenameOrchestrator` | Plan / Execute / Reconcile 3 단계 |
| Domain | `OCCManager` | version 발급, If-Match 검사, 3-way merge payload |
| Worker | `path-worker` (Arq) | inbound 패치, chunk metadata 갱신 |
| Worker | `content-worker` (Arq) | 청킹, 임베딩, BM25/ES 색인, 스냅샷 |
| Worker | `reconciler` (cron) | RefIndex ↔ 실제 본문 drift 감지 + 자동 수정 |

### 3.3 락 도메인 분리

| 락 | 키 형식 | TTL | 누가 잡나 |
|---|---|---|---|
| **content lock** | `ontong:lock:content:{path}` | 5s | save 트랜잭션 시작 |
| **path lock — source** | `ontong:lock:path:{path}` | 5s | rename 의 source |
| **path lock — inbound batch** | `ontong:lock:path:{inbound_path}` × N | 5s | rename Phase 2 (N=50) |
| **edit session lock** (기존) | `ontong:lock:edit:{path}` | 300s | UI 가 편집 시작 시 |

**데드락 회피 규칙**: rename 시 `[source] + sorted(inbound)` 알파벳 순서로 락 획득. 모든 호출자 동일 순서 준수.

**"편집 중 rename 차단" UX (R1.Q7)** 는 path 락 획득 전 edit session lock 존재 여부 검사. 존재 시 사용자에게 경고.

---

## 4. 데이터 모델

### 4.1 Postgres 스키마 (team / enterprise profile)

```sql
-- 4.1.1 참조 인덱스 (ReferenceIndex 백엔드)
CREATE TABLE wiki_references (
    id           BIGSERIAL PRIMARY KEY,
    source_path  TEXT NOT NULL,           -- 참조하는 문서
    target_path  TEXT NOT NULL,           -- 참조 대상 문서
    kind         SMALLINT NOT NULL,       -- 1=frontmatter_supersedes, 2=frontmatter_superseded_by,
                                          -- 3=frontmatter_related, 4=body_wikilink, 5=body_md_link
    location     JSONB NOT NULL,          -- { offset, length, raw } 정확한 패치를 위한 위치 정보
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_refs_target ON wiki_references (target_path);   -- 역방향 (rename 핵심)
CREATE INDEX idx_refs_source ON wiki_references (source_path);   -- 정방향
CREATE UNIQUE INDEX idx_refs_unique ON wiki_references (source_path, target_path, kind, (location->>'offset'));

-- 4.1.2 OCC version
CREATE TABLE wiki_versions (
    path         TEXT PRIMARY KEY,
    version      TEXT NOT NULL,           -- ULID
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by   TEXT
);

-- 4.1.3 스냅샷 (편집 충돌 복원 + undo)
CREATE TABLE wiki_snapshots (
    id           BIGSERIAL PRIMARY KEY,
    path         TEXT NOT NULL,
    version      TEXT NOT NULL,           -- 매 저장마다 ULID
    content      BYTEA NOT NULL,          -- 압축된 raw 본문 (LOB; ≥ 16KB 면 toast)
    user_name    TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason       TEXT                     -- "save" | "pre_rename" | "pre_merge"
);
CREATE INDEX idx_snap_path_time ON wiki_snapshots (path, created_at DESC);

-- 4.1.4 감사 로그 (rename / move audit)
CREATE TABLE wiki_audit (
    id           BIGSERIAL PRIMARY KEY,
    op           TEXT NOT NULL,            -- "rename" | "move" | "folder_move" | "bulk"
    actor        TEXT NOT NULL,
    payload      JSONB NOT NULL,           -- { from, to, inbound_count, ... }
    started_at   TIMESTAMPTZ NOT NULL,
    finished_at  TIMESTAMPTZ,
    status       TEXT NOT NULL,            -- "running" | "success" | "partial" | "failed"
    error        TEXT
);

-- 4.1.5 작업 큐 항목 (Arq 도 자체 키 사용; 이건 사용자 가시 진행률용)
CREATE TABLE wiki_jobs (
    id           BIGSERIAL PRIMARY KEY,
    audit_id     BIGINT REFERENCES wiki_audit(id),
    kind         TEXT NOT NULL,            -- "patch_inbound" | "update_chunk_meta" | ...
    target_path  TEXT NOT NULL,
    status       TEXT NOT NULL,            -- "pending" | "running" | "done" | "failed"
    attempts     SMALLINT DEFAULT 0,
    last_error   TEXT,
    updated_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_jobs_audit ON wiki_jobs (audit_id);
CREATE INDEX idx_jobs_status ON wiki_jobs (status) WHERE status IN ('pending', 'failed');

-- 4.1.6 broken link 리포트 (read-only view 기반)
CREATE VIEW wiki_broken_refs AS
SELECT r.* FROM wiki_references r
LEFT JOIN wiki_versions v ON v.path = r.target_path
WHERE v.path IS NULL;
```

### 4.2 Redis 키 구조

```
ontong:lock:content:{path}              -- content lock, EX 5
ontong:lock:path:{path}                 -- path lock, EX 5
ontong:lock:edit:{path}                 -- edit session lock, EX 300
ontong:user_locks:{user}                -- SET, 사용자별 보유 락 추적

ontong:event:tree                       -- pub/sub channel: tree_change
ontong:event:index                      -- pub/sub channel: index_status
ontong:event:rename                     -- pub/sub channel: rename progress

ontong:meta:files                       -- HASH, MetadataIndex 캐시 (path → entry json)
ontong:meta:tag_files:{tag}             -- SET, 역방향 인덱스
ontong:meta:domain_files:{domain}       -- SET
ontong:meta:related_index:{target}      -- SET (target 을 related 로 가지는 source 들)
ontong:meta:supersedes_index:{target}   -- SET

ontong:hash:{path}                      -- STRING, content hash (FileHashStore)
ontong:pending:{path}                   -- STRING(timestamp), IndexStatus

arq:queue:path                          -- Arq queue 1: path-worker
arq:queue:content                       -- Arq queue 2: content-worker
```

### 4.3 SQLite 스키마 (dev profile)

`wiki_references`, `wiki_versions`, `wiki_snapshots` 만 동일 형태로 SQLite 에 둔다 (`audit`, `jobs` 는 dev 에서 in-memory 또는 생략 가능).

### 4.4 Elasticsearch 인덱스 (enterprise profile, 옵션)

| 인덱스 | 용도 | 매핑 핵심 |
|---|---|---|
| `wiki-chunks` | BM25 대체 / 한국어 nori | `path` keyword, `heading` text, `content` text(nori), `tags` keyword[], `domain` keyword, `process` keyword, `mtime_epoch` long |
| `wiki-files` | 파일 단위 검색 | `path` keyword, `title` text, `authors` keyword[], `access_read` keyword[] |

---

## 5. 핵심 흐름

### 5.1 Save (내용 저장)

```
1. 클라가 GET /api/wiki/file/{path}
   → 응답에 ETag: <version>, body 에 raw_content + version

2. 사용자가 자유롭게 편집 (락 없음, 자동 저장 없음)

3. 클라가 PUT /api/wiki/file/{path}
   Headers: If-Match: <version>
   Body:    { content }

4. WikiContentService.save():
   a. content lock 획득 (Redis SET NX, EX 5)
   b. OCCManager.check(path, version) → 일치하면 진행, 불일치면 409 + base/server 본문 반환
   c. SnapshotStore.append(path, old_content, old_version, user, reason="save")
   d. ContentStore.write(path, new_content)  -- atomic file rename
   e. 새 version = ULID(); wiki_versions UPDATE
   f. ReferenceExtractor.extract(new_content)
      diff vs 기존 → ReferenceIndex.add / remove (Postgres)
   g. content queue enqueue: bg_index(path)
   h. content lock 해제
   i. EventBus.publish("file_saved", { path, version, user })

5. content-worker 가 bg_index:
   - chunking + embedding + BM25/ES upsert
   - ChromaDB upsert (file_path metadata 포함)
```

**충돌 시 (4b 에서 409)**:

```
응답 body:
{
  "conflict": true,
  "base_version": "<클라가 보낸 version>",
  "server_version": "<현재 버전>",
  "server_content": "<현재 본문>",
  "diff": <unified diff base→server>
}
```

UI 는 3-way diff (base / mine / server) 화면에서 사용자가 머지 → version=server_version 으로 다시 PUT.

### 5.2 Rename (경로 변경)

`RenameOrchestrator.execute(old_path, new_path, actor)`:

```
PHASE 1 — Plan (synchronous, < 100ms 목표)
─────────────────────────────────────────
  1.1 source path lock 획득. 실패 → 409 (다른 사용자가 rename 중)
  1.2 edit session lock 검사. 활성 → 사용자에게 경고 (force=false 면 차단)
  1.3 target collision 검사: ContentStore.exists(new_path) → 충돌 시 409
  1.4 ACL 검사: source write 권한 + new_path 부모 폴더 write 권한
  1.5 ReferenceIndex.inbound(old_path) → 영향 inbound 목록
  1.6 audit 행 생성 (status=running, payload 에 inbound_count)
  1.7 SnapshotStore.append(reason="pre_rename") -- 자기 자신만
  1.8 만약 inbound > confirm_threshold(=10) 이고 force=false:
      → 영향도 미리보기 응답으로 종료 (HTTP 202 + audit_id, 사용자 확인 후 force=true 로 재호출)

PHASE 2 — Execute (synchronous core, async tail)
─────────────────────────────────────────
  2.1 ContentStore.move(old_path, new_path)  -- 파일시스템 atomic
  2.2 ReferenceIndex.rename_target(old_path, new_path)
      -- 역방향 인덱스의 target_path 만 일괄 update (단일 SQL: UPDATE ... WHERE target_path=$1)
  2.3 MetadataIndex.on_path_renamed(old_path, new_path)
      -- 정/역방향 인덱스 모두 갱신
  2.4 wiki_versions UPDATE path=new_path WHERE path=old_path
  2.5 EventBus.publish("file_moved", { old_path, new_path, audit_id })
  2.6 inbound 가 confirm_threshold 이하 → 즉시 동기 패치 (아래 2.7~2.10 인라인)
      초과 → path queue 에 청크 단위 (=50) 작업 enqueue 후 사용자에 audit_id 반환
  
  --- 인바운드 패치 (Phase 2 또는 path-worker) ---
  2.7 path lock 배치 획득 (정렬 순서)
  2.8 각 inbound 문서 (시스템 권한):
      a. content lock 1초 시도 — 실패 시 즉시 path queue 재시도 (사용자 편집 진행 중)
      b. ContentStore.read(inbound_path) + 현재 OCC version 캡처
      c. ReferenceIndex.location.offset 으로 정확 위치 탐색
         (offset 의 raw substring 이 old_path 와 일치하는지 검증; 불일치면 location 마이그레이션 필요 → reconciler 에 위임)
      d. patcher.replace_at_offsets(content, refs_to_old_path, new_path) → 새 content
      e. WikiContentService.save(inbound_path, new_content, version=captured_version, system=True)
         (내부에서 OCC 검사; 충돌 시 1회 재시도 후 path queue 재시도)
      f. ReferenceIndex.update_location() — offset shift 반영
      g. content lock 해제
      (위 e 가 자동으로 content queue 에 bg_index 트리거)
  2.9 chunk metadata + 본문 path prefix 갱신 (OQ-4=A)
      a. ChromaDB metadata.file_path: old_path → new_path 일괄 update (chunk ID 단위)
      b. _build_path_prefix 재생성 — 본문 [분류: ...] [문서: ...] 를 new_path 로
      c. 본문이 바뀌므로 임베딩 재생성 — content queue enqueue: bg_reembed_chunks(new_path)
      d. ES 가용 시 update_by_query 동시 적용
      e. 임베딩 cost 는 audit 진행률에 별도 표시 (사용자가 인지)
  2.10 path lock 해제

PHASE 3 — Reconcile (async, eventual)
─────────────────────────────────────────
  3.1 wiki_jobs 의 failed 항목 재시도 (지수 백오프, 최대 3회)
  3.2 영구 실패 → DLQ + 사용자 알림 + audit status=partial
  3.3 reconciler cron (시간당 1회):
      ReferenceIndex 의 위치 정보 vs 실제 본문 차이 검출 → 자동 재추출
```

### 5.3 Folder rename / move

본질적으로 단일 파일 rename 의 batch:

```
1. 사용자당 1 bulk 락 획득 (OQ-5=B): ontong:lock:bulk:{user}, TTL 1800s
   이미 진행 중인 bulk 가 있으면 409 + "이미 다른 bulk 작업이 진행 중입니다"
2. 서브트리 enumeration (ContentStore.list_subtree)
3. 자기 자신과 자식 파일 모두를 (old_subpath, new_subpath) pair 리스트로 변환
4. RenameOrchestrator 의 dryrun → 총 inbound 개수 + 추정 시간 응답
5. 사용자 확정 시 path queue 에 청크 (=50) 단위 enqueue
6. 각 청크 = 5.2 의 단일 rename 흐름
7. 진행률 SSE: { done, total, failed }
8. 모든 청크 완료 시 bulk 락 해제
```

**주의**: 폴더 이름만 바뀌고 자식 stem 은 그대로 → L2 wikilink 는 stem-resolved 라 영향 없음. 그러나 L3 markdown link `[t](folder/child.md)` 와 L1 frontmatter 는 영향 있음. ReferenceIndex 가 정확히 구분해 처리.

### 5.4 Snapshot 복원 / Undo

```
GET  /api/wiki/snapshots/{path}                  -- 최근 N=20 목록
GET  /api/wiki/snapshots/{path}/{version}        -- 특정 스냅샷 본문
POST /api/wiki/snapshots/{path}/{version}/restore  -- 복원 = 새 save (현재 version 위에 덮어씀)
```

**Undo (rename 직후 5분 윈도우)**:

1. `wiki_audit` 에서 `actor + op=rename + finished_at > now()-5min` 조회 → 대상 audit_id
2. 역방향 plan: 신규 RenameOrchestrator.plan(new_path, old_path, actor=system+actor)
3. source 본문: 5.2 Phase 1.7 에서 저장한 `pre_rename` 스냅샷으로 복원 (`SnapshotStore.get_content`)
4. inbound 본문: `wiki_jobs` 의 audit_id 별 inbound 목록 + 현재 ReferenceIndex 위치 정보 사용해 `new_path → old_path` 역치환. 5분 사이 inbound 가 사용자에 의해 다시 편집됐다면 OCC 충돌 → 그 항목만 partial 표시 + 사용자 알림 (시스템이 사용자 변경을 덮어쓰지 않음).
5. 결과 audit 새로 적재 (op=`undo_rename`, payload에 원 audit_id 참조). 부분 성공 가능.

### 5.5 Broken-link 리포트

```
GET /api/wiki/broken-refs?limit=100&offset=0&kind=body_md_link
→ wiki_broken_refs view 조회
→ { source_path, target_path, kind, location } 목록
```

UI 는 사용자가 클릭하면 source 문서 열고 location 강조.

### 5.6 Delete (그래프 보호 — G7)

`WikiPathService.delete_file(path, actor)`:

```
1. ReferenceIndex.inbound(path) 조회 (모든 kind 포함: L1+L2+L3)
2. 비어있지 않으면 → 409 Conflict
   응답: {
     blocked: true,
     inbound_count: <int>,
     inbound: [{ source_path, kind, location_excerpt }]
   }
   → UI: "이 문서를 N 개 문서가 인용 중입니다. 먼저 인용을 정리하거나
         해당 문서들을 함께 삭제하세요." + 인용 문서 목록 (클릭 시 이동)
3. 비어있으면 진행:
   a. content lock 획득
   b. SnapshotStore.append(reason="pre_delete") — 5분 undo 윈도우용
   c. ContentStore.delete(path)
   d. ReferenceIndex.remove_for_source(path) — outbound 정리
   e. OCCManager: wiki_versions DELETE WHERE path=$1
   f. content queue enqueue: bg_remove_chunks(path) — ChromaDB / BM25 / ES 정리
   g. MetadataIndex.on_file_deleted(path)
   h. EventBus.publish("file_deleted", { path })
4. wiki_audit 적재 (op=delete, payload={ inbound_count: 0 })
5. 5분 윈도우 내 POST /api/wiki/audit/{audit_id}/undo 가능
   복원 흐름: pre_delete 스냅샷 본문으로 새 save → 같은 path 로 부활
```

**force 옵션 없음**: G7 정책상 강제 차단. `force=true` 도 우회 불가. 사용자가 모든 inbound 를 먼저 정리해야 함.

**대량 정리 도구** (Phase 5): broken-link 리포트 페이지에서 일괄 "이 문서로의 참조 모두 제거" 액션 — 인용 측 본문에서 해당 link 노드 자동 삭제 → audit 1건으로 묶임.

### 5.7 ACL 누출 윈도우 (H14) 처리

private → public 폴더 move 시:

```
RenameOrchestrator.execute() 의 2.1 직전:
  acl_store.compute_access_scope(new_path) 미리 계산 → access_scope_new
2.1 ContentStore.move
2.9 chunk metadata 갱신 시 access_read/access_write 도 같은 update_by_query 에 포함
  → file_path 와 access_scope 가 atomic 갱신 (ES bulk single op, ChromaDB metadata.update)
```

ChromaDB 는 metadata.update 가 collection 락이 아닌 ID 단위라 다른 사용자의 검색이 stale chunk 를 잠시 볼 수는 있으나, **public→private 방향만** 위험. 현재 정책상 폴더 ACL 변경은 별도 admin 작업이라 빈도 낮음. enterprise 환경에서 ES bulk + alias swap 으로 추가 강화 가능.

---

## 6. 인터페이스 (Python protocol)

### 6.1 ReferenceIndex

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class Reference:
    source_path: str
    target_path: str
    kind: int                 # RefKind enum
    location: dict             # { offset, length, raw }

class RefKind:
    FM_SUPERSEDES      = 1
    FM_SUPERSEDED_BY   = 2
    FM_RELATED         = 3
    BODY_WIKILINK      = 4
    BODY_MD_LINK       = 5

class ReferenceIndex(Protocol):
    def upsert_for_source(self, source: str, refs: list[Reference]) -> None: ...
    def remove_for_source(self, source: str) -> None: ...
    def inbound(self, target: str, *, kind: int | None = None) -> list[Reference]: ...
    def outbound(self, source: str) -> list[Reference]: ...
    def rename_target(self, old: str, new: str) -> int: ...
    def rename_source(self, old: str, new: str) -> int: ...
    def broken(self, *, limit: int, offset: int, kind: int | None = None) -> list[Reference]: ...
```

### 6.2 SnapshotStore

```python
@dataclass(frozen=True)
class Snapshot:
    path: str
    version: str
    user_name: str
    created_at: float
    reason: str

class SnapshotStore(Protocol):
    def append(self, path: str, content: str, version: str, user: str, reason: str) -> None: ...
    def list(self, path: str, *, limit: int = 20) -> list[Snapshot]: ...
    def get_content(self, path: str, version: str) -> str | None: ...
    def prune(self, path: str, *, keep: int = 20) -> int: ...     # 슬라이딩 윈도우
```

### 6.3 OCCManager

```python
@dataclass(frozen=True)
class ConflictPayload:
    base_version: str
    server_version: str
    server_content: str
    diff_unified: str

class OCCManager(Protocol):
    def issue(self, path: str) -> str: ...                                 # 새 ULID 발급
    def current(self, path: str) -> str | None: ...
    def check(self, path: str, expected: str) -> bool: ...
    def conflict_payload(self, path: str, expected: str) -> ConflictPayload: ...
```

### 6.4 TaskQueue

```python
class TaskQueue(Protocol):
    async def enqueue(self, queue: str, fn: str, *args, retry: int = 3, **kwargs) -> str: ...
    async def progress(self, audit_id: str) -> dict: ...      # { done, total, failed }
    async def cancel(self, audit_id: str) -> None: ...
```

### 6.5 RenameOrchestrator

```python
@dataclass(frozen=True)
class RenamePlan:
    audit_id: str
    inbound_count: int
    confirm_required: bool
    estimated_seconds: float

@dataclass(frozen=True)
class RenameResult:
    audit_id: str
    status: str                 # "success" | "queued" | "partial"
    inbound_done: int
    inbound_failed: int

class RenameOrchestrator(Protocol):
    async def plan(self, old: str, new: str, actor: str) -> RenamePlan: ...
    async def execute(self, audit_id: str, *, force: bool = False) -> RenameResult: ...
    async def undo(self, audit_id: str, actor: str) -> RenameResult: ...
```

### 6.6 ReferenceExtractor

```python
class ReferenceExtractor(Protocol):
    def extract(self, source_path: str, raw_content: str) -> list[Reference]: ...
        # 입력: 본문 raw (frontmatter 포함)
        # 출력: 위치 정보 포함 모든 reference
        # 구현: PyYAML for frontmatter + markdown-it-py for body AST
```

---

## 7. Profile 추상화 — 소/대규모 토글

### 7.1 Profile 정의

```
dev:        InMemory + filesystem (테스트 / 개인 사용)
team:       Redis + Postgres (10~100명, 단일 배포)
enterprise: Redis + Postgres + Elasticsearch (5K~30K명, 멀티 호스트)
```

### 7.2 환경변수

기본 토글:
```
ONTONG_PROFILE=team
```

세밀 토글 (명시 시 profile 위에 덮어쓰기):
```
ONTONG_LOCK_BACKEND=redis|memory
ONTONG_REF_INDEX_BACKEND=postgres|sqlite
ONTONG_SNAPSHOT_BACKEND=postgres|filesystem
ONTONG_TASK_QUEUE_BACKEND=arq|asyncio
ONTONG_FULLTEXT_BACKEND=es|pg_fts|bm25_inmem
ONTONG_METADATA_INDEX_BACKEND=redis|file_json
ONTONG_EVENT_BUS_BACKEND=redis_pubsub|inproc
```

### 7.3 Backend 매트릭스

| 컴포넌트 | dev | team | enterprise |
|---|---|---|---|
| `LockBackend` | InMemory | Redis | Redis |
| `EventBus` | InProcess | Redis Pub/Sub | Redis Pub/Sub |
| `ReferenceIndex` | SQLite | Postgres | Postgres |
| `SnapshotStore` | filesystem | Postgres LOB | Postgres LOB (옵션 S3) |
| `TaskQueue` | asyncio.Queue | Arq + Redis | Arq + Redis |
| `FullTextSearch` | BM25 in-memory | Postgres FTS or BM25 | Elasticsearch (nori) |
| `MetadataIndex` | JSON file | Redis hash | Redis hash |
| `ContentStore` | LocalFS | LocalFS (NFS 공유) | LocalFS (NFS) or S3 |
| `OCCManager` | SQLite | Postgres | Postgres |

### 7.4 토글 안정성 보장

1. **모든 백엔드 protocol 동일** — 같은 메서드 시그니처, 의미 동일
2. **마이그레이션 도구** — Phase 0 의 작업 0-9 로 신설 `ontong` CLI 진입점 도입:
   - `ontong migrate refindex --from sqlite --to postgres`
   - `ontong migrate snapshots --from filesystem --to postgres`
   - `ontong migrate fulltext --from bm25 --to es`
3. **통합 테스트**: dev profile 로 빠르게 (CI 매 PR), team profile 로 nightly (Postgres 컨테이너), enterprise 는 release 전에만
4. **프로파일 검증 endpoint**: `GET /api/wiki/profile-status` → 각 백엔드 ping + 버전 + 카운트
5. **Reload 정책 (OQ-7=A)**: 모든 backend 토글 / Profile 변경은 프로세스 재시작 필요. SIGHUP hot-reload 미지원. 운영 시 점진 롤아웃은 호스트 단위 rolling restart.

### 7.5 마이그레이션 안전성

- ReferenceIndex 는 dump/load 가 멱등 (source_path 단위 upsert)
- SnapshotStore 는 시간 순서만 보존하면 됨, dedup 불필요
- OCC version 은 Postgres 의 `wiki_versions` 가 진실의 원천 — SQLite 로 회귀 시 전체 재발급
- FullText 는 손실 없는 재인덱싱 (raw 본문에서 다시 빌드 가능)

---

## 8. 에러 처리 / 복구

### 8.1 부분 실패 시나리오

| 시나리오 | 처리 |
|---|---|
| `ContentStore.move` 실패 | 즉시 abort, audit status=failed, 사용자 에러 표시 |
| ReferenceIndex `rename_target` 실패 | rollback `ContentStore.move`, audit failed |
| 일부 inbound 패치 실패 | `wiki_jobs.status=failed`, Arq 재시도 (지수 백오프 3회), 영구 실패 시 DLQ (Dead Letter Queue) + audit partial + 사용자 알림 SSE |
| chunk metadata 갱신 실패 (ChromaDB / ES) | 재시도 큐에 재적재, 검색 결과 일시 stale 허용 |
| 스냅샷 저장 실패 | 저장은 성공으로 진행, 경고 로그 (스냅샷은 best-effort) |
| OCC version unique 위반 (race) | 새 ULID 재발급 + 1회 재시도 |

### 8.2 Reconciler

Cron (시간당 1회) :

1. `ReferenceIndex` 의 sample 100 개 source 를 실제 본문에서 재추출 → 차이 발견 시 전체 재추출
2. `wiki_broken_refs` view 카운트가 임계값 (예: 직전 24h 대비 +20%) 초과 시 알림
3. `wiki_jobs` 의 stuck "running" (1h 초과) 항목 재가동
4. 멀티 호스트 환경: `ontong:lock:*` 의 stale lock (TTL 만료된 것이 잔존하는 경우는 Redis 가 자동 처리, 정합성 확인용)

### 8.3 Crash 복구

- 서버 크래시 → Redis 락은 TTL 로 자연 해제, audit `running` 항목은 reconciler 가 처리
- Arq 워커 크래시 → 작업은 자동 재시도 (Arq 보장)
- Postgres 트랜잭션 중간 크래시 → ACID 보장으로 일관성 유지

---

## 9. 보안 / ACL

### 9.1 rename 권한

- source 에 `write` 권한
- target 폴더 ACL 에 `write` 권한
- inbound 패치는 **시스템 권한**으로 진행 (사용자가 inbound 문서에 직접 권한 없어도 ref 갱신 자체는 진행) — `OQ-1` 참조

### 9.2 ACL 누출 윈도우 (H14)

5.7 절 참조. 핵심: ACL 변경과 chunk metadata path 변경을 같은 ES bulk operation 으로 묶음.

### 9.3 Path traversal

기존 `_DANGEROUS_PATH_RE` (`backend/api/wiki.py:20`) 유지. RenameOrchestrator 의 모든 입력 경로에 동일 검증.

### 9.4 Audit 로그 무결성

`wiki_audit` 는 append-only. 이벤트 헤시 체인 (직전 audit hash 를 다음 행에 포함) 은 enterprise 옵션, 기본 X.

---

## 10. 마이그레이션

### 10.1 ReferenceIndex 초기 빌드

전체 코퍼스 1 회 추출 작업. dev 환경 100K 시드 기준 약 5~10 분 추정.

```
ontong migrate refindex-build --batch 1000 --workers 4
```

진행률 SSE 표출. 완료까지 기존 `_update_references` 폴백 유지.

### 10.2 OCC version 초기 부여

```
UPDATE wiki_versions SET version = ulid_from_mtime(mtime_epoch) WHERE version IS NULL;
```

또는 실시간 lazy: 첫 GET 시 버전 발급.

### 10.3 스냅샷

마이그레이션 시점부터 누적. 이전 히스토리 없음.

### 10.4 점진 활성화

- Phase 0~1 끝에 ReferenceIndex 가 read-only 로 가용 → 기존 `_update_references` 와 병렬 운용, 결과 비교
- Phase 3 끝에 신규 `RenameOrchestrator` 가 메인 경로, 기존 코드 deprecated
- Phase 6 끝에 기존 코드 제거

### 10.5 NFS SPOF 경고 (OQ-6=A)

enterprise profile 의 ContentStore 는 NFS 단일 마운트. NFS 서버 장애 시 모든 호스트의 위키 접근 불가. 운영 권장:

- HA NFS (Pacemaker + DRBD, 또는 Ceph FS)
- 정기 NFS 백업 (rsync 또는 zfs snapshot)
- 호스트별 mount 모니터링 (Prometheus `node_filesystem_avail_bytes`)
- 향후 S3-호환 마이그레이션 시 atomic rename 보장 위해 Two-Phase commit 코드 추가 필요 (현재 deferred)

---

## 11. 테스트 전략

### 11.1 단위 테스트

- `ReferenceExtractor` — 다양한 markdown / frontmatter 케이스 (코드블록 안 link, 중첩 list, escaped bracket)
- `OCCManager` — version 비교, 동시 발급
- `RenameOrchestrator.plan` — inbound count, ACL 검사, edit lock 검사
- 데드락 회피: 정렬 순서 락 획득 시뮬레이션

### 11.2 통합 테스트

- dev profile + team profile 양쪽 동일 시나리오 매트릭스
- 핵심 시나리오:
  - file rename → inbound 5 개 패치 → broken-ref view 비어 있음
  - folder rename 100 개 자식 → 청크 진행 → 모든 wiki_jobs done
  - 동시 save (OCC 충돌) → 409 + 3-way diff payload
  - rename + concurrent edit → edit lock 차단 또는 충돌 감지
  - rename 중 서버 재시작 → reconciler 가 partial 복구

### 11.3 부하 테스트

| 환경 | 시드 | 동시 사용자 | SLA |
|---|---|---|---|
| dev | 1K 문서 | 10 | rename inbound 100 ≤ 1s |
| team | 10K 문서 | 100 | rename inbound 100 ≤ 2s |
| enterprise | 100K 문서 | 5K | rename inbound 100 ≤ 2s, inbound 1K ≤ 30s, inbound 10K progressive ≤ 5min |

**SLA 외 측정 (OQ-4=A 의 영향)**:
- chunk 본문 path prefix 재생성 → 임베딩 재계산 비용
- rename 1 회당 평균 chunk 수 × 임베딩 latency
- 인기 문서 (chunk 50 개) rename 시 약 5~10s 추가 예상 (사용 모델에 따라 변동)
- enterprise profile 에서 P95 측정 + audit 진행률에 분리 표시

`locust` 또는 `k6` 시나리오:

- 70% read (GET file/tree/search)
- 20% save (PUT file)
- 5% rename (PATCH file)
- 5% folder ops

### 11.4 회귀 가드

- 기존 105 개 테스트 통과 유지
- `tests/test_rename_concurrency.py` 신규 — 위 통합 시나리오 자동화

---

## 12. 운영

### 12.1 메트릭 (Prometheus)

```
wiki_rename_duration_seconds{inbound_size_bucket}
wiki_rename_failures_total{phase}
wiki_save_conflict_total
wiki_snapshot_storage_bytes
wiki_ref_index_size
wiki_broken_refs_total{kind}
wiki_queue_lag_seconds{queue}
wiki_lock_contention_total{lock_type}
wiki_occ_version_collision_total
```

### 12.2 알람

- rename SLA 위반 (P95 > 임계)
- DLQ 누적 (1h > 50)
- ReferenceIndex drift > 0.1% (reconciler 결과)
- 스냅샷 스토리지 > 80% capacity

### 12.3 운영 명령

```
ontong refindex rebuild [--source PATH | --all]
ontong refindex verify [--sample N]
ontong snapshot prune --keep 20
ontong audit list --since 24h --status partial
ontong rename undo <audit_id>
```

---

## 13. Phase 분해

라운드 2 D5 동의된 P0~P6. 각 phase 완료 시 데모 가능한 산출물 + 테스트 통과 + Step Completion Protocol (`CLAUDE.md`) 7 단계 모두 수행.

### Phase 0 — 인프라 추상화 + 백엔드 (선행 0)

**목표**: 모든 인프라 의존성을 protocol 뒤로 추상화. dev 와 team profile 동시 가용.

작업:
- 0-1 Profile 시스템: `ONTONG_PROFILE` 환경변수 + 컴포넌트별 토글
- 0-2 `LockBackend`: InMemory + Redis (이미 있음, 활성화 + 통합)
- 0-3 `EventBus` Redis Pub/Sub adapter
- 0-4 `MetadataIndex` Redis hash 백엔드 + 마이그레이션 도구
- 0-5 `FileHashStore` / `IndexStatus` Redis 백엔드
- 0-6 Postgres 스키마 마이그레이션 (alembic 권장)
- 0-7 Arq 워커 도입 (`path-worker`, `content-worker` 큐 분리)
- 0-8 `GET /api/wiki/profile-status` endpoint
- 0-9 `ontong` CLI 진입점 (`backend/cli/__main__.py`) — migrate 명령 골격

산출물: dev / team 프로파일 동작 검증 페이지, 마이그레이션 가이드.

### Phase 1 — ReferenceIndex + 추출기 (선행 P0)

**목표**: 정/역방향 참조 인덱스 가용 + 깨진 링크 리포트.

작업:
- 1-1 `ReferenceExtractor` (markdown-it-py + PyYAML)
- 1-2 `wiki_references` Postgres 테이블 + `ReferenceIndex` 구현
- 1-3 `WikiContentService.save` 핫패스에 추출기 wiring (기존 `_update_references` 와 병렬)
- 1-4 마이그레이션 명령 `ontong migrate refindex-build`
- 1-5 broken-link `wiki_broken_refs` view + `GET /api/wiki/broken-refs`
- 1-6 broken-link 리포트 UI 페이지
- 1-7 **Delete 차단 정책 (G7)** — `WikiPathService.delete_file` 가 ReferenceIndex.inbound() 검사. 비어있지 않으면 409 + 인용 문서 목록 (force 옵션 없음). §5.6 흐름 구현. 5분 undo.

산출물: 100K 시드 추출 ≤ 10분, broken-link 리포트 페이지 동작, inbound 있는 문서 삭제 시 409 + 인용 목록 응답.

### Phase 2 — OCC + 스냅샷 (선행 P0, P1 과 병렬 가능)

**목표**: 저장 시 충돌 감지 + 3-way diff + undo 기반.

작업:
- 2-1 `wiki_versions` 테이블 + `OCCManager`
- 2-2 `GET /api/wiki/file/{path}` ETag 헤더 + body version 필드
- 2-3 `PUT /api/wiki/file/{path}` `If-Match` 검사 → 409 + ConflictPayload
- 2-4 `wiki_snapshots` + `SnapshotStore` (Postgres LOB)
- 2-5 매 save 마다 pre-image 스냅샷 + 슬라이딩 N=20
- 2-6 프론트 3-way diff UI (`diff-match-patch` 또는 `diff` 라이브러리)
- 2-7 `GET /api/wiki/snapshots/{path}` + 복원 endpoint
- 2-8 마이그레이션: 기존 파일 lazy version 부여

산출물: 동시 저장 시뮬레이션 → 한쪽이 conflict UI 진입 → 머지 → 두 변경 모두 보존.

### Phase 3 — 단일 파일 rename/move (선행 P1 + P2)

**목표**: `RenameOrchestrator` 가 single-file rename 의 정합성 핵심을 담당.

작업:
- 3-1 `RenameOrchestrator.plan` — ACL, edit lock 검사, 영향도 산정
- 3-2 source path lock + Two-Phase 배치 락 (정렬 순서)
- 3-3 inbound 정확 패치 (offset 기반, ReferenceIndex 위치 정보 사용)
- 3-4 ChromaDB chunk metadata path patch + ES 동기 (가용 시)
- 3-5 `wiki_audit` + `wiki_jobs` 진행률 추적
- 3-6 SSE `rename_progress` 이벤트
- 3-7 `GET /api/wiki/rename-preview/{path}?to=...` (영향도 미리보기)
- 3-8 `PATCH /api/wiki/file/{path}` 가 신규 orchestrator 사용 (기존 코드 deprecated)
- 3-9 실패 항목 재시도 큐 + DLQ + 사용자 알림 SSE
- 3-10 5 분 윈도우 undo

산출물: file rename 시 모든 inbound 갱신, 부하 100K + 동시 100 사용자 시 SLA 만족.

### Phase 4 — 폴더 / bulk (선행 P3)

**목표**: 서브트리 작업 = P3 의 batched 호출.

작업:
- 4-1 서브트리 enumeration + (old, new) 페어 리스트
- 4-2 폴더 rename dryrun (총 inbound 합산)
- 4-3 청크 (=50) 단위 path queue enqueue
- 4-4 진행률 집계 SSE
- 4-5 다중 선택 드래그 앤 드롭 bulk 지원

산출물: 100 자식 폴더 rename 진행률 표시, 부분 실패 시 일부만 재시도.

### Phase 5 — UX 마감 (선행 P3, P4 와 일부 병렬)

작업:
- 5-1 영향도 미리보기 다이얼로그 (`> 임계값 confirm`)
- 5-2 편집 중 rename 경고 / 차단 (`edit session lock` 검사)
- 5-3 진행률 토스트 + 결과 뱃지
- 5-4 undo 버튼 (5 분 윈도우)
- 5-5 broken-link 리포트 페이지 (P1 산출물 통합)

### Phase 6 — 스케일 검증 (선행 P3~P5)

작업:
- 6-1 100K 시드 + 동시 50/500/5000 사용자 부하 시나리오 (locust/k6)
- 6-2 SLA 가드 (CI nightly)
- 6-3 ACL 누출 윈도우 측정 (H14)
- 6-4 enterprise profile 활성화 검증 (LockBackend, EventBus, MetadataIndex 모두 Redis)
- 6-5 **Elasticsearch 도입 (OQ-3=C)** — nori analyzer 매핑 + alias swap 마이그레이션 + BM25 → ES 회귀 테스트 + 한국어 형태소 분석 검증
- 6-6 (조건부) chunk 본문 path prefix 비용이 SLA 위반 시 OQ-4 의 B/C 옵션 평가

---

## 14. Open Questions

**라운드 3 (2026-05-05) 에서 OQ-1~7 모두 결정됨** — §2 결정 표 참조. 본 절은 신규 OQ 발생 시 추가용 placeholder.

---

## 15. 변경 로그

| 버전 | 일자 | 작성자 | 변경 |
|---|---|---|---|
| v0.1 | 2026-05-05 | 위키 Claude 세션 | 초안 — 라운드 1·2 통합 |
| v0.2 | 2026-05-05 | 위키 Claude 세션 | 라운드 3 OQ-1~7 결정 반영 + G7 Delete 차단 정책 추가 + §5.6 Delete 흐름 + §13 Phase 1 작업 1-8 + Phase 6 작업 6-5/6-6 + §10.5 NFS SPOF |

---

## 부록 A. 라운드 1 가설 → 본 설계 매핑

| 가설 | 처리 |
|---|---|
| H1 wikilink 부패 | ReferenceIndex L2 + body 정확 패치 (Phase 1+3) |
| H2 markdown link 부패 | L3 추출기 + 패치 |
| H3 stem 충돌 | ReferenceIndex 가 path 기반이라 stem 모호성 제거 |
| H4 folder move inbound 0 | Phase 4 가 P3 batch 로 처리 |
| H5 naive replace | offset-기반 정확 패치 |
| H6 rename + edit race | edit session lock 검사 + path lock |
| H7 동일 target 충돌 | RenameOrchestrator.plan 의 collision check |
| H8 인덱싱 중 rename | content/path 락 분리 + audit 추적 |
| H9 inbound 비원자성 | wiki_jobs 재시도 + reconciler |
| H10 멀티워커 드리프트 | Redis 외부화 (Phase 0) |
| H11 audit 부재 | wiki_audit 테이블 |
| H12 dryrun/undo 부재 | plan 단계 + 5분 undo |
| H13 hot doc 성능 | Two-Phase 배치 + progressive 청크 |
| H14 ACL 누출 | 5.6 atomic ES bulk |
| H15 락 미적용 | edit session lock 검사 + path lock |
| H16 throttle 부재 | Arq 큐 자체 rate limit + audit 빈도 메트릭 |
