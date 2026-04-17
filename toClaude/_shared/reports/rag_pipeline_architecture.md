# onTong RAG 파이프라인 아키텍처

> 발표용 리포트 | 작성일: 2026-03-26 | 갱신: 2026-03-28 (Phase 2-A 고도화 반영)

---

## 1. 전체 흐름 요약

```
┌─────────────────── 문서 저장 단계 ───────────────────┐
│                                                       │
│  사용자가 Wiki 문서 저장 (Ctrl+S)                      │
│       ↓                                               │
│  WikiService.save_file()                              │
│       ↓                                               │
│  로컬 디스크 저장 (wiki/*.md)                          │
│       ↓                                               │
│  WikiIndexer.index_file()                             │
│       ↓                                               │
│  마크다운 → 섹션별 청킹 (heading 기반, 500 토큰 단위)   │
│       ↓                                               │
│  ChromaDB.upsert()                                    │
│  [텍스트 → OpenAI 임베딩 → 벡터 저장 + 메타데이터]      │
│                                                       │
└───────────────────────────────────────────────────────┘
                         ↓
┌─────────────────── AI 질의 단계 ─────────────────────┐
│                                                       │
│  사용자가 AI Copilot에 질문 입력                       │
│       ↓                                               │
│  POST /api/agent/chat (SSE 스트리밍)                   │
│       ↓                                               │
│  MainRouter: 의도 분류 (키워드 → LLM 2단계)            │
│       ↓                                               │
│  RAGAgent.execute()                                   │
│       ↓                                               │
│  ChromaDB.query() — 질문 임베딩 → 코사인 유사도 검색    │
│       ↓                                               │
│  상위 5개 관련 문서 청크 조회                           │
│       ↓                                               │
│  LLM에 컨텍스트 주입 + 스트리밍 답변 생성               │
│       ↓                                               │
│  SSE 이벤트: sources → content_delta → done            │
│                                                       │
└───────────────────────────────────────────────────────┘
```

---

## 2. 단계별 상세 설명

### Stage 1: 문서 저장 → 인덱싱 트리거

```python
# WikiService.save_file()
async def save_file(self, path: str, content: str) -> WikiFile:
    wiki_file = await self.storage.write(path, content)   # 디스크 저장
    await self.indexer.index_file(wiki_file)               # 즉시 인덱싱
    return wiki_file
```

**핵심 설계**: 저장과 인덱싱이 **동기적**으로 처리됩니다. 저장 완료 = 검색 반영 완료. 비동기 큐 없이 일관성을 보장합니다.

---

### Stage 2: 마크다운 청킹

문서를 통째로 벡터화하면 검색 정확도가 떨어지므로, **헤딩 기반 섹션 분할**을 합니다.

| 파라미터 | 값 | 설명 |
|---------|---|------|
| MAX_CHUNK_TOKENS | 500 | 청크당 최대 토큰 수 |
| OVERLAP_TOKENS | 50 | 청크 간 겹침 (문맥 연속성) |
| 토큰 추정 | `len(text) // 3` | 한영 혼합 기준 |

**청킹 알고리즘**:

```
원본 문서
├── # 주문 처리 규칙 (H1)
│   └── 본문 텍스트... → Chunk 0: "order-processing-rules.md::chunk_0"
├── ## 주문 상태 전이 (H2)
│   └── 본문 텍스트... → Chunk 1: "order-processing-rules.md::chunk_1"
├── ## 핵심 규칙 (H2)
│   ├── ### Rule 1: 유효성 검증
│   │   └── 본문... → Chunk 2 (500토큰 이하)
│   ├── ### Rule 2: 재고 할당
│   │   └── 본문이 길면 → Chunk 3_0, Chunk 3_1 (50토큰 겹침)
```

**청크 ID 규칙**: `{파일경로}::chunk_{인덱스}` (하위 분할 시 `_sub_idx` 추가)

---

### Stage 3: 벡터 저장 (ChromaDB)

각 청크가 다음 데이터와 함께 ChromaDB에 저장됩니다:

```
ChromaDB Document
├── id: "order-processing-rules.md::chunk_0"
├── document: "주문 처리 비즈니스 규칙..."  ← 임베딩 대상 텍스트
├── embedding: [0.023, -0.105, ...]         ← OpenAI text-embedding-3-small
└── metadata:
    ├── file_path: "order-processing-rules.md"
    ├── heading: "주문 처리 규칙"
    ├── domain: "SCM"
    ├── process: "주문처리"
    ├── tags: "|주문 처리|재고 관리|FIFO 원칙|"   ← 파이프 구분자
    ├── error_codes: "|DG320|"
    └── author: "admin"
```

