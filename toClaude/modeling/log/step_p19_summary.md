# P19 — Multi-Layer ImpactPropagator + IA Phase 2/3 + Q3/Q4

## 한 번에 적용된 4 작업
사용자 요청 「Phase 2~5 시작 + 흡수 1 개는 알아서 + Q3/Q4 그대로」 반영.

| 작업 | 내용 |
|---|---|
| **Q3** | 온톨로지 그래프 default 「관계 있는 노드만」 ON |
| **Q4** | 기준서 + 매뉴얼 작성 → 단일 「📚 매뉴얼」 탭 (sub-tab : 업로드 / 작성) |
| **Phase 3** | 역탐색 → Workbench ⌘K Command Palette 흡수 (deprecation banner 추가) |
| **P19 + Phase 2** | Multi-Layer Impact 백엔드 + Workbench 「🧬 영향」 탭 활성화 + 영향 분석 탭 deprecate |

## 산출물

### Backend (P19)
- `backend/modeling/impact/__init__.py` (NEW) — 모듈 외부 노출
- `backend/modeling/impact/multi_layer_propagator.py` (NEW)
  - `LayerKind` enum 3 종 — code / ontology / manual
  - `ImpactNode` dataclass + `MultiLayerImpactResult.to_dict()`
  - `MultiLayerImpactPropagator` 3 layer BFS
    - **code** : `query_engine.impact()` 재사용 + anchor 확장 (`anchor_store.list_by_method`)
    - **ontology** : `OntologyRelation` BFS + auto-derived edges (`rule.terms_ref` → `term governs rule`)
    - **manual** : `ManualFragment.attributes` 의 `term` / `rule` ref 매칭
  - `_derive_ontology_seed` — code 시작점이면 method_fqn → 매칭 rule fqn 변환
  - `_label_for` — fqn → 사람용 라벨 (term canonical, rule statement[:80])
- `backend/modeling/api/multi_impact_api.py` (NEW)
  - `GET /api/modeling/impact/multi-layer` — 단일 endpoint
  - 파라미터 : `repo_id`, `target_fqn`, `target_kind` (code|term|rule), `hops_code/ontology/manual`, `node_limit`, `include_anchors`
- `backend/modeling/api/modeling.py` — `multi_impact_api.router` include
- `backend/main.py` — `MultiLayerImpactPropagator` 인스턴스 + `multi_impact_api.init`

### Frontend
- `frontend/src/lib/api/modeling.ts` — `MultiLayerImpactNode` / `MultiLayerImpactResponse` 타입 + `getMultiLayerImpact` 함수
- `frontend/src/components/sections/modeling/MethodWorkbench.tsx`
  - Workbench R 「영향」 탭 placeholder → `ImpactPanel` 컴포넌트로 교체
  - target 선택 토글 (메서드 / 매서드의 rule 들)
  - layer 별 그룹핑 (코드 💻 / 온톨로지 🌐 / 매뉴얼 📚) + 색상 + 펼치기 상세
- `frontend/src/components/sections/modeling/WorkbenchCommandPalette.tsx` (NEW)
  - ⌘K / Ctrl+K 토글 (input 안이 아니면)
  - 모드 토글 「코드」 / 「용어」 → 각각 `globalSearch` / `reverseLookup`
  - 키보드 단축키 : ↑↓ 이동, Enter 선택, Esc 닫기, ⌘K 모드 토글
  - 자동 디바운스 (250ms), 결과 자동 스크롤
- `frontend/src/components/sections/modeling/ManualHub.tsx` (NEW)
  - 단일 「📚 매뉴얼」 탭, sub-tab 으로 업로드 / 작성 분리
  - 기존 `ManualUpload` / `ManualWriter` 재사용 (변경 없음)
- `frontend/src/components/sections/modeling/OntologyGraphPanel.tsx`
  - `useState<bool>(true)` — onlyConnected default ON
- `frontend/src/components/sections/modeling/ReverseLookupPanel.tsx`
  - 상단에 amber deprecation banner — Workbench ⌘K 안내
- `frontend/src/components/sections/modeling/ImpactAnalysisPanel.tsx`
  - 상단에 amber deprecation banner — Workbench R 「🧬 영향」 안내 (3 layer 강조)
- `frontend/src/components/sections/ModelingSection.tsx`
  - `Share2` 추가, `PenLine` 제거 (사용 안 함)
  - `ManualHub` import + `manual` view + legacy redirect
  - MAIN_NAV 정리 : 기준서 + 매뉴얼 작성 → 매뉴얼 (1개)
  - 역탐색 description : "(deprecated) Workbench ⌘K 로 이동 권장"
  - 영향 분석 description : "(deprecated) Workbench R 「🧬 영향」 으로 이동 권장 (3 layer)"

## 검증

### Backend (curl)
```
GET /api/modeling/impact/multi-layer
   ?repo_id=slab-design-real
   &target_fqn=term.품종코드
   &target_kind=term
   &hops_ontology=4

→ counts: {code:0, ontology:2, manual:0}
  ontology[0] : term.열연공장코드 (related_to, depth=1)
  ontology[1] : SdLengthRangeAction.execute#guard-0 (governs, depth=1)
```

### UI (스크린샷 `/tmp/p19_*.png`)
- 사이드바 : Workbench / 온톨로지 그래프 / Repository / **매뉴얼 (통합)** / 용어 매핑 / 갭 큐 / 역탐색 (deprecated) / 영향 분석 (deprecated) / DI 그래프
- 온톨로지 그래프 : default 「관계 있는 노드만」 ON 으로 2 term + edge 1 만 표시 (clean)
- Workbench 헤더 : 「⌘ 검색 ⌘K」 + reindex 버튼

## 사이드바 변화 요약 (10 → 9 + 2 deprecated 표기)

| 카테고리 | 탭 | 비고 |
|---|---|---|
| 핵심 | Workbench, 온톨로지 그래프 | (그대로) |
| 입력 | Repository, **매뉴얼**, 용어 매핑 | 매뉴얼 통합 |
| 배치 | 갭 큐 | (그대로) |
| Deprecated | 역탐색, 영향 분석 | banner + Workbench 흡수 안내 |
| 보조 | DI 그래프 | (그대로) |

다음 단계 (Phase 4) — 갭 큐 흡수 검토는 P22 시뮬레이션 drawer 와 함께 (P22 후).
다음 단계 (Phase 5) — DI 그래프 → Repository 우측 패널 흡수 (선택).

## 다음 (P21 또는 P23 spike)
- **P21** Ontology Editor 인라인 편집 + 외부 매뉴얼 LLM auto-link → 매핑 기능 80% → 95% 완성
- **P23 spike** PythonGenerator (Java method body → Python LLM) 가설 검증 — 시뮬레이션 가능성 결정
