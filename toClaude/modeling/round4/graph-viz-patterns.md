# Graph Viz Patterns — Stage 3 deep-dive

작성일: 2026-05-02
배경: 사용자가 명시 — "ontology graph viz 가 onTong 약점". xyflow + dagre + 3 mode (이웃/경로/클러스터) + n_max 의 현재 구현을 한 단계 끌어올리기.
범위: Palantir 6 화면 + 외부 5 도구 + code-aware 영역 + 기술 패턴 + onTong adoption matrix + 청사진.
규칙: `[확인]` = 1차 source 직접 / `[추정]` = 검색 발췌 + 추론 / `[알 수 없음]` = 공개 자료 비어있음.

---

## Section A — Palantir Graph 6 화면 요약

(상세는 `palantir-ux-catalog.md` A1~A6. 여기는 패턴 추출.)

### A.1 공통 패턴 (Foundry 6 화면 모두에서)

1. **Auto-layout default + manual drag override** [확인, 모든 화면]
   - dagre 와 같은 알고리즘이 초기 layout, 사용자 drag 자유, "Layout all nodes" 로 reset.
   - **우리 현재 상태**: ✅ dagre LR + draggable. 동일.
2. **Color group (사용자 지정)** [확인, A2/A3/A4]
   - 노드 자체 색은 type-기반 (auto), 추가로 사용자가 group 별 색 부여 가능.
   - **우리 현재 상태**: ❌ KIND_COLOR auto 만. 사용자 그룹 X.
3. **Multi-select + bulk operation** [확인, A2/A4]
   - drag-rectangle 로 다수 선택 → 색/hide/일괄 수정.
   - **우리 현재 상태**: ❌ 단일 선택만.
4. **Save/share view + SVG export** [확인, A3]
   - 자주 쓰는 view 를 명명/저장, link 공유, SVG 다운로드.
   - **우리 현재 상태**: ❌ 매번 stateless rebuild.
5. **Right-click context menu** [확인, A2/A3]
   - "View dependencies" / "Expand here" / "Hide" / "Pin preview".
   - **우리 현재 상태**: ❌ 클릭 = focus 변경만.
6. **Bottom preview panel + pin/split** [확인, A2]
   - 노드 클릭 시 graph 위에 pop-up 안 띄우고 별도 영역에 detail. 여러 pin 가능.
   - **우리 현재 상태**: ❌ detail 은 별도 routing.
7. **Hop-by-hop expand arrows** [확인, A3]
   - 노드 양쪽 ←→ 화살표 → 1-hop 단위 점진 expand.
   - **우리 현재 상태**: ❌ n_max slider 로 일괄.
8. **Search-driven entry + group sidebar** [확인, A6]
   - 좌측 group tree + 메인 graph + 상단 global search.
   - **우리 현재 상태**: 부분. 검색만 있고 group sidebar 없음.

### A.2 Palantir 의 "약한" 영역

- **edge label 처리**: Foundry 도 dense label 문제는 명확한 해법 없음 (S6 의 "click on link symbol" lazy reveal 정도).
- **graph diff / time travel**: Foundry docs 에서 graph viz 의 version diff UX 는 [알 수 없음].
- **edge bundling**: docs 미언급. 추정컨대 적용 안 함.
- **mini-graph hover preview**: docs 미언급.
- **importance-based pruning (자동)**: Foundry 는 group 으로 분할만 권장 (수동). 우리는 importance score 기반 자동 — **이 영역에선 우리가 우위**.

---

## Section B — 외부 reference 5 종

### B.1 Neo4j Bloom — Perspective + Search-driven

**핵심 아이디어** [확인, neo4j docs]:
- **Perspective**: 한 graph DB 위에 **여러 business view** 생성 가능. category 분류 / property visibility / relationship visibility / 색-아이콘 / 검색 prefab 모두를 perspective 가 정의.
- **자동 생성**: DB 스캔 → label 분석 → perspective auto-fill. 10M+ node 면 sampling 으로 우회.
- **Search-driven**: 모든 exploration 이 search bar 에서 시작. "describe what you are looking for" → scene 에 시각화.
- **Slicer**: timestamp property 가 있으면 timeline slider 로 graph time travel. 2026-02 강조 feature.
- **Perspective sharing**: 정적 chart 가 아니라 perspective 자체를 공유 → 받는 쪽이 그 lens 로 본다.

**우리에 차용 가능**:
- ⭐⭐⭐⭐ **Perspective 개념 도입**: 우리 OntologyGraph 에 "Perspective" = (도메인 필터 + edge kind 필터 + node kind 필터 + color rule + 저장된 focus) 의 named bundle. 사용자가 "Order workflow lens" "VerificationLevel < SIM_VERIFIED lens" 만들어 공유.
- ⭐⭐⭐ **Search-driven entry**: 우리 OntologyGraph 가 빈 화면 시작 X — perspective 또는 search 결과로 자동 채움.
- ⭐⭐ **Slicer (time travel)**: term confirmed_at / created_at 으로 ontology 진화 view. 데모용.
- ⭐⭐ **Perspective sharing URL**: Foundry data lineage 의 share URL + Bloom 의 perspective 공유 = 우리 PM/도메인 전문가에 그래프 공유.

