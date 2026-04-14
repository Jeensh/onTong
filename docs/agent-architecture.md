# AI Agent Architecture (v3)

onTong의 AI Copilot 에이전트 아키텍처 문서입니다.

## 전체 파이프라인

```
사용자 질문
    │
    ▼
┌─────────────────────────────────────────┐
│  API Layer (api/agent.py)               │
│  ┌──────────┐  ┌────────────────┐       │
│  │ 의도 분류 │  │ 쿼리 보강      │  병렬  │
│  │ (Router)  │  │ (QueryAugment) │       │
│  └─────┬────┘  └───────┬────────┘       │
│        └───────┬───────┘                │
│                ▼                        │
│         AgentContext 생성               │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│  RAG Agent (rag_agent.py)               │
│                                         │
│  1. 하이브리드 검색 (wiki_search)       │
│        ↓                                │
│  2. ReAct 평가 (관련도 < 25%)           │
│        ↓ insufficient → 재검색 (최대 3턴)│
│        ↓ sufficient                     │
│  3. 출처 표시 + 충돌 감지               │
│        ↓                                │
│  4. LLM 답변 생성 (스트리밍)            │
│        ↓                                │
│  SSE 이벤트 스트림                      │
└─────────────────────────────────────────┘
```

## 핵심 컴포넌트

### 1. 에이전트 인격 (`backend/ontong.md`)

에이전트의 응답 톤, 규칙, 제약조건을 마크다운으로 정의합니다.
코드 변경 없이 프롬프트를 수정할 수 있어 빠른 이터레이션이 가능합니다.

주요 규칙:
- 검색된 문서에 근거해서만 답변 (환각 방지)
- 출처 명시, 문서 간 충돌 시 양쪽 다 안내
- 대화 요약이 포함되어도 메타 발언 금지

### 2. 토큰 기반 히스토리 윈도우

```python
build_history_window(history, max_tokens=4000)
```

고정 턴 수(6턴) 대신 **토큰 예산**으로 히스토리를 관리합니다.
예산 초과 시 오래된 메시지를 규칙 기반으로 요약합니다:

- 대화 범위 (Scope)
- 최근 요청 사항
- 참조된 문서
- 사용된 스킬
- 마지막 응답 요약

### 3. 주제 전환 감지 (Topic Shift)

`QueryAugmentResult.topic_shift` 필드로 주제 전환을 감지합니다.
주제가 전환되면 이전 히스토리를 LLM에 전달하지 않아 컨텍스트 오염을 방지합니다.

```
"후판 공정계획 알려줘" → "담당자 누구야?"     → topic_shift=false (후속 질문)
"후판 공정계획 알려줘" → "회의실 예약 방법은?" → topic_shift=true (주제 전환)
```

### 4. ReAct 자율 검색

검색 결과 품질을 평가하여 부족하면 자동으로 재검색합니다.

| 관련도 | 동작 | LLM 호출 |
|--------|------|----------|
| 40%+ | 즉시 답변 (fast-path) | 없음 |
| 25~40% | moderate, 즉시 답변 | 없음 |
| 25% 미만 | LLM이 평가 + 재검색 쿼리 생성 | 1회 |
| 결과 없음 | 즉시 insufficient | 없음 |

재검색 전략 (우선순위):
1. **구체화**: "휴가 규정" → "연차 휴가 규정 변경 2025"
2. **시간 추가**: "작년" → "2025"
3. **동의어**: "휴가" → "연차", "휴직"
4. **상위 개념**: "연차 휴가 변경" → "인사 규정 개정"

최대 3턴 후 중단 (비용 통제). 평균 케이스 1턴, 어려운 케이스 2~3턴.

### 5. 스킬 시스템

스킬은 에이전트가 호출할 수 있는 독립적인 기능 단위입니다.

| 스킬 | 권한 | 설명 |
|------|------|------|
| `wiki_search` | READ | 하이브리드 검색 (벡터 + BM25 + RRF) |
| `wiki_read` | READ | 문서 전문 읽기 |
| `wiki_write` | WRITE | 새 문서 생성 (승인 필요) |
| `wiki_edit` | WRITE | 문서 수정 (승인 필요) |
| `llm_generate` | READ | LLM 답변 생성 (스트리밍) |
| `conflict_check` | READ | 문서 간 충돌 감지 |
| `query_augment` | READ | 후속 질문 쿼리 보강 |

#### 스킬별 도구 풀 제한 (INTENT_ALLOWED_SKILLS)

의도(intent)에 따라 사용 가능한 스킬이 자동으로 제한됩니다:

```python
INTENT_ALLOWED_SKILLS = {
    "question": ["wiki_search", "wiki_read", "llm_generate", "conflict_check", "query_augment"],
    "write":    ["wiki_search", "wiki_read", "wiki_write", "llm_generate"],
    "edit":     ["wiki_search", "wiki_read", "wiki_edit", "llm_generate"],
}
```

#### 스킬 권한 매핑

```python
SKILL_PERMISSIONS = {
    "wiki_search": PermissionLevel.READ,    # 모든 사용자
    "wiki_write":  PermissionLevel.WRITE,   # editor, admin만
    "wiki_edit":   PermissionLevel.WRITE,   # editor, admin만
}
```

WRITE 권한 스킬 실행 시 사용자 역할을 검증하며, 권한 부족 시 안내 메시지를 반환합니다.

#### PreSkill/PostSkill 훅 시스템