**파이프 구분자 형식**: ChromaDB의 `$contains` 쿼리를 위해 `|tag1|tag2|` 형태로 저장합니다.

```python
# 검색 시
where = {"tags": {"$contains": "|FIFO|"}}  # FIFO 태그를 가진 청크만 검색
```

---

### Stage 4: 의도 분류 (2단계 라우터)

사용자 질문이 들어오면 어떤 AI 에이전트가 처리할지 결정합니다.

```
사용자 메시지
    ↓
[Tier 1] 키워드 매칭 (정규식, 0ms)
    "주문 처리 규칙 알려줘"
    → "(장애|대응|절차|규칙|룰|정책|가이드)" 매칭
    → WIKI_QA (confidence: 0.8)
    ↓ (매칭 실패 시)
[Tier 2] LLM 분류 (GPT-4o-mini, ~500ms)
    → WIKI_QA / SIMULATION / DEBUG_TRACE / UNKNOWN
    → confidence: 0.7
```

| 에이전트 | 역할 | 트리거 키워드 |
|---------|------|-------------|
| **WIKI_QA** | 지식 검색 + 답변 | 문서, 규칙, 절차, 가이드 |
| **SIMULATION** | 예측/최적화 | 시뮬레이션, 예측, 파라미터 |
| **DEBUG_TRACE** | 장애 추적 | 추적, 디버그, 왜 사라졌는지 |

---

### Stage 5: RAG 실행

#### 5-1. 벡터 검색

```python
results = chroma.query(query_text="주문 처리 규칙", n_results=5)
# 또는 메타데이터 필터 포함:
results = chroma.query_with_filter(query_text=..., where={"domain": "SCM"})
```

반환값:
```python
{
    "documents": [["청크1 텍스트", "청크2 텍스트", ...]],
    "metadatas": [[{"file_path": "...", "heading": "..."}, ...]],
    "distances": [[0.17, 0.25, ...]]  # 코사인 거리 (낮을수록 유사)
}
```

#### 5-2. 출처 생성

```python
relevance = max(0, 1 - distance)  # 거리 → 유사도 변환
# distance 0.17 → relevance 0.83 (83% 관련)
```

중복 제거 후 SSE `sources` 이벤트로 전송:
```json
{"event": "sources", "sources": [
    {"doc": "order-processing-rules.md", "relevance": 0.83}
]}
```

#### 5-3. LLM 답변 스트리밍

검색된 문서를 컨텍스트로 주입하여 답변을 생성합니다:

```
System Prompt:
"당신은 제조 SCM 도메인의 지식 관리 AI 어시스턴트입니다.
 아래 Wiki 문서 컨텍스트를 기반으로 사용자의 질문에 정확하게 답변하세요.
 답변에는 출처 문서를 언급하세요.
 컨텍스트에 없는 내용은 추측하지 마세요.

 ## Wiki 컨텍스트
 {검색된 문서 청크들 (---로 구분)}"

User: "주문 처리 규칙 알려줘"
```

LLM 응답은 토큰 단위로 스트리밍됩니다:
```
event: content_delta → {"delta": "주"}
event: content_delta → {"delta": "문"}
event: content_delta → {"delta": " 처리"}
...
event: done → {"usage": {"output_tokens": 150}}
```

---

### Stage 6: Wiki 문서 생성 (승인 흐름)

사용자가 "~~ 문서 만들어줘"라고 하면 별도 흐름을 탑니다:

```
사용자: "캐시 장애 대응 문서 만들어줘"
    ↓
_detect_write_intent() → True
    ↓
LLM에게 문서 생성 요청 (JSON 형식)
    ↓
{"path": "캐시-장애대응.md", "content": "# 캐시 장애 대응\n\n..."}
    ↓
미리보기 생성 (상위 20줄)
    ↓
SessionStore에 PendingAction 저장
    ↓
SSE event: approval_request
    {"action_id": "uuid", "path": "캐시-장애대응.md", "diff_preview": "..."}
    ↓
사용자가 승인/거절
    ↓
POST /api/approval/resolve → WikiService.save_file() 실행
```

---

## 3. SSE 이벤트 흐름 (실제 예시)

사용자가 "주문 처리 규칙 알려줘"를 입력했을 때:

```
→ POST /api/agent/chat {"message": "주문 처리 규칙 알려줘"}

← event: routing
← data: {"agent": "WIKI_QA", "confidence": 0.8}

← event: sources
← data: {"sources": [{"doc": "order-processing-rules.md", "relevance": 0.83}]}

← event: content_delta
← data: {"delta": "주문 처리"}

← event: content_delta
← data: {"delta": "에 대한 비즈니스 규칙은"}

  ... (토큰 단위 스트리밍) ...

← event: content_delta
← data: {"delta": "입니다."}

← event: done
← data: {"usage": {"input_tokens": 0, "output_tokens": 156}}
```

---

## 4. 사용 기술 스택

| 계층 | 기술 | 역할 |
|------|------|------|
| 임베딩 | OpenAI `text-embedding-3-small` | 텍스트 → 1536차원 벡터 |
| 벡터 DB | ChromaDB (Docker) | 벡터 저장 + 코사인 유사도 검색 |
| LLM | GPT-4o-mini (via LiteLLM) | 답변 생성, 의도 분류, 문서 생성 |
| 스트리밍 | SSE (Server-Sent Events) | 실시간 토큰 스트리밍 |
| 백엔드 | FastAPI + uvicorn | 비동기 API 서버 |
| 메타데이터 | YAML Frontmatter | 문서 내 구조화 메타데이터 |

---

## 5. 핵심 설계 결정과 근거

| 결정 | 근거 |
|------|------|
| **동기적 인덱싱** | 저장 즉시 검색 반영 — Phase 1에서 일관성 > 성능 |
| **헤딩 기반 청킹** | 의미 단위 보존, 500토큰 제한으로 임베딩 품질 유지 |
| **50토큰 겹침** | 청크 경계에서 문맥 손실 방지 |
| **파이프 구분자 메타데이터** | ChromaDB `$contains` 쿼리로 다중 태그 필터링 가능 |
| **2단계 라우터** | 키워드 매칭(~0ms) → LLM fallback(~500ms) 순서로 비용 최소화 |
| **OpenAI 임베딩** | text-embedding-3-small — 비용 효율 + 한국어 성능 양호 |
| **SSE 스트리밍** | WebSocket 대비 구현 단순 + 단방향 스트리밍에 적합 |
| **Human-in-the-Loop** | 문서 자동 생성 시 사용자 승인 필수 — 안전장치 |

---

# Phase 2-A: RAG 성능 고도화 (2026-03-28)

> Phase 1에서 구축한 기본 파이프라인의 **응답 속도**와 **검색 품질**을 6단계에 걸쳐 최적화한 내용입니다.

---

## 6. 고도화 전체 파이프라인 흐름도

```
사용자 질문
    │
    ├─ 라우팅 (키워드 ~0ms) ──────┐
    │                              │ asyncio.gather (병렬)
    ├─ 쿼리 보강 (LLM, 후속만) ───┘
    │
    ▼
메타데이터 필터 추출 (규칙 기반, ~0ms)       ← [P2A-5]
    │
    ▼
캐시 확인 ──── HIT → 즉시 결과 반환          ← [P2A-4]
    │
   MISS
    │
    ├─ 벡터 검색 (ChromaDB) ──┐
    │                          │ RRF 병합    ← [P2A-2]
    ├─ BM25 키워드 검색 ──────┘
    │
    ▼
Cross-encoder 리랭킹 (LLM, optional)        ← [P2A-6]
    │
    ▼
명확화 체크 (규칙 기반, ~0ms)                ← [P2A-1]
    │
    ▼
인지 반영 (Cognitive Reflection, LLM, 숨김)
    │
    ▼
최종 답변 스트리밍 (LLM, SSE)
```

---

## 7. Step P2A-1: LLM 호출 병렬화 + 제거

### 7-1. 문제

RAG 파이프라인에서 LLM을 여러 번 **순차 호출**하면 대기 시간이 누적됩니다.

```
[기존] 순차 실행 — 최악 시나리오
  라우팅(LLM)  →  쿼리보강(LLM)  →  명확화(LLM)  →  답변(LLM)
  ~700ms          ~1200ms            ~700ms
  ────────── 총 대기: ~2600ms + 답변 생성 시간 ──────────
```

### 7-2. 해결: 3가지 최적화

#### (a) 키워드 라우팅 커버리지 확대

