"use client";

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCopy,
  GitPullRequest,
  Loader2,
  Wand2,
} from "lucide-react";
import {
  suggestPatch,
  targetForStep,
  type AutoPRSuggestResponse,
  type FailedCaseDto,
} from "@/lib/simulation/autoPrApi";

interface Props {
  /** 현재 실행한 step_id — 자바 파일/메서드 매핑에 사용. */
  stepId: string;
  /** 샌드박스 결과의 실패 케이스. */
  failures: Array<{
    case_id: string;
    description?: string;
    case_type?: string;
    expected?: Record<string, unknown>;
    actual_output?: Record<string, unknown>;
  }>;
}

/**
 * Auto-PR 카드 — 실패 케이스를 LLM 에 보내 자바 방어 코드 패치 제안 받기.
 *
 * step_id 가 알려진 자바 파일에 매핑되지 않으면 비활성 안내.
 */
export function AutoPRCard({ stepId, failures }: Props) {
  const target = targetForStep(stepId);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AutoPRSuggestResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState<"diff" | "patched" | null>(null);

  if (!target) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/20 p-3 text-[11px] text-muted-foreground">
        <GitPullRequest size={12} className="inline mr-1.5" />
        Auto-PR 자바 패치는 자바 원본과 매핑된 step (예: thickness / slab_count) 에서만 동작합니다.
        현재 step <span className="font-mono">{stepId}</span> 은 매핑이 없습니다.
      </div>
    );
  }

  const onSuggest = async () => {
    setLoading(true);
    setErr(null);
    setResult(null);
    setCopied(null);
    try {
      const failuresDto: FailedCaseDto[] = failures.slice(0, 5).map((f) => ({
        case_id: f.case_id,
        description: f.description ?? "",
        case_type: (f.case_type as FailedCaseDto["case_type"]) ?? "error",
        expected: (f.expected as Record<string, unknown>) ?? {},
        actual_output: (f.actual_output as Record<string, unknown>) ?? {},
      }));
      const r = await suggestPatch({
        java_path: target.java_path,
        method_name: target.method_name,
        class_name: target.class_name,
        failures: failuresDto,
        prefer_llm: true,
      });
      setResult(r);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const copy = async (text: string, kind: "diff" | "patched") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      setErr("클립보드 복사 실패 — 수동으로 선택해 복사해 주세요.");
    }
  };

  return (
    <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-3 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
          <GitPullRequest size={14} className="text-blue-600" />
          Auto-PR — 자바 방어 코드 자동 생성
          <span className="text-[10px] text-muted-foreground font-normal ml-1">
            실패 케이스 → LLM 패치 제안 (검토 후 GitHub PR 활용)
          </span>
        </h4>
        <button
          onClick={onSuggest}
          disabled={loading || failures.length === 0}
          className="inline-flex items-center gap-1 rounded bg-blue-600 text-white px-3 py-1.5 text-xs font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
          {result ? "다시 생성" : "패치 제안 받기"}
        </button>
      </div>

      <div className="text-[11px] text-muted-foreground">
        대상: <span className="font-mono text-foreground">{target.class_name}.{target.method_name}</span>
        {" · "}실패 케이스 {failures.length}건 (상위 5건 LLM 전달)
      </div>

      {err && (
        <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {err}
        </div>
      )}

      {result && (
        <div className="space-y-3">
          {/* 메타 */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
            <Badge label="경로" value={result.suggestion.method === "llm" ? "LLM 생성" : "Fallback"} />
            <Badge label="신뢰도" value={`${(result.suggestion.confidence * 100).toFixed(0)}%`} />
            <Badge label="추가 import" value={`${result.suggestion.additional_imports.length}건`} />
          </div>

          {/* rationale */}
          <div className="rounded border border-amber-500/30 bg-amber-500/5 p-2 text-[11px]">
            <p className="font-medium text-foreground mb-0.5">변환 근거</p>
            <p className="text-muted-foreground leading-relaxed">{result.suggestion.rationale}</p>
          </div>

          {/* unified diff */}
          <div className="rounded border border-border bg-card overflow-hidden">
            <div className="flex items-center justify-between border-b border-border bg-muted/30 px-2 py-1">
              <span className="text-[11px] font-medium text-foreground">Unified Diff</span>
              <button
                onClick={() => copy(result.unified_diff, "diff")}
                className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
              >
                {copied === "diff" ? (
                  <>
                    <CheckCircle2 size={10} className="text-emerald-600" />
                    복사됨
                  </>
                ) : (
                  <>
                    <ClipboardCopy size={10} />
                    복사
                  </>
                )}
              </button>
            </div>
            <pre className="p-2 text-[10px] font-mono leading-relaxed max-h-[280px] overflow-auto">
              <DiffColored text={result.unified_diff} />
            </pre>
          </div>

          {/* patched method */}
          <details className="rounded border border-border bg-card overflow-hidden">
            <summary className="cursor-pointer flex items-center justify-between border-b border-border bg-muted/30 px-2 py-1">
              <span className="text-[11px] font-medium text-foreground">패치된 메서드 전체</span>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  copy(result.suggestion.patched_method, "patched");
                }}
                className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
              >
                {copied === "patched" ? (
                  <>
                    <CheckCircle2 size={10} className="text-emerald-600" />
                    복사됨
                  </>
                ) : (
                  <>
                    <ClipboardCopy size={10} />
                    복사
                  </>
                )}
              </button>
            </summary>
            <pre className="p-2 text-[10px] font-mono leading-relaxed max-h-[320px] overflow-auto bg-zinc-950 text-zinc-100">
              {result.suggestion.patched_method}
            </pre>
          </details>

          {/* risk notes */}
          {result.suggestion.risk_notes.length > 0 && (
            <div className="rounded border border-amber-500/30 bg-amber-500/5 p-2 text-[11px]">
              <p className="font-medium text-foreground mb-1 flex items-center gap-1">
                <AlertTriangle size={11} className="text-amber-600" />
                리스크 / 검토 포인트
              </p>
              <ul className="list-disc list-inside text-muted-foreground space-y-0.5">
                {result.suggestion.risk_notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Badge({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border bg-background px-2 py-1">
      <p className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="text-foreground font-mono truncate">{value}</p>
    </div>
  );
}

function DiffColored({ text }: { text: string }) {
  // 라인별 +/-/@@/--- 색칠
  const lines = text.split("\n");
  return (
    <>
      {lines.map((line, i) => {
        let cls = "text-muted-foreground";
        if (line.startsWith("+++") || line.startsWith("---")) cls = "text-foreground font-semibold";
        else if (line.startsWith("@@")) cls = "text-purple-700 dark:text-purple-300";
        else if (line.startsWith("+")) cls = "text-emerald-700 dark:text-emerald-300";
        else if (line.startsWith("-")) cls = "text-red-700 dark:text-red-300";
        return (
          <div key={i} className={cls}>
            {line || " "}
          </div>
        );
      })}
    </>
  );
}
