"use client";

/** executed 게이트 카드 — intent 별 차별 레이아웃. */
import React, { useEffect, useState } from "react";
import { RotateCcw, Plus, ChevronRight, ChevronDown, Loader2, Code, FileSpreadsheet, Download } from "lucide-react";
import { simulationApi, type MethodBodyView, type HypothesisResponse, type ImpactCompareResponse, type TranspiledMethod } from "@/lib/section3/simulation";
import { ExcelExportDialog } from "./ExcelExportDialog";
import { EvidenceBar } from "./EvidenceBar";
import { PipelineTimeline } from "./PipelineTimeline";
import { Q3InteractiveCard } from "./Q3InteractiveCard";
import { WalkthroughStepsCard } from "./WalkthroughStepsCard";
import { DynamicBlocksCard } from "./DynamicBlocksCard";
import { EditableBaseOrderPanel } from "./EditableBaseOrderPanel";

export type Perspective = "business" | "it";
export type ResultMode = "data_only" | "code_and_data";

interface Props {
  payload: Record<string, unknown>;
  intent: string;
  onRerun: () => void;
  onNew: () => void;
  busy: boolean;
  perspective?: Perspective;
  resultMode?: ResultMode;
  sessionId?: string;
  /** 2026-05-25 — 결과 승인 상태 lift up. SimulationChat 의 왼쪽 turn 카드가 이 값을 봐서 표시. */
  approved?: boolean;
  onApproveChange?: (approved: boolean) => void;
}

/** 결과 본문 카드 렌더 시 throw 차단 — 전체 페이지 죽지 않도록 fallback UI. */
export class ResultErrorBoundary extends React.Component<
  { name: string; children: React.ReactNode },
  { err: Error | null }
> {
  state: { err: Error | null } = { err: null };
  static getDerivedStateFromError(err: Error) { return { err }; }
  componentDidCatch(err: Error, info: React.ErrorInfo) {
    console.error(`[ResultErrorBoundary:${this.props.name}] caught:`, err, info);
  }
  render() {
    if (this.state.err) {
      return (
        <div className="border-2 border-amber-300 bg-amber-50/70 rounded-lg p-4 my-2 text-[12px] text-amber-900 sim-anim-fadein">
          <div className="font-semibold mb-1.5 flex items-center gap-2">
            <span>⚠</span><span>결과 카드 렌더 중 오류 — {this.props.name}</span>
          </div>
          <div className="text-amber-800 text-[11px] mb-2">
            backend 응답을 화면에 그리는 과정에서 예외가 발생했습니다. 다른 질문으로 다시 시도하거나 페이지를 새로고침해 주세요. (에러는 페이지 전체를 죽이지 않고 이 카드 안에서만 잡혔습니다.)
          </div>
          <details className="text-[10px] text-amber-700">
            <summary className="cursor-pointer">기술 상세 (개발용)</summary>
            <pre className="mt-1 whitespace-pre-wrap break-all bg-amber-100/60 p-2 rounded">{String(this.state.err?.message ?? this.state.err)}</pre>
            {this.state.err?.stack && (
              <pre className="mt-1 whitespace-pre-wrap break-all bg-amber-100/60 p-2 rounded">{this.state.err.stack.slice(0, 800)}</pre>
            )}
          </details>
        </div>
      );
    }
    return this.props.children;
  }
}

class _SafeView extends React.Component<
  { name: string; children: React.ReactNode },
  { err: Error | null }
> {
  state: { err: Error | null } = { err: null };
  static getDerivedStateFromError(err: Error) { return { err }; }
  componentDidCatch(err: Error, info: React.ErrorInfo) {
    console.error(`[SafeView:${this.props.name}] caught:`, err, info);
  }
  render() {
    if (this.state.err) {
      return (
        <div className="border-2 border-amber-300 bg-amber-50/60 rounded-lg p-3 text-[12px] text-amber-900">
          <div className="font-semibold mb-1">⚠ 카드 렌더 중 오류 — {this.props.name}</div>
          <div className="text-amber-800 text-[11px]">
            화면 표시 중 예외가 발생했습니다. 새 질문으로 다시 시도하거나 페이지를 새로고침해 주세요.
          </div>
          <details className="mt-2 text-[10px] text-amber-700">
            <summary className="cursor-pointer">기술 상세</summary>
            <pre className="mt-1 whitespace-pre-wrap break-all">{String(this.state.err?.message ?? this.state.err)}</pre>
          </details>
        </div>
      );
    }
    return this.props.children;
  }
}

/** 코드 카드를 어떻게 노출할지 결정.
 *
 * 2026-05-25 변경: 현업 모드도 코드/온톨로지 raw 를 *완전 hide* 가 아니라
 *   "collapsed" — 사용자가 "상세" 클릭 시 펼침. (역할 모호함 해소).
 *   - business → collapsed (기본 접힘, 상세 펼침 가능)
 *   - it + data_only → collapsed
 *   - it + code_and_data → open
 *
 * "hide" 는 더 이상 반환하지 않지만, legacy 코드와의 호환을 위해 enum 유지.
 */
export function shouldShowCode(perspective: Perspective, resultMode: ResultMode): "hide" | "collapsed" | "open" {
  if (perspective === "business") return "collapsed";
  if (resultMode === "data_only") return "collapsed";
  return "open";
}

