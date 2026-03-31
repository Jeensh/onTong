# 기술 스택 상세

> onTong에서 사용하는 각 기술의 선택 이유, 구체적인 사용 방식, 그리고 프로젝트 내에서의 역할을 설명합니다.

---

## Frontend

### Next.js 15

**역할**: 프론트엔드 프레임워크

**선택 이유**: Standalone 출력 모드가 Docker 컨테이너 배포에 최적화되어 있고, Turbopack으로 개발 시 빌드 속도가 빠릅니다. API Rewrite 기능으로 백엔드 프록시를 설정 파일 한 줄로 처리할 수 있어, 별도의 프록시 미들웨어가 불필요합니다.

**사용 방식**:
- `next.config.ts`에서 `/api/*` 요청을 FastAPI 백엔드(`localhost:8001`)로 프록시
- Standalone 모드로 빌드하여 `node_modules` 없이 경량 Docker 이미지 생성
- Turbopack 활성화(`--turbopack`)로 개발/빌드 속도 향상
- `"use client"` 지시자로 서버/클라이언트 컴포넌트를 명확히 분리

**참고 파일**: `frontend/next.config.ts`, `frontend/Dockerfile`

---

### React 19

**역할**: UI 라이브러리

**선택 이유**: Tiptap 에디터, Zustand 상태 관리, Force Graph 등 프로젝트의 핵심 라이브러리들이 React 훅 기반으로 동작합니다. 19 버전은 개선된 TypeScript 타입 시스템을 제공하며, `useEditor`, `useCallback` 등 훅에서 별도 제네릭 지정 없이 타입이 자동 추론됩니다.

**사용 방식**:
- 커스텀 훅(`useEditor`, `useWorkspaceStore`)으로 에디터와 상태를 관리
- 클라이언트 컴포넌트에서 `useEffect`, `useCallback`으로 API 호출과 이벤트 처리

---

### Tiptap

**역할**: 위키 문서 WYSIWYG 에디터

**선택 이유**: 플러그인 아키텍처 덕분에 WikiLink 노드, 슬래시 명령어 같은 커스텀 기능을 자유롭게 추가할 수 있습니다. ProseMirror 기반이라 복잡한 문서 구조(테이블, 코드 블록, 체크리스트)를 안정적으로 처리하고, 벤더 락인 없이 에디터를 완전히 제어할 수 있습니다.

**사용 방식**:
- **기본 확장**: StarterKit (헤딩, 리스트, 볼드/이탤릭), Table (테이블 편집), Image (이미지 삽입)
- **코드**: CodeBlockLowlight + Lowlight로 구문 강조 코드 블록
- **체크리스트**: TaskItem + TaskList 확장
- **커스텀 확장**:
  - `WikiLinkNode` — `[[문서명]]` 입력 시 자동 인식되는 커스텀 노드
  - `SlashCommandExtension` — `/` 입력 시 명령어 팔레트 표시
  - `PasteHandlerExtension` — Excel 표 붙여넣기 → HTML 테이블 변환
- **자동 저장**: `onUpdate` 콜백에서 3초 디바운스로 서버 저장
- **마크다운 변환**: `marked`(MD→HTML)와 `turndown`(HTML→MD)으로 소스 모드 전환 지원

**참고 파일**: `frontend/src/components/editors/MarkdownEditor.tsx`, `frontend/src/lib/tiptap/`

---

### shadcn/ui

**역할**: UI 컴포넌트 라이브러리

**선택 이유**: 위키 에디터, 커맨드 팔레트, 스킬 생성 다이얼로그 등 onTong의 UI는 범용 디자인 시스템과 맞지 않는 커스텀 레이아웃이 많습니다. shadcn/ui는 스타일이 없는(unstyled) 기본 컴포넌트를 제공하므로, Tailwind CSS로 각 화면에 맞게 자유롭게 커스터마이징할 수 있습니다.

