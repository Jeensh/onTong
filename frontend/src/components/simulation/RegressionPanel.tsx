"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  GitCompare,
  Loader2,
  Minus,
  Plus,
  XCircle,
} from "lucide-react";
import {
  listRuns,
  regressionDiff,
  type RegressionResult,
  type RunRecord,
} from "@/lib/simulation/storageApi";
import { getStepLabel } from "@/lib/simulation/stepLabels";
import { HelpPopover } from "./HelpPopover";
import { OntologyEvidenceToggle } from "./OntologyEvidencePanel";

export function RegressionPanel() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [baselineId, setBaselineId] = useState<string>("");
  const [candidateId, setCandidateId] = useState<string>("");
  const [diff, setDiff] = useState<RegressionResult | null>(null);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    listRuns({ limit: 100 }).then(setRuns).catch((e) => setErr(String(e)));
  }, []);

  const onCompare = async () => {
    if (!baselineId || !candidateId) {
      setErr("기준 결과(baseline) 와 비교 대상(candidate) 두 실행을 모두 선택하세요.");
      return;
    }
    setRunning(true);
    setErr(null);
    try {
      const r = await regressionDiff(baselineId, candidateId);
      setDiff(r);
    } catch (e) {
      setErr(String(e));
    } finally {
      setRunning(false);
    }
  };

  const baselineOptions = runs.filter((r) => r.is_baseline);
  const allOptions = runs;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
          <GitCompare size={20} className="text-primary" />
          재실행 비교 (차이 검증)
          <HelpPopover
            title="재실행 비교 — 무엇을 하는가"
            body={
              <>
                <p>두 실행 결과의 모든 출력 필드를 <b>하나하나</b> 비교합니다. 중첩된 값도 풀어서 경로 (예: <code>slab.slabThickness</code>) 단위로 변경을 표시.</p>
                <p>차이 0건 → 회귀 없음 (안전). 차이 1건 이상 → 변경된 부분 즉시 강조.</p>
                <p>비교 결과는 양방향 추적 그래프(lineage) 에 자동 기록 → 나중에 「언제 깨졌나」 추적 가능.</p>
              </>
            }
          />
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          기준 결과 (baseline) 와 비교 대상 실행 (candidate) 의 출력을 필드 단위로 비교. 변경된 필드, 단계, 오류 코드까지 표시.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-foreground mb-1">기준 결과 (baseline)</label>
            <select
              value={baselineId}
              onChange={(e) => setBaselineId(e.target.value)}
              className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs font-mono"
            >
              <option value="">— 선택 —</option>
              {baselineOptions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id.slice(0, 16)} · {getStepLabel(r.step_id)} · {r.started_at?.slice(0, 19)}
                </option>
              ))}
            </select>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              「기준 결과」로 표시된 실행만 표시 ({baselineOptions.length}건). 실행 이력 화면에서 등록.
            </p>
          </div>
          <div>
            <label className="block text-xs font-medium text-foreground mb-1">비교 대상 실행 (candidate)</label>
            <select
              value={candidateId}
              onChange={(e) => setCandidateId(e.target.value)}
              className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs font-mono"
            >
              <option value="">— 선택 —</option>
              {allOptions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id.slice(0, 16)} · {getStepLabel(r.step_id)} · {r.stage ?? "—"}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button
          onClick={onCompare}
          disabled={running || !baselineId || !candidateId}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {running ? <Loader2 size={14} className="animate-spin" /> : <GitCompare size={14} />}
          비교 실행
        </button>

        {err && (
          <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {err}
          </div>
        )}
      </div>

      {diff && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <div className="flex items-center gap-3 text-xs">
            <span className="font-medium">변경 필드 {diff.summary.diff_count}건</span>
            {diff.summary.stage_changed && (
              <span className="inline-flex items-center gap-0.5 rounded border border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300 px-1.5 py-0.5">
                stage 변경
              </span>
            )}
            {diff.summary.error_code_changed && (
              <span className="inline-flex items-center gap-0.5 rounded border border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300 px-1.5 py-0.5">
                error code 변경
              </span>
            )}
            {diff.summary.diff_count === 0 && (
              <span className="inline-flex items-center gap-0.5 text-emerald-700 dark:text-emerald-300">
                <CheckCircle2 size={12} /> 결과 동일
              </span>
            )}
          </div>

          <OntologyEvidenceToggle
            actionFqn="action.scm.슬랩설계_실행"
            label={`📚 비교 대상 단계의 온톨로지 근거 (${diff.baseline.step_id} ↔ ${diff.candidate?.step_id ?? "?"})`}
          />

          {diff.summary.field_diffs.length > 0 && (
            <div className="border border-border rounded overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-muted/30">
                  <tr className="text-left">
                    <th className="px-2 py-1.5 font-medium">field</th>
                    <th className="px-2 py-1.5 font-medium">before</th>
                    <th className="px-2 py-1.5 font-medium">after</th>
                  </tr>
                </thead>
                <tbody>
                  {diff.summary.field_diffs.map((f, i) => (
                    <tr key={i} className="border-t border-border">
                      <td className="px-2 py-1.5 font-mono text-[10px] text-muted-foreground">{f.path}</td>
                      <td className="px-2 py-1.5 font-mono text-[11px] text-red-700 dark:text-red-300 break-all">
                        <span className="inline-flex items-start gap-0.5">
                          <Minus size={10} className="mt-0.5 flex-shrink-0" />
                          <span>{JSON.stringify(f.before)?.slice(0, 100) ?? "null"}</span>
                        </span>
                      </td>
                      <td className="px-2 py-1.5 font-mono text-[11px] text-emerald-700 dark:text-emerald-300 break-all">
                        <span className="inline-flex items-start gap-0.5">
                          <Plus size={10} className="mt-0.5 flex-shrink-0" />
                          <span>{JSON.stringify(f.after)?.slice(0, 100) ?? "null"}</span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="pt-2 border-t border-border">
            <button
              onClick={() => setShowRaw((v) => !v)}
              className="text-xs text-primary hover:underline"
            >
              {showRaw ? "▼ 원본 JSON 숨기기" : "▶ 원본 JSON 보기 (baseline / candidate inputs · outputs)"}
            </button>

            {showRaw && (
              <div className="mt-3 space-y-3">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  <div className="rounded border border-amber-500/30 bg-amber-500/5 p-2">
                    <div className="text-[10px] uppercase tracking-wide text-amber-700 dark:text-amber-300 font-medium mb-1">
                      ★ 기준 결과 (baseline) — {diff.baseline.id.slice(0, 12)}
                    </div>
                    <div className="text-[10px] text-muted-foreground mb-1">
                      step: <code>{diff.baseline.step_id}</code> · stage: <code>{diff.baseline.stage ?? "—"}</code>
                      {diff.baseline.error_code && <> · error: <code className="text-red-600">{diff.baseline.error_code}</code></>}
                    </div>
                    <div className="text-[10px] uppercase tracking-wide text-muted-foreground mt-2 mb-1">📥 inputs</div>
                    <pre className="rounded bg-background border border-border p-2 text-[10px] overflow-auto max-h-48 font-mono">
{JSON.stringify(diff.baseline.inputs ?? {}, null, 2)}
                    </pre>
                    <div className="text-[10px] uppercase tracking-wide text-muted-foreground mt-2 mb-1">📤 outputs</div>
                    <pre className="rounded bg-background border border-border p-2 text-[10px] overflow-auto max-h-48 font-mono">
{JSON.stringify(diff.baseline.outputs ?? {}, null, 2)}
                    </pre>
                  </div>
                  <div className="rounded border border-blue-500/30 bg-blue-500/5 p-2">
                    <div className="text-[10px] uppercase tracking-wide text-blue-700 dark:text-blue-300 font-medium mb-1">
                      ▶ 비교 대상 (candidate) — {diff.candidate.id.slice(0, 12)}
                    </div>
                    <div className="text-[10px] text-muted-foreground mb-1">
                      step: <code>{diff.candidate.step_id}</code> · stage: <code>{diff.candidate.stage ?? "—"}</code>
                      {diff.candidate.error_code && <> · error: <code className="text-red-600">{diff.candidate.error_code}</code></>}
                    </div>
                    <div className="text-[10px] uppercase tracking-wide text-muted-foreground mt-2 mb-1">📥 inputs</div>
                    <pre className="rounded bg-background border border-border p-2 text-[10px] overflow-auto max-h-48 font-mono">
{JSON.stringify(diff.candidate.inputs ?? {}, null, 2)}
                    </pre>
                    <div className="text-[10px] uppercase tracking-wide text-muted-foreground mt-2 mb-1">📤 outputs</div>
                    <pre className="rounded bg-background border border-border p-2 text-[10px] overflow-auto max-h-48 font-mono">
{JSON.stringify(diff.candidate.outputs ?? {}, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
