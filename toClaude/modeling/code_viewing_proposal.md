# 코드 뷰잉 UX 개선 제안 (Modeling Section 2)

> 사용자 요구: "클래스 등 코드트리에서 코드가 있는 대상을 클릭하면 코드 내용을 잘 볼 수 있게 해줘. 모달이든 메인 detail이든 잘 찾아봐줘."
>
> 작성: 2026-05-10. 코드 변경 없음. 감사 + 옵션 제안 + 권고만.
>
> 관련 파일:
> - `frontend/src/components/sections/modeling/MainPanel.tsx` (1526줄, `CodeTypeDetail` @1063, `SplitMode` @528, `FqnLink` @1483)
> - `frontend/src/components/sections/modeling/RightPanel.tsx` (`TabCode` @159)
> - `frontend/src/components/sections/modeling/ModuleTree.tsx` (`renderNode` @238)
> - `frontend/src/components/sections/modeling/JavaCode.tsx` (lightweight tokenizer)
> - `frontend/src/components/sections/modeling/store.ts` (selection state)
> - `frontend/src/components/sections/modeling/ParamDrawer.tsx` (기존 slide-in drawer 패턴)

---

## 1. 현재 상태 감사 (Numbered Findings)

### 1.1 클릭 → 무엇이 뜨는가 — 클래스
1. ModuleTree leaf의 클래스 버튼 → `setSelectedCodeType(fqn)` (ModuleTree.tsx:326).
2. Store의 `selectOnly` 의미론으로 다른 4개 selection 은 자동 null (store.ts:120).
3. MainPanel `ForwardDetail` → `<CodeTypeDetail fqn={...} />` 라우팅 (MainPanel.tsx:144).
4. `CodeTypeDetail` (MainPanel.tsx:1063~1187) 가 **클래스 메타 정보**를 렌더 — kind, role, extends/implements, annotations, fields, **methods (시그니처만, 50개 cap)**, source_file 경로.
5. **메서드 body_text 는 표시 안 됨**. 메서드 행은 `name(args) → returnType` + role badge + line_start 만.
6. 동시에 RightPanel `TabCode` 가 `selection.kind === "codeType"` 분기로 **요약 카드** 표시 (RightPanel.tsx:232~247) — kind / role / field 수 / method 수 / source_file. body 없음. "전체 detail 은 가운데 패널 참고. 우측은 요약." 명시.

### 1.2 클릭 → 무엇이 뜨는가 — 메서드
1. ModuleTree 자체에서는 **메서드 leaf 가 없음**. 트리 표시는 패키지 → 클래스까지만.
2. 검색에서 `kind === "code_method"` hit 클릭 시 `parent type fqn` 으로 fallback (ModuleTree.tsx:136~140) — 클래스 detail 로 떨어지고 어떤 메서드를 골랐는지 잊힘.
3. `CodeTypeDetail`의 메서드 행(MainPanel.tsx:1153~1168)은 **클릭 불가능한 정적 div**.
4. 메서드 body 가 실제로 화면에 나타나는 유일한 경로:
   - `RightPanel TabCode` + selection 이 **action** 이거나 **anchor** 일 때 → `primary realization`의 `code_method_fqn` 으로 `getCodeType()` 호출 후 그 method 의 `body_text` 렌더 (RightPanel.tsx:163~197). 폭은 우측 사이드바 너비(rightWidth, 기본 380px) 안.
   - `MainPanel SplitMode` + selection 이 **action** 일 때 → 좌측 절반에 `<JavaCode>` 로 메서드 body 풀 표시 + 라인 마커 + 호버 동기화 (MainPanel.tsx:622~628).
5. **selection 이 codeType 일 때 메서드 body 를 보는 직접 경로는 없음.** Action 매핑이 있어야 우회 가능.

### 1.3 selection 모델 (store.ts)
1. 5종 selection: `selectedActionFqn / selectedCodeTypeFqn / selectedTermFqn / selectedRuleFqn / selectedAnchorId`. **`selectedCodeMethodFqn` 은 존재하지 않음** — 메서드는 1급 selection 이 아님.
2. `selectOnly` 가 새 selection 시 다른 4개를 강제 null 로 (store.ts:136~142). Action 보고 있다가 realization 메서드 클릭하면 **action context 를 잃을 가능성** 있음 (현재는 FqnLink 가 parent class 로 navigate 하므로 둘 다 잃음).

