"use client";

import { useEffect, useState } from "react";
import {
  Beaker,
  Download,
  Loader2,
  Play,
  Square,
  Sparkles,
} from "lucide-react";
import { useAgent2Stream, type CaseType } from "@/lib/simulation/useAgent2Stream";
import { SandboxConsole } from "./SandboxConsole";
import { ResultChart } from "./ResultChart";
import { RiskHeatmap } from "./RiskHeatmap";
import { HelpPopover } from "./HelpPopover";
import { JsonTable } from "./JsonTable";
import { TimelineScrubber } from "./TimelineScrubber";
import { AutoPRCard } from "./AutoPRCard";
import { OntologyEvidenceToggle } from "./OntologyEvidencePanel";
import { resolveActionFqn } from "@/lib/simulation/stepActionMap";

interface Props {
  initialStepId?: string;
  onConsumeInitial?: () => void;
}

const STEP_OPTIONS = [
  { id: "pipeline", label: "기본 파이프라인", desc: "검증 → 실수율 → 분할 → 매수 → 단중" },
  { id: "pipeline_full", label: "전체 파이프라인 (1~19)", desc: "validate → step 1~19 전체 흐름" },
  { id: "validator", label: "검증 (DG001~005)", desc: "재고/사이즈/포장단중/설계대기량/작업기한일" },
  { id: "productivity", label: "누적 실수율", desc: "활성 공정 실수율 곱" },
  { id: "thickness", label: "Step 1 — 1차 두께 결정", desc: "CAST_SPEC 룩업 → Slab 두께" },
  { id: "width_range", label: "Step 2 — 1차 폭 범위", desc: "CAST ∩ HR_SPEC ∩ EDGING" },
  { id: "length_range", label: "Step 3 — 1차 길이 범위", desc: "CAST ∩ HR_SPEC" },
  { id: "second_wgt", label: "Step 5+6 — 단중 하/상한", desc: "HR_MIN/MAX_WGT 2D 격자 룩업" },
  { id: "max_split", label: "Step 7 — 최대 분할수", desc: "A-a 루프 시작점" },
  { id: "split_range", label: "Step 8 — 분할 범위", desc: "분할수 고려 단중 범위" },
  { id: "slab_count", label: "Step 9 — Slab 매수 ★", desc: "floor(설계대기량 ÷ 실수율 ÷ 단중)" },
  { id: "slab_weight", label: "Step 10 — Slab 단중", desc: "설계대기량 만족 점검" },
  { id: "final_width_range", label: "Step 16 — 최종 폭 범위", desc: "최종 폭 하/상한" },
  { id: "final_length_range", label: "Step 17 — 최종 길이 범위", desc: "최종 길이 하/상한" },
  { id: "target_size", label: "Step 18+19 — 목표 폭/길이", desc: "최종 목표 사이즈" },
];