### B.2 Cambridge Intelligence (KeyLines / ReGraph) — Large-scale 전략

**핵심 아이디어** [확인, cambridge-intelligence docs]:
- **5-step funnel** (1M → 100 노드):
  1. Backend filter (1M+) — search and expand interaction
  2. Aggregation (100K) — merge duplicates + collapse links
  3. Visual modeling (10K-1K) — 분석 목적별 alternative schema
  4. Interactive declutter (1K) — combo (group), prune leaf
  5. Layout (100) — force-directed
- **GPU rendering**: pan/zoom 부드러움. 큰 그래프 처리 핵심.
- **Adaptive styling (LOD)**: zoom level 에 따라 노드 detail 변화 (label 표시/숨김 등).
- **Combo (확장/축소 그룹)**: cytoscape 의 compound nodes 와 같은 패턴.
- **kCore 등 SNA 알고리즘**: 클러스터 자동 식별.
- **timeline + heatmap**: 시간별 aggregated view.

**인용 보존**:
> "visualizing so much data in one screen is rarely useful or successful, as many huge graphs are too densely connected to be usefully visualized all at once" — 한 화면 다 보여주려는 욕심 자체가 잘못.

**우리에 차용 가능**:
- ⭐⭐⭐⭐⭐ **5-step funnel 사고**: 우리 100K class 시나리오에 직접 적용. 현재 우리 backend graph_api 는 step 1 (importance pruning) + step 5 (layout) 만. 2/3/4 가 비어 있음.
- ⭐⭐⭐⭐ **Adaptive styling (LOD)**: zoom out 하면 label 숨기고 node 작아지고, zoom in 하면 fragment / mapping 정보까지. 현재 우리는 fixed.
- ⭐⭐⭐⭐ **Combo (compound nodes)**: 우리 cluster mode 가 패키지 단위 supernode 인데, **expand/collapse in-place** 가 안 됨 (mode 전환 필요). 한 화면에서 cluster 일부만 expand.
- ⭐⭐ **GPU rendering**: xyflow 가 SVG 기반이라 1K+ 노드 시 버벅. WebGL renderer (sigma.js / cosmos / G6) 검토.
- ⭐⭐ **Time-based filter / slicer**: Bloom 과 동일.

### B.3 Sourcegraph — Code Intelligence (★ code-aware)

**핵심 아이디어** [확인, sourcegraph docs]:
- **SCIP (Source Code Intelligence Protocol)**: language-agnostic indexing format. semantic info (definition, reference, hover) 를 정형화.
- **Cross-repo navigation**: definition / reference 가 repo 경계 넘음.
- **Code Graph**: Cody (AI assistant) 의 context 소스. semantic 인덱스.
- **검색 우선 (graph viz X)**: Sourcegraph 의 1급은 텍스트 검색 + go-to-def. **graph viz 는 1급이 아님**.

**우리에 차용 가능**:
- ⭐⭐⭐ **검색 우선 + graph viz 는 보조**: 사용자 인용 "검색 우선 + 부분 뷰". Sourcegraph 패턴과 정합. 우리 그래프가 first screen 이 되면 안 될 수도.
- ⭐⭐⭐ **definition / reference 의 hover preview**: 노드 hover 시 mini-graph + code snippet 미리보기. 그래프 위에서 "이 CodeType 의 method 6 개" 같은 inline preview.
- ⭐ **SCIP 같은 정형 indexing 포맷**: 우리는 이미 Pydantic schema 로 정형. 차용 가치 낮음.

**한계**: Sourcegraph 자체가 graph viz 도구가 아님. 우리 영역과 부분 겹침만.

### B.4 Backstage (Spotify) — Software Catalog Graph

**핵심 아이디어** [확인, backstage docs + Spotify Engineering blog]:
- **Software graph**: component / system / domain / API / resource 노드 + dependsOn / partOf / providesApi / consumesApi 엣지.
- **Catalog 처음 의도**: "human mental model" 위주. 모든 인스턴스 lister 가 아니라 사용자 멘탈 모델 매칭.
- **System diagram**: System page 의 Architecture tab 에서 component diagram 자동 렌더 (Mermaid / IcePanel).
- **Plugin 확장**: workflows plugin 에 data lineage graph + log inspector + alerts.
- **YAML metadata**: code 와 함께 catalog-info.yaml. **즉 ontology 가 코드 옆에 있음** ← 우리와 매우 유사.

