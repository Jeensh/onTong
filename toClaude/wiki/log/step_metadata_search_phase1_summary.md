# Phase 1 — Metadata Search Backend 기반 완료 (2026-04-17)

## 목표
문서 메타데이터·경로·폴더를 효과적으로 검색 조건으로 쓰도록 FilterSpec 기반 파이프라인 + Boolean DSL 도입.

## 결과
65/65 테스트 통과. `WikiSearchSkill`이 `filters` 객체 파라미터를 받아 Chroma `where`와 BM25 post-filter를 동시에 적용.

## 산출물

### 신규 파일
- `backend/application/agent/filter_compiler.py`
  - `compile_to_chroma_where(spec)` — FilterSpec(dict) → Chroma `where` clause
  - `compile_to_bm25_predicate(spec)` — FilterSpec(dict) → `(meta) -> bool` predicate
  - `eval_where(clause, meta)` — 공용 where 평가기 (BM25 post-filter, fallback)
  - 지원 필드: `path`, `folders`, `tags{include/exclude/mode}`, `authors`, `types`, `mtime_from/to`, `statuses`, `acl`, `boolean`
- `backend/application/agent/filter_dsl.py`
  - `parse_dsl(text)` — Boolean DSL → where clause
  - Recursive descent 파서 (expr → or → and → term → atom)
  - 필드 atom: `folder:`, `tag:`, `author:`, `type:`, `status:`, `acl:`, `path:`, `mtime:`
  - 연산자: `AND`, `OR`, `NOT`/`!`, 괄호, `mtime:>=…` 등 비교 접두사
  - `NOT`은 De Morgan's law + 연산자 flip (`$eq↔$ne`, `$in↔$nin`, `$gt↔$lte` 등)
- `tests/test_filter_compiler.py` (35 케이스)
- `tests/test_filter_dsl.py` (24 케이스)
- `tests/test_wiki_search_filters.py` (6 통합 케이스)

### 수정된 파일
- `backend/infrastructure/search/bm25.py`
  - `BM25Index.search(..., filter_predicate: Callable[[BM25Document], bool] | None = None)`
  - 스코어링 후 `n_results` 슬라이싱 전에 predicate 통과 문서만 수집
- `backend/application/agent/skills/wiki_search.py`
  - `execute(..., filters: dict | None = None)` 시그니처 확장
  - `compile_to_chroma_where(filters)`를 기존 `metadata_filter`와 `$and` 머지
  - BM25 호출 시 `meta_index.get_file_entry`로 메타 조회하는 closure를 `filter_predicate`로 전달
  - 0-result fallback 재귀 호출에도 `filters` 전파
  - `to_tool_schema()`에 `filters` 객체 스키마 추가 (folders/tags/authors/types/mtime_from/mtime_to/statuses/acl/boolean)

## 아키텍처 결정
- **Pre-filter (Chroma where) + Post-filter (BM25 predicate) 병행.** 벡터 인덱스는 메타 필터를 지원하므로 pre-filter가 효율적. BM25는 기존 corpus 스냅샷에 predicate를 적용하는 방식으로 reindex 없이 연동.
- **FilterSpec은 dict 기반 (TypedDict 선언 유예).** tool_call 스키마가 JSONSchema로 직접 노출되므로 TypedDict는 선택적. 필드가 안정된 뒤 추가하면 됨.
- **Boolean DSL이 structured 필드보다 우선.** `spec["boolean"]`이 있으면 다른 필드는 무시. 사용자가 쓴 표현식이 가장 명시적이라는 원칙.

## 검증
```
source venv/bin/activate
python -m pytest tests/test_filter_compiler.py tests/test_filter_dsl.py tests/test_wiki_search_filters.py -v
# 65 passed in 0.36s
```

테스트 커버리지:
- Empty spec, invalid date 예외
- path glob → path_depth_* 분해
- folders OR, nested folder AND
- tags include/exclude, AND/OR mode
- authors/types/statuses/acl $in
- mtime range, ISO → epoch 변환
- DSL atoms, 괄호, implicit AND, case-insensitive 키워드
- DSL NOT De Morgan's law 전개
- WikiSearchSkill filters → Chroma where 병합
- DSL boolean end-to-end
- filters + metadata_filter 동시 적용
- BM25 predicate closure
- ACL user_scope와 filters 동시 적용

## 기존 테스트 상태
- `test_ag23_skill_feedback.py::test_wiki_search_deprecated_feedback` 1건 실패 — 피드백 문자열 포맷이 basename만 쓰도록 이전 커밋에서 변경되었는데 테스트가 stale. 이번 작업과 무관.

## 다음 단계
- Phase 2: `WikiIndexer`에 `authors[]`, `doc_type`, `mtime_epoch` 메타 필드 채우고 100K 규모 재인덱싱 검증
- Phase 3: 프론트엔드 FilterSheet 드로어 + 검색 팔레트 칩 영역
- Phase 4: Agent system prompt에 filter 힌트 + `applied_filters` SSE payload + 프리셋 저장
