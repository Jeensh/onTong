# User-Facing Skill System 구현 요약

## 완료 내역 (15 tasks, 6 phases)

### Phase 1: 데이터 모델 + 백엔드 기반
- `schemas.py`: SkillMeta, SkillListResponse, SkillCreateRequest 추가. ChatRequest에 skill_path, GraphNode에 node_type 추가
- `skill_loader.py`: _skills/ 폴더 스캔, frontmatter 파싱, 30s TTL 캐시, [[wikilink]] 참조 문서 로딩
- `skill_matcher.py`: trigger 키워드 매칭 (substring 0.9 + token Jaccard 0.8, threshold 0.5)

### Phase 2: 에이전트 파이프라인 통합
- `context.py`: user_skill, skill_context 필드 추가
- `api/agent.py`: 명시적 skill_path 해석 + 자동 매칭 + SSE skill_match 이벤트 발송
- `rag_agent.py`: _handle_skill_qa() — 스킬 지시사항 + 참조 문서 → LLM 답변 스트리밍

### Phase 3: Skill CRUD API
- `api/skill.py`: GET/POST/PUT/DELETE + match 엔드포인트
- `main.py`: UserSkillLoader/SkillMatcher 초기화, skill_api 라우터 등록

### Phase 4: 프론트엔드 사이드바
- `types/wiki.ts`: SkillMeta, SkillListResponse, SkillCreateRequest, GraphNode.node_type
- `lib/api/skills.ts`: fetchSkills, createSkill, deleteSkill, matchSkill
- `TreeNav.tsx`: SidebarSection에 "skills" 추가, SkillsSection (목록 + 인라인 생성 폼), SkillCard

### Phase 5: Copilot 통합
- `AICopilot.tsx`: ⚡ 스킬 피커 버튼, selectedSkill pill, 400ms 디바운스 자동 제안 배너, onSkillMatch thinking step
- `sseClient.ts`: skillPath 파라미터, onSkillMatch 콜백, skill_match 이벤트 디스패치

### Phase 6: 그래프 노드 구분
- `search.py`: path가 _skills/로 시작하면 node_type="skill"
- `DocumentGraph.tsx`: 스킬 노드 = 보라색(#a855f7) 다이아몬드 형태, 범례 추가

## 테스트 결과
- 68/68 기존 테스트 PASSED (회귀 없음)
- TypeScript: 타입 에러 없음

## 핵심 아키텍처 결정
- 스킬 = 위키 마크다운 파일 (`type: skill` frontmatter)
- 기존 위키 인프라 100% 재사용: 에디터, [[wikilink]], 백링크, 그래프
- LLM 호출 없는 키워드 매칭 (빠른 응답)
- 2가지 호출 방식: 수동 선택 (⚡ 피커) + 자동 제안 (trigger 매칭)
