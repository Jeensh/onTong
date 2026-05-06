# Palantir Foundry UX Catalog — Stage 3

작성일: 2026-05-02
범위: Foundry 의 11 화면 — graph viz 6 + non-graph 5. Stage 4 (adoption decision) 의 입력.
규칙: `[확인]` = 공식 docs 직접, `[추정]` = docs 발췌 + 추론, `[알 수 없음]` = 공개 자료 비어있음.

---

## A. Graph viz 화면 (6 종, 본 보고서의 60% 비중)

### A1. Workshop Object Set Canvas

**진입점**: Workshop dashboard builder → object set widget. 사용자가 dashboard 안에 object set 을 embed.

**주요 primitive** [확인, S23, S24]:
- Object set = filtered subset of one ObjectType
- Widget kind: Object View (full / panel / instance / adaptive / set view)
- Filter widgets (slider, dropdown, search) 가 object set 을 동적으로 좁힘
- **Graph viz 는 1급 widget 이 아님** — table / card / chart 가 default. Quiver embed 또는 별도 plugin 으로 graph 표시 가능 [추정].

**스케일 전략**:
- "Object set" 자체가 결과 집합 → backend 에서 query pruning (S32 의 1000x fewer records).
- Workshop widget 단에서는 visible row count 제한 (paging / virtual scroll) [추정].

**우리에 매핑**:
- 우리는 "object set" 개념이 없음 (시뮬 schema 라 instance data 없음).
- 차용 가능: **filter widget + result widget** 의 조합 패턴. "이 BusinessTerm 의 모든 PARTIAL 매핑 CodeType" 같은 set 을 dashboard widget 으로.
- 차용 불가: instance-level table.

**스크린샷 URL**: https://www.palantir.com/docs/foundry/workshop/widgets-object-view (페이지에 widget 모드 4종 스크린샷)

**신뢰도**: [확인] widget 종류 / [추정] graph viz 의 widget 위치.

**한계**: Workshop docs 에서 graph viz 가 1급으로 다뤄지지 않음. 화면이 table-first 라는 강한 신호.

---

### A2. Quiver Graph Mode (★ 가장 가까운 prior art)

**진입점**: Quiver Analysis → 우상단 mode toggle "Canvas / Graph". 분석 cards (transform / chart / filter 단위) 의 흐름을 노드 그래프로 보여줌.

**주요 primitive** [확인, quiver/analysis-graph]:
- "cards are represented by nodes on the Graph and each card is linked to its inputs and outputs"
- **Layout**: left-to-right (LR), 즉 dataflow 방향
- **Node**: title + identifier + type 의 compact card
- **Preview panel** (하단): pin 가능, split-screen 비교 가능
- **Right-click → "View dependencies"**: 선택 카드의 upstream/downstream 만 보이는 dependency view 로 전환
- **Mode 전환**: Panning mode ↔ Selection mode (별도 toggle)
- **Multi-select drag**: 다수 노드 선택 후 색 group 부여 / hide / 일괄 삭제
- **Color groups**: 사용자가 노드 그룹을 색으로 visually 구분
- **Eligible-input highlight**: input 설정 시 eligible 노드가 graph 상에서 highlight (list 검색 대신 시각 선택)

**인용 보존**:
> "the Graph allows you to see all of the content in your analysis at once, along with the logical paths involved" (quiver/analysis-graph)
> "View dependencies, which will only show the card selected and its upstream and downstream dependencies — useful when trying to understand how a specific card was created in a large analysis"

**스케일 전략**:
- Quiver graph 는 한 분석 내 cards 수 (수백) 가 상한 [추정]. 100K+ ontology 엔터티는 대상 아님.
- 큰 분석에서는 dependency view 로 가지치기 (focus + neighborhood) — 우리 neighborhood mode 와 거의 동일 패턴.
- Color group + drag-multi-select 로 **수동 클러스터링** — 우리는 패키지 자동 cluster 사용 중.

**우리에 매핑**:
- **거의 1:1 매핑 가능**: 우리 OntologyGraph 의 neighborhood mode + dependency view = Quiver graph mode + "View dependencies".
- 차용 후보 (강함):
  - **Bottom preview panel + pin/split**: 노드 클릭 시 metadata 만 띄우는 게 아니라, **fragment / mapping detail 을 하단 panel 에 pin**. 여러 노드 비교 가능. 현재 우리는 graph 만 보여주고 detail 은 별도 페이지.
  - **Selection mode vs Panning mode toggle**: 다중 선택해서 일괄 작업 (PARTIAL 승인 / 색 그룹 / hide).
  - **Eligible highlight**: 사용자가 "이 BusinessTerm 에 매핑할 후보 CodeType 추가" 작업 시, 그래프 상에서 eligible 노드 highlight.
