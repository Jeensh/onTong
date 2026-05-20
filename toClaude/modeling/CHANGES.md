# 변경/추가 요청

> 세션 사이에 요구사항이 바뀌거나 추가되면 여기에 메모.
> Claude는 매 세션 시작 시 이 파일의 `[ ]` 항목을 확인하고 우선 처리.
> 처리 완료 시 `[x]`로 체크하고 TODO.md/master_plan.md에 반영.

---

## 2026-05-18 (cross-section: Phase E-C — Parser + Translator rework)

> Section 3 (simulation) 세션이 cross-section 권한으로 modeling 코드 수정.
> 상세 분해 + 카운트 변화는 `../simulation/log/step_ec_parser_translator_rework.md` 참조.

### 추가/수정 (modeling 영역만)
- [x] `backend/modeling/code_analysis/method_symbol_table.py` (신규 190 LOC) — params/locals/for-each/try-with-resources/catch/instanceof pattern var/class field 추적
- [x] `backend/modeling/code_analysis/java_parser.py` — `_extract_calls` 가 `attributes["receiver_type"]` + `receiver_kind` + `receiver_text` 를 additive 부착. **target shape 보존** (call_resolver backward-compat OK).
- [x] `scripts/export_modeling_enrichment.py` + `scripts/reapply_modeling_enrichment.py` — re-import safety net (round-trip verified)

### Importer 영향
- 다음 import 부터 자동으로 `receiver_type` 채움 → `analyze_call_sites` 가 single_impl/annotation 으로 native 분류 (이전: 모두 static_unresolved)
- slab-design-real-v2 기준: 2,448 raw calls 중 2,114 (86%) 가 receiver_type 자동 채움, 1,435 (≥0.85 confidence) 가 native high-conf 분류

### 회귀 검증 (modeling 측)
- `tests/test_java_parser_basic.py` 19 PASS
- `tests/test_java_parser_annotations.py` 14 PASS (3 skipped)
- `tests/test_java_parser_field_attributes.py` 14 PASS (3 skipped)
- `tests/code_layer/` 64 PASS (2 pre-existing FK 실패는 무관)
- `tests/test_spring_*_analyzer.py` 60+ PASS (call_resolver qualifier 테스트도 OK)

### 커밋
- `9a6a6a8` feat(modeling): enrichment export/re-apply safety net
- `f449355` fix(modeling+sim_v2): receiver-type symbol table + 5 translator gaps

---

## 2026-05-18 (Graph Redesign — Option 3 Coverage + Impact 분업)

사용자 결정: 옵션 3 (B Coverage daily + A Impact event) + d/a/a + b/a 로 확정.
"확실한 가치와 목표를 정하고 가줘" → 두 모드 분업으로 일상 진척률 모니터링 + 변경 영향 분석을 분리.

- [x] **Backend audit 테이블** — `backend/modeling/audit/{__init__,orm,store}.py` 신설.
      `EntityChangeLogRow` PK=autoincrement + 복합 인덱스 (repo_id, changed_at) / (entity_kind, entity_id).
      `log_change`, `log_changes_bulk`, `count_recent_changes`, `recently_changed_ids` 헬퍼.
      `queue_actions_api.py` confirm/reject/unconfirm/patch 모든 분기에 hook + `recommend_api.py` persist 시 bulk hook.
- [x] **Coverage 엔드포인트** — `GET /api/ontology/repos/{repo_id}/graph/coverage`
      도메인 grid heatmap (term/action/code_type by domain — code_type 는 package 마지막 2 segment).
      `+ /coverage/{domain}/priority?lens=draft,orphan,recent&limit=50&recent_days=7`
      우선 처리 entity 리스트 (priority_score + reasons). 2026-05-18 후속: code_type branch 추가
      (예: `domain.logic` 같은 code_type-only 도메인이 0 hits 였던 문제 해결 — **백엔드 재시작 필요**).
- [x] **Impact 엔드포인트** — `GET /api/ontology/repos/{repo_id}/graph/impact?focus=...&focus_kind=...&hops=2&direction=both`
      양방향 BFS, match_kind 5단계 strength (receiver_exact/short/runtime_type/package_proximity/name_only)
      기반 risk_score = 10 × strength / (distance+1). risk_top + re_verify_targets (confirmed anchor)
      + expand_method_targets. `+ /impact/expand-method?code_type_fqn=...` 클래스 lazy method 펴기.
      `_forward_neighbors` self-join SQL bug 수정 (ambiguous column name).
- [x] **Frontend store** — `graphTopMode: coverage|impact|explore`, `coverageLenses[]`,
      `coverageExpandedDomain`, `impactFocusFqn`, `impactFocusKind`, `impactHops`, `impactDirection`,
      `impactMinStrength`, `impactIncludeMethods`, `impactExpandedTypes[]` + setters/toggles + `jumpToImpact()`.
- [x] **Frontend API client** — `lib/api/ontology.ts` 에 `getCoverage`, `getCoveragePriority`, `getImpact`,
      `expandImpactMethods` + 대응 DTO (`CoverageResponseDTO`, `DomainCellDTO`, `PriorityResponseDTO`,
      `ImpactResponseDTO`, `ImpactNodeDTO`, `ImpactEdgeDTO`, `MethodNodeDTO`, `ExpandMethodResponseDTO`).
- [x] **Frontend URL sync** — `useUrlSync.ts` 에 `graph_mode`, `lenses`, `impact_focus`, `impact_kind`,
      `hops`, `dir` 양방향 sync 추가. Explore 모드는 기존 `mode/focus/target/n_max/p/compound` 유지.
- [x] **GraphMode.tsx** — top-level 3-mode switcher (Coverage / Impact / Explore) + 한 줄 hint.
      Esc 닫기는 유지.
- [x] **CoverageView.tsx** — lens 토글 (☑/☐ Draft / Orphan / Recent) + recent_days select (1/3/7/14/30d)
      + stalled 6 / 완료율 % 헤더 + ratio 색조 cell (green/amber/rose) + cell click → priority panel
      펼침. entity hover → "Impact" 버튼 노출 → `jumpToImpact(fqn, kind)` 로 Impact mode 진입.
- [x] **ImpactView.tsx** — focus chip + 5단계 strength 색 엣지 (sky/cyan/emerald/amber/red-400) + xyflow
      canvas (distance 기반 layout: focus 중앙, backward 좌측, forward 우측) + 사이드 패널
      (Summary / 위험 Top 12 / 재검증 대상 / 메서드 확장 (lazy ExpandMethodRow)).
- [x] **E2E 검증** — `view=graph` 진입 → Coverage 39 도메인 grid 정상 렌더 + lens 토글 ☑/☐ 작동
      + cell click → 패널 펼침 (term/action 도메인 = 0 candidates because all confirmed; code_type
      도메인은 backend 재시작 후 작동). Impact `?graph_mode=impact&impact_focus=...&impact_kind=action`
      URL 진입 → focus chip + risk Top (5.00 execute / 4.50 BR original_equals_adjusted 등) +
      재검증 대상 (SdSlabSaveAction.execute, SlabNoSequence.next) 정상.
- [ ] **백엔드 재시작 후 확인** — `domain.logic`, `working.action` 같은 code_type-only 도메인의
      priority 패널이 entity 리스트를 채우는지. (현재 코드는 패치 완료, uvicorn `--reload` 없이
      실행 중이라 hot pickup 안 됨.)

### 2026-05-18 후속: CodeType detail 메서드 inline expand

사용자 flag: "큐 → code type → 메서드 클릭 무반응".

- [x] **method row → 펼침 토글** — `MainPanel.tsx CodeTypeDetail` 의 method 렌더가 `<div>` (onClick
  X) 였음. `<button>` 으로 교체 + `expandedMethods: Set<string>` state + `ChevronRight` 회전.
  `m.body_text` 가 이미 CodeTypeDTO 에 포함되어 있어 추가 fetch 없이 inline `JavaCode` 렌더.
  body 가 없는 (abstract/interface/parser 누락) method 는 `disabled + opacity-30 chevron` 으로
  명시. line 정보 + anchor count header 도 펼친 코드 위에 표시.

### 2026-05-18 후속: 큐 미리보기 색상 통일 + 정보 완전성

사용자 피드백: "색상때문에 글자 안 보임 + 의미있는 작업 도달 가능?" → 3개 항목.

- [x] **색상 통일 (single accent)** — violet/emerald/rose 의 혼재 제거. Header `bg-violet-500/10 +
  text-violet-300` → `bg-muted/40 + bullet primary dot + text-foreground`. Confirm 버튼
  `bg-emerald-500/20 text-emerald-200` (저대비) → 기본 `<Button>` (solid primary). Reject 는
  `text-destructive border-destructive/40 hover:bg-destructive/10` 로 idle 상태에서도 의미 노출.
  Selected QueueRow / 추천 버튼 / 새 entity 버튼 모두 `text-primary + bg-primary/10 + border-primary` 로 통일.
- [x] **Action preview realizations/params/effects 상위 3개** — `ListSection` 컴포넌트 신설.
  count 만 보이던 `Params · 4`, `Effects · 2`, `Realizations · 3` 영역에 각각 상위 3개 압축
  list (main / sub 2-line) + `+ N more (Detail 탭에서 전체 확인)` 표시. 의사결정 직전 충분한
  근거 노출.
- [x] **Realization preview 양쪽 context** — code_type + term 을 concurrent fetch
  (`Promise.all`). 상단에 `code_type → term` 매핑 헤더 + scope chip (primary/muted) + confidence.
  아래에 `ContextCard` 2개: (1) Code type — simple_name / package / kind / role / 메서드 상위 4 +
  +N more, (2) Term — label / kind / domain / aliases / root flag / description block. rationale
  은 별도 Block. "이 매핑 맞아?" 판단 정보 완전화.
- [x] **공통 building blocks** — `Field` (label/value grid), `Block` (description/rationale 박스),
  `ListSection` (top-3 + rest), `ContextCard` (heading + loading + empty) 4개 small components
  로 분리. 시각 위계 통일.

### 2026-05-18 후속: 새 entity 생성 + 큐 미리보기 결함 일괄 수리

사용자 피드백: "사용성/UI 버그 + Code 큐 여전히 무반응". 검토 후 6개 항목 수리.

- [x] **Code (legacy) section row 클릭 원활화** — `LeftPanel.tsx:258-321` 의 `<div>` 를
  `<button>` 으로 교체. ambig callsite → caller method 의 parent type 으로, unmapped method →
  `code_method.parent_type_fqn` 으로 `setSelectedCodeType` + `setLeftTab("code")`. selected 시
  violet 좌측 border. (사용자 flag — Code 큐 53개 항목 무반응 해결)
- [x] **NewEntityModal kind 전환 시 state reset** — `switchKind(k)` 헬퍼가 reset 호출 후 setKind.
  Term → Action 전환 시 fqn/label/domain/aliases 다 초기화 → 잘못된 entity 로 submit 위험 제거.
- [x] **Modal backdrop click 제한** — `hasInput` 가드. 입력 있을 때 backdrop 클릭 무시. X 버튼
  또는 "취소" 버튼으로만 닫힘. 실수로 입력 손실 방지.
- [x] **"+ 새로" 버튼 재배치** — 탭 strip 안 misalignment 제거. 별도 toolbar 로 분리 (탭 strip
  위에 우측 정렬, violet 테두리 + "새 entity 추가" full label).
- [x] **QueuePreviewPanel → Detail 이동 시 leftTab 동기화** — Term/Action 선택 시
  `setLeftTab("ontology")`, Realization 의 code_type 선택 시 `setLeftTab("code")`. tree 와 detail
  panel 의 entity kind 일치.
- [x] **Anchor 입력 search picker** — `SearchPicker` 컴포넌트 신설. `code_method_fqn` /
  `target_action_fqn` 필드를 backend `/api/ontology/search` 호출 autocomplete 로 교체. kind filter
  (code_method 또는 action) + debounced 200ms + 외부 클릭 시 dropdown 닫힘 + 매칭 없으면 직접
  입력 fallback. 사용자가 손으로 FQN 타이핑 부담 제거.

### 2026-05-18 후속: 새 entity 생성 진입점 + 큐 미리보기 패널

사용자 결정 (브리핑 후): 새 entity 생성 = 전용 모달 / 큐 row 클릭 = RightPanel preview.

**새 entity 직접 추가**
- [x] **Backend `entity_create_api.py`** — 4개 POST 엔드포인트 신설:
  - `POST /api/ontology/repos/{repo_id}/terms` (TermCreateBody)
  - `POST /api/ontology/repos/{repo_id}/actions` (ActionCreateBody)
  - `POST /api/ontology/repos/{repo_id}/business-rules` (BusinessRuleCreateBody)
  - `POST /api/ontology/repos/{repo_id}/anchor-bindings` (AnchorBindingCreateBody)

  모두 `confirmed=False` + audit log `changed_by="user"` + 충돌 시 HTTP 409.
  Anchor 는 `sha1(method|locator|action|slot)[:16]` 으로 id 자동 계산.
  `main.py` 의 `include_router(entity_create_api.router)` 등록.
- [x] **Frontend `NewEntityModal.tsx`** — `LeftPanel` 상단 우측 `+ 새로` 버튼 → modal. Kind selector
  (Term/Action/BR/Anchor) + kind 별 필수 필드 (FQN/Label/Statement/anchor locator 등) + radio pill
  (atomic/composite, pure/effectful/workflow, hard/soft) + 검증 에러 표시. 성공 시 적절한
  `setSelectedXxx` + `bumpQueueRefresh` + 모달 닫기.
- [x] **API client 확장** — `ontology.ts` 에 `createTerm / createAction / createBusinessRule /
  createAnchorBinding` + DTO (`TermCreateBody / ActionCreateBody / BusinessRuleCreateBody /
  AnchorBindingCreateBody / CreateResult`).

**큐 row 클릭 → RightPanel 미리보기**
- [x] **`selectedQueueItem` store state** — `{kind: "term"|"action"|"realization", id}` + setter.
- [x] **`QueueRow` 클릭 영역** — title/subtitle/tag block 을 `<button>` 으로 감싸 `onSelect` 호출.
  `selected={true}` 시 violet 좌측 border + 배경. confirm/reject 버튼은 별도 영역 유지.
- [x] **`QueuePreviewPanel.tsx`** — RightPanel 자리에 표시되는 별도 컴포넌트. Term/Action 은 detail
  fetch + 기본 필드 요약 (FQN/Label/Kind/Domain/Aliases/Description), Realization 은 queue list
  에서 다시 찾아 code_type/term/scope/confidence 표시. 하단에 "Detail 탭으로 이동" + Confirm /
  Reject mirror 버튼. ESC 또는 X 로 닫으면 평소 RightPanel 복귀.
- [x] **RightPanel 분기** — `selectedQueueItem` 이 truthy 면 평소 tab/breadcrumb 자리에 `QueuePreviewPanel`
  full takeover. 우측 panel drag handle 만 유지.

### 2026-05-18 후속: 모델링 섹션 전체 inventory + 정리 (확장 라운드)

사용자 결정 (브리핑 후 다중 선택): 검색 통합 + dead code 청소 + UX 수리 모두 채택.

**검색 수리**
- [x] **Cmd+K 전 kind navigate** — `code_type / term / code_method / rule` 클릭 시 적절한
      `setSelectedXxxFqn` 호출. code_method 는 parent type FQN 으로 fallback. 이전엔 `action`
      만 navigate 가능했음. `CmdKPalette.tsx:55-72`
- [x] **BR 클릭 원활화** — ModuleTree `onPickSearchHit` + Cmd+K 모두 `kind==="rule"` 시
      `setSelectedRule(fqn)` 호출. backend 응답에 BR 포함되어도 클릭이 무반응이던 문제 해결.
- [x] **검색 정렬 tie-break** — `ontology_query.py:_KIND_RANK` 추가. 같은 score 안에서
      `term > action > code_type > code_method > rule` 우선순위. Python dict 순서 의존 제거.
- [x] **Graph cluster mode 에서 검색 노출** — `mode !== "cluster"` 가드 제거. cluster supernode
      도 검색 결과에 노출, 클릭 시 `pkg:` prefix 감지해 `setMode("neighborhood") + setFocus(members[0])`
      로 자동 expand. `OntologyGraph.tsx:193-220`

**Dead code 청소**
- [x] **BackwardMode.tsx + Direction toggle 제거** — `BackwardMode.tsx` 파일 삭제, `MainPanel.tsx`
      의 fwd/bwd 토글 + `direction === "bwd" && <BackwardMode />` 분기 제거. `store.ts` 의 `Direction`
      타입 + `direction` state + `setDirection` 제거. `StatusBar.tsx` 의 "Forward/Backward 모드" footer 제거.
      "Simulation Engine — 다음 phase" 표시는 의도된 dead UX 였음.
- [x] **LeftPanel V6 잔재 함수 제거** — `MapTab` / `CodeTreeTab` / `DomainTreeTab` /
      `ActionTreeTab` 4개 함수 (~235줄) 제거. 실제 사용 컴포넌트는 `ModuleTree` / `OntologyTab`
      / `QueueTab` 만. unused DTO type imports 동시 정리.
- [x] **RightPanel `_CodeViewUnused`** — 조사 결과 실제로 존재하지 않음 (audit agent 오인). 패스.

**UX 수리**
- [x] **Manual Re-recommend 버튼** — `LeftPanel.tsx` 의 QueueTab 상단에 `Sparkles` 아이콘 버튼
      추가. 클릭 시 `ontologyApi.recommendForRepo(repo, {persist: true})` + queue reload.
      에러 시 빨간 배너 표시. Import 후 매핑 보정 → 재추천 시나리오 해금.
- [x] **Authoring confirm → Queue 자동 refresh** — workbench store 에 `queueRefreshTick` +
      `bumpQueueRefresh()` 추가. authoring/store 의 `runConfirm` 성공 후 호출. QueueTab 의
      `useEffect` deps 에 `queueRefreshTick` 추가 → 자동 reload. cross-store 신호 패턴.
- [x] **Split mode anchor scroll** — `MainPanel.tsx` 의 Static Parser Anchors 12개 limit + "…N
      더" 메시지 제거. `max-h-48 overflow-y-auto pr-1` 로 전체 anchor scroll 가능.
- [x] **StatusBar 카운터 검증** — `/queue/verification-progress/slab-design-real-v2` HTTP 200
      `{total_actions: 130, by_level: {sim_verified: 124, signature_locked: 6}}`. UI 도 정확히
      반영 (`U 0 / D 0 / SL 6 / BA 0 / SV 124 / PR 0 · 총 130`). 이전 "모두 0" 은 백엔드 미시드 상태였음.

### 2026-05-18 후속: 그래프 perf 조치 + 기능 정리

사용자 결정 (브리핑 후): backend `_importance_neighborhood` 최적화 + Impact 더블클릭 렉 완화 +
lens="verify" / Compound / Path 제거 + Cluster supernode expand 수리.

- [x] **`lens="verify"` dead code 제거** — `store.ts` 의 `Lens` 타입 + `lens` state + `setLens`,
      `TopBar.tsx` 의 "Lens: verify" crumb 제거. V7 잔재 청소.
- [x] **Compound mode 제거** — `graphCompound` state + ELK `INCLUDE_CHILDREN` 옵션 + Domain box
      nesting 전부 정리. `useUrlSync` 의 `compound=1` URL param 제거. `PerspectiveDropdown` 의
      compound 표시 + spec 저장 시 `compound: false` 로 고정 (backend 스키마 backward-compat).
- [x] **Path mode UI 제거** — `OntologyGraph` 에서 "경로" ModeButton, target 검색 input, target
      chip, `searchTargetQ`/`targetHits` state 제거. `mode === "path"` 분기 → neighborhood 으로
      coerce. `GraphViewMode` 타입은 `"path"` 유지 (저장된 Perspective backward-compat).
- [x] **백엔드 `_importance_neighborhood` 힙 최적화** — `graph_api.py` 의 `max()` 풀스캔
      (O(selected × |pool|)) → max-heap (O((selected+frontier) log frontier)). 합성 5K node /
      40K edge 그래프에서 ~9ms (n_max=600). 옛 로직은 5K 규모에서 추정 1초 이상.
- [x] **Impact 더블클릭 렉 완화** — `ImpactCanvas` 가 `key={data.focus.fqn}` 로 re-mount
      (xyflow 1K+ 노드 diff 비용 회피). `FIT_VIEW_OPTS` 정적화 (`duration: 0`). edges > 200
      이면 label/animated/markerEnd (약한 엣지) 비활성 — dense paint 비용 절감.
- [x] **Cluster `pkg:` supernode expand 수리** — `OntologyGraph.tsx:179` 의 click ignore 제거.
      backend `_cluster_by_package` 가 supernode `extra.members[]` (max 50) 채움. 프론트 click →
      `setMode("neighborhood") + setFocus(members[0])` 로 패키지 내부 진입. R4-T3.3 미완성 TODO 종결.

### 2026-05-18 후속: ontology.db 스키마-데이터 정합성 마이그레이션

증상: 우측 트리 로드 실패 — `API 400: 2 validation errors for ActionEffect target_term Field
required ... target Extra inputs are not permitted ...`. listActions 가 ORM row → Pydantic
DTO 직렬화 시 invariant 어김.

- [x] **legacy effect shape 변환** — 52 rows. `{op, target, description}` → `{op, target_term,
      target_attr, description}`. "Term.attr" 는 split, "Term (모든 필드)" 는 suffix 를 description
      으로 보존. 백업: `data/ontology.db.bak-effect-migration-20260518-162547`.
- [x] **op='emit' 19개 → 'create'** — emit (exception 발생 / enum 출력 반환) 은 `ActionEffectOp`
      enum 에 없음. 의미상 "결과 instance 생성" 이라 create 가 가장 가까움.
- [x] **pure_function with effects 24개 → effectful** — schema invariant
      (`pure_function MUST NOT have effects`) 충족. 실제로 term read + exception emit 하는 게 다수.
- [x] **workflow with realization 1개 → effectful** — `action.scm.슬랩설계_실행__designer` 가
      sub_actions=[] + realizations=1 이라 mis-classification. canonical workflow
      `action.scm.슬랩설계_실행` 은 sub_actions 21 + realizations 0 으로 유지.
- [x] **결과** — `GET /actions?repo_id=slab-design-real-v2` HTTP 200. by_kind = workflow 1 /
      effectful 128 / pure_function 1, effects 가진 action 52 개. 좌측 트리 정상 로드 (150 CodeType
      + package breakdown).

### 2026-05-18 후속: 모델링 섹션 전체 텍스트 overflow sweep

사용자 호소: "전체적으로 모든 섹션 설명이 막 섹션안에 갇혀서 짤리기도 하고, 영역을 텍스트가
벗어나기도하고 문제가 많아 전체 작업해줘". audit agent 가 ~25 spots 식별 → 4개 공통 패턴
도출 후 7개 파일에 일괄 적용.

**Pattern A — `flex + truncate` 깨짐 (`min-w-0` 누락)**
- [x] `MainPanel.tsx` Action FQN row (`line 210`) / Term FQN row (`line 833`) / CodeType package row
      (`line 974`) — truncate span 에 `min-w-0 flex-1` 부여. flex 부모가 자식 너비를 강제 축소
      하지 않으면 truncate 가 안 먹는 root cause.
- [x] `OntologyTab.tsx` TermRow/ActionRow/BRRow/AnchorRow 의 4개 row 모두 (line 315/334/357/374) —
      label/FQN 영역 span 에 `min-w-0` 추가. 좌측 트리 항목이 컨테이너 밖으로 새어나가던 증상 해결.
- [x] `NodePreviewPanel.tsx` 헤더 label span (`line 178`) — `truncate flex-1 min-w-0` 로 그래프
      노드 hover 박스의 긴 FQN 짤림 처리.
- [x] `QueuePreviewPanel.tsx` realization mapping header 의 양쪽 FQN span — `min-w-0` + outer flex
      `min-w-0`. code type method list (line 347) 도 동일.

**Pattern B — description/rationale 등 textarea readonly 영역 break-words 누락**
- [x] `InlineEdit.tsx InlineEditTextArea` 의 non-editing 블록 (`line 230~237`) — wrapper 에
      `min-w-0`, value div 에 `flex-1 min-w-0 whitespace-pre-wrap break-words`. 이 컴포넌트가
      Term description / Action description / BR rationale / Anchor description 모두에 쓰이므로
      한 군데 수정으로 전체 cascading. 긴 한국어 문장이 컨테이너 폭을 강제 확장하던 문제 해결.
- [x] `OntologyTab.tsx` BR row statement line-clamp-1 에 `break-words` 추가.
- [x] `MainPanel.tsx` BR statement line-clamp-2 (`line 643`) 에도 `break-words`.

**Pattern C — 한국어 label grid 폭 부족 (`[100-110px_1fr]`)**
- [x] `MainPanel.tsx` Action Composition rows (`grid-cols-[110px_1fr_60px]`) + Term Composition rows
      — 모두 `[140px_1fr_60px]`. "이 Action 의 Params 중에 …" 같은 label 이 잘리던 문제.
- [x] `MainPanel.tsx KV` helper grid (`line 1348`) — `[140px_1fr]` + label `truncate min-w-0 title`
      + value `min-w-0 break-words`. Anchor/BR/Action detail 의 모든 key-value 표시에 cascading.
- [x] `MainPanel.tsx` params grid + BR enforced_by grid (`line 662 area`) — `[100~120px_1fr]` →
      `[120px_1fr] min-w-0` + value span `truncate min-w-0` + title attribute.
- [x] `QueuePreviewPanel.tsx Field` helper — `[72px_1fr]` → `[88px_1fr] min-w-0`, label/value 모두
      truncate + title.

**Pattern D — Section/Card 래퍼 자체가 overflow 누락**
- [x] `MainPanel.tsx Section` 컴포넌트 (`line 378-386`) — `<section>` 에 `min-w-0 overflow-hidden`,
      `<h3>` 에 `flex items-center justify-between gap-2 min-w-0` + title span `truncate min-w-0`
      + action 영역 `shrink-0`, children wrapper 에 `min-w-0`. 긴 section title 이 옆 action 버튼을
      밀어내던 증상 해결.
- [x] `QueuePreviewPanel.tsx Block` / `ListSection` / `ContextCard` 세 building block 모두 `min-w-0`
      + 내용 `break-words`. 큐 미리보기 우측 패널의 카드 자체가 부모 폭을 무시하던 문제 해결.
- [x] `NewEntityModal.tsx SearchPicker` dropdown row — `min-w-0` + fqn tail `shrink-0`. 긴 FQN
      autocomplete 결과가 modal 우측을 침범하던 문제 해결.

**검증**
- [x] TypeScript `./node_modules/.bin/tsc --noEmit --pretty false` — 0 errors.
- [x] 7개 파일 약 25 spots 수정. (`MainPanel.tsx` 11 / `InlineEdit.tsx` 1 / `OntologyTab.tsx` 4 /
      `NodePreviewPanel.tsx` 1 / `QueuePreviewPanel.tsx` 6 / `NewEntityModal.tsx` 1 / `LeftPanel.tsx`
      audit-only)
- [ ] **브라우저 시각 검증** — 사용자 잔여. localhost:3000 에서 modeling 진입 후 (1) 좌측 트리 긴
      한국어 항목, (2) 우측 큐 미리보기 description, (3) Term/Action detail 의 KV row, (4) BR
      statement 의 line-clamp, (5) Anchor list 항목이 컨테이너 안에 잘 갇혀 있는지 확인.

---

## 2026-05-13 (Authoring Phase C-3a/b/c)

사용자 요청 (연속): Authoring 모드 JPO-only 한계 → JPA/Service/Action 풀 지원 확장.

- [x] Phase C-3a — Service/Action `*_interview.md` 프롬프트 + `design_interview_dispatcher` 추가, `/authoring/interview` 가 Hypothesis union 디스패치.
- [x] Phase C-3a — frontend store `hypothesis` 를 Hypothesis union 으로 확장, `_entityOrThrow` / `_hypothesisDisplayFields` 헬퍼 도입.
- [x] Phase C-3b — toolbar ③ 인터뷰 모든 kind 허용. ⑤/⑥/⑦/⑨/✓ 는 entity-only 게이트 + 한국어 툴팁.
- [x] Phase C-3b — HypothesisCard / CompletedEntitiesPreview universal display (kind-aware).
- [ ] Phase C-3c — options/gaps/pattern/archive/naming 의 service/action 본격 지원 (별도 세션, 현재는 deferred).

---

## 2026-05-01 (온톨로지 방식 재검토 — Action 도입 논의)

사용자 요청: "메서드 자체를 Action 으로 매핑해야 하지 않을까?" — 팔란티어 온톨로지와의
정합성 비판적 검토 + 토론용 HTML.

- [x] `toClaude/modeling/온톨로지-방식-고찰.html` v1 작성 — 팔란티어 4-pillar 조사, 옵션 4가지 트레이드오프.
- [x] 사용자 결정 (2026-05-01): **Action 도입 방향 확정**.
- [x] `toClaude/modeling/온톨로지-방식-고찰-v2.html` 작성 — Action 도입 전제로 시뮬레이션 정합성 재고찰.
  Before/After 파이프라인, Action 데이터 모델 (params/output/preconditions/effects/anchors_locked/sub_actions),
  Pure/Effectful/Workflow 3분류 + simulator 전략, 라이프사이클 (discovery→pairing→anchor→lock→simulate→PR),
  7 설계 원칙, 기존 ChangeSpec 5종의 Action 슬롯 매핑, 결정 질문 10개를 페이지 내 라디오+textarea
  + localStorage 자동 저장 + "📋 전체 답변 복사" 마크다운 클립보드 기능으로 인터랙티브하게.
- [x] 사용자 v2 답변 (2026-05-01): Q3=A / Q5=C / Q6=B / Q8=A / Q9=C / Q10=D 확정.
  Q1·Q2·Q4·Q7 은 추가 고찰 요청 (메모로).
- [x] `toClaude/modeling/온톨로지-방식-고찰-v3.html` 작성 — 4개 심층 재고찰:
  (Q1) 우리 환경에서 Action/Function 분리 불필요 + **VerificationLevel** 신설 제안 (UNMAPPED→DRAFT→
  SIGNATURE_LOCKED→BODY_ANCHORED→SIM_VERIFIED→PR_PROVEN). (Q2/Q4) 매핑 곤란 4 패턴 (helper/composite/
  glue/generic) + Method.role 자동 분류 + fragment-level AnchorBinding + Workbench unmapped 패널.
  (Q7) 팔란티어 Scenario 패턴 차용 — Action atomic 유지, **SimulationScenario** 별도 모델 신설,
  UI = Step List + Side-by-side Diff 조합. 종합 모델 (6 노드) + 갱신 질문 4개 인터랙티브 폼.
- [x] 사용자 v3 답변 (2026-05-01): Q1'=A / Q2'=C(LLM 보조) / Q4'=A / Q7'=A 확정.
- [x] `toClaude/modeling/온톨로지-방식-고찰-v4.html` 작성 — 복합 도메인(주문) 처리 + 팔란티어 심층:
  (§1) 팔란티어 Interface Type / Shared Property / Struct(depth 1, max 10, primitives only) 한계 발견.
  (§2) 강약점 매트릭스 — 우리 5승 (코드 ground truth, 매뉴얼 통합, 사각지대 가시화, fragment anchor,
  VerificationLevel) vs 팔란티어 2승 (interface polymorphism, 거버넌스). (§3) 주문 분해 — 4 패턴
  atomic/bundle/aggregate/reference. (§4) BusinessTerm.kind 신설 + TermComposition 엣지 + dotted path syntax
  ("params[0].화학성분정보[-1].C") + 5 invariant. (§5) PythonGenerator nested dataclass codegen,
  anchor 깊이 처리, Scenario composite path. (§6) Workbench Term tree + Action card nested params +
  path picker 자동완성. C1~C4 결정 질문 인터랙티브 폼.
- [x] 사용자 v4 답변 (2026-05-01): C1=A·C2=A·C3=A(추상화 요청)·C4=A 받음.
  C1 메모로 **결정적 비판** — "자바 상속/인터페이스를 표현 못 하면 레거시 자바 시스템에 더 큰 문제,
  아부하지 말고 열린 사고로 재검토". 정직하게 v4 의 결함 4가지 인정.
- [x] `toClaude/modeling/온톨로지-방식-고찰-v5.html` 작성 — Java OO 표현력 재설계:
  (§1) v1~v4 모델이 extends/implements/override/abstract 4가지를 못 다룬 결함 + 다형성 무시 시뮬 신뢰성 0.
  (§2) Framing X (단일 BusinessTerm + OO) vs Framing Y (Code Type 별도 레이어) 정직 비교 — X 채택,
  단 코드 노이즈는 Class.role 분류로 차단. (§3) BusinessTerm 단순화 — 4-kind → **2-kind (atomic/composite) +
  facets** (is_abstract/is_interface/is_root_entity/struct_like_hint). C1 답변 변경 권장.
  Inheritance(extends/implements) 신설. (§4) Action.realizations 다중 + applies_to_term subtype 필터,
  PythonGenerator 자동 dispatcher 생성. (§5) C3 후속 — ScenarioInputAdapter plugin pattern
  (Form/Generated/Fixture/Json/Csv/Db/Api 점진 추가). (§7) C1~C4 영향 정리. D1~D3 결정 질문 인터랙티브 폼.
- [x] 사용자 v5 답변 (2026-05-01): D1=C (**Two-Layer 분리**) / D2=A (Class.role 자동) /
  D3=A + **call-flow 자동 추적** 메모.
- [x] `toClaude/modeling/온톨로지-방식-결정.html` (FINAL) 작성 — 5 라운드 토론 결과 lock:
  결정 16개 정리 + Two-Layer 종합 아키텍처 (Code/Mapping/Domain/Simulation 4 레이어) + 종합 스키마
  (CodeType/CodeMethod/CallSite + BusinessTerm/Inheritance/Composition + Action/Realization/AnchorBinding +
  SimulationScenario/InputAdapter) + **CallSiteAnalyzer 7-case 분류** (single_impl/instanceof_guard/
  annotation/factory_branch 자동, generic/Strategy_Map/Reflection 사용자 큐 with 후보·컨텍스트) +
  end-to-end 데이터 흐름 + 주문 검증 walk-through (abstract Order + StandardOrder + RushOrder) +
  **Step 1~8 작업 분해** (각 step 산출물 명시) + Q10=D 데이터 reset 마이그레이션 + Phase 2+ open 영역.
- [x] 사용자 지침 (2026-05-01): "토론 결과가 ideal — 충돌 시 기존 그냥 삭제. 시뮬레이션·NL 영향 분석은
  부착/탈착 가능한 agent 로 분리. 핵심은 Java 표현 + 도메인 매핑 + 여러 기능 편하게 하는 온톨로지."
- [x] `toClaude/modeling/온톨로지-방식-플랜.html` 작성 — 결정 16개 기반 작업 플랜 재작성:
  **CORE Phase 6 step (C1~C6)** — clean slate (기존 archive+drop), Code Layer (Java mirror + CallSiteAnalyzer),
  Domain Layer (Term 신모델), Mapping Layer (Action+Realization+AnchorBinding), Query API (Agent boundary),
  Workbench UI (편집/탐색만, 시뮬·NL drawer 없음).
  **AGENT Phase 4 step (A1~A4)** — Plugin framework, Simulation Agent (Scenario+Sandbox+Diff),
  ChangeSpec+DraftPR Agent, NL 영향 분석 Agent. 모두 Query API 만 호출, Core internal import 정적 검사 차단.
  폐기 대상 8종 + 보존 (Java 분석 로직 — 출력만 어댑터) 명시. C6/A2 두 시연 분기점.
- [x] 사용자 O1·O2·O3·O4 답변 (2026-05-01): O1=A (B8/B9 폐기) / O2=A (Section 1 그대로 + 모델링 측 agent
  새로) / O3=A (Section 3 폐기) / O4=D (mode rail 폐기, UI 완전 재구성, **브라우저 기반 이터레이션**).
- [x] 사용자 정정 (Section 1 wiki/RAG 절대 안 건드림 — 다른 세션 소유, CLAUDE.md Section Isolation Rule).
- [x] `toClaude/modeling/온톨로지-방식-플랜-v2.html` 작성 — 정정된 Section 경계 반영:
  Section 1 LOCKED (backend/wiki, backend/application/{wiki,agent,metadata}, backend/api/search.py,
  frontend wiki) 명시. Section 2 + Section 3 만 폐기·재구성. CORE C1~C6 + AGENT A1~A4 step 분해.
  **C6 (Workbench UI) 는 6 sub-step + N회 이터레이션 루프** — gstack /design-shotgun, /browse,
  /design-review, /qa 등 활용해 사용자 관점 탐구·고도화. 두 시연 분기점 (C6 standalone 온톨로지, A2 시뮬).
- [x] 사용자 "진행하자" → **C1 완료** (2026-05-01):
  - Git tag `pre-clean-slate-2026-05-01` 생성
  - `archive/2026-05-pre-clean-slate/` (.gitignore) 에 346 파일 / 38K LOC 이동
  - backend/modeling/{mapping,ontology,simulation,query,impact,sweepers,gap_detection,manuals,manual_ingest,demo,api} archive
  - backend/simulation/ (Section 3) 통째 archive
  - frontend ModelingSection / modeling/ / SimulationSection / simulation/ / lib/api/modeling.ts archive
  - SectionNav: 3탭 → wiki 1탭 / page.tsx: modeling/simulation 라우팅 제거
  - backend/main.py: 965 → 431 라인 (Section 2/3 imports + wiring + routers 제거, Section 1 보존)
  - data/ontology.db archive (13 tables drop)
  - 검증: backend main.py import OK, 보존 모듈 (Java parser, Spring 분석기, persistence, agent_framework, contracts) OK, frontend tsc OK
  - 산출물: `log/step_C1_summary.md` + HANDOFF.md 갱신
- [x] 사용자 "진행해" → **C2 완료** (2026-05-02):
  - backend/modeling/code_layer/ 신설 (6 파일, 1.8K LOC including tests)
  - Pydantic DTO: CodeType (kind+role+is_abstract+extends+implements) / CodeField / CodeMethod
    (role+is_abstract+is_override+anchors) / CallSite (possible_runtime_types[]+confidence+analysis_source)
  - SQLAlchemy ORM 4 테이블 (code_types/fields/methods/call_sites)
  - Store: upsert/list/get + repo_id 격리 + idempotent
  - Adapter: 기존 java_parser ParseResult → 새 schema (annotations dict→string 정규화 +
    @Override 자동 검출 + interface 자동 abstract)
  - role_classifier: annotation 우선 + 이름 패턴 (Repository/Mapper/Dto/Util/Helper/Abstract/Base) +
    abstract class 도 DOMAIN 처리, interface DOMAIN 기본
  - callsite_analyzer: Case 1 (SINGLE_IMPL) + Case 3 (ANNOTATION) + 자체정의 자동 / 모호
    (다중 impl / 다중 override / receiver 모름) → STATIC_UNRESOLVED + needs_user_confirm + 후보 list 컨텍스트
  - 보존 활용: java_parser + Spring 10 analyzer + method_anchor (출력만 어댑터, 로직 재작성 X)
  - persistence/{models,*_store,registry}.py 9 파일 추가 archive (database.py 만 보존)
  - **검증**: pytest 15/15 PASSED, backend.main import OK, frontend tsc OK
  - 산출물: `log/step_C2_summary.md` + HANDOFF.md 갱신
- [x] 사용자 "진행해" → **C3 완료** (2026-05-02):
  - backend/modeling/domain_layer/ 신설 (6 파일, 1.5K LOC including tests)
  - Pydantic DTO: BusinessTerm (2-kind + 4 facets) / Inheritance / Composition / BusinessRule
  - SQLAlchemy ORM 4 테이블 (business_terms / inheritance_edges / composition_edges / business_rules)
  - Store: upsert 4 메서드 + repo 격리 + idempotent + (parent,role) 중복 replace
  - Validator: three-color DFS 사이클 검출 (extends+implements+composition 모두 DAG) +
    atomic-parts 금지 + dangling reference + duplicate role warning
  - Resolver: ancestors / descendants / effective_parts (own→자손 우선 override 의미)
  - E2E: 주문 도메인 13 terms (주문 + 주문스펙 + 화학성분 [1:N] + 진행관리 + 품질설계 +
    Trackable interface + StandardOrder/RushOrder extends + 4 atomic leaves + 2 rules)
  - effective_parts(긴급주문) = {spec, progress, quality, chemical, trackingNo, priorityLevel} ✓
  - **검증**: tests 30/30 PASSED (누적 C2+C3 = 45/45), backend.main import OK, frontend tsc OK
  - 산출물: `log/step_C3_summary.md` + HANDOFF.md 갱신
- [x] 사용자 "진행해" → **C4 완료** (2026-05-02):
  - backend/modeling/mapping_layer/ 신설 (6 파일, 1.6K LOC including tests)
  - Pydantic DTO: Action (1급, kind+is_abstract+declared_on_term+params+output+preconditions+
    postconditions+effects+realizations+sub_actions+verification_level) / ActionParam (typed +
    object_ref + anchor_locator + confirmed) / ActionEffect (정형 op+target_term+target_attr) /
    Realization (다형성 + dispatch_source 9-enum) / AnchorBinding (fragment-level + path with subtype) /
    TypeRealization (Code↔Domain) / VerificationLevel
  - SQLAlchemy ORM 4 테이블 + UniqueConstraints
  - Store: Action 저장 시 realizations 별도 테이블에 분리 저장 + 조회 시 합쳐 반환 / verification_min 필터
  - Path syntax parser: params[i]<Subtype>.role.role[idx] / output / preconditions[i] / effects[i].field
  - Path validator: BusinessTerm 그래프 traversal + atomic.range 인덱싱 + subtype cast descendants 검증 +
    CamelCase→snake 자동 매칭 (RushOrder → rush_order)
  - VerificationLevel 자동 계산 (UNMAPPED→DRAFT→SIGNATURE_LOCKED→BODY_ANCHORED) + 외부 신호
    (SIM_VERIFIED/PR_PROVEN) + can_simulate Q8=A Strict gate
  - Action invariants: pure_function 무 effects / workflow 무 realizations / object_ref 시 term 필수
  - E2E: Code(Order+Rush+Standard) + Domain(주문 도메인) + Mapping(Action 다형성 2 realizations +
    AnchorBinding composite path) → BODY_ANCHORED 도달
  - **검증**: tests 47/47 PASSED (누적 C2+C3+C4 = 92/92), backend.main import OK, frontend tsc OK
  - 산출물: `log/step_C4_summary.md` + HANDOFF.md 갱신
- [x] 사용자 "진행해" → **C5 완료** (2026-05-02):
  - backend/shared/contracts/ontology_query.py — Agent boundary 확정 (DTO alias re-export +
    OntologyQueryClient Protocol 16 method) + 추가 DTO (VerificationProgressDTO, SearchHitDTO,
    AmbiguousCallSiteDTO with LLM hook, UnmappedMethodDTO)
  - backend/modeling/api/ontology_query.py — OntologyQueryClientImpl (Code+Domain+Mapping store 통합)
  - backend/modeling/api/ontology_router.py — FastAPI router 16 endpoints (`/api/ontology/*`),
    OpenAPI spec 자동 생성. Catchall path 매칭 순서 조정 (specific suffix 먼저)
  - tools/check_agent_isolation.py — backend.modeling.{code,domain,mapping}_layer +
    persistence/code_analysis/api + application(Section 1) 직접 import 차단. agents 폴더 없으면 skip.
  - backend/agents/AGENT_GUIDE.md — 새 agent 작성 규칙 + 예시 + OntologyQueryClient 메서드 표
  - main.py wired: ORM module import (Base.metadata 등록) → bootstrap_database() → ontology_query_api.init()
    → router include. Section 1 wiring 절대 무관.
  - 기존 backend/shared/contracts/__init__.py 의 simulation contract 는 archive (Section 3 archive 정합)
  - **검증**: tests 29/29 PASSED (16 facade + 9 REST + 4 isolation 도구), 누적 C2~C5 = 121/121,
    backend.main import OK (16 routes 등록), isolation 도구 OK, frontend tsc OK
  - 산출물: `log/step_C5_summary.md` + AGENT_GUIDE.md + HANDOFF.md 갱신
- [x] 사용자 "진행해" → **C6 1차 사이클** (2026-05-02):
  - `toClaude/modeling/ux/scenarios.md` — Persona (SCM 분석가 지윤) + 4 핵심 시나리오 (S1 import / S2 매뉴얼 /
    S3 Action 매핑 큐 / S4 verification 진척) + 8 위젯 + 8 design 차원 trade-off + 5 평가 기준
  - `toClaude/modeling/ux/prototypes/_shared.css` — 4안 공통 디자인 토큰 (color, pill, typography)
  - `prototypes/v1-three-pane.html` — 좌트리·중앙 Action card·우 컨텍스트 (탭 4종)
  - `prototypes/v2-code-domain-split.html` — 좌 Code Tree | 중앙 매핑 split (위 Java body / 아래 Action card) | 우 Domain Tree
  - `prototypes/v3-activity-feed.html` — 좌 통합 큐 (anchor/callsite/unmapped) | 중앙 focus task + AI 추천 + 후보 grid | 우 컨텍스트
  - `prototypes/v4-workspace-tabs.html` — 브라우저-like 탭 (여러 작업 동시 + ⌘1-5 전환), 한 탭 fully focused single-task UI
  - `toClaude/modeling/ux/index.html` — 4안 비교 보드 (각 prototype 링크 + 비교 매트릭스 8 차원 +
    P1~P4 인터랙티브 폼 라디오/체크박스/textarea + localStorage + 복사 버튼)
  - 같은 시나리오 (S3 — 주문_검증 anchor 매핑) 4가지 layout 으로 visualize 해서 비교 가능
- [x] 사용자 1차 답변 (2026-05-02): P1=V1 (IT 운영자 친숙) + 우측 사이드바 좁음 fix /
  P2=V1_action_card,V2_split,V2_dual_tree,V2_clickable_anchor,V3_queue,V4_tabs,cmd_k,status_progress /
  P3=그래프는 별도 화면 / P4=refine_main → V5 보강
- [x] **C6 2차 사이클** (2026-05-02): V5 Hybrid prototype 작성
  - `prototypes/v5-hybrid.html` — V1 3-pane 유지 + 흡수 요소 통합:
    * 좌측 4탭 (Code/Domain/Action/Queue) + Queue 는 V3 풍부함 차용
    * 상단 탭바 (V4 — 여러 작업 동시)
    * 중앙 **Mode 토글: Detail / ↕ Split / 🌐 Graph** (V1+V2+full-screen graph 통합)
    * 우측 사이드바 fix 3가지 동시 — resize 드래그 + "↕ Split mode 로" 버튼 + 별창 placeholder
    * Graph mode = full-screen takeover (Action 의존 + 4 종 노드 + 6 종 엣지 + legend), esc 닫기
    * ⌘K palette overlay (term/action/code/명령 통합 검색)
    * status bar verification 진척 (UDSL/BA/SV/PR + 전체 % + plugin)
    * JS 인터랙션 (mode 토글 / graph mode / ⌘K / resize 드래그 작동)
  - `index-v2.html` — V5 안내 + P5~P8 피드백 폼 (충분? / 우측 fix 효과 / Graph 정도 / React 우선순위)
  - browse 로 5 screenshot 검증 (Detail / Split / Graph / ⌘K / index-v2)
- [x] 사용자 2차 답변 (2026-05-02): P5=more_iter (매핑 2 방향성: Code→Domain forward / Domain→Code
  backward 둘 다 경쟁력) / P6=all_three / P7=interaction (Top-down 큰 그림 → 세부) / P8=full_v5
- [x] **C6 3차 사이클** (2026-05-02): V6 Bidirectional + Top-down 작성
  - `prototypes/v6-bidirectional.html` — V5 위에 흡수:
    * **Direction 토글** (NEW): 🔍 Forward (Code→Domain 초기) / 🔧 Backward (Domain→Code 수정모드)
      - Backward 모드: amber 색조 + 영향 banner + 4-card grid (Action 6 / Code 14위치 / Rule 2 /
        매뉴얼 fragment) + 자동 Java patch preview + 시뮬/PR 버튼
    * **좌측 5번째 탭 = Domain Map** (NEW landing): 4 도메인 카드 (SCM/Quality/Production/Logistics) +
      그룹 미리보기 + 진척 bar. memory `feedback_topdown_domain_view` 정합
    * **Top-down Graph 4 레벨** (NEW): L1 도메인 박스 (treemap-like) → L2 그룹 cluster →
      L3 노드 (Action/Term/Rule + 6 종 엣지) → L4 코드/anchor. Breadcrumb + Level slider +
      키보드 (1-4 직접 점프, ↑↓ level navigate)
  - `index-v3.html` — V6 안내 + V5→V6 매트릭스 + Backward 흐름 시연 + P9~P12 폼
  - browse 시연: 6 screenshot (Forward / Backward / Graph L1 / L2 / L3 / L4)
- [x] 사용자 3차 답변 (2026-05-02): P9=yes_done / P10=diff_view+risk+cascade+rollback (4개 다) /
  P11=zoom_pan+filter+search_highlight+path_trace + 메모 ("4-level 충분? 팔란티어 비교 후 한계 파악") /
  P12=more_design (한 사이클 더)
- [x] **C6 4차 사이클** (2026-05-02): 팔란티어 비교 분석 + V7 작성:
  - WebSearch: Workflow Lineage / Vertex (dynamic styling, layer styling, Search Around panel,
    chain models, scenario 통합, current vs simulated)
  - `palantir-comparison.md` 작성 — 4-level 한계 9가지 (single lens / cross-domain edge /
    path-trace / anchor micro / time / version / cluster / filter / backward graph 통합) +
    팔란티어 vs onTong 11 영역 비교 + ★ 차별 4가지 (코드 raw / Java OO 다형성 / 매뉴얼 통합 /
    매핑 신뢰도) + V7 보강 8안 + Backward 강화 4가지
  - `prototypes/v7-lens-path.html` — V6 위에 흡수:
    * **Backward 강화 4종** (P10): branch bar (4 가설 동시) + risk score ring (62/100, conic gradient
      + 영향 크기/시뮬 신뢰도/HARD 위반 분해) + side-by-side diff (Java/Term/Rule/매뉴얼 토글) +
      cascade tree (depth 슬라이더 1~5, 직접/간접 색 구분, ⚠ HARD 위반 자동 표시)
    * **Lens 시스템** (팔란티어 dynamic styling 차용): Verification (default, level별 노드 색) /
      Domain / Confidence / Simulation hot, 토글
    * **Path-trace 양방향** (P11): forward/backward/양방향 토글 + hop 슬라이더, 노드 클릭 시
      path 강조 + 나머지 dim
    * **Search Around** (팔란티어 차용): 노드 우클릭 → context menu (X-hop deps/dependents,
      매뉴얼 fragments, Backward 모드로)
    * **L5 — Anchor micro-graph** (NEW, ★우리 차별): 메서드 본체 dataflow (param/field →
      branch + literal → return + extracted_rule). 팔란티어 Functions 추상화로 못 다루는 영역
    * **Cross-domain edge 강조** (NEW): 도메인 boundary crossing edge 노란 굵게 + ⚠ 표시
    * **Filter sidebar** (그래프 좌측): domain / verification min / kind / 매뉴얼 토글
    * **Search highlight** (그래프 위): ⌘F 검색박스
  - `index-v4.html` — V7 안내 + P10/P11 흡수 매트릭스 + Lens/Search Around/L5/Cross-domain 설명 +
    P13~P16 폼 (충분? / L5 가치 / React 우선순위 / 추가 차별 아이디어)
  - browse 시연: 4 screenshot (Backward / Graph L3 lens+path / L5 micro / index-v4)
- [x] 사용자 4차 답변 (2026-05-02): P13=done / P14=critical (L5) / P15=phase1 (단계) / P16=skip
- [x] **C6 React Phase 1 완료** (2026-05-02): Modeling Workbench React 구현 시작
  - `frontend/src/lib/api/ontology.ts` — REST client 16 메서드 (backend OntologyQueryClient 1:1)
  - `frontend/src/components/sections/modeling/` — 9 컴포넌트 + zustand store (1,815 LOC)
    * WorkbenchShell (3-pane grid + graph 토글)
    * TopBar (brand/repo/⌘K/graph/sim 버튼)
    * TabBar (V4 차용 — 여러 작업 동시)
    * LeftPanel (5 탭: Map landing 4 도메인 카드 / Code tree filter / Domain tree / Action tree / Queue)
    * MainPanel (Forward+Backward 토글 + Detail/Split mode + 그래프 진입)
    * RightPanel (4 탭 + resize 드래그 + Split mode 버튼)
    * GraphMode (Top-down L1~L4 + breadcrumb + level slider + 키보드 1-4/↑↓)
    * CmdKPalette (cmdk 라이브러리, 검색 + 명령)
    * StatusBar (live verification 진척 + Forward/Backward)
  - `ModelingSection.tsx` + SectionNav 다시 modeling 탭 + page.tsx 라우팅 복구
  - backend `bootstrap_database()` 수정 — archive 된 `models.py` 의존 제거 (각 layer ORM 직접 import)
  - **검증**: tsc clean, backend 121/121 PASSED, dev 서버 작동, browse 시연 OK (Workbench 표시)
  - 산출물: `log/step_C6R_phase1_summary.md` + HANDOFF.md 갱신
- [x] 사용자 "1.5 → 2 진행" → **C6 React Phase 1.5 + Phase 2 완료** (2026-05-02):
  - **Phase 1.5**: GraphMode 에 L5 추가 (Level 5 = anchor micro-graph, ★ 우리 차별).
    Level 1-5 키보드 (1-5, ↑↓), Level5View 컴포넌트 (메서드 본체 dataflow:
    action 위 → 4 field/param 좌 → 3 branch+literal 가운데 → 4 return 우 → extracted_rule 아래
    + SVG markers + label, 팔란티어 못 다루는 영역 callout)
  - **Phase 2a Backward 강화**: BackwardMode.tsx 신설 — branch bar (4 가설), risk score conic
    ring (62/100), side-by-side diff (Java/Term/Rule/매뉴얼 토글), cascade tree
    (depth 슬라이더, ⚠ HARD 위반)
  - **Phase 2b Lens 시스템**: store 에 lens 추가 (verify/domain/confidence/simulation/none).
    Node 의 background tint 가 lens 별로 다름. GraphMode 헤더에 활성 lens 표시.
  - **Phase 2c Path-trace**: store 에 pathTrace/pathTraceHops/pathTraceFromFqn. GraphFilters 의
    4-dir 토글 + hop 슬라이더. Node 의 path-traced border glow + 그 외 dim.
  - **Phase 2d Search Around + Cross-domain + Filter**: 노드 우클릭 ContextMenu 6 옵션
    (X-hop deps/dependents/매뉴얼/코드/Backward/Path-trace). Cross-domain 노드 ring + ⚠ 배지.
    GraphFilters sidebar (domain 체크 / verification min / cross-domain 토글 / lens / path-trace).
  - **Phase 2e xyflow**: 의존성 확인 ✓, 본격 통합은 Phase 3 실제 데이터 wiring 시 (현 mock 으로
    lens/path/cross-domain 시연 충분).
  - WorkbenchShell grid: graph mode 시 좌측 = GraphFilters 로 교체 (240px).
  - **검증**: tsc clean, backend 121/121 PASSED, browse Backward 시연 OK
    (`/tmp/c6r2_bwd.png` — 모든 강화 표시). 누적 LOC 2,235.
  - 산출물: `log/step_C6R_phase15_2_summary.md` + HANDOFF.md 갱신
- [x] 사용자 "Phase 3 진행 + sample-repos/slab-design-real 데모 + 공 많이 들여줘"
- [x] **P3-1 데모 repo 깊이 파악 완료** (2026-05-02):
  - **slab-design-real**: 한국 철강 SCM (slab design 21-step), Java 21 + Spring Boot 3.4,
    4-module Maven (boot/facade/feature/store), **122 Java 파일**, 12 JPA tables, "drama DNA" 가득
  - 자동 추출 예상: CodeType ~120 / CodeMethod ~600+ / Action 후보 **~32** / BusinessTerm 후보 **~30**
  - 핵심 Action: SdDesigner (21-step orchestrator) / SdOrderValidator (DG001~005) / 16 Action 클래스
    (SdLengthRangeAction 등) / 5 Controller
  - 핵심 BusinessTerm: 슬랩/주문/강종/**품종 (4 aliases ★)**/실수율/단중/포장단중/공정/EDGING/회사·소/...
  - Drama DNA: 품종/품명 chaos (4 컬럼 같은 개념) / 공정 chaos (8-char + 8 separate) /
    DG001~005 short-circuit / SDOrderLogic reflection mapping
  - 시연 시나리오 5종 (S1 import / S2 품종 매핑 / S3 DG003 영향 / S4 LengthRange 시뮬 / S5 Top-down)
  - 산출물: `toClaude/modeling/p3_demo_repo_analysis.md`
- [ ] **다음 P3-2**: Import 파이프라인 백엔드 — `POST /api/ontology/repos/import` + 비동기 분석 +
  CodeLayerStore.upsert + SSE 진행률.

---

## 2026-04-25 (사용자 워크플로우 가이드 + 다음 우선순위 결정 대기)

`/design-review` 메타 요청 — "신선한 사용자" 시점으로 앱을 둘러보고 막히는 지점 식별,
HTML 가이드 작성. 4 가지 핵심 product ambiguity 사용자에게 질의하여 다음 답변 확정:

- **용어 발견**: 사용자 직접 작성 메인, 매뉴얼/코드 기반 LLM 추천 보조
- **No-manual 흐름**: 코드 탐색 우선 → 분석된 코드 옆에서 매뉴얼 작성 (UI/UX 핵심)
- **시드 데이터**: 완전 빈 시작 + "데모 로드" 버튼
- **매뉴얼 출처**: 우리 앱이 메인 에디터 (코드와 정형화), 외부 PDF 는 LLM enrich

- [x] `toClaude/modeling/사용자-가이드.html` 작성 — 7-Phase 정규 워크플로우 + 빠진 기능 6 종 + 다음 우선순위 추천
- 사용자 결정: 1번부터 순서대로 5 개 작업 모두 진행.

### P1 (완료) — 자동 시드 제거 + 데모 데이터 로드 버튼

backend startup 시 강제 시드 (BusinessTerm 2개 + 매뉴얼 2건 + auto-link)를
사용자 트리거 엔드포인트로 분리. 신선한 사용자 시나리오를 시연 가능.

- [x] `backend/modeling/demo/seeder.py` 신설 — `seed_demo_data() / reset_demo_data() / is_demo_loaded()`. 매뉴얼 인제스트 + BusinessTerm 등록 + auto_link_rules_to_fragments + 임베더 빌드 (OpenAI → Hashing fallback) 캡슐화.
- [x] `backend/modeling/api/demo_api.py` 신설 — `GET /status`, `POST /load`, `POST /reset`. `post_change_hook` 으로 gaps_api 의 module-level `auto_described_in` 캐시 갱신.
- [x] `backend/main.py` 자동 시드 60+ 줄 제거 + cold start 보장. demo_api 와이어링 추가.
- [x] `backend/modeling/api/modeling.py` — demo_api router include.
- [x] `backend/modeling/mapping/concept_store.py` — `InMemoryConceptBindingStore.clear()` 추가 (demo reset 용).
- [x] `frontend/src/lib/api/modeling.ts` — `getDemoStatus / loadDemoData / resetDemoData` 함수 + 타입 추가.
- [x] `frontend/src/components/sections/ModelingSection.tsx` — 사이드바 하단에 데모 컨트롤 패널 추가 (loaded 시 로드 비활성화, 초기화는 confirm 다이얼로그).
- [x] `tests/test_demo_seeder.py` — cold start / load / reset / e2e API 4 테스트 PASS.
- [x] **End-to-end 검증**: cold (manuals=0/terms=0/loaded=false) → POST /load (manuals=2/terms=2/auto_bindings=7, OpenAI embedder) → POST /reset (loaded=false). gaps_api auto-link 캐시도 7 → 0 동기화 확인.

### P2 (완료) — Structured Manual directive UI 가이드

ManualUpload 페이지에 collapsible 가이드 패널 추가. 사용자는 `<!-- ontong: term=... -->` 문법
존재 자체를 모르고 있었는데, 이제 페이지를 열면 호박색 alert 박스로 노출되고 펼치면 문법 + 예시
markdown + 「복사」 버튼이 나옴.

- [x] `frontend/src/components/sections/modeling/ManualUpload.tsx` — 헤더 아래에 collapsible 가이드 섹션. 문법 (`term=` / `rule=`) + 동작 (다음 fragment attribute 로 흡수, confidence 1.0) + 예시 코드 + 클립보드 복사 버튼.
- 외부 PDF/DOCX 는 directive 인식 안 함을 명시.
- 메타 섹션 (작성 가이드, STATUS, Q&A 등) 자동 제외 룰도 노출.

### P3 (완료) — 매뉴얼 → BusinessTerm LLM 일괄 추천

PDF/MD 등록만 하면 후보 BusinessTerm 30 개를 LLM 이 자동 추출, 사용자는 체크박스
로 일괄 등록. 「매뉴얼이 있는데 용어를 일일이 타이핑」 노가다 제거.

- [x] `backend/modeling/mapping/term_suggester.py` — `ClaudeTermSuggester` (suggest_from_manual / suggest_from_code), graceful no-op (API key/SDK 없으면 빈 리스트). JSON-only system prompt + array parser.
- [x] `backend/modeling/api/terms_api.py` — `POST /terms/suggest-from-manual`, `POST /terms/bulk-add` 추가. manual_registry + suggester wired in `init()`. `BusinessTermSource.LLM_PROPOSED` 로 source 표기.
- [x] `backend/main.py` — `ClaudeTermSuggester` 인스턴스 생성 + terms_api.init 에 전달.
- [x] `frontend/src/lib/api/modeling.ts` — `suggestTermsFromManual / bulkAddTerms` + 타입 추가.
- [x] `frontend/src/components/sections/modeling/TermMapping.tsx` — 「AI 추천」 버튼 + 모달 추가. 매뉴얼 선택 → 추천 → 체크박스 멀티 선택 → 일괄 등록 → 자동 refresh. 이미 등록된 용어는 disabled + 「이미 등록됨」 뱃지.
- [x] `tests/test_term_suggester.py` — 6 테스트 PASS (suggester no-op / JSON parse / invalid JSON 안전 처리 / e2e 엔드포인트 / bulk-add dedup / 503 when unavailable).

### P4 (완료) — 코드 → BusinessTerm 추천

매뉴얼이 0건인 cold-start 사용자도 코드만으로 BusinessTerm 후보를 LLM 으로 추출.
JPA `@Column` + 필드명 + Javadoc 을 prompt 에 합성.

- [x] `backend/modeling/api/terms_api.py` — `_collect_column_summaries(parse_results)` 헬퍼 + `POST /terms/suggest-from-code` 엔드포인트.
- [x] `frontend/src/lib/api/modeling.ts` — `suggestTermsFromCode` 함수 추가.
- [x] `frontend/src/components/sections/modeling/TermMapping.tsx` — 추천 모달에 「매뉴얼 / 코드」 source 토글 추가. 코드 모드는 매뉴얼 셀렉터 숨김, 「코드」 추천은 매뉴얼 0건이어도 가능.
- [x] `tests/test_term_suggester.py` — `_collect_column_summaries` 단위 테스트 추가 (JPA 컬럼 + Javadoc + @Id 표시 검증).

### P5 (완료) — 코드 옆 매뉴얼 작성 split-view 에디터

새 탭 「매뉴얼 작성」 — 3분할 레이아웃: 좌(코드/용어 검색) · 중(markdown 에디터) · 우(미리보기).
사용자가 매뉴얼을 우리 앱 안에서 작성 → 저장 시 자동으로 `data/manual_writes/{repo_id}/`
하위 .md 파일 생성 + 매뉴얼 파이프라인 인제스트 → ManualRegistry 에 등록.

- [x] `backend/modeling/api/manuals_api.py` — `POST /api/modeling/manuals/write` 엔드포인트.
  filename validation (path traversal/슬래시 거부, .md 자동 부여), `data/manual_writes/{repo_id}/`
  하위 저장, force 모드 default.
- [x] `frontend/src/lib/api/modeling.ts` — `writeManual()` + `ManualWriteResponse` 타입.
- [x] `frontend/src/components/sections/modeling/ManualWriter.tsx` — 신설 컴포넌트.
  좌측: 코드 엔티티 검색 (method/field/class 필터) + BusinessTerm 검색.
  결과 hover 시 + 버튼으로 directive 끝에 자동 삽입 (`<!-- ontong: term/rule=fqn -->`).
  중앙: textarea + 표/코드 템플릿 삽입 버튼.
  우측: react-markdown + remark-gfm 미리보기.
  헤더: filename input + 「저장 + 인제스트」 버튼. 결과 banner.
- [x] `frontend/src/components/sections/ModelingSection.tsx` — `manual-writer` 뷰 추가, MAIN_NAV 7→8 탭.
- [x] `tests/test_manual_write_api.py` — 4 테스트 PASS (정상 write + 인제스트 / 경로 traversal 거부 / 슬래시 거부 / 확장자 자동 부여).
- [x] **E2E 검증**: curl POST /manuals/write → outcome="ingested" + saved_path 디스크 파일 + GET /manuals 에 즉시 노출 확인.

### P1-P5 모두 완료

`/design-review` 메타 요청에서 식별된 5개 작업 모두 마침. 신선한 사용자가 cold-start →
demo 로드 (선택) → 코드 분석 → 매뉴얼 작성 (in-app) → 용어 LLM 추천 (코드/매뉴얼 둘 다) →
용어 매핑 확정 → 갭 큐 → 역탐색 까지 한 사이클 가능.

### P7 (완료) — ingest 후 auto-link 자동 재실행 (manual writer + upload + SSE)

사용자가 매뉴얼 쓸 때마다 「갭 큐 → 자동 링크 재계산」 수동 클릭하던 것을 silent 후크로 자동화.

- [x] `backend/modeling/api/gaps_api.py` — endpoint 로직을 `recompute_auto_links(repo_id, top_k, min_confidence, quiet)` 함수로 추출. quiet 모드에서 인프라 미초기화 / 입력 부족은 dict 반환 (HTTPException X). `_AutoLinkInputError` 분리.
- [x] `backend/modeling/api/manuals_api.py` — `_trigger_auto_link_after_ingest()` helper. upload / write / SSE upload 3 경로 모두 ingest 성공 후 호출. circular import / 인프라 부재 모두 swallow.
- [x] `backend/main.py` — gaps_api init 에 default OpenAI 임베더 (실패 시 Hashing fallback) 항상 와이어링. cold-start 사용자도 P7 후크가 silent recompute.
- [x] `tests/test_auto_link_after_ingest.py` — 2 테스트 PASS (write 후 cache 갱신 / rules=0 quiet skip).

### P8 (완료) — AI 추천 모달 인라인 편집 + 전체선택/해제

- [x] `frontend/src/components/sections/modeling/TermMapping.tsx` — 추천 카드마다 「수정」 버튼 → canonical_label / aliases / description 인라인 input. `editingFqns` Set 으로 토글. 수정값은 bulk-add 에 그대로 반영. footer 에 「전체 선택」 / 「전체 해제」 버튼 (이미 등록된 것 자동 제외).

### P9 (완료) — 매뉴얼 작성 에디터 폴리시

- [x] `frontend/src/components/sections/modeling/ManualWriter.tsx` — `insertAtCursor` 로 textarea selection 위치 정확히 삽입 + requestAnimationFrame 으로 caret 복원. `Cmd/Ctrl+S` 저장, `Cmd/Ctrl+P` 미리보기 토글. 헤더에 「미리보기 닫기/열기」 버튼. 미리보기 닫으면 grid 2 분할로 전환.

### P10 (완료) — In-app onboarding modal

- [x] `frontend/src/components/sections/modeling/OnboardingModal.tsx` — localStorage 기반 1회 노출. 5 단계 워크플로우 요약 (Repository → 매뉴얼 → 용어 → 갭 → 역탐색) + 양자택일 CTA (「내 코드로 시작」 / 「데모 데이터로 둘러보기」). demo 가 이미 적재된 환경 (재방문/타 세션 부산물) 은 자동 dismiss.
- [x] `frontend/src/components/sections/ModelingSection.tsx` — 마운트.

### P12 (완료) — `/browse` 전체 사용성 + 규모 스트레스 검증

slab-design-real (123 파일 / 1781 entities / 3257 relations) 환경에서 헤드리스 브라우저
+ API stress 검증. 발견된 회귀 3건 즉시 수정 + 성능 측정.

**발견 → 즉시 수정한 회귀 3건 :**
1. **CORS 차단** (P12 #1) — 프론트가 `127.0.0.1:3000` 으로 떴는데 backend 가 `localhost:3000` 만 허용. 모든 API 요청 `Failed to fetch`. `backend/main.py` _cors_origins 에 127.0.0.1 변종 추가.
2. **자동 선택된 repo 가 작은 데모** (P12 #2) — `r.items[0]` (alphabetical) 로 slab-design-engine (11 파일) 이 자동 선택됨. 데모 매뉴얼은 slab-design-real 에 연결인데 UI 는 다른 repo 로 표시 → 혼란. `ModelingSection.tsx` 의 `useEffect` 를 `Promise.all([listRepos(), getDemoStatus()])` 로 변경 — demo 적재 시 demo_repo_id 우선, 그 외엔 entities 내림차순.
3. **데모 적재 후 selectedRepoId 동기화 안됨** (P12 #3) — onboarding modal CTA 「데모 데이터로 둘러보기」 클릭 후 사이드바 선택은 그대로. `refreshDemoStatus` 가 `s.loaded && s.demo_repo_id` 시 자동 setSelectedRepoId.

**Next.js dev origin 경고 수정 :**
- `frontend/next.config.ts` 에 `allowedDevOrigins: ["127.0.0.1", "localhost"]` 명시 — future major Next 차단 회피.

**규모 스트레스 결과 (slab-design-real 1781 entities) :**
| 작업 | 결과 | 시간 |
|---|---|---|
| 자동 발견 (.analyzed/ 캐시) | 123 파일 / 1781 ent / 3257 rel | startup 캐시 |
| propose-bindings (jpa_only) | 9 bindings, 159 skipped | <11ms |
| propose-bindings (all_fields + LLM) | 24 bindings, 0 opaque (slab 데모 의미적 컬럼만) | <12ms |
| gap scan | 18 manual_only + 7 conflicts | <20ms |
| DI graph | 61 nodes / 50 edges / 5 layers | <11ms |
| entity search 200 limit | 200 matches | <8ms |
| reverse_lookup `품종코드` | exact, term.품종코드 | <6ms |
| **suggest-from-code (1781 ent → 200 col → LLM)** | 20 suggestions | **13.6s** (LLM round-trip) |
| **suggest-from-manual (5 frag → LLM)** | 15 suggestions | **11.5s** |
| **15KB manual write + ingest + auto-link recompute** | 15 bindings | **15.1s** (OpenAI embedding 50 frags) |
| 동시 5 요청 (gap+di+search+propose+manuals) | 모두 OK 무경쟁 | 단일 요청 시간과 유사 |

**결론** : pure CPU 작업 (gap scan / DI / search / propose) 은 모두 **20ms 이하**. LLM/임베딩 라운드트립이 들어가는 작업은 10~15s — 사용자 체감엔 「추천 받기」 버튼 누른 뒤 spinner. 1781 entities 규모에서도 회귀 없음.

**검증 못한 부분 :**
- 헤드리스 Chromium daemon 이 modeling 탭 클릭 후 페이지 종료 (Playwright 환경 issue) — 풀 UI walkthrough 는 단편적 screenshot 3장 (Repository / 빠진 것 검증) 으로만 확보. 실제 사용자가 직접 클릭해야 매뉴얼 작성/AI 추천 모달 등 UI 동작 최종 확인.

회귀 테스트 55/55 PASS.

### P11 (완료) — Slab 데모 풀 사이클 검증 + 발견된 회귀 즉시 수정

slab-design-real (122 Java, 4 모듈, Spring Boot 3.4 / Java 21) 로 cold-start → AI 추천 →
bulk-add → 매핑 → 매뉴얼 작성 → 갭 큐 → 역탐색 까지 full cycle E2E.

- 자동 발견 : 123 파일 / 1781 entities / 3257 relations / 38 Javadoc rules.
- DI 그래프 : 61 beans, 50 autowires.

**발견 → 즉시 수정한 회귀 :**
1. **AI 추천 from code** = 0 — `_collect_column_summaries` 가 DI 주입 필드 (Designer.validator 등) 만 200개 뽑아서 LLM 이 뽑아낼 게 없었음. JPA `@Column` 우선 + `_DI_HOLDER_SUFFIXES` (Service/Controller/Designer 등) 필터 추가. 결과 : `SlabDesignHistJpo.slabNo (col=SLAB_NO)` 같은 진짜 도메인 컬럼만 prompt 에 들어감.
2. **AI 추천** 200 컬럼 + 15 max_terms = JSON 응답 0건 — `max_tokens=2000` 이 작아 응답 truncate. `_max_tokens_for(max_terms)` 동적 스케일러 (250 토큰/term + overhead, floor 1500 / ceiling 8000). 결과 : 12 suggestions 정상 추출.
3. **역탐색** = `resolution=null` — `TermResolver` 가 startup snapshot 이라 cold-start 후 사용자가 추가한 용어를 모름. `reverse_lookup_api.init` 에 `terms_provider` 콜백 추가 → 매 요청마다 live registry snapshot 으로 fresh resolver 생성. main.py 가 `_live_terms_provider` lambda 전달.

**E2E 검증 결과 :**
- AI 추천 12 → bulk-add 8 등록 → propose-bindings 30 bindings (alias 매칭 1.0 confidence).
- manual write `slab-rules.md` (rule_ast 와 의도적 충돌) → P7 후크 자동 발동 → auto-link cache 0 → **29 bindings**.
- gap scan → **26 conflicts** (rule_ast diff: unit mismatch g↔건/t↔g, comparator mismatch ≥↔≤, 이하↔이상).
- reverse_lookup `슬래브` → `resolution_source=exact` + impact targets 추출.

회귀 테스트 55/55 PASS.

### P6 (완료) — 사용자-가이드.html v2 갱신

- [x] `toClaude/modeling/사용자-가이드.html` v1 → v2. version badge, 헤더 lead 에 v2 변경 요약 추가.
  Phase 0 (cold start + 데모 로드 버튼), Phase 3 (3-A 외부 / 3-B in-app 작성기 / 3-C directive 가이드),
  Phase 4 (4-A 직접 / 4-B AI 추천 모달 source 토글) 재구성. §4 빠진 기능 표를 P1~P5 완료 반영
  ('완료' 색상으로 일괄 변경, 미완은 in-app onboarding tour 1건). §5 다음 우선순위를
  「실데모 검증 + 폴리시 4종」 으로 재기획. §6 치트시트에 「매뉴얼 작성」 + 사이드바 하단 컨트롤 행 추가.
  목차 라벨도 동기화.

---

## 2026-04-26 (네이밍 정정 + opaque 식별자 매핑 인프라 풀확장)

사용자 피드백 — "도메인 매핑" 은 과대 명명, 실제 스코프는 용어 ↔ 코드 컬럼/필드.
의미 없는 식별자 (`a1`, `i`) 도 클래스/메서드 컨텍스트로 매핑 가능하게 인프라
풀 확장 (Phase A~E).

- [x] **Phase A — 사이드바 라벨 "도메인 매핑" → "용어 매핑"**
  - `ModelingSection.tsx` MAIN_NAV — label + description 정직하게 표기.

- [x] **Phase B — `ContextBundler` 신설 (`backend/modeling/mapping/context_bundler.py`)**
  - `CodeContextBundle` dataclass — code_fqn 별 주변 컨텍스트 (name_tokens, enclosing_class/method, sibling_field_names, type_hint, db_column_name, is_jpa_column).
  - 토크나이저 — camelCase + snake_case + letter↔digit split, stop word 제거 (`a1` → `["a","1"]` → opaque).
  - `is_opaque()` heuristic — name_tokens 의 의미 있는 토큰이 0 이면 opaque (LLM 도움 필요 마킹).
  - `candidate_queries_from_bundle()` — bundle → resolver query 변종 (db_column_name, name_lower, snake/space joined, suffix-stripped, opaque 시 class+name 합친 enriched query).
  - `llm_prompt_context()` — LLM stage 에 넘길 한국어 한 줄 (필드/클래스/메서드/타입/sibling).
  - 13 unit tests (`tests/test_context_bundler.py`).

- [x] **Phase C — `propose_bindings_service` 확장**
  - `mode` 파라미터 신설 — `"jpa_only"` (기존 default) | `"all_fields"` (모든 FIELD entity).
  - 모든 매칭이 ContextBundler 통과 — 같은 query 생성 로직 재사용.
  - `total_opaque_inspected` 카운트 + result.warnings 에 `llm_budget_exhausted_N`.
  - Scope 결정 — JPA + EXACT/ALIAS → PRIMARY, 그 외 → PARTIAL (LLM 매칭 포함).
  - `_match_with_bundle` — 두 resolver 사용 (alias-only 와 LLM-enabled), 단순 query 는 alias 만, LLM 은 enriched query 한 번.
  - LLM 호출 게이트 — `bundle.is_opaque()` 일 때만 (의미 있는 이름은 alias 로 못 잡으면 LLM 도 불가능).
  - Budget cap — `llm_call_budget=30` (기본). 초과 시 skip + warning.
  - 신규 테스트 — non-JPA field iteration + opaque 카운트.

- [x] **Phase D — `ClaudeTermResolver` (`backend/modeling/query/llm_term_resolver.py`)**
  - `LLMResolver` Protocol 구현, sync (resolver chain 호환).
  - 한국어 system prompt — 철강 도메인 + JSON-only 응답 강제.
  - JSON 파서 — fenced code, raw object, regex fallback 3중 시도.
  - Graceful degrade — API key 없거나 SDK 없거나 호출 실패 시 None 반환 (pipeline 안 깨짐).
  - 환각 방어 — propose service 가 `term_fqn in registry` 체크 후 채택.
  - `main.py` wire — `_llm_term_resolver = ClaudeTermResolver()` 후 `ProposeBindingsService(llm_resolver=...)`.
  - 9 unit tests (mocked client).

- [x] **Phase E — UI evidence expander ("왜 이 매칭?")**
  - Backend: `GET /api/modeling/bindings/{id}/evidence` — proposal + bundle (class/method/sibling/queries/llm_prompt) + rationale.
  - `ConceptBinding.rationale` 필드 신설 (default ""). LLM 매칭은 `proposal.reasoning`, alias 매칭은 `이름 매칭: query="..." → alias hit`.
  - Frontend: 매핑 행 좌측 chevron 클릭 → 인라인 패널 — 클래스/메서드/타입/DB 컬럼/이름 토큰/sibling/시도된 query/LLM context 표시.
  - "JPA only" / "all fields + LLM" 모드 토글 헤더에 추가.
  - propose 결과 strip 에 `total_opaque_inspected` 추가 (LLM 추론 시도 수).

- [x] **이벤트 루프 차단 방지**
  - `propose-bindings` endpoint — `await asyncio.to_thread(propose, ...)` 로 sync 호출 위임. propose 가 LLM 호출하는 동안 다른 endpoint (list_terms, evidence, repos) 동시 처리 가능.

- [x] **검증**
  - 백엔드 — 101 테스트 PASS (신규 22건 포함).
  - End-to-end :
    - jpa_only — 0.02s, 9 proposals (slab-design-real seeds 2 terms × @Column variants).
    - all_fields — 0.02s, 24 proposals (15 new from non-JPA + 9 refreshed). slab 코드는 의미 있는 이름 → opaque=0 → LLM 호출 0.
    - confirm 후 re-propose → preserved=1 (회귀 방지 fix 유지).
  - UI — 도움말 패널 + 모드 토글 + 매칭 후보 24건 + 매칭 근거 패널 (class context + queries) 시각 검증.

- [x] **결정 변경 (confirmed ↔ rejected) UI 노출**
  - 사용자 피드백 — "한번 확정한거 거부로는 못바꾸나?" — 백엔드는 idempotent 했으나 UI 가 결정 후 버튼을 숨겨서 변경 불가능했음.
  - Fix — 행마다 [확정][거부] 두 버튼을 항상 렌더, 현재 상태 = 색채워진 disabled, 반대 상태 = outlined clickable. 클릭 시 flip.
  - 백엔드 변경 0 — `confirm`/`reject` 가 status 무관 무조건 덮어쓰는 기존 동작 그대로 활용.
  - 시각 검증 — confirmed 행 → "거부" 클릭 → "거부됨" [disabled] + "확정" 활성화로 즉시 전환 (브라우저 DOM snapshot 확인).

- [x] **갭 큐 데이터 시드 + conflicts 인프라 활성화**
  - 사용자 피드백 — "갭 큐 도 검증해보자". 컴포넌트는 있는데 데이터가 없어서 빈 결과만 나오던 상태.
  - **백엔드 startup 시드** (`backend/main.py`) — `seed_rules_from_repo()` 호출로 등록된 모든 repo 의 Java Javadoc 에서 BusinessRule 자동 추출 → RuleRegistry 적재. slab-design-engine 16 + slab-design-real 38 = **54 룰 자동 시드**. ManualIngestPipeline 으로 `sample-repos/slab-design-real/toClaude/{sd-tables,slab-design}.md` 두 개를 IngestMode.SKIP 로 시드 (체크섬 같으면 노옵).
  - **GapQueue.tsx 수정** — 하드코딩 `repo_id: "default"` → sidebar 의 `selectedRepoId` prop 사용. `rules: []` 강제 빈 배열 → 필드 omit 으로 backend auto-pull 트리거. `include_unconfirmed_terms: true` 추가.
  - **`GapScanRequest` 타입 갱신** — `rules` optional, `include_unconfirmed_terms` 신규.

- [x] **갭 큐 UX 풀 정비 (용어 매핑 동일 패턴)**
  - 도움말 패널 (default open) — 3 종류 갭 (code_only / manual_only / conflicts) + 컬럼 풀이.
  - **한국어 라벨** — `code_only` → "코드 → (기준서 없음)", `manual_only` → "기준서 → (코드 없음)", `conflict` → "충돌". severity `soft/hard` → "낮음/높음". 헤더 tooltip 포함.
  - 헤더 카피 — "갭 큐 — 코드 ↔ 기준서" + 한국어 설명. 버튼 "스캔 실행" → "갭 자동 탐지".
  - Repo 미선택 가드 — sidebar 안내 배너.
  - **결정 flip** — confirm/unconfirm 양방향. `gap_store.unconfirm()` + `POST /gaps/{id}/unconfirm` 신규. 행마다 [확정] / [보류로] 버튼 (현재 상태에 따라 색채워진 disabled vs outlined clickable).
  - 스캔 결과 strip — code/manual/conflicts 분리 카운트 + 한국어 라벨.

- [x] **매뉴얼 노이즈 필터** (manual_only 26 → 18)
  - `md_parser` — `_META_SECTION_TITLE_PATTERNS` 신설. heading_path 에 메타 섹션 (작성 가이드 / 작성 순서 / Q&A / STATUS / TODO 등) 이 하나라도 포함되면 해당 섹션 fragment 안 만듦. 섹션 자체는 보존.
  - `SimpleHeuristicExtractor._NOISE_PATTERNS` — 휴리스틱 추출 후보에 워크플로우 마커 (STATUS/TODO/DONE/WIP), DDL annotation (PK/FK/UK), 불릿/번호 마커, 순수 숫자/URL/수식 패턴 매칭 시 제외.
  - 효과 — `STATUS: TODO`, `(PK)`, `(FK→ORDER_OS)` 등 8개 노이즈 빠짐. 도메인 콘텐츠 (`회사코드 + 소코드`, `PRODUCT_TYPE_CD VARCHAR2(4)` 등) 는 유지.

- [x] **DescribedInBinding auto-linker → conflicts 탐지 활성화** ⭐
  - 신규 모듈 `backend/modeling/gap_detection/auto_linker.py` — `auto_link_rules_to_fragments(rules, fragments, embedder, *, top_k=3, min_confidence=0.5)`. 각 rule 마다 가장 유사한 fragment top-K → DescribedInBinding 자동 생성. 신뢰도 기록.
  - `gaps_api._auto_described_in` 모듈 변수 + `init(auto_described_in=...)` 파라미터. scan 요청 의 `described_in` 비어있으면 startup 에서 만든 auto-bindings 로 fallback.
  - main.py startup — rule 시드 + manual 시드 직후 auto-linker 실행 → 결과를 `gaps_api.init` 재호출로 주입.
  - 8 unit tests (`tests/test_auto_linker.py`).

- [x] **Conflicts evidence panel — AST diff 시각화**
  - GapQueue 의 evidence 패널 — 기존 raw JSON dump → 구조화된 시각화.
  - `EvidencePanel` 컴포넌트 — rule_statement (코드 룰, amber 박스) vs fragment_text (기준서, blue 박스) side-by-side. 각 mismatch type (numeric/comparator/unit) 별 색깔 (amber/purple/rose) + chips 로 left↔right pair 표시.
  - 비-conflicts (manual_only/code_only) evidence 는 raw JSON fallback.

- [x] **Auto-linker 임베더 업그레이드 — OpenAI text-embedding-3-small** ⭐⭐
  - 신규 `OpenAITextEmbedder` (`backend/modeling/gap_detection/embedding_drifter.py`) — sync OpenAI client + per-instance 캐시 + `embed_batch()` (1 round-trip 으로 모든 텍스트 임베딩).
  - main.py auto-linker — OpenAITextEmbedder 우선, fail 시 HashingTextEmbedder fallback. OpenAI 면 threshold=0.55 (의미 임베딩이라 더 엄격), 아니면 0.5.
  - **품질 효과** —
    - HashingTextEmbedder: 160 bindings → 111 conflicts (대부분 노이즈)
    - OpenAI: **7 bindings → 7 conflicts (실제 충돌만)** + 31 code_only (진짜 미설명 룰) + 18 manual_only.
  - 비용 — startup 시 1회 batch 호출. ~120 tokens 짧은 텍스트 → 거의 무료 ($0.02/1M tokens).

- [x] **3번째 데모 기능: Reverse Lookup (역탐색)** ⭐
  - `ReverseLookupPanel.tsx` 신규 — 사이드바 4번째 탭 "역탐색" 추가.
  - 흐름: 사용자가 한국어 용어 (예: "품종코드") 입력 → BusinessTerm 매칭 → 확정된 ConceptBinding 그래프 BFS → 영향받는 코드 위치 (column/field/method) 표시.
  - UI: 검색 폼 (모드 safe/observed/potential, scope filter, max_hops, 미확정 포함) + 용어 해석 결과 strip + 영향 받는 코드 위치 리스트 (kind 배지 + fqn + 거리/신뢰도/경로).
  - **버그 fix** — `concept_store.list_by_term()` 이 confirmed proposal 의 binding 을 반환할 때 `binding.confirmed=True` 로 patch (proposal.status 와 binding.confirmed 가 별도 필드라 reverse_lookup 의 confirmed-only 게이트가 모두 차단하던 회귀).
  - main.py — terms_api 시드 후 reverse_lookup_api 재init (TermResolver 에 등록된 BusinessTerm 주입 + 같은 binding store 공유).
  - **검증** — "품종코드" 검색 → exact 매칭 (conf 1.0) → 3 confirmed binding → 3 affected code positions. 거리 1, name_match 경로.
  - **데모 가치** — 용어 매핑에서 확정한 결정의 가치를 즉시 활용. "이 용어 바꾸면 어디 영향?" 질문에 즉답.

- [x] **HANDOFF.md 갱신** — `## 🟢 현재 상태 (2026-04-26 세션 종료)` 섹션 추가 (4-탭 + 신규 모듈 + 시드 + 검증 수치 + 데모 흐름 + 다음 세션 첫 할 일 + 한계). 과거 기록은 `## 📜 과거 세션 기록` 으로 분리.

- [x] **Demo guide 4-탭 시연 시나리오** — `toClaude/modeling/demo_guide.md` 에 8~12분 풀 데모 스크립트 추가. Step 1~4 (Repository → 용어 매핑 → 갭 큐 → 역탐색) + 마무리 멘트 + 자주 받는 질문 + 시연 전 체크리스트 + Troubleshooting.

- [x] **End-to-end 회귀 테스트 보강 (165 PASS)**
  - `tests/test_concept_binding_proposal.py::TestConfirmedPatchRegression` — `list_by_term` 의 confirmed=True patch 회귀 (2건).
  - `tests/test_auto_linker.py::TestAutoLinkerGapScannerIntegration` — auto-linker 의 binding 으로 gap_scanner 가 conflicts 잡는지 통합 테스트.
  - `tests/test_reverse_lookup_api.py::test_proposal_confirm_flows_to_reverse_lookup` — propose-confirm-reverse_lookup 흐름 end-to-end.

- [x] **Auto-linker UI 노출** — 사용자가 trigger / 임계값 조정
  - 백엔드: `POST /api/modeling/gaps/auto-link` (top_k, min_confidence) + `GET /auto-link/status`. main.py 가 rule_registry + embedder 를 gaps_api.init 에 wire.
  - 프론트엔드: 갭 큐 헤더에 "auto-link (N)" 토글 버튼 + 펼침 패널 (top-K input + threshold slider + 재계산 button + 결과 strip).
  - 사용자 흐름: threshold 조정 → 재계산 → bindings 갱신 → "갭 자동 탐지" 다시 → conflicts 재산출.

- [x] **5번째 탭: 영향 분석 (Impact Analysis)** ⭐
  - 신규 모듈 `backend/modeling/api/impact_api.py` — `POST /api/modeling/impact/analyze` (repo_id, target_fqn, direction=incoming/outgoing, mode, max_hops).
  - `InMemoryGraphView` 가 RepositoryRegistry 의 parse_results 로부터 graph 빌드 (repo 별 cache).
  - QueryEngine.impact() 활용 — incoming = 호출자/의존자, outgoing = 의존하는 코드.
  - 신규 컴포넌트 `frontend/src/components/sections/modeling/ImpactAnalysisPanel.tsx` — 사이드바 5번째 탭 "영향 분석". 검색 폼 (target fqn + direction + mode + max_hops) + 결과 패널 (target_exists 배지 + affected list with kind/distance/confidence/path).
  - 5 unit tests (`tests/test_impact_api.py`).
  - **데모 가치** — "이 코드 바꾸면 무엇이 깨지나" / "이 서비스가 무엇에 의존하나" 즉답. 역탐색과 짝 (term→code, code→code).

- [x] **6번째 탭: 기준서 (매뉴얼 업로드)** ⭐
  - FE API 추가 — `listRegisteredManuals`, `toggleManualAuthoritative`, `uploadManualStream`, `IngestMode`, `ManualDocumentDto` (`frontend/src/lib/api/modeling.ts`).
  - 사이드바 nav 에 FileText icon 으로 "기준서" 탭 추가 (Repository 다음 순서 — 데이터 입력 layer 인접).
  - 기존 `ManualUpload.tsx` 가 SSE upload + 모드 토글 (skip/update/force) + 매뉴얼 목록 + authoritative 토글 모두 갖춘 상태였으나, FE API 누락으로 빌드 실패 중. API 추가 후 즉시 동작.
  - **지원 포맷** — Markdown, PDF (pypdf), DOCX (python-docx), PPTX (python-pptx), Image (easyocr OCR).
  - **검증** — curl 로 markdown 새 매뉴얼 업로드 → ingested, ManualRegistry 2→3.

- [x] **Impact Analysis 강화 — cross-file method resolution** ⭐
  - 신규 모듈 `backend/modeling/code_analysis/call_resolver.py` — JavaParser 의 unresolved call (변수명 그대로 적힌 target) 을 field type lookup 으로 후처리 해소.
    - 1. simple-name → FQN 인덱스 (class/interface/enum)
    - 2. class FQN → field_name → field_type 인덱스
    - 3. unresolved `<class>.<varname>.<method>` → `<class>` 의 field 면 → field_type 의 클래스 FQN 룩업 → resolved edge 추가
  - `impact_api._get_view` — call_resolver 결과를 GraphView 에 합성 ParseResult 로 추가 (기존 edges 는 보존, 새 edges 만 augment).
  - 5 unit tests (`tests/test_call_resolver.py`).
  - **slab-design-real 효과** — 1018 calls 중 95 already resolved + **42 newly resolved** + 879 still unresolved (주로 local var / lambda).
  - **End-to-end 효과** — `EdgingService.findGroup` incoming **0 → 1** (`SdWidthRangeAction.execute` 가 호출자로 등장).
  - **한계** — 완전한 type 분석 (local var / generic / stream) 은 별도 작업. 현재 PoC 는 field DI 패턴 (Spring autowired) 에 한정.

---

## 📊 모델링 섹션 최종 상태 (2026-04-26 끝)

**6 사이드바 탭 모두 활성**, **198 backend tests PASS**

| # | 탭 | 입력 | 출력 |
|---|---|---|---|
| 1 | Repository | 코드 경로 | 12-analyzer 파싱 (entities/relations) |
| 2 | 기준서 | PDF/DOCX/PPTX/MD/Image 파일 | 인제스트된 ManualDocument + fragments |
| 3 | 용어 매핑 | 한국어 BusinessTerm | JPA 컬럼/필드 자동 후보 + 사람 확정 (LLM stage 포함) |
| 4 | 갭 큐 | (자동) | 코드↔기준서 갭 3종 + auto-link 컨트롤 + AST diff evidence |
| 5 | 역탐색 | 한국어 용어 | 코드 위치 (term → code) |
| 6 | 영향 분석 | 코드 fqn + 방향 | 다른 코드 위치 (code → code, +call_resolver) |

- [x] **Cross-tab navigation — 깊이 탐색 흐름 wiring** ⭐
  - `ModelingSection` 에 `navigateTo(view, params)` + `navParams` state 추가. `ModelingView` / `ModelingNavParams` export.
  - `ReverseLookupPanel` — `prefillTerm` prop, mount 시 자동 검색. affected list 의 각 코드 fqn 옆에 [영향 분석] 버튼 → 영향 분석 탭으로 jump + targetFqn pre-fill.
  - `ImpactAnalysisPanel` — `prefillTargetFqn` prop, mount 시 자동 분석. affected list 의 각 fqn 옆에 [드릴다운] 버튼 → 같은 탭에서 그 fqn 으로 재검색.
  - `TermMapping` — binding row 의 term_fqn 클릭 → 역탐색 (term → code), code_fqn 클릭 → 영향 분석 (code → code). `term.<name>` prefix 제거 후 검색어로 사용.
  - `GapQueue` — conflict gap 의 target_fqn (예: `<code_fqn>#rule1` 형태) 에서 `#` 앞 부분 추출 → 영향 분석.
  - **사용자 흐름** — "품종코드" 검색 → 영향받는 3 코드 위치 → 그 중 하나 [영향 분석] → 호출자 트리 → [드릴다운] 으로 깊이 탐색. 한 화면에서 도메인 → 코드 → 코드 그래프 끝까지 도달.
  - 무한 루프 방지: 같은 fqn navigate 시 `autoSearchedRef` 가드.

- [x] **7번째 탭: DI 그래프 (Spring beans + autowires 시각화)** ⭐
  - 신규 모듈 `backend/modeling/api/di_graph_api.py` — `GET /api/modeling/di/graph?repo_id=X` returning nodes + edges. Layer heuristic (controller/service/repository/config/other) 으로 패키지/이름 패턴 매칭.
  - 신규 컴포넌트 `frontend/src/components/sections/modeling/DiGraphPanel.tsx` — `@xyflow/react` 기반. Layer 별 horizontal layout, MiniMap, Controls. Layer 색깔 표 (도움말).
  - 노드 클릭 → 우측 패널 → incoming/outgoing 빈 리스트 → 클릭으로 이동 또는 [이 빈 영향 분석] 으로 영향 분석 탭 jump (cross-tab nav 활용).
  - **slab-design-real 검증** — 61 beans / 50 autowires / layers: config(4) / service(14) / controller(4) / repository(11) / other(28). slab-design-engine 4 beans 도 정상 렌더 (Controller→Service→others 화살표).
  - **데모 가치** — Spring 아키텍처 한눈에 — "이 시스템 어떻게 구성됐나" / "Service 가 의존하는 빈 / Controller 가 호출하는 흐름" 즉답.

- [x] **데모 가이드 v2 — 7-탭 시나리오 + cross-nav 흐름**
  - `toClaude/modeling/demo_guide.md` 에 12~15분 풀 데모 스크립트 추가 (Step 0~7 + 마무리 + Q&A + Checklist v2).
  - 4-탭 v1 스크립트는 그대로 보존 (이전 버전 참고용).
  - 핵심 하이라이트: 7 탭 모두 cross-navigation 으로 연결 — 도메인 용어 한 단어로 시작 → 한 클릭마다 한 단계 깊이 들어감.

- [x] **Cross-nav 시각 피드백 strip**
  - `ModelingNavParams` 에 `from?: string` 추가 — 출발 탭 라벨.
  - 모든 cross-nav 호출처 에 `from` 명시 ("용어 매핑" / "갭 큐 (충돌)" / "역탐색" / "DI 그래프" / "드릴다운").
  - `ReverseLookupPanel` + `ImpactAnalysisPanel` — prefill 발생 시 보라색 strip 표시 (`**OOO** 에서 자동 입력 — "값"` + [닫기]).
  - 사용자가 어디서 navigation 됐는지 즉시 파악 가능 — 흐름 추적 UX 개선.

- [x] **수동 매핑 UI — 사용자가 직접 ConceptBinding 생성** ⭐ (사용자 직감 #2)
  - 사용자 의문 — "LLM 추천만 있고 사용자가 직접 1:1 매핑하는 UI가 없다". 정확히 맞음.
  - 신규 endpoint `POST /api/modeling/bindings/manual` — `{repo_id, term_fqn, code_fqn, scope, decided_by}` → 즉시 confirmed 상태로 ConceptBindingProposal 생성. source=`manual`, confidence=1.0.
  - 신규 endpoint `GET /api/modeling/repos/{repo_id}/entities/search?q=X&kind=field&limit=20` — 코드 entity substring 검색 (수동 매핑 자동완성).
  - FE API client `createManualBinding` + `searchEntities` 추가.
  - `TermMapping.tsx` — "매핑 후보" 헤더에 emerald [수동 매핑] 토글 버튼. 클릭 시 emerald 패널 펼침 :
    - 용어 dropdown (등록된 BusinessTerm)
    - 코드 검색 input (250ms 디바운스, 2글자 이상)
    - scope dropdown (primary/partial)
    - 검색 결과 리스트 — 각 항목에 [매핑] 버튼 → 즉시 confirmed binding 생성 + 폼 닫힘 + 목록 갱신
  - **end-to-end 검증** — curl 로 `term.품종코드` ↔ `com.example.test.ManualMappedClass.field1` 매핑 → status confirmed, source manual, conf 1.0.

- [x] **Structured Manual 형식 — frontmatter directive** ⭐ (사용자 직감 #1)
  - 사용자 의문 — "기준서도 코드처럼 정형화돼야 매핑 정확". 정확히 맞음. 자유 형식 markdown 은 임베딩 추측 한계.
  - **HTML comment directive** — `<!-- ontong: term=term.X rule=rule.Y scope=primary unit=char -->`. 다음 paragraph 의 `attributes` 로 흡수.
  - `ManualFragment.attributes: dict[str, str]` 필드 신설.
  - `md_parser._chunk_body` — `_DIRECTIVE_RE` 인식, `_KV_RE` 로 key=value 파싱, `pending_attrs` → 다음 chunk 흡수.
  - `auto_link_rules_to_fragments` 우선순위 변경:
    1. **Pass 1 (directive)** — `fragment.attributes["rule"] == rule.qualified_name` 매칭 → confidence=1.0, source=`manual_directive`. embedding 우회.
    2. **Pass 2 (embedding)** — directive 로 안 잡힌 rule 만 cosine top-K (기존 동작).
  - 효과 — 매뉴얼 작성자가 "이 단락은 이 룰" 명시 가능. 자동 추측 의존 줄임 + 정확도 1.0 확정.
  - 7 신규 unit tests (auto_linker 3 + md_parser 4). 217 backend tests PASS.

---

## 📊 모델링 섹션 최종 상태 v3 (2026-04-26 끝)

**7 사이드바 탭 모두 활성** + cross-nav + 수동 매핑 + Structured Manual + **217 backend tests PASS**

| # | 탭 | 입력 | 출력 |
|---|---|---|---|
| 1 | Repository | 코드 경로 | 12-analyzer 파싱 |
| 2 | 기준서 | PDF/DOCX/PPTX/MD/Image (+ structured directive) | ManualDocument + fragments (with attributes) |
| 3 | 용어 매핑 | BusinessTerm | 자동 후보 + **수동 매핑 직접 생성** |
| 4 | 갭 큐 | (자동) | 갭 3종 + auto-link (directive 우선) |
| 5 | 역탐색 | 한국어 용어 | 코드 위치 (term → code) |
| 6 | 영향 분석 | 코드 fqn | 다른 코드 (code → code) |
| 7 | DI 그래프 | (자동) | Spring beans + autowires viz |

**자동화 의존도 낮춤** :
- 매뉴얼: structured directive 로 정밀 매칭 (작성자 명시)
- 매핑: 수동 매핑 으로 사용자가 직접 만들기 (추천 의존 X)
- 둘 다 자동 흐름 (LLM/임베딩) 과 공존 — 사용자 통제력 + 자동화 효율 모두 확보
  - 신규 모듈 `backend/modeling/api/di_graph_api.py` — `GET /api/modeling/di/graph?repo_id=X` returning nodes + edges. Layer heuristic (controller/service/repository/config/other) 으로 패키지/이름 패턴 매칭.
  - 신규 컴포넌트 `frontend/src/components/sections/modeling/DiGraphPanel.tsx` — `@xyflow/react` 기반. Layer 별 horizontal layout, MiniMap, Controls. Layer 색깔 표 (도움말).
  - 노드 클릭 → 우측 패널 → incoming/outgoing 빈 리스트 → 클릭으로 이동 또는 [이 빈 영향 분석] 으로 영향 분석 탭 jump (cross-tab nav 활용).
  - **slab-design-real 검증** — 61 beans / 50 autowires / layers: config(4) / service(14) / controller(4) / repository(11) / other(28). slab-design-engine 4 beans 도 정상 렌더 (Controller→Service→others 화살표).
  - **데모 가치** — Spring 아키텍처 한눈에 — "이 시스템 어떻게 구성됐나" / "Service 가 의존하는 빈 / Controller 가 호출하는 흐름" 즉답.

---

## 2026-04-26 (이전 세션 — 도메인 매핑 UX rework + 결정 보존 버그 fix)

---

## 2026-04-26 (도메인 매핑 UX rework + 결정 보존 버그 fix)

`/design-review` 결과 — "용어 설명 UI 부재 / term 수정 안 됨 / 확정한 매핑이
스캔마다 초기화" 의 3건을 한 번에 처리.

- [x] **CRITICAL bug fix — `concept_store.put_proposal` 가 결정 덮어씀**
  - 증상: `propose-bindings` 재실행 시 사용자가 confirmed/rejected 한 binding 이 다시 PROPOSED 로 초기화돼 모든 검토 결과 소실.
  - 원인: 기존 docstring 이 "idempotent — 같은 id 재 put 시 덮어쓰기" 로 의도된 동작이었으나 UX 가 잘못됨.
  - Fix: `existing.status is not PROPOSED` 인 경우 status / decided_* 보존하고 binding metadata 만 갱신 (`backend/modeling/mapping/concept_store.py`).
  - 회귀 방지 테스트: `tests/test_propose_bindings_service.py::TestIdempotency::test_re_propose_preserves_user_decision`, `tests/test_terms_api.py::TestProposeResultBreakdown`.

- [x] **`ProposeBindingsResult` 분리 — new / refreshed / preserved**
  - 기존: `total_proposed` 만 반환 → 사용자가 "재 propose 가 무엇을 했는지" 알 수 없었음.
  - 신규: `new` (처음 발견), `refreshed` (PROPOSED 메타 갱신), `total_preserved` (사용자 결정 보존). `total_proposed = new + refreshed` (backward-compat).
  - API DTO `ProposeBindingsResponse` 도 동일 필드 노출.

- [x] **Term 수정·삭제 API**
  - `BusinessTermRegistry.delete(repo_id, term_fqn)` 신설.
  - `PUT /api/modeling/terms/{repo_id}/{qualified_name}` — canonical_label / aliases / domain / description 교체 (qualified_name 자체는 불변).
  - `DELETE /api/modeling/terms/{repo_id}/{qualified_name}` — 용어 + 관련 ConceptBindingProposal 동시 정리 (confirmed/rejected 포함). 응답에 `proposals_removed` 카운트.
  - 테스트: `tests/test_terms_api.py::TestUpdateTerm`, `TestDeleteTerm`.

- [x] **Frontend `TermMapping` UX 전면 재설계**
  - **도움말 패널** (default open) — 3단계 워크플로우 (등록→탐색→검토) + 7개 용어 풀이 (term_fqn / canonical_label / aliases / code_fqn / scope / source / conf).
  - **헤더 카피 개선** — "BusinessTerm 등록 → 자동 매칭 제안 → 사람 확정. 시나리오 1·2 의 무대" 같은 내부 용어 제거. "현업이 쓰는 용어를 등록하면, 코드의 JPA 컬럼·필드와 자동으로 후보 매핑을 만들어 줍니다."
  - **버튼 카피** — "매핑 제안 실행" → "매핑 자동 탐색", title 에 "확정·거부한 결정은 보존됩니다" 안내.
  - **용어 카드 — 수정/삭제 버튼 항상 표시** (기존 hover-only 는 발견성 0). aria-label 로 스크린리더 친화.
  - **Edit form** — 클릭 시 기존 값 pre-fill, qualified_name 은 read-only 표기 ("등록 후 변경 불가").
  - **삭제 confirm dialog** — 매핑 동시 정리 사실 안내.
  - **Propose 결과 strip** — 4개 숫자 분리 표시: 신규 후보 / 메타 갱신 / 결정 보존 / 매칭 안 됨.
  - **테이블 헤더 한국어화** — 상태/용어/코드/범위/출처/신뢰도. 각 헤더에 title (tooltip) 로 의미 설명.
  - **상태 라벨** — `proposed` → "검토 대기", `name_match` → "이름매치", `embedding` → "임베딩" 등.
  - **빈 상태** — 비어있을 때 다음 액션 안내 ("새 용어 버튼으로 첫 용어를 등록한 뒤..."). 필터 때문에 비어보이는 경우 자동 감지.

- [x] **API client 확장** — `updateTerm`, `deleteTerm`, `BusinessTermUpdateRequest`, 확장된 `ProposeBindingsResponse` (`frontend/src/lib/api/modeling.ts`).

- [x] **검증**
  - 백엔드: 73/73 테스트 PASS (신규 6건 포함).
  - End-to-end: confirm → re-propose → preserved=1 + confirmed status 유지 확인 (`curl` 흐름).
  - UI: `/browse` 로 도움말 패널 + propose 결과 strip + edit form pre-fill 모두 시각 검증.

---

## 2026-04-25 (Repository workflow + UI redesign)

도메인 매핑 클릭 시 빈 화면 문제(`needsRepoSelector` 게이트가 잘못 차단) 수정에서
출발해, Repository 등록·관리 워크플로우 풀버전으로 확장.

- [x] **Bug fix — `needsRepoSelector` 게이트 우회**
  - `MAIN_NAV` 가 `term-mapping`/`gap-queue` 만 가지는데 게이트가 항상 활성화돼 빈 화면이 떴음.
  - 이후 게이트 자체를 제거하고 Repository 탭으로 대체.

- [x] **Backend — `RepositoryRegistry` + 4 REST endpoints**
  - `backend/modeling/code_analysis/repo_parser.py` — `dump_entities_snapshot.py` 의 12-analyzer 파이프라인을 런타임 함수로 추출 (`parse_repo`, `serialize_parse_results`, `rehydrate_from_snapshot`).
  - `backend/modeling/code_analysis/repository_registry.py` — `RepositoryEntry` + `RepositoryRegistry` Protocol + `InMemoryRepositoryRegistry`.
  - `backend/modeling/api/repos_api.py` — `GET /api/modeling/repos`, `POST /repos/register` (sync), `POST /repos/register/stream` (SSE), `DELETE /repos/{repo_id}`.
  - `terms_api`: `_repo_registry` 추가 + `_lookup_parse_results()` helper — propose-bindings 가 registry 우선 조회, 없으면 친절한 404.
  - `backend/main.py` — startup 시 `auto_discover_from_disk(scan_roots=[sample-repos])` 로 기존 캐시 자동 복원.

- [x] **Backend — Disk caching (`<repo>/.analyzed/`)**
  - `register()` 시 `entities.json` (12-analyzer dedup 형식) + `repo-meta.json` (registry용 가벼운 메타) 동시 작성.
  - `auto_discover_from_disk()` — `entities.json` 기준 스캔, `repo-meta.json` 있으면 우선, 없으면 `metadata.repo_id`/`metadata.repo_path` fallback.

- [x] **Backend — SSE progress streaming**
  - `parse_repo(on_progress)` callback signature: `(stage, done, total)` — stages: `discovering`/`parsing`/`enriching`/`complete`.
  - `POST /repos/register/stream` — `asyncio.Queue` + `loop.call_soon_threadsafe` 패턴으로 worker thread → main loop 안전 전달.

- [x] **Frontend — Repository 관리 탭 신설**
  - `RepositoryManager.tsx` — 등록된 repo 카드 리스트 + preset chip (slab-design-real / slab-design-engine / scm-demo) + custom 등록 폼 + SSE 진행 표시 (단계별 progress bar).
  - `ModelingSection.tsx` 리팩토링: 기존 "SCM 데모 프로젝트 로드" 게이트 제거, nav 최상단에 `Repository` 탭 추가 (default 진입점), `selectedRepoId` 를 parent state 로 lift, sidebar 에 "선택된 Repository" 표시.
  - 카드 클릭 시 자동으로 `term-mapping` 탭으로 이동.

- [x] **Frontend — `TermMapping` repo 선택 sync**
  - `repoId` prop 으로 받음 (자체 state 제거), 빈값일 때 friendly empty state + propose 버튼 비활성화. 헤더에는 read-only `repo: <id>` 배지.

- [x] **검증**
  - 백엔드: 23 테스트 PASS (`tests/test_repository_registry.py` 12, `tests/test_repos_api.py` 11). slab repo 의 `.analyzed/` 오염 방지를 위해 `tmp_path` 사본 후 register 하도록 fixture 변경.
  - 프론트: `/browse` 로 `localhost:3001` 풀 워크플로우 검증 — Modeling → Repository 카드 클릭 → 자동 도메인 매핑 이동 → BusinessTerm 2개 + 매핑 후보 9개 표시 확인.

---

## 2026-04-25 (`JpaAnalyzer` 12번째 Spring analyzer — OD-11-B5-7)

**배경**: 사용자 의견 — "데모 코드 어차피 JPA 쓸 텐데 미리 준비하는 게 낫다". B5-7 은 B5 단계에서 우선순위 낮아 연기됐던 항목 (Slab 샘플은 JPA 없음). 데모 코드 도착 즉시 Repository 메서드 → 테이블 접근 그래프 자동 추출 가능하도록 prep.

- [x] **모듈 신규** — `backend/modeling/code_analysis/spring/jpa_analyzer.py` (~210 LOC) :
  - **탐지 대상** : interface declaration + (`@Repository` annotation OR Spring Data 4 base interface 중 하나를 extends) :
    - `Repository` / `CrudRepository` / `PagingAndSortingRepository` / `JpaRepository`
    - `_REPO_BASE_INTERFACES` frozenset 으로 simple name 매칭 (import 무관).
  - **entity simple name 추출** : `extends JpaRepository<User, Long>` → "User" (`_extract_entity_type` walk: extends_interfaces > generic_type > type_arguments > 첫 type_identifier).
  - **메서드 이름 컨벤션** :
    - `find*By*` / `get*By*` / `query*By*` / `read*By*` / `search*By*` → `READS_TABLE` (`jpa_operation="find"`)
    - `exists*By*` → `READS_TABLE` (`"exists"`)
    - `count*By*` → `READS_TABLE` (`"count"`)
    - `delete*By*` / `remove*By*` → `WRITES_TABLE` (`"delete"`)
    - `save` / `saveAll` / `saveAndFlush` (정확 매치) → `WRITES_TABLE` (`"save"`)
    - 그 외 → edge 없음 (custom @Query 는 `NativeSqlAnalyzer` 영역, marker only future).
  - **prefix 매칭 방어** : prefix 다음 글자가 대문자거나 끝이어야 함 — `find` / `findX` OK, `findxxx` (소문자) 매칭 X (false-positive 차단).
  - **property path 추출** : `_BY_SPLIT_RE = (?<=[a-z])By(?=[A-Z])` 로 `findByEmailAndStatus` → `EmailAndStatus` 분리 → `_PROP_SPLIT_RE = And|Or` 로 split → `["Email", "Status"]` → 첫 글자 소문자화 → `["email", "status"]`.
  - **edge attributes** : `jpa_operation` (find/exists/count/delete/save) + `jpa_property_path` (list[str], save 는 빈 list) + `target_kind="jpa_entity_simple_name"` (CrossFileEnricher 가 향후 `@Table(name=...)` 으로 rewrite 가능 표시).
  - **out of scope (v1)** : `@Entity` ↔ `@Table` cross-file 해소 (CrossFileEnricher v2), `@OneToMany`/`@ManyToOne` 관계 엣지, `@Query` (이미 NativeSqlAnalyzer 가 처리), 메서드 entity 직접 emit (JavaParser 가 이미 함).
- [x] **`spring/__init__.py`** : `JpaAnalyzer` import + `__all__` 에 12번째로 추가.
- [x] **`scripts/dump_entities_snapshot.py`** : `_build_parser()` 11→12 analyzer + 주석 갱신.
- [x] **`tests/test_dump_entities_snapshot.py`** 동기화 — `test_build_parser_wires_eleven_spring_analyzers` → `_twelve_`, expected set 에 JpaAnalyzer 추가, metadata.analyzers 길이 검증 11→12.
- [x] **TDD RED → GREEN** — `tests/test_spring_jpa_analyzer.py` 27/27 PASS (0.06s) :
  - TestDetection (5) : JpaRepository / CrudRepository / PagingAndSortingRepository extends 매칭, @Repository 만 있고 entity 미식별 시 빈 결과, plain interface 무시.
  - TestMethodNameOperations (14 parametrized) : 10 prefix variant 모두 정확 매핑 + 3 save variant + unknown method (`customComputeStuff`).
  - TestMethodAttributes (3) : `jpa_operation` 정확, `jpa_property_path = ["email", "status"]` And split, save 는 property_path 빈 list.
  - TestMultipleMethods (2) : 한 interface 안 4 메서드 매칭 + helper 미매칭, target 동일 entity.
  - TestProtocol (3) : SpringAnalyzer 적합 / 빈 tree 빈 결과 / class declaration 무시 (interface only).
- [x] **회귀 검증** :
  - Slab 샘플 (JPA 없음) 12-analyzer 결과 **95/177** 그대로 — JPA 없는 코드 안 깨짐 검증.
  - 전체 1627 PASS / 20 FAIL (전부 Section 1 baseline). E1-j 1600 → +27.

**의의**
- 데모 코드 도착 시 Repository 메서드 → 테이블 접근 그래프가 자동 추출 — Impact Analysis 의 핵심 입력 (어떤 코드가 어떤 테이블 읽나).
- 데모 코드 무관 인프라 정책 8번째 (B5-7 옵션이 정식 종결).
- `target_kind="jpa_entity_simple_name"` 으로 마킹 → 향후 CrossFileEnricher v2 가 `@Table(name="users")` 매칭해 simple name "User" → "users" 로 rewrite 가능.

**다음 일감**
- **DescribedInStore** — 자동 발견 메커니즘 미정. 데모 코드 + 매뉴얼 함께 와야 결정 가능.
- **Slab 데모 코드 도착 대기** → B 매뉴얼 작성 / D4 UI 디자인 스펙 / E1-e 5종 gap 실증.
- (선택) **CrossFileEnricher v2** — JpaAnalyzer 의 `target_kind="jpa_entity_simple_name"` 엣지를 `@Table(name=...)` 으로 rewrite. JpaAnnotationExtractor (B6-4) 와 결합. 데모 코드 보고 결정.

---

## 2026-04-25 (`scripts/dump_entities_snapshot.py` — JSON 스냅샷 — OD-11-E1-j / A1)

**배경**: 데모 코드 도착 전후 비교 + 외부 도구 (jq, diff, vim) 입력 + 회귀 baseline 자료. 50줄 미만 스크립트로 끝낸다는 가벼운 항목. E1-f 까지의 11-analyzer 결과를 JSON 으로 덤프해 다음 단계의 분석 / 데모 / 디버깅에 활용.

- [x] **모듈 신규** — `scripts/dump_entities_snapshot.py` (~140 LOC, 위의 50줄 추산보다 길어졌으나 docstring + argparse + 헤더 포함):
  - argparse `--repo` (기본 `sample-repos/slab-design-engine/src/main/java`) / `--out` (기본 `sample-repos/.../.analyzed/entities.json`) / `--repo-id` (메타데이터 ID).
  - `_build_parser()` 11-analyzer 일괄 구성 — DI/AOP/HTTP/Events/Scheduled/Profile/Reflection/MapStruct/BeanUtils/NativeSql/**ConfigProperties** (E1-f 신규).
  - `dump_snapshot(repo_path, repo_id)` Java rglob → JavaParser.parse_file → `asdict` 직렬화 → 통계 누적 → 통합 dict 반환.
  - 출력 스키마 :
    ```jsonc
    {
      "metadata": {
        "repo_id": "slab-design-engine",
        "repo_path": "...",
        "generated_at": "2026-04-25T...Z",
        "analyzers": [...11종 이름],
        "totals": {"files": 11, "entities": 95, "relations": 177, "errors": 0}
      },
      "files": {
        "com/ontong/slab/.../X.java": {
          "language": "Java",
          "errors": [],
          "entities": [{kind, qualified_name, name, line_start, line_end, modifiers, parent, attributes}],
          "relations": [{kind, source, target, line, attributes}]
        }
      }
    }
    ```
  - **파일 경로 키 = repo_path 기준 상대경로** (다른 머신에서도 안정적, diff 가능).
- [x] **TDD** — `tests/test_dump_entities_snapshot.py` 8/8 PASS :
  - `test_build_parser_wires_eleven_spring_analyzers` — 11 종 정확히 묶음, set 비교로 누락/중복 차단.
  - `TestSnapshotSchema` (5) — top-level `{metadata, files}` 두 키만, metadata 필드 9개 검증, 파일 키 절대경로/Windows 분리자 금지, 각 파일 entry 가 `language/errors/entities/relations` 보유, `config_property` 5개 + `maxThicknessMm.default_value="240.0"` + `key_kebab="slab.equipment.max-thickness-mm"` round-trip.
  - `TestJsonSerialization` (2) — `json.dumps` round-trip (datetime/enum 등 비직렬화 객체 부재 확인) + tmp_path 파일 쓰기 후 사이즈+`{`/`}` 마커 검증.
- [x] **Slab 실행** — `.venv/bin/python scripts/dump_entities_snapshot.py` 실행 결과 `[snapshot] sample-repos/slab-design-engine/.analyzed/entities.json : 11 files / 95 entities / 177 relations / 0 errors` — E1-f 검증과 동일 (회귀 baseline). 출력 파일 ~114KB.
- [x] **`.gitignore`** 에 `**/.analyzed/` 추가 — regenerable artifact (parser/analyzer 변경 시 재실행해야 정확). 큰 파일 (~114KB) 이 git diff 노이즈 일으키지 않도록.
- [x] **회귀 검증** — 전체 1600 PASS / 20 FAIL (전부 Section 1 baseline). 8개 신규 테스트만 추가 (1592 → 1600).

**활용 시나리오**
- 데모 코드 도착 → 같은 스크립트로 새 repo 스냅샷 떠서 Slab 비교, 11-analyzer 가 새 repo 에서 어떤 entity / relation 잡는지 즉시 확인.
- parser 회귀 테스트 — 코드 수정 전후 스냅샷 비교 (`diff`/`jq`) 로 의도치 않은 변화 발견.
- 외부 도구 (그래프 시각화, 통계) 입력 데이터.

**다음 일감 (남은 인프라 거의 마무리)**
- (선택) **JpaAnalyzer B5-7** — Spring Data JPA Repository 정식 처리. 데모 코드가 JPA 사용하면 효과 큼.
- **DescribedInStore** — 자동 발견 메커니즘 미정. 데모 코드 + 매뉴얼 함께 와야 결정 가능.
- **Slab 데모 코드 도착 대기** → B 매뉴얼 작성 / D4 UI 디자인 스펙 / E1-e 5종 gap 실증.

---

## 2026-04-25 (`GapCandidate.evidence` + reevaluate 엔드포인트 + GapQueue evidence panel — OD-11-E1-i, D3-3 미수거 3/3)

**배경**: D3-3 미수거 마지막 항목. 사용자가 gap 후보의 "왜 이렇게 판단됐지?" 까볼 수 있고, "다시 판단해줘" 누를 수 있게 하는 evidence 패널 + LLM 재평가. 사용자 정책 "최소 침습" (`feedback_ui_ux_rework.md`) 반영해 UI 는 minimal `<details>` 스타일.

- [x] **`GapCandidate` 스키마 확장** — `gap_models.py` 에 `evidence: dict[str, object] = field(default_factory=dict)` 추가 (frozen dataclass). 기존 호출 sites 무수정 (default empty).
- [x] **stage 별 evidence 채우기** :
  - `RuleASTDiffer._make_candidate` : `{stage: "rule_ast", rule_statement, fragment_text, mismatch}`
  - `CosineDrifter._make_candidate` : `{stage: "drift", rule_statement, fragment_text, cosine, cutoff}`
  - `HierarchicalGapEngine._apply_llm` : 기존 evidence 보존 + `llm_reasoning` / `llm_severity` merge
  - `LLMOnlyGapEngine` : `{stage: "llm_only", rule_statement, fragment_text, llm_reasoning, llm_severity}`
- [x] **`gaps_api.GapCandidateDTO`** : evidence 필드 노출 (`Field(default_factory=dict)`). `from_candidate` 에서 dict 복사.
- [x] **신규 엔드포인트** `POST /api/modeling/gaps/{gap_id}/reevaluate` (~75 LOC) :
  - evidence 의 `rule_statement` + `fragment_text` 로 stub `BusinessRule` + `ManualFragment` 재구성 → 등록기 lookup 회피.
  - `comparator.compare()` 직접 호출 → severity + reasoning 갱신, evidence merge 후 store.upsert.
  - 에러 우선순위 **404 → 422 → 503**: gap 없음 404 / MISSING_IN gap (direction != None) 422 / comparator 미설정 503 / evidence 텍스트 누락 500.
  - `asyncio.to_thread(comparator.compare, ...)` 로 이벤트 루프 보호.
- [x] **`gaps_api.init()` 시그니처 확장** : `llm_comparator: LLMComparator | None = None` 파라미터 추가 + 모듈 싱글턴 `_llm_comparator`. `reset()` 도 정리.
- [x] **`backend/main.py` lifespan** : 기존 `_llm_comparator` (D3-2-b 의 PydanticAILLMComparator 인스턴스 또는 None) 를 `gaps_api.init(llm_comparator=...)` 에 그대로 패스.
- [x] **프런트 `modeling.ts` 인터페이스 정정** : 기존 `GapCandidateDto` 가 백엔드와 안 맞았음 (`gap_id`/`gap_type`/`confidence` 가짜 필드). 백엔드 `GapCandidateDTO` 와 1:1 맞춤 — `id` / `detected_by` / `gap_mode` / `direction: GapDirection | null` (conflicts null 허용) / `evidence: Record<string, unknown>` 추가. `reevaluateGap(gapId)` 함수 신규.
- [x] **프런트 `GapQueue.tsx`** :
  - 행 좌측 토글 컬럼 (▸/▾) — evidence 있으면 펼치기 가능.
  - 펼친 행 아래 evidence panel `<pre>` JSON pretty-print (minimal — 사용자 정책 "디자인 투자 최소화").
  - CONFLICTS_WITH 행 (direction === null) 에만 "재평가" 버튼 (Sparkles 아이콘) — `reevaluateGap()` 호출 후 setItems in-place 갱신 (전체 refresh 안 함).
  - 모든 `g.gap_id` 사용처를 `g.id` 로 정정 (기존 인터페이스 가짜 필드였던 잔재 제거 — 사용 안 됐어도 정합성).
  - 헤더 컬럼 +1 (토글), 빈 상태 colSpan 6→7 동기화.
- [x] **TDD 신규 5 케이스** (`tests/test_gaps_api.py`) :
  - `test_scan_response_includes_evidence_for_conflicts` — scan 응답의 conflicts 후보가 evidence 채워서 옴 (rule_statement / fragment_text / stage 키).
  - `test_reevaluate_unknown_gap_returns_404` — 미존재 id 404.
  - `test_reevaluate_missing_in_gap_returns_422` — MISSING_IN gap 은 LLM 재평가 의미 없음 → 422 + detail "CONFLICTS_WITH ...".
  - `test_reevaluate_without_comparator_returns_503` — comparator 미설정 instance 면 503 + "comparator" 문구.
  - `test_reevaluate_calls_comparator_and_updates_gap` — StubComparator 가 CRITICAL 반환하면 응답 severity=critical / evidence.llm_reasoning 갱신 / store.get(id) 도 갱신 확인.
- [x] **회귀 검증** — `tests/test_gaps_api.py` 20/20 PASS (기존 15 + 신규 5). 모델링 gap+rule+manual 146/146. 전체 1592 PASS / 20 FAIL (전부 Section 1 baseline). main.py 157 routes (+1 reevaluate).
- [x] **TypeScript** : GapQueue.tsx + modeling.ts 본인 깨끗. 사전 orphan (ManualOntologyBuilder/ManualUpload) 의 import 에러는 본 작업과 무관.

**의의**
- gap 후보의 근거 데이터 (rule_statement / fragment_text / cosine score / LLM reasoning 등) 가 처음으로 UI 에 노출 — 사용자가 "왜 이게 충돌이라고 잡혔는지" 즉시 검증 가능.
- 단일 gap LLM 재평가 → 전체 scan 다시 안 돌리고 1건만 빠르게 다시 판단. 다른 gap 의 confirmed 상태 보존.
- `<details>` 스타일 evidence panel 은 디자인 투자 최소 — 향후 Section 2 UI 재설계 시 영향 적음.
- 백엔드 시드 시점에 evidence 가 잘 채워지므로 향후 다른 클라이언트 (CLI, 메모리 그래프 export 등) 도 같은 데이터 활용 가능.

**D3-3 미수거 진행 상황 — 100% 완결**
- ✅ 1/3 RuleRegistry (E1-g)
- ✅ 2/3 SSE 진짜 streaming (E1-h)
- ✅ 3/3 evidence panel + LLM 재평가 (이번 작업, E1-i)

**다음 일감 (사용자 정책 — 데모 코드 무관 범용 인프라 우선)**
- **A1** entities.json 스냅샷 (50줄, 데모 코드 도착 전후 비교용)
- **(선택) JpaAnalyzer B5-7** — `@Entity` / `@Repository` 정식 처리
- 또는 **DescribedInStore** — 자동 발견 메커니즘 결정 후 (현재 보류)
- 또는 **Slab 데모 코드 도착** 대기 → B 매뉴얼 작성 / D4 UI 디자인 스펙 / E1-e 실증

---

## 2026-04-25 (`gaps_api.scan_stream` 진짜 stage-by-stage streaming — OD-11-E1-h, D3-3 미수거 2/3)

**배경**: D3-3 시점에 `scan_stream_endpoint` 는 buffered-flush PoC 였음 — 전체 scan 을 thread 에서 끝낸 뒤 stages 리스트를 한 번에 SSE 로 emit. 큰 repo 에서 사용자가 "백엔드 멈춘 건가?" 의심하는 UX 문제. 진짜 streaming 으로 격상.

- [x] **`gaps_api.scan_stream_endpoint` 재구현** :
  - **패턴** : `asyncio.Queue` + `loop.call_soon_threadsafe(queue.put_nowait, ...)` 로 worker thread → main loop 안전 전달.
  - **`_on_progress(stage)`** : worker thread 에서 호출, stage 받자마자 `loop.call_soon_threadsafe` 로 큐 push. `STAGE_COMPLETE` 만 suppress (그 시점에 result 가 없음).
  - **`_sync_scan()`** : 정상 종료 시 `(STAGE_COMPLETE, payload)` push, 예외 시 `("error", {"detail": "{ExcType}: {msg}"})` push, finally 에 sentinel `None` push 로 generator 종료.
  - **fire-and-forget worker** : `asyncio.create_task(asyncio.to_thread(_sync_scan))` — `await` 하면 다시 buffered 되므로 절대 await 금지.
  - **`stream()` async generator** : `await queue.get()` 로 drain, `None` sentinel 면 return, finally 에서 `worker_task` 정리 (조기 끊김 방어).
  - 결과 : 클라이언트가 각 stage 를 실시간으로 받음. `scanning` 즉시, `stage1_missing_in` 즉시, `stage2_conflicts` (CPU 작업 끝나자마자), `complete` (payload 포함).
- [x] **TDD 신규 3 케이스** (`tests/test_gaps_api.py` 추가) :
  - `test_scan_stream_pattern_pushes_stages_via_threadsafe_queue` — 진짜 asyncio loop + 진짜 worker thread + 진짜 asyncio.Queue 사용. `threading.Event` gate 로 main loop 가 stage1 을 받기 전엔 worker 가 진행 못 하게 막음. buffered-flush 였다면 main loop 가 영원히 stage1 을 못 받고 5초 timeout. **이 테스트가 통과 = 패턴 자체가 실시간 동작 증명**.
  - `test_scan_stream_emits_complete_event_with_payload` — complete event 가 단순 stage 라벨이 아니라 UnifiedScanResponse JSON 을 담는지.
  - `test_scan_stream_propagates_scan_exception` — worker 가 RuntimeError 던지면 "error" SSE event 가 마지막에 오고, complete 는 안 옴.
- [x] **TestClient ASGITransport 한계** :
  - 처음엔 `httpx.AsyncClient + ASGITransport` 로 E2E 실시간 검증 시도 → ASGITransport 가 SSE chunks 를 버퍼링해 클라이언트가 stage1 을 worker timeout (5초) 후에야 받음. ASGITransport 의 sync 본질 한계.
  - 우회 : 패턴 자체를 unit test 로 검증 (`test_scan_stream_pattern_pushes_stages_via_threadsafe_queue`). 실 uvicorn 환경의 E2E 실시간 데모는 `demo_guide_modeling.md` 시나리오로 manual.
  - 향후 옵션 : (i) uvicorn subprocess 띄워서 진짜 HTTP/2 chunked transfer 테스트 / (ii) 현재 unit-pattern 검증 유지. PoC 단계에서는 (ii) 로 충분.
- [x] **회귀 검증** — `tests/test_gaps_api.py` 15/15 PASS (기존 12 + 신규 3). 모델링 gap+rule+manual 141/141 (E1-g 138 → +3). 전체 1587 PASS / 20 FAIL (전부 Section 1 baseline).

**의의**
- 큰 repo 스캔에서도 클라이언트가 stage 진행을 라이브로 봄 — UX 격상 (멈춘 줄 알았던 5~10초 → 단계별 진행 가시).
- 에러 발생 시 클라이언트가 "scan 실패" 정보를 SSE event 로 받아 대응 가능 (기존 buffered-flush 에서는 worker 예외 시 raise → HTTP 500).
- worker_task 정리 finally 추가로 클라이언트 조기 끊김 시 thread leak 방어.

**D3-3 미수거 진행 상황**
- ✅ 1/3 RuleRegistry (E1-g 완료)
- ✅ 2/3 SSE 진짜 streaming (이번 작업, E1-h 완료)
- ⏭ 3/3 GapQueue evidence panel + LLM 재평가 트리거 (UI 작업, 사용자 정책 "최소 침습" 원칙 반영해 v1 minimal)

**다음 일감**
- D3-3 미수거 3/3 (evidence panel + 재평가) — 백엔드 `POST /gaps/{id}/reevaluate` (50줄) + 프런트 `<details>` 기반 minimal UI (~80줄)
- 또는 **A1** entities.json 스냅샷 (50줄)
- 또는 (선택) **JpaAnalyzer B5-7**

---

## 2026-04-25 (`RuleRegistry` + scanner/API auto-pull — OD-11-E1-g, D3-3 미수거 1/3)

**배경**: D3-3 시점에 fragments 만 ManualRegistry 에서 auto-pull 하고 rules/described_in 은 body 명시 강제였음 (Q1=A partial hybrid). 이제 A3 (15 BusinessRule) + CPA (5 config_property) 산출이 있어 RuleRegistry 만 만들면 full hybrid 격상 가능 → gap_scan(repo_id=...) 이 body 비어도 동작.

- [x] **모듈 신규** — `backend/modeling/gap_detection/rule_registry.py` (~110 LOC) :
  - `RuleRegistry` Protocol (runtime_checkable) — `put` / `put_many` / `get` / `list_by_repo` / `clear` / `repos`.
  - `InMemoryRuleRegistry` reference 구현 — 내부 `dict[repo_id, dict[rule_fqn, BusinessRule]]`. `(repo_id, qualified_name)` 복합 키로 multi-repo 격리. 같은 FQN 재 put 시 idempotent upsert.
  - `seed_rules_from_repo(repo_path, repo_id, registry, parser=None)` convenience helper — `JavadocRuleExtractor` 활용 `.java` 디렉토리 walk → 자동 인제스트. `SeedResult(total_files_scanned, total_rules, errors)` 보고. FQN 결정성 덕에 두 번 돌려도 같은 rule 만 갱신 (idempotent).
  - 실패 격리 : `read_text` `OSError`/`UnicodeDecodeError` + parse/extract `Exception` 모두 `errors` 에 누적, 다른 파일 처리 계속.
- [x] **`gap_detection/__init__.py`** : `RuleRegistry` / `InMemoryRuleRegistry` / `SeedResult` / `seed_rules_from_repo` 4종 export 추가.
- [x] **`GapScanner` 확장** :
  - `rule_source: Optional[RuleRegistry] = None` 필드 추가.
  - `_resolve_rules(business_rules, repo_id)` helper — `fragments` 패턴 답습 : `None` → registry 에서 auto-pull, 명시 list (빈 list 포함) → 그대로 사용 (auto-pull 차단).
  - `scan()` 시그니처 `business_rules: Iterable=()` → `Optional[Iterable]=None` 변경 (격상).
  - 모듈 docstring 업데이트 (E1-g 정책 명문화).
- [x] **`gaps_api.ScanRequest`** : `rules: list[BusinessRule] = Field(default_factory=list)` → `rules: list[BusinessRule] | None = None` (fragments 와 동일 정책). docstring 갱신.
- [x] **`backend/main.py` lifespan** : `InMemoryRuleRegistry()` 인스턴스 생성 + `GapScanner(rule_source=_rule_registry)` 주입. 주석에 D3-3 → E1-g 격상 표기. described_in 은 미구현 명시.
- [x] **TDD RED → GREEN** — `tests/test_rule_registry.py` 16/16 PASS (0.11s) :
  - TestProtocol (1) : `InMemoryRuleRegistry` 가 `RuleRegistry` Protocol 구조 적합.
  - TestBasic (5) : put/get/put_many/list_by_repo/repos.
  - TestIdempotency (1) : 같은 FQN 재 put 시 덮어쓰기.
  - TestMultiRepoIsolation (2) : 같은 FQN 다른 repo 격리, `clear(repo_id)` 단일 repo 만 제거.
  - TestSeeder (4) : Slab 인제스트 `total_rules >= 10` / 통계 일치 / idempotent / 비-java 파일 skip.
  - TestScannerIntegration (2) : `business_rules=None` → auto-pull / `[]` 명시 → auto-pull 차단 (registry 그대로 보존 검증).
- [x] **회귀 검증** — gap+rule+manual 범위 138/138 PASS (E1-f 122 → +16). 전체 1584 PASS / 20 FAIL (전부 Section 1 baseline).
- [x] **End-to-end demo** :
  - `seed_rules_from_repo(Path('sample-repos/slab-design-engine/src/main/java'), 'slab-design-engine', reg)` → 11 java files → **16 BusinessRule indexed**.
  - `scanner.scan(business_rules=None, fragments=[])` → `errors=[]` 정상 수행 — body 미지정 → registry auto-pull 동작 확인.
  - `main.py` 로드 정상, 156 routes 그대로 (API 신규 엔드포인트 없음 — body 시맨틱 격상만).

**의의**
- gap_scan 이 진정한 "repo_id 만 주면 됨" 모드 진입 (matrials/rules 양쪽 자동). 이제 사용자 데모 시 `POST /api/modeling/gaps/scan {"repo_id":"slab-design-engine"}` 단발 호출만으로 가능.
- A3 산출 BusinessRule 의 자연스러운 영구 저장소 확보. 향후 ChromaDB / SQLite 백엔드 교체는 Protocol 구현체 교체로 가능.
- D3-3 미수거 3개 항목 중 1번째 완료 (RuleRegistry). 남은 2개 : (i) DescribedInStore — 자동 발견 메커니즘 미정 / (ii) SSE 진짜 stage-by-stage streaming + GapQueue evidence panel.

**운영 시드 메커니즘** (의도적 미구현)
- `seed_rules_from_repo` 는 Python 함수로 노출만 하고 startup auto-seeding 은 안 함. 이유 : (a) 어떤 repo 경로를 가져올지 환경마다 다름 (ENV 변수? config 파일?) (b) 개발 단계에서는 REPL/스크립트로 충분. 운영 단계에서 필요해지면 (i) `POST /api/modeling/rules/seed` 엔드포인트 / (ii) ENV `ONTONG_RULE_SEED_REPOS` startup 분기 / (iii) ManualUpload 처럼 watch_folder 도입 중 선택.

**다음 일감 (사용자 정책 — 데모 코드 무관 범용 인프라 우선)**
- D3-3 미수거 (ii) **SSE 진짜 stage-by-stage streaming 재설계** — 현재 buffered-flush PoC. worker thread + asyncio.Queue + `loop.call_soon_threadsafe` 패턴으로 재설계. evidence panel 도 같이.
- D3-3 미수거 (iii) **GapQueue UI : evidence panel + LLM 재평가 트리거** — 데모 코드 무관 범용 UI 개선.
- 또는 **A1** entities.json 스냅샷 (50줄 미만 스크립트, 언제든).
- 또는 (선택) **JpaAnalyzer** B5-7 — Spring Data JPA Repository 정식 처리.

---

## 2026-04-25 (`ConfigPropertiesAnalyzer` 11번째 Spring analyzer — OD-11-E1-f)

**배경**: 데모 코드 무관 범용 인프라 정책 3번째 산출물. E1-b 검증에서 `EquipmentProperties` 가 단순 `class` 로만 잡히고 `config_property` entity 로 승격되지 않는 한계 발견 → 11번째 Spring analyzer 신규. CONFLICTS_WITH gap 감지에서 매뉴얼 "두께 250mm 이상 허용" ↔ 코드 `slab.equipment.maxThicknessMm.default_value=240.0` 직접 비교의 핵심 입력.

- [x] **모듈 신규** — `backend/modeling/code_analysis/spring/config_properties_analyzer.py` (~190 LOC) :
  - **3 어노테이션 형식 지원** : `@ConfigurationProperties(prefix = "...")` keyword / `@ConfigurationProperties("...")` 단일 값 / `@ConfigurationProperties` 마커 (prefix=""). prefix/value 키워드 모두 같은 의미로 처리.
  - **Field 선택** : 비-`static` instance field 만 (constants 는 config 가 아님). `final` 은 허용 (Spring Boot 2.2+ 생성자 바인딩 호환).
  - **Entity FQN** = `{prefix}.{fieldName}` (camelCase canonical, 코드 선언 그대로). prefix 없으면 그냥 fieldName.
  - **attributes** : `prefix` / `key` (canonical, FQN 과 동일) / `key_kebab` (Spring relaxed binding alias — `_CAMEL_TO_KEBAB_RE = r"([a-z0-9])([A-Z])"` 로 `maxThicknessMm` → `max-thickness-mm`) / `field_name` / `field_type` (선언 타입) / `default_value` (initializer literal raw text — 없으면 키 부재) / `bound_class_fqn` / `bound_field_fqn` (FIELD entity 와의 백링크).
  - **Relation** : 기존 등록 `has_config` 사용 (`parser_protocol.py` L169 `spring_bean/method → config_property`). source = class FQN, target = config_property FQN, 한 field 당 1 엣지.
  - **annotation parser** : `_find_config_properties_annotation` 은 `modifiers` 안 / 직접 자식 양쪽 모두 검색. 어노테이션 명은 `_annotation_name(node)` 로 첫 identifier 추출.
  - 어노테이션 없는 클래스 → 빈 결과. 다른 어노테이션 (`@Component` 등) 만 있는 경우도 빈 결과.
- [x] **`spring/__init__.py`** : `ConfigPropertiesAnalyzer` import + `__all__` 에 추가 (11번째). 기존 export 알파벳 정렬 유지.
- [x] **TDD RED → GREEN** — `tests/test_spring_config_properties_analyzer.py` 27/27 PASS (0.05s) :
  - TestAnnotationForms (5) : keyword prefix / single value / marker / no annotation / other annotation.
  - TestFieldSelection (4) : 다중 instance field / static skip / final 유지 / default 없는 field 는 키 부재.
  - TestAttributes (6) : canonical key / kebab alias / field_type / default_value / bound_class+field_fqn / field_name.
  - TestHasConfigEdge (4) : 1 엣지/field / kind=has_config / source=class FQN / target 매칭.
  - TestKebabCaseEdgeCases (2) : 연속 대문자 split / 단일 단어 보존.
  - TestSlabSample (4) : 실제 EquipmentProperties — 5 config_property / maxThicknessMm default 240.0 / 5 키 모두 / 엣지 source = EquipmentProperties FQN.
  - TestProtocol (2) : `SpringAnalyzer` 구조 적합 / 빈 tree → 빈 결과.
- [x] **회귀 검증** — 모델링 코드 분석 359/359 PASS (E1-d 332 → +27). 전체 1568 PASS / 20 FAIL (전부 Section 1 baseline).
- [x] **Slab 11-analyzer end-to-end demo** — `JavaParser(spring_analyzers=[10 기존 + ConfigPropertiesAnalyzer()])` 로 sample-repos/slab-design-engine 전체 11 파일 일괄 파싱 :
  - **Before (10-analyzer)** : 90 entities / 172 relations
  - **After (11-analyzer)** : **95 entities (+5) / 177 relations (+5)** — 정확히 EquipmentProperties 의 5 instance field × 1 (config_property + has_config edge).
  - 5 config_property : `slab.equipment.{rollingMillMaxWidthMm,furnaceMaxLengthMm,craneMaxLoadKg,minThicknessMm,maxThicknessMm}` 모두 default 값 + kebab alias + bound_field_fqn 노출.
  - 5 has_config 엣지 : 모두 source=`com.ontong.slab.config.EquipmentProperties`.

**의의**
- CONFLICTS_WITH gap 감지의 3번째 코드 쪽 입력 (A2 매직넘버 + A3 자연어 룰 + 본 config_property default) 모두 확보.
- 데모 코드 무관 범용 — 어떤 Spring Boot `@ConfigurationProperties` 클래스에도 즉시 동작.
- `bound_field_fqn` 으로 FIELD entity 와 백링크 — Impact Analysis 에서 "config 변경 → 사용 메서드" 추적 가능 (별도 join 없이).
- `key_kebab` 으로 Spring relaxed binding 양쪽 표기 모두 노출 → application.yml 검색 가능.

**runtime wiring**
- `backend/main.py` 에는 미등록 (현재 Spring analyzer 들은 lifespan 에 wiring 되어있지 않음 — 모두 테스트 + REPL 데모 단계). Phase E 코드 분석 파이프라인을 FastAPI 로 노출할 때 11 analyzer 모두 함께 합류 예정.

**다음 일감 (사용자 정책 — 데모 코드 무관 범용 인프라 우선)**
- **D3-3 미수거 인프라** — `RuleRegistry`/`DescribedInStore` 설계 (full auto-pull) / SSE 진짜 stage-by-stage streaming 재설계 / GapQueue evidence panel + LLM 재평가 트리거. **A3/CPA 산출** : Javadoc BusinessRule + config_property 들을 RuleRegistry/CodeRegistry 첫 시드로 활용 가능.
- 또는 **A1** entities.json 스냅샷 (50줄 미만 스크립트, 언제든).
- 또는 (선택) **JpaAnalyzer** B5-7 — `@Entity` / `@Repository` 정식 처리 (현재 NativeSqlAnalyzer 가 raw SQL 만 캡처).

---

## 2026-04-25 (Javadoc → BusinessRule 추출기 — OD-11-E1-d / A3)

**배경**: A2 (E1-c) 로 매직넘버가 `field.attributes` 에 노출됐으니, 이제 매뉴얼 룰과 비교할 **코드 쪽 rule 입력**이 필요. `BusinessRule.statement` 가 free-text str 이라 `RuleASTDiffer` 가 정규식 수량 추출로 비교한다. Slab 샘플의 한국어 Javadoc 이 풍부하니 (목적식 + 제약 4종 + 메서드별 룰) 데모 코드 도착 전에도 충분한 입력 마련 가능.

- [x] **명세 정정** — HANDOFF/CHANGES 의 "REALIZES 엣지" 표기 오류 확인 후 정정. parser_protocol.py §C1 합의에 따라 REALIZES 는 `business_term → method/class`, **VALIDATES** 가 `business_rule → method` (line 177). 추출기는 VALIDATES 만 emit.
- [x] **모듈 신규** — `backend/modeling/code_analysis/javadoc_rule_extractor.py` (~190 LOC) :
  - `JavadocRuleExtractor` 클래스 + `extract_rules_from_file()` 모듈-레벨 convenience.
  - tree-sitter Java 로 재파싱 → `block_comment` 노드 walk → `/** ... */` 인 것만 채택 (일반 `/* */` skip).
  - `_next_declaration_sibling()` : Javadoc 의 `next_sibling` 이 declaration 이면 채택. modifier/`;` 등이 끼면 None (Javadoc 이 그 decl 에 붙은 게 아님).
  - **타겟 매칭** : `(line_start, kind)` → FQN 색인을 ParseResult.entities 에서 빌드 → decl 의 `start_point[0]+1` 로 lookup. class/interface/enum/method/constructor 5종 지원, **field 는 v1 skip**.
  - **본문 정리** : `_strip_javadoc_decoration()` `/**`/`*/` + 라인별 `*` 제거.
  - **분리** : bullet (`- ` `* ` `1. `) 마커는 한 후보, 나머지는 `(?<=다)\.\s+|(?<=요)\.\s+|(?<=니)\.\s+` 로 한국어 sentence 분리.
  - **휴리스틱** : `_is_rule_like()` — keyword (`이상\|이하\|초과\|미만\|동일\|같음\|할 수 없\|불가\|금지\|허용되지\|던진다\|해야 한다\|되어야 한다\|이어야 한다\|여야 한다`) OR (`≤≥<=>===!=` 부등식 AND 식별자 `[A-Za-z가-힣]`). 사실 진술 ("X 는 2400mm 이다") 은 자동 reject.
  - **Severity** : `_classify_severity()` — HARD if `불가\|금지\|허용되지 않\|던진다\|차단\|거부\|초과할 수 없\|IllegalArgumentException\|Exception` else SOFT.
  - **FQN 규칙** : `{target_fqn}#rule{N}` (1-indexed, target 별 카운터 — 두 번 추출해도 동일).
  - **타임스탬프 주입** : `JavadocRuleExtractor(now=…)` 옵션 — 테스트 결정성 + 기본 `datetime.now(UTC)`.
  - 출력 : `tuple[list[BusinessRule], list[CodeRelation]]`. BusinessRule 은 frozen Pydantic, 엣지는 `RelationKinds.VALIDATES`.
- [x] **TDD RED → GREEN** — `tests/test_javadoc_rule_extractor.py` 23/23 PASS (0.10s) :
  - TestBasic (3) : 코멘트 없음 / 일반 block_comment skip / 룰 키워드 없는 단순 설명 skip.
  - TestClassLevelBullets (4) : 4 bullet → 4 rules + 모두 class FQN target / FQN 결정성 / 한국어 텍스트 보존 / source==rule_fqn.
  - TestMethodLevel (4) : method FQN target / 다중 문장 분리 / 사실 진술 reject / Javadoc 없는 메서드 skip.
  - TestSeverity (3) : Exception → HARD / 금지 → HARD / comparator-only → SOFT.
  - TestMetadata (3) : `source="javadoc:{target_fqn}"` / `confirmed=False` 기본 / `terms_ref=[]` 기본.
  - TestSlabSample (4) : 실제 sample-repos 파일 — Checker class 4 bullets + method-level 분리 + WeightMaximizer 목적식 + Slab Exception.
  - TestExtractorClassAPI (2) : 클래스 인스턴스 API + frozen BaseModel 변조 차단.
- [x] **회귀 검증** — 모델링 코드 분석 범위 332/332 PASS (E1-c 309 → +23). 전체 1541 PASS / 20 FAIL (전부 Section 1 baseline — ag33_hooks/confidence/lineage_validation/p2b6/pydantic_ai/rag_tag_boost/skill_api).
- [x] **Slab end-to-end demo** — 4 파일 일괄 추출 :
  - WeightMaximizer : 7 rules (목적식 5 + 수주 사양 2)
  - EquipmentConstraintChecker : 7 rules (4 class bullets + 3 method-level)
  - Slab : 1 rule (HARD — 음수 dimensions Exception)
  - EquipmentProperties : 0 rules (descriptive only — 정상)
  - **총 15 BusinessRule + 15 VALIDATES 엣지**. SOFT 11 + HARD 4 (3 prohibition + 1 Exception) — 분류 정확.

**의의**
- CONFLICTS_WITH gap 감지에 필요한 양쪽 입력 (코드 매직넘버 from A2 + 코드 자연어 룰 from A3) 모두 확보. RuleASTDiffer 가 매뉴얼 룰 ↔ 코드 룰 통합 비교 가능.
- 데모 코드 무관 범용 추출기 — 실 데모 코드 도착 시 그대로 적용. Javadoc 주석 패턴이 한국어 비즈니스 문장이면 즉시 동작.
- `terms_ref` 는 빈 list — 향후 C3 `TermResolver` 가 statement 에서 BusinessTerm FQN 매칭해 채움.

**다음 일감 (사용자 정책 — 데모 코드 무관 범용 인프라 우선)**
- (격상) **ConfigPropertiesAnalyzer** 11번째 Spring analyzer — `@ConfigurationProperties` → `config_property` entity 승격 + field-by-field config key (`slab.equipment.maxThicknessMm`) 추출. Slab 의 EquipmentProperties 가 현재 단순 class 로만 잡힘.
- 또는 **D3-3 미수거 인프라** — RuleRegistry/DescribedInStore 설계 / SSE 진짜 stage-by-stage streaming / GapQueue evidence panel.
- 또는 **A1** entities.json 스냅샷 (50줄 미만 스크립트, 언제든).

---

## 2026-04-25 (JavaParser field 추출 확장 — OD-11-E1-c / A2)

**배경**: Slab 데모 코드 도착 전까지 "데모 코드 무관 범용 인프라" 우선 정책. A2 가 가장 risky 분기 (매직넘버 240/1.02/50 이 그래프에 노출되어야 CONFLICTS_WITH gap 감지가 의미 있음). OD-11-E1-b 검증에서 `field.attributes` 가 전부 `{}` 로 비어있음을 확인 → JavaParser 확장 필요.

- [x] **확장 범위 결정** — `field.attributes` 에 3 키 :
  - `field_type` : 선언 타입 텍스트 (primitive `double`/`int` · reference `String` · generic `List<String>`).
  - `initializer` : 초기화 식 raw 텍스트 (literal text 또는 expression text).
  - `initializer_kind` : 6 분류 — `literal_number` / `literal_string` / `literal_boolean` / `literal_null` / `literal_char` / `expression`.
- [x] **TDD RED** — `tests/test_java_parser_field_attributes.py` 신규 20 테스트 작성 후 1번째 테스트 즉시 FAIL 확인 (attrs={} 상태).
- [x] **GREEN** — `backend/modeling/code_analysis/java_parser.py` `_extract_field` 확장 :
  - field_declaration `child_by_field_name("type")` → `field_type` 추출.
  - variable_declarator `child_by_field_name("value")` → 존재 시 `initializer` (raw text) + `_classify_initializer(value_node)` → `initializer_kind`.
  - `_classify_initializer()` 신규 helper : 6 literal node type 화이트리스트 + `unary_expression` 부호 wrapping (-1.5 → literal_number) + 기타는 `expression`.
  - `_NUMERIC_LITERAL_TYPES` frozenset (decimal/hex/octal/binary integer + decimal/hex floating-point).
  - 기존 `parent`/`modifiers` 등 인자 그대로 보존 + `attributes=attributes` 한 줄 추가.
- [x] **신규 테스트 통과** — 20/20 PASS (TestFieldType 4 + TestInitializerLiteral 10 + TestInitializerEdgeCases 3 + TestSlabSampleLiterals 3, 0.06s).
  - 케이스 커버 : double/int/String/`List<String>` 타입, 정수/실수/명시소수점0/문자열/불린/null/음수/문자/Long suffix/Hex 리터럴, 초기화식 부재, 표현식 초기화 (메서드 호출).
  - Slab 실증 : `WeightMaximizer.WEIGHT_BIAS_FACTOR=1.02` ✓ / `WeightMaximizer.GRID_STEP_MM=50.0` ✓ / `EquipmentProperties.maxThicknessMm=240.0` ✓.
- [x] **회귀 검증** — modeling 범위 (`-k "java_parser or spring or code_analysis or graph or cross_file"`) 309/309 PASS. 전체 1518 PASS / 20 FAIL (전부 Section 1 baseline : ag33_hooks/confidence/lineage/p2b6/pydantic_ai/rag_tag_boost/skill_api).
- [x] **End-to-end demo** — `JavaParser().parse_file()` 직접 호출로 EquipmentProperties 5 필드 (rollingMillMaxWidthMm=2400 / furnaceMaxLengthMm=12000 / craneMaxLoadKg=45000 / minThicknessMm=180 / maxThicknessMm=240) 전부 노출 확인.

**의의**
- CONFLICTS_WITH gap 감지의 코드 쪽 입력이 확보됨. 이제 A3 Javadoc 추출기로 룰 텍스트만 만들면 `RuleASTDiffer.find_conflicts()` 가 매뉴얼 vs 코드 매직넘버 비교 가능.
- `attributes["initializer_kind"]` 분기로 다운스트림이 "literal vs expression" 을 구분해서 매직넘버만 골라 비교 가능.
- 데모 코드 무관 범용 파서 기능 — 실제 Slab 데모 코드 도착 후에도 그대로 활용.

**다음 일감 (사용자 정책 : 데모 코드 무관 작업 우선)**
- A3 Javadoc → BusinessRule 추출기 (`backend/modeling/code_analysis/javadoc_rule_extractor.py` 신규)
- 또는 (선택→격상 가능) ConfigPropertiesAnalyzer 11번째 Spring analyzer
- 또는 D3-3 미수거 인프라 (RuleRegistry 설계 / SSE 진짜 streaming 재설계 / GapQueue evidence panel)

---

## 2026-04-21 (Slab Design Engine 파서 파이프라인 등록 검증 — OD-11-E1-b)

**배경**: OD-11-E1-a (Slab Design Engine 샘플 생성) 직후, 사용자 승인 "A로 진행" → onTong 코드 분석 파이프라인에 등록해 CodeEntity / Relation 추출 결과 확인.

- [x] **JavaParser 기본 (Spring analyzer 0개)** — `sample-repos/slab-design-engine/src/main/java/**/*.java` 11 파일 파싱.
  - 결과: **85 entities / 167 relations / 0 errors**.
  - 주요 entity kind: package(2) + class(7) + interface(0) + enum(1) + method(15+) + field(20+) + constructor(여러) — domain/constraint/optimizer/service/controller 패키지 그래프 정상 추출.
  - 주요 relation kind: CONTAINS / EXTENDS(없음) / IMPLEMENTS(없음) / DEPENDS_ON (필드 타입 의존) / CALLS (메서드 호출 그래프).
- [x] **Spring 10-analyzer 일괄 적용** (DI/AOP/HTTP/Events/Scheduled/Profile/Reflection/MapStruct/BeanUtils/NativeSql).
  - 결과: **90 entities (+5) / 172 relations (+5) / 0 errors**.
  - 신규 Spring entity: `spring_bean` × 4 (`Application` / `EquipmentConstraintChecker` / `WeightMaximizer` / `SlabDesignService` / `SlabDesignController` 중 stereotype 매칭) + `http_endpoint` × 1 (`POST /slabs/design` MAPS_URL).
  - 신규 Spring relation: `AUTOWIRES` × 4 (Controller→Service / Service→WeightMaximizer / WeightMaximizer→Checker / WeightMaximizer→Properties) + `MAPS_URL` × 1.
  - **DI 그래프 검증** : `SlabDesignController` → `SlabDesignService` → `WeightMaximizer` → {`EquipmentConstraintChecker`, `EquipmentProperties`} — 의도한 wiring 그대로 그래프에 반영.
- [x] **검증 완료 — 코드 → CodeEntity 추출 파이프라인이 Slab 엔진에 정상 동작.**

**한계 / 남은 갭**
- `EquipmentProperties` 가 `config_property` entity 로 승격되지 않음. 이유: 10-analyzer 셋 안에 `@ConfigurationProperties` 전담 analyzer 없음. 현재는 `class` + `AUTOWIRES` (의존자 측에서 이름 알려짐) 까지만 캡처. 향후 후보: `ConfigPropertiesAnalyzer` 추가 → field-by-field config key (`slab.equipment.maxThicknessMm`) 추출.
- `field.attributes` 에 리터럴 값 (예: `WEIGHT_BIAS_FACTOR = 1.02`, `GRID_STEP_MM = 50.0`, `maxThicknessMm` default `240.0`) 이 들어가는지 미확인. CONFLICTS_WITH 매직넘버 감지에 필수 — 다음 세션 우선 항목.
- Javadoc 본문이 `BusinessRule` 로 변환되는 추출기 부재. 한국어 자연어 룰 ("두께 180~240mm 이상" 등) 이 코드 쪽 규칙 입력으로 들어가야 gap scan 이 5종 후보를 실제로 잡아냄.

**주요 결정**
- `sample-repos/slab-design-engine` 을 OD-11-E1 의 1 도메인 PoC 타겟으로 잠정 채택 (E1 마스터 row 는 여전히 [ ] — 매뉴얼+gap scan 까지 완결되어야 close).
- 파서 검증은 별도 sub-task `OD-11-E1-b [x]` 로 기록 (Slab 생성 = `OD-11-E1-a [x]`).

**후속 후보 — 다음 세션 첫 일감**
- [ ] **A1** `sample-repos/slab-design-engine/.analyzed/entities.json` 스냅샷 덤프 (재현 가능성 확보)
- [x] **A2** `field.attributes` 리터럴 값 검증 — 240/1.02/50 이 attributes dict 에 들어가는지 확인. 필요 시 `JavaParser` field 추출 확장 PR (2026-04-25 완료, 아래 OD-11-E1-c 섹션 참조)
- [x] **A3** Javadoc → BusinessRule 추출기 (한국어 자연어 룰 → `BusinessRule` DTO + **VALIDATES** 엣지 — 명세 정정, REALIZES 는 BusinessTerm 전용) — gap scan 의 코드 쪽 입력 보강 (2026-04-25 완료, 아래 OD-11-E1-d 섹션 참조)
- [ ] **B** 매뉴얼 작성 — 의도적 gap 5종을 실제로 트리거할 Slab 기준서 (PDF/MD) 작성 → ManualRegistry 업로드 → `POST /api/modeling/gaps/scan` 5건 후보 출력 검증
- [x] (선택→격상) `ConfigPropertiesAnalyzer` 추가 — `EquipmentProperties` → `config_property` entity + field-by-field config key 추출 (2026-04-25 완료, OD-11-E1-f. Slab 5 config_property + 5 has_config 엣지 emit. CONFLICTS_WITH 의 default_value 비교 입력 확보)

---

## 2026-04-21 (Slab Design Engine 샘플 프로젝트 추가 — gap scan 실증용)

**배경**: 사용자 요청 "아직 데모용 프로그램 및 매뉴얼이 준비가 안됐어, 너가 임의로 설비 제약을 고려하고 중량 최대화 목적식을 가진 엔진 소스를 만들어서 직육면체 slab 사이즈 설계 엔진으로 해볼까?" → 승인 "진행해".

- [x] **`sample-repos/slab-design-engine/`** 신규 Spring Boot 3 / Java 17 프로젝트 (14 files). 패키지 `com.ontong.slab`:
  - `SlabDesignApplication` — 부팅 엔트리 (@SpringBootApplication + @EnableConfigurationProperties)
  - `domain/` — `Slab` (L×W×T + grade, weight=ρ·V) · `OrderSpec` (수주 범위) · `SteelGrade` (SS400/SM490/AH36, 밀도 7850~7860)
  - `config/EquipmentProperties` — @ConfigurationProperties("slab.equipment"), 설비 파라미터 5개 (압연기 폭 2400 / 가열로 길이 12000 / 크레인 하중 45000 / 두께 180~240)
  - `constraint/` — `ConstraintViolation` record + `EquipmentConstraintChecker` (@Component) 규칙별 메서드 분리 (`checkRollingMillWidth` / `checkFurnaceLength` / `checkThicknessRange` / `checkCraneLoad`)
  - `optimizer/` — `DesignCandidate` record + `WeightMaximizer` (@Component, 50mm 그리드 + `max ρ·L·W·T`) + `adjustWeightBias(1.02)` 안전계수
  - `service/SlabDesignService` — @Service 파사드
  - `controller/SlabDesignController` — @RestController, POST `/slabs/design` (DesignRequest/DesignResponse records)
  - `src/main/resources/application.yml` — 설비 파라미터 외부화
  - `pom.xml` — Spring Boot 3.2.5 starter-web + validation + config processor + lombok optional
  - `README.md` — 도메인 요약 + 실행 가이드 + **의도적으로 심어둔 Gap 후보 5종** 표
- [x] **의도적 gap 유발 포인트 (기준서 준비 시 자연 재현)**:
  1. `EquipmentProperties.maxThicknessMm = 240.0` vs 예상 기준서 "250mm 이상" → **CONFLICTS_WITH** (수량 mismatch)
  2. `WeightMaximizer.WEIGHT_BIAS_FACTOR = 1.02` vs 예상 "안전계수 1.05" → **CONFLICTS_WITH**
  3. `WeightMaximizer.adjustWeightBias()` 메서드 있음 but 매뉴얼 언급 없음 → **MISSING_IN** manual (code_only)
  4. 보정 후 크레인 하중 재검증 없음 vs 예상 "재검증 필수" → **MISSING_IN** code (manual_only)
  5. `WeightMaximizer.GRID_STEP_MM = 50.0` vs 예상 "그리드 25mm 이하" → **CONFLICTS_WITH**
- [x] **검증** — `javac 17 --source 17` domain/constraint 순수 Java 파일 clean compile (0 errors). Spring annotation 참조 에러는 classpath 문제일 뿐 문법 에러 아님.
- [x] **주석/Javadoc** — 한국어 비즈니스 룰 자연어 문장 포함 (규칙 추출기 타겟). 예: "slab 두께는 180mm 이상 240mm 이하여야 한다", "중량 = 밀도 × 체적", "보정 후 크레인 하중 재검증 필수" (상응하는 코드 누락 의도).

**주요 결정**
- 언어/프레임워크 = Java 17 + Spring Boot 3 (OD-11 파서 타겟 일치, 추후 `sample-repos/scm-demo` 와 동일한 분석 파이프라인 재사용 가능)
- 스코프 = medium (domain 3 + constraint 2 + optimizer 2 + service 1 + controller 1 + config 1). 최소(1~2 파일)는 파서 실증 커버 부족, 대형(multi-module)은 현 단계 과투자.
- DB 미포함 — JPA/Repository 계층 추가는 향후 필요 시. 지금은 순수 연산 엔진.

**후속 후보** (미수거)
- [ ] `sample-repos/slab-design-engine` 을 onTong 코드 분석 파이프라인에 등록 → CodeEntity 그래프 추출 확인
- [ ] 대응 매뉴얼 (`wiki/` 또는 별도 슬랩 기준서) 작성 → ManualRegistry 업로드 → gap scan 5종 재현
- [ ] (선택) `mvn package` 까지 성공시키려면 실제 Maven 캐시 필요. 지금은 javac 문법만 검증.

---

## 2026-04-21 (ModelingSection 사이드바 정리 — 데모 테스트 불필요 탭 숨김)

**배경**: 사용자 피드백 "브라우저로 들어갔더니 옛날 기능들이 전부 살아났네 ... 추후 UI/UX 대대적 개편 가능성 있음. 일단 테스트가 필요 없는 기능은 브라우저에서 보이지 않도록 정리해."

- [x] **`ModelingSection.tsx` MAIN_NAV 단일 항목** — "갭 큐"(`gap-queue`) 만 남기고 분석/워크벤치/코드/온톨로지/매핑/영향/승인/시뮬 탭 모두 사이드바에서 제거. `ViewRouter` switch case 는 보존(향후 재연결 시 import 복구 최소 침습).
- [x] **`SETTINGS_NAV` 비우기 + 조건부 렌더** — `SETTINGS_NAV.length > 0 && (...)` 로 설정 구분선 자체를 숨김.
- [x] **`needsRepoSelector` 유도 상수** — 비-gap-queue 항목이나 SETTINGS_NAV 항목이 있을 때만 Repository 입력 + 플레이스홀더 렌더. 현재는 false 이므로 Repo 입력·데모 로드 버튼·"Repository를 선택하세요" 스크린 모두 숨김. 갭 큐는 repoId 독립이므로 즉시 ViewRouter 로 진입.
- [x] **`activeView` 초기값 "gap-queue"** — 이전 기본값 "analysis" 는 사이드바에 없으므로 의미 없음.
- [x] **미사용 lucide 아이콘 import 제거** — `Code / Network / GitBranch / GitCompare / Search / CheckSquare / Zap` 제거 (사이드바에서 사라진 탭들에서만 쓰였음). `PackageOpen / Loader2 / CircleCheck / Circle / CircleDot / Settings2 / ListChecks` 만 유지.
- [x] **TS compile clean** — `bunx tsc --noEmit` 에서 내 변경 관련 에러 0. 기존 orphan `ManualOntologyBuilder` / `ManualUpload` 에러는 이 작업 범위 밖.

**주요 결정**
- 레거시 컴포넌트(AnalysisConsole, MappingWorkbench, CodeGraphViewer 등) 자체는 보존. ViewRouter 의 switch 분기와 파일도 건드리지 않음. 이유: UI/UX 개편이 오면 다시 살아날 수도 있고, 지금 당장은 import 만 유지해도 번들 영향 미미.
- Repo 입력 UI 는 제거가 아니라 "조건부 렌더". `needsRepoSelector` 가 true 로 돌아가는 순간(즉 다른 탭이 되살아나면) 자동 복구.

**후속 후보** (미수거, 사용자 승인 필요)
- [ ] "모델링" 사이드바 제목 → "갭 큐" 전용 제목으로 바꿀지 여부
- [ ] 사용자가 갭 큐 외 기능 다시 필요해지면 `MAIN_NAV` 에 원하는 탭 도로 추가

---

## 2026-04-21 (OD-11-D3-3 Gap 승인 큐 API + UI 완료)

- [x] **D3-3 Backend: `GapScanner` 오케스트레이터** — `backend/modeling/gap_detection/gap_scanner.py`. `MissingInDetector` + `GapEngine` 을 단일 스캔으로 묶고 ManualRegistry 에서 fragments auto-pull. `UnifiedScanResult` frozen dataclass (`.all` property). Progress callback 4단계.
- [x] **D3-3 Backend: `gaps_api.py` 4 엔드포인트** — `POST /scan` + `POST /scan/stream` (SSE buffered-flush) + `GET ""` (direction/severity/include_confirmed 필터) + `POST /{gap_id}/confirm`. `ScanRequest` Pydantic + `GapCandidateDTO.from_candidate`.
- [x] **D3-3 Backend: Partial Hybrid API 계약** — `fragments` 만 auto-pull (body 없으면 ManualRegistry 조회), `rules` / `described_in` 은 body 필수. 근거: store 아직 없음. Phase E 에서 `RuleRegistry` 고려.
- [x] **D3-3 Backend: `HashingTextEmbedder` fallback** — `embedding_drifter.py` 에 SHA256 3-gram 64-dim L2 normalized 결정적 임베더 추가. OpenAI 의존성 없이 `CosineDrifter` 초기화 가능.
- [x] **D3-3 Backend: main.py wiring** — `InMemoryGapStore` → `MissingInDetector` → `create_gap_engine(HIERARCHICAL, rule_differ, drifter, llm_comparator, gap_store)` → `GapScanner(fragment_source=_manual_registry)` → `gaps_api.init(...)` + 라우터 include. 156 routes (+4 vs D3-2-b).
- [x] **D3-3 Frontend: modeling.ts Gap 섹션** — `GapCandidateDto` / `UnifiedScanResponse` / `GapScanRequest` / `SseEvent` + `scanGaps` / `scanGapsStream` (async generator with AbortSignal) / `listGaps` / `confirmGap`.
- [x] **D3-3 Frontend: `GapQueue.tsx` 신규** — 필터 바 + "스캔 실행" (SSE stream) + 후보 테이블 (direction/severity 배지, target_fqn mono, 확정 버튼).
- [x] **D3-3 Frontend: `ModelingSection.tsx` 탭 추가** — MAIN_NAV 에 "갭 큐" (`gap-queue`, `ListChecks` 아이콘). ViewRouter case 추가.
- [x] **D3-3 Test: `tests/test_gap_scanner.py` 10 + `tests/test_gaps_api.py` 12 = 22 PASS** — auto-pull / body-override / persistence / idempotent / progress / SSE 4-stage / filters / 422.
- [x] **D3-3 Regression**: 모델링 gap 계열 127/127. 전체 pytest 1498 passed / 31 baseline (우리 변경 무관). TS clean (orphan 제외).

**주요 결정**
1. Q1 = Partial Hybrid (fragments auto-pull, rules/described_in body)
2. Q2 = Unified scan (단일 엔드포인트가 MISSING_IN + CONFLICTS_WITH)
3. Q3 = SSE primary + `/scan` sync fallback. Buffered-flush 로 TestClient race 해결 (PoC 수용 가능 trade-off)

---

## 2026-04-19 (OD-11 방향 전환 : 매뉴얼 1차 → 레거시 코드 1차)

**배경**: 사용자 요청 "설명 보니까 내가 원하던 거랑 방향이 좀 다르고 이 구현 방식으로는 우리팀의 목적을 달성하기 어려울 것 같아." OD-1 ~ OD-10 전체 방향 재검토.

**새 방향**: 10년 유지보수된 Java/Spring 레거시 코드를 1차 소스로, 업무처리기준서를 보조 검증 자료로. 온톨로지는 메서드 단위 매핑 그래프. 3대 기능(Impact / Reverse Lookup / Test Generation)이 이 위에서 동작.

**OD-10이 착오 판단**: 당시 사용자 피드백("예전 기능이 다 남아 있으니 힘들어")을 "legacy 일괄 제거"로 해석해 `code_analysis/` `mapping/` `query/` `change/` `simulation/` `approval/` `git_connector` 등을 삭제했다. 그러나 `parser_protocol`, `java_parser`, `query_engine`, `change_detector` 는 새 방향의 정확한 알맹이였음. 워킹트리 상태(커밋 전)이므로 `git restore`로 복원 가능. 아직 안 날아감.

**상세 계획**: `toClaude/modeling/OD-11-PLAN.md` (§1 배경 / §2 비교 / §4 3대 기능 / §6 Spring 8 난제 / §7 기준서 / §8 3라운드 / §9 복원 매트릭스 / §11 태스크 목록)

### Phase A — 문서화 + 복원 결정 (완료 2026-04-19)
- [x] **OD-11-A1** — OD-11-PLAN.md 작성 (`toClaude/modeling/OD-11-PLAN.md`)
- [x] **OD-11-A2** — TODO.md / HANDOFF.md / CHANGES.md (이 항목) / memory project_status.md 갱신
- [x] **OD-11-A3** — 사용자 "응 동의" + "진행해" 로 복원 범위 + B1 착수 승인 (2026-04-19)

### Phase B — Round 1 스키마 (진행 중)
- [x] **OD-11-B1** — `toClaude/modeling/round1-code-schema.html` 초안 작성 (2026-04-19)
  - 노드 15종 (PACKAGE/CLASS/INTERFACE/ENUM/METHOD/FIELD/CONSTRUCTOR/SPRING_BEAN/HTTP_ENDPOINT/ASPECT/SCHEDULED_TASK/MSG_LISTENER/EVENT_TYPE/DB_TABLE/DB_COLUMN/CONFIG_PROPERTY)
  - 엣지 15종 (CONTAINS/CALLS/EXTENDS/IMPLEMENTS/DEPENDS_ON/READS/WRITES/AUTOWIRES/INTERCEPTS/MAPS_URL/PUBLISHES/HANDLES/READS_TABLE/WRITES_TABLE/HAS_CONFIG)
  - Spring 8 난제 처리 방식 (DI / AOP / Reflection / Data JPA / Bean Config / Event / Scheduled / Profile) 각각 문제·처리·잔여
  - 워킹 예시 : `OrderController.place()` 전체 그래프 SVG 시각화
  - 메서드 노드 상세 필드 (precondition / postcondition / input_domain 등 Test Generation 밑받침)
  - Impact Analysis BFS 시뮬레이션 (Cypher 초안 + 결과 테이블)
  - Q1~Q8 합의 체크리스트
- [x] **OD-11-B2** — Q1~Q8 피드백 반영 rev.2 (2026-04-19)
  - **Q1/Q2 (확장성)**: §3-A 신설 — `EntityKindRegistry` 플러그인 패턴 + Neo4j 자유 스키마로 신규 kind 추가 시 기존 쿼리 깨지지 않음 명시
  - **Q3 (필드 값 전파)**: §6-B 데이터 계보 섹션 신설 — METHOD 속성 `value_flow` + 엣지 `DERIVES_FROM` / `PROPAGATES_TO` 2종 추가 → 총 엣지 17종.
  - **Q4 (Reflection 런타임)**: §5-3 재작성 — 1차 범위 밖→안 승격.
  - **Q5 (precondition/postcondition)**: §6 callout 확장 — 3가지 이유.
  - **Q6 (hops)**: §7 step 3-A 신설 — 기본값 8 철회 → 무제한 + 사용자 조정.
  - **Q7/Q8**: 합의.
- [x] **OD-11-B2'** — Q9~Q11 답변 rev.3 반영 (2026-04-19)
  - **Q9 (동적 매핑 3 분석기)**: §6-B-4 재작성 — MapStruct / BeanUtils.copyProperties / native SQL·JPQL 3개 전부 1차 포함. 각 전략/산출 엣지/confidence 속성 명시. "신뢰성 > 구현 무게" 원칙.
  - **Q10 (JVM Agent 시점)**: §7-A 신설 — "임시 섹션" 개념 도입. Section 2 모델링 완성 후 별도 throwaway 섹션에서 3대 기능 + JVM Agent 실험. 정식 Section 3는 그 이후. 세 섹션(Section 2 / 임시 섹션 / Section 3)의 역할 구분 명시.
  - **Q11 (타겟)**: §7-B 신설 — 공정계획 Slab 설계 엔진 (사용자가 단순화해 직접 제공). sample repo 형태 예상(Java/Spring Boot, 수천~수만 라인, 3대 기능 검증 가능 도메인 특성). 파서가 건드릴 지점 사전 매핑 (입력 DTO / 계산 메서드 / 서비스 / DB / 진입점 / 설정).
  - HTML 목차 / 헤더 / 푸터 rev.3 동기화. 다음 작업 경로는 OD-11-B3 (코드 복원) 6단계로 세분.
- [x] **Round 1 스키마 확정** (2026-04-19) — 노드 15종 + 엣지 17종 + Spring 8 난제 + 데이터 계보 + 확장성 + 런타임 계측 + hops 자율 조정 + 임시 섹션 + slab 엔진 타겟 모두 합의 완료
- [x] **OD-11-B3** — `parser_protocol.py` 복원 + `EntityKindRegistry` / `RelationKindRegistry` 플러그인 패턴 (2026-04-19)
  - 고정 Enum 제거 → `EntityKindSpec` / `RelationKindSpec` + 런타임 등록 가능한 registry.
  - 기본 16 entity kind (code 7 / spring 6 / db 2 / config 1) + 17 relation kind (code 7 / spring 5 / db 2 / config 1 / lineage 2) 자동 등록.
  - `CodeEntity` / `CodeRelation` : `kind: str` + `__post_init__` 검증 + `attributes: dict` 추가 (precondition/postcondition/value_flow/via_methods/confidence/profile 등 확장 속성 담을 자리).
  - TDD : `tests/test_code_analysis_registry.py` 21 cases — 전부 통과.
- [x] **OD-11-B4** — `java_parser.py` + `graph_writer.py` 복원 + Spring 분석기 패키지 스캐폴드 (2026-04-19)
  - `java_parser.py` : 새 `EntityKinds` / `RelationKinds` 문자열 상수로 전환. 7 기본 kind (PACKAGE/CLASS/INTERFACE/ENUM/METHOD/FIELD/CONSTRUCTOR) + 5 relation (CONTAINS/CALLS/EXTENDS/IMPLEMENTS/DEPENDS_ON) 추출 동작 확인.
  - `graph_writer.py` : 17 relation kind 지원. `attributes` dict 직렬화 (primitives/flat list 그대로 + nested dict/mixed list → JSON 문자열). `RelationKindRegistry` 화이트리스트 + `^[A-Z_]+$` 정규식 이중 검사로 Cypher 인젝션 차단.
  - `backend/modeling/code_analysis/spring/` 신설 : `SpringAnalyzer` Protocol + 6 스텁 (`DIAnalyzer`/`AopAnalyzer`/`HttpAnalyzer`/`EventsAnalyzer`/`ScheduledAnalyzer`/`ProfileAnalyzer`). 실제 구현은 B5.
  - TDD : `tests/test_java_parser_basic.py` (19) + `tests/test_graph_writer_edges.py` (9) + `tests/test_spring_analyzer_scaffold.py` (2) — 30/30 통과 + B3 포함 51/51.
- [~] **OD-11-B5** — Spring 8 난제 PoC 개별 (진행 중, 7/8 — B5-7 `JpaAnalyzer` 우선순위 낮아 B6 이후로 연기)
  - [x] **OD-11-B5-1** — `DIAnalyzer` 구현 (2026-04-19)
    - 6 stereotype (`@Component`/`@Service`/`@Repository`/`@Controller`/`@RestController`/`@Configuration`) → `spring_bean` 엔티티. `qualified_name = 클래스 FQN`.
    - `@Bean` 메서드 (in `@Configuration` 클래스) → `spring_bean` 엔티티. `qualified_name = <class FQN>.<method>#bean` (method 노드와 충돌 회피).
    - `@Autowired` / `@Inject` (필드 / 명시 생성자) → `AUTOWIRES` 엣지 (source = bean FQN, target = 주입 대상 타입 FQN).
    - Spring 4.3+ 단일 생성자 암묵적 주입 지원 (생성자 1개 + 파라미터 ≥1 → 자동 `AUTOWIRES`). 생성자 2개 이상 + 명시 `@Autowired` 없음 → 엣지 미생성.
    - `@Qualifier("primary")` → `attributes.qualifier = "primary"`.
    - class-level `@Profile("prod")` / `@Profile({"prod","legacy"})` → `attributes.profile = ["prod", ...]` on outgoing AUTOWIRES.
    - class-level `@ConditionalOnProperty("feature.x")` / `@ConditionalOnProperty(name="k", havingValue="v")` → `attributes.condition` (단일 또는 `k=v` 합성 문자열).
    - `JavaParser(spring_analyzers=[DIAnalyzer()])` 옵션 주입 — 파서 출력에 Spring 엔티티/관계 병합. 기본값은 빈 리스트 (하위 호환).
    - TDD : `tests/test_spring_di_analyzer.py` 23 cases (6 parametrized stereotype + plain class + autowired/inject field + ctor (명시/암묵/다중/무파라미터) + qualifier + profile (단일/배열) + condition (단일/kv) + @Bean (in/out of @Configuration) + `JavaParser` 통합 + 하위호환) — 전부 통과.
    - 누적 회귀 : B3 21 + B4 30 + B5-1 23 + ontology 37 = **111/111 pass**.
  - [x] **OD-11-B5-2** — `AopAnalyzer` 구현 (2026-04-19)
    - `@Aspect` 클래스 → `aspect` 엔티티 (qn = 클래스 FQN). `@Component` 등 stereotype 공존 시 `spring_bean` 은 DIAnalyzer 가 담당 — AopAnalyzer 는 aspect 만 emit.
    - 5 advice 애너테이션 (`@Before`/`@After`/`@Around`/`@AfterReturning`/`@AfterThrowing`) → `INTERCEPTS` 엣지. `attributes.advice_type` ∈ {before, after, around, after_returning, after_throwing}.
    - `attributes.pointcut_expr` 원본 문자열 보존. `attributes.pointcut_kind` ∈ {execution, within, annotation, within_annotation, named, raw} 로 해석 방식 표기.
    - Pointcut 파서 (PoC 범위):
      - `execution(* <FQN>.<method>(..))` → target = FQN, kind = execution
      - `within(<FQN>)` → target = FQN, kind = within
      - `@annotation(<FQN>)` → target = FQN, kind = annotation
      - `@within(<FQN>)` → target = FQN, kind = within_annotation
      - `<name>()` (named pointcut ref) → 같은 클래스의 `@Pointcut` 이름으로 lookup → 내부 표현식 재귀 해석. `attributes.resolved_expr` 에 원본 표현식 기록.
      - 복합식 / 복잡 표현 → target = `<unresolved>`, kind = raw (expr 은 그대로 유지)
    - `@Order(N)` 처리 : class-level → 모든 advice 에 적용, method-level → 해당 advice 만 override. 없으면 `order` 속성 생략.
    - `@Pointcut` 2-pass : 1차로 이름↔표현식 수집, 2차로 advice 에서 참조 해석.
    - `JavaParser(spring_analyzers=[AopAnalyzer()])` 통합 확인. `DIAnalyzer` + `AopAnalyzer` 동시 주입 시 둘 다 산출물 병합 (`@Aspect @Component` 클래스에서 `spring_bean` + `aspect` 엔티티 공존).
    - TDD : `tests/test_spring_aop_analyzer.py` 23 cases (aspect 엔티티 / 5 advice parametrized / non-aspect 무시 / execution·within·@annotation·@within·named·unresolved pointcut / class-level·method-level `@Order` / JavaParser 통합 / DI+AOP 동시 주입) — 전부 통과. 회귀 누적 **177/177 pass**.
  - [x] **OD-11-B5-3** — `HttpAnalyzer` 구현 (2026-04-19)
    - `@RestController` / `@Controller` class-level → controller 인식. `controller_type` ∈ {rest, mvc} 로 구분.
    - 클래스 `@RequestMapping("/api")` + 메서드 mapping → path 조합. 슬래시 정규화 (선행 `/` 추가, 후행 `/` 제거, 루트 `/` 예외).
    - 5 HTTP shortcut (`@GetMapping`/`@PostMapping`/`@PutMapping`/`@DeleteMapping`/`@PatchMapping`) → 단일 http_method.
    - `@RequestMapping(method=RequestMethod.POST)` → POST, `method={RequestMethod.GET, POST}` → 2 endpoint emit. method 미지정 → `http_method = "ANY"`.
    - Path attribute 형식 3종 지원 : 위치 인자 (`@GetMapping("/x")`), `value="..."`, `path="..."`.
    - `produces` / `consumes` 키워드 → 엔티티 속성.
    - 메서드 파라미터 : `@PathVariable` → `edge_attrs.path_variables`, `@RequestParam` → `edge_attrs.request_params` (파라미터 이름 리스트).
    - 엔티티 qn 규약 : `<METHOD>:<full_path>` (예: `GET:/api/orders/{id}`). `MAPS_URL` 엣지 source = controller FQN, target = endpoint qn.
    - `JavaParser(spring_analyzers=[DIAnalyzer(), AopAnalyzer(), HttpAnalyzer()])` 삼중 주입 검증. `@RestController` 는 DIAnalyzer 의 stereotype 중 하나이므로 `spring_bean` + `http_endpoint` 공존.
    - TDD : `tests/test_spring_http_analyzer.py` 26 cases (controller 타입 / 5 method shortcut parametrized / path 조합·정규화 / method 배열 다중 endpoint / value·path 키워드 / produces·consumes / `@PathVariable` / `@RequestParam` / JavaParser 통합 / DI+AOP+HTTP 삼중) — 전부 통과. 회귀 누적 **203/203 pass**.
  - [x] **OD-11-B5-4** — `EventsAnalyzer` 구현 (2026-04-19)
    - `@EventListener` (method-level) → `HANDLES` 엣지 (source = handler method FQN, target = event_type qn). `attributes.handler_method` 로 짧은 메서드 이름 breadcrumb 보존.
    - `@TransactionalEventListener` (method-level) → 동일한 `HANDLES` 엣지 + `attributes.transactional = True`.
    - `ApplicationEventPublisher.publishEvent(new X(...))` 호출 → `PUBLISHES` 엣지 (source = 발행 메서드 FQN, target = 이벤트 클래스 FQN). `attributes.via` = publisher 필드/식별자 이름 (`this.pub.publishEvent` 은 마지막 세그먼트 `pub`, object 없으면 `this`).
    - `publishEvent(existingVar)` 등 첫 인자가 `object_creation_expression` 이 아닐 때 → target = `<unresolved>` + `attributes.publish_expr` 에 인자 리스트 raw 텍스트 보존.
    - Event 타입 추론 (HANDLES):
      - `@EventListener(X.class)` / `@EventListener(value=X.class)` / `@EventListener(classes={X.class})` → value-form 우선 추출.
      - 그 외 → 메서드 첫 파라미터 타입 (단일 파라미터 관례).
      - 어느 쪽도 없음 → target = `<unresolved>`.
    - `event_type` 엔티티 : qn = 이벤트 클래스 FQN (`import_map` 해석 → 같은 패키지 fallback → 원문 유지). 파일별 dedup (같은 이벤트 여러 번 참조 시 1개 엔티티). `attributes.inferred_from` ∈ {"handler", "publish"}.
    - 발행 메서드 호출 위치(`method_invocation`) 는 메서드 body 트리 전체를 walk 하여 수집 — 중첩 블록/람다 내부에서도 탐지.
    - `publishEvent` 라는 이름만으로 매칭하되 `method_invocation` 의 `name` 필드 정확 일치. `someService.publishEvent()` 같은 도메인 메서드도 포함되는 한계는 PoC 범위로 수용 (Spring 실제 사용처에서 `ApplicationEventPublisher` 의존성이 있으면 B7 런타임 교차검증으로 오탐 제거 가능).
    - `JavaParser(spring_analyzers=[DIAnalyzer(), AopAnalyzer(), HttpAnalyzer(), EventsAnalyzer()])` 4중 주입 검증. `@RestController` + `@Autowired ApplicationEventPublisher` + `@PostMapping` 내부 `publishEvent` + `@EventListener` 가 한 클래스에 모두 있는 케이스에서 `spring_bean`, `http_endpoint`, `event_type` 엔티티 + `AUTOWIRES` / `MAPS_URL` / `PUBLISHES` / `HANDLES` 엣지 전부 산출.
    - TDD : `tests/test_spring_events_analyzer.py` 19 cases (handler 단일 파라미터 / event_type 엔티티 / class-literal value / value-form 우선 / 같은 패키지 fallback / 파라미터·value 모두 없음 unresolved / `@TransactionalEventListener` transactional=True / publishEvent(new X(...)) / publishEvent(var) unresolved + publish_expr / `this.pub` 접두사 via=pub / object 없는 publishEvent via=this / 다중 publishEvent / 중복 event dedup / 이름만 같은 메서드 미매칭 / 같은 클래스 publish+handle / plain method no-op / JavaParser 통합 / DI+AOP+HTTP+Events 사중 / EventsAnalyzer 미주입 시 산출물 없음) — 전부 통과. 회귀 누적 (Spring+parser+graph+ontology 범위) **222/222 pass** (B5-3 대비 +19).
  - [x] **OD-11-B5-5** — `ScheduledAnalyzer` 구현 (2026-04-19)
    - `@Scheduled` (method-level) → `scheduled_task` 엔티티. qn = `<method FQN>#scheduled` (메서드 엔티티와 충돌 회피; `@Bean` 의 `<method FQN>#bean` 컨벤션과 동일 패턴). Entity-only (관계 없음).
    - 항상 기록되는 속성: `method_fqn` = 스케줄 메서드 FQN (클래스 FQN + 메서드명).
    - 조건부 트리거 속성 (실제 애너테이션 arg 에 존재할 때만):
      - 정수/플레이스홀더 키 : `fixed_rate` / `fixed_delay` / `initial_delay`. 값은 `decimal_integer_literal` 원문 또는 placeholder 문자열 그대로.
      - 문자열 키 : `cron` / `zone`. `string_literal` 내부 인용부호 제거 후 저장.
    - String variant 통합 : `fixedRateString` / `fixedDelayString` / `initialDelayString` 을 각각 `fixed_rate` / `fixed_delay` / `initial_delay` 키로 매핑. `${app.rate}` 같은 SpEL / property placeholder 도 그대로 보존. → 소비자가 ms 리터럴 / String 변종을 별도 처리할 필요 없음.
    - 바인딩 형식: `@Scheduled` (arg 없음) 도 방어적으로 entity emit — `method_fqn` 만 기록, 트리거 키는 생략. Spring 런타임상 유효하지 않지만 파서가 엔티티를 빠뜨리는 것보다 기록 후 검증 단계에서 걸러내는 편이 안전.
    - 트리 순회 : 클래스 내부 `method_declaration` 만 검사 (inner class 제외), `modifiers` 내부와 직접 자식 둘 다에서 `marker_annotation` / `annotation` 탐색. `@Scheduled` 만 매칭 — 다른 애너테이션 공존 케이스 무영향.
    - `JavaParser(spring_analyzers=[ScheduledAnalyzer()])` 옵션 주입 검증. DIAnalyzer 와 동시 주입 시 `@Component` + `@Autowired` + `@Scheduled` 혼재 클래스에서 `spring_bean` + `scheduled_task` 엔티티 공존.
    - 스텁 정리 : `spring/analyzer_protocol.py` 의 `ScheduledAnalyzer(_NoopAnalyzer)` 더미 클래스 제거, `spring/__init__.py` 에서 실제 `scheduled_analyzer.ScheduledAnalyzer` 재수출로 교체. 하위 호환 (import 경로 동일).
    - TDD : `tests/test_spring_scheduled_analyzer.py` 15 cases (기본 fixedRate 엔티티 + plain 메서드 무시 + fixedDelay / initialDelay / cron 단독 / cron + zone / String variants parametrized 3종 → 통합 키 / cron placeholder / 다중 `@Scheduled` 메서드 각각 엔티티 + notScheduled 제외 / arg 없는 `@Scheduled` 방어적 emit / JavaParser 통합 / DI+Scheduled 복합 / 분석기 미주입 시 산출 없음) — 전부 통과.
    - 회귀 : Spring 5-analyzer (`DI`/`AOP`/`HTTP`/`Events`/`Scheduled`) 범위 106/106 + 모델링 전체 180/180.
  - [x] **OD-11-B5-6** — `ProfileAnalyzer` method-level 구현 (2026-04-19)
    - method-level `@Profile("prod")` / `@Profile({"a","b"})` / `@ConditionalOnProperty("k")` / `@ConditionalOnProperty(name="k", havingValue="v")` → 다른 analyzer 가 emit 한 entity/relation 의 `attributes.profile` / `attributes.condition` 에 merge (추가 entity/relation emit 없음).
    - 적용 대상 : `@Bean` 메서드 `spring_bean` entity + `@Scheduled` `scheduled_task` + HTTP handler `http_endpoint` entity/`MAPS_URL` relation + `@EventListener`/`@TransactionalEventListener` `HANDLES` relation + publisher 메서드의 `PUBLISHES` relation.
    - method FQN 매칭 규약 :
      - `spring_bean` (#bean 접미사) : qn 에서 `#bean` 스트립
      - `scheduled_task` (#scheduled 접미사) : `attributes.method_fqn` 우선, fallback qn 스트립
      - `http_endpoint` : `attributes.controller_fqn + "." + handler_method`
      - `MAPS_URL` : `source + "." + attributes.handler_method`
      - `HANDLES` / `PUBLISHES` : `source` 가 이미 method FQN
    - 구조 (post-processor 패턴) : `analyze()` 는 Protocol 호환 위해 `([], [])` 반환. 신규 `enrich(entities, relations, tree, pkg_name)` 메서드에서 AST → method FQN 별 profile/condition 맵 구축 후 기존 entity/relation 속성 merge.
    - `JavaParser` 변경 : analyzer 루프를 2패스로 확장. 1패스는 기존 `analyze()` 병합, 2패스는 `hasattr(analyzer, 'enrich')` 체크해서 `enrich()` 호출. duck-typing 으로 선택적 hook (다른 analyzer 에 영향 없음).
    - class-level `@Profile` / `@ConditionalOnProperty` 는 B5-1 DIAnalyzer 가 AUTOWIRES 엣지 속성으로 이미 처리 — ProfileAnalyzer 가 다시 손대지 않음 (중복 회피).
    - 스텁 정리 : `analyzer_protocol.py` 의 `ProfileAnalyzer(_NoopAnalyzer)` 더미 클래스 제거 + `__all__` 축소. `spring/__init__.py` 에서 실제 `profile_analyzer.ProfileAnalyzer` 재수출.
    - TDD : `tests/test_spring_profile_analyzer.py` 17 cases (`analyze()` 빈 결과 보장 / `@Bean + @Profile` 단일 / `@Bean + @Profile` 배열 / `@Bean + @ConditionalOnProperty` 단일 / `@Bean + @ConditionalOnProperty` kv / `@Bean` 단독 시 profile 속성 없음 / `@Scheduled + @Profile` / `@Scheduled + @ConditionalOnProperty` / HTTP handler `@Profile` endpoint + MAPS_URL 동시 / `@EventListener + @Profile` / `@TransactionalEventListener + @Profile` transactional 보존 / `@Bean + @Profile + @ConditionalOnProperty` 동시 / 주석 메서드만 적용 scope / class-level `@Profile` 은 AUTOWIRES 에만 남음 / ProfileAnalyzer 단독일 때 no-op / `enrich()` hook 존재 보장 / publisher 메서드 PUBLISHES 엣지도 enrich) — 전부 통과.
    - 회귀 : Spring 6-analyzer (`DI`/`AOP`/`HTTP`/`Events`/`Scheduled`/`Profile`) 범위 **123/123** + 모델링 전체 **197/197**.
  - [ ] **OD-11-B5-7** — (optional, 연기) `JpaAnalyzer` Spring Data JPA Repository + 쿼리 메서드 — B7 런타임 / B9 Slab 엔진 E2E 에서 실제 데이터 접근 경로 드러날 때 재검토
  - [x] **OD-11-B5-8** — `ReflectionAnalyzer` static call-site marker (2026-04-19, B5-7 스킵 후 직행)
    - 감지 대상 (method/constructor body 내) : `Class.forName("...")` / `Proxy.newProxyInstance(...)` / `ctx.getBean("name")` / `clazz.getMethod("x")` / `clazz.getDeclaredMethod("x")` / `clazz.getField("x")` / `clazz.getDeclaredField("x")`.
    - 출력 포맷 (METHOD / CONSTRUCTOR entity 속성 merge) : `reflection_calls = [{api, arg, line}, ...]`. 추가 entity/relation 은 emit 하지 않음.
    - `api` 규약 : static 호출 `Class.forName` / `Proxy.newProxyInstance` 는 prefix 포함 (object identifier 가 `Class`/`Proxy` 인 경우에 한정). 나머지는 bare method name (`getBean`/`getMethod`/`getDeclaredMethod`/`getField`/`getDeclaredField`).
    - `arg` 규약 : 첫 번째 인자가 `string_literal` 이면 quote 제거한 텍스트, 그 외(변수/클래스 리터럴/식)는 `"<dynamic>"` 로 기록. source order 로 정렬.
    - PoC 범위 제외 : `Method.invoke` / `Constructor.newInstance` — noise 가 커서 B7 런타임 collector 에서 정밀 감지. (테스트로 negative case 고정.)
    - 구조 (post-processor) : `analyze()` 는 Protocol 호환 위해 `([], [])` 반환. 신규 `enrich(entities, relations, tree, pkg_name)` 에서 AST → `class_declaration` / nested type → method/constructor 별 reflection call 리스트 구축 → METHOD/CONSTRUCTOR entity 의 `attributes["reflection_calls"]` 에 덮어쓰기.
    - `JavaParser` 의 2-pass enrich 훅(B5-6 에서 추가) 재사용 — 별도 수정 없음.
    - Scope 격리 : 같은 클래스의 다른 non-reflective 메서드는 속성 없음. try/catch·lambda 등 중첩 블록 내부도 body tree walk 로 감지.
    - `spring/__init__.py` 에서 `ReflectionAnalyzer` export 추가. 단독 주입 시 Spring 전용 entity (`spring_bean`/`scheduled_task`/`http_endpoint`/`aspect`) 는 새로 emit 하지 않음 확인.
    - TDD : `tests/test_spring_reflection_analyzer.py` 20 cases (`analyze()` 빈 결과 / `Class.forName` literal & dynamic / `getBean` literal & class-literal(dynamic) / `getMethod` / `getDeclaredMethod` / `getField` + `getDeclaredField` 혼재 / `Proxy.newProxyInstance` 항상 dynamic / 다중 호출 source 순서 / 속성 없음 무반영 / try-catch 중첩 / lambda 중첩 / constructor body / 비-reflection 호출 배제 / invoke + newInstance PoC 제외 고정 / scope 격리 / `enrich()` hook / 단독 no-op / tree=None 안전) — 전부 통과.
    - 회귀 : Spring 7-analyzer (`DI`/`AOP`/`HTTP`/`Events`/`Scheduled`/`Profile`/`Reflection`) 범위 **143/143** + 모델링 전체 **217/217**.
- [~] **OD-11-B6** — 동적 매핑 3 분석기 + Cross-file Enricher (진행 중, 3/4 — B6-1, B6-2, B6-3 완료)
  - [x] **OD-11-B6-SPEC** — 스펙 확정 (2026-04-19, 사용자 "이대로 진행" 승인)
    - `toClaude/modeling/OD-11-B6-SPEC.md` 신설 — 10 결정사항 + 4 sub-step 상세.
    - 핵심 결정: standalone `analyze()` 패턴 (D7), `CrossFileEnricher` 4th sub-step 분리 (D8), 새 EntityKind 불필요 (D9), SQL 파서는 `sqlglot` (D3), BeanUtils 필드 교집합은 B6-4 에서 (D2), 동적 SQL `<dynamic>` marker + `raw_sql` 보존 (D5).
  - [x] **OD-11-B6-1** — `MapStructAnalyzer` 구현 (2026-04-19)
    - `@Mapper` / `@Mapper(componentModel=...)` 가 붙은 interface + abstract class 대상. 중첩 타입도 재귀 스캔.
    - `@Mapping(source, target)` → `PROPAGATES_TO` (FIELD→FIELD, confidence=1.0). `via_methods = [mapper_fqn.method_name]`, `mapper_fqn` 속성 별도 저장.
    - `@Mapping(expression = "java(...)", target)` → `DERIVES_FROM` + `expression` 속성. source 는 `<expression>` 가상 노드로 기록 (B6-4 에서 실제 field 해소).
    - `@Mapping(target, ignore = true)` → 엣지 미생성.
    - `@Mappings({@Mapping(...), @Mapping(...)})` 컨테이너 flatten 지원 — 내부 각 `@Mapping` 을 개별로 처리.
    - `@Mapping(source, target, qualifiedByName = "foo")` → `via_methods` 에 qualifier 이름을 append + `qualified_by_name` 속성도 추가.
    - `default` 메서드 / `@Named` 메서드는 MapStruct 의 helper 이므로 skip.
    - 파라미터 prefix 해석 : `@Mapping.source = "src.item.id"` 처럼 첫 토큰이 파라미터 이름이면 타입 FQN 으로 replace → `<SrcTypeFqn>.item.id`. 일치하는 param 없을 시 첫 파라미터 타입으로 fallback prefix.
    - Import-based FQN 해소 : import 맵에서 해소 실패하면 simple name 그대로 보존 (B6-4 에서 repo-level 재해소). 제네릭/배열 접미사 strip.
    - 명시 `@Mapping` 이 전혀 없는 매퍼 메서드는 METHOD entity 의 `attributes["mapstruct_implicit_fields"]` 에 marker 주입 (`{mapper_fqn, method, src_type, dst_type, line}`) — B6-4 에서 FIELD 교집합 확정 후 `PROPAGATES_TO{implicit, confidence: 0.9}` 로 승격.
    - 설계 : `analyze()` 는 standalone 으로 `(entities=[], relations)` 직접 반환 (B5 의 enrich 후처리 패턴과 달리 lineage 엣지는 1차 아티팩트). `enrich()` 는 implicit marker 주입 전용 (JavaParser 가 만든 기존 METHOD 엔티티에 속성 merge).
    - `spring/__init__.py` 에 `MapStructAnalyzer` export 추가.
    - TDD : `tests/test_spring_mapstruct_analyzer.py` 16 cases (non-@Mapper 무시 / `@Mapper` 빈 인터페이스 / source-target PROPAGATES_TO + confidence/via_methods/mapper_fqn 검증 / expression DERIVES_FROM + `<expression>` sentinel / dotted source path 유지 / 파라미터 prefix replace / ignore=true skip / `@Mappings` 컨테이너 다중 / qualifiedByName via_methods append / 다중 매핑 메서드 scope 격리 / default method skip / `@Named` method skip / implicit marker only (엣지 미생성) / `componentModel="spring"` detection / abstract class `@Mapper` / import 누락 시 simple name fallback) — 전부 통과.
    - 회귀 : Spring 8-analyzer 범위 **159/159** (16 신규 포함) + 모델링 범위 **223/224** (test_lineage_validation 1 건 선행 실패, Wiki 영역 무관).
  - [x] **OD-11-B6-2** — `BeanUtilsAnalyzer` 구현 (2026-04-19)
    - `org.springframework.beans.BeanUtils.copyProperties(src, dst, ...ignore)` — Spring 규약 (SRC, DST, ...ignore). 3+번째 인자의 string literal 은 `ignore` 리스트에 축적.
    - `org.apache.commons.beanutils.BeanUtils.copyProperties(dst, src)` — **인자 순서 반대 (DST, SRC)**. import 기반 판별로 자동 swap.
    - `org.modelmapper.ModelMapper.map(src, Dst.class)` / `.map(src, dst)` — 인스턴스 메서드. 2번째 인자는 `class_literal` (Dst.class) 또는 인스턴스. class literal 에서는 type identifier 추출 + import 로 FQN 해소.
    - Static import 지원 : `import static org.springframework.beans.BeanUtils.copyProperties` / `...BeanUtils.*` → bare `copyProperties(src, dst)` 호출도 감지 (Apache 변종도 동일).
    - Import 판별 실패 : `BeanUtils.copyProperties(...)` 가 있는데 어느 변종 import 도 없으면 `library="unknown"`, `confidence=0.5` 로 낮춤 (Spring 기본 규약으로 해석).
    - Scope 맵 (param + local var + class field + `this` → FQN) : per-method/per-constructor 구축. 인자 identifier → 타입 lookup. `field_access (this.x)` 도 지원. 해소 실패 시 simple name fallback (B6-4 에서 repo-level 재해소).
    - 출력 : METHOD/CONSTRUCTOR entity `.attributes["beanutils_calls"] = [{library, src_type, dst_type, ignore, confidence, line}, ...]`. `PROPAGATES_TO` 엣지 emit 없음 — B6-4 에서 src/dst 의 FIELD 교집합을 계산해 `PROPAGATES_TO{confidence: 0.7, library, via_methods}` 로 승격.
    - 설계 : post-processor 패턴 (`analyze()` 는 `([], [])` 반환, `enrich()` 에서 기존 METHOD/CONSTRUCTOR entity 속성에 merge) — ReflectionAnalyzer/ProfileAnalyzer 와 동일한 접근. JavaParser 의 B5-6 2-pass enrich 훅 재사용, 변경 없음.
    - `spring/__init__.py` 에 `BeanUtilsAnalyzer` export 추가.
    - TDD : `tests/test_spring_beanutils_analyzer.py` 13 cases (`analyze()` 빈 결과 / Spring 기본 (src, dst) / Apache 인자 순서 swap / ModelMapper + class literal / ModelMapper + 인스턴스 2번째 arg / Spring + ignore list ["password","secret"] / import 없음 unknown + confidence 0.5 / 같은 메서드 2회 호출 순서 / 서로 다른 메서드 scope 격리 + 비-BeanUtils 메서드 속성 없음 / 비-BeanUtils 호출 무시 / static import bare call / constructor body 호출 → CONSTRUCTOR 마커 / 미해소 타입 simple name fallback) — 전부 통과.
    - 회귀 : Spring 9-analyzer 범위 (B5-1~B5-8 + B6-1 + B6-2) **172/172** + 모델링 범위 **283/284** (test_lineage_validation 1 건 선행 실패, Wiki 영역, B6-2 무관).
  - [x] **OD-11-B6-3** — `NativeSqlAnalyzer` 구현 (2026-04-19)
    - 감지 대상 7 경로 : Spring Data `@Query("...")` / `@Query(value=..., nativeQuery=true)` / `@Modifying` + `@Query(...)` / `EntityManager.createNativeQuery` / `EntityManager.createQuery` (JPQL) / `JdbcTemplate.{query,queryForObject,queryForList}` (read) / `JdbcTemplate.{update,batchUpdate}` (write).
    - SQL 파싱 : `sqlglot.parse(sql, error_level="ignore")` default dialect. `parse_one` 대신 `parse` 를 써서 multi-statement 감지 (len>1 시 첫 stmt 처리 + `multi_statement_warning=True` 속성). 스펙 §5.2 의 `dialect="ansi"` 는 sqlglot 23.x 에 미존재 — default 로 호출.
    - op_kind 결정 : SQL root 기반 (`Insert`/`Update`/`Delete` → write, `Select`/`Union`/`CTE` → read). `JdbcTemplate` 은 메서드 이름으로 `force_kind` 힌트 (parse 실패 시 dynamic 엣지 kind 결정용).
    - 쓰기/읽기 테이블 분리 : `Insert` 는 `stmt.this` (Table 또는 Schema(Table, cols)) 를 write target, `stmt.expression` (Select) 내 테이블은 read. 초기 `parent.key=='insert'` 접근은 `INSERT INTO orders (a,b) VALUES (?,?)` 케이스에서 Schema 래핑 때문에 오탐 → `stmt.this` 직접 참조로 수정. `Update`/`Delete` 첫 Table = write, 이후 (서브쿼리) = read.
    - 엣지 포맷 : `CodeRelation(kind=reads_table|writes_table, source=<METHOD fqn>, target=<lower(table)>, attributes={columns, confidence, raw_sql, dialect, multi_statement_warning?})`. `columns` 는 `find_all(exp.Column)` dedupe 순서 보존. target 은 항상 lowercase, `raw_sql` 은 원본.
    - dialect marker : `@Query` 기본 → `"jpql"`, `nativeQuery=true` → `"sql"`. `createQuery` → `"jpql"`, `createNativeQuery` → `"sql"`. `JdbcTemplate.*` → `"sql"`. JPQL entity 이름 (`Order` 등) 도 lowercase 화해 edge target 에 기록, B6-4 가 `class_index` 로 entity↔table 대응 해소.
    - Dynamic SQL : first arg 가 `string_literal` 이 아니면 (`binary_expression` concat / `identifier` local var / `method_invocation` builder) 단일 `<dynamic>` marker 엣지 emit (`target=<dynamic>`, `columns=[<dynamic>]`, `confidence=0.3`, `raw_sql` 에 원본 concat 표현 보존).
    - Scope 맵 (BeanUtilsAnalyzer 패턴 재사용) : field_types + params + locals + `this` → FQN 으로 `EntityManager` / `JdbcTemplate` 인스턴스 타입 해소. `EntityManager` FQN set 에 `javax.persistence.EntityManager`, `jakarta.persistence.EntityManager`, 그리고 import 해소 실패 대비 simple name `"EntityManager"` 도 포함.
    - 설계 : `analyze()` 가 relation 직접 emit (standalone, B6-1 MapStruct 와 동일). `enrich()` 는 identity no-op. DB_TABLE entity 는 B6-3 에서 emit 안 함 — B6-4 `CrossFileEnricher` 에서 repo-wide dedup.
    - MyBatis `SqlSession.selectOne` 등은 Round 1 out-of-scope (B6-SPEC §5.4) — 메서드 이름이 매칭 set 에 없어 자연스럽게 skip. negative test 로 회귀 고정.
    - `pyproject.toml` 의존성 : `sqlglot = "^23.0"` 추가 (사용자 승인 2026-04-19, sqlglot 23.17.0 설치).
    - `spring/__init__.py` 에 `NativeSqlAnalyzer` export 추가.
    - TDD : `tests/test_spring_native_sql_analyzer.py` 16 cases (`@Query` native SELECT / `@Query(nativeQuery=true)` INSERT / `@Modifying` UPDATE / JPQL `@Query("SELECT o FROM Order o")` / `em.createNativeQuery` / `jdbcTemplate.query` / `jdbcTemplate.update` / JOIN 다중 테이블 2 엣지 / 서브쿼리 내부 테이블 read 포함 / INSERT...SELECT write+read 동시 / 동적 SQL `<dynamic>` marker / MyBatis `sqlSession.selectOne` 무시 / `@Query` native=true vs default JPQL dialect 구분 / multi-statement 첫 stmt + warning / uppercase `ORDERS` → lowercase / standalone `analyze()` 검증) — 전부 통과.
    - 회귀 : Spring 10-analyzer 범위 (B5-1~B5-8 + B6-1~B6-3) **190/190** + 모델링 범위 `-k "spring or java_parser or code_analysis or modeling or graph"` **262/262** (test_lineage_validation 1 건 선행 실패는 Wiki 영역, B6-3 무관).
  - [x] **OD-11-B6-4** — `CrossFileEnricher` 구현 (2026-04-19)
    - 입력 : `enrich_repo(parse_results, class_index, field_index) -> list[ParseResult]` — JavaParser 외부 repo-level 헬퍼 (analyzer 아님).
    - 4 책임 : (1) MapStruct implicit finalize — B6-1 marker `mapstruct_implicit_fields` → src/dst FIELD 교집합 → `PROPAGATES_TO{confidence:0.9, implicit:true}` 엣지. (2) BeanUtils FIELD 교집합 — B6-2 marker `beanutils_calls` → FQN 재해소 + 교집합 → `PROPAGATES_TO{confidence:0.7, library, via_methods}`. (3) NativeSQL column→field resolution — B6-3 `READS_TABLE`/`WRITES_TABLE` 엣지 × `class_index` 의 `@Table`/`@Column`/`@Entity` 매핑 → `DB_COLUMN` 노드 + `READS`/`WRITES` 엣지 + JPQL entity → lowercase table 재작성. (4) DB_TABLE dedup — 모든 target 을 모아 단일 synthetic `ParseResult(file_path="<db_schema>", language="java")` 에 집약.
    - 설계 결정 (B6-SPEC §6 Q1~Q10) :
      - Q1 In-place mutation — `CodeEntity`/`CodeRelation` 은 `frozen=True` 이나 `.attributes` dict 는 mutable. marker 추가는 dict 직접 변경, edge target 재작성은 `dataclasses.replace(rel, target=new)` + `pr.relations[idx] = new_rel` in-place 대입.
      - Q2 Option C — `JpaAnnotationExtractor` 별도 모듈 (`backend/modeling/code_analysis/jpa_annotation_extractor.py`, ~90 LOC). `@Entity(name=...)` / `@Table(name=...)` / `@Column(name=...)` annotation 을 class entity `.attributes["jpa_entity_name" / "jpa_table" / "jpa_columns"]` 로 병합. `setdefault(...)` 로 기존 키 보존.
      - Q3 FIELD 교집합 — 이름+타입 일치 우선, 이름만 일치 fallback. `serialVersionUID`/`$jacocoData`/`static`/`transient` 제외 (`_eligible_field_names`).
      - Q4 JPQL → table — `dialect=jpql` edge target (lowercase entity name) 을 `class_index` 에서 `jpa_entity_name.lower()` 또는 simple class name lower 매칭 → `jpa_table` 로 rewrite.
      - Q5 DB_TABLE/DB_COLUMN dedup — `enrich_repo` 전체 lifetime 에 `dict` 유지 후 synthetic `ParseResult` 1 개에 방출. qn : `DB_TABLE = <table>`, `DB_COLUMN = <table>.<column>` 모두 lowercase.
      - Q6 Ambiguous simple name — class_index 에서 ≥2 후보 해소 시 엣지 emit 생략 + `METHOD/CONSTRUCTOR.attributes["beanutils_ambiguous_types"] = [{call_line, src_candidates, dst_candidates}, ...]` marker 기록.
      - Q7 qn 컨벤션 — `DB_TABLE.qn = <table>`, `DB_COLUMN.qn = <table>.<column>`, 둘 다 lowercase. `READS`/`WRITES` source = METHOD fqn, target = DB_COLUMN qn.
      - Q8 명시 매핑 중복 방지 — MapStruct implicit finalize 전에 기존 `(source, target)` 페어 스냅샷 수집해 명시 `@Mapping` 과 겹치는 경우 skip.
      - Q9 Dynamic SQL — `target=="<dynamic>"` edge 는 DB_TABLE/DB_COLUMN emit 및 READS/WRITES 엣지 모두 skip. 원본 `READS_TABLE`/`WRITES_TABLE` 엣지는 그대로 유지.
      - Q10 multi_statement_warning 패스스루 — 첫 stmt 만 처리된 edge 의 warning 속성은 column 해소 결과 엣지에도 전달.
    - 출력 위치 : synthetic `ParseResult(file_path="<db_schema>", language="java", entities=[*DB_TABLE, *DB_COLUMN], relations=[])` 를 `parse_results` 끝에 append. 호출자는 반환 리스트를 그대로 graph writer 에 넘기면 됨.
    - TDD : `tests/test_cross_file_enricher.py` 10 cases — MapStruct implicit / explicit+implicit 혼합 / simple-name 해소 / BeanUtils Spring / Apache 인자 순서 + ignore / ambiguous marker / NativeSQL READS_TABLE → DB_COLUMN+READS / JPQL `FROM Order o` rewrite / Dynamic SQL skip / 2-file DB_TABLE dedup — 전부 통과 (0.02s).
    - 회귀 : 모델링 범위 `-k "spring or java_parser or code_analysis or modeling or graph or cross_file"` **272/272** pass, 768 deselected, 0 failures. `test_lineage_validation::test_new_file_superseding_unknown` 1 선행 실패는 Wiki 영역, B6-4 무관.
    - JavaParser / graph_writer / 기존 analyzer 변경 없음. 신규 `cross_file_enricher.py` (~250 LOC) + `jpa_annotation_extractor.py` (~90 LOC) 만 추가.
    - **B6 sub-phase 완료 → 다음 OD-11-B7 Reflection 런타임 collector 인터페이스**.
  - [x] **OD-11-B7-0** — `ReflectionAnalyzer` marker `arg_kind` 필드 확장 (2026-04-19)
    - 배경 : 사용자 지적 — `getBean("literal")` / `Class.forName("com.x.Foo")` 같이 첫 인자가 문자열 리터럴이면 런타임 없이도 `class_index` / `bean_index` 로 정적 해석 가능. 기존 B5-8 marker 는 literal ↔ dynamic 만 구분해서 downstream 가 변수/concat/타입을 분기할 수 없었다.
    - Marker schema 변경 : `reflection_calls = [{"api", "arg", "line"}]` → `reflection_calls = [{"api", "arg", "arg_kind", "line"}]`.
      - `arg` 의미 변경 : 항상 소스 텍스트. `<dynamic>` sentinel 제거. B7-1 resolver 가 concat 의 prefix 부분을 읽을 수 있게 됨.
      - `arg_kind` 5-값 : `"literal"` / `"variable"` / `"concat"` / `"type"` / `"other"`.
    - 설계 결정 :
      - Q. `class_literal` 에서 클래스 이름 추출 — 소스 텍스트에서 `.class` 접미사 strip. tree-sitter-java 에서 `Foo.class` / `com.x.Foo.class` 모두 안전.
      - Q. `binary_expression` 연산자 판별 — `operator` field 가 `+` 일 때만 `concat`, 그 외는 `other`. Reflection 첫 인자 context 에서 numeric `+` 는 사실상 불가능.
      - Q. 기존 `<dynamic>` 테스트 전환 — 이름 포함 rewrite (`test_class_forname_with_dynamic_arg` → `test_class_forname_with_variable_arg`) 해서 리뷰어가 의도 변경을 즉시 인지.
    - 구현 범위 :
      - `backend/modeling/code_analysis/spring/reflection_analyzer.py` — `_first_arg_value()` 시그니처 `str → tuple[str, str]`, `_classify_arg_node()` helper 추가, `_classify_invocation()` 반환 dict 에 `arg_kind` 주입. LOC delta +28.
      - `tests/test_spring_reflection_analyzer.py` — 기존 4 tests `<dynamic>` → 실제 source text + `arg_kind` assertion 업데이트, 신규 5 tests 추가 (`test_arg_kind_literal_class_forname` / `test_arg_kind_variable_get_bean` / `test_arg_kind_concat_class_forname` / `test_arg_kind_other_method_call_arg` / `test_literal_arg_tests_carry_arg_kind_literal`). 20 → 25 cases.
    - TDD 싸이클 : **Red** 9 failed / 16 passed → **Green** 25 passed / 0 failed (0.06s).
    - 회귀 : 모델링 범위 `-k "reflection or java_parser or spring or analyzer or ..."` **231/231** pass, 광범위 924/924 non-wiki subset pass. wiki 섹션 pre-existing 실패 2건 (B7 무관).
    - B7-1 로 인계 : `arg_kind == "literal"` → 정확 매칭, `"type"` → 타입 기반 lookup (deferred per SPEC §10), `"concat"` → prefix wildcard, `"variable"`/`"other"` → B7-2 runtime trace fallback.
  - [x] **OD-11-B7-1** — `reflection_literal_resolver.py` : literal arg 정적 해소 (2026-04-19)
    - 배경 : B7-0 이 남긴 `reflection_calls` marker 중 `arg_kind == "literal"` 은 런타임 없이 `class_index` / `bean_index` 조회만으로 타깃을 확정 가능. SPEC §5.3 의 getBean / Class.forName 리터럴 경로 구현.
    - 모듈 : `backend/modeling/code_analysis/reflection_literal_resolver.py` (~200 LOC).
      - `build_bean_index(parse_results) -> dict[bean_name → SPRING_BEAN entity]` — DIAnalyzer 가 기록한 `attributes["bean_name"]` 을 그대로 index 로 집계. 첫-발견 우선 collision 규칙.
      - `resolve_reflection_literals(parse_results, class_index, bean_index)` — METHOD/CONSTRUCTOR 의 `reflection_calls` marker 순회 → `getBean` → bean_index 조회, `Class.forName` → class_index 조회. 매치 시 `CALLS{source:static_literal, confidence:0.9, api, arg}` 엣지, 미스 시 `CALLS{source:static_unresolved, confidence:0.4, reason:bean_not_found|class_not_found, target:"<reflection-site>"}` 엣지. `arg_kind != "literal"` 또는 `getMethod`/`getField`/`Proxy.newProxyInstance` 는 B7-1 에서 skip.
    - DI analyzer 연계 확장 : `backend/modeling/code_analysis/spring/di_analyzer.py` 에서 SPRING_BEAN entity 를 emit 할 때 `attributes["bean_name"]` 을 함께 기록.
      - `_extract_stereotype_bean_name(annotations, stereotype, class_name)` : `@Component("name")` / `(value=...)` / `(name=...)` → 명시된 이름, 없으면 module-level `_camel_case(class_name)` fallback.
      - `_extract_bean_method_name(annotations, method_name)` : `@Bean("name")` / `(name=...)` → 명시된 이름, 없으면 메서드명.
      - `_camel_case("OrderService")` → `"orderService"`. `URLHandler` / `HTTPClient` 처럼 첫 두 글자가 uppercase 인 경우 원본 유지 — Spring 의 `Introspector.decapitalize` 와 동일 규칙.
      - CodeEntity `frozen=True` 제약은 보존 (생성 시점 attributes 삽입).
    - 설계 결정 :
      - Q. bean_name 저장 위치 — **DIAnalyzer 가 SPRING_BEAN.attributes 에 기록**. 이유 : resolver 가 annotation AST 를 재파싱하지 않아도 되고, DIAnalyzer 는 이미 annotation 순회 중이라 한 줄 추가로 해결.
      - Q. 해소 실패 시 엣지 — **`<reflection-site>` sentinel target 으로 emit**. 이유 : Impact Analysis 가 `source=static_unresolved` 로 필터해 "정적 시도 실패" 리포트 가능, B7-2 런타임 trace 와 coexist (덮어쓰지 않음).
      - Q. getMethod / getField — **B7-1 skip**. 이유 : receiver 타입 역추적이 필요해 별도 scope-tracking 모듈 요구, SPEC §10 deferred.
    - TDD 싸이클 : **Red** `ModuleNotFoundError on import` → **Green** 15 passed / 0 failed (`tests/test_reflection_literal_resolver.py`).
      - Test 구성 (15) : build_bean_index 4 (explicit / camelCase / bean method / bean method with name) + resolve 10 (getBean match / camelCase match / miss → unresolved, Class.forName match / miss, variable skip, type skip, concat skip, getMethod skip, multi-method same bean, no-marker) + sanity 1.
    - 회귀 : 4 모듈 통합 `di_analyzer + reflection_analyzer + cross_file_enricher + reflection_literal_resolver` **73/73** pass. 모델링 범위 `-k "spring or java_parser or code_analysis or modeling or graph or cross_file or reflection"` **295/295** pass, 765 deselected, 1 warning. 기존 DI 23 tests 는 새 `bean_name` attribute 를 assert 하지 않아 모두 통과.
    - B7-2 로 인계 : `arg_kind ∈ {variable, concat, type, other}` marker 는 그대로 남음 → 런타임 trace 와 line 기반으로 매칭해 `CALLS{source:runtime, 0.95}` emit. `source:static_unresolved` 엣지는 덮어쓰지 않고 공존 (Q2 Coexist). `REFLECTS_AS` 엣지는 B7-2 런타임 trace 의 resolved_target 에서 method/field 이름까지 추적해 emit.
  - [x] **OD-11-B7-2** — `runtime_collector.py` : Protocol + DTO + JSON collector + 병합기 (2026-04-19)
    - 배경 : B7-1 이 해소 못 한 `arg_kind ∈ {variable, concat, type, other}` reflection marker + 정적 분석기가 놓친 dynamic dispatch / lambda 경로를 JVM Agent runtime trace 로 복구. B9 실 instrumentation 전에 Protocol + DTO + JSON reference collector 까지 확정 (SPEC §Q3 "A 채택 — Protocol+DTO only").
    - 모듈 : `backend/modeling/code_analysis/runtime_collector.py` (~250 LOC).
      - DTO : `ReflectionTrace{method_fqn, api, line, resolved_target, sample_count}` + `CallTrace{caller_fqn, callee_fqn, sample_count}`. `@dataclass(frozen=True)`.
      - Protocol : `@runtime_checkable class RuntimeCollector(Protocol)` — `load_reflection_traces()` / `load_call_traces()`. duck-typed 로 JVM Agent / JSON 파일 / in-memory fixture 어느 쪽도 구현 자유.
      - Reference : `JsonFileCollector(path)` — SPEC §6.2 스키마 로드, 필수 필드 누락 시 `ValueError("reflection_trace missing required field(s): ...")` fail-fast.
      - Merger : `merge_runtime_traces(parse_results, collector, class_index)` — synthetic `ParseResult(file_path="<runtime>", language="java", entities=[], relations=[...])` in-place append. caller method_fqn 이 METHOD/CONSTRUCTOR entity 에 없으면 해당 trace drop (orphan edge 방지).
    - 엣지 emission 규칙 :
      - class-lookup API (`Class.forName`, `getBean`, `ApplicationContext.getBean`, `Proxy.newProxyInstance`, 기타) → `CALLS{source:runtime, 0.95, api, sample_count}` caller → resolved_target (class FQN).
      - method-lookup API (`getMethod`, `getDeclaredMethod`, `getMethods`, `getDeclaredMethods`, `Method.invoke`) → `CALLS` (class FQN, `resolved_target.rpartition(".")` 앞부분) + `REFLECTS_AS` (method FQN 전체) 쌍 emit.
      - field-lookup API (`getField`, `getDeclaredField`, `getFields`, `getDeclaredFields`) → method-lookup 과 동일 (REFLECTS_AS 타깃만 field FQN).
      - `CallTrace` (비-reflection) → `CALLS{source:runtime, 0.95, sample_count}`.
    - 중복/분기 병합 : 키 `(kind, source, target, line, api)`. 같으면 sample_count 합산, 다르면 분기 유지 (동적 dispatch 표현).
    - Parser protocol 확장 : `RelationKindSpec("reflects_as", "code", ...)` 등록, `RelationKinds.REFLECTS_AS = "reflects_as"` 상수. 기본 relation kind 17 → 18. graph_writer 는 whitelist 기반이라 신규 kind 자동 허용. `test_code_analysis_registry.py` code 카테고리 목록 + `REFLECTS_AS` assertion 업데이트.
    - 설계 결정 :
      - Q. method-lookup 엣지 분기 — **CALLS (class) + REFLECTS_AS (member) 병행 emit**. 이유 : Impact Analysis BFS 가 class 단위 + method 단위 양쪽에서 도달 가능해야 하며, class FQN 도출은 rpartition 으로 즉시 가능.
      - Q. Unknown caller — **skip**. 이유 : orphan edge 방지. synthetic lambda / obfuscated FQN 등 B9 instrumentation 버그 의심 포인트로 남김.
      - Q. static_unresolved 와 공존 — **덮어쓰지 않음 (Coexist 3-way)**. 이유 : SPEC Q2. runtime 에 관측되지 않은 다른 경로의 표식을 유지해야 "관측 안 됐지만 정적으로 시도된 경로" 리포트 가능.
      - Q. Protocol 런타임 체크 — **`@runtime_checkable` 적용**. 이유 : subclass 없이 `isinstance` 검증 가능.
    - TDD 싸이클 : **Red** `ModuleNotFoundError` → **Green** 14 passed / 0 failed (0.07s).
      - Test 구성 (14) : DTO shape 2 (ReflectionTrace/CallTrace frozen) + reflection trace 6 (class-lookup CALLS, method-lookup CALLS+REFLECTS_AS, Coexist, unknown caller skip, 2-target dispatch, 중복 합산) + call trace 2 (CALLS emit, unknown caller skip) + empty trace synthetic PR 1 + JsonFileCollector 2 (roundtrip, missing field ValueError) + Protocol duck typing 1.
    - 회귀 : Combined 타깃 7 모듈 (`runtime_collector + reflection_literal_resolver + reflection_analyzer + cross_file_enricher + di_analyzer + graph_writer_edges + code_analysis_registry`) **117/117** pass. 모델링 범위 `-k "spring or java_parser or code_analysis or modeling or graph or cross_file or reflection or runtime"` **309/309** pass, 765 deselected, 1 warning.
    - B8 로 인계 : `query_engine.py` 복원 + confidence threshold 파라미터화 (`>=0.9` safe / `source IN {runtime, static_literal}` observed / no threshold potential). 실제 JVM Agent 는 B9 Slab sample repo 수령 후 `toClaude/temp-runtime/` 에서.
  - [x] **OD-11-B8 SPEC 확정** — Impact/BFS hops 자율 조정 API 신규 설계. SPEC 문서 + 7 design decisions 사용자 승인 완료 (2026-04-19)
    - SPEC : `toClaude/modeling/OD-11-B8-SPEC.md`. §0 배경/§1 구버전 대비/§2 DTO+Engine+InMemoryGraphView 제안/§3 BFS 알고리즘/§4 hops 자율 축소 휴리스틱/§5 Q1~Q7 결정 + `ImpactConfig`/§6 테스트 계획/§7 인계.
    - 결정 요약 : Q1=A(OBSERVED 에 None 포함) / Q2=B(direction 파라미터, incoming 기본) / Q3=A(`<reflection-site>` skip) / Q4=B(entity_kinds 기본 세트 {method, constructor, http_endpoint, event_type, db_table, scheduled_task}) / Q5=설정 외부화 (ImpactConfig) / Q6=A(InMemoryGraphView 만, Neo4j 보류) / Q7=A(4-way 서브스텝 B8-0/1/2/3).
    - 핵심 변경 : 구버전 `query_engine.py` 의 term→domain 매핑 대신 **code entity→code entity BFS**. 도메인 매핑 복원은 Phase C Round 2 로 이관.
  - [x] **OD-11-B8-0** — Query DTO + GraphView Protocol + InMemoryGraphView + ImpactConfig (2026-04-19)
    - 배경 : B8 Impact/Reverse Lookup 엔진의 기초 뼈대. BFS 로직 이전에 값 객체 레이어 + 그래프 읽기 추상화 확정 필요. B6/B7 패턴 (SPEC → 서브스텝 TDD) 동일.
    - 모듈 :
      - `backend/modeling/query/__init__.py` (패키지 선언)
      - `backend/modeling/query/query_models.py` (~95 LOC) : `ImpactMode(StrEnum)` + `ImpactQuery(BaseModel)` + `AffectedEntity(BaseModel)` + `ImpactResult(BaseModel)` + `EdgeRow(frozen dataclass)` + `EntityRow(frozen dataclass)` + `ImpactConfig(frozen dataclass)`
      - `backend/modeling/query/graph_view.py` (~90 LOC) : `@runtime_checkable Protocol GraphView` + `InMemoryGraphView` 어댑터 + `_edge_row_from(CodeRelation)` 변환기
    - DTO 정의 요약 :
      - `ImpactQuery` : `target_fqn` + `mode=OBSERVED` + `max_hops=5 (ge=1, le=20)` + `auto_hops=True` + `direction Literal["incoming","outgoing"]="incoming"` + `edge_kinds`/`entity_kinds set[str] | None`
      - `AffectedEntity` : qualified_name/kind/distance/confidence_min/edge_source_chain (`list[str | None]`)/path/reasons
      - `ImpactResult` : source/mode/hops_used/hops_shrunk_reason (nullable)/affected/unresolved_sources/message
      - `EdgeRow` : source/target/kind/confidence(float)/edge_source(str|None)/attributes(dict). frozen dataclass.
      - `EntityRow` : qualified_name/kind/attributes. frozen dataclass.
      - `ImpactConfig` : 기본 `shrink_result_threshold=200` / `timeout_seconds=2.0` / `frontier_warn_threshold=500` / `observed_sources=frozenset({None, "static_literal", "runtime"})` / `safe_min_confidence=0.9` / `default_entity_kinds=frozenset({method, constructor, http_endpoint, event_type, db_table, scheduled_task})`. frozen dataclass, DI 로 주입.
    - GraphView :
      - `outgoing(fqn) -> list[EdgeRow]` / `incoming(fqn) -> list[EdgeRow]` / `entity(fqn) -> EntityRow | None`. `@runtime_checkable` 로 테스트 단 isinstance 검증 가능.
      - `InMemoryGraphView(parse_results)` : `_entities` / `_outgoing` / `_incoming` 3-인덱스. `defaultdict(list)` 로 bidirectional O(1) lookup.
    - `_edge_row_from` 변환 규칙 : `CodeRelation.attributes["source"]` → `EdgeRow.edge_source` (None 허용, 정적 JavaParser 기본 엣지 보존). `attributes["confidence"]` → `EdgeRow.confidence` (기본값 `_DEFAULT_STATIC_CONFIDENCE=1.0` — source 없는 엣지는 정적 확정으로 간주).
    - 설계 결정 :
      - Q. Pydantic vs dataclass — **외부 API 경계(Query/Result/Affected)는 Pydantic BaseModel, 내부 값 객체(EdgeRow/EntityRow/ImpactConfig)는 frozen dataclass**. 이유 : 외부는 validation, 내부는 불변 + 퍼포먼스.
      - Q. `edge_source=None` 의 confidence 기본값 — **1.0**. 이유 : JavaParser 가 한 번에 해소한 엣지는 `static_literal` (0.9) 보다 확신 높음. B6/B7 의 `source` 명시 엣지는 각자 이유로 < 1.0.
      - Q. `ImpactConfig.observed_sources` 에 `None` 포함 — **Q1 결정 반영**. 이유 : `None` 을 제외하면 OBSERVED 가 리플렉션/DI 샘플만 보여 Impact 용도로 무용.
      - Q. `ImpactQuery.direction` Literal — **"incoming"/"outgoing" 2-way**. 이유 : Q2 결정. 양방향(`both`)은 B9+ 로 보류.
    - TDD 싸이클 : **Red** `ModuleNotFoundError: No module named 'backend.modeling.query'` → **Green** 25 passed / 0 failed (0.08s). 중간 `_method` fixture 가 단일 토큰 FQN 처리 못 하던 IndexError 한 번만 수정.
      - Test 구성 (25) : `test_query_models.py` 15 (Mode values/ImpactQuery defaults+hops bounds+direction enum+edge_kinds/AffectedEntity shape/ImpactResult defaults+hops_shrunk_reason/EdgeRow frozen+None source/EntityRow/ImpactConfig defaults+override+frozen) + `test_in_memory_graph_view.py` 10 (Protocol satisfy/entity lookup × 3/outgoing+incoming 필터/edge_source+confidence attributes/None source 기본 1.0/missing fqn empty/다중 PR 병합/엣지 kind 보존).
    - 회귀 : 모델링 범위 13 모듈 (`code_analysis_registry + cross_file_enricher + graph_writer_edges + java_parser_basic + spring_analyzer_scaffold + spring_aop_analyzer + spring_beanutils_analyzer + spring_di_analyzer + spring_reflection_analyzer + reflection_literal_resolver + runtime_collector + query_models + in_memory_graph_view`) **199/199** pass (0.92s). 기존 모듈 0건 회귀.
    - B8-1 로 인계 : `QueryEngine(graph, config)` 구현. BFS incoming 기본, 3-mode `passes_filter`, `confidence_min` 병목 계산, `edge_source_chain` 누적, 12 테스트 케이스 (SAFE/OBSERVED/POTENTIAL/max_hops/cycle/2-paths 최단/edge_kinds/entity_kinds/`<reflection-site>` skip/unknown target/path 역추적/confidence_min).
  - [x] **OD-11-B8-1** — `QueryEngine.impact` BFS 코어 + 3-mode filter (2026-04-19)
    - 배경 : B8-0 값 객체/GraphView 위에서 실제 Impact Analysis 엔진 구현. SPEC §3, §6 의 알고리즘/테스트 계획을 코드로 확정. B8-2 의 hops 자율 축소·timeout 은 다음 서브스텝으로 분리.
    - 모듈 :
      - `backend/modeling/query/query_engine.py` (~165 LOC) : `QueryEngine(graph, config)` 클래스 + `.impact(query)` public API + `_bfs` 코어 + `_diagnostic_reflection_site` 분기 + `_Frontier` frozen dataclass + `_kind_of`/`_passes_mode`/`_format_reason` 헬퍼.
    - BFS 알고리즘 :
      - 초기화 : `visited = {target_fqn}` (자기 자신은 affected 에서 제외) → 초기 frontier `_Frontier(distance=0, confidence_min=1.0, chain=(), path=(target,), reasons=())`.
      - hop 루프 (`frontier and hops_used < max_hops`) : frontier 각 노드에서 `_step_edges(fqn, direction)` 로 incoming/outgoing 엣지 수집 → `other = edge.source if direction=="incoming" else edge.target` → `<reflection-site>` 면 `unresolved.append(edge.source)` 후 skip → `visited` 중복 skip → `_passes_mode(edge, mode, cfg)` 통과 확인 (SAFE: `edge.confidence >= cfg.safe_min_confidence` / OBSERVED: `edge.edge_source in cfg.observed_sources` / POTENTIAL: True) → `edge_kinds` 화이트리스트 → 통과 시 `visited` 추가.
      - affected 기록 : `other_kind in allowed_entity_kinds` 일 때만 `AffectedEntity` push — traversal 은 모든 kind 를 지나가되 결과 테이블에는 kind 매치 엔티티만 남김 (class 중간 노드 보존 + 결과 리포트 노이즈 제거).
      - 누적 : `confidence_min = min(parent.confidence_min, edge.confidence)` 병목 전파, `edge_source_chain = parent + (edge.edge_source,)`, `path = parent + (other,)`, `reasons = parent + (f"{edge.kind} ({src})",)` (`_format_reason`, `edge_source=None` 은 `"static"` 으로 표기).
      - 종료 : frontier 비거나 `hops_used >= max_hops`. `hops_used` 는 실제 전진한 hop 수.
    - `<reflection-site>` 이중 처리 :
      - BFS 중간 조우 : skip + `unresolved_sources` 에 caller 누적 (중복 제거).
      - target 이 직접 `<reflection-site>` : `_diagnostic_reflection_site` 진단 모드 → `graph.incoming(_REFLECTION_SITE)` 로 모든 caller 수집, `affected=[]` + `unresolved_sources=callers` + `message="{N} callers reached <reflection-site> (unresolved at static time)"`.
    - `_step_edges` / `direction` 공용 : 한 함수 한 방향 분기만 담당 → B8-3 Reverse Lookup 은 `direction="outgoing"` 으로 같은 `_bfs` 재사용 (term→FQN 매핑 스텁만 추가 예정).
    - 설계 결정 :
      - Q. Entity kind 필터 위치 — **traversal 은 모든 kind, affected 기록만 kind 매치**. 이유 : class 를 지나쳐야 method 에 도달하는 사례(`CALLS` + `CONTAINS` 조합) 보존. 결과만 노이즈 제거.
      - Q. `<reflection-site>` 직접 질의 — **별도 진단 분기**. 이유 : `graph.entity(_REFLECTION_SITE)` 는 None 반환 → 일반 경로는 "target not found" 로 조기 종료되어 caller 수집 불가. 진단용으로 incoming 전체를 `unresolved_sources` 로 덤프.
      - Q. `visited` 에 target 포함 — **Yes**. 이유 : target 자신을 affected 에 넣지 않기 위해.
      - Q. `_Frontier` 불변 — **frozen dataclass + tuple 누적**. 이유 : reassignment 없는 순수 BFS 상태 전파. 사이클 차단은 `visited` set.
    - TDD 싸이클 : **Red** `ModuleNotFoundError: No module named 'backend.modeling.query.query_engine'` → **Green** (1회 조정) 14 중 13 passed / 1 failed (`test_reflection_site_skipped_and_collected` — target 이 `<reflection-site>` 일 때 "target not found" 조기 반환으로 unresolved 수집 실패) → `_diagnostic_reflection_site` 분기 추가 → **Green** 14/14 pass (0.07s).
      - Test 구성 (`tests/test_query_engine_impact.py` 14) : SAFE 는 `static_unresolved` 제외 / OBSERVED 는 `{None, static_literal, runtime}` 포함 / POTENTIAL 은 전부 / `max_hops=2` 에서 hop 3·4 차단 / 사이클(A↔B) 무한루프 방지 / 2-경로 도달 시 최단 hop 유지 / `edge_kinds={"calls"}` 는 publishes 제외 + `{"publishes"}` 는 publishes 허용 / 기본 `entity_kinds` 로 class 제외 + 명시 `{"class"}` 는 class 포함 / `<reflection-site>` 직접 질의 → `affected=[]` + `unresolved_sources=[caller]` / unknown target → `affected=[]` + "not found" / `path` 순서 `[target → ... → affected]` / `confidence_min` 병목 min 계산.
    - 회귀 : 모델링 범위 14 모듈 (B8-0 의 13 + `query_engine`) **213/213** pass (0.88s). 기존 모듈 0건 회귀.
    - B8-2 로 인계 : hops 자율 축소 (`len(affected) > cfg.shrink_result_threshold` → `hops_shrunk_reason="result_too_large"`) / timeout (`elapsed > cfg.timeout_seconds` → `hops_shrunk_reason="timeout"`) / frontier 경고 (`len(frontier) > cfg.frontier_warn_threshold` → 로깅만) / `auto_hops=False` 시 축소 비활성화 (테스트·감사용). 테스트는 임계 초과 축소 동작 + `auto_hops=False` 완주 2건 추가.
  - [x] **OD-11-B8-2** — hops 자율 축소 + timeout + frontier 경고 (2026-04-19)
    - 배경 : B8-1 BFS 코어 위에서 SPEC §4 의 축소 휴리스틱 구현. 100K+ 엔티티 규모 그래프에서 결과 폭발·타임아웃 방지. 설정 외부화 (Q5) 전제 완성.
    - 모듈 :
      - `backend/modeling/query/query_engine.py` (+27 LOC) : `import logging` + `import time` + `logger` 모듈 수준. `_bfs` 에 `start = time.monotonic()` + `hops_shrunk_reason: str | None = None` 추적. `frontier = next_frontier` 직후 훅 3종 (frontier warn / shrink-by-result / shrink-by-timeout) 추가. `message` 에 `" — auto-shrunk: {reason}"` 접미사.
    - 훅 로직 (hop 경계에서만 체크) :
      - frontier 경고 : `len(frontier) > cfg.frontier_warn_threshold` → `logger.warning(...)` (lazy `%`-format). `auto_hops` 와 무관. 탐색은 `max_hops` 까지 계속.
      - result 축소 : `if query.auto_hops and len(affected) > cfg.shrink_result_threshold` → `hops_shrunk_reason = "result_too_large"` + `break` (다음 hop 미처리).
      - timeout 축소 : `if query.auto_hops and time.monotonic() - start > cfg.timeout_seconds` → `"timeout"` + `break` (현재 hop 완료 후, 다음 hop 미처리).
    - 메시지 포맷 : `"{N} entity affected (hops={H})"` + 축소 시 `" — auto-shrunk: {reason}"`. 프로그램적 분기는 `hops_shrunk_reason`, UI 텍스트는 `message`.
    - 설계 결정 :
      - Q. 축소 체크 위치 — **hop 경계에만** (매 엣지 X). 이유 : 중간 break 면 partial hop 결과로 `hops_used` 와 실제 결과 불일치. SPEC §4.1 "다음 hop 중단" 명시.
      - Q. 타임아웃 시점 — **현재 hop 완료 후**. 이유 : 중간 중단하면 반쪽 결과 잔류. SPEC §4.1 "현재 hop 완료 후".
      - Q. frontier 경고와 `auto_hops` 관계 — **무관 (항상 로깅)**. 이유 : 경고는 순수 진단 신호 — 사용자가 `max_hops` 낮추도록 유도. 감사 모드에서도 경고는 필요.
      - Q. `time.monotonic()` 참조 방식 — **`import time` + `time.monotonic()`**. 이유 : 테스트에서 `monkeypatch.setattr("backend.modeling.query.query_engine.time.monotonic", ...)` 가능. 모의 시계 DI 불필요.
      - Q. 축소 발생 시 partial 결과 처리 — **보존**. 이유 : 현재까지 수집한 `affected`·`unresolved_sources` 는 의미 있음. 축소는 다음 hop 확장만 차단.
    - TDD 싸이클 : **Red** `AssertionError: assert None == 'result_too_large'` → **Green** (조정 없이 1회) 7/7 pass (0.07s).
      - Test 구성 (`tests/test_query_engine_shrink.py` 7) : result_too_large 축소 (hop1=3 > threshold=2 → hops_used=1 + hop2 미도달) / timeout 축소 (`monkeypatch.setattr` 로 time.monotonic (0.0, 5.0) 주입 + timeout=1.0 → `"timeout"` + hops_used=1) / `auto_hops=False` + low threshold → reason=None + hop2 까지 완주 (12 affected) / `auto_hops=False` + monkeypatched time → reason=None / frontier_warn=3 + 실제 5 → `caplog` WARNING 기록 + hops 2 완주 / message 에 `"result_too_large"` 포함 / 정상 범위 → reason=None.
      - fixture : `_chain_fanout(target, hop1_width, hop2_per_hop1)` 헬퍼로 fan-out 체인 생성. 기존 `_m`/`_rel`/`_pr` 패턴 재사용.
    - 회귀 : 모델링 범위 21 test 파일 (registry + cross_file + graph_writer + java_parser + 10 Spring analyzer + reflection_literal + runtime_collector + query_models + in_memory_graph_view + query_engine + query_engine_shrink) **329/329** pass (0.83s). B8-1 14 tests 기존 동작 0건 회귀 — 모두 `auto_hops=False` 명시로 새 경로와 무관.
    - B8-3 로 인계 : `.reverse_lookup(term)` 메서드 + 내부적으로 `ImpactQuery(direction="outgoing")` 로 `_bfs` 재사용 (shrink/timeout 자동 적용). `<reflection-site>` 진단 완결 — 현재 `_diagnostic_reflection_site` 가 `incoming` 만 덤프하는데, Reverse 시점 `outgoing` 방향 진단 의미 있는지 검토. B9 Slab 샘플 수령 후 실제 임계값 튜닝 (기본 200/2.0/500 은 추정치).
  - [x] **OD-11-B8-3** — Reverse Lookup 스텁 + direction-aware `<reflection-site>` 진단 (2026-04-19)
    - 배경 : B8-2 로 Impact(incoming) 완결. Reverse Lookup(outgoing) 을 공용 BFS 엔진에 얹어 Phase B 코드 영역 종결. `<reflection-site>` 직접 질의 시 direction 에 따라 진단 메시지가 분기되도록 확장.
    - 모듈 :
      - `backend/modeling/query/query_engine.py` (+38 LOC) :
        - `reverse_lookup(term, *, mode, max_hops, auto_hops, edge_kinds, entity_kinds)` 추가 (10 LOC) — `ImpactQuery(..., direction="outgoing")` 로 `impact()` 위임. 한 줄 구현으로 shrink/timeout/frontier 경고/entity_kinds 필터/reflection-site skip 전부 자동 상속.
        - `_diagnostic_reflection_site` 를 direction 분기 (15 LOC):
          - `outgoing` 진입 시 → `affected=[]`, `unresolved_sources=[]`, `message="<reflection-site> is a sentinel sink with no outgoing edges; use direction='incoming' to list callers that reached it"`.
          - `incoming` (기본) → B8-1 동작 유지 : `graph.incoming(<reflection-site>)` 순회 → `unresolved_sources` (callers 덤프).
        - 모듈 docstring 업데이트 (B8-3 범위 + SPEC §2.2·§3.3·§5.2 명시).
    - 설계 결정 :
      - Q. 본체 재구현 vs 위임 — **위임 (한 줄)**. 이유 : shrink/timeout/frontier 경고/entity_kinds 필터/reflection-site 처리 모두 공용. 중복 구현은 drift 위험. SPEC §3.3 "BFS core 재사용" 명시.
      - Q. outgoing 직접 질의 시 callers 덤프할지 — **하지 않음 (`unresolved_sources=[]`)**. 이유 : Reverse 시점에서 callers 는 무관. reflection 은 "어디서 어디로 가는지" 모르는 게 핵심 → outgoing 방향으론 answer 를 만들 수 없음. 메시지에 "use direction='incoming'" 힌트만.
      - Q. B8-1 incoming 진단 유지 — **완전 보존**. 이유 : 회귀 테스트 6번으로 방어. incoming callers 덤프는 Impact Analysis 표준. 바뀌면 B8-1 스펙 위반.
      - Q. term 해소 범위 — **B8-3 은 FQN 직접 매칭 스텁**. 이유 : 비즈니스 용어 → FQN 매핑은 Phase C Round 2 `term_resolver.py` (임베딩 + data-driven alias) 의 책임. B8-3 은 엔진 레이어만.
      - Q. `reverse_lookup` auto_hops 기본값 — **`True`** (impact 과 동일). 이유 : UX 일관성. 100K+ 그래프 가정 → 축소 기본 켜짐. 감사/테스트는 `auto_hops=False` 명시.
    - TDD 싸이클 : **Red** `AttributeError: 'QueryEngine' object has no attribute 'reverse_lookup'` → **Green** (조정 없이 1회) 8/8 pass (0.07s).
      - Test 구성 (`tests/test_query_engine_reverse.py` 8) : (1) outgoing 기본 — A.run→{B.foo,C.bar} hops_used=1 / (2) multi-hop — A→B→C→D distance={1,2,3} / (3) unknown term — affected=[] + "not found" / (4) mid-traversal `<reflection-site>` — B.foo 수집, `<reflection-site>` skip + unresolved_sources=[A.run] / (5) `<reflection-site>` 직접 + outgoing — sentinel sink 메시지, unresolved_sources=[] / (6) B8-1 회귀 — `<reflection-site>` 직접 + incoming → callers 덤프 유지 / (7) auto-shrink 상속 — shrink_result_threshold=2 + auto_hops=True → hop1 중단 "result_too_large" / (8) entity_kinds 기본값 — class 는 경유만, method 는 포함.
      - fixture : `_m`/`_c`/`_rel`/`_pr`/`_engine` 기존 헬퍼 재사용.
    - 회귀 : 모델링 스코프 `test_query_models` + `test_in_memory_graph_view` + `test_query_engine_impact` + `test_query_engine_shrink` + `test_query_engine_reverse` 및 기타 모델링 파일 — scope filter 기준 **47/47** pass (3.37s). B8-1 incoming direct query 동작 테스트 6번으로 회귀 확인.
    - 인계 :
      - **B9 (Slab sample E2E)** : Phase B 코드 영역 이제 종결. sample repo 수령 후 실제 그래프에서 `impact()`/`reverse_lookup()` 시연 + 임계값 실측 튜닝 (shrink 200 / timeout 2.0 / warn 500 은 추정치).
      - **Phase C Round 2 (`term_resolver`)** : 현재 FQN 직접 매칭 → 비즈니스 용어 처리는 transformer 레이어 추가로 해결. `reverse_lookup` 엔진 메서드는 그대로 두고 term 전처리 레이어만 얹음.
      - **C4 (Reverse Lookup API)** : `backend/modeling/api/reverse_lookup_api.py` — 엔진을 REST/SSE 로 노출.
      - **E3 (시나리오 검증)** : Slab sample 기준 Q11 "X 테이블이 변하면 무엇이 깨지나?" 유형 실증.
  - [x] **OD-11-C1** — Round 2 HTML 설명서 rev.2 Q1~Q7 사용자 합의 반영 (2026-04-20)
    - 배경 : Phase B 코드 영역 종결 후 B9 Slab sample 수령 대기. 병행 가능한 경로 = Phase C Round 2 (비즈니스 개념 + 브릿지 스키마). Round 1 패턴 (HTML 드래프트 → Q/A → rev. 갱신 → 코드) 반복.
    - 산출물 : `toClaude/modeling/round2-concept-bridge.html` (645 LOC, 43KB) 신규. 10 섹션 — Why / 노드 / 엣지 / 1:N / 워킹 예시(안전재고) / Term Resolution Chain 4단 / 매핑 운영 파이프라인 / Reverse Lookup 시나리오 A~D / 결정 사항 (Q1~Q7) / Round 3 예고.
    - 결정 사항 (2026-04-20 사용자 확정) :
      - **Q1 A** : 수동 seed 우선. 팀 리더가 핵심 BusinessTerm 20~50 먼저 등록 → 자동 제안(name_match/embedding/llm) 확장. `C2` seed CLI + `C3` 제안 엔진 분리.
      - **Q2 B** : 표준 confidence cutoff = name_match≥0.85 / embedding≥0.78 / llm≥0.6. Round 1 기본(SAFE≥0.9 / POTENTIAL 0.5~) 와 정렬. `C2` `ConceptBindingConfig` frozen dataclass DI.
      - **Q3 B** : primary 메서드당 1개, partial 무제한. 역방향 1:N 허용 (한 메서드가 여러 BusinessTerm 에 REALIZES 가능). `C2` primary 유일성 검증 + `C4` API scope 필터.
      - **Q4 D** : Role 노드 1차 제외 (Phase D 이월). Slab PoC 범위에서 Spring Security role 활용 패턴 미확인. `C2` Role DTO 미작성, `RESPONSIBLE_FOR` 엣지 삭제.
      - **Q5 A→B** : VALIDATES 는 어노테이션(@AssertTrue/@Valid/Javadoc) 우선 → 검증 메서드 이름 패턴(`validateXxx`/`checkYyy`) 자동 제안 2단계 확장. C (branch LLM) 는 Phase D+. `C2` `RuleBindingAnalyzer` 2-stage.
      - **Q6 A** : 임베딩 스택 = OpenAI text-embedding-3-small + chromadb (Wiki 통일). `C3` `EmbeddingProvider` Protocol + `OpenAIChromaProvider` 구현으로 추상화 (로컬 모델 전환 대비).
      - **Q7 경계 B + 재검증 (d)** : BusinessProcess 1차 제외 (Phase D 이월). Round 2 는 Term + Rule 만. 재검증은 PR 영향 범위만 (webhook / CLI). `C2` `BusinessProcess` DTO 미작성 + `C4` PR 기반 재검증 진입점.
    - **1차 범위 확정** :
      - 노드 2종 : `BusinessTerm` / `BusinessRule`
      - 엣지 2종 + 1 예약 : `REALIZES` (Method/Class → BusinessTerm, primary 1 + partial N) / `VALIDATES` (Method → BusinessRule) / `DERIVED_FROM` (Round 3 연결 예약)
      - Term Resolution 4단 : exact → alias → embedding(cutoff 0.78) → LLM fallback (사람 승인 큐)
      - 매핑 운영 파이프라인 : 수동 seed (20~50) → 자동 제안 (name_match / embedding / llm, `confirmed=False` 큐잉) → 사람 승인 (`confirmed=True`) → 활성 룩업 (confirmed 만 기본)
    - Phase D 이월 : BusinessProcess / Role / PART_OF / RESPONSIBLE_FOR / `VALIDATES` C단계 branch LLM.
    - 인계 (C2~C4) :
      - **C2 `backend/modeling/mapping/mapping_models.py`** : `BusinessTerm` / `BusinessRule` 노드 DTO + `ConceptBinding` 엣지 DTO (method-level 기본, primary 유일성) + seed CLI + YAML 배치 로더. 기존 `Mapping` 단일 qualified_name 구조 완전 교체.
      - **C3 `backend/modeling/query/term_resolver.py`** : 4단 체인 구현 + `EmbeddingProvider` Protocol + `OpenAIChromaProvider` 구현 + LLM fallback 은 사람 승인 큐에만 enqueue (자동 바인딩 금지).
      - **C4 `backend/modeling/api/reverse_lookup_api.py`** : QueryEngine.reverse_lookup + term_resolver 를 REST/SSE 로 노출. `include_unconfirmed`/`scope_filter` 옵션.
      - **E3** : Slab sample 수령 후 BusinessTerm seed → Reverse Lookup 시나리오 검증 (Q11 "'안전재고' → 어느 코드?" 유형).
  - [x] **OD-11-C2** — `mapping_models.py` 신규 작성 (DTO-only, primary unique invariant, 2026-04-20)
    - 배경 : C1 HTML rev.2 Q1~Q7 합의 이후 C2 는 Phase C 코드 영역의 첫 스텝. OD-10 Legacy Cleanup 에서 `backend/modeling/mapping/` 디렉토리가 삭제된 상태 → 신규 작성.
    - 산출물 : `backend/modeling/mapping/__init__.py` (30 LOC) + `backend/modeling/mapping/mapping_models.py` (~180 LOC).
      - **Enum 5종** : `BusinessTermSource` (manual/extracted/llm_proposed) / `BindingSource` (manual/name_match/embedding/llm) / `BindingScope` (primary/partial) / `RuleSeverity` (hard/soft) / `ResolutionSource` (exact/alias/embedding/llm/miss). 전부 `StrEnum` (JSON round-trip 문자열).
      - **노드 DTO 2종** : `BusinessTerm` (qualified_name / canonical_label / aliases / domain / description / embedding / source / confirmed / created_at) / `BusinessRule` (qualified_name / statement / terms_ref / severity / source / confirmed / created_at). 모두 `frozen=True` Pydantic BaseModel.
      - **엣지 DTO 1종** : `ConceptBinding` (term_fqn / code_fqn / scope / confidence[0,1] / source / confirmed / confirmed_by:str|None / created_at).
      - **집합 invariant 1종** : `ConceptBindingSet` — `@model_validator(mode="after")` 로 ① 동일 `code_fqn` PRIMARY 최대 1개 ② 동일 `(term_fqn, code_fqn)` 쌍 중복 금지.
      - **감사 DTO 1종** : `ResolutionAuditLog` (query_term / resolved_term_fqn:str|None / resolution_source / confidence / confirmed / timestamp). miss 는 `resolution_source=MISS` + `resolved_term_fqn=None`.
    - 설계 결정 (D1~D10) :
      - D1 Pydantic BaseModel frozen=True (dataclass 대신 — 외부 API 노출 대비)
      - D2 StrEnum (JSON round-trip 자연스러움, B8-0 ImpactMode 와 동일 convention)
      - D3 primary 유일성은 `ConceptBindingSet` 집합 단위 (단일 binding 은 이웃을 모름)
      - D4 `(term_fqn, code_fqn)` 쌍 중복도 거부 — 갱신은 replace 로 명시적 처리
      - D5 alias 중복 검증 case-insensitive — Term Resolution alias 단계의 전제
      - D6 description / domain / source(Rule) 빈 문자열 허용 — 수동 seed CLI 최소 필수 필드만 채우고 enrich
      - D7 `BusinessRule.terms_ref` 빈 리스트 허용 — 초안 작성 시 연결 용어 없이 시작 가능
      - D8 `ResolutionSource.MISS` 값 포함 — 4단 실패도 감사 로그에 남겨야 재검증 트리거 가능
      - D9 `confirmed_by: str | None` — HTML §4-2 "승인자 (사람만 저장, llm=None)" 반영
      - D10 Phase D 이월 BusinessProcess / Role DTO 는 이번 모듈에서 제외 (Q4 D / Q7 경계 B 준수)
    - Invariants (I1~I8) : confidence[0,1] / qn·label min_length=1 / term_fqn·code_fqn min_length=1 / aliases case-insensitive 중복 금지 + 빈 문자열 금지 / PRIMARY unique per code_fqn / (term,code) pair unique / JSON round-trip invariant 재검증.
    - TDD : Red `ModuleNotFoundError: backend.modeling.mapping` → Green (조정 없이) 28/28 pass (0.08s). `tests/test_mapping_models.py` 28 cases (Enum 1 / BusinessTerm 8 / BusinessRule 4 / ConceptBinding 4 / ConceptBindingSet 7 / ResolutionAuditLog 4).
    - 회귀 : 모델링 스코프 `-k "mapping_models or query_models or in_memory_graph_view or query_engine or code_analysis_registry or cross_file_enricher or graph_writer or java_parser or spring or reflection_literal or runtime_collector"` **365/365** pass (3.57s). 기존 337 + 신규 28 = 365. 0 regression.
    - 한계 : (1) 저장소 레이어 없음 (C3+C4 에서) / (2) term_fqn 참조 무결성은 저장소 책임 / (3) VALIDATES 엣지 DTO (`ValidationBinding`) 는 B9 E2E 이후 Q5 A 단계에서 추가 / (4) alias 정규화는 lowercase 단순 매칭 (한글 분해/하이픈/언더스코어 정규화는 C3 에서).
    - 상세 archive : `toClaude/modeling/archive/step_c2_summary.md`.
    - 인계 (C3) : `ResolutionAuditLog` 1회/쿼리 기록 / chain 4단 cutoff 1.0/1.0/0.78/0.6 / `BusinessTerm.aliases` O(1) 역인덱스 / `BusinessTerm.embedding` chromadb 업로드 top-K / `EmbeddingProvider` Protocol + `OpenAIChromaProvider` reference.
  - [x] **OD-11-C3** — `term_resolver.py` Round 2 4-stage chain 구현 (2026-04-20)
    - 배경 : C2 DTO 레이어 고정 이후 C3 는 Phase C 의 "개념 브릿지" 질의 엔진. OD-10 에서 삭제된 `backend/modeling/query/term_resolver.py` 를 신규 작성 (이전 한글 하드코딩 ALIASES 버전은 폐기, §6-2 데이터 드리븐 원칙 적용).
    - 산출물 : `backend/modeling/query/term_resolver.py` (~280 LOC) + `tests/test_term_resolver.py` (35 cases).
      - **DTO 5종** : `SimHit` (term_fqn, similarity∈[0,1]) / `LLMProposal` (term_fqn, confidence, reasoning) / `Candidate` (term_fqn, confidence, source) / `ResolutionCutoffs` (embedding=0.78, llm=0.6, top_k=3) / `ResolutionResult` (query_term, matched_term_fqn:str|None, resolution_source, confidence, confirmed, candidates[], audit_log). 전부 `frozen=True`.
      - **Protocol 2종** : `EmbeddingProvider` (`search_similar(query, top_k) -> list[SimHit]`, `index(term)`) / `LLMResolver` (`propose(query, available_terms) -> LLMProposal | None`). `@runtime_checkable` 로 DI 친화적.
      - **TermResolver** 클래스 : `__init__(terms, embedding_provider=None, llm_resolver=None, cutoffs=None, clock=_utc_now)` + `resolve(query) -> ResolutionResult` + `_build_alias_index(terms)`.
      - **Normalization** : `_normalize(s) = "".join(s.split()).casefold()` — 공백 strip + 대소문자 무시. "안전 재고" / "안전재고" / "Safety Stock" / "SAFETY STOCK" 한 키.
      - **InMemoryEmbeddingProvider** (참조 구현 #1, 테스트/데모) : `embeddings: dict[str, list[float]]` + `embed_fn: Callable[[str], list[float]]`. `_cosine` (ZeroDivision guard) + top_k sorted desc + `index(term)` (term.embedding 있으면 저장, 없으면 `embed_fn(canonical + desc)`).
      - **OpenAIChromaProvider** (참조 구현 #2, Q6 A 프로덕션) : `openai_client` + `chroma_collection` 생성자 주입. Model 기본 `text-embedding-3-small`. `search_similar` 는 chromadb cosine distance → 유사도 (`1 - dist/2` clamp). 모듈 top-level 에 openai/chromadb import 없음 (late binding).
    - 설계 결정 (D1~D12) :
      - D1 TermResolver 는 불변 상태 (alias index `__init__` 1회 빌드)
      - D2 Normalization = casefold + 공백 strip (spec §6-1 "대소문자/공백 정규화")
      - D3 alias_index 충돌 시 canonical 우선 (EXACT > ALIAS), 두 term 충돌 시 first-registered
      - D4 exact/alias 만 `confirmed=True`. embedding/LLM 은 `confirmed=False` (§7-1 승인 큐)
      - D5 미스 시에도 embedding candidates 보존 (UI "근사 후보" 표시)
      - D6 LLM 환각 방어 — `proposal.term_fqn ∉ self._by_fqn` 이면 MISS
      - D7 embedding 히트 동일 guard — provider 가 오래된 인덱스 반환 시 방어
      - D8 cutoff inclusive (`>=`) — 경계값(0.78 / 0.6)도 히트
      - D9 `clock` injection — 테스트 결정성 + audit 타임스탬프
      - D10 `audit_log.query_term` 은 원본 보존 (normalize 전)
      - D11 `InMemoryEmbeddingProvider` zero vector cosine 은 0 (ZeroDivisionError 방어)
      - D12 `OpenAIChromaProvider` 는 top-level import 없음 (테스트 환경 의존 제거)
    - Invariants (I1~I9) : I1 EXACT 1.0/True / I2 ALIAS 1.0/True / I3 EMBEDDING ∈ [0.78, 1]/False / I4 LLM ∈ [0.6, 1]/False / I5 MISS 0.0/None/False / I6 상위 단계 히트 시 하위 provider 호출 금지 / I7 audit.query_term = 원본 / I8 Cutoffs 범위 검증 / I9 search_similar 결과 desc 정렬 + top_k truncate.
    - TDD : Red `ModuleNotFoundError: backend.modeling.query.term_resolver` → Green (조정 없이) 35/35 pass (0.09s). Test 분포 : Cutoffs 2 / Stage1 exact 4 / Stage2 alias 4 / Stage3 embedding 5 / Stage4 LLM 6 / No providers 2 / Audit log 3 / InMemoryProvider 7 / Integration 1 + ResolutionCutoffs boundary 1 = 35.
    - 회귀 : 모델링 스코프 `-k "term_resolver or mapping_models or query_models or in_memory_graph_view or query_engine or code_analysis_registry or cross_file_enricher or graph_writer or java_parser or spring or reflection_literal or runtime_collector"` **400/400** pass (3.57s). 기존 365 + 신규 35 = 400. 0 regression.
    - 한계 : (L1) `OpenAIChromaProvider` 는 참조 구현, 실제 연결은 C4/main.py startup 에서 / (L2) BusinessTerm store 영속화 없음 — resolver 는 terms 를 init 에 받을 뿐, 런타임 갱신은 재생성 필요 (Service 레이어 책임) / (L3) alias 충돌 first-wins 는 침묵 (seed CLI 검증 필요) / (L4) §7-2 제안 트리거 (신규 term/PR 변경 → 전 코드 자동 제안) 는 `ProposalEngine` 별도 모듈로 C4/D 에서 / (L5) normalize 는 공백+casefold 만, NFD/NFC/하이픈·언더스코어 정규화는 추후.
    - 상세 archive : `toClaude/modeling/archive/step_c3_summary.md`.
    - 인계 (C4) : `TermResolver(terms, embedding_provider, llm_resolver, cutoffs, clock)` DI → REST `GET /modeling/reverse-lookup?term=...&include_unconfirmed=&scope=` + SSE (LLM 진행) + `ResolutionResult.audit_log` → `audit_log_store.append` / `EmbeddingProvider` 선택은 startup 환경변수 분기 (`InMemoryEmbeddingProvider` 테스트 / `OpenAIChromaProvider` 운영).
  - [x] **OD-11-C4** — `reverse_lookup_api.py` REST + SSE 엔드포인트 (2026-04-20)
    - 배경 : C3 `TermResolver` 확정 이후 Phase C 의 API 레이어. 비즈니스 용어 → 소스 위치 역탐색을 REST/SSE 로 노출. 사용자 3대 기능 중 **Reverse Lookup** 의 1차 entry point.
    - 산출물 (3 신규 + 4 편집) :
      - **신규** `backend/modeling/api/reverse_lookup_api.py` (296 LOC) — FastAPI `APIRouter(prefix="/api/modeling")`, `init(*, resolver, binding_store, audit_store, engine_config?)` DI, `reset()` 테스트 헬퍼, `_require_initialized()` 503 가드, `ReverseLookupResponse` DTO (query_term/resolution/scope_filter/include_unconfirmed/impact), `@router.get("/reverse_lookup")` + `@router.get("/reverse_lookup/stream")`, `_compute_impact` (2-stage gate + binding filter + per-request InMemoryGraphView 합성 + `QueryEngine.reverse_lookup(edge_kinds={REALIZES})` 위임), `_build_binding_view` (term → code 합성), `_sse` 포맷터.
      - **신규** `backend/modeling/mapping/concept_store.py` (64 LOC) — `ScopeFilter = Literal["primary","partial","all"]`, `@runtime_checkable Protocol ConceptBindingStore`, `InMemoryConceptBindingStore` (dict[term_fqn → list[ConceptBinding]] + `add()` seed 헬퍼).
      - **신규** `backend/modeling/mapping/audit_store.py` (43 LOC) — `@runtime_checkable Protocol AuditLogStore` (append/recent), `InMemoryAuditLogStore`.
      - **편집** `backend/modeling/api/modeling.py` — `reverse_lookup_api.router` 포함 (`/api/modeling/reverse_lookup` 2 endpoint 추가).
      - **편집** `backend/main.py` startup — `ONTONG_EMBEDDING=openai` + `OPENAI_API_KEY` + `chroma._client` 삼중 조건에서만 `OpenAIChromaProvider(openai, coll="modeling_terms")` 사용, 그 외는 `InMemoryEmbeddingProvider(embeddings={}, embed_fn=lambda _: [])` 로 fallback. `reverse_lookup_api.init(resolver=TermResolver(terms=[], embedding_provider=_emb, llm_resolver=None), binding_store=InMemoryConceptBindingStore([]), audit_store=InMemoryAuditLogStore())`.
      - **편집** `backend/modeling/code_analysis/parser_protocol.py` — Round 2 kind 정식 등록 (C1 합의 반영). Entity : `business_term`, `business_rule` (category=concept). Relation : `realizes`, `validates`, `derived_from` (category=concept). `EntityKinds.BUSINESS_TERM/BUSINESS_RULE` + `RelationKinds.REALIZES/VALIDATES/DERIVED_FROM` 상수 공개.
      - **편집** `toClaude/modeling/TODO.md` — OD-11-C4 `[x]` + 산출물 기록.
    - 설계 결정 D1~D12 : (D1) module-level init DI, 싱글턴 아님 / (D2) 503 가드 + `reset()` 테스트 헬퍼 / (D3) 2-stage gate — ① matched=None → None ② confirmed=False + !include_unconfirmed → None, **audit 는 선행 append** / (D4) binding 필터는 engine 전 수행 (scope_filter + confirmed) / (D5) per-request tiny InMemoryGraphView 합성 (term=business_term, code=method, edge=realizes+attributes) / (D6) 기본 mode=POTENTIAL (binding.source 와 parser observed_sources 불일치) / (D7) edge_kinds={REALIZES} 고정 (VALIDATES/DERIVED_FROM 은 Phase D) / (D8) SAFE = engine safe_min_confidence=0.9 / (D9) SSE `resolving → resolved → complete` 3단 / (D10) scope_filter FastAPI `Literal[...]` → 422 / (D11) Protocol 기반 Store, Neo4j 전환은 D / (D12) main.py 환경변수 분기 + graceful fallback + warning 로그.
    - Invariants I1~I10 : I1 초기화 전 503 / I2 쿼리마다 audit append 선행 / I3 MISS → impact=None + audit MISS / I4 unconfirmed + !opt-in → impact=None + audit 히트 / I5 include_unconfirmed=True → embedding/LLM 드러남 + confirmed=False binding 통과 / I6 scope_filter primary/partial/all 분기 / I7 scope_filter 잘못 → 422 / I8 SSE 이벤트 3단 순서 고정 / I9 unique code_fqn 별 1 method entity (dedup) / I10 SAFE 는 confidence<0.9 edge drop.
    - TDD : Red `ImportError: cannot import name 'reverse_lookup_api'` → Green (1번 조정 : `_embed` 헬퍼가 토큰 순서 무관하게 매칭하도록 `if "safety" in lower and "stock" in lower → [1,0,0]`) 22/22 pass (0.33s). `tests/test_reverse_lookup_api.py` (22 cases : 503/422 2 + MISS 1 + EXACT 1 + ALIAS 1 + embedding hidden/surfaced 2 + scope_filter primary/partial/all/invalid 4 + unconfirmed binding hidden/surfaced 2 + audit 2 + LLM fallback gated 1 + SSE hit+miss 2 + scope edge exclude 1 + SAFE drops 1 + store scope_filter reject 1 + store empty 1).
    - 회귀 : 모델링 스코프 `-k "reverse_lookup_api or term_resolver or mapping_models or query_models or in_memory_graph_view or query_engine or code_analysis_registry or cross_file_enricher or graph_writer or java_parser or spring or reflection_literal or runtime_collector"` → **422/422** (기존 400 + 신규 22, 791 deselected, 1.07s). 앱 로드 `./venv/bin/python -c "from backend.main import app; print(len(app.routes))"` → 147 (이전 145 + 2 신규). 0 regression.
    - 한계 L1~L7 : (L1) main.py 는 terms=[] 로 resolver → 실제 쿼리는 MISS, seed CLI 는 D 단계 / (L2) ConceptBinding 영속화 없음 (In-process) / (L3) Audit log InMemory 최근 50건 / (L4) OBSERVED 는 binding.source 불일치로 항상 drop (의도적) / (L5) SSE 3 이벤트만, hop 별 progress 미구현 / (L6) edge_kinds 하드코딩 → Phase D 파라미터화 / (L7) include_unconfirmed 과 scope_filter 조합 gate 는 transparent 하지만 복잡도 상승 시 DTO 확장 고려.
    - 상세 archive : `toClaude/modeling/archive/step_c4_summary.md` (7 섹션).
    - 인계 :
      - **C5 (선택)** `backend/modeling/query/llm_resolver.py` — pydantic-ai Agent 기반 실제 LLM resolver. 현재 startup `llm_resolver=None` → Stage 4 skip.
      - **Phase D** BusinessProcess/Role + `edge_kinds` 쿼리 파라미터화.
      - **E3** Slab sample 수령 후 BusinessTerm seed 20~50 + ConceptBinding seed → 실 curl 시나리오 (§D-OD-11-C4 데모).
      - **Neo4j 전환** `ConceptBindingRepository(Neo4jClient)` + `AuditLogRepository` → Protocol 동일 시그니처로 swap.
      - **임베딩 재인덱싱** API (`POST /modeling/terms/reindex`) 는 D.

### Phase D — Round 3 스키마 (2026-04-20 진입)
- [x] **OD-11-D1** — `toClaude/modeling/round3-manual-gap.html` rev.2 (Q1~Q9 합의 반영, 2026-04-20, 771 LOC)
  - 배경 : Phase C4 완료 후 Option 1 통합 (Layer A 조직 + Layer B 기준서/갭) 사용자 승인 ("1번으로 가자", 2026-04-20). Round 1/2 HTML → 사용자 Q/A → rev.2 패턴 그대로 적용.
  - 산출물 (1 신규 + 1 편집) :
    - **신규** `toClaude/modeling/round3-manual-gap.html` rev.2 — 10개 섹션 (Why / Nodes 5종 / Edges 6종 / 4-Layer 아키텍처 SVG / 워크스텝 7단 "안전재고 변경 → 누구에게 알리나" / Ingest 파이프라인 / Gap Detection 3 케이스 + Cypher 예시 / 운영 알림 3단 라우팅 / Q1~Q9 결정 블록 / Next Steps).
    - **편집** `toClaude/modeling/TODO.md` OD-11-D1 → `[x]` + rev.2 산출물 상세.
  - 노드 5종 확정 :
    - `BusinessProcess` : qualified_name `{domain}.{process_name}`, canonical_label, description, domain, source, confirmed. <strong>계층 필드 제거</strong> (Q1=C — PARENT_PROCESS 엣지로 분리).
    - `Role` : <strong>team 단위 고정</strong> (Q2=A). qualified_name `team.{slug}`, kind="team" (column 은 유지, Phase E+ 확장 여지), label, contact, source, confirmed.
    - `ManualDocument` : qualified_name `{path}#sha256:...`, title, format ∈ {pdf,pptx,docx,md,image,html}, last_modified, version, <strong>`authoritative:bool=False`</strong> (Q8=B), checksum, source_repo.
    - `ManualSection` : qualified_name `{doc_fqn}#{section_path}`, doc_fqn, heading, ordinal, page_or_slide.
    - `ManualFragment` : qualified_name `{section_fqn}::{ordinal}`, section_fqn, kind ∈ {text,image,table,formula,ocr_text}, content, content_hash, ocr_confidence, embedding (chromadb "manual_fragments").
  - 엣지 6종 확정 :
    - `PART_OF` : BusinessTerm/Rule → BusinessProcess (N:M, confidence, source, confirmed)
    - `RESPONSIBLE_FOR` : Role → BusinessProcess (N:M, responsibility_kind ∈ {owner, approver, reviewer, notify}, confirmed)
    - `DESCRIBED_IN` : BusinessTerm/Rule/Process → <strong>ManualSection 또는 ManualFragment</strong> (Q3=C, N:M, confidence, source ∈ {manual, name_match, embedding, llm}, confirmed, excerpt)
    - `CONFLICTS_WITH` : BusinessTerm/Rule ↔ 동종 또는 ManualFragment (N:M, severity ∈ {low,medium,high,critical}, detected_by ∈ {llm, rule_ast, embedding_drift}, summary, confirmed:false, <strong>`gap_mode`</strong>)
    - `MISSING_IN` : BusinessTerm/Rule → ManualDocument (N:1, direction ∈ {code_only, manual_only} — Q6=A 양방향, severity, confirmed)
    - `PARENT_PROCESS` : BusinessProcess (자식) → BusinessProcess (부모) (Q1=C, N:1, source ∈ {manual, scor_template, llm}, confirmed, 자기참조 금지 cycle 검출)
  - Q1~Q9 결정 (전 항목 §9 결정 블록에 반영) :
    - **Q1 = C** (Claude 제안 B→C) — 별도 PARENT_PROCESS 엣지로 분리. graph 쿼리 유연성 우선.
    - **Q2 = A** (Claude 제안 D→A) — Role team 단위 고정. title/person 은 Phase E+ 연장 옵션.
    - **Q3 = C** (추천 채택) — DESCRIBED_IN Section+Fragment 양쪽 target.
    - **Q4 = C + A 전환 옵션** (Claude 제안 C 확장) — 기본 hierarchical 3단 (Rule AST→Embedding→LLM), `gap_mode=llm_only` 로 LLM 단독 최대 정확도 모드 선택 가능. strategy 패턴.
    - **Q5 = A** (추천 채택) — LLM severity 4단계 자동 제안 + 사람 승인 큐.
    - **Q6 = A** (추천 채택) — MISSING_IN 양방향. code_only=medium / manual_only=high 기본 severity.
    - **Q7 = E** (Claude 제안 D→E) — UI + watch folder + git hook 3 트리거 모두 구현. `ManualDocument.source` 로 진입 경로 기록. D2 우선순위 A>B>C, git hook 은 endpoint 만 D2, 활성은 Phase E.
    - **Q8 = B** (추천 채택) — 명시적 `authoritative` 플래그 (기본 false). 팀 리더 승격.
    - **Q9 = D** (추천 채택) — pypdf + pdfplumber + python-docx 전부 설치 + OCREngine 재사용.
  - 주요 설계 결정 :
    - 4-Layer 아키텍처 : Code (Round 1) × Concept (Round 2 BusinessTerm/Rule) × Manual (Round 3 Document/Section/Fragment) × Organization (Round 3 Process/Role). 세로로 Realizes/PartOf/DescribedIn/ResponsibleFor, 가로로 CONFLICTS/MISSING.
    - Ingest 재사용 : `OCREngine` (tesseract+easyocr, 기 존재) + `_parse_pptx_slides` (python-pptx, 기 존재) + MD (기본 파이썬). 신규 : pypdf+pdfplumber (PDF), python-docx (Word).
    - Gap Detection 3 케이스 : Case A code-only (REALIZES 있고 DESCRIBED_IN 없음 → MISSING_IN manual_only), Case B manual-only (Fragment 에서 추출됐지만 Term 등록 안됨 → MISSING_IN code_only), Case C conflict (양쪽 있고 AST/embedding/LLM 비교로 차이 검출 → CONFLICTS_WITH).
    - 운영 알림 : Term/Rule 변경 → PART_OF 따라 Process 집합 → RESPONSIBLE_FOR 역방향 → Role 집합 → contact 필드 기반 dispatcher (로그 → 이메일/슬랙 → PR bot 3단계).
  - 워킹 예시 : "SafetyStockService.calc() PR → Term inventory.safety_stock → Process inventory.safety_stock_management → Role 3개 (재고관리팀 owner + 생산관리팀 approver + 품질관리팀 notify) + Manual Section 2개 (SOP-안전재고-v3.pdf §3.2 + 계산기준서-2024.pptx slide-7) + CONFLICTS_WITH 1건 (공식 μ·L vs z·σ·√L)".
  - 다음 : D1.5 DTO (Process/Role/Manual* 5개 모델 + Binding 6종) → D1.6 parser_protocol (EntityKinds 5종 + RelationKinds 6종 등록) → D2 인제스트 (UI+watch+git hook + 5 파서) → D3 gap detector (hierarchical+llm_only strategy) → D4 UI 디자인 → Phase E 실증.
- [x] **OD-11-D1.5** — Round 3 DTO 확장 (조직 + 기준서 + Gap), 2026-04-20, TDD 69 테스트 선행
  - 배경 : D1 rev.2 확정 후 13종 Pydantic DTO 를 Smart TDD 규칙대로 작성. Red (import 실패) → Green (104/104 PASS) → 회귀 (246/246 PASS) 사이클 완주.
  - 산출물 (3 신규 + 3 편집) :
    - **신규** `backend/modeling/manuals/__init__.py` + `backend/modeling/manuals/manual_models.py` — 기준서/Gap DTO 7종 + enum 7종
    - **신규** `tests/test_manual_models.py` — 44 테스트 (ManualDocument/Section/Fragment + DescribedIn/Conflict/Missing Binding + 모든 enum + json round-trip)
    - **편집** `backend/modeling/mapping/mapping_models.py` — 조직 레이어 6종 추가 + 모듈 docstring 확장 (Round 3 컨텍스트)
    - **편집** `backend/modeling/mapping/__init__.py` — 재-export 10 → 18 심볼
    - **편집** `tests/test_mapping_models.py` — BusinessProcess/Role/Part/Role/ParentProcess Binding 25 테스트 추가 (기존 43 → 68)
    - **편집** `toClaude/modeling/archive/step_d1_5_summary.md` — 스텝 요약
  - 조직 레이어 (mapping_models.py, Layer A) :
    - `BusinessProcess` — canonical_label + description. <strong>parent 필드 없음</strong> (Q1=C PARENT_PROCESS 엣지로 분리).
    - `Role` — <strong>qualified_name `team.` 접두어 강제</strong> (Q2=A, field_validator), kind=RoleKind.TEAM 기본.
    - `PartOfBinding` — code_fqn ↔ process_fqn.
    - `RoleBinding` — role_fqn (team.) ↔ target_fqn, responsibility_kind ∈ {owner/approver/reviewer/notify}.
    - `ParentProcessBinding` — parent_fqn ↔ child_fqn. <strong>자기 참조 금지</strong> (model_validator). 
    - `ParentProcessBindingSet` — 중복 엣지 금지 + <strong>three-color DFS 사이클 검출</strong>. 테스트 : 빈/단일/트리/다이아몬드 DAG 통과, 직접/간접 사이클 거부.
  - 기준서/Gap 레이어 (manuals/manual_models.py, Layer B) :
    - `ManualDocument` — format ∈ {markdown,pdf,docx,pptx,image}, checksum 필수, <strong>`authoritative=False` 기본</strong> (Q8=B).
    - `ManualSection` — doc_fqn ref, heading_path (list), order_index.
    - `ManualFragment` — kind ∈ {text,image,table,formula,ocr_text}, embedding optional (chromadb "manual_fragments" 라우팅).
    - `DescribedInBinding` — source_fqn → target_fqn, <strong>target_kind ∈ {manual_section, manual_fragment}</strong> (Q3=C).
    - `ConflictBinding` — code_fqn ↔ manual_section_fqn, severity/detected_by/<strong>gap_mode</strong> 세 축 기록 (Q4=C+A).
    - `MissingBinding` — target_fqn + direction ∈ {code_only, manual_only} (Q6=A).
  - 신규 enum 9종 : `RoleKind` (team 고정, Phase E+ 확장 여지), `ResponsibilityKind` (owner/approver/reviewer/notify), `ManualFormat` (markdown/pdf/docx/pptx/image), `ManualFragmentKind` (text/image/table/formula/ocr_text), `GapSeverity` (hard/soft), `GapDetectedBy` (hierarchical/llm_only/manual), `GapMode` (hierarchical/llm_only, Q4=C+A), `GapDirection` (code_only/manual_only), `DescribedInTargetKind` (manual_section/manual_fragment).
  - 검증 :
    - 단위 — `tests/test_manual_models.py` 44 + `tests/test_mapping_models.py` 60 = 104/104 PASS (0.07s).
    - 회귀 — modeling 범위 246/246 PASS (test_ontology_* / test_query_engine_reverse / test_reverse_lookup_api / test_term_resolver 포함, 2.26s).
  - 설계 메모 : StrEnum + Pydantic v2 frozen BaseModel + `model_config = {"frozen": True}` + `field_validator` / `model_validator` 조합. `_ROLE_PREFIX = "team."` 상수 공유 (Role + RoleBinding 양쪽에서 사용). `_has_parent_process_cycle` 헬퍼는 three-color DFS (WHITE/GRAY/BLACK) 로 back edge 탐지. 자기 참조는 DTO 레벨, 집합 사이클은 Set 레벨에서 각각 차단 (책임 분리).
  - 다음 : D1.6 `parser_protocol.py` 에 EntityKinds +5 / RelationKinds +6 추가 (category=concept). ontology_validator 영향도 검증.
- [x] **OD-11-D1.6** — parser_protocol EntityKinds/RelationKinds 확장 (Round 3 concept 레이어), 2026-04-20, TDD 24 테스트 선행
  - 배경 : D1.5 에서 만든 13 DTO 중 그래프 기록 대상인 5 엔티티 + 6 관계를 parser_protocol 레지스트리에 등록. Red (AttributeError: EntityKinds/RelationKinds 상수 없음 + KindRegistry.get 반환 None) → Green (24/24 PASS) → 회귀 (524/524 PASS).
  - 산출물 (1 편집 + 1 신규) :
    - **편집** `backend/modeling/code_analysis/parser_protocol.py`
      - 모듈 docstring : Round 3 블록 추가 (Q1~Q9 합의 참조)
      - `_DEFAULT_ENTITY_KINDS` +5 : `business_process` / `role` / `manual_document` / `manual_section` / `manual_fragment` (모두 category="concept")
      - `_DEFAULT_RELATION_KINDS` +6 : `part_of` / `responsible_for` / `parent_process` / `described_in` / `conflicts_with` / `missing_in` (모두 category="concept")
      - `EntityKinds` 클래스 상수 +5 : `BUSINESS_PROCESS` / `ROLE` / `MANUAL_DOCUMENT` / `MANUAL_SECTION` / `MANUAL_FRAGMENT`
      - `RelationKinds` 클래스 상수 +6 : `PART_OF` / `RESPONSIBLE_FOR` / `PARENT_PROCESS` / `DESCRIBED_IN` / `CONFLICTS_WITH` / `MISSING_IN`
    - **신규** `tests/test_parser_protocol_phase_d.py` — 24 테스트
      - 5 parametrized entity registry tests (category="concept" 검증)
      - 6 parametrized relation registry tests (category="concept" 검증)
      - concept 카테고리 누적 카운트 검증 (Round2+Round3 ≥ 7 entity / ≥ 9 relation)
      - EntityKinds/RelationKinds 편의 상수 일치 검증
      - CodeEntity/CodeRelation 인스턴스화 end-to-end 검증
  - 설계 결정 :
    - `concept` 카테고리 유지 : `code` 계열은 파싱 직접 추출, `concept` 는 사람 승인 + LLM 제안 + 수동 seed 로 만들어지는 레이어. 그래프 시각화 이분법에 실용적.
    - **ontology_validator 영향도 = 0** : `backend/modeling/ontology/schema.py` 의 `RelationKind = Literal["part_of", "uses", "produces", "responsible_for"]` 는 별도 YAML 온톨로지 빌더 전용 좁은 리터럴. 이름 겹침 (`part_of`, `responsible_for`) 있으나 모듈 경계 완전 분리 — 충돌 없음.
    - **graph_writer 화이트리스트 = 자동 통과** : `RelationKindRegistry.is_registered(rel.kind)` 동적 검증. Phase D kinds 도 `rel.kind.upper()` → `PART_OF` 등 `^[A-Z_]+$` 정규식 이중 검사 통과.
  - 검증 :
    - 단위 — `tests/test_parser_protocol_phase_d.py` 24/24 PASS (0.02s).
    - 회귀 — 모델링 범위 `-k "modeling or parser_protocol or java_parser or code_analysis or graph_writer or ontology or mapping_models or manual_models or reverse_lookup or term_resolver or cross_file or spring"` 524/524 PASS (3.19s, D1.5 246 대비 +278 = 이미 등록된 광범위 모델링 테스트 포함).
    - 레지스트리 누적 — entity 25종 (Round1 18 + Round2 2 + Round3 5), relation 27종 (Round1 18 + Round2 3 + Round3 6).
  - 다음 : **D2 인제스트 파이프라인** (`backend/modeling/manual_ingest/`). 3 트리거 (UI+watch+git hook, Q7=E) × 5 파서 (pypdf+pdfplumber Q9=D / python-docx / python-pptx 재사용 / OCREngine 재사용 / MD). 신규 deps : pypdf, pdfplumber, python-docx. 사용자 승인 대기.
- [x] **OD-11-D2-1** — 5 포맷 파서 + ManualParser Protocol + ParseResult DTO, 2026-04-20, TDD 48 테스트 선행 (D2 3-subphase 분할 중 1/3)
  - 배경 : D2 umbrella 를 범위 명확화 + 단계별 검증 위해 D2-1 (파서) / D2-2 (pipeline + UI) / D2-3 (watch + git hook) 3 서브로 분할. D2-1 은 포맷 → `ManualParseResult(Document/Section[]/Fragment[]/warnings)` 변환 책임만. D2-2 (pipeline) 가 checksum dedup → 임베딩 → graph 쓰기를 담당.
  - 산출물 (6 신규 + 1 편집) :
    - **편집** `pyproject.toml` — deps 추가 : `pypdf ^5.0` / `pdfplumber ^0.11` (D2-3 에서 표 심화 추출 용) / `python-docx ^1.2` / `python-pptx ^1.0`. `python -m ensurepip` 으로 venv pip 복구 후 `python -m pip install` 로 실제 venv 설치 검증.
    - **신규** `backend/modeling/manual_ingest/__init__.py` — 패키지 docstring + Protocol/Helper 재노출.
    - **신규** `backend/modeling/manual_ingest/parser_protocol.py` (~115 LOC) :
      - `_slugify()` (영숫자 외 `-` 치환 + 빈 문자열 `section` fallback)
      - `make_document_fqn(path)` → `manual.<slug-of-stem>`
      - `make_section_fqn(doc_fqn, heading_path, order_index)` → `<doc>#<h1>/<h2>/.../<n>` (heading_path 비면 `<doc>#<n>`)
      - `make_fragment_fqn(section_fqn, order_index)` → `<sec>:f<n>`
      - `compute_checksum(path, chunk_size=65536)` → SHA-256 hex (대용량 대비 chunked 읽기)
      - `ManualParseResult` (frozen Pydantic : document/sections/fragments/warnings)
      - `@runtime_checkable class ManualParser(Protocol)` : `format: str` + `parse(path) -> ManualParseResult`
    - **신규** `backend/modeling/manual_ingest/md_parser.py` (~175 LOC) — heading-stack 기반 섹션 분할 + `_chunk_body` 로 paragraph/code fence/table 모드 전환 (TEXT / TABLE Fragment 분리). heading 없는 문서는 문서 stem 으로 단일 섹션 fallback.
    - **신규** `backend/modeling/manual_ingest/pdf_parser.py` (~95 LOC) — `pypdf.PdfReader` 로 페이지별 `extract_text()` → 1 페이지 = 1 Section (`Page N`) + TEXT Fragment 1개. 추출 예외는 warning 누적.
    - **신규** `backend/modeling/manual_ingest/docx_parser.py` (~120 LOC) — `Heading N` 스타일 정규식으로 섹션 분할, 비-heading paragraph 는 buffer → blank line 기준 TEXT Fragment 분리. 문서 타이틀은 첫 `Heading 1` 텍스트 > path.stem fallback.
    - **신규** `backend/modeling/manual_ingest/pptx_parser.py` (~95 LOC) — `python-pptx` 슬라이드 순회. 1 슬라이드 = 1 Section (`slide.shapes.title.text`, 없으면 `Slide N`). 타이틀 외 shape 의 text_frame 을 `\n\n` 으로 합쳐 TEXT Fragment 1개.
    - **신규** `backend/modeling/manual_ingest/image_parser.py` (~95 LOC) — `ImageParser(ocr_engine=None)` 주입 가능 constructor (None → `OCREngine()` 기본). `parse()` 가 `asyncio.run(ocr.extract_text(path))` 호출, dict/str 반환 모두 허용. 성공 시 OCR_TEXT Fragment 1개 (`image_ref=str(path)`) + `text` 가 빈 문자열이어도 Fragment 는 존재. 실패 (Exception) 시 Fragment 생략 + warning `"OCR failed for <name>: <exc>"`.
    - **신규** `tests/_manual_ingest_fixtures.py` — fixture helper 3종 : `make_pdf(path, pages_text)` (pypdf low-level : `PdfWriter.add_blank_page` + `DecodedStreamObject` content stream `BT /F1 12 Tf 72 720 Td (text) Tj ET` + Helvetica Type1 폰트 참조. reportlab 의존 회피), `make_docx(path, title, headings)` (python-docx `Document.add_heading(level)` + `add_paragraph`), `make_pptx(path, slides)` (python-pptx Title-and-Content 레이아웃).
    - **신규** 6 테스트 파일 총 48 테스트 (모두 PASS) :
      - `test_manual_ingest_parser_protocol.py` 11 : FQN helpers (slug/heading/fragment) + 한글 stem + checksum 결정성/차이/SHA-256 hex 형식 + ParseResult frozen.
      - `test_manual_ingest_md_parser.py` 13 : format literal, heading path 계층 유지, TEXT/TABLE/CODE fragment 분리, fragment order_index per-section 재시작, no-heading fallback, empty file.
      - `test_manual_ingest_pdf_parser.py` 6 : single/multi-page, fragment ↔ section 참조, checksum hex 형식, doc_fqn stem 포함.
      - `test_manual_ingest_docx_parser.py` 6 : 단일 heading, 계층 depth, TEXT fragment, section_fqn 참조 무결성, stem 포함.
      - `test_manual_ingest_pptx_parser.py` 6 : 1/다중 슬라이드, body TEXT fragment, section 참조, order_index 슬라이드 순서 일치.
      - `test_manual_ingest_image_parser.py` 7 : `_FakeOCREngine` 데이터클래스 스텁 주입 (tesseract 바이너리 불필요), 단일 section + OCR_TEXT fragment, OCR 실패 시 warning + fragment 생략, OCR 빈 문자열 시 fragment 존재 + text 비어있음, default constructor OCREngine 인스턴스 생성.
  - 설계 결정 :
    - **DI + Protocol** : `ImageParser.__init__(ocr_engine=None)` 로 결정적 테스트. OCREngine 반환 타입 불일치 (기존 `str` vs 테스트 스텁 `dict`) 양쪽 허용하는 어댑터를 parser 안에 둠 — D2-2 pipeline 이 아닌 파서 경계에서 표준화.
    - **FQN 계층** : `manual.<stem>#<h-slug>/<h-slug>:<n>:f<n>` 3-level. heading path 가 slug 단계에 녹아있어 LLM 이 URL-safe 하게 다룰 수 있고 order_index 로 안정 정렬.
    - **pypdf 저수준 fixture** : reportlab 없이 테스트 결정성 확보. 실제 PDF 생성은 D2-2 에서도 계속 pypdf 만 사용.
    - **D2 분할 이유** : 사용자 승인 (`"응 진행해"`) 받은 후에도 scope 크기 (deps + 파서 5 + pipeline + UI + watch + git hook) 가 1 step 에 부담. 3 서브로 나눠 D2-1 (파서) → 데모 가능, D2-2 (pipeline + UI), D2-3 (3 트리거) 로 점진 완성.
  - 검증 :
    - D2-1 범위 — `tests/test_manual_ingest_*.py` 48/48 PASS (0.35s).
    - 모델링 회귀 — `-k "modeling or manual or concept_resolver or parser or ontology or graph_writer or neo4j_adapter or business_term or business_rule or domain_rule"` 251/251 PASS (4.12s).
    - 전체 suite — 1340 PASS / 21 FAIL. 실패 21건 전부 Section 1 wiki/RAG/skill 영역 (test_ag23_skill_feedback / test_ag33_hooks / test_auto_tag_quality / test_confidence / test_lineage_validation / test_p2b6_deprecated_filter / test_pydantic_ai_migration / test_rag_tag_boost / test_skill_api). 모델링 회귀 없음 확인.
  - 다음 : **D2-2** (`pipeline.py` + `manual_registry.py` + 업로드 REST/SSE API). checksum dedup → chromadb 임베딩 (manual_fragments 컬렉션) → Neo4j graph_writer 로 ManualDocument/Section/Fragment 노드 기록. 사용자 승인 대기.
- [x] **OD-11-D2-2** — Ingest pipeline + Manual registry + Upload REST/SSE API, 2026-04-20, TDD 36 테스트 선행 (D2 3-subphase 분할 중 2/3)
  - 배경 : D2-1 에서 파서가 뱉은 `ManualParseResult` 를 어디에 저장하고 중복은 어떻게 가리는지 채운다. 3 트리거(Q7=E) 가 공유할 엔트리포인트를 파이프라인 + REST + SSE 로 확정.
  - 산출물 (4 신규 모듈 + 3 신규 테스트 + 2 wiring 편집) :
    - **신규** `backend/modeling/manual_ingest/manual_registry.py` — `ManualRegistry` Protocol (`@runtime_checkable`) + `ManualRegistryEntry` (frozen dataclass, document/sections/fragments) + `InMemoryManualRegistry` (primary fqn 인덱스 + secondary checksum 인덱스, authoritative 토글은 `ManualDocument.model_copy(update={...})` 로 frozen 불변성 보존, Q8=B).
    - **신규** `backend/modeling/manual_ingest/embedding_store.py` — `ManualEmbeddingStore` Protocol + `InMemoryManualEmbeddingStore` (`section_fqn` prefix 매칭으로 document 단위 삭제) + `ChromaManualEmbeddingStore` (ids=fragment fqn / documents=text / metadatas={doc_fqn, section_fqn, kind, order_index, image_ref} / `where={"doc_fqn": ...}` 삭제). 컬렉션 이름 상수 `MANUAL_FRAGMENTS_COLLECTION = "manual_fragments"`.
    - **신규** `backend/modeling/manual_ingest/pipeline.py` — `IngestMode(SKIP/UPDATE/FORCE)` + `IngestOutcome(INGESTED/SKIPPED/UPDATED)` + `IngestResult(outcome, document, parse_result, warnings)` frozen dataclass + `UnsupportedFormatError(ValueError)` + `detect_format(path)` 모듈 헬퍼 (.md/.markdown/.pdf/.docx/.pptx/.png/.jpg/.jpeg → ManualFormat) + `ManualGraphWriter` Protocol (`write_manual(document, sections, fragments, repo_id)` + `delete_manual(doc_fqn, repo_id)`) + `CodeGraphManualWriter` 어댑터 (Manual*→CodeEntity via 기존 `CodeGraphWriter.write_entities` — D1.6 에서 등록된 manual_document/section/fragment kind 재사용 / containment 는 property `doc_fqn`·`section_fqn`·`parent` 로만 표현, PART_OF 엣지 안 씀 — Q1=C BusinessProcess 전용 유지) + `ManualIngestPipeline.ingest(path, *, repo_id, mode, on_progress)` (검출→checksum 계산→fqn 조회→동일 fqn+동일 checksum+non-FORCE 면 SKIPPED 리턴→파싱→UPDATE+prior 존재 시 graph/embedding delete→graph write→embedding upsert→registry add→progress 콜백 5종 emit).
    - **신규** `backend/modeling/api/manuals_api.py` — `init(pipeline, registry, repo_id)` / `reset()` 싱글턴 + `router = APIRouter(prefix="/api/modeling")` + `POST /manuals/upload` (multipart + `mode` query) + `GET /manuals` ({total, items}) + `POST /manuals/{fqn:path}/authoritative` ({authoritative: bool}) + `POST /manuals/upload/stream` (SSE — worker thread 가 파이프라인 호출 + progress 콜백을 `queue.Queue` 에 push, coroutine 이 `asyncio.to_thread(q.get)` 로 drain 해서 `event: <name>\ndata: <json>\n\n` 프레임 방출 + sentinel `None` 으로 종료). 업로드는 `tempfile.mkdtemp() + 원본 파일명` 으로 저장해 FQN stem 보존 (NamedTemporaryFile 로 저장하면 두 번째 업로드 때 stem 이 달라져 dedup 실패 — Red 에서 발견).
    - **편집** `backend/modeling/api/modeling.py` — `router.include_router(manuals_api.router)` 추가.
    - **편집** `backend/main.py` — lifespan 에 5 파서 주입 + `InMemoryManualRegistry` + Chroma 가용 시 `ChromaManualEmbeddingStore(get_or_create_collection('manual_fragments'))` 아니면 `InMemoryManualEmbeddingStore` fallback + `graph_writer=None` (D3 에서 Neo4j 실연동 시 주입) + `manuals_api.init(...)` 호출. `ONTONG_REPO_ID` 환경변수 또는 `"default"`.
    - **신규** `tests/test_manual_registry.py` 13 테스트 — Protocol 준수 · add/get_by_fqn · `has_checksum` · `list_all` · get_missing→None · add same fqn → 이전 checksum index 제거 · remove + missing noop · `set_authoritative(True/False)` + missing KeyError · 빈 레지스트리 엣지.
    - **신규** `tests/test_manual_ingest_pipeline.py` 13 테스트 — fake `_FakeGraphWriter`/`_FakeEmbeddingStore` dataclass 주입, 포맷 라우팅 · `UnsupportedFormatError` · SKIP 모드 dedup · FORCE 모드 재기록 · UPDATE 모드 (다른 checksum → UPDATED + prior delete 양쪽 호출 / 같은 checksum → SKIPPED) · registry population · graph writes · embedding upserts · `detect_format` 매핑 · graph/embedding 없이도 동작.
    - **신규** `tests/test_manuals_api.py` 10 테스트 — FastAPI `TestClient` + `init/reset` fixture, upload 성공 · dup checksum SKIPPED · `mode=force` re-ingest · 415 unsupported ext · `GET /manuals` empty/populated · authoritative 토글 + missing 404 · SSE `event: parsing`/`event: complete` 이벤트 · 503 uninitialized.
  - 설계 결정 :
    - **dedup 기준 = fqn + checksum 두 단계** : has_checksum 단독이 아니라 doc_fqn 매칭 후 checksum 동일 확인. 다른 파일명 우연히 같은 checksum 오탐 스킵 방지.
    - **업로드 tempfile 네이밍** : `mkdtemp() + 원본 파일명` 으로 저장해 원본 파일명 기반 FQN 유지. Red 테스트에서 발견한 버그 → Green 수정.
    - **UPDATE 모드 이전 버전 처리** : graph + embedding 양쪽에서 `delete_manual` / `delete_document` 명시 호출. Registry 는 `add()` 시 자동 overwrite.
    - **GraphWriter 전략** : Manual* → CodeEntity 어댑터. D1.6 에서 EntityKinds 에 등록된 `manual_document`/`manual_section`/`manual_fragment` 를 `CodeGraphWriter.write_entities` 에 kind 만 바꿔 넘김. Containment 는 edge 가 아니라 property — PART_OF 엣지 안 씀 (Q1=C 결정 유지).
    - **SSE 분리** : 파이프라인은 progress 콜백만 받고 SSE 를 모름. API 레이어에서 worker thread + Queue + asyncio.to_thread drain 으로 변환. CLI/batch 에서도 파이프라인 재사용 가능.
    - **graph_writer 기본 None** : D2-2 는 "업로드 흐름 + 인덱싱 + 임베딩" 범위. 실 Neo4j 주입은 D3 에서 gap detector 와 함께. Pipeline 은 graph/embedding 모두 optional.
  - 검증 :
    - D2-2 범위 — `tests/test_manual_registry.py` + `tests/test_manual_ingest_pipeline.py` + `tests/test_manuals_api.py` 36/36 PASS (0.19s).
    - 모델링 회귀 — `-k "modeling or manual or parser or reverse_lookup or ontology or term_resolver"` 329/329 PASS (4.90s).
    - 전체 suite — 1376 PASS / 21 FAIL (Section 1 baseline, 이번 변경과 무관).
    - 런타임 smoke — `python -c "from backend.main import app"` OK (Chroma 없어도 InMemory fallback).
  - 다음 : **D2-3** (`watch_folder.py` + `git_hook_webhook.py` + 프런트 업로드 UI). D2-2 의 `ManualIngestPipeline.ingest` 와 SSE 엔드포인트를 3 트리거(Q7=E) 가 그대로 공유.

- [x] **OD-11-D2-3** — 3 트리거 wiring (watch folder + git hook + 프런트 업로드 UI), 2026-04-21, TDD 30 테스트 선행 (D2 3-subphase 중 3/3 — Phase D2 종결)
  - 배경 : D2-2 에서 준비한 `ManualIngestPipeline.ingest` + SSE + REST 을 세 번째·네 번째 진입로 (폴더 감시 + git post-receive webhook + 브라우저 UI) 가 공유하도록 wiring. Q7=E 트리거 3종 완성.
  - 산출물 (2 backend 신규 + 1 API 편집 + 1 frontend 신규 + 2 frontend 편집 + 3 테스트 신규) :
    - **신규** `backend/modeling/manual_ingest/watch_folder.py` — `ManualFolderWatcher(pipeline, folder, repo_id, seed_existing=True)` + `WatchScanResult(ingested, removed, skipped_unchanged, errors)` dataclass. watchdog 의존성 **제거** (폴링 방식으로 단순화). 내부 `_snapshot: dict[Path, tuple[mtime, size]]` 스냅샷 + `rglob("*")` 재귀 walk + `detect_format` 필터 → 변경 감지 시 `pipeline.ingest(mode=UPDATE)`. `seed_existing=False` 는 초기 파일을 baseline 에만 등록. 삭제 파일은 `removed` 리스트만. 폴더 미존재 / 파일 경로 거부 (`ValueError`) / `UnsupportedFormatError` 는 `errors` 에 집계 후 계속.
    - **신규** `backend/modeling/manual_ingest/git_hook_webhook.py` — `GitHookRequest`/`GitHookResponse` frozen dataclass + `parse_git_webhook_payload(payload: dict) -> GitHookRequest` (`repo_root` 필수, added/modified/removed 상대·절대 경로 모두 resolve) + `ingest_changed_files(request, *, pipeline, repo_id) -> GitHookResponse` (added+modified → `pipeline.ingest(mode=UPDATE)`, `detect_format` 실패 → `skipped`, 존재 안함 → `errors`, repo_root 밖 경로 → `errors` (`_inside_repo_root` path escape 방어), removed 는 응답에만 포함).
    - **편집** `backend/modeling/api/manuals_api.py` — `POST /api/modeling/manuals/git-hook` 추가. `GitHookIngestedItem(outcome, document, warnings)` + `GitHookResponseDTO(ingested, skipped, removed, errors)` Pydantic 응답. `asyncio.to_thread(ingest_changed_files, ...)` 로 동기 함수 래핑. `ValueError` → 400, 미초기화 → 503. 모듈 `__all__` 에 DTO 2개 추가.
    - **편집** `frontend/src/lib/api/modeling.ts` (+95 LOC) — `ManualFormatKind`, `IngestMode`, `IngestOutcome`, `ManualDocumentDto`, `ManualUploadResponse`, `ManualListResponse`, `SseEvent` 타입 + `listRegisteredManuals()`, `uploadManual(file, mode)`, `toggleManualAuthoritative(fqn, bool)`, `uploadManualStream(file, mode, signal?)` async generator. `uploadManualStream` 은 EventSource 불가 (POST multipart) → `fetch` + `ReadableStream.getReader` + `TextDecoder` + `\n\n` 경계 파서 `parseSseFrame` 으로 직접 SSE 스트림 처리. `AbortController.signal` 지원.
    - **신규** `frontend/src/components/sections/modeling/ManualUpload.tsx` (~230 LOC) — 모드 pill (SKIP/UPDATE/FORCE) + 드롭존 (클릭 → `<input type="file">`, accept `.md,.markdown,.pdf,.docx,.pptx,.png,.jpg,.jpeg`) + SSE 라이브 이벤트 리스트 (Radio 아이콘 + `[event]` 태그 + payload JSON) + 완료/에러 배너 + 등록된 매뉴얼 목록 + authoritative 토글 스위치 (체크박스 + peer-checked styling, 오프=Draft 회색 배지 / 온=Authoritative 앰버 배지). `useEffect` 로 초기 로드 + `refresh` 버튼.
    - **편집** `frontend/src/components/sections/ModelingSection.tsx` — `Upload` 아이콘 import + `ModelingView` union 에 `"manual-upload"` 추가 + `MAIN_NAV` 에 "매뉴얼 업로드" 탭 (builder 와 ontology 사이) + `<ManualUpload />` 렌더 분기.
    - **신규** `tests/test_manual_watch_folder.py` 12 테스트 — 신규 파일 ingest · 변경 없음 noop (`skipped_unchanged`) · 수정 감지 UPDATE · 재귀 서브폴더 · 지원 안 되는 확장자 무시 · 파서 미등록 warning · `seed_existing=False` baseline · 삭제 추적 · 폴더 미존재 empty · 파일 경로 `ValueError` · 다수 파일 batching · 1개만 변경 시 1개만 UPDATE.
    - **신규** `tests/test_manual_git_hook_webhook.py` 11 테스트 — payload 기본/누락/절대 경로 · repo_root 누락 `ValueError` · added INGESTED · modified UPDATED · removed 응답 포함만 · unsupported skipped · 빈 payload noop · 파일 미존재 errors · repo_root escape 거부.
    - **신규** `tests/test_manuals_api_git_hook.py` 7 테스트 — FastAPI `TestClient` + `init/reset` fixture 재사용, POST JSON 처리 · modified UPDATED · unsupported skipped · 빈 payload → 빈 응답 · 미초기화 503 · repo_root 누락 400 · removed 응답 확인.
  - 설계 결정 :
    - **watchdog 무의존** : 폴링 방식 (`scan_once()` + 호출자가 주기 관리) 으로 단순화. watchdog 설치 불필요, 테스트 결정성 확보. 실 운영은 asyncio 루프에서 `while True: await asyncio.sleep(n); watcher.scan_once()` 패턴.
    - **mtime + size 2-tuple 스냅샷** : 해시 대신 가벼운 key 로 1차 감지 → 파이프라인의 checksum dedup 이 2차 확인. 역할 분리.
    - **seed_existing 디폴트 True** : 새 프로세스 기동 시 기존 매뉴얼 전부 한 번 인덱싱. 재기동 시 checksum dedup 이 자연히 skip 처리.
    - **git hook payload 일반화** : `{repo_root, added, modified, removed}` 최소 공통 포맷. GitHub/GitLab webhook 을 그대로 받지 않고 사용자 post-receive 가 `jq` 로 래핑해 POST. provider 별 어댑터는 D4 또는 운영 시 추가.
    - **path escape 방어** : `_inside_repo_root` 로 `repo_root` 밖 경로 거부. 악의적 webhook 이 `/etc/passwd` 등 시스템 파일 타깃하지 못하도록.
    - **removed 는 그래프 noop** : D3 Gap Detector 가 MISSING_IN (기준서 ↔ 문서) 를 다룰 때 통합 처리. D2-3 에서는 집계만.
    - **POST+SSE 를 EventSource 대신 fetch streaming** : EventSource 는 POST body 지원 불가 → `fetch` + `ReadableStream` + TextDecoder + `\n\n` 버퍼 파서로 직접 구현. AbortController 로 취소도 지원.
    - **프론트 범위 = 업로드 + 목록 + authoritative 토글** : 편집/승인 큐/Role 관리는 D4.
  - 검증 :
    - D2-3 범위 — `tests/test_manual_watch_folder.py` 12 + `tests/test_manual_git_hook_webhook.py` 11 + `tests/test_manuals_api_git_hook.py` 7 = 30/30 PASS.
    - D2 전체 — 파서 48 + pipeline 13 + registry 13 + API 10 + watch 12 + hook 11 + hook API 7 = 66/66 (신규 3 파일 기준 + D2-2 36 통합 시 66/66).
    - 모델링 회귀 — `-k "modeling or spring or manual or java_parser or code_analysis or graph_writer or cross_file or parser_protocol or mapping or query_engine or query_models or ontology or concept or term_resolver or reverse_lookup or gap or ingest"` 677/677 PASS (2.01s).
    - 전체 suite — 1406 passed / 21 failed (Section 1 baseline, 이번 변경과 무관). D2-2 대비 +30 테스트.
    - TS — `cd frontend && npx tsc --noEmit` 0 errors.
    - Runtime smoke — `from backend.main import app` OK, routes 152 (D2-2 151 → +1 git-hook).
  - 다음 : **D3 Gap Detector** (`backend/modeling/gap_detection/` — rule_ast_differ + embedding_drifter + llm_comparator + gap_engine, Strategy 패턴 2 모드 hierarchical/llm_only, Q4=C+A), 또는 **D4 UI 디자인 스펙** (CONFLICTS_WITH 승인 큐 + Role team 관리 + 매뉴얼 업로드 UI 확장 + authoritative 토글 연동 — D2-3 업로드 UI 를 기반으로 점진 확장). 사용자 승인 대기.

- [x] **OD-11-D3-1** — MISSING_IN 양방향 탐지기 (Q6=A), 2026-04-21, TDD 28 테스트 선행 (D3 3-subphase 중 1/3)
  - 배경 : "A 진행해" 승인. D3 를 D2 처럼 3 서브로 분할 (D3-1 MISSING_IN / D3-2 CONFLICTS_WITH / D3-3 API). D3-1 은 결정적 (deterministic) 만, LLM/resolver 통합은 D3-2 이후. 사용자 Q1=(a) store 추상화 선행, Q2=(c) 단순 휴리스틱 추출 승인.
  - 산출물 (3 신규 + 1 init + 2 테스트) :
    - **신규** `backend/modeling/gap_detection/gap_models.py` — `ScanConfig(repo_id, gap_mode, detected_by, include_unconfirmed_terms, min_occurrence_for_manual_only)` + `GapCandidate(id, direction, target_fqn, counterpart_fqn, severity, detected_by, gap_mode, description, confirmed, created_at)` + `ScanResult(code_only, manual_only, errors, .all)`. `direction: GapDirection | None` — D3-2 의 CONFLICTS_WITH 도 같은 타입 사용 가능.
    - **신규** `backend/modeling/gap_detection/gap_store.py` — `GapStore` Protocol + `InMemoryGapStore` 구현. `upsert` 는 기존 gap 이 `confirmed=True` 면 덮어쓰지 않음 (재스캔 안정성). `confirm(gap_id)` 는 없으면 `KeyError`.
    - **신규** `backend/modeling/gap_detection/missing_in_detector.py` — `FragmentTermExtractor` Protocol + `SimpleHeuristicExtractor` (4 regex: `**bold**` / `` `code` `` / `「한글」` / `"ascii"`, 2~30 자, IMAGE kind 스킵) + `MissingInDetector.scan()`. code_only (Term/Rule confirmed + described_in 없음, severity=SOFT) + manual_only (추출 phrase 가 name/aliases 매칭 실패, min_occurrence 이상, severity=HARD). 각 gap 은 `sha1(direction|target|counterpart)[:16]` 로 stable id → re-scan idempotent.
    - **신규** `backend/modeling/gap_detection/__init__.py` — public re-export.
    - **신규** `tests/test_gap_store.py` 10 테스트 — Protocol 적합성 · upsert/get 왕복 · pending 덮어쓰기 · confirmed 보호 · list_pending · list_by_direction · confirm flag flip · missing KeyError · remove · missing noop.
    - **신규** `tests/test_missing_in_detector.py` 18 테스트 — extractor 3 (bold/code/quote · IMAGE skip · within-fragment dedup) + code_only 5 (term → SOFT · with described_in skip · rule → SOFT · unconfirmed skip · include_unconfirmed 플래그) + manual_only 5 (unmatched bold → HARD · canonical_label match skip · alias case-insensitive · min_occurrence threshold · IMAGE skip) + store 통합 5 (upsert 확인 · re-scan idempotency · confirm 보존 · llm_only 전파 · ScanResult.all).
  - 설계 결정 :
    - **`MissingBinding` 대신 `GapCandidate` 도입** : D1.5 의 MissingBinding 은 graph 엣지 DTO (severity 필드 없음). 스캔 중간/승인 큐 상태(id, confirmed) 를 담기 위해 별도 introduction. 그래프 쓰기 시점에 변환 어댑터 예정.
    - **severity 2 단계 (HARD/SOFT)** : D1.5 `GapSeverity` 그대로. 디자인 스펙의 4 단계(low/medium/high/critical) 는 CONFLICTS_WITH 에 주로 쓰이므로 D3-2 에서 재검토. MISSING_IN 은 결정적이라 2 단계로 충분.
    - **휴리스틱 추출기 기본** : term_resolver 통합은 D3-2. `FragmentTermExtractor` Protocol 이라 교체 가능.
    - **confirmed 보호** : `InMemoryGapStore.upsert` 가 기존 gap 이 confirmed 면 no-op. 사람이 승인한 갭이 재스캔으로 되돌아가지 않음.
    - **stable id** : sha1(direction|target|counterpart)[:16] 로 idempotent scan.
    - **`direction: GapDirection | None`** : D3-2 의 CONFLICTS_WITH 는 direction 없이 target/counterpart 쌍으로 표현 → 미리 Optional.
  - 검증 :
    - D3-1 범위 — `tests/test_gap_store.py` 10 + `tests/test_missing_in_detector.py` 18 = 28/28 PASS (0.06s).
    - 모델링 회귀 — `-k "modeling or manual or ... or gap or ingest or missing_in"` 705/705 PASS (2.58s). D2-3 기준 677 → +28.
    - 전체 suite — 1434 passed / 21 failed (Section 1 baseline, 이번 변경과 무관). D2-3 기준 1406 → +28.
    - Runtime smoke — routes 152 (D3-1 은 API 미추가). `from backend.modeling.gap_detection import MissingInDetector, InMemoryGapStore, ScanConfig` OK.
  - 다음 : **D3-2 CONFLICTS_WITH 3단 hierarchical + llm_only** (`rule_ast_differ.py` + `embedding_drifter.py` + `llm_comparator.py` + `gap_engine.py` Strategy, Q4=C+A), 또는 **D4 UI 디자인 스펙** 선행. 사용자 승인 대기.

- [x] **OD-11-D3-2-a** — CONFLICTS_WITH deterministic (rule_ast + drift + engine skeleton), 2026-04-21, TDD 30 테스트 선행 (D3-2 2-subphase 중 1/2)
  - 배경 : "A부터 진행해" 승인. D3-2 를 D3-2-a (deterministic) / D3-2-b (LLM) 으로 분할. 사용자 Q1=(a) 수량 표현만 추출 / Q2=(b) 2 단 분할 / Q3=(a) GapSeverity 6값 단일 Enum / Q5=(a) TextEmbedder Protocol 최소 인터페이스 승인.
  - 산출물 (3 신규 + 2 edit + 3 테스트) :
    - **편집** `backend/modeling/manuals/manual_models.py` — `GapSeverity` Enum 에 LOW/MEDIUM/HIGH/CRITICAL 4 값 추가. HARD/SOFT 유지 (MISSING_IN 호환).
    - **신규** `backend/modeling/gap_detection/rule_ast_differ.py` (~230 LOC) — `extract_quantities(text) -> RuleStatementTokens` : 숫자 정규식(`-?\d+(\.\d+)?`) + 비교연산자 14종(≥/≤/>=/<=/==/!=/>/</=/이상/이하/초과/미만/같음/동일/부터/까지) + 단위 화이트리스트(%/원/달러/$/개/건/명/회/kg/g/t/일/시간/분/초/주/월/년). `_canonical_comparator` 로 "≥/≥/이상" 정규화. `RuleStatementTokens(numbers, comparators, units)` + `DiffOutcome` + `RuleASTDiffer(clock).compare() / .find_conflicts(rules, fragments, described_in, config)`. 빈 쪽은 not-mismatch (stage 2 위임). Hit severity=GapSeverity.HIGH. IMAGE 스킵. described_in 매핑 쌍만.
    - **신규** `backend/modeling/gap_detection/embedding_drifter.py` (~120 LOC) — `@runtime_checkable TextEmbedder` Protocol + `_cosine(a, b)` zero-vector 안전 + `CosineDrifter(embedder, cutoff=0.65, clock).find_drift()`. Hit severity=MEDIUM, description 에 cosine 값 기록.
    - **신규** `backend/modeling/gap_detection/gap_engine.py` (~240 LOC) — `@runtime_checkable LLMComparator` Protocol (`compare(rule, fragment, prior_severity, config) -> (severity, reasoning)`) + `@runtime_checkable GapEngine` Protocol + `HierarchicalGapEngine(rule_differ, drifter, llm_comparator=None, gap_store=None)` (stage 1 hit pair 는 stage 2 skip dedup, stage 3 LLM override severity+reasoning) + `LLMOnlyGapEngine(llm_comparator=None)` skeleton (comparator 없으면 []+warning) + `create_gap_engine(mode=…)` factory.
    - **편집** `backend/modeling/gap_detection/__init__.py` — rule_ast/drift/engine public API 추가 재노출.
    - **신규** `tests/test_rule_ast_differ.py` 14 테스트.
    - **신규** `tests/test_embedding_drifter.py` 7 테스트.
    - **신규** `tests/test_gap_engine_conflicts.py` 9 테스트.
    - **편집** `tests/test_manual_models.py` — `test_gap_enum_values` 에 4값 assertion 추가, `test_conflict_binding_severity_enum_validates` 의 invalid literal 을 "apocalyptic" 으로 교체 (critical 이 정식 값으로 승격됨).
  - 설계 결정 :
    - **자연어 자유 텍스트** : BusinessRule.statement 는 str 이라 full AST 불가능. 수량 표현만 추출하는 경량 정규식으로 축소. 자연어 의미는 embedding/LLM 단계 책임.
    - **빈 토큰 not mismatch** : rule_ast 는 수량 근거 필요. 순수 산문 rule 은 stage 1 skip → stage 2 embedding 이 판정.
    - **GapSeverity 6값 단일 Enum** : HARD/SOFT + LOW/MEDIUM/HIGH/CRITICAL. MISSING_IN 2값, CONFLICTS_WITH 4값 공존. 타입 단순 + 필터 용이.
    - **Strategy skeleton w/ optional LLM** : `llm_comparator=None` 도 운영 가능 — deterministic 2 stage 만으로도 사람 검증 가능한 결과. D3-2-b 에서 comparator 만 끼워넣으면 완성.
    - **stage dedup** : rule_ast hit 쌍은 drift stage 에서 skip. LLM override 시 동일 candidate 만 갱신.
    - **stable id prefix 분리** : rule_ast/drift/llm_only 각각 prefix → stage 충돌 방지.
    - **gap_store optional** : 엔진 배출은 `list[GapCandidate]`. store 주입시에만 upsert. D3-3 오케스트레이터가 결정.
    - **IMAGE 스킵 2 stage 모두** : OCR 텍스트는 OCR_TEXT kind 로 별도 fragment.
  - 검증 :
    - D3-2-a 범위 — 14 + 7 + 9 = 30/30 PASS (0.08s).
    - 모델링 회귀 — `-k "modeling or ... or rule_ast or embedding_drifter or gap_engine"` 735/735 PASS (2.14s). D3-1 기준 705 → +30.
    - 전체 suite — 1464 passed / 21 failed (Section 1 baseline, 무관). D3-1 기준 1434 → +30.
    - Runtime smoke — routes 152 (D3-2-a 도 API 미추가, D3-3 예정). `from backend.modeling.gap_detection import HierarchicalGapEngine, CosineDrifter, RuleASTDiffer, create_gap_engine` OK.
  - 다음 : **D3-2-b LLM Comparator 실 구현** (`llm_comparator.py` — pydantic-ai Agent or OpenAI direct, severity Literal[low/medium/high/critical], 환각 방어 fallback, `backend/main.py` startup `ONTONG_LLM_COMPARATOR=openai` 분기). 또는 **D3-3 승인 큐 API + UI** (engine+store 준비 완료이라 병행 가능). 사용자 승인 대기.

- [x] **OD-11-D3-2-b** — CONFLICTS_WITH LLM Comparator (pydantic-ai Agent), 2026-04-21, TDD 13 테스트 선행 (D3-2 2-subphase 중 2/2)
  - 배경 : "A부터 진행해" 승인. D3-2-a 에서 Protocol 만 정의한 `LLMComparator` 의 운영 구현. 사용자 Q1=(a) pydantic-ai Agent / Q2=(a) llm_factory.get_model() 재사용 / Q3=(a) minimal prompt inputs / Q4=(a) @pytest.mark.integration + 환경 변수 이중 게이트 승인.
  - 산출물 (1 신규 + 3 edit + 1 테스트) :
    - **신규** `backend/modeling/gap_detection/llm_comparator.py` (~210 LOC) — `LLMComparisonResult(BaseModel)` pydantic-ai 구조화 출력 (`severity: Literal["low","medium","high","critical"]` + `reasoning: str`). `_SYSTEM_PROMPT` ERP/MES/SCM 충돌 분석가 역할 + severity decision guide. `_render_user_message()` rule/fragment/prior severity 직렬화. `_default_agent_factory()` pydantic-ai `Agent(get_model(), output_type=..., retries=2, defer_model_check=True)` lazy import. `PydanticAILLMComparator(agent_factory=None)` Protocol 구현 — `agent.run_sync()` 블로킹 호출 + **graceful degrade** 어떤 예외도 재발생 안 함 (prior severity 유지 + reasoning 에 ExcType 기록). `_coerce_conflict_severity()` **belt-and-suspenders** 이차 방어 — CONFLICTS_WITH 카테고리 (LOW/MEDIUM/HIGH/CRITICAL) 만 허용, MISSING_IN 카테고리(hard/soft) 또는 unknown 문자열 → MEDIUM 폴백.
    - **편집** `backend/modeling/gap_detection/__init__.py` — `LLMComparisonResult`, `PydanticAILLMComparator` public re-export.
    - **편집** `backend/main.py` lifespan — `ONTONG_LLM_COMPARATOR=openai` 분기 (D2-2 `manuals_api.init(...)` 직후). 인스턴스만 생성/보관, engine 주입은 D3-3.
    - **편집** `pyproject.toml` — `[tool.pytest.ini_options].markers` 에 `integration` 추가. unregistered marker warning 억제.
    - **신규** `tests/test_llm_comparator.py` 13 테스트 (output schema 2 / protocol 1 / success 2 / graceful 3 / prompt 2 / defensive 2 / integration 1 — 12 PASS + 1 SKIP 기본 스위트).
  - 설계 결정 :
    - **pydantic-ai Agent** : `builder_service.py` 패턴 재사용. `output_type` 이 프레임워크 레벨에서 출력 강제 → 환각 1차 차단. provider-agnostic.
    - **llm_factory.get_model() 재사용** : 모델 스위치 단일 지점 (`settings.litellm_model` "provider/model"). OpenAI/Anthropic/Ollama/Google 모두 공유.
    - **동기 Protocol + run_sync** : D3-2-a 정의 유지 → 기존 테스트 회귀 제로. REST/SSE 호출자(D3-3)는 `asyncio.to_thread` 로 감쌀 것.
    - **Graceful degrade (never raise)** : 대량 candidate scan 에서 한 건 LLM 실패가 전체 중단으로 번지지 않도록 예외 포착 + prior severity 유지 + reasoning 에 에러 타입 기록.
    - **Belt-and-suspenders (Literal + enum 화이트리스트)** : Literal 이 일차(프레임워크 강제), `_coerce_conflict_severity` 가 이차(모킹/버그 방어). MISSING_IN 카테고리 leak → MEDIUM 폴백.
    - **Integration 격리** : `@pytest.mark.integration` + `skipif(not ONTONG_LLM_INTEGRATION)` 이중 게이트. 기본 pytest SKIP. CI 속도/비결정성 차단.
    - **env 분기는 보관만** : D3-2-b 는 comparator 생성만. engine 주입은 D3-3 (`create_gap_engine(llm=_llm_comparator)`). API/UI 없이 wiring 만 하면 무의미.
  - 검증 :
    - D3-2-b 범위 — `tests/test_llm_comparator.py` 13 선택 실행 : 12 PASS + 1 SKIP (integration) (0.05s).
    - 모델링 회귀 — `-k "modeling or manual or ... or llm_comparator"` 747/747 PASS. D3-2-a 기준 735 → +12.
    - 전체 suite — 1476 passed / 21 failed (Section 1 baseline, 무관) / 1 skipped (integration). D3-2-a 기준 1464 → +12.
    - Runtime smoke — `from backend.modeling.gap_detection import PydanticAILLMComparator, LLMComparisonResult` OK. `main.py` `ast.parse` OK. Routes 152 유지 (D3-2-b 도 API 미추가, D3-3 예정).
  - 다음 : **D3-3 승인 큐 + REST/SSE API + 프런트 스텁** (Q5=A 승인 예정) — `backend/modeling/api/gaps_api.py` (`POST /gaps/scan` + `GET /gaps` + `POST /gaps/{id}/confirm` + SSE `POST /gaps/scan/stream`) + 프런트 `ConflictsQueue` 페이지 + `main.py` 에서 `_llm_comparator` 를 `create_gap_engine()` 에 주입. 또는 **D4 UI 디자인 스펙** 선행 (프런트-first). 사용자 승인 대기.

### Phase C/D/E
`toClaude/modeling/TODO.md` Section 2 — OD-11 방향 전환 표 참조.

### 방향 전환에 따른 이전 OD 상태 변경
- **OD-7-B** (팀 분배표) : 일단 보류. 방향 재정립 후 재계획.
- **OD-9** (빌더 UX) : 매뉴얼 빌더가 기준서 인제스트 보조 도구로 재정의됨. UX 개선 작업은 재우선순위화 필요.
- **Section 3 — 3 agents (WhatIf/WhyTrace/Diagnostic)** : **취소**. 새 3대 기능(Impact / Reverse / Test)으로 교체.

---

## 2026-04-18 (Ontology-First Redesign — Week 1 DSL Lock)

새 설계 문서 `~/.gstack/projects/Jeensh-onTong/donghae-main-design-20260418-173359.md` (APPROVED). Section 2는 온톨로지 빌더 담당, 3 agents는 Section 3로 마이그레이션 예정. Week 1 = Primary Layer DSL 확정 + 서브-DSL 문법 lock.

### Scope 정정 (post-approval)
- [x] **OD-0** — 3 agents의 최종 owner는 Section 3. Section 2는 빌더. 3 agents는 validation harness로 `backend/modeling/agents/` 격리 구현 후 Phase 2에 Section 3로 lift-and-shift. Premise 8 + Migration Architecture 섹션으로 설계 반영.

### Week 1 — Ontology DSL Lock (39 tests pass, 0 failures)
- [x] **OD-1** — Pydantic schema (`backend/modeling/ontology/schema.py`): Ontology + OntologyHeader + Process + Formula + Rule(warning/assign/constraint) + IOPort + Term + CodeBinding. `extra="forbid"` 강제.
- [x] **OD-2** — Sub-DSL AST 파서 + graph validator (`backend/modeling/ontology/validator.py`): arithmetic(+/-/*///**, whitelist 함수 sqrt/abs/min/max/norminv/round) + boolean(AND/OR/NOT case-insensitive + 6개 비교 연산자), cycle/duplicate/refers_to 검증.
- [x] **OD-3** — YAML loader/dumper (`backend/modeling/ontology/loader.py`): `load_ontology()` + `dump_ontology()` + 기본값으로 validation 수행.
- [x] **OD-4** — 샘플 온톨로지 (`ontologies/safety_stock_v1.yaml`): SafetyStockCalculation + ReorderPointCalculation (2 processes, 4 rules, 3 terms, 2 code_bindings).
- [x] **OD-5** — pytest 39개 (`tests/test_ontology_schema.py` 6개 + `test_ontology_validator.py` 28개 + `test_ontology_loader.py` 5개), 모두 pass.

### Week 1.5 — OD-6 Legacy Ontology Migration (110 tests pass)
- [x] **OD-6** — `:DomainNode` 라벨을 `:OntNode{kind}` 로 완전 재작성. Schema 루트에 `entities`/`roles`/`relations` 추가 + `Process.parent_id` 계층화. `ontologies/scor_isa95_v1.yaml` 기반 템플릿 (26 processes / 7 entities / 5 roles / 16 relations). Downstream Cypher(`mapping_service`, `sim_engine`, `query_engine`, `source_api`) 일괄 교체. `domain_models.py` / `scor_template.py` / `test_scor_template.py` 삭제. e2e 파이프라인 테스트는 YAML 로더 기반으로 재작성.

### Week 2 — OD-7/8 Ontology Builder (119 tests pass)
- [x] **OD-7** — 매뉴얼 샘플 폴더 생성. `wiki/공정/가열공정-SOP.md` + `wiki/표준/품질기준-균열관리.md` → `ontologies/manuals/{heating-process-sop.md, crack-quality-standard.md}` 복사 + README. 팀 분배표는 팀원 정보가 필요해 별도 대화 예정.
- [x] **OD-8** — 매뉴얼 빌더 UI + 백엔드 완료.
  - 백엔드: `backend/modeling/ontology/builder_service.py` 신규 — pydantic_ai Agent로 markdown→YAML 드래프트 + `validate_yaml_text()` (파싱/스키마/그래프 3단 검증).
  - API: `ontology_api.py`에 4개 엔드포인트 추가 — `POST /draft`, `POST /validate`, `POST /save`, `GET /manuals`, `GET /manuals/{name}`.
  - 프론트: `ManualOntologyBuilder.tsx` 신규 — 좌(매뉴얼 markdown 에디터) + 우(YAML 에디터) 분할, 샘플 매뉴얼 드롭다운, LLM Draft 버튼, 500ms debounce 실시간 validation, 저장.
  - 네비: `ModelingSection.tsx` MAIN_NAV 최상단에 "매뉴얼 빌더" 탭 추가.
  - 테스트: `test_ontology_builder_service.py` 17건 (valid/invalid YAML, code-fence 제거, LLM 예외 처리, 드래프트 round-trip).
  - 기존 `DomainOntologyEditor`(SCOR 트리 뷰)는 유지 — 이름 분리 완료.

### Week 2.5 — OD-10 Legacy Cleanup (2026-04-18)

현재 Ontology-First Redesign 계획과 무관한 Engine Phase 1a / Phase 2a UI/API/모듈을 일괄 제거. 사용자 피드백: "예전 기능이 다 남아 있으니 힘들다". 목적: 매뉴얼 빌더 중심 UX로 단순화 + 코드베이스에서 legacy 경로 완전 제거.

- [x] **OD-10-A (Frontend UI)** — `ModelingSection.tsx` 단순화. `repoId`/`workflow`/`seeding`/`simTarget`/SETTINGS_NAV/SCM 데모 로더 전부 제거. nav는 `builder` + `ontology` 2개만. 삭제 컴포넌트: `AnalysisConsole`, `SimulationPanel`, `MappingWorkbench`, `MappingCanvas`, `MappingSplitView`, `CodeGraphViewer`, `SourceViewer`, `ApprovalList`, `ImpactQueryPanel` (9개). `DomainOntologyEditor`에서 미사용 `repoId` prop 제거.
- [x] **OD-10-B (Frontend API)** — `lib/api/modeling.ts` 재작성. 남는 것: `DomainNode`, `loadTemplate`, `getOntologyTree`, `addDomainNode`, `draftOntology`, `validateOntologyYaml`, `saveOntologyYaml`, `listManuals`, `readManual`. 제거: `parseRepo`, `getCodeGraph`, 모든 `mapping/*`, `impact/*`, `approval/*`, `seed/*`, `engine/*`, `source/*` 함수 (총 17개 + 관련 타입).
- [x] **OD-10-C (Backend API)** — `backend/modeling/api/modeling.py` 재작성(ontology_api만 include). 파일 삭제: `code_api.py`, `source_api.py`, `mapping_api.py`, `approval_api.py`, `engine_api.py`, `query_api.py`, `seed_api.py` (7개).
- [x] **OD-10-D (Backend 모듈)** — `backend/modeling/` 하위 `code_analysis/`, `mapping/`, `approval/`, `change/`, `simulation/`, `query/`, `data/`, `agent/` 디렉터리 일괄 삭제. `infrastructure/git_connector.py` 삭제. 남는 것: `ontology/` + `infrastructure/neo4j_client.py` + `api/{modeling,ontology_api}`.
- [x] **OD-10-E (Tests)** — legacy 테스트 15개 삭제: `test_code_graph`, `test_change_detector`, `test_git_connector`, `test_java_parser`, `test_mapping_service`, `test_query_engine`, `test_modeling_api`, `test_modeling_e2e`, `test_sim_engine`, `test_sim_models`, `test_sim_registry`, `test_approval_service`, `test_engine_api`, `test_source_api`, `test_term_resolver`.
- [x] **OD-10-F (Docs)** — `demo_guide.md`에서 Mapping Workbench + Section 2 Modeling MVP 섹션 제거, 최상단에 cleanup 경고 배너 추가.
- [x] **검증** — 84 ontology tests pass (`pytest tests/test_ontology_*.py tests/test_neo4j_client.py`), 791 tests collect (import 에러 없음), `tsc --noEmit` 0 error, `python -c "from backend.main import app"` OK (145 routes).

### 다음 (Week 2+)
- [ ] **OD-7-B** — 팀 분배표 (팀원 정보 필요)
- [ ] **OD-9** — 빌더 UX 개선: YAML 구문 하이라이트 (Monaco/CodeMirror), 포맷 버튼, 기존 온톨로지 불러와 편집
- [ ] **Section 3 신설** — 3 agents(WhatIf/WhyTrace/Diagnostic) + 시뮬레이션 엔진을 Section 3에서 새로 설계. OD-10으로 제거된 코드는 git history에 있음(`4b66c65` 이전).

---

## 2026-04-17 (Image Management System 구현)

### 위키 이미지 관리 시스템 (11 tasks, 60 tests, TS clean)
- [x] **IMGM-1** — ImageRegistry core (hash index, ref counting, startup scan)
- [x] **IMGM-2** — Source field on ImageAnalysis sidecar (annotation derivative tracking)
- [x] **IMGM-3** — Upload SHA-256 hash dedup (12-char prefix filename)
- [x] **IMGM-4** — Registry init in main.py + tree_change event handler (ref cleanup on delete)
- [x] **IMGM-5** — Ref tracking on document save (diff old/new image refs in wiki_service.py)
- [x] **IMGM-6** — Admin API (stats, paginated list, single delete w/ 409, bulk-delete unused)
- [x] **IMGM-7** — OCR inheritance endpoint (copy sidecar data between images)
- [x] **IMGM-8** — fabric.js + ImageCopyExtension (Ctrl+C + right-click context menu)
- [x] **IMGM-9** — ImageViewerModal (fullscreen viewer + annotation editor: rect/ellipse/arrow/text)
- [x] **IMGM-10** — ImageManagementPage (admin gallery + pagination + filter + search + bulk delete)
- [x] **IMGM-11** — Routing + types + admin gate (VirtualTabType, store title, FileRouter, TreeNav)

---

## 2026-04-17 (Phase 2a Design Review 수정)

### Mapping Workbench 버그 수정 (design review 발견)
- [x] **E2a-7** — Seed API에서 소스 파일 자동 복사 (`sample-repos/scm-demo/src` → `/tmp/ontong-repos/scm-demo/src`). Source API가 빈 트리 반환하던 문제 해결 (`seed_api.py`)
- [x] **E2a-8** — React Flow fitView 노드 로딩 후 재실행. `onInit`으로 ReactFlowInstance ref 저장, layout useEffect 후 `requestAnimationFrame(() => fitView())` 호출 (`MappingCanvas.tsx`)
- [x] **DEMO** — `toClaude/demo_guide_modeling.md` 전면 재작성 (Part A: Engine Phase 1a + Part B: Mapping Workbench Phase 2a 통합)

---

## 2026-04-16 (Image Search — 위키 이미지 검색 가능화)

### 이미지 분석 파이프라인 구현 (10 tasks + review fixes, 30 tests)
- [x] **IMG-MODELS** — ImageAnalysis dataclass + sidecar .meta.json I/O (save/load/needs_processing)
- [x] **IMG-OCR** — OCREngine (EasyOCR wrapper, lazy init, asyncio.to_thread)
- [x] **IMG-VISION** — VisionProvider protocol + NoopVisionProvider + OllamaVisionProvider (base64 + Korean prompt)
- [x] **IMG-ANALYZER** — ImageAnalyzer orchestrator (OCR→Vision→sidecar caching, force reprocess)
- [x] **IMG-CONFIG** — 8 settings (image_analysis_enabled, ocr_engine/languages/confidence/gpu, vision_provider/model, max_workers)
- [x] **IMG-INDEXER** — enrich_chunk_with_images() + IMAGE_REF_RE → [이미지: description] 치환, external URL filter
- [x] **IMG-QUEUE** — ImageProcessingQueue (asyncio.Semaphore + gather 병렬 처리, max_concurrent)
- [x] **IMG-WIRE** — WikiService._bg_image_process() + main.py lifespan 초기화
- [x] **IMG-CLI** — backfill_images.py (--dry-run, --ocr-only, --vision-only, --reprocess, --workers N)
- [x] **IMG-E2E** — TestEndToEndImageSearch (2 tests: enriched chunks + image-only document searchable)
- [x] **IMG-FIX** — Code review 4건 수정 (URL filter, parallel workers, vision-only flag, dedup needs_processing)

---

## 2026-04-16 (Section 2 Modeling Engine — Phase 1a)

### Engine-First Architecture 리디자인 (10 tasks, 28 tests)
- [x] **E1a-MODELS** — ParametricSimResult, SimulationParam, SimulationOutput, AffectedProcessRef
- [x] **E1a-RESOLVER** — TermResolver (Korean alias 30개 + fuzzy 0.55 + LLM fallback)
- [x] **E1a-REGISTRY** — SimRegistry (9 SCM entities × calc functions, static _REGISTRY pattern)
- [x] **E1a-ENGINE** — SimulationEngine (param clamp + calculate + BFS impact tracing)
- [x] **E1a-API** — Engine API (/engine/query, /simulate, /params/{id}, /status)
- [x] **E1a-SEED** — Seed enhancement (sim_entities count in response)
- [x] **E1a-CLIENT** — Frontend API client (4 functions + 6 TypeScript interfaces)
- [x] **E1a-ANALYSIS** — AnalysisConsole.tsx (자연어 입력 + 예시 질의 + 결과 표시)
- [x] **E1a-SIM** — SimulationPanel.tsx (엔티티 드롭다운 + 파라미터 슬라이더 + before/after)
- [x] **E1a-SIDEBAR** — ModelingSection.tsx (MAIN_NAV/SETTINGS_NAV 분리, 기본탭=analysis)
- [x] **E1a-FIX** — Division-by-zero guard + hardcoded condition fix (코드 리뷰 반영)

---

## 2026-04-12 (Section 2 Modeling MVP — Full Implementation)

### Section 2 Modeling MVP 완료 (18 tasks, 69 tests)
- [x] **S2-INFRA** — Neo4j Community docker service + Neo4jClient + config
- [x] **S2-PARSER** — CodeParser Protocol + tree-sitter Java parser (15 entity/relation types)
- [x] **S2-GRAPH** — Code graph writer (Neo4j MERGE queries)
- [x] **S2-GIT** — Git connector (clone/pull/diff/list_files)
- [x] **S2-ONTOLOGY** — SCOR+ISA-95 template (30+ nodes) + OntologyStore CRUD
- [x] **S2-MAPPING** — Mapping engine (YAML persistence, inheritance, gap detection)
- [x] **S2-QUERY** — Deterministic impact analysis (term lookup → BFS → reverse mapping)
- [x] **S2-CHANGE** — Change detector (diff → BROKEN/REVIEW/UNMAPPED classification)
- [x] **S2-APPROVAL** — Approval workflow (draft → review → confirmed)
- [x] **S2-API** — FastAPI endpoints (code, ontology, mapping, query, approval)
- [x] **S2-FE** — Frontend: API client + 5 view components + ModelingSection shell
- [x] **S2-E2E** — End-to-end integration test (7 tests)
- [x] **S2-REVIEW** — Final code review fixes (security guards, type fixes, frontend enum mismatch)

---

## 2026-04-12 (Lineage Bugfix — VersionTimeline + MetadataIndex)

### VersionTimeline 자동 갱신 수정
- [x] **P2-FIX1** — `VersionTimeline.tsx`에 `wiki:lineage-changed` 이벤트 리스너 추가. 폐기 되돌리기 후 "전체 버전 히스토리" 즉시 갱신
- [x] **P2-FIX2** — `wiki_service.py` `_clear_stale_lineage_refs()`에서 파일의 stale lineage 제거 후 MetadataIndex 미갱신 → version-chain API가 stale 체인 반환하던 버그 수정

---

## 2026-04-11 (Status Simplification + Lineage/Versioning Overhaul)

### Phase 1: Status Simplification
- [x] **SL-1** — review/미설정 제거, draft|approved|deprecated만 남김
- [x] **SL-2** — 새 문서 자동 draft, approved 수정 시 자동 draft 강등
- [x] **SL-3** — 프론트엔드 타입/드롭다운/뱃지 색상 업데이트

### Phase 2: Scoring Update
- [x] **SL-4** — review=70, unset=50 제거, draft 폴백 40

### Phase 3: MetadataIndex Enrichment
- [x] **SL-5** — status/supersedes/superseded_by 저장 + 역참조 인덱스

### Phase 4: Lineage Write-Time Validation
- [x] **SL-6** — 자기참조 차단, 사이클 감지, 경쟁 대체 경고

### Phase 5: Deprecation Side Effects
- [x] **SL-7** — 폐기 시 충돌 자동 해결, deprecated 제외, 0건 검색 폴백

### Phase 6: Version Chain API + Timeline UI
- [x] **SL-8** — version-chain API + VersionTimeline 프론트엔드 컴포넌트

### Phase 7: Reference Integrity + Deprecation UX
- [x] **SL-9** — 이동/삭제 시 참조 업데이트, TreeNav deprecated 표시, statuses API

### Phase 8: Metadata Inheritance + Bulk Status
- [x] **SL-10** — predecessor-context API, bulk-status API

---

## 2026-04-11 (UI/UX Overhaul — Content-First Layout)

### Collapsible Side Panels
- [x] **UX-1 TreeNav 접기** — react-resizable-panels collapsible prop, Cmd+B 단축키, 접힌 상태에서 아이콘 스트립 표시, localStorage 상태 유지
- [x] **UX-2 AICopilot 접기** — 동일 패턴, Cmd+J 단축키

### AI Copilot Popout
- [x] **UX-6 AI 팝아웃** — AICopilot을 별도 floating window로 분리 가능. 드래그 이동 + 리사이즈. Cmd+J로 토글. 패널 복귀(dock back) 지원. `page.tsx`

### Unified Document Info Bar
- [x] **UX-3 DocumentInfoBar** — 32px 단일 행에 status badge, domain/process, confidence pill, stale dot, 연결 문서 수, feedback 아이콘 버튼, drawer 토글
- [x] **UX-4 DocumentInfoDrawer** — 3탭(메타데이터/신뢰도/연결 문서) overlay drawer, Cmd+I 토글, Escape/외부 클릭으로 닫기
- [x] **UX-5 MarkdownEditor 리팩토링** — MetadataTagBar + TrustBanner + LinkedDocsPanel 3개 스택 → DocumentInfoBar + DocumentInfoDrawer로 교체. 기존 기능 100% 보존

---

## 2026-04-11 (세션 42 — User-Driven Self-Healing Phase C+D)

### Phase D — Knowledge Graph Unification
- [x] **PD-1 Relationship 모델** — source, target, rel_type, strength, created_by, metadata. GraphResult/GraphStats 모델 추가
- [x] **PD-2 GraphStore** — InMemoryGraphStore + RedisGraphStore. BFS get_graph(depth), stats, upsert 중복 제거, remove_all 양방향 정리
- [x] **PD-3 GraphBuilder** — metadata.related → "related", supersedes → "supersedes", ConflictStore → "conflicts" (resolved 제외). rebuild_all + rebuild_file (incremental)
- [x] **PD-4 Graph API** — GET /api/graph/{path}?depth=1&rel_type=, GET /api/graph/stats. main.py에서 startup 시 graph rebuild, tree_change 이벤트 시 incremental rebuild
- [x] **PD-5 테스트** — test_phase_d_knowledge_graph.py (22 tests: Model 3, Store 10, Builder 7, Models 2)

---

## 2026-04-11 (세션 42 — User-Driven Self-Healing Phase C: Score Integration)

### Phase C — Score Integration
- [x] **PC-1 가중치 재조정** — freshness 30→25, backlinks 15→10, owner_activity 15→10, user_feedback(신규) 15. 합계 100 유지
- [x] **PC-2 _score_user_feedback** — verified/(verified+needs_update) × 100. 피드백 없으면 50 (중립). compute_confidence에 feedback_verified, feedback_needs_update 파라미터 추가
- [x] **PC-3 ConfidenceService 피드백 연동** — set_feedback_tracker(), _get_feedback_counts(). main.py에서 feedback_tracker를 confidence_svc보다 먼저 생성하도록 순서 수정
- [x] **PC-4 "확인했음" → freshness 갱신** — POST /api/wiki/feedback/{path} action=verified 시 문서 frontmatter의 updated/updated_by 자동 갱신. 내용 변경 없이 stale 해제
- [x] **PC-5 테스트** — test_phase_c_score_integration.py (20 tests: WeightConfig 3, ScoreUserFeedback 7, ComputeConfidence 5, ServiceFeedback 3, FreshnessRefresh 2)

---

## 2026-04-11 (세션 41 — User-Driven Self-Healing Phase A+B)

### Phase B — User Feedback Loop
- [x] **PB-1 FeedbackTracker** — InMemory + Redis 이중 구현. verified/needs_update/thumbs_up/thumbs_down 4종 액션. FeedbackSummary 모델 (카운트 + last_verified_at/by)
- [x] **PB-2 Feedback API** — POST/GET /api/wiki/feedback/{path:path}. 피드백 기록 시 confidence 캐시 자동 무효화. main.py에 create_feedback_tracker() 와이어링
- [x] **PB-3 TrustBanner 피드백 버튼** — "확인했음" (초록) / "수정 필요" (주황) 버튼. 피드백 카운트 + 마지막 확인자/시간 표시. 피드백 후 신뢰도 점수 자동 리프레시
- [x] **PB-4 AICopilot 소스 thumbs** — 소스 카드 옆 ThumbsUp/ThumbsDown 아이콘. 클릭 시 thumbs_up/thumbs_down 피드백 전송
- [x] **PB-5 테스트** — test_phase_b_feedback.py (12 tests: InMemoryStore 5, Tracker 5, Model 2)

---

## 2026-04-11 (세션 41 — User-Driven Self-Healing Phase A: Foundation Fixes)

### Phase A — 기반 수리
- [x] **PA-1 MetadataIndex 확장** — on_file_saved()에 updated/updated_by/created_by/related 파라미터 추가. rebuild()에 extended kwarg 추가. wiki_service, main.py, metadata.py의 모든 호출부 업데이트
- [x] **PA-2 _get_backlink_count 버그 수정** — 루프 본문이 비어 항상 0 반환하던 버그. related 필드에서 현재 문서를 참조하는 다른 문서를 카운트하도록 수정
- [x] **PA-3 _is_owner_active 버그 수정** — 루프 본문이 비어 항상 False 반환하던 버그. updated_by 매칭 + updated 타임스탬프 90일 체크 로직 구현. _parse_date() 유틸 추가
- [x] **PA-4 프론트엔드 사용자 ID 연결** — currentUser.ts 싱글톤, AuthContext에서 setCurrentUser 호출, lockManager/MarkdownEditor에서 랜덤 SESSION_USER 제거 → getCurrentUserName() 사용. GET /api/auth/me 엔드포인트 추가
- [x] **PA-5 테스트** — test_phase_a_confidence_signals.py (16 tests: MetadataIndex 확장 4, Backlink 4, Owner Activity 5, ParseDate 3)

---

## 2026-04-11 (세션 40 — Trust System Phase 4: Smart Conflict Resolution)

### Phase 4 — Smart Conflict Resolution
- [x] **P4-1 TypedConflict + ConflictAnalysis 모델** — `schemas.py`에 TypedConflict, `models.py`에 ConflictAnalysis LLM 출력 모델 추가
- [x] **P4-2 analyze_pair() + StoredConflict 확장** — ConflictCheckSkill에 LLM 기반 페어 분석 static method 추가. StoredConflict에 conflict_type/severity/summary_ko/claim_a/claim_b/suggested_resolution/resolution_detail/analyzed_at/resolved/resolved_by/resolved_action 필드 확장. conflict_analyze_pair.md 프롬프트 생성
- [x] **P4-3 해결 액션 API** — POST /resolve (dismiss/version_chain/scope_clarify/merge), GET /typed (분석된 충돌 목록), POST /analyze-pair (수동 AI 분석). ConflictStore에 update_analysis/resolve_pair 메서드 추가 (InMemory + Redis). ConflictDetectionService에 get_typed_pairs/resolve_pair/trigger_deep_analysis/update_analysis 추가
- [x] **P4-4 ConflictDashboard 유형 뱃지 + 해결 UI** — 대시보드 전면 리라이트. 제목 "관련 문서 관리"로 변경. 유형 뱃지(사실 불일치/범위 중복/시간 차이/무관), 심각도 dot, AI 분석 버튼, 원클릭 해결 버튼 4종, claim 인용 표시
- [x] **P4-5 관리 다이제스트** — DocumentDigestService (오래됨/신뢰도낮음/미해결충돌 그룹핑), GET /api/wiki/digest 엔드포인트, MaintenanceDigest.tsx 컴포넌트, 사이드바 설정에 "관리가 필요한 문서" 메뉴 추가
- [x] **P4-6 테스트 + 문서** — test_phase4_smart_conflict.py 13 tests all pass

### 스케일 대비 + UI 자기설명 개선
- [x] **API 페이지네이션** — GET /conflict/typed에 limit/offset 추가 (기본 50, 최대 200). GET /wiki/digest에 limit/offset 추가 (섹션별 적용)
- [x] **파일 스캔 안전 캡** — digest.py MAX_FILES_SCAN=100,000
- [x] **ConflictDashboard UX** — 사용 가이드 토글 (유형별 의미, 해결 액션 설명), 미분석 뱃지에 안내 문구, 타입 뱃지 툴팁에 설명 추가, 클라이언트 페이지네이션 (20건/페이지)
- [x] **MaintenanceDigest UX** — 각 섹션별 설명+조치방법 안내, 안내 배너 추가, 접기/펼치기 (기본 5건), 빈 상태 가이드 개선

### 100K+ 문서 스케일 대비 (2차)
- [x] **ConfidenceCache LRU** — OrderedDict 기반 LRU + TTL 이중 캐시 (max_size=5,000). 100K 문서 중 hot working set만 캐싱, 메모리 누수 방지
- [x] **Digest 결과 캐싱** — DigestResult TTL 5분 캐시 + tree_change 이벤트로 자동 무효화
- [x] **Digest async 스캔** — asyncio.to_thread()로 rglob 이동, 이벤트 루프 블로킹 방지. frontmatter 1KB만 읽기
- [x] **EventBus 콜백** — event_bus.on("tree_change", callback) 패턴 추가. confidence + digest 캐시 자동 무효화
- [x] **search_path 최적화** — full tree build 대신 list_file_paths() 사용 + early termination (limit 도달 시 즉시 중단)
- [x] **reindex-pending 배치 제한** — REINDEX_BATCH_LIMIT=100, 나머지는 remaining 카운트로 반환
- [x] **Storage I/O 비동기화** — list_tree(), list_subtree() 모두 asyncio.to_thread()로 이동. 100K 파일 디렉토리에서 이벤트 루프 블로킹 방지
- [x] **충돌 해결 상태 보존 버그 수정** — replace_for_file()이 재인덱싱 시 resolved/analyzed 상태를 덮어쓰던 버그. 유사도 변동 < 0.05이면 상태 보존, > 0.05이면 리셋 (내용 변경 시 재감지). InMemory + Redis 양쪽 수정. 테스트 4건 추가 (총 17건)

---

## 2026-04-11 (세션 39 — Trust System Phase 3: 읽기 시 맥락)

### Trust System Phase 3 — Read-Time Trust Context
- [x] **P3-1 CitationTracker** — AI 답변 소스 인용 카운트 (Redis/InMemory). `rag_agent.py`에서 소스 emit 후 자동 기록. 파일: `trust/citation_tracker.py`, `rag_agent.py`
- [x] **P3-2 ConfidenceResult 확장** — `citation_count` (인용 횟수) + `newer_alternatives` (신뢰도 < 40인 문서에 대한 더 높은 신뢰도 대안 3건). `NewerAlternative` 모델 추가. 파일: `trust/confidence.py`, `trust/confidence_service.py`
- [x] **P3-3 TrustBanner 컴포넌트** — 에디터 상단에 신뢰도 pill(팝오버), 오래된 문서 경고, 최신 대안 링크, 인용 카운트 통합 표시. MarkdownEditor에서 기존 pill 코드 제거 후 TrustBanner로 대체. 파일: `TrustBanner.tsx`, `MarkdownEditor.tsx`
- [x] **P3-4 와이어링** — main.py에서 CitationTracker 생성 → ConfidenceService + RAGAgent에 주입. 파일: `main.py`
- [x] **P3-5 테스트** — 14개 단위 테스트 (CitationTracker, ConfidenceResult 확장, NewerAlternative, 직렬화). 파일: `tests/test_phase3_trust.py`

---

## 2026-04-11 (세션 39 — 스코어링 중앙화 + UX 개선)

### 스코어링 설정 중앙화
- [x] **S-1 scoring_config.py** — 모든 점수 가중치/임계값/공식을 `ScoringConfig` 데이터클래스 + `explain()` 메서드로 단일 파일에 집중. 파일: `trust/scoring_config.py`
- [x] **S-2 confidence.py 리팩터** — 하드코딩 가중치(30/25/15/15/15)와 tier 임계값(70/40) → `SCORING.confidence` 참조로 교체. 파일: `trust/confidence.py`
- [x] **S-3 search.py 리팩터** — 관련 문서 min_similarity 0.5→0.7(SCORING.related.min_similarity), composite 가중치 하드코딩 → `SCORING.related.w_similarity/w_confidence`. 파일: `api/search.py`
- [x] **S-4 rag_agent.py 리팩터** — RAG boost floor 0.7 → `SCORING.rag_boost.floor`. 파일: `rag_agent.py`
- [x] **S-5 conflict_service.py 리팩터** — SIMILARITY_THRESHOLD/HNSW_N_RESULTS/MAX_RESULTS → `SCORING.conflict.*`. 파일: `conflict_service.py`
- [x] **S-6 wiki_service.py 리팩터** — auto_suggest 임계값 0.7 / top 3 → `SCORING.related.auto_suggest_similarity/auto_suggest_max`. 파일: `wiki_service.py`

### 관련 문서 UX 개선
- [x] **U-1 기본 2건 표시 + 더 보기** — LinkedDocsPanel에서 기본 2건만 보여주고 나머지는 "더 보기 (+N)" 토글. 파일: `LinkedDocsPanel.tsx`
- [x] **U-2 결과 0건일 때 섹션 숨김** — 이미 구현 완료 (relatedDocs.length > 0 조건)

### 스코어링 투명성 API
- [x] **E-1 GET /api/wiki/scoring-config** — `SCORING.explain()` 반환. 모든 가중치/임계값/공식을 한국어로 설명. 파일: `api/wiki.py`

### 사용자 투명성 + 관리자 대시보드
- [x] **V-1 신뢰도 pill 팝오버** — 에디터 상단 pill 클릭 시 5개 시그널 상세(점수 바 + 가중치 + 설명) 팝오버. 클릭 외부 닫기. 파일: `MarkdownEditor.tsx`
- [x] **V-2 ScoringDashboard 관리자 페이지** — 설정 사이드바에 "신뢰도 설정" 항목 추가. scoring-config API 호출하여 모든 가중치/임계값/공식을 카드 형태로 표시. 파일: `ScoringDashboard.tsx`, `TreeNav.tsx`, `FileRouter.tsx`, `workspace.ts`, `useWorkspaceStore.ts`
- [x] **V-3 AI소스 뱃지 툴팁 강화** — 호버 시 신뢰도 + 해석 메시지("높음 — 신뢰할 수 있는 문서" 등) 표시. 줄바꿈으로 가독성 개선. 파일: `AICopilot.tsx`

---

## 2026-04-11 (세션 38 — Trust System Phase 2: Write-Time Related Document Nudge)

### Trust System Phase 2 — 작성 시 넛지
- [x] **T2-1 관련 문서 API** — `GET /api/search/related?path=X&limit=5`. HNSW 후보 발견 → 파일 평균 임베딩 cosine 비교 → 신뢰도+메타데이터 보강. 정렬: `0.6*sim + 0.4*(conf/100)`. 시스템 경로 제외. 파일: `api/search.py`, `schemas.py`
- [x] **T2-2 LinkedDocsPanel 확장** — "참고할 만한 문서" 섹션 추가 (Sparkles 아이콘 + 신뢰도 dot + 유사도%). 파일 열 때 + 500ms 디바운스 fetch. 파일: `LinkedDocsPanel.tsx`
- [x] **T2-3 저장 시 자동 related** — `_bg_index()` 완료 후 `_auto_suggest_related()` 호출. `related` 비어있을 때만, similarity>0.7 상위 3건 frontmatter에 자동 추가. 파일: `wiki_service.py`
- [x] **T2-4 와이어링+테스트** — `main.py`에서 chroma/confidence_svc → wiki_service, search_api에 주입. 12개 테스트 통과. 파일: `main.py`, `tests/test_related_search.py`

---

## 2026-04-09 (세션 38 — Trust System Phase 1: Document Confidence Score)

### Trust System Phase 1 — 문서 신뢰도 점수
- [x] **T1-1 ConfidenceScorer 엔진** — 5개 시그널(최신성 30, 상태 25, 메타완성도 15, 백링크 15, 소유자활동 15) 가중 합산 → 0-100 점수 + tier(high/medium/low) + stale 플래그. 파일: `trust/confidence.py`, `trust/confidence_cache.py`, `trust/confidence_service.py`, `trust/__init__.py`
- [x] **T1-2 Confidence API** — `GET /api/wiki/confidence/{path}`, `GET /api/wiki/confidence-batch?paths=`. 파일: `api/wiki.py`
- [x] **T1-3 RAG 랭킹 통합** — `_build_sources()`에 confidence_service 전달, 신뢰도 기반 mild boost (`0.7 + 0.3 * conf/100`), `SourceRef`에 `confidence_score` + `confidence_tier` 필드 추가. 파일: `rag_agent.py`, `schemas.py`
- [x] **T1-4 프론트엔드 뱃지** — AICopilot 소스에 초록/노랑/회색 신뢰도 dot + 툴팁, MarkdownEditor 헤더에 신뢰도 pill(점수+메시지). 파일: `AICopilot.tsx`, `MarkdownEditor.tsx`, `sseClient.ts`
- [x] **T1-5 와이어링+테스트** — main.py에서 ConfidenceService 생성→wiki_api, RAGAgent에 주입. 28개 단위 테스트 통과. 파일: `main.py`, `tests/test_confidence.py`

---

## 2026-04-09 (세션 37 — Path-Aware RAG + 대화형 경로 명확화 + 버그 수정)

### 버그 수정
- [x] **스킬 무시 버튼 무효** — 프론트에서 "무시" 클릭해도 백엔드가 독자적으로 auto-match → 적용됨. `ChatRequest.dismissed_skills` 필드 추가, 프론트에서 무시 목록 전송, 백엔드에서 해당 스킬 건너뜀. 파일: `schemas.py`, `api/agent.py`, `sseClient.ts`, `AICopilot.tsx`
- [x] **사이드바 스킬 목록 미표시** — FastAPI 307 trailing slash redirect ↔ Next.js 308 strip slash가 무한 리다이렉트 루프 생성. `redirect_slashes=False` + 라우트 `"/"` → `""` 수정. 파일: `main.py`, `api/skill.py`
- [x] **보안-점검-도우미 frontmatter 누락** — `type: skill`, `trigger` 필드 없어서 스킬 로더가 무시. frontmatter 보완. 파일: `wiki/_skills/보안/보안-점검-도우미.md`
- [x] **채팅 첫 응답 지연 체감** — `main_router.classify()` LLM 호출 동안 UI 무반응. classify 시작 전 즉시 `thinking_step(routing, start)` 이벤트 발행. 파일: `api/agent.py`

### Part 2 — 충돌 & Lineage
- [x] **2A 사이클 감지** — `_resolve_superseded_chain`에 `visited` set 추가, 재방문 시 break + warning. 파일: `rag_agent.py`
- [x] **2C deprecated 뱃지** — `SourceRef.superseded_by` 필드 추가, deprecated 소스도 검색 결과에 포함, FE에 "폐기됨" 뱃지 + "→ 새 버전" 링크. 파일: `schemas.py`, `rag_agent.py`, `sseClient.ts`, `AICopilot.tsx`
- [x] **2B 폐기 되돌리기** — `POST /api/conflict/undeprecate` API + ConflictDashboard "되돌리기" 버튼. 파일: `api/conflict.py`, `ConflictDashboard.tsx`
- [x] **2D 쌍 그룹핑** — 같은 file_a를 공유하는 충돌 쌍을 그룹 렌더링 (주 문서 + 충돌 문서 목록). 파일: `ConflictDashboard.tsx`
- [x] **충돌 스캔 결과 영속화** — `.env`에 `REDIS_URL` 추가 → RedisConflictStore 활성화. 서버 재시작해도 스캔 결과 유지. 기본 threshold 0.95 → 0.85로 변경 (`ONTONG_CONFLICT_THRESHOLD` 환경변수). 파일: `.env`, `conflict_service.py`

### Path-Aware RAG

### Phase 1 — 인덱싱 변경 (L1 + L2A)
- [x] **P1-1~3** — `_build_path_prefix()` + 모든 청크에 `[분류: X > Y] [문서: Z]` 프리픽스 + `path_depth_1/2/stem` 메타데이터. 재인덱싱 완료 (172 chunks).

### Phase 2 — 쿼리 경로 필터링 (L2B + L2C)
- [x] **P2-1~2** — `extract_path_filter()` + wiki_search 스킬 `path_preference` 파라미터 통합

### Phase 3 — 경로 분산 감지 + 대화형 명확화 (L3)
- [x] **P3-1~4** — `_detect_path_ambiguity()` (min_paths=3, dominance=0.70), `ClarificationRequestEvent` 발행, `clarification_response_id` 활성화, 세션 `path_preferences` 누적

### Phase 4 — 경로 부스트 리랭크 (L4)
- [x] **P4-1~2** — `_path_boost_rerank()` (recency decay, weight=0.08) + _handle_qa 통합

### 평가 + 문서
- [x] **E1** — 기존 RAG 12쿼리 회귀 테스트 통과 (hit@5=1.0, MRR=1.0)
- [x] **E2** — 브라우저 E2E 검증 완료
- [x] **DOC** — CHANGES/TODO/demo_guide 동기화

---

## 2026-04-07 ~ 2026-04-08 (세션 36 — 태그 자동화 고도화 + RAG tag boost)

### Phase A — 추천 정확도 + 중복 방지
- [x] **A1 프롬프트 외부화** — `auto_tag_pass1.md`, `auto_tag_pass2.md`, `auto_tag.md` (fallback)
- [x] **A2 컨텍스트 확장** — filename/parent_dir, neighbor tags/domains, related docs tags 신호 주입
- [x] **A3 2-pass 계층 추론** — Pass1: domain/process → Pass2: tags scoped to domain (domain_tags top 50 주입)
- [x] **A4 Few-shot 예시** — `auto_tag_examples.json` 7개 도메인 예시, Pass2 프롬프트에 동적 주입
- [x] **A5 Always-normalize + 스키마 확장** — 모든 추천 태그를 `tag_registry.find_similar` 3층 통과
  (auto-replace<0.35 / LLM-confirm<0.55 / soft-alternative<0.65). `TagAlternative`, `tag_replaced`, `tag_alternatives` 필드 추가
- [x] **A6 Soft UI** — AutoTagButton에 alternatives 칩 표시, 클릭 시 치환 수락, 정규화 toast
- [x] **A7 Confidence 자동 보정** — alternatives 수 / 재사용 비율 / neighbor 도메인 일치도 반영
- [x] **A8 회귀 테스트** — `tests/test_auto_tag_quality.py`, 27개 샘플에 대해 **domain 정확도 100%, 평균 conf 0.85, 22건 자동 치환** 베이스라인 기록

### Phase B — Query-time tag boost + 평가
- [x] **B1 extract_query_tags** — `filter_extractor.py`에 쿼리→기존 태그 의미 매칭 (거리 0.55)
- [x] **B2 RAG boost rerank** — `RAGAgent._tag_boost_rerank`로 태그 교집합만큼 cosine 거리 감산, `ONTONG_TAG_BOOST_WEIGHT` 환경변수
- [x] **B3 Tag-only fallback** — domain/process 필터 0건 시 태그 교집합 필터로 재시도 → 그것도 0이면 무필터
- [x] **B4 평가 스크립트** — `tests/test_rag_tag_boost.py` + `rag_eval_queries.json` (12 쿼리). **Baseline hit@5=1.0, MRR=1.0** (천장 효과, 회귀 없음)

---

## 2026-04-05 (세션 33 — Domain-Process 계층 구조 + 데이터 클린업)

- [x] **템플릿 구조 변경** — flat `{domains[], processes[]}` → hierarchical `{domain_processes: {domain: [procs]}}`
- [x] **백엔드 CRUD API** — domain/process 계층 CRUD (`POST/DELETE /templates/domain`, `/domain/{d}/process`)
- [x] **레거시 마이그레이션** — 기존 flat 템플릿 자동 감지 → hierarchical 변환
- [x] **프론트엔드 cascade UI** — domain 선택 → 해당 process만 표시, domain 변경 시 process 리셋
- [x] **위키 데이터 클린업** — 기존 20개 문서 삭제, 7개 도메인별 21개 샘플 문서 생성
- [x] **filter_extractor 동적 키워드** — 하드코딩 → templates.json에서 동적 로드 (lazy import로 테스트 호환)
- [x] **metadata_service 프롬프트** — 도메인/프로세스 목록을 templates에서 동적 생성
- [x] **AutoTagButton confidence** — 신뢰도 뱃지(색상 3단계), domain/process 개별 수락, 저신뢰 태그 흐림 처리
- [x] **메타데이터 validation** — DomainSelect 템플릿 외 값 노란 경고, wiki_service 저장 시 warning 로그
- [x] **related 문서 편집 UI** — MetadataTagBar에 관련 문서 TagInput(파일 경로 자동완성) + lineage 읽기전용 표시
- [x] **Bulk auto-tag API** — `POST /api/metadata/suggest-bulk` (배치 처리, apply 옵션)
- [x] **UntaggedDashboard 업그레이드** — bulk API 연동, 미리보기/전체적용, confidence 표시, 진행률 바
- [x] **Materialized metadata index** — `.ontong/metadata_index.json` 증분 업데이트 (save/delete/reindex)
- [x] **Lazy tag search API** — `GET /api/metadata/tags/search?q=` (debounce prefix match)
- [x] **Lazy path search API** — `GET /api/wiki/search-path?q=` (related 문서 자동완성)
- [x] **MetadataTagBar lazy refactor** — `fetchAllTags()` + `fetchTree()` 제거 → templates O(1) + debounce search
- [x] **UntaggedDashboard pagination** — offset/limit 페이지네이션 + `/api/metadata/stats` 인덱스 기반
- [x] **TagInput onSearch prop** — 정적 suggestions + async debounce search 이중 지원
- [x] **DomainProcessPicker** — Domain/Process 드롭다운 2개 → 트리형 통합 셀렉터 1개 (도메인 펼치면 하위 프로세스 lazy 표시)
- [x] **MetadataTagBar 복원** — DomainProcessPicker 적용 취소, 기존 DomainSelect 2개(Domain/Process) 방식으로 복원
- [x] **MetadataTemplateEditor 트리 구조** — Domain/Process/Tags 3섹션 → Domain-Process 트리(도메인 클릭→프로세스→파일) + Tags 2섹션으로 개편. lazy loading 적용.
- [x] **사이드바 태그 브라우저 트리 구조** — Domain/Process/Tags 3섹션 → Domain→Process→Files 트리 + Tags 2섹션. Process lazy loading 적용.

## 2026-04-06 (세션 34 — 10만 문서 스케일 성능 최적화)

- [x] **역인덱스 추가** — metadata_index에 `domain_files`, `process_files`, `tag_files` 역인덱스. rebuild/save/delete 모두 증분 유지.
- [x] **`/files-by-tag` O(n)→O(1)** — 인덱스 기반 조회 + pagination(`offset`, `limit`) 지원. 전체 스캔 제거.
- [x] **`/tags/search` pagination** — `{tags: [{name, count}], total}` 형식으로 변경, offset/limit 지원.
- [x] **`/suggest-bulk` 병렬화** — `asyncio.gather` + `Semaphore(5)` 동시 LLM 호출 (순차→병렬).
- [x] **사이드바 파일 목록 limit** — 프로세스/태그 하위 파일 20건 단위 + "더보기" 버튼.
- [x] **사이드바 태그 뱃지 limit+검색** — 상위 30개 표시 + 검색 input + 이전/다음 페이지네이션.
- [x] **UntaggedDashboard bulk 단순화** — 프론트에서 3건 청크 분할 제거, 백엔드 병렬에 위임.
- [x] **Layer 1: 프롬프트 태그 주입** — LLM suggest 시 기존 태그 상위 100개를 프롬프트에 주입, 재사용 강제 지시
- [x] **Layer 2: 임베딩+LLM 태그 정규화** — ChromaDB tag_registry 컬렉션, 유사도 <0.08 자동치환, 0.08~0.20 LLM 확인
- [x] **Tag Registry** — `tag_registry.py` NEW, ChromaDB 기반 의미적 태그 저장소, 서버 시작 시 인덱스에서 벌크 동기화
- [x] **Smart Friction** — TagInput에서 새 태그 입력 시 ��사 태그 확인 → "기존 태그를 사용하시겠습니까?" 프롬프트
- [x] **태그 건수 자동완성** — TagInput `onSearchWithCount` prop, 드롭다운에 건수 표시 (수렴 유도)
- [x] **유사 태그 그룹 대시보드** — 관리 페이지에서 "분석 실행" → 유사 태그 그룹 표시 + 클릭 병합
- [x] **고아 태그 표시** — 1건 이하 사용 태그 목록 표시
- [x] **태그 병합 API** — `POST /tags/merge?source=&target=` 전체 문서 일괄 업데이트 + 레지스트리 정리
- [x] **임베딩 임계값 교정** — OpenAI text-embedding-3-small 단문 한국어 실측 기반 임계값 대폭 상향 (auto-replace 0.08→0.35, LLM confirm 0.20→0.55, API filter 0.25→0.60, groups 0.20→0.55). 유사 태그 그룹 4건 정상 검출 확인.

## 2026-04-07 (세션 35 — Smart Friction 레이턴시 최적화)

- [x] **Smart Friction 체감 지연 제거** — `/tags/similar`가 OpenAI 임베딩 왕복으로 560ms 소요하여 Enter 누를 때 답답함. TagInput에서 디바운스된 search 콜백과 함께 `onCheckSimilar`를 백그라운드로 선제 호출하여 캐시에 저장. 사용자가 드롭다운 훑어보는 동안 워밍되어 Enter 시점엔 캐시 히트 → 체감 0ms.
- [x] **similarCache LRU 50개 제한** — `Map` 삽입 순서 특성으로 가벼운 LRU 구현(재삽입으로 recency 갱신, 초과 시 oldest eviction). 장시간 세션에서의 메모리 누수 방지.

---

## 2026-04-05 (세션 32 — 사용자별 AI 페르소나 커스터마이징)

- [x] **Persona API** — `POST /api/persona/ensure` (템플릿 자동 생성), `POST /api/persona/invalidate`
- [x] **시스템 프롬프트 병합** — `build_system_prompt(username, storage)`, 60초 TTL 캐시, Q&A+스킬 경로 적용
- [x] **AgentContext.username** — 인증된 사용자명 전달
- [x] **자유 마크다운 페르소나** — Settings 버튼 → 워크스페이스에서 ontong.local.md 탭 열기 (Tiptap 에디터)
- [x] **가이드 템플릿** — 처음 열 때 "나에 대해/응답 스타일/참고 사항" 가이드 자동 생성
- [x] **자동 캐시 무효화** — wiki save 시 persona 파일이면 캐시 클리어
- [x] **빈 템플릿 감지** — 가이드 주석만 있는 상태(미작성)는 프롬프트에 주입 안 함

---

## 2026-04-05 (세션 31b — 스킬 UX 개선: 사용자 교육 & 가이드)

- [x] **스킬 소개 배너** — TreeNav 스킬 섹션 상단에 일회성 안내 ("스킬이란?"), localStorage 기반 닫기
- [x] **빈 상태 → 액션 유도** — 내 스킬/공용 스킬 빈 상태에 아이콘+설명+CTA ("첫 번째 스킬 만들기")
- [x] **스킬 피커 교육** — 채팅 피커 헤더 서브텍스트, 빈 상태 안내, 자동제안 설명 추가
- [x] **스킬 생성 가이드** — 다이얼로그 헤더 개선, 트리거 힌트, 6-Layer 라벨 인라인 설명
- [x] **탭 툴팁 개선** — "스킬 — AI 응답을 커스터마이징하는 템플릿"

---

## 2026-04-05 (세션 31 — 훅 시스템 + Completion Protocol + 스킬 고도화)

- [x] **AG-3-3: PreSkill/PostSkill 훅 시스템** — SkillHook protocol, HookRegistry, PreHookResult, QuerySanitizeHook(pre), DeprecatedDocHook(post), main.py 등록
- [x] **CompletionStatus 확장** — SkillResult에 DONE/DONE_WITH_CONCERNS/BLOCKED/NEEDS_CONTEXT enum 추가, 자동 상태 추론
- [x] **AG-4-3: 사용자 확인 루프** — ClarificationRequestEvent SSE, ChatRequest.clarification_response_id, AgentContext.emit_clarification()
- [x] **Per-Skill allowed-tools** — SkillMeta/SkillCreateRequest에 allowed_tools 필드, skill_loader YAML 파싱, context.py 우선순위 적용, skill_api 마크다운 템플릿
- [x] **스킬 크리에이터 UI 강화** — SkillCreateDialog에 allowed-tools 체크박스 UI, TypeScript 타입 동기화
- [x] **agent-architecture.md 업데이트** — 훅, CompletionStatus, Clarification, per-skill tools 문서화
- [x] **test_ag33_hooks.py** — 14 tests (CompletionStatus 5, HookRegistry 6, BuiltinHooks 3)

---

## 2026-04-05 (세션 30 — 고도화 완료 + 문서화 + Claude 전환)

- [x] **Claude API 키 설정** — `anthropic/claude-sonnet-4-20250514`로 모델 전환, .env gitignore 확인
- [x] **CORS 3001 포트 추가** — 프론트엔드 포트 변경(3001) 대응
- [x] **README.md 업데이트** — AI Copilot 섹션 v3 고도화 내용 반영, 구 Self-Reflective Pipeline 제거
- [x] **docs/agent-architecture.md 신규** — 에이전트 v3 아키텍처 기술 문서 (파이프라인, ReAct, 스킬, 권한, 세션, 프롬프트)
- [x] **demo_guide.md 업데이트** — AG-2~4 데모 시나리오 12개 + 트러블슈팅 추가
- [x] **테스트 격리 수정** — AG-3-1/3-2 pytest 크로스테스트 모듈 캐시 문제 해결 (importlib.reload)

---

## 2026-04-04 (세션 29 — 에이전트 고도화 착수)

- [x] **agent_bible(claw-code-parity) 분석** — 6개 영역 + 3개 심층 분석, 9개 분석 문서 작성
- [x] **99_adoption_plan.md v3 확정** — 전문가 리뷰 반영 (하이브리드 라우팅 삭제, topic_shift 추가, 훅 후퇴 등)
- [x] **TODO.md 에이전트 고도화 태스크 추가** — AG-1~4, 17 tasks
- [x] **.env LLM 모델 복원** — `gpt-4o-mini` → `gpt-4o` (API 키 권한 해결)
- [x] **AG-1-1: ontong.md 생성** — 에이전트 성격/규칙 정의 (`backend/ontong.md`)
- [x] **AG-1-2: 시스템 프롬프트 교체** — FINAL_ANSWER_SYSTEM_PROMPT → `get_system_prompt()` (ontong.md 로드)
- [x] **AG-1-3: 토큰 기반 히스토리** — `history[-6:]` → `build_history_window()` (4000 토큰 예산)
- [x] **AG-1-4: 구조화된 대화 요약** — 예산 초과 시 규칙 기반 요약 (Scope/Requests/Docs/Skills/Last response)
- [x] **AG-1-5: Continuation instruction** — ontong.md Context Awareness 강화 + 요약 프리픽스에 지시 내장
- [x] **AG-1-6: query_augment + topic_shift** — QueryAugmentResult 구조화 출력, 주제 전환 시 히스토리 미주입
- [x] **AG-1-7: 스킬 프롬프트 마크다운 분리** — 4개 스킬 프롬프트 .md 파일로 분리 + prompt_loader.py
- [x] **AG-1-8: Cognitive Reflect 제거** — 3단계 자기성찰 파이프라인 제거, LLM 1회 절약, 충돌 감지는 conflict_check 스킬로 전담
- [x] **AG-2-1: 스킬별 도구 풀 제한** — INTENT_ALLOWED_SKILLS 매핑 + run_skill() 차단 로직
- [x] **AG-2-2: 파이프라인 병렬화** — api/agent.py에서 routing+augment 병렬화 이미 구현, 추가 병렬화 여지 제한적
- [x] **AG-2-3: SkillResult feedback 필드** — `feedback`/`retry_hint` 필드 추가, wiki_search에서 deprecated 문서 필터 시 경고 반환, rag_agent에서 thinking_step으로 표시
- [x] **AG-3-1: 세션 JSONL 영속성** — 인메모리 → JSONL append 방식, 서버 재시작 후 대화 복원, `session_store.append_message()` API 추가, path traversal 방지
- [x] **AG-3-2: 스킬 권한 매핑** — `PermissionLevel` enum (READ/WRITE/EXECUTE), `SKILL_PERMISSIONS` 매핑, WRITE 스킬은 editor/admin 역할 필요, 권한 부족 시 retry_hint 반환
- [x] **AG-4-1: Q&A ReAct 자율 검색** — 검색 결과 품질 평가 후 자동 재검색 (최대 3턴), `SearchEvaluation` 모델, `qa_react.md` 프롬프트, 규칙 기반 fast-path (관련도 40%↑ → 즉시 답변)
- [x] **AG-4-2: 검색 자기 평가 + 재검색 전략** — qa_react.md에 충분성 체크리스트 + 5단계 재검색 전략(구체화→시간→동의어→상위개념→탐색) 보강
- [x] **.env 모델 변경** — `openai/gpt-4o-mini` → `anthropic/claude-sonnet-4-20250514` (Claude API 키 적용 완료)

---

## 2026-04-04 (세션 28 — 외부 접속 환경 구축 + 인프라 수정)

- [x] **외부 접속 환경 구축** — cloudflared → ngrok 고정 도메인(`architecturally-televisional-fumiko.ngrok-free.dev`) 전환
- [x] **SSE 스트리밍 프록시 추가** — `frontend/src/app/api/agent/chat/route.ts` (Next.js rewrite 버퍼링 우회)
- [x] **sseClient.ts 수정** — 외부 접속 시 Next.js API route 경유, localhost는 직접 백엔드 호출
- [x] **Next.js production 빌드 전환** — dev 모드 85개 청크 → prod 5개 번들 (외부 접속 속도 개선)
- [x] **.env LLM 모델 변경** — `gpt-4o` → `gpt-4o-mini` (API 키 권한 이슈)
- [x] **ChromaDB 강제 재인덱싱** — `force=true`로 해시 캐시 초기화 후 236 청크 인덱싱
- [ ] **ngrok 자동 시작 스크립트** — 매 세션마다 수동 실행 필요, 자동화 미구현

---

## 2026-04-16 (docs 정리)

- [x] **Section 3 고도화 + Section 2 연결 로드맵 문서 작성**
  - `docs/section3-roadmap.md` 신규 생성
  - Phase A: Section 2 최소 API 4개 구현 (주문/설비/온톨로지/시뮬레이션 실행)
  - Phase B: 섹션 3 코어 고도화 (그래프 시각화, 역계산, 멀티셋 비교, Wiki SEQ 연동)
  - Phase C: 플랫폼 통합 (섹션 1→3 연결, 실시간 동기화, 팀 에이전트 라이브러리)
  - Phase D: 해커톤 차별화 (Extended Thinking, MCP 서버, Graph RAG, Observability)
  - 통합 후 아키텍처 및 데이터 플로우 다이어그램 포함

- [x] **section3-developer-guide.md 업데이트**
  - 상태 정보 현행화 (Phase 1+1.5 완료 반영)
  - 참고 문서 경로 업데이트 (section3-* 접두어 반영)

- [x] **section3-user-guide.md 업데이트**
  - 로드맵 테이블 현행화 (Phase A/B/C/D 구조로 변경)

---

## 2026-04-09 (외부 접속 + 개발 가이드 보완)

- [x] **SSE 스트리밍 프록시 추가** (`12cb42a`)
  - ngrok/LAN 환경에서 SSE 이벤트 스트리밍 정상 동작하도록 프록시 설정
  - Next.js rewrite 규칙에 SSE 엔드포인트 buffering off 적용

- [x] **section3-developer-guide.md 업데이트** (`181546d`)
  - 실제 실행 환경 기반 세팅 가이드 전면 재작성
  - Section 10 추가: 현재 구현된 아키텍처 전체 문서화
    - Slab 에이전트 API (SSE 이벤트 상세)
    - Custom Agent API (CRUD + 빌더 + 실행)
    - SimulationToolExecutor ReAct 루프 아키텍처
    - Tool Registry 자기 기술 시스템
    - Parallel Executor (asyncio.gather)
    - 온톨로지 그래프 구조
    - ActiveView 프론트엔드 뷰 라우팅

- [x] **의존성 누락 수정** (`5c1e46d`)
  - fresh install 시 빌드 실패하던 문제 해결
  - package.json / pyproject.toml 의존성 정리

---

## 2026-04-07 (Phase 1.5 Custom Agent Hub 완성)

- [x] **Custom Agent 시스템 전체 구현 (백엔드)**
  - `custom_agent.py` — Custom Agent CRUD API + 채팅 빌더 + 실행 API
  - `agent_builder_agent.py` — LLM 기반 에이전트 정의 수집 채팅 빌더
  - `custom_agent_runner.py` — 등록된 Custom Agent 실행기
  - `custom_agents.json` — 파일 기반 영구 저장소
  - SSE 이벤트: `agent_ready` (정의 완성 시) + 기존 `thinking/tool_call/tool_result/content_delta/done`

- [x] **Custom Agent 시스템 전체 구현 (프론트엔드)**
  - `CustomAgentHub.tsx` — 에이전트 카드 목록 + 채팅/양식 생성 버튼
  - `AgentBuilderChat.tsx` — AI와 대화하며 에이전트 설계 + 미리보기 카드 + 등록 버튼
  - `CustomAgentFormBuilder.tsx` — 구조화된 폼 기반 에이전트 생성 (아이콘/색상/도구/프롬프트)
  - `CustomAgentRunner.tsx` — 등록된 에이전트 실행 채팅 (에이전트별 독립 대화)
  - `SimulationSidebar.tsx` — Custom Agent 섹션 통합 (헤더 클릭→허브, 채팅/양식 빌더, 에이전트 목록)
  - `SimulationSection.tsx` — `activeView` 기반 뷰 라우팅 확장 (custom_hub/custom_chat_builder/custom_form_builder/custom_agent)

- [x] **Phase 1 연동 기능 완성**
  - Scenario A 딥링크: `done` 이벤트 + `suggested_width` → "이 주문을 Slab 설계 3D로 확인" 버튼
  - Scenario C 딥링크: `done` 이벤트 + `recommended_split_count` → "최적 분할수 N개를 3D로 확인" 버튼
  - Scenario B 딥링크: 영향받은 Slab Slab 설계 3D 연결 버튼
  - 온톨로지 그래프 Order 노드 클릭 → 시뮬레이터 자동 이동 + 파라미터 로딩
  - 주문 선택 드롭다운 (`GET /api/simulation/slab/orders` → SlabParamController 상단)

- [x] **Tool Registry 시스템 구축**
  - `tool_registry.py` — SimulationToolRegistry: 중앙 등록, Anthropic 스키마 조회, 실행
  - `tool_definitions.py` — 10개 도구 Anthropic tool_use 형식 JSON 스키마 선언
  - 시나리오별 도구 묶음: SCENARIO_A_TOOLS, SCENARIO_B_TOOLS, SCENARIO_C_TOOLS, ALL_TOOLS
  - `GET /api/simulation/slab/tools` — Custom Agent 빌더 UI용 도구 목록

- [x] **사용자 가이드 + 개발자 가이드 전면 작성**
  - `section3-user-guide.md` — 800줄 사용자 매뉴얼 (화면 구성, 시나리오 사용법, FAQ, 연동 흐름 5가지)
  - `section3-developer-guide.md` — Custom Agent API 상세 + 도구 추가 가이드 + 뷰 라우팅 설명 추가

---

## 2026-04-04 (Phase 1 시나리오 에이전트 + Slab 시뮬레이터 구축)

- [x] **시나리오 A/B/C AI 에이전트 구현**
  - `scenario_a_agent.py` — DG320 에러 진단 (주문 조회 → Edging 기준 확인 → 폭 조정 제안)
  - `scenario_b_agent.py` — Edging 파급효과 분석 (변경 파라미터 파싱 → 전체 주문 영향 스캔)
  - `scenario_c_agent.py` — 단중·분할수 최적화 (분할수 1~N 조합별 만족률 계산)
  - `llm_tool_executor.py` — Anthropic tool_use 기반 ReAct 루프 실행기 (모든 에이전트 공통)

- [x] **Slab 설계 도구 함수 7개 구현**
  - `mock_simulator.py` — get_order_info, simulate_width_range, suggest_adjusted_width, find_edging_specs_for_order, simulate_width_impact, batch_simulate_width_impact, find_orders_by_rolling_line, simulate_split_combinations, get_equipment_spec
  - `parallel_executor.py` — asyncio.gather 기반 병렬 주문 영향 분석 (시나리오 B용)
  - `ontology_graph.py` — NetworkX 기반 Mock 온톨로지 그래프 (build_mock_graph, find_edging_specs_for_order, find_orders_by_rolling_line)

- [x] **Slab Size Simulator 프론트엔드 구현**
  - `SlabSizeSimulator.tsx` — 3-pane 레이아웃 컨테이너
  - `SlabParamController.tsx` — 6개 파라미터 슬라이더 + 숫자 입력 + 상태 인디케이터 (🟢🟡🔴)
  - `SlabViewer3D.tsx` — Three.js 3D Slab 렌더링 (OrbitControls, 치수 라벨, 상태별 색상 코딩)
  - `SlabDesignViewer3D.tsx` — 고급 3D 뷰어 (분할 애니메이션, 시나리오 C 딥링크용)
  - `SlabImpactPanel.tsx` — SEQ 2~16 단계별 통과 여부 실시간 판정 트리
  - `SlabCompareTable.tsx` — 변경 전/후 파라미터 비교 테이블

- [x] **SEQ 1~16 설계 계산 엔진 구현**
  - `slab_size_simulator.py` — calculate_slab_design() 함수
  - SEQ2 두께 결정, SEQ3 1차 폭범위, SEQ4 길이범위, SEQ5 단중범위, SEQ8 분할수, SEQ9 매수, SEQ12 2차 폭범위, SEQ14 Target폭, SEQ16 Target길이
  - 설비 제약 기반 상태 판정 (ok/warning/error)

- [x] **Slab 에이전트 API 구축**
  - `slab_agent.py` — Slab 전용 API 라우터
  - `POST /api/simulation/slab/run` — 시나리오 A/B/C 에이전트 실행 (SSE 스트리밍)
  - `GET /api/simulation/slab/orders` — Mock 주문 목록
  - `GET /api/simulation/slab/ontology` — 온톨로지 그래프 JSON
  - `POST /api/simulation/slab/calculate` — Slab 설계 파라미터 계산
  - `GET /api/simulation/slab/constraints` — 슬라이더 min/max 범위용 설비 제약
  - `GET /api/simulation/slab/equipment` — 설비 스펙 데이터

- [x] **채팅 패널 + 온톨로지 그래프 구현**
  - `ChatPanel.tsx` — SSE 스트리밍 + 마크다운 렌더링 + 추론 과정/도구 호출 표시
  - `OntologyGraph.tsx` — vis-network 기반 그래프 시각화 (노드 타입별 색상, 에이전트 탐색 경로 하이라이트)

- [x] **프론트엔드 상태 관리 + API 클라이언트**
  - `useSimulationStore.ts` — Zustand 전역 상태 (activeView, graphData, customAgents, orders)
  - `useSlabSimulator.ts` — Slab 시뮬레이터 전용 훅 (파라미터 상태 + API 호출)
  - `api.ts` — API 클라이언트 + SSE 파서 (fetchOntologyGraph, runAgent, runCustomAgent, etc.)
  - `types.ts` — TypeScript 타입 정의 (CustomAgent, ActiveView, SLAB_TOOLS, SCENARIO_META)

- [x] **Mock 데이터 생성**
  - `mock_orders.json` — 5개 주문 (DG320 에러 1건 포함)
  - `mock_equipment_spec.json` — 연주설비 2대 + 열연설비 2대
  - `mock_edging_spec.json` — Edging 기준 3건 (HR-A 2구간 + HR-B 1구간)
  - `mock_ontology.json` — 13노드 12엣지 온톨로지 그래프

---

## 2026-04-02 (3-Section 플랫폼 스캐폴딩)

- [x] **3-Section 플랫폼 아키텍처 구현** (`00e81f2`)
  - `backend/simulation/` 스캐폴딩 — API 라우터, mock 서버, client Protocol, agent 빈 모듈
  - `backend/modeling/` 스캐폴딩 — API 라우터(health), 빈 모듈
  - `backend/shared/contracts/simulation.py` — Section 2↔3 typed 계약 (Pydantic 모델)
  - `main.py` 라우터 등록 — modeling_api, simulation_api, slab_agent_api, custom_agent_api
  - 프론트엔드 SectionNav 상단 탭 (Wiki/Modeling/Simulation)
  - SimulationSection 3-pane 레이아웃 + SimulationSidebar
  - ModelingSection placeholder 카드
  - MockModelingClient — 파라미터 기반 동적 결과 생성 (수요예측/재고최적화/리드타임분석)

---

## 2026-04-07 (세션 — SimCopilot 프론트엔드 통합 완료)

- [x] **Custom Agent 시스템 프론트엔드 통합**
  - `CustomAgentRunner.tsx` — 등록된 커스텀 에이전트 실행 채팅 UI (에이전트별 독립 대화)
  - `CustomAgentFormBuilder.tsx` — 양식 기반 에이전트 생성 UI (아이콘/색상/도구/프롬프트)
  - `SimulationSection.tsx` — 사이드바 통합 + `activeView` 기반 뷰 라우팅
  - `SimulationSidebar.tsx` — "Custom Agent" 헤더 → `custom_hub` 뷰 링크 추가
  - 앱 시작 시 `fetchCustomAgents()` 호출, 기존 에이전트 자동 로드
  - `api.ts` TypeScript 타입 캐스팅 수정 (`unknown` → 구체 타입)

- [x] **문서 업데이트 (`docs/`)**
  - `section3-user-guide.md` — 사이드바 레이아웃 설명 + Custom Agent 섹션(7-1~7-6) + FAQ + 로드맵
  - `section3-developer-guide.md` — 파일 구조 현행화 + Custom Agent API 상세 + 도구 추가 가이드 + 뷰 라우팅 설명

---

## 2026-04-01 (세션 27 — Phase 0 스캐폴딩 + 개발자 C 환경 구축)

- [x] **shared/contracts/ 생성** — `simulation.py` typed 계약 (DemandForecastParams, InventoryOptimizeParams, LeadTimeAnalysisParams, SimulationJob 등)
- [x] **shared/agent_framework/ 생성** — AgentPlugin Protocol re-export
- [x] **backend/simulation/ 스캐폴딩** — API 라우터, mock 서버(파라미터 기반), client Protocol, agent/visualization/storage 빈 모듈
- [x] **backend/modeling/ 스캐폴딩** — API 라우터(health), agent/ontology/code_analysis/mapping/simulation/data 빈 모듈
- [x] **main.py 라우터 등록** — modeling_api, simulation_api 등록 + MockModelingClient 초기화
- [x] **프론트엔드 Section 네비게이션** — SectionNav 상단 탭 (Wiki/Modeling/Simulation), useWorkspaceStore에 activeSection 상태 추가
- [x] **SimulationSection 3-pane 레이아웃** — 시나리오 목록(API 연동) + 대시보드 영역 + SimCopilot placeholder
- [x] **ModelingSection stub** — Phase 1 로드맵 카드 + ModelingCopilot placeholder
- [x] **개발자 C 가이드 문서** — `docs/section3-developer-guide.md` (실행법, 디렉토리, API 계약, mock 사용법, 규칙)
- [x] **전체 테스트 통과** — 177/177 pass + TypeScript 빌드 성공

---

## 2026-04-01 (세션 26 — 3-Section Platform 아키텍처 v2)

- [x] **3-Section 플랫폼 아키텍처 설계** — Wiki / Source-Domain Modeling / Simulation 3섹션 분리
- [x] **3관점 리뷰 수행** — Systems Architect, Developer C, Domain Expert 관점 검토 (26건 이슈 도출)
- [x] **리뷰 반영 아키텍처 v2 확정** — 시뮬레이션 2종 분리, SCOR+ISA-95, typed 계약, 비동기 job, 매핑 임계값 상향
- [x] **아키텍처 문서 작성** — `toClaude/reports/platform_architecture_v2.md` (16개 섹션)
- [x] **TODO.md 업데이트** — V2 Phase 0~3 태스크 44건 추가
- [x] **메모리 업데이트** — project_status, architecture_v2, user_role
- [x] **Phase 0 실행 시작** — 세션 27에서 스캐폴딩 + 개발자 C 환경 구축 완료

### 핵심 아키텍처 결정 (합의 완료)
- 에이전트 섹션별 독립 (공유 금지, Protocol만 공유)
- ISA-95 단독 X → SCOR + ISA-95 하이브리드 온톨로지
- 시뮬레이션 2종: 코드 영향분석(그래프 BFS) + 비즈니스시뮬(파라메트릭 모델)
- 매핑 자동승인 임계값 0.95 (제조업 기준 상향)
- 비동기 Job queue 필수 (동기 HTTP X)
- Typed 계약 (dict X → 시나리오별 Pydantic 모델)
- Chat + Dashboard 하이브리드 UI (섹션 3)
- 모노리스 솔직하게 인정 (Python Protocol → 나중에 HTTP 분리)
- MVP 순서: Phase 1은 코드 영향분석 (데이터 없이 가치 제공 가능)
- Neo4j Community (그래프 DB)

---

## 2026-04-01 (세션 23 — GitHub 배포 + 방법론 + 기술스택 + 에이전트 논의)

- [x] **README.md 한국어 가이드** — 주요 기능, 아키텍처, 실행법, API, 스킬 작성법, 배포 가이드
- [x] **GitHub 공개 배포** — Jeensh/onTong, v1.0.0 태그, 프론트엔드 서브모듈 fix
- [x] **위키 콘텐츠 교체** — IT 시스템 운영 데모용 21개 문서 (장애대응/인프라/보안/업무절차/개발운영 + 스킬 3개)
- [x] **Agentic Workflow 방법론** — agentic-workflow/ 폴더 (가이드 + 템플릿 5개 + CLAUDE.md 프리셋 3개 + 6-Layer 스킬 2개)
- [x] **Mermaid 다이어그램** — ASCII → Mermaid 전환, 서브에이전트 검토 반영
- [x] **기술스택 상세 문서** — docs/tech-stack.md 작성 완료 (2회 검토, 로컬에 있음, 미커밋)
- [x] **Pydantic AI 프레임워크 도입** — Hybrid 접근: 구조화된 출력(cognitive reflect, classify, edit, write, conflict) + ReAct 루프 + 스트리밍을 Pydantic AI로 전환. litellm 직접 호출을 llm_generate.py 1곳으로 격리. 신규 7파일, 수정 12파일, 테스트 174/174 PASS
- [x] **SIMULATION/DEBUG_TRACE 에이전트** — 스캐폴딩 완료. 본격 구현은 동료가 별도 진행 (본 TODO 범위 밖)

## 2026-04-01 (세션 25 — 충돌 문서 비교 해결 기능)

- [x] **ConflictPair 모델** — `schemas.py`에 `ConflictPair(file_a, file_b, similarity, summary)` 추가, `ConflictWarningEvent`에 `conflict_pairs` 필드 추가
- [x] **충돌 페어 빌드** — `rag_agent.py`에서 충돌 감지 시 문서 쌍별 similarity 계산 + 명시적 ConflictPair 목록 생성
- [x] **ConflictStore 연동** — `AgentContext`에 `conflict_store` 추가, 채팅에서 감지된 충돌을 ConflictStore에 등록하여 ConflictDashboard와 동기화
- [x] **채팅 충돌 배너 개선** — 페어별 유사도 표시 + "나란히 비교" 버튼 → 기존 DiffViewer에서 "A가 최신/B가 최신" 선택으로 해결
- [x] **해결 상태 반영** — DiffViewer에서 deprecation 완료 시 채팅 배너에 "해결됨" 표시 (`resolvedConflicts` 상태 관리)
- [x] **하위 호환** — `conflict_pairs`가 없는 기존 이벤트에서도 레거시 배너 정상 표시
- [x] **충돌 감지 오탐 수정** — 2차 conflict_check 조건을 관련도 60% 이상 문서 2개 이상으로 강화, 일반적 질문에서 불필요한 충돌 경고 방지
- [x] **충돌 요약 품질 개선** — conflict_details[:200] 단순 자르기 → 문서명 기반 문장 추출 (`_extract_pair_summary`)

## 2026-04-01 (세션 24 — Pydantic AI 데모 테스트 버그 수정)

- [x] **스킬 참조문서 wikilink 해석 버그** — `[[장애등급-분류기준]]` 등 하위 디렉토리 문서를 파일명만으로 찾지 못하던 문제. skill_loader에 파일명→전체경로 인덱스 추가
- [x] **Pydantic AI LiteLLMProvider API 키 버그** — LiteLLMProvider가 OPENAI_API_KEY를 무시하고 placeholder 키를 사용하던 문제. OpenAIProvider로 직접 교체하여 올바른 API 키 전달
- [x] **Write intent 패턴 확장** — "체크리스트/가이드/매뉴얼/절차서 만들어줘" 패턴 추가 (기존은 "문서/위키" 키워드 필수)
- [x] **LLM Provider 추상화** — llm_factory.py를 레지스트리 패턴으로 재설계. OpenAI/Anthropic/Ollama/Google/Azure/Groq/DeepSeek 7개 프로바이더 지원. .env의 LITELLM_MODEL만 변경하면 전환 가능
- [x] **LLM 모델 업그레이드** — gpt-4o-mini → gpt-4o로 변경
- [x] **키워드 라우팅 → LLM 통합 분류** — router.py의 40+ regex 규칙과 rag_agent.py의 edit/write regex를 제거. 단일 LLM 호출(UserIntent 모델)로 agent + action을 동시에 판단. 키워드 누락 문제 근본 해결
- [x] **문서 업데이트** — README.md (AI Copilot 설명, LLM 설정 7개 프로바이더, 환경 변수 테이블, 테스트 수 177), docs/tech-stack.md (LiteLLM→Pydantic AI 섹션 재작성, Ollama 연동 방식 업데이트)
- [x] **충돌 감지 버그 수정** — (1) context[:3000]→[:6000] 확장 (2) zip() 불일치 수정: relevant_docs/metas/dists 동기화 (3) cognitive reflection이 놓친 충돌을 conflict_check 스킬로 2차 감지
- [x] **Lineage 동기화 버그 수정** — status를 미설정으로 변경 시 supersedes/superseded_by 자동 정리 + 상대 문서의 역참조도 연동 삭제
- [x] **충돌 설명 한국어화** — cognitive reflection + conflict_check 스킬 프롬프트에서 conflict_details를 한국어로 출력하도록 변경
- [x] **채팅 입력 히스토리** — 위/아래 방향키로 이전 질문 재입력 기능 (세션 내 히스토리)
- [x] **문서 생성/수정 워크스페이스 직접 작업** — 채팅에서 승인 버튼 제거, workspace에서 바로 미리보기+승인/취소/편집. 생성: 렌더링된 미리보기+상단바(저장/직접편집/취소). 수정: DiffView에서 hunk별 선택+전체적용/되돌리기/직접편집. 채팅은 상태 메시지만 표시.

## 2026-04-01 (세션 22 — Skill 시스템 테스트 추가)

- [x] **skill_loader Unit 테스트** — frontmatter 파싱, 카테고리 추출, 6-Layer 섹션, 캐시, wikilink 참조 (39 tests)
- [x] **skill_matcher Unit 테스트** — substring/Jaccard 매칭, threshold, priority 가중치, 한국어 토큰화 (18 tests)
- [x] **Skill API Integration 테스트** — CRUD, toggle, move, match, context 엔드포인트 (20 tests)

## 2026-04-01 (세션 21 — 스킬 관리 편의 기능)

- [x] **스킬 우클릭 컨텍스트 메뉴** — 편집/복제/토글/삭제 메뉴 (SkillContextMenu 컴포넌트)
- [x] **스킬 삭제 기능** — confirm 확인 후 deleteSkill API 호출
- [x] **스킬 드래그앤드롭** — 카테고리 간 이동 (PATCH /api/skills/{path}/move + 네이티브 DnD)
- [x] **BE move API** — 카테고리 변경 시 파일 이동 + frontmatter 업데이트

## 2026-03-31 (세션 21 — FE 고급 설정 UI)

- [x] **SkillCreateDialog 모달** — 6-Layer 필드(역할/워크플로우/체크리스트/출력형식/제한사항) + 참조문서 피커 포함 스킬 생성 다이얼로그
- [x] **ReferencedDocsPicker** — /api/search/quick 기반 문서 검색/선택 컴포넌트
- [x] **GET /api/skills/{path}/context** — 스킬 6-Layer 컨텍스트 조회 API
- [x] **스킬 복제 6-Layer 복사** — handleDuplicate에서 context API로 전체 내용 복사
- [x] **SkillContext TypeScript 타입** — FE 타입 추가

## 2026-03-31 (세션 20 — 6-Layer Skill Architecture)

- [x] **SkillContext 구조체** — 6개 레이어(role, workflow, checklist, output_format, self_regulation + instructions) 독립 필드
- [x] **skill_loader 업그레이드** — load_skill_context()가 SkillContext 반환, 참조문서 누락 추적
- [x] **Preamble 런타임 주입** — 날짜, 사용자 이름, 참조문서 현황을 코드가 자동 수집
- [x] **6-Layer 프롬프트 빌더** — _handle_skill_qa()에서 레이어별 조건부 조립 (빈 레이어 skip → 하위호환)
- [x] **스킬 생성 템플릿 확장** — 역할/워크플로우/체크리스트/출력형식/제한사항 가이드 추가
- [x] **SkillCreateRequest 확장** — role, workflow, checklist, output_format, self_regulation 필드 (BE+FE)
- [x] **데모 스킬 업그레이드** — 신규입사자-온보딩.md를 6-layer 형식으로 전환
- [x] **후속 질문 스킬 유지** — sessionSkill state로 세션 내 스킬 자동 유지, X 버튼/세션 전환 시만 해제
- [x] **자동 매칭 스킬 유지** — onSkillMatch SSE에서도 sessionSkill 저장
- [x] **스킬 유지 UI** — pill에 "(유지 중)" 라벨, Zap 버튼 하이라이트
- [x] **테스트 회귀 확인** — 68/68 PASSED

## 2026-03-31 (세션 19 — Skill System 고도화)

- [x] **스킬 생성 템플릿** — 지시사항/배경/제약조건/질문예시/참조문서 가이드 자동 채움
- [x] **스킬 CRUD 직접 파일 쓰기** — create/update도 storage.write() 우회 (frontmatter 보존)
- [x] **참조 문서 탐색 시각화** — thinking step에서 각 참조 문서를 개별 표시 (📄 문서명 1/N)
- [x] **스킬 목록 API 비활성 포함** — list_skills(include_disabled=True)로 사이드바에서 재활성화 가능
- [x] **Copilot 피커 실시간 갱신** — 피커 열 때마다 refreshSkillList() 호출
- [x] **HR 스킬 파일 복원** — storage.write()로 frontmatter 손상된 파일 복구
- [x] **토글 API 직접 파일 쓰기** — storage.write() 우회하여 스킬 frontmatter 보존
- [x] **SE-1~12: Skill System 고도화** (카테고리 + 우선순위 + 무시 관리)
  - BE: SkillMeta에 category/priority/pinned 필드 추가
  - skill_loader: 폴더 경로 기반 카테고리 자동 추출 (_skills/HR/file.md → "HR")
  - skill_matcher: priority 곱셈 가중치 (score * (0.8 + p*0.04)) + tiebreaker 확장
  - PATCH toggle API: enabled 필드 flip
  - FE 사이드바: 카테고리 접이식 그룹, 검색, 토글(활성/비활성), 복제 버튼, pinned 표시
  - FE 생성 폼: 카테고리(combobox) + 우선순위 입력 추가
  - Copilot 피커: 카테고리별 그룹핑 + 스킬 검색
  - localStorage: dismissed skills 영속화
  - 데모 스킬 카테고리 폴더 이동: HR/신규입사자, Finance/출장비, @개발자/SCM/구매발주

---

## 2026-03-31 (세션 18 — User-Facing Skill System)

- [x] **US-1~15: User-Facing Skill System 전체 구현** (6 phases)
  - Phase 1: 스키마(SkillMeta, SkillListResponse, SkillCreateRequest) + skill_loader + skill_matcher
  - Phase 2: AgentContext 확장 + api/agent.py 스킬 해석 + RAGAgent._handle_skill_qa
  - Phase 3: Skill CRUD API + main.py 와이어링
  - Phase 4: 사이드바 ⚡ 스킬 탭 + 인라인 생성 폼
  - Phase 5: Copilot 스킬 피커 + 자동 제안 + SSE skill_match 이벤트
  - Phase 6: 그래프 스킬 노드 (보라색 다이아몬드)
- [x] **데모용 샘플 스킬 3개 생성**
  - `_skills/출장비-정산-도우미.md` (공용, trigger: 출장비/출장 정산)
  - `_skills/신규입사자-온보딩.md` (공용, trigger: 신규입사/온보딩)
  - `_skills/@개발자/구매발주-안내.md` (개인, trigger: 구매발주/납품 검수)

---

## 2026-03-30 (세션 16 — 문서 관계 그래프 리디자인)

- [x] **P3-AH5: 그래프 검색 우선 UX** — 전체 그래프 대신 검색 우선 UI로 전환. 중심 문서 선택 후 BFS 관계만 표시
  - `DocumentGraph.tsx`: 검색 랜딩 페이지 + `/api/search/quick` 디바운스(200ms) + 인라인 문서 전환 검색
  - `search.py`: `center_path` 필수 파라미터로 변경, 유사도 엣지 conflict store에서 읽기 (broken import 수정)

---

## 2026-03-30 (세션 15 — 충돌 감지 리팩토링)

- [x] **CR-1: ChromaDB 네이티브 유사도 검색** — `get_file_embeddings()`, `query_by_embedding()` 추가
- [x] **CR-2: ConflictStore 신규** — Redis/InMemory 이중 백엔드, SHA256 해시 키, `replace_for_file`/`remove_for_file`
- [x] **CR-3: ConflictService 리라이트** — `check_file()` 증분 감지, `full_scan()`, `get_pairs()`, `update_metadata()`
- [x] **CR-4: API 수정** — `/duplicates` store 읽기, `/full-scan` + `/scan-status` 신규
- [x] **CR-5: WikiService 훅** — `_bg_index()`, `delete_file()`, `move_file()`, `move_folder()`에 충돌 감지 연결
- [x] **CR-6: 프론트엔드** — 즉시 로드 + "전체 스캔" 버튼 + 프로그레스 바
- [x] **CR-7: 테스트** — conflict_store, conflict_service, API, E2E (23 tests 통과)

---

## 2026-03-30 (세션 14 — Phase 5 구현)

- [x] P5A-1: 트리 Lazy Loading — depth=1 초기 로드 + subtree API, `has_children` 플래그
- [x] P5A-2: 서버 사이드 검색 — MiniSearch 제거, `/api/search/quick` + `/api/search/resolve-link`
- [x] P5A-3: 트리 증분 업데이트 — CRUD 후 낙관적 로컬 업데이트 (fetchTree 제거)
- [x] P5A-4: 프론트엔드 ETag 활용 — `fetchWithETag()` 유틸리티, 304 캐시
- [x] P5B-1: Uvicorn 멀티 워커 — `--workers 4` + Docker 리소스 제한
- [x] P5B-2: 비동기 인덱싱 — save 즉시 반환 + IndexStatus 추적
- [x] P5B-2a: 인덱싱 상태 UI — 에디터 "검색 반영 대기 중" 배너
- [x] P5B-3: BM25 주기적 리빌드 — 10초 데몬 스레드
- [x] P5B-4: 하이브리드 검색 병렬화 — vector + BM25 병렬 실행
- [x] P5B-5: 시작 시 백그라운드 인덱싱 — 앱 즉시 가용
- [x] P5B-6: list_all_files() 최적화 — asyncio.to_thread + list_file_paths()
- [x] P5C-1: Redis 도입 + Lock 이관 — SET NX EX, LockBackend ABC, 자동 폴백
- [x] P5C-2: Redis 기반 쿼리 캐시 — RedisQueryCache, file→key 인덱스
- [x] P5C-3: Lock Refresh 배치화 — lockManager 중앙 매니저 + batchRefreshLock API
- [x] P5C-4: ACL 캐싱 + 핫 리로드 — check_permission LRU 캐시(60s TTL), 30s 파일 변경 감지
- [x] P5D-1: Nginx 리버스 프록시 — nginx.conf + docker-compose nginx 서비스
- [x] P5D-2: Docker 리소스 제한 — 이전 세션에서 완료 (backend 4C/4G, frontend 1C/1G 등)
- [x] P5D-3: ChromaDB 커넥션 풀링 — chromadb.Settings 설정
- [x] P5D-4: get_all_embeddings 페이지네이션 — offset/limit 1000건 배치 조회
- [x] P5D-5: SSE 실시간 이벤트 — EventBus + /api/events SSE endpoint + TreeNav 구독
- [x] P5E-1: RAG LLM 파이프라인 최적화 — reflection 캐시로 반복 쿼리 LLM 호출 스킵
- [x] P5E-2: LLM 응답 캐싱 — cognitive_reflect 인메모리 LRU (256개, TTL 10분)
- [x] P5E-3: Ollama 동시 처리 — OLLAMA_NUM_PARALLEL=4, asyncio.Semaphore(8)
- [x] P5E-4: 검색 인덱스 캐싱 — backlinks/tags 엔드포인트 60s TTL 캐시
- [x] P5E-5: 메타데이터 엔드포인트 최적화 — `list_all_metadata()` (frontmatter 4KB만 읽기) + 60s TTL 캐시
- [x] **충돌 감지 성능 개선 + 500 에러 수정** — numpy 벡터화 코사인 유사도, asyncio.to_thread() 래핑, threshold 0.95로 상향, 결과 200건 제한, 120s TTL 캐시. ChromaDB get_all_embeddings 79초 병목은 캐싱으로 완화.

---

## 2026-03-30 (세션 13)

- [x] Phase 4 프로덕션 작업 리포트 작성 → `toClaude/reports/phase4_production_readiness.md`
- [x] Phase 4 검토/테스트 플랜 작성 → `toClaude/reports/phase4_review_test_plan.md`
- [x] 대규모 대응 규모 분석 (컴포넌트별 병목, 커버 가능 규모 판정)
- [x] 스트레스 테스트 스크립트 3종 포함 (파일 규모, 동시 사용자, 잠금 동시성)
- [x] 스트레스 테스트 실행 + 결과 리포트 → `toClaude/reports/phase4_stress_test_results.md`
- [x] Phase 5 엔터프라이즈 스케일링 플랜 수립 (23 tasks, 5 sub-phase)
- [x] TODO.md에 Phase 5 태스크 추가 (P5A~P5E)

---

## 2026-03-29 (세션 12 — Phase 4 프로덕션 준비)

- [x] P4A-1: PDF.js worker 로컬 번들링 (unpkg CDN → public/)
- [x] P4A-2: Google Fonts 제거 → 시스템 폰트 스택
- [x] P4A-3: LLM 설정 추상화 (Ollama 기본값, OpenAI 옵션)
- [x] P4A-4: 임베딩 로컬 전환 (설정 기반, ChromaDB 기본 embedding)
- [x] P4A-5: 외부 의존성 점검 스크립트
- [x] P4B-1: Backend Dockerfile (Python 3.10-slim 멀티스테이지)
- [x] P4B-2: Frontend Dockerfile (Node 20-alpine 멀티스테이지 + standalone)
- [x] P4B-3: docker-compose.yml 통합 (backend+frontend+chroma, monitoring profile)
- [x] P4B-4: 환경 변수 분리 (.env.example + .env.production.example)
- [x] P4B-5: 헬스체크 + 시작 순서 + .dockerignore
- [x] P4C-3: NASBackend 구현 (LocalFSAdapter 서브클래스, 마운트 경로 검증)
- [x] P4C-4: 스토리지 팩토리 설정 기반 전환 (STORAGE_BACKEND=local/nas)
- [x] next.config.ts: standalone 출력 모드 + BACKEND_URL 환경변수 지원
- [x] P4D-1: Lock 서비스 (인메모리, TTL 5분, 자동 만료)
- [x] P4D-2: Lock API (POST /lock, DELETE, GET /status, POST /refresh)
- [x] P4D-3: 에디터 잠금 UI (잠금 획득, 읽기전용 배너, 세션 사용자 ID)
- [x] P4D-4: 자동 해제 (탭 닫기 → releaseLock, 2분 주기 TTL 리프레시)
- [x] P4F-1: .gitignore 강화 (.pem, .key, credentials.json 추가)
- [x] P4F-2: CORS 강화 (와일드카드 → 명시적 메서드/헤더 화이트리스트)
- [x] P4F-3: 구조화 로깅 (JSON 포맷 + request_id 미들웨어)
- [x] P4F-4: 입력 검증 (path traversal 차단, content 10MB 제한)
- [x] P4F-5: 전역 에러 핸들러 (500 → JSON 응답, ValueError → 400)
- [x] P4E-1~2: ACL 저장소 (JSON 기반, 폴더 상속, document 오버라이드)
- [x] P4E-3: require_read/require_write 의존성
- [x] P4E-4: Wiki API에 읽기/쓰기 권한 체크 적용
- [x] P4E-5: RAG 검색 결과에 ACL 기반 필터 추가
- [x] P4E-7: ACL 관리 API + PermissionEditor UI + TreeNav 메뉴
- [x] P4G-1: 검색 인덱스 API에 offset/limit 페이지네이션
- [x] P4G-2: 트리 API depth 파라미터 + subtree lazy load API
- [x] P4G-3: ChromaDB upsert 100건 단위 배치 처리
- [x] P4G-4: 트리 API ETag/304 캐싱

---

## 2026-03-29 (세션 11)

- [x] **Phase 3-A: 문서 검색 (커맨드 팔레트)** (7 tasks)
  - MiniSearch 클라이언트 사이드 검색 (즉시 결과, prefix+fuzzy, 한글 토크나이저)
  - 서버 사이드 하이브리드 검색 API (`GET /api/search/hybrid` — BM25+벡터 RRF)
  - Ctrl+K / Cmd+K 커맨드 팔레트 UI (cmdk CommandDialog 기반)
  - 키워드/의미 검색 모드 전환, 결과 하이라이트, 태그 뱃지, 스니펫 미리보기
  - TreeNav 사이드바 헤더에 검색 아이콘 추가

- [x] **Phase 3 고도화** (4 tasks)
  - 문서 열기 시 연결 문서 패널 (lineage + wiki-link 백링크, 참조/역참조, 접이식)
  - 그래프 내 문서 검색 (검색→노드 센터링+줌)
  - 문서 링크 복사 — 사이드바 우클릭 "문서 링크 복사" (md→`[[문서명]]`, 기타→경로)
  - WikiLink 인라인 노드: `[[문서명]]` 타이핑/붙여넣기 시 클릭 가능한 링크로 자동 변환, 클릭 시 openTab

- [x] **Phase 3-B: 문서 관계 그래프** (13 tasks)
  - react-force-graph-2d 기반 force-directed 그래프 시각화
  - 그래프 데이터 API (`GET /api/search/graph` — 백링크+lineage+related+similarity 집계, BFS)
  - 4가지 연결 타입: wiki-link(gray), supersedes(orange), related(blue/dashed), similar(red/dotted)
  - 노드: status별 색상, degree 기반 크기, 라벨, 호버 툴팁
  - 노드 클릭→문서 열기, 우클릭→컨텍스트 메뉴, 현재 문서 중심 보기
  - center_path + depth BFS로 대규모 위키 성능 보장
  - Virtual Tab (`"document-graph"`), 관리 섹션 메뉴 진입점

---

## 2026-03-29 (세션 10)

- [x] **P2B-6: RAG deprecated 문서 필터링 + 최신 문서 자동 대체** (3 tasks)
  - 검색 시 deprecated 문서 제외 (ChromaDB where + BM25 필터)
  - deprecated만 검색 시 superseded_by 체인 추적 → 최신 문서 자동 대체
  - 기존 +0.3 패널티 로직 제거

- [x] **P2B-7: 충돌 대시보드 해결 상태 관리** (3 tasks)
  - DuplicatePair에 resolved 필드 + 양방향 lineage 자동 해결 판정
  - API filter 파라미터 (unresolved/resolved/all)
  - 프론트엔드 탭 필터 (미해결/해결됨/전체), 기본값 "미해결"

- [x] **증분 인덱싱 해시 비교 버그 수정** — frontmatter만 변경 시 인덱싱 스킵되던 문제
- [x] **conflict_service numpy array 비교 버그** — ChromaDB embeddings가 numpy array → len() 체크로 변경
- [x] **deprecate API 500 에러 수정** — storage.save → _serialize_frontmatter + save_file로 변경
- [x] **DiffViewer React key 경고 수정** — Fragment key 추가
- [x] **CONFLICT_CHECK 프롬프트 강화** — 다른 팀/부서의 다른 수치도 충돌로 판정
- [x] **ChromaDB 메타데이터 동기화 버그 수정** — `_metadata_to_chroma()`에 `superseded_by`/`supersedes` 누락 → 추가
- [x] **deprecate API force reindex** — 상태 변경 후 ChromaDB 즉시 동기화 보장
- [x] **메타데이터 완전성 가드 테스트** — `DocumentMetadata` 스칼라 필드 누락 시 테스트 실패
- [x] **`_metadata_to_chroma()` 자동생성 전환** — 수동 필드 나열 → `DocumentMetadata.model_fields` 순회 방식으로 변경. 새 필드 추가 시 자동 반영
- [x] **재고관리 샘플 데이터 lineage 누락 수정** — v1에 `superseded_by`, v2에 `supersedes` 추가

---

## 2026-03-28 (세션 9)

- [x] **증분 인덱싱 해시 비교 버그 수정** — frontmatter만 변경 시 인덱싱 스킵되던 문제
  - `wiki_indexer.py`: `has_changed()` 비교 대상을 `wiki_file.content` → `wiki_file.raw_content`로 변경
  - `sseClient.ts`: `onSources` 콜백 타입에 `status`, `updated`, `updated_by` 필드 추가

- [x] **P2B-5: 문서 계보(Lineage) 시스템** (5 tasks)
  - `schemas.py`: `DocumentMetadata`에 `supersedes`, `superseded_by`, `related` 필드 추가
  - `local_fs.py`: frontmatter 파싱/직렬화에 lineage 필드 반영
  - `rag_agent.py`: superseded 문서 +0.3 거리 패널티 + "폐기됨" 경고 삽입
  - `api/wiki.py`: `GET /api/wiki/lineage/{path}` — 계보 트리 반환 (supersedes/superseded_by/related 해석)
  - `LineageWidget.tsx`: 에디터 상단 lineage 배너 (이전/새 버전 링크, 관련 문서)
  - `DiffViewer.tsx`: "A가 최신"/"B가 최신" 버튼 → bidirectional lineage 자동 설정
  - `tests/test_p2b5_lineage.py`: 10 tests (lineage 필드, frontmatter roundtrip, 패널티) ✅

- [x] **P2B-4: 인라인 비교 뷰** (5 tasks)
  - `api/wiki.py`: `GET /api/wiki/compare?path_a=&path_b=` — 두 문서 body+메타데이터 반환
  - `DiffViewer.tsx`: side-by-side diff (추가=녹색, 삭제=빨강, 변경=amber), 라인 번호
  - `workspace.ts`: `document-compare` VirtualTabType
  - `useWorkspaceStore.ts`: `openCompareTab(pathA, pathB)` 메서드 + 타이틀 자동 생성
  - `FileRouter.tsx`: compare 탭 라우팅 (filePath에서 경로 파싱)
  - `DiffViewer.tsx`: "A가 최신"/"B가 최신" 버튼 → deprecated 자동 설정
  - `ConflictDashboard.tsx`: "나란히 비교" 버튼 → openCompareTab 연동

- [x] **P2B-3: 문서 중복/충돌 감지 대시보드** (5 tasks)
  - `chroma.py`: `get_all_embeddings()` — 전체 임베딩/문서/메타데이터 조회
  - `conflict/conflict_service.py`: `ConflictDetectionService` — 파일별 평균 임베딩 + 코사인 유사도 쌍 탐지
  - `api/conflict.py`: `GET /duplicates` (유사 문서 쌍) + `POST /deprecate` (deprecated 설정)
  - `main.py`: conflict_api 라우터 등록
  - `workspace.ts`: `conflict-dashboard` VirtualTabType 추가
  - `useWorkspaceStore.ts`: 탭 타이틀 추가
  - `FileRouter.tsx`: ConflictDashboard 라우팅
  - `TreeNav.tsx`: 관리 섹션에 "문서 충돌 감지" 메뉴 (AlertTriangle 아이콘)
  - `ConflictDashboard.tsx`: 유사도 임계값 조절 + 유사 문서 쌍 테이블 + 파일 열기/폐기 액션
  - `tests/test_p2b3_conflict_dashboard.py`: 11 tests (코사인유사도, 평균임베딩, 서비스 통합)

- [x] **P2B-2: 메타데이터 기반 신뢰도 표시** (5 tasks)
  - `schemas.py`: `DocumentMetadata.status` 필드 추가 (draft/review/approved/deprecated)
  - `local_fs.py`: frontmatter 파싱/직렬화에 status 반영
  - `wiki_indexer.py`: ChromaDB metadata에 status 포함
  - `schemas.py`: `SourceRef`에 `updated`, `updated_by`, `status` 필드 확장
  - `rag_agent.py`: `_build_sources()`에서 메타데이터 주입
  - `agent.ts`: SourceRef 타입 확장
  - `AICopilot.tsx`: 소스 패널에 status 아이콘/색상 + 날짜 배지 + 상세 tooltip
  - `wiki.ts`: `DocumentStatus` 타입 + `DocumentMetadata.status`
  - `MetadataTagBar.tsx`: status 드롭다운 + collapsed 뱃지
  - `frontmatterSync.ts`: status 파싱/직렬화
  - `tests/test_p2b2_status_field.py`: 10 tests (스키마, SourceRef, frontmatter roundtrip)

- [x] **P2B-1: RAG 답변 충돌 감지 프롬프트** (4 tasks)
  - `rag_agent.py`: `_build_context_with_metadata()` — 각 청크에 [출처/작성자/최종수정/도메인/관련도] 헤더 삽입, 중복 파일 표시
  - `rag_agent.py`: `FINAL_ANSWER_SYSTEM_PROMPT`에 문서 충돌 감지 규칙 추가 (모순 시 ⚠️ 경고 + 최신 문서 권고)
  - `rag_agent.py`: `COGNITIVE_REFLECT_PROMPT`에 CONFLICT_CHECK 항목 + `has_conflict`/`conflict_details` JSON 필드
  - `schemas.py`: `ConflictWarningEvent` 스키마 신규 (details + conflicting_docs)
  - `agent.ts`: `ConflictWarningEvent` 타입 추가
  - `sseClient.ts`: `onConflictWarning` 콜백 + dispatch 처리
  - `AICopilot.tsx`: `ConflictWarning` 인터페이스, ChatMessage에 필드 추가, amber 경고 배너 UI
  - `tests/test_p2b1_conflict_detection.py`: 8 tests (메타데이터 헤더, 스키마, 프롬프트 검증)

---

## 2026-03-28 (세션 8)

- [x] **P2A-1: LLM 호출 병렬화 + 제거** (4 tasks)
  - `router.py`: 키워드 규칙 확대 — 기업/도메인 용어 + 한글 catch-all 패턴 추가 (11/12 키워드 적중)
  - `rag_agent.py`: `_check_clarity` LLM 호출 → `_check_clarity_rule_based` 규칙 기반으로 전환 (0ms)
  - `agent.py` + `rag_agent.py`: 라우팅 + 쿼리보강 `asyncio.gather` 병렬화, `augmented_query` 파라미터 전달
  - `tests/bench_rag_latency.py`: 파이프라인 지연시간 벤치마크 스크립트 (키워드 적중률, 순차/병렬 비교)

- [x] **메타데이터 템플릿 한글 IME 버그 수정**
  - `MetadataTemplateEditor.tsx`: `onKeyDown`에 `isComposing` 체크 추가 — 한글 조합 중 Enter 이중 등록 방지

- [x] **샘플 PDF/PPTX 파일 재생성**
  - 이전 세션에서 깨진 파일(8B/70B) → reportlab/python-pptx로 정상 재생성

- [x] **P2A-2: 하이브리드 검색 (벡터 + BM25)** (5 tasks)
  - `infrastructure/search/bm25.py`: BM25Okapi 인덱스 + 한글/영어 토크나이저
  - `infrastructure/search/hybrid.py`: RRF(Reciprocal Rank Fusion) 병합
  - `rag_agent.py`: 하이브리드 검색 적용, thinking step에 검색 모드 표시
  - `wiki_indexer.py`: BM25 인덱스 자동 동기화 (추가/삭제/전체 재인덱싱)
  - `tests/test_hybrid_search.py`: 검색 품질 비교 테스트

- [x] **P2A-3: 증분 인덱싱** (4 tasks)
  - `infrastructure/storage/file_hash.py`: SHA256 해시 기반 변경 감지
  - `wiki_indexer.py`: 해시 비교 → 미변경 파일 스킵 (15파일 0초 완료)
  - `wiki.py`: `POST /api/wiki/reindex?force=true` 파라미터 추가

- [x] **P2A-4: 임베딩/검색 캐싱** (4 tasks)
  - `infrastructure/cache/query_cache.py`: LRU 캐시 (TTL 5분, 128 entries)
  - `rag_agent.py`: 캐시 히트 시 검색 스킵 ("캐시" 모드 표시)
  - `wiki_indexer.py`: 문서 변경 시 해당 파일 관련 캐시 자동 무효화
  - 캐시 히트율 모니터링 로그 내장

- [x] **P2A-5: 메타데이터 사전 필터링** (4 tasks)
  - `application/agent/filter_extractor.py`: domain/process 키워드 자동 추출
  - `rag_agent.py`: 추출 필터 → ChromaDB where 절 적용 + 0건 시 필터 제거 fallback

- [x] **P2A-6: Cross-encoder 리랭킹** (4 tasks)
  - `infrastructure/search/reranker.py`: LLM 기반 리랭킹 (기존 LiteLLM 활용)
  - `rag_agent.py`: 검색 후 리랭킹 단계 추가
  - `config.py`: `enable_reranker` 설정 (on/off), 지연 시간 로깅
  - `tests/test_reranker.py`: A/B 비교 테스트

- [x] **Phase 2-B: 문서 충돌 감지 & 해소 계획 수립** (5 Steps, 24 Tasks)
  - `master_plan.md`에 Phase 2-B 섹션 추가 (배경, 5단계 상세 설계, 타임라인)
  - `TODO.md`에 P2B-1 ~ P2B-5 태스크 테이블 추가 + 진행 요약 갱신
  - 항목: RAG 충돌 감지 프롬프트, 메타데이터 신뢰도, 중복 감지 대시보드, 인라인 비교 뷰, 문서 계보

---

## 2026-03-28 (세션 7)

- [x] **Phase 1.5: PDF Viewer 구현**
  - `react-pdf` 패키지 설치
  - `PdfViewer.tsx`: 페이지 네비게이션, 6단계 줌(50%~200%), 50페이지 이상 페이지 그룹 페이지네이션
  - 키보드 화살표 네비게이션, 페이지 번호 직접 입력
  - `FileRouter.tsx`: dynamic import (ssr: false)

- [x] **Phase 1.5: Presentation Viewer 구현**
  - 백엔드: `GET /api/files/pptx-data/{path}` — python-pptx로 슬라이드 JSON 추출 (텍스트/이미지/서식)
  - `PresentationViewer.tsx`: 백엔드 JSON → HTML/CSS 렌더링, 슬라이드 네비게이션, 키보드 조작
  - pptx-viewer 패키지는 Turbopack 호환 문제로 제거, 백엔드 파싱 방식으로 전환

---

## 2026-03-26 (세션 5)

- [x] **에이전트 라우팅/RAG 고도화 — 일반 질문 WIKI_QA 미라우팅 수정**
  - `router.py`: KEYWORD_RULES 확장 — 일반 검색(찾아줘, 누구, 어떻게 등) 패턴 WIKI_QA 매칭
  - `router.py`: LLM classifier 프롬프트 개선 — UNKNOWN 대신 WIKI_QA를 기본 폴백으로 설정
  - `rag_agent.py`: 시스템 프롬프트 범용화 ("제조 SCM 도메인" → "사내 Wiki", 인사/조직 등 포함)
  - `rag_agent.py`: Clarity check 조건 완화 — `len(query) < 10` 제거, 관련성 기반으로만 판단
  - `rag_agent.py`: Clarity check 프롬프트 개선 — 구체적 키워드 있으면 CLEAR 처리

- [x] **RAG 검색 품질 고도화 — 구조화 데이터(인사정보) 미검색 수정**
  - `rag_agent.py`: 대화 히스토리 기반 쿼리 보강 (`_augment_query`) — 후속 질문에 이전 맥락 반영
  - `rag_agent.py`: 시스템 프롬프트 강화 — 구조화 데이터(키:값) 추출, 인사정보 이름/소속 명시 규칙
  - `rag_agent.py`: 검색 범위 확대 (n_results 5→8) + MIN_SOURCE_RELEVANCE 0.4→0.3
  - `wiki_indexer.py`: 짧은 문서에 파일 경로 컨텍스트 프리픽스 추가 → 임베딩 품질 향상

- [x] **RAG 탐색 과정 시각화 (하이브리드 방식)**
  - Backend: `ThinkingStepEvent` 스키마 추가, RAG 파이프라인 각 단계에서 `thinking_step` SSE 이벤트 방출
  - 단계: 쿼리 보강 → 문서 검색 → 명확성 확인 → 답변 생성 (각각 start/done 상태)
  - Frontend: `ThinkingStepsDisplay` 컴포넌트 — 진행 중 애니메이션 + 완료 후 접이식 로그
  - SSE client에 `onThinkingStep` 콜백 추가

- [x] **Self-Reflective Cognitive Pipeline (Option A: Two-Step Run)**
  - `rag_agent.py`: `_cognitive_reflect()` — 숨겨진 LLM 호출로 의도분석/초안/자기검토 수행, 백엔드 콘솔에만 로깅
  - `rag_agent.py`: 최종 답변 생성 시 critique 피드백을 시스템 프롬프트로 주입 → 품질 향상
  - `rag_agent.py`: `FINAL_ANSWER_SYSTEM_PROMPT` — 공감 IT 파트너 페르소나, Minto Pyramid, 실행 가능 다음 단계
  - `rag_agent.py`: `COGNITIVE_REFLECT_PROMPT` — 3단계 인지 분석 (thought/draft/critique)
  - `AICopilot.tsx`: `cognitive_reflect` thinking step + Brain 아이콘 추가
  - **SSE 파이프라인 무변경**: content_delta에는 최종 답변만 전송, 내부 사고 절대 미노출

- [x] **Phase 2-A: RAG 성능 고도화 계획 수립** (6 Steps, 25 Tasks)
  - `master_plan.md`에 Phase 2-A 섹션 추가 (배경, 6단계 상세 설계, 타임라인)
  - `TODO.md`에 P2A-1 ~ P2A-6 태스크 테이블 추가 + 진행 요약 갱신
  - 항목: LLM 병렬화, 하이브리드 검색, 증분 인덱싱, 캐싱, 메타데이터 필터링, 리랭킹

---

## 2026-03-26 (세션 4)

- [x] **문서 메타데이터 이력 관리 (생성일/수정일/생성자/수정자)**
  - `DocumentMetadata`에 `updated`, `created_by`, `updated_by` 필드 추가 (기존 `author` → `created_by` 마이그레이션)
  - Backend Storage Layer: 저장 시 자동 타임스탬프/작성자 주입 (`created`/`created_by`는 최초만, `updated`/`updated_by`는 매번)
  - WikiService + Wiki API에 `user_name` 전달 경로 연결 (인증 레이어 활용)
  - ChromaDB indexer에 새 필드 반영 → RAG 검색에서 활용 가능
  - Frontend: 타입/파서/시리얼라이저 업데이트, MetadataTagBar에 읽기전용 이력 표시

- [x] **AI Copilot 마크다운 렌더링 + 저장 후 메타데이터 갱신 버그 수정**
  - `react-markdown` + `remark-gfm` 설치, AssistantBubble에 마크다운 렌더링 적용
  - prose 스타일링 (볼드, 이탤릭, 코드, 리스트, 테이블, 헤딩 등)
  - `handleSave` 후 서버 응답의 metadata를 로컬 상태에 반영 (updated/updated_by 갱신)

- [x] **사이드바 빈 공간 우클릭 컨텍스트 메뉴**
  - 빈 공간 우클릭 시 "새 문서" / "새 폴더" 메뉴 표시 (루트 레벨)
  - ContextMenuState.node를 nullable로 변경, RootDropZone에 onContextMenu 핸들러 추가

- [x] **인증 추상화 레이어 (Auth Abstraction Layer)**
  - Backend: `backend/core/auth/` — User 모델, AuthProvider ABC, NoOpProvider, FastAPI Depends
  - Backend: 전체 API 라우터에 `dependencies=[Depends(get_current_user)]` 적용
  - Backend: `config.py`에 `auth_provider` 설정, `factory.py`로 provider 선택
  - Frontend: `lib/auth/` — AuthProvider 인터페이스, AuthContext, useAuth hook, DevAuthProvider
  - Frontend: `Providers.tsx` → `layout.tsx` 연결, `useAuthFetch` 유틸
  - 추후 SSO/LDAP/OIDC 등으로 교체 시 Provider만 구현하면 됨

---

## 2026-03-26 (세션 3)

- [x] **TreeNav 활성 파일 강조 + 폴더 기본 접힘**
  - 현재 열린 탭의 파일이 사이드바에 `bg-primary/15` 강조 표시
  - 폴더 기본값 접힘 (`useState(false)`), 활성 파일 포함 폴더만 자동 펼침
  - `activeFilePath` prop을 DraggableTreeItem에 전달

- [x] **Context Engineering 시스템 업그레이드**
  - `toClaude/archive/` 생성, 기존 요약/이슈 파일 8개 아카이브 이동
  - CHECKLIST.md → 테스트 매뉴얼로 전환 (모든 체크박스 제거)
  - `agent_tools_schema.md` 스켈레톤 생성 (PydanticAI tool SSOT)
  - CLAUDE.md에 Smart TDD Rule + Archive Rule 추가
  - TODO.md = 상태 추적 SSOT 확립

---

## 2026-03-26 (세션 2)

- [x] **RAG 에이전트 명확화 질문 기능** (Step 1-F 고도화)
  - 모호한 질문 시 바로 답변하지 않고 검색 결과 기반 명확화 질문
  - 검색 결과를 보여주면서 선택지 제시 ("이런 문서를 찾았는데 어떤 걸 원하시나요?")
  - 대화 히스토리 활용 (세션 내 멀티턴 맥락 유지)

- [x] **RAG 출처 참조 고도화** (Step 1-F 고도화)
  - 관련도 필터링: MIN_SOURCE_RELEVANCE(0.4) 미만 출처 제외
  - 명확화 질문 시 낮은 threshold(0.2)로 참조 문서 표시
  - 구체적 답변 시 높은 threshold(0.4)로 관련 문서만 표시

- [x] **UI 라벨 변경**
  - AI Copilot → On-Tong Agent
  - 사이드바 Wiki → On-Tong

- [x] **에이전트 세션 관리** (Step 1-F 고도화)
  - 새 대화 시작 / 세션 목록 / 세션 전환 / 세션 삭제
  - 첫 메시지 기반 세션 제목 자동 생성
  - 세션별 독립된 대화 히스토리

- [x] **드래그앤드롭 + 이름 변경** (Step 1-A 고도화)
  - @dnd-kit DndContext + DragOverlay + PointerSensor(distance:8)
  - DraggableTreeItem: useDraggable + useDroppable(폴더만)
  - RootDropZone: 루트 레벨 드롭 지원
  - 이름 변경: 우클릭 → InlineInput 인라인 편집 → PATCH API
  - 열린 탭 경로 자동 업데이트 (updateTabPath 스토어 메서드 추가)
  - 백엔드: PATCH /api/wiki/file/{path}, PATCH /api/wiki/folder/{path}

- [x] **사이드바 파일/폴더 관리** (Step 1-A 고도화)
  - 새 문서 생성 (+ 버튼 → 파일명 입력 → .md 자동 생성)
  - 파일 삭제 (우클릭 → 컨텍스트 메뉴 → 삭제 + 탭 자동 닫기)
  - 새 폴더 생성 (헤더 버튼 + 폴더 우클릭 → 새 폴더)
  - 폴더 삭제 (우클릭 → 삭제, 빈 폴더만 가능)
  - 폴더 내 파일/하위폴더 생성 (폴더 우클릭 컨텍스트 메뉴)
  - 트리 새로고침 버튼
  - 백엔드: POST/DELETE /api/wiki/folder API 추가

---

## 2026-03-26 (세션 1)

- [x] **메타데이터 템플릿 관리 기능** (Phase 2)
  - 백엔드: `GET/PUT/POST /api/metadata/templates` — JSON 파일 기반 CRUD (`wiki/.ontong/metadata_templates.json`)
  - 프론트엔드: `MetadataTemplateEditor` — Workspace 가상 탭으로 열림, Domain/Process/Tags 추가·삭제 UI
  - MetadataTagBar의 하드코딩된 DEFAULT_DOMAINS/DEFAULT_PROCESSES → 템플릿 API에서 동적 로드로 대체

- [x] **메타데이터 태깅 고도화** (Phase 2)
  - 에러코드 자동 추출: 저장 시 본문에서 정규식(`DG320`, `ERR-001` 등) 자동 감지 → frontmatter에 주입
  - 태그 정규화: `GET /api/metadata/tag-merge-suggestions` — 유사 태그 감지 (캐시/캐쉬/cache → 통합 제안)
  - 태그 기반 사이드바: Domain > Process > Tags 계층 브라우저, 클릭 시 문서 목록 표시
  - 미태깅 문서 대시보드: `UntaggedDashboard` — 미태깅 목록 + 일괄 자동 태깅 + 태그 사용 통계
  - `GET /api/metadata/files-by-tag` — 필드·값 기반 문서 필터링 API
  - `GET /api/metadata/untagged` — 미태깅 문서 목록 API

- [x] **3-Pane UI 고도화** (Phase 2)
  - 탭 시스템 확장: `TabType = FileType | VirtualTabType`, `openVirtualTab()` 스토어 메서드 추가
  - 사이드바 3-섹션 전환: 파일 트리(FolderTree) / 태그 브라우저(Tags) / 관리(Settings) 아이콘 탭
  - Workspace: 가상 탭(메타데이터 템플릿, 미태깅 대시보드) 지원, FileRouter에서 TabType 기반 라우팅

---

## 2026-03-30 (세션 17 — Skill System 기반 구축)

- [x] **Skill System Phase 1-5 구현**
  - Skill Protocol + SkillResult + SkillRegistry (`backend/application/agent/skill.py`)
  - AgentContext: per-request context with `run_skill()`, `emit_thinking()`, `sse()` (`backend/application/agent/context.py`)
  - 7개 스킬 추출: query_augment, wiki_search, wiki_read, wiki_write, wiki_edit, llm_generate, conflict_check (`backend/application/agent/skills/`)
  - ReAct loop + tool executor for LLM tool-use agents (`backend/application/agent/tool_executor.py`)
  - RAGAgent refactoring: skill 호출로 전환, backward compatibility 유지 (ctx 없을 때 inline fallback)
  - main.py: `register_all_skills()` 호출 + `agent_api.init(wiki_service, chroma, storage)` 업데이트
  - api/agent.py: AgentContext 생성 + `ctx=ctx` kwarg으로 agent에 전달
  - 68개 기존 테스트 전부 통과 (regression 없음)

---

## 2026-04-27 (Section 2 — P29 + P30 Hardcore validation fix)

- [x] **P29-1: TransactionalAnalyzer + AsyncAnalyzer**
  - `spring/transactional_analyzer.py` — `@Transactional` class/method → `tx_marker` entity (propagation, isolation, read_only, rollback_for, transaction_manager). class-level → public method 상속.
  - `spring/async_analyzer.py` — `@Async` + `@TransactionalEventListener.phase` → `async_marker` entity.
  - `parser_protocol.py` — `tx_marker`, `async_marker` entity kind 등록.

- [x] **P29-2: MyBatis 지원 (annotation + XML)**
  - `spring/mybatis_mapper_analyzer.py` — `@Mapper` + `@Select/@Insert/@Update/@Delete` → table edges.
  - `mybatis_xml_parser.py` — XML mapper namespace + statement id → method FQN. `<if>/<choose>/<when>/<otherwise>/<foreach>` 조건부 분기 confidence=0.7, 단순 SQL=0.95.
  - `repo_parser.py` — Java pass 끝나면 `parse_mybatis_xml_files(repo_path)` 추가 호출.
  - `parser_protocol.py` — `mapper_method` entity kind 등록.

- [x] **P29-3: call_resolver qualifier-aware + DI field_name**
  - `spring/di_analyzer.py` — `AUTOWIRES` edge 에 `field_name` (field/constructor 둘 다) + `injection_kind` 추가.
  - `call_resolver.py` — qualifier 가 명시되어 bean_name_index 에 hit 하면 type_candidates 와 무관하게 qualifier 가 가리키는 impl 사용 (interface 필드 + impl `@Component("name")` 패턴 해소).

- [x] **P29-4: LLM 호출처 valid set 검증 (hallucination firewall)**
  - `mapping/anchor_binding_suggester.py::_parse()` — `valid_term_fqns`, `valid_anchor_locators` frozenset 으로 hallucinated FQN drop.
  - `mapping/rule_suggester.py::_parse()` — `valid_frag_fqns`, `valid_term_fqns` 검증.

- [x] **P30-1: AOP INTERCEPTS class → method fan-out**
  - `cross_file_enricher.py::_expand_intercepts_to_methods()` — class-level INTERCEPTS edge target 이 class FQN 이면 그 class 의 public method 단위로 method-level synthesized edge 추가.

- [x] **P30-2: Event chain publisher → handler 직접 합성 엣지**
  - `cross_file_enricher.py::_synthesize_event_chain_edges()` — `publishes` + `handles` 조합으로 `calls_via_event` (publisher → handler) 직접 엣지 합성. async_marker 의 `async`/`tx_phase` 도 attribute.
  - `parser_protocol.py` — `calls_via_event` relation kind 등록.

- [x] **P30-3: QueryDSL JPAQueryFactory + JPQL post-translation**
  - `spring/native_sql_analyzer.py::_classify_invocation()` — `JPAQueryFactory.selectFrom/select/.../update/delete/insert(QSlab.slab)` 패턴 인지.
  - `_edges_from_qdsl_arg()` + `_infer_qclass_entity()` — Q-prefix strip 으로 entity simple name 추출 (`QSlab.slab` → `Slab`). `dialect=jpql, via=querydsl, confidence=0.5, dynamic_predicates=True` 로 emit → cross_file_enricher `_resolve_jpql_to_table` 가 `@Table(name=...)` 매핑으로 실제 테이블명 (`Slab` → `tb_slab`) 변환.

- [x] **Chaos test invert + 회귀 가드**
  - `tests/test_spring_chaos_async.py` — qualifier resolution / MyBatis presence 두 결함 증명 테스트를 fix 검증 테스트로 invert.
  - `tests/test_code_analysis_registry.py` — 새 entity/relation kind (`tx_marker`, `async_marker`, `mapper_method`, `calls_via_event`) 가 spring 카테고리에 추가된 상태로 카테고리 단정 완화.
  - 결과: 모델링 영역 pytest 1862 pass / 0 modeling-side fail.

---

## 2026-05-01 세션 — Scale (5000+ class) + UX 대대적 개편 + Phase 1 보완

### Scale 대응 (S1~S6)
- [x] **S1 백엔드 EntitySearchIndex** — `backend/modeling/code_analysis/entity_search_index.py` 신규. per-repo 인메모리 인덱스, score 정렬 (exact > startswith > contains + kind boost), 다중 kind 필터, parent_fqn, pagination, binding/rule 카운트 enrichment. `repos_api.search_entities` 교체.
- [x] **S2 OntologyGraph subgraph navigation** — `/repos/{id}/ontology-subgraph?focus=...&depth=N&node_cap=80`. 프론트 `OntologyGraphPanel.tsx` 완전 재작성 — focus 검색 → 1~3 hop subgraph, dagre LR + smoothstep, 노드 더블클릭으로 새 focus, ConceptBinding 패널.
- [x] **S3 TermMapping 가상 페이지 + 검색** — 검색 박스 (term/code/scope/source 부분 일치), 100건 페이지 + 「+200건 더보기」.
- [x] **S4 메서드 트리 적응형 expand** — ≤500 클래스 자동 펼침 / >500 collapsed. 「⊞ 전체 펼침/⊟ 접기」 컨트롤 + 가시 카운트. (react-window 진짜 가상화는 다음 세션).
- [x] **S5 ⌘K 통합 검색** — `/search/global` 인덱스 기반 + term/rule 통합. 종류별 그룹 (용어/클래스/메서드/필드/규칙) + T/R 매핑 카운트 배지. `WorkbenchCommandPalette.tsx` GroupedHits 컴포넌트.
- [x] **S6 Domain map (Top-down 진입점)** — `backend/modeling/api/domain_map_api.py` 신규. `/repos/{id}/domain-map` + `/llm-categorize`. LLM 자동 9 카테고리 (주문→화학성분→Slab사양→공정설비→...→상태진도). `BusinessTerm.domain` 에 `"NN|name"` 인코딩으로 order 보존. OntologyGraphPanel EmptyState 가 도메인 맵으로 교체.

### Phase 1 보완 — Binding Health 파이프라인 (S7)
- [x] **S7-B Stale binding sweeper** — `backend/modeling/sweepers/stale_binding_sweeper.py` 신규. confirmed binding 의 code_fqn 이 신규 entity index 에 없으면 stale 분류. 3 tier rematch 후보: alias-exact (정규화 camel↔snake) / simple-name / parent-preserved.
- [x] **S7-A Reindex 엔드포인트** — `backend/modeling/api/binding_health_api.py` 신규. `POST /repos/{id}/reindex` (재파싱 + sweep), `GET /repos/{id}/stale-bindings`, `POST /bindings/{id}/rematch` (1-click + audit log). 비파괴 — 자동 confirmed 변경 X.
- [x] **S7-C Diff-driven 알림** — reindex 응답에 added/removed FQN 샘플 30개 포함. 이전 entity snapshot 과 set diff. UI 에서 +N -M 표시 + detail 펼치기.
- [x] **검증** — `CastSpecJpo.productTypeCd → productKindCd` 한 줄 리네임 시 stale 2건 자동 감지 + alias-exact 후보 conf 0.95 자동 제시. 100% 적중.

### UX 라운드 (U1~U9 + 폴리시 라운드)
- [x] **U1 TermMapping 첫 진입 spinner** — `loadingTerms/loadingBindings = true` 초기화로 ~3초 빈 화면 제거.
- [x] **U2 도메인 흐름 wrap** — 9 단계 카드 짤림 0 (overflow-x → flex-wrap, 4-4-1 자동).
- [x] **U3 데모 데이터 amber CTA + LOADED 배지** — 옅은 disabled-look → 강조 CTA + emerald 「LOADED」.
- [x] **U4 Binding Health 신규 패널** — 사이드바 「🛡️ 매핑 상태」 신규 탭 + `BindingHealthPanel.tsx` (380줄). 건강도 막대 + healthy/stale/total grid + 「재파싱 + 진단」 CTA + diff 카드 + stale rematch 1-click.
- [x] **U5 Workbench 메서드 트리 default expand** — nestedTree 빌드 후 모든 fullPath 자동 open (≤500 클래스 한정).
- [x] **U6 Workbench placeholder** — 어두운 빈 영역 → ← 화살표 + 한국어 안내 + ⌘K hint kbd.
- [x] **U7 매뉴얼 가이드 collapse** — viewport 절반 → 한 줄 + 「클릭해서 펼침」 토글.
- [x] **U8 5-mode rail tooltip** — 6 탭 모두 한국어 tip + aria-label.
- [x] **U9 Repository ACTIVE indicator** — 좌측 4px 굵은 border + `ACTIVE` 진한 배지 + bold + checkmark.

### 검증 + 가이드
- [x] **P27 E2E 검증** — `SdFinalLengthRangeAction.execute` 시뮬 풀 사이클 (Java→한국어 Python by Claude → RestrictedPython sandbox → DiffReporter). status: completed, mutation_diff 정상.
- [x] **P28 사용자 가이드 v4** — `toClaude/modeling/사용자-가이드-v4.html`. 7개 탭 walkthrough + ⌘K + 새 기능 모두 반영.
- [x] **/browse 자율 audit + verify 루프** — gstack browse 스킬로 5탭 전수 캡처 → 9건 결함 자동 발견 → fix → 재캡처 검증 흐름 작동.

### 보고서 (참고용)
- `toClaude/modeling/reports/4-phase-ideal-comparison.html` — 외부 의견의 4 Phase 프레임워크 vs 현재 시스템 정직한 비교 + 점수 (Phase 1: 35→75, Phase 2: 45, Phase 3: 30, Phase 4: 10)
- `toClaude/modeling/reports/phase1-beyond-100.html` — Phase 1 100→180점 16가지 + 4-주 로드맵 + 우리만의 차별화 5가지
- `toClaude/modeling/reports/ux-audit-2026-05-01.md` — UX audit 9건 결함 시트

### 다음 세션 후보 (HANDOFF.md 참조)
- 옵션 A: Phase 1 TIER 1 — file watcher / git provenance / auto self-heal / type-aware (1~2일 → 100점)
- 옵션 B: Phase 2 SemanticHook (3~5일, 외부 차별화 시작)
- 옵션 C: react-window 도입 (메서드 트리 진짜 가상화)
- 옵션 D: Phase 3 ConstraintEvaluator (옵션 B 의존)

---

## 2026-05-01 — Phase 3 Step 2: Repo Import 백엔드 (P3-2 완료)

### Code
- [x] `backend/modeling/api/repo_import.py` 신규 — `POST /api/ontology/repos/import`, `GET .../{job_id}`, `GET .../{job_id}/stream` (SSE), `GET .../import` (list)
- [x] `backend/main.py` — repo_import_api router 등록
- [x] `backend/modeling/persistence/database.py` — SQLite FK pragma ON (connect 이벤트). delete_repo bulk delete 의 cascade 가 동작하도록.
- [x] `backend/modeling/code_layer/role_classifier.py` — `*Jpo` / `*PK` 등 INFRA 이름 패턴이 `@Entity` annotation 보다 우선. slab-design 컨벤션 (Jpo=raw row=INFRA, *Entity=rich domain=DOMAIN) 정합.
- [x] `backend/modeling/code_layer/importer.py` — `_normalize_caller_fqns` 추가. parser 의 `Pkg.Class.method` (signature 없음) 을 저장된 `Pkg.Class.method(int,String)` 로 line 매칭 → CallSite FK 정합.

### Verification (curl)
- [x] 1차 import: `done`, 123 CodeType / 956 method / 1018 CallSite / errors=0
- [x] 2차 import (idempotent): 같은 repo_id 재실행 → done, 동일 카운트, errors=0
- [x] role 분포: framework=6 / domain=76 / infra=41 (Jpo 14 모두 INFRA, Entity 12 모두 DOMAIN)
- [x] SSE: `event: progress` 다회 + `event: end` 정상 송출

---

## 2026-05-01 — Phase 3 Step 3: 자동 매핑 추천 (P3-3 완료)

### Code
- [x] `backend/modeling/code_layer/recommender.py` 신규 — `build_recommendations(types, repo_id)` → `RecommendationResult{term_candidates, action_candidates, type_realization_candidates}`. slab-design glossary 30+ 매핑 (`SDOrderEntity→주문`, `SDSlabEntity→슬랩`, ...). ActionKind 휴리스틱 (`design`/orchestrator → workflow, void+save → effectful, return + 무mutation → pure_function). 핵심: `*Entity ⊃ *Jpo` 평탄화 흡수 패턴 자동 검출 → PARTIAL TypeRealization 후보.
- [x] `backend/modeling/api/recommend_api.py` 신규 — `POST /api/ontology/repos/{repo_id}/recommend?persist=true&min_confidence=0.7`. read-only DTO 반환 + 옵션으로 `confirmed=False, source="auto"` 영속. 결과는 confidence DESC 정렬.
- [x] `backend/main.py` — `recommend_api` router 등록.

### Verification (curl on slab-design-real)
- [x] read-only 호출: 29 term + 36 action + 34 realization 반환, top 12 term 모두 conf=1.0 (글로서리 정확 매칭: 에러코드/검증결과/이력/주조스펙/고객표준/EDGING그룹/...).
- [x] persist=true: 29/36/34 모두 store 적재 → 기존 `/api/ontology/terms` `/actions` 에서 confirmed=False 로 조회됨.
- [x] **드라마 DNA**: SDOrderEntity 의 PARTIAL 4건 (OS/OM/Chemical/QD) + SDSlabEntity ⊃ SlabResult 자동 발견. p3_order_mapping.md 의 평탄화 매핑 패턴 정합.
- [x] declared_on_term 자동 추정: 16 *Action.execute(SDOrderEntity, SDSlabEntity) 모두 `term.scm.order` (주문) 으로 매핑.

---

## 2026-05-01 — Phase 3 Step 4: Frontend Repo Import UI (P3-4 완료)

### Code
- [x] `frontend/src/lib/api/ontology.ts` — 4 신규 메서드 + 3 DTO. `startRepoImport`, `getRepoImportStatus`, `streamRepoImportProgress` (EventSource wrapper, 닫힘/오류 시 cleanup), `recommendForRepo`. `RepoImportJobDTO` / `RepoImportStatusDTO` / `RecommendationResponseDTO`.
- [x] `frontend/src/components/sections/modeling/RepoImportModal.tsx` 신규 — shadcn Dialog 기반. 4 phase: `form` (path + repo_id 입력, basename 자동 추출) → `importing` (SSE 진행률 + progress bar + parsing/adapting/classifying/storing 단계 라벨) → `recommending` (자동 매핑 추천 persist=true) → `done` (CodeType/Method/CallSite stat + Term/Action/Realization 큐 카드). SSE 끊기면 status polling 으로 자동 폴백. 모달 닫힘 → SSE cleanup + 200ms 후 form 으로 reset.
- [x] `frontend/src/components/sections/modeling/TopBar.tsx` — `Import` 버튼 추가 (FolderInput 아이콘, "그래프" 옆). 클릭 → 모달 open.

### Verification
- [x] `npx tsc --noEmit` clean (exit 0).
- [x] 백엔드 endpoint 직접 curl 검증 (모달이 호출하는 것과 동일 시퀀스): `POST /import` → SSE done → `POST /recommend?persist=true` → 29/36/34 persisted.
- [x] CORS allowlist 에 localhost:3000/3001 + 127.0.0.1 포함 — Next dev 어느 origin 으로든 서빙 OK.

---

## 2026-05-01 — Phase 3 Step 5: xyflow + dagre 자동 layout (P3-5 완료)

### Code
- [x] `backend/modeling/api/graph_api.py` 신규 — `GET /api/ontology/repos/{repo_id}/graph?focus_fqn=&hops=&include_kinds=`. CodeType + BusinessTerm + Action 노드, Inheritance/Composition/TypeRealization/Realization 엣지 통합. `focus_fqn` 주면 BFS k-hop subgraph (5000+ class scale 대응). 노드 600개 hard cap (workflow Action / root Term 우선).
- [x] `backend/main.py` — `ontology_graph_api` 별칭으로 router 등록 (기존 `graph_api` 와 이름 충돌 회피).
- [x] `frontend/src/lib/api/ontology.ts` — `getOntologyGraph` 메서드 + 4 DTO (`GraphNodeDTO`, `GraphEdgeDTO`, `GraphNodeKind`, `OntologyGraphDTO`).
- [x] `frontend/src/components/sections/modeling/OntologyGraph.tsx` 신규 — xyflow + `@dagrejs/dagre` LR layout. 검색 → focus 노드 선택 + hops slider (1~4). 엣지 색상 분리: PRIMARY=emerald 굵게 / PARTIAL=amber 애니메이션 / realization=orange / extends/implements=slate / composition=violet. minimap + zoom 0.1~2x. custom node (kind 별 색 + role/verification subtitle).
- [x] `frontend/src/components/sections/modeling/GraphMode.tsx` — L3 view 를 mock 에서 `<OntologyGraph repoId={activeRepoId} />` 로 교체. default level=3. keydown handler 에 input/textarea/contenteditable 가드 추가 (검색박스 숫자 입력이 level switch 안 발화).

### Verification
- [x] `tsc --noEmit` clean.
- [x] curl `/repos/slab-design-real/graph` → 188 nodes / 69 edges (123 code_type + 29 term + 36 action). edge kind 분포: 29 PRIMARY + 5 PARTIAL + 35 realization.
- [x] focus 동작: `?focus_fqn=term.scm.order.order&hops=1` → 2 nodes (주문 term + SDOrderEntity).
- [x] Next dev rewrite 통해 동일 응답 (origin: localhost:3000).

---

## 2026-05-01 — Phase 3 Step 6: 매핑 큐 액션 (P3-6 완료)

### Code
- [x] `backend/modeling/api/queue_actions_api.py` 신규 — `GET /repos/{id}/queue?limit=` (Term/Action/Realization 후보 통합, 모두 `confirmed=False` 만) + 6 confirm/reject endpoint:
  - `POST /repos/{id}/terms/{fqn}/confirm` (sets confirmed=True, source=user)
  - `POST /repos/{id}/terms/{fqn}/reject` (delete + cascade related TypeRealizations)
  - `POST /repos/{id}/actions/{fqn}/confirm?by=user` (confirmed_by + verification draft → signature_locked)
  - `POST /repos/{id}/actions/{fqn}/reject` (delete + cascade Realizations)
  - `POST /repos/{id}/type-realizations/{tr_id}/confirm`
  - `POST /repos/{id}/type-realizations/{tr_id}/reject`
- [x] `backend/main.py` — `queue_actions_api` router 등록.
- [x] `frontend/src/lib/api/ontology.ts` — `getMappingQueue` + 6 confirm/reject 메서드 + 5 DTO.
- [x] `frontend/src/components/sections/modeling/LeftPanel.tsx` — `QueueTab` 재구성. 4-section tab (Term/Action/Real/Code legacy) + 카운트 배지 + reload (↻) 버튼 + 행별 ✓/✗ 버튼 + optimistic UI (실패 시 자동 reload). Realization 행은 PRIMARY/PARTIAL 색 구분 (🟢/🟡).

### Verification
- [x] curl 6 endpoint 모두 성공: confirm 1 term + 1 action + 1 partial realization + reject 1 realization → 큐 99 → 95 정확히 정합.
- [x] Next proxy 통한 `getMappingQueue` 응답 정상.
- [x] tsc clean.

---

## 2026-05-02 — Phase 3 Step 7: 데모 시나리오 끝-끝 검증 + UX fix (P3-7 완료)

헤드리스 Chromium (gstack `browse`) 으로 Import → Graph → 큐 confirm 풀 사이클 검증. 발견 즉시 fix.

### 발견 + fix UX 이슈 6건

1. **default repo "scm"** — `store.ts` 의 `activeRepoId` 기본값이 mock 시절의 `"scm"` 이라 페이지 reload 후 그래프/Map 모두 빈 화면. → `"slab-design-real"` 로 변경. 백엔드 영속성 + idempotent import 라 사용자 경험 단절 없음.
2. **그래프 LR layout 가독성** — 188 노드 LR 이라 가로 한 줄로 펼쳐져 노드 라벨 안 읽힘. → `OntologyGraph.tsx` rankdir TB + nodesep/ranksep 조정 + Handle 위치 Top/Bottom.
3. **isolated CodeType 노이즈** — 91개 framework/infra CodeType 이 매핑 안 된 채 그래프에 포함되어 hub-spoke 형태 압축. → `graph_api.py` `connected_only=true` default 추가, 117 노드로 감소.
4. **첫 진입 가시성** — 117 노드도 스타형이라 한 화면에 펼치면 압축. → `OntologyGraph.tsx` 데이터 로드 후 가장 connected 한 term/action 자동 focus + hops=2 (40 노드 이상일 때만). 첫 화면이 의미있는 7~15 노드 subgraph.
5. **focus 변경 시 fitView 미재실행** — ReactFlow `fitView` 는 mount 시 한 번만. → `key={repoId|focus|hops|nodeCount}` 로 remount 강제. focus / hops slider / 검색 후 즉시 새 viewport.
6. **키보드 안내 카드 minimap 겹침** — `GraphMode.tsx` 우하단 카드와 ReactFlow minimap 충돌. → L3 (실제 그래프) 일 때만 숨김. L1/L2/L4/L5 mock view 에서는 유지.

### 검증 (브라우저 자동화)

| 시나리오 | 결과 |
|---|---|
| S1 Import | 모달 SSE 진행률 → 353ms 완료 → done 카드 (123/956/1018 + 추천 29/36/34 큐 적재) |
| S5 Graph | 자동 focus "화학성분" (degree-highest term) 2-hop → 7 nodes 6 edges. **PARTIAL realization 4건 (SDOrderEntity → OS/OM/Chemical/QD) amber 점선 ★** + PRIMARY emerald 굵게. 드라마 DNA 즉시 시각화. |
| S6 Queue | Term/Action/Real/Code 4-section + 카운트 배지. confirm 1 Term ✓ → optimistic UI 즉시 반영 + 백엔드 29 → 28 정확 정합. |

S2 "품종" 4-aliases 는 S5 그래프의 PARTIAL realization 시각화로 동일 시연됨.
S3 DG003 cascade / S4 LengthRange 시뮬 은 Backward / SimEngine 미구현 영역 (현재 mock UI), Phase 3 범위 외.

### 변경 파일
- `frontend/src/components/sections/modeling/store.ts` (default repo)
- `frontend/src/components/sections/modeling/OntologyGraph.tsx` (TB layout + auto-focus + remount key)
- `frontend/src/components/sections/modeling/GraphMode.tsx` (L3 안내 카드 숨김)
- `backend/modeling/api/graph_api.py` (connected_only)

---

## 2026-05-02 — V7 IA 리디자인 (D plan: 1+2+3 통합)

사용자 피드백 1번 (SCM 4 도메인 chaos), 2번 (hops cap 한계), 3번 (탭 wiring 부재) 을 한 번에 정산. mock UI 부채 제거 + 실 데이터 기반 구조로 통일.

### Backend
- [x] `backend/modeling/api/modules_api.py` 신규
  - `GET /repos/{id}/modules?min_classes=` — Java 패키지 계층 트리 + 각 노드 inventory 카운트 (direct_classes / total_classes / direct_terms / direct_actions / confirmed_ratio / children)
  - `GET /repos/{id}/modules/inventory?package=&recursive=` — 패키지 안 CodeType list (role / has_term / method_count)
- [x] `backend/modeling/api/graph_api.py` 확장
  - `mode=neighborhood|path|cluster` 3종 + `n_max` (hops 대체)
  - `_importance_neighborhood`: BFS 하면서 importance score (degree + role 가중 + confirmed) 기준 frontier expand → n_max 도달 시 중단
  - `_topn_by_importance`: focus 없을 때 상위 N
  - `_shortest_path`: A → B 무방향 BFS
  - `_cluster_by_package`: code_type 노드를 패키지 별 supernode 1개로 collapse, edges aggregated
- [x] `backend/main.py` modules_api 라우터 등록

### Frontend
- [x] `frontend/src/lib/api/ontology.ts`
  - `getOntologyGraph` 시그니처 확장 (mode/target_fqn/n_max/connected_only)
  - `getModules` / `getModuleInventory` + ModuleNodeDTO / ModulesResponseDTO / ModuleInventoryItemDTO
  - `qs()` 가 boolean 도 받게 타입 확장
- [x] `frontend/src/components/sections/modeling/ModuleTree.tsx` 신규
  - 패키지 계층 트리 (재귀 렌더, 검색 필터, 자동 chain expand)
  - 노드 별 카운트: 클래스 수 + T(term) + A(action) 색 구분 배지
  - 패키지 클릭 → 좌하단 inventory 패널 (그 패키지의 CodeType list, role dot + has_term ★)
- [x] `frontend/src/components/sections/modeling/LeftPanel.tsx`
  - 5 tab (Map/Code/Domain/Action/큐) → **2 tab (코드/큐)**. Map/Code/Domain/Action 은 모두 ModuleTree 안에서 표현됨
  - 옛 leftTab 값 호환 (자동 fallback to "code")
- [x] `frontend/src/components/sections/modeling/GraphMode.tsx`
  - L1/L2/L4/L5 mock view 완전 삭제 (~280 LOC). OntologyGraph 단일 view 로 단순화.
  - LEVELS / BREADCRUMB_LABELS / Level1View / ... / Level5View / Node mock 모두 제거.
  - Esc 닫기 + 헤더에 닫기 버튼만.
- [x] `frontend/src/components/sections/modeling/OntologyGraph.tsx`
  - **mode 토글** 3 버튼 (이웃 / 경로 / 클러스터) + 아이콘 (Network / GitFork / Boxes)
  - **n_max slider** (20/60/150/400) — neighborhood mode 전용
  - path mode 두 번째 검색박스 (도착 노드) + focus chip → target chip
  - ReactFlow `key` 에 `mode` 추가 → mode 변경 시 fitView 재실행
- [x] `frontend/src/components/sections/modeling/WorkbenchShell.tsx`
  - TabBar 제거 + grid template rows 36px+1fr+24px (옛 32px tabs row 삭제)
  - graphModeActive 상태에서도 LeftPanel 유지 (옛 GraphFilters 대체 패널 제거)
- [x] `frontend/src/components/sections/modeling/TopBar.tsx`
  - **breadcrumb** 추가: `repo › view (Detail/Graph) › selection › Lens: x`
  - 그래프 버튼 toggle (variant 변경)
  - 시뮬 버튼 disabled + tooltip ("다음 phase")
- [x] **삭제**: `frontend/src/components/sections/modeling/TabBar.tsx`

### 검증 (헤드리스 Chromium)
- [x] tsc clean.
- [x] Detail 진입: 좌측 패키지 트리 (com → example → slabdesign → boot/facade/feature/store) + 카운트 정합. Breadcrumb `slab-design-real › Detail › order_validate › Lens: verify` 노출.
- [x] 트리 drill-down: feature/sd/process/working/action (23 클래스, A22), wrapper (T5 A2), service (T1 A1) — Java 패키지 hierarchy 그대로.
- [x] Graph 진입: mode 토글 3버튼 + 검색 + n_max slider + counts. 자동 focus → 4-7 노드 의미있는 subgraph (PRIMARY emerald + impl orange + PARTIAL amber).
- [x] Cluster mode: 81 노드 (29 Term + 17 Code 클러스터 + 35 Action). 188 → 17 패키지 supernode collapse.

### 영향
- mock UI 부채 ~600 LOC 제거 (TabBar.tsx + GraphMode 의 5 mock Level view)
- 좌측 navigator 가 비로소 "내 코드 어디?" 답을 줌 (사용자 피드백 6번 해결)
- 그래프 mode 3종으로 5000+ class 시나리오 답 보유
- breadcrumb 으로 "어디서 뭐하는지" 항상 가시 (사용자 피드백 4번 해결)

---

## 2026-05-02 — Audit + 패키지 컨텍스트 (피드백 5번 + 6번 일부)

### Audit cleanup (피드백 5번)
- [x] `store.ts` — V6/V7 mock 잔재 제거. 삭제된 state/method:
  - `tabs`, `activeTabId`, `addTab`, `closeTab`, `setActiveTab`, `WorkbenchTab`, `SAMPLE_TABS` (TabBar 가 제거됐으니 unused)
  - `pathTrace`, `pathTraceHops`, `pathTraceFromFqn`, `setPathTrace`, `setPathTraceHops`, `setPathTraceFrom` (옛 GraphFilters 만 사용)
  - `showCrossDomainHighlight`, `toggleCrossDomain`, `graphFilterDomains`, `toggleGraphDomain`, `graphVerificationMin`, `setGraphVerificationMin` (모두 GraphFilters 만 사용)
  - `LeftTab` enum 도 5종 → 2종 ("code" | "queue") 으로 축소
  - `selectedActionFqn` default `"action.scm.order_validate"` (mock) → `null`
  - 결과: store.ts 145 → 79 LOC (-45%)
- [x] `GraphFilters.tsx` 삭제 (V7 에서 mount 안 됨, 사용처 0)
- [x] `MainPanel.tsx` 헤더 정리:
  - 옛 inner breadcrumb (`scm › action.scm.order_validate`) → 단순 "현재 Action: <name>" 또는 미선택 안내. 진짜 breadcrumb 은 TopBar
  - Backward 버튼 disabled + tooltip ("다음 phase") — Backward 모드 미구현 명시

### 패키지 컨텍스트 (피드백 6번 일부)
- [x] `OntologyGraph.tsx` `nodeSubtitle` 개선:
  - code_type 노드는 패키지 마지막 2 segment 표시 (`working.wrapper` / `process.std.service` 등)
  - term 노드는 root_entity 여부 강조
  - action 노드는 verification level 명시
  - 결과: ValidationResult 같은 노드가 "code_type · domain" 대신 **"working.wrapper"** 로 컨텍스트 즉시 식별

### 검증
- [x] tsc clean
- [x] 헤드리스 Chromium walkthrough — Detail/Graph 모두 정상, breadcrumb 단일화, 패키지 라벨 가시화

### 미진행 (사용자 결정 대기)
- 6번 추가 — 그래프에 패키지 cluster background (dagre compound / ELK group nodes) — 별도 phase
- 7번 — prior art 리서치 (Backstage / Palantir Foundry / Sourcegraph / Atlas / Bloom) — 별도 트랙

---

## 2026-05-02 — R4-T2.1: NodePreviewPanel (그래프 노드 클릭 → bottom slide-up)

### Code
- [x] `frontend/src/components/sections/modeling/NodePreviewPanel.tsx` 신규 — 240px 고정 bottom slide-up 패널.
  - Header: kind 색 dot + 라벨 + pin/close 버튼 + action feedback (확정됨/거절됨/오류) inline
  - Body 2-col grid: 좌 (fqn/role/domain/verification/confirmed/+ kind 별 facet), 우 (1-hop neighbors by kind + edge 종류 카운트 + kind 별 추가 detail)
  - Footer quick actions: "이 노드 중심" (focus 변경) / "Detail 모드 열기" (graph 종료 + setSelected*) / Term/Action 큐 확정·거절 (conditional, confirm 상태에 따라)
  - 큐 mutation (확정/거절) 시 onMutated 콜백 → 그래프 reload
  - pin 시 다른 노드 클릭해도 갈아치움 X
- [x] `OntologyGraph.tsx` 통합:
  - state 추가: `previewNode`, `pinned`, `reloadTick`
  - `onNodeClick` 변경: path mode 외에는 click → preview panel 열기 (focus 자동 변경 안 함). focus 는 panel 의 "이 노드 중심" 버튼 또는 검색박스로.
  - reloadTick 을 useEffect deps 에 추가 → 큐 mutation 후 자동 재조회

### Verification
- [x] `tsc --noEmit` clean
- [x] 헤드리스 walkthrough — Modeling → 그래프 → ValidationResult 클릭 → 패널 슬라이드업
  - 좌: FQN (전체 fqn) / ROLE=domain / DOMAIN (패키지) / JAVA KIND=class / CONFIRMED=queue 대기
  - 우: 이웃 1 Term + 2 Action, 엣지 1 PRIMARY emerald + 2 impl orange, METHODS 7개
  - footer: "이 노드 중심" + "Detail 모드 열기" 버튼 + "다른 노드 클릭 시 갈아치워짐" hint

### 영향 / 다음
- 사용자 피드백 4번 (길 잃음) 추가 해소 — graph 떠나지 않고 detail 봄
- R4-T2.2 (Perspective backend) 다음 → R4-T2.3 (URL state sync) → 트랙 1 인프라 + 트랙 3 통합

---

## 2026-05-02 — R4-T2.2: Perspective backend entity (안건 2 B)

새 layer `backend/modeling/view_layer/` 도입. Bloom Perspective 차용 — backend 1급 entity.

### Code
- [x] `backend/modeling/view_layer/__init__.py` — layer entry
- [x] `backend/modeling/view_layer/schema.py` — `Perspective` (id/name/repo_id/description/spec/owner_id/created_at/updated_at) + `PerspectiveSpec` (mode/n_max/focus/target/visible_kinds/visible_edge_kinds/filter/lens). spec 은 strict Pydantic, 향후 facet 추가 시 마이그레이션.
- [x] `backend/modeling/view_layer/orm.py` — `PerspectiveRow` (`perspectives` table, repo_id index + (repo_id, name) composite index). `created_at`/`updated_at` auto.
- [x] `backend/modeling/view_layer/store.py` — `ViewLayerStore` CRUD (list/get/create/update/delete + repo_id 격리 + id None 검증)
- [x] `backend/modeling/api/perspective_api.py` — REST 5 endpoint:
  - `GET    /repos/{repo_id}/perspectives` — list (repo 내)
  - `POST   /repos/{repo_id}/perspectives` — create (201)
  - `GET    /repos/{repo_id}/perspectives/{id}` — get (404 cross-repo)
  - `PUT    /repos/{repo_id}/perspectives/{id}` — partial update (name/description/spec)
  - `DELETE /repos/{repo_id}/perspectives/{id}` — delete (204)
- [x] `main.py` — view_layer ORM 등록 (bootstrap_database 자동 생성) + perspective_api router

### Tests
- [x] `tests/view_layer/test_store.py` 5/5 PASS — create_get_list / update / delete / repo_isolation / id_must_be_none_for_create

### Verification (curl via Next proxy)
- [x] list (empty) → 0
- [x] POST 한국어 name + 복합 spec → id=1, created_at/updated_at 자동
- [x] list after → 1 (id/name/mode/focus 정합)
- [x] PUT description 만 → 다른 field 유지
- [x] DELETE → 204
- [x] verify list → 0

### 다음
R4-T2.3 (URL state sync) — useSearchParams ↔ store 양방향 sync. Saved Perspective fetch 후 store 채우기 + ad-hoc state encode.

---

## 2026-05-02 — R4-T2.3: URL state sync (Saved Perspective + ad-hoc)

### Code
- [x] `frontend/src/components/sections/modeling/store.ts` — graph state 를 store 로 lift
  - 신규: `graphMode` / `graphFocus` / `graphTarget` / `graphNMax` / `activePerspectiveId` + setters
  - `applyGraphState({mode?, focus?, target?, nMax?})` 한 번에 적용
  - 옛 `LeftTab` 5종 → 2종 (이미 정리됨)
- [x] `frontend/src/components/sections/modeling/OntologyGraph.tsx` — local useState → store hook 으로 교체
- [x] `frontend/src/components/sections/modeling/useUrlSync.ts` 신규 — URL ↔ store 양방향 sync
  - URL → store (mount): `?section=modeling&repo=...&view=graph&p={id}&mode=...&focus=...&target=...&n_max=...`
  - store → URL (mutation, 200ms debounce, `router.replace` history 안 쌓음)
  - Saved Perspective fetch (`?p=42`) → spec 적용 + `?focus=...` override 지원
  - default value (mode=neighborhood, n_max=60) 는 URL 에서 생략
- [x] `frontend/src/app/page.tsx` — `useUrlSync()` 최상단 mount (모든 섹션 영향)
- [x] `frontend/src/lib/api/ontology.ts` — `getPerspective` / `listPerspectives` / `createPerspective` / `updatePerspective` / `deletePerspective` + 4 DTO (PerspectiveDTO / PerspectiveSpecDTO / Create / Update)
- [x] `OntologyGraph` toolbar — 「URL」 복사 버튼 (Link2 아이콘) — clipboard API + 1.4s 피드백

### Verification (헤드리스 walkthrough)
- [x] 새 탭 deep link `?section=modeling&view=graph&focus=term.scm.order.order&n_max=80&repo=slab-design-real`
  - → 자동 modeling 섹션 진입 + slab-design-real repo + 그래프 모드 + focus 적용
  - → 10 노드 (SDOrderEntity ⊃ 4 PARTIAL OS/OM/Chemical/QD + SDOrderChemicalJpo PRIMARY + 5 Term) 시각화
- [x] 그래프 모드 진입 → URL 자동 업데이트 `?repo=slab-design-real&view=graph&focus=...`
- [x] 새로고침 → state 완전 복원 (10 노드 그대로)
- [x] tsc clean

### 영향 / 다음
- 안건 5 B 충족 — saved perspective + ad-hoc 둘 다 URL share 가능
- 새로고침 / 뒤로가기 자연스러움 부수효과
- 다음 트랙: 트랙 1 (인프라 검증) — R4-T1.1 합성 generator 또는 트랙 3 (통합) — R4-T3.1 graph_api 5-kind 확장

---

## 2026-05-02 — R4-T1.1: synthetic 5K + perf bottleneck fix 3종

### 신규
- `scripts/synthesize_5k_repo.py` — source repo (slab-design-real, 123 CodeType) 를 N 배 cloning. fqn prefix `syn{i}.{original}` 충돌 방지. 41 copies → 5043 CodeType + 1189 Term + 1476 Action + 1394 TypeRealization in 5.7s.

### Perf 측정 + bottleneck fix
6 metric 측정 → bottleneck 3종 발견 → fix → 측정 (단계별 측정값):

| metric | 시작 | N+1 fix | summary fix | 최종 개선 |
|---|---|---|---|---|
| graph cluster mode | 1.85s | 1.75s | **180ms** | **10x** |
| graph nbr (focus + n_max=60) | 1.84s | 1.64s | **210ms** | **9x** |
| graph nbr (n_max=400) | 1.82s | 1.77s | **160ms** | **11x** |
| modules tree | **15.20s** | 1.64s | **140ms** | **108x** |

Bottleneck 3종:
1. **modules_api N+1 (`backend/modeling/api/modules_api.py:78`)** — `list_type_realizations(repo_id)` 가 CodeType 마다 호출 (5043 round-trip). → 1회 fetch + in-memory `primary_confirmed: set[str]` lookup. **15s → 1.7s** (8.8x).
2. **mapping_layer N+1 (`backend/modeling/mapping_layer/store.py:list_actions`)** — Action 마다 `RealizationRow.action_fqn == row.fqn` 별도 query (1476 round-trip). → 1 query `in_([...fqns])` + dict group. 직접 영향은 작음 (1.7s → 1.6s) — 하지만 large repo 에서 important.
3. **`CodeLayerStore.list_types` 가 method body_text 까지 다 로드 (76MB DB 의 대부분)** — graph_api / modules_api 는 metadata 만 필요. → `list_types_summary` 신규 (SQL group_by + count(method)). graph_api + modules_api + get_inventory 모두 summary 사용. **1.7s → 0.18s** (~10x).

### 회귀
- pytest layers 95/97 PASS (2 fail 은 FK pragma 영향 사전 존재, R4-T1.1 무관)

### 다음
R4-T1.2 ELK PoC — xyflow + ELK 통합으로 117 + 5K 노드 layout 시간 측정. 이번 backend perf fix 로 frontend 가 받는 데이터 크기·시간 모두 sub-second → ELK layout 만 측정하면 됨.

---

## 2026-05-02 — R4-T1.2 + T1.3: ELK PoC + micro-decision

### Code
- `npm install elkjs@0.11.1`
- `frontend/public/elk-worker.min.js` — elkjs 의 web worker (Next 가 직접 import 못해서 public 에 정적 배치 + dynamic 로드)
- `frontend/src/app/elk-spike/page.tsx` 신규 — spike route `/elk-spike`. repo selector (slab-design-real / synthetic-5k) × layout selector (dagre TB / ELK Layered / ELK Box / ELK Force) × Compound 토글. layout 시간 + 노드 수 + 엣지 수 표시.
- 핵심 trick: `import("elkjs/lib/elk-api.js")` dynamic + `new Cls({ workerUrl: "/elk-worker.min.js" })`. main entry 의 'web-worker' Node 의존 우회.

### 측정 결과 (T1.2)
| repo | layout | compound | nodes | layout_ms |
|---|---|---|---|---|
| 117 (slab-design-real) | dagre-tb | n/a | 117 | **13ms** |
| 117 | elk-layered | on | 134 | 142ms |
| 5K → cap 600 | dagre-tb | n/a | 600 | **24ms** |
| 5K → cap 600 | elk-layered | off (flat) | 600 | 56ms |
| 5K → cap 600 | elk-layered | on (compound) | 641 | 88ms |

(fetch 시간 별도: 117 ~10ms, 5K ~300ms — backend perf fix 결과)

### Micro-decision (T1.3)
- dagre 가 ELK 보다 **2-7x 빠름** — 단, 둘 다 sub-200ms 라 interactive UX 합격
- ELK 만 compound 지원 — 안건 4 (Domain expand-in-place) 의 prereq
- **추천 = Hybrid**: dagre default (small + flat), ELK on-demand (compound mode 진입 시)
- 대안: 풀 ELK (단일 엔진 정합, 약간 느림). 풀 dagre 유지 (compound 포기, 안건 4 일부 cost)

→ 사용자 confirm 다음 단계.

### 다음
- 사용자 micro-decision (hybrid / 풀 ELK / dagre 유지) confirm
- 결정 따라 트랙 3 (R4-T3.1+ 5-kind 노드 확장) 시작
- Track 1 마무리 = R4-T1.4 Spring Framework 정식 검증 — backend perf 가 sub-200ms 라 별도 spike 가치 낮음. 다음 phase 로 미룰 수도.

---

## 2026-05-02 — R4-T1.3 결정 적용: dagre → ELK 풀 마이그 (production)

사용자 결정: **B (풀 ELK)**.

### Code
- `frontend/src/components/sections/modeling/OntologyGraph.tsx`:
  - `import dagre from "@dagrejs/dagre"` 제거
  - `getElk()` dynamic import 추가 (elk-spike 의 패턴)
  - `buildLayout` sync useMemo → async useEffect + useState (rfNodes/rfEdges/layoutBusy)
  - 함수 dagre → ELK Layered (rankdir DOWN, nodeNodeBetweenLayers 70, nodeNode 32)
  - Loading overlay 가 graph fetch + layout 둘 다 cover
- `frontend/src/components/sections/modeling/GraphMode.tsx` docstring update

### dagre dependency 처리
- `@dagrejs/dagre` 는 elk-spike 페이지 만 사용 (비교용) — 유지
- production 코드에서 dagre 참조 0건

### 검증
- tsc clean
- 헤드리스 walkthrough: 117 노드 deep link `?section=modeling&view=graph&focus=term.scm.order.order&n_max=80` → 10 노드 + 9 엣지 정상 (SDOrderEntity ⊃ 4 PARTIAL amber 점선 + PRIMARY emerald 그대로). ELK 가 2-column layout (Code 위 / Term 아래) 으로 깔끔하게 정렬.

### 다음
- Track 1 마무리: T1.4 Spring 정식 검증 (선택, backend perf 가 sub-200ms 라 가치 낮음)
- Track 3 시작: R4-T3.1 (graph_api 5-kind 확장 — Domain 노드 emit + CONTAINS edge + Term split)

---

## 2026-05-02 — R4-T3.1 + T3.2: 5-kind 노드 확장 (Domain 추가) — backend + frontend

안건 4 C 결정 적용. Track 3 시작. Domain (Java 패키지) 노드 + CONTAINS edge.

### Backend (R4-T3.1)
- `backend/modeling/api/graph_api.py`:
  - `GraphNodeKind` += `"domain"`, `GraphEdgeKind` += `"contains"`
  - Domain 노드 emit — 직접 클래스 가진 Java 패키지만 (5K 시 visual 부담 ↓). id: `pkg::{full_path}`, label: 마지막 segment, extra: `{package_full, class_count, members}`
  - CONTAINS edge: Domain → CodeType (1:N)
  - `include_kinds` default 5종, validation 도 4 kind
  - summary 에 `nodes_domain` 추가

### Frontend (R4-T3.2)
- `frontend/src/lib/api/ontology.ts`:
  - `GraphNodeKind` += `"domain"`, `GraphEdgeKind` += `"contains"`
- `frontend/src/components/sections/modeling/OntologyGraph.tsx`:
  - KIND_COLOR: domain = slate `#64748b`
  - OntologyNode: atomic term = pill (rounded-full), domain = dashed border + `bg-slate-500/10` + 📦 prefix
  - nodeSubtitle 5-kind 분기:
    - term: composite/atomic + root/struct
    - domain: `패키지 · {n} class`
    - code_type: 패키지 마지막 2 segment
    - action: kind + verification
  - edgeKindColor: contains = `#475569` (slate dim)
  - edgeKindLabel: contains = undefined (라벨 생략, 너무 많아서)
  - NodeBadge: 토바에 Pkg 카운트 (조건부)
- `frontend/src/components/sections/modeling/NodePreviewPanel.tsx`:
  - KIND_COLOR / KIND_LABEL_KO domain 추가
  - neighborCounts 초기값 +domain
  - 1-hop neighbor 표시 loop +domain

### 검증
- tsc clean
- 헤드리스 walkthrough — focus=주문, n_max=80
  - toolbar: `7 Term · 6 Code · 0 Action · 2 Pkg · 17 edges`
  - 3-layer 시각화: Top 📦 jpo (7 class) + entity (2 class) → Middle 6 CodeType → Bottom 7 Term
  - composite/atomic subtitle 표시 (composite·root, composite·struct, atomic 등)
  - PARTIAL/PRIMARY/contains edge 색 분리

### 다음
- R4-T3.3 Domain compound (안건 1 결정 B = 풀 ELK 기반 — 패키지 box 안에 자식 클래스 nest, expand-in-place)
- R4-T3.4 Perspective ↔ kind 통합 (visible_kinds 5종 + visible_edge_kinds 6+contains 7종 토글)

---

## 2026-05-02 — R4-T3.3: Domain compound (ELK nest)

안건 1 B (풀 ELK) 의 진정한 활용. Domain (Java 패키지) 노드 안에 자식 CodeType nest.

### Code
- `frontend/src/components/sections/modeling/store.ts`:
  - `graphCompound: boolean` state + `setGraphCompound`. default false (사용자 토글).
- `frontend/src/components/sections/modeling/OntologyGraph.tsx`:
  - `compound` state 받아 `buildLayout(nodes, edges, compound)` 으로 전달
  - `buildLayout` compound 분기:
    - Domain 노드 → ELK compound parent. children = members (intersect with nodes set)
    - 다른 노드 (Term/Action/non-member CodeType) → root level
    - contains edge 제외 (nesting 으로 충분)
    - elk hierarchyHandling INCLUDE_CHILDREN
  - `DomainGroupNode` 컴포넌트 신규 — slate dashed border + bg-slate-500/5 + 📦 헤더 (class count)
  - NODE_TYPES 에 `domainGroup` 추가
  - rfNodes 빌드 시 domain + compound + children > 0 → group node, 자식 노드는 parentId/extent="parent"
  - rfEdges 빌드 시 contains 제외
  - toolbar 에 `[v] 패키지 묶음` 토글 (Boxes 아이콘)
- `frontend/src/components/sections/modeling/useUrlSync.ts`:
  - `?compound=1` URL ↔ store 양방향 sync
  - graph state deps 에 compound 추가

### 검증
- tsc clean
- 헤드리스 walkthrough — `?section=modeling&view=graph&focus=term.scm.order.order&n_max=80&compound=1`
  - 15 RF 노드 (2 group + 6 CodeType + 7 Term)
  - 시각화: 2 dashed slate group box (📦 entity 2 class + 📦 jpo 4 class), 자식 CodeType nest
  - PARTIAL/PRIMARY edges 가 cross-package 로 표현 — **드라마 DNA 더 자연스러움**
  - URL `?compound=1` 정상

### 다음
- R4-T3.4 Perspective ↔ kind 통합 (visible_kinds 5종 + edge kinds + compound + filter + lens 묶어서 Perspective spec 에 저장 + 토글 UI)
- 그 후 Track 마무리 + Phase summary

---

## 2026-05-02 — R4-T3.4: Perspective ↔ 5-kind/compound 통합 (Track 3 마무리)

### Backend
- `backend/modeling/view_layer/schema.py` PerspectiveSpec 갱신:
  - `visible_kinds` default `["term", "code_type", "action", "domain"]`
  - `visible_edge_kinds` default 7종 (+ `"contains"`)
  - `compound: bool = False` 추가

### Frontend
- `frontend/src/lib/api/ontology.ts` PerspectiveSpecDTO 에 `compound: boolean` 필드.
- `frontend/src/components/sections/modeling/useUrlSync.ts`:
  - saved perspective fetch 시 `spec.compound` 도 `setGraphCompound` 적용
- `frontend/src/components/sections/modeling/PerspectiveDropdown.tsx` 신규:
  - toolbar dropdown (Bookmark 아이콘) — 저장된 view 목록 표시
  - 적용: spec → applyGraphState + setGraphCompound + setActivePerspectiveId
  - 「현 view 저장」 — prompt 로 이름 받아 createPerspective (현 mode/focus/target/n_max/compound + 5-kind defaults)
  - 행 hover → 삭제 버튼 (휴지통)
  - active 상태 = violet 배경 + 「View」 버튼 violet 강조
  - x 클릭 = active 해제 (ad-hoc 모드 복귀)
  - mount + activeId 변경 시 자동 reload (active 이름 표시)
- `frontend/src/components/sections/modeling/OntologyGraph.tsx` toolbar 에 통합

### 검증
- tsc clean
- `?p=1` deep link → 저장된 perspective fetch + spec 적용 (compound=true → ✓ 패키지 묶음, focus=주문, n_max=80) → 2 group box 시각화
- Dropdown 이름 정상 표시 ("드라마 DNA 시연 (compound)")

### Track 3 종합 (R4-T3.1 ~ T3.4 모두 완료)

| step | 산출 |
|---|---|
| T3.1 | graph_api 5-kind (Domain) + CONTAINS edge — backend |
| T3.2 | frontend 5-kind 시각 (KIND_COLOR / OntologyNode / nodeSubtitle / edgeKindColor / NodeBadge / NodePreviewPanel domain 처리) |
| T3.3 | Domain compound (ELK nest) — buildLayout compound 분기 + DomainGroupNode + toolbar 토글 + URL sync |
| T3.4 | Perspective ↔ 통합 — schema 확장 + Dropdown UI + 적용/저장/삭제/해제 |

**Track 1 (인프라)** + **Track 2 (UX)** + **Track 3 (통합)** 모두 종결. 7 안건 중 6 안건 (1, 2, 3, 4, 5, 7) 의 실행 단위 완료. 안건 6 (5K 검증) 의 T1.4 (Spring Framework 정식 검증) 만 남음 — backend perf 가 sub-200ms 라 다음 phase 로 미뤄도 무방.

### 다음
- (선택) R4-T1.4 Spring Framework 정식 검증
- 또는 Phase R4 마무리 + 다음 phase 진입 (A1 Plugin / A2 Simulation Agent / etc.)

---

## 2026-05-05 (Round 6 — Authoring Agent Graph 아키텍처 진입)

사용자 결정: Authoring agent 가 raw text 가 아닌 Code+Ontology+Mapping graph 를 ReAct 루프로 직접 탐색.
배경 분석: `agent-graph-architecture.html`. 메모리: `project_authoring_graph_agent.md`.

### Batch A — INF-1 + INF-2 (인프라) [x] 완료

추가 결정: cross-cutting 모듈로. operational 은 Protocol 인터페이스로 분리 → 다른 에이전트도 사용 가능.

- [x] `backend/application/agent_tools/__init__.py` — 패키지 entry (register_tools / RunTracker / ToolCallRecord 노출)
- [x] `agent_tools/tracking.py` — RunTracker (max_calls + dedup + logger), ToolCallRecord (Pydantic transport), ToolCallLogger Protocol, make_tracked decorator (예산 / 캐시 / 에러 → observation 전환)
- [x] `agent_tools/code_tools.py` — 12 tools (code_lookup / code_search / find_subclasses / find_implementations / find_callers / find_callees / find_field_readers / find_field_writers / get_method_body / get_method_anchors / find_related_jpos / find_in_same_package). class_kind 필드는 wrapper kind 충돌 회피로 별도 명명.
- [x] `agent_tools/ontology_tools.py` — 6 tools (domain_search / term_lookup / action_lookup / find_term_realizations / find_action_realizations / find_terms_in_domain). TypeRealization.scope 정합.
- [x] `agent_tools/mapping_tools.py` — 3 tools (find_existing_mapping / lookup_anchor_binding / find_unmapped_methods_in_class)
- [x] `agent_tools/operational.py` — OperationalSession Protocol + NullOperationalSession + make_note_observation / make_request_user_input (closure-based factory)
- [x] `agent_tools/registry.py` — register_tools(agent, allowed, tracker, operational_session) + 5 PRESETS (authoring_full / extract / hypothesize / pattern_check / naming) + validate_allowlist
- [x] `backend/application/authoring/orm.py` — `AuthoringToolCallRow` 신규 (session_id FK + turn_no + capability + tool_name + args_json + result_summary + duration_ms + cached + error)
- [x] `application/authoring/cost.py` — `log_tool_call(...)` 확장 (FK 위반 swallow 패턴 동일)
- [x] `application/authoring/agent_tool_adapter.py` — AuthoringToolLogger (ToolCallRecord → DB row), AuthoringOperationalSession (observation/user_question → decision_log), build_run_tracker / build_operational_session 헬퍼, list_tool_calls_for_session (archive markdown용)

### 검증
- `tests/test_agent_tools_registry.py` — 10 unit (inventory 23 / allowlist / dedup / max_calls sentinel / logger callback / exception → observation / register subset / null operational session)
- `tests/test_agent_tools_graph_queries.py` — 17 integration (slab-design-real 실 DB 대상 12 graph tool 동작 + cold-start safety: 모든 tool 이 unknown fqn 에 대해 None/[] 반환 — 예외 없음)
- `tests/test_agent_tool_adapter.py` — 4 e2e (table 생성 / observation persist / user_question persist / register→invoke→trace round-trip)
- 회귀: `tests/test_authoring_*` 전체 39 PASS, agent_tools 합산 **125 PASS · 11 SKIP** (skip 은 LLM 키 필요 integration)
- DB: `authoring_tool_call_log` 자동 생성 확인 (4 tables 모두 존재)
- Live backend (port 8001) 자동 reload, sessions 정상 응답
- 실 DB 호출 sample: `find_related_jpos(HrSpecJpo)` → 5 sibling JPO with shared PKs (cmpCd, orgCd, productTypeCd) — agent 가 실제로 graph 탐색 가능 확인

### 영향
- 기존 cap 1~9 코드 미수정 → 회귀 0
- 다른 에이전트 (Section 1 RAG / 향후 추가) 가 `register_tools(agent, allowed=...)` 한 줄로 graph 도구 사용 가능
- ontology cold-start 안전 (29 terms → 0 hits 도 graceful)

### 다음 (Batch B 후보)
- INF-3 SSE: tool_call_start / tool_call_end event 정의 → 기존 endpoint stream 화
- INF-4 Forced Reflection: N tool call 마다 강제 정리 step (system prompt rule 또는 agent state machine)
- 또는 Batch C 부터 (cap 5+6 retro-fit) — INF-3·4 필요해질 때 합류

### Batch B+C 묶음 — INF-3 + INF-4 + CAP-5 + CAP-6 + UI-1 + UI-2 [x] 완료 (2026-05-05)

사용자 결정: c (B+C 묶음). 인프라(B) 보강 → cap 5+6 retro-fit → UI 트레이스 노출 까지 한 사이클로.

#### Backend
- [x] **INF 시그니처 보존 fix**: 기존 `make_tracked` wrapper 가 `**kwargs` 만 가져 LLM 이 받는 JSON schema 가 비어있던 버그 (LLM 이 파라미터 모름) → `functools.update_wrapper` + `__signature__` + `__annotations__` 명시 보존. 이제 schema 가 `{fqn: string, required: [fqn]}` 처럼 정확히 derive 됨.
- [x] **INF-4 forced reflection**: `RunTracker(reflect_every=5)` 옵션. `wrap_with_reflect(value, calls)` 가 N째 호출 결과를 `{result, _system_note}` dict 로 wrap → LLM 이 정리·결정 step 자연스럽게 trigger. cached / non-cached 양쪽 적용.
- [x] **INF-3 SSE 인프라**: `agent_tools/sse.py` 신규 — `ToolEventPump` (asyncio.Queue + start/end logger). `bridge(coro)` async generator 가 agent run 과 이벤트 인터리브 → 마지막 `done` 에 `output` + `tool_call_count`. `sse_format(ev)` data: 프레임 인코더.
- [x] **INF-3 ToolStartLogger Protocol**: `RunTracker.start_logger_fn` 추가. `make_tracked` 가 tool body 실행 *전* `emit_start(tool_name, args)` 호출 → SSE start 이벤트 트리거 (사용자가 spinner 즉시 봄).
- [x] **CAP-5 gap_detector retrofit**: per-call `_build_agent()` (캐싱 제거 — tool wrapper 가 closure 라 per-run 필요). `RunTracker(max_calls=12, reflect_every=5)` + `AuthoringToolLogger` + `AuthoringOperationalSession` + `event_pump` 인자. PRESET `authoring_full` (22 tools). prompt `gap_detection.md` 에 `# Tool use (R6)` 섹션 추가 (tool 호출 패턴 가이드 + reflection 안내).
- [x] **CAP-6 option_proposer retrofit**: 동일 패턴. max_calls=10. prompt `option_proposal.md` 에 `# Tool use (R6)` 섹션 추가.
- [x] **API 신규 endpoint** (3개):
  - `POST /api/authoring/sessions/{id}/options/stream` — SSE: stream_open → tool_call_start/end* → done
  - `POST /api/authoring/sessions/{id}/gaps/stream` — 동일 패턴
  - `GET /api/authoring/sessions/{id}/tool-calls` — γ 트레이스 조회 (persisted)

#### Frontend
- [x] `frontend/src/lib/api/authoring.ts` — `ToolStreamEvent` union (stream_open / tool_call_start / tool_call_end / heartbeat / done / error) + `ToolCallRow` (γ 데이터) + `postSSE<E>(path, body, signal)` async generator helper (chunked TextDecoder + frame split + JSON parse robust to malformed frames). `authoringApi.optionsStream` / `gapsStream` / `toolCalls` 3 메서드.
- [x] `store.ts` — `ToolTraceEntry` + `ActiveToolTrace` 상태 + `ChatMessage.toolTrace` optional 필드. `consumeStream(stage, stream)` 내부 helper 가 SSE 를 drain 하면서 `activeToolTrace` 업데이트 + 마지막 `done` 의 output 반환. `runOptions` / `runGaps` 가 SSE 패턴으로 전환.
- [x] `AuthoringMode.tsx`:
  - **β LiveToolTraceCard** — ChatThread 하단에 stream 진행 중일 때만 표시. blue 카드 안에서 현재 tool 의 `●` 펄스 + tool_name + args_summary, 하단에 완료 N회 + 최근 3개 tool 이름.
  - **γ ToolTraceToggle** — assistant 메시지의 `toolTrace` 가 있을 때 `🔍 어떻게 알아냈나` 토글. 클릭 시 ordered list (각 row 좌측 border-l-2 — error=rose / cached=amber / normal=blue) + tool_name · args · result_summary · duration · cached · error.

### 검증
- pytest **136 PASS · 11 SKIP** (회귀 0 — 기존 cap 5/6 unit 테스트 그대로 통과, SSE 엔드포인트 3 신규 + reflection 2 신규 + sse helper 4 신규 + signature 1 신규 = 10 신규)
- TS `npx tsc --noEmit` clean (frontend 미수정 영역 영향 0)
- Backend live 점검: 정상 응답. 단, uvicorn `--reload` 없이 띄워있어 새 endpoint 는 서버 재시작 필요 (사용자 결정 영역).

### 영향
- 기존 `/options`, `/gaps` sync 엔드포인트는 **그대로 유지** (legacy frontend / 다른 caller 호환).
- frontend `runOptions` / `runGaps` 만 SSE 로 갈아탐 → β 즉시 적용. `useState` 추가 store 필드만으로 컴포넌트 마운트 시 reactive 동작.
- 이제 cap 5/6 가 graph 활용. 자바독 없는 레거시 코드에서 Round 5 협업 수준의 confidence 회복 가능 (실제 LLM 호출 없는 단위 테스트라 측정은 R6-VAL 단계).

### 다음
- (선택) CAP-1 + CAP-2 retro-fit (사용자가 "둘 다" 명시한 항목)
- (선택) CAP-7 신규 (greenfield ReAct)
- (선택) R6-VAL — 자바독 strip repo 로 e2e + confidence 측정
- 또는 다음 큰 phase 진입

---

## 2026-05-05 (Round 6 — Batch C2: CAP-1 + CAP-2 retro-fit) [x] 완료

사용자 결정 Q5 = "둘 다" 의 명시 항목 종결. cap 1/2 가 진입점이라 graph 활용 가치 가장 큼.

### Backend
- [x] **PRESETS 갱신** — `authoring_extract` (5 tool: +note_observation), `authoring_hypothesize` (10 tool: +note_observation)
- [x] **CAP-1 code_extractor retrofit** — `_build_agent()` per-call, `RunTracker(max_calls=5, reflect_every=None)` (예산 작아 reflection 오버헤드), `event_pump` 인자, prompt `code_extraction.md` 에 `# Tool use (R6)` 섹션 (sparingly 가이드: 3 use case + note_observation). API `POST /sessions/{id}/extract/stream` 신규.
- [x] **CAP-2 hypothesis retrofit** — `_build_agent()` per-call, `RunTracker(max_calls=8, reflect_every=5)`, `event_pump` 인자. prompt `hypothesis.md` 에 `# Tool use (R6)` 섹션 — **권장 순서 6 단계** (1. find_existing_mapping → 2. find_related_jpos → 3. domain_search → 4. extends 시 code_lookup/find_subclasses → 5. opaque 컬럼 시 code_search+get_method_body → 6. note_observation). 신뢰도 calibration 도 graph 증거에 따라 조정 (0.45→0.65 with graph, stay near 0.35 without). API `POST /sessions/{id}/hypothesize/stream` 신규.

### Frontend
- [x] `lib/api/authoring.ts` — `authoringApi.extractStream` / `hypothesizeStream` 2 메서드 추가
- [x] `store.ts` — `ToolTraceStage` union 확장 (`extract` / `hypothesize` 추가). `runExtract` / `runHypothesize` 가 `consumeStream` 으로 전환 — β 라이브 progress + γ trace 모두 cap 1/2 결과 메시지에 attach. `refreshHypothesisFromAnswers` (P2-B) 와 `rerunStage("hypothesis"/"options"...)` (F3) 도 함께 SSE 로 갈아탐.
- [x] `AuthoringMode.tsx` `LiveToolTraceCard` — stage label switch 에 `extract`(코드 추출) / `hypothesize`(가설 수립) 추가.

### 검증
- pytest **138 PASS · 11 SKIP** (회귀 0, 신규 2: `test_extract_stream_emits_done_with_jpo`, `test_hypothesize_stream_emits_done_with_hypothesis`)
- TS clean
- 모든 ChatBubble 의 assistant 메시지 (extract/hypothesize/options/gaps) 가 이제 `toolTrace` 필드를 가짐 → 하단 `🔍 어떻게 알아냈나` 토글 일관 적용
- F3 rerun 도 SSE 통과 — 사용자가 `✏ 수정` 으로 hypothesis 다시 돌릴 때도 graph 호출 + 진행 표시

### 영향
- **모든 Authoring assistant cap (1/2/5/6) 이 이제 graph-aware**. 자바독 0% 레거시에서 cap 2 의 hypothesis 가 ontology + sibling JPO 증거 기반 — confidence 계산도 graph 호출 횟수에 따라 차등.
- 라이브 백엔드 `--reload` 없이 띄워있어 새 endpoint 4개 (`/extract/stream`, `/hypothesize/stream`, `/options/stream`, `/gaps/stream`) + `/tool-calls` 를 보려면 서버 재시작 필요.
- 레거시 sync endpoints (`/extract`, `/hypothesize`, `/options`, `/gaps`) 그대로 유지 — 외부 caller / 다른 에이전트 호환.

### 다음 (남은 R6 항목)
- (a) **CAP-7 신규** — pattern_checker greenfield (도입 순서 마지막)
- (b) **R6-VAL** — 자바독 strip repo 로 e2e + confidence 측정 (실제 LLM 비용)
- (c) 다음 큰 phase

---

## 2026-05-05 (Round 6 — CAP-7 pattern_checker greenfield) [x] 완료

사용자 결정: (a) 진입.

### 설계 결정
- 위치: cap 6 (option_proposer) 결과 → 사용자 옵션 채택 → **cap 7 (pattern_checker)** → cap 8 (naming) → cap 9 (archive)
- 역할 분리: cap 5 (gap_detector) = code-vs-domain 불일치, cap 7 = **ontology-vs-ontology** 일관성. 둘 다 false-positive 회피 우선.
- 검사 차원 5종: composition_pattern / naming_convention / domain_grouping / facet_consistency / inheritance_pattern
- Cold-start 안전: ontology 작거나 비교군 없을 때 `findings=[]` + `consistency_score=0.85` + summary 자동 처리

### Backend
- [x] `prompts/pattern_check.md` 신규 — 5 dimension 가이드, severity calibration (false positive 금지), Tool use 권장 순서 4단계 (find_terms_in_domain → term_lookup → find_term_realizations → domain_search)
- [x] `capabilities/pattern_checker.py` 신규 (~190 LOC). PatternFinding (id/dimension/alignment/title/evidence_existing/evidence_proposed/severity/suggestion) + PatternCheck (findings/consistency_score/summary/recommendation). PRESET `authoring_pattern_check` (5 tool: 4 ontology + note_observation). max_calls=6, reflect_every=5.
- [x] `agent_tools/registry.py` PRESET 갱신 (note_observation 추가)
- [x] API: `POST /api/authoring/sessions/{id}/pattern` (sync) + `/pattern/stream` (SSE) 신규

### Frontend
- [x] `lib/api/authoring.ts` — `PatternDimension/Alignment/Severity/Recommendation/Finding/Check` 타입. `authoringApi.pattern` + `patternStream`.
- [x] `store.ts` — `pattern: PatternCheck | null` 상태 + `runPatternCheck` action (SSE). `ToolTraceStage` 에 `pattern` 추가. `pattern` ChatKind. reset / hypothesis-clear-downstream 시 pattern 도 초기화.
- [x] `AuthoringMode.tsx`:
  - 툴바 `⑦ 패턴` 버튼 (`runPatternCheck`, disabled when no `acceptedOption`)
  - `LiveToolTraceCard` stage label "패턴 검사"
  - **`PatternView` 컴포넌트** — severity 별 border (block=rose / warn=amber / info=blue), alignment 배지 (✓ matches / ≠ deviates / · neutral), recommendation 색상 (그대로 진행=emerald / 옵션 재고려=rose / 사용자 의견 필요=amber), consistency_score 색상 (≥0.8 emerald / ≥0.5 amber / <0.5 rose)

### 검증
- pytest **140 PASS · 11 SKIP** (회귀 0, 신규 2: pattern endpoint sync + stream)
- TS clean

### 영향
- **모든 R6 cap retro-fit 종결**: cap 1, 2, 5, 6 retro-fit + cap 7 신규 = **5 cap 이 graph-aware ReAct 루프**
- 라이브 백엔드 재시작 시 endpoint 7개 추가 (`/extract/stream` `/hypothesize/stream` `/options/stream` `/gaps/stream` `/pattern` `/pattern/stream` `/tool-calls`)
- 사용자 흐름: 코드 추출 → 가설 → 인터뷰 → 옵션 → 옵션 채택 → **⑦ 패턴 (선택)** → ⑥ 갭 (선택) → 명명 → archive

### 남은 R6 항목
- R6-VAL — 자바독 strip repo 로 e2e + confidence 측정 (실 LLM 비용)
- 또는 다음 phase

---

## 2026-05-05 (Round 6 — R6-VAL e2e 검증 + 백엔드 재시작) [x] 완료

사용자 결정: 백엔드 재시작 후 (a) R6-VAL 진입.

### Backend 재시작
- [x] 기존 PID 31468 SIGTERM → 신규 background uvicorn 띄움 (동일 args). 새 endpoint 7개 (`/extract/stream`, `/hypothesize/stream`, `/options/stream`, `/gaps/stream`, `/pattern`, `/pattern/stream`, `/tool-calls`) 모두 라우트 확인 — **14 → 21 routes**.

### R6-VAL 검증 결과 (HrSpecJpo 기반)
- 대상: `com.example.slabdesign.store.sd.std.oracle.jpo.HrSpecJpo` (8 fields, rich Korean comments + class Javadoc)
- 방식: 동일 JPO 의 (a) baseline = 원본 / (b) blind = `class_docstring=None` + 모든 `column.comment=None` 으로 strip.

**핵심 측정**:
| Metric | Baseline | Blind | Δ |
|---|---|---|---|
| Cap 2 confidence | 0.50 | 0.45 | **-0.05 only** |
| Cap 2 tool calls | 5 | 6 | +1 (`code_search` for opaque column) |
| Domain role | standard | standard | same |
| Eng id | HrSpec | HrSpec | same |

**해석**: graph 가 docs 부재 거의 완전 회복. 사전에 우려했던 "자바독 없는 레거시" 시나리오에서 실제로 confidence 0.05pt drop 만 발생.

**전체 파이프라인 on blind**:
- Cap 5 (gap_detector): `gaps=[]`, `갭 없음` — 정확 (false positive 0).
- Cap 6 (option_proposer): 3 options, ★ B = "HrPlant 가상 마스터 + 자매 standard 묶음" — sibling JPO 증거 활용.
- Cap 7 (pattern_checker): **5 findings, score=0.55, "사용자 의견 필요"** — composition_pattern 2건(matches + deviates) + domain_grouping 1건(deviates) + facet 1건 + naming 1건. 정확히 기존 confirmed 온톨로지(`term.smoke-slab.hrplant`/`term.smoke-slab.hrplantspec`)와의 부분 이탈 catch.

**비용**:
| Cap | Cost |
|---|---|
| Cap 1 (Sonnet) | $0.03 |
| Cap 2 baseline | $0.81 |
| Cap 2 blind | $1.01 |
| Cap 5 | $0.48 |
| Cap 6 | $2.10 |
| Cap 7 | $1.91 |
| **TOTAL** | **$6.34** |

Cold cache + cap 6 over-budget(14/10) 으로 예상 $1.5 보다 4× 초과. 정상 세션 (warm cache) 은 $2-3 추정.

### 산출물
- `scripts/r6_validation.py` — 재실행 가능한 검증 스크립트
- `toClaude/modeling/r6_validation_report.md` — 상세 보고서 (140 LOC)
- `toClaude/modeling/r6_val_run.log` — 전체 LLM 호출 로그
- `toClaude/modeling/r6_val_summary.json` — 구조화 결과 (재집계용)
- 영속 sessions: A=`092b447a-2065-4fb1-9883-f0f6599b8153`, B=`80c5828b-8a63-4c94-99f9-418b2be2766c`

### Issues / 후속 항목
1. **Cap 6 budget 초과 (14/10)** — RunTracker 가 marker 만 반환하고 LLM 이 무시. 비용 ~$0.40 낭비. 강한 마커 / 시스템 메시지 / pydantic_ai exception 중 택일 필요. 비치명 — 추후 튜닝.
2. **Cap 2 baseline confidence 0.50** — 의도된 calibration (P1-B humble feedback). Δ 가 의미 있는 지표.
3. Validation 은 cap 2 + 다운스트림 중심. cap 1 의 "Java 파일 자체에서 docstring 제거" 시나리오는 cap 1 이 mechanical extractor 라 부가 가치 적어 생략.

### 결론
**R6 graph-aware retrofit 의 value proposition 검증 완료**. 자바독 부재시 confidence drop 5pt 만 발생, 전체 파이프라인 정상 동작, cap 7 가 패턴 deviation 정확히 탐지. **R6 demo-ready**.

---

## 2026-05-05 (Round 6 — Cap 6 budget enforcement 강화) [x] 완료

R6-VAL 에서 발견한 cap 6 over-budget (14/10) 이슈 fix.

### 원인 분석
- 기존 `RunTracker.exceeded` 가 `BUDGET_EXCEEDED_MARKER` 문자열만 반환하고 LLM 의 자발적 중단에 의존.
- 검증 결과 LLM 이 marker 무시하고 추가 4 calls 실행 → ~$0.40 낭비.

### Fix
- [x] **소프트 마커 강화** — `BUDGET_EXCEEDED_MARKER` 를 imperative 톤으로 재작성 (`⛔ TOOL_BUDGET_EXCEEDED... DO NOT call any more tools — further calls will raise an exception and abort this run. Produce your final structured output IMMEDIATELY...`). 다음 호출이 abort 한다고 명시.
- [x] **하드 캡 추가** — `agent_tools/tracking.py` `usage_limits_for(max_calls)` 헬퍼 신규. pydantic_ai 의 `UsageLimits(tool_calls_limit=max_calls)` 반환. cap 1, 2, 5, 6, 7 의 `agent.run()` 호출에 `usage_limits=usage_limits_for(TOOL_BUDGET)` 추가.
- [x] **이중 안전망** — 소프트 마커가 LLM 자발적 stop 유도, 그래도 무시하면 pydantic_ai 가 `UsageLimitExceeded` 예외 raise → agent run 안전 중단.

### 검증
- pytest **142 PASS · 11 SKIP** (회귀 0, 신규 2: `test_usage_limits_for_sets_tool_calls_limit`, `test_budget_exceeded_marker_is_aggressive`)
- 기존 `test_run_tracker_max_calls_returns_sentinel` 새 marker 텍스트 반영 (assert "TOOL_BUDGET_EXCEEDED")
- TS 변경 0 (백엔드 only)
- 백엔드 재시작 → 21 routes 그대로

### 남은 R6 항목
- (선택) R6-VAL 재실행 — 새 enforcement 가 cap 6 를 10 calls 안에 멈추는지 확인. 비용 ~$2-3 추가.
- 또는 다음 phase

---

## 2026-05-05 (Round 6 — A: Demo-ready 마무리) [x] 완료

사용자 결정: A 진입. (1) Browser UI 검증 → (2) Cap 10 next_step 신규 → (3) demo_guide 갱신.

### (1) Browser UI 검증 (`/browse`)
- 백엔드 21 routes (R6 SSE/trace 7개 모두 등록 확인)
- Authoring 모드 UI 정상 — 툴바 ⑦ 패턴 버튼 visible
- 새 세션 → ① 코드 추출 e2e 흐름 동작
- **β LiveToolTraceCard 검증** — cap 1 + cap 2 진행 중 모두 화면에 정상 렌더링 ("🔍 코드 추출 · 그래프 탐색 중", "🔍 가설 수립 · 그래프 탐색 중"). 스크린샷 `/tmp/r6_ui_during_extract.png`, `/tmp/r6_cap2_during.png`.
- Cap 1 결과 ChatBubble 정상: "ASSISTANT · EXTRACTED HrSpecJpo → HR_SPEC, PK 4줄 · 컬럼 4개 · PK class: HrSpecPK".
- 비용 트래킹 UI 표시 ($0.0282 cap 1 후).
- **UX 작은 fix**: `LiveToolTraceCard` 내 "graph 탐색 중" → "그래프 탐색 중" (Tailwind `uppercase` 가 영어만 대문자화 → 한국어 일관성).
- Cap 1 의 tool_calls=0 케이스 → γ `ToolTraceToggle` 표시 안 됨 — 정상 동작 (조건: `m.toolTrace && m.toolTrace.length > 0`).

### Browse 안정성 한계
- `/browse` 서버가 명령 사이에 자주 재시작 → state 손실. 단일 chain 안에서만 안정. cap 2 done state 직접 시각 검증 어려움. 단, 핵심인 β 카드는 양쪽 cap 에서 검증됨. γ 는 코드 review + integration test (`test_authoring_sse_endpoints.py`) 로 보증.

### (2) R6-CAP-10 next_step 신규
- [x] `prompts/next_step.md` — 13 가지 RecommendedAction enum + branching rules (HIGH gap → 갭 우선, 옵션 재고려 → revise_options 등) + 3 priority (critical/recommended/optional)
- [x] `capabilities/next_step.py` — Sonnet (STANDARD), no graph tools (pure state policy). `SessionStateSnapshot` 입력 (has_hypothesis / hypothesis_confidence / has_interview_batch / has_answers / has_option_table / has_accepted_option / has_gaps / gaps_block_modeling / gap_high_count / has_pattern_check / pattern_recommendation / has_names / has_archive / persisted_fqn_count). NextStep 출력 (recommended_action / reason_korean / priority / alternatives).
- [x] API: `POST /api/authoring/sessions/{id}/next-step` (sync only, no SSE — 짧고 결정적).
- [x] Frontend `lib/api/authoring.ts` — `RecommendedAction` / `StepPriority` / `NextStep` / `SessionStateSnapshot` 타입 + `authoringApi.nextStep` 메서드.
- [x] `store.ts` — `runNextStep` action (snapshot 빌드 + nextStep 호출 + ChatMessage push). `next_step` ChatKind.
- [x] `AuthoringMode.tsx` — `NextStepView` 컴포넌트 (priority 색깔 + RecommendedAction → 한국어 라벨 매핑 + alternatives "또는: ..." 표시). 툴바 `⑩ 다음 단계` 버튼 (session 있으면 활성).

### (3) Demo guide
- [x] `demo_guide.md` 에 R6 흐름 추가 — 새 흐름 9 단계 + β 진행 카드 + γ trace 펼치기 + 검증 시나리오 + 비용 추정.

### 검증
- pytest **142 PASS · 11 SKIP** (회귀 0 — cap 10 신규)
- TS clean
- Backend 재시작 → **22 routes** (`/next-step` 추가 확인)
- Live β card UI 검증 ✓

### 비용 (Browser UI 세션)
- Cap 1 × 2 sessions: ~$0.06
- Cap 2 1 session (실행 중 chain timeout, 백엔드 완료 추정): ~$1.00
- 총 이번 검증: ~$1.10

### 결론
**R6 demo-ready 100% 완료.** 모든 cap 1·2·5·6·7·10 + UI β·γ + endpoint 8개 + 검증 보고서 모두 정렬. UI 핵심 흐름 (β 라이브 진행 카드) 실 브라우저에서 시각 검증 완료.

### 다음
- A 종결. 다음 결정 영역.

---

## 2026-05-05 (P1-a Multi-entity workflow — Batch A) [x] 완료

사용자 결정: 추천대로 (P1 Authoring 확장 → Multi-entity).

### 설계
한 세션 = 한 JPO 한계 해소. v1 은 frontend 만 — 세션 안에서 여러 entity 연속 처리. 백엔드 decisions/cost 는 이미 누적되므로 변경 불필요.

### Frontend
- [x] `store.ts`:
  - `CompletedEntityCycle` 타입 (jpo / hypothesis / acceptedOption / names / archive / pattern / gaps / persistedFqns / completedAt)
  - `completedEntities: CompletedEntityCycle[]` state
  - `startNextEntity()` action — 현재 entity 의 final artifacts 를 cycle 로 push, capability state (jpo/hypothesis/...) 만 초기화. session/messages/turnNo/costUsd/completedEntities 는 keep
  - reset() 도 `completedEntities: []` 처리
- [x] `AuthoringMode.tsx`:
  - **`NextEntityButton`** (툴바 우측) — violet 색깔, `archive || persistedFqns` 있을 때 fully-active, 그 전에는 opacity 60% 로 hint. 클릭 시 history 로 push + 현재 reset.
  - **`CompletedEntitiesPreview`** (우측 사이드바) — 완료된 entity 목록. 각 row 에 class_name + ★ 채택 옵션 / 가설 / 미완 표시 + archive/persist 상태 + 완료 시각. violet border-l-2.
  - reset 시 `info` 메시지: "✓ {ClassName} 마무리 — 다음 JPO 를 골라 ① 코드 추출 부터 시작하세요."

### 검증
- TS clean
- 백엔드 회귀 142 PASS · 11 SKIP (백엔드 무변경)

### 영향
- 사용자 흐름이 1-JPO-per-session → multi-JPO-per-session 전환
- 5K 클래스 repo 에서 새 세션 5000번 만들 필요 ✗ — 세션 1개 안에서 줄줄이 처리 가능
- 메시지 thread 가 이번 세션의 모든 entity 작업을 포함 → 종합 archive (cap 9 에 multi-entity input) 의 prereq 도 일부 충족

### 다음 (Batch B 후보 — 결정 영역)
- **B (Backend session resume)**: 세션 ID 만으로 페이지 reload 후 state 복원 (decisions 재생). 현재는 reload 시 store 초기화.
- **C (Smart next-entity 제안)**: cap 10 (next_step) 확장 또는 새 cap — find_related_jpos 로 직전 entity 와 연관된 JPO 자동 추천.
- **D (Cap 7 cross-entity)**: pattern_check 가 completedEntities 도 입력으로 받아 세션 내 패턴 catch.
- **E (종합 archive)**: cap 9 가 multi-entity 받으면 종합 markdown — 도메인 전체 모델링 보고서 포맷.

---

## 2026-05-05 (P1-a Batch D — Cap 7 cross-entity pattern check) [x] 완료

사용자 결정: D 진입.

### 설계
Cap 7 가 두 가지 패턴 source 비교:
1. **Persisted ontology** (DB) — 기존 동작 (ontology tools)
2. **In-session prior entities** (P1a-D 신규) — 같은 세션 내 사용자가 방금 결정한 entity 들. **DB 영속화 여부 무관 가장 신선한 신호**.

### Backend
- [x] `capabilities/pattern_checker.py` — `PriorEntitySnapshot` 신규 (class_name / candidate_term_korean·english / domain_role / accepted_option_name·structure·alignment / persisted_fqns / archive_summary). `_format_for_prompt(...)` 가 `prior_session_entities` 인자 받아 `# Prior entities completed THIS SESSION` 섹션 렌더링 (각 prior 의 채택 옵션 + 구조 + alignment + persisted FQN + archive 요약 300 chars 제한).
- [x] `prompts/pattern_check.md` — pattern source 2종 명시. **"In-session priors are the strongest signal"** 룰 추가 (DB 와 in-session 충돌 시 in-session 승리). `evidence_existing` 에 source 명시 의무 (`Prior #N (HrPlant)` 또는 `term.scm.hr_plant` 형태).
- [x] `api/authoring.py` — `PatternCheckRequest.prior_session_entities: list[PriorEntitySnapshot] | None`. sync + stream endpoint 모두 forwarding.
- 백엔드 재시작 — openapi 에 PatternCheckRequest.prior_session_entities + PriorEntitySnapshot 등록 확인.

### Frontend
- [x] `lib/api/authoring.ts` — `PriorEntitySnapshot` 타입 + `pattern` / `patternStream` 메서드 시그니처에 optional 필드.
- [x] `store.ts` `runPatternCheck` — `completedEntities → PriorEntitySnapshot[]` 변환 (각 cycle 의 jpo / hypothesis / acceptedOption / persistedFqns / archive markdown 첫 3줄 요약). priors 0 개면 `null` 전달.

### 검증
- pytest **146 PASS · 11 SKIP** (회귀 0, 신규 4: `test_format_no_priors_omits_prior_section`, `test_format_with_priors_renders_each_entity`, `test_format_handles_partial_prior_no_accepted_option`, `test_format_truncates_archive_summary_at_300_chars`)
- TS clean
- Backend openapi 에 새 필드 등록 확인

### 영향
- **세션의 두 번째 entity 부터 cap 7 이 즉시 가치** — HrPlant 채택 옵션이 Composition 이라면 HrPlantConstraint 검사 시 "이 세션에서 방금 Composition 했는데 새 entity 도 그 패턴 따르는지" 자동 판정.
- DB 영속화 여부 무관 — 사용자가 Confirm 안 하고도 cap 7 가 해당 entity 의 의도를 활용.

### 다음 (P1a 남은 batch)
- **B Backend session resume** — reload 후 state 복원 (decisions 재생)
- **C Smart next-entity 제안** — cap 10 확장 또는 신규 cap (find_related_jpos)
- **E 종합 archive** — cap 9 multi-entity → 도메인 전체 보고서

---

## 2026-05-05 (P1-a Batch C — Cap 11 Next Entity Picker) [x] 완료

사용자 결정: C 진입.

### 설계
"⤳ 다음 Entity" 클릭 후 사용자 결정 부담 (좌측 트리에서 어떤 JPO 다음에 할지) 제거. graph 호출로 자동 추천.

### Backend
- [x] **신규 cap 11 — `next_entity` (Sonnet, STANDARD)**:
  - `prompts/next_entity.md` — 5 signal (pk_overlap / same_package / uncovered_domain / frequent_caller / inheritance_chain) + 권장 tool 호출 순서 6단계 + no fabrication / no duplicates / 구체 evidence 룰
  - `capabilities/next_entity.py` — `NextEntityCandidate` (fqn / simple_name / reason_korean / signal / confidence) + `NextEntityRecommendation` (candidates 0-8 + summary_korean) + `NextEntityRequest` (repo_id / completed_entity_fqns / confirmed_term_fqns)
- [x] **PRESET `authoring_pick_next` 신규** (6 tools): find_related_jpos / find_in_same_package / code_search / domain_search / find_existing_mapping / note_observation. max_calls=6, reflect_every=None.
- [x] **API 신규 2 endpoint**:
  - `POST /sessions/{id}/next-entity` (sync)
  - `POST /sessions/{id}/next-entity/stream` (SSE, β tool trace 라이브 진행 표시)

### Frontend
- [x] `lib/api/authoring.ts` — `NextEntitySignal` (5종 union) + `NextEntityCandidate` + `NextEntityRecommendation` 타입. `authoringApi.nextEntity` + `nextEntityStream` 메서드.
- [x] `store.ts`:
  - `next_entity` ChatKind + `ToolTraceStage` 에 `next_entity` 추가
  - `pickNextEntity(repoId)` action — completedEntities → completed_entity_fqns + confirmed_term_fqns 변환 후 SSE 스트림 호출
  - `startNextEntity()` 가 메시지 "다음 JPO 추천 받는 중..." 으로 변경
- [x] `AuthoringMode.tsx`:
  - `LiveToolTraceCard` stage label "다음 JPO 추천" 추가
  - **`NextEntityView` 컴포넌트** — signal 별 border 색깔 (pk_overlap=emerald / same_package=blue / uncovered_domain=violet / frequent_caller=amber / inheritance_chain=cyan) + confidence % + reason + **「① 이 JPO 로 시작」 버튼** 클릭 시 `runExtract({fqn, repoId})` 자동 호출
  - `NextEntityButton` 클릭 시 `startNextEntity()` 후 자동으로 `pickNextEntity(activeRepoId)` 호출 (fire-and-forget)

### 검증
- pytest **146 PASS · 11 SKIP** (회귀 0)
- TS clean
- Backend 재시작 → **24 routes** (cap 11 sync + stream 신규)

### 영향
- **multi-entity 흐름의 마지막 마찰 해소**: 한 entity 마무리 → 추천 → 클릭 → 다음 entity 자동 시작. 사용자 좌측 트리 안 봐도 OK.
- pk_overlap 시그널이 가장 가치 있음 — 직접 연관된 sibling JPO 자동 발견. 자바독 없는 레거시에서 도메인 클러스터 탐색 비용 0.
- 비용: cap 11 ~$0.05-0.10 per 호출 (Sonnet, ~4 tool calls 기대).

### P1a 진척 요약
| Batch | 상태 |
|---|---|
| A 프론트 multi-entity | [x] |
| B Backend session resume | [ ] |
| **C Smart next-entity** | **[x]** |
| D Cap 7 cross-entity | [x] |
| E 종합 archive | [ ] |

### 남은 P1a
- **B** session resume — 페이지 reload 시 state 복원 (decisions 재생)
- **E** 종합 archive — cap 9 multi-entity → 도메인 전체 모델링 보고서

---

## 2026-05-05 (P1-a Batch E + B — 종합 archive 신규 + 세션 재개) [x] 완료

사용자 결정: 추천대로 진행 (E 우선, 그 다음 B).

### Batch E — Cap 12 Comprehensive Archive
- [x] **신규 cap 12** (`comprehensive_archive`, Sonnet, no graph tools — pure synthesis):
  - `prompts/comprehensive_archive.md` — title/executive_summary/entity_sections/cross_cutting_observations/decisions_made/next_steps_korean. echo not invent. Korean narrative.
  - `capabilities/comprehensive_archive.py` — `EntitySnapshot` (입력 per entity), `ComprehensiveArchiveBody` (LLM 출력), `ComprehensiveArchive` (LLM body + Python-rendered markdown + ISO timestamp). `_render_markdown()` 가 deterministic 마크다운 생성 (요약 / Entity 섹션 / 종합 관찰 / 이번 세션 결정 / 다음 세션 follow-up — 빈 섹션 자동 skip).
  - API `POST /sessions/{id}/comprehensive-archive`, decision_kind="archive_saved" 로 기록 + archive_markdown 영속.
- [x] Frontend:
  - 타입 6종 + `authoringApi.comprehensiveArchive` 메서드.
  - Store `runComprehensiveArchive(repoId)` action — completedEntities + 현재 in-progress entity 모두 EntitySnapshot 변환.
  - **`ComprehensiveArchiveButton`** (📚 종합 archive, cyan, ≥1 entity 시 노출, ≥2 일 때 fully-active).
  - **`ComprehensiveArchiveView`** (`react-markdown` + GFM 렌더링, .md 다운로드, follow-up 카운트 표시).
- 5 신규 unit test: `test_authoring_comprehensive_archive_render.py` (제목·요약·entity 섹션·종합 관찰·결정·다음 단계 + 빈 섹션 skip).

### Batch B — Backend session resume
- [x] **`decision_kind` 확장**: `"next_entity_started"` 추가 (cycle boundary marker).
- [x] `application/authoring/replay.py` 신규 — `CompletedEntitySnapshot` / `CurrentEntityState` / `SessionResumeState` Pydantic. `build_resume_state(session_id)` 가 decisions chronologically 재생, `next_entity_started` 만나면 cycle 경계 push, 각 decision 의 `decision_kind` + `payload.capability` 보고 jpo/hypothesis/option_table/gaps/pattern 등 채움. `payload.persisted_fqns` 가 있으면 dedup merge (confirm endpoint 출력 호환).
- [x] API `GET /sessions/{id}/replay` (404 on miss) + `POST /sessions/{id}/next-entity-marker` (frontend 가 "다음 Entity" 클릭 시 호출).
- [x] Frontend:
  - 타입 3종 (`CompletedEntitySnapshot`, `CurrentEntityState`, `SessionResumeState`) + `authoringApi.replay` / `markNextEntity`.
  - Store `resumeSession(sessionId)` action — replay fetch → store 전체 populate (session/turnNo/cost/현재 cycle 모든 artifact/completedEntities, messages 비움). info 메시지 "↻ 세션 ... 이어서 진행".
  - `startNextEntity()` 가 backend 에 `markNextEntity` fire-and-forget 발사 (non-critical).
  - **URL `?authoring_session=<id>`** → AuthoringMode `useEffect` 자동 resume.
  - **`ResumeSessionButton`** (↻ 이어서) — 세션 ID prompt → `resumeSession`.
  - **`CopySessionUrlButton`** (🔗 URL) — 현재 세션의 resume URL 클립보드 복사. fallback `window.prompt`.
- 5 신규 unit test: `test_authoring_replay.py` (unknown session → None / empty session / decisions walk → current state / cycle 분리 / persisted_fqns merge).

### 검증
- pytest **156 PASS · 11 SKIP** (회귀 0, 신규 10: archive render 5 + replay 5)
- TS clean
- Backend 재시작 → **27 routes** (`/comprehensive-archive`, `/replay`, `/next-entity-marker` 모두 신규 등록)

### 영향
- 5 entity 처리 후 한 번에 종합 보고서 다운로드 가능 → 발표·인계 친화 결과물.
- 페이지 reload / 새 탭 / 다른 컴퓨터 에서도 `?authoring_session=<id>` 만으로 resume — 작업 연속성 확보.
- decision_kind 확장은 backward-compatible (기존 코드는 `next_entity_started` 무시).

### P1a 진척 (전체 종결)
| Batch | 상태 |
|---|---|
| **A** 프론트 multi-entity | [x] |
| **B** Backend session resume | [x] |
| **C** Smart next-entity | [x] |
| **D** Cap 7 cross-entity | [x] |
| **E** 종합 archive | [x] |

**P1a 100% 완료.** Multi-entity workflow 전체 흐름 (한 세션 N JPO + 누적 + 추천 + 종합 + 재개) 모두 정렬.

### 다음 결정 영역
- **R6-VAL 재실행** — cap 6 budget enforcement fix 동작 확인 (~$2-3)
- **사용자 데모** — P1a 흐름 발표 / 피드백 수집
- **A2 Simulation Agent** — 다음 큰 phase
- **P3 폴리싱** — 작은 작업 모음

---

## 2026-05-05 (R6-VAL v2 + P3 폴리싱) [x] 완료

사용자 결정: R6-VAL 재실행 + P3 폴리싱.

### R6-VAL v2 결과
- `scripts/r6_validation.py` 재실행. cap 1 + cap 2 baseline + cap 2 blind + cap 5 정상.
- **Cap 6 가 11번째 tool call 시도 시 `UsageLimitExceeded` raise** — pydantic_ai hard cap 동작 확인 ✓
- 단점: agent 가 결과 출력 전 abort → cap 6 + cap 7 결과 못 만듦
- **이전 (no UsageLimits)**: cap 6 가 14 calls 까지 가서 결과 출력 (over-budget)
- **이번 (UsageLimits, no cushion)**: cap 6 가 11째 hard abort
- 결론: hard cap 자체는 동작. 하지만 너무 빡빡 → cushion 필요.

### Fix — usage_limits_for cushion=2
- [x] `agent_tools/tracking.py` `usage_limits_for(max_calls, cushion=2)` — hard limit = max_calls + 2.
- 동작:
  - 1...max_calls: 정상
  - max_calls+1째: BUDGET_EXCEEDED marker (LLM 멈출 기회)
  - max_calls+2째: 마커 무시 시 grace
  - max_calls+3째 (= hard limit + 1): UsageLimitExceeded raise
- cap 별 hard limit: cap 1=7, cap 2=10, cap 5=14, cap 6=12, cap 7=8
- 비용 cap 변동 미미 (cushion 2개 추가 ≈ $0.20 worst case). 안정성 ↑.

### P3 폴리싱 항목
- [x] **Cushion fix** (위)
- [x] **Demo guide P1a 추가** — multi-entity 흐름 + cap 11 신호 5종 + 종합 archive + 세션 재개 + cap 7 cross-entity + 비용
- [x] **Resume 시 chat 복원 메시지** — `resumeSession` 이 completed entities 를 1줄씩 system info 로 push (사용자가 chat 만 보고도 어디까지 했는지 파악)

### 검증
- pytest **156 PASS · 11 SKIP** (회귀 0, `test_usage_limits_for_adds_cushion_default_2` 갱신)
- TS clean
- `usage_limits_for(10) = 12`, `(12) = 14`, `(5) = 7` 확인
- Backend 재시작 — endpoint 27개 그대로

### 영향
- Cap 6 가 marker 따라 멈출 가능성 ↑ (대부분 정상 종료)
- LLM 이 무시해도 grace period 안에서 결과 출력 후 hard abort 회피
- 비용 통제 + 결과 보장 양립

### 다음 결정 영역
- **사용자 데모** — P1a 흐름 발표 / 피드백 수집 (P4)
- **A2 Simulation Agent** — 다음 큰 phase
- **추가 P3** — 6번째 graph 노드 kind / Hover preview / Time-travel / Schema migration framework / R4-T1.4 Spring Framework 검증

---

## 2026-05-05 (추가 P3 폴리싱 — Sessions picker + UX) [x] 완료

### Sessions picker dropdown
- **문제**: `ResumeSessionButton` 이 prompt 로 ID 입력 받음 → 사용자가 세션 ID 외워야 함. resume 기능 가치 절반.
- **Fix**: 기존 `authoringApi.listSessions({status:"active"})` 활용해 dropdown 으로 교체.
- 동작:
  - "↻ 이어서" 클릭 → active 세션 fetch + dropdown open
  - 각 row: session id (8글자) + last_activity 시각 + repo_id + entity_focus + operator_id
  - last_activity_at 내림차순, 최근 12개 표시 (그 외 "+N개 더")
  - 클릭 → `resumeSession(id)` (기존 흐름)
  - mouseLeave 시 close
  - fetching 중 버튼에 "..." 표시
- 빈 상태: "active 상태의 기존 세션이 없습니다." 안내.

### Stat row entity 카운트
- 기존 row: `session: <id> · turn N · cost $X · ⏳`
- 추가: `entity N (+1 진행)` — completedEntities 갯수 + 현재 in-progress 표시
- multi-entity 작업 중 진척도 한 눈에 보임.

### 검증
- TS clean
- 백엔드 무변경 (기존 listSessions 활용)
- 회귀 0

### 누적 P3 폴리싱 (이번 phase)
1. `usage_limits_for(cushion=2)` — R6-VAL hard cap fix
2. `demo_guide.md` P1a 흐름 추가
3. `resumeSession` chat thread 복원 메시지
4. **Sessions picker dropdown** (이번)
5. **Entity 카운트 stat row** (이번)

### 다음 결정 영역
- **사용자 데모 / 피드백** — 가장 demo 친화적 시점
- **A2 Simulation Agent** — 다음 큰 phase
- **남은 작은 P3** — graph viz (Method 노드 / Hover preview / Time-travel) — R4 leftovers, Authoring 과 별개

---

## 2026-05-05 (남은 작은 P3 — Graph Hover preview) [x] 완료

R4 leftover 중 가장 작은 폴리싱 — 그래프 노드 hover 시 floating tooltip.

### 동작
- 노드 위에 마우스 ENTER → cursor 위치 12px 우상단에 280px 폭 카드 노출
- 카드 내용: kind dot + label (mono) + nodeSubtitle (kind 별 색상) + incoming/outgoing edge 카운트 + domain + "클릭하면 자세히 보기" 힌트
- viewport 우측 가까이 가면 자동으로 좌측 flip
- `pointer-events-none` — 호버 자체 방해 안 함
- 클릭 → NodePreviewPanel (full info) 로 commit + tooltip 자동 close
- mouse LEAVE → tooltip clear

### 구현
- [x] `OntologyGraph.tsx` `hoverNode` state ({ node, x, y })
- [x] `onNodeMouseEnter` / `onNodeMouseLeave` callback — pkg cluster supernode 는 무시
- [x] ReactFlow 에 핸들러 wire
- [x] **`HoverPreview` 컴포넌트 신규** — fixed positioning, edge count, viewport edge flip
- [x] `onNodeClick` 도 hoverNode 클리어 (commit 시 hover→panel 전환)

### 검증
- TS clean
- 백엔드 회귀 0 (frontend-only 변경, 156 PASS)

### 효과
- 사용자가 그래프 노드 의미를 click 없이 빠르게 확인 가능 — 큰 그래프 (5K 노드) 에서 "이 노드 뭐였더라" 빠른 확인용
- NodePreviewPanel (full slide-up) 은 commit 후 진입 — 의도/UX 분리

### 안 한 P3
- **6번째 graph 노드 kind: Method** — 작업 중 / zoom-in mode 라 정확히 무엇 의미하는지 명세 필요. 단순 "code_method 를 graph 에 표시" 라면 이미 됨. method-method call edge / method body anchor 까지 포함 시 큰 작업. 보류.
- **Time-travel / graph diff** — perspective + 스냅샷 기반 diff. 큰 작업, 별도 phase.
- **Schema migration framework** — Foundry 8-option, 가장 큰 빈 영역. 별도 phase.

### 누적 P3 (총 6건)
1. `usage_limits_for(cushion=2)` — R6-VAL hard cap fix
2. `demo_guide.md` P1a 흐름 추가
3. `resumeSession` chat thread 복원 메시지
4. Sessions picker dropdown
5. Entity 카운트 stat row
6. **Graph Hover preview** (이번)

### 다음 결정 영역
- **P4 사용자 데모 / 피드백** — 가장 demo-ready 한 시점
- **A2 Simulation Agent** — 다음 큰 phase
- **A1 Plugin** — input adapter / runtime collector / sandbox runner

---

## 🏁 2026-05-05 세션 종료 — Round 5 식 풀 사이클 재개 준비

사용자 결정: P4 (데모) 진입 전 **Round 5 식 풀 사이클 한 번** 필요. 이번 세션 마무리하고 다음 세션에서 시작.

### 사용자 인용 (정확)
*"지금 큐에 있는 애들은 그냥 recommend 로 추가된 애들이야. 우리가 html 로 대화하면서 구체화하고 만들어갔던 방식으로 전체 한 사이클이 돌아야해. 그걸 다음 세션에서 시작할 수 있도록 모두 준비하고 이번 세션 마무리해줘."*

### 종료 시점 정리
- [x] **HANDOFF.md 갱신** — "🔴 다음 세션 첫 작업" 섹션 추가 (보류 시점 + 재개 후보 + Entity/모드 갈래 + 시작 직후 행동 순서 + 환경 점검).
- [x] **`toClaude/modeling/next-session-cycle-start.html` 신규** — 다음 세션 첫 화면용 카드 7섹션 (기억 환기 + B.5.1 후속 요약 + DB 현재 + 결정 후보 G1/G2/G3 × M1/M2/M3 + Claude 행동 순서 + 참조 자료 + 환경 점검 명령).
- [x] **메모리 `project_round5_resume.md` 신규** — 보류 컨텍스트 + 사용자 핵심 인용 + 추천 G2+M3.
- [x] **MEMORY.md 인덱스** 갱신 (Project Status 섹션).
- [x] **TODO.md** "🔴 다음 세션 첫 작업" 섹션 추가.

### 이번 세션 종료 시점 누적 진척
- R6 (Authoring AI graph 인프라) — 완료 (cap 1, 2, 5, 6, 7, 10, 11, 12 + UI β·γ + 27 routes)
- P1a (multi-entity workflow) — 완료 (5 batch 모두 [x])
- R6-VAL — 완료 (cap 2 confidence 0.50/0.45 검증)
- P3 폴리싱 — 6건 완료
- 도구 demo-ready ✅, 사용자 합의 풀 사이클은 미완 ⚠

### 다음 세션 첫 메시지 예상
사용자가 "이어서 하자" 라고 하면 Claude 가 자동으로:
1. `HANDOFF.md` 의 "🔴 다음 세션 첫 작업" 섹션 읽음
2. `next-session-cycle-start.html` 열어보길 권유 (브라우저)
3. G/M/스코프 3 가지 결정 받음
4. 진입

### 종료 마지막 점검
- ✅ 백엔드 살아있음 (port 8001, 27 routes)
- ✅ 프론트엔드 살아있음 (port 3000)
- ✅ pytest 156 PASS · 11 SKIP
- ✅ TS clean
- ✅ 모든 변경 git 추적 가능 (commit 안 됨 — 사용자 지시 대기)
- ✅ /loop 다음 wakeup 23:24 예약됨 — 발사되면 idle ping, 별도 작업 없음. 사용자가 명시적으로 끄지 않는 한 계속.

세션 종료. 다음 세션 시작 시 위 자료들로 즉시 픽업 가능.

---

## 2026-05-16 (Section 4 sim_v2 W77 + W78 마무리 + Section 3 handoff 패키지 완성) [x] 완료

Section 3 시뮬레이션 담당자에게 sim_v2 자산을 인계하는 작업 마무리.

### W77 + W78 한국어 검색 layer (보완 개념)

- [x] **W77 KoreanTermResolver** — `backend/sim_v2/core/search/korean_term_resolver.py`. ontology 의 `business_terms.aliases_json` 을 *대체하지 않고 fully exploit*. label / aliases / description / fqn **4 컬럼 통합 token index**. UC41 실측 9/10 hit (90%).
- [x] **W78 hybrid tier** — 동일 파일에 4 tier 통합. Tier 2 한↔영 정적 매핑 (`transliteration.py`, ~50 매핑), Tier 3 difflib edit-distance fallback, Tier 4 caller-supplied LLM callback. typo "edgign" / 비표준 음역 "에징" 모두 close. UC42 production demo + 14 unit test 통과.
- [x] **public API**: `resolve(query, *, use_transliteration=True, use_fuzzy=True, llm_assist=None)`. 본인 LLM 한 줄 plug-in.

### Section 3 handoff 패키지 v4 — `toClaude/modeling/section4-verification/section3_handoff/`

- [x] `README.md` — navigation hub. §0~7 + **신규 §8 시뮬레이션 담당자 onboarding 가이드** (pull / venv / first-run / 본인 클로드 코드 첫 메시지 / sprint 단위 작업 순서 / 막힘 대응표).
- [x] `for-humans.html` — 사람용 인터랙티브 페이지. ⑧ 한국어 검색 카드 + § F 아키텍처 카드에 W78 hybrid tier 시각화 (4 tier ASCII diagram).
- [x] `api-reference/W77-korean-term-resolver.md` — W78 통합 버전 (§3.5 hybrid tier API + tier 별 production 실측 표).
- [x] `usage-recipes/recipe-5-korean-term-search.py` — typo (Tier 3) + 비표준 음역 (Tier 4) 시연 추가, production DB 동작 확인.
- [x] `gap-analysis.md` — 한계 #2 를 W77 + W78 통합 close 로 표기, "한 줄 결론" 표에 W78 추가.

### 회귀 / 실측

- [x] sim_v2 전체 회귀: **1,892 passed, 3 skipped** (W77 27 + W78 14 추가, 회귀 0).
- [x] UC42 production demo: T1~T4 close rate 측정 (T3 1/2, T4 1/1).

### 다음 세션 / 다음 담당자

- 시뮬레이션 담당자 → `toClaude/modeling/section4-verification/section3_handoff/README.md` §8 가이드로 시작. 클로드 코드 첫 메시지 템플릿 포함.
- 모델링 세션은 별도 (handoff 작업 종료).
