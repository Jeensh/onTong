# HelpHint Audit — 추가 권장 위치

> 본 문서의 권장 사항은 **병렬 에이전트가 담당한 surface** 들에 대한
> HelpHint 추가 제안이다. 본 에이전트가 직접 손대지 않은 파일들 —
> `MainPanel.tsx`, `ModuleTree.tsx`, `OntologyTab.tsx`, `LeftPanel.tsx`,
> `CmdKPalette.tsx` — 의 제안만 모아두었다.
>
> **적용 방법**: 각 위치의 label span 옆에 다음 패턴으로 삽입.
>
> ```tsx
> <span className="...">label-text</span>
> <span className="shrink-0 inline-flex"><HelpHint term="<key>" inline /></span>
> ```
>
> button / row 가 이미 `<button>` 인 경우 nested-button 방지를 위해
> 바깥 wrapper 를 `<span>` 또는 `<div role="button">` 로 감싸야 할 수 있다.
> HelpHint 자체는 span(role=button) 이라 안전.
>
> 우선순위 표기:
> - **P0** = essential — 도메인 신규 사용자가 이해 못함, 반드시 추가.
> - **P1** = nice — 알면 좋음, 한 번이라도 본 적 있는 사용자엔 불필요.
> - **P2** = optional — 이미 다른 곳에 같은 용어 HelpHint 가 있어 redundant 일 수 있음.

---

## 1) MainPanel.tsx

5 Detail 컴포넌트가 모인 중심 surface. 이미 13+ HelpHint 가 있지만 추가 권장 후보.

### ActionDetail (lines ~154-440)

| Location (대략 라인) | Term key | Why useful | 우선순위 |
|---|---|---|---|
| h1 옆 verification stepper 위 (`signature_locked_at` ts 표시되는 영역) | `verification_level` | stepper 자체에 step 별 hint 가 있지만 전체 개념 1 회는 필요 | P1 |
| Section "Effects" title 옆 (`Effects · {n}`) | `effectful` | effect 자체가 effectful action 의 핵심. effects[].op 4 종 이해 위해 필요 | P0 |
| Effects row 안의 `op` chip (create/mutate/read/delete) — 각 op 별 | (op 설명 4 종 — `effectful` 또는 신규 entry 권장) | mutate vs read 구분이 사용자에게 모호 | P1 |
| Section "Preconditions" title | `business_rule` | precondition 은 BR 의 fqn 참조. BR 자체가 무엇인지 hint 필요 | P0 |
| Section "Postconditions" title | `business_rule` | 동일 | P0 |
| Section "Output" title | `action` | output type 의 의미 (return type vs object_ref_term) | P1 |
| Section "Aliases" title | (없음 — 일반 용어, skip) | — | — |
| Realizations row의 `applies to` 부분 | `realization_for_input` | 다형성 dispatch 의 입력 타입 차원 설명 | P1 |
| Realizations row 의 `(base)` 표기 | `realization` | base 의 의미가 모호 | P2 |
| AnchorBindings 의 `매핑` 버튼 옆 | `binding` | 신규 추가된 binding entry 활용처 | P0 |
| ParamRow 의 `params[i]` label | `action` | params indexing 규칙 (0-based) | P2 |

### TermDetail (lines ~965-1129)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| h1 의 domain inline-edit | (없음 — domain 은 일반어) | — | — |
| Section "값 형식 (atomic)" title | `atomic` | 이미 h1 에 atomic chip 있음 — duplicate. skip 가능 | P2 |
| KV row `value_type` | (없음 — Java type 이라 일반) | — | — |
| KV row `unit` | (없음 — 일반어) | — | — |
| KV row `range` | `atomic` | range 의 [min, max] 의미 | P2 |
| KV row `enum_values` | `atomic` | enum 표현법 | P2 |
| Section "Composition Parts" title | `composition` | parts 의 cardinality / required 이해 | **P0** |
| Composition row 의 `cardinality` (1:1/0:1/1:N/0:N) | `composition` | 표기법이 사용자에게 모호 | P1 |
| Section "Flags" title | `is_root_entity` 또는 `struct_like_hint` | 신규 추가 entry 활용 | P1 |
| FlagsRow 안의 `struct_like_hint` chip | `struct_like_hint` | 신규 entry, 직접 매칭 | P0 |
| FlagsRow 안의 `interface` chip | (없음 — Java 일반) | — | — |
| (header) `is_abstract` chip | (없음 — Java 일반) | — | — |

### CodeTypeDetail (lines ~1134-1328)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| h1 의 `role:` inline-select | `role` | role 4 종 의미 | **P0** |
| Section "Inheritance" title | `inheritance` | extends/implements 표 의미 | P1 |
| Section "Annotations" title | (없음 — Java 일반) | — | — |
| Section "Fields" title | (없음 — Java 일반) | — | — |
| Section "Methods" title 옆 | `code_method` | role chip 의미 (business/helper/adapter) | P0 |
| Method row 의 `role` chip (business/helper/adapter) | `role` | 위와 동일 | P0 |
| Section "원본 파일" title | (없음 — 일반) | — | — |

