# Phase 3 — Frontend UI (필터 칩 + 우측 드로어 + 경량 DSL)

**일자**: 2026-04-17
**범위**: MS-11 ~ MS-15
**테스트**: 백엔드 8 신규 통과 (`tests/test_search_api_filters.py`) / 누적 85 통과. 프론트 TypeScript 빌드 0 에러.

## 목적

Phase 1(컴파일러/DSL)과 Phase 2(Indexer 필드) 위에 **UI를 얹는다**. 사용자가 명시적으로 필터를 쌓고, 조합하고, 제거할 수 있게 한다. AI Copilot은 건드리지 않음 (Phase 4 범위).

## 변경 파일

### 백엔드 — REST 엔드포인트에 필터 파이프라인 연결
Phase 1은 `WikiSearchSkill`(에이전트 경로)만 필터를 지원했다. `/api/search/quick`과 `/api/search/hybrid`(REST, 검색창이 호출)는 스킬을 거치지 않으므로 별도 와이어링이 필요.

- `backend/api/search.py`
  - `init(..., meta_index=None)` — `MetadataIndex` 주입
  - `_parse_filters(filters_raw: str | None)` — JSON 파싱 + 400 에러 핸들링 (한국어 메시지)
  - `_build_bm25_predicate(spec)` — `compile_to_bm25_predicate(spec)` + `meta_index.get_file_entry` + `_extract_path_depths(file_path)` 런타임 주입 (path_depth_* 폴더 필터가 그대로 작동)
  - `/quick`, `/hybrid` 모두 `filters: str | None = Query(None)` 받아서
    - 벡터: `compile_to_chroma_where(spec)`
    - BM25: `_build_bm25_predicate(spec)` (클로저)
- `backend/main.py` — `search_api.init(..., meta_index=meta_index)` 한 줄 추가

### 프론트엔드 — 필터 상태, DSL, 드로어, 칩, 컨텍스트 메뉴

- `frontend/src/lib/search/useSearchStore.ts` (MS-11)
  - `FilterSpec` / `TagFilter` 타입 export (DSL 파서와 드로어가 공유)
  - 상태: `filters: FilterSpec`, `filterSheetOpen: boolean`
  - 액션: `setFilter`, `removeFilter`, `clearFilters`, `mergeFilters`, `setFilterSheetOpen`, `openWithFilters(patch)` (팔레트도 같이 open)
  - `buildFiltersQuery(f)` — 빈 필드 정리 + JSON 인코딩 → `&filters=...`; `search`/`searchSemantic` 모두 여기 통과

- `frontend/src/lib/search/dslParser.ts` (MS-15) — 신규
  - `parseLightDSL(input: string) → { query, patch }`
  - 정규식 `/(\S+?):(\S+)/g` 로 prefix 토큰 추출
  - 지원: `folder:`, `author:`(`@` 자동 prefix), `tag:`, `-tag:`, `type:`, `status:`, `acl:`, `since:`/`mtime_from:`, `until:`/`mtime_to:`
  - 매칭 범위 역순 strip → 공백 정리. 백엔드 Boolean DSL(`filter_dsl.py`)과 다른 **경량** 파서 — AND/OR/괄호 없음. Boolean은 `FilterSheet`의 DSL 입력으로 별도 제공.

- `frontend/src/components/search/FilterSheet.tsx` (MS-13) — 신규
  - `CommandDialog` 안의 Dialog 중첩을 피하려 **fixed 포지션** 우측 드로어 (`absolute right-0 top-0 h-full w-[380px]`)
  - 로컬 `draft` 상태 + 명시적 "적용" 버튼 (undo 가능)
  - 섹션: 폴더 / 작성자 / 태그 include·exclude / 태그 모드 AND·OR / 문서 유형 / 상태 / 최근 수정 기간 프리셋(전체/7/30/90일 + 커스텀) / ACL / Boolean DSL
  - 각 chip list는 × 버튼 + Enter/Add. Boolean DSL은 textarea (줄바꿈 허용).
  - 푸터: `필터 초기화` + `적용 (N개)` (필터 N개 카운트)

- `frontend/src/components/search/SearchCommandPalette.tsx` (MS-12)
  - `buildActiveChips(filters, removeFilter, mergeFilters)` — 모든 필터 키를 emoji prefix chip으로 평탄화. 제외 태그(`-tag:`)는 `!🏷️ X` + `destructive` variant.
  - 칩 영역: CommandInput 아래, 모드 토글 위. `+ 필터` 버튼 → `setFilterSheetOpen(true)`. chip이 하나라도 있으면 "모두 지우기" 링크 노출.
  - `handleQueryChange(next)` — trailing space 감지 시 `parseLightDSL(next)` 호출 → patch 비지 않으면 `mergeFilters(patch)` + 잔여 텍스트로 재설정 (즉시 칩 승격 UX)
  - 빈 결과 + 활성 칩 → "필터를 제거하고 다시 시도" 버튼 노출
  - `<FilterSheet />`는 `<CommandDialog>` **밖에** 렌더 (fixed 레이어가 서로 간섭하지 않도록)

