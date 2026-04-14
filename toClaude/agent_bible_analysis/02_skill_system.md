# 02. Skill System 분석 — claw-code-parity

## 핵심 아키텍처

### 스킬 = Markdown 파일 (SKILL.md)
- 스킬은 코드가 아니라 **마크다운 프롬프트 파일**
- YAML frontmatter (메타데이터) + Content (실행 프롬프트) 분리
- 스킬 실행 = 프롬프트를 LLM에 주입하는 것

```yaml
---
name: gstack
preamble-tier: 1
version: 1.1.0
description: |
  Fast headless browser for QA testing...
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---
(프롬프트 본문)
```

### 계층적 디스커버리 & 섀도잉
```
우선순위 (높음 → 낮음):
1. 프로젝트 .codex/skills/
2. 프로젝트 .claude/skills/
3. $CODEX_HOME/skills/
4. 사용자 ~/.codex/skills/
5. 사용자 ~/.claude/skills/
```
- 같은 이름 스킬 → 상위 경로가 하위를 shadow
- 프로젝트별 스킬 오버라이드 가능

### 스킬 실행 플로우
```
사용자 "/qa" 입력
  → Skill 툴 호출 (skill="qa")
  → resolve_skill_path(): 검색 경로 순회하며 SKILL.md 찾기
  → SKILL.md 전체 내용 로드
  → frontmatter에서 metadata 추출
  → SkillOutput { prompt, description, args } 반환
  → 프롬프트가 LLM 컨텍스트에 주입되어 실행
```

### 핵심 설계 패턴

1. **Frontmatter + Content 분리** — 메타데이터와 실행 로직 분리
2. **allowed-tools 제한** — 스킬별 허용 툴 세트 제한 (보안)
3. **Preamble-tier 기반 초기화** — 환경 설정 쿼리가 먼저 실행
4. **구성 기반 행동** — config 파일로 proactive mode, telemetry 등 제어
5. **암묵적 합성** — 스킬 체이닝은 프레임워크가 아닌 프롬프트 내 지시로 수행
6. **구조화된 완료 프로토콜** — DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT

### 스킬 프롬프트 내부 구조 (gstack 예시)
```
1. Preamble (bash 초기화 스크립트)
2. Voice/Tone 설정 ("direct, concrete, sharp, never corporate")
3. Configuration-Aware 행동 규칙
4. 메인 지시사항
5. 완료 프로토콜 (DONE/BLOCKED/NEEDS_CONTEXT)
6. 텔레메트리 로깅
```

---

## 🔄 온통 에이전트 적용 인사이트

### 현재 온통 스킬 시스템 vs claw-code-parity

| 항목 | 온통 (현재) | claw-code-parity |
|------|-----------|------------------|
| 스킬 정의 | Python Protocol 클래스 | Markdown 파일 (SKILL.md) |
| 라우팅 | LLM 인텐트 분류 + SkillMatcher | 명시적 슬래시 커맨드 + 경로 해석 |
| 실행 | Python execute() 메서드 | 프롬프트 주입 |
| 행동 제어 | 코드에 하드코딩 | frontmatter + config 파일 |
| 합성 | 없음 | 프롬프트 내 암묵적 합성 |
| 완료 보고 | 없음 | DONE/BLOCKED/NEEDS_CONTEXT |

### 도입 가능한 전략

1. **완료 프로토콜 도입** — 스킬 결과에 DONE/BLOCKED/NEEDS_CONTEXT 상태 추가
   - 현재: 스킬이 결과만 반환, 성공/실패 구분 없음
   - 개선: 구조화된 상태로 후속 처리 결정

2. **Voice/Tone 설정** — 시스템 프롬프트에 명확한 톤 지시 추가
   - "direct, concrete, sharp, never corporate" 같은 명확한 톤 정의
   - 현재 온통의 "공감적 IT 파트너"는 너무 추상적

3. **allowed-tools 제한** — 스킬별 사용 가능 툴 제한
   - wiki_search 스킬이 wiki_write를 호출하지 않도록 등

4. **Preamble 초기화** — 스킬 실행 전 환경 상태 확인
   - DB 연결 상태, 인덱싱 상태 등 사전 확인

5. **Configuration-Driven 행동** — 사용자 설정에 따른 동적 행동 변경
   - 응답 상세도, 자동 제안 on/off 등