### BusinessRuleDetail (lines ~1333-1504)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| Section "Statement" title | `business_rule` | statement 의 의미 (자연어 invariant) | P1 |
| (이미 있음) "Enforced By" → `enforced_by` | — | — | OK |
| (이미 있음) "Terms Referenced" → `term` | — | — | OK |
| (이미 있음) "Operational History" → `operational_history` | — | — | OK |
| (이미 있음) "Violated-At Call Sites" → `violated_at_call` | — | — | OK |
| `severity` inline-select 옆 | `severity` | 이미 severity chip 시 chip 색이 의미 갖지만 hint 추가 안전 | P1 |
| Section "Source / Origin" title | (없음 — 일반) | — | — |

### AnchorDetail (lines ~1509-1629)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| h1 의 `src:` chip (anchor.source) | `dispatch_source` | source 가 어떤 enum 인지 모호 — 단, anchor 의 source 는 dispatch_source 와 다름. 신규 entry 권장 (`anchor_source`) 또는 skip | P1 |
| h1 의 `conf` chip | (이미 있음 — `confidence`) | OK | OK |
| (이미 있음) "Anchor Locator" → `anchor_locator` | — | — | OK |
| (이미 있음) "Code Method" → `code_method` | — | — | OK |
| (이미 있음) "Target Action / Slot" → `target_slot` | — | — | OK |
| Section "Rationale" title | `confidence` | rationale 이 confidence 의 근거 텍스트 | P2 |
| (헤더) `id` 표시 옆 | (없음 — 일반) | — | — |

### VerificationStepper (lines ~544-591)

이미 isCurrent 단계만 HelpHint 표시. 권장:

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| 모든 단계 dot 의 `title` (현재 `step.level` 텍스트만) → tooltip 대체 또는 추가 HelpHint | `verification_level` | hover 시 어느 단계인지 즉시 인지 — title 은 미니멀 | P2 |

### Split Mode 관련 (lines ~593-825)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| 우측 "Semantic Anchors" 섹션 헤더 | `anchor` | semantic vs static 구분의 핵심 | **P0** |
| 우측 "Static Parser Anchors" 섹션 헤더 | `anchor` (또는 신규 `static_anchor` entry) | static = parser 추출, semantic = 사용자 매핑 — 차이 설명 | **P0** |
| 우측 "BR enforced by 이 method" 섹션 헤더 | `enforced_by` | 이미 있음 — duplicate 안전 | P1 |
| 우측 "Action params" 섹션 헤더 | `action` | params 와 anchor target_slot 의 관계 | P1 |

### FqnLink (lines ~1679-1799)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| Eye icon (peek) | `peek` | peek vs navigate 차이 — Eye icon hover 시 title 외에 hint | P1 |
| ↗ icon (parent class 로 이동) | (없음 — 일반 navigation) | — | — |

---

## 2) ModuleTree.tsx

좌측 코드 트리 + 검색. 사용자가 가장 많이 보는 화면.

### Search 영역 (lines ~62-145)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| `KindBadge` 5 종 (`class` / `mtd` / `term` / `act` / `rule`) | 각 종 별 (`code_type` / `code_method` / `term` / `action` / `business_rule`) | 검색 결과 줄에서 5 종 분류가 사용자에게 모호 | **P0** |
| 검색창 placeholder 옆 | (없음 — 검색은 일반) | — | — |

### RoleDotLegend (lines ~646-664)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| Legend 의 각 role label (domain/framework/infra/unknown) | `role` | 4 종 분류 의미 — legend 1 곳에만 hint 면 충분 | **P0** |
| Legend 전체 우측 끝 | `role` | 또는 위 대신 한 곳에만 묶음 | P1 |

### Module Tree 노드 (lines ~290-380)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| 노드 우측 "C{count}" / "T{count}" / "A{count}" 카운트 | `code_type` / `term` / `action` | C/T/A 약자 의미가 사용자에게 모호 | **P0** |
| RoleDot (domain/framework/infra/unknown) | `role` | hover 시 title 은 있지만 HelpHint 가 명시적 | P1 |
| `confirmed_ratio` 표시 (있다면) | `confirmed` | confirm/draft 비율 | P1 |
| Action leaf 의 `verification_level` 약자 (예: SL, BA, SV, PP) | `verification_level` | 약자 의미 | **P0** |
| Action leaf 의 ✓ chip ("confirmed (signature_locked 이상)") | `verification_level` | 이미 title 에 있지만 명시적 hint | P1 |

### Inventory Panel (lines ~580-595)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| inventory row 의 `Xm` (method count) | `code_method` | 단순 카운트지만 m 약자 | P2 |
| inventory row 의 `role` dot | `role` | 위와 동일 | P1 |

---

## 3) OntologyTab.tsx

`OntologyTab` 은 이미 5 개 HelpHint 보유. 추가 권장:

### Section Headers (lines ~206-301)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| Section "Term" header | `term` | 이미 헤더 카운트에 atomic / composite hint 있음 — 중복 가능 | P2 |
| Section "Action" header | `action` | 동일 | P2 |
| Section "BusinessRule" header | `business_rule` | 동일 | P2 |
| Section "AnchorBinding" header | `anchor` | 동일 | P2 |
| `confirmed N / draft M` 텍스트 | `confirmed` 또는 `draft` | 두 상태의 차이 | P0 |
| `hard N` 텍스트 (rule 섹션 sub) | `severity` | hard vs soft 의미 | **P0** |

### TermRow / ActionRow / BRRow / AnchorRow

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| TermRow 의 atomic/composite dot 색 | (이미 헤더에 있음 — skip) | — | P2 |
| ActionRow 의 ✓/· 표시 (confirmed indicator) | `confirmed` 또는 `draft` | dot 단독으론 의미 모호 | P0 |
| ActionRow 의 `kind.slice(0,4)` 약자 (pure / effe / work) | `pure_function` 등 | 약자 의미 | **P0** |
| BRRow 의 severity dot (hard rose / soft amber) | `severity` | 색 의미 | P1 |
| AnchorRow 의 confidence number | `confidence` | 0.0-1.0 의미 | P1 |
| AnchorRow 의 ✓ checkmark | `confirmed` | confirm 상태 의미 | P1 |

---

## 4) LeftPanel.tsx

탭 헤더 + Queue 탭이 핵심.

### 탭 헤더 (lines ~38-55)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| "큐" 탭 label | `matching` 또는 `draft` | 큐가 무엇인지 — 자동 매칭 후보 합의 대기 | **P0** |
| "온톨로지" 탭 label | `mapping` | ontology 탭이 무엇을 보여주는지 | P1 |
| "코드" 탭 label | `code_type` | 코드 트리 = CodeType 계층 | P2 |

### QueueTab (lines ~310-486)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| 섹션 탭 "Term" / "Action" / "Real" / "Code" | `term` / `action` / `realization` / `code_type` | 4 섹션 의미 | **P0** |
| "Real" 탭 (= type_realization) | `type_realization` | "Real" 약자가 가장 모호 | **P0** |
| QueueRow 의 ✓ button (confirm) | `confirmed` | confirm 동작이 하는 일 | P1 |
| QueueRow 의 ✕ button (reject) | (신규 entry `reject` 권장 또는 skip) | reject = 후보 row 삭제 | P1 |
| QueueRow 의 confidence 표기 (있다면) | `confidence` | 0-1 점수 의미 | P1 |
| QueueRow subtitle 의 `struct_like_hint` 표기 | `struct_like_hint` | 신규 entry 활용 | P1 |
| Legacy 큐의 "🟡 CALLSITE 모호 dispatch" | `ambiguous_call_site` | 직접 매칭 | **P0** |
| Legacy 큐의 "🟠 UNMAPPED" | `code_method` 또는 신규 `unmapped` entry | UNMAPPED 의미 | P1 |
| 새로고침 ↻ 버튼 옆 | (없음 — 일반) | — | — |
| 섹션 탭 우측 카운트 색 (text-violet-400 등) | (없음 — 시각만) | — | — |

---

## 5) CmdKPalette.tsx

### CommandList (lines ~48-87)

| Location | Term key | Why useful | 우선순위 |
|---|---|---|---|
| `h.kind` 약자 (term/action/code_type 등) | (각 종 별) | 검색 결과 분류 — ModuleTree 의 KindBadge 와 동일 | P0 |
| "시뮬레이션 시작" 명령 옆 `SIGNATURE_LOCKED+` 표기 | `signature_locked` | 이 단계 이상에서만 가능한 이유 | **P0** |
| "그래프 모드" 명령 | (없음 — 일반) | — | — |

---

## 추가: 신규 entry 후보 (glossary.ts 에 없는 것)

본 작업에서 추가하지 않았으나, 위 권장 사항을 모두 구현하려면 다음 entry 추가가 좋다:

- `effect_op` — create/mutate/read/delete 4 종 op 의 의미
- `static_anchor` vs `semantic_anchor` — Split mode 의 두 종 anchor 차이
- `anchor_source` — AnchorBinding.source enum (parser_extracted / user_manual / llm_inferred 등)
- `unmapped` — 큐의 UNMAPPED 분류 의미
- `reject` — 큐 row reject 의 효과 (= row 삭제, vs unconfirm = 보존)
- `kind_badge` (또는 5 종 약자별 entry) — class/mtd/term/act/rule 약자 매핑

---

## 통계

- **P0 (essential)**: 24 개
- **P1 (nice)**: 18 개
- **P2 (optional)**: 11 개
- **합계**: ~53 권장 사항

## 적용 순서 권장

1. **Phase A** — P0 만 적용 (24 곳). 사용자 학습 곡선이 가장 낮아짐.
2. **Phase B** — 위 "신규 entry 후보" 5 종을 glossary.ts 에 추가. 그 후 관련 P1 적용.
3. **Phase C** — P1 / P2 중 사용자 피드백 받아 선별 적용.