### 1.4 코드 본체가 보이는 위치 인벤토리
| 위치 | selection 트리거 | 표시 폭 | body? | 라인 마커 / 호버 |
|---|---|---|---|---|
| `RightPanel TabCode` (codeType 분기) | codeType | 380px (사이드바) | ❌ 메타만 | — |
| `RightPanel TabCode` (action 분기) | action | 380px (사이드바) | ✅ primary realization body | ❌ |
| `RightPanel TabCode` (anchor 분기) | anchor | 380px (사이드바) | ✅ method body | ❌ |
| `MainPanel SplitMode` | action | 50% (메인 절반) | ✅ primary realization body | ✅ markers + hover sync |
| `MainPanel CodeTypeDetail` | codeType | 메인 풀폭 | ❌ 시그니처만 | — |
| 그 외 | — | — | — | — |

→ **codeType selection 으로는 어디서도 body 를 못 봄.** Method 하나만 따로 골라서 body 만 보는 경로도 없음.

### 1.5 스케일 관련 관찰
1. `CodeTypeDetail` 의 methods 섹션은 `slice(0, 50)` 컷오프 + "… N 더" — 50 메서드 이상은 안 보임.
2. fields 도 30 컷오프.
3. body_text 는 50~200줄, 가끔 500+ — 한 클래스에 30 메서드면 모든 body 인라인 노출 시 평균 3000~6000줄 → **인라인 풀 노출은 가상 스크롤 없이 위험**.
4. JavaCode 컴포넌트는 `useMemo` 토큰화, line 단위 div — 1000줄 정도까지는 무리 없음 측정. 그 이상은 가상 스크롤 필요.

---

## 2. 식별된 갭 (요약)

| # | 갭 | 영향 |
|---|---|---|
| **G1** | 클래스 클릭 → 어떤 메서드의 body 도 못 봄 | **결정적**. 사용자 요구의 핵심 |
| G2 | 메서드는 1급 selection 이 아님. 검색에서 메서드 hit → 클래스로 떨어져서 어떤 메서드 골랐는지 잊힘 | 메서드 단위 작업 시 navigation cost |
| G3 | Action 의 realization 메서드 FqnLink 클릭 → 클래스로 가면서 action context 손실 (`selectOnly`) | "action 보면서 메서드 코드 비교" 흐름 깨짐 |
| G4 | RightPanel TabCode 폭(380px) 으로는 Java code 가독성 떨어짐 (50자 이상 라인 자주 wrap) | 우측 본체로는 코드 리뷰 부적합 |
| G5 | CodeTypeDetail methods 섹션에서 어떤 메서드도 클릭 안 됨 (정적 div) | 의미 있는 진입점 없음 |
| G6 | SplitMode 는 action 전용 — 클래스/메서드만 보고 싶을 때 진입 불가 | 코드만 빠르게 확인 워크플로우 부재 |

가장 큰 갭: **G1 (codeType / method 클릭으로 body 도달 불가)** — 사용자 요구가 정확히 이거.

---

## 3. 디자인 옵션 (3안)

### Option A — CodeTypeDetail 인라인 확장 + 메서드 expandable

각 메서드 행을 expandable 로 만들어 클릭 시 body 인라인 토글. CodeMethod 단일 selection 도 추가해서 search hit / FqnLink 가 메서드 단위로 떨어질 수 있게.

**Mock**:
```
 📦 ProcessSlabService                        [class][role:domain]
 com.foo.process.ProcessSlabService · L12-340

 ▸ Fields · 8
 ▾ Methods · 23

   [business] ▶ processBatch(List<Slab>) → Result        L42  @Override
   [business] ▼ validateSlab(Slab) → ValidationResult    L78
       ┌───────────────────────────────────────────────┐
       │ 78 │  if (slab.thickness < MIN_THICKNESS) {  │
       │ 79 │    throw new ValidationException(...);  │
       │ 80 │  }                                       │
       │ ...                                           │
       │ [↕ Split mode 로]  [📋 복사]  [📍 anchor 보기]│
       └───────────────────────────────────────────────┘
   [helper]   ▶ computeMargin(double) → double           L120
```

