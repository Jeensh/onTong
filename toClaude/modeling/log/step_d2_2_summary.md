# OD-11-D2-2 — Manual Ingest Pipeline + Registry + Upload API

완료일: 2026-04-20
선행: D1 / D1.5 / D1.6 / D2-1 ✅
후행: D2-3 (watch folder + git hook + 프런트 업로드 UI)
누적 테스트: 36 신규 + 329 회귀 = 모델링 범위 0 regression.

---

## 1. 왜 이 스텝인가

D2-1 에서 5 포맷 파서가 `ManualParseResult` 를 뱉을 수 있게 됐지만, 이 결과를
**어디에 저장하고 중복은 어떻게 가리는가** 는 아직 비어 있었다. D2-2 는 다음을 확정한다.

1. **Registry** — 파싱 결과(메타 + 하위 sections/fragments) 를 저장하고, checksum
   중복 / fqn 조회 / Q8=B authoritative 토글을 처리한다.
2. **EmbeddingStore** — Fragment 를 ChromaDB `manual_fragments` 컬렉션에 upsert 한다.
3. **Pipeline** — 파일 경로를 받아 포맷 감지 → 파서 호출 → checksum 단위 중복 스킵 →
   graph / embedding / registry 3 갈래에 쓰기 → `IngestResult` 반환.
4. **API** — `POST /api/modeling/manuals/upload` (multipart) + `GET /manuals` +
   `POST /manuals/{fqn}/authoritative` + `POST /manuals/upload/stream` (SSE).

## 2. 산출물

### 2.1 신규 파이썬 모듈

| 파일 | 역할 |
|---|---|
| `backend/modeling/manual_ingest/manual_registry.py` | `ManualRegistry` Protocol + `ManualRegistryEntry` dataclass + `InMemoryManualRegistry` (primary fqn 인덱스 + secondary checksum 인덱스 + authoritative 토글 model_copy 경유 불변성 보존) |
| `backend/modeling/manual_ingest/embedding_store.py` | `ManualEmbeddingStore` Protocol + `InMemoryManualEmbeddingStore` (section_fqn prefix 매칭 삭제) + `ChromaManualEmbeddingStore` (upsert ids/documents/metadatas + `where={"doc_fqn": ...}` 삭제). 컬렉션 이름 상수 `MANUAL_FRAGMENTS_COLLECTION` |
| `backend/modeling/manual_ingest/pipeline.py` | `IngestMode` (SKIP/UPDATE/FORCE) + `IngestOutcome` (INGESTED/SKIPPED/UPDATED) + `IngestResult` dataclass + `UnsupportedFormatError` + `detect_format` (확장자 → ManualFormat) + `ManualIngestPipeline.ingest(path, *, repo_id, mode, on_progress)` + `ManualGraphWriter` Protocol + `CodeGraphManualWriter` 어댑터 (Manual*→CodeEntity via 기존 `CodeGraphWriter.write_entities`) |
| `backend/modeling/api/manuals_api.py` | `init(pipeline, registry, repo_id)` / `reset()` 싱글턴 + 4 endpoint. SSE 는 worker thread 가 progress 콜백을 queue 에 push, coroutine 이 `asyncio.to_thread(q.get)` 로 drain |

### 2.2 테스트

| 파일 | 개수 | 범위 |
|---|---|---|
| `tests/test_manual_registry.py` | 13 | Protocol 준수 · add/get/remove · `has_checksum` · 같은 fqn overwrite 시 이전 checksum gone · `set_authoritative(True/False)` + missing KeyError · 빈 상태 엣지 |
| `tests/test_manual_ingest_pipeline.py` | 13 | 포맷 라우팅 + `UnsupportedFormatError` · SKIP 모드 dedup · FORCE 모드 재기록 · UPDATE 모드 (다른 checksum 재-ingest + prior delete 호출 / 같은 checksum SKIP) · registry 등록 · graph write / embedding upsert · `detect_format` 매핑 · graph/embedding 없이도 동작 |
| `tests/test_manuals_api.py` | 10 | upload 성공 · dup checksum SKIPPED · `mode=force` re-ingest · 415 unsupported · `GET /manuals` empty/populated · authoritative 토글 True + missing 404 · SSE parsing/complete 이벤트 · 503 uninitialized |