**사용 컴포넌트**: Button, Badge, Command (커맨드 팔레트), Dialog, DropdownMenu, Popover, Select, Input, Textarea, Sonner (토스트 알림)

**스타일링 방식**: `class-variance-authority`(CVA)로 버튼 변형(default, outline, ghost, destructive 등)과 크기(xs, sm, default, lg, icon)를 타입 안전하게 정의

**참고 파일**: `frontend/src/components/ui/`

---

### Zustand 5

**역할**: 클라이언트 상태 관리

**선택 이유**: onTong은 탭 기반 멀티 문서 편집기로, 탭 열기/닫기/정렬, dirty 상태, 검색 쿼리 등 빈번한 상태 변경이 발생합니다. Redux의 action/reducer 보일러플레이트는 이런 간단한 상태에 과하고, Zustand는 `create()` 한 줄로 스토어를 만들어 즉시 사용할 수 있습니다.

**관리하는 상태**:

| 스토어 | 상태 | 주요 액션 |
|--------|------|-----------|
| `useWorkspaceStore` | 열린 탭 목록, 활성 탭, 트리 버전, diff 상태 | `openTab`, `closeTab`, `reorderTabs`, `setDirty` |
| `useSearchStore` | 검색 쿼리, 결과, 검색 모드(local/semantic) | `search`, `searchSemantic`, `toggle` |

- 검색 스토어는 200ms 디바운스로 서버 API 호출
- 워크스페이스 스토어는 탭 드래그 정렬, 경로 변경 시 열린 탭 자동 갱신

**참고 파일**: `frontend/src/lib/workspace/useWorkspaceStore.ts`, `frontend/src/lib/search/useSearchStore.ts`

---

### react-force-graph-2d

**역할**: 문서 관계 그래프 시각화

**선택 이유**: Force-directed 레이아웃은 문서 간 유기적 관계(WikiLink, 계보, 유사도)를 직관적으로 표현하는 데 적합합니다. Canvas 기반 WebGL 렌더링으로 수백 개 노드에서도 부드럽게 동작합니다.

**사용 방식**:
- `next/dynamic`으로 동적 임포트 (SSR 환경에서 Canvas 오류 방지)
- `d3-force`의 `forceRadial`로 중심 노드 기준 원형 배치, 120px 간격 링 레이어
- **노드 색상**: approved(녹색), review(파란), draft(회색), deprecated(빨강), skill(보라)
- **엣지 타입별 시각화**: wiki-link(0.8px), supersedes(1.8px 굵은 선), related(1.2px), similar(0.6px 얇은 점선)
- 호버 시 연결되지 않은 노드 투명도 0.08로 디밍

**참고 파일**: `frontend/src/components/editors/DocumentGraph.tsx`

---

## Backend

### FastAPI

**역할**: REST API 서버 + SSE 스트리밍

**선택 이유**: async/await 네이티브 지원으로 RAG 파이프라인(LLM 호출 + 벡터 검색 + BM25)을 비동기로 병렬 처리합니다. Pydantic 통합으로 요청/응답 자동 검증, OpenAPI 문서 자동 생성이 가능합니다.

**사용 방식**:
- **Lifespan 컨텍스트 매니저**: 앱 시작 시 인증 → 스토리지 → ChromaDB → 인덱싱 → 에이전트 순서로 초기화
- **10개 라우터**: wiki, search, agent, approval, files, metadata, conflict, lock, acl, skill
- **SSE 스트리밍**: `StreamingResponse`로 AI Copilot 토큰 스트리밍, 트리 갱신, 인덱싱 상태 실시간 전달
- **미들웨어**: CORS (명시적 오리진 화이트리스트), Request ID (분산 추적용)
- **헬스체크**: `/health` 엔드포인트에서 ChromaDB 연결, 인덱싱 상태, SSE 구독자 수 노출
- **Uvicorn**: 4 워커, keep-alive 65초, 요청 1만 건 후 워커 재시작(메모리 누수 방지)

