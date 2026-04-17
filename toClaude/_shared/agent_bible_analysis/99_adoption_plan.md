# 99. 최종 도입 계획 (v3) — 성능 최대화 + 전문가 리뷰 반영

## 관점

**"에이전트가 말을 못 알아먹는다"는 실사용 VOC가 최우선 해결 대상.**
비용/속도 최적화는 이해력 확보 후에 한다. claw-code-parity에서 좋은 것은 적극 차용하되,
온통의 use case(한국어 위키 Q&A 웹앱)에 맞지 않는 패턴은 차용하지 않는다.

### v2 → v3 변경 요약
- 하이브리드 키워드 라우팅 **삭제** (한국어 자연어에서 오분류 위험)
- query_augment에 **주제 전환 감지(topic shift detection)** 추가
- 실행 순서를 **이해력 직접 개선 항목 우선**으로 재조정
- ontong.md → Cognitive Reflect 제거 순서를 **검증 후 제거**로 변경
- 훅 시스템을 Phase 2 이후로 후퇴
- 에러 포맷을 enum 4종 → **feedback 필드 추가**로 간소화
- 프롬프트 캐싱(3-1)을 **프로바이더 확정 후**로 보류

---

## 재평가 결과: 차용 비율

| 영역 | v1 차용 | v2 차용 | v3 차용 | 변경 이유 |
|------|--------|--------|--------|----------|
| 시스템 프롬프트 | 70% | 90% | **90%** | ontong.md 전략으로 전면 도입 (유지) |
| 품질 보장 | 90% | 95% | **95%** | cognitive reflect 제거 + 프롬프트 품질 투자 (유지) |
| 컨텍스트 관리 | 50% | 80% | **80%** | 구조화된 요약 + continuation instruction + topic shift 감지 |
| 스킬 시스템 | 25% | 70% | **70%** | 마크다운 프롬프트 분리 + allowed-tools + 완료 프로토콜 (유지) |
| 오케스트레이션 | 40% | 60% | **50%** | 파이프라인 병렬화 유지, 하이브리드 라우팅 삭제 |
| 도구 시스템 | 35% | 55% | **40%** | 도구 풀 제한 유지, 훅 시스템 Phase 2로 후퇴 |

---

## Phase 1: 이해력 혁신 (VOC 직접 해결)

### 1-1. ontong.md 도입
**차용 대상**: CLAUDE.md 계층적 성격 계층 패턴
**차용 수준**: 90% — 구조와 철학 전면 차용, 내용만 온통에 맞게

- `ontong.md` 파일 생성 → 에이전트 성격/규칙 정의
- `ontong.local.md` → 환경별 오버라이드 (개발/운영)
- 시스템 프롬프트에서 ontong.md 로드 → 정적/동적 분리 주입
- **기존 FINAL_ANSWER_SYSTEM_PROMPT / COGNITIVE_REFLECT_PROMPT 상수 교체**

### 1-2. 토큰 기반 히스토리 + 구조화된 요약
**차용 대상**: compact.rs의 스마트 요약 + summary_compression.rs의 우선순위 압축
**차용 수준**: 80%

**VOC 핵심**: "대화가 길어지면 앞에서 한 말을 잊어버린다"
→ 현재 `history[-6:]` 고정 슬라이스가 원인. 7번째 턴부터 컨텍스트 유실.

구현 순서:
```
Step A: history[-6:] → 토큰 예산 기반 윈도우 (최근 메시지 최대한 유지)
Step B: 예산 초과 시 구조화된 요약 생성 (규칙 기반, LLM 아님)
         - Scope (대화 규모)
         - Skills used (사용된 스킬)
         - Recent requests (최근 요청 3개)
         - Referenced docs (참조 문서)
         - Current work (현재 작업)
Step C: Continuation instruction 추가
         "요약을 인정하지 말고 이어서 답변하라"
```

Step A만으로도 체감 개선이 크다. B-C는 A 적용 후 여전히 문제 있으면 이어서 진행.

### 1-3. query_augment 프롬프트 강화 + 주제 전환 감지
**차용 대상**: 온통 자체 개선 (분석서에 없던 항목)
**추가 근거**: 실사용 VOC — "주제를 바꿔서 물어보면 이전 내용을 어설프게 섞어서 이상한 답변"

