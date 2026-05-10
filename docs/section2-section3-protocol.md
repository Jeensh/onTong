# Section 2 ↔ Section 3 통신 프로토콜

> **한 줄 요약**: 섹션3(시뮬레이션)가 섹션2(모델링)에 말을 걸 때 쓰는 **공용 배달원(`ModelingClient`) 하나만** 통해서 통신한다. 그래야 Mock → Real 전환 시 UI·에이전트 코드를 안 건드린다.
>
> **최종 수정일**: 2026-04-18

---

## 1. 현재 문제

섹션3 에이전트 툴이 `mock_orders.json` 같은 Mock 파일을 **직접 import**하고 있다. 섹션2가 실제 구현되는 순간 고쳐야 할 곳이 여기저기 흩어진다.

**목표**: Mock 파일을 직접 읽는 코드를 **0건**으로 만들고, 모든 데이터 접근을 `ModelingClient` 하나로 모은다.

---

## 2. 역할 분담 (원칙)

| 섹션 | 책임 |
| ---- | ---- |
| **Section 2 (모델링)** | 원본 데이터 저장소. 주문·설비·온톨로지 그래프·영향 분석 |
| **Section 3 (시뮬레이션)** | 사용자 경험. 3D 뷰, SSE 스트리밍, ReAct 루프, **Slab 수치 계산** |

- 섹션2는 사용자 이벤트 루프를 몰라야 한다.
- Slab 설계 수치 계산은 섹션3가 계속 소유(섹션2에 넘기지 않음).

---

## 3. 통신 구조 3층

```
섹션3 UI/에이전트 툴
    │
    ▼
[ Pydantic 타입 계약 ]  ← backend/shared/contracts/
    │
    ▼
[ ModelingClient Protocol ]  ← 공용 배달원 인터페이스
    │
    ├── MockModelingClient   (현재: Mock JSON)
    └── RealModelingClient   (미래: 섹션2 REST API 호출)
                │
                ▼
        섹션2 REST API
```

**스위치**: 환경변수 `MODELING_CLIENT_MODE = mock | real` 한 줄로 전환.

---

## 4. 필요한 것 3가지

### ① 타입 계약 신규 파일 — `backend/shared/contracts/modeling.py`

섹션2가 섹션3에 넘기는 데이터의 모양을 Pydantic 모델로 고정한다.

- `Order` — 주문 (order_id, target_width, rolling_line, status, error_code 등)
- `EquipmentSpec` — 설비 제약 (width_range, edging_spec 등)
- `OntologyGraph` — `{nodes: [OntologyNode], edges: [OntologyEdge]}`
- `ImpactResult` — 그래프 기반 영향 분석 결과
- `ModelingError` — 공용 에러 (`code`, `message`, `retryable`)

> 기존 `backend/shared/contracts/simulation.py`는 그대로 유지. 여기에 추가.

### ② `ModelingClient` Protocol 확장

기존 4개 메서드(`submit_scenario` 등)에 다음을 추가.

| 메서드 | 용도 |
| ------ | ---- |
| `list_orders()` / `get_order(id)` | 주문 조회 |
| `list_equipment()` / `get_equipment(id)` | 설비 제약 조회 |
| `get_full_ontology()` / `get_subgraph(query)` / `find_related(node_id)` | 온톨로지 탐색 |
| `analyze_impact(source, change, depth)` | "이거 바꾸면 뭐가 깨져?" BFS |

### ③ 섹션2가 구현할 REST API

**(a) 단순 조회 API — 캐시 가능한 데이터 읽기**

| 메서드 | 경로 | 용도 |
| ------ | ---- | ---- |
| `GET` | `/api/modeling/orders` | 주문 목록 |
| `GET` | `/api/modeling/equipment` | 설비 제약 목록 |
| `GET` | `/api/modeling/ontology/graph` | 온톨로지 그래프 |

**(b) 통합 질의 API — LLM 기반 자유 질의 ⭐**

| 메서드 | 경로 | 용도 |
| ------ | ---- | ---- |
| `POST` | `/api/modeling/query` | intent 기반 통합 질의 (조회·시뮬·영향분석·최적화·설명) |

→ 시나리오 A/B/C 및 Custom Agent의 모든 자유 질의는 이 한 엔드포인트로 수렴.

응답은 JSON, 날짜는 ISO 8601. 에러는 `ModelingError` 모양으로 반환.

---

## 5. 요청/응답 봉투 (Envelope) — `modeling/query`의 계약 ⭐

### 5.1 Intent 5종

섹션3가 섹션2에 요청하는 **질문의 의도**를 5개로 분류한다. 신규 질문이 추가돼도 이 5개 안에 들어가면 Modeling 재개발 불필요.

| intent | 의미 | 예시 질문 | 기존 매핑 |
| ------ | ---- | -------- | -------- |
| `query` | 데이터 조회 | "ORD-2024-0042 정보 줘" | - |
| `simulate` | 시뮬레이션 실행 | "폭 1200으로 돌리면?" | 시나리오 A |
| `impact_analysis` | 파급 영향 분석 | "Edging 상한 160으로 바꾸면 영향 주문?" | 시나리오 B |
| `optimize` | 최적값 탐색 | "이 주문의 분할수 최적 조합은?" | 시나리오 C |
| `explain` | 원인·규칙 설명 | "이 주문이 왜 DG320 에러?" | - |

### 5.2 요청 포맷 (Simulation → Modeling)