- 차용 불가: cards = transform 이라는 의미적 차이. 우리 노드는 ontology 엔터티지 transform 이 아님.

**스크린샷 URL**: https://www.palantir.com/docs/foundry/quiver/analysis-graph

**신뢰도**: [확인] (docs 직접 fetch, 인용 다수).

**한계**: Quiver graph 는 본질상 dataflow 그래프 (DAG) 라 ontology 의 양방향 / cyclic 관계엔 부분만 적용 가능.

---

### A3. Foundry Data Lineage (★★ 가장 비슷한 large-graph 화면)

**진입점**: 좌상단 메뉴 → Data Lineage. 단일 dataset 또는 ontology entity 에서 시작.

**주요 primitive** [확인, data-lineage/explore-lineage, navigation, learning-data-lineage]:
- **Dataset DAG** node-and-link, **auto-layout default**
- **Manual drag**: 노드 자유 이동, "Layout all nodes" 로 auto 복귀
- **Expand arrows**: 노드 양쪽의 ←→ 화살표 클릭 → direct parents / children 노출 (점진적 expand)
- **Color coding**: "color-coding your data transforms to visually separate distinct groups" (사용자 지정 색)
- **Node coloring**: dataset type/status 별 자동 색 [확인, 별도 페이지 존재]
- **Save/Open graph**: lineage view 자체를 저장 + 공유 링크 + SVG export
- **Build timeline**, staleness, permissions, marking change impact 모두 lineage view 안에서 접근

**인용 보존**:
> "the graph is your workspace for arranging and manipulating nodes as you explore your data pipeline. After adding nodes to the graph, you can add their related resources by clicking on the arrows on either side of the node or by using the Expand option in the graph tools"
> "Lineage allows color-coding your data transforms to visually separate distinct groups"
> "click on the left arrow of the node to expose the direct parents of the resource"

**스케일 전략**:
- **점진적 expand 가 핵심**: 1000+ dataset 환경에서도 사용자가 시작 노드 → ←→ 클릭으로 hop-by-hop. 한 번에 전체 안 보여줌.
- **Search-driven entry**: "search-based exploration to locate datasets within complex dependency networks"
- **Save graph**: 사용자가 자주 쓰는 lineage view 를 저장 → 매번 expand 안 함.

**우리에 매핑**:
- **차용 후보 (가장 강함)**:
  1. **Hop-by-hop expand arrows**: 우리는 `n_max` slider 로 한 번에 N 노드 가져옴. Foundry 처럼 **노드 양쪽 화살표 → 1-hop expand** 패턴이 사용자 인지 부하 ↓.
  2. **Save/share graph**: 사용자가 "Order entity 분석 view" 같은 그래프 view 를 저장하고 다른 팀원과 공유. 데모에서 강력.
  3. **Color coding (사용자 지정)**: 현재 우리는 KIND_COLOR 만 (term/code/action). Foundry 처럼 **사용자가 임의 그룹에 색 부여** → "이 4 노드는 우리 팀 책임" 같은 manual 라벨링.
  4. **SVG export**: 보고서/wiki 에 그래프 박제. 데모 발표 활용도 높음.
- 차용 불가: dataset build/schedule 같은 runtime 기능 (우리는 schema only).

**스크린샷 URL**: https://www.palantir.com/docs/foundry/data-lineage/explore-lineage

**신뢰도**: [확인] (docs + Medium 글 + Unit8 Foundry 101 글 cross-ref).

**한계**: Foundry lineage 가 정확히 몇 노드까지 부드럽게 처리하는지 [알 수 없음] — 일반적 docs 는 "thousands of datasets" 만 언급.

---

### A4. Pipeline Builder Canvas

**진입점**: Pipeline Builder app → 새 pipeline 또는 기존 dataset 의 transform 편집.