**우리에 차용 가능**:
- ⭐⭐⭐⭐ **System / Component / Domain 3-level navigation**: Backstage 가 domain → system → component → API hierarchy. 우리 ontology 는 domain → BusinessTerm composite → atomic → CodeType realization. 4-level top-down navigation 화면 (memory: feedback_topdown_domain_view 와 정합).
- ⭐⭐⭐ **YAML co-located + graph 자동 generation**: 우리는 wiki 에 mapping 정보. Backstage 처럼 **코드 옆 yaml** + 그래프는 그것에서 자동 derive.
- ⭐⭐⭐ **Architecture tab**: 우리 BusinessTerm Detail page 에 "Architecture" tab — 그 term 을 중심으로 한 mini-graph 자동 렌더.
- ⭐⭐ **dependsOn 같은 정형 edge kind**: 우리 6 종 edge 도 동일 정형성.

### B.5 Apache Atlas / DataHub — Column-level Lineage

**핵심 아이디어** [확인, datahub docs]:
- **Toggle table-level vs column-level**: 한 클릭으로 lineage granularity 변경. 처음엔 table-level (덜 dense), 필요 시 column-level expand.
- **Column 의 expand-in-place**: table 노드 안에서 column 펼침. 노드 안에서 부분 노출.
- **Right-click → "lineage in Lineage Explorer"**: 특정 column 만 새 view 로.
- **Impact analysis 별도 도구**: 변경 영향 어디까지 미치는지 정량 표시.

**우리에 차용 가능**:
- ⭐⭐⭐⭐⭐ **2-level toggle (CodeType-level vs method/property-level)**: 우리 그래프는 CodeType + Term + Action 노드. 하나 더 추가: **method 레벨**. 평소엔 CodeType 노드 = supernode, expand 시 그 안 method (Realization 의 endpoint) 노출. **PARTIAL realization 의 fragment-level 도 동일** — Term 노드 = supernode, expand 시 sub-term composition.
- ⭐⭐⭐⭐ **Impact analysis as separate view**: 우리 path mode 외에 "이 BusinessTerm 의 영향 범위" 별도 view (모든 reachable node + 거리 표시).
- ⭐⭐⭐ **Right-click "view in lineage explorer"**: 노드에서 새 view spawn.

---

## Section C — Code-Aware Graph Viz (★ 우리만의 영역)

### C.1 영역 정의

우리 OntologyGraph 의 고유 특성:
1. **노드 3종 mixed** — Term (도메인) + CodeType (Java) + Action (verb)
2. **Code ↔ Domain mapping (PARTIAL)** — 한 클래스가 여러 sub-term 에 부분 매핑
3. **패키지 hierarchy + relational graph 동시** — package containment + extends/implements/composition relational
4. **Method-level dispatch (9-enum)** — 다형성을 1급 시각화 가능

이 4 가지 동시 보유한 도구 — 외부 prior art 가 매우 빈약. 사용자 가정 ("우리만의 영역") 검증.

### C.2 가능한 prior art 분포

| 도구 | code 분석 | domain mapping | 패키지+relational 동시 | method-level | viz 강도 |
|---|---|---|---|---|---|
| **IntelliJ UML Diagram** [확인] | ✅ | ❌ | ✅ (package containment + class) | ✅ method 표시 | 중 (정적, IDE 내) |
| **AppMap** [확인] | ✅ runtime trace | ❌ | 부분 | ✅ runtime call | 중 |
| **CAST Imaging** [확인] | ✅ deep | ⚠️ "blockers/boosters" 정도 | ✅ | ✅ transaction path | 매우 강 (commercial) |
| **Structurizr (C4 model)** [확인] | ⚠️ DSL 수동 | ✅ Container/Component | ❌ (4-level abstract) | ❌ | 강 (diagrams as code) |
| **Sourcegraph** [확인] | ✅ semantic | ❌ | ❌ | ✅ def/ref | 약 (graph 아닌 검색) |
| **Backstage** [확인] | ⚠️ catalog yaml | ✅ domain/system | ❌ (component만) | ❌ | 중 (component diagram) |
| **OntoWeR / CODT** [확인] | ✅ | ✅ ontology gen | ❌ | ❌ | 약 (research, UI 미성숙) |
| **onTong (현재)** | ✅ AST | ✅ PARTIAL | ✅ pkg+relational | ✅ realization 9-enum | 중 (xyflow + dagre) |

**발견**:
- **CAST Imaging** 가 우리와 가장 가까운 영역 (code-aware + 시각화). 그러나 mapping 은 ISO 5055 / cloud-readiness 같은 고정 카테고리. **자유로운 "이 domain 에 매핑" 이 아님**.
- **Structurizr** 의 C4 모델 (System / Container / Component / Code) 4-level + diagrams-as-code 패턴은 우리 **다중 추상화 level 시각화** 에 차용 가능. 단 우리는 자동 추출 (Structurizr 는 수동 DSL).
- **IntelliJ UML Diagram** 의 "Analyze Graph | Focus On Paths Between Two Nodes" 는 우리 path mode 와 동일 — 즉, **우리 path mode 는 prior art 와 동등**.
- **Backstage 의 catalog-info.yaml 옆에 코드** 패턴이 우리 ontology + Java 코드 패턴과 가장 비슷. UX 는 component-only 라 우리보다 얕음.