```python
# 기존: 13개 패턴
KEYWORD_RULES = [
    (r"(장애|대응|절차|규칙|룰|정책|가이드)", "WIKI_QA", 0.8),
    ...
]

# 개선: 25개 패턴 + 한글 catch-all
KEYWORD_RULES = [
    ...기존 패턴...,
    # 기업/도메인 용어 추가
    (r"(회의|미팅|일정|스케줄|공지|안내|보고|보고서)", "WIKI_QA", 0.70),
    (r"(매뉴얼|SOP|표준|기준|규정|규격)", "WIKI_QA", 0.75),
    (r"(MES|ERP|SCM|CRM|PLM|DG\d{3})", "WIKI_QA", 0.70),
    # catch-all: 한글 2자 이상이면 WIKI_QA로 분류
    (r"[가-힣]{2,}", "WIKI_QA", 0.50),
]
```

**결과**: 12개 테스트 쿼리 중 **11개 키워드 매칭** (92%). LLM 폴백은 영어 쿼리 1건뿐.

#### (b) asyncio.gather — 라우팅 + 쿼리보강 병렬 실행

```python
# 기존: 순차 실행
decision = await main_router.route(message)        # ~700ms (LLM 시)
augmented_query = await rag_agent._augment_query()  # ~1200ms
# 총: ~1900ms

# 개선: asyncio.gather로 병렬
decision, augmented_query = await asyncio.gather(
    main_router.route(message),          # ─┐
    rag_agent._augment_query(message),   # ─┘ 동시 실행
)
# 총: max(700, 1200) = ~1200ms  → 700ms 절감
```

#### asyncio.gather 상세 설명

`asyncio.gather`는 Python의 비동기 동시 실행 도구입니다.

```python
# 핵심 원리
results = await asyncio.gather(coroutine_A, coroutine_B)
```

- 두 코루틴을 **이벤트 루프에 동시에 등록**
- 각각 독립적으로 I/O 대기 (네트워크 요청 등)
- **모두 완료될 때까지** 대기 → 결과를 튜플로 반환

```
시간 →
                    0ms                    700ms               1200ms
                     │                       │                    │
  라우팅 (LLM)  ─────┤███████████████████████│                    │
                     │                       │                    │
  쿼리보강 (LLM) ────┤██████████████████████████████████████████████│
                     │                       │                    │
                     ├───── 기존: 순차 = 1900ms ──────────────────│
                     ├───── 개선: 병렬 = 1200ms ─────────────────→│
                     │       (느린 쪽만 대기)                      │
```

**중요 전제**: 두 작업이 서로 **독립적**이어야 합니다.
- 라우팅: 사용자 메시지만 필요 ✓
- 쿼리보강: 사용자 메시지 + 대화 이력만 필요 ✓
- 서로의 결과를 참조하지 않음 → 병렬 안전

**에러 처리**: `asyncio.gather`는 하나가 실패하면 기본적으로 예외를 전파합니다.
하지만 라우팅/쿼리보강 각각 내부에서 try/except로 안전하게 처리되어 있어 전체 파이프라인이 멈추지 않습니다.

#### (c) 명확화 체크 → 규칙 기반 전환

```python
# 기존: LLM 호출 (~700ms)
clarification = await self._check_clarity(query, documents, metadatas, distances)

# 개선: 규칙 기반 (~0ms)
def _check_clarity_rule_based(self, query, metadatas, distances):
    # 1. 특정 엔티티(이름, 에러코드) 있으면 → CLEAR
    if re.search(r'[A-Z]{2,}|[가-힣]{2,4}(님|씨)|[A-Z]+[-_]?\d+', query):
        return None

    # 2. 검색 결과가 1건 이하 → 그냥 사용
    if len(unique_files) <= 1:
        return None

    # 3. 여러 후보 → 선택지 목록 생성 (LLM 없이)
    return "Wiki에서 관련 문서를 찾았습니다.\n1. **출장규정**\n2. **재고관리** — SCM\n..."
```

### 7-3. 개선 효과

```
[개선 후]
  라우팅 (키워드) ─┐ ~0ms
                    │ asyncio.gather
  쿼리보강 (LLM) ──┘ ~1200ms (후속 질문만)
  명확화 (규칙) ──── ~0ms
  ─────────────────────────
  총 절감: ~1400ms (순차 대비 ~54%)
```

---

## 8. Step P2A-2: 하이브리드 검색 (벡터 + BM25)

### 8-1. 문제

벡터 검색은 **의미적 유사성**에 강하지만, **정확한 키워드 매칭**에 약합니다.

