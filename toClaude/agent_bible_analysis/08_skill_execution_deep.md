# 08. Skill 실행 메커니즘 심층 분석

## 스킬 프롬프트가 LLM에 주입되는 방식

### 핵심 발견: 스킬 = 도구 결과로 주입되는 프롬프트

```
사용자 "/qa" 입력
  → Skill 도구 호출 (tool_use)
  → resolve_skill_path() → SKILL.md 로드
  → SkillOutput { prompt: "전체 마크다운 내용" } 반환
  → 도구 결과(tool_result)로 LLM에 전달
  → LLM은 이 프롬프트를 지시사항으로 인식하고 따름
  → 기본 시스템 프롬프트와 "공존" (대체가 아닌 추가)
```

**핵심**: 스킬 프롬프트는 시스템 메시지를 교체하는 게 아니라, **도구 결과로 대화에 추가**됨.
기본 안전 규칙(시스템 프롬프트)은 유지하면서 스킬 특화 지시가 덧붙여짐.

### allowed-tools의 실제 동작

```yaml
# SKILL.md frontmatter
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
```

**2중 보안**:
1. **API 레벨**: LLM에게 보내는 도구 정의 자체를 필터링 → LLM이 다른 도구를 호출할 수 없음
2. **런타임 레벨**: SubagentToolExecutor가 실행 시점에 다시 검증

```rust
// API 레벨: 도구 목록 필터
definitions(allowed_tools: Option<&BTreeSet<String>>) → 필터된 도구만 반환

// 런타임 레벨: 실행 시 게이트
if !self.allowed_tools.contains(tool_name) { return Err("not allowed") }
```

### preamble-tier: 스킬 초기화 순서

```
Tier 1: 인프라 스킬 (browse, gstack) → 먼저 초기화
Tier 2: 고급 스킬 (cso, investigate) → Tier 1 이후
```
- {{PREAMBLE}} 템플릿 자리표시자 → 실제 bash 설정 스크립트로 교체
- 레이스 컨디션 방지 (브라우저가 준비되기 전에 테스트 시작 방지)

---

## 왜 마크다운 스킬이 Python 클래스보다 좋은 답변을 만드는가

### 1. 프롬프트가 곧 스펙
- `/investigate` 스킬: "Iron Law: NO FIXES WITHOUT ROOT CAUSE" → 4단계 디버깅 프로세스
- `/cso` 스킬: 622줄 마크다운, 14단계 보안 감사 → 코드로는 유지보수 불가능
- LLM은 "이 함수를 호출하라"보다 "이 절차를 따르라"를 더 잘 이해함

### 2. 선언적 제약
```
Python 클래스: execute() 안에서 if-else로 도구 제한 → 추적 어려움
마크다운 스킬: allowed-tools: [Bash, Read] → 한눈에 파악
```

### 3. 반복 최적화 용이
```
Python: 코드 수정 → 배포 → 테스트
마크다운: 프롬프트 편집 → 즉시 테스트 → 반복
```

### 4. 톤/보이스 명시
```markdown
## Voice
Tone: direct, concrete, sharp, never corporate, never academic.
Sound like a builder, not a consultant.
```
- Python 클래스에서는 톤을 코드로 표현하기 어려움
- 마크다운에서는 자연어로 명시 → LLM이 정확히 따름

### 5. 완료 프로토콜 내장
```markdown
- DONE — 모든 단계 완료. 증거 제시.
- DONE_WITH_CONCERNS — 완료했지만 주의사항 있음.
- BLOCKED — 진행 불가. 차단 원인과 시도한 내용 명시.
- NEEDS_CONTEXT — 계속하려면 추가 정보 필요.
```

---

## 온통 에이전트 적용 방안 (재평가)

### 기존 평가: 25% 차용 → 수정 평가: 70% 차용

**이전에 보류한 이유**: 아키텍처 변경이 크다고 판단
**재평가 이유**: 성능 최대화가 목표이고, 마크다운 스킬은 답변 품질에 직접적 영향

### 도입 방안

#### A. 스킬 프롬프트 분리 (Python 코드에서 마크다운으로)
```
현재:
  skills/wiki_search.py → execute() 메서드 안에 로직 하드코딩

개선:
  skills/wiki_search.py → execute()는 실행 로직만
  skills/prompts/wiki_search.md → LLM 지시사항 (톤, 규칙, 포맷)
```

#### B. 스킬별 allowed-tools 적용
```python
SKILL_TOOL_MAP = {
    "wiki_search": ["wiki_search", "llm_generate"],
    "wiki_write": ["wiki_search", "wiki_read", "wiki_write", "llm_generate"],
    "conflict_check": ["wiki_search", "conflict_check", "llm_generate"],
}
```

#### C. 완료 프로토콜을 스킬 프롬프트에 내장
```markdown
# wiki_search.md

## 검색 완료 시 응답 규칙
- DONE: 관련 문서를 찾았고 답변 가능
- DONE_WITH_CONCERNS: 문서를 찾았지만 오래되었거나 모순 있음
- BLOCKED: 검색 자체가 실패 (ChromaDB 연결 등)
- NEEDS_CONTEXT: 질문이 너무 모호해서 재검색 필요
```

#### D. 톤/보이스 설정을 ontong.md에서 통합 관리
- 개별 스킬이 아닌 ontong.md에서 전체 톤 정의
- 스킬 프롬프트는 해당 스킬의 특화 규칙만 담당
