# FE 고급 설정 UI — Step Summary

## 완료 태스크 (SA-1 ~ SA-6)

### SA-1: SkillContext TypeScript 타입
- `frontend/src/types/wiki.ts`에 `SkillContext` 인터페이스 추가

### SA-2: ReferencedDocsPicker 컴포넌트
- 신규: `frontend/src/components/skills/ReferencedDocsPicker.tsx`
- `/api/search/quick` 기반 문서 검색, Badge 표시, X 삭제

### SA-3: SkillCreateDialog 모달
- 신규: `frontend/src/components/skills/SkillCreateDialog.tsx`
- 기본 필드 + 접이식 "고급 설정 (6-Layer)" 섹션
- 6개 textarea: 역할/지시사항/워크플로우/체크리스트/출력형식/제한사항
- ReferencedDocsPicker 통합

### SA-4: TreeNav.tsx 통합
- 인라인 생성 버튼 옆에 ⚙️ 아이콘 추가 → 모달 오픈
- SkillCreateDialog 렌더링

### SA-5: Context API 엔드포인트
- `backend/api/skill.py`: `GET /api/skills/{path}/context` → SkillContext 반환
- catch-all `/{path:path}` 위에 배치

### SA-6: 스킬 복제 6-Layer 복사
- `frontend/src/lib/api/skills.ts`: `fetchSkillContext()` 추가
- `handleDuplicate`: context API로 6-layer 조회 → createSkill에 전달

## 검증 결과
- FE 빌드: ✅ 성공
- BE 테스트: ✅ 68/68 통과