```json
{
  "request_id": "req-20260418-001",
  "intent": "impact_analysis",
  "natural_language": "Edging 상한 180→160 바꾸면 영향받는 주문?",
  "parameters": {
    "target": "HR-A",
    "change": { "edging_max": { "from": 180, "to": 160 } }
  },
  "context": {
    "conversation_history": [...],
    "ontology_version": "origin"
  },
  "expected_output": { "format_hints": ["table", "graph_highlight"] }
}
```

### 5.3 응답 포맷 (Modeling → Simulation)

```json
{
  "request_id": "req-20260418-001",
  "status": "success | partial | need_more_info | unsupported | error",
  "result": {
    "summary": "...",
    "outputs": [ { "kind": "table", "rows": [...] } ]
  },
  "missing_info": {
    "questions": [
      { "field": "rolling_line", "question": "어느 라인?",
        "input_type": "select", "options": ["HR-A", "HR-B"] }
    ]
  }
}
```

### 5.4 status 5종 — Human-in-the-Loop 트리거

| status | 의미 | Simulation UI 대응 |
| ------ | ---- | ------------------ |
| `success` | 완전 답변 | 결과 시각화 |
| `partial` | 일부만 답변 | 부분 결과 + 보완 안내 |
| `need_more_info` | 정보 부족 (HITL) | `missing_info.questions`로 **역질문 UI 자동 생성** |
| `unsupported` | Modeling 범위 밖 | "Wiki에서 찾아보세요" 유도 |
| `error` | 실행 실패 | 에러 표시 + 재시도 |

→ `need_more_info`가 정해져야 배지윤 차장님의 "컨텍스트 엔지니어링"이 실제 UI 동작으로 연결됨.

### 5.5 가변 영역 3레벨 — `ontology_version`으로 표현

Simulation이 변경할 수 있는 범위를 3단계로 정의한다.

| Level | 의미 | `ontology_version` | 요청 예시 |
| ----- | ---- | ------------------ | -------- |
| **1. 파라미터 가변** | 온톨로지 구조는 그대로, 값만 변경 | `"origin"` | 폭 1040 → 1200 |
| **2. 온톨로지 가변** | 노드/엣지/속성 추가·수정 (draft) | `"draft-<id>"` | "Edging 기준 1건 추가해서 돌려봐" |
| **3. 로직 가변** | 계산 공식 자체 변경 | (미래) | 신동해 차장님 CLI 레벨 |

**규칙**: Level 2의 draft는 원본을 건드리지 않는다. 섹션3는 draft를 먼저 생성 → draft ID를 `ontology_version`에 넣어 시뮬레이션 실행.

---

## 6. 롤아웃 단계

| 단계 | 할 일 | 완료 기준 |
| ---- | ---- | --------- |
| **M1** | 타입 계약·Protocol 확장 + Mock을 배달원 뒤로 숨기기 | 섹션3 코드에서 `mock_*.json` import **0건** |
| **M2** | 섹션2가 REST API 4개 구현 + Neo4j 시드 | `MODELING_CLIENT_MODE=real`로 전환해도 UI 그대로 동작 |
| **M3** | 영향 분석·시뮬 위임 연동 | 시나리오 B 에이전트가 섹션2 그래프 호출 |
| **M4** | 인증(JWT) + 관측성 | 프로덕션 준비 완료 |

**핵심**: M1만 끝내면 섹션2가 늦어져도 섹션3는 정상 동작.

---

## 7. 변경 규칙

| 변경 | 허용 여부 |
| ---- | -------- |
| 신규 optional 필드 추가 | ✅ 자유 |
| 신규 required 필드 추가 | ⚠️ 양 섹션 합의 필요 |
| 필드 삭제·타입 변경·enum 값 삭제 | ❌ 1 스프린트 deprecation 후에만 |

계약 파일(`shared/contracts/`) 수정 PR은 **양 섹션 리뷰 필수**.

---

## 8. 미해결 질문 (동프·배프께 확인 필요)

| # | 질문 | 잠정 결정 |
| - | ---- | --------- |
| Q1 | Intent 5종으로 충분한가? | 5종으로 시작, 부족하면 추가 |
| Q2 | status 5종 괜찮은가? | 5종으로 시작 |
| Q3 | 각 intent별 응답시간 SLA? | 미정 (query 1초 / simulate 3초 / optimize 10초 제안) |
| Q4 | `need_more_info.questions`의 `input_type` 목록? | `select / number / text` 초안 |
| Q5 | 온톨로지 draft 생성·폐기 API는 누가 소유? | Modeling 쪽 제안 |
| Q6 | 온톨로지 실시간 반영 vs 세션 스냅샷 | **스냅샷 고정** (`ontology_version` 잠금) |
| Q7 | 섹션2가 Slab 수치 계산도 대체? | **아니오, 보완만**. Slab 계산은 섹션3 소유 |
| Q8 | Custom Agent가 섹션2에 직접 접근? | **불가**. 등록된 툴(ModelingClient 경유)만 |

---

## 9. 관련 문서

- [Section 2 가이드](section2-modeling.md)
- [Section 3 개발자 가이드](section3-developer-guide.md)
- [Section 3 로드맵](section3-roadmap.md) — Phase A-1~A-4와 본 문서 Milestone이 정렬됨
- 기존 계약: `backend/shared/contracts/simulation.py`
- 배달원: `backend/simulation/client/modeling_client.py`

---

*문서 버전: 1.0 · 2026-04-18*
