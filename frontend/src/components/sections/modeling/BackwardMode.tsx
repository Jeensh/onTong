"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useWorkbench } from "./store";
import { cn } from "@/lib/utils";

/**
 * Backward (수정 모드) — Phase 2a 강화.
 * V7 prototype 정합:
 * - branch bar (4 가설 동시)
 * - risk score ring (conic gradient)
 * - side-by-side diff (Java/Term/Rule/매뉴얼)
 * - cascade tree (depth 슬라이더 + HARD 위반 표시)
 *
 * 현재 mock 데이터로 표시. Phase 2 후반에 Query API 의 cascade endpoint 와 연결.
 */

interface Branch {
  id: string;
  label: string;
  desc: string;
}

const BRANCHES: Branch[] = [
  { id: "b1", label: "0.25→0.30", desc: "current" },
  { id: "b2", label: "0.25→0.28", desc: "보수" },
  { id: "b3", label: "0.25→0.35", desc: "적극" },
  { id: "b4", label: "Mn 도 동시", desc: "복합" },
];

const DIFF_TABS = ["Java", "Term", "Rule", "매뉴얼"] as const;
type DiffTab = (typeof DIFF_TABS)[number];

interface CascadeRow {
  depth: 0 | 1 | 2;
  kind: "term" | "rule" | "action";
  label: string;
  note: string;
  hard?: boolean;
}

const CASCADE: CascadeRow[] = [
  { depth: 0, kind: "term", label: "term.scm.c_pct.range[1]", note: "변경 시작점" },
  { depth: 1, kind: "rule", label: "rule.scm.c_range", note: "precondition refs" },
  { depth: 1, kind: "action", label: "action.scm.주문_검증", note: "preconditions[0]" },
  { depth: 1, kind: "action", label: "action.scm.화학성분_검증", note: "preconditions[2]" },
  { depth: 2, kind: "action", label: "action.scm.출하_승인", note: "depends on 화학성분_검증 (간접)" },
  { depth: 2, kind: "rule", label: "rule.scm.quality_grade_a", note: "⚠ HARD 위반 가능", hard: true },
];

