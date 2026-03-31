# Step P2B-2: 메타데이터 기반 신뢰도 표시 — 완료 요약

## 완료 일시
2026-03-28

## 구현 내용 (5 tasks)

### P2B-2-1: DocumentMetadata status 필드
- Backend `schemas.py`: status field (draft/review/approved/deprecated)
- `local_fs.py`: frontmatter 파싱/직렬화에 status 반영

### P2B-2-2: ChromaDB 인덱서
- `wiki_indexer.py` `_metadata_to_chroma()`: status 포함

### P2B-2-3: SourceRef 확장
- `schemas.py` SourceRef: updated, updated_by, status 필드 추가
- `rag_agent.py` `_build_sources()`: 메타데이터에서 값 주입

### P2B-2-4: 소스 패널 UI
- AICopilot 소스 버튼: status별 색상/아이콘 (approved=녹색체크, deprecated=빨간X)
- 날짜 뱃지 (MM-DD), 상세 tooltip (관련도, 작성자, 수정일, status)

### P2B-2-5: MetadataTagBar status
- Status 드롭다운 (draft/review/approved/deprecated)
- Collapsed 뱃지: 색상별 status 표시
- frontmatterSync.ts: status 파싱/직렬화

## 테스트
- `tests/test_p2b2_status_field.py`: 10 tests 전체 PASS
- TypeScript 컴파일: 에러 없음
- P2B-1 + P2B-2 전체 18 tests 통과
