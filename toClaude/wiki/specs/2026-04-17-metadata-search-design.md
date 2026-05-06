# Wiki 메타데이터/경로/폴더 검색 조건화 — 설계 스펙

> 작성: 2026-04-17 (위키 세션)
> 상태: Draft — 사용자 승인 대기
> 담당: Section 1 (Wiki)

## 1. 배경 / 현재 상태

### 이미 구현된 것 (재사용 가능)
- **Backend Skill** (`backend/application/agent/skills/wiki_search.py`): hybrid (벡터 + BM25 + RRF) 완성, `metadata_filter`, `path_preference`, `user_scope` 파라미터 이미 존재
- **Chroma where-clause**: `chroma.query_with_filter(where=...)` 사용 중
- **ACL scope**: `backend/core/auth/scope.py` + `acl_store.check_permission`로 user-scoping 필터 이미 주입
- **자연어 추출기**: `backend/application/agent/filter_extractor.py` — 쿼리에서 domain/process 키워드 뽑아 metadata filter 생성
- **Query cache**: filter 포함 캐싱 (`query_cache.get(query, effective_filter)`)

### 비어있는 것
- `wiki_search.to_tool_schema()`가 `query`, `n_results`만 노출 → LLM이 필터 명시적으로 호출 못 함
- `SearchCommandPalette.tsx`: local/semantic 토글만, 필터 UI 없음
- BM25 인덱스에 메타데이터 필터 미지원 (현재 full-text만)
- 프리셋/저장된 필터 개념 없음
- 폴더 트리에서 "이 폴더에서 검색" 컨텍스트 액션 없음

---

## 2. 목표 / 비목표

### 목표
- 모든 메타데이터 필터 타입 지원 (path/folder/tag/author/type/mtime/status/acl + Boolean)
- 두 표면 모두 지원: (A) 검색창 UI 명시적 필터, (B) AI Copilot 자연어
- 100K+ 문서 가정, **품질 우선 / 동률 시 속도**
- 확장·유지보수 용이한 구조 (FilterSpec 단일 모델, compile 레이어 분리)

### 비목표
- 전문 검색 엔진 (Elastic/Meilisearch) 교체 — 현 Chroma+BM25 유지
- 실시간 수정 페이지 즉시 반영 (이미 indexer가 처리)
- 팀 프리셋 공유 (Phase 1~3은 개인 프리셋만)

---

## 3. 필터 Taxonomy

| 필터 | 타입 | 저장 필드 (Chroma metadata) | 예시 |
|------|------|-----------------------------|------|
| **path** | glob | `path` (전체 경로) | `wiki/ERP/**` |
| **folders** | 다중 선택 | `path_depth_1`, `path_depth_2` | `[ERP, MES]` |
| **tags** | include/exclude + AND/OR | `tags[]` (array) | include=`[재고, 주문]` op=AND |
| **authors** | 다중 | `authors[]` | `[@동해, @재인]` |
| **types** | 다중 | `doc_type` | `[sop, spec, decision]` |
| **mtime** | from/to | `mtime_epoch` (numeric) | from=`2026-01-01` |
| **statuses** | 다중 (기본: non-deprecated) | `status` | `[active, review]` |
| **acl** | 다중 (항상 user scope 교집합) | `acl_read[]` | `[public, team:mes]` |
| **Boolean 조합** | DSL 문자열 | — | `(tag:재고 OR tag:주문) AND !author:@민수` |

---

## 4. 백엔드 아키텍처

### 결정: **메타데이터 선필터링 + 하이브리드 랭킹 + 후처리 리랭크**

#### 근거
- 100K에서 selective 필터(예: 특정 폴더 1,500건)로 pre-filter 하면 벡터 검색 질·속도 모두 이득
- Chroma `where` 절은 B-tree 인덱스로 상수 시간 근접 — RRF 전 적용 자연스러움
- Chroma는 `$and/$or/$in/$gte/$lte` 지원 → Boolean DSL을 compile 가능
- 품질 우선: pre-filter 결과가 0이면 **필터 완화 fallback** (기존 코드에 이미 존재)