**주요 primitive** [확인, pipeline-builder/overview]:
- **DAG canvas**: input → transform → output 의 흐름 (LR layout 추정)
- **Node = transform step / dataset**
- **Folder, color group, text node**: pipeline 조직화 (노드 자체가 아닌 메타 organize 도구)
- **Checkpoint node**: pipeline 의 중간 stable 지점 표시
- **Job group**: 여러 transform 을 논리적으로 묶음
- **Find and replace**: bulk edit (예: column rename 시 모든 transform 에서)

**스케일 전략**:
- Folder / color group / job group 으로 **수동 grouping** (Quiver 와 동일 패턴).
- Sidebar nav 로 transforms / outputs 별 점프 (canvas 안 클러터 회피).
- Find-and-replace 로 대규모 refactoring.

**우리에 매핑**:
- **차용 가능**: **Folder + text node + color group**. 우리 그래프 위에 사용자가 자유롭게 색 박스를 그려 grouping. 패키지 cluster 외에 manual 그룹.
- **Checkpoint**: 우리에 적용하면 "이 BusinessTerm 부분은 confirmed 상태로 lock" 같은 의미.
- **Find-and-replace**: ontology refactoring 도구 (ex: term FQN rename 시 모든 reference 자동 변경).

**스크린샷 URL**: https://www.palantir.com/docs/foundry/pipeline-builder/overview

**신뢰도**: [확인] facet 자체 / [추정] 정확한 layout.

**한계**: Pipeline canvas 의 정확한 시각 패턴은 docs 가 텍스트 위주라 직접 보지 못함.

---

### A5. AIP Logic Block-and-Wire Canvas

**진입점**: AIP Logic editor. 좌측 input / 중앙 blocks / 우측 outputs 3-pane [확인, S18].

**주요 primitive** [확인, S17, S18, logic/blocks]:
- **Blocks (6 종)**: Use LLM / Apply Action / Execute Function / Conditional / Loop / Create Variable
- **Sequential chain**: block 출력 = 다음 block 입력
- **Branching**: Conditional block → multiple branches (if-then-else), 각 branch return type 일치 강제
- **Loop block**: collection 반복, `element` + `index` 변수 노출, action 없으면 parallel 실행
- **Debugger**: 실행 후 LLM CoT 표시, block card expand/collapse
- **Versioning**: 입력 version 저장 → unit test 가능

**인용 보존**:
> "Operations execute in parallel when containing no actions" (logic/blocks)
> "if-then-else logic with consistent return types across all branches" (logic/blocks)

**스케일 전략**:
- 한 logic function 의 block 수 자체는 작음 (수십). Logic chain 의 깊이/넓이 자체가 시각적 한계.
- Block 별 expand/collapse 로 detail level 조절.

**우리에 매핑**:
- 우리 ontology graph 와 영역이 다름 (workflow vs ontology). 그러나:
- **차용 가능**: **block expand/collapse pattern** — 우리 노드를 클릭하면 inline 으로 expand 해서 properties / realizations / fragments 표시 (현재 별도 panel).
- **Conditional / Loop visualization**: 우리 Action.kind=workflow + sub_actions 시각화 시 차용. 현재 workflow 노드가 sub_action 을 단순 edge 로만 표시 — Logic 처럼 sequential block + branching 시각.
- 차용 불가: LLM CoT debugger (우리 그래프 화면은 ontology 탐색이지 execution 디버그 아님).

**스크린샷 URL**: https://www.palantir.com/docs/foundry/logic/getting-started

**신뢰도**: [확인] block 종류 / [추정] 정확한 시각 layout.

**한계**: Logic canvas 의 정확한 wiring 시각 패턴은 docs 텍스트만 — 실제 화면 영상 검증 필요.

---

### A6. Object Explorer Group-Graph (★★★ 우리 ontology 와 직접 비교)

**진입점**: 좌상단 Object Explorer → 사이드바에서 그룹 클릭 → 메인 영역에 그 그룹 안 ObjectType 들의 graph 표시.

**주요 primitive** [확인, S21, object-explorer/getting-started]:
- **Group sidebar**: 좌측에 ObjectType group + Favorites
- **Group graph**: 그룹 안 ObjectType 들이 노드, link type 이 엣지
- **Link symbol (<->)**: 클릭 → 그 두 ObjectType 사이 link type 종류 노출
- **Node click → menu**: "object type preview" 또는 "Start Exploration"
- **Layout 변경 가능** [확인 — "you can change the layout"]
- **Inter-group link 도 표시** (group 경계 넘는 link)

