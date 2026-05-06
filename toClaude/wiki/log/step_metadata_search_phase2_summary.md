# Phase 2 — Indexer 보강 (`authors[]`, `doc_type`, `mtime_epoch`)

**일자**: 2026-04-17
**범위**: MS-8 ~ MS-10
**테스트**: 12 신규 통과 (`tests/test_indexer_metadata_fields.py`) / 누적 77 통과

## 목적

Phase 1에서 구현한 `FilterSpec` 컴파일러가 **실제로 돌아가려면** Chroma 메타데이터와 `MetadataIndex` JSON 엔트리에 `authors[]`, `doc_type`, `mtime_epoch` 세 필드가 채워져 있어야 한다. Phase 2는 그 인덱싱 파이프라인을 뚫는 작업이다.

- Chroma는 스칼라만 저장 → `authors[]` 는 `|@a|@b|` pipe-delimited 문자열
- `MetadataIndex`(로컬 JSON)는 네이티브 타입 유지 → BM25 post-filter가 그대로 리스트/숫자를 먹을 수 있음
- `mtime_epoch`: frontmatter `updated` → `created` → filesystem `mtime` → 0.0 우선순위

## 변경 파일

### 스키마 / 스토리지
- `backend/core/schemas.py` — `DocumentMetadata`에 `doc_type: str`, `authors: list[str]` 추가
- `backend/infrastructure/storage/local_fs.py` — frontmatter 파싱(`type` alias 허용) + 직렬화에 두 필드 추가

### 인덱서
- `backend/application/wiki/wiki_indexer.py`
  - `compute_effective_authors(meta)` — 명시 `authors[]` 우선, 없으면 `[created_by, updated_by]` 중복 제거 및 공백 제외
  - `compute_mtime_epoch(meta, file_abs_path)` — ISO 파싱 실패/미존재 시 파일시스템 fallback
  - `_metadata_to_chroma` — 두 헬퍼를 호출해 `authors`(파이프 문자열), `doc_type`, `mtime_epoch` 세팅
- `backend/application/metadata/metadata_index.py`
  - `on_file_saved(..., authors=None, doc_type="", mtime_epoch=0.0)` — 저장 시 확장 필드
  - `rebuild(extended=[{...}])` — 확장 포맷 지원 (기존 `files=` 포맷은 유지, 하위 호환)

### 저장 경로
- `backend/application/wiki/wiki_service.py:136` — 메인 저장 호출이 `compute_effective_authors(m)`, `m.doc_type`, `compute_mtime_epoch(m)`를 명시적으로 전달

### CLI
- `backend/cli/reindex_metadata.py` — 100K 규모 마이그레이션
  - `--force` : 해시 캐시 무시하고 전체 재인덱싱
  - `--dry-run` : 상위 20개 샘플 + 계산된 필드 출력
  - `--batch N` : 진행률 로깅 주기 (기본 500)
  - 동작 순서: `LocalFSAdapter.list_tree` → `MetadataIndex.rebuild(extended=...)` → `WikiIndexer.index_file(force=...)` 루프

### 테스트
- `tests/test_indexer_metadata_fields.py` — 12 테스트
  - `compute_effective_authors` 4종: 명시 리스트 우선 / fallback / dedup / 빈 문자열 필터
  - `compute_mtime_epoch` 3종: ISO updated / fallback to created / zero when missing
  - `_metadata_to_chroma` 2종: 신규 필드 포함 + pipe-delimited / fallback authors
  - `MetadataIndex` 2종: `on_file_saved` 확장 / `rebuild(extended=...)`
  - 통합: `FilterSpec` → predicate → `meta_index` 엔트리(+ path_depth 주입) 매칭 1종

## 설계 결정 & 이유

1. **`authors[]`를 Chroma에서 pipe-delimited 문자열로 저장** — 기존 `tags`와 동일한 관례. Chroma의 `$contains` 쿼리 호환. 리스트 기반 정확 매칭은 BM25 post-filter(`meta_index`)에서 해결.
2. **BM25 closure가 `path_depth_*`를 런타임 주입** — `meta_index` 엔트리는 경로 분해 필드를 저장하지 않음. `wiki_search.py`의 `bm25_filter_fn`이 `_extract_path_depths(file_path)`를 호출해 predicate 평가 직전에 dict에 주입. 인덱스를 비대하게 만들지 않으면서 폴더 필터가 작동.
3. **`mtime_epoch`: frontmatter 우선, 파일시스템은 fallback** — 제품 콘텐츠는 frontmatter가 소스 오브 트루스. 파일 복사/재편성 시 mtime 섞이는 이슈 회피.
4. **`wiki_service.py`의 부가 경로(lineage sync)는 기본값 유지** — 메인 저장 경로만 새 필드 전달. 리니지 싱크는 사용자 편집 이벤트가 아니라 자동 파생이라, 굳이 재계산 비용을 들이지 않음.

## 알려진 제약

- **Chroma `where`만으로는 리스트 필드 정확 매칭 불가** — `authors`, `tags`, `acl` 기반 필터는 pipe-delimited `$contains`로 근사하되, 진짜 정확도는 BM25 post-filter 경로에서 나온다. 벡터 단독 쿼리 시 false positive 가능성.
- **Reindex CLI는 아직 실제 데이터로 돌리지 않음** — `--dry-run`으로 구조 검증까지만. 운영 적용은 사용자가 명시적으로 실행할 것 (Phase 2 범위 밖).

## 검증 로그

```
$ source venv/bin/activate && python -m pytest tests/test_indexer_metadata_fields.py -v
============================= 12 passed in 0.21s ==============================

$ python -m pytest tests/test_filter_compiler.py tests/test_filter_dsl.py \
    tests/test_wiki_search_filters.py tests/test_indexer_metadata_fields.py -v
============================== 77 passed in 0.36s ==============================
```

## 다음 단계

Phase 3 — Frontend UI (MS-11 ~ MS-15):
1. `useSearchStore` filters 상태 + 액션
2. `SearchCommandPalette` 칩 영역
3. `FilterSheet` 우측 드로어
4. `TreeNav` 우클릭 "이 폴더에서 검색"
5. 프론트 DSL 경량 파서

자세한 디자인은 `specs/2026-04-17-metadata-search-design.md` §Phase 3 참조.
