# Sidebar / Chrome / Breadcrumb Noise Audit (Modeling Section 2)

**Audit B 와 분리 — 5 Detail 본문 (MainPanel ForwardDetail 의 Action/Term/CodeType/BR/Anchor 5종) 은 본 문서 범위 밖이다.**
대상: TopBar · LeftPanel (탭 + ModuleTree + OntologyTab + QueueTab) · MainPanel 상단 모드바 + activeKind 라인 · RightPanel 의 탭 헤더 + selection breadcrumb · StatusBar.

작성: 2026-05-10. 코드 스냅샷 = 현 main.

---

## Section 1 — FQN / Path 표시 사이트 매핑 (모든 발생지)

| # | Component | Element / Line | 표시되는 path 형태 | 왜 거기 있는가 | Verdict |
|---|-----------|---------------|-------------------|---------------|---------|
| 1 | `TopBar.tsx:38` | breadcrumb `Crumb label={activeRepoId}` | `slab-design-real` 같은 repo 식별자 (full string) | "어떤 repo 인가" 표시 | KEEP — repo 는 다른 곳 어디서도 안 보임 |
| 2 | `TopBar.tsx:40` | breadcrumb `Crumb label={view}` | `Detail` / `Graph` (모드 라벨) | "어떤 mode" 표시 | KEEP (단, MainPanel 모드바와 중복 — Sec 2-#1) |
| 3 | `TopBar.tsx:43-46` | breadcrumb selection crumb | `selection` = `selectedActionFqn?.split(".").pop()` 등의 simple name (mono) | "지금 뭘 보고 있는가" | KEEP (이게 canonical site 후보 #1) |
| 4 | `TopBar.tsx:47-52` | breadcrumb `Lens: ${lens}` | 항상 `Lens: verify` (default) | 미래 lens 전환용 placeholder | **REMOVE — dead** (lens 는 store 에서 set 함수도 안 호출됨, default `"verify"` 영구 노출. PerspectiveDropdown 도 `lens: null` 로 spec 넣음 = 의미 없음) |
| 5 | `MainPanel.tsx:55-61` | `<div>현재 ${KIND_LABEL}: <code>{id.split(".").pop()}</code></div>` | simple name (last segment) | "지금 뭘 보고 있는가" | **REDUNDANT — TopBar #3 과 100% 중복** (kind 라벨만 풀어쓴 차이). COLLAPSE |
| 6 | `RightPanel.tsx:113-122` | "선택:" breadcrumb (font-mono `selection.id.split(".").pop()` + `(kind)`) | simple name + kind text | "지금 우측 패널이 무엇을 보여주나" | **REDUNDANT — TopBar #3 + MainPanel #5 와 3중 중복.** Pane 분리에 도움 안 됨. REMOVE or 두 단계 path (e.g. `Action › calculatePrice`) |
| 7 | `RightPanel.tsx:217` (TabCode) | `<div>{m.parent_type_fqn}</div>` (full FQN, break-all) | `com.scm.api.std.OrderService` 같은 부모 타입 풀 path | 메서드 컨텍스트 — Detail h1 에 이미 있음 | REDUNDANT — Audit B (Detail) 에 있는 본문 헤더와 또 중복. COLLAPSE to last segment + tooltip |
| 8 | `RightPanel.tsx:236` (TabCode) | `<div>{ct.fqn}</div>` (full FQN) | full CodeType FQN | CodeType 컨텍스트 표시 | 같은 이유 — REDUNDANT |
| 9 | `RightPanel.tsx:241` (TabCode) | `<div>{ct.source_file}</div>` | `src/main/java/com/scm/.../OrderService.java` 풀 경로 | 소스 파일 위치 | KEEP — 유일하게 file path 보여주는 곳. 단 `…/OrderService.java` 중간 elide 권장 |
| 10 | `RightPanel.tsx:417` (TabImpact, actions) | `<span class="font-mono">{a.fqn}</span>` (break-all) | Action 풀 FQN | 클릭 가능한 link target 라벨 | COLLAPSE — `a.label` (이미 두번째 줄에 있음) 기준으로 표시. FQN 은 hover/title 만 |
| 11 | `RightPanel.tsx:440` (TabImpact, rules) | `<span>{r.fqn}</span>` (full BR FQN) | BR 풀 FQN | link target 라벨 | COLLAPSE — last segment + tooltip |
| 12 | `RightPanel.tsx:456` (TabImpact, anchors) | `<span>{a.anchor_locator}</span>` | anchor locator 문자열 (이미 짧은 편) | locator 식별 | KEEP |
| 13 | `RightPanel.tsx:458` (TabImpact, anchors) | `<div>→ {a.target_slot}</div>` | slot path | anchor 의 target slot | KEEP |
| 14 | `RightPanel.tsx:471-475` (TabImpact, related terms) | `<button class="font-mono break-all">{t}</button>` | Term 풀 FQN | link target 라벨 | COLLAPSE — last segment + tooltip |
| 15 | `RightPanel.tsx:455` (TabImpact, anchors) | `<span>L{a.line ?? "?"}</span>` | 라인 번호 prefix | 위치 표시 | KEEP |
| 16 | `LeftPanel.tsx:393` (QueueRow term subtitle) | `subtitle={\`${t.kind}…\`}` 안에 `aliases.slice(0,2).join(", ")` | kind + alias (FQN 아님) | 매핑 후보 미리보기 | KEEP — aliases 가 짧음 |
| 17 | `LeftPanel.tsx:413` (QueueRow action subtitle) | `\`on ${a.declared_on_term.split(".").pop()}\`` | last segment of term FQN | "이 action 이 어느 term 에 매달렸나" | KEEP — 이미 last segment |
| 18 | `LeftPanel.tsx:432` (QueueRow realization) | `\`${r.code_type_fqn.split(".").pop()} → ${r.term_fqn.split(".").pop()}\`` | 양쪽 last segment + arrow | TypeRealization 미리보기 | KEEP — 잘 짧혀짐 |
| 19 | `LeftPanel.tsx:462` (QueueRow legacy unmapped) | `<div class="truncate">{u.code_method.fqn}</div>` | method 풀 FQN (full!) | 미매핑 method 식별 | COLLAPSE — `ClassName.methodName` 로 줄이고 hover 시 full |
| 20 | `LeftPanel.tsx:509` (QueueRow tag footer) | `<div class="font-mono text-[9px]" title={tag}>{tag}</div>` | tag = `t.fqn` / `a.fqn` / `tr#${id}` | 명시적 ID 표시 (구별용) | OK — 이미 9px 회색 + truncate. KEEP, but `text-[9px]` 가 거의 안 보임 → 9.5–10px 권장 |
| 21 | `OntologyTab.tsx:336` (TermRow) | `<span class="font-mono">{t.label}</span>` | label (보통 한국어) | 트리 row label | KEEP — label 이 FQN 아님 |
| 22 | `OntologyTab.tsx:330` (TermRow) | `title={\`${t.fqn}\\n${t.description}\`}` | hover 시 full FQN + 설명 | 정확한 식별이 필요할 때 | KEEP — hover only, 좋은 패턴 |
| 23 | `OntologyTab.tsx:355` (ActionRow) | `<span>{a.label}</span>` + `title={a.fqn}…` | label + hover full | 같은 패턴 | KEEP |
| 24 | `OntologyTab.tsx:378` (BRRow) | `<span>{r.fqn}</span>` (full!) | BR 풀 FQN | BR 는 label 이 없음 | COLLAPSE — 마지막 1–2 segment + tooltip. BR fqn 은 보통 매우 김 |
| 25 | `OntologyTab.tsx:395` (AnchorRow) | `<span>{a.anchor_locator}</span>` | locator (이미 짧은 편) | row label | KEEP |
| 26 | `ModuleTree.tsx:286-289` (renderNode prefix) | `<span class="text-muted-foreground/60">{prefix.join(".")}.</span><span>{n.name}</span>` | 압축된 chain prefix + 마지막 segment | 빈 패키지 chain 압축 | KEEP — 명시적으로 "중간이 비어있다" 시각화. 좋은 패턴 |
| 27 | `ModuleTree.tsx:332` (class leaf) | `title={it.fqn}` | hover 시 full FQN | 정확한 ID 필요 시 | KEEP — hover only |
| 28 | `ModuleTree.tsx:336` (class leaf body) | `<span class="font-mono">{it.simple_name}</span>` | simple name | 트리 row | KEEP |
| 29 | `ModuleTree.tsx:362-366` (action leaf) | `title={\`${a.fqn}\\nkind:…\\n→ ${primary_method_fqn}\`}` | hover 시 multiline detail | 풀 FQN 과 primary method | KEEP — hover only |
| 30 | `ModuleTree.tsx:443-466` (search results) | `parent` (FQN 의 fqn − simple name 부분) + `simple` (마지막 segment) | full parent path (truncate) + simple name + kind badge | 검색 결과 컨텍스트 | KEEP — 검색은 path 가 핵심 |
| 31 | `ModuleTree.tsx:513` (selectedPkg 패널) | `<span class="truncate" title={selectedPkg}>{selectedPkg}</span>` | full package path | 선택된 패키지 표시 | OVERLAP with #26 (chain prefix) — 이 패널 자체가 inline tree 와 기능 중복. Sec 2-#3 참조 |
| 32 | `MainPanel.tsx:200`+ (Detail 본문) | h1 의 entity FQN | full FQN | Detail h1 | **Audit B 범위** — 본 문서에서 평가 안 함 |

**총 32 사이트** (그중 Audit B 범위 1개 제외 → **본 audit 가 평가 가능한 31 사이트**)

---

## Section 2 — 중복 패턴 Top 5

### Pattern 1 — 같은 entity 의 simple name 이 동시에 3 곳에 표시
**현장**: Action `com.scm.api.std.OrderService.calculatePrice` 선택 시:
- TopBar breadcrumb 마지막 crumb (`calculatePrice`) — TableRow #3
- MainPanel 상단 activeKind 라인 (`현재 Action: calculatePrice`) — TableRow #5
- RightPanel selection breadcrumb (`선택: calculatePrice (action)`) — TableRow #6
- (참고: Audit B 의 Detail h1 까지 합치면 4 곳)

**문제**: 같은 시각 정보가 화면 위·중·우 3 곳에 서로 다른 폰트·라벨로 반복. 사용자 시선 분산. "쓸데없는 경로 노출" 핵심 원인 #1.

**제안**: TopBar 의 breadcrumb 을 SOLE 위치로 승격. MainPanel 의 activeKind 라인은 **REMOVE** (모드 토글만 남기고 헤더 슬림화). RightPanel 의 selection breadcrumb 은 **REMOVE** — kind 별 색칠된 작은 1-line badge 정도로 (`🟠 Action`) 축소.

---

### Pattern 2 — Mode/View 가 두 곳에 표시
- TopBar breadcrumb `Crumb label={view}` (`Detail` / `Graph`) — TableRow #2
- MainPanel 상단 모드 토글 그룹 (`Detail` / `↕ Split` / `🌐 Graph` / `✏️ Authoring`)

**문제**: 토글 자체가 현재 active 를 highlight 로 보여줌. TopBar 의 view crumb 는 동일 정보를 read-only 로 또 보여줌 → 잉여.

**제안**: TopBar 의 view crumb 을 **REMOVE**. 모드 토글이 SOT.

---

### Pattern 3 — ModuleTree 의 inline 클래스 leaf vs selectedPkg 패널 = 같은 데이터 두 번
- ModuleTree.tsx:321-344 — `hasDirectClasses` 인 패키지 expand 시 inline 으로 class leaves 를 트리 row 로 렌더 (예: `OrderService 12m`).
- ModuleTree.tsx:510-548 — `selectedPkg` 가 있으면 트리 하단에 같은 inventory 가 별도 패널로 또 렌더 (`max-h-72`, X 닫기 버튼).

**문제**: 사용자가 `direct_classes>0` 인 패키지를 클릭하면 (toggle 함수가 그렇게 함, `setSelectedPkg(n.path)` 호출 — 264-270번 라인) 같은 클래스 list 가 inline tree + 하단 패널 두 곳에 동시에 나타남.

**제안**: 하단 inventory 패널을 **REMOVE**. inline tree leaf 가 충분 (오히려 더 자연스러운 navigation). 만약 그룹별 dense view 가 필요하면 `searchPkg` 같은 별도 입구로.

---

### Pattern 4 — 카운트 / 진행률이 3 곳에 분산
- StatusBar 하단 — `LEVELS` 6개 badge (U/D/SL/BA/SV/PR) + 총합 + BODY_ANCHORED+ % — TableRow에 없음, 별도
- LeftPanel 의 OntologyTab 헤더 — `atomic / composite / action / rule / anchor` 카운트
- LeftPanel 의 OntologyTab section header sub — 예: `confirmed N / draft M`
- LeftPanel 의 QueueTab section tabs — `Term N · Action M · Real K · Code L`

**문제**: 6개 verification level + 5개 entity 카운트 + 4개 queue 카운트 = 화면에 동시에 카운트가 ~15개. 시각 noise.

**제안**: StatusBar 의 6 level badges 는 **COLLAPSE** — 가장 의미 있는 것만 (예: `✓ 23/47 confirmed (49%)`) 로. 6 level 분포는 hover 시 popover 로. OntologyTab section header sub 는 좋음 (KEEP). QueueTab tabs 카운트도 좋음 (KEEP) — 큐에서는 카운트가 핵심.

---

### Pattern 5 — RightPanel TabCode 가 Detail 본문 정보를 작은 글씨로 똑같이 또 보여줌
- RightPanel TabCode (RightPanel.tsx:212-247) — method/codeType 의 parent FQN, name+params, line range, role, 코드 본문 미리보기
- MainPanel Detail 본문 (Audit B) — 동일 데이터의 풀 디스플레이

**문제**: RightPanel TabCode 의 존재 의의가 불명. Detail 이 더 풍부한데, "요약" 라벨로 같은 정보를 작게 또 보여줌.

**제안**: RightPanel TabCode 를 **CALLEES & 호출 통계 패널** 등으로 PROMOTE 하거나, 아니면 코드 본문 미리보기 (JavaCode) 만 남기고 메타데이터 (FQN/role/line) 는 모두 **REMOVE** (Detail 에서 본다).

---

## Section 3 — Dead UI 인벤토리

| # | 위치 | Element | 왜 dead 인가 | Verdict |
|---|------|---------|-------------|---------|
| 1 | TopBar.tsx:47-52 | `lens !== "none"` crumb (`Lens: verify`) | `setLens` 호출처 0개 (grep 결과). default `"verify"` 영구 노출. PerspectiveDropdown 의 saved spec 에서도 `lens: null` 로 무력화. | **REMOVE** — 또는 배선 작업 후 살리기 |
| 2 | MainPanel.tsx:74-80 | `🔧 Backward` 버튼 (disabled) | 영구 disabled, `title="Backward 모드 — 다음 phase"`. 사용자에게 "이게 곧 온다" 를 alarming 하게만 보여줌 | **REMOVE** — phase 도달 전까지는 숨기는 게 맞음. 또는 옅은 "coming soon" 칩으로 |
| 3 | TopBar.tsx:80-82 | `🟢 시뮬` 버튼 (disabled) | 영구 disabled, `title="Simulation Engine — 다음 phase"`. 같은 이유 | **REMOVE** 또는 매우 옅게 |
| 4 | RightPanel.tsx 매뉴얼 탭 (`TabManual`) | "📖 매뉴얼" 탭 — 본문 전부 "Phase E 미구현" 안내 | 항상 빈 콘텐츠 + 미구현 메시지. 탭이 클릭 가능한 채로 노출됨 | **REMOVE** 탭 자체. Phase E 구현 시 다시 추가 |
| 5 | RightPanel.tsx:301-305 (TabCallSite) | `selection.kind !== "action"` 일 때 "호출지점은 Action 또는 CodeMethod 선택 시만 표시. 현재 ${kind}." | term/rule/anchor 선택 시 항상 같은 안내. 탭 자체가 활성 가능 → 사용자가 클릭하고 후회 | 탭을 disable 하거나 (kind 별로 적용 가능한 탭만) **HIDE** |
| 6 | RightPanel.tsx:201-208 (TabCode) | term/rule 선택 시 "Term/BR 은 코드 method 와 직접 매핑 안 됨" 안내 | 같은 패턴 — 탭이 활성인 채 항상 빈 안내 표시 | term/rule 일 때 코드 탭을 자동 숨김 또는 disable |
| 7 | OntologyTab.tsx:339 (TermRow) | `<span>{(t as { value_type?: string }).value_type ?? ""}</span>` | DTO 에 `value_type` 이 없는 term 이 대부분. 빈 string 으로 폭만 차지하는 zero-info span | **REMOVE** — 있을 때만 conditional |
| 8 | TopBar.tsx 검색 버튼 vs ModuleTree 검색 input | Top bar 의 `⌘K` 검색 + 좌측 ModuleTree 검색 input + 좌측 OntologyTab 검색 input 총 3개 검색 | 3개 검색 입구 — 어떤 것이 어디까지 검색하는지 사용자 학습 부담 | 통합 — Sec 4-#5 |
| 9 | StatusBar.tsx:11 LEVELS array | `signature_locked (SL)` `body_anchored (BA)` 두 badge 가 회색 (border-border) — color cue 없음 | unmapped(U)/draft(D)/sim_verified(SV)/pr_proven(PR) 만 색상. SL/BA 는 회색 = 의미 없는 노이즈 | SL/BA 도 옅은 emerald gradient 로 ADD-COLOR, 아니면 통합 |
| 10 | OntologyTab.tsx:115 — `domain` "(도메인 없음)" | term/action 에 domain 이 빈 경우 "(도메인 없음)" 그룹 헤더로 표시 | 첫 import 직후 모든 term 이 여기 모이면 "(도메인 없음) · 287" 같이 노이즈 | **RELABEL** to "분류 미지정" + 카운트 0 일 때 그룹 자체 hide |

---

## Section 4 — 명확성 갭 (Clarity)

| # | 위치 | 문제 | 제안 |
|---|------|------|------|
| 1 | LeftPanel.tsx:354-358 (Queue tabs) | `Real` 탭 라벨 — Realization 의 약어. 처음 보는 사용자는 "Real(time)?" 으로 오해 가능 | RELABEL `Real` → `타입 실현` 또는 `TypeReal` |
| 2 | LeftPanel.tsx:357 | `Code` 탭 — 사실은 "legacy 미매핑/모호 큐". "Code" 는 좌측 `코드` 탭과 라벨 충돌 | RELABEL `Code` → `미매핑/모호` |
| 3 | RightPanel.tsx:21 (RightPanel TABS) | `📜 이력` — 너무 짧음 ("이력" = "history" 인지 "변경이력" 인지 모호) | RELABEL → `📜 변경이력` |
| 4 | RightPanel.tsx:24 | `🌊 영향` — 시각적으로 신선하지만 "이 entity 의 영향 범위" 라는 의미 불명확. 영향을 "받는" 건지 "주는" 건지 | RELABEL → `🌊 연결관계` 또는 ADD-CAPTION (HelpHint) |
| 5 | TopBar.tsx 검색 + ModuleTree 검색 + OntologyTab 검색 | 3개 검색 입구 — 차이가 placeholder 에 모호 ("검색 / 명령" vs "검색 (클래스 / 메서드 / Term / Action)" vs "검색 (Term / Action / BR / Anchor)") | TopBar `⌘K` 만 글로벌 검색 (좌측 두 검색은 트리 필터 전용임을 placeholder 로 명시: `필터: 클래스 이름…`) |
| 6 | LeftPanel.tsx 좌측 메인 탭 (`코드 / 온톨로지 / 큐`) | 이모지 (🗂 🧬 📥) 만 구분, 라벨은 한국어 1단어 — 처음 사용자가 차이 학습 어려움 | ADD-CAPTION via HelpHint 또는 longer label |
| 7 | StatusBar 의 6 LEVELS badge | U/D/SL/BA/SV/PR — 약어. legend 없음 | ADD-CAPTION HelpHint 1개 우측에 (`?`) — 6 level 의미 표 |
| 8 | StatusBar.tsx:71-73 | `🔍 Forward 모드` / `🔧 Backward 모드` text | Backward 가 disabled 인 현재, 항상 Forward 표시 → 뭘 표시하는지 사용자 불명확. context 도움 안 됨 | **REMOVE** until Backward ships |
| 9 | OntologyTab.tsx:332-334 (TermRow dot) | atomic = emerald dot, composite = violet dot — 위 헤더의 emerald `atomic (N)` / violet `composite (N)` 텍스트와 색 매치는 OK. 그러나 처음 보는 사람은 dot 색 의미 모름 | KEEP (헤더 카운트가 legend 역할) — 단 헤더 카운트와 dot 사이가 멀면 (스크롤 시) dot 색 의미 잊음. ADD-CAPTION 1줄 |
| 10 | OntologyTab.tsx:359 (ActionRow draft `·` icon) | draft 시 "·" (가운데점). hover 해야 "draft" 의미 알 수 있음 | RELABEL → 작은 amber `D` 칩 (verification level 약어와 통일) |

---

## Section 5 — Tree Scale 우려 (5K class)

`ModuleTree.tsx` 분석 (rendered row 당 시각 요소):

### 5-1. 패키지 row (lines 264-302)
**현재 노출**:
- chevron (toggle) 또는 빈 공간
- folder/box 아이콘
- compressed prefix (옅은 회색, optional, 좋은 압축)
- name (마지막 segment)
- right-aligned counts: `direct_classes` + `/total_classes` + `T${terms}` + `A${actions}` (보라/주황 색칠)

**5K class 시 우려**:
- `T${n}` `A${n}` 색칠 카운트가 모든 패키지 row 에 표시 → 숫자만 보아도 너무 많음. 패키지 trees 가 깊어지면 (e.g. depth 6) 작은 화면에서 가독성 깨짐.
- compressed prefix 는 좋은 패턴이지만, 검색 모드에서 disable 되므로 검색 결과는 path 가 항상 길어서 truncate 발생.

**제안**:
- 패키지 row 의 `T${n}` / `A${n}` 카운트를 **HOVER ONLY** (title 에) 로. `direct_classes/total` 카운트만 항상 표시.
- 또는 `Lens` 가 도입되면 그때만 표시 (Term/Action lens 시).

### 5-2. Class leaf row (lines 321-344)
**현재 노출**:
- RoleDot (6px)
- `simple_name` (font-mono truncate)
- `★` (has_term 표시) — 옅은 violet, 9px
- `${method_count}m` (옅은 회색 9px)

**5K class 시 우려**:
- `${method_count}m` 가 거의 모든 row 에 표시. 9px 작아서 noise 보다는 dense 정보 제공으로 OK.
- `★` 는 매핑된 class 만 → 명확한 status indicator. KEEP.
- RoleDot 색 (`domain=#a78bfa`, `framework=#94a3b8`, `infra=#fbbf24`) 은 legend 없음 → 5K rows 스크롤할 때 어느 색이 무엇인지 학습 부담.

**제안**:
- RoleDot 위에 sticky legend (3 dot + 라벨) 1줄 추가 — 트리 헤더 바로 아래.
- `${method_count}m` 는 큰 클래스 (e.g. `>20m`) 만 표시하고 작은 건 생략 — visual rhythm 유지.

### 5-3. Action leaf row (lines 356-377)
**현재 노출**:
- 주황 square (2x2 px)
- `name` (font-mono)
- ✓ (confirmed) 또는 · (draft) — green / amber
- `${realization_count}r` (옅은 회색)

**5K class × ~3 action/class = 15K action 가능 시 우려**:
- 모든 action row 에 4개 시각 요소. dense 하지만 일관됨 (KEEP).

### 5-4. 검색 결과 row (lines 443-468)
**현재 노출**:
- KindBadge (color-coded `class/mtd/term/act/rule`) — 좋음
- `simple` (font-mono truncate)
- `label` (옅은 회색, simple 과 다를 때만)
- `parent` (옅은 회색, max-w-40%, truncate)

**KEEP** — 검색 결과는 path 가 핵심 정보. 좋은 패턴.

### 5-5. 시각적 rhythm 깨짐 시점
500 row 스크롤 시:
- 패키지 row 와 leaf row 의 폰트 크기 차이 (12px vs 11.5px) 미미 → 단계 구분 약함. **CONCERN**: 깊은 hierarchy 에서 어디가 패키지인지 어디가 leaf 인지 헷갈림.
- 들여쓰기 (depth × 12px) — 충분.
- 추천: 패키지 row 에 옅은 background tint (e.g. `bg-muted/20`) 한 줄, leaf 는 plain — visual rhythm 강화.

---

## Section 6 — Canonical FQN Site 규칙 제안

> **원칙**: 같은 entity 의 full FQN 은 화면 한 곳에서만 읽을 수 있다. 다른 곳은 모두 simple name + tooltip.

### 정의
- **Full FQN**: `com.scm.api.std.OrderService.calculatePrice(BigDecimal,String)`
- **Compact**: `OrderService.calculatePrice` (parent type . simple name)
- **Simple**: `calculatePrice` (마지막 segment)
- **Label**: 한국어 라벨 (`주문가격계산`)

### Sole-Site 매트릭스

| 표시 형태 | 유일 위치 | 비고 |
|----------|----------|------|
| Full FQN | **MainPanel Detail 본문 헤더** (Audit B 범위) | 1차 정확한 식별이 필요한 단 1곳 |
| Compact | TopBar breadcrumb 마지막 crumb | 항상 visible 하므로 컨텍스트 컴팩트 |
| Simple + label | LeftPanel 트리 row, OntologyTab row, 검색 결과 simple | navigation/scan 용 |
| Simple + tooltip = Full | RightPanel TabImpact link, QueueRow `tag` footer | 클릭 가능 link 의 hover 보조 |
| Full (read-only) | RightPanel TabCode 의 `parent_type_fqn` ❌ → simple+tooltip 으로 강등 | Detail 헤더와 중복 제거 |

### 변경 결과
- TopBar 가 컨텍스트 1차 위치 (한 줄, 항상 visible)
- MainPanel Detail h1 가 정확한 식별 1차 위치 (Audit B 가 결정)
- 그 외 모든 곳: simple/compact + tooltip — 화면에서 풀 path 제거

### Pseudo-규칙 (코드 패턴)
```
// rule
"표시는 simple/compact, 식별은 hover/title 로"
"tree row 는 항상 simple_name. parent 는 들여쓰기로"
"link button 안에 full FQN 노출 금지 — last segment + title"
"breadcrumb crumb 는 항상 한 segment씩, full path 는 첫 cell 이 repo 만"
```

---

## Section 7 — Top 10 Fixes (impact 순, with effort)

| # | Fix | Impact | Effort | 위치 |
|---|-----|--------|--------|------|
| 1 | **MainPanel 상단 activeKind 라인 REMOVE** — TopBar breadcrumb 이 동일 정보. 모드 토글만 남김 | ★★★ (사용자가 가장 많이 보는 화면 상단 1줄 제거) | S | MainPanel.tsx:54-62 |
| 2 | **RightPanel selection breadcrumb REMOVE** — 또는 작은 색칠 칩으로 축소 | ★★★ (우측 패널 column header 잡음 제거) | S | RightPanel.tsx:113-132 |
| 3 | **TopBar `Lens: verify` crumb REMOVE** (dead) — `lens` 실제 set 되는 곳 없음 | ★★ (영구 노출되는 의미 없는 텍스트 제거) | S | TopBar.tsx:47-52 |
| 4 | **Disabled 버튼 2개 REMOVE** — `🔧 Backward` (MainPanel), `🟢 시뮬` (TopBar) — 미구현 시 숨김 | ★★ (영구 disabled UI = "기능이 안 되는 시각적 알림") | S | MainPanel.tsx:74-80, TopBar.tsx:80-82 |
| 5 | **RightPanel TabCode 의 메타 라인 (parent FQN, simple_name, line, role) REMOVE** — Detail 본문에 동일. 코드 본문(JavaCode)만 남김 | ★★ (우측 column 의 `com.scm.api.std.X.Y(...)` 풀 path 노출 제거) | S | RightPanel.tsx:215-225, 232-247 |
| 6 | **Manual 탭 REMOVE** (Phase E 미구현 안내만) — 탭 자체 숨김 | ★★ (탭 헤더 1개 절약 + 사용자가 클릭하고 후회 X) | S | RightPanel.tsx:23, TabManual |
| 7 | **TabCallSite/TabCode 의 "이 kind 에 적용 안 됨" 안내 → 탭 자체 conditional hide** (term/rule 선택 시 탭 안 보임) | ★★ (RightPanel 탭 행이 selection 에 적응 — 의미 있는 탭만) | M | RightPanel.tsx selection 별 TABS 필터링 |
| 8 | **ModuleTree selectedPkg 패널 REMOVE** — inline tree leaf 가 동일 inventory. 두 곳에 같은 list 표시 제거 | ★★ (좌측 sidebar 하단 30% 영역 회수) | S | ModuleTree.tsx:510-548 |
| 9 | **OntologyTab BRRow / TabImpact 의 link 라벨에서 풀 BR FQN 제거** — last segment + tooltip | ★ (긴 BR FQN 이 좌측/우측에서 truncate 되는 노이즈 제거) | S | OntologyTab.tsx:378, RightPanel.tsx:440 |
| 10 | **StatusBar 의 6 LEVELS badge → 1줄 요약 (`✓ N/M (%) ▸ 분포 hover`)** + Forward/Backward text REMOVE | ★ (status bar 가 1줄로 명료해짐) | M | StatusBar.tsx 전체 |

### 부록 — Effort 정의
- **S** (Small) — 단일 컴포넌트의 conditional 변경, ~30 line 이하
- **M** (Medium) — 컴포넌트 간 props/state 시그너처 작은 조정
- **L** — 본 audit 에는 없음 (구조 재작성은 권장 안 함)

### 부록 — 빠른 시도 순서 (한 번의 PR 단위 권장)
1. Fixes #1 #2 #3 #4 #6 모두 한 PR — 모두 단순 삭제. visual diff 가 즉시 사용자에게 도움.
2. Fix #8 별도 PR — `selectedPkg` 패널 제거. 회기 테스트 (검색 → 패키지 클릭 → expand 흐름) 필요.
3. Fix #5 별도 PR — RightPanel TabCode 의 의미 재정의. Audit B 와 함께 검토.
4. Fix #7 별도 PR — TABS 의 selection-aware 필터링. middle effort.
5. Fix #9 #10 마지막 — polish.

---

## 부록 — 본 audit 가 평가하지 않은 영역
- **MainPanel 의 5 Detail 본문** (Action/Term/CodeType/BR/Anchor 의 ForwardDetail 컴포넌트 본체) — Audit B 범위.
- **GraphMode** (`GraphMode.tsx`) — 다른 화면, 별도 검토 권장.
- **AuthoringMode** — sidebar/chrome 영향 작음. 별도 검토 권장.
- **CmdKPalette** — 글로벌 검색 UX, 별도 검토 권장.
- **InlineEdit*** 컴포넌트 — Detail 본문 안의 edit affordance.