**인용 보존**:
> "Click on a link symbol (<->) to show the type of links between the object types"
> "Select a single object to view a menu that allows you to explore the object type preview or start an exploration"
> "When more than 250 object types exist... To search a specific object type or a group of object types you must leverage the functionality described below" (Object Explorer docs)

**스케일 전략 (★ 핵심 발견)**:
- **250 ObjectType 임계** 가 Foundry 가 명시적으로 인정한 cliff. 그 이상은 group 기반 검색으로 분할 권장.
- Group = 사용자/관리자 정의 카테고리. 즉 **graph viz 는 250 노드 미만 group 단위로 fragmenting**.
- Inter-group link 는 보이지만 group 자체가 supernode 처럼 작동 — 우리 cluster mode 와 동일 패턴.

**우리에 매핑**:
- **거의 1:1 매핑**: 우리 5K class / 117 노드 데모와 같은 영역.
- **차용 후보 (강함)**:
  1. **Domain-grouped graph view**: 우리는 현재 "전체 ontology 그래프" 또는 "focus 주변" 둘 뿐. Foundry 처럼 **Domain 별로 분할 view** (예: "scm domain", "process domain") + inter-domain link 가 보이는 패턴. Top-down 도메인 진입 (memory: feedback_topdown_domain_view) 과 정합.
  2. **250 임계 강제**: 우리도 "한 view 에 노드 N 개 이상 시 자동 group/cluster" rule 명시.
  3. **Link symbol (<->) 클릭으로 link type 표시**: 우리 엣지에 항상 label 그려넣음 (혼잡). Foundry 식 **lazy reveal** (hover/click 시만 label) 검토.
  4. **Sidebar group + graph 의 통합 navigation**: 우리는 검색 only. 좌측 도메인 트리 + 메인 graph 의 master-detail.

**스크린샷 URL**: https://www.palantir.com/docs/foundry/object-explorer/getting-started

**신뢰도**: [확인] (docs + 250 ObjectType 발췌).

**한계**: 1000+ object type 의 실제 graph viz 는 docs 가 명시 안 함 (group 기반 분할만 권장).

---

## B. Non-graph 화면 5 종 (40% 비중, 짧게)

### B1. Object Explorer (Type 목록 + 검색) [확인, S21, S22]

- **Layout**: 상단 global search + 좌측 group sidebar + 중앙 그래프/카드.
- **Search syntax**: AND/OR/NOT, exact phrase ("..."), wildcard `?`/`*`, fuzzy `~`. Field-scoped (`property:value`) 는 명시 없음.
- **Type-ahead**: 검색하면 매칭 ObjectType 드롭다운.
- **Preview panel**: description / properties / linked types / "Start Exploration" 버튼.
- **우리에 매핑**: 우리 OntologySearchPanel 과 거의 동일 패턴. 차용: **Field-scoped 안 되는 점이 흥미롭다 — 우리는 `kind:term role:workflow` 같은 facet 검색 추가하면 우위**.

### B2. Object Type Detail (한 Type 의 properties / links / actions / usage) [확인, S21]

- **Layout**: header (name + icon + group) + tabs (Properties / Links / Actions / Usage / Docs).
- **Inline preview**: 각 property 의 type / required / description.
- **Linked types**: 다른 ObjectType 으로의 link cardinality + 양방향 명명.
- **"Start Exploration" CTA**: detail → graph 진입.
- **우리에 매핑**: 우리는 BusinessTerm Detail panel 이 있으나 actions / realizations 가 분리. 차용: **단일 detail page + tab 4종** 통합. "Usage" tab 에 어떤 Action/Workflow 가 이 term 을 declare_on 하는지 reverse-lookup.

### B3. Object Set 빌더 [확인, S21]

- **Compare object sets** + **Save lists**.
- 정확한 빌더 화면은 docs 가 짧음 — Search → set, Search Around (link traversal), Filter add 가 핵심 verbs.
- **우리에 매핑**: 우리는 schema only 라 instance set 없음. 차용 비중 낮음. 단, **"BusinessTerm 의 모든 PARTIAL realization 집합"** 같은 schema-set 빌더는 가치 있음 (예: "VerificationLevel ≤ DRAFT 인 모든 Action" set).

### B4. Action Editor / Workshop Action Button [확인, S09, S10, S11]

