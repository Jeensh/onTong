# 환경 변수 레퍼런스

> `.env` 파일 또는 컨테이너 환경에서 설정할 수 있는 모든 변수의 목록입니다.
> 실제 템플릿은 `.env.example` (개발) / `.env.production.example` (운영)을 참고하세요.

---

## 1. LLM 프로바이더

`LITELLM_MODEL`을 `{provider}/{model}` 형식으로 설정하면 자동으로 해당 프로바이더에 연결됩니다.

### Ollama (로컬, 기본값)

```env
LITELLM_MODEL=ollama/llama3
OLLAMA_HOST=http://localhost:11434
```

### OpenAI

```env
LITELLM_MODEL=openai/gpt-4o
LITELLM_API_KEY=sk-your-api-key
```

### Anthropic

```env
LITELLM_MODEL=anthropic/claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-your-key
```

### Google Gemini

```env
LITELLM_MODEL=google/gemini-2.0-flash
GOOGLE_API_KEY=your-key
```

### Azure OpenAI

```env
LITELLM_MODEL=azure/gpt-4o
AZURE_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_API_KEY=your-azure-key
```

### Groq

```env
LITELLM_MODEL=groq/llama3-70b-8192
GROQ_API_KEY=gsk_your-key
```

### DeepSeek

```env
LITELLM_MODEL=deepseek/deepseek-chat
DEEPSEEK_API_KEY=sk-your-key
```

> LLM 없이도 위키 편집, 검색, 파일 뷰어 등 핵심 기능은 모두 동작합니다.

---

## 2. 전체 변수 목록

### 필수/LLM

| 변수 | 기본값 | 설명 |
| ---- | ------ | ---- |
| `LITELLM_MODEL` | `ollama/llama3` | LLM 모델 (`{provider}/{model}` 형식) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama 서버 주소 |
| `LITELLM_API_KEY` | (없음) | OpenAI API 키 |
| `ANTHROPIC_API_KEY` | (없음) | Anthropic API 키 |
| `GOOGLE_API_KEY` | (없음) | Google Gemini API 키 |
| `GROQ_API_KEY` | (없음) | Groq API 키 |
| `DEEPSEEK_API_KEY` | (없음) | DeepSeek API 키 |
| `AZURE_ENDPOINT` | (없음) | Azure OpenAI 엔드포인트 |
| `AZURE_API_KEY` | (없음) | Azure OpenAI API 키 |

### 임베딩 / 벡터 DB

| 변수 | 기본값 | 설명 |
| ---- | ------ | ---- |
| `EMBEDDING_PROVIDER` | `default` | `default` (ChromaDB 내장) / `openai` |
| `OPENAI_API_KEY` | (없음) | 임베딩용 OpenAI API 키 (Python 3.13 환경 필수) |
| `CHROMADB_HOST` | `localhost` | ChromaDB 호스트 |
| `CHROMADB_PORT` | `8000` | ChromaDB 포트 |
| `ENABLE_RERANKER` | `true` | Cross-encoder 리랭킹 활성화 |

### 스토리지

| 변수 | 기본값 | 설명 |
| ---- | ------ | ---- |
| `STORAGE_BACKEND` | `local` | `local` / `nas` |
| `WIKI_DIR` | `wiki` | 위키 파일 저장 경로 (local) |
| `NAS_WIKI_DIR` | (없음) | NAS 마운트 경로 (nas 모드) |

### 캐시 / 분산

| 변수 | 기본값 | 설명 |
| ---- | ------ | ---- |
| `REDIS_URL` | (없음) | Redis 접속 URL (미설정 시 인메모리 폴백) |

### 인증 / 권한

| 변수 | 기본값 | 설명 |
| ---- | ------ | ---- |
| `AUTH_PROVIDER` | `noop` | 인증 제공자 (`noop` / 사내 SSO 연동 등) |

### Section 3 (Simulation)

| 변수 | 기본값 | 설명 |
| ---- | ------ | ---- |
| `SIMULATION_USE_MOCK` | `true` | Section 2 Mock 사용 여부 (false 시 실제 API 호출) |

### 이미지 분석

| 변수 | 기본값 | 설명 |
| ---- | ------ | ---- |
| `IMAGE_OCR_ENABLED` | `true` | EasyOCR 활성화 |
| `IMAGE_OCR_LANGUAGES` | `ko,en` | OCR 언어 |
| `IMAGE_VISION_PROVIDER` | `none` | Vision 모델 (`none` / `ollama` / `openai`) |
| `IMAGE_MAX_CONCURRENT` | `2` | 병렬 분석 수 |

### 런타임 / 로깅

| 변수 | 기본값 | 설명 |
| ---- | ------ | ---- |
| `ENVIRONMENT` | `development` | `development` / `production` |
| `LOG_LEVEL` | `INFO` | 로그 레벨 (DEBUG/INFO/WARNING/ERROR) |

### 모니터링 (선택)

| 변수 | 기본값 | 설명 |
| ---- | ------ | ---- |
| `LANGFUSE_PUBLIC_KEY` | (없음) | Langfuse LLM 관측 |
| `LANGFUSE_SECRET_KEY` | (없음) | Langfuse secret |
| `LANGFUSE_HOST` | (없음) | Langfuse 서버 주소 |

---

## 3. 환경별 권장 조합

### 로컬 개발 (에어갭 시뮬레이션)

```env
LITELLM_MODEL=ollama/llama3
OLLAMA_HOST=http://localhost:11434
EMBEDDING_PROVIDER=default
STORAGE_BACKEND=local
WIKI_DIR=wiki
ENABLE_RERANKER=true
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

### 운영 (클라우드 LLM 사용)

```env
LITELLM_MODEL=anthropic/claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-...
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
STORAGE_BACKEND=nas
NAS_WIKI_DIR=/mnt/nas/ontong/wiki
REDIS_URL=redis://redis:6379/0
ENABLE_RERANKER=true
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 운영 (에어갭)

```env
LITELLM_MODEL=ollama/llama3
OLLAMA_HOST=http://ollama-internal:11434
EMBEDDING_PROVIDER=default
STORAGE_BACKEND=nas
NAS_WIKI_DIR=/mnt/nas/ontong/wiki
REDIS_URL=redis://redis:6379/0
ENABLE_RERANKER=true
ENVIRONMENT=production
LOG_LEVEL=INFO
```

---

## 관련 문서

| 문서 | 설명 |
| ---- | ---- |
| [배포 가이드](deployment.md) | Docker Compose / NAS / 에어갭 배포 |
| [기술 스택 상세](tech-stack.md) | 각 계층 기술 선택 이유 |
