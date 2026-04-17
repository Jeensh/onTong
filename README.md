# onTong

**Knowledge-Fused Multi-Agent Platform for Manufacturing SCM**

위키 지식관리 · 코드–도메인 매핑 · 비즈니스 시뮬레이션을 하나의 애플리케이션으로 통합한 제조 SCM 플랫폼.

---

## 이런 문제를 해결합니다

| 기존 문제 | onTong 해결 방식 |
| --------- | ---------------- |
| 사내 문서가 여기저기 흩어져 있어 찾기 어렵다 | 하이브리드 검색(BM25 + 벡터) + 관계 그래프로 즉시 탐색 |
| 같은 내용의 문서가 여러 버전 존재한다 | 자동 충돌 감지 + 문서 계보(Lineage) 추적 |
| 신입/담당자가 바뀔 때마다 인수인계가 안 된다 | AI Copilot이 문서 기반으로 절차를 즉시 안내 |
| 코드 한 줄 바꿨을 때 어디가 깨지는지 모른다 | 코드 → 도메인 온톨로지 매핑 + 영향 분석 엔진 |
| "폭을 이만큼 바꾸면 어떻게 되지?" 즉시 못 본다 | 파라메트릭 시뮬레이션 + 3D 실시간 시각화 |
| 보안/폐쇄망 환경에서 클라우드 도구를 쓸 수 없다 | 로컬 LLM(Ollama) 지원, 외부 의존성 제로 |

---

## 플랫폼 구조

onTong은 3개 섹션이 하나의 애플리케이션에서 함께 동작합니다.

| 섹션 | 대상 | 주요 기능 | 상태 | 상세 |
| ---- | ---- | --------- | ---- | ---- |
| **Section 1 — Wiki** | 전 직원 | 문서 CRUD · 하이브리드 검색 · AI Copilot · 스킬 시스템 · 이미지 관리 | 운영 중 | [기능 가이드 →](docs/section1-wiki.md) |
| **Section 2 — Modeling** | IT 담당자 | 분석 콘솔 · 매핑 워크벤치 · 영향분석 · 파라메트릭 시뮬레이션 | Phase 1a + 2a 완료 | [기능 가이드 →](docs/section2-modeling.md) |
| **Section 3 — Simulation** | SCM 현업 | Slab 3D 시뮬레이터 · 시나리오 A/B/C 에이전트 · Custom Agent Hub | Phase 1 + 1.5 완료 | [사용자 가이드 →](docs/section3-user-guide.md) · [개발 가이드 →](docs/section3-developer-guide.md) |

> 전체 플랫폼 설계 상세: [platform_architecture_v2.md](toClaude/_shared/reports/platform_architecture_v2.md)

### 섹션별 특징 요약

**Section 1 — Wiki**
Tiptap WYSIWYG 에디터 · WikiLink · Excel/PDF/PPT 뷰어 · Ctrl+K 커맨드 팔레트 · 문서 관계 그래프 · 충돌 감지 대시보드 · 이미지 OCR 검색 · RBAC + 에어갭 지원.

**Section 2 — Modeling**
한국어 자연어로 코드 엔티티를 resolve하고 영향받는 프로세스를 보여주는 **분석 콘솔**, 파일 트리 ↔ 도메인 온톨로지를 드래그-드롭으로 매핑하는 **워크벤치**, 9개 SCM 엔티티의 before/after를 즉시 비교하는 **시뮬레이션 패널**.

**Section 3 — Simulation**
Slab 설계 SEQ 1~16을 실시간 계산하는 **3D 뷰어**, DG320 에러 진단 · Edging 파급효과 · 분할수 최적화를 다루는 **시나리오 A/B/C 에이전트**, 사용자가 직접 설계하는 **Custom Agent Hub** (채팅/양식 빌더).

---

## 아키텍처

