# Step P2B-6 & P2B-7 Summary

## P2B-6: RAG deprecated 문서 필터링 + 최신 문서 자동 대체

### 변경 내역
1. **ChromaDB where 필터** (`_build_status_filter`): `{"status": {"$ne": "deprecated"}}` — 벡터 검색 단계에서 deprecated 문서 제외
2. **Post-RRF 필터**: BM25를 통해 유입된 deprecated 문서를 RRF 병합 후 제거
3. **Superseded_by 체인 해결** (`_resolve_superseded_chain`): v1→v2→v3 체인을 따라 최신 버전 추적, max_depth로 순환참조 방지
4. **최신 문서 자동 대체** (`_replace_deprecated_with_latest`): deprecated 문서가 검색에 포함될 경우 최신 버전으로 자동 교체
5. **패널티 로직 제거**: 기존 +0.3 distance 패널티 → 완전한 필터링으로 대체
6. **소스 패널 제외**: `_build_sources`에서 deprecated 문서 skip

### 수정 파일
- `backend/application/agent/rag_agent.py` — 6개 메서드 추가/수정

### 테스트
- `tests/test_p2b6_deprecated_filter.py` — 7 tests, ALL PASSED

---

## P2B-7: 충돌 대시보드 해결 상태 관리

### 변경 내역
1. **`is_pair_resolved()` 함수**: superseded_by/supersedes 양방향 lineage 확인으로 해결 여부 자동 판정
2. **`DuplicatePair.resolved` 필드**: 기본값 False, 유사도 스캔 시 자동 설정
3. **API `filter` 파라미터**: `GET /api/conflict/duplicates?filter=unresolved|resolved|all`
4. **프론트엔드 탭 필터**: 미해결 / 해결됨 / 전체 3개 탭, 기본값 "미해결"
5. **해결됨 뱃지**: 해결된 쌍에 초록색 체크 아이콘 + "해결됨" 텍스트

### 수정 파일
- `backend/application/conflict/conflict_service.py` — `is_pair_resolved()` 추가, `DuplicatePair` 모델 확장
- `backend/api/conflict.py` — `filter` 쿼리 파라미터 추가
- `frontend/src/components/editors/ConflictDashboard.tsx` — 탭 UI, 뱃지, API 연동

### 테스트
- `tests/test_p2b7_dashboard_resolved.py` — 7 tests, ALL PASSED

---

## Phase 2-B 완료 상태
- P2B-1~P2B-7 전체 30 tasks 완료
