"use client";

/**
 * Gate II — bundle_prepared.
 * Java body + Python 변환 + fixture 표 + entity schema. 사용자는 [실행] / [재합성].
 */

import { useState } from "react";
import { Package, Play, RefreshCw, Code2, ArrowRight, FileCode2, Edit3, Lightbulb } from "lucide-react";
import type { GateBundle } from "@/lib/section3/multiturn";
import { ProvenanceRow } from "./ProvenanceBadge";
import { CodeViewerDrawer } from "./CodeViewerDrawer";
import { TryModificationTab } from "./TryModificationTab";
import { ModificationGuidePanel } from "./ModificationGuidePanel";

interface Props {
  payload: GateBundle;
  turn_no: number;
  pending: boolean;
  isLast: boolean;
  repoId: string;
  onProceed: () => void;
}

type Tab = "java" | "python" | "fixtures" | "schema" | "idioms" | "try-mod";

export function GateBundleCard(p: Props) {
  const [tab, setTab] = useState<Tab>("python");
  const [viewerOpen, setViewerOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const conf = p.payload.confidence;
  const confColor =
    conf >= 0.7 ? "text-emerald-600" :
    conf >= 0.4 ? "text-amber-600" : "text-rose-600";

  return (
    <div className="border border-border rounded-lg bg-card p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <Package size={14} className="text-primary" />
            <span className="text-sm font-semibold">Gate II — 번들 준비</span>
            <span className="text-[10px] text-muted-foreground">turn {p.turn_no}</span>
          </div>
          <div className="mt-1.5 text-[11px] font-mono text-muted-foreground truncate">
            {p.payload.target.code_method_fqn}
          </div>
          <div className="flex items-center gap-3 mt-1">
            <button
              type="button"
              onClick={() => setViewerOpen(true)}
              className="text-[10px] inline-flex items-center gap-1 text-primary hover:underline"
            >
              <FileCode2 size={10} /> legacy 원본 + 변환 코드 보기
            </button>
            <button
              type="button"
              onClick={() => setGuideOpen(true)}
              className="text-[10px] inline-flex items-center gap-1 text-amber-600 hover:underline"
            >
              <Lightbulb size={10} /> 수정 가이드
            </button>
          </div>
        </div>
        <div className={`text-[11px] font-semibold ${confColor}`}>
          신뢰도 {Math.round(conf * 100)}%
        </div>
      </div>

      {/* tabs */}
      <div className="flex items-center gap-1 mb-2 border-b border-border">
        <TabBtn active={tab === "python"} onClick={() => setTab("python")}>
          Python ({p.payload.python_source ? "✓" : "—"})
        </TabBtn>
        <TabBtn active={tab === "java"} onClick={() => setTab("java")}>
          Java ({p.payload.java_source ? "✓" : "—"})
        </TabBtn>
        <TabBtn active={tab === "fixtures"} onClick={() => setTab("fixtures")}>
          Fixtures ({p.payload.fixtures.length})
        </TabBtn>
        <TabBtn active={tab === "schema"} onClick={() => setTab("schema")}>
          Schema ({p.payload.schema_summary.fields.length})
        </TabBtn>
        <TabBtn active={tab === "idioms"} onClick={() => setTab("idioms")}>
          Idiom diff ({p.payload.idiom_diffs.length})
        </TabBtn>
        <TabBtn active={tab === "try-mod"} onClick={() => setTab("try-mod")}>
          <span className="inline-flex items-center gap-1">
            <Edit3 size={10} /> 수정 시뮬
          </span>
        </TabBtn>
      </div>

      {/* tab body */}
      <div className="text-[11px]">
        {tab === "java" && (
          <pre className="bg-muted/60 rounded p-2 max-h-72 overflow-auto font-mono">
            {p.payload.java_source || <span className="text-muted-foreground italic">empty — ontology body 부재</span>}
          </pre>
        )}
        {tab === "python" && (
          <pre className="bg-muted/60 rounded p-2 max-h-72 overflow-auto font-mono">
            {p.payload.python_source || <span className="text-muted-foreground italic">empty — W75 변환 실패</span>}
          </pre>
        )}
        {tab === "fixtures" && (
          <FixtureTable fixtures={p.payload.fixtures} />
        )}
        {tab === "schema" && (
          <SchemaTable summary={p.payload.schema_summary} />
        )}
        {tab === "idioms" && (
          <IdiomDiffTable diffs={p.payload.idiom_diffs} />
        )}
        {tab === "try-mod" && (
          <TryModificationTab bundle={p.payload} repoId={p.repoId} />
        )}
      </div>

      {/* actions */}
      {p.isLast && (
        <div className="flex items-center justify-end gap-2 mt-3 pt-3 border-t border-border/50">
          <button
            onClick={p.onProceed}
            disabled={p.pending || !p.payload.python_source}
            className="inline-flex items-center gap-1 text-[12px] bg-primary text-primary-foreground px-3 py-1.5 rounded hover:bg-primary/90 disabled:opacity-50"
          >
            <Play size={12} /> 실행 (Gate III)
          </button>
        </div>
      )}

      <ProvenanceRow sources={p.payload.sources} />

      {viewerOpen && (
        <CodeViewerDrawer
          open
          fqn={p.payload.target.code_method_fqn}
          repoId={p.repoId}
          location={p.payload.target.location}
          preloadedBody={p.payload.java_source || null}
          preloadedPython={p.payload.python_source || null}
          onClose={() => setViewerOpen(false)}
        />
      )}
      {guideOpen && (
        <ModificationGuidePanel
          open
          fqn={p.payload.target.code_method_fqn}
          repoId={p.repoId}
          onClose={() => setGuideOpen(false)}
        />
      )}
    </div>
  );
}

function TabBtn(props: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={props.onClick}
      className={`px-2 py-1 text-[11px] border-b-2 transition-colors ${
        props.active
          ? "border-primary text-primary font-medium"
          : "border-transparent text-muted-foreground hover:text-foreground"
      }`}
    >
      {props.children}
    </button>
  );
}