#### 데이터 플로우
```
User Query + FilterSpec (UI 또는 LLM)
        ↓
  compile_filter_to_where(FilterSpec) → Chroma where dict
        ↓  (merge with ACL user_scope)
  Chroma.query_with_filter(query, where=...)   ┐
  BM25.search(query, filter=...)               │  병렬
                                                ┘
        ↓
  RRF (Reciprocal Rank Fusion)
        ↓
  Post-filter: deprecated 제거, ACL 재확인
        ↓
  Cross-encoder rerank (top-k)
        ↓
  Response { documents, metadatas, search_mode, applied_filters }
```

### 4.1 FilterSpec 모델

`backend/core/schemas.py`에 추가:
```python
class TagFilter(TypedDict, total=False):
    include: list[str]
    exclude: list[str]
    mode: Literal["AND", "OR"]      # include 연산자, 기본 OR

class FilterSpec(TypedDict, total=False):
    path: str                        # glob, 예: "wiki/ERP/**"
    folders: list[str]               # ["ERP", "MES/설비"]
    tags: TagFilter
    authors: list[str]
    types: list[str]
    mtime_from: str                  # ISO-8601 date
    mtime_to: str
    statuses: list[str]
    acl: list[str]
    boolean: str                     # DSL, 있으면 위 필드보다 우선
```

### 4.2 Compiler

`backend/application/agent/filter_compiler.py` (신규):
```python
def compile_filter_to_where(spec: FilterSpec) -> dict | None:
    """FilterSpec → Chroma where dict"""

def compile_filter_to_bm25(spec: FilterSpec) -> Callable[[dict], bool]:
    """FilterSpec → BM25 post-filter predicate (metadata dict 검사)"""
```

### 4.3 DSL Parser (파워유저 전용)

`backend/application/agent/filter_dsl.py` (신규):
- grammar: `(atom | group) (AND|OR atom)*`
- atom: `[!]field:value` (field ∈ {path, folder, tag, author, type, mtime, status, acl})
- `"(tag:재고 OR tag:주문) AND !author:@민수"` → AST → `FilterSpec`

### 4.4 Tool Schema 확장

`WikiSearchSkill.to_tool_schema()` 에:
```json
{
  "parameters": {
    "properties": {
      "query": { "type": "string" },
      "n_results": { "type": "integer", "default": 8 },
      "filters": {
        "type": "object",
        "properties": {
          "path": { "type": "string", "description": "glob, e.g. wiki/ERP/**" },
          "folders": { "type": "array", "items": {"type": "string"} },
          "tags": {
            "type": "object",
            "properties": {
              "include": { "type": "array", "items": {"type": "string"} },
              "exclude": { "type": "array", "items": {"type": "string"} },
              "mode": { "type": "string", "enum": ["AND", "OR"] }
            }
          },
          "authors": { "type": "array", "items": {"type": "string"} },
          "types": { "type": "array", "items": {"type": "string"} },
          "mtime_from": { "type": "string", "description": "ISO date" },
          "mtime_to": { "type": "string" },
          "statuses": { "type": "array", "items": {"type": "string"} }
        }
      }
    },
    "required": ["query"]
  }
}
```

### 4.5 인덱스 마이그레이션

ChromaDB metadata에 필터링 가능한 평면 필드 보장 (현재 부분만 있음):
| 필드 | 현재 | 작업 |
|------|------|------|
| `path` | ✅ 있음 | — |
| `path_depth_1` (예: "ERP") | ✅ 있음 | — |
| `path_depth_2` | 일부 | 재인덱싱 확인 |
| `tags[]` | ✅ 있음 | — |
| `authors[]` | ❌ 없음 (frontmatter author 단일) | Wiki indexer에 authors array 추가 |
| `doc_type` | ❌ 없음 | frontmatter `type` 필드 반영 |
| `mtime_epoch` (numeric) | ❌ 없음 (ISO string만) | numeric 변환 추가 |
| `status` | ✅ 있음 | — |
| `acl_read[]` | ✅ 있음 | — |

→ **마이그레이션 스크립트**: `backend/cli/reindex_metadata.py` 기존 `reindex_wiki`에 이 필드들 보완

---

## 5. UI/UX 설계

### 5.1 메인 검색: 커맨드바 + 칩 + 발견형 파셋

