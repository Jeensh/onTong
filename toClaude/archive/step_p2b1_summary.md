# Step P2B-1: RAG 답변 충돌 감지 프롬프트 — 완료 요약

## 완료 일시
2026-03-28

## 구현 내용 (4 tasks)

### P2B-1-1: `_build_context_with_metadata()`
- `rag_agent.py`에 static method 추가
- 각 문서 청크에 `[출처]`, `[작성자 | 최종수정 | 도메인 | 관련도]` 헤더 삽입
- updated_by → created_by fallback 체인
- 같은 파일의 다른 섹션 표시 (`[참고: 같은 파일의 다른 섹션]`)
- 기존 `"\n\n---\n\n".join(relevant_docs)` 대체

### P2B-1-2: `FINAL_ANSWER_SYSTEM_PROMPT` 충돌 감지 규칙
- "문서 충돌 감지 규칙" 섹션 추가
- 모순 감지 시 ⚠️ 경고 형식 지정 (문서명, 수정일, 차이 내용)
- 최신 문서 우선 + 담당자 확인 권고

### P2B-1-3: `COGNITIVE_REFLECT_PROMPT` 충돌 확인
- self_critique에 `CONFLICT_CHECK` 품질 게이트 추가
- JSON 응답에 `has_conflict` (boolean), `conflict_details` (string) 필드 추가
- 인지 파이프라인이 문서 간 모순을 자동 감지

### P2B-1-4: ConflictWarningEvent SSE + 프론트엔드
- **Backend**: `ConflictWarningEvent` Pydantic 스키마 (details + conflicting_docs)
- **Backend**: cognitive reflection에서 `has_conflict=true` 시 SSE `conflict_warning` 이벤트 방출
- **Frontend**: `agent.ts`에 타입 추가, `sseClient.ts`에 콜백/dispatch 추가
- **Frontend**: `AICopilot.tsx`에 amber 색상 경고 배너 (문서 클릭 가능)

## 테스트
- `tests/test_p2b1_conflict_detection.py`: 8 tests 전체 PASS
  - 메타데이터 헤더 생성 (4 tests)
  - 스키마 검증 (2 tests)
  - 프롬프트 내용 검증 (2 tests)
- TypeScript 컴파일: 에러 없음

## 변경 파일
- `backend/application/agent/rag_agent.py` — 메서드/프롬프트 추가
- `backend/core/schemas.py` — ConflictWarningEvent
- `frontend/src/types/agent.ts` — ConflictWarningEvent type
- `frontend/src/lib/api/sseClient.ts` — conflict_warning handler
- `frontend/src/components/AICopilot.tsx` — ConflictWarning UI
- `tests/test_p2b1_conflict_detection.py` — 신규 테스트
