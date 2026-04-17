# Step 4: 샘플 데이터 마이그레이션 + 통합 테스트 — 완료 요약

## 완료 일시
2026-03-26 (세션 4)

## 완료 태스크

### 4-1~4-3: Frontmatter 마이그레이션
- `getting-started.md`: author, created, tags (인사/직원정보/포스코) → YAML frontmatter
- `order-processing-rules.md`: domain(SCM), process(주문처리), error_codes(DG320), tags → YAML frontmatter
- `kv-cache-troubleshoot.md`: domain(LOGISTICS), process(후판공정계획), tags → YAML frontmatter
- 모든 wiki 파일에 YAML frontmatter 적용 완료

### 4-4: ChromaDB Metadata 검증
- `POST /api/wiki/reindex` → 10 chunks 인덱싱 완료
- ChromaDB에 domain, process, tags, error_codes 파이프 구분자로 저장 확인
- `GET /api/metadata/tags` → domains(2), processes(2), error_codes(1), tags(14) 반환 확인

### 4-5: E2E — TreeNav → 탭 → MD → AI Copilot
- TreeNav 파일 클릭 → 탭 생성 + 에디터 로드 ✅
- MetadataTagBar 표시 (Domain/Process/Tags) ✅
- AI Copilot "주문 처리 규칙 알려줘" → SSE 스트리밍 답변 ✅
- 출처 표시 (order-processing-rules.md, relevance 0.83) ✅
- 출처 클릭 → 해당 파일 탭 열림 ✅
- 활성 파일 사이드바 강조 ✅

### 4-6: E2E — Auto-Tag → Hybrid Search
- Auto-Tag 버튼 → LLM 추천 태그 점선 Badge 표시 ✅
- "모두 수락" → 실선 Badge 전환 ✅
- Ctrl+S 저장 → frontmatter에 새 태그 반영 (판매/생산조정/팀원 추가) ✅
- Reindex 후 RAG 검색 정상 동작 확인 ✅

### 4-7: E2E — Multi-Format 뷰어
- xlsx 파일 클릭 → 스프레드시트 뷰어 열림 (다수 시트 탭 표시) ✅
- 이미지 파일 클릭 → 이미지 뷰어 열림 (줌 −/+/1:1 버튼) ✅
- MetadataTagBar는 .md 파일에만 표시 (정상) ✅

### 4-8: E2E — 클립보드 기능
- 이미지 업로드 API (`POST /api/files/upload/image`) → assets/ 저장 확인 ✅
- 클립보드 붙여넣기는 headless 브라우저 한계로 API 레벨 검증

## 미완료/보류
- PPT 뷰어 (1D-5): Phase 1.5 보류
- PDF 뷰어 (1D-6): Phase 1.5 보류
- DG320 쿼리 → DEBUG_TRACE 에이전트 라우팅 (Phase 2 기능, 현재 placeholder 응답)

## Phase 1 전체 상태
**Phase 1 모든 P1 태스크 완료!** Step 0 ~ 1-F + Step 4 통합 테스트 통과.