#### 와이어프레임 (데스크탑)

```
┌─ SearchCommandPalette (Ctrl+K) ─────────────────────────────┐
│                                                              │
│  [📁 ERP] [👤 @동해] [🏷️ 재고] [📅 최근30일]  [+ 필터]    │ ← 칩 영역
│                                                              │
│  ┌────────────────────────────────────────────┐              │
│  │ 🔍  재고 동기화 주기                        │ ← 입력창    │
│  └────────────────────────────────────────────┘              │
│                                                              │
│  ◉ 하이브리드  ○ 키워드  ○ 벡터          저장된 필터 ▾     │
│  ─────────────────────────────────────────────────           │
│                                                              │
│  📄 마스터데이터-관리-지침.md       · wiki/ERP/   2일 전   │
│      ... 재고 데이터 동기화는 매일 배치로 ...                │
│      [@동해] [재고] [ERP] [sop]                             │
│                                                              │
│  📄 모듈별-권한-설정.md             · wiki/ERP/   3주 전   │
│      ... 재고 조회 권한은 ...                                │
│      [@재인] [권한] [ERP]                                   │
│                                                              │
│  ─────────────────────────────────────────────────           │
│  💾 필터 저장    ·    📎 이 검색 공유    ·    2건 매칭     │
└──────────────────────────────────────────────────────────────┘
```

#### 필터 시트 (우측 슬라이드인 드로어, `+ 필터` 또는 `Cmd+F`)

```
┌─ 고급 필터 ──────────────────────┐
│                              [✕] │
├──────────────────────────────────┤
│                                  │
│ 📁 폴더                          │
│   ▼ wiki                         │
│     ▶ ERP         (48건)        │
│        ☑ 마스터데이터  (12)     │
│        ☐ 권한          (6)      │
│     ☑ MES         (37건)        │
│     ☐ SCM         (22건)        │
│   [폴더 초기화]                  │
│                                  │
│ 🏷️ 태그                          │
│   포함 (● AND  ○ OR):            │
│     [재고 ×] [주문 ×] [+ 추가]  │
│   제외:                          │
│     [draft ×] [+ 추가]          │
│                                  │
│ 👤 작성자                        │
│   ☑ @동해  ☐ @재인  ☐ @민수    │
│   ☐ 전체 표시 (47명)            │
│                                  │
│ 📄 문서 유형                     │
│   ☑ sop    ☑ spec   ☐ decision  │
│   ☐ postmortem  ☐ meeting       │
│                                  │
│ 📅 수정일                        │
│   ○ 전체                         │
│   ● 최근 30일                    │
│   ○ 최근 7일                     │
│   ○ 사용자 지정: [___]~[___]   │
│                                  │
│ 🚦 상태                          │
│   ☑ active   ☐ review           │
│   ☐ deprecated (기본 제외)      │
│                                  │
│ 🔐 ACL (읽기 가능 범위)          │
│   ● 내가 볼 수 있는 전체 (기본) │
│   ○ 특정 스코프 지정             │
│                                  │
├──────────────────────────────────┤
│ [필터 초기화]        [✓ 적용]    │
└──────────────────────────────────┘
```

#### 칩 인터랙션 규칙
- **칩 클릭** → 파셋 시트 열림 + 해당 섹션 스크롤/강조
- **칩 ×** → 해당 필터만 제거
- **부정 필터 표기**: `[!@민수]` (느낌표 + 배경 회색 + 취소선)
- **태그 AND/OR 토글**: 태그 칩 그룹 옆 작은 토글 (`+2 more` 식으로 접기)
- **칩 드래그 재정렬**: Boolean 우선순위 시각 표현 (Phase 2 polish)

### 5.2 DSL 직접 입력 (파워유저)

입력창에 DSL 패턴을 타이핑하면 **실시간 파싱 → 칩으로 승격**:

```
입력: folder:ERP/마스터데이터 author:@동해 tag:재고 동기화 주기
      ↓ (스페이스 감지 후)
칩: [📁 ERP/마스터데이터] [👤 @동해] [🏷️ 재고]
쿼리: 동기화 주기
```

- 파싱 실패 토큰은 쿼리에 남김
- `Tab`으로 자동완성 (폴더명, 태그명, 사용자)