```
질문: "DG320 에러 대응 방법"

벡터 검색:
  "DG320" → 임베딩 벡터 → 코사인 유사도
  "에러 대응 매뉴얼" 문서와 의미적으로 유사하지만,
  정확히 "DG320"이 언급된 문서를 놓칠 수 있음

BM25 검색:
  "DG320" 단어가 포함된 문서를 정확히 찾음
  하지만 "에러 대응 방법"의 의미를 이해하지 못함
```

### 8-2. 해결: 양쪽을 합치는 RRF (Reciprocal Rank Fusion)

```
사용자 질문: "DG320 에러 대응 방법"
              │
     ┌────────┴────────┐
     ▼                  ▼
  벡터 검색           BM25 검색
  (의미 유사도)       (키워드 정확 매칭)
     │                  │
  1위: 에러대응.md    1위: DG320가이드.md
  2위: 장애매뉴얼.md  2위: 에러대응.md
  3위: DG320가이드.md 3위: 캐시장애.md
     │                  │
     └────────┬────────┘
              ▼
     RRF (Reciprocal Rank Fusion)
```

**RRF 공식**:

```
RRF_score(문서d) = Σ  weight / (k + rank_i(d))
                  각 검색 결과에서 d의 순위

k = 60 (표준 상수, 상위권 차이를 완화)
```

**계산 예시**:

```
"에러대응.md":
  벡터 1위: 1.0 / (60 + 1) = 0.0164
  BM25  2위: 1.0 / (60 + 2) = 0.0161
  RRF = 0.0164 + 0.0161 = 0.0325  ← 양쪽 상위 → 최종 1위

"DG320가이드.md":
  벡터 3위: 1.0 / (60 + 3) = 0.0159
  BM25  1위: 1.0 / (60 + 1) = 0.0164
  RRF = 0.0159 + 0.0164 = 0.0323  ← 최종 2위
```

**핵심 포인트**: RRF는 **점수(score)**가 아니라 **순위(rank)**만 사용합니다.
검색 엔진마다 점수 스케일이 다른 문제를 순위 기반으로 우아하게 해결합니다.

### 8-3. BM25 토크나이저

```python
def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = re.findall(r"[가-힣a-z0-9]+", text)
    return [t for t in tokens if len(t) >= 1]

# "DG320 에러 대응 방법" → ["dg320", "에러", "대응", "방법"]
```

한글은 형태소 분석기 없이 어절(공백) 단위로 분리합니다. 간단하지만 사내 위키 규모에서는 충분한 성능입니다.

### 8-4. 인덱스 동기화

BM25 인덱스는 **인메모리**로 관리되며, ChromaDB와 항상 동기화됩니다:

| 이벤트 | BM25 동작 |
|--------|----------|
| 문서 저장 | `remove_by_file()` → `add_documents()` |
| 문서 삭제 | `remove_by_file()` |
| 전체 재인덱싱 | `clear()` → 전체 추가 |
| 서버 재시작 | 기동 시 ChromaDB에서 부트스트랩 |

---

## 9. Step P2A-3: 증분 인덱싱

### 9-1. 문제

문서 1개를 수정해도 `reindex_all`이 **전체 15개 파일**을 다시 임베딩합니다.
OpenAI 임베딩 API 호출 비용 + 시간이 불필요하게 소모됩니다.

### 9-2. 해결: SHA256 해시 기반 변경 감지

```
문서 저장 시:
  content → SHA256("출장 경비 규정...") → "a3f2b1c8"
                                              │
                                   저장된 해시와 비교
                                   ┌──────┴──────┐
                                   │              │
                                 같음           다름
                                   │              │
                              스킵 (0ms)     재인덱싱
                                              (API 호출)
                                              │
                                         해시 갱신
```

**해시 저장 위치**: `wiki/.ontong/index_hashes.json`

```json
{
  "출장-경비-규정.md": "a3f2b1c8e5d71234",
  "재고관리-프로세스가이드.md": "7b92f4a1d3c60987",
  ...
}
```

### 9-3. 실측 결과

```bash
# 1차: 전체 인덱싱
curl -X POST "http://localhost:8001/api/wiki/reindex?force=true"
→ {"total_chunks": 90}  # 15 파일, ~3초

# 2차: 증분 인덱싱 (변경 없음)
curl -X POST "http://localhost:8001/api/wiki/reindex"
→ {"total_chunks": 0}   # 0 파일, ~0.05초 (해시 비교만)
```

---

## 10. Step P2A-4: 쿼리 캐싱

### 10-1. 문제

