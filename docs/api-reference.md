# API 레퍼런스

> onTong 백엔드(FastAPI, 기본 포트 `8001`)의 엔드포인트 전체 목록입니다.
> 인증 등 공통 미들웨어: `X-User-Id` 헤더(Multi-user Auth), CORS 화이트리스트, Request ID.

---

## Section 1 — Wiki

### 문서 CRUD

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `GET` | `/api/wiki/tree` | 파일 트리 조회 (ETag 캐싱) |
| `GET` | `/api/wiki/file/{path}` | 문서 내용 조회 |
| `PUT` | `/api/wiki/file/{path}` | 문서 저장 (비동기 인덱싱 트리거) |
| `DELETE` | `/api/wiki/file/{path}` | 문서 삭제 |
| `POST` | `/api/wiki/reindex` | 전체 재인덱싱 (admin 전용) |
| `GET` | `/api/wiki/lineage/{path}` | 문서 계보 조회 (supersedes/superseded_by 체인) |
| `GET` | `/api/wiki/compare` | 두 문서 비교 (diff) |

### 검색

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `GET` | `/api/search/quick` | 하이브리드 빠른 검색 |
| `GET` | `/api/search/hybrid` | 의미 검색 + 리랭킹 |
| `GET` | `/api/search/graph` | 문서 관계 그래프 데이터 |
| `GET` | `/api/search/backlinks` | 백링크 맵 |

### AI Copilot

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `POST` | `/api/agent/chat` | SSE 스트리밍 채팅 (세션 ID 기반) |
| `POST` | `/api/approval/resolve` | 문서 수정 승인/거절 |

### 스킬 CRUD

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `GET` | `/api/skills/` | 스킬 목록 |
| `POST` | `/api/skills/` | 스킬 생성 |
| `GET` | `/api/skills/match` | 질문 → 스킬 자동 매칭 |
| `PUT` | `/api/skills/{path}` | 스킬 수정 |
| `PATCH` | `/api/skills/{path}/toggle` | 활성/비활성 전환 |
| `DELETE` | `/api/skills/{path}` | 스킬 삭제 |

### 관리 / 품질

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `GET` | `/api/conflict/duplicates` | 유사 문서 쌍 조회 |
| `GET` | `/api/metadata/tags` | 전체 태그 목록 |
| `POST` | `/api/metadata/suggest` | AI 태그 추천 |
| `GET` | `/api/acl/{path}` | 경로별 ACL 조회 |
| `POST` | `/api/acl/{path}` | ACL 설정 |
| `GET` | `/api/files/assets` | 이미지 자산 목록 (관리자 갤러리용) |
| `DELETE` | `/api/files/assets/batch` | 이미지 일괄 삭제 |

### 이벤트 / 공통

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `GET` | `/health` | 헬스체크 (ChromaDB/인덱싱/SSE 구독자 수) |
| `GET` | `/api/events` | 실시간 SSE 이벤트 (트리 갱신, 잠금, 인덱싱 상태) |

---

## Section 2 — Modeling

### 엔진 (분석 콘솔 / 시뮬레이션)

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `POST` | `/api/modeling/engine/query` | 한국어 질의 → 엔티티 resolve + 영향 프로세스 |
| `POST` | `/api/modeling/engine/simulate` | 파라메트릭 시뮬레이션 (before/after diff) |
| `GET` | `/api/modeling/engine/params/{entity_id}` | 엔티티 파라미터 메타데이터 |
| `GET` | `/api/modeling/engine/status` | 엔진 초기화 상태 |

### 코드 분석

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `POST` | `/api/modeling/code/parse` | tree-sitter 파싱 → 엔티티 추출 |
| `GET` | `/api/modeling/code/graph/{repo_id}` | 코드 의존성 그래프 |

### 소스 뷰어 (Phase 2a)

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `GET` | `/api/modeling/source/tree/{repo_id}` | 파일 트리 |
| `GET` | `/api/modeling/source/file/{repo_id}` | 파일 내용 조회 |
| `GET` | `/api/modeling/source/entity/{repo_id}/{qname}` | 엔티티 위치 조회 |

### 매핑

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `GET` | `/api/modeling/mapping/{repo_id}` | 매핑 목록 |
| `POST` | `/api/modeling/mapping/{repo_id}` | 매핑 생성/수정 |
| `DELETE` | `/api/modeling/mapping/{repo_id}/{code}` | 매핑 삭제 |
| `GET` | `/api/modeling/mapping/{repo_id}/gaps` | 미매핑 엔티티 목록 |
| `GET` | `/api/modeling/mapping/{repo_id}/resolve/{qname}` | 엔티티 → 도메인 매핑 조회 |

