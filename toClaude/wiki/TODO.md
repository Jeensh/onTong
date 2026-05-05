# 위키 섹션 TODO (Section 1)

> 단일 진실 소스. 완료 시 `[x]` 체크.
> 상위 규칙: `CLAUDE.md`의 **📋 Step Completion Protocol**.

---

## 진행 중

### 메타데이터/경로/폴더 검색 조건화

스펙: `specs/2026-04-17-metadata-search-design.md`

#### Phase 1 — Backend 기반 (3-4h) ✅
| # | Task | 상태 |
|---|------|------|
| MS-1 | FilterSpec 형태 확정 (dict 기반, TypedDict 선언은 유예) | [x] |
| MS-2 | `backend/application/agent/filter_compiler.py` + 35 테스트 | [x] |
| MS-3 | `backend/application/agent/filter_dsl.py` (Boolean 파서) + 24 테스트 | [x] |
| MS-4 | `WikiSearchSkill.execute(filters=...)` 확장 + 기존 filter merge | [x] |
| MS-5 | `to_tool_schema()` filters 객체 노출 | [x] |
| MS-6 | BM25 `filter_predicate` 파라미터 | [x] |
| MS-7 | `tests/test_wiki_search_filters.py` (6 테스트, ACL × filter × 폐기) | [x] |

#### Phase 2 — Indexer 보강 (2h) ✅
| # | Task | 상태 |
|---|------|------|
| MS-8 | `wiki_indexer.py`에 `authors[]`, `doc_type`, `mtime_epoch` 추가 | [x] |
| MS-9 | `cli/reindex_metadata.py` 마이그레이션 스크립트 | [x] |
| MS-10 | 전체 재인덱싱 + 메타 필드 검증 (12 테스트 통과) | [x] |

#### Phase 3 — Frontend UI (5-6h) ✅
| # | Task | 상태 |
|---|------|------|
| MS-11 | `useSearchStore` `filters` 상태 + 액션 | [x] |
| MS-12 | SearchCommandPalette 칩 영역 렌더링 | [x] |
| MS-13 | `FilterSheet` 컴포넌트 (우측 드로어) | [x] |
| MS-14 | TreeNav 우클릭 "이 폴더에서 검색" | [x] |
| MS-15 | 프론트 DSL 경량 파서 | [x] |

#### Phase 4 — Agent 브릿지 + 프리셋 (3-4h) ✅
| # | Task | 상태 |
|---|------|------|
| MS-16 | 시스템 프롬프트에 filter 힌트 추가 | [x] |
| MS-17 | SSE `applied_filters` payload + "검색창에서 계속" 버튼 | [x] |
| MS-18 | localStorage 프리셋 저장/로드 | [x] |
| MS-19 | 빈 결과 상태 (필터 완화 제안) | [x] |
| MS-20 | 접근성 마무리 + demo_guide 추가 | [x] |

---

### Rename / 경로 변경 + 동시성 정합성 (신규 initiative — 2026-05-05)

설계서: `specs/2026-05-05-rename-concurrency-design.md` (v0.2)
구현 플랜: `specs/2026-05-05-phase0-implementation-plan.md` (Phase 0)

#### Phase 0 — 인프라 추상화 + 백엔드 (선행 0)
| # | Task | 상태 |
|---|------|------|
| 0-1 | Profile 시스템 (`backend/core/profile.py` + Settings 확장) | [ ] |
| 0-2 | Backend factory + Lock 통합 (Redis 활성화) | [ ] |
| 0-3 | EventBus Redis Pub/Sub adapter | [ ] |
| 0-4 | KVStore 추상 + FileHashStore/IndexStatus 마이그레이션 | [ ] |
| 0-5 | MetadataIndex Redis hash 백엔드 | [ ] |
| 0-6 | Postgres 스키마 + Alembic (refs/versions/snapshots/audit/jobs) | [ ] |
| 0-7 | TaskQueue (asyncio + Arq) + path/content worker 스켈레톤 | [ ] |
| 0-8 | `GET /api/wiki/profile-status` endpoint | [ ] |
| 0-9 | `ontong` CLI 진입점 + `migrate db-upgrade` | [ ] |

#### Phase 1~6 — 후속 (Phase 0 완료 후 분해)
| # | Phase | 상태 |
|---|------|------|
| P1 | ReferenceIndex + 추출기 + broken-link + Delete 차단 (G7) | [ ] |
| P2 | OCC + 스냅샷 (P0 와 병렬 가능) | [ ] |
| P3 | 단일 파일 rename — RenameOrchestrator + Two-Phase 락 + chunk 본문 패치 | [ ] |
| P4 | 폴더 / bulk (P3 batch) + bulk 락 | [ ] |
| P5 | UX 마감 — 영향도 미리보기 / 진행률 / undo / 편집 차단 | [ ] |
| P6 | 스케일 검증 + ES enterprise 도입 | [ ] |

---

## 대기

_(없음)_

---

## 완료 (최근 5개)

- 2026-04-17 · Phase 4 Agent 브릿지 + 프리셋 (MS-16~MS-20, NL rule extractor + SSE `applied_filters` + localStorage 프리셋 + 빈결과 완화 제안 + a11y + demo_guide, 누적 105 테스트)
- 2026-04-17 · 운영 재인덱싱 (`reindex_metadata --force`, 22 파일 / 140 청크 / 13.8s, mtime bug 수정)
- 2026-04-17 · Phase 3 Frontend UI (MS-11~MS-15, `useSearchStore.filters` + `FilterSheet` 우측 드로어 + 칩 영역 + TreeNav "이 폴더에서 검색" + 경량 DSL 파서, 누적 85 테스트)
- 2026-04-17 · Phase 2 Indexer 보강 (MS-8~MS-10, `authors[]`/`doc_type`/`mtime_epoch` 필드 추가, CLI 마이그레이션 스크립트, 12 테스트 통과)
- 2026-04-17 · Phase 1 메타데이터 검색 백엔드 기반 (MS-1~MS-7, 65 테스트 통과)

---

## 메모

- 위키 섹션(Section 1)은 **이 폴더(`toClaude/wiki/`)만** 쓰기 가능
- `wiki/` 루트(제품 콘텐츠)는 격리 예외 — 작업 전 `git status` 확인
- `toClaude/_shared/` 수정은 **사용자 승인 필수**
