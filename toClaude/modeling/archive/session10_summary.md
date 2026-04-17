# 세션 10 요약 (2026-03-29)

## 완료 작업

### P2B-6: RAG deprecated 문서 필터링 (3 tasks)
- ChromaDB where 필터 (`status != deprecated`) + Post-RRF BM25 필터
- superseded_by 체인 해결 (multi-hop, 순환참조 방지)
- +0.3 패널티 로직 → 완전 필터링으로 대체
- 소스 패널에서 deprecated 완전 제외

### P2B-7: 충돌 대시보드 해결 상태 (3 tasks)
- `is_pair_resolved()`: superseded_by/supersedes 양방향 lineage 판정
- API `filter` 파라미터 (unresolved/resolved/all)
- 프론트엔드 3탭 (미해결/해결됨/전체) + 해결됨 뱃지

### 메타데이터 동기화 버그 수정
- **근본 원인**: `_metadata_to_chroma()`에서 `superseded_by`/`supersedes` 필드 누락
- **구조적 수정**: 수동 필드 나열 → `DocumentMetadata.model_fields` 자동 순회 방식 전환
- **재발 방지**: 가드 테스트 3개 (필드 완전성, pipe-delimited 직렬화, 빈 리스트)
- deprecate API에 force reindex 추가

### 기타 버그 수정 (세션 9~10)
- 증분 인덱싱 해시: `content` → `raw_content`
- conflict_service numpy array 비교
- deprecate API 500 에러
- DiffViewer React key 경고
- CONFLICT_CHECK 프롬프트 강화
- 재고관리 샘플 데이터 lineage 누락

## 테스트 결과
- `test_p2b6_deprecated_filter.py`: 10/10 PASSED
- `test_p2b7_dashboard_resolved.py`: 7/7 PASSED

## Phase 2-B 최종 상태
- **30/30 tasks 완료** (P2B-1 ~ P2B-7)
- 다음 Phase 방향 미정 — 사용자 논의 필요