### 2.3 런타임 wiring

- `backend/modeling/api/modeling.py` — `router.include_router(manuals_api.router)` 추가 (기존 ontology/reverse_lookup 와 같은 depth)
- `backend/main.py` lifespan —
  - 5 파서 (`MarkdownParser`/`PdfParser`/`DocxParser`/`PptxParser`/`ImageParser`) 주입
  - `InMemoryManualRegistry` 생성
  - ChromaDB 사용 가능하면 `ChromaManualEmbeddingStore(get_or_create_collection('manual_fragments'))`, 실패/부재 시 `InMemoryManualEmbeddingStore` fallback
  - `graph_writer=None` (D3 에서 Neo4j 실연동 시 `CodeGraphManualWriter(neo4j_graph_writer)` 로 교체 예정)
  - `manuals_api.init(pipeline, registry, repo_id=ONTONG_REPO_ID 또는 "default")`

## 3. 주요 설계 결정

### 3.1 dedup 기준 : fqn + checksum (checksum 단독 X)

파이프라인은 `registry.get_by_fqn(doc_fqn)` 으로 먼저 조회하고, 조회된 entry 의
checksum 이 현재 파일 checksum 과 같으면 SKIP 한다. `has_checksum` 단독으로 판정하지
않는 이유는, **다른 파일명인데 우연히 checksum 이 같은 경우** (예: 다른 문서를 복사해 붙여넣은 경우)
를 오탐 스킵하지 않기 위해서다. 원본 파일명이 FQN 의 근간이므로 이 선택은 안전하다.

### 3.2 업로드 API 의 tempfile 네이밍

멀티파트 업로드를 `tempfile.NamedTemporaryFile` 로 저장하면 파일명이 `manual-upload-xxx`
식으로 달라져서, **동일 내용을 두 번 올리면 FQN 이 매번 달라진다**. 이를 막기 위해
`tempfile.mkdtemp()` 로 전용 디렉터리를 만들고 **원본 파일명을 그대로 유지한 경로**
에 저장한 뒤 정리는 `unlink` + `rmdir` 로 한다. `test_upload_duplicate_checksum_returns_skipped`
가 이 동작에 의존한다 (Red → Green 발견).

### 3.3 UPDATE 모드의 "이전 버전" 정의

UPDATE 모드에서 **이전 버전 제거는 graph + embedding 양쪽에서 수행** 한다. Registry 는
`add()` 시 같은 fqn 을 overwrite 하므로 별도 삭제 호출 불필요. 다만 Neo4j / ChromaDB
는 add-only 성격이라 명시적 삭제가 없으면 고아 fragment 가 누적된다. 따라서 파이프라인은
`mode == UPDATE and existing is not None` 일 때만
`graph_writer.delete_manual` + `embedding_store.delete_document` 를 호출한다. FORCE 모드는
현재 삭제하지 않고 상위 쓰기에만 의존 (향후 필요하면 같은 분기 확장 가능).

### 3.4 GraphWriter 전략 : Manual* → CodeEntity 어댑터

D1.6 에서 `EntityKinds` 에 `manual_document`/`manual_section`/`manual_fragment` 를
이미 등록해 뒀으므로, 별도 그래프 레이어를 새로 만드는 대신
**`CodeGraphWriter.write_entities` 에 kind 만 바꿔 넘기는 어댑터** 를 썼다 (`CodeGraphManualWriter`).

- 장점 : Round 1 Cypher / `_flatten_attributes` / `RelationKindRegistry` 인프라 재사용.
- 단점 : document/section/fragment 간 **containment 관계는 edge 가 아니라 property**
  (`doc_fqn`, `section_fqn`, `parent`) 로만 표현. PART_OF 엣지는 D1 HTML 에서
  BusinessProcess 전용이라 여기서는 쓰지 않는다 (Q1=C 결정과 일치).
- 지금은 `delete_manual` 은 placeholder log — Round 1 `clear_repo` 는 repo 전체 삭제라
  단일 문서 단위 Cypher 가 필요하다. D3 에서 추가 예정.

### 3.5 SSE 어댑터 : 파이프라인은 callback, API 는 queue+thread