export function BackwardMode() {
  const [activeBranch, setActiveBranch] = useState("b1");
  const [diffTab, setDiffTab] = useState<DiffTab>("Java");
  const [cascadeDepth, setCascadeDepth] = useState(2);
  const { setGraphMode } = useWorkbench();

  return (
    <div className="p-5 max-w-[920px]">
      {/* Banner */}
      <div className="bg-amber-500/10 border border-amber-400 rounded-md px-3 py-2.5 mb-4 flex items-center gap-3">
        <span className="bg-amber-500 text-background font-bold text-[10.5px] px-2 py-0.5 rounded">
          🔧 BACKWARD
        </span>
        <span className="text-[12.5px]">
          <strong>C 함량 max 0.25 → 0.30 변경 영향</strong> · 4 branches 동시 비교 · risk 62/100
        </span>
      </div>

      {/* Branch bar */}
      <div className="flex items-center gap-1.5 mb-3 flex-wrap">
        <span className="text-[11px] text-muted-foreground mr-1">분기:</span>
        {BRANCHES.map((b) => (
          <button
            key={b.id}
            onClick={() => setActiveBranch(b.id)}
            className={cn(
              "px-2.5 py-1 text-[11.5px] rounded border flex items-center gap-1.5",
              activeBranch === b.id
                ? "border-primary text-primary bg-primary/5"
                : "border-border text-muted-foreground hover:bg-muted",
            )}
          >
            <span>{activeBranch === b.id ? "●" : "○"}</span>
            {b.label}
            <span className="text-[10px] text-muted-foreground">({b.desc})</span>
          </button>
        ))}
        <button className="text-[11px] px-2 py-1 rounded border border-dashed border-border text-muted-foreground hover:text-primary hover:border-primary">
          + 새 분기
        </button>
        <span className="ml-auto text-[10.5px] text-muted-foreground">⏎ 활성 분기 비교</span>
      </div>

      {/* Risk score */}
      <div className="bg-card border border-border rounded-md p-4 mb-4 flex items-center gap-4">
        <div
          className="w-[70px] h-[70px] rounded-full relative flex items-center justify-center"
          style={{
            background: `conic-gradient(rgb(245,158,11) 0% 62%, rgb(15,23,42) 62% 100%)`,
          }}
        >
          <div className="absolute inset-1.5 bg-card rounded-full" />
          <span className="relative z-10 text-[18px] font-bold text-amber-400">62</span>
        </div>
        <div className="flex-1 text-[12px] text-muted-foreground leading-7">
          <div>
            <strong className="text-foreground">위험도 62/100</strong> · medium-high
          </div>
          <div>
            · 영향 크기: <strong className="text-foreground">14 코드 위치 + 6 Action + 2 Rule</strong>{" "}
            (점수 18)
          </div>
          <div>
            · 시뮬 통과 신뢰도: <strong className="text-foreground">78%</strong> (점수 22)
          </div>
          <div>
            · HARD-rule 위반 가능: <strong className="text-foreground">1건</strong>{" "}
            (rule.scm.quality_grade_a, 점수 22)
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Button size="sm" className="text-[11px]">🌊 시뮬 실행</Button>
          <Button size="sm" variant="outline" className="text-[11px]">📤 draft PR</Button>
        </div>
      </div>

      {/* Side-by-side diff */}
      <div className="mb-2 flex items-center gap-3">
        <h3 className="text-[12.5px] font-semibold uppercase tracking-wider text-muted-foreground">
          Side-by-side Diff
        </h3>
        <div className="ml-auto flex bg-muted border border-border rounded overflow-hidden">
          {DIFF_TABS.map((t) => (
            <button
              key={t}
              onClick={() => setDiffTab(t)}
              className={cn(
                "px-2.5 py-0.5 text-[10.5px] border-r border-border last:border-r-0",
                diffTab === t
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2.5 mb-4">
        <DiffPane
          label="As-is (현재)"
          tone="muted"
          lines={[
            { type: "u", text: "@Override" },
            { type: "u", text: "public ValidationResult validate() {" },
            { type: "u", text: "  if (latest.C < 0.10 ||" },
            { type: "del", text: "      latest.C > 0.25)" },
            { type: "u", text: '    return fail("C 함량 위반");' },
            { type: "u", text: "  ..." },
            { type: "u", text: "}" },
          ]}
        />
        <DiffPane
          label="To-be (제안)"
          tone="emerald"
          lines={[
            { type: "u", text: "@Override" },
            { type: "u", text: "public ValidationResult validate() {" },
            { type: "u", text: "  if (latest.C < 0.10 ||" },
            { type: "add", text: "      latest.C > 0.30)" },
            { type: "u", text: '    return fail("C 함량 위반");' },
            { type: "u", text: "  ..." },
            { type: "u", text: "}" },
          ]}
        />
      </div>

      {/* Cascade preview */}
      <div className="mb-2 flex items-center gap-3">
        <h3 className="text-[12.5px] font-semibold uppercase tracking-wider text-muted-foreground">
          Cascade — 직접 + 간접 영향
        </h3>
        <div className="ml-auto flex items-center gap-2 text-[11px] text-muted-foreground">
          depth:
          <input
            type="range"
            min={1}
            max={5}
            value={cascadeDepth}
            onChange={(e) => setCascadeDepth(Number(e.target.value))}
            className="w-32 accent-primary"
          />
          <span className="text-primary font-semibold">{cascadeDepth} hops</span>
        </div>
      </div>

      <div className="bg-card border border-border rounded-md p-3 mb-4 text-[12.5px]">
        {CASCADE.filter((r) => r.depth <= cascadeDepth - 1).map((row, i) => (
          <CascadeRowEl key={i} row={row} />
        ))}
      </div>

      <div className="flex items-center gap-2 mt-4">
        <Button size="sm" onClick={() => setGraphMode(true)} className="text-[11.5px]">
          🌐 그래프 위에서 path 시각화 보기
        </Button>
        <span className="ml-auto text-[11px] text-muted-foreground">
          diff/risk/cascade/branch 4가지 = P10 답변 흡수 ✓
        </span>
      </div>
    </div>
  );
}

function DiffPane({
  label,
  tone,
  lines,
}: {
  label: string;
  tone: "muted" | "emerald";
  lines: { type: "u" | "del" | "add"; text: string }[];
}) {
  return (
    <div className="bg-muted border border-border rounded-md p-3 overflow-x-auto">
      <div
        className={cn(
          "text-[11px] font-semibold uppercase tracking-wider mb-1.5",
          tone === "emerald" ? "text-emerald-400" : "text-muted-foreground",
        )}
      >
        {label}
      </div>
      <pre className="font-mono text-[11.5px] leading-relaxed">
        {lines.map((l, i) => (
          <span
            key={i}
            className={cn(
              "block px-1",
              l.type === "del" && "bg-destructive/10",
              l.type === "add" && "bg-emerald-500/10",
              l.type === "u" && "text-muted-foreground",
            )}
          >
            {l.text}
          </span>
        ))}
      </pre>
    </div>
  );
}

function CascadeRowEl({ row }: { row: CascadeRow }) {
  const indent = row.depth === 0 ? "" : row.depth === 1 ? "pl-6" : "pl-10 text-muted-foreground";
  const bg = row.depth === 0 ? "bg-amber-500/10" : "";
  const arrow = row.depth === 0 ? "" : row.depth === 1 ? "↓" : "↓↓";
  const kindPill = {
    term: { color: "text-violet-400 border-violet-400 bg-violet-400/10", label: "term" },
    rule: { color: "text-pink-400 border-pink-400 bg-pink-400/10", label: "rule" },
    action: { color: "text-orange-400 border-orange-400 bg-orange-400/10", label: "action" },
  }[row.kind];
  return (
    <div className={cn("flex items-center gap-2 py-1 px-2 rounded", indent, bg)}>
      {arrow && <span className="text-muted-foreground">{arrow}</span>}
      <span className={cn("text-[10px] px-1 rounded border", kindPill.color)}>{kindPill.label}</span>
      <span className="font-mono text-[11.5px]">{row.label}</span>
      <span
        className={cn(
          "ml-auto text-[11px]",
          row.hard ? "text-destructive font-semibold" : "text-muted-foreground",
        )}
      >
        {row.note}
      </span>
    </div>
  );
}
