# Phase 4-A/B/C Summary — 에어갭 + Docker + 스토리지

> 완료일: 2026-03-29 | 14 tasks 완료

## 변경 사항

### Phase 4-A: 에어갭 대응 (5 tasks)
- PDF.js worker: `unpkg.com` CDN → `public/pdf.worker.min.mjs` 로컬 파일
- Google Fonts: `next/font/google` (Geist) → 시스템 폰트 스택 (Pretendard, system-ui)
- LLM 기본값: `claude-3-5-sonnet` → `ollama/llama3` (에어갭 안전)
- 임베딩: 설정 기반 (`EMBEDDING_PROVIDER=default/openai`), OpenAI import를 lazy로 변경
- 점검 스크립트: `scripts/check-external-deps.sh` — 빌드 산출물 외부 URL 스캔

### Phase 4-B: Docker 컨테이너화 (5 tasks)
- `Dockerfile.backend`: Python 3.10-slim 멀티스테이지, healthcheck 포함
- `frontend/Dockerfile`: Node 20-alpine 멀티스테이지 + standalone 출력
- `docker-compose.yml`: backend + frontend + chroma 통합, monitoring은 profile로 분리
- `.env.production.example`: 프로덕션 환경 변수 템플릿
- `.dockerignore`: 백엔드/프론트엔드 각각 최적화

### Phase 4-C: 스토리지 추상화 (4 tasks, 2 기존 완료)
- `NASBackend`: LocalFSAdapter 서브클래스, 마운트 경로 검증 포함
- 팩토리: `STORAGE_BACKEND=local/nas` 설정 기반 전환
- Config: `storage_backend`, `nas_wiki_dir`, `embedding_provider` 추가
- `next.config.ts`: `output: "standalone"` + `BACKEND_URL` 환경변수 지원

## 검증 결과
- ✅ `npm run build` 성공
- ✅ 외부 의존성 점검 PASS (node_modules 제외)
- ✅ 백엔드 config/factory 정상 작동
- ✅ StorageProvider ABC → LocalFSAdapter → NASBackend 상속 구조 검증

## 수정된 파일
| 파일 | 변경 |
|------|------|
| `frontend/src/components/editors/PdfViewer.tsx` | worker URL 로컬화 |
| `frontend/src/app/layout.tsx` | Google Fonts 제거 |
| `frontend/src/app/globals.css` | 시스템 폰트 스택 |
| `frontend/next.config.ts` | standalone + BACKEND_URL |
| `frontend/Dockerfile` | 신규 |
| `frontend/.dockerignore` | 신규 |
| `frontend/public/pdf.worker.min.mjs` | 신규 (worker 복사) |
| `backend/core/config.py` | 설정 추가 |
| `backend/infrastructure/vectordb/chroma.py` | 임베딩 설정 기반 |
| `backend/infrastructure/storage/nas_backend.py` | 신규 |
| `backend/infrastructure/storage/factory.py` | 설정 기반 팩토리 |
| `backend/main.py` | 로그 개선 |
| `Dockerfile.backend` | 신규 |
| `docker-compose.yml` | 전체 리빌드 |
| `.env.example` | 전면 갱신 |
| `.env.production.example` | 신규 |
| `.dockerignore` | 신규 |
| `scripts/check-external-deps.sh` | 신규 |
