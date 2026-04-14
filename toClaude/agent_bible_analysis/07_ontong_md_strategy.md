# 07. ontong.md 전략 — CLAUDE.md 패턴 분석 & 온통 적용

## claw-code-parity의 CLAUDE.md 전략

### 핵심 메커니즘
CLAUDE.md는 단순한 문서가 아니라 **에이전트의 성격 계층(personality layer)**으로 시스템 프롬프트에 주입됨.

### 발견 & 주입 흐름
```
1. CWD에서 루트까지 상위 디렉토리 순회
2. 각 디렉토리에서 4개 파일 탐색:
   - CLAUDE.md (primary)
   - CLAUDE.local.md (로컬 오버라이드)
   - .claw/CLAUDE.md (구조화)
   - .claw/instructions.md (대안 이름)
3. 루트→현재 순서로 정렬 (부모가 먼저, 자식이 구체화)
4. 콘텐츠 해시로 중복 제거
5. 파일당 4,000자 / 전체 12,000자 예산 내에서 렌더링
6. __SYSTEM_PROMPT_DYNAMIC_BOUNDARY__ 이후에 주입 (동적 컨텍스트)
```

### 프롬프트 전체 구조
```
[정적 영역 — 캐싱 가능]
1. Intro (페르소나)
2. Output Style (옵션)
3. System Rules (핵심 행동 규칙)
4. Doing Tasks (작업 원칙)
5. Action Safety (리스크 관리)

__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__

[동적 영역 — 매 세션 갱신]
6. Environment (OS, 날짜, CWD)
7. Project Context (git status/diff)
8. Instruction Files (CLAUDE.md 등)  ← 성격 계층
9. Runtime Config (설정)
```

### CLAUDE.md 실제 내용 (22줄, ~800자)
```markdown
# CLAUDE.md
## Detected stack — 언어/프레임워크
## Verification — 검증 명령어
## Repository shape — 디렉토리 구조 설명
## Working agreement — 행동 계약
  - 작은 리뷰 가능한 변경 선호
  - 공유 설정은 .claude.json에, 로컬은 settings.local.json에
  - CLAUDE.md를 자동으로 덮어쓰지 말 것
```

### 핵심 인사이트
1. **800자로 성격이 결정됨** — 짧고 명확할수록 효과적
2. **계층 상속** — 루트(기본) → 하위(구체화)로 자연스러운 오버라이드
3. **예산 제한이 품질을 강제** — 4,000/12,000자 제한이 장황함 방지
4. **동적 영역에 배치** — 프로젝트 맥락과 함께 처리되어 적응적

---

## ontong.md 설계안

### 파일 위치 & 계층
```
backend/
├── ontong.md              ← 전체 에이전트 성격 + 행동 규칙
├── ontong.local.md        ← 환경별 오버라이드 (개발/운영)
└── application/agent/
    └── ontong.md          ← 에이전트 모듈 전용 규칙 (선택)
```

### ontong.md 초안 구조
```markdown
# On-Tong AI Assistant

## Identity
사내 위키 기반 AI 어시스턴트. 동료 엔지니어처럼 간결하고 구체적으로 답한다.

## Response Rules
1. 결론을 첫 문장에 쓴다. 근거는 그 다음.
2. 문서에 없는 내용은 추측하지 않는다. "관련 문서를 찾지 못했습니다"로 처리.
3. 문서를 인용할 때 출처(파일명, 섹션)를 명시한다.
4. 후속 확인이 필요하면 구체적 질문 1-2개를 제안한다.
5. 공감 문구("어려우시겠습니다")는 사용하지 않는다.

## Quality Gates
- 검색 결과가 0건이면 솔직히 말한다. 억지로 답변하지 않는다.
- 여러 문서가 모순되면 충돌을 명시하고 어느 문서가 최신인지 알린다.
- 답변 길이는 질문 복잡도에 비례. 단순 질문에 장문 금지.

## Tone
간결, 구체적, 직접적. 컨설턴트가 아니라 옆자리 동료처럼.

## Context Awareness
- 대화 히스토리 요약이 있으면 인정하지 말고 바로 이어서 답한다.
- 이전 턴에서 검색한 문서가 현재 질문과 관련 있으면 재활용한다.
```

### 주입 방식 (현재 온통 아키텍처 기반)
```python
# rag_agent.py에서
def _build_system_prompt(self, context: str, history_summary: str = "") -> str:
    # 1. 정적 영역: ontong.md 로드 (캐싱)
    static_prompt = self._load_ontong_md()
    
    # 2. 동적 영역: RAG 컨텍스트 + 히스토리 요약
    dynamic_parts = []
    if history_summary:
        dynamic_parts.append(f"## 이전 대화 요약\n{history_summary}")
    if context:
        dynamic_parts.append(f"## Wiki 컨텍스트\n{context}")
    
    return static_prompt + "\n---\n" + "\n\n".join(dynamic_parts)
```

### ontong.local.md (환경별 오버라이드)
```markdown
# 개발 환경 설정
- 모델: gpt-4o
- 응답 최대 길이: 2000 토큰
- 디버그 로깅: 활성화
- 충돌 감지: 엄격 모드
```