- **선택 모델**: `selectedCodeTypeFqn` 유지. 추가로 expanded methods 는 CodeTypeDetail 로컬 state (`Set<methodFqn>`). 검색 hit `code_method` 시 `selectedCodeTypeFqn` + scroll-to-method + auto-expand.
- **Pros**: 기존 detail 페이지 자연스러운 확장. 코드 + 시그니처 + role + Override 한 화면. 한 클래스 안 여러 메서드 비교 쉬움.
- **Cons**: 30 메서드 모두 펼치면 길이 폭주 → 디폴트 collapsed + 한 번에 N개 만 expand 정책 필요. 메서드 단위 selection 을 store 에 안 올리면 우측 4탭이 클래스 컨텍스트로 묶임.
- **스케일**: 100 메서드 클래스 = `slice(0, 50)` 풀어서 가상 스크롤 도입 필요. 펼친 메서드 N개만 body 토큰화 (lazy) → 부담 적음.
- **공수**: 6~10시간. CodeTypeDetail 메서드 섹션 재작성 + body fetch + JavaCode 활용. SplitMode 로 점프 버튼만 추가.
- **터칠 파일**: `MainPanel.tsx` (CodeTypeDetail), 옵션으로 `store.ts` (`selectedCodeMethodFqn` 추가).

### Option B — 코드 모달 (CodePeekModal) 즉시 띄우기

ModuleTree 에서 클래스 클릭 시 메인 detail 은 그대로 두되, 우측 상단 또는 메서드 행 우측에 "📄 코드" 버튼/링크 → **풀스크린 모달** 로 클래스 source 전체 또는 메서드 body 표시. action context 손실 없이 **peek**.

**Mock**:
```
 ┌────────────────────────────────────────────────────────────┐
 │ 📄 ProcessSlabService.validateSlab(Slab)              [Esc]│
 │ com.foo.process · L78-95 · role: business     ✓ business   │
 │ ┌──────────────────────────────────────────────────────┐  │
 │ │  78│ public ValidationResult validateSlab(Slab s) {  │  │
 │ │  79│   if (s.thickness < MIN_THICKNESS) {            │  │
 │ │  80│     throw new ValidationException("too thin");  │  │
 │ │  ...│                                                 │  │
 │ │  95│ }                                                │  │
 │ └──────────────────────────────────────────────────────┘  │
 │  📍 매핑된 Action: [validateSlabThickness] →             │
 │  ⚓ Anchor: param[0].thickness (L79) [✓]                 │
 │  [↕ Split 으로 열기]   [↑ 클래스 전체 보기]   [복사]     │
 └────────────────────────────────────────────────────────────┘
```

- **선택 모델**: 별도 store state `peekTarget: { kind: "method"|"type", fqn } | null`. 모달 종류는 read-only — selection 자체는 안 바뀜 → **action context 보존**.
- **Pros**: 어떤 selection 컨텍스트도 손실 없음. peek-and-close 흐름이 IntelliJ "Quick Definition (Cmd+Y)" 와 일치. 모달 안에서 anchor / Action 매핑 cross-link 노출 자유.
- **Cons**: 모달 = 컨텍스트 격리 → "여러 메서드 비교" 같은 작업에는 불리. 모달 안에서 다른 메서드로 점프하면 모달 stack 또는 단일 모달 navigation 패턴 정해야.
- **스케일**: 모달은 한 번에 1 메서드 또는 1 클래스만 → 100 메서드 클래스도 부담 없음. 클래스 전체 모드 시 가상 스크롤 도입 필요.
- **공수**: 8~12시간. 새 컴포넌트 `CodePeekModal.tsx` + ModuleTree / FqnLink / CodeTypeDetail 에 trigger 부착. ESC / 백드롭 / 키보드 navigation.
- **터칠 파일**: 신규 `CodePeekModal.tsx`, `store.ts` (peekTarget), `ModuleTree.tsx`, `MainPanel.tsx` (CodeTypeDetail 메서드 행 + FqnLink), `RightPanel.tsx` (TabCode 의 "확장" 버튼).