### 5.3 폴더 트리 통합

`TreeNav` 폴더 우클릭 메뉴 추가:
```
┌──────────────────────┐
│ 새 문서              │
│ 새 폴더              │
│ 이름 변경            │
│ 삭제                 │
│ ──────────────────── │
│ 🔍 이 폴더에서 검색  │ ← 신규
│ 🏷️ 이 폴더 태그 보기 │ ← 신규 (Phase 4)
└──────────────────────┘
```
→ SearchCommandPalette 열림 + `folders: [선택경로]` 칩 pre-set

### 5.4 AI Copilot (onTalk) 자연어 브릿지

#### 예시 플로우
```
User: ERP 폴더에서 @동해가 지난 달 쓴 재고 관련 문서 찾아줘

  ↓ LLM tool_call

wiki_search({
  "query": "재고 관리",
  "filters": {
    "folders": ["ERP"],
    "authors": ["@동해"],
    "mtime_from": "2026-03-17",
    "mtime_to": "2026-04-17"
  }
})

  ↓ SSE 렌더링

🔍 다음 필터로 검색했어요:
   📁 ERP  👤 @동해  📅 3/17-4/17

찾은 문서 3건:
  • 마스터데이터-관리-지침.md
  • ...

[🔎 검색창에서 계속 탐색 →]  ← 버튼 클릭 시 SearchCommandPalette 열림 + 동일 필터 적용
```

#### 시스템 프롬프트 업데이트
현재 프롬프트(`backend/application/agent/prompts/`)에 필터 가능 속성 목록 명시:
```
When calling wiki_search, you MAY pass a `filters` object with these properties:
- folders: array of folder names (e.g. ["ERP", "MES"])
- authors: array of author handles (e.g. ["@동해"])
- tags: {include, exclude, mode: "AND"|"OR"}
- mtime_from/mtime_to: ISO dates
- types: array of doc types ["sop", "spec", ...]

Parse natural language date expressions ("최근 30일", "지난 달", "2026년 3월 이후")
into mtime_from/mtime_to fields before calling.
```

### 5.5 저장된 필터 (프리셋)

**Phase 4 스콥** — 간단한 개인 프리셋:
- 좌측 상단 프리셋 드롭다운: `▼ 저장된 필터`
  - `⭐ ERP 내부만`
  - `⭐ 내가 쓴 최근 문서`
  - `⭐ review 상태만`
- `💾 필터 저장` → 이름 입력 → `localStorage` (user-scoped via user_id key)
- 우클릭 → 수정/삭제/기본 설정

---

## 6. Accessibility / 키보드

- `Ctrl+K`: 팔레트 열기
- `Cmd+F` (팔레트 열린 상태): 필터 시트 토글
- `Tab/Shift+Tab`: 칩 ↔ 입력창 ↔ 결과 리스트
- `Alt+1~9`: 결과 번호로 바로 열기
- 칩 focus 상태에서 `Delete`: 해당 필터 제거
- aria-label: 칩 → "ERP 폴더 필터, 삭제하려면 Delete"

---

## 7. 성능 예측

### 100K 문서 기준 추정 (품질 우선)
| 시나리오 | pre-filter 후 후보 | 벡터 검색 | 전체 응답 |
|----------|-------------------|-----------|-----------|
| 필터 없음 | 100,000 | ~120ms | ~200ms |
| folders=["ERP"] | 15,000 | ~40ms | ~100ms |
| authors+folders | 500 | ~15ms | ~50ms |
| 매우 선택적 (day+author) | 20 | ~5ms | ~30ms |

- 캐시 히트 시 전체 <10ms
- reranker on: +150ms (top 20 → top 8)
- **품질 이득**: 필터 없이는 noise docs가 top-k 밀어냄, 필터 후엔 정확도 체감 크게 상승

---

## 8. 구현 단계