**참고 파일**: `backend/main.py`, `backend/api/`

---

### Pydantic v2

**역할**: 데이터 검증 및 직렬화

**선택 이유**: API 경계에서 자동으로 JSON 유효성을 검증하고, `computed_field`로 하위호환 필드를 추가할 수 있습니다. `BaseSettings`로 `.env` 파일과 환경 변수를 타입 안전하게 로딩합니다.

**주요 스키마**:
- `DocumentMetadata` — domain, process, tags, status, supersedes/superseded_by (계보), error_codes
- `WikiFile` — content, raw_content, metadata, links
- `ChatRequest` — session_id, attached_files, skill_path
- SSE 이벤트: `ThinkingStepEvent`, `ContentDelta`, `SourcesEvent`, `ApprovalRequestEvent` 등 `Literal` 타입으로 구분
- 그래프: `GraphNode` (document/skill), `GraphEdge` (wiki-link/supersedes/related/similar)

**참고 파일**: `backend/core/schemas.py`, `backend/core/config.py`

---

### LiteLLM

**역할**: LLM 추상화 레이어

**선택 이유**: 하나의 인터페이스(`acompletion`)로 Ollama(로컬)와 OpenAI(클라우드)를 동일하게 호출합니다. 모델을 `ollama/llama3` → `openai/gpt-4o-mini`로 환경 변수 하나만 바꿔서 전환할 수 있어, 에어갭 환경과 클라우드 환경을 동일 코드로 지원합니다.

**사용 방식**:
- `litellm.acompletion()` — 비동기 LLM 호출 (일반 응답)
- 스트리밍 모드 — async generator로 토큰 단위 SSE 전달
- Tool/Function calling — 에이전트 도구 호출 지원
- **세마포어**: 동시 LLM 호출을 8개로 제한하여 Ollama 과부하 방지
- **기본값**: `ollama/llama3` (로컬, API 키 불필요)

**참고 파일**: `backend/core/config.py`, `backend/application/agent/skills/llm_generate.py`

---

### aiofiles

**역할**: 비동기 파일 I/O

**선택 이유**: onTong은 파일 기반 스토리지를 사용하므로, 문서 저장/조회와 전체 재인덱싱 시 수백 개 파일을 읽고 씁니다. 동기 `open()`을 사용하면 파일 I/O 중 다른 HTTP 요청 처리가 멈추는데, aiofiles는 이를 비동기로 처리하여 FastAPI의 이벤트 루프를 블로킹하지 않습니다.

**사용 방식**:
```python
async with aiofiles.open(path, "r", encoding="utf-8") as f:
    content = await f.read()
```

**사용 위치**: 스토리지 레이어(`local_fs.py`), 스킬 파일 CRUD(`skill.py`)

**참고 파일**: `backend/infrastructure/storage/local_fs.py`, `backend/api/skill.py`

---

## 검색 파이프라인

### rank-bm25 (BM25 키워드 검색)

**역할**: 키워드 기반 텍스트 검색

**선택 이유**: 벡터 검색만으로는 정확한 키워드 매칭(에러 코드, 명령어 이름 등)이 약합니다. BM25가 키워드 정확도를 보완하고, 벡터 검색이 의미적 유사성을 담당하는 하이브리드 구성입니다.

**구현 방식**:
- `BM25Okapi` 알고리즘 사용
- 커스텀 토크나이저: 한국어/영어 혼합 처리, 소문자 변환, 빈 토큰 필터링(len >= 1)
- **백그라운드 데몬 리빌드**: 10초 간격으로 인덱스 갱신, dirty flag로 검색 중 블로킹 방지
- 스레드 안전: Lock으로 동시 접근 보호

**참고 파일**: `backend/infrastructure/search/bm25.py`

---

### ChromaDB (벡터 DB)

**역할**: 문서 임베딩 저장 및 벡터 유사도 검색