**결론**: 우리 가설 검증됨 — **code + domain + 패키지 + method 4 차원 동시 graph viz 의 일관된 prior art 는 사실상 부재**. 가장 가까운 건 CAST (그러나 자유로운 domain mapping 부재) + Backstage (그러나 단일 layer).

### C.3 차용 후보 (code-aware 영역)

- ⭐⭐⭐⭐ **IntelliJ Diagram의 inheritance/composition/dependency 토글**: 우리 6 종 edge kind 를 사용자가 toggle 로 켜고 끔 (현재는 다 보여줌).
- ⭐⭐⭐⭐ **Structurizr의 4-level abstract 시점**: 우리 ontology 도 Domain / Composite Term / Atomic Term + CodeType / Method 4-level. View 를 그 level 별로.
- ⭐⭐⭐ **CAST Imaging의 "transaction path"**: 우리 Action 의 sub_actions 호출 chain 시각화 (workflow 트레이스).
- ⭐⭐⭐ **AppMap의 runtime 시각화**: 우리는 정적 분석만. 시뮬 실행 trace 시각화 차용 (Step 8 시뮬 결과 viz).

---

## Section D — 기술 패턴 (라이브러리 X, 패턴 O)

### D.1 Cluster collapse / Compound nodes

**원리** [확인, cytoscape docs]:
- 노드 안에 노드 포함 = compound node (parent + child).
- expand-collapse extension: 사용자가 parent 클릭 시 child 토글.
- **dagre는 compound 미지원**. ELK Layered 또는 cytoscape 자체 layout 필요.

**우리 현재**: cluster mode 가 패키지 단위 supernode (별도 mode 로 전환). compound expand-in-place 안 됨.
**차용 우선순위**: ⭐⭐⭐⭐ — Adoption matrix 1순위.

### D.2 Importance pruning

**알고리즘**:
- Degree centrality (가장 단순)
- PageRank (전역 중요도)
- Betweenness centrality (bridge 노드)
- HITS (hub vs authority)

**우리 현재** [확인, graph_api.py `_importance_score`]:
- degree + role-weighted (term root +5, action workflow +4, confirmed +2). **사실상 우리식 weighted-degree centrality**.
**차용 우선순위**: ⭐⭐ — 이미 잘 구현. PageRank 추가 검토.

### D.3 Faceted filter + lens (multi-dimension)

**원리** [확인, multi-faceted graph viz survey]:
- 4 facet: partitions / attributes / time / space.
- Filter facet 마다 select-all/deselect-all/sort/remove.
- AND 연결 (모든 facet 충족).

**우리 현재**: include_kinds (1차원만). domain / role / verification 은 fixed.
**차용 우선순위**: ⭐⭐⭐⭐⭐ — Bloom Perspective + 이 패턴이 합쳐지면 우리 약점 핵심.

### D.4 Search-driven exploration

**원리** [확인, Bloom + Linkurious]:
- Empty graph → search → result populate scene.
- "Find shortest path" / "Find indirect connections" 같은 query primitive.
- 검색 결과를 graph 에 add (replace 가 아니라).

**우리 현재**: 검색 결과를 focus 변경에만 사용. add 안 됨.
**차용 우선순위**: ⭐⭐⭐⭐ — "검색 결과를 graph 에 누적 추가" 패턴.

### D.5 Path discovery (다중 경로)

**원리** [확인, Linkurious]:
- A→B 최단 경로뿐 아니라 K-shortest paths (다양한 경로 비교).
- "Find indirect connections" — A 의 모든 indirect neighbor.

**우리 현재**: 단일 BFS shortest path.
**차용 우선순위**: ⭐⭐⭐ — K-shortest paths 추가 가치 있음 (PARTIAL realization 시 여러 경로 발견 의미 큼).

### D.6 Lineage 모드 (DAG upstream/downstream 색 분리)

**원리** [확인, Foundry Data Lineage + DataHub]:
- 한 노드 기준으로 ←upstream 빨강 / →downstream 파랑.
- Distance 별 fade.
- Direct vs transitive 구분.

**우리 현재**: 색 분리 없음.
**차용 우선순위**: ⭐⭐⭐⭐ — Action workflow 시각화에 필수. "이 Action 이 영향주는 Term + 의존 Term 색 분리".

### D.7 Mini-graph in tooltip / Hover preview

**원리** [확인, DataHub + 일반 viz 패턴]:
- 노드 hover → 작은 ego-network preview tooltip.
- 미리보기 후 클릭 시 main graph focus 변경.

