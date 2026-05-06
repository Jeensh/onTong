# Step OD-11-D2-3 — 3 트리거 wiring (watch + git hook + 프론트 업로드 UI) 완료

완료일: 2026-04-21

## 스코프

Manual ingestion 의 3번째 트리거 (Q7=E) 구현. D2-2 에서 준비한
`ManualIngestPipeline.ingest()` + SSE endpoint 를 watch folder + git hook +
프론트엔드 UI 가 공유한다.

## 신규 산출물

### Backend

1. `backend/modeling/manual_ingest/watch_folder.py` (~100 LOC)
   - `ManualFolderWatcher` — 폴링 기반 폴더 감시자, watchdog 무의존
   - `WatchScanResult` dataclass (ingested/removed/skipped_unchanged/errors)
   - mtime+size 스냅샷 비교로 신규/변경 검출 → `IngestMode.UPDATE`
   - `seed_existing=True|False` 플래그 (최초 스캔 동작 선택)
   - 재귀 서브폴더 walk, 지원 확장자만 필터

2. `backend/modeling/manual_ingest/git_hook_webhook.py` (~120 LOC)
   - `GitHookRequest` / `GitHookResponse` frozen dataclass
   - `parse_git_webhook_payload(payload)` — `{repo_root, added, modified, removed}` JSON → DTO
     - 상대 경로는 `repo_root` 기준 resolve
     - 절대 경로는 그대로 resolve
     - `repo_root` 누락 → `ValueError`
   - `ingest_changed_files(request, pipeline, repo_id)`
     - added + modified 순회 → `pipeline.ingest(mode=UPDATE)`
     - 지원 안 되는 확장자 → `skipped` 집계
     - 파일 미존재 → `errors`
     - `repo_root` 밖 경로 → `errors` (path escape 방어)
     - `removed` 는 응답에만 포함 (D3 에서 그래프 반영)

3. `backend/modeling/api/manuals_api.py` 확장
   - `POST /api/modeling/manuals/git-hook` 엔드포인트 추가
   - `GitHookIngestedItem` / `GitHookResponseDTO` Pydantic 응답 모델
   - `asyncio.to_thread(ingest_changed_files, ...)` — 동기 파이프라인을 async 루프에서 안전하게
   - `ValueError` → 400 / 미초기화 → 503 (`_require_initialized()` 재사용)

### Frontend

4. `frontend/src/lib/api/modeling.ts` 확장 (+95 LOC)
   - 타입 : `ManualFormatKind`, `IngestMode`, `IngestOutcome`, `ManualDocumentDto`,
     `ManualUploadResponse`, `ManualListResponse`, `SseEvent`
   - 함수 : `listRegisteredManuals()`, `uploadManual(file, mode)`,
     `toggleManualAuthoritative(fqn, bool)`, `uploadManualStream(file, mode, signal)`
   - `uploadManualStream` 은 POST+SSE 를 fetch + ReadableStream + TextDecoder 로
     구현 (EventSource 는 POST 불가). `\n\n` 경계 버퍼 파서 `parseSseFrame`.

5. `frontend/src/components/sections/modeling/ManualUpload.tsx` (신규, ~230 LOC)
   - 상단 헤더 + 새로고침 버튼
   - 모드 선택 pill (SKIP/UPDATE/FORCE)
   - 파일 드롭존 (클릭/드래그) + accept 필터 (md/pdf/docx/pptx/image)
   - 업로드 중 : SSE 이벤트 라이브 리스트 + spinner
   - 완료/에러 배너
   - 등록된 매뉴얼 목록 + format/version 메타 + authoritative 토글 스위치
     (체크박스 + peer styling, 오프=Draft/온=Authoritative 배지 색상)

6. `frontend/src/components/sections/ModelingSection.tsx` 편집
   - `MAIN_NAV` 에 "매뉴얼 업로드" 탭 추가 (Upload 아이콘, builder 와 ontology 사이)
   - `ModelingView` union 에 `"manual-upload"` 추가
   - `<ManualUpload />` 컴포넌트 렌더링 분기

### 테스트 (신규 3 파일, 30 tests)