### Option C — 메서드를 1급 selection 으로 + Split mode 일반화

`selectedCodeMethodFqn` 추가. ModuleTree 의 클래스 leaf 를 expandable 로 만들어 메서드 leaf 노출. SplitMode 의 입력을 action 전용에서 "action 또는 method" 로 일반화 → 메서드 클릭 → 자동으로 split (좌: 코드, 우: 매핑 카드) 또는 main detail 에 코드 패널 추가.

**Mock**:
```
 ModuleTree                       Main (split mode)
 ─────────────                    ─────────────────────────────
 ▾ com.foo.process                📦 ProcessSlabService
   ▾ ProcessSlabService [25m]     validateSlab(Slab) → Result  L78
     · processBatch  L42          ┌────────────────────────────┐
     · validateSlab  L78  [→]     │ 78│ if (s.thickness < ...) │
     · computeMargin L120         │ 79│   throw ...            │
     · saveResult    L240         │ ...│                        │
   ▸ AnotherService  [12m]        └────────────────────────────┘
                                  Mappings ↔
                                  📍 Action: validateSlabThickness
                                  ⚓ Anchor L79: param.thickness
                                  ⚖ BR enforced: BR-101
```

- **선택 모델**: `selectedCodeMethodFqn` 신규. selectOnly 에 "method" kind 추가. `selectedCodeTypeFqn` 와 method 는 양립 가능 (parent 자동 derive). Action 보다가 realization 메서드 클릭 시 → action 도 유지 (FqnLink + selection 유지 두 가지 모두 허용).
- **Pros**: IntelliJ-like. 트리에서 한 번에 모든 코드 entity 도달. SplitMode 가 코드 중심 워크플로우 (action 이 없는 클래스도 split 가능) 로 확장. `RightPanel TabCode` 도 method selection 분기 추가하면 일관됨.
- **Cons**: 가장 큰 변경. 트리 expand 가 100메서드 클래스에 부담 (가상 스크롤 / lazy load 필요). 메서드 selection 시 RightPanel 4탭 (callsite/impact/manual/이력) 의미 재정의 필요. selection 모델 변경은 graph mode / search hit 라우팅 / breadcrumb 모두 영향.
- **스케일**: ModuleTree 클래스 노드 expand 시 method list 는 이미 인벤토리 API 에 `method_count` 만 있고 전체 list 는 별도 fetch 필요 (`getCodeType(fqn).methods`) — 100 메서드면 가상 스크롤 + virtualization 필요. 메서드 fetch 는 클래스 expand 시 1 회.
- **공수**: 16~24시간. store / ModuleTree / MainPanel 라우팅 / SplitMode 일반화 / RightPanel 분기 + 회귀 영향 큼. 디자인 결정 다수 필요.
- **터칠 파일**: `store.ts`, `ModuleTree.tsx`, `MainPanel.tsx` (SplitMode + CodeTypeDetail + ForwardDetail), `RightPanel.tsx` (TabCode/TabCallSite/TabImpact/TabHistory 메서드 분기), `CmdKPalette.tsx`, `WorkbenchShell.tsx` (split 진입 조건).

---

## 4. 권고

**Option B (CodePeekModal) 를 1차로 채택. 이후 Option A 의 메서드 expandable 을 점진 추가.**

이유:
1. **사용자 요구의 핵심을 가장 빠르게 충족** — "코드 내용을 잘 볼 수 있게" + "모달 또는 메인 detail" 양쪽 다 답이지만, peek-and-close 모달이 **action 컨텍스트 보존** + IntelliJ 비유에 가장 부합 (Cmd+Y / Quick Definition).
2. **selection 모델 변경 없음** — 회귀 risk 낮음. graph / search / breadcrumb 영향 없음.
3. **단일 진입점, 다양한 trigger** — ModuleTree 클래스 클릭, CodeTypeDetail 메서드 행, RightPanel TabCode 의 "확장" 버튼, FqnLink kind=code_method 모두 같은 모달로 모임 → 학습곡선 1회.
4. **점진 발전 여지** — Option A 의 메서드 expandable 은 같은 모달 컴포넌트를 inline 으로 재사용 가능. Option C 의 method selection 은 미래 phase 에 필요할 때 도입 (Phase E 의 anchor 작업에서 메서드 단위 작업이 늘 때).
5. **JavaCode 그대로 활용** — 의존성 추가 없음. 모달 안에서 풀폭 + line marker + anchor 호버 등 기존 UX 재사용.