같은 질문을 반복하면 매번 벡터 검색 + BM25 + RRF 병합을 실행합니다.

### 10-2. 해결: LRU 캐시 + TTL + 자동 무효화

```
질문: "출장 경비 규정"
       │
  캐시 키 생성: SHA256("출장 경비 규정".lower()) → "f7a2..."
       │
  ┌────┴────────────┐
  │ 캐시 HIT        │ → 저장된 검색 결과 즉시 반환 (0ms)
  │                  │   thinking step에 "캐시" 모드 표시
  └──────────────────┘
  │ 캐시 MISS       │ → 하이브리드 검색 실행
  │                  │   → 결과를 캐시에 저장
  └──────────────────┘
```

**LRU (Least Recently Used) 동작**:

```
캐시 크기: 128 (최대 엔트리 수)

  [질문A] [질문B] [질문C] ... [질문128]
     ↑                            ↑
  가장 최근                   가장 오래됨

  새 질문 D 추가 시:
  → 질문128 삭제 (가장 오래 사용 안 된 것)
  → [질문D] [질문A] [질문B] [질문C] ... [질문127]

  질문B 재사용 시:
  → 질문B를 맨 앞으로 이동
  → [질문B] [질문D] [질문A] [질문C] ... [질문127]
```

**TTL (Time To Live)**: 5분 후 자동 만료 → 오래된 검색 결과가 계속 쓰이는 것 방지

**자동 무효화**: 문서 수정 시 해당 파일이 포함된 캐시만 정확히 삭제

```python
# 예: "출장-경비-규정.md" 수정 시
query_cache.invalidate_by_file("출장-경비-규정.md")
# → 이 파일이 검색 결과에 포함된 캐시 엔트리만 삭제
# → 다른 질문의 캐시는 유지
```

### 10-3. 모니터링

```python
cache.stats.hits          # 캐시 적중 횟수
cache.stats.misses        # 캐시 미적중 횟수
cache.stats.hit_rate      # 적중률 (hits / total)
cache.stats.evictions     # LRU 퇴거 횟수
cache.stats.invalidations # 무효화 횟수
```

---

## 11. Step P2A-5: 메타데이터 사전 필터링

### 11-1. 문제

"재고관리 프로세스 알려줘"를 검색하면 HR, IT 등 **관련 없는 도메인 문서**도 함께 검색됩니다.

### 11-2. 해결: 질문에서 domain/process 키워드 자동 추출 → ChromaDB WHERE 절 적용

```
질문: "재고관리 프로세스 알려줘"
       │
  키워드 추출 (규칙 기반):
    "재고" → process = "재고관리"
       │
  ChromaDB 검색:
    SELECT * FROM wiki
    WHERE process = "재고관리"   ← 사전 필터
    ORDER BY cosine_similarity
       │
  0건? → 필터 제거 후 전체 검색 (fallback)
```

**키워드 사전**:

```python
DOMAIN_KEYWORDS = {
    "SCM": ["SCM", "공급망", "supply chain"],
    "IT":  ["IT", "시스템", "서버", "인프라", "보안"],
    "HR":  ["HR", "인사", "채용", "교육", "OJT", "온보딩"],
    ...
}

PROCESS_KEYWORDS = {
    "재고관리": ["재고", "inventory", "stock"],
    "주문처리": ["주문", "발주", "order"],
    ...
}
```

### 11-3. Fallback 전략

필터링이 너무 제한적이면 0건이 나올 수 있습니다. 이때:

```python
# 1차: 필터 적용 검색
results = chroma.query_with_filter(query, where={"process": "재고관리"})

# 결과 0건이면
if not results["documents"][0]:
    # 2차: 필터 없이 전체 검색
    results = chroma.query(query)
```

이렇게 하면 **정밀도(precision)를 먼저 시도**하되, 실패 시 **재현율(recall)로 안전하게 복귀**합니다.

---

## 12. Step P2A-6: Cross-encoder 리랭킹

### 12-1. 문제

벡터 검색과 BM25는 후보를 **빠르게** 뽑지만, **정밀한 관련도 순위**를 매기는 데는 한계가 있습니다.

### 12-2. 원리: 2단계 파이프라인 (Retrieve → Rerank)