**우리 현재**: 노드 hover 효과 없음 (CSS 만).
**차용 우선순위**: ⭐⭐⭐ — 사용자 탐색 cost 감소.

### D.8 Time travel (graph diff)

**원리** [확인, Bloom Slicer + History flow]:
- Timestamp slider → 그 시점의 graph state.
- 두 시점 비교 시 added (녹색) / removed (빨강) / changed (노랑) overlay.

**우리 현재**: 없음.
**차용 우선순위**: ⭐⭐ — 데모용 가치 (ontology 진화 시각화). 운영용 우선순위 낮음.

### D.9 Annotated edges / Edge density

**원리** [확인, edge bundling 논문]:
- Hierarchical Edge Bundling: 같은 hierarchy 클러스터로 가는 엣지 묶음 → 빨대처럼 합쳐 그림.
- Lazy reveal: edge label 평소 hide, hover/select 시만 표시 (Foundry 패턴).
- Adaptive bundling: dense 영역만 묶음.

**우리 현재**: edge label 항상 표시. 100+ edge 시 클러터.
**차용 우선순위**: ⭐⭐⭐ — Lazy reveal 부터 (bundling 은 cost 큼).

### D.10 Adaptive styling (Level-of-Detail)

**원리** [확인, KeyLines]:
- Zoom level 에 따라 node detail 변화.
- Far: dot only. Mid: label. Near: full card with subtitle.
- Edge label, marker 등도 동일.

**우리 현재**: fixed style.
**차용 우선순위**: ⭐⭐⭐⭐ — xyflow 의 zoom event 활용 가능.

### D.11 GPU rendering

**원리**:
- SVG (xyflow default) → 1K+ 노드 시 버벅.
- Canvas 또는 WebGL → 10K+ 노드 가능.
- 대안 라이브러리: sigma.js / cosmos / G6.

**우리 현재**: xyflow SVG.
**차용 우선순위**: ⭐⭐ — 5K class 데모는 SVG 로 가능. 100K 가면 필수.

### D.12 Manual color group + hide

**원리** [확인, Quiver + Pipeline Builder]:
- 사용자가 노드 다중 선택 → 색 group 부여 / hide / 폴더로 묶기.
- 그래프 위에 사용자 자신의 의미 layer overlay.

**우리 현재**: 없음.
**차용 우선순위**: ⭐⭐⭐ — 모델링 협업 시 가치.

### D.13 Save / Share / Export

**원리** [확인, Foundry Data Lineage + Bloom]:
- 현재 view (filter + focus + layout) 를 named bundle 로 저장.
- 공유 URL 생성 (read-only).
- SVG / PNG export.

**우리 현재**: 없음.
**차용 우선순위**: ⭐⭐⭐⭐ — 데모/협업 가치 큼. 구현 비용 낮음.

### D.14 Right-click context menu

**원리** [확인, Quiver + Lineage]:
- 우클릭 → "View dependencies" / "Expand here" / "Hide" / "Pin" / "Set as focus".

**우리 현재**: 없음. 클릭 = focus 변경.
**차용 우선순위**: ⭐⭐⭐⭐ — Universally expected pattern.

### D.15 Bottom preview panel (pin/split)

**원리** [확인, Quiver]:
- 그래프 아래 dedicated preview area. 노드 클릭 = preview 채움. pin = 다른 클릭에도 유지. split = 둘 비교.

**우리 현재**: 별도 routing.
**차용 우선순위**: ⭐⭐⭐⭐ — Detail 보면서 graph 컨텍스트 유지.

### D.16 Selection mode vs Panning mode

**원리** [확인, Quiver]:
- Toggle 로 마우스 동작 모드 변경. Selection: drag = 사각형 다중 선택. Panning: drag = view pan.

**우리 현재**: pan only.
**차용 우선순위**: ⭐⭐⭐ — multi-select 의 prereq.

### D.17 Hop-by-hop expand arrows

**원리** [확인, Foundry Data Lineage]:
- 노드 양쪽 ←→ 화살표 → 1-hop 단위 점진 expand.

**우리 현재**: n_max 일괄.
**차용 우선순위**: ⭐⭐⭐⭐ — 사용자 인지부하 ↓.

### D.18 Perspective (named lens)

**원리** [확인, Bloom]:
- (filter + style + search prefab + focus) 를 named bundle 로 저장 + 공유.

**우리 현재**: 없음.
**차용 우선순위**: ⭐⭐⭐⭐⭐ — D.3 facet + D.13 save 의 통합. 가장 임팩트 큰 차용.

### D.19 Compound expand-in-place

**원리** [확인, cytoscape compound]:
- cluster supernode 클릭 → 그 자리에서 expand. 다른 cluster 는 그대로.
- Re-layout 은 partial (전체 재계산 X).

**우리 현재**: cluster mode 통째 전환.
**차용 우선순위**: ⭐⭐⭐⭐⭐ — 가장 뚜렷한 UX 개선.

