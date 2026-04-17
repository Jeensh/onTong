# 빠른 시작 가이드

> 처음 onTong을 설치하고 실행하는 방법입니다. 5분 안에 브라우저에서 위키 화면이 뜹니다.

---

## 1. 사전 요구사항

| 구분 | 버전 | 필수 여부 |
| ---- | ---- | --------- |
| Docker & Docker Compose | 20+ | 필수 |
| Node.js | 20+ | 개발 모드 시 |
| Python | 3.10+ | 개발 모드 시 |
| Ollama | 최신 | LLM 기능 사용 시 |

---

## 2. 방법 A — Docker로 전체 실행 (권장)

```bash
# 1. 저장소 클론
git clone https://github.com/Jeensh/onTong.git
cd onTong

# 2. 환경 변수 설정
cp .env.production.example .env

# 3. 전체 서비스 실행
docker compose up -d

# 4. 상태 확인
docker compose ps
curl http://localhost/health
```

브라우저에서 [http://localhost](http://localhost) 접속.

---

## 3. 방법 B — 개발 모드 (소스 직접 실행)

### 3-1. 인프라 서비스

```bash
docker compose up -d chroma redis
```

### 3-2. 백엔드 (포트 8001)

```bash
# 가상환경 생성
python3.13 -m venv venv    # 또는 python3.12
source venv/bin/activate

# 의존성 설치
pip install poetry && poetry install

# 환경 변수 로드
cp .env.example .env
set -a && source .env && set +a

# 서버 실행
uvicorn backend.main:app --port 8001 --reload
```

> macOS 기본 Python(3.9)은 미지원. Python 3.13 + onnxruntime 미지원 시 `OPENAI_API_KEY` 설정.

### 3-3. 프론트엔드 (포트 3000)

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 [http://localhost:3000](http://localhost:3000) 접속.

---

## 4. LLM 설정 (선택)

AI Copilot 기능을 사용하려면 LLM이 필요합니다. `LITELLM_MODEL` 환경 변수를 `{provider}/{model}` 형식으로 설정합니다.

### Ollama (로컬, 기본값)

```bash
ollama pull llama3
```

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

### 그 외 지원 프로바이더

Google Gemini, Azure OpenAI, Groq, DeepSeek 등 7개 프로바이더 지원. 전체 목록: [환경 변수 레퍼런스 →](environment-variables.md)

> LLM 없이도 위키 편집, 검색, 파일 뷰어 등 핵심 기능은 모두 동작합니다.

---

## 5. 정상 동작 확인

```bash
# 1. 백엔드 헬스
curl http://localhost:8001/health
# → "status": "healthy"

# 2. Section 3 헬스
curl http://localhost:8001/api/simulation/health

# 3. Section 2 헬스
curl http://localhost:8001/api/modeling/health

# 4. 브라우저
# http://localhost:3000 → 상단 [Wiki] / [Modeling] / [Simulation] 탭 확인
```

---

## 6. 다음 단계

| 관심사 | 가이드 |
| ------ | ------ |
| Wiki 에디터 + AI Copilot | [Section 1 기능 가이드](section1-wiki.md) |
| 스킬 만들기 | [스킬 작성 가이드](skill-authoring.md) |
| Section 2 Modeling 사용 | [Section 2 기능 가이드](section2-modeling.md) |
| Section 3 Simulation 사용 | [Section 3 사용자 가이드](section3-user-guide.md) |
| Section 3 개발 참여 | [Section 3 개발 가이드](section3-developer-guide.md) |
| 운영 배포 | [배포 가이드](deployment.md) |
| 환경 변수 | [환경 변수 레퍼런스](environment-variables.md) |
