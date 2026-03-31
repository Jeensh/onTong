# Step P2B-5: 문서 계보(Lineage) 시스템 — Summary

## 완료 일자
2026-03-28

## 구현 내용

### P2B-5-1: DocumentMetadata lineage 필드
- `schemas.py`: `supersedes`, `superseded_by` (str), `related` (list[str]) 추가
- `local_fs.py`: frontmatter 파싱/직렬화 — lineage 필드 처리, 빈 값은 직렬화 생략
- `frontmatterSync.ts`: 프론트엔드 파서/시리얼라이저에도 동일 필드 추가

### P2B-5-2: RAG 검색 시 superseded 문서 패널티
- `rag_agent.py`: step 3.5 — deprecated/superseded 문서에 +0.3 distance 패널티
- `_build_context_with_metadata()`: "⚠️ 폐기됨" 경고 + superseded_by 안내 삽입

### P2B-5-3: Lineage API
- `api/wiki.py`: `GET /api/wiki/lineage/{path}` — supersedes/superseded_by/related를 파일 메타데이터로 해석하여 title/status/updated 포함 반환

### P2B-5-4: 프론트엔드 Lineage 위젯
- `LineageWidget.tsx`: 에디터 상단에 조건부 렌더링
  - superseded_by → amber 경고 ("이 문서는 폐기되었습니다. 새 버전: ...")
  - supersedes → 녹색 링크 ("이전 버전: ...")
  - related → 관련 문서 링크 목록
- `MarkdownEditor.tsx`: MetadataTagBar 아래에 LineageWidget 배치

### P2B-5-5: 자동 lineage 제안
- `api/conflict.py`: `POST /deprecate?superseded_by=` — bidirectional lineage 설정
  - deprecated 문서: `status=deprecated`, `superseded_by=newer_path`
  - 최신 문서: `supersedes=deprecated_path`
- `DiffViewer.tsx`: "A가 최신"/"B가 최신" 버튼이 deprecate API에 superseded_by 전달

## 테스트
- `tests/test_p2b5_lineage.py`: 10 tests ALL PASSED
  - TestLineageFields: 기본값, 설정값 검증
  - TestLineageFrontmatter: 파싱, 직렬화, 빈 값 생략, roundtrip
  - TestSupersededPenalty: deprecated 문서 패널티 확인

## Phase 2-B 전체 완료
- P2B-1: RAG 충돌 감지 프롬프트 (4 tasks) ✅
- P2B-2: 메타데이터 신뢰도 표시 (5 tasks) ✅
- P2B-3: 중복/충돌 감지 대시보드 (5 tasks) ✅
- P2B-4: 인라인 비교 뷰 (5 tasks) ✅
- P2B-5: 문서 계보 시스템 (5 tasks) ✅
- **총 24 tasks 완료**