**문제**: query_augment가 주제 전환을 감지하지 못해, 이전 주제의 컨텍스트를 새 질문에 오염시킴.
**해결**: 기존 query_augment LLM 호출에 topic_shift 판단 필드를 추가 (추가 비용 없음).

```python
# query_augment 결과 모델 확장
class AugmentResult:
    augmented_query: str
    topic_shift: bool  # 주제가 바뀌었는가?

# 주제 전환 감지 시 히스토리 주입 전략 변경
if augment_result.topic_shift:
    # 이전 히스토리 요약을 system prompt에서 제외
    # 또는 "이전 대화와 무관한 새 질문입니다" 프리픽스 추가
    history_context = []
else:
    history_context = build_history_window(session)
```

프롬프트에 추가할 규칙:
- "대화 맥락에서 빠진 주어/목적어를 반드시 복원하라"
- "이전 대화와 주제가 완전히 달라졌으면 topic_shift: true로 판단하라"

### 1-4. 스킬 프롬프트 마크다운 분리
**차용 대상**: SKILL.md 패턴 — 스킬 지시사항을 코드에서 프롬프트로 분리
**차용 수준**: 70%

```
현재: skills/wiki_search.py에 실행 로직 + LLM 지시가 혼재
개선:
  skills/wiki_search.py → 실행 로직만
  skills/prompts/wiki_search.md → LLM 지시사항 (톤, 규칙, 포맷, 완료 프로토콜)
```

- 각 스킬 프롬프트에 완료 프로토콜 내장 (DONE/BLOCKED/NEEDS_CONTEXT)
- 톤/보이스는 ontong.md에서 통합, 스킬별 특화 규칙만 개별 관리
- 프롬프트 수정 시 코드 변경 불필요 → 빠른 반복

### 1-5. Cognitive Reflect 제거 (ontong.md 검증 후)
**차용 대상**: claw-code-parity의 "self-reflect 없이 좋은 프롬프트로 품질 보장" 철학
**차용 수준**: 100%

**⚠️ 전제 조건**: ontong.md 적용 상태에서 답변 품질이 기존 대비 동등 이상임을 확인한 후 제거.

순서:
```
1. ontong.md 생성 + 기존 Cognitive Reflect와 병행 운영
2. ontong.md 적용 상태에서 A/B 비교 (동일 질문 세트로)
3. 품질 검증 후 Cognitive Reflect 제거
```

- `_run_cognitive_pipeline()` 제거
- 품질 게이트를 ontong.md의 Response Rules로 이전
- LLM 호출 1회 절약 → 속도 2배, 비용 절반

---

## Phase 2: 실행 최적화

### 2-1. 스킬별 도구 풀 제한 (allowed-tools)
**차용 대상**: GlobalToolRegistry의 도구 필터링 + SKILL.md의 allowed-tools
**차용 수준**: 70%

```python
SKILL_ALLOWED_TOOLS = {
    "WIKI_QA": ["wiki_search", "wiki_read", "llm_generate", "conflict_check"],
    "WIKI_WRITE": ["wiki_search", "wiki_read", "wiki_write", "llm_generate"],
    "WIKI_EDIT": ["wiki_search", "wiki_read", "wiki_edit", "llm_generate"],
    "SIMULATION": ["simulation_forecast", "simulation_optimize", "llm_generate"],
}
```
- 인텐트별로 LLM에 노출되는 도구 제한 → 선택 정확도 향상
- LLM이 불필요한 도구에 혼란되지 않음

### 2-2. 파이프라인 병렬화
**차용 대상**: bootstrap_session의 병렬 command+tool 실행
**차용 수준**: 60%

```python
# 현재 직렬:
augmented = await query_augment(query)
results = await vector_search(augmented)

# 개선 병렬:
augmented, results = await asyncio.gather(
    query_augment(query),
    vector_search(query)  # 원본 쿼리로 먼저 검색
)
# augmented 결과로 보충 검색 (필요 시)
```

### 2-3. SkillResult feedback 필드 추가
**차용 대상**: Result<String, String> 일관된 에러 타입
**차용 수준**: 40% (v2의 60%에서 하향)

