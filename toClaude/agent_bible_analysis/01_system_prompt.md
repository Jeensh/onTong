# 01. System Prompt & 응답 품질 전략 — claw-code-parity

## 핵심 아키텍처: Builder Pattern 기반 시스템 프롬프트

### 프롬프트 구성 순서 (10개 섹션)
```
1. Simple Intro — 페르소나 정의
2. Output Style — 응답 포맷 가이드라인 (옵션)
3. System Section — 핵심 행동 규칙
4. Doing Tasks — 작업 실행 원칙
5. Executing Actions with Care — 리스크 관리
6. __SYSTEM_PROMPT_DYNAMIC_BOUNDARY__ — 정적/동적 구분선
7. Environment Context — 모델, CWD, 날짜, 플랫폼
8. Project Context — git status, git diff
9. Claude Instructions — CLAUDE.md 등 (중복 제거)
10. Runtime Config — .claude.json 설정
```

### 핵심 설계 원칙

#### 1. 정적/동적 분리
- `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__`로 명확히 구분
- 정적: 페르소나, 행동 규칙 (변하지 않음)
- 동적: 환경, 프로젝트, 설정 (매 세션 갱신)

#### 2. 행동 규칙이 구체적
온통의 "공감적 IT 파트너"와 달리, **구체적 판단 기준** 제공:
- "Read relevant code before changing it"
- "Do not add speculative abstractions"
- "If an approach fails, diagnose the failure before switching tactics"
- "Report outcomes faithfully: if verification fails, say so explicitly"
- "Carefully consider reversibility and blast radius"

#### 3. Output Style 설정 가능
```rust
SystemPromptBuilder::new()
    .with_output_style("Concise", "Prefer short answers.")
```
- 사용자가 응답 스타일을 커스터마이징 가능

#### 4. 지시 파일 계층적 발견 & 중복 제거
```
/ → CLAUDE.md
/project/ → CLAUDE.md (오버라이드)
/project/sub/ → CLAUDE.md (더 구체적)
```
- 콘텐츠 해시로 중복 제거
- 파일당 4,000자, 전체 12,000자 제한

### Git 인식 컨텍스트
- `git status --short --branch` 자동 캡처
- staged/unstaged diff 자동 주입
- 에이전트가 현재 작업 상태를 인식하고 판단

---

## 응답 품질 전략: Self-Reflect 대신 "좋은 프롬프트"

### claw-code-parity의 접근법
- **Self-reflection/critique 단계 없음**
- 대신 시스템 프롬프트에 구체적 행동 규칙 내장
- "Report outcomes faithfully" — 모호한 답변 금지
- "Diagnose before switching" — 성급한 전환 금지

### 온통 Cognitive Reflect와의 비교

| 항목 | 온통 (현재) | claw-code-parity |
|------|-----------|------------------|
| 품질 보장 방식 | 3단계 self-reflect (LLM 호출 추가) | 시스템 프롬프트에 규칙 내장 |
| 레이턴시 | +1 LLM 호출 (500ms~2s) | 추가 호출 없음 |
| 효과 | 모델이 자기 비판을 잘 못함 | 처음부터 올바른 방향 유도 |
| 토큰 비용 | 2배 (reflect + answer) | 1배 |

---

## 🔄 온통 에이전트 적용 인사이트

### 1. 시스템 프롬프트 전면 리디자인
**현재 문제**: 추상적 규칙 나열 ("민토 피라미드", "공감적 응답")
**개선 방향**: 구체적 판단 기준으로 전환

```
Before: "사용자의 상황을 먼저 공감하라"
After:  "사용자가 문제를 설명하면, 먼저 원인 가능성 2-3개를 제시하고,
         각 원인에 대한 확인 방법을 구체적으로 안내하라.
         '어려우시겠습니다' 같은 공감 문구는 불필요."
```

### 2. Cognitive Reflect 제거 또는 간소화
- 추가 LLM 호출 제거 → 레이턴시 절반 감소
- 대신 시스템 프롬프트 품질 투자

### 3. 정적/동적 프롬프트 분리
- 핵심 페르소나+규칙은 캐싱 가능 (프롬프트 캐시 활용)
- 동적 부분만 매 요청 갱신

### 4. Git/프로젝트 컨텍스트 자동 주입
- 현재 온통은 위키 문서만 RAG → 프로젝트 상태 인식 없음
- claw-code-parity처럼 환경 정보 자동 주입 고려

### 5. Output Style 커스터마이징
- 사용자별 응답 스타일 설정 가능하게
- "간결하게" vs "상세하게" 등