- `frontend/src/components/TreeNav.tsx` (MS-14)
  - `useSearchStore((s) => s.openWithFilters)` 연결
  - 컨텍스트 메뉴에 `이 폴더에서 검색` 항목 추가 (폴더·루트 아님 조건)
  - 클릭 시 `openWithFilters({ folders: [node.path] })` → 검색창 open + 폴더 칩 선적용

### 테스트
- `tests/test_search_api_filters.py` (신규, 8건)
  - `_parse_filters`: None / 빈 dict / 유효 / 400 (JSON 오류) / 400 (비-dict)
  - `_build_bm25_predicate`: None-when-empty / 폴더 매칭 / 작성자 매칭 (`_meta_index` 목 + `_extract_path_depths` 주입 동작 검증)

### 데이터 수정 (부수 효과)
- `wiki/제품/K-Pro-양산이관계획.md` — frontmatter `tags: [제품, K-Pro, 신제품, 양산이관, 2026]` → `[..., "2026"]`
  - YAML이 `2026`을 int로 파싱 → `DocumentMetadata.tags: list[str]` Pydantic 검증 실패 → 백그라운드 인덱서 중단
  - 따옴표로 감싸 str 강제. Phase 3 작업과 직접 관련 없으나 데모 블로커였음.

## 설계 결정 & 이유

1. **REST 필터 파이프라인 별도 와이어링** — `WikiSearchSkill`은 에이전트 전용 경로. 검색창 REST는 같은 `filter_compiler` + `MetadataIndex` 조합이지만 호출 지점이 다름. DRY 유혹을 피하고 직접 주입 (중간 레이어 추가는 과도한 추상화).
2. **FilterSheet를 fixed panel로 (Dialog 중첩 X)** — `CommandDialog` 내부에 또 Dialog를 띄우면 focus trap과 z-index가 꼬인다. `absolute right-0 top-0 h-full` + 자체 backdrop 이벤트로 해결.
3. **draft + Apply 패턴** — 드로어에서 여러 필드를 편집 중 실수로 닫아도 스토어는 건드리지 않음. "적용" 버튼만 `mergeFilters` 호출. UX 측면에서 undo 비용 낮춤.
4. **프론트 DSL은 의도적으로 얕게** — prefix 토큰만. Boolean은 FilterSheet의 DSL 입력으로 유도. 검색창에 AND/OR/괄호 섞으면 자동완성이 복잡해지고 오타 리스크 큼. "간단한 건 prefix, 복잡한 건 DSL 입력" 역할 분리.
5. **trailing space를 토큰 경계로** — 사용자가 `folder:ERP` 입력 중엔 그대로 두고, 공백 치는 순간 칩으로 승격. 타이핑 흐름을 끊지 않음.

## 알려진 제약

- **`authors=@이서연` BM25 필터 smoke test에서 0 결과** — 벡터 경로 `$eq` vs pipe-delimited 의미 차이일 수도 있고, 단순히 해당 작성자 문서가 적거나 쿼리 "관리"와 매칭되는 작성자 문서가 없을 수도 있음. 재인덱싱 후 재확인 필요 (Phase 4 QA 범위).
- **DSL 파서는 quoted value 미지원** — `tag:"인사 평가"` 같은 공백 포함 값은 FilterSheet에서만 입력 가능. 폴리시 관점에서 Phase 3 범위 밖.
- **Reindex 미실행** — Phase 2 CLI가 완성되어 있지만 운영 데이터로 돌리지 않음. `authors[]`/`doc_type`/`mtime_epoch` 반영 정도는 기존 write path(새 저장 이벤트)로만 누적.

## 검증 로그

```
$ python -m pytest tests/test_filter_compiler.py tests/test_filter_dsl.py \
    tests/test_wiki_search_filters.py tests/test_indexer_metadata_fields.py \
    tests/test_search_api_filters.py -q
.................................................................................
85 passed in 0.57s

$ cd frontend && npx tsc --noEmit
(exit 0, no output)
```

실 서버 curl smoke test (port 8001):
```
# 베이스라인
GET /api/search/hybrid?q=관리 → 8 results

# 폴더 필터
GET /api/search/hybrid?q=관리&filters={"folders":["제품"]} → 2 results (all under 제품/)

# 타입 필터
GET /api/search/hybrid?q=공정&filters={"types":["sop"]} → 5 results (all *-SOP.md)

# Boolean DSL
GET /api/search/hybrid?q=관리&filters={"boolean":"folder:제품 OR folder:공정"} → 5 results

# 오류 핸들링
GET /api/search/hybrid?q=관리&filters={invalid → 400 "filters JSON 파싱 실패"
```

## 다음 단계

Phase 4 — Agent 브릿지 + 프리셋 (MS-16 ~ MS-20):
1. AI Copilot 시스템 프롬프트에 `filters` 스키마 힌트 주입
2. SSE payload에 `applied_filters` → "검색창에서 계속" 버튼으로 핸드오프
3. localStorage 프리셋 저장/로드 (개인만, 팀 공유 X)
4. 빈 결과 UX — 필터 완화 제안 ("이 태그만 빼고 다시", "기간 확장")
5. 접근성 감사 (aria-label, focus trap, 키보드만 조작) + `demo_guide.md` 시나리오 확장

자세한 디자인은 `specs/2026-04-17-metadata-search-design.md` §Phase 4 참조.