**v2 계획의 SkillOutcome enum 4종(DONE/DONE_WITH_CONCERNS/BLOCKED/NEEDS_CONTEXT)은 과하다.**
스킬이 7개인 현재 규모에서 모든 스킬과 프론트엔드 SSE 핸들러에 4-way 분기를 넣으면 복잡도만 증가.

```python
@dataclass
class SkillResult:
    data: Any = None
    success: bool = True
    error: str | None = None
    feedback: str | None = None   # 추가: deprecated 경고, 보충 정보 등
    retry_hint: str | None = None
```

`DONE` + `feedback`으로 `DONE_WITH_CONCERNS`를 표현하고, `success=False` + `error`로 `BLOCKED`를 표현.
별도 enum 없이 기존 구조에 필드 1개 추가로 충분하다.

---

## Phase 3: 인프라 강화

### 3-1. 세션 영속성 (JSONL)
- 인메모리 → JSONL append 방식
- 서버 재시작 후 대화 복원
- 압축 이벤트도 기록

### 3-2. 스킬 권한 매핑
```python
SKILL_PERMISSIONS = {
    "wiki_search": PermissionLevel.READ,
    "wiki_write": PermissionLevel.WRITE,   # 승인 필요
    "wiki_edit": PermissionLevel.WRITE,    # 승인 필요
}
```

### 3-3. PreSkill/PostSkill 훅 (스킬 15개 이상 시)
**v2에서 Phase 2였으나 v3에서 Phase 3으로 후퇴.**
**이유**: 현재 스킬 7개에서 훅 프레임워크는 오버엔지니어링. deprecated 문서 경고, 쿼리 길이 체크 등은 인라인 코드로 충분. 스킬 수가 15개 이상으로 늘어나면 그때 프레임워크화.

```python
# Phase 3에서 도입할 훅 패턴
class QuerySanitizeHook:
    async def pre_execute(self, skill_name, ctx):
        if len(ctx.query) < 3:
            return HookResult(needs_context=True, message="좀 더 구체적으로 질문해주세요")
        return HookResult(allow=True)

class DeprecatedDocHook:
    async def post_execute(self, skill_name, result):
        deprecated = [d for d in result.docs if d.status == "deprecated"]
        if deprecated:
            result.feedback = f"⚠️ {len(deprecated)}건의 폐기 문서 포함"
        return result
```

---

## 🎯 실행 순서 (v3 — 이해력 우선)

```
--- Phase 1: 이해력 혁신 (VOC 직접 해결) ---
1. ontong.md 생성 + 시스템 프롬프트 교체           ← 이해력의 기반
2. 토큰 기반 히스토리 + 구조화된 요약              ← 컨텍스트 유실 해결
3. query_augment 강화 + 주제 전환 감지            ← 컨텍스트 오염 해결
4. 스킬 프롬프트 마크다운 분리                     ← 스킬별 이해력 향상
5. Cognitive Reflect 제거 (1번 검증 후)            ← 속도 + 비용

--- Phase 2: 실행 최적화 ---
6. 스킬별 도구 풀 제한 (allowed-tools)             ← 도구 선택 정확도
7. 파이프라인 병렬화                              ← 속도
8. SkillResult feedback 필드 추가                 ← 안정성

--- Phase 3: 인프라 강화 (규모 확대 후) ---
9.  세션 JSONL 영속성                             ← 장기 운영
10. 스킬 권한 매핑                                ← 거버넌스
11. PreSkill/PostSkill 훅 시스템                   ← 스킬 15개+ 시

--- Phase 4: Q&A ReAct 루프 (만족도 결정적 도약) ---
12. Q&A 멀티턴 자율 검색                           ← 답변 정확도 근본 해결
13. 검색 결과 자기 평가 + 재검색 전략               ← 자기 수정 능력
14. 사용자 확인 루프 (선택적)                       ← 고위험 답변 신뢰도
```

### v2 대비 변경점
- ~~하이브리드 라우팅~~ → **삭제** (한국어 자연어에서 키워드 매칭은 오분류 위험. 현재 LLM 라우터 유지, 필요 시 라우팅 전용 저비용 모델 지정)
- query_augment + topic shift 감지 → **신규 추가** (3번)
- Cognitive Reflect 제거 → 1번에서 **5번으로 이동** (ontong.md 검증 후 제거)
- 훅 시스템 → Phase 2에서 **Phase 3으로 후퇴**
- 에러 포맷 → enum 4종 대신 **feedback 필드 1개 추가**로 간소화

