# Detail Panels — Information Density Audit

**Status:** Review-only. No code changes proposed yet.
**Scope:** 5 Forward Detail components in `MainPanel.tsx` (TermDetail / ActionDetail / CodeTypeDetail / BusinessRuleDetail / AnchorDetail).
**Date:** 2026-05-10

---

## Section 1 — Audit Method

Each Detail component was walked top-to-bottom, treating every distinct rendered element (h1 segment, badge, mono-line, KV row, section header, body row) as one auditable unit. Each unit was classified into 🟢 ESSENTIAL / 🟡 USEFUL / 🟠 NOISE / 🔴 DELETE based on (a) whether a non-expert teammate can act on it, (b) whether the same information is shown elsewhere on the panel, (c) whether the field carries decision weight or is bookkeeping. The 28-term `glossary.ts` was cross-checked before flagging "needs explanation" — anything already covered by a `HelpHint` was left alone. Edit affordance (`InlineEditX` vs `read_only`) was treated as already documented in `editable_fields_guide.html` and **not** re-discussed; this audit focuses purely on **presentation density**.

---

## Section 2 — Per-Entity Tables

### 2.1 TermDetail (lines 899–1058)

**Element count: 22 elements → ESSENTIAL 9 / USEFUL 5 / NOISE 6 / DELETE 2**

