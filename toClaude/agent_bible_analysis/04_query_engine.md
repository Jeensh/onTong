# 04. Query Engine 분석 — claw-code-parity

## 핵심 아키텍처

### 쿼리 처리 파이프라인
```
User Input
  → Token Budget 검사 (max_turns, max_budget_tokens)
  → Route Prompt (토큰 기반 매칭)
  → Execute (매칭된 command/tool 실행)
  → Format Output (plain text or structured JSON)
  → Stream Events (실시간 이벤트)
  → Compact & Persist (히스토리 관리 + 저장)
```

### 핵심 설정
```python
QueryEngineConfig:
    max_turns: 8              # 최대 턴 수
    max_budget_tokens: 2000   # 토큰 예산
    compact_after_turns: 12   # 12턴 이후 압축
    structured_output: bool   # JSON 구조화 출력
    structured_retry_limit: 2 # 구조화 출력 재시도
```

### 스트리밍 이벤트 시퀀스
```
message_start → command_match → tool_match → permission_denial → message_delta → message_stop
```

### Stop Reason 체계
- `completed` — 정상 완료
- `max_turns_reached` — 턴 한도 초과
- `max_budget_reached` — 토큰 예산 초과

---

## Prefetch 전략 (사전 로딩)
```
Bootstrap 시점에 병렬 실행:
1. mdm_raw_read — 시스템 메타데이터
2. keychain_prefetch — 인증 정보
3. project_scan — 프로젝트 파일 스캔
```
- 세션 시작 전에 필요한 정보를 미리 로드
- Trust-gated: 신뢰 플래그에 따라 plugin/skill/MCP 초기화 결정

### Direct Modes vs Normal Modes
- **Normal**: 프롬프트 → 라우팅 → 실행 (일반 파이프라인)
- **Direct**: 라우팅 바이패스, 특정 타겟에 직접 연결
  - `direct-connect`: 포인트-투-포인트
  - `deep-link`: 특정 리소스 직접 접근

---

## 🔄 온통 에이전트 적용 인사이트

### 1. 토큰 예산 관리 도입
현재 온통: 토큰 관리 없음 → LLM에 무제한 요청
```python
# 도입 방안
class ChatConfig:
    max_context_tokens: int = 8000   # 컨텍스트 윈도우 예산
    max_output_tokens: int = 2000    # 응답 예산
    compact_after_tokens: int = 6000 # 이 이상이면 압축
```

### 2. Stop Reason 체계 도입
현재: 성공/실패만 구분
개선: 구체적 중단 사유로 후속 처리 결정
```python
class StopReason(Enum):
    COMPLETED = "completed"
    CONTEXT_LIMIT = "context_limit"
    NO_RELEVANT_DOCS = "no_relevant_docs"
    NEEDS_CLARIFICATION = "needs_clarification"
    SKILL_BLOCKED = "skill_blocked"
```

### 3. Prefetch/Precomputation 강화
현재 온통의 query_augment는 직렬 실행 → 병렬화 가능:
- RAG 검색 + query augment + clarity check를 병렬 실행
- 세션 시작 시 인기 문서 프리페치

### 4. 구조화된 출력 + 재시도
- JSON 직렬화 실패 시 단순화된 페이로드로 재시도
- 현재 온통은 스트리밍 실패 시 에러만 반환
