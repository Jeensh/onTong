# 배포 가이드

> onTong을 운영 환경에 배포하는 방법과 구성 옵션을 정리한 문서입니다.

---

## 1. Docker Compose (권장)

5개 서비스(Nginx, Backend, Frontend, ChromaDB, Redis)를 한 번에 실행합니다.

```bash
# 환경 변수 설정
cp .env.production.example .env
# .env 파일을 편집하여 LLM, 스토리지 등 설정

# 전체 서비스 실행 (백엔드 4 워커, 리소스 제한 포함)
docker compose up -d

# 모니터링 포함 실행 (Langfuse + PostgreSQL)
docker compose --profile monitoring up -d

# 상태 확인
docker compose ps
curl http://localhost/health
```

이후 [http://localhost](http://localhost)에서 접속할 수 있습니다.

### 서비스별 리소스 제한

| 서비스 | CPU | 메모리 | 헬스체크 |
| ------ | --- | ------ | -------- |
| Backend | 4 | 4GB | `/health` 10초 간격 |
| Frontend | 1 | 1GB | wget root |
| ChromaDB | 2 | 2GB | curl API |
| Redis | 1 | 512MB | redis-cli ping |

---

## 2. NAS 스토리지 연결

여러 인스턴스가 동일한 위키 데이터를 공유하려면 `.env`에서 다음을 설정합니다.

```env
STORAGE_BACKEND=nas
NAS_WIKI_DIR=/mnt/nas/ontong/wiki
```

NAS 마운트 예시(docker-compose override):

```yaml
services:
  backend:
    volumes:
      - /mnt/nas/ontong/wiki:/app/wiki
```

---

## 3. 에어갭 (폐쇄망) 배포

onTong은 외부 네트워크 없이 완전히 동작하도록 설계되어 있습니다.

- **LLM**: Ollama 로컬 모델 (기본값)
- **임베딩**: ChromaDB 내장 all-MiniLM-L6-v2
- **프론트엔드**: 외부 CDN/폰트 의존성 없음
- **검증**: `scripts/check-external-deps.sh`로 빌드 결과물 확인

```bash
# 에어갭 의존성 검증
cd frontend && npm run build
../scripts/check-external-deps.sh
```

### 에어갭 체크리스트

- [ ] `LITELLM_MODEL=ollama/llama3` (또는 사내 호스팅 LLM)
- [ ] `EMBEDDING_PROVIDER=default` (ChromaDB 내장)
- [ ] 외부 CDN/폰트 없음 (`check-external-deps.sh` 통과)
- [ ] NAS/내부 스토리지만 사용
- [ ] Docker 이미지 사내 레지스트리로 미러링

---

## 4. 개발 모드 (소스 직접 실행)

Docker 없이 소스에서 직접 실행합니다.

### 터미널 1 — 인프라 서비스

```bash
docker compose up -d chroma redis
```

### 터미널 2 — 백엔드

```bash
# 가상환경 생성 (Python 3.10+)
python3.13 -m venv venv    # 또는 python3.12
source venv/bin/activate

# 의존성 설치
pip install poetry && poetry install

# 환경 변수 로드
cp .env.example .env
set -a && source .env && set +a

# 서버 실행 (포트 8001)
uvicorn backend.main:app --port 8001 --reload
```

> macOS 기본 Python(3.9)은 지원하지 않습니다. `python3.13` 또는 `python3.12` 경로를 명시하세요.
> Python 3.13에서는 onnxruntime 미지원으로 ChromaDB 내장 임베딩이 동작하지 않습니다. 이 경우 `OPENAI_API_KEY`를 설정하여 OpenAI 임베딩을 사용하세요.

### 터미널 3 — 프론트엔드

```bash
cd frontend
npm install
npm run dev   # 포트 3000
```

[http://localhost:3000](http://localhost:3000)에서 접속합니다. 포트 충돌 시 `PORT=3001 npm run dev`.

---

## 5. 수평 확장

| 구성 요소 | 확장 방식 |
| --------- | --------- |
| Backend | Uvicorn 4 워커 기본, 추가 인스턴스는 Nginx upstream 블록에 등록 |
| Frontend | stateless, 여러 인스턴스 간 라운드로빈 가능 |
| ChromaDB | HTTP 클라이언트 모드로 별도 인스턴스 운영 가능 |
| Redis | 분산 락, 쿼리 캐시, 충돌 스토어 공용. Sentinel/Cluster 고려 |

### Nginx upstream 예시

```nginx
upstream ontong_backend {
    server backend1:8001;
    server backend2:8001;
    keepalive 32;
}
```

---

## 6. 테스트

```bash
source venv/bin/activate
pytest tests/ -v          # 전체 (177+ tests)
pytest tests/test_skill_loader.py tests/test_skill_matcher.py tests/test_skill_api.py -v  # 스킬 시스템만
```

프론트엔드:

```bash
cd frontend
npx tsc --noEmit          # 타입 체크
npm run build             # 프로덕션 빌드
```

---

## 관련 문서

| 문서 | 설명 |
| ---- | ---- |
| [환경 변수 레퍼런스](environment-variables.md) | 모든 환경 변수 목록 |
| [기술 스택 상세](tech-stack.md) | 각 계층 기술 선택 이유 |
| [API 레퍼런스](api-reference.md) | 전체 엔드포인트 목록 |