7. `tests/test_manual_watch_folder.py` (12 tests)
   - 신규 파일 → ingested, 변경 없음 → noop + skipped_unchanged
   - 수정 감지 → UPDATE mode
   - 재귀 서브폴더, 지원 안 되는 확장자 무시
   - 파서 미등록 시 warning 집계 (raise 없음)
   - `seed_existing=False` → baseline 에만 등록
   - 삭제 파일 → `removed` 리스트
   - 폴더 미존재 → empty result
   - 파일 경로 전달 → `ValueError`
   - 다수 파일 batching, 1개만 변경 시 1개만 UPDATE

8. `tests/test_manual_git_hook_webhook.py` (11 tests)
   - payload 기본 파싱, 필드 누락 시 빈 리스트
   - 절대 경로 / 상대 경로 혼용 resolve
   - `repo_root` 누락 → `ValueError`
   - added → INGESTED, modified → UPDATED (same file)
   - removed → response only
   - 지원 안 되는 확장자 → skipped
   - 빈 페이로드 → 빈 응답
   - 파일 미존재 → errors
   - `repo_root` 밖 경로 거부 → errors

9. `tests/test_manuals_api_git_hook.py` (7 tests)
   - JSON payload → per-file 처리, outcome ingested/updated
   - 지원 안 되는 확장자 → skipped 배열
   - 빈 페이로드, 미초기화(503), repo_root 누락(400)
   - removed 필드 응답 포함

## 설계 결정

- **watchdog 의존성 제거** : 폴링 방식으로 단순화. 호출자가 주기를 제어하거나
  백그라운드 코루틴에서 루프 돌리면 됨. 테스트 결정성 확보 + 1개 deps 감소.
- **mtime + size 스냅샷** : hash 대신 가벼운 key 로 변경 감지 → `pipeline` 내부의
  checksum dedup (D2-2) 과 두 단계로 역할 분리.
- **seed_existing 디폴트 True** : 새로 띄운 인스턴스가 기존 매뉴얼 전부를 한 번에
  인덱싱하는 게 운영 상식에 부합. 재기동 시 checksum dedup 이 자연히 skip 해줌.
- **git hook payload 일반화** : GitHub/GitLab/Gitea 공통 — `{repo_root, added,
  modified, removed}` 최소 형태. 사용자가 post-receive hook 에서 `jq` 등으로
  래핑해 보내도록. webhook provider 별 어댑터는 D4 또는 운영 시 추가.
- **path escape 방어** : `repo_root` 밖 경로는 거부. 악의적 웹훅이 시스템 경로
  (`/etc/passwd` 등) 를 타깃하지 못하도록.
- **removed 는 noop** : D2-3 에서는 삭제 이벤트를 집계만. 그래프 삭제는 D3 Gap
  Detector 가 "기준서에 기술됐으나 현재 문서에 없음" (MISSING_IN) 을 다루는 시점에
  통합 처리.
- **EventSource 대신 fetch streaming** : POST multipart 를 SSE 로 받으려면
  EventSource 로는 불가능. fetch `ReadableStream` + `\n\n` 경계 파싱으로 해결.
  AbortController 로 중간 취소도 지원.
- **프론트 — 업로드 UI 는 readonly 목록 + 토글** : D2-3 범위는 인제스트까지.
  편집 UI (섹션 편집/사람 승인 큐) 는 D4 범위.

## 검증

### Red phase (실패 확인)
```bash
.venv/bin/python -m pytest tests/test_manual_watch_folder.py -x
# ModuleNotFoundError: backend.modeling.manual_ingest.watch_folder
.venv/bin/python -m pytest tests/test_manual_git_hook_webhook.py -x
# ModuleNotFoundError: backend.modeling.manual_ingest.git_hook_webhook
.venv/bin/python -m pytest tests/test_manuals_api_git_hook.py -x
# 404 Not Found (엔드포인트 없음)
```

