# 09. Hooks & Permissions 심층 분석

## 핵심 발견: 훅은 보안만이 아니라 "응답 품질 거버넌스"

### 3계층 안전 아키텍처
```
Layer 1: Hooks (PreToolUse / PostToolUse / PostToolUseFailure)
  → 입력 변환, 권한 오버라이드, 피드백 주입
  
Layer 2: Permissions (모드 계층 + 규칙 매칭)
  → ReadOnly < WorkspaceWrite < DangerFullAccess
  → 패턴 기반 규칙: bash(git:*) → allow, bash(rm:*) → deny
  
Layer 3: Enforcer (실행 시점 검증)
  → 워크스페이스 경계 체크
  → Bash 읽기전용 휴리스틱 (229개 화이트리스트)
```

### 훅의 핵심 기능: 입력 변환 (Input Transformation)

```
PreToolUse 훅이 도구 입력을 변환할 수 있음:

원래 입력: {"command": "rm -rf /important"}
    ↓ 훅 실행
변환된 입력: {"command": "ls -la /important"}
    ↓
변환된 입력이 권한 체크 + 실행에 사용됨
```

```rust
let effective_input = pre_hook_result
    .updated_input()
    .map_or_else(|| input.clone(), ToOwned::to_owned);
// effective_input이 이후 모든 처리에 사용됨
```

### 훅 출력 구조
```json
{
  "systemMessage": "사용자에게 보이는 피드백",
  "reason": "왜 이런 결정을 했는지",
  "hookSpecificOutput": {
    "permissionDecision": "allow|deny|ask",
    "updatedInput": {"transformed": "input"},
    "additionalContext": "추가 맥락"
  }
}
```

### 피드백 머징: 도구 결과에 훅 메시지 추가
```
도구 결과: "검색 결과 3건"
훅 피드백: "이 중 2건은 deprecated 문서입니다"
    ↓
합성 결과: "검색 결과 3건\n\nHook feedback:\n이 중 2건은 deprecated 문서입니다"
```
- 실행을 차단하지 않으면서 맥락 추가 가능

---

## 권한 체계

### 5단계 모드
```
ReadOnly        ← 가장 제한적
WorkspaceWrite  ← 파일 쓰기 허용 (워크스페이스 내)
DangerFullAccess ← 모든 도구 허용
Prompt          ← 매번 사용자 확인
Allow           ← 모든 것 허용
```

### 규칙 기반 세밀한 제어
```rust
// 패턴 매칭:
"bash(git:*)"           // git으로 시작하는 bash 명령 허용
"bash(rm -rf:*)"        // rm -rf 차단
"read_file(*)"          // 모든 파일 읽기 허용
"write_file(/etc/*:*)"  // /etc 쓰기 시 확인 요청
```

### 권한 결정 흐름
```
1. deny 규칙 매치? → 즉시 거부
2. 훅이 Deny 반환? → 즉시 거부
3. 훅이 Ask 반환? → 사용자 확인 요청
4. 훅이 Allow 반환? → ask 규칙 확인 후 허용/확인
5. allow 규칙 매치? → 허용
6. 모드 계층 체크? → 모드 ≥ 요구 모드면 허용
7. 그 외 → 거부
```

---

## 온통 에이전트 적용 방안 (재평가)

### 기존 평가: 35% 차용 → 수정 평가: 55% 차용

### 도입 가능한 패턴

#### 1. PreSkill / PostSkill 훅 (도입 권장)
```python
class SkillHook:
    async def pre_execute(self, skill_name: str, ctx: AgentContext) -> HookResult:
        """스킬 실행 전 검증/변환"""
        pass
    
    async def post_execute(self, skill_name: str, result: SkillResult) -> SkillResult:
        """스킬 결과에 피드백 추가"""
        pass

# 예시: wiki_search 결과에 deprecated 경고 추가
class DeprecatedDocHook(SkillHook):
    async def post_execute(self, skill_name, result):
        if skill_name == "wiki_search":
            deprecated = [d for d in result.docs if d.status == "deprecated"]
            if deprecated:
                result.feedback = f"주의: {len(deprecated)}건의 문서가 폐기 상태입니다"
        return result
```

#### 2. 스킬별 권한 매핑 (도입 권장)
```python
SKILL_PERMISSIONS = {
    "wiki_search": PermissionLevel.READ,
    "wiki_read": PermissionLevel.READ,
    "wiki_write": PermissionLevel.WRITE,    # 승인 필요
    "wiki_edit": PermissionLevel.WRITE,     # 승인 필요
    "llm_generate": PermissionLevel.EXECUTE,
    "conflict_check": PermissionLevel.READ,
}
```

#### 3. 입력 검증/변환 (도입 권장)
```python
# PreSkill 훅: 검색 쿼리 정제
class QuerySanitizeHook(SkillHook):
    async def pre_execute(self, skill_name, ctx):
        if skill_name == "wiki_search":
            # 너무 짧은 쿼리 → 보강
            if len(ctx.query) < 5:
                return HookResult(needs_context=True, message="좀 더 구체적으로 질문해주세요")
            # 특수문자 정리, 불용어 제거 등
            ctx.query = sanitize(ctx.query)
        return HookResult(allow=True)
```

#### 4. 피드백 머징 (도입 권장)
```python
# 도구 결과 + 훅 피드백을 LLM에 함께 전달
def merge_feedback(result: SkillResult, hook_feedback: str) -> str:
    if not hook_feedback:
        return result.data
    return f"{result.data}\n\n---\n⚠️ {hook_feedback}"
```

### 보류하는 패턴
- Bash 읽기전용 휴리스틱 (229개 화이트리스트) → 온통에 bash 도구 없음
- 워크스페이스 경계 체크 → 파일 시스템 접근 없음
- 사용자 확인(Prompt 모드) → 이미 승인 플로우 있음
- 정책 엔진(LaneContext) → 멀티레인 에이전트 아님