### D.20 Eligible-node highlight

**원리** [확인, Quiver]:
- 사용자가 어떤 액션 (예: realization 추가) 시작하면, eligible 노드만 graph 상에서 highlight.

**우리 현재**: 없음 (모든 액션이 form-기반).
**차용 우선순위**: ⭐⭐ — 모델링 액션 단계에서 가치.

---

## Section E — onTong OntologyGraph Adoption Matrix

| # | 패턴 | 영역 | 현재 상태 | 차용/적응/skip | 우선순위 | 구현 비용 |
|---|---|---|---|---|---|---|
| E1 | Auto-layout + manual drag | 기본 | ✅ 보유 | keep | — | — |
| E2 | Color group (사용자 지정) | UX | ❌ | 차용 | ★★★ | 중 |
| E3 | Multi-select + bulk op | UX | ❌ | 차용 | ★★★ | 중 |
| E4 | Save/share view | 협업 | ❌ | 차용 | ★★★★ | 중 |
| E5 | SVG/PNG export | 협업 | ❌ | 차용 | ★★★ | 낮 |
| E6 | Right-click context menu | UX | ❌ | 차용 | ★★★★ | 중 |
| E7 | Bottom preview panel + pin | UX | ❌ | 차용 | ★★★★ | 중 |
| E8 | Hop-by-hop expand arrows | 탐색 | ❌ | 차용 | ★★★★ | 중 |
| E9 | Selection vs Panning mode toggle | UX | ❌ | 차용 (E3 prereq) | ★★★ | 낮 |
| E10 | Search-driven entry | 탐색 | 부분 | 강화 | ★★★★ | 중 |
| E11 | Group sidebar (domain tree) | 탐색 | ❌ | 차용 | ★★★★ | 중 |
| E12 | 250-node 임계 (자동 group 권장) | scale | 부분 (n_max) | 적응 | ★★★ | 낮 |
| E13 | Lazy edge label (hover/click) | edge density | ❌ | 차용 | ★★★ | 낮 |
| E14 | Compound expand-in-place | scale | ❌ (mode 전환만) | 차용 | ★★★★★ | 높 (ELK 도입) |
| E15 | Importance pruning | scale | ✅ weighted-degree | keep + PageRank 추가 검토 | ★★ | 낮 |
| E16 | Faceted filter (kind/role/verif/domain) | lens | 부분 (kind only) | 차용 | ★★★★★ | 중 |
| E17 | Perspective (named lens bundle) | lens | ❌ | 차용 | ★★★★★ | 중 |
| E18 | Search 결과 graph 누적 add | 탐색 | ❌ | 차용 | ★★★★ | 중 |
| E19 | Path discovery (K-shortest) | 탐색 | 부분 (단일 경로) | 적응 | ★★★ | 중 |
| E20 | Lineage 모드 (upstream/downstream 색) | viz | ❌ | 차용 | ★★★★ | 중 |
| E21 | Mini-graph hover preview | 탐색 | ❌ | 차용 | ★★★ | 중 |
| E22 | Time travel (graph diff) | viz | ❌ | 보류 | ★★ | 높 |
| E23 | Edge bundling (hierarchical) | edge density | ❌ | skip (cost > value) | ★ | 매우 높 |
| E24 | Adaptive styling (LOD) | scale | ❌ | 차용 | ★★★★ | 중 |
| E25 | GPU rendering (canvas/WebGL) | scale | ❌ | 보류 (5K 까지 SVG OK) | ★★ | 높 |
| E26 | Eligible-node highlight | 액션 | ❌ | 차용 (액션 추가 시) | ★★ | 낮 |
| E27 | Backstage 식 4-level top-down nav | IA | ❌ | 차용 | ★★★★ | 높 (별도 화면) |
| E28 | DataHub 식 column→method-level toggle | code-aware | ❌ | 차용 | ★★★★★ | 높 (스키마 + UI) |
| E29 | Structurizr C4 4-level view | IA | ❌ | 차용 | ★★★★ | 중 |
| E30 | IntelliJ "Focus on paths" | 탐색 | ✅ path mode | keep | — | — |
| E31 | CAST 식 transaction path (workflow trace) | code-aware | ❌ | 차용 (Action workflow) | ★★★ | 중 |
| E32 | AppMap 식 runtime trace overlay | sim | ❌ | 보류 (Step 8 시뮬 후) | ★★ | 높 |
| E33 | Edge kind toggle (extends/implements/...) | lens | ❌ | 차용 (E16 의 일부) | ★★★ | 낮 |
| E34 | Folder + text node (canvas annotation) | UX | ❌ | 보류 | ★★ | 중 |
| E35 | Slicer (timestamp slider) | viz | ❌ | 보류 (데모용) | ★★ | 중 |
| E36 | Cross-ontology / cross-repo navigation | scale | ❌ | 보류 | ★ | 매우 높 |
| E37 | "Find indirect connections" query | 탐색 | ❌ | 보류 | ★★ | 중 |
| E38 | Impact analysis as separate view | 분석 | ❌ | 차용 | ★★★ | 중 |