**선택 이유**: HTTP 클라이언트 모드로 별도 컨테이너에서 실행되어 백엔드와 독립적으로 스케일링 가능합니다. 내장 임베딩(all-MiniLM-L6-v2)을 지원하여 외부 API 없이 에어갭 환경에서도 동작합니다.

**사용 방식**:
- 컬렉션: `ontong_wiki`, 코사인 거리 사용
- 100건 단위 배치 upsert로 대량 인덱싱 최적화
- **쿼리 API**:
  - `query()` — 텍스트 → 벡터 자동 변환 후 유사도 검색
  - `query_with_filter()` — 메타데이터 조건(status, domain 등) 필터링
  - `query_by_embedding()` — 직접 임베딩 벡터로 검색
  - `get_all_embeddings()` — 충돌 감지를 위한 전체 임베딩 배치 조회
- **임베딩**: 기본 `all-MiniLM-L6-v2` (로컬), 옵션으로 OpenAI Embedding API

**참고 파일**: `backend/infrastructure/vectordb/chroma.py`

---

### Reciprocal Rank Fusion (RRF)

**역할**: 하이브리드 검색 결과 병합

**선택 이유**: BM25와 벡터 검색의 점수 스케일이 다르기 때문에 단순 합산이 불가능합니다. RRF는 순위 기반으로 병합하여 스케일 차이 문제를 자연스럽게 해결하며, 가중치 튜닝이 불필요합니다.

**알고리즘**: `score = Σ(weight / (k + rank))`, k=60 (상수)

**구현 방식**:
- 벡터 검색(async)과 BM25(CPU-bound)를 병렬 실행
- 각 결과의 순위를 RRF 공식으로 변환 후 합산
- 최종 점수 기준 상위 N개 반환

**참고 파일**: `backend/infrastructure/search/hybrid.py`

---

### Cross-encoder 리랭킹

**역할**: 검색 결과 정밀 재정렬

**선택 이유**: BM25+벡터의 1차 검색은 빠르지만 정밀도가 부족합니다. Cross-encoder는 질문과 문서를 함께 입력받아 더 정확한 관련도를 산출합니다. 1차에서 후보를 줄인 뒤 2차로 정밀 정렬하는 2-stage 구조입니다.

**동작 방식**:
1. 하이브리드 검색(BM25 + 벡터)으로 후보 문서 추출
2. LLM에게 질문-문서 쌍을 제시하여 관련도 점수를 산출
3. 관련도 점수 기준으로 최종 상위 N개를 재정렬하여 반환

**설정**: `ENABLE_RERANKER` 환경 변수로 활성화/비활성화 가능 (기본값: `true`). Ollama 등 로컬 LLM에서는 리랭킹 시간이 길어질 수 있으므로, 응답 속도가 우선인 환경에서는 비활성화를 고려하세요.

**참고 파일**: `backend/infrastructure/search/`, `backend/core/config.py`

---

## 인프라

### Redis 7

**역할**: 분산 락 + 충돌 스토어 + 쿼리 캐시

**선택 이유**: 여러 Uvicorn 워커가 동시에 같은 문서를 편집하는 것을 방지하려면 프로세스 간 공유 가능한 락이 필요합니다. Redis가 분산 락, 충돌 감지 결과 캐시, 쿼리 캐시를 하나의 인스턴스로 처리합니다.

**사용 방식**:
- **충돌 스토어**: SHA256 해시 키로 문서 쌍 저장, 파이프라인으로 원자적 다중 키 업데이트
- **LRU 정책**: maxmemory 256MB, 초과 시 가장 오래 사용되지 않은 키 자동 삭제 (컨테이너 메모리 제한은 512MB)
- **폴백**: Redis 미연결 시 `InMemoryConflictStore`로 자동 전환 (개발 환경)

**참고 파일**: `backend/application/conflict/conflict_store.py`, `docker-compose.yml`

---

### Nginx

**역할**: 리버스 프록시 + 로드밸런서