### Phase 1 — Backend 기반 (3-4시간)
- [ ] `FilterSpec`/`TagFilter` TypedDict 정의 (`backend/core/schemas.py`)
- [ ] `filter_compiler.py` 구현 + unit 테스트
- [ ] `filter_dsl.py` 구현 + unit 테스트
- [ ] `WikiSearchSkill.execute(filters=...)` 시그니처 확장, 기존 `metadata_filter`와 통합
- [ ] `to_tool_schema()` 확장
- [ ] BM25 인덱스 post-filter 지원 (`backend/infrastructure/search/bm25.py`)
- [ ] `tests/test_filter_compiler.py` 20+ 케이스
- [ ] `tests/test_wiki_search_filters.py` (ACL ∩ filter 상호작용)

### Phase 2 — Indexer 보강 (2시간)
- [ ] `wiki_indexer.py`: `authors[]`, `doc_type`, `mtime_epoch` 메타데이터 추가
- [ ] `backend/cli/reindex_metadata.py` 마이그레이션 스크립트
- [ ] 전체 wiki 재인덱싱 (기존 문서 ~100건 검증)

### Phase 3 — Frontend UI (5-6시간)
- [ ] `useSearchStore`에 `filters: FilterSpec` 상태 + `setFilter/removeFilter/clearFilters` 액션
- [ ] `SearchCommandPalette`에 칩 영역 + 모드 뱃지
- [ ] `FilterSheet` 컴포넌트 (우측 드로어, base-ui `Drawer` 또는 `Dialog`)
- [ ] 폴더 트리 통합: `TreeNav` 우클릭 → "이 폴더에서 검색"
- [ ] DSL 파서 (프론트 경량판: split by space + field: prefix 감지)

### Phase 4 — Agent 브릿지 + 프리셋 + 폴리싱 (3-4시간)
- [ ] 시스템 프롬프트 업데이트 (filter 힌트)
- [ ] SSE 이벤트에 `applied_filters` payload 포함
- [ ] Chat UI에 "검색창에서 계속" 딥링크 버튼
- [ ] localStorage 프리셋 저장/로드
- [ ] 빈 결과 상태 (필터 완화 제안)
- [ ] 접근성 마무리 (aria-label, keyboard)
- [ ] `/demo_guide.md`에 시나리오 추가

### 총 예상 시간 — 13~17시간 (4 phase, 단계별 사용자 확인)

---

## 9. 테스트 / 검증 전략

### 자동 (TDD per `CLAUDE.md`)
- `test_filter_compiler.py`: 25+ 케이스 (각 필터 × Boolean × edge)
- `test_filter_dsl.py`: 파싱 AST 정확성
- `test_wiki_search_filters.py`: ACL × filter × 폐기 제외 통합
- `test_bm25_post_filter.py`: post-filter predicate

### 수동 (pre-demo verify per `CLAUDE.md`)
- 실제 채팅: "ERP에서 @동해가 쓴 재고 문서 찾아줘" → 필터 추출 + 결과 정확도
- UI: 5가지 필터 조합 × 빈 결과 × 단일 결과 × 다수 결과
- 100K 스케일 시뮬레이션: 합성 데이터 생성 + 응답 시간 측정

---

## 10. 열린 결정 사항 (사용자 확인 부탁)

1. **필터 시트 위치**: 우측 드로어 (추천) / 상단 확장 / 좌측 사이드바
2. **DSL 지원 범위**: 기본 필드만 / 완전한 Boolean + 괄호 (추천)
3. **프리셋 스코프**: 개인만 (Phase 4 추천) / 팀 공유 (별도 Phase 5)
4. **자연어 실패 처리**: 경고 칩 "필터 추출 실패" 표시 (추천) / 조용히 쿼리로 fallback

---

## 11. 참고 파일 (기존)

- Backend: `backend/application/agent/skills/wiki_search.py`, `backend/application/agent/filter_extractor.py`
- ACL: `backend/core/auth/scope.py`, `backend/core/auth/acl_store.py`
- Chroma: `backend/infrastructure/search/` (chroma, bm25, hybrid, reranker)
- Frontend: `frontend/src/components/search/SearchCommandPalette.tsx`, `frontend/src/lib/search/useSearchStore.ts`
- TreeNav: `frontend/src/components/TreeNav.tsx`

---

## 12. 다음 단계

승인되면 **Phase 1 TDD 착수** (FilterSpec + compiler + DSL 유닛 테스트 먼저).
차단 이슈 있으면 Phase별 재검토.
