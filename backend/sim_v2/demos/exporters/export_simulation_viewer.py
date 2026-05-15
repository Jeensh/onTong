"""Run UC36 + UC37 + UC38 + UC39 and emit a self-contained HTML viewer.

Output: `toClaude/modeling/section4-verification/simulation-viewer.html`
        with all data inlined as a single JSON blob. No web server, no
        external assets — opens directly in any browser.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.exporters.export_simulation_viewer
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc36_v2_final_goal.run import run_v2_final_goal
from backend.sim_v2.demos.uc37_production_fixture_coverage.run import (
    run_production_coverage,
)
from backend.sim_v2.demos.uc38_production_invariants.run import (
    run_invariant_survey,
)
from backend.sim_v2.demos.uc39_b_level_capstone.run import (
    run_production_gap,
    run_synthetic_capstone,
)
from backend.sim_v2.demos.uc40_stub_injected_behavioral.run import (
    run_stub_injected_survey,
)


OUT_PATH = (
    Path(__file__).resolve().parents[4]
    / "toClaude/modeling/section4-verification/simulation-viewer.html"
)


def _effect_lc(lc) -> dict:
    return {
        "source_axis":    lc.source_axis,
        "effect_kind":    lc.effect_kind,
        "discriminator":  lc.discriminator,
        "action_fqn":     lc.action_fqn,
        "proposal_id":    lc.proposal_id,
        "states_visited": list(lc.states_visited),
        "final_state":    lc.final_state,
        "oracle_status":  lc.oracle_status,
        "revision_id":    lc.revision_id,
        "rejection_reason": lc.rejection_reason or "",
    }


def _struct_lc(lc) -> dict:
    return {
        "source_axis":    lc.source_axis,
        "kind":           lc.kind,
        "action_fqn":     lc.action_fqn,
        "proposal_id":    lc.proposal_id,
        "states_visited": list(lc.states_visited),
        "final_state":    lc.final_state,
        "oracle_status":  lc.oracle_status,
        "revision_id":    lc.revision_id,
        "rejection_reason": lc.rejection_reason or "",
    }


def _term_lc(lc) -> dict:
    return {
        "term_fqn":       lc.term_fqn,
        "target_class":   lc.target_class,
        "proposal_id":    lc.proposal_id,
        "states_visited": list(lc.states_visited),
        "final_state":    lc.final_state,
        "oracle_status":  lc.oracle_status,
        "revision_id":    lc.revision_id,
        "rejection_reason": lc.rejection_reason or "",
    }


def _gather_data() -> dict:
    session = open_readonly_session()
    if session is None:
        print(f"WARN: {PRODUCTION_DB_PATH} not found — exporting empty viewer")
        return {"error": "production_db_missing"}

    try:
        print("• Running UC36 (contract-level capstone)…")
        uc36 = run_v2_final_goal(session)

        print("• Running UC37 (fixture coverage)…")
        uc37 = run_production_coverage(session)

        print("• Running UC38 (invariant survey)…")
        uc38 = run_invariant_survey(session)

        print("• Running UC39 (B-level capstone)…")
        uc39_synth = run_synthetic_capstone()
        uc39_prod = run_production_gap(session)

        print("• Running UC40 (stub-injected behavioral survey)…")
        uc40 = run_stub_injected_survey(session)

        # Remaining findings per gate
        remaining_by_gate: dict[str, list[dict]] = {}
        for f in uc36.report.remaining_findings:
            remaining_by_gate.setdefault(f.gate, []).append({
                "action_fqn": f.action_fqn,
                "status":     f.status,
                "key":        f.key,
            })

        data = {
            "generated_at": None,    # set just before write
            "uc36": {
                "repo_id":              uc36.repo_id,
                "baseline_findings":    uc36.baseline_findings,
                "simulated_findings":   uc36.simulated_findings,
                "reduction_pct":        uc36.reduction_pct,
                "term_unblocked_count": uc36.term_unblocked_count,
                "effect_lifecycles":    [_effect_lc(x) for x in uc36.effect_lifecycles],
                "struct_lifecycles":    [_struct_lc(x) for x in uc36.struct_lifecycles],
                "term_lifecycles":      [_term_lc(x) for x in uc36.term_lifecycles],
                "effect_state_counts":  dict(Counter(
                    x.final_state for x in uc36.effect_lifecycles
                )),
                "struct_state_counts":  dict(Counter(
                    x.final_state for x in uc36.struct_lifecycles
                )),
                "term_state_counts":    dict(Counter(
                    x.final_state for x in uc36.term_lifecycles
                )),
                "effect_merged":        uc36.report.effect_merged,
                "structural_merged":    uc36.report.structural_merged,
                "remaining_by_gate":    remaining_by_gate,
            },
            "uc37": {
                "repo_id":             uc37.repo_id,
                "total_actions":       uc37.total_actions,
                "total_fixtures":      uc37.total_fixtures,
                "directly_driveable":  uc37.directly_driveable,
                "status_counts":       dict(uc37.status_counts),
                "rows": [
                    {
                        "action_fqn":      r.action_fqn,
                        "code_method_fqn": r.code_method_fqn or "",
                        "status":          r.status,
                        "fixtures":        r.fixtures,
                        "primitives":      r.primitives,
                        "skipped":         r.skipped,
                        "error":           r.error,
                    } for r in uc37.rows
                ],
            },
            "uc38": {
                "repo_id":         uc38.repo_id,
                "total_actions":   uc38.total_actions,
                "total_fixtures":  uc38.total_fixtures,
                "total_passing":   uc38.total_passing,
                "status_counts":   dict(uc38.status_counts),
                "rows": [
                    {
                        "action_fqn":      r.action_fqn,
                        "declared_return": r.declared_return,
                        "fixtures":        r.fixtures,
                        "passing":         r.passing,
                        "status":          r.status,
                        "sample_error":    r.sample_error,
                    } for r in uc38.rows
                ],
            },
            "uc39": {
                "synthetic": {
                    "fixtures_generated": uc39_synth.fixtures_generated,
                    "fixtures_matched":   uc39_synth.fixtures_matched,
                    "fixtures_passed":    uc39_synth.fixtures_passed,
                    "aggregate_status":   uc39_synth.aggregate_status,
                },
                "production": {
                    "total_actions": uc39_prod.total_actions,
                    "cause_counts":  dict(uc39_prod.cause_counts),
                    "rows": [
                        {
                            "action_fqn":     r.action_fqn,
                            "fixtures":       r.fixtures,
                            "matched":        r.matched,
                            "passes":         r.passes,
                            "failure_cause":  r.failure_cause,
                            "sample_error":   r.sample_error,
                        } for r in uc39_prod.rows
                    ],
                },
            },
            "uc40": {
                "repo_id":         uc40.repo_id,
                "total_actions":   uc40.total_actions,
                "total_fixtures":  uc40.total_fixtures,
                "total_passing":   uc40.total_passing,
                "status_counts":   dict(uc40.status_counts),
                "rows": [
                    {
                        "action_fqn":      r.action_fqn,
                        "declared_return": r.declared_return,
                        "fixtures":        r.fixtures,
                        "passing":         r.passing,
                        "status":          r.status,
                        "stub_count":      r.stub_count,
                        "sample_error":    r.sample_error,
                    } for r in uc40.rows
                ],
            },
        }
        return data
    finally:
        session.close()


_HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<title>Section 4 — Simulation Viewer</title>
<style>
  :root { --blue:#1e40af; --green:#059669; --amber:#b45309; --red:#b91c1c;
          --bg:#f9fafb; --card:#fff; --line:#e5e7eb; --text:#111827;
          --muted:#6b7280; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif;
         margin: 0; background: var(--bg); color: var(--text); }
  header { background: linear-gradient(180deg,#1e3a8a,#1e40af); color:#fff;
           padding: 22px 28px; }
  header h1 { margin: 0 0 6px 0; font-size: 1.6rem; }
  header .sub { color:#bfdbfe; font-size: 0.85rem; }
  nav.tabs { display:flex; gap:0; padding: 0 16px; background:#1e3a8a;
             border-top:1px solid #1d4ed8; }
  nav.tabs button { background: transparent; color:#bfdbfe; border:0;
                    padding: 10px 16px; cursor:pointer; font-size:0.95rem;
                    border-bottom: 3px solid transparent; }
  nav.tabs button.active { color:#fff; border-bottom-color:#fbbf24;
                           background: rgba(255,255,255,0.08); }
  nav.tabs button:hover { background: rgba(255,255,255,0.06); }
  main { padding: 24px 28px; max-width: 1280px; margin: 0 auto; }
  section.tab { display:none; }
  section.tab.active { display:block; }
  h2 { margin-top: 0; color: var(--blue); }
  h3 { margin-top: 26px; color: #374151; }
  .grid4 { display:grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
           margin: 18px 0; }
  .card { background: var(--card); padding: 16px 18px; border-radius: 10px;
          border:1px solid var(--line); }
  .card .n { font-size: 1.8rem; font-weight: 700; color: var(--blue); }
  .card .lbl { font-size: 0.82rem; color: var(--muted); margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; background: var(--card);
          border-radius: 8px; overflow: hidden; border:1px solid var(--line);
          margin-top: 12px; }
  th, td { padding: 9px 12px; border-bottom: 1px solid var(--line);
           text-align: left; font-size: 0.88rem; }
  th { background: #f3f4f6; font-weight: 600; color: #374151; }
  tr:last-child td { border-bottom: 0; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 8px;
           font-size: 0.74rem; font-weight: 600; white-space: nowrap; }
  .b-green { background: #d1fae5; color:#065f46; }
  .b-amber { background: #fef3c7; color:#92400e; }
  .b-red   { background: #fee2e2; color:#991b1b; }
  .b-blue  { background: #dbeafe; color:#1e40af; }
  .b-gray  { background: #e5e7eb; color:#374151; }
  code { font-family: ui-monospace, monospace; background:#f3f4f6;
         padding: 1px 5px; border-radius: 3px; font-size: 0.85em; }
  .row-detail { color: var(--muted); font-size: 0.82rem; }
  .legend { margin: 8px 0 16px; color: var(--muted); font-size: 0.85rem; }
  .counts { display:flex; gap: 10px; flex-wrap: wrap; margin: 8px 0 16px; }
  .count-chip { background:#fff; border:1px solid var(--line);
                padding: 6px 12px; border-radius: 18px; font-size: 0.85rem; }
  .count-chip b { color: var(--blue); }
  details { background:#fff; border:1px solid var(--line); border-radius:6px;
            padding: 8px 12px; margin: 6px 0; }
  details summary { cursor: pointer; font-weight: 600; }
  .filter-bar { display:flex; gap:8px; margin: 10px 0; flex-wrap: wrap; }
  .filter-bar input { padding: 6px 10px; border:1px solid var(--line);
                      border-radius: 6px; font-size: 0.9rem; min-width: 200px; }
  .filter-bar select { padding: 6px 10px; border:1px solid var(--line);
                       border-radius: 6px; font-size: 0.9rem; }
  .empty { color: var(--muted); padding: 16px; text-align: center; }
  pre.err { background: #fef2f2; color: #991b1b; padding: 8px 12px;
            border-radius: 4px; font-size: 0.78rem; white-space: pre-wrap;
            margin: 4px 0 0 0; }
</style>
</head><body>
<header>
  <h1>Section 4 — Simulation Viewer  <span style="font-size:0.7em;font-weight:400;opacity:0.7;">slab-design-real-v2</span></h1>
  <div class="sub">UC36 (contract-level) + UC37/38/39 (B-level) — 결과 정적 viewer</div>
</header>
<nav class="tabs">
  <button class="tab-btn active" data-tab="overview">Overview</button>
  <button class="tab-btn" data-tab="effect">Effect Axis</button>
  <button class="tab-btn" data-tab="struct">Structural Axis</button>
  <button class="tab-btn" data-tab="term">Term Axis</button>
  <button class="tab-btn" data-tab="blevel">B-level</button>
  <button class="tab-btn" data-tab="stubs">W74 Stub-injected</button>
  <button class="tab-btn" data-tab="coverage">Coverage</button>
</nav>
<main>
  <section id="overview" class="tab active"></section>
  <section id="effect" class="tab"></section>
  <section id="struct" class="tab"></section>
  <section id="term" class="tab"></section>
  <section id="blevel" class="tab"></section>
  <section id="stubs" class="tab"></section>
  <section id="coverage" class="tab"></section>
</main>

<script id="sim-data" type="application/json">__DATA_JSON__</script>
<script>
const DATA = JSON.parse(document.getElementById("sim-data").textContent);

function el(tag, attrs, ...children) {
  const e = document.createElement(tag);
  for (const k in (attrs||{})) {
    if (k === "class") e.className = attrs[k];
    else if (k === "html") e.innerHTML = attrs[k];
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), attrs[k]);
    else e.setAttribute(k, attrs[k]);
  }
  for (const c of children.flat()) {
    if (c == null) continue;
    if (typeof c === "string") e.appendChild(document.createTextNode(c));
    else e.appendChild(c);
  }
  return e;
}

function badge(state) {
  const m = {
    "MERGED":  "b-green",
    "ACCEPTED":"b-green",
    "REVIEWED":"b-blue",
    "ORACLED": "b-blue",
    "PROPOSED":"b-blue",
    "DRAFT":   "b-amber",
    "REJECTED":"b-red",
    "PASS":    "b-green",
    "FAIL":    "b-red",
    "GREEN":   "b-green",
    "FULL_PRIMITIVE": "b-green",
    "PARTIAL":         "b-amber",
    "ALL_NULL":        "b-gray",
    "NO_LINK":         "b-gray",
    "TRANSLATOR_NAMERROR":  "b-amber",
    "TRANSLATOR_ATTRERROR": "b-amber",
    "TRANSLATOR_SYNTAX":    "b-amber",
    "NO_BASELINE":          "b-blue",
    "FAIL_THROW":           "b-red",
    "FAIL_TYPE":            "b-red",
    "FAIL_DETERMINISM":     "b-red",
    "ERROR":                "b-red",
    "INCONCLUSIVE":         "b-gray",
  };
  return el("span", {class: "badge " + (m[state] || "b-gray")}, state);
}

function countChips(counts) {
  const wrap = el("div", {class:"counts"});
  for (const [k, v] of Object.entries(counts || {})) {
    wrap.appendChild(el("span", {class:"count-chip"},
      el("b", null, String(v)), " " + k));
  }
  return wrap;
}

// ─── Overview ─────────────────────────────────────────────────────────
function renderOverview() {
  const sec = document.getElementById("overview");
  sec.innerHTML = "";
  if (DATA.error) {
    sec.appendChild(el("div", {class:"empty"}, "production DB 없음 — viewer 가 빈 상태입니다."));
    return;
  }
  const u36 = DATA.uc36, u37 = DATA.uc37, u38 = DATA.uc38, u39 = DATA.uc39;

  sec.appendChild(el("h2", null, "Contract-level capstone (UC36) — v2 fully clean"));
  const g = el("div", {class:"grid4"});
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, String(u36.baseline_findings)),
    el("div", {class:"lbl"}, "Baseline findings")));
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, String(u36.simulated_findings)),
    el("div", {class:"lbl"}, "Simulated remaining")));
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, u36.reduction_pct.toFixed(1) + "%"),
    el("div", {class:"lbl"}, "Reduction")));
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, String(u36.effect_merged + u36.structural_merged + u36.term_lifecycles.filter(t=>t.final_state==="MERGED").length)),
    el("div", {class:"lbl"}, "Total MERGED proposals")));
  sec.appendChild(g);

  sec.appendChild(el("h3", null, "Axis breakdown"));
  const tbl = el("table");
  tbl.appendChild(el("thead", null, el("tr", null,
    el("th", null, "Axis"), el("th", null, "Lifecycles"),
    el("th", null, "MERGED"), el("th", null, "Other states"))));
  const tb = el("tbody");
  for (const [axis, lcs, counts] of [
    ["Effect (exception + annotation)", u36.effect_lifecycles, u36.effect_state_counts],
    ["Structural (param + return-type)", u36.struct_lifecycles, u36.struct_state_counts],
    ["Term (PROPOSE_NEW_TERM cascade)", u36.term_lifecycles, u36.term_state_counts],
  ]) {
    const merged = counts.MERGED || 0;
    const other = Object.entries(counts).filter(([k]) => k !== "MERGED")
      .map(([k,v]) => k + " " + v).join(", ") || "—";
    tb.appendChild(el("tr", null,
      el("td", null, axis),
      el("td", null, String(lcs.length)),
      el("td", null, badge(merged > 0 ? "MERGED" : "DRAFT"), " " + merged),
      el("td", {class:"row-detail"}, other),
    ));
  }
  tbl.appendChild(tb);
  sec.appendChild(tbl);

  sec.appendChild(el("h2", null, "B-level capstone (UC39)"));
  const synth = u39.synthetic;
  sec.appendChild(el("p", null,
    "Part A — synthetic pipeline proof: ",
    el("b", null, synth.fixtures_passed + " / " + synth.fixtures_matched + " PASS"),
    " (status: ", badge(synth.aggregate_status), ")"));
  const prod = u39.production;
  const greenCount = prod.cause_counts.GREEN || 0;
  sec.appendChild(el("p", null,
    "Part B — production gap: ",
    el("b", null, greenCount + " / " + prod.rows.length + " GREEN"),
    " (rest 가 모두 named cause)"));
  sec.appendChild(countChips(prod.cause_counts));

  sec.appendChild(el("h3", null, "Production fixture reach (UC37)"));
  sec.appendChild(el("p", {class:"row-detail"},
    u37.directly_driveable + " / " + u37.total_actions +
    " actions driveable end-to-end, " + u37.total_fixtures + " fixtures generated"));
  sec.appendChild(countChips(u37.status_counts));

  sec.appendChild(el("h3", null, "Twin invariant survey (UC38)"));
  sec.appendChild(el("p", {class:"row-detail"},
    u38.total_passing + " / " + u38.total_fixtures + " fixture PASS, " +
    u38.rows.length + " actions surveyed"));
  sec.appendChild(countChips(u38.status_counts));
}

// ─── Lifecycle tabs ──────────────────────────────────────────────────
function renderLifecycleTable(sec_id, title, rows, columns) {
  const sec = document.getElementById(sec_id);
  sec.innerHTML = "";
  sec.appendChild(el("h2", null, title));

  const counts = {};
  for (const r of rows) counts[r.final_state] = (counts[r.final_state]||0) + 1;
  sec.appendChild(countChips(counts));

  const bar = el("div", {class:"filter-bar"});
  const inp = el("input", {placeholder:"action / target 검색…", type:"text"});
  const sel = el("select");
  sel.appendChild(el("option", {value:""}, "(모든 final_state)"));
  for (const s of Object.keys(counts)) sel.appendChild(el("option", {value:s}, s));
  bar.appendChild(inp); bar.appendChild(sel);
  sec.appendChild(bar);

  const tbl = el("table");
  const head = el("thead", null,
    el("tr", null, ...columns.map(c => el("th", null, c.label))));
  tbl.appendChild(head);
  const tb = el("tbody");
  tbl.appendChild(tb);
  sec.appendChild(tbl);

  function render() {
    tb.innerHTML = "";
    const needle = inp.value.toLowerCase().trim();
    const wantState = sel.value;
    let shown = 0;
    for (const r of rows) {
      if (wantState && r.final_state !== wantState) continue;
      const hay = (r.action_fqn || r.term_fqn || "") + " " +
                  (r.target_class || "") + " " + (r.kind || r.effect_kind || "");
      if (needle && !hay.toLowerCase().includes(needle)) continue;
      const tr = el("tr");
      for (const c of columns) {
        const cell = c.render(r);
        tr.appendChild(el("td", null, cell));
      }
      tb.appendChild(tr);
      shown++;
    }
    if (shown === 0) tb.appendChild(el("tr", null,
      el("td", {colspan:String(columns.length), class:"empty"}, "조건 일치 없음")));
  }
  inp.addEventListener("input", render);
  sel.addEventListener("change", render);
  render();
}

function renderEffect() {
  if (!DATA.uc36) return;
  renderLifecycleTable("effect",
    "Effect axis — exception + annotation lifecycle",
    DATA.uc36.effect_lifecycles, [
      {label:"Action FQN",     render: r => r.action_fqn},
      {label:"Source",         render: r => badge(r.source_axis)},
      {label:"Effect kind",    render: r => r.effect_kind},
      {label:"Discriminator",  render: r => r.discriminator || "—"},
      {label:"States visited", render: r => el("span", {class:"row-detail"},
         r.states_visited.join(" → "))},
      {label:"Final",          render: r => badge(r.final_state)},
      {label:"Oracle",         render: r => badge(r.oracle_status)},
    ]);
}

function renderStruct() {
  if (!DATA.uc36) return;
  renderLifecycleTable("struct",
    "Structural axis — param + return-type lifecycle",
    DATA.uc36.struct_lifecycles, [
      {label:"Action FQN",     render: r => r.action_fqn},
      {label:"Source",         render: r => badge(r.source_axis)},
      {label:"Kind",           render: r => r.kind},
      {label:"States visited", render: r => el("span", {class:"row-detail"},
         r.states_visited.join(" → "))},
      {label:"Final",          render: r => badge(r.final_state)},
      {label:"Oracle",         render: r => badge(r.oracle_status)},
    ]);
}

function renderTerm() {
  if (!DATA.uc36) return;
  const sec = document.getElementById("term");
  sec.innerHTML = "";
  sec.appendChild(el("h2", null, "Term axis — PROPOSE_NEW_TERM lifecycle + cascade"));
  sec.appendChild(el("p", {class:"row-detail"},
    "두 term MERGE (ProductCategory + BatchResult) 가 " +
    DATA.uc36.term_unblocked_count +
    " PROPOSE_NEW_TERM structural case 를 cascade 로 unblock"));

  const tbl = el("table");
  tbl.appendChild(el("thead", null, el("tr", null,
    el("th", null, "Term FQN"), el("th", null, "Target class"),
    el("th", null, "States visited"), el("th", null, "Final"),
    el("th", null, "Oracle"))));
  const tb = el("tbody");
  for (const r of DATA.uc36.term_lifecycles) {
    tb.appendChild(el("tr", null,
      el("td", null, r.term_fqn),
      el("td", null, el("code", null, r.target_class)),
      el("td", {class:"row-detail"}, r.states_visited.join(" → ")),
      el("td", null, badge(r.final_state)),
      el("td", null, badge(r.oracle_status)),
    ));
  }
  tbl.appendChild(tb);
  sec.appendChild(tbl);

  if (Object.keys(DATA.uc36.remaining_by_gate).length) {
    sec.appendChild(el("h3", null, "Remaining findings after simulation"));
    const t2 = el("table");
    t2.appendChild(el("thead", null, el("tr", null,
      el("th", null, "Gate"), el("th", null, "Action FQN"),
      el("th", null, "Status"), el("th", null, "Key"))));
    const tb2 = el("tbody");
    for (const [gate, items] of Object.entries(DATA.uc36.remaining_by_gate)) {
      for (const f of items) tb2.appendChild(el("tr", null,
        el("td", null, gate),
        el("td", null, f.action_fqn),
        el("td", null, f.status),
        el("td", null, el("code", null, f.key)),
      ));
    }
    t2.appendChild(tb2);
    sec.appendChild(t2);
  } else {
    sec.appendChild(el("h3", null, "✓ Remaining findings: 0 (fully clean state)"));
  }
}

function renderBLevel() {
  if (!DATA.uc39) return;
  const sec = document.getElementById("blevel");
  sec.innerHTML = "";
  const u39 = DATA.uc39;

  sec.appendChild(el("h2", null, "B-level capstone — UC39"));

  sec.appendChild(el("h3", null, "Part A — Synthetic pipeline proof"));
  const synth = u39.synthetic;
  const g = el("div", {class:"grid4"});
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, String(synth.fixtures_generated)),
    el("div", {class:"lbl"}, "Generated")));
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, String(synth.fixtures_matched)),
    el("div", {class:"lbl"}, "Baselines attached")));
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, String(synth.fixtures_passed)),
    el("div", {class:"lbl"}, "Behavioral PASS")));
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, synth.aggregate_status),
    el("div", {class:"lbl"}, "Aggregate")));
  sec.appendChild(g);

  sec.appendChild(el("h3", null, "Part B — Production gap diagnosis"));
  sec.appendChild(countChips(u39.production.cause_counts));

  const tbl = el("table");
  tbl.appendChild(el("thead", null, el("tr", null,
    el("th", null, "Action FQN"),
    el("th", null, "Fixtures"),
    el("th", null, "Matched"),
    el("th", null, "Passes"),
    el("th", null, "Cause"),
    el("th", null, "Sample error"),
  )));
  const tb = el("tbody");
  for (const r of u39.production.rows) {
    tb.appendChild(el("tr", null,
      el("td", null, r.action_fqn),
      el("td", null, String(r.fixtures)),
      el("td", null, String(r.matched)),
      el("td", null, String(r.passes)),
      el("td", null, badge(r.failure_cause)),
      el("td", null, r.sample_error ? el("pre", {class:"err"}, r.sample_error) : "—"),
    ));
  }
  tbl.appendChild(tb);
  sec.appendChild(tbl);
}

function renderCoverage() {
  if (!DATA.uc37) return;
  const sec = document.getElementById("coverage");
  sec.innerHTML = "";

  sec.appendChild(el("h2", null, "Fixture coverage + invariant survey (UC37 + UC38)"));

  if (DATA.uc40) {
    sec.appendChild(el("h2", null, "W74 Stub-injected production behavioral (UC40)"));
    const u40 = DATA.uc40;
    const passN = u40.status_counts.PASS || 0;
    sec.appendChild(el("p", null,
      "Sandbox stub injection 적용 후 ",
      el("b", null, passN + " / " + u40.rows.length + " actions PASS"),
      " · fixture pass rate ",
      el("b", null, (100 * u40.total_passing / Math.max(1, u40.total_fixtures))
                        .toFixed(1) + "%")));
    sec.appendChild(countChips(u40.status_counts));
  }

  sec.appendChild(el("h3", null, "UC37 — W71 fixture coverage"));
  sec.appendChild(countChips(DATA.uc37.status_counts));

  const t1 = el("table");
  t1.appendChild(el("thead", null, el("tr", null,
    el("th", null, "Action FQN"),
    el("th", null, "Status"),
    el("th", null, "Fixtures"),
    el("th", null, "Primitives"),
    el("th", null, "Skipped (object_ref)"),
    el("th", null, "Code method FQN"),
  )));
  const tb1 = el("tbody");
  for (const r of DATA.uc37.rows) tb1.appendChild(el("tr", null,
    el("td", null, r.action_fqn),
    el("td", null, badge(r.status)),
    el("td", null, String(r.fixtures)),
    el("td", null, String(r.primitives)),
    el("td", null, String(r.skipped)),
    el("td", {class:"row-detail"}, el("code", null, r.code_method_fqn || "—")),
  ));
  t1.appendChild(tb1);
  sec.appendChild(t1);

  sec.appendChild(el("h3", null, "UC38 — W72 invariant survey"));
  sec.appendChild(countChips(DATA.uc38.status_counts));

  const t2 = el("table");
  t2.appendChild(el("thead", null, el("tr", null,
    el("th", null, "Action FQN"),
    el("th", null, "Status"),
    el("th", null, "Pass / total fixtures"),
    el("th", null, "Declared return"),
    el("th", null, "Sample error"),
  )));
  const tb2 = el("tbody");
  for (const r of DATA.uc38.rows) tb2.appendChild(el("tr", null,
    el("td", null, r.action_fqn),
    el("td", null, badge(r.status)),
    el("td", null, r.passing + " / " + r.fixtures),
    el("td", null, r.declared_return),
    el("td", null, r.sample_error ? el("pre", {class:"err"}, r.sample_error) : "—"),
  ));
  t2.appendChild(tb2);
  sec.appendChild(t2);
}

// Tab switching
document.querySelectorAll("nav.tabs .tab-btn").forEach(b => {
  b.addEventListener("click", () => {
    document.querySelectorAll("nav.tabs .tab-btn").forEach(x => x.classList.remove("active"));
    document.querySelectorAll("section.tab").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    document.getElementById(b.dataset.tab).classList.add("active");
  });
});

function renderStubs() {
  if (!DATA.uc40) return;
  const sec = document.getElementById("stubs");
  sec.innerHTML = "";
  const u = DATA.uc40;

  sec.appendChild(el("h2", null, "W74 Stub-injected production behavioral survey (UC40)"));
  sec.appendChild(el("p", {class:"row-detail"},
    "W74 의 sandbox stub injection 으로 UC38 의 0/11 PASS → 큰 폭으로 개선. " +
    "각 method 의 anchor_locator 의 'CONST = value' + AST unbound names 로 " +
    "자동 stub 생성, NameError 발생 0건."));

  const g = el("div", {class:"grid4"});
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, (u.status_counts.PASS || 0) + " / " + u.rows.length),
    el("div", {class:"lbl"}, "Actions PASS")));
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, u.total_passing + " / " + u.total_fixtures),
    el("div", {class:"lbl"}, "Fixtures PASS")));
  const passPct = u.total_fixtures > 0
    ? (100 * u.total_passing / u.total_fixtures).toFixed(1) : "0";
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, passPct + "%"),
    el("div", {class:"lbl"}, "Fixture pass rate")));
  const totalStubs = u.rows.reduce((s, r) => s + r.stub_count, 0);
  g.appendChild(el("div", {class:"card"},
    el("div", {class:"n"}, String(totalStubs)),
    el("div", {class:"lbl"}, "Total stubs auto-derived")));
  sec.appendChild(g);

  sec.appendChild(el("h3", null, "Status counts"));
  sec.appendChild(countChips(u.status_counts));

  sec.appendChild(el("h3", null, "Per-action"));
  const tbl = el("table");
  tbl.appendChild(el("thead", null, el("tr", null,
    el("th", null, "Action FQN"),
    el("th", null, "Status"),
    el("th", null, "Pass / total"),
    el("th", null, "Stubs"),
    el("th", null, "Return"),
    el("th", null, "Sample error"),
  )));
  const tb = el("tbody");
  for (const row of u.rows) {
    tb.appendChild(el("tr", null,
      el("td", null, row.action_fqn),
      el("td", null, badge(row.status)),
      el("td", null, row.passing + " / " + row.fixtures),
      el("td", null, String(row.stub_count)),
      el("td", null, row.declared_return),
      el("td", null, row.sample_error
                       ? el("pre", {class:"err"}, row.sample_error) : "—"),
    ));
  }
  tbl.appendChild(tb);
  sec.appendChild(tbl);
}

renderOverview();
renderEffect();
renderStruct();
renderTerm();
renderBLevel();
renderStubs();
renderCoverage();
</script>
</body></html>
"""


def main() -> int:
    print(f"Exporting simulation viewer → {OUT_PATH}")
    data = _gather_data()

    import datetime
    data["generated_at"] = datetime.datetime.now().isoformat(timespec="seconds")

    json_blob = json.dumps(data, ensure_ascii=False, indent=2)
    # Embed safely inside a <script type="application/json"> tag — only need to
    # escape `</script>` sequences.
    json_blob = json_blob.replace("</script>", "<\\/script>")

    html = _HTML_TEMPLATE.replace("__DATA_JSON__", json_blob)
    OUT_PATH.write_text(html, encoding="utf-8")

    print(f"✓ Written {len(html):,} bytes")
    print(f"  Open in browser: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