### 온톨로지

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `POST` | `/api/modeling/ontology/load-template` | SCOR + ISA-95 템플릿 로드 |
| `GET` | `/api/modeling/ontology/tree` | 온톨로지 트리 |
| `GET` | `/api/modeling/ontology/children/{node_id}` | 자식 노드 |
| `POST` | `/api/modeling/ontology/node` | 노드 생성 |
| `PUT` | `/api/modeling/ontology/node/{node_id}` | 노드 수정 |
| `DELETE` | `/api/modeling/ontology/node/{node_id}` | 노드 삭제 |

### 승인 / 질의 / 시드

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `POST` | `/api/modeling/query/analyze` | 질의 분석 |
| `POST` | `/api/modeling/approval/submit` | 매핑 승인 요청 |
| `POST` | `/api/modeling/approval/{review_id}/approve` | 승인 |
| `POST` | `/api/modeling/approval/{review_id}/reject` | 거절 |
| `GET` | `/api/modeling/approval/pending/{repo_id}` | 대기 목록 |
| `POST` | `/api/modeling/seed/scm-demo` | SCM 데모 데이터 시딩 |
| `GET` | `/api/modeling/health` | 헬스 체크 |

---

## Section 3 — Simulation

### 일반 시뮬레이션

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `GET` | `/api/simulation/health` | Section 3 헬스 체크 |
| `GET` | `/api/simulation/scenarios` | 사용 가능한 시나리오 목록 |
| `POST` | `/api/simulation/scenario` | 시뮬레이션 실행 (Job 반환, 비동기) |
| `GET` | `/api/simulation/job/{job_id}` | Job 상태 폴링 |
| `DELETE` | `/api/simulation/job/{job_id}` | Job 취소 |

### Slab 설계 (시나리오 A/B/C)

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `POST` | `/api/simulation/slab/run` | 시나리오 A/B/C 에이전트 실행 (SSE 스트리밍) |
| `GET` | `/api/simulation/slab/orders` | Mock 주문 목록 |
| `GET` | `/api/simulation/slab/ontology` | 온톨로지 그래프 JSON |
| `GET` | `/api/simulation/slab/equipment` | 설비 스펙 데이터 |
| `POST` | `/api/simulation/slab/calculate` | Slab 설계 파라미터 계산 (SEQ 1~16) |
| `GET` | `/api/simulation/slab/constraints` | 슬라이더 min/max 범위 |
| `GET` | `/api/simulation/slab/tools` | 등록된 Slab 도구 목록 |

### Custom Agent

| 메서드 | 경로 | 설명 |
| ------ | ---- | ---- |
| `GET` | `/api/simulation/custom-agents` | 등록된 에이전트 목록 |
| `POST` | `/api/simulation/custom-agents` | 새 에이전트 등록 |
| `DELETE` | `/api/simulation/custom-agents/{id}` | 에이전트 삭제 |
| `POST` | `/api/simulation/custom-agents/build/chat` | 채팅 빌더 (SSE) |
| `POST` | `/api/simulation/custom-agents/{id}/run` | 에이전트 실행 (SSE) |

---

## SSE 이벤트 종류

SSE 스트리밍 엔드포인트(`/api/agent/chat`, `/api/simulation/slab/run`, `/api/simulation/custom-agents/{id}/run` 등)에서 전송하는 이벤트 목록입니다.

| 이벤트 | 발생 시점 | data 구조 |
| ------ | --------- | --------- |
| `thinking` | 에이전트 사고 단계 | `{"message": "분석을 시작합니다..."}` |
| `tool_call` | LLM이 툴 호출 결정 | `{"tool": "get_order_info", "args": {...}}` |
| `tool_result` | 툴 실행 완료 | `{"tool": "get_order_info", "result": {...}}` |
| `graph_state` | 온톨로지 탐색 툴 실행 후 (Section 3) | `{"traversal": [...], "highlighted_edges": [...]}` |
| `slab_state` | Slab 상태 변경 툴 실행 후 (Section 3) | `{"slabs": [{...}]}` |
| `content_delta` | LLM 최종 답변 토큰 스트리밍 | `{"delta": "텍스트 조각"}` |
| `sources` | RAG 출처 문서 목록 (Section 1) | `{"sources": [{path, score, ...}]}` |
| `approval_request` | 문서 수정 승인 요청 (Section 1) | `{"diff": "...", "target_path": "..."}` |
| `clarification_request` | 사용자 추가 정보 요청 | `{"question": "..."}` |
| `agent_ready` | Custom Agent 정의 완성 (Section 3) | `{"agent": {...}}` |
| `done` | 전체 완료 | `{"result": {...}}` |
| `error` | 예외 발생 | `{"message": "에러 메시지"}` |

---

## 관련 문서

| 문서 | 설명 |
| ---- | ---- |
| [AI 에이전트 아키텍처](agent-architecture.md) | Section 1 RAG 파이프라인 + 스킬 시스템 |
| [Section 3 개발 가이드](section3-developer-guide.md) | Slab 에이전트 + Custom Agent + Tool Registry |
| [Section 2 기능 가이드](section2-modeling.md) | Modeling 엔진 + 매핑 워크벤치 |