스킬 실행 전후에 훅을 삽입하여 입력 검증, 결과 변환, 피드백 주입이 가능합니다.

```python
class PreSkillHook(Protocol):
    async def before(self, skill_name, ctx, kwargs) -> PreHookResult:
        ...  # allow=False → 실행 차단, modified_kwargs → 입력 변환

class PostSkillHook(Protocol):
    async def after(self, skill_name, ctx, result) -> SkillResult:
        ...  # 결과 변환, 피드백 주입
```

내장 훅:
- `QuerySanitizeHook` (pre): 검색 쿼리 공백 정리
- `DeprecatedDocHook` (post): 폐기 문서 경고 주입

#### Completion Protocol (CompletionStatus)

`SkillResult.status`로 실행 완료 상태를 4단계로 구분합니다:

| 상태 | 값 | 설명 |
|------|-----|------|
| DONE | `done` | 정상 완료 |
| DONE_WITH_CONCERNS | `concerns` | 완료 + 경고 (폐기 문서, 부분 결과 등) |
| BLOCKED | `blocked` | 진행 불가 (권한 부족, 데이터 없음) |
| NEEDS_CONTEXT | `needs_context` | 사용자 확인 필요 (ClarificationRequestEvent 발생) |

#### 사용자 확인 루프 (Clarification)

`NEEDS_CONTEXT` 상태 시 `ClarificationRequestEvent` SSE 이벤트를 발생시켜
사용자에게 추가 정보를 요청합니다. 사용자 응답은 `clarification_response_id`로 연결됩니다.

#### Per-Skill Allowed Tools

User-facing 스킬은 YAML frontmatter에 `allowed-tools` 필드로 사용 가능한 내장 스킬을 제한할 수 있습니다.
설정하지 않으면 intent 기반 기본값(INTENT_ALLOWED_SKILLS)을 사용합니다.

```yaml
---
type: skill
allowed-tools:
  - wiki_search
  - wiki_read
  - llm_generate
---
```

#### 프롬프트 마크다운 분리

각 스킬의 LLM 프롬프트는 Python 코드가 아닌 `.md` 파일로 관리됩니다:

```
backend/application/agent/skills/prompts/
├── query_augment.md    # 쿼리 보강 규칙
├── conflict_check.md   # 충돌 감지 규칙
├── wiki_write.md       # 문서 생성 규칙
├── wiki_edit.md        # 문서 편집 규칙
└── qa_react.md         # ReAct 검색 평가 규칙
```

### 6. 세션 영속성 (JSONL)

대화 기록을 세션별 JSONL 파일로 저장합니다.

```
data/sessions/
├── session-abc123.jsonl
├── session-def456.jsonl
└── ...
```

각 줄은 하나의 메시지:
```json
{"ts": "2026-04-05T13:54:07+00:00", "role": "user", "content": "장애대응 플레이북 알려줘"}
{"ts": "2026-04-05T13:54:12+00:00", "role": "assistant", "content": "장애대응 플레이북은..."}
```

서버 재시작 시 자동 복원됩니다.

### 7. SkillResult feedback

스킬 실행 결과에 비치명적 경고를 포함할 수 있습니다:

```python
@dataclass
class SkillResult:
    data: Any = None
    success: bool = True
    error: str = ""
    feedback: str = ""      # 비치명적 경고 (예: "폐기 문서 2건 제외됨")
    retry_hint: str = ""    # 사용자 안내 (예: "관리자에게 권한 요청")
```

예: `wiki_search`에서 deprecated 문서가 필터링되면 feedback에 경고를 담아 반환합니다.

## 설정

| 환경변수 | 기본값 | 설명 |
|----------|--------|------|
| `LITELLM_MODEL` | `anthropic/claude-sonnet-4-20250514` | 사용 LLM 모델 |
| `ANTHROPIC_API_KEY` | - | Anthropic API 키 |
| `OPENAI_API_KEY` | - | OpenAI API 키 (임베딩 등) |

LiteLLM을 통해 OpenAI, Anthropic, Ollama 등 다양한 LLM 프로바이더를 지원합니다.
`.env`에서 `LITELLM_MODEL`만 변경하면 모델을 교체할 수 있습니다.

## 관련 파일

| 파일 | 설명 |
|------|------|
| `backend/ontong.md` | 에이전트 인격/규칙 정의 |
| `backend/application/agent/rag_agent.py` | 핵심 RAG 에이전트 (히스토리, ReAct, 답변 생성) |
| `backend/application/agent/skill.py` | 스킬 인터페이스, 권한 매핑, SkillResult, CompletionStatus, HookRegistry |
| `backend/application/agent/hooks.py` | 내장 훅 (QuerySanitize, DeprecatedDoc) |
| `backend/application/agent/context.py` | AgentContext, 도구 풀 제한, 권한 검증, 훅 실행 파이프라인 |
| `backend/application/agent/models.py` | 구조화된 LLM 출력 모델 |
| `backend/application/agent/skills/` | 개별 스킬 구현체 |
| `backend/application/agent/skills/prompts/` | 스킬별 프롬프트 (.md) |
| `backend/application/skill/skill_loader.py` | User-facing 스킬 로더 (allowed-tools 파싱 포함) |
| `backend/core/session.py` | 세션 JSONL 영속성 |
| `backend/api/agent.py` | SSE 스트리밍 API 엔드포인트 |
| `backend/api/skill.py` | 스킬 CRUD API (스킬 크리에이터) |