```mermaid
graph TB
    subgraph proxy["Reverse Proxy"]
        Nginx(["Nginx · :80"])
    end

    subgraph app["Application"]
        Frontend["Frontend\n Next.js 15 · :3000"]
        Backend["Backend\nFastAPI · :8001"]
    end

    subgraph infra["Infrastructure"]
        ChromaDB[("ChromaDB\n:8000")]
        Redis[("Redis\n:6379")]
        Ollama["Ollama\n:11434"]
    end

    Nginx -->|static| Frontend
    Nginx -->|"/api"| Backend
    Frontend -. "proxy" .-> Backend
    Backend --> ChromaDB
    Backend --> Redis
    Backend --> Ollama

    style proxy fill:#e8f5e9,stroke:#66bb6a,color:#000
    style app fill:#e3f2fd,stroke:#42a5f5,color:#000
    style infra fill:#fff3e0,stroke:#ffa726,color:#000
```

### 기술 스택 요약

| 계층 | 기술 |
| ---- | ---- |
| 프론트엔드 | Next.js 15 · React 19 · Tiptap · shadcn/ui · Zustand · Three.js · react-force-graph-2d |
| 백엔드 | FastAPI · Pydantic v2 · Pydantic AI · aiofiles |
| 벡터 DB | ChromaDB (all-MiniLM-L6-v2) |
| 검색 | BM25 + 벡터 + RRF + Cross-encoder 리랭킹 |
| LLM | Ollama · OpenAI · Anthropic · Google Gemini · Azure · Groq · DeepSeek |
| 그래프 | NetworkX (Section 3) · Neo4j (Section 2 예정) |
| 캐시/락 | Redis 7 (분산 락, 쿼리 캐시, 충돌 스토어) |
| 프록시 | Nginx (로드밸런싱, SSE 지원, gzip) |
| 컨테이너 | Docker Compose, 멀티스테이지 빌드 |

각 기술의 선택 이유: [기술 스택 상세 →](docs/tech-stack.md)

---

## 빠른 시작

### Docker로 전체 실행 (권장)

```bash
git clone https://github.com/Jeensh/onTong.git
cd onTong
cp .env.production.example .env
docker compose up -d
```