export function ExecutedResultCard({
  payload, intent, onRerun, onNew, busy,
  perspective = "it", resultMode = "code_and_data", sessionId,
  approved: approvedProp, onApproveChange,
}: Props) {
  const error = payload.error as string | undefined;
  const codeMode = shouldShowCode(perspective, resultMode);
  const [excelOpen, setExcelOpen] = useState(false);

  const evidence = payload._evidence as {
    overall_confidence: number;
    source_breakdown_pct: Record<string, number>;
    fields: Record<string, Array<{
      kind: string; summary: string; confidence: number;
      source_ref?: string | null; detail?: string | null;
    }>>;
  } | undefined;
  // backend 2026-05-24 변경 — dict { sections, markdown }. legacy string 호환.
  const llmAnalysisRaw = payload._llm_analysis;
  const llmSections = (typeof llmAnalysisRaw === "object" && llmAnalysisRaw !== null
    ? (llmAnalysisRaw as { sections?: { heading: string; body: string }[] }).sections
    : undefined) ?? [];
  const llmAnalysisLegacy = typeof llmAnalysisRaw === "string"
    ? (llmAnalysisRaw as string).replace(/\*\*/g, "").replace(/`/g, "").replace(/^##\s*/gm, "")
    : undefined;
  const pipelineSteps = (payload._pipeline_steps as Array<{
    step_no: number; title: string; action: string; result_summary: string;
    details?: Record<string, unknown>; evidence_kind?: string; duration_hint?: string;
  }> | undefined) ?? [];
  // 21-step walkthrough — 사용자 질문 관련 step
  const walkthroughSteps = (payload._walkthrough_steps as Array<{
    step_no: number | null; phase: string; phase_label: string; title: string;
    purpose: string; formula: string; input_terms: string[]; output_field: string;
    action_fqn: string | null; base_tables: string[]; notes: string;
  }> | undefined) ?? [];
  const walkthroughInsight = payload._walkthrough_insight as string | undefined;
  // 사용자 승인 게이트 — 외부 lift up 지원. props 가 있으면 외부 state, 없으면 internal.
  const [approvedInternal, setApprovedInternal] = useState<boolean>(false);
  const approved = approvedProp ?? approvedInternal;
  const setApproved = (v: boolean) => {
    if (onApproveChange) onApproveChange(v);
    else setApprovedInternal(v);
  };

  // 2026-05-25 — clarify_form / new_standard_form submit 시 AI 분석 노출.
  // payload._dynamic_blocks 에 form type 이 있으면 사용자 액션 대기 상태.
  const dynamicBlocks = (payload._dynamic_blocks as Array<{type: string}> | undefined) ?? [];
  const hasFormBlock = dynamicBlocks.some(b =>
    b.type === "clarify_form" || b.type === "new_standard_form");
  const [formSubmitted, setFormSubmitted] = useState<boolean>(false);
  useEffect(() => {
    const handler = () => setFormSubmitted(true);
    window.addEventListener("sim:form-submitted", handler);
    return () => window.removeEventListener("sim:form-submitted", handler);
  }, []);
  // 새 session 시작 시 reset
  useEffect(() => { setFormSubmitted(false); }, [sessionId]);

  return (
    <div className="border border-gray-300 rounded-lg bg-white p-4 space-y-3 sim-stagger">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-sm font-semibold text-gray-900">실행 결과 (3/3)</h3>
        <div className="flex items-center gap-2 flex-wrap">
          <span className={"text-[10px] px-1.5 py-0.5 rounded border " + (
            perspective === "business"
              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
              : "bg-violet-50 text-violet-700 border-violet-200"
          )}>{perspective === "business" ? "현업 모드" : "IT 모드"}</span>
          <span className="text-xs text-gray-400">intent={intent}</span>
        </div>
      </header>

      {/* 🆕 신뢰도 chip — 카드 전체 + source breakdown */}
      {evidence && (
        <div className="sim-anim-fadein"><EvidenceBar evidence={evidence} /></div>
      )}

      {/* 🆕 순차 ontology 호출 timeline + 사용자 승인 게이트 */}
      {pipelineSteps.length > 0 && (
        <div className="sim-anim-fadein"><PipelineTimeline
          steps={pipelineSteps}
          approved={approved}
          onApprove={() => setApproved(true)}
          onRegenerate={() => { setApproved(false); onRerun(); }}
          regenerating={busy}
        /></div>
      )}

      {error && (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          ⚠ {error}
        </div>
      )}

      {/* 🆕 (2026-05-25) 결과 승인 후 최우선 표시 — 사용자 질문 맞춤 가변 UI.
          기존엔 결과 본문 (term/code 카드) 아래에 있었지만 사용자 의미 우선순위에 맞춰 위로 이동. */}
      {(approved || pipelineSteps.length === 0) && Array.isArray(payload._dynamic_blocks) && (payload._dynamic_blocks as unknown[]).length > 0 && (
        <DynamicBlocksCard blocks={payload._dynamic_blocks as never} />
      )}

      {/* 🆕 21-step 카탈로그 — 질문 관련 단계만 surface (승인 후) */}
      {(approved || pipelineSteps.length === 0) && walkthroughSteps.length > 0 && (
        <WalkthroughStepsCard steps={walkthroughSteps} insight={walkthroughInsight} />
      )}

      {/* 결과 본문 (term/code 등 ontology raw) — 가변 UI 다음에 보조 정보로 표시 */}
      {(approved || pipelineSteps.length === 0) && (
        <>
          {!error && payload.kind === "executed_full_design" && <_SafeView name="FullDesign"><_FullDesignView payload={payload} codeMode={codeMode} /></_SafeView>}
          {!error && payload.kind === "executed_compare" && <_SafeView name="Compare"><_CompareView payload={payload} codeMode={codeMode} /></_SafeView>}
          {!error && payload.kind === "executed_hypothesis_workflow" && <_SafeView name="HypothesisWorkflow"><_HypothesisWorkflowView payload={payload} codeMode={codeMode} /></_SafeView>}
          {!error && payload.kind === "executed_new_standard" && <_SafeView name="NewStandard"><_NewStandardView payload={payload} codeMode={codeMode} /></_SafeView>}
          {!error && payload.kind !== "executed_compare" && payload.kind !== "executed_full_design" && payload.kind !== "executed_hypothesis_workflow" && intent === "simulate" && <_SafeView name="Simulate"><_SimulateView payload={payload} codeMode={codeMode} /></_SafeView>}
          {!error && payload.kind !== "executed_compare" && payload.kind !== "executed_full_design" && intent === "impact" && <_SafeView name="Impact"><_ImpactView payload={payload} codeMode={codeMode} /></_SafeView>}
          {!error && payload.kind !== "executed_hypothesis_workflow" && intent === "locate" && <_SafeView name="Locate"><_LocateView payload={payload} codeMode={codeMode} /></_SafeView>}
          {!error && payload.kind !== "executed_hypothesis_workflow" && intent === "explain" && <_SafeView name="Explain"><_ExplainView payload={payload} codeMode={codeMode} /></_SafeView>}
          {!error
            && (payload.kind === "executed_hypothesis" || payload.kind === "executed_new_standard")
            && intent === "hypothesis"
            && <_SafeView name="Hypothesis"><_HypothesisView payload={payload} codeMode={codeMode} /></_SafeView>}
        </>
      )}

      {/* AI 분석 대기 안내 — 사용자 액션 (결과 승인 OR 폼 submit) 전엔 대기 */}
      {/* 1) pipeline 미승인 — "결과 승인" 누르라고 안내 */}
      {!approved && pipelineSteps.length > 0 && (llmSections.length > 0 || llmAnalysisLegacy) && (
        <div className="border-2 border-dashed border-amber-300 bg-amber-50/40 rounded-lg p-3 text-[11.5px] text-amber-900 sim-anim-fadein">
          <div className="font-bold mb-0.5">⏳ AI 분석 대기 중 — 결과 승인 필요</div>
          <div className="text-amber-800">위의 timeline 카드에서 <strong>[✓ 결과 승인]</strong> 을 누르세요. 승인 후 본문 카드들 + 입력 폼 → 입력 승인 → AI 분석이 표시됩니다.</div>
        </div>
      )}
      {/* 2) pipeline 승인 + 폼 있는데 폼 submit 안 됨 */}
      {(approved || pipelineSteps.length === 0) && hasFormBlock && !formSubmitted && (llmSections.length > 0 || llmAnalysisLegacy) && (
        <div className="border-2 border-dashed border-amber-300 bg-amber-50/40 rounded-lg p-3 text-[11.5px] text-amber-900 sim-anim-fadein">
          <div className="font-bold mb-0.5">⏳ AI 분석 대기 중 — 입력 폼 승인 필요</div>
          <div className="text-amber-800">
            위의 입력 폼 (🛠 시뮬 입력 / 신규 기준 입력) 에서 값을 확인·수정하고 <strong>[✓ 승인]</strong> 을 눌러주세요.
            승인된 입력값 + 가상 주문 결과 + 21-step 산식을 함께 분석한 답변이 그 후 표시됩니다.
          </div>
        </div>
      )}

      {/* 🆕 LLM 분석 카드 — 모든 의도 공통 gate: 사용자 액션 후에만 마지막 표시.
          - pipelineSteps 있으면 approved 필수
          - form 있으면 formSubmitted 필수
          - 둘 다 통과해야 노출 (모든 의도 공통). */}
      {(approved || pipelineSteps.length === 0)
        && (!hasFormBlock || formSubmitted)
        && (llmSections.length > 0 || llmAnalysisLegacy) && (
        <div className="border-2 border-indigo-300 bg-gradient-to-br from-indigo-50/60 to-blue-50/40 rounded-lg p-4 sim-anim-fadein">
          <div className="flex items-center gap-2 mb-3 flex-wrap border-b-2 border-indigo-200 pb-2">
            <span className="text-[11px] px-2 py-0.5 rounded bg-indigo-700 text-white font-bold tracking-wide">AI 분석</span>
            <span className="text-[14px] text-indigo-900 font-extrabold">왜 이런 결과가 나왔는가</span>
            <_MiniConfidenceChip evidence={evidence} />
          </div>
          {llmSections.length > 0 ? (
            <div className="space-y-3">
              {llmSections.map((s, i) => (
                <div key={i} className="bg-white rounded-lg p-3 border-l-4 border-l-indigo-500 border border-indigo-100 shadow-sm">
                  <div className="flex items-baseline gap-2 mb-2 pb-1.5 border-b border-indigo-100">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-700 text-white font-bold">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h4 className="text-[13.5px] font-extrabold text-indigo-900 tracking-tight">{s.heading}</h4>
                  </div>
                  <div className="text-[12.5px] text-gray-800 leading-[1.85] pl-1">
                    <_AnalysisBody text={s.body.replace(/\*\*/g, "").replace(/`/g, "")} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[12.5px] text-gray-800 leading-[1.85] bg-white rounded-lg p-3 border-l-4 border-l-indigo-500">
              <_AnalysisBody text={(llmAnalysisLegacy ?? "").toString()} />
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-200 flex-wrap">
        {sessionId && (
          <button
            onClick={() => setExcelOpen(true)}
            className="px-3 py-1.5 text-xs rounded border border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
            title="결과를 Excel 로 다운로드 — 컬럼명 한글+영어 동시 표기"
          >
            <FileSpreadsheet size={11} className="inline mr-1" /> Excel 추출
          </button>
        )}
        {intent === "simulate" && (
          <button onClick={onRerun} disabled={busy} className="px-3 py-1.5 text-xs rounded border border-gray-300 hover:bg-gray-50">
            <RotateCcw size={11} className="inline mr-1" /> 재실행
          </button>
        )}
        <button onClick={onNew} className="px-3 py-1.5 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-500">
          <Plus size={11} className="inline mr-1" /> 새 질문
        </button>
      </div>

      {excelOpen && sessionId && (
        <ExcelExportDialog
          sessionId={sessionId}
          payload={payload}
          intent={intent}
          onClose={() => setExcelOpen(false)}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// intent 별 sub-view
// ─────────────────────────────────────────────────────────────────────────────

function _SimulateView({ payload, codeMode = "open" }: { payload: Record<string, unknown>; codeMode?: "hide" | "collapsed" | "open" }) {
  const results = (payload.results as Array<Record<string, unknown>> | undefined) ?? [];
  const invariant = payload.invariant_status as string | undefined;
  const baselineDiff = payload.baseline_diff as Record<string, unknown> | null;

  return (
    <>
      <div className="bg-gradient-to-r from-emerald-600 to-emerald-700 text-white rounded-lg p-3">
        <div className="text-[10px] uppercase tracking-wide opacity-80">시뮬레이션 실행 결과</div>
        <div className="text-sm font-semibold mt-0.5 flex items-center justify-between">
          <span>{results.length} case 실행</span>
          <span className={
            "text-xs px-2 py-0.5 rounded " + (
              invariant === "all_pass" ? "bg-emerald-200 text-emerald-900" :
              invariant === "some_fail" ? "bg-red-200 text-red-900" :
              "bg-white/20"
            )
          }>invariant: {invariant ?? "?"}</span>
        </div>
      </div>

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {results.map((r, i) => {
          const fixtureId = String(r.fixture_id ?? `case_${i}`);
          const ok = !r.error;
          return (
            <div key={i} className={
              "border rounded p-2 " +
              (ok ? "border-emerald-200 bg-emerald-50/40" : "border-red-200 bg-red-50/40")
            }>
              <div className="flex items-center gap-2 mb-1">
                <span className={
                  "text-[10px] px-1.5 py-0.5 rounded font-semibold " +
                  (ok ? "bg-emerald-600 text-white" : "bg-red-600 text-white")
                }>{ok ? "PASS" : "FAIL"}</span>
                <code className="text-[10px] text-gray-700">{fixtureId}</code>
              </div>
              {r.input ? (
                <details className="text-[10px]">
                  <summary className="cursor-pointer text-gray-600">input 보기</summary>
                  <pre className="bg-white border border-gray-200 rounded p-1.5 mt-1 overflow-x-auto">
                    {JSON.stringify(r.input, null, 2).slice(0, 300)}
                  </pre>
                </details>
              ) : null}
              {r.output_value !== undefined && r.output_value !== null && (
                <div className="mt-1 text-[10px]">
                  <span className="text-gray-500">output: </span>
                  <code className="font-mono text-emerald-700">
                    {typeof r.output_value === "object"
                      ? JSON.stringify(r.output_value).slice(0, 120)
                      : String(r.output_value)}
                  </code>
                </div>
              )}
              {Boolean(r.error) && (
                <div className="mt-1 text-[10px] text-red-700">⚠ {String(r.error)}</div>
              )}
            </div>
          );
        })}
        {results.length === 0 && (
          <div className="text-[10px] text-gray-400 italic">실행 결과 없음 — bundle 합성/실행이 빈 결과 반환</div>
        )}
      </div>

      {baselineDiff && (
        <div className="border border-amber-200 bg-amber-50 rounded p-2">
          <div className="text-[11px] text-amber-800 font-semibold mb-1">baseline diff</div>
          <pre className="text-[10px] overflow-x-auto text-gray-800">
            {JSON.stringify(baselineDiff, null, 2).slice(0, 600)}
          </pre>
        </div>
      )}
    </>
  );
}

/** stage 4: 선택 주문 + 변경 대상 → baseline vs projected slab 비교 + Java→Python. */
function _ImpactSlabCompareCard({ table, column, before, after, order_no, affectedFqns, codeMode = "open" }: {
  table: string; column: string; before: string; after: string; order_no: string; affectedFqns: string[];
  codeMode?: "hide" | "collapsed" | "open";
}) {
  const [data, setData] = useState<ImpactCompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(null);
    simulationApi.impactCompare({
      table, column, before, after, order_no, affected_method_fqns: affectedFqns,
    })
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [table, column, before, after, order_no, affectedFqns.join("|")]);

  if (loading) return (
    <div className="text-[11px] bg-emerald-50 border border-emerald-200 rounded p-3 flex items-center gap-2">
      <Loader2 size={12} className="animate-spin text-emerald-700" />
      <span>주문 <code className="bg-white px-1 rounded">{order_no}</code> 의 변경 전/후 Slab 결과 계산 중...</span>
    </div>
  );
  if (error) return <div className="text-[11px] text-red-700 bg-red-50 border border-red-200 rounded p-2">⚠ {error}</div>;
  if (!data || !data.ok) return (
    <div className="text-[11px] bg-amber-50 border border-amber-200 rounded p-2">
      ⚠ Slab 비교 실패: {data?.error || "unknown"}
    </div>
  );

  const HIGHLIGHT = ["slabThickness", "slabWidth", "slabLength", "slabWgt", "splitCount", "designStatus"];
  const changedFields = new Set(data.diff.map((d) => d.field));

  return (
    <div className="border-2 border-emerald-300 bg-white rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-gradient-to-r from-emerald-600 to-emerald-700 text-white flex items-center gap-2">
        <span>🎯</span>
        <strong className="text-sm">변경 전·후 Slab 설계 결과 비교</strong>
        <span className="text-[10px] ml-auto opacity-80">
          {data.diff.length}개 필드 변경 · 주문 {order_no}
        </span>
      </div>

      {/* 핵심 필드 3-col */}
      <div className="grid grid-cols-3 gap-2 p-3 text-[11px]">
        <div className="border border-gray-300 rounded p-2 bg-gray-50">
          <div className="text-[9px] text-gray-500 uppercase mb-1">변경 전 (baseline)</div>
          {HIGHLIGHT.map((f) => {
            const v = data.baseline_slab?.[f];
            if (v === undefined || v === null) return null;
            return (
              <div key={f} className="font-mono">
                <span className="text-gray-500">{f}</span>{": "}
                <span className="text-gray-800 font-semibold">
                  {typeof v === "number" ? v.toLocaleString(undefined, {maximumFractionDigits: 2}) : String(v)}
                </span>
              </div>
            );
          })}
        </div>
        <div className="border border-emerald-300 rounded p-2 bg-emerald-50/40">
          <div className="text-[9px] text-emerald-700 uppercase mb-1">변경 후 (projected)</div>
          {HIGHLIGHT.map((f) => {
            const v = data.projected_slab?.[f];
            const ch = changedFields.has(f);
            if (v === undefined || v === null) return null;
            return (
              <div key={f} className="font-mono">
                <span className="text-gray-500">{f}</span>{": "}
                <span className={ch ? "text-emerald-700 font-bold" : "text-gray-700"}>
                  {typeof v === "number" ? v.toLocaleString(undefined, {maximumFractionDigits: 2}) : String(v)}
                  {ch && " ✦"}
                </span>
              </div>
            );
          })}
        </div>
        <div className="border border-amber-300 rounded p-2 bg-amber-50/40">
          <div className="text-[9px] text-amber-700 uppercase mb-1">DIFF ({data.diff.length})</div>
          {data.diff.slice(0, 8).map((d, i) => (
            <div key={i} className="font-mono">
              <span className="text-gray-500">{d.field}</span>
              <div className="text-[10px]">
                <span className="text-red-700 line-through">{String(d.before)}</span>
                <span className="mx-1 text-gray-400">→</span>
                <span className="text-emerald-700 font-bold">{String(d.after)}</span>
                {d.delta_pct !== null && (
                  <span className="ml-1 text-amber-700">({d.delta_pct > 0 ? "+" : ""}{d.delta_pct}%)</span>
                )}
              </div>
            </div>
          ))}
          {data.diff.length === 0 && <div className="text-gray-400 italic">변경 없음</div>}
        </div>
      </div>

      {/* 전체 필드 collapsible */}
      {data.projected_slab && (
        <details className="border-t border-gray-200">
          <summary className="px-3 py-1.5 text-[11px] text-gray-600 cursor-pointer hover:bg-gray-50">
            전체 Slab 필드 ({Object.keys(data.projected_slab).length}) — 변경된 필드는 ✦
          </summary>
          <div className="p-2 max-h-48 overflow-auto">
            <table className="w-full text-[10px]">
              <thead><tr className="border-b border-gray-300">
                <th className="text-left p-0.5">field</th>
                <th className="text-right p-0.5">before</th>
                <th className="text-right p-0.5">after</th>
              </tr></thead>
              <tbody>
                {Object.entries(data.projected_slab).map(([k, v]) => {
                  const ch = changedFields.has(k);
                  const b = data.baseline_slab?.[k];
                  return (
                    <tr key={k} className={"border-b border-gray-100 " + (ch ? "bg-emerald-50/40" : "")}>
                      <td className="p-0.5 font-mono">{ch ? "✦ " : ""}{k}</td>
                      <td className="p-0.5 font-mono text-right text-gray-500">
                        {b === null || b === undefined ? "—" : String(b)}
                      </td>
                      <td className={"p-0.5 font-mono text-right " + (ch ? "text-emerald-700 font-bold" : "text-gray-700")}>
                        {v === null || v === undefined ? "—" : String(v)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {/* Java → Python 변환 — 현업 모드(codeMode=hide)에서는 숨김 */}
      {data.transpiled_methods.length > 0 && codeMode !== "hide" && (
        codeMode === "collapsed" ? (
          <details className="border-t border-gray-200 p-3">
            <summary className="text-[11px] font-semibold text-gray-700 cursor-pointer">
              ⚙ 영향받는 Java 코드 → Python 실시간 변환 ({data.transpiled_methods.length}) — 클릭하여 펼치기
            </summary>
            <div className="mt-2 space-y-2">
              {data.transpiled_methods.map((m) => <_TranspiledMethodCard key={m.fqn} method={m} />)}
            </div>
          </details>
        ) : (
          <div className="border-t border-gray-200 p-3 space-y-2">
            <div className="text-[11px] font-semibold text-gray-700 flex items-center gap-1">
              ⚙ 영향받는 Java 코드 → Python 실시간 변환 ({data.transpiled_methods.length})
            </div>
            {data.transpiled_methods.map((m) => <_TranspiledMethodCard key={m.fqn} method={m} />)}
          </div>
        )
      )}

      {data.notes.length > 0 && (
        <details className="border-t border-gray-200 text-[10px]">
          <summary className="px-3 py-1.5 cursor-pointer text-gray-500">분석 노트 ({data.notes.length})</summary>
          <ul className="p-2 space-y-1">
            {data.notes.map((n, i) => <li key={i} className="text-gray-600">· {n}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
}

/** Java→Python 한 method — 2-col 코드 비교 + idiom diffs. */
function _TranspiledMethodCard({ method }: { method: TranspiledMethod }) {
  return (
    <div className="border border-gray-200 rounded">
      <div className="px-2 py-1 bg-gray-50 border-b border-gray-200 text-[10px] flex items-center gap-1">
        <code className="font-mono font-bold text-gray-800">{method.class_name}.{method.method_name}</code>
        {method.line_start && <span className="text-gray-400">L{method.line_start}-{method.line_end ?? "?"}</span>}
        {method.error && <span className="ml-auto text-red-700">⚠ {method.error}</span>}
      </div>
      <div className="grid grid-cols-2 gap-0">
        <div>
          <div className="text-[9px] text-amber-700 px-2 py-0.5 bg-amber-50 border-b border-r border-amber-200">Java (원본)</div>
          <pre className="p-2 text-[10px] max-h-48 overflow-auto bg-white border-r border-gray-200 text-gray-800">
            {method.java || "(본문 없음)"}{method.java_truncated && "\n..."}
          </pre>
        </div>
        <div>
          <div className="text-[9px] text-emerald-700 px-2 py-0.5 bg-emerald-50 border-b border-emerald-200">Python (sim_v2 변환)</div>
          <pre className="p-2 text-[10px] max-h-48 overflow-auto bg-emerald-50/30 text-emerald-900">
            {method.python || "(변환 실패)"}{method.python_truncated && "\n..."}
          </pre>
        </div>
      </div>
      {method.idiom_diffs && method.idiom_diffs.length > 0 && (
        <details className="border-t border-gray-200">
          <summary className="px-2 py-1 text-[10px] text-gray-500 cursor-pointer">idiom 변환 {method.idiom_diffs.length}건</summary>
          <ul className="px-3 pb-2 text-[10px] space-y-0.5">
            {method.idiom_diffs.map((d, i) => (
              <li key={i}>
                <code className="bg-amber-100 px-1 rounded">{String(d.idiom_name ?? "?")}</code>
                <span className="text-gray-600 ml-1">{String(d.summary ?? "")}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

/** table 별 맞춤 변경 대상 카드. CAST_SPEC, EDGING_GROUP, HR_SPEC, SD_PRODUCTIVITY_STD 등.
 *  editable=true 면 before/after 값을 사용자가 직접 입력/수정. */
function _TargetChangeCard({ targetChange, editable, onChange, onColumnChange, availableColumns, pkColumns }: {
  targetChange: Record<string, unknown>;
  editable?: boolean;
  onChange?: (next: { before: string; after: string }) => void;
  onColumnChange?: (newColumn: string) => void;
  availableColumns?: string[];
  pkColumns?: string[];
}) {
  const table = String(targetChange.table ?? "");
  const column = String(targetChange.column ?? "");
  const initialBefore = targetChange.before;
  const initialAfter = targetChange.after;
  const product = targetChange.product as string | undefined;

  const [beforeVal, setBeforeVal] = useState<string>(
    initialBefore === null || initialBefore === undefined ? "" : String(initialBefore)
  );
  const [afterVal, setAfterVal] = useState<string>(
    initialAfter === null || initialAfter === undefined ? "" : String(initialAfter)
  );

  function _updateBefore(v: string) {
    setBeforeVal(v);
    onChange?.({ before: v, after: afterVal });
  }
  function _updateAfter(v: string) {
    setAfterVal(v);
    onChange?.({ before: beforeVal, after: v });
  }

  // table 별 메타 (icon · 한국어 라벨 · 주요 컬럼 분류)
  const META: Record<string, { icon: string; ko: string; columns: string[]; color: string }> = {
    CAST_SPEC: { icon: "🏭", ko: "연주설비사양", color: "amber", columns: ["SLAB_THICKNESS","WIDTH_LOW","WIDTH_HIGH","LENGTH_LOW","LENGTH_HIGH","WGT_LOW","WGT_HIGH"] },
    HR_SPEC: { icon: "🔥", ko: "열연설비사양", color: "rose", columns: ["WIDTH_LOW","WIDTH_HIGH","LENGTH_LOW","LENGTH_HIGH"] },
    EDGING_GROUP: { icon: "📐", ko: "EDGING 그룹", color: "purple", columns: ["GROUP_CD","WIDTH_LOW","WIDTH_HIGH"] },
    HR_MAX_WGT: { icon: "⬆", ko: "열연 최대 단중", color: "rose", columns: ["THICKNESS","WIDTH","MAX_WGT"] },
    HR_MIN_WGT: { icon: "⬇", ko: "열연 최소 단중", color: "rose", columns: ["THICKNESS","WIDTH","MIN_WGT"] },
    SD_PRODUCTIVITY_STD: { icon: "📊", ko: "실수율 기준", color: "indigo", columns: ["PROC_CD","GRADE_CD","PRODUCTIVITY"] },
    CUSTOMER_STD: { icon: "👥", ko: "고객표준", color: "sky", columns: ["CUSTOMER_CD"] },
  };
  const meta = META[table] ?? { icon: "📋", ko: table, color: "amber", columns: [column] };

  return (
    <div className={`bg-${meta.color}-50 border-2 border-${meta.color}-300 rounded-lg p-3`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">{meta.icon}</span>
        <div>
          <div className={`text-[10px] uppercase text-${meta.color}-700 font-semibold tracking-wide`}>변경 대상 (기준 테이블)</div>
          <div className="text-sm font-semibold text-gray-900">
            <code className="text-[12px]">{table}</code>
            <span className="text-gray-500 text-[11px] ml-1.5">({meta.ko})</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 bg-white rounded p-2 border border-gray-200">
        <div>
          <div className="text-[9px] text-gray-500 uppercase">column</div>
          {editable && onColumnChange && (availableColumns?.length ?? 0) > 0 ? (
            <select
              value={column}
              onChange={(e) => onColumnChange(e.target.value)}
              className={`w-full text-xs px-1.5 py-0.5 border border-${meta.color}-300 rounded font-mono text-${meta.color}-800 font-bold bg-${meta.color}-50 focus:outline-none focus:border-${meta.color}-500`}
            >
              {(availableColumns ?? []).map((c) => (
                <option key={c} value={c}>
                  {pkColumns?.includes(c) ? "🔑 " : ""}{c}
                </option>
              ))}
            </select>
          ) : (
            <code className={`text-xs text-${meta.color}-800 font-bold`}>{column || "?"}</code>
          )}
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase">변경 전 (현재값)</div>
          {editable ? (
            <input
              type="text"
              value={beforeVal}
              onChange={(e) => _updateBefore(e.target.value)}
              placeholder="(seed 미존재 — 직접 입력)"
              className="w-full text-xs px-1.5 py-0.5 border border-gray-300 rounded font-mono text-gray-800 focus:outline-none focus:border-amber-500"
            />
          ) : (
            <code className="text-xs text-gray-700">{beforeVal || "(seed 미존재)"}</code>
          )}
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase">변경 후</div>
          {editable ? (
            <input
              type="text"
              value={afterVal}
              onChange={(e) => _updateAfter(e.target.value)}
              placeholder="값 입력"
              className={`w-full text-xs px-1.5 py-0.5 border border-red-300 rounded font-mono text-red-700 font-bold focus:outline-none focus:border-red-500`}
            />
          ) : (
            <code className={`text-xs text-red-700 font-bold`}>{afterVal || "?"}</code>
          )}
        </div>
      </div>
      {editable && (
        <div className="text-[10px] text-gray-500 mt-1.5 italic">
          💡 자연어에서 추출한 값이 부정확하거나 비어있으면 직접 수정해 주세요. "다음" 진행 시 입력값 기반으로 영향 분석합니다.
        </div>
      )}

      {product && (
        <div className="mt-2 text-[10px] text-gray-600">
          <span className="text-gray-500">scope: </span>
          <code className="bg-white px-1.5 py-0.5 rounded border border-gray-200">PRODUCT_CD = {product}</code>
        </div>
      )}

      {/* table 의 주요 컬럼 hint */}
      <details className="mt-2 text-[10px]">
        <summary className="cursor-pointer text-gray-500">이 테이블의 주요 컬럼 ({meta.columns.length})</summary>
        <div className="mt-1 flex flex-wrap gap-1">
          {meta.columns.map((c) => (
            <code key={c} className={
              "text-[9px] px-1.5 py-0.5 rounded border " +
              (c === column ? `bg-${meta.color}-200 border-${meta.color}-400 font-bold` : "bg-white border-gray-200 text-gray-600")
            }>{c}</code>
          ))}
        </div>
      </details>

      {Boolean(targetChange.note) && (
        <div className="text-[10px] text-gray-600 mt-2 italic">{String(targetChange.note)}</div>
      )}
    </div>
  );
}


function _ImpactView({ payload, codeMode = "open" }: { payload: Record<string, unknown>; codeMode?: "hide" | "collapsed" | "open" }) {
  const methods = (payload.affected_methods as Array<Record<string, unknown>> | undefined) ?? [];
  const confidence = (payload.confidence as number | undefined) ?? 0;
  const detectedTerms = (payload._detected_terms as Array<Record<string, unknown>> | undefined) ?? [];
  const targetChange = payload._target_change as Record<string, unknown> | undefined;
  const affectedOrders = (payload._affected_orders as Array<Record<string, unknown>> | undefined) ?? [];
  const affectedOrdersColumns = (payload._affected_orders_columns as string[] | undefined)
    ?? ["ORDER_NO", "GRADE_CD", "PRODUCT_CD", "ORDER_WIDTH", "DESIGN_PEND_QTY"];
  const affectedOrdersSynthesisNote = payload._affected_orders_synthesis as string | undefined;
  const affectedRules = (payload._affected_rules as Array<Record<string, unknown>> | undefined) ?? [];
  const affectedSteps = (payload._affected_steps as Array<Record<string, unknown>> | undefined) ?? [];
  const affectedActions = (payload._affected_actions as Array<Record<string, unknown>> | undefined) ?? [];
  const affectedApis = (payload._affected_apis as Array<Record<string, unknown>> | undefined) ?? [];
  const intentFocus = (payload._intent_focus as string) || "code";
  // 🆕 Q2 — Edging 능력 상하한 변경 영향
  const edgingImpact = payload._edging_impact as {
    title: string; purpose: string;
    base_edging: { HR_TGT_WIDTH_LOW: number; HR_TGT_WIDTH_HIGH: number };
    external_constraints: Record<string, number>;
    scenarios: {
      label: string; new_low: number; new_high: number;
      effective_low: number; effective_high: number; effective_range: number;
      range_change_pct: number; avg_width: number; weight_change_pct: number;
      max_wgt_change_pct?: number; min_wgt_change_pct?: number;
      feasible: boolean; binding_constraint?: string; edging_active?: boolean;
      warning: string | null;
    }[];
    core_logic: string; insight?: string; note: string;
  } | undefined;
  // 🆕 Q3 interactive — 가상 주문 + 사용자 입력 4-stage (사용자 명시 2026-05-23)
  const q3Interactive = payload._q3_interactive as {
    virtual_order: Record<string, unknown>;
    constraints: { HR_MAX_WGT: number; HR_MIN_WGT: number };
    ontology_basis: string[];
    default_before: { ORDER_WGT_LOW: number; ORDER_WGT_HIGH: number; DESIGN_PEND_QTY: number };
    default_after_hint: { ORDER_WGT_LOW: number; ORDER_WGT_HIGH: number; DESIGN_PEND_QTY: number };
  } | undefined;
  // 🆕 Q3 — 포장단중·설계대기량 sweep (auto, q3 interactive 없을 때 fallback)
  const weightSweep = payload._weight_sweep as {
    base_order: Record<string, unknown>;
    sweep_variables: string[];
    var_ranges: Record<string, [number, number]>;
    grid: { vars: Record<string, number>; projected_split_count: number; projected_slab_wgt: number; feasible: boolean; violations: string[] }[];
    best: { vars: Record<string, number>; projected_split_count: number; projected_slab_wgt: number } | null;
    total_cells: number; feasible_cells: number; summary: string;
  } | undefined;

  // ── Progressive disclosure stages ─────────────────────────────────────────
  // stage 1: 변경 대상 확인  (target_change 가 있을 때만)
  // stage 2: 매칭 주문 선택 (affected_orders 있을 때만)
  // stage 3: 영향 결과 표시
  // 변경 대상 없으면 1을 skip, 주문 없으면 2를 skip → 3 직진
  const hasTarget = !!targetChange;
  const hasOrders = affectedOrders.length > 0;
  const targetRows = (payload._target_table_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const targetMeta = payload._target_table_meta as { pk_columns?: string[]; columns?: string[]; description?: string } | undefined;
  const hasTargetRows = targetRows.length > 0;

  // ── 4-stage flow ──
  //   1: 기준 row 선택 (해당 table 의 seed rows)
  //   2: 변경 전·후 입력
  //   3: 매칭 주문 선택
  //   4: 영향 결과
  // hasTargetRows=false 면 stage 1 skip → 2 부터, hasOrders=false 면 stage 3 skip → 4
  // Q3 일 때는 Q3InteractiveCard 가 본문 → 외부 stage 흐름은 skip 해 stage 4 로 직진
  // Q2(Edging) 일 때도 stage 3 가상주문 선택 후 → stage 4 의 결과 카드를 새로 띄움
  const initialStage: 1 | 2 | 3 | 4 = q3Interactive
    ? 4
    : hasTargetRows ? 1 : hasTarget ? 2 : hasOrders ? 3 : 4;
  const [stage, setStage] = useState<1 | 2 | 3 | 4>(initialStage);
  const [pickedRowIdx, setPickedRowIdx] = useState<number | null>(null);
  const [pickedOrder, setPickedOrder] = useState<string | null>(null);
  // 사용자가 입력한 변경 전·후 (stage 2 에서 editable)
  const [userChange, setUserChange] = useState<{ before: string; after: string }>({
    before: String(targetChange?.before ?? ""),
    after: String(targetChange?.after ?? ""),
  });

  // 선택된 기준 row → before 값 자동 채움
  const pickedRow = pickedRowIdx !== null ? targetRows[pickedRowIdx] : null;
  // 사용자가 stage 1·2 에서 column 을 자유롭게 바꿀 수 있도록 별도 state.
  // backend 추출이 "?" 이거나 부정확할 때 dropdown / 헤더클릭으로 override.
  const initialCol = (() => {
    const c = String(targetChange?.column ?? "");
    if (c && c !== "?") return c;
    // 변경 대상 자동: pk 가 아닌 첫 컬럼
    const cols = targetMeta?.columns ?? Object.keys(targetRows[0] ?? {});
    const pk = new Set(targetMeta?.pk_columns ?? []);
    return cols.find((c) => !pk.has(c)) ?? cols[0] ?? "";
  })();
  const [pickedCol, setPickedCol] = useState<string>(initialCol);
  const targetCol = pickedCol;
  const targetColumns: string[] = targetMeta?.columns ?? Object.keys(targetRows[0] ?? {});

  // column 변경 시 — 선택된 row 가 있으면 그 row 의 새 column 값으로 before 갱신
  function pickColumn(newCol: string) {
    setPickedCol(newCol);
    if (pickedRow) {
      const v = pickedRow[newCol];
      setUserChange((s) => ({
        ...s,
        before: v === null || v === undefined ? "" : String(v),
      }));
    } else {
      setUserChange((s) => ({ ...s, before: "" }));
    }
  }

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (fqn: string) => {
    setExpanded((s) => {
      const n = new Set(s);
      n.has(fqn) ? n.delete(fqn) : n.add(fqn);
      return n;
    });
  };

  // 단계별 안내 stepper
  const stepperLabels = [
    hasTargetRows ? "1. 기준 row 선택" : null,
    hasTarget ? "2. 변경 전/후 입력" : null,
    hasOrders ? "3. 가상 주문 선택" : null,
    "4. 영향 결과",
  ].filter(Boolean) as string[];
  const currentStepIdx = (() => {
    let idx = 0;
    if (hasTargetRows) { if (stage === 1) return idx; idx++; }
    if (hasTarget) { if (stage === 2) return idx; idx++; }
    if (hasOrders) { if (stage === 3) return idx; idx++; }
    return idx;
  })();

  return (
    <>
      {/* Stepper */}
      {stepperLabels.length > 1 && (
        <div className="flex items-center gap-1 text-[10px]">
          {stepperLabels.map((lab, i) => {
            const done = i < currentStepIdx;
            const active = i === currentStepIdx;
            return (
              <div key={lab} className="flex items-center gap-1">
                <span className={
                  "px-2 py-0.5 rounded border " + (
                    active ? "bg-amber-100 border-amber-400 text-amber-800 font-bold" :
                    done ? "bg-emerald-50 border-emerald-300 text-emerald-700" :
                    "bg-gray-50 border-gray-200 text-gray-400"
                  )
                }>{done ? "✓ " : ""}{lab}</span>
                {i < stepperLabels.length - 1 && <span className="text-gray-300">→</span>}
              </div>
            );
          })}
        </div>
      )}

      {/* SECTION 0: 감지된 ontology 용어 (항상 보임) */}
      {detectedTerms.length > 0 && (
        <div className="bg-emerald-50 border border-emerald-200 rounded p-2 text-[11px]">
          <div className="font-semibold text-emerald-700 mb-1">감지된 ontology 용어</div>
          <div className="flex flex-wrap gap-1">
            {detectedTerms.map((t, i) => (
              <span key={i} className="px-1.5 py-0.5 bg-white border border-emerald-300 rounded font-mono text-[10px]">
                {String(t.token)} → {String(t.label)}{" "}
                <code className="text-emerald-700">{String(t.term_fqn)}</code>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 🆕 Q2 — Edging 능력 상하한 변경 영향 */}
      {edgingImpact && (
        <div className="border-2 border-purple-300 bg-gradient-to-br from-purple-50/60 to-fuchsia-50/40 rounded-lg p-3 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-700 text-white font-semibold">EDGING</span>
            <span className="text-sm font-bold text-purple-900">{edgingImpact.title}</span>
          </div>
          <div className="text-[11px] text-purple-800 italic">{edgingImpact.purpose}</div>

          {/* 기준 + 외부 제약 */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-white/80 rounded p-2 border border-purple-200">
              <div className="text-[9px] text-purple-700 uppercase font-semibold mb-1">현재 Edging 능력</div>
              <code className="text-[11px] text-purple-900 font-mono">
                LOW {edgingImpact.base_edging.HR_TGT_WIDTH_LOW.toLocaleString()} ~ HIGH {edgingImpact.base_edging.HR_TGT_WIDTH_HIGH.toLocaleString()}
              </code>
            </div>
            <div className="bg-white/80 rounded p-2 border border-amber-200">
              <div className="text-[9px] text-amber-700 uppercase font-semibold mb-1">외부 설비 제약 (교집합)</div>
              {Object.entries(edgingImpact.external_constraints).map(([k, v]) => (
                <div key={k} className="text-[10px] font-mono text-amber-900">
                  <code>{k}</code>=<strong>{v.toLocaleString()}</strong>
                </div>
              ))}
            </div>
          </div>

          {/* insight — 현재 EDGING binding 여부 핵심 메시지 */}
          {edgingImpact.insight && (
            <div className="bg-white/90 rounded border-2 border-purple-400 p-2 text-[11px] text-purple-900 leading-relaxed">
              {edgingImpact.insight}
            </div>
          )}

          {/* 시나리오 표 */}
          <div className="bg-white/80 rounded border border-purple-200 overflow-x-auto">
            <div className="px-2 py-1.5 bg-purple-100/60 text-[10.5px] font-semibold text-purple-900 border-b border-purple-200">
              시나리오 비교 — 변경 후 효과 폭 · binding 설비 · 단중 영향
            </div>
            <table className="w-full text-[10.5px]">
              <thead className="bg-purple-50">
                <tr className="border-b border-purple-200 text-purple-700">
                  <th className="text-left p-1.5">시나리오</th>
                  <th className="text-right p-1.5">신규 EDGING</th>
                  <th className="text-right p-1.5">효과 폭 (교집합)</th>
                  <th className="text-left p-1.5">binding 설비</th>
                  <th className="text-right p-1.5">폭 범위 변화</th>
                  <th className="text-right p-1.5">최대 단중 변화</th>
                  <th className="text-right p-1.5">최소 단중 변화</th>
                </tr>
              </thead>
              <tbody>
                {edgingImpact.scenarios.map((sc, i) => (
                  <tr key={i} className={
                    "border-b border-gray-100 " + (
                      !sc.feasible ? "bg-red-50/40 text-gray-500" :
                      sc.label === "현재 EDGING" ? "bg-gray-50 font-semibold" :
                      sc.weight_change_pct > 0.5 ? "bg-emerald-50/50" :
                      sc.weight_change_pct < -0.5 ? "bg-orange-50/50" : ""
                    )
                  }>
                    <td className="p-1.5 font-semibold">{sc.label}</td>
                    <td className="text-right p-1.5 font-mono">
                      {sc.new_low.toLocaleString()} ~ {sc.new_high.toLocaleString()}
                    </td>
                    <td className="text-right p-1.5 font-mono">
                      {sc.feasible
                        ? `${sc.effective_low.toLocaleString()} ~ ${sc.effective_high.toLocaleString()}`
                        : "—"}
                    </td>
                    <td className="p-1.5 text-[10px]">
                      {sc.binding_constraint && (
                        <span className={
                          "px-1 py-0.5 rounded " + (
                            sc.edging_active
                              ? "bg-purple-200 text-purple-900 font-semibold"
                              : "bg-gray-200 text-gray-700"
                          )
                        }>{sc.binding_constraint}</span>
                      )}
                    </td>
                    <td className={"text-right p-1.5 font-mono " + (
                      sc.range_change_pct > 0.5 ? "text-emerald-700" :
                      sc.range_change_pct < -0.5 ? "text-orange-700" : "text-gray-500"
                    )}>
                      {sc.range_change_pct > 0 ? "+" : ""}{sc.range_change_pct.toFixed(1)}%
                    </td>
                    <td className={"text-right p-1.5 font-mono font-bold " + (
                      (sc.max_wgt_change_pct ?? sc.weight_change_pct) > 0.5 ? "text-emerald-700" :
                      (sc.max_wgt_change_pct ?? sc.weight_change_pct) < -0.5 ? "text-orange-700" : "text-gray-500"
                    )}>
                      {sc.warning ? (
                        <span className="text-red-700">⚠ {sc.warning}</span>
                      ) : (
                        <>{(sc.max_wgt_change_pct ?? sc.weight_change_pct) > 0 ? "+" : ""}{(sc.max_wgt_change_pct ?? sc.weight_change_pct).toFixed(1)}%</>
                      )}
                    </td>
                    <td className={"text-right p-1.5 font-mono " + (
                      (sc.min_wgt_change_pct ?? 0) > 0.5 ? "text-orange-700" :
                      (sc.min_wgt_change_pct ?? 0) < -0.5 ? "text-emerald-700" : "text-gray-500"
                    )}>
                      {sc.warning || sc.min_wgt_change_pct === undefined ? "—" : (
                        <>{sc.min_wgt_change_pct > 0 ? "+" : ""}{sc.min_wgt_change_pct.toFixed(1)}%</>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10.5px]">
            <div className="bg-white/70 rounded p-2 border border-purple-200">
              <div className="text-[9px] text-purple-700 uppercase font-semibold mb-1">핵심 로직</div>
              <div className="text-gray-800 leading-relaxed">{edgingImpact.core_logic}</div>
            </div>
            <div className="bg-amber-50/70 rounded p-2 border border-amber-200">
              <div className="text-[9px] text-amber-700 uppercase font-semibold mb-1">⚠ 유의사항</div>
              <div className="text-gray-800 leading-relaxed">{edgingImpact.note}</div>
            </div>
          </div>
        </div>
      )}

      {/* 🆕 Q3 interactive — 가상 주문 + 사용자 입력 (우선) */}
      {/* Q3 — default sweep 결과 즉시 노출 (사용자가 단계 진행 안 해도 best 결과 바로 보이게) */}
      {/* 🆕 editable 기준주문 + 21-step 산식 trace (2026-05-25) */}
      {q3Interactive && weightSweep && weightSweep.best && (
        <EditableBaseOrderPanel initial={weightSweep as never} />
      )}

      {q3Interactive && (
        <Q3InteractiveCard data={q3Interactive} />
      )}

      {/* 🆕 Q3 fallback — auto sweep (q3 interactive 없을 때만) */}
      {!q3Interactive && weightSweep && (
        <div className="border-2 border-teal-300 bg-gradient-to-br from-teal-50/60 to-cyan-50/40 rounded-lg p-3 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-teal-700 text-white font-semibold">SWEEP</span>
            <span className="text-sm font-bold text-teal-900">단중 최적화 — 변수 sweep</span>
            <span className="text-[10px] text-teal-700 ml-auto">
              {weightSweep.total_cells} 조합 · feasible {weightSweep.feasible_cells} 건
            </span>
          </div>

          {/* base order */}
          <div className="bg-white/80 rounded p-2 border border-teal-200">
            <div className="text-[9px] text-teal-700 uppercase font-semibold mb-1">기준 주문 (base)</div>
            <div className="flex flex-wrap gap-1 text-[10px]">
              {Object.entries(weightSweep.base_order)
                .filter(([k, v]) => !k.startsWith("_") && v !== null && v !== undefined && typeof v !== "object")
                .slice(0, 8)
                .map(([k, v]) => (
                  <code key={k} className="bg-teal-50 border border-teal-200 px-1.5 py-0.5 rounded text-teal-900">
                    {k}=<strong>{String(v)}</strong>
                  </code>
                ))}
            </div>
          </div>

          {/* sweep 변수 + 범위 */}
          <div className="bg-white/80 rounded p-2 border border-teal-200">
            <div className="text-[9px] text-teal-700 uppercase font-semibold mb-1">sweep 변수 ({weightSweep.sweep_variables.length})</div>
            <div className="space-y-1 text-[10.5px]">
              {weightSweep.sweep_variables.map((v) => {
                const r = weightSweep.var_ranges[v];
                return (
                  <div key={v} className="flex items-center gap-2">
                    <code className="font-mono text-teal-900 font-bold">{v}</code>
                    <span className="text-gray-600">범위:</span>
                    <code className="bg-gray-50 px-1 rounded text-gray-800">
                      {r?.[0]?.toLocaleString()} ~ {r?.[1]?.toLocaleString()}
                    </code>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 최적 조합 highlight */}
          {weightSweep.best && (
            <div className="bg-emerald-100/70 border-2 border-emerald-400 rounded p-2.5">
              <div className="flex items-center gap-1 mb-1.5">
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-700 text-white font-bold">🏆 BEST</span>
                <span className="text-[11px] font-bold text-emerald-900">최적 조합</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <div className="text-[9px] text-emerald-700 uppercase font-semibold">예상 slab 단중</div>
                  <div className="text-lg font-bold text-emerald-900">
                    {weightSweep.best.projected_slab_wgt.toLocaleString()} <span className="text-xs text-emerald-700">kg</span>
                  </div>
                  <div className="text-[10px] text-emerald-700">
                    split {weightSweep.best.projected_split_count}개
                  </div>
                </div>
                <div>
                  <div className="text-[9px] text-emerald-700 uppercase font-semibold">권장 변수값</div>
                  {Object.entries(weightSweep.best.vars).map(([k, v]) => (
                    <div key={k} className="text-[10.5px]">
                      <code className="text-emerald-900">{k}</code> = <strong>{v.toLocaleString()}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* grid 표 — 상위 12 cell */}
          <details className="bg-white/80 rounded border border-teal-200" open>
            <summary className="cursor-pointer px-2 py-1 text-[10.5px] text-teal-900 font-semibold">
              sweep grid ({weightSweep.grid.length} 조합, slab 단중 ↓ 정렬)
            </summary>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead className="bg-teal-50">
                  <tr className="border-b border-teal-200 text-teal-700">
                    <th className="text-left p-1.5">상태</th>
                    {weightSweep.sweep_variables.map((v) => (
                      <th key={v} className="text-right p-1.5 font-mono">{v}</th>
                    ))}
                    <th className="text-right p-1.5">예상 slab 단중</th>
                    <th className="text-right p-1.5">split</th>
                    <th className="text-left p-1.5">위반</th>
                  </tr>
                </thead>
                <tbody>
                  {[...weightSweep.grid]
                    .sort((a, b) => b.projected_slab_wgt - a.projected_slab_wgt)
                    .slice(0, 16)
                    .map((c, i) => (
                      <tr key={i} className={"border-b border-gray-100 " + (
                        c === weightSweep.best ? "bg-emerald-50 font-bold" :
                        !c.feasible ? "bg-red-50/50 text-gray-500" : ""
                      )}>
                        <td className="p-1.5">
                          <span className={"text-[9px] px-1 py-0.5 rounded " + (
                            c.feasible ? "bg-emerald-200 text-emerald-900" : "bg-red-200 text-red-900"
                          )}>
                            {c.feasible ? "OK" : "✗"}
                          </span>
                        </td>
                        {weightSweep.sweep_variables.map((v) => (
                          <td key={v} className="text-right p-1.5 font-mono">
                            {c.vars[v]?.toLocaleString()}
                          </td>
                        ))}
                        <td className="text-right p-1.5 font-mono text-emerald-900">
                          {c.projected_slab_wgt.toLocaleString()}
                        </td>
                        <td className="text-right p-1.5 font-mono">{c.projected_split_count}</td>
                        <td className="text-[9px] text-red-700">{c.violations.join(", ")}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </details>

          <div className="text-[10.5px] text-teal-800 bg-teal-100/40 rounded p-1.5 italic">
            💡 {weightSweep.summary}
          </div>
        </div>
      )}

      {/* STAGE 1: 기준 데이터 row 선택 */}
      {stage === 1 && hasTargetRows && (
        <div className="border-2 border-amber-300 bg-amber-50/40 rounded p-3 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xl">📋</span>
            <div>
              <div className="text-[10px] uppercase text-amber-700 font-semibold tracking-wide">기준 데이터 선택</div>
              <div className="text-sm text-gray-700">
                <code className="font-mono text-amber-900">{String(targetChange?.table)}</code> 에 어떤 row 의 값을 변경하시겠어요? <strong>{targetRows.length}건</strong> 中 1건 선택
              </div>
              {targetMeta?.description && <div className="text-[10px] text-gray-500 mt-0.5">{targetMeta.description}</div>}
            </div>
          </div>
          {/* 컬럼 선택 안내 + dropdown */}
          <div className="bg-white border border-amber-200 rounded p-2 flex items-center gap-2 flex-wrap text-[11px]">
            <span className="text-amber-700 font-semibold">변경할 컬럼:</span>
            <select
              value={pickedCol}
              onChange={(e) => pickColumn(e.target.value)}
              className="text-xs px-2 py-1 border border-amber-300 rounded font-mono bg-amber-50 text-amber-900 focus:outline-none focus:border-amber-500"
            >
              {targetColumns.map((c) => (
                <option key={c} value={c}>
                  {targetMeta?.pk_columns?.includes(c) ? "🔑 " : ""}{c}
                </option>
              ))}
            </select>
            <span className="text-[10px] text-gray-500">또는 아래 표의 ⭐ 컬럼 헤더를 클릭해서 변경</span>
          </div>

          <div className="max-h-72 overflow-y-auto border border-amber-200 rounded bg-white">
            <table className="w-full text-[10px]">
              <thead className="sticky top-0 bg-amber-50">
                <tr className="border-b border-amber-200">
                  <th className="p-1.5 w-8"></th>
                  {/* PK 컬럼 먼저 + 변경 대상 컬럼 — 헤더 클릭으로 column 변경 */}
                  {targetColumns.slice(0, 9).map((c) => (
                    <th
                      key={c}
                      onClick={() => pickColumn(c)}
                      title={`이 컬럼을 변경 대상으로 선택: ${c}`}
                      className={
                        "text-left p-1.5 font-mono cursor-pointer hover:bg-amber-100 transition " + (
                          targetMeta?.pk_columns?.includes(c) ? "text-amber-700 font-bold" :
                          c === targetCol ? "text-red-700 font-bold bg-red-50 ring-2 ring-red-300" : "text-gray-600"
                        )
                      }
                    >
                      {targetMeta?.pk_columns?.includes(c) && "🔑 "}
                      {c === targetCol && "⭐ "}
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {targetRows.map((row, i) => {
                  const isPicked = i === pickedRowIdx;
                  return (
                    <tr key={i}
                      onClick={() => {
                        setPickedRowIdx(i);
                        const cur = row[targetCol];
                        setUserChange((s) => ({
                          ...s,
                          before: cur === null || cur === undefined ? "" : String(cur),
                        }));
                      }}
                      className={
                        "cursor-pointer border-b border-gray-100 hover:bg-amber-50/60 " +
                        (isPicked ? "bg-amber-100 ring-1 ring-amber-400" : "")
                      }>
                      <td className="p-1.5 text-center">
                        <input type="radio" checked={isPicked} readOnly className="accent-amber-500" />
                      </td>
                      {targetColumns.slice(0, 9).map((c) => (
                        <td key={c} className={
                          "p-1.5 font-mono " + (
                            c === targetCol ? "text-red-700 font-bold bg-red-50" : "text-gray-800"
                          )
                        }>
                          {row[c] === null || row[c] === undefined
                            ? <span className="text-gray-300">null</span>
                            : String(row[c]).length > 18 ? String(row[c]).slice(0, 18) + "…" : String(row[c])}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end items-center gap-2 pt-1">
            <button onClick={() => setStage(2)} disabled={pickedRowIdx === null}
              className="px-3 py-1.5 text-xs rounded bg-amber-600 text-white hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed">
              {pickedRowIdx !== null
                ? `✓ 이 row 의 ${targetCol} 변경하기`
                : `row 선택 필요 (현재 변경 컬럼: ${targetCol})`}
            </button>
          </div>
        </div>
      )}

      {/* STAGE 2: 변경 전·후 값 입력 — editable */}
      {stage === 2 && hasTarget && (
        <>
          {/* 선택된 row 표시 */}
          {pickedRow && (
            <div className="text-[10px] bg-amber-50 border border-amber-200 rounded p-2">
              <div className="text-gray-500 mb-1">선택된 기준 row:</div>
              <div className="flex flex-wrap gap-1">
                {(targetMeta?.pk_columns ?? Object.keys(pickedRow).slice(0, 4)).map((c) => (
                  <span key={c} className="px-1.5 py-0.5 bg-white border border-amber-300 rounded font-mono">
                    {c}=<strong>{String(pickedRow[c] ?? "")}</strong>
                  </span>
                ))}
              </div>
            </div>
          )}
          <_TargetChangeCard
            targetChange={{
              ...targetChange!,
              column: targetCol,
              before: userChange.before || targetChange!.before,
            }}
            editable
            onChange={(next) => setUserChange(next)}
            onColumnChange={pickColumn}
            availableColumns={targetColumns}
            pkColumns={targetMeta?.pk_columns}
          />
          <div className="flex justify-between items-center gap-2 pt-1">
            {hasTargetRows && (
              <button onClick={() => setStage(1)} className="text-[10px] text-gray-500 hover:text-gray-700">← 다른 row 선택</button>
            )}
            <div className="flex items-center gap-2 ml-auto">
              {(!userChange.before || !userChange.after) && (
                <span className="text-[10px] text-amber-700">⚠ 변경 전/후 값 입력 필요</span>
              )}
              <button
                onClick={() => setStage(hasOrders ? 3 : 4)}
                disabled={!userChange.before || !userChange.after}
                className="px-3 py-1.5 text-xs rounded bg-amber-600 text-white hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed">
                ✓ 변경 전 {userChange.before || "?"} → 후 {userChange.after || "?"} 로 진행
              </button>
            </div>
          </div>
        </>
      )}

      {/* STAGE 3: 시뮬용 가상 주문 선택 — 2026-05-25 사용자 요구: clarify_form 위에서
          이미 가상 주문 입력 받으므로 중복 — 영구 hide. Q3 도 동일. */}
      {false && stage === 3 && hasOrders && !q3Interactive && (
        <div className="border-2 border-sky-300 bg-sky-50/40 rounded-lg p-3 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xl">🧪</span>
            <div className="flex-1">
              <div className="text-[10.5px] uppercase text-sky-700 font-semibold tracking-wide">가상 주문 (실제 DB 사용 안 함)</div>
              <div className="text-[12.5px] text-gray-800">
                이 변경을 시뮬할 <strong>가상 주문 {affectedOrders.length}건</strong>을 합성했습니다 — 어떤 주문 기준으로 결과를 보시겠어요?
              </div>
              {affectedOrdersSynthesisNote && (
                <div className="text-[10px] text-sky-600 mt-0.5">💡 {affectedOrdersSynthesisNote}</div>
              )}
            </div>
          </div>
          <div className="bg-white rounded border border-sky-200 overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead className="bg-sky-50 sticky top-0">
                <tr className="border-b border-sky-200 text-sky-700">
                  <th className="text-left p-2 w-6"></th>
                  {affectedOrdersColumns.map((c) => (
                    <th key={c} className="text-left p-2 font-mono text-[10px]">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {affectedOrders.map((o, i) => {
                  const orderNo = String(o.ORDER_NO ?? "");
                  const isPicked = pickedOrder === orderNo;
                  return (
                    <tr key={i}
                      onClick={() => setPickedOrder(orderNo)}
                      className={
                        "cursor-pointer border-b border-sky-100 hover:bg-sky-50/60 " +
                        (isPicked ? "bg-sky-100 ring-1 ring-sky-400" : "")
                      }>
                      <td className="p-2 text-center">
                        <input type="radio" checked={isPicked} readOnly className="accent-sky-500" />
                      </td>
                      {affectedOrdersColumns.map((c) => (
                        <td key={c} className={"p-2 font-mono " + (
                          c === "ORDER_NO" ? "text-sky-800 font-semibold" : "text-gray-800"
                        )}>
                          {o[c] === null || o[c] === undefined ? <span className="text-gray-300">—</span> : String(o[c])}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex justify-between items-center pt-1">
            <button onClick={() => setStage(2)}
              className="text-[11px] text-gray-600 hover:text-gray-900 underline">← 변경값 다시 입력</button>
            <div className="flex items-center gap-2">
              <button onClick={() => setStage(4)}
                className="text-[11px] text-gray-500 hover:text-gray-700">전체 보기 →</button>
              <button onClick={() => setStage(4)} disabled={!pickedOrder}
                className="px-3 py-1.5 text-[11px] rounded bg-sky-600 text-white hover:bg-sky-500 disabled:opacity-50 font-semibold">
                {pickedOrder ? `✓ ${pickedOrder} 기준으로 진행` : "주문 선택 필요"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STAGE 4: 영향 결과 — stage 4 일 때만 표시 */}
      {stage === 4 && (
        <>
          {/* slab 비교 (선택된 주문 기반) — 변경 전/후 결과 */}
          {pickedOrder && targetChange && userChange.before && userChange.after && (
            <_ImpactSlabCompareCard
              table={String(targetChange.table)}
              column={targetCol}
              before={userChange.before}
              after={userChange.after}
              order_no={pickedOrder}
              affectedFqns={methods.map((m) => String(m.fqn ?? "")).filter(Boolean).slice(0, 5)}
              codeMode={codeMode}
            />
          )}
          {/* Q2 Edging — 선택 주문에 6 시나리오 적용한 slab 결과 변화 */}
          {pickedOrder && edgingImpact && (() => {
            const pOrder = affectedOrders.find((o) => String(o.ORDER_NO) === pickedOrder);
            const orderW = pOrder ? Number(pOrder.ORDER_WIDTH) : 0;
            return (
              <div className="border-2 border-purple-300 bg-gradient-to-br from-purple-50/60 to-fuchsia-50/40 rounded-lg p-3 sim-anim-fadein">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className="text-[10.5px] px-2 py-0.5 rounded bg-purple-700 text-white font-bold">선택 주문 결과</span>
                  <strong className="text-[13px] text-purple-900">
                    {pickedOrder} 주문 — Edging 6 시나리오 적용 시 slab 결과
                  </strong>
                </div>
                {pOrder && (
                  <div className="bg-white/80 rounded p-2 mb-2 border border-purple-100 text-[11px] flex flex-wrap gap-2">
                    <code className="text-purple-800">PRODUCT={String(pOrder.PRODUCT_CD ?? "?")}</code>
                    <code className="text-purple-800">GRADE={String(pOrder.GRADE_CD ?? "?")}</code>
                    <code className="text-purple-800">ORDER_WIDTH={String(pOrder.ORDER_WIDTH ?? "?")}</code>
                    <code className="text-purple-800">DESIGN_PEND_QTY={String(pOrder.DESIGN_PEND_QTY ?? "?")}</code>
                  </div>
                )}
                <table className="w-full text-[11px] bg-white rounded border border-purple-200">
                  <thead className="bg-purple-50">
                    <tr className="border-b border-purple-200 text-purple-700">
                      <th className="text-left p-2">시나리오</th>
                      <th className="text-right p-2">효과 폭 교집합</th>
                      <th className="text-right p-2">주문 폭({orderW}) 수용?</th>
                      <th className="text-right p-2">최대 단중 변화</th>
                    </tr>
                  </thead>
                  <tbody>
                    {edgingImpact.scenarios.map((sc, i) => {
                      const inRange = orderW >= sc.effective_low && orderW <= sc.effective_high;
                      return (
                        <tr key={i} className={
                          "border-b border-gray-100 " + (
                            !sc.feasible ? "bg-red-50/40 text-gray-500" :
                            sc.label === "현재 EDGING" ? "bg-gray-100 font-semibold" :
                            sc.weight_change_pct > 0.5 ? "bg-emerald-50/50" :
                            sc.weight_change_pct < -0.5 ? "bg-orange-50/50" : ""
                          )
                        }>
                          <td className="p-2 font-semibold">{sc.label}</td>
                          <td className="text-right p-2 font-mono">
                            {sc.feasible ? `${sc.effective_low.toLocaleString()} ~ ${sc.effective_high.toLocaleString()}` : "—"}
                          </td>
                          <td className="text-right p-2">
                            {sc.feasible ? (
                              inRange
                                ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">✓ 수용</span>
                                : <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-800 font-semibold">✗ 범위 밖</span>
                            ) : "—"}
                          </td>
                          <td className={"text-right p-2 font-mono font-bold " + (
                            (sc.max_wgt_change_pct ?? sc.weight_change_pct) > 0.5 ? "text-emerald-700" :
                            (sc.max_wgt_change_pct ?? sc.weight_change_pct) < -0.5 ? "text-orange-700" : "text-gray-500"
                          )}>
                            {sc.warning ? <span className="text-red-700">⚠</span> : (
                              <>{(sc.max_wgt_change_pct ?? sc.weight_change_pct) > 0 ? "+" : ""}{(sc.max_wgt_change_pct ?? sc.weight_change_pct).toFixed(1)}%</>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <div className="mt-2 text-[11px] text-purple-800 bg-purple-50 rounded p-2">
                  💡 선택한 주문 폭({orderW}mm)이 각 시나리오의 효과 폭 안에 들어가는지 + 그 시나리오에서 최대 단중이 얼마나 변하는지 한눈에 비교
                </div>
              </div>
            );
          })()}
          {hasTarget && (
            <div className="text-[11px] bg-amber-50 border border-amber-300 rounded p-2 flex items-center gap-2">
              <span>🔄</span>
              <span>
                {pickedRow && targetMeta?.pk_columns && (
                  <span className="text-gray-500">
                    {targetMeta.pk_columns.map((c) => `${c}=${pickedRow[c]}`).join(" · ")} · {" "}
                  </span>
                )}
                <code className="bg-white px-1.5 py-0.5 rounded border border-amber-200 text-amber-900">
                  {String(targetChange!.table)}.{String(targetChange!.column)}
                </code>
                {" "}을(를){" "}
                <code className="bg-red-50 px-1 rounded text-red-700">{userChange.before || "?"}</code>
                <span className="mx-1 text-gray-400">→</span>
                <code className="bg-emerald-50 px-1 rounded text-emerald-700 font-bold">{userChange.after || "?"}</code>
                {" "}변경 시 영향
              </span>
              <button onClick={() => setStage(2)} className="ml-auto text-[10px] text-amber-700 hover:underline">
                ← 값 다시 입력
              </button>
            </div>
          )}
          {pickedOrder && (
            <div className="text-[11px] bg-sky-50 border border-sky-200 rounded p-2 flex items-center gap-2">
              <span>📦</span>
              <span><strong className="text-sky-800">{pickedOrder}</strong> 주문 기준으로 분석</span>
              <button onClick={() => setStage(3)} className="ml-auto text-[10px] text-sky-700 hover:underline">
                ← 다른 주문 선택
              </button>
            </div>
          )}
          {!pickedOrder && hasOrders && (
            <div className="text-[10px] text-gray-500 flex items-center gap-2">
              <button onClick={() => setStage(2)} className="text-sky-700 hover:underline">
                📦 주문 선택해서 보기
              </button>
            </div>
          )}

      {/* SECTION 2: 영향받는 코드 — codeMode=collapsed 면 details 로 접힘, open 면 펼침 */}
      {codeMode !== "hide" && methods.length > 0 && (() => {
        const headerTitle = (payload._affected_methods_source === "related")
          ? `📎 관련 있는 코드 (method) ${methods.length}건`
          : `영향받는 코드 (method) ${methods.length}건`;
        const headerSubtitle = (payload._affected_methods_source === "related")
          ? "직접 영향은 0건이라 관련 term → action → method 로 대체"
          : `confidence ${confidence.toFixed(2)} · 행 click → 본문`;
        const tableBody = (
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-[11px] border-collapse">
              <thead className="sticky top-0">
                <tr className="bg-gray-50/95 border-b border-gray-200">
                  <th className="text-left p-1.5 w-6"></th>
                  <th className="text-left p-1.5 text-gray-600">method (class.name)</th>
                  <th className="text-left p-1.5 text-gray-600">via</th>
                  <th className="text-right p-1.5 text-gray-600">distance</th>
                  <th className="text-right p-1.5 text-gray-600">strength</th>
                </tr>
              </thead>
              <tbody>
                {methods.slice(0, 50).map((m) => {
                  const fqn = String(m.fqn ?? "");
                  if (!fqn) return null;
                  const isOpen = expanded.has(fqn);
                  return (
                    <React.Fragment key={fqn}>
                      <tr
                        className="border-b border-gray-100 hover:bg-amber-50/40 cursor-pointer"
                        onClick={() => toggle(fqn)}
                      >
                        <td className="p-1.5 text-gray-400">
                          {isOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                        </td>
                        <td className="p-1.5 font-mono text-gray-800 truncate max-w-[280px]" title={fqn}>
                          {fqn.split(".").slice(-2).join(".").replace(/\(.*\)/, "")}
                        </td>
                        <td className="p-1.5 text-gray-500">{String(m.via ?? "—")}</td>
                        <td className="p-1.5 text-right text-gray-500">{String(m.distance ?? "—")}</td>
                        <td className="p-1.5 text-right text-gray-700 font-mono">
                          {Number(m.strength ?? 0).toFixed(2)}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr className="border-b border-amber-100">
                          <td colSpan={5} className="p-0">
                            <_MethodBodyRow fqn={fqn} onJumpTo={(f) => { toggle(f); }} />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
                {methods.length === 0 && (
                  <tr><td colSpan={5} className="p-2 text-gray-400 text-[10px]">영향받는 method 없음</td></tr>
                )}
              </tbody>
            </table>
          </div>
        );
        if (codeMode === "collapsed") {
          return (
            <details className="border border-gray-200 rounded">
              <summary className="px-2 py-1.5 bg-gray-50 border-b border-gray-200 cursor-pointer text-[11px] flex items-center justify-between">
                <strong>{headerTitle}</strong>
                <span className="text-[10px] text-gray-500">{headerSubtitle} · 상세 펼치기</span>
              </summary>
              {tableBody}
            </details>
          );
        }
        return (
          <div className="border border-gray-200 rounded">
            <div className="px-2 py-1.5 bg-gray-50 border-b border-gray-200 flex items-center justify-between text-[11px]">
              <strong>{headerTitle}</strong>
              <span className="text-[10px] text-gray-500">{headerSubtitle}</span>
            </div>
            {tableBody}
          </div>
        );
      })()}

      {/* SECTION 3: 영향받는 룰 — chip + hover tooltip (디폴트 단순) */}
      {affectedRules.length > 0 && (
        <div className="bg-indigo-50/40 border border-indigo-200 rounded-lg p-2 flex items-center gap-2 flex-wrap">
          <span className="text-[11px] text-indigo-900 font-semibold">📘 적용 업무 규칙</span>
          <span className="text-[10.5px] text-indigo-700">{affectedRules.length}개</span>
          <div className="flex gap-1 flex-wrap">
            {affectedRules.slice(0, 8).map((r, i) => {
              const sev = String(r.severity ?? "soft");
              const isHard = sev === "hard";
              const fqn = String(r.fqn ?? "");
              const shortName = fqn.split(".").slice(-2).join(".") || `규칙 #${i + 1}`;
              return (
                <span key={i}
                  className={"group relative text-[10.5px] px-2 py-0.5 rounded border cursor-help " + (
                    isHard ? "bg-indigo-100 text-indigo-900 border-indigo-300 hover:bg-indigo-200"
                           : "bg-sky-100 text-sky-900 border-sky-300 hover:bg-sky-200"
                  )}
                  title={`${isHard ? "필수 규칙" : "권장 규칙"}\n${String(r.statement ?? "")}`}
                >
                  {isHard ? "🔷" : "🔹"} {shortName}
                  <span className="absolute left-0 top-full mt-1 z-30 hidden group-hover:block w-80 bg-white border-2 border-indigo-300 rounded-lg p-2.5 shadow-xl text-left">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className={"text-[9px] px-1.5 py-0.5 rounded font-bold " + (
                        isHard ? "bg-indigo-600 text-white" : "bg-sky-400 text-sky-900"
                      )}>{isHard ? "필수 규칙" : "권장 규칙"}</span>
                      <code className="text-[9.5px] text-gray-500 font-mono">{fqn}</code>
                    </div>
                    <div className="text-[11.5px] text-gray-800 leading-relaxed">
                      {String(r.statement ?? "")}
                    </div>
                  </span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* SECTION 4: 가상 주문 — 질문 연관 동적 컬럼. 주문 선택 후엔 hide (중복 방지) */}
      {affectedOrders.length > 0 && !pickedOrder && (
        <div className="border border-sky-200 bg-sky-50/40 rounded p-2">
          <div className="flex items-baseline gap-1.5 mb-1">
            <span className="text-[11px] font-semibold text-sky-800">🧪 시뮬용 가상 주문 ({affectedOrders.length}건)</span>
            <span className="text-[9.5px] text-sky-600">실제 DB 사용 안 함 · 기준 데이터 범위 내 ontology 합성</span>
          </div>
          <table className="w-full text-[10px]">
            <thead><tr className="border-b border-sky-200">
              {affectedOrdersColumns.map((c) => (
                <th key={c} className={c === "ORDER_NO" ? "text-left p-0.5" : "text-right p-0.5"}>{c}</th>
              ))}
            </tr></thead>
            <tbody>
              {affectedOrders.slice(0, 10).map((o, i) => (
                <tr key={i} className="border-b border-sky-100">
                  {affectedOrdersColumns.map((c) => (
                    <td key={c} className={"p-0.5 font-mono " + (c === "ORDER_NO" ? "" : "text-right")}>
                      {o[c] === null || o[c] === undefined ? "—" : String(o[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* SECTION 5: affected_steps (intent_focus=step 또는 항상 표시) */}
      {affectedSteps.length > 0 && (
        <div className="border border-violet-200 bg-violet-50/40 rounded p-2">
          <div className="text-[11px] font-semibold text-violet-800 mb-1 flex items-center gap-1">
            🪜 영향받는 21-step ({affectedSteps.length})
            {intentFocus === "step" && <span className="text-[9px] bg-violet-600 text-white px-1.5 py-0.5 rounded">질문 의도</span>}
          </div>
          <div className="flex flex-wrap gap-1">
            {affectedSteps.map((s, i) => (
              <span key={i} title={String(s.method_fqn)}
                className="text-[10px] px-2 py-1 rounded border border-violet-300 bg-white font-mono">
                Step {String(s.step)} · {String(s.action_class).replace(/Action$/, "")}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 6: affected_actions (ontology actions) */}
      {affectedActions.length > 0 && (
        <div className="border border-indigo-200 bg-indigo-50/40 rounded p-2">
          <div className="text-[11px] font-semibold text-indigo-800 mb-1 flex items-center gap-1">
            ⚙ 영향받는 ontology actions ({affectedActions.length})
            {intentFocus === "action" && <span className="text-[9px] bg-indigo-600 text-white px-1.5 py-0.5 rounded">질문 의도</span>}
          </div>
          <ul className="text-[10px] space-y-0.5">
            {affectedActions.map((a, i) => (
              <li key={i}>
                <code className="text-indigo-700 font-mono">{String(a.fqn)}</code>
                <span className="text-gray-500 ml-1">· {String(a.label ?? "")}</span>
                {a.kind ? <span className="text-[9px] ml-1 bg-indigo-100 text-indigo-700 px-1 rounded">{String(a.kind)}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* SECTION 7: affected_apis */}
      {affectedApis.length > 0 && (
        <div className="border border-cyan-200 bg-cyan-50/40 rounded p-2">
          <div className="text-[11px] font-semibold text-cyan-800 mb-1 flex items-center gap-1">
            🔌 영향받는 API ({affectedApis.length})
            {intentFocus === "api" && <span className="text-[9px] bg-cyan-600 text-white px-1.5 py-0.5 rounded">질문 의도</span>}
          </div>
          <ul className="text-[10px] space-y-0.5">
            {affectedApis.map((a, i) => (
              <li key={i}>
                <code className="text-cyan-700 font-mono">{String(a.controller)}</code>
                <span className="text-gray-500 ml-1">· {String(a.method_fqn).split(".").pop()}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
        </>
      )}
    </>
  );
}

/** 인터랙티브 expand — method body + callers/callees navigation. */
function _MethodBodyRow({ fqn, onJumpTo }: { fqn: string; onJumpTo: (f: string) => void }) {
  const [data, setData] = useState<MethodBodyView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    simulationApi.methodBody(fqn)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fqn]);

  if (loading) {
    return (
      <div className="px-3 py-2 text-[11px] text-gray-500 bg-amber-50/30 flex items-center gap-1">
        <Loader2 size={11} className="animate-spin" /> 코드 로드 중...
      </div>
    );
  }
  if (error) {
    return <div className="px-3 py-2 text-[11px] text-red-700 bg-red-50">{error}</div>;
  }
  if (!data) return null;

  return (
    <div className="px-3 py-2 bg-amber-50/30 space-y-2">
      <div className="text-[10px] text-gray-500 font-mono break-all">{fqn}</div>
      {data.line_start && (
        <div className="text-[10px] text-gray-500">
          L{data.line_start}–{data.line_end ?? "?"}
          {data.annotations.length > 0 && (
            <span className="ml-2">
              {data.annotations.map((a) => (
                <code key={a} className="ml-1 text-[9px] px-1 bg-indigo-100 text-indigo-700 rounded">@{a}</code>
              ))}
            </span>
          )}
        </div>
      )}
      {data.body ? (
        <pre className="text-[10px] bg-white border border-amber-200 rounded p-2 max-h-48 overflow-auto text-gray-800">
{data.body.slice(0, 1200)}{data.body.length > 1200 ? "\n..." : ""}
        </pre>
      ) : (
        <div className="text-[10px] text-gray-400 italic">body 없음 (ontology 응답 비어있음)</div>
      )}
      <div className="grid grid-cols-2 gap-2 text-[10px]">
        <div>
          <div className="text-gray-500 mb-1 flex items-center gap-1">
            <Code size={10} /> 호출하는 곳 ({data.callers.length})
          </div>
          <ul className="space-y-0.5">
            {data.callers.slice(0, 6).map((c) => (
              <li key={c}>
                <button
                  onClick={(e) => { e.stopPropagation(); onJumpTo(c); }}
                  className="font-mono text-emerald-700 hover:underline truncate text-left"
                  title={c}
                >
                  ← {c.split(".").slice(-2).join(".")}
                </button>
              </li>
            ))}
            {data.callers.length === 0 && <li className="text-gray-400">없음</li>}
          </ul>
        </div>
        <div>
          <div className="text-gray-500 mb-1 flex items-center gap-1">
            <Code size={10} /> 호출되는 곳 ({data.callees.length})
          </div>
          <ul className="space-y-0.5">
            {data.callees.slice(0, 6).map((c) => (
              <li key={c}>
                <button
                  onClick={(e) => { e.stopPropagation(); onJumpTo(c); }}
                  className="font-mono text-sky-700 hover:underline truncate text-left"
                  title={c}
                >
                  → {c.split(".").slice(-2).join(".")}
                </button>
              </li>
            ))}
            {data.callees.length === 0 && <li className="text-gray-400">없음</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}

/** 코드 본문에서 keyword 를 highlight (배경 노랑). */
function _HighlightedCode({ body, keyword }: { body: string; keyword: string }) {
  if (!keyword || !body) return <>{body}</>;
  const parts = body.split(new RegExp(`(${keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"));
  return (
    <>
      {parts.map((p, i) =>
        p.toLowerCase() === keyword.toLowerCase()
          ? <mark key={i} className="bg-amber-200 text-amber-900">{p}</mark>
          : <span key={i}>{p}</span>
      )}
    </>
  );
}


/** locate — VSCode 스타일 위치 list + 클릭 시 본문 expand + keyword highlight. */
function _LocateView({ payload, codeMode = "open" }: { payload: Record<string, unknown>; codeMode?: "hide" | "collapsed" | "open" }) {
  const target = payload.target as Record<string, unknown> | undefined;
  const body = (payload.body as string | undefined) ?? "";
  const summary = payload.summary as string | undefined;
  const callers = (payload.callers as Array<Record<string, unknown>> | undefined) ?? [];
  const rules = (payload.business_rules as Array<Record<string, unknown>> | undefined) ?? [];
  const locateMatches = (payload._locate_matches as Array<Record<string, unknown>> | undefined) ?? [];
  const fqn = String(target?.code_method_fqn ?? "");

  // 위치 list — _locate_matches 우선 + primary target + callers
  type Match = { fqn: string; primary?: boolean; matched_line?: number; keyword?: string; snippet?: string };
  const matches: Match[] = [];
  if (fqn) matches.push({ fqn, primary: true });
  for (const m of locateMatches) {
    const f = String(m.method_fqn ?? "");
    if (f && f !== fqn) {
      matches.push({
        fqn: f,
        matched_line: m.matched_line as number | undefined,
        keyword: m.keyword as string | undefined,
        snippet: m.snippet as string | undefined,
      });
    }
  }
  for (const c of callers) {
    // backend caller shape: {fqn, distance, via, match_kind} — c.fqn 우선
    const f = String(c?.fqn ?? c?.method_fqn ?? c?.code_method_fqn ?? "");
    if (f && !matches.find((mm) => mm.fqn === f)) matches.push({ fqn: f });
  }

  const [activeFqn, setActiveFqn] = useState<string>(fqn);
  const [activeBody, setActiveBody] = useState<string>(body);
  const [activeKeyword, setActiveKeyword] = useState<string>("");
  const [activeMatchedLine, setActiveMatchedLine] = useState<number>(0);

  // 다른 위치 click → /method/body 조회
  async function pickLocation(m: Match) {
    if (m.fqn === activeFqn) return;
    setActiveFqn(m.fqn);
    setActiveKeyword(m.keyword ?? "");
    setActiveMatchedLine(m.matched_line ?? 0);
    if (m.primary) {
      setActiveBody(body);
      return;
    }
    if (m.snippet) {
      setActiveBody(m.snippet);
      return;
    }
    try {
      setActiveBody("");
      const r = await simulationApi.methodBody(m.fqn);
      setActiveBody(r.body || "(본문 없음 — ontology 응답 비어있음)");
    } catch (e) {
      setActiveBody(`로드 실패: ${String(e)}`);
    }
  }

  const filePathOf = (f: string) => {
    const cls = f.split("(")[0].split(".").slice(0, -1).join(".");
    return cls.replace(/\./g, "/") + ".java";
  };

  return (
    <>
      <div className="text-[11px] text-sky-800 bg-sky-50 border border-sky-200 rounded p-2 flex items-center gap-2">
        <span>🔍</span>
        <span>{summary || "코드 위치 검색 결과"} · {matches.length} 위치</span>
      </div>

      <div className={"gap-2 border border-gray-300 rounded overflow-hidden " + (
        codeMode === "open" ? "grid grid-cols-[240px_1fr]" : "grid grid-cols-1"
      )}>
        {/* 좌: 위치 list */}
        <div className="bg-slate-50 border-r border-gray-200 max-h-[420px] overflow-y-auto">
          <div className="px-2 py-1 bg-slate-100 text-[10px] text-gray-600 uppercase tracking-wide border-b border-gray-200">
            매칭 위치 ({matches.length})
          </div>
          <ul className="text-[10px]">
            {matches.map((m, i) => (
              <li key={m.fqn}>
                <button
                  onClick={() => pickLocation(m)}
                  className={
                    "w-full text-left px-2 py-1.5 border-b border-gray-100 hover:bg-sky-50 font-mono " +
                    (m.fqn === activeFqn ? "bg-sky-100 border-l-2 border-l-sky-500" : "")
                  }
                  title={m.fqn}
                >
                  <div className="text-sky-800 font-semibold truncate">
                    {m.primary ? "⚡ " : m.keyword ? "🔍 " : "↑ "}
                    {m.fqn.split(".").pop()?.split("(")[0]}
                  </div>
                  <div className="text-gray-500 truncate text-[9px]">
                    {filePathOf(m.fqn)}
                    {m.matched_line ? ` :${m.matched_line}` : ""}
                  </div>
                  {m.keyword && (
                    <div className="text-amber-700 text-[9px] mt-0.5">
                      🔑 <code className="bg-amber-100 px-0.5 rounded">{m.keyword}</code> 매칭
                    </div>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* 우: 활성 위치의 코드 본문 — open 이면 인라인, collapsed 면 details 로 접힘 */}
        {codeMode === "open" && (
          <div className="bg-white">
            <div className="px-2 py-1 bg-gray-50 border-b border-gray-200 text-[10px] flex items-center justify-between">
              <code className="text-gray-700">{filePathOf(activeFqn)}{activeMatchedLine ? `:${activeMatchedLine}` : ""}</code>
              <span className="text-gray-400">{activeBody.split("\n").length} lines{activeKeyword && ` · 🔑 ${activeKeyword}`}</span>
            </div>
            <pre className="p-2 text-[10px] max-h-[420px] overflow-auto text-gray-800 font-mono leading-relaxed">
              {activeBody
                ? activeKeyword
                  ? <_HighlightedCode body={activeBody} keyword={activeKeyword} />
                  : activeBody
                : "(좌측 위치 선택 — 클릭 시 본문 로드)"}
            </pre>
          </div>
        )}
      </div>
      {codeMode === "collapsed" && (
        <details className="border border-gray-200 rounded bg-white">
          <summary className="px-2 py-1.5 bg-gray-50 border-b border-gray-200 cursor-pointer text-[10.5px] text-gray-700 flex items-center justify-between">
            <span>📄 코드 본문 보기 — <code className="text-gray-800">{filePathOf(activeFqn)}{activeMatchedLine ? `:${activeMatchedLine}` : ""}</code></span>
            <span className="text-gray-400">{activeBody.split("\n").length} lines{activeKeyword && ` · 🔑 ${activeKeyword}`} · 상세 펼치기</span>
          </summary>
          <pre className="p-2 text-[10px] max-h-[420px] overflow-auto text-gray-800 font-mono leading-relaxed">
            {activeBody
              ? activeKeyword
                ? <_HighlightedCode body={activeBody} keyword={activeKeyword} />
                : activeBody
              : "(좌측 위치 선택 — 클릭 시 본문 로드)"}
          </pre>
        </details>
      )}

      {rules.length > 0 && (
        <div className="border border-rose-200 bg-rose-50/40 rounded p-2">
          <div className="text-[11px] font-semibold text-rose-700 mb-1">관련 business rules ({rules.length})</div>
          <ul className="text-[10px] space-y-0.5">
            {rules.slice(0, 5).map((r, i) => (
              <li key={i}>
                <code className="bg-rose-100 px-1 rounded text-[9px]">{String(r.severity ?? "?")}</code>
                <span className="ml-1 text-gray-700">{String(r.statement ?? "")}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

/** explain — 자연어 답변 + 관련 객체 카드 grid. */
/** 답변/카드의 mini 신뢰도 chip — overall + 상위 2개 source. hover 시 근거 원문. */
/** LLM 분석 body 시각 강조 — 이모지 없이 색·굵기로 가독성. */
function _AnalysisBody({ text }: { text: string }) {
  if (!text) return null;
  // 정규식: 숫자(단위) | 변화율 | key term (Slab 단중/분할수/매수/Step N/HR_MAX_WGT/ORDER_WGT_HIGH/DESIGN_PEND_QTY)
  const PATTERN = /(\d{1,3}(?:,\d{3})+(?:\.\d+)?\s*(?:kg|mm|g\/cm³|톤|개|매|건|%|단)?|\d+(?:\.\d+)?\s*%|[+\-]\d+(?:\.\d+)?%|Step\s*\d+|HR_MAX_WGT|HR_MIN_WGT|ORDER_WGT_HIGH|ORDER_WGT_LOW|DESIGN_PEND_QTY|ORDER_WIDTH|ORDER_LENGTH|slabWgt|secondWgtHigh|splitWgtHigh|maxSplitCountUpper|optimalSplitCount|slabCount|Slab\s*(?:단중|매수|분할수|두께|폭|길이)|분할수|매수|단중\s*(?:상한|하한)?|포장단중|설계대기량|baseline|after|productivity|비중)/g;
  const parts: Array<{ type: "text" | "highlight"; value: string }> = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = PATTERN.exec(text)) !== null) {
    if (m.index > last) parts.push({ type: "text", value: text.slice(last, m.index) });
    parts.push({ type: "highlight", value: m[0] });
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push({ type: "text", value: text.slice(last) });
  return (
    <span style={{ whiteSpace: "pre-wrap" }}>
      {parts.map((p, i) => {
        if (p.type === "text") return <span key={i}>{p.value}</span>;
        const v = p.value;
        // 변화율 (+/-NN%) — 양수=emerald, 음수=rose
        const pctMatch = v.match(/^([+\-]?)(\d+(?:\.\d+)?)\s*%$/);
        if (pctMatch) {
          const sign = pctMatch[1];
          const cls = sign === "-" ? "text-rose-700 bg-rose-100" :
                      sign === "+" ? "text-emerald-700 bg-emerald-100" :
                      "text-gray-700 bg-gray-100";
          return (
            <strong key={i} className={`${cls} px-1 py-0.5 rounded font-extrabold`}>
              {v}
            </strong>
          );
        }
        // 숫자 + 단위 (12,345 kg / 1500 mm / 7.82 g/cm³ 등) — indigo 강조
        if (/\d/.test(v) && /(kg|mm|g\/cm³|톤|개|매|건|단)/.test(v)) {
          return (
            <strong key={i} className="text-indigo-800 font-extrabold bg-indigo-50 px-1 rounded">
              {v}
            </strong>
          );
        }
        // Step N / 산식 키 (HR_MAX_WGT, slabWgt 등) — violet 굵기
        if (/^(Step\s*\d+|HR_|ORDER_|DESIGN_|slabWgt|secondWgtHigh|splitWgtHigh|maxSplit|optimalSplit|slabCount)/.test(v)) {
          return (
            <code key={i} className="text-violet-800 font-bold bg-violet-50 px-1 rounded text-[11.5px]">
              {v}
            </code>
          );
        }
        // 도메인 한국어 key term — gray-900 굵기
        return <strong key={i} className="text-gray-900 font-bold underline decoration-indigo-300 decoration-2 underline-offset-2">{v}</strong>;
      })}
    </span>
  );
}

function _MiniConfidenceChip({ evidence }: {
  evidence: {
    overall_confidence: number;
    source_breakdown_pct: Record<string, number>;
    fields?: Record<string, Array<{ kind: string; summary: string; source_ref?: string | null; detail?: string | null }>>;
  } | undefined;
}) {
  if (!evidence) return null;
  const conf = evidence.overall_confidence;
  const breakdown = evidence.source_breakdown_pct ?? {};
  const fields = evidence.fields ?? {};
  const top = Object.entries(breakdown).filter(([_, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]).slice(0, 3);
  const KIND_LABEL: Record<string, string> = {
    ontology: "온톨로지", business_rule: "업무규칙", seed_data: "seed", java_anchor: "java",
    propagation: "전파규칙", inference: "AI 추론", assumption: "가정",
  };
  const confColor =
    conf >= 0.85 ? "bg-emerald-100 text-emerald-800 border-emerald-300" :
    conf >= 0.7  ? "bg-cyan-100 text-cyan-800 border-cyan-300" :
    conf >= 0.5  ? "bg-amber-100 text-amber-800 border-amber-300" :
                   "bg-gray-100 text-gray-700 border-gray-300";
  // 각 chip 의 hover 시 — 해당 kind 의 근거 5건 모음
  function _evidenceFor(kind: string) {
    const items: Array<{ summary: string; source_ref?: string | null; detail?: string | null }> = [];
    for (const evs of Object.values(fields)) {
      for (const e of evs) {
        if (e.kind === kind) items.push(e);
        // ontology 카테고리는 business_rule/seed/java_anchor 도 포함
        else if (kind === "ontology" && ["business_rule","seed_data","java_anchor"].includes(e.kind)) items.push(e);
        // inference 카테고리는 propagation/assumption 포함
        else if (kind === "inference" && ["propagation","assumption"].includes(e.kind)) items.push(e);
      }
    }
    return items.slice(0, 5);
  }
  return (
    <span className="inline-flex items-center gap-1 flex-wrap">
      <span className={"text-[10px] px-1.5 py-0.5 rounded border font-semibold " + confColor}
            title={`종합 신뢰도 ${(conf * 100).toFixed(0)}% (1.0 = 사실 근거, 0.0 = 추측)`}>
        신뢰도 {(conf * 100).toFixed(0)}%
      </span>
      {top.map(([k, v]) => {
        const evList = _evidenceFor(k);
        return (
          <span key={k} className="group relative text-[10px] px-1 py-0.5 rounded bg-white border border-gray-200 text-gray-700 cursor-help">
            {KIND_LABEL[k] ?? k} <strong>{v}%</strong>
            {evList.length > 0 && (
              <span className="absolute left-0 top-full mt-1 z-40 hidden group-hover:block w-80 bg-white border-2 border-indigo-300 rounded-lg p-2.5 shadow-xl text-left">
                <div className="text-[11px] font-bold text-indigo-900 mb-1">
                  {KIND_LABEL[k] ?? k} 근거 ({evList.length}건)
                </div>
                <ul className="space-y-1 text-[10.5px] text-gray-800">
                  {evList.map((e, i) => (
                    <li key={i} className="border-l-2 border-indigo-200 pl-1.5">
                      <div className="font-semibold">{e.summary.slice(0, 80)}</div>
                      {e.source_ref && (
                        <code className="text-[9px] text-gray-500 break-all">{e.source_ref}</code>
                      )}
                      {e.detail && (
                        <div className="text-[10px] text-gray-600 italic mt-0.5">{e.detail.slice(0, 100)}</div>
                      )}
                    </li>
                  ))}
                </ul>
              </span>
            )}
          </span>
        );
      })}
    </span>
  );
}


function _ExplainView({ payload, codeMode = "open" }: { payload: Record<string, unknown>; codeMode?: "hide" | "collapsed" | "open" }) {
  const target = payload.target as Record<string, unknown> | undefined;
  const body = (payload.body as string | undefined) ?? "";
  const summary = payload.summary as string | undefined;
  const callers = (payload.callers as Array<Record<string, unknown>> | undefined) ?? [];
  const rules = (payload.business_rules as Array<Record<string, unknown>> | undefined) ?? [];
  const detectedTerms = (payload._detected_terms as Array<{
    token: string; term_fqn: string; label: string; definition: string; aliases?: string[];
  }> | undefined) ?? [];
  // 2026-05-23: Q1 — 단중 영향 변수 카탈로그
  const weightCatalog = payload._weight_catalog as {
    title: string; purpose: string; core_formula: string;
    external_constraint: string;
    variables: {
      variable: string; table_column: string; direction: string;
      formula_role: string; rationale: string; constraint: string;
      controllable_by: string;
    }[];
    ontology_terms: { fqn: string; label: string; description: string; aliases: string[]; kind: string }[];
    controllable_summary: { priority: string; items: string[]; note: string }[];
  } | undefined;
  // 2026-05-22: term-first 답변 — backend 가 atomic term 의 ontology fan-out 첨부
  // 2026-05-25: nested array 가 undefined 일 때 throw 차단 — defaults 적용
  const termExplainRaw = payload._term_explain as {
    term_fqn?: string;
    term?: Record<string, unknown> | null;
    effective_parts?: Record<string, unknown>[];
    related_actions?: { fqn: string; label: string; kind: string; description: string }[];
    business_rules?: { fqn: string; statement: string; severity: string; enforced_by: string[] }[];
    anchor_bindings?: { anchor_id: string; method_fqn: string; target_slot: string; anchor_locator: string; line: number | null }[];
  } | undefined;
  const termExplain = termExplainRaw ? {
    term_fqn: termExplainRaw.term_fqn ?? "",
    term: termExplainRaw.term ?? null,
    effective_parts: termExplainRaw.effective_parts ?? [],
    related_actions: termExplainRaw.related_actions ?? [],
    business_rules: termExplainRaw.business_rules ?? [],
    anchor_bindings: termExplainRaw.anchor_bindings ?? [],
  } : undefined;
  const primarySource = (payload._explain_primary_source as string | undefined) ?? "method";

  const targetClass = String(target?.code_method_fqn ?? "").split("(")[0].split(".").slice(-2, -1)[0] ?? "";
  const targetMethod = String(target?.code_method_fqn ?? "").split("(")[0].split(".").pop() ?? "";

  // 답변 보조 텍스트 — summary 가 없거나 약할 때, detected term 으로 자연어 답을 합성
  const fallbackAnswer = (() => {
    if (summary && summary.length > 30) return null;
    if (detectedTerms.length === 0) return null;
    const t = detectedTerms[0];
    const alias = (t.aliases ?? []).filter((a) => a !== t.label).slice(0, 4).join(", ");
    return (
      <>
        <span className="font-semibold">{t.token}</span> 은(는) ontology 용어{" "}
        <span className="font-semibold text-violet-800">{t.label}</span>
        {alias && (<span className="text-gray-600"> (별칭: {alias})</span>)}
        {t.definition && (<span className="block mt-1 text-gray-700">{t.definition}</span>)}
      </>
    );
  })();

  return (
    <>
      {/* 큰 답변 박스 — chat 이 더 수용 + 신뢰도 chip inline */}
      <div className="bg-gradient-to-br from-violet-50 to-purple-50 border-2 border-violet-200 rounded-lg p-3 shadow-sm">
        <div className="flex items-start gap-2">
          <div className="text-xl">💬</div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="text-[10px] uppercase tracking-wide text-violet-700 font-semibold">답변</span>
              <_MiniConfidenceChip evidence={payload._evidence as never} />
            </div>
            <div className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {summary && summary.length > 30 ? summary
                : fallbackAnswer ? fallbackAnswer
                : (target ? `${targetClass}.${targetMethod} 에 대한 설명입니다. 본문은 아래 코드 카드를 참고하세요.` :
                    "해당 의미에 대한 정확한 답변을 ontology 가 합성하지 못했습니다. 다른 표현으로 다시 시도해 주세요.")}
            </div>
          </div>
        </div>
      </div>

      {/* 🆕 Q1 — slab 단중 영향 변수 카탈로그 (사용자 명시 2026-05-23) */}
      {weightCatalog && (
        <div className="border-2 border-emerald-300 bg-gradient-to-br from-emerald-50/60 to-teal-50/40 rounded-lg p-3 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-700 text-white font-semibold">CATALOG</span>
            <span className="text-sm font-bold text-emerald-900">{weightCatalog.title}</span>
          </div>
          <div className="text-[11px] text-emerald-800 italic">목적: {weightCatalog.purpose}</div>

          {/* 핵심 공식 / 외부 제약 */}
          <div className="grid grid-cols-1 gap-2">
            <div className="bg-white/80 rounded p-2 border border-emerald-200">
              <div className="text-[9px] text-emerald-700 uppercase font-semibold mb-1">핵심 공식</div>
              <code className="text-[12px] text-emerald-900 font-mono">{weightCatalog.core_formula}</code>
            </div>
            <div className="bg-white/80 rounded p-2 border border-amber-200">
              <div className="text-[9px] text-amber-700 uppercase font-semibold mb-1">외부 제약 (단중 상하한)</div>
              <code className="text-[12px] text-amber-900 font-mono">{weightCatalog.external_constraint}</code>
            </div>
          </div>

          {/* 변수 카탈로그 — 영향 방향 + 통제 가능성 */}
          <div className="bg-white/80 rounded border border-emerald-200">
            <div className="px-2 py-1.5 bg-emerald-100/60 text-[10.5px] font-semibold text-emerald-900 border-b border-emerald-200">
              영향 변수 ({weightCatalog.variables.length}개)
            </div>
            <table className="w-full text-[10.5px]">
              <thead className="bg-emerald-50">
                <tr className="border-b border-emerald-200 text-emerald-700">
                  <th className="text-left p-1.5 font-semibold">변수</th>
                  <th className="text-left p-1.5 font-semibold">단중 방향</th>
                  <th className="text-left p-1.5 font-semibold">출처 (table·column)</th>
                  <th className="text-left p-1.5 font-semibold">제약 / 통제</th>
                </tr>
              </thead>
              <tbody>
                {weightCatalog.variables.map((v, i) => (
                  <tr key={i} className="border-b border-emerald-100 align-top hover:bg-emerald-50/40">
                    <td className="p-1.5 font-semibold text-emerald-900">{v.variable}</td>
                    <td className="p-1.5">
                      <span className={"text-[10px] px-1.5 py-0.5 rounded border " + (
                        v.direction.includes("비례") && !v.direction.includes("반비례")
                          ? "bg-emerald-100 text-emerald-800 border-emerald-300"
                          : v.direction.includes("반비례")
                          ? "bg-orange-100 text-orange-800 border-orange-300"
                          : "bg-gray-100 text-gray-700 border-gray-300"
                      )}>{v.direction}</span>
                      <div className="text-[9px] text-gray-600 mt-0.5 font-mono">{v.formula_role}</div>
                    </td>
                    <td className="p-1.5">
                      <code className="text-[10px] bg-emerald-50 px-1 rounded text-emerald-900 break-all">
                        {v.table_column}
                      </code>
                      <div className="text-[10px] text-gray-700 mt-0.5 leading-tight">{v.rationale}</div>
                    </td>
                    <td className="p-1.5">
                      <div className="text-[10px] text-amber-800 bg-amber-50 rounded p-1 mb-0.5">⚠ {v.constraint}</div>
                      <div className="text-[10px] text-emerald-700">✦ {v.controllable_by}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 통제 가능성 별 priority */}
          <div className="grid grid-cols-3 gap-2">
            {weightCatalog.controllable_summary.map((c, i) => (
              <div key={i} className={
                "rounded p-2 border " + (
                  i === 0 ? "bg-emerald-100/60 border-emerald-300" :
                  i === 1 ? "bg-amber-100/60 border-amber-300" :
                  "bg-rose-100/40 border-rose-300"
                )
              }>
                <div className="text-[10.5px] font-bold mb-1">{c.priority}</div>
                <ul className="text-[10px] space-y-0.5">
                  {c.items.map((it, j) => (
                    <li key={j} className="text-gray-800">• {it}</li>
                  ))}
                </ul>
                <div className="text-[9px] text-gray-600 mt-1 italic">{c.note}</div>
              </div>
            ))}
          </div>

          {/* ontology terms hit */}
          {weightCatalog.ontology_terms.length > 0 && (
            <details className="bg-white/70 rounded border border-emerald-200">
              <summary className="cursor-pointer px-2 py-1 text-[10.5px] text-emerald-900 font-semibold">
                ontology 매칭 term ({weightCatalog.ontology_terms.length})
              </summary>
              <ul className="px-2 pb-2 space-y-1">
                {weightCatalog.ontology_terms.map((t) => (
                  <li key={t.fqn} className="border-l-2 border-emerald-300 pl-1.5 text-[10px]">
                    <div className="flex items-baseline gap-1 flex-wrap">
                      <span className="font-semibold text-emerald-900">{t.label}</span>
                      <code className="text-[9px] text-gray-500">{t.fqn}</code>
                      <span className="text-[9px] text-gray-500">{t.kind}</span>
                    </div>
                    {t.description && (
                      <div className="text-gray-700 mt-0.5">{t.description}</div>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {/* atomic term ontology 근거 — collapsed (사용자 요구 2026-05-25: hover/펼치기로만 노출) */}
      {termExplain && termExplain.term && (
        <details className="border border-violet-200 bg-violet-50/40 rounded-lg">
          <summary className="cursor-pointer px-3 py-2 flex items-baseline gap-2 flex-wrap text-[12px] hover:bg-violet-100/40 rounded-lg">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-700 text-white font-semibold">📚 ontology 근거</span>
            <span className="font-bold text-violet-900">{String(termExplain.term.label ?? "")}</span>
            <code className="text-[10px] text-gray-500 font-mono">{termExplain.term_fqn}</code>
            <span className="ml-auto text-[10px] text-gray-500">
              {String(termExplain.term.kind ?? "")}
              {termExplain.term.value_type ? ` · ${termExplain.term.value_type}` : ""}
              {" · 펼치기"}
            </span>
          </summary>
          <div className="px-3 pb-3 pt-1 space-y-2">
          {(termExplain.term.aliases as string[] | undefined) && (termExplain.term.aliases as string[]).length > 0 && (
            <div className="flex items-baseline gap-1 flex-wrap">
              <span className="text-[10px] text-gray-500">aliases:</span>
              {(termExplain.term.aliases as string[]).map((a) => (
                <code key={a} className="text-[10px] px-1 rounded bg-white border border-violet-200 text-violet-900">{a}</code>
              ))}
            </div>
          )}
          {(termExplain.term.description as string | undefined) && (
            <div className="text-[11.5px] text-gray-800 leading-relaxed bg-white/60 rounded p-2 border border-violet-100">
              {String(termExplain.term.description)}
            </div>
          )}
          <div className="grid grid-cols-3 gap-2 text-[10.5px]">
            <div className="bg-white/70 rounded p-1.5 border border-violet-100">
              <div className="text-[9px] text-gray-500 uppercase">value_type</div>
              <div className="font-mono text-violet-900">{String(termExplain.term.value_type ?? "—")}</div>
            </div>
            <div className="bg-white/70 rounded p-1.5 border border-violet-100">
              <div className="text-[9px] text-gray-500 uppercase">unit</div>
              <div className="font-mono text-violet-900">{String(termExplain.term.unit ?? "—")}</div>
            </div>
            <div className="bg-white/70 rounded p-1.5 border border-violet-100">
              <div className="text-[9px] text-gray-500 uppercase">domain</div>
              <div className="font-mono text-violet-900">{String(termExplain.term.domain ?? "—")}</div>
            </div>
          </div>

          {/* 관련 action — 디폴트 닫힘 */}
          {termExplain.related_actions.length > 0 && (
            <details className="bg-white/70 rounded border border-violet-100">
              <summary className="cursor-pointer px-2 py-1 text-[11px] text-violet-900 font-semibold hover:text-violet-700">
                ⋯ 관련 ontology action ({termExplain.related_actions.length}) — 펼치기
              </summary>
              <ul className="px-2 pb-2 space-y-1">
                {termExplain.related_actions.slice(0, 8).map((a) => (
                  <li key={a.fqn} className="border-l-2 border-violet-300 pl-1.5">
                    <div className="flex items-baseline gap-1">
                      <span className="text-[9px] px-1 rounded bg-purple-100 text-purple-800">{a.kind}</span>
                      <span className="text-[11px] font-semibold text-purple-900">{a.label}</span>
                    </div>
                    <code className="text-[9px] text-gray-500 break-all">{a.fqn}</code>
                    {a.description && (
                      <div className="text-[10px] text-gray-700 mt-0.5">
                        {a.description.length > 160 ? a.description.slice(0, 160) + "..." : a.description}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {/* business rules — 디폴트 닫힘 */}
          {termExplain.business_rules.length > 0 && (
            <details className="bg-white/70 rounded border border-amber-200">
              <summary className="cursor-pointer px-2 py-1 text-[11px] text-amber-900 font-semibold hover:text-amber-700">
                ⋯ 적용 업무 규칙 ({termExplain.business_rules.length}) — 펼치기
              </summary>
              <ul className="px-2 pb-2 space-y-1">
                {termExplain.business_rules.slice(0, 6).map((r) => (
                  <li key={r.fqn} className="border-l-2 border-amber-300 pl-1.5">
                    <div className="flex items-baseline gap-1 flex-wrap">
                      <span className={"text-[9px] px-1 rounded " + (
                        r.severity === "hard" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-800"
                      )}>{r.severity}</span>
                      <code className="text-[9px] text-gray-700">{r.fqn}</code>
                    </div>
                    <div className="text-[10.5px] text-gray-800">{r.statement}</div>
                  </li>
                ))}
              </ul>
            </details>
          )}

          {/* anchor bindings — code 모드 hide 면 가리기 */}
          {termExplain.anchor_bindings.length > 0 && codeMode !== "hide" && (
            <details className="bg-white/70 rounded border border-emerald-200">
              <summary className="cursor-pointer px-2 py-1 text-[11px] text-emerald-900 font-semibold">
                anchor bindings — Java 코드 attach 지점 ({termExplain.anchor_bindings.length})
              </summary>
              <ul className="px-2 pb-2 space-y-1">
                {termExplain.anchor_bindings.slice(0, 6).map((ab) => (
                  <li key={ab.anchor_id} className="border-l-2 border-emerald-300 pl-1.5">
                    <div className="flex items-baseline gap-1 flex-wrap">
                      <code className="text-[9px] text-emerald-800 font-semibold">{ab.anchor_id}</code>
                      {ab.line !== null && <span className="text-[9px] text-gray-500">L{ab.line}</span>}
                    </div>
                    <code className="text-[9px] text-gray-600 break-all block">{ab.method_fqn}</code>
                    <div className="text-[10px] text-gray-700">slot: <code>{ab.target_slot}</code></div>
                    {ab.anchor_locator && (
                      <code className="text-[9px] bg-gray-50 px-1 rounded text-gray-700">{ab.anchor_locator}</code>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}
          </div>
        </details>
      )}

      {/* 질문에서 짚어낸 온톨로지 용어 — chip 한 줄, hover 시 상세 tooltip */}
      {!termExplain && detectedTerms.length > 0 && (
        <div className="bg-fuchsia-50/40 border border-fuchsia-200 rounded-lg p-2 flex items-center gap-2 flex-wrap">
          <span className="text-[11px] text-fuchsia-800 font-semibold">📚 온톨로지 근거</span>
          <span className="text-[10.5px] text-fuchsia-700">질문에서 짚어낸 온톨로지 용어 {detectedTerms.length}개</span>
          <div className="flex gap-1 flex-wrap">
            {detectedTerms.map((t) => (
              <span
                key={t.term_fqn}
                className="group relative text-[10.5px] px-2 py-0.5 rounded bg-fuchsia-100 text-fuchsia-900 border border-fuchsia-200 cursor-help hover:bg-fuchsia-200"
                title={`${t.label}\n${t.definition ?? ""}${(t.aliases?.length ?? 0) > 1 ? "\n다른 이름: " + (t.aliases ?? []).filter((a) => a !== t.label).slice(0, 4).join(", ") : ""}`}
              >
                {t.label}
                <span className="absolute left-0 top-full mt-1 z-30 hidden group-hover:block w-72 bg-white border-2 border-fuchsia-300 rounded-lg p-2.5 shadow-xl text-left">
                  <strong className="text-[12px] text-fuchsia-900">{t.label}</strong>
                  <span className="ml-1 text-[10px] text-gray-500 font-mono">{t.term_fqn}</span>
                  {t.definition && (
                    <div className="text-[11px] text-gray-700 mt-1 leading-relaxed">
                      {t.definition.length > 220 ? t.definition.slice(0, 220) + "…" : t.definition}
                    </div>
                  )}
                  {(t.aliases?.length ?? 0) > 1 && (
                    <div className="text-[10px] text-gray-500 mt-1.5">
                      다른 이름: <span className="text-fuchsia-700">{(t.aliases ?? []).filter((a) => a !== t.label).slice(0, 5).join(" · ")}</span>
                    </div>
                  )}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 관련 객체 카드 grid — weightCatalog (Q1) 답변엔 CODE 카드 자체 hide */}
      <div className="grid grid-cols-2 gap-2">
        {/* code 카드: weightCatalog 가 있으면 (Q1) 관련 없으므로 표시 안 함.
            현업 모드(collapsed) 면 details 안에 접힘, IT 모드(open) 면 펼침 표시. */}
        {target && !weightCatalog && codeMode !== "hide" && body && (
          codeMode === "collapsed" ? (
            <details className="border-2 border-emerald-200 bg-emerald-50/50 rounded p-2 col-span-2">
              <summary className="cursor-pointer flex items-center gap-1.5">
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-600 text-white font-semibold">
                  CODE{primarySource === "term" ? " (참고 — 자동 매칭)" : ""}
                </span>
                <code className="text-[11px] font-mono text-emerald-900">
                  {targetClass}.{targetMethod}
                </code>
                <span className="ml-auto text-[9px] text-emerald-700">상세 펼치기</span>
              </summary>
              <pre className="mt-2 text-[10.5px] bg-white border border-emerald-200 rounded p-2 overflow-auto text-gray-800 max-h-72">
                {body.slice(0, 1500) || "(본문 없음)"}
              </pre>
            </details>
          ) : (
            <div className="border-2 border-emerald-200 bg-emerald-50/50 rounded p-2 col-span-2">
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-600 text-white font-semibold">
                  CODE{primarySource === "term" ? " (참고 — 자동 매칭)" : ""}
                </span>
                <code className="text-[11px] font-mono text-emerald-900">
                  {targetClass}.{targetMethod}
                </code>
                {primarySource === "term" && (
                  <span className="text-[9px] text-gray-500 ml-auto">term 답변과 직접 관련은 적을 수 있음</span>
                )}
              </div>
              <pre className="text-[10.5px] bg-white border border-emerald-200 rounded p-2 overflow-auto text-gray-800 max-h-72">
                {body.slice(0, 1500) || "(본문 없음)"}
              </pre>
            </div>
          )
        )}

        {/* 적용되는 업무 규칙 — chip + hover 상세 (정보색 indigo) */}
        {rules.length > 0 && (
          <div className="bg-indigo-50/40 border border-indigo-200 rounded-lg p-2 col-span-2 flex items-center gap-2 flex-wrap">
            <span className="text-[11px] text-indigo-900 font-semibold">📘 온톨로지 근거</span>
            <span className="text-[10.5px] text-indigo-700">적용 업무 규칙 {rules.length}개</span>
            <div className="flex gap-1 flex-wrap">
              {rules.slice(0, 8).map((r, i) => {
                const sev = String(r.severity ?? "soft");
                const isHard = sev === "hard";
                const fqn = String(r.fqn ?? "");
                const shortName = fqn.split(".").slice(-2).join(".") || `규칙 #${i + 1}`;
                return (
                  <span key={i}
                    className={"group relative text-[10.5px] px-2 py-0.5 rounded border cursor-help " + (
                      isHard ? "bg-red-100 text-red-900 border-red-300 hover:bg-red-200"
                             : "bg-amber-100 text-amber-900 border-amber-300 hover:bg-amber-200"
                    )}
                    title={`${isHard ? "절대 위반 불가" : "권장 규칙"}\n${String(r.statement ?? "")}`}
                  >
                    {isHard ? "🔴" : "🟡"} {shortName}
                    <span className="absolute left-0 top-full mt-1 z-30 hidden group-hover:block w-80 bg-white border-2 border-rose-300 rounded-lg p-2.5 shadow-xl text-left">
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className={"text-[9px] px-1.5 py-0.5 rounded font-bold " + (
                          isHard ? "bg-red-600 text-white" : "bg-amber-400 text-amber-900"
                        )}>{isHard ? "절대 위반 불가" : "권장"}</span>
                        <code className="text-[9.5px] text-gray-500 font-mono">{fqn}</code>
                      </div>
                      <div className="text-[11.5px] text-gray-800 leading-relaxed">
                        {String(r.statement ?? "")}
                      </div>
                    </span>
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {/* 이걸 호출하는 곳 — chip + hover 상세 */}
        {callers.length > 0 && (
          <div className="bg-sky-50/40 border border-sky-200 rounded-lg p-2 col-span-2 flex items-center gap-2 flex-wrap">
            <span className="text-[11px] text-sky-900 font-semibold">🔗 온톨로지 근거</span>
            <span className="text-[10.5px] text-sky-700">변경 시 같이 영향받는 호출 위치 {callers.length}개</span>
            <div className="flex gap-1 flex-wrap">
              {callers.slice(0, 10).map((c, i) => {
                const fqn = String((c?.fqn ?? c?.method_fqn ?? c?.code_method_fqn ?? "") || "");
                const distance = c?.distance !== undefined ? Number(c.distance) : 1;
                const display = fqn.split("(")[0].split(".").slice(-2).join(".") || "(미상)";
                const distanceLabel = distance === 1 ? "직접 호출" : `${distance} 단계`;
                return (
                  <span key={i}
                    className="group relative text-[10.5px] px-2 py-0.5 rounded bg-sky-100 text-sky-900 border border-sky-200 cursor-help hover:bg-sky-200 font-mono"
                    title={`${distanceLabel}\n${fqn}`}
                  >
                    ← {display}
                    <span className="absolute left-0 top-full mt-1 z-30 hidden group-hover:block w-96 bg-white border-2 border-sky-300 rounded-lg p-2.5 shadow-xl text-left">
                      <div className="text-[10.5px] text-sky-700 font-semibold mb-1">{distanceLabel}로 영향받는 위치</div>
                      <code className="text-[10.5px] text-gray-800 break-all">{fqn}</code>
                    </span>
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// _FullDesignView — Java :8080 의 /api/sd/working/single 결과
// ─────────────────────────────────────────────────────────────────────────────

function _FullDesignView({ payload, codeMode = "open" }: { payload: Record<string, unknown>; codeMode?: "hide" | "collapsed" | "open" }) {
  const orderNo = payload.order_no as string;
  const slabResults = (payload.slab_results as Array<Record<string, unknown>> | undefined) ?? [];
  const trace = (payload.trace as Array<Record<string, unknown>> | undefined) ?? [];
  const errorCode = payload.error_code as string | null;
  const errorMessage = payload.error_message as string | null;
  const ok = payload.ok as boolean;

  const statusCounts: Record<string, number> = {};
  for (const t of trace) {
    const s = String(t.status);
    statusCounts[s] = (statusCounts[s] || 0) + 1;
  }

  return (
    <>
      <div className="bg-gradient-to-r from-emerald-600 to-emerald-700 text-white rounded-lg p-3 shadow">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-wide opacity-80">주문</div>
            <div className="text-lg font-mono font-bold">{orderNo}</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wide opacity-80">설계 결과</div>
            <div className="text-lg font-bold">
              {ok && !errorCode ? `Slab ${slabResults.length}매 SUCCESS` : `FAIL ${errorCode || ""}`}
            </div>
          </div>
        </div>
      </div>

      {!ok && errorCode && (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          ⚠ {errorCode}: {errorMessage}
        </div>
      )}

      {slabResults.map((slab, i) => (
        <_SlabResultCard key={i} slab={slab} index={i + 1} />
      ))}

      {trace.length > 0 && (
        <div className="border border-gray-200 rounded">
          <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
            <strong className="text-xs text-gray-800">21-step 알고리즘 실행 진행도</strong>
            <div className="flex gap-1.5 text-[10px]">
              {Object.entries(statusCounts).map(([s, n]) => (
                <span key={s} className={
                  "px-1.5 py-0.5 rounded font-semibold " + (
                    s === "OK" ? "bg-emerald-100 text-emerald-800" :
                    s === "RETRY" ? "bg-amber-100 text-amber-800" :
                    s === "FAIL" ? "bg-red-100 text-red-800" :
                    s === "SKIP" ? "bg-gray-100 text-gray-600" : "bg-gray-100 text-gray-600"
                  )
                }>{s} {n}</span>
              ))}
            </div>
          </div>
          <_TraceGantt trace={trace} />
        </div>
      )}

      <div className="text-[10px] text-gray-400 mt-2">
        Java :8080 /api/sd/working/single?trace=true · 21-step 알고리즘 전체 실행
      </div>
    </>
  );
}

/** Slab 1매 — SVG 원면도 + KPI 4종 + 허용범위 미니바 + 전체 필드. */
function _SlabResultCard({ slab, index }: { slab: Record<string, unknown>; index: number }) {
  const thickness = Number(slab.slabThickness ?? 0);
  const width = Number(slab.slabWidth ?? 0);
  const length = Number(slab.slabLength ?? 0);
  const wgt = Number(slab.slabWgt ?? 0);
  const splitCount = Number(slab.splitCount ?? 0);
  const status = String(slab.designStatus ?? "?");

  const maxDim = Math.max(width, length, 1);
  const scale = 200 / maxDim;
  const l = length * scale;
  const w = Math.max(width * scale * 0.3, 20);
  const t = Math.max(thickness * 0.06, 6);

  const RangeBar = ({ label, value, low, high, unit }: {
    label: string; value: number; low: number; high: number; unit: string;
  }) => {
    const range = high - low || 1;
    const pct = Math.max(0, Math.min(100, ((value - low) / range) * 100));
    return (
      <div>
        <div className="flex items-baseline justify-between text-[10px]">
          <span className="text-gray-500">{label}</span>
          <span className="text-emerald-700 font-mono font-semibold">
            {value.toLocaleString(undefined,{maximumFractionDigits:1})}{unit}
          </span>
        </div>
        <div className="h-2 bg-gray-100 rounded relative">
          <div className="absolute h-2 bg-emerald-500 rounded-sm" style={{ left: `${pct}%`, width: 4 }} />
        </div>
        <div className="flex justify-between text-[9px] text-gray-400 font-mono mt-0.5">
          <span>{low.toLocaleString(undefined,{maximumFractionDigits:0})}</span>
          <span>{high.toLocaleString(undefined,{maximumFractionDigits:0})}{unit}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="border-2 border-emerald-300 rounded-lg bg-white shadow-sm">
      <div className="px-3 py-2 bg-emerald-50 border-b border-emerald-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <strong className="text-emerald-900 text-sm">Slab #{index}</strong>
          <code className="text-[10px] text-emerald-700">slabNo {String(slab.slabNo)}</code>
        </div>
        <span className={
          "text-[10px] px-2 py-0.5 rounded font-semibold " +
          (status === "SUCCESS" ? "bg-emerald-600 text-white" : "bg-red-600 text-white")
        }>{status}</span>
      </div>

      <div className="grid grid-cols-[210px_1fr] gap-3 p-3">
        <div className="flex flex-col items-center">
          <svg viewBox="0 0 240 200" width="200" height="170">
            <defs>
              <linearGradient id={`g${index}`} x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#fbbf24" />
                <stop offset="100%" stopColor="#d97706" />
              </linearGradient>
            </defs>
            <rect x={(240 - l) / 2} y="70" width={l} height={t} fill={`url(#g${index})`} stroke="#92400e" strokeWidth="1" />
            <text x="120" y="66" textAnchor="middle" fontSize="9" fill="#92400e">길이 {length.toLocaleString()} mm</text>
            <text x={(240 - l) / 2 - 3} y={75 + t / 2} textAnchor="end" fontSize="8" fill="#92400e">↑{thickness}mm</text>
            <rect x={(240 - l) / 2} y="105" width={l} height={w} fill="#fef3c7" stroke="#92400e" strokeWidth="1" strokeDasharray="2 2" />
            <text x="120" y={105 + w + 12} textAnchor="middle" fontSize="9" fill="#92400e">폭 {width.toLocaleString()} mm</text>
          </svg>
          <div className="text-[9px] text-gray-400 mt-1">schematic · 비율 아님</div>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-2 text-center">
            <div className="bg-amber-50 rounded p-2 border border-amber-200">
              <div className="text-[9px] text-amber-700">두께</div>
              <div className="text-sm font-mono font-bold text-amber-900">{thickness}</div>
              <div className="text-[9px] text-amber-600">mm</div>
            </div>
            <div className="bg-sky-50 rounded p-2 border border-sky-200">
              <div className="text-[9px] text-sky-700">폭</div>
              <div className="text-sm font-mono font-bold text-sky-900">{width.toLocaleString()}</div>
              <div className="text-[9px] text-sky-600">mm</div>
            </div>
            <div className="bg-violet-50 rounded p-2 border border-violet-200">
              <div className="text-[9px] text-violet-700">길이</div>
              <div className="text-sm font-mono font-bold text-violet-900">{length.toLocaleString()}</div>
              <div className="text-[9px] text-violet-600">mm</div>
            </div>
            <div className="bg-emerald-50 rounded p-2 border border-emerald-200">
              <div className="text-[9px] text-emerald-700">단중</div>
              <div className="text-sm font-mono font-bold text-emerald-900">
                {wgt.toLocaleString(undefined,{maximumFractionDigits:1})}
              </div>
              <div className="text-[9px] text-emerald-600">kg · {splitCount}분할</div>
            </div>
          </div>

          {slab.slabWidthLow !== undefined && slab.slabWidthHigh !== undefined && (
            <RangeBar label="폭 허용범위 안 위치" value={width}
              low={Number(slab.slabWidthLow)} high={Number(slab.slabWidthHigh)} unit="mm" />
          )}
          {slab.slabWgtLow !== undefined && slab.slabWgtHigh !== undefined && (
            <RangeBar label="단중 허용범위 안 위치" value={wgt}
              low={Number(slab.slabWgtLow)} high={Number(slab.slabWgtHigh)} unit="kg" />
          )}
        </div>
      </div>

      <details className="border-t border-emerald-200">
        <summary className="px-3 py-1.5 text-[11px] text-emerald-800 cursor-pointer hover:bg-emerald-50/80">
          전체 필드 보기 ({Object.keys(slab).length}건)
        </summary>
        <div className="p-2 max-h-64 overflow-auto">
          <table className="w-full text-[10px]">
            <tbody>
              {Object.entries(slab).map(([k, v]) => (
                <tr key={k} className="border-b border-emerald-100">
                  <td className="py-0.5 pr-2 text-gray-500 font-mono">{k}</td>
                  <td className="py-0.5 font-mono text-gray-800">
                    {v === null ? <span className="text-gray-300">null</span> :
                     typeof v === "number" ? v.toLocaleString(undefined,{maximumFractionDigits:6}) :
                     String(v)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

/** 21-step gantt 스타일 진행도. */
function _TraceGantt({ trace }: { trace: Array<Record<string, unknown>> }) {
  type StepBar = { step: number; stepName: string; rows: Array<Record<string, unknown>>; finalStatus: string };
  const byStep: Record<number, StepBar> = {};
  for (const t of trace) {
    const n = Number(t.step);
    if (!byStep[n]) byStep[n] = { step: n, stepName: String(t.stepName), rows: [], finalStatus: String(t.status) };
    byStep[n].rows.push(t);
    byStep[n].finalStatus = String(t.status);
  }
  const steps = Object.values(byStep).sort((a, b) => a.step - b.step);

  return (
    <div className="p-2 space-y-0.5 max-h-72 overflow-y-auto">
      {steps.map((s) => {
        const color =
          s.finalStatus === "OK" ? "bg-emerald-500" :
          s.finalStatus === "RETRY" ? "bg-amber-500" :
          s.finalStatus === "FAIL" ? "bg-red-500" :
          s.finalStatus === "SKIP" ? "bg-gray-300" : "bg-gray-400";
        const hasRetry = s.rows.length > 1;
        return (
          <div key={s.step} className="flex items-center gap-2 text-[10px]" title={s.stepName}>
            <code className="w-7 text-right text-gray-500">{s.step}</code>
            <div className="w-40 truncate text-gray-700">{s.stepName.replace(/Action$/, "")}</div>
            <div className="flex-1 h-3 rounded bg-gray-100 relative overflow-hidden">
              <div className={"h-full " + color} style={{ width: "100%" }} />
              {hasRetry && (
                <div className="absolute inset-0 flex items-center justify-center text-[8px] font-bold text-white">
                  {s.rows.length}× iter
                </div>
              )}
            </div>
            <span className={
              "w-12 text-right font-semibold " + (
                s.finalStatus === "OK" ? "text-emerald-700" :
                s.finalStatus === "RETRY" ? "text-amber-700" :
                s.finalStatus === "FAIL" ? "text-red-700" :
                s.finalStatus === "SKIP" ? "text-gray-400" : "text-gray-500"
              )
            }>{s.finalStatus}</span>
          </div>
        );
      })}
    </div>
  );
}


function _CompareView({ payload, codeMode = "open" }: { payload: Record<string, unknown>; codeMode?: "hide" | "collapsed" | "open" }) {
  const before = payload.before_result as Record<string, unknown> | null;
  const after = payload.after_result as Record<string, unknown> | null;
  const diffs = (payload.field_diffs as Array<Record<string, unknown>> | undefined) ?? [];
  const summary = payload.summary as string | undefined;
  const changedCount = diffs.filter((d) => d.changed).length;

  return (
    <>
      <div className="text-sm font-semibold text-amber-800 bg-amber-50 border border-amber-300 rounded p-2">
        변경 전·후 비교 · {summary}
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div className="border border-gray-200 rounded">
          <div className="px-2 py-1 bg-gray-50 text-[11px] text-gray-600">변경 전</div>
          <pre className="p-2 text-[10px] max-h-40 overflow-auto">
            {JSON.stringify(before ?? {}, null, 2).slice(0, 600)}
          </pre>
        </div>
        <div className="border border-emerald-300 rounded">
          <div className="px-2 py-1 bg-emerald-50 text-[11px] text-emerald-800">변경 후</div>
          <pre className="p-2 text-[10px] max-h-40 overflow-auto">
            {JSON.stringify(after ?? {}, null, 2).slice(0, 600)}
          </pre>
        </div>
        <div className="border border-amber-300 rounded">
          <div className="px-2 py-1 bg-amber-50 text-[11px] text-amber-800">
            DIFF (변경 {changedCount}/{diffs.length})
          </div>
          <ul className="p-2 text-[10px] max-h-40 overflow-auto space-y-0.5">
            {diffs.filter((d) => d.changed).slice(0, 20).map((d, i) => (
              <li key={i} className="font-mono">
                <span className="text-gray-500">{String(d.field)}:</span>{" "}
                <span className="text-red-700 line-through">{JSON.stringify(d.before)}</span>{" "}
                →{" "}
                <span className="text-emerald-700">{JSON.stringify(d.after)}</span>
              </li>
            ))}
            {changedCount === 0 && <li className="text-gray-400">변경 없음</li>}
          </ul>
        </div>
      </div>
    </>
  );
}

function _HypothesisView({ payload, codeMode = "open" }: { payload: Record<string, unknown>; codeMode?: "hide" | "collapsed" | "open" }) {
  // legacy multiturn hypothesis payload + 신규 hypothesis workflow 둘 다 처리
  const verdict = payload.verdict as string | undefined;
  const reasoning = payload.reasoning as string | undefined;

  const [hyp, setHyp] = useState<HypothesisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [params, setParams] = useState({
    base_grade: "SS400", new_grade: "SS500",
    productivity_multiplier: 0.95, base_order_no: "ORD20260510001",
  });
  const [error, setError] = useState<string | null>(null);

  // 자동 1회 호출 (default 파라미터)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    simulationApi.hypothesis(params)
      .then((d) => { if (!cancelled) setHyp(d); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function _rerun() {
    setLoading(true); setError(null);
    try {
      const d = await simulationApi.hypothesis(params);
      setHyp(d);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* 시나리오 헤더 */}
      <div className="bg-gradient-to-r from-rose-600 to-rose-700 text-white rounded-lg p-3 shadow">
        <div className="text-[10px] uppercase tracking-wide opacity-80">가설 검증</div>
        <div className="text-sm font-semibold mt-0.5">
          신규 강종 <code className="bg-white/20 px-1.5 py-0.5 rounded">{params.new_grade}</code> 가 추가되면
          <span className="opacity-80">
            {" "}({params.base_grade} 대비 productivity ×{params.productivity_multiplier})
          </span>
          {" "}→ <code className="bg-white/20 px-1.5 py-0.5 rounded">{params.base_order_no}</code> 의 Slab 결과는?
        </div>
      </div>

      {/* legacy multiturn 응답이 있으면 같이 표시 */}
      {(verdict || reasoning) && (
        <div className="text-xs bg-gray-50 border border-gray-200 rounded p-2">
          <div className="font-semibold text-gray-700">multiturn verdict: <span className={
            verdict === "passes" ? "text-emerald-700" :
            verdict === "fails" ? "text-red-700" : "text-amber-700"
          }>{verdict ?? "?"}</span></div>
          {reasoning && <div className="text-gray-600 mt-1">{reasoning}</div>}
        </div>
      )}

      {/* 파라미터 컨트롤 */}
      <details className="border border-gray-200 rounded text-[11px]">
        <summary className="px-2 py-1 bg-gray-50 cursor-pointer text-gray-700">파라미터 조정</summary>
        <div className="p-2 grid grid-cols-2 gap-2">
          {(["base_grade","new_grade","base_order_no"] as const).map((k) => (
            <label key={k} className="flex flex-col">
              <span className="text-gray-500">{k}</span>
              <input value={params[k] as string}
                onChange={(e) => setParams({...params, [k]: e.target.value})}
                className="px-1 py-0.5 border border-gray-300 rounded font-mono"/>
            </label>
          ))}
          <label className="flex flex-col">
            <span className="text-gray-500">productivity_multiplier</span>
            <input type="number" step="0.01" min="0.5" max="1.5"
              value={params.productivity_multiplier}
              onChange={(e) => setParams({...params, productivity_multiplier: parseFloat(e.target.value)})}
              className="px-1 py-0.5 border border-gray-300 rounded font-mono"/>
          </label>
          <button onClick={_rerun} disabled={loading}
            className="col-span-2 px-2 py-1 bg-rose-600 text-white rounded hover:bg-rose-500 disabled:opacity-50">
            {loading ? "분석 중..." : "재실행"}
          </button>
        </div>
      </details>

      {loading && (
        <div className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded p-2 flex items-center gap-1">
          <Loader2 size={12} className="animate-spin" /> 기존 데이터 분석 + 가상 합성 + 추론 진행 중...
        </div>
      )}
      {error && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">{error}</div>}

      {hyp && (
        <>
          {/* 4-step section */}
          <_HypoStep n={1} title="기존 데이터 분석" color="sky">
            <div className="text-[10px] text-gray-600 mb-1">
              <code className="bg-sky-100 px-1 rounded">{hyp.base_grade}</code> 강종의 SD_PRODUCTIVITY_STD {hyp.existing_productivity_rows.length}건
            </div>
            <table className="w-full text-[10px]">
              <thead><tr className="border-b border-sky-200">
                <th className="text-left p-0.5">PROC_CD</th>
                <th className="text-left p-0.5">CUSTOMER_CD</th>
                <th className="text-right p-0.5">PRODUCTIVITY</th>
              </tr></thead>
              <tbody>
                {hyp.existing_productivity_rows.slice(0, 12).map((r, i) => (
                  <tr key={i} className="border-b border-sky-100">
                    <td className="p-0.5 font-mono">{String(r.PROC_CD)}</td>
                    <td className="p-0.5 font-mono text-gray-500">{String(r.CUSTOMER_CD)}</td>
                    <td className="p-0.5 font-mono text-right">{String(r.PRODUCTIVITY)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </_HypoStep>

          <_HypoStep n={2} title="가상 강종 합성" color="amber">
            <div className="text-[10px] text-gray-600 mb-1">
              <code className="bg-amber-100 px-1 rounded">{hyp.new_grade}</code> ×{hyp.productivity_multiplier}
            </div>
            <table className="w-full text-[10px]">
              <thead><tr className="border-b border-amber-200">
                <th className="text-left p-0.5">PROC_CD</th>
                <th className="text-right p-0.5">기존</th>
                <th className="text-right p-0.5">가상</th>
              </tr></thead>
              <tbody>
                {hyp.virtual_productivity_rows.slice(0, 12).map((r, i) => {
                  const orig = hyp.existing_productivity_rows[i];
                  return (
                    <tr key={i} className="border-b border-amber-100">
                      <td className="p-0.5 font-mono">{String(r.PROC_CD)}</td>
                      <td className="p-0.5 font-mono text-right text-gray-500">{String(orig?.PRODUCTIVITY ?? "?")}</td>
                      <td className="p-0.5 font-mono text-right text-amber-700 font-semibold">{String(r.PRODUCTIVITY)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </_HypoStep>

          <_HypoStep n={3} title="가상 주문 합성" color="violet">
            <div className="text-[10px] text-gray-600">
              <code className="bg-violet-100 px-1 rounded">{hyp.base_order_no}</code> 4 table 복제 →
              ORDER_QD.GRADE_CD = <code className="bg-amber-100 px-1 rounded">{hyp.new_grade}</code> 만 변경
            </div>
            <ul className="text-[10px] mt-1 space-y-0.5">
              {Object.entries(hyp.virtual_order_rows).map(([t, row]) => (
                <li key={t} className="font-mono">
                  <span className="text-violet-700">{t}</span>
                  <span className="text-gray-400 ml-1">
                    {t === "ORDER_QD" ? `GRADE_CD=${row.GRADE_CD}` :
                     t === "ORDER_OM" ? `width=${row.ORDER_WIDTH} len=${row.ORDER_LENGTH} wgt=${row.ORDER_WGT_LOW}~${row.ORDER_WGT_HIGH}` :
                     `${Object.keys(row).length} 필드 복제`}
                  </span>
                </li>
              ))}
            </ul>
          </_HypoStep>

          <_HypoStep n={4} title="Slab 결과 비교 (추론)" color="emerald">
            {hyp.baseline_slab ? (
              <div className="space-y-2">
                <div className="grid grid-cols-3 gap-2 text-[10px]">
                  <div className="border border-gray-300 rounded p-1.5">
                    <div className="text-gray-500">기존 ({hyp.base_grade})</div>
                    <div className="font-mono">
                      두께 {hyp.baseline_slab.slabThickness as number} · 폭 {hyp.baseline_slab.slabWidth as number}
                    </div>
                    <div className="font-mono text-emerald-700 font-semibold">
                      단중 {Number(hyp.baseline_slab.slabWgt).toFixed(1)}kg
                    </div>
                  </div>
                  <div className="border border-amber-300 bg-amber-50 rounded p-1.5">
                    <div className="text-amber-700">가상 ({hyp.new_grade})</div>
                    <div className="font-mono">
                      두께 {hyp.projected_slab?.slabThickness as number} · 폭 {hyp.projected_slab?.slabWidth as number}
                    </div>
                    <div className="font-mono text-amber-800 font-semibold">
                      단중 {Number(hyp.projected_slab?.slabWgt ?? 0).toFixed(1)}kg
                    </div>
                  </div>
                  <div className="border border-red-300 bg-red-50 rounded p-1.5">
                    <div className="text-red-700">DIFF</div>
                    <div className="font-mono">두께 0 · 폭 0 (강종 무관)</div>
                    <div className="font-mono text-red-800 font-semibold">
                      단중 {hyp.diff_summary.find((d) => d.field === "slabWgt")?.delta_pct ?? 0}%
                    </div>
                  </div>
                </div>
                {hyp.diff_summary.length > 0 && (
                  <details className="text-[10px]">
                    <summary className="cursor-pointer text-gray-600">전체 diff ({hyp.diff_summary.length}건)</summary>
                    <table className="w-full mt-1">
                      <thead><tr className="border-b border-gray-300">
                        <th className="text-left p-0.5">field</th>
                        <th className="text-right p-0.5">before</th>
                        <th className="text-right p-0.5">after</th>
                        <th className="text-right p-0.5">%</th>
                      </tr></thead>
                      <tbody>
                        {hyp.diff_summary.map((d) => (
                          <tr key={d.field} className="border-b border-gray-100">
                            <td className="p-0.5 font-mono">{d.field}</td>
                            <td className="p-0.5 font-mono text-right">{d.before.toFixed(2)}</td>
                            <td className="p-0.5 font-mono text-right text-emerald-700">{d.after.toFixed(2)}</td>
                            <td className="p-0.5 font-mono text-right text-red-700">{d.delta_pct}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </details>
                )}
              </div>
            ) : (
              <div className="text-[10px] text-gray-400">baseline 실행 결과 없음</div>
            )}
          </_HypoStep>

          {hyp.notes.length > 0 && (
            <details className="text-[10px] border border-gray-200 rounded">
              <summary className="px-2 py-1 bg-gray-50 cursor-pointer text-gray-600">분석 노트 ({hyp.notes.length})</summary>
              <ul className="p-2 space-y-1">
                {hyp.notes.map((n, i) => <li key={i} className="text-gray-700">· {n}</li>)}
              </ul>
            </details>
          )}
        </>
      )}
    </>
  );
}

/** backend 가 직접 hypothesis_workflow 결과를 payload 로 보낸 경우 — fetch 없이 즉시 표시.
 *
 * 사용자 요구: SSE 스트리밍으로 4-step 순차 등장. payload 의 default 값으로 즉시 stream 시작.
 */
function _HypothesisWorkflowView({ payload, codeMode = "open" }: { payload: Record<string, unknown>; codeMode?: "hide" | "collapsed" | "open" }) {
  const initialHyp = payload as unknown as HypothesisResponse;
  // SSE 스트림으로 step 별 progressive 표시
  const [streamedStages, setStreamedStages] = useState<Record<number, Record<string, unknown>>>({});
  const [streaming, setStreaming] = useState(false);
  const [streamDone, setStreamDone] = useState(false);

  // payload 가 이미 데이터 가지고 있으면 stream 안 함 (initial render). 사용자가 "↻ 스트리밍 보기" 버튼 누를 때 시작.
  async function startStream() {
    setStreaming(true);
    setStreamDone(false);
    setStreamedStages({});
    try {
      const r = await fetch("/api/section3/simulation/hypothesis/stream", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          base_grade: initialHyp.base_grade, new_grade: initialHyp.new_grade,
          productivity_multiplier: initialHyp.productivity_multiplier,
          base_order_no: initialHyp.base_order_no,
        }),
      });
      if (!r.ok || !r.body) { setStreaming(false); return; }
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        // SSE: "data: {...}\n\n"
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const p of parts) {
          const m = p.match(/^data:\s*(.+)$/m);
          if (!m) continue;
          try {
            const evt = JSON.parse(m[1]);
            if (evt.stage === "done") { setStreamDone(true); continue; }
            // 250ms 딜레이로 사용자에게 단계가 보이도록
            await new Promise((res) => setTimeout(res, 400));
            setStreamedStages((s) => ({ ...s, [evt.stage]: evt.data }));
          } catch {}
        }
      }
    } finally {
      setStreaming(false);
      setStreamDone(true);
    }
  }

  // streamedStages 가 있으면 우선. 없으면 payload 값 사용
  const usingStream = Object.keys(streamedStages).length > 0;
  const hyp: HypothesisResponse = usingStream
    ? {
        ...initialHyp,
        existing_productivity_rows: (streamedStages[1]?.existing_productivity_rows as never) ?? [],
        existing_order_rows: (streamedStages[1]?.existing_order_rows as never) ?? {},
        virtual_productivity_rows: (streamedStages[2]?.virtual_productivity_rows as never) ?? [],
        virtual_order_rows: (streamedStages[3]?.virtual_order_rows as never) ?? {},
        baseline_slab: (streamedStages[4]?.baseline_slab as never) ?? null,
        baseline_trace: (streamedStages[4]?.baseline_trace as never) ?? [],
        projected_slab: (streamedStages[4]?.projected_slab as never) ?? null,
        diff_summary: (streamedStages[4]?.diff_summary as never) ?? [],
      }
    : initialHyp;

  // streaming 시 어떤 stage 까지 도달했는지
  const stagesDone = Object.keys(streamedStages).filter((k) => k !== "done").length;

  return (
    <>
      <div className="bg-gradient-to-r from-rose-600 to-rose-700 text-white rounded-lg p-3 shadow">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-[10px] uppercase tracking-wide opacity-80">가설 검증 — 자동 진행</div>
            <div className="text-sm font-semibold mt-0.5">
              신규 강종 <code className="bg-white/20 px-1.5 py-0.5 rounded">{hyp.new_grade}</code>
              {" "}({hyp.base_grade} 대비 productivity ×{hyp.productivity_multiplier}) →
              {" "}<code className="bg-white/20 px-1.5 py-0.5 rounded">{hyp.base_order_no}</code> 의 Slab 결과
            </div>
          </div>
          <button onClick={startStream} disabled={streaming}
            className="px-2.5 py-1 bg-white/20 hover:bg-white/30 rounded text-[11px] font-semibold disabled:opacity-50">
            {streaming ? `▶ ${stagesDone}/4 stream...` : streamDone ? "↻ 다시" : "▶ SSE stream"}
          </button>
        </div>
      </div>

      <_HypoStep n={1} title="기존 데이터 분석" color="sky">
        <div className="text-[10px] text-gray-600 mb-1">
          <code className="bg-sky-100 px-1 rounded">{hyp.base_grade}</code> 강종의 SD_PRODUCTIVITY_STD {hyp.existing_productivity_rows.length}건
        </div>
        <table className="w-full text-[10px]">
          <thead><tr className="border-b border-sky-200">
            <th className="text-left p-0.5">PROC_CD</th>
            <th className="text-left p-0.5">CUSTOMER_CD</th>
            <th className="text-right p-0.5">PRODUCTIVITY</th>
          </tr></thead>
          <tbody>
            {hyp.existing_productivity_rows.slice(0, 10).map((r, i) => (
              <tr key={i} className="border-b border-sky-100">
                <td className="p-0.5 font-mono">{String(r.PROC_CD)}</td>
                <td className="p-0.5 font-mono text-gray-500">{String(r.CUSTOMER_CD)}</td>
                <td className="p-0.5 font-mono text-right">{String(r.PRODUCTIVITY)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </_HypoStep>

      <_HypoStep n={2} title="가상 강종 합성" color="amber">
        <div className="text-[10px] text-gray-600 mb-1">
          <code className="bg-amber-100 px-1 rounded">{hyp.new_grade}</code> ×{hyp.productivity_multiplier}
        </div>
        <table className="w-full text-[10px]">
          <thead><tr className="border-b border-amber-200">
            <th className="text-left p-0.5">PROC_CD</th>
            <th className="text-right p-0.5">기존</th>
            <th className="text-right p-0.5">가상</th>
          </tr></thead>
          <tbody>
            {hyp.virtual_productivity_rows.slice(0, 10).map((r, i) => {
              const orig = hyp.existing_productivity_rows[i];
              return (
                <tr key={i} className="border-b border-amber-100">
                  <td className="p-0.5 font-mono">{String(r.PROC_CD)}</td>
                  <td className="p-0.5 font-mono text-right text-gray-500">{String(orig?.PRODUCTIVITY ?? "?")}</td>
                  <td className="p-0.5 font-mono text-right text-amber-700 font-semibold">{String(r.PRODUCTIVITY)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </_HypoStep>

      <_HypoStep n={3} title="가상 주문 합성" color="violet">
        <div className="text-[10px] text-gray-600">
          <code className="bg-violet-100 px-1 rounded">{hyp.base_order_no}</code> 4 table 복제 →
          ORDER_QD.GRADE_CD = <code className="bg-amber-100 px-1 rounded">{hyp.new_grade}</code> 만 변경
        </div>
        <ul className="text-[10px] mt-1 space-y-0.5">
          {Object.entries(hyp.virtual_order_rows).map(([t, row]) => (
            <li key={t} className="font-mono">
              <span className="text-violet-700">{t}</span>
              <span className="text-gray-400 ml-1">
                {t === "ORDER_QD" ? `GRADE_CD=${(row as Record<string, unknown>).GRADE_CD}` :
                 t === "ORDER_OM" ? `width=${(row as Record<string, unknown>).ORDER_WIDTH} len=${(row as Record<string, unknown>).ORDER_LENGTH}` :
                 `${Object.keys(row).length} 필드 복제`}
              </span>
            </li>
          ))}
        </ul>
      </_HypoStep>

      <_HypoStep n={4} title="Slab 결과 비교 (추론)" color="emerald">
        {hyp.baseline_slab ? (
          <div className="space-y-2">
            <div className="grid grid-cols-3 gap-2 text-[10px]">
              <div className="border border-gray-300 rounded p-1.5">
                <div className="text-gray-500">기존 ({hyp.base_grade})</div>
                <div className="font-mono">
                  두께 {hyp.baseline_slab.slabThickness as number} · 폭 {hyp.baseline_slab.slabWidth as number}
                </div>
                <div className="font-mono text-emerald-700 font-semibold">
                  단중 {Number(hyp.baseline_slab.slabWgt).toFixed(1)}kg
                </div>
              </div>
              <div className="border border-amber-300 bg-amber-50 rounded p-1.5">
                <div className="text-amber-700">가상 ({hyp.new_grade})</div>
                <div className="font-mono">
                  두께 {hyp.projected_slab?.slabThickness as number} · 폭 {hyp.projected_slab?.slabWidth as number}
                </div>
                <div className="font-mono text-amber-800 font-semibold">
                  단중 {Number(hyp.projected_slab?.slabWgt ?? 0).toFixed(1)}kg
                </div>
              </div>
              <div className="border border-red-300 bg-red-50 rounded p-1.5">
                <div className="text-red-700">DIFF</div>
                <div className="font-mono">두께 0 · 폭 0 (강종 무관)</div>
                <div className="font-mono text-red-800 font-semibold">
                  단중 {hyp.diff_summary.find((d) => d.field === "slabWgt")?.delta_pct ?? 0}%
                </div>
              </div>
            </div>
            {hyp.diff_summary.length > 0 && (
              <details className="text-[10px]">
                <summary className="cursor-pointer text-gray-600">전체 diff ({hyp.diff_summary.length}건)</summary>
                <table className="w-full mt-1">
                  <thead><tr className="border-b border-gray-300">
                    <th className="text-left p-0.5">field</th>
                    <th className="text-right p-0.5">before</th>
                    <th className="text-right p-0.5">after</th>
                    <th className="text-right p-0.5">%</th>
                  </tr></thead>
                  <tbody>
                    {hyp.diff_summary.map((d) => (
                      <tr key={d.field} className="border-b border-gray-100">
                        <td className="p-0.5 font-mono">{d.field}</td>
                        <td className="p-0.5 font-mono text-right">{d.before.toFixed(2)}</td>
                        <td className="p-0.5 font-mono text-right text-emerald-700">{d.after.toFixed(2)}</td>
                        <td className="p-0.5 font-mono text-right text-red-700">{d.delta_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}
          </div>
        ) : (
          <div className="text-[10px] text-gray-400">baseline 실행 결과 없음</div>
        )}
      </_HypoStep>

      {hyp.notes.length > 0 && (
        <details className="text-[10px] border border-gray-200 rounded">
          <summary className="px-2 py-1 bg-gray-50 cursor-pointer text-gray-600">분석 노트 ({hyp.notes.length})</summary>
          <ul className="p-2 space-y-1">
            {hyp.notes.map((n, i) => <li key={i} className="text-gray-700">· {n}</li>)}
          </ul>
        </details>
      )}
    </>
  );
}


/** 신규 기준 추가 시나리오 결과 — _NewStandardView.
 *  사용자: "신규 품종 X 가 추가되면 어디 영향?" → 가상 주문 + 시뮬 + 코드 영향 + Java→Python.
 */
function _NewStandardView({ payload, codeMode = "open" }: { payload: Record<string, unknown>; codeMode?: "hide" | "collapsed" | "open" }) {
  const newProduct = payload.new_product_cd as string | null;
  const newGrade = payload.new_grade_cd as string | null;
  const closest = payload.closest_existing_order as Record<string, unknown> | null;
  const useVirtual = payload.use_virtual as boolean;
  const virtualOrder = payload.virtual_order as Record<string, Record<string, unknown>>;
  const baselineSlab = payload.baseline_slab as Record<string, unknown> | null;
  const projectedSlab = payload.projected_slab as Record<string, unknown> | null;
  const diff = (payload.diff as Array<Record<string, unknown>> | undefined) ?? [];
  const notes = (payload.notes as string[] | undefined) ?? [];
  const transpiled = (payload.transpiled_methods as TranspiledMethod[] | undefined) ?? [];
  const codeChanges = (payload.code_changes_needed as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <>
      <div className="bg-gradient-to-r from-rose-600 to-fuchsia-600 text-white rounded-lg p-3 shadow">
        <div className="text-[10px] uppercase tracking-wide opacity-80">신규 기준 추가 시뮬레이션</div>
        <div className="text-sm font-semibold mt-0.5">
          {newProduct && <>신규 품종 <code className="bg-white/20 px-1.5 py-0.5 rounded">{newProduct}</code></>}
          {newGrade && <> · 신규 강종 <code className="bg-white/20 px-1.5 py-0.5 rounded">{newGrade}</code></>}
          {" "}→ 가상 주문 합성 + Slab 결과 추론 + 코드 영향 분석
        </div>
      </div>

      <_HypoStep n={1} title={useVirtual ? "가상 주문 합성 (매칭 기존 주문 없음)" : "매칭 기존 주문 사용"} color="violet">
        {closest && (
          <div className="text-[10px] mb-2">
            <span className="text-gray-500">closest existing order: </span>
            <code className="bg-white px-1.5 py-0.5 rounded border border-violet-200">
              {String(closest.order_no)} (PRODUCT={String(closest.PRODUCT_CD)} · GRADE={String(closest.GRADE_CD)} · score {String(closest.score)})
            </code>
          </div>
        )}
        {useVirtual && Object.keys(virtualOrder).length > 0 && (
          <div className="space-y-1">
            <div className="text-[10px] text-gray-600">합성된 가상 주문 4 table:</div>
            <ul className="text-[10px] space-y-0.5">
              {Object.entries(virtualOrder).map(([t, row]) => (
                <li key={t} className="font-mono">
                  <span className="text-violet-700 font-semibold">{t}</span>
                  <span className="text-gray-500 ml-1">
                    ORDER_NO={String((row as Record<string, unknown>).ORDER_NO)}
                    {t === "ORDER_OM" && <> · PRODUCT_CD={String((row as Record<string, unknown>).PRODUCT_CD)} · width={String((row as Record<string, unknown>).ORDER_WIDTH)}</>}
                    {t === "ORDER_QD" && <> · GRADE_CD={String((row as Record<string, unknown>).GRADE_CD)}</>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </_HypoStep>

      <_HypoStep n={2} title="Slab 결과 추론 (변경 전·후 비교)" color="emerald">
        {baselineSlab && projectedSlab ? (
          <>
            <div className="text-[10px] text-gray-600 mb-1">
              baseline 주문 = <code className="bg-white px-1 rounded">{String(payload.baseline_order_no ?? "?")}</code>
            </div>
            <div className="grid grid-cols-3 gap-2 text-[10px]">
              <div className="border border-gray-300 rounded p-1.5">
                <div className="text-gray-500">기존 (closest)</div>
                <div className="font-mono">
                  두께 {String(baselineSlab.slabThickness)} · 폭 {String(baselineSlab.slabWidth)}
                </div>
                <div className="font-mono text-emerald-700 font-semibold">
                  단중 {Number(baselineSlab.slabWgt ?? 0).toFixed(1)}kg
                </div>
              </div>
              <div className="border border-fuchsia-300 bg-fuchsia-50 rounded p-1.5">
                <div className="text-fuchsia-700">신규 기준 + 가상 주문</div>
                <div className="font-mono">
                  두께 {String(projectedSlab.slabThickness)} · 폭 {String(projectedSlab.slabWidth)}
                </div>
                <div className="font-mono text-fuchsia-800 font-semibold">
                  단중 {Number(projectedSlab.slabWgt ?? 0).toFixed(1)}kg
                </div>
              </div>
              <div className="border border-amber-300 bg-amber-50 rounded p-1.5">
                <div className="text-amber-700">DIFF ({diff.length})</div>
                {diff.length === 0 ? (
                  <div className="font-mono text-gray-500">변경 없음 (추론 기반)</div>
                ) : (
                  <div className="font-mono text-amber-800">
                    {diff.slice(0, 3).map((d) => (
                      <div key={String(d.field)}>{String(d.field)}: {String(d.delta_pct ?? 0)}%</div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="text-[10px] text-gray-400">baseline 결과 없음</div>
        )}
      </_HypoStep>

      <_HypoStep n={3} title="영향받는 Java 코드 → Python 실시간 변환" color="amber">
        {transpiled.length > 0 ? (
          <div className="space-y-2">
            {transpiled.map((m) => <_TranspiledMethodCard key={m.fqn} method={m} />)}
          </div>
        ) : (
          <div className="text-[10px] text-gray-400">영향받는 코드 없음 — DB 룰만 추가하면 됨</div>
        )}
      </_HypoStep>

      <_HypoStep n={4} title="코드 수정 필요 여부" color="sky">
        <ul className="space-y-1.5 text-[11px]">
          {codeChanges.map((c, i) => {
            const sev = String(c.severity);
            const sevColor =
              sev === "high" ? "bg-red-100 text-red-800 border-red-300" :
              sev === "medium" ? "bg-amber-100 text-amber-800 border-amber-300" :
              sev === "info" ? "bg-emerald-100 text-emerald-800 border-emerald-300" :
              "bg-gray-100 text-gray-700 border-gray-300";
            return (
              <li key={i} className="bg-white border border-sky-200 rounded p-2">
                <div className="flex items-start gap-2">
                  <span className={"text-[9px] px-1.5 py-0.5 rounded border font-semibold " + sevColor}>
                    {sev.toUpperCase()}
                  </span>
                  <div className="flex-1">
                    <code className="text-[10px] text-sky-800">{String(c.file)}</code>
                    <div className="text-gray-800 mt-0.5">{String(c.issue)}</div>
                    <div className="text-gray-600 text-[10px] mt-1">
                      <strong>조치:</strong> {String(c.action)}
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </_HypoStep>

      {notes.length > 0 && (
        <details className="text-[10px] border border-gray-200 rounded">
          <summary className="px-2 py-1 bg-gray-50 cursor-pointer text-gray-600">분석 노트 ({notes.length})</summary>
          <ul className="p-2 space-y-1">
            {notes.map((n, i) => <li key={i} className="text-gray-700">· {n}</li>)}
          </ul>
        </details>
      )}
    </>
  );
}

function _HypoStep({ n, title, color, children }: {
  n: number; title: string; color: "sky"|"amber"|"violet"|"emerald"; children: React.ReactNode;
}) {
  const colorMap = {
    sky:     "border-sky-300 bg-sky-50/40",
    amber:   "border-amber-300 bg-amber-50/40",
    violet:  "border-violet-300 bg-violet-50/40",
    emerald: "border-emerald-300 bg-emerald-50/40",
  };
  const badge = {
    sky:     "bg-sky-600",
    amber:   "bg-amber-600",
    violet:  "bg-violet-600",
    emerald: "bg-emerald-600",
  };
  return (
    <div className={"border-2 rounded p-2 " + colorMap[color]}>
      <div className="flex items-center gap-2 mb-2">
        <span className={"text-[10px] w-5 h-5 rounded-full text-white font-bold flex items-center justify-center " + badge[color]}>{n}</span>
        <strong className="text-xs text-gray-800">{title}</strong>
      </div>
      {children}
    </div>
  );
}