function FixtureTable({ fixtures }: { fixtures: GateBundle["fixtures"] }) {
  if (fixtures.length === 0) {
    return <p className="text-muted-foreground italic p-2">empty — W71 fixture 합성 없음</p>;
  }
  const argKeys = Array.from(
    new Set(fixtures.flatMap((f) => Object.keys(f.args))),
  );
  return (
    <div className="overflow-auto max-h-64 border border-border rounded">
      <table className="text-[11px] w-full">
        <thead className="bg-muted sticky top-0">
          <tr>
            <th className="px-2 py-1 text-left font-medium">fixture_id</th>
            {argKeys.map((k) => (
              <th key={k} className="px-2 py-1 text-left font-medium font-mono">
                {k}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fixtures.map((f) => (
            <tr key={f.fixture_id} className="border-t border-border">
              <td className="px-2 py-1 font-mono">{f.fixture_id}</td>
              {argKeys.map((k) => (
                <td key={k} className="px-2 py-1 font-mono text-muted-foreground">
                  {f.args[k] === undefined
                    ? "—"
                    : f.args[k] === null
                      ? "null"
                      : JSON.stringify(f.args[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IdiomDiffTable({ diffs }: { diffs: GateBundle["idiom_diffs"] }) {
  if (diffs.length === 0) {
    return (
      <p className="text-muted-foreground italic p-2">
        W75 idiom rewrite 0건 — body 가 Java idiom (`s.length()`, `List.add`, `Math.abs` 등) 을 사용하지 않거나 body 부재.
      </p>
    );
  }
  return (
    <div className="overflow-auto max-h-64 border border-border rounded">
      <table className="text-[11px] w-full">
        <thead className="bg-muted sticky top-0">
          <tr>
            <th className="px-2 py-1 text-left font-medium">idiom</th>
            <th className="px-2 py-1 text-left font-medium">Java</th>
            <th className="px-2 py-1 text-center font-medium w-6"></th>
            <th className="px-2 py-1 text-left font-medium">Python</th>
          </tr>
        </thead>
        <tbody>
          {diffs.map((d, i) => (
            <tr key={`${d.idiom_name}-${i}`} className="border-t border-border">
              <td className="px-2 py-1 font-mono text-primary/80">{d.idiom_name}</td>
              <td className="px-2 py-1 font-mono text-muted-foreground">{d.java_snippet}</td>
              <td className="px-2 py-1 text-center text-muted-foreground">
                <ArrowRight size={11} className="inline" />
              </td>
              <td className="px-2 py-1 font-mono">{d.python_snippet}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SchemaTable({ summary }: { summary: GateBundle["schema_summary"] }) {
  if (!summary.entity_name) {
    return (
      <p className="text-muted-foreground italic p-2">
        entity schema 부재 — Section 2 API 미연결 (Phase 4 swap 후 surface).
        Q5 비전: "빠진 내용은 빠진대로".
      </p>
    );
  }
  return (
    <div className="overflow-auto max-h-64 border border-border rounded">
      <div className="bg-muted px-2 py-1 text-[11px] font-semibold flex items-center gap-1">
        <Code2 size={11} /> {summary.entity_name}
      </div>
      <table className="text-[11px] w-full">
        <thead className="bg-muted/40">
          <tr>
            <th className="px-2 py-1 text-left font-medium">name</th>
            <th className="px-2 py-1 text-left font-medium">type</th>
            <th className="px-2 py-1 text-left font-medium">nullable</th>
          </tr>
        </thead>
        <tbody>
          {summary.fields.map((f) => (
            <tr key={f.name} className="border-t border-border">
              <td className="px-2 py-1 font-mono">{f.name}</td>
              <td className="px-2 py-1 font-mono text-muted-foreground">{f.type_name}</td>
              <td className="px-2 py-1">{f.nullable ? "Y" : "N"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
