# Phase 4: 프로덕션 투입 준비 — 작업 리포트

> 작성일: 2026-03-30
> 총 태스크: 34개 (7 sub-phase) / 전체 완료

---

## 1. Phase 4-A: 에어갭(Air-gap) 대응 (5 tasks)

사내 private망에서 외부 인터넷 없이 동작하도록 모든 외부 의존성 제거.

### 변경 내용

| 항목 | Before | After |
|------|--------|-------|
| PDF.js Worker | `unpkg.com` CDN | `public/pdf.worker.min.mjs` 로컬 파일 |
| 폰트 | `next/font/google` (Geist) | 시스템 폰트 스택 (Pretendard, Apple SD) |
| LLM | `openai/gpt-4o-mini` 기본값 | `ollama/llama3` 기본값 |
| 임베딩 | OpenAI `text-embedding-3-small` | ChromaDB 내장 (all-MiniLM-L6-v2) |

### 수정 파일
- `frontend/src/components/editors/PdfViewer.tsx` — 로컬 worker 경로
- `frontend/src/app/layout.tsx` — Google Fonts 제거
- `frontend/src/app/globals.css` — 시스템 폰트 스택 정의
- `backend/core/config.py` — `litellm_model`, `embedding_provider` 기본값 변경
- `backend/infrastructure/vectordb/chroma.py` — 설정 기반 임베딩 함수 선택
- `scripts/check-external-deps.sh` — 빌드 산출물 외부 URL 검증 스크립트

### 검증 방법
```bash
# 빌드 후 외부 URL 검사
./scripts/check-external-deps.sh
# 네트워크 차단 상태에서 PDF 열기, 폰트 렌더링 확인
```

---

## 2. Phase 4-B: Docker 컨테이너화 (5 tasks)

사내 Docker 환경에서 원클릭 배포.

### 아키텍처
```
docker-compose.yml
├── backend    (Python 3.10-slim, uvicorn)
├── frontend   (Node 20-alpine, Next.js standalone)
├── chroma     (chromadb/chroma:latest)
└── [monitoring profile]
    ├── postgres   (langfuse DB)
    └── langfuse   (observability)
```

### 수정/생성 파일
- `Dockerfile.backend` — 멀티스테이지 빌드 (poetry → slim runtime)
- `frontend/Dockerfile` — 3-stage 빌드 (deps → build → standalone)
- `docker-compose.yml` — 통합 구성 + healthcheck + depends_on
- `.env.example` — 전체 설정 템플릿
- `.env.production.example` — Docker 전용 기본값
- `.dockerignore`, `frontend/.dockerignore` — 빌드 컨텍스트 최적화
- `frontend/next.config.ts` — `output: "standalone"`, `BACKEND_URL` 환경변수

### 핵심 설계 결정
- Next.js `standalone` 모드로 Docker 이미지 크기 최소화 (~150MB)
- `BACKEND_URL` 환경변수로 프록시 대상 설정 가능
- monitoring 서비스는 `--profile monitoring`으로 분리

---

## 3. Phase 4-C: 스토리지 추상화 (4 tasks)

NAS/네트워크 드라이브 대응 가능한 구조.

### 클래스 계층
```
StorageProvider (ABC)
├── LocalFSAdapter — 기존 로컬 파일시스템
└── NASBackend(LocalFSAdapter) — NFS/SMB 마운트 경로 기반
```

### 수정/생성 파일
- `backend/infrastructure/storage/nas_backend.py` — NAS 어댑터 (마운트 경로 검증)
- `backend/infrastructure/storage/factory.py` — `STORAGE_BACKEND` 설정 기반 팩토리
- `backend/core/config.py` — `storage_backend`, `nas_wiki_dir` 설정 추가

### 설정
```env
STORAGE_BACKEND=local    # 또는 "nas"
NAS_WIKI_DIR=/mnt/nas/wiki  # NAS 경로 (nas일 때만 필수)
```

---

## 4. Phase 4-D: 편집 잠금 (4 tasks)

동시 편집 충돌 방지를 위한 문서 잠금.

### 동작 흐름
```
사용자 A: 문서 열기 → POST /api/lock (잠금 획득)
                    → 2분마다 POST /api/lock/refresh
                    → 탭 닫기 시 DELETE /api/lock (해제)

사용자 B: 같은 문서 열기 → GET /api/lock/status → "A가 편집 중"
                        → 읽기전용 모드 + amber 배너 표시
```

### 수정/생성 파일
- `backend/application/lock_service.py` — 인메모리 Lock 관리 (TTL=5분)
- `backend/api/lock.py` — REST API (acquire/release/status/refresh)
- `frontend/src/lib/api/wiki.ts` — Lock API 클라이언트 함수
- `frontend/src/components/editors/MarkdownEditor.tsx` — 잠금 UI 통합

### 핵심 설계 결정
- 인메모리 dict 방식 — 서버 재시작 시 잠금 초기화 (의도적)
- TTL 5분 자동 해제 — 비정상 종료 대비
- 세션 기반 사용자 ID — SSO 연동 전 임시 방안

---

## 5. Phase 4-E: 권한 관리 RBAC (7 tasks)

폴더/문서별 접근 제어 + AI 에이전트 권한 기반 응답.

### ACL 구조
```json
{
  "wiki/hr/": { "read": ["all"], "write": ["hr-team", "admin"] },
  "wiki/finance/": { "read": ["finance-team", "admin"], "write": ["finance-team"] },
  "wiki/public/": { "read": ["all"], "write": ["all"] }
}
```