파이프라인은 **progress 콜백만 받고** SSE 를 알지 못한다. API 레이어에서
`threading.Thread` 로 `pipeline.ingest()` 를 돌리고, 파이프라인이 콜백을 할 때마다
`queue.Queue` 에 push, coroutine 이 `asyncio.to_thread(q.get)` 로 drain 하며 SSE 프레임
(`event: <name>\ndata: <json>\n\n`) 으로 변환한다. 파이프라인 끝에 sentinel `None`
을 push 해서 stream 종료. 이 분리 덕에 CLI/batch 경로에서도 파이프라인을 재사용 가능.

이벤트 5 종 — `detecting` / `parsing` / `skipped` / `persisting` / `complete`
+ 에러 시 `error` (`{status, message}`).

### 3.6 D2-2 의 graph_writer 기본값 `None`

lifespan 에서 `graph_writer=None` 을 넘긴다. 실제 Neo4j 연결은 D3 (gap detector) 에서
`described_in` / `conflicts_with` / `missing_in` 엣지를 쓸 때 함께 주입한다. D2-2
단계 목표는 "**업로드 흐름 + registry 인덱싱 + 임베딩**" 이며 그래프 단계는 optional —
`test_pipeline_works_without_graph_writer` 로 이 invariant 를 pin 한다.

## 4. 검증

### 4.1 자동 테스트

```bash
.venv/bin/python -m pytest tests/test_manual_registry.py \
  tests/test_manual_ingest_pipeline.py tests/test_manuals_api.py -q
# 36 passed in 0.19s
```

### 4.2 회귀 (modeling 범위)

```bash
.venv/bin/python -m pytest tests/ -q \
  -k "modeling or manual or parser or reverse_lookup or ontology or term_resolver"
# 329 passed, 1068 deselected, 1 warning in 4.90s
```

### 4.3 전체 스위트

```bash
.venv/bin/python -m pytest tests/ -q --ignore=tests/test_frontend
# 21 failed, 1376 passed, 39 warnings in 75.70s
```

- 실패 21건 = Section 1 / RAG / skill 기존 baseline (이번 변경과 무관).
- 새로운 failure 0 건 — D2-2 코드는 기존 테스트에 영향 없음.

### 4.4 런타임 smoke

```bash
.venv/bin/python -c "from backend.main import app; print('OK')"
# Redis query cache failed, falling back to in-memory: No module named 'redis'
# main.py imports OK
```

lifespan 에서 ChromaDB 없는 상태에서도 `InMemoryManualEmbeddingStore` 로 fallback.

## 5. D2-3 진입 조건

다음 스텝 (watch folder + git hook + 프런트 업로드 UI) 은 D2-2 가 제공한
**`ManualIngestPipeline.ingest(path, *, repo_id, mode)`** 를 그대로 쓰면 된다.

- `watch_folder.py` : `watchdog` observer → `IngestMode.UPDATE` 로 콜
- `git_hook_webhook.py` : post-receive webhook → 변경된 파일만 `IngestMode.SKIP` 으로 배치 콜
- 프런트 업로드 UI : `POST /api/modeling/manuals/upload/stream` 을 `EventSource` 로 구독 + 진행률 표시

즉, **D2-2 의 API 와 파이프라인이 D2-3 의 3 트리거 각각에 동일한 엔트리포인트로 작동**
하도록 설계돼 있다. Registry 는 동일 인스턴스를 공유해 dedup 가 서로 인식한다.

## 6. 커밋 파일

- backend/modeling/manual_ingest/manual_registry.py (신규)
- backend/modeling/manual_ingest/embedding_store.py (신규)
- backend/modeling/manual_ingest/pipeline.py (신규)
- backend/modeling/api/manuals_api.py (신규)
- backend/modeling/api/modeling.py (router include 추가)
- backend/main.py (lifespan wiring)
- tests/test_manual_registry.py (신규, 13)
- tests/test_manual_ingest_pipeline.py (신규, 13)
- tests/test_manuals_api.py (신규, 10)
- toClaude/modeling/{TODO,CHANGES,HANDOFF,demo_guide}.md
- toClaude/modeling/log/step_d2_2_summary.md
- toClaude/modeling/archive/step_d2_2_summary.md (사본)
- ~/.claude memory project_status.md