### E.39 우선순위 그룹 (★★★★★ = 8개)

**Tier S (★★★★★ — 차세대 핵심 5개)**:
- E14 Compound expand-in-place
- E16 Faceted filter (multi-dimension)
- E17 Perspective (named lens)
- E28 Code-Domain 2-level toggle (CodeType ↔ method, Term ↔ sub-term)

**Tier A (★★★★ — 9개)**:
- E4 Save/share view
- E6 Right-click context menu
- E7 Bottom preview panel
- E8 Hop-by-hop expand arrows
- E10 Search-driven entry
- E11 Group sidebar (domain tree)
- E18 Search 결과 graph 누적
- E20 Lineage 모드 (색 분리)
- E24 Adaptive styling (LOD)
- E27 Backstage 4-level top-down
- E29 Structurizr C4 view

**Tier B (★★★ — 8개)** + **Tier C/skip — 16개** 생략 (matrix 참조).

---

## Section F — 차세대 OntologyGraph 청사진 (Spec 1-2 페이지)

### F.1 비전 (1단락)

**현재**: xyflow + dagre + 3 mode 의 단일 캔버스. focus + n_max 로 5K class 까지 실용. 그러나 (a) 정적 lens (kind only), (b) cluster expand 불연속, (c) save/share 부재, (d) detail 컨텍스트 단절, (e) hover/preview 부재.

**Next**: **Perspective-driven, multi-level, lens-rich graph workspace**. 한 화면 다 보여주는 graph 가 아니라, 사용자가 자신의 lens (perspective) 로 들어와 부분 expand 하면서 detail 을 graph 옆에 keep 하는 작업 환경.

### F.2 IA 변화

```
[기존]  /modeling/ontology → OntologyGraph 단일 캔버스

[제안]  /modeling/ontology
        ├ 좌: Domain Tree Sidebar          (Backstage-식, Top-down)
        ├ 중상: Graph Canvas               (Perspective + multi-level)
        ├ 중하: Preview Panel (pin/split)  (Quiver-식, detail)
        └ 우: Perspective + Filter Panel   (Bloom-식, faceted lens)
```

### F.3 Layout Engine

- **dagre → ELK Layered** 마이그레이션 검토. 이유: compound nodes (E14) 지원.
- ELK 의 "cross-hierarchy edges" + "bottom-up compound layout" 가 우리 패키지/도메인 hierarchy + relational 동시 처리에 적합.
- xyflow + ELK 통합 예시: jointJS 데모 / reactflow ELK plugin.

### F.4 Perspective (Bloom 차용)

**Schema**:
```python
class Perspective(BaseModel):
    fqn: str                            # "perspective.scm.order_view"
    label: str                          # "Order Workflow Lens"
    description: str
    # filter
    include_kinds: set[NodeKind]        # {term, code_type, action}
    include_edge_kinds: set[EdgeKind]   # {extends, type_realization_partial}
    domain_filter: list[str] | None
    role_filter: list[str] | None
    verification_min: VerificationLevel | None
    # style
    color_rules: list[ColorRule]        # [{filter: "role=workflow", color: "#fb923c"}]
    label_visibility: Literal["always", "hover", "selected"]
    # focus
    initial_focus_fqn: str | None
    saved_layout: dict | None           # 노드 좌표 박제
    saved_visible_nodes: set[str] | None  # named view
    # 검색 prefab
    search_queries: list[SavedQuery]
```

**Endpoint**: GET / POST `/api/ontology/perspectives` + share URL `/ontology?perspective=<fqn>`.

### F.5 Multi-level (E14 + E28)

**3 추상 level**:
1. **Domain level** (top): Domain 노드 + inter-domain 의존 (집계).
2. **Type level** (default): 현재 BusinessTerm + CodeType + Action.
3. **Member level** (zoom in): CodeType expand → method 노드. Term expand → sub-term composition. Action expand → ActionParam + ActionEffect.

**전환**:
- Zoom + LOD 자동 전환 (E24).
- 노드 클릭 → 그 노드만 in-place expand (E19).

### F.6 Faceted Filter Panel (E16)

```
[ Perspective ▾ Order Workflow Lens     ]   ⓘ Save | Share | Export
─────────────────────────────────────────
Node kind   ☑ Term  ☑ CodeType  ☑ Action
Edge kind   ☑ extends ☐ implements ☑ partial
Domain      [scm ✕] [process ✕] + add
Role        [workflow ✕] + add
Verification ≥ [ DRAFT ▾ ]
─────────────────────────────────────────
[ Search 🔍 ............................ ]
  + 결과 누적 add to graph
```

### F.7 Workspace 인터랙션