브라우저에서 [http://localhost](http://localhost) 접속.

### 개발 모드

```bash
# 인프라
docker compose up -d chroma redis

# 백엔드
python3.13 -m venv venv && source venv/bin/activate
pip install poetry && poetry install
cp .env.example .env
uvicorn backend.main:app --port 8001 --reload

# 프론트엔드
cd frontend && npm install && npm run dev
```

브라우저에서 [http://localhost:3000](http://localhost:3000) 접속.

전체 설치 안내: [빠른 시작 가이드 →](docs/getting-started.md)

### LLM 설정

기본값은 로컬 Ollama(`ollama/llama3`)입니다. OpenAI / Anthropic / Gemini 등으로 바꾸려면 `LITELLM_MODEL`과 API 키만 설정하면 됩니다.

```env
LITELLM_MODEL=anthropic/claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-your-key
```

지원 프로바이더 7종 전체 가이드: [환경 변수 레퍼런스 →](docs/environment-variables.md)

> LLM 없이도 위키 편집, 검색, 파일 뷰어 등 핵심 기능은 모두 동작합니다.

---

## 프로젝트 구조

```
onTong/
├── backend/
│   ├── api/              # Section 1 REST API
│   ├── application/      # Section 1 비즈니스 로직 (Wiki)
│   │   ├── agent/        #   AI 에이전트 (RAG, ReAct, 스킬, 권한)
│   │   ├── skill/        #   스킬 로더, 매처
│   │   ├── wiki/         #   위키 서비스, 인덱서
│   │   ├── conflict/     #   충돌 감지 서비스
│   │   ├── image/        #   이미지 분석 (OCR + Vision)
│   │   └── metadata/     #   메타데이터 서비스
│   ├── modeling/         # Section 2 — 분석 콘솔, 매핑, 시뮬레이션 엔진
│   ├── simulation/       # Section 3 — Slab 에이전트, Custom Agent Hub
│   ├── shared/           # 섹션 간 공유 계약 (typed API contracts)
│   ├── core/             # 설정, 스키마, 인증
│   └── infrastructure/   # 스토리지, 벡터DB, 검색, 캐시
│
├── frontend/src/
│   ├── components/
│   │   ├── simulation/   # Section 3 컴포넌트
│   │   ├── sections/     # Section 2 컴포넌트 + 섹션 네비게이션
│   │   ├── editors/      # 에디터 (MD, Excel, PDF, PPT, Image)
│   │   └── workspace/    # 탭, 파일 라우터
│   └── lib/
│       ├── simulation/   # Section 3 훅/스토어/API
│       ├── workspace/    # Zustand 상태 관리
│       └── api/          # SSE 클라이언트, Wiki API
│
├── docs/                 # 모든 가이드 문서
├── wiki/                 # 위키 콘텐츠 (파일 기반 스토리지)
├── tests/                # 테스트 스위트 (177+ tests)
└── docker-compose.yml    # 전체 서비스 오케스트레이션
```

---

## 테스트

```bash
source venv/bin/activate
pytest tests/ -v          # 전체 (177+ tests)

cd frontend
npx tsc --noEmit          # 타입 체크
npm run build             # 프로덕션 빌드
```

---

## AI 에이전트 협업 방법론

이 프로젝트는 AI 코딩 에이전트(Claude Code)와의 구조적 협업 방법론을 사용해 개발되었습니다. 같은 방식으로 프로젝트를 진행하고 싶다면:

**[Agentic Workflow 가이드 →](agentic-workflow/README.md)**

- 세션 간 컨텍스트 유실 방지
- 파일 기반 작업 추적 (TODO / CHANGES / CHECKLIST)
- 데모–피드백 사이클을 통한 품질 확보
- 프로젝트 규모별 3단계 프리셋 (Light / Standard / Full)

---

## 문서 인덱스

### 시작하기

| 문서 | 설명 |
| ---- | ---- |
| [빠른 시작 가이드](docs/getting-started.md) | 설치, 첫 실행, LLM 설정 |
| [배포 가이드](docs/deployment.md) | Docker Compose / NAS / 에어갭 배포 |
| [환경 변수 레퍼런스](docs/environment-variables.md) | 모든 환경 변수 + 환경별 권장 조합 |

### 기능 가이드

| 문서 | 섹션 |
| ---- | ---- |
| [Section 1 — Wiki 기능 가이드](docs/section1-wiki.md) | 에디터, 뷰어, AI Copilot, 스킬, 검색, 품질 관리, 이미지 |
| [Section 2 — Modeling 기능 가이드](docs/section2-modeling.md) | 분석 콘솔, 매핑 워크벤치, 시뮬레이션 엔진 |
| [Section 3 — Simulation 사용자 가이드](docs/section3-user-guide.md) | Slab 3D 시뮬레이터, 시나리오 A/B/C, Custom Agent |
| [Section 3 — 개발 가이드](docs/section3-developer-guide.md) | 백엔드·프론트엔드 구조, Tool Registry, ReAct 루프 |

### 기술 레퍼런스

| 문서 | 설명 |
| ---- | ---- |
| [기술 스택 상세](docs/tech-stack.md) | 각 기술의 선택 이유 + 사용 방식 |
| [AI 에이전트 아키텍처](docs/agent-architecture.md) | RAG, ReAct, 스킬 시스템, 훅 파이프라인 |
| [스킬 작성 가이드](docs/skill-authoring.md) | 6-Layer 구조, 트리거, 참조 문서 |
| [API 레퍼런스](docs/api-reference.md) | 전체 엔드포인트 + SSE 이벤트 |

### 설계 문서

| 문서 | 설명 |
| ---- | ---- |
| [플랫폼 아키텍처 v2](toClaude/_shared/reports/platform_architecture_v2.md) | 3-Section 전체 설계 (16개 섹션) |
| [Section 3 요구사항](docs/section3-requirements.md) | 도메인 검증 + 계산 공식 |
| [Section 3 로드맵](docs/section3-roadmap.md) | 완료 이력 + 고도화 계획 |
| [superpowers/specs/](docs/superpowers/specs/) | 기능별 설계 명세 (ACL, 이미지, 매핑 등) |
| [superpowers/plans/](docs/superpowers/plans/) | 기능별 구현 플랜 |

---

## 기여

1. Fork
2. 브랜치 생성 (`git checkout -b feature/my-feature`)
3. 커밋 (`git commit -m "feat: add my feature"`)
4. Push (`git push origin feature/my-feature`)
5. Pull Request 생성

> `backend/shared/contracts/` 수정이 포함된 PR은 섹션 간 계약이 걸려 있으므로 팀 리더 리뷰가 필요합니다.

---

## 라이선스

MIT License
