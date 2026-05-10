"use client";

import { Fragment, useEffect, useState } from "react";
import { History, Loader2, RefreshCw, Star, StarOff } from "lucide-react";
import {
  getRun,
  listRuns,
  registerBaseline,
  type RunRecord,
} from "@/lib/simulation/storageApi";
import { getStepLabel } from "@/lib/simulation/stepLabels";
import { HelpPopover } from "./HelpPopover";
import { OntologyEvidenceToggle } from "./OntologyEvidencePanel";

/** step_id → action_fqn 매핑 (옛 storage API 의 step_id 를 ontology action 으로). */
const STEP_TO_ACTION: Record<string, string> = {
  pipeline_full: "action.scm.슬랩설계_실행",
  pipeline: "action.scm.슬랩설계_실행",
  thickness: "action.scm.슬랩설계_실행",
  width_range: "action.scm.슬랩설계_실행",
  length_range: "action.scm.슬랩설계_실행",
  second_wgt: "action.scm.슬랩설계_실행",
  max_split: "action.scm.슬랩설계_실행",
  split_range: "action.scm.슬랩설계_실행",
  slab_count: "action.scm.슬랩설계_실행",
  slab_weight: "action.scm.슬랩설계_실행",
  final_width_range: "action.scm.슬랩설계_실행",
  final_length_range: "action.scm.슬랩설계_실행",
  target_size: "action.scm.슬랩설계_실행",
  validator: "action.scm.슬랩설계_실행",
  productivity: "action.scm.슬랩설계_실행",
};

function resolveActionFqn(stepId: string | null | undefined): string | undefined {
  if (!stepId) return undefined;
  return STEP_TO_ACTION[stepId] ?? "action.scm.슬랩설계_실행";
}

interface Props {
  onSelectForRegression?: (run: RunRecord) => void;
}

const STAGE_TONE: Record<string, string> = {
  ok: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  validate: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  algorithm: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300",
  data_integrity: "border-purple-500/30 bg-purple-500/10 text-purple-700 dark:text-purple-300",
};