- **Right-click menu** (E6): View dependencies / Expand here / Hide / Pin preview / Set focus / Find path to...
- **Multi-select** (E3, E9): drag-rect 다중 → 색 group / hide / 일괄 Action 적용.
- **Bottom preview panel** (E7): 클릭 = 채움, pin = keep, split = 비교.
- **Hop-by-hop expand** (E8): 노드 ←→ 화살표 = 1-hop expand. n_max slider 는 advanced 로.
- **Lineage 모드** (E20): 노드 우클릭 → "Show lineage" → upstream 빨강 / downstream 파랑.
- **Domain tree sidebar** (E11): top-down nav. 도메인 클릭 = 그 도메인 노드들로 perspective 자동 만들어 채움.

### F.8 단계적 도입 제안 (사용자 승인 영역)

이 파일은 **Stage 3** 산출물 — 결정 X. Stage 4 (adoption decision) 회의에서 사용자가 우선순위 정함. 본 spec 은 ceiling (다 한다면 이렇게) 의 그림만.

---

## 신뢰도 + 한계

### 섹션별 신뢰도

| Section | docs/직접 fetch | 추정 비율 |
|---|---|---|
| A Palantir 6 화면 | 75% | 25% |
| B 외부 5 도구 | 80% | 20% |
| C Code-aware | 60% | 40% (prior art 빈약 자체가 발견) |
| D 기술 패턴 | 85% | 15% |
| E Adoption matrix | n/a | 우리 판단 |
| F 청사진 | n/a | 우리 spec |

### 한계

1. **Foundry docs 의 graph viz 영역은 의외로 얕음** — group 기반 분할만 권장하고, 1000+ object type 의 화면 캡처가 docs 에 없음. 우리가 직접 Foundry 환경 접근 불가.
2. **Bloom / KeyLines 는 commercial** — 라이브 데모 본 적 없음. docs + 블로그 글만.
3. **Code-aware 영역의 prior art 결핍 자체** — 정량화 어려움. CAST Imaging 같은 고가 commercial 만 가까운데 detail 미공개.
4. **xyflow → ELK 마이그레이션 cost** 는 별도 spike 필요 — F.3 의 권고는 [추정] 기반.
5. **사용자 5K class 가정 검증 안 됨** — 실제 5K class import 테스트 필요. 현재 데모는 117 노드.

---

## Sources

- [Palantir Quiver Analysis Graph](https://www.palantir.com/docs/foundry/quiver/analysis-graph)
- [Palantir Data Lineage Explore](https://www.palantir.com/docs/foundry/data-lineage/explore-lineage)
- [Palantir Object Explorer](https://www.palantir.com/docs/foundry/object-explorer/getting-started)
- [Palantir AIP Logic Blocks](https://www.palantir.com/docs/foundry/logic/blocks)
- [Palantir Pipeline Builder](https://www.palantir.com/docs/foundry/pipeline-builder/overview)
- [Neo4j Bloom Perspectives](https://neo4j.com/docs/bloom-user-guide/current/bloom-perspectives/bloom-perspectives/)
- [Cambridge Intelligence — Big Graph 5 Steps](https://cambridge-intelligence.com/big-graph-data-visualization/)
- [Cambridge Intelligence — Very Large Networks](https://cambridge-intelligence.com/visualizing-very-large-networks-an-update/)
- [Sourcegraph Cross-Repo Navigation](https://sourcegraph.com/blog/cross-repository-code-navigation)
- [Backstage Catalog Graph](https://backstage.io/docs/features/software-catalog/creating-the-catalog-graph/)
- [Spotify Engineering — Software Visualization](https://engineering.atspotify.com/2022/07/software-visualization-challenge-accepted)
- [Apache Atlas / DataHub — Column-Level Lineage](https://datahub.com/blog/column-level-lineage-comes-to-datahub/)
- [Linkurious — Path Discovery](https://linkurious.com/platform/)
- [IntelliJ UML Class Diagram](https://www.jetbrains.com/help/idea/class-diagram.html)
- [IntelliJ Module Dependency Diagram](https://www.jetbrains.com/help/idea/project-module-dependencies-diagram.html)
- [Structurizr — C4 Model](https://structurizr.com/)
- [CAST Imaging — Capabilities](https://www.castsoftware.com/imaging/capabilities)
- [Cytoscape.js Expand-Collapse Extension](https://github.com/iVis-at-Bilkent/cytoscape.js-expand-collapse)
- [Eclipse Layout Kernel (ELK)](https://eclipse.dev/elk/)
- [ELK Layered Algorithm](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)
- [Hierarchical Edge Bundling — Data to Viz](https://www.data-to-viz.com/graph/edge_bundling.html)
- [Multi-faceted Graph Visualization Survey (PDF)](https://www.researchgate.net/publication/274633015_A_Survey_of_Multi-faceted_Graph_Visualization)

끝.