```
┌─────── 1단계: Retrieval (빠르고 넓게) ────────┐
│                                                 │
│  벡터 + BM25 → 상위 8개 후보                    │
│  속도: ~50ms                                    │
│  방식: 각 문서를 독립적으로 임베딩 비교           │
│                                                 │
└─────────────────────────────────────────────────┘
                     ↓
┌─────── 2단계: Reranking (느리지만 정밀) ────────┐
│                                                 │
│  LLM에게 질문 + 8개 후보 스니펫을 한번에 전달     │
│  "가장 관련 있는 순서로 번호를 매겨줘"            │
│  → "2, 0, 4, 1, 3, 5, 7, 6"                    │
│  속도: ~1000ms (LLM 호출)                       │
│                                                 │
└─────────────────────────────────────────────────┘
```

**왜 2단계인가?**

- 1단계(Retrieval): 수만 개 문서에서 **수백 ms** 안에 후보를 뽑아야 함 → 가벼운 모델 필요
- 2단계(Reranking): 8개 후보만 비교하면 되므로 **LLM 급** 모델 사용 가능

이 구조는 **검색 엔진의 표준 패턴**입니다 (Google, Bing 등도 동일한 2단계 사용).

### 12-3. on/off 설정

```python
# backend/core/config.py
enable_reranker: bool = True  # False로 끄면 리랭킹 생략

# .env 파일에서도 설정 가능
ENABLE_RERANKER=false
```

속도 우선이면 끄고, 정확도 우선이면 켭니다.

---

## 13. 현재 방식의 장점과 단점 분석

### 13-1. 장점

| 영역 | 장점 | 설명 |
|------|------|------|
| **아키텍처** | 모듈형 설계 | 각 최적화가 독립 모듈 → 개별 on/off 가능 |
| **속도** | 캐시 + 증분 인덱싱 | 반복 질의 0ms, 미변경 문서 스킵 |
| **검색 품질** | 하이브리드 검색 | 의미 검색 + 키워드 검색의 상호 보완 |
| **비용** | LLM 호출 최소화 | 키워드 라우팅 92%, 규칙 기반 명확화, 캐시 히트 |
| **운영** | 설정 유연성 | `config.py` / `.env`로 리랭킹, 캐시 TTL 등 조절 |
| **확장성** | 표준 패턴 사용 | RRF, 2단계 리랭킹 등 검색 업계 검증된 방법론 |

### 13-2. 단점 및 한계

| 영역 | 한계 | 원인 | 영향 |
|------|------|------|------|
| **BM25 토크나이저** | 형태소 분석 없이 어절 단위 분리 | 한국어 전문 토크나이저 미사용 | "재고관리"와 "재고 관리"를 다른 토큰으로 취급 |
| **BM25 인덱스** | 인메모리 → 서버 재시작 시 소실 | 영속화 미구현 | 재시작 시 ChromaDB에서 부트스트랩 필요 |
| **리랭킹 비용** | LLM 호출 1회 추가 (~1초) | 전용 cross-encoder 미사용 | 응답 시간 증가, API 비용 발생 |
| **필터 추출** | 하드코딩된 키워드 사전 | 동적 학습 미지원 | 새 도메인/프로세스 추가 시 코드 수정 필요 |
| **캐시 범위** | 검색 결과만 캐싱 | LLM 답변은 캐싱 안 됨 | 같은 질문이라도 답변 생성 시간은 매번 소요 |
| **RRF 가중치** | vector=1, BM25=1 고정 | 도메인별 최적 비율 미탐색 | 특정 쿼리에서 하이브리드가 단독보다 나빠질 수 있음 |
| **동시성** | 캐시 lock 없음 | 단일 프로세스 전제 | 멀티 워커 배포 시 캐시 불일치 가능 |

### 13-3. 근본적 한계

1. **임베딩 모델 의존**: OpenAI `text-embedding-3-small`은 한국어에 최적화되지 않음. 사내 용어나 약어(DG320, MES 등)의 벡터 표현이 부정확할 수 있음.

2. **청킹 전략 고정**: 헤딩 기반 분할은 구조화된 문서에 적합하지만, 표 형태의 데이터(인사정보 등)나 비구조화 문서에서는 의미 단위가 깨질 수 있음.

3. **단일 벡터 DB**: ChromaDB는 프로토타입/소규모에 적합하지만, 수만 건 이상에서는 성능/가용성 한계.

---

## 14. 고도화 전략 로드맵

### 14-1. 단기 (1~2주) — 현재 구조 내 튜닝

