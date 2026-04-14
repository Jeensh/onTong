# 05. Coordinator & Orchestration 분석 — claw-code-parity

## 핵심 아키텍처

### 7단계 Bootstrap Graph
```
1. Prefetch side effects (병렬)     — 시스템 리소스 사전 로드
2. Environment guards               — 보안/안전 체크
3. CLI parse + trust gate           — 인자 파싱 + 권한 검증
4. Setup + Command/Agent load (병렬) — 워크스페이스 초기화
5. Deferred init (trust-gated)      — 플러그인/스킬/MCP 초기화
6. Mode routing                     — local/remote/ssh/teleport/direct
7. Query engine loop                — 메인 대화 루프
```

### 핵심 패턴: Parallel + Sequential 하이브리드
- **턴 내부**: 매칭된 command + tool 병렬 실행
- **턴 간**: 순차 실행 (이전 결과가 다음 입력에 영향)

### Execution Registry
```python
ExecutionRegistry:
    commands: tuple[MirroredCommand, ...]  # 커맨드 레지스트리
    tools: tuple[MirroredTool, ...]        # 도구 레지스트리
    
    def command(name) → MirroredCommand    # 대소문자 무시 검색
    def tool(name) → MirroredTool          # 대소문자 무시 검색
```

### Command Graph (계층적 분류)
```python
CommandGraph:
    builtins: tuple[...]      # 핵심 커맨드
    plugin_like: tuple[...]   # 플러그인 커맨드
    skill_like: tuple[...]    # 스킬 커맨드
```
- 선택적 로딩 가능 (플러그인 비활성화 등)

### 토큰 기반 라우팅
```python
def route_prompt(prompt, limit=5):
    tokens = tokenize(prompt)  # '/', '-', 공백 기준 분리
    for module in commands + tools:
        score = count_token_matches(tokens, module.name + source_hint + responsibility)
    # 결과: top 1 command + top 1 tool + 나머지 상위 매치
```

### Trust-Gated Deferred Init
```python
DeferredInitResult:
    plugin_init: bool      # trusted일 때만
    skill_init: bool       # trusted일 때만
    mcp_prefetch: bool     # trusted일 때만
    session_hooks: bool    # trusted일 때만
```
- 신뢰되지 않은 환경에서는 핵심 기능만 활성화

---

## Buddy System (참고)
- UI 기반 컴패니언 시스템 (스프라이트 애니메이션)
- 대화 중 시각적 피드백 제공
- 온통에서는 프론트엔드 UX 개선 시 참고 가능

---

## 🔄 온통 에이전트 적용 인사이트

### 현재 온통 vs claw-code-parity

| 항목 | 온통 (현재) | claw-code-parity |
|------|-----------|------------------|
| 초기화 | 서버 시작 시 전체 로드 | 7단계 점진적 + trust-gated |
| 라우팅 | LLM 인텐트 분류 (1 LLM 호출) | 토큰 매칭 (LLM 호출 없음) |
| 실행 | 순차 (RAG → reflect → answer) | 병렬 (command + tool 동시) |
| 레지스트리 | SkillRegistry 싱글턴 | ExecutionRegistry (불변) |
| 분류 | agent type (WIKI_QA 등) | command graph (builtin/plugin/skill) |

### 도입 가능한 전략

#### 1. 파이프라인 병렬화
현재 온통 RAG 파이프라인:
```
query_augment → vector_search → clarity_check → cognitive_reflect → answer_gen (직렬)
```
개선:
```
┌─ query_augment ─┐
│                  ├─→ clarity_check → answer_gen
└─ vector_search ──┘
```
- query_augment와 vector_search는 독립적 → 병렬 실행 가능
- cognitive_reflect 제거 시 더 단순해짐

#### 2. LLM-free 라우팅 옵션
- 현재: 모든 라우팅에 LLM 호출 필요
- 키워드/패턴 매칭으로 명확한 케이스 빠르게 라우팅
- LLM은 애매한 케이스에만 사용 (하이브리드)

#### 3. 점진적 초기화
- 서버 시작 시 핵심만 로드
- 첫 사용 시 나머지 로드 (lazy init)
- 콜드 스타트 시간 단축

#### 4. 불변 레지스트리
- 현재 SkillRegistry는 mutable → 스레드 안전성 이슈 가능
- 초기화 시 한번 빌드 후 불변 객체로 사용