- **Editor 5 facet**: Parameters / Rules / Submission Criteria / Side Effects / Security.
- **Rule 정의 → Parameter 자동 생성** [확인, S10] — declarative 강력.
- **Workshop action button widget**: 사용자에게 form-with-validation 자동 노출.
- **우리에 매핑**: 우리 Action 1급 노드 + Pydantic params 로 동일한 form-자동생성 가능 (Pydantic → JSON Schema → form). 차용: **Submission Criteria 와 Rules 의 facet 분리** (현재 우리는 preconditions + effects 단일).

### B5. Branching / Proposal 흐름 [확인, S25, S26]

- **5-stage**: Create / Edit / Propose / Review / Merge.
- **Proposal = PR** for ontology resources, reviewer 한 명에 모든 resource 일괄 적용.
- **Branch ↔ single Ontology** 강제.
- **우리에 매핑**: 우리는 외부 git PR 사용. 차용 보류 (v3 결정 충돌). 단, **"한 proposal 에 여러 ontology resource 묶음"** + **"reviewer 한 명에 일괄 적용"** 패턴은 모델링 워크플로 (term 추가 + Action 추가 + realization 추가 동시) 에 적용 가치 있음.

---

## C. 신뢰도 + 한계

### C1. 화면별 신뢰도

| 화면 | 신뢰도 | 비고 |
|---|---|---|
| A1 Workshop canvas | [추정] 60% | docs 가 widget 카탈로그 위주, graph viz 위치 명확치 않음 |
| A2 Quiver graph | [확인] 90% | quiver/analysis-graph 직접 fetch 성공 |
| A3 Data Lineage | [확인] 85% | docs + Medium + Unit8 cross-ref |
| A4 Pipeline canvas | [확인] 70% | overview docs 만 — 정확한 시각 patterns [추정] |
| A5 AIP Logic canvas | [확인] 75% | block 종류 [확인], 정확한 wiring 시각 [추정] |
| A6 Object Explorer group-graph | [확인] 85% | 250 ObjectType 임계 명시 발견 |
| B1 Object Explorer | [확인] 85% | docs + search syntax 직접 |
| B2 Type detail | [확인] 75% | preview 만 docs, full detail page 추정 |
| B3 Object Set | [확인] 60% | docs 가 짧음 |
| B4 Action editor | [확인] 90% | 5 facet 명시 |
| B5 Branching | [확인] 90% | docs + S26 인용 |

### C2. 본 catalog 의 한계

1. **스크린샷 직접 캡처 안 함** — docs 페이지 URL 만 제공. Stage 4 결정 시 실제 스크린샷 보고 검증 필요.
2. **404 페이지 다수** — Foundry docs URL 일부가 변경됨. 검색 결과 발췌로 보강한 부분은 [추정] 표기.
3. **Foundry 의 internal admin UI 는 black box** — public docs 가 user-facing 만 노출.
4. **실제 사용 영상 미확인** — YouTube `Quiver | How to Build an Analysis in Palantir Foundry` 등 영상 자료는 시간상 미확인. Stage 4 에서 옵션.

---

## Sources

- [Palantir Quiver Analysis Graph](https://www.palantir.com/docs/foundry/quiver/analysis-graph)
- [Palantir Quiver Overview](https://www.palantir.com/docs/foundry/quiver/overview)
- [Palantir Data Lineage Explore](https://www.palantir.com/docs/foundry/data-lineage/explore-lineage)
- [Palantir Data Lineage Navigation](https://www.palantir.com/docs/foundry/data-lineage/navigation)
- [Palantir Object Explorer Getting Started](https://www.palantir.com/docs/foundry/object-explorer/getting-started)
- [Palantir AIP Logic Blocks](https://www.palantir.com/docs/foundry/logic/blocks)
- [Palantir Pipeline Builder](https://www.palantir.com/docs/foundry/pipeline-builder/overview)
- [Palantir Workshop Object View Widget](https://www.palantir.com/docs/foundry/workshop/widgets-object-view)
- [Palantir Action Types Overview](https://www.palantir.com/docs/foundry/action-types/overview)
- [Palantir Foundry Branching Lifecycle](https://www.palantir.com/docs/foundry/foundry-branching/branching-lifecycle-usage)
- [Medium - Workflow Lineage in Palantir Foundry](https://medium.com/@aish17/understanding-workflow-lineage-in-palantir-foundry-how-dependency-graphs-reveal-the-architecture-fd60b1982943)
- [Unit8 - Palantir Foundry 101](https://unit8.com/resources/palantir-foundry-101-2/)

끝.