| 항목 | 내용 | 기대 효과 |
|------|------|-----------|
| **RRF 가중치 탐색** | 쿼리 유형별 vector/BM25 가중치 A/B 테스트 | 하이브리드 정확도 5~10% 향상 |
| **BM25 부트스트랩 자동화** | 서버 기동 시 ChromaDB → BM25 자동 빌드 | 재시작 후 첫 질문부터 하이브리드 작동 |
| **필터 사전 동적화** | `/api/metadata/templates`에서 domain/process 목록을 읽어 필터 사전 자동 갱신 | 코드 수정 없이 새 도메인 지원 |
| **캐시 통계 API** | `GET /api/admin/cache-stats` — 히트율, 크기, 최근 질문 | 운영 모니터링 |

### 14-2. 중기 (1~2개월) — 검색 품질 도약

| 항목 | 내용 | 기대 효과 |
|------|------|-----------|
| **한국어 형태소 분석기** | `konlpy` (Mecab/Komoran) 적용 → BM25 토큰 품질 향상 | "재고관리" ↔ "재고 관리" 동일 토큰화 |
| **다국어 임베딩 모델** | `multilingual-e5-large` 또는 `bge-m3` (로컬 실행) | 한국어 임베딩 정확도 향상 + API 비용 제거 |
| **전용 Cross-encoder** | `ms-marco-MiniLM` 등 경량 리랭커 (로컬) | 리랭킹 300ms → 50ms, API 비용 제거 |
| **Adaptive Chunking** | 문서 구조에 따라 청킹 전략 자동 선택 (표/리스트/산문) | 구조화 데이터 검색 품질 향상 |
| **Query Expansion** | 동의어/관련어 자동 확장 ("서버" → "서버 인프라 시스템") | 재현율 향상 |

### 14-3. 장기 (3개월+) — 아키텍처 전환

| 항목 | 내용 | 기대 효과 |
|------|------|-----------|
| **벡터 DB 전환** | ChromaDB → Qdrant 또는 Milvus | 수만~수십만 문서 대응, 필터링 성능 향상 |
| **분산 캐시** | Redis 기반 쿼리/답변 캐시 | 멀티 워커/멀티 서버 환경 지원 |
| **학습 기반 리랭킹** | 사용자 클릭/피드백으로 리랭커 파인튜닝 | 도메인 특화 정확도 |
| **RAG Evaluation 파이프라인** | RAGAS 등으로 자동 품질 측정 (Faithfulness, Relevancy) | 변경 시 품질 회귀 자동 감지 |
| **Streaming 캐시** | LLM 답변까지 캐싱 (동일 질문 → 저장된 답변 즉시 재생) | 반복 질문 응답 시간 0ms |

### 14-4. 우선순위 매트릭스

```
          높은 효과
              ↑
              │  ★ 한국어 형태소 분석기
              │  ★ 다국어 임베딩 모델
              │
              │  ● RRF 가중치 탐색      ★ 전용 Cross-encoder
              │  ● BM25 부트스트랩
              │  ● 필터 사전 동적화
              │
              │                          ○ Qdrant 전환
              │  ● 캐시 통계 API         ○ RAG Evaluation
              │                          ○ 분산 캐시
              │
 낮은 노력 ──┼──────────────────────────── 높은 노력 →
              │
          낮은 효과

  ● 단기    ★ 중기    ○ 장기
```

---

## 15. 참고: 주요 파일 맵

| 파일 | 역할 |
|------|------|
| `backend/application/agent/router.py` | 2단계 의도 분류 (키워드 → LLM) |
| `backend/application/agent/rag_agent.py` | RAG 파이프라인 메인 로직 |
| `backend/application/agent/filter_extractor.py` | 질문 → 메타데이터 필터 추출 |
| `backend/infrastructure/vectordb/chroma.py` | ChromaDB 래퍼 |
| `backend/infrastructure/search/bm25.py` | BM25 인메모리 인덱스 |
| `backend/infrastructure/search/hybrid.py` | RRF 병합 모듈 |
| `backend/infrastructure/search/reranker.py` | LLM 기반 리랭커 |
| `backend/infrastructure/cache/query_cache.py` | LRU 쿼리 캐시 |
| `backend/infrastructure/storage/file_hash.py` | 증분 인덱싱 해시 저장소 |
| `backend/application/wiki/wiki_indexer.py` | 문서 청킹 + 인덱싱 오케스트레이션 |
| `backend/core/config.py` | `enable_reranker` 등 설정 |
| `tests/bench_rag_latency.py` | 파이프라인 지연시간 벤치마크 |
| `tests/test_hybrid_search.py` | 하이브리드 검색 품질 비교 |
| `tests/test_reranker.py` | 리랭킹 A/B 비교 |
