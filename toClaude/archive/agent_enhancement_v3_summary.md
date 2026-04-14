# 에이전트 고도화 v3 완료 요약

## 작업 기간
- 세션 29~30 (2026-04-04 ~ 2026-04-05)

## 완료 현황: 15/17 tasks (2 deferred)

### Phase 1: 이해력 혁신 (8/8)
- AG-1-1: ontong.md 에이전트 인격 정의
- AG-1-2: 시스템 프롬프트 교체 (get_system_prompt)
- AG-1-3: 토큰 기반 히스토리 윈도우 (4000 토큰)
- AG-1-4: 구조화된 대화 요약 (규칙 기반, LLM 호출 없음)
- AG-1-5: Continuation instruction (요약 후 자연스러운 이어가기)
- AG-1-6: query_augment + topic_shift 감지
- AG-1-7: 스킬 프롬프트 마크다운 분리 (5개 .md 파일)
- AG-1-8: Cognitive Reflect 파이프라인 제거 (LLM 1회 절약)

### Phase 2: 실행 최적화 (3/3)
- AG-2-1: 스킬별 도구 풀 제한 (INTENT_ALLOWED_SKILLS)
- AG-2-2: 파이프라인 병렬화 (routing+augment asyncio.gather)
- AG-2-3: SkillResult feedback/retry_hint 필드

### Phase 3: 인프라 강화 (2/3)
- AG-3-1: 세션 JSONL 영속성 (서버 재시작 후 복원)
- AG-3-2: 스킬 권한 매핑 (READ/WRITE/EXECUTE + 역할 검증)
- AG-3-3: ~~PreSkill/PostSkill 훅~~ → deferred (스킬 15개+ 시)

### Phase 4: Q&A ReAct 루프 (2/3)
- AG-4-1: Q&A 멀티턴 자율 검색 (관련도 기반 평가 + 재검색)
- AG-4-2: 재검색 전략 5단계 (구체화→시간→동의어→상위개념→탐색)
- AG-4-3: ~~사용자 확인 루프~~ → deferred (UX 협의 필요)

## 핵심 성과
| 지표 | Before | After |
|------|--------|-------|
| LLM 호출/질문 | 2~3회 | 1회 (ReAct 시 2회) |
| 히스토리 윈도우 | 고정 6턴 | 토큰 기반 4000 |
| 주제 전환 대응 | 없음 | topic_shift 감지 |
| 검색 실패 복구 | 없음 | ReAct 자율 재검색 |
| 세션 영속성 | 인메모리 | JSONL 파일 |
| 스킬 권한 | 없음 | READ/WRITE/EXECUTE |

## 테스트 현황
- pytest: 38+ tests passed (AG 전용 7개 테스트 파일)
- RAG 채팅 테스트: 전 Phase 완료
- 권한 매핑: viewer 차단 + editor 통과 확인
- ReAct: LLM 평가 → 재검색 쿼리 생성 확인

## 변경 파일 목록
- `backend/ontong.md` — 에이전트 인격
- `backend/application/agent/rag_agent.py` — 핵심 에이전트 (히스토리, 요약, ReAct)
- `backend/application/agent/skill.py` — PermissionLevel, SKILL_PERMISSIONS, SkillResult feedback
- `backend/application/agent/context.py` — INTENT_ALLOWED_SKILLS, 권한 검증
- `backend/application/agent/models.py` — QueryAugmentResult, SearchEvaluation
- `backend/application/agent/skills/prompt_loader.py` — 프롬프트 로더
- `backend/application/agent/skills/prompts/` — 5개 .md 프롬프트 파일
- `backend/core/session.py` — JSONL 영속성
- `backend/api/agent.py` — append_message, topic_shift 전달