### Green phase (통과 확인)
```bash
$ .venv/bin/python -m pytest tests/test_manual_watch_folder.py
12 passed in 0.09s

$ .venv/bin/python -m pytest tests/test_manual_git_hook_webhook.py
11 passed in 0.05s

$ .venv/bin/python -m pytest tests/test_manuals_api_git_hook.py
7 passed in 0.16s

$ .venv/bin/python -m pytest \
    tests/test_manual_watch_folder.py \
    tests/test_manual_git_hook_webhook.py \
    tests/test_manuals_api_git_hook.py \
    tests/test_manuals_api.py \
    tests/test_manual_ingest_pipeline.py \
    tests/test_manual_registry.py
66 passed in 0.29s
```

### 모델링 회귀
```bash
$ .venv/bin/python -m pytest tests/ -k "modeling or spring or manual or java_parser or code_analysis or graph_writer or cross_file or parser_protocol or mapping or query_engine or query_models or ontology or concept or term_resolver or reverse_lookup or gap or ingest"
677 passed, 750 deselected in 2.01s
```

### 전체 스위트
```bash
$ .venv/bin/python -m pytest tests/ --tb=no -q
21 failed, 1406 passed, 39 warnings in 58.72s
```
Baseline 21 failures (Section 1 — skill/wiki/RAG/lineage/confidence/metadata) 그대로 유지. D2-2 기준 1376 → 1406 (+30 신규 D2-3 테스트).

### TS / Runtime
```bash
$ cd frontend && npx tsc --noEmit
# (0 errors)

$ .venv/bin/python -c "from backend.main import app; print(f'routes: {len(app.routes)}')"
routes: 152   # D2-2 대비 +1 (/api/modeling/manuals/git-hook)
```

## 엔트리 포인트 요약

### REST
- `POST /api/modeling/manuals/upload`          — 멀티파트 업로드
- `POST /api/modeling/manuals/upload/stream`   — 멀티파트 + SSE
- `POST /api/modeling/manuals/git-hook`        — **D2-3 신규** JSON payload 배치
- `GET  /api/modeling/manuals`                 — 등록 매뉴얼 목록
- `POST /api/modeling/manuals/{fqn}/authoritative` — 승급 토글

### Python
```python
from backend.modeling.manual_ingest.watch_folder import ManualFolderWatcher

watcher = ManualFolderWatcher(
    pipeline=app.state.manual_pipeline,   # backend.main 에서 inject
    folder="/path/to/manuals",
    repo_id="prod",
    seed_existing=True,
)
# 주기적으로 :
result = watcher.scan_once()
# result.ingested / .removed / .skipped_unchanged / .errors
```

### Git hook 사용 예 (git server 의 `post-receive`)
```bash
#!/bin/bash
REPO_ROOT=$(git rev-parse --show-toplevel)
ADDED=$(git diff --name-only --diff-filter=A HEAD~1 HEAD | jq -R . | jq -s .)
MODIFIED=$(git diff --name-only --diff-filter=M HEAD~1 HEAD | jq -R . | jq -s .)
REMOVED=$(git diff --name-only --diff-filter=D HEAD~1 HEAD | jq -R . | jq -s .)
curl -X POST -H "Content-Type: application/json" \
  -d "{\"repo_root\":\"$REPO_ROOT\",\"added\":$ADDED,\"modified\":$MODIFIED,\"removed\":$REMOVED}" \
  http://ontong:8001/api/modeling/manuals/git-hook
```

## D3 진입 조건

D2 Phase 3 subphase 완료 (D2-1 파서 / D2-2 pipeline+API / D2-3 트리거). 다음은
**D3 Gap Detector** :

- `backend/modeling/gap_detection/` 신규 패키지
- Strategy 패턴 2 모드 (hierarchical 3단 rule_ast_differ + embedding_drifter + llm_comparator / llm_only, Q4=C+A)
- CONFLICTS_WITH gap_mode 속성 (Q4 전환) + MISSING_IN 양방향 (Q6=A)
- severity LLM 제안 + 사람 승인 큐 (Q5=A)

또는 D4 UI 디자인 스펙으로 바로 진입 가능 (승인 큐 + Role 관리 + Manual 업로드 UI
확장 + authoritative 토글 연동 — D2-3 업로드 UI 를 기반으로 점진 확장).

사용자 승인 대기.
