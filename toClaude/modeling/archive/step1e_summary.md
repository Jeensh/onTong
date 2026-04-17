# Step 1-E: Metadata Tagging Pipeline — 작업 요약

## 완료일: 2026-03-25

---

## 백엔드 (B1~B9)

### B1. schemas.py 수정
- `DocumentMetadata` 모델 추가 (domain, process, error_codes, tags, author, created)
- `MetadataSuggestion` 모델 추가 (confidence, reasoning 포함)
- `WikiFile`에 `metadata` (DocumentMetadata), `raw_content` (원본 포함) 필드 추가
- `tags`를 `computed_field` property로 변경 → `metadata.tags` 위임, 하위 호환 유지

### B2. local_fs.py Frontmatter 파싱
- `_parse_frontmatter()` 함수 추가: YAML frontmatter `---...---` 파싱
- `_to_wiki_file()`에서 frontmatter → `DocumentMetadata` 매핑
- frontmatter 없으면 `#hashtag` 폴백
- invalid YAML → 경고 로그 + 빈 metadata + 전체 content (graceful degradation)
- PyYAML (`yaml.safe_load`) 사용

### B3. wiki_indexer.py 메타데이터 확장
- `_metadata_to_chroma()` 정적 메서드 추가
- tags/error_codes → 파이프 구분자 형식 (`|tag1|tag2|`) → ChromaDB `$contains` 쿼리 지원
- 빈 필드는 `""` (None 아님)
- `index_file()`에서 기존 `file_path`, `heading` + 새 metadata 필드 모두 upsert

### B4. chroma.py query_with_filter
- `query_with_filter(query_text, n_results, where)` 메서드 추가
- `where=None` → 기존 query와 동일
- ChromaDB 미연결 또는 쿼리 실패 → 빈 결과 반환 (에러 아님)

### B5. rag_agent.py
- `execute()`에 `metadata_filter: dict | None` 파라미터 추가
- 필터 있으면 `query_with_filter()`, 없으면 기존 `query()` 호출

### B6. GET /api/metadata/tags
- `backend/api/metadata.py` 신규 생성
- 전체 wiki 파일 스캔 → 고유 domains, processes, error_codes, tags 반환
- `main.py`에 라우터 등록 완료

### B7. metadata_service.py (LLM Auto-Tag)
- `backend/application/metadata/metadata_service.py` 신규 생성
- `suggest_metadata(content, existing_tags)` → LLM 호출 → `MetadataSuggestion` 반환
- JSON 응답 파싱, markdown fence 제거, existing_tags 필터링
- LLM 실패 시 confidence=0 + 에러 메시지 반환

### B8. POST /api/metadata/suggest
- `metadata.py`에 엔드포인트 추가
- `SuggestRequest` (content, existing_tags) → `MetadataSuggestion` 응답

### B9. 하위 호환성 검증
- `WikiSearchService.build_tag_index()` → 새 `WikiFile.tags` property 정상 동작
- `build_search_index()` → tags 필드 정상 매핑

---

## 프론트엔드 (F1~F6)

### F1. MetadataTagBar
- `components/editors/metadata/MetadataTagBar.tsx`
- 에디터 상단에 표시, 열기/접기 토글
- `GET /api/metadata/tags`에서 옵션 목록 로드

### F2. TagInput
- `components/editors/metadata/TagInput.tsx`
- Badge 기반 태그 입력, 자동 완성 드롭다운
- Enter로 새 태그 생성, ✕로 제거, Backspace로 마지막 태그 삭제

### F3. DomainSelect
- `components/editors/metadata/DomainSelect.tsx`
- Domain/Process 선택을 위한 네이티브 select 컴포넌트
- MetadataTagBar에서 2개 인스턴스로 사용 (Domain, Process)

### F4. AutoTagButton
- `components/editors/metadata/AutoTagButton.tsx`
- ✨ Sparkles 아이콘 + 로딩 스피너
- 추천 결과 → 점선 테두리 Badge, 개별 수락(✓)/거절(✕) + "모두 수락"
- API 실패 시 Toast

### F5. frontmatterSync.ts
- `lib/markdown/frontmatterSync.ts`
- `serializeMetadataToFrontmatter()` → YAML 문자열 생성
- `stripFrontmatter()` → `---...---` 블록 제거
- `parseFrontmatter()` → 간단한 YAML 파서 (외부 라이브러리 없음)
- `mergeFrontmatterAndBody()` → frontmatter + body 결합
- `emptyMetadata()` → 기본값 객체

### F6. MarkdownEditor 통합
- `MarkdownEditor.tsx` 수정
- 열기: `raw_content`에서 `parseFrontmatter()` → `setMetadata()`
- 저장: `mergeFrontmatterAndBody(metadata, md)` → 백엔드에 전송
- MetadataTagBar 변경 시 dirty 표시

---

## 타입 변경
- `types/wiki.ts`: `DocumentMetadata`, `MetadataSuggestion`, `MetadataTagsResponse` 추가, `WikiFile`에 `raw_content`/`metadata` 필드 추가
- `types/workspace.ts`: 중복 `DocumentMetadata` 제거

---

## 주의사항
- Auto-Tag 기능은 LLM API 키가 설정되어 있어야 동작 (`LITELLM_MODEL`, `ANTHROPIC_API_KEY` 등)
- ChromaDB 미실행 시 metadata 인덱싱은 skip되지만 파일 저장/조회는 정상 동작