| # | Element | Currently shown as | Category | Proposal |
|---|---------|-------------------|----------|----------|
| 1 | Banner "🧬 BusinessTerm — 도메인 의미 단위" | violet left-border banner above h1 | 🟠 NOISE | Color/icon already present in h1 badge + sidebar selection. Banner repeats it on every entity load → screen real estate burned for no info. **Hide by default** (or shrink to 4-px violet stripe on left edge of card). |
| 2 | `term.label` (h1, editable) | large h1 + InlineEditText | 🟢 ESSENTIAL | Keep. Add muted-text caption "이 용어의 사람이 부르는 이름" on hover/help-icon. |
| 3 | `term.kind` badge (atomic / composite) | violet pill in h1 + HelpHint | 🟢 ESSENTIAL | Keep. HelpHint already covers atomic/composite. |
| 4 | `term.is_root_entity` badge | green pill in h1 (only when true) | 🟡 USEFUL | Keep. **Already conditional** (only renders when true) — no change. |
| 5 | ConfirmToggle | top-right of h1 | 🟢 ESSENTIAL | Keep. |
| 6 | `term.fqn` mono line | full FQN below h1 | 🟠 NOISE | FQN is also the breadcrumb (header bar shows "현재 Term: customer_std"). Last segment is enough — show short form, full FQN on hover/click-to-copy. |
| 7 | "·" separator + "domain" label + InlineEditText | inline next to FQN | 🟡 USEFUL | Keep but reflow — currently the line reads `term.scm.std.customer_std · domain ___` which is dense. Move `domain` to its own KV row OR right-align. |
| 8 | "설명" Section + InlineEditTextArea | full Section card | 🟢 ESSENTIAL | Keep. |
| 9 | "값 형식 (atomic)" Section header | only renders when atomic | 🟢 ESSENTIAL | Keep. (Section already conditional on `kind === "atomic"`.) |
| 10 | KV `value_type` (ValueTypeEdit) | inline_select w/ fallback | 🟢 ESSENTIAL | Keep. |
| 11 | KV `unit` | inline_text | 🟢 ESSENTIAL | Keep. |
| 12 | KV `range` (InlineEditRange min→max) | inline_range | 🟢 ESSENTIAL | Keep. |
| 13 | KV `enum_values` | inline_list | 🟡 USEFUL | Keep. Often empty for non-enum atomic — when empty + `value_type ≠ enum`, hide the row entirely (instead of showing "(없음)"). |
| 14 | "Aliases · N" Section | always rendered | 🟢 ESSENTIAL | Keep. **But:** when `N=0` and not editing, collapse the section to a single "Aliases · 0 (클릭해서 추가)" row instead of showing the placeholder card. |
| 15 | Composition Parts Section | only renders when composite | 🟢 ESSENTIAL | Keep. |
| 16 | Each Part row: `role_name` + simple_name + **full FQN repeated** + cardinality | grid-cols-[110px_1fr_60px] | 🟠 NOISE | Each row shows `child_fqn.split(".").pop()` AND the full `child_fqn` next to it as muted mono. Pick one. **Show simple_name only**; full FQN on hover/title attr. |
| 17 | Cardinality + " req" | small text, right column | 🟡 USEFUL | Keep. Add muted caption "0:N = 여러 개, 선택" once per term as helper text (or leverage glossary entry — there's none for cardinality). |
| 18 | "Flags" Section | always shown | 🟠 NOISE | All three flags (`is_abstract` / `is_interface` / `struct_like_hint`) shown unconditionally with ✓ or — . **Show only flags that are TRUE**. If all three are false, hide the entire Flags section. |
| 19 | KV `is_abstract` | "✓" or "—" | 🟠 NOISE | See #18. |
| 20 | KV `is_interface` | "✓" or "—" | 🟠 NOISE | See #18. |
| 21 | KV `struct_like_hint` | "✓" or "—" | 🔴 DELETE | Pure parser hint — not actionable by user, not part of any documented workflow. Either hide entirely OR move to a "Diagnostics" disclosure (collapsed by default). The glossary doesn't even document it. |
| 22 | AuthoringBridge violet card | bottom of panel | 🟡 USEFUL | Keep but **shorten** the note to 1 line ("대량 변경은 Authoring 모드"); current 2-line note feels promotional. |

**Needs muted-text caption:**
- Element #4 `is_root_entity` — currently has HelpHint; OK.
- Element #7 `domain` — needs caption "도메인 분류 (`scm.shared` 등)" when input is empty (currently just shows "(미지정)").
- Element #17 `cardinality` — there's no glossary entry for "0:N / 1:1 / required". Add to glossary OR add a one-time helper line above the parts list: *"좌측은 part 의 역할명, 우측은 카디널리티 (0:N=여러 개)."*

---

### 2.2 ActionDetail (lines 151–443)

**Element count: 28 elements → ESSENTIAL 11 / USEFUL 7 / NOISE 8 / DELETE 2**

| # | Element | Currently shown as | Category | Proposal |
|---|---------|-------------------|----------|----------|
| 1 | Banner "🔍 Forward 매핑 — 코드를 도메인 의미로 매핑" | primary blue banner above h1 | 🟠 NOISE | Same complaint as TermDetail #1 — the Forward/Backward state is already shown in the top mode toggle. Drop or shrink. |
| 2 | `action.label` (h1, editable) | InlineEditText | 🟢 ESSENTIAL | Keep. |
| 3 | "action" badge (orange) + HelpHint | always present | 🟠 NOISE | This badge says "this is an action" — but the user already navigated to the Action panel and the violet/orange color of the panel signals it. **Drop the badge**; keep HelpHint moved to h1 caption ("?" icon). |
| 4 | `action.kind` badge (pure_function / effectful / workflow) + HelpHint | always present | 🟢 ESSENTIAL | Keep — kind is decision-relevant (sim safety differs). |
| 5 | `action.is_abstract` badge | only when true | 🟡 USEFUL | Keep (conditional). |
| 6 | ConfirmToggle | right side of h1 | 🟢 ESSENTIAL | Keep. |
| 7 | `action.fqn` mono line | full FQN under h1 | 🟠 NOISE | Same as TermDetail #6 — FQN repeated from breadcrumb. Show short form + on-hover full path. |
| 8 | "· declared on Term" link | inline with FQN | 🟢 ESSENTIAL | Keep — this is **the** key cross-reference for an action. |
| 9 | `verification_level` badge | inline w/ fqn line, small amber pill | 🔴 NOISE→ELEVATE | This is **the most decision-relevant attribute** of an Action (UNMAPPED → DRAFT → SIGNATURE_LOCKED → ...) but it's rendered as a tiny pill in a metadata strip. **Promote**: move to its own row with a compact stepper visualization (○○●○○○) or at least make the badge larger and the most prominent thing after the label. |
| 10 | `action.domain` derived line | italic muted "domain (derived): X" | 🟠 NOISE | Same domain string is implied by `declared_on_term`'s fqn (which is already shown in #8). When `declared_on_term` is set, this row is fully redundant. **Hide** when `declared_on_term` is set; only show when it's standalone. |
| 11 | "설명" Section + InlineEditTextArea | full Section card | 🟢 ESSENTIAL | Keep. |
| 12 | "Aliases · N" Section | always | 🟢 ESSENTIAL | Keep (same shrink-when-empty proposal as TermDetail #14). |
| 13 | "Parameters · N" Section | always | 🟢 ESSENTIAL | Keep. |
| 14 | Each ParamRow: `params[i]` key + name + `→ refTerm` violet badge + ✓/... | grid 110/1fr/60 | 🟢 ESSENTIAL | Keep. Caption above section: *"클릭 → param 상세 (drawer)"* — already exists as title attribute, but invisible. Surface it as muted-text below section header. |
| 15 | Output Section (when present) | full ParamRow | 🟢 ESSENTIAL | Keep. |
| 16 | "Realizations · N (다형성)" Section | always | 🟢 ESSENTIAL | Keep. |
| 17 | Each Realization row | dense: code badge + method FQN + @Override + ✓ scope + applies-to + dispatch_source + conf | 🟠 NOISE-DENSE | The second line *"applies to ... · dispatch_source ... · conf 0.95"* has 3 facts crammed with separators + 2 HelpHints. Split into 2 lines: line 1 = code link + scope badge; line 2 = "applies to X" only when not base. Move `dispatch_source` + `confidence` to a subtle right-aligned hover-disclosure (these matter only on inspection, not at-a-glance). |
| 18 | "Postconditions · N" Section | always | 🟡 USEFUL | Keep. **But:** when N=0, current behavior shows the section with "(없음)" italic — collapse to a single header-only row "Postconditions · 0" without the body card. |
| 19 | "Effects · N" Section | always | 🟡 USEFUL | Same as #18 — collapse-when-empty. |
| 20 | Each Effect row: op pill + target term link + .attr + description | colored op pill | 🟢 ESSENTIAL | Keep — the color-coded op (create/mutate/read/delete) is excellent density. |
| 21 | "Preconditions · N" Section | only when N>0 | 🟢 ESSENTIAL | Keep (already conditional). |
| 22 | Each Precondition row: `[i]` + "rule" pill + mono text | font-mono with pink rule pill | 🟡 USEFUL | The pink "rule" pill on every row is visual noise — same word once would suffice. Consider: drop the pill, use a section-level "🛡 each line is a rule predicate" caption. |
| 23 | "Anchor Bindings · N" Section + "↕ Split mode 로" button | always | 🟢 ESSENTIAL | Keep. |
| 24 | Each Anchor row: locator + target_slot + ✓ or "매핑" button | grid 110/1fr/60 | 🟢 ESSENTIAL | Keep. **But:** target_slot is shown as raw `params[0]<RushOrder>.spec.diameter.range[1]` syntax — needs glossary cross-link or a tooltip explaining the path syntax. (`target_slot` HelpHint exists in glossary.ts L94 — wire it on the Section title once, not per-row.) |
| 25 | Empty-anchor placeholder line | muted text | 🟡 USEFUL | Keep. |
| 26 | AuthoringBridge | bottom violet card | 🟡 USEFUL | Same as TermDetail #22 — shorten. |
| 27 | Sub-actions list (workflow only) | not rendered in current code | 🔴 GAP | `action.sub_actions` is a real DTO field but never displayed. For `kind=workflow` it's the most important relationship. **Add a Section**: "Sub-actions · N" with FqnLink to each. (Or keep this audit's "no new features" rule and just call it out.) |
| 28 | `signature_locked_at` / `confirmed_by` | not rendered | 🔴 DELETE/HIDE | Both are in the DTO but not shown — currently fine. If future code adds them, make sure they're in a "Audit" disclosure, not the main flow. |

**Needs muted-text caption:**
- Element #9 `verification_level` — when value is `unmapped` or `draft`, add a single muted line *"매핑 큐 또는 Confirm 으로 진급"* once next to the badge. Glossary covers each level individually but doesn't show the **progression**.
- Element #14 (params section) — caption *"각 행 클릭 → 상세 drawer"* (currently hidden in `title` attribute).
- Element #17 (realizations) — when more than one realization exists, add caption *"동일 Action 의 다형성 구현 N 개"* once.

---

### 2.3 CodeTypeDetail (lines 1063–1187)

**Element count: 17 elements → ESSENTIAL 7 / USEFUL 4 / NOISE 4 / DELETE 2**

| # | Element | Currently shown as | Category | Proposal |
|---|---------|-------------------|----------|----------|
| 1 | Banner "📦 CodeType — Java 클래스/인터페이스 (mirror)" | primary banner above h1 | 🟠 NOISE | Same as Term/Action banners — info already in tree icon + h1 badge. Drop. |
| 2 | `ct.simple_name` (h1, plain text) | large bold | 🟢 ESSENTIAL | Keep. |
| 3 | `ct.kind` badge | primary pill | 🟢 ESSENTIAL | Keep. **Add HelpHint** — `class` / `abstract_class` / `interface` / `enum` / `record` is mostly self-evident but `record` may not be for non-Java teammates. Glossary doesn't cover these. |
| 4 | `ct.role` inline_select w/ confirm modal | "role: [domain ▼]" pill | 🟢 ESSENTIAL | Keep — only editable field on CodeType. Glossary covers `role`. |
| 5 | `ct.is_abstract` badge | only when true | 🟡 USEFUL | Keep. |
| 6 | `ct.fqn` mono line | full FQN below h1 | 🟠 NOISE | Same redundancy. Show package separately + simple_name as h1. Or just show package as a small caption "in com.scm.api.std.dto" under h1. |
| 7 | `ct.source_file:line_start–line_end` | appended to FQN line | 🟡 USEFUL | Keep but separate to its own line — currently jammed onto the FQN line with " · ". Easier to scan as: <br>`📄 com/scm/api/std/dto/CustomerStd.java  L48–112` |
| 8 | "Inheritance" Section (extends + implements) | only when present | 🟢 ESSENTIAL | Keep. |
| 9 | KV `extends` + KV `implements` rows | one row per | 🟢 ESSENTIAL | Keep. |
| 10 | "Annotations · N" Section | only when N>0 | 🟢 ESSENTIAL | Keep — `@Service`, `@Transactional` etc. are decision-relevant. |
| 11 | Each annotation pill | `@SomeAnnotation` orange pill | 🟢 ESSENTIAL | Keep. |
| 12 | "Fields · N" Section (capped 30) | always rendered | 🟡 USEFUL | Keep. |
| 13 | Each Field row: `name` + `type` + `Lxx` | grid 160/1fr/60 | 🟡 USEFUL | Keep. **But:** field types like `List<Map<String, OrderItem>>` overflow the column. Truncate w/ tooltip. |
| 14 | "Methods · N" Section (capped 50) | always | 🟢 ESSENTIAL | Keep. |
| 15 | Each Method row: `role` pill + `name(types) → return` + `Lxx` + `@Override` | dense single line | 🟠 NOISE-DENSE | The role pill (business/helper/adapter) + `@Override` badge + line number all shown side-by-side — when method has business role + @Override + L-number it's 4 visual elements before the user reads the method name. **Move `@Override` to a small superscript next to method name, not as a separate badge**. The `Lxx` is only useful when navigating to source — cluster it with a "↗" jump icon. |
| 16 | "원본 파일" Section | always shown | 🔴 DELETE | Just repeats `ct.source_file` which is already on the FQN line (see #7). Delete the section entirely. |
| 17 | "* 이 CodeType 에 매핑된 ... reverse-lookup endpoint (Phase E #50+)" footnote | muted text at bottom | 🔴 DELETE | This is a developer self-note about a missing endpoint, not user guidance. Delete from production UI; move to backlog/TODO. |

**Needs muted-text caption:**
- Element #3 `ct.kind` — add HelpHint covering `record` at minimum (glossary gap).
- Element #4 `ct.role` — caption already in glossary, OK.
- Element #15 `m.role` (per-method) — `business / helper / adapter` are color-coded but unlabeled. Add a single legend caption above the methods list: *"🟢 business · 🟡 helper · ◌ adapter"* (one-time, not per row).

---

### 2.4 BusinessRuleDetail (lines 1192–1322)

**Element count: 19 elements → ESSENTIAL 9 / USEFUL 5 / NOISE 4 / DELETE 1**

| # | Element | Currently shown as | Category | Proposal |
|---|---------|-------------------|----------|----------|
| 1 | Banner "⚖ BusinessRule — 도메인 제약 (코드 가드 enforced)" | rose banner above h1 | 🟠 NOISE | Same as others. Drop or shrink to 4-px stripe. |
| 2 | `rule.fqn` (h1, mono, plain text) | large bold mono | 🟢 ESSENTIAL | Keep — but FQN-as-h1 is harder to read than label-as-h1. **Show last segment as h1, full FQN as muted line below.** (Same pattern as TermDetail h1 = label, fqn = subline.) BR has no `label` field — use the last segment. |
| 3 | `rule.severity` inline_select pill (hard/soft, color-coded, w/ confirm modal) | inline in h1 area | 🟢 ESSENTIAL | Keep. |
| 4 | ConfirmToggle | top-right of h1 | 🟢 ESSENTIAL | Keep. |
| 5 | "Statement" Section + InlineEditTextArea | full card | 🟢 ESSENTIAL | Keep. |
| 6 | "Enforced By (코드 가드 위치) · N" Section | always | 🟢 ESSENTIAL | Keep — HelpHint already on title. |
| 7 | Each Enforced By row: "code" pill + FqnLink to method | always | 🟢 ESSENTIAL | Keep. |
| 8 | Empty enforced_by placeholder "미등록 — 운영 시 enforced_by 자동 검출 큐로 보강." | always when empty | 🟡 USEFUL | Keep — this is genuinely informative. |
| 9 | "Terms Referenced · N" Section | only when N>0 | 🟢 ESSENTIAL | Keep. |
| 10 | Each Term Ref pill | violet | 🟢 ESSENTIAL | Keep. |
| 11 | "Operational History (운영 사고) · N" Section | only when N>0 | 🟢 ESSENTIAL | Keep — this is the "drama DNA" core feature. |
| 12 | Each history row: incident_id pill + summary + occurred_at + triggered_by + commit | dense grid | 🟡 USEFUL | Keep. **But:** `triggered_by` is a method FQN shown as plain mono (no FqnLink) — make it clickable. `fixed_at_commit` is a hash with no link — at minimum, monospace it. |
| 13 | "Violated-At Call Sites · N" Section | only when N>0 | 🟠 NOISE-RAW | Currently displays each call site as **`{JSON.stringify(v)}`** — i.e., raw JSON dumped on screen. This is unreadable. **Either** parse the dict and render `caller_method_fqn:line` properly, **or** hide the section behind a "Show diagnostics" disclosure. As-is it actively hurts the user. |
| 14 | "Source / Origin" Section + KV `source` | always | 🟠 NOISE | `rule.source` is bookkeeping ("how was this BR created" — manual/recommend/import). For 99% of inspection it's not needed. **Hide by default**; show under a "Provenance" disclosure with confirmed-by + source + created-at. |
| 15 | KV `source` value "(미지정)" or string | inside Source Section | 🔴 DELETE | See #14 — just hide when empty. |
| 16 | AuthoringBridge | bottom | 🟡 USEFUL | Same — shorten. |
| 17 | (gap) `rule.repo_id` | not shown — OK | 🟢 ESSENTIAL not-rendered | Correct to not render. |
| 18 | (gap) `rule.confirmed` value as text | only via ConfirmToggle | 🟢 ESSENTIAL | OK. |
| 19 | Severity edit confirm modal body | "severity 를 X 로 바꿉니다. 관련 코드 가드 거동에 영향이 있을 수 있습니다." | 🟢 ESSENTIAL | Keep wording — appropriate caution. |

**Needs muted-text caption:**
- Element #2 `rule.fqn` — when shown, add small caption *"BR 식별자 — 도메인.서브도메인.규칙명"* once (BR is the only entity where the FQN itself is the name; users may not realize there's no separate label).
- Element #11 (operational_history) — add muted line under section header: *"이 BR 위반으로 발생한 실 운영 사고."* (glossary covers `operational_history` but the section title alone is dry.)

---

### 2.5 AnchorDetail (lines 1327–1443)

**Element count: 14 elements → ESSENTIAL 7 / USEFUL 3 / NOISE 3 / DELETE 1**

| # | Element | Currently shown as | Category | Proposal |
|---|---------|-------------------|----------|----------|
| 1 | Banner "⚓ AnchorBinding — 코드 fragment ↔ Action slot" | sky banner | 🟠 NOISE | Same pattern. Drop. |
| 2 | `anchor.id` (h1, mono) | large bold mono, truncated | 🟠 NOISE | Anchor IDs are hashes/uuids. Showing them as h1 is hostile to humans. **Use `anchor_locator` as the h1** (it's the human-readable fragment) and put the id under it as a small "id: …" caption. Locator is already shown again in its own Section (#7) — moving it up doesn't double-show because the Section becomes the **edit affordance** while h1 becomes the **identity at a glance**. |
| 3 | `confidence` badge w/ HelpHint | sky pill | 🟡 USEFUL | Keep. |
| 4 | `source` badge "src: AUTO_RECOMMEND" | muted pill | 🟠 NOISE | `source` is bookkeeping (similar to BR.source). **Hide by default**; surface only when `confidence < 0.5` or in a "Provenance" disclosure. The `target_slot` HelpHint covers the relevant info; the source pill clutters the h1 row. |
| 5 | ConfirmToggle | top-right of h1 | 🟢 ESSENTIAL | Keep. |
| 6 | "Anchor Locator" Section + autocomplete edit + HelpHint | full card | 🟢 ESSENTIAL | Keep. |
| 7 | "Code Method (코드 위치)" Section + FqnLink | always shown | 🟢 ESSENTIAL | Keep. |
| 8 | `anchor.line` row "line N (1-indexed)" | muted line under FqnLink | 🟡 USEFUL | Keep. Drop "(1-indexed)" — this is implementation detail, not user info. **Reflow as** `📍 line 35` next to the FqnLink, not as a separate row. |
| 9 | "Target Action / Slot" Section + FqnLink + slot edit | full card | 🟢 ESSENTIAL | Keep. |
| 10 | Target action button "→ action.scm.std.X" + slot inline_text | inside same card | 🟢 ESSENTIAL | Keep. |
| 11 | Slot label "slot:" + InlineEditText | inline | 🟢 ESSENTIAL | Keep. **But:** add a one-time muted caption above the slot field: *"path syntax — 예: params[0]<X>.spec.y"* (glossary covers it but the path syntax is unusual enough that a hint inline helps). |
| 12 | "Rationale" Section + InlineEditTextArea | full card | 🟢 ESSENTIAL | Keep. |
| 13 | AuthoringBridge | bottom | 🟡 USEFUL | Same — shorten. |
| 14 | (gap) `anchor.repo_id` | not rendered — OK | — | OK. |

**Needs muted-text caption:**
- Element #2 (h1 reorganization) — once `anchor_locator` becomes h1, add caption *"코드 fragment 식별자 — Java method body 안의 위치"* on hover.
- Element #11 `slot:` — see above.

---

## Section 3 — Cross-Cutting Patterns (Top 5)

### Pattern A: Banner-on-every-panel redundancy
All 5 components open with a colored banner ("🧬 BusinessTerm — 도메인 의미 단위"). The information is **already encoded** in (1) the breadcrumb at the top of MainPanel (line 56–58), (2) the entity badge in the h1, (3) the panel's accent color. The banner is screen real estate sacrificed to redundant labeling.

**Frequency:** 5/5 components.
**Fix:** Remove the banner OR replace with a 4-px colored left border on the whole panel (no text). Save ~24px of vertical space per panel.

### Pattern B: FQN repeated 3+ times
On a typical Action panel, the FQN `action.scm.std.match_customer_limit_for_order` appears in: (1) the breadcrumb header, (2) the h1 mono line, (3) `declared_on_term` link prefix, (4) the Anchor Bindings → target_action_fqn (rendered in inner cards, sometimes the FQN is shown). Three to four times is typical.

**Frequency:** 5/5 components show FQN at least twice.
**Fix:** Pick **one** authoritative FQN display per panel — the breadcrumb. Other places use the last segment as the visible text and put the full FQN in a `title=` attribute or copy-on-click.

### Pattern C: False/empty fields rendered with placeholder text
Term Flags section (`is_abstract: ✓ is_interface: — struct_like_hint: ✓`), Action Postconditions/Effects empty cards saying "(없음)", Term Composition Parts saying "(미정의)", BR Source saying "(미지정)". These take up vertical space to communicate "nothing here."

**Frequency:** 5/5 components.
**Fix:** Universal rule — **if a field/section has no positive content, collapse to a single header line "X · 0" or hide entirely.** Only show the empty-state card when it's actively informative (e.g., BR `enforced_by` empty has a meaningful caption "운영 시 자동 검출 큐로 보강" — keep that one; drop the rest).

### Pattern D: Status/decision-weight fields shown as small subtitle pills
The two highest-decision-weight fields in the entire modeling section are buried as tiny inline pills:
- `Action.verification_level` (UNMAPPED → ... → PR_PROVEN) — a 5-stage progression that determines whether this Action is trustworthy. Currently a 11px pill in a metadata strip.
- `BusinessRule.severity` (hard / soft) — better positioned, but the visual weight doesn't match its blast radius.

**Frequency:** Most-prominent in ActionDetail; secondary in BR.
**Fix:** Promote `verification_level` to a dedicated row with a 5-step visual indicator (●○○○○ → ●●●●● style). Keep severity as-is (already prominent enough due to color contrast).

### Pattern E: Raw JSON / mono syntax leaked to UI
- `BusinessRuleDetail` line 1308–1311 dumps `JSON.stringify(v)` for each violated-at-call entry. This is debug output, not UI.
- `AnchorBinding.target_slot` shows raw `params[0]<RushOrder>.spec.diameter.range[1]` syntax with no explanation.
- `Action.preconditions` items are shown as bare mono strings — could be DSL code, could be predicate text — no signaling.

**Frequency:** 3 places (BR.violated_at_call, Anchor.target_slot, Action.preconditions).
**Fix:** Either pretty-print or hide-behind-disclosure. Never `JSON.stringify` to UI.

---

## Section 4 — Recommended Fixes Ranked by Impact

| # | Fix | Effort | Impact | Why this rank |
|---|-----|-------|--------|---------------|
| 1 | **Promote `Action.verification_level`** to a 5-step visual indicator on its own row, not a tiny pill | M | ★★★★★ | This is the field users will scan for the most. Burying it is the single biggest UX miss in ActionDetail. |
| 2 | **Hide false/empty flag rows + collapse empty sections** (Pattern C) across all 5 entities | S | ★★★★★ | Removes ~30-50% of visual noise on a typical "lightly mapped" entity. Trivial code change (conditional render). |
| 3 | **Fix `BR.violated_at_call` JSON-dump** (Pattern E #1) — either render properly or hide behind disclosure | S | ★★★★ | Currently embarrassing — looks like a bug. Worse than missing data. |
| 4 | **Replace AnchorDetail h1 (id → locator)** so the most identifying string is on top | S | ★★★★ | Anchor IDs are hashes — useless to humans as h1. Locator is the human-readable thing. |
| 5 | **Drop the 5 colored banners** ("🧬 BusinessTerm — 도메인 의미 단위" etc., Pattern A) in favor of a 4-px left stripe | S | ★★★★ | Saves ~24px/panel × 5 panels = recovered vertical space; removes redundant labeling. |
| 6 | **De-duplicate FQN displays** (Pattern B) — h1/breadcrumb only; other places use last segment + tooltip | M | ★★★★ | Reduces mono-line clutter; FQN becomes a tooltip resource not a visual-weight tax. |
| 7 | **Split dense Realization rows** (#17 Action) into 2 lines + hide `dispatch_source` / `confidence` behind hover | S | ★★★ | These rows currently cram 6+ facts on 2 lines — second-line is hard to parse. |
| 8 | **Render BR `triggered_by` as FqnLink** + monospace `fixed_at_commit` (#12 BR) | S | ★★★ | Tiny change, but `triggered_by` being unclickable is an inconsistency that already trips users. |
| 9 | **Add legend captions for color-coded role pills** (Method roles in CodeTypeDetail #15; Effect ops in ActionDetail #20) | S | ★★★ | Currently users have to memorize green=business, amber=helper. One-line legend per section solves it. |
| 10 | **Move `source` / provenance fields to a "Provenance" disclosure** (BR #14, Anchor #4) collapsed by default | S | ★★ | Cleans up h1 metadata; provenance still reachable for audit. |

(Stretched goal — out of scope for "no code changes" but flagged: Add `sub_actions` rendering for `kind=workflow` Actions. Currently the most important relationship for a workflow Action is invisible.)

---

## Section 5 — Before / After ASCII Mocks

### Mock 1 — ActionDetail h1 + verification (Fix #1, #5, #6)

**BEFORE** (current; lines 200–260):
```
┌─────────────────────────────────────────────────────────────────────┐
│ 🔍 Forward 매핑 — 코드를 도메인 의미로 매핑 (초기 작업)                  │  ← banner
├─────────────────────────────────────────────────────────────────────┤
│ # match customer limit for order   [action] [pure_function] [✓]    │  ← h1
│ action.scm.std.match_customer_limit_for_order · declared on        │  ← mono FQN
│   term.scm.std.customer_std  [SIGNATURE_LOCKED]                    │  ← buried lvl pill
│ domain (derived): scm.std                                           │  ← derived dup
│                                                                     │
│ ┌── 설명 ────────────────────────────────────────────────────────┐  │
```
8 lines of header before content. FQN appears twice (breadcrumb + here). `verification_level` is a 11px pill in a comma-separated list. `domain` is duplicate of `declared_on_term`'s domain.

**AFTER:**
```
┃ # match customer limit for order   [pure_function] [abstract] [✓]  │  ← h1, dropped redundant 'action' badge
┃ ↳ on term.scm.std.customer_std  ⓘ                                  │  ← cross-ref, last segment + tooltip on full
┃                                                                     │
┃ Verification:  ●━━●━━●━━○━━○━━○                                     │  ← promoted, visible
┃                draft  sig   body  sim   pr                          │
┃                ↑ 현재 SIGNATURE_LOCKED                              │
┃                                                                     │
┃ ┌── 설명 ────────────────────────────────────────────────────────┐  │
```
4-px left stripe (┃) replaces banner. Saved ~3 lines. `verification_level` visible at a glance. `domain` removed (implied by declared_on_term).

---

### Mock 2 — TermDetail Flags section (Fix #2)

**BEFORE** (lines 1049–1053):
```
┌── Flags ────────────────────────────────────────────────────────────┐
│  is_abstract       ✓                                                │
│  is_interface      —                                                │
│  struct_like_hint  ✓                                                │
└─────────────────────────────────────────────────────────────────────┘
```
Always rendered. 3 rows × every Term load. Half the rows show `—` (a "false" signal that costs visual weight).

**AFTER (case 1 — at least one flag true):**
```
┌── Flags ────────────────────────────────────────────────────────────┐
│  ✓ is_abstract    ✓ struct_like_hint                                │
└─────────────────────────────────────────────────────────────────────┘
```
Single row, only TRUE flags. (Or hide flags with no documented user action like `struct_like_hint` entirely — see Term audit row #21.)

**AFTER (case 2 — all false):**
```
(section not rendered)
```

---

### Mock 3 — BusinessRuleDetail violated_at_call section (Fix #3)

**BEFORE** (lines 1305–1313):
```
┌── Violated-At Call Sites · 3 ───────────────────────────────────────┐
│  {"caller_method_fqn":"com.scm.api.OrderService#submit","line":     │
│  142,"argument_index":2,"reason":"no_pre_check"}                    │
│  {"caller_method_fqn":"com.scm.api.OrderService#retry","line":      │
│  87,"argument_index":2,"reason":"missed_validation"}                │
│  {"caller_method_fqn":"com.scm.api.BatchJob#nightly","line":        │
│  311,"argument_index":1,"reason":"no_pre_check"}                    │
└─────────────────────────────────────────────────────────────────────┘
```
Raw JSON. Unscannable. Looks like a bug.

**AFTER:**
```
┌── Violated-At Call Sites · 3   (BR 미체크 호출부) ──────────────────┐
│  ⚠  OrderService#submit       L142    no_pre_check        [열기]   │
│  ⚠  OrderService#retry        L87     missed_validation   [열기]   │
│  ⚠  BatchJob#nightly          L311    no_pre_check        [열기]   │
└─────────────────────────────────────────────────────────────────────┘
```
Parse the dict — caller, line, reason. Add caption explaining what this list **means** (it's not obvious from the title alone).

---

## Appendix — Element Count Recap

| Component | Total | 🟢 ESSENTIAL | 🟡 USEFUL | 🟠 NOISE | 🔴 DELETE |
|-----------|------:|----------:|---------:|--------:|---------:|
| TermDetail        | 22 |  9 | 5 | 6 | 2 |
| ActionDetail      | 28 | 11 | 7 | 8 | 2 |
| CodeTypeDetail    | 17 |  7 | 4 | 4 | 2 |
| BusinessRuleDetail| 19 |  9 | 5 | 4 | 1 |
| AnchorDetail      | 14 |  7 | 3 | 3 | 1 |
| **TOTAL**         | **100** | **43** | **24** | **25** | **8** |

**~33% of rendered elements are noise or deletable.** Removing/collapsing them recovers significant vertical space and lets the 43 essential elements breathe.