const CASE_TYPES: { id: CaseType; label: string; tone: string; desc: string }[] = [
  { id: "normal", label: "정상", tone: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300", desc: "통과 기대" },
  { id: "boundary", label: "경계", tone: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300", desc: "임계치" },
  { id: "error", label: "오류", tone: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300", desc: "DG 트리거" },
  { id: "performance", label: "성능", tone: "border-purple-500/40 bg-purple-500/10 text-purple-700 dark:text-purple-300", desc: "대량 Slab" },
];

export function SandboxPanel({ initialStepId, onConsumeInitial }: Props = {}) {
  const [stepId, setStepId] = useState(initialStepId ?? "pipeline");
  const [selectedCases, setSelectedCases] = useState<CaseType[]>(["normal", "boundary"]);
  const [count, setCount] = useState(20);
  const [hrfRule, setHrfRule] = useState("");
  const [hrRule, setHrRule] = useState("");

  const stream = useAgent2Stream();

  useEffect(() => {
    if (initialStepId) {
      setStepId(initialStepId);
      onConsumeInitial?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialStepId]);

  const toggleCase = (c: CaseType) => {
    setSelectedCases((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  };

  const submit = async () => {
    if (selectedCases.length === 0) return;
    const rules: Record<string, string> = {};
    if (hrRule.trim()) rules.hr = hrRule.trim();
    if (hrfRule.trim()) rules.hrf = hrfRule.trim();
    await stream.start({
      target_id: stepId,
      case_types: selectedCases,
      test_count: count,
      rules: Object.keys(rules).length > 0 ? rules : undefined,
    });
  };

  const downloadSkeleton = () => {
    if (!stream.summary?.code_skeleton) return;
    const blob = new Blob([stream.summary.code_skeleton], { type: "text/x-python" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `test_${stepId}_${Date.now()}.py`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
            <Beaker size={20} className="text-primary" />
            안전 가상 실행 (샌드박스)
            <HelpPopover
              title="안전 가상 실행 — 무엇을 하는가"
              body={
                <>
                  <p><b>대상 단계</b>를 골라 <b>케이스 유형</b>(정상/경계/오류/성능) × <b>건수</b> 만큼 테스트 케이스가 자동 생성됩니다 (Hypothesis 라이브러리). 각 케이스는 격리된 안전한 환경에서 실행되고, 결과는 실시간으로 표시.</p>
                  <p>실행 결과는 자바 코드의 <b>라인별 위험도 히트맵</b>으로 색칠 — 🔴 어떤 케이스로도 도달 못 한 분기 = 진짜 위험.</p>
                  <p>「룰 변경」 토글에서 실수율 (HR/HRF) 즉석 변경 가능.</p>
                  <p className="text-[10px]">하단 「pytest 코드 다운로드」 = 현재 결과를 외부에서 재현하기 위한 .py 파일.</p>
                </>
              }
            />
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            테스트 케이스를 자동으로 만들고, 격리된 안전한 환경에서 파이썬으로 실시간 실행합니다.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[400px_1fr]">
        {/* Config card */}
        <section className="rounded-lg border border-border bg-card p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-foreground mb-1.5">
              대상 Step
            </label>
            <select
              value={stepId}
              onChange={(e) => setStepId(e.target.value)}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm"
            >
              {STEP_OPTIONS.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </select>
            <p className="text-[10px] text-muted-foreground mt-1">
              {STEP_OPTIONS.find((s) => s.id === stepId)?.desc}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1.5">
              케이스 유형
            </label>
            <div className="grid grid-cols-2 gap-1.5">
              {CASE_TYPES.map((c) => {
                const active = selectedCases.includes(c.id);
                return (
                  <button
                    key={c.id}
                    onClick={() => toggleCase(c.id)}
                    className={`rounded border px-2 py-1.5 text-left transition-colors ${
                      active ? c.tone : "border-border text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    <div className="text-xs font-medium">{c.label}</div>
                    <div className="text-[10px] opacity-70">{c.desc}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1.5">
              유형별 케이스 수: <span className="text-primary tabular-nums">{count}</span>
            </label>
            <input
              type="range"
              min={1}
              max={100}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              className="w-full accent-primary"
            />
            <p className="text-[10px] text-muted-foreground">
              총 {count * selectedCases.length}건 생성 (격리 subprocess 4-way 병렬)
            </p>
          </div>

          <details className="text-sm">
            <summary className="cursor-pointer text-xs font-medium text-foreground select-none flex items-center gap-1.5">
              <Sparkles size={12} className="text-amber-500" />
              룰 변경 (시나리오 5)
            </summary>
            <div className="mt-2 space-y-2 pl-4 border-l-2 border-border">
              <p className="text-[10px] text-muted-foreground">
                pipeline step에서 누적 실수율 곱 변동을 시뮬. 빈 값 = default.
              </p>
              <div>
                <label className="block text-[10px] text-muted-foreground">HR (default 0.95)</label>
                <input
                  type="text"
                  value={hrRule}
                  onChange={(e) => setHrRule(e.target.value)}
                  placeholder="0.92"
                  className="w-full rounded border border-border bg-background px-2 py-1 text-xs font-mono"
                />
              </div>
              <div>
                <label className="block text-[10px] text-muted-foreground">HRF (default 0.93)</label>
                <input
                  type="text"
                  value={hrfRule}
                  onChange={(e) => setHrfRule(e.target.value)}
                  placeholder="0.85"
                  className="w-full rounded border border-border bg-background px-2 py-1 text-xs font-mono"
                />
              </div>
            </div>
          </details>

          <div className="flex gap-2 pt-2">
            <button
              disabled={stream.running || selectedCases.length === 0}
              onClick={submit}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {stream.running ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  실행 중
                </>
              ) : (
                <>
                  <Play size={14} />
                  실행
                </>
              )}
            </button>
            {stream.running && (
              <button
                onClick={stream.cancel}
                className="inline-flex items-center justify-center rounded-md border border-destructive/30 px-3 py-2 text-sm font-medium text-destructive hover:bg-destructive/10"
                aria-label="cancel"
              >
                <Square size={14} />
              </button>
            )}
          </div>

          {stream.summary && (
            <button
              onClick={downloadSkeleton}
              className="w-full inline-flex items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-xs font-medium text-foreground hover:bg-muted"
            >
              <Download size={12} />
              pytest 코드 다운로드
            </button>
          )}

          {/* 온톨로지 근거 — 어떤 ontology action 기반인지 */}
          <OntologyEvidenceToggle
            actionFqn={resolveActionFqn(stepId)}
            label={`📚 이 단계의 온톨로지 근거 (${stepId} → ${resolveActionFqn(stepId)})`}
          />

          {stream.error && (
            <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {stream.error}
            </div>
          )}
        </section>

        {/* Console + chart */}
        <section className="space-y-4">
          <div className="h-72">
            <SandboxConsole
              cases={stream.cases}
              progress={stream.progress}
              running={stream.running}
            />
          </div>

          <ResultChart summary={stream.summary} />

          {/* Time-travel scrubber — case_done 풀 payload 시계열 재생 */}
          {stream.casesDetailed.length > 0 && <TimelineScrubber cases={stream.casesDetailed} />}

          {stream.summary?.heatmap && (
            <RiskHeatmap heatmap={stream.summary.heatmap} />
          )}

          {stream.failures.length > 0 && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 space-y-3">
              <h4 className="text-sm font-semibold text-destructive">
                기대 불일치 케이스 ({stream.failures.length}건)
              </h4>

              {/* Auto-PR — 실패 케이스 → LLM 자바 패치 제안 */}
              <AutoPRCard stepId={stepId} failures={stream.failures} />
              <div className="max-h-[28rem] overflow-y-auto space-y-3 pr-1">
                {stream.failures.slice(0, 20).map((f) => (
                  <details
                    key={f.case_id}
                    className="rounded border border-border bg-background p-2 text-xs"
                    open
                  >
                    <summary className="cursor-pointer flex items-center gap-2 mb-2 select-none">
                      <span className="font-mono text-destructive">{f.case_id}</span>
                      <span className="text-muted-foreground flex-1 truncate">{f.description}</span>
                    </summary>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-2 mt-1">
                      <JsonTable
                        data={f.expected}
                        caption="expected (기대 결과)"
                        maxRows={12}
                      />
                      <JsonTable
                        data={f.actual_output}
                        caption="actual (실제 결과)"
                        maxRows={20}
                      />
                    </div>
                  </details>
                ))}
                {stream.failures.length > 20 && (
                  <div className="text-[10px] text-muted-foreground italic text-center py-1">
                    +{stream.failures.length - 20}건 더 있음 (상위 20건만 표시)
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
