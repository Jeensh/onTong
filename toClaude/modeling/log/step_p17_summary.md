# P17 — BusinessRule 검토 큐 (Backend REST + Workbench R 패널)

## 목적
P16 으로 메서드 body 에서 추출한 7-종 BusinessRule 중 `guard / bound / enum / lookup` 은
`auto_confirmed=False` 상태로 저장된다 (Q-C=C3 결정).
사용자가 메서드 단위로 검토 → 확정 / 거부 / 편집 할 수 있어야 시뮬레이션 input 으로 신뢰
가능한 rule set 이 만들어진다.

## 산출물

### Backend
- `backend/modeling/api/rules_api.py` (NEW)
  - `GET    /api/modeling/repos/{repo_id}/rules` — 필터 (confirmed/source_prefix/body_kind/method_fqn/limit)
  - `GET    /api/modeling/repos/{repo_id}/rules/stats` — by_source/by_kind/confirmed/pending
  - `POST   /api/modeling/rules/{rule_fqn:path}/confirm` — `confirmed=True` 로 갱신
  - `POST   /api/modeling/rules/{rule_fqn:path}/reject` — registry.delete()
  - `PUT    /api/modeling/rules/{rule_fqn:path}` — statement / severity / terms_ref 편집
  - `RuleDto.from_rule()` 가 `<method_fqn>#<kind>-<idx>` 패턴에서 `method_fqn` + `body_kind` 추출
- `backend/modeling/persistence/rule_registry.py` — `SqliteRuleRegistry.delete(repo_id, rule_fqn) -> bool` 추가
- `backend/modeling/api/modeling.py` — `rules_api` import + `router.include_router(rules_api.router)`
- `backend/main.py` — anchors_api wiring 직후 `_rules_api.init(rule_registry=_rule_registry)`

### Frontend
- `frontend/src/lib/api/modeling.ts` — `RuleDto`, `RuleListResponse`, `RuleStatsResponse` 타입 +
  `listRules / rulesStats / confirmRule / rejectRule / updateRule` API 클라이언트
- `frontend/src/components/sections/modeling/MethodWorkbench.tsx`
  - R 패널 첫 번째 탭으로 「⚖️ 룰 검토」 추가 (default tab)
  - 탭 라벨에 저장소 전체 미확정 수 amber 배지 (예: `62`)
  - `RuleReviewPanel` 컴포넌트 — 메서드 선택 시 그 메서드의 body rule 만 표시
    - kind 별 색상 배지 (`guard / bound / formula / enum / regex / throw / lookup`)
    - severity 배지 (hard 빨강 / soft 회색)
    - 미확정 카드: amber bg, 확정 카드: emerald bg
    - 액션: 확정 / 편집 / 거부 (편집은 statement + severity 인라인)
    - 미확정만 / 전체 토글
    - 메서드 미선택 상태에서는 저장소 통계 (총/확정/미확정 + by_kind) 표시
  - 메서드 클릭 시 `selectMethod` 가 source/anchors/suggestions/rules 4 개를 `Promise.all` 병렬 로드

## 검증 (curl 직접 실행 — 2026-04-26)

```
# 미확정 body rule 5 개 listing
GET /api/modeling/repos/slab-design-real/rules?confirmed=false&source_prefix=body&limit=5
→ 200, 5 items (lookup, formula, throw 등)

# stats
GET /api/modeling/repos/slab-design-real/rules/stats
→ total=119  (body:throw 13 / body:lookup 10 / body:formula 43 / body:bound 6 / body:guard 9 + javadoc 38)

# confirm — `#` 은 %23 으로 인코딩
POST /api/modeling/rules/<fqn>%23lookup-0/confirm
→ confirmed: true

# PUT — 한글 statement + severity 변경
PUT /api/modeling/rules/<fqn>%23lookup-0
body: {"statement":"주조주문 단위로 spec lookup (R-1)","severity":"hard"}
→ 변경 반영

# reject — 실제 SQLite 행 삭제
POST /api/modeling/rules/<fqn>%23lookup-0/reject
→ {"deleted": true}
이후 list 에서 사라지고 stats total 119 → 118
```

UI 시각 검증 (스크린샷 `/tmp/p17_modeling3.png`):
- R 패널 헤더: `⚖️ 룰 검토 [62]` 배지가 정상 표시
- 메서드 미선택 상태에서 "저장소 전체 rule 통계" 카드 + kind 배지 (throw/lookup/javadoc/formula/bound/guard) 모두 색상 정상

## Q-C=C3 정책 매핑
- `formula / throw / regex` → `auto_confirmed=True` (자동 확정, 검토 큐 미노출)
- `guard / bound / enum / lookup` → `confirmed=False` (사용자 1차 검토)
- 사용자가 「확정」 누르면 검토 큐에서 빠지고 ontology card 의 rule 으로 승격

## 다음 (P18)
- TermRelation + RuleRelation 모델 (이미 ontology 에 있는 term 끼리 연결)
- 「온톨로지 그래프」 탭 (xyflow) — Q-U3=C