export function RunHistoryPanel({ onSelectForRegression }: Props = {}) {
  const [items, setItems] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [onlyBaseline, setOnlyBaseline] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const toggleExpand = async (run: RunRecord) => {
    if (expanded === run.id) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    setExpanded(run.id);
    setDetail(null);
    setDetailLoading(true);
    try {
      const full = await getRun(run.id);
      setDetail(full);
    } catch (e) {
      setErr(String(e));
    } finally {
      setDetailLoading(false);
    }
  };

  const refresh = async () => {
    setLoading(true);
    setErr(null);
    try {
      const items = await listRuns({ onlyBaseline, limit: 100 });
      setItems(items);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onlyBaseline]);

  const onSetBaseline = async (run: RunRecord) => {
    if (!run.scenario_id) {
      alert("이 실행은 시나리오에 묶여있지 않아 \"기준 결과\"로 저장할 수 없습니다.");
      return;
    }
    try {
      await registerBaseline(run.scenario_id, run.id);
      await refresh();
    } catch (e) {
      alert(String(e));
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
          <History size={20} className="text-primary" />
          실행 이력
          <HelpPopover
            title="실행 이력 — 무엇을 하는가"
            body={
              <>
                <p>모든 안전 가상 실행 결과가 자동 기록됩니다 (실행 ID / 입력 / 결과 / 단계 / 오류 코드 / 소요시간).</p>
                <p>★ 노란 별 = <b>기준 결과 (baseline)</b>. 어느 실행을 「기준 결과」로 저장하면, 같은 시나리오를 다시 돌릴 때 시스템이 자동으로 「기준이랑 뭐가 달라졌는지」 비교해 줍니다.</p>
                <p>4초마다 자동 갱신. 「기준 결과」 저장은 시나리오에 묶인 실행만 가능합니다.</p>
              </>
            }
          />
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          모든 실행 기록 (4초마다 자동 갱신). 별표(★) 가 「기준 결과」 표시. 차이 비교로 바로 넘기기.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={refresh}
          disabled={loading}
          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-muted"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          새로고침
        </button>
        <label className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={onlyBaseline}
            onChange={(e) => setOnlyBaseline(e.target.checked)}
            className="accent-primary"
          />
          기준 결과만 보기
        </label>
        <span className="text-xs text-muted-foreground ml-auto">{items.length} 건</span>
      </div>

      {err && (
        <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {err}
        </div>
      )}

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-muted/40">
            <tr className="text-left">
              <th className="px-2 py-2 font-medium">시작</th>
              <th className="px-2 py-2 font-medium">step</th>
              <th className="px-2 py-2 font-medium">scenario</th>
              <th className="px-2 py-2 font-medium">stage</th>
              <th className="px-2 py-2 font-medium text-right">elapsed</th>
              <th className="px-2 py-2 font-medium">action</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => {
              const tone = STAGE_TONE[r.stage ?? ""] ?? "border-border bg-muted/30 text-muted-foreground";
              const ts = r.started_at ? r.started_at.replace("T", " ").slice(0, 19) : "—";
              const isOpen = expanded === r.id;
              return (
                <Fragment key={r.id}>
                  <tr className="border-t border-border hover:bg-muted/20">
                    <td className="px-2 py-1.5 font-mono text-[10px] text-muted-foreground">{ts}</td>
                    <td className="px-2 py-1.5 text-[11px]">
                      <div className="text-foreground">{getStepLabel(r.step_id)}</div>
                      <div className="font-mono text-[10px] text-muted-foreground/70">{r.step_id}</div>
                    </td>
                    <td className="px-2 py-1.5 font-mono text-[10px] text-muted-foreground truncate max-w-[120px]">
                      {r.scenario_id ?? "—"}
                    </td>
                    <td className="px-2 py-1.5">
                      <span className={`inline-block rounded border px-1.5 py-0.5 text-[10px] ${tone}`}>
                        {r.stage ?? "—"}
                      </span>
                      {r.error_code && (
                        <span className="ml-1 text-[10px] font-mono text-red-600">{r.error_code}</span>
                      )}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                      {r.elapsed_ms != null ? `${r.elapsed_ms}ms` : "—"}
                    </td>
                    <td className="px-2 py-1.5">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => toggleExpand(r)}
                          className={`rounded border px-1.5 py-0.5 text-[10px] ${
                            isOpen ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:bg-muted"
                          }`}
                          title="입력값/결과 JSON 펼치기"
                        >
                          {isOpen ? "▼ 닫기" : "▶ 상세"}
                        </button>
                        <button
                          onClick={() => onSetBaseline(r)}
                          className={`inline-flex items-center gap-0.5 rounded border px-1.5 py-0.5 text-[10px] ${
                            r.is_baseline
                              ? "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300"
                              : "border-border text-muted-foreground hover:bg-muted"
                          }`}
                          title="기준 결과 등록 / 해제 (시나리오 묶임 필요)"
                        >
                          {r.is_baseline ? <Star size={10} /> : <StarOff size={10} />}
                          기준
                        </button>
                        {onSelectForRegression && (
                          <button
                            onClick={() => onSelectForRegression(r)}
                            className="rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted"
                          >
                            비교
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {isOpen && (
                    <tr key={`${r.id}-detail`} className="border-t border-border bg-muted/30">
                      <td colSpan={6} className="p-3">
                        {detailLoading ? (
                          <div className="text-xs text-muted-foreground flex items-center gap-1">
                            <Loader2 size={12} className="animate-spin" /> 로딩 중...
                          </div>
                        ) : detail ? (
                          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                            <div>
                              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
                                📥 입력 (inputs)
                              </div>
                              <pre className="rounded bg-background border border-border p-2 text-[10px] overflow-auto max-h-72 font-mono">
{JSON.stringify(detail.inputs ?? {}, null, 2)}
                              </pre>
                            </div>
                            <div>
                              <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
                                📤 결과 (outputs)
                              </div>
                              <pre className="rounded bg-background border border-border p-2 text-[10px] overflow-auto max-h-72 font-mono">
{JSON.stringify(detail.outputs ?? {}, null, 2)}
                              </pre>
                            </div>
                            <div className="lg:col-span-2 text-[11px] text-muted-foreground space-x-3">
                              <span><b>run_id:</b> <code>{detail.id}</code></span>
                              {detail.parent_run_id && (
                                <span><b>parent:</b> <code>{detail.parent_run_id}</code></span>
                              )}
                              {detail.is_baseline && (
                                <span className="text-amber-600 dark:text-amber-300 font-medium">★ 기준 결과</span>
                              )}
                            </div>
                            <div className="lg:col-span-2">
                              <OntologyEvidenceToggle
                                actionFqn={resolveActionFqn(detail.step_id)}
                                label={`📚 이 run 의 온톨로지 근거 (${detail.step_id} → ${resolveActionFqn(detail.step_id)})`}
                              />
                            </div>
                          </div>
                        ) : (
                          <div className="text-xs text-muted-foreground">상세 정보 없음</div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {items.length === 0 && !loading && (
              <tr><td colSpan={6} className="px-2 py-6 text-center text-muted-foreground">실행 이력 없음</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