---

## Phase 4: Q&A ReAct 루프 (v3 완료 후)

### 문제 인식
v3(Phase 1-3)로 VOC의 70-80%는 해결되지만, 근본적 한계가 남는다:
- **단발 응답 구조**: 검색이 엉뚱한 결과를 가져오면 복구할 방법이 없다
- **자기 수정 불가**: Claude Code는 파일을 여러 번 읽으며 맥락을 쌓지만, 온통 Q&A는 한 번에 맞춰야 한다
- 이해력이 90%여도 나머지 10%에서 사용자가 실망한다

### 핵심 아이디어
현재 `tool_executor.py`의 ReAct 루프는 write/edit 액션에서만 사용된다.
이를 **Q&A에도 확장**하여, 에이전트가 검색 결과를 보고 부족하면 스스로 재검색하는 구조로 만든다.

### 4-1. Q&A 멀티턴 자율 검색

**현재 (단발)**:
```
사용자: "작년에 바뀐 휴가 규정 알려줘"
→ wiki_search("휴가 규정") → 3건 → 답변 생성 (변경분이 없어도 있는 걸로 답변)
```

**개선 (ReAct 루프)**:
```
사용자: "작년에 바뀐 휴가 규정 알려줘"

Turn 1: wiki_search("휴가 규정") → 3건 반환
Turn 2: 에이전트 판단 — "작년 변경분"에 해당하는 내용 없음
         → wiki_search("휴가 규정 변경 2025") 재검색
Turn 3: 관련 문서 발견 → 답변 생성
```

**구현 방향**:
```python
# rag_agent.py의 _handle_qa를 ReAct 기반으로 교체
async def _handle_qa_react(self, ctx: AgentContext):
    """Q&A를 멀티턴 ReAct 루프로 실행. 최대 max_turns까지 자율 검색."""

    react_agent = create_react_agent(
        model=get_model(),
        system_prompt=load_ontong_md() + qa_react_instructions,
        tools=[wiki_search, wiki_read, conflict_check],
        max_turns=4,          # 무한 루프 방지
        max_budget_tokens=3000,  # 비용 상한
    )

    async for event in react_agent.run(ctx.request.message, history=ctx.history):
        if isinstance(event, ToolCallEvent):
            yield ctx.sse("thinking_step", {"tool": event.tool_name, "args": event.args})
        elif isinstance(event, ContentDelta):
            yield ctx.sse("content_delta", {"text": event.text})
```

**Q&A ReAct 전용 프롬프트 규칙** (`skills/prompts/qa_react.md`):
```markdown
## 검색 전략
1. 첫 검색 결과를 받으면, 사용자 질문에 실제로 답할 수 있는지 판단하라
2. 답할 수 없으면:
   - 검색어를 구체화하여 재검색 (날짜, 키워드 추가)
   - 관련 문서를 wiki_read로 전문 확인
   - 다른 관점의 검색어로 시도
3. 답할 수 있으면: 즉시 답변 생성 (불필요한 추가 검색 금지)

## 중단 조건
- 검색 3회 이상 했는데 관련 문서 없음 → 솔직하게 "찾지 못했습니다" 답변
- 부분적으로만 답할 수 있음 → 있는 것만 답하고 부족한 부분 명시

## 비용 통제
- max_turns: 4 (검색 3회 + 답변 1회가 상한)
- 첫 검색에서 충분하면 Turn 1에서 바로 답변 (기존과 동일한 비용)
- 평균 케이스는 1-2턴, 어려운 케이스만 3-4턴
```

### 4-2. 검색 결과 자기 평가 + 재검색 전략

에이전트가 검색 결과의 **충분성을 판단**하는 기준을 명시적으로 제공:

```python
# 검색 결과 평가 기준 (프롬프트에 내장)
SEARCH_SUFFICIENCY_RULES = """
다음 기준으로 검색 결과가 충분한지 판단하라:

충분함:
- 사용자 질문의 핵심 키워드가 검색 결과에 존재
- 시간 범위가 일치 (작년 → 2025년 문서)
- 구체적 수치/절차/규정이 포함

불충분함:
- 질문의 핵심이 검색 결과에 없음 (일반적인 관련 문서만 있음)
- 시간 범위 불일치
- 제목만 관련되고 내용은 다른 주제
"""
```

**재검색 전략**:
```python
RETRY_STRATEGIES = """
재검색 시 다음 전략을 순서대로 시도:
1. 구체화: "휴가 규정" → "연차 휴가 규정 변경 2025"
2. 동의어: "휴가" → "연차", "휴직", "leave"
3. 상위 개념: "연차 휴가 변경" → "인사 규정 개정"
4. 문서 탐색: 관련 문서를 wiki_read로 전문 읽기 → 내부 링크 따라가기
"""
```

### 4-3. 사용자 확인 루프 (선택적)

답변 신뢰도가 낮을 때, 답변 전에 사용자에게 확인하는 옵션:

```python
# 낮은 확신도일 때 SSE 이벤트로 중간 확인
if confidence < 0.5 and search_turns >= 2:
    yield ctx.sse("clarification_request", {
        "message": "이런 내용을 찾았는데, 찾으시는 게 맞나요?",
        "candidates": [doc.title for doc in top_results[:3]],
    })
    # 프론트엔드에서 사용자 선택 → 후속 요청으로 이어짐
```

이건 UX 설계가 필요하므로 프론트엔드 팀과 협의 후 구현.

### Phase 4 비용 영향
| 케이스 | 현재 (단발) | ReAct 루프 | 비용 증가 |
|--------|------------|-----------|----------|
| 명확한 질문, 검색 적중 | LLM 1회 | LLM 1회 (Turn 1에서 종료) | **없음** |
| 애매한 질문, 재검색 필요 | LLM 1회 (부정확한 답변) | LLM 2-3회 (정확한 답변) | 2-3배 |
| 어려운 질문, 문서 부재 | LLM 1회 (환각 답변) | LLM 3-4회 ("못 찾았습니다") | 3-4배 |

**핵심**: 쉬운 질문은 비용 동일, 어려운 질문만 비용 증가. 그리고 어려운 질문에서 환각 답변을 주는 것보다 비용을 써서라도 정확한 답변(또는 솔직한 "모름")을 주는 게 사용자 신뢰에 훨씬 낫다.

### Phase 4 전제 조건
- Phase 1 완료 (ontong.md + 히스토리 + query_augment가 안정화되어야 ReAct 품질이 나옴)
- Phase 2의 allowed-tools 완료 (ReAct에서 도구 풀 제한이 없으면 에이전트가 엉뚱한 도구 호출)

---

## 보류 항목 (온통 아키텍처에 맞지 않음)

| 항목 | 보류 이유 |
|------|----------|
| 하이브리드 키워드 라우팅 | 한국어 자연어에서 키워드 매칭 오분류율 높음. "찾아서 고쳐줘" → "찾아" 매칭 → WIKI_QA 오분류. 조사/어미 변형 폭발. LLM 라우터 유지가 정답 |
| 시스템 프롬프트 캐싱 (정적/동적 분리) | LiteLLM prompt caching은 Anthropic API의 cache_control 기반. ollama 로컬 모델에서 미작동. 상용 API 전환 확정 후 도입 |
| 스킬 계층 디스커버리 (프로젝트→사용자→글로벌) | 웹 앱이라 디렉토리 계층 없음 |
| 스킬 섀도잉 | 단일 서버에서 운영, 오버라이드 불필요 |
| Bash 읽기전용 휴리스틱 | 온통에 bash 도구 없음 |
| 워크스페이스 경계 체크 | 파일 시스템 직접 접근 없음 |
| 정책 엔진 (LaneContext) | 멀티레인 에이전트 아님 |
| Bootstrap Graph 7단계 | CLI 초기화 패턴, 웹 서버와 다름 |
| Deferred Tool Search | 도구 수가 적어서 불필요 |
| MCP 통합 | 현재 외부 도구 연동 없음 |
| 텔레메트리 (스킬 사용 로깅) | Langfuse로 이미 커버 |