### 권한 해석 규칙
1. 정확히 일치하는 경로의 ACL 확인
2. 없으면 부모 폴더로 올라가며 탐색
3. 루트까지 없으면 **기본 허용** (open by default)
4. `"all"` 키워드: 모든 사용자에게 허용
5. `"admin"` 역할: 항상 모든 권한 보유

### RAG 권한 필터링
- 벡터 검색 후 **post-filter** 방식
- 검색 결과에서 사용자가 `read` 권한 없는 문서 제외
- `agent.py`에서 `user.roles`를 kwargs로 전달

### 수정/생성 파일
- `backend/core/auth/acl_store.py` — ACL 저장/조회 (JSON 파일)
- `backend/core/auth/permission.py` — `require_read`/`require_write` 의존성
- `backend/api/acl.py` — 관리자용 ACL REST API
- `backend/api/wiki.py` — 읽기/쓰기 API에 권한 체크 적용
- `backend/application/agent/rag_agent.py` — RAG 결과 ACL 필터링
- `frontend/src/components/admin/PermissionEditor.tsx` — ACL 관리 UI

---

## 6. Phase 4-F: 보안 강화 (5 tasks)

### 변경 요약

| 항목 | 구현 |
|------|------|
| 시크릿 관리 | `.env.example` 템플릿, `.gitignore`에 `.pem`, `.key`, `credentials.json` 추가 |
| CORS | 와일드카드 제거, `localhost:3000` 개발용만 허용, 명시적 메서드/헤더 |
| 구조화 로깅 | JSON 포맷, `request_id` ContextVar 추적, pythonjsonlogger v4 |
| 입력 검증 | path traversal 차단 (`..`, `//`, `\`, 제어문자), 콘텐츠 10MB 제한 |
| 에러 핸들러 | 전역 Exception→500, ValueError→400, 일관된 JSON 에러 응답 |

### 수정/생성 파일
- `backend/core/logging_config.py` — RequestIdFilter, JSON 포맷터
- `backend/main.py` — CORS, 미들웨어, 에러 핸들러
- `backend/api/wiki.py` — `_validate_path()`, `SaveRequest` 크기 검증

---

## 7. Phase 4-G: 대규모 대응 (4 tasks)

### 구현 내용

| 항목 | 구현 |
|------|------|
| 검색 페이지네이션 | `/api/search/index`에 `offset`/`limit` 파라미터 |
| 트리 지연 로딩 | `depth` 파라미터 + `GET /tree/{path}` subtree API |
| 배치 인덱싱 | ChromaDB upsert `batch_size=100` |
| ETag 캐싱 | `/api/wiki/tree` MD5 해시 + 304 Not Modified |

---

## 전체 파일 변경 목록

### 신규 파일 (12개)
| 파일 | 용도 |
|------|------|
| `Dockerfile.backend` | 백엔드 Docker 이미지 |
| `frontend/Dockerfile` | 프론트엔드 Docker 이미지 |
| `.dockerignore` / `frontend/.dockerignore` | 빌드 컨텍스트 제외 |
| `.env.production.example` | 프로덕션 환경변수 템플릿 |
| `scripts/check-external-deps.sh` | 외부 의존성 검사 |
| `backend/infrastructure/storage/nas_backend.py` | NAS 스토리지 어댑터 |
| `backend/application/lock_service.py` | 편집 잠금 서비스 |
| `backend/api/lock.py` | Lock REST API |
| `backend/core/auth/acl_store.py` | ACL 저장소 |
| `backend/core/auth/permission.py` | 권한 체크 미들웨어 |
| `backend/api/acl.py` | ACL 관리 API |
| `frontend/src/components/admin/PermissionEditor.tsx` | 권한 관리 UI |

### 수정 파일 (17개)
| 파일 | 변경 내용 |
|------|-----------|
| `frontend/src/components/editors/PdfViewer.tsx` | 로컬 worker |
| `frontend/src/app/layout.tsx` | Google Fonts 제거 |
| `frontend/src/app/globals.css` | 시스템 폰트 스택 |
| `frontend/next.config.ts` | standalone + BACKEND_URL |
| `frontend/src/lib/api/wiki.ts` | Lock API 함수 추가 |
| `frontend/src/components/editors/MarkdownEditor.tsx` | 잠금 UI |
| `frontend/src/components/TreeNav.tsx` | 권한 관리 버튼 |
| `frontend/src/types/workspace.ts` | permission-editor 탭 |
| `frontend/src/lib/workspace/useWorkspaceStore.ts` | 탭 타이틀 |
| `frontend/src/components/workspace/FileRouter.tsx` | PermissionEditor 라우팅 |
| `backend/core/config.py` | LLM/임베딩/스토리지 설정 |
| `backend/infrastructure/vectordb/chroma.py` | 임베딩 함수 선택, 배치 upsert |
| `backend/infrastructure/storage/factory.py` | 팩토리 패턴 |
| `backend/main.py` | CORS, 로깅, 에러핸들러, 라우터 |
| `backend/api/wiki.py` | 권한, 검증, ETag, depth |
| `backend/api/search.py` | 페이지네이션 |
| `backend/application/agent/rag_agent.py` | ACL 필터링 |
| `docker-compose.yml` | 전체 재구성 |
| `.env.example` | 전체 재작성 |
| `.gitignore` | 시크릿 파일 추가 |