**선택 이유**: 프론트엔드(:3000)와 백엔드(:8001)를 단일 포트(:80)로 통합합니다. SSE 스트리밍을 위한 버퍼링 비활성화와 gzip 압축을 설정 파일 하나로 처리합니다.

**핵심 설정**:
- `/api/*` → 백엔드 프록시, keepalive 32 커넥션
- `/api/events` → SSE 전용: `proxy_buffering off`, 타임아웃 3600초
- `/` → 프론트엔드 프록시, WebSocket 업그레이드 지원 (Next.js HMR/개발용)
- `/health` → 백엔드 헬스체크 직접 노출
- 최대 업로드 50MB, gzip on (JSON/JS/CSS)

**참고 파일**: `nginx.conf`

---

### Docker Compose

**역할**: 멀티 컨테이너 오케스트레이션

**선택 이유**: 5개 서비스(Nginx, Backend, Frontend, ChromaDB, Redis)를 `docker compose up -d` 한 줄로 실행합니다. 각 서비스의 리소스 제한, 헬스체크, 재시작 정책이 선언적으로 정의되어 재현 가능한 배포 환경을 보장합니다.

**서비스별 리소스 제한**:

| 서비스 | CPU | 메모리 | 헬스체크 |
|--------|-----|--------|----------|
| Backend | 4 | 4GB | `/health` 10초 간격 |
| Frontend | 1 | 1GB | wget root |
| ChromaDB | 2 | 2GB | curl API |
| Redis | 1 | 512MB | redis-cli ping |

**추가 기능**:
- `--profile monitoring` 플래그로 Langfuse(LLM 모니터링) + PostgreSQL 선택적 실행
- 영구 볼륨: wiki_data, chroma_data, redis_data

**참고 파일**: `docker-compose.yml`, `Dockerfile.backend`, `frontend/Dockerfile`

---

### Ollama

**역할**: 로컬 LLM 런타임

**선택 이유**: 에어갭(폐쇄망) 환경에서 외부 API 호출 없이 LLM 기능을 제공합니다. API 키 관리가 불필요하고, 데이터가 외부로 유출되지 않아 보안 요구사항을 충족합니다.

**연동 방식**: LiteLLM을 통해 `ollama/llama3`로 호출 (직접 Ollama API를 사용하지 않음)

**운영 설정**:
- 병렬 처리: 4 (단일 GPU 기준 적정치)
- 세마포어: 8 (전체 에이전트 동시 호출 상한)
- 호스트: `http://localhost:11434` (기본값)

**참고 파일**: `backend/core/config.py`

---

## 기타 라이브러리

| 라이브러리 | 역할 | 비고 |
|-----------|------|------|
| `@dnd-kit` | 드래그앤드롭 | 탭 정렬, 트리 노드 이동에 사용 |
| `xlsx` | Excel 파일 읽기/편집 | .xlsx 뷰어/에디터 구현 |
| `react-pdf` | PDF 렌더링 | 페이지 네비게이션, 줌 지원 |
| `react-resizable-panels` | 리사이저블 패널 | 3-Pane 레이아웃 패널 크기 조절 |
| `marked` | Markdown → HTML 변환 | WikiLink 커스텀 확장 포함 |
| `turndown` | HTML → Markdown 변환 | 테이블, 체크리스트 커스텀 규칙 |
| `d3-force` | 그래프 물리 엔진 | react-force-graph-2d 내부 사용 |
| `lucide-react` | 아이콘 라이브러리 | 트리, 에디터 등 전역 아이콘 |
| `next-themes` | 다크 모드 | 시스템 설정 연동 |
| `Tailwind CSS 4` | 유틸리티 CSS | CSS-only 설정 (config 파일 불필요) |
| `Poetry` | Python 의존성 관리 | lock 파일 기반 재현 가능한 빌드 |
| `Langfuse` | LLM 모니터링 | `--profile monitoring`으로 선택적 실행 |