핵심 디자인 포인트:
- 트리거는 **명시적 버튼** (📄 아이콘) 으로 만들어 single click 이 selection 변경, 명시적 click 이 peek 라는 분리. ModuleTree 클래스 leaf 의 우측 hover-action 으로 추가.
- 모달 안에서 anchor / action 매핑 정보를 **같이 노출** (이게 onTong 의 차별점). source 만 보여주는 IDE 와 다름.
- 모달 footer 에 "↕ Split 모드로 열기" CTA → 풀 워크벤치로 escalate.
- ESC 닫기, 백드롭 클릭 닫기, keyboard navigation. ParamDrawer 패턴 재사용.

---

## 5. 구현 파일 + 공수

### Phase 1 (권고) — CodePeekModal
| 파일 | 작업 | LoC 변화 |
|---|---|---|
| 신규 `frontend/src/components/sections/modeling/CodePeekModal.tsx` | 모달 컴포넌트, ParamDrawer 패턴 베이스 | +200~250 |
| `store.ts` | `peekTarget: { kind: "method"\|"type", fqn } \| null` + setter | +10 |
| `ModuleTree.tsx` | 클래스 leaf 우측 hover 시 📄 버튼 → peek trigger | +20 |
| `MainPanel.tsx` (`CodeTypeDetail` 메서드 행) | 행 클릭 또는 우측 📄 버튼 → peek (메서드 단위) | +30 |
| `MainPanel.tsx` (`FqnLink` kind=code_method) | 옵션: shift-click 시 peek (단순 click 은 기존 navigate) | +10 |
| `RightPanel.tsx` (`TabCode` codeType 분기) | "📄 코드 풀폭으로 보기" 버튼 → peek | +10 |
| `WorkbenchShell.tsx` 또는 layout 어딘가 | `<CodePeekModal />` 마운트 | +5 |

**총 공수**: 8~12시간 (1.5 일).

추가 고려:
- 모달 안 코드가 1000줄 넘으면 가상 스크롤 (react-window 등) 도입 또는 `<JavaCode>` 자체에 lazy line 렌더 옵션 추가. 현재 5K 클래스 평균은 수십~수백 줄이므로 1차에는 그대로 ok.
- `getCodeType()` 호출 시 method 만 필요하면 backend에 `?fields=methods.body_text` 같은 projection 옵션 검토 (현재는 풀 DTO).

### Phase 2 (보강) — Option A 인라인 확장
모달이 익숙해진 뒤 CodeTypeDetail 의 메서드 행을 expandable 로 만들어 한 페이지 안에서 여러 메서드 비교 가능하게. 같은 `<JavaCode>` 재사용.

**총 공수**: 추가 4~6시간.

---

## 6. 사용자에게 묻고 싶은 열린 질문

1. **모달 vs 메서드 행 인라인 expand — 어느 쪽이 더 자연스러우신가?**
   현재 권고는 모달이지만, 사용자 분께서 "한 클래스 안에서 여러 메서드를 좌우로 비교" 가 잦으면 인라인 expand (Option A) 또는 둘 다가 답일 수 있음.

2. **메서드를 1급 selection 으로 만들지?** (Option C)
   결정 시 RightPanel 4탭 (callsite/impact/manual/이력) 가 메서드 단위로 의미를 가짐 → 더 강력하지만 회귀 영향 큼. Phase E 의 anchor 보강 작업에서 메서드 단위 워크플로우가 늘어날 가능성을 미리 잡아야 하나?

3. **모달 안에서 다른 메서드로 점프할 때 — 모달 stack(이전으로) vs 단일 모달 replace?**
   IntelliJ 는 stack (브라우저처럼 ◀ 가능). onTong 의 모달은 anchor/action cross-link 가 많아서 stack 이 자연스러우나 구현 복잡도 ↑. 1차에는 단일 모달 replace + ESC 로 닫기 권장.
