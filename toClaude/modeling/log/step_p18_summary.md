# P18 — TermRelation + RuleRelation + 「온톨로지 그래프」 탭 (xyflow)

## 목적
지금까지 BusinessTerm + BusinessRule 은 *개별 노드*만 있었다.
실제 도메인은 그래프 — `품종코드 is_a 코드`, `품종코드 governs <SdLengthRangeAction.guard-0>`,
`<rule-1> conflicts <rule-2>` 같은 관계가 있어야 시뮬레이션 input 의 신뢰도와
사용자 검증 (전체 조감) 이 가능하다.

Q-U3=C 결정 — 온톨로지 그래프 는 **별도 탭** (xyflow), Workbench 와 분리.

## 산출물

### Backend
- `backend/modeling/persistence/models.py` — `OntologyRelationRow` 신규
  (id PK = sha1(repo|src|dst|kind)[:16], unique constraint, ix on src/dst)
- `backend/modeling/persistence/relation_store.py` (NEW)
  - `RelationKind` enum 7 종 — `is_a / part_of / synonym_of / related_to / governs / derives / conflicts`
  - `NodeKind` enum 2 종 — `term / rule`
  - `OntologyRelation` Pydantic + `derive_id()` 헬퍼
  - `SqliteOntologyRelationStore` — put/put_many/get/list_by_repo/list_by_node/delete/clear
- `backend/modeling/api/ontology_graph_api.py` (NEW) — 4 엔드포인트
  - `GET    /api/modeling/repos/{repo_id}/ontology-graph` — nodes (term + rule) + edges (explicit + derived)
    - `?include_unconfirmed_rules=true` 쿼리 파라미터
    - **derived edge** : `rule.terms_ref` → `term governs rule` 자동 inferred (DB 미저장)
  - `GET    /api/modeling/repos/{repo_id}/relations`        — list explicit edges
  - `POST   /api/modeling/relations`                        — 새 관계 생성
  - `DELETE /api/modeling/relations/{rel_id}`               — 삭제 (404 if not found)
- `backend/modeling/api/modeling.py` — `ontology_graph_api.router` include
- `backend/main.py` — `_relation_store = SqliteOntologyRelationStore()` + `_ontology_graph_api.init(...)`

### Frontend
- `frontend/src/lib/api/modeling.ts`
  - 타입 : `RelationKind` (7), `NodeKind` (2), `GraphNode`, `GraphEdge`, `OntologyGraphResponse`
  - 함수 : `getOntologyGraph` / `createRelation` / `deleteRelation`
- `frontend/src/components/sections/modeling/OntologyGraphPanel.tsx` (NEW)
  - xyflow 기반 (`@xyflow/react ^12.10.2` — DI Graph 와 같은 라이브러리)
  - 좌측 column = term (파랑), 우측 multi-column rule (16 개씩 분할, 녹색=확정 / 노랑=미확정)
  - 노드 선택 → 우측 detail 패널 + 연결된 관계 리스트 + 새 관계 추가 폼
  - `RELATION_KINDS` 7 종 색상 + 노드 타입 별 허용 페어 자동 필터
  - 헤더 토글 : 「관계 있는 노드만」 (orphan 숨김) + 「미확정 rule 포함」
  - 도움말 popover (기본은 닫힘)
  - 미니맵 + 줌 컨트롤 + fitView default
- `frontend/src/components/sections/ModelingSection.tsx`
  - `Share2` lucide 아이콘 import
  - `MAIN_NAV` 에 「온톨로지 그래프」 추가 (Workbench 다음 위치)
  - `ModelingView` 타입에 `ontology-graph` 추가 + switch case

### IA 통합 제안
- `toClaude/modeling/IA-개선제안-v1.html` (NEW) — 사용자 검토 요청 4 항목 포함
  - Workbench First 원칙
  - 10 탭 → 6 탭 단계적 전환 (Phase 1~5)
  - 역탐색 / 영향 분석 / DI 그래프 흡수 로드맵
  - 위험 / 트레이드오프

## 검증 (curl, 2026-04-27)

```
# 콜드 그래프 — 2 term + 56 confirmed rule
GET /api/modeling/repos/slab-design-real/ontology-graph
→ counts: {terms:2, rules:56, explicit_edges:0, derived_edges:0}

# 새 관계 (term-term related_to)
POST /relations
body: {"repo_id":"slab-design-real","src_kind":"term","src_fqn":"term.품종코드",
       "dst_kind":"term","dst_fqn":"term.열연공장코드","kind":"related_to","rationale":"..."}
→ id=eb46c82f2a86bcd8, src_id="term.품종코드", ...

# term governs rule (cross-kind)
POST /relations
body: {"src_kind":"term","src_fqn":"term.품종코드","dst_kind":"rule",
       "dst_fqn":"...SdLengthRangeAction.execute#guard-0","kind":"governs","rationale":"..."}
→ id=1f0ef3f39202bc0a

# 그래프 다시 → counts.explicit_edges=2

# DELETE
DELETE /relations/eb46c82f2a86bcd8 → {"deleted":true}
```

UI 시각 검증 (`/tmp/p18_with_edges.png`):
- 사이드바 「온톨로지 그래프」 (Share2 아이콘) 활성
- 헤더 stats: `term 2 · rule 56 · edge 2`
- 좌측 2 term 노드 + 우측 4 column × 14 rule 노드
- 노드 클릭 → 우측 detail 패널 (label, domain, fqn, 연결된 관계, 새 관계 폼)
- 관계 만들기 dropdown : src/dst 노드 종류 페어에 따라 허용 RelationKind 만 표시

## Q-U3=C 정책 매핑
- 온톨로지 그래프 = **별도 탭** (Workbench 와 분리)
- 이유 : Workbench = 메서드 단위 좁은 시각, 그래프 = 전체 조감
- Workbench 에서 노드 검색 → 그래프 jump (cross-nav, 추후 P19+ 에서 구현)

## 다음 (P19)
- Multi-Layer ImpactPropagator — anchor 단위까지 정밀 BFS
- Workbench R 패널 「영향」 탭 활성화
- 영향 분석 탭 흡수 가능성 (IA 제안 Phase 2)
