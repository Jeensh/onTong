"use client";

/**
 * Phase 11 — Try Modification tab inside GateBundleCard.
 *
 * 사용자가 Python source 를 직접 편집하고 fixture set 을 골라 in-process 실행.
 * Backend: POST /api/section3/multiturn/run-custom.
 * 결과: per-fixture invariant status + output_repr.
 */

import { useState } from "react";
import { Play, Loader2, AlertTriangle, CheckCircle2, XCircle, Edit3, Plus, Trash2 } from "lucide-react";
import type { GateBundle, FixtureRow } from "@/lib/section3/multiturn";

interface CaseResult {
  fixture_id: string;
  status: string;
  output_repr: string;
  error: string;
  elapsed_sec: number;
}

interface RunResp {
  function_name: string;
  cases: CaseResult[];
  stub_namespace_size: number;
  blocked: boolean;
  block_reason: string;
}

interface UserFixture {
  fixture_id: string;
  args_json: string;
}

export function TryModificationTab({
  bundle, repoId,
}: { bundle: GateBundle; repoId: string }) {
  const [pythonSource, setPythonSource] = useState(bundle.python_source);
  const [fixtures, setFixtures] = useState<UserFixture[]>(() =>
    bundle.fixtures.length > 0
      ? bundle.fixtures.map((f, i) => ({
          fixture_id: f.fixture_id || `fx-${i}`,
          args_json: JSON.stringify(toArgsArray(f), null, 2),
        }))
      : [{ fixture_id: "fx-1", args_json: "[]" }],
  );
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const functionName = extractFunctionName(pythonSource) || "execute";
  const declaredReturn = inferReturnType(bundle);

  const addFixture = () => {
    setFixtures([...fixtures, {
      fixture_id: `fx-${fixtures.length + 1}`,
      args_json: "[]",
    }]);
  };

  const removeFixture = (i: number) => {
    setFixtures(fixtures.filter((_, j) => j !== i));
  };

  const updateFixture = (i: number, patch: Partial<UserFixture>) => {
    setFixtures(fixtures.map((f, j) => (j === i ? { ...f, ...patch } : f)));
  };

  const run = async () => {
    setRunning(true); setErr(null); setResult(null);
    try {
      const parsed: { fixture_id: string; input_args: unknown[] }[] = [];
      for (const f of fixtures) {
        try {
          const args = JSON.parse(f.args_json);
          if (!Array.isArray(args)) {
            throw new Error(`fixture ${f.fixture_id}: args_json must be JSON array`);
          }
          parsed.push({ fixture_id: f.fixture_id, input_args: args });
        } catch (e) {
          throw new Error(`fixture ${f.fixture_id}: ${(e as Error).message}`);
        }
      }
      const r = await fetch("/api/section3/multiturn/run-custom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          python_source: pythonSource,
          function_name: functionName,
          fixtures: parsed,
          method_fqn: bundle.target.code_method_fqn,
          repo_id: repoId,
          declared_return: declaredReturn,
        }),
      });
      const body: RunResp = await r.json();
      setResult(body);
    } catch (e) {
      setErr(String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="text-[11px] text-muted-foreground">
          Python 코드를 직접 수정한 뒤, fixture 입력값을 골라 in-process 실행.
          위험한 import (<code className="font-mono">os/sys/subprocess</code> 등) 는 차단.
        </div>
        <button
          onClick={() => setPythonSource(bundle.python_source)}
          className="text-[10px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1 px-2 py-1 rounded border border-border"
        >
          <Edit3 size={10} /> 원본 복원
        </button>
      </div>

      {/* Editor */}
      <div className="border border-border rounded overflow-hidden">
        <div className="bg-muted/50 px-2 py-1 text-[11px] font-medium border-b border-border flex items-center justify-between">
          <span>Python source · function: <code className="font-mono text-primary">{functionName}</code></span>
          <span className="text-[10px] text-muted-foreground">declared_return: {declaredReturn}</span>
        </div>
        <textarea
          value={pythonSource}
          onChange={(e) => setPythonSource(e.target.value)}
          spellCheck={false}
          className="w-full bg-card text-[11px] font-mono leading-relaxed p-2 outline-none resize-vertical"
          style={{ minHeight: 180 }}
        />
      </div>

      {/* Fixtures editor */}
      <div className="border border-border rounded overflow-hidden">
        <div className="bg-muted/50 px-2 py-1 text-[11px] font-medium border-b border-border flex items-center justify-between">
          <span>Fixtures (입력값) — {fixtures.length} 건</span>
          <button
            onClick={addFixture}
            className="text-[10px] text-primary hover:underline inline-flex items-center gap-1"
          >
            <Plus size={10} /> fixture 추가
          </button>
        </div>
        <div className="p-2 space-y-2 max-h-64 overflow-auto">
          {fixtures.map((f, i) => (
            <div key={i} className="flex items-start gap-2">
              <input
                value={f.fixture_id}
                onChange={(e) => updateFixture(i, { fixture_id: e.target.value })}
                className="text-[11px] font-mono px-2 py-1 border border-border rounded w-24 bg-card"
              />
              <textarea
                value={f.args_json}
                onChange={(e) => updateFixture(i, { args_json: e.target.value })}
                placeholder='args JSON 배열 (e.g. ["A", 12])'
                className="flex-1 text-[11px] font-mono px-2 py-1 border border-border rounded bg-card"
                rows={2}
              />
              <button
                onClick={() => removeFixture(i)}
                className="p-1 text-muted-foreground hover:text-rose-600"
                aria-label="remove fixture"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Run */}
      <div className="flex items-center justify-end gap-2">
        <button
          onClick={run}
          disabled={running}
          className="inline-flex items-center gap-1 text-[12px] bg-primary text-primary-foreground px-3 py-1.5 rounded hover:bg-primary/90 disabled:opacity-50"
        >
          {running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
          실행
        </button>
      </div>

      {err && (
        <div className="text-[11px] text-rose-700 bg-rose-50 border border-rose-200 rounded p-2 flex items-start gap-2">
          <AlertTriangle size={12} className="mt-0.5 shrink-0" />
          {err}
        </div>
      )}
      {result?.blocked && (
        <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 flex items-start gap-2">
          <AlertTriangle size={12} className="mt-0.5 shrink-0" />
          차단: {result.block_reason}
        </div>
      )}
      {result && !result.blocked && (
        <div className="border border-border rounded overflow-hidden">
          <div className="bg-muted/50 px-2 py-1 text-[11px] font-medium border-b border-border">
            결과 ({result.cases.length} fixtures · stub 주입 {result.stub_namespace_size}개)
          </div>
          <table className="text-[11px] w-full">
            <thead className="bg-muted/30">
              <tr>
                <th className="px-2 py-1 text-left font-medium w-24">fixture</th>
                <th className="px-2 py-1 text-left font-medium w-32">status</th>
                <th className="px-2 py-1 text-left font-medium">output / error</th>
                <th className="px-2 py-1 text-right font-medium w-20">elapsed</th>
              </tr>
            </thead>
            <tbody>
              {result.cases.map((c) => (
                <tr key={c.fixture_id} className="border-t border-border">
                  <td className="px-2 py-1 font-mono">{c.fixture_id}</td>
                  <td className="px-2 py-1 font-mono">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-2 py-1 font-mono text-muted-foreground truncate max-w-[400px]">
                    {c.status === "PASS" ? c.output_repr : (c.error || c.output_repr)}
                  </td>
                  <td className="px-2 py-1 font-mono text-right text-muted-foreground">
                    {(c.elapsed_sec * 1000).toFixed(1)} ms
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "PASS") {
    return (
      <span className="inline-flex items-center gap-1 text-emerald-700">
        <CheckCircle2 size={11} /> PASS
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-rose-700">
      <XCircle size={11} /> {status}
    </span>
  );
}

function extractFunctionName(source: string): string | null {
  const first = source.split("\n")[0] || "";
  const m = first.match(/^\s*def\s+(\w+)\s*\(/);
  return m ? m[1] : null;
}

function toArgsArray(f: FixtureRow): unknown[] {
  // args is dict {arg0, arg1, ...} - convert to positional array
  const keys = Object.keys(f.args).filter((k) => k.startsWith("arg")).sort();
  const args = keys.map((k) => f.args[k]);
  // include kwargs as remaining named entries
  Object.keys(f.args).filter((k) => !k.startsWith("arg")).forEach((k) => {
    // skip — kwargs not supported in this simple input encoding
  });
  return args;
}

function inferReturnType(b: GateBundle): string {
  // best-effort — Python source 가 `-> Type:` annotation 없으면 Any
  const m = b.python_source.match(/->\s*([A-Za-z_][\w.\[\],\s]*)\s*:/);
  return m ? m[1].trim() : "Any";
}
